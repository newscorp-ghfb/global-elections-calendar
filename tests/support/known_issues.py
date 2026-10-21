"""known_issues.yml text for the health tests."""

from datetime import UTC, datetime, timedelta

from elections_calendar.health import KnownIssues, parse_known_issues

NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)

SCOPE_FETCH = "{stage: fetch, year: null, page: null}"


def ts(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def entry(**changes: str | None) -> str:
    """The YAML of one valid IPU ``http_error`` acknowledgement, with ``changes`` applied.

    A value is YAML text; ``None`` removes the field; a new name adds one.
    """
    fields: dict[str, str | None] = {
        "source": "ipu",
        "reason": "http_error",
        "scope": SCOPE_FETCH,
        "explanation": "the site is down for maintenance",
        "owner": "ops",
        "acknowledged_at": ts(NOW - timedelta(hours=1)),
        "expires_at": ts(NOW + timedelta(days=6)),
    }
    fields.update(changes)
    lines = [f"{name}: {value}" for name, value in fields.items() if value is not None]
    return "\n".join(("- " if n == 0 else "  ") + line for n, line in enumerate(lines))


def issues(*texts: str, now: datetime = NOW) -> KnownIssues:
    result = parse_known_issues("\n".join(texts) + "\n", now=now)
    assert result.problems == ()
    return result
