"""
Utilities package for the dotfiles installer.

This package provides organized utility functions for shell operations,
system detection, and process inspection.
"""

# Export only the functions that are actually used by the main modules
from .shell import run_command, command_exists
from .system import get_home_dir, get_dotfiles_dir, is_wsl, is_macos, is_linux
from .process import get_parent_process_name

__all__ = [
    "run_command",
    "command_exists", 
    "get_home_dir",
    "get_dotfiles_dir",
    "is_wsl",
    "is_macos", 
    "is_linux",
    "get_parent_process_name",
]
