---
description: Generate a self-contained prompt to hand off to another agent session (e.g. a database session), to be pasted back here
argument-hint: [focus of the handoff]
allowed-tools: Read, Grep, Glob
profiles: clp
---

## Purpose

Produce a single prompt block that the user will copy-paste into a SEPARATE agent session — by
default a `clb` Bedrock session that is BAA-covered and has database + PHI access. That agent runs
the task where PHI is allowed and reports a summary back into THIS session. This keeps PHI out of
the current (non-BAA) session and keeps context lean.

**Focus / task:** $ARGUMENTS

## How to build it

1. **Infer the focus.** If $ARGUMENTS is given, that's the focus. Otherwise infer the most likely
   handoff from what we've been doing — usually a database probe/query, a data-export
   (xlsx/csv/parquet) inspection, or similar PHI-touching work that can't happen in this session.

2. **Make it fully self-contained.** The other agent has NONE of our context. Spell out every fact
   it needs: the relevant background, exact table/column/file names, scoping (date ranges,
   client/facility), and any decisions already made. Use Read/Grep/Glob to pin down exact
   identifiers (table names, paths, CLI commands) rather than leaving them vague. Prefer reusing
   the repo's own CLI/query tools (e.g. `uv run -m aaos ... show-query`) over hand-written SQL when
   possible.

3. **Pre-shape the work for speed.** The other agent tends to launch a slow query or script and
   then sleep for 5–15 minutes waiting on it. You have the code here, so head that off:
   - If the handoff runs repo code (a runner, repo method, pull job), read the path it will
     exercise and name any per-row / per-message database calls — lookups inside a loop, lazy
     ORM loads — and say how to batch or memoize them.
   - If you're writing the SQL, make it set-based: filter and aggregate in the database, select
     only the needed columns, keep predicates sargable on indexed columns.
   - Give a rough size for the tables involved when you know it, so the estimate starts grounded.

4. **Use this structure** (omit a section only if genuinely N/A):
   - **CONTEXT** — the minimal background needed to act.
   - **GOAL** — the one-sentence task.
   - **SPECIFICS** — exact tables/columns/paths/scope; the cohort or filter.
   - **EXECUTION BUDGET** — always include; for trivially small work, one line (expected runtime,
     poll rather than sleep) is enough. Otherwise tell the other agent to:
     - **Estimate before running.** Check table row counts from catalog metadata, the indexes on
       filter/join columns, and the estimated plan (not an actual run), then state an expected
       runtime per step. If plan or metadata access is denied, time a small `TOP`/`LIMIT` sample
       instead.
     - **Restructure anything over ~1 minute** before running it: collapse per-row round trips
       into one set-based query or batched `IN` lists, memoize repeated lookups, push filtering
       and aggregation into SQL, and validate the shape on a small sample (`TOP`/`LIMIT`, one
       day, one facility) first.
     - **Build in visibility.** Long scripts print progress with elapsed time (`n/total`, flushed
       — `python -u`), time each stage separately (query vs. processing) so a stall is
       attributable, and write intermediate results to that session's own scratch (they never
       leave the BAA session) so a rerun skips the expensive fetch.
     - **Never sleep blind.** Poll progress output at short intervals; if a step runs past ~2×
       its estimate or its progress stalls, kill it and restructure rather than keep waiting.
   - **REPORT BACK** — what to return so it pastes cleanly back here — summary / aggregate tables,
     not raw dumps — plus estimated vs. actual runtime per query, so slow paths surface here.
   - **GUARDRAILS** — SELECT-only, no DML/DDL, aggregate counts/distributions only, and NO
     PHI / patient-level rows. PHI stays in the BAA session.

5. **Output rules:**
   - Emit the prompt as one fenced code block so it is trivially copyable, with no commentary
     inside the block.
   - Keep it tight; don't reference a specific model.
   - Outside the block, say which session to paste it into (default: a `clb` Bedrock session) and
     what you expect back.

Now generate the prompt.
