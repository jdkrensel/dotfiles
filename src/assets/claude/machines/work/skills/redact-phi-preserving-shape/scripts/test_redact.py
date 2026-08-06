"""End-to-end tests: redact a file, then assert the verifier passes it.

Run:  uv run --with pytest --with openpyxl python -m pytest test_redact.py -q

The strongest signal available is that redact.py's output survives verify.py's own
checks, so most of these tests build a small file, run both, and require a clean
report. The edge cases are the ones that quietly corrupt files in production:
unusual delimiters, quoted fields containing the delimiter, blank lines, ragged
rows, non-UTF-8 encodings and CRLF endings.
"""

from __future__ import annotations

import csv
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HERE / script), *args],
                          capture_output=True, text=True)


def write_plan(tmp: Path, **over) -> Path:
    plan = {
        "header_row": 0,
        "identity_key": ["MRN"],
        "date_offset_range": [-400, 400],
        "columns": [
            {"name": "MRN", "type": "id"},
            {"name": "Name", "type": "name", "name_order": "last_first"},
            {"name": "DOB", "type": "date"},
        ],
    }
    plan.update(over)
    p = tmp / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def make_csv(tmp: Path, rows: list[list[str]], delim="|", newline="\r\n",
             encoding="utf-8", name="in.csv", quoting=csv.QUOTE_MINIMAL) -> Path:
    buf = io.StringIO()
    csv.writer(buf, delimiter=delim, lineterminator=newline, quoting=quoting).writerows(rows)
    p = tmp / name
    p.write_bytes(buf.getvalue().encode(encoding))
    return p


# Invented patients. Never seed a fixture from a real extract: these files are
# committed, and git history cannot be redacted after the fact.
BASE = [
    ["MRN", "Name", "DOB", "Payor"],
    ["0012345", "TEST,ALPHA A", "01/02/1950", "MEDICARE"],
    ["0098765", "MOCKS,BRAVO DELTA", "03/04/1960", "VA"],
    ["0012345", "TEST,ALPHA A", "01/02/1950", "MEDICARE"],
    ["0055512", "SAMPLE,ECHO", "05/06/1970", "UHC"],
]


def redact_and_verify(tmp: Path, src: Path, plan: Path, extra_verify=()) -> str:
    out = tmp / f"{src.stem}_REDACTED{src.suffix}"
    r = run("redact.py", "--plan", str(plan), "--in", str(src), "--out", str(out))
    assert r.returncode == 0, r.stderr
    v = run("verify.py", "--original", str(src), "--redacted", str(out),
            "--plan", str(plan), *extra_verify)
    assert v.returncode == 0, v.stdout + v.stderr
    return out.read_bytes().decode("utf-8", "replace")


# -- delimited round trips ---------------------------------------------------

@pytest.mark.parametrize("delim", ["|", ",", "\t", ";"])
def test_delimiters(tmp_path, delim):
    src = make_csv(tmp_path, BASE, delim=delim)
    redact_and_verify(tmp_path, src, write_plan(tmp_path))


@pytest.mark.parametrize("newline", ["\r\n", "\n"])
def test_newline_styles(tmp_path, newline):
    src = make_csv(tmp_path, BASE, newline=newline)
    redact_and_verify(tmp_path, src, write_plan(tmp_path))


@pytest.mark.parametrize("encoding", ["utf-8", "cp1252"])
def test_encodings(tmp_path, encoding):
    rows = [r[:] for r in BASE]
    rows[1][1] = "SAMPLE,ROMEO"  # plain ASCII keeps cp1252 round-trip unambiguous
    src = make_csv(tmp_path, rows, encoding=encoding)
    redact_and_verify(tmp_path, src, write_plan(tmp_path))


def test_bom_is_preserved(tmp_path):
    src = tmp_path / "bom.csv"
    body = "MRN|Name|DOB|Payor\r\n0012345|TEST,ALPHA A|01/02/1950|MEDICARE\r\n"
    src.write_bytes(b"\xef\xbb\xbf" + body.encode())
    out = redact_and_verify(tmp_path, src, write_plan(tmp_path))
    assert (tmp_path / "bom_REDACTED.csv").read_bytes().startswith(b"\xef\xbb\xbf")


def test_quoted_field_containing_delimiter(tmp_path):
    rows = [
        ["MRN", "Name", "DOB", "Note"],
        ["0012345", "TEST,ALPHA A", "01/02/1950", "pain, worsening"],
    ]
    src = make_csv(tmp_path, rows, delim=",", quoting=csv.QUOTE_MINIMAL)
    text = redact_and_verify(tmp_path, src, write_plan(tmp_path))
    assert '"pain, worsening"' in text  # preserved verbatim, still quoted


def test_blank_lines_preserved(tmp_path):
    src = tmp_path / "blanks.csv"
    src.write_bytes(b"MRN|Name|DOB\r\n0012345|TEST,ALPHA A|01/02/1950\r\n\r\n0098765|MOCKS,BRAVO|03/04/1960\r\n")
    out = tmp_path / "blanks_REDACTED.csv"
    r = run("redact.py", "--plan", str(write_plan(tmp_path)), "--in", str(src), "--out", str(out))
    assert r.returncode == 0, r.stderr
    assert src.read_bytes().count(b"\r\n") == out.read_bytes().count(b"\r\n")


def test_ragged_rows_do_not_crash(tmp_path):
    src = tmp_path / "ragged.csv"
    src.write_bytes(b"MRN|Name|DOB|Payor\r\n0012345|TEST,ALPHA A|01/02/1950\r\n0098765|MOCKS,BRAVO|03/04/1960|VA|EXTRA\r\n")
    out = tmp_path / "ragged_REDACTED.csv"
    r = run("redact.py", "--plan", str(write_plan(tmp_path)), "--in", str(src), "--out", str(out))
    assert r.returncode == 0, r.stderr
    orig_widths = [len(l.split(b"|")) for l in src.read_bytes().strip().split(b"\r\n")]
    new_widths = [len(l.split(b"|")) for l in out.read_bytes().strip().split(b"\r\n")]
    assert orig_widths == new_widths


def test_empty_cells_stay_empty(tmp_path):
    rows = [["MRN", "Name", "DOB", "Payor"], ["0012345", "", "", "SELF-PAY"]]
    src = make_csv(tmp_path, rows)
    text = redact_and_verify(tmp_path, src, write_plan(tmp_path))
    assert text.strip().endswith("0" + text.strip().split("|")[0][1:] + "|||SELF-PAY") or "|||SELF-PAY" in text


def test_header_only_file(tmp_path):
    src = make_csv(tmp_path, [["MRN", "Name", "DOB"]])
    redact_and_verify(tmp_path, src, write_plan(tmp_path))


def test_non_phi_columns_are_untouched(tmp_path):
    src = make_csv(tmp_path, BASE)
    text = redact_and_verify(tmp_path, src, write_plan(tmp_path))
    for payor in ["MEDICARE", "VA", "UHC"]:
        assert payor in text


# -- consistency and determinism --------------------------------------------

def test_same_subject_gets_same_fake(tmp_path):
    """Rows 1 and 3 share an MRN, so they must land on one identity."""
    src = make_csv(tmp_path, BASE)
    text = redact_and_verify(tmp_path, src, write_plan(tmp_path))
    rows = [r for r in csv.reader(io.StringIO(text), delimiter="|") if r]
    body = rows[1:]
    assert body[0] == body[2]


def test_deterministic_for_a_given_salt(tmp_path):
    """Determinism is opt-in: it needs a salt, because the default is random."""
    src = make_csv(tmp_path, BASE)
    plan = write_plan(tmp_path)
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    for o in (a, b):
        assert run("redact.py", "--plan", str(plan), "--in", str(src),
                   "--out", str(o), "--salt", "fixed").returncode == 0
    assert a.read_bytes() == b.read_bytes()


def test_default_salt_is_random_per_run(tmp_path):
    """A salt baked into the script would be a re-identification key in the repo."""
    src = make_csv(tmp_path, BASE)
    plan = write_plan(tmp_path)
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    for o in (a, b):
        assert run("redact.py", "--plan", str(plan), "--in", str(src), "--out", str(o)).returncode == 0
    assert a.read_bytes() != b.read_bytes()


def test_salt_changes_output(tmp_path):
    src = make_csv(tmp_path, BASE)
    plan = write_plan(tmp_path)
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    run("redact.py", "--plan", str(plan), "--in", str(src), "--out", str(a), "--salt", "one")
    run("redact.py", "--plan", str(plan), "--in", str(src), "--out", str(b), "--salt", "two")
    assert a.read_bytes() != b.read_bytes()


def test_date_interval_preserved_per_subject(tmp_path):
    rows = [
        ["MRN", "Name", "DOB", "DOS"],
        ["0012345", "TEST,ALPHA A", "01/02/1950", "03/01/2026"],
        ["0012345", "TEST,ALPHA A", "01/02/1950", "03/31/2026"],
    ]
    src = make_csv(tmp_path, rows)
    plan = write_plan(tmp_path, columns=[
        {"name": "MRN", "type": "id"},
        {"name": "Name", "type": "name", "name_order": "last_first"},
        {"name": "DOB", "type": "date"},
        {"name": "DOS", "type": "date"},
    ])
    text = redact_and_verify(tmp_path, src, plan)
    import datetime
    out = [r for r in csv.reader(io.StringIO(text), delimiter="|") if r][1:]
    d = lambda s: datetime.datetime.strptime(s, "%m/%d/%Y").date()
    assert (d(out[0][3]) - d(out[0][2])).days == (datetime.date(2026, 3, 1) - datetime.date(1950, 1, 2)).days
    assert (d(out[1][3]) - d(out[0][3])).days == 30  # visit spacing intact


def test_verifier_catches_an_unredacted_column(tmp_path):
    """The real workflow: verify against the SAME plan that did the redaction.

    Checking against a fuller plan proves nothing, because no user has a fuller
    plan lying around -- if they did, they would have redacted with it. The plan is
    the only thing verify is given, so it has to form its own opinion of what PHI
    looks like or it cannot catch the omission at all.
    """
    src = make_csv(tmp_path, BASE)
    out = tmp_path / "partial.csv"
    partial = tmp_path / "partial_plan.json"
    partial.write_text(json.dumps({
        "header_row": 0, "identity_key": ["MRN"],
        "columns": [{"name": "MRN", "type": "id"}],  # Name and DOB left in place
    }))
    assert run("redact.py", "--plan", str(partial), "--in", str(src), "--out", str(out)).returncode == 0
    v = run("verify.py", "--original", str(src), "--redacted", str(out), "--plan", str(partial))
    assert v.returncode != 0, v.stdout
    assert "missing from the plan" in v.stdout
    assert "Name" in v.stdout or "DOB" in v.stdout


def test_reviewed_non_phi_column_can_be_recorded_as_keep(tmp_path):
    """A false positive is resolved by recording the decision, not by loosening."""
    rows = [["MRN", "Name", "DOB", "Ref"],
            ["0012345", "TEST,ALPHA A", "01/02/1950", "AB-40021"],
            ["0098765", "MOCKS,BRAVO DELTA", "03/04/1960", "AB-40022"]]
    src = make_csv(tmp_path, rows)
    plan = write_plan(tmp_path, columns=[
        {"name": "MRN", "type": "id"},
        {"name": "Name", "type": "name", "name_order": "last_first"},
        {"name": "DOB", "type": "date"},
        {"name": "Ref", "type": "keep"},
    ])
    text = redact_and_verify(tmp_path, src, plan)
    assert "AB-40021" in text  # acknowledged, so preserved byte-for-byte


def test_banner_rows_above_the_header_do_not_defeat_redaction(tmp_path):
    """Sniffing the delimiter off a banner line silently copies the file through."""
    src = tmp_path / "banner.csv"
    src.write_bytes(
        b"Report for TEST,ALPHA A -- generated 2026-01-02\r\n"
        b"MRN|Name|DOB\r\n"
        b"0012345|TEST,ALPHA A|01/02/1950\r\n"
    )
    out = tmp_path / "banner_REDACTED.csv"
    plan = write_plan(tmp_path, header_row=1)
    assert run("redact.py", "--plan", str(plan), "--in", str(src), "--out", str(out)).returncode == 0
    text = out.read_bytes().decode()
    assert "0012345|TEST,ALPHA A" not in text, text  # the data row was redacted
    assert text.count("|") == src.read_bytes().decode().count("|")  # shape intact


def test_draft_plan_from_inspect_file_round_trips(tmp_path):
    """The documented workflow end to end: profile -> set identity_key -> redact -> verify.

    inspect_file and verify both classify columns, and if they disagree the tool
    fails on a plan it generated itself. Only an end-to-end run catches that.
    """
    rows = [
        ["MRN", "Patient Name", "DOB", "Payor", "CPT Code", "Effective Date"],
        ["0012345", "TEST,ALPHA A", "01/02/1950", "MEDICARE", "27447", "01/01/2020"],
        ["0098765", "MOCKS,BRAVO DELTA", "03/04/1960", "VA", "27130", "01/01/2020"],
        ["0055512", "SAMPLE,ECHO", "05/06/1970", "UHC", "27447", "01/01/2020"],
    ]
    src = make_csv(tmp_path, rows)
    draft = tmp_path / "draft.json"
    assert run("inspect_file.py", str(src), "--emit-plan", str(draft)).returncode == 0

    plan = json.loads(draft.read_text())
    plan["identity_key"] = ["MRN"]  # the one edit the workflow always requires
    for entry in plan["columns"]:
        if entry["type"] == "REVIEW":  # a human resolves these; here they are code dates
            entry["type"] = "keep"
    draft.write_text(json.dumps(plan))

    text = redact_and_verify(tmp_path, src, draft)
    assert "MEDICARE" in text and "27447" in text  # clinical vocabulary preserved
    assert "TEST,ALPHA A" not in text


def test_pre_header_rows_are_scanned_for_leaks(tmp_path):
    """A banner is copied through verbatim, so nothing else ever inspects it."""
    src = tmp_path / "banner.csv"
    src.write_bytes(
        b"Report for TEST,ALPHA A -- generated 2026-01-02\r\n"
        b"MRN|Name|DOB\r\n"
        b"0012345|TEST,ALPHA A|01/02/1950\r\n"
    )
    out = tmp_path / "banner_REDACTED.csv"
    plan = write_plan(tmp_path, header_row=1)
    assert run("redact.py", "--plan", str(plan), "--in", str(src), "--out", str(out)).returncode == 0
    v = run("verify.py", "--original", str(src), "--redacted", str(out), "--plan", str(plan))
    assert v.returncode != 0, v.stdout
    assert "survives" in v.stdout


def test_fully_quoted_file_stays_fully_quoted(tmp_path):
    """QUOTE_ALL is shape: verify parses both files identically and cannot see it."""
    src = make_csv(tmp_path, BASE, delim=",", quoting=csv.QUOTE_ALL)
    text = redact_and_verify(tmp_path, src, write_plan(tmp_path))
    first = text.splitlines()[1]
    assert first.startswith('"') and first.endswith('"'), first
    assert '",' in first, first


def test_plan_that_matches_no_header_fails_loudly(tmp_path):
    """A renamed column must not produce an unredacted file with a green report."""
    src = make_csv(tmp_path, BASE)
    out = tmp_path / "nomatch.csv"
    plan = write_plan(tmp_path, columns=[{"name": "PatientMRN", "type": "id"}])
    assert run("redact.py", "--plan", str(plan), "--in", str(src), "--out", str(out)).returncode == 0
    v = run("verify.py", "--original", str(src), "--redacted", str(out), "--plan", str(plan))
    assert v.returncode != 0, v.stdout
    assert "matched a header" in v.stdout


# -- Excel -------------------------------------------------------------------

def test_excel_round_trip(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    import datetime

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pts"
    ws.append(["MRN", "Name", "DOB", "Payor"])
    ws.append(["0012345", "TEST,ALPHA A", datetime.date(1950, 1, 2), "MEDICARE"])
    ws.append(["0098765", "MOCKS,BRAVO DELTA", datetime.date(1960, 3, 4), "VA"])
    w2 = wb.create_sheet("Enc")
    w2.append(["MRN", "CPT"])
    w2.append(["0012345", "27447"])
    w2["D1"] = "=COUNTA(A2:A3)"
    src = tmp_path / "wb.xlsx"
    wb.save(src)

    out = tmp_path / "wb_REDACTED.xlsx"
    plan = write_plan(tmp_path)
    assert run("redact.py", "--plan", str(plan), "--in", str(src), "--out", str(out)).returncode == 0
    v = run("verify.py", "--original", str(src), "--redacted", str(out), "--plan", str(plan))
    assert v.returncode == 0, v.stdout

    rb = openpyxl.load_workbook(out)
    assert rb.sheetnames == ["Pts", "Enc"]
    assert rb["Enc"]["D1"].value == "=COUNTA(A2:A3)"          # formula intact
    assert isinstance(rb["Pts"]["C2"].value, (datetime.date, datetime.datetime))
    assert rb["Pts"]["D2"].value == "MEDICARE"                # non-PHI intact
    # Same MRN in both tabs resolves to the same fake.
    assert rb["Pts"]["A2"].value == rb["Enc"]["A2"].value


def test_excel_document_properties_are_scrubbed(tmp_path):
    """lastModifiedBy on a client workbook is routinely a real person's name."""
    openpyxl = pytest.importorskip("openpyxl")
    import datetime

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["MRN", "Name", "DOB"])
    ws.append(["0012345", "TEST,ALPHA A", datetime.date(1950, 1, 2)])
    wb.properties.creator = "Real Person"
    wb.properties.lastModifiedBy = "Another Real Person"
    wb.properties.title = "Patient List"
    src = tmp_path / "props.xlsx"
    wb.save(src)

    out = tmp_path / "props_REDACTED.xlsx"
    plan = write_plan(tmp_path)
    assert run("redact.py", "--plan", str(plan), "--in", str(src), "--out", str(out)).returncode == 0

    rb = openpyxl.load_workbook(out)
    assert not rb.properties.creator
    assert not rb.properties.lastModifiedBy
    assert not rb.properties.title
    v = run("verify.py", "--original", str(src), "--redacted", str(out), "--plan", str(plan))
    assert v.returncode == 0, v.stdout


def test_legacy_xls_is_rejected_not_mangled(tmp_path):
    """openpyxl cannot read BIFF; failing clearly beats a confusing zip error."""
    src = tmp_path / "old.xls"
    src.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")  # OLE2 magic
    r = run("redact.py", "--plan", str(write_plan(tmp_path)), "--in", str(src),
            "--out", str(tmp_path / "out.xls"))
    assert r.returncode != 0
    assert ".xls" in r.stderr and "not supported" in r.stderr


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
