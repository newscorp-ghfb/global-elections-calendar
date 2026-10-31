"""``known_unit_reasons``: which unit reasons the last served data already had (P149)."""

import pytest

from elections_calendar.health import UNIT_REASONS
from elections_calendar.model import InputUnit, Outcome, Reason, Relevance
from elections_calendar.snapshots import _UNIT_OUTCOME, Snapshot, known_unit_reasons
from tests.support.snapshots import SynthPage, synth

T1, T2, T3 = "first unit", "second unit", "third unit"
PAGES = {"p26": ("s", 2026), "p27": ("s", 2027), "q26": ("q", 2026)}

Spec = tuple[str, str, str, Relevance]  # (page, outcome, text, relevance)


def U(text: str, page: str = "p26", relevance: Relevance = "in_or_after_window") -> Spec:  # noqa: N802
    return (page, "unparsed", text, relevance)


def P(text: str, page: str = "p26", relevance: Relevance = "in_or_after_window") -> Spec:  # noqa: N802
    return (page, "partial", text, relevance)


def parsed(text: str, page: str = "p26") -> Spec:
    return (page, "parsed", text, "in_or_after_window")


def snapshot(specs: list[Spec], source: str = "aweb") -> Snapshot:
    by_page: dict[str, list[InputUnit]] = {}
    for n, (page, outcome, text, relevance) in enumerate(specs, 1):
        by_page.setdefault(page, [])
        outcome_: Outcome = outcome  # type: ignore[assignment]
        by_page[page].append(
            InputUnit(
                f"{source}:{page}/u{n}",
                source,
                text,
                outcome_,
                None if outcome == "parsed" else "no date",
                relevance,
            )
        )
    pages = tuple(
        SynthPage(page, scope=PAGES[page][0], year=PAGES[page][1], extra=tuple(units))
        for page, units in by_page.items()
    )
    return synth(source, pages)


def reason(code: str) -> Reason:
    return Reason(code, "units")  # type: ignore[arg-type]


UR, PR, TO = reason("unparsed_relevant"), reason("partial_relevant"), reason("timeout")


def rows() -> dict[str, tuple[list[Reason], list[Spec], list[Spec] | None, str, tuple[Reason, ...]]]:
    return {
        "none": ([UR], [U(T1)], None, "aweb", ()),
        "all": ([UR], [U(T1), U(T2)], [U(T1), U(T2), parsed(T3)], "aweb", (UR,)),
        "one_new": ([UR], [U(T1), U(T2)], [U(T1)], "aweb", ()),
        "outcome": ([UR], [U(T1)], [P(T1)], "aweb", ()),
        "spaces": ([UR], [U("a b")], [U("a \n  b")], "aweb", (UR,)),
        "case": ([UR], [U("A b")], [U("a b")], "aweb", ()),
        "partial": ([PR], [P(T1)], [P(T1)], "aweb", (PR,)),
        "mixed_outcomes": ([UR, PR], [U(T1), P(T2)], [U(T1)], "aweb", (UR,)),
        "other_reason": ([TO, UR], [U(T1)], [U(T1)], "aweb", (UR,)),
        "reordered": ([UR], [U(T2), U(T1)], [U(T1), U(T2)], "aweb", (UR,)),
        "extra_occurrence": ([UR], [U(T1), U(T1)], [U(T1)], "aweb", ()),
        "other_scope": ([UR], [U(T1, "q26")], [U(T1)], "aweb", ()),
        "page_year_changed": ([UR], [U(T1, "p27")], [U(T1)], "aweb", (UR,)),
        "other_source": ([UR], [U(T1)], [U(T1)], "ndi", ()),
        "baseline_before_window": ([UR], [U(T1)], [U(T1, relevance="before_window")], "aweb", ()),
    }


@pytest.mark.parametrize("name", list(rows()))
def test_known_unit_reasons(name: str) -> None:
    reasons, served, before, before_source, expected = rows()[name]
    base = None if before is None else snapshot(before, before_source)
    assert known_unit_reasons(reasons, snapshot(served), base) == expected


def test_no_served_snapshot_knows_nothing() -> None:
    assert known_unit_reasons([UR], None, snapshot([U(T1)])) == ()


def test_the_unit_reasons_match_health() -> None:
    assert set(_UNIT_OUTCOME) == set(UNIT_REASONS)
