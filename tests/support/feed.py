"""A first run over the fixtures, as the pipeline will do it (Plan 4 Tasks 5-7 and 9).

``first_run()`` decides every source with no baseline, merges the served claims once at
``RUN_NOW`` and gives each source its match diagnostic, reasons and severity. Task 9 checks the
pipeline against the same values, so the two cannot drift apart.
"""

import dataclasses
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from types import MappingProxyType

from elections_calendar import ledger
from elections_calendar.feed import FeedParts, RunInfo, SourceResult, build_feed
from elections_calendar.health import HealthState, match_diagnostic, severity, source_reasons
from elections_calendar.ledger import LedgerReport
from elections_calendar.merge import merge
from elections_calendar.model import SOURCE_ORDER, Claim, MergeResult
from elections_calendar.places import PlaceRegistry
from elections_calendar.publish import feed_bytes
from elections_calendar.runner import SourceRun
from elections_calendar.snapshots import (
    Decision,
    Snapshot,
    build_snapshot,
    decide,
    registry_version,
    unit_items,
)
from elections_calendar.sources.base import PARSER_VERSION, ParseResult, RawPages
from elections_calendar.window import Window, window_for
from tests.support.fixture_claims import fixture_results

RUN_NOW = datetime(2026, 10, 19, 12, tzinfo=UTC)

# Each source's fetch time, from tests/fixtures/<source>/PROVENANCE.md.
FIXTURE_FETCHED: Mapping[str, datetime] = MappingProxyType({
    "electionguide": datetime(2026, 10, 16, 14, 39, tzinfo=UTC),
    "wikipedia": datetime(2026, 10, 17, 16, 13, tzinfo=UTC),
    "osce": datetime(2026, 10, 18, 11, 18, 37, tzinfo=UTC),
    "ipu": datetime(2026, 10, 18, 11, 18, 37, tzinfo=UTC),
    "aweb": datetime(2026, 10, 18, 11, 18, 38, tzinfo=UTC),
    "carter": datetime(2026, 10, 18, 11, 18, 40, tzinfo=UTC),
    "eeas": datetime(2026, 10, 18, 11, 18, 40, tzinfo=UTC),
    "ndi": datetime(2026, 10, 19, 8, 57, 34, tzinfo=UTC),
    "eisa": datetime(2026, 10, 19, 8, 57, 41, tzinfo=UTC),
})


@dataclass(frozen=True)
class FirstRun:
    window: Window
    sources: Mapping[str, SourceResult]
    merge: MergeResult
    claims: tuple[Claim, ...]  # every decision's served and provisional claims, in source order


def fixture_snapshot(source: str) -> tuple[RawPages, ParseResult, Snapshot, LedgerReport]:
    """The fixture pages (re-stamped with the source's fetch time), result, snapshot and report.

    NDI and EISA fetch through ``datetime.now``, so the pages are always re-stamped.
    """
    raw, result = fixture_results()[source]
    raw = dataclasses.replace(
        raw,
        pages=tuple(
            dataclasses.replace(p, fetched_at=FIXTURE_FETCHED[source]) for p in raw.pages
        ),
    )
    snapshot = build_snapshot(
        raw,
        result,
        parser_version=PARSER_VERSION,
        registry_version=registry_version(),
        years=window_for(RUN_NOW).years,
    )
    return raw, result, snapshot, ledger.check(raw, result)


@cache
def first_run() -> FirstRun:
    window = window_for(RUN_NOW)
    decided: dict[str, tuple[SourceRun, LedgerReport, Decision]] = {}
    for source in SOURCE_ORDER:
        raw, _, snapshot, report = fixture_snapshot(source)
        decision = decide(
            snapshot,
            run_outcome="complete",
            run_detail="",
            ledger=report,
            baseline=None,
            baseline_problem=None,
            acceptances=(),
            window=window,
            now=RUN_NOW,
        )
        decided[source] = (SourceRun(source, raw, "complete", 0), report, decision)
    claims = tuple(c for source in SOURCE_ORDER for c in decided[source][2].claims)
    merged = merge(claims, now=RUN_NOW, places=PlaceRegistry.load())
    fresh = frozenset(
        s for s, (_, _, d) in decided.items() if d.acceptance == "promoted"
    )
    sources: dict[str, SourceResult] = {}
    for source, (run, report, decision) in decided.items():
        items = unit_items(decision)
        match = match_diagnostic(merged, claims, source, fresh=fresh, window=window)
        reasons = source_reasons(decision.reasons, items, match, HealthState(()))
        sources[source] = SourceResult(
            source=source,
            run=run,
            parse_ms=0,
            ledger=report,
            decision=decision,
            items=items,
            match=match,
            reasons=reasons,
            acknowledged=(),
            severity=severity(reasons),
        )
    return FirstRun(window, MappingProxyType(sources), merged, claims)


@cache
def fixture_feed() -> tuple[FeedParts, bytes]:
    """The ``first_run()`` feed document and its published bytes (``RUN_NOW`` for both times)."""
    run = first_run()
    parts = build_feed(
        run.merge,
        [run.sources[s] for s in SOURCE_ORDER],
        window=run.window,
        now=RUN_NOW,
        run=RunInfo("local", ()),
        run_reasons=(),
    )
    return parts, feed_bytes(parts.doc, published_at=RUN_NOW)
