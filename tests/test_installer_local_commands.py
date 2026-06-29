"""Integration tests for SymlinkManager.setup_local_commands — symlinks the
machine-local Claude commands (commands/local/*.md) into each Claude profile that
exists on the machine, honoring an optional `profiles:` frontmatter allow-list.

These drive the installer against a synthetic fake-dotfiles tree so the behavior
is tested directly, independent of which profiles the real commands opt into."""

from pathlib import Path

from src.installer.printer import Printer
from src.installer.symlinker import SymlinkManager


def _make_command(local_dir: Path, name: str, profiles_line: str | None = None) -> Path:
    """Write a minimal local command file, optionally with a `profiles:` line."""
    local_dir.mkdir(parents=True, exist_ok=True)
    front = "---\ndescription: test\n"
    if profiles_line is not None:
        front += f"profiles: {profiles_line}\n"
    front += "---\n\nbody\n"
    path = local_dir / name
    path.write_text(front)
    return path


def _manager(home: Path, dotfiles: Path) -> SymlinkManager:
    manager = SymlinkManager(Printer(), dotfiles)
    manager.home_dir = home  # redirect symlink destinations to an isolated tmp home
    return manager


def _local_dir(dotfiles: Path) -> Path:
    return dotfiles / "src" / "assets" / "claude" / "commands" / "local"


# --- _allowed_profiles unit tests -------------------------------------------------


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


# --- setup_local_commands integration tests --------------------------------------


def test_noop_when_local_dir_absent(tmp_path):
    """Home-machine case: no commands/local dir at all → no-op, no dirs created."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    (dotfiles / "src" / "assets" / "claude" / "commands").mkdir(
        parents=True
    )  # no local/
    home.mkdir()
    assert _manager(home, dotfiles).setup_local_commands() is True
    assert not (home / ".claude").exists()
    assert not (home / ".claude-bedrock").exists()


def test_noop_when_local_dir_empty(tmp_path):
    """Home-machine case: local/ exists but holds no .md files → no-op."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _local_dir(dotfiles).mkdir(parents=True)  # empty local/
    home.mkdir()
    assert _manager(home, dotfiles).setup_local_commands() is True
    assert not (home / ".claude" / "commands").exists()


def test_does_not_disturb_unrelated_existing_commands(tmp_path):
    """An unrelated command already in a profile is left untouched."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_command(_local_dir(dotfiles), "a.md")
    existing = home / ".claude" / "commands"
    existing.mkdir(parents=True)
    (existing / "personal.md").write_text("my own command")

    assert _manager(home, dotfiles).setup_local_commands() is True
    assert (existing / "personal.md").read_text() == "my own command"
    assert (existing / "a.md").is_symlink()


def test_idempotent_across_repeated_installs(tmp_path):
    """Re-running with the same inputs leaves links correct and returns True."""
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_command(_local_dir(dotfiles), "a.md", profiles_line="clp")
    manager = _manager(home, dotfiles)
    assert manager.setup_local_commands() is True
    assert (
        manager.setup_local_commands() is True
    )  # second run is a no-op-shaped success

    link = home / ".claude" / "commands" / "a.md"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_links_into_default_profile(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_command(_local_dir(dotfiles), "a.md")
    assert _manager(home, dotfiles).setup_local_commands() is True

    link = home / ".claude" / "commands" / "a.md"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_skips_bedrock_when_absent(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_command(_local_dir(dotfiles), "a.md")
    assert _manager(home, dotfiles).setup_local_commands() is True
    assert not (home / ".claude-bedrock").exists()


def test_links_into_bedrock_when_present(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    src = _make_command(_local_dir(dotfiles), "a.md")
    (home / ".claude-bedrock").mkdir(parents=True)
    assert _manager(home, dotfiles).setup_local_commands() is True

    link = home / ".claude-bedrock" / "commands" / "a.md"
    assert link.is_symlink() and link.resolve() == src.resolve()


def test_allow_list_routes_to_named_profile_only(tmp_path):
    dotfiles, home = tmp_path / "repo", tmp_path / "home"
    _make_command(_local_dir(dotfiles), "clp_only.md", profiles_line="clp")
    _make_command(_local_dir(dotfiles), "clb_only.md", profiles_line="clb")
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
    src = _make_command(_local_dir(dotfiles), "a.md")  # starts unrestricted (both)
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
    _make_command(_local_dir(dotfiles), "a.md", profiles_line="clp")  # denies clb
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
    _make_command(_local_dir(dotfiles), "a.md", profiles_line="clp")  # denies clb
    other = tmp_path / "somewhere_else.md"
    other.write_text("a different target")
    clb_cmds = home / ".claude-bedrock" / "commands"
    clb_cmds.mkdir(parents=True)
    foreign = clb_cmds / "a.md"
    foreign.symlink_to(other)  # same name, but NOT our source file

    assert _manager(home, dotfiles).setup_local_commands() is True
    assert foreign.is_symlink() and foreign.resolve() == other.resolve()
