"""The monitored window and month buckets (spec §5.1).

Window = [M-1, M, M+1, M+2, M+3], where M is the month of the generation's
UTC civil date T.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from elections_calendar.model import DateSpan, month_end

MONTHS_BACK = 1
MONTHS_AHEAD = 3


def add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    """(year, month) shifted by ``delta`` months."""
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


@dataclass(frozen=True, slots=True)
class Window:
    today: date
    months: tuple[tuple[int, int], ...]

    @property
    def start(self) -> date:
        year, month = self.months[0]
        return date(year, month, 1)

    @property
    def end(self) -> date:
        year, month = self.months[-1]
        return month_end(year, month)

    @property
    def years(self) -> tuple[int, ...]:
        """Every calendar year the window touches (the requested years)."""
        return tuple(sorted({year for year, _ in self.months}))

    @property
    def month_keys(self) -> tuple[str, ...]:
        return tuple(month_key(year, month) for year, month in self.months)

    @property
    def current_month(self) -> str:
        return month_key(self.today.year, self.today.month)

    def overlaps(self, span: DateSpan) -> bool:
        """True when a dated span overlaps the window; year precision never does."""
        if span.start is None or span.end is None:
            return False
        return span.start <= self.end and span.end >= self.start

    def bucket(self, span: DateSpan) -> str | None:
        """The one month bucket for a dated span, or None (undated / outside).

        Spec §5.1: the start month if it is in the window, otherwise the first
        window month the interval overlaps. Both are the first window month
        the interval overlaps, which is what this returns.
        """
        if span.start is None or span.end is None:
            return None
        for year, month in self.months:
            if date(year, month, 1) <= span.end and month_end(year, month) >= span.start:
                return month_key(year, month)
        return None


def window_for(now: datetime) -> Window:
    """Window for the generation time ``now`` (timezone-aware; converted to UTC)."""
    if now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    today = now.astimezone(UTC).date()
    months = tuple(
        add_months(today.year, today.month, delta)
        for delta in range(-MONTHS_BACK, MONTHS_AHEAD + 1)
    )
    return Window(today=today, months=months)
