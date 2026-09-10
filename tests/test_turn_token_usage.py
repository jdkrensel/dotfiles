"""Tests for the turn_token_usage Stop hook.

The hook reports one turn's cost and timing, so the tests centre on the things
that decide those numbers: an API response is split across several transcript
lines sharing a requestId, the transcript holds the whole session rather than one
turn, cache writes are priced by TTL, and tool duration exists only as the gap
between two timestamps. Getting any of them wrong misreports spend silently. Every
malformed input has a test too, since a hook that runs after every response must
never break the session."""

import json

import pytest

HOOK = "turn_token_usage.py"

MODEL = "claude-opus-5"  # $5/$25 per MTok, the rates the cost assertions assume


def stamp(second: int) -> str:
    """An offset in seconds from a fixed start, as the ISO-8601 stamp on a line."""
    return f"2026-09-09T16:{second // 60:02d}:{second % 60:02d}.000Z"


def usage(output=100, thinking=0, write_5m=0, write_1h=0, cache_read=0, uncached=0) -> dict:
    return {
        "input_tokens": uncached,
        "cache_creation_input_tokens": write_5m + write_1h,
        "cache_creation": {
            "ephemeral_5m_input_tokens": write_5m,
            "ephemeral_1h_input_tokens": write_1h,
        },
        "cache_read_input_tokens": cache_read,
        "output_tokens": output,
        "output_tokens_details": {"thinking_tokens": thinking},
    }


def assistant(request_id: str, second: int = 0, model: str = MODEL, **kwargs) -> dict:
    return {
        "type": "assistant",
        "requestId": request_id,
        "timestamp": stamp(second),
        "message": {"role": "assistant", "model": model, "usage": usage(**kwargs)},
    }


def user_message(text: str = "do the thing", second: int = 0) -> dict:
    return {"type": "user", "timestamp": stamp(second), "message": {"role": "user", "content": text}}


def tool_call(request_id: str, second: int, name: str = "Bash", tool_id: str = "toolu_1") -> dict:
    entry = assistant(request_id, second)
    entry["message"]["content"] = [{"type": "tool_use", "id": tool_id, "name": name, "input": {}}]
    return entry


def meta_message(text: str = "Base directory for this skill: /tmp/skill", second: int = 0) -> dict:
    """A harness injection: prose content, but flagged isMeta and arriving mid-turn."""
    return {
        "type": "user",
        "isMeta": True,
        "timestamp": stamp(second),
        "message": {"role": "user", "content": [{"type": "text", "text": text}]},
    }


def tool_result(second: int, tool_id: str = "toolu_1") -> dict:
    return {
        "type": "user",
        "timestamp": stamp(second),
        "message": {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": tool_id, "content": "ok"}],
        },
    }


@pytest.fixture
def transcript(tmp_path):
    """Write JSONL lines to a transcript and return the Stop payload for it."""

    def _write(entries: list[dict]) -> dict:
        path = tmp_path / "session.jsonl"
        path.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
        return {
            "session_id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
            "transcript_path": str(path),
            "hook_event_name": "Stop",
            "stop_hook_active": False,
        }

    return _write


def message(result) -> str:
    assert result.returncode == 0
    return json.loads(result.stdout)["systemMessage"]


# --- tokens ------------------------------------------------------------------


def test_reports_the_usage_of_a_single_response(run_hook, transcript):
    payload = transcript([
        user_message(),
        assistant("req_1", output=1200, thinking=300, write_5m=20568, cache_read=26906),
    ])

    line = message(run_hook(HOOK, payload)).splitlines()[1]

    assert "47.5k in, 57% cached (20.6k written)" in line
    assert "1,200 out (300 thinking)" in line
    assert "1 request" in line


def test_counts_a_split_response_once(run_hook, transcript):
    """Thinking, text and tool_use arrive as separate lines under one requestId;
    summing per line would double every number."""
    payload = transcript([
        user_message(),
        assistant("req_1", output=500, write_5m=1000, cache_read=2000),
        assistant("req_1", output=500, write_5m=1000, cache_read=2000),
    ])

    line = message(run_hook(HOOK, payload))

    assert "3,000 in" in line
    assert "500 out" in line
    assert "1 request" in line


def test_sums_every_request_in_the_turn(run_hook, transcript):
    payload = transcript([
        user_message(),
        assistant("req_1", output=100, write_5m=10, cache_read=20),
        tool_result(second=1),
        assistant("req_2", output=200, write_5m=30, cache_read=40),
    ])

    line = message(run_hook(HOOK, payload))

    assert "100 in" in line  # 40 written + 60 read
    assert "300 out" in line
    assert "2 requests" in line


def test_excludes_earlier_turns(run_hook, transcript):
    """The turn boundary is the point of the whole thing: a long session must not
    report its cumulative total."""
    payload = transcript([
        user_message("first"),
        assistant("req_old", output=9999, write_5m=9999, cache_read=9999),
        user_message("second"),
        assistant("req_new", output=100, write_5m=10, cache_read=20),
    ])

    line = message(run_hook(HOOK, payload))

    assert "100 out" in line
    assert "1 request" in line
    assert "9,999" not in line


def test_a_tool_result_does_not_start_a_new_turn(run_hook, transcript):
    """Tool results are `user` lines too, but the work they trigger is this turn's."""
    payload = transcript([
        user_message(),
        assistant("req_1", output=100),
        tool_result(second=1),
        assistant("req_2", output=100),
    ])

    assert "2 requests" in message(run_hook(HOOK, payload))


def test_omits_thinking_when_there_was_none(run_hook, transcript):
    payload = transcript([user_message(), assistant("req_1", output=100, thinking=0)])

    assert "thinking" not in message(run_hook(HOOK, payload))


def test_abbreviates_a_million_cache_reads(run_hook, transcript):
    """A long turn reads millions of cached tokens; 1626.0k does not read as a number."""
    payload = transcript([user_message(), assistant("req_1", cache_read=1_626_000)])

    assert "1.6M in" in message(run_hook(HOOK, payload))


# --- cost --------------------------------------------------------------------


def test_prices_output_at_the_model_rate(run_hook, transcript):
    """1M output tokens on Opus 5 is $25."""
    payload = transcript([user_message(), assistant("req_1", output=1_000_000)])

    assert "$25.00" in message(run_hook(HOOK, payload))


def test_prices_a_cache_read_at_a_tenth_of_the_input_rate(run_hook, transcript):
    """1M read tokens is 0.1 x $5 = $0.50, against $5 had they been uncached."""
    payload = transcript([user_message(), assistant("req_1", output=0, cache_read=1_000_000)])

    assert "$0.50" in message(run_hook(HOOK, payload))


def test_prices_the_two_cache_write_ttls_differently(run_hook, transcript):
    """An hour-long write is 2x the base rate against 1.25x for five minutes —
    the difference the hook exists to make visible."""
    short = transcript([user_message(), assistant("req_1", output=0, write_5m=1_000_000)])
    assert "$6.25" in message(run_hook(HOOK, short))

    long = transcript([user_message(), assistant("req_1", output=0, write_1h=1_000_000)])
    assert "$10.00" in message(run_hook(HOOK, long))


def test_prices_uncached_input_at_the_full_rate(run_hook, transcript):
    payload = transcript([user_message(), assistant("req_1", output=0, uncached=1_000_000)])

    assert "$5.00" in message(run_hook(HOOK, payload))


def test_prices_each_model_at_its_own_rate(run_hook, transcript):
    """A turn that switched models must not be priced at one model's rates."""
    payload = transcript([
        user_message(),
        assistant("req_1", output=1_000_000, model="claude-opus-5"),
        assistant("req_2", output=1_000_000, model="claude-haiku-4-5"),
    ])

    assert "$30.00" in message(run_hook(HOOK, payload))  # 25 + 5


def test_reports_a_tiny_cost_without_rounding_it_to_zero(run_hook, transcript):
    payload = transcript([user_message(), assistant("req_1", output=10)])

    assert "<$0.01" in message(run_hook(HOOK, payload))


def test_omits_the_cost_for_an_unknown_model(run_hook, transcript):
    """A model released after this rate table would otherwise be priced wrongly,
    which is worse than not pricing it at all."""
    payload = transcript([user_message(), assistant("req_1", output=100, model="claude-next-9")])

    line = message(run_hook(HOOK, payload))

    assert "$" not in line
    assert "100 out" in line


# --- timing ------------------------------------------------------------------


def test_reports_the_wall_time_of_the_turn(run_hook, transcript):
    """Named, so the duration is not read as another token count: it is wall clock
    from the user's message to the end of the response."""
    payload = transcript([user_message(second=10), assistant("req_1", second=52)])

    assert "elapsed 42.0s" in message(run_hook(HOOK, payload))


def test_splits_wall_time_between_tools_and_the_model(run_hook, transcript):
    payload = transcript([
        user_message(second=0),
        tool_call("req_1", second=10),
        tool_result(second=25),
        assistant("req_2", second=40),
    ])

    line = message(run_hook(HOOK, payload)).splitlines()[2]

    assert "40.0s" in line
    assert "tools 15.0s, model 25.0s" in line


def test_names_the_slowest_tool_call(run_hook, transcript):
    payload = transcript([
        user_message(second=0),
        tool_call("req_1", second=1, name="Read", tool_id="toolu_a"),
        tool_result(second=2, tool_id="toolu_a"),
        tool_call("req_2", second=3, name="Bash", tool_id="toolu_b"),
        tool_result(second=33, tool_id="toolu_b"),
    ])

    line = message(run_hook(HOOK, payload)).splitlines()[2]

    assert "slowest Bash 30.0s of 2" in line


def test_formats_a_long_turn_in_minutes(run_hook, transcript):
    payload = transcript([user_message(second=0), assistant("req_1", second=125)])

    assert "2m05s" in message(run_hook(HOOK, payload))


def test_reports_tokens_even_when_timestamps_are_absent(run_hook, transcript):
    """An older transcript without timestamps still has usage worth reporting."""
    payload = transcript([
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {
            "type": "assistant",
            "requestId": "req_1",
            "message": {"model": MODEL, "usage": {"output_tokens": 42}},
        },
    ])

    reported = message(run_hook(HOOK, payload))

    assert "42 out" in reported
    assert len(reported.splitlines()) == 2  # the blank lead-in, then cost; no timing line


# --- refusing to break the session -------------------------------------------


def test_silent_when_the_turn_has_no_assistant_lines(run_hook, transcript):
    result = run_hook(HOOK, transcript([user_message()]))

    assert result.returncode == 0
    assert result.stdout == ""


def test_silent_when_no_user_message_is_found(run_hook, transcript):
    """A transcript that starts mid-turn (e.g. after a compaction) has no boundary."""
    result = run_hook(HOOK, transcript([assistant("req_1", output=100)]))

    assert result.returncode == 0
    assert result.stdout == ""


def test_silent_when_the_transcript_is_missing(run_hook, tmp_path):
    payload = {"transcript_path": str(tmp_path / "gone.jsonl"), "hook_event_name": "Stop"}

    result = run_hook(HOOK, payload)

    assert result.returncode == 0
    assert result.stdout == ""


def test_skips_malformed_lines_and_reports_the_rest(run_hook, tmp_path):
    path = tmp_path / "session.jsonl"
    path.write_text(
        json.dumps(user_message()) + "\n"
        + "{not json at all\n"
        + "\n"
        + json.dumps(assistant("req_1", output=100)) + "\n"
    )

    line = message(run_hook(HOOK, {"transcript_path": str(path), "hook_event_name": "Stop"}))

    assert "100 out" in line


def test_silent_on_a_payload_that_is_not_a_stop_payload(run_hook, run_hook_raw):
    for result in (run_hook(HOOK, {}), run_hook_raw(HOOK, "not json"), run_hook_raw(HOOK, "[]")):
        assert result.returncode == 0
        assert result.stdout == ""


def test_tolerates_usage_fields_being_absent(run_hook, transcript):
    """Older transcript lines predate output_tokens_details and cache_creation; a
    KeyError here would surface as a hook failure after a fine response."""
    payload = transcript([
        user_message(),
        {
            "type": "assistant",
            "requestId": "req_1",
            "timestamp": stamp(1),
            "message": {"model": MODEL, "usage": {"output_tokens": 42}},
        },
    ])

    assert "42 out" in message(run_hook(HOOK, payload))


def test_tolerates_a_tool_call_with_no_result(run_hook, transcript):
    """An interrupted turn ends with a tool_use and no matching tool_result."""
    payload = transcript([
        user_message(second=0),
        tool_call("req_1", second=5),
    ])

    line = message(run_hook(HOOK, payload))

    assert "1 request" in line
    assert "slowest" not in line


def test_starts_on_its_own_line(run_hook, transcript):
    """The harness prefixes the message with "Stop says:", so a leading newline is
    what keeps both reported lines starting at the same column."""
    payload = transcript([user_message(second=0), assistant("req_1", second=5)])

    reported = message(run_hook(HOOK, payload))

    assert reported.startswith("\n")
    assert reported.splitlines()[0] == ""


def test_a_meta_line_does_not_start_a_new_turn(run_hook, transcript):
    """Skill preambles and slash-command context blocks are `user` lines carrying
    prose, injected mid-turn. Treating one as the turn start drops every request
    before it — a silent under-report of exactly what the hook is for."""
    payload = transcript([
        user_message(second=0),
        assistant("req_1", second=1, output=100),
        meta_message(second=2),
        assistant("req_2", second=3, output=100),
    ])

    line = message(run_hook(HOOK, payload))

    assert "200 out" in line
    assert "2 requests" in line


def test_an_empty_user_line_does_not_start_a_new_turn(run_hook, transcript):
    payload = transcript([
        user_message(second=0),
        assistant("req_1", second=1, output=100),
        {"type": "user", "timestamp": stamp(2), "message": {"role": "user", "content": []}},
        assistant("req_2", second=3, output=100),
    ])

    assert "2 requests" in message(run_hook(HOOK, payload))


def test_counts_overlapping_tool_calls_once(run_hook, transcript):
    """Tools issued in one batch run concurrently. Summing their durations would
    exceed the turn's own wall time and report the model's share as zero."""
    payload = transcript([
        user_message(second=0),
        tool_call("req_1", second=10, name="Bash", tool_id="toolu_a"),
        tool_call("req_1", second=10, name="Read", tool_id="toolu_b"),
        tool_result(second=30, tool_id="toolu_a"),
        tool_result(second=30, tool_id="toolu_b"),
        assistant("req_2", second=40),
    ])

    line = message(run_hook(HOOK, payload)).splitlines()[2]

    assert "tools 20.0s, model 20.0s" in line  # not 40s of tools and no model time


def test_prices_a_write_with_no_ttl_breakdown_at_the_short_rate(run_hook, transcript):
    """Without the nested cache_creation block the TTL is unknown; the reported
    figure and the billed one must still come from the same number."""
    payload = transcript([
        user_message(),
        {
            "type": "assistant",
            "requestId": "req_1",
            "timestamp": stamp(1),
            "message": {
                "model": MODEL,
                "usage": {"output_tokens": 0, "cache_creation_input_tokens": 1_000_000},
            },
        },
    ])

    line = message(run_hook(HOOK, payload))

    assert "$6.25" in line
    assert "1.0M written" in line


def test_survives_a_timestamp_it_cannot_subtract(run_hook, transcript):
    """A line with an offset-less timestamp must not traceback after a fine response."""
    entry = assistant("req_1", output=100)
    entry["timestamp"] = "2026-09-09T16:00:05"
    payload = transcript([user_message(second=0), entry])

    result = run_hook(HOOK, payload)

    assert result.returncode == 0
    assert result.stderr == ""


def test_survives_a_non_numeric_usage_value(run_hook, transcript):
    payload = transcript([
        user_message(),
        {
            "type": "assistant",
            "requestId": "req_1",
            "timestamp": stamp(1),
            "message": {"model": MODEL, "usage": {"output_tokens": "lots"}},
        },
    ])

    result = run_hook(HOOK, payload)

    assert result.returncode == 0
    assert result.stderr == ""
