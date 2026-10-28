"""lib/load.js, the module worker and the popup's loading (Plan 5b-1 Task 4)."""

import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Final

import pytest
from playwright.sync_api import Page

from tests.support.extension import (
    PAGE_NOW,
    PAGE_NOW_MS,
    Ext,
    artifact_pair,
    feed_record,
    js,
    linking,
    published_at,
    republication,
    run_check,
    status_record,
    v1_feed,
)

ORDER = "lib/order.js"
SCHEMA = "lib/schema.js"
FEED: Final = "elections_cache_v2"
STATUS: Final = "status_cache"
CHECK: Final = "check_state_v2"
ZEROS: Final = "0" * 64
T0: Final = "2026-10-17T12:00:00Z"
T1: Final = "2026-10-18T12:00:00Z"
T2: Final = "2026-10-19T12:00:00Z"
T3: Final = "2026-10-20T12:00:00Z"
KEY_T2: Final = "2026-10-19T12:00:00Z"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dump(doc: Any) -> bytes:
    return json.dumps(doc, separators=(",", ":")).encode("utf-8")


def _elsewhere(status: bytes, attempt_at: str | None = None) -> bytes:
    """``status`` made to describe no feed we have (S')."""
    doc = json.loads(status)
    doc["serving_feed_sha256"] = ZEROS
    if attempt_at is not None:
        doc["attempt_at"] = attempt_at
    return _dump(doc)


def _check(lab: Page, **kw: Any) -> dict[str, Any]:
    kw.setdefault("stored", {})
    kw.setdefault("now", PAGE_NOW_MS)
    return run_check(lab, **kw)


def _feed_sha(ran: dict[str, Any]) -> str | None:
    record = ran["stored"].get(FEED)
    return None if record is None else str(record["sha256"])


def _status_sha(ran: dict[str, Any]) -> str | None:
    record = ran["stored"].get(STATUS)
    return None if record is None else str(record["sha256"])


@pytest.fixture(scope="module")
def pair() -> tuple[bytes, bytes]:
    return artifact_pair()


def test_check_links_and_refetches_once(lab: Page, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    # (a) a linked pair: two requests, one write
    ran = _check(lab, feed=[feed], status=[status])
    assert ran["log"] == ["elections.json", "status.json"]
    record = ran["stored"][FEED]
    assert record["sha256"] == _sha(feed) and record["order_key"] == KEY_T2
    assert record["format"] == "v2" and record["received_at"] == PAGE_NOW_MS
    assert ran["stored"][STATUS]["sha256"] == _sha(status)
    assert ran["stored"][STATUS]["data"] == json.loads(status)
    assert ran["stored"][CHECK] == {"ok_at": PAGE_NOW_MS, "failed_at": None, "error": None}
    assert ran["result"] == {"ok": True, "changed": True}
    assert ran["sets"] == [[FEED, STATUS, CHECK]]
    # (b) a stale status first: both documents are fetched once more
    stale = _elsewhere(status)
    ran = _check(lab, feed=[feed], status=[stale, status])
    assert ran["log"] == ["elections.json", "status.json", "elections.json", "status.json"]
    assert _status_sha(ran) == _sha(status)
    # (c) the status never links: the last one received is kept
    ran = _check(lab, feed=[feed], status=[stale])
    assert ran["log"] == ["elections.json", "status.json", "elections.json", "status.json"]
    assert _status_sha(ran) == _sha(stale) and _feed_sha(ran) == _sha(feed)
    # (d) a linked status is cached: a stale one does not replace it
    cached = {FEED: feed_record(feed), STATUS: status_record(status)}
    ran = _check(lab, feed=[feed], status=[stale], stored=cached)
    assert ran["log"] == ["elections.json", "status.json", "elections.json", "status.json"]
    assert _status_sha(ran) == _sha(status)
    # (e) no usable status: the feed is stored, there is no status and no second round
    no_outcome = json.loads(status)
    del no_outcome["outcome"]
    for bad in (404, b"{", _dump(no_outcome), None):
        ran = _check(lab, feed=[feed], status=[bad])
        assert ran["log"] == ["elections.json", "status.json"]
        assert _feed_sha(ran) == _sha(feed) and STATUS not in ran["stored"]
        assert ran["result"] == {"ok": True, "changed": True}


def test_check_orders_responses(lab: Page, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    docs = {}
    for name, key in (("t2", T2), ("t1", T1), ("t3", T3)):
        f = published_at(feed, key)
        docs[name] = (f, linking(f, status))
    stored: dict[str, Any] = {}
    seen = []
    for name, changed in (("t2", True), ("t1", False), ("t3", True)):
        f, s = docs[name]
        ran = _check(lab, feed=[f], status=[s], stored=stored)
        stored = ran["stored"]
        seen.append((stored[FEED]["order_key"], ran["result"]["changed"]))
        if name == "t1":
            assert stored[STATUS]["sha256"] == _sha(docs["t2"][1])
        assert ran["result"]["ok"] is True and ran["result"]["changed"] is changed
    assert seen == [(T2, True), (T2, False), (T3, True)]
    f, s = docs["t3"]
    ran = _check(lab, feed=[f], status=[s], stored=stored)
    assert ran["result"] == {"ok": True, "changed": False}
    assert ran["sets"] == [[CHECK]]


def test_a_retry_keeps_the_best_feed(lab: Page, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    f0, f1, f2 = (published_at(feed, k) for k in (T0, T1, T2))
    stale = _elsewhere(status, "2026-10-19T06:00:00Z")
    s1 = linking(f1, status, "2026-10-19T07:00:00Z")
    s2 = linking(f2, status, "2026-10-19T08:00:00Z")
    s0 = linking(f0, status, "2026-10-19T05:00:00Z")
    rows: list[tuple[dict[str, Any], list[Any], list[Any], bytes, bytes, bool]] = [
        ({}, [f2, f1], [stale, s1], f2, s1, False),
        ({FEED: feed_record(f0)}, [f2, 503], [stale, stale], f2, stale, False),
        ({}, [f2, None], [stale, s2], f2, s2, True),
        ({}, [f1, f2], [stale, s2], f2, s2, True),
        ({FEED: feed_record(f2)}, [f2, f2], [stale, "hang"], f2, stale, False),
        # B2: none of the statuses describes f2 (P132), so the latest attempt is kept
        (
            {FEED: feed_record(f0), STATUS: status_record(s0)},
            [f2, f1], [stale, s1], f2, s1, False,
        ),
    ]
    for stored, feeds, statuses, want_feed, want_status, linked in rows:
        ran = _check(lab, feed=feeds, status=statuses, stored=stored)
        assert ran["result"]["ok"] is True
        assert _feed_sha(ran) == _sha(want_feed)
        assert _status_sha(ran) == _sha(want_status)
        got = js(lab, ORDER, "isLinked", _feed_sha(ran), ran["stored"][STATUS]["data"])
        assert got is linked
        assert ran["stored"][CHECK] == {"ok_at": PAGE_NOW_MS, "failed_at": None, "error": None}
    unchanged = _check(
        lab, feed=[f2, f2], status=[stale, "hang"], stored={FEED: feed_record(f2)}
    )
    assert unchanged["stored"][FEED] == feed_record(f2)


def test_cached_records_are_validated(lab: Page, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    ahead = "2026-10-19T13:00:00Z"
    good = feed_record(feed)

    def mangled(edit: Callable[[dict[str, Any]], None], key: str | None = ahead) -> dict[str, Any]:
        record = feed_record(feed)
        if key is not None:
            record["order_key"] = key
        edit(record)
        return record

    def drop_months(record: dict[str, Any]) -> None:
        del record["data"]["months"]

    cases = {
        "no months": mangled(drop_months, None),
        "format": mangled(lambda r: r.update(format="legacy"), None),
        "order_key": mangled(lambda r: None),
        "sha256": mangled(lambda r: r.update(sha256="x"), None),
        "received_at": mangled(lambda r: r.update(received_at="x"), None),
        "no record": "garbage",
    }
    for name, record in cases.items():
        ran = _check(lab, feed=[feed], status=[status], stored={FEED: record})
        assert _feed_sha(ran) == _sha(feed), name
        assert ran["stored"][FEED] == good | {"received_at": PAGE_NOW_MS}, name
    later = published_at(feed, ahead)
    control = _check(lab, feed=[feed], status=[status], stored={FEED: feed_record(later)})
    assert _feed_sha(control) == _sha(later)
    assert control["stored"][FEED] == feed_record(later)

    garbage = json.loads(status)
    del garbage["outcome"]
    garbage["attempt_at"] = "2026-10-19T13:00:00Z"  # later than the real status: it would win
    record = {"data": garbage, "sha256": "a" * 64, "received_at": 0}
    ran = _check(lab, feed=[feed], status=[status], stored={STATUS: record})
    assert _status_sha(ran) == _sha(status)


def test_check_has_a_deadline(lab: Page, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    ran = _check(lab, feed=["hang"], status=[status])
    assert ran["result"] == {"ok": False, "error": "elections.json: no response in time"}
    ran = _check(lab, feed=[feed], status=["hang"])
    assert ran["result"]["ok"] is True
    assert _feed_sha(ran) == _sha(feed) and STATUS not in ran["stored"]
    again = _check(lab, feed=[feed], status=[status], stored=ran["stored"])
    assert again["result"] == {"ok": True, "changed": True}
    assert _status_sha(again) == _sha(status)


def test_check_records_failures_and_keeps_the_cache(lab: Page, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    cached = {
        FEED: feed_record(feed),
        STATUS: status_record(status),
        CHECK: {"ok_at": PAGE_NOW_MS - 1, "failed_at": None, "error": None},
    }
    huge = b" " * 4_000_001
    cases: list[tuple[Any, str]] = [
        (503, "elections.json: HTTP 503"),
        (None, "elections.json: the request failed"),
        (b"\xff", "elections.json: not UTF-8 JSON"),
        (b"[]", "elections.json: unreadable feed: "),
        (huge, "elections.json: over the limit of 4000000 bytes"),
    ]
    for response, error in cases:
        ran = _check(lab, feed=[response], status=[status], stored=cached)
        got = ran["result"]
        assert got["ok"] is False
        if response == b"[]":
            assert got["error"].startswith(error) and len(got["error"]) > len(error)
        else:
            assert got["error"] == error
        assert ran["stored"][FEED] == cached[FEED] and ran["stored"][STATUS] == cached[STATUS]
        assert ran["stored"][CHECK] == {
            "ok_at": PAGE_NOW_MS - 1,
            "failed_at": PAGE_NOW_MS,
            "error": got["error"],
        }
        assert ran["log"] == ["elections.json"]


def test_a_digest_failure_is_a_failed_check(lab: Page, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    cached = {
        FEED: feed_record(feed),
        STATUS: status_record(status),
        CHECK: {"ok_at": PAGE_NOW_MS - 1, "failed_at": None, "error": None},
    }
    lab.evaluate(
        """() => {
  window.__digest = crypto.subtle.digest;
  crypto.subtle.digest = () => Promise.reject(new Error('no digest'));
}"""
    )
    try:
        ran = _check(lab, feed=[feed], status=[status], stored=cached)
    finally:
        lab.evaluate("() => { crypto.subtle.digest = window.__digest; }")
    assert ran["result"] == {
        "ok": False,
        "error": "elections.json: the response could not be checked",
    }
    assert ran["stored"][FEED] == cached[FEED] and ran["stored"][STATUS] == cached[STATUS]
    assert ran["stored"][CHECK]["ok_at"] == PAGE_NOW_MS - 1
    assert ran["stored"][CHECK]["failed_at"] == PAGE_NOW_MS


def test_a_failed_write_keeps_the_previous_pair(lab: Page, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    f2, f3 = published_at(feed, T2), published_at(feed, T3)
    s2, s3 = linking(f2, status), linking(f3, status)
    cached = {FEED: feed_record(f2), STATUS: status_record(s2)}
    ran = _check(lab, feed=[f3], status=[s3], stored=cached, set_fails="QUOTA_BYTES quota exceeded")
    assert ran["result"] == {
        "ok": False,
        "error": "could not save the new data: QUOTA_BYTES quota exceeded",
    }
    assert ran["stored"][FEED] == cached[FEED] and ran["stored"][STATUS] == cached[STATUS]
    assert ran["sets"] == [[FEED, STATUS, CHECK], [CHECK]]
    assert ran["stored"][CHECK]["failed_at"] == PAGE_NOW_MS


def test_recovery_reaches_the_client(lab: Page, pair: tuple[bytes, bytes]) -> None:
    feed, _ = pair
    n = datetime.now(UTC).replace(microsecond=0)

    def stamp(moment: datetime) -> str:
        return moment.strftime("%Y-%m-%dT%H:%M:%SZ")

    def at(moment: datetime) -> bytes:
        return published_at(feed, stamp(moment))

    d = at(n - timedelta(days=2))
    original = at(n - timedelta(days=5))
    r, rs = republication(original, now=n - timedelta(days=1))
    v1 = json.loads(v1_feed())
    v1["generated_at"] = stamp(n - timedelta(hours=12))
    v = _dump(v1)
    now = int(n.timestamp() * 1000)

    ran = _check(lab, feed=[r], status=[rs], stored={FEED: feed_record(d)}, now=now)
    assert _feed_sha(ran) == _sha(r) and ran["stored"][FEED]["format"] == "v2"
    assert js(lab, ORDER, "isLinked", _sha(r), ran["stored"][STATUS]["data"]) is True
    assert ran["log"] == ["elections.json", "status.json"]

    delayed = _check(lab, feed=[d], status=[rs], stored=ran["stored"], now=now)
    assert delayed["result"] == {"ok": True, "changed": False}

    rolled = _check(lab, feed=[v], status=[rs], stored=delayed["stored"], now=now)
    assert _feed_sha(rolled) == _sha(v)
    assert rolled["stored"][FEED]["format"] == "legacy"
    assert rolled["stored"][FEED]["order_key"] == v1["generated_at"]
    assert _status_sha(rolled) == _sha(rs)
    assert js(lab, ORDER, "isLinked", _sha(v), rolled["stored"][STATUS]["data"]) is False


def test_missing_schemas_fail_the_check(lab: Page, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    ran = _check(lab, feed=[feed], status=[status], schemas=False)
    error = "the extension's schemas could not be read"
    assert ran["result"] == {"ok": False, "error": error}
    assert ran["log"] == [] and FEED not in ran["stored"]
    assert ran["stored"][CHECK] == {"ok_at": None, "failed_at": PAGE_NOW_MS, "error": error}


def test_schema_problems_without_a_schema(lab: Page) -> None:
    got = lab.evaluate(
        "async m => { const { schemaProblems } = await import(m);"
        " return [undefined, null, 5, 'x', []].map((s) => schemaProblems({}, s)); }",
        "/" + SCHEMA,
    )
    assert got == [["/: no schema"]] * 5


# ── the module worker and the popup, in Chromium ──────────────────────────────


def _send_check(page: Page, force: bool = True) -> dict[str, Any]:
    reply: dict[str, Any] = page.evaluate(
        "force => chrome.runtime.sendMessage({ type: 'CHECK', force })", force
    )
    return reply


def _wake(ext: Ext) -> None:
    ext.lab().evaluate("() => chrome.runtime.sendMessage({ type: 'PING' }).catch(() => null)")


def _alarm(page: Page) -> dict[str, Any] | None:
    got: dict[str, Any] | None = page.evaluate("() => chrome.alarms.get('elections-refresh')")
    return got


def _cards(page: Page) -> int:
    return page.locator(".election-item").count()


def _settled(page: Page, state: str = "ready") -> None:
    page.wait_for_function(
        "s => document.body.dataset.state === s && document.body.dataset.checking === 'false'",
        arg=state,
    )


def test_the_worker_checks_and_the_popup_shows_the_result(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    ext.served.set("elections.json", feed)
    ext.served.set("status.json", status)
    page = ext.popup()
    assert ext.served.log == ["elections.json", "status.json"]
    assert ext.storage()[FEED]["sha256"] == _sha(feed)
    assert _cards(page) == 30
    classes = {t: page.locator(f"#{t}").get_attribute("class") or "" for t in ("tabAll", "tabUpcoming", "tabPast")}
    assert "active" in classes["tabAll"].split()
    assert all("active" not in classes[t].split() for t in ("tabUpcoming", "tabPast"))
    assert page.locator("body").get_attribute("data-state") == "ready"
    assert ext.page_errors == []


def test_two_checks_at_once_fetch_once(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    ext.served.set("elections.json", feed)
    ext.served.set("status.json", status)
    replies = ext.lab().evaluate(
        "() => Promise.all([1, 2].map(() => chrome.runtime.sendMessage({ type: 'CHECK', force: true })))"
    )
    assert [r["ok"] for r in replies] == [True, True]
    assert ext.served.log.count("elections.json") == 1


def test_the_alarm_survives_restart_and_worker_termination(
    fresh_ext: Ext, pair: tuple[bytes, bytes]
) -> None:
    feed, _ = pair
    lab = fresh_ext.lab()
    found = _alarm(lab)
    assert found is not None and found["periodInMinutes"] == 60
    lab.evaluate("() => chrome.alarms.clearAll()")
    assert _alarm(lab) is None
    fresh_ext.stop_worker()
    fresh_ext.seed({FEED: feed_record(feed)})
    page = fresh_ext.popup()
    again = _alarm(lab)
    assert again is not None and again["periodInMinutes"] == 60
    assert _cards(page) == 30
    lab.evaluate("() => chrome.alarms.clearAll()")
    # A relaunch fires onInstalled (reason install), not onStartup, under --load-extension.
    relaunched = fresh_ext.relaunch()
    back = _alarm(relaunched.lab())
    assert back is not None and back["periodInMinutes"] == 60


CHECK_RESULT: Final = {"ok": True, "changed": True, "marker": 1}
SKIPPED: Final = {"ok": True, "changed": False, "skipped": True}
HANDLER_ROWS: Final = [
    (
        "installed",
        {"reason": "install"},
        True,
        ["openHelp", "migratePins", "ensureAlarm", "runCheck"],
        None,
    ),
    ("installed", {"reason": "update"}, True, ["migratePins", "ensureAlarm", "runCheck"], None),
    ("startup", None, True, ["migratePins", "ensureAlarm", "runCheck"], None),
    ("alarm", {"name": "elections-refresh"}, True, ["runCheck", "ensureAlarm"], None),
    ("alarm", {"name": "other"}, True, [], None),
    ("message", {"type": "CHECK", "force": False}, False, ["ensureAlarm", "isDue"], SKIPPED),
    (
        "message",
        {"type": "CHECK", "force": False},
        True,
        ["ensureAlarm", "isDue", "runCheck"],
        CHECK_RESULT,
    ),
    ("message", {"type": "CHECK", "force": True}, False, ["ensureAlarm", "runCheck"], CHECK_RESULT),
    ("message", {"type": "FETCH_DATA"}, True, [], None),
]


@pytest.mark.parametrize(("call", "arg", "due", "calls", "result"), HANDLER_ROWS)
def test_worker_handlers(
    lab: Page, call: str, arg: Any, due: bool, calls: list[str], result: Any
) -> None:
    ran = lab.evaluate(
        "async s => (await import('/test/fakes.js')).runHandlers(s)",
        {"call": call, "arg": arg, "due": due},
    )
    assert ran["log"] == [f"{name}:{edge}" for name in calls for edge in ("start", "end")]
    assert ran["result"] == result
    assert ran["undefinedResult"] is (result is None)


def test_a_failing_help_tab_does_not_stop_the_install_check(lab: Page) -> None:
    ran = lab.evaluate(
        "async s => (await import('/test/fakes.js')).runHandlers(s)",
        {"call": "installed", "arg": {"reason": "install"}, "due": True, "helpRejects": True},
    )
    calls = ["openHelp", "migratePins", "ensureAlarm", "runCheck"]
    assert ran["log"] == [f"{name}:{edge}" for name in calls for edge in ("start", "end")]


MIGRATED: Final = {"ok": True, "migrated": True, "marker": 2}


def _handlers(lab: Page, **spec: Any) -> dict[str, Any]:
    ran: dict[str, Any] = lab.evaluate(
        "async s => (await import('/test/fakes.js')).runHandlers(s)", spec
    )
    return ran


def _calls(*names: str) -> list[str]:
    return [f"{name}:{edge}" for name in names for edge in ("start", "end")]


def test_the_worker_migrates_pins_on_install_update_and_startup(lab: Page) -> None:
    ran = _handlers(lab, call="installed", arg={"reason": "install"}, due=True)
    assert ran["log"] == _calls("openHelp", "migratePins", "ensureAlarm", "runCheck")
    ran = _handlers(lab, call="installed", arg={"reason": "update"}, due=True)
    assert ran["log"] == _calls("migratePins", "ensureAlarm", "runCheck")
    ran = _handlers(lab, call="startup", due=True)
    assert ran["log"] == _calls("migratePins", "ensureAlarm", "runCheck")
    # the alarm path does not migrate
    ran = _handlers(lab, call="alarm", arg={"name": "elections-refresh"})
    assert ran["log"] == _calls("runCheck", "ensureAlarm")

    # a migration that rejects still runs the alarm and the check
    ran = _handlers(lab, call="startup", due=True, migrateRejects=True)
    assert ran["log"] == _calls("migratePins", "ensureAlarm", "runCheck")
    assert ran["rejected"] is None

    # PINS waits for the migration and returns its reply; the listener must hold the channel
    ran = _handlers(lab, call="message", arg={"type": "PINS"})
    assert ran["log"] == _calls("migratePins")
    assert ran["result"] == MIGRATED and ran["undefinedResult"] is False
    edit = {"type": "PIN_EDIT", "op": "pin", "value": "iso:LS"}
    ran = _handlers(lab, call="message", arg=edit)
    assert ran["log"] == _calls("editPin")
    assert ran["result"] == {"ok": True, "edited": {"op": "pin", "value": "iso:LS"}}


def test_the_place_table_loads(lab: Page) -> None:
    got = lab.evaluate(
        """async () => {
          const { loadPlaces } = await import('/lib/load.js');
          const table = await loadPlaces((p) => chrome.runtime.getURL(p));
          const real = window.fetch;
          const failure = async (response) => {
            window.fetch = async () => response;
            try {
              await loadPlaces((p) => p);
              return null;
            } catch (e) {
              return e.message;
            } finally {
              window.fetch = real;
            }
          };
          return [
            Object.keys(table.names).length,
            Object.keys(table.places).length,
            await failure(new Response('', { status: 404 })),
            await failure(new Response('{"names": {}}')),
          ];
        }"""
    )
    assert got == [487, 264, "HTTP 404 for places.json", "places.json is not a place table"]


def test_a_failed_write_in_the_worker_keeps_the_cache(
    fresh_ext: Ext, pair: tuple[bytes, bytes]
) -> None:
    feed, _ = pair
    f2, f3 = published_at(feed, T2), published_at(feed, T3)
    fresh_ext.seed({FEED: feed_record(f2)})
    _wake(fresh_ext)
    fresh_ext.worker().evaluate(
        "() => { chrome.storage.local.set = () => Promise.reject(new Error('QUOTA_BYTES quota exceeded')); }"
    )
    fresh_ext.served.set("elections.json", f3)
    lab = fresh_ext.lab()
    reply = _send_check(lab)
    assert reply["error"] == "could not save the new data: QUOTA_BYTES quota exceeded"
    assert fresh_ext.storage()[FEED]["order_key"] == T2
    fresh_ext.stop_worker()  # the next worker has the real API
    assert _send_check(lab)["ok"] is True
    assert fresh_ext.storage()[FEED]["order_key"] == T3


_FILL = """
async () => {
  const area = chrome.storage.local;
  const target = 100000;
  let n = area.QUOTA_BYTES - (await area.getBytesInUse(null)) - target;
  for (let i = 0; i < 4; i++) {
    await area.set({ filler: 'x'.repeat(Math.max(n, 0)) });
    const left = area.QUOTA_BYTES - (await area.getBytesInUse(null));
    if (left === target) break;
    n += left - target;
  }
  return area.QUOTA_BYTES - (await area.getBytesInUse(null));
}
"""


def test_a_real_quota_failure_keeps_the_previous_pair(fresh_ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    f2, f3 = published_at(feed, T2), published_at(feed, T3)
    s2 = linking(f2, status)
    seeded = {FEED: feed_record(f2), STATUS: status_record(s2)}
    fresh_ext.seed(seeded)
    lab = fresh_ext.lab()
    assert lab.evaluate(_FILL) == 100_000
    big = json.loads(f3)
    big["padding"] = "x" * 400_000  # an unknown top-level key: ignored by validation
    served = _dump(big)
    s3 = linking(served, status)  # describes the feed that is served, so it is in the write set
    fresh_ext.served.set("elections.json", served)
    fresh_ext.served.set("status.json", s3)
    reply = _send_check(lab)
    assert reply["ok"] is False
    assert reply["error"].startswith("could not save the new data: ")
    assert "quota" in reply["error"].lower()
    stored = fresh_ext.storage()
    assert stored[FEED] == seeded[FEED] and stored[STATUS] == seeded[STATUS]
    lab.evaluate("() => chrome.storage.local.remove('filler')")
    assert _send_check(lab)["ok"] is True
    assert fresh_ext.storage()[FEED]["order_key"] == T3
    assert fresh_ext.storage()[STATUS]["sha256"] == _sha(s3)


def test_offline_with_and_without_a_cache(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    expired = int(time.time() * 1000) - 7_200_000
    ext.seed({FEED: feed_record(feed), CHECK: {"ok_at": expired, "failed_at": None, "error": None}})
    page = ext.popup()
    assert "elections.json" in ext.served.log
    assert _cards(page) == 30 and page.locator("#stateError").is_hidden()

    ext.close_other_pages()
    ext.clear()
    ext.served.reset()
    page = ext.popup()
    assert page.locator("#stateError").is_visible()
    assert page.locator("#errorMsg").text_content() == (
        "Could not load data: elections.json: the request failed"
    )
    assert page.locator("body").get_attribute("data-state") == "error"

    ext.served.set("elections.json", feed)
    ext.served.set("status.json", status)
    page.click("#retryBtn")
    _settled(page)
    assert _cards(page) == 30


def test_the_v1_cache_and_pins_are_left_alone(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    seeded = {
        "elections_cache": {"ts": 1, "data": json.loads(v1_feed())},
        "pinned_countries": ["Brazil"],
        "selected_countries": ["Brazil"],
    }
    ext.seed(seeded)
    ext.served.set("elections.json", feed)
    ext.served.set("status.json", status)
    ext.popup()
    stored = ext.storage()
    assert FEED in stored
    assert {k: stored[k] for k in seeded} == seeded
    # a migration (the options page asks the worker for one) leaves the v1 keys alone too
    ext.open("options.html").wait_for_function("() => document.body.dataset.pinSync === 'idle'")
    after = ext.storage()
    assert after["pins_migrated_v2"] is True and after["unresolved_pins_v2"] == []
    assert after["pinned_places_v2"] == ["iso:BR"]
    assert {k: after[k] for k in seeded} == seeded


def test_a_corrupt_cache_is_ignored(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    broken = feed_record(feed)
    del broken["data"]["months"]
    broken["order_key"] = _stamp_in(timedelta(hours=1))
    for corrupt in ("garbage", {"data": 5, "sha256": "x"}, broken):
        ext.close_other_pages()
        ext.clear()
        ext.served.reset()
        ext.seed({FEED: corrupt})
        page = ext.popup()
        # nothing is served and nothing valid is cached: an error, with nothing drawn
        assert page.locator("body").get_attribute("data-state") == "error"
        assert _cards(page) == 0 and page.locator("#footer").text_content() == ""
        ext.served.set("elections.json", feed)
        ext.served.set("status.json", status)
        page.click("#refreshBtn")
        _settled(page)
        assert ext.storage()[FEED] == feed_record(feed) | {
            "received_at": ext.storage()[FEED]["received_at"]
        }
        assert _cards(page) == 30
        assert ext.page_errors == []


def _stamp_in(delta: timedelta) -> str:
    return (datetime.now(UTC) + delta).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_a_check_cut_short_leaves_the_previous_pair(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    f2, f3 = published_at(feed, T2), published_at(feed, T3)
    s2, s3 = linking(f2, status), linking(f3, status)
    seeded = {FEED: feed_record(f2), STATUS: status_record(s2)}
    ext.seed(seeded)
    ext.served.set("elections.json", "hang")
    lab = ext.lab()
    lab.evaluate(
        "() => { chrome.runtime.sendMessage({ type: 'CHECK', force: true }).catch(() => null); }"
    )
    deadline = time.monotonic() + 10
    while "elections.json" not in ext.served.log:
        assert time.monotonic() < deadline, "the check never requested elections.json"
        lab.wait_for_timeout(50)
    ext.stop_worker()
    stored = ext.storage()
    assert stored[FEED] == seeded[FEED] and stored[STATUS] == seeded[STATUS]
    ext.served.set("elections.json", f3)
    ext.served.set("status.json", s3)
    assert _send_check(lab)["ok"] is True
    assert ext.storage()[FEED]["order_key"] == T3


def test_a_check_cut_short_after_the_feed_arrived_writes_nothing(
    ext: Ext, pair: tuple[bytes, bytes]
) -> None:
    feed, status = pair
    f2, f3 = published_at(feed, T2), published_at(feed, T3)
    s2 = linking(f2, status)
    state = {"ok_at": 1, "failed_at": None, "error": None}
    seeded = {FEED: feed_record(f2), STATUS: status_record(s2), CHECK: state}
    ext.seed(seeded)
    ext.served.set("elections.json", f3)  # a newer, valid feed arrives ...
    ext.served.set("status.json", "hang")  # ... but the status never does
    lab = ext.lab()
    lab.evaluate(
        "() => { chrome.runtime.sendMessage({ type: 'CHECK', force: true }).catch(() => null); }"
    )
    deadline = time.monotonic() + 10
    while "status.json" not in ext.served.log:
        assert time.monotonic() < deadline, "the check never requested status.json"
        lab.wait_for_timeout(50)
    ext.stop_worker()
    stored = ext.storage()
    assert stored[FEED] == seeded[FEED] and stored[STATUS] == seeded[STATUS]
    assert stored[CHECK] == state


def test_schemas_are_retried_after_a_failed_load(fresh_ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    fresh_ext.served.set("elections.json", feed)
    fresh_ext.served.set("status.json", status)
    schema = fresh_ext.folder / "schemas" / "status-v1.schema.json"
    hidden = schema.with_suffix(".hidden")
    fresh_ext.clear()
    fresh_ext.stop_worker()
    schema.rename(hidden)
    try:
        lab = fresh_ext.lab()
        assert _send_check(lab) == {
            "ok": False,
            "error": "the extension's schemas could not be read",
        }
    finally:
        hidden.rename(schema)
    assert _send_check(lab)["ok"] is True
    assert fresh_ext.storage()[FEED]["sha256"] == _sha(feed)


_HOLD_FIRST_CHECK = """() => {
  const real = chrome.runtime.sendMessage.bind(chrome.runtime);
  let held = false;
  chrome.runtime.sendMessage = (msg) => {
    if (!held && msg && msg.type === 'CHECK') {
      held = true;
      return new Promise((resolve) => { window.__release = () => resolve({ ok: true }); });
    }
    return real(msg);
  };
}"""


def test_the_popup_settles_only_when_every_check_is_done(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    ext.served.set("elections.json", feed)
    ext.served.set("status.json", status)
    ext.context.clock.set_fixed_time(PAGE_NOW)
    page = ext.context.new_page()
    page.on("pageerror", lambda error: ext.page_errors.append(str(error)))
    page.add_init_script(script=f"({_HOLD_FIRST_CHECK})()")
    page.goto(f"chrome-extension://{ext.ext_id}/popup.html")
    page.wait_for_function("() => typeof window.__release === 'function'")  # check 1 is held
    page.click("#refreshBtn")  # check 2 goes through the worker and finishes
    page.wait_for_function("() => document.body.dataset.state === 'ready'")
    assert page.locator("body").get_attribute("data-checking") == "true"  # check 1 is still open
    page.evaluate("() => window.__release()")
    _settled(page)
    assert _cards(page) == 30 and ext.served.log.count("elections.json") == 1
    assert ext.page_errors == []


# ── the check's error boundary and request limits (Plan 5b-2 Task 1; P147) ────

BOOM: Final = "the check failed unexpectedly: boom"


def _cached_pair(pair: tuple[bytes, bytes]) -> dict[str, Any]:
    feed, status = pair
    return {
        FEED: feed_record(feed),
        STATUS: status_record(status),
        CHECK: {"ok_at": PAGE_NOW_MS - 1, "failed_at": None, "error": None},
    }


def test_an_unexpected_error_fails_the_check(lab: Page, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    # no cache
    ran = _check(lab, feed=[feed], status=[status], throw="boom")
    assert ran["result"] == {"ok": False, "error": BOOM}
    assert ran["stored"] == {CHECK: {"ok_at": None, "failed_at": PAGE_NOW_MS, "error": BOOM}}
    assert ran["reported"] == ["boom"]
    # a cached pair
    cached = _cached_pair(pair)
    ran = _check(lab, feed=[feed], status=[status], stored=cached, throw="boom")
    assert ran["result"] == {"ok": False, "error": BOOM}
    assert ran["stored"][FEED] == cached[FEED] and ran["stored"][STATUS] == cached[STATUS]
    assert ran["stored"][CHECK] == {"ok_at": PAGE_NOW_MS - 1, "failed_at": PAGE_NOW_MS, "error": BOOM}
    # a long message is cut
    ran = _check(lab, feed=[feed], status=[status], stored=cached, throw="x" * 1000)
    assert ran["result"]["error"] == "the check failed unexpectedly: " + "x" * 200 + "…"
    # recovery: real schemas on the resulting storage, with the pair served
    stored = _check(lab, feed=[feed], status=[status], stored=cached, throw="boom")["stored"]
    later = published_at(feed, T3)
    served = linking(later, status)
    ran = _check(lab, feed=[later], status=[served], stored=stored)
    assert ran["result"] == {"ok": True, "changed": True}
    assert _feed_sha(ran) == _sha(later) and _status_sha(ran) == _sha(served)
    assert ran["stored"][CHECK] == {"ok_at": PAGE_NOW_MS, "failed_at": None, "error": None}
    # a report that throws changes nothing
    ran = _check(lab, feed=[feed], status=[status], stored=cached, throw="boom", report_throws=True)
    assert ran["result"] == {"ok": False, "error": BOOM}
    assert ran["reported"] == ["boom"]
    assert ran["stored"][CHECK] == {"ok_at": PAGE_NOW_MS - 1, "failed_at": PAGE_NOW_MS, "error": BOOM}
    # a first read that fails on use: ok_at comes from the boundary's own re-read
    t0 = PAGE_NOW_MS - 600_000
    old = cached | {CHECK: {"ok_at": t0, "failed_at": None, "error": None}}
    ran = _check(lab, feed=[feed], status=[status], stored=old, stored_throws=True)
    assert ran["result"] == {"ok": False, "error": BOOM}
    assert ran["stored"][CHECK] == {"ok_at": t0, "failed_at": PAGE_NOW_MS, "error": BOOM}
    assert ran["stored"][FEED] == old[FEED] and ran["stored"][STATUS] == old[STATUS]


def test_a_failure_that_cannot_be_saved_still_settles(
    lab: Page, pair: tuple[bytes, bytes]
) -> None:
    feed, status = pair
    cached = _cached_pair(pair)
    for kw, want in (
        ({"feed": [503]}, {"ok": False, "error": "elections.json: HTTP 503"}),
        ({"feed": [feed], "throw": "boom"}, {"ok": False, "error": BOOM}),
    ):
        ran = _check(lab, status=[status], stored=cached, set_fails_all=True, **kw)
        assert ran["result"] == want
        assert ran["stored"] == cached
        assert ran["sets"] == [[CHECK]]  # the fake saw the failed set


def test_the_alarm_is_kept_when_a_check_rejects(lab: Page) -> None:
    ran = lab.evaluate(
        "async s => (await import('/test/fakes.js')).runHandlers(s)",
        {"call": "alarm", "arg": {"name": "elections-refresh"}, "runCheckRejects": True},
    )
    calls = ["runCheck", "ensureAlarm"]
    assert ran["log"] == [f"{name}:{edge}" for name in calls for edge in ("start", "end")]
    assert ran["rejected"] == "runCheck failed"


def test_a_hung_request_is_aborted(ext: Ext, lab: Page, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    ran = _check(lab, feed=["hang"], status=[status])
    assert ran["result"] == {"ok": False, "error": "elections.json: no response in time"}
    assert "elections.json:aborted" in ran["log"]
    ran = _check(lab, feed=[feed], status=["hang"])
    assert ran["result"]["ok"] is True and STATUS not in ran["stored"]
    assert "status.json:aborted" in ran["log"]
    assert ext.page_errors == []


# A bounded source for the stream tests. It makes at most 32 chunks of 65,536 bytes on demand (no
# prefetch: highWaterMark 0), then closes, so even a reader that buffers the whole body ends at
# 2 MiB. `bounded(out, run)` races the whole call against a 2 s page timer; on expiry the timer
# errors the source (so the work stops, not only the wait) and sets out.timedOut. `out.seen` is
# copied the moment the call settles, before any teardown can change it.
_BOUNDED_JS = """
const bounded = async (out, run) => {
  const live = { pulled: 0, ended: false, cancelled: false, pulledAtCancel: null };
  let controller = null;
  const stream = new ReadableStream({
    start(c) { controller = c; },
    pull(c) {
      if (live.pulled >= 32) { live.ended = true; c.close(); return; }
      live.pulled += 1;
      c.enqueue(new Uint8Array(65536));
    },
    cancel() { live.cancelled = true; live.pulledAtCancel = live.pulled; },
  }, { highWaterMark: 0 });
  let timedOut = false;
  let timer = null;
  const expired = new Promise((resolve) => {
    timer = setTimeout(() => {
      timedOut = true;
      try { controller.error(new Error('test deadline')); } catch { /* already closed */ }
      resolve({ expired: true });
    }, 2000);
  });
  const call = run(stream).then((value) => ({ value }), (error) => ({ error }));
  const outcome = await Promise.race([call, expired]);
  clearTimeout(timer);
  out.seen = { pulled: live.pulled, ended: live.ended, cancelled: live.cancelled, timedOut };
  return outcome;
};
"""

_READ_LIMITED = (
    """
async () => {
  const { readLimited, OverLimit } = await import('/lib/load.js');
  const out = {};
  out.exact = (await readLimited(new Response(new Uint8Array(10)), 10)).length;
  try {
    await readLimited(new Response(new Uint8Array(10)), 9);
  } catch (e) {
    out.over = [e instanceof OverLimit, e.message, e.limit];
  }
  return out;
}
"""
)

def test_a_body_is_read_up_to_its_limit(lab: Page) -> None:
    got = lab.evaluate(_READ_LIMITED)
    assert got["exact"] == 10
    assert got["over"] == [True, "over the limit of 9 bytes", 9]


_READ_LONG: Final = (
    "async () => {"
    + _BOUNDED_JS
    + """
  const { readLimited, OverLimit } = await import('/lib/load.js');
  const out = {};
  const outcome = await bounded(out, (stream) => readLimited(new Response(stream), 1000000));
  const e = outcome.error;
  out.error = e === undefined ? null : [e instanceof OverLimit, e.message];
  return out;
}
"""
)


def test_a_long_body_is_cancelled_before_its_end(lab: Page) -> None:
    started = time.monotonic()
    got = lab.evaluate(_READ_LONG)
    assert time.monotonic() - started < 2
    assert got["error"] == [True, "over the limit of 1000000 bytes"]
    seen = got["seen"]
    assert seen["timedOut"] is False
    assert seen["cancelled"] is True and seen["ended"] is False
    assert seen["pulled"] == 16  # the 16th chunk takes the total to 1,048,576 > 1,000,000


_FETCH_LIMITED: Final = (
    "async () => {"
    + _BOUNDED_JS
    + """
  const { fetchLimited, OverLimit } = await import('/lib/load.js');
  const out = { calls: [] };
  const signal = new AbortController().signal;
  const fake = (response) => (url, options) => {
    out.calls.push([url, options.cache, options.signal === signal, Object.keys(options).sort()]);
    return Promise.resolve(response);
  };
  const long = await bounded(out, (stream) => fetchLimited(
    fake(new Response(stream)), 'https://x/y.json', { signal, limit: 1000000 }));
  out.endless = long.error === undefined ? null : [long.error instanceof OverLimit, long.error.message];
  try {
    await fetchLimited(fake(new Response('', { status: 503 })), 'https://x/y.json', { signal, limit: 10 });
  } catch (e) {
    out.http = e.message;
  }
  const body = await fetchLimited(fake(new Response(new Uint8Array(10))), 'https://x/y.json', { signal, limit: 10 });
  out.length = body.length;
  return out;
}
"""
)


def test_the_real_fetch_reads_a_bounded_body(lab: Page) -> None:
    started = time.monotonic()
    got = lab.evaluate(_FETCH_LIMITED)
    assert time.monotonic() - started < 2
    assert got["endless"] == [True, "over the limit of 1000000 bytes"]
    seen = got["seen"]
    assert seen["timedOut"] is False
    assert seen["cancelled"] is True and seen["ended"] is False
    assert seen["pulled"] == 16  # the 16th chunk takes the total to 1,048,576 > 1,000,000
    assert got["http"] == "HTTP 503" and got["length"] == 10
    assert got["calls"] == [["https://x/y.json", "no-store", True, ["cache", "signal"]]] * 3


def test_an_oversized_feed_fails_the_check_in_the_worker(ext: Ext) -> None:
    ext.served.set("elections.json", b" " * 4_000_001)
    reply = _send_check(ext.lab())
    assert reply == {"ok": False, "error": "elections.json: over the limit of 4000000 bytes"}


def test_the_worker_recovers_after_an_unexpected_failure(
    ext: Ext, pair: tuple[bytes, bytes]
) -> None:
    feed, status = pair
    t0 = int(time.time() * 1000) - 60_000
    ext.seed(
        {
            FEED: feed_record(feed),
            STATUS: status_record(status),
            CHECK: {"ok_at": t0, "failed_at": None, "error": None},
        }
    )
    ext.served.set("elections.json", feed)
    ext.served.set("status.json", status)
    page = ext.popup()
    assert ext.served.log == []  # no check was due
    before = ext.storage()
    ext.worker().evaluate(
        """() => {
  const area = chrome.storage.local;
  const real = area.get.bind(area);
  let once = true;
  area.get = (keys) => {
    if (!once) return real(keys);
    once = false;
    return Promise.resolve(new Proxy({}, {
      get(_, prop) {
        if (prop === 'then') return undefined;
        throw new Error('boom');
      },
    }));
  };
}"""
    )
    started = int(time.time() * 1000)
    page.click("#refreshBtn")
    _settled(page)
    assert _cards(page) == 30
    stored = ext.storage()
    state = stored[CHECK]
    assert (state["ok_at"], state["error"]) == (t0, BOOM)
    assert state["failed_at"] >= started
    assert stored[FEED] == before[FEED] and stored[STATUS] == before[STATUS]
    assert _alarm(page) is not None
    page.click("#refreshBtn")
    _settled(page)
    state = ext.storage()[CHECK]
    assert state["error"] is None and state["failed_at"] is None  # a new check ran
    assert ext.page_errors == []


def test_a_deeply_nested_unknown_value_is_stored_safely(
    ext: Ext, pair: tuple[bytes, bytes]
) -> None:
    feed, status = pair
    depth = 10_000
    served = (
        feed.rstrip()[:-1]
        + b',"x_probe_extra":'
        + b"[" * depth
        + b"0"
        + b"]" * depth
        + b"}"
    )
    linked = _dump(json.loads(status) | {"serving_feed_sha256": _sha(served)})
    ext.served.set("elections.json", served)
    ext.served.set("status.json", linked)
    lab = ext.lab()
    assert _send_check(lab)["ok"] is True
    record = ext.storage()[FEED]
    assert record["sha256"] == _sha(served) and record["format"] == "v2"
    want = json.dumps(json.loads(feed)["months"], sort_keys=True)
    assert json.dumps(record["data"]["months"], sort_keys=True) == want
    page = ext.popup()
    assert _cards(page) == 30
    assert _send_check(lab) == {"ok": True, "changed": False}
    assert ext.page_errors == []
