"""System and filesystem utilities."""

from pathlib import Path


def get_home_dir() -> Path:
    return Path.home()


def get_dotfiles_dir() -> Path:
    # This file lives at src/installer/utils/system.py — 4 levels up is the repo root.
    return Path(__file__).parent.parent.parent.parent
