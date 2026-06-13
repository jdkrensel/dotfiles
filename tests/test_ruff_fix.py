"""Tests for the PostToolUse ruff hook (Python import/type-hint enforcement)."""

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUFF_FIX_PATH = REPO_ROOT / "src" / "assets" / "claude" / "hooks" / "ruff_fix.py"


def _load_ruff_fix():
    spec = importlib.util.spec_from_file_location("ruff_fix_under_test", RUFF_FIX_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_fake_ruff(venv_bin: Path, body: str) -> None:
    venv_bin.mkdir(parents=True, exist_ok=True)
    ruff = venv_bin / "ruff"
    ruff.write_text(body)
    ruff.chmod(0o755)


def test_non_python_file_noop(run_hook):
    result = run_hook("ruff_fix.py", {"tool_input": {"file_path": "/tmp/notes.txt"}, "cwd": "/tmp"})
    assert result.returncode == 0
    assert result.stderr.strip() == ""


def test_missing_python_file_noop(run_hook):
    result = run_hook("ruff_fix.py", {"tool_input": {"file_path": "/tmp/does_not_exist.py"}, "cwd": "/tmp"})
    assert result.returncode == 0


def test_malformed_json_noop(run_hook_raw):
    result = run_hook_raw("ruff_fix.py", "not json")
    assert result.returncode == 0


def test_find_ruff_prefers_project_venv(tmp_path):
    module = _load_ruff_fix()
    _write_fake_ruff(tmp_path / ".venv" / "bin", "#!/bin/sh\nexit 0\n")
    assert module.find_ruff(str(tmp_path)) == str(tmp_path / ".venv" / "bin" / "ruff")


def test_find_ruff_none_when_absent(tmp_path, monkeypatch):
    module = _load_ruff_fix()
    monkeypatch.setattr(module.shutil, "which", lambda _: None)
    assert module.find_ruff(str(tmp_path)) is None


def test_reports_unfixable_violations(run_hook, tmp_path):
    _write_fake_ruff(
        tmp_path / ".venv" / "bin",
        '#!/bin/sh\necho "sample.py:5:1: E402 module import not at top"\nexit 1\n',
    )
    sample = tmp_path / "sample.py"
    sample.write_text("x = 1\n")
    result = run_hook("ruff_fix.py", {"tool_input": {"file_path": str(sample)}, "cwd": str(tmp_path)})
    assert result.returncode == 2
    assert "E402" in result.stderr


def test_clean_file_exit_zero(run_hook, tmp_path):
    _write_fake_ruff(tmp_path / ".venv" / "bin", "#!/bin/sh\nexit 0\n")
    sample = tmp_path / "sample.py"
    sample.write_text("x = 1\n")
    result = run_hook("ruff_fix.py", {"tool_input": {"file_path": str(sample)}, "cwd": str(tmp_path)})
    assert result.returncode == 0
    assert result.stderr.strip() == ""
