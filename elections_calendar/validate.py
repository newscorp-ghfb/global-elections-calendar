"""The checks a feed or a status must pass before it is published (spec §11.3; P96, P104).

``validate_feed`` returns every problem it finds, each prefixed by its check: ``json``,
``schema``, ``legacy``, ``invariant``, ``size``, ``timestamp`` or ``served``. It never raises on
the content of the bytes, whatever their shape, and it never passes a value it cannot read: an
impossible timestamp or day is a problem, not a skip. ``validate`` is a sibling of ``feed`` and
``publish``: it imports neither, so its limit on attention items has its own constant (a test
keeps it equal to the feed's). Nothing here reads the clock: ``wall_clock`` is passed in.
"""

import calendar
import json
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any, Final, get_args

from jsonschema import Draft202012Validator, ValidationError, validators

from elections_calendar.model import LegacyStatus, _utc_iso

FEED_MAX_BYTES: Final = 2_000_000
MAX_AHEAD: Final = timedelta(minutes=10)
MAX_ATTENTION_ITEMS: Final = 500  # feed.MAX_FEED_ITEMS; a test keeps the two equal
SCHEMAS: Final = Path(__file__).resolve().parents[1] / "schemas"
FEED_SCHEMA: Final = SCHEMAS / "feed-v2.schema.json"
STATUS_SCHEMA: Final = SCHEMAS / "status-v1.schema.json"
MAX_PROBLEM: Final = 300

_DAY: Final = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_STAMP: Final = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z")
_MONTH: Final = re.compile(r"[0-9]{4}-[0-9]{2}")
_LEGACY_STATUS: Final = frozenset(get_args(LegacyStatus))
_SURROGATE: Final = re.compile(r"[\ud800-\udfff]")
_HASH: Final = re.compile(r"[0-9a-f]{64}")
_LEGACY_REQUIRED: Final = frozenset({"current_month", "errors", "generated_at", "months"})
_LEGACY_KEYS: Final = _LEGACY_REQUIRED | {"published_at", "republished_from_sha256"}


@dataclass(frozen=True, slots=True)
class ServedCheck:
    """What the pipeline found when it re-checked one source's served snapshot (§11.3 check 6)."""

    source: str
    snapshot_id: str | None  # None for an unavailable source: nothing is served
    ledger_ok: bool
    discovery_ok: bool


@cache
def _ecma(pattern: str) -> re.Pattern[str]:
    """``pattern`` as ECMA-262 reads it without the ``m`` flag: a final unescaped ``$`` is the end.

    Python's ``$`` also matches just before a final newline, so it is read as ``\\Z``. A test keeps
    every schema pattern to one ``$``, at the end. The ``$`` is an anchor when an even number of
    backslashes (zero included) precede it.
    """
    body = pattern[:-1]
    backslashes = len(body) - len(body.rstrip("\\"))
    if pattern.endswith("$") and backslashes % 2 == 0:
        return re.compile(body + "\\Z")
    return re.compile(pattern)


def _pattern(validator: Any, pattern: str, instance: Any, schema: Any) -> Iterator[Any]:
    if isinstance(instance, str) and _ecma(pattern).search(instance) is None:
        yield ValidationError(f"{instance!r} does not match {pattern!r}")


_SchemaValidator: Final = validators.extend(Draft202012Validator, {"pattern": _pattern})


@cache
def _validator(path: Path) -> Draft202012Validator:
    return _SchemaValidator(json.loads(path.read_text(encoding="utf-8")))


def _constant(name: str) -> Any:
    raise ValueError(f"{name} is not JSON")


def _lone_surrogate(doc: Any) -> bool:
    """Whether a key or a string anywhere in ``doc`` holds a lone surrogate (not UTF-8 text)."""
    todo = [doc]
    while todo:
        item = todo.pop()
        if isinstance(item, str):
            if _SURROGATE.search(item):
                return True
        elif isinstance(item, dict):
            todo.extend(item.keys())
            todo.extend(item.values())
        elif isinstance(item, list):
            todo.extend(item)
    return False


def _load(data: bytes) -> tuple[bool, Any]:
    """``(True, document)`` when ``data`` is UTF-8 JSON that any JSON reader accepts, else not.

    ``NaN``, ``Infinity`` and ``-Infinity`` are not JSON, and a lone surrogate (JSON's escape
    for U+D800, say) is not text that can be written as UTF-8: both make the bytes unloadable.
    """
    try:
        doc = json.loads(data.decode("utf-8"), parse_constant=_constant)
    except (ValueError, RecursionError):
        return False, None
    if _lone_surrogate(doc):
        return False, None
    return True, doc


def _path_key(error: Any) -> tuple[tuple[int, int, str], ...]:
    return tuple(
        (0, p, "") if isinstance(p, int) else (1, 0, str(p)) for p in error.absolute_path
    )


def _schema_problems(doc: Any, path: Path) -> list[str]:
    errors = sorted(_validator(path).iter_errors(doc), key=_path_key)
    return [
        "schema: /{}: {}".format("/".join(str(p) for p in e.absolute_path), e.message)[:MAX_PROBLEM]
        for e in errors
    ]


def validate_status(data: bytes) -> tuple[str, ...]:
    """The problems of a ``status.json``, or ``()``."""
    ok, doc = _load(data)
    if not ok:
        return ("json: not UTF-8 JSON",)
    return tuple(_schema_problems(doc, STATUS_SCHEMA))


# --- tolerant readers: the checks after the schema must survive any shape --------------------


def _dicts(value: Any) -> list[dict[str, Any]]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _cards(doc: Any) -> Iterator[tuple[str, dict[str, Any]]]:
    months = doc.get("months") if isinstance(doc, dict) else None
    if isinstance(months, dict):
        for month, cards in months.items():
            for card in _dicts(cards):
                yield str(month), card


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _day(value: Any) -> date | None:
    if isinstance(value, str) and _DAY.fullmatch(value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _legacy(doc: Any) -> list[str]:
    problems: list[str] = []
    for _, card in _cards(doc):
        who = f"legacy: {_text(card.get('group_id')) or '?'}: "
        if _day(card.get("date")) is None:
            problems.append(f"{who}date {card.get('date')!r} is not YYYY-MM-DD")
        if not (isinstance(card.get("country"), str) and card["country"]):
            problems.append(f"{who}country is empty")
        if not isinstance(card.get("type"), str):
            problems.append(f"{who}type is not a string")
        status = card.get("status")
        if not isinstance(status, str) or status not in _LEGACY_STATUS:
            problems.append(f"{who}status {status!r} is not a legacy value")
        sources = card.get("sources")
        names: list[Any] = []
        links: list[Any] = []
        well_formed = isinstance(sources, list)
        for source in sources if isinstance(sources, list) else []:
            if not (
                isinstance(source, dict)
                and isinstance(source.get("name"), str)
                and isinstance(source.get("link"), str)
            ):
                well_formed = False
                continue
            names.append(source["name"])
            links.append(source["link"])
        if not well_formed:
            problems.append(f"{who}sources is not a list of name and link strings")
        if card.get("source_names") != names:
            problems.append(f"{who}source_names differ from the names of sources")
        if card.get("links") != links:
            problems.append(f"{who}links differ from the links of sources")
    return [p[:MAX_PROBLEM] for p in problems]


def _month(key: str) -> tuple[int, int] | None:
    """``(year, month)`` of a ``YYYY-MM`` key naming a real month, else None."""
    if not _MONTH.fullmatch(key):
        return None
    year, month = int(key[:4]), int(key[5:])
    return (year, month) if year >= 1 and 1 <= month <= 12 else None


def _first_window_month(months: list[str], start: date, end: date) -> str | None:
    for key in months:
        parsed = _month(key)
        if parsed is None:
            continue
        year, month = parsed
        first, last = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
        if start <= last and end >= first:
            return key
    return None


def _repeats(label: str, ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in ids:
        if value in seen and f"invariant: {label} {value} appears twice" not in out:
            out.append(f"invariant: {label} {value} appears twice")
        seen.add(value)
    return out


def _invariants(doc: Any) -> list[str]:
    if not isinstance(doc, dict):
        return []
    problems: list[str] = []
    window = doc.get("window")
    months = [m for m in window.get("months", []) if isinstance(m, str)] if isinstance(
        window, dict
    ) and isinstance(window.get("months"), list) else []
    problems += [
        f"invariant: window month {m!r} is not a real YYYY-MM month"
        for m in months
        if _month(m) is None
    ]
    cards = list(_cards(doc))
    kids = [(card, c) for _, card in cards for c in _dicts(card.get("children"))]
    listings = _dicts(doc.get("undated"))
    items = _dicts(doc.get("attention_items"))
    problems += _repeats("group_id", [_text(c.get("group_id")) for _, c in cards])
    problems += _repeats("child_id", [_text(c.get("child_id")) for _, c in kids])
    problems += _repeats("undated_id", [_text(u.get("undated_id")) for u in listings])
    problems += _repeats("item_id", [_text(i.get("item_id")) for i in items])

    for month, card in cards:
        start, end = _day(card.get("date")), _day(card.get("end_date"))
        if end is None:
            problems.append(
                f"invariant: card {_text(card.get('group_id'))} end_date "
                f"{card.get('end_date')!r} is not a real YYYY-MM-DD day"
            )
        if start is None or end is None:
            continue  # a bad date is a legacy problem
        expected = _first_window_month(months, start, end)
        if expected != month:
            where = "outside the window" if expected is None else f"belongs in {expected}"
            problems.append(
                f"invariant: card {_text(card.get('group_id'))} is in month {month}, but {where}"
            )

    child_ids = {_text(c.get("child_id")) for _, c in kids}
    for owner, record in (
        *((f"child {_text(c.get('child_id'))}", c) for _, c in kids),
        *((f"listing {_text(u.get('undated_id'))}", u) for u in listings),
        *((f"item {_text(i.get('item_id'))}", i) for i in items),
    ):
        matches = record.get("possible_matches")
        for match in matches if isinstance(matches, list) else []:
            if not isinstance(match, str) or match not in child_ids:
                problems.append(f"invariant: {owner} has possible_matches {match!r}, not a child")

    undated_ids = {_text(u.get("undated_id")) for u in listings}
    for item in items:
        link = item.get("undated_id")
        if link is not None and (not isinstance(link, str) or link not in undated_ids):
            problems.append(
                f"invariant: item {_text(item.get('item_id'))} has undated_id {link!r}, "
                "not in undated"
            )
    linked = {i.get("undated_id") for i in items if isinstance(i.get("undated_id"), str)}
    for listing in listings:  # the feed keeps a listing only for an attention item that links it
        if listing.get("undated_id") not in linked:
            problems.append(
                f"invariant: listing {_text(listing.get('undated_id'))} has no attention item"
            )

    for _, card in cards:
        mine = {_text(c.get("child_id")) for c in _dicts(card.get("children"))}
        for umbrella in _dicts(card.get("umbrellas")):
            listed = umbrella.get("children")
            for child in listed if isinstance(listed, list) else []:
                if not isinstance(child, str) or child not in mine:
                    problems.append(
                        f"invariant: umbrella of card {_text(card.get('group_id'))} "
                        f"names child {child!r}, which is not on the card"
                    )

    if len(items) > MAX_ATTENTION_ITEMS:
        problems.append(
            f"invariant: {len(items)} attention items, at most {MAX_ATTENTION_ITEMS} allowed"
        )
    for card, child in kids:
        chosen = sum(1 for s in _dicts(child.get("sources")) if s.get("selected") is True)
        if chosen != 1:
            problems.append(
                f"invariant: child {_text(child.get('child_id'))} has {chosen} selected sources, "
                f"not one (card {_text(card.get('group_id'))})"
            )
    return [p[:MAX_PROBLEM] for p in problems]


def _moment(value: Any) -> datetime | None:
    if isinstance(value, str) and _STAMP.fullmatch(value):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _timestamps(doc: Any, wall_clock: datetime) -> list[str]:
    if not isinstance(doc, dict):
        return []
    problems = []
    for field in ("generated_at", "published_at"):
        moment = _moment(doc.get(field))
        if moment is None:
            problems.append(
                f"timestamp: {field} {doc.get(field)!r} is not a real UTC timestamp"[:MAX_PROBLEM]
            )
        elif moment - wall_clock > MAX_AHEAD:
            problems.append(
                f"timestamp: {field} is {doc[field]}, more than 10 minutes ahead of "
                f"{_utc_iso(wall_clock)}"
            )
    return problems


def _served(doc: Any, served: Sequence[ServedCheck]) -> list[str]:
    if not isinstance(doc, dict):
        return []
    checks = {c.source: c for c in served}
    problems: list[str] = []
    seen: set[str] = set()
    for entry in _dicts(doc.get("source_health")):
        source = _text(entry.get("source"))
        seen.add(source)
        check = checks.get(source)
        if check is None:
            problems.append(f"served: {source}: no served check was given")
            continue
        snapshot = entry.get("snapshot")
        listed = snapshot.get("served_snapshot_id") if isinstance(snapshot, dict) else None
        if listed != check.snapshot_id:
            problems.append(
                f"served: {source}: the feed lists snapshot {listed}, "
                f"but {check.snapshot_id} is served"
            )
        if not check.ledger_ok:
            problems.append(f"served: {source}: the ledger check of the served snapshot failed")
        if not check.discovery_ok:
            problems.append(f"served: {source}: the discovery check of the served snapshot failed")
    problems += [
        f"served: {source}: a served check was given for a source that is not in the feed"
        for source in checks
        if source not in seen
    ]
    return problems


def _real_moment(value: Any, wall_clock: datetime) -> str | None:
    """Why ``value`` is not a real UTC timestamp no more than ``MAX_AHEAD`` ahead, or None."""
    moment = _moment(value)
    if moment is None:
        return f"{value!r} is not a real UTC timestamp"
    if moment - wall_clock > MAX_AHEAD:
        return f"{value} is more than 10 minutes ahead of {_utc_iso(wall_clock)}"
    return None


def legacy_feed_problems(data: bytes, *, wall_clock: datetime) -> tuple[str, ...]:
    """The problems of a v1 ``elections.json`` as v1.0.2 reads it; each starts ``legacy: ``.

    The top-level keys are ``current_month``, ``errors``, ``generated_at`` and ``months``, plus the
    two a republication adds (``published_at``, ``republished_from_sha256``). Every card passes the
    per-card checks of §11.3. A naive ``wall_clock`` raises ``ValueError``.
    """
    if wall_clock.utcoffset() is None:
        raise ValueError("wall_clock must be timezone-aware")
    ok, doc = _load(data)
    if not ok:
        return ("legacy: not UTF-8 JSON",)
    if not isinstance(doc, dict):
        return ("legacy: the feed is not a JSON object",)
    problems = [f"legacy: missing key {key}" for key in sorted(_LEGACY_REQUIRED - doc.keys())]
    problems += [
        f"legacy: unexpected key {str(key)[:40]!r}"
        for key in doc
        if key not in _LEGACY_KEYS
    ]
    for field in ("generated_at", "published_at"):
        if field in doc and (why := _real_moment(doc[field], wall_clock)) is not None:
            problems.append(f"legacy: {field} {why}")
    if "republished_from_sha256" in doc:
        digest = doc["republished_from_sha256"]
        if not (isinstance(digest, str) and _HASH.fullmatch(digest)):
            problems.append("legacy: republished_from_sha256 is not 64 lowercase hex characters")
    month = doc.get("current_month")
    if "current_month" in doc and not (isinstance(month, str) and _MONTH.fullmatch(month)):
        problems.append(f"legacy: current_month {month!r} is not YYYY-MM")
    if "errors" in doc and not isinstance(doc["errors"], list):
        problems.append("legacy: errors is not a list")
    months = doc.get("months")
    if "months" in doc:
        if not isinstance(months, dict):
            problems.append("legacy: months is not an object")
        else:
            for key, cards in months.items():
                if not (isinstance(key, str) and _MONTH.fullmatch(key)):
                    problems.append(f"legacy: months key {str(key)[:40]!r} is not YYYY-MM")
                if not (isinstance(cards, list) and all(isinstance(c, dict) for c in cards)):
                    problems.append(f"legacy: months {str(key)[:40]!r} is not a list of objects")
    if len(data) > FEED_MAX_BYTES:
        problems.append(f"legacy: size: {len(data)} bytes is over {FEED_MAX_BYTES}")
    problems += _legacy(doc)
    return tuple(p[:MAX_PROBLEM] for p in problems)


def republished_problems(data: bytes, *, wall_clock: datetime) -> tuple[str, ...]:
    """The problems of a feed about to be republished, by its format (P122), or ``()``.

    ``schema_version`` exactly the integer 2 is a v2 feed (``feed_content_problems``); no
    ``schema_version`` key is a v1 feed (``legacy_feed_problems``); anything else is refused.
    """
    if wall_clock.utcoffset() is None:
        raise ValueError("wall_clock must be timezone-aware")
    ok, doc = _load(data)
    if not ok:
        return ("json: not UTF-8 JSON",)
    if not isinstance(doc, dict):
        return ("format: the feed is not a JSON object",)
    if "schema_version" not in doc:
        return legacy_feed_problems(data, wall_clock=wall_clock)
    version = doc["schema_version"]
    if type(version) is int and version == 2:
        return feed_content_problems(data, wall_clock=wall_clock)
    return (f"format: schema_version {version!r} is not supported"[:MAX_PROBLEM],)


def _content_problems(ok: bool, doc: Any, data: bytes, wall_clock: datetime) -> list[str]:
    if not ok:
        return ["json: not UTF-8 JSON"]
    problems = _schema_problems(doc, FEED_SCHEMA)
    problems += _legacy(doc)
    problems += _invariants(doc)
    if len(data) > FEED_MAX_BYTES:
        problems.append(f"size: {len(data)} bytes is over {FEED_MAX_BYTES}")
    problems += _timestamps(doc, wall_clock)
    return problems


def feed_content_problems(data: bytes, *, wall_clock: datetime) -> tuple[str, ...]:
    """The problems of an ``elections.json`` other than its served checks (§11.3), or ``()``.

    ``wall_clock`` is the machine clock, timezone-aware. Bytes that are not UTF-8 JSON give
    the ``json`` problem alone; otherwise the schema, legacy, invariant, size and timestamp
    checks run. It never raises on the document's content; a naive ``wall_clock`` raises
    ``ValueError``.
    """
    if wall_clock.utcoffset() is None:
        raise ValueError("wall_clock must be timezone-aware")
    ok, doc = _load(data)
    return tuple(_content_problems(ok, doc, data, wall_clock))


def validate_feed(
    data: bytes, *, served: Sequence[ServedCheck], wall_clock: datetime
) -> tuple[str, ...]:
    """The problems of an ``elections.json`` (§11.3), or ``()``.

    ``feed_content_problems`` plus the served checks, which run only when the bytes load.
    It never raises on the document's content, whatever its shape; a naive ``wall_clock``
    raises ``ValueError``.
    """
    if wall_clock.utcoffset() is None:
        raise ValueError("wall_clock must be timezone-aware")
    ok, doc = _load(data)
    problems = _content_problems(ok, doc, data, wall_clock)
    if ok:
        problems += _served(doc, served)
    return tuple(problems)
