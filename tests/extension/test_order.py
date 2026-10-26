"""lib/order.js and load.due: publication order, status selection, the check interval (Plan 5b-1 Task 4)."""

import json
from datetime import UTC, datetime
from typing import Any, Final

import pytest
from playwright.sync_api import Page

from tests.support.extension import artifact_pair, js, republication, v1_feed

ORDER = "lib/order.js"
LOAD = "lib/load.js"
D: Final = "d" * 64
E: Final = "e" * 64
F: Final = "f" * 64


def _ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def test_order_keys(lab: Page) -> None:
    feed = json.loads(artifact_pair()[0])
    v1 = json.loads(v1_feed())
    republished = json.loads(republication(v1_feed(), now=_aware("2026-10-17T00:03:00"))[0])
    assert js(lab, ORDER, "orderKey", feed) == "2026-10-19T12:00:00Z"
    assert js(lab, ORDER, "orderKey", v1) == v1["generated_at"]
    assert js(lab, ORDER, "orderKey", republished) == republished["published_at"]
    assert republished["published_at"] != republished["generated_at"]
    assert js(lab, ORDER, "orderKey", {"published_at": "x", "generated_at": "2026-10-01T00:00:00Z"}) == (
        "2026-10-01T00:00:00Z"
    )
    assert js(lab, ORDER, "orderKey", {"published_at": "x", "generated_at": "y"}) is None
    assert js(lab, ORDER, "orderKey", {"published_at": "2026-02-30T00:00:00Z"}) is None
    for not_an_object in (None, "2026-10-19T12:00:00Z", 5, [], ["published_at"]):
        assert js(lab, ORDER, "orderKey", not_an_object) is None


def _aware(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


ROLLBACK: Final = [
    ("2026-10-16T12:00:00Z", "2026-10-15T02:00:00Z", "2026-10-17T12:00:00Z", False),
    ("2026-10-16T12:00:00Z", "2026-10-17T00:02:00Z", "2026-10-17T12:00:00Z", True),
    ("2026-10-19T12:00:00Z", "2026-10-20T00:02:00Z", "2026-10-20T01:00:00Z", True),
    ("2026-10-19T12:00:00Z", "2026-10-19T12:00:00Z", "2026-10-20T01:00:00Z", False),
    (None, "2026-10-19T12:00:00Z", "2026-10-01T00:00:00Z", True),
    ("2026-10-19T12:00:01Z", "2026-10-18T00:00:00Z", "2026-10-18T12:00:00Z", True),
    ("2026-10-19T12:00:00Z", "2026-10-18T00:00:00Z", "2026-10-18T12:00:00Z", False),
    ("2026-10-19T12:00:00Z", None, "2026-10-20T00:00:00Z", False),
    ("2026-10-19T12:00:00Z", "2026-10-19T12:00:00.5Z", "2026-10-20T00:00:00Z", True),
    ("2026-10-19T12:00:00Z", "2026-02-30T00:00:00Z", "2026-10-20T00:00:00Z", False),
]


@pytest.mark.parametrize(("cached", "incoming", "now", "accepts"), ROLLBACK)
def test_rollback_ordering(
    lab: Page, cached: str | None, incoming: str | None, now: str, accepts: bool
) -> None:
    assert js(lab, ORDER, "accepts", cached, incoming, _ms(now)) is accepts


def _status(serves: str, outcome: str, hour: int, digest: str) -> dict[str, Any]:
    return {
        "data": {
            "serving_feed_sha256": serves,
            "outcome": outcome,
            "attempt_at": f"2026-10-19T{hour:02d}:00:00Z",
        },
        "sha256": digest,
        "received_at": 0,
    }


def _pick(lab: Page, cached: Any, received: list[Any]) -> Any:
    return js(lab, ORDER, "pickStatus", cached, received, D)


def test_status_selection(lab: Page) -> None:
    pub, bad = "published", "validation_failed"
    s = _status
    a, b, c = "a" * 64, "b" * 64, "c" * 64

    def digest_of(rec: Any) -> Any:
        return None if rec is None else rec["sha256"]

    rows: list[tuple[str, Any, list[Any], Any]] = []
    new = s(D, pub, 0, a)
    rows.append(("null cache", None, [new], new))
    cached = s(D, bad, 6, a)
    old = s(D, pub, 0, b)
    rows.append(("older success never erases a newer failure", cached, [old], cached))
    recovery = s(D, pub, 12, b)
    rows.append(("newer recovery", cached, [recovery], recovery))
    ok_cached = s(D, pub, 0, a)
    failure = s(D, bad, 6, b)
    rows.append(("newer failure", ok_cached, [failure], failure))
    tie_ok = s(D, pub, 6, a)
    tie_bad = s(D, bad, 6, b)
    rows.append(("tie: the failure wins (received)", tie_ok, [tie_bad], tie_bad))
    tie_bad_cached = s(D, bad, 6, a)
    tie_ok_received = s(D, pub, 6, b)
    rows.append(("tie: the failure wins (cached)", tie_bad_cached, [tie_ok_received], tie_bad_cached))
    other = s(D, pub, 6, b)
    rows.append(("tie: no flapping", tie_ok, [dict(tie_ok), other], tie_ok))
    rows.append(("same bytes", tie_ok, [dict(tie_ok)], tie_ok))
    about_e = s(E, pub, 12, b)
    rows.append(("only the cached describes D", ok_cached, [about_e], ok_cached))
    e_cached = s(E, pub, 0, a)
    f_new = s(F, pub, 12, b)
    rows.append(("neither describes D: the latest (received)", e_cached, [f_new], f_new))
    e_late = s(E, pub, 12, a)
    f_old = s(F, pub, 0, b)
    rows.append(("neither describes D: the latest (cached)", e_late, [f_old], e_late))
    e_second = s(E, pub, 6, b)
    d_third = s(D, pub, 3, c)
    rows.append(("the only one describing D", e_cached, [e_second, d_third], d_third))
    rows.append(("no received", ok_cached, [], ok_cached))
    rows.append(("nothing at all", None, [], None))

    for name, cache, received, want in rows:
        got = _pick(lab, cache, received)
        assert digest_of(got) == digest_of(want), name
        assert got == want, name


def test_due(lab: Page) -> None:
    now = 1_800_000_000_000

    def due(state: Any) -> Any:
        return js(lab, LOAD, "due", state, now)

    assert due(None) is True
    assert due({"ok_at": None, "failed_at": None, "error": None}) is True
    assert due({"ok_at": now - 1_799_999}) is False
    assert due({"ok_at": now - 1_800_000}) is True
    assert due({"ok_at": now}) is False
    assert due({"ok_at": "x"}) is True
    assert due({"ok_at": now + 1}) is True
    assert due("garbage") is True
    assert due({"ok_at": now - 1_000, "failed_at": now}) is False
    non_finite = lab.evaluate(
        "async ([m, now]) => { const { due } = await import(m);"
        " return [NaN, Infinity, -Infinity].map((v) => due({ ok_at: v }, now)); }",
        ["/" + LOAD, now],
    )
    assert non_finite == [True, True, True]
