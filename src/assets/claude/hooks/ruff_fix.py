#!/usr/bin/env python3
"""PostToolUse hook: enforce Python import placement and modern type hints with ruff.

Runs after Edit/Write on a *.py file. Auto-fixes import ordering (I) and modern
type-hint syntax (UP), then reports any remaining import-placement issues (E402)
back to Claude so it can fix them by hand. No-op when ruff is unavailable, so the
rules/python.md guidance stays the fallback. Registered for Edit|Write in
settings.shared.json.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

SELECT = "I,UP,E402"


def find_ruff(cwd: str) -> str | None:
    venv_ruff = os.path.join(cwd, ".venv", "bin", "ruff")
    if os.path.isfile(venv_ruff) and os.access(venv_ruff, os.X_OK):
        return venv_ruff
    return shutil.which("ruff")


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path.endswith(".py") or not os.path.isfile(file_path):
        sys.exit(0)

    cwd = data.get("cwd") or os.getcwd()
    ruff = find_ruff(cwd)
    if ruff is None:
        sys.exit(0)

    result = subprocess.run(
        [ruff, "check", "--fix", "--select", SELECT, file_path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 and result.stdout.strip():
        # Violations ruff could not auto-fix (e.g. E402 imports not at top of file).
        print(result.stdout.strip(), file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
