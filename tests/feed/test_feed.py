"""The v2 feed document (spec §5.3-§5.5, §5.7; P84-P87, P97; R5, R17, R20, R24)."""

import dataclasses
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from functools import cache
from typing import Any

from elections_calendar.feed import (
    MAX_FEED_ITEMS,
    FeedParts,
    RunInfo,
    SourceResult,
    build_feed,
)
from elections_calendar.merge import merge
from elections_calendar.model import (
    SOURCE_NAMES,
    SOURCE_ORDER,
    AttentionItem,
    MergeResult,
    Reason,
    _utc_iso,
)
from elections_calendar.places import PlaceRegistry
from elections_calendar.window import Window, window_for
from tests.support.claims import EGU, GD, NOW, OBS, WPn, cl, day, year
from tests.support.feed import RUN_NOW, first_run
from tests.support.unit_items import item

RUN = RunInfo("local", ())
EMPTY = MergeResult((), (), (), ())

CARD_KEYS = [
    "date", "country", "type", "status", "sources", "source_names", "links", "group_id",
    "end_date", "date_precision", "date_meaning", "date_status", "level", "place_id",
    "country_code", "children", "umbrella_sources", "umbrellas",
]  # fmt: skip
CHILD_KEYS = [
    "child_id", "jurisdiction", "jurisdiction_kind", "institution", "office_class",
    "office_label", "kind", "round", "indirect", "aggregate", "occurrence_confirmed",
    "status_conflict", "date_conflict", "unverified", "ambiguous", "rescheduled_from",
    "provisional_date", "possible_matches", "possible_matches_outside", "sources",
]  # fmt: skip
CHILD_SOURCE_KEYS = [
    "name", "link", "source_event_id", "date", "end_date", "date_precision", "date_text",
    "date_meaning", "date_status", "status_claim", "fetched_at", "fallback", "provisional",
    "evidence_kind", "selected", "rejected_reason",
]  # fmt: skip
UMBRELLA_KEYS = ["name", "link", "office_label", "date_text", "children"]
LISTING_KEYS = [
    "undated_id", "place_id", "country", "office_label", "year", "sources", "possible_matches",
    "possible_matches_outside",
]  # fmt: skip
ITEM_KEYS = [
    "item_id", "kind", "source", "link", "snapshot_id", "relevance", "date", "text", "reason",
    "possible_matches", "possible_matches_outside", "undated_id",
]  # fmt: skip
DOC_KEYS = [
    "schema_version", "content_id", "generated_at", "published_at", "data_as_of",
    "current_month", "window", "months", "undated", "attention_items", "attention_truncated",
    "source_health", "run", "errors",
]  # fmt: skip
RUN_KEYS = [
    "parser_version", "code_sha", "trust_sources", "merge_checks", "severity", "reasons",
]  # fmt: skip


@cache
def fixture_parts() -> FeedParts:
    r = first_run()
    return build_feed(
        r.merge,
        [r.sources[s] for s in reversed(SOURCE_ORDER)],  # the order given is not the order kept
        window=r.window,
        now=RUN_NOW,
        run=RunInfo("a" * 40, ("osce",)),
        run_reasons=(),
    )


def cards(parts: FeedParts) -> list[dict[str, Any]]:
    return [c for month in parts.doc["months"].values() for c in month]


def feed_children(parts: FeedParts) -> list[dict[str, Any]]:
    return [ch for c in cards(parts) for ch in c["children"]]


def synthetic(
    claims: Sequence[Any], now: datetime = NOW
) -> tuple[MergeResult, Window, FeedParts]:
    result = merge(claims, now=now, places=PlaceRegistry.load())
    window = window_for(now)
    parts = build_feed(result, [], window=window, now=now, run=RUN, run_reasons=())
    return result, window, parts


def with_items(source: SourceResult, items: Sequence[AttentionItem]) -> SourceResult:
    return dataclasses.replace(source, items=tuple(items))


def with_served(source: SourceResult, moment: datetime | None) -> SourceResult:
    health = dataclasses.replace(source.decision.health, served_fetched_at=moment)
    return dataclasses.replace(source, decision=dataclasses.replace(source.decision, health=health))


def test_feed_serialises_every_merge_record() -> None:
    r = first_run()
    parts = fixture_parts()
    doc = parts.doc
    assert list(doc) == DOC_KEYS
    assert doc["schema_version"] == 2
    assert doc["content_id"] is None
    assert doc["published_at"] is None
    assert doc["generated_at"] == "2026-10-19T12:00:00Z"
    assert doc["current_month"] == "2026-10"
    assert doc["window"] == {
        "months": ["2026-09", "2026-10", "2026-11", "2026-12", "2027-01"],
        "years": [2026, 2027],
    }
    assert list(doc["months"]) == ["2026-09", "2026-10", "2026-11", "2026-12", "2027-01"]
    assert [len(v) for v in doc["months"].values()] == [22, 30, 28, 15, 5]
    assert len(cards(parts)) == 100
    assert len(feed_children(parts)) == 202
    assert sum(len(ch["sources"]) for ch in feed_children(parts)) == 274
    assert len(doc["undated"]) == 31
    assert len(doc["attention_items"]) == 157
    assert doc["attention_truncated"] == 0
    assert [h["source"] for h in doc["source_health"]] == list(SOURCE_ORDER)
    assert doc["run"] == {
        "parser_version": "2.0",
        "code_sha": "a" * 40,
        "trust_sources": ["osce"],
        "merge_checks": {"conservation": "ok"},
        "severity": "warning",
        "reasons": [],
    }
    assert list(doc["run"]) == RUN_KEYS
    assert parts.severity == "warning"
    assert parts.run_reasons == ()

    full = parts.attention_full["items"]
    assert len(full) == 188
    assert [i["item_id"] for i in full] == sorted(i["item_id"] for i in full)
    assert sum(i["unit_id"] is None for i in full) == 67
    assert all(i["merge_ids"] for i in full if i["unit_id"] is None)
    assert sum(i["unit_id"] is not None for i in full) == 121
    assert all(i["merge_ids"] == [] for i in full if i["unit_id"] is not None)
    assert sum(i["unit_text"] is not None for i in full) > 0
    assert all("unit_text" not in i and "merge_ids" not in i for i in doc["attention_items"])
    assert len(parts.dispositions["dispositions"]) == 1335
    assert list(parts.dispositions["dispositions"][0]) == ["merge_id", "kind", "targets"]

    card = cards(parts)[0]
    child = card["children"][0]
    assert list(card) == CARD_KEYS
    assert list(child) == CHILD_KEYS
    assert list(child["sources"][0]) == CHILD_SOURCE_KEYS
    umbrella = next(u for c in cards(parts) for u in c["umbrellas"])
    assert list(umbrella) == UMBRELLA_KEYS
    assert list(doc["undated"][0]) == LISTING_KEYS
    assert list(doc["attention_items"][0]) == ITEM_KEYS
    assert list(full[0]) == [*ITEM_KEYS, "merge_ids", "unit_id", "unit_text"]
    assert [u["undated_id"] for u in doc["undated"]] == sorted(u["undated_id"] for u in doc["undated"])

    record = next(c for c in r.merge.cards if c.group_id == "54b356d5b5ea")
    assert (record.country, record.span.start) == ("Brazil", date(2026, 10, 4))
    got = next(c for c in cards(parts) if c["group_id"] == "54b356d5b5ea")
    assert got["date"] == "2026-10-04"
    assert got["end_date"] == record.span.end.isoformat()  # type: ignore[union-attr]
    assert got["date_precision"] == record.span.precision
    assert got["country"] == record.country
    assert got["type"] == record.type
    assert got["status"] == record.status
    assert got["date_meaning"] == record.date_meaning
    assert got["date_status"] == record.date_status
    assert got["level"] == record.level
    assert got["place_id"] == record.place_id
    assert got["country_code"] == record.country_code
    assert got["sources"] == [
        {"name": SOURCE_NAMES[b.source], "link": b.link} for b in record.sources
    ]
    assert got["source_names"] == [SOURCE_NAMES[b.source] for b in record.sources]
    assert got["links"] == [b.link for b in record.sources]
    assert got["umbrella_sources"] == [
        {"name": SOURCE_NAMES[b.source], "link": b.link} for b in record.umbrella_sources
    ]
    assert [c["child_id"] for c in got["children"]] == [c.child_id for c in record.children]
    for out, ch in zip(got["children"], record.children, strict=True):
        assert out["jurisdiction"] == ch.jurisdiction
        assert out["jurisdiction_kind"] == ch.jurisdiction_kind
        assert out["institution"] == ch.institution
        assert out["office_class"] == ch.office_class
        assert out["office_label"] == ch.office_label
        assert out["kind"] == ch.kind
        assert out["round"] == ch.round
        assert out["indirect"] == ch.indirect
        assert out["aggregate"] == ch.aggregate
        assert out["occurrence_confirmed"] == ch.occurrence_confirmed
        assert out["status_conflict"] == ch.status_conflict
        assert out["date_conflict"] == ch.date_conflict
        assert out["unverified"] == ch.unverified
        assert out["ambiguous"] == ch.ambiguous
        assert out["rescheduled_from"] == list(ch.rescheduled_from)
        assert out["provisional_date"] == ch.provisional_date
        assert "place_id" not in out and "country" not in out and "status" not in out
        for o, s in zip(out["sources"], ch.sources, strict=True):
            c = s.claim
            assert o == {
                "name": SOURCE_NAMES[c.source],
                "link": c.link,
                "source_event_id": c.source_event_id,
                "date": c.span.start.isoformat() if c.span.start else None,
                "end_date": c.span.end.isoformat() if c.span.end else None,
                "date_precision": c.span.precision,
                "date_text": c.date_text,
                "date_meaning": c.date_meaning,
                "date_status": c.date_status,
                "status_claim": c.status_claim,
                "fetched_at": _utc_iso(c.fetched_at),
                "fallback": c.fallback,
                "provisional": c.provisional,
                "evidence_kind": c.evidence_kind,
                "selected": s.selected,
                "rejected_reason": s.rejected_reason,
            }
    # A year-precision claim keeps its precision and has no dates.
    year_sources = [
        s for ch in feed_children(parts) for s in ch["sources"] if s["date_precision"] == "year"
    ]
    assert year_sources
    assert all(s["date"] is None and s["end_date"] is None for s in year_sources)
    # The statuses the sources claim reach the feed.
    assert {s["status_claim"] for ch in feed_children(parts) for s in ch["sources"]} - {None}


def test_possible_matches_never_dangle() -> None:
    r = first_run()
    parts = fixture_parts()
    ids = {ch["child_id"] for ch in feed_children(parts)}
    listings = {u["undated_id"] for u in parts.doc["undated"]}
    assert all(m in ids for ch in feed_children(parts) for m in ch["possible_matches"])
    assert all(m in ids for u in parts.doc["undated"] for m in u["possible_matches"])
    items = parts.doc["attention_items"]
    assert all(m in ids for i in items for m in i["possible_matches"])
    assert all(i["undated_id"] in listings for i in items if i["undated_id"] is not None)

    merge_items = [i for i in items if i["item_id"] in {a.item_id for a in r.merge.attention}]
    assert len(merge_items) == 36
    assert sum(len(i["possible_matches"]) for i in merge_items) == 1
    assert sum(i["possible_matches_outside"] for i in merge_items) == 15
    full = {i["item_id"]: i for i in parts.attention_full["items"]}
    shut_out = [i for i in merge_items if i["possible_matches"] == [] and i["possible_matches_outside"]]
    assert len(shut_out) == 4
    for i in shut_out:
        assert i["kind"] == "unresolved_evidence"
        assert i["reason"] == full[i["item_id"]]["reason"]
        assert full[i["item_id"]]["possible_matches"]

    original = {a.item_id: a for a in [*r.merge.attention, *(x for s in r.sources.values() for x in s.items)]}
    for i in items:
        assert len(i["possible_matches"]) + i["possible_matches_outside"] == len(
            set(original[i["item_id"]].possible_matches)
        )
        assert full[i["item_id"]]["possible_matches"] == list(original[i["item_id"]].possible_matches)
        assert full[i["item_id"]]["possible_matches_outside"] == i["possible_matches_outside"]

    # The same rules for children: with today in mid-September, 1 December is in the window and
    # its partner, 1 January, is not.
    sept = datetime(2026, 9, 15, 12, tzinfo=UTC)
    narrow = build_feed(r.merge, [], window=window_for(sept), now=sept, run=RUN, run_reasons=())
    inside = {ch["child_id"] for ch in feed_children(narrow)}
    by_id = {ch.child_id: ch for c in r.merge.cards for ch in c.children}
    assert "00d51e66e43c" in inside
    assert "1e0beadfb091" not in inside
    got = next(ch for ch in feed_children(narrow) if ch["child_id"] == "00d51e66e43c")
    assert got["possible_matches"] == []
    assert got["possible_matches_outside"] == 1
    for ch in feed_children(narrow):
        assert all(m in inside for m in ch["possible_matches"])
        assert len(ch["possible_matches"]) + ch["possible_matches_outside"] == len(
            by_id[ch["child_id"]].possible_matches
        )

    # And for listings: one listing is given a match inside the feed and one outside it.
    in_feed = sorted(ch["child_id"] for ch in feed_children(parts))
    out_of_feed = sorted(set(by_id) - set(in_feed))
    wanted = sorted({in_feed[0], out_of_feed[0], out_of_feed[1]})
    shown = parts.doc["undated"][0]["undated_id"]
    swapped = tuple(
        dataclasses.replace(u, possible_matches=tuple(wanted)) if u.undated_id == shown else u
        for u in r.merge.undated
    )
    merged = dataclasses.replace(r.merge, undated=swapped)
    probe = build_feed(merged, list(r.sources.values()), window=r.window, now=RUN_NOW, run=RUN, run_reasons=())
    got_listing = next(u for u in probe.doc["undated"] if u["undated_id"] == shown)
    assert got_listing["possible_matches"] == [in_feed[0]]
    assert got_listing["possible_matches_outside"] == 2


def test_attention_cap_sets_attention_truncated() -> None:
    base = first_run().sources["ipu"]
    dated = [
        dataclasses.replace(
            item("partial_unit", "ipu", f"dated {n}"),
            date=date(2026, 11, 1) + timedelta(days=(n * 7) % 300),
        )
        for n in range(300)
    ]
    undated = [item("unparsed_unit", "ipu", f"undated {n}") for n in range(100)]
    unknown = [
        dataclasses.replace(item("unparsed_unit", "ipu", f"unknown {n}"), relevance="unknown")
        for n in range(101)
    ]
    # Two unknown items carry early dates: relevance still comes before the date.
    unknown[0] = dataclasses.replace(unknown[0], date=date(2026, 1, 1))
    unknown[1] = dataclasses.replace(unknown[1], date=date(2026, 1, 2))
    everything = [*unknown, *undated, *dated]
    src = with_items(base, everything)
    parts = build_feed(
        EMPTY, [src], window=window_for(RUN_NOW), now=RUN_NOW, run=RUN, run_reasons=()
    )

    def rank(i: AttentionItem) -> tuple[int, bool, date, str]:
        return (i.relevance == "unknown", i.date is None, i.date or date.min, i.item_id)

    expected = sorted(everything, key=rank)[:MAX_FEED_ITEMS]
    assert MAX_FEED_ITEMS == 500
    assert [i["item_id"] for i in parts.doc["attention_items"]] == [i.item_id for i in expected]
    shown = parts.doc["attention_items"]
    assert [i["relevance"] for i in shown[:400]] == ["in_or_after_window"] * 400
    assert [i["date"] for i in shown[:300]] == sorted(i["date"] for i in shown[:300])
    assert all(i["date"] is None for i in shown[300:400])
    assert [i["item_id"] for i in shown[300:400]] == sorted(i["item_id"] for i in shown[300:400])
    assert [i["relevance"] for i in shown[400:]] == ["unknown"] * 100
    assert shown[400]["date"] == "2026-01-01"
    assert parts.doc["attention_truncated"] == 1
    reason = parts.run_reasons[-1]
    assert reason == Reason("attention_truncated", "attention items left out of the feed: 1")
    assert parts.doc["run"]["reasons"][-1]["code"] == "attention_truncated"
    assert parts.doc["run"]["reasons"][-1]["level"] == "warning"
    assert parts.doc["run"]["reasons"][-1]["text"] == "attention items left out of the feed: 1"
    assert parts.doc["errors"][-1] == "Run: attention_truncated: attention items left out of the feed: 1"
    assert parts.severity == "warning"
    assert parts.doc["run"]["severity"] == "warning"
    assert len(parts.attention_full["items"]) == 501

    # The given run reasons come first.
    given = Reason("ack_invalid", "x")
    again = build_feed(
        EMPTY, [src], window=window_for(RUN_NOW), now=RUN_NOW, run=RUN, run_reasons=(given,)
    )
    assert again.run_reasons[0] == given
    assert again.run_reasons[-1].code == "attention_truncated"

    # An undated listing whose item is cut is not in the feed.
    r = first_run()
    flood = [
        dataclasses.replace(
            item("partial_unit", "eeas", f"early {n}"), date=date(2026, 1, 1) + timedelta(days=n)
        )
        for n in range(400)
    ]
    sources = [with_items(s, [*s.items, *flood]) if s.source == "eeas" else s for s in r.sources.values()]
    cut = build_feed(r.merge, sources, window=r.window, now=RUN_NOW, run=RUN, run_reasons=())
    assert cut.doc["attention_truncated"] == 57
    kept = {i["undated_id"] for i in cut.doc["attention_items"] if i["undated_id"] is not None}
    assert {u["undated_id"] for u in cut.doc["undated"]} == kept
    assert 0 < len(kept) < 31
    assert len(cut.attention_full["items"]) == 188 + 400


def test_unit_and_claim_attention_items_share_one_list() -> None:
    items = fixture_parts().doc["attention_items"]
    ids = [i["item_id"] for i in items]
    assert len(set(ids)) == len(ids) == 157
    merge_ids = {a.item_id for a in first_run().merge.attention}
    assert {i["item_id"] in merge_ids for i in items} == {True, False}

    def key(i: dict[str, Any]) -> tuple[int, bool, str, str]:
        return (i["relevance"] == "unknown", i["date"] is None, i["date"] or "", i["item_id"])

    assert items == sorted(items, key=key)
    assert items[0]["relevance"] == "in_or_after_window"
    assert [i["relevance"] for i in items[-31:]] == ["unknown"] * 31
    assert all(i["relevance"] == "in_or_after_window" for i in items[:-31])
    assert all(i["relevance"] != "before_window" for i in items)


def test_feed_serialises_rescheduling_and_provisional_date() -> None:
    _, _, moved = synthetic(
        [cl(f"{EGU}/r1"), cl("osce:elections/r1", provisional=True, span=day(2026, 12, 6))]
    )
    (card,) = cards(moved)
    (child,) = card["children"]
    assert child["provisional_date"] == "moved"
    assert child["date_conflict"] is True
    by_name = {s["name"]: s for s in child["sources"]}
    assert by_name["OSCE/ODIHR"]["provisional"] is True
    assert by_name["OSCE/ODIHR"]["selected"] is False
    assert by_name["OSCE/ODIHR"]["rejected_reason"] == "provisional"
    assert by_name["OSCE/ODIHR"]["date"] == "2026-12-06"
    assert by_name["ElectionGuide"]["selected"] is True

    _, _, late = synthetic(
        [cl("eisa:y2026/r3", status_claim="postponed", previous_date_text="1 November 2026")]
    )
    (card,) = cards(late)
    assert card["status"] == "Upcoming"
    assert card["children"][0]["rescheduled_from"] == ["1 November 2026"]
    assert card["children"][0]["sources"][0]["status_claim"] == "postponed"
    assert card["children"][0]["sources"][0]["name"] == "EISA"


def test_umbrella_link_targets_children_in_the_feed() -> None:
    r = first_run()
    parts = fixture_parts()
    umbrellas = [(c, u) for c in cards(parts) for u in c["umbrellas"]]
    assert len(umbrellas) == 16
    for c, u in umbrellas:
        assert u["children"]
        assert set(u["children"]) <= {ch["child_id"] for ch in c["children"]}
        assert u["children"] == sorted(u["children"])
    ss = next(c for c in cards(parts) if c["group_id"] == "811a20289c2a")
    assert (ss["country"], ss["date"]) == ("South Sudan", "2026-12-22")
    assert len(ss["children"]) == 3
    by_name = {u["name"]: u for u in ss["umbrellas"]}
    assert by_name["EISA"]["children"] == ["31ce89602954", "6f60dcabc9d2"]
    assert len(by_name["NDI"]["children"]) == 3
    assert len(by_name["A-WEB"]["children"]) == 3
    # An umbrella lists only the children of its own card, whatever its disposition names.
    foreign = next(
        ch["child_id"] for c in cards(parts) if c["group_id"] != "811a20289c2a" for ch in c["children"]
    )
    eisa_claim = next(
        u for c in r.merge.cards if c.group_id == "811a20289c2a" for u in c.umbrellas if u.source == "eisa"
    )
    widened = tuple(
        dataclasses.replace(d, targets=tuple(sorted({*d.targets, foreign})))
        if d.merge_id == eisa_claim.merge_id and d.kind == "umbrella_link"
        else d
        for d in r.merge.dispositions
    )
    other = build_feed(
        dataclasses.replace(r.merge, dispositions=widened),
        [], window=r.window, now=RUN_NOW, run=RUN, run_reasons=(),
    )  # fmt: skip
    ss_other = next(c for c in cards(other) if c["group_id"] == "811a20289c2a")
    eisa_other = next(u for u in ss_other["umbrellas"] if u["name"] == "EISA")
    assert eisa_other["children"] == ["31ce89602954", "6f60dcabc9d2"]
    record = next(c for c in r.merge.cards if c.group_id == "811a20289c2a")
    eisa = next(u for u in record.umbrellas if u.source == "eisa")
    assert (by_name["EISA"]["link"], by_name["EISA"]["office_label"], by_name["EISA"]["date_text"]) == (
        eisa.link, eisa.office_label, eisa.date_text,
    )  # fmt: skip


def test_unknown_meaning_observation_never_makes_held_or_ongoing() -> None:
    wp = cl(f"{WPn}/November/li[1]", GD)
    ee = cl("eeas:missions/r1c1", GD, OBS, span=year(2026), status_claim="held")
    _, _, both = synthetic([wp, ee])
    (card,) = cards(both)
    assert card["date"] == "2026-11-05"
    assert card["status"] == "Upcoming"
    (child,) = card["children"]
    seen = {s["name"]: s for s in child["sources"]}
    assert seen["EEAS"]["selected"] is False
    assert seen["EEAS"]["rejected_reason"] == "observation"
    assert seen["EEAS"]["evidence_kind"] == "observation"
    assert seen["EEAS"]["status_claim"] == "held"
    assert seen["EEAS"]["date"] is None
    assert seen["Wikipedia"]["selected"] is True

    _, _, alone = synthetic([ee])
    assert cards(alone) == []
    (only,) = alone.attention_full["items"]
    assert only["kind"] == "unresolved_evidence"
    assert only["reason"] == "no_candidate"
    assert [i["kind"] for i in alone.doc["attention_items"]] == ["unresolved_evidence"]

    selected = [s for ch in feed_children(fixture_parts()) for s in ch["sources"] if s["selected"]]
    assert selected
    assert not [s for s in selected if s["evidence_kind"] == "observation"]


def test_data_as_of_is_the_oldest_served_fetch() -> None:
    r = first_run()
    assert fixture_parts().doc["data_as_of"] == "2026-10-16T14:39:00Z"
    t0 = datetime(2026, 10, 10, 8, tzinfo=UTC)
    t1 = datetime(2026, 10, 18, 8, tzinfo=UTC)
    t2 = datetime(2026, 10, 19, 8, tzinfo=UTC)
    served: dict[str, datetime | None] = {s: t2 for s in SOURCE_ORDER}
    served["osce"] = t1
    served["ipu"] = t0  # a fallback, served from an old fetch
    served["eeas"] = None  # unavailable
    sources = [with_served(r.sources[s], served[s]) for s in SOURCE_ORDER]
    sources[SOURCE_ORDER.index("ipu")] = dataclasses.replace(
        sources[SOURCE_ORDER.index("ipu")],
        decision=dataclasses.replace(
            sources[SOURCE_ORDER.index("ipu")].decision,
            health=dataclasses.replace(
                sources[SOURCE_ORDER.index("ipu")].decision.health, using_fallback=True
            ),
        ),
    )
    got = build_feed(EMPTY, sources, window=r.window, now=RUN_NOW, run=RUN, run_reasons=())
    assert got.doc["data_as_of"] == _utc_iso(t0)
    none = [with_served(r.sources[s], None) for s in SOURCE_ORDER]
    assert (
        build_feed(EMPTY, none, window=r.window, now=RUN_NOW, run=RUN, run_reasons=()).doc[
            "data_as_of"
        ]
        is None
    )


def test_errors_lines() -> None:
    r = first_run()
    reasons: dict[str, tuple[Reason, ...]] = {s: () for s in SOURCE_ORDER}
    reasons["ipu"] = (Reason("http_error", "elections"), Reason("count_change", "ignored"))
    reasons["eisa"] = (Reason("unparsed_relevant"),)
    sources = [
        dataclasses.replace(r.sources[s], reasons=reasons[s], severity="ok") for s in SOURCE_ORDER
    ]
    sources[SOURCE_ORDER.index("ipu")] = dataclasses.replace(
        sources[SOURCE_ORDER.index("ipu")], severity="error"
    )
    run_reasons = (Reason("ack_invalid", "known_issues.yml: tab"), Reason("provisional_changes", "x"))
    parts = build_feed(
        EMPTY, sources, window=r.window, now=RUN_NOW, run=RUN, run_reasons=run_reasons
    )
    assert parts.doc["errors"] == [
        "EISA: unparsed_relevant",
        "IPU: http_error: elections",
        "Run: ack_invalid: known_issues.yml: tab",
    ]
    assert parts.severity == "error"  # the worst of the sources
    clean = [dataclasses.replace(s, reasons=(), severity="ok") for s in sources]
    only_run = build_feed(
        EMPTY, clean, window=r.window, now=RUN_NOW, run=RUN, run_reasons=run_reasons
    )
    assert only_run.severity == "warning"  # the run's own reasons count
    assert only_run.doc["run"]["severity"] == "warning"
    assert [x["code"] for x in only_run.doc["run"]["reasons"]] == ["ack_invalid", "provisional_changes"]
    quiet = build_feed(EMPTY, clean, window=r.window, now=RUN_NOW, run=RUN, run_reasons=())
    assert quiet.doc["errors"] == []
    assert quiet.severity == "ok"


def test_orphan_unit_items_with_an_empty_link_are_copied() -> None:
    r = first_run()
    orphan = dataclasses.replace(item("unparsed_unit", "ipu", "orphan"), link="")
    parts = build_feed(
        EMPTY,
        [with_items(r.sources["ipu"], [orphan])],
        window=r.window,
        now=RUN_NOW,
        run=RUN,
        run_reasons=(),
    )
    assert [i["link"] for i in parts.doc["attention_items"]] == [""]
