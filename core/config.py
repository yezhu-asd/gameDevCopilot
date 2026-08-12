"""Project-wide configuration."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Absolute paths ---------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools"
GODOT_EXE = TOOLS_DIR / "Godot_v4.7.1-stable_win64.exe"

# Examples ---------------------------------------------------------------------
EXAMPLES_DIR = PROJECT_ROOT / "examples"
SMOKE_EXAMPLE = EXAMPLES_DIR / "playground"  # known-good project used in tests

# Generation -------------------------------------------------------------------
MAX_FIX_ROUNDS = int(os.getenv("MAX_FIX_ROUNDS", "3"))
MAX_FILES_PER_GEN = int(os.getenv("MAX_FILES_PER_GEN", "8"))

# LLM --------------------------------------------------------------------------
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai-compatible")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen-plus")

# Verifier ---------------------------------------------------------------------
VERIFY_TIMEOUT_SEC = int(os.getenv("VERIFY_TIMEOUT_SEC", "30"))


def ensure_tools() -> Path:
    """Return the Godot binary path, raising if missing."""
    if not GODOT_EXE.exists():
        raise FileNotFoundError(
            f"Godot binary not found at {GODOT_EXE}. "
            "Download it and place it under tools/, or set GODOT_EXE."
        )
    return GODOT_EXE
