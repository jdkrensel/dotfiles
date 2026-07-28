"""Integration tests for machine-scoped Claude skills — SymlinkManager's
setup_local_skills().

Skills specific to a machine category (e.g. work vs personal) live under
src/assets/claude/machines/<category>/skills/<name>/ — one directory per
skill holding SKILL.md plus any bundled resources — tracked in git. Each
skill directory is symlinked whole into every Claude profile whose root dir
exists on the machine (~/.claude and ~/.claude-bedrock), mirroring the
machine-scoped commands in test_installer_machine_assets.py.

These drive the installer against a synthetic fake-dotfiles tree so the
behavior is tested directly, independent of which machine assets actually
ship in the repo."""

from pathlib import Path

from src.installer.printer import Printer
from src.installer.symlinker import SymlinkManager


def _make_skill(skills_dir: Path, name: str) -> Path:
    """Create a minimal skill directory containing a SKILL.md."""
    skill = skills_dir / name
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: test\n---\n\nbody\n")
    return skill


def _manager(home: Path, dotfiles: Path) -> SymlinkManager:
    manager = SymlinkManager(Printer(), dotfiles)
    manager.home_dir = home  # redirect symlink destinations to an isolated tmp home
    return manager


def _machines_dir(dotfiles: Path) -> Path:
    return dotfiles / "src" / "assets" / "claude" / "machines"


def _skills_dir(dotfiles: Path, category: str) -> Path:
    return _machines_dir(dotfiles) / category / "skills"


def _set_marker(home: Path, category: str) -> Path:
    marker = home / ".dotfiles-machine"
    marker.write_text(category)
    return marker


def test_fails_without_marker(tmp_path, capsys):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_skill(_skills_dir(dotfiles, "work"), "deploy-page")
    home.mkdir()
    assert _manager(home, dotfiles).setup_local_skills() is False
    assert not (home / ".claude").exists()
    assert "Machine category marker not found" in capsys.readouterr().out


def test_fails_with_unknown_category(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_skill(_skills_dir(dotfiles, "work"), "deploy-page")
    home.mkdir()
    _set_marker(home, "nope")
    assert _manager(home, dotfiles).setup_local_skills() is False
    assert not (home / ".claude").exists()


def test_noop_when_category_has_no_skills(tmp_path):
    """Recognized machine, but no skills defined yet → no-op."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    (_machines_dir(dotfiles) / "work").mkdir(parents=True)
    home.mkdir()
    _set_marker(home, "work")
    assert _manager(home, dotfiles).setup_local_skills() is True
    assert not (home / ".claude" / "skills").exists()


def test_links_skill_dir_into_default_profile(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_skill(_skills_dir(dotfiles, "work"), "deploy-page")
    home.mkdir()
    _set_marker(home, "work")
    assert _manager(home, dotfiles).setup_local_skills() is True

    link = home / ".claude" / "skills" / "deploy-page"
    assert link.is_symlink() and link.resolve() == src.resolve()
    assert (link / "SKILL.md").is_file()  # bundled content reachable through the link


def test_skips_bedrock_when_absent(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_skill(_skills_dir(dotfiles, "work"), "deploy-page")
    home.mkdir()
    _set_marker(home, "work")
    assert _manager(home, dotfiles).setup_local_skills() is True
    assert not (home / ".claude-bedrock").exists()


def test_links_into_bedrock_when_present(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_skill(_skills_dir(dotfiles, "work"), "deploy-page")
    home.mkdir()
    _set_marker(home, "work")
    (home / ".claude-bedrock").mkdir(parents=True)
    assert _manager(home, dotfiles).setup_local_skills() is True

    link = home / ".claude-bedrock" / "skills" / "deploy-page"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_idempotent_across_repeated_installs(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_skill(_skills_dir(dotfiles, "work"), "deploy-page")
    home.mkdir()
    _set_marker(home, "work")
    manager = _manager(home, dotfiles)
    assert manager.setup_local_skills() is True
    assert manager.setup_local_skills() is True  # second run is a no-op-shaped success

    link = home / ".claude" / "skills" / "deploy-page"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_does_not_disturb_unrelated_existing_skills(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_skill(_skills_dir(dotfiles, "work"), "deploy-page")
    home.mkdir()
    _set_marker(home, "work")
    existing = home / ".claude" / "skills" / "my-own-skill"
    existing.mkdir(parents=True)
    (existing / "SKILL.md").write_text("mine")

    assert _manager(home, dotfiles).setup_local_skills() is True
    assert (existing / "SKILL.md").read_text() == "mine"
    assert (home / ".claude" / "skills" / "deploy-page").is_symlink()


def test_stray_files_in_skills_dir_are_ignored(tmp_path):
    """Only directories are skills; a loose file (e.g. a README) must not be linked."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    skills = _skills_dir(dotfiles, "work")
    _make_skill(skills, "deploy-page")
    (skills / "README.md").write_text("about these skills")
    home.mkdir()
    _set_marker(home, "work")
    assert _manager(home, dotfiles).setup_local_skills() is True

    dest = home / ".claude" / "skills"
    assert (dest / "deploy-page").is_symlink()
    assert not (dest / "README.md").exists()
