"""LangGraph workflow for the generate -> verify -> fix loop.

The graph mirrors the linear pipeline as a state machine so the flow is
inspectable and extensible (add nodes for planning / GDD / engine validation):

    generate -> normalize -> verify --passed--> END
                                  --failed, has rounds--> fix -> normalize -> verify ...
                                  --failed, no rounds--> END (failed)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Optional

from agents import coder
from core import config
from core.pipeline import RunRecord, _make_attempt_dir, _write_files, normalize_files
from core.verifier import _check_godot3_apis, verify_project

logger = logging.getLogger(__name__)

from langgraph.graph import END, StateGraph


@dataclass
class WorkflowResult:
    """Outcome of a workflow run, structurally compatible with PipelineResult."""
    spec: str
    success: bool
    final_dir: Optional[Path]
    runs: list = field(default_factory=list)

    @property
    def rounds_used(self) -> int:
        return len(self.runs)

    @property
    def last_errors(self) -> list:
        if not self.runs:
            return []
        last = self.runs[-1]
        return [] if last.result is None else last.result.errors


class GameState(dict):
    """State passed between graph nodes. dict subclass so LangGraph mutates it in place."""
    spec: str = ""
    output_root: Optional[Path] = None
    model: Any = None
    max_rounds: int = 0
    files: dict = {}
    errors: list = []
    attempts: int = 0
    runs: list = []
    success: bool = False
    final_dir: Optional[Path] = None


def _generate(state: GameState) -> dict:
    spec = state["spec"]
    files = coder.generate_project(spec, model=state["model"])
    state["files"] = files
    return {"files": files}


def _normalize(state: GameState) -> dict:
    files = normalize_files(state["files"])
    state["files"] = files
    return {"files": files}


def _verify(state: GameState) -> dict:
    files = state["files"]
    attempt_dir = _make_attempt_dir(state["output_root"], "gen" if state["attempts"] == 0 else f"fix{state['attempts']}")
    _write_files(attempt_dir, files)
    result = verify_project(attempt_dir)
    static_errors = _check_godot3_apis(files)
    if static_errors:
        result.errors = static_errors + result.errors
    state["attempts"] += 1
    state["errors"] = result.errors
    state["runs"].append(RunRecord(attempt=state["attempts"], action="generate" if state["attempts"] == 1 else "fix",
                                   files=files, output_dir=attempt_dir, result=result))
    logger.info("[workflow attempt %d] errors=%d (static=%d)",
                state["attempts"], result.error_count, len(static_errors))
    if result.passed:
        state["success"] = True
        state["final_dir"] = attempt_dir
    return {"errors": result.errors, "attempts": state["attempts"], "runs": state["runs"],
            "success": state["success"], "final_dir": state["final_dir"]}


def _fix(state: GameState) -> dict:
    spec = state["spec"]
    files = coder.fix_project(spec, state["errors"], state["files"], model=state["model"])
    state["files"] = files
    return {"files": files}


def _should_fix(state: GameState) -> str:
    if state["success"]:
        return "end"
    if state["attempts"] >= state["max_rounds"] + 1:
        return "end"  # ran out of rounds
    return "fix"


def build_graph():
    """Build and return the compiled LangGraph StateGraph."""
    graph = StateGraph(GameState)

    graph.add_node("generate", _generate)
    graph.add_node("normalize", _normalize)
    graph.add_node("verify", _verify)
    graph.add_node("fix", _fix)

    graph.set_entry_point("generate")
    graph.add_edge("generate", "normalize")
    graph.add_edge("normalize", "verify")
    graph.add_conditional_edges("verify", _should_fix, {"fix": "fix", "end": END})
    graph.add_edge("fix", "normalize")

    return graph.compile()


def run_workflow(spec: str, output_root: Path, model=None, max_rounds: int | None = None) -> WorkflowResult:
    """Run the LangGraph workflow. Mirrors run_pipeline's signature/result."""
    max_rounds = max_rounds or config.MAX_FIX_ROUNDS
    output_root.mkdir(parents=True, exist_ok=True)
    graph = build_graph()

    state = GameState(
        spec=spec,
        output_root=output_root,
        model=model,
        max_rounds=max_rounds,
        files={},
        errors=[],
        attempts=0,
        runs=[],
        success=False,
        final_dir=None,
    )
    final_state = graph.invoke(state)
    # invoke() returns the post-run state; prefer it over the input dict.
    return WorkflowResult(
        spec=final_state["spec"],
        success=bool(final_state["success"]),
        final_dir=final_state["final_dir"],
        runs=final_state["runs"],
    )
