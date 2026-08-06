---
name: redact-phi-preserving-shape
description: >
  Create a safe, shareable copy of a file containing PHI/PII by replacing every patient
  identifier with realistic fake data while keeping the file's shape byte-for-byte identical --
  same extension and MIME type, same tabs, same headers, same column counts, same row counts,
  same date formats, same ID character patterns, and the same mix of value formats in the same
  proportions. Use this whenever someone wants to de-identify, redact, anonymize, scrub,
  sanitize, mask, or "fake out" a real data file, or wants a test/sample/dummy/mock version of a
  production file they can safely commit to a repo, attach to a ticket, paste in Slack, send to a
  vendor, or hand to a colleague. Trigger it for any CSV, TSV, pipe-delimited, or Excel file
  holding patient names, MRNs, DOBs, SSNs, subscriber/member IDs, account numbers, phone numbers,
  emails, or addresses -- including phrasings like "remove the PHI from this", "make me a fake
  version of this file", "I need to share this billing extract but not the patient data", or
  "scrub this before I commit it". Prefer this skill over writing an ad-hoc script, because
  hand-rolled redaction reliably breaks shape fidelity and silently misses columns.
profiles: clb
---

# Shape-preserving PHI redaction

Turn a real file into a fake one that is **structurally indistinguishable** from the original and
contains **no real patient data**.

Both halves matter, and they pull against each other. If shape drifts, the redacted file stops
exercising the code paths the real one does, so testing against it gives false confidence. If a
single real identifier survives, the file is still PHI and the whole exercise failed. The workflow
below exists to get both, and to *prove* it rather than assume it.

## The workflow

Five steps. Step 4 is the one people skip; it's the one that catches the mistakes.

```
1. inspect_file.py   ->  profile the file, draft a column plan
2. (you decide)      ->  resolve every REVIEW column; set identity_key
3. redact.py         ->  apply the plan
4. verify.py         ->  prove shape held and nothing leaked  <-- never skip
5. report            ->  full path to the output + what was redacted
```

Run everything with `uv run --with openpyxl python <script>` so `openpyxl` is available for Excel.
The scripts live in `scripts/` next to this file.

### 1. Profile the file

```bash
uv run --with openpyxl python scripts/inspect_file.py INPUT --emit-plan plan.json
```

This prints, per column: sample values, distinct counts, character masks, name templates, and a
proposed type with the reasoning behind it. It writes a draft `plan.json`.

Read the output. It is evidence for a decision you are making, not a decision already made.

### 2. Decide what is PHI

Two edits are always yours to make:

**Set `identity_key`.** This names the column(s) that identify a patient — usually the MRN. It is
how the tool knows two rows are the same person, which is what makes one patient's name, DOB and
IDs come out consistent everywhere they appear. Leave it empty and every row becomes its own
person, destroying the duplicate-patient and repeat-visit structure that makes the file useful.

**Resolve every `"type": "REVIEW"`.** These are columns the profiler could not judge confidently.
Either give it a real type or change it to `"keep"` to leave the column untouched. A `REVIEW` left
in the plan is treated as an opaque id, which is safe but may be wrong.

Use `"keep"` rather than deleting the entry. Verification re-profiles the file independently and
fails on any *unlisted* column that looks like PHI, so a deleted entry comes back as a failure on
the next run; `keep` records that you looked. On a wide extract, expect to add a few `keep`
entries on the first pass — a date column that belongs to a code rather than a person is the
usual one.

Header names lie. A column called `ID` may be a patient identifier or a procedure code; `Date`
may be a birth date or a code's effective date. The sample values in the profile tell you which.

#### What counts as PHI here

The 18 HIPAA identifiers, scoped to **the patient and their relatives, employers and household
members**. That scope is what Safe Harbor actually requires, and it is what keeps the output
useful.

Redact: names, geography finer than a state (street, city, county, ZIP), dates tied to the
individual (birth, admission, discharge, death; ages over 89), phone and fax numbers, email
addresses, SSNs, MRNs, health-plan and beneficiary numbers, account numbers, certificate and
licence numbers, vehicle and device identifiers, personal URLs and IP addresses, biometrics,
face photographs, and any other uniquely identifying code.

Preserve: **everything else, byte-for-byte.** Clinical codes (CPT, ICD, HCPCS, DRG), procedure
descriptions, payor names, laterality, encounter type, sex, race, language, state, consent flags,
charges — these carry no identity and they are exactly what makes the redacted file worth having.

Two boundary calls worth stating outright, because they come up in almost every file:

- **Treating providers and facilities are not patient PHI.** A surgeon's name, an ORP number, a
  hospital or OR-suite name identifies the covered entity and its staff, not the patient. Default
  to preserving them: surgeon→NPI mapping and facility routing are common things to test. If the
  file is going somewhere the client's identity shouldn't travel, redact them too — but say so,
  since it costs test fidelity.
- **Free-text notes are the exception to "preserve everything else."** A note field can contain
  anything, including names and dates the column plan knows nothing about. If a file has one,
  either redact the whole column or read enough of it to be sure. Flag this to the user rather
  than quietly hoping.

The available types:

| type | for | how the fake is built |
|---|---|---|
| `name` | any name column | same template and mask; per-row structure preserved |
| `date` | person-linked dates | shifted, original format re-rendered exactly |
| `id` | MRN, subscriber, account, CSN, licence, serial, VIN, device | character mask filled |
| `ssn` | SSNs | mask preserved, forced into the never-issued 900-999 range |
| `phone` | phone and fax | mask preserved, forced to reserved 555-01xx |
| `email` | emails | structure kept, domain forced to `example.com` |
| `zip` / `city` / `address` | geography | invented place and street names |
| `age` | ages | plausible value, never above 89 |
| `url` / `ip` | personal links, device IPs | reserved documentation ranges |
| `keep` | a column you reviewed and judged non-PHI | nothing — preserved byte-for-byte, but recorded as considered |

For split name columns add `"name_part": "first" | "middle" | "last"`. For whole-name columns
add `"name_order": "last_first"` or `"first_last"` (the profiler usually infers this).

### 3. Redact

```bash
uv run --with openpyxl python scripts/redact.py --plan plan.json --in INPUT [--out OUTPUT]
```

The default output name inserts `_REDACTED` before the extension: `BillingExtract_2026Q2.csv` →
`BillingExtract_2026Q2_REDACTED.csv`. The stem and extension are kept so the file stays recognisable
to whatever routes or reads it, but the marker is deliberate — a redacted file that looks
byte-identical in a directory listing is how the wrong one eventually gets sent to a client.

Each run uses a **fresh random salt by default**, so two runs of the same file produce different
fake data. That is deliberate: every fake value derives from the salt and the real value, so a
salt someone else can obtain is a re-identification key — the identifier spaces are small enough
to brute-force, and a candidate that reproduces the fake MRN also reproduces the fake name and
date shift, confirming the hit.

Set `REDACT_SALT` (or `--salt`) when you need determinism — regenerating a committed fixture
without churning the diff is the usual reason. Treat that salt as a secret: it is the crosswalk.

### 4. Verify — always

```bash
uv run --with openpyxl python scripts/verify.py --original INPUT --redacted OUTPUT \
    --plan plan.json --distributions
```

Exit code is non-zero if any check fails. It independently confirms both halves of the contract:
row and column counts, headers, tab names and order, delimiter, encoding, BOM, newline style,
per-cell character masks, name templates, date formats, cell types and number formats, and
workbook document properties — and separately, that **no original PHI value appears anywhere in
the output**, including as a component of a name and including in columns it wasn't supposed to
be in.

Crucially, it does not take the plan's word for what counts as PHI. It re-profiles the original
with the same classifier `inspect_file.py` uses and fails if a column *absent from the plan* looks
like PHI, or if a plan column matched no header in the file. Without that, the leak scan could
only ever search for values the plan already named — so the one mistake that matters most, a
column nobody thought about, would be the one mistake it could not see.

`--distributions` prints template frequencies side by side. They should match exactly.

If a check fails, fix the cause rather than the check — a failing verify is most often a column
missing from the plan, and that is precisely the bug worth catching. Where the classifier is
wrong about a column, record the decision as `{"name": "...", "type": "keep"}` rather than
silencing the check; a reviewed column and an overlooked one should not look alike.

### 5. Tell the user where the file is

Close every run by naming the **full absolute path** of the redacted file, on its own line, plus
the verify result and which columns were redacted versus preserved:

```
Redacted file: /Users/you/data/BillingExtract_2026Q2_REDACTED.csv
Verify: 17/17 checks passed
Redacted: MRN #, DOS, PAT_NAME, DOB, both Subscriber Numbers, EncounterCSN
Preserved: Hospital, Surgical Location, payors, SURGEON, ORP, CPT, PROC_NAME, ICD10 CM, LATERALITY
```

This matters more than it looks. The output usually lands somewhere the user didn't pick — next to
the input, or in whatever directory the command ran from — and they are about to move it into a
repo, attach it to a ticket, or send it to a vendor. A relative path or "I've created the redacted
file" makes them go hunting, and hunting near a directory that still contains the *real* file is
exactly where the wrong one gets picked up. Naming the path also lets them confirm at a glance
that you wrote the copy and not over the original.

## How shape is preserved

Two ideas carry most of the weight; knowing them helps when something looks off.

**Character masks** reduce a value to its skeleton — `1AB2CD3EF45` → `9AA9AA9AA99` — and the fake
is generated to fill that skeleton exactly. Length, digit and letter positions, punctuation, case
and zero-padding all survive. This handles every opaque identifier without per-column rules.

**Per-row template preservation** is how the frequency requirement is met. Rather than measuring
that a name column is 20% `FIRST M` and 60% `FIRST M LAST` and then sampling to hit those
targets, each row keeps *its own* structure: `TEST,ALPHA A` → `YOST,ADELA D`. The distribution
therefore matches the source exactly, with no sampling error, and the same trick covers date
formats and ID variants.

Dates use **one shift per patient**, applied to all their dates. Age at surgery, days between
visits and encounter ordering all survive; the link to the real calendar does not.

Unpadded formats (`3/7/51`) and spelled-out months (`1 September 1948`) keep their component
widths, which costs a small nudge to the shift for those values — so a patient whose dates are
written in *two different* formats has the interval between those two dates move by up to a few
months. Within a single format, and so in almost every real column, intervals are exact.

## Things worth getting right

**Never write a crosswalk.** A real→fake mapping file is a re-identification key: it is PHI, and
writing one converts a safe artifact into a liability sitting next to it. The mapping lives in
memory and is discarded. If someone needs reproducibility, that is what the salt is for.

**Consistency is per-subject, not per-value.** One patient's identity is stable across every row,
column and worksheet. That is what keeps duplicate-patient logic, joins on MRN and repeat-visit
ordering meaningful in the output.

**Check the whole workbook.** Excel files hide PHI in places a first pass misses: additional
tabs, hidden sheets, header and footer text, defined names, comments, and the document
properties. `redact.py` edits cells on a copy, so formulas, number formats, column widths, freeze
panes and (for `.xlsm`) macros survive; it also clears the identifying document properties —
`creator`, `lastModifiedBy`, `title`, `company` and friends — because `lastModifiedBy` on a client
workbook is routinely a real person's name, and verify.py fails if any are still set.

What the copy does *not* carry through is anything openpyxl itself drops: charts, images, pivot
caches and cached formula results. If the workbook has those, or a sheet header/footer or comment
naming a patient, say so rather than assuming it was handled. Legacy `.xls` is rejected outright —
re-save as `.xlsx` first, since openpyxl cannot read the old format at all.

**A row count that changed is a bug, not a rounding difference.** Same for a column count. If
verify reports one, something dropped data.

## Reference

- `references/plan-format.md` — every plan field, worked examples, and the awkward cases
  (multi-sheet plans, split names, ID columns that are also foreign keys)
- `scripts/test_shapes.py`, `scripts/test_redact.py` — the test suites. Run them after changing
  any script: `uv run --with pytest --with openpyxl python -m pytest scripts/ -q`

## If the file isn't CSV/TSV/Excel

These scripts cover delimited text and Excel. For HL7, JSON, XML or PDF, the same principles
apply — mask-preserving replacement, per-subject consistency, verify afterwards — but the
scripts won't parse them. Say that plainly and either write a targeted transform for that format
or ask how the user wants to proceed. Do not run a delimited-text parser over an HL7 message and
hope; it will mangle segment structure while appearing to succeed.
