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


def _at(feed: bytes, key: str) -> bytes:
    """``feed`` published (and generated) at ``key``."""
    doc = json.loads(feed)
    doc["published_at"] = key
    doc["generated_at"] = key
    return _dump(doc)


def _links(feed: bytes, status: bytes, attempt_at: str | None = None) -> bytes:
    """``status`` made to describe ``feed``."""
    doc = json.loads(status)
    fdoc = json.loads(feed)
    doc["serving_feed_sha256"] = _sha(feed)
    doc["serving_published_at"] = fdoc["published_at"]
    doc["serving_generated_at"] = fdoc["generated_at"]
    if attempt_at is not None:
        doc["attempt_at"] = attempt_at
    return _dump(doc)


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
        f = _at(feed, key)
        docs[name] = (f, _links(f, status))
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
    f0, f1, f2 = (_at(feed, k) for k in (T0, T1, T2))
    stale = _elsewhere(status, "2026-10-19T06:00:00Z")
    s1 = _links(f1, status, "2026-10-19T07:00:00Z")
    s2 = _links(f2, status, "2026-10-19T08:00:00Z")
    rows: list[tuple[dict[str, Any], list[Any], list[Any], bytes, bytes, bool]] = [
        ({}, [f2, f1], [stale, s1], f2, s1, False),
        ({FEED: feed_record(f0)}, [f2, 503], [stale, stale], f2, stale, False),
        ({}, [f2, None], [stale, s2], f2, s2, True),
        ({}, [f1, f2], [stale, s2], f2, s2, True),
        ({FEED: feed_record(f2)}, [f2, f2], [stale, "hang"], f2, stale, False),
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
    later = _at(feed, ahead)
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
        (huge, "elections.json: 4000001 bytes is over the limit of 4000000"),
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


def test_a_failed_write_keeps_the_previous_pair(lab: Page, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    f2, f3 = _at(feed, T2), _at(feed, T3)
    s2, s3 = _links(f2, status), _links(f3, status)
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
        return _at(feed, stamp(moment))

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
    ("installed", {"reason": "install"}, True, ["openHelp", "ensureAlarm", "runCheck"], None),
    ("installed", {"reason": "update"}, True, ["ensureAlarm", "runCheck"], None),
    ("startup", None, True, ["ensureAlarm", "runCheck"], None),
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
    calls = ["openHelp", "ensureAlarm", "runCheck"]
    assert ran["log"] == [f"{name}:{edge}" for name in calls for edge in ("start", "end")]


def test_a_failed_write_in_the_worker_keeps_the_cache(
    fresh_ext: Ext, pair: tuple[bytes, bytes]
) -> None:
    feed, _ = pair
    f2, f3 = _at(feed, T2), _at(feed, T3)
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
    f2, f3 = _at(feed, T2), _at(feed, T3)
    s2 = _links(f2, status)
    seeded = {FEED: feed_record(f2), STATUS: status_record(s2)}
    fresh_ext.seed(seeded)
    lab = fresh_ext.lab()
    assert lab.evaluate(_FILL) == 100_000
    big = json.loads(f3)
    big["padding"] = "x" * 400_000  # an unknown top-level key: ignored by validation
    served = _dump(big)
    s3 = _links(served, status)  # describes the feed that is served, so it is in the write set
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
    f2, f3 = _at(feed, T2), _at(feed, T3)
    s2, s3 = _links(f2, status), _links(f3, status)
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
