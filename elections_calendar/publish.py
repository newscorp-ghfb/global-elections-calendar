"""The feed's bytes and how files reach disk (spec §5.7, §9.7; P103; R26).

Nothing here reads the clock: the publication time is passed in. ``publish`` is a sibling of
``feed`` and imports only ``model``.
"""

import hashlib
import json
import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Final

from elections_calendar.model import _utc_iso, canonical_json, stored_json

FEED_BUDGET_BYTES: Final = 524_288  # R26: 512 KiB, the user's decision of 2026-10-20


def _without_fetched_at(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _without_fetched_at(v) for k, v in value.items() if k != "fetched_at"}
    if isinstance(value, list):
        return [_without_fetched_at(v) for v in value]
    return value


def content_id(doc: Mapping[str, Any]) -> str:
    """SHA-256 of the evidence the feed shows, without any ``fetched_at`` (P103)."""
    evidence = {
        "months": doc["months"],
        "undated": doc["undated"],
        "attention_items": doc["attention_items"],
        "snapshots": [
            [entry["source"], entry["snapshot"]["served_snapshot_id"]]
            for entry in doc["source_health"]
        ],
    }
    return hashlib.sha256(canonical_json(_without_fetched_at(evidence))).hexdigest()


def feed_bytes(doc: Mapping[str, Any], *, published_at: datetime) -> bytes:
    """``elections.json``: the document with its content id and publication time set."""
    out = dict(doc)
    out["content_id"] = content_id(doc)
    out["published_at"] = _utc_iso(published_at)
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n"
    return text.encode("utf-8")


def write_atomic(path: Path, data: bytes) -> None:
    """Write ``data`` to a temporary name beside ``path``, sync it and rename it onto ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def write_manifest(out: Path) -> dict[str, Any]:
    """Write ``manifest.json``: the SHA-256 of every file under ``out``, last."""
    files = {
        path.relative_to(out).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(out.rglob("*"))
        if path.is_file() and path != out / "manifest.json" and path.suffix != ".tmp"
    }
    manifest: dict[str, Any] = {"schema_version": 1, "files": dict(sorted(files.items()))}
    write_atomic(out / "manifest.json", stored_json(manifest))
    return manifest
