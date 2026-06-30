"""Integration tests for SymlinkManager.setup_claude_rules — symlinks the
path-scoped Claude rule files (rules/*.md) into each Claude profile that exists
on the machine (default ~/.claude and the Bedrock ~/.claude-bedrock profile).

These drive the installer against a synthetic fake-dotfiles tree so the behavior
is tested directly, independent of which rule files actually ship in the repo."""

from pathlib import Path

from src.installer.printer import Printer
from src.installer.symlinker import SymlinkManager


def _make_rule(rules_dir: Path, name: str) -> Path:
    """Write a minimal rule file into the fake dotfiles rules dir."""
    rules_dir.mkdir(parents=True, exist_ok=True)
    path = rules_dir / name
    path.write_text("---\npaths:\n  - '**/*.py'\n---\n\n# rule body\n")
    return path


def _manager(home: Path, dotfiles: Path) -> SymlinkManager:
    manager = SymlinkManager(Printer(), dotfiles)
    manager.home_dir = home  # redirect symlink destinations to an isolated tmp home
    return manager


def _rules_dir(dotfiles: Path) -> Path:
    return dotfiles / "src" / "assets" / "claude" / "rules"


def test_noop_when_rules_dir_absent(tmp_path):
    """No rules dir at all → no-op, no profile dirs created."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    (dotfiles / "src" / "assets" / "claude").mkdir(parents=True)  # no rules/
    home.mkdir()
    assert _manager(home, dotfiles).setup_claude_rules() is True
    assert not (home / ".claude").exists()


def test_noop_when_rules_dir_empty(tmp_path):
    """rules/ exists but holds no .md files → no-op."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _rules_dir(dotfiles).mkdir(parents=True)  # empty rules/
    home.mkdir()
    assert _manager(home, dotfiles).setup_claude_rules() is True
    assert not (home / ".claude" / "rules").exists()


def test_links_into_default_profile(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_rule(_rules_dir(dotfiles), "python.md")
    assert _manager(home, dotfiles).setup_claude_rules() is True

    link = home / ".claude" / "rules" / "python.md"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_skips_bedrock_when_absent(tmp_path):
    """Bedrock profile is only populated if its root dir already exists."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_rule(_rules_dir(dotfiles), "python.md")
    assert _manager(home, dotfiles).setup_claude_rules() is True
    assert not (home / ".claude-bedrock").exists()


def test_links_into_bedrock_when_present(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_rule(_rules_dir(dotfiles), "python.md")
    (home / ".claude-bedrock").mkdir(parents=True)
    assert _manager(home, dotfiles).setup_claude_rules() is True

    link = home / ".claude-bedrock" / "rules" / "python.md"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_links_every_rule_into_both_profiles(tmp_path):
    """All rules/*.md fan out to every existing profile (no per-file narrowing)."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_rule(_rules_dir(dotfiles), "python.md")
    _make_rule(_rules_dir(dotfiles), "typescript.md")
    (home / ".claude-bedrock").mkdir(parents=True)
    assert _manager(home, dotfiles).setup_claude_rules() is True

    for profile in (".claude", ".claude-bedrock"):
        for name in ("python.md", "typescript.md"):
            assert (home / profile / "rules" / name).is_symlink()


def test_idempotent_across_repeated_installs(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_rule(_rules_dir(dotfiles), "python.md")
    manager = _manager(home, dotfiles)
    assert manager.setup_claude_rules() is True
    assert manager.setup_claude_rules() is True  # second run is a no-op-shaped success

    link = home / ".claude" / "rules" / "python.md"
    assert link.is_symlink() and link.resolve() == src.resolve()
