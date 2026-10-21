"""The cross-source match diagnostic (spec §9.5; S4-T16)."""

import re
from collections.abc import Collection
from datetime import UTC, datetime
from functools import cache
from typing import Any

import pytest

from elections_calendar import ledger
from elections_calendar.health import (
    HealthState,
    MatchDiagnostic,
    match_diagnostic,
    match_reason,
    severity,
    source_reasons,
)
from elections_calendar.merge import merge
from elections_calendar.model import SOURCE_ORDER, Claim, MergeResult, Reason
from elections_calendar.places import PlaceRegistry
from elections_calendar.snapshots import build_snapshot, decide, registry_version
from elections_calendar.sources.base import PARSER_VERSION, ParseResult, RawPages, Registries
from elections_calendar.sources.osce import Osce
from elections_calendar.window import window_for
from tests.support.claims import NOW, cl, day, result
from tests.support.feed import RUN_NOW, first_run, fixture_snapshot
from tests.support.fixture_claims import FIXTURE_NOW, fixture_claims
from tests.support.fixtures import fixture
from tests.support.pages import raw_pages
from tests.support.pages import result as fetched
from tests.support.snapshots import promoted

WINDOW = window_for(NOW)
ALL = frozenset(SOURCE_ORDER)
COUNTRIES = ("SE", "NO", "DK", "FI", "IS")


def nat(source: str, cc: str, **fields: Any) -> Claim:
    """A national contest of country ``cc`` on 15 November 2026 (in the window)."""
    preset = dict(place_id=f"iso:{cc}", place_raw=cc, institution=f"iso:{cc}/riksdag")
    return cl(f"{source}:p/{cc}", preset, **fields)


def diag(
    claims: list[Claim], source: str = "osce", fresh: Collection[str] = ALL
) -> MatchDiagnostic:
    return match_diagnostic(result(*claims), claims, source, fresh=fresh, window=WINDOW)


def osce_five() -> list[Claim]:
    return [nat("osce", cc) for cc in COUNTRIES]


def test_match_diagnostic() -> None:
    # ipu lists SE and NO, wikipedia SE and IS: 3 of the 5 contests have another source.
    base = [
        *osce_five(),
        nat("ipu", "SE"),
        nat("ipu", "NO"),
        nat("wikipedia", "SE"),
        nat("wikipedia", "IS"),
    ]
    assert diag(base) == MatchDiagnostic(5, 2, 3, 2, True)

    # Not eligible: subnational, aggregate, outside the window, a provisional claim only.
    # carter lists the places of the noise: it is no peer of any eligible contest.
    noise = [
        nat("osce", "PL", level="subnational"),
        nat("osce", "DE", aggregate=True),
        nat("osce", "EE", span=day(2027, 6, 1)),
        nat("ipu", "PT"),
        nat("osce", "PT", provisional=True),
        *(nat("carter", cc, span=day(2026, 11, 16)) for cc in ("PL", "DE", "EE")),
    ]
    assert diag([*base, *noise]) == MatchDiagnostic(5, 2, 3, 2, True)

    # A peer that is not fresh counts for neither peers_fresh nor matched.
    assert diag(base, fresh={"osce", "ipu"}) == MatchDiagnostic(5, 1, 2, 3, False)
    assert diag(base, fresh={"osce", "wikipedia"}) == MatchDiagnostic(5, 1, 2, 3, False)

    # A peer's provisional claim is no match.
    provisional = [*osce_five(), nat("ipu", "SE", provisional=True), nat("wikipedia", "NO")]
    assert diag(provisional).matched == 1

    # 5 eligible and 2 peers: informative; 4 eligible or 1 peer: not.
    assert diag(base).informative
    assert not diag([c for c in base if "FI" not in c.place_id]).informative
    assert not diag([c for c in base if c.source != "wikipedia"]).informative


def test_match_reason() -> None:
    # Both peers list one of the countries, but on another date: nothing matches.
    elsewhere = [
        *osce_five(),
        nat("ipu", "SE", span=day(2026, 12, 20)),
        nat("wikipedia", "NO", span=day(2026, 12, 20)),
    ]
    got = diag(elsewhere)
    assert got == MatchDiagnostic(5, 2, 0, 5, True)
    assert match_reason(got) == Reason(
        "no_cross_source_match", "no other source lists any of its 5 in-window national contests"
    )
    # Not informative: no reason, matched or not.
    assert match_reason(MatchDiagnostic(4, 2, 0, 4, False)) is None
    assert match_reason(MatchDiagnostic(5, 1, 0, 5, False)) is None
    assert match_reason(MatchDiagnostic(5, 2, 1, 4, True)) is None


@cache
def _fixture_merge() -> MergeResult:
    return merge(fixture_claims(), now=FIXTURE_NOW, places=PlaceRegistry.load())


FIXTURE_MATCH = [
    ("electionguide", MatchDiagnostic(46, 8, 38, 8, True)),
    ("osce", MatchDiagnostic(7, 5, 7, 0, True)),
    ("wikipedia", MatchDiagnostic(54, 8, 37, 17, True)),
    ("ndi", MatchDiagnostic(7, 7, 5, 2, True)),
    ("aweb", MatchDiagnostic(3, 6, 3, 0, False)),
    ("eisa", MatchDiagnostic(6, 6, 5, 1, True)),
    ("ipu", MatchDiagnostic(18, 7, 14, 4, True)),
    ("carter", MatchDiagnostic(0, 0, 0, 0, False)),
    ("eeas", MatchDiagnostic(0, 0, 0, 0, False)),
]


@pytest.mark.parametrize(("source", "expected"), FIXTURE_MATCH)
def test_match_diagnostic_on_the_fixtures(source: str, expected: MatchDiagnostic) -> None:
    got = match_diagnostic(
        _fixture_merge(), fixture_claims(), source, fresh=ALL, window=window_for(FIXTURE_NOW)
    )
    assert got == expected
    assert match_reason(got) is None


# --- the OSCE column shift ----------------------------------------------------------------

_CAPTURED = datetime(2026, 10, 18, tzinfo=UTC)
_COUNTRY = '<th style="width: 25%;">Country</th>'
_ACTIVITY = '<th style="width: 25%;">Activity</th>'
_ELECTION = '<th style="width: 25%;">Election</th>'


def _page() -> str:
    return fixture("osce", "elections.html", "2026-10-18").decode()


def _parse_osce(text: str) -> tuple[RawPages, ParseResult]:
    window = window_for(_CAPTURED)
    adapter = Osce()
    request = adapter.requests(window)[0]
    raw = raw_pages("osce", [(request, fetched(text.encode(), url=request.url))])
    return raw, adapter.parse(raw, window, Registries.load())


def _with_type_column(text: str) -> str:
    """A ``Type`` column after ``Country``, with a ``<td>-</td>`` after each row's second cell."""
    head = text.replace(_COUNTRY, _COUNTRY + "<th>Type</th>", 1)
    start, end = head.index("<tbody"), head.index("</tbody>")
    shifted: list[str] = []
    for row in re.split(r"(?=<tr)", head[start:end]):
        cells = [m.end() for m in re.finditer(r"</td>", row)]
        if row.startswith("<tr") and len(cells) >= 2:
            row = row[: cells[1]] + "<td>-</td>" + row[cells[1] :]
        shifted.append(row)
    return head[:start] + "".join(shifted) + head[end:]


def test_osce_column_shift_is_an_error() -> None:
    _, base = _parse_osce(_page())
    assert len(base.claims) == 180

    # Columns are found by header: an inserted column changes no claim.
    shifted = _with_type_column(_page())
    assert shifted.count("<td>-</td>") == 634
    _, moved = _parse_osce(shifted)
    assert len(moved.units) == 634
    assert moved.claims == base.claims

    # A missing or renamed header is caught by the layout check, before any match diagnostic.
    baseline = promoted(fixture_snapshot("osce")[2])
    window = window_for(RUN_NOW)
    for broken in (
        _page().replace(_ACTIVITY, "", 1),
        _page().replace(_ELECTION, "<th>Contest</th>", 1),
    ):
        raw, parsed = _parse_osce(broken)
        assert parsed.coverage[0].outcome == "layout_not_recognised"
        assert parsed.coverage[0].detail == "0 tables with headers date, country, election, activity"
        assert parsed.units == ()
        candidate = build_snapshot(
            raw,
            parsed,
            parser_version=PARSER_VERSION,
            registry_version=registry_version(),
            years=window.years,
        )
        decision = decide(
            candidate,
            run_outcome="complete",
            run_detail="",
            ledger=ledger.check(raw, parsed),
            baseline=baseline,
            baseline_problem=None,
            acceptances=(),
            window=window,
            now=RUN_NOW,
        )
        assert decision.acceptance == "fallback"
        empty = MatchDiagnostic(0, 0, 0, 0, False)
        reasons = source_reasons(decision.reasons, (), empty, HealthState(()))
        assert [r.code for r in reasons] == ["layout_not_recognised"]
        assert severity(reasons) == "error"


@pytest.mark.parametrize(("source", "expected"), FIXTURE_MATCH)
def test_first_run_matches_the_fixture_table(source: str, expected: MatchDiagnostic) -> None:
    assert first_run().sources[source].match == expected
