"""Tests for the gitignore-guard PreToolUse hook (work machine).

Gitignored files are where credentials live (settings.py, *.env), so the hook
hard-denies (exit 2) any Read/Grep/Glob of one, and any Bash command whose
arguments name one. Everything else passes with exit 0.

Each test builds its own git repo under tmp_path. Git's global and system
config are switched off, and HOME points into tmp_path, so neither a user-level
excludesFile nor the default ~/.config/git/ignore can change what counts as
ignored.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "assets/machines/work/claude/hooks/gitignore-guard.sh"

GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


@pytest.fixture(autouse=True)
def isolated_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the real user's git ignore files out of every git call."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    for key, value in GIT_ENV.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A git repo holding one ignored file (secret.env) and one tracked-able file."""
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("secret.env\n")
    (root / "secret.env").write_text("TOKEN=x\n")
    (root / "public.txt").write_text("hello\n")
    return root


def run_guard(payload: dict[str, Any]) -> int:
    result = subprocess.run(
        ["bash", str(HOOK)],
        check=False,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    return result.returncode


def tool(name: str, path: str, cwd: Path) -> dict[str, Any]:
    """A tool call shaped like the real one: Read sends file_path, Grep and Glob send path."""
    key = "file_path" if name in ("Read", "Write") else "path"
    return {"tool_name": name, "cwd": str(cwd), "tool_input": {key: path}}


def bash(command: str, cwd: Path) -> dict[str, Any]:
    return {"tool_name": "Bash", "cwd": str(cwd), "tool_input": {"command": command}}


@pytest.mark.parametrize("name", ["Read", "Grep", "Glob"])
def test_ignored_file_is_denied(repo: Path, name: str) -> None:
    assert run_guard(tool(name, str(repo / "secret.env"), repo)) == 2


@pytest.mark.parametrize("name", ["Read", "Grep", "Glob"])
def test_tracked_file_passes(repo: Path, name: str) -> None:
    assert run_guard(tool(name, str(repo / "public.txt"), repo)) == 0


@pytest.mark.parametrize("path", ["secret.env", "./secret.env"])
def test_relative_path_resolves_against_cwd(repo: Path, path: str) -> None:
    assert run_guard(tool("Read", path, repo)) == 2


def test_missing_ignored_file_passes(repo: Path) -> None:
    """Only an existing file is checked; a path that names nothing cannot leak."""
    (repo / "secret.env").unlink()
    assert run_guard(tool("Read", str(repo / "secret.env"), repo)) == 0


def test_file_outside_any_repo_passes(tmp_path: Path) -> None:
    loose = tmp_path / "secret.env"
    loose.write_text("TOKEN=x\n")
    assert run_guard(tool("Read", str(loose), tmp_path)) == 0


@pytest.mark.parametrize(
    "command",
    ["cat secret.env", "cat 'secret.env'", 'cat "secret.env"', "grep TOKEN secret.env | head", "echo hi; cat secret.env"],
    ids=["bare", "single-quoted", "double-quoted", "piped", "chained"],
)
def test_bash_naming_an_ignored_file_is_denied(repo: Path, command: str) -> None:
    assert run_guard(bash(command, repo)) == 2


def test_bash_naming_only_tracked_files_passes(repo: Path) -> None:
    assert run_guard(bash("cat public.txt", repo)) == 0


@pytest.mark.parametrize("command", ["tool --file=secret.env", "tool -secret.env"], ids=["key-value", "flag"])
def test_bash_flag_tokens_are_not_checked(repo: Path, command: str) -> None:
    """Best-effort by design: tokens shaped like flags or assignments are skipped."""
    assert run_guard(bash(command, repo)) == 0


def test_other_tools_pass(repo: Path) -> None:
    assert run_guard(tool("Write", str(repo / "secret.env"), repo)) == 0
