"""Resolved-value selection and the legacy status (spec 10.5, 5.9; P67-P69, P75, R2-01)."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from elections_calendar.dates import parse_date_text
from elections_calendar.merge.identity import MergeError, claim_order, dates_compatible, family
from elections_calendar.model import (
    Claim,
    DateSpan,
    LegacyStatus,
    RejectedReason,
    StatusClaim,
    month_end,
)

STALE_AFTER = timedelta(days=7)
_TIER = {"calendar": 0, "umbrella": 0, "expected_renewal": 1}
_CERTAINTY = {"confirmed": 0, "tentative": 1, "unknown": 2}
_WORDS: tuple[StatusClaim, ...] = ("cancelled", "postponed", "disputed")


def is_stale(claim: Claim, now: datetime) -> bool:
    """A fallback claim with no fetch time, or fetched more than 7 days ago (P69)."""
    if not claim.fallback:
        return False
    return claim.fetched_at is None or now - claim.fetched_at > STALE_AFTER


def rescheduling(direct: Sequence[Claim]) -> tuple[Claim, ...]:
    """The postponements, when every one carries an old date and a usable new date (D2)."""
    posted = [
        c for c in direct if c.evidence_kind != "observation" and c.status_claim == "postponed"
    ]
    if not posted or not all(
        c.previous_date_text is not None and c.span.precision != "year" for c in posted
    ):
        return ()
    return tuple(sorted(posted, key=lambda c: c.merge_id))


@dataclass(frozen=True, slots=True)
class Selection:
    claim: Claim | None
    reasons: Mapping[str, RejectedReason | None]
    date_conflict: bool
    unverified: bool


def _narrow(
    pool: list[Claim],
    keep: list[Claim],
    reason: RejectedReason,
    reasons: dict[str, RejectedReason | None],
) -> list[Claim]:
    kept = {c.merge_id for c in keep}
    for c in pool:
        if c.merge_id not in kept:
            reasons[c.merge_id] = reason
    return keep


def _bounds(span: DateSpan) -> tuple[date, date]:
    if span.start is None or span.end is None:
        raise MergeError("a dated span is needed")
    return span.start, span.end


def _inside(x: DateSpan, y: DateSpan) -> bool:
    (xs, xe), (ys, ye) = _bounds(x), _bounds(y)
    return ys <= xs and xe <= ye


def _is_old_date(c: Claim, rs: Sequence[Claim]) -> bool:
    """R2-01: c disagrees with a rescheduling's new date, or still gives its old date."""
    if any(not dates_compatible(c, r) for r in rs):
        return True
    for r in rs:
        assert r.previous_date_text is not None
        old = parse_date_text(r.previous_date_text, default_year=r.span.year).spans
        for o in old:
            if o.precision != "year" and _inside(c.span, o) and _inside(o, r.span):
                return True
    return False


def _covering(pool: list[Claim]) -> list[Claim]:
    days = [_bounds(c.span) for c in pool if c.span.precision == "day"]
    return [
        c
        for c in pool
        if c.span.precision == "day"
        and c.date_meaning == "voting_period"
        and all(_bounds(c.span)[0] <= s and e <= _bounds(c.span)[1] for s, e in days)
    ]


def select(direct: Sequence[Claim], now: datetime) -> Selection:
    """Pick the claim that dates a contest, and say why each other claim lost (spec 10.5)."""
    reasons: dict[str, RejectedReason | None] = {c.merge_id: None for c in direct}
    eligible: list[Claim] = []
    for c in direct:
        if c.evidence_kind == "observation":
            reasons[c.merge_id] = "observation"
        elif c.span.precision == "year":
            reasons[c.merge_id] = "year_only"
        else:
            eligible.append(c)
    if not eligible:
        return Selection(None, reasons, False, False)

    best = min(_TIER[c.evidence_kind] for c in eligible)
    pool = _narrow(
        eligible, [c for c in eligible if _TIER[c.evidence_kind] == best], "lower_evidence", reasons
    )

    resched = {c.merge_id for c in rescheduling(direct)}
    rs = [c for c in pool if c.merge_id in resched]
    if rs:
        keep = [c for c in pool if c.merge_id in resched or not _is_old_date(c, rs)]
        pool = _narrow(pool, keep, "old_date", reasons)

    covering = _covering(pool)
    if covering:
        pool = _narrow(pool, covering, "not_covering", reasons)
    if any(c.span.precision == "day" for c in pool):
        days = [c for c in pool if c.span.precision == "day"]
        pool = _narrow(pool, days, "less_precise", reasons)
    top = min(_CERTAINTY[c.date_status] for c in pool)
    certain = [c for c in pool if _CERTAINTY[c.date_status] == top]
    pool = _narrow(pool, certain, "less_certain", reasons)
    fresh = [c for c in pool if not is_stale(c, now)]
    if fresh:
        pool = _narrow(pool, fresh, "stale", reasons)
    winner = min(pool, key=claim_order)
    _narrow(pool, [winner], "lower_priority", reasons)

    support = [c for c in eligible if c.evidence_kind == winner.evidence_kind]
    w_start, w_end = _bounds(winner.span)
    date_conflict = any(r == "old_date" for r in reasons.values()) or (
        is_stale(winner, now)
        and any(
            not is_stale(c, now)
            and not (_bounds(c.span)[0] <= w_start and w_end <= _bounds(c.span)[1])
            for c in support
        )
    )
    same = [
        c
        for c in support
        if _bounds(c.span) == (w_start, w_end)
        and c.date_meaning == winner.date_meaning
        and c.span.precision == winner.span.precision
    ]
    unverified = all(is_stale(c, now) for c in same)
    return Selection(winner, reasons, date_conflict, unverified)


@dataclass(frozen=True, slots=True)
class StatusResult:
    status: LegacyStatus
    resolved: StatusClaim | None
    conflict: bool
    rescheduled: bool


def _word_stands(claimers: list[Claim], live: list[Claim], span: DateSpan) -> tuple[bool, bool]:
    """(the word stands, an opposing claim met it) for a cancellation or postponement (D1)."""
    families = {family(c) for c in claimers}
    start, end = _bounds(span)
    opposing = [
        c
        for c in live
        if c.evidence_kind == "calendar"
        and c.span.precision != "year"
        and not c.fallback
        and family(c) not in families
    ]
    for c in opposing:
        s, e = _bounds(c.span)
        if c.status_claim == "held" and s <= end and start <= e:
            return False, True
    return True, any(c.status_claim in (None, "held") for c in opposing)


def legacy_status(direct: Sequence[Claim], span: DateSpan, today: date) -> StatusResult:
    """The legacy status of a contest from its direct claims and selected date (spec 5.9)."""
    live = [c for c in direct if c.evidence_kind != "observation"]
    rescheduled = False
    voiced = [c for c in live if c.status_claim in _WORDS and not c.fallback]
    conflict = any(
        a.status_claim != b.status_claim and family(a) != family(b)
        for i, a in enumerate(voiced)
        for b in voiced[i + 1 :]
    )
    for word in ("cancelled", "postponed"):
        claimers = [c for c in live if c.status_claim == word]
        if not claimers:
            continue
        if word == "postponed" and rescheduling(live):
            rescheduled = True
            continue
        stands, opposed = _word_stands(claimers, live, span)
        conflict = conflict or opposed
        if stands:
            status: LegacyStatus = "Cancelled" if word == "cancelled" else "Postponed"
            return StatusResult(status, word, conflict, False)
    if any(c.status_claim == "disputed" and not c.fallback for c in live):
        return StatusResult("Disputed", "disputed", conflict, rescheduled)
    start, end = _bounds(span)
    if span.precision == "day":
        status = "Held" if end < today else "Upcoming"
    elif end < date(today.year, today.month, 1):
        status = "Held"
    elif start <= month_end(today.year, today.month):
        status = "Unknown"
    else:
        status = "Upcoming"
    return StatusResult(status, None, conflict, rescheduled)
