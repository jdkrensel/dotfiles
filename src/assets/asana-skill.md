# Asana Task Fetcher Skill

## Purpose
Fetch task details from Asana including description, comments, subtasks, and custom fields for bug fixes and context loading.

## Repository Location
`/Users/jessekrensel/repos/analyzer`

## Usage
When the user mentions an Asana task URL (e.g., "the asana task is https://app.asana.com/...") or provides a task GID:

1. Run: `/Users/jessekrensel/repos/analyzer/scripts/asana <task_identifier>`
2. The script uses credentials stored in `.env` file (ASANA_API_TOKEN)
3. Task identifier can be:
   - Full Asana URL: `https://app.asana.com/.../task/1234567890`
   - Task GID only: `1234567890`

## Example Output
```
================================================================================
ASANA TASK DETAILS
================================================================================

Task Name: PROJECT_123 - Update Importer to Enroll New Location and Providers
Task URL: https://app.asana.com/.../task/1234567890
Created: 2026-01-07T19:20:46.597Z
Completed: False
Assigned to: User A

--------------------------------------------------------------------------------
DESCRIPTION
--------------------------------------------------------------------------------

Email address:
user@example.com

Project Title:
PROJECT_123 - Update Importer to Enroll New Location and Providers

Who are the Client-Side Subject Matter Experts (SMEs)?:
SME User

What does the client want?:
We are going to be receiving schedules for a new location...

--------------------------------------------------------------------------------
KEY FIELDS
--------------------------------------------------------------------------------

Build Started: 2026-01-26T00:00:00.000Z
Client: [ABC] Client Name
Hrs Budgeted: 6
Implementation: User A
Next Step: Send to QA
Primary Domain: Integration
Status: On Deck
Systems: Import | API
Team: Infrastructure
Type of work: Update

--------------------------------------------------------------------------------
COMMENTS (4)
--------------------------------------------------------------------------------

Comment 1:
  Author: User B
  Date: 2026-01-08T17:57:58.755Z
  Text: do we know if these will be coming in via System A or System B?

...

--------------------------------------------------------------------------------
SUBTASKS (3)
--------------------------------------------------------------------------------

  ✓ Review import configuration (Assignee: User A)
  ○ Test with staging data (Assignee: QA Team)
  ○ Deploy to production (Assignee: Unassigned)

================================================================================
```

## Common Commands
- Get task details: `/Users/jessekrensel/repos/analyzer/scripts/asana <task_id>`
- Get from URL: `/Users/jessekrensel/repos/analyzer/scripts/asana <asana_url>`
- Get JSON output: `/Users/jessekrensel/repos/analyzer/scripts/asana <task_id> --json`
- Get Python script path: `/Users/jessekrensel/repos/analyzer/scripts/get_asana_task.py`

## Technical Details
- Script: `/Users/jessekrensel/repos/analyzer/scripts/get_asana_task.py`
- Wrapper: `/Users/jessekrensel/repos/analyzer/scripts/asana`
- Uses `uv run` to execute with dependencies
- Extracts task GID from URL using regex pattern `task/(\d+)`
- Fetches task details, comments (filtered to actual comments only), and subtasks
- Displays relevant custom fields (Status, Team, Client, etc.)
