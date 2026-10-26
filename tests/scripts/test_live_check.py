"""The bounded live check (Plan 5a Task 9; P116, P125; spec 13.5).

Nothing here touches the network or starts the real scraper: the live run is a fake that copies
the offline fixture artifact, or an edited copy of it. The one real subprocess test starts a
throw-away script and must leave nothing behind on any path.
"""

import contextlib
import copy
import gzip
import json
import os
import shutil
import signal
import subprocess
import sys
import textwrap
import threading
import time
import types
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from elections_calendar import pipeline
from elections_calendar.model import stored_json
from scripts import live_check
from tests.support.artifact import fixture_artifact

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = ROOT / "tests" / "expected" / "2026-10-16.yaml"
REVIEWED_FILE = ROOT / "tests" / "expected" / "reviewed_reschedules.yaml"
SHA = "0" * 40
REVIEWED = [
    {
        "place": "iso:BR",
        "office": "Presidency",
        "round": 1,
        "from": "2026-10-04",
        "to": "2026-10-11",
        "note": "test",
    }
]


def _copy(tmp_path: Path, name: str) -> Path:
    return fixture_artifact(tmp_path / name, code_sha=SHA)


def _edit(path: Path, change: Callable[[Any], None]) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    change(doc)
    path.write_bytes(stored_json(doc))


def _candidate(root: Path, source: str) -> Path:
    return root / "data" / "sources" / source / "candidate.json"


def _page_edit(root: Path, source: str, key: str, change: Callable[[dict[str, Any]], None]) -> None:
    def apply(doc: Any) -> None:
        change(next(p for p in doc["scope"]["pages"] if p["key"] == key))

    _edit(_candidate(root, source), apply)


def _first_page(root: Path, source: str) -> dict[str, Any]:
    doc = json.loads(_candidate(root, source).read_text(encoding="utf-8"))
    page: dict[str, Any] = doc["scope"]["pages"][0]
    return page


def _kill_pid(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True, check=False)
    else:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)


def _wait_gone(pid: int, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not live_check.alive(pid):
            return True
        time.sleep(0.1)
    return not live_check.alive(pid)


# --- run_bounded -------------------------------------------------------------------------------

OVERRUN_SCRIPT = textwrap.dedent(
    """
    import multiprocessing
    import os
    import sys
    import time
    from pathlib import Path


    def child(path):
        Path(path).write_text(str(os.getpid()))
        time.sleep(120)


    if __name__ == "__main__":
        pids = Path(sys.argv[1])
        kid = pids.with_name("child.pid")
        process = multiprocessing.get_context("spawn").Process(target=child, args=(str(kid),))
        process.start()
        for _ in range(300):
            if kid.exists() and kid.read_text():
                break
            time.sleep(0.1)
        pids.write_text(str(os.getpid()))
        time.sleep(120)
    """
)


def test_an_overrunning_run_is_killed_with_its_children(tmp_path: Path) -> None:
    script = tmp_path / "overrun.py"
    script.write_text(OVERRUN_SCRIPT, encoding="utf-8")
    pidfile = tmp_path / "parent.pid"
    kidfile = tmp_path / "child.pid"
    log = tmp_path / "run.log"
    result: dict[str, int | None] = {}

    def call() -> None:
        result["rc"] = live_check.run_bounded(
            [sys.executable, str(script), str(pidfile)], limit_s=3, cwd=tmp_path, log=log
        )

    pids: list[int] = []
    finished = False
    started = time.monotonic()
    thread = threading.Thread(target=call, daemon=True)
    try:
        thread.start()
        thread.join(3 + 10)
        finished = not thread.is_alive()
        took = time.monotonic() - started
        for path in (pidfile, kidfile):
            if path.exists() and path.read_text().strip():
                pids.append(int(path.read_text().strip()))
        gone = [_wait_gone(pid, 5) for pid in pids]
    finally:
        for pid in pids:
            _kill_pid(pid)
        thread.join(15)
    assert finished, "run_bounded did not return within its limit + 10 s"
    assert result["rc"] is None
    assert took < 3 + 10
    assert len(pids) == 2, "the script did not get both processes going before the limit"
    assert gone == [True, True], "a process of the killed run is still alive"


def test_a_run_within_the_limit_returns_its_code(tmp_path: Path) -> None:
    script = tmp_path / "quick.py"
    script.write_text(
        "import sys\nprint('hello from the run')\nprint('and stderr', file=sys.stderr)\n"
        "sys.exit(3)\n",
        encoding="utf-8",
    )
    log = tmp_path / "quick.log"
    rc = live_check.run_bounded([sys.executable, str(script)], limit_s=60, cwd=tmp_path, log=log)
    assert rc == 3
    text = log.read_text(encoding="utf-8")
    assert "hello from the run" in text
    assert "and stderr" in text


def test_alive_is_true_for_this_process_and_false_for_a_gone_one(tmp_path: Path) -> None:
    assert live_check.alive(os.getpid())
    done = subprocess.Popen([sys.executable, "-c", "pass"])
    done.wait()
    assert _wait_gone(done.pid, 5)


# --- compare -----------------------------------------------------------------------------------


def test_compare_marks_material_differences(tmp_path: Path) -> None:
    offline = _copy(tmp_path, "offline")
    live = _copy(tmp_path, "live")
    material, info = live_check.compare(live, offline, EXPECTED, [])
    assert material == []
    assert any(line.startswith("feed: ") for line in info)

    low = _first_page(offline, "osce")
    assert low["units_seen"] > 0
    bad = _first_page(offline, "ipu")
    gone = _first_page(offline, "carter")
    high = _first_page(offline, "aweb")
    assert high["units_seen"] > 0
    zero = next(
        (s, p)
        for s in ("eisa", "wikipedia", "ndi", "eeas", "electionguide")
        for p in [_first_page(offline, s)]
        if p["units_seen"] == 0
    )
    steps: list[tuple[str, Callable[[], None]]] = [
        (
            f"osce/{low['key']}",
            lambda: _page_edit(
                live, "osce", low["key"], lambda p: p.update(units_seen=low["units_seen"] // 3)
            ),
        ),
        (
            f"aweb/{high['key']}",
            lambda: _page_edit(
                live,
                "aweb",
                high["key"],
                lambda p: p.update(units_seen=high["units_seen"] * 2 + 1),
            ),
        ),
        (
            f"ipu/{bad['key']}",
            lambda: _page_edit(live, "ipu", bad["key"], lambda p: p.update(outcome="fetch_failed")),
        ),
        (
            f"carter/{gone['key']}",
            lambda: _edit(
                _candidate(live, "carter"),
                lambda d: d["scope"]["pages"].remove(
                    next(p for p in d["scope"]["pages"] if p["key"] == gone["key"])
                ),
            ),
        ),
        (
            "source ndi",
            lambda: _edit(
                live / "status.json",
                lambda d: next(s for s in d["sources"] if s["source"] == "ndi").update(
                    severity="error"
                ),
            ),
        ),
        (
            "feed over budget",
            lambda: _edit(
                live / "verdict.json",
                lambda d: d.update(feed_bytes=d["feed_budget_bytes"] + 1),
            ),
        ),
        (
            "requests over the limit",
            lambda: _edit(live / "verdict.json", lambda d: d.update(requests=41)),
        ),
    ]
    for count, (needle, step) in enumerate(steps, start=1):
        step()
        material, _ = live_check.compare(live, offline, EXPECTED, [])
        assert len(material) == count, material
        assert sum(needle in line for line in material) == 1, (needle, material)

    # A fixture page with no units is never judged on its count.
    source, page = zero
    _page_edit(offline, source, page["key"], lambda p: p.update(units_seen=0))
    _page_edit(live, source, page["key"], lambda p: p.update(units_seen=50))
    after, _ = live_check.compare(live, offline, EXPECTED, [])
    assert after == material


def test_a_page_present_live_only_is_information(tmp_path: Path) -> None:
    offline = _copy(tmp_path, "offline")
    live = _copy(tmp_path, "live")

    def add(doc: Any) -> None:
        extra = dict(doc["scope"]["pages"][0])
        extra["key"] = "a-longer-chain-page"
        doc["scope"]["pages"].append(extra)

    _edit(_candidate(live, "ndi"), add)
    material, info = live_check.compare(live, offline, EXPECTED, [])
    assert material == []
    assert any("ndi/a-longer-chain-page" in line for line in info)


def test_compare_information_lists_severities_size_requests(tmp_path: Path) -> None:
    offline = _copy(tmp_path, "offline")
    live = _copy(tmp_path, "live")
    _, info = live_check.compare(live, offline, EXPECTED, [])
    status = json.loads((live / "status.json").read_text(encoding="utf-8"))
    for entry in status["sources"]:
        assert any(
            line.startswith(f"severity {entry['source']}: live {entry['severity']}, fixtures ")
            for line in info
        ), entry
    verdict = json.loads((live / "verdict.json").read_text(encoding="utf-8"))
    feed = (live / "elections.json").read_bytes()
    expected_feed = (
        f"feed: {verdict['feed_bytes']} bytes of {verdict['feed_budget_bytes']}, "
        f"gzip {len(gzip.compress(feed))} bytes"
    )
    assert expected_feed in info
    assert "requests: not recorded" in info
    _edit(live / "verdict.json", lambda d: d.update(requests=17))
    _, info = live_check.compare(live, offline, EXPECTED, [])
    assert "requests: 17 of 40" in info


def test_compare_never_raises_on_a_missing_or_unreadable_live_file(tmp_path: Path) -> None:
    offline = _copy(tmp_path, "offline")
    empty = tmp_path / "empty-live"
    empty.mkdir()
    material, _ = live_check.compare(empty, offline, EXPECTED, [])
    for name in ("verdict.json", "status.json", "elections.json", "candidate.json"):
        assert any(name in line for line in material), (name, material)

    live = _copy(tmp_path, "live")
    for name in ("verdict.json", "status.json", "elections.json"):
        (live / name).write_text("{ not json", encoding="utf-8")
    _candidate(live, "osce").write_bytes(b"\xff\xfe")
    material, _ = live_check.compare(live, offline, EXPECTED, [])
    for name in ("verdict.json", "status.json", "elections.json"):
        assert sum(name in line for line in material) == 1, (name, material)
    assert any("osce" in line and "candidate.json" in line for line in material)

    # Valid JSON of the wrong shape is a material line too, never an exception.
    for name in ("verdict.json", "status.json", "elections.json"):
        (live / name).write_text("[]", encoding="utf-8")
    material, _ = live_check.compare(live, offline, EXPECTED, [])
    for name in ("verdict.json", "status.json", "elections.json"):
        assert any(name in line for line in material), (name, material)


# --- the witness child -------------------------------------------------------------------------


def _brazil(feed: dict[str, Any]) -> dict[str, Any]:
    return next(
        c
        for c in feed["months"]["2026-10"]
        if c["place_id"] == "iso:BR" and c["level"] == "national" and c["date"] == "2026-10-04"
    )


def _no_presidency(feed: dict[str, Any]) -> None:
    card = _brazil(feed)
    card["children"] = [c for c in card["children"] if c["office_label"] != "Brazilian Presidency"]


def _no_card(feed: dict[str, Any]) -> None:
    feed["months"]["2026-10"].remove(_brazil(feed))


def _presidency_lost_to_another_office(feed: dict[str, Any]) -> None:
    """The Presidency child is gone, but a child of another office has round 1 on the card."""
    _no_presidency(feed)
    card = _brazil(feed)
    other = copy.deepcopy(next(c for c in card["children"] if "Chamber" in c["office_label"]))
    other["round"] = 1
    card["children"].append(other)


def _round_two(feed: dict[str, Any]) -> None:
    child = next(c for c in _brazil(feed)["children"] if c["office_label"] == "Brazilian Presidency")
    child["round"] = 2


def _move(old_dates: list[str], to: str = "2026-10-11") -> Callable[[dict[str, Any]], None]:
    def edit(feed: dict[str, Any]) -> None:
        card = _brazil(feed)
        child = next(c for c in card["children"] if c["office_label"] == "Brazilian Presidency")
        card["children"].remove(child)
        child["rescheduled_from"] = old_dates
        feed["months"][to[:7]].append({**card, "date": to, "end_date": to, "children": [child]})

    return edit


def _nothing(feed: dict[str, Any]) -> None:
    del feed


PRESIDENCY = "iso:BR Presidency round 1 2026-10-04"


def _possible(old: str, to: str = "2026-10-11") -> str:
    return (
        f"possible reschedule, review required: {PRESIDENCY} -> {to} (rescheduled_from: {old})"
    )


def _two_expectations(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    one = next(
        e
        for e in entries
        if e["place"] == "iso:BR" and e["office"] == "Presidency" and e["round"] == 1
    )
    # The wrong-date entry comes first: rows are used in order, so only the `from` match
    # keeps it from taking the row meant for the 2026-10-04 entry.
    return [{**one, "date": "2026-11-08"}, one]


def _range_entry(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    del entries
    return [
        {
            "place": "iso:ZZ",
            "office": "Parliament",
            "round": None,
            "date": "2026-08-25 to 2026-09-05",
            "level": "national",
        }
    ]


def _reviewed_info(old: str) -> str:
    return (
        "rescheduled from 2026-10-04 to 2026-10-11 (reviewed): iso:BR Presidency; "
        f"the sources wrote {old}"
    )


@pytest.mark.parametrize(
    ("edit", "entries", "reviewed", "material", "info"),
    [
        pytest.param(_nothing, None, [], [], [], id="unedited"),
        pytest.param(
            _no_presidency,
            None,
            [],
            [f"expected and not found: {PRESIDENCY}"],
            [],
            id="presidency child removed",
        ),
        pytest.param(
            _no_card,
            None,
            [],
            [
                f"expected and not found: {PRESIDENCY}",
                "expected and not found: iso:BR Brazilian Chamber of Deputies 2026-10-04",
                "expected and not found: iso:BR Brazilian Federal Senate 2026-10-04",
            ],
            [],
            id="whole card removed",
        ),
        pytest.param(
            _presidency_lost_to_another_office,
            None,
            [],
            [f"expected and not found: {PRESIDENCY}"],
            [],
            id="other office, same round",
        ),
        pytest.param(
            _round_two,
            None,
            [],
            [f"expected and not found: {PRESIDENCY}"],
            [],
            id="round changed",
        ),
        pytest.param(
            _move(["4 October 2026"]),
            None,
            REVIEWED,
            [],
            [_reviewed_info("4 October 2026")],
            id="moved with a reviewed row",
        ),
        *[
            pytest.param(
                _move(["4 October 2026"]),
                None,
                [{**REVIEWED[0], **change}],
                [_possible("4 October 2026")],
                [],
                id=f"moved, a reviewed row with the wrong {name}",
            )
            for name, change in (
                ("to", {"to": "2026-10-20"}),
                ("round", {"round": 2}),
                ("jurisdiction", {"jurisdiction": "X"}),
                ("office", {"office": "Senate"}),
                ("place", {"place": "iso:AR"}),
            )
        ],
        pytest.param(
            _move(["4 October 2026"]),
            None,
            [],
            [_possible("4 October 2026")],
            [],
            id="moved without a row",
        ),
        pytest.param(
            _move(["1 September 2026"]),
            None,
            [],
            [_possible("1 September 2026")],
            [],
            id="moved, unrelated old date",
        ),
        pytest.param(
            _move(["???"]), None, [], [_possible("???")], [], id="moved, unreadable old date"
        ),
        pytest.param(
            _move([]),
            None,
            [],
            [f"expected and not found: {PRESIDENCY}"],
            [],
            id="moved, no old date, no row",
        ),
        pytest.param(
            _move([]),
            None,
            REVIEWED,
            [],
            [_reviewed_info("no old date")],
            id="moved, no old date, reviewed",
        ),
        pytest.param(
            _move(["4 October 2026"], to="2026-11-29"),
            _two_expectations,
            [{**REVIEWED[0], "to": "2026-11-29"}],
            [
                "possible reschedule, review required: iso:BR Presidency round 1 2026-11-08 "
                "-> 2026-11-29 (rescheduled_from: 4 October 2026)"
            ],
            [
                "rescheduled from 2026-10-04 to 2026-11-29 (reviewed): iso:BR Presidency; "
                "the sources wrote 4 October 2026"
            ],
            id="two expectations, one link",
        ),
        pytest.param(
            _nothing,
            _range_entry,
            [],
            ["expected and not found: iso:ZZ Parliament 2026-08-25 to 2026-09-05"],
            [],
            id="range overlapping the window",
        ),
    ],
)
def test_compare_needs_a_witness_child(
    tmp_path: Path,
    edit: Callable[[dict[str, Any]], None],
    entries: Callable[[list[dict[str, Any]]], list[dict[str, Any]]] | None,
    reviewed: Sequence[Mapping[str, Any]],
    material: list[str],
    info: list[str],
) -> None:
    offline = _copy(tmp_path, "offline")
    live = _copy(tmp_path, "live")
    _edit(live / "elections.json", edit)
    expected = EXPECTED
    if entries is not None:
        real = yaml.safe_load(EXPECTED.read_text(encoding="utf-8"))
        expected = tmp_path / "expected.yaml"
        expected.write_text(yaml.safe_dump(entries(real)), encoding="utf-8")
    got_material, got_info = live_check.compare(live, offline, expected, reviewed)
    assert got_material == material
    assert [line for line in got_info if line.startswith("rescheduled from")] == info


@pytest.mark.parametrize(
    ("n", "live_n", "flagged"),
    [
        (10, 5, False),  # exactly half
        (10, 4, True),
        (10, 20, False),  # exactly double
        (10, 21, True),
        (11, 6, False),  # half of 11 is 5.5
        (11, 5, True),
        (11, 22, False),
        (11, 23, True),
    ],
)
def test_the_units_seen_boundaries(tmp_path: Path, n: int, live_n: int, flagged: bool) -> None:
    offline = _copy(tmp_path, "offline")
    live = _copy(tmp_path, "live")
    key = _first_page(offline, "osce")["key"]
    _page_edit(offline, "osce", key, lambda p: p.update(units_seen=n))
    _page_edit(live, "osce", key, lambda p: p.update(units_seen=live_n))
    material, _ = live_check.compare(live, offline, EXPECTED, [])
    assert len(material) == int(flagged), material
    if flagged:
        assert f"osce/{key}" in material[0]


def _presidency_entry() -> dict[str, Any]:
    entries = yaml.safe_load(EXPECTED.read_text(encoding="utf-8"))
    entry: dict[str, Any] = next(
        e
        for e in entries
        if e["place"] == "iso:BR" and e["office"] == "Presidency" and e["round"] == 1
    )
    return entry


def test_a_reviewed_row_links_one_entry(tmp_path: Path) -> None:
    offline = _copy(tmp_path, "offline")
    live = _copy(tmp_path, "live")
    _edit(live / "elections.json", _move(["4 October 2026"]))
    expected = tmp_path / "expected.yaml"
    one = _presidency_entry()
    expected.write_text(yaml.safe_dump([one, dict(one)]), encoding="utf-8")
    material, info = live_check.compare(live, offline, expected, REVIEWED)
    assert [line for line in info if line.startswith("rescheduled from")] == [
        _reviewed_info("4 October 2026")
    ]
    assert material == [_possible("4 October 2026")]


def test_a_reversed_expected_date_is_a_material_line_and_does_not_skip_the_rest(
    tmp_path: Path,
) -> None:
    offline = _copy(tmp_path, "offline")
    live = _copy(tmp_path, "live")
    base = {"office": "Parliament", "round": None, "level": "national"}
    entries = [
        {**base, "place": "iso:ZZ", "date": "2026-10-20 to 2026-10-11"},
        {**base, "place": "iso:ZY", "date": "2026-10-05"},
    ]
    expected = tmp_path / "expected.yaml"
    expected.write_text(yaml.safe_dump(entries), encoding="utf-8")
    material, _ = live_check.compare(live, offline, expected, [])
    assert material == [
        "cannot read expected entry iso:ZZ Parliament: "
        "'2026-10-20 to 2026-10-11' runs backwards",
        "expected and not found: iso:ZY Parliament 2026-10-05",
    ]


def test_load_reviewed_reports_mixed_type_keys_as_a_value_error(tmp_path: Path) -> None:
    path = tmp_path / "reviewed.yaml"
    path.write_text(
        "- place: 'iso:BR'\n  office: Presidency\n  round: 1\n  from: '2026-10-04'\n"
        "  to: '2026-10-11'\n  note: t\n  1: a\n  x: b\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"^reviewed_reschedules\.yaml row 1: unexpected key"):
        live_check.load_reviewed(path)


def test_an_unlistable_sources_folder_is_a_material_line(tmp_path: Path) -> None:
    offline = _copy(tmp_path, "offline")
    live = _copy(tmp_path, "live")
    shutil.rmtree(offline / "data" / "sources")
    material, _ = live_check.compare(live, offline, EXPECTED, [])
    assert any("cannot list offline data/sources" in line for line in material), material
    offline = _copy(tmp_path, "offline2")
    shutil.rmtree(live / "data" / "sources")
    material, _ = live_check.compare(live, offline, EXPECTED, [])
    assert any("cannot list live data/sources" in line for line in material), material


def test_the_witness_is_a_child_of_the_same_jurisdiction(tmp_path: Path) -> None:
    offline = _copy(tmp_path, "offline")
    live = _copy(tmp_path, "live")
    entry = {
        "place": "iso:BR",
        "office": "Presidency",
        "jurisdiction": "Sao Paulo",
        "round": 1,
        "date": "2026-10-04",
        "level": "national",
    }
    expected = tmp_path / "expected.yaml"
    expected.write_text(yaml.safe_dump([entry]), encoding="utf-8")
    material, _ = live_check.compare(live, offline, expected, [])
    assert material == [
        "expected and not found: iso:BR Presidency round 1 2026-10-04"
    ]


# --- the reviewed file -------------------------------------------------------------------------


def test_the_committed_reviewed_file_is_empty() -> None:
    assert live_check.load_reviewed(REVIEWED_FILE) == []


def test_load_reviewed_reads_good_rows(tmp_path: Path) -> None:
    path = tmp_path / "reviewed.yaml"
    rows = [
        dict(REVIEWED[0]),
        {**REVIEWED[0], "jurisdiction": "Sao Paulo", "round": None, "to": "2026-10 to 2026-11"},
    ]
    path.write_text(yaml.safe_dump(rows), encoding="utf-8")
    assert live_check.load_reviewed(path) == rows


@pytest.mark.parametrize(
    ("change", "fragment"),
    [
        pytest.param(lambda r: r.pop("note"), "note", id="no note"),
        pytest.param(lambda r: r.update(note="  "), "note", id="blank note"),
        pytest.param(lambda r: r.update(extra="x"), "extra", id="extra key"),
        pytest.param(lambda r: r.update(round="1"), "round", id="round as text"),
        pytest.param(lambda r: r.update({"from": "4 October"}), "from", id="bad from"),
        pytest.param(lambda r: r.update(to="2026-13-01"), "to", id="bad to"),
        pytest.param(lambda r: r.update(place=""), "place", id="empty place"),
        pytest.param(lambda r: r.update(jurisdiction=""), "jurisdiction", id="empty jurisdiction"),
        pytest.param(
            lambda r: r.update(to="2026-10-20 to 2026-10-11"), "backwards", id="reversed to"
        ),
        pytest.param(
            lambda r: r.update({"from": "2026-10-20 to 2026-10-11"}), "backwards", id="reversed from"
        ),
    ],
)
def test_load_reviewed_rejects_a_bad_row(
    tmp_path: Path, change: Callable[[dict[str, Any]], object], fragment: str
) -> None:
    bad = dict(REVIEWED[0])
    change(bad)
    path = tmp_path / "reviewed.yaml"
    path.write_text(yaml.safe_dump([dict(REVIEWED[0]), bad]), encoding="utf-8")
    with pytest.raises(ValueError, match=rf"^reviewed_reschedules\.yaml row 2: .*{fragment}"):
        live_check.load_reviewed(path)


@pytest.mark.parametrize("text", ["", "# only a comment\n", "{}\n", "{a: 1}\n", "- 3\n", ": : :\n"])
def test_load_reviewed_never_reads_a_bad_file_as_empty(tmp_path: Path, text: str) -> None:
    path = tmp_path / "reviewed.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed_reschedules"):
        live_check.load_reviewed(path)
    with pytest.raises(ValueError, match="reviewed_reschedules"):
        live_check.load_reviewed(tmp_path / "missing.yaml")


# --- main --------------------------------------------------------------------------------------


class Fake:
    """Replaces run_bounded: the offline run writes the fixture artifact, the live run copies it."""

    def __init__(self, tmp_path: Path, *, offline: int | None = 0, live: int | None = 0) -> None:
        self.tmp_path = tmp_path
        self.offline = offline
        self.live = live
        self.calls: list[tuple[list[str], float, Path, Path]] = []

    def __call__(self, cmd: Sequence[str], *, limit_s: float, cwd: Path, log: Path) -> int | None:
        cmd = list(cmd)
        self.calls.append((cmd, limit_s, cwd, log))
        out = Path(cmd[cmd.index("--out") + 1])
        is_offline = "elections_calendar" in cmd
        log.write_text(f"fake {'offline' if is_offline else 'live'} run output\n", encoding="utf-8")
        code = self.offline if is_offline else self.live
        if code == 0:
            if is_offline:
                fixture_artifact(out, code_sha=SHA)
            else:
                shutil.copytree(out.parent / "offline", out)
        return code


def _stamp_dir(out: Path) -> Path:
    (folder,) = [p for p in out.iterdir() if p.is_dir()]
    return folder


def test_live_check_main_with_a_fake_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = Fake(tmp_path)
    monkeypatch.setattr(live_check, "run_bounded", fake)
    out = tmp_path / "out"
    assert live_check.main(["--out", str(out)]) == 0
    folder = _stamp_dir(out)
    assert len(folder.name) == 16 and folder.name.endswith("Z") and folder.name[8] == "T"
    report = (folder / "live_check.md").read_text(encoding="utf-8")
    assert report.startswith(f"# Live check {folder.name}\n")
    assert "Material differences: 0" in report
    assert "Information" in report
    assert "fake live run output" in report
    assert str(live_check.LIMIT_S) in report
    assert str(capsys.readouterr().out).strip() != ""

    (offline_cmd, offline_limit, offline_cwd, offline_log), (
        live_cmd,
        live_limit,
        live_cwd,
        live_log,
    ) = fake.calls
    assert offline_cmd[:3] == [sys.executable, "-m", "elections_calendar"]
    assert offline_cmd[offline_cmd.index("--offline") + 1] == "tests/fixtures"
    assert offline_cmd[offline_cmd.index("--now") + 1] == "2026-10-19T12:00:00Z"
    assert offline_limit == live_check.OFFLINE_LIMIT_S == 120
    assert offline_log == folder / "offline.log"
    assert live_cmd[:2] == [sys.executable, "scraper.py"]
    assert live_cmd[2:4] == ["--live", "--dry-run"]
    assert live_limit == live_check.LIMIT_S == 600
    assert live_log == folder / "live.log"
    assert offline_cwd == live_cwd == ROOT
    assert Path(offline_cmd[offline_cmd.index("--out") + 1]) == folder / "offline"
    assert Path(live_cmd[live_cmd.index("--out") + 1]) == folder / "live"
    repos = [Path(c[c.index("--repo") + 1]) for c in (offline_cmd, live_cmd)]
    assert repos[0] != repos[1]
    for repo in repos:
        assert repo.parent == folder
        assert repo.is_dir() and list(repo.iterdir()) == []

    # A live run killed at the limit still writes its report, and exits 1.
    monkeypatch.setattr(live_check, "run_bounded", Fake(tmp_path, live=None))
    killed = tmp_path / "killed"
    assert live_check.main(["--out", str(killed)]) == 1
    text = (_stamp_dir(killed) / "live_check.md").read_text(encoding="utf-8")
    assert "killed" in text


def test_a_killed_or_failed_live_run_exits_1_with_a_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, code, text in (("killed", None, "killed"), ("failed", 4, "exited with code 4")):
        fake = Fake(tmp_path, live=code)
        monkeypatch.setattr(live_check, "run_bounded", fake)
        out = tmp_path / name
        assert live_check.main(["--out", str(out)]) == 1
        report = (_stamp_dir(out) / "live_check.md").read_text(encoding="utf-8")
        assert text in report
        assert "Material differences: 0" not in report
        assert "fake live run output" in report


def test_a_bad_offline_run_stops_before_the_live_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name, code, text in (("killed", None, "killed"), ("failed", 3, "exited with code 3")):
        fake = Fake(tmp_path, offline=code)
        monkeypatch.setattr(live_check, "run_bounded", fake)
        out = tmp_path / name
        assert live_check.main(["--out", str(out)]) == 1
        assert len(fake.calls) == 1
        report = (_stamp_dir(out) / "live_check.md").read_text(encoding="utf-8")
        assert "offline run" in report and text in report
        assert "live run was not started" in report
        assert "fake offline run output" in report


def test_a_bad_reviewed_file_exits_2_before_anything_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def explode(*args: object, **kwargs: object) -> int:
        raise AssertionError("run_bounded was called")

    monkeypatch.setattr(live_check, "run_bounded", explode)
    bad = dict(REVIEWED[0])
    del bad["note"]
    path = tmp_path / "reviewed.yaml"
    path.write_text(yaml.safe_dump([bad]), encoding="utf-8")
    out = tmp_path / "out"
    assert live_check.main(["--out", str(out), "--reviewed", str(path)]) == 2
    assert "reviewed_reschedules.yaml row 1:" in capsys.readouterr().err
    assert not out.exists()


def test_a_reviewed_row_reaches_the_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Moving(Fake):
        def __call__(
            self, cmd: Sequence[str], *, limit_s: float, cwd: Path, log: Path
        ) -> int | None:
            code = super().__call__(cmd, limit_s=limit_s, cwd=cwd, log=log)
            if "scraper.py" in cmd:
                out = Path(cmd[cmd.index("--out") + 1])
                _edit(out / "elections.json", _move(["4 October 2026"]))
            return code

    monkeypatch.setattr(live_check, "run_bounded", Moving(tmp_path))
    path = tmp_path / "reviewed.yaml"
    path.write_text(yaml.safe_dump(REVIEWED), encoding="utf-8")
    out = tmp_path / "out"
    assert live_check.main(["--out", str(out), "--reviewed", str(path)]) == 0
    report = (_stamp_dir(out) / "live_check.md").read_text(encoding="utf-8")
    assert "Material differences: 0" in report
    assert _reviewed_info("4 October 2026") in report


def test_two_runs_in_one_second_exit_1_with_a_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    frozen = datetime(2026, 10, 24, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(live_check, "datetime", types.SimpleNamespace(now=lambda tz=None: frozen))
    fake = Fake(tmp_path)
    monkeypatch.setattr(live_check, "run_bounded", fake)
    out = tmp_path / "out"
    assert live_check.main(["--out", str(out)]) == 0
    capsys.readouterr()
    calls = len(fake.calls)
    assert live_check.main(["--out", str(out)]) == 1
    assert "already exists (two runs in one second); run again" in capsys.readouterr().err
    assert len(fake.calls) == calls
    assert (_stamp_dir(out) / "live_check.md").is_file()


def test_a_relative_out_reaches_the_children_as_an_absolute_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = Fake(tmp_path)
    monkeypatch.setattr(live_check, "run_bounded", fake)
    monkeypatch.chdir(tmp_path)
    assert live_check.main(["--out", "rel-out"]) == 0
    for cmd, *_ in fake.calls:
        assert Path(cmd[cmd.index("--out") + 1]).is_absolute()
        assert Path(cmd[cmd.index("--repo") + 1]).is_absolute()


def test_a_failing_kill_tree_still_ends_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "sleeper.py"
    script.write_text(
        "import os, sys, time\nopen(sys.argv[1], 'w').write(str(os.getpid()))\ntime.sleep(120)\n",
        encoding="utf-8",
    )
    pidfile = tmp_path / "sleeper.pid"
    seen: list[subprocess.Popen[bytes]] = []

    def broken(process: subprocess.Popen[bytes]) -> None:
        seen.append(process)
        raise OSError("taskkill refused")

    monkeypatch.setattr(live_check, "kill_tree", broken)
    monkeypatch.setattr(live_check, "REAP_S", 2)
    try:
        with pytest.raises(RuntimeError, match="kill_tree failed"):
            live_check.run_bounded(
                [sys.executable, str(script), str(pidfile)],
                limit_s=2,
                cwd=tmp_path,
                log=tmp_path / "sleeper.log",
            )
        assert seen[0].poll() is not None
    finally:  # the venv launcher's child outlives the launcher itself
        if pidfile.exists() and pidfile.read_text().strip():
            _kill_pid(int(pidfile.read_text().strip()))
        for process in seen:
            process.kill()
            process.wait(10)


def test_a_child_that_survives_the_kill_is_reported_not_waited_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Stubborn:
        pid = 1

        def kill(self) -> None:
            pass

        def wait(self, timeout: float | None = None) -> int:
            assert timeout is not None, "waited without a limit"
            raise subprocess.TimeoutExpired("stubborn", timeout)

    monkeypatch.setattr(live_check, "kill_tree", lambda process: None)
    with pytest.raises(RuntimeError, match="still alive"):
        live_check._stop(Stubborn())  # type: ignore[arg-type]


@pytest.mark.parametrize("side", ["offline", "live"])
@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("kill_tree failed (x); process 1 was killed, but its children may remain"),
        OSError("no such file"),
    ],
    ids=["RuntimeError", "OSError"],
)
def test_a_run_that_raises_still_writes_the_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, side: str, error: Exception
) -> None:
    class Raising(Fake):
        def __call__(
            self, cmd: Sequence[str], *, limit_s: float, cwd: Path, log: Path
        ) -> int | None:
            if ("elections_calendar" in cmd) == (side == "offline"):
                self.calls.append((list(cmd), limit_s, cwd, log))
                raise error
            return super().__call__(cmd, limit_s=limit_s, cwd=cwd, log=log)

    fake = Raising(tmp_path)
    monkeypatch.setattr(live_check, "run_bounded", fake)
    out = tmp_path / "out"
    assert live_check.main(["--out", str(out)]) == 1
    text = (_stamp_dir(out) / "live_check.md").read_text(encoding="utf-8")
    line = f"the {side} run failed: {type(error).__name__}: {error}"
    if side == "offline":
        assert f"{line}; the live run was not started" in text
        assert not any("scraper.py" in cmd for cmd, *_ in fake.calls)
    else:
        assert f"- {line}\n" in text
        assert "Information" in text
        assert "elapsed:" in text


def test_dry_run_fits_the_live_check_limit() -> None:
    assert pipeline.DRY_RUN_SCRAPE_DEADLINE_S + 5 + 2 + 60 <= live_check.LIMIT_S


# --- the final fix wave (final review F4; Task 9 minors m1, m2, m4) ---------------------------


@pytest.mark.parametrize("key", ["from", "to"])
@pytest.mark.parametrize("value", ["9999-12-31", "2026-10-01 to 9999-12-31"])
def test_a_reviewed_row_ending_on_9999_12_31_is_a_row_error(
    tmp_path: Path, key: str, value: str
) -> None:
    row = {**REVIEWED[0], key: value}
    path = tmp_path / "reviewed.yaml"
    path.write_text(yaml.safe_dump([row]), encoding="utf-8")
    with pytest.raises(ValueError, match=rf"^reviewed_reschedules\.yaml row 1: {key}: "):
        live_check.load_reviewed(path)


def test_main_exits_2_for_a_reviewed_row_ending_on_9999_12_31(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(live_check, "run_bounded", Fake(tmp_path))
    path = tmp_path / "reviewed.yaml"
    path.write_text(yaml.safe_dump([{**REVIEWED[0], "to": "9999-12-31"}]), encoding="utf-8")
    assert live_check.main(["--out", str(tmp_path / "out"), "--reviewed", str(path)]) == 2
    assert "reviewed_reschedules.yaml row 1: to: " in capsys.readouterr().err


def test_a_live_card_ending_on_9999_12_31_is_a_material_line_and_the_report_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def far_end(feed: dict[str, Any]) -> None:
        card = next(c for m in feed["months"].values() for c in m if c["date_precision"] == "day")
        card["end_date"] = "9999-12-31"

    class Far(Fake):
        def __call__(
            self, cmd: Sequence[str], *, limit_s: float, cwd: Path, log: Path
        ) -> int | None:
            code = super().__call__(cmd, limit_s=limit_s, cwd=cwd, log=log)
            if "scraper.py" in cmd:
                _edit(Path(cmd[cmd.index("--out") + 1]) / "elections.json", far_end)
            return code

    monkeypatch.setattr(live_check, "run_bounded", Far(tmp_path))
    out = tmp_path / "out"
    assert live_check.main(["--out", str(out)]) == 0
    report = (_stamp_dir(out) / "live_check.md").read_text(encoding="utf-8")
    assert "cannot use live elections.json against the expected file" in report
    assert "9999-12-31" in report


@pytest.mark.parametrize(
    ("bad", "said"),
    [
        ({"place": "iso:ZZ", "office": "Parliament", "round": None, "level": "national"}, "'date'"),
        ({"place": "iso:ZZ", "office": "Parliament", "round": None, "date": "2026-10-05"}, "'level'"),
        ({"office": "Parliament", "round": None, "level": "national", "date": "2026-10-05"}, "'place'"),
        ({"place": "iso:ZZ", "round": None, "level": "national", "date": "2026-10-05"}, "'office'"),
        ({"place": "iso:ZZ", "office": "Parliament", "level": "national", "date": "2026-10-05"}, "'round'"),
        ("not an entry", "is not a mapping"),
    ],
    ids=["no date", "no level", "no place", "no office", "no round", "not a mapping"],
)
def test_a_malformed_expected_entry_is_a_material_line_and_does_not_skip_the_rest(
    tmp_path: Path, bad: Any, said: str
) -> None:
    offline = _copy(tmp_path, "offline")
    live = _copy(tmp_path, "live")
    good = {
        "place": "iso:ZY",
        "office": "Parliament",
        "round": None,
        "level": "national",
        "date": "2026-10-05",
    }
    expected = tmp_path / "expected.yaml"
    expected.write_text(yaml.safe_dump([bad, good]), encoding="utf-8")
    material, _ = live_check.compare(live, offline, expected, [])
    assert len(material) == 2, material
    assert material[0].startswith("cannot read expected entry ") and said in material[0]
    assert material[1] == "expected and not found: iso:ZY Parliament 2026-10-05"


def test_an_unreadable_report_parent_is_a_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = Fake(tmp_path)
    monkeypatch.setattr(live_check, "run_bounded", fake)
    out = (tmp_path / "out").resolve()
    stamp_dir = out / "20261024T120000Z"
    real = Path.exists

    def refusing(self: Path, *args: Any, **kwargs: Any) -> bool:
        if self == out:
            raise PermissionError("denied")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "exists", refusing)
    problem = live_check._make_folders(out, stamp_dir)
    assert problem is not None and problem.startswith("cannot check ")
    assert problem.endswith("denied")
    assert live_check.main(["--out", str(out)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("cannot check ") and err.rstrip().endswith("denied")
    assert fake.calls == []


def test_an_out_that_is_a_file_is_not_a_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = Fake(tmp_path)
    monkeypatch.setattr(live_check, "run_bounded", fake)
    afile = tmp_path / "afile"
    afile.write_text("x", encoding="utf-8")
    for out in (afile, afile / "below"):
        assert live_check.main(["--out", str(out)]) == 1
        err = capsys.readouterr().err
        assert f"{afile.resolve()} is not a directory" in err
        assert "two runs" not in err
    assert fake.calls == []


@pytest.mark.parametrize("name", ["20261024T120000Z", "repo-offline", "repo-live"])
def test_another_mkdir_failure_is_a_message_not_a_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    name: str,
) -> None:
    frozen = datetime(2026, 10, 24, 12, 0, 0, tzinfo=UTC)
    monkeypatch.setattr(live_check, "datetime", types.SimpleNamespace(now=lambda tz=None: frozen))
    fake = Fake(tmp_path)
    monkeypatch.setattr(live_check, "run_bounded", fake)
    real = Path.mkdir

    def refusing(self: Path, *args: Any, **kwargs: Any) -> None:
        if self.name == name:
            raise PermissionError("read-only disk")
        real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", refusing)
    assert live_check.main(["--out", str(tmp_path / "out")]) == 1
    err = capsys.readouterr().err
    assert "cannot create " in err and name in err and "read-only disk" in err
    assert fake.calls == []


class _Gone:
    pid = 4242


def _taskkill(monkeypatch: pytest.MonkeyPatch, outcome: int | BaseException) -> list[Any]:
    calls: list[Any] = []

    def run(cmd: Sequence[str], **kwargs: Any) -> Any:
        calls.append((list(cmd), kwargs))
        if isinstance(outcome, BaseException):
            raise outcome
        return types.SimpleNamespace(returncode=outcome)

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "run", run)
    return calls


@pytest.mark.parametrize("code", [0, 128])
def test_taskkill_success_or_not_found_is_not_a_failure(
    monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    calls = _taskkill(monkeypatch, code)
    live_check.kill_tree(_Gone())  # type: ignore[arg-type]
    (cmd, kwargs), = calls
    assert cmd == ["taskkill", "/T", "/F", "/PID", "4242"]
    assert kwargs["timeout"] == live_check.REAP_S


def test_a_failing_taskkill_is_a_kill_tree_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _taskkill(monkeypatch, 1)
    with pytest.raises(RuntimeError, match="taskkill exited with code 1"):
        live_check.kill_tree(_Gone())  # type: ignore[arg-type]


def test_a_hung_taskkill_is_a_kill_tree_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _taskkill(monkeypatch, subprocess.TimeoutExpired("taskkill", 30))
    with pytest.raises(RuntimeError, match="taskkill ran over"):
        live_check.kill_tree(_Gone())  # type: ignore[arg-type]


def test_stop_reports_a_failing_taskkill(monkeypatch: pytest.MonkeyPatch) -> None:
    _taskkill(monkeypatch, 5)

    class Dead:
        pid = 4242

        def kill(self) -> None:
            pass

        def wait(self, timeout: float | None = None) -> int:
            return 0

    with pytest.raises(RuntimeError, match="kill_tree failed .*taskkill exited with code 5"):
        live_check._stop(Dead())  # type: ignore[arg-type]


def test_posix_kill_tree_treats_a_missing_group_as_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    def killpg(pid: int, sig: int) -> None:
        raise ProcessLookupError

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(os, "killpg", killpg, raising=False)
    monkeypatch.setattr(signal, "SIGKILL", 9, raising=False)
    live_check.kill_tree(_Gone())  # type: ignore[arg-type]

    def refused(pid: int, sig: int) -> None:
        raise PermissionError("no")

    monkeypatch.setattr(os, "killpg", refused, raising=False)
    with pytest.raises(PermissionError):
        live_check.kill_tree(_Gone())  # type: ignore[arg-type]
