"""Tests for the selftest-static SessionStart hook (work machine, locked Max profile).

The hook reads ~/.claude/settings.json and the guard scripts beside it, and
reports any PHI safeguard that is no longer configured. A clean run prints one
"intact" line; a failing one prints SessionStart JSON whose systemMessage lists
each problem. It never blocks the session.

HOME points at tmp_path, so every run reads a settings file built here, never
the real one.
"""

import json
import os
import subprocess
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "assets/machines/work/claude/hooks/selftest-static.sh"

GUARD_HOOKS = ["phi-guard.sh", "gitignore-guard.sh", "prompt-guard.sh"]
# Variables that change which profile the hook thinks it is in, or what it skips.
SCOPING_VARS = ("CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CONFIG_DIR", "SELFTEST_SKIP_LOG_CHECK")
ASK_RULES = ["Read(**/*.xlsx)", "Read(**/*.csv)", "Read(**/*.parquet)", "Read(~/Downloads/**)", "Read(~/Desktop/**)"]


def healthy_settings() -> dict[str, Any]:
    """A settings.json that passes every check."""
    return {
        "sandbox": {
            "enabled": True,
            "network": {"allowedDomains": []},
            "filesystem": {
                "allowRead": [
                    "~/repos/*/aaos/registries/*/spec/data/**/*",
                    "~/repos/*/clients/AJRR_queries/**/*",
                    "~/Documents/ajrr_docs",
                    "~/Documents/asr_docs",
                ]
            },
            "allowUnsandboxedCommands": False,
            "failIfUnavailable": True,
        },
        "permissions": {"deny": ["Bash(mysql *)", "Bash(logcli *)"], "ask": list(ASK_RULES)},
        "hooks": {
            "PreToolUse": [
                {"hooks": [{"type": "command", "command": f"bash ~/.claude/hooks/{h}"}]}
                for h in ("phi-guard.sh", "gitignore-guard.sh")
            ],
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "bash ~/.claude/hooks/prompt-guard.sh"}]}],
        },
    }


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """A home whose profile is fully guarded and whose probe suite passed today."""
    claude = tmp_path / ".claude"
    hooks = claude / "hooks"
    hooks.mkdir(parents=True)
    for name in GUARD_HOOKS:
        script = hooks / name
        script.write_text("#!/bin/bash\nexit 0\n")
        script.chmod(0o755)
    (claude / "settings.json").write_text(json.dumps(healthy_settings()))
    (claude / "selftest-full.log").write_text(f"RESULT {date.today():%Y-%m-%d}: ALL PASS\n")
    return tmp_path


def write_settings(home: Path, settings: dict[str, Any]) -> None:
    (home / ".claude" / "settings.json").write_text(json.dumps(settings))


def run_hook(home: Path, **env: str) -> subprocess.CompletedProcess[str]:
    """Run the hook as the Max profile would, with HOME at the test home."""
    inherited = {k: v for k, v in os.environ.items() if k not in SCOPING_VARS}
    result = subprocess.run(
        ["bash", str(HOOK)], check=False, input="{}", capture_output=True, text=True, env={**inherited, "HOME": str(home), **env}
    )
    assert result.returncode == 0, result.stderr
    return result


def run_check(home: Path, **env: str) -> str:
    """Run the hook; return what it reports ("" for silence)."""
    out = run_hook(home, **env).stdout.strip()
    if out.startswith("{"):
        return json.loads(out)["systemMessage"]
    return out


def test_healthy_profile_reports_intact(home: Path) -> None:
    assert run_check(home) == "Guard selftest: all PHI safeguards intact."


def test_failures_reach_both_user_and_claude(home: Path) -> None:
    (home / ".claude" / "settings.json").unlink()
    payload = json.loads(run_hook(home).stdout)
    assert payload["systemMessage"] == payload["hookSpecificOutput"]["additionalContext"]
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"


def test_bedrock_session_is_skipped(home: Path) -> None:
    (home / ".claude" / "settings.json").unlink()
    assert run_check(home, CLAUDE_CODE_USE_BEDROCK="1") == ""


def test_other_profile_dir_is_skipped(home: Path) -> None:
    (home / ".claude" / "settings.json").unlink()
    assert run_check(home, CLAUDE_CONFIG_DIR=str(home / ".claude-bedrock")) == ""


def test_default_profile_dir_named_explicitly_still_checks(home: Path) -> None:
    (home / ".claude" / "settings.json").unlink()
    assert "settings.json is missing" in run_check(home, CLAUDE_CONFIG_DIR=str(home / ".claude"))


def test_missing_settings_is_reported(home: Path) -> None:
    (home / ".claude" / "settings.json").unlink()
    assert "settings.json is missing or not valid JSON" in run_check(home)


def test_invalid_settings_json_is_reported(home: Path) -> None:
    (home / ".claude" / "settings.json").write_text("{not json")
    assert "settings.json is missing or not valid JSON" in run_check(home)


@pytest.mark.parametrize("name", GUARD_HOOKS)
def test_unregistered_guard_hook_is_reported(home: Path, name: str) -> None:
    settings = healthy_settings()
    for event in settings["hooks"].values():
        for group in event:
            group["hooks"] = [h for h in group["hooks"] if name not in h["command"]]
    write_settings(home, settings)
    assert f"hook not registered in settings.json: {name}" in run_check(home)


@pytest.mark.parametrize("name", GUARD_HOOKS)
def test_non_executable_guard_hook_is_reported(home: Path, name: str) -> None:
    (home / ".claude" / "hooks" / name).chmod(0o644)
    assert f"hook script missing or not executable: {name}" in run_check(home)


def test_sandbox_off_is_reported(home: Path) -> None:
    settings = healthy_settings()
    settings["sandbox"]["enabled"] = False
    write_settings(home, settings)
    assert "sandbox.enabled is not true" in run_check(home)


def test_network_egress_is_reported(home: Path) -> None:
    settings = healthy_settings()
    settings["sandbox"]["network"]["allowedDomains"] = ["example.com"]
    write_settings(home, settings)
    assert "sandbox network allowlist is not empty" in run_check(home)


@pytest.mark.parametrize("rule", ["Bash(mysql *)", "Bash(logcli *)"])
def test_missing_deny_rule_is_reported(home: Path, rule: str) -> None:
    settings = healthy_settings()
    settings["permissions"]["deny"].remove(rule)
    write_settings(home, settings)
    assert f"permissions.deny rule missing: {rule}" in run_check(home)


@pytest.mark.parametrize("rule", ASK_RULES)
def test_missing_ask_rule_is_reported(home: Path, rule: str) -> None:
    settings = healthy_settings()
    settings["permissions"]["ask"].remove(rule)
    write_settings(home, settings)
    assert f"permissions.ask rule missing: {rule}" in run_check(home)


def test_ask_rule_also_in_deny_is_reported(home: Path) -> None:
    """Deny outranks ask, so a rule in both can never be approved."""
    settings = healthy_settings()
    settings["permissions"]["deny"].append("Read(**/*.csv)")
    write_settings(home, settings)
    assert "rule sits in deny AND ask, so it can never be approved: Read(**/*.csv)" in run_check(home)


def test_spec_carve_out_pinned_to_one_clone_is_reported(home: Path) -> None:
    settings = healthy_settings()
    settings["sandbox"]["filesystem"]["allowRead"][0] = "~/repos/sqs_importer/aaos/registries/*/spec/data/**/*"
    write_settings(home, settings)
    assert "pins a clone name" in run_check(home)


@pytest.mark.parametrize(
    ("index", "fragment"),
    [(0, "aaos/registries/[^/]*/spec/data"), (1, "clients/AJRR_queries")],
    ids=["spec-data", "ajrr-queries"],
)
def test_missing_spec_carve_out_is_reported(home: Path, index: int, fragment: str) -> None:
    settings = healthy_settings()
    del settings["sandbox"]["filesystem"]["allowRead"][index]
    write_settings(home, settings)
    assert f"allowRead has no entry for {fragment}" in run_check(home)


def test_spec_carve_out_glob_without_subtree_suffix_is_reported(home: Path) -> None:
    """A bare-directory glob matches the directory itself, not the files in it."""
    settings = healthy_settings()
    settings["sandbox"]["filesystem"]["allowRead"][1] = "~/repos/*/clients/AJRR_queries"
    write_settings(home, settings)
    assert "lacks a /**/* subtree suffix" in run_check(home)


@pytest.mark.parametrize("directory", ["ajrr_docs", "asr_docs"])
def test_missing_spec_document_dir_is_reported(home: Path, directory: str) -> None:
    settings = healthy_settings()
    settings["sandbox"]["filesystem"]["allowRead"].remove(f"~/Documents/{directory}")
    write_settings(home, settings)
    assert f"allowRead missing ~/Documents/{directory}" in run_check(home)


@pytest.mark.parametrize(
    ("key", "value"), [("allowUnsandboxedCommands", True), ("failIfUnavailable", False)]
)
def test_strict_mode_key_left_off_is_reported(home: Path, key: str, value: bool) -> None:
    settings = healthy_settings()
    settings["sandbox"][key] = value
    write_settings(home, settings)
    assert f"strict mode pending: set sandbox.{key}" in run_check(home)


def test_probe_suite_that_never_ran_is_reported(home: Path) -> None:
    (home / ".claude" / "selftest-full.log").unlink()
    assert "dynamic probe suite has never run" in run_check(home)


def test_failed_probe_run_is_reported(home: Path) -> None:
    (home / ".claude" / "selftest-full.log").write_text(f"RESULT {date.today():%Y-%m-%d}: FAIL (2 probes)\n")
    assert "last dynamic probe run FAILED" in run_check(home)


def test_stale_probe_run_is_reported(home: Path) -> None:
    # 10, not 9: the hook floors elapsed seconds to whole days, so a 9-day span
    # that crosses the spring DST change counts as 8 and is not yet stale.
    old = date.today() - timedelta(days=10)
    (home / ".claude" / "selftest-full.log").write_text(f"RESULT {old:%Y-%m-%d}: ALL PASS\n")
    assert "dynamic probe suite is stale" in run_check(home)


def test_probe_log_check_can_be_skipped(home: Path) -> None:
    """The probe suite calls this hook itself, before it has logged a result."""
    (home / ".claude" / "selftest-full.log").unlink()
    assert run_check(home, SELFTEST_SKIP_LOG_CHECK="1") == "Guard selftest: all PHI safeguards intact."
