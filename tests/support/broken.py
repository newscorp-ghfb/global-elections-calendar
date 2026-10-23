"""Adapters that fail, for the tests of what a failure leaves behind (Plan 5a Task 3).

The message holds a marker and a Windows path: neither may reach a committed file.
"""

from collections.abc import Iterator

from elections_calendar.fetch import Deadline
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
