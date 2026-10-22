"""Snapshot records, ids and the baseline loader (spec §5.10, §9.3; P91, P93, P94, P96)."""

import dataclasses
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from elections_calendar.fetch import FetchResult
from elections_calendar.model import (
    SOURCE_ORDER,
    Claim,
    InputUnit,
    RecordError,
    stored_json,
)
from elections_calendar.snapshots import (
    MAX_DIAGNOSTIC,
    REGISTRY_FILES,
    STAMPED,
    Baseline,
    CoverageGap,
    Disappeared,
    HistoryEntry,
    PageDownload,
    PageRecord,
    Snapshot,
    baseline_to_dict,
    build_snapshot,
    load_baseline,
    registry_version,
    snapshot_id,
)
from elections_calendar.window import window_for
from tests.support.fixture_claims import FIXTURE_NOW, fixture_results

YEARS = window_for(FIXTURE_NOW).years
SINCE = datetime(2026, 10, 19, 6, 0, tzinfo=UTC)
NAIVE = datetime(2026, 10, 19, 6, 0)


def snapshot_of(source: str) -> Snapshot:
    raw, result = fixture_results()[source]
    return build_snapshot(
        raw, result, parser_version="2.0", registry_version=registry_version(), years=YEARS
    )


def good(source: str = "osce") -> Baseline:
    return Baseline(snapshot_of(source), (), (), (), True, True)


def write(path: Path, data: Any) -> Path:
    path.write_bytes(data if isinstance(data, bytes) else stored_json(data))
    return path


@pytest.mark.parametrize("source", SOURCE_ORDER)
def test_snapshots_of_the_fixtures_round_trip(source: str, tmp_path: Path) -> None:
    snapshot = snapshot_of(source)
    assert len(snapshot.snapshot_id) == 64
    assert set(snapshot.snapshot_id) <= set("0123456789abcdef")
    baseline = Baseline(snapshot, (), (), (), True, True)
    path = write(tmp_path / "baseline.json", baseline_to_dict(baseline))
    assert load_baseline(path) == baseline


def test_snapshot_id_ignores_provenance() -> None:
    snapshot = snapshot_of("osce")
    assert set(STAMPED) == {"fetched_at", "fallback", "snapshot_id", "provisional"}
    stamped = [
        dataclasses.replace(
            c, fetched_at=SINCE, fallback=True, snapshot_id="x" * 64, provisional=True
        )
        for c in snapshot.claims
    ]
    assert snapshot_id(snapshot.units, stamped) == snapshot.snapshot_id
    first = snapshot.claims[0]
    other = next(c for c in snapshot.claims if c.span != first.span)
    swapped = [dataclasses.replace(first, span=other.span), *snapshot.claims[1:]]
    assert snapshot_id(snapshot.units, swapped) != snapshot.snapshot_id
    units = [dataclasses.replace(snapshot.units[0], text="changed"), *snapshot.units[1:]]
    assert snapshot_id(units, snapshot.claims) != snapshot.snapshot_id


def test_registry_version(tmp_path: Path) -> None:
    def copy_to(directory: Path) -> list[Path]:
        directory.mkdir()
        copies = []
        for source in REGISTRY_FILES:
            (directory / source.name).write_bytes(source.read_bytes())
            copies.append(directory / source.name)
        return copies

    first, second = copy_to(tmp_path / "a"), copy_to(tmp_path / "b")
    version = registry_version(first)
    assert version == registry_version() == registry_version(second)
    for changed in first:
        original = changed.read_bytes()
        changed.write_bytes(original + b" ")
        assert registry_version(first) != version
        changed.write_bytes(original)
    assert registry_version(first) == version


def refresh_id(data: dict[str, Any]) -> None:
    units = [InputUnit.from_dict(u) for u in data["units"]]
    claims = [Claim.from_dict(c) for c in data["claims"]]
    data["snapshot_id"] = snapshot_id(units, claims)


def shift_a_date(data: dict[str, Any]) -> None:
    claim = next(
        c
        for c in data["claims"]
        if c["date_precision"] == "day"
        and date.fromisoformat(c["date"]).day < 28
        and date.fromisoformat(c["end_date"]).day < 28
    )
    for key in ("date", "end_date"):
        claim[key] = (date.fromisoformat(claim[key]) + timedelta(days=1)).isoformat()


def stamp_a_claim(data: dict[str, Any]) -> None:
    data["claims"][0]["fallback"] = True
    refresh_id(data)


def orphan_a_claim(data: dict[str, Any]) -> None:
    claim = data["claims"][0]
    claim["unit_id"] = "osce:elections/999999"
    claim["claim_id"] = "osce:elections/999999#0"
    refresh_id(data)


def stamp_a_gap_claim(data: dict[str, Any]) -> None:
    claim = dict(next(c for c in data["claims"] if c["date"] is not None))
    claim["fallback"] = True
    data["coverage_gaps"] = [
        {
            "scope": "elections",
            "old_year": 2025,
            "new_year": 2026,
            "since": "2026-10-19T06:00:00Z",
            "claims": [claim],
        }
    ]


def fail_the_ledger_check(data: dict[str, Any]) -> None:
    data["checks"]["ledger"] = False


def drop_claims(data: dict[str, Any]) -> None:
    del data["claims"]


def add_a_key(data: dict[str, Any]) -> None:
    data["note"] = "x"


def units_object(data: dict[str, Any]) -> None:
    data["units"] = {}


def gaps_object(data: dict[str, Any]) -> None:
    data["coverage_gaps"] = {}


def orphan_a_unit(data: dict[str, Any]) -> None:
    """Move one unit (and its claims) under an id that no page's prefix starts."""
    old = data["units"][0]["unit_id"]
    new = "osce:nowhere/" + old.rsplit("/", 1)[-1]
    data["units"][0]["unit_id"] = new
    for claim in data["claims"]:
        if claim["unit_id"] == old:
            claim["unit_id"] = new
            claim["claim_id"] = new + claim["claim_id"][len(old) :]
    refresh_id(data)


def overlap_two_pages(data: dict[str, Any]) -> None:
    """A second page with the same prefix: every unit is on two pages."""
    pages = data["scope"]["pages"]
    pages.append({**pages[0], "key": "second"})


CORRUPT: list[tuple[str, Any, str]] = [
    ("open-brace", b"{", "not JSON"),
    ("not-utf-8", b"\xff", "not JSON"),
    ("list", b"[]", "shape: "),
    ("no-claims", drop_claims, "shape: "),
    ("extra-key", add_a_key, "shape: "),
    ("units-object", units_object, "shape: "),
    ("gaps-object", gaps_object, "shape: "),
    ("moved-date", shift_a_date, "record: Snapshot: snapshot_id does not match"),
    ("stamped-claim", stamp_a_claim, "record: Snapshot: claims are stored unstamped"),
    ("ledger-flag", fail_the_ledger_check, "record: Baseline: a baseline passed"),
    ("stamped-gap-claim", stamp_a_gap_claim, "record: CoverageGap: a gap holds unstamped claims"),
    ("orphan-claim", orphan_a_claim, "ledger: "),
    ("orphan-unit", orphan_a_unit, "ledger: unit osce:nowhere/"),
    ("unit-on-two-pages", overlap_two_pages, "ledger: unit osce:elections/"),
]


@pytest.mark.parametrize(
    ("edit", "start"), [(e, s) for _, e, s in CORRUPT], ids=[n for n, _, _ in CORRUPT]
)
def test_corrupt_baselines_are_never_served(
    edit: bytes | Callable[[dict[str, Any]], None], start: str, tmp_path: Path
) -> None:
    if isinstance(edit, bytes):
        path = write(tmp_path / "baseline.json", edit)
    else:
        data = baseline_to_dict(good())
        edit(data)
        path = write(tmp_path / "baseline.json", data)
    with pytest.raises(RecordError) as caught:
        load_baseline(path)
    assert str(caught.value).startswith("baseline.json is corrupt: " + start)
    assert load_baseline(tmp_path / "missing.json") is None


def test_a_good_baseline_loads(tmp_path: Path) -> None:
    path = write(tmp_path / "baseline.json", baseline_to_dict(good()))
    assert load_baseline(path) == good()


def page(**changes: Any) -> PageRecord:
    return dataclasses.replace(snapshot_of("osce").pages[0], **changes)


def test_page_record_rules() -> None:
    with pytest.raises(RecordError, match=r"^PageRecord.fetched_at must be timezone-aware$"):
        page(fetched_at=NAIVE)
    with pytest.raises(RecordError, match=r"^PageRecord: fetched_at and download go together$"):
        page(fetched_at=None)
    with pytest.raises(RecordError, match=r"^PageRecord: fetched_at and download go together$"):
        page(download=None)
    assert page(fetched_at=None, download=None).download is None
    snapshot = snapshot_of("osce")
    other = dataclasses.replace(snapshot.units[0], source="ipu", unit_id="ipu:elections/0")
    with pytest.raises(RecordError, match=r"^Snapshot: a unit or claim of another source$"):
        dataclasses.replace(snapshot, units=(other, *snapshot.units[1:]))
    stamped = dataclasses.replace(snapshot.claims[0], provisional=True)
    with pytest.raises(RecordError, match=r"^Snapshot: claims are stored unstamped$"):
        dataclasses.replace(snapshot, claims=(stamped, *snapshot.claims[1:]))
    with pytest.raises(RecordError, match=r"^Snapshot: snapshot_id does not match"):
        dataclasses.replace(snapshot, snapshot_id="0" * 64)
    with pytest.raises(RecordError, match=r"^HistoryEntry: fetched_at must be timezone-aware$"):
        HistoryEntry("elections", NAIVE, 1, 1)
    day = date(2026, 11, 1)
    with pytest.raises(RecordError, match=r"^Disappeared: since must be timezone-aware$"):
        Disappeared("e", "osce:elections/1", "t", "d", day, day, "https://e.test/", NAIVE)


def a_gap(**changes: Any) -> CoverageGap:
    claim = next(c for c in snapshot_of("aweb").claims if c.span.start is not None)
    values: dict[str, Any] = {
        "scope": "calendar",
        "old_year": 2026,
        "new_year": 2027,
        "since": SINCE,
        "claims": (claim,),
    }
    return CoverageGap(**{**values, **changes})


def test_coverage_gaps_round_trip(tmp_path: Path) -> None:
    snapshot = snapshot_of("aweb")
    baseline = Baseline(snapshot, (), (), (a_gap(),), True, True)
    path = write(tmp_path / "baseline.json", baseline_to_dict(baseline))
    assert load_baseline(path) == baseline
    message = r"^CoverageGap: a gap holds unstamped claims of a year change$"
    with pytest.raises(RecordError, match=message):
        a_gap(claims=())
    with pytest.raises(RecordError, match=message):
        a_gap(old_year=2027)
    with pytest.raises(RecordError, match=message):
        a_gap(claims=(dataclasses.replace(a_gap().claims[0], fallback=True),))
    with pytest.raises(RecordError, match=r"^CoverageGap: since must be timezone-aware$"):
        a_gap(since=NAIVE)
    foreign = a_gap(claims=(snapshot_of("osce").claims[0],))
    with pytest.raises(RecordError, match=r"^Baseline: a coverage gap of another source$"):
        Baseline(snapshot, (), (), (foreign,), True, True)
    with pytest.raises(RecordError, match=r"^Baseline: a baseline passed its ledger"):
        Baseline(snapshot, (), (), (), True, False)


def test_page_download_redacts_and_cuts() -> None:
    fetched = FetchResult(
        url="https://e.test/a",
        final_url="https://e.test/a;jsessionid=XYZ?token=abc&page=2" + "x" * 400,
        outcome="http_error",
        stage="response",
        http_status=500,
        content_type="text/html",
        body=b"12345",
        elapsed_ms=7,
        attempts=2,
        error_type="HTTPError",
        error="failed at https://e.test/?key=s3cret " + "y" * 400,
    )
    download = PageDownload.of(fetched)
    assert (download.bytes, download.elapsed_ms, download.attempts) == (5, 7, 2)
    for text in (download.final_url, download.error or ""):
        assert text
        assert len(text) <= MAX_DIAGNOSTIC
        assert not any(secret in text for secret in ("XYZ", "abc", "s3cret"))
