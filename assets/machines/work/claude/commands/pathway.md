---
description: Analyze pathway content and produce a readable summary
allowed-tools: Bash(cd*), Bash(uv*), Read
---

## Instructions

You are helping analyze a patient pathway from the PathwaysCreator database. Follow this workflow exactly:

### Step 1: Get Pathway ID

Ask the user directly (in plain text) for the pathway ID. Do NOT use `AskUserQuestion` -- just ask them to type the numeric ID. If the user already provided a pathway ID in their message, skip asking and proceed immediately.

### Step 2: Verify Pathway Exists

Run inline Python via `cd /Users/jessekrensel/repos/analyzer && uv run python -c "..."` using `DatabaseAnalyzer('prod')` to query:

```sql
SELECT * FROM PathwaysCreator.Pathways WHERE id = %s
```

**Execution Method:**
```bash
cd /Users/jessekrensel/repos/analyzer && uv run python -c "
from lib.db_analyzer import DatabaseAnalyzer

with DatabaseAnalyzer('prod') as db:
    result = db.query_raw('SELECT * FROM PathwaysCreator.Pathways WHERE id = %s', [PATHWAY_ID])
    print(result)
"
```

If no result is returned, tell the user the pathway doesn't exist and stop.

Store the pathway metadata for the final summary.

### Step 3: Fetch All Events

```bash
cd /Users/jessekrensel/repos/analyzer && uv run python -c "
from lib.db_analyzer import DatabaseAnalyzer

with DatabaseAnalyzer('prod') as db:
    result = db.query_raw('''
        SELECT * FROM PathwaysCreator.PathwayEvents
        WHERE PathwayID = %s AND Testing = 0
        ORDER BY RelativeToSignup, StartDay
    ''', [PATHWAY_ID])
    for row in result:
        print(row)
"
```

Store the full event list. Identify each event's `EventType` for the next step.

### Step 4: Fetch Content for Each Event Type

Run queries **only for event types that exist** in the pathway. Skip any event type that has zero events. Replace `PATHWAY_ID` with the actual pathway ID.

**IMPORTANT:** The PathwayEvents table uses `Label` (not `Name`) for the event label column.

**For alert events (EventType = 'alert'):**
```bash
cd /Users/jessekrensel/repos/analyzer && uv run python -c "
from lib.db_analyzer import DatabaseAnalyzer

with DatabaseAnalyzer('prod') as db:
    result = db.query_raw('''
        SELECT pe.id AS EventID, pe.Label, pe.StartDay, pe.RelativeToSignup,
               pa.Subject, pa.Message
        FROM PathwaysCreator.PathwayEvents pe
        JOIN PathwaysCreator.PathwayAlerts pa ON pa.EventID = pe.id
        WHERE pe.PathwayID = %s AND pe.Testing = 0 AND pe.EventType = \"alert\"
        ORDER BY pe.RelativeToSignup, pe.StartDay
    ''', [PATHWAY_ID])
    for row in result:
        print(row)
"
```

**For email events (EventType = 'email'):**
```bash
cd /Users/jessekrensel/repos/analyzer && uv run python -c "
from lib.db_analyzer import DatabaseAnalyzer

with DatabaseAnalyzer('prod') as db:
    result = db.query_raw('''
        SELECT pe.id AS EventID, pe.Label, pe.StartDay, pe.RelativeToSignup,
               pi.Subject, pi.Content, pi.Category
        FROM PathwaysCreator.PathwayEvents pe
        JOIN PathwaysCreator.PathwayInform pi ON pi.EventID = pe.id
        WHERE pe.PathwayID = %s AND pe.Testing = 0 AND pe.EventType = \"email\"
        ORDER BY pe.RelativeToSignup, pe.StartDay
    ''', [PATHWAY_ID])
    for row in result:
        print(row)
"
```

**For survey events (EventType = 'survey'):**
```bash
cd /Users/jessekrensel/repos/analyzer && uv run python -c "
from lib.db_analyzer import DatabaseAnalyzer

with DatabaseAnalyzer('prod') as db:
    result = db.query_raw('''
        SELECT pe.id AS EventID, pe.Label, pe.StartDay, pe.RelativeToSignup,
               ps.SurveyID, ps.MonitoringSurvey, ps.SurveyLinkText
        FROM PathwaysCreator.PathwayEvents pe
        JOIN PathwaysCreator.PathwaySurveys ps ON ps.EventID = pe.id
        WHERE pe.PathwayID = %s AND pe.Testing = 0 AND pe.EventType = \"survey\"
        ORDER BY pe.RelativeToSignup, pe.StartDay
    ''', [PATHWAY_ID])
    for row in result:
        print(row)
"
```

### Step 5: For Each Survey, Fetch Full Survey Content

For each unique `SurveyID` found in Step 4, run the following sequence. Replace `SURVEY_ID` with the actual survey ID.

**5a. Find the root QuestionSet node:**

SurveyIDs often use hyphens (e.g. `OrthoIndy-PT-Email`) while the database stores names with spaces (e.g. `OrthoIndy PT Email`). Always try an exact match first, then fall back to a LIKE search with hyphens replaced by `%` wildcards.

```bash
cd /Users/jessekrensel/repos/analyzer && uv run python -c "
from lib.db_analyzer import DatabaseAnalyzer

with DatabaseAnalyzer('prod') as db:
    survey_id = 'SURVEY_ID'
    # Try exact match first
    result = db.query_raw('''
        SELECT qs.NodeID, qs.Survey, qs.Name
        FROM CareSenseSurvey.QuestionSets qs
        WHERE qs.Survey = %s OR qs.Name = %s
        LIMIT 1
    ''', [survey_id, survey_id])
    if not result:
        # Fuzzy fallback: replace hyphens with wildcards
        fuzzy = survey_id.replace('-', '%')
        result = db.query_raw('''
            SELECT qs.NodeID, qs.Survey, qs.Name
            FROM CareSenseSurvey.QuestionSets qs
            WHERE qs.Survey LIKE %s OR qs.Name LIKE %s
        ''', [fuzzy, fuzzy])
    for row in result:
        print(row)
"
```

If multiple results are returned, select the one whose Name most closely matches the SurveyID (e.g. prefer "Email" variant for an email pathway). If no results at all, note this survey as "Survey not found" and continue with other events.

**5b. Get all child nodes in the survey tree** (using the `NodeID` from 5a):

**IMPORTANT:** The column `set` is a MySQL reserved word and must be backtick-escaped as `` `set` ``.

```bash
cd /Users/jessekrensel/repos/analyzer && uv run python -c "
from lib.db_analyzer import DatabaseAnalyzer

with DatabaseAnalyzer('prod') as db:
    result = db.query_raw('''
        SELECT child.ID, child.ElementTable
        FROM CareSenseSurvey.Nodes parent
        JOIN CareSenseSurvey.Nodes child
          ON child.lft > parent.lft AND child.rgt < parent.rgt AND child.\`set\` = parent.\`set\`
        WHERE parent.ID = %s AND child.Deleted = 0
        ORDER BY child.lft
    ''', [NODE_ID])
    for row in result:
        print(row)
"
```

From the results, collect node IDs grouped by their `ElementTable` type:
- `Questions` nodes -> for Step 5c
- `QuestionSets` nodes -> for Step 5e
- `References` nodes -> for Step 5f

**5c. Get all questions from those nodes** (using Question node IDs from 5b):

**IMPORTANT:** The Questions table columns are: `NodeID`, `Text`, `Survey`, `Field`, `TemplateID`, `OnLoad`, `OnNext`, `OnBack`, `Scoring`, `ScoringReference`, `Dynamic`, `Instance`, `Table`, `UseParentMapping`, `DBValue`. There is NO `Variable` or `InputType` column.

```bash
cd /Users/jessekrensel/repos/analyzer && uv run python -c "
from lib.db_analyzer import DatabaseAnalyzer

with DatabaseAnalyzer('prod') as db:
    node_ids = [NODE_ID_1, NODE_ID_2, ...]  # Question nodes from step 5b
    placeholders = ','.join(['%s'] * len(node_ids))
    result = db.query_raw(f'''
        SELECT q.NodeID, q.Text, q.Field, q.TemplateID
        FROM CareSenseSurvey.Questions q
        WHERE q.NodeID IN ({placeholders})
        ORDER BY q.NodeID
    ''', node_ids)
    for row in result:
        print(row)
"
```

**5d. Get answers for those questions** (using the question NodeIDs as question IDs):

**IMPORTANT:** The Answers table columns are: `QuestionID`, `OptionID`, `Ordering`, `Text`, `DBValue`, `Score`, `OnClick`, `Deleted`. There is NO `Value` column. Always filter out deleted answers.

```bash
cd /Users/jessekrensel/repos/analyzer && uv run python -c "
from lib.db_analyzer import DatabaseAnalyzer

with DatabaseAnalyzer('prod') as db:
    question_ids = [Q_ID_1, Q_ID_2, ...]  # NodeIDs from step 5c
    placeholders = ','.join(['%s'] * len(question_ids))
    result = db.query_raw(f'''
        SELECT a.QuestionID, a.Text, a.DBValue, a.Score, a.Ordering
        FROM CareSenseSurvey.Answers a
        WHERE a.QuestionID IN ({placeholders}) AND (a.Deleted = 0 OR a.Deleted IS NULL)
        ORDER BY a.QuestionID, a.Ordering
    ''', question_ids)
    for row in result:
        print(row)
"
```

**5e. Get child QuestionSet names** (using QuestionSet node IDs from 5b):

This reveals the survey's branching structure (anatomy groups, sections, etc.).

```bash
cd /Users/jessekrensel/repos/analyzer && uv run python -c "
from lib.db_analyzer import DatabaseAnalyzer

with DatabaseAnalyzer('prod') as db:
    qs_ids = [QS_ID_1, QS_ID_2, ...]  # QuestionSet nodes from step 5b
    placeholders = ','.join(['%s'] * len(qs_ids))
    result = db.query_raw(f'''
        SELECT qs.NodeID, qs.Survey, qs.Name
        FROM CareSenseSurvey.QuestionSets qs
        WHERE qs.NodeID IN ({placeholders})
        ORDER BY qs.NodeID
    ''', qs_ids)
    for row in result:
        print(row)
"
```

**5f. Resolve References to linked surveys** (using Reference node IDs from 5b):

Surveys commonly use References to embed external clinical instruments (e.g. DASH, HOOS, KOOS). The References table columns are: `NodeID`, `ReferenceID` (the target QuestionSet NodeID). There is NO `ReferenceNodeID` or `Description` column.

```bash
cd /Users/jessekrensel/repos/analyzer && uv run python -c "
from lib.db_analyzer import DatabaseAnalyzer

with DatabaseAnalyzer('prod') as db:
    ref_ids = [REF_ID_1, REF_ID_2, ...]  # Reference nodes from step 5b
    placeholders = ','.join(['%s'] * len(ref_ids))
    result = db.query_raw(f'''
        SELECT r.NodeID, r.ReferenceID
        FROM CareSenseSurvey.\`References\` r
        WHERE r.NodeID IN ({placeholders})
        ORDER BY r.NodeID
    ''', ref_ids)
    for row in result:
        print(row)
"
```

Then resolve each unique `ReferenceID` to its QuestionSet name:

```bash
cd /Users/jessekrensel/repos/analyzer && uv run python -c "
from lib.db_analyzer import DatabaseAnalyzer

with DatabaseAnalyzer('prod') as db:
    ref_node_ids = [REF_TARGET_1, REF_TARGET_2, ...]  # ReferenceID values from above
    placeholders = ','.join(['%s'] * len(ref_node_ids))
    result = db.query_raw(f'''
        SELECT qs.NodeID, qs.Survey, qs.Name
        FROM CareSenseSurvey.QuestionSets qs
        WHERE qs.NodeID IN ({placeholders})
        ORDER BY qs.NodeID
    ''', ref_node_ids)
    for row in result:
        print(row)
"
```

**5g. Fetch questions and answers for referenced surveys:**

For each referenced survey from 5f, repeat Steps 5b-5d to get its child question nodes, questions, and answers. You can batch all referenced surveys into a single query for efficiency:

```bash
cd /Users/jessekrensel/repos/analyzer && uv run python -c "
from lib.db_analyzer import DatabaseAnalyzer
from collections import defaultdict

with DatabaseAnalyzer('prod') as db:
    survey_roots = [ROOT_1, ROOT_2, ...]  # ReferenceID values (QuestionSet NodeIDs)
    all_question_nodes = []

    for root_id in survey_roots:
        children = db.query_raw('''
            SELECT child.ID, child.ElementTable
            FROM CareSenseSurvey.Nodes parent
            JOIN CareSenseSurvey.Nodes child
              ON child.lft > parent.lft AND child.rgt < parent.rgt AND child.\`set\` = parent.\`set\`
            WHERE parent.ID = %s AND child.Deleted = 0 AND child.ElementTable = \"Questions\"
            ORDER BY child.lft
        ''', [root_id])
        all_question_nodes.extend([c['ID'] for c in children])

    if all_question_nodes:
        placeholders = ','.join(['%s'] * len(all_question_nodes))
        questions = db.query_raw(f'''
            SELECT q.NodeID, q.Text, q.Field, q.TemplateID
            FROM CareSenseSurvey.Questions q
            WHERE q.NodeID IN ({placeholders})
            ORDER BY q.NodeID
        ''', all_question_nodes)

        q_ids = [q['NodeID'] for q in questions]
        if q_ids:
            placeholders2 = ','.join(['%s'] * len(q_ids))
            answers = db.query_raw(f'''
                SELECT a.QuestionID, a.Text, a.DBValue, a.Score, a.Ordering
                FROM CareSenseSurvey.Answers a
                WHERE a.QuestionID IN ({placeholders2}) AND (a.Deleted = 0 OR a.Deleted IS NULL)
                ORDER BY a.QuestionID, a.Ordering
            ''', q_ids)

            answers_by_q = defaultdict(list)
            for a in answers:
                answers_by_q[a['QuestionID']].append(a)

            for q in questions:
                print(f\"--- Q [{q['NodeID']}] ({q['Field']}): {q['Text']}\")
                for a in answers_by_q.get(q['NodeID'], []):
                    print(f\"    [{a['Score']}] {a['Text']}\")
                print()
"
```

### Step 5.5: Scan Survey Content for Variable References

After fetching all survey questions (Steps 5c and 5g), scan all question `Text` fields for:
- `<var>globals.XXXX</var>` patterns — template variables that must be populated at runtime
- `<var>...</var>` patterns in general — any dynamic content

This is a text analysis step (no new DB query needed). Parse the question text already fetched and collect:
1. All unique `globals.*` variable names referenced (e.g., `globals.side`, `globals.area`)
2. Any other `<var>...</var>` references

Store these for the Data Requirements section in Step 6.

### Step 5.6: Check for PassedDataQueries on Email/Inform Events

PassedDataQueries are JSON-encoded SQL queries on events that feed data into **email/inform Twig templates** (NOT survey globals). Query which events have them:

```bash
cd /Users/jessekrensel/repos/analyzer && uv run python -c "
from lib.db_analyzer import DatabaseAnalyzer

with DatabaseAnalyzer('prod') as db:
    result = db.query_raw('''
        SELECT id, Label, EventType, PassedDataQueries
        FROM PathwaysCreator.PathwayEvents
        WHERE PathwayID = %s AND Testing = 0 AND PassedDataQueries IS NOT NULL
    ''', [PATHWAY_ID])
    for row in result:
        print(row)
"
```

Store the results for the Data Requirements section in Step 6. Note: PassedDataQueries are only relevant for email/inform events, not survey events.

### Step 6: Synthesize and Present

Combine all collected data into a structured, readable summary:

#### 1. Pathway Overview
- Name, ID, and all metadata from the Pathways table

#### 2. Timeline
- Events organized chronologically by `RelativeToSignup` and `StartDay`
- Group events by their relative timing (e.g., "Day 0", "Day 7", etc.)

#### 3. Event Details
For each event, show the relevant content:
- **Alert events:** Subject + message content
- **Email events:** Subject + content summary (strip HTML to key points)
- **Survey events:** Survey name + all questions with their answer options formatted readably

#### 4. Summary
Provide a high-level analysis of:
- What the pathway does overall
- The patient journey it describes
- Any notable patterns (e.g., escalating survey frequency, conditional branching)

#### 5. Data Requirements

**a) Assignment Form Fields** — derived from pathway metadata (Step 2):
- Always required: PathwayID, PatientID, AnchorDate (labeled from `AnchorLabel`), Doctor
- Conditional: Side (if `HasSide='Yes'`), Anatomy (if `Anatomies` is non-empty), Location
- List the supported anatomies from the `Anatomies` field
- Note which anatomies hide the side selector (spine, neck, back, pelvis, sacroiliac)

**b) Survey Variable Dependencies** — derived from Step 5.5:
- List all unique `globals.*` variables referenced in survey question text
- **IMPORTANT: Only report variables that require external data** (i.e., data injected from outside the survey). Do NOT list any variable that the survey derives/computes internally from other globals. Common internally-derived variables to EXCLUDE:
  - `globals.sideCAPS` — derived from `globals.side.toUpperCase()`
  - `globals.showLeftKnee`, `globals.showRightKnee`, etc. — derived from `globals.patientAnatomies`
  - Any variable set via `OnLoad` JavaScript that computes from existing globals
  To identify internally-derived variables, check the `OnLoad` field of questions — if a variable is assigned there using other globals as input, it's internal and should NOT be listed.
- For each external variable, explain where it comes from at runtime using this reference:

| Global Variable | Database Source | How It Reaches the Survey |
|---|---|---|
| `globals.patient.PatientID` | `CareSenseData.Patients.PatientID` | **Pathway surveys**: `pathways_events/surveybuilder.py::build_patient_json()` embeds in processor node on_load JS in the survey cache. **Also**: PHP injection in `show.php` line 140 |
| `globals.patient.FirstName` | `CareSenseData.Patients.FirstName` | Same as PatientID |
| `globals.patient.LastName` | `CareSenseData.Patients.LastName` | Same as PatientID |
| `globals.patient.DOB` | `CareSenseData.Patients.DOB` | Same as PatientID |
| `globals.patient.Email` | `CareSenseData.ContactInfo.Email` | `pathways_events/surveybuilder.py::build_patient_json()` (line 745-786) fetches from ContactInfo and embeds in processor node. NOT in `show.php` — the Patients table has no Email column |
| `globals.patient.Phone` | `CareSenseData.ContactInfo.MobilePhone` (or HomePhone) | Same mechanism as Email via `build_patient_json()` |
| `globals.side` | `CareSensePathways.AssignedPathways.Side` | **Pathway surveys**: `pathways_events/surveybuilder.py::build_survey_cache()` (line 873) reads Side from Events→AssignedPathways and embeds `globals.side = 'left';` in a processor node's on_load JS baked into the survey cache. **V2**: v2_helper.php reads `interaction_schedule.instance` JSON and injects via processor node. **Ad-hoc**: can also arrive via `ScheduledEmails.Globals` query string or URL params |
| `globals.area` | `CareSensePathways.AssignedPathways.Area` | Same mechanisms as `globals.side` |
| `globals.treatments[anatomy]` | `CareSenseData.Treatments` (all columns, keyed by `Anatomy` field) | PHP injection in `show.php` lines 144-161 via `getMostRecentTreatmentByAnatomyForPatient()` |
| `globals.patientAnatomies` | `CareSenseData.Treatments.Anatomy` joined with `CareSenseData.StudyCollectionIntervals` | Runtime AJAX call to `api/patient/getAnatomiesForActiveIntervals` triggered by an External survey node |

- Flag if surveys reference `globals.side` or `globals.area` but the pathway has `HasSide='No'` or empty `Anatomies` (potential misconfiguration)

**c) PassedDataQueries Summary** — derived from Step 5.6:
- PassedDataQueries are **only for email/inform template variables** (Twig substitution), NOT for survey globals
- Note how many email/inform events have PassedDataQueries and list them
- If no email events exist, this section can be brief

### Data Issue Detection

When presenting the Data Requirements section, flag the following potential issues:

- **Missing Side/Area on assignment:** If `HasSide='Yes'` and `Anatomies` is non-empty and surveys reference `globals.side`/`globals.area`, note that the importer **must** set `side` and `area` on the `AssignedPathway` object. If these are null/empty at assignment time, surveys will render with blank placeholders. The data flows: importer writes `AssignedPathways.Side`/`Area` → `pathways_events/surveybuilder.py::build_survey_cache()` reads Side/Area from Events→AssignedPathways and embeds `globals.side`/`globals.area` values directly into a processor node's on_load JS in the survey cache file. V2 pathways use a similar mechanism through v2_helper.php processor nodes reading from `interaction_schedule.instance`.
- **Unreferenced globals:** If surveys reference `globals.side` or `globals.area` but the pathway has `HasSide='No'` or empty `Anatomies`, flag as a potential misconfiguration — the assignment form wouldn't collect these values, so the importer wouldn't know to set them.
- **Anatomy-survey mismatch:** If `Anatomies` is empty but the pathway's survey tree branches by anatomy (detected via QuestionSet names containing anatomy terms), flag as a potential issue.
- **Treatment record dependency:** If surveys use `globals.patientAnatomies` (fetched at runtime from `CareSenseData.Treatments` via `StudyCollectionIntervals`), note that the importer must write Treatment records with correct `Anatomy` values (e.g., "left knee", "right shoulder") for the survey branching to work. Without matching treatment records, `globals.patientAnatomies` will be empty and anatomy-based show flags won't activate.

Present these as **"Potential Issues"** subsection within Data Requirements, using clear language about what might go wrong and why.

**Important:** PassedDataQueries on events are for email/inform Twig template substitution only — they do NOT feed data into survey globals. Do not flag missing PassedDataQueries as a survey data issue.

### Error Handling

- If the pathway doesn't exist, report it clearly and stop
- If a survey can't be resolved from `CareSenseSurvey`, note it as "Survey not found" and continue with other events
- If the database connection fails, direct the user to check the `.env` file in `/Users/jessekrensel/repos/analyzer/`

### Important Reminders

- **Always** use the DatabaseAnalyzer context manager (`with` statement) for automatic connection cleanup
- **Never** hard-code credentials — they come from `.env`
- **Use `query_raw()`** method for raw dict results instead of pandas DataFrames
- **Run all queries automatically** — don't ask the user to run them manually
- **Always use `uv run`** to execute Python code — never use bare `python3`
- Always run from the analyzer directory: `cd /Users/jessekrensel/repos/analyzer`

### Database Schema Reference

These are the verified column names. Never guess column names -- use only these.

**PathwaysCreator.PathwayEvents:** `id`, `PathwayID`, `InitialEventID`, `Testing`, `EventType`, `Duration`, `Label` (NOT `Name`), `EventTypeID`, `StartDay`, `EndDay`, `RelativeToSignup`, `PeriodAmount`, `PeriodUnit`, `ExpirationAmount`, `ExpirationUnit`, `WeekdaysOnly`, `MaxLagDays`, `Highlighted`, `AppShowsEvent`, `ConditionalQuery`, `EvaluateConditionalQueryOnAssign`, `RelativeToSecondaryAnchor`, `RRule`, `CommSchedule`, `PassedDataQueries`, `EventOrder`, `BranchLevel`, `ImageID`, `Modified`

**CareSenseSurvey.Questions:** `ID`, `NodeID`, `Text`, `OnLoad`, `OnNext`, `OnBack`, `Scoring`, `ScoringReference`, `TemplateID`, `Survey`, `Dynamic`, `Instance`, `Table`, `UseParentMapping`, `Field`, `DBValue`, `Modified`

**CareSenseSurvey.Answers:** `ID`, `QuestionID`, `OptionID`, `Ordering`, `Text`, `DBValue`, `Score`, `OnClick`, `Modified`, `Deleted`

**CareSenseSurvey.References:** `ID`, `NodeID`, `ReferenceID`, `Modified`

**CareSenseSurvey.Nodes:** `ID`, `ElementTable`, `lft`, `rgt`, `` `set` `` (reserved word -- always backtick-escape), `Deleted`
