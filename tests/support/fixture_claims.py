"""Claims parsed from the captured fixtures of all nine adapters, each at its capture day."""

from datetime import UTC, datetime
from functools import cache

from elections_calendar.fetch import Deadline
from elections_calendar.model import Claim
from elections_calendar.sources.aweb import Aweb
from elections_calendar.sources.base import Adapter, ParseResult, RawPages, Registries
from elections_calendar.sources.carter import Carter
from elections_calendar.sources.eeas import Eeas
from elections_calendar.sources.eisa import AJAX, Eisa
from elections_calendar.sources.eisa import URL as EISA_URL
from elections_calendar.sources.electionguide import ElectionGuide
from elections_calendar.sources.ipu import Ipu
from elections_calendar.sources.ndi import Ndi, request
from elections_calendar.sources.osce import Osce
from elections_calendar.sources.wikipedia import Wikipedia
from elections_calendar.window import Window, window_for
from tests.support.fixtures import fixture
from tests.support.pages import Served, raw_pages, result

FIXTURE_NOW = datetime(2026, 10, 19, tzinfo=UTC)
_JSON = "application/json; charset=utf-8"
_ORDER = ("electionguide", "wikipedia", "osce", "ipu", "aweb", "carter", "eeas", "ndi", "eisa")


def _window(day: int) -> Window:
    return window_for(datetime(2026, 10, day, tzinfo=UTC))


def _single(
    adapter: Adapter, source: str, name: str, reg: Registries
) -> tuple[RawPages, ParseResult]:
    win = _window(18)
    req = adapter.requests(win)[0]
    raw = raw_pages(source, [(req, result(fixture(source, name, "2026-10-18"), url=req.url))])
    return raw, adapter.parse(raw, win, reg)


@cache
def fixture_results() -> dict[str, tuple[RawPages, ParseResult]]:
    reg = Registries.load()
    out: dict[str, tuple[RawPages, ParseResult]] = {}
    win = _window(16)
    eg = ElectionGuide()
    raw = raw_pages(
        "electionguide",
        [
            (r, result(fixture("electionguide", f"{r.key}.html"), url=r.url))
            for r in eg.requests(win)
        ],
    )
    out["electionguide"] = (raw, eg.parse(raw, win, reg))
    wp = Wikipedia()
    raw = raw_pages(
        "wikipedia",
        [
            (r, result(fixture("wikipedia", f"{r.key}.json"), url=r.url, content_type=_JSON))
            for r in wp.requests(win)
        ],
    )
    out["wikipedia"] = (raw, wp.parse(raw, win, reg))
    out["osce"] = _single(Osce(), "osce", "elections.html", reg)
    out["ipu"] = _single(Ipu(), "ipu", "elections.html", reg)
    out["aweb"] = _single(Aweb(), "aweb", "calendar.html", reg)
    out["carter"] = _single(Carter(), "carter", "observed.html", reg)
    out["eeas"] = _single(Eeas(), "eeas", "missions.html", reg)
    win = _window(19)
    served = {request(n).url: fixture("ndi", f"p{n}.html", "2026-10-19") for n in range(5)}
    ndi = Ndi()
    raw = RawPages("ndi", tuple(ndi.fetch(win, Served(served), Deadline.after(60))), ())
    out["ndi"] = (raw, ndi.parse(raw, win, reg))
    served = {
        EISA_URL: fixture("eisa", "calendar.html", "2026-10-19"),
        AJAX.format(table_id="38978"): fixture("eisa", "y2026.json", "2026-10-19"),
        AJAX.format(table_id="34700"): fixture("eisa", "y2025.json", "2026-10-19"),
    }
    eisa = Eisa()
    raw = RawPages("eisa", tuple(eisa.fetch(win, Served(served), Deadline.after(60))), ())
    out["eisa"] = (raw, eisa.parse(raw, win, reg))
    return out


@cache
def fixture_claims() -> tuple[Claim, ...]:
    results = fixture_results()
    return tuple(c for s in _ORDER for c in results[s][1].claims)


def fixture_claim(claim_id: str) -> Claim:
    for c in fixture_claims():
        if c.claim_id == claim_id:
            return c
    raise KeyError(claim_id)
