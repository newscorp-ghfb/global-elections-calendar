"""Claims for merge tests: ``mk`` builds a valid claim from a unit id and field overrides."""

from datetime import UTC, date, datetime
from typing import Any

from elections_calendar.model import Claim, DateSpan

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def day(y: int, m: int, d: int) -> DateSpan:
    return DateSpan.day(date(y, m, d))


def days(y1: int, m1: int, d1: int, y2: int, m2: int, d2: int) -> DateSpan:
    return DateSpan.days(date(y1, m1, d1), date(y2, m2, d2))


def month(y: int, m: int) -> DateSpan:
    return DateSpan.month(y, m)


def months(y1: int, m1: int, y2: int, m2: int) -> DateSpan:
    return DateSpan.months(y1, m1, y2, m2)


def year(y: int) -> DateSpan:
    return DateSpan.of_year(y)


BASE: dict[str, Any] = dict(
    link="https://example.test/e",
    source_event_id=None,
    place_raw="Sweden",
    place_id="iso:SE",
    jurisdiction=None,
    jurisdiction_kind="nationwide",
    level="national",
    institution="iso:SE/riksdag",
    office_class="legislature",
    office_label="Riksdag",
    aggregate=False,
    kind="candidate_election",
    round=None,
    date_meaning="voting_period",
    date_status="unknown",
    date_text="15 November 2026",
    status_claim=None,
    previous_date_text=None,
    evidence_kind="calendar",
    indirect=False,
)
OBS: dict[str, Any] = dict(
    evidence_kind="observation",
    office_class="general",
    aggregate=True,
    kind="aggregate",
    institution=None,
    level="unknown",
    date_meaning="unknown",
    office_label="Election observation mission",
)
UMB: dict[str, Any] = dict(
    office_class="general",
    aggregate=True,
    kind="aggregate",
    institution=None,
    office_label="General elections",
)
RENEW: dict[str, Any] = dict(
    evidence_kind="expected_renewal", date_status="tentative", date_meaning="expected_window"
)


def mk(unit_id: str, n: int = 0, **fields: Any) -> Claim:
    """A valid claim; the source is the unit id's prefix, the id ``<unit_id>#<n>``."""
    values = {**BASE, **fields}
    values.setdefault("span", day(2026, 11, 15))
    return Claim(
        unit_id=unit_id, claim_id=f"{unit_id}#{n}", source=unit_id.split(":", 1)[0], **values
    )
