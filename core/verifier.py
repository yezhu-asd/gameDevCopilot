"""Run a Godot project in headless mode and collect its output."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from core import config

# Lines that indicate a genuine script/resource problem.
ERROR_PATTERNS = (
    "ERROR:",
    "SCRIPT ERROR:",
    "Parse Error",
    "Parser Error",
    "Invalid call",
    "Attempt to call",
    "Cannot open file",
    "Failed loading resource",
    "Nonexistent function",
    "Invalid access",
    "out of bounds",
)


@dataclass
class VerifyResult:
    project_dir: Path
    exit_code: int
    output: str
    errors: list[str] = field(default_factory=list)
    timeout: bool = False

    @property
    def passed(self) -> bool:
        return not self.errors

    @property
    def error_count(self) -> int:
        return len(self.errors)


# Godot 3 API patterns that must not appear in a Godot 4 project.
# Values are regexes; (?!2D|3D) avoids flagging the valid StaticBody2D/3D.
GODOT3_PATTERNS = {
    r"KinematicBody(?!2D|3D)": "Godot 4 中 KinematicBody 已改为 CharacterBody3D/CharacterBody2D",
    r"KinematicBody2D": "Godot 4 中 KinematicBody2D 已改为 CharacterBody2D",
    r"move_and_collide\(": "Godot 4 请使用 move_and_slide()",
    r"translate\(Vector": "Godot 4 移动请用 velocity + move_and_slide()，不要用 translate()",
    r"StaticBody(?!2D|3D)": "Godot 4 的 StaticBody 已改名 StaticBody2D/StaticBody3D",
}


def _extract_errors(output: str) -> list[str]:
    """Pull distinct lines that look like Godot script/resource errors."""
    errors: list[str] = []
    seen: set[str] = set()
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(p in line for p in ERROR_PATTERNS):
            key = re.sub(r"at:.*$", "", line).strip()
            if key not in seen:
                seen.add(key)
                errors.append(line)
    return errors


def _check_godot3_apis(files: dict) -> list[str]:
    """Flag obsolete Godot 3 API usage that would confuse the fix loop."""
    issues: list[str] = []
    for path, content in files.items():
        if not (path.endswith(".gd") or path.endswith(".tscn")):
            continue
        for pattern, hint in GODOT3_PATTERNS.items():
            if re.search(pattern, content):
                issues.append(
                    f"[Godot4] {path}: 包含 Godot 3 写法 {pattern!r}，{hint}"
                )
    return issues


def run_headless(project_dir: Path, timeout: int) -> VerifyResult:
    godot = config.ensure_tools()
    cmd = [
        str(godot),
        "--headless",
        "--path", str(project_dir),
        "--quit-after", "5",
    ]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        output = proc.stdout + proc.stderr
        errors = _extract_errors(output)
        return VerifyResult(
            project_dir=project_dir,
            exit_code=proc.returncode,
            output=output,
            errors=errors,
        )
    except subprocess.TimeoutExpired:
        return VerifyResult(
            project_dir=project_dir,
            exit_code=-1,
            output="",
            errors=["Timeout: headless run exceeded limit"],
            timeout=True,
        )


def verify_project(project_dir: Path, timeout: int | None = None) -> VerifyResult:
    return run_headless(project_dir, timeout or config.VERIFY_TIMEOUT_SEC)
