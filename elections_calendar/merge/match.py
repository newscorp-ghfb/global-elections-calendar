"""Matching: claims into contests, umbrella links, undated groups and pending items.

Spec 10.1-10.4 with the plan's P66-P82. ``match`` runs the steps in order: 0 input, 1 the
clustering (used by 2, 4, 11 and 13), 2 Phase A, 3 Phase B, 4 Phase C, 5 umbrellas and C7,
6 sessions, 7 observations, 8 resolve, 9 Phase D, 10 links, 11 aggregates, 12 possible
matches, 13 undated groups. Claims are paired only within one place.

Step 0 sorts the claims by merge id and every walk follows that order. A contest's members,
attached and provisional claims are kept in step 0's order as they are added. The undated
pool, the umbrella list and the pending items are not: they also take claims after their
walk (conflicting proposals, year-only umbrellas, dissolved sessions), so step 0's order is
restored where the pool and the umbrella list are read (steps 10 and 13), and the pending
items are sorted at the output like every result tuple. So the result never depends on the
input order.
"""

from bisect import insort
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from elections_calendar.dates import parse_date_text
from elections_calendar.merge.identity import (
    CHAMBERS,
    REFERENDA,
    MergeError,
    Role,
    dates_compatible,
    family,
    gap_days,
    identity_compatible,
    joinable,
    qualified_numbers,
    role,
    same_source_compatible,
    short_id,
    years_of,
)
from elections_calendar.merge.select import Selection, StatusResult, legacy_status, select
from elections_calendar.model import Claim, DateSpan, Level, ProvisionalDate
from elections_calendar.text import norm_name
from elections_calendar.window import window_for

Origin = Literal["anchor", "standalone", "aggregate"]
PendingKind = Literal["unresolved_evidence", "provisional_change"]
PendingReason = Literal[
    "no_candidate", "several_candidates", "provisional_aggregate", "conflicting_claims"
]  # P82

_NEAR_DAYS = 7  # P73 (b): contests 1 to 7 days apart are linked
_RANK = {"day": 0, "month": 1, "year": 2}  # D5: precision ranks
_SCOPED = ("named", "subdivision")
_COUNCIL_OFFICES = frozenset({"local_council", "mayor"})

Edge = Callable[[Claim, Claim], bool]


@dataclass(eq=False)  # identity semantics: contests go in sets
class Contest:
    """One contest (spec 10.2).

    ``members``, ``attached`` and ``provisional`` keep step 0's order.
    """

    origin: Origin
    members: list[Claim]
    attached: list[Claim] = field(default_factory=list)
    provisional: list[Claim] = field(default_factory=list)
    ambiguous: bool = False
    possible: set[Contest] = field(default_factory=set, repr=False)
    date_conflict: bool = False
    status_conflict: bool = False
    provisional_date: ProvisionalDate | None = None  # Phase D (P74, D3)
    selection: Selection | None = None  # set when the contest is resolved
    status: StatusResult | None = None

    def direct(self) -> list[Claim]:
        """The members and the attached claims, sorted by merge id."""
        return sorted([*self.members, *self.attached], key=lambda c: c.merge_id)

    @property
    def child_id(self) -> str:
        """``short_id`` of the direct anchors' merge ids, else of every direct claim's (5.3)."""
        direct = self.direct()
        anchors = [c.merge_id for c in direct if role(c) == "anchor"]
        return short_id(anchors or [c.merge_id for c in direct])

    @property
    def span(self) -> DateSpan:
        """The selected claim's span."""
        if self.selection is None or self.selection.claim is None:
            raise MergeError(f"contest {self.child_id} is not resolved yet")
        return self.selection.claim.span


@dataclass(frozen=True)
class Pending:
    """A claim that becomes an attention item (Task 5)."""

    kind: PendingKind
    reason: PendingReason
    claim: Claim
    candidates: tuple[Contest, ...]  # sorted by child_id


@dataclass(frozen=True)
class Undated:
    """Year-only claims that become an undated listing (Task 5)."""

    claims: tuple[Claim, ...]  # sorted by merge_id
    possible: tuple[Contest, ...]  # sorted by child_id


@dataclass(frozen=True)
class Link:
    """An umbrella and the contests it fits."""

    claim: Claim
    contests: tuple[Contest, ...]  # sorted by child_id


@dataclass(frozen=True)
class Matching:
    contests: tuple[Contest, ...]  # sorted by child_id
    links: tuple[Link, ...]  # sorted by claim.merge_id
    undated: tuple[Undated, ...]  # sorted by claims[0].merge_id
    pending: tuple[Pending, ...]  # sorted by claim.merge_id


# ---------------------------------------------------------------- the run's state


@dataclass(eq=False)
class _Item:
    """A pending item while matching runs: its candidates can still lose a session (step 6)."""

    kind: PendingKind
    reason: PendingReason
    claim: Claim
    candidates: list[Contest]


@dataclass(eq=False)
class _Run:
    claims: list[Claim]  # step 0's order
    roles: dict[str, Role]
    rank: dict[str, int]  # merge id -> position in step 0's order
    now: datetime
    today: date
    phase_a: list[Contest] = field(default_factory=list)
    contests: list[Contest] = field(default_factory=list)  # steps 2-7, still present
    standalone: list[Claim] = field(default_factory=list)  # the standalone pool
    umbrellas: list[Claim] = field(default_factory=list)  # the umbrella list
    pool: list[tuple[Claim, list[Contest]]] = field(default_factory=list)  # the undated pool
    items: list[_Item] = field(default_factory=list)
    links: list[tuple[Claim, list[Contest]]] = field(default_factory=list)
    loose: list[Claim] = field(default_factory=list)
    aggregates: list[Contest] = field(default_factory=list)

    def of_role(self, name: Role) -> list[Claim]:
        return [c for c in self.claims if self.roles[c.merge_id] == name]

    def in_order(self, claims: Iterable[Claim]) -> list[Claim]:
        """``claims`` in step 0's order, as if taken by walking the sorted claims."""
        return sorted(claims, key=lambda c: self.rank[c.merge_id])

    def add(self, part: list[Claim], claim: Claim) -> None:
        """Add ``claim`` to one of a contest's lists, keeping step 0's order."""
        insort(part, claim, key=lambda c: self.rank[c.merge_id])


def _start(claims: Sequence[Claim], now: datetime) -> _Run:
    """Step 0: the window, the duplicate check, the sort, the source check and the roles."""
    window = window_for(now)
    repeated = sorted(m for m, n in Counter(c.merge_id for c in claims).items() if n > 1)
    if repeated:
        raise MergeError(f"duplicate merge_id: {repeated[0]}")
    ordered = sorted(claims, key=lambda c: c.merge_id)
    for c in ordered:
        family(c)  # an unknown source raises before any phase, whatever the claim's role
    roles = {c.merge_id: role(c) for c in ordered}
    rank = {c.merge_id: i for i, c in enumerate(ordered)}
    return _Run(ordered, roles, rank, now, window.today)


# ---------------------------------------------------------------- step 1: clustering


@dataclass
class _Group:
    claims: list[Claim]
    ambiguous: bool
    neighbours: list[int]  # indices of the edge neighbours' groups


def _cluster(claims: Sequence[Claim], edge: Edge) -> list[_Group]:
    """Step 1: the groups of ``claims`` (given in step 0's order), in step 0's order.

    A connected component whose every pair has an edge is one group; otherwise each of its
    claims is its own group, flagged ambiguous, with its edge neighbours' groups.
    """
    parent = list(range(len(claims)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    places: dict[str, list[int]] = {}
    for i, c in enumerate(claims):
        places.setdefault(c.place_id, []).append(i)
    edges: list[set[int]] = [set() for _ in claims]
    for indices in places.values():
        for x, i in enumerate(indices):
            for j in indices[x + 1 :]:
                if edge(claims[i], claims[j]):
                    edges[i].add(j)
                    edges[j].add(i)
                    parent[root(i)] = root(j)
    components: dict[int, list[int]] = {}
    for i in range(len(claims)):
        components.setdefault(root(i), []).append(i)
    groups: list[_Group] = []
    group_of: dict[int, int] = {}
    for comp in sorted(components.values()):  # by first index: step 0's order
        if all(j in edges[i] for x, i in enumerate(comp) for j in comp[x + 1 :]):
            group_of.update((i, len(groups)) for i in comp)
            groups.append(_Group([claims[i] for i in comp], False, []))
        else:
            for i in comp:
                group_of[i] = len(groups)
                groups.append(_Group([claims[i]], True, []))
    for i in range(len(claims)):
        if groups[group_of[i]].ambiguous:
            groups[group_of[i]].neighbours = sorted(group_of[j] for j in edges[i])
    return groups


def _contests(groups: Sequence[_Group], origin: Origin) -> list[Contest]:
    made = [Contest(origin, list(g.claims), ambiguous=g.ambiguous) for g in groups]
    for k, g in zip(made, groups, strict=True):
        k.possible.update(made[i] for i in g.neighbours)
    return made


def _place(k: Contest) -> str:
    return k.members[0].place_id


def _by_place(contests: Iterable[Contest]) -> dict[str, list[Contest]]:
    out: dict[str, list[Contest]] = {}
    for k in contests:
        out.setdefault(_place(k), []).append(k)
    return out


def _conflicting(proposals: Sequence[Claim], conflict: Edge) -> set[str]:
    """Merge ids of the proposals that conflict with another proposal (P82)."""
    bad: set[str] = set()
    for i, a in enumerate(proposals):
        for b in proposals[i + 1 :]:
            if conflict(a, b):
                bad |= {a.merge_id, b.merge_id}
    return bad


# ---------------------------------------------------------------- steps 2-4: Phases A to C


def _phase_a(run: _Run) -> None:
    run.phase_a = _contests(_cluster(run.of_role("anchor"), joinable), "anchor")


def _fits(w: Claim, k: Contest) -> bool:
    """Phase B: every member is compatible with the weak claim (spec 10.3)."""
    relax = w.jurisdiction_kind == "unknown"
    return all(
        identity_compatible(w, m, relax_jurisdiction=relax)
        and same_source_compatible(w, m)
        and dates_compatible(w, m)
        for m in k.members
    )


def _names_by_month(w: Claim, k: Contest) -> bool:
    """Month disagreement (spec 10.3): strict identity, rule F, the claim's year in every member's.

    A month span's ``year`` is its start year.
    """
    return all(
        identity_compatible(w, m)
        and same_source_compatible(w, m)
        and w.span.year in years_of(m.span)
        for m in k.members
    )


def _proposals_conflict(a: Claim, b: Claim) -> bool:
    relax = "unknown" in (a.jurisdiction_kind, b.jurisdiction_kind)
    return not (
        identity_compatible(a, b, relax_jurisdiction=relax) and same_source_compatible(a, b)
    )


def _phase_b(run: _Run) -> None:
    """Step 3: the weak claims that are not observations (spec 10.3, P68, P82)."""
    here = _by_place(run.phase_a)
    proposals: dict[Contest, list[tuple[Claim, bool]]] = {}
    for w in run.of_role("weak"):
        if w.evidence_kind == "observation":
            continue
        contests = here.get(w.place_id, [])
        candidates = [k for k in contests if _fits(w, k)]
        if not candidates and w.span.precision == "month":
            by_month = [k for k in contests if _names_by_month(w, k)]
            if len(by_month) == 1:
                proposals.setdefault(by_month[0], []).append((w, True))
                continue
            if by_month:
                run.items.append(_Item("unresolved_evidence", "several_candidates", w, by_month))
                continue
        if len(candidates) == 1:
            proposals.setdefault(candidates[0], []).append((w, False))
        elif w.span.precision == "year":
            run.pool.append((w, candidates))
        elif not candidates:
            run.standalone.append(w)
        else:
            run.items.append(_Item("unresolved_evidence", "several_candidates", w, candidates))
    for k in run.phase_a:
        props = proposals.get(k, [])
        bad = _conflicting([w for w, _ in props], _proposals_conflict)
        for w, month_disagreement in props:
            if w.merge_id not in bad:
                run.add(k.attached, w)
                k.date_conflict = k.date_conflict or month_disagreement
            elif w.span.precision == "year":
                run.pool.append((w, [k]))
            else:
                run.items.append(_Item("unresolved_evidence", "conflicting_claims", w, [k]))


def _phase_c(run: _Run) -> None:
    run.contests = run.phase_a + _contests(_cluster(run.standalone, joinable), "standalone")


# ---------------------------------------------------------------- steps 5-7


def _chamber_candidate(u: Claim, k: Contest) -> bool:
    """C7 (P71): a contest that a generic legislature claim can name."""
    return (
        not k.ambiguous
        and all(m.office_class in CHAMBERS and m.kind not in REFERENDA for m in k.members)
        and all(
            identity_compatible(u, m, ignore_kind=True, ignore_institution=True)
            and same_source_compatible(u, m)
            and dates_compatible(u, m)
            for m in k.members
        )
        and all(
            identity_compatible(u, a, ignore_kind=True, ignore_institution=True)
            and same_source_compatible(u, a)
            for a in k.attached
            if a.evidence_kind != "observation"
        )
    )


def _chamber_proposals_conflict(a: Claim, b: Claim) -> bool:
    return not (
        identity_compatible(a, b, ignore_kind=True, ignore_institution=True)
        and same_source_compatible(a, b)
    )


def _umbrellas(run: _Run) -> None:
    """Step 5: year-only umbrellas to the undated pool, C7 proposals, the umbrella list."""
    here = _by_place(run.contests)
    proposals: dict[Contest, list[Claim]] = {}
    for u in run.of_role("umbrella"):
        if u.span.precision == "year":
            run.pool.append((u, []))
            continue
        if u.office_class == "legislature" and u.aggregate:
            candidates = [k for k in here.get(u.place_id, []) if _chamber_candidate(u, k)]
            if len(candidates) == 1:
                proposals.setdefault(candidates[0], []).append(u)
                continue
        run.umbrellas.append(u)
    for k in run.contests:
        props = proposals.get(k, [])
        bad = _conflicting(props, _chamber_proposals_conflict)
        for u in props:
            if u.merge_id in bad:
                run.umbrellas.append(u)
            else:
                run.add(k.attached, u)


def _is_session(k: Contest, contests: Sequence[Contest]) -> bool:
    """P78: a referendum day beside a contest of its questions."""
    return all(m.kind == "referendum_day" for m in k.members) and any(
        all(q.kind == "referendum_question" for q in other.members)
        and all(
            identity_compatible(m, q, ignore_kind=True) and dates_compatible(m, q)
            for m in k.members
            for q in other.members
        )
        for other in contests
    )


def _sessions(run: _Run) -> None:
    """Step 6 (P78): a session contest is dissolved, and removed from every candidate list."""
    gone = {k for k in run.contests if _is_session(k, run.contests)}
    for k in (k for k in run.contests if k in gone):
        for c in k.direct():
            if c.span.precision == "year":
                run.pool.append((c, []))
            else:
                run.umbrellas.append(c)
    run.contests = [k for k in run.contests if k not in gone]
    for item in run.items:
        item.candidates = [k for k in item.candidates if k not in gone]
    run.pool = [(c, [k for k in ks if k not in gone]) for c, ks in run.pool]
    for k in run.contests:
        k.possible -= gone


def _observations(run: _Run) -> None:
    """Step 7 (P67): an observation attaches to the one Phase A contest its date fits."""
    here = _by_place(run.contests)
    for o in run.of_role("weak"):
        if o.evidence_kind != "observation":
            continue
        candidates = [
            k
            for k in here.get(o.place_id, [])
            if k.origin == "anchor" and all(dates_compatible(o, m) for m in k.members)
        ]
        if len(candidates) == 1:
            run.add(candidates[0].attached, o)
        else:
            reason: PendingReason = "several_candidates" if candidates else "no_candidate"
            run.items.append(_Item("unresolved_evidence", reason, o, candidates))


# ---------------------------------------------------------------- steps 8-9


def _resolve(k: Contest, run: _Run) -> None:
    """Step 8: the selection and the legacy status."""
    direct = k.direct()
    k.selection = select(direct, run.now)
    if k.selection.claim is None:
        raise MergeError(f"contest {k.child_id} has no eligible date")
    k.date_conflict = k.date_conflict or k.selection.date_conflict
    k.status = legacy_status(direct, k.selection.claim.span, run.today)
    k.status_conflict = k.status_conflict or k.status.conflict


def _covers(s: DateSpan, t: DateSpan) -> bool:
    """P74: span ``s`` contains span ``t``."""
    if s.precision == "year":
        return years_of(t) == {s.year}
    if s.start is None or s.end is None or t.start is None or t.end is None:
        return False  # t has year precision
    return s.start <= t.start and t.end <= s.end


def _date_change(p: Claim, served: Claim | None, span: DateSpan) -> ProvisionalDate | None:
    """P74, D3, D5: how a provisional claim changes its contest's date.

    With a twin, the change is judged against the twin's served copy; without one, against
    the contest's span.
    """
    if served is not None:
        finer = _RANK[p.span.precision] < _RANK[served.span.precision]
        coarser = _RANK[p.span.precision] > _RANK[served.span.precision]
        if p.span == served.span or (_covers(served.span, p.span) and finer):
            return None
        if _covers(p.span, served.span) and coarser:
            return "less_precise"
        return "moved"
    if p.span.precision == "year" or _covers(p.span, span) or _covers(span, p.span):
        return None
    return "moved"


def _phase_d(run: _Run) -> None:
    """Step 9: the provisional claims, against the resolved contests of steps 2-7."""
    here = _by_place(run.contests)
    for p in run.of_role("provisional"):
        contests = here.get(p.place_id, [])
        if p.office_class == "general" or p.aggregate:
            fits = [k for k in contests if umbrella_fits(p, k)]
            run.items.append(_Item("provisional_change", "provisional_aggregate", p, fits))
            continue
        twin = "served/" + p.claim_id
        candidates = [
            k
            for k in contests
            if any(c.merge_id == twin for c in k.direct())
            and all(identity_compatible(p, m) for m in k.members)
        ]
        served = next((c for k in candidates for c in k.direct() if c.merge_id == twin), None)
        if not candidates:
            candidates = [
                k
                for k in contests
                if all(
                    identity_compatible(p, m)
                    and same_source_compatible(p, m)
                    and bool(years_of(p.span) & years_of(m.span))
                    for m in k.members
                )
            ]
        if len(candidates) != 1:
            reason: PendingReason = "several_candidates" if candidates else "no_candidate"
            run.items.append(_Item("provisional_change", reason, p, candidates))
            continue
        k = candidates[0]
        run.add(k.provisional, p)
        change = _date_change(p, served, k.span)
        if change == "moved":
            k.date_conflict = True
            k.provisional_date = "moved"
        elif change == "less_precise" and k.provisional_date is None:
            k.provisional_date = "less_precise"
        assert k.status is not None  # resolved in step 8
        word = k.status.resolved
        if word is None and k.status.rescheduled:
            word = "postponed"
        if p.status_claim != word and not (p.status_claim == "held" and word is None):
            k.status_conflict = True


# ---------------------------------------------------------------- step 10: umbrella links


def _overlap(s: DateSpan, t: DateSpan) -> bool:
    if s.start is None or s.end is None or t.start is None or t.end is None:
        raise MergeError("a dated span is needed")
    return s.start <= t.end and t.start <= s.end


def _level(direct: Sequence[Claim]) -> Level:
    levels = {c.level for c in direct if c.evidence_kind != "observation" and c.level != "unknown"}
    if len(levels) == 1:
        (level,) = levels
        return level
    return "unknown"


def _round(direct: Sequence[Claim]) -> int | None:
    rounds = {c.round for c in direct if c.evidence_kind != "observation" and c.round is not None}
    if len(rounds) == 1:
        (stated,) = rounds
        return stated
    return None


def contest_level(contest: Contest) -> Level:
    """The one known level among the non-observation direct claims, else ``unknown``."""
    return _level(contest.direct())


def contest_round(contest: Contest) -> int | None:
    """The one stated round among the non-observation direct claims, else None."""
    return _round(contest.direct())


def _unrecognised(c: Claim) -> bool:
    """An office the parsers do not model: class ``general`` of unknown level (P81, R2-02)."""
    return c.office_class == "general" and c.level == "unknown"


def _office_in_scope(u: Claim, m: Claim) -> bool:
    if u.office_class == "legislature":
        return m.office_class in CHAMBERS
    if u.office_class == "local_council":
        return m.office_class in _COUNCIL_OFFICES
    return u.office_class == "general" or m.office_class == u.office_class


def umbrella_covers(
    umbrella: Claim, members: Sequence[Claim], direct: Sequence[Claim], span: DateSpan
) -> bool:
    """Whether an umbrella covers a contest of these claims and span (spec 10.4; P78, P81, R2-03).

    ``members`` give the place, referendum, jurisdiction and office rules; ``direct`` gives
    the qualified numbers, the level and the round. Task 6's audit calls it on a child.
    """
    u = umbrella
    if any(m.place_id != u.place_id for m in members):
        return False
    if u.kind == "referendum_day":
        if not all(m.kind == "referendum_question" for m in members):
            return False
    elif any(m.kind in REFERENDA for m in members):
        return False
    if u.jurisdiction_kind in _SCOPED and not all(
        m.jurisdiction_kind in _SCOPED
        and norm_name(m.jurisdiction or "") == norm_name(u.jurisdiction or "")
        for m in members
    ):
        return False
    if not all(_office_in_scope(u, m) for m in members):
        return False
    if _unrecognised(u):
        return False
    numbers = qualified_numbers(u.office_label)
    for d in direct:
        if d.evidence_kind == "observation":
            continue
        theirs = qualified_numbers(d.office_label)
        if any(numbers[q] != theirs[q] for q in numbers.keys() & theirs.keys()):
            return False
    if u.span.precision == "year":
        if u.span.year not in years_of(span):
            return False
    elif not _overlap(u.span, span):
        return False
    level = _level(direct)
    if u.level != level and "unknown" not in (u.level, level):
        return False
    stated = _round(direct)
    return u.round is None or stated is None or u.round == stated


def umbrella_fits(umbrella: Claim, contest: Contest) -> bool:
    return umbrella_covers(umbrella, contest.members, contest.direct(), contest.span)


def _links(run: _Run) -> None:
    """Step 10: each claim of the umbrella list links to the contests it fits, or is loose."""
    here = _by_place(run.contests)
    for u in run.in_order(run.umbrellas):
        fits = [k for k in here.get(u.place_id, []) if umbrella_fits(u, k)]
        if fits:
            run.links.append((u, fits))
        else:
            run.loose.append(u)


# ---------------------------------------------------------------- steps 11-13


def _aggregate_edge(a: Claim, b: Claim) -> bool:
    """P72, R2-02: two loose claims of one grouping."""
    unrecognised = _unrecognised(a) or _unrecognised(b)
    if unrecognised and norm_name(a.office_label) != norm_name(b.office_label):
        return False
    return (
        a.office_class == b.office_class
        and identity_compatible(a, b, ignore_institution=True)
        and same_source_compatible(a, b)
        and dates_compatible(a, b)
    )


def _aggregates(run: _Run) -> None:
    """Step 11: the loose claims cluster into aggregate contests, resolved as in step 8."""
    run.aggregates = _contests(_cluster(run.loose, _aggregate_edge), "aggregate")
    for k in run.aggregates:
        _resolve(k, run)


def _link(a: Contest, b: Contest) -> None:
    a.possible.add(b)
    b.possible.add(a)


def _hints(contests: Sequence[Contest]) -> None:
    """P73 (a): a claim's previous date names another compatible contest."""
    for k in contests:
        for d in k.direct():
            if d.previous_date_text is None:
                continue
            spans = parse_date_text(d.previous_date_text, default_year=d.span.year).spans
            old = [s for s in spans if s.precision != "year"]
            for other in contests:
                if (
                    other is not k
                    and all(
                        identity_compatible(d, m) and same_source_compatible(d, m)
                        for m in other.members
                    )
                    and any(_overlap(s, other.span) for s in old)
                ):
                    _link(k, other)


def _near_dates(contests: Sequence[Contest]) -> None:
    """P73 (b): compatible contests of one place 1 to 7 days apart."""
    for here in _by_place(contests).values():
        for i, a in enumerate(here):
            for b in here[i + 1 :]:
                if 1 <= gap_days(a.span, b.span) <= _NEAR_DAYS and all(
                    identity_compatible(x, y) and same_source_compatible(x, y)
                    for x in a.members
                    for y in b.members
                ):
                    _link(a, b)


def _event_copies(contests: Sequence[Contest]) -> None:
    """P73 (c): one source's copies of an event (IPU excluded: it names a chamber, R3)."""
    copies: dict[tuple[str, str], list[tuple[Contest, Claim]]] = {}
    for k in contests:
        for c in k.direct():
            if c.source != "ipu" and c.source_event_id is not None:
                copies.setdefault((c.source, c.source_event_id), []).append((k, c))
    for found in copies.values():
        holders: list[Contest] = []
        for k, _ in found:
            if k not in holders:
                holders.append(k)
        for i, a in enumerate(holders):
            for b in holders[i + 1 :]:
                _link(a, b)
        for k in holders:
            intervals = {(c.span.start, c.span.end, c.span.year) for h, c in found if h is k}
            if len(intervals) > 1:
                k.date_conflict = True


def _possible(contests: Sequence[Contest]) -> None:
    """Step 12 (P73), over every contest; each link goes both ways."""
    _hints(contests)
    _near_dates(contests)
    _event_copies(contests)


def _by_child_id(contests: Iterable[Contest]) -> tuple[Contest, ...]:
    return tuple(sorted(contests, key=lambda k: k.child_id))


def _undated(run: _Run) -> list[Undated]:
    """Step 13: the undated pool, clustered with ``joinable``.

    A complete group is one listing with the union of its claims' candidates; an incomplete
    component's claims come back from the clustering as one group each.
    """
    candidates = {c.merge_id: ks for c, ks in run.pool}
    out: list[Undated] = []
    for g in _cluster(run.in_order(c for c, _ in run.pool), joinable):
        possible = {k for c in g.claims for k in candidates[c.merge_id]}
        out.append(Undated(tuple(g.claims), _by_child_id(possible)))
    return out


def match(claims: Sequence[Claim], now: datetime) -> Matching:
    """Match claims into contests, umbrella links, undated groups and pending items."""
    run = _start(claims, now)
    _phase_a(run)
    _phase_b(run)
    _phase_c(run)
    _umbrellas(run)
    _sessions(run)
    _observations(run)
    for k in run.contests:
        _resolve(k, run)
    _phase_d(run)
    _links(run)
    _aggregates(run)
    _possible(run.contests + run.aggregates)
    pending = (Pending(i.kind, i.reason, i.claim, _by_child_id(i.candidates)) for i in run.items)
    links = (Link(u, _by_child_id(ks)) for u, ks in run.links)
    return Matching(
        contests=_by_child_id(run.contests + run.aggregates),
        links=tuple(sorted(links, key=lambda link: link.claim.merge_id)),
        undated=tuple(sorted(_undated(run), key=lambda u: u.claims[0].merge_id)),
        pending=tuple(sorted(pending, key=lambda p: p.claim.merge_id)),
    )
