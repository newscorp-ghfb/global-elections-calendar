"""Build FetchResults and RawPages for adapter tests."""

from collections.abc import Iterable
from datetime import UTC, datetime

from elections_calendar.fetch import FetchResult
from elections_calendar.model import FetchOutcome
from elections_calendar.sources.base import PageRequest, RawPage, RawPages

FETCHED = datetime(2026, 10, 16, 14, 39, tzinfo=UTC)


def result(
    body: bytes,
    *,
    url: str = "https://example.test/",
    outcome: FetchOutcome = "ok",
    status: int | None = 200,
    content_type: str = "text/html; charset=utf-8",
    api_code: str | None = None,
    final_url: str | None = None,
) -> FetchResult:
    return FetchResult(
        url=url,
        final_url=final_url or url,
        outcome=outcome,
        stage="done",
        http_status=status,
        content_type=content_type,
        body=body,
        elapsed_ms=0,
        attempts=1,
        api_code=api_code,
    )


def raw_pages(
    source: str,
    pages: Iterable[tuple[PageRequest, FetchResult]],
    unfinished: tuple[PageRequest, ...] = (),
) -> RawPages:
    return RawPages(source, tuple(RawPage(req, res, FETCHED) for req, res in pages), unfinished)
