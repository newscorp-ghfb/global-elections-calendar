"""status.json: the attempt, the serving feed and the reasons (spec §5.8; P103, P104; NM-T04)."""

import dataclasses
import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from elections_calendar.feed import Attempt, AttemptOutcome, SourceResult, attempt_of, status_doc
from elections_calendar.health import Acknowledgement, Severity
from elections_calendar.model import REASON_LEVEL, SOURCE_NAMES, SOURCE_ORDER, Reason, _utc_iso
from elections_calendar.validate import validate_status
from tests.support.feed import RUN_NOW, first_run, fixture_feed

V1_FEED = Path(__file__).parent.parent / "fixtures" / "feed" / "2026-10-16-ff30417.json"
SHA = "0123456789abcdef0123456789abcdef01234567"
KEYS = [
    "schema_version", "attempt_id", "attempt_at", "trigger", "code_sha", "outcome", "severity",
    "reasons", "serving_feed_sha256", "serving_published_at", "serving_generated_at",
    "serving_content_id", "sources", "acknowledged",
]  # fmt: skip


def attempt() -> Attempt:
    return attempt_of({}, RUN_NOW)


def doc(
    *,
    run: Attempt | None = None,
    outcome: AttemptOutcome = "published",
    severity: Severity = "warning",
    sources: Sequence[SourceResult] | None = None,
    run_reasons: Sequence[Reason] = (),
    serving: bytes | None = None,
) -> dict[str, Any]:
    """``status_doc`` of the ``first_run()`` sources, given in the opposite of their order."""
    first = first_run()
    return status_doc(
        attempt=run or attempt(),
        outcome=outcome,
        severity=severity,
        sources=sources if sources is not None else [first.sources[s] for s in reversed(SOURCE_ORDER)],
        run_reasons=run_reasons,
        serving=serving,
    )


def rest(got: dict[str, Any]) -> list[Any]:
    """The serving fields other than the digest."""
    return [got[k] for k in KEYS if k.startswith("serving_") and "sha" not in k]


def test_attempt_of() -> None:
    at = datetime(2026, 10, 19, 12, tzinfo=UTC)
    got = attempt_of(
        {"GITHUB_RUN_ID": "123", "GITHUB_EVENT_NAME": "schedule", "GITHUB_SHA": SHA}, at
    )
    assert got.attempt_id == "20261019T120000Z-123"
    assert (got.run_id, got.trigger, got.code_sha, got.attempt_at) == ("123", "schedule", SHA, at)
    empty = attempt_of({}, at)
    assert (empty.run_id, empty.trigger, empty.code_sha) == ("local", "local", "local")
    assert empty.attempt_id == "20261019T120000Z-local"
    bad = attempt_of(
        {"GITHUB_RUN_ID": "12a", "GITHUB_EVENT_NAME": "push; rm", "GITHUB_SHA": "abc"}, at
    )
    assert (bad.run_id, bad.trigger, bad.code_sha) == ("local", "local", "local")
    upper = attempt_of({"GITHUB_SHA": SHA.upper(), "GITHUB_RUN_ID": "٣"}, at)
    assert (upper.run_id, upper.code_sha) == ("local", "local")
    assert attempt_of({"GITHUB_SHA": SHA + "\n"}, at).code_sha == "local"
    # the id is the UTC time, whatever zone the clock was given in
    zone = timezone(timedelta(hours=2))
    assert attempt_of({}, datetime(2026, 10, 19, 14, tzinfo=zone)).attempt_id.startswith(
        "20261019T120000Z"
    )


def test_attempt_times_must_be_aware() -> None:
    naive = datetime(2026, 10, 19, 12)
    with pytest.raises(ValueError, match="timezone-aware"):
        attempt_of({}, naive)
    with pytest.raises(ValueError, match="timezone-aware"):
        Attempt(naive, "local", "local", "local")


def test_status_keys_and_attempt() -> None:
    got = doc()
    assert list(got) == KEYS
    assert got["schema_version"] == 1
    assert got["attempt_id"] == "20261019T120000Z-local"
    assert got["attempt_at"] == "2026-10-19T12:00:00Z"
    assert (got["trigger"], got["code_sha"], got["outcome"], got["severity"]) == (
        "local", "local", "published", "warning"
    )  # fmt: skip
    ci = attempt_of(
        {"GITHUB_RUN_ID": "77", "GITHUB_EVENT_NAME": "schedule", "GITHUB_SHA": SHA}, RUN_NOW
    )
    got = doc(run=ci, outcome="validation_failed", severity="error")
    assert (got["attempt_id"], got["trigger"], got["code_sha"]) == (
        "20261019T120000Z-77", "schedule", SHA
    )  # fmt: skip
    assert (got["outcome"], got["severity"]) == ("validation_failed", "error")


def test_status_links_the_feed_by_its_bytes() -> None:
    parts, data = fixture_feed()
    feed = parts.doc
    published = doc(outcome="published", serving=data)
    assert published["serving_feed_sha256"] == hashlib.sha256(data).hexdigest()
    assert published["serving_published_at"] == "2026-10-19T12:00:00Z"
    assert published["serving_generated_at"] == feed["generated_at"]
    assert published["serving_content_id"] == json.loads(data)["content_id"]
    assert published["serving_content_id"] is not None
    assert validate_status(json.dumps(published).encode()) == ()

    v1 = V1_FEED.read_bytes()
    failed = doc(outcome="validation_failed", serving=v1)
    assert failed["serving_feed_sha256"] == hashlib.sha256(v1).hexdigest()
    assert failed["serving_generated_at"] == "2026-10-16T00:02:31Z"
    assert failed["serving_published_at"] is None
    assert failed["serving_content_id"] is None
    assert failed["serving_feed_sha256"] != published["serving_feed_sha256"]

    nothing = doc(outcome="validation_failed", serving=None)
    assert [nothing[k] for k in KEYS if k.startswith("serving_")] == [None] * 4

    junk = doc(outcome="validation_failed", serving=b"not json")
    assert junk["serving_feed_sha256"] == hashlib.sha256(b"not json").hexdigest()
    assert rest(junk) == [None] * 3

    for other in (b"[1, 2]", b'{"generated_at": 5, "content_id": ["x"]}', b"\xff\xfe"):
        odd = doc(outcome="validation_failed", serving=other)
        assert odd["serving_feed_sha256"] == hashlib.sha256(other).hexdigest()
        assert rest(odd) == [None] * 3
    # a string that is not a timestamp or a digest is not echoed (it would fail the schema)
    foreign = doc(
        outcome="validation_failed",
        serving=b'{"generated_at": "yesterday", "published_at": "x", "content_id": "abc"}',
    )
    assert rest(foreign) == [None] * 3

    for result in (published, failed, nothing, junk, odd, foreign):
        assert validate_status(json.dumps(result).encode()) == ()


def test_status_lists_reasons_and_sources() -> None:
    run = first_run()
    got = doc()
    sources = got["sources"]
    assert [s["name"] for s in sources] == [SOURCE_NAMES[s] for s in SOURCE_ORDER]
    assert [s["served_fetched_at"] for s in sources] == [
        _utc_iso(run.sources[s].decision.health.served_fetched_at)
        for s in SOURCE_ORDER
    ]
    assert all(s["using_fallback"] is False and s["severity"] in ("ok", "warning") for s in sources)
    ipu = run.sources["ipu"]
    health = dataclasses.replace(ipu.decision.health, using_fallback=True)
    fell_back = dataclasses.replace(ipu, decision=dataclasses.replace(ipu.decision, health=health))
    mixed = doc(sources=[fell_back if s == "ipu" else run.sources[s] for s in SOURCE_ORDER])
    assert [s["using_fallback"] for s in mixed["sources"]] == [s == "ipu" for s in SOURCE_ORDER]
    assert [s["severity"] for s in sources] == [run.sources[k].severity for k in SOURCE_ORDER]

    all_reasons = [(k, r) for k in SOURCE_ORDER for r in run.sources[k].reasons]
    assert any(REASON_LEVEL[r.code] == "info" for _, r in all_reasons)  # EISA, count_change
    expected = [(k, r.code) for k, r in all_reasons if REASON_LEVEL[r.code] != "info"]
    assert [(r["source"], r["code"]) for r in got["reasons"]] == expected
    assert all(r["level"] in ("error", "warning") and r["acknowledged"] is False for r in got["reasons"])
    assert got["acknowledged"] == []

    merge = Reason("merge_failed", "boom")
    note = Reason("count_change", "an info reason")
    with_run = doc(run_reasons=(merge, note))
    assert with_run["reasons"][-1] == {
        "source": None, "code": "merge_failed", "level": "error", "text": "boom",
        "page": None, "year": None, "acknowledged": False,
    }  # fmt: skip
    assert len(with_run["reasons"]) == len(got["reasons"]) + 1  # the info reason is left out
    assert [r["code"] for r in with_run["reasons"][:-1]] == [r["code"] for r in got["reasons"]]
    # a reason without a detail shows its code
    bare = doc(run_reasons=(Reason("validation_failed"),))
    assert bare["reasons"][-1]["text"] == "validation_failed"


def test_status_acknowledgements_are_per_page() -> None:
    run = first_run()
    until = RUN_NOW + timedelta(days=3)
    a, b = Reason("http_error", "x", page="a"), Reason("http_error", "x", page="b")
    ipu = dataclasses.replace(
        run.sources["ipu"],
        reasons=(a, b),
        acknowledged=(Acknowledgement("http_error", until, "fetch", None, "a"),),
        severity="error",
    )
    sources = [run.sources[s] if s != "ipu" else ipu for s in SOURCE_ORDER]
    got = doc(sources=sources, severity="error")
    mine = [r for r in got["reasons"] if r["source"] == "ipu"]
    assert [(r["page"], r["acknowledged"]) for r in mine] == [("a", True), ("b", False)]
    assert got["acknowledged"] == [
        {
            "source": "ipu", "code": "http_error", "until": "2026-10-22T12:00:00Z",
            "stage": "fetch", "year": None, "page": "a",
        }
    ]  # fmt: skip
    assert validate_status(json.dumps(got).encode()) == ()


def test_status_refuses_unknown_and_repeated_sources() -> None:
    run = first_run()
    twice = [run.sources["osce"], run.sources["osce"]]
    with pytest.raises(ValueError, match="twice"):
        doc(sources=twice)
    stray = dataclasses.replace(run.sources["osce"], source="nowhere")
    with pytest.raises(ValueError, match="unknown source"):
        doc(sources=[stray])


def test_validate_status() -> None:
    good = json.dumps(doc()).encode()
    assert validate_status(good) == ()
    assert validate_status(b"{") == ("json: not UTF-8 JSON",)
    assert validate_status(b"\xff") == ("json: not UTF-8 JSON",)
    bad = json.loads(good)
    bad["outcome"] = "Published"
    bad["extra"] = 1
    problems = validate_status(json.dumps(bad).encode())
    assert len(problems) == 2 and all(p.startswith("schema: ") for p in problems)
    for outcome in ("superseded", "paused", "republished", "validation_failed"):
        ok = json.loads(good)
        ok["outcome"] = outcome
        assert validate_status(json.dumps(ok).encode()) == ()


def test_the_v1_fixture_is_the_committed_file() -> None:
    data = V1_FEED.read_bytes()
    assert len(data) == 27_557
    assert hashlib.sha256(data).hexdigest() == (
        "0e5ca8d5bf1cc90beb2a00081308e5cf2c81220eda2c3d3b2429ee715afef89b"
    )
    assert json.loads(data)["generated_at"] == "2026-10-16T00:02:31Z"
