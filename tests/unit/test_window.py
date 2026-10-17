"""Window and month buckets (spec §5.1)."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from elections_calendar.model import DateSpan
from elections_calendar.window import add_months, window_for

OCT_16 = datetime(2026, 10, 16, 0, 0, tzinfo=UTC)


def test_october_window_is_september_to_january() -> None:
    window = window_for(OCT_16)
    assert window.month_keys == ("2026-09", "2026-10", "2026-11", "2026-12", "2027-01")
    assert window.years == (2026, 2027)
    assert (window.start, window.end) == (date(2026, 9, 1), date(2027, 1, 31))
    assert window.current_month == "2026-10"
    assert window.today == date(2026, 10, 16)


def test_january_window_reaches_back_into_december() -> None:
    window = window_for(datetime(2027, 1, 3, tzinfo=UTC))
    assert window.month_keys[0] == "2026-12"
    assert window.years == (2026, 2027)


def test_naive_now_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        window_for(datetime(2026, 10, 16))


def test_now_is_converted_to_the_utc_civil_date() -> None:
    late_evening_new_york = datetime(2026, 10, 31, 23, 30, tzinfo=timezone(timedelta(hours=-5)))
    window = window_for(late_evening_new_york)  # 2026-11-01 04:30 UTC
    assert window.today == date(2026, 11, 1)
    assert window.month_keys[0] == "2026-10"


def test_add_months_crosses_years() -> None:
    assert add_months(2026, 12, 1) == (2027, 1)
    assert add_months(2027, 1, -1) == (2026, 12)
    assert add_months(2026, 10, 3) == (2027, 1)


@pytest.mark.parametrize(
    ("span", "bucket"),
    [
        (DateSpan.day(date(2026, 10, 25)), "2026-10"),
        (DateSpan.days(date(2026, 9, 18), date(2026, 9, 20)), "2026-09"),
        (DateSpan.month(2026, 12), "2026-12"),
        # starts before the window: first window month it overlaps
        (DateSpan.days(date(2026, 8, 30), date(2026, 9, 2)), "2026-09"),
        (DateSpan.months(2026, 6, 2026, 11), "2026-09"),
        # starts inside, ends after: its start month
        (DateSpan.months(2026, 11, 2027, 3), "2026-11"),
        (DateSpan.day(date(2026, 8, 31)), None),
        (DateSpan.day(date(2027, 2, 1)), None),
        (DateSpan.of_year(2026), None),  # undated items are never bucketed
    ],
)
def test_bucket(span: DateSpan, bucket: str | None) -> None:
    window = window_for(OCT_16)
    assert window.bucket(span) == bucket
    assert window.overlaps(span) is (bucket is not None)
