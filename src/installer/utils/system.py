"""System and filesystem utilities."""

import os
import sys
from pathlib import Path


def get_home_dir() -> Path:
    return Path.home()


def get_dotfiles_dir() -> Path:
    # This file lives at src/installer/utils/system.py — 4 levels up is the repo root.
    return Path(__file__).parent.parent.parent.parent


def is_wsl() -> bool:
    if not os.path.exists("/proc/version"):
        return False
    with open("/proc/version") as f:
        return "microsoft" in f.read().lower()


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_linux() -> bool:
    return sys.platform == "linux"
