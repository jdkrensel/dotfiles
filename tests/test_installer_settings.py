"""Integration tests for DotfilesInstaller.setup_claude_settings — the step that
merges the shared settings fragment (hooks, statusLine) into each Claude
profile's machine-local settings.json."""

import json
from pathlib import Path

from src.installer.installer import DotfilesInstaller


def _installer_with_home(home: Path) -> DotfilesInstaller:
    inst = DotfilesInstaller()
    inst.home_dir = home  # redirect writes to an isolated tmp home
    return inst


def test_creates_settings_when_absent(tmp_path):
    inst = _installer_with_home(tmp_path)
    assert inst.setup_claude_settings() is True
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert set(settings["hooks"]) == {"PreToolUse", "PostToolUse"}
    assert not (tmp_path / ".claude" / "settings.json.bak").exists()


def test_preserves_scalars_and_backs_up(tmp_path):
    cdir = tmp_path / ".claude"
    cdir.mkdir()
    original = {"model": "opus", "skipDangerousModePermissionPrompt": True}
    (cdir / "settings.json").write_text(json.dumps(original))

    inst = _installer_with_home(tmp_path)
    assert inst.setup_claude_settings() is True

    settings = json.loads((cdir / "settings.json").read_text())
    assert settings["model"] == "opus"
    assert settings["skipDangerousModePermissionPrompt"] is True
    assert "hooks" in settings
    assert json.loads((cdir / "settings.json.bak").read_text()) == original


def test_idempotent_no_rewrite(tmp_path):
    inst = _installer_with_home(tmp_path)
    inst.setup_claude_settings()
    first = (tmp_path / ".claude" / "settings.json").read_text()
    assert inst.setup_claude_settings() is True
    assert (tmp_path / ".claude" / "settings.json").read_text() == first


def test_invalid_json_is_backed_up_and_rewritten(tmp_path):
    cdir = tmp_path / ".claude"
    cdir.mkdir()
    (cdir / "settings.json").write_text("this is not json")

    inst = _installer_with_home(tmp_path)
    assert inst.setup_claude_settings() is True

    settings = json.loads((cdir / "settings.json").read_text())
    assert "hooks" in settings
    assert (cdir / "settings.json.bak").read_text() == "this is not json"


def test_leaves_settings_local_untouched(tmp_path):
    cdir = tmp_path / ".claude"
    cdir.mkdir()
    local = {"permissions": {"allow": ["Bash(aws:*)"]}}
    (cdir / "settings.local.json").write_text(json.dumps(local))

    inst = _installer_with_home(tmp_path)
    inst.setup_claude_settings()

    assert json.loads((cdir / "settings.local.json").read_text()) == local


def test_default_profile_gets_status_line(tmp_path):
    inst = _installer_with_home(tmp_path)
    assert inst.setup_claude_settings() is True
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert settings["statusLine"]["type"] == "command"


def test_bedrock_profile_gets_status_line_but_not_hooks(tmp_path):
    (tmp_path / ".claude-bedrock").mkdir()
    inst = _installer_with_home(tmp_path)
    assert inst.setup_claude_settings() is True

    settings = json.loads((tmp_path / ".claude-bedrock" / "settings.json").read_text())
    assert settings["statusLine"]["type"] == "command"
    assert "hooks" not in settings


def test_bedrock_profile_skipped_when_absent(tmp_path):
    inst = _installer_with_home(tmp_path)
    assert inst.setup_claude_settings() is True
    assert not (tmp_path / ".claude-bedrock").exists()


def test_bedrock_merge_preserves_existing_settings(tmp_path):
    bdir = tmp_path / ".claude-bedrock"
    bdir.mkdir()
    original = {"model": "opus", "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": []}]}}
    (bdir / "settings.json").write_text(json.dumps(original))

    inst = _installer_with_home(tmp_path)
    assert inst.setup_claude_settings() is True

    settings = json.loads((bdir / "settings.json").read_text())
    assert settings["model"] == "opus"
    assert settings["hooks"] == original["hooks"]  # bedrock hooks untouched
    assert "statusLine" in settings
