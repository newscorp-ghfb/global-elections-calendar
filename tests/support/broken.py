"""Adapters that fail, for the tests of what a failure leaves behind (Plan 5a Task 3).

The message holds a marker and a Windows path: neither may reach a committed file.
"""

from collections.abc import Iterator
from typing import Any

import pytest

from elections_calendar import pipeline
from elections_calendar.fetch import Deadline
from elections_calendar.runner import ScrapeRun, SourceRun
from elections_calendar.sources.base import (
    Getter,
    ParseResult,
    RawPage,
    RawPages,
    Registries,
)
from elections_calendar.sources.osce import Osce
from elections_calendar.window import Window

MESSAGE = "boom-7f3a C:/Users/someone/secret"


class BrokenParse(Osce):
    def parse(self, raw: RawPages, window: Window, registries: Registries) -> ParseResult:
        raise RuntimeError(MESSAGE)


class BrokenFetch(Osce):
    def fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]:
        raise RuntimeError(MESSAGE)


def fail_the_parse_of_an_unfinished_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """The stand-in of two pipeline tests: every OSCE request is unfinished, then its parse raises."""

    def fake(specs: Any, window: Any, **kwargs: Any) -> ScrapeRun:
        raw = RawPages("osce", (), Osce().requests(window))
        return ScrapeRun((), (SourceRun("osce", raw, "complete", 0),))

    def boom(self: Osce, *args: object) -> None:
        raise ValueError("x")

    monkeypatch.setattr(pipeline, "run_sources", fake)
    monkeypatch.setattr(Osce, "parse", boom)
