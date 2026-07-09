"""Integration tests for SymlinkManager.setup_claude_statusline — symlinks the
shared status line script (claude/statusline.sh) into each Claude profile that
exists on the machine (default ~/.claude and the Bedrock ~/.claude-bedrock
profile).

These drive the installer against a synthetic fake-dotfiles tree so the behavior
is tested directly, independent of the script that actually ships in the repo."""

from pathlib import Path

from src.installer.printer import Printer
from src.installer.symlinker import SymlinkManager


def _make_script(dotfiles: Path) -> Path:
    """Write a minimal status line script into the fake dotfiles tree."""
    claude_dir = dotfiles / "src" / "assets" / "claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    path = claude_dir / "statusline.sh"
    path.write_text("#!/bin/bash\necho status\n")
    return path


def _manager(home: Path, dotfiles: Path) -> SymlinkManager:
    manager = SymlinkManager(Printer(), dotfiles)
    manager.home_dir = home  # redirect symlink destinations to an isolated tmp home
    return manager


def test_fails_when_script_absent(tmp_path):
    """Missing tracked script is an error, not a silent no-op — the shared
    settings fragment points every profile at it."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    (dotfiles / "src" / "assets" / "claude").mkdir(parents=True)  # no statusline.sh
    home.mkdir()
    assert _manager(home, dotfiles).setup_claude_statusline() is False
    assert not (home / ".claude").exists()


def test_links_into_default_profile(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_script(dotfiles)
    home.mkdir()
    assert _manager(home, dotfiles).setup_claude_statusline() is True

    link = home / ".claude" / "statusline.sh"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_skips_bedrock_when_absent(tmp_path):
    """Bedrock profile is only populated if its root dir already exists."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_script(dotfiles)
    home.mkdir()
    assert _manager(home, dotfiles).setup_claude_statusline() is True
    assert not (home / ".claude-bedrock").exists()


def test_links_into_bedrock_when_present(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_script(dotfiles)
    (home / ".claude-bedrock").mkdir(parents=True)
    assert _manager(home, dotfiles).setup_claude_statusline() is True

    link = home / ".claude-bedrock" / "statusline.sh"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_idempotent_across_repeated_installs(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_script(dotfiles)
    home.mkdir()
    manager = _manager(home, dotfiles)
    assert manager.setup_claude_statusline() is True
    assert manager.setup_claude_statusline() is True  # second run is a no-op-shaped success

    link = home / ".claude" / "statusline.sh"
    assert link.is_symlink() and link.resolve() == src.resolve()
