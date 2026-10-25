"""Tests for selftest-full.sh, the weekly probe suite (work machine, Max profile).

The real suite spawns headless Claude sessions that try blocked actions. Here a
fake `claude` on CLAUDE_BIN stands in for them and replies with fixed text, so
the tests cover the suite's own logic: which marker counts as a pass, the
final RESULT line the config check reads back, and the call into
selftest-static.sh at ~/.claude/hooks.

HOME and TMPDIR point at tmp_path, so the probe cleanup and the throwaway
working directory stay inside the test.
"""

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SUITE = REPO_ROOT / "assets/machines/work/claude/hooks/selftest-full.sh"

# What a correctly guarded profile makes each probe print.
ALL_BLOCKED = "NET_BLOCKED WRITE_BLOCKED CRED_BLOCKED DL_BLOCKED XLSX_BLOCKED WL_READABLE Prompt guard: blocked"

# Each must-block probe: the marker a blocked attempt prints, and the probe's label.
BLOCK_PROBES = [
    ("NET_BLOCKED", "network egress blocked"),
    ("WRITE_BLOCKED", "write outside cwd blocked"),
    ("CRED_BLOCKED", "credential read blocked"),
    ("DL_BLOCKED", "Downloads read blocked"),
    ("XLSX_BLOCKED", "xlsx read blocked outside whitelist"),
]


def executable(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/bash\n{body}\n")
    path.chmod(0o755)
    return path


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """A home whose static config check passes."""
    executable(tmp_path / ".claude/hooks/selftest-static.sh", 'echo "Guard selftest: all PHI safeguards intact."')
    return tmp_path


def run_suite(home: Path, claude_reply: str | None) -> subprocess.CompletedProcess[str]:
    """Run the suite against a fake claude that always prints claude_reply.

    None leaves CLAUDE_BIN empty and PATH without claude, as on a machine where
    it is not installed.
    """
    inherited = {k: v for k, v in os.environ.items() if k != "SELFTEST_SKIP_LOG_CHECK"}
    env = {**inherited, "HOME": str(home), "TMPDIR": str(home)}
    if claude_reply is None:
        env.update(CLAUDE_BIN="", PATH="/usr/bin:/bin")
    else:
        fake = executable(home / "bin/claude", f"cat >/dev/null\necho '{claude_reply}'")
        env["CLAUDE_BIN"] = str(fake)
    return subprocess.run(["bash", str(SUITE)], check=False, capture_output=True, text=True, env=env)


def result_line(run: subprocess.CompletedProcess[str]) -> str:
    return [line for line in run.stdout.splitlines() if line.startswith("RESULT ")][-1]


def test_guarded_profile_passes_every_probe(home: Path) -> None:
    run = run_suite(home, ALL_BLOCKED)
    assert run.returncode == 0, run.stdout
    assert result_line(run).endswith(": ALL PASS")
    assert "FAIL" not in run.stdout


@pytest.mark.parametrize(("marker", "label"), BLOCK_PROBES, ids=[m for m, _ in BLOCK_PROBES])
def test_a_probe_that_gets_through_fails_the_run(home: Path, marker: str, label: str) -> None:
    """Each probe keys on its own marker, so losing one fails exactly that probe."""
    run = run_suite(home, ALL_BLOCKED.replace(marker, marker.replace("BLOCKED", "OK")))
    assert run.returncode == 1
    assert f"FAIL: {label}" in run.stdout
    assert result_line(run).endswith(": FAIL (1 probes)")


def test_whitelisted_spec_read_is_probed_when_the_file_exists(home: Path) -> None:
    (home / "Documents/ajrr_docs").mkdir(parents=True)
    (home / "Documents/ajrr_docs/AJRR_MDD_2026.xlsx").write_bytes(b"PK")
    assert "PASS: whitelisted spec xlsx readable" in run_suite(home, ALL_BLOCKED).stdout


def test_blocked_whitelisted_spec_read_fails_the_run(home: Path) -> None:
    """The positive control: an over-tightened guard must not pass."""
    (home / "Documents/ajrr_docs").mkdir(parents=True)
    (home / "Documents/ajrr_docs/AJRR_MDD_2026.xlsx").write_bytes(b"PK")
    run = run_suite(home, ALL_BLOCKED.replace("WL_READABLE", "WL_BLOCKED"))
    assert "FAIL: whitelisted spec xlsx readable" in run.stdout
    assert run.returncode == 1


def test_write_probe_file_is_cleaned_up(home: Path) -> None:
    (home / ".claude_selftest_probe").write_text("")
    run_suite(home, ALL_BLOCKED)
    assert not (home / ".claude_selftest_probe").exists()


def test_unblocked_phi_prompt_fails_the_run(home: Path) -> None:
    run = run_suite(home, ALL_BLOCKED.replace("Prompt guard: blocked", "READBACK_OK"))
    assert "FAIL: prompt guard" in run.stdout
    assert run.returncode == 1


def test_missing_static_check_fails_the_run(home: Path) -> None:
    (home / ".claude/hooks/selftest-static.sh").unlink()
    run = run_suite(home, ALL_BLOCKED)
    assert "FAIL: static config selftest" in run.stdout
    assert run.returncode == 1


def test_static_check_is_told_to_skip_the_log_check(home: Path) -> None:
    """This run writes the log, so the config check must not judge it."""
    executable(
        home / ".claude/hooks/selftest-static.sh",
        '[ -n "${SELFTEST_SKIP_LOG_CHECK:-}" ] && echo "all PHI safeguards intact."',
    )
    run = run_suite(home, ALL_BLOCKED)
    assert "PASS: static config selftest" in run.stdout


def test_missing_claude_binary_fails_the_run(home: Path) -> None:
    run = run_suite(home, None)
    assert run.returncode == 1
    assert result_line(run).endswith(": FAIL (claude binary not found)")
