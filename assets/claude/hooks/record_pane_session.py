#!/usr/bin/env python3
"""SessionStart hook: record which conversation a Zellij pane is currently on.

bin/claude-session gives each pane a token, puts it in the pane's argv, and
exports it as CLAUDE_PANE_TOKEN. Zellij snapshots that argv, but argv is fixed at
launch — so a conversation switched to later with /resume would be invisible to
the snapshot, and a restart would reopen whichever conversation the pane started
with. This hook closes the gap by writing the live session id next to the token
every time a session starts, resumes, clears or compacts. The wrapper reads it
back when the pane is resurrected.

The token is exported, so it also reaches every process Claude spawns — including
a nested `claude` run from a tool call, whose SessionStart would otherwise point
the pane at a throwaway conversation. Such a session is recognised by its parent:
the pane's own Claude was started by the wrapper, a nested one was not.

A no-op outside a wrapped pane, so ordinary `claude` sessions leave nothing
behind. Registered for SessionStart in settings.shared.json.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Both values name a file on disk, so neither is trusted to be a plain word.
SESSION_ID_PATTERN = re.compile(r"\A[0-9a-fA-F-]{36}\Z")

# Enough to cross the shell Claude runs hooks through, and the tool process a
# nested session would sit behind, without walking to init on a surprise.
MAX_ANCESTRY_DEPTH = 12


def config_dir() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")


def process_table() -> dict[int, tuple[int, str]]:
    """Every process as pid -> (parent pid, command name), from one ps snapshot."""
    try:
        listing = subprocess.run(
            ["ps", "-Ao", "pid=,ppid=,comm="],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {}

    table: dict[int, tuple[int, str]] = {}
    for line in listing.splitlines():
        fields = line.split(maxsplit=2)
        if len(fields) == 3 and fields[0].isdigit() and fields[1].isdigit():
            table[int(fields[0])] = (int(fields[1]), os.path.basename(fields[2]))

    return table


def owning_claude(table: dict[int, tuple[int, str]], start_pid: int) -> int | None:
    """The nearest Claude this hook is running under, or None if unidentifiable."""
    pid = start_pid
    for _ in range(MAX_ANCESTRY_DEPTH):
        entry = table.get(pid)
        if entry is None:
            return None

        parent_pid, command = entry
        if command == "claude":
            return pid

        pid = parent_pid

    return None


def belongs_to_the_pane(wrapper_pid: str) -> bool:
    """Whether this session is the pane's own, rather than one nested inside it.

    Unrecognisable ancestry is treated as the pane's own: the cost of a stray note
    is a pane that resumes the wrong conversation, while refusing to write at all
    would silently drop the feature wherever ps output is unfamiliar."""
    if not wrapper_pid.isdigit():
        return True

    table = process_table()
    claude_pid = owning_claude(table, os.getppid())
    if claude_pid is None:
        return True

    return table[claude_pid][0] == int(wrapper_pid)


def main() -> None:
    token = os.environ.get("CLAUDE_PANE_TOKEN", "")
    if not SESSION_ID_PATTERN.match(token):
        sys.exit(0)

    if not belongs_to_the_pane(os.environ.get("CLAUDE_PANE_PID", "")):
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        sys.exit(0)

    if not isinstance(data, dict):
        sys.exit(0)

    session_id = str(data.get("session_id", ""))
    if not SESSION_ID_PATTERN.match(session_id):
        sys.exit(0)

    note = config_dir() / "pane-sessions" / token
    try:
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(session_id + "\n")
    except OSError:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
