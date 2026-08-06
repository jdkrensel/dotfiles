# The column plan

The plan is a JSON file naming which columns hold PHI and what kind. Everything not
named in it is copied through byte-for-byte.

Read this when the draft plan from `inspect_file.py` doesn't cover your case: split
name columns, per-sheet headers, ID columns that are also foreign keys, or a column
the profiler flagged `REVIEW` and you're unsure how to resolve.

## Contents

- [Top-level fields](#top-level-fields)
- [Column entries](#column-entries)
- [Types in detail](#types-in-detail)
- [Worked example: pipe-delimited billing extract](#worked-example-pipe-delimited-billing-extract)
- [Worked example: multi-sheet workbook](#worked-example-multi-sheet-workbook)
- [Awkward cases](#awkward-cases)

## Top-level fields

```json
{
  "header_row": 0,
  "identity_key": ["MRN #"],
  "date_offset_range": [-540, 540],
  "output_suffix": "_REDACTED",
  "delimiter": "|",
  "sheets": {"Summary": {"skip": true}},
  "columns": []
}
```

| field | default | meaning |
|---|---|---|
| `header_row` | `0` | Zero-based index of the header row. Use `2` for a file with two banner rows above the headers. |
| `identity_key` | `[]` | Column(s) identifying a patient. **Set this.** See below. |
| `date_offset_range` | `[-540, 540]` | Bounds, in days, for the per-patient date shift. |
| `output_suffix` | `"_REDACTED"` | Inserted before the extension when `--out` is omitted. |
| `delimiter` | auto-detected | Override only if detection gets it wrong. |
| `sheets` | `{}` | Per-worksheet overrides, keyed by tab name. `{"skip": true}` leaves a sheet alone; `{"header_row": N}` overrides the header row for that sheet. |
| `columns` | — | The list of PHI columns. |

### Why `identity_key` matters

It defines what makes two rows the same person. All of that person's generated values —
name, DOB shift, IDs — derive from it, so the same patient comes out identical on every
row, in every column, across every worksheet.

Prefer a stable identifier over a name: source systems spell names inconsistently
(`TEST,ALPHA A` vs `Test, Alpha`) but rarely mistype the MRN. Values are normalized
(case, punctuation and accents folded) before use, so minor variants still agree.

Composite keys work when no single column identifies a patient:

```json
"identity_key": ["Last Name", "First Name", "DOB"]
```

If `identity_key` is empty, or every key column is blank on a row, that row becomes its
own subject. Safe, but it flattens duplicate-patient structure — the thing that usually
made the file interesting to test against.

### Choosing `date_offset_range`

The default ±540 days moves dates far enough that the real calendar date isn't
recoverable, while keeping ages roughly plausible. Widen it for stronger
de-identification; narrow it if downstream logic depends on dates landing in a
particular era (a fiscal year, a specific quarter). The shift is never zero.

All of one patient's dates move together, so intervals survive — with one exception
worth knowing. Where a date is written unpadded (`3/7/51`) or with a spelled-out month
(`1 September 1948`), the shift is nudged a few days to a few months so the re-rendered
value keeps its original field width. That nudge is per value, so two dates for the same
patient written in *different* formats can move by different amounts, and the interval
between those two specific dates shifts with it. Dates sharing a format — the normal
case, and always true of zero-padded columns — keep their intervals exactly.

## Column entries

```json
{"name": "PAT_NAME", "type": "name", "name_order": "last_first"}
```

| key | required | meaning |
|---|---|---|
| `name` | yes | Header text. Matched case-insensitively, whitespace-trimmed. |
| `type` | yes | See the table below. |
| `aliases` | no | Other headers meaning the same field, e.g. `["MRN", "MRN #", "Medical Record Number"]`. Useful for one plan across several sheets or file versions. |
| `name_part` | for split names | `"first"`, `"middle"`, or `"last"`. |
| `name_order` | for whole names | `"last_first"` or `"first_last"`. Inferred from a comma if omitted. |

A column named in the plan but absent from the file is **reported as an error by
`verify.py`**. One plan can still serve a family of similar files — use `aliases` to
cover the naming variants — but an entry that silently matches nothing is how a
renamed column stops being redacted without anyone noticing, so it is surfaced
rather than ignored.

### `keep`: recording a column as reviewed

`verify.py` independently re-profiles the original and fails if a column absent from
the plan looks like PHI. When it is wrong about a column, say so explicitly:

```json
{"name": "Ref", "type": "keep"}
```

The column is preserved byte-for-byte exactly as if it were unlisted — the entry
changes nothing about the output. What it changes is the audit trail: a column
somebody considered and cleared no longer looks identical to one nobody ever read.

## Types in detail

### `name`

Preserves the row's own template exactly — word count, initials, separators, suffixes,
punctuation and case — and matches each word's length so the character mask survives.

```
TEST,ALPHA A               ->  YOST,ADELA D
MOCKS,BRAVO DELTA          ->  STARK,VESTA JONAH
TESTCO,FOXTROT GOLF JR.    ->  PRESTON,ROSIE MABEL JR.
VAN DER TEST,HOTEL INDIA   ->  MEADE LA VEGA,CAROL ANNA
O'SAMPLE,QUEBEC P          ->  D'AMATO,CARL B
```

Suffixes (`JR.`, `III`, `MD`) are kept verbatim: they describe structure, not identity,
and preserving them keeps the template intact. Initials stay initials, and never become
a letter that reads as a suffix (`V`, `I`) — that would silently change the template.

Generated words avoid every name word appearing anywhere in the source file, so no fake
name coincides with a real one from another patient.

### `date`

Recognises and re-renders these spellings exactly:

```
01/02/1950   3/7/51   1950-01-02   01.02.1950   19500102
12-Jan-1950  12 January 1950   2026-03-01 14:22:00
```

Two-digit years stay two-digit; unpadded components stay unpadded; trailing timestamps
are preserved. A value that doesn't parse as a date is left alone rather than corrupted —
so if a date column comes through unchanged, check the format is one of the above.

### `id`

The generic type for opaque identifiers: MRN, subscriber/member number, account number,
encounter CSN, licence number, device serial, VIN. Fills the value's character mask:

```
1000001            ->  8156204
0100002            ->  0473819     (zero padding and width preserved)
1AB2CD3EF45        ->  7QT2XN8KP41
100000000001AB02   ->  418266915073BJ72
100003-04          ->  920377-41
```

Prefer `id` whenever you're unsure about a non-name, non-date identifier. It is
shape-exact and always safe.

### `ssn`, `phone`, `email`

These use ranges reserved for fiction, so a generated value provably cannot refer to a
real person or reach a real mailbox:

- `ssn` — area number 900-999, never issued.
- `phone` — the 555-01xx fictional exchange. Mask preserved, so `(601) 200-3000` →
  `(233) 555-0166`.
- `email` — local part is rebuilt from the fake persona in the same style
  (`first.last`, `flast`, `flast88`), domain forced to `example.com`/`.org`/`.net` per
  RFC 2606.

The email **domain is deliberately not shape-preserved.** Every other field keeps its
shape, but a preserved domain is a live route to a real organisation, and no amount of
fidelity justifies that. `verify.py` knows this and checks structure rather than length
for these.

### `zip`, `city`, `address`

`zip` replaces the whole value rather than truncating to three digits. Safe Harbor
permits keeping the first three, but truncation changes the value's length — the exact
shape drift this skill exists to prevent — and full replacement is strictly more
protective.

`address` keeps structural words verbatim (`APT`, `STE`, `N`, `RD`, `CR`, `HWY`) and the
digit count of house and route numbers, replacing only the naming words:

```
1420 N MAPLE ST APT 3      ->  6073 N CEDAR ST APT 2
890 OLD MILL RD STE 200    ->  602 ELM WALNUT RD STE 811
12 CR 431                  ->  19 CR 501
```

`city` draws from a pool of invented place names; length may differ, since padding a
place name to an exact width produces visible gibberish in a human-read column.

### `age`

Caps at 90, mirroring Safe Harbor's treatment of ages over 89 as identifying — very old
patients are rare enough to single out. Other ages become a plausible value of the same
width.

### `url`, `ip`

`url` keeps the scheme and path structure, pointing at `example.com`. `ip` uses the
RFC 5737 documentation range `203.0.113.0/24`, or `2001:db8::/32` for IPv6.

## Worked example: pipe-delimited billing extract

For a file with headers
`Hospital|Surgical Location|MRN #|DOS|PAT_NAME|DOB|Primary Payor|Primary Subscriber Number|Scheduled Encounter Type|Secondary Payor|Secondary Subscriber Number|SURGEON|ORP|CPT Code|PROC_NAME|ICD10 CM|Deceased|SMS Consent Status|EncounterCSN|LATERALITY`:

```json
{
  "header_row": 0,
  "identity_key": ["MRN #"],
  "date_offset_range": [-540, 540],
  "delimiter": "|",
  "columns": [
    {"name": "MRN #", "type": "id"},
    {"name": "DOS", "type": "date"},
    {"name": "PAT_NAME", "type": "name", "name_order": "last_first"},
    {"name": "DOB", "type": "date"},
    {"name": "Primary Subscriber Number", "type": "id"},
    {"name": "Secondary Subscriber Number", "type": "id"},
    {"name": "EncounterCSN", "type": "id"}
  ]
}
```

Seven columns redacted; thirteen preserved. `SURGEON` and `ORP` are treating providers,
`Hospital`/`Surgical Location` identify the facility, and the rest is clinical or
administrative vocabulary — all of it is what makes this file useful as a fixture, and
none of it identifies a patient.

## Worked example: multi-sheet workbook

One plan covers every sheet; entries apply wherever a matching header appears. Because
`MRN` is the identity key on both tabs, a patient's fake MRN agrees across them — so
joins still work.

```json
{
  "header_row": 0,
  "identity_key": ["MRN"],
  "sheets": {
    "Lookup Tables": {"skip": true},
    "Summary": {"header_row": 3}
  },
  "columns": [
    {"name": "MRN", "aliases": ["Patient MRN", "MRN #"], "type": "id"},
    {"name": "First Name", "type": "name", "name_part": "first"},
    {"name": "MI", "type": "name", "name_part": "middle"},
    {"name": "Last Name", "type": "name", "name_part": "last"},
    {"name": "DOB", "type": "date"},
    {"name": "DOS", "type": "date"},
    {"name": "SSN", "type": "ssn"},
    {"name": "Home Phone", "aliases": ["Mobile Phone", "Fax"], "type": "phone"},
    {"name": "Email", "type": "email"},
    {"name": "Street Address", "type": "address"},
    {"name": "City", "type": "city"},
    {"name": "ZIP", "type": "zip"},
    {"name": "Age", "type": "age"},
    {"name": "Encounter CSN", "type": "id"}
  ]
}
```

Split name columns resolve to one persona, so `ALPHA` / `A` / `TEST` becomes
`ADELA` / `D` / `YOST` — a coherent person, not three unrelated words.

## Awkward cases

**An ID column that is also a foreign key.** No special handling needed: a given real
value always maps to the same fake one, so `MRN` on the Patients tab and `MRN` on the
Encounters tab stay joinable. Just list the column on both.

**A date column that isn't about a person.** A code's effective date or a report
generation date isn't PHI, and shifting it would corrupt data for no benefit. Record the
decision rather than dropping the column silently:

```json
{"name": "Effective Date", "type": "keep"}
```

The values are preserved either way, but an omitted date column trips verify's
PHI-shaped-column check (a date-shaped column with a non-personal header is exactly
the `REVIEW` case the profiler flags for you to decide). Writing `keep` is how the
decision gets recorded instead of re-litigated on every run.

**A middle-name column holding sometimes a name, sometimes an initial.** Use
`"name_part": "middle"`. Each cell is handled on its own, so full names stay full and
initials stay single letters — and the per-row mix is preserved.

**Numeric ID columns in Excel.** Handled automatically: a numeric cell comes back
numeric, so Excel's sorting, formatting and aggregation behave the same. Never convert
these to text by hand.

**A column that is blank throughout.** Leave it out. Empty cells stay empty regardless,
since blankness is part of the file's shape.

**A free-text note column.** The riskiest case, because it can contain anything. Either
give it a type (`id` will mask-fill the whole thing, destroying readability but
guaranteeing safety) or read enough of the column to be confident, and tell the user
which you did. Don't leave it unexamined.

**A header appearing twice.** Both instances get the same treatment, since matching is
by name. If they need different types, rename one first or split the work per sheet.
