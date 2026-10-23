"""Acknowledgements, accepted drops and recurrence state (spec §9.6; P91, P94, P95; R16).

``known_issues.yml`` is a hand-edited list of entries; ``data/sources/<source>/health_state.json``
records when each acknowledged reason was last absent, so a reason that went away and came back
is a new incident. Both files are trusted fully or not at all: a file that cannot be read gives
an ``ack_invalid`` reason and no acknowledgement has an effect (P94). Nothing here reads the
clock; ``now`` is passed in and must be timezone-aware.
"""

import hashlib
import json
from collections.abc import Collection, Hashable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final, Literal, cast, get_args

import yaml
import yaml.constructor

from elections_calendar.model import (
    FIRST_YEAR,
    LAST_YEAR,
    MAX_DETAIL,
    NEVER_ACKNOWLEDGEABLE,
    REASON_LEVEL,
    REASON_STAGE,
    SOURCE_ORDER,
    AttentionItem,
    Claim,
    DropAcceptance,
    MergeResult,
    Reason,
    ReasonCode,
    RecordError,
    Stage,
    _check_aware,
    _check_fields,
    _utc_iso,
)
from elections_calendar.text import collapse_ws
from elections_calendar.window import Window

MAX_ACK_LENGTH: Final = timedelta(days=14)
MAX_ACK_AHEAD: Final = timedelta(days=1)
MAX_FLOOR: Final = 1_000_000  # accept_units_seen_min and accept_claims_min
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
MIN_ELIGIBLE: Final = 5  # a match diagnostic says something from this many contests
MIN_PEERS: Final = 2  # ... and from this many other sources

Severity = Literal["ok", "warning", "error"]
Verdict = Literal["green", "red"]


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
    # A page of None and of "" share a key: the same intent, so the sharing is harmless.
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
    try:
        return value.astimezone(UTC)
    except OverflowError:  # year 9999 with a negative offset, year 1 with a positive one
        return None


def _show(value: object) -> str:
    """A YAML value as it may appear in a message: a string, a small int, else its type name.

    Never calls ``str`` or ``repr`` on a huge int or an alias-heavy container.
    """
    if isinstance(value, str):
        return value if _encodable(value) else _escaped(value)
    if type(value) is int and abs(value) < 10**20:
        return str(value)
    return type(value).__name__


def _encodable(text: str) -> bool:
    """Whether ``text`` writes as UTF-8; a lone surrogate (YAML can escape one) does not."""
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _escaped(text: str) -> str:
    """``text`` as ASCII JSON cut to 80 characters: safe to echo in a message."""
    return json.dumps(text)[:80]


def _require_aware(now: datetime) -> None:
    if now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")


def _whole_number(value: object) -> bool:
    return type(value) is int and value >= 0


def _text(value: object) -> str | None:
    return collapse_ws(value) or None if isinstance(value, str) and _encodable(value) else None


def _scope(value: object) -> tuple[str, int | None, str | None] | None:
    """The raw stage, year and page of a well-shaped scope; ``Scope`` is built after the checks."""
    if not isinstance(value, dict) or set(value) != {"stage", "year", "page"}:
        return None
    stage, year, page = value["stage"], value["year"], value["page"]
    if year is not None and type(year) is not int:
        return None
    if page is not None and not (isinstance(page, str) and _encodable(page)):
        return None
    if not isinstance(stage, str):
        return None
    return stage, year, page


def _entry(index: int, raw: object, now: datetime) -> Entry | str:
    """The entry, or the first problem with it (the checks are in the plan's table order)."""
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
    for name in sorted(raw, key=_show):
        if name not in names:
            return f"unknown field {_show(name)}"
    shape = None
    if kind != "unit_acknowledgement":
        shape = _scope(raw["scope"])
        if shape is None:
            return "scope must have stage, year and page"
        if shape[1] is not None and not FIRST_YEAR <= shape[1] <= LAST_YEAR:
            return f"scope.year must be from {FIRST_YEAR} to {LAST_YEAR}"
    source, reason = raw["source"], raw["reason"]
    if source not in SOURCE_ORDER:
        return f"unknown source {_show(source)}"
    if not isinstance(reason, str) or reason not in _REASON_CODES:
        return f"unknown reason {_show(reason)}"
    reason = cast(ReasonCode, reason)
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
            if raw[name] > MAX_FLOOR:
                return f"{name} must be at most {MAX_FLOOR}"
    if shape is not None and shape[0] != REASON_STAGE[reason]:
        return f"scope.stage must be {REASON_STAGE[reason]} for {reason}"
    scope = None if shape is None else Scope(REASON_STAGE[reason], shape[1], shape[2])
    if kind == "accept_drop" and shape is not None and shape[2] is None:
        return "an accept_drop needs scope.page"
    texts: dict[str, str] = {}
    for name in ("explanation", "owner", "unit_text"):
        if name in raw:
            text = _text(raw[name])
            if text is None:
                if isinstance(raw[name], str) and not _encodable(raw[name]):
                    return f"{name} must be text that writes as UTF-8"
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
    _require_aware(now)
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
    _require_aware(now)
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


class _RepeatedKey(Exception):
    pass


def _no_repeats(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """A repeated key could hide a later absence (last wins), so it is a corrupt file."""
    if len({k for k, _ in pairs}) != len(pairs):
        raise _RepeatedKey
    return dict(pairs)


def load_health_state(path: Path, *, now: datetime) -> HealthState:
    """A missing file is an empty state; a file that cannot be read gives a ``problem``.

    A time later than ``now`` is a problem too (P110): no run writes one, and a future absence
    would void acknowledgements made before it. A time equal to ``now`` is valid.
    """
    _require_aware(now)
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return HealthState(())
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_repeats)
    except _RepeatedKey:
        return HealthState((), "shape")
    except UnicodeDecodeError, ValueError, RecursionError:
        return HealthState((), "not JSON")
    if (
        not isinstance(data, dict)
        or set(data) != {"last_absent_at", "reset_at"}
        or not isinstance(data["last_absent_at"], dict)
    ):
        return HealthState((), "shape")
    pairs: list[tuple[str, datetime]] = []
    if not all(_encodable(key) for key in data["last_absent_at"]):
        return HealthState((), "shape")
    for key in sorted(data["last_absent_at"]):
        moment = _moment(data["last_absent_at"][key])
        if moment is None:
            return HealthState((), f"timestamp of {_escaped(key)}")
        if moment > now:
            return HealthState((), f"timestamp of {_escaped(key)} is after the run")
        pairs.append((key, moment))
    reset = data["reset_at"]
    reset_at = None if reset is None else _moment(reset)
    if reset is not None and reset_at is None:
        return HealthState((), "timestamp of reset_at")
    if reset_at is not None and reset_at > now:
        return HealthState((), "timestamp of reset_at is after the run")
    return HealthState(tuple(pairs), None, reset_at)


def health_state_to_dict(state: HealthState) -> dict[str, Any]:
    return {
        "last_absent_at": {key: _utc_iso(at) for key, at in state.last_absent_at},
        "reset_at": _utc_iso(state.reset_at),
    }


def state_problem_reason(state: HealthState) -> Reason | None:
    if state.problem is None:
        return None
    detail = collapse_ws(f"health_state.json is corrupt: {state.problem}")
    return Reason("ack_invalid", detail[:MAX_DETAIL])


# --- effect ----------------------------------------------------------------------------------


def in_effect(entry: Entry, state: HealthState, now: datetime) -> bool:
    """Active at ``now``, the state readable, the key not absent since, not before a reset."""
    _require_aware(now)
    if not entry.acknowledged_at <= now < entry.expires_at or state.problem is not None:
        return False
    if state.reset_at is not None and state.reset_at > entry.acknowledged_at:
        return False
    key = entry.key
    return not any(k == key and at > entry.acknowledged_at for k, at in state.last_absent_at)


def not_yet_active(issues: KnownIssues, now: datetime) -> tuple[Entry, ...]:
    _require_aware(now)
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
    _require_aware(now)
    live = [e for e in issues.entries if e.source == source and in_effect(e, state, now)]
    scoped = [e for e in live if e.kind != "unit_acknowledgement"]
    units = [e for e in live if e.kind == "unit_acknowledgement"]
    result: list[Acknowledgement] = []
    for reason in reasons:
        if reason.code in NEVER_ACKNOWLEDGEABLE or REASON_LEVEL[reason.code] == "info":
            continue  # the loader rejects such entries; a hand-built Entry must not mute them
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

    An entry whose source has no state gives none (a loosening is never assumed). The loader
    guarantees every ``accept_drop`` scope has a page.
    """
    _require_aware(now)
    result: list[DropAcceptance] = []
    for e in issues.entries:
        state = states.get(e.source)
        if e.kind != "accept_drop" or state is None or not in_effect(e, state, now):
            continue
        assert e.scope is not None and e.units_seen_min is not None and e.claims_min is not None
        assert e.scope.page is not None
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
    """The state to write after a published generation.

    A key that an unexpired entry names is recorded absent now, or keeps its previous pair when
    present. Every other previous pair is carried unchanged until it is older than
    ``MAX_ACK_LENGTH``: an entry valid now was acknowledged within that time, and ``in_effect``
    needs a recurrence after ``acknowledged_at``, so an older pair can void no entry.
    The file stays bounded: a key enters only while named and leaves 14 days later.
    """
    _require_aware(now)
    named = {e.key for e in issues.entries if e.source == source and e.expires_at > now}
    before = dict(previous.last_absent_at)
    pairs: list[tuple[str, datetime]] = []
    for key in sorted(named | before.keys()):
        if key in named:
            if key not in present:
                pairs.append((key, now))
            elif key in before:
                pairs.append((key, before[key]))
        elif before[key] > now - MAX_ACK_LENGTH:
            pairs.append((key, before[key]))
    # The lost history could have voided an old acknowledgement (review P4-05).
    reset_at = now if previous.problem is not None else previous.reset_at
    return HealthState(tuple(pairs), None, reset_at)


# --- match diagnostic, severity and verdict (spec §5.6, §9.4, §9.5) ------------------------------


@dataclass(frozen=True, slots=True)
class MatchDiagnostic:
    """How many of a source's in-window national contests another source also lists."""

    eligible: int
    peers_fresh: int
    matched: int
    unmatched: int
    informative: bool

    def __post_init__(self) -> None:
        _check_fields(self)


def match_diagnostic(
    result: MergeResult,
    claims: Sequence[Claim],
    source: str,
    *,
    fresh: Collection[str],
    window: Window,
) -> MatchDiagnostic:
    """The diagnostic of ``source`` over a merge of ``claims``; ``fresh`` are the sources whose
    candidate was promoted this run.

    Eligible: a national, non-aggregate child of an in-window card with a claim of ``source``
    that is not provisional. A peer is another fresh source with any claim in ``claims`` at an
    eligible child's place. A child is matched when a non-provisional claim of a fresh peer is
    among its sources.
    """
    eligible = [
        child
        for card in result.cards
        if window.bucket(card.span) is not None
        for child in card.children
        if child.level == "national"
        and not child.aggregate
        and any(s.claim.source == source and not s.claim.provisional for s in child.sources)
    ]
    places = {child.place_id for child in eligible}
    peers = {
        c.source
        for c in claims
        if c.source != source and c.source in fresh and c.place_id in places
    }
    matched = sum(
        any(
            s.claim.source != source and s.claim.source in fresh and not s.claim.provisional
            for s in child.sources
        )
        for child in eligible
    )
    return MatchDiagnostic(
        eligible=len(eligible),
        peers_fresh=len(peers),
        matched=matched,
        unmatched=len(eligible) - matched,
        informative=len(peers) >= MIN_PEERS and len(eligible) >= MIN_ELIGIBLE,
    )


def match_reason(diagnostic: MatchDiagnostic) -> Reason | None:
    if diagnostic.informative and diagnostic.matched == 0:
        return Reason(
            "no_cross_source_match",
            f"no other source lists any of its {diagnostic.eligible} in-window national contests",
        )
    return None


def source_reasons(
    decision_reasons: Sequence[Reason],
    items: Sequence[AttentionItem],
    match: MatchDiagnostic,
    state: HealthState,
) -> tuple[Reason, ...]:
    """The decision's reasons, then those of the unit items, the match and the state file."""
    later = (match_reason(match), state_problem_reason(state))
    return (
        *decision_reasons,
        *relevance_reasons(items),
        *(r for r in later if r is not None),
    )


def severity(reasons: Sequence[Reason]) -> Severity:
    levels = {REASON_LEVEL[r.code] for r in reasons}
    if "error" in levels:
        return "error"
    return "warning" if "warning" in levels else "ok"


def _covers(a: Acknowledgement, r: Reason) -> bool:
    return (
        a.code == r.code
        and a.stage == REASON_STAGE[r.code]
        and a.year == r.year
        and a.page == r.page
        and a.since == r.since
    )


def unacknowledged(
    reasons: Sequence[Reason], acknowledged: Sequence[Acknowledgement]
) -> tuple[Reason, ...]:
    """The error and warning reasons that no acknowledgement covers, in order (P91).

    An acknowledgement covers a reason of the same code, stage, year, page and ``since``.
    """
    return tuple(
        r
        for r in reasons
        if REASON_LEVEL[r.code] != "info" and not any(_covers(a, r) for a in acknowledged)
    )


def verdict(open_reasons: Sequence[Reason]) -> Verdict:
    """Red when any reason of level error or warning is open."""
    return "red" if any(REASON_LEVEL[r.code] != "info" for r in open_reasons) else "green"
