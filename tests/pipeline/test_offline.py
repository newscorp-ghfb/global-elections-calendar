"""``pages.json`` and the offline getter (Plan 4 Task 8)."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from elections_calendar.fetch import Deadline
from elections_calendar.pipeline import OfflineGetter, OfflinePage, UsageError, load_offline

T = datetime(2026, 10, 18, 11, 18, 37, tzinfo=UTC)
DEADLINE = Deadline.after(60)


def test_offline_getter(tmp_path: Path) -> None:
    (tmp_path / "a.html").write_bytes(b"<p>a</p>")
    (tmp_path / "b.html").write_bytes(b"")
    getter = OfflineGetter(
        [
            OfflinePage("https://x.test/a", tmp_path / "a.html", T, "text/html", 200),
            OfflinePage("https://x.test/b", tmp_path / "b.html", T, "text/html", None, "timeout"),
        ]
    )
    known = getter.get("https://x.test/a", deadline=DEADLINE)
    assert (known.outcome, known.http_status, known.content_type, known.body) == (
        "ok",
        200,
        "text/html",
        b"<p>a</p>",
    )
    failed = getter.get("https://x.test/b", deadline=DEADLINE)
    assert (failed.outcome, failed.http_status, failed.body) == ("timeout", None, b"")
    unknown = getter.get("https://x.test/other", deadline=DEADLINE)
    assert (unknown.outcome, unknown.http_status, unknown.body) == ("http_error", 404, b"")
    assert unknown.url == unknown.final_url == "https://x.test/other"
    assert getter.fetched_at("https://x.test/a") == T
    assert getter.fetched_at("https://x.test/other") is None


def entry(**changes: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "url": "https://x.test/a",
        "file": "a.html",
        "fetched_at": "2026-10-18T11:18:37Z",
        "content_type": "text/html",
        "status": 200,
    }
    values.update(changes)
    return {k: v for k, v in values.items() if v is not ...}


def test_a_good_pages_json_loads(tmp_path: Path) -> None:
    (tmp_path / "bodies").mkdir()
    (tmp_path / "bodies" / "a.html").write_bytes(b"x")
    (tmp_path / "pages.json").write_text(
        json.dumps(
            {
                "pages": [
                    entry(file="bodies/a.html"),
                    entry(url="https://x.test/b", file="bodies/a.html", outcome="timeout"),
                ]
            }
        )
    )
    getter = load_offline(tmp_path)
    assert getter.get("https://x.test/a", deadline=DEADLINE).body == b"x"
    assert getter.get("https://x.test/b", deadline=DEADLINE).outcome == "timeout"
    assert getter.fetched_at("https://x.test/a") == T


BAD: list[tuple[str, object, str]] = [
    ("missing", ..., "pages.json: not found"),
    ("not-json", b"{", "pages.json: shape"),
    ("not-utf-8", b"\xff", "pages.json: shape"),
    ("list", [], "pages.json: shape"),
    ("pages-not-a-list", {"pages": 1}, "pages.json: shape"),
    ("extra-top-key", {"pages": [], "x": 1}, "pages.json: shape"),
    ("entry-not-an-object", {"pages": ["a"]}, "pages.json: shape"),
    ("missing-key", {"pages": [entry(status=...)]}, "pages.json: shape"),
    ("extra-key", {"pages": [entry(x=1)]}, "pages.json: shape"),
    ("bad-outcome", {"pages": [entry(outcome="fine")]}, "pages.json: shape"),
    ("bad-status", {"pages": [entry(status="200")]}, "pages.json: shape"),
    ("bool-status", {"pages": [entry(status=True)]}, "pages.json: shape"),
    ("bad-time", {"pages": [entry(fetched_at="yesterday")]}, "pages.json: shape"),
    ("time-not-text", {"pages": [entry(fetched_at=5)]}, "pages.json: shape"),
    (
        "time-too-early",
        {"pages": [entry(fetched_at="0001-01-01T00:00:00+05:00")]},
        "pages.json: shape",
    ),
    (
        "time-too-late",
        {"pages": [entry(fetched_at="9999-12-31T23:59:59-05:00")]},
        "pages.json: shape",
    ),
    ("no-file", {"pages": [entry(file="gone.html")]}, "pages.json: no file gone.html"),
    (
        "naive-time",
        {"pages": [entry(fetched_at="2026-10-18T11:18:37")]},
        "pages.json: https://x.test/a: fetched_at needs a time zone",
    ),
    (
        "repeated-url",
        {"pages": [entry(), entry()]},
        "pages.json: repeated url https://x.test/a",
    ),
]


@pytest.mark.parametrize(("content", "message"), [(c, m) for _, c, m in BAD], ids=[n for n, _, _ in BAD])
def test_bad_pages_json(content: object, message: str, tmp_path: Path) -> None:
    (tmp_path / "a.html").write_bytes(b"x")
    if content is not ...:
        data = content if isinstance(content, bytes) else json.dumps(content).encode()
        (tmp_path / "pages.json").write_bytes(data)
    with pytest.raises(UsageError) as caught:
        load_offline(tmp_path)
    assert str(caught.value) == message
