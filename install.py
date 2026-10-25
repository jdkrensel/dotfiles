"""Shortcut entry point: `uv run -m install` runs the dotfiles installer.

Every flag and subcommand passes through, so `uv run -m install --dry-run` and
`uv run -m install doctor` work too. `uv run -m src.installer` still works.
"""

import sys

from src.installer.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
