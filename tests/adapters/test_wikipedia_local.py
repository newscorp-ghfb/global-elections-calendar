import json
from collections import Counter
from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest

from elections_calendar.fetch import FetchResult
from elections_calendar.ledger import check
from elections_calendar.model import Claim, InputUnit
from elections_calendar.sources import wikipedia
from elections_calendar.sources.base import ParseResult, RawPages, Registries
from elections_calendar.sources.wikipedia import Wikipedia
from elections_calendar.window import window_for
from tests.support.fixtures import fixture
from tests.support.pages import raw_pages, result

WINDOW = window_for(datetime(2026, 10, 16, tzinfo=UTC))
REGISTRIES = Registries.load()
JSON_TYPE = "application/json; charset=utf-8"


def _pages(prefix: str | None) -> RawPages:
    return raw_pages(
        "wikipedia",
        [
            (r, result(fixture("wikipedia", f"{r.key}.json"), url=r.url, content_type=JSON_TYPE))
            for r in Wikipedia().requests(WINDOW)
            if prefix is None or r.key.startswith(prefix)
        ],
    )


LOCAL = _pages("local-")
ALL4 = _pages(None)
RES = Wikipedia().parse(LOCAL, WINDOW, REGISTRIES)
CLAIMS = {c.claim_id: c for c in RES.claims}
UNITS = {u.unit_id: u for u in RES.units}
L = "wikipedia:local-2026@rev1380378807/"
L27 = "wikipedia:local-2027@rev1379495387/"
S = "wikipedia:local-2026@rev7/"
TITLE = "2026 local electoral calendar"


def wiki_page(sections: dict[str, str], *, title: str = TITLE, revid: int = 7) -> bytes:
    """The MediaWiki parse JSON of a page with these sections (id -> inner HTML)."""
    html = "".join(
        f'<div class="mw-heading mw-heading2"><h2 id="{sid}">{sid.replace("_", " ")}</h2></div>{body}'
        for sid, body in sections.items()
    )
    text = f'<div class="mw-parser-output">{html}</div>'
    return json.dumps({"parse": {"title": title, "pageid": 1, "revid": revid, "text": text}}).encode()


def body_of(body: bytes, key: str = "local-2026") -> FetchResult:
    request = next(p.request for p in LOCAL.pages if p.request.key == key)
    return result(body, url=request.url, content_type=JSON_TYPE)


def synth(sections: dict[str, str]) -> ParseResult:
    """A local-2026 page with these sections in place of the fixture; the ledger must balance."""
    replaced = body_of(wiki_page(sections))
    raw = raw_pages(
        "wikipedia",
        [(p.request, replaced if p.request.key == "local-2026" else p.result) for p in LOCAL.pages],
    )
    res = Wikipedia().parse(raw, WINDOW, REGISTRIES)
    assert check(raw, res).ok
    return res


def mine(res: ParseResult) -> tuple[list[InputUnit], list[Claim]]:
    return (
        [u for u in res.units if u.unit_id.startswith("wikipedia:local-2026@rev7/")],
        [c for c in res.claims if c.unit_id.startswith("wikipedia:local-2026@rev7/")],
    )


def per_page_counter(key: str, fn: Callable[[Claim], object]) -> Counter[object]:
    return Counter(fn(c) for c in RES.claims if c.unit_id.startswith(f"wikipedia:{key}@"))


def of(key: str) -> list[InputUnit]:
    return [u for u in RES.units if u.unit_id.startswith(f"wikipedia:{key}@")]


def fields(claim_id: str) -> tuple[str, str | None, str, str, str | None, str]:
    c = CLAIMS[claim_id]
    return (c.place_id, c.jurisdiction, c.jurisdiction_kind, c.office_class, c.institution, c.level)


def test_local_fixture_ledger_balances() -> None:
    res = Wikipedia().parse(LOCAL, WINDOW, REGISTRIES)
    assert check(LOCAL, res).ok and res.reasons == ()
    assert [(c.key, c.outcome, c.units_seen, c.revid) for c in res.coverage] == [
        ("local-2026", "ok", 457, 1380378807),
        ("local-2027", "ok", 53, 1379495387),
    ]
    assert Counter((u.outcome, u.reason) for u in of("local-2026")) == {
        ("parsed", None): 299,
        ("partial", "office_not_modelled"): 29,
        ("partial", "office_unrecognised"): 28,
        ("unparsed", "office_not_modelled"): 4,
        ("ignored", "container_item"): 97,
    }
    assert sum(1 for c in res.claims if c.unit_id.startswith("wikipedia:local-2026@")) == 369
    october = [u for u in of("local-2026") if u.unit_id.startswith(L + "October/")]
    assert len(october) == 48
    assert sum(1 for u in october if u.outcome == "ignored") == 5
    assert sum(1 for c in res.claims if c.unit_id.startswith(L + "October/")) == 44
    assert Counter((u.outcome, u.reason) for u in of("local-2027")) == {
        ("parsed", None): 3,
        ("partial", "office_unrecognised"): 2,
        ("unparsed", "article_title"): 46,
        ("ignored", "container_item"): 2,
    }
    assert sum(1 for c in res.claims if c.unit_id.startswith("wikipedia:local-2027@")) == 5
    assert per_page_counter("local-2026", lambda c: (c.office_class, c.level)) == {
        ("general", "subnational"): 1, ("general", "unknown"): 28, ("governor", "subnational"): 71,
        ("head_of_state", "subnational"): 1, ("legislature", "national"): 13,
        ("legislature", "subnational"): 35, ("local_council", "subnational"): 70,
        ("lower_house", "national"): 30, ("lower_house", "subnational"): 43,
        ("mayor", "subnational"): 39, ("referendum", "subnational"): 18,
        ("upper_house", "national"): 2, ("upper_house", "subnational"): 18,
    }
    assert per_page_counter("local-2027", lambda c: (c.office_class, c.level)) == {
        ("general", "unknown"): 2, ("governor", "subnational"): 1,
        ("local_council", "subnational"): 1, ("mayor", "subnational"): 1,
    }


def test_national_values_are_unchanged() -> None:
    res = Wikipedia().parse(ALL4, WINDOW, REGISTRIES)
    assert check(ALL4, res).ok and res.reasons == ()
    assert len(res.units) == 664 and len(res.claims) == 543
    assert [(c.key, c.outcome, c.units_seen) for c in res.coverage] == [
        ("national-2026", "ok", 108), ("national-2027", "ok", 46),
        ("local-2026", "ok", 457), ("local-2027", "ok", 53),
    ]
    for key, counts, n_claims in (
        ("national-2026", {("parsed", None): 95, ("partial", "office_unrecognised"): 1,
                           ("unparsed", "office_not_modelled"): 1,
                           ("ignored", "container_item"): 11}, 113),
        ("national-2027", {("parsed", None): 44, ("ignored", "container_item"): 2}, 56),
    ):
        units = [u for u in res.units if u.unit_id.startswith(f"wikipedia:{key}@")]
        assert Counter((u.outcome, u.reason) for u in units) == counts
        assert sum(1 for c in res.claims if c.unit_id.startswith(f"wikipedia:{key}@")) == n_claims

    def national(key: str) -> Counter[object]:
        return Counter(
            (c.office_class, c.level) for c in res.claims if c.unit_id.startswith(f"wikipedia:{key}@")
        )

    assert national("national-2026") == {
        ("general", "national"): 1, ("general", "unknown"): 1, ("head_of_state", "national"): 32,
        ("legislature", "national"): 35, ("lower_house", "national"): 18,
        ("referendum", "national"): 14, ("upper_house", "national"): 12,
    }
    assert national("national-2027") == {
        ("head_of_state", "national"): 15, ("legislature", "national"): 27,
        ("lower_house", "national"): 7, ("upper_house", "national"): 7,
    }
    nat = [c for c in res.claims if c.unit_id.startswith("wikipedia:national-")]
    assert {(c.jurisdiction, c.jurisdiction_kind) for c in nat} == {(None, "nationwide")}


@pytest.mark.parametrize(
    ("claim_id", "place", "jurisdiction", "jkind", "label", "office_class", "institution",
     "level", "kind", "start", "end"),
    [
        (L + "September/li[4]/li[2]#0", "iso:SE", None, "nationwide", "regional and municipal elections", "local_council", None, "subnational", "aggregate", "2026-09-13", "2026-09-13"),
        (L + "September/li[4]/li[1]#0", "iso:DE", "Lower Saxony", "subdivision", "local elections", "local_council", None, "subnational", "aggregate", "2026-09-13", "2026-09-13"),
        (L + "October/li[1]/li[1]#0", "iso:BR", None, "nationwide", "Governors", "governor", None, "subnational", "aggregate", "2026-10-04", "2026-10-04"),
        (L + "October/li[1]/li[1]/li[6]#0", "iso:BR", "Federal District", "subdivision", "Governor", "governor", None, "subnational", "candidate_election", "2026-10-04", "2026-10-04"),
        (L + "October/li[1]/li[3]#0", "iso:PY", None, "nationwide", "municipal elections", "local_council", None, "subnational", "aggregate", "2026-10-04", "2026-10-04"),
        (L + "October/li[1]/li[4]#0", "iso:PE", None, "nationwide", "regional and municipal elections", "local_council", None, "subnational", "aggregate", "2026-10-04", "2026-10-04"),
        (L + "October/li[1]/li[4]/li[1]#0", "iso:PE", "Lima", "subdivision", "Mayor", "mayor", None, "subnational", "candidate_election", "2026-10-04", "2026-10-04"),
        (L + "October/li[3]/li[2]#0", "iso:GB", "Holborn and St Pancras", "named", "House of Commons by-election", "lower_house", "iso:GB/house-of-commons", "national", "by_election", "2026-10-08", "2026-10-08"),
        (L + "October/li[4]#0", "iso:CZ", None, "nationwide", "municipal elections", "local_council", None, "subnational", "aggregate", "2026-10-09", "2026-10-10"),
        (L + "October/li[9]/li[2]#0", "iso:SK", None, "nationwide", "regional and local elections", "local_council", None, "subnational", "aggregate", "2026-10-24", "2026-10-24"),
        (L + "September/li[5]/li[1]#0", "iso:PH", None, "nationwide", "Bangsamoro Parliament", "legislature", None, "subnational", "aggregate", "2026-09-14", "2026-09-14"),
    ],
)
def test_appendix_b_local_claims(
    claim_id: str,
    place: str,
    jurisdiction: str | None,
    jkind: str,
    label: str,
    office_class: str,
    institution: str | None,
    level: str,
    kind: str,
    start: str,
    end: str,
) -> None:
    c = CLAIMS[claim_id]
    assert (
        c.place_id, c.jurisdiction, c.jurisdiction_kind, c.office_label, c.office_class,
        c.institution, c.level, c.kind, c.span.start, c.span.end,
    ) == (
        place, jurisdiction, jkind, label, office_class, institution, level, kind,
        date.fromisoformat(start), date.fromisoformat(end),
    )
    assert c.indirect is False


def test_the_brazil_governors_card_lists_the_states_in_this_fixture() -> None:
    kids = [c for c in RES.claims if c.unit_id.startswith(L + "October/li[1]/li[1]/li[")]
    assert [c.jurisdiction for c in kids] == [
        "Alagoas", "Amazonas", "Bahia", "Ceará", "Espírito Santo", "Federal District",
        "Goiás", "Maranhão", "Minas Gerais", "Pará", "Paraíba", "Paraná", "Pernambuco",
        "Rio de Janeiro", "Rio Grande do Norte", "Rio Grande do Sul", "Santa Catarina",
        "São Paulo",
    ]
    assert {(c.office_class, c.jurisdiction_kind, c.aggregate) for c in kids} == {
        ("governor", "subdivision", False)
    }
    parent = CLAIMS[L + "October/li[1]/li[1]#0"]  # "Brazil, Governors" stays aggregate evidence
    assert (parent.aggregate, parent.kind) == (True, "aggregate")
    assert UNITS[L + "October/li[1]"].reason == "container_item"  # "4 October:" emits no claim
    assert not [c for c in RES.claims if c.unit_id == L + "October/li[1]"]


def test_a_nested_item_never_re_resolves_its_country() -> None:
    c = CLAIMS[L + "May/li[11]/li[2]/li[2]#0"]  # 19 May: United States > Georgia > Court of Appeals
    assert (c.place_id, c.jurisdiction, c.jurisdiction_kind, c.office_label, c.level) == (
        "iso:US", "Georgia", "subdivision", "Court of Appeals", "unknown",
    )
    assert UNITS[L + "May/li[11]/li[2]"].reason == "container_item"
    unit = UNITS[L + "May/li[11]/li[2]/li[2]"]
    assert (unit.outcome, unit.reason) == ("partial", "office_unrecognised")


def test_registered_subdivisions_become_the_place() -> None:  # P4; level national (user's ruling)
    assert fields(L + "May/li[4]/li[1]#0") == (
        "iso:GB-SCT", None, "nationwide", "legislature", "iso:GB-SCT/scottish-parliament", "national",
    )
    assert fields(L + "May/li[4]/li[2]#0") == (
        "iso:GB-WLS", None, "nationwide", "legislature", "iso:GB-WLS/senedd", "national",
    )


def test_jurisdictions_and_their_kinds() -> None:
    cases = [
        (L + "May/li[2]/li[2]/li[1]/li[1]#0",
         ("iso:US", "Texas", "subdivision", "upper_house", None, "subnational"), "by_election"),
        (L + "February/li[2]/li[2]/li[1]#0",
         ("iso:US", "New York", "subdivision", "legislature", None, "subnational"), "by_election"),
        (L + "June/li[10]/li[1]#0",
         ("iso:AT", "Graz", "named", "local_council", None, "subnational"), "candidate_election"),
        (L + "October/li[1]/li[2]/li[1]#0",
         ("iso:BA", "Federation of Bosnia and Herzegovina", "subdivision", "legislature", None,
          "subnational"), "candidate_election"),
    ]
    for claim_id, expected, kind in cases:
        assert fields(claim_id) == expected, claim_id
        assert CLAIMS[claim_id].kind == kind, claim_id
    la = CLAIMS[L + "June/li[1]/li[1]/li[3]#0"]  # California, Los Angeles: duplicate-free, in order
    assert (la.jurisdiction, la.jurisdiction_kind) == ("California, Los Angeles", "subdivision")


def test_adapter_overrides() -> None:
    ca = CLAIMS[L + "April/li[6]/li[1]#0"]  # Scarborough Southwest
    assert (ca.place_id, ca.jurisdiction_kind, ca.office_label) == (
        "iso:CA", "named", "federal by-election",
    )
    assert (ca.office_class, ca.institution, ca.level, ca.kind, ca.aggregate) == (
        "lower_house", "iso:CA/house-of-commons", "national", "by_election", False,
    )
    assert UNITS[L + "April/li[6]/li[1]"].outcome == "parsed"  # an override is recognised
    for claim_id, rnd in ((L + "July/li[8]#0", 1), (L + "August/li[11]/li[1]#0", 2)):
        c = CLAIMS[claim_id]
        assert (c.place_id, c.jurisdiction, c.jurisdiction_kind) == ("iso:US", "Georgia", "subdivision")
        assert c.office_label.startswith("Georgia's 13th congressional district, special election")
        assert (c.office_class, c.institution, c.level, c.kind, c.round, c.aggregate) == (
            "lower_house", "iso:US/house-of-representatives", "national", "by_election", rnd, False,
        )
        assert UNITS[c.unit_id].outcome == "parsed"
    plain = CLAIMS[L + "August/li[14]/li[1]#0"]  # Beaches-East York: "by-election", not "federal"
    assert (plain.office_class, plain.aggregate, plain.level) == ("general", True, "unknown")
    unit = UNITS[plain.unit_id]
    assert (unit.outcome, unit.reason) == ("partial", "office_unrecognised")


def test_us_executive_lists() -> None:  # 3 November: United States, midterm elections > ...
    n = L + "November/li[2]"
    cases = [
        (n + "/li[1]", "partial", "office_not_modelled",
         "Lieutenant Governor, Secretary of State, Attorney General",
         ["Governor", "ballot measures", "local elections"], ["governor", "referendum", "local_council"]),
        (n + "/li[3]", "partial", "office_not_modelled",
         "Lieutenant Governor, Secretary of State, Attorney General", ["Governor"], ["governor"]),
        (n + "/li[8]", "partial", "office_not_modelled", "Attorney General", ["Mayor"], ["mayor"]),
        (n + "/li[14]", "unparsed", "office_not_modelled", "Secretary of State", [], []),
        (n + "/li[38]", "partial", "office_not_modelled", "Lieutenant Governor",
         ["Governor", "ballot measure"], ["governor", "referendum"]),
        (n, "partial", "office_unrecognised", "", ["midterm elections"], ["general"]),
        (L + "June/li[1]/li[1]/li[3]", "partial", "office_not_modelled",
         "City Attorney (1st round), City Controller",
         ["Mayor (1st round)", "City Council (1st round)"], ["mayor", "local_council"]),
    ]
    for unit_id, outcome, reason, leftover, labels, classes in cases:
        u = UNITS[unit_id]
        assert (u.outcome, u.reason, u.leftover) == (outcome, reason, leftover), unit_id
        kids = [c for c in RES.claims if c.unit_id == unit_id]
        assert [c.office_label for c in kids] == labels, unit_id
        assert [c.office_class for c in kids] == classes, unit_id
    midterm = CLAIMS[n + "#0"]
    assert (midterm.aggregate, midterm.level) == (True, "unknown")
    titles = {"Lieutenant Governor", "Secretary of State", "Attorney General", "City Attorney", "City Controller"}
    for c in RES.claims:
        assert not any(c.office_label.startswith(t) for t in titles), c.claim_id
        assert c.office_class != "governor" or c.office_label.startswith("Governor"), c.claim_id


def test_article_titles_are_unparsed_and_relevant() -> None:
    u = UNITS[L27 + "March/li[1]"]
    assert (u.outcome, u.reason, u.relevance, u.text) == (
        "unparsed", "article_title", "in_or_after_window", "7 March: 2027 Lithuanian municipal elections",
    )
    assert not [c for c in RES.claims if c.unit_id == u.unit_id]
    # the same text under an inherited place is an office text, not an article title
    c = CLAIMS[L27 + "February/li[1]#0"]  # 23 February: United States, 2027 Chicago mayoral election
    assert (c.place_id, c.office_class, c.office_label) == ("iso:US", "mayor", "2027 Chicago mayoral election")
    kid = synth({"May": "<ul><li>7 May: <a>Sweden</a><ul><li>2027 Parliament</li></ul></li></ul>"})
    units, claims = mine(kid)
    assert [(u.outcome, u.reason) for u in units] == [("ignored", "container_item"), ("parsed", None)]
    assert [c.office_label for c in claims] == ["2027 Parliament"]


def test_tokens_that_name_places_are_not_offices() -> None:
    res = synth({"May": "<ul><li>7 May: <a>United States</a>, Orange County, Board of Supervisors</li></ul>"})
    units, claims = mine(res)
    (c,) = claims
    assert (c.place_id, c.jurisdiction, c.jurisdiction_kind, c.office_label, c.office_class) == (
        "iso:US", "Orange County", "named", "Board of Supervisors", "local_council",
    )
    assert [(u.outcome, u.reason) for u in units] == [("parsed", None)]
    # a token that is a subdivision of the place is not an office either
    res2 = synth({"May": "<ul><li>7 May: <a>Chile</a>, Region Metropolitana de Santiago, Mayor</li></ul>"})
    assert [(c.jurisdiction, c.jurisdiction_kind, c.office_label) for c in mine(res2)[1]] == [
        ("Region Metropolitana de Santiago", "subdivision", "Mayor"),
    ]


def test_election_word_makes_a_token_the_office() -> None:
    # the token with the election word starts the office text; the tokens after it stay in it
    res = synth({"May": "<ul><li>7 May: <a>Sweden</a>, Stockholm, Zorp election, Foo</li></ul>"})
    (c,) = mine(res)[1]
    assert (c.jurisdiction, c.office_label, c.office_class) == (
        "Stockholm", "Zorp election, Foo", "general",
    )
    # without the election word the last token is the office text
    res2 = synth({"May": "<ul><li>7 May: <a>Sweden</a>, Stockholm, Zorp</li></ul>"})
    (c2,) = mine(res2)[1]
    assert (c2.jurisdiction, c2.office_label) == ("Stockholm", "Zorp")


def test_containers_and_leaves_without_an_office_token() -> None:
    res = synth(
        {
            "May": (
                "<ul>"
                # all new tokens are subdivisions -> container_item; the children inherit them
                "<li>7 May: <a>United States</a>, Texas<ul><li>Austin, Mayor</li><li>Mayor</li><li>Foo, Zorp</li></ul></li>"
                # a token that is no subdivision -> container_text, tokens in leftover
                "<li>8 May: <a>United States</a>, Foo Bar<ul><li>Mayor</li></ul></li>"
                # leaf with one token: that token; leaf with several: the last is the office
                "<li>9 May: <a>United States</a>, Zorp</li>"
                "<li>10 May: <a>United States</a>, Foo, Zorp</li>"
                # a leaf with a place and nothing else
                "<li>11 May: <a>United States</a></li>"
                "</ul>"
            )
        }
    )
    units, claims = mine(res)
    got = [(u.unit_id.removeprefix(S), u.outcome, u.reason, u.leftover) for u in units]
    assert got == [
        ("May/li[1]", "ignored", "container_item", ""),
        ("May/li[1]/li[1]", "parsed", None, ""),
        ("May/li[1]/li[2]", "parsed", None, ""),
        ("May/li[1]/li[3]", "partial", "office_unrecognised", ""),
        ("May/li[2]", "unparsed", "container_text", "Foo Bar"),
        ("May/li[2]/li[1]", "parsed", None, ""),
        ("May/li[3]", "partial", "office_unrecognised", ""),
        ("May/li[4]", "partial", "office_unrecognised", ""),
        ("May/li[5]", "unparsed", "office_missing", ""),
    ]
    by_unit = {c.unit_id.removeprefix(S): c for c in claims}
    assert (by_unit["May/li[1]/li[1]"].jurisdiction, by_unit["May/li[1]/li[1]"].jurisdiction_kind) == (
        "Texas, Austin", "subdivision",
    )
    assert by_unit["May/li[1]/li[2]"].jurisdiction == "Texas"
    # a leaf under a container uses all its tokens as the office text
    assert (by_unit["May/li[1]/li[3]"].jurisdiction, by_unit["May/li[1]/li[3]"].office_label) == (
        "Texas", "Foo, Zorp",
    )
    assert (by_unit["May/li[2]/li[1]"].jurisdiction, by_unit["May/li[2]/li[1]"].jurisdiction_kind) == (
        "Foo Bar", "named",
    )
    assert (by_unit["May/li[3]"].jurisdiction, by_unit["May/li[3]"].office_label) == (None, "Zorp")
    assert (by_unit["May/li[4]"].jurisdiction, by_unit["May/li[4]"].office_label) == ("Foo", "Zorp")
    assert not [c for c in claims if c.unit_id.endswith(("May/li[2]", "May/li[5]"))]


def test_jurisdiction_tokens_are_de_duplicated() -> None:
    res = synth(
        {"May": "<ul><li>7 May: <a>United States</a>, Texas<ul><li>Texas, Mayor</li></ul></li></ul>"}
    )
    (c,) = mine(res)[1]
    assert (c.jurisdiction, c.jurisdiction_kind) == ("Texas", "subdivision")


def test_a_nested_item_with_its_own_date_keeps_the_inherited_place() -> None:
    res = synth(
        {"May": "<ul><li>7 May: <a>United States</a><ul><li>9 May: Texas, Mayor</li></ul></li></ul>"}
    )
    (c,) = mine(res)[1]
    assert (c.place_id, c.jurisdiction, c.span.start) == ("iso:US", "Texas", date(2026, 5, 9))


def test_an_empty_office_split_is_office_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wikipedia, "split_offices", lambda *_: [])
    units, claims = mine(synth({"May": "<ul><li>7 May: <a>Sweden</a>, Parliament</li></ul>"}))
    assert [(u.outcome, u.reason, u.leftover) for u in units] == [("unparsed", "office_missing", "")]
    assert not claims


def test_overrides_need_their_conditions() -> None:
    def one(item: str) -> Claim:
        (c,) = mine(synth({"May": f"<ul><li>{item}</li></ul>"}))[1]
        return c

    # Canada override needs jurisdiction kind "named": nationwide "federal by-election" is not it
    nationwide = one("7 May: <a>Canada</a>, federal by-election")
    assert (nationwide.office_class, nationwide.institution, nationwide.level) == ("general", None, "unknown")
    # a country with no single active lower house is left alone
    other = one("7 May: <a>Sweden</a>, Stockholm, 3rd congressional district, special election")
    assert (other.office_class, other.institution, other.aggregate, other.level) == (
        "legislature", None, True, "subnational",
    )
    # without a by-election word the district election is a candidate election
    plain = one("7 May: <a>United States</a>, Georgia, Georgia's 13th congressional district")
    assert (plain.office_class, plain.kind, plain.level) == ("lower_house", "candidate_election", "national")


def test_overrides_use_the_exactly_one_active_lower_house_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    chambers = REGISTRIES.institutions.chambers("iso:US")
    lower = [c for c in chambers if c.office_class == "lower_house" and c.active]
    assert len(lower) == 1
    doubled = (*chambers, lower[0])
    original = REGISTRIES.institutions.chambers
    monkeypatch.setattr(
        REGISTRIES.institutions, "chambers", lambda pid: doubled if pid == "iso:US" else original(pid)
    )
    res = synth({"May": "<ul><li>7 May: <a>United States</a>, Georgia, Georgia's 13th congressional district, special election</li></ul>"})
    (c,) = mine(res)[1]
    assert c.institution != "iso:US/house-of-representatives"


def test_a_month_turned_into_prose_rejects_that_page_and_only_that_page() -> None:
    data = json.loads(fixture("wikipedia", "national-2026.json"))
    text: str = data["parse"]["text"]
    start = text.index("<ul>", text.index('id="November"'))
    stop = text.index('<div class="mw-heading mw-heading2"', start)
    prose = text[start:stop].replace("<ul>", "").replace("</ul>", "").replace("<li>", "<p>")
    data["parse"]["text"] = text[:start] + prose.replace("</li>", "</p>") + text[stop:]
    request = next(p.request for p in ALL4.pages if p.request.key == "national-2026")
    edited = result(json.dumps(data).encode(), url=request.url, content_type=JSON_TYPE)
    raw = raw_pages(
        "wikipedia",
        [(p.request, edited if p.request == request else p.result) for p in ALL4.pages],
    )
    res = Wikipedia().parse(raw, WINDOW, REGISTRIES)
    assert check(raw, res).ok
    full = Wikipedia().parse(ALL4, WINDOW, REGISTRIES)
    assert [(c.key, c.outcome) for c in res.coverage] == [
        ("national-2026", "layout_not_recognised"), ("national-2027", "ok"),
        ("local-2026", "ok"), ("local-2027", "ok"),
    ]
    assert res.coverage[1:] == full.coverage[1:]
    rest = "wikipedia:national-2026@"
    assert [u for u in res.units if u.unit_id.startswith(rest)] == []
    assert [u for u in res.units if not u.unit_id.startswith(rest)] == [
        u for u in full.units if not u.unit_id.startswith(rest)
    ]
    assert list(res.claims) == [c for c in full.claims if not c.unit_id.startswith(rest)]
    (reason,) = res.reasons
    assert reason.code == "layout_not_recognised"
    assert reason.detail == "national-2026: section November: text in <p>"
