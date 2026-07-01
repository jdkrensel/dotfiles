"""Integration tests for SymlinkManager.setup_claude_agents — symlinks the
custom Claude subagent files (agents/*.md) into each Claude profile that exists
on the machine (default ~/.claude and the Bedrock ~/.claude-bedrock profile).

These drive the installer against a synthetic fake-dotfiles tree so the behavior
is tested directly, independent of which agent files actually ship in the repo."""

from pathlib import Path

from src.installer.printer import Printer
from src.installer.symlinker import SymlinkManager


def _make_agent(agents_dir: Path, name: str) -> Path:
    """Write a minimal subagent file into the fake dotfiles agents dir."""
    agents_dir.mkdir(parents=True, exist_ok=True)
    path = agents_dir / name
    path.write_text("---\nname: reviewer\ndescription: reviews code\n---\n\n# agent body\n")
    return path


def _manager(home: Path, dotfiles: Path) -> SymlinkManager:
    manager = SymlinkManager(Printer(), dotfiles)
    manager.home_dir = home  # redirect symlink destinations to an isolated tmp home
    return manager


def _agents_dir(dotfiles: Path) -> Path:
    return dotfiles / "src" / "assets" / "claude" / "agents"


def test_noop_when_agents_dir_absent(tmp_path):
    """No agents dir at all → no-op, no profile dirs created."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    (dotfiles / "src" / "assets" / "claude").mkdir(parents=True)  # no agents/
    home.mkdir()
    assert _manager(home, dotfiles).setup_claude_agents() is True
    assert not (home / ".claude").exists()


def test_noop_when_agents_dir_empty(tmp_path):
    """agents/ exists but holds no .md files → no-op."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _agents_dir(dotfiles).mkdir(parents=True)  # empty agents/
    home.mkdir()
    assert _manager(home, dotfiles).setup_claude_agents() is True
    assert not (home / ".claude" / "agents").exists()


def test_links_into_default_profile(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_agent(_agents_dir(dotfiles), "reviewer.md")
    assert _manager(home, dotfiles).setup_claude_agents() is True

    link = home / ".claude" / "agents" / "reviewer.md"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_skips_bedrock_when_absent(tmp_path):
    """Bedrock profile is only populated if its root dir already exists."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_agent(_agents_dir(dotfiles), "reviewer.md")
    assert _manager(home, dotfiles).setup_claude_agents() is True
    assert not (home / ".claude-bedrock").exists()


def test_links_into_bedrock_when_present(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_agent(_agents_dir(dotfiles), "reviewer.md")
    (home / ".claude-bedrock").mkdir(parents=True)
    assert _manager(home, dotfiles).setup_claude_agents() is True

    link = home / ".claude-bedrock" / "agents" / "reviewer.md"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_links_every_agent_into_both_profiles(tmp_path):
    """All agents/*.md fan out to every existing profile (no per-file narrowing)."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_agent(_agents_dir(dotfiles), "reviewer.md")
    _make_agent(_agents_dir(dotfiles), "planner.md")
    (home / ".claude-bedrock").mkdir(parents=True)
    assert _manager(home, dotfiles).setup_claude_agents() is True

    for profile in (".claude", ".claude-bedrock"):
        for name in ("reviewer.md", "planner.md"):
            assert (home / profile / "agents" / name).is_symlink()


def test_idempotent_across_repeated_installs(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_agent(_agents_dir(dotfiles), "reviewer.md")
    manager = _manager(home, dotfiles)
    assert manager.setup_claude_agents() is True
    assert manager.setup_claude_agents() is True  # second run is a no-op-shaped success

    link = home / ".claude" / "agents" / "reviewer.md"
    assert link.is_symlink() and link.resolve() == src.resolve()
