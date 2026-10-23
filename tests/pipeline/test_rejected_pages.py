"""Tracebacks to stderr and the raw bodies of invalid pages (R33, P115)."""

import hashlib
from pathlib import Path
from typing import Any

import pytest

from elections_calendar import pipeline
from elections_calendar.pipeline import rejected_pages
from elections_calendar.runner import AdapterSpec
from elections_calendar.sources.base import PageCoverage, PageRequest
from tests.pipeline.test_run import files, go, load
from tests.support.pages import raw_pages, result
from tests.support.repo import OSCE_FETCHED, offline_dir, osce_offline, osce_url

MAINTENANCE = b"<html><body>Maintenance</body></html>"
BROKEN_PARSE = AdapterSpec("osce", "tests.support.broken:BrokenParse")
BROKEN_FETCH = AdapterSpec("osce", "tests.support.broken:BrokenFetch")


def maintenance_dir(tmp_path: Path) -> Path:
    page = tmp_path / "maintenance.html"
    page.write_bytes(MAINTENANCE)
    return offline_dir(tmp_path, [(osce_url(), page, OSCE_FETCHED, "ok")])


@pytest.mark.parametrize(
    ("spec", "words", "detail"),
    [
        (BROKEN_PARSE, "osce: parse failed", "parse: RuntimeError"),
        (BROKEN_FETCH, "osce: fetch failed", "fetch: RuntimeError"),
    ],
)
def test_worker_traceback_is_logged_not_committed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    spec: AdapterSpec,
    words: str,
    detail: str,
) -> None:
    _, out = go(tmp_path, osce_offline(tmp_path), specs=(spec,))
    err = capsys.readouterr().err
    assert words in err
    assert err.index(words) < err.index("Traceback (most recent call last)")
    assert err.count("Traceback (most recent call last)") == 1
    assert "RuntimeError: boom-7f3a" in err
    (entry,) = load(out, "elections.json")["source_health"]
    assert {r["code"]: r["text"] for r in entry["reasons"]}["worker_failed"] == detail
    for path in out.rglob("*"):
        if path.is_file():
            assert b"boom-7f3a" not in path.read_bytes(), path


def test_invalid_page_bodies_are_in_the_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    offline = maintenance_dir(tmp_path)
    _, out = go(tmp_path, offline)
    assert (out / "rejected" / "pages" / "osce" / "0.body").read_bytes() == MAINTENANCE
    index = load(out, "rejected/pages/index.json")
    assert index == [
        {
            "source": "osce",
            "index": 0,
            "key": "elections",
            "year": None,
            "url": osce_url(),
            "final_url": osce_url(),
            "fetch_outcome": "ok",
            "page_outcome": "layout_not_recognised",
            "http_status": 200,
            "content_type": "text/html; charset=utf-8",
            "bytes": len(MAINTENANCE),
            "sha256": hashlib.sha256(MAINTENANCE).hexdigest(),
            "why": "page_outcome",
            "kept": True,
        }
    ]
    manifest = load(out, "manifest.json")["files"]
    assert "rejected/pages/index.json" in manifest
    assert "rejected/pages/osce/0.body" in manifest

    # The parser failed: every page, with no page outcome.
    _, out = go(tmp_path, offline, specs=(BROKEN_PARSE,), out="broken")
    (row,) = load(out, "rejected/pages/index.json")
    assert (row["why"], row["page_outcome"], row["kept"]) == ("parse_failed", None, True)

    # A clean page leaves nothing.
    _, out = go(tmp_path, osce_offline(tmp_path, name="clean"), out="clean-out")
    assert not any(name.startswith("rejected/pages") for name in files(out))

    # Past the cap: listed, not kept, no body file.
    monkeypatch.setattr(pipeline, "REJECTED_PAGES_MAX_BYTES", 10)
    _, out = go(tmp_path, offline, out="capped")
    (row,) = load(out, "rejected/pages/index.json")
    assert row["kept"] is False
    assert not (out / "rejected" / "pages" / "osce" / "0.body").exists()
    assert "rejected/pages/osce/0.body" not in load(out, "manifest.json")["files"]


def page(request_key: str, body: bytes, outcome: Any = "ok") -> tuple[PageRequest, Any]:
    url = f"https://example.test/{request_key}"
    return PageRequest(request_key, url), result(body, url=url, outcome=outcome)


def cover(outcome: Any, key: str = "a") -> PageCoverage:
    prefix = f"osce:{key}/" if outcome in ("ok", "valid_empty") else None
    return PageCoverage(key, None, outcome, prefix, 0)


def test_rejected_pages_rows() -> None:
    raw = raw_pages("osce", [page("a", b"x"), page("b", b""), page("c", b"y")])
    both_ok = [cover("ok", "a"), cover("ok", "b"), cover("ok", "c")]
    # Nothing wrong.
    assert rejected_pages(raw, both_ok, ledger_ok=True, parse_failed=False) == []
    # A ledger that is not ok keeps every page that has a body.
    assert rejected_pages(raw, both_ok, ledger_ok=False, parse_failed=False) == [
        (0, "ledger"),
        (2, "ledger"),
    ]
    # The parser failing wins over the ledger.
    assert rejected_pages(raw, [], ledger_ok=False, parse_failed=True) == [
        (0, "parse_failed"),
        (2, "parse_failed"),
    ]
    # An http_error page with no body is not kept; a challenge page with a body is.
    raw = raw_pages(
        "osce",
        [page("a", b"", "http_error"), page("b", b"<html>Just a moment</html>", "ok")],
    )
    coverage = [cover("http_error", "a"), cover("challenge_page", "b")]
    assert rejected_pages(raw, coverage, ledger_ok=True, parse_failed=False) == [
        (1, "page_outcome")
    ]
    # valid_empty is fine; a coverage list shorter than the pages is a ledger problem.
    raw = raw_pages("osce", [page("a", b"x"), page("b", b"y")])
    assert rejected_pages(
        raw, [cover("valid_empty", "a"), cover("valid_empty", "b")], ledger_ok=True,
        parse_failed=False,
    ) == []
    assert rejected_pages(raw, [cover("ok")], ledger_ok=True, parse_failed=False) == [
        (1, "ledger")
    ]
