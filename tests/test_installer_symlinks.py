"""Integration tests for SymlinkManager.setup_claude_hooks — symlinks the shared
hook scripts into ~/.claude/hooks (and work-only ones from hooks/local/)."""

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
    assert manager.setup_claude_hooks() is True

    hooks = tmp_path / ".claude" / "hooks"
    for name in ("block_dangerous_commands.py", "ruff_fix.py"):
        link = hooks / name
        assert link.is_symlink()
        assert link.resolve() == (repo / "src" / "assets" / "claude" / "hooks" / name).resolve()


def test_only_shared_when_no_local_dir(tmp_path):
    manager = _manager_with_home(tmp_path)
    manager.setup_claude_hooks()
    hooks = tmp_path / ".claude" / "hooks"
    linked = sorted(p.name for p in hooks.iterdir() if p.is_symlink())
    assert linked == ["block_dangerous_commands.py", "ruff_fix.py"]
