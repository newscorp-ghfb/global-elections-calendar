"""Unit attention items for the acknowledgement tests: real ones from the fixtures, or built."""

import dataclasses

from elections_calendar.model import AttentionItem, AttentionKind, short_id
from elections_calendar.snapshots import build_snapshot, decide, unit_items
from elections_calendar.window import window_for
from tests.support.fixture_claims import FIXTURE_NOW, fixture_results
from tests.support.snapshots import REGISTRY, report


def fixture_unit_items(source: str) -> tuple[AttentionItem, ...]:
    """One source's unit items on its fixtures: a first run, so its snapshot is promoted."""
    window = window_for(FIXTURE_NOW)
    raw, result = fixture_results()[source]
    snapshot = build_snapshot(
        raw, result, parser_version="2.0", registry_version=REGISTRY, years=window.years
    )
    decision = decide(
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
    assert decision.acceptance == "promoted"
    return unit_items(decision)


def item(
    kind: AttentionKind, source: str, unit_text: str | None, unit_id: str | None = None
) -> AttentionItem:
    """A unit item; ``text`` is the first 300 characters of ``unit_text``."""
    uid = unit_id or f"{source}:p/{short_id([kind, unit_text or ''])}"
    return AttentionItem(
        item_id=short_id([kind, uid]),
        kind=kind,
        source=source,
        link="https://example.test/p",
        snapshot_id="a" * 12,
        relevance="in_or_after_window",
        text=(unit_text or "")[:300],
        reason="no date",
        possible_matches=(),
        merge_ids=(),
        undated_id=None,
        unit_id=uid,
        unit_text=unit_text,
    )


def renumbered(items: tuple[AttentionItem, ...]) -> tuple[AttentionItem, ...]:
    """The same texts under other unit ids and item ids, in the opposite order."""
    return tuple(
        dataclasses.replace(
            i, unit_id=f"{i.source}:other/{n}", item_id=short_id(["renumbered", str(n)])
        )
        for n, i in enumerate(reversed(items))
    )
