"""Integration tests for machine-scoped Claude skills — SymlinkManager's
setup_local_skills().

Skills specific to a machine category (e.g. work vs personal) live under
src/assets/claude/machines/<category>/skills/<name>/ — one directory per
skill holding SKILL.md plus any bundled resources — tracked in git. Each
skill directory is symlinked whole into every Claude profile whose root dir
exists on the machine (~/.claude and ~/.claude-bedrock), unless its SKILL.md
carries a `profiles:` allow-list narrowing it to a subset, mirroring the
machine-scoped commands in test_installer_machine_assets.py.

These drive the installer against a synthetic fake-dotfiles tree so the
behavior is tested directly, independent of which machine assets actually
ship in the repo."""

from pathlib import Path

from src.installer.printer import Printer
from src.installer.symlinker import SymlinkManager


def _make_skill(skills_dir: Path, name: str, profiles_line: str | None = None) -> Path:
    """Create a minimal skill directory containing a SKILL.md.

    ``profiles_line`` adds a `profiles:` allow-list, which narrows the skill to a
    subset of profiles.
    """
    skill = skills_dir / name
    skill.mkdir(parents=True, exist_ok=True)
    front = f"---\nname: {name}\ndescription: test\n"
    if profiles_line is not None:
        front += f"profiles: {profiles_line}\n"
    front += "---\n\nbody\n"
    (skill / "SKILL.md").write_text(front)
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


def test_bedrock_only_skill_skips_the_default_profile(tmp_path):
    """`profiles: clb` keeps a skill out of the non-BAA default profile.

    This is the whole point of narrowing skills: one that reaches PHI, clinical
    databases, or production hosts must not appear in ~/.claude.
    """
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_skill(_skills_dir(dotfiles, "work"), "read-php-logs", profiles_line="clb")
    home.mkdir()
    _set_marker(home, "work")
    (home / ".claude-bedrock").mkdir(parents=True)

    assert _manager(home, dotfiles).setup_local_skills() is True

    linked = home / ".claude-bedrock" / "skills" / "read-php-logs"
    assert linked.is_symlink() and linked.resolve() == src.resolve()
    assert not (home / ".claude" / "skills" / "read-php-logs").exists()


def test_narrowing_prunes_a_link_left_by_an_earlier_install(tmp_path):
    """Adding `profiles: clb` to an already-installed skill removes the stale link.

    Without this, a skill that fanned out before it was narrowed would stay in the
    default profile forever — the link is what actually exposes it.
    """
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    skills = _skills_dir(dotfiles, "work")
    src = _make_skill(skills, "read-php-logs")
    home.mkdir()
    _set_marker(home, "work")
    (home / ".claude-bedrock").mkdir(parents=True)

    manager = _manager(home, dotfiles)
    assert manager.setup_local_skills() is True
    stale = home / ".claude" / "skills" / "read-php-logs"
    assert stale.is_symlink()  # fanned out while unrestricted

    _make_skill(skills, "read-php-logs", profiles_line="clb")  # now narrowed
    assert manager.setup_local_skills() is True

    assert not stale.exists()
    still_there = home / ".claude-bedrock" / "skills" / "read-php-logs"
    assert still_there.is_symlink() and still_there.resolve() == src.resolve()


def test_prune_leaves_a_users_own_skill_alone(tmp_path):
    """A real directory at the denied path is never removed — only our own symlink is."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_skill(_skills_dir(dotfiles, "work"), "read-php-logs", profiles_line="clb")
    home.mkdir()
    _set_marker(home, "work")
    (home / ".claude-bedrock").mkdir(parents=True)
    mine = home / ".claude" / "skills" / "read-php-logs"
    mine.mkdir(parents=True)
    (mine / "SKILL.md").write_text("mine")

    assert _manager(home, dotfiles).setup_local_skills() is True
    assert (mine / "SKILL.md").read_text() == "mine"


def test_prune_never_touches_foreign_symlink(tmp_path):
    """Deny must not remove a same-named symlink pointing somewhere else.

    This is the branch where unlink() is actually reachable, so it's the one worth
    pinning for directory assets too.
    """
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_skill(_skills_dir(dotfiles, "work"), "read-php-logs", profiles_line="clb")
    home.mkdir()
    _set_marker(home, "work")
    (home / ".claude-bedrock").mkdir(parents=True)
    other = tmp_path / "somewhere_else"
    other.mkdir()
    clp_skills = home / ".claude" / "skills"
    clp_skills.mkdir(parents=True)
    foreign = clp_skills / "read-php-logs"
    foreign.symlink_to(other)  # same name, but NOT our source dir

    assert _manager(home, dotfiles).setup_local_skills() is True
    assert foreign.is_symlink() and foreign.resolve() == other.resolve()


def test_narrowed_skill_is_idempotent_across_repeated_installs(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_skill(_skills_dir(dotfiles, "work"), "read-php-logs", profiles_line="clb")
    home.mkdir()
    _set_marker(home, "work")
    (home / ".claude-bedrock").mkdir(parents=True)

    manager = _manager(home, dotfiles)
    assert manager.setup_local_skills() is True
    assert manager.setup_local_skills() is True

    linked = home / ".claude-bedrock" / "skills" / "read-php-logs"
    assert linked.is_symlink() and linked.resolve() == src.resolve()
    assert not (home / ".claude" / "skills" / "read-php-logs").exists()


def test_unknown_profile_token_fails_the_step_loudly(tmp_path, capsys):
    """A typo'd allow-list must abort, not silently install into every profile.

    Widening on a typo is the failure that would quietly put a PHI skill in the
    non-BAA profile, so it has to be noisy rather than convenient.
    """
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_skill(_skills_dir(dotfiles, "work"), "read-php-logs", profiles_line="bedrock")
    home.mkdir()
    _set_marker(home, "work")

    assert _manager(home, dotfiles).setup_local_skills() is False
    assert not (home / ".claude" / "skills" / "read-php-logs").exists()
    assert "naming no known profile" in capsys.readouterr().out


def test_skill_dir_without_skill_md_still_links(tmp_path):
    """No SKILL.md means nothing to state a preference with — keep the old default."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    (_skills_dir(dotfiles, "work") / "bare").mkdir(parents=True)
    home.mkdir()
    _set_marker(home, "work")

    assert _manager(home, dotfiles).setup_local_skills() is True
    assert (home / ".claude" / "skills" / "bare").is_symlink()
