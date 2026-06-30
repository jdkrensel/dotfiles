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

3. **Use this structure** (omit a section only if genuinely N/A):
   - **CONTEXT** — the minimal background needed to act.
   - **GOAL** — the one-sentence task.
   - **SPECIFICS** — exact tables/columns/paths/scope; the cohort or filter.
   - **REPORT BACK** — what to return so it pastes cleanly back here — summary / aggregate tables,
     not raw dumps.
   - **GUARDRAILS** — SELECT-only, no DML/DDL, aggregate counts/distributions only, and NO
     PHI / patient-level rows. PHI stays in the BAA session.

4. **Output rules:**
   - Emit the prompt as one fenced code block so it is trivially copyable, with no commentary
     inside the block.
   - Keep it tight; don't reference a specific model.
   - Outside the block, say which session to paste it into (default: a `clb` Bedrock session) and
     what you expect back.

Now generate the prompt.
