"""Integration tests for the read-only commands: resolve, plan, and doctor.

These verify the two properties that make the commands worth trusting: they
report the same routing the installer acts on, and they never write anything.
Exact wording is left untested — only the facts each command exists to convey.

They drive a synthetic dotfiles tree and an isolated home so the output does not
depend on which assets ship in the repo or how the developer's machine is set up."""

from dataclasses import replace
from pathlib import Path

from src.installer.cli import Context, doctor, plan, resolve
from src.installer.printer import Printer
from src.installer.resolver import Profile

PROFILE_ROOTS = {"clp": ".claude", "clb": ".claude-bedrock"}


def _write(path: Path, text: str = "body\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _command(path: Path, profiles_line: str | None = None) -> Path:
    front = "---\ndescription: test\n"
    if profiles_line is not None:
        front += f"profiles: {profiles_line}\n"
    return _write(path, front + "---\n\nbody\n")


def _context(tmp_path: Path, *tokens: str, machine: str | None = "work") -> Context:
    """Build a context over a synthetic dotfiles tree and an isolated home."""
    dotfiles = tmp_path / "dotfiles"
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    (dotfiles / "src" / "assets" / "claude" / "machines" / "work").mkdir(parents=True, exist_ok=True)
    return Context(
        printer=Printer(),
        dotfiles_dir=dotfiles,
        home_dir=home,
        profiles=[Profile(token=token, root=home / PROFILE_ROOTS[token]) for token in tokens or ("clp",)],
        machine=machine,
    )


def _home_tree(context: Context) -> set[Path]:
    return set(context.home_dir.rglob("*"))


# --- resolve -----------------------------------------------------------------


def test_resolve_lists_each_asset_with_a_column_per_profile(tmp_path, capsys):
    context = _context(tmp_path, "clp", "clb")
    _write(context.assets_dir / "claude" / "rules" / "python.md")

    assert resolve.run(context) == 0
    out = capsys.readouterr().out
    assert "claude/rules/python.md" in out
    assert "clp" in out and "clb" in out


def test_resolve_shows_a_narrowed_command_opting_out(tmp_path, capsys):
    """The whole point of the per-profile columns: seeing where a command lands."""
    context = _context(tmp_path, "clp", "clb")
    _command(context.assets_dir / "claude" / "machines" / "work" / "commands" / "bedrock.md", profiles_line="clb")

    assert resolve.run(context) == 0
    row = next(line for line in capsys.readouterr().out.splitlines() if "bedrock.md" in line)
    assert row.split()[-2:] == ["-", "yes"]  # denied under clp, linked under clb


def test_resolve_distinguishes_a_pinned_collection_from_an_opt_out(tmp_path, capsys):
    """Both leave a profile empty, but for opposite reasons: hooks are pinned to the
    default profile by design, whereas a dash means the asset refused that profile."""
    context = _context(tmp_path, "clp", "clb")
    _write(context.assets_dir / "claude" / "hooks" / "guard.py")

    assert resolve.run(context) == 0
    row = next(line for line in capsys.readouterr().out.splitlines() if "guard.py" in line)
    assert row.split()[-2:] == ["yes", "pin"]  # not "-": nothing opted out here


def test_resolve_reports_an_empty_tree_without_failing(tmp_path, capsys):
    assert resolve.run(_context(tmp_path)) == 0
    assert "No assets resolve" in capsys.readouterr().out


def test_resolve_honors_the_group_filter(tmp_path, capsys):
    context = _context(tmp_path)
    _write(context.assets_dir / "claude" / "rules" / "python.md")
    _write(context.assets_dir / "claude" / "agents" / "reviewer.md")

    assert resolve.run(context, group="rules") == 0
    out = capsys.readouterr().out
    assert "python.md" in out
    assert "reviewer.md" not in out


def test_resolve_warns_when_no_machine_is_set(tmp_path, capsys):
    context = _context(tmp_path, machine=None)
    _write(context.assets_dir / "claude" / "rules" / "python.md")

    assert resolve.run(context) == 0
    assert "No machine category set" in capsys.readouterr().out


# --- plan --------------------------------------------------------------------


def test_plan_reports_links_it_would_create(tmp_path, capsys):
    context = _context(tmp_path)
    _write(context.assets_dir / "claude" / "rules" / "python.md")

    assert plan.run(context) == 0
    out = capsys.readouterr().out
    assert "create" in out
    assert "~/.claude/rules/python.md" in out


def test_plan_reports_nothing_pending_once_installed(tmp_path, capsys):
    context = _context(tmp_path)
    source = _write(context.assets_dir / "claude" / "rules" / "python.md")
    dest = context.home_dir / ".claude" / "rules" / "python.md"
    dest.parent.mkdir(parents=True)
    dest.symlink_to(source)

    assert plan.run(context) == 0
    out = capsys.readouterr().out
    assert "up to date" in out
    # It must not claim the whole install is current: the shell files, ~/.config,
    # ~/bin and the settings.json merge are all outside what the resolver produces.
    assert "--dry-run" in out


def test_plan_flags_an_existing_file_as_a_replacement(tmp_path, capsys):
    """A real file at the destination would be backed up, not silently kept."""
    context = _context(tmp_path)
    _write(context.assets_dir / "claude" / "rules" / "python.md")
    _write(context.home_dir / ".claude" / "rules" / "python.md", "hand-written\n")

    assert plan.run(context) == 0
    assert "replace" in capsys.readouterr().out


def test_plan_reports_a_stale_link_it_would_prune(tmp_path, capsys):
    context = _context(tmp_path, "clp", "clb")
    source = _command(
        context.assets_dir / "claude" / "machines" / "work" / "commands" / "bedrock.md",
        profiles_line="clb",
    )
    stale = context.home_dir / ".claude" / "commands" / "bedrock.md"
    stale.parent.mkdir(parents=True)
    stale.symlink_to(source)

    assert plan.run(context) == 0
    out = capsys.readouterr().out
    assert "remove" in out
    assert "~/.claude/commands/bedrock.md" in out


def test_plan_writes_nothing(tmp_path, capsys):
    """The guarantee that makes plan safe to run at any time."""
    context = _context(tmp_path)
    _write(context.assets_dir / "claude" / "rules" / "python.md")
    before = _home_tree(context)

    assert plan.run(context) == 0
    assert _home_tree(context) == before


# --- doctor ------------------------------------------------------------------


def test_doctor_is_clean_on_a_freshly_installed_machine(tmp_path, capsys):
    context = _context(tmp_path)
    source = _write(context.assets_dir / "claude" / "rules" / "python.md")
    dest = context.home_dir / ".claude" / "rules" / "python.md"
    dest.parent.mkdir(parents=True)
    dest.symlink_to(source)

    assert doctor.run(context) == 0
    assert "No drift found" in capsys.readouterr().out


def test_doctor_finds_an_orphaned_backup(tmp_path, capsys):
    context = _context(tmp_path)
    _write(context.home_dir / ".claude" / "commands" / "commit.md.bak", "old\n")

    assert doctor.run(context) == 1
    assert "orphaned-backup" in capsys.readouterr().out


def test_doctor_finds_a_broken_link(tmp_path, capsys):
    context = _context(tmp_path)
    dest = context.home_dir / ".claude" / "rules" / "gone.md"
    dest.parent.mkdir(parents=True)
    dest.symlink_to(context.assets_dir / "claude" / "rules" / "gone.md")

    assert doctor.run(context) == 1
    assert "broken-link" in capsys.readouterr().out


def test_doctor_finds_a_link_left_by_a_renamed_asset(tmp_path, capsys):
    """The drift an install cannot see: the old link still resolves, but nothing
    in the repo routes there any more."""
    context = _context(tmp_path)
    renamed = _write(context.assets_dir / "claude" / "rules" / "old-name.md")
    dest = context.home_dir / ".claude" / "rules" / "old-name.md"
    dest.parent.mkdir(parents=True)
    dest.symlink_to(renamed)
    renamed.rename(context.assets_dir / "claude" / "rules" / "new-name.md")
    dest.unlink()
    dest.symlink_to(context.assets_dir / "claude" / "rules" / "new-name.md")

    assert doctor.run(context) == 1
    assert "stale-link" in capsys.readouterr().out


def test_doctor_ignores_files_the_installer_does_not_own(tmp_path, capsys):
    """A user's own file in a managed dir is theirs — reporting it would be noise."""
    context = _context(tmp_path)
    _write(context.home_dir / ".claude" / "rules" / "my-own-notes.md")
    _write(context.home_dir / ".claude" / "settings.json", "{}")

    assert doctor.run(context) == 0
    assert "No drift found" in capsys.readouterr().out


def test_doctor_accepts_a_link_the_next_install_would_prune(tmp_path, capsys):
    """A `profiles:` opt-out leaves a link behind, but an install removes it — so
    it is pending work that `plan` lists, not drift doctor should alarm about."""
    context = _context(tmp_path, "clp", "clb")
    source = _command(
        context.assets_dir / "claude" / "machines" / "work" / "commands" / "bedrock.md",
        profiles_line="clb",
    )
    stale = context.home_dir / ".claude" / "commands" / "bedrock.md"
    stale.parent.mkdir(parents=True)
    stale.symlink_to(source)

    assert doctor.run(context) == 0
    assert "No drift found" in capsys.readouterr().out


def test_doctor_does_not_call_machine_assets_stale_when_no_marker_is_set(tmp_path, capsys):
    """Without a category, resolution omits machine-scoped collections entirely —
    so correctly installed local commands must not be reported as unaccounted for."""
    context = _context(tmp_path, machine=None)
    source = _command(context.assets_dir / "claude" / "machines" / "work" / "commands" / "deploy.md")
    installed = context.home_dir / ".claude" / "commands" / "deploy.md"
    installed.parent.mkdir(parents=True)
    installed.symlink_to(source)

    assert doctor.run(context) == 1
    out = capsys.readouterr().out
    assert "machine-marker" in out
    assert "stale-link" not in out


def test_doctor_reports_a_missing_machine_marker(tmp_path, capsys):
    assert doctor.run(_context(tmp_path, machine=None)) == 1
    assert "machine-marker" in capsys.readouterr().out


def test_doctor_writes_nothing(tmp_path, capsys):
    context = _context(tmp_path)
    _write(context.home_dir / ".claude" / "commands" / "commit.md.bak", "old\n")
    before = _home_tree(context)

    assert doctor.run(context) == 1
    assert _home_tree(context) == before


def test_doctor_finds_stale_links_when_the_repo_path_is_a_symlink(tmp_path, capsys):
    """A checkout reached through a symlink must not silently disable the check:
    the link resolves to the real path, so the repo root has to be resolved too."""
    context = _context(tmp_path)
    unrouted = _write(context.assets_dir / "claude" / "not-a-collection.md")
    dest = context.home_dir / ".claude" / "rules" / "not-a-collection.md"
    dest.parent.mkdir(parents=True)
    dest.symlink_to(unrouted)

    alias = tmp_path / "dotfiles-alias"
    alias.symlink_to(context.dotfiles_dir)
    via_alias = replace(context, dotfiles_dir=alias)

    assert doctor.run(via_alias) == 1
    assert "stale-link" in capsys.readouterr().out


def test_doctor_reports_a_malformed_allow_list_without_losing_the_other_checks(tmp_path, capsys):
    """The command you reach for when something is wrong must not die on that thing.

    A `profiles:` line naming no known profile makes resolution refuse to guess, which
    would otherwise abort the whole report. It becomes a finding instead, and the
    checks that need no resolution still run.
    """
    context = _context(tmp_path)
    _command(context.assets_dir / "claude" / "machines" / "work" / "commands" / "a.md", "bogus")
    _write(context.home_dir / ".claude" / "commands" / "commit.md.bak", "old\n")

    assert doctor.run(context) == 1
    out = capsys.readouterr().out
    assert "malformed-frontmatter" in out
    assert "orphaned-backup" in out  # the resolution-free checks still reported


def test_doctor_reports_an_unreadable_managed_directory(tmp_path, capsys):
    context = _context(tmp_path)
    commands = context.home_dir / ".claude" / "commands"
    commands.mkdir(parents=True)
    commands.chmod(0o000)
    try:
        assert doctor.run(context) == 1
        assert "unreadable-directory" in capsys.readouterr().out
    finally:
        commands.chmod(0o755)  # restore so tmp_path cleanup can remove it
