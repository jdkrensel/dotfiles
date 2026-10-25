"""Tests for the prompt-guard UserPromptSubmit hook (work machine, locked Max profile).

The hook rejects a prompt (exit 2) when its text looks like PHI or pasted query
output, and lets it through (exit 0) otherwise. A first line starting with
"no-phi:" bypasses every check, so the user can confirm a false positive.

Pasted images are deliberately NOT gated: the [Image #N] chip passes through.
"""

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "assets/machines/work/claude/hooks/prompt-guard.sh"

TABLE = "\n".join("a | b | c | d | e" for _ in range(10))


def run_guard(prompt: str) -> int:
    """Invoke the hook with a prompt; return its exit status."""
    result = subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps({"prompt": prompt}),
        capture_output=True,
        text=True,
    )
    return result.returncode


def test_plain_prompt_passes() -> None:
    assert run_guard("why did the hook fail?") == 0


def test_pasted_image_passes() -> None:
    assert run_guard("what is wrong here? [Image #1]") == 0


@pytest.mark.parametrize(
    "prompt",
    [
        "patient 123-45-6789",
        "MRN: 1234567",
        "+----+\n| id |\n+----+",
        "3 rows in set (0.01 sec)",
        TABLE,
    ],
    ids=["ssn", "mrn", "mysql-border", "rows-in-set", "bulk-table"],
)
def test_phi_shaped_prompt_is_rejected(prompt: str) -> None:
    assert run_guard(prompt) == 2


@pytest.mark.parametrize("prefix", ["no-phi:", "  NO-PHI:"], ids=["plain", "indented-upper"])
def test_no_phi_prefix_bypasses_checks(prefix: str) -> None:
    assert run_guard(f"{prefix} cohort counts\n{TABLE}") == 0


def test_no_phi_prefix_counts_only_on_first_line() -> None:
    assert run_guard(f"summary\nno-phi: x\n{TABLE}") == 2
