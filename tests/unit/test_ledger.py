"""The ledger: unit accounting and the independent discovery check (spec §9.1, §7)."""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

import pytest

from elections_calendar.ledger import (
    COUNT_RULES,
    CardBlocksRule,
    CountRule,
    HeaderTableRowsRule,
    HeadingTablesRule,
    JsonListRule,
    LinkTableCellsRule,
    SectionItemsRule,
    TableRowsRule,
    check,
    discover,
    marker_problems,
    page_revid,
    record_problems,
)
from elections_calendar.model import Claim, InputUnit, Reason
from elections_calendar.sources.base import PageCoverage, PageRequest, ParseResult, RawPages
from tests.support.fixtures import fixture
from tests.support.pages import claim, raw_pages, result, unit

RULES: dict[str, CountRule] = {"s": TableRowsRule("t")}
THREE_ROWS = b'<table id="t"><tbody>' + b"<tr><td>x</td></tr>" * 3 + b"</tbody></table>"
STOP_IDS = frozenset(
    {
        "See_also",
        "References",
        "Notes",
        "External_links",
        "Footnotes",
        "Further_reading",
        "Sources",
        "Citations",
        "Bibliography",
    }
)
WIKI_RULE = SectionItemsRule(frozenset({"References"}), ("parse", "text"), ("parse", "revid"))
WIKI_TEXT = '<h2 id="J">J</h2><ul><li>a</li><li>b</li></ul>'
WIKI_BODY = json.dumps({"parse": {"text": WIKI_TEXT, "revid": 7}}).encode()


def req(key: str) -> PageRequest:
    return PageRequest(key, f"https://example.test/{key}")


def ok(
    key: str = "v", seen: int = 3, prefix: str | None = None, revid: int | None = None
) -> PageCoverage:
    return PageCoverage(key, None, "ok", prefix or f"s:{key}/", seen, revid)


def timeout(key: str) -> PageCoverage:
    return PageCoverage(key, None, "timeout", None, 0)


def three_units() -> list[InputUnit]:
    return [unit("s", f"s:v/r{i}") for i in (1, 2, 3)]


def three_claims() -> list[Claim]:
    return [claim(f"s:v/r{i}") for i in (1, 2, 3)]


@dataclass
class Scene:
    """A consistent three-row source; each case changes one thing. An empty body is a timeout page."""

    units: list[InputUnit] = field(default_factory=three_units)
    claims: list[Claim] = field(default_factory=three_claims)
    coverage: list[PageCoverage] = field(default_factory=lambda: [ok()])
    pages: list[tuple[PageRequest, bytes]] = field(default_factory=lambda: [(req("v"), THREE_ROWS)])
    unfinished: tuple[PageRequest, ...] = ()
    rules: dict[str, CountRule] = field(default_factory=lambda: dict(RULES))
    raw_source: str = "s"
    statuses: dict[str, int] = field(default_factory=dict)  # fetch status per page key

    def build(self) -> tuple[RawPages, ParseResult]:
        raw = raw_pages(
            self.raw_source,
            [
                (r, result(b, outcome="ok" if b else "timeout", status=self.statuses.get(r.key, 200)))
                for r, b in self.pages
            ],
            self.unfinished,
        )
        parsed = ParseResult("s", tuple(self.units), tuple(self.claims), tuple(self.coverage))
        return raw, parsed


def codes(scene: Scene) -> list[str]:
    raw, parsed = scene.build()
    return [r.code for r in check(raw, parsed, rules=scene.rules).reasons]


def says(scene: Scene, needle: str) -> bool:
    """Some problem of the checked scene mentions ``needle`` (the case failed for its own reason)."""
    raw, parsed = scene.build()
    return any(needle in p for p in check(raw, parsed, rules=scene.rules).problems)


def test_discover_table_rows() -> None:
    html = (
        b'<table id="electionsTable"><thead><tr><th>x</th></tr></thead><tbody>'
        b"<tr><td><table><tbody><tr><td>n</td></tr><tr><td>n</td></tr></tbody></table></td></tr>"
        b"<tr><td>b</td></tr><tr><td>c</td></tr></tbody></table>"
        b'<table id="other"><tbody><tr><td/></tr></tbody></table>'
    )
    assert discover(TableRowsRule("electionsTable"), html) == ("r1", "r2", "r3")
    implicit = (
        b'<table id="electionsTable"><thead><tr><th>Country</th></tr></thead>'
        b"<tr><td>Sweden</td></tr></table>"
    )
    assert discover(TableRowsRule("electionsTable"), implicit) == ("r1",)


def test_discover_section_items() -> None:
    text = (
        '<div class="mw-parser-output"><ul><li>lead</li></ul>'
        '<div class="mw-heading"><h2 id="January">J</h2></div>'
        "<ul><li>a<ul><li>b</li><li>c</li></ul></li><li>d</li></ul>"
        '<h2 id="References">R</h2><ol><li>r</li></ol></div>'
    )
    body = json.dumps({"parse": {"text": text, "revid": 7}}).encode()
    assert discover(WIKI_RULE, body) == (
        "January/li[1]",
        "January/li[1]/li[1]",
        "January/li[1]/li[2]",
        "January/li[2]",
    )
    assert page_revid(WIKI_RULE, body) == 7
    for bad in (b"not json", b"[]", b"null", b'{"parse": []}', b'{"parse": {"text": 5}}'):
        assert discover(WIKI_RULE, bad) is None
    for revid in ("true", "0", "-3", '"7"'):
        page = b'{"parse": {"text": "", "revid": ' + revid.encode() + b"}}"
        assert page_revid(WIKI_RULE, page) is None
    assert page_revid(TableRowsRule("t"), b"7") is None
    assert page_revid(WIKI_RULE, b"not json") is None


def test_discover_and_page_revid_never_raise() -> None:
    bodies = [b"", b"\xff\xfe\x00<li", b"[]", b"null", b'{"parse": {"te', b"</li></li></table>"]
    bodies += [b"[" * 100_000, b"<li>" * 50_000, bytes(range(256)) * 20]
    for rule in (TableRowsRule("t"), WIKI_RULE):
        for body in bodies:
            discover(rule, body)
            page_revid(rule, body)
    unmatched = json.dumps({"parse": {"text": "</li><h2 id='a'></li><li>x</li></ul>"}}).encode()
    assert discover(WIKI_RULE, unmatched) == ("a/li[1]",)


def test_discovery_of_the_fixtures() -> None:
    eg = {"upcoming.html": 45, "past.html": 200, "anticipated.html": 106}
    counts = {
        n: len(discover(COUNT_RULES["electionguide"], fixture("electionguide", n)) or ())
        for n in eg
    }
    assert counts == eg
    wiki = {
        "national-2026.json": ("January/li[1]", "Indirect_elections/li[14]", 108),
        "national-2027.json": ("January/li[1]", "Indirect_elections/li[1]", 46),
        "local-2026.json": ("January/li[1]", "Unknown_date/li[2]", 457),
        "local-2027.json": ("February/li[1]", "Unknown_date/li[13]", 53),
    }
    for name, (first, last, n) in wiki.items():
        locs = discover(COUNT_RULES["wikipedia"], fixture("wikipedia", name))
        assert locs is not None
        assert (locs[0], locs[-1], len(locs), len(set(locs))) == (first, last, n, n)


def test_count_rules_belong_to_the_ledger() -> None:
    assert COUNT_RULES["electionguide"] == TableRowsRule("electionsTable")
    assert COUNT_RULES["wikipedia"] == SectionItemsRule(
        STOP_IDS, ("parse", "text"), ("parse", "revid"), frozenset({"ambox", "metadata", "navbox"})
    )


def test_a_balanced_result_passes() -> None:
    body = b'<table id="t"><tbody>' + b"<tr><td>x</td></tr>" * 4 + b"</tbody></table>"
    units = [
        unit("s", "s:v/r1"),
        unit("s", "s:v/r2", "partial", "no end date"),
        unit("s", "s:v/r3", "unparsed", "odd", relevance="unknown"),
        unit("s", "s:v/r4", "ignored", "duplicate", duplicate_of="s:v/r1"),
    ]
    claims = [claim("s:v/r1", 0), claim("s:v/r1", 1), claim("s:v/r2")]
    raw, parsed = Scene(units, claims, [ok(seen=4)], [(req("v"), body)]).build()
    report = check(raw, parsed, rules=RULES)
    assert report.ok and report.reasons == () and report.problems == ()
    assert report.source == "s" and report.units_seen == 4
    assert report.outcomes == {"parsed": 1, "partial": 1, "unparsed": 1, "ignored": 1}
    assert report.ignored_reasons == {"duplicate": 1}
    assert report.relevance == {"in_or_after_window": 1, "unknown": 1, "before_window": 0}


def test_page_failures_do_not_make_a_report_not_ok() -> None:
    scene = Scene(
        pages=[(req("v"), THREE_ROWS), (req("t"), b"")],
        coverage=[ok(), timeout("t"), PageCoverage("u", None, "unfinished", None, 0)],
        unfinished=(req("u"),),
    )
    raw, parsed = scene.build()
    report = check(raw, parsed, rules=RULES)
    assert report.ok and report.reasons == ()


def test_every_parsed_unit_has_a_claim() -> None:  # requirement (a)
    assert codes(Scene(claims=three_claims()[1:])) == ["ledger_mismatch"]


def test_raw_source_must_match_the_result_source() -> None:
    assert codes(Scene(raw_source="other")) == ["ledger_mismatch"]


def dup_scene(dup_of: str) -> Scene:
    return Scene(
        units=[
            unit("s", "s:v/r1"),
            unit("s", "s:v/r2", "unparsed", "no date"),
            unit("s", "s:v/r3", "ignored", "duplicate", duplicate_of=dup_of),
        ],
        claims=[claim("s:v/r1")],
    )


def off_allowlist() -> Scene:
    scene = Scene(
        units=[
            unit("s", "s:v/r1"),
            unit("s", "s:v/r2"),
            unit("s", "s:v/r3", "ignored", "empty_cell"),
        ],
        claims=[claim("s:v/r1"), claim("s:v/r2")],
    )
    object.__setattr__(scene.units[2], "reason", "made_up")  # a saved record that skipped checks
    return scene


def claim_saved_with_another_source() -> Scene:
    scene = Scene()
    object.__setattr__(scene.claims[0], "source", "t")  # a saved record that skipped checks
    return scene


RECORD_CASES: dict[str, Callable[[], Scene]] = {
    "claim on an unparsed unit": lambda: Scene(
        units=[*three_units()[:2], unit("s", "s:v/r3", "unparsed", "odd")]
    ),
    "claim on a missing unit": lambda: Scene(claims=[*three_claims(), claim("s:v/r9")]),
    "duplicate claim id": lambda: Scene(claims=[*three_claims(), claim("s:v/r1")]),
    "claim of another source": lambda: Scene(claims=[*three_claims(), claim("t:v/r1")]),
    "claim saved with another source": claim_saved_with_another_source,
    "unit of another source": lambda: Scene(
        units=[*three_units(), unit("t", "t:v/r1", "unparsed", "odd")]
    ),
    "claims #0 and #2": lambda: Scene(claims=[*three_claims(), claim("s:v/r1", 2)]),
    "parsed unit without a claim": lambda: Scene(claims=three_claims()[:2]),
    "partial unit without a claim": lambda: Scene(
        units=[*three_units()[:2], unit("s", "s:v/r3", "partial", "office_unrecognised")],
        claims=three_claims()[:2],
    ),
    "duplicate_of an unparsed unit": lambda: dup_scene("s:v/r2"),
    "duplicate_of a missing unit": lambda: dup_scene("s:v/r9"),
    "ignored reason off the allowlist": off_allowlist,
}


RECORD_NEEDLES = {
    "claim on an unparsed unit": "s:v/r3#0 is on no parsed or partial unit",
    "claim on a missing unit": "s:v/r9#0 is on no parsed or partial unit",
    "duplicate claim id": "duplicate claim id s:v/r1#0",
    "claim of another source": "claim t:v/r1#0 has source 't'",
    "claim saved with another source": "claim s:v/r1#0 has source 't'",
    "unit of another source": "unit t:v/r1 has source 't'",
    "claims #0 and #2": "claims of s:v/r1 are not numbered",
    "parsed unit without a claim": "parsed unit s:v/r3 has no claim",
    "partial unit without a claim": "partial unit s:v/r3 has no claim",
    "duplicate_of an unparsed unit": "unit s:v/r3 duplicates s:v/r2",
    "duplicate_of a missing unit": "unit s:v/r3 duplicates s:v/r9",
    "ignored reason off the allowlist": "'made_up', not allowlisted",
}


@pytest.mark.parametrize("case", list(RECORD_CASES))
def test_record_problems_are_ledger_mismatches(case: str) -> None:
    scene = RECORD_CASES[case]()
    raw, parsed = scene.build()
    problems = record_problems(parsed)
    assert problems and set(problems) <= set(check(raw, parsed, rules=RULES).problems)
    assert any(RECORD_NEEDLES[case] in p for p in problems)
    assert codes(scene) == ["ledger_mismatch"]


def test_record_problems_of_a_clean_result_is_empty() -> None:
    assert record_problems(Scene().build()[1]) == ()


PAGE_CASES: dict[str, Callable[[], Scene]] = {
    "duplicate unit id": lambda: Scene(units=[*three_units(), unit("s", "s:v/r1")]),
    "unit outside every prefix": lambda: Scene(
        units=[*three_units(), unit("s", "s:w/r1")], claims=[*three_claims(), claim("s:w/r1")]
    ),
    "unit on a timeout page": lambda: Scene(
        units=[*three_units(), unit("s", "s:t/r1")],
        claims=[*three_claims(), claim("s:t/r1")],
        pages=[(req("v"), THREE_ROWS), (req("t"), b"")],
        coverage=[ok(), timeout("t")],
    ),
    "page without coverage": lambda: Scene(pages=[(req("v"), THREE_ROWS), (req("w"), b"")]),
    "unfinished request without coverage": lambda: Scene(unfinished=(req("u"),)),
    "coverage for no page": lambda: Scene(coverage=[ok(), timeout("z")]),
    "two pages with one key": lambda: Scene(pages=[(req("v"), THREE_ROWS), (req("v"), THREE_ROWS)]),
    "page and unfinished request with one key": lambda: Scene(
        pages=[(req("v"), THREE_ROWS), (req("t"), b"")],
        unfinished=(req("t"),),
        coverage=[ok(), timeout("t")],
    ),
    "two coverage entries for one page": lambda: Scene(coverage=[ok(), timeout("v")]),
    "source without a rule": lambda: Scene(rules={}),
    "ok coverage for an unfinished request": lambda: Scene(
        unfinished=(req("u"),), coverage=[ok(), ok("u", seen=0)]
    ),
    "timeout coverage for an unfinished request": lambda: Scene(
        unfinished=(req("u"),), coverage=[ok(), timeout("u")]
    ),
    "valid_empty coverage on a timed-out page": lambda: Scene(
        pages=[(req("v"), THREE_ROWS), (req("t"), b"")],
        coverage=[ok(), PageCoverage("t", None, "valid_empty", "s:t/", 0)],
    ),
    "ok coverage on a redirect without Location": lambda: Scene(
        pages=[(req("v"), THREE_ROWS), (req("r"), b"x")],
        coverage=[ok(), ok("r", seen=0)],
        statuses={"r": 302},
    ),
    "timeout coverage on a page that downloaded": lambda: Scene(
        units=[], claims=[], coverage=[timeout("v")]
    ),
    "http_error coverage on a timed-out page": lambda: Scene(
        pages=[(req("v"), THREE_ROWS), (req("t"), b"")],
        coverage=[ok(), PageCoverage("t", None, "http_error", None, 0)],
    ),
    "not_published_yet coverage on a page that downloaded": lambda: Scene(
        units=[], claims=[], coverage=[PageCoverage("v", None, "not_published_yet", None, 0)]
    ),
    "required_year_missing coverage on a page that downloaded": lambda: Scene(
        units=[], claims=[], coverage=[PageCoverage("v", None, "required_year_missing", None, 0)]
    ),
    "layout_not_recognised coverage on a timed-out page": lambda: Scene(
        pages=[(req("v"), THREE_ROWS), (req("t"), b"")],
        coverage=[ok(), PageCoverage("t", None, "layout_not_recognised", None, 0)],
    ),
    "layout_not_recognised coverage on a redirect without Location": lambda: Scene(
        pages=[(req("v"), THREE_ROWS), (req("r"), b"x")],
        coverage=[ok(), PageCoverage("r", None, "layout_not_recognised", None, 0)],
        statuses={"r": 302},
    ),
    "units seen on a page that gave none": lambda: Scene(
        pages=[(req("v"), THREE_ROWS), (req("t"), b"")],
        coverage=[ok(), PageCoverage("t", None, "timeout", None, 5)],
    ),
    "units seen on an unfinished request": lambda: Scene(
        unfinished=(req("u"),), coverage=[ok(), PageCoverage("u", None, "unfinished", None, 2)]
    ),
    "unfinished coverage on a page that was fetched": lambda: Scene(
        units=[], claims=[], coverage=[PageCoverage("v", None, "unfinished", None, 0)]
    ),
}
PAGE_NEEDLES = {
    "duplicate unit id": "duplicate unit id s:v/r1",
    "unit outside every prefix": "unit s:w/r1 is under 0",
    "unit on a timeout page": "unit s:t/r1 is under 0",
    "page without coverage": "page 'w' has 0 coverage entries",
    "unfinished request without coverage": "page 'u' has 0 coverage entries",
    "coverage for no page": "coverage for 'z'",
    "two pages with one key": "page key 'v' is requested 2 times",
    "page and unfinished request with one key": "page key 't' is requested 2 times",
    "two coverage entries for one page": "page 'v' has 2 coverage entries",
    "source without a rule": "has no counting rule",
    "ok coverage for an unfinished request": "page 'u' is ok but no page was fetched",
    "timeout coverage for an unfinished request": "page 'u' is an unfinished request",
    "valid_empty coverage on a timed-out page": "page 't' is valid_empty but its download failed",
    "ok coverage on a redirect without Location": "page 'r' is ok but its download failed",
    "timeout coverage on a page that downloaded": "page 'v' is timeout but its download succeeded",
    "http_error coverage on a timed-out page": "page 't' is http_error but its download failed: timeout",
    "not_published_yet coverage on a page that downloaded": (
        "page 'v' is not_published_yet but its download succeeded"
    ),
    "required_year_missing coverage on a page that downloaded": (
        "page 'v' is required_year_missing but its download succeeded"
    ),
    "layout_not_recognised coverage on a timed-out page": (
        "page 't' is layout_not_recognised but its download failed: timeout"
    ),
    "layout_not_recognised coverage on a redirect without Location": (
        "page 'r' is layout_not_recognised but its download failed: http_error"
    ),
    "units seen on a page that gave none": "page 't' is timeout but reports units_seen 5",
    "units seen on an unfinished request": "page 'u' is unfinished but reports units_seen 2",
    "unfinished coverage on a page that was fetched": (
        "page 'v' is unfinished but its page was fetched"
    ),
}


def test_coverage_for_an_unknown_key_is_one_problem() -> None:  # R2-2
    raw, parsed = Scene(coverage=[ok(), PageCoverage("z", None, "unfinished", None, 0)]).build()
    assert check(raw, parsed, rules=RULES).problems == (
        "coverage for 'z', which is no page or unfinished request",
    )


@pytest.mark.parametrize("case", list(PAGE_CASES))
def test_page_accounting_problems_are_ledger_mismatches(case: str) -> None:
    scene = PAGE_CASES[case]()
    assert codes(scene) == ["ledger_mismatch"]
    assert says(scene, PAGE_NEEDLES[case])


def test_each_page_outcome_that_matches_its_download_is_accepted() -> None:
    redirect = {"r": 302}
    for pages, entry, statuses in (
        ([(req("t"), b"")], PageCoverage("t", None, "timeout", None, 0), {}),
        ([(req("r"), b"x")], PageCoverage("r", None, "http_error", None, 0), redirect),
        ([(req("t"), b"")], PageCoverage("t", None, "not_published_yet", None, 0), {}),
        ([(req("t"), b"")], PageCoverage("t", None, "required_year_missing", None, 0), {}),
        ([(req("v"), THREE_ROWS)], PageCoverage("v", None, "layout_not_recognised", None, 0), {}),
    ):
        scene = Scene(units=[], claims=[], pages=pages, coverage=[entry], statuses=statuses)
        raw, parsed = scene.build()
        assert check(raw, parsed, rules=scene.rules).ok, entry.outcome


def test_a_unit_under_two_prefixes_is_a_ledger_mismatch() -> None:
    nested = [unit("s", f"s:v/r/r{i}") for i in (1, 2, 3)]
    scene = Scene(
        units=[*three_units(), *nested],
        claims=[*three_claims(), *(claim(u.unit_id) for u in nested)],
        pages=[(req("v"), THREE_ROWS), (req("v/r"), THREE_ROWS)],
        coverage=[ok(), ok("v/r")],
    )
    # the units of "v/r" also lie under the prefix of "v", so "v" disagrees with its page too
    assert codes(scene) == ["ledger_mismatch", "discovery_mismatch"]


def wiki_scene(
    revid: int | None = 7, prefix: str = "s:v@rev7/", body: bytes = WIKI_BODY
) -> Scene:
    return Scene(
        units=[unit("s", f"{prefix}J/li[{i}]") for i in (1, 2)],
        claims=[claim(f"{prefix}J/li[{i}]") for i in (1, 2)],
        coverage=[ok(seen=2, prefix=prefix, revid=revid)],
        pages=[(req("v"), body)],
        rules={"s": WIKI_RULE},
    )


def test_a_consistent_revision_page_passes() -> None:
    assert codes(wiki_scene()) == []


DISCOVERY_CASES: dict[str, Callable[[], Scene]] = {
    "one row missing": lambda: Scene(
        units=three_units()[:2], claims=three_claims()[:2], coverage=[ok(seen=2)]
    ),
    # every unit has a claim and the counts agree, yet the set differs (review P2-06)
    "r1 r2 r4 for three rows": lambda: Scene(
        units=[unit("s", f"s:v/r{i}") for i in (1, 2, 4)],
        claims=[claim(f"s:v/r{i}") for i in (1, 2, 4)],
    ),
    "units_seen off by one": lambda: Scene(coverage=[ok(seen=4)]),
    "prefix names another key": lambda: Scene(
        units=[unit("s", f"s:x/r{i}") for i in (1, 2, 3)],
        claims=[claim(f"s:x/r{i}") for i in (1, 2, 3)],
        coverage=[ok(prefix="s:x/")],
    ),
    "wrong revid": lambda: wiki_scene(revid=8, prefix="s:v@rev8/"),
    "revid missing from the page": lambda: wiki_scene(
        body=json.dumps({"parse": {"text": WIKI_TEXT}}).encode()
    ),
    "prefix without the revision": lambda: wiki_scene(prefix="s:v/"),
    "unreadable body": lambda: Scene(pages=[(req("v"), b"x")], rules={"s": WIKI_RULE}),
}


DISCOVERY_NEEDLES = {
    "one row missing": "the page has 3 units, the result has 2",
    "r1 r2 r4 for three rows": "missing ['s:v/r3'], unexpected ['s:v/r4']",
    "units_seen off by one": "units_seen 4, page has 3",
    "prefix names another key": "unit prefix 's:x/', not 's:v/'",
    "wrong revid": "page revid 7 differs from 8",
    "revid missing from the page": "page revid None differs from 7",
    "prefix without the revision": "unit prefix 's:v/', not 's:v@rev7/'",
    "unreadable body": "cannot be read for the counting rule",
}


@pytest.mark.parametrize("case", list(DISCOVERY_CASES))
def test_disagreeing_with_the_page_is_a_discovery_mismatch(case: str) -> None:
    scene = DISCOVERY_CASES[case]()
    assert codes(scene) == ["discovery_mismatch"]
    assert says(scene, DISCOVERY_NEEDLES[case])


def test_reasons_come_ledger_first_one_each_and_cut() -> None:
    scene = Scene(
        units=[*three_units(), unit("s", "s:w/r1")],
        claims=[*three_claims(), claim("s:v/r1", 5)],
        coverage=[ok(seen=9)],
    )
    raw, parsed = scene.build()
    report = check(raw, parsed, rules=RULES)
    assert [r.code for r in report.reasons] == ["ledger_mismatch", "discovery_mismatch"]
    assert not report.ok and len(report.problems) >= 3

    long_id = "s:" + "k" * 400 + "/r1"
    long = Scene(units=[unit("s", long_id, "unparsed", "x")], claims=[])
    raw, parsed = long.build()
    first = check(raw, parsed, rules=RULES).reasons[0]
    assert isinstance(first, Reason) and first.code == "ledger_mismatch"
    assert len(first.detail) == 300


def test_no_rule_skips_the_discovery_checks() -> None:
    # units and counts disagree with the page, but without a rule only the ledger objects
    scene = Scene(units=three_units()[:1], claims=three_claims()[:1], rules={})
    assert codes(scene) == ["ledger_mismatch"]


@pytest.mark.parametrize(
    ("source", "name", "rule", "n", "first", "last"),
    [
        ("osce", "elections.html", HeaderTableRowsRule(frozenset({"date", "country", "election", "activity"})), 634, "r1", "r634"),
        ("ipu", "elections.html", HeaderTableRowsRule(frozenset({"country", "chamber", "principal mode of designation of members", "expected date of next elections"})), 281, "r1", "r281"),
        ("aweb", "calendar.html", HeaderTableRowsRule(frozenset({"country", "election", "date"})), 32, "r1", "r32"),
        ("carter", "observed.html", HeadingTablesRule((("elections monitored by the carter center", "monitored"), ("expert missions", "expert"))), 61, "monitored-r1", "expert-r18"),
        ("eeas", "missions.html", LinkTableCellsRule(r"EOM .+ \d{4}"), 34, "r1c1", "r17c2"),
    ],
)  # fmt: skip
def test_new_rules_count_the_fixtures(
    source: str, name: str, rule: CountRule, n: int, first: str, last: str
) -> None:
    found = discover(rule, fixture(source, name, "2026-10-18"))
    assert found is not None and (len(found), found[0], found[-1]) == (n, first, last)


CARTER = HeadingTablesRule(
    (("elections monitored by the carter center", "monitored"), ("expert missions", "expert"))
)


def carter_page() -> str:
    return fixture("carter", "observed.html", "2026-10-18").decode("utf-8")


def carter_found(page: str) -> tuple[str, ...] | None:
    return discover(CARTER, page.encode("utf-8"))


def test_heading_tables_on_changed_carter_pages() -> None:
    page = carter_page()
    first = page.index("<table")
    end = page.index("</table>", first) + len("</table>")
    gone = carter_found(page[:first] + page[end:])  # B-T01: the heading stays, its table goes
    assert gone is not None and (len(gone), gone[0], gone[-1]) == (18, "expert-r1", "expert-r18")
    assert not [i for i in gone if i.startswith("monitored-")]
    heading = "Expert Missions</h2>"
    assert heading in page
    assert carter_found(page.replace(heading, heading + "<h2>Expert Missions</h2>", 1)) is None
    note = "<table><tr><td>Note</td></tr></table>"
    assert carter_found(page[:first] + note + page[first:]) is None
    before = carter_found(page.replace("<h2", note + "<h2", 1))
    assert before is not None and len(before) == 61
    rows = re.sub(r"<tr>\s*<td([^>]*)>(.*?)</td>", r'<tr><th scope="row"\1>\2</th>', page, flags=re.S)
    assert rows != page
    th = carter_found(rows)
    assert th is not None and len(th) == 61


def test_heading_tables_on_synthetic_pages() -> None:
    rule = HeadingTablesRule((("a", "a"), ("b", "b")))

    def found(html: str) -> tuple[str, ...] | None:
        return discover(rule, html.encode())

    two = "<tr><td>x</td></tr>" * 2
    assert found(f"<h2>A</h2><table>{two}</table><h2>B</h2><p>none</p>") == ("a-r1", "a-r2")
    # a thead row counts, and a nested table's rows do not
    head = "<thead><tr><th>H</th></tr></thead>"
    assert found(f"<h2> A <b>x</b></h2><table>{head}{two}</table>") is None
    assert found(f"<h2>A</h2><table>{head}{two}</table>") == ("a-r1", "a-r2", "a-r3")
    nested = "<tr><td><table><tr><td>y</td></tr></table></td></tr>"
    assert found(f"<h2>A</h2><table>{nested}{two}</table>") == ("a-r1", "a-r2", "a-r3")
    assert found("<h2>C</h2><table><tr><td>x</td></tr></table>") is None
    assert found("<table><tr><td>x</td></tr></table><h2>A</h2>") is None
    assert found("<h2>A</h2><table></table><h2>B</h2><table><tr><td/></tr></table>") == ("b-r1",)
    assert found(f"<h2>A</h2><table>{two}</table><table>{two}</table>") is None
    assert found("<h2>A</h2><h2>B</h2><table><tr><td>x</td></tr></table>") == ("b-r1",)


def header_page(*tables: str) -> bytes:
    return "".join(tables).encode()


def header_table(heads: str, rows: int, extra: str = "") -> str:
    ths = "".join(f"<th>{h}</th>" for h in heads.split("|"))
    body = "<tr><td>x</td></tr>" * rows
    return f"<table><thead><tr>{ths}</tr></thead><tbody>{body}{extra}</tbody></table>"


def test_header_table_rows_on_synthetic_pages() -> None:
    rule = HeaderTableRowsRule(frozenset({"date", "country"}))
    ok_table = header_table("Date|Country", 2)
    assert discover(rule, header_page(ok_table)) == ("r1", "r2")
    assert discover(rule, header_page(ok_table, ok_table)) is None
    assert discover(rule, header_page(header_table("Start date|Country", 2))) is None
    assert discover(rule, b"<p>nothing</p>") is None
    # U01: a required header twice is no layout
    assert discover(rule, header_page(header_table("Date|Country|Date", 2))) is None
    assert discover(rule, header_page(header_table("Date|Country|Country", 2))) is None
    assert discover(rule, header_page(header_table("Date|Type|Country", 2))) == ("r1", "r2")
    assert discover(rule, header_page(header_table("Date|Type|Type|Country", 1))) == ("r1",)
    nested = "<tr><td><table><tr><td>y</td></tr></table></td></tr>"
    assert discover(rule, header_page(header_table("Date|Country", 2, nested))) == ("r1", "r2", "r3")
    # a matching header split by markup is still one text
    split = "<table><thead><tr><th>Da<b>te</b></th><th>Country</th></tr></thead><tr><td/></tr></table>"
    assert discover(rule, split.encode()) is None
    spaced = "<table><thead><tr><th>Date <br> </th><th> Country</th></tr></thead><tr><td/></tr></table>"
    assert discover(rule, spaced.encode()) == ("r1",)


def test_link_table_cells_on_synthetic_pages() -> None:
    rule = LinkTableCellsRule(r"EOM .+ \d{4}")
    link = '<a href="/x">EOM Peru 2026</a>'
    table = f"<table><tr><td>{link}</td><th>b</th></tr><tr><td>c</td></tr></table>"
    assert discover(rule, table.encode()) == ("r1c1", "r1c2", "r2c1")
    assert discover(rule, (table + table).encode()) is None
    assert discover(rule, b"<table><tr><td><a>EOM Peru</a></td></tr></table>") is None
    assert discover(rule, f"<p>{link}</p>".encode()) is None
    both = f"<table><tr><td>{link}</td></tr></table><table><tr><td><a>other</a></td></tr></table>"
    assert discover(rule, both.encode()) == ("r1c1",)
    nested = f"<table><tr><td><table><tr><td>{link}</td></tr></table></td><td>z</td></tr></table>"
    assert discover(rule, nested.encode()) == ("r1c1",)
    assert discover(rule, b'<table><tr><td><a>EOM <b>Peru</b> 2026</a></td></tr></table>') == ("r1c1",)


def test_a_link_must_match_as_a_whole() -> None:
    rule = LinkTableCellsRule(r"EOM .+ \d{4}")
    page = b"<table><tr><td><a>EOM Peru 2026 and more</a></td></tr></table>"
    assert discover(rule, page) is None


def test_new_rules_have_no_revision() -> None:
    for rule in (
        HeaderTableRowsRule(frozenset({"a"})),
        HeadingTablesRule((("a", "a"),)),
        LinkTableCellsRule("a"),
    ):
        assert page_revid(rule, b"<table></table>") is None


@pytest.mark.parametrize("reason", ["inactive_chamber", "no_expected_date", "footnote"])
def test_the_new_ignored_reasons_are_allowlisted(reason: str) -> None:
    scene = Scene(units=[unit("s", "s:v/r1", "ignored", reason)], claims=[])
    assert not [p for p in record_problems(scene.build()[1]) if "allowlisted" in p]


@pytest.mark.parametrize(
    ("thead", "expected"),
    [
        ("<tr><th>Date</th><th>Country</th></tr><tr><th>a</th><th>b</th></tr>", None),
        ('<tr><th colspan="2">Date</th><th>Country</th></tr>', None),
        ("<tr><th>Date</th><th>Country</th><td>x</td></tr>", None),
        ("<tr><th>Date</th><th>Country</th></tr>", ("r1", "r2", "r3")),
        (
            "<tr><th>Date<table><thead><tr><th>a</th></tr><tr><th>b</th></tr></thead></table></th>"
            "<th>Country</th></tr>",
            ("r1", "r2", "r3"),
        ),
    ],
)
def test_header_table_rows_reject_irregular_headers(
    thead: str, expected: tuple[str, ...] | None
) -> None:
    body = "<tr><td>a</td><td>b</td></tr>" * 3
    page = f"<table><thead>{thead}</thead><tbody>{body}</tbody></table>".encode()
    rule = HeaderTableRowsRule(frozenset({"date", "country"}))
    assert discover(rule, page) == expected


NDI_BLOCKS = CardBlocksRule(
    (("upcoming-elections", "upcoming"), ("past-elections", "past")), "election-wrapper"
)
EISA_RULE = JsonListRule(frozenset({"calendar"}))


def card_ids(slug: str, last: int) -> list[str]:
    return [f"{slug}-c{i}" for i in range(1, last + 1)]


def test_card_blocks_and_json_lists_count_the_fixtures() -> None:
    day = "2026-10-19"
    expected = {
        "p0.html": card_ids("upcoming", 10) + card_ids("past", 10),
        "p1.html": card_ids("upcoming", 8) + card_ids("past", 10),
        "p2.html": card_ids("past", 10),
        "p3.html": card_ids("past", 10),
        "p4.html": card_ids("past", 10),
    }
    for name, units in expected.items():
        assert discover(NDI_BLOCKS, fixture("ndi", name, day)) == tuple(units), name
    for name, n in (("y2026.json", 22), ("y2025.json", 23)):
        found = discover(EISA_RULE, fixture("eisa", name, day), name.removesuffix(".json"))
        assert found == tuple(f"r{i}" for i in range(1, n + 1)), name
    calendar = fixture("eisa", "calendar.html", day)
    assert discover(EISA_RULE, calendar, "calendar") == ()
    assert discover(EISA_RULE, calendar, "y2026") is None


CARD = '<div class="partial"><div class="text"><div>x</div></div>text</div>'
WRAPPED = f'<div class="election-wrapper">{CARD}</div>'


def block_page(upcoming: str, past: str = WRAPPED) -> bytes:
    return (
        f'<html><body><div id="upcoming-elections"><div class="bound">{upcoming}</div></div>'
        f'<div id="past-elections"><div class="bound">{past}</div></div></body></html>'
    ).encode()


def test_card_blocks_on_synthetic_pages() -> None:
    def count(body: bytes) -> tuple[str, ...] | None:
        return discover(NDI_BLOCKS, body)

    assert count(block_page(WRAPPED + WRAPPED)) is None
    twice = block_page(WRAPPED).replace(b"</body>", b'<div id="upcoming-elections"></div></body>')
    assert count(twice) is None
    assert count(block_page(WRAPPED).replace(b'id="past-elections"', b'id="x"')) is None
    assert count(block_page("<p>No Results Found</p>")) == ("past-c1",)
    loose = f'<div class="election-wrapper">{CARD} loose text {CARD}</div>'
    assert count(block_page(loose)) == ("upcoming-c1", "upcoming-c2", "past-c1")
    with_br = f'<div class="election-wrapper">{CARD}<br>{CARD}</div>'
    assert count(block_page(with_br)) == ("upcoming-c1", "upcoming-c2", "upcoming-c3", "past-c1")
    two_classes = f'<div class="x election-wrapper">{CARD}</div>'
    assert count(block_page(two_classes)) == ("upcoming-c1", "past-c1")


def test_json_lists_on_synthetic_bodies() -> None:
    def count(body: bytes, key: str = "y2026") -> tuple[str, ...] | None:
        return discover(EISA_RULE, body, key)

    assert count(b"[]") == ()
    assert count(b'[1, {"a": 2}]') == ("r1", "r2")
    assert count(b"{}") is None
    assert count(b"<html>") is None
    assert count(b"garbage", "calendar") == ()


def test_discovery_uses_the_page_key() -> None:
    cal = PageRequest("calendar", "https://example.test/c")
    y26 = PageRequest("y2026", "https://example.test/y")
    raw = raw_pages("eisa", [(cal, result(b"<html></html>")), (y26, result(b"[{}, {}]"))])
    coverage = (
        PageCoverage("calendar", None, "ok", "eisa:calendar/", 0),
        PageCoverage("y2026", None, "ok", "eisa:y2026/", 2),
    )
    rules: dict[str, CountRule] = {"eisa": EISA_RULE}

    def parsed(*ids: str) -> ParseResult:
        return ParseResult(
            "eisa",
            tuple(unit("eisa", uid) for uid in ids),
            tuple(claim(uid) for uid in ids),
            coverage,
        )

    assert check(raw, parsed("eisa:y2026/r1", "eisa:y2026/r2"), rules=rules).ok
    bad = check(raw, parsed("eisa:y2026/r1", "eisa:y2026/r2", "eisa:calendar/r1"), rules=rules)
    assert [r.code for r in bad.reasons] == ["discovery_mismatch"]


def test_marker_rule_on_synthetic_pages() -> None:
    rule = CardBlocksRule(NDI_BLOCKS.blocks, NDI_BLOCKS.wrapper, marker="add-to-cal")

    def card(inner: str) -> str:
        return f'<div class="partial">{inner}</div>'

    good = card('<button class="add-to-cal">x</button>')

    def wrapped(*cards: str) -> str:
        return f'<div class="election-wrapper">{"".join(cards)}</div>'

    def problems(upcoming: str, past: str | None = None) -> list[str]:
        body = block_page(upcoming, wrapped(good) if past is None else past)
        return marker_problems(rule, body, "k")

    assert problems(wrapped(good)) == []
    assert problems(wrapped(card("<p>none</p>"))) == [
        "page 'k': upcoming card 1 holds 0 add-to-cal markers",
        "page 'k': upcoming block holds 0 add-to-cal markers for 1 cards",
    ]
    assert problems(wrapped(card('<i class="add-to-cal"/>'))) == []
    assert problems(wrapped(card('<i class="x add-to-cal"></i>'))) == []
    assert problems(wrapped(card('<i class="add-to-cal-button"></i>'))) == [
        "page 'k': upcoming card 1 holds 0 add-to-cal markers",
        "page 'k': upcoming block holds 0 add-to-cal markers for 1 cards",
    ]
    deep = card('<div><div><div><b class="add-to-cal"></b></div></div></div>')
    assert problems(wrapped(deep)) == []
    assert problems(wrapped(good, "<br>", good)) == [
        "page 'k': upcoming card 2 holds 0 add-to-cal markers",
        "page 'k': upcoming block holds 2 add-to-cal markers for 3 cards",
    ]
    assert problems(wrapped(good), wrapped(card(""))) == [
        "page 'k': past card 1 holds 0 add-to-cal markers",
        "page 'k': past block holds 0 add-to-cal markers for 1 cards",
    ]
    assert marker_problems(NDI_BLOCKS, block_page(wrapped(card(""))), "k") == []
    assert marker_problems(rule, b"<html></html>", "k") == []
