"""Source priority, roles and identity rules of the merge (spec section 10.1, 10.2, 10.5)."""

import hashlib
import re
from collections.abc import Iterable
from typing import Literal

from elections_calendar.model import Claim, DateSpan
from elections_calendar.text import norm_name


class MergeError(ValueError):
    """The merge cannot give a trustworthy result; publication stops."""


PRIORITY: tuple[str, ...] = (
    "electionguide",
    "osce",
    "wikipedia:national",
    "wikipedia:local",
    "ndi",
    "aweb",
    "eisa",
    "ipu",
    "carter",
    "eeas",
)
SOURCE_ORDER: tuple[str, ...] = (
    "electionguide",
    "osce",
    "wikipedia",
    "ndi",
    "aweb",
    "eisa",
    "ipu",
    "carter",
    "eeas",
)
REFERENDA: frozenset[str] = frozenset({"referendum_day", "referendum_question"})
CHAMBERS: frozenset[str] = frozenset({"lower_house", "upper_house", "legislature"})
Role = Literal["provisional", "anchor", "weak", "umbrella"]

QUALIFIERS: tuple[str, ...] = (
    "district",
    "ward",
    "constituency",
    "seat",
    "phase",
    "series",
    "division",
    "precinct",
    "circuit",
    "zone",
    "position",
    "place",
)
_Q = "|".join(QUALIFIERS)
_AFTER = re.compile(rf"\b({_Q})\s+(?:no\s+|number\s+)?([0-9]+)(?![0-9a-z])")
_BEFORE = re.compile(rf"(?<![0-9a-z])([0-9]+)(?:st|nd|rd|th)\s+(?:[a-z]+\s+){{0,4}}?({_Q})\b")


def family(claim: Claim) -> str:
    """The source family used for priority and rule F."""
    if claim.source == "wikipedia":
        name = (
            "wikipedia:national"
            if claim.unit_id.startswith("wikipedia:national-")
            else "wikipedia:local"
        )
    else:
        name = claim.source
    if name not in PRIORITY:
        raise MergeError(f"unknown source: {claim.source}")
    return name


def claim_order(claim: Claim) -> tuple[int, bool, str, str, str]:
    """Total order of claims: family priority, then event id (missing last), unit, merge id."""
    return (
        PRIORITY.index(family(claim)),
        claim.source_event_id is None,
        claim.source_event_id or "",
        claim.unit_id,
        claim.merge_id,
    )


def role(claim: Claim) -> Role:
    """The role of a claim in a contest (spec 10.2, P66, P67)."""
    if claim.provisional:
        return "provisional"
    if claim.evidence_kind == "observation":
        return "weak"
    if claim.office_class == "general" or claim.aggregate:
        return "umbrella"
    if (
        claim.evidence_kind == "calendar"
        and claim.span.precision == "day"
        and claim.date_meaning == "voting_period"
        and (claim.institution is not None or claim.kind in REFERENDA)
        and claim.jurisdiction_kind in ("nationwide", "named", "subdivision")
    ):
        return "anchor"
    return "weak"


def qualified_numbers(label: str) -> dict[str, frozenset[int]]:
    """Numbers that qualify a district, ward, phase and so on in a label (P80)."""
    text = norm_name(label)
    found: dict[str, set[int]] = {}
    for m in _AFTER.finditer(text):
        found.setdefault(m.group(1), set()).add(int(m.group(2)))
    for m in _BEFORE.finditer(text):
        found.setdefault(m.group(2), set()).add(int(m.group(1)))
    return {k: frozenset(v) for k, v in found.items()}


def _jurisdiction_agrees(a: Claim, b: Claim, relax: bool) -> bool:
    if a.jurisdiction_kind == "unknown" or b.jurisdiction_kind == "unknown":
        return relax
    if a.jurisdiction_kind == "nationwide" or b.jurisdiction_kind == "nationwide":
        return a.jurisdiction_kind == b.jurisdiction_kind
    return norm_name(a.jurisdiction or "") == norm_name(b.jurisdiction or "")


def identity_compatible(
    a: Claim,
    b: Claim,
    *,
    relax_jurisdiction: bool = False,
    ignore_kind: bool = False,
    ignore_institution: bool = False,
) -> bool:
    """Whether two claims can name one contest (spec 10.1, P78, P80)."""
    if a.place_id != b.place_id:
        return False
    if a.level != b.level and "unknown" not in (a.level, b.level):
        return False
    if not ignore_institution:
        if a.institution is not None and b.institution is not None:
            if a.institution != b.institution:
                return False
        elif a.office_class != b.office_class:
            return False
    if not _jurisdiction_agrees(a, b, relax_jurisdiction):
        return False
    if a.round is not None and b.round is not None and a.round != b.round:
        return False
    if not ignore_kind:
        if a.kind != b.kind:
            return False
        if a.kind == "referendum_question" and norm_name(a.office_label) != norm_name(
            b.office_label
        ):
            return False
    na = qualified_numbers(a.office_label)
    nb = qualified_numbers(b.office_label)
    return all(na[q] == nb[q] for q in na.keys() & nb.keys())


def same_source_compatible(a: Claim, b: Claim) -> bool:
    """Rule F (P70): one family's claims join only under equal labels."""
    return family(a) != family(b) or norm_name(a.office_label) == norm_name(b.office_label)


def years_of(span: DateSpan) -> frozenset[int]:
    if span.precision == "year":
        return frozenset({span.year})
    assert span.start is not None and span.end is not None
    return frozenset(range(span.start.year, span.end.year + 1))


def dates_compatible(a: Claim, b: Claim) -> bool:
    """Year spans meet by year, others by overlap; no tolerance (spec 10.2)."""
    if a.span.precision == "year" or b.span.precision == "year":
        return bool(years_of(a.span) & years_of(b.span))
    assert a.span.start and a.span.end and b.span.start and b.span.end
    return a.span.start <= b.span.end and b.span.start <= a.span.end


def joinable(a: Claim, b: Claim) -> bool:
    return identity_compatible(a, b) and same_source_compatible(a, b) and dates_compatible(a, b)


def gap_days(s: DateSpan, t: DateSpan) -> int:
    """Days between two dated spans; 0 when they overlap."""
    if s.start is None or s.end is None or t.start is None or t.end is None:
        raise ValueError("gap_days needs dated spans")
    if s.start <= t.end and t.start <= s.end:
        return 0
    if s.end < t.start:
        return (t.start - s.end).days
    return (s.start - t.end).days


def short_id(parts: Iterable[str]) -> str:
    return hashlib.sha1("\n".join(sorted(parts)).encode("utf-8")).hexdigest()[:12]
