"""lib/schema.js and lib/validate.js: the format dispatch and both documents (Plan 5b-1 Task 3)."""

import copy
import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any, Final

import pytest
from playwright.sync_api import Page

from elections_calendar.ci.recovery import republished_feed
from elections_calendar.validate import legacy_feed_problems
from tests.support.extension import ROOT, artifact_pair, js, v1_feed

V = "lib/validate.js"
S = "lib/schema.js"
NOW: Final = datetime(2026, 10, 19, 14, tzinfo=UTC)
FEED_SCHEMA_FILE: Final = "feed-v2.schema.json"
STATUS_SCHEMA_FILE: Final = "status-v1.schema.json"
ACK: Final = {
    "code": "unparsed_relevant",
    "until": "2026-11-01T00:00:00Z",
    "stage": "parse",
    "year": None,
    "page": None,
}
KEYWORD_CONTAINERS: Final = ("properties", "$defs")
SUBSCHEMA_KEYS: Final = ("items", "additionalProperties", "propertyNames")


@pytest.fixture(scope="module")
def schemas() -> dict[str, dict[str, Any]]:
    def load(name: str) -> dict[str, Any]:
        loaded: dict[str, Any] = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
        return loaded

    return {"feed": load(FEED_SCHEMA_FILE), "status": load(STATUS_SCHEMA_FILE)}


def _feed() -> dict[str, Any]:
    feed: dict[str, Any] = json.loads(artifact_pair()[0])
    return feed


def _status() -> dict[str, Any]:
    status: dict[str, Any] = json.loads(artifact_pair()[1])
    return status


def _v1() -> dict[str, Any]:
    feed: dict[str, Any] = json.loads(v1_feed())
    return feed


def _format(lab: Page, doc: Any, schemas: dict[str, Any]) -> dict[str, Any]:
    got: dict[str, Any] = js(lab, V, "feedFormat", doc, schemas["feed"])
    return got


def _status_problems(lab: Page, doc: Any, schemas: dict[str, Any]) -> list[str]:
    got: list[str] = js(lab, V, "statusProblems", doc, schemas["status"])
    return got


def _republished(feed: bytes) -> Any:
    return json.loads(republished_feed(feed, now=datetime(2026, 10, 19, 13, tzinfo=UTC)))


def test_the_fixture_documents_are_valid(lab: Page, schemas: dict[str, Any]) -> None:
    feed, status = artifact_pair()
    assert _format(lab, json.loads(feed), schemas) == {"format": "v2", "problems": []}
    assert _status_problems(lab, json.loads(status), schemas) == []
    assert _format(lab, json.loads(v1_feed()), schemas) == {"format": "legacy", "problems": []}
    assert _format(lab, _republished(feed), schemas) == {"format": "v2", "problems": []}
    assert _format(lab, _republished(v1_feed()), schemas) == {"format": "legacy", "problems": []}


def _object_schemas(schema: Any, path: str, found: dict[str, dict[str, Any]]) -> None:
    """Every object schema of ``schema`` by the path the page-side walk also uses."""
    if not isinstance(schema, dict):
        return
    if schema.get("type") == "object":
        found[path] = schema
    for key, value in schema.items():
        if key in KEYWORD_CONTAINERS:
            for name, sub in value.items():
                _object_schemas(sub, f"{path}/{key}/{name}", found)
        elif key in SUBSCHEMA_KEYS and isinstance(value, dict):
            _object_schemas(value, f"{path}/{key}", found)
        elif key == "anyOf":
            for i, sub in enumerate(value):
                _object_schemas(sub, f"{path}/anyOf/{i}", found)


_EVERY_REQUIRED_FIELD = """
async ([doc, schema]) => {
  const { schemaProblems } = await import("/lib/schema.js");
  const { REAL } = await import("/lib/validate.js");
  const escape = (k) => k.replace(/~/g, "~0").replace(/\\//g, "~1");
  const isObject = (v) => typeof v === "object" && v !== null && !Array.isArray(v);
  const ref = (s) => (s.$ref === undefined ? s : schema.$defs[s.$ref.split("/").pop()]);
  const takesString = (s) => {
    s = ref(s);
    if (s.type === "string") return true;
    if (typeof s.const === "string") return true;
    if (Array.isArray(s.enum)) return s.enum.some((v) => typeof v === "string");
    return Array.isArray(s.anyOf) && s.anyOf.some(takesString);
  };
  const first = new Map(); // schema path -> {node, steps}
  const visit = (value, node, path, steps) => {
    if (!isObject(node)) return;
    if (node.$ref !== undefined) {
      const name = node.$ref.split("/").pop();
      return visit(value, schema.$defs[name], "#/$defs/" + name, steps);
    }
    if (node.type === "object" && isObject(value) && !first.has(path)) {
      first.set(path, { node, steps });
    }
    (node.anyOf || []).forEach((b, i) => visit(value, b, path + "/anyOf/" + i, steps));
    if (isObject(value)) {
      for (const [k, v] of Object.entries(value)) {
        if (node.properties && k in node.properties) {
          visit(v, node.properties[k], path + "/properties/" + k, [...steps, k]);
        } else if (isObject(node.additionalProperties)) {
          visit(v, node.additionalProperties, path + "/additionalProperties", [...steps, k]);
        }
      }
    }
    if (Array.isArray(value) && isObject(node.items)) {
      value.forEach((v, i) => visit(v, node.items, path + "/items", [...steps, String(i)]));
    }
  };
  visit(doc, schema, "#", []);
  const pointer = (steps) => steps.map((s) => "/" + escape(s)).join("");
  const at = (d, steps) => steps.reduce((x, s) => x[s], d);
  const report = [];
  for (const [path, { node, steps }] of first) {
    for (const key of node.required || []) {
      const ptr = pointer(steps);
      const gone = structuredClone(doc);
      delete at(gone, steps)[key];
      const deleted = schemaProblems(gone, schema, REAL);
      const sub = node.properties[key];
      const wrong = structuredClone(doc);
      at(wrong, steps)[key] = takesString(sub) ? 5 : "x";
      const replaced = schemaProblems(wrong, schema, REAL);
      report.push({
        path,
        key,
        deleted: deleted.some((p) => p.startsWith(ptr + ": ") && p.includes(key)),
        replaced: replaced.some((p) => p.startsWith(ptr + "/" + escape(key) + ": ")),
      });
    }
  }
  return report;
}
"""


def _with_acknowledgements() -> tuple[dict[str, Any], dict[str, Any]]:
    feed, status = _feed(), _status()
    for health in feed["source_health"]:
        if health["source"] == "ipu":
            health["acknowledged"].append(dict(ACK))
    status["acknowledged"].append({"source": "ipu", **ACK})
    return feed, status


def test_every_required_field_is_checked(lab: Page, schemas: dict[str, Any]) -> None:
    feed, status = _with_acknowledgements()
    for name, doc in (("feed", feed), ("status", status)):
        schema = schemas[name]
        objects: dict[str, dict[str, Any]] = {}
        _object_schemas(schema, "#", objects)
        expected = {(path, key) for path, node in objects.items() for key in node.get("required", [])}
        assert len(expected) > 30, name
        report = lab.evaluate(_EVERY_REQUIRED_FIELD, [doc, schema])
        reported = {(row["path"], row["key"]) for row in report}
        assert reported == expected, (name, sorted(expected - reported))
        assert [row for row in report if not (row["deleted"] and row["replaced"])] == []


def _keywords(schema: Any, found: set[str]) -> None:
    if not isinstance(schema, dict):
        return
    found.update(schema)
    for key, value in schema.items():
        if key in KEYWORD_CONTAINERS:
            for sub in value.values():
                _keywords(sub, found)
        elif key in SUBSCHEMA_KEYS:
            _keywords(value, found)
        elif key == "anyOf":
            for sub in value:
                _keywords(sub, found)


def _additional_properties(schema: Any) -> Iterator[Any]:
    if not isinstance(schema, dict):
        return
    if "additionalProperties" in schema:
        yield schema["additionalProperties"]
    for key, value in schema.items():
        if key in KEYWORD_CONTAINERS:
            for sub in value.values():
                yield from _additional_properties(sub)
        elif key in SUBSCHEMA_KEYS:
            yield from _additional_properties(value)
        elif key == "anyOf":
            for sub in value:
                yield from _additional_properties(sub)


def _export(lab: Page, name: str) -> Any:
    return lab.evaluate(f'async () => (await import("/{S}"))["{name}"]')


def test_every_schema_keyword_is_handled(lab: Page, schemas: dict[str, Any]) -> None:
    enforced, ignored = _export(lab, "ENFORCED_KEYWORDS"), _export(lab, "IGNORED_KEYWORDS")
    used: set[str] = set()
    for schema in schemas.values():
        _keywords(schema, used)
    assert used - set(enforced) - set(ignored) == set()
    assert sorted(ignored) == sorted(
        ["$schema", "$id", "title", "description", "maxLength", "maxItems"]
    )
    for schema in schemas.values():
        for value in _additional_properties(schema):
            assert value is False or isinstance(value, dict)


def test_patterns_read_dollar_as_the_end_of_input(lab: Page, schemas: dict[str, Any]) -> None:
    # No refChecks: only the schema's own patterns may reject these.
    def problems(doc: Any, schema: Any) -> list[str]:
        got: list[str] = js(lab, S, "schemaProblems", doc, schema)
        return got

    feed = _feed()
    feed["generated_at"] = "2026-10-19T12:00:00Z\n"
    assert any(p.startswith("/generated_at:") for p in problems(feed, schemas["feed"]))
    status = _status()
    status["attempt_at"] = "2026-10-19T12:00:00Z\n"
    assert any(p.startswith("/attempt_at:") for p in problems(status, schemas["status"]))
    feed = _feed()
    feed["months"]["2026-10"][0]["date"] += "\n"
    got = problems(feed, schemas["feed"])
    assert any(p.startswith("/months/2026-10/0/date:") for p in got)


def _set_generated(feed: dict[str, Any]) -> None:
    feed["generated_at"] = "2026-02-30T00:00:00Z"


def _set_published(feed: dict[str, Any]) -> None:
    feed["published_at"] = "2026-10-19T24:00:00Z"


def _set_fetched(feed: dict[str, Any]) -> None:
    feed["months"]["2026-10"][0]["children"][0]["sources"][0]["fetched_at"] = "2026-10-19T12:60:00Z"


def _set_card_date(feed: dict[str, Any]) -> None:
    feed["months"]["2026-10"][0]["date"] = "2026-02-30"


@pytest.mark.parametrize(
    ("edit", "pointer", "format"),
    [
        (_set_generated, "/generated_at", "invalid"),
        (_set_published, "/published_at", "invalid"),
        (_set_fetched, "/months/2026-10/0/children/0/sources/0/fetched_at", "update_needed"),
        (_set_card_date, "/months/2026-10/0/date", "invalid"),
    ],
)
def test_timestamps_and_dates_must_be_real(
    lab: Page,
    schemas: dict[str, Any],
    edit: Callable[[dict[str, Any]], None],
    pointer: str,
    format: str,
) -> None:
    feed = _feed()
    edit(feed)
    got = _format(lab, feed, schemas)
    assert got["format"] == format
    assert any(p.startswith(pointer + ":") for p in got["problems"])
    if pointer == "/generated_at":
        assert f"{pointer}: not a real timestamp" in got["problems"]


def test_a_status_timestamp_must_be_real(lab: Page, schemas: dict[str, Any]) -> None:
    status = _status()
    status["attempt_at"] = "2026-02-30T00:00:00Z"
    assert "/attempt_at: not a real timestamp" in _status_problems(lab, status, schemas)


def test_limits_are_not_enforced_on_the_client(lab: Page, schemas: dict[str, Any]) -> None:
    feed = _feed()
    feed["future"] = 1
    assert _format(lab, feed, schemas) == {"format": "v2", "problems": []}

    feed = _feed()
    donor = next(r for h in feed["source_health"] for r in h["reasons"])
    feed["source_health"][0]["reasons"] = [{**donor, "text": "x" * 301}]
    assert _format(lab, feed, schemas) == {"format": "v2", "problems": []}

    feed = _feed()
    feed["attention_items"] = [copy.deepcopy(feed["attention_items"][0]) for _ in range(501)]
    assert _format(lab, feed, schemas) == {"format": "v2", "problems": []}


def _drop(doc: dict[str, Any], key: str) -> dict[str, Any]:
    return {k: v for k, v in doc.items() if k != key}


def test_versions_are_dispatched(lab: Page, schemas: dict[str, Any]) -> None:
    rows: list[tuple[Any, str]] = [
        (_feed(), "v2"),
        (_v1(), "legacy"),
        ({**_feed(), "schema_version": 3}, "update_needed"),
        ({**_feed(), "schema_version": "2"}, "update_needed"),
        (_drop(_feed(), "source_health"), "update_needed"),
        (_drop(_feed(), "months"), "invalid"),
        (_drop(_v1(), "months"), "invalid"),
        ([], "invalid"),
        (None, "invalid"),
        ("x", "invalid"),
        ({**_v1(), "schema_version": 1}, "update_needed"),
    ]
    for doc, expected in rows:
        assert _format(lab, doc, schemas)["format"] == expected, (str(doc)[:80], expected)


def _first_card(feed: dict[str, Any]) -> dict[str, Any]:
    card: dict[str, Any] = feed["months"][next(iter(feed["months"]))][0]
    return card


def _edit_card(**changes: Any) -> Callable[[dict[str, Any]], None]:
    def edit(feed: dict[str, Any]) -> None:
        _first_card(feed).update(changes)

    return edit


def _set(**changes: Any) -> Callable[[dict[str, Any]], None]:
    def edit(feed: dict[str, Any]) -> None:
        feed.update(changes)

    return edit


def _delete_generated(feed: dict[str, Any]) -> None:
    del feed["generated_at"]


def _rename_month(feed: dict[str, Any]) -> None:
    feed["months"]["2026-1"] = feed["months"].pop("2026-09")


def _different_names(feed: dict[str, Any]) -> None:
    _first_card(feed)["source_names"] = ["Other"]


def _different_links(feed: dict[str, Any]) -> None:
    _first_card(feed)["links"] = ["https://example.org/other"]


# Excluded: the producer-only rows (an unexpected top-level key, a time ahead of the clock, the
# size cap), which the client does not check.
LEGACY_ROWS: Final[list[tuple[str, Callable[[dict[str, Any]], None]]]] = [
    ("unedited", lambda feed: None),
    ("no generated_at", _delete_generated),
    ("generated_at x", _set(generated_at="x")),
    ("generated_at newline", _set(generated_at="2026-10-16T00:02:31Z\n")),
    ("current_month", _set(current_month="2026-1")),
    ("errors", _set(errors="x")),
    ("months empty list", _set(months=[])),
    ("months key", _rename_month),
    ("months value", lambda feed: feed["months"].update({"2026-09": [5]})),
    ("card date", _edit_card(date="2026-02-30")),
    ("card country", _edit_card(country="")),
    ("card type", _edit_card(type=5)),
    ("card status", _edit_card(status="Held\n")),
    ("card sources", _edit_card(sources=[{"name": 5, "link": "x"}])),
    ("card source_names", _different_names),
    ("card links", _different_links),
    ("republished_from_sha256", _set(republished_from_sha256="ABC")),
]


@pytest.mark.parametrize(("label", "edit"), LEGACY_ROWS, ids=[row[0] for row in LEGACY_ROWS])
def test_legacy_checks_match_the_producer(
    lab: Page, label: str, edit: Callable[[dict[str, Any]], None]
) -> None:
    feed = _v1()
    edit(feed)
    data = json.dumps(feed).encode("utf-8")
    producer = legacy_feed_problems(data, wall_clock=NOW)
    client: list[str] = js(lab, V, "legacyProblems", feed)
    assert bool(client) == bool(producer), (label, client, producer)
    assert bool(client) == (label != "unedited")


def test_status_validation(lab: Page, schemas: dict[str, Any]) -> None:
    assert _status_problems(lab, _status(), schemas) == []
    assert _status_problems(lab, _drop(_status(), "serving_feed_sha256"), schemas) != []
    assert _status_problems(lab, {**_status(), "outcome": "banana"}, schemas) != []
    assert _status_problems(lab, {**_status(), "future": 1}, schemas) == []
    status = _status()
    status["sources"][0]["source"] = "nowhere"
    assert _status_problems(lab, status, schemas) != []


def test_sizes_are_the_plan_limits(lab: Page) -> None:
    assert _export_of(lab, "MAX_FEED_BYTES") == 4_000_000
    assert _export_of(lab, "MAX_STATUS_BYTES") == 1_000_000


def _export_of(lab: Page, name: str) -> Any:
    return lab.evaluate(f'async () => (await import("/{V}"))["{name}"]')


def test_minimum_and_min_items_are_enforced(lab: Page, schemas: dict[str, Any]) -> None:
    feed = _feed()
    feed["months"]["2026-10"][0]["children"] = []
    assert any(p.startswith("/months/2026-10/0/children:") for p in _format(lab, feed, schemas)["problems"])
    feed = _feed()
    feed["attention_truncated"] = -1
    assert any(p.startswith("/attention_truncated:") for p in _format(lab, feed, schemas)["problems"])
