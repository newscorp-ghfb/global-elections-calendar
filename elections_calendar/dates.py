"""Civil-date grammar for source text (spec §6.1).

Dates are year/month/day components (``datetime.date``); nothing here goes
through a timestamp or a time zone. ``parse_date_text`` extracts status words
first, then parses what is left with one of the full-match forms below. Text
it cannot account for is returned as ``leftover``, never silently dropped.
"""

import re
from dataclasses import dataclass
from datetime import date

from elections_calendar.model import DateSpan, DateStatus, Relevance, StatusClaim, month_end
from elections_calendar.text import collapse_ws

MONTH_NUMBERS: dict[str, int] = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}  # fmt: skip

_MONTH = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
    r"|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\.?"
)
_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
_YEAR = r"\d{4}"
_DASH = r"\s*(?:-|\bto\b|\buntil\b|\bthrough\b)\s*"
_OPT_YEAR = r"(?:,?\s+(?P<{name}>\d{{4}}))?"


def _full(pattern: str) -> re.Pattern[str]:
    return re.compile(rf"^{pattern}$", re.IGNORECASE)


def _y(name: str) -> str:
    return _OPT_YEAR.format(name=name)


_ISO = _full(r"(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})")
_DMY_DMY = _full(
    rf"(?P<d1>{_DAY})\s+(?P<m1>{_MONTH}){_y('y1')}{_DASH}(?P<d2>{_DAY})\s+(?P<m2>{_MONTH}){_y('y2')}"
)
_DD_M = _full(rf"(?P<d1>{_DAY}){_DASH}(?P<d2>{_DAY})\s+(?P<m2>{_MONTH}){_y('y2')}")
_MD_MD = _full(
    rf"(?P<m1>{_MONTH})\s+(?P<d1>{_DAY}){_DASH}(?P<m2>{_MONTH})\s+(?P<d2>{_DAY}){_y('y2')}"
)
_M_DD = _full(rf"(?P<m1>{_MONTH})\s+(?P<d1>{_DAY}){_DASH}(?P<d2>{_DAY}){_y('y2')}")
_DMY = _full(rf"(?P<d>{_DAY})\s+(?P<m>{_MONTH}){_y('y')}")
_MDY = _full(rf"(?P<m>{_MONTH})\s+(?P<d>{_DAY}){_y('y')}")
_M_M = _full(rf"(?P<m1>{_MONTH}){_y('y1')}{_DASH}(?P<m2>{_MONTH}){_y('y2')}")
_MY = _full(rf"(?P<m>{_MONTH}){_y('y')}")
_YEAR_ONLY = _full(r"(?P<y>\d{4})")
_LIST_ITEM = rf"{_DAY}(?:\s+{_MONTH})?"
_LIST = _full(
    rf"(?P<items>{_LIST_ITEM}(?:\s*,\s*(?:and\s+)?{_LIST_ITEM}|\s+and\s+{_LIST_ITEM})+){_y('y')}"
)
_LIST_SPLIT = re.compile(r"\s*,\s*(?:and\s+)?|\s+and\s+", re.IGNORECASE)

# en dash, em dash, figure dash, minus sign, hyphen, non-breaking hyphen
_DASHES = str.maketrans(dict.fromkeys("\u2013\u2014\u2012\u2212\u2010\u2011", "-"))
_YEAR_THEN_LETTER = re.compile(r"(\d{4})(?=[A-Za-z])")
_POSTPONED = re.compile(
    r"\bpostponed\b(?:\s+from\s+(?P<prev>.+?))?(?:\s+to\s+(?P<new>.+?))?\s*$", re.IGNORECASE
)
_MARKERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\(d\)", re.IGNORECASE), "(d)"),
    (re.compile(r"\(t\)", re.IGNORECASE), "(t)"),
    (re.compile(r"\bdate not confirmed\b", re.IGNORECASE), "date not confirmed"),
    (re.compile(r"\(\s*(?:exact\s+)?date\s+tb[dc]\s*\)", re.IGNORECASE), "tbd"),
    (re.compile(r"\b(?:exact\s+)?date\s+tb[dc]\b", re.IGNORECASE), "tbd"),
    (re.compile(r"\btb[dc]\b", re.IGNORECASE), "tbd"),
    (re.compile(r"\btentative(?:ly)?\b", re.IGNORECASE), "tentative"),
    (re.compile(r"\bexpected\b", re.IGNORECASE), "expected"),
    (re.compile(r"\(\s*all day\s*\)", re.IGNORECASE), "all day"),
    (re.compile(r"\bupcoming\b", re.IGNORECASE), "upcoming"),
    (re.compile(r"\bpast\b", re.IGNORECASE), "past"),
    (re.compile(r"\bcancel+ed\b", re.IGNORECASE), "cancelled"),
    (re.compile(r"\bdisputed\b", re.IGNORECASE), "disputed"),
    (re.compile(r"\bheld\b", re.IGNORECASE), "held"),
    (re.compile(r"^\s*stag+e?r+e?d\b\s*:?", re.IGNORECASE), "staggered"),
    (re.compile(r"\*+"), "*"),
)
_TENTATIVE_WORDS = frozenset({"(t)", "date not confirmed", "tbd", "tentative", "expected"})
_STATUS_ORDER: tuple[StatusClaim, ...] = ("cancelled", "postponed", "disputed", "held")
_EDGE_PUNCT = " ,;:-"
_MAX_ROLL_MONTHS = 5  # "Sep - Feb 2027" rolls; "10 Oct - 5 Sep 2026" is likelier a typo


@dataclass(frozen=True, slots=True)
class DateParse:
    """Result of parsing one date text.

    ``spans`` is empty when the text holds no date of its own (e.g. only
    "Postponed from April 2026"). ``leftover`` is the text that could not be
    parsed; it is "" when everything was accounted for.
    """

    spans: tuple[DateSpan, ...]
    date_status: DateStatus
    status_claim: StatusClaim | None
    status_words: tuple[str, ...]
    previous_text: str | None
    previous_spans: tuple[DateSpan, ...]
    leftover: str
    phased: bool

    @property
    def ok(self) -> bool:
        return not self.leftover


def parse_date_text(text: str, *, default_year: int | None = None) -> DateParse:
    """Parse a source's date text; ``default_year`` fills in a missing year."""
    clean = _YEAR_THEN_LETTER.sub(r"\1 ", collapse_ws(text.translate(_DASHES)))
    words: list[str] = []
    previous_text: str | None = None
    previous_spans: tuple[DateSpan, ...] = ()
    postponed = _POSTPONED.search(clean)
    if postponed:
        words.append("postponed")
        previous_text = (postponed.group("prev") or "").strip(_EDGE_PUNCT) or None
        if previous_text:
            previous_spans, prev_left = _parse_core(previous_text, default_year)
            if prev_left:
                previous_spans = ()
        clean = f"{clean[: postponed.start()]} {postponed.group('new') or ''}"
    for pattern, word in _MARKERS:
        if pattern.search(clean):
            words.append(word)
            clean = pattern.sub(" ", clean)
    core = collapse_ws(clean).strip(_EDGE_PUNCT)
    spans, leftover = _parse_core(core, default_year) if core else ((), "")
    return DateParse(
        spans=spans,
        date_status=_date_status(words),
        status_claim=next((s for s in _STATUS_ORDER if s in words), None),
        status_words=tuple(words),
        previous_text=previous_text,
        previous_spans=previous_spans,
        leftover=leftover,
        phased="staggered" in words,
    )


def _date_status(words: list[str]) -> DateStatus:
    if any(w in _TENTATIVE_WORDS for w in words):
        return "tentative"
    if "(d)" in words:
        return "confirmed"
    return "unknown"


def _parse_core(core: str, default_year: int | None) -> tuple[tuple[DateSpan, ...], str]:
    """Spans for ``core`` (no status words left), or ((), core) when it doesn't parse."""
    try:
        spans = _match(core, default_year)
    except ValueError:
        spans = None
    return (spans, "") if spans else ((), core)


def _match(core: str, default_year: int | None) -> tuple[DateSpan, ...] | None:
    if m := _ISO.match(core):
        return (DateSpan.day(date(int(m["y"]), int(m["m"]), int(m["d"]))),)
    for pattern in (_DMY_DMY, _DD_M, _MD_MD, _M_DD):
        if m := pattern.match(core):
            return (_day_range(m.groupdict(), default_year),)
    for pattern in (_DMY, _MDY):
        if m := pattern.match(core):
            year = _year(m["y"], default_year)
            return (DateSpan.day(date(year, _month(m["m"]), _day(m["d"]))),)
    if m := _M_M.match(core):
        m1, m2 = _month(m["m1"]), _month(m["m2"])
        y1, y2 = _range_years(m["y1"], m["y2"], default_year, (m1, 1), (m2, 1))
        return (DateSpan.months(y1, m1, y2, m2),)
    if m := _MY.match(core):
        return (DateSpan.month(_year(m["y"], default_year), _month(m["m"])),)
    if m := _YEAR_ONLY.match(core):
        return (DateSpan.of_year(int(m["y"])),)
    if m := _LIST.match(core):
        return _day_list(m["items"], _year(m["y"], default_year))
    return None


def _day(token: str) -> int:
    digits = re.match(r"\d+", token)
    if digits is None:
        raise ValueError(f"no day in {token!r}")
    return int(digits.group())


def _month(token: str) -> int:
    return MONTH_NUMBERS[token.rstrip(".").casefold()]


def _year(token: str | None, default_year: int | None) -> int:
    if token:
        return int(token)
    if default_year is None:
        raise ValueError("no year in the text and no default year")
    return default_year


def _range_years(
    y1: str | None,
    y2: str | None,
    default_year: int | None,
    first: tuple[int, int],
    last: tuple[int, int],
) -> tuple[int, int]:
    """Years for a range whose ends may omit them.

    The end rolls into the next year when its month is earlier than the
    start's ("30 December - 2 January"), by at most ``_MAX_ROLL_MONTHS``
    months; a longer wrap ("10 Oct - 5 Sep 2026") raises, so the text stays
    leftover. Within one month an inverted range stays invalid. Only the end
    year given: the start takes it, or the year before. No year at all: the
    default is the start's.
    """
    rolls = last[0] < first[0]
    if y1 is not None and y2 is not None:
        return int(y1), int(y2)
    if rolls and last[0] + 12 - first[0] > _MAX_ROLL_MONTHS:
        raise ValueError(f"month {last[0]} after month {first[0]} is too far to roll a year")
    if y2 is not None:
        end = int(y2)
        return (end - 1 if rolls else end), end
    start = int(y1) if y1 is not None else _year(None, default_year)
    return start, (start + 1 if rolls else start)


def _day_range(groups: dict[str, str | None], default_year: int | None) -> DateSpan:
    first_month = groups.get("m1") or groups.get("m2")
    last_month = groups.get("m2") or groups.get("m1")
    if first_month is None or last_month is None:
        raise ValueError("day range without a month")
    m1, m2 = _month(first_month), _month(last_month)
    d1, d2 = _day(groups.get("d1") or ""), _day(groups.get("d2") or "")
    y1, y2 = _range_years(groups.get("y1"), groups.get("y2"), default_year, (m1, d1), (m2, d2))
    return DateSpan.days(date(y1, m1, d1), date(y2, m2, d2))


def _day_list(items: str, year: int) -> tuple[DateSpan, ...]:
    """'16 March, 18 June, and 16 October' -> one span per date; '4 and 18 Oct' shares a month.

    The dates must ascend as written: "30 December, 2 January" spans two
    years and one list year cannot say which, so it raises.
    """
    tokens = [t for t in _LIST_SPLIT.split(items) if t]
    month: int | None = None
    days: list[date] = []
    for token in reversed(tokens):
        parts = token.split()
        if len(parts) == 2:
            month = _month(parts[1])
        if month is None:
            raise ValueError(f"no month for {token!r}")
        days.append(date(year, month, _day(parts[0])))
    days.reverse()
    if days != sorted(days):
        raise ValueError("day list out of order")
    return tuple(DateSpan.day(d) for d in days)


# --- helpers for adapters -------------------------------------------------


def month_of(span: DateSpan) -> DateSpan:
    """The month-precision span covering ``span`` (NDI 'TBD' rows, IPU month ends)."""
    if span.start is None or span.end is None:
        return span
    return DateSpan.months(span.start.year, span.start.month, span.end.year, span.end.month)


def make_range(first: DateSpan, last: DateSpan) -> DateSpan:
    """Day interval from ``first``'s start to ``last``'s end (ElectionGuide Start/End)."""
    if first.precision != "day" or last.precision != "day":
        raise ValueError("make_range needs two day-precision spans")
    if first.start is None or last.end is None:
        raise ValueError("make_range needs dated spans")
    return DateSpan.days(first.start, last.end)


def plausible(span: DateSpan, today: date, years: int = 5) -> bool:
    """Spec §9.2: the span's years lie within ±``years`` of T."""
    last = span.end.year if span.end else span.year
    return abs(span.year - today.year) <= years and abs(last - today.year) <= years


# --- relevance (spec §6.1) -----------------------------------------------

_SCAN = re.compile(
    rf"(?P<iso>\b\d{{4}}-\d{{1,2}}-\d{{1,2}}\b)"
    rf"|\b(?P<d1>{_DAY})\s+(?P<m1>{_MONTH})(?:,?\s+(?P<y1>{_YEAR}))?"
    rf"|\b(?P<m2>{_MONTH})\s+(?P<d2>{_DAY}),?\s+(?P<y2>{_YEAR})"
    rf"|\b(?P<m3>{_MONTH}),?\s+(?P<y3>{_YEAR})",
    re.IGNORECASE,
)
_BARE_YEAR = re.compile(r"\b(?:19|20|21)\d{2}\b")
_CHANGE_MARKER = re.compile(r"\bpostpon\w*|\bto\b", re.IGNORECASE)


def relevance(text: str, window_start: date, *, default_year: int | None = None) -> Relevance:
    """Relevance of a unit's text to the window (spec §6.1).

    in_or_after_window: a date in the text ends on or after the window start,
    or a year that is not part of a date is >= the window start's year.
    before_window: every year mentioned (inside dates or bare) is before the
    window start's year, and there is no "postponed"/"to" marker.
    Otherwise unknown (including text with no date or year at all).
    """
    clean = collapse_ws(text.translate(_DASHES))
    date_ends: list[date] = []
    years: list[int] = []
    covered: list[tuple[int, int]] = []
    for m in _SCAN.finditer(clean):
        end = _scan_end(m, default_year)
        explicit = m["y1"] or m["y2"] or m["y3"] or (m["iso"] or "")[:4]
        if end is not None:
            date_ends.append(end)
            years.append(end.year)
            covered.append(m.span())
        elif explicit:
            years.append(int(explicit))
            covered.append(m.span())
    bare = [
        int(m.group())
        for m in _BARE_YEAR.finditer(clean)
        if not any(a <= m.start() < b for a, b in covered)
    ]
    years.extend(bare)
    if any(end >= window_start for end in date_ends) or any(y >= window_start.year for y in bare):
        return "in_or_after_window"
    if years and all(y < window_start.year for y in years) and not _CHANGE_MARKER.search(clean):
        return "before_window"
    return "unknown"


def _scan_end(m: re.Match[str], default_year: int | None) -> date | None:
    """Last civil day of a scanned date, or None when it isn't a valid date."""
    try:
        if m["iso"]:
            return date.fromisoformat(_zero_pad_iso(m["iso"]))
        if m["d1"]:
            year = int(m["y1"]) if m["y1"] else default_year
            if year is None:
                return None
            return date(year, _month(m["m1"]), _day(m["d1"]))
        if m["d2"]:
            return date(int(m["y2"]), _month(m["m2"]), _day(m["d2"]))
        return month_end(int(m["y3"]), _month(m["m3"]))
    except ValueError:
        return None


def _zero_pad_iso(text: str) -> str:
    y, mo, d = text.split("-")
    return f"{y}-{int(mo):02d}-{int(d):02d}"
