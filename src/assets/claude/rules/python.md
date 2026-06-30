---
paths:
  - "**/*.py"
---

# Python

- Use modern type-hint syntax (3.9+): lowercase built-in generics — `list[int]`, `dict[str, int]`, `tuple[str, ...]` — never `List`/`Dict`/`Tuple` from `typing`.
- Put all imports at the top of the file, before any other code — never inside functions or mid-module.
- Use type hints throughout, and Pydantic models for structured data.
- CLIs: use Click. Put each command in `cli/<command-name>.py` (no `_command` suffix); the filename matches the command name exactly.
- Type-check with both `ruff check` and `basedpyright`, and resolve issues from both — a clean basedpyright run is part of "done".
- NEVER add `assert` statements to satisfy the type checker. Fix types properly: correct/add annotations, narrow with `isinstance`/`is not None` guards, use `typing.cast()`, or restructure. (`assert` masks the issue with a runtime check that `python -O` strips.)

<!-- The type-hint and import rules are auto-enforced by the ruff PostToolUse hook (hooks/ruff_fix.py) when ruff is available; this file documents intent and is the fallback on machines without ruff. -->
