"""The conservation audit (spec 10.8, 10.9; P79, R2-04, R2-05).

``check`` takes the input claims and a ``MergeResult`` and returns the problems it finds, as
sorted messages per check. An empty tuple means every input is accounted for exactly where its
disposition says, nothing was changed, and no child holds a wrong merge or misses a partner.
"""

from collections import Counter, defaultdict
from collections.abc import Iterable
from itertools import combinations

from elections_calendar.merge.identity import (
    CHAMBERS,
    REFERENDA,
    dates_compatible,
    identity_compatible,
    joinable,
    same_source_compatible,
)
from elections_calendar.merge.match import umbrella_covers
from elections_calendar.model import Card, Child, Claim, Disposition, MergeResult

_JOINED = ("anchor_member", "standalone")
_CHILD_KINDS = ("anchor_member", "standalone", "attached", "provisional", "umbrella_link")


def _is_member(rejected_reason: str | None) -> bool:
    return rejected_reason != "provisional"


def check(claims: Iterable[Claim], result: MergeResult) -> tuple[str, ...]:
    """Every problem in ``result``, check by check (each check's messages sorted).

    ``claims`` may be any iterable; it is read once (into ``by_id``).
    """
    by_id = {c.merge_id: c for c in claims}
    cards: tuple[Card, ...] = result.cards
    children: list[Child] = [k for card in cards for k in card.children]
    kids = {k.child_id: k for k in children}
    group_of = {k.child_id: card.group_id for card in cards for k in card.children}
    disps: dict[str, list[Disposition]] = defaultdict(list)
    for d in result.dispositions:
        disps[d.merge_id].append(d)
    out: list[str] = []

    # 1. ids
    id_lists = (
        [k.child_id for k in children],
        [card.group_id for card in cards],
        [u.undated_id for u in result.undated],
        [a.item_id for a in result.attention],
    )
    found = [f"duplicate id: {i}" for ids in id_lists for i, n in Counter(ids).items() if n > 1]
    out += sorted(found)

    # 2. dispositions
    found = [f"no disposition: {m}" for m in by_id if m not in disps]
    found += [f"duplicate disposition: {m}" for m, ds in disps.items() if len(ds) > 1]
    found += [f"unknown input: {m}" for m in disps if m not in by_id]
    out += sorted(found)

    # 3. targets
    pools = {
        "undated": {u.undated_id for u in result.undated},
        "attention": {a.item_id for a in result.attention},
    }
    found = []
    for d in result.dispositions:
        pool = kids.keys() if d.kind in _CHILD_KINDS else pools[d.kind]
        found += [f"dangling target: {d.merge_id} -> {t}" for t in d.targets if t not in pool]
    out += sorted(found)

    # 4. holders
    held = [s.claim for k in children for s in k.sources]
    held += [u for card in cards for u in card.umbrellas]
    held += [c for listing in result.undated for c in listing.claims]
    bad: set[str] = set()
    for c in held:
        if c.merge_id not in by_id:
            bad.add(f"unknown holder: {c.merge_id}")
        elif c != by_id[c.merge_id]:
            bad.add(f"changed claim: {c.merge_id}")
    for item in result.attention:
        bad.update(f"unknown holder: {m}" for m in item.merge_ids if m not in by_id)
    out += sorted(bad)

    # 5. placement
    holders: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for k in children:
        for s in k.sources:
            where = "member" if _is_member(s.rejected_reason) else "provisional"
            holders[s.claim.merge_id].append((where, k.child_id))
    for card in cards:
        for umbrella in card.umbrellas:
            holders[umbrella.merge_id].append(("card", card.group_id))
    for listing in result.undated:
        for c in listing.claims:
            holders[c.merge_id].append(("listing", listing.undated_id))
    for item in result.attention:
        if item.kind != "undated_listing":
            for m in item.merge_ids:
                holders[m].append(("item", item.item_id))
    found = []
    for m, ds in disps.items():
        if m not in by_id or len(ds) != 1:
            continue
        d = ds[0]
        if d.kind in ("anchor_member", "standalone", "attached"):
            want = [("member", t) for t in d.targets]
        elif d.kind == "provisional":
            want = [("provisional", t) for t in d.targets]
        elif d.kind == "umbrella_link":
            groups = {group_of[t] for t in d.targets if t in group_of}
            want = [("card", g) for g in sorted(groups)]
        elif d.kind == "undated":
            want = [("listing", t) for t in d.targets]
        else:
            want = [("item", t) for t in d.targets]
        if sorted(holders[m]) != sorted(want):
            found.append(f"misplaced: {m}")
    out += sorted(found)

    # per-child views for checks 6 to 8
    def members_of(k: Child) -> list[Claim]:
        return [s.claim for s in k.sources if _is_member(s.rejected_reason)]

    def joined_of(k: Child) -> list[Claim]:
        return sorted(
            (
                c
                for c in members_of(k)
                if any(
                    d.kind in _JOINED and k.child_id in d.targets for d in disps.get(c.merge_id, ())
                )
            ),
            key=lambda c: c.merge_id,
        )

    joined = {k.child_id: joined_of(k) for k in children}

    def covers(u: Claim, k: Child) -> bool:
        return umbrella_covers(u, joined[k.child_id], members_of(k), k.span)

    # 6. coverage
    plain = [k for k in children if not k.aggregate]
    found = []
    for m, ds in disps.items():
        for d in ds:
            if d.kind == "umbrella_link" and m in by_id:
                want_ids = sorted(k.child_id for k in plain if covers(by_id[m], k))
                if list(d.targets) != want_ids:
                    found.append(f"wrong coverage: {m}")
    for k in children:
        if k.aggregate:
            for c in joined[k.child_id]:
                if any(covers(c, j) for j in plain):
                    found.append(f"wrong coverage: {c.merge_id}")
    out += sorted(found)

    # 7. wrong merge
    found = []
    for k in children:
        for s in k.sources:
            c = s.claim
            if (
                c.evidence_kind == "observation" or s.rejected_reason == "provisional"
            ) and c.place_id != k.place_id:
                found.append(f"wrong merge: {k.child_id} holds {c.merge_id} from another place")
        ident = sorted(
            (c for c in members_of(k) if c.evidence_kind != "observation"),
            key=lambda c: c.merge_id,
        )
        c7 = {
            c.merge_id
            for c in ident
            if not k.aggregate and c.office_class == "legislature" and c.aggregate
        }
        if c7 and any(
            c.merge_id not in c7 and (c.office_class not in CHAMBERS or c.kind in REFERENDA)
            for c in ident
        ):
            found.append(f"wrong merge: {k.child_id} has a legislature umbrella outside a chamber")
        for a, b in combinations(ident, 2):
            loose = a.merge_id in c7 or b.merge_id in c7
            if not (
                identity_compatible(
                    a,
                    b,
                    relax_jurisdiction=True,
                    ignore_kind=loose,
                    ignore_institution=loose or k.aggregate,
                )
                and same_source_compatible(a, b)
            ):
                found.append(f"wrong merge: {k.child_id}: {a.merge_id} and {b.merge_id}")
        jc = joined[k.child_id]
        for a, b in combinations(jc, 2):
            if not dates_compatible(a, b):
                found.append(
                    f"wrong merge: {k.child_id}: {a.merge_id} and {b.merge_id} have other dates"
                )
        if k.aggregate and len({c.office_class for c in ident}) > 1:
            found.append(f"wrong merge: {k.child_id} has two office classes")
        if not k.date_conflict:
            for c in members_of(k):
                if (
                    c.evidence_kind != "observation"
                    and any(
                        d.kind == "attached" and k.child_id in d.targets
                        for d in disps.get(c.merge_id, ())
                    )
                    and not all(dates_compatible(c, j) for j in jc)
                ):
                    found.append(
                        f"wrong merge: {k.child_id}: {c.merge_id} has another date"
                        " and no date_conflict"
                    )
    out += sorted(found)

    # 8. missed merge
    by_place: dict[str, list[Child]] = defaultdict(list)
    for k in children:
        if not k.ambiguous and not k.aggregate:
            by_place[k.place_id].append(k)
    partners: dict[str, set[str]] = defaultdict(set)
    for ks in by_place.values():
        for first, second in combinations(ks, 2):
            union = joined[first.child_id] + joined[second.child_id]
            if all(joinable(x, y) for x, y in combinations(union, 2)):
                partners[first.child_id].add(second.child_id)
                partners[second.child_id].add(first.child_id)
    missed = {
        tuple(sorted((a, next(iter(p)))))
        for a, p in partners.items()
        if len(p) == 1 and len(partners[next(iter(p))]) == 1
    }
    out += sorted(f"missed merge: {a} and {b}" for a, b in missed)

    # 9. possible matches
    owners = [
        *((k.child_id, k.possible_matches) for k in children),
        *((u.undated_id, u.possible_matches) for u in result.undated),
        *((a.item_id, a.possible_matches) for a in result.attention),
    ]
    out += sorted(
        f"dangling possible match: {owner} -> {p}"
        for owner, matches in owners
        for p in matches
        if p not in kids
    )
    return tuple(out)
