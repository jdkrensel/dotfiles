"""Pure helpers for merging the tracked shared Claude settings fragment into a
machine-local ~/.claude/settings.json.

settings.json is a mixed file: Claude writes per-machine scalars (model,
effortLevel) into it, and the auto-grown permission allow-list lives alongside in
settings.local.json. We therefore never symlink settings.json — the installer
merges only the shared, machine-agnostic keys (hooks, and optionally generic
permission rules) into it, leaving everything else untouched. The merge is
idempotent so it can run safely on every install.
"""

from __future__ import annotations

from typing import Any


def _union_hook_event(base: list[Any], shared: list[Any]) -> list[Any]:
    """Append shared matcher-groups that aren't already present (dedup by equality)."""
    merged = list(base)
    for group in shared:
        if group not in merged:
            merged.append(group)
    return merged


def merge_settings(base: dict[str, Any], fragment: dict[str, Any]) -> dict[str, Any]:
    """Return ``base`` with the shared ``fragment`` merged in.

    - ``hooks``: union per event, de-duplicated.
    - ``permissions`` (allow/deny/ask): union of the string lists, de-duplicated.
    - every other key in ``base`` (model, effortLevel, runtime scalars) is preserved.

    The fragment is expected to contain only shared, machine-agnostic keys.
    """
    result = dict(base)

    fragment_hooks = fragment.get("hooks") or {}
    if fragment_hooks:
        merged_hooks = dict(result.get("hooks") or {})
        for event, groups in fragment_hooks.items():
            merged_hooks[event] = _union_hook_event(merged_hooks.get(event, []), groups)
        result["hooks"] = merged_hooks

    fragment_perms = fragment.get("permissions") or {}
    if fragment_perms:
        merged_perms = dict(result.get("permissions") or {})
        for key, values in fragment_perms.items():
            existing = list(merged_perms.get(key, []))
            merged_perms[key] = existing + [v for v in values if v not in existing]
        result["permissions"] = merged_perms

    return result
