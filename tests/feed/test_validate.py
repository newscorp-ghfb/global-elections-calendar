"""The feed schema and the checks of spec §11.3 (S4-T06, Review Focus 5)."""

import copy
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from functools import cache
from pathlib import Path
from typing import Any, get_args

import pytest
from jsonschema import Draft202012Validator

from elections_calendar import feed as feed_module
from elections_calendar import health, model, validate
from elections_calendar.feed import (
    MAX_FEED_ITEMS,
    DownloadOutcome,
    RunInfo,
    SourceResult,
    build_feed,
)
from elections_calendar.health import HealthState, match_diagnostic, severity, source_reasons
from elections_calendar.merge import merge
from elections_calendar.model import SOURCE_ORDER
from elections_calendar.places import PlaceRegistry
from elections_calendar.publish import feed_bytes
from elections_calendar.runner import SourceRun
from elections_calendar.snapshots import decide, unit_items
from elections_calendar.sources.base import PARSER_VERSION
from elections_calendar.validate import (
    FEED_MAX_BYTES,
    FEED_SCHEMA,
    MAX_AHEAD,
    STATUS_SCHEMA,
    ServedCheck,
    validate_feed,
)
from tests.support.feed import FIXTURE_FETCHED, RUN_NOW, first_run, fixture_feed, fixture_snapshot
from tests.support.snapshots import SynthPage, promoted, report, synth

V1_FEED = Path(__file__).parent.parent / "fixtures" / "feed" / "2026-10-16-ff30417.json"
WALL = RUN_NOW


def feed_doc() -> dict[str, Any]:
    out: dict[str, Any] = json.loads(fixture_feed()[1])
    return out


def dump(doc: Any) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def served_for(doc: dict[str, Any]) -> list[ServedCheck]:
    return [
        ServedCheck(e["source"], e["snapshot"]["served_snapshot_id"], True, True)
        for e in doc["source_health"]
    ]


def check(doc: Any, *, served: list[ServedCheck] | None = None, wall: datetime = WALL) -> tuple[str, ...]:
    given = served_for(doc) if served is None else served
    return validate_feed(dump(doc), served=given, wall_clock=wall)


def prefixes(problems: tuple[str, ...]) -> set[str]:
    return {p.split(":")[0] for p in problems}


def children(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for cards in doc["months"].values() for card in cards for c in card["children"]]


def cards(doc: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [(m, c) for m, items in doc["months"].items() for c in items]


@cache
def fallback_feed() -> tuple[dict[str, Any], dict[str, str]]:
    """Every source failed (all pages http_error) and serves its baseline, stamped ``fallback``."""
    run = first_run()
    decided = {}
    versions = {}
    for source in SOURCE_ORDER:
        _, _, snapshot, _ = fixture_snapshot(source)
        version = "1.9" if source == "osce" else PARSER_VERSION
        versions[source] = version
        candidate = synth(
            source,
            tuple(
                SynthPage(p.key, outcome="http_error", year=p.year, scope=p.scope or None)
                for p in snapshot.pages
            ),
            fetched_at=FIXTURE_FETCHED[source] + timedelta(days=1),
            parser_version=version,
            registry=snapshot.registry_version,
        )
        decided[source] = decide(
            candidate,
            run_outcome="complete",
            run_detail="",
            ledger=report(candidate),
            baseline=promoted(snapshot),
            baseline_problem=None,
            acceptances=(),
            window=run.window,
            now=RUN_NOW,
        )
        assert decided[source].acceptance == "fallback", source
    claims = tuple(c for s in SOURCE_ORDER for c in decided[s].claims)
    merged = merge(claims, now=RUN_NOW, places=PlaceRegistry.load())
    fresh = frozenset(s for s, d in decided.items() if d.acceptance == "promoted")
    results = []
    for source in SOURCE_ORDER:
        decision = decided[source]
        items = unit_items(decision)
        match = match_diagnostic(merged, claims, source, fresh=fresh, window=run.window)
        reasons = source_reasons(decision.reasons, items, match, HealthState(()))
        results.append(
            SourceResult(
                source=source,
                run=SourceRun(source, fixture_snapshot(source)[0], "complete", 0),
                parse_ms=0,
                ledger=report(decision.candidate),
                decision=decision,
                items=items,
                match=match,
                reasons=reasons,
                acknowledged=(),
                severity=severity(reasons),
            )
        )
    parts = build_feed(
        merged, results, window=run.window, now=RUN_NOW, run=RunInfo("local", ()), run_reasons=()
    )
    return json.loads(feed_bytes(parts.doc, published_at=RUN_NOW)), versions


def test_feed_schema() -> None:
    doc = feed_doc()
    assert check(doc) == ()
    assert validate_feed(fixture_feed()[1], served=served_for(doc), wall_clock=WALL) == ()

    fallback, versions = fallback_feed()
    assert check(fallback) == ()
    assert [e["snapshot"]["using_fallback"] for e in fallback["source_health"]] == [True] * 9
    assert [e["snapshot"]["acceptance"] for e in fallback["source_health"]] == ["fallback"] * 9
    sources = [s for ch in children(fallback) for s in ch["sources"]]
    assert sources and all(s["fallback"] is True for s in sources)
    assert fallback["run"]["parser_version"] == PARSER_VERSION
    assert {e["source"]: e["parse"]["parser_version"] for e in fallback["source_health"]} == versions
    assert versions["osce"] != PARSER_VERSION
    assert doc["run"]["parser_version"] == PARSER_VERSION == "2.0"

    schema = json.loads(FEED_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)

    bad = copy.deepcopy(doc)
    child = children(bad)[0]
    child["sources"][0]["extra"] = 1
    problems = check(bad)
    assert any(p.startswith("schema: ") and "extra" in p for p in problems), problems

    bad = copy.deepcopy(doc)
    del children(bad)[0]["round"]
    assert any(p.startswith("schema: ") and "round" in p for p in check(bad))

    bad = copy.deepcopy(doc)
    cards(bad)[0][1]["status"] = "Ongoing"
    problems = check(bad)
    assert any(p.startswith("schema: ") and "Ongoing" in p for p in problems), problems


def test_the_schema_accepts_what_the_records_allow() -> None:
    """Nullable fields follow the record types, not the fixture's narrower values."""
    doc = feed_doc()
    child = next(c for c in children(doc) if len(c["sources"]) >= 1)
    child["round"] = 2
    child["sources"][0]["date"] = None
    child["sources"][0]["end_date"] = None
    child["sources"][0]["date_precision"] = "year"
    child["sources"][0]["fetched_at"] = None
    child["sources"][0]["source_event_id"] = None
    doc["attention_items"][0]["link"] = ""
    doc["attention_items"][0]["snapshot_id"] = None
    doc["data_as_of"] = None
    first = doc["source_health"][0]
    first["snapshot"].update(
        acceptance="unavailable", served_snapshot_id=None, served_fetched_at=None,
        using_fallback=False, baseline_units_seen=None,
    )  # fmt: skip
    first["download"].update(http_status=None, final_url=None, content_type=None, error=None)
    served = served_for(doc)
    served[0] = ServedCheck(first["source"], None, True, True)
    assert check(doc, served=served) == ()


def test_schema_enums_equal_the_literals() -> None:
    feed_defs = json.loads(FEED_SCHEMA.read_text(encoding="utf-8"))["$defs"]
    status_defs = json.loads(STATUS_SCHEMA.read_text(encoding="utf-8"))["$defs"]
    literals = {
        "Kind": model.Kind, "OfficeClass": model.OfficeClass, "Level": model.Level,
        "JurisdictionKind": model.JurisdictionKind, "Precision": model.Precision,
        "DateMeaning": model.DateMeaning, "DateStatus": model.DateStatus,
        "StatusClaim": model.StatusClaim, "LegacyStatus": model.LegacyStatus,
        "EvidenceKind": model.EvidenceKind, "RejectedReason": model.RejectedReason,
        "ProvisionalDate": model.ProvisionalDate, "AttentionKind": model.AttentionKind,
        "Relevance": model.Relevance, "Acceptance": model.Acceptance,
        "DownloadOutcome": DownloadOutcome, "Severity": health.Severity,
        "ReasonCode": model.ReasonCode, "ReasonLevel": model.ReasonLevel, "Stage": model.Stage,
    }  # fmt: skip
    assert len(literals) == 20
    for name, literal in literals.items():
        values = list(get_args(literal))
        assert values and len(set(values)) == len(values)
        assert sorted(feed_defs[name]["enum"]) == sorted(values), name
        if name in status_defs:
            assert sorted(status_defs[name]["enum"]) == sorted(values), name
    assert sorted(feed_defs["sourceHealth"]["properties"]["source"]["enum"]) == sorted(SOURCE_ORDER)
    assert status_defs["Outcome"]["enum"] == [
        "published", "validation_failed", "superseded", "paused", "republished",
    ]  # fmt: skip
    status = json.loads(STATUS_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(status)


# Written only by a republication (Plan 5a Task 8, P122); every other property is required.
OPTIONAL_PROPERTIES = {"republished_from_sha256"}


def test_every_schema_object_is_closed_and_complete() -> None:
    for path in (FEED_SCHEMA, STATUS_SCHEMA):
        schema = json.loads(path.read_text(encoding="utf-8"))
        seen = 0

        def walk(node: Any) -> None:
            nonlocal seen
            if isinstance(node, dict):
                if node.get("type") == "object" and "properties" in node:
                    seen += 1
                    assert node["additionalProperties"] is False
                    assert set(node["required"]) <= set(node["properties"])
                    assert set(node["properties"]) - set(node["required"]) <= OPTIONAL_PROPERTIES
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)

        walk(schema)
        assert seen >= (10 if path == FEED_SCHEMA else 3)
        optional = set(schema["properties"]) - set(schema["required"])
        assert optional == (OPTIONAL_PROPERTIES if path == FEED_SCHEMA else set())


def test_v1_feed_is_not_a_v2_feed() -> None:
    problems = validate_feed(V1_FEED.read_bytes(), served=[], wall_clock=WALL)
    assert problems and "schema" in prefixes(problems)
    assert all(p.split(":")[0] in {"schema", "legacy", "invariant", "served", "timestamp"} for p in problems)


@pytest.mark.parametrize(
    "data", [b"{}", b"[]", b"null", b"3", b'"x"', b'{"months": []}', b'{"months": {"2026-10": 5}}',
             b'{"months": {"2026-10": [3, {"children": 4, "sources": 5, "umbrellas": [6]}]}}',
             b'{"attention_items": [1, {"item_id": 2}], "undated": "x", "source_health": [7]}'],
)  # fmt: skip
def test_odd_shapes_give_problems_and_never_crash(data: bytes) -> None:
    problems = validate_feed(data, served=[], wall_clock=WALL)
    assert problems and "schema" in prefixes(problems)


def test_non_json_stops_at_the_json_check() -> None:
    for data in (b"nope", b"\xff\xfe\x00", b"", b'{"a": 1,}', b"\xef\xbb\xbf{}"):
        assert validate_feed(data, served=[], wall_clock=WALL) == ("json: not UTF-8 JSON",), data


def test_validate_is_unchanged_clean() -> None:
    assert check(feed_doc()) == ()


def corrupt_date(doc: dict[str, Any]) -> None:
    cards(doc)[0][1]["date"] = "2026-10"


def corrupt_names(doc: dict[str, Any]) -> None:
    cards(doc)[0][1]["source_names"] = ["Nobody"]


def corrupt_links(doc: dict[str, Any]) -> None:
    cards(doc)[1][1]["links"] = []


def corrupt_country(doc: dict[str, Any]) -> None:
    cards(doc)[2][1]["country"] = ""


def corrupt_status(doc: dict[str, Any]) -> None:
    cards(doc)[3][1]["status"] = "Ongoing"


def corrupt_status_unhashable(doc: dict[str, Any]) -> None:
    cards(doc)[3][1]["status"] = []


def corrupt_bib(doc: dict[str, Any]) -> None:
    cards(doc)[4][1]["sources"][0]["link"] = 7


def corrupt_impossible_date(doc: dict[str, Any]) -> None:
    cards(doc)[5][1]["date"] = "2026-13-45"


LEGACY_ROWS = [
    ("date", corrupt_date, 0, "is not YYYY-MM-DD"),
    ("source_names", corrupt_names, 0, "source_names differ"),
    ("links", corrupt_links, 1, "links differ"),
    ("country", corrupt_country, 2, "country is empty"),
    ("status", corrupt_status, 3, "is not a legacy value"),
    ("status list", corrupt_status_unhashable, 3, "is not a legacy value"),
    ("sources", corrupt_bib, 4, "sources is not a list of name and link strings"),
    ("impossible date", corrupt_impossible_date, 5, "is not YYYY-MM-DD"),
]


@pytest.mark.parametrize(
    ("label", "change", "index", "said"), LEGACY_ROWS, ids=[r[0] for r in LEGACY_ROWS]
)
def test_validate_legacy_contract(label: str, change: Any, index: int, said: str) -> None:
    doc = feed_doc()
    group = cards(doc)[index][1]["group_id"]
    change(doc)
    problems = check(doc)
    legacy = [p for p in problems if p.startswith("legacy: ")]
    assert legacy, (label, problems)
    assert any(said in p for p in legacy), (said, legacy)
    assert all(p.startswith(f"legacy: {group}: ") for p in legacy), legacy
    # the other cards are untouched
    assert len(legacy) == 1 or label in ("status", "status list", "sources")


def test_validate_source_names_out_of_step_is_only_a_legacy_problem() -> None:
    doc = feed_doc()
    corrupt_names(doc)
    assert prefixes(check(doc)) == {"legacy"}


def test_validate_invariants() -> None:
    base = feed_doc()
    kids = children(base)
    kid_a, kid_b = kids[0], next(k for k in kids if k["child_id"] != kids[0]["child_id"])
    one, two = cards(base)[0][1], cards(base)[1][1]

    def repeat_child(doc: dict[str, Any]) -> None:
        children(doc)[1]["child_id"] = children(doc)[0]["child_id"]

    def repeat_group(doc: dict[str, Any]) -> None:
        cards(doc)[1][1]["group_id"] = cards(doc)[0][1]["group_id"]

    def repeat_undated(doc: dict[str, Any]) -> None:
        doc["undated"][1]["undated_id"] = doc["undated"][0]["undated_id"]

    def repeat_item(doc: dict[str, Any]) -> None:
        doc["attention_items"][1]["item_id"] = doc["attention_items"][0]["item_id"]

    def dangling_child_match(doc: dict[str, Any]) -> None:
        children(doc)[0]["possible_matches"] = ["f" * 12]

    def dangling_item_match(doc: dict[str, Any]) -> None:
        doc["attention_items"][0]["possible_matches"] = ["e" * 12]

    def dangling_listing_match(doc: dict[str, Any]) -> None:
        doc["undated"][0]["possible_matches"] = ["d" * 12]

    def lost_listing(doc: dict[str, Any]) -> None:
        doc["attention_items"][0]["undated_id"] = "c" * 12

    def orphan_listing(doc: dict[str, Any]) -> None:
        for item in doc["attention_items"]:
            item["undated_id"] = None

    def foreign_umbrella_child(doc: dict[str, Any]) -> None:
        mine = cards(doc)[0][1]
        other = cards(doc)[1][1]["children"][0]["child_id"]
        mine["umbrellas"].append(
            {"name": "x", "link": "", "office_label": "", "date_text": "", "children": [other]}
        )

    def two_selected(doc: dict[str, Any]) -> None:
        child = next(c for c in children(doc) if len(c["sources"]) >= 2)
        for source in child["sources"]:
            source["selected"] = True

    def none_selected(doc: dict[str, Any]) -> None:
        for source in children(doc)[0]["sources"]:
            source["selected"] = False

    def wrong_month(doc: dict[str, Any]) -> None:
        month, card = cards(doc)[0]
        other = next(m for m in doc["months"] if m != month)
        doc["months"][month].remove(card)
        doc["months"][other].append(card)

    def too_many_items(doc: dict[str, Any]) -> None:
        template = doc["attention_items"][0]
        doc["attention_items"] = [
            {**template, "item_id": f"{n:012x}", "undated_id": None, "kind": "unresolved_evidence"}
            for n in range(501)
        ]

    def outside_window(doc: dict[str, Any]) -> None:
        card = cards(doc)[0][1]
        card["date"] = card["end_date"] = "2031-01-01"

    rows = [
        (repeat_child, "child_id"), (repeat_group, "group_id"), (repeat_undated, "undated_id"),
        (repeat_item, "item_id"), (dangling_child_match, "possible_matches"),
        (dangling_item_match, "possible_matches"), (dangling_listing_match, "possible_matches"),
        (lost_listing, "undated_id"), (orphan_listing, "no attention item"),
        (foreign_umbrella_child, "umbrella"),
        (two_selected, "selected"), (none_selected, "selected"), (wrong_month, "month"),
        (too_many_items, "500"), (outside_window, "month"),
    ]  # fmt: skip
    assert kid_a["child_id"] != kid_b["child_id"] and one is not two
    for change, word in rows:
        doc = copy.deepcopy(base)
        change(doc)
        found = [p for p in check(doc) if p.startswith("invariant: ")]
        assert found, change.__name__
        assert any(word in p for p in found), (change.__name__, found)
    # a repeated id names the repeat
    doc = copy.deepcopy(base)
    repeat_child(doc)
    named = children(doc)[0]["child_id"]
    assert any(named in p for p in check(doc) if p.startswith("invariant: "))


def test_max_items_constant_matches_the_feed() -> None:
    assert validate.MAX_ATTENTION_ITEMS == MAX_FEED_ITEMS == 500
    schema = json.loads(FEED_SCHEMA.read_text(encoding="utf-8"))
    assert schema["properties"]["attention_items"]["maxItems"] == MAX_FEED_ITEMS
    assert feed_module.MAX_FEED_ITEMS == validate.MAX_ATTENTION_ITEMS


def test_a_truncated_feed_of_500_items_is_valid() -> None:
    doc = feed_doc()
    template = doc["attention_items"][0]
    doc["attention_items"] = [
        {**template, "item_id": f"{n:012x}", "undated_id": None, "kind": "unresolved_evidence"}
        for n in range(500)
    ]
    doc["attention_truncated"] = 3
    doc["undated"] = []  # the feed keeps a listing only for an item that links it
    assert check(doc) == ()
    doc["attention_items"].append({**template, "item_id": "a" * 12, "undated_id": None})
    problems = check(doc)
    assert {"schema", "invariant"} <= prefixes(problems)


def test_validate_size() -> None:
    doc = feed_doc()
    data = dump(doc)
    served = served_for(doc)
    exact = data + b" " * (FEED_MAX_BYTES - len(data))
    assert len(exact) == FEED_MAX_BYTES == 2_000_000
    assert validate_feed(exact, served=served, wall_clock=WALL) == ()
    over = exact + b" "
    assert validate_feed(over, served=served, wall_clock=WALL) == (
        "size: 2000001 bytes is over 2000000",
    )


def test_validate_timestamps_and_served() -> None:
    doc = feed_doc()
    late = WALL - timedelta(minutes=11)  # published_at is 11 minutes ahead of this clock
    problems = check(doc, wall=late)
    stamped = [p for p in problems if p.startswith("timestamp: ")]
    assert len(stamped) == 2
    assert stamped[1] == (
        "timestamp: published_at is 2026-10-19T12:00:00Z, "
        "more than 10 minutes ahead of 2026-10-19T11:49:00Z"
    )
    assert prefixes(problems) == {"timestamp"}

    served = served_for(doc)
    wrong = [ServedCheck(served[0].source, "0" * 64, True, True), *served[1:]]
    found = check(doc, served=wrong)
    assert len(found) == 1 and found[0].startswith(f"served: {served[0].source}: ")

    for field in ("ledger_ok", "discovery_ok"):
        bad = [ServedCheck(served[1].source, served[1].snapshot_id, **{
            "ledger_ok": field != "ledger_ok", "discovery_ok": field != "discovery_ok"})]
        found = check(doc, served=[served[0], *bad, *served[2:]])
        assert len(found) == 1 and found[0].startswith(f"served: {served[1].source}: "), found
        assert field.split("_")[0] in found[0]

    missing = check(doc, served=served[1:])
    assert len(missing) == 1 and missing[0].startswith(f"served: {served[0].source}: ")
    stray = check(doc, served=[*served, ServedCheck("nowhere", None, True, True)])
    assert len(stray) == 1 and stray[0].startswith("served: nowhere: ")


def test_an_unavailable_source_is_served_nothing() -> None:
    doc = feed_doc()
    entry = doc["source_health"][2]
    entry["snapshot"].update(
        acceptance="unavailable", using_fallback=False, served_snapshot_id=None,
        served_fetched_at=None,
    )  # fmt: skip
    served = served_for(doc)
    assert served[2].snapshot_id is None
    assert check(doc, served=served) == ()
    # the same entry against a served snapshot is a mismatch (the check compares null with None)
    served[2] = ServedCheck(entry["source"], "a" * 64, True, True)
    found = check(doc, served=served)
    assert len(found) == 1 and found[0].startswith(f"served: {entry['source']}: ")


def ahead(field: str, delta: timedelta) -> tuple[str, ...]:
    doc = feed_doc()
    moment = WALL + delta
    doc[field] = moment.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return check(doc)


@pytest.mark.parametrize("field", ["generated_at", "published_at"])
def test_timestamps_ahead_of_the_clock_fail(field: str) -> None:
    assert ahead(field, timedelta(minutes=10)) == ()
    assert ahead(field, timedelta(minutes=-30)) == ()
    found = ahead(field, timedelta(minutes=10, seconds=1))
    assert len(found) == 1 and found[0].startswith(f"timestamp: {field} is ")
    assert found[0] == (
        f"timestamp: {field} is 2026-10-19T12:10:01Z, "
        "more than 10 minutes ahead of 2026-10-19T12:00:00Z"
    )
    fractional = ahead(field, timedelta(minutes=10, microseconds=500_000))
    assert len(fractional) == 1 and fractional[0].startswith("timestamp: ")
    assert timedelta(minutes=10) == MAX_AHEAD


def test_an_offset_timestamp_is_a_schema_problem() -> None:
    doc = feed_doc()
    doc["generated_at"] = "2026-10-19T14:00:00+02:00"
    problems = check(doc)
    assert any(p.startswith("schema: ") and "generated_at" in p for p in problems), problems
    doc = feed_doc()
    doc["published_at"] = "2026-10-19T12:00:00"
    assert any(p.startswith("schema: ") for p in check(doc))


def test_wall_clock_zone_does_not_matter() -> None:
    doc = feed_doc()
    zone = timezone(timedelta(hours=-5))
    assert check(doc, wall=WALL.astimezone(zone)) == ()
    assert check(doc, wall=(WALL - timedelta(minutes=11)).astimezone(zone))


def test_naive_wall_clock_raises() -> None:
    doc = feed_doc()
    with pytest.raises(ValueError, match="timezone-aware"):
        check(doc, wall=datetime(2026, 10, 19, 12))
    with pytest.raises(ValueError, match="timezone-aware"):
        validate_feed(b"nope", served=[], wall_clock=datetime(2026, 10, 19, 12))


def test_schema_problems_are_sorted_and_cut() -> None:
    doc = feed_doc()
    doc["window"]["years"] = "x"
    doc["current_month"] = "b" * 1000
    doc["errors"] = [1] * 3
    problems = [p for p in check(doc) if p.startswith("schema: ")]
    assert len(problems) >= 5
    paths = [p.split(": ")[1] for p in problems]
    assert paths == sorted(paths, key=lambda s: s.split("/"))
    assert all(len(p) <= 300 for p in problems)
    assert any(len(p) == 300 for p in problems)


# --- review round 1: never raise on an odd shape, never pass what cannot be read --------------


def first_card(doc: dict[str, Any]) -> dict[str, Any]:
    return next(c for items in doc["months"].values() for c in items if c["children"])


def umbrella_card(doc: dict[str, Any]) -> dict[str, Any]:
    return next(c for items in doc["months"].values() for c in items if c["umbrellas"])


def odd_possible_matches(doc: dict[str, Any]) -> None:
    first_card(doc)["children"][0]["possible_matches"] = [[1]]


def odd_undated_id(doc: dict[str, Any]) -> None:
    doc["attention_items"][0]["undated_id"] = []


def odd_umbrella_children(doc: dict[str, Any]) -> None:
    umbrella_card(doc)["umbrellas"][0]["children"] = [{}]


def odd_window_month(doc: dict[str, Any]) -> None:
    doc["window"]["months"][0] = "0000-01"


ODD_ROWS = [
    ("possible_matches", odd_possible_matches, "invariant"),
    ("undated_id", odd_undated_id, "invariant"),
    ("umbrella children", odd_umbrella_children, "invariant"),
    ("month 0000-01", odd_window_month, "invariant"),
]


@pytest.mark.parametrize(("label", "change", "kind"), ODD_ROWS, ids=[r[0] for r in ODD_ROWS])
def test_odd_values_are_problems_not_exceptions(label: str, change: Any, kind: str) -> None:
    doc = feed_doc()
    change(doc)
    problems = check(doc)  # must not raise
    assert any(p.startswith(f"{kind}: ") for p in problems), (label, problems)


def test_a_window_month_that_is_not_a_real_month_is_an_invariant_problem() -> None:
    for bad in ("0000-01", "2026-13", "2026-00", "2026-1x"):
        doc = feed_doc()
        doc["window"]["months"][0] = bad
        problems = check(doc)
        assert any(p.startswith("invariant: ") and bad in p for p in problems), (bad, problems)


def pick(doc: Any, path: tuple[Any, ...]) -> Any:
    for step in path:
        doc = doc[step]
    return doc


def fuzz_paths(doc: dict[str, Any]) -> list[tuple[Any, ...]]:
    month = next(iter(doc["months"]))
    index = next(i for i, c in enumerate(doc["months"][month]) if c["children"])
    card = ("months", month, index)
    return [
        ("months",), ("months", month), (*card,), (*card, "children"), (*card, "children", 0),
        (*card, "children", 0, "possible_matches"), (*card, "children", 0, "child_id"),
        (*card, "children", 0, "sources"), (*card, "children", 0, "sources", 0),
        (*card, "children", 0, "sources", 0, "selected"), (*card, "umbrellas"),
        (*card, "sources"), (*card, "status"), (*card, "country"), (*card, "type"),
        (*card, "source_names"), (*card, "links"), (*card, "date"), (*card, "end_date"), (*card, "group_id"),
        ("window",), ("window", "months"), ("window", "months", 0),
        ("attention_items",), ("attention_items", 0), ("attention_items", 0, "undated_id"),
        ("attention_items", 0, "item_id"), ("attention_items", 0, "possible_matches"),
        ("undated",), ("source_health",), ("source_health", 0), ("source_health", 0, "source"),
        ("source_health", 0, "snapshot"), ("source_health", 0, "snapshot", "served_snapshot_id"),
        ("generated_at",), ("published_at",),
    ]  # fmt: skip


def empty_ok_paths(doc: dict[str, Any]) -> set[tuple[Any, ...]]:
    """Where an empty list is a valid feed: the optional or may-be-empty collections."""
    month = next(iter(doc["months"]))
    index = next(i for i, c in enumerate(doc["months"][month]) if c["children"])
    card = ("months", month, index)
    return {
        (*card, "children", 0, "possible_matches"), (*card, "umbrellas"),
        ("attention_items", 0, "possible_matches"), ("attention_items",),
    }  # fmt: skip


FUZZ_VALUES: list[Any] = [[], {}, [[1]], None, "0000-01"]


def test_a_replaced_value_at_any_depth_never_raises() -> None:
    base = feed_doc()
    paths = fuzz_paths(base)
    empty_ok = empty_ok_paths(base)
    served = served_for(base)
    for path in paths:
        for value in FUZZ_VALUES:
            doc = copy.deepcopy(base)
            original = pick(doc, path)
            pick(doc, path[:-1])[path[-1]] = copy.deepcopy(value)
            problems = validate_feed(dump(doc), served=served, wall_clock=WALL)  # no raise
            if doc == base:
                continue
            allowed = value == [] and isinstance(original, list) and path in empty_ok
            # a free-text card field accepts any other non-empty string
            allowed = allowed or (value == "0000-01" and path[3:] in (("country",), ("type",)))
            assert problems or allowed, (path, value)


def test_a_second_non_string_in_each_reference_is_a_problem() -> None:
    doc = feed_doc()
    first_card(doc)["children"][0]["possible_matches"] = [{"a": 1}]
    assert any(p.startswith("invariant: ") for p in check(doc))


def test_an_impossible_timestamp_is_a_problem_not_skipped() -> None:
    for field, value in (
        ("generated_at", "2026-13-01T00:00:00Z"),
        ("published_at", "2027-10-19T12:00:00Z\n"),
        ("published_at", "2026-02-30T00:00:00Z"),
    ):
        doc = feed_doc()
        doc[field] = value
        problems = check(doc)
        assert any(p.startswith(f"timestamp: {field} ") for p in problems), (field, value, problems)


def test_a_card_end_date_that_is_not_a_real_day_is_a_problem() -> None:
    for bad in ("2026-02-30", "2026-10-04\n"):
        doc = feed_doc()
        first_card(doc)["end_date"] = bad
        group = first_card(doc)["group_id"]
        problems = check(doc)
        assert any(
            p.startswith(f"invariant: card {group} ") and "end_date" in p for p in problems
        ), (bad, problems)


def test_a_card_date_with_a_trailing_newline_is_a_legacy_problem() -> None:
    doc = feed_doc()
    first_card(doc)["date"] = "2026-10-04\n"
    assert any(p.startswith("legacy: ") and "is not YYYY-MM-DD" in p for p in check(doc))
    doc = feed_doc()
    first_card(doc)["date"] = "2026-02-30"
    assert any(p.startswith("legacy: ") for p in check(doc))
    doc = feed_doc()
    first_card(doc)["date"] = "20261004"  # date.fromisoformat accepts it; the feed does not
    assert any(p.startswith("legacy: ") for p in check(doc))


def test_the_schema_accepts_the_republication_field() -> None:
    doc = feed_doc()
    assert check(doc) == ()
    doc["republished_from_sha256"] = "a" * 64
    assert check(doc) == ()
    for bad in ("x", "A" * 64, "a" * 63, 5, None):
        doc["republished_from_sha256"] = bad
        problems = check(doc)
        assert problems, bad
        assert problems[0].startswith("schema: /republished_from_sha256"), problems


def _schema_ends(doc: Any) -> bool:
    return any(p.startswith("schema: ") for p in check(doc))


def test_a_schema_pattern_reads_dollar_as_the_end_of_input() -> None:
    """ECMA-262 ``$`` without ``m`` is the end of input; Python's also matches before a final ``\\n``."""
    assert check(feed_doc()) == ()
    doc = feed_doc()
    doc["current_month"] += "\n"
    assert _schema_ends(doc)
    doc = feed_doc()
    first_card(doc)["group_id"] += "\n"
    assert _schema_ends(doc)
    doc = feed_doc()
    doc["window"]["months"][0] += "\n"
    assert _schema_ends(doc)
    doc = feed_doc()
    month = next(iter(doc["months"]))
    doc["months"][month + "\n"] = doc["months"].pop(month)  # a propertyNames pattern
    assert _schema_ends(doc)


def test_a_status_pattern_reads_dollar_as_the_end_of_input() -> None:
    from tests.feed.test_status import doc as status_doc

    assert validate.validate_status(json.dumps(status_doc()).encode()) == ()
    for field in ("attempt_id", "attempt_at", "code_sha"):
        bad = status_doc()
        bad[field] += "\n"
        problems = validate.validate_status(json.dumps(bad).encode())
        assert len(problems) == 1 and problems[0].startswith(f"schema: /{field}: "), problems
        assert "does not match" in problems[0]
    wrong_type = status_doc()
    wrong_type["attempt_id"] = 5  # a pattern is checked on strings only; the type is the one problem
    (problem,) = validate.validate_status(json.dumps(wrong_type).encode())
    assert "is not of type 'string'" in problem


def test_a_pattern_message_names_the_pattern_as_written() -> None:
    doc = feed_doc()
    doc["current_month"] = "2026-1"
    (problem,) = [p for p in check(doc) if p.startswith("schema: /current_month")]
    assert problem == "schema: /current_month: '2026-1' does not match '^[0-9]{4}-[0-9]{2}$'"


def test_every_schema_pattern_ends_in_one_unescaped_dollar() -> None:
    """The translation of ``$`` to ``\\Z`` is complete only if no pattern holds another bare ``$``."""

    def patterns(node: Any) -> Iterator[str]:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "pattern" and isinstance(value, str):
                    yield value
                else:
                    yield from patterns(value)
        elif isinstance(node, list):
            for value in node:
                yield from patterns(value)

    found = []
    for path in (validate.FEED_SCHEMA, validate.STATUS_SCHEMA):
        found += list(patterns(json.loads(path.read_text(encoding="utf-8"))))
    assert len(found) == 13
    for pattern in found:
        assert pattern.endswith("$") and not pattern.endswith("\\$"), pattern
        body = pattern[:-1]
        bare, in_class, i = 0, False, 0
        while i < len(body):
            char = body[i]
            if char == "\\":
                i += 2
                continue
            if char == "[":
                in_class = True
            elif char == "]":
                in_class = False
            elif char == "$" and not in_class:
                bare += 1
            i += 1
        assert bare == 0, pattern


# --- the final fix wave (final review T8-M1, T8-M2): bytes no JSON reader can use --------------

UNREADABLE = [
    pytest.param(b'"\\ud800"', id="lone high surrogate"),
    pytest.param(b'"\\udc00"', id="lone low surrogate"),
    pytest.param(b'{"\\ud800": 1}', id="surrogate in a key"),
    pytest.param(b'{"a": [{"b": "x\\ud800y"}]}', id="surrogate deep in a value"),
    pytest.param(b'{"a": NaN}', id="NaN"),
    pytest.param(b'{"a": [Infinity]}', id="Infinity"),
    pytest.param(b'{"a": -Infinity}', id="-Infinity"),
]


@pytest.mark.parametrize("data", UNREADABLE)
def test_json_no_reader_can_use_is_not_loadable(data: bytes) -> None:
    ok, doc = validate._load(data)
    assert (ok, doc) == (False, None)
    assert validate.validate_status(data) == ("json: not UTF-8 JSON",)
    assert validate.feed_content_problems(data, wall_clock=WALL) == ("json: not UTF-8 JSON",)
    assert validate.legacy_feed_problems(data, wall_clock=WALL) == ("legacy: not UTF-8 JSON",)
    assert validate.republished_problems(data, wall_clock=WALL) == ("json: not UTF-8 JSON",)
    assert validate.validate_feed(data, served=[], wall_clock=WALL) == ("json: not UTF-8 JSON",)


def test_a_surrogate_pair_and_ordinary_numbers_still_load() -> None:
    assert validate._load(b'"\\ud83d\\ude00"') == (True, "\U0001f600")
    assert validate._load(b'{"a": [1, 2.5, -0, 1e3, null, true]}')[0] is True


def test_a_legacy_feed_with_a_nan_or_a_lone_surrogate_has_a_json_problem() -> None:
    doc = json.loads(V1_FEED.read_bytes())
    doc["errors"] = ["@@"]
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    for replacement in ("NaN", '"\\ud800"'):
        data = text.replace('"@@"', replacement).encode("utf-8")
        assert validate.legacy_feed_problems(data, wall_clock=WALL) == ("legacy: not UTF-8 JSON",)
