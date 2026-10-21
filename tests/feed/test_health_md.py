"""HEALTH.md: sections, escaping and capped diagnostics (spec §11.6; P96; R11, S4-T19)."""

import copy
import dataclasses
import json
import re
from collections.abc import Sequence
from datetime import timedelta
from functools import cache
from typing import Any

from elections_calendar.feed import (
    FeedParts,
    RunInfo,
    SourceResult,
    build_feed,
    health_md,
    md_text,
    source_health_entry,
)
from elections_calendar.fetch import FetchResult
from elections_calendar.health import (
    Acknowledgement,
    HealthState,
    Verdict,
    not_yet_active,
    source_reasons,
)
from elections_calendar.model import (
    MAX_DETAIL,
    SOURCE_NAMES,
    SOURCE_ORDER,
    InputUnit,
    Reason,
)
from elections_calendar.publish import FEED_BUDGET_BYTES, feed_bytes
from elections_calendar.runner import SourceRun
from elections_calendar.snapshots import build_snapshot, decide, unit_items
from elections_calendar.sources.base import PARSER_VERSION, Registries
from elections_calendar.sources.osce import Osce
from elections_calendar.window import window_for
from tests.support.feed import RUN_NOW, first_run, fixture_snapshot
from tests.support.known_issues import NOW as ISSUES_NOW
from tests.support.known_issues import entry, issues, ts
from tests.support.pages import raw_pages
from tests.support.snapshots import SynthPage, promoted, report, synth

HOSTILE = (
    "# H1\n<script>x</script> [a](javascript:alert(1)) ![i](https://e.test/i.png) `c` a|b \x07"
    + "y" * 10_000
)
SUFFIX_UNIT = "acknowledge each unit by its full text (unit_text in attention_full.json)"


def render(
    sources: Sequence[SourceResult] | None = None,
    *,
    run_reasons: Sequence[Reason] = (),
    outcome: str = "published",
    verdict: Verdict = "red",
    feed_size: int | None = 377_000,
    budget: int = FEED_BUDGET_BYTES,
    problems: Sequence[str] = (),
    waiting: Sequence = (),  # type: ignore[type-arg]
) -> tuple[str, FeedParts]:
    run = first_run()
    given = list(sources if sources is not None else run.sources.values())
    parts = build_feed(
        run.merge,
        given,
        window=run.window,
        now=RUN_NOW,
        run=RunInfo("local", ()),
        run_reasons=run_reasons,
    )
    text = health_md(
        parts,
        sources=given,
        outcome=outcome,  # type: ignore[arg-type]
        verdict=verdict,
        severity=parts.severity,
        feed_size=feed_size,
        budget=budget,
        problems=problems,
        not_yet_active=waiting,
    )
    return text, parts


@cache
def first_text() -> str:
    return render()[0]


def section(text: str, heading: str) -> list[str]:
    """The lines under ``heading`` up to the next heading of the same or a higher level."""
    level = len(heading.split(" ")[0])
    lines = text.splitlines()
    start = lines.index(heading)
    out: list[str] = []
    for line in lines[start + 1 :]:
        match = re.match(r"(#+) ", line)
        if match and len(match.group(1)) <= level:
            break
        out.append(line)
    return out


def headings(text: str, prefix: str = "## ") -> list[str]:
    return [line for line in text.splitlines() if line.startswith(prefix)]


def replaced(source: str, **changes: Any) -> list[SourceResult]:
    run = first_run()
    return [
        dataclasses.replace(run.sources[s], **changes) if s == source else run.sources[s]
        for s in SOURCE_ORDER
    ]


def test_md_text() -> None:
    assert md_text("a*b_[c]") == "a\\*b\\_\\[c\\]"
    assert md_text("x\n\ty") == "x y"
    assert md_text("\x1b[31m") == "\\[31m"
    assert md_text(None) == "None"
    assert md_text(12) == "12"
    assert md_text("  a   b  ") == "a b"
    assert md_text("a|b `c` <d> \\ &") == "a\\|b \\`c\\` \\<d\\> \\\\ \\&"
    assert md_text("tab\x00nul\x7fdel\x85nel") == "tabnuldel nel"  # NEL is whitespace, so it collapses to a space
    assert md_text("São Tomé – 東京") == "São Tomé – 東京"  # letters and non-ASCII are left alone


def test_health_md_sections() -> None:
    text = first_text()
    assert text.splitlines()[0] == "# Elections calendar health"
    assert [line for line in text.splitlines() if line.startswith("# ")] == [
        "# Elections calendar health"
    ]
    names = [md_text(SOURCE_NAMES[s]) for s in SOURCE_ORDER]
    assert headings(text) == [
        "## Run",
        "## Sources",
        *(f"## {n}" for n in names),
        "## Attention items",
    ]
    top = text.split("\n## ")[0].splitlines()
    bullets = [line for line in top if line.startswith("- ")]
    assert [b.split(":")[0] for b in bullets] == [
        "- Generated", "- Outcome", "- Verdict", "- Severity", "- Data as of", "- Feed",
    ]  # fmt: skip
    assert "- Outcome: published" in bullets
    assert "- Verdict: red" in bullets
    assert "- Severity: warning" in bullets
    assert "- Generated: 2026-10-19T12:00:00Z" in bullets
    assert "- Feed: 377000 bytes of a 524288 byte budget" in bullets
    assert section(text, "## Run") == ["", "No run reasons.", ""]

    ipu = section(text, "## " + md_text(SOURCE_NAMES["ipu"]))
    ignored = (
        f"{md_text('appointed_chamber')} 28, {md_text('inactive_chamber')} 10, "
        f"{md_text('no_expected_date')} 5"
    )
    assert f"- Ignored: {ignored}" in ipu
    assert "- Ignored: appointed\\_chamber 28, inactive\\_chamber 10, no\\_expected\\_date 5" in ipu
    osce = section(text, "## " + md_text(SOURCE_NAMES["osce"]))
    guide = section(text, "## " + md_text(SOURCE_NAMES["electionguide"]))
    assert "- Ignored: duplicate 106" in guide
    assert "- Ignored: none" in osce

    eisa = section(text, "## " + md_text(SOURCE_NAMES["eisa"]))
    published = next(r for r in first_run().sources["eisa"].reasons if r.code == "not_published_yet")
    line = f"- **info** {md_text(published.code)}: {md_text(published.detail)}"
    assert line in eisa  # nothing follows an info reason

    wiki = section(text, "## " + md_text(SOURCE_NAMES["wikipedia"]))
    unparsed = next(line for line in wiki if "unparsed\\_relevant" in line)
    assert unparsed.startswith("- **warning** unparsed\\_relevant: ")
    assert unparsed.endswith(f" — {SUFFIX_UNIT}")
    assert "### Reasons" in wiki and "### Unparsed samples" in wiki
    assert "### Provisional changes" not in wiki and "### No longer listed" not in wiki
    assert "## Not yet active" not in text

    coverage = next(line for line in ipu if line.startswith("- Coverage: "))
    assert coverage == "- Coverage: all: 1 pages, 281 units, ok"
    wiki_cov = next(line for line in wiki if line.startswith("- Coverage: "))
    assert re.fullmatch(
        r"- Coverage: 2026: 2 pages, 565 units, ok; 2027: 2 pages, 99 units, ok", wiki_cov
    )
    assert "- Match: " in "\n".join(osce) and "- Snapshot: " in "\n".join(osce)
    assert "- Download: " in "\n".join(osce) and "- Parse: " in "\n".join(osce)


def test_health_md_feed_line_and_outcome() -> None:
    over, _ = render(feed_size=600_000, budget=524_288)
    assert "- Feed: 600000 bytes of a 524288 byte budget, over budget" in over
    exact, _ = render(feed_size=524_288, budget=524_288)
    assert "- Feed: 524288 bytes of a 524288 byte budget" in exact.splitlines()
    none, _ = render(feed_size=None, outcome="validation_failed", verdict="green")
    assert "- Feed: no feed" in none.splitlines()
    assert "- Outcome: validation failed" in none.splitlines()
    assert "- Verdict: green" in none.splitlines()
    assert "over budget" not in none and "over budget" not in first_text()


def test_health_md_run_reasons_and_problems() -> None:
    text, _ = render(
        run_reasons=(Reason("merge_failed", "boom: a*b"), Reason("count_change", "note")),
        problems=("schema: /x: 'a' is not one of ['b']", "size: 3 bytes is over 2"),
    )
    run = section(text, "## Run")
    bullets = [line for line in run if line.startswith("- ")]
    assert bullets == [
        rf"- **error** merge\_failed: {md_text('boom: a*b')}",
        r"- **info** count\_change: note",
        f"- {md_text("schema: /x: 'a' is not one of ['b']")}",
        f"- {md_text('size: 3 bytes is over 2')}",
    ]
    assert "No run reasons." not in run


def test_health_md_sources_table_and_acknowledgements() -> None:
    until = RUN_NOW + timedelta(days=3)
    a = Reason("http_error", "x", page="a")
    b = Reason("http_error", "x", page="b")
    drop = Reason("sudden_drop", "fell", page="elections")
    never = Reason("ledger_mismatch", "off")
    unit = Reason("partial_relevant", "units")
    info = Reason("count_change", "n")
    ipu = [a, b, drop, never, unit, info]
    acks = (Acknowledgement("http_error", until, "fetch", None, "a"),)
    text, _ = render(replaced("ipu", reasons=tuple(ipu), acknowledged=acks, severity="error"))
    section_ipu = section(text, "## " + md_text(SOURCE_NAMES["ipu"]))
    lines = [line for line in section_ipu if line.startswith("- **")]
    assert lines[0] == "- **error** http\\_error: x — acknowledged until 2026-10-22T12:00:00Z"
    assert lines[1] == (
        "- **error** http\\_error: x — to acknowledge: scope {stage: fetch, year: null, page: b}"
    )
    assert lines[2].startswith("- **warning** sudden\\_drop: fell — to acknowledge: scope {stage: ")
    assert lines[2].endswith("; to accept the drop: accept_drop with this scope and the candidate's counts")
    assert lines[3] == "- **error** ledger\\_mismatch: off — cannot be acknowledged"
    assert lines[4].endswith(f" — {SUFFIX_UNIT}")
    assert lines[5] == "- **info** count\\_change: n"
    table = [line for line in section(text, "## Sources") if line.startswith("|")]
    assert table[0] == "| Source | Severity | Acceptance | Served data fetched | Open reasons |"
    rows = {r.split(" | ")[0].strip("| "): r for r in table[2:]}
    assert len(rows) == 9
    assert rows["IPU"].endswith("| 4 |")  # six reasons: the info one and the acknowledged one are not open
    assert rows[md_text(SOURCE_NAMES["wikipedia"])].endswith("| 2 |")  # unparsed and partial
    assert rows[md_text(SOURCE_NAMES["osce"])].endswith("| 0 |")
    # the scope shows a hostile page escaped, never as markup
    weird = Reason("http_error", "x", page="a|b\n# c")
    text2, _ = render(replaced("ipu", reasons=(weird,), severity="error"))
    assert "page: a\\|b \\# c}" in text2


def test_health_md_not_yet_active() -> None:
    waiting = not_yet_active(
        issues(entry(acknowledged_at=ts(ISSUES_NOW + timedelta(hours=2)))), ISSUES_NOW
    )
    assert len(waiting) == 1
    text, _ = render(waiting=waiting)
    assert section(text, "## Not yet active") == [
        "",
        "- entry 1: ipu http\\_error, from 2026-10-20T14:00:00Z",
        "",
    ]
    names = headings(text)
    assert names.index("## Not yet active") == names.index("## Attention items") - 1


def test_health_md_provisional_and_no_longer_listed() -> None:
    osce = first_run().sources["osce"]
    base = osce.items[0] if osce.items else first_run().sources["wikipedia"].items[0]
    prov = dataclasses.replace(
        base, kind="provisional_change", item_id="1" * 12, unit_text=None, text="moved *x*"
    )
    gone = dataclasses.replace(
        base, kind="disappeared_unit", item_id="2" * 12, unit_text=None, text="No longer listed: Y_Z"
    )
    text, _ = render(replaced("osce", items=(prov, gone, *osce.items)))
    sec = section(text, "## " + md_text(SOURCE_NAMES["osce"]))
    assert section("\n".join(["## s", *sec, "## end"]), "### Provisional changes") == ["", "- moved \\*x\\*", ""]
    assert section("\n".join(["## s", *sec, "## end"]), "### No longer listed") == [
        "",
        "- No longer listed\\: Y\\_Z",
        "",
    ]


def test_health_md_attention_table() -> None:
    text, parts = render()
    rows = [line for line in section(text, "## Attention items") if line.startswith("|")]
    assert rows[0] == "| Kind | Source | Date | Text |"
    assert len(rows) == 2 + len(parts.doc["attention_items"])
    assert "more in attention_full.json" not in text
    cut_parts = dataclasses.replace(
        parts, doc={**parts.doc, "attention_truncated": 3}
    )
    again = health_md(
        cut_parts,
        sources=list(first_run().sources.values()),
        outcome="published",
        verdict="red",
        severity="warning",
        feed_size=1,
        budget=2,
        problems=(),
        not_yet_active=(),
    )
    assert "and 3 more in attention_full.json" in again.splitlines()


def hostile_osce() -> SourceResult:
    """OSCE with a hostile unit text (through ``unit_items``) and a hostile reason detail."""
    unit = InputUnit(
        "osce:elections/hostile", "osce", HOSTILE, "unparsed", "no date", "in_or_after_window"
    )
    snapshot = synth("osce", (SynthPage("elections", 3, extra=(unit,)),))
    decision = decide(
        snapshot,
        run_outcome="complete",
        run_detail="",
        ledger=report(snapshot),
        baseline=None,
        baseline_problem=None,
        acceptances=(),
        window=window_for(RUN_NOW),
        now=RUN_NOW,
    )
    items = unit_items(decision)
    assert len(items) == 1 and "<script>" in items[0].text
    base = first_run().sources["osce"]
    own = Reason("http_error", HOSTILE[:MAX_DETAIL], page="e|l\n# x")
    reasons = (*decision.reasons, own)
    return dataclasses.replace(
        base,
        decision=decision,
        items=items,
        ledger=report(snapshot),
        reasons=reasons,
        severity="error",
    )


def test_health_md_escapes_hostile_text() -> None:
    hostile = hostile_osce()
    text, parts = render(
        replaced(
            "osce",
            decision=hostile.decision,
            items=hostile.items,
            ledger=hostile.ledger,
            reasons=hostile.reasons,
            severity=hostile.severity,
        ),
        run_reasons=(Reason("merge_failed", HOSTILE[:MAX_DETAIL]),),
        problems=(f"schema: {HOSTILE[:200]}",),
    )
    titles = {
        "Elections calendar health", "Run", "Sources", "Reasons", "Unparsed samples",
        "Provisional changes", "No longer listed", "Not yet active", "Attention items",
        *(md_text(n) for n in SOURCE_NAMES.values()),
    }  # fmt: skip
    for line in text.splitlines():
        if line.startswith("#"):
            assert re.fullmatch(r"#{1,3} (.*)", line) and line.lstrip("#")[1:] in titles, line
    bare = re.sub(r"\\.", "", text.replace("\\\\", ""))  # drop escaped backslashes, then pairs
    for markup in ("<script", "](", "![", "`"):
        assert markup not in bare, markup  # escaped, it is plain text
    assert "\x07" not in text
    # the hostile text is still there, escaped (it was not dropped)
    assert "\\# H1 \\<script\\>x\\<\\/script\\>" in text
    assert text.count("javascript") >= 3
    rows = [line for line in section(text, "## Attention items") if line.startswith("|")]
    pipes = {len(re.findall(r"(?<!\\)\|", row)) for row in rows}
    assert pipes == {5}, pipes
    assert any("javascript" in row for row in rows)


def test_diagnostics_are_capped_and_redacted() -> None:
    window = window_for(RUN_NOW)
    adapter = Osce()
    request = adapter.requests(window)[0]
    secret = FetchResult(
        url="https://e.test/a",
        final_url="https://e.test/a;jsessionid=XYZ?token=abc&page=2" + "x" * 400,
        outcome="http_error",
        stage="response",
        http_status=500,
        content_type="text/html",
        body=b"12345",
        elapsed_ms=7,
        attempts=2,
        error_type="HTTPError",
        error="failed at https://e.test/?key=s3cret " + "y" * 400,
    )
    raw = raw_pages("osce", [(request, secret)])
    parsed = adapter.parse(raw, window, Registries.load())
    candidate = build_snapshot(
        raw,
        parsed,
        parser_version=PARSER_VERSION,
        registry_version=fixture_snapshot("osce")[2].registry_version,
        years=window.years,
    )
    import elections_calendar.ledger as ledger_mod

    decision = decide(
        candidate,
        run_outcome="complete",
        run_detail="",
        ledger=ledger_mod.check(raw, parsed),
        baseline=promoted(fixture_snapshot("osce")[2]),
        baseline_problem=None,
        acceptances=(),
        window=window,
        now=RUN_NOW,
    )
    base = first_run().sources["osce"]
    items = unit_items(decision)
    reasons = source_reasons(decision.reasons, items, base.match, HealthState(()))
    result = dataclasses.replace(
        base,
        run=SourceRun("osce", raw, "complete", 0),
        decision=decision,
        ledger=ledger_mod.check(raw, parsed),
        items=items,
        reasons=reasons,
    )
    assert decision.acceptance == "fallback"
    entry_ = source_health_entry(result)
    download = entry_["download"]
    assert download["outcome"] == "http_error"
    assert download["final_url"] and len(download["final_url"]) <= 300
    assert download["error"] and len(download["error"]) <= 300
    sources = [result if s == "osce" else first_run().sources[s] for s in SOURCE_ORDER]
    text, parts = render(sources)
    data = feed_bytes(parts.doc, published_at=RUN_NOW)
    # "abc" alone also occurs in hex digests, so the token is checked with its name
    for secret_text in ("XYZ", "jsessionid", "token=abc", "s3cret"):
        assert secret_text not in data.decode(), secret_text
        assert secret_text not in text, secret_text
    doc = json.loads(data)
    for health in doc["source_health"]:
        for reason in health["reasons"]:
            assert len(reason["text"]) <= 300
        for sample in health["parse"]["unparsed_samples"]:
            assert len(sample) <= 200
    for item in doc["attention_items"]:
        assert len(item["text"]) <= 300
    assert any(r["code"] == "http_error" for r in entry_["reasons"])
    section_text = "\n".join(section(text, "## " + md_text(SOURCE_NAMES["osce"])))
    assert f"; url {md_text(download['final_url'])}" in section_text
    assert f"; error {md_text(download['error'])}" in section_text


def test_health_md_escapes_every_string_of_the_document() -> None:
    """Values the document carries are escaped even when they are not what they should be."""
    text, parts = render()
    doc = copy.deepcopy(parts.doc)
    bad = "# x <b>y</b> [l](u) | `c`"
    doc["generated_at"] = bad
    doc["data_as_of"] = bad
    doc["attention_items"][0]["date"] = bad
    doc["attention_items"][0]["source"] = bad
    entry = doc["source_health"][0]
    entry["snapshot"]["served_fetched_at"] = bad
    entry["snapshot"]["served_snapshot_id"] = bad
    entry["download"]["error"] = bad
    entry["download"]["final_url"] = bad
    entry["download"]["pages"]["stop_reason"] = bad
    entry["parse"]["parser_version"] = bad
    entry["parse"]["ignored_reasons"] = {bad: 1}
    entry["coverage"]["per_year"] = {bad: {"requested": 1, "units_seen": 2, "outcome": bad}}
    changed = health_md(
        dataclasses.replace(parts, doc=doc),
        sources=list(first_run().sources.values()),
        outcome="published",
        verdict="red",
        severity="warning",
        feed_size=1,
        budget=2,
        problems=(),
        not_yet_active=(),
    )
    assert changed != text
    escaped = md_text(bad)
    assert changed.count(escaped) >= 12
    leftover = changed.replace(escaped, "")
    assert "<b>" not in leftover and "](" not in leftover and "`" not in leftover
    assert not any(line.startswith("# x") for line in changed.splitlines())


def test_health_md_escapes_a_timestamp_followed_by_hostile_text() -> None:
    """A value that merely starts like a timestamp is escaped whole (anchored match, S4-T19)."""
    text, parts = render()
    doc = copy.deepcopy(parts.doc)
    bad = "2026-10-16T00:00:00Z <script>x</script> [l](u)"
    doc["generated_at"] = bad
    doc["data_as_of"] = bad
    doc["source_health"][0]["snapshot"]["served_fetched_at"] = bad
    doc["attention_items"][0]["date"] = bad
    changed = health_md(
        dataclasses.replace(parts, doc=doc),
        sources=list(first_run().sources.values()),
        outcome="published",
        verdict="red",
        severity="warning",
        feed_size=1,
        budget=2,
        problems=(),
        not_yet_active=(),
    )
    assert changed.count(md_text(bad)) >= 4
    bare = re.sub(r"\\.", "", changed.replace("\\\\", ""))
    assert "<script" not in bare and "](" not in bare
