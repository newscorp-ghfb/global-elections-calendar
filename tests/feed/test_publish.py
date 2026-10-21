"""The feed's bytes, its content id and atomic writes (§5.7; P103; R26; NM-T04)."""

import copy
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from elections_calendar.publish import (
    FEED_BUDGET_BYTES,
    content_id,
    feed_bytes,
    write_atomic,
    write_manifest,
)
from tests.feed.test_feed import fixture_parts

PUBLISHED = datetime(2026, 10, 19, 13, 30, tzinfo=UTC)


def fixture_doc() -> dict[str, Any]:
    return copy.deepcopy(fixture_parts().doc)


def test_feed_size_is_within_the_budget() -> None:
    size = len(feed_bytes(fixture_parts().doc, published_at=PUBLISHED))
    assert size <= FEED_BUDGET_BYTES, f"the feed is {size} bytes; the budget is {FEED_BUDGET_BYTES}"
    assert FEED_BUDGET_BYTES == 524_288


def test_feed_bytes() -> None:
    doc = fixture_doc()
    data = feed_bytes(doc, published_at=PUBLISHED)
    assert data.endswith(b"}\n")
    assert not data.endswith(b"\n\n")
    loaded = json.loads(data)
    assert loaded["published_at"] == "2026-10-19T13:30:00Z"
    assert loaded["content_id"] == content_id(doc)
    assert doc["content_id"] is None  # the document itself is not changed
    assert list(loaded) == list(doc)
    assert list(loaded["months"]["2026-10"][0]) == list(doc["months"]["2026-10"][0])
    assert {**loaded, "content_id": None, "published_at": None} == doc
    assert data == feed_bytes(fixture_parts().doc, published_at=PUBLISHED)

    small: dict[str, Any] = {
        "z": "é",
        "a": [1, {"y": 2, "b": 3}],
        "content_id": None,
        "published_at": None,
        "months": {},
        "undated": [],
        "attention_items": [],
        "source_health": [],
    }
    text = feed_bytes(small, published_at=PUBLISHED).decode("utf-8")
    cid = content_id(small)
    assert text == (
        '{"z":"é","a":[1,{"y":2,"b":3}],'
        f'"content_id":"{cid}","published_at":"2026-10-19T13:30:00Z",'
        '"months":{},"undated":[],"attention_items":[],"source_health":[]}\n'
    )


def moved_fetches(value: Any) -> int:
    """Move every ``fetched_at`` in place; the number moved."""
    count = 0
    if isinstance(value, dict):
        for key, inner in value.items():
            if key == "fetched_at" and inner is not None:
                value[key] = "2030-01-01T00:00:00Z"
                count += 1
            else:
                count += moved_fetches(inner)
    elif isinstance(value, list):
        for inner in value:
            count += moved_fetches(inner)
    return count


def test_same_evidence_shares_a_content_id() -> None:
    doc = fixture_doc()
    again = fixture_doc()
    assert moved_fetches(again) > 100
    again["generated_at"] = "2026-10-20T12:00:00Z"
    assert content_id(again) == content_id(doc)
    assert len(content_id(doc)) == 64
    assert int(content_id(doc), 16) >= 0
    assert feed_bytes(again, published_at=PUBLISHED) != feed_bytes(doc, published_at=PUBLISHED)

    # Another published_at changes the bytes and not the id.
    later = datetime(2026, 10, 20, tzinfo=UTC)
    assert feed_bytes(doc, published_at=later) != feed_bytes(doc, published_at=PUBLISHED)
    assert json.loads(feed_bytes(doc, published_at=later))["content_id"] == content_id(doc)

    changed = fixture_doc()
    first = next(c for m in changed["months"].values() for c in m)["children"][0]["sources"][0]
    first["date"] = "2031-01-01"
    assert content_id(changed) != content_id(doc)

    reserved = fixture_doc()
    reserved["source_health"][0]["snapshot"]["served_snapshot_id"] = "0" * 12
    assert content_id(reserved) != content_id(doc)

    swapped = fixture_doc()
    swapped["source_health"][0]["source"] = "elsewhere"
    assert content_id(swapped) != content_id(doc)

    item = fixture_doc()
    item["attention_items"][0]["text"] = "other"
    assert content_id(item) != content_id(doc)
    listing = fixture_doc()
    listing["undated"][0]["year"] += 1
    assert content_id(listing) != content_id(doc)


def test_write_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "deep" / "er" / "a.json"
    write_atomic(target, b"one")
    assert target.read_bytes() == b"one"
    write_atomic(target, b"two")
    assert target.read_bytes() == b"two"
    assert sorted(p.name for p in target.parent.iterdir()) == ["a.json"]

    def boom(src: object, dst: object) -> None:
        raise OSError("disk says no")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="disk says no"):
        write_atomic(target, b"three")
    assert target.read_bytes() == b"two"
    assert sorted(p.name for p in target.parent.iterdir()) == ["a.json"]

    fresh = tmp_path / "new.json"
    with pytest.raises(OSError, match="disk says no"):
        write_atomic(fresh, b"x")
    assert not fresh.exists()
    assert not (tmp_path / "new.json.tmp").exists()


def test_write_atomic_never_writes_the_target_directly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "t.json"
    target.write_bytes(b"old")
    seen: list[bytes] = []

    real = os.replace

    def spy(src: Any, dst: Any) -> None:
        seen.append(target.read_bytes())  # still the old content when the rename happens
        real(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    write_atomic(target, b"new")
    assert seen == [b"old"]
    assert target.read_bytes() == b"new"


def test_manifest_lists_every_file(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_bytes(b"alpha")
    nested = tmp_path / "data" / "sources" / "osce"
    nested.mkdir(parents=True)
    (nested / "baseline.json").write_bytes(b"beta")
    (tmp_path / "x.tmp").write_bytes(b"stray")
    (tmp_path / "manifest.json").write_bytes(b"old manifest")
    manifest = write_manifest(tmp_path)
    assert manifest == {
        "schema_version": 1,
        "files": {
            "a.json": hashlib.sha256(b"alpha").hexdigest(),
            "data/sources/osce/baseline.json": hashlib.sha256(b"beta").hexdigest(),
        },
    }
    assert list(manifest["files"]) == ["a.json", "data/sources/osce/baseline.json"]
    assert json.loads((tmp_path / "manifest.json").read_bytes()) == manifest
