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
from tests.support.appendix_b import appendix_b
from tests.support.claims import list_order
from tests.support.fixture_claims import FIXTURE_NOW, fixture_claims, fixture_results


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


def testappendix_b() -> None:
    cards = {card.group_id: card for card in fixture_result().cards}
    rows = appendix_b()
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
