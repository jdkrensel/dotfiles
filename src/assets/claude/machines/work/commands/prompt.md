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

   Pin every data source to its environment: name the server/database and schema-qualify every
   table (`live.anchor`, not `anchor`). When repo code resolves the schema indirectly — a
   `search_path`, a settings stage — read how it resolves and state the value the other agent
   must bind to, rather than letting the repo's default pick it.

3. **Pre-shape the work for speed.** The other agent tends to launch a slow query or script and
   then sleep for 5–15 minutes waiting on it. You have the code here, so head that off:
   - If the handoff runs repo code (a runner, repo method, pull job), read the path it will
     exercise and name any per-row / per-message database calls — lookups inside a loop, lazy
     ORM loads — and say how to batch or memoize them. Note whether each item's work is
     independent (no shared writes or state), so the other agent knows it can split the loop
     across workers.
   - If you're writing the SQL, make it set-based: filter and aggregate in the database, select
     only the needed columns, keep predicates sargable on indexed columns.
   - Give a rough size for the tables involved when you know it, so the estimate starts grounded.

4. **Use this structure** (omit a section only if genuinely N/A):
   - **CONTEXT** — the minimal background needed to act.
   - **GOAL** — the one-sentence task.
   - **SPECIFICS** — exact tables/columns/paths/scope; the cohort or filter.
   - **VERIFY BEFORE CONCLUDING** — always include; for trivial or non-database work, one line
     (suspect the query before the system) is enough. Otherwise tell the other agent to:
     - **Confirm where each connection lands** before trusting its results (e.g.
       `SELECT current_database(), current_setting('search_path')`,
       `SELECT DB_NAME(), SCHEMA_NAME()`), and schema-qualify tables in any SQL it writes.
     - **Suspect the query before the system.** A result implying something is broken or
       missing — a near-zero match rate, a feed that "stopped", an empty table — is first a
       sign of a wrong source or join. Check it from an independent angle (a raw count in the
       expected schema, a known recent record, another time window); re-running the same code
       path is not verification.
     - **Mark what it couldn't check** — a broken-or-missing result not confirmed from an
       independent angle stays under RESULTS, marked UNVERIFIED.
   - **EXECUTION BUDGET** — always include; for trivially small work, one line (expected runtime,
     poll rather than sleep) is enough. Otherwise tell the other agent to:
     - **Estimate before running.** Check table row counts from catalog metadata, the indexes on
       filter/join columns, and the estimated plan (not an actual run), then state an expected
       runtime per step. If plan or metadata access is denied, time a small `TOP`/`LIMIT` sample
       instead.
     - **Restructure anything over ~1 minute** before running it: collapse per-row round trips
       into one set-based query or batched `IN` lists, memoize repeated lookups, push filtering
       and aggregation into SQL, and validate the shape on a small sample (`TOP`/`LIMIT`, one
       day, one facility) first. Profile that sample once to find every per-item database call
       together, rather than fixing one per restart.
     - **Parallelize what stays per-item.** Project the total from the sample's per-item rate
       (0.2s × 10,000 messages is 33 minutes). If the projection is over ~5 minutes and the
       items are independent, split the input into chunks across a process pool — each worker
       with its own connection and cache — and cap workers at ~4–8 so the load on the
       production database stays modest. Run independent queries concurrently too, within the
       same cap.
     - **Build in visibility.** Long scripts print progress with elapsed time (`n/total`, flushed
       — `python -u`), time each stage separately (query vs. processing) so a stall is
       attributable, and write intermediate results to that session's own scratch (they never
       leave the BAA session) so a rerun skips the expensive fetch.
     - **Never sleep blind.** Poll progress output at short intervals; if a step runs past ~2×
       its estimate or its progress stalls, kill it and restructure rather than keep waiting.
       When killing a pool, terminate every worker and confirm its queries are gone from the
       server.
   - **REPORT BACK** — what to return so it pastes cleanly back here — summary / aggregate tables,
     not raw dumps — plus, per query, the server/database/schema it actually hit (or "not
     confirmed") and estimated vs. actual runtime, with unchecked results marked UNVERIFIED.
   - **GUARDRAILS** — SELECT-only, no DML/DDL, aggregate counts/distributions only, and NO
     PHI / patient-level rows. PHI stays in the BAA session.

5. **Output rules:**
   - Emit the prompt as one fenced code block so it is trivially copyable, with no commentary
     inside the block.
   - Keep it tight; don't reference a specific model.
   - Outside the block, say which session to paste it into (default: a `clb` Bedrock session) and
     what you expect back.

Now generate the prompt.
