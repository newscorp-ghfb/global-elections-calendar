"""Build FetchResults and RawPages for adapter tests."""

from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime

from elections_calendar.fetch import Deadline, FetchResult
from elections_calendar.model import Claim, DateSpan, FetchOutcome, InputUnit, Outcome, Relevance
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


class Served:
    """A ``Getter`` over fixed bodies. A known URL gives ``ok`` with its body, any other a 404.

    One content type serves every URL (only its charset matters); ``asked`` lists the URLs
    asked for, in order.
    """

    def __init__(
        self, bodies: Mapping[str, bytes], content_type: str = "text/html; charset=UTF-8"
    ) -> None:
        self._bodies = bodies
        self._content_type = content_type
        self.asked: list[str] = []

    def get(self, url: str, *, deadline: Deadline, mediawiki: bool = False) -> FetchResult:
        self.asked.append(url)
        body = self._bodies.get(url)
        if body is None:
            return result(b"", url=url, outcome="http_error", status=404)
        return result(body, url=url, content_type=self._content_type)


def raw_pages(
    source: str,
    pages: Iterable[tuple[PageRequest, FetchResult]],
    unfinished: tuple[PageRequest, ...] = (),
) -> RawPages:
    return RawPages(source, tuple(RawPage(req, res, FETCHED) for req, res in pages), unfinished)


def unit(
    source: str,
    uid: str,
    outcome: Outcome = "parsed",
    reason: str | None = None,
    *,
    duplicate_of: str | None = None,
    relevance: Relevance = "in_or_after_window",
) -> InputUnit:
    """A valid unit; ``uid`` is the full unit id (``<source>:<page>/<position>``)."""
    return InputUnit(
        unit_id=uid,
        source=source,
        text="row",
        outcome=outcome,
        reason=reason,
        relevance=relevance,
        duplicate_of=duplicate_of,
    )


def claim(unit_id: str, n: int = 0, *, source: str | None = None) -> Claim:
    """A fixed valid claim; the source defaults to the unit id's prefix."""
    return Claim(
        unit_id=unit_id,
        claim_id=f"{unit_id}#{n}",
        source=source if source is not None else unit_id.split(":", 1)[0],
        link="https://example.test/e",
        source_event_id=None,
        place_raw="Sweden",
        place_id="iso:SE",
        jurisdiction=None,
        jurisdiction_kind="nationwide",
        level="national",
        institution=None,
        office_class="legislature",
        office_label="Riksdag",
        aggregate=False,
        kind="candidate_election",
        round=None,
        span=DateSpan.day(date(2026, 9, 13)),
        date_meaning="voting_period",
        date_status="confirmed",
        date_text="13 September 2026",
        status_claim=None,
        previous_date_text=None,
        evidence_kind="calendar",
        indirect=False,
    )
