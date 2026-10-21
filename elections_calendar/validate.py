"""The checks a feed or a status must pass before it is published (spec §11.3; P96, P104).

``validate_feed`` returns every problem it finds, each prefixed by its check: ``json``,
``schema``, ``legacy``, ``invariant``, ``size``, ``timestamp`` or ``served``. It never raises on
the content of the bytes, whatever their shape. ``validate`` is a sibling of ``feed`` and
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

from jsonschema import Draft202012Validator

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
_LEGACY_STATUS: Final = frozenset(get_args(LegacyStatus))


@dataclass(frozen=True, slots=True)
class ServedCheck:
    """What the pipeline found when it re-checked one source's served snapshot (§11.3 check 6)."""

    source: str
    snapshot_id: str | None  # None for an unavailable source: nothing is served
    ledger_ok: bool
    discovery_ok: bool


@cache
def _validator(path: Path) -> Draft202012Validator:
    return Draft202012Validator(json.loads(path.read_text(encoding="utf-8")))


def _load(data: bytes) -> tuple[bool, Any]:
    try:
        return True, json.loads(data.decode("utf-8"))
    except (ValueError, RecursionError):
        return False, None


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
        if card.get("status") not in _LEGACY_STATUS:
            problems.append(f"{who}status {card.get('status')!r} is not a legacy value")
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


def _first_window_month(months: list[str], start: date, end: date) -> str | None:
    for key in months:
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}", key):
            continue
        year, month = int(key[:4]), int(key[5:])
        if not 1 <= month <= 12:
            continue
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
        if start is None or end is None:
            continue
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
            if match not in child_ids:
                problems.append(f"invariant: {owner} has possible_matches {match!r}, not a child")

    undated_ids = {_text(u.get("undated_id")) for u in listings}
    for item in items:
        link = item.get("undated_id")
        if link is not None and link not in undated_ids:
            problems.append(
                f"invariant: item {_text(item.get('item_id'))} has undated_id {link!r}, "
                "not in undated"
            )

    for _, card in cards:
        mine = {_text(c.get("child_id")) for c in _dicts(card.get("children"))}
        for umbrella in _dicts(card.get("umbrellas")):
            listed = umbrella.get("children")
            for child in listed if isinstance(listed, list) else []:
                if child not in mine:
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
        if moment is not None and moment - wall_clock > MAX_AHEAD:
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


def validate_feed(
    data: bytes, *, served: Sequence[ServedCheck], wall_clock: datetime
) -> tuple[str, ...]:
    """The problems of an ``elections.json`` (§11.3), or ``()``.

    ``wall_clock`` is the machine clock, timezone-aware. Bytes that are not UTF-8 JSON give
    the ``json`` problem alone; otherwise every check runs.
    """
    if wall_clock.utcoffset() is None:
        raise ValueError("wall_clock must be timezone-aware")
    ok, doc = _load(data)
    if not ok:
        return ("json: not UTF-8 JSON",)
    problems = _schema_problems(doc, FEED_SCHEMA)
    problems += _legacy(doc)
    problems += _invariants(doc)
    if len(data) > FEED_MAX_BYTES:
        problems.append(f"size: {len(data)} bytes is over {FEED_MAX_BYTES}")
    problems += _timestamps(doc, wall_clock)
    problems += _served(doc, served)
    return tuple(problems)
