import json
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

from elections_calendar.fetch import Deadline
from elections_calendar.ledger import COUNT_RULES, JsonListRule, check
from elections_calendar.model import Claim, DateSpan, InputUnit, Reason
from elections_calendar.sources.base import (
    Adapter,
    PageRequest,
    ParseResult,
    RawPages,
    Registries,
)
from elections_calendar.sources.eisa import AJAX, URL, Eisa, expected
from elections_calendar.window import Window, window_for
from tests.support.fixtures import fixture
from tests.support.pages import Served, raw_pages, result

_: Adapter = Eisa()

DAY = "2026-10-19"
WINDOW = window_for(datetime(2026, 10, 19, tzinfo=UTC))
REGISTRIES = Registries.load()
CALENDAR = fixture("eisa", "calendar.html", DAY)
SERVED = {
    URL: CALENDAR,
    AJAX.format(table_id="38978"): fixture("eisa", "y2026.json", DAY),
    AJAX.format(table_id="34700"): fixture("eisa", "y2025.json", DAY),
}
RAW = RawPages("eisa", tuple(Eisa().fetch(WINDOW, Served(SERVED), Deadline.after(60))), ())
RES = Eisa().parse(RAW, WINDOW, REGISTRIES)
NOTE_2027 = Reason("not_published_yet", "no heading 'eisa african election calendar 2027'")
H26 = "EISA African Election Calendar 2026"


def eisa_cal(headings: list[tuple[str, str | None]]) -> bytes:
    parts = []
    for title, table_id in headings:
        table = f'<table class="foo" data-footable_id="{table_id}"></table>' if table_id else ""
        parts.append(
            '<div class="footable_parent ninja_table_wrapper">'
            f'<h3 class="table_title footable_title">{title}</h3>{table}</div>'
        )
    return ("<!DOCTYPE html><html><body>" + "".join(parts) + "</body></html>").encode()


def rows(*vals: tuple[str, str, str]) -> bytes:
    return json.dumps(
        [
            {"options": {"classes": ""}, "value": {"country": c, "election": e, "date": d, "___id___": i}}
            for i, (c, e, d) in enumerate(vals, 1)
        ]
    ).encode()


def table_of(*elements: Any) -> bytes:
    return json.dumps(list(elements)).encode()


CAL26 = eisa_cal([(H26, "1")])


def raw_of(cal: bytes, tables: Mapping[int, bytes], unfinished: tuple[PageRequest, ...] = ()) -> RawPages:
    pages = [(PageRequest("calendar", URL), result(cal))]
    for year, body in tables.items():
        pages.append((PageRequest(f"y{year}", AJAX.format(table_id="1"), year), result(body)))
    return raw_pages("eisa", pages, unfinished)


def parse(raw: RawPages, window: Window = WINDOW, *, balanced: bool = True) -> ParseResult:
    res = Eisa().parse(raw, window, REGISTRIES)
    if balanced:
        assert check(raw, res).ok
    return res


def run(
    tables: Mapping[int, bytes], cal: bytes = CAL26, window: Window = WINDOW, *, balanced: bool = True
) -> ParseResult:
    return parse(raw_of(cal, tables), window, balanced=balanced)


def y26(*vals: tuple[str, str, str]) -> ParseResult:
    return run({2026: rows(*vals)})


def detail(res: ParseResult, key: str) -> tuple[str, str]:
    cov = next(c for c in res.coverage if c.key == key)
    return cov.outcome, cov.detail


def units(res: ParseResult) -> dict[str, InputUnit]:
    return {u.unit_id: u for u in res.units}


def claims(res: ParseResult, uid: str) -> list[Claim]:
    return [c for c in res.claims if c.unit_id == f"eisa:y2026/{uid}"]


def year_notes(res: ParseResult) -> list[Reason]:
    return [r for r in res.reasons if r.code in ("not_published_yet", "required_year_missing")]


def test_fixture_ledger_balances() -> None:
    report = check(RAW, RES)
    assert report.ok and RES.reasons == (NOTE_2027,)
    assert report.outcomes == {"parsed": 20, "partial": 0, "unparsed": 2, "ignored": 0}
    assert [(c.key, c.outcome, c.units_seen, c.year) for c in RES.coverage] == [
        ("calendar", "ok", 0, None),
        ("y2026", "ok", 22, 2026),
    ]
    assert len(RES.claims) == 25


def test_fixture_values() -> None:
    C = RES.claims
    assert Counter(c.level for c in C) == {"national": 22, "subnational": 3}
    assert Counter(c.office_class for c in C) == {
        "head_of_state": 9,
        "legislature": 6,
        "lower_house": 5,
        "local_council": 3,
        "general": 1,
        "upper_house": 1,
    }
    assert Counter(c.span.precision for c in C) == {"day": 19, "month": 3, "year": 3}
    assert Counter(c.date_meaning for c in C) == {"voting_period": 18, "unknown": 6, "expected_window": 1}
    assert Counter(c.status_claim for c in C) == {"held": 13, None: 10, "postponed": 2}
    assert {c.link for c in C} == {URL} and {c.jurisdiction for c in C} == {None}
    assert Counter(u.relevance for u in RES.units) == {"unknown": 13, "in_or_after_window": 9}
    assert [(u.unit_id, u.reason, u.leftover, u.relevance) for u in RES.units if u.outcome != "parsed"] == [
        ("eisa:y2026/r11", "no_new_date", "Postponed from April 2026", "unknown"),
        ("eisa:y2026/r12", "no_new_date", "Postponed from April 2026", "unknown"),
    ]


def test_in_window_claims() -> None:
    assert sorted(
        (c.span.start.isoformat(), c.place_id, c.office_class, c.level, c.span.precision)
        for c in RES.claims
        if WINDOW.overlaps(c.span) and c.span.start is not None
    ) == [
        ("2026-09-23", "iso:MA", "lower_house", "national", "day"),
        ("2026-09-27", "iso:ST", "legislature", "national", "day"),
        ("2026-10-01", "iso:CV", "head_of_state", "national", "month"),
        ("2026-11-01", "iso:ZA", "local_council", "subnational", "month"),
        ("2026-12-01", "iso:CM", "lower_house", "national", "month"),
        ("2026-12-05", "iso:GM", "head_of_state", "national", "day"),
        ("2026-12-22", "iso:SS", "head_of_state", "national", "day"),
        ("2026-12-22", "iso:SS", "legislature", "national", "day"),
    ]


def test_claims_field_by_field() -> None:
    C = {c.claim_id: c for c in RES.claims}
    U = units(RES)
    b0, b1 = C["eisa:y2026/r3#0"], C["eisa:y2026/r3#1"]
    assert (b0.office_class, b0.institution, b0.level) == ("lower_house", "iso:BJ/national-assembly", "national")
    assert (b1.office_class, b1.institution, b1.level) == ("local_council", None, "subnational")
    assert b1.aggregate is True and b1.office_label == "local"
    for c in (b0, b1):
        assert c.span == DateSpan.day(date(2026, 1, 11))
        assert (c.date_meaning, c.status_claim) == ("voting_period", "held")
    cv = C["eisa:y2026/r7#0"]
    assert U["eisa:y2026/r7"].text == "Cape Verde (from the row above) | Presidential | October 2026"
    assert cv.place_raw == "Cape Verde" and cv.span == DateSpan.month(2026, 10)
    assert (cv.date_meaning, cv.office_class) == ("unknown", "head_of_state")
    assert U["eisa:y2026/r12"].text == (
        "Libya (from the row above) | House of Representatives | Postponed from April 2026"
    )
    assert [u.unit_id for u in RES.units if "(from the row above)" in u.text] == [
        f"eisa:y2026/r{n}" for n in (4, 7, 12, 15)
    ]
    gm = C["eisa:y2026/r10#0"]
    assert (gm.institution, gm.span, gm.date_meaning) == (
        "iso:GM/president",
        DateSpan.day(date(2026, 12, 5)),
        "voting_period",
    )
    assert (gm.status_claim, gm.date_text) == (None, "5 December 2026")
    s0, s1 = C["eisa:y2026/r16#0"], C["eisa:y2026/r16#1"]
    for c in (s0, s1):
        assert c.place_id == "x:somaliland" and c.span == DateSpan.of_year(2028)
        assert (c.status_claim, c.previous_date_text) == ("postponed", "June 2026")
    assert (s0.office_class, s0.office_label) == ("lower_house", "House of Representatives")
    assert (s1.office_class, s1.office_label) == ("upper_house", "House of Elders (Guitr)")
    so = C["eisa:y2026/r17#0"]
    assert so.span == DateSpan.days(date(2026, 5, 10), date(2026, 7, 30))
    assert (so.date_meaning, so.office_class, so.level) == ("unknown", "local_council", "subnational")
    za = C["eisa:y2026/r18#0"]
    assert (za.span.precision, za.span.start, za.span.end) == ("month", date(2026, 11, 1), date(2027, 1, 31))
    assert za.date_meaning == "expected_window"
    ss0, ss1 = C["eisa:y2026/r19#0"], C["eisa:y2026/r19#1"]
    assert (ss0.office_class, ss0.institution) == ("head_of_state", "iso:SS/president")
    assert (ss1.office_class, ss1.institution, ss1.aggregate) == ("legislature", None, True)
    for c in (ss0, ss1):
        assert c.level == "national" and c.span == DateSpan.day(date(2026, 12, 22))
    eh = C["eisa:y2026/r22#0"]
    assert (eh.place_id, eh.span, eh.office_class) == ("iso:EH", DateSpan.of_year(2026), "legislature")


def chained(day: datetime) -> tuple[Served, RawPages, ParseResult, Window]:
    window = window_for(day)
    served = Served(SERVED)
    raw = RawPages("eisa", tuple(Eisa().fetch(window, served, Deadline.after(60))), ())
    return served, raw, parse(raw, window), window


def test_chain_by_window() -> None:
    served, _raw, res, _w = chained(datetime(2026, 10, 19, tzinfo=UTC))
    assert served.asked == [URL, AJAX.format(table_id="38978")]
    assert [(c.key, c.outcome, c.units_seen, c.year) for c in res.coverage] == [
        ("calendar", "ok", 0, None),
        ("y2026", "ok", 22, 2026),
    ]
    assert res.reasons == (NOTE_2027,) and (len(res.units), len(res.claims)) == (22, 25)

    served, _raw, res, _w = chained(datetime(2027, 1, 10, tzinfo=UTC))
    assert served.asked == [URL, AJAX.format(table_id="38978")]
    assert [(c.key, c.outcome, c.units_seen, c.year) for c in res.coverage] == [
        ("calendar", "ok", 0, None),
        ("y2026", "ok", 22, 2026),
    ]
    assert res.reasons == (
        Reason("required_year_missing", "no heading 'eisa african election calendar 2027'"),
    )
    assert (len(res.units), len(res.claims)) == (22, 25)

    served, raw, res, _w = chained(datetime(2025, 11, 15, tzinfo=UTC))
    assert served.asked == [URL, AJAX.format(table_id="34700"), AJAX.format(table_id="38978")]
    assert [(c.key, c.outcome, c.units_seen, c.year) for c in res.coverage] == [
        ("calendar", "ok", 0, None),
        ("y2025", "ok", 23, 2025),
        ("y2026", "ok", 22, 2026),
    ]
    assert res.reasons == ()
    assert (len(res.units), len(res.claims)) == (45, 57)
    assert check(raw, res).outcomes == {"parsed": 41, "partial": 0, "unparsed": 4, "ignored": 0}
    U = units(res)
    assert (U["eisa:y2025/r4"].reason, U["eisa:y2025/r4"].leftover) == ("date_unparsed", "Extended to 2026")
    assert (U["eisa:y2025/r18"].reason, U["eisa:y2025/r18"].leftover) == (
        "date_unparsed",
        "Postponed indefinitely from 2025",
    )
    rounds = {c.claim_id: c.round for c in res.claims if c.round is not None and c.unit_id.startswith("eisa:y2025")}
    assert rounds == {
        "eisa:y2025/r9#0": 1,
        "eisa:y2025/r10#0": 2,
        "eisa:y2025/r19#0": 1,
        "eisa:y2025/r19#1": 1,
        "eisa:y2025/r20#0": 2,
        "eisa:y2025/r20#1": 2,
    }


def cal_result(cal: bytes, window: Window = WINDOW) -> tuple[ParseResult, RawPages]:
    raw = raw_pages("eisa", [(PageRequest("calendar", URL), result(cal))])
    return Eisa().parse(raw, window, REGISTRIES), raw


def asked_keys(cal: bytes, window: Window = WINDOW) -> list[tuple[str, str]]:
    raw = raw_pages("eisa", [(PageRequest("calendar", URL), result(cal))])
    return [(r.key, r.url) for r in expected(window, raw.pages)][1:]


def test_calendar_headings() -> None:
    heading = "heading 'eisa african election calendar 2026' has table ids "
    res, _ = cal_result(CALENDAR[:100000])
    assert detail(res, "calendar") == ("layout_not_recognised", "page does not end with </html>")
    assert asked_keys(CALENDAR[:100000]) == []
    res, _ = cal_result(eisa_cal([(H26, "38978"), (H26, "99999")]))
    assert detail(res, "calendar") == ("layout_not_recognised", heading + "38978, 99999")
    assert asked_keys(eisa_cal([(H26, "38978"), (H26, "99999")])) == []
    res, _ = cal_result(eisa_cal([(H26, None)]))
    assert detail(res, "calendar") == ("layout_not_recognised", heading + "(none)")
    res, _ = cal_result(eisa_cal([(H26, "abc")]))
    assert detail(res, "calendar") == ("layout_not_recognised", heading + "abc")
    twice = eisa_cal([(H26, "38978"), (H26, "38978")])
    res, _ = cal_result(twice)
    assert detail(res, "calendar") == ("ok", "")
    assert [k for k, _ in asked_keys(twice)] == ["y2026"]
    only25 = eisa_cal([("EISA African Election Calendar 2025", "34700")])
    res, _ = cal_result(only25)
    assert year_notes(res) == [
        Reason("required_year_missing", "no heading 'eisa african election calendar 2026'"),
        Reason("not_published_yet", "no heading 'eisa african election calendar 2027'"),
    ]
    both = eisa_cal([(H26, "38978"), ("EISA African Election Calendar 2027", "40001")])
    res, _ = cal_result(both)
    assert year_notes(res) == []
    assert asked_keys(both) == [
        ("y2026", AJAX.format(table_id="38978")),
        ("y2027", AJAX.format(table_id="40001")),
    ]
    messy = eisa_cal([("  eisa  AFRICAN election calendar 2026 ", "38978")])
    assert [k for k, _ in asked_keys(messy)] == ["y2026"]
    other = eisa_cal([("EISA Comprehensive African Election Calendar", "1"), ("Election Calendar 2026", "2")])
    res, _ = cal_result(other)
    assert detail(res, "calendar") == ("ok", "")
    assert [r.code for r in year_notes(res)] == ["required_year_missing", "not_published_yet"]
    assert asked_keys(other) == []


def test_broken_json() -> None:
    cases = {
        b"<html>error</html>": "the body is not JSON",
        b"0": "the body is not a JSON list",
        b"-1": "the body is not a JSON list",
        b'{"success": false}': "the body is not a JSON list",
        b'{"data": []}': "the body is not a JSON list",
        b"[]": "the table has no rows",
        b'[{"value": {"name": "x"}}, 3]': "no row has country, election and date",
        b"[" * 100000: "the body is not JSON",
    }
    for body, message in cases.items():
        res = run({2026: body})
        assert detail(res, "y2026") == ("layout_not_recognised", message), body[:20]
        assert res.units == () and res.claims == ()


def test_row_kinds_and_inheritance() -> None:
    chad = {"value": {"country": "Chad", "election": "Presidential", "date": "5 December 2026"}}
    gap = {"value": {"country": "", "election": "National Assembly", "date": "5 December 2026"}}
    bad = {"value": {"country": 7, "election": "x", "date": "y"}}
    res = run({2026: table_of(chad, "junk", gap, bad)})
    U = units(res)
    assert [(u.unit_id, u.outcome, u.reason) for u in res.units] == [
        ("eisa:y2026/r1", "parsed", None),
        ("eisa:y2026/r2", "unparsed", "row_unrecognised"),
        ("eisa:y2026/r3", "unparsed", "place_missing"),
        ("eisa:y2026/r4", "unparsed", "row_unrecognised"),
    ]
    assert U["eisa:y2026/r2"].text == '"junk"' and U["eisa:y2026/r2"].relevance == "unknown"
    assert U["eisa:y2026/r4"].text == json.dumps(bad, sort_keys=True)

    cal = eisa_cal([(H26, "1"), ("EISA African Election Calendar 2027", "2")])
    res = run(
        {
            2026: rows(("Chad", "Local", "Nov 2026 - Jan 2027")),
            2027: rows(("", "Senate", "5 January 2027"), ("Chad", "Local", "Nov 2026 - Jan 2027")),
        },
        cal,
    )
    U = units(res)
    assert (U["eisa:y2027/r1"].outcome, U["eisa:y2027/r1"].reason) == ("unparsed", "place_missing")
    r2 = U["eisa:y2027/r2"]
    assert (r2.outcome, r2.reason, r2.duplicate_of) == ("ignored", "duplicate", "eisa:y2026/r1")
    assert [c.claim_id for c in res.claims] == ["eisa:y2026/r1#0"]

    texts = []
    for first in ("Libya", "Chad"):
        res = y26(
            (first, "Presidential", "Postponed from April 2026"),
            ("", "House of Representatives", "Postponed from April 2026"),
        )
        U = units(res)
        assert [(u.outcome, u.reason) for u in res.units] == [("unparsed", "no_new_date")] * 2
        texts.append(U["eisa:y2026/r2"].text)
    assert texts == [
        "Libya (from the row above) | House of Representatives | Postponed from April 2026",
        "Chad (from the row above) | House of Representatives | Postponed from April 2026",
    ]


def test_row_grammar() -> None:
    table = [
        ("", "Presidential", "5 December 2026", "unparsed", "place_missing", ""),
        ("Chad", "Presidential", "Postponed from April 2026", "unparsed", "no_new_date", "Postponed from April 2026"),
        ("Chad", "Senate", "Postponed from June 2026 to 2028", "parsed", None, ""),
        ("Chad", "Presidential", "Held 2 July 2026", "parsed", None, ""),
        ("Chad", "Local", "Nov 2026 - Jan 2027", "parsed", None, ""),
        ("Chad", "Regional and local", "Stagerred: 10 May 2026 - 30 July 2026", "parsed", None, ""),
        ("Chad", "Senate", "2026", "parsed", None, ""),
        ("Chad", "Senate", "TBD", "unparsed", "date_missing", ""),
        ("Chad", "Senate", "", "unparsed", "date_missing", ""),
        ("Chad", "", "5 December 2026", "unparsed", "office_missing", ""),
        ("Chad", "President", "Second Round: Held 9 - 11 Oct 2026", "parsed", None, ""),
        ("Chad", "President", "First Round: 13 Sep 2026", "parsed", None, ""),
        ("Chad", "National Assembly", "Held 13 May 2026 (first round)", "parsed", None, ""),
        ("Chad", "National Assembly", "Held 27 May 2026 (second round)", "parsed", None, ""),
        ("Chad", "House of Assembly", "Held 29 Jan 2026 (runoff)", "parsed", None, ""),
        ("Chad", "House of Assembly", "Held18 June 2026", "unparsed", "date_unparsed", "Held18 June 2026"),
        ("Chad", "President and National Assembly", "5 December 2026", "parsed", None, ""),
        ("Chad", "Regional and local", "5 December 2026", "parsed", None, ""),
        ("Narnia", "Presidential", "5 December 2026", "partial", "place_unregistered", ""),
        ("Chad", "Presidential", "5 December 2036", "unparsed", "implausible_date", ""),
        ("Chad", "Presidential", "Cancelled 5 December 2026", "parsed", None, ""),
        ("Chad", "Presidential", "December 2026", "parsed", None, ""),
        ("Chad", "Prime Minister", "5 December 2026", "partial", "office_unrecognised", ""),
        ("Chad", "Presidential", "10, 11, 12 Dec 2026", "unparsed", "date_unparsed", "10, 11, 12 Dec 2026"),
        ("Chad", "Lieutenant Governor", "5 December 2026", "unparsed", "office_not_modelled", "Lieutenant Governor"),
    ]
    res = y26(*[(c, e, d) for c, e, d, *_ in table])
    got = [(u.outcome, u.reason, u.leftover) for u in res.units]
    assert got == [(o, r, left) for *_, o, r, left in table]

    def one(n: int) -> Claim:
        (c,) = claims(res, f"r{n}")
        return c

    c3 = one(3)
    assert (c3.span, c3.status_claim, c3.previous_date_text) == (DateSpan.of_year(2028), "postponed", "June 2026")
    c4 = one(4)
    assert (c4.span, c4.date_meaning, c4.status_claim) == (DateSpan.day(date(2026, 7, 2)), "voting_period", "held")
    c5 = one(5)
    assert (c5.span.precision, c5.date_meaning, c5.level) == ("month", "expected_window", "subnational")
    c6 = one(6)
    assert (c6.span, c6.date_meaning) == (DateSpan.days(date(2026, 5, 10), date(2026, 7, 30)), "unknown")
    c7 = one(7)
    assert (c7.span, c7.date_meaning) == (DateSpan.of_year(2026), "unknown")
    c11 = one(11)
    assert (c11.span, c11.date_meaning, c11.status_claim, c11.round) == (
        DateSpan.days(date(2026, 10, 9), date(2026, 10, 11)),
        "unknown",
        "held",
        2,
    )
    c12 = one(12)
    assert (c12.date_meaning, c12.round, c12.span) == ("voting_period", 1, DateSpan.day(date(2026, 9, 13)))
    assert [one(n).round for n in (13, 14, 15)] == [1, 2, 2]
    assert [c.office_class for c in claims(res, "r17")] == ["head_of_state", "lower_house"]
    c18 = one(18)
    assert c18.office_class == "local_council"
    c19 = one(19)
    assert (c19.place_id, c19.place_raw) == ("unknown:narnia", "Narnia")
    c21 = one(21)
    assert (c21.date_meaning, c21.status_claim) == ("voting_period", "cancelled")
    c22 = one(22)
    assert (c22.span, c22.date_meaning) == (DateSpan.month(2026, 12), "unknown")
    c23 = one(23)
    assert (c23.office_class, c23.level) == ("general", "unknown")
    assert [u.unit_id for u in res.units if not claims(res, u.unit_id.split("/")[1])] == [
        f"eisa:y2026/r{n}" for n in (1, 2, 8, 9, 10, 16, 20, 24, 25)
    ]


def test_table_year_check() -> None:
    gap = Reason("coverage_gap", "y2026 has no 2026 date")
    res = y26(("Chad", "Presidential", "10 January 2027"))
    assert units(res)["eisa:y2026/r1"].outcome == "parsed" and res.reasons[-1] == gap
    res = y26(("Chad", "Presidential", "5 December 2018"), ("Chad", "Senate", "10 May 2019"))
    assert [(u.outcome, u.reason, u.relevance) for u in res.units] == [
        ("unparsed", "implausible_date", "before_window")
    ] * 2
    assert gap in res.reasons
    res = y26(("Chad", "Presidential", "TBD"), ("Chad", "Senate", "TBD"))
    assert [(u.outcome, u.reason) for u in res.units] == [("unparsed", "date_missing")] * 2
    assert gap not in res.reasons
    res = y26(("Chad", "Presidential", "5 December 2026"), ("Chad", "Senate", "Postponed from June 2026 to 2028"))
    assert [u.outcome for u in res.units] == ["parsed"] * 2 and gap not in res.reasons
    res = y26(("Chad", "Local", "Nov 2025 - Jan 2026"))
    assert units(res)["eisa:y2026/r1"].outcome == "parsed" and gap not in res.reasons
    res = y26(("Chad", "Presidential", "First Round: 10 January 2027"))
    assert gap in res.reasons


def test_rounds_and_parts() -> None:
    res = y26(
        ("Chad", "Presidential Run-off", "First Round: 13 Sep 2026"),
        ("Chad", "President (2nd round)", "Held 27 May 2026 (second round)"),
        ("Chad", "President and Xyz", "5 December 2026"),
        ("Nigeria", "Osun Governor and State Assembly", "5 December 2026"),
        ("Chad", "President (runoff) and National Assembly", "First Round: 13 Sep 2026"),
        ("Nigeria", "State Assembly", "5 December 2026"),
        ("Nigeria", "Presidential and Osun Governor", "5 December 2026"),
        ("Nigeria", "Osun Governor and Lagos State Assembly", "7 December 2026"),
    )
    assert [(u.outcome, u.reason, u.leftover) for u in res.units] == [
        ("partial", "round_conflict", "First Round:"),
        ("parsed", None, ""),
        ("partial", "office_unrecognised", "Xyz"),
        ("parsed", None, ""),
        ("partial", "round_conflict", "First Round:"),
        ("parsed", None, ""),
        ("parsed", None, ""),
        ("parsed", None, ""),
    ]
    (c,) = claims(res, "r1")
    assert (c.office_class, c.round) == ("head_of_state", None)
    (c,) = claims(res, "r2")
    assert (c.office_class, c.round) == ("head_of_state", 2)
    (c,) = claims(res, "r3")
    assert (c.office_class, c.office_label) == ("head_of_state", "President and Xyz")
    a, b = claims(res, "r4")
    assert (a.office_class, b.office_class) == ("governor", "legislature")
    for c in (a, b):
        assert (c.level, c.jurisdiction, c.jurisdiction_kind) == ("subnational", "Osun", "subdivision")
    a, b = claims(res, "r5")
    assert (a.office_class, a.round) == ("head_of_state", None)
    assert (b.office_class, b.institution, b.round) == ("lower_house", "iso:TD/national-assembly", 1)
    (c,) = claims(res, "r6")
    assert (c.office_class, c.level, c.jurisdiction, c.jurisdiction_kind) == (
        "legislature",
        "subnational",
        None,
        "nationwide",
    )
    a, b = claims(res, "r7")
    assert (a.office_class, a.institution, a.level, a.jurisdiction) == (
        "head_of_state",
        "iso:NG/president",
        "national",
        None,
    )
    assert (b.office_class, b.level, b.jurisdiction) == ("governor", "subnational", "Osun")
    a, b = claims(res, "r8")
    assert (a.office_class, a.level, a.jurisdiction) == ("governor", "subnational", "Osun")
    assert (b.office_class, b.level, b.jurisdiction) == ("legislature", "subnational", "Lagos State")


def test_pagination_failures_are_loud() -> None:
    raw = raw_pages("eisa", [(PageRequest("calendar", URL), result(CALENDAR))])
    res = parse(raw)
    assert res.reasons == (NOTE_2027, Reason("pagination_incomplete", "y2026 was not fetched"))
    url = AJAX.format(table_id="38978")
    raw = raw_pages(
        "eisa",
        [
            (PageRequest("calendar", URL), result(CALENDAR)),
            (PageRequest("y2026", url, 2026), result(b"", outcome="timeout", status=None)),
        ],
    )
    res = parse(raw)
    assert [(c.key, c.outcome, c.year) for c in res.coverage] == [("calendar", "ok", None), ("y2026", "timeout", 2026)]
    assert res.notes == (NOTE_2027,)
    raw = RawPages("eisa", (), (PageRequest("calendar", URL),))
    res = parse(raw)
    assert [(c.key, c.outcome, c.units_seen) for c in res.coverage] == [("calendar", "unfinished", 0)]
    assert res.notes == ()


def test_content_never_raises() -> None:
    deep = b"<!DOCTYPE html><html><body>" + b"<div>" * 3000 + b"</body></html>"
    res = parse(raw_pages("eisa", [(PageRequest("calendar", URL), result(deep))]), balanced=False)
    assert res.coverage[0].outcome in ("layout_not_recognised", "ok")
    res = run({2026: b'{"a":' * 100000})
    assert detail(res, "y2026") == ("layout_not_recognised", "the body is not JSON")


def test_count_rule_matches_the_adapter() -> None:
    assert COUNT_RULES["eisa"] == JsonListRule(frozenset({"calendar"}))


def test_requests_are_the_calendar_only() -> None:
    assert Eisa().requests(WINDOW) == (PageRequest("calendar", URL),)
    assert Eisa().source == "eisa"
