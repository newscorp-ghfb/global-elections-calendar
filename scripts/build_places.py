"""Build data/places.yaml (spec §6.2).

Inputs: pycountry (ISO 3166-1 and -2), data/feed_country_history.tsv (frozen
display names) and data/places_manual.yaml. The output is committed and its
diff reviewed; nothing reads pycountry at runtime.

Display name, first rule that applies:
1. the majority spelling in feed history (a tie goes to the legacy canonical);
2. the manual display (subdivisions, extra places) or a display override;
3. the legacy canonical name from v1's COUNTRY_SYNONYMS;
4. pycountry's common_name, else its name.

    .venv\\Scripts\\python.exe -m scripts.build_places
"""

import sys
from pathlib import Path
from typing import Any

import pycountry
import yaml

from elections_calendar.text import norm_name, slug

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "data" / "feed_country_history.tsv"
MANUAL = ROOT / "data" / "places_manual.yaml"
OUT = ROOT / "data" / "places.yaml"

# v1 scraper.py COUNTRY_SYNONYMS: canonical name per ISO code, and its other keys.
LEGACY_CANONICAL: dict[str, str] = {
    "US": "United States", "RU": "Russia", "CD": "DR Congo", "KR": "South Korea",
    "KP": "North Korea", "IR": "Iran", "SY": "Syria", "GB": "United Kingdom",
    "TR": "Turkey", "CZ": "Czech Republic", "SK": "Slovakia", "LA": "Laos",
    "VN": "Vietnam", "TW": "Taiwan", "TZ": "Tanzania", "BO": "Bolivia",
    "VE": "Venezuela", "MD": "Moldova", "MK": "North Macedonia", "SZ": "Eswatini",
    "CV": "Cape Verde", "TL": "East Timor", "MM": "Myanmar",
}  # fmt: skip
LEGACY_ALIASES: dict[str, list[str]] = {
    "US": ["usa", "u.s.", "u.s.a."],
    "CD": ["drc"],
    "GB": ["great britain"],
    "LA": ["lao pdr"],
    "SZ": ["swaziland", "kingdom of eswatini"],
    "MK": ["republic of north macedonia"],
    "MM": ["burma"],
}


COUNTRIES = {country.alpha_2: country for country in pycountry.countries}
SUBDIVISION_CODES = frozenset(sub.code for sub in pycountry.subdivisions)


class BuildError(Exception):
    pass


def load_history(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or line == "country\tcount":
            continue
        name, n = line.rsplit("\t", 1)
        counts[name] = int(n)
    return counts


def build(manual: dict[str, Any], history: dict[str, int]) -> dict[str, dict[str, Any]]:
    places: dict[str, dict[str, Any]] = {}
    for code, country in COUNTRIES.items():
        names = {country.name, getattr(country, "official_name", None)}
        names.add(getattr(country, "common_name", None))
        aliases = {n for n in names if n}
        aliases.update(manual["extra_aliases"].get(code, []))
        if code in LEGACY_CANONICAL:
            aliases.add(LEGACY_CANONICAL[code])
            aliases.update(LEGACY_ALIASES.get(code, []))
        places[f"iso:{code}"] = _entry(None, code, None, aliases)
    for code, item in manual["subdivisions"].items():
        if code not in SUBDIVISION_CODES:
            raise BuildError(f"{code} is not an ISO 3166-2 code")
        parent = code.split("-")[0]
        aliases = {item["display"], *item["aliases"]}
        places[f"iso:{code}"] = _entry(item["display"], parent, f"iso:{parent}", aliases)
    for key, item in manual["extra_places"].items():
        if key != slug(item["display"]):
            raise BuildError(f"x:{key} must be x:{slug(item['display'])}")
        aliases = {item["display"], *item["aliases"]}
        places[f"x:{key}"] = _entry(item["display"], None, item["parent"], aliases)
    for place_id, place in places.items():
        if place["parent"] is not None and place["parent"] not in places:
            raise BuildError(f"{place_id} has unknown parent {place['parent']}")
    index = alias_index(places)
    spellings: dict[str, dict[str, int]] = {}
    for raw, n in history.items():
        owner = index.get(norm_name(raw))
        if owner is None:
            raise BuildError(f"history string {raw!r} matches no place; add an alias")
        spellings.setdefault(owner, {})[raw] = n
        places[owner]["aliases"].add(raw)
    for place_id, place in places.items():
        place["display"] = _display(place_id, place, spellings.get(place_id, {}), manual)
        place["aliases"].add(place["display"])
    alias_index(places)
    return places


def _entry(
    display: str | None, code: str | None, parent: str | None, aliases: set[str]
) -> dict[str, Any]:
    return {"display": display, "country_code": code, "parent": parent, "aliases": set(aliases)}


def alias_index(places: dict[str, dict[str, Any]]) -> dict[str, str]:
    """norm_name(alias) -> place_id; two places sharing an alias fail the build."""
    index: dict[str, str] = {}
    for place_id, place in sorted(places.items()):
        for alias in place["aliases"]:
            key = norm_name(alias)
            if not key:
                raise BuildError(f"{place_id} has an empty alias")
            owner = index.setdefault(key, place_id)
            if owner != place_id:
                raise BuildError(f"alias {alias!r} names both {owner} and {place_id}")
    return index


def _display(
    place_id: str, place: dict[str, Any], spellings: dict[str, int], manual: dict[str, Any]
) -> str:
    code = place["country_code"]
    manual_display = place["display"]  # set for subdivisions and extra places
    is_country = place_id.startswith("iso:") and "-" not in place_id
    override = manual["display_overrides"].get(code) if is_country else None
    if spellings:
        top = max(spellings.values())
        leaders = sorted(name for name, n in spellings.items() if n == top)
        if len(leaders) == 1:
            chosen = leaders[0]
        elif LEGACY_CANONICAL.get(code) in leaders:
            chosen = LEGACY_CANONICAL[code]
        else:
            raise BuildError(f"{place_id}: history tie {leaders} and no legacy canonical name")
        if override is not None or manual_display not in (None, chosen):
            raise BuildError(f"{place_id}: a manual display conflicts with feed history")
        return chosen
    if manual_display:
        return str(manual_display)
    if override is not None:
        if code in LEGACY_CANONICAL:
            raise BuildError(f"{place_id}: display override conflicts with the legacy name")
        return str(override)
    if code in LEGACY_CANONICAL:
        return LEGACY_CANONICAL[code]
    country = COUNTRIES.get(code)
    if country is None:
        raise BuildError(f"{place_id}: no display name")
    return str(getattr(country, "common_name", None) or country.name)


def render(places: dict[str, dict[str, Any]]) -> str:
    body = {
        place_id: {
            "display": place["display"],
            "country_code": place["country_code"],
            "parent": place["parent"],
            "aliases": sorted(place["aliases"]),
        }
        for place_id, place in sorted(places.items())
    }
    header = "# Generated by scripts/build_places.py from pycountry, feed history and\n"
    header += "# data/places_manual.yaml. Do not edit; edit the inputs and rebuild.\n"
    return header + yaml.safe_dump(body, allow_unicode=True, sort_keys=False, width=100)


def main() -> int:
    manual = yaml.safe_load(MANUAL.read_text(encoding="utf-8"))
    places = build(manual, load_history(HISTORY))
    OUT.write_text(render(places), encoding="utf-8", newline="\n")
    print(f"{len(places)} places -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
