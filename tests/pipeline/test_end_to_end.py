"""The whole offline pipeline on the committed fixture pages (Plan 4 Task 9).

One run of ``pipeline.run`` at ``RUN_NOW`` over ``tests/fixtures/pages.json`` feeds every test
here: the counts, Appendix B, the hand-written expected file (SC1), the v1-to-v2 mapping (SC2),
the feed size and the command line.
"""

import copy
import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml
from bs4 import BeautifulSoup

from elections_calendar import feed
from elections_calendar.__main__ import main
from elections_calendar.feed import RunInfo, build_feed, md_text
from elections_calendar.model import SOURCE_NAMES, SOURCE_ORDER
from elections_calendar.pipeline import OfflineGetter, RunConfig, RunResult, run
from elections_calendar.places import PlaceRegistry
from elections_calendar.publish import FEED_BUDGET_BYTES
from elections_calendar.runner import DEFAULT_ADAPTERS, load_adapter
from elections_calendar.sources.eisa import AJAX
from elections_calendar.text import collapse_ws, fold
from elections_calendar.validate import ServedCheck, validate_feed
from elections_calendar.window import window_for
from tests.support.appendix_b import appendix_b
from tests.support.feed import first_run
from tests.support.fixture_claims import fixture_claim
from tests.support.fixtures import FIXTURES

RUN_NOW = datetime(2026, 10, 19, 12, tzinfo=UTC)
EXPECTED = FIXTURES.parent / "expected"
V1_FEED = FIXTURES / "feed" / "2026-10-16-ff30417.json"
HTML = "text/html; charset=utf-8"
JSON = "application/json; charset=utf-8"

# The pages the adapters ask for at RUN_NOW (NDI stops after p1, EISA asks for the calendar and
# y2026 only): file -> (fetched_at, content type), from each PROVENANCE.md.
PAGES: dict[str, tuple[str, str]] = {
    "electionguide/2026-10-16/upcoming.html": ("2026-10-16T14:39:00Z", HTML),
    "electionguide/2026-10-16/past.html": ("2026-10-16T14:39:00Z", HTML),
    "electionguide/2026-10-16/anticipated.html": ("2026-10-16T14:39:00Z", HTML),
    "wikipedia/2026-10-16/national-2026.json": ("2026-10-17T16:13:00Z", JSON),
    "wikipedia/2026-10-16/national-2027.json": ("2026-10-17T16:13:00Z", JSON),
    "wikipedia/2026-10-16/local-2026.json": ("2026-10-17T16:13:00Z", JSON),
    "wikipedia/2026-10-16/local-2027.json": ("2026-10-17T16:13:00Z", JSON),
    "osce/2026-10-18/elections.html": ("2026-10-18T11:18:37Z", HTML),
    "ipu/2026-10-18/elections.html": ("2026-10-18T11:18:37Z", "text/html; charset=UTF-8"),
    "aweb/2026-10-18/calendar.html": ("2026-10-18T11:18:38Z", "text/html;charset=utf-8"),
    "carter/2026-10-18/observed.html": ("2026-10-18T11:18:40Z", "text/html; charset=UTF-8"),
    "eeas/2026-10-18/missions.html": ("2026-10-18T11:18:40Z", HTML),
    "ndi/2026-10-19/p0.html": ("2026-10-19T08:57:34Z", "text/html; charset=UTF-8"),
    "ndi/2026-10-19/p1.html": ("2026-10-19T08:57:36Z", "text/html; charset=UTF-8"),
    "eisa/2026-10-19/calendar.html": ("2026-10-19T08:57:41Z", "text/html; charset=UTF-8"),
    "eisa/2026-10-19/y2026.json": ("2026-10-19T08:57:53Z", "application/json; charset=UTF-8"),
}
SOURCE_KEYS = {name: key for key, name in SOURCE_NAMES.items()}
_SHA = re.compile(r"SHA-256 of `(?P<file>[^`]+)`:\*\* (?P<hex>[0-9a-f]{64})")


@dataclass(frozen=True)
class Fixture:
    out: Path
    result: RunResult
    asked: tuple[str, ...]
    feed_bytes: bytes
    doc: dict[str, Any]


@pytest.fixture(scope="module")
def e2e(tmp_path_factory: pytest.TempPathFactory) -> Fixture:
    """One run over ``tests/fixtures``, with the URLs it asked the offline getter for."""
    base = tmp_path_factory.mktemp("e2e")
    repo = base / "repo"
    repo.mkdir()
    asked: list[str] = []
    original = OfflineGetter.get

    def spy(self: OfflineGetter, url: str, **kw: Any) -> Any:
        asked.append(url)
        return original(self, url, **kw)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(OfflineGetter, "get", spy)
        result = run(
            RunConfig(
                out=base / "out",
                repo=repo,
                now=RUN_NOW,
                wall_clock=RUN_NOW,
                environ={},
                offline=FIXTURES,
                timer=lambda: 0.0,
            )
        )
    feed_bytes = (base / "out" / "elections.json").read_bytes()
    return Fixture(base / "out", result, tuple(asked), feed_bytes, json.loads(feed_bytes))


def cards_of(doc: Mapping[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    for month, cards in doc["months"].items():
        for card in cards:
            yield month, card


def test_pages_json_matches_provenance(e2e: Fixture) -> None:
    listed = json.loads((FIXTURES / "pages.json").read_text(encoding="utf-8"))
    assert set(listed) == {"pages"}
    pages = listed["pages"]
    assert {p["file"]: (p["fetched_at"], p["content_type"]) for p in pages} == PAGES
    assert all(p["status"] == 200 and set(p) == {"url", "file", "fetched_at", "content_type", "status"} for p in pages)
    for page in pages:
        path = FIXTURES / page["file"]
        found = {m["file"]: m["hex"] for m in _SHA.finditer((path.parent / "PROVENANCE.md").read_text(encoding="utf-8"))}
        assert found[path.name] == hashlib.sha256(path.read_bytes()).hexdigest(), page["file"]
    urls = [p["url"] for p in pages]
    assert len(set(urls)) == len(urls) == 16
    # every URL the run asks for is listed, and every entry is asked for
    assert sorted(set(e2e.asked)) == sorted(urls)
    # the adapters' first requests and the two follow-up pages
    window = window_for(RUN_NOW)
    first = {r.url for spec in DEFAULT_ADAPTERS for r in load_adapter(spec).requests(window)}
    assert first <= set(urls)
    assert set(urls) - first == {"https://www.ndi.org/elections-calendar?page=1", AJAX.format(table_id="38978")}


def test_end_to_end_counts(e2e: Fixture) -> None:
    doc = e2e.doc
    assert (e2e.result.outcome, e2e.result.verdict) == ("published", "red")
    assert doc["run"]["severity"] == "warning"
    assert doc["run"]["reasons"] == []
    assert {m: len(c) for m, c in doc["months"].items()} == {
        "2026-09": 22,
        "2026-10": 30,
        "2026-11": 28,
        "2026-12": 15,
        "2027-01": 5,
    }
    assert sum(len(c) for _, c in doc["months"].items()) == 100
    assert sum(len(card["children"]) for _, card in cards_of(doc)) == 202
    assert len(doc["attention_items"]) == 157
    assert Counter(i["relevance"] for i in doc["attention_items"]) == {"in_or_after_window": 126, "unknown": 31}
    assert doc["attention_truncated"] == 0
    assert doc["data_as_of"] == "2026-10-16T14:39:00Z"
    served = {
        "electionguide": "2026-10-16T14:39:00Z",
        "wikipedia": "2026-10-17T16:13:00Z",
        "osce": "2026-10-18T11:18:37Z",
        "ipu": "2026-10-18T11:18:37Z",
        "aweb": "2026-10-18T11:18:38Z",
        "carter": "2026-10-18T11:18:40Z",
        "eeas": "2026-10-18T11:18:40Z",
        "ndi": "2026-10-19T08:57:34Z",
        "eisa": "2026-10-19T08:57:41Z",
    }
    entries = {e["source"]: e for e in doc["source_health"]}
    assert set(entries) == set(served)
    for source, entry in entries.items():
        snap = entry["snapshot"]
        assert (snap["acceptance"], snap["comparable"], snap["using_fallback"]) == ("promoted", False, False), source
        assert snap["served_fetched_at"] == served[source], source
    assert {s: e["severity"] for s, e in entries.items()} == {
        "electionguide": "ok",
        "wikipedia": "warning",
        "osce": "ok",
        "ipu": "warning",
        "aweb": "warning",
        "carter": "ok",
        "eeas": "ok",
        "ndi": "warning",
        "eisa": "warning",
    }
    reasons = {s: [(r["code"], r["text"]) for r in e["reasons"]] for s, e in entries.items()}
    assert reasons == {
        "electionguide": [],
        "osce": [],
        "carter": [],
        "eeas": [],
        "wikipedia": [
            ("unparsed_relevant", "relevant units unparsed: 51"),
            ("partial_relevant", "relevant units partly parsed: 60"),
        ],
        "ipu": [("unparsed_relevant", "relevant units unparsed: 4")],
        "aweb": [
            ("unparsed_relevant", "relevant units unparsed: 1"),
            ("partial_relevant", "relevant units partly parsed: 2"),
        ],
        "ndi": [("partial_relevant", "relevant units partly parsed: 1")],
        "eisa": [
            ("not_published_yet", "no heading 'eisa african election calendar 2027'"),
            ("unparsed_relevant", "relevant units unparsed: 2"),
        ],
    }
    # the served check comes from the artifact's own baselines, not from the feed under test
    checks = []
    for source, entry in entries.items():
        baseline = json.loads((e2e.out / "data" / "sources" / source / "baseline.json").read_text(encoding="utf-8"))
        assert entry["snapshot"]["served_snapshot_id"] == baseline["snapshot_id"], source
        checks.append(
            ServedCheck(source, baseline["snapshot_id"], baseline["checks"]["ledger"], baseline["checks"]["discovery"])
        )
    assert validate_feed(e2e.feed_bytes, served=checks, wall_clock=RUN_NOW) == ()
    manifest = json.loads((e2e.out / "manifest.json").read_text(encoding="utf-8"))
    on_disk = {p.relative_to(e2e.out).as_posix() for p in e2e.out.rglob("*") if p.is_file()}
    assert set(manifest["files"]) == on_disk - {"manifest.json"}
    for name, digest in manifest["files"].items():
        assert hashlib.sha256((e2e.out / name).read_bytes()).hexdigest() == digest, name


def test_appendix_b_in_the_feed(e2e: Fixture) -> None:
    cards = {card["group_id"]: card for _, card in cards_of(e2e.doc)}
    rows = appendix_b()
    assert len(rows) == 23

    def of(merge_id: str) -> tuple[str, str | None]:
        claim = fixture_claim(merge_id.removeprefix("served/"))
        return SOURCE_NAMES[claim.source], claim.link

    for row in rows:
        group_id, place, level, start, end, precision, meaning, date_status, status, type_, children, umbrellas = row
        card = cards[group_id]
        assert (
            card["place_id"],
            card["level"],
            card["date"],
            card["end_date"],
            card["date_precision"],
            card["date_meaning"],
            card["date_status"],
            card["status"],
            card["type"],
        ) == (place, level, start, end, precision, meaning, date_status, status, type_), group_id
        assert [c["child_id"] for c in card["children"]] == [c[0] for c in children], group_id
        for child, (child_id, aggregate, conflict, sources) in zip(card["children"], children, strict=True):
            assert (child["aggregate"], child["date_conflict"]) == (aggregate, conflict), child_id
            assert [(s["name"], s["link"], s["rejected_reason"]) for s in child["sources"]] == [
                (*of(merge_id), reason) for merge_id, reason in sources
            ], child_id
        assert sorted((u["name"], u["link"]) for u in card["umbrellas"]) == sorted(of(m) for m in umbrellas), group_id


# --- SC1: the hand-written expected file --------------------------------------------------------


def _strings(value: object) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def page_text(path: Path) -> str:
    """The text of a fixture page: HTML as text, JSON as the text of each of its string values."""
    body = path.read_bytes().decode("utf-8")
    if path.suffix == ".json":
        parts = [BeautifulSoup(s, "lxml").get_text(" ") for s in _strings(json.loads(body))]
        return " ".join(collapse_ws(p) for p in parts)
    return collapse_ws(BeautifulSoup(body, "lxml").get_text(" "))


def source_texts() -> dict[str, list[str]]:
    texts: dict[str, list[str]] = {}
    for file in PAGES:
        texts.setdefault(file.split("/")[0], []).append(page_text(FIXTURES / file))
    return texts


def card_date(card: Mapping[str, Any]) -> str:
    if card["date_precision"] == "month":
        return str(card["date"])[:7]
    if card["date"] == card["end_date"]:
        return str(card["date"])
    return f"{card['date']} to {card['end_date']}"


def in_scope(doc: Mapping[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Every child of a national or unknown-level card, and of a subnational card of 2026-10."""
    return [
        (card, child)
        for month, card in cards_of(doc)
        if card["level"] in ("national", "unknown") or (card["level"] == "subnational" and month == "2026-10")
        for child in card["children"]
    ]


def entry_children(entry: Mapping[str, Any], scope: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[str]:
    """The ids of the children an entry fits: its office is in the child's label, and the rest is equal.

    When several fit and one's label is exactly the entry's office, that child is the entry's
    ("municipal elections" is the whole label of one Ontario child and part of another's).
    """
    fits = []
    for card, child in scope:
        label = fold(child["office_label"])
        if (
            (card["place_id"], card["level"], card["status"], card_date(card))
            == (entry["place"], entry["level"], entry["status"], entry["date"])
            and fold(entry["office"]) in label
            and child["round"] == entry["round"]
            and ("jurisdiction" not in entry or child["jurisdiction"] == entry["jurisdiction"])
            and entry["source"] in {SOURCE_KEYS[s["name"]] for s in child["sources"]}
        ):
            fits.append((child["child_id"], label))
    exact = [child_id for child_id, label in fits if label == fold(entry["office"])]
    return exact if len(fits) > 1 and exact else [child_id for child_id, _ in fits]


def test_expected_file(e2e: Fixture) -> None:
    entries = yaml.safe_load((EXPECTED / "2026-10-16.yaml").read_text(encoding="utf-8"))
    assert len(entries) == 122
    assert all(
        set(e) in ({"place", "office", "round", "date", "level", "status", "source", "quote"},
                   {"place", "office", "jurisdiction", "round", "date", "level", "status", "source", "quote"})
        for e in entries
    )
    texts = source_texts()
    for entry in entries:
        assert any(entry["quote"] in text for text in texts[entry["source"]]), entry["quote"]
    scope = in_scope(e2e.doc)
    assert len(scope) == 122
    fitted = [entry_children(entry, scope) for entry in entries]
    for entry, hits in zip(entries, fitted, strict=True):
        assert len(hits) == 1, (entry["place"], entry["office"], entry["date"], hits)
    # every child in scope is the one child of exactly one entry
    assert sorted(h for (h,) in fitted) == sorted(child["child_id"] for _, child in scope)
    elsewhere = sum(
        len(card["children"])
        for month, card in cards_of(e2e.doc)
        if card["level"] == "subnational" and month != "2026-10"
    )
    print(f"subnational children in other months: {elsewhere}")
    assert elsewhere == 80


# --- SC2: every v1 record maps to a v2 card -----------------------------------------------------


def near(label: str, kind: str) -> bool:
    """The folded ``label`` contains the folded ``kind`` or is contained in it."""
    a, b = fold(label), fold(kind)
    return a in b or b in a


def map_v1(v1: Mapping[str, Any], feed: Mapping[str, Any], places: PlaceRegistry) -> dict[str, Any]:
    """Place each v1 record on a v2 card (P101): place and span, then link, then label, then witness."""
    cards = [card for _, card in cards_of(feed)]
    result: dict[str, Any] = {"unmapped": [], "ambiguous": [], "unwitnessed": [], "witness": Counter(), "step": Counter()}
    by_card: dict[str, list[dict[str, str]]] = {}
    for record in (r for month in v1["months"].values() for r in month):
        place = places.resolve(record["country"])
        # 1. the cards of the record's place whose span holds its date
        hits = [
            c
            for c in cards
            if place is not None and c["place_id"] == place.place_id and c["date"] <= record["date"] <= c["end_date"]
        ]
        if not hits:
            result["unmapped"].append({"date": record["date"], "country": record["country"]})
            continue
        # 2. exactly one of them has a child source with one of the record's links
        linked = [c for c in hits if any(s["link"] in record["links"] for ch in c["children"] for s in ch["sources"])]
        step = "unique"
        picked = hits
        # (on these fixtures the label step alone would pick the same card as the link step)
        if len(hits) > 1 and len(linked) == 1:
            picked, step = linked, "by_link"
        # 3. still several: those with a child whose label contains, or is contained in, the type
        if len(picked) > 1:
            labelled = [c for c in picked if any(near(ch["office_label"], record["type"]) for ch in c["children"])]
            if labelled:
                picked, step = labelled, "by_label"
        if len(picked) != 1:
            result["ambiguous"].append(
                {"date": record["date"], "country": record["country"], "cards": sorted(c["group_id"] for c in picked)}
            )
            continue
        card = picked[0]
        # 4. the witness: a child or an umbrella of that card carries the record's type
        by_child = any(near(ch["office_label"], record["type"]) for ch in card["children"])
        by_umbrella = any(near(u["office_label"], record["type"]) for u in card["umbrellas"])
        brief = {"date": record["date"], "country": record["country"], "type": record["type"]}
        if not (by_child or by_umbrella):
            result["unwitnessed"].append(brief)
        result["witness"]["child" if by_child else "umbrella" if by_umbrella else "none"] += 1
        result["step"][step] += 1
        by_card.setdefault(card["group_id"], []).append(brief)
    result["merged"] = {group: records for group, records in by_card.items() if len(records) > 1}
    return result


def test_v1_records_map_to_v2_cards(e2e: Fixture) -> None:
    v1 = json.loads(V1_FEED.read_text(encoding="utf-8"))
    assert sum(len(m) for m in v1["months"].values()) == 50
    mapped = map_v1(v1, e2e.doc, PlaceRegistry.load())
    expected = yaml.safe_load((EXPECTED / "legacy-mapping-exceptions.yaml").read_text(encoding="utf-8"))
    assert set(expected) == {"unmapped", "ambiguous", "merged", "unwitnessed"}
    assert sum(mapped["witness"].values()) == 44
    assert mapped["witness"] == {"child": 42, "umbrella": 2}
    assert mapped["step"] == {"unique": 36, "by_link": 7, "by_label": 1}
    for kind in ("unmapped", "ambiguous", "merged", "unwitnessed"):
        assert mapped[kind] == expected[kind], kind
    assert len(mapped["unmapped"]) == 5
    assert len(mapped["ambiguous"]) == 1


def test_sc2_needs_a_witness(e2e: Fixture) -> None:
    v1 = json.loads(V1_FEED.read_text(encoding="utf-8"))
    places = PlaceRegistry.load()
    # on the real feed no child carries both records of a merged card
    cards = {card["group_id"]: card for _, card in cards_of(e2e.doc)}
    merged = map_v1(v1, e2e.doc, places)["merged"]
    assert set(merged) == {"54b356d5b5ea", "4b35f9d2401c"}
    for group, records in merged.items():
        first, second = records[0]["type"], records[1]["type"]
        for child in cards[group]["children"]:
            assert not (near(child["office_label"], first) and near(child["office_label"], second)), group
    # a card whose child no longer says "Presidency" and which has no umbrella witnesses neither
    broken = copy.deepcopy(e2e.doc)
    (card,) = (c for _, c in cards_of(broken) if c["group_id"] == "4b35f9d2401c")
    (child,) = (c for c in card["children"] if c["child_id"] == "f90b0d7db440")
    child["office_class"], child["office_label"] = "lower_house", "Chamber of Deputies"
    card["umbrellas"] = []
    assert map_v1(v1, broken, places)["unwitnessed"] == [
        {"date": "2026-10-25", "country": "Brazil", "type": "Brazilian Presidency"},
        {"date": "2026-10-25", "country": "Brazil", "type": "2026 General Elections (2nd round)"},
    ]


# --- size and command line ----------------------------------------------------------------------


def test_every_relevant_item_is_served_or_counted(
    e2e: Fixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """P112 (M2, transport half): the feed holds the first relevant items in cap order."""
    full = json.loads((e2e.out / "attention_full.json").read_text(encoding="utf-8"))["items"]
    rank = {"in_or_after_window": 0, "unknown": 1}
    relevant = sorted(
        (i for i in full if i["relevance"] in rank),
        key=lambda i: (rank[i["relevance"]], i["date"] is None, i["date"] or "", i["item_id"]),
    )
    items = e2e.doc["attention_items"]
    assert len(relevant) == 157
    assert [i["item_id"] for i in items] == [i["item_id"] for i in relevant[: len(items)]]
    assert len(items) + e2e.doc["attention_truncated"] == 157
    assert (len(items), e2e.doc["attention_truncated"]) == (157, 0)

    run = first_run()
    expected = {i.item_id for i in run.merge.attention} | {
        i.item_id for s in run.sources.values() for i in s.items
    }
    assert {i["item_id"] for i in full} == expected

    monkeypatch.setattr(feed, "MAX_FEED_ITEMS", 100)
    capped = build_feed(
        run.merge,
        [run.sources[s] for s in SOURCE_ORDER],
        window=run.window,
        now=RUN_NOW,
        run=RunInfo("local", ()),
        run_reasons=(),
    ).doc
    assert [i["item_id"] for i in capped["attention_items"]] == [i["item_id"] for i in relevant[:100]]
    assert capped["attention_truncated"] == 57


def test_feed_size_on_the_fixtures(e2e: Fixture) -> None:
    size = len(e2e.feed_bytes)
    assert FEED_BUDGET_BYTES == 524_288
    assert size <= FEED_BUDGET_BYTES
    health = (e2e.out / "HEALTH.md").read_text(encoding="utf-8")
    assert f"- Feed: {md_text(size)} bytes of a 524288 byte budget" in health.splitlines()
    verdict = json.loads((e2e.out / "verdict.json").read_text(encoding="utf-8"))
    assert verdict["feed_bytes"] == size
    assert verdict["feed_budget_bytes"] == FEED_BUDGET_BYTES
    assert e2e.result.feed_bytes == size


def test_main_on_the_fixtures(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    out = tmp_path / "out"
    code = main(["--offline", str(FIXTURES), "--now", "2026-10-19T12:00:00Z", "--out", str(out), "--repo", str(repo)])
    assert code == 0
    size = len((out / "elections.json").read_bytes())
    assert capsys.readouterr().out == f"published, verdict red, {size} feed bytes\n"
