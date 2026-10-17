"""Civil-date grammar (spec §6.1). Inputs are real strings from the 2026-10-16 sources."""

from datetime import date

import pytest

from elections_calendar.dates import (
    make_range,
    month_of,
    parse_date_text,
    plausible,
    relevance,
)
from elections_calendar.model import DateSpan

D = date
WINDOW_START = D(2026, 9, 1)


def one(text: str, default_year: int | None = None) -> DateSpan:
    parsed = parse_date_text(text, default_year=default_year)
    assert parsed.ok, parsed.leftover
    assert len(parsed.spans) == 1, parsed.spans
    return parsed.spans[0]


@pytest.mark.parametrize(
    ("text", "start", "end"),
    [
        ("25 Oct 2026", D(2026, 10, 25), D(2026, 10, 25)),  # OSCE
        ("October 25, 2026", D(2026, 10, 25), D(2026, 10, 25)),  # NDI
        ("2026-10-25", D(2026, 10, 25), D(2026, 10, 25)),  # ElectionGuide
        ("5 December 2026", D(2026, 12, 5), D(2026, 12, 5)),
        ("01 Feb 2026", D(2026, 2, 1), D(2026, 2, 1)),  # A-WEB
        ("22 December 2026", D(2026, 12, 22), D(2026, 12, 22)),  # EISA
        ("Sept. 13, 2026", D(2026, 9, 13), D(2026, 9, 13)),
        ("1st November 2026", D(2026, 11, 1), D(2026, 11, 1)),
    ],
)
def test_single_days(text: str, start: date, end: date) -> None:
    assert one(text) == DateSpan.days(start, end)


@pytest.mark.parametrize(
    ("text", "default_year", "start", "end"),
    [
        ("18–20 September", 2026, D(2026, 9, 18), D(2026, 9, 20)),  # Wikipedia, en dash
        ("9-10 Oct 2026", None, D(2026, 10, 9), D(2026, 10, 10)),
        ("16 – 17 October", 2026, D(2026, 10, 16), D(2026, 10, 17)),
        ("18 to 20 September 2026", None, D(2026, 9, 18), D(2026, 9, 20)),
        ("October 9-10, 2026", None, D(2026, 10, 9), D(2026, 10, 10)),
        ("30 Sep – 2 Oct 2026", None, D(2026, 9, 30), D(2026, 10, 2)),
        ("02 Nov 2026 - 31 Jan 2027", None, D(2026, 11, 2), D(2027, 1, 31)),
        ("20 Oct 2018 - 21 Oct 2018", None, D(2018, 10, 20), D(2018, 10, 21)),  # IPU
        ("24 December – 6 February 2027", None, D(2026, 12, 24), D(2027, 2, 6)),
        ("30 December – 2 January", 2026, D(2026, 12, 30), D(2027, 1, 2)),
        ("October 30 - November 2, 2026", None, D(2026, 10, 30), D(2026, 11, 2)),
    ],
)
def test_day_ranges(text: str, default_year: int | None, start: date, end: date) -> None:
    assert one(text, default_year) == DateSpan.days(start, end)


def test_day_list_gives_one_span_per_date() -> None:
    parsed = parse_date_text("16 March, 18 June, and 16 October", default_year=2026)
    assert parsed.ok
    assert parsed.spans == (
        DateSpan.day(D(2026, 3, 16)),
        DateSpan.day(D(2026, 6, 18)),
        DateSpan.day(D(2026, 10, 16)),
    )


def test_day_list_shares_the_following_month() -> None:
    parsed = parse_date_text("4 and 18 October 2026")
    assert parsed.spans == (DateSpan.day(D(2026, 10, 4)), DateSpan.day(D(2026, 10, 18)))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("October 2026", DateSpan.month(2026, 10)),  # EISA
        ("Apr 2027", DateSpan.month(2027, 4)),  # OSCE
        ("December 2026", DateSpan.month(2026, 12)),
        ("Nov 2026 - Jan 2027", DateSpan.months(2026, 11, 2027, 1)),  # EISA
        ("May-June 2022", DateSpan.months(2022, 5, 2022, 6)),  # Carter
        ("December 2026 – January 2027", DateSpan.months(2026, 12, 2027, 1)),
    ],
)
def test_months(text: str, expected: DateSpan) -> None:
    assert one(text) == expected


def test_month_range_end_is_last_day_of_end_month() -> None:
    span = one("Nov 2026 - Jan 2027")
    assert (span.start, span.end) == (D(2026, 11, 1), D(2027, 1, 31))


def test_year_only_is_undated() -> None:
    span = one("2026")
    assert span == DateSpan.of_year(2026)
    assert span.start is None and span.end is None


@pytest.mark.parametrize(
    ("text", "status", "words"),
    [
        ("2026-10-16 (d)", "confirmed", ("(d)",)),  # ElectionGuide declared start
        ("2026-12-31 (t)", "tentative", ("(t)",)),
        ("25 Oct 2026 Upcoming", "unknown", ("upcoming",)),  # OSCE badge
        ("25 Oct 2026Upcoming", "unknown", ("upcoming",)),  # OSCE cell text, no space
        ("October 25, 2026 (ALL DAY)", "unknown", ("all day",)),  # NDI
        ("October 25, 2026 (exact date TBD)", "tentative", ("tbd",)),
        ("2026-12-09 Date not confirmed", "tentative", ("date not confirmed",)),
    ],
)
def test_status_words_are_extracted_before_parsing(
    text: str, status: str, words: tuple[str, ...]
) -> None:
    parsed = parse_date_text(text)
    assert parsed.ok, parsed.leftover
    assert len(parsed.spans) == 1
    assert parsed.date_status == status
    assert parsed.status_words == words


def test_held_is_a_status_claim() -> None:
    parsed = parse_date_text("Held 2 July 2026")  # EISA
    assert parsed.spans == (DateSpan.day(D(2026, 7, 2)),)
    assert parsed.status_claim == "held"


def test_postponed_from_x_is_a_previous_date_not_a_claim() -> None:
    parsed = parse_date_text("Postponed from April 2026")  # EISA
    assert parsed.ok
    assert parsed.spans == ()
    assert parsed.status_claim == "postponed"
    assert parsed.previous_text == "April 2026"
    assert parsed.previous_spans == (DateSpan.month(2026, 4),)


def test_postponed_from_x_to_y_claims_y() -> None:
    parsed = parse_date_text("Postponed from June 2026 to 2028")  # EISA
    assert parsed.spans == (DateSpan.of_year(2028),)
    assert parsed.previous_spans == (DateSpan.month(2026, 6),)
    assert parsed.status_claim == "postponed"


def test_staggered_range_is_phased() -> None:
    parsed = parse_date_text("Stagerred: 10 May 2026 - 30 July 2026")  # EISA's spelling
    assert parsed.phased
    assert parsed.spans == (DateSpan.days(D(2026, 5, 10), D(2026, 7, 30)),)


def test_carter_footnote_marker_is_recorded() -> None:
    parsed = parse_date_text("October 2020*")
    assert parsed.spans == (DateSpan.month(2020, 10),)
    assert "*" in parsed.status_words


@pytest.mark.parametrize(
    "text",
    [
        "31 Sep 2026",  # no such day
        "29 Feb 2027",
        "2026-02-30",
        "Spring 2027",
        "18–20 September",  # no year and no default
        "20 Sep – 18 Sep 2026",  # end before start
    ],
)
def test_unparseable_text_is_leftover_never_dropped(text: str) -> None:
    parsed = parse_date_text(text)
    assert parsed.spans == ()
    assert parsed.leftover
    assert not parsed.ok


@pytest.mark.parametrize("text", ["", "   ", "-"])
def test_empty_date_cells_have_no_spans_and_no_leftover(text: str) -> None:
    parsed = parse_date_text(text)  # IPU uses "-" for "no expected date"
    assert parsed.spans == ()
    assert parsed.leftover == ""


def test_nbsp_and_em_dash_are_normalised() -> None:
    assert one("18\u00a0\u2014\u00a020\u00a0September\u00a02026") == DateSpan.days(
        D(2026, 9, 18), D(2026, 9, 20)
    )


def test_month_of_widens_days_to_whole_months() -> None:
    span = month_of(DateSpan.days(D(2026, 12, 24), D(2027, 2, 6)))
    assert span == DateSpan.months(2026, 12, 2027, 2)
    assert month_of(DateSpan.of_year(2026)) == DateSpan.of_year(2026)


def test_make_range_joins_start_and_end_columns() -> None:
    start, end = one("2026-12-24 (t)"), one("2027-02-06 (t)")  # ElectionGuide Fijian Parliament
    assert make_range(start, end) == DateSpan.days(D(2026, 12, 24), D(2027, 2, 6))
    with pytest.raises(ValueError):
        make_range(end, start)
    with pytest.raises(ValueError):
        make_range(DateSpan.month(2026, 10), end)


def test_plausible_years_are_within_five_of_today() -> None:
    today = D(2026, 10, 16)
    assert plausible(DateSpan.day(D(2031, 1, 1)), today)
    assert not plausible(DateSpan.day(D(2032, 1, 1)), today)
    assert not plausible(DateSpan.days(D(2026, 1, 1), D(2032, 1, 1)), today)
    assert not plausible(DateSpan.of_year(2020), today)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Sweden, Parliament, 13 September 2026", "in_or_after_window"),
        ("Election planned for 2027", "in_or_after_window"),
        ("2 Nov 2026 - 31 Jan 2027", "in_or_after_window"),
        ("Presidential election, 12 March 2024", "before_window"),
        ("2019 and 2022 rounds", "before_window"),
        ("Postponed from June 2024", "unknown"),  # a change marker keeps it relevant
        ("Moved from 2024 to a later date", "unknown"),
        ("Presidential election", "unknown"),  # no date at all
        ("15 March 2026", "unknown"),  # before the window, but not before its year
        ("31 Sep 2024 (sic)", "before_window"),  # invalid date: its year still counts
    ],
)
def test_relevance(text: str, expected: str) -> None:
    assert relevance(text, WINDOW_START) == expected


def test_relevance_uses_the_page_year_for_dates_without_one() -> None:
    assert relevance("13 September: Sweden", WINDOW_START, default_year=2026) == (
        "in_or_after_window"
    )
    assert relevance("13 September: Sweden", WINDOW_START) == "unknown"
