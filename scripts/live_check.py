"""The bounded live check: one dry run on the real sources, compared with the fixtures.

Run from the repository root as ``python -m scripts.live_check --out DIR`` (spec 13.5; Plan 5a
P116 and P125). It makes at most 40 read-only requests and is killed, with every process it
started, after ``LIMIT_S`` seconds. It is a report for the user, not a gate: it exits 0 when the
report is written and the live run exited 0, whatever the report says.
"""

import argparse
import contextlib
import ctypes
import gzip
import json
import os
import re
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Final

import yaml

from elections_calendar.pipeline import DRY_RUN_REQUESTS, DRY_RUN_SCRAPE_DEADLINE_S
from elections_calendar.publish import FEED_BUDGET_BYTES
from elections_calendar.text import fold

ROOT: Final = Path(__file__).resolve().parents[1]
LIMIT_S: Final = 600  # the live run's hard limit (spec 13.5)
REAP_S: Final = 30  # how long a killed run may take to disappear
OFFLINE_LIMIT_S: Final = 120  # the offline fixture run takes about 4 s
OFFLINE_NOW: Final = "2026-10-19T12:00:00Z"
DEFAULT_REVIEWED: Final = ROOT / "tests" / "expected" / "reviewed_reschedules.yaml"
EXPECTED: Final = ROOT / "tests" / "expected" / "2026-10-16.yaml"
GOOD_OUTCOMES: Final = ("ok", "valid_empty")
LOG_TAIL_LINES: Final = 40
_REVIEWED_NAME: Final = "reviewed_reschedules.yaml"
_REVIEWED_KEYS: Final = frozenset({"place", "office", "round", "from", "to", "note"})
_TASKKILL_NOT_FOUND: Final = 128  # the process is already gone
_DATE_PART: Final = re.compile(r"[0-9]{4}-[0-9]{2}(-[0-9]{2})?")
_DAY: Final = timedelta(days=1)
_Span = tuple[date, date]  # first day, and the day after the last


# --- processes ---------------------------------------------------------------------------------


def kill_tree(process: subprocess.Popen[bytes]) -> None:
    """Kill ``process`` and everything it started; raises when that could not be done.

    On Windows ``taskkill`` gets ``REAP_S`` seconds. Exit 128 ("not found") means the tree is
    already gone; any other non-zero exit, or a timeout, raises ``RuntimeError``.
    """
    if sys.platform == "win32":
        try:
            done = subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
                timeout=REAP_S,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"taskkill ran over {REAP_S} s") from None
        if done.returncode not in (0, _TASKKILL_NOT_FOUND):
            raise RuntimeError(f"taskkill exited with code {done.returncode}")
    else:
        with contextlib.suppress(ProcessLookupError):  # start_new_session: the pgid is the pid
            os.killpg(process.pid, signal.SIGKILL)


def run_bounded(cmd: Sequence[str], *, limit_s: float, cwd: Path, log: Path) -> int | None:
    """Run ``cmd`` in its own process group, output to ``log``; None when killed at the limit.

    Raises ``RuntimeError`` when the kill failed (``kill_tree`` raised, so the child's own
    children may remain) or the child outlived it by ``REAP_S`` seconds; the child itself has
    been killed in the first case. An interrupt kills the run too, and propagates.
    """
    with log.open("wb") as sink:
        if sys.platform == "win32":
            process = subprocess.Popen(
                list(cmd),
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=sink,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            process = subprocess.Popen(
                list(cmd),
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=sink,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        try:
            return process.wait(timeout=limit_s)
        except subprocess.TimeoutExpired:
            _stop(process)
            return None
        except BaseException:  # an interrupt must not leave the run behind either
            with contextlib.suppress(RuntimeError):
                _stop(process)
            raise


def _stop(process: subprocess.Popen[bytes]) -> None:
    """Kill the tree; when that fails, kill the child itself. Never waits more than REAP_S.

    Raises RuntimeError when ``kill_tree`` failed (the child's own children may remain) or the
    child is still alive REAP_S seconds after the kill.
    """
    problem: Exception | None = None
    try:
        kill_tree(process)
    except Exception as exc:
        problem = exc
    process.kill()
    try:
        process.wait(timeout=REAP_S)
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"process {process.pid} is still alive {REAP_S} s after the kill"
        ) from problem
    if problem is not None:
        raise RuntimeError(
            f"kill_tree failed ({problem}); process {process.pid} was killed, "
            "but its children may remain"
        ) from problem


def alive(pid: int) -> bool:
    """Whether process ``pid`` is still running (never signals it)."""
    if sys.platform == "win32":
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel32.OpenProcess.restype = ctypes.c_void_p
        kernel32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        kernel32.GetExitCodeProcess.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel32.OpenProcess(0x1000, 0, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.get_last_error() == 5  # access denied: it exists
        try:
            code = ctypes.c_uint32()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    else:
        return _posix_alive(pid)


def _posix_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:  # Linux: a killed process waiting to be reaped is gone
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return True
    return stat.rpartition(")")[2].split()[:1] != ["Z"]


# --- dates -------------------------------------------------------------------------------------


def _next_day(day: date) -> date:
    try:
        return day + _DAY
    except OverflowError:  # 9999-12-31 has no next day
        raise ValueError(f"{day} is the last day this check can read") from None


def _span(text: str) -> _Span:
    """YYYY-MM-DD is a day, YYYY-MM a month, ``A to B`` runs from A through B."""
    if " to " in text:
        first, last = text.split(" to ")
        start, end = _span(first)[0], _span(last)[1]
        if end <= start:
            raise ValueError(f"{text!r} runs backwards")
        return start, end
    if not _DATE_PART.fullmatch(text):
        raise ValueError(f"{text!r} is not YYYY-MM-DD, YYYY-MM or YYYY-MM-DD to YYYY-MM-DD")
    if len(text) == 7:
        start = date.fromisoformat(f"{text}-01")
        return start, date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    day = date.fromisoformat(text)
    return day, _next_day(day)


def _overlaps(a: _Span, b: _Span) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def _card_span(card: Mapping[str, Any]) -> _Span:
    if card["date_precision"] == "month":
        return _span(str(card["date"])[:7])
    start = date.fromisoformat(card["date"])
    return start, _next_day(date.fromisoformat(card.get("end_date") or card["date"]))


# --- the reviewed reschedules ------------------------------------------------------------------


def _row_problem(row: Any) -> str | None:
    if not isinstance(row, dict):
        return "is not a mapping"
    keys = set(row)
    if missing := sorted(_REVIEWED_KEYS - keys):
        return f"missing key {missing[0]}"
    if extra := sorted(map(str, keys - _REVIEWED_KEYS - {"jurisdiction"})):
        return f"unexpected key {extra[0]}"
    for name in ("place", "office", "note"):
        if not isinstance(row[name], str) or not row[name].strip():
            return f"{name} must be non-empty text"
    if "jurisdiction" in row and (
        not isinstance(row["jurisdiction"], str) or not row["jurisdiction"].strip()
    ):
        return "jurisdiction must be non-empty text when present"
    if row["round"] is not None and (
        isinstance(row["round"], bool) or not isinstance(row["round"], int)
    ):
        return "round must be an integer or null"
    for name in ("from", "to"):
        try:
            if not isinstance(row[name], str):
                raise ValueError(f"{row[name]!r} is not text (quote dates)")
            _span(row[name])
        except ValueError as exc:
            return f"{name}: {exc}"
    return None


def load_reviewed(path: Path) -> list[dict[str, Any]]:
    """The reviewed reschedule rows of ``path``; ValueError on anything but a list of good rows."""
    try:
        rows = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"{_REVIEWED_NAME}: cannot read {path.name}: {exc}") from exc
    if not isinstance(rows, list):
        raise ValueError(f"{_REVIEWED_NAME}: {path.name} is not a list of rows")
    for n, row in enumerate(rows, start=1):
        if problem := _row_problem(row):
            raise ValueError(f"{_REVIEWED_NAME} row {n}: {problem}")
    return rows


# --- compare -----------------------------------------------------------------------------------


def _load(path: Path, label: str, material: list[str]) -> Any | None:
    """The JSON in ``path``; None, with a material line, when it cannot be read."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # a bad JSON or UTF-8 text is a ValueError
        material.append(f"cannot read {label}: {exc}")
        return None


def _guarded(label: str, material: list[str], step: Callable[[], None]) -> None:
    try:
        step()
    except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
        material.append(f"cannot use {label}: unexpected content ({type(exc).__name__}: {exc})")


def _source_names(root: Path, side: str, material: list[str]) -> list[str]:
    try:
        return sorted(p.name for p in (root / "data" / "sources").iterdir() if p.is_dir())
    except OSError as exc:
        material.append(f"cannot list {side} data/sources: {exc}")
        return []


def _pages(
    root: Path, side: str, source: str, material: list[str]
) -> dict[str, dict[str, Any]] | None:
    """The pages of one source's candidate; None, with a material line, when unreadable."""
    label = f"{side} data/sources/{source}/candidate.json"
    doc = _load(root / "data" / "sources" / source / "candidate.json", label, material)
    if doc is None:
        return None
    pages: dict[str, dict[str, Any]] = {}

    def read() -> None:
        for page in doc["scope"]["pages"]:
            pages[str(page["key"])] = {
                "outcome": page["outcome"],
                "units_seen": int(page["units_seen"]),
            }

    before = len(material)
    _guarded(label, material, read)
    return pages if len(material) == before else None


def _only_live(source: str, pages: Mapping[str, Mapping[str, Any]], info: list[str]) -> None:
    for key, page in pages.items():
        info.append(
            f"page only live: {source}/{key} ({page['outcome']}, units_seen {page['units_seen']})"
        )


def _compare_pages(live: Path, offline: Path, material: list[str], info: list[str]) -> None:
    offline_names = _source_names(offline, "offline", material)
    for source in offline_names:
        fixture = _pages(offline, "offline", source, material)
        got = _pages(live, "live", source, material)
        if fixture is None or got is None:
            continue
        for key, page in fixture.items():
            name = f"{source}/{key}"
            if key not in got:
                material.append(f"page missing live: {name}")
                continue
            now = got[key]
            if now["outcome"] not in GOOD_OUTCOMES:
                material.append(f"page not ok live: {name} is {now['outcome']}")
            elif page["units_seen"] > 0 and not (
                page["units_seen"] / 2 <= now["units_seen"] <= page["units_seen"] * 2
            ):
                material.append(
                    f"page units_seen out of range: {name} "
                    f"(live {now['units_seen']}, fixtures {page['units_seen']})"
                )
        _only_live(source, {k: v for k, v in got.items() if k not in fixture}, info)
    for source in _source_names(live, "live", material):
        if source not in offline_names:
            _only_live(source, _pages(live, "live", source, material) or {}, info)


def _severities(root: Path, side: str, material: list[str]) -> dict[str, str] | None:
    doc = _load(root / "status.json", f"{side} status.json", material)
    if doc is None:
        return None
    found: dict[str, str] = {}

    def read() -> None:
        for entry in doc["sources"]:
            found[str(entry["source"])] = str(entry["severity"])

    _guarded(f"{side} status.json", material, read)
    return found


def _compare_status(live: Path, offline: Path, material: list[str], info: list[str]) -> None:
    now = _severities(live, "live", material)
    then = _severities(offline, "offline", material)
    if now is None:
        return
    for source in sorted(now):
        if now[source] == "error":
            material.append(f"source {source} is at severity error live")
    for source in sorted(set(now) | set(then or {})):
        info.append(
            f"severity {source}: live {now.get(source, 'not reported')}, "
            f"fixtures {(then or {}).get(source, 'not reported')}"
        )


def _compare_verdict(live: Path, material: list[str], info: list[str]) -> None:
    doc = _load(live / "verdict.json", "live verdict.json", material)
    if doc is None:
        return

    def read() -> None:
        size, budget = int(doc["feed_bytes"]), int(doc["feed_budget_bytes"])
        if size > budget:
            material.append(f"feed over budget: {size} bytes, budget {budget}")
        try:
            packed = f", gzip {len(gzip.compress((live / 'elections.json').read_bytes()))} bytes"
        except OSError:
            packed = ""
        info.append(f"feed: {size} bytes of {budget}{packed}")
        used = doc.get("requests")
        if used is None:
            info.append("requests: not recorded")
            return
        used = int(used)
        info.append(f"requests: {used} of {DRY_RUN_REQUESTS}")
        if used > DRY_RUN_REQUESTS:
            material.append(f"requests over the limit: {used} of {DRY_RUN_REQUESTS}")

    _guarded("live verdict.json", material, read)


def _entry_name(entry: Any) -> str:
    if isinstance(entry, Mapping):
        return f"{entry.get('place', '?')} {entry.get('office', '?')}"
    return repr(entry)[:60]


def _contest(entry: Mapping[str, Any]) -> str:
    rnd = "" if entry["round"] is None else f" round {entry['round']}"
    return f"{entry['place']} {entry['office']}{rnd} {entry['date']}"


def _same_contest(
    entry: Mapping[str, Any], card: Mapping[str, Any], child: Mapping[str, Any]
) -> bool:
    return bool(
        card["place_id"] == entry["place"]
        and card["level"] == entry["level"]
        and fold(entry["office"]) in fold(child["office_label"])
        and child["round"] == entry["round"]
        and ("jurisdiction" not in entry or child["jurisdiction"] == entry["jurisdiction"])
    )


def _reviewed_rows(
    entry: Mapping[str, Any], reviewed: Sequence[Mapping[str, Any]], used: set[int]
) -> list[tuple[int, Mapping[str, Any]]]:
    """The not yet used reviewed rows that name ``entry`` (one row links one entry)."""
    return [
        (n, row)
        for n, row in enumerate(reviewed)
        if n not in used
        and row["place"] == entry["place"]
        and row["office"] == entry["office"]
        and row["round"] == entry["round"]
        and row.get("jurisdiction") == entry.get("jurisdiction")
        and row["from"] == entry["date"]
    ]


def _compare_contests(
    live: Path,
    expected: Path,
    reviewed: Sequence[Mapping[str, Any]],
    material: list[str],
    info: list[str],
) -> None:
    try:
        entries = yaml.safe_load(expected.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        material.append(f"cannot read the expected file {expected.name}: {exc}")
        return
    feed = _load(live / "elections.json", "live elections.json", material)
    if feed is None:
        return

    def read() -> None:
        months = feed["window"]["months"]
        window = (_span(months[0])[0], _span(months[-1])[1])
        cards = [card for month in feed["months"].values() for card in month]
        used: set[int] = set()
        for entry in entries:
            try:
                if not isinstance(entry, Mapping):
                    raise ValueError("is not a mapping")
                if entry["level"] != "national":
                    continue
                wanted = _span(str(entry["date"]))
            except KeyError as exc:
                name = _entry_name(entry)
                material.append(f"cannot read expected entry {name}: missing key {exc}")
                continue
            except ValueError as exc:
                material.append(f"cannot read expected entry {_entry_name(entry)}: {exc}")
                continue
            if not _overlaps(wanted, window):
                continue
            pairs = [
                (card, child)
                for card in cards
                for child in card["children"]
                if _same_contest(entry, card, child)
            ]
            if any(_overlaps(_card_span(card), wanted) for card, _ in pairs):
                continue
            rows = _reviewed_rows(entry, reviewed, used)
            linked = [
                (card, child, n, row)
                for card, child in pairs
                for n, row in rows
                if _overlaps(_card_span(card), _span(str(row["to"])))
            ]
            if linked:
                card, child, n, row = linked[0]
                used.add(n)
                wrote = "; ".join(child["rescheduled_from"]) or "no old date"
                info.append(
                    f"rescheduled from {row['from']} to {card['date']} (reviewed): "
                    f"{entry['place']} {entry['office']}; the sources wrote {wrote}"
                )
                continue
            moved = [(card, child) for card, child in pairs if child["rescheduled_from"]]
            if moved:
                card, child = moved[0]
                material.append(
                    f"possible reschedule, review required: {_contest(entry)} -> {card['date']} "
                    f"(rescheduled_from: {'; '.join(child['rescheduled_from'])})"
                )
            else:
                material.append(f"expected and not found: {_contest(entry)}")

    _guarded("live elections.json against the expected file", material, read)


def compare(
    live: Path, offline: Path, expected: Path, reviewed: Sequence[Mapping[str, Any]]
) -> tuple[list[str], list[str]]:
    """(material lines, information lines) of the live artifact against the fixture run (P125).

    Never raises on a missing or unreadable live file: each one is a material line.
    """
    material: list[str] = []
    info: list[str] = []
    _compare_pages(live, offline, material, info)
    _compare_status(live, offline, material, info)
    _compare_verdict(live, material, info)
    _compare_contests(live, expected, reviewed, material, info)
    return material, info


# --- the command -------------------------------------------------------------------------------


def _tail(log: Path) -> str:
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "(no log)"
    return "\n".join(lines[-LOG_TAIL_LINES:]) or "(empty log)"


def _report(stamp: str, material: list[str], info: list[str], log_name: str, tail: str) -> str:
    limits = (
        f"Limits: the live run is killed after {LIMIT_S} s (the scrape deadline is "
        f"{DRY_RUN_SCRAPE_DEADLINE_S} s); the offline run after {OFFLINE_LIMIT_S} s; at most "
        f"{DRY_RUN_REQUESTS} requests; the feed budget is {FEED_BUDGET_BYTES} bytes."
    )
    parts = [
        f"# Live check {stamp}",
        "",
        limits,
        "",
        f"Material differences: {len(material)}",
        *[f"- {line}" for line in material],
        "",
        "Information",
        *[f"- {line}" for line in info],
        "",
        f"Last {LOG_TAIL_LINES} lines of {log_name}",
        "",
        "```text",
        tail,
        "```",
    ]
    return "\n".join(parts) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.live_check",
        description="One bounded dry run on the live sources, compared with the fixtures.",
    )
    parser.add_argument("--out", type=Path, required=True, help="where the report folder goes")
    parser.add_argument(
        "--reviewed",
        type=Path,
        default=DEFAULT_REVIEWED,
        help=f"the reviewed reschedule rows (default {DEFAULT_REVIEWED.name})",
    )
    return parser


def _attempt(cmd: Sequence[str], *, limit_s: float, log: Path) -> tuple[int | None, str | None]:
    """``run_bounded`` as (code, failure text): a run that raises must still get its report."""
    try:
        return run_bounded(cmd, limit_s=limit_s, cwd=ROOT, log=log), None
    except (RuntimeError, OSError) as exc:  # not BaseException: an interrupt propagates
        return None, f"{type(exc).__name__}: {exc}"


def _make_folders(out: Path, folder: Path, *repos: Path) -> str | None:
    """Create the report folder and the two repository folders; the reason when that fails."""
    for parent in (out, *out.parents):
        if parent.exists() and not parent.is_dir():
            return f"{parent} is not a directory"
    target = folder
    try:
        folder.mkdir(parents=True)
        for target in repos:
            target.mkdir()
    except FileExistsError:
        if target is folder:
            return f"{folder} already exists (two runs in one second); run again"
        return f"cannot create {target}: it already exists"
    except OSError as exc:
        return f"cannot create {target}: {exc}"
    return None


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exit_:
        return exit_.code if isinstance(exit_.code, int) else 2
    try:
        reviewed = load_reviewed(args.reviewed)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    folder: Path = args.out.resolve() / stamp  # the children run with cwd = the repository root
    offline_repo, live_repo = folder / "repo-offline", folder / "repo-live"
    if (problem := _make_folders(args.out.resolve(), folder, offline_repo, live_repo)) is not None:
        print(problem, file=sys.stderr)
        return 1
    report = folder / "live_check.md"

    offline_cmd = [
        sys.executable,
        "-m",
        "elections_calendar",
        "--offline",
        "tests/fixtures",
        "--now",
        OFFLINE_NOW,
        "--out",
        str(folder / "offline"),
        "--repo",
        str(offline_repo),
    ]
    offline_code, offline_failure = _attempt(
        offline_cmd, limit_s=OFFLINE_LIMIT_S, log=folder / "offline.log"
    )
    if offline_code != 0:
        how = (
            f"failed: {offline_failure}"
            if offline_failure
            else f"was killed at {OFFLINE_LIMIT_S} s"
            if offline_code is None
            else f"exited with code {offline_code}"
        )
        material = [f"the offline run {how}; the live run was not started"]
        text = _report(stamp, material, [], "offline.log", _tail(folder / "offline.log"))
        report.write_bytes(text.encode("utf-8"))
        print(f"Material differences: {len(material)}; report: {report}")
        return 1

    live_cmd = [
        sys.executable,
        "scraper.py",
        "--live",
        "--dry-run",
        "--out",
        str(folder / "live"),
        "--repo",
        str(live_repo),
    ]
    started = time.monotonic()
    live_code, live_failure = _attempt(live_cmd, limit_s=LIMIT_S, log=folder / "live.log")
    elapsed = time.monotonic() - started

    material, info = compare(folder / "live", folder / "offline", EXPECTED, reviewed)
    if live_failure:
        material.insert(0, f"the live run failed: {live_failure}")
    elif live_code is None:
        material.insert(0, f"the live run was killed at {LIMIT_S} s")
    elif live_code != 0:
        material.insert(0, f"the live run exited with code {live_code}")
    info.append(f"elapsed: {elapsed:.1f} s of {LIMIT_S} s")
    text = _report(stamp, material, info, "live.log", _tail(folder / "live.log"))
    report.write_bytes(text.encode("utf-8"))
    print(f"Material differences: {len(material)}; report: {report}")
    return 0 if live_code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
