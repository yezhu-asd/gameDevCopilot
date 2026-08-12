"""Orchestrate the generate -> verify -> fix loop."""
from __future__ import annotations

import logging
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from agents import coder
from core import config
from core.verifier import verify_project, _check_godot3_apis

logger = logging.getLogger(__name__)


@dataclass
class RunRecord:
    """One generate-or-fix attempt: what was written and how verification went."""
    attempt: int
    action: str  # "generate" | "fix"
    files: dict
    output_dir: Path
    result: object = None

    @property
    def passed(self) -> bool:
        return self.result is not None and self.result.passed


@dataclass
class PipelineResult:
    spec: str
    success: bool
    final_dir: Path | None
    runs: list[RunRecord] = field(default_factory=list)

    @property
    def rounds_used(self) -> int:
        return len(self.runs)

    @property
    def last_errors(self) -> list[str]:
        if not self.runs:
            return []
        last = self.runs[-1]
        return [] if last.result is None else last.result.errors


def run_pipeline(spec: str, output_root: Path, model=None, max_rounds: int | None = None,
                 on_progress=None) -> PipelineResult:
    """Generate a game from `spec`, verifying each attempt headlessly.

    Writes each attempt into a fresh timestamped subdirectory under output_root.
    `on_progress` is an optional callable(event: str, data: dict) invoked as the
    pipeline advances (used by the web UI to stream progress).
    """
    max_rounds = max_rounds or config.MAX_FIX_ROUNDS
    output_root.mkdir(parents=True, exist_ok=True)
    record = PipelineResult(spec=spec, success=False, final_dir=None)

    def _emit(event: str, data: dict) -> None:
        if on_progress is not None:
            on_progress(event, data)

    _emit("start", {"spec": spec})
    files = coder.generate_project(
        spec, model=model,
        on_phase=lambda phase: _emit("phase", {"phase": phase}),
    )
    _emit("generated", {"n_files": len(files)})
    files = normalize_files(files)
    attempt_dir = _make_attempt_dir(output_root, "gen")
    _write_files(attempt_dir, files)
    _emit("verifying", {"round": 1, "action": "generate"})
    result = verify_project(attempt_dir)
    static_errors = _check_godot3_apis(files)
    if static_errors:
        result.errors = static_errors + result.errors
    record.runs.append(RunRecord(attempt=1, action="generate", files=files, output_dir=attempt_dir, result=result))
    _emit("verified", {"round": 1, "passed": result.passed, "errors": result.errors[:5]})
    logger.info("[attempt 1/generate] errors=%d (static=%d)", result.error_count, len(static_errors))

    round_no = 2
    while not result.passed and round_no <= max_rounds + 1:
        _emit("fixing", {"round": round_no, "errors": result.errors[:5]})
        files = coder.fix_project(spec, result.errors, files, model=model)
        files = normalize_files(files)
        attempt_dir = _make_attempt_dir(output_root, f"fix{round_no - 1}")
        _write_files(attempt_dir, files)
        _emit("verifying", {"round": round_no, "action": "fix"})
        result = verify_project(attempt_dir)
        static_errors = _check_godot3_apis(files)
        if static_errors:
            result.errors = static_errors + result.errors
        record.runs.append(RunRecord(attempt=round_no, action="fix", files=files, output_dir=attempt_dir, result=result))
        _emit("verified", {"round": round_no, "passed": result.passed, "errors": result.errors[:5]})
        logger.info("[attempt %d/fix] errors=%d (static=%d)", round_no, result.error_count, len(static_errors))
        round_no += 1

    record.success = result.passed
    record.final_dir = attempt_dir if result.passed else None
    _emit("done", {"success": record.success, "final_dir": str(record.final_dir) if record.final_dir else None,
                   "rounds": len(record.runs)})
    return record


def _make_attempt_dir(output_root: Path, tag: str) -> Path:
    """Create an attempt dir without depending on time-based uniqueness."""
    idx = 0
    while True:
        d = output_root / f"attempt_{tag}_{idx}"
        if not d.exists():
            d.mkdir(parents=True)
            return d
        idx += 1


def _write_files(project_dir: Path, files: dict) -> None:
    for rel, content in files.items():
        target = project_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


# Mechanical Godot 3 -> 4 renames applied to model output. Keys are regexes;
# the negative lookahead stops `StaticBody` from rewriting the valid StaticBody2D.
GODOT3_TO_4 = {
    re.compile(r"KinematicBody2D"): "CharacterBody2D",
    re.compile(r"KinematicBody(?!2D|3D)"): "CharacterBody2D",
    re.compile(r"StaticBody(?!2D|3D)"): "StaticBody2D",
}


def normalize_files(files: dict) -> dict:
    """Apply deterministic fixes before verification.

    Weak models often emit Godot 3 syntax or malformed tscn; this shim fixes
    the exact mechanical problems so the fix loop only handles logic errors.
    """
    changed = 0
    out: dict[str, str] = {}
    for path, content in files.items():
        text = content
        for pattern, replacement in GODOT3_TO_4.items():
            new_text, n = pattern.subn(replacement, text)
            changed += n
            text = new_text
        if path.endswith(".tscn"):
            fixed = normalize_tscn(text)
            if fixed != text:
                changed += 1
                text = fixed
        out[path] = text
    if changed:
        logger.info("[normalize] applied %d fixes", changed)
    return out


def normalize_tscn(text: str) -> str:
    """Reorder a Godot 4 .tscn so all ext_resource lines precede sub_resource.

    Godot fails with "Unknown tag 'ext_resource'" if an ext_resource appears
    after a sub_resource. Models frequently get this order wrong.
    """
    lines = text.splitlines()
    header: list[str] = []
    ext: list[str] = []
    subs: list[str] = []
    nodes: list[str] = []
    current: list[str] = header

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("[ext_resource"):
            current = ext
            ext.append(line)
        elif stripped.startswith("[sub_resource"):
            current = subs
            subs.append(line)
        elif stripped.startswith("[node"):
            current = nodes
            nodes.append(line)
        else:
            current.append(line)

    if not subs:
        return text  # nothing to reorder

    # Rebuild: header, ext_resources, sub_resources, then nodes.
    reordered = header + ext + subs + nodes
    result = "\n".join(reordered)
    return result + ("\n" if text.endswith("\n") else "")


def make_temp_output() -> Path:
    return Path(tempfile.mkdtemp(prefix="gdc_run_"))


def cleanup(output_root: Path) -> None:
    if output_root.exists():
        shutil.rmtree(output_root, ignore_errors=True)
