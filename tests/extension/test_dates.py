"""lib/dates.js: civil dates, timestamps, badges and local stamps (Plan 5b-1 Task 2)."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import pytest
from playwright.sync_api import Page, Playwright

from tests.support.extension import extension_copy, js, launch


@pytest.mark.parametrize(
    ("value", "ok"),
    [
        ("2026-10-19", True),
        ("2028-02-29", True),
        ("2026-02-29", False),
        ("2100-02-29", False),
        ("2026-13-01", False),
        ("2026-00-10", False),
        ("2026-10-32", False),
        ("2026-1-9", False),
        ("2026-10-19\n", False),
        ("", False),
        (20261019, False),
        (None, False),
    ],
)
def test_civil_dates_are_checked_by_components(lab: Page, value: object, ok: bool) -> None:
    assert js(lab, "lib/dates.js", "isCivilDate", value) is ok


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-19T12:00:00Z", datetime(2026, 10, 19, 12, tzinfo=UTC)),
        ("2026-10-19T12:00:00.5Z", datetime(2026, 10, 19, 12, 0, 0, 500000, tzinfo=UTC)),
        ("2026-10-19T12:00:00+00:00", None),
        ("2026-10-19T24:00:00Z", None),
        ("2026-02-30T00:00:00Z", None),
        ("2026-10-19T12:00:00Z\n", None),
        ("x", None),
        (5, None),
    ],
)
def test_timestamps(lab: Page, value: object, expected: datetime | None) -> None:
    got = js(lab, "lib/dates.js", "parseTimestamp", value)
    assert got == (None if expected is None else expected.timestamp() * 1000)


@pytest.mark.parametrize(
    ("date", "end", "precision", "day", "mon"),
    [
        ("2026-10-04", "2026-10-04", "day", "4", "OCT"),
        ("2026-09-18", "2026-09-20", "day", "18–20", "SEP"),
        ("2026-09-30", "2026-10-02", "day", "30–2", "SEP–OCT"),
        ("2026-12-24", "2027-02-06", "day", "24–6", "DEC–FEB"),
        ("2026-12-01", "2026-12-31", "month", "TBC", "DEC"),
        ("2026-11-01", "2027-01-31", "month", "TBC", "NOV–JAN"),
        ("2027-01-01", "2027-12-31", "year", "TBC", "2027"),
    ],
)
def test_badges(lab: Page, date: str, end: str, precision: str, day: str, mon: str) -> None:
    card = {"date": date, "end_date": end, "date_precision": precision}
    assert js(lab, "lib/dates.js", "badge", card) == {"day": day, "mon": mon}


ZONES: Final = ("Pacific/Kiritimati", "Pacific/Pago_Pago", "Europe/London")  # UTC+14, UTC-11
DAYS: Final = {  # instant -> the local date in each of ZONES
    "2026-10-19T10:30:00Z": ("2026-10-20", "2026-10-18", "2026-10-19"),
    "2026-10-24T23:30:00Z": ("2026-10-25", "2026-10-24", "2026-10-25"),  # London 00:30 BST
    "2026-03-29T00:30:00Z": ("2026-03-29", "2026-03-28", "2026-03-29"),  # before BST starts
}
ONE_DAY: Final = {"date": "2026-10-25", "end_date": "2026-10-25", "date_precision": "day"}


def ms(instant: str) -> float:
    return datetime.fromisoformat(instant).timestamp() * 1000


@pytest.mark.parametrize(("col", "zone"), list(enumerate(ZONES)))
def test_local_today_across_time_zones_and_dst(
    playwright: Playwright, tmp_path: Path, col: int, zone: str
) -> None:
    folder = extension_copy(tmp_path / "x", legacy=False)
    e = launch(playwright, tmp_path / "p", folder, timezone_id=zone)
    try:
        page = e.lab()
        for instant, days in DAYS.items():
            assert js(page, "lib/dates.js", "localToday", ms(instant)) == days[col]
        assert js(page, "lib/dates.js", "badge", ONE_DAY) == {"day": "25", "mon": "OCT"}
        if zone == "Europe/London":  # the clock shows 01:30 twice on 25 Oct 2026
            for instant in ("2026-10-25T00:30:00Z", "2026-10-25T01:30:00Z"):
                assert js(page, "lib/dates.js", "stamp", ms(instant)) == "25 Oct 2026, 01:30"
    finally:
        e.close()
