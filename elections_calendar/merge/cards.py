"""Children, cards, undated listings, attention items and dispositions (spec 5.3-5.5, 10.7).

``build`` turns a ``Matching`` into the merge's ``MergeResult``. Plan 3's P75-P77, P79, P81,
P82, R2-01 and D4 give the rules; every order below is total, so the result depends only on
the set of input claims.
"""

from collections.abc import Iterable, Mapping, Sequence
from datetime import date

from elections_calendar.merge.identity import SOURCE_ORDER, claim_order, dates_compatible, short_id
from elections_calendar.merge.match import (
    Contest,
    Matching,
    Pending,
    Undated,
    contest_level,
    contest_round,
)
from elections_calendar.model import (
    MAX_ATTENTION_TEXT,
    MAX_TYPE,
    AttentionItem,
    BibEntry,
    Card,
    Child,
    ChildSource,
    Claim,
    Disposition,
    DispositionKind,
    JurisdictionKind,
    MergeResult,
    Relevance,
    UndatedListing,
)
from elections_calendar.offices import extract_round
from elections_calendar.places import PlaceRegistry
from elections_calendar.text import collapse_ws, norm_name
from elections_calendar.window import Window

CLASS_ORDER: tuple[str, ...] = (
    "head_of_state",
    "lower_house",
    "upper_house",
    "legislature",
    "governor",
    "mayor",
    "local_council",
    "referendum",
    "general",
)
PLURAL: Mapping[str, str] = {
    "head_of_state": "Presidents",
    "lower_house": "Lower houses",
    "upper_house": "Upper houses",
    "legislature": "Legislatures",
    "governor": "Governors",
    "mayor": "Mayors",
    "local_council": "Local councils",
    "referendum": "Referendums",
    "general": "Elections",
}
_ORDINAL = {1: "1st", 2: "2nd", 3: "3rd"}
_SCOPED: tuple[JurisdictionKind, ...] = ("named", "subdivision")


# ---------------------------------------------------------------- labels and types


def display_label(child: Child) -> str:
    """The child's label with its round and jurisdiction made explicit (P76)."""
    label = child.office_label
    if child.round is not None and extract_round(label)[0] is None:
        n = child.round
        label += f" ({_ORDINAL.get(n, f'{n}th')} round)"
    jurisdiction = child.jurisdiction
    if (
        child.jurisdiction_kind in _SCOPED
        and jurisdiction
        and norm_name(jurisdiction) not in norm_name(label)
    ):
        label = f"{jurisdiction}: {label}"
    return label


def card_type(children: Sequence[Child]) -> str:
    """A card's type: a label, or the children's jurisdictions or labels, within MAX_TYPE (P76)."""
    if len(children) == 1:
        text = display_label(children[0])
        return text if len(text) <= MAX_TYPE else text[: MAX_TYPE - 1] + "…"
    classes = {c.office_class for c in children}
    named = all(c.jurisdiction_kind in _SCOPED and c.jurisdiction for c in children)
    items: list[str]
    if (
        len(classes) == 1
        and named
        and len({norm_name(c.jurisdiction or "") for c in children}) == len(children)
    ):
        items = [c.jurisdiction or "" for c in children]
        sep = "; " if any("," in item for item in items) else ", "
        plural = PLURAL[next(iter(classes))]

        def render(n: int) -> str:
            more = len(items) - n
            tail = f" (+{more} more)" if more else ""
            return f"{plural}: {sep.join(items[:n])}{tail} ({len(children)})"
    else:
        items = [display_label(c) for c in children]

        def render(n: int) -> str:
            more = len(items) - n
            return " · ".join(items[:n]) + (f" (+{more} more)" if more else "")

    for n in range(len(items), 0, -1):
        if len(render(n)) <= MAX_TYPE:
            return render(n)
    return render(1)[: MAX_TYPE - 1] + "…"


def relevance_of(claim: Claim, window: Window) -> Relevance:
    """Whether a claim's own date is in or after the window (P77, G07)."""
    span = claim.span
    if span.precision == "year":
        later = span.year >= window.start.year
    else:
        assert span.end is not None
        later = span.end >= window.start
    return "in_or_after_window" if later else "before_window"


# ---------------------------------------------------------------- display names, bibliography


def _display(claims: Iterable[Claim], places: PlaceRegistry) -> tuple[str, str | None]:
    """(country, country_code) of the claims' place (P79)."""
    first = min(claims, key=claim_order)
    if first.place_id in places:
        place = places.get(first.place_id)
        return place.display, place.country_code
    return first.place_raw, None


def _bibliography(claims: Iterable[Claim]) -> tuple[BibEntry, ...]:
    """One entry per source, from its first claim in the walk, in SOURCE_ORDER (5.4)."""
    first: dict[str, str] = {}
    for c in claims:
        first.setdefault(c.source, c.link)
    return tuple(BibEntry(s, first[s]) for s in SOURCE_ORDER if s in first)


# ---------------------------------------------------------------- children


def _occurrence_confirmed(k: Contest, identity: Sequence[Claim]) -> bool:
    """A held identity claim, cached or not, for the selected date; no resolved word (D4)."""
    assert k.status is not None and k.selection is not None and k.selection.claim is not None
    if k.status.resolved in ("cancelled", "postponed"):
        return False
    chosen = k.selection.claim
    return any(c.status_claim == "held" and dates_compatible(c, chosen) for c in identity)


def _rescheduled_from(identity: Sequence[Claim]) -> tuple[str, ...]:
    """The old dates of a rescheduling as the sources wrote them: distinct, collapsed, sorted."""
    dates = (collapse_ws(c.previous_date_text) for c in identity if c.previous_date_text)
    return tuple(sorted(set(dates)))


def _child(k: Contest, places: PlaceRegistry) -> Child:
    assert k.selection is not None and k.selection.claim is not None and k.status is not None
    selected, status = k.selection.claim, k.status
    direct = sorted(k.direct(), key=claim_order)
    identity = [c for c in direct if c.evidence_kind != "observation"]
    pool = [c for c in identity if k.origin == "aggregate" or not c.aggregate]
    label = (pool or direct)[0]
    institutions = {c.institution for c in identity if c.institution is not None}
    scoped = [c for c in identity if c.jurisdiction_kind != "unknown"]
    country, code = _display(direct, places)
    reasons = k.selection.reasons
    child_sources = [
        ChildSource(c, reasons[c.merge_id] is None, reasons[c.merge_id]) for c in direct
    ]
    child_sources += [
        ChildSource(c, False, "provisional") for c in sorted(k.provisional, key=claim_order)
    ]
    return Child(
        child_id=k.child_id,
        place_id=label.place_id,
        country=country,
        country_code=code,
        jurisdiction=scoped[0].jurisdiction if scoped else None,
        jurisdiction_kind=scoped[0].jurisdiction_kind if scoped else "unknown",
        level=contest_level(k),
        institution=next(iter(institutions)) if len(institutions) == 1 else None,
        office_class=label.office_class,
        office_label=label.office_label,
        kind=label.kind,
        round=contest_round(k),
        indirect=any(c.indirect for c in identity),
        aggregate=k.origin == "aggregate",
        span=selected.span,
        date_meaning=selected.date_meaning,
        date_status=selected.date_status,
        status=status.status,
        occurrence_confirmed=_occurrence_confirmed(k, identity),
        status_conflict=k.status_conflict,
        date_conflict=k.date_conflict,
        unverified=k.selection.unverified,
        ambiguous=k.ambiguous,
        rescheduled_from=_rescheduled_from(identity) if status.rescheduled else (),
        provisional_date=k.provisional_date,
        possible_matches=tuple(sorted(q.child_id for q in k.possible)),
        sources=tuple(child_sources),
    )


# ---------------------------------------------------------------- cards


def _card_key(child: Child) -> tuple[str, ...]:
    return (
        child.place_id,
        child.level,
        child.span.start.isoformat() if child.span.start else "",
        child.span.end.isoformat() if child.span.end else "",
        child.span.precision,
        child.date_meaning,
        child.date_status,
        child.status,
    )


def _child_order(child: Child) -> tuple[int, str, str]:
    return (
        CLASS_ORDER.index(child.office_class),
        norm_name(child.jurisdiction or ""),
        child.child_id,
    )


def _cards(
    contests: Sequence[Contest], matching: Matching, places: PlaceRegistry
) -> tuple[Card, ...]:
    built = [(k, _child(k, places)) for k in contests]
    groups: dict[tuple[str, ...], list[tuple[Contest, Child]]] = {}
    for k, child in built:
        groups.setdefault(_card_key(child), []).append((k, child))
    cards: list[Card] = []
    for key, members in groups.items():
        members.sort(key=lambda m: _child_order(m[1]))
        children = tuple(child for _, child in members)
        ids = {child.child_id for child in children}
        umbrellas = sorted(
            (
                link.claim
                for link in matching.links
                if any(k.child_id in ids for k in link.contests)
            ),
            key=claim_order,
        )
        walk = [
            s.claim
            for child in children
            for s in child.sources
            if s.rejected_reason != "provisional"
        ]
        country, code = _display((c for k, _ in members for c in k.direct()), places)
        first = children[0]
        cards.append(
            Card(
                group_id=short_id(["|".join(key)]),
                place_id=first.place_id,
                country=country,
                country_code=code,
                level=first.level,
                span=first.span,
                date_meaning=first.date_meaning,
                date_status=first.date_status,
                status=first.status,
                type=card_type(children),
                children=children,
                sources=_bibliography([*walk, *umbrellas]),
                umbrella_sources=_bibliography(umbrellas),
                umbrellas=tuple(umbrellas),
            )
        )
    cards.sort(key=lambda c: (c.span.start or date.min, c.place_id, c.group_id))
    return tuple(cards)


# ---------------------------------------------------------------- listings and items


def _cut(text: str) -> str:
    return collapse_ws(text)[:MAX_ATTENTION_TEXT]


def _listing(u: Undated, places: PlaceRegistry) -> UndatedListing:
    claims = sorted(u.claims, key=claim_order)
    first = claims[0]
    country, _ = _display(claims, places)
    return UndatedListing(
        undated_id=short_id(["undated", *(c.merge_id for c in claims)]),
        place_id=first.place_id,
        country=country,
        office_label=first.office_label,
        year=first.span.year,
        claims=tuple(claims),
        sources=_bibliography(claims),
        possible_matches=tuple(sorted(k.child_id for k in u.possible)),
    )


def _pending_item(p: Pending, window: Window, places: PlaceRegistry) -> AttentionItem:
    c = p.claim
    country, _ = _display([c], places)
    text = f"{country}: {c.office_label} ({c.date_text})"
    if p.kind == "provisional_change":
        text += ", from an incomplete fetch"
    return AttentionItem(
        item_id=short_id([p.kind, c.merge_id]),
        kind=p.kind,
        source=c.source,
        link=c.link,
        snapshot_id=c.snapshot_id,
        relevance=relevance_of(c, window),
        text=_cut(text),
        reason=p.reason,
        possible_matches=tuple(sorted(k.child_id for k in p.candidates)),
        merge_ids=(c.merge_id,),
        undated_id=None,
    )


def _listing_item(listing: UndatedListing, window: Window) -> AttentionItem:
    first = listing.claims[0]
    relevant = any(relevance_of(c, window) == "in_or_after_window" for c in listing.claims)
    return AttentionItem(
        item_id=short_id(["undated_listing", listing.undated_id]),
        kind="undated_listing",
        source=first.source,
        link=first.link,
        snapshot_id=first.snapshot_id,
        relevance="in_or_after_window" if relevant else "before_window",
        text=_cut(f"{listing.country}: {listing.office_label} ({listing.year}), date not given"),
        reason="undated",
        possible_matches=listing.possible_matches,
        merge_ids=tuple(sorted(c.merge_id for c in listing.claims)),
        undated_id=listing.undated_id,
    )


# ---------------------------------------------------------------- build


def build(matching: Matching, *, window: Window, places: PlaceRegistry) -> MergeResult:
    """Children, cards, listings, attention items and one disposition per claim."""
    cards = _cards(matching.contests, matching, places)
    listings = sorted((_listing(u, places) for u in matching.undated), key=lambda x: x.undated_id)
    items = [_pending_item(p, window, places) for p in matching.pending]
    items += [_listing_item(x, window) for x in listings]
    items.sort(key=lambda i: i.item_id)

    dispositions: list[Disposition] = []
    for k in matching.contests:
        member_kind: DispositionKind = "anchor_member" if k.origin == "anchor" else "standalone"
        dispositions += [Disposition(c.merge_id, member_kind, (k.child_id,)) for c in k.members]
        dispositions += [Disposition(c.merge_id, "attached", (k.child_id,)) for c in k.attached]
        dispositions += [
            Disposition(c.merge_id, "provisional", (k.child_id,)) for c in k.provisional
        ]
    dispositions += [
        Disposition(
            link.claim.merge_id, "umbrella_link", tuple(sorted(k.child_id for k in link.contests))
        )
        for link in matching.links
    ]
    listing_of = {c.merge_id: x.undated_id for x in listings for c in x.claims}
    dispositions += [Disposition(m, "undated", (u,)) for m, u in listing_of.items()]
    item_of = {i.merge_ids[0]: i.item_id for i in items if i.undated_id is None}
    dispositions += [Disposition(m, "attention", (i,)) for m, i in item_of.items()]
    dispositions.sort(key=lambda d: d.merge_id)
    return MergeResult(cards, tuple(listings), tuple(items), tuple(dispositions))
