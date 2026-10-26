"""lib/health.js, the banner, the health panel and the footer (Plan 5b-1 Task 5; P133)."""

import copy
import hashlib
import json
import time
from datetime import UTC, datetime
from typing import Any, Final

import pytest
from playwright.sync_api import Page

from tests.support.extension import (
    PAGE_NOW,
    Ext,
    artifact_pair,
    feed_record,
    js,
    republication,
    status_record,
    v1_feed,
)

HEALTH: Final = "lib/health.js"
FEED: Final = "elections_cache_v2"
STATUS: Final = "status_cache"
CHECK: Final = "check_state_v2"
HOUR: Final = 3_600_000
UNCONFIRMED: Final = "Current health can't be confirmed for this data"
NO_HEALTH: Final = "Source health isn't available for this data"
FAILED: Final = "The latest update failed its checks — showing the last good data"
UPDATE: Final = "This data is newer than this extension — update the extension"
UNTIL: Final = "2027-01-01T00:00:00Z"


def _ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dump(doc: Any) -> bytes:
    return json.dumps(doc, separators=(",", ":")).encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now_ms() -> int:
    return int(time.time() * 1000)


@pytest.fixture(scope="module")
def pair() -> tuple[bytes, bytes]:
    return artifact_pair()


@pytest.fixture(scope="module")
def feed_doc(pair: tuple[bytes, bytes]) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(pair[0])
    return doc


@pytest.fixture(scope="module")
def status_doc(pair: tuple[bytes, bytes]) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(pair[1])
    return doc


def _source(doc: dict[str, Any], key: str) -> dict[str, Any]:
    found: dict[str, Any] = next(s for s in doc["source_health"] if s["source"] == key)
    return found


def _acknowledge(entry: dict[str, Any], reason: dict[str, Any], until: str = UNTIL) -> None:
    entry["acknowledged"].append(
        {k: reason[k] for k in ("code", "stage", "year", "page")} | {"until": until}
    )


def _acknowledge_all(doc: dict[str, Any]) -> None:
    for entry in doc["source_health"]:
        for reason in entry["reasons"]:
            if reason["level"] in ("error", "warning"):
                _acknowledge(entry, reason)


def _banner(page: Page, **kw: Any) -> dict[str, str]:
    result: dict[str, str] = js(page, HEALTH, "bannerState", kw)
    return result


def _g(doc: dict[str, Any]) -> int:
    return _ms(doc["generated_at"])


def test_banner_conditions_in_order(
    lab: Page, feed_doc: dict[str, Any], status_doc: dict[str, Any]
) -> None:
    g = _g(feed_doc)
    now = g + 2 * HOUR
    # the first nine of P133, worst first; a row that names no status passes S, linked
    ipu_error = copy.deepcopy(feed_doc)
    reason = _source(ipu_error, "ipu")["reasons"][0]
    reason["level"], reason["code"] = "error", "unavailable"
    ipu_acked = copy.deepcopy(ipu_error)
    _acknowledge(_source(ipu_acked, "ipu"), reason)
    all_acked = copy.deepcopy(feed_doc)
    _acknowledge_all(all_acked)
    no_reasons = copy.deepcopy(feed_doc)
    for entry in no_reasons["source_health"]:
        entry["reasons"] = []
    failed = status_doc | {"outcome": "validation_failed"}
    unknown = copy.deepcopy(feed_doc)
    unknown["schema_version"] = 3
    v1 = json.loads(v1_feed())
    v1_now = _ms(v1["generated_at"]) + 2 * HOUR
    republished_bytes, republished_status = republication(
        v1_feed(), now=datetime.fromisoformat(PAGE_NOW.replace("Z", "+00:00"))
    )
    republished = json.loads(republished_bytes)
    rep_status = json.loads(republished_status)
    rep_now = _g(republished) + 2 * HOUR
    s = status_doc
    rows: list[tuple[str, dict[str, Any], str, str, str]] = [
        (
            "warnings",
            {"format": "v2", "doc": feed_doc, "status": s, "linked": True, "now": now},
            "amber", "7 warnings", "7 warnings",
        ),
        (
            "error",
            {"format": "v2", "doc": ipu_error, "status": s, "linked": True, "now": now},
            "red", "1 source error", "1 error · 6 warnings",
        ),
        (
            "error acknowledged",
            {"format": "v2", "doc": ipu_acked, "status": s, "linked": True, "now": now},
            "amber", "6 warnings", "6 warnings · 1 acknowledged",
        ),
        (
            "all acknowledged",
            {"format": "v2", "doc": all_acked, "status": s, "linked": True, "now": now},
            "grey", "7 acknowledged issues: Wikipedia unparsed relevant", "7 acknowledged",
        ),
        (
            "no reasons",
            {"format": "v2", "doc": no_reasons, "status": s, "linked": True, "now": now},
            "ok", "All sources OK", "",
        ),
        (
            "failed, linked",
            {"format": "v2", "doc": feed_doc, "status": failed, "linked": True, "now": now},
            "red", FAILED, "7 warnings",
        ),
        (
            "failed, not linked",
            {"format": "v2", "doc": feed_doc, "status": failed, "linked": False, "now": now},
            "amber", UNCONFIRMED, "7 warnings",
        ),
        (
            "no status",
            {"format": "v2", "doc": feed_doc, "status": None, "linked": False, "now": now},
            "amber", UNCONFIRMED, "7 warnings",
        ),
        (
            "stale",
            {"format": "v2", "doc": feed_doc, "status": s, "linked": True, "now": g + 36 * HOUR + 1000},
            "red", "Data is 36 hours old — the daily update hasn't arrived", "7 warnings",
        ),
        (
            "update needed",
            {"format": "update_needed", "doc": unknown, "status": s, "linked": True, "now": now},
            "amber", UPDATE, "",
        ),
        (
            "v1, status of the republication",
            {"format": "legacy", "doc": v1, "status": rep_status, "linked": False, "now": v1_now},
            "amber", UNCONFIRMED, "",
        ),
        (
            "republished, linked",
            {"format": "legacy", "doc": republished, "status": rep_status, "linked": True, "now": rep_now},
            "amber", NO_HEALTH, "",
        ),
        (
            "republished, no status",
            {"format": "legacy", "doc": republished, "status": None, "linked": False, "now": rep_now},
            "amber", UNCONFIRMED, "",
        ),
        (
            "republished, stale",
            {"format": "legacy", "doc": republished, "status": rep_status, "linked": True, "now": _g(republished) + 37 * HOUR},
            "red", "Data is 37 hours old — the daily update hasn't arrived", "",
        ),
        (
            "republished, failed",
            {
                "format": "legacy", "doc": republished,
                "status": rep_status | {"outcome": "validation_failed"},
                "linked": True, "now": rep_now,
            },
            "red", FAILED, "",
        ),
    ]
    for name, args, level, text, counts in rows:
        assert _banner(lab, **args) == {"level": level, "text": text, "counts": counts}, name


def test_banner_plurals(lab: Page, feed_doc: dict[str, Any], status_doc: dict[str, Any]) -> None:
    now = _g(feed_doc) + 2 * HOUR
    one = copy.deepcopy(feed_doc)
    for entry in one["source_health"]:
        entry["reasons"] = [r for r in entry["reasons"] if r["level"] == "info"]
    reasons = _source(feed_doc, "ipu")["reasons"]
    for source, level, text, counts in (
        ("ipu", "warning", "1 warning", "1 warning"),
        ("ipu", "error", "1 source error", "1 error"),
    ):
        doc = copy.deepcopy(one)
        _source(doc, source)["reasons"] = [copy.deepcopy(reasons[0]) | {"level": level}]
        args = {"format": "v2", "doc": doc, "status": status_doc, "linked": True, "now": now}
        assert _banner(lab, **args)["text"] == text
        assert _banner(lab, **args)["counts"] == counts
    acked = copy.deepcopy(one)
    ipu = _source(acked, "ipu")
    ipu["reasons"] = [copy.deepcopy(reasons[0]), copy.deepcopy(reasons[0]) | {"code": "unavailable"}]
    for r in ipu["reasons"]:
        _acknowledge(ipu, r)
    args = {"format": "v2", "doc": acked, "status": status_doc, "linked": True, "now": now}
    assert _banner(lab, **args)["text"] == "2 acknowledged issues: IPU unparsed relevant"
    ipu["reasons"] = ipu["reasons"][:1]
    ipu["acknowledged"] = ipu["acknowledged"][:1]
    assert _banner(lab, **args)["text"] == "1 acknowledged issue: IPU unparsed relevant"
    errors = copy.deepcopy(one)
    _source(errors, "ipu")["reasons"] = [copy.deepcopy(reasons[0]) | {"level": "error"}] * 2
    args = {"format": "v2", "doc": errors, "status": status_doc, "linked": True, "now": now}
    assert _banner(lab, **args) == {"level": "red", "text": "2 source errors", "counts": "2 errors"}


def test_freshness_thresholds_and_clock_skew(
    lab: Page, feed_doc: dict[str, Any], status_doc: dict[str, Any]
) -> None:
    g = _g(feed_doc)

    def banner(now: int) -> dict[str, str]:
        return _banner(lab, format="v2", doc=feed_doc, status=status_doc, linked=True, now=now)

    def data(now: int) -> str:
        foot: dict[str, str] = js(lab, HEALTH, "footerState", {"doc": feed_doc, "check": None, "now": now})
        return foot["data"]

    assert banner(g + 36 * HOUR)["level"] == "amber"
    assert banner(g + 36 * HOUR + 1)["level"] == "red"
    assert banner(g - 2 * HOUR)["level"] == "amber"
    assert data(g - 2 * HOUR).endswith(" (ahead of this computer's clock)")
    assert "ahead" not in data(g - 9 * 60_000)
    assert data(g - 11 * 60_000).endswith(" (ahead of this computer's clock)")
    assert banner(g + 40 * HOUR)["text"] == "Data is 40 hours old — the daily update hasn't arrived"
    limits = lab.evaluate(
        "async () => { const h = await import('/lib/health.js');"
        " return [h.STALE_MS, h.AHEAD_MS, h.AS_OF_GAP_MS]; }"
    )
    assert limits == [129_600_000, 600_000, 86_400_000]


def test_the_footer(lab: Page, feed_doc: dict[str, Any]) -> None:
    g = _g(feed_doc)
    now = g + 2 * HOUR
    moved = copy.deepcopy(feed_doc)
    moved["data_as_of"] = _iso(g - 24 * HOUR)
    nulled = copy.deepcopy(feed_doc)
    nulled["data_as_of"] = None
    v1 = json.loads(v1_feed())
    ok = _ms("2026-10-19T13:58:00Z")
    failed = _ms("2026-10-19T13:59:00Z")
    error = "elections.json: HTTP 503"
    cases: list[tuple[dict[str, Any], Any, str, str | None]] = [
        (feed_doc, None, "Data as of 19 Oct 2026, 12:00 · oldest source data 16 Oct 2026, 14:39", None),
        (moved, None, "Data as of 19 Oct 2026, 12:00", None),
        (nulled, None, "Data as of 19 Oct 2026, 12:00", None),
        (v1, None, "Data as of 16 Oct 2026, 00:02", None),
        (feed_doc, {"ok_at": ok, "failed_at": None, "error": None}, "", "Checked 19 Oct 2026, 13:58"),
        (
            feed_doc,
            {"ok_at": ok, "failed_at": failed, "error": error},
            "",
            "Checked 19 Oct 2026, 13:58 · couldn't check at 19 Oct 2026, 13:59: elections.json: HTTP 503",
        ),
        (
            feed_doc,
            {"ok_at": None, "failed_at": failed, "error": error},
            "",
            "Couldn't check at 19 Oct 2026, 13:59: elections.json: HTTP 503",
        ),
        (feed_doc, None, "", "Not checked yet"),
        # a failure older than the success is not mentioned
        (feed_doc, {"ok_at": failed, "failed_at": ok, "error": error}, "", "Checked 19 Oct 2026, 13:59"),
        # malformed check states count as absent
        (feed_doc, {"ok_at": "x", "failed_at": None, "error": None}, "", "Not checked yet"),
        (feed_doc, {"ok_at": None, "failed_at": float("nan"), "error": "e"}, "", "Not checked yet"),
        (feed_doc, {"ok_at": ok, "failed_at": "late", "error": "e"}, "", "Checked 19 Oct 2026, 13:58"),
    ]
    for doc, check, data, checked in cases:
        got: dict[str, str] = js(lab, HEALTH, "footerState", {"doc": doc, "check": check, "now": now})
        if checked is None:
            assert got["data"] == data
        else:
            assert got["checked"] == checked
    for missing in (None, "text", 5):
        got = js(lab, HEALTH, "footerState", {"doc": feed_doc, "check": missing, "now": now})
        assert got["checked"] == "Not checked yet"


def test_acknowledged_issues_describe_the_real_condition(
    lab: Page, feed_doc: dict[str, Any]
) -> None:
    def found(doc: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        got: dict[str, list[dict[str, Any]]] = js(lab, HEALTH, "issues", doc)
        return got

    base = found(feed_doc)
    assert len(base["warnings"]) == 7 and base["errors"] == [] and base["acknowledged"] == []
    assert base["warnings"][0]["source"] == "Wikipedia"
    assert base["warnings"][0]["code"] == "unparsed_relevant"
    assert all(i["code"] != "not_published_yet" for i in base["warnings"])  # info is in no list

    doc = copy.deepcopy(feed_doc)
    ipu = _source(doc, "ipu")
    reason = ipu["reasons"][0]
    reason["level"], reason["code"], reason["text"] = "error", "unavailable", "IPU is down"
    _acknowledge(ipu, reason)
    got = found(doc)
    assert got["errors"] == []
    assert got["acknowledged"] == [
        {"source": "IPU", "code": "unavailable", "text": "IPU is down", "until": _ms(UNTIL)}
    ]

    twice = copy.deepcopy(doc)
    _source(twice, "ipu")["reasons"].append(copy.deepcopy(reason))
    got = found(twice)
    assert len(got["acknowledged"]) == 1 and len(got["errors"]) == 1
    assert got["errors"][0]["until"] is None

    other_page = copy.deepcopy(doc)
    _source(other_page, "ipu")["acknowledged"][0]["page"] = "elsewhere"
    got = found(other_page)
    assert got["acknowledged"] == [] and len(got["errors"]) == 1

    with_run = copy.deepcopy(feed_doc)
    base_reason = {"code": "worker_failed", "stage": "run", "year": None, "page": None}
    with_run["run"]["reasons"] = [
        base_reason | {"level": "warning", "text": "slow"},
        base_reason | {"level": "error", "text": "broke"},
        base_reason | {"level": "info", "text": "fyi"},
    ]
    got = found(with_run)
    assert [(i["source"], i["text"]) for i in got["warnings"] if i["source"] == "Run"] == [("Run", "slow")]
    assert [(i["source"], i["text"]) for i in got["errors"]] == [("Run", "broke")]


def test_panel_rows(lab: Page, feed_doc: dict[str, Any], status_doc: dict[str, Any]) -> None:
    def rows(doc: dict[str, Any], *, fmt: str = "v2", linked: bool = True) -> list[dict[str, Any]]:
        got: list[dict[str, Any]] = js(
            lab, HEALTH, "panelRows",
            {"format": fmt, "doc": doc, "status": status_doc, "linked": linked},
        )
        return got

    keys = [s["source"] for s in feed_doc["source_health"]]
    got = rows(feed_doc)
    assert [r["source"] for r in got] == ["latest", *keys]
    assert got[0]["severity"] == "warning"
    assert got[0]["lines"] == ["Latest attempt 19 Oct 2026, 12:00: published"]
    wikipedia = next(r for r in got if r["source"] == "wikipedia")
    assert wikipedia["lines"] == [r["text"] for r in _source(feed_doc, "wikipedia")["reasons"]]
    assert len(wikipedia["lines"]) == 2
    assert [r["source"] for r in rows(feed_doc, linked=False)] == keys
    assert rows(feed_doc, fmt="legacy") == [] and rows(feed_doc, fmt="update_needed") == []

    doc = copy.deepcopy(feed_doc)
    ipu = _source(doc, "ipu")
    _acknowledge(ipu, ipu["reasons"][0])
    line = next(r for r in rows(doc) if r["source"] == "ipu")["lines"][0]
    assert line == ipu["reasons"][0]["text"] + " (acknowledged until 1 Jan 2027)"

    doc["run"]["reasons"] = [
        {"code": "worker_failed", "stage": "run", "year": None, "page": None, "level": "error", "text": "broke"}
    ]
    last = rows(doc)[-1]
    assert (last["source"], last["severity"], last["lines"]) == ("run", "error", ["broke"])


def _cards(page: Page) -> int:
    return page.locator(".election-item").count()


def _settled(page: Page) -> None:
    page.wait_for_function(
        "() => document.body.dataset.state === 'ready' && document.body.dataset.checking === 'false'"
    )


def _fresh_check() -> dict[str, Any]:
    return {"ok_at": _now_ms(), "failed_at": None, "error": None}


def test_a_newer_failure_is_not_erased(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    s = json.loads(status)
    attempt = _ms(s["attempt_at"])
    failed = _dump(s | {"outcome": "validation_failed", "attempt_at": _iso(attempt + 6 * HOUR)})
    ext.seed({FEED: feed_record(feed), STATUS: status_record(failed)})
    ext.served.set("elections.json", feed)
    ext.served.set("status.json", status)
    page = ext.popup()
    assert "status.json" in ext.served.log  # no check state, so a check was due
    assert page.locator("#bannerText").text_content() == FAILED
    assert ext.storage()[STATUS]["sha256"] == _sha(failed)

    later = _dump(s | {"attempt_at": _iso(attempt + 12 * HOUR)})
    ext.served.set("status.json", later)
    page.click("#refreshBtn")
    _settled(page)
    assert page.locator("#bannerText").text_content() == "7 warnings"
    assert ext.storage()[STATUS]["sha256"] == _sha(later)


def test_banner_and_panel_in_the_popup(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    ext.served.set("elections.json", feed)
    ext.served.set("status.json", status)
    page = ext.popup()
    banner = page.locator("#banner")
    assert banner.get_attribute("data-level") == "amber"
    assert page.locator("#bannerText").text_content() == "7 warnings"
    assert page.locator("#bannerCounts").text_content() == "7 warnings"
    assert banner.get_attribute("aria-expanded") == "false"
    assert page.locator("#healthPanel").is_hidden()

    banner.click()
    assert banner.get_attribute("aria-expanded") == "true"
    assert page.locator("#healthPanel").is_visible()
    rows = page.locator("#healthList > li")
    assert rows.count() == 10
    keys = [s["source"] for s in json.loads(feed)["source_health"]]
    assert [rows.nth(i).get_attribute("data-source") for i in range(10)] == ["latest", *keys]
    wikipedia = json.loads(feed)["source_health"][2]
    text = page.locator("#healthList > li[data-source=wikipedia]").text_content() or ""
    assert all(r["text"] in text for r in wikipedia["reasons"]) and len(wikipedia["reasons"]) == 2
    assert page.locator("#healthNote").text_content() == ""
    banner.click()
    assert banner.get_attribute("aria-expanded") == "false"
    assert page.locator("#healthPanel").is_hidden()

    assert page.locator("#footerData").text_content() == (
        "Data as of 19 Oct 2026, 12:00 · oldest source data 16 Oct 2026, 14:39"
    )
    assert (page.locator("#footerChecked").text_content() or "").startswith("Checked ")
    assert ext.page_errors == []


def test_an_open_panel_is_rebuilt_by_the_next_render(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, status = pair
    ext.served.set("elections.json", feed)
    ext.served.set("status.json", status)
    page = ext.popup()
    page.click("#banner")
    assert page.locator("#healthList > li").count() == 10
    # the next status is about another feed: no "latest" row, and the open panel shows that
    other = _dump(json.loads(status) | {"serving_feed_sha256": "0" * 64})
    ext.seed({STATUS: status_record(other)})
    ext.served.set("elections.json", 503)
    page.click("#refreshBtn")
    _settled(page)
    assert page.locator("#healthPanel").is_visible()
    assert page.locator("#healthList > li").count() == 9
    assert page.locator("#bannerText").text_content() == UNCONFIRMED


def test_no_banner_without_data(ext: Ext) -> None:
    ext.served.set("elections.json", 503)
    page = ext.popup()
    assert page.locator("#stateError").is_visible()
    assert page.locator("#banner").is_hidden()
    assert page.locator("#healthPanel").is_hidden()


def test_rollback_v1_feed_shows_the_mismatch_banner(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, _ = pair
    page_now = datetime.fromisoformat(PAGE_NOW.replace("Z", "+00:00"))
    doc = json.loads(v1_feed())
    doc["generated_at"] = _iso(int(page_now.timestamp() * 1000) - 12 * HOUR)
    _, republished_status = republication(feed, now=page_now)
    ext.seed(
        {
            FEED: feed_record(_dump(doc), fmt="legacy"),
            STATUS: status_record(republished_status),
            CHECK: _fresh_check(),
        }
    )
    page = ext.popup()
    assert ext.served.log == []
    assert _cards(page) == 27
    assert page.locator("#bannerText").text_content() == UNCONFIRMED
    assert page.locator("#banner").get_attribute("data-level") == "amber"
    assert page.locator("#healthNote").text_content() == NO_HEALTH
    page.click("#banner")
    assert page.locator("#healthNote").is_visible()
    assert page.locator("#healthList > li").count() == 0


def test_an_unknown_version_shows_the_update_banner(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, _ = pair
    doc = json.loads(feed)
    doc["schema_version"] = 3
    ext.seed({FEED: feed_record(_dump(doc), fmt="update_needed"), CHECK: _fresh_check()})
    page = ext.popup()
    assert _cards(page) == 30
    assert page.locator("#bannerText").text_content() == UPDATE
    assert page.locator("#healthNote").text_content() == NO_HEALTH


def test_health_text_is_inserted_as_text(ext: Ext, pair: tuple[bytes, bytes]) -> None:
    feed, _ = pair
    hostile = '<img src=x onerror="document.title=1">'
    doc = json.loads(feed)
    doc["source_health"][2]["reasons"][0]["text"] = hostile
    ext.seed({FEED: feed_record(_dump(doc)), CHECK: _fresh_check()})
    page = ext.popup()
    page.click("#banner")
    row = page.locator("#healthList > li[data-source=wikipedia]")
    assert hostile in (row.text_content() or "")
    assert page.locator("#healthPanel img").count() == 0
    assert page.title() != "1"
    assert ext.page_errors == []
