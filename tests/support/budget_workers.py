"""The child process of the request-budget test (spawned, so it must be importable)."""

from pathlib import Path

from elections_calendar.fetch import RequestBudget


def take_many(directory: str, limit: int, count: int, result: str) -> None:
    """Take ``count`` tokens; write how many were granted to ``result``."""
    budget = RequestBudget(Path(directory), limit)
    granted = sum(1 for _ in range(count) if budget.take())
    Path(result).write_text(str(granted), encoding="utf-8")
