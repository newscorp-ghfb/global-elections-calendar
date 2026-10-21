"""Acknowledgements, accepted drops and recurrence state (spec §9.6; P91, P94, P95; R16).

``known_issues.yml`` is a hand-edited list of entries; ``data/sources/<source>/health_state.json``
records when each acknowledged reason was last absent, so a reason that went away and came back
is a new incident. Both files are trusted fully or not at all: a file that cannot be read gives
an ``ack_invalid`` reason and no acknowledgement has an effect (P94). Nothing here reads the
clock; ``now`` is passed in and must be timezone-aware.
"""

import hashlib
import json
from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final, Literal, get_args

import yaml
import yaml.constructor

from elections_calendar.model import (
    MAX_DETAIL,
    NEVER_ACKNOWLEDGEABLE,
    REASON_LEVEL,
    REASON_STAGE,
    SOURCE_ORDER,
    AttentionItem,
    DropAcceptance,
    Reason,
    ReasonCode,
    RecordError,
    Stage,
    _check_aware,
    _check_fields,
    _utc_iso,
)
from elections_calendar.text import collapse_ws

MAX_ACK_LENGTH: Final = timedelta(days=14)
MAX_ACK_AHEAD: Final = timedelta(days=1)
UNIT_REASONS: Final = ("unparsed_relevant", "partial_relevant")
DROP_REASONS: Final = ("sudden_drop", "cumulative_drop")

_REASON_CODES: Final = frozenset(get_args(ReasonCode))
_UNIT_KIND: Final = {"unparsed_relevant": "unparsed_unit", "partial_relevant": "partial_unit"}
_ACK_FIELDS: Final = (
    "source",
    "reason",
    "scope",
    "explanation",
    "owner",
    "acknowledged_at",
    "expires_at",
)
_UNIT_FIELDS: Final = tuple("unit_text" if f == "scope" else f for f in _ACK_FIELDS)
_DROP_FIELDS: Final = (*_ACK_FIELDS, "accept_units_seen_min", "accept_claims_min")
_FILE_NOT_VALID: Final = "known_issues.yml is not valid YAML"
_FILE_NOT_LIST: Final = "known_issues.yml is not a list"


@dataclass(frozen=True, slots=True)
class Scope:
    """The reason's stage, year and page an entry covers."""

    stage: Stage
    year: int | None
    page: str | None

    def __post_init__(self) -> None:
        _check_fields(self)


EntryKind = Literal["acknowledgement", "unit_acknowledgement", "accept_drop"]


def _key(code: str, stage: str, year: int | None, page: str | None) -> str:
    return f"{code}|{stage}|{year if year is not None else ''}|{page or ''}"


def unit_key(reason: ReasonCode, text: str) -> str:
    """The recurrence key of one unit's text (R16): the whole text, hashed."""
    return f"unit|{reason}|{hashlib.sha256(text.encode()).hexdigest()[:16]}"


def reason_key(reason: Reason) -> str:
    """The recurrence key of a reason: its code, stage, year and page."""
    return _key(reason.code, REASON_STAGE[reason.code], reason.year, reason.page)


@dataclass(frozen=True, slots=True)
class Entry:
    """One valid entry of ``known_issues.yml``; timestamps are timezone-aware (UTC)."""

    index: int  # 1-based position in the file
    kind: EntryKind
    source: str
    reason: ReasonCode
    scope: Scope | None  # None for a unit acknowledgement
    unit_text: str | None  # only for a unit acknowledgement
    units_seen_min: int | None  # only for an accept_drop
    claims_min: int | None  # only for an accept_drop
    explanation: str
    owner: str
    acknowledged_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        _check_fields(self)
        _check_aware(self, "acknowledged_at", "expires_at")

    @property
    def key(self) -> str:
        if self.scope is None:
            return unit_key(self.reason, self.unit_text or "")
        return _key(self.reason, self.scope.stage, self.scope.year, self.scope.page)


@dataclass(frozen=True, slots=True)
class KnownIssues:
    entries: tuple[Entry, ...]  # the valid ones, in file order
    problems: tuple[Reason, ...]  # one ack_invalid per invalid entry, or one for the whole file

    def __post_init__(self) -> None:
        _check_fields(self)


@dataclass(frozen=True, slots=True)
class HealthState:
    """One source's ``health_state.json``.

    ``last_absent_at`` is sorted by key. ``problem`` is set when the file was corrupt;
    acknowledgements made before ``reset_at`` never count (P94).
    """

    last_absent_at: tuple[tuple[str, datetime], ...]
    problem: str | None = None
    reset_at: datetime | None = None

    def __post_init__(self) -> None:
        # _check_fields has no check for a tuple of pairs, so the pairs are checked here.
        pairs = self.last_absent_at
        if not isinstance(pairs, tuple) or not all(
            isinstance(p, tuple)
            and len(p) == 2
            and isinstance(p[0], str)
            and isinstance(p[1], datetime)
            and p[1].utcoffset() is not None
            for p in pairs
        ):
            raise RecordError("HealthState.last_absent_at: (key, aware datetime) pairs expected")
        keys = [k for k, _ in pairs]
        if keys != sorted(set(keys)):
            raise RecordError("HealthState.last_absent_at must be sorted by key, without repeats")
        if self.problem is not None and not isinstance(self.problem, str):
            raise RecordError("HealthState.problem must be a string or None")
        if self.reset_at is not None and not (
            isinstance(self.reset_at, datetime) and self.reset_at.utcoffset() is not None
        ):
            raise RecordError("HealthState.reset_at must be a timezone-aware datetime")


@dataclass(frozen=True, slots=True)
class Acknowledgement:
    """One reason acknowledged in this run (§5.6 ``acknowledged[]``)."""

    code: ReasonCode
    until: datetime
    stage: Stage
    year: int | None
    page: str | None
    since: datetime | None = None  # the acknowledged reason's (P91)

    def __post_init__(self) -> None:
        _check_fields(self)
        _check_aware(self, "until", "since")


# --- known_issues.yml ------------------------------------------------------------------------


class _Loader(yaml.SafeLoader):
    """A safe loader whose mappings reject a repeated key."""


def _construct_mapping(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False) -> Any:
    loader.flatten_mapping(node)
    seen: set[Hashable] = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if isinstance(key, Hashable):
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"found a repeated key {key!r}", key_node.start_mark
                )
            seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


_Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def _whole_file(detail: str) -> KnownIssues:
    return KnownIssues((), (Reason("ack_invalid", detail),))


def _moment(value: object) -> datetime | None:
    """An aware datetime in UTC, from a YAML timestamp or an ISO string; else None."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if not isinstance(value, datetime) or value.utcoffset() is None:  # a date is no datetime
        return None
    return value.astimezone(UTC)


def _whole_number(value: object) -> bool:
    return type(value) is int and value >= 0


def _text(value: object) -> str | None:
    return collapse_ws(value) or None if isinstance(value, str) else None


def _scope(value: object) -> Scope | None:
    if not isinstance(value, dict) or set(value) != {"stage", "year", "page"}:
        return None
    year, page = value["year"], value["page"]
    if year is not None and type(year) is not int:
        return None
    if page is not None and not isinstance(page, str):
        return None
    stage = value["stage"]
    if not isinstance(stage, str):
        return None
    return Scope(stage, year, page)  # type: ignore[arg-type]  # compared with the reason's stage


def _entry(index: int, raw: object, now: datetime) -> Entry | str:
    """The entry, or the first problem with it (the checks are in §9.6's order)."""
    if not isinstance(raw, dict):
        return "not a mapping"
    kind: EntryKind = "acknowledgement"
    names: tuple[str, ...] = _ACK_FIELDS
    if "unit_text" in raw:
        kind, names = "unit_acknowledgement", _UNIT_FIELDS
    elif "accept_units_seen_min" in raw or "accept_claims_min" in raw:
        kind, names = "accept_drop", _DROP_FIELDS
    for name in names:
        if name not in raw:
            return f"missing field {name}"
    for name in sorted(raw, key=str):
        if name not in names:
            return f"unknown field {name}"
    scope = None
    if kind != "unit_acknowledgement":
        scope = _scope(raw["scope"])
        if scope is None:
            return "scope must have stage, year and page"
    source, reason = raw["source"], raw["reason"]
    if source not in SOURCE_ORDER:
        return f"unknown source {source}"
    if reason not in _REASON_CODES:
        return f"unknown reason {reason}"
    if reason in NEVER_ACKNOWLEDGEABLE:
        return f"{reason} can never be acknowledged"
    if kind == "unit_acknowledgement":
        if reason not in UNIT_REASONS:
            return "unit_text is only for unparsed_relevant and partial_relevant"
    elif reason in UNIT_REASONS:
        return f"{reason} is acknowledged per unit (unit_text)"
    if kind == "accept_drop" and reason not in DROP_REASONS:
        return (
            "accept_units_seen_min and accept_claims_min "
            "are only for sudden_drop and cumulative_drop"
        )
    if kind == "accept_drop":
        for name in ("accept_units_seen_min", "accept_claims_min"):
            if not _whole_number(raw[name]):
                return f"{name} must be a whole number of at least 0"
    if scope is not None and scope.stage != REASON_STAGE[reason]:
        return f"scope.stage must be {REASON_STAGE[reason]} for {reason}"
    texts: dict[str, str] = {}
    for name in ("explanation", "owner", "unit_text"):
        if name in raw:
            text = _text(raw[name])
            if text is None:
                return f"{name} must not be empty"
            texts[name] = text
    moments: dict[str, datetime] = {}
    for name in ("acknowledged_at", "expires_at"):
        moment = _moment(raw[name])
        if moment is None:
            return f"{name} must be a timestamp with a time zone"
        moments[name] = moment
    given, expires = moments["acknowledged_at"], moments["expires_at"]
    if expires <= given:
        return "expires_at must be after acknowledged_at"
    if expires - given > MAX_ACK_LENGTH:
        return "an acknowledgement lasts at most 14 days"
    if given > now + MAX_ACK_AHEAD:
        return "acknowledged_at is more than 1 day in the future"
    return Entry(
        index=index,
        kind=kind,
        source=source,
        reason=reason,
        scope=scope,
        unit_text=texts.get("unit_text"),
        units_seen_min=raw["accept_units_seen_min"] if kind == "accept_drop" else None,
        claims_min=raw["accept_claims_min"] if kind == "accept_drop" else None,
        explanation=texts["explanation"],
        owner=texts["owner"],
        acknowledged_at=given,
        expires_at=expires,
    )


def parse_known_issues(text: str, *, now: datetime) -> KnownIssues:
    """Read ``known_issues.yml``; an invalid entry gives ``ack_invalid`` and no effect."""
    if now.utcoffset() is None:
        raise ValueError("parse_known_issues: now must be timezone-aware")
    try:
        data = yaml.load(text, Loader=_Loader)  # noqa: S506  (a SafeLoader subclass)
    except yaml.YAMLError, ValueError, OverflowError, RecursionError:
        return _whole_file(_FILE_NOT_VALID)
    if data is None:
        return KnownIssues((), ())
    if not isinstance(data, list):
        return _whole_file(_FILE_NOT_LIST)
    entries: list[Entry] = []
    problems: list[Reason] = []
    for index, raw in enumerate(data, start=1):
        result = _entry(index, raw, now)
        if isinstance(result, Entry):
            entries.append(result)
        else:
            detail = collapse_ws(f"known_issues.yml entry {index}: {result}")
            problems.append(Reason("ack_invalid", detail[:MAX_DETAIL]))
    return KnownIssues(tuple(entries), tuple(problems))


def load_known_issues(path: Path, *, now: datetime) -> KnownIssues:
    """A missing file has no entries; one that cannot be decoded is not valid YAML.

    Other ``OSError`` (a directory at the path, no permission) propagate.
    """
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return KnownIssues((), ())
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return _whole_file(_FILE_NOT_VALID)
    return parse_known_issues(text, now=now)


# --- health_state.json -----------------------------------------------------------------------


def load_health_state(path: Path) -> HealthState:
    """A missing file is an empty state; a file that cannot be read gives a ``problem``."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return HealthState(())
    try:
        data = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError, ValueError, RecursionError:
        return HealthState((), "not JSON")
    if (
        not isinstance(data, dict)
        or set(data) != {"last_absent_at", "reset_at"}
        or not isinstance(data["last_absent_at"], dict)
    ):
        return HealthState((), "shape")
    pairs: list[tuple[str, datetime]] = []
    for key in sorted(data["last_absent_at"]):
        moment = _moment(data["last_absent_at"][key])
        if moment is None:
            return HealthState((), f"timestamp of {key}")
        pairs.append((key, moment))
    reset = data["reset_at"]
    reset_at = None if reset is None else _moment(reset)
    if reset is not None and reset_at is None:
        return HealthState((), "timestamp of reset_at")
    return HealthState(tuple(pairs), None, reset_at)


def health_state_to_dict(state: HealthState) -> dict[str, Any]:
    return {
        "last_absent_at": {key: _utc_iso(at) for key, at in state.last_absent_at},
        "reset_at": _utc_iso(state.reset_at),
    }


def state_problem_reason(state: HealthState) -> Reason | None:
    if state.problem is None:
        return None
    return Reason("ack_invalid", f"health_state.json is corrupt: {state.problem}"[:MAX_DETAIL])


# --- effect ----------------------------------------------------------------------------------


def in_effect(entry: Entry, state: HealthState, now: datetime) -> bool:
    """Active at ``now``, the state readable, the key not absent since, not before a reset."""
    if not entry.acknowledged_at <= now < entry.expires_at or state.problem is not None:
        return False
    if state.reset_at is not None and state.reset_at > entry.acknowledged_at:
        return False
    return not any(k == entry.key and at > entry.acknowledged_at for k, at in state.last_absent_at)


def not_yet_active(issues: KnownIssues, now: datetime) -> tuple[Entry, ...]:
    return tuple(e for e in issues.entries if e.acknowledged_at > now)


def relevance_reasons(items: Sequence[AttentionItem]) -> tuple[Reason, ...]:
    unparsed = sum(i.kind == "unparsed_unit" for i in items)
    partial = sum(i.kind == "partial_unit" for i in items)
    reasons: list[Reason] = []
    if unparsed:
        reasons.append(Reason("unparsed_relevant", f"relevant units unparsed: {unparsed}"))
    if partial:
        reasons.append(Reason("partial_relevant", f"relevant units partly parsed: {partial}"))
    return tuple(reasons)


def _unit_until(
    reason: Reason, source: str, items: Sequence[AttentionItem], live: Sequence[Entry]
) -> datetime | None:
    """The earliest, over the units, of each unit's latest covering expiry; None if one is open."""
    kind = _UNIT_KIND[reason.code]
    untils: list[datetime] = []
    for unit in (i for i in items if i.source == source and i.kind == kind):
        covering = [
            e.expires_at for e in live if e.reason == reason.code and e.unit_text == unit.unit_text
        ]
        if not covering:
            return None
        untils.append(max(covering))
    return min(untils) if untils else None  # no unit, no acknowledgement


def acknowledge(
    source: str,
    reasons: Sequence[Reason],
    items: Sequence[AttentionItem],
    issues: KnownIssues,
    state: HealthState,
    now: datetime,
) -> tuple[Acknowledgement, ...]:
    """The reasons of ``source`` that an entry in effect acknowledges, in the order given."""
    live = [e for e in issues.entries if e.source == source and in_effect(e, state, now)]
    scoped = [e for e in live if e.kind != "unit_acknowledgement"]
    units = [e for e in live if e.kind == "unit_acknowledgement"]
    result: list[Acknowledgement] = []
    for reason in reasons:
        if REASON_LEVEL[reason.code] == "info":
            continue
        until: datetime | None
        if reason.code in UNIT_REASONS:
            until = _unit_until(reason, source, items, units)
        else:
            key = reason_key(reason)
            expiries = [
                e.expires_at
                for e in scoped
                if e.key == key and (reason.since is None or e.acknowledged_at >= reason.since)
            ]
            until = max(expiries) if expiries else None
        if until is not None:
            result.append(
                Acknowledgement(
                    reason.code,
                    until,
                    REASON_STAGE[reason.code],
                    reason.year,
                    reason.page,
                    reason.since,
                )
            )
    return tuple(result)


def drop_acceptances(
    issues: KnownIssues, states: Mapping[str, HealthState], now: datetime
) -> tuple[DropAcceptance, ...]:
    """Each ``accept_drop`` entry in effect, in file order.

    An entry whose source has no state, or whose scope has no page, gives none.
    """
    result: list[DropAcceptance] = []
    for e in issues.entries:
        state = states.get(e.source)
        if e.kind != "accept_drop" or state is None or not in_effect(e, state, now):
            continue
        assert e.scope is not None and e.units_seen_min is not None and e.claims_min is not None
        if e.scope.page is None:
            continue
        reason: Literal["sudden_drop", "cumulative_drop"] = (
            "sudden_drop" if e.reason == "sudden_drop" else "cumulative_drop"
        )
        result.append(
            DropAcceptance(
                e.source,
                reason,
                e.scope.page,
                e.scope.year,
                e.units_seen_min,
                e.claims_min,
                e.expires_at,
            )
        )
    return tuple(result)


def present_keys(reasons: Sequence[Reason], items: Sequence[AttentionItem]) -> frozenset[str]:
    """The recurrence keys present in a run: every reason, and every unparsed or partial unit."""
    keys = {reason_key(r) for r in reasons}
    for i in items:
        if i.kind in ("unparsed_unit", "partial_unit") and i.unit_text is not None:
            code: ReasonCode = (
                "unparsed_relevant" if i.kind == "unparsed_unit" else "partial_relevant"
            )
            keys.add(unit_key(code, i.unit_text))
    return frozenset(keys)


def next_health_state(
    previous: HealthState,
    source: str,
    issues: KnownIssues,
    present: frozenset[str],
    now: datetime,
) -> HealthState:
    """The state to write after a published generation: only keys that unexpired entries name."""
    named = {e.key for e in issues.entries if e.source == source and e.expires_at > now}
    before = dict(previous.last_absent_at)
    pairs: list[tuple[str, datetime]] = []
    for key in sorted(named):
        if key not in present:
            pairs.append((key, now))
        elif key in before:
            pairs.append((key, before[key]))
    # The lost history could have voided an old acknowledgement (review P4-05).
    reset_at = now if previous.problem is not None else previous.reset_at
    return HealthState(tuple(pairs), None, reset_at)
