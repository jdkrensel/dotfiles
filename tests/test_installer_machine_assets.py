"""Integration tests for machine-scoped Claude assets — SymlinkManager's
_require_machine_category(), setup_local_commands(), and setup_claude_hooks().

Commands and hooks specific to a machine category (e.g. work vs personal)
live under src/assets/claude/machines/<category>/{commands,hooks}/, tracked
in git. Which category a machine is gets resolved from a ~/.dotfiles-machine
marker file — installation must fail clearly if that marker is missing or
names an unrecognized category, never silently skip.

These drive the installer against a synthetic fake-dotfiles tree so the
behavior is tested directly, independent of which machine assets actually
ship in the repo."""

from pathlib import Path

from src.installer.printer import Printer
from src.installer.symlinker import SymlinkManager


def _make_command(commands_dir: Path, name: str, profiles_line: str | None = None) -> Path:
    """Write a minimal local command file, optionally with a `profiles:` line."""
    commands_dir.mkdir(parents=True, exist_ok=True)
    front = "---\ndescription: test\n"
    if profiles_line is not None:
        front += f"profiles: {profiles_line}\n"
    front += "---\n\nbody\n"
    path = commands_dir / name
    path.write_text(front)
    return path


def _make_hook(hooks_dir: Path, name: str) -> Path:
    """Write a minimal hook script into a hooks dir."""
    hooks_dir.mkdir(parents=True, exist_ok=True)
    path = hooks_dir / name
    path.write_text("#!/bin/bash\necho hi\n")
    path.chmod(0o755)
    return path


def _manager(home: Path, dotfiles: Path) -> SymlinkManager:
    manager = SymlinkManager(Printer(), dotfiles)
    manager.home_dir = home  # redirect symlink destinations to an isolated tmp home
    return manager


def _machines_dir(dotfiles: Path) -> Path:
    return dotfiles / "src" / "assets" / "claude" / "machines"


def _commands_dir(dotfiles: Path, category: str) -> Path:
    return _machines_dir(dotfiles) / category / "commands"


def _machine_hooks_dir(dotfiles: Path, category: str) -> Path:
    return _machines_dir(dotfiles) / category / "hooks"


def _shared_hooks_dir(dotfiles: Path) -> Path:
    return dotfiles / "src" / "assets" / "claude" / "hooks"


def _set_marker(home: Path, category: str) -> Path:
    marker = home / ".dotfiles-machine"
    marker.write_text(category)
    return marker


# --- _allowed_profiles unit tests (unchanged by the machine-category split) ------


def test_no_profiles_line_means_all(tmp_path):
    cmd = _make_command(tmp_path, "a.md")
    assert SymlinkManager._allowed_profiles(cmd) == {"clp", "clb"}


def test_profiles_line_is_an_allow_list(tmp_path):
    cmd = _make_command(tmp_path, "a.md", profiles_line="clb")
    assert SymlinkManager._allowed_profiles(cmd) == {"clb"}


def test_profiles_line_accepts_comma_and_space(tmp_path):
    cmd = _make_command(tmp_path, "a.md", profiles_line="clp, clb")
    assert SymlinkManager._allowed_profiles(cmd) == {"clp", "clb"}


def test_unknown_tokens_ignored_empty_falls_back_to_all(tmp_path):
    cmd = _make_command(tmp_path, "a.md", profiles_line="bogus")
    assert SymlinkManager._allowed_profiles(cmd) == {"clp", "clb"}


def test_profiles_only_counts_inside_frontmatter(tmp_path):
    """A `profiles:` line in the body is not frontmatter and must be ignored."""
    cmd = tmp_path / "a.md"
    cmd.write_text("---\ndescription: test\n---\n\nprofiles: clb\n")
    assert SymlinkManager._allowed_profiles(cmd) == {"clp", "clb"}


def test_no_frontmatter_at_all_means_all(tmp_path):
    """A file that doesn't open with a `---` fence has no frontmatter → all profiles."""
    cmd = tmp_path / "a.md"
    cmd.write_text("# just a heading\n\nprofiles: clb\n")
    assert SymlinkManager._allowed_profiles(cmd) == {"clp", "clb"}


def test_empty_profiles_line_falls_back_to_all(tmp_path):
    cmd = _make_command(tmp_path, "a.md", profiles_line="")
    assert SymlinkManager._allowed_profiles(cmd) == {"clp", "clb"}


def test_mixed_valid_and_invalid_tokens_keeps_valid(tmp_path):
    cmd = _make_command(tmp_path, "a.md", profiles_line="clb, bogus")
    assert SymlinkManager._allowed_profiles(cmd) == {"clb"}


# --- _require_machine_category unit tests -----------------------------------------


def test_marker_missing_fails_clearly(tmp_path, capsys):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    (_machines_dir(dotfiles) / "work").mkdir(parents=True)  # a known category exists
    home.mkdir()
    assert _manager(home, dotfiles)._require_machine_category() is None
    assert "Machine category marker not found" in capsys.readouterr().out


def test_marker_names_unrecognized_category_fails_clearly(tmp_path, capsys):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    (_machines_dir(dotfiles) / "work").mkdir(parents=True)
    home.mkdir()
    _set_marker(home, "nope")
    assert _manager(home, dotfiles)._require_machine_category() is None
    assert "Unrecognized machine category 'nope'" in capsys.readouterr().out


def test_no_machines_dir_means_no_known_categories(tmp_path, capsys):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    dotfiles.mkdir(parents=True)
    home.mkdir()
    assert _manager(home, dotfiles)._require_machine_category() is None
    assert "none defined yet" in capsys.readouterr().out


def test_marker_with_known_category_resolves(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    (_machines_dir(dotfiles) / "work").mkdir(parents=True)
    home.mkdir()
    _set_marker(home, "work")
    assert _manager(home, dotfiles)._require_machine_category() == "work"


def test_marker_whitespace_is_stripped(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    (_machines_dir(dotfiles) / "work").mkdir(parents=True)
    home.mkdir()
    (home / ".dotfiles-machine").write_text("work\n")
    assert _manager(home, dotfiles)._require_machine_category() == "work"


# --- setup_local_commands integration tests ----------------------------------------


def test_setup_local_commands_fails_without_marker(tmp_path, capsys):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_command(_commands_dir(dotfiles, "work"), "a.md")
    home.mkdir()
    assert _manager(home, dotfiles).setup_local_commands() is False
    assert not (home / ".claude").exists()
    assert "Machine category marker not found" in capsys.readouterr().out


def test_setup_local_commands_fails_with_unknown_category(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_command(_commands_dir(dotfiles, "work"), "a.md")
    home.mkdir()
    _set_marker(home, "nope")
    assert _manager(home, dotfiles).setup_local_commands() is False
    assert not (home / ".claude").exists()


def test_noop_when_category_has_no_commands(tmp_path):
    """Recognized machine, but no commands defined yet → no-op."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    (_machines_dir(dotfiles) / "work").mkdir(parents=True)
    home.mkdir()
    _set_marker(home, "work")
    assert _manager(home, dotfiles).setup_local_commands() is True
    assert not (home / ".claude" / "commands").exists()


def test_does_not_disturb_unrelated_existing_commands(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_command(_commands_dir(dotfiles, "work"), "a.md")
    home.mkdir()
    _set_marker(home, "work")
    existing = home / ".claude" / "commands"
    existing.mkdir(parents=True)
    (existing / "personal.md").write_text("my own command")

    assert _manager(home, dotfiles).setup_local_commands() is True
    assert (existing / "personal.md").read_text() == "my own command"
    assert (existing / "a.md").is_symlink()


def test_idempotent_across_repeated_installs(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_command(_commands_dir(dotfiles, "work"), "a.md", profiles_line="clp")
    home.mkdir()
    _set_marker(home, "work")
    manager = _manager(home, dotfiles)
    assert manager.setup_local_commands() is True
    assert manager.setup_local_commands() is True  # second run is a no-op-shaped success

    link = home / ".claude" / "commands" / "a.md"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_links_into_default_profile(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_command(_commands_dir(dotfiles, "work"), "a.md")
    home.mkdir()
    _set_marker(home, "work")
    assert _manager(home, dotfiles).setup_local_commands() is True

    link = home / ".claude" / "commands" / "a.md"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_skips_bedrock_when_absent(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_command(_commands_dir(dotfiles, "work"), "a.md")
    home.mkdir()
    _set_marker(home, "work")
    assert _manager(home, dotfiles).setup_local_commands() is True
    assert not (home / ".claude-bedrock").exists()


def test_links_into_bedrock_when_present(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_command(_commands_dir(dotfiles, "work"), "a.md")
    home.mkdir()
    _set_marker(home, "work")
    (home / ".claude-bedrock").mkdir(parents=True)
    assert _manager(home, dotfiles).setup_local_commands() is True

    link = home / ".claude-bedrock" / "commands" / "a.md"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_allow_list_routes_to_named_profile_only(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_command(_commands_dir(dotfiles, "work"), "clp_only.md", profiles_line="clp")
    _make_command(_commands_dir(dotfiles, "work"), "clb_only.md", profiles_line="clb")
    home.mkdir()
    _set_marker(home, "work")
    (home / ".claude-bedrock").mkdir(parents=True)
    assert _manager(home, dotfiles).setup_local_commands() is True

    clp = home / ".claude" / "commands"
    clb = home / ".claude-bedrock" / "commands"
    assert (clp / "clp_only.md").is_symlink()
    assert not (clp / "clb_only.md").exists()
    assert (clb / "clb_only.md").is_symlink()
    assert not (clb / "clp_only.md").exists()


def test_deny_prunes_stale_link(tmp_path):
    """A command that previously linked into a profile is removed once it opts out."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_command(_commands_dir(dotfiles, "work"), "a.md")  # starts unrestricted (both)
    home.mkdir()
    _set_marker(home, "work")
    (home / ".claude-bedrock").mkdir(parents=True)
    assert _manager(home, dotfiles).setup_local_commands() is True
    stale = home / ".claude-bedrock" / "commands" / "a.md"
    assert stale.is_symlink()

    # Now restrict it to clp and re-install — the bedrock link should be pruned.
    src.write_text("---\nprofiles: clp\n---\n\nbody\n")
    assert _manager(home, dotfiles).setup_local_commands() is True
    assert not stale.exists()
    assert (home / ".claude" / "commands" / "a.md").is_symlink()


def test_prune_never_touches_foreign_files(tmp_path):
    """Deny must not delete a real file or a symlink the installer didn't create."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_command(_commands_dir(dotfiles, "work"), "a.md", profiles_line="clp")  # denies clb
    home.mkdir()
    _set_marker(home, "work")
    clb_cmds = home / ".claude-bedrock" / "commands"
    clb_cmds.mkdir(parents=True)
    foreign = clb_cmds / "a.md"
    foreign.write_text("a real, unrelated file")  # same name, not our symlink

    assert _manager(home, dotfiles).setup_local_commands() is True
    assert foreign.is_file() and not foreign.is_symlink()
    assert foreign.read_text() == "a real, unrelated file"


def test_prune_never_touches_foreign_symlink(tmp_path):
    """Deny must not remove a same-named symlink that points elsewhere."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_command(_commands_dir(dotfiles, "work"), "a.md", profiles_line="clp")  # denies clb
    home.mkdir()
    _set_marker(home, "work")
    other = tmp_path / "somewhere_else.md"
    other.write_text("a different target")
    clb_cmds = home / ".claude-bedrock" / "commands"
    clb_cmds.mkdir(parents=True)
    foreign = clb_cmds / "a.md"
    foreign.symlink_to(other)  # same name, but NOT our source file

    assert _manager(home, dotfiles).setup_local_commands() is True
    assert foreign.is_symlink() and foreign.resolve() == other.resolve()


# --- setup_claude_hooks integration tests -------------------------------------------


def test_setup_claude_hooks_fails_without_marker(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_hook(_shared_hooks_dir(dotfiles), "shared.py")
    home.mkdir()
    assert _manager(home, dotfiles).setup_claude_hooks() is False
    assert not (home / ".claude" / "hooks").exists()


def test_setup_claude_hooks_links_shared_hooks_with_no_machine_hooks(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_hook(_shared_hooks_dir(dotfiles), "shared.py")
    (_machines_dir(dotfiles) / "work").mkdir(parents=True)  # known category, no hooks/
    home.mkdir()
    _set_marker(home, "work")
    assert _manager(home, dotfiles).setup_claude_hooks() is True

    link = home / ".claude" / "hooks" / "shared.py"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_setup_claude_hooks_merges_shared_and_machine_hooks(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    shared = _make_hook(_shared_hooks_dir(dotfiles), "shared.py")
    machine = _make_hook(_machine_hooks_dir(dotfiles, "work"), "work_only.sh")
    home.mkdir()
    _set_marker(home, "work")
    assert _manager(home, dotfiles).setup_claude_hooks() is True

    dest = home / ".claude" / "hooks"
    assert (dest / "shared.py").resolve() == shared.resolve()
    assert (dest / "work_only.sh").resolve() == machine.resolve()


def test_setup_claude_hooks_noop_when_nothing_to_link(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _shared_hooks_dir(dotfiles).mkdir(parents=True)  # empty shared hooks dir
    (_machines_dir(dotfiles) / "work").mkdir(parents=True)  # known category, no hooks/
    home.mkdir()
    _set_marker(home, "work")
    assert _manager(home, dotfiles).setup_claude_hooks() is True
    assert not (home / ".claude" / "hooks").exists()
