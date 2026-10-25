---
description: Optimize a SQL query with full context analysis
allowed-tools: AskUserQuestion, Bash(cd*), Bash(python3*), Read, Write
---

## Instructions

You are helping optimize a SQL query. Follow this workflow exactly:

### Step 1: Gather Requirements

Ask the user for:
1. The SQL query to optimize
2. Which database environment (staging or prod)

Use AskUserQuestion to collect both pieces of information.

### Step 2: Parse Table Names

Extract all table names from the query. Look for:
- Tables in FROM clauses
- Tables in JOIN clauses
- Tables referenced with schema prefixes (e.g., `schema.table`)

### Step 3: Execute Database Queries Directly

**IMPORTANT:** Execute Python code directly using `uv run python -c` from `/Users/jessekrensel/repos/analyzer`.

**Execution Method:**
1. **Prefer inline execution:** Use `uv run python -c "code here"` for all queries
2. **Only create script files** if the code is too complex for inline execution (rare)
3. Import DatabaseAnalyzer: `from lib.db_analyzer import DatabaseAnalyzer`
4. Use the environment from user's response ("staging" or "prod")
5. Execute all queries and print results

**Example - Run code inline (PREFERRED):**
```bash
cd /Users/jessekrensel/repos/analyzer && uv run python -c "
from lib.db_analyzer import DatabaseAnalyzer

with DatabaseAnalyzer('staging') as db:
    result = db.query_raw('SHOW CREATE TABLE users')
    print(result)
"
```

**Example - Multiple queries inline:**
```bash
cd /Users/jessekrensel/repos/analyzer && uv run python -c "
from lib.db_analyzer import DatabaseAnalyzer

with DatabaseAnalyzer('prod') as db:
    # Get table structure
    create_table = db.query_raw('SHOW CREATE TABLE users')
    print('CREATE TABLE:', create_table)

    # Get indexes
    indexes = db.query_raw('SHOW INDEX FROM users')
    print('INDEXES:', indexes)

    # Run EXPLAIN
    explain = db.query_raw('EXPLAIN ANALYZE SELECT * FROM users WHERE email = \"test@example.com\"')
    print('EXPLAIN:', explain)
"
```

**Dependency Management:**
- If you encounter a missing dependency (e.g., `ModuleNotFoundError`), add it using:
  ```bash
  cd /Users/jessekrensel/repos/analyzer && uv add package-name
  ```
- After adding dependencies, sync the environment:
  ```bash
  cd /Users/jessekrensel/repos/analyzer && uv sync
  ```
- Then retry running the script with `uv run`

**Important Notes:**
- **Always use `uv run`** to execute Python code - never use bare `python3`
- Always run from the analyzer directory: `cd /Users/jessekrensel/repos/analyzer`
- Database credentials are loaded from `/Users/jessekrensel/repos/analyzer/.env`
- The `.env` file uses environment variables: `{ENV}_DB_{HOST|PORT|USER|PASSWORD|NAME}`
- Use `query_raw()` method for dict results (not `query()` which returns DataFrames)
- The analyzer project uses `uv` for dependency management - respect the existing pyproject.toml

### Step 4: Gather Table Context

For each table found in Step 2, automatically run these queries:

**A. Get table structure:**
```sql
SHOW CREATE TABLE table_name;
```

**B. Get index information:**
```sql
SHOW INDEX FROM table_name;
```

Store all results for analysis.

### Step 5: Analyze Query Execution

Run EXPLAIN ANALYZE on the user's original query:

```sql
EXPLAIN ANALYZE
<user's query here>
```

This provides:
- Execution plan
- Actual timing data
- Rows examined vs rows returned
- Index usage

### Step 6: Analyze and Recommend

Based on all gathered context, provide optimization recommendations covering:

**Index Optimization:**
- Missing indexes that would speed up the query
- Unused indexes that could be dropped
- Composite index suggestions for multi-column filters
- Index cardinality issues

**Query Rewriting:**
- Subquery vs JOIN performance
- WHERE clause optimization
- SELECT * vs specific columns
- LIMIT usage for large result sets

**Join Optimization:**
- Join order optimization
- Join type selection (INNER vs LEFT)
- ON clause vs WHERE clause filtering

**Table Structure Issues:**
- Data type inefficiencies
- Normalization recommendations
- Partitioning opportunities (if applicable)

### Step 7: Present Results

Format your response with:

1. **Current Performance Summary**
   - Execution time
   - Rows examined
   - Key bottlenecks identified

2. **Recommended Optimizations** (prioritized by impact)
   - Each recommendation with:
     - What to change
     - Why it will help
     - Expected performance improvement
     - SQL statement to implement (for index changes)

3. **Rewritten Query** (if applicable)
   - Show the optimized version of the query
   - Highlight what changed and why

### Error Handling

If you encounter connection issues:
- Verify `.env` file exists in `/Users/jessekrensel/repos/analyzer/`
- Check that credentials are set for the selected environment
- Confirm user has network access to the database

If a table doesn't exist:
- Check for schema prefixes
- Verify the table name is spelled correctly
- Ask user to confirm the database environment

## Example Workflow

```
User provides: "SELECT * FROM users WHERE email = 'test@example.com'"
Environment: staging

1. Parse tables → Found: users
2. Run: SHOW CREATE TABLE users
3. Run: SHOW INDEX FROM users
4. Run: EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'test@example.com'
5. Analyze results and recommend:
   - Add index on email column
   - Use SELECT id, name, email instead of SELECT *
6. Show optimized query with expected improvements
```

## Important Reminders

- **Always** use the DatabaseAnalyzer context manager (with statement) for automatic connection cleanup
- **Never** hard-code credentials - they come from `.env`
- **Use query_raw()** method for raw dict results instead of pandas DataFrames
- **Run all queries automatically** - don't ask the user to run them manually
- **Be specific** with index recommendations - provide exact CREATE INDEX statements
