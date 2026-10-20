"""Shared vocabulary of the v2 pipeline (spec §5).

This module is the bottom layer: it imports only the standard library.
Civil dates are ``datetime.date`` values (year/month/day components); a
civil date is never derived through a timestamp.

Annotations are not enforced at runtime and records also come back from
saved JSON, so every record checks its own fields when it is built: each
field must hold its annotated type, and a Literal field one of its words.
A record that breaks a rule raises ``RecordError``.
"""

import calendar
import functools
import hashlib
import json
import re
import types
import typing
from collections.abc import Iterable
from dataclasses import dataclass, fields
from datetime import UTC, date, datetime
from typing import Any, Final, Literal, get_args, get_origin

Precision = Literal["day", "month", "year"]
DateMeaning = Literal["voting_period", "expected_window", "unknown"]
DateStatus = Literal["confirmed", "tentative", "unknown"]
StatusClaim = Literal["postponed", "cancelled", "disputed", "held"]
Level = Literal["national", "subnational", "unknown"]
# named: a constituency, city or other named area; subdivision: a registered
# ISO 3166-2 subdivision (a state, province or region) of the place.
JurisdictionKind = Literal["nationwide", "named", "subdivision", "unknown"]
Kind = Literal[
    "candidate_election", "by_election", "referendum_day", "referendum_question", "aggregate"
]
OfficeClass = Literal[
    "head_of_state",
    "lower_house",
    "upper_house",
    "legislature",
    "governor",
    "mayor",
    "local_council",
    "referendum",
    "general",
]
EvidenceKind = Literal["calendar", "expected_renewal", "observation", "umbrella"]
Outcome = Literal["parsed", "partial", "unparsed", "ignored"]
IgnoredReason = Literal[
    "header_row",
    "year_heading",
    "empty_cell",
    "container_item",
    "appointed_chamber",
    "duplicate",
    "inactive_chamber",
    "no_expected_date",
    "footnote",
]
Relevance = Literal["in_or_after_window", "unknown", "before_window"]
FetchOutcome = Literal[
    "ok",
    "http_error",
    "timeout",
    "tls_error",
    "dns_error",
    "challenge_page",
    "api_error",
    "deadline",
    "fetch_failed",
]

IGNORED_REASONS: frozenset[str] = frozenset(get_args(IgnoredReason))
FIRST_YEAR = 1900  # Carter Center missions go back to 1989
LAST_YEAR = 2199


class RecordError(ValueError):
    """A record breaks the model's rules, whether built in code or loaded from JSON."""


def short_id(parts: Iterable[str]) -> str:
    """The first 12 hex characters of SHA-1 over the sorted parts joined by newlines."""
    return hashlib.sha1("\n".join(sorted(parts)).encode("utf-8")).hexdigest()[:12]


def canonical_json(value: object) -> bytes:
    """Compact JSON with sorted keys, UTF-8: the bytes that ids and versions hash."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def stored_json(value: object) -> bytes:
    """Indented JSON with a final newline, UTF-8: the form of committed files."""
    return (json.dumps(value, ensure_ascii=False, indent=1) + "\n").encode("utf-8")


SOURCE_ORDER: Final[tuple[str, ...]] = (
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
SOURCE_NAMES: Final[dict[str, str]] = {
    "electionguide": "ElectionGuide",
    "osce": "OSCE/ODIHR",
    "wikipedia": "Wikipedia",
    "ndi": "NDI",
    "aweb": "A-WEB",
    "eisa": "EISA",
    "ipu": "IPU",
    "carter": "Carter Center",
    "eeas": "EEAS",
}


def month_end(year: int, month: int) -> date:
    """Last civil day of the month."""
    return date(year, month, calendar.monthrange(year, month)[1])


@dataclass(frozen=True, slots=True)
class DateSpan:
    """A civil-date interval (spec §5.2).

    Day and month precision always have ``start`` and ``end`` (inclusive);
    month precision runs from the 1st of the start month to the last day of
    the end month. Year precision ("2026") has neither and is never bucketed.
    """

    start: date | None
    end: date | None
    precision: Precision
    year: int

    def __post_init__(self) -> None:
        _check_fields(self)
        if not FIRST_YEAR <= self.year <= LAST_YEAR:
            raise RecordError(f"year {self.year} is outside {FIRST_YEAR}-{LAST_YEAR}")
        if self.precision == "year":
            if self.start is not None or self.end is not None:
                raise RecordError("year precision has no start or end")
            return
        if self.start is None or self.end is None:
            raise RecordError(f"{self.precision} precision needs start and end")
        if self.end < self.start:
            raise RecordError(f"end {self.end} is before start {self.start}")
        if self.year != self.start.year:
            raise RecordError(f"year {self.year} differs from start {self.start}")
        if self.end.year > LAST_YEAR:
            raise RecordError(f"end {self.end} is after {LAST_YEAR}")
        if self.precision == "month" and (
            self.start.day != 1 or self.end != month_end(self.end.year, self.end.month)
        ):
            raise RecordError("month precision must cover whole months")

    @classmethod
    def day(cls, d: date) -> DateSpan:
        return cls(d, d, "day", d.year)

    @classmethod
    def days(cls, start: date, end: date) -> DateSpan:
        return cls(start, end, "day", start.year)

    @classmethod
    def month(cls, year: int, month: int) -> DateSpan:
        return cls(date(year, month, 1), month_end(year, month), "month", year)

    @classmethod
    def months(cls, year1: int, month1: int, year2: int, month2: int) -> DateSpan:
        return cls(date(year1, month1, 1), month_end(year2, month2), "month", year1)

    @classmethod
    def of_year(cls, year: int) -> DateSpan:
        return cls(None, None, "year", year)

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.start.isoformat() if self.start else None,
            "end_date": self.end.isoformat() if self.end else None,
            "date_precision": self.precision,
            "year": self.year,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DateSpan:
        _require_record(cls, data)
        try:
            start, end = _iso_date(data["date"]), _iso_date(data["end_date"])
            return cls(start, end, data["date_precision"], data["year"])
        except KeyError as exc:
            raise RecordError(f"DateSpan: missing {exc}") from exc


@dataclass(frozen=True, slots=True)
class InputUnit:
    """One discovered input unit and its single ledger outcome (spec §7, §9.1).

    ``unit_id`` is ``<source>:<page key>/<position>``: where the unit was
    observed, never a publisher event ID. ``duplicate_of`` names the unit of
    the same source that a ``duplicate`` unit repeats (and only such a unit).
    """

    unit_id: str
    source: str
    text: str
    outcome: Outcome
    reason: str | None
    relevance: Relevance
    leftover: str = ""
    duplicate_of: str | None = None

    def __post_init__(self) -> None:
        _check_fields(self)
        _check_unit_id(self.unit_id, self.source)
        if (self.reason == "duplicate") != (self.duplicate_of is not None):
            raise RecordError("duplicate_of is set exactly when the reason is 'duplicate'")
        if self.duplicate_of is not None:
            _check_unit_id(self.duplicate_of, self.source)
            if self.duplicate_of == self.unit_id:
                raise RecordError("a unit cannot duplicate itself")
        if self.outcome == "ignored" and self.reason not in IGNORED_REASONS:
            raise RecordError(f"ignored unit needs an allowlisted reason, got {self.reason!r}")
        if self.outcome == "parsed" and self.reason is not None:
            raise RecordError("a parsed unit has no reason")
        if self.outcome in ("partial", "unparsed") and not self.reason:
            raise RecordError(f"a {self.outcome} unit needs a reason")

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "source": self.source,
            "text": self.text,
            "outcome": self.outcome,
            "reason": self.reason,
            "relevance": self.relevance,
            "leftover": self.leftover,
            "duplicate_of": self.duplicate_of,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InputUnit:
        return _construct(cls, data)


@dataclass(frozen=True, slots=True)
class Claim:
    """One record emitted from an input unit (spec §5.2).

    ``fetched_at``, ``fallback``, ``snapshot_id`` and ``provisional`` are
    provenance stamped after parsing (``dataclasses.replace``); they are
    excluded from ``snapshot_id`` hashing (spec §5.10).
    """

    unit_id: str
    claim_id: str
    source: str
    link: str
    source_event_id: str | None
    place_raw: str
    place_id: str
    jurisdiction: str | None
    jurisdiction_kind: JurisdictionKind
    level: Level
    institution: str | None
    office_class: OfficeClass
    office_label: str
    aggregate: bool
    kind: Kind
    round: int | None
    span: DateSpan
    date_meaning: DateMeaning
    date_status: DateStatus
    date_text: str
    status_claim: StatusClaim | None
    previous_date_text: str | None
    evidence_kind: EvidenceKind
    indirect: bool
    fetched_at: datetime | None = None
    fallback: bool = False
    snapshot_id: str | None = None
    provisional: bool = False

    def __post_init__(self) -> None:
        _check_fields(self)
        _check_unit_id(self.unit_id, self.source)
        index = self.claim_id.removeprefix(f"{self.unit_id}#")
        if index == self.claim_id or not _is_index(index):
            raise RecordError(f"claim_id {self.claim_id!r} is not <unit_id>#<n>")
        if self.round is not None and self.round < 1:
            raise RecordError(f"round {self.round} is not 1 or more")
        if self.fetched_at is not None and self.fetched_at.utcoffset() is None:
            raise RecordError("fetched_at must be timezone-aware")

    @property
    def merge_id(self) -> str:
        """Identity in the merge: ``served/`` or ``provisional/`` + claim_id (spec §5.2)."""
        return f"{'provisional' if self.provisional else 'served'}/{self.claim_id}"

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "unit_id": self.unit_id,
            "claim_id": self.claim_id,
            "source": self.source,
            "link": self.link,
            "source_event_id": self.source_event_id,
            "place_raw": self.place_raw,
            "place_id": self.place_id,
            "jurisdiction": self.jurisdiction,
            "jurisdiction_kind": self.jurisdiction_kind,
            "level": self.level,
            "institution": self.institution,
            "office_class": self.office_class,
            "office_label": self.office_label,
            "aggregate": self.aggregate,
            "kind": self.kind,
            "round": self.round,
            **self.span.to_dict(),
            "date_meaning": self.date_meaning,
            "date_status": self.date_status,
            "date_text": self.date_text,
            "status_claim": self.status_claim,
            "previous_date_text": self.previous_date_text,
            "evidence_kind": self.evidence_kind,
            "indirect": self.indirect,
            "fetched_at": _utc_iso(self.fetched_at),
            "fallback": self.fallback,
            "snapshot_id": self.snapshot_id,
            "provisional": self.provisional,
        }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Claim:
        _require_record(cls, data)
        values = dict(data)
        try:
            span = DateSpan.from_dict(
                {k: values.pop(k) for k in ("date", "end_date", "date_precision", "year")}
            )
            fetched = _iso_moment(values.pop("fetched_at"))
        except KeyError as exc:
            raise RecordError(f"Claim: missing {exc}") from exc
        return _construct(cls, {**values, "span": span, "fetched_at": fetched})


ReasonCode = Literal[
    # errors (spec §9.4)
    "fetch_failed",
    "tls_error",
    "timeout",
    "dns_error",
    "http_error",
    "challenge_page",
    "api_error",
    "layout_not_recognised",
    "required_year_missing",
    "pagination_incomplete",
    "deadline",
    "unavailable",
    "ledger_mismatch",
    "discovery_mismatch",
    "worker_failed",
    "merge_failed",
    "validation_failed",
    # warnings
    "unparsed_relevant",
    "partial_relevant",
    "sudden_drop",
    "cumulative_drop",
    "coverage_gap",
    "no_cross_source_match",
    "fallback_stale",
    "served_mismatch",
    "attention_truncated",
    "ack_invalid",
    # info
    "not_published_yet",
    "count_change",
    "provisional_changes",
    "units_disappeared",
]
ReasonLevel = Literal["error", "warning", "info"]
Stage = Literal["fetch", "parse", "snapshot", "match", "run"]


def _table[V](rows: tuple[tuple[V, tuple[ReasonCode, ...]], ...]) -> dict[ReasonCode, V]:
    return {code: value for value, codes in rows for code in codes}


# Spec §9.4 and P89, P104: the level and the stage of each code.
REASON_LEVEL: Final[dict[ReasonCode, ReasonLevel]] = _table(
    (
        (
            "error",
            (
                "fetch_failed",
                "tls_error",
                "timeout",
                "dns_error",
                "http_error",
                "challenge_page",
                "api_error",
                "deadline",
                "worker_failed",
                "layout_not_recognised",
                "required_year_missing",
                "pagination_incomplete",
                "ledger_mismatch",
                "discovery_mismatch",
                "unavailable",
                "merge_failed",
                "validation_failed",
            ),
        ),
        (
            "warning",
            (
                "unparsed_relevant",
                "partial_relevant",
                "coverage_gap",
                "sudden_drop",
                "cumulative_drop",
                "fallback_stale",
                "no_cross_source_match",
                "served_mismatch",
                "attention_truncated",
                "ack_invalid",
            ),
        ),
        (
            "info",
            ("not_published_yet", "count_change", "provisional_changes", "units_disappeared"),
        ),
    )
)
REASON_STAGE: Final[dict[ReasonCode, Stage]] = _table(
    (
        (
            "fetch",
            (
                "fetch_failed",
                "tls_error",
                "timeout",
                "dns_error",
                "http_error",
                "challenge_page",
                "api_error",
                "deadline",
                "worker_failed",
            ),
        ),
        (
            "parse",
            (
                "layout_not_recognised",
                "required_year_missing",
                "pagination_incomplete",
                "ledger_mismatch",
                "discovery_mismatch",
                "unparsed_relevant",
                "partial_relevant",
                "coverage_gap",
                "not_published_yet",
            ),
        ),
        (
            "snapshot",
            (
                "unavailable",
                "sudden_drop",
                "cumulative_drop",
                "fallback_stale",
                "count_change",
                "provisional_changes",
                "units_disappeared",
            ),
        ),
        ("match", ("no_cross_source_match",)),
        (
            "run",
            (
                "merge_failed",
                "validation_failed",
                "served_mismatch",
                "attention_truncated",
                "ack_invalid",
            ),
        ),
    )
)
# Spec §9.6: no acknowledgement ever mutes these; every info code is among them.
NEVER_ACKNOWLEDGEABLE: Final[frozenset[ReasonCode]] = frozenset(
    (
        "ledger_mismatch",
        "discovery_mismatch",
        "fallback_stale",
        "served_mismatch",
        "attention_truncated",
        "ack_invalid",
        "merge_failed",
        "validation_failed",
        *(code for code, level in REASON_LEVEL.items() if level == "info"),
    )
)
MAX_DETAIL = 300


@dataclass(frozen=True, slots=True)
class Reason:
    """Why a source or run is not fully healthy (spec §9.4); ``detail`` is short free text.

    ``page`` is the page key or scope the reason concerns and ``year`` the year it concerns
    (P89); ``since`` is when a coverage gap began (P91) and is timezone-aware.
    """

    code: ReasonCode
    detail: str = ""
    page: str | None = None
    year: int | None = None
    since: datetime | None = None

    def __post_init__(self) -> None:
        _check_fields(self)
        if len(self.detail) > MAX_DETAIL:
            raise RecordError(f"Reason.detail is longer than {MAX_DETAIL} characters")
        if self.since is not None and self.since.utcoffset() is None:
            raise RecordError("Reason.since must be timezone-aware")

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "detail": self.detail,
            "page": self.page,
            "year": self.year,
            "since": _utc_iso(self.since),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Reason:
        _require_record(cls, data)
        values = dict(data)
        if "since" in values:
            values["since"] = _iso_moment(values["since"])
        return _construct(cls, values)


# --- the merge's output (spec §5.3-§5.5, §10.8) --------------------------------------------------

RejectedReason = Literal[
    "observation",
    "year_only",
    "lower_evidence",
    "old_date",  # R2-01
    "not_covering",
    "less_precise",
    "less_certain",
    "stale",
    "lower_priority",
    "provisional",
]
LegacyStatus = Literal["Upcoming", "Held", "Postponed", "Cancelled", "Disputed", "Unknown"]
DispositionKind = Literal[
    "anchor_member",
    "attached",
    "provisional",
    "umbrella_link",
    "standalone",
    "undated",
    "attention",
]
AttentionKind = Literal[
    "unparsed_unit",
    "partial_unit",
    "undated_listing",
    "unresolved_evidence",
    "provisional_change",
    "disappeared_unit",
]
ProvisionalDate = Literal["moved", "less_precise"]  # P74, D3
MAX_TYPE = 200
MAX_ATTENTION_TEXT = 300
_SHORT_ID = re.compile(r"[0-9a-f]{12}")


def _check_short_id(record: Any, name: str) -> None:
    value = getattr(record, name)
    if not _SHORT_ID.fullmatch(value):
        raise RecordError(f"{type(record).__name__}.{name} {value!r} is not 12 hex characters")


def _sorted_unique(values: tuple[str, ...]) -> bool:
    return list(values) == sorted(set(values))


def _check_matches(record: Any) -> None:
    if not _sorted_unique(record.possible_matches):
        raise RecordError(f"{type(record).__name__}.possible_matches must be sorted and unique")


@dataclass(frozen=True, slots=True)
class ChildSource:
    """One of a child's claims (spec §5.3); ``rejected_reason`` is None when selected."""

    claim: Claim
    selected: bool
    rejected_reason: RejectedReason | None

    def __post_init__(self) -> None:
        _check_fields(self)
        if self.selected != (self.rejected_reason is None):
            raise RecordError("selected and rejected_reason disagree")


@dataclass(frozen=True, slots=True)
class BibEntry:
    """One bibliography entry (spec §5.4)."""

    source: str
    link: str

    def __post_init__(self) -> None:
        _check_fields(self)


@dataclass(frozen=True, slots=True)
class Child:
    """One contest (spec §5.3)."""

    child_id: str
    place_id: str
    country: str
    country_code: str | None
    jurisdiction: str | None
    jurisdiction_kind: JurisdictionKind
    level: Level
    institution: str | None
    office_class: OfficeClass
    office_label: str
    kind: Kind
    round: int | None
    indirect: bool
    aggregate: bool  # an aggregate grouping (§10.4), never a specific contest
    span: DateSpan
    date_meaning: DateMeaning
    date_status: DateStatus
    status: LegacyStatus
    occurrence_confirmed: bool
    status_conflict: bool
    date_conflict: bool
    unverified: bool
    ambiguous: bool
    rescheduled_from: tuple[str, ...]  # D2: old dates, as the sources wrote them
    provisional_date: ProvisionalDate | None  # D3: how a provisional claim changes the date
    possible_matches: tuple[str, ...]
    sources: tuple[ChildSource, ...]

    def __post_init__(self) -> None:
        _check_fields(self)
        _check_short_id(self, "child_id")
        if self.span.precision == "year":
            raise RecordError("Child: span is never year precision")
        if sum(s.selected for s in self.sources) != 1:
            raise RecordError("Child: exactly one source is selected")
        _check_matches(self)
        if self.child_id in self.possible_matches:
            raise RecordError("Child.possible_matches names the child itself")
        if not _sorted_unique(self.rescheduled_from):
            raise RecordError("Child.rescheduled_from must be sorted and unique")
        if self.provisional_date is not None and not any(
            s.rejected_reason == "provisional" for s in self.sources
        ):
            raise RecordError("Child: provisional_date needs a provisional source")


@dataclass(frozen=True, slots=True)
class Card:
    """One card: the children that share a date (spec §5.4)."""

    group_id: str
    place_id: str
    country: str
    country_code: str | None
    level: Level
    span: DateSpan
    date_meaning: DateMeaning
    date_status: DateStatus
    status: LegacyStatus
    type: str
    children: tuple[Child, ...]
    sources: tuple[BibEntry, ...]
    umbrella_sources: tuple[BibEntry, ...]
    umbrellas: tuple[Claim, ...]  # the umbrella claims linked to any of this card's children

    def __post_init__(self) -> None:
        _check_fields(self)
        _check_short_id(self, "group_id")
        if self.span.precision == "year":
            raise RecordError("Card: span is never year precision")
        if not self.children:
            raise RecordError("Card: no children")
        if not 1 <= len(self.type) <= MAX_TYPE:
            raise RecordError(f"Card.type is 1 to {MAX_TYPE} characters")


@dataclass(frozen=True, slots=True)
class UndatedListing:
    """A contest known only by its year (spec §5.5)."""

    undated_id: str
    place_id: str
    country: str
    office_label: str
    year: int
    claims: tuple[Claim, ...]
    sources: tuple[BibEntry, ...]
    possible_matches: tuple[str, ...]

    def __post_init__(self) -> None:
        _check_fields(self)
        _check_short_id(self, "undated_id")
        _check_matches(self)
        if not self.claims or any(
            c.span.precision != "year" or c.span.year != self.year for c in self.claims
        ):
            raise RecordError("UndatedListing: every claim is year-only, of its year")


@dataclass(frozen=True, slots=True)
class AttentionItem:
    """Something a person should look at (spec §5.5)."""

    item_id: str
    kind: AttentionKind
    source: str
    link: str
    snapshot_id: str | None
    relevance: Relevance
    text: str
    reason: str
    possible_matches: tuple[str, ...]
    merge_ids: tuple[str, ...]
    undated_id: str | None

    def __post_init__(self) -> None:
        _check_fields(self)
        _check_short_id(self, "item_id")
        if len(self.text) > MAX_ATTENTION_TEXT:
            raise RecordError(f"AttentionItem.text is over {MAX_ATTENTION_TEXT} characters")
        if (self.undated_id is not None) != (self.kind == "undated_listing"):
            raise RecordError("AttentionItem: undated_id goes with kind undated_listing")
        _check_matches(self)
        if not self.merge_ids or not _sorted_unique(self.merge_ids):
            raise RecordError("AttentionItem.merge_ids must be sorted, unique and non-empty")


@dataclass(frozen=True, slots=True)
class Disposition:
    """Where one claim went (spec §10.8); ``targets`` are child ids, a listing id or an item id."""

    merge_id: str
    kind: DispositionKind
    targets: tuple[str, ...]

    def __post_init__(self) -> None:
        _check_fields(self)
        if not self.targets or not _sorted_unique(self.targets):
            raise RecordError("Disposition.targets must be sorted, unique and non-empty")
        if self.kind != "umbrella_link" and len(self.targets) != 1:
            raise RecordError(f"Disposition: {self.kind} has exactly one target")


@dataclass(frozen=True, slots=True)
class MergeResult:
    """Everything the merge returns."""

    cards: tuple[Card, ...]
    undated: tuple[UndatedListing, ...]
    attention: tuple[AttentionItem, ...]
    dispositions: tuple[Disposition, ...]

    def __post_init__(self) -> None:
        _check_fields(self)


# --- snapshot acceptance (spec §5.6, §9.3, §9.6) ---------------------------------------------

Acceptance = Literal["promoted", "quarantined", "fallback", "unavailable"]


def _check_aware(record: Any, *names: str) -> None:
    for name in names:
        moment = getattr(record, name)
        if moment is not None and moment.utcoffset() is None:
            raise RecordError(f"{type(record).__name__}.{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class DropAcceptance:
    """An ``accept_drop`` entry in effect (§9.6): it explains one drop of one scope.

    The candidate must reach both floors, ``units_seen_min`` and ``claims_min`` (P95).
    """

    source: str
    reason: Literal["sudden_drop", "cumulative_drop"]
    page: str  # the scope
    year: int | None
    units_seen_min: int
    claims_min: int
    until: datetime

    def __post_init__(self) -> None:
        _check_fields(self)
        _check_aware(self, "until")


@dataclass(frozen=True, slots=True)
class SnapshotHealth:
    """Spec §5.6 "Snapshot": what was served and how old it is (never the run's time)."""

    acceptance: Acceptance
    using_fallback: bool
    served_snapshot_id: str | None
    served_fetched_at: datetime | None
    baseline_units_seen: int | None
    comparable: bool

    def __post_init__(self) -> None:
        _check_fields(self)
        _check_aware(self, "served_fetched_at")


def _utc_iso(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _iso_date(value: object) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise RecordError(f"{value!r} is not an ISO date") from exc


def _iso_moment(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise RecordError(f"{value!r} is not an ISO timestamp") from exc


def _check_unit_id(unit_id: str, source: str) -> None:
    if not unit_id.startswith(f"{source}:") or "/" not in unit_id:
        raise RecordError(f"unit_id {unit_id!r} is not <source>:<page key>/<position>")


def _is_index(text: str) -> bool:
    """``0``, ``1``, ``2``, ...: ASCII digits without a leading zero."""
    return text.isascii() and text.isdigit() and (text == "0" or not text.startswith("0"))


def _require_record(cls: type[object], data: object) -> None:
    """A saved record is a JSON object; anything else is a RecordError, not a TypeError."""
    if not isinstance(data, dict):
        raise RecordError(f"{cls.__name__}: {type(data).__name__} is not a record")


def _construct[R](cls: type[R], values: dict[str, Any]) -> R:
    """``cls(**values)``, reporting an unknown or a missing field as a RecordError."""
    try:
        return cls(**values)
    except TypeError as exc:
        raise RecordError(f"{cls.__name__}: {exc}") from exc


@functools.cache
def _hints(cls: type) -> dict[str, Any]:
    return typing.get_type_hints(cls)


def _check_fields(record: Any) -> None:
    cls: type = type(record)
    hints = _hints(cls)
    for f in fields(record):
        value = getattr(record, f.name)
        if not _conforms(value, hints[f.name]):
            raise RecordError(f"{cls.__name__}.{f.name}: {value!r} is not {hints[f.name]}")


def _conforms(value: object, hint: Any) -> bool:
    origin = get_origin(hint)
    if origin is Literal:
        return isinstance(value, str) and value in get_args(hint)
    if origin is types.UnionType:  # typing.Union is the same class since 3.14
        return any(_conforms(value, arm) for arm in get_args(hint))
    if hint is type(None):
        return value is None
    if hint in (bool, int, str, date):
        return type(value) is hint  # True is not an int, a datetime is not a date
    if origin is tuple:
        arms = get_args(hint)
        if len(arms) == 2 and arms[1] is Ellipsis:  # tuple[X, ...]; other tuple hints fall through
            return isinstance(value, tuple) and all(_conforms(v, arms[0]) for v in value)
    if isinstance(hint, type):
        return isinstance(value, hint)
    raise TypeError(f"no runtime check for {hint!r}")
