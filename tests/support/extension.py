"""The Playwright harness for the extension (Plan 5b-1 Task 1).

A hermetic persistent Chromium context loads an extension folder. Every request to the raw host is
answered from ``Served``, and every other host fails to resolve (``--host-resolver-rules``), so no
test touches the network. The worker is stopped with CDP ``Target.closeTarget`` (P136); there is no
``chrome.runtime.reload()`` (it loses the extension under ``--load-extension``).
"""

import base64
import contextlib
import hashlib
import json
import re
import shutil
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal
from urllib.parse import urlsplit

from playwright.sync_api import BrowserContext, Page, Playwright, Route, Worker

from elections_calendar.ci.recovery import republished_feed
from elections_calendar.feed import Attempt, status_doc
from elections_calendar.model import stored_json
from tests.support.artifact import _built
from tests.support.git_repos import V1_FEED

ROOT: Final = Path(__file__).resolve().parents[2]
V1_EXTENSION: Final = ROOT / "tests" / "fixtures" / "v1" / "extension"
PAGE_FILES: Final = Path(__file__).resolve().parent / "extension_page"
RAW_BASE: Final = "https://raw.githubusercontent.com/newscorp-ghfb/global-elections-calendar/main/"
PAGE_NOW: Final = "2026-10-19T14:00:00Z"  # 2 h after the fixture artifact's generated_at
PAGE_NOW_MS: Final = int(datetime(2026, 10, 19, 14, tzinfo=UTC).timestamp() * 1000)
_INSTALL_CHECK_WAIT_S: Final = 10

_STEP_S: Final = 0.1
Response = bytes | int | None | Literal["hang"]


def artifact_pair() -> tuple[bytes, bytes]:
    """(elections.json, status.json) of the fixture artifact; the artifact is built once."""
    out = _built("published")
    return (out / "elections.json").read_bytes(), (out / "status.json").read_bytes()


def fresh_v1_doc() -> dict[str, Any]:
    """The v1 feed as a document, generated 12 h before PAGE_NOW so it is not stale."""
    doc: dict[str, Any] = json.loads(v1_feed())
    doc["generated_at"] = "2026-10-19T02:00:00Z"
    return doc


def fresh_v1_feed() -> bytes:
    """The v1 feed generated 12 h before PAGE_NOW, as bytes."""
    return _dump(fresh_v1_doc())


def v1_feed() -> bytes:
    """The 2026-10-16 v1 feed, as committed."""
    return V1_FEED.read_bytes()


def extension_copy(dest: Path, *, legacy: bool) -> Path:
    """A copy of v1.0.2 (``legacy``) or of the working extension, plus ``test/``; its folder."""
    shutil.copytree(V1_EXTENSION if legacy else ROOT / "extension", dest, dirs_exist_ok=True)
    shutil.copytree(PAGE_FILES, dest / "test", dirs_exist_ok=True)
    return dest


class Served:
    """The routed raw host: per file name, a queue of responses whose last one repeats."""

    def __init__(self) -> None:
        self.log: list[str] = []
        self._responses: dict[str, tuple[Response, ...]] = {}
        self._taken: dict[str, int] = {}

    def set(self, name: str, *responses: Response) -> None:
        self._responses[name] = responses
        self._taken[name] = 0

    def reset(self) -> None:
        self._responses.clear()
        self._taken.clear()
        self.log.clear()

    def _next(self, name: str) -> Response:
        queue = self._responses.get(name, (None,))
        taken = self._taken.get(name, 0)
        self._taken[name] = taken + 1
        return queue[min(taken, len(queue) - 1)] if queue else None

    def handle(self, route: Route) -> None:
        name = urlsplit(route.request.url).path.rsplit("/", 1)[-1]
        self.log.append(name)
        response = self._next(name)
        if response is None:
            route.abort()
        elif response == "hang":
            return  # never answered
        elif isinstance(response, bytes):
            route.fulfill(
                status=200,
                body=response,
                headers={"content-type": "application/json", "access-control-allow-origin": "*"},
            )
        else:
            route.fulfill(status=response, body=b"")


class Ext:
    """One launched extension: its context, id, routed host, profile and folder."""

    def __init__(
        self,
        playwright: Playwright,
        context: BrowserContext,
        ext_id: str,
        served: Served,
        profile: Path,
        folder: Path,
        timezone_id: str,
        settle_install_check: bool = False,
    ) -> None:
        self.context = context
        self.ext_id = ext_id
        self.served = served
        self.profile = profile
        self.folder = folder
        self._playwright = playwright
        self._timezone_id = timezone_id
        self._settle_install_check = settle_install_check
        self._lab: Page | None = None
        self._anchor: Page = context.pages[0] if context.pages else context.new_page()
        self._successor: Ext | None = None
        self.page_errors: list[str] = []  # uncaught exceptions of the pages opened by `open`

    def _prefix(self) -> str:
        return f"chrome-extension://{self.ext_id}/"

    def worker(self, wait_s: float = 10) -> Worker:
        """The live worker, waiting up to ``wait_s``.

        Playwright keeps the ``Worker`` of a stopped worker (its ``close`` event never fires, and
        evaluating in it hangs), so liveness is the CDP target list.
        """
        deadline = time.monotonic() + wait_s
        while True:
            if self.worker_running():
                for candidate in self.context.service_workers:
                    if candidate.url.startswith(self._prefix()):
                        return candidate
            if time.monotonic() > deadline:
                raise TimeoutError(f"no live extension worker within {wait_s} s")
            self._anchor.wait_for_timeout(int(_STEP_S * 1000))

    def storage(self) -> dict[str, Any]:
        got: dict[str, Any] = self.lab().evaluate("() => chrome.storage.local.get(null)")
        return got

    def seed(self, values: Mapping[str, Any]) -> None:
        self.lab().evaluate("v => chrome.storage.local.set(v)", dict(values))

    def clear(self) -> None:
        self.lab().evaluate("() => chrome.storage.local.clear()")

    def open(self, path: str, *, now: str | None = PAGE_NOW) -> Page:
        if now is not None:
            self.context.clock.set_fixed_time(now)
        page = self.context.new_page()
        page.on("pageerror", lambda error: self.page_errors.append(str(error)))
        page.goto(self._prefix() + path)
        return page

    def popup(self, *, now: str | None = PAGE_NOW) -> Page:
        """The popup, once its first check has replied (``data-checking`` is ``false``)."""
        page = self.open("popup.html", now=now)
        page.wait_for_function(
            "() => document.body.dataset.state !== 'loading'"
            " && document.body.dataset.checking === 'false'"
        )
        return page

    def wait_for_install_check(self, started_ms: int) -> None:
        """Wait until the check the worker runs on install has stored its result.

        The worker's clock is the real clock, so a result is this launch's when its time is not
        before ``started_ms`` (a relaunch keeps the old storage).
        """
        deadline = time.monotonic() + _INSTALL_CHECK_WAIT_S
        while True:
            state = self.storage().get("check_state_v2")
            if isinstance(state, dict):
                newest = max(state.get("ok_at") or 0, state.get("failed_at") or 0)
                if newest >= started_ms:
                    return
            if time.monotonic() > deadline:
                raise TimeoutError(
                    f"the install check stored no result within {_INSTALL_CHECK_WAIT_S} s"
                )
            self._anchor.wait_for_timeout(int(_STEP_S * 1000))

    def opened(self, action: Callable[[], None]) -> list[str]:
        """The URLs of the tabs ``action`` opens within 5 s; the opened tabs are closed after.

        Every new page of the context counts, whatever its URL (``about:blank`` and the new-tab
        page included), so ``[]`` means no tab opened. While the action runs, every ``https``
        request outside the raw host is answered by a stub page, so an https tab keeps its URL.
        The wait ends 0.3 s after the first https request (1.5 s after a tab that makes none), or at 5 s.
        """
        requested: list[str] = []
        opened: list[Page] = []

        def stub(route: Route) -> None:
            if route.request.is_navigation_request():
                requested.append(route.request.url)
            route.fulfill(status=200, content_type="text/html", body="<title>stub</title>")

        def outside(url: str) -> bool:
            return url.startswith("https://") and not url.startswith(RAW_BASE)

        def track(page: Page) -> None:
            opened.append(page)

        before = set(self.context.pages)
        self.context.on("page", track)
        self.context.route(outside, stub)
        try:
            action()
            deadline = time.monotonic() + 5
            # an https tab is seen by the stub; a tab that never requests one gets 1.5 s to do so
            first_tab: float | None = None
            while not requested and time.monotonic() < deadline:
                if opened and first_tab is None:
                    first_tab = time.monotonic()
                if first_tab is not None and time.monotonic() - first_tab > 1.5:
                    break
                self._anchor.wait_for_timeout(int(_STEP_S * 1000))
            if opened or requested:
                self._anchor.wait_for_timeout(300)
            urls: list[str] = []
            pending = list(requested)
            for page in opened:
                with contextlib.suppress(Exception):  # a tab that closes itself has no URL to read
                    page.wait_for_load_state("load", timeout=2000)
                    url = page.url
                    # a tab on a stubbed https URL can still end on Chrome's error page
                    if url.startswith("chrome-error://") and pending:
                        url = pending.pop(0)
                    elif url.split("#")[0] in pending:  # a request carries no fragment
                        pending.remove(url.split("#")[0])
                    urls.append(url)
            return urls + pending
        finally:
            self.context.remove_listener("page", track)
            self.context.unroute(outside, stub)
            for page in list(self.context.pages):
                if page not in before:
                    page.close()

    def lab(self) -> Page:
        if self._lab is None or self._lab.is_closed():
            self._lab = self.open("test/test.html", now=None)
        return self._lab

    def close_other_pages(self) -> None:
        keep = {self._anchor, self._lab}
        for page in list(self.context.pages):
            if page not in keep:
                page.close()

    def reset(self) -> None:
        """Back to a clean slate for the next test."""
        self.close_other_pages()
        self.clear()
        self.served.reset()
        self.page_errors.clear()

    def _targets(self) -> list[dict[str, Any]]:
        browser = self.context.browser
        assert browser is not None, "a persistent context has a browser"
        session = browser.new_browser_cdp_session()
        try:
            infos: list[dict[str, Any]] = session.send("Target.getTargets")["targetInfos"]
        finally:
            session.detach()
        return [i for i in infos if i["type"] == "service_worker" and self.ext_id in i["url"]]

    def worker_running(self) -> bool:
        return bool(self._targets())

    def stop_worker(self) -> None:
        browser = self.context.browser
        assert browser is not None, "a persistent context has a browser"
        session = browser.new_browser_cdp_session()
        try:
            for info in self._targets():
                session.send("Target.closeTarget", {"targetId": info["targetId"]})
        finally:
            session.detach()
        deadline = time.monotonic() + 5
        while self._targets():
            if time.monotonic() > deadline:
                raise TimeoutError("the extension worker did not stop within 5 s")
            self._anchor.wait_for_timeout(int(_STEP_S * 1000))

    def relaunch(self) -> Ext:
        """Close the browser and launch the same profile and folder again."""
        self.context.close()
        again = launch(
            self._playwright,
            self.profile,
            self.folder,
            timezone_id=self._timezone_id,
            settle_install_check=self._settle_install_check,
        )
        self._successor = again
        return again

    def close(self) -> None:
        """Close this browser and any relaunched successor; closing twice is harmless."""
        with contextlib.suppress(Exception):  # already closed
            self.context.close()
        if self._successor is not None:
            self._successor.close()


def launch(
    playwright: Playwright,
    profile: Path,
    folder: Path,
    *,
    timezone_id: str = "UTC",
    settle_install_check: bool = False,
    worker_wait_s: float = 10,
) -> Ext:
    """Launch ``folder``; ``settle_install_check`` (working extension only) waits for its check.

    Any failure after the browser is up closes it and re-raises.
    """
    started_ms = int(time.time() * 1000)
    context = playwright.chromium.launch_persistent_context(
        str(profile),
        channel="chromium",
        headless=True,
        timezone_id=timezone_id,
        locale="en-GB",
        args=[
            f"--disable-extensions-except={folder}",
            f"--load-extension={folder}",
            "--host-resolver-rules=MAP * ~NOTFOUND",
        ],
    )
    try:
        context.set_default_timeout(10_000)
        served = Served()
        context.route(RAW_BASE + "*", served.handle)
        found = [w for w in context.service_workers if w.url.startswith("chrome-extension://")]
        worker = (
            found[0]
            if found
            else context.wait_for_event("serviceworker", timeout=int(worker_wait_s * 1000))
        )
        ext_id = worker.url.split("/")[2]
        running = Ext(
            playwright, context, ext_id, served, profile, folder, timezone_id, settle_install_check
        )
        if settle_install_check:
            running.wait_for_install_check(started_ms)
    except BaseException:
        with contextlib.suppress(Exception):  # the original error is the one to raise
            context.close()
        raise
    return running


def js(page: Page, module: str, name: str, *args: Any) -> Any:
    """Call ``module``'s export ``name`` in the page: ``(await import(module))[name](...args)``."""
    return page.evaluate(
        "async ([m, n, a]) => (await import(m))[n](...a)", ["/" + module, name, list(args)]
    )


def _real_timestamp(value: str) -> bool:
    pattern = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z"
    if not re.fullmatch(pattern, value):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return True


def _order_key(doc: Mapping[str, Any]) -> str | None:
    """P132's key: a valid ``published_at``, else a valid ``generated_at``, else None."""
    for name in ("published_at", "generated_at"):
        value = doc.get(name)
        if isinstance(value, str) and _real_timestamp(value):
            return value
    return None


def feed_record(feed: bytes, *, fmt: str = "v2", received_at: int = 0) -> dict[str, Any]:
    """The stored record (``elections_cache_v2``) of ``feed`` as the worker would write it."""
    doc = json.loads(feed)
    return {
        "data": doc,
        "sha256": hashlib.sha256(feed).hexdigest(),
        "order_key": _order_key(doc),
        "format": fmt,
        "received_at": received_at,
    }


def status_record(status: bytes) -> dict[str, Any]:
    """The stored record (``status_cache``) of ``status``."""
    return {
        "data": json.loads(status),
        "sha256": hashlib.sha256(status).hexdigest(),
        "received_at": 0,
    }


def republication(original: bytes, *, now: datetime) -> tuple[bytes, bytes]:
    """``(elections.json, status.json)`` as ``recovery.republish`` builds them from ``original``."""
    feed = republished_feed(original, now=now)
    status = stored_json(
        status_doc(
            attempt=Attempt(now, "local", "republish", "0" * 40),
            outcome="republished",
            severity="ok",
            sources=(),
            run_reasons=(),
            serving=feed,
        )
    )
    return feed, status


def _dump(doc: Any) -> bytes:
    return json.dumps(doc, separators=(",", ":")).encode("utf-8")


def published_at(feed: bytes, key: str) -> bytes:
    """``feed`` published (and generated) at ``key``."""
    doc = json.loads(feed)
    doc["published_at"] = key
    doc["generated_at"] = key
    return _dump(doc)


def linking(feed: bytes, status: bytes, attempt_at: str | None = None) -> bytes:
    """``status`` made to describe ``feed``."""
    doc = json.loads(status)
    fdoc = json.loads(feed)
    doc["serving_feed_sha256"] = hashlib.sha256(feed).hexdigest()
    doc["serving_published_at"] = fdoc["published_at"]
    doc["serving_generated_at"] = fdoc["generated_at"]
    if attempt_at is not None:
        doc["attempt_at"] = attempt_at
    return _dump(doc)


def _wire(response: Response) -> dict[str, Any]:
    if response is None:
        return {"fail": True}
    if response == "hang":
        return {"hang": True}
    if isinstance(response, bytes):
        return {"b64": base64.b64encode(response).decode("ascii")}
    return {"http": response}


def run_check(
    lab: Page,
    *,
    feed: Sequence[Response],
    status: Sequence[Response],
    stored: Mapping[str, Any],
    now: int,
    set_fails: str | None = None,
    set_fails_all: bool = False,
    timeout_ms: int = 50,
    schemas: bool = True,
    throw: str | None = None,
    report_throws: bool = False,
    stored_throws: bool = False,
) -> dict[str, Any]:
    """Run ``load.check`` on fakes in the lab page: ``{result, stored, log, sets, reported}``.

    Each request takes the next response of its list and the last repeats; ``"hang"`` never
    answers, so the deadline does (and the fake logs ``<name>:aborted``). ``schemas=False`` passes
    none. ``set_fails`` rejects the sets that hold the feed, ``set_fails_all`` every set.
    ``throw`` makes the feed schema an object whose every property read throws that message
    (so the throw comes from ``feedFormat``, in ``storedFeed`` or after the fetch),
    ``report_throws`` makes ``deps.report`` throw, and ``stored_throws`` makes the first ``get``
    resolve to an object whose every property read throws.
    """
    spec = {
        "feed": [_wire(r) for r in feed],
        "status": [_wire(r) for r in status],
        "stored": dict(stored),
        "now": now,
        "setFails": set_fails,
        "setFailsAll": set_fails_all,
        "throw": throw,
        "reportThrows": report_throws,
        "storedThrows": stored_throws,
        "timeoutMs": timeout_ms,
        "schemas": schemas,
    }
    ran: dict[str, Any] = lab.evaluate(
        "async s => (await import('/test/fakes.js')).runCheck(s)", spec
    )
    return ran


def run_pins(
    lab: Page,
    *,
    stored: Mapping[str, Any],
    verify_mismatch: bool = False,
    get_fails: str | None = None,
    set_fails: str | None = None,
) -> dict[str, Any]:
    """Run ``pins.migratePins`` once on a fake storage: ``{result, stored, sets}``.

    ``sets`` lists the keys of each ``set``. ``verify_mismatch`` makes the migrated places read
    back as something else, ``get_fails`` rejects every ``get`` and ``set_fails`` every ``set``,
    with that message.
    """
    spec = {
        "stored": dict(stored),
        "verifyMismatch": verify_mismatch,
        "getFails": get_fails,
        "setFailsAll": set_fails is not None,
        "setFailsWith": set_fails,
    }
    ran: dict[str, Any] = lab.evaluate(
        "async s => (await import('/test/fakes.js')).runPins(s)", spec
    )
    return ran


def run_pin_edits(
    lab: Page,
    *,
    stored: Mapping[str, Any],
    edits: Sequence[Mapping[str, Any]],
    set_delay_ms: int = 30,
    set_fails: Sequence[int] = (),
) -> dict[str, Any]:
    """Send every edit to one ``pins.editQueue`` without waiting: ``{replies, stored, sets}``.

    The fake storage's ``set``s take ``set_delay_ms``; ``set_fails`` holds the indexes of the
    ``set`` calls that reject (with "quota"). The replies come back in edit order.
    """
    spec = {
        "stored": dict(stored),
        "edits": [dict(e) for e in edits],
        "setDelayMs": set_delay_ms,
        "setFails": list(set_fails),
        "setFailsWith": "quota",
    }
    ran: dict[str, Any] = lab.evaluate(
        "async s => (await import('/test/fakes.js')).runPinEdits(s)", spec
    )
    return ran


_WRAP_PIN_MESSAGES: Final = """mode => {
  const real = chrome.runtime.sendMessage.bind(chrome.runtime);
  let armed = true;
  chrome.runtime.sendMessage = async (message, ...rest) => {
    if (!armed || !message || message.type !== 'PIN_EDIT') return real(message, ...rest);
    armed = false;
    if (mode === 'reject-before') {
      throw new Error('Could not establish connection. Receiving end does not exist.');
    }
    if (mode === 'no-reply') return undefined;
    const reply = real(message, ...rest);
    if (mode === 'reject-after') {
      await reply;
      throw new Error('The message port closed before a response was received.');
    }
    const gate = new Promise((resolve) => { window.__releasePinReply = resolve; });
    window.__pinReplyHeld = reply;
    await gate;
    return reply;
  };
}"""

_WRAP_PIN_READS: Final = """mode => {
  const real = chrome.storage.local.get.bind(chrome.storage.local);
  let armed = mode === 'hold-next';
  chrome.storage.local.get = async (keys, ...rest) => {
    const isPinRead = Array.isArray(keys) && keys.includes('pinned_places_v2');
    if (!isPinRead) return real(keys, ...rest);
    if (mode === 'fail') throw new Error('boom');
    if (!armed) return real(keys, ...rest);
    armed = false;
    const value = await real(keys, ...rest);
    window.__pinReadHeld = value;
    await new Promise((resolve) => { window.__releasePinRead = resolve; });
    return value;
  };
}"""

_RELEASE: Final = """async name => {
  window[name]();
  await new Promise((resolve) => setTimeout(resolve, 0));
}"""


def wrap_pin_messages(page: Page, mode: str) -> None:
    """Change the options page's next ``PIN_EDIT`` message only (and no other message).

    ``mode``: ``"hold"`` forwards it and keeps the real reply until ``release_pin_reply``;
    ``"reject-before"`` rejects without forwarding; ``"reject-after"`` forwards, awaits the real
    reply, then rejects; ``"no-reply"`` resolves ``undefined`` without forwarding.
    """
    assert mode in ("hold", "reject-before", "reject-after", "no-reply"), mode
    page.evaluate(_WRAP_PIN_MESSAGES, mode)


def release_pin_reply(page: Page) -> None:
    """Deliver the held reply; returns once one task has passed."""
    page.evaluate(_RELEASE, "__releasePinReply")


def wrap_pin_reads(page: Page, mode: str) -> None:
    """Change ``chrome.storage.local.get`` calls that read the pin keys.

    ``"hold-next"`` holds the next one's result until ``release_pin_read`` (``window.__pinReadHeld``
    is the value the real read returned); ``"fail"`` rejects every one with "boom".
    """
    assert mode in ("hold-next", "fail"), mode
    page.evaluate(_WRAP_PIN_READS, mode)


def release_pin_read(page: Page) -> None:
    """Deliver the held read; returns once one task has passed."""
    page.evaluate(_RELEASE, "__releasePinRead")


def _fresh_ids(doc: Mapping[str, Any]) -> Callable[[], str]:
    """A source of 12-hex ids that appear nowhere in ``doc``."""
    taken = set(re.findall(r'"([0-9a-f]{12})"', json.dumps(doc)))
    counter = iter(range(10**9))

    def fresh() -> str:
        while True:
            candidate = hashlib.sha256(f"synthetic-{next(counter)}".encode()).hexdigest()[:12]
            if candidate not in taken:
                taken.add(candidate)
                return candidate

    return fresh


def synthetic_feed(
    base: bytes, *, cards: int = 0, children: int = 0, items: int = 0, truncated: int = 0
) -> bytes:
    """``base`` (a v2 feed) with October grown, as bytes; schema-valid and under 4,000,000 bytes.

    October gains ``cards`` one-child cards and, when ``children`` > 0, one card with ``children``
    children. ``items`` > 0 replaces the attention items by that many fresh ones ("Synthetic item
    <n>", source ``wikipedia``; at most 500, the schema's cap). ``attention_truncated`` is
    ``truncated``. Every new id is a fresh 12-hex value.
    """
    assert 0 <= items <= 500, items
    doc = json.loads(base)
    fresh = _fresh_ids(doc)
    october: list[dict[str, Any]] = doc["months"]["2026-10"]

    def grown(country: str, count: int) -> dict[str, Any]:
        card: dict[str, Any] = json.loads(json.dumps(october[0]))
        card.update(
            group_id=fresh(), country=country, status="Upcoming", level="national",
            date="2026-10-26", end_date="2026-10-26", date_precision="day",
            date_meaning="voting_period", date_status="confirmed", umbrellas=[],
            umbrella_sources=[],
        )
        child = card["children"][0]
        child.update(
            occurrence_confirmed=False, status_conflict=False, date_conflict=False,
            possible_matches=[], possible_matches_outside=0, rescheduled_from=[],
            provisional_date=None,
        )
        child["sources"] = child["sources"][:1]
        child["sources"][0].update(selected=True, fallback=False, provisional=False, status_claim=None)
        card["children"] = [{**child, "child_id": fresh()} for _ in range(count)]
        return card

    october.extend(grown(f"Synthetic {n}", 1) for n in range(cards))
    if children > 0:
        october.append(grown("Synthetic Big", children))
    if items > 0:
        model = doc["attention_items"][0]
        doc["attention_items"] = [
            {
                **model, "item_id": fresh(), "kind": "partial_unit", "source": "wikipedia",
                "link": "https://en.wikipedia.org/wiki/Synthetic", "snapshot_id": None,
                "date": None, "text": f"Synthetic item {n}", "possible_matches": [],
                "possible_matches_outside": 0, "undated_id": None,
            }
            for n in range(items)
        ]
    doc["attention_truncated"] = truncated
    out = _dump(doc)
    assert len(out) < 4_000_000, len(out)
    return out
