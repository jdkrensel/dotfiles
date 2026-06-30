---
description: Summarize PHI-touching work from THIS clb session into a PHI-free block to paste back into the clp session
argument-hint: [what to summarize, if not the recent work]
allowed-tools: Read, Grep, Glob
profiles: clb
---

## Purpose

The other half of `/prompt`. Run this INSIDE a `clb` Bedrock (BAA-covered, PHI-capable) session
after the handed-off work is done. It distills what just happened — queries run, files inspected,
findings — into a single PHI-free block to paste BACK into the originating `clp` session, so that
session can keep reasoning with the results while no PHI ever crosses over.

**What to summarize:** $ARGUMENTS

## How to build it

1. **Identify the work.** If $ARGUMENTS is given, summarize that. Otherwise summarize the
   PHI-touching work done so far in this session — the database probe/query, data-export
   (xlsx/csv/parquet) inspection, or analysis that prompted the handoff.

2. **Strip all PHI.** This block leaves the BAA session, so it must contain ZERO patient-level
   data: no names, MRNs, DOBs, addresses, free-text notes, or individual rows. Report only
   aggregates — counts, distributions, min/max/medians, group-by tallies — and structural facts
   (table/column/file names, scope, what was checked). When in doubt, leave it out.

3. **Use this structure** (omit a section only if genuinely N/A):
   - **WHAT RAN** — the query/CLI/file actually used (the SQL or `uv run -m aaos ...` command),
     so the result is reproducible and auditable.
   - **SCOPE** — date range, client/facility, filters, row counts considered.
   - **RESULTS** — the findings as aggregate tables or counts, not raw dumps.
   - **DECISIONS / OPEN QUESTIONS** — anything resolved or still ambiguous that the clp session
     needs to continue.

4. **Output rules:**
   - Emit the summary as one fenced code block so it is trivially copyable, with no commentary
     inside the block.
   - Keep it tight; don't reference a specific model.
   - Outside the block, note it goes back into the originating `clp` session, and call out
     explicitly that you confirmed it contains no PHI.

Now generate the summary.
