"""Claims for merge tests: ``mk`` builds a valid claim from a unit id and field overrides."""

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

from elections_calendar.merge.cards import build
from elections_calendar.merge.match import match
from elections_calendar.model import Claim, DateSpan, MergeResult
from elections_calendar.places import PlaceRegistry
from elections_calendar.window import window_for

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)


def day(y: int, m: int, d: int) -> DateSpan:
    return DateSpan.day(date(y, m, d))


def days(y1: int, m1: int, d1: int, y2: int, m2: int, d2: int) -> DateSpan:
    return DateSpan.days(date(y1, m1, d1), date(y2, m2, d2))


def month(y: int, m: int) -> DateSpan:
    return DateSpan.month(y, m)


def months(y1: int, m1: int, y2: int, m2: int) -> DateSpan:
    return DateSpan.months(y1, m1, y2, m2)


def year(y: int) -> DateSpan:
    return DateSpan.of_year(y)


BASE: dict[str, Any] = dict(
    link="https://example.test/e",
    source_event_id=None,
    place_raw="Sweden",
    place_id="iso:SE",
    jurisdiction=None,
    jurisdiction_kind="nationwide",
    level="national",
    institution="iso:SE/riksdag",
    office_class="legislature",
    office_label="Riksdag",
    aggregate=False,
    kind="candidate_election",
    round=None,
    date_meaning="voting_period",
    date_status="unknown",
    date_text="15 November 2026",
    status_claim=None,
    previous_date_text=None,
    evidence_kind="calendar",
    indirect=False,
)
OBS: dict[str, Any] = dict(
    evidence_kind="observation",
    office_class="general",
    aggregate=True,
    kind="aggregate",
    institution=None,
    level="unknown",
    date_meaning="unknown",
    office_label="Election observation mission",
)
UMB: dict[str, Any] = dict(
    office_class="general",
    aggregate=True,
    kind="aggregate",
    institution=None,
    office_label="General elections",
)
RENEW: dict[str, Any] = dict(
    evidence_kind="expected_renewal", date_status="tentative", date_meaning="expected_window"
)


def mk(unit_id: str, n: int = 0, **fields: Any) -> Claim:
    """A valid claim; the source is the unit id's prefix, the id ``<unit_id>#<n>``."""
    values = {**BASE, **fields}
    values.setdefault("span", day(2026, 11, 15))
    return Claim(
        unit_id=unit_id, claim_id=f"{unit_id}#{n}", source=unit_id.split(":", 1)[0], **values
    )


WPn = "wikipedia:national-2026@rev1"
WPl = "wikipedia:local-2026@rev2"
EGU = "electionguide:upcoming"
EGP = "electionguide:past"

# The presets (the brief's values, verbatim).
PE = dict(place_id="iso:PE", place_raw="Peru", institution=None, level="subnational",
          span=day(2026, 11, 22))
CH = dict(place_id="iso:CH", place_raw="Switzerland", institution=None, office_class="referendum",
          span=day(2026, 11, 29))
GB = dict(place_id="iso:GB", place_raw="United Kingdom", institution="iso:GB/house-of-commons",
          office_class="lower_house", kind="by_election",
          office_label="House of Commons by-election", span=day(2026, 11, 26))
XS = dict(place_id="x:south-ossetia", place_raw="South Ossetia",
          institution="x:south-ossetia/president", office_class="head_of_state",
          office_label="President")
IP = dict(**RENEW, source_event_id="ipu:SE-LC")
RU = dict(place_id="iso:RU", place_raw="Russia", institution="iso:RU/state-duma",
          office_class="lower_house", office_label="State Duma")
BR = dict(place_id="iso:BR", place_raw="Brazil")
PRES_BR = dict(**BR, institution="iso:BR/president", office_class="head_of_state",
               office_label="President")
LEG = dict(institution=None, office_class="legislature", aggregate=True, office_label="Parliament")
GD = dict(place_id="iso:GD", place_raw="Grenada", span=day(2026, 11, 5))
GD_IPU = dict(**RENEW, institution="iso:GD/house-of-representatives", office_class="lower_house",
              office_label="House of Representatives")
ES = dict(place_id="iso:ES", place_raw="Spain", span=day(2026, 11, 29))
SS = dict(place_id="iso:SS", place_raw="South Sudan", span=day(2026, 12, 22))
SI = dict(place_id="iso:SI", place_raw="Slovenia")
US = dict(place_id="iso:US", place_raw="United States",
          institution="iso:US/house-of-representatives", office_class="lower_house",
          kind="by_election", jurisdiction="Louisiana", jurisdiction_kind="subdivision",
          level="unknown", span=day(2026, 11, 3))
KG = dict(place_id="iso:KG", place_raw="Kyrgyzstan", institution="iso:KG/president",
          office_class="head_of_state", office_label="President")
CI = dict(place_id="iso:CI", place_raw="Côte d'Ivoire", institution="iso:CI/president",
          office_class="head_of_state", span=day(2026, 10, 25))
CO = dict(place_id="iso:CO", place_raw="Colombia")
LOWER = dict(**CO, institution="iso:CO/chamber", office_class="lower_house",
             office_label="Chamber of Representatives")
UPPER = dict(**CO, institution="iso:CO/senate", office_class="upper_house", office_label="Senate")
COUNCIL = dict(institution=None, office_class="local_council", office_label="Municipal councils",
               level="subnational")
GA = dict(place_id="iso:US", place_raw="United States", institution=None, level="subnational",
          jurisdiction="Georgia", jurisdiction_kind="subdivision", span=day(2026, 5, 19))
MB = dict(span=month(2026, 11), date_meaning="unknown", date_text="November 2026")
NOV = dict(span=month(2026, 11), date_meaning="unknown")
BRP = {**PRES_BR, "office_label": "Brazilian Presidency"}
EGE = dict(source_event_id="electionguide:5259")


def cl(unit_id: str, *presets: Mapping[str, Any], n: int = 0, **fields: Any) -> Claim:
    """``mk`` with presets applied left to right, then the fields (later values win)."""
    values: dict[str, Any] = {}
    for preset in presets:
        values.update(preset)
    return mk(unit_id, n, **{**values, **fields})


def result(*claims: Claim, now: datetime = NOW) -> MergeResult:
    """Match and build ``claims`` (Tasks 4 and 5); Task 6's conservation tests import it."""
    return build(match(list(claims), now), window=window_for(now), places=PlaceRegistry.load())
