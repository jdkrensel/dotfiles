"""Tests for the shape-preservation primitives.

Run:  uv run --with pytest python -m pytest test_shapes.py -q

These cover the properties that are easy to break and expensive to notice: mask
equality, name-template equality, date-format round-tripping, and the invariant
that a generated value never equals the value it replaced.
"""

from __future__ import annotations

import datetime

import pytest

from shapes import (
    Persona,
    _rand,
    fake_age,
    fake_email,
    fake_phone,
    fake_ssn,
    fill_mask,
    mask_of,
    name_template,
    parse_date,
    render_name,
    shift_date,
)


def rng(tag="t"):
    return _rand("test-salt", tag)


# -- masks ------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("1AB2CD3EF45", "9AA9AA9AA99"),
    ("100000000001AB02", "999999999999AA99"),
    ("100003-04", "999999-99"),
    ("TEST,ALPHA A", "AAAA,AAAAA A"),
    ("Opt In", "Aaa Aa"),
    ("M17.11~Z96.651", "A99.99~A99.999"),
    ("", ""),
])
def test_mask_of(value, expected):
    assert mask_of(value) == expected


@pytest.mark.parametrize("value", [
    "1000001", "0100002", "1AB2CD3EF45", "X1234567890", "100000000001AB02",
    "100003-04", "XYZ100000005B", "1000000006", "00012",
])
def test_fill_mask_preserves_mask(value):
    out = fill_mask(mask_of(value), rng(value), value)
    assert mask_of(out) == mask_of(value)
    assert len(out) == len(value)


def test_fill_mask_keeps_leading_zeros():
    """Zero padding is format, not identity; consumers may depend on the width."""
    for v in ["0100002", "0010000007", "00012"]:
        out = fill_mask(mask_of(v), rng(v), v)
        assert out.startswith("0" * (len(v) - len(v.lstrip("0"))))


# -- names ------------------------------------------------------------------

@pytest.mark.parametrize("value,expected", [
    ("TEST,ALPHA A", "W,W I"),
    ("MOCKS,BRAVO DELTA", "W,W W"),
    ("SAMPLE,ECHO", "W,W"),
    ("TESTCO,FOXTROT GOLF JR.", "W,W W S"),
    ("VAN DER TEST,HOTEL INDIA", "W W W,W W"),
    ("EXAMPLE, JULIET T.", "W, W I"),  # separator kept verbatim
])
def test_name_template(value, expected):
    assert name_template(value) == expected


# Deliberately invented names, chosen to cover every template the renderer handles:
# initials, multi-word surnames, suffixes, mixed case and apostrophes. Never use
# values lifted from a real file here -- a fixture is forever, and git history is
# not redactable.
NAMES = [
    "TEST,ALPHA A", "MOCKS,BRAVO DELTA", "SAMPLE,ECHO", "TESTCO,FOXTROT GOLF JR.",
    "VAN DER TEST,HOTEL INDIA", "FIXTURE,KILO L", "MOCKUP,LIMA L", "SAMPLER,MIKE NOVEMBER OSCAR",
    "Sample, Mary Jane", "o'sample,quebec p",
]


@pytest.mark.parametrize("value", NAMES)
def test_render_name_preserves_template_and_mask(value):
    p = Persona(rng(value), 7, 8)
    out = render_name(value, p)
    assert name_template(out) == name_template(value), f"{value!r} -> {out!r}"
    assert mask_of(out) == mask_of(value), f"{value!r} -> {out!r}"


@pytest.mark.parametrize("value", NAMES)
def test_render_name_changes_every_word(value):
    p = Persona(rng(value), 7, 8)
    out = render_name(value, p)
    src_words = {w.rstrip(".").upper() for w in value.replace(",", " ").split() if len(w.rstrip(".")) > 1}
    out_words = {w.rstrip(".").upper() for w in out.replace(",", " ").split() if len(w.rstrip(".")) > 1}
    # Suffixes are intentionally preserved; every other word must be new.
    assert not (src_words & out_words) - {"JR", "SR", "II", "III", "IV"}


def test_render_name_no_repeated_words():
    """A person is not called "EDITH EDITH"; sibling slots must differ."""
    for v in ["MOCKS,BRAVO DELTA", "SAMPLER,MIKE NOVEMBER OSCAR"]:
        out = render_name(v, Persona(rng(v), 7, 8))
        words = [w for w in out.replace(",", " ").split() if len(w) > 1]
        assert len(words) == len(set(words)), out


def test_initial_never_becomes_a_suffix():
    """A middle initial of "V" would re-read as a generational suffix."""
    for i in range(60):
        v = "FIXTURE,KILO L"
        out = render_name(v, Persona(rng(f"seed{i}"), 4, 7))
        assert name_template(out) == "W,W I", out


def test_persona_is_stable_across_calls():
    a = render_name("TEST,ALPHA A", Persona(rng("subj-1"), 5, 4))
    b = render_name("TEST,ALPHA A", Persona(rng("subj-1"), 5, 4))
    assert a == b


def test_persona_differs_between_subjects():
    a = render_name("TEST,ALPHA A", Persona(rng("subj-1"), 5, 4))
    b = render_name("TEST,ALPHA A", Persona(rng("subj-2"), 5, 4))
    assert a != b


def test_forbidden_words_are_avoided():
    p = Persona(rng("x"), 5, 5, forbidden={"AGNES", "BASIL", "CAROL", "CLARK", "DAVIS"})
    out = render_name("CLARK,AGNES", p).upper()
    assert "AGNES" not in out and "CLARK" not in out


# -- dates ------------------------------------------------------------------

@pytest.mark.parametrize("value", [
    "01/02/1950", "3/7/51", "1950-01-02", "01.02.1950", "19500102",
    "12-Jan-1950", "12 January 1950", "2026-03-01 14:22:00",
])
def test_parse_and_reshift_preserves_format(value):
    p = parse_date(value)
    assert p is not None, value
    out = shift_date(p, 100)
    assert mask_of(out) == mask_of(value), f"{value!r} -> {out!r}"
    assert out != value


@pytest.mark.parametrize("value", ["not a date", "", "abc", "M17.11", "27447", "Right"])
def test_non_dates_rejected(value):
    assert parse_date(value) is None


@pytest.mark.parametrize("value", [
    "12 January 1950", "1 May 1950", "30 September 1950", "5 June 1950", "18 October 1948",
])
@pytest.mark.parametrize("offset", [1, 100, -100, 233, 400])
def test_spelled_out_month_keeps_its_width(value, offset):
    """Month names run 3-9 characters, so a shift can silently resize the field."""
    out = shift_date(parse_date(value), offset)
    assert mask_of(out) == mask_of(value), f"{value!r} + {offset} -> {out!r}"
    assert out != value


def test_shift_preserves_interval():
    """Age at surgery and visit ordering must survive the shift."""
    dob, dos = parse_date("01/02/1950"), parse_date("03/01/2026")
    off = 233
    nd = datetime.datetime.strptime(shift_date(dob, off), "%m/%d/%Y").date()
    ns = datetime.datetime.strptime(shift_date(dos, off), "%m/%d/%Y").date()
    orig = datetime.date(2026, 3, 1) - datetime.date(1950, 1, 2)
    assert (ns - nd) == orig


def test_leap_day_does_not_crash():
    p = parse_date("02/29/2024")
    assert p is not None
    for off in (1, 365, -365, 1461):
        assert mask_of(shift_date(p, off)) == "99/99/9999"


def test_two_digit_year_stays_two_digit():
    assert shift_date(parse_date("3/7/51"), 40).count("/") == 2
    assert len(shift_date(parse_date("03/07/51"), 40)) == len("03/07/51")


# -- typed identifiers ------------------------------------------------------

def test_fake_ssn_is_in_unissued_range():
    for i in range(20):
        out = fake_ssn("123-45-6789", rng(f"s{i}"))
        assert mask_of(out) == mask_of("123-45-6789")
        assert out.startswith("9")


def test_fake_phone_uses_reserved_555_range():
    for fmt in ["(601) 555-0123", "601-555-0123", "6015550123", "+1 601 555 0123"]:
        out = fake_phone(fmt, rng(fmt))
        assert mask_of(out) == mask_of(fmt)
        digits = "".join(c for c in out if c.isdigit())
        assert digits[-7:-4] == "555" and digits[-4:-2] == "01", out


def test_fake_email_uses_reserved_domain():
    out = fake_email("alpha.test@oldclinic.invalid", rng("e"), Persona(rng("p"), 5, 4))
    assert out.endswith(("example.com", "example.org", "example.net"))
    assert "oldclinic" not in out


def test_fake_age_caps_at_90():
    assert fake_age("94", rng("a")) == "90"
    for i in range(20):
        v = fake_age("67", rng(f"a{i}"))
        assert v.isdigit() and 18 <= int(v) <= 89


@pytest.mark.parametrize("value", ["94", "102", "0102", "90", "090"])
def test_fake_age_cap_preserves_mask(value):
    """Capping must not change the width, or verification becomes unpassable."""
    out = fake_age(value, rng("a"))
    assert mask_of(out) == mask_of(value), f"{value!r} -> {out!r}"
    assert int(out) <= 90, out
    assert out != value, "an unchanged cell fails verification with no recourse"


def test_fake_age_never_returns_the_original():
    """A ~72-value space collides often; a collision fails the 'cell changed' check."""
    for i in range(200):
        src = str(18 + (i % 72))
        assert fake_age(src, rng(f"age{i}")) != src


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
