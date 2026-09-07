"""Tests for the bin/claude-session wrapper.

These never run Claude. A stub ``claude`` is placed first on PATH and records the
arguments it was handed, because the argument list is where the behaviour lives:
whether the wrapper starts a new conversation or resumes one, and which one. That
choice is the whole point — Zellij snapshots a pane's argv, so anything the
wrapper cannot express there is lost when the machine restarts."""

import subprocess
import uuid
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = REPO_ROOT / "bin" / "claude-session"

TOKEN = "9f3c1d2e-4a5b-4c6d-8e7f-0a1b2c3d4e5f"
SWITCHED_TO = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"

STUB_CLAUDE = """#!/bin/sh
printf '%s\\n' "$@" > "$ARGV_LOG"
printf '%s\\n' "${CLAUDE_PANE_TOKEN:-}" > "$TOKEN_LOG"
ps -o args= -p $PPID > "$PARENT_LOG"
exit "${STUB_EXIT:-0}"
"""

METADATA_LINE = '{"type":"bridge-session","sessionId":"%s"}'
USER_LINE = '{"type":"user","sessionId":"%s"}'


@pytest.fixture
def stub(tmp_path):
    """A ``claude`` on PATH that records how the wrapper invoked it."""
    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir()
    executable = stub_dir / "claude"
    executable.write_text(STUB_CLAUDE)
    executable.chmod(0o755)

    return {
        "dir": stub_dir,
        "argv_log": tmp_path / "argv.txt",
        "token_log": tmp_path / "token.txt",
        "parent_log": tmp_path / "parent.txt",
    }


@pytest.fixture
def launch(tmp_path, stub):
    """Run the wrapper and return the arguments Claude was invoked with."""

    def _launch(
        *args: str,
        config_dir: Path | None = None,
        claude_fails: bool = False,
    ) -> list[str]:
        env = {
            "PATH": f"{stub['dir']}:/usr/bin:/bin",
            "HOME": str(tmp_path / "home"),
            "ARGV_LOG": str(stub["argv_log"]),
            "TOKEN_LOG": str(stub["token_log"]),
            "PARENT_LOG": str(stub["parent_log"]),
        }
        if config_dir is not None:
            env["CLAUDE_CONFIG_DIR"] = str(config_dir)
        if claude_fails:
            env["STUB_EXIT"] = "1"

        result = subprocess.run(
            [str(WRAPPER), *args], env=env, capture_output=True, text=True
        )
        assert result.returncode == (1 if claude_fails else 0), result.stderr

        return stub["argv_log"].read_text().splitlines()

    return _launch


@pytest.fixture
def config_dir(tmp_path) -> Path:
    directory = tmp_path / "claude-config"
    (directory / "projects").mkdir(parents=True)
    return directory


def write_transcript(config_dir: Path, session_id: str, *, spoken: bool = True) -> None:
    """Write the transcript Claude leaves behind for a session.

    Claude creates the file at launch, so an untouched pane leaves one holding
    nothing but metadata. ``spoken=False`` reproduces that, and it is the case the
    wrapper has to tell apart from a conversation worth resuming."""
    project = config_dir / "projects" / "-Users-someone-repos-thing"
    project.mkdir(parents=True, exist_ok=True)

    lines = [METADATA_LINE % session_id]
    if spoken:
        lines.append(USER_LINE % session_id)

    (project / f"{session_id}.jsonl").write_text("\n".join(lines) + "\n")


def write_note(config_dir: Path, token: str, session_id: str) -> None:
    """Record what the SessionStart hook would have seen this pane switch to."""
    notes = config_dir / "pane-sessions"
    notes.mkdir(parents=True, exist_ok=True)
    (notes / token).write_text(session_id + "\n")


def test_bare_invocation_starts_a_new_session_with_a_generated_id(launch, config_dir):
    flag, session_id = launch(config_dir=config_dir)

    assert flag == "--session-id"
    assert uuid.UUID(session_id)


def test_generated_token_is_lowercase(launch, config_dir):
    _, token = launch(config_dir=config_dir)

    assert token == token.lower()


def test_unknown_token_starts_a_session_under_it(launch, config_dir):
    """No transcript means the token was never claimed, so it can be used as an id."""
    assert launch("--session", TOKEN, config_dir=config_dir) == ["--session-id", TOKEN]


def test_token_with_a_conversation_is_resumed(launch, config_dir):
    write_transcript(config_dir, TOKEN)

    assert launch("--session", TOKEN, config_dir=config_dir) == ["--resume", TOKEN]


def test_session_that_was_never_spoken_to_is_replaced_by_a_fresh_token(
    launch, config_dir
):
    """A transcript with no conversation can neither be resumed nor reused."""
    write_transcript(config_dir, TOKEN, spoken=False)

    flag, started_id = launch("--session", TOKEN, config_dir=config_dir)

    assert flag == "--session-id"
    assert started_id != TOKEN
    assert uuid.UUID(started_id)


def test_conversation_is_found_regardless_of_which_project_holds_it(launch, config_dir):
    """Ids are unique across projects, so the lookup globs instead of encoding a path."""
    other = config_dir / "projects" / "-tmp-somewhere-else"
    other.mkdir(parents=True)
    (other / f"{TOKEN}.jsonl").write_text(USER_LINE % TOKEN + "\n")

    assert launch("--session", TOKEN, config_dir=config_dir) == ["--resume", TOKEN]


def test_transcripts_default_to_home_when_no_config_dir_is_set(launch, tmp_path):
    write_transcript(tmp_path / "home" / ".claude", TOKEN)

    assert launch("--session", TOKEN) == ["--resume", TOKEN]


def test_note_resumes_the_conversation_the_pane_switched_to(launch, config_dir):
    """The hook's note is what makes an in-app /resume survive a restart."""
    write_transcript(config_dir, TOKEN)
    write_transcript(config_dir, SWITCHED_TO)
    write_note(config_dir, TOKEN, SWITCHED_TO)

    assert launch("--session", TOKEN, config_dir=config_dir) == [
        "--resume",
        SWITCHED_TO,
    ]


def test_note_for_an_empty_conversation_falls_back_to_a_fresh_token(launch, config_dir):
    """A pane whose last session holds nothing has nothing to go back to."""
    write_transcript(config_dir, TOKEN, spoken=False)
    write_transcript(config_dir, SWITCHED_TO, spoken=False)
    write_note(config_dir, TOKEN, SWITCHED_TO)

    flag, started_id = launch("--session", TOKEN, config_dir=config_dir)

    assert flag == "--session-id"
    assert started_id not in (TOKEN, SWITCHED_TO)


def test_pane_token_is_exported_for_the_hook(launch, config_dir, stub):
    launch("--session", TOKEN, config_dir=config_dir)

    assert stub["token_log"].read_text().strip() == TOKEN


def test_replacement_token_is_the_one_exported(launch, config_dir, stub):
    write_transcript(config_dir, TOKEN, spoken=False)

    _, started_id = launch("--session", TOKEN, config_dir=config_dir)

    assert stub["token_log"].read_text().strip() == started_id


def test_extra_arguments_are_passed_through(launch, config_dir):
    flag, session_id, *rest = launch("--model", "opus", config_dir=config_dir)

    assert flag == "--session-id"
    assert uuid.UUID(session_id)
    assert rest == ["--model", "opus"]


def test_extra_arguments_survive_a_resume(launch, config_dir):
    write_transcript(config_dir, TOKEN)

    assert launch("--session", TOKEN, "--model", "opus", config_dir=config_dir) == [
        "--resume",
        TOKEN,
        "--model",
        "opus",
    ]


def test_extra_arguments_survive_the_replacement_of_a_dead_token(launch, config_dir):
    write_transcript(config_dir, TOKEN, spoken=False)

    flag, started_id, *rest = launch(
        "--session", TOKEN, "--model", "opus", config_dir=config_dir
    )

    assert flag == "--session-id"
    assert started_id != TOKEN
    assert rest == ["--model", "opus"]


def test_zellij_snapshots_the_wrapper_rather_than_claude(launch, config_dir, stub):
    """The token only survives a reboot if it is the *wrapper's* argv Zellij sees.

    Claude has to stay a child for that to hold: exec'ing would put claude's own
    arguments in the pane's snapshot, and replaying those fails outright."""
    write_transcript(config_dir, TOKEN)

    launch("--session", TOKEN, config_dir=config_dir)
    parent = stub["parent_log"].read_text()

    assert "claude-session" in parent
    assert f"--session {TOKEN}" in parent


def test_refused_resume_falls_back_to_a_fresh_session(launch, config_dir):
    """Otherwise the pane replays the same refusal into a dead pane every reboot."""
    write_transcript(config_dir, TOKEN)

    flag, started_id = launch("--session", TOKEN, config_dir=config_dir, claude_fails=True)

    assert flag == "--session-id"
    assert started_id != TOKEN


def test_a_dead_token_takes_its_note_with_it(launch, config_dir):
    """Notes would otherwise pile up under tokens no pane can reach any more."""
    write_transcript(config_dir, TOKEN, spoken=False)
    write_note(config_dir, TOKEN, SWITCHED_TO)

    launch("--session", TOKEN, config_dir=config_dir)

    assert not (config_dir / "pane-sessions" / TOKEN).exists()


def test_a_token_with_no_value_is_replaced(launch, config_dir):
    """A truncated snapshot should still open a working pane."""
    flag, started_id = launch("--session", config_dir=config_dir)

    assert flag == "--session-id"
    assert uuid.UUID(started_id)
