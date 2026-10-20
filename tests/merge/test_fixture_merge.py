"""The fixture claims that the merge tests build on, and the fixture merged end to end."""

import functools
from collections import Counter
from datetime import date
from typing import Any

from elections_calendar.ledger import check
from elections_calendar.merge import merge
from elections_calendar.merge.match import match
from elections_calendar.model import Card, Child, Claim, Disposition, MergeResult
from elections_calendar.places import PlaceRegistry
from elections_calendar.window import window_for
from tests.support.claims import list_order
from tests.support.fixture_claims import FIXTURE_NOW, fixture_claims, fixture_results

WPN = "wikipedia:national-2026@rev1380221397"
WPL = "wikipedia:local-2026@rev1380378807"
DOT = " · "


def test_fixture_claims() -> None:
    claims = fixture_claims()
    assert Counter(c.source for c in claims) == {
        "electionguide": 243,
        "wikipedia": 543,
        "osce": 180,
        "ipu": 234,
        "aweb": 31,
        "carter": 18,
        "eeas": 23,
        "ndi": 38,
        "eisa": 25,
    }
    assert len(claims) == 1335
    for source, (raw, parsed) in fixture_results().items():
        assert check(raw, parsed).ok, source
    assert len({c.claim_id for c in claims}) == len(claims)
    assert fixture_claims() is fixture_claims()


# --- the fixture merge end to end (Appendix B, R4, R8, R13) --------------------------------------


@functools.cache
def fixture_result() -> MergeResult:
    return merge(fixture_claims(), now=FIXTURE_NOW, places=PlaceRegistry.load())


def _source(merge_id: str) -> str:
    return merge_id.removeprefix("served/").split(":")[0]


def _children() -> list[Child]:
    return [ch for card in fixture_result().cards for ch in card.children]


def _card_of_child() -> dict[str, Card]:
    return {ch.child_id: card for card in fixture_result().cards for ch in card.children}


def _dispositions() -> dict[str, Disposition]:
    return {d.merge_id: d for d in fixture_result().dispositions}


def _iso(day: date | None) -> str:
    assert day is not None
    return day.isoformat()


def test_fixture_merge_counts() -> None:
    result = fixture_result()
    children = _children()
    assert len(result.cards) == 742
    assert len(children) == 988
    assert len(result.dispositions) == 1335
    assert Counter(d.kind for d in result.dispositions) == {
        "standalone": 602,
        "anchor_member": 557,
        "attached": 58,
        "umbrella_link": 47,
        "attention": 36,
        "undated": 35,
    }
    anchored = {t for d in result.dispositions if d.kind == "anchor_member" for t in d.targets}
    standalone = {t for d in result.dispositions if d.kind == "standalone" for t in d.targets}
    assert (len(anchored), len(standalone)) == (397, 591)
    assert anchored | standalone == {ch.child_id for ch in children}
    aggregate = {ch.child_id for ch in children if ch.aggregate}
    assert len(aggregate) == 150
    assert aggregate <= standalone
    assert not any(ch.ambiguous for ch in children)

    assert len(result.attention) == 67
    assert Counter((i.kind, i.reason, i.relevance) for i in result.attention) == {
        ("undated_listing", "undated", "in_or_after_window"): 31,
        ("unresolved_evidence", "no_candidate", "before_window"): 24,
        ("unresolved_evidence", "several_candidates", "before_window"): 7,
        ("unresolved_evidence", "several_candidates", "in_or_after_window"): 5,
    }
    evidence = [
        i
        for i in result.attention
        if i.kind == "unresolved_evidence" and i.relevance == "in_or_after_window"
    ]
    assert sorted(
        (i.item_id, i.source, i.text, i.merge_ids, i.possible_matches) for i in evidence
    ) == [
        (
            "36ad1dcad007",
            "eeas",
            "Peru: EU election observation mission (2026)",
            ("served/eeas:missions/r2c2#0",),
            ("10bce39f7c6a", "40c90cc9183c", "be9c226b2d9a", "fd914fc6ede2"),
        ),
        (
            "612356b9548b",
            "eeas",
            "Sao Tome and Principe: EU election observation mission (2026)",
            ("served/eeas:missions/r4c1#0",),
            ("2b76c271e7be", "eb7084dbf7f1"),
        ),
        (
            "b98546e8d6db",
            "eeas",
            "Zambia: EU election observation mission (2026)",
            ("served/eeas:missions/r3c2#0",),
            ("3b43a9575bcc", "964b76e3a20e", "d3effb731ef3"),
        ),
        (
            "c8534f5327a6",
            "eeas",
            "Bangladesh: EU election observation mission (2026)",
            ("served/eeas:missions/r3c1#0",),
            ("37f6037fd15b", "a8031995b7b2", "d97dacc76861"),
        ),
        (
            "ed745bd6cbe3",
            "eeas",
            "Colombia: EU election observation mission (2026)",
            ("served/eeas:missions/r2c1#0",),
            ("10b7dbe42fb7", "45a7ab6234dd", "862d26542ee0", "be76457bc81c"),
        ),
    ]

    listings = result.undated
    assert len(listings) == 31
    assert Counter(len(u.claims) for u in listings) == {1: 27, 2: 4}
    assert not any(u.possible_matches for u in listings)
    pairs = [u for u in listings if len(u.claims) == 2]
    assert sorted(c.claim_id for u in pairs for c in u.claims if c.source == "osce") == [
        f"osce:elections/r{n}#0" for n in range(24, 28)
    ]
    for u in pairs:
        assert sorted(c.source for c in u.claims) == ["osce", "wikipedia"]
        (wiki,) = (c for c in u.claims if c.source == "wikipedia")
        assert wiki.claim_id.startswith("wikipedia:national-2027@rev1379360216/Unknown_date/")

    assert sorted(
        (ch.office_label, _iso(ch.span.start)) for ch in children if ch.date_conflict
    ) == [
        ("Cabo Verdean Presidency", "2026-11-15"),
        ("Nigerian House of Representatives", "2027-01-16"),
        ("Nigerian Senate", "2027-01-16"),
    ]
    assert sum(ch.status_conflict for ch in children) == 0
    assert sum(ch.unverified for ch in children) == 0
    assert sum(ch.occurrence_confirmed for ch in children) == 197
    assert not any(ch.rescheduled_from or ch.provisional_date for ch in children)

    matched = [ch for ch in children if ch.possible_matches]
    assert len(matched) == 4
    by_id = {ch.child_id: ch for ch in children}
    for ch in matched:
        assert len(ch.possible_matches) == 1
        other = by_id[ch.possible_matches[0]]
        assert other.possible_matches == (ch.child_id,)
        assert other.place_id == ch.place_id
    assert Counter(ch.place_id for ch in matched) == {"iso:KG": 2, "iso:CM": 2}

    links = [d for d in result.dispositions if d.kind == "umbrella_link"]
    assert sum(len(d.targets) for d in links) == 120
    assert Counter(len(d.targets) for d in links) == {1: 15, 2: 18, 3: 9, 6: 4, 18: 1}
    card_of = _card_of_child()
    wide = {d.merge_id for d in links if len({card_of[t].group_id for t in d.targets}) > 1}
    assert wide == {"served/aweb:calendar/r3#0", "served/ndi:p0/upcoming-c10#0"}
    assert len(links) - len(wide) == 45
    assert Counter(_source(d.merge_id) for d in links) == {
        "ndi": 13,
        "aweb": 12,
        "wikipedia": 11,
        "osce": 9,
        "eisa": 2,
    }
    dispositions = _dispositions()
    partial = 0
    for card in result.cards:
        in_card = {ch.child_id for ch in card.children}
        for umbrella in card.umbrellas:
            covered = set(dispositions[umbrella.merge_id].targets) & in_card
            assert covered
            partial += len(covered) < len(in_card)
    assert partial == 4

    assert Counter(ch.status for ch in children) == {"Held": 613, "Upcoming": 375}
    assert Counter(s.rejected_reason for ch in children for s in ch.sources) == {
        None: 988,
        "less_certain": 161,
        "lower_evidence": 33,
        "not_covering": 17,
        "lower_priority": 9,
        "observation": 5,
        "year_only": 3,
        "less_precise": 1,
    }

    window = window_for(FIXTURE_NOW)
    inside = [card for card in result.cards if window.overlaps(card.span)]
    assert len(inside) == 100
    assert sum(len(card.children) for card in inside) == 202
    assert Counter(card.status for card in inside) == {"Upcoming": 59, "Held": 41}
    assert Counter(card.span.precision for card in inside) == {"day": 95, "month": 5}

    assert max(len(card.type) for card in result.cards) == 200
    largest = max(result.cards, key=lambda card: len(card.children))
    assert (largest.place_id, largest.level, largest.span.start, len(largest.children)) == (
        "iso:US",
        "subnational",
        date(2026, 11, 3),
        59,
    )

    claims = fixture_claims()
    observations = [c for c in claims if c.evidence_kind == "observation"]
    assert Counter(dispositions[c.merge_id].kind for c in observations) == {
        "attention": 36,
        "attached": 5,
    }
    assert sum(c.span.precision == "year" for c in claims) == 61


def _view(card: Card) -> tuple[Any, ...]:
    """A card as the Appendix B table states it."""
    return (
        card.group_id,
        card.place_id,
        card.level,
        _iso(card.span.start),
        _iso(card.span.end),
        card.span.precision,
        card.date_meaning,
        card.date_status,
        card.status,
        card.type,
        tuple(
            (
                ch.child_id,
                ch.aggregate,
                ch.date_conflict,
                tuple((s.claim.merge_id, s.rejected_reason) for s in ch.sources),
            )
            for ch in card.children
        ),
        sorted(u.merge_id for u in card.umbrellas),
    )


def _eg(page: str, row: int) -> str:
    return f"served/electionguide:{page}/r{row}#0"


def _less(claim: str, reason: str = "less_certain") -> tuple[str, str]:
    return (claim, reason)


def _child(
    child_id: str,
    selected: str,
    *others: tuple[str, str],
    aggregate: bool = False,
    conflict: bool = False,
) -> tuple[Any, ...]:
    return (child_id, aggregate, conflict, ((selected, None), *others))


def _row(
    group_id: str,
    place: str,
    level: str,
    dates: str,
    date_status: str,
    status: str,
    type_: str,
    children: list[tuple[Any, ...]],
    umbrellas: list[str],
) -> tuple[Any, ...]:
    start, _, end = dates.partition(" to ")
    return (
        group_id,
        place,
        level,
        start,
        end or start,
        "day",
        "voting_period",
        date_status,
        status,
        type_,
        tuple(children),
        sorted(umbrellas),
    )


def _appendix_b() -> list[tuple[Any, ...]]:
    n = f"served/{WPN}"
    local = f"served/{WPL}"
    governors = "2b844b3ca773 35eb32947fa0 073382e19da1 44bb208b4d0b 75fde6bff123 081cccbcc211 19387752fb15 1f89511d91cc d45e8a31e7a1 13df4c00d608 86e5eae386c7 876f29950cf7 6b25112ee8a5 fbfc708ccaaf 51f6dd2bcb50 e81e7ee84dc0 b8729ff253bf 3cfdd6789f20"
    return [
        _row("fcd48da30f32", "iso:SE", "national", "2026-09-13", "confirmed", "Held",
             "Swedish Parliament",
             [_child("451e4f4c0054", _eg("past", 13), _less("served/osce:elections/r34#0"),
                     _less(f"{n}/September/li[1]#0"))], []),
        _row("4f4a086286ed", "iso:SE", "subnational", "2026-09-13", "unknown", "Held",
             "regional and municipal elections",
             [_child("16b1e5c54480", f"{local}/September/li[4]/li[2]#0", aggregate=True)], []),
        _row("c7558bb61e25", "x:south-ossetia", "national", "2026-09-18", "unknown", "Held",
             "President", [_child("5f80a5eff1aa", f"{n}/September/li[2]#0")], []),
        _row("0854d007f42e", "iso:RU", "national", "2026-09-18 to 2026-09-20", "confirmed", "Held",
             "Russian State Duma",
             [_child("4856e73735ea", _eg("past", 12),
                     _less("served/osce:elections/r33#0", "not_covering"),
                     _less(f"{n}/September/li[3]#0"),
                     _less("served/aweb:calendar/r23#0", "not_covering"))], []),
        _row("af23c8e10357", "iso:MA", "national", "2026-09-23", "confirmed", "Held",
             "Moroccan Chamber of Representatives",
             [_child("b5e3f77c0c1b", _eg("past", 11), _less(f"{n}/September/li[4]#0"),
                     _less("served/ndi:p0/past-c5#0"), _less("served/eisa:y2026/r13#0"))], []),
        _row("2064e8f68b8c", "iso:IM", "national", "2026-09-24", "unknown", "Held",
             "House of Keys", [_child("b74251137bc8", f"{n}/September/li[5]#0")], []),
        _row("8818bc29cc27", "iso:ST", "national", "2026-09-27", "confirmed", "Held",
             "Sao Tomean National Assembly",
             [_child("2b76c271e7be", _eg("past", 10), _less(f"{n}/September/li[6]/li[1]#0"),
                     _less("served/ndi:p0/past-c4#0"), _less("served/eisa:y2026/r15#0"))], []),
        _row("54b356d5b5ea", "iso:BR", "national", "2026-10-04", "confirmed", "Held",
             f"Brazilian Presidency (1st round){DOT}Brazilian Chamber of Deputies{DOT}"
             "Brazilian Federal Senate",
             [_child("baa1bb5de7fe", _eg("past", 4), _less(f"{n}/October/li[2]/li[2]#0")),
              _child("219ff0785bdd", _eg("past", 7), _less(f"{n}/October/li[2]/li[2]#1")),
              _child("aefc0f383484", _eg("past", 3), _less(f"{n}/October/li[2]/li[2]#2"))],
             ["served/aweb:calendar/r25#0", "served/ndi:p0/past-c2#0"]),
        _row("c8c9844ab7a8", "iso:BR", "subnational", "2026-10-04", "unknown", "Held",
             "Governors: Alagoas, Amazonas, Bahia, Ceará, Espírito Santo, "
             "Federal District, Goiás, Maranhão, Minas Gerais, Pará, Paraíba, "
             "Paraná, Pernambuco, Rio de Janeiro, Rio Grande do Norte (+3 more) (18)",
             [_child(child_id, f"{local}/October/li[1]/li[1]/li[{i}]#0")
              for i, child_id in enumerate(governors.split(), start=1)],
             [f"{local}/October/li[1]/li[1]#0"]),
        _row("d01ed25c943e", "iso:PY", "subnational", "2026-10-04", "unknown", "Held",
             "municipal elections",
             [_child("9ea96cd48d74", f"{local}/October/li[1]/li[3]#0", aggregate=True)], []),
        _row("05f32126cb43", "iso:PE", "subnational", "2026-10-04", "unknown", "Held",
             "Lima: Mayor", [_child("1ba2f246cd98", f"{local}/October/li[1]/li[4]/li[1]#0")],
             ["served/ndi:p0/past-c1#0", f"{local}/October/li[1]/li[4]#0"]),
        _row("cc453aae6835", "iso:GB", "national", "2026-10-08", "unknown", "Held",
             "Holborn and St Pancras: House of Commons by-election",
             [_child("d5cc461fb60f", f"{local}/October/li[3]/li[2]#0")], []),
        _row("abf124b4c48f", "iso:CZ", "subnational", "2026-10-09 to 2026-10-10", "unknown",
             "Held", "municipal elections",
             [_child("fd0fffe821dc", f"{local}/October/li[4]#0", aggregate=True)], []),
        _row("d8b6179b8850", "iso:SK", "subnational", "2026-10-24", "unknown", "Upcoming",
             "regional and local elections",
             [_child("117d9dff3af3", f"{local}/October/li[9]/li[2]#0", aggregate=True)], []),
        _row("4b35f9d2401c", "iso:BR", "national", "2026-10-25", "confirmed", "Upcoming",
             "Brazilian Presidency (2nd round)",
             [_child("f90b0d7db440", _eg("upcoming", 3), _less(f"{n}/October/li[6]/li[3]#0"))],
             ["served/aweb:calendar/r27#0"]),
        _row("c5842ef99109", "iso:RS", "national", "2026-10-25", "confirmed", "Upcoming",
             "Serbian National Assembly",
             [_child("bcb7e2ccdf47", _eg("upcoming", 2), _less("served/osce:elections/r2#0"),
                     _less(f"{n}/October/li[6]/li[2]#0"),
                     _less("served/ndi:p0/upcoming-c2#0", "not_covering"),
                     _less("served/ipu:elections/r222#0", "lower_evidence"))], []),
        _row("f65719631682", "iso:GD", "national", "2026-11-05", "unknown", "Upcoming",
             "House of Representatives",
             [_child("1e8c23148913", f"{n}/November/li[2]#0",
                     _less("served/ipu:elections/r105#0", "lower_evidence"))], []),
        _row("32dd654de9aa", "iso:NZ", "national", "2026-11-07", "confirmed", "Upcoming",
             "New Zealand House of Representatives",
             [_child("1e8e1a5746c8", _eg("upcoming", 16), _less(f"{n}/November/li[3]#0"),
                     _less("served/ipu:elections/r180#0", "lower_evidence"))], []),
        _row("b65b9fe5b9b3", "iso:CV", "national", "2026-11-15", "confirmed", "Upcoming",
             "Cabo Verdean Presidency",
             [_child("eae5cc187a1a", _eg("upcoming", 17), _less(f"{n}/November/li[4]#0"),
                     _less("served/ndi:p0/upcoming-c4#0"),
                     _less("served/eisa:y2026/r7#0", "not_covering"), conflict=True)], []),
        _row("4e451911e2f5", "iso:SI", "subnational", "2026-11-15", "unknown", "Upcoming",
             "Local Elections",
             [_child("ca2bd502e0e0", "served/osce:elections/r4#0", aggregate=True)], []),
        _row("64539229886f", "iso:ES", "national", "2026-11-29", "confirmed", "Upcoming",
             f"Spanish Congress of Deputies{DOT}Spanish Senate",
             [_child("ad420bd35f9c", _eg("upcoming", 18), _less(f"{n}/November/li[5]/li[1]#1"),
                     _less("served/ipu:elections/r236#0", "lower_evidence")),
              _child("8199c9644471", _eg("upcoming", 19), _less(f"{n}/November/li[5]/li[1]#0"),
                     _less("served/ipu:elections/r237#0", "lower_evidence"))],
             ["served/osce:elections/r5#0"]),
        _row("4a02993930ce", "iso:CH", "national", "2026-11-29", "confirmed", "Upcoming",
             "Referendum",
             [_child("22e9f7b733fe", _eg("upcoming", 20), _less(f"{n}/November/li[5]/li[2]#0"))],
             []),
        _row("792ca8cad502", "iso:CZ", "national", "2026-10-09 to 2026-10-10", "confirmed",
             "Held", "Czech Senate (1st round)",
             [_child("d3df127ddfa9", _eg("past", 2), _less(f"{n}/October/li[3]#0"))], []),
    ]


def test_appendix_b() -> None:
    cards = {card.group_id: card for card in fixture_result().cards}
    rows = _appendix_b()
    assert len(rows) == 23
    for row in rows:
        assert _view(cards[row[0]]) == row, row[0]


def test_unmatched_renewal_is_expected_not_announced() -> None:
    ipu_only = [ch for ch in _children() if all(s.claim.source == "ipu" for s in ch.sources)]
    assert len(ipu_only) == 201
    for ch in ipu_only:
        assert (ch.date_status, ch.date_meaning, ch.status) == (
            "tentative",
            "expected_window",
            "Upcoming",
        )
    assert Counter(ch.span.precision for ch in ipu_only) == {"month": 181, "day": 20}
    window = window_for(FIXTURE_NOW)
    assert sorted(
        (ch.place_id, ch.office_label, _iso(ch.span.start)[:7])
        for ch in ipu_only
        if window.overlaps(ch.span)
    ) == [
        ("iso:CM", "National Assembly", "2027-01"),
        ("iso:LY", "House of Representatives", "2026-12"),
        ("iso:MG", "Senate", "2026-12"),
        ("iso:SO", "Upper House", "2026-12"),
    ]


def test_year_precision_claims_are_undated() -> None:
    dispositions = _dispositions()
    year = [c for c in fixture_claims() if c.span.precision == "year"]
    assert len(year) == 61
    assert Counter(dispositions[c.merge_id].kind for c in year) == {
        "undated": 35,
        "attention": 22,
        "attached": 4,
    }

    def sources(kind: str) -> Counter[str]:
        return Counter(c.source for c in year if dispositions[c.merge_id].kind == kind)

    assert sources("undated") == {"wikipedia": 24, "osce": 7, "eisa": 3, "ndi": 1}
    assert sources("attention") == {"eeas": 22}
    assert sources("attached") == {"wikipedia": 2, "osce": 1, "eeas": 1}
    for n in range(24, 31):
        assert dispositions[f"served/osce:elections/r{n}#0"].kind == "undated"
    attached = dispositions["served/osce:elections/r6#0"]
    assert (attached.kind, attached.targets) == ("attached", ("f4ad0477ca3a",))
    (child,) = (ch for ch in _children() if ch.child_id == "f4ad0477ca3a")
    assert child.office_label == "Early Presidential Election"
    reasons = {s.claim.merge_id: s.rejected_reason for s in child.sources}
    assert reasons["served/osce:elections/r6#0"] == "year_only"
    assert not [c for c in year if c.source == "eeas" and dispositions[c.merge_id].kind == "undated"]


def test_a_year_only_claim_stays_visible() -> None:
    dispositions = _dispositions()
    haiti = dispositions["served/ndi:p0/upcoming-c7#0"]
    assert (haiti.kind, haiti.targets) == ("undated", ("fd43d6447fdf",))
    (item,) = (i for i in fixture_result().attention if i.item_id == "f6e0fc10981e")
    assert (item.kind, item.relevance, item.undated_id) == (
        "undated_listing",
        "in_or_after_window",
        "fd43d6447fdf",
    )
    assert item.text == "Haiti: 2026 Haiti General Election (Phase 1) (Date TBD) (2026), date not given"

    salvador = dispositions["served/ndi:p0/upcoming-c10#0"]
    assert (salvador.kind, salvador.targets) == ("umbrella_link", ("846a4e205782", "c06f962c22e2"))
    card_of = _card_of_child()
    assert card_of["846a4e205782"].group_id == "fb957eb6f305"
    assert card_of["c06f962c22e2"].group_id == "51f6324c23ed"


def test_fixture_order() -> None:
    places = PlaceRegistry.load()
    claims = fixture_claims()
    reverse: tuple[Claim, ...] = tuple(reversed(claims))
    assert merge(reverse, now=FIXTURE_NOW, places=places) == fixture_result()
    assert list_order(match(reverse, FIXTURE_NOW)) == list_order(match(claims, FIXTURE_NOW))
