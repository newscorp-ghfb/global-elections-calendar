"""The harness itself: routing, the worker's stop, relaunching and the module importer."""

import pytest
from playwright.sync_api import Page

from tests.support.extension import RAW_BASE, Ext, js


def test_pure_modules_import_in_an_extension_page(lab: Page) -> None:
    assert js(lab, "test/probe.js", "answer", 40, 2) == 42


def test_requests_are_routed_and_nothing_else_resolves(ext: Ext) -> None:
    ext.served.set("elections.json", b'{"x": 1}')
    page = ext.open("test/test.html")
    got = page.evaluate("u => fetch(u).then(r => r.text())", RAW_BASE + "elections.json")
    assert got == '{"x": 1}' and ext.served.log == ["elections.json"]
    failed = page.evaluate(  # no-cors: a reachable host resolves (opaque); only DNS fails
        "() => fetch('https://example.com/', {mode: 'no-cors'}).then(() => 'ok', e => e.name)"
    )
    assert failed == "TypeError"


def test_served_answers_each_kind(ext: Ext) -> None:
    ext.served.set("elections.json", b"one", 404)
    ext.served.set("status.json", None)
    page = ext.open("test/test.html")
    probe = "u => fetch(u).then(async r => [r.status, await r.text()], e => e.name)"
    url = RAW_BASE + "elections.json"
    assert page.evaluate(probe, url) == [200, "one"]
    assert page.evaluate(probe, url) == [404, ""]
    assert page.evaluate(probe, url) == [404, ""]  # the last response repeats
    assert page.evaluate(probe, RAW_BASE + "status.json") == "TypeError"
    assert page.evaluate(probe, RAW_BASE + "never-set.json") == "TypeError"
    assert ext.served.log == [
        "elections.json",
        "elections.json",
        "elections.json",
        "status.json",
        "never-set.json",
    ]


def test_the_worker_can_be_stopped_and_woken(ext: Ext) -> None:
    ext.stop_worker()
    assert not ext.worker_running()
    page = ext.open("test/test.html")
    page.evaluate("() => chrome.runtime.sendMessage({type: 'PING'}).catch(() => null)")
    page.wait_for_timeout(500)
    assert ext.worker_running()


def test_a_relaunch_keeps_the_id_and_storage(fresh_ext: Ext) -> None:
    fresh_ext.seed({"probe": [1, 2]})
    old = fresh_ext.ext_id
    again = fresh_ext.relaunch()
    assert again.ext_id == old and again.storage()["probe"] == [1, 2]


def test_a_stopped_worker_is_not_the_live_one(ext: Ext) -> None:
    ext.stop_worker()
    with pytest.raises(TimeoutError):
        ext.worker(wait_s=0.5)
    page = ext.open("test/test.html")
    page.evaluate("() => chrome.runtime.sendMessage({type: 'PING'}).catch(() => null)")
    assert ext.worker().evaluate("() => 1") == 1


def test_page_errors_are_collected(ext: Ext) -> None:
    page = ext.open("test/test.html")
    page.evaluate("() => queueMicrotask(() => { throw new Error('boom'); })")
    page.wait_for_timeout(300)
    assert ext.page_errors == ["boom"]
