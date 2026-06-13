"""Tests for the pure settings-merge logic that installs shared hooks into a
machine-local settings.json without disturbing per-machine config."""

import json

from src.installer.settings_merger import merge_settings

FRAGMENT = {
    "hooks": {
        "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "block"}]}],
        "PostToolUse": [{"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "ruff"}]}],
    }
}


def test_preserves_scalars_and_adds_hooks():
    base = {"model": "opus", "skipDangerousModePermissionPrompt": True}
    merged = merge_settings(base, FRAGMENT)
    assert merged["model"] == "opus"
    assert merged["skipDangerousModePermissionPrompt"] is True
    assert set(merged["hooks"]) == {"PreToolUse", "PostToolUse"}


def test_idempotent():
    base = {"model": "opus"}
    once = merge_settings(base, FRAGMENT)
    twice = merge_settings(once, FRAGMENT)
    assert once == twice


def test_does_not_mutate_inputs():
    base = {"model": "opus", "hooks": {"PreToolUse": []}}
    base_snapshot = json.loads(json.dumps(base))
    merge_settings(base, FRAGMENT)
    assert base == base_snapshot


def test_unions_hooks_preserving_existing():
    base = {
        "hooks": {
            "PreToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "command": "existing"}]}]
        }
    }
    merged = merge_settings(base, FRAGMENT)
    pre = merged["hooks"]["PreToolUse"]
    assert {"matcher": "Read", "hooks": [{"type": "command", "command": "existing"}]} in pre
    assert any(group["matcher"] == "Bash" for group in pre)
    assert len(pre) == 2


def test_hooks_dedup_on_remerge():
    base = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "block"}]}]}}
    merged = merge_settings(base, FRAGMENT)
    assert len(merged["hooks"]["PreToolUse"]) == 1


def test_empty_base():
    merged = merge_settings({}, FRAGMENT)
    assert merged["hooks"] == FRAGMENT["hooks"]


def test_permissions_union_dedup():
    base = {"permissions": {"deny": ["Bash(rm:*)"]}}
    fragment = {"permissions": {"deny": ["Bash(rm:*)", "Bash(curl:*)"]}}
    merged = merge_settings(base, fragment)
    assert merged["permissions"]["deny"] == ["Bash(rm:*)", "Bash(curl:*)"]


def test_preserves_unrelated_permission_keys():
    base = {"permissions": {"allow": ["Read"]}}
    fragment = {"permissions": {"deny": ["Bash(rm:*)"]}}
    merged = merge_settings(base, fragment)
    assert merged["permissions"]["allow"] == ["Read"]
    assert merged["permissions"]["deny"] == ["Bash(rm:*)"]
