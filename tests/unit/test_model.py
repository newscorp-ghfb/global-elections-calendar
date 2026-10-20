"""Shared vocabulary (spec §5.2, §7, §9.1)."""

import dataclasses
import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, timezone
from typing import get_args

import pytest

from elections_calendar.model import (
    MAX_ATTENTION_TEXT,
    MAX_TYPE,
    NEVER_ACKNOWLEDGEABLE,
    REASON_LEVEL,
    REASON_STAGE,
    SOURCE_NAMES,
    SOURCE_ORDER,
    AttentionItem,
    BibEntry,
    Card,
    Child,
    ChildSource,
    Claim,
    DateSpan,
    Disposition,
    DropAcceptance,
    InputUnit,
    MergeResult,
    Reason,
    ReasonCode,
    RecordError,
    SnapshotHealth,
    UndatedListing,
    _conforms,
    canonical_json,
    month_end,
    short_id,
    stored_json,
)
from elections_calendar.text import collapse_ws, fold, norm_name, slug
from tests.support.pages import claim as page_claim


def test_month_end_handles_leap_years() -> None:
    assert month_end(2028, 2) == date(2028, 2, 29)
    assert month_end(2027, 2) == date(2027, 2, 28)


def test_month_span_runs_to_the_last_day_of_the_end_month() -> None:
    span = DateSpan.months(2026, 11, 2027, 1)
    assert (span.start, span.end, span.precision, span.year) == (
        date(2026, 11, 1),
        date(2027, 1, 31),
        "month",
        2026,
    )


@pytest.mark.parametrize(
    "build",
    [
        lambda: DateSpan(date(2026, 10, 2), date(2026, 10, 1), "day", 2026),
        lambda: DateSpan(date(2026, 10, 2), date(2026, 10, 31), "month", 2026),
        lambda: DateSpan(None, None, "day", 2026),
        lambda: DateSpan(date(2026, 1, 1), None, "year", 2026),
        lambda: DateSpan(date(2026, 10, 1), date(2026, 10, 1), "day", 2027),
    ],
)
def test_invalid_spans_are_rejected(build: object) -> None:
    with pytest.raises(ValueError):
        build()  # type: ignore[operator]


def test_span_round_trips_through_dict() -> None:
    for span in (DateSpan.day(date(2026, 10, 25)), DateSpan.month(2026, 10), DateSpan.of_year(2026)):
        assert DateSpan.from_dict(span.to_dict()) == span


def unit(**changes: object) -> InputUnit:
    values: dict[str, object] = {
        "unit_id": "electionguide:upcoming/r17",
        "source": "electionguide",
        "text": "Serbia | Serbian National Assembly | 2026-10-25 (d)",
        "outcome": "parsed",
        "reason": None,
        "relevance": "in_or_after_window",
    }
    values.update(changes)
    return InputUnit(**values)  # type: ignore[arg-type]


def test_unit_round_trips() -> None:
    u = unit()
    assert InputUnit.from_dict(u.to_dict()) == u


@pytest.mark.parametrize(
    "changes",
    [
        {"unit_id": "electionguide:5259"},  # an event id is not an observation locator
        {"unit_id": "ndi:p1:upcoming/r3"},  # wrong source prefix
        {"outcome": "ignored", "reason": "before_window"},  # not an allowlisted reason
        {"outcome": "parsed", "reason": "too_few_cells"},
        {"outcome": "unparsed", "reason": None},
        {"outcome": "partial", "reason": ""},
    ],
)
def test_unit_invariants(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        unit(**changes)


def claim(**changes: object) -> Claim:
    values: dict[str, object] = {
        "unit_id": "electionguide:upcoming/r17",
        "claim_id": "electionguide:upcoming/r17#0",
        "source": "electionguide",
        "link": "https://www.electionguide.org/elections/id/5259/",
        "source_event_id": "electionguide:5259",
        "place_raw": "Serbia",
        "place_id": "iso:RS",
        "jurisdiction": None,
        "jurisdiction_kind": "nationwide",
        "level": "national",
        "institution": "iso:RS/national-assembly",
        "office_class": "legislature",
        "office_label": "Serbian National Assembly",
        "aggregate": False,
        "kind": "candidate_election",
        "round": None,
        "span": DateSpan.day(date(2026, 10, 25)),
        "date_meaning": "voting_period",
        "date_status": "confirmed",
        "date_text": "2026-10-25 (d)",
        "status_claim": None,
        "previous_date_text": None,
        "evidence_kind": "calendar",
        "indirect": False,
    }
    values.update(changes)
    return Claim(**values)  # type: ignore[arg-type]


def test_claim_round_trips_with_utc_provenance() -> None:
    fetched = datetime(2026, 10, 16, 2, 0, tzinfo=UTC)
    c = claim(fetched_at=fetched, snapshot_id="abc")
    data = c.to_dict()
    assert data["fetched_at"] == "2026-10-16T02:00:00Z"
    assert data["date"] == "2026-10-25" and data["end_date"] == "2026-10-25"
    assert Claim.from_dict(data) == c


def test_claim_serialises_non_utc_provenance_as_utc() -> None:
    fetched = datetime(2026, 10, 16, 4, 0, tzinfo=timezone(timedelta(hours=2)))
    assert claim(fetched_at=fetched).to_dict()["fetched_at"] == "2026-10-16T02:00:00Z"


def test_claim_rejects_naive_fetched_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        claim(fetched_at=datetime(2026, 10, 16, 2, 0))


def test_claim_id_must_extend_unit_id() -> None:
    with pytest.raises(ValueError):
        claim(claim_id="electionguide:upcoming/r18#0")


@pytest.mark.parametrize(
    "changes",
    [
        {"source": "osce"},  # the unit belongs to another source
        {"claim_id": "electionguide:upcoming/r17#banana"},
        {"claim_id": "electionguide:upcoming/r17#"},
        {"claim_id": "electionguide:upcoming/r17#01"},
        {"claim_id": "electionguide:upcoming/r17#\uff11"},  # a fullwidth digit one
    ],
)
def test_claim_provenance_must_be_consistent(changes: dict[str, object]) -> None:
    with pytest.raises(RecordError):
        Claim.from_dict(saved_claim(**changes))


def test_merge_id_distinguishes_served_and_provisional() -> None:
    served = claim()
    provisional = dataclasses.replace(served, provisional=True)
    assert served.merge_id == "served/electionguide:upcoming/r17#0"
    assert provisional.merge_id == "provisional/electionguide:upcoming/r17#0"


def saved_claim(**changes: object) -> dict[str, object]:
    return {**claim().to_dict(), **changes}


@pytest.mark.parametrize(
    "load",
    [
        lambda: DateSpan.from_dict({**DateSpan.month(2026, 10).to_dict(), "date_precision": "hour"}),
        lambda: DateSpan.from_dict({**DateSpan.of_year(2026).to_dict(), "year": "2026"}),  # not coerced
        lambda: InputUnit.from_dict({**unit().to_dict(), "outcome": "banana"}),
        lambda: InputUnit.from_dict({**unit().to_dict(), "relevance": "maybe"}),
        lambda: InputUnit.from_dict({**unit().to_dict(), "colour": "red"}),  # unknown field
        lambda: Claim.from_dict(saved_claim(fallback="yes")),
        lambda: Claim.from_dict(saved_claim(aggregate=1)),
        lambda: Claim.from_dict(saved_claim(jurisdiction_kind="planet")),
        lambda: Claim.from_dict(saved_claim(round=True)),
        lambda: Claim.from_dict(saved_claim(date=20261025)),
        lambda: Claim.from_dict(saved_claim(fetched_at="yesterday")),
        lambda: Claim.from_dict({k: v for k, v in claim().to_dict().items() if k != "kind"}),
    ],
)
def test_saved_records_outside_the_vocabulary_are_rejected(load: Callable[[], object]) -> None:
    with pytest.raises(RecordError):
        load()


@pytest.mark.parametrize("data", [None, "ab", [1, 2], []])
@pytest.mark.parametrize("load", [DateSpan.from_dict, InputUnit.from_dict, Claim.from_dict])
def test_a_saved_record_that_is_not_an_object_is_a_record_error(
    load: Callable[[object], object], data: object
) -> None:
    with pytest.raises(RecordError):
        load(data)


@pytest.mark.parametrize(
    "build",
    [
        lambda: DateSpan.of_year(1899),
        lambda: DateSpan.of_year(2200),
        lambda: DateSpan.day(date(1, 1, 1)),
        lambda: DateSpan.days(date(2026, 12, 30), date(2200, 1, 1)),
        lambda: claim(round=0),
    ],
)
def test_years_and_rounds_are_bounded(build: Callable[[], object]) -> None:
    with pytest.raises(RecordError):
        build()
    assert DateSpan.of_year(1989).year == 1989  # Carter Center missions go back to 1989
    assert claim(round=2).round == 2


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("Gambia (The)", "gambia"),  # IPU
        ("Gambia, The", "gambia"),  # ElectionGuide
        ("The Philippines", "philippines"),  # A-WEB
        ("Côte d’Ivoire", "cote d'ivoire"),  # Carter Center, curly apostrophe
        ("São Tomé e Príncipe", "sao tome e principe"),
        ("Bolivia (Plurinational State of)", "bolivia plurinational state of"),
        ("Bolivia, Plurinational State of", "bolivia plurinational state of"),
        ("Virgin Islands, U.S.", "virgin islands u s"),
        ("Trinidad & Tobago", "trinidad and tobago"),
        ("Hawai\u02bbi", "hawai'i"),  # okina
        ("\u6771\u4eac", "\u6771\u4eac"),  # Tokyo: other scripts keep their letters
        ("\u0423\u043a\u0440\u0430\u0457\u043d\u0430", "\u0443\u043a\u0440\u0430\u0456\u043d\u0430"),
        ("\u304c\u304d", "\u304c\u304d"),  # kana keep their voicing marks
        ("\u0928\u0947\u092a\u093e\u0932", "\u0928\u0947\u092a\u093e\u0932"),  # Nepal: vowel signs
        ("snake_case", "snake case"),
    ],
)
def test_norm_name(raw: str, key: str) -> None:
    assert norm_name(raw) == key


def test_slug_and_fold() -> None:
    assert slug("Muscogee (Creek) Nation") == "muscogee-creek-nation"
    assert slug("Democratic People's Republic of Korea") == "democratic-peoples-republic-of-korea"
    assert fold("Türkiye") == "turkiye"
    assert collapse_ws(" 18\u00a0\u2013  20\nSeptember ") == "18 – 20 September"


def test_reasons_are_checked_records() -> None:
    assert Reason("coverage_gap", "past list starts 2026-09-02").to_dict() == {
        "code": "coverage_gap",
        "detail": "past list starts 2026-09-02",
        "page": None,
        "year": None,
        "since": None,
    }
    assert Reason.from_dict({"code": "worker_failed", "detail": "exit code 3"}) == Reason(
        "worker_failed", "exit code 3"
    )
    assert Reason("deadline", "x" * 300).detail == "x" * 300
    for bad in (
        {"code": "banana", "detail": ""},
        {"code": "deadline", "detail": "x" * 301},
        {"code": "deadline", "detail": 5},
        {"code": "deadline", "extra": 1},
        "deadline",
    ):
        with pytest.raises(RecordError):
            Reason.from_dict(bad)  # type: ignore[arg-type]


def test_a_duplicate_names_the_unit_it_duplicates() -> None:
    dup = InputUnit(
        "electionguide:anticipated/r1",
        "electionguide",
        "x",
        "ignored",
        "duplicate",
        "unknown",
        duplicate_of="electionguide:upcoming/r4",
    )
    assert InputUnit.from_dict(dup.to_dict()) == dup
    for reason, target in (
        ("duplicate", None),
        ("container_item", "electionguide:upcoming/r4"),
        ("duplicate", "wikipedia:national-2026@rev1/January/li[1]"),
        ("duplicate", "electionguide:anticipated/r1"),
    ):
        with pytest.raises(RecordError):
            InputUnit(
                "electionguide:anticipated/r1",
                "electionguide",
                "x",
                "ignored",
                reason,
                "unknown",
                duplicate_of=target,
            )


def test_a_saved_unit_without_duplicate_of_still_loads() -> None:
    saved = InputUnit("s:p/1", "s", "t", "parsed", None, "unknown").to_dict()
    del saved["duplicate_of"]
    assert InputUnit.from_dict(saved).duplicate_of is None


# --- the merge's output records ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "hint", "expected"),
    [
        pytest.param((), tuple[str, ...], True, id="empty"),
        pytest.param(("a", "b"), tuple[str, ...], True, id="strings"),
        pytest.param(["a"], tuple[str, ...], False, id="list"),
        pytest.param(("a", 1), tuple[str, ...], False, id="mixed"),
        pytest.param((True,), tuple[int, ...], False, id="bool-is-not-int"),
    ],
)
def test_tuple_hints(value: object, hint: object, expected: bool) -> None:
    assert _conforms(value, hint) is expected


def test_a_fixed_length_tuple_hint_has_no_runtime_check() -> None:
    with pytest.raises(TypeError, match="no runtime check for"):
        _conforms((1, "a"), tuple[int, str])


def _source(selected: bool = True, reason: str | None = None, n: int = 0) -> ChildSource:
    return ChildSource(
        claim=page_claim("s:v/r1", n),
        selected=selected,
        rejected_reason=reason,  # type: ignore[arg-type]
    )


def _child(**changes: object) -> Child:
    values: dict[str, object] = {
        "child_id": "0123456789ab",
        "place_id": "iso:SE",
        "country": "Sweden",
        "country_code": "SE",
        "jurisdiction": None,
        "jurisdiction_kind": "nationwide",
        "level": "national",
        "institution": None,
        "office_class": "legislature",
        "office_label": "Riksdag",
        "kind": "candidate_election",
        "round": None,
        "indirect": False,
        "aggregate": False,
        "span": DateSpan.day(date(2026, 9, 13)),
        "date_meaning": "voting_period",
        "date_status": "confirmed",
        "status": "Upcoming",
        "occurrence_confirmed": False,
        "status_conflict": False,
        "date_conflict": False,
        "unverified": False,
        "ambiguous": False,
        "rescheduled_from": ("1 November 2026",),
        "provisional_date": None,
        "possible_matches": ("aaaaaaaaaaaa", "bbbbbbbbbbbb"),
        "sources": (_source(),),
    }
    return Child(**{**values, **changes})  # type: ignore[arg-type]


def _bib() -> BibEntry:
    return BibEntry(source="s", link="https://example.test/e")


def _card(**changes: object) -> Card:
    values: dict[str, object] = {
        "group_id": "0123456789ab",
        "place_id": "iso:SE",
        "country": "Sweden",
        "country_code": "SE",
        "level": "national",
        "span": DateSpan.day(date(2026, 9, 13)),
        "date_meaning": "voting_period",
        "date_status": "confirmed",
        "status": "Upcoming",
        "type": "Parliamentary",
        "children": (_child(),),
        "sources": (_bib(),),
        "umbrella_sources": (),
        "umbrellas": (page_claim("s:v/u", 1),),
    }
    return Card(**{**values, **changes})  # type: ignore[arg-type]


def _listing(**changes: object) -> UndatedListing:
    values: dict[str, object] = {
        "undated_id": "0123456789ab",
        "place_id": "iso:SE",
        "country": "Sweden",
        "office_label": "Riksdag",
        "year": 2026,
        "claims": (dataclasses.replace(page_claim("s:v/r1"), span=DateSpan.of_year(2026)),),
        "sources": (_bib(),),
        "possible_matches": ("aaaaaaaaaaaa",),
    }
    return UndatedListing(**{**values, **changes})  # type: ignore[arg-type]


def _item(**changes: object) -> AttentionItem:
    values: dict[str, object] = {
        "item_id": "0123456789ab",
        "kind": "unparsed_unit",
        "source": "s",
        "link": "https://example.test/e",
        "snapshot_id": None,
        "relevance": "unknown",
        "text": "text",
        "reason": "reason",
        "possible_matches": (),
        "merge_ids": ("served/s:v/r1#0",),
        "undated_id": None,
    }
    return AttentionItem(**{**values, **changes})  # type: ignore[arg-type]


def _disposition(**changes: object) -> Disposition:
    values: dict[str, object] = {
        "merge_id": "served/s:v/r1#0",
        "kind": "attached",
        "targets": ("0123456789ab",),
    }
    return Disposition(**{**values, **changes})  # type: ignore[arg-type]


def test_merge_records_accept_valid_values() -> None:
    provisional = _child(
        provisional_date="moved",
        sources=(_source(), _source(False, "provisional", 1)),
    )
    result = MergeResult(
        cards=(_card(), _card(children=(provisional,))),
        undated=(_listing(),),
        attention=(_item(),),
        dispositions=(_disposition(),),
    )
    assert result.cards[1].children[0].provisional_date == "moved"
    assert _child().rescheduled_from == ("1 November 2026",)
    assert _item(kind="undated_listing", undated_id="0123456789ab").undated_id


_TWO_SELECTED = (_source(), _source(True, None, 1))
_BAD_ID = "0123456789AB"
_SORTED_UNIQUE = "{}.{} must be sorted and unique"
_MERGE_IDS = "AttentionItem.merge_ids must be sorted, unique and non-empty"
_TARGETS = "Disposition.targets must be sorted, unique and non-empty"
_LISTING = "UndatedListing: every claim is year-only, of its year"
_UNDATED_ID = "AttentionItem: undated_id goes with kind undated_listing"


@pytest.mark.parametrize(
    ("build", "message"),
    [
        pytest.param(
            lambda: _source(True, "stale"),
            "selected and rejected_reason disagree",
            id="source-selected-with-reason",
        ),
        pytest.param(
            lambda: _source(False, None),
            "selected and rejected_reason disagree",
            id="source-rejected-without-reason",
        ),
        pytest.param(
            lambda: _child(child_id=_BAD_ID),
            "Child.child_id '0123456789AB' is not 12 hex characters",
            id="child-id",
        ),
        pytest.param(
            lambda: _card(group_id="short"),
            "Card.group_id 'short' is not 12 hex characters",
            id="card-id",
        ),
        pytest.param(
            lambda: _listing(undated_id=_BAD_ID),
            "UndatedListing.undated_id '0123456789AB' is not 12 hex characters",
            id="listing-id",
        ),
        pytest.param(
            lambda: _item(item_id=_BAD_ID),
            "AttentionItem.item_id '0123456789AB' is not 12 hex characters",
            id="item-id",
        ),
        pytest.param(
            lambda: _child(span=DateSpan.of_year(2026)),
            "Child: span is never year precision",
            id="child-year-span",
        ),
        pytest.param(
            lambda: _card(span=DateSpan.of_year(2026)),
            "Card: span is never year precision",
            id="card-year-span",
        ),
        pytest.param(
            lambda: _child(sources=_TWO_SELECTED),
            "Child: exactly one source is selected",
            id="child-two-selected",
        ),
        pytest.param(
            lambda: _child(sources=(_source(False, "stale"),)),
            "Child: exactly one source is selected",
            id="child-none-selected",
        ),
        pytest.param(
            lambda: _child(possible_matches=("bbbbbbbbbbbb", "aaaaaaaaaaaa")),
            _SORTED_UNIQUE.format("Child", "possible_matches"),
            id="child-matches-unsorted",
        ),
        pytest.param(
            lambda: _listing(possible_matches=("aaaaaaaaaaaa", "aaaaaaaaaaaa")),
            _SORTED_UNIQUE.format("UndatedListing", "possible_matches"),
            id="listing-matches-repeat",
        ),
        pytest.param(
            lambda: _item(possible_matches=("b", "a")),
            _SORTED_UNIQUE.format("AttentionItem", "possible_matches"),
            id="item-matches-unsorted",
        ),
        pytest.param(
            lambda: _child(possible_matches=("0123456789ab",)),
            "Child.possible_matches names the child itself",
            id="child-matches-itself",
        ),
        pytest.param(
            lambda: _child(rescheduled_from=("2 November 2026", "1 November 2026")),
            _SORTED_UNIQUE.format("Child", "rescheduled_from"),
            id="child-rescheduled-unsorted",
        ),
        pytest.param(
            lambda: _child(provisional_date="moved"),
            "Child: provisional_date needs a provisional source",
            id="child-provisional-date-without-source",
        ),
        pytest.param(lambda: _card(children=()), "Card: no children", id="card-no-children"),
        pytest.param(
            lambda: _card(type=""), "Card.type is 1 to 200 characters", id="card-type-empty"
        ),
        pytest.param(
            lambda: _card(type="x" * (MAX_TYPE + 1)),
            "Card.type is 1 to 200 characters",
            id="card-type-201",
        ),
        pytest.param(lambda: _listing(claims=()), _LISTING, id="listing-no-claims"),
        pytest.param(
            lambda: _listing(claims=(page_claim("s:v/r1"),)), _LISTING, id="listing-day-claim"
        ),
        pytest.param(lambda: _listing(year=2027), _LISTING, id="listing-other-year"),
        pytest.param(
            lambda: _item(text="x" * (MAX_ATTENTION_TEXT + 1)),
            "AttentionItem.text is over 300 characters",
            id="item-text-301",
        ),
        pytest.param(
            lambda: _item(undated_id="0123456789ab"), _UNDATED_ID, id="item-undated-id-other-kind"
        ),
        pytest.param(
            lambda: _item(kind="undated_listing"), _UNDATED_ID, id="item-listing-without-id"
        ),
        pytest.param(lambda: _item(merge_ids=()), _MERGE_IDS, id="item-merge-ids-empty"),
        pytest.param(lambda: _item(merge_ids=("b", "a")), _MERGE_IDS, id="item-merge-ids-unsorted"),
        pytest.param(lambda: _disposition(targets=()), _TARGETS, id="disposition-no-targets"),
        pytest.param(
            lambda: _disposition(kind="umbrella_link", targets=("b", "a")),
            _TARGETS,
            id="disposition-targets-unsorted",
        ),
        pytest.param(
            lambda: _disposition(targets=("a", "b")),
            "Disposition: attached has exactly one target",
            id="disposition-two-targets",
        ),
    ],
)
def test_merge_record_rules(build: Callable[[], object], message: str) -> None:
    with pytest.raises(RecordError) as caught:
        build()
    assert str(caught.value) == message


def test_a_card_type_of_the_limit_builds() -> None:
    assert len(_card(type="x" * MAX_TYPE).type) == 200


def test_an_umbrella_link_has_many_targets() -> None:
    assert _disposition(kind="umbrella_link", targets=("a", "b")).targets == ("a", "b")


LEVELS = {
    "error": (
        "fetch_failed tls_error timeout dns_error http_error challenge_page api_error deadline "
        "worker_failed layout_not_recognised required_year_missing pagination_incomplete "
        "ledger_mismatch discovery_mismatch unavailable merge_failed validation_failed"
    ),
    "warning": (
        "unparsed_relevant partial_relevant coverage_gap sudden_drop cumulative_drop "
        "fallback_stale no_cross_source_match served_mismatch attention_truncated ack_invalid"
    ),
    "info": "not_published_yet count_change provisional_changes units_disappeared",
}
STAGES = {
    "fetch": (
        "fetch_failed tls_error timeout dns_error http_error challenge_page api_error deadline "
        "worker_failed"
    ),
    "parse": (
        "layout_not_recognised required_year_missing pagination_incomplete ledger_mismatch "
        "discovery_mismatch unparsed_relevant partial_relevant coverage_gap not_published_yet"
    ),
    "snapshot": (
        "unavailable sudden_drop cumulative_drop fallback_stale count_change "
        "provisional_changes units_disappeared"
    ),
    "match": "no_cross_source_match",
    "run": "merge_failed validation_failed served_mismatch attention_truncated ack_invalid",
}


def test_reason_tables_cover_every_code() -> None:
    codes = set(get_args(ReasonCode))
    assert set(REASON_LEVEL) == codes
    assert set(REASON_STAGE) == codes
    assert {c: lv for lv, names in LEVELS.items() for c in names.split()} == REASON_LEVEL
    assert {c: st for st, names in STAGES.items() for c in names.split()} == REASON_STAGE
    assert set(
        ["ledger_mismatch", "discovery_mismatch", "fallback_stale", "served_mismatch", "attention_truncated", "ack_invalid", "merge_failed", "validation_failed"]
    ) | set(LEVELS["info"].split()) == NEVER_ACKNOWLEDGEABLE
    assert all(c in NEVER_ACKNOWLEDGEABLE for c in codes if REASON_LEVEL[c] == "info")
    assert "http_error" not in NEVER_ACKNOWLEDGEABLE


def test_reason_page_and_year() -> None:
    plain = Reason("http_error", "upcoming", page="upcoming", year=None)
    assert Reason.from_dict(plain.to_dict()) == plain
    assert set(plain.to_dict()) == {"code", "detail", "page", "year", "since"}
    old = Reason.from_dict({"code": "worker_failed", "detail": "exit code 3"})
    assert (old.page, old.year, old.since) == (None, None, None)
    since = datetime(2026, 10, 19, 12, 30, tzinfo=timezone(timedelta(hours=2)))
    gap = Reason("coverage_gap", "x", page="calendar", year=2027, since=since)
    assert gap.to_dict()["since"] == "2026-10-19T10:30:00Z"
    assert Reason.from_dict(gap.to_dict()) == gap
    with pytest.raises(RecordError, match="Reason.since must be timezone-aware"):
        Reason("coverage_gap", "x", since=datetime(2026, 10, 19))
    with pytest.raises(RecordError, match="Reason.since must be timezone-aware"):
        Reason.from_dict({**gap.to_dict(), "since": "2026-10-19T10:30:00"})


def test_canonical_and_stored_json() -> None:
    assert canonical_json({"b": 1, "a": "é"}) == '{"a":"é","b":1}'.encode()
    stored = stored_json([1])
    assert stored.endswith(b"\n")
    assert json.loads(stored) == [1]


def test_source_names() -> None:
    assert tuple(SOURCE_NAMES) == SOURCE_ORDER
    assert list(SOURCE_NAMES.values()) == [
        "ElectionGuide",
        "OSCE/ODIHR",
        "Wikipedia",
        "NDI",
        "A-WEB",
        "EISA",
        "IPU",
        "Carter Center",
        "EEAS",
    ]


def test_identity_re_exports() -> None:
    from elections_calendar.merge import identity

    assert identity.short_id is short_id
    assert identity.SOURCE_ORDER is SOURCE_ORDER


def test_drop_acceptance_and_snapshot_health() -> None:
    until = datetime(2026, 10, 22, 12, tzinfo=UTC)
    naive = datetime(2026, 10, 22, 12)
    accept = DropAcceptance("osce", "sudden_drop", "elections", None, 40, 40, until)
    assert (accept.units_seen_min, accept.claims_min, accept.until) == (40, 40, until)
    with pytest.raises(RecordError, match=r"^DropAcceptance.until must be timezone-aware$"):
        DropAcceptance("osce", "sudden_drop", "elections", None, 40, 40, naive)
    with pytest.raises(RecordError, match=r"^DropAcceptance.reason: "):
        DropAcceptance("osce", "count_change", "elections", None, 40, 40, until)  # type: ignore[arg-type]
    health = SnapshotHealth("fallback", True, "a" * 64, until, 100, True)
    assert health.served_fetched_at == until
    assert SnapshotHealth("unavailable", False, None, None, None, False).served_fetched_at is None
    with pytest.raises(
        RecordError, match=r"^SnapshotHealth.served_fetched_at must be timezone-aware$"
    ):
        SnapshotHealth("fallback", True, "a" * 64, naive, 100, True)
    with pytest.raises(RecordError, match=r"^SnapshotHealth.acceptance: "):
        SnapshotHealth("served", True, None, None, None, True)  # type: ignore[arg-type]
