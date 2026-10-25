"""Tests for removing links left dangling when an asset is deleted or renamed —
resolver.broken_repo_links() and SymlinkManager.remove_broken_links().

An install only ever removes a link that points into the repo and whose target
is gone, so these check both halves of that rule: such links are removed, and
anything else (a live link, a real file, a dangling link elsewhere) is kept."""

from pathlib import Path

from src.installer.printer import Printer
from src.installer.resolver import broken_repo_links
from src.installer.symlinker import SymlinkManager


def _write(path: Path, text: str = "body\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _link(path: Path, target: Path | str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(target)
    return path


def _tree(tmp_path: Path) -> tuple[Path, Path]:
    """Return (home, dotfiles) for a work machine with no assets yet."""
    home = tmp_path / "home"
    dotfiles = tmp_path / "dotfiles"
    _write(home / ".dotfiles-machine", "work")
    (dotfiles / "src" / "assets" / "claude" / "machines" / "work").mkdir(parents=True)
    return home, dotfiles


def _manager(home: Path, dotfiles: Path, dry_run: bool = False) -> SymlinkManager:
    manager = SymlinkManager(Printer(), dotfiles, dry_run=dry_run)
    manager.home_dir = home  # redirect symlink destinations to an isolated tmp home
    return manager


# --- broken_repo_links -------------------------------------------------------


def test_finds_a_dangling_link_into_the_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    link = _link(tmp_path / "home" / "old.md", repo / "src" / "old.md")

    assert broken_repo_links([link.parent], repo) == [link]


def test_finds_a_relative_dangling_link_into_the_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    link = _link(tmp_path / "home" / "old.md", "../repo/src/old.md")

    assert broken_repo_links([link.parent], repo) == [link]


def test_ignores_a_dangling_link_outside_the_repo(tmp_path):
    """Not ours, so not ours to delete — doctor reports these instead."""
    repo = tmp_path / "repo"
    repo.mkdir()
    link = _link(tmp_path / "home" / "other.md", tmp_path / "elsewhere" / "other.md")

    assert broken_repo_links([link.parent], repo) == []


def test_ignores_live_links_and_real_files(tmp_path):
    repo = tmp_path / "repo"
    source = _write(repo / "src" / "live.md")
    home = tmp_path / "home"
    _link(home / "live.md", source)
    _write(home / "notes.md")

    assert broken_repo_links([home], repo) == []


def test_ignores_a_link_whose_name_merely_starts_like_the_repo(tmp_path):
    """`repo-old/` shares a string prefix with `repo/` but is not inside it."""
    repo = tmp_path / "repo"
    repo.mkdir()
    link = _link(tmp_path / "home" / "old.md", tmp_path / "repo-old" / "old.md")

    assert broken_repo_links([link.parent], repo) == []


def test_scans_one_level_deep(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    home = tmp_path / "home"
    _link(home / "nested" / "old.md", repo / "old.md")

    assert broken_repo_links([home], repo) == []


def test_skips_a_missing_directory(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    assert broken_repo_links([tmp_path / "absent"], repo) == []


# --- SymlinkManager.remove_broken_links --------------------------------------


def test_removes_the_link_left_by_a_deleted_asset(tmp_path):
    """The case this exists for: delete a tracked command, re-run the install."""
    home, dotfiles = _tree(tmp_path)
    source = _write(dotfiles / "src" / "assets" / "claude" / "commands" / "plain.md")
    manager = _manager(home, dotfiles)
    assert manager.setup_claude_commands() is True
    link = home / ".claude" / "commands" / "plain.md"
    assert link.is_symlink()

    source.unlink()
    rerun = _manager(home, dotfiles)
    assert rerun.setup_claude_commands() is True
    assert rerun.remove_broken_links() is True

    assert not link.is_symlink()


def test_removes_from_a_profile_that_is_not_the_default(tmp_path):
    home, dotfiles = _tree(tmp_path)
    (home / ".claude-bedrock").mkdir()
    link = _link(home / ".claude-bedrock" / "skills" / "probe", dotfiles / "src" / "assets" / "probe")

    assert _manager(home, dotfiles).remove_broken_links() is True

    assert not link.is_symlink()


def test_removes_from_a_directory_the_run_linked_into(tmp_path):
    """$HOME is not a collection directory, but it is where zshrc gets linked."""
    home, dotfiles = _tree(tmp_path)
    _write(dotfiles / "src" / "assets" / "zshrc")
    stale = _link(home / ".oldrc", dotfiles / "src" / "assets" / "oldrc")
    manager = _manager(home, dotfiles)
    assert manager.setup_dotfiles_symlinks(["zshrc"]) is True

    assert manager.remove_broken_links() is True

    assert not stale.is_symlink()
    assert (home / ".zshrc").is_symlink()


def test_leaves_directories_the_run_did_not_link_into(tmp_path):
    home, dotfiles = _tree(tmp_path)
    stale = _link(home / ".oldrc", dotfiles / "src" / "assets" / "oldrc")

    assert _manager(home, dotfiles).remove_broken_links() is True

    assert stale.is_symlink()


def test_keeps_a_dangling_link_outside_the_repo(tmp_path):
    home, dotfiles = _tree(tmp_path)
    foreign = _link(home / ".claude" / "commands" / "mine.md", tmp_path / "elsewhere" / "mine.md")

    assert _manager(home, dotfiles).remove_broken_links() is True

    assert foreign.is_symlink()


def test_dry_run_reports_the_link_and_keeps_it(tmp_path, capsys):
    home, dotfiles = _tree(tmp_path)
    link = _link(home / ".claude" / "commands" / "plain.md", dotfiles / "src" / "assets" / "plain.md")

    assert _manager(home, dotfiles, dry_run=True).remove_broken_links() is True

    assert link.is_symlink()
    assert f"Would remove {link}" in capsys.readouterr().out


def test_dry_run_does_not_report_a_link_the_run_replaces(tmp_path, capsys):
    """A real run replaces this link rather than removing it, so a preview that
    reported a removal would describe work the install never does."""
    home, dotfiles = _tree(tmp_path)
    _write(dotfiles / "src" / "assets" / "zshrc")
    deleted_override = dotfiles / "src" / "assets" / "machines" / "work" / "zshrc"
    _link(home / ".zshrc", deleted_override)
    manager = _manager(home, dotfiles, dry_run=True)
    assert manager.setup_dotfiles_symlinks(["zshrc"]) is True

    assert manager.remove_broken_links() is True

    assert "Would remove" not in capsys.readouterr().out


def test_a_failed_removal_fails_the_step(tmp_path, capsys, monkeypatch):
    home, dotfiles = _tree(tmp_path)
    link = _link(home / ".claude" / "commands" / "plain.md", dotfiles / "src" / "assets" / "plain.md")

    def _refuse(self, missing_ok=False):
        raise PermissionError("Operation not permitted")

    monkeypatch.setattr(Path, "unlink", _refuse)

    assert _manager(home, dotfiles).remove_broken_links() is False

    assert link.is_symlink()
    assert f"Failed to remove {link}" in capsys.readouterr().out


def test_nothing_to_remove_prints_nothing(tmp_path, capsys):
    home, dotfiles = _tree(tmp_path)

    assert _manager(home, dotfiles).remove_broken_links() is True

    assert capsys.readouterr().out == ""
