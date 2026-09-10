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
    assert set(settings["hooks"]) == {"PreToolUse", "PostToolUse", "SessionStart", "Stop"}
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


def test_bedrock_profile_gets_status_line_but_not_the_default_profile_hooks(tmp_path):
    (tmp_path / ".claude-bedrock").mkdir()
    inst = _installer_with_home(tmp_path)
    assert inst.setup_claude_settings() is True

    settings = json.loads((tmp_path / ".claude-bedrock" / "settings.json").read_text())
    assert settings["statusLine"]["type"] == "command"
    assert set(settings["hooks"]) == {"Stop"}  # only the all-profiles fragment


def test_every_profile_gets_the_all_profiles_hooks(tmp_path):
    (tmp_path / ".claude-bedrock").mkdir()
    inst = _installer_with_home(tmp_path)
    assert inst.setup_claude_settings() is True

    for profile in (".claude", ".claude-bedrock"):
        settings = json.loads((tmp_path / profile / "settings.json").read_text())
        commands = [
            hook["command"]
            for group in settings["hooks"]["Stop"]
            for hook in group["hooks"]
        ]
        assert any("turn_token_usage.py" in command for command in commands)


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
    # The bedrock profile's own hooks survive; only Stop is added alongside them.
    assert settings["hooks"]["PreToolUse"] == original["hooks"]["PreToolUse"]
    assert "statusLine" in settings


def test_reports_a_missing_all_profiles_fragment(tmp_path):
    """Both fragments are required assets: a silent skip would leave the Stop hook
    installed in no profile at all, with the install still reporting success."""
    dotfiles = tmp_path / "dotfiles"
    assets = dotfiles / "src" / "assets" / "claude"
    assets.mkdir(parents=True)
    (assets / "settings.shared.json").write_text(json.dumps({"hooks": {}}))

    inst = _installer_with_home(tmp_path / "home")
    inst.dotfiles_dir = dotfiles

    assert inst.setup_claude_settings() is False
