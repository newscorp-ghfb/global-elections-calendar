"""Small adapters for the runner tests, built and run inside the worker process.

Each takes its settings as string keyword options, like a real ``AdapterSpec``.
They never resolve a real host name: the ones that fail in the network layer
patch resolution and connecting inside the worker.
"""

import os
import signal
import socket
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

from elections_calendar.fetch import Deadline, FetchResult
from elections_calendar.sources.base import (
    Getter,
    PageRequest,
    ParseResult,
    RawPage,
    RawPages,
    Registries,
    fetch_pages,
)
from elections_calendar.window import Window

KEYS = ("one", "two", "three", "four", "five", "six")


def fake_page(key: str) -> RawPage:
    """A finished page that needed no network."""
    result = FetchResult(
        url="https://fake.test/",
        final_url="https://fake.test/",
        outcome="ok",
        stage="done",
        http_status=200,
        content_type="text/html",
        body=b"fake",
        elapsed_ms=0,
        attempts=1,
    )
    return RawPage(PageRequest(key, "https://fake.test/"), result, datetime.now(UTC))


class _Base:
    source = "test"

    def requests(self, window: Window) -> tuple[PageRequest, ...]:
        return ()

    def parse(self, raw: RawPages, window: Window, registries: Registries) -> ParseResult:
        raise NotImplementedError("the runner tests never parse")


class Pages(_Base):
    """Fetches the comma-separated test-server URLs; keys ``one``, ``two``, ..."""

    def __init__(self, urls: str) -> None:
        self._requests = tuple(
            PageRequest(KEYS[number], url) for number, url in enumerate(urls.split(","))
        )

    def requests(self, window: Window) -> tuple[PageRequest, ...]:
        return self._requests

    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        return fetch_pages(self._requests, fetcher, deadline)


class DripHeaders(Pages):
    """One test-server URL whose server sends its headers a byte at a time."""

    def __init__(self, url: str) -> None:
        super().__init__(url)


class _OnePage(_Base):
    """Base for adapters with the single page ``one``, requested from ``url``.

    ``SlowDns`` and ``LatePage`` use ``https://slow.test/``; ``FailingAddresses`` names its own.
    """

    url = "https://slow.test/"

    def requests(self, window: Window) -> tuple[PageRequest, ...]:
        return (PageRequest("one", self.url),)


class SlowDns(_OnePage):
    """Name resolution takes 30 s and then fails."""

    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        def slow(*args: Any, **kwargs: Any) -> NoReturn:
            time.sleep(30)
            raise socket.gaierror("resolution gave up")

        socket.getaddrinfo = slow
        return fetch_pages(self.requests(window), fetcher, deadline)


class FailingAddresses(_OnePage):
    """The name resolves to 4 addresses and connecting to each takes 1 s and fails."""

    url = "https://failing.test/"

    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        def resolve(host: str, port: int, *args: Any, **kwargs: Any) -> list[Any]:
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", (f"192.0.2.{n}", port))
                for n in range(1, 5)
            ]

        def connect(self: socket.socket, address: Any) -> NoReturn:
            time.sleep(1)
            raise ConnectionRefusedError("test address refused")

        socket.getaddrinfo = resolve  # type: ignore[assignment]
        socket.socket.connect = connect  # type: ignore[method-assign,assignment]
        return fetch_pages(self.requests(window), fetcher, deadline)


class Sleeper(_Base):
    """Writes its start and end ``time.time()`` to ``record`` and yields nothing."""

    def __init__(self, seconds: str, record: str = "") -> None:
        self._seconds = float(seconds)
        self._record = record

    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        started = time.time()
        time.sleep(self._seconds)
        if self._record:
            Path(self._record).write_text(f"{started} {time.time()}", encoding="utf-8")
        return iter(())


class IgnoreTerm(_Base):
    """Ignores SIGTERM where the platform has it, then sleeps."""

    def __init__(self, seconds: str) -> None:
        self._seconds = float(seconds)

    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        if os.name == "posix":
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
        time.sleep(self._seconds)
        return iter(())


class LatePage(_OnePage):
    """Sleeps, then yields one page."""

    def __init__(self, seconds: str) -> None:
        self._seconds = float(seconds)

    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        time.sleep(self._seconds)
        yield fake_page("one")


class StallMidWrite(_OnePage):
    """The patched ``os.replace`` sleeps 30 s and returns without replacing anything, so the
    page stays an unpublished ``.tmp`` file. It first writes a marker file to ``record``.
    """

    def __init__(self, record: str = "") -> None:
        self._record = record

    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        record = self._record

        def stall(*args: Any, **kwargs: Any) -> None:
            if record:
                Path(record).write_text("stalled", encoding="utf-8")
            time.sleep(30)

        os.replace = stall
        yield fake_page("one")


class CrashAfterPage(_Base):
    """Yields page ``one`` (a real fetch of ``url``), then the process dies with code 3."""

    def __init__(self, url: str) -> None:
        self._requests = (PageRequest("one", url), PageRequest("two", "https://never.test/"))

    def requests(self, window: Window) -> tuple[PageRequest, ...]:
        return self._requests

    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        yield from fetch_pages(self._requests[:1], fetcher, deadline)
        os._exit(3)


class Raise(_Base):
    """Raises an error whose message carries a URL with a secret."""

    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        raise RuntimeError("https://x.test/?token=abc")


class Crash(_Base):
    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        os._exit(3)
