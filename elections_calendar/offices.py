"""Office classification (spec §6.3) and level evidence (spec §6.4).

``classify`` turns one office text (already split with ``split_offices``)
into an ``Office``. Scope comes before identity: a chamber's name in the
text does not by itself say which body is elected. The text is *qualified*
when it has a subnational word ("State Senate", "provincial"). The voting
area is not evidence of level: the voters of one state elect its US
senators, so a ``subdivision`` jurisdiction never makes a chamber
subnational (spec §6.4: the level is the institution's). The order of the
rules matters:

1. referendum words, even when the text names a chamber ("Referendum on
   reform of the Senate");
2. a chamber of the place named by its IPU name or an alias, suspended
   chambers included. A name with a word of its own ("State Duma",
   "Knesset", "United States Senate") is national evidence wherever the
   vote is held. A name built only from generic chamber words ("Senate",
   "House of Commons") counts only when the text is not qualified, and then
   only nationwide or for a by-election in a named constituency, so
   "Virginia, Senate" is not the US Senate;
3. head of state, governor, mayor;
4. generic chamber words: "senate" -> the place's one active upper chamber,
   "house of representatives" -> its one active lower chamber (or its only
   chamber), nationwide only; when qualified, a subnational chamber;
   otherwise the class alone, with no level hint, so the source's default
   level applies (a bare "Senate" in a state may be either);
5. local bodies ("municipal", "local", "city council", ...);
6. generic legislature words ("Parliament", "Legislative", "Congress"):
   subnational when qualified or regional; identity only for a place with one
   active, unicameral chamber, nationwide; in a subdivision one body with no
   level hint; otherwise an aggregate (spec §6.3);
7. "General" and anything unrecognised: class ``general``, aggregate.

A body named inside another body's name is not the place's own: a
subnational word directly before the chamber's name or "president"
("Moscow City Duma", "Regional presidents") skips rules 2 and 3, and a
parliament that is not the place's ("European Parliament", "Sami
Parliament") is a legislature aggregate with no level hint, before rule 2.

A by-election says how a seat is filled, not which level owns it: it lends
identity only to a chamber the text names (rule 2), never to generic words.
A suspended or dissolved chamber keeps its identity, so older evidence still
resolves; whether it can hold an election now is the caller's decision.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from elections_calendar.model import JurisdictionKind, Kind, Level, OfficeClass
from elections_calendar.text import collapse_ws, norm_name, slug

DEFAULT_INSTITUTIONS = Path(__file__).resolve().parent.parent / "data" / "institutions.yaml"


def _rx(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


_ROUND = _rx(
    r"\(?\s*\b(?:(?P<n>[1-9])(?:st|nd|rd|th)|(?P<w>first|second|third|fourth))[\s-]+round\b\s*\)?"
    r"|\(?\s*\bround\s+(?P<k>[1-9])\b\s*\)?"
    r"|\(?\s*\brun[\s-]?offs?\b\s*\)?"
)
_ROUND_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4}
_BY_ELECTION = _rx(
    r"\bby[\s-]?elections?\b|\bspecial elections?\b|\bpartial elections?\b"
    r"|\bsupplementary elections?\b"
)
_REFERENDUM = _rx(
    r"\breferend(?:um|ums|a)\b|\bplebiscites?\b|\bpopular (?:votes?|initiatives?)\b"
    r"|\bballot (?:measures?|questions?)\b"
)
_HEAD_OF_STATE = _rx(r"\bpresiden(?:t|ts|cy|tial)\b")
_GOVERNOR = _rx(r"\bgovern(?:or|ors|orial|atorial)\b|\bgubernatorial\b")
_MAYOR = _rx(r"\bmayor(?:s|al|alty)?\b")
_UPPER = _rx(
    r"\bsenat(?:e|es|orial)\b|\bupper (?:house|chamber)\b"
    r"|\bhouse of (?:lords|elders|councillors|councilors)\b"
)
_LOWER = _rx(
    r"\bhouse of (?:representatives|commons|deputies|delegates|assembly)\b"
    r"|\bchamber of deputies\b|\blower (?:house|chamber)\b|\bhouse of the people\b"
)
_LEGISLATURE = _rx(
    r"\bparliament(?:s|ary)?\b|\blegislat(?:ive|ures?)\b|\bnational assembly\b"
    r"|\bassembl(?:y|ies)\b|\bcongress(?:ional)?\b|\bdiet\b"
)
_LOCAL = _rx(
    r"\b(?:municipal(?:ity|ities)?|local|city|town|village|parish|communal|commune|district"
    r"|county|borough|ward|metropolitan)\b"
)
_REGIONAL = _rx(r"\b(?:regional|region|provincial|prefectural|departmental|cantonal)\b")
_SUBNATIONAL = _rx(
    r"\b(?:state|provincial|province|regional|region|prefectural|departmental|cantonal|county"
    r"|municipal|city|territorial)\b"
)
_OTHER_PARLIAMENT = _rx(
    r"\b(?:european|pan-african|central american|andean|mercosur|sami|saami|youth)\s+parliament\b"
)
_COUNCIL = _rx(r"\bcouncil(?:s|lors?|lers?)?\b")
_GENERAL = _rx(r"\bgeneral\b")
_PLURAL_BODY = _rx(r"\b(?:councils|assemblies|elections|governors|mayors)\b|\band\b")
_GOVERNORS = _rx(r"\bgovernors\b")
_MAYORS = _rx(r"\bmayors\b")
_GENERIC_CHAMBER_WORDS = (_UPPER, _LOWER, _LEGISLATURE)
_HOUSES: tuple[tuple[re.Pattern[str], OfficeClass], ...] = (
    (_UPPER, "upper_house"),
    (_LOWER, "lower_house"),
)


ChamberStatus = Literal["active", "suspended", "dissolved"]


@dataclass(frozen=True, slots=True)
class Chamber:
    name: str
    office_class: OfficeClass  # lower_house | upper_house | legislature (unicameral)
    designation: str  # direct | indirect | appointed | other
    aliases: tuple[str, ...]
    status: ChamberStatus  # as of the IPU capture named in data/institutions.yaml

    @property
    def names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)

    @property
    def active(self) -> bool:
        return self.status == "active"


@dataclass(frozen=True, slots=True)
class Office:
    label: str
    office_class: OfficeClass
    institution: str | None
    aggregate: bool
    kind: Kind
    round: int | None
    level_hint: Level | None
    recognised: bool


class InstitutionRegistry:
    def __init__(self, chambers: dict[str, tuple[Chamber, ...]]) -> None:
        self._chambers = chambers

    @classmethod
    def load(cls, path: Path = DEFAULT_INSTITUTIONS) -> InstitutionRegistry:
        raw: dict[str, list[dict[str, Any]]] = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(
            {
                place_id: tuple(
                    Chamber(
                        c["name"],
                        c["office_class"],
                        c["designation"],
                        tuple(c["aliases"]),
                        c["status"],
                    )
                    for c in items
                )
                for place_id, items in raw.items()
            }
        )

    def chambers(self, place_id: str) -> tuple[Chamber, ...]:
        return self._chambers.get(place_id, ())

    def unicameral(self, place_id: str) -> Chamber | None:
        """The place's chamber when it has exactly one active chamber, a unicameral one."""
        active = [c for c in self.chambers(place_id) if c.active]
        if len(active) == 1 and active[0].office_class == "legislature":
            return active[0]
        return None


def institution_id(place_id: str, chamber: Chamber) -> str:
    return f"{place_id}/{slug(chamber.name)}"


def extract_round(text: str) -> tuple[int | None, str]:
    """('President (1st round)') -> (1, 'President'). A run-off is round 2."""
    match = _ROUND.search(text)
    if match is None:
        return None, collapse_ws(text)
    if match["n"]:
        number = int(match["n"])
    elif match["w"]:
        number = _ROUND_WORDS[match["w"].casefold()]
    elif match["k"]:
        number = int(match["k"])
    else:
        number = 2
    rest = collapse_ws(f"{text[: match.start()]} {text[match.end() :]}").strip(" ,;-")
    return number, rest


def _name_pattern(needle: str) -> re.Pattern[str] | None:
    key = norm_name(needle)
    return re.compile(rf"(?:^| ){re.escape(key)}(?: |$)") if key else None


def _contains(haystack: str, needle: str) -> bool:
    pattern = _name_pattern(needle)
    return pattern is not None and pattern.search(haystack) is not None


def _subnational_before(text: str, needle: str) -> bool:
    """Whether a subnational word comes right before ``needle`` ("City" in "Moscow City Duma")."""
    key = norm_name(text)
    pattern = _name_pattern(needle)
    found = pattern.search(key) if pattern is not None else None
    words = key[: found.start()].split() if found is not None else []
    return bool(words) and _SUBNATIONAL.fullmatch(words[-1]) is not None


def _generic(name: str) -> bool:
    """Whether a chamber name is only generic chamber words ("House of Commons").

    "United States Senate" and "Federal Senate" have words of their own.
    """
    rest = norm_name(name)
    for pattern in _GENERIC_CHAMBER_WORDS:
        rest = pattern.sub(" ", rest)
    return set(rest.split()) <= {"of", "the"}


def _named_chamber(text: str, chambers: Iterable[Chamber]) -> tuple[Chamber, str] | None:
    """The chamber whose longest name or alias occurs in ``text``."""
    key = norm_name(text)
    best: tuple[Chamber, str] | None = None
    for chamber in chambers:
        for name in chamber.names:
            if _contains(key, name) and (best is None or len(name) > len(best[1])):
                best = (chamber, name)
    return best


def _chamber_of_class(chambers: tuple[Chamber, ...], office_class: str) -> Chamber | None:
    matches = [c for c in chambers if c.active and c.office_class == office_class]
    return matches[0] if len(matches) == 1 else None


def keyword_class(text: str) -> OfficeClass | None:
    """The office class generic words in ``text`` point to, ignoring the place."""
    if _REFERENDUM.search(text):
        return "referendum"
    if _HEAD_OF_STATE.search(text):
        return "head_of_state"
    if _GOVERNOR.search(text):
        return "governor"
    if _MAYOR.search(text):
        return "mayor"
    if _UPPER.search(text):
        return "upper_house"
    if _LOWER.search(text):
        return "lower_house"
    if _LOCAL.search(text):
        return "local_council"
    if _LEGISLATURE.search(text):
        return "legislature"
    if _REGIONAL.search(text) or _COUNCIL.search(text):
        return "local_council"
    if _GENERAL.search(text):
        return "general"
    return None


def classify(
    label: str,
    place_id: str,
    jurisdiction_kind: JurisdictionKind,
    registry: InstitutionRegistry,
) -> Office:
    """Classify one office text for a place (spec §6.3); see the module docstring."""
    text = collapse_ws(label)
    round_, rest = extract_round(text)
    by_election = _BY_ELECTION.search(rest) is not None
    nationwide = jurisdiction_kind == "nationwide"
    chambers = registry.chambers(place_id)

    def office(
        office_class: OfficeClass,
        *,
        institution: str | None = None,
        aggregate: bool = False,
        level: Level | None = None,
        recognised: bool = True,
        kind: Kind | None = None,
    ) -> Office:
        if kind is None:
            if aggregate:
                kind = "aggregate"
            elif by_election:
                kind = "by_election"
            else:
                kind = "candidate_election"
        return Office(text, office_class, institution, aggregate, kind, round_, level, recognised)

    if _REFERENDUM.search(rest):
        level: Level | None = "national" if nationwide else (
            "subnational" if jurisdiction_kind in ("named", "subdivision") else None
        )
        return office("referendum", level=level, kind="referendum_day")
    if _OTHER_PARLIAMENT.search(rest):
        return office("legislature", aggregate=True)
    qualified = _SUBNATIONAL.search(rest) is not None
    named = _named_chamber(rest, chambers)
    if named is not None and not _subnational_before(rest, named[1]):
        found, name = named
        constituency = by_election and jurisdiction_kind == "named"
        if not _generic(name) or (not qualified and (nationwide or constituency)):
            return office(
                found.office_class, institution=institution_id(place_id, found), level="national"
            )
    president = _HEAD_OF_STATE.search(rest)
    if president is not None and not _subnational_before(rest, president.group()):
        institution = f"{place_id}/president" if nationwide else None
        return office(
            "head_of_state", institution=institution, level="national" if nationwide else None
        )
    if _GOVERNOR.search(rest):
        return office("governor", aggregate=bool(_GOVERNORS.search(rest)), level="subnational")
    if _MAYOR.search(rest):
        return office("mayor", aggregate=bool(_MAYORS.search(rest)), level="subnational")
    for pattern, house in _HOUSES:
        if pattern.search(rest):
            if qualified:
                return office(house, level="subnational")
            chamber = _chamber_of_class(chambers, house)
            if house == "lower_house" and chamber is None:
                chamber = registry.unicameral(place_id)
            if chamber is not None and nationwide:
                return office(
                    chamber.office_class,
                    institution=institution_id(place_id, chamber),
                    level="national",
                )
            return office(house)
    if _LOCAL.search(rest) or (
        _REGIONAL.search(rest) and not _LEGISLATURE.search(rest)
    ) or (_COUNCIL.search(rest) and not _LEGISLATURE.search(rest)):
        single_body = jurisdiction_kind == "named" and not _PLURAL_BODY.search(rest)
        return office("local_council", aggregate=not single_body, level="subnational")
    if _LEGISLATURE.search(rest):
        if qualified or _REGIONAL.search(rest):
            return office("legislature", level="subnational")
        only = registry.unicameral(place_id)
        if only is not None and nationwide:
            return office(
                "legislature", institution=institution_id(place_id, only), level="national"
            )
        # in one state the words name one body: the state's own, or national seats there
        return office("legislature", aggregate=jurisdiction_kind != "subdivision")
    return office("general", aggregate=True, recognised=bool(_GENERAL.search(rest)))


def split_offices(text: str, place_id: str, registry: InstitutionRegistry) -> list[str]:
    """Split a list of offices ("President (1st round), Chamber of Deputies and Senate").

    Commas first, then "and"/"&", never inside parentheses. A split is kept
    only when every part names an office and the parts are not all of one
    class, so "regional and municipal elections" and "President and Vice
    President" stay whole.
    """
    parts: list[str] = []
    for chunk in _split_if_offices(text, (",",), place_id, registry):
        parts.extend(_split_if_offices(chunk, (" and ", " & "), place_id, registry))
    return parts


def _split_if_offices(
    text: str, separators: tuple[str, ...], place_id: str, registry: InstitutionRegistry
) -> list[str]:
    whole = collapse_ws(text)
    parts = [p for p in (collapse_ws(x) for x in _split_top_level(whole, separators)) if p]
    if len(parts) < 2:
        return [whole] if whole else []
    classes = [_class_of(p, place_id, registry) for p in parts]
    if all(c is not None for c in classes) and len(set(classes)) > 1:
        return parts
    return [whole]


def _class_of(part: str, place_id: str, registry: InstitutionRegistry) -> OfficeClass | None:
    named = _named_chamber(part, registry.chambers(place_id))
    if named is not None:
        return named[0].office_class
    return keyword_class(part)


def _split_top_level(text: str, separators: tuple[str, ...]) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    i = 0
    lowered = text.casefold()
    while i < len(text):
        char = text[i]
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(depth - 1, 0)
        elif depth == 0:
            sep = next((s for s in separators if lowered.startswith(s, i)), None)
            if sep is not None:
                parts.append(text[start:i])
                i += len(sep)
                start = i
                continue
        i += 1
    parts.append(text[start:])
    return parts


def resolve_level(default: Level | None, hints: Iterable[Level | None]) -> Level:
    """Spec §6.4: office/institution evidence overrides the source default.

    Conflicting evidence gives ``unknown``; no evidence gives the default,
    or ``unknown`` when the source has none.
    """
    evidence = {h for h in hints if h is not None and h != "unknown"}
    if len(evidence) > 1:
        return "unknown"
    if evidence:
        return evidence.pop()
    return default or "unknown"


_STOP = frozenset({"of", "the", "and", "for", "in", "a", "an", "election", "elections"})


def _stems(label: str) -> set[str]:
    words = [w for w in re.split(r"[\W_]+", label.casefold()) if len(w) > 1 and w not in _STOP]
    return {w[:6] for w in words}


def labels_similar(a: str, b: str) -> bool:
    """v1's 6-character stem overlap (>= 40% of the smaller label's words).

    Used by the merge only to generate candidates within one office class
    (spec §6.3); it never decides identity. Two different stated rounds are
    never similar.
    """
    round_a, rest_a = extract_round(a)
    round_b, rest_b = extract_round(b)
    if round_a is not None and round_b is not None and round_a != round_b:
        return False
    stems_a, stems_b = _stems(rest_a), _stems(rest_b)
    if not stems_a or not stems_b:
        return True
    return len(stems_a & stems_b) / min(len(stems_a), len(stems_b)) >= 0.4
