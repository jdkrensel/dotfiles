"""Integration tests for SymlinkManager.setup_claude_commands — symlinks the
shared Claude slash-command files (commands/*.md, e.g. /commit) into each Claude
profile that exists on the machine (default ~/.claude and the Bedrock
~/.claude-bedrock profile).

These drive the installer against a synthetic fake-dotfiles tree so the behavior
is tested directly, independent of which command files actually ship in the repo."""

from pathlib import Path

from src.installer.printer import Printer
from src.installer.symlinker import SymlinkManager


def _make_command(commands_dir: Path, name: str) -> Path:
    """Write a minimal slash-command file into the fake dotfiles commands dir."""
    commands_dir.mkdir(parents=True, exist_ok=True)
    path = commands_dir / name
    path.write_text("---\ndescription: do a thing\n---\n\n# command body\n")
    return path


def _manager(home: Path, dotfiles: Path) -> SymlinkManager:
    manager = SymlinkManager(Printer(), dotfiles)
    manager.home_dir = home  # redirect symlink destinations to an isolated tmp home
    return manager


def _commands_dir(dotfiles: Path) -> Path:
    return dotfiles / "src" / "assets" / "claude" / "commands"


def test_noop_when_commands_dir_absent(tmp_path):
    """No commands dir at all → no-op, no profile dirs created."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    (dotfiles / "src" / "assets" / "claude").mkdir(parents=True)  # no commands/
    home.mkdir()
    assert _manager(home, dotfiles).setup_claude_commands() is True
    assert not (home / ".claude").exists()


def test_noop_when_commands_dir_empty(tmp_path):
    """commands/ exists but holds no .md files → no-op."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _commands_dir(dotfiles).mkdir(parents=True)  # empty commands/
    home.mkdir()
    assert _manager(home, dotfiles).setup_claude_commands() is True
    assert not (home / ".claude" / "commands").exists()


def test_links_into_default_profile(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_command(_commands_dir(dotfiles), "commit.md")
    assert _manager(home, dotfiles).setup_claude_commands() is True

    link = home / ".claude" / "commands" / "commit.md"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_skips_bedrock_when_absent(tmp_path):
    """Bedrock profile is only populated if its root dir already exists."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_command(_commands_dir(dotfiles), "commit.md")
    assert _manager(home, dotfiles).setup_claude_commands() is True
    assert not (home / ".claude-bedrock").exists()


def test_links_into_bedrock_when_present(tmp_path):
    """The whole point: a shared command fans into Bedrock too when it exists."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_command(_commands_dir(dotfiles), "commit.md")
    (home / ".claude-bedrock").mkdir(parents=True)
    assert _manager(home, dotfiles).setup_claude_commands() is True

    link = home / ".claude-bedrock" / "commands" / "commit.md"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_links_every_command_into_both_profiles(tmp_path):
    """All commands/*.md fan out to every existing profile (no per-file narrowing)."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_command(_commands_dir(dotfiles), "commit.md")
    _make_command(_commands_dir(dotfiles), "review.md")
    (home / ".claude-bedrock").mkdir(parents=True)
    assert _manager(home, dotfiles).setup_claude_commands() is True

    for profile in (".claude", ".claude-bedrock"):
        for name in ("commit.md", "review.md"):
            assert (home / profile / "commands" / name).is_symlink()


def test_idempotent_across_repeated_installs(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_command(_commands_dir(dotfiles), "commit.md")
    manager = _manager(home, dotfiles)
    assert manager.setup_claude_commands() is True
    assert manager.setup_claude_commands() is True  # second run is a no-op-shaped success

    link = home / ".claude" / "commands" / "commit.md"
    assert link.is_symlink() and link.resolve() == src.resolve()
