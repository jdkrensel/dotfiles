#!/usr/bin/env python3
"""
Dotfiles Installer Application Entry Point

Contains the main execution logic for the installer package.
Launch with: python3 -m src.installer
"""
import logging
import sys

from .installer import DotfilesInstaller

logger = logging.getLogger(__name__)

def main() -> int:
    """
    Main entry point for the installer.

    Returns:
        int: The process exit code (0 for success, non-zero for failure).
    """
    try:
        success = DotfilesInstaller().run()
        return 0 if success else 1
    except Exception:
        logger.exception("An unhandled error occurred during installation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())