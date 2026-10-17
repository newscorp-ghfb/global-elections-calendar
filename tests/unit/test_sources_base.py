"""The adapter contract (spec §8, §9.4)."""

from datetime import datetime, timedelta, timezone

import pytest

from elections_calendar.fetch import Deadline, FetchResult
from elections_calendar.model import Reason, RecordError
from elections_calendar.offices import InstitutionRegistry
from elections_calendar.places import PlaceRegistry, SubdivisionIndex
from elections_calendar.sources.base import (
    PageCoverage,
    PageRequest,
    ParseResult,
    RawPage,
    Registries,
    coverage_reasons,
    fetch_pages,
    page_failure,
)
from tests.support.pages import FETCHED, raw_pages, result


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
