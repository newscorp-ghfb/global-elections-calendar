"""The adapter contract (spec §8, §9.4)."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta, timezone
from typing import get_args

import pytest

from elections_calendar.fetch import Deadline, FetchResult
from elections_calendar.model import MAX_DETAIL, Reason, ReasonCode, RecordError
from elections_calendar.offices import InstitutionRegistry
from elections_calendar.places import Place, PlaceRegistry, SubdivisionIndex
from elections_calendar.runner import DEFAULT_ADAPTERS, _load
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
    fetch_chain,
    fetch_pages,
    label_scope,
    missing_pages,
    page_failure,
    parse_pages,
    part_scopes,
)
from elections_calendar.window import window_for
from tests.support.pages import FETCHED, Served, claim, raw_pages, result, unit


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
        Reason("not_published_yet", "b", page="b", year=2027),
        Reason("deadline", "c", page="c", year=2026),
        Reason("challenge_page", "d", page="d", year=None),
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
    assert bad.reasons == (
        Reason("layout_not_recognised", "a", page="a", year=None),
        Reason("count_change", "n"),
    )


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
        Reason("layout_not_recognised", "p: section May: text in <p>", page="p", year=2026),
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
        assert coverage_reasons([page]) == (Reason(PAGE_REASONS[outcome], "p", page="p"),)
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


_REGISTRIES = Registries.load()


@pytest.mark.parametrize(
    ("country", "label", "office_class", "institution", "level", "unresolved"),
    [
        ("Bulgaria", "Presidential Election", "head_of_state", "iso:BG/president", "national", False),
        ("United States", "United States Senate election in Ohio", "upper_house", "iso:US/senate", "national", False),
        ("United States", "Ohio State Senate election", "upper_house", None, "subnational", False),
        ("United Kingdom", "Referendum in Scotland", "referendum", None, "subnational", False),
        ("Moldova", "Election of Governor of Gagauzia", "governor", None, "subnational", False),
        ("Bosnia and Herzegovina", "Republika Srpska Early Presidential election", "head_of_state", None, "unknown", True),
        ("Pakistan", "2026 Gilgit Baltistan Assembly Election", "legislature", None, "unknown", True),
        ("Mexico", "Mexico General Election", "general", None, "national", False),
        ("Trinidad and Tobago", "Trinidad and Tobago House of Representatives", "lower_house", "iso:TT/house-of-representatives", "national", False),
    ],
)
def test_label_scope_precedence(
    country: str,
    label: str,
    office_class: str,
    institution: str | None,
    level: str,
    unresolved: bool,
) -> None:
    place = _REGISTRIES.places.resolve(country)
    assert place is not None
    scope = label_scope(label, place, _REGISTRIES)
    assert (
        scope.office.office_class,
        scope.office.institution,
        scope.level,
        scope.unresolved,
    ) == (office_class, institution, level, unresolved)


def test_label_scope_of_a_named_subdivision_withholds_the_national_default() -> None:
    place = _REGISTRIES.places.resolve("Pakistan")
    assert place is not None
    scope = label_scope("2026 Gilgit Baltistan Assembly Election", place, _REGISTRIES)
    assert (scope.jurisdiction_kind, scope.jurisdiction, scope.office.aggregate) == (
        "subdivision",
        "Gilgit Baltistan",
        False,
    )
    plain = label_scope("Mexico General Election", _REGISTRIES.places.resolve("Mexico"), _REGISTRIES)  # type: ignore[arg-type]
    assert (plain.jurisdiction_kind, plain.jurisdiction) == ("nationwide", None)


def chain_requests() -> list[PageRequest]:
    return [PageRequest(key, f"https://example.test/{key}") for key in ("p0", "p1", "p2")]


def more_expected(pages: Sequence[RawPage]) -> list[PageRequest]:
    """The first page, then the next one after each page whose body is ``more``."""
    wanted = chain_requests()
    out = wanted[:1]
    for page, nxt in zip(pages, wanted[1:], strict=False):
        if page.result.body != b"more":
            break
        out.append(nxt)
    return out


def test_fetch_chain() -> None:
    urls = [r.url for r in chain_requests()]
    served = Served({urls[0]: b"more", urls[1]: b"more", urls[2]: b"end"})
    pages = list(fetch_chain(more_expected, served, Deadline.after(60), now=lambda: FETCHED))
    assert [p.request.key for p in pages] == ["p0", "p1", "p2"]
    assert served.asked == urls
    assert all(p.fetched_at == FETCHED for p in pages)
    once = Served({urls[0]: b"more"})
    only_first = list(fetch_chain(lambda pages: chain_requests()[:1], once, Deadline.after(60)))
    assert [p.request.key for p in only_first] == ["p0"]
    assert once.asked == urls[:1]


def test_fetch_chain_is_lazy() -> None:
    urls = [r.url for r in chain_requests()]
    served = Served(dict.fromkeys(urls, b"more"))
    pages = fetch_chain(more_expected, served, Deadline.after(60))
    assert served.asked == []
    next(pages)
    assert served.asked == urls[:1]


def test_missing_pages() -> None:
    a, b, c = chain_requests()
    page_a = (a, result(b"x", url=a.url))
    assert missing_pages([a, b, c], raw_pages("s", [page_a], unfinished=(b,))) == [
        Reason("pagination_incomplete", "p2 was not fetched", page="p2")
    ]
    full = raw_pages("s", [page_a, (b, result(b"x")), (c, result(b"x"))])
    assert missing_pages([a, b, c], full) == []


def _place(name: str) -> Place:
    place = _REGISTRIES.places.resolve(name)
    assert place is not None
    return place


@pytest.mark.parametrize(
    ("name", "label", "default", "office_text", "expected"),
    [
        (
            "Nigeria", "Osun Governor and State Assembly", "national", "State Assembly",
            ("legislature", None, False, "subnational", "Osun", "subdivision", False),
        ),
        (
            "Nigeria", "Osun Governor and State Assembly", "national", "Osun Governor",
            ("governor", None, False, "subnational", "Osun", "subdivision", False),
        ),
        (
            "Philippines", "2026 Philippines (BARMM) BSKE Elections", "subnational", "Regional",
            ("local_council", None, True, "subnational", "BARMM", "subdivision", False),
        ),
        (
            "Chad", "President and National Assembly", "national", "National Assembly",
            ("lower_house", "iso:TD/national-assembly", False, "national", None, "nationwide", False),
        ),
    ],
)
def test_label_scope_office_text(
    name: str, label: str, default: str, office_text: str, expected: tuple[object, ...]
) -> None:
    scope = label_scope(label, _place(name), _REGISTRIES, default, office_text=office_text)  # type: ignore[arg-type]
    assert (
        scope.office.office_class,
        scope.office.institution,
        scope.office.aggregate,
        scope.level,
        scope.jurisdiction,
        scope.jurisdiction_kind,
        scope.unresolved,
    ) == expected


@pytest.mark.parametrize(
    ("name", "label", "office_class"),
    [
        ("Nigeria", "Osun Governor", "governor"),
        ("Philippines", "2026 Philippines (BARMM) Parliamentary Elections", "legislature"),
        ("Nigeria", "Presidential", "head_of_state"),
    ],
)
def test_label_scope_without_office_text_classifies_the_label(
    name: str, label: str, office_class: str
) -> None:
    place = _place(name)
    scope = label_scope(label, place, _REGISTRIES, office_text=None)
    assert scope == label_scope(label, place, _REGISTRIES)
    assert scope.office.office_class == office_class


def test_label_scope_names_barmm() -> None:  # P51
    scope = label_scope(
        "2026 Philippines (BARMM) Parliamentary Elections", _place("Philippines"), _REGISTRIES
    )
    assert scope.office.office_class == "legislature"
    assert scope.level == "unknown"
    assert scope.jurisdiction == "BARMM"
    assert scope.jurisdiction_kind == "subdivision"
    assert scope.unresolved is True


@pytest.mark.parametrize(
    ("name", "parts", "expected"),
    [
        (
            "Nigeria", ["Presidential", "Osun Governor"],
            [("head_of_state", "national", None, "nationwide", False),
             ("governor", "subnational", "Osun", "subdivision", False)],
        ),
        (
            "Nigeria", ["President", "Osun State Assembly"],
            [("head_of_state", "national", None, "nationwide", False),
             ("legislature", "subnational", "Osun State", "subdivision", False)],
        ),
        (
            "Nigeria", ["Osun Governor", "State Assembly"],
            [("governor", "subnational", "Osun", "subdivision", False),
             ("legislature", "subnational", "Osun", "subdivision", False)],
        ),
        (
            "Nigeria", ["Osun Governor", "Lagos State Assembly"],
            [("governor", "subnational", "Osun", "subdivision", False),
             ("legislature", "subnational", "Lagos State", "subdivision", False)],
        ),
        (
            "Philippines", ["(BARMM) Parliamentary", "Local Elections"],
            [("legislature", "unknown", "BARMM", "subdivision", True),
             ("local_council", "subnational", "BARMM", "subdivision", False)],
        ),
        (
            "Philippines", ["Presidential", "Local Elections"],
            [("head_of_state", "national", None, "nationwide", False),
             ("local_council", "subnational", None, "nationwide", False)],
        ),
    ],
)
def test_part_scopes(name: str, parts: list[str], expected: list[tuple[object, ...]]) -> None:  # P63
    out = part_scopes(parts, _place(name), _REGISTRIES)
    assert [
        (s.office.office_class, s.level, s.jurisdiction, s.jurisdiction_kind, s.unresolved)
        for s in out
    ] == expected


@pytest.mark.parametrize(
    ("name", "label"),
    [
        ("Nigeria", "Osun Governor"),
        ("Philippines", "2026 Philippines (BARMM) Parliamentary Elections"),
        ("Nigeria", "Presidential"),
    ],
)
def test_part_scopes_of_one_part_is_label_scope(name: str, label: str) -> None:
    place = _place(name)
    assert part_scopes([label], place, _REGISTRIES) == [label_scope(label, place, _REGISTRIES)]


def test_coverage_reasons_have_page_and_year() -> None:
    cov = [PageCoverage("national-2027", 2027, "timeout", None, 0)]
    assert coverage_reasons(cov) == (
        Reason("timeout", "national-2027", page="national-2027", year=2027),
    )


def test_missing_pages_have_page_and_year() -> None:
    a = PageRequest("p0", "https://example.test/0", 2026)
    b = PageRequest("p1", "https://example.test/1")
    reasons = missing_pages([a, b], raw_pages("s", []))
    assert reasons == [
        Reason("pagination_incomplete", "p0 was not fetched", page="p0", year=2026),
        Reason("pagination_incomplete", "p1 was not fetched", page="p1", year=None),
    ]


def test_page_request_scope_and_link() -> None:
    from elections_calendar.sources import eisa
    from elections_calendar.sources.ndi import request

    plain = PageRequest("k", "https://example.test/u")
    assert (plain.scope_name, plain.page_link) == ("k", "https://example.test/u")
    assert request(3).scope_name == "pages"
    wiki = next(
        r
        for r in _load(DEFAULT_ADAPTERS[2]).requests(window_for(datetime(2026, 10, 19, tzinfo=UTC)))
        if r.key == "national-2026"
    )
    assert wiki.page_link == "https://en.wikipedia.org/wiki/2026_national_electoral_calendar"
    assert eisa.year_request(2026, "38978").page_link == eisa.URL


def test_every_adapter_declares_its_parser_version() -> None:
    assert [_load(spec).parser_version for spec in DEFAULT_ADAPTERS] == ["2.0"] * 9


def test_eisa_year_notes_have_a_year() -> None:
    from tests.adapters.test_eisa import RES

    notes = [n for n in RES.notes if n.code == "not_published_yet"]
    assert [n.year for n in notes] == [2027]
