---
description: Start an exploratory analysis session against a database environment
allowed-tools: mcp__mysql_prod__query, mcp__mysql_staging__query, Read, Write, Edit, Glob, Grep, AskUserQuestion
---

## Instructions

The user is starting an exploratory database analysis session.

**Arguments:** $ARGUMENTS

### 1. Parse Arguments

- **First word** must be `prod` or `staging` — this is the database environment.
- **Everything after** is the analysis goal. If no goal is provided, ask what they want to investigate.
- If no environment is provided, ask which one to use.

### 2. Connect to the Right Server

- `prod` → use **only** the `mysql_prod` MCP server
- `staging` → use **only** the `mysql_staging` MCP server
- Do not query the other environment unless the user explicitly asks to switch.

### 3. Explore

Start by understanding the analysis goal, then:

1. Browse relevant schemas and tables to orient yourself
2. Sample data to understand column values and cardinality
3. Form hypotheses and test with queries
4. Iterate based on what the data shows

### 4. Optimize Before Executing Expensive Queries

Before running any query that touches large tables or performs joins across multiple tables:

1. `SHOW CREATE TABLE` for every table in the query
2. `SHOW INDEX FROM` for each table
3. `EXPLAIN` the query — check for full table scans, unindexed joins, high row estimates
4. If the plan is bad, rewrite first. Only execute once the plan is acceptable.

### 5. Cache Expensive Results

When an expensive query produces useful results:

- Save the output as a parquet file in the working analysis directory under `outputs/`
- Subsequent analysis should read from the cache, not re-query the database
- Always provide a `--refresh` flag to force re-query when needed

### 6. Graduate to a Script

When the exploration produces a repeatable analysis worth keeping, create a script using `DatabaseAnalyzer` from `/Users/jessekrensel/repos/analyzer/lib/`. Follow existing analysis patterns in that repo:

1. Create a script in `analyses/<name>/queries/` using `DatabaseAnalyzer`
2. Include parquet caching for any expensive queries
3. Run `EXPLAIN ANALYZE` on the final optimized query and include a comment in the script noting the expected row count and timing
4. Run with `cd /Users/jessekrensel/repos/analyzer && uv run analyses/<name>/queries/<script>.py`
