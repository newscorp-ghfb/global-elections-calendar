"""The ledger: unit accounting and the independent discovery check (spec §9.1, §7)."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field

import pytest

from elections_calendar.ledger import (
    COUNT_RULES,
    CountRule,
    SectionItemsRule,
    TableRowsRule,
    check,
    discover,
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
        STOP_IDS, ("parse", "text"), ("parse", "revid")
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
}


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
