"""The adapter contract (spec §8, §9.4)."""

from datetime import datetime, timedelta, timezone
from typing import get_args

import pytest

from elections_calendar.fetch import Deadline, FetchResult
from elections_calendar.model import MAX_DETAIL, Reason, ReasonCode, RecordError
from elections_calendar.offices import InstitutionRegistry
from elections_calendar.places import PlaceRegistry, SubdivisionIndex
from elections_calendar.sources.base import (
    PAGE_REASONS,
    PageCoverage,
    PageOutcome,
    PageParse,
    PageRequest,
    ParseResult,
    RawPage,
    Registries,
    coverage_reasons,
    fetch_pages,
    page_failure,
    parse_pages,
)
from tests.support.pages import FETCHED, claim, raw_pages, result, unit


class StubGetter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool, Deadline]] = []

    def get(self, url: str, *, deadline: Deadline, mediawiki: bool = False) -> FetchResult:
        self.calls.append((url, mediawiki, deadline))
        return result(b"x", url=url)


def test_fetch_pages_fetches_one_at_a_time_in_order() -> None:
    reqs = [
        PageRequest("a", "https://example.test/a"),
        PageRequest("b", "https://example.test/b", 2026, mediawiki=True),
        PageRequest("c", "https://example.test/c"),
    ]
    getter = StubGetter()
    deadline = Deadline.after(60)
    pages = fetch_pages(reqs, getter, deadline, now=lambda: FETCHED)
    assert getter.calls == []  # lazy: nothing before the first next()
    first = next(pages)
    assert [c[0] for c in getter.calls] == ["https://example.test/a"]
    rest = list(pages)
    assert [c[:2] for c in getter.calls] == [
        ("https://example.test/a", False),
        ("https://example.test/b", True),
        ("https://example.test/c", False),
    ]
    assert all(c[2] is deadline for c in getter.calls)
    got = [first, *rest]
    assert all(p.fetched_at == FETCHED for p in got)
    assert all(p.request is r for p, r in zip(got, reqs, strict=True))


def test_fetch_pages_stamps_an_aware_time_by_default() -> None:
    request = PageRequest("a", "https://example.test/a")
    (page,) = fetch_pages([request], StubGetter(), Deadline.after(60))
    assert page.fetched_at.utcoffset() == timedelta(0)


def test_a_raw_page_needs_an_aware_fetch_time() -> None:
    req = PageRequest("upcoming", "https://example.test/")
    with pytest.raises(RecordError):
        RawPage(req, result(b""), datetime(2026, 10, 16, 14, 39))
    aware = datetime(2026, 10, 16, 16, 39, tzinfo=timezone(timedelta(hours=2)))
    assert RawPage(req, result(b""), aware).fetched_at.utcoffset()


def test_a_redirect_without_location_is_an_http_error() -> None:
    req = PageRequest("upcoming", "https://example.test/")
    for status in (300, 302, 399):
        assert page_failure(RawPage(req, result(b"", status=status), FETCHED)) == "http_error"
    assert page_failure(RawPage(req, result(b"", status=299), FETCHED)) is None
    timed_out = result(b"", outcome="timeout", status=None)
    assert page_failure(RawPage(req, timed_out, FETCHED)) == "timeout"
    assert page_failure(RawPage(req, result(b"<html></html>"), FETCHED)) is None


def test_page_outcomes_give_reasons() -> None:
    cov = [
        PageCoverage("a", None, "ok", "s:a/", 3),
        PageCoverage("b", 2027, "not_published_yet", None, 0),
        PageCoverage("c", 2026, "unfinished", None, 0),
        PageCoverage("d", None, "challenge_page", None, 0),
        PageCoverage("e", None, "valid_empty", "s:e/", 0),
    ]
    assert coverage_reasons(cov) == (
        Reason("not_published_yet", "b"),
        Reason("deadline", "c"),
        Reason("challenge_page", "d"),
    )


def test_a_unit_prefix_is_set_exactly_for_ok_and_valid_empty_pages() -> None:
    with pytest.raises(RecordError):
        PageCoverage("a", None, "ok", None, 0)
    with pytest.raises(RecordError):
        PageCoverage("b", None, "timeout", "s:b/", 0)
    with pytest.raises(RecordError):
        PageCoverage("b", None, "valid_empty", None, 0)
    assert PageCoverage("b", None, "timeout", None, 0).unit_prefix is None


def test_layout_ok_and_reasons_of_a_parse_result() -> None:
    good = ParseResult("s", (), (), (PageCoverage("a", None, "ok", "s:a/", 1),))
    assert good.layout_ok
    assert good.reasons == ()
    bad = ParseResult(
        "s",
        (),
        (),
        (PageCoverage("a", None, "layout_not_recognised", None, 0),),
        (Reason("count_change", "n"),),
    )
    assert not bad.layout_ok
    assert bad.reasons == (Reason("layout_not_recognised", "a"), Reason("count_change", "n"))


def test_raw_pages_helper_builds_pages_at_the_fixed_time() -> None:
    req = PageRequest("a", "https://example.test/a")
    raw = raw_pages("s", [(req, result(b"x"))], (PageRequest("b", "https://example.test/b"),))
    assert raw.pages[0].fetched_at == FETCHED
    assert raw.unfinished[0].key == "b"


def test_registries_load_the_default_data() -> None:
    reg = Registries.load()
    assert isinstance(reg.places, PlaceRegistry)
    assert isinstance(reg.institutions, InstitutionRegistry)
    assert isinstance(reg.subdivisions, SubdivisionIndex)


def test_a_page_detail_follows_the_page_key_in_its_reason() -> None:
    page = PageCoverage("p", 2026, "layout_not_recognised", None, 0, detail="section May: text in <p>")
    assert coverage_reasons([page]) == (
        Reason("layout_not_recognised", "p: section May: text in <p>"),
    )
    long = PageCoverage("p", 2026, "layout_not_recognised", None, 0, detail="x" * 1000)
    (reason,) = coverage_reasons([long])
    assert reason.detail == ("p: " + "x" * 1000)[:300]


def test_only_a_page_without_units_has_a_detail() -> None:
    for outcome in ("ok", "valid_empty"):
        with pytest.raises(RecordError):
            PageCoverage("a", None, outcome, "s:a/", 0, detail="why")
    assert PageCoverage("a", None, "timeout", None, 0, detail="why").detail == "why"


def test_every_page_outcome_without_units_maps_to_a_reason_code() -> None:
    without_units = [o for o in get_args(PageOutcome) if o not in ("ok", "valid_empty")]
    assert sorted(PAGE_REASONS) == sorted(without_units)
    assert set(PAGE_REASONS.values()) <= set(get_args(ReasonCode))
    for outcome in without_units:
        page = PageCoverage("p", None, outcome, None, 0)
        assert coverage_reasons([page]) == (Reason(PAGE_REASONS[outcome], "p"),)
    assert PAGE_REASONS["unfinished"] == "deadline"
    assert all(PAGE_REASONS[o] == o for o in without_units if o != "unfinished")


def _pages(*specs: tuple[str, bytes, dict[str, object]]):  # type: ignore[no-untyped-def]
    return raw_pages(
        "s",
        [
            (PageRequest(key, f"https://example.test/{key}"), result(body, **kw))  # type: ignore[arg-type]
            for key, body, kw in specs
        ],
    )


def test_parse_pages() -> None:
    calls: list[str] = []

    def parse_page(page: RawPage) -> PageParse:
        calls.append(page.request.key)
        key = page.request.key
        if key == "a":
            uid = "s:a/r1"
            return PageParse(
                "ok", [unit("s", uid)], [claim(uid)], year=2026, notes=[Reason("count_change", "n")]
            )
        if key == "b":
            return PageParse("valid_empty", notes=[Reason("coverage_gap", "g")])
        if key == "c":
            return PageParse(
                "layout_not_recognised",
                [unit("s", "s:c/r1")],
                [claim("s:c/r1")],
                "d" * 500,
                notes=[Reason("count_change", "lost")],
            )
        if key == "d":
            raise RecursionError
        return PageParse("not_published_yet", detail="soon")

    raw = _pages(
        ("a", b"x", {}),
        ("down", b"", {"outcome": "timeout", "status": None}),
        ("b", b"x", {}),
        ("c", b"x", {}),
        ("d", b"x", {}),
        ("e", b"x", {}),
    )
    raw = type(raw)(raw.source, raw.pages, (PageRequest("late", "https://example.test/late", 2027),))
    out = parse_pages("s", raw, parse_page)
    assert calls == ["a", "b", "c", "d", "e"]  # never the failed download
    assert [(c.key, c.outcome, c.unit_prefix, c.units_seen, c.year) for c in out.coverage] == [
        ("a", "ok", "s:a/", 1, 2026),
        ("down", "timeout", None, 0, None),
        ("b", "valid_empty", "s:b/", 0, None),
        ("c", "layout_not_recognised", None, 0, None),
        ("d", "layout_not_recognised", None, 0, None),
        ("e", "not_published_yet", None, 0, None),
        ("late", "unfinished", None, 0, 2027),
    ]
    assert [c.detail for c in out.coverage] == [
        "", "", "", "d" * MAX_DETAIL, "nested too deep", "soon", ""
    ]
    assert [u.unit_id for u in out.units] == ["s:a/r1"]
    assert [c.claim_id for c in out.claims] == ["s:a/r1#0"]
    assert out.notes == (Reason("count_change", "n"), Reason("coverage_gap", "g"))
    assert out.source == "s"
