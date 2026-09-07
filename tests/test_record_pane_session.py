"""Tests for the record_pane_session SessionStart hook.

The hook exists so that a conversation switched to with /resume survives a
restart: bin/claude-session can only put a fixed token in the pane's argv, and
this is what keeps that token pointing at the conversation the pane is actually
on. Both halves of the note it writes — the token from the environment and the
session id from the payload — name a file on disk, so the tests cover what
happens when either is not what it should be."""

import importlib.util

import pytest

TOKEN = "9f3c1d2e-4a5b-4c6d-8e7f-0a1b2c3d4e5f"
SESSION = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
LATER_SESSION = "c70d3ce4-0468-464b-a5db-5757eb3e0dd3"

HOOK = "record_pane_session.py"


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    directory = tmp_path / "claude-config"
    directory.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(directory))
    monkeypatch.setenv("CLAUDE_PANE_TOKEN", TOKEN)
    return directory


def payload(session_id: str = SESSION, source: str = "startup") -> dict:
    return {
        "session_id": session_id,
        "hook_event_name": "SessionStart",
        "source": source,
        "cwd": "/Users/someone/repos/thing",
    }


def note(config_dir, token: str = TOKEN):
    return config_dir / "pane-sessions" / token


def test_records_the_session_against_the_pane_token(run_hook, config_dir):
    run_hook(HOOK, payload())

    assert note(config_dir).read_text().strip() == SESSION


def test_a_later_session_replaces_the_earlier_one(run_hook, config_dir):
    """Switching conversations mid-pane is the case the whole hook is for."""
    run_hook(HOOK, payload())
    run_hook(HOOK, payload(LATER_SESSION, source="resume"))

    assert note(config_dir).read_text().strip() == LATER_SESSION


def test_records_a_compacted_session(run_hook, config_dir):
    run_hook(HOOK, payload(LATER_SESSION, source="compact"))

    assert note(config_dir).read_text().strip() == LATER_SESSION


def test_does_nothing_outside_a_wrapped_pane(run_hook, config_dir, monkeypatch):
    monkeypatch.delenv("CLAUDE_PANE_TOKEN")

    result = run_hook(HOOK, payload())

    assert result.returncode == 0
    assert not (config_dir / "pane-sessions").exists()


def test_rejects_a_token_that_is_not_a_session_id(run_hook, config_dir, monkeypatch):
    """The token names a file, so a path masquerading as one is not written."""
    monkeypatch.setenv("CLAUDE_PANE_TOKEN", "../../escaped")

    result = run_hook(HOOK, payload())

    assert result.returncode == 0
    assert not (config_dir / "pane-sessions").exists()


def test_rejects_a_session_id_that_is_not_a_session_id(run_hook, config_dir):
    result = run_hook(HOOK, payload("/etc/passwd"))

    assert result.returncode == 0
    assert not (config_dir / "pane-sessions").exists()


@pytest.mark.parametrize("raw", ["not json", "null", "[1, 2]", ""])
def test_survives_a_payload_it_cannot_use(run_hook_raw, config_dir, raw):
    result = run_hook_raw(HOOK, raw)

    assert result.returncode == 0
    assert not (config_dir / "pane-sessions").exists()


def test_ignores_a_session_id_that_is_not_a_string(run_hook, config_dir):
    result = run_hook(HOOK, {"session_id": 123, "hook_event_name": "SessionStart"})

    assert result.returncode == 0
    assert not (config_dir / "pane-sessions").exists()


def test_defaults_to_the_home_config_directory(run_hook, tmp_path, monkeypatch):
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("CLAUDE_PANE_TOKEN", TOKEN)
    monkeypatch.setenv("HOME", str(tmp_path))

    run_hook(HOOK, payload())

    assert (tmp_path / ".claude" / "pane-sessions" / TOKEN).read_text().strip() == SESSION


def load_hook(hooks_dir):
    """Import the hook so its ancestry logic can be exercised without real processes."""
    spec = importlib.util.spec_from_file_location("record_pane_session", hooks_dir / HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# pid -> (parent pid, command), shaped like the chain a hook really sees:
# the hook, the shell Claude runs it through, Claude itself, then the wrapper.
PANE_PROCESSES = {
    900: (800, "python3"),
    800: (700, "sh"),
    700: (600, "claude"),
    600: (1, "sh"),
}

# The same, with a nested `claude` from a tool call between the hook and the pane's.
NESTED_PROCESSES = {
    **PANE_PROCESSES,
    700: (650, "claude"),
    650: (500, "zsh"),
    500: (600, "claude"),
}


def test_finds_the_claude_the_hook_is_running_under(hooks_dir):
    hook = load_hook(hooks_dir)

    assert hook.owning_claude(PANE_PROCESSES, 900) == 700


def test_ancestry_that_cannot_be_read_finds_nothing(hooks_dir):
    hook = load_hook(hooks_dir)

    assert hook.owning_claude({}, 900) is None


def test_records_a_session_the_wrapper_itself_started(hooks_dir, monkeypatch):
    hook = load_hook(hooks_dir)
    monkeypatch.setattr(hook, "process_table", lambda: PANE_PROCESSES)
    monkeypatch.setattr(hook.os, "getppid", lambda: 900)

    assert hook.belongs_to_the_pane("600") is True


def test_ignores_a_claude_nested_inside_the_pane(hooks_dir, monkeypatch):
    """A `claude` run from a tool call must not repoint the pane at its own session."""
    hook = load_hook(hooks_dir)
    monkeypatch.setattr(hook, "process_table", lambda: NESTED_PROCESSES)
    monkeypatch.setattr(hook.os, "getppid", lambda: 900)

    assert hook.belongs_to_the_pane("600") is False


def test_unreadable_ancestry_is_treated_as_the_pane_itself(hooks_dir, monkeypatch):
    """Failing open costs a stray note; failing closed would drop the feature."""
    hook = load_hook(hooks_dir)
    monkeypatch.setattr(hook, "process_table", lambda: {})
    monkeypatch.setattr(hook.os, "getppid", lambda: 900)

    assert hook.belongs_to_the_pane("600") is True
