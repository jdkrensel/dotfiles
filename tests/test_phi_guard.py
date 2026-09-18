"""Tests for the phi-guard PreToolUse hook (work machine, locked Max profile).

The hook has THREE outcomes, and the tool decides which apply to a given path:
exit 2 is a hard deny nobody can override, a permissionDecision of "ask" on
stdout prompts the user, and a silent exit 0 lets the call through. Read is the
only promptable tool — Bash/Grep/Glob can sweep a directory through a single
approval, so they keep the hard deny. Asserting the ask/deny split per tool is
the point of the paired tests below: a regression that makes Bash promptable
would let one approval cover an unbounded set of files.

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
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "src/assets/claude/machines/work/hooks/phi-guard.sh"
HOME = str(Path.home())
REPO = f"{HOME}/repos/sqs_importer_aaos"

ALLOW, ASK, DENY = "allow", "ask", "deny"


def run_guard(payload: dict, env: dict | None = None) -> str:
    """Invoke the hook with a JSON payload; return its verdict.

    Distinguishes the ask path from the allow path, which both exit 0 — the
    difference is whether a permissionDecision was written to stdout. Reading
    the exit status alone would score a prompt as a silent pass and every
    ask-vs-allow assertion below would be vacuously true.
    """
    result = subprocess.run(
        ["bash", str(HOOK)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env={**os.environ, **env} if env else None,
    )
    if result.returncode == 2:
        return DENY
    if result.stdout.strip():
        return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]
    return ALLOW


def read(path: str, cwd: str = "/tmp") -> dict:
    return {"tool_name": "Read", "cwd": cwd, "tool_input": {"file_path": path}}


def bash(command: str, cwd: str = "/tmp") -> dict:
    return {"tool_name": "Bash", "cwd": cwd, "tool_input": {"command": command}}


def grep(path: str, cwd: str = "/tmp") -> dict:
    return {"tool_name": "Grep", "cwd": cwd, "tool_input": {"path": path}}


def glob(path: str, cwd: str = "/tmp") -> dict:
    return {"tool_name": "Glob", "cwd": cwd, "tool_input": {"path": path}}


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
    # Hand-redacted outputs the user has staged for work in this profile.
    f"{HOME}/redacted/vmc_ajrr/ajrr export 2026.csv",
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
    f"{HOME}/redacted/vmc_ajrr/export.csv",
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


# --- data-export files outside the whitelist need explicit approval --------------

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
    # ~/redacted is anchored at $HOME and matched as a whole segment: a
    # lookalike sibling or a nested dir of the same name gets no pass.
    f"{HOME}/redacted_raw/export.csv",
    f"{HOME}/Downloads/redacted/export.csv",
    f"/tmp/redacted/export.csv",
]


@pytest.mark.parametrize("path", BLOCKED_EXPORTS)
def test_non_whitelisted_exports_prompt_on_read(path):
    """Read is promptable: the user sees this exact path and decides."""
    assert run_guard(read(path)) == ASK


@pytest.mark.parametrize("path", BLOCKED_EXPORTS)
def test_non_whitelisted_exports_denied_via_bash(path):
    assert run_guard(bash(f'cat "{path}"')) == DENY


@pytest.mark.parametrize("path", BLOCKED_EXPORTS)
def test_non_whitelisted_exports_denied_via_grep_and_glob(path):
    """Only Read prompts. Grep and Glob take a directory and fan out across it,
    so one approval would cover an unbounded set of files rather than the single
    named one the user was shown."""
    assert run_guard(grep(path)) == DENY
    assert run_guard(glob(path)) == DENY


def test_bash_ref_loops_never_use_a_heredoc():
    """The Bash ref loops must be fed by process substitution, not a heredoc.

    Regression test for a real fail-open: the ref loop was fed by a heredoc,
    which bash implements by writing a temp file. Where that write failed the
    redirect failed, the loop body never ran, and the hook fell through to
    exit 0 — silently ALLOWING every .xlsx/.csv/.parquet the check exists to
    block. It cannot be reproduced by poisoning TMPDIR — /bin/bash falls back
    to /tmp — so the guard is static: no heredoc or herestring in the hook.
    """
    source = HOOK.read_text()
    assert "<<" not in source
    assert source.count("done < <(") == 2


@pytest.mark.parametrize(
    "directory, verdict",
    [
        (f"{HOME}/redacted", ALLOW),
        (f"{HOME}/redacted/vmc_ajrr", ALLOW),
        (f"{HOME}/Downloads/redacted", DENY),
        (f"{HOME}/Documents/redacted", DENY),
    ],
)
def test_grep_and_glob_judge_the_redacted_dir_as_a_whole_segment(directory, verdict):
    """Grep and Glob take directories, so the whitelist must hold for the dir
    itself, not only for files under it — and a lookalike must not pass."""
    assert run_guard(grep(directory)) == verdict
    assert run_guard(glob(directory)) == verdict


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
    f"{HOME}/redacted/../Downloads/export.csv",
]


@pytest.mark.parametrize("path", TRAVERSALS)
def test_parent_traversal_out_of_a_whitelisted_dir_is_not_silently_allowed(path):
    """A traversal must never inherit the whitelist's silent pass.

    Falling back to the normal rules is the whole protection: Read lands on a
    prompt (same as any other unwhitelisted export) and Bash stays denied. The
    failure this guards against is ALLOW — a spec-dir prefix plus enough `../`
    reading anything on disk with no prompt at all.
    """
    assert run_guard(read(path)) == ASK
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


def test_personal_areas_prompt_on_read_and_deny_elsewhere():
    for area in ("Downloads", "Desktop", "Documents"):
        assert run_guard(read(f"{HOME}/{area}/x.txt")) == ASK
        assert run_guard(bash(f"cat {HOME}/{area}/x.txt")) == DENY
        assert run_guard(grep(f"{HOME}/{area}")) == DENY


def test_credentials_are_never_promptable_even_as_a_data_export():
    """The credential/Bedrock check must run BEFORE the promptable-export check.

    Ordered the other way, a `.csv` under ~/.claude-bedrock matches the export
    rule first and the user is offered a prompt to read another profile's
    credentials — the one case where approval must not be on the table.
    """
    assert run_guard(read(f"{HOME}/.claude-bedrock/leaked.csv")) == DENY
    assert run_guard(read(f"{HOME}/.config/loki/token.csv")) == DENY


def test_credential_paths_are_denied_when_only_the_cwd_names_them():
    """A bare filename carries no ".claude-bedrock" of its own; the check must
    run on the cwd-joined path or a session started inside the profile dir
    reads its settings with no prompt at all."""
    assert run_guard(read("settings.json", cwd=f"{HOME}/.claude-bedrock")) == DENY
    assert run_guard(read("token", cwd=f"{HOME}/.config/loki")) == DENY


def test_ordinary_source_file_and_command_pass():
    assert run_guard(read(f"{REPO}/aaos/cli/_kit.py")) == ALLOW
    assert run_guard(bash("git status", cwd=REPO)) == ALLOW
