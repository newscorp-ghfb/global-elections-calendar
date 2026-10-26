"""The Playwright harness for the extension (Plan 5b-1 Task 1).

A hermetic persistent Chromium context loads an extension folder. Every request to the raw host is
answered from ``Served``, and every other host fails to resolve (``--host-resolver-rules``), so no
test touches the network. The worker is stopped with CDP ``Target.closeTarget`` (P136); there is no
``chrome.runtime.reload()`` (it loses the extension under ``--load-extension``).
"""

import contextlib
import shutil
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, Literal
from urllib.parse import urlsplit

from playwright.sync_api import BrowserContext, Page, Playwright, Route, Worker

from tests.support.artifact import _built
from tests.support.git_repos import V1_FEED

ROOT: Final = Path(__file__).resolve().parents[2]
V1_EXTENSION: Final = ROOT / "tests" / "fixtures" / "v1" / "extension"
PAGE_FILES: Final = Path(__file__).resolve().parent / "extension_page"
RAW_BASE: Final = "https://raw.githubusercontent.com/newscorp-ghfb/global-elections-calendar/main/"
PAGE_NOW: Final = "2026-10-19T14:00:00Z"  # 2 h after the fixture artifact's generated_at

_STEP_S: Final = 0.1
Response = bytes | int | None | Literal["hang"]


def artifact_pair() -> tuple[bytes, bytes]:
    """(elections.json, status.json) of the fixture artifact; the artifact is built once."""
    out = _built("published")
    return (out / "elections.json").read_bytes(), (out / "status.json").read_bytes()


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
    ) -> None:
        self.context = context
        self.ext_id = ext_id
        self.served = served
        self.profile = profile
        self.folder = folder
        self._playwright = playwright
        self._timezone_id = timezone_id
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
            self._playwright, self.profile, self.folder, timezone_id=self._timezone_id
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
    playwright: Playwright, profile: Path, folder: Path, *, timezone_id: str = "UTC"
) -> Ext:
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
    context.set_default_timeout(10_000)
    served = Served()
    context.route(RAW_BASE + "*", served.handle)
    found = [w for w in context.service_workers if w.url.startswith("chrome-extension://")]
    worker = found[0] if found else context.wait_for_event("serviceworker", timeout=10_000)
    ext_id = worker.url.split("/")[2]
    return Ext(playwright, context, ext_id, served, profile, folder, timezone_id)


def js(page: Page, module: str, name: str, *args: Any) -> Any:
    """Call ``module``'s export ``name`` in the page: ``(await import(module))[name](...args)``."""
    return page.evaluate(
        "async ([m, n, a]) => (await import(m))[n](...a)", ["/" + module, name, list(args)]
    )
