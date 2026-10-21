"""Acknowledgements, accepted drops and recurrence state (§9.6; P91, P94, P95; R16)."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from elections_calendar.health import (
    Acknowledgement,
    HealthState,
    acknowledge,
    drop_acceptances,
    health_state_to_dict,
    in_effect,
    load_health_state,
    next_health_state,
    present_keys,
    reason_key,
    relevance_reasons,
    state_problem_reason,
    unit_key,
)
from elections_calendar.model import DropAcceptance, Reason
from tests.support.known_issues import NOW, SCOPE_FETCH, entry, issues, ts
from tests.support.unit_items import fixture_unit_items, item, renumbered

HOUR = timedelta(hours=1)
CLEAN = HealthState(())
EISA_LIBYA = "Libya | Presidential | Postponed from April 2026"
EISA_REPEAT = "Libya (from the row above) | House of Representatives | Postponed from April 2026"
HTTP = Reason("http_error", "HTTP 500")


def codes(acks: tuple[Acknowledgement, ...]) -> list[str]:
    return [a.code for a in acks]


def test_acknowledgement_scope() -> None:
    known = issues(entry())
    got = acknowledge("ipu", [HTTP], [], known, CLEAN, NOW)
    assert got == (Acknowledgement("http_error", NOW + timedelta(days=6), "fetch", None, None),)
    assert acknowledge("aweb", [HTTP], [], known, CLEAN, NOW) == ()
    assert (
        acknowledge("ipu", [Reason("http_error", "x", page="elections")], [], known, CLEAN, NOW)
        == ()
    )
    assert acknowledge("ipu", [Reason("timeout")], [], known, CLEAN, NOW) == ()
    assert acknowledge("ipu", [Reason("http_error", "x", year=2027)], [], known, CLEAN, NOW) == ()

    paged = issues(entry(scope="{stage: fetch, year: null, page: elections}"))
    assert acknowledge("ipu", [HTTP], [], paged, CLEAN, NOW) == ()
    page_reason = Reason("http_error", "x", page="elections")
    assert codes(acknowledge("ipu", [page_reason], [], paged, CLEAN, NOW)) == ["http_error"]

    deadline = Reason("deadline", "x", page="p3")
    wrong = issues(entry(reason="deadline", scope=SCOPE_FETCH))
    right = issues(entry(reason="deadline", scope="{stage: fetch, year: null, page: p3}"))
    assert acknowledge("ipu", [deadline], [], wrong, CLEAN, NOW) == ()
    (hit,) = acknowledge("ipu", [deadline], [], right, CLEAN, NOW)
    assert (hit.stage, hit.page, hit.year) == ("fetch", "p3", None)


def test_info_reasons_and_the_order_of_reasons() -> None:
    known = issues(entry(), entry(reason="timeout"))
    reasons = [Reason("timeout"), Reason("count_change", "x"), HTTP]
    assert codes(acknowledge("ipu", reasons, [], known, CLEAN, NOW)) == ["timeout", "http_error"]


def test_two_matching_entries_give_the_later_until() -> None:
    later = NOW + timedelta(days=9)
    known = issues(
        entry(), entry(expires_at=ts(later)), entry(expires_at=ts(NOW + timedelta(days=2)))
    )
    (got,) = acknowledge("ipu", [HTTP], [], known, CLEAN, NOW)
    assert got.until == later


def test_a_not_yet_active_entry_acknowledges_nothing() -> None:
    soon = NOW + timedelta(minutes=5)
    known = issues(entry(acknowledged_at=ts(soon), expires_at=ts(soon + timedelta(days=1))))
    assert acknowledge("ipu", [HTTP], [], known, CLEAN, NOW) == ()
    assert codes(acknowledge("ipu", [HTTP], [], known, CLEAN, soon)) == ["http_error"]


def test_recurrence_voids_an_acknowledgement() -> None:
    known = issues(entry())
    (only,) = known.entries
    assert only.key == reason_key(HTTP)
    assert in_effect(only, HealthState(((only.key, NOW - 2 * HOUR),)), NOW)
    assert not in_effect(only, HealthState(((only.key, NOW - HOUR / 2),)), NOW)
    assert in_effect(only, HealthState(((only.key, NOW - HOUR),)), NOW)  # not later
    assert in_effect(only, HealthState((("other|key||", NOW - HOUR / 2),)), NOW)
    voided = HealthState(((only.key, NOW - HOUR / 2),))
    assert acknowledge("ipu", [HTTP], [], known, voided, NOW) == ()

    absent = next_health_state(CLEAN, "ipu", known, frozenset(), NOW)
    assert absent.last_absent_at == ((only.key, NOW),)
    assert absent.problem is None
    previous = HealthState(((only.key, NOW - 2 * HOUR),))
    kept = next_health_state(previous, "ipu", known, frozenset({only.key}), NOW)
    assert kept.last_absent_at == ((only.key, NOW - 2 * HOUR),)
    gone_again = next_health_state(previous, "ipu", known, frozenset(), NOW)
    assert gone_again.last_absent_at == ((only.key, NOW),)
    first_seen = next_health_state(CLEAN, "ipu", known, frozenset({only.key}), NOW)
    assert first_seen.last_absent_at == ()

    stale = HealthState(((only.key, NOW - 2 * HOUR), ("old|fetch||", NOW - HOUR)))
    assert next_health_state(stale, "ipu", known, frozenset({only.key}), NOW).last_absent_at == (
        (only.key, NOW - 2 * HOUR),
    )

    expired = issues(entry(expires_at=ts(NOW + timedelta(days=1))))
    later = NOW + timedelta(days=2)
    gone = next_health_state(previous, "ipu", expired, frozenset(), later)
    assert gone.last_absent_at == ()
    other_source = next_health_state(previous, "aweb", known, frozenset(), NOW)
    assert other_source.last_absent_at == ()


def test_next_state_keeps_keys_of_not_yet_active_entries_and_sorts() -> None:
    soon = NOW + timedelta(minutes=5)
    known = issues(
        entry(reason="timeout"),
        entry(acknowledged_at=ts(soon), expires_at=ts(soon + timedelta(days=1))),
        entry(reason="api_error"),
    )
    state = next_health_state(CLEAN, "ipu", known, frozenset(), NOW)
    assert [k for k, _ in state.last_absent_at] == [
        "api_error|fetch||",
        "http_error|fetch||",
        "timeout|fetch||",
    ]
    assert {at for _, at in state.last_absent_at} == {NOW}


GOOD_STATE_BYTES = json.dumps(
    {
        "last_absent_at": {"b|fetch||": "2026-10-20T10:00:00Z", "a|x||": "2026-10-19T10:00:00Z"},
        "reset_at": None,
    }
).encode()

CORRUPT = [
    (b"{", "not JSON"),
    (b'{"last_absent_at": {"k\xff": "2026-10-20T10:00:00Z"}, "reset_at": null}', "not JSON"),
    (b"[]", "shape"),
    (b'{"last_absent_at": {}}', "shape"),
    (b'{"last_absent_at": [], "reset_at": null}', "shape"),
    (b'{"last_absent_at": {}, "reset_at": null, "x": 1}', "shape"),
    (b'{"last_absent_at": {"k": "2026-10-20T10:00:00"}, "reset_at": null}', "timestamp of k"),
    (b'{"last_absent_at": {"k": 5}, "reset_at": null}', "timestamp of k"),
    (b'{"last_absent_at": {}, "reset_at": "2026-10-20T10:00:00"}', "timestamp of reset_at"),
    (b'{"last_absent_at": {}, "reset_at": 7}', "timestamp of reset_at"),
]


@pytest.mark.parametrize(
    ("raw", "problem"),
    CORRUPT,
    ids=[
        "brace",
        "bad-utf8",
        "list",
        "no-reset-at",
        "absent-list",
        "extra-key",
        "naive-k",
        "number-k",
        "naive-reset",
        "number-reset",
    ],
)
def test_a_corrupt_health_state_voids_every_acknowledgement(
    tmp_path: Path, raw: bytes, problem: str
) -> None:
    path = tmp_path / "health_state.json"
    path.write_bytes(raw)
    state = load_health_state(path)
    assert state == HealthState((), problem)

    known = issues(
        entry(),
        entry(
            source="osce",
            reason="cumulative_drop",
            scope="{stage: snapshot, year: null, page: elections}",
            accept_units_seen_min="1",
            accept_claims_min="1",
        ),
    )
    assert acknowledge("ipu", [HTTP], [], known, state, NOW) == ()
    assert drop_acceptances(known, {"osce": state}, NOW) == ()
    assert drop_acceptances(known, {"osce": CLEAN}, NOW) != ()
    assert state_problem_reason(state) == Reason(
        "ack_invalid", f"health_state.json is corrupt: {problem}"
    )


def test_a_good_state_has_no_problem_reason_and_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "health_state.json"
    assert load_health_state(path) == CLEAN
    assert state_problem_reason(CLEAN) is None
    path.write_bytes(GOOD_STATE_BYTES)
    loaded = load_health_state(path)
    assert loaded.last_absent_at == (
        ("a|x||", datetime(2026, 10, 19, 10, tzinfo=UTC)),
        ("b|fetch||", datetime(2026, 10, 20, 10, tzinfo=UTC)),
    )
    assert loaded.reset_at is None
    with_reset = HealthState(loaded.last_absent_at, None, NOW)
    for state in (loaded, with_reset):
        data = health_state_to_dict(state)
        path.write_text(json.dumps(data), encoding="utf-8")
        assert load_health_state(path) == state
    assert health_state_to_dict(with_reset) == {
        "last_absent_at": {"a|x||": "2026-10-19T10:00:00Z", "b|fetch||": "2026-10-20T10:00:00Z"},
        "reset_at": "2026-10-20T12:00:00Z",
    }
    assert health_state_to_dict(CLEAN) == {"last_absent_at": {}, "reset_at": None}


def test_a_health_state_is_sorted_and_aware() -> None:
    from elections_calendar.model import RecordError

    with pytest.raises(RecordError):
        HealthState((("b", NOW), ("a", NOW)))
    with pytest.raises(RecordError):
        HealthState((("a", NOW), ("a", NOW)))
    with pytest.raises(RecordError):
        HealthState((("a", datetime(2026, 10, 20)),))
    with pytest.raises(RecordError):
        HealthState((), None, datetime(2026, 10, 20))


def test_recovery_after_a_corrupt_state() -> None:
    known = issues(entry(), entry(source="osce"))
    ipu_state = HealthState((), "not JSON")
    ipu_entry, osce_entry = known.entries
    assert not in_effect(ipu_entry, ipu_state, NOW)
    assert in_effect(osce_entry, CLEAN, NOW)

    # the reason is present, so only reset_at (not a recurrence) voids the old entry
    recovered = next_health_state(ipu_state, "ipu", known, frozenset({ipu_entry.key}), NOW)
    assert recovered.problem is None
    assert recovered.reset_at == NOW

    later = NOW + timedelta(days=1)
    fresh = entry(acknowledged_at=ts(NOW + HOUR), expires_at=ts(NOW + HOUR + timedelta(days=3)))
    both = issues(entry(), fresh, now=later)
    old, new = both.entries
    assert not in_effect(old, recovered, later)
    assert in_effect(new, recovered, later)
    assert codes(acknowledge("ipu", [HTTP], [], both, recovered, later)) == ["http_error"]
    only_old = issues(entry(), now=later)
    assert acknowledge("ipu", [HTTP], [], only_old, recovered, later) == ()
    again = next_health_state(recovered, "ipu", both, frozenset({new.key}), later)
    assert again.reset_at == NOW

    untouched = next_health_state(CLEAN, "ipu", known, frozenset(), NOW)
    assert untouched.reset_at is None


def test_an_acknowledgement_never_covers_a_later_gap() -> None:
    known = issues(
        entry(
            source="aweb",
            reason="coverage_gap",
            scope="{stage: parse, year: 2027, page: calendar}",
        )
    )
    ack_time = NOW - HOUR

    def gap(since: datetime | None) -> Reason:
        return Reason("coverage_gap", "calendar: 3 claims", page="calendar", year=2027, since=since)

    (got,) = acknowledge("aweb", [gap(NOW - 2 * HOUR)], [], known, CLEAN, NOW)
    assert got.since == NOW - 2 * HOUR
    assert (got.stage, got.year, got.page) == ("parse", 2027, "calendar")
    assert acknowledge("aweb", [gap(NOW - HOUR / 2)], [], known, CLEAN, NOW) == ()
    assert codes(acknowledge("aweb", [gap(None)], [], known, CLEAN, NOW)) == ["coverage_gap"]
    assert codes(acknowledge("aweb", [gap(ack_time)], [], known, CLEAN, NOW)) == ["coverage_gap"]


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


def test_drop_acceptances() -> None:
    known = issues(_drop())
    states = {"osce": CLEAN}
    expires = NOW + timedelta(days=6)
    assert drop_acceptances(known, states, NOW) == (
        DropAcceptance("osce", "cumulative_drop", "elections", None, 30, 20, expires),
    )
    assert drop_acceptances(known, states, expires) == ()
    soon = NOW + timedelta(minutes=5)
    waiting = issues(_drop(acknowledged_at=ts(soon), expires_at=ts(soon + timedelta(days=1))))
    assert drop_acceptances(waiting, states, NOW) == ()
    key = known.entries[0].key
    voided = {"osce": HealthState(((key, NOW - HOUR / 2),))}
    assert drop_acceptances(known, voided, NOW) == ()
    plain = issues(
        entry(
            source="osce",
            reason="cumulative_drop",
            scope="{stage: snapshot, year: null, page: elections}",
        )
    )
    assert drop_acceptances(plain, states, NOW) == ()
    assert drop_acceptances(known, {"ipu": CLEAN}, NOW) == ()
    assert drop_acceptances(known, {}, NOW) == ()


def test_drop_acceptances_follow_file_order_and_carry_the_year() -> None:
    known = issues(
        _drop(
            reason="sudden_drop",
            scope="{stage: snapshot, year: 2027, page: calendar}",
            source="aweb",
            accept_units_seen_min="0",
            accept_claims_min="0",
        ),
        _drop(),
    )
    got = drop_acceptances(known, {"osce": CLEAN, "aweb": CLEAN}, NOW)
    assert [(a.source, a.reason, a.page, a.year, a.units_seen_min, a.claims_min) for a in got] == [
        ("aweb", "sudden_drop", "calendar", 2027, 0, 0),
        ("osce", "cumulative_drop", "elections", None, 30, 20),
    ]


def test_an_accept_drop_without_a_page_gives_no_acceptance() -> None:
    known = issues(_drop(scope="{stage: snapshot, year: null, page: null}"))
    assert len(known.entries) == 1
    assert drop_acceptances(known, {"osce": CLEAN}, NOW) == ()


def test_an_accept_drop_also_acknowledges_the_drop_warning() -> None:
    known = issues(_drop())
    drop = Reason("cumulative_drop", "x", page="elections")
    assert codes(acknowledge("osce", [drop], [], known, CLEAN, NOW)) == ["cumulative_drop"]


def test_relevance_reasons() -> None:
    items = [
        item("unparsed_unit", "wikipedia", "a"),
        item("unparsed_unit", "wikipedia", "b"),
        item("partial_unit", "wikipedia", "c"),
        item("provisional_change", "wikipedia", None),
        item("disappeared_unit", "wikipedia", None),
    ]
    assert relevance_reasons(items) == (
        Reason("unparsed_relevant", "relevant units unparsed: 2"),
        Reason("partial_relevant", "relevant units partly parsed: 1"),
    )
    assert relevance_reasons(items[2:]) == (
        Reason("partial_relevant", "relevant units partly parsed: 1"),
    )
    assert relevance_reasons(items[:1]) == (
        Reason("unparsed_relevant", "relevant units unparsed: 1"),
    )
    assert relevance_reasons(items[3:]) == ()
    assert relevance_reasons([]) == ()


def _unit_entry(
    text: str, reason: str = "unparsed_relevant", source: str = "eisa", **changes: str | None
) -> str:
    return entry(reason=reason, scope=None, unit_text=f'"{text}"', source=source, **changes)


UNPARSED = Reason("unparsed_relevant", "relevant units unparsed: 2")


def test_a_no_new_date_unit_can_be_acknowledged_until_it_changes() -> None:
    items = fixture_unit_items("eisa")
    assert sorted(i.unit_text or "" for i in items) == [EISA_REPEAT, EISA_LIBYA]
    known = issues(_unit_entry(EISA_LIBYA), _unit_entry(EISA_REPEAT))
    (got,) = acknowledge("eisa", [UNPARSED], items, known, CLEAN, NOW)
    assert (got.code, got.stage, got.until) == (
        "unparsed_relevant",
        "parse",
        NOW + timedelta(days=6),
    )
    assert codes(acknowledge("eisa", [UNPARSED], renumbered(items), known, CLEAN, NOW)) == [
        "unparsed_relevant"
    ]
    changed = issues(_unit_entry(EISA_LIBYA.replace("April", "May")), _unit_entry(EISA_REPEAT))
    assert acknowledge("eisa", [UNPARSED], items, changed, CLEAN, NOW) == ()


def test_an_inherited_country_change_reopens_an_acknowledgement() -> None:
    items = fixture_unit_items("eisa")
    chad = EISA_REPEAT.replace("Libya", "Chad")
    assert (
        acknowledge(
            "eisa",
            [UNPARSED],
            items,
            issues(_unit_entry(EISA_LIBYA), _unit_entry(chad)),
            CLEAN,
            NOW,
        )
        == ()
    )
    assert acknowledge("eisa", [UNPARSED], items, issues(_unit_entry(EISA_LIBYA)), CLEAN, NOW) == ()
    extra = issues(
        _unit_entry(EISA_LIBYA), _unit_entry(EISA_REPEAT), _unit_entry("no item has this text")
    )
    assert codes(acknowledge("eisa", [UNPARSED], items, extra, CLEAN, NOW)) == ["unparsed_relevant"]


def test_unit_acknowledgements_take_the_earliest_item_expiry() -> None:
    items = fixture_unit_items("eisa")
    early = NOW + timedelta(days=2)
    late = NOW + timedelta(days=9)
    known = issues(
        _unit_entry(EISA_LIBYA, expires_at=ts(early)),
        _unit_entry(EISA_LIBYA, expires_at=ts(NOW + timedelta(days=1))),
        _unit_entry(EISA_REPEAT, expires_at=ts(late)),
    )
    (got,) = acknowledge("eisa", [UNPARSED], items, known, CLEAN, NOW)
    assert got.until == early


def test_unit_acknowledgements_match_source_reason_and_state() -> None:
    items = [item("unparsed_unit", "eisa", "t1"), item("partial_unit", "eisa", "t2")]
    partial = Reason("partial_relevant", "relevant units partly parsed: 1")
    reasons = [UNPARSED, partial]
    known = issues(_unit_entry("t1"), _unit_entry("t2", reason="partial_relevant"))
    assert codes(acknowledge("eisa", reasons, items, known, CLEAN, NOW)) == [
        "unparsed_relevant",
        "partial_relevant",
    ]
    # an entry of another reason covers nothing
    swapped = issues(_unit_entry("t1", reason="partial_relevant"), _unit_entry("t2"))
    assert acknowledge("eisa", reasons, items, swapped, CLEAN, NOW) == ()
    # an entry of another source covers nothing
    other = issues(
        _unit_entry("t1", source="ipu"), _unit_entry("t2", reason="partial_relevant", source="ipu")
    )
    assert acknowledge("eisa", reasons, items, other, CLEAN, NOW) == ()
    # a void entry covers nothing
    key = known.entries[0].key
    voided = HealthState(((key, NOW - HOUR / 2),))
    assert codes(acknowledge("eisa", reasons, items, known, voided, NOW)) == ["partial_relevant"]
    # a plain acknowledgement by scope cannot mute a unit reason
    scoped = issues(entry(source="eisa", reason="http_error"))
    assert acknowledge("eisa", reasons, items, scoped, CLEAN, NOW) == ()


def test_a_unit_reason_with_no_items_is_not_acknowledged() -> None:
    known = issues(_unit_entry("t1"))
    assert acknowledge("eisa", [UNPARSED], [], known, CLEAN, NOW) == ()
    others = [item("unparsed_unit", "ipu", "t1"), item("partial_unit", "eisa", "t1")]
    assert acknowledge("eisa", [UNPARSED], others, known, CLEAN, NOW) == ()


def test_unit_acknowledgement_uses_the_full_text() -> None:
    head = "Libya: " + "x" * 400
    first, second = f"{head} District A", f"{head} District B"
    one, two = item("unparsed_unit", "eisa", first), item("unparsed_unit", "eisa", second)
    assert one.text == two.text
    items = [one, two]
    assert acknowledge("eisa", [UNPARSED], items, issues(_unit_entry(first)), CLEAN, NOW) == ()
    both = issues(_unit_entry(first), _unit_entry(second))
    assert codes(acknowledge("eisa", [UNPARSED], items, both, CLEAN, NOW)) == ["unparsed_relevant"]
    cut = issues(_unit_entry(one.text))
    assert acknowledge("eisa", [UNPARSED], items, cut, CLEAN, NOW) == ()
    spaced = first.replace(" ", "  ")
    assert acknowledge("eisa", [UNPARSED], [one], issues(_unit_entry(spaced)), CLEAN, NOW) != ()
    assert present_keys([], [one]) != present_keys([], [two])


def test_present_keys() -> None:
    items = [
        item("unparsed_unit", "eisa", "t1"),
        item("partial_unit", "eisa", "t2"),
        item("provisional_change", "eisa", None),
        item("disappeared_unit", "eisa", None),
    ]
    reasons = [HTTP, Reason("coverage_gap", "x", page="calendar", year=2027)]
    assert present_keys(reasons, items) == frozenset(
        {
            "http_error|fetch||",
            "coverage_gap|parse|2027|calendar",
            unit_key("unparsed_relevant", "t1"),
            unit_key("partial_relevant", "t2"),
        }
    )
    assert unit_key("unparsed_relevant", "t1") != unit_key("partial_relevant", "t1")
    assert unit_key("unparsed_relevant", "t1") != unit_key("unparsed_relevant", "t2")
    assert present_keys([], []) == frozenset()


def test_the_key_of_a_unit_entry_is_the_key_of_its_item() -> None:
    (unit_entry,) = issues(_unit_entry("t1")).entries
    assert unit_entry.key == unit_key("unparsed_relevant", "t1")
    state = next_health_state(CLEAN, "eisa", issues(_unit_entry("t1")), frozenset(), NOW)
    assert state.last_absent_at == ((unit_entry.key, NOW),)
