"""Integration tests for --dry-run.

A dry run is only useful if it is trustworthy in both directions: it must not
write anything, and it must report the same work a real install would do. These
drive SymlinkManager against a synthetic dotfiles tree and an isolated home, then
assert the home is untouched — and that running for real afterwards produces
exactly what the dry run described."""

import json
from pathlib import Path

from src.installer.installer import DotfilesInstaller
from src.installer.printer import Printer
from src.installer.symlinker import SymlinkManager


def _write(path: Path, text: str = "body\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _manager(home: Path, dotfiles: Path, dry_run: bool) -> SymlinkManager:
    manager = SymlinkManager(Printer(), dotfiles, dry_run=dry_run)
    manager.home_dir = home  # redirect symlink destinations to an isolated tmp home
    return manager


def _tree(tmp_path: Path) -> tuple[Path, Path]:
    """Return (home, dotfiles) for a machine with one rule and one local command."""
    home = tmp_path / "home"
    home.mkdir()
    dotfiles = tmp_path / "dotfiles"
    assets = dotfiles / "src" / "assets"
    _write(assets / "claude" / "rules" / "python.md")
    _write(assets / "claude" / "machines" / "work" / "commands" / "deploy.md", "---\ndescription: t\n---\n\nbody\n")
    _write(home / ".dotfiles-machine", "work")
    return home, dotfiles


def test_dry_run_creates_no_links(tmp_path, capsys):
    home, dotfiles = _tree(tmp_path)
    assert _manager(home, dotfiles, dry_run=True).setup_claude_rules() is True
    assert not (home / ".claude").exists()


def test_dry_run_creates_no_directories(tmp_path, capsys):
    """The destination dirs an install would mkdir must not appear either."""
    home, dotfiles = _tree(tmp_path)
    assert _manager(home, dotfiles, dry_run=True).setup_local_commands() is True
    assert set(home.iterdir()) == {home / ".dotfiles-machine"}


def test_dry_run_reports_what_it_would_create(tmp_path, capsys):
    home, dotfiles = _tree(tmp_path)
    _manager(home, dotfiles, dry_run=True).setup_claude_rules()
    out = capsys.readouterr().out
    assert "Would create" in out
    assert "python.md" in out


def test_dry_run_recognizes_an_already_correct_link(tmp_path, capsys):
    home, dotfiles = _tree(tmp_path)
    _manager(home, dotfiles, dry_run=False).setup_claude_rules()
    capsys.readouterr()

    _manager(home, dotfiles, dry_run=True).setup_claude_rules()
    out = capsys.readouterr().out
    assert "already correct" in out
    assert "Would" not in out


def test_dry_run_reports_a_replacement_of_an_existing_file(tmp_path, capsys):
    home, dotfiles = _tree(tmp_path)
    existing = _write(home / ".claude" / "rules" / "python.md", "hand-written\n")

    _manager(home, dotfiles, dry_run=True).setup_claude_rules()
    assert "Would replace" in capsys.readouterr().out
    assert existing.read_text() == "hand-written\n"  # untouched, and no .bak beside it
    assert not existing.with_name("python.md.bak").exists()


def test_dry_run_never_prompts(tmp_path, capsys, monkeypatch):
    """The (y/n) backup prompt would hang a dry run; it must not be reached."""
    def _fail(*args, **kwargs):
        raise AssertionError("dry run must not prompt for input")

    monkeypatch.setattr("builtins.input", _fail)
    home, dotfiles = _tree(tmp_path)
    _write(home / ".claude" / "rules" / "python.md", "hand-written\n")

    assert _manager(home, dotfiles, dry_run=True).setup_claude_rules() is True


def test_dry_run_leaves_a_prunable_link_in_place(tmp_path, capsys):
    home, dotfiles = _tree(tmp_path)
    (home / ".claude-bedrock").mkdir()
    source = _write(
        dotfiles / "src" / "assets" / "claude" / "machines" / "work" / "commands" / "bedrock.md",
        "---\nprofiles: clb\n---\n\nbody\n",
    )
    stale = home / ".claude" / "commands" / "bedrock.md"
    stale.parent.mkdir(parents=True)
    stale.symlink_to(source)

    _manager(home, dotfiles, dry_run=True).setup_local_commands()
    assert "Would remove" in capsys.readouterr().out
    assert stale.is_symlink()


def test_dry_run_predicts_what_a_real_install_then_does(tmp_path, capsys):
    """The property that makes the preview worth reading: same plan, same result."""
    home, dotfiles = _tree(tmp_path)
    _manager(home, dotfiles, dry_run=True).setup_local_commands()
    previewed = {line for line in capsys.readouterr().out.splitlines() if "Would create" in line}

    _manager(home, dotfiles, dry_run=False).setup_local_commands()
    created = sorted(path.name for path in (home / ".claude" / "commands").iterdir())

    assert len(previewed) == len(created)
    assert all(any(name in line for line in previewed) for name in created)


# --- the whole-installer preview ---------------------------------------------

# Every asset the configuration phase touches. A missing source is a hard error in
# create_symlink, so the preview can only be walked end to end against a full tree.
CONFIG_ASSETS = (
    "zshrc",
    "gitconfig",
    "vimrc",
    "AGENTS.md",
    "config/starship.toml",
    "config/ghostty/config",
    "config/aerospace/aerospace.toml",
    "config/zellij/config.kdl",
    "config/zellij/layouts/default.kdl",
    "config/zed/themes/ayu-dark-custom.json",
    "claude/statusline.sh",
    "claude/settings.shared.json",
    "claude/settings.all-profiles.json",
)


def _never_called(*args, **kwargs):
    raise AssertionError("a dry run must not reach this")


def _full_tree(tmp_path: Path) -> tuple[Path, Path]:
    """Extend the Claude-asset tree with everything else an install symlinks."""
    home, dotfiles = _tree(tmp_path)
    assets = dotfiles / "src" / "assets"
    for name in CONFIG_ASSETS:
        _write(assets / name, "{}\n" if name.endswith(".json") else "body\n")
    _write(dotfiles / "src" / "scripts" / "git_log_hyperlinks.py", "#!/usr/bin/env python3\n")
    return home, dotfiles


def _installer(home: Path, dotfiles: Path, monkeypatch) -> DotfilesInstaller:
    """A DotfilesInstaller pointed at a synthetic tree instead of the real machine."""
    monkeypatch.setattr("src.installer.installer.get_home_dir", lambda: home)
    monkeypatch.setattr("src.installer.installer.get_dotfiles_dir", lambda: dotfiles)
    monkeypatch.setattr("src.installer.symlinker.get_home_dir", lambda: home)
    return DotfilesInstaller(dry_run=True)


def test_preview_skips_the_phases_it_cannot_simulate(tmp_path, capsys, monkeypatch):
    """Dependency phases depend on what their package managers decide at run time,
    so preview says it skipped them rather than guessing."""
    home, dotfiles = _full_tree(tmp_path)
    installer = _installer(home, dotfiles, monkeypatch)
    monkeypatch.setattr(installer.system_deps, "install_system_dependencies", _never_called)
    monkeypatch.setattr(installer, "install_homebrew_packages", _never_called)

    assert installer.run() is True
    out = capsys.readouterr().out
    assert "Dry run" in out
    assert "Skipped, not previewed" in out


def test_preview_does_not_reload_the_shell(tmp_path, capsys, monkeypatch):
    """complete_installation() calls os.execv, which would replace the process."""
    home, dotfiles = _full_tree(tmp_path)
    monkeypatch.setattr("os.execv", _never_called)

    assert _installer(home, dotfiles, monkeypatch).run() is True


def test_preview_does_not_write_settings_json(tmp_path, capsys, monkeypatch):
    """The one remaining write path in a dry run: backup, temp file, then replace."""
    home, dotfiles = _full_tree(tmp_path)
    fragment = {"statusLine": {"type": "command", "command": "bash statusline.sh"}}
    _write(dotfiles / "src" / "assets" / "claude" / "settings.shared.json", json.dumps(fragment))
    settings = _write(home / ".claude" / "settings.json", "{}\n")

    assert _installer(home, dotfiles, monkeypatch).setup_claude_settings() is True

    assert settings.read_text() == "{}\n"
    assert sorted(path.name for path in (home / ".claude").iterdir()) == ["settings.json"]
    assert "Would merge" in capsys.readouterr().out


def test_preview_leaves_the_home_directory_untouched(tmp_path, capsys, monkeypatch):
    """The whole promise of --dry-run, asserted over every path the walk touches."""
    home, dotfiles = _full_tree(tmp_path)
    monkeypatch.setattr("os.execv", _never_called)
    before = {path: path.lstat().st_mtime_ns for path in home.rglob("*")}

    assert _installer(home, dotfiles, monkeypatch).run() is True

    assert {path: path.lstat().st_mtime_ns for path in home.rglob("*")} == before


def test_preview_reports_the_work_a_real_install_would_do(tmp_path, capsys, monkeypatch):
    """A preview that walked the tree but reported nothing would pass every
    'writes nothing' test above while being useless."""
    home, dotfiles = _full_tree(tmp_path)
    monkeypatch.setattr("os.execv", _never_called)

    _installer(home, dotfiles, monkeypatch).run()
    out = capsys.readouterr().out
    assert out.count("Would create") >= len(CONFIG_ASSETS)
