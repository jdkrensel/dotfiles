"""Integration test for SymlinkManager.setup_claude_hooks against the REAL repo
tree — confirms the shared hook scripts resolve correctly on disk. Behavior
around machine-scoped hooks (marker requirement, merging) is covered against
an isolated synthetic tree in test_installer_machine_assets.py instead, since
this repo's real machines/ directory now has real per-machine content."""

from src.installer.printer import Printer
from src.installer.symlinker import SymlinkManager
from src.installer.utils import get_dotfiles_dir


def _manager_with_home(home) -> SymlinkManager:
    manager = SymlinkManager(Printer(), get_dotfiles_dir())
    manager.home_dir = home  # redirect symlink destinations to an isolated tmp home
    return manager


def test_symlinks_shared_scripts(tmp_path):
    repo = get_dotfiles_dir()
    manager = _manager_with_home(tmp_path)
    (tmp_path / ".dotfiles-machine").write_text("work")
    assert manager.setup_claude_hooks() is True

    hooks = tmp_path / ".claude" / "hooks"
    for name in ("block_dangerous_commands.py", "ruff_fix.py"):
        link = hooks / name
        assert link.is_symlink()
        assert link.resolve() == (repo / "src" / "assets" / "claude" / "hooks" / name).resolve()
