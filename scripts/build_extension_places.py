"""Build extension/places.json, the extension's place table (Plan 5b-2 Task 2; D3, P140).

The table is generated from data/places.yaml and never edited by hand:

    {"names": {<every name exactly as written>: place_id},
     "places": {place_id: {"display": ..., "parent": ... or null}}}

Keys are sorted, separators compact, UTF-8 without escapes, with a final newline. A name is a
place's display or one of its aliases (the display is also an alias). The extension looks names
up exactly, so no normalisation happens in the browser.

    .venv\\Scripts\\python.exe -m scripts.build_extension_places
"""

import json
import sys
from pathlib import Path
from typing import Any

import yaml

from elections_calendar.places import DEFAULT_PLACES

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "extension" / "places.json"


def build(places: Path = DEFAULT_PLACES) -> bytes:
    raw: dict[str, dict[str, Any]] = yaml.safe_load(places.read_text(encoding="utf-8"))
    names: dict[str, str] = {}
    table: dict[str, dict[str, str | None]] = {}
    for place_id, entry in raw.items():
        table[place_id] = {"display": entry["display"], "parent": entry["parent"]}
        for name in (entry["display"], *entry["aliases"]):
            owner = names.setdefault(name, place_id)
            if owner != place_id:
                raise ValueError(f"name {name!r} names both {owner} and {place_id}")
    text = json.dumps(
        {"names": names, "places": table},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return (text + "\n").encode("utf-8")


def main() -> int:
    data = build()
    OUT.write_bytes(data)
    print(f"{len(data)} bytes -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
