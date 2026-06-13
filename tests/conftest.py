"""Shared fixtures for the dotfiles test suite."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.dont_write_bytecode = True

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / "src" / "assets" / "claude" / "hooks"


def _invoke(script_name: str, stdin_text: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOKS_DIR / script_name)],
        input=stdin_text,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def hooks_dir() -> Path:
    return HOOKS_DIR


@pytest.fixture
def run_hook():
    """Run a hook with a dict payload serialized to JSON on stdin."""

    def _run(script_name: str, payload: dict) -> subprocess.CompletedProcess:
        return _invoke(script_name, json.dumps(payload))

    return _run


@pytest.fixture
def run_hook_raw():
    """Run a hook with raw text on stdin (for malformed-input tests)."""

    def _run(script_name: str, raw: str) -> subprocess.CompletedProcess:
        return _invoke(script_name, raw)

    return _run
