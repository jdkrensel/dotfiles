"""Shape-preserving fake-value generation.

The contract this module implements: a fake value must be *indistinguishable in
shape* from the real one it replaces. Same length, same character classes in the
same positions, same punctuation, same case style, same date format, same token
template. Only the identity underneath changes.

Why shape fidelity matters: these files are used to test ingest pipelines. A
parser that splits on a comma, a regex that expects 7 digits, a date reader that
assumes MM/DD/YYYY, a dedupe rule keyed on repeated MRNs -- all of them behave
differently if the redacted file's shape drifts. A redacted file that doesn't
exercise the same code paths as the real one is worse than useless, because it
gives false confidence.

Two ideas do most of the work here:

1. *Masks.* Reduce a value to its character-class skeleton ("1AB2CD3EF45" ->
   "9AA9AA9AA99"), then generate a new value that fills that exact skeleton.
   This handles every opaque identifier -- MRN, subscriber number, account
   number, CSN -- generically, with no per-column rules.

2. *Per-row template preservation.* Rather than measuring that names are 20%
   "FIRST M" and then sampling to hit 20%, preserve each row's own template.
   The distribution then matches the source exactly and for free, with no
   sampling error. Same trick for date formats and mask variants.
"""

from __future__ import annotations

import datetime
import hashlib
import re
import unicodedata

# Word pools. Deliberately ordinary, obviously-fake-in-aggregate names spanning a
# range of lengths so a generated value can match the visual density of the value
# it replaces.
SURNAMES = [
    "ABBOT", "ABBOTT", "ADAMS", "ALDRICH", "ALDRIDGE", "BAKER", "BARNES", "BARNETT",
    "BELL", "BENSON", "BLACKSTONE", "BLACKWOOD", "BLAIR", "BRADLEY",
    "BRIGHTMAN", "CALHOUN", "CALLOWAY", "CARRINGTON", "CARTER", "CASTELLAN", "CHANDLER",
    "CLARK", "CONWAY", "COOK", "CRANDALL", "CROSS", "CRUZ", "DAVIS", "DAWSON",
    "DEAN", "DELANEY", "DEVEREAUX", "DIAZ", "DRISCOLL", "DUNNE", "EASTERLY", "ELDER", "EVANS", "FAIRBANKS", "FAIRFAX", "FIELD", "FLETCHER", "FONTAINE", "FORD",
    "FOSTER", "FROST", "FRYE", "GALLOWAY", "GARRISON", "GOODWIN", "GORDON", "GRANT",
    "GRANTHAM", "GRAY", "HALE", "HALEY", "HALSTEAD", "HARPER", "HAWTHORNE",
    "HAYES", "HOLBROOK", "HOLLAND", "HOLT", "HOPKINS", "HUNT", "INGRAM", "IRELAND",
    "IRWIN", "JONES", "JORDAN", "KANE", "KELLER", "KERR", "KINCAID", "LANE",
    "LATIMER", "LAWSON", "LOCKHART", "LOGAN", "LOWE", "MACK", "MADISON", "MARLOWE",
    "MEADE", "MERCER", "MONTAGUE", "MOORE", "MORROW", "MOSS",
    "NASH", "NEWSOME", "NOBLE", "NORTON", "OSBORNE", "OSGOOD", "OWENS", "PAGE",
    "PARKER", "PENDERGAST", "PENDLETON", "PERRY", "PIKE", "PRESTON", "PRICE",
    "QUAYLE", "QUINN", "QUINTANA", "RADCLIFFE", "REDDING", "REEVE", "REID",
    "RIVENBARK", "SANDERSON", "SHAW", "SHELTON", "SLOAN", "SNOW", "STANFIELD",
    "STARK", "SUMNER", "SUTHERLAND", "TATE", "THORNBURY", "THORNTON", "THURMAN",
    "TOBIN", "TODD", "TURNER", "UNDERWOOD", "VANCE", "VANDERBILT", "VAUGHN",
    "VOSS", "WAINWRIGHT", "WALKER", "WARE", "WEBER", "WEBSTER", "WHITAKER",
    "WHITLEY", "WOLF", "YOST", "YOUNG",
    "ARMISTEADLY", "BRECKENRIDGES", "BRIGHTWATER", "CARPENTIERE", "CHRISTOPHERS", "CHRISTOPHERSON",
    "CHRISTOPHERSONS", "FEATHERSTON", "FEATHERSTONE", "HOLLINGSWOOD", "HOLLINGSWORTH", "HOLLINGSWORTHE",
    "HOLLINGSWORTHES", "HOLLINGWOOD", "MERRIWEATHER", "MONTGOMERIE", "MONTGOMERYSHI", "WETHERINGLY",
    "WINTERBOTHAM", "WINTERBOTHAMLY", "WINTERBOTHAMS",
]

GIVEN_NAMES = [
    "ABE", "ABEL", "ABIGAIL", "ADA", "ADELA", "ADRIENNE", "AGNES", "ALBERT",
    "ALESSANDRA", "ALEXANDRA", "ALMA", "ANA", "ANTOINETTE", "ARNOLD", "AUGUSTA", "AUGUSTUS",
    "BASIL", "BEATRICE", "BENEDICT", "BERNADETTE", "BERNARD", "BERTHA", "BESS", "BEULAH",
    "BRUCE", "BURT", "CAROL", "CASSANDRA", "CECILE", "CHARLOTTE", "CLARA", "CLARENCE",
    "CLEMENTINE", "CLEO", "CLIFTON", "CONRAD", "CORA", "CORNELIUS", "DALE",
    "DELIA", "DEMETRIA", "DENNIS", "DORIS", "DOROTHY", "DREW", "EDGAR", "EDMUND",
    "EDNA", "ELMER", "ELSA", "EMMANUEL", "ERIC", "ERNESTINE", "EUNICE",
    "EVA", "FAYE", "FERDINAND", "FERN", "FLORA", "FLORENCE", "FLORIAN", "FRANCESCA",
    "FRANK", "FREDERICK", "FRIEDA", "GAIL", "GENEVIEVE", "GERALD", "GERTRUDE", "GILBERT",
    "GLEN", "GRACE", "GUS", "GWENDOLYN", "HANK", "HARVEY", "HAZEL", "HERBERT",
    "HILDA", "HORACIO", "HORTENSE", "HUGH", "IDA", "IGNATIUS", "IRENE",
    "IRIS", "ISABEL", "IVAN", "IVY", "JASMINE", "JAY", "JOAN",
    "JOANNA", "JONAH", "JOSEPHINE", "JOY", "JUDE", "KAI", "KARLA", "KATHLEEN",
    "KENDALL", "KURT", "LAWRENCE", "LEN", "LENA", "LEO", "LEONA", "LEONARD", "LOIS", "LORETTA", "LUELLA", "MABEL", "MAE", "MARGARET", "MARGUERITE", "MARION", "MARTHA", "MATTHIAS", "MAURICE", "MAVIS", "MAX", "MILDRED",
    "MYRA", "NED", "NEIL", "NOLA", "NORMA", "NORRIS", "NORWOOD", "OCTAVIUS",
    "OLIVER", "OPAL", "OSCAR", "OTTO", "PEARL", "PERCIVAL", "PERCY",
    "PERSEPHONE", "PHOEBE", "QUINCY", "RALPH", "RAY", "RAYMOND", "REGINALD", "REID",
    "RON", "ROSALIE", "ROSALIND", "ROSCOE", "ROSIE", "RUTH", "SADIE",
    "SELMA", "SETH", "SEYMOUR", "SIMONE", "SUE", "SYBIL", "TED", "TESSA",
    "THELMA", "THEODORA", "THERESA", "TOBY", "ULYSSES", "VERA", "VESTA",
    "VIOLA", "VIOLET", "WADE", "WALTER", "WANDA", "WENDELL", "WILHELMINA", "WILMA", "WYNN", "YOLANDA", "YVETTE", "ZELDA", "ZOE",
    "ALEXANDRINAS", "ALEXANDRINEAS", "ALEXANDRINELLA", "ALEXANDRINELLAS", "BARTHOLOMEUS", "BARTHOLOMEW",
    "BARTHOLOMEWES", "CHRISTOPHER", "CHRISTOPHERA", "CHRISTOPHERAS", "CHRISTOPHERINA", "CONSTANTINE",
    "CONSTANTINUS", "MAXIMILIANO", "THEOPHILUSA",
]

# Suffixes and honorifics are structural, not identifying -- "JR." carries no more
# information about who someone is than a comma does. Keeping them verbatim
# preserves the row template exactly.
NAME_SUFFIXES = {
    "JR", "JR.", "SR", "SR.", "II", "III", "IV", "V", "VI", "MD", "M.D.", "DO", "D.O.",
    "PHD", "PH.D.", "RN", "NP", "PA", "PA-C", "DDS", "DPM", "ESQ", "ESQ.", "CRNA", "APRN",
}

# Single letters that double as suffixes. A middle initial of "V" would be read as a
# generational suffix, changing the row's template, so these are avoided for initials.
_SINGLE_LETTER_SUFFIXES = {"V", "I"}

# RFC 2606 reserves these; a generated address provably cannot reach a real person.
RESERVED_DOMAINS = ["example.com", "example.org", "example.net"]

UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWER = "abcdefghijklmnopqrstuvwxyz"
DIGITS = "0123456789"


def _rand(salt: str, *parts: object) -> "_Rng":
    """Derive a deterministic stream from a salt plus key parts.

    Using a hash rather than a seeded PRNG means a given (salt, key) always maps to
    the same fake regardless of the order rows are processed in. That order
    independence is what lets the same MRN on row 2 and row 118 land on the same
    fake value without the caller having to thread state around.
    """
    key = "\x1f".join(str(p) for p in parts)
    return _Rng(hashlib.sha256(f"{salt}\x1e{key}".encode()).digest())


class _Rng:
    """A tiny deterministic byte stream, extended by rehashing as needed."""

    def __init__(self, seed: bytes) -> None:
        self._buf = bytearray(seed)
        self._pos = 0

    def _byte(self) -> int:
        if self._pos >= len(self._buf):
            self._buf.extend(hashlib.sha256(bytes(self._buf[-32:])).digest())
        b = self._buf[self._pos]
        self._pos += 1
        return b

    def below(self, n: int) -> int:
        """Uniform-ish integer in [0, n). Modulo bias is irrelevant for fake data."""
        if n <= 1:
            return 0
        v = 0
        for _ in range(4):
            v = (v << 8) | self._byte()
        return v % n

    def pick(self, seq):
        return seq[self.below(len(seq))]

    def between(self, lo: int, hi: int) -> int:
        """Inclusive on both ends."""
        return lo + self.below(hi - lo + 1)


# ---------------------------------------------------------------------------
# Masks: the generic engine for opaque identifiers
# ---------------------------------------------------------------------------

def mask_of(value: str) -> str:
    """Reduce a value to its character-class skeleton.

    Letters become A or a (preserving case), digits become 9, and everything else
    is kept verbatim because punctuation is part of the shape a parser sees.

        "1AB2CD3EF45"        -> "9AA9AA9AA99"
        "100000000001AB02"   -> "999999999999AA99"
        "100003-04"          -> "999999-99"
        "TEST,ALPHA A"       -> "AAAA,AAAAA A"
    """
    out = []
    for ch in value:
        if ch.isdigit():
            out.append("9")
        elif ch.isalpha():
            out.append("A" if ch.isupper() else "a")
        else:
            out.append(ch)
    return "".join(out)


def fill_mask(mask: str, rng: _Rng, source: str = "") -> str:
    """Generate a value matching a mask exactly.

    Runs of leading zeros are preserved in full. A column of zero-padded 7-digit
    MRNs should stay zero-padded to the same width -- the padding is format, not
    identity, and code that strips it, or that relies on a fixed width, has to see
    the same thing. Preserving only the first zero of "00012" would change its
    apparent magnitude from 12 to thousands.
    """
    out = []
    in_leading_zeros = False
    for i, m in enumerate(mask):
        prev_is_digit = i > 0 and mask[i - 1] == "9"
        if m == "9":
            if not prev_is_digit:
                in_leading_zeros = True  # start of a digit run
            src_ch = source[i] if i < len(source) else ""
            if in_leading_zeros and src_ch == "0":
                out.append("0")
            else:
                in_leading_zeros = False
                # Keep the run's first significant digit non-zero so the value's
                # magnitude, and therefore its printed width, matches the original.
                out.append(rng.pick(DIGITS[1:]) if (not prev_is_digit and src_ch != "0")
                           else rng.pick(DIGITS))
        elif m == "A":
            out.append(rng.pick(UPPER))
        elif m == "a":
            out.append(rng.pick(LOWER))
        else:
            in_leading_zeros = False
            out.append(m)
    return "".join(out)


# ---------------------------------------------------------------------------
# Names: template preservation
# ---------------------------------------------------------------------------

_NAME_SPLIT = re.compile(r"([^\W\d_]+(?:'[^\W\d_]+)?\.?)", re.UNICODE)


def name_template(value: str) -> str:
    """Describe a name's structure, ignoring which name it actually is.

    This is the thing that must be preserved per row for the distribution
    requirement to hold. Two names share a template when a parser would treat
    them identically:

        "TEST,ALPHA A"              -> "W,W I"
        "MOCKS,BRAVO DELTA"         -> "W,W W"
        "TESTCO,FOXTROT GOLF JR."   -> "W,W W S"
        "VAN DER TEST,HOTEL INDIA"  -> "W W W,W W"
    """
    parts = []
    for tok in _NAME_SPLIT.split(value):
        if not tok:
            continue
        # Separators are kept verbatim rather than trimmed, so "SMITH,JOHN" and
        # "SMITH, JOHN" are recognised as different templates. They are different to
        # a parser, and render_name reproduces them exactly, so the comparison
        # should be exact too.
        parts.append(_classify_name_token(tok) if _NAME_SPLIT.fullmatch(tok) else tok)
    return "".join(parts)


def _classify_name_token(tok: str) -> str:
    bare = tok.rstrip(".")
    if bare.upper() in {s.rstrip(".") for s in NAME_SUFFIXES}:
        return "S"
    if len(bare) == 1:
        return "I"
    return "W"


def _case_like(word: str, model: str) -> str:
    """Match the case style of the value being replaced."""
    if model.isupper():
        return word.upper()
    if model.islower():
        return word.lower()
    if model[:1].isupper():
        return word.capitalize()
    return word


def _fit_length(pool: list[str], target: int, rng: _Rng, avoid: set[str] | None = None) -> str:
    """Pick a pool word of exactly `target` letters, avoiding given words.

    Exact length matters more than it might seem. The character mask is the
    strictest shape test there is -- "TEST,ALPHA A" and "FRYE,BLYTHE C" have the
    same name template but different masks, so a fixed-width reader or a
    column-width assertion would see the file change. Matching length exactly
    makes the mask survive for free.

    `avoid` keeps a generated word from colliding with a real word in the source
    value. Reusing a real name as its own replacement is not a leak of that
    person's identity, but it reads as one to anyone auditing the output, and
    dodging it costs nothing.
    """
    avoid = {a.upper() for a in (avoid or set())}
    exact = [w for w in pool if len(w) == target and w.upper() not in avoid]
    if exact:
        return rng.pick(exact)
    # No pool word of this length: take the closest and pad or trim to fit. The
    # result is a touch less name-like, but mask fidelity is the harder requirement
    # and this keeps it exact.
    near = sorted((w for w in pool if w.upper() not in avoid) or pool,
                  key=lambda w: (abs(len(w) - target), w))
    for _ in range(8):
        base = rng.pick(near[: max(4, len(near) // 8)])
        cand = (base[:target] if len(base) > target
                else base + "".join(rng.pick("AEIOULNRST") for _ in range(target - len(base))))
        cand = cand or base[:1]
        if cand.upper() not in avoid:
            return cand
    return cand


class Persona:
    """A stable fake identity, so every column about one person agrees.

    A file may carry the patient's name in one column, or split across
    first/middle/last columns, or repeat it on several rows. All of those must
    resolve to the same invented person, otherwise the redacted file breaks the
    duplicate-patient and name-matching logic it is supposed to exercise.

    Words are chosen to match the length of the value being replaced, and cached
    per (role, slot, length). So a person whose name is spelled identically
    everywhere -- the common case -- gets one consistent identity, while an
    unusual row that spells it at a different length still keeps its mask. Where
    those two goals conflict, mask fidelity wins, because a broken mask is
    visible to every downstream consumer whereas the identity link only matters
    within the file.
    """

    def __init__(self, rng: _Rng, first_len: int = 7, last_len: int = 8,
                 forbidden: set[str] | None = None) -> None:
        self.rng = rng
        # Words that appear anywhere in the source file. Avoiding all of them means
        # no generated name can be mistaken for a surviving real one.
        self.forbidden = forbidden or set()
        self._cache: dict[tuple[str, int, int], str] = {}
        self.first = self._pick("given", 0, first_len)
        self.middle = self._pick("given", 1, first_len)
        self.last = self._pick("last", 0, last_len)

    def _pick(self, role: str, slot: int, length: int, avoid: set[str] | None = None) -> str:
        """Choose (and remember) the word for one name slot.

        The cache is keyed on the slot and the required length, deliberately not on
        `avoid`: a cached choice is reused as long as it does not collide. That way
        the same person keeps the same name across rows, and `avoid` only forces a
        fresh pick when it actually has to -- which is what stops "EDITH EDITH"
        without fragmenting the identity.
        """
        key = (role, slot, length)
        blocked = set(self.forbidden) | {a.upper() for a in (avoid or set())}
        cached = self._cache.get(key)
        if cached is not None and cached.upper() not in blocked:
            return cached
        pool = SURNAMES if role == "last" else GIVEN_NAMES
        # Vary the seed by collision count so a retry lands somewhere new.
        seed = _rand("persona-word", role, slot, length, self._seed_tag(), len(blocked))
        word = _fit_length(pool, length, seed, blocked)
        if cached is None:
            self._cache[key] = word
        return word

    def _seed_tag(self) -> str:
        # The construction rng already encodes the subject; draw a stable tag from it
        # once so per-slot picks vary independently but reproducibly.
        if not hasattr(self, "_tag"):
            self._tag = "".join(str(self.rng.below(10)) for _ in range(8))
        return self._tag

    def word(self, index: int, model: str, role: str, avoid: set[str] | None = None) -> str:
        """Return a name word shaped like `model`, invented once per slot and length.

        Internal punctuation is re-inserted at the same offsets, so "O'SAMPLE" yields
        another apostrophised word rather than a plain one -- otherwise the mask
        changes and a parser splitting on apostrophes sees a different row.
        """
        bare = model.rstrip(".")
        punct = [(i, c) for i, c in enumerate(bare) if not c.isalpha()]
        target = len(bare) - len(punct)
        slot_role = "last" if role == "last" else "given"
        word = self._pick(slot_role, index, target, avoid)
        if punct:
            chars = list(word)
            for i, c in punct:
                chars.insert(i, c)
            word = "".join(chars)
        return _case_like(word, model)


def render_name(value: str, persona: Persona, last_first: bool | None = None) -> str:
    """Rebuild a name with fake words but the original template byte-for-byte.

    Separators, suffixes and initials are copied through untouched; only the
    name words change. Because the template comes from this specific value, a
    file that is 20% "FIRST M" and 60% "FIRST M LAST" stays exactly that.
    """
    tokens = [t for t in _NAME_SPLIT.split(value) if t]
    if last_first is None:
        last_first = "," in value

    # Decide which word tokens belong to the surname. With "LAST,FIRST M" every
    # word before the comma is surname; otherwise the trailing word is.
    word_positions = [i for i, t in enumerate(tokens) if _NAME_SPLIT.fullmatch(t) and _classify_name_token(t) == "W"]
    surname_positions: set[int] = set()
    if word_positions:
        if last_first:
            comma_at = next((i for i, t in enumerate(tokens) if "," in t), None)
            if comma_at is not None:
                surname_positions = {i for i in word_positions if i < comma_at}
        if not surname_positions:
            surname_positions = {word_positions[-1] if not last_first else word_positions[0]}

    # Never emit a word that appears in the source value. It would not identify the
    # real patient, but it looks like a leak to a reviewer and to the verifier's
    # substring scan, and avoiding it is free.
    avoid = {t.rstrip(".").upper() for t in tokens if _NAME_SPLIT.fullmatch(t)}

    out = []
    given_index = 0
    surname_index = 0
    # Words already emitted for this name. A person is not called "EDITH EDITH", so
    # each slot also steers clear of its siblings.
    used: set[str] = set()
    for i, tok in enumerate(tokens):
        if not _NAME_SPLIT.fullmatch(tok):
            out.append(tok)
            continue
        kind = _classify_name_token(tok)
        if kind == "S":
            out.append(tok)  # suffixes are structure, not identity
        elif kind == "I":
            # An initial must stay an initial. Deriving it from the fake given name
            # keeps "JAMES A" style rows internally coherent -- except for letters
            # that would re-read as a suffix ("V", "I"), which would silently change
            # the row's template from "W,W I" to "W,W S".
            trailing = "." if tok.endswith(".") else ""
            src = persona.first if (given_index == 0 and i not in surname_positions) else persona.middle
            letter = src[0]
            if letter.upper() in _SINGLE_LETTER_SUFFIXES:
                letter = next((c for c in src[1:] + "BCDEFGH"
                               if c.upper() not in _SINGLE_LETTER_SUFFIXES), "B")
            out.append(_case_like(letter, tok[0]) + trailing)
            if i not in surname_positions:
                given_index += 1
        else:
            role = "last" if i in surname_positions else "given"
            idx = surname_index if role == "last" else given_index
            word = persona.word(idx, tok, role, avoid | used)
            used.add(word.upper())
            out.append(word)
            if role == "last":
                surname_index += 1
            else:
                given_index += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# Dates: format-faithful shifting
# ---------------------------------------------------------------------------

_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
_MONTHS_FULL = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
                "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]

_NUM_DATE = re.compile(
    r"^(?P<a>\d{1,4})(?P<s1>[/\-.])(?P<b>\d{1,2})(?P<s2>[/\-.])(?P<c>\d{2,4})(?P<tail>[ T].*)?$"
)
_COMPACT_DATE = re.compile(r"^(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})(?P<tail>.*)?$")
_TEXT_DATE = re.compile(
    r"^(?P<d>\d{1,2})[ \-](?P<mon>[A-Za-z]{3,9})[ \-](?P<y>\d{2,4})(?P<tail>[ T].*)?$"
)

_DAYS_IN_MONTH = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _to_ordinal(y: int, m: int, d: int) -> int:
    m = min(max(m, 1), 12)
    d = min(max(d, 1), _DAYS_IN_MONTH[m - 1])
    if m == 2 and d == 29 and not (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)):
        d = 28
    return datetime.date(y, m, d).toordinal()


def _from_ordinal(n: int) -> datetime.date:
    return datetime.date.fromordinal(n)


def parse_date(value: str) -> dict | None:
    """Recognise a date and record its exact written format.

    The format is captured as component widths, separators and ordering rather
    than a strftime string, because that is the only way to round-trip "3/7/51"
    and "03/07/1951" back to their own spelling.
    """
    v = value.strip()
    if not v:
        return None

    m = _NUM_DATE.match(v)
    if m:
        a, b, c = m.group("a"), m.group("b"), m.group("c")
        if len(a) == 4:  # Y-M-D
            order, y, mo, d = "ymd", a, b, c
        else:  # M-D-Y, the dominant US clinical spelling
            order, mo, d, y = "mdy", a, b, c
        try:
            yi = _expand_year(y)
            return {
                "kind": "numeric", "order": order, "year": yi, "month": int(mo), "day": int(d),
                "widths": (len(y), len(mo), len(d)), "seps": (m.group("s1"), m.group("s2")),
                "tail": m.group("tail") or "",
            }
        except ValueError:
            return None

    m = _COMPACT_DATE.match(v)
    if m and not m.group("tail"):
        try:
            return {
                "kind": "compact", "year": int(m.group("y")), "month": int(m.group("m")),
                "day": int(m.group("d")), "tail": "",
            }
        except ValueError:
            return None

    m = _TEXT_DATE.match(v)
    if m:
        mon = m.group("mon")[:3].upper()
        if mon in _MONTHS:
            return {
                "kind": "text", "year": _expand_year(m.group("y")), "month": _MONTHS.index(mon) + 1,
                "day": int(m.group("d")), "mon_style": m.group("mon"),
                "sep": "-" if "-" in v else " ", "ywidth": len(m.group("y")),
                "dwidth": len(m.group("d")), "tail": m.group("tail") or "",
            }
    return None


def _fit_component_widths(parsed: dict, offset_days: int) -> int:
    """Adjust an offset so month/day keep the digit widths the source used.

    Only relevant for unpadded dates. Searching outward from the requested offset
    keeps the shift as close as the constraint allows; de-identification strength is
    unchanged, since the result is still a shift of hundreds of days.

    The cost is that the fitted offset is per value, not per patient: two dates for
    one patient written in different formats can move by different amounts (up to
    ~57 days apart here), so the interval between those two shifts. Dates sharing a
    format keep their intervals exactly, which is the ordinary case.
    """
    ywidth, mwidth, dwidth = parsed["widths"]
    if mwidth > 1 and dwidth > 1:
        return offset_days  # zero-padded: any date renders at the same width
    base = _to_ordinal(parsed["year"], parsed["month"], parsed["day"])
    want_m_single = mwidth == 1 and parsed["month"] < 10
    want_d_single = dwidth == 1 and parsed["day"] < 10
    for delta in range(0, 400):
        for cand in ({offset_days + delta, offset_days - delta} if delta else {offset_days}):
            d = _from_ordinal(base + cand)
            if want_m_single and d.month >= 10:
                continue
            if want_d_single and d.day >= 10:
                continue
            if mwidth == 1 and parsed["month"] >= 10 and d.month < 10:
                continue  # source wrote a 2-digit month unpadded; keep it 2-digit
            if dwidth == 1 and parsed["day"] >= 10 and d.day < 10:
                continue
            if cand != 0:
                return cand
    return offset_days


def _fit_text_widths(parsed: dict, offset_days: int) -> int:
    """Adjust an offset so a month-name date keeps the source's field widths.

    Two things can resize this format. Month names are not a uniform length --
    "May" is 3 characters and "September" is 9 -- so a shift landing on a different
    month changes the field width. And an unpadded day ("1 May 1950") grows a
    character the moment it shifts past the 9th. Either one breaks the character
    mask, and a column of "18 October 1948" values in a fixed-width export is
    exactly what a downstream parser measures.

    Same outward search as _fit_component_widths, and the same per-value caveat --
    more sharply here, because month-name lengths are sparse (only September has 9
    letters), so the search can walk a season: up to ~177 days from the requested
    offset. De-identification strength is unaffected, but a patient with one date
    in this format and another in a numeric format will see the interval between
    those two move. Abbreviations are uniformly three letters, so the month
    constraint only binds on spelled-out names.
    """
    want_mon = len(parsed["mon_style"])
    fit_mon = want_mon > 3
    fit_day = parsed["dwidth"] == 1  # unpadded: rendered without zero-padding
    if not fit_mon and not fit_day:
        return offset_days
    base = _to_ordinal(parsed["year"], parsed["month"], parsed["day"])
    for delta in range(0, 400):
        for cand in ({offset_days + delta, offset_days - delta} if delta else {offset_days}):
            if cand == 0:
                continue  # the shift is never zero; that would leave the date real
            d = _from_ordinal(base + cand)
            if fit_mon and len(_MONTHS_FULL[d.month - 1]) != want_mon:
                continue
            if fit_day and d.day >= 10:
                continue
            return cand
    return offset_days


def _expand_year(y: str) -> int:
    n = int(y)
    if len(y) == 4:
        if not 1800 <= n <= 2200:
            raise ValueError("implausible year")
        return n
    return 2000 + n if n < 40 else 1900 + n


def shift_date(parsed: dict, offset_days: int) -> str:
    """Re-render a parsed date shifted by offset_days, in its original spelling.

    Where the source wrote a component unpadded ("3/7/51" rather than "03/07/51"),
    the shift is nudged so the result stays in the same width. A source that writes
    single-digit months and days is telling us its fields are variable-width, and a
    2-character day where there was a 1-character day is shape drift -- it changes
    the line length and the mask.
    """
    if parsed["kind"] == "numeric":
        offset_days = _fit_component_widths(parsed, offset_days)
    elif parsed["kind"] == "text":
        offset_days = _fit_text_widths(parsed, offset_days)
    d = _from_ordinal(_to_ordinal(parsed["year"], parsed["month"], parsed["day"]) + offset_days)

    if parsed["kind"] == "compact":
        return f"{d.year:04d}{d.month:02d}{d.day:02d}"

    if parsed["kind"] == "text":
        style = parsed["mon_style"]
        # Match abbreviated vs spelled-out months. Writing "Jan" where the source
        # said "October" changes the field's width and its mask.
        mon = _MONTHS_FULL[d.month - 1] if len(style) > 3 else _MONTHS[d.month - 1]
        if style[:1].isupper() and style[1:2].islower():
            mon = mon.capitalize()
        elif style.islower():
            mon = mon.lower()
        year = f"{d.year:04d}" if parsed["ywidth"] == 4 else f"{d.year % 100:02d}"
        day = f"{d.day:0{parsed['dwidth']}d}"
        return f"{day}{parsed['sep']}{mon}{parsed['sep']}{year}{parsed['tail']}"

    ywidth, mwidth, dwidth = parsed["widths"]
    year = f"{d.year:04d}" if ywidth == 4 else f"{d.year % 100:02d}"
    month = f"{d.month:0{mwidth}d}"
    day = f"{d.day:0{dwidth}d}"
    s1, s2 = parsed["seps"]
    if parsed["order"] == "ymd":
        return f"{year}{s1}{month}{s2}{day}{parsed['tail']}"
    return f"{month}{s1}{day}{s2}{year}{parsed['tail']}"


# ---------------------------------------------------------------------------
# Typed generators for the identifiers that benefit from being provably fake
# ---------------------------------------------------------------------------

def fake_ssn(source: str, rng: _Rng) -> str:
    """Shape-preserved SSN in the 900-999 area, which was never issued."""
    mask = mask_of(source)
    digits = [str(rng.below(10)) for _ in range(sum(1 for c in mask if c == "9"))]
    if len(digits) >= 3:
        digits[0], digits[1], digits[2] = "9", str(rng.between(0, 9)), str(rng.between(0, 9))
    return _refill_digits(mask, digits)


def fake_phone(source: str, rng: _Rng) -> str:
    """Shape-preserved phone using the reserved 555-01xx fictional range."""
    mask = mask_of(source)
    slots = sum(1 for c in mask if c == "9")
    digits = [str(rng.below(10)) for _ in range(slots)]
    # Locate the national number (last 10 digits) and stamp 555 into the exchange.
    if slots >= 10:
        base = slots - 10
        digits[base] = str(rng.between(2, 9))
        digits[base + 1] = str(rng.between(0, 8))
        digits[base + 2] = str(rng.between(0, 9))
        digits[base + 3:base + 6] = ["5", "5", "5"]
        digits[base + 6:base + 8] = ["0", "1"]
    return _refill_digits(mask, digits)


def fake_email(source: str, rng: _Rng, persona: Persona | None = None) -> str:
    """A structurally similar address on a reserved domain.

    The domain is deliberately *not* shape-preserved. Every other field in this
    module keeps its shape, but an email that keeps its real domain is a live
    route to a real mailbox, and no amount of shape fidelity justifies that.
    """
    if "@" not in source:
        return fill_mask(mask_of(source), rng, source)
    local, _, domain = source.partition("@")
    if persona is not None:
        first, last = persona.first.lower(), persona.last.lower()
        if "." in local:
            new_local = f"{first}.{last}"
        elif "_" in local:
            new_local = f"{first}_{last}"
        else:
            new_local = f"{first[0]}{last}"
        digits = "".join(c for c in local if c.isdigit())
        new_local += digits
    else:
        new_local = fill_mask(mask_of(local), rng, local).lower()
    tld_style = domain.rsplit(".", 1)[-1].lower() if "." in domain else "com"
    dom = next((d for d in RESERVED_DOMAINS if d.endswith("." + tld_style)), RESERVED_DOMAINS[0])
    return f"{new_local}@{dom}"


def fake_zip(source: str, rng: _Rng) -> str:
    """Shape-preserved ZIP. Fully invented rather than truncated to 3 digits.

    Safe Harbor allows keeping the first three digits of a non-restricted ZIP,
    but truncation changes the value's length -- which is exactly the shape drift
    this skill exists to avoid. Replacing the whole thing is both simpler and
    strictly more protective.
    """
    return fill_mask(mask_of(source), rng, source)


def fake_age(source: str, rng: _Rng) -> str:
    """Plausible age, never above 89.

    Safe Harbor treats an exact age over 89 as identifying, because very old
    patients are rare enough to single out. Capping at 90 mirrors the standard's
    "90 or above" aggregation while keeping the field numeric.
    """
    s = source.strip()
    if not s.isdigit():
        return fill_mask(mask_of(source), rng, source)
    width = len(s)
    real = int(s)
    if real > 89:
        # Zero-pad to the source width so the character mask survives: "102" has to
        # become "090", not "90". A width change here is unfixable by the user --
        # age is not a loose-mask type, so verify reports a mask mismatch and the
        # only way out would be to stop capping, which is the thing Safe Harbor
        # requires. Padding also avoids the old slicing rule, which turned a
        # 4-character "0102" into "0190" -- an age of 190.
        capped = f"{90:0{width}d}"
        # An age that already reads exactly 90 would come back unchanged and fail
        # "no PHI cell left unchanged" with no recourse -- the cap path takes no
        # randomness, so re-salting cannot help. 89 keeps the width and is still
        # clear of the identifying tail.
        return capped if capped != s else f"{89:0{width}d}"
    # Redraw until the value actually differs. A two-digit age has only ~72
    # possibilities, so landing back on the original happens often enough to trip
    # the "no PHI cell left unchanged" check -- and because generation is
    # deterministic, the user's only recourse would be re-salting the whole file.
    for _ in range(8):
        cand = f"{rng.between(18, 89):0{width}d}" if width >= 2 else str(rng.between(1, 9))
        if cand != s:
            return cand
    return cand


def _refill_digits(mask: str, digits: list[str]) -> str:
    out, i = [], 0
    for m in mask:
        if m == "9":
            out.append(digits[i] if i < len(digits) else "0")
            i += 1
        elif m == "A":
            out.append("X")
        elif m == "a":
            out.append("x")
        else:
            out.append(m)
    return "".join(out)


def normalize_key(value: str) -> str:
    """Fold a value for use as a mapping key so trivial variants agree.

    "TEST,ALPHA A" and "Test, Alpha A" are the same person as far as consistency
    is concerned; they should land on the same fake identity.
    """
    v = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "", v).upper()
