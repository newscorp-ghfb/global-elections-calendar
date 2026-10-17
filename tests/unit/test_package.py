"""Package skeleton (spec §4)."""

import elections_calendar


def test_parser_version_is_recorded() -> None:
    assert elections_calendar.PARSER_VERSION == "2.0.0"
