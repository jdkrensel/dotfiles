#!/usr/bin/env python3
"""Stop hook: report what the turn that just finished cost, and where it went slow.

Two lines after every response. The first answers "was that prompt efficient?" —
list-price cost, how much of the input was served from cache, and how many API
requests it took. The second answers "what was slow?" — wall time split between
model and tools, and the single slowest tool call.

Cache hit rate is the number to watch. A read bills at a tenth of the base input
rate and a write at 1.25x (2x on the 1-hour TTL), so a turn that re-reads a warm
prefix is nearly free while one that rewrites it pays a premium; a hit rate that
drops between similar turns means something invalidated the prefix.

Usage is read from the session transcript (JSONL) rather than the payload, which
carries only session_id, transcript_path and stop_hook_active. Three properties of
that file shape the code: the same API response is split across several
`assistant` lines sharing one requestId, so totals are summed per requestId rather
than per line; the file holds the whole session, so the turn is delimited by
walking backward to the most recent real user message — a line whose content is
prose rather than a tool_result; and every line carries an ISO-8601 timestamp,
which is the only timing signal available, since no tool duration is recorded.

Any unreadable, malformed or unrecognisable transcript exits silently — a hook
that runs after every single response must never be what breaks a session.
Registered for Stop in settings.all-profiles.json.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime

# List prices per million tokens, as published for the first-party API. These
# drift: they are a relative efficiency signal, not a bill — and on a Max plan
# nothing here is charged per token at all. A model missing from the table simply
# reports no dollar figure.
BASE_RATES = {
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
    "claude-opus-4-7": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

# Multipliers on the base input rate, fixed by the caching contract rather than
# by model: a read is a tenth, a 5-minute write a quarter more, an hour-long
# write double.
CACHE_READ_RATE = 0.1
CACHE_WRITE_5M_RATE = 1.25
CACHE_WRITE_1H_RATE = 2.0


def parse_time(entry: dict) -> datetime | None:
    stamp = entry.get("timestamp")
    if not isinstance(stamp, str):
        return None

    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_user_turn_start(entry: dict) -> bool:
    """Whether this line is the prose message that opened the current turn.

    Three kinds of line wear `type: "user"` and only one of them starts a turn.
    Tool results carry blocks of type tool_result. Harness injections — a skill
    preamble, a slash-command's context block — carry plain text but are flagged
    isMeta, and they arrive *mid-turn*: mistaking one for the start silently drops
    every request before it from the totals. What is left is the real message,
    which is a string or at least one text block."""
    if entry.get("type") != "user" or entry.get("isSidechain") or entry.get("isMeta"):
        return False

    content = entry.get("message", {}).get("content")
    if isinstance(content, str):
        return bool(content)

    if isinstance(content, list):
        return any(isinstance(block, dict) and block.get("type") == "text" for block in content)

    return False


def read_turn(transcript_path: str) -> list[dict]:
    """The transcript lines belonging to the turn that just finished."""
    # errors="replace": the newest line can be half-written while the session is
    # still flushing it, and a decode error there must not cost the whole report.
    with open(transcript_path, encoding="utf-8", errors="replace") as handle:
        entries = []
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(entry, dict):
                entries.append(entry)

    for index in range(len(entries) - 1, -1, -1):
        if is_user_turn_start(entries[index]):
            return entries[index:]

    return []


def totals(entries: list[dict]) -> dict:
    """Token totals and list-price cost for the turn, each API response counted once."""
    seen: set[str] = set()
    summed = {
        "uncached": 0,
        "cache_write": 0,
        "cache_read": 0,
        "output": 0,
        "thinking": 0,
        "requests": 0,
        "cost": 0.0,
        "priced": True,
    }

    for entry in entries:
        if entry.get("type") != "assistant":
            continue

        request_id = entry.get("requestId")
        if not request_id or request_id in seen:
            continue

        message = entry.get("message") or {}
        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue

        # Only now is the request accounted for. Marking it seen any earlier would
        # let a first line that carries no usage suppress the later ones that do.
        seen.add(request_id)

        details = usage.get("output_tokens_details") or {}
        creation = usage.get("cache_creation") or {}

        uncached = int(usage.get("input_tokens") or 0)
        read = int(usage.get("cache_read_input_tokens") or 0)

        # The TTL breakdown is the authority when present, so the figure reported
        # and the figure billed are the same one. Without it, everything falls back
        # to the top-level total at the 5-minute rate.
        if creation:
            write_5m = int(creation.get("ephemeral_5m_input_tokens") or 0)
            write_1h = int(creation.get("ephemeral_1h_input_tokens") or 0)
        else:
            write_5m = int(usage.get("cache_creation_input_tokens") or 0)
            write_1h = 0
        write_total = write_5m + write_1h
        output = int(usage.get("output_tokens") or 0)

        summed["uncached"] += uncached
        summed["cache_write"] += write_total
        summed["cache_read"] += read
        summed["output"] += output
        summed["thinking"] += int(details.get("thinking_tokens") or 0)
        summed["requests"] += 1

        rates = BASE_RATES.get(message.get("model"))
        if rates is None:
            summed["priced"] = False
            continue

        input_rate, output_rate = rates
        billed_input = (
            uncached
            + write_5m * CACHE_WRITE_5M_RATE
            + write_1h * CACHE_WRITE_1H_RATE
            + read * CACHE_READ_RATE
        )
        summed["cost"] += (billed_input * input_rate + output * output_rate) / 1_000_000

    return summed


def tool_spans(entries: list[dict]) -> list[tuple[str, datetime, datetime]]:
    """Each tool call in the turn as (name, start, end), timed call to result.

    Wall time is all the transcript records, so a span includes any wait for
    permission — which is the honest number anyway, since that is time the turn
    actually took."""
    started: dict[str, tuple[str, datetime]] = {}
    spans: list[tuple[str, datetime, datetime]] = []

    for entry in entries:
        moment = parse_time(entry)
        if moment is None:
            continue

        content = (entry.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict):
                continue

            if block.get("type") == "tool_use" and block.get("id"):
                started[block["id"]] = (str(block.get("name") or "tool"), moment)

            if block.get("type") == "tool_result":
                call = started.pop(block.get("tool_use_id"), None)
                if call is not None:
                    spans.append((call[0], call[1], moment))

    return spans


def occupied_seconds(spans: list[tuple[str, datetime, datetime]]) -> float:
    """How long the turn spent inside tools, counting overlap once.

    Tools issued in one batch run concurrently, so adding their durations would
    exceed the turn's own wall time and leave the model's share reported as zero.
    Merging the intervals first is what keeps the split honest."""
    total = 0.0
    current_start: datetime | None = None
    current_end: datetime | None = None

    for _, start, end in sorted(spans, key=lambda span: span[1]):
        if current_end is None or start > current_end:
            if current_end is not None and current_start is not None:
                total += (current_end - current_start).total_seconds()
            current_start, current_end = start, end
        elif end > current_end:
            current_end = end

    if current_start is not None and current_end is not None:
        total += (current_end - current_start).total_seconds()

    return total


def compact(count: int) -> str:
    """Token counts, abbreviated once they stop being worth reading digit by digit."""
    if count < 10_000:
        return f"{count:,}"
    if count < 1_000_000:
        return f"{count / 1_000:.1f}k"
    return f"{count / 1_000_000:.1f}M"


def duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds) // 60}m{int(seconds) % 60:02d}s"


def money(dollars: float) -> str:
    return "<$0.01" if dollars < 0.005 else f"${dollars:,.2f}"


def cost_line(summed: dict) -> str:
    """Cost, cache efficiency and request count — the prompting-efficiency half."""
    billed_input = summed["uncached"] + summed["cache_write"] + summed["cache_read"]
    parts = []

    if summed["priced"]:
        parts.append(money(summed["cost"]))

    if billed_input:
        hit_rate = summed["cache_read"] / billed_input * 100
        parts.append(
            f"{compact(billed_input)} in, {hit_rate:.0f}% cached "
            f"({compact(summed['cache_write'])} written)"
        )

    output = f"{compact(summed['output'])} out"
    if summed["thinking"]:
        output += f" ({compact(summed['thinking'])} thinking)"
    parts.append(output)

    requests = summed["requests"]
    parts.append(f"{requests} request{'' if requests == 1 else 's'}")

    return " · ".join(parts)


def timing_line(entries: list[dict], spans: list[tuple[str, float]]) -> str | None:
    """Wall time split between model and tools, plus the slowest single call."""
    moments = [moment for moment in map(parse_time, entries) if moment is not None]
    if len(moments) < 2:
        return None

    wall = (max(moments) - min(moments)).total_seconds()
    # "elapsed" rather than "time": it names what the number measures — wall clock
    # from the user's message to the end of the response, tool waits included —
    # which a bare duration beside a line of token counts does not.
    parts = [f"elapsed {duration(wall)}"]

    if spans:
        in_tools = occupied_seconds(spans)
        parts.append(f"tools {duration(in_tools)}, model {duration(max(wall - in_tools, 0))}")

        name, start, end = max(spans, key=lambda span: span[2] - span[1])
        parts.append(f"slowest {name} {duration((end - start).total_seconds())} of {len(spans)}")

    return " · ".join(parts)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        sys.exit(0)

    if not isinstance(payload, dict):
        sys.exit(0)

    transcript_path = payload.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        sys.exit(0)

    # Everything past this point reads a file written by another process, so it is
    # guarded as one: a missing field, an odd timestamp or a half-written line ends
    # the hook quietly. Reporting nothing costs a line of output; a traceback after
    # every response costs the session.
    try:
        entries = read_turn(transcript_path)
        summed = totals(entries)
        if not summed["requests"]:
            sys.exit(0)

        lines = [cost_line(summed), timing_line(entries, tool_spans(entries))]
    except Exception:
        sys.exit(0)

    # A leading newline puts the harness's "Stop says:" prefix on a line of its
    # own, so both reported lines start at the same column.
    report = "\n" + "\n".join(line for line in lines if line)
    print(json.dumps({"systemMessage": report}))
    sys.exit(0)


if __name__ == "__main__":
    main()
