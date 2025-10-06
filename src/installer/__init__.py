"""
Dotfiles Installer Package

A Python package for installing and configuring dotfiles with support for:
- Prerequisites installation (Homebrew, Rust, nvm)
- Configuration file symlinking
- Git alias setup
- Cross-platform support (macOS, WSL/Linux)
"""

__version__ = "1.0.0"
__author__ = "Jesse Krensel"

from .installer import DotfilesInstaller

__all__ = [
    "DotfilesInstaller"
]
