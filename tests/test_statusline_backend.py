"""Tests for the backend badge on line 1 of the status line.

Both Claude profiles on the work machine share one statusline.sh, so the badge
is the only always-visible cue for which service the session talks to — and the
answer gates whether PHI may enter the session at all.

The failure that matters is a Bedrock session that reads as Max, or worse a Max
session that reads as Bedrock, so both directions are pinned here. Color is part
of the contract rather than decoration — the badge distinguishes states at a
glance or it does nothing — so the green/orange codes are asserted on the raw
output, not stripped away.
"""

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATUSLINE = REPO_ROOT / "assets/claude/statusline.sh"

ANSI = re.compile(r"\033\[[0-9;]*m")

GREEN = "\033[32m"
ORANGE = "\033[38;5;208m"
RESET = "\033[0m"

# Every value the env var realistically takes, and whether it means Bedrock.
# Only the literal "1" does; everything else falls through to the conservative
# label. Note this is the repo's own convention — if Claude Code itself ever
# enabled Bedrock on any non-empty value, "0" would be a real Bedrock session
# labeled MAX. That is still the safe direction: the
# badge under-claims BAA coverage rather than over-claiming it.
ENV_VALUES = [("1", True), ("0", False), ("true", False), ("yes", False), ("", False), (None, False)]


def _env(tmp_path: Path, bedrock: str | None, *, bedrock_profile: bool = True) -> dict[str, str]:
    """Env for one run, with HOME redirected so the badge's profile probe is hermetic.

    TMPDIR rides along at tmp_path so the per-session git cache the status line
    writes never lands in the real temp dir.
    """
    if bedrock_profile:
        (tmp_path / ".claude-bedrock").mkdir(exist_ok=True)
    env = dict(os.environ)
    env["HOME"] = str(tmp_path)
    env["TMPDIR"] = str(tmp_path)
    env.pop("CLAUDE_CODE_USE_BEDROCK", None)
    if bedrock is not None:
        env["CLAUDE_CODE_USE_BEDROCK"] = bedrock
    return env


def run_statusline(tmp_path: Path, bedrock: str | None, *, bedrock_profile: bool = True) -> str:
    """Invoke the status line outside any git repo; return line 1 with ANSI intact."""
    payload = {"model": {"display_name": "Opus 5"}, "workspace": {"current_dir": str(tmp_path)}}
    result = subprocess.run(
        ["bash", str(STATUSLINE)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=_env(tmp_path, bedrock, bedrock_profile=bedrock_profile),
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.splitlines()[0]


def test_bedrock_session_is_labeled_bedrock(tmp_path):
    line = run_statusline(tmp_path, "1")
    assert f"{GREEN}BEDROCK{RESET}" in line
    assert "[BEDROCK Opus 5]" in ANSI.sub("", line)


def test_default_session_is_labeled_max(tmp_path):
    line = run_statusline(tmp_path, None)
    assert f"{ORANGE}MAX{RESET}" in line
    assert "[MAX Opus 5]" in ANSI.sub("", line)


@pytest.mark.parametrize(("value", "is_bedrock"), ENV_VALUES)
def test_only_literal_one_reads_as_bedrock(tmp_path, value, is_bedrock):
    plain = ANSI.sub("", run_statusline(tmp_path, value))
    assert ("[BEDROCK Opus 5]" in plain) is is_bedrock
    assert ("[MAX Opus 5]" in plain) is not is_bedrock


def test_badge_is_hidden_on_machines_with_no_bedrock_profile(tmp_path):
    """Nothing to distinguish there, and an always-on warning color is one you stop seeing."""
    line = run_statusline(tmp_path, None, bedrock_profile=False)
    plain = ANSI.sub("", line)
    assert plain.startswith("[Opus 5]")
    assert "MAX" not in plain
    assert ORANGE not in line


def test_badge_still_shows_if_the_env_var_is_set_without_a_local_profile(tmp_path):
    """The env var is the authoritative signal; a missing dir must not suppress it."""
    line = run_statusline(tmp_path, "1", bedrock_profile=False)
    assert "[BEDROCK Opus 5]" in ANSI.sub("", line)
