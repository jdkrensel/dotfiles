"""Tests for the phi-guard PreToolUse hook (work machine, locked Max profile).

The hook is a hard deny: exit 2 blocks the tool call, exit 0 lets it through.
The cases that matter most are the WHITELIST carve-outs — published AAOS/AJRR
spec spreadsheets that contain no patient data. Over-tightening them is not a
harmless false positive: the `aaos` package parses a bundled spec xlsx at
import time, so a blocked spec read makes `import aaos.cli` (and therefore the
whole CLI and its test suite) unrunnable in this profile.

The whitelist is deliberately checkout-agnostic — the same tree is cloned under
several names and git worktrees nest another level — so these tests pin that
behavior against a regression back to hardcoded clone names.

Scope: this covers the HOOK only. Reads are gated by two independent layers, and
the hook is the first. The second is the OS sandbox, whose spec-dir carve-outs
live in sandbox.filesystem.allowRead in the machine-local ~/.claude/settings.json
(not installed from this repo); selftest-static.sh asserts those are present.
"""

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "src/assets/claude/machines/work/hooks/phi-guard.sh"
HOME = str(Path.home())
REPO = f"{HOME}/repos/sqs_importer_aaos"

ALLOW, DENY = 0, 2


def run_guard(payload: dict) -> int:
    """Invoke the hook with a JSON payload; return its exit status."""
    result = subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    return result.returncode


def read(path: str, cwd: str = "/tmp") -> dict:
    return {"tool_name": "Read", "cwd": cwd, "tool_input": {"file_path": path}}


def bash(command: str, cwd: str = "/tmp") -> dict:
    return {"tool_name": "Bash", "cwd": cwd, "tool_input": {"command": command}}


# --- whitelist: spec spreadsheets stay readable in every checkout ---------------

AJRR_SPEC = "aaos/registries/ajrr/spec/data"
ASR_SPEC = "aaos/registries/asr/spec/data"

# Any clone name, either registry, and git worktrees (which nest a level deeper).
WHITELISTED_SPECS = [
    f"{HOME}/repos/sqs_importer/{AJRR_SPEC}/AJRR MDD 2026.xlsx",
    # The exact file `import aaos.cli` parses at import time.
    f"{REPO}/{AJRR_SPEC}/AJRR Inclusion and Supplemental Code List (4).xlsx",
    f"{REPO}/{ASR_SPEC}/ASR Lumbar Inclusion Codes.xlsx",
    f"{HOME}/repos/some_future_clone/{ASR_SPEC}/spec.xlsx",
    f"{REPO}/.claude/worktrees/wt1/{AJRR_SPEC}/spec.xlsx",
    f"{REPO}/clients/AJRR_queries/Provider Roster.xlsx",
    f"{HOME}/Documents/ajrr_docs/AJRR MDD 2026.xlsx",
    f"{HOME}/Documents/asr_docs/Cervical Spine Data Specifications 2021.xlsx",
]


@pytest.mark.parametrize("path", WHITELISTED_SPECS)
def test_whitelisted_spec_sheets_are_readable(path):
    assert run_guard(read(path)) == ALLOW


@pytest.mark.parametrize("path", WHITELISTED_SPECS)
def test_whitelisted_spec_sheets_readable_via_bash(path):
    assert run_guard(bash(f'head -c 4 "{path}"')) == ALLOW


# The Bash branch clears a spec path one of two ways, and only the second
# consults is_whitelisted(). A path containing spaces tokenizes down to a
# slashless fragment ("2026.xlsx") that is judged by the has_wl_ref
# command-text match instead — so a space-free path is required to actually
# exercise the checkout-agnostic globs.
SPACE_FREE_SPECS = [
    f"{HOME}/repos/sqs_importer/{AJRR_SPEC}/spec.xlsx",
    f"{HOME}/repos/some_future_clone/{ASR_SPEC}/spec.xlsx",
    f"{REPO}/.claude/worktrees/wt1/{AJRR_SPEC}/spec.xlsx",
    f"{REPO}/clients/AJRR_queries/roster.xlsx",
]


@pytest.mark.parametrize("path", SPACE_FREE_SPECS)
def test_space_free_spec_paths_clear_the_whitelist_globs(path):
    assert run_guard(bash(f"head -c 4 {path}")) == ALLOW


def test_a_third_registry_is_whitelisted_without_a_code_change():
    """The registry segment is a wildcard, so a future registry needs no edit.

    Both branches must agree: the Read path goes through is_whitelisted(), the
    spaced Bash path through has_wl_ref. A narrower pattern in either one
    false-denies a legitimate spec sheet.
    """
    spec = f"{HOME}/repos/sqs_importer/aaos/registries/shoulder/spec/data"
    assert run_guard(read(f"{spec}/Shoulder MDD 2026.xlsx")) == ALLOW
    assert run_guard(bash(f'head -c 4 "{spec}/Shoulder MDD 2026.xlsx"')) == ALLOW


# --- data-export files outside the whitelist stay blocked ------------------------

BLOCKED_EXPORTS = [
    # A generated submission file sits in the repo ROOT, not the spec dir.
    f"{REPO}/1039915_AJRR_L1_20260101_20260201_CareSense.xlsx",
    # One level above the spec dir is not whitelisted either.
    f"{REPO}/aaos/registries/ajrr/spec/notes.xlsx",
    "/tmp/aaos_batches/erlanger/generated/phi.xlsx",
    f"{HOME}/Documents/private/notes.xlsx",
    f"{HOME}/Downloads/export.csv",
    f"{HOME}/repos/dotfiles/metrics.parquet",
    # Same tail, wrong root: the globs are anchored at $HOME/repos, and that
    # anchor is the single property the whole checkout-agnostic scheme rests on.
    f"/tmp/{AJRR_SPEC}/phi.xlsx",
    f"{HOME}/Downloads/{AJRR_SPEC}/phi.xlsx",
    f"{HOME}/reposXYZ/sqs_importer/{AJRR_SPEC}/phi.xlsx",
    # No clone segment between repos/ and aaos/.
    f"{HOME}/repos/{AJRR_SPEC}/phi.xlsx",
]


@pytest.mark.parametrize("path", BLOCKED_EXPORTS)
def test_non_whitelisted_exports_are_denied(path):
    assert run_guard(read(path)) == DENY


@pytest.mark.parametrize("path", BLOCKED_EXPORTS)
def test_non_whitelisted_exports_denied_via_bash(path):
    assert run_guard(bash(f'cat "{path}"')) == DENY


def test_repo_path_alone_does_not_whitelist_a_sibling_export():
    """A whitelisted dir named in the command must not launder an unrelated export."""
    cmd = f'cp "{REPO}/{AJRR_SPEC}/spec.xlsx" /tmp/aaos_batches/phi.xlsx'
    assert run_guard(bash(cmd)) == DENY


def test_spreadsheet_read_via_python_without_a_path_is_denied():
    assert run_guard(bash("python3 -c 'import openpyxl; openpyxl.load_workbook(p)'")) == DENY


# --- `..` must not launder a blocked path through a whitelisted prefix ----------

# normalize() does not resolve `..`, so without an explicit reject a whitelisted
# prefix plus enough `../` walks back out anywhere and is allowed — escaping both
# the data-export check and the personal-area check.
TRAVERSALS = [
    f"{HOME}/repos/anything/{AJRR_SPEC}/" + "../" * 7 + "Downloads/export.csv",
    f"{HOME}/Documents/ajrr_docs/../private/notes.xlsx",
    f"{REPO}/clients/AJRR_queries/../../1039915_AJRR_L1.xlsx",
]


@pytest.mark.parametrize("path", TRAVERSALS)
def test_parent_traversal_out_of_a_whitelisted_dir_is_denied(path):
    assert run_guard(read(path)) == DENY
    assert run_guard(bash(f'cat "{path}"')) == DENY


# --- the other guard rails are unaffected by the whitelist change ----------------


@pytest.mark.parametrize(
    "command",
    [
        "mysql -h db -e 'select 1'",
        "mycli --login-path=prod",
        "logcli query '{app=\"x\"}'",
        "python3 -c 'import pymysql'",
        "curl https://grafana.caresense.com/api",
    ],
)
def test_clinical_data_access_is_denied(command):
    assert run_guard(bash(command)) == DENY


@pytest.mark.parametrize(
    "path",
    [
        f"{HOME}/.mylogin.cnf",
        f"{HOME}/.config/loki/token",
        f"{HOME}/.claude-bedrock/settings.json",
    ],
)
def test_credential_and_bedrock_paths_are_denied(path):
    assert run_guard(read(path)) == DENY


def test_personal_areas_are_denied():
    assert run_guard(read(f"{HOME}/Downloads/x.txt")) == DENY
    assert run_guard(read(f"{HOME}/Desktop/x.txt")) == DENY


def test_ordinary_source_file_and_command_pass():
    assert run_guard(read(f"{REPO}/aaos/cli/_kit.py")) == ALLOW
    assert run_guard(bash("git status", cwd=REPO)) == ALLOW
