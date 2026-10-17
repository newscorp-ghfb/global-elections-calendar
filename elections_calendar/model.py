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
import types
import typing
from dataclasses import dataclass, fields
from datetime import UTC, date, datetime
from typing import Any, Literal, get_args, get_origin

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
    "header_row", "year_heading", "empty_cell", "container_item", "appointed_chamber", "duplicate"
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
    observed, never a publisher event ID.
    """

    unit_id: str
    source: str
    text: str
    outcome: Outcome
    reason: str | None
    relevance: Relevance
    leftover: str = ""

    def __post_init__(self) -> None:
        _check_fields(self)
        _check_unit_id(self.unit_id, self.source)
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
    if isinstance(hint, type):
        return isinstance(value, hint)
    raise TypeError(f"no runtime check for {hint!r}")
