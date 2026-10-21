"""known_issues.yml: validity, loading and the never-acknowledgeable codes (§9.6, P95)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from elections_calendar.health import (
    HealthState,
    KnownIssues,
    in_effect,
    load_known_issues,
    not_yet_active,
    parse_known_issues,
)
from elections_calendar.model import NEVER_ACKNOWLEDGEABLE, REASON_STAGE
from tests.support.known_issues import NOW, SCOPE_FETCH, entry, ts

ACK = NOW - timedelta(hours=1)
FUTURE = NOW + timedelta(minutes=5)
DAY = timedelta(days=1)
NOT_VALID = "known_issues.yml is not valid YAML"
TS_ACK = "acknowledged_at must be a timestamp with a time zone"
TS_EXP = "expires_at must be a timestamp with a time zone"

# (id, change, problem or None, in effect at NOW)
VALIDITY: list[tuple[str, dict[str, str | None], str | None, bool]] = [
    ("Z", {}, None, True),
    ("offset", {"acknowledged_at": "2026-10-20T13:00:00+02:00"}, None, True),
    ("quoted", {"acknowledged_at": '"2026-10-20T11:00:00Z"'}, None, True),
    ("naive", {"acknowledged_at": "2026-10-20T11:00:00"}, TS_ACK, False),
    ("date only", {"expires_at": "2026-10-25"}, TS_EXP, False),
    ("naive string", {"expires_at": '"2026-10-25T00:00:00"'}, TS_EXP, False),
    ("not a time", {"expires_at": "soon"}, TS_EXP, False),
    ("zero length", {"expires_at": ts(ACK)}, "expires_at must be after acknowledged_at", False),
    (
        "reversed",
        {"expires_at": ts(ACK - timedelta(hours=1))},
        "expires_at must be after acknowledged_at",
        False,
    ),
    ("14 days", {"expires_at": ts(ACK + timedelta(days=14))}, None, True),
    (
        "14 days + 1 s",
        {"expires_at": ts(ACK + timedelta(days=14, seconds=1))},
        "an acknowledgement lasts at most 14 days",
        False,
    ),
    ("now + 5 min", {"acknowledged_at": ts(FUTURE), "expires_at": ts(FUTURE + DAY)}, None, False),
    (
        "now + 1 day",
        {"acknowledged_at": ts(NOW + DAY), "expires_at": ts(NOW + 2 * DAY)},
        None,
        False,
    ),
    (
        "now + 1 day + 1 s",
        {
            "acknowledged_at": ts(NOW + DAY + timedelta(seconds=1)),
            "expires_at": ts(NOW + 2 * DAY),
        },
        "acknowledged_at is more than 1 day in the future",
        False,
    ),
    ("at expiry", {"expires_at": ts(NOW)}, None, False),
    ("1 s before expiry", {"expires_at": ts(NOW + timedelta(seconds=1))}, None, True),
    ("impossible date", {"expires_at": "2026-13-45T00:00:00Z"}, NOT_VALID, False),
]


@pytest.mark.parametrize(
    ("change", "problem", "effective"), [r[1:] for r in VALIDITY], ids=[r[0] for r in VALIDITY]
)
def test_acknowledgement_validity(
    change: dict[str, str | None], problem: str | None, effective: bool
) -> None:
    result = parse_known_issues(entry(**change) + "\n", now=NOW)
    if problem is not None:
        assert result.entries == ()
        detail = problem if problem == NOT_VALID else f"known_issues.yml entry 1: {problem}"
        assert [(r.code, r.detail) for r in result.problems] == [("ack_invalid", detail)]
        return
    assert result.problems == ()
    (only,) = result.entries
    assert only.acknowledged_at.utcoffset() == timedelta(0)
    assert only.expires_at.utcoffset() == timedelta(0)
    assert in_effect(only, HealthState(()), NOW) is effective
    assert not_yet_active(result, NOW) == (() if only.acknowledged_at <= NOW else (only,))


def test_offsets_are_stored_in_utc() -> None:
    (only,) = parse_known_issues(
        entry(acknowledged_at="2026-10-20T13:00:00+02:00") + "\n", now=NOW
    ).entries
    assert only.acknowledged_at == datetime(2026, 10, 20, 11, tzinfo=UTC)
    assert only.acknowledged_at.tzinfo is UTC


def test_the_entry_is_read_field_by_field() -> None:
    (only,) = parse_known_issues(entry(explanation='"  a   b "') + "\n", now=NOW).entries
    assert (only.index, only.kind, only.source, only.reason) == (
        1,
        "acknowledgement",
        "ipu",
        "http_error",
    )
    assert only.scope is not None
    assert (only.scope.stage, only.scope.year, only.scope.page) == ("fetch", None, None)
    assert (only.unit_text, only.units_seen_min, only.claims_min) == (None, None, None)
    assert (only.explanation, only.owner) == ("a b", "ops")
    assert only.key == "http_error|fetch||"


def test_a_naive_now_raises() -> None:
    with pytest.raises(ValueError, match="timezone"):
        parse_known_issues("[]", now=datetime(2026, 10, 20, 12))


def _unit(**changes: str | None) -> str:
    base: dict[str, str | None] = {
        "reason": "unparsed_relevant",
        "scope": None,
        "unit_text": "Libya | Presidential",
    }
    base.update(changes)
    return entry(**base)


def _drop(**changes: str | None) -> str:
    base: dict[str, str | None] = {
        "source": "osce",
        "reason": "cumulative_drop",
        "scope": "{stage: snapshot, year: null, page: elections}",
        "accept_units_seen_min": "30",
        "accept_claims_min": "20",
    }
    base.update(changes)
    return entry(**base)


def test_the_three_kinds_and_their_keys() -> None:
    result = parse_known_issues(
        "\n".join([entry(), _unit(unit_text='"  Libya |  Presidential "'), _drop()]) + "\n",
        now=NOW,
    )
    assert result.problems == ()
    plain, unit, drop = result.entries
    assert [e.index for e in result.entries] == [1, 2, 3]
    assert (plain.kind, unit.kind, drop.kind) == (
        "acknowledgement",
        "unit_acknowledgement",
        "accept_drop",
    )
    assert unit.scope is None
    assert unit.unit_text == "Libya | Presidential"
    assert unit.key.startswith("unit|unparsed_relevant|")
    assert len(unit.key) == len("unit|unparsed_relevant|") + 16
    assert (drop.units_seen_min, drop.claims_min) == (30, 20)
    assert drop.key == "cumulative_drop|snapshot||elections"


MALFORMED_WHOLE_FILE = [
    ("a tab", "- source: ipu\n\treason: http_error\n", NOT_VALID),
    ("repeated owner", entry() + "\n  owner: someone else\n", NOT_VALID),
    ("unclosed", "- [\n", NOT_VALID),
    ("a mapping", "{a: 1}\n", "known_issues.yml is not a list"),
    ("a scalar", "hello\n", "known_issues.yml is not a list"),
]


@pytest.mark.parametrize(
    ("text", "detail"),
    [r[1:] for r in MALFORMED_WHOLE_FILE],
    ids=[r[0] for r in MALFORMED_WHOLE_FILE],
)
def test_malformed_known_issues(text: str, detail: str) -> None:
    result = parse_known_issues(text, now=NOW)
    assert result.entries == ()
    assert [(r.code, r.detail) for r in result.problems] == [("ack_invalid", detail)]


def test_strings_in_a_list_are_not_mappings() -> None:
    result = parse_known_issues("- one\n- two\n", now=NOW)
    assert result.entries == ()
    assert [r.detail for r in result.problems] == [
        "known_issues.yml entry 1: not a mapping",
        "known_issues.yml entry 2: not a mapping",
    ]


@pytest.mark.parametrize("text", ["", "   \n", "# only a comment\n", "[]\n"])
def test_an_empty_file_has_no_entries_and_no_problems(text: str) -> None:
    assert parse_known_issues(text, now=NOW) == KnownIssues((), ())


PARSE = "{stage: parse, year: null, page: null}"
ONLY_FOR_DROPS = (
    "accept_units_seen_min and accept_claims_min are only for sudden_drop and cumulative_drop"
)
SCOPE_SHAPE = "scope must have stage, year and page"
MIN_INT = "must be a whole number of at least 0"

ENTRY_CHECKS: list[tuple[str, str, str]] = [
    ("missing owner", entry(owner=None), "missing field owner"),
    ("missing before unknown", entry(owner=None, note="x"), "missing field owner"),
    ("missing in table order", entry(scope=None, owner=None), "missing field scope"),
    ("unknown note", entry(note="x"), "unknown field note"),
    ("first unknown, sorted", entry(zeta="1", alpha="2"), "unknown field alpha"),
    ("scope without page", entry(scope="{stage: fetch, year: null}"), SCOPE_SHAPE),
    (
        "scope with extra",
        entry(scope="{stage: fetch, year: null, page: null, x: 1}"),
        SCOPE_SHAPE,
    ),
    ("scope not a mapping", entry(scope="fetch"), SCOPE_SHAPE),
    ("year true", entry(scope="{stage: fetch, year: true, page: null}"), SCOPE_SHAPE),
    ("year text", entry(scope='{stage: fetch, year: "2027", page: null}'), SCOPE_SHAPE),
    ("page a number", entry(scope="{stage: fetch, year: null, page: 5}"), SCOPE_SHAPE),
    ("source cnn", entry(source="cnn"), "unknown source cnn"),
    ("reason oops", entry(reason="oops"), "unknown reason oops"),
    (
        "unit_text with http_error",
        entry(scope=None, unit_text="x"),
        "unit_text is only for unparsed_relevant and partial_relevant",
    ),
    (
        "scoped unparsed_relevant",
        entry(reason="unparsed_relevant", scope=PARSE),
        "unparsed_relevant is acknowledged per unit (unit_text)",
    ),
    (
        "scoped partial_relevant",
        entry(reason="partial_relevant", scope=PARSE),
        "partial_relevant is acknowledged per unit (unit_text)",
    ),
    (
        "accept_units_seen_min with http_error",
        entry(accept_units_seen_min="1", accept_claims_min="1"),
        ONLY_FOR_DROPS,
    ),
    (
        "accept_drop without claims min",
        _drop(accept_claims_min=None),
        "missing field accept_claims_min",
    ),
    (
        "accept_drop without units min",
        _drop(accept_units_seen_min=None),
        "missing field accept_units_seen_min",
    ),
    ("units min -1", _drop(accept_units_seen_min="-1"), f"accept_units_seen_min {MIN_INT}"),
    ("units min true", _drop(accept_units_seen_min="true"), f"accept_units_seen_min {MIN_INT}"),
    ("units min a float", _drop(accept_units_seen_min="1.5"), f"accept_units_seen_min {MIN_INT}"),
    ("claims min true", _drop(accept_claims_min="true"), f"accept_claims_min {MIN_INT}"),
    ("claims min -1", _drop(accept_claims_min="-1"), f"accept_claims_min {MIN_INT}"),
    (
        "units min is checked first",
        _drop(accept_units_seen_min="-1", accept_claims_min="-1"),
        f"accept_units_seen_min {MIN_INT}",
    ),
    (
        "zero minimums are fine, a wrong stage is not",
        _drop(
            accept_units_seen_min="0",
            accept_claims_min="0",
            scope="{stage: parse, year: null, page: elections}",
        ),
        "scope.stage must be snapshot for cumulative_drop",
    ),
    ("stage parse for http_error", entry(scope=PARSE), "scope.stage must be fetch for http_error"),
    ("explanation blank", entry(explanation='"  "'), "explanation must not be empty"),
    ("explanation a number", entry(explanation="5"), "explanation must not be empty"),
    ("owner blank", entry(owner='""'), "owner must not be empty"),
    ("unit_text blank", _unit(unit_text='" "'), "unit_text must not be empty"),
    (
        "unit_text with accept_drop fields",
        _unit(accept_claims_min="1"),
        "unknown field accept_claims_min",
    ),
    (
        "accept_drop with a unit reason",
        _drop(reason="unparsed_relevant"),
        "unparsed_relevant is acknowledged per unit (unit_text)",
    ),
    ("accept_drop with http_error", _drop(reason="http_error", scope=SCOPE_FETCH), ONLY_FOR_DROPS),
]


NULL_PAGE = "{stage: snapshot, year: null, page: null}"
TYPO = "{stage: fecth, year: null, page: null}"
LATER = NOW + 3 * DAY
HUGE = "0x" + "f" * 4000
YEAR_RANGE = "scope.year must be from 1900 to 2199"
ENTRY_CHECKS += [
    ("year 1899", entry(scope="{stage: fetch, year: 1899, page: null}"), YEAR_RANGE),
    ("year 2200", entry(scope="{stage: fetch, year: 2200, page: null}"), YEAR_RANGE),
    ("year huge", entry(scope="{stage: fetch, year: " + HUGE + ", page: null}"), YEAR_RANGE),
    (
        "order: year before source",
        entry(source="cnn", scope="{stage: fetch, year: 2200, page: null}"),
        YEAR_RANGE,
    ),
    (
        "units min over the cap",
        _drop(accept_units_seen_min="1000001"),
        "accept_units_seen_min must be at most 1000000",
    ),
    (
        "claims min over the cap",
        _drop(accept_claims_min="1000001"),
        "accept_claims_min must be at most 1000000",
    ),
    (
        "units min huge",
        _drop(accept_units_seen_min=HUGE),
        "accept_units_seen_min must be at most 1000000",
    ),
    ("claims min huge", _drop(accept_claims_min=HUGE), "accept_claims_min must be at most 1000000"),
    ("stage typo", entry(scope=TYPO), "scope.stage must be fetch for http_error"),
    (
        "bad stage and bad source: source wins",
        entry(source="cnn", scope=TYPO),
        "unknown source cnn",
    ),
    (
        "stage a list",
        entry(scope="{stage: [fetch], year: null, page: null}"),
        SCOPE_SHAPE,
    ),
    ("reason a list", entry(reason="[http_error]"), "unknown reason list"),
    ("reason a mapping", entry(reason="{a: 1}"), "unknown reason dict"),
    ("reason a huge int", entry(reason="0x" + "f" * 4000), "unknown reason int"),
    ("reason a small int", entry(reason="42"), "unknown reason 42"),
    ("source a list", entry(source="[ipu]"), "unknown source list"),
    ("source a mapping", entry(source="{a: 1}"), "unknown source dict"),
    ("an unknown field that is not a string", entry(**{"5": "1"}), "unknown field 5"),
    ("accept_drop without a page", _drop(scope=NULL_PAGE), "an accept_drop needs scope.page"),
    (
        "sudden_drop without a page",
        _drop(reason="sudden_drop", scope=NULL_PAGE),
        "an accept_drop needs scope.page",
    ),
    (
        "accept_drop: the stage is checked before the page",
        _drop(scope="{stage: parse, year: null, page: null}"),
        "scope.stage must be snapshot for cumulative_drop",
    ),
    (
        "accept_drop: the page is checked before the text",
        _drop(scope=NULL_PAGE, explanation='" "'),
        "an accept_drop needs scope.page",
    ),
    ("order: shape before source", entry(source="cnn", scope="{stage: fetch}"), SCOPE_SHAPE),
    ("order: source before reason", entry(source="cnn", reason="oops"), "unknown source cnn"),
    (
        "order: never before unit",
        entry(reason="ledger_mismatch", scope=None, unit_text="x"),
        "ledger_mismatch can never be acknowledged",
    ),
    (
        "order: ints before stage",
        _drop(accept_units_seen_min="-1", scope="{stage: parse, year: null, page: elections}"),
        f"accept_units_seen_min {MIN_INT}",
    ),
    (
        "order: text before timestamp",
        entry(explanation='" "', expires_at="soon"),
        "explanation must not be empty",
    ),
    (
        "order: acknowledged_at before expires_at",
        entry(acknowledged_at="2026-10-20T11:00:00", expires_at="soon"),
        TS_ACK,
    ),
    (
        "order: length before ahead",
        entry(acknowledged_at=ts(LATER), expires_at=ts(LATER + 20 * DAY)),
        "an acknowledgement lasts at most 14 days",
    ),
    (
        "order: after before ahead",
        entry(acknowledged_at=ts(LATER), expires_at=ts(LATER - DAY)),
        "expires_at must be after acknowledged_at",
    ),
    ("expires_at overflows UTC", entry(expires_at="9999-12-31T23:59:59-05:00"), TS_EXP),
    ("acknowledged_at overflows UTC", entry(acknowledged_at="0001-01-01T00:00:00+05:00"), TS_ACK),
]


@pytest.mark.parametrize(
    ("text", "problem"), [r[1:] for r in ENTRY_CHECKS], ids=[r[0] for r in ENTRY_CHECKS]
)
def test_each_entry_check(text: str, problem: str) -> None:
    result = parse_known_issues(text + "\n", now=NOW)
    assert result.entries == ()
    assert [(r.code, r.detail) for r in result.problems] == [
        ("ack_invalid", f"known_issues.yml entry 1: {problem}")
    ]


def test_one_bad_entry_does_not_cost_the_good_one() -> None:
    result = parse_known_issues(entry(owner=None) + "\n" + entry() + "\n", now=NOW)
    assert [r.detail for r in result.problems] == ["known_issues.yml entry 1: missing field owner"]
    assert [e.index for e in result.entries] == [2]


def test_a_problem_is_cut_to_the_detail_limit() -> None:
    result = parse_known_issues(entry(source="x" * 1000) + "\n", now=NOW)
    (problem,) = result.problems
    assert len(problem.detail) == 300


@pytest.mark.parametrize("code", sorted(NEVER_ACKNOWLEDGEABLE))
def test_never_acknowledgeable(code: str) -> None:
    scope = f"{{stage: {REASON_STAGE[code]}, year: null, page: null}}"  # type: ignore[index]
    result = parse_known_issues(entry(reason=code, scope=scope) + "\n", now=NOW)
    assert result.entries == ()
    assert [r.detail for r in result.problems] == [
        f"known_issues.yml entry 1: {code} can never be acknowledged"
    ]


def test_load_known_issues(tmp_path: Path) -> None:
    assert load_known_issues(tmp_path / "missing.yml", now=NOW) == KnownIssues((), ())
    good = tmp_path / "good.yml"
    good.write_bytes(b"\xef\xbb\xbf" + entry().encode() + b"\n")
    assert len(load_known_issues(good, now=NOW).entries) == 1
    bad = tmp_path / "bad.yml"
    bad.write_bytes(b"- source: \xff\xfe\n")
    result = load_known_issues(bad, now=NOW)
    assert result.entries == ()
    assert [r.detail for r in result.problems] == [NOT_VALID]


def test_repository_file_is_empty_and_valid() -> None:
    path = Path(__file__).resolve().parents[2] / "known_issues.yml"
    assert load_known_issues(path, now=NOW) == KnownIssues((), ())


@pytest.mark.parametrize("year", [1900, 2199])
def test_the_year_bounds_are_valid(year: int) -> None:
    result = parse_known_issues(
        entry(scope=f"{{stage: fetch, year: {year}, page: null}}") + "\n", now=NOW
    )
    assert result.problems == ()
    (only,) = result.entries
    assert only.scope is not None and only.scope.year == year
    assert in_effect(only, HealthState(()), NOW)


def test_the_floor_cap_is_valid() -> None:
    result = parse_known_issues(
        _drop(accept_units_seen_min="1000000", accept_claims_min="1000000") + "\n", now=NOW
    )
    assert result.problems == ()
    (only,) = result.entries
    assert (only.units_seen_min, only.claims_min) == (1_000_000, 1_000_000)
