"""Unit attention items (P87, P88; R20): what the merge cannot see, because a unit has no claim."""

import dataclasses
from collections import Counter
from datetime import date

from elections_calendar.model import MAX_ATTENTION_TEXT, AttentionItem, InputUnit, short_id
from elections_calendar.snapshots import (
    Decision,
    Disappeared,
    build_snapshot,
    decide,
    snapshot_id,
    unit_items,
)
from elections_calendar.text import collapse_ws
from elections_calendar.window import window_for
from tests.snapshots.test_decide import (
    EG,
    OLD,
    OTHERS,
    YEARLY,
    A,
    B,
    C,
    G,
    listing,
    run,
    unparsed,
)
from tests.support.claims import day, mk, year
from tests.support.fixture_claims import FIXTURE_NOW, fixture_results
from tests.support.snapshots import NOW, REGISTRY, T0, SynthPage, promoted, report, synth


def _fixture_items() -> list[AttentionItem]:
    items: list[AttentionItem] = []
    window = window_for(FIXTURE_NOW)
    for raw, result in fixture_results().values():
        snapshot = build_snapshot(
            raw, result, parser_version="2.0", registry_version=REGISTRY, years=window.years
        )
        d = decide(
            snapshot,
            run_outcome="complete",
            run_detail="",
            ledger=report(snapshot),
            baseline=None,
            baseline_problem=None,
            acceptances=(),
            window=window,
            now=FIXTURE_NOW,
        )
        assert d.acceptance == "promoted"
        items += unit_items(d)
    return items


def test_unit_items_on_the_fixtures() -> None:
    items = _fixture_items()
    assert len(items) == 121
    assert Counter(i.source for i in items) == {
        "wikipedia": 111,
        "ipu": 4,
        "aweb": 3,
        "ndi": 1,
        "eisa": 2,
    }
    wiki = [i for i in items if i.source == "wikipedia"]
    assert Counter(i.kind for i in wiki) == {"partial_unit": 60, "unparsed_unit": 51}
    pages = Counter(i.unit_id.split(":")[1].split("@")[0].split("/")[0] for i in wiki if i.unit_id)
    assert pages == {"local-2026": 61, "local-2027": 48, "national-2026": 2}
    assert Counter((i.source, i.reason) for i in items) == {
        ("wikipedia", "article_title"): 46,
        ("wikipedia", "office_not_modelled"): 34,
        ("wikipedia", "office_unrecognised"): 31,
        ("ipu", "designation_unrecognised"): 4,
        ("aweb", "level_unresolved"): 1,
        ("aweb", "office_not_modelled"): 1,
        ("aweb", "office_unrecognised"): 1,
        ("ndi", "level_unresolved"): 1,
        ("eisa", "no_new_date"): 2,
    }
    assert Counter(i.relevance for i in items) == {"in_or_after_window": 90, "unknown": 31}
    dated = [i.date for i in items if i.date is not None]
    assert len(dated) == 63
    assert sum(d > window_for(FIXTURE_NOW).end for d in dated) == 2
    assert not any("api.php" in i.link for i in items)
    assert all(i.link.startswith("https://en.wikipedia.org/wiki/") for i in wiki)
    eisa = sorted(i.text for i in items if i.source == "eisa")
    assert eisa == [
        "Libya (from the row above) | House of Representatives | Postponed from April 2026",
        "Libya | Presidential | Postponed from April 2026",
    ]
    assert all(i.snapshot_id and i.merge_ids == () and i.unit_text for i in items)


def test_unit_items_follow_the_served_snapshot() -> None:
    u1 = unparsed("osce:p1/u1", "Gambia:  vote on 5 December")
    u2 = unparsed("osce:p1/u2", "Benin: vote in 2027")
    base = promoted(
        synth(
            pages=(SynthPage("p1", claims=(A, B), extra=(u1,)), SynthPage("p2", claims=(C,))),
            fetched_at=T0,
        )
    )
    cand = synth(
        pages=(SynthPage("p1", claims=(A, B), extra=(u2,)), SynthPage("p2", outcome="timeout")),
        fetched_at=NOW,
    )
    d = run(cand, base)
    assert d.acceptance == "fallback"
    assert d.provisional_units == (u2,)
    by_kind = {i.kind: i for i in unit_items(d)}
    assert sorted(by_kind) == ["provisional_change", "unparsed_unit"]
    served = by_kind["unparsed_unit"]
    assert (served.unit_id, served.snapshot_id) == (u1.unit_id, base.snapshot.snapshot_id)
    assert served.text == served.unit_text == "Gambia: vote on 5 December"
    prov = by_kind["provisional_change"]
    assert (prov.unit_id, prov.snapshot_id) == (u2.unit_id, cand.snapshot_id)
    assert prov.text == "From an incomplete fetch: Benin: vote in 2027"
    assert prov.unit_text is None
    assert prov.reason == "no date"
    assert prov.link == "https://osce.test/p1"
    items = unit_items(d)
    assert [i.item_id for i in items] == sorted(short_id([i.kind, i.unit_id or ""]) for i in items)

    pending = unparsed("osce:p1/u3", "Mali: vote soon")
    cut = synth(
        pages=(SynthPage("p1", claims=(A,), extra=(pending,)), SynthPage("p2", outcome="timeout")),
        fetched_at=NOW,
    )
    gone = run(cut)
    assert gone.acceptance == "unavailable"
    assert pending in gone.candidate.units
    assert unit_items(gone) == ()


def _gone_decision() -> tuple[Decision, Disappeared]:
    texts = ((G.unit_id, "Gambia: Presidential"),)
    page = SynthPage("upcoming", claims=(G, OLD, YEARLY), texts=texts)
    b0 = promoted(synth(source="electionguide", pages=(page,), fetched_at=T0))
    d = run(listing(*OTHERS, at=NOW), b0)
    assert len(d.disappeared) == 1
    return d, d.disappeared[0]


def test_disappeared_items() -> None:
    d, gone = _gone_decision()
    (item,) = unit_items(d)
    assert item.kind == "disappeared_unit"
    assert item.item_id == short_id(["disappeared_unit", gone.source_event_id])
    assert (
        item.text == "No longer listed by ElectionGuide: Gambia: Presidential, was 15 November 2026"
    )
    assert item.date == date(2026, 11, 15)
    assert item.unit_id == gone.unit_id == G.unit_id
    assert item.unit_id.startswith(EG)
    assert item.reason == "disappeared"
    assert item.relevance == "in_or_after_window"
    assert item.link == gone.link
    assert d.served is not None and item.snapshot_id == d.served.snapshot_id
    assert item.source == "electionguide"
    assert (item.unit_text, item.merge_ids, item.possible_matches) == (None, (), ())


def test_unit_item_ids_are_stable() -> None:
    units = tuple(unparsed(f"osce:p1/u{i}", f"Country {i}: vote soon") for i in range(1, 9))
    base = promoted(synth(pages=(SynthPage("p1", claims=(A,), extra=units),), fetched_at=T0))
    d = run(synth(pages=(SynthPage("p1", claims=(A,), extra=units),), fetched_at=NOW), base)
    first, second = unit_items(d), unit_items(d)
    assert len(first) == 8
    assert [i.item_id for i in first] == sorted(short_id([i.kind, i.unit_id or ""]) for i in first)
    assert first == second
    assert [i.item_id for i in first] == sorted(i.item_id for i in first)
    assert len({i.item_id for i in first}) == 8


def test_unit_items_carry_the_full_text() -> None:
    head = "Kenya: " + "x" * 293
    long = unparsed("osce:p1/u1", head + "a" * 100, "in_or_after_window")
    other = unparsed("osce:p1/u2", head + "b" * 100, "in_or_after_window")
    assert len(long.text) == 400
    d = run(synth(pages=(SynthPage("p1", claims=(A,), extra=(long, other)),), fetched_at=NOW))
    a, b = sorted(unit_items(d), key=lambda i: i.unit_id or "")
    assert a.text == b.text == head[:MAX_ATTENTION_TEXT]
    assert len(a.text) == MAX_ATTENTION_TEXT
    assert a.unit_text == collapse_ws(long.text) and len(a.unit_text) == 400
    assert b.unit_text == collapse_ws(other.text) and a.unit_text != b.unit_text

    gone, _ = _gone_decision()
    assert [i.unit_text for i in unit_items(gone)] == [None]
    base = promoted(synth(pages=(SynthPage("p1", claims=(A,)),), fetched_at=T0))
    cand = synth(
        pages=(SynthPage("p1", claims=(A,), extra=(long,)), SynthPage("p2", outcome="timeout")),
        fetched_at=NOW,
    )
    (prov,) = unit_items(run(cand, base))
    assert prov.kind == "provisional_change" and prov.unit_text is None
    assert len(prov.text) == MAX_ATTENTION_TEXT


def test_unit_items_skip_units_before_the_window() -> None:
    early = unparsed("osce:p1/u1", "Togo: vote in 2025", "before_window")
    shown = unparsed("osce:p1/u2", "Mali: vote soon")
    d = run(synth(pages=(SynthPage("p1", claims=(A,), extra=(early, shown)),), fetched_at=NOW))
    assert [i.unit_id for i in unit_items(d)] == [shown.unit_id]


def test_unit_item_date_and_link_come_from_the_served_claims() -> None:
    partial = InputUnit("osce:p1/u1", "osce", "Mali:  two votes", "partial", "level", "unknown")
    claims = (
        mk(partial.unit_id, 0, span=day(2026, 11, 22), link="https://example.test/first"),
        mk(partial.unit_id, 1, span=day(2026, 11, 8), link="https://example.test/second"),
        mk(partial.unit_id, 2, span=year(2026)),
    )
    snap = synth(pages=(SynthPage("p1", claims=claims),), fetched_at=NOW)
    units = (partial,)
    snap = dataclasses.replace(snap, units=units, snapshot_id=snapshot_id(units, snap.claims))
    d = dataclasses.replace(run(synth(pages=(SynthPage("p1", 1),), fetched_at=NOW)), served=snap)
    (item,) = unit_items(d)
    assert item.kind == "partial_unit"
    assert item.date == date(2026, 11, 8)
    assert item.link == "https://example.test/first"
    assert item.text == item.unit_text == "Mali: two votes"
    only_year = dataclasses.replace(
        snap, claims=claims[2:], snapshot_id=snapshot_id(units, claims[2:])
    )
    (item,) = unit_items(dataclasses.replace(d, served=only_year))
    assert item.date is None
    assert item.link == claims[2].link


def test_an_orphan_unit_keeps_its_item() -> None:
    orphan = unparsed("osce:p1/u1", "Mali: vote soon")
    d = run(synth(pages=(SynthPage("p1", claims=(A,), extra=(orphan,)),), fetched_at=NOW))
    assert d.served is not None
    page = d.served.pages[0]
    moved = dataclasses.replace(page, unit_prefix="osce:elsewhere/")
    lost = dataclasses.replace(d.served, pages=(moved,))
    (item,) = unit_items(dataclasses.replace(d, served=lost))
    assert (item.unit_id, item.link) == (orphan.unit_id, page.link)
    none = dataclasses.replace(d.served, pages=())
    (item,) = unit_items(dataclasses.replace(d, served=none))
    assert (item.unit_id, item.link) == (orphan.unit_id, "")
