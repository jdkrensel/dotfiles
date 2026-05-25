## Project Context

This is primarily a Python codebase. Use Python conventions, type hints, and Pydantic models. YAML is used for configs. When reading files, always verify you're reading the current branch/version before reviewing.

## Interaction Rules

- When asked to review or explain code, ALWAYS explain first before making any changes. Do not edit files unless explicitly asked to do so.
- When the user corrects your understanding or rejects an approach, do NOT re-suggest the same approach later in the session. Acknowledge the correction and move on.

## Code Style & Design

- Prefer simple, minimal solutions. Do not propose abstractions, wrappers, or architectural patterns beyond what is explicitly requested. When in doubt, ask before adding complexity.
- Python: NEVER put import statements anywhere other than the top of the file. All imports must be at the beginning of the file, before any other code.
- Python: always use modern type hint syntax (Python 3.9+) — use lowercase built-in types `list`, `dict`, `tuple` instead of importing `List`, `Dict`, `Tuple` from typing. For example: `list[int]`, `dict[str, int]`, `tuple[str, ...]`.

## System Dependencies

Never install, upgrade, or remove system-level packages without explicit user permission. This includes but is not limited to: `brew install`, `brew uninstall`, `apt install`, `apt upgrade`, `pip install` (outside a project virtualenv managed by uv), `npm install -g`, or any other package manager that modifies the system environment. If a dependency is missing, identify it and ask the user before proceeding.

## Debugging

When debugging or investigating issues, present your hypothesis and the evidence for it. Do NOT assert a root cause unless you can prove it with code or data. If the user disproves a hypothesis, move on to a genuinely different angle.

## Git & Commits

- Always use the `/commit` slash command when making git commits. Do NOT run `git commit` directly.
- Never automatically interact with the remote repository. Do NOT run `git push`, `git pull`, `git fetch`, or `git rebase` unless the user explicitly asks.
- For commit messages, use the EXACT wording the user provides. Do not paraphrase, reorder, or "improve" commit messages unless asked.
- Keep commits atomic: commit only the files you touched and list each path explicitly.
  - Tracked files: `git commit -m "<scoped message>" -- path/to/file1 path/to/file2`
  - Brand-new files: `git restore --staged :/ && git add "path/to/file1" "path/to/file2" && git commit -m "<scoped message>" -- path/to/file1 path/to/file2`

## Documentation & APIs

Always use Context7 (via `mcp__plugin_context7_context7__resolve-library-id` and `mcp__plugin_context7_context7__query-docs`) when working with library documentation, API references, code generation, or setup/configuration steps — without waiting to be asked.

## Agent Delegation

Delegate ALL substantive tasks (file reads, edits, research, implementation, testing) to subagents via the Task tool. Use the main session only for coordination and final output.

## CLI Structure

For Click CLI apps, put each command in `cli/<command-name>.py` (no `_command` suffix). The file name matches the command name exactly.

## Implementation Plans

For any substantial code change NOT using plan mode, write the implementation plan to a scratch file before starting work — e.g. `./tmp/<short-topic>-plan.md`. The file should capture the goal, the files to touch, and the step-by-step approach. This preserves context across auto-compaction. Delete the file when the work is complete and verified. "Substantial" = multi-file changes, anything requiring sequencing, or work that will span more than a few tool calls. Trivial edits (typo fixes, single-line changes, one-off questions) do not need a plan file.

## Temporary Files & Scripts

- Analysis scripts, one-off queries, and other short-lived scripts go to `/tmp` by default — do NOT persist them in the repo unless explicitly asked.
- If a task spans multiple days (e.g. a plan file or a script you'll need tomorrow), use `./tmp/` instead — it's project-scoped and survives reboots. Add `./tmp/` to `.gitignore` if it isn't already.
- Only write a script to the repo root (or another permanent location) when the user explicitly asks to keep it.

## Tests

- When adding new code (new functions, classes, modules, features), add corresponding tests in the same change. Follow the project's existing test conventions and location.
- When modifying existing code, run the relevant tests after the change and report the result. If the project has no tests for the touched area, say so explicitly rather than skipping silently.
- If the test command isn't obvious from the project, ask before guessing.
