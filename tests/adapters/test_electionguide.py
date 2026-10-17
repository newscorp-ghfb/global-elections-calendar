import re
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime

import pytest

from elections_calendar.fetch import Deadline, FetchResult
from elections_calendar.ledger import check
from elections_calendar.model import Claim, DateSpan, InputUnit, Reason
from elections_calendar.sources.base import Adapter, ParseResult, RawPages, Registries
from elections_calendar.sources.electionguide import ElectionGuide
from elections_calendar.window import window_for
from tests.support.fixtures import fixture
from tests.support.pages import raw_pages, result

_: Adapter = ElectionGuide()

WINDOW = window_for(datetime(2026, 10, 16, tzinfo=UTC))
REGISTRIES = Registries.load()
REQUESTS = ElectionGuide().requests(WINDOW)
ALL = raw_pages(
    "electionguide",
    [(r, result(fixture("electionguide", f"{r.key}.html"), url=r.url)) for r in REQUESTS],
)
HEADERS = ["", "Country", "Election for", "Start Date", "End Date", "Status", "Is Snap?"]
D = "2026-11-01 <small>(d)</small>"
RES = ElectionGuide().parse(ALL, WINDOW, REGISTRIES)
UNITS = {u.unit_id: u for u in RES.units}
CLAIMS = {c.claim_id: c for c in RES.claims}


def parse(raw: RawPages = ALL) -> ParseResult:
    res = ElectionGuide().parse(raw, WINDOW, REGISTRIES)
    assert check(raw, res).ok
    return res


def eg_page(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    tbody: bool = True,
    trailer: str = "",
) -> bytes:
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    if tbody:
        body = f"<tbody>{body}</tbody>"
    return (
        f"<!doctype html><html><body><table id='electionsTable'><thead><tr>{head}</tr></thead>"
        f"{body}</table></body></html>{trailer}"
    ).encode()


def row(
    country: str = "Sweden",
    label: str = "Swedish Riksdag",
    start: str = D,
    end: str = D,
    status: str | None = "Confirmed",
    event: int | None = 42,
) -> list[str]:
    link = f'<a href="/elections/id/{event}/?x=1">{label}</a>' if event else label
    cells = ["", country, link, start, end]
    if status is not None:
        cells += [status, "No"]
    return cells


def views(**pages: bytes) -> RawPages:
    """Synthetic views by key; the others are empty valid pages."""
    empty = eg_page(HEADERS, [])
    return raw_pages(
        "electionguide", [(r, result(pages.get(r.key, empty), url=r.url)) for r in REQUESTS]
    )


def one_row(r: list[str], key: str = "upcoming", headers: Sequence[str] = HEADERS) -> tuple[InputUnit, list[Claim]]:
    res = parse(views(**{key: eg_page(headers, [r])}))
    unit = next(u for u in res.units if u.unit_id == f"electionguide:{key}/r1")
    return unit, [c for c in res.claims if c.unit_id == unit.unit_id]


def by_view(v: str) -> list[Claim]:
    return [c for c in RES.claims if c.unit_id.startswith(f"electionguide:{v}/")]


def test_requests_are_the_three_views() -> None:
    assert [(r.key, r.url, r.mediawiki) for r in ElectionGuide().requests(WINDOW)] == [
        ("upcoming", "https://www.electionguide.org/elections/type/upcoming/", False),
        ("past", "https://www.electionguide.org/elections/type/past/", False),
        ("anticipated", "https://www.electionguide.org/elections/type/anticipated/", False),
    ]


def test_fetch_gets_each_request_in_order() -> None:
    urls: list[str] = []

    class Stub:
        def get(self, url: str, *, deadline: Deadline, mediawiki: bool = False) -> FetchResult:
            urls.append(url)
            return result(b"x", url=url)

    pages = list(ElectionGuide().fetch(WINDOW, Stub(), Deadline.after(60)))
    assert [p.request.key for p in pages] == ["upcoming", "past", "anticipated"]
    assert urls == [r.url for r in REQUESTS]


def test_fixture_ledger_balances() -> None:
    res = parse()
    report = check(ALL, res)
    assert report.ok and res.reasons == ()
    assert report.outcomes == {"parsed": 243, "partial": 0, "unparsed": 2, "ignored": 106}
    assert [(c.key, c.outcome, c.units_seen) for c in res.coverage] == [
        ("upcoming", "ok", 45),
        ("past", "ok", 200),
        ("anticipated", "ok", 106),
    ]
    assert len(res.claims) == 243


def test_view_values() -> None:
    assert Counter(c.date_status for c in by_view("upcoming")) == {"confirmed": 28, "tentative": 17}
    assert Counter(c.date_status for c in by_view("past")) == {"confirmed": 187, "tentative": 11}
    assert {c.status_claim for c in by_view("past")} == {"held"}
    assert {c.status_claim for c in by_view("upcoming")} == {None}
    assert Counter(c.level for c in by_view("upcoming")) == {"national": 42, "subnational": 3}
    assert Counter(c.level for c in by_view("past")) == {"national": 196, "subnational": 2}
    assert Counter((c.office_class, c.aggregate) for c in by_view("upcoming")) == {
        ("governor", False): 3,
        ("head_of_state", False): 11,
        ("legislature", False): 12,
        ("legislature", True): 1,
        ("lower_house", False): 8,
        ("referendum", False): 3,
        ("upper_house", False): 7,
    }
    assert Counter((c.office_class, c.aggregate) for c in by_view("past")) == {
        ("head_of_state", False): 48,
        ("legislature", False): 59,
        ("legislature", True): 6,
        ("local_council", True): 1,
        ("lower_house", False): 43,
        ("referendum", False): 27,
        ("upper_house", False): 14,
    }


@pytest.mark.parametrize(
    ("claim_id", "event", "place", "office_class", "institution", "start", "end", "status"),
    [
        ("electionguide:upcoming/r1#0", "5259", "iso:CZ", "upper_house", "iso:CZ/senate", "2026-10-16", "2026-10-17", "confirmed"),
        ("electionguide:upcoming/r2#0", "5252", "iso:RS", "legislature", "iso:RS/national-assembly", "2026-10-25", "2026-10-25", "confirmed"),
        ("electionguide:upcoming/r3#0", "5254", "iso:BR", "head_of_state", "iso:BR/president", "2026-10-25", "2026-10-25", "confirmed"),
        ("electionguide:upcoming/r45#0", "5250", "iso:FR", "head_of_state", "iso:FR/president", "2027-04-18", "2027-04-18", "tentative"),
        ("electionguide:past/r3#0", "5089", "iso:BR", "upper_house", "iso:BR/federal-senate", "2026-10-04", "2026-10-04", "confirmed"),
        ("electionguide:past/r4#0", "5091", "iso:BR", "head_of_state", "iso:BR/president", "2026-10-04", "2026-10-04", "confirmed"),
        ("electionguide:past/r7#0", "5090", "iso:BR", "lower_house", "iso:BR/chamber-of-deputies", "2026-10-04", "2026-10-04", "confirmed"),
        ("electionguide:past/r11#0", "5083", "iso:MA", "lower_house", "iso:MA/house-of-representatives", "2026-09-23", "2026-09-23", "confirmed"),
        ("electionguide:past/r12#0", "5084", "iso:RU", "lower_house", "iso:RU/state-duma", "2026-09-18", "2026-09-20", "confirmed"),
        ("electionguide:past/r13#0", "5079", "iso:SE", "legislature", "iso:SE/parliament", "2026-09-13", "2026-09-13", "confirmed"),
        ("electionguide:past/r30#0", "5073", "iso:ET", "lower_house", "iso:ET/house-of-peoples-representatives", "2026-06-01", "2026-06-01", "confirmed"),
        ("electionguide:past/r105#0", "4735", "iso:NL", "lower_house", "iso:NL/house-of-representatives", "2025-10-29", "2025-10-29", "confirmed"),
    ],
)
def test_appendix_b_rows(
    claim_id: str,
    event: str,
    place: str,
    office_class: str,
    institution: str,
    start: str,
    end: str,
    status: str,
) -> None:
    c = CLAIMS[claim_id]
    assert c.source_event_id == f"electionguide:{event}"
    assert c.link == f"https://www.electionguide.org/elections/id/{event}/"
    assert (c.place_id, c.office_class, c.institution, c.date_status) == (
        place,
        office_class,
        institution,
        status,
    )
    assert c.span == DateSpan.days(date.fromisoformat(start), date.fromisoformat(end))
    assert UNITS[c.unit_id].outcome == "parsed"


def test_one_claim_field_by_field() -> None:
    c = CLAIMS["electionguide:upcoming/r2#0"]
    assert (
        c.place_raw, c.office_label, c.date_text, c.span, c.level, c.jurisdiction,
        c.jurisdiction_kind, c.kind, c.round, c.date_meaning, c.evidence_kind, c.indirect,
        c.status_claim, c.fetched_at,
    ) == (
        "Serbia", "Serbian National Assembly", "2026-10-25 (d) to 2026-10-25 (d)",
        DateSpan.day(date(2026, 10, 25)), "national", None, "nationwide",
        "candidate_election", None, "voting_period", "calendar", False, None, None,
    )  # fmt: skip
    assert (
        UNITS["electionguide:upcoming/r2"].text
        == "Serbia | Serbian National Assembly | 2026-10-25 (d) | 2026-10-25 (d) | Confirmed | Yes"
    )
    guam = CLAIMS["electionguide:upcoming/r8#0"]
    assert (guam.office_class, guam.level) == ("governor", "subnational")
    vi = CLAIMS["electionguide:upcoming/r15#0"]
    assert (vi.office_class, vi.aggregate, vi.institution, vi.level) == (
        "legislature", True, None, "national",
    )  # fmt: skip


def test_links_never_come_from_the_final_url() -> None:
    evil = "https://evil.test/x"
    raw = raw_pages(
        "electionguide",
        [
            (r, result(fixture("electionguide", f"{r.key}.html"), url=r.url, final_url=evil))
            for r in REQUESTS
        ],
    )
    res = parse(raw)
    assert len(res.claims) == 243
    assert all(c.link.startswith("https://www.electionguide.org/elections/id/") for c in res.claims)
    # no event link: the view's request URL, still not the final URL
    body = eg_page(HEADERS, [row(event=None)])
    raw = raw_pages(
        "electionguide", [(r, result(body, url=r.url, final_url=evil)) for r in REQUESTS[:1]]
    )
    claim = parse(raw).claims[0]
    assert (claim.link, claim.source_event_id) == (REQUESTS[0].url, None)


def test_anticipated_rows_seen_earlier_are_duplicates() -> None:
    anticipated = [u for u in RES.units if u.unit_id.startswith("electionguide:anticipated/")]
    assert {(u.outcome, u.reason) for u in anticipated} == {("ignored", "duplicate")}
    assert len(anticipated) == 106
    assert Counter(
        u.duplicate_of.split(":")[1].split("/")[0] for u in anticipated if u.duplicate_of
    ) == {"past": 73, "upcoming": 33}


def _two(first: list[str], second: list[str], key: str = "past") -> dict[str, InputUnit]:
    res = parse(views(upcoming=eg_page(HEADERS, [first]), **{key: eg_page(HEADERS, [second])}))
    return {u.unit_id: u for u in res.units if u.unit_id.endswith("/r1")}


def test_copies_of_one_event() -> None:
    soon = row(start="soon")
    # an unparsed first copy does not reserve the event id
    units = _two(soon, row())
    assert units["electionguide:upcoming/r1"].reason == "date_unparsed"
    assert units["electionguide:past/r1"].outcome == "parsed"
    claims = parse(views(upcoming=eg_page(HEADERS, [soon]), past=eg_page(HEADERS, [row()]))).claims
    assert [c.status_claim for c in claims] == ["held"]
    # an unparsed later copy stays unparsed
    units = _two(row(), soon)
    assert units["electionguide:upcoming/r1"].outcome == "parsed"
    past = units["electionguide:past/r1"]
    assert (past.outcome, past.reason) == ("unparsed", "date_unparsed")
    # different dates: both kept, one event id
    dec = "2026-12-01 <small>(d)</small>"
    res = parse(
        views(
            upcoming=eg_page(HEADERS, [row()]),
            anticipated=eg_page(HEADERS, [row(start=dec, end=dec)]),
        )
    )
    assert [(c.unit_id, c.source_event_id) for c in res.claims] == [
        ("electionguide:upcoming/r1", "electionguide:42"),
        ("electionguide:anticipated/r1", "electionguide:42"),
    ]
    # a past copy claims "held", the upcoming one claims nothing: both kept
    units = _two(row(), row())
    assert [u.outcome for u in units.values()] == ["parsed", "parsed"]
    # a copy with no status claim of its own repeats a postponed first copy
    bare = "2026-11-01"
    units = _two(row(status="Postponed"), row(start=bare, end=bare, status=""), "anticipated")
    dup = units["electionguide:anticipated/r1"]
    assert (dup.outcome, dup.reason, dup.duplicate_of) == (
        "ignored", "duplicate", "electionguide:upcoming/r1",
    )  # fmt: skip
    # identical rows in one view
    res = parse(views(upcoming=eg_page(HEADERS, [row(), row()])))
    got = {u.unit_id: (u.outcome, u.duplicate_of) for u in res.units if "upcoming" in u.unit_id}
    assert got == {
        "electionguide:upcoming/r1": ("parsed", None),
        "electionguide:upcoming/r2": ("ignored", "electionguide:upcoming/r1"),
    }
    # equal rows of different events are not duplicates; rows without an event never are
    res = parse(views(upcoming=eg_page(HEADERS, [row(event=1), row(event=2)])))
    assert len(res.claims) == 2
    res = parse(views(upcoming=eg_page(HEADERS, [row(event=None), row(event=None)])))
    assert len(res.claims) == 2


def test_a_failed_view_does_not_hide_its_events_elsewhere() -> None:
    raw = raw_pages(
        "electionguide",
        [
            (REQUESTS[0], result(b"", outcome="timeout", status=None, url=REQUESTS[0].url)),
            *[
                (r, result(fixture("electionguide", f"{r.key}.html"), url=r.url))
                for r in REQUESTS[1:]
            ],
        ],
    )
    res = parse(raw)
    assert [(c.key, c.outcome, c.units_seen) for c in res.coverage][0] == ("upcoming", "timeout", 0)
    anticipated = [u for u in res.units if u.unit_id.startswith("electionguide:anticipated/")]
    assert Counter((u.outcome, u.reason) for u in anticipated) == {
        ("parsed", None): 33,
        ("ignored", "duplicate"): 73,
    }
    assert Reason("timeout", "upcoming") in res.reasons


def test_reversed_ranges_are_unparsed() -> None:
    for uid, country in (
        ("electionguide:past/r126", "Seychelles"),
        ("electionguide:past/r176", "Bermuda"),
    ):
        unit = UNITS[uid]
        assert (unit.outcome, unit.reason) == ("unparsed", "end_before_start")
        assert country in unit.text


def _empty_tbody(body: bytes) -> bytes:
    """Empty the electionsTable body; the mobile table still links the elections."""
    pattern = rb'(id="electionsTable".*?<tbody>).*?(</tbody>)'
    return re.sub(pattern, lambda m: m[1] + m[2], body, count=1, flags=re.DOTALL)


@pytest.mark.parametrize(
    "change",
    [
        lambda b: b.replace(b'id="electionsTable"', b'id="elections"'),
        lambda b: b.replace(b"Election for", b"Contest", 1),
        lambda b: b[: len(b) // 2],
        lambda b: b"",
        lambda b: b"\xff\xfe\x00garbage",
        _empty_tbody,
    ],
    ids=["no_table", "header_renamed", "truncated", "empty", "garbage", "rows_gone_links_remain"],
)
def test_broken_pages_get_an_outcome_never_units(change: Callable[[bytes], bytes]) -> None:
    pages = [
        (r, result(fixture("electionguide", f"{r.key}.html"), url=r.url)) for r in REQUESTS
    ]
    pages[0] = (REQUESTS[0], result(change(fixture("electionguide", "upcoming.html")), url=REQUESTS[0].url))
    res = parse(raw_pages("electionguide", pages))
    assert res.coverage[0].outcome == "layout_not_recognised"
    assert res.coverage[0].unit_prefix is None
    assert not [u for u in res.units if u.unit_id.startswith("electionguide:upcoming/")]
    assert [c.outcome for c in res.coverage[1:]] == ["ok", "ok"]


def test_download_failures_keep_their_own_outcome() -> None:
    body = fixture("electionguide", "upcoming.html")
    res = parse(raw_pages("electionguide", [(REQUESTS[0], result(body, status=302, url=REQUESTS[0].url))]))
    assert res.coverage[0].outcome == "http_error" and res.units == ()
    res = parse(raw_pages("electionguide", [(REQUESTS[0], result(body, outcome="challenge_page", url=REQUESTS[0].url))]))
    assert res.coverage[0].outcome == "challenge_page" and res.units == ()


def test_row_structures_html_allows_are_still_rows() -> None:
    rows = [row(event=1), row(event=2)]
    base = eg_page(HEADERS, rows)

    def units(body: bytes) -> int:
        res = parse(views(upcoming=body))
        assert res.coverage[0].outcome == "ok"
        return len(res.units)

    assert units(eg_page(HEADERS, rows, tbody=False)) == 2
    nested = [r[:-1] + ["<table><tr><td>x</td></tr></table>"] for r in rows]
    assert units(eg_page(HEADERS, nested)) == 2
    wrapped = base.replace(b"<body>", b"<body><div><div>").replace(b"</body>", b"</div></div></body>")
    assert units(wrapped) == 2
    assert units(eg_page(HEADERS, rows, trailer="<!-- cache 3 -->\n")) == 2
    assert units(eg_page(HEADERS, rows, trailer="\n<!-- a -->\n<!-- b -->  \n")) == 2
    # nothing in the table and no election link anywhere: a valid empty page
    res = parse(views(upcoming=eg_page(HEADERS, [])))
    assert (res.coverage[0].outcome, res.coverage[0].unit_prefix) == (
        "valid_empty", "electionguide:upcoming/",
    )  # fmt: skip


def test_a_short_row_is_a_discovered_unparsed_unit() -> None:
    rows = [row(event=i) for i in range(1, 6)]
    rows[4] = rows[4][:5]
    res = parse(views(upcoming=eg_page(HEADERS, rows)))
    assert res.coverage[0].units_seen == 5
    short = next(u for u in res.units if u.unit_id == "electionguide:upcoming/r5")
    assert (short.outcome, short.reason) == ("unparsed", "too_few_cells")
    assert len(res.claims) == 4


@pytest.mark.parametrize(
    ("start", "end", "status", "outcome", "reason", "date_status", "claim", "leftover"),
    [
        ("(d)", "(d)", "Confirmed", "parsed", None, "confirmed", None, ""),
        ("(d)", "(d)", "Date not confirmed", "parsed", None, "tentative", None, ""),
        ("(t)", "(d)", "Confirmed", "parsed", None, "tentative", None, ""),
        ("(d)", "(d)", None, "parsed", None, "confirmed", None, ""),
        ("(d)", "(d)", "Postponed", "parsed", None, "unknown", "postponed", ""),
        ("(d)", "(d)", "Canceled", "parsed", None, "unknown", "cancelled", ""),
        ("(d)", "(d)", "Cancelled", "parsed", None, "unknown", "cancelled", ""),
        ("(d)", "(d)", "Rescheduled", "partial", "status_unrecognised", "unknown", None, "Rescheduled"),
    ],
)
def test_status_cells(
    start: str, end: str, status: str | None, outcome: str, reason: str | None,
    date_status: str, claim: str | None, leftover: str,
) -> None:  # fmt: skip
    cell = {"(d)": D, "(t)": "2026-11-01 <small>(t)</small>"}
    headers = HEADERS if status is not None else HEADERS[:5]
    unit, claims = one_row(row(start=cell[start], end=cell[end], status=status), headers=headers)
    assert (unit.outcome, unit.reason, unit.leftover) == (outcome, reason, leftover)
    assert [(c.date_status, c.status_claim) for c in claims] == [(date_status, claim)]


def test_status_cell_on_a_past_view() -> None:
    _, claims = one_row(row(status="Postponed"), "past")
    assert claims[0].status_claim == "postponed"
    _, claims = one_row(row(status="Confirmed"), "past")
    assert claims[0].status_claim == "held"


def test_places_and_offices_that_do_not_resolve() -> None:
    unit, claims = one_row(row(country="Atlantis"))
    assert (unit.outcome, unit.reason) == ("partial", "place_unregistered")
    assert claims[0].place_id == "unknown:atlantis"
    unit, claims = one_row(row(country=""))
    assert (unit.outcome, unit.reason, claims) == ("unparsed", "place_missing", [])
    unit, claims = one_row(row(country="Iran", label="Supreme Leader"))
    assert (unit.outcome, unit.reason) == ("partial", "office_unrecognised")
    assert claims[0].level == "unknown"
    unit, claims = one_row(row(label="Vice President"))
    assert (unit.outcome, unit.reason, unit.leftover, claims) == (
        "unparsed", "office_not_modelled", "Vice President", [],
    )  # fmt: skip


def test_missing_and_implausible_dates_are_unparsed() -> None:
    unit, _ = one_row(row(start=""))
    assert unit.reason == "date_missing"
    unit, _ = one_row(row(start="soon"))
    assert unit.reason == "date_unparsed"
    far = "2040-01-01 <small>(d)</small>"
    unit, claims = one_row(row(start=far, end=far))
    assert (unit.outcome, unit.reason, claims) == ("unparsed", "implausible_date", [])


def test_coverage_gap_when_the_past_list_starts_inside_the_window() -> None:
    sep = "2026-09-02 <small>(d)</small>"
    res = parse(views(past=eg_page(HEADERS, [row(start=sep, end=sep)])))
    assert Reason("coverage_gap", "past list starts 2026-09-02") in res.reasons
    res = parse(views(past=eg_page(HEADERS, [])))
    assert res.reasons == ()  # valid_empty is not "ok": no note
    res = parse(views(past=eg_page(HEADERS, [row(start="soon")])))
    assert Reason("coverage_gap", "past list starts empty") in res.reasons
    old = "2024-11-24 <small>(d)</small>"
    res = parse(views(past=eg_page(HEADERS, [row(start=old, end=old)])))
    assert res.reasons == ()

