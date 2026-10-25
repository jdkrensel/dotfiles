"""Integration tests for SymlinkManager.setup_claude_skills — symlinks the shared
Claude skill directories (assets/claude/skills/<name>/) into each Claude
profile that exists on the machine (default ~/.claude and the Bedrock
~/.claude-bedrock profile).

Unlike the machine-scoped skills in test_installer_skills.py, these need no
machine marker and ignore any `profiles:` line, mirroring the shared commands in
test_installer_commands.py.

These drive the installer against a synthetic fake-dotfiles tree so the behavior
is tested directly, independent of which skills actually ship in the repo."""

from pathlib import Path

from installer.printer import Printer
from installer.symlinker import SymlinkManager


def _make_skill(skills_dir: Path, name: str, profiles_line: str | None = None) -> Path:
    """Create a minimal skill directory with a SKILL.md and one bundled file."""
    skill = skills_dir / name
    (skill / "references").mkdir(parents=True, exist_ok=True)
    front = f"---\nname: {name}\ndescription: test\n"
    if profiles_line is not None:
        front += f"profiles: {profiles_line}\n"
    front += "---\n\nbody\n"
    (skill / "SKILL.md").write_text(front)
    (skill / "references" / "notes.md").write_text("notes\n")
    return skill


def _manager(home: Path, dotfiles: Path) -> SymlinkManager:
    manager = SymlinkManager(Printer(), dotfiles)
    manager.home_dir = home  # redirect symlink destinations to an isolated tmp home
    return manager


def _skills_dir(dotfiles: Path) -> Path:
    return dotfiles / "assets" / "claude" / "skills"


def test_noop_when_skills_dir_absent(tmp_path):
    """No skills dir at all → no-op, no profile dirs created."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    (dotfiles / "assets" / "claude").mkdir(parents=True)  # no skills/
    home.mkdir()
    assert _manager(home, dotfiles).setup_claude_skills() is True
    assert not (home / ".claude").exists()


def test_ignores_loose_files(tmp_path):
    """Only directories are skills; a stray file in skills/ is not linked."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _skills_dir(dotfiles).mkdir(parents=True)
    (_skills_dir(dotfiles) / ".DS_Store").write_text("")
    home.mkdir()
    assert _manager(home, dotfiles).setup_claude_skills() is True
    assert not (home / ".claude" / "skills").exists()


def test_links_skill_dir_without_machine_marker(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_skill(_skills_dir(dotfiles), "anki-cards")
    home.mkdir()  # no ~/.dotfiles-machine
    assert _manager(home, dotfiles).setup_claude_skills() is True

    link = home / ".claude" / "skills" / "anki-cards"
    assert link.is_symlink() and link.resolve() == src.resolve()
    assert (link / "references" / "notes.md").is_file()  # bundled files travel with it


def test_skips_bedrock_when_absent(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_skill(_skills_dir(dotfiles), "anki-cards")
    assert _manager(home, dotfiles).setup_claude_skills() is True
    assert not (home / ".claude-bedrock").exists()


def test_profiles_line_does_not_narrow(tmp_path):
    """Shared skills fan out to every existing profile, whatever SKILL.md says."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_skill(_skills_dir(dotfiles), "anki-cards", profiles_line="clb")
    (home / ".claude-bedrock").mkdir(parents=True)
    assert _manager(home, dotfiles).setup_claude_skills() is True

    for profile in (".claude", ".claude-bedrock"):
        assert (home / profile / "skills" / "anki-cards").is_symlink()


def test_idempotent_across_repeated_installs(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_skill(_skills_dir(dotfiles), "anki-cards")
    manager = _manager(home, dotfiles)
    assert manager.setup_claude_skills() is True
    assert manager.setup_claude_skills() is True

    link = home / ".claude" / "skills" / "anki-cards"
    assert link.is_symlink() and link.resolve() == src.resolve()
