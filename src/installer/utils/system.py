"""
System and filesystem utilities.

This module provides functions for detecting the operating system,
getting directory paths, and other system-related operations.
"""

import os
import sys
from pathlib import Path


def get_home_dir() -> Path:
    """
    Get the user's home directory.
    
    Returns:
        Path object representing the user's home directory
    """
    return Path.home()


def get_dotfiles_dir() -> Path:
    """
    Get the dotfiles directory (where this script is located).
    
    Returns:
        Path object representing the dotfiles root directory
    """
    return Path(__file__).parent.parent.parent.parent


def is_wsl() -> bool:
    """
    Check if running on Windows Subsystem for Linux (WSL).
    
    Returns:
        True if running on WSL, False otherwise
    """
    return os.path.exists("/proc/version") and "microsoft" in open("/proc/version").read().lower()


def is_macos() -> bool:
    """
    Check if running on macOS.
    
    Returns:
        True if running on macOS, False otherwise
    """
    return sys.platform == "darwin"


def is_linux() -> bool:
    """
    Check if running on Linux.
    
    Returns:
        True if running on Linux, False otherwise
    """
    return sys.platform == "linux"
