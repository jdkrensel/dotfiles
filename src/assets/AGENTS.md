## Project Context

This is primarily a Python codebase. Use Python conventions, type hints, and Pydantic models. YAML is used for configs. When reading files, always verify you're reading the current branch/version before reviewing.

## Interaction Rules

- When asked to review or explain code, ALWAYS explain first before making any changes. Do not edit files unless explicitly asked to do so.
- When the user corrects your understanding or rejects an approach, do NOT re-suggest the same approach later in the session. Acknowledge the correction and move on.

## Code Style & Design

- Prefer simple, minimal solutions. Do not propose abstractions, wrappers, or architectural patterns beyond what is explicitly requested. When in doubt, ask before adding complexity.
- Python: NEVER put import statements anywhere other than the top of the file. All imports must be at the beginning of the file, before any other code.
- Python: always use modern type hint syntax (Python 3.9+) — use lowercase built-in types `list`, `dict`, `tuple` instead of importing `List`, `Dict`, `Tuple` from typing. For example: `list[int]`, `dict[str, int]`, `tuple[str, ...]`.

## Debugging

When debugging or investigating issues, present your hypothesis and the evidence for it. Do NOT assert a root cause unless you can prove it with code or data. If the user disproves a hypothesis, move on to a genuinely different angle.

## Git & Commits

- For commit messages, use the EXACT wording the user provides. Do not paraphrase, reorder, or "improve" commit messages unless asked.
- Keep commits atomic: commit only the files you touched and list each path explicitly.
  - Tracked files: `git commit -m "<scoped message>" -- path/to/file1 path/to/file2`
  - Brand-new files: `git restore --staged :/ && git add "path/to/file1" "path/to/file2" && git commit -m "<scoped message>" -- path/to/file1 path/to/file2`

## Documentation & APIs

Always use Context7 (via `mcp__plugin_context7_context7__resolve-library-id` and `mcp__plugin_context7_context7__query-docs`) when working with library documentation, API references, code generation, or setup/configuration steps — without waiting to be asked.

## Agent Delegation

Delegate ALL substantive tasks (file reads, edits, research, implementation, testing) to subagents via the Task tool. Use the main session only for coordination and final output.
