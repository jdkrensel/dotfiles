#!/usr/bin/env python3
"""confirm_installs_and_git_remote_ops.py — PreToolUse hook (every machine, default profile)

Does: asks for confirmation before a Bash command that installs or removes
      packages (pip, uv, brew, apt, global npm, gem, cargo, go), or runs
      git push/pull/fetch/rebase. The full list is PATTERNS below.
Why:  these install or remove packages, or touch git remotes or history, so
      each one needs a person's approval, even in bypass-permissions mode.
Runs: PreToolUse with the Bash matcher, registered in settings.shared.json.
Exit: 0. A match prints permissionDecision "ask"; anything else, including
      unparseable JSON, prints nothing. A payload that is not an object, or a
      null command, crashes with exit 1, a non-blocking error. It never
      blocks: the user can approve on the spot.

The "ask" prompts for confirmation even in bypass-permissions mode, where
normal prompts are skipped.
"""

from __future__ import annotations

import json
import re
import sys

# (regex pattern, human-readable reason) — matched against the full Bash command.
PATTERNS: list[tuple[str, str]] = [
    (r"\b(?:pip|pip3)\s+(?:install|uninstall)\b", "pip install/uninstall"),
    (r"\bpipx\s+(?:install|uninstall)\b", "pipx install/uninstall"),
    (r"\buv\s+(?:add|remove)\b", "uv add/remove"),
    (r"\buv\s+pip\s+(?:install|uninstall)\b", "uv pip install/uninstall"),
    (r"\buv\s+tool\s+(?:install|uninstall)\b", "uv tool install/uninstall"),
    (r"\bbrew\s+(?:install|uninstall|upgrade)\b", "brew install/uninstall/upgrade"),
    (r"\bapt(?:-get)?\s+(?:install|remove|purge|upgrade|autoremove)\b", "apt package change"),
    (r"\bnpm\s+(?:install|i|uninstall)\b.*(?:\s-g\b|\s--global\b)", "global npm package change"),
    (r"\b(?:yarn\s+global|pnpm)\s+(?:add|remove)\b", "global node package change"),
    (r"\bgem\s+(?:install|uninstall)\b", "gem install/uninstall"),
    (r"\bcargo\s+install\b", "cargo install"),
    (r"\bgo\s+install\b", "go install"),
    (r"\bgit\s+(?:push|pull|fetch|rebase)\b", "remote/history git operation (push/pull/fetch/rebase)"),
]


def main() -> None:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    command = data.get("tool_input", {}).get("command", "")
    for pattern, reason in PATTERNS:
        if re.search(pattern, command):
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "ask",
                            "permissionDecisionReason": f"Confirm before running: {reason}.",
                        }
                    }
                )
            )
            return
    # No match: stay silent and let the normal permission flow proceed.


if __name__ == "__main__":
    main()
