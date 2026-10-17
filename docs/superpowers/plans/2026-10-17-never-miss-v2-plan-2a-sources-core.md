# Never-miss v2, Plan 2a: Adapter contract, ledger, runner, ElectionGuide and Wikipedia — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn source pages into accounted-for input units and claims. This plan builds the
adapter contract, the unit ledger with its independent cross-count, and the per-source time-limit
runner. It adds two adapters, ElectionGuide and Wikipedia (national and local calendars), checked
against byte-exact fixtures with provenance notes. v1 keeps running unchanged.

**Architecture:**
- `sources/base.py` (layer 5) defines what an adapter is:
  - `requests(window)` lists the pages;
  - `fetch` streams `RawPage`s;
  - `parse` turns `RawPages` into a `ParseResult` (units, claims, per-page coverage, reasons).
- `ledger.py` (layer 4) checks every `ParseResult` against the spec §9.1 invariants. It also
  re-counts every page's container with a stdlib `html.parser` counter that shares no code with
  the adapters.
- `runner.py` (layer 4) runs each source's fetch in a child process under the source and scrape
  deadlines. It kills and reaps late workers and keeps only pages that arrived complete.
- Parsing reuses Plan 1's `dates`, `places` and `offices`. Two additions come from the fixtures: a
  first-level subdivision index, and office vocabulary.

**Tech Stack:**
- Python 3.14.1, `beautifulsoup4` 4.15.0 + `lxml` 6.1.3 (adapters).
- stdlib `html.parser` (cross-count), stdlib `multiprocessing` with the `spawn` context (runner).
- `pycountry` 26.2.16, in the build script only.
- No new dependencies. The versions are as pinned by Plan 1.

**Spec:** `docs/superpowers/specs/2026-10-16-never-miss-v2-design.md`.
- Read §5.2, §6, §7, §8, §9.1–§9.4, §13.1, §13.4 and Appendix B before you start.
- Where this plan and the spec differ, the plan is right *only* for the items under "Spec
  corrections".
- Plan 1, `docs/superpowers/plans/2026-10-16-never-miss-v2-plan-1-foundations.md`, is built at
  `8632297`. Its Interfaces blocks describe the code, except where the erratum below says
  otherwise.

## Plan 1 "as built" erratum (read first)

Plan 1's document was not re-rendered after its review rounds. The code differs from its text in
these places:

- Plan 1 ends at **415 tests**, not 379 (gates at `8632297`: 415 passed; mypy 24 files; ruff;
  lint-imports 1 contract kept).
- **Task 5 Interfaces is stale:** it says "<Name> (part of <Parent>) → `unknown:<key>@<parent ID>`".
  As built, a name that is one of the parent's registered subdivisions resolves to that
  subdivision, however the parent is spelled (`9d71903`).
- **Task 4 (`9f0f2df`):**
  - `parse_date_text` rolls a missing year forward only for a wrap of at most 5 months;
  - it rejects a day list that does not ascend as written.
- **Task 6 (`c8785c8`):** a body named inside another body's name is not the place's own. This
  covers "Moscow City Duma", "Regional presidents" and "European/Sami Parliament".
- **Task 7 (`1dc2c98`):** `fetch._mediawiki` maps RecursionError (JSON nested too deep) to
  `api_error`.
- **Final round (`8632297`):**
  - `parse_retry_after` treats OverflowError as unreadable;
  - the published MediaWiki error text carries `_api_code(code)`;
  - `DateSpan.from_dict` and `Claim.from_dict` raise `RecordError` on a non-dict;
  - `extract_round` digits are `[1-9]`;
  - the fetch docstrings mark the runner as "not built" (Task 9 below builds it, so update them
    there).

## Plan series

1. **Foundations** (done, `8632297`).
2. **Sources:**
   - **2a (this plan):** fixtures, the adapter contract, the ledger and cross-count, the runner,
     the subdivision index and office vocabulary, ElectionGuide, and Wikipedia national + local;
   - **2b:** NDI, OSCE, IPU, A-WEB, EISA, Carter Center and EEAS. It is written after 2a lands,
     against the code as it is then.
3. **Merge.**
4. **Health, snapshots, feed and publishing**, including the hand-written expected file (§13.2).
5. **Workflow, extension v2.0.0 and rollout.**

**Not in this plan:**
- no change to `scraper.py`, `elections.json`, `.github/workflows/` or `extension/`;
- nothing is pushed or merged;
- no network access.

The fixtures were captured during plan writing. They are copied from the main checkout's
`.scratch/`.

## Global Constraints

Plan 1's Global Constraints all still hold:
- the layering;
- civil dates;
- the window;
- fetching;
- no network in tests;
- the four gates, each in its own shell call;
- mutation checks;
- git on `feat/never-miss-v2` only, checked with `git rev-parse --abbrev-ref HEAD` in its own call
  before every commit;
- `.scratch/` for scratch files;
- the `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>` trailer.

This plan adds:

- **Every input unit gets exactly one outcome** (spec §7, §9.1, G1).
  - A `parsed` unit emits at least one claim.
  - Only `parsed` and `partial` units emit claims.
  - A unit that cannot emit a claim is `unparsed` with a reason, never `parsed`. This covers no
    date, no place, no office, or a reversed range.
- **Adapters never raise on page content.** Any body (empty, binary, truncated, `[]`, `null`, a
  changed layout) gives a `ParseResult` with a page outcome.
- **No units from a page that failed.** A page whose fetch failed, or whose layout is not
  recognised, contributes zero units.
- **Claim links come from the page's own content, never from `FetchResult.final_url`.**
  `final_url` is redacted (Plan 1 requirement b).
- **Unit IDs:**
  - ElectionGuide: `electionguide:<view>/r<n>`, where `n` is the 1-based body row.
  - Wikipedia: `wikipedia:<kind>-<year>@rev<revid>/<h2 id>/li[i]` with nested `/li[j]`, 1-based.
- **Fixtures are byte-exact.** `tests/fixtures/** -text` is already in `.gitattributes`. Tests
  read them as bytes.
- **The runner uses `multiprocessing.get_context("spawn")`** on every platform. No worker may
  outlive `run_sources`.
- **Tests never resolve real host names.** Runner tests use the 127.0.0.1 HTTPS server, or patch
  name resolution inside the worker.

## Review Focus

The five inputs most likely to hurt a user that the spec implies but no step spells out. Each one
is pinned by the tests named here, in the task that owns the code:

1. **Pages that half-work** should end with a named page outcome, no units from that page and no
   exception. Examples:
   - an HTML body cut off mid-table;
   - a 3xx without `Location` (returned as `ok` by `fetch`);
   - HTTP-200 MediaWiki JSON that is `[]`, `null` or `{"parse": []}`;
   - a table whose id or a needed header changed;
   - a valid page with no rows (this one is `valid_empty`, not an error).

   Pinned by:
   - `test_a_redirect_without_location_is_an_http_error` (Task 4);
   - `test_broken_pages_get_an_outcome_never_units` (Task 6);
   - `test_mediawiki_bodies_that_are_not_an_object_fail_the_layout_check` and
     `test_a_page_with_month_headings_and_no_items_is_valid_empty` (Task 7).
2. **One event in several views, or a failed view.**
   - An event seen again in a later view is ignored as `duplicate`, and the fixed view order
     decides which copy counts.
   - When an earlier view failed, the later copy is parsed instead of being lost.

   Pinned by `test_anticipated_rows_seen_earlier_are_duplicates` and
   `test_a_failed_view_does_not_hide_its_events_elsewhere` (Task 6).
3. **Place names that are also subdivision names, and inherited context.** Examples: Georgia the
   US state, a nested item under "United States", Scotland under the United Kingdom, Brazil's
   "Federal District", "Punjab, India". A nested item inherits its ancestors' place and never
   re-resolves its own first token as a country. Pinned by
   `test_a_nested_item_never_re_resolves_its_country` and
   `test_registered_subdivisions_become_the_place` (Task 8), and
   `test_subdivision_lookups_that_must_miss` (Task 2).
4. **A worker that never returns.** Examples: slow name resolution; a server that drips its
   headers; addresses that fail one after another; the scrape budget ending mid-source; a worker
   that crashes or raises.
   - Each ends with an explicit outcome.
   - The worker is killed and reaped.
   - Pages that arrived complete are kept, and nothing arrives late.

   Pinned by the Task 9 tests, every one of which runs under the autouse
   `no_worker_outlives_the_test` check.
5. **Text the grammar doesn't expect** never becomes a parsed unit without a claim. Examples: a
   date-looking prefix that doesn't parse, an article title instead of "Country, office", an empty
   country cell, a reversed or implausible range, a short row. Pinned by:
   - `test_every_parsed_unit_has_a_claim` (Task 5);
   - `test_reversed_ranges_are_unparsed`, `test_a_short_row_is_a_discovered_unparsed_unit` and
     `test_missing_and_implausible_dates_are_unparsed` (Task 6);
   - `test_date_looking_text_that_does_not_parse_is_unparsed` (Task 7);
   - `test_article_titles_are_unparsed_and_relevant` (Task 8).

**Known limits, by design.** The measured values below include them, and each is visible as a
`general` or aggregate claim:
- Canadian federal by-elections listed under "Canada" without the word "federal" come out
  `general`/`subnational`.
- "Tennessee, Supreme Court, retention elections" gets an untidy jurisdiction text.
- A US executive list like "Governor, Lieutenant Governor, and Attorney General" stays one
  `governor` label.
- Myanmar's "Vice President" is `head_of_state`.
- The 46 article-title items on the 2027 local page are attention items (P12).

## Spec corrections

Found while measuring the 2026-10-16 captures.

**Semantic decisions** change behaviour or a promise of the spec: P1, P2, P4, P10 and P12. They
need the user's approval before Task 7 starts. The others refine names, files or details.

| ID | Spec says | This plan does | Why |
|---|---|---|---|
| P1 (semantic) | §7 Wikipedia unit: "every `li`, at any depth, under month sections and 'Indirect elections'" | Every `li` under **every** `h2` section except the stop set {See_also, References, Notes, External_links, Footnotes, Further_reading, Sources, Citations, Bibliography}. "Unknown date" items get a year span for the page's year | national-2027 and local-2026 have an "Unknown date" section. The literal rule would drop its items silently (I1). Pinned by `test_undated_items_get_the_page_year` (Task 7) |
| P2 (semantic) | §7: "an `li` with no text of its own (only a nested list) → ignored `container_item`" | An `li` with nested items whose own text adds only context is ignored `container_item`. Context means a date ("4 October:"), a country ("Canada") or subdivision names ("United States, Minnesota"). Its children inherit that context. An `li` with nested items that also names an office ("Brazil, Governors") is a parsed unit with its own aggregate claim | Every date-only container has text of its own (the date), so the literal rule fits none of the 113 real containers. Pinned by `test_section_items_and_ids` (Task 7) and `test_local_fixture_ledger_balances` (Task 8) |
| P3 | §7: "Offices are split by their separate links" | Offices are split by text, with Plan 1's `split_offices` | One link can hold several offices: Brazil's "President (1st round), Chamber of Deputies and Senate" is a single link. Separate links are joined by " and " or ", ", which `split_offices` already splits (Task 7) |
| P4 (semantic) | §6.2 "a claim with country UK and jurisdiction Scotland resolves to `iso:GB-SCT`" (no adapter rule) | Wikipedia: when the first token after a registered place is one of its registered subdivisions, the subdivision becomes the claim's place and the token is used up. "United Kingdom > Scotland, Parliament" → place `iso:GB-SCT`, institution `iso:GB-SCT/scottish-parliament`. Its level is `national` by Plan 1's rule 2 (open question to the user, unchanged) | Implements §6.2 at the adapter, so v1.0.2 pins on "Scotland (part of the United Kingdom)" keep matching. Pinned by `test_registered_subdivisions_become_the_place` (Task 8) |
| P5 | §7 lists Wikipedia national and local as two rows | One source key `wikipedia`. Its page keys are `national-YYYY` and `local-YYYY` | Follows §5.2's unit-ID example `wikipedia:national-2026@rev1380378807` (Task 7) |
| P6 | §7 contract `fetch(window, fetcher) -> RawPages`, `parse(raw, window) -> (units, claims, layout_ok, coverage)` | `requests(window)`; `fetch(window, fetcher, deadline) -> Iterator[RawPage]`; `parse(raw, window, registries) -> ParseResult`. Each `PageCoverage` carries the page's count rule | Streaming lets the runner keep finished pages when it kills a worker. The ledger needs per-page counts and rules (Tasks 4, 5, 9) |
| P7 | §4 has no runner module | `elections_calendar/runner.py` in layer 4, beside `health \| snapshots \| ledger` | The hard time bound that Plan 1 C15 handed to Plan 2 needs a home above `sources` (Task 9) |
| P8 | §9.4 codes, no type | `ReasonCode` (every §9.4 code plus `worker_failed`) and `Reason(code, detail)` live in `model.py` | Reasons cross layers 4–7. A crashed worker is not a fetch failure (Tasks 4, 9) |
| P9 | §5.6 `per_year.outcome` values | `PageOutcome` adds `valid_empty` and `unfinished` to the download outcomes and `not_published_yet` / `required_year_missing` / `layout_not_recognised` | §9.3 names `valid_empty` as a drop explanation. `unfinished` is a page the deadline cut (Task 4) |
| P10 (semantic) | §6.2 "an empty country string makes the unit `partial` (`place_missing`)" | `unparsed` with reason `place_missing` | A `Claim` needs a `place_id`, and a partial unit keeps its claims. With no place there is no claim (Tasks 6, 7) |
| P11 | §9.2 "end ≥ start, year within ±5 of T" (no outcome named) | ElectionGuide and Wikipedia make the unit `unparsed` with reason `end_before_start`, `date_missing`, `date_unparsed` or `implausible_date` (Plan 1's `plausible`) | Two real ElectionGuide past rows are reversed: Seychelles r126 and Bermuda r176 (Task 6) |
| P12 (semantic) | §7 Wikipedia grammar "<date>: <Country>, <offices>" | An item whose country position starts with a 4-digit year and a space is `unparsed` (`article_title`) with no claim. It stays relevant, so it is an attention item | local-2027 lists 46 items as article titles ("2027 Saarland state election"). Option B, a title grammar with a demonym table, is left for the user to choose (Task 8) |
| P13 | §7 ElectionGuide "fewer than 5 `td` → unparsed (`too_few_cells`)" | A row needs a cell for every mapped column | The three views have 7, 8 and 5 columns. Columns are found by header text (Task 6) |
| P14 | Plan 1 "Plan 2, jurisdictions": decide how to recognise unregistered first-level subdivisions | `scripts/build_subdivisions.py` builds `data/subdivisions.yaml` from pycountry's first-level subdivisions plus `data/subdivisions_manual.yaml` (English exonyms). `places.SubdivisionIndex` reads it. pycountry stays build-only | Same pattern and freshness test as `places.yaml` (Task 2) |
| P15 | §7 ElectionGuide layout check: header only | The layout is recognised only when the body also ends with `</html>` | A page cut mid-table still has its header (Task 6) |
| P16 | §6.3 vocabulary | From the captured labels: office titles are not "general"; a seat district is not a local body; German/Swiss/Spanish legislature words; Austrian/Berlin council words; "amendment(s)" is a referendum; a "Federal …" council in rule 5 is a national aggregate; Oxford-comma parts lose their "and "; aliases for Morocco, Ireland, Lithuania, Algeria | Each was a misclassified real label (Task 3) |
| P17 | Plan 1 "Plan 2, jurisdictions": Canada's "federal by-election" is an adapter rule | That rule, plus "… congressional district …" → the place's one active lower chamber, national | 13th congressional district of Georgia (Task 8) |

**Also settled (no spec change):**
- §13.2's "Wikipedia local alone has 48 list items" in October 2026 is confirmed: 48 units.
- **Plan 1 requirements (a)–(e):**
  - (a) is the first Global Constraint.
  - (b) is the links constraint.
  - (c) is in Task 9: `TrustBundleError.variable`; the message goes to the console only.
  - (d) is in Tasks 4 and 7.
  - (e) is Task 9 Step 1.
- **Deferred minors:**
  - M6 (Cf characters, rare dashes), M7 ("(postponed)"), L70, L72 and L81: the 2a fixtures have
    no Cf character, no dash other than U+002D/U+2013/U+2014, and no "postponed", "(TBC)" or
    "(expected)". 2b decides them with EISA's and OSCE's text.
  - L82 (identical spans): Wikipedia dedupes spans (Task 7).
  - L110: goes away now that Wikipedia sets `subdivision` (Task 8: "Texas, 4th Senate district"
    has no institution).
  - L109 (bare "state"): no misfire in the captured labels ("Mexico, state elections" is `general`).

## How to execute this plan

- **Where:** the worktree `C:/Users/senescalk/Desktop/elections-calendar/.claude/worktrees/never-miss-v2`,
  branch `feat/never-miss-v2`.
  - Do not create worktrees, do not switch branches, do not commit to `main`.
  - Keep the shell in the worktree. Use absolute paths for the main checkout (fixture sources).
- **Style:** this plan pins names, signatures, rules and test values. You write the bodies.
  - A code block appears only where a rule needs it.
  - Where the plan leaves a choice (a data structure, a helper's name), choose; private helpers
    are yours.
  - If a rule is ambiguous, stop and ask the controller. Never guess a value.
- **Measured values:** every count and claim in the tests was measured on the fixtures by
  prototypes that implement exactly these rules.
  - Reference dumps (untracked) live in `.scratch/plan2/full_<page>.txt` (`U` lines are units,
    `C` lines are claims) and `.scratch/plan2/full_eg.txt`.
  - The prototypes are `.scratch/plan2/proto_wiki.py` and `proto_eg.py`. They are measurement
    tools, not code to copy.
  - When a count differs, diff your units/claims against the dump to find the rule that
    differs. Then stop and report: never change the expected value to match.
- **Per task:** follow the Implement-Review loop in the user's CLAUDE.md (at most 3 rounds).
  1. Write the failing test.
  2. Implement.
  3. Run the four gates.
  4. Run the mutation table.
  5. Commit.
- **Mutations:** one per new test. The implementer writes them to
  `.scratch/mutations/plan2a-task-<N>.json`, in the format of `.scratch/mutate.py`, and pastes the
  helper's output into the task report.
  - Stage the task's files with `git add` first.
  - Use `PYTHONDONTWRITEBYTECODE=1`.
- **Handover:** record the commit and the next task after every task in
  `C:/Users/senescalk/Desktop/handovers/elections-v2-plan2a-sdd-ledger.md` and
  `C:/Users/senescalk/Desktop/handovers/elections-v2-RESUME.md`.
- **The Desktop PostToolUse hook** runs `ruff check --fix` on each edited `.py` file. Check
  `git diff --stat` for unrelated rewrites.

## File structure

| Path | Responsibility | Task |
|---|---|---|
| `tests/fixtures/electionguide/2026-10-16/` | the three ElectionGuide views + `PROVENANCE.md` | 1 |
| `tests/fixtures/wikipedia/2026-10-16/` | four MediaWiki parse JSON pages + `PROVENANCE.md` | 1 |
| `tests/support/fixtures.py` | `fixture()` reader | 1 |
| `scripts/build_subdivisions.py`, `data/subdivisions_manual.yaml` → `data/subdivisions.yaml` | first-level subdivision names per country | 2 |
| `elections_calendar/places.py` | + `SubdivisionIndex` | 2 |
| `elections_calendar/offices.py`, `data/institutions_manual.yaml` → `data/institutions.yaml` | vocabulary, aliases, `office_class_of`, `is_by_election` | 3 |
| `elections_calendar/model.py` | + `ReasonCode`, `Reason` | 4 |
| `elections_calendar/sources/__init__.py`, `sources/base.py` | adapter contract, page helpers, `Registries` | 4 |
| `tests/support/pages.py` | `result()`, `raw_pages()`, `claim()`, `unit()` builders | 4, 5 |
| `elections_calendar/ledger.py` | invariants and the stdlib cross-count | 5 |
| `elections_calendar/sources/electionguide.py` | ElectionGuide adapter | 6 |
| `elections_calendar/sources/wikipedia.py` | Wikipedia adapter | 7, 8 |
| `elections_calendar/runner.py` | per-source child processes under deadlines | 9 |
| `elections_calendar/fetch.py` | `TrustBundleError.variable`; docstrings that named the runner as unbuilt | 9 |
| `tests/support/http_server.py` | + `Reply.header_drip` | 9 |
| `tests/support/slow_adapters.py` | adapters that block, crash or sleep, for runner tests | 9 |
| `importlinter.ini` | `sources`, `ledger`, `runner` become real; adapter independence | 4, 5, 7, 9 |
| `tests/unit/test_*.py`, `tests/adapters/test_*.py` | one test file per module / adapter | all |
| `.scratch/mutate.py` (untracked) | kills the whole process tree on timeout | 9 |

## Tasks

### Task 1: Source fixtures with provenance notes

**Files:**
- Create: `tests/fixtures/electionguide/2026-10-16/upcoming.html`, `past.html`, `anticipated.html`
- Create: `tests/fixtures/electionguide/2026-10-16/PROVENANCE.md`
- Create: `tests/fixtures/wikipedia/2026-10-16/national-2026.json`, `local-2026.json`, `national-2027.json`, `local-2027.json`
- Create: `tests/fixtures/wikipedia/2026-10-16/PROVENANCE.md`
- Create: `tests/support/fixtures.py`
- Test: `tests/unit/test_fixtures.py`

**Interfaces:**
- Produces:
  - `tests.support.fixtures.FIXTURES: Path` (the `tests/fixtures` directory);
  - `fixture(source: str, name: str, day: str = "2026-10-16") -> bytes`.

- [ ] **Step 1: Copy the captures byte for byte.** Copy each with `cp`, never through an editor:
  - `C:/Users/senescalk/Desktop/elections-calendar/.scratch/pages2/eg_<view>.html` →
    `<view>.html`;
  - `C:/Users/senescalk/Desktop/elections-calendar/.scratch/pages8/<page>.json` → `<page>.json`.

  Then check: `sha256sum tests/fixtures/electionguide/2026-10-16/* tests/fixtures/wikipedia/2026-10-16/*.json`
  must print exactly the digests in the notes below.

- [ ] **Step 2: Write the two notes** with exactly this content:

`tests/fixtures/electionguide/2026-10-16/PROVENANCE.md`:

```markdown
# ElectionGuide election lists, captured 2026-10-16

- **URLs:** https://www.electionguide.org/elections/type/upcoming/, `.../past/`, `.../anticipated/`
- **Fetched:** 2026-10-16, 14:39 UTC (file times of `.scratch/pages2/eg_*.html`)
- **HTTP status:** not recorded at capture; each body is the complete page, ending in `</html>`
- **SHA-256 of `upcoming.html`:** 72537331120eb385bbe63384c63e549aa17484b21708dfa5d8e863dc1983fe86
- **SHA-256 of `past.html`:** 5c72cb7fc1f33823cd4438fde5344840036ff1593b9b7209851bdf579f9940ce
- **SHA-256 of `anticipated.html`:** 7deaa9935cea758b12715c070b87709a9a180f71411bb8fd0661a11cc390724a
- **Used by:** `tests/adapters/test_electionguide.py`, `tests/unit/test_ledger.py`
```

`tests/fixtures/wikipedia/2026-10-16/PROVENANCE.md`:

```markdown
# Wikipedia electoral calendars (MediaWiki parse API), revisions current on 2026-10-16

- **URLs:** `https://en.wikipedia.org/w/api.php?action=parse&oldid=<revid>&prop=text%7Crevid&format=json&formatversion=2`
  for the revisions current when the HTML pages were captured on 2026-10-16:
  national-2026 1380221397, local-2026 1380378807, national-2027 1379360216, local-2027 1379495387
- **Fetched:** 2026-10-17, 16:13 UTC, through `Fetcher` + `trust_bundle` (HTTP 200,
  `application/json; charset=utf-8`, one attempt each)
- **Shape:** `{"parse": {"title", "pageid", "revid", "text"}}`; `text` is the page HTML
- **SHA-256 of `national-2026.json`:** 9e7c66703fe4fbcfc61e147c30679068e34ac73df177d9c7ab37684dc9622955
- **SHA-256 of `local-2026.json`:** dca4cc6dfc6646e786400de68761c99816210d27a445ed49c73037253f46769c
- **SHA-256 of `national-2027.json`:** 878908fe27271753034ff856f13d717afdc3b2a97586d2d878839c561040fa64
- **SHA-256 of `local-2027.json`:** 9b24f2b85dde3231cd6e2e4b2b9b7eb77d74326b27b9a678fc61a8c3f43d6652
- **Used by:** `tests/adapters/test_wikipedia_*.py`, `tests/unit/test_ledger.py`
```

- [ ] **Step 3: Write the failing test**

```python
SHA_LINE = re.compile(r"\*\*SHA-256 of `([^`]+)`:\*\* ([0-9a-f]{64})")

def test_every_fixture_file_matches_its_provenance_note() -> None:
    notes = sorted(FIXTURES.glob("*/*/PROVENANCE.md"))
    assert [n.parent.relative_to(FIXTURES).as_posix() for n in notes] == [
        "electionguide/2026-10-16", "ipu/2026-10-16", "wikipedia/2026-10-16"]
    for note in notes:
        listed = dict(SHA_LINE.findall(note.read_text(encoding="utf-8")))
        files = {p.name for p in note.parent.iterdir() if p.name != "PROVENANCE.md"}
        assert set(listed) == files, note
        for name, digest in listed.items():
            assert hashlib.sha256((note.parent / name).read_bytes()).hexdigest() == digest, name

def test_fixture_reads_bytes() -> None:
    assert fixture("electionguide", "upcoming.html").rstrip().endswith(b"</html>")
    assert json.loads(fixture("wikipedia", "local-2026.json"))["parse"]["revid"] == 1380378807
```

- [ ] **Step 4: Run** `.venv/Scripts/python.exe -m pytest tests/unit/test_fixtures.py -q`.
  Expected: FAIL first (no `tests.support.fixtures`), then PASS after Step 5.
- [ ] **Step 5: Implement** `tests/support/fixtures.py`. `fixture` reads
  `FIXTURES / source / day / name`.
- [ ] **Step 6: Run the gates, the mutation table, then commit:**
  `test: source fixtures for ElectionGuide and Wikipedia with provenance notes`.

### Task 2: First-level subdivision index

**Files:**
- Create: `scripts/build_subdivisions.py`, `data/subdivisions_manual.yaml`, `data/subdivisions.yaml` (generated)
- Modify: `elections_calendar/places.py` (append `DEFAULT_SUBDIVISIONS`, `SubdivisionIndex`)
- Modify: `README.md` ("Reference data": one line for the new file and its rebuild command)
- Test: `tests/unit/test_places.py`

**Interfaces:**
- Consumes: `elections_calendar.text.norm_name`.
- Produces:
  - `places.DEFAULT_SUBDIVISIONS: Path`;
  - `class SubdivisionIndex` with `load(cls, path: Path = DEFAULT_SUBDIVISIONS) -> SubdivisionIndex`
    and `find(self, country_code: str | None, name: str) -> str | None` (an ISO 3166-2 code);
  - `scripts.build_subdivisions.build(rows: Iterable[tuple[str, str, str]], manual: dict[str, dict[str, str]]) -> tuple[dict[str, dict[str, str]], list[str]]`,
    where `rows` are `(code, country_code, name)` of first-level subdivisions. It returns
    `({country: {key: code}}, ambiguous)`, with `ambiguous` as `"<country> <key>"` strings;
  - `render(index, ambiguous) -> str`;
  - `main() -> int`;
  - `OUT`, `MANUAL` paths. Run it as `python -m scripts.build_subdivisions`.

**Rules (build):**
- **Which subdivisions:** first-level ones, i.e. pycountry entries whose `parent_code is None`.
- **Name keys:**
  - Drop a trailing parenthesised part (`\s*\([^)]*\)$`).
  - The key is the `norm_name` of the result.
  - When the name holds ", ", also add the key of the part before the first ", ". So
    "Madrid, Comunidad de" adds "madrid".
- **Ambiguous keys:** a key two different codes of one country share is left out entirely and
  listed in `ambiguous`. There are 10 in pycountry 26.2.16, e.g. `BG sofia` (BG-22, BG-23).
- **Manual entries:** entries in `data/subdivisions_manual.yaml` are added after the
  ambiguity check and win over generated keys. The file maps country → English exonym → code:

```yaml
# Hand-maintained input to scripts/build_subdivisions.py: English names sources use
# that pycountry does not list. Edit this file, rebuild data/subdivisions.yaml, review both diffs.
DE: {Bavaria: DE-BY, Hesse: DE-HE, Lower Saxony: DE-NI, Rhineland-Palatinate: DE-RP,
     Saxony-Anhalt: DE-ST, North Rhine-Westphalia: DE-NW, Saxony: DE-SN, Thuringia: DE-TH}
ES: {Andalusia: ES-AN, Castile and León: ES-CL, Catalonia: ES-CT, Basque Country: ES-PV}
BA: {Federation of Bosnia and Herzegovina: BA-BIH}
BR: {Federal District: BR-DF}
CH: {Bern: CH-BE}
MD: {Gagauzia: MD-GA}
MX: {Coahuila: MX-COA}
PK: {Azad Kashmir: PK-JK}
TH: {Bangkok: TH-10}
```

- **Output:** `render` writes YAML with countries and keys sorted. Its header comment names
  the generator, the pycountry version and the ambiguous keys. A manual code pycountry doesn't
  know raises `BuildError`. Reuse the pattern of `scripts/build_places.py`.

**Rules (`find`):**
- `None` for a `None` or empty country code, or an empty name.
- Otherwise `key = norm_name(name)`; return the direct hit.
- Else, when the key ends with " prefecture", " state", " province" or " region" and the
  remainder is a hit, return that code.
- Else `None`.

- [ ] **Step 1: Write the failing tests**

```python
SUBDIVISIONS = SubdivisionIndex.load()

def test_subdivisions_resolve_names_sources_use() -> None:
    cases = {("US", "Georgia"): "US-GA", ("US", "Texas"): "US-TX", ("BR", "Federal District"): "BR-DF",
             ("BR", "São Paulo"): "BR-SP", ("DE", "Lower Saxony"): "DE-NI", ("CH", "Bern"): "CH-BE",
             ("ES", "Madrid"): "ES-MD", ("CZ", "Praha"): "CZ-10", ("JP", "Okinawa Prefecture"): "JP-47",
             ("NG", "Oyo State"): "NG-OY", ("PE", "Lima"): "PE-LIM", ("CA", "Ontario"): "CA-ON",
             ("AU", "Northern Territory"): "AU-NT", ("US", "District of Columbia"): "US-DC"}
    assert {k: SUBDIVISIONS.find(*k) for k in cases} == cases

def test_subdivision_lookups_that_must_miss() -> None:
    assert SUBDIVISIONS.find("GE", "Georgia") is None      # the country has no such subdivision
    assert SUBDIVISIONS.find(None, "Texas") is None
    assert SUBDIVISIONS.find("US", "") is None
    assert SUBDIVISIONS.find("US", "Scarborough Southwest") is None
    assert SUBDIVISIONS.find("BG", "Sofia") is None         # ambiguous: BG-22 and BG-23
    assert SUBDIVISIONS.find("PH", "Bangsamoro") is None

def test_build_leaves_out_names_two_subdivisions_share() -> None:
    index, ambiguous = build([("XA-1", "XA", "Alpha"), ("XA-2", "XA", "Alpha (city)"),
                              ("XA-3", "XA", "Beta, Region of")], {"XA": {"Gamma": "XA-3"}})
    assert index == {"XA": {"beta": "XA-3", "beta region of": "XA-3", "gamma": "XA-3"}}
    assert ambiguous == ["XA alpha"]

def test_committed_subdivisions_yaml_is_up_to_date() -> None:
    ...  # same shape as test_committed_places_yaml_is_up_to_date
```

  `test_build_leaves_out_names_two_subdivisions_share` gives a manual code pycountry doesn't
  know: pass the known codes to `build`'s caller, not to `build`, or let `build` accept a
  `known_codes` set. That choice is yours; pin it with a fifth test,
  `test_build_rejects_an_unknown_manual_code`.

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/unit/test_places.py -q`.
  Expected: the new tests FAIL on import.
- [ ] **Step 3: Implement** the builder and `SubdivisionIndex`. Then run
  `.venv/Scripts/python.exe -m scripts.build_subdivisions` and review `data/subdivisions.yaml`
  (200 countries).
- [ ] **Step 4: Run** the file's tests; expected PASS. Then run the gates and the mutation table.
- [ ] **Step 5: Commit:** `feat(places): first-level subdivision index from pycountry plus English exonyms`.

### Task 3: Office vocabulary and chamber aliases from the captured labels

**Files:**
- Modify: `elections_calendar/offices.py` (regexes, rule 5, `split_offices`, `office_class_of`, `is_by_election`, module docstring)
- Modify: `data/institutions_manual.yaml`; rebuild `data/institutions.yaml` with `python -m scripts.build_institutions`
- Test: `tests/unit/test_offices.py` (it uses the helper `classify(label, place_id, kind)`, which returns `(office_class, institution, aggregate, kind, round, level_hint)`)

**Interfaces:**
- Produces:
  - `office_class_of(part: str, place_id: str, registry: InstitutionRegistry) -> OfficeClass | None`.
    This is the old `_class_of`, renamed and now public; `split_offices` uses it.
  - `is_by_election(text: str) -> bool` (`_BY_ELECTION.search`).
  - `split_offices` returns parts with a leading "and " or "& " removed (Oxford comma). The
    split decisions are unchanged: the strip happens after both split passes.

**Changes (P16):**
1. **`_GENERAL`:** "general" does not count when the word right before it is attorney,
   auditor, solicitor, secretary, inspector or comptroller.
2. **`_LOCAL`, "district":** counts only when no word comes right before it and no number
   follows it. "36th State Assembly district" and "Assembly district 5" are seats.
3. **`_LEGISLATURE`:** add landtag, cortes, abgeordnetenhaus, kantonsrat, grosser rat and
   bürgerschaft. Not landrat: it is a cantonal parliament in Switzerland but a district
   executive in Germany, so it stays unrecognised.
4. **`_LOCAL`:** add gemeinderat and bezirksverordnetenversammlung(en).
5. **`_REFERENDUM`:** add `amendments?`.
6. **Rule 5 (local bodies):** when the text has the word "federal" and no `_LOCAL` word, so it
   reached rule 5 through council or regional words, return class `general`, `aggregate=True`,
   `level_hint="national"`, kind `aggregate`, `recognised=True`.
7. **Aliases** under `aliases:` in `data/institutions_manual.yaml`:
   - `iso:MA: {House of Representatives: [Chamber of Representatives]}`;
   - `iso:IE: {House of Representatives: [Dáil, Dáil Éireann], Senate: [Seanad, Seanad Éireann]}`;
   - `iso:LT: {Parliament: [Seimas]}`;
   - `iso:DZ: {National People's Assembly: [People's National Assembly]}`.
8. **The module docstring** describes items 1, 2 and 6.

- [ ] **Step 1: Write the failing tests** (values measured with these rules):

```python
def test_office_titles_are_not_general_elections() -> None:
    for title in ("Attorney General", "Auditor General", "Solicitor General", "Secretary General"):
        assert keyword_class(title) is None
    assert keyword_class("General") == "general"

def test_a_seat_district_is_not_a_local_body() -> None:
    assert keyword_class("36th State Assembly district, special election") == "legislature"
    assert keyword_class("Assembly district 5") == "legislature"
    assert keyword_class("District council elections") == "local_council"
    assert classify("36th State Assembly district, special election", "iso:US", "subdivision") == (
        "legislature", None, False, "by_election", None, "subnational")

def test_body_names_from_the_captured_pages() -> None:
    for name in ("Landtag", "Cortes", "Abgeordnetenhaus", "Kantonsrat", "Grosser Rat", "Bürgerschaft"):
        assert keyword_class(name) == "legislature"
    for name in ("Gemeinderat", "Bezirksverordnetenversammlungen"):
        assert keyword_class(name) == "local_council"
    assert keyword_class("Landrat") is None
    assert keyword_class("amendments") == keyword_class("constitutional amendment") == "referendum"

def test_a_federal_council_is_a_national_aggregate() -> None:
    o = classify_office("Federal Council", "iso:CH", "nationwide", REGISTRY)
    assert (o.office_class, o.institution, o.aggregate, o.kind, o.level_hint, o.recognised) == (
        "general", None, True, "aggregate", "national", True)
    assert classify("Federal Council", "iso:DE")[:2] == ("upper_house", "iso:DE/federal-council")

def test_chamber_aliases_from_the_captured_pages() -> None:
    assert classify("Chamber of Representatives", "iso:MA")[:2] == ("lower_house", "iso:MA/house-of-representatives")
    assert classify("Dáil by-election", "iso:IE", "named")[:4] == (
        "lower_house", "iso:IE/house-of-representatives", False, "by_election")
    assert classify("Seanad", "iso:IE")[:2] == ("upper_house", "iso:IE/senate")
    assert classify("Seimas by-election", "iso:LT", "named")[:4] == (
        "legislature", "iso:LT/parliament", False, "by_election")
    assert classify("People's National Assembly", "iso:DZ")[:2] == ("lower_house", "iso:DZ/national-peoples-assembly")

def test_split_offices_drops_the_oxford_and() -> None:
    assert split_offices("Mayor (1st round), City Attorney (1st round), City Controller, and City Council (1st round)",
                         "iso:US", REGISTRY) == ["Mayor (1st round)", "City Attorney (1st round)", "City Controller",
                                                 "City Council (1st round)"]
    assert split_offices("Governor, Lieutenant Governor, and ballot measure", "iso:US", REGISTRY) == [
        "Governor", "Lieutenant Governor", "ballot measure"]
    assert split_offices("Governor, Lieutenant Governor, and Attorney General", "iso:US", REGISTRY) == [
        "Governor, Lieutenant Governor, and Attorney General"]       # known limit: one label

def test_office_class_of_and_is_by_election_are_public() -> None:
    assert office_class_of("Senedd", "iso:GB-WLS", REGISTRY) == "legislature"
    assert office_class_of("by-election", "iso:GB", REGISTRY) is None
    assert is_by_election("Georgia's 13th congressional district, special election (1st round)")
    assert not is_by_election("Governor")
```

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/unit/test_offices.py -q`.
  Expected: the new tests FAIL; the 96 existing ones pass.
- [ ] **Step 3: Implement**, rebuild `data/institutions.yaml`, and check that its diff holds
  only the 6 new aliases.
- [ ] **Step 4: Run** the full suite. Expected: every earlier test still passes. If one fails,
  the vocabulary contradicts a Plan 1 decision: stop and ask.
- [ ] **Step 5:** Run the gates and the mutation table, then commit:
  `feat(offices): vocabulary and chamber aliases from the 2026-10-16 labels`.

### Task 4: Reasons and the adapter contract

**Files:**
- Modify: `elections_calendar/model.py` (append `ReasonCode`, `Reason`)
- Create: `elections_calendar/sources/__init__.py` (empty), `elections_calendar/sources/base.py`
- Modify: `importlinter.ini` (`(sources)` → `sources`)
- Create: `tests/support/pages.py`
- Test: `tests/unit/test_model.py`, `tests/unit/test_sources_base.py`

**Interfaces:**
- Consumes:
  - `fetch.Deadline`, `fetch.FetchResult` and `fetch.Fetcher`;
  - `PlaceRegistry`, `SubdivisionIndex` (Task 2) and `InstitutionRegistry`;
  - `window.Window`;
  - `model.InputUnit`, `model.Claim` and `model.RecordError`.
- Produces in `model.py`:
  - `ReasonCode = Literal[...]`: the §9.4 errors (`fetch_failed`, `tls_error`, `timeout`,
    `dns_error`, `http_error`, `challenge_page`, `api_error`, `layout_not_recognised`,
    `required_year_missing`, `pagination_incomplete`, `deadline`, `unavailable`,
    `ledger_mismatch`, `discovery_mismatch`, plus `worker_failed`), warnings and info codes, in
    §9.4's order.
  - `@dataclass(frozen=True, slots=True) class Reason: code: ReasonCode; detail: str = ""`. It
    is checked like every model record (`_check_fields`). A detail longer than 300 characters
    raises `RecordError`. It has `to_dict()` and `from_dict()`.
- Produces in `sources/base.py`:
  - `PageOutcome = Literal["ok", "valid_empty", "not_published_yet", "required_year_missing", "layout_not_recognised", "unfinished", "http_error", "timeout", "tls_error", "dns_error", "challenge_page", "api_error", "deadline", "fetch_failed"]`.
  - `PageRequest(key: str, url: str, year: int | None = None, mediawiki: bool = False)`.
  - `RawPage(request: PageRequest, result: FetchResult, fetched_at: datetime)`. A naive
    `fetched_at` raises `RecordError`.
  - `RawPages(source: str, pages: tuple[RawPage, ...], unfinished: tuple[PageRequest, ...] = ())`.
  - `TableRowsRule(table_id: str)` and
    `SectionItemsRule(stop_ids: frozenset[str], json_text_path: tuple[str, ...] = ())`;
    `CountRule = TableRowsRule | SectionItemsRule`.
  - `PageCoverage(key: str, year: int | None, outcome: PageOutcome, unit_prefix: str | None, units_seen: int, revid: int | None = None, rule: CountRule | None = None)`.
    `unit_prefix` is e.g. `"electionguide:upcoming/"` or `"wikipedia:national-2026@rev1380221397/"`.
    It and `rule` are set exactly when the outcome is `ok` or `valid_empty`.
  - Every adapter's `parse` returns one `PageCoverage` per `RawPage`, in page order, then
    `PageCoverage(request.key, request.year, "unfinished", None, 0)` per `raw.unfinished` request.
  - `ParseResult(source: str, units: tuple[InputUnit, ...], claims: tuple[Claim, ...], coverage: tuple[PageCoverage, ...], notes: tuple[Reason, ...] = ())`,
    with two properties:
    - `layout_ok`: no page is `layout_not_recognised`;
    - `reasons`: `coverage_reasons(coverage) + notes`.
  - `coverage_reasons(coverage) -> tuple[Reason, ...]`. Each page with one of these outcomes
    gives `Reason(<code>, detail=<page key>)`:
    - `ok` and `valid_empty` → no reason;
    - `unfinished` → `deadline`;
    - every other outcome → the code of the same name.
  - `Registries(places: PlaceRegistry, institutions: InstitutionRegistry, subdivisions: SubdivisionIndex)`
    with `load(cls) -> Registries` (default paths).
  - `class Getter(Protocol): def get(self, url: str, *, deadline: Deadline, mediawiki: bool = False) -> FetchResult`.
  - `class Adapter(Protocol)`: `source: str`; `requests(self, window: Window) -> tuple[PageRequest, ...]`;
    `fetch(self, window: Window, fetcher: Getter, deadline: Deadline) -> Iterator[RawPage]`;
    `parse(self, raw: RawPages, window: Window, registries: Registries) -> ParseResult`.
  - `fetch_pages(requests: Iterable[PageRequest], fetcher: Getter, deadline: Deadline, *, now: Callable[[], datetime] = <UTC now>) -> Iterator[RawPage]`:
    one request at a time, in order (§8: "requests within one source run one at a time").
  - `page_failure(page: RawPage) -> PageOutcome | None`, the shared download check:
    - a non-`ok` fetch outcome → that outcome;
    - an `ok` result with a 3xx status (a redirect without `Location`, Plan 1 L126) →
      `http_error`;
    - otherwise `None`, and the adapter's layout check decides.
- Produces in `tests/support/pages.py`:
  - `FETCHED = datetime(2026, 10, 16, 14, 39, tzinfo=UTC)`;
  - `result(body: bytes, *, url: str = "https://example.test/", outcome: FetchOutcome = "ok", status: int | None = 200, content_type: str = "text/html; charset=utf-8", api_code: str | None = None, final_url: str | None = None) -> FetchResult`;
  - `raw_pages(source: str, pages: Iterable[tuple[PageRequest, FetchResult]], unfinished: tuple[PageRequest, ...] = ()) -> RawPages`.

- [ ] **Step 1: Write the failing tests**

```python
def test_reasons_are_checked_records() -> None:
    assert Reason("coverage_gap", "past list starts 2026-09-02").to_dict() == {
        "code": "coverage_gap", "detail": "past list starts 2026-09-02"}
    assert Reason.from_dict({"code": "worker_failed", "detail": "exit code 3"}) == Reason("worker_failed", "exit code 3")
    for bad in ({"code": "banana", "detail": ""}, {"code": "deadline", "detail": "x" * 301}, {"code": "deadline", "detail": 5}):
        with pytest.raises(RecordError):
            Reason.from_dict(bad)

def test_fetch_pages_fetches_one_at_a_time_in_order() -> None:
    # a stub Getter records (url, mediawiki, deadline) and returns result(b"x", url=url)
    ...  # assert the order, the flags, the shared deadline and fetched_at == FETCHED (now=lambda: FETCHED)

def test_a_raw_page_needs_an_aware_fetch_time() -> None:
    req = PageRequest("upcoming", "https://example.test/")
    with pytest.raises(RecordError):
        RawPage(req, result(b""), datetime(2026, 10, 16, 14, 39))
    assert RawPage(req, result(b""), datetime(2026, 10, 16, 16, 39, tzinfo=timezone(timedelta(hours=2)))).fetched_at.utcoffset()

def test_a_redirect_without_location_is_an_http_error() -> None:
    req = PageRequest("upcoming", "https://example.test/")
    assert page_failure(RawPage(req, result(b"", status=302), FETCHED)) == "http_error"
    assert page_failure(RawPage(req, result(b"", outcome="timeout", status=None), FETCHED)) == "timeout"
    assert page_failure(RawPage(req, result(b"<html></html>"), FETCHED)) is None

def test_page_outcomes_give_reasons() -> None:
    cov = [PageCoverage("a", None, "ok", "s:a/", 3, rule=TableRowsRule("t")),
           PageCoverage("b", 2027, "not_published_yet", None, 0), PageCoverage("c", 2026, "unfinished", None, 0),
           PageCoverage("d", None, "challenge_page", None, 0), PageCoverage("e", None, "valid_empty", "s:e/", 0, rule=TableRowsRule("t"))]
    assert coverage_reasons(cov) == (Reason("not_published_yet", "b"), Reason("deadline", "c"), Reason("challenge_page", "d"))
```

- [ ] **Step 2: Run** the two test files. Expected: FAIL on import.
- [ ] **Step 3: Implement.** In `importlinter.ini`, change `(sources)` to `sources`.
- [ ] **Step 4:** Run the gates (lint-imports must say `Contracts: 1 kept`) and the mutation
  table, then commit: `feat(sources): adapter contract, page outcomes and reasons`.

### Task 5: Ledger and the independent cross-count

**Files:**
- Create: `elections_calendar/ledger.py`
- Modify: `importlinter.ini` (`(ledger)` → `ledger`), `tests/support/pages.py` (+ `unit()` and `claim()`)
- Test: `tests/unit/test_ledger.py`

**Interfaces:**
- Consumes: Task 4's `RawPages`, `ParseResult`, `PageCoverage`, `TableRowsRule`, `SectionItemsRule`
  and `Reason`.
- Produces:
  - `cross_count(rule: CountRule, body: bytes) -> int | None`. It uses stdlib `html.parser` and
    `json` only. It returns `None` when the body cannot be read for the rule: invalid JSON, a
    missing path or a non-string text.
    - **`TableRowsRule`** counts the `tr` tags inside a `tbody` of the table with that id. A
      table nested inside it is not counted.
    - **`SectionItemsRule`** first follows `json_text_path` when one is given. It then counts
      every `li` start tag after an `h2` start tag whose `id` is not in `stop_ids`. An `li`
      before the first `h2` is not counted.
  - `@dataclass(frozen=True, slots=True) class LedgerReport`, with fields:
    - `source: str`;
    - `units_seen: int`;
    - `outcomes: dict[Outcome, int]`, all 4 keys;
    - `ignored_reasons: dict[str, int]`;
    - `relevance: dict[Relevance, int]`, all 3 keys, counting partial + unparsed units;
    - `problems: tuple[str, ...]`;
    - `reasons: tuple[Reason, ...]`;
    - property `ok`.
  - `check(raw: RawPages, result: ParseResult) -> LedgerReport`. `reasons` holds
    `Reason("discovery_mismatch", ...)` when any cross-count differs, and
    `Reason("ledger_mismatch", ...)` for any other problem, each at most once. The detail is the
    first problem of that kind, cut to 300 characters.
- Produces in `tests/support/pages.py`:
  - `unit(source: str, uid: str, outcome: Outcome = "parsed", reason: str | None = None) -> InputUnit`;
  - `claim(unit_id: str, n: int = 0, *, source: str | None = None) -> Claim`, a fixed
    valid claim (place `iso:SE`, legislature, day 2026-09-13).

**Invariants `check` enforces** (spec §9.1; Plan 1 C20; requirement a):
1. `raw.source == result.source`, and every unit and claim has that source.
2. Unit IDs are unique; claim IDs are unique.
3. **Coverage matches the pages:**
   - there is one coverage entry per `RawPage` (by key) and one per unfinished request;
   - every unit's ID starts with the `unit_prefix` of exactly one `ok`/`valid_empty` entry;
   - that entry's `units_seen` equals its unit count;
   - pages with any other outcome have no units.
4. **Cross-count:** for each `ok`/`valid_empty` entry, `cross_count(rule, page body)` equals
   `units_seen`. Otherwise `discovery_mismatch`; `None` counts as a mismatch.
5. Every claim's `unit_id` names a unit of this result whose outcome is `parsed` or `partial`.
6. Every `parsed` unit has at least one claim.
7. Ignored units carry an allowlisted reason. `InputUnit` checks this already; re-check it,
   because Plan 4 loads saved units.

- [ ] **Step 1: Write the failing tests**

```python
def test_cross_count_table_rows() -> None:
    html = (b'<table id="electionsTable"><thead><tr><th>x</th></tr></thead><tbody>'
            b'<tr><td><table><tbody><tr><td>n</td></tr><tr><td>n</td></tr></tbody></table></td></tr>'
            b'<tr><td>b</td></tr><tr><td>c</td></tr></tbody></table><table id="other"><tbody><tr><td/></tr></tbody></table>')
    assert cross_count(TableRowsRule("electionsTable"), html) == 3

def test_cross_count_section_items() -> None:
    text = ('<div class="mw-parser-output"><ul><li>lead</li></ul><div class="mw-heading"><h2 id="January">J</h2></div>'
            '<ul><li>a<ul><li>b</li></ul></li></ul><h2 id="References">R</h2><ol><li>r</li></ol></div>')
    rule = SectionItemsRule(frozenset({"References"}), ("parse", "text"))
    assert cross_count(rule, json.dumps({"parse": {"text": text}}).encode()) == 2
    for body in (b"not json", b"[]", b"null", b'{"parse": []}', b'{"parse": {"text": 5}}'):
        assert cross_count(rule, body) is None

def test_cross_count_of_the_fixtures() -> None:
    eg = {"upcoming.html": 45, "past.html": 200, "anticipated.html": 106}
    assert {n: cross_count(TableRowsRule("electionsTable"), fixture("electionguide", n)) for n in eg} == eg
    wiki = {"national-2026.json": 108, "local-2026.json": 457, "national-2027.json": 46, "local-2027.json": 53}
    rule = SectionItemsRule(WIKI_STOP, ("parse", "text"))   # WIKI_STOP: the nine P1 ids
    assert {n: cross_count(rule, fixture("wikipedia", n)) for n in wiki} == wiki

def test_a_balanced_result_passes() -> None:
    # page "v" with 4 rows; units r1 parsed + 1 claim, r2 partial + 1 claim, r3 unparsed (relevance unknown), r4 ignored duplicate
    report = check(raw, result)
    assert report.ok and report.reasons == ()
    assert report.outcomes == {"parsed": 1, "partial": 1, "unparsed": 1, "ignored": 1}
    assert report.ignored_reasons == {"duplicate": 1}
    assert report.relevance == {"in_or_after_window": 1, "unknown": 1, "before_window": 0}

def test_every_parsed_unit_has_a_claim() -> None:          # requirement (a)
    assert [r.code for r in check(raw, result_with_parsed_r1_and_no_claims).reasons] == ["ledger_mismatch"]

def test_claims_must_name_a_parsed_or_partial_unit_of_the_result() -> None:
    # one case each: a claim on r3 (unparsed), on r9 (no such unit), a duplicate claim id,
    # a claim of another source: each gives exactly ["ledger_mismatch"]

def test_unit_accounting_problems_are_ledger_mismatches() -> None:
    # one case each: a duplicate unit id; a unit outside every unit_prefix; units_seen != unit count;
    # a unit on a "timeout" page; a RawPage with no coverage entry; an unfinished request with none

def test_a_count_mismatch_is_a_discovery_mismatch() -> None:
    # page body has 5 rows, coverage and units say 4
    assert [r.code for r in check(raw, result).reasons] == ["discovery_mismatch"]
```

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/unit/test_ledger.py -q`.
  Expected: FAIL on import.
- [ ] **Step 3: Implement.** In `importlinter.ini`, change `(ledger)` to `ledger`.
- [ ] **Step 4:** Run the gates and the mutation table. Then commit:
  `feat(ledger): unit accounting invariants and an independent stdlib cross-count`.

### Task 6: ElectionGuide adapter

**Files:**
- Create: `elections_calendar/sources/electionguide.py`, `tests/adapters/__init__.py`
- Test: `tests/adapters/test_electionguide.py`

**Interfaces:**
- Consumes:
  - Task 4's contract, `fetch_pages` and `page_failure`; Task 5's `check` (tests);
  - `dates.parse_date_text`, `dates.make_range`, `dates.plausible`, `dates.relevance`;
  - `offices.classify` and `offices.resolve_level`; `Registries`.
- Produces:
  - `class ElectionGuide`, with `source = "electionguide"`;
  - `VIEWS = ("upcoming", "past", "anticipated")`;
  - `requests(window)`: one `PageRequest(view, f"https://www.electionguide.org/elections/type/{view}/")`
    per view, in that order;
  - `fetch = fetch_pages(self.requests(window), ...)`;
  - `parse`.

**Rules:**
- **Pages:** handle them in `VIEWS` order. `page_failure` decides first.
- **Layout:** recognised when all of these hold:
  - the decoded body (`result.text()`), stripped, ends with `</html>` (case-insensitive);
  - it has `table#electionsTable`;
  - its `thead th` texts (`collapse_ws` + casefold) include "country", "election for",
    "start date" and "end date".

  Otherwise `layout_not_recognised`. "status" is mapped too when present.
- **Units:** every `tr` that is a direct child of a `tbody` that is a direct child of the
  table. Zero rows means `valid_empty`. Coverage is `PageCoverage(view, None, outcome,
  f"electionguide:{view}/", n, rule=TableRowsRule("electionsTable"))`.
- **Unit text:** the collapsed text of each cell, empty cells dropped, joined by `" | "`.
  Relevance is `relevance(text, window.start)`.
- **Short rows:** a row needs a cell for every mapped column. Otherwise it is unparsed
  `too_few_cells`.
- **Event:** the first `a[href]` in the "election for" cell matching `/elections/id/(\d+)/`.
  - Event `N`: `source_event_id = f"electionguide:{N}"` and
    `link = f"https://www.electionguide.org/elections/id/{N}/"`.
  - No event link: `source_event_id = None` and `link` = the view's request URL.
  - The office label is the event link's collapsed text, or the cell's when there is no event
    link.
- **Duplicates:** an event ID carried by an earlier unit, in an earlier view or earlier in the
  same view, is ignored `duplicate`, whatever that earlier unit's outcome. A `too_few_cells` row
  carries no event ID.
- **Check order:** `too_few_cells`, `duplicate`, `place_missing`, then the date reasons. A row
  that passes them all is partial `place_unregistered` when its place is unregistered, else
  parsed.
- **Country:** the "country" cell text goes through `places.resolve`.
  - `None` → unparsed `place_missing` (P10).
  - Unregistered → partial `place_unregistered`. The claim is kept, with place
    `unknown:<key>`.
- **Dates:** parse the start and end cells with `parse_date_text`. Reasons, checked in this
  order:
  - `ok` with no spans → unparsed `date_missing`;
  - not `ok`, more than one span, or not day precision → unparsed `date_unparsed`;
  - `make_range` raises `RecordError` → unparsed `end_before_start`;
  - not `plausible(span, window.today)` → unparsed `implausible_date`.
  - `date_text = f"{start cell} to {end cell}"`, using the collapsed cell texts.
- **date_status:**
  - `tentative` if either cell is tentative, or the status cell (casefolded) is
    "date not confirmed";
  - `confirmed` if both cells are confirmed and the status cell is absent or "confirmed";
  - else `unknown`.
- **Claim:**
  - one per parsed or partial unit, `claim_id = unit_id + "#0"`;
  - `classify(label, place_id, "nationwide", institutions)`;
  - `level = resolve_level("national", [office.level_hint])`;
  - `jurisdiction=None`, `jurisdiction_kind="nationwide"`;
  - `date_meaning="voting_period"`;
  - `status_claim="held"` on past rows, else `None`;
  - `previous_date_text=None`, `evidence_kind="calendar"`, `indirect=False`;
  - `kind`, `round` and `aggregate` from the office.
- **Coverage gap:** when the past page is `ok`, and either it has no parsed unit or its oldest
  parsed start is on or after `window.start`, add the note
  `Reason("coverage_gap", f"past list starts {oldest or 'empty'}")`. The fixture's oldest start
  is 2024-11-24, so there is no note.

`WINDOW = window_for(datetime(2026, 10, 16, tzinfo=UTC))` in every adapter test.
`ALL = raw_pages("electionguide", [(r, result(fixture("electionguide", f"{r.key}.html"), url=r.url)) for r in ElectionGuide().requests(WINDOW)])`.

- [ ] **Step 1: Write the failing tests**

```python
def test_requests_are_the_three_views() -> None:
    assert [(r.key, r.url, r.mediawiki) for r in ElectionGuide().requests(WINDOW)] == [
        ("upcoming", "https://www.electionguide.org/elections/type/upcoming/", False),
        ("past", "https://www.electionguide.org/elections/type/past/", False),
        ("anticipated", "https://www.electionguide.org/elections/type/anticipated/", False)]

def test_fixture_ledger_balances() -> None:
    res = ElectionGuide().parse(ALL, WINDOW, REGISTRIES)
    report = check(ALL, res)
    assert report.ok and res.reasons == ()
    assert report.outcomes == {"parsed": 243, "partial": 0, "unparsed": 2, "ignored": 106}
    assert [(c.key, c.outcome, c.units_seen) for c in res.coverage] == [
        ("upcoming", "ok", 45), ("past", "ok", 200), ("anticipated", "ok", 106)]
    assert len(res.claims) == 243

def test_view_values() -> None:
    by_view = lambda v: [c for c in res.claims if c.unit_id.startswith(f"electionguide:{v}/")]
    assert Counter(c.date_status for c in by_view("upcoming")) == {"confirmed": 28, "tentative": 17}
    assert Counter(c.date_status for c in by_view("past")) == {"confirmed": 187, "tentative": 11}
    assert {c.status_claim for c in by_view("past")} == {"held"} and {c.status_claim for c in by_view("upcoming")} == {None}
    assert Counter(c.level for c in by_view("upcoming")) == {"national": 42, "subnational": 3}
    assert Counter(c.level for c in by_view("past")) == {"national": 196, "subnational": 2}
    assert Counter((c.office_class, c.aggregate) for c in by_view("upcoming")) == {
        ("governor", False): 3, ("head_of_state", False): 11, ("legislature", False): 12, ("legislature", True): 1,
        ("lower_house", False): 8, ("referendum", False): 3, ("upper_house", False): 7}
    assert Counter((c.office_class, c.aggregate) for c in by_view("past")) == {
        ("general", True): 2, ("head_of_state", False): 48, ("legislature", False): 59, ("legislature", True): 6,
        ("local_council", True): 1, ("lower_house", False): 41, ("referendum", False): 27, ("upper_house", False): 14}

@pytest.mark.parametrize(("claim_id", "event", "place", "office_class", "institution", "start", "end", "status"), [
    ("electionguide:upcoming/r1#0", "5259", "iso:CZ", "upper_house", "iso:CZ/senate", "2026-10-16", "2026-10-17", "confirmed"),
    ("electionguide:upcoming/r2#0", "5252", "iso:RS", "legislature", "iso:RS/national-assembly", "2026-10-25", "2026-10-25", "confirmed"),
    ("electionguide:upcoming/r3#0", "5254", "iso:BR", "head_of_state", "iso:BR/president", "2026-10-25", "2026-10-25", "confirmed"),
    ("electionguide:upcoming/r45#0", "5250", "iso:FR", "head_of_state", "iso:FR/president", "2027-04-18", "2027-04-18", "tentative"),
    ("electionguide:past/r3#0", "5089", "iso:BR", "upper_house", "iso:BR/federal-senate", "2026-10-04", "2026-10-04", "confirmed"),
    ("electionguide:past/r4#0", "5091", "iso:BR", "head_of_state", "iso:BR/president", "2026-10-04", "2026-10-04", "confirmed"),
    ("electionguide:past/r7#0", "5090", "iso:BR", "lower_house", "iso:BR/chamber-of-deputies", "2026-10-04", "2026-10-04", "confirmed"),
    ("electionguide:past/r11#0", "5083", "iso:MA", "lower_house", "iso:MA/house-of-representatives", "2026-09-23", "2026-09-23", "confirmed"),
    ("electionguide:past/r12#0", "5084", "iso:RU", "lower_house", "iso:RU/state-duma", "2026-09-18", "2026-09-20", "confirmed"),
    ("electionguide:past/r13#0", "5079", "iso:SE", "legislature", "iso:SE/parliament", "2026-09-13", "2026-09-13", "confirmed"),
])
def test_appendix_b_rows(claim_id, event, place, office_class, institution, start, end, status) -> None: ...
    # also: the claim's link == f"https://www.electionguide.org/elections/id/{event}/"

def test_one_claim_field_by_field() -> None:
    c = claims["electionguide:upcoming/r2#0"]
    assert (c.place_raw, c.office_label, c.date_text, c.span, c.level, c.jurisdiction, c.jurisdiction_kind,
            c.kind, c.round, c.date_meaning, c.evidence_kind, c.indirect, c.status_claim, c.fetched_at) == (
        "Serbia", "Serbian National Assembly", "2026-10-25 (d) to 2026-10-25 (d)", DateSpan.day(date(2026, 10, 25)),
        "national", None, "nationwide", "candidate_election", None, "voting_period", "calendar", False, None, None)
    assert units["electionguide:upcoming/r2"].text == "Serbia | Serbian National Assembly | 2026-10-25 (d) | 2026-10-25 (d) | Confirmed | Yes"
    # the Guam Governor (upcoming/r8) is governor, subnational; the U.S. Virgin Islands Legislature
    # (upcoming/r15) is a legislature aggregate with no institution, national

def test_links_never_come_from_the_final_url() -> None:   # requirement (b)
    # ALL with every result's final_url="https://evil.test/x": every link starts with
    # "https://www.electionguide.org/elections/id/"

def test_anticipated_rows_seen_earlier_are_duplicates() -> None:
    anticipated = [u for u in res.units if u.unit_id.startswith("electionguide:anticipated/")]
    assert {(u.outcome, u.reason) for u in anticipated} == {("ignored", "duplicate")} and len(anticipated) == 106

def test_a_failed_view_does_not_hide_its_events_elsewhere() -> None:
    # upcoming: result(b"", outcome="timeout", status=None); past and anticipated from the fixtures
    assert [(c.key, c.outcome, c.units_seen) for c in res.coverage][0] == ("upcoming", "timeout", 0)
    assert Counter((u.outcome, u.reason) for u in anticipated) == {("parsed", None): 33, ("ignored", "duplicate"): 73}
    assert Reason("timeout", "upcoming") in res.reasons and check(raw, res).ok

def test_reversed_ranges_are_unparsed() -> None:
    for uid, country in (("electionguide:past/r126", "Seychelles"), ("electionguide:past/r176", "Bermuda")):
        assert (units[uid].outcome, units[uid].reason) == ("unparsed", "end_before_start") and country in units[uid].text

@pytest.mark.parametrize(("change", "outcome"), [
    (lambda b: b.replace(b'id="electionsTable"', b'id="elections"'), "layout_not_recognised"),
    (lambda b: b.replace(b"Election for", b"Contest", 1), "layout_not_recognised"),
    (lambda b: b[: len(b) // 2], "layout_not_recognised"),
    (lambda b: b"", "layout_not_recognised"),
    (lambda b: b"\xff\xfe\x00garbage", "layout_not_recognised"),
    (empty_tbody, "valid_empty"),          # helper: removes every <tr> inside the table's tbody
])
def test_broken_pages_get_an_outcome_never_units(change, outcome) -> None:
    # upcoming body changed, past + anticipated untouched: upcoming's coverage outcome is `outcome`,
    # no unit id starts with "electionguide:upcoming/", check(raw, res).ok, no exception;
    # plus: result(b"", status=302) -> "http_error" and result(..., outcome="challenge_page") -> "challenge_page"

def test_a_short_row_is_a_discovered_unparsed_unit() -> None:   # NM-T01
    # remove the last two <td> of upcoming's 5th row: 45 upcoming units, r5 unparsed too_few_cells, ledger ok

def test_status_cells_and_markers_combine() -> None:
    # synthetic one-view pages (eg_page(headers, rows) helper in this file):
    # ("(d)", "(d)", "Confirmed") -> confirmed; ("(d)", "(d)", "Date not confirmed") -> tentative;
    # ("(t)", "(d)", "Confirmed") -> tentative; ("(d)", "(d)", no status column) -> confirmed;
    # ("(d)", "(d)", "Postponed") -> unknown

def test_places_that_do_not_resolve() -> None:
    # country "Atlantis": partial place_unregistered, claim place_id "unknown:atlantis";
    # country "": unparsed place_missing, no claim

def test_missing_and_implausible_dates_are_unparsed() -> None:
    # start "" -> date_missing; start "soon" -> date_unparsed; 2040-01-01 both cells -> implausible_date

def test_coverage_gap_when_the_past_list_starts_inside_the_window() -> None:
    # a past page holding only rows dated 2026-09-02 or later -> Reason("coverage_gap", "past list starts 2026-09-02") in res.reasons
```

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/adapters/test_electionguide.py -q`.
  Expected: FAIL on import.
- [ ] **Step 3: Implement.** When a count differs, diff against `.scratch/plan2/full_eg.txt`.
- [ ] **Step 4:** Run the gates and the mutation table. Then commit:
  `feat(sources): ElectionGuide adapter on the 2026-10-16 views`.

### Task 7: Wikipedia adapter, page machinery and the national calendars

**Files:**
- Create: `elections_calendar/sources/wikipedia.py`
- Modify: `importlinter.ini`. Add a second contract:
  `[importlinter:contract:adapters]`, `name = Adapters are independent (spec §4)`,
  `type = independence`, `modules = elections_calendar.sources.electionguide`,
  `elections_calendar.sources.wikipedia`.
- Test: `tests/adapters/test_wikipedia_national.py`

**Interfaces:**
- Consumes:
  - Task 4's contract; `Registries`;
  - `dates.parse_date_text`, `plausible` and `relevance`; `DateSpan.month` and `DateSpan.of_year`;
  - `offices.classify`, `split_offices`, `resolve_level`, `office_class_of` (Task 3).
- Produces:
  - `class Wikipedia`, with `source = "wikipedia"` and `KINDS = ("national", "local")`;
  - `STOP_IDS: frozenset[str]`, the nine P1 ids;
  - `requests(window)`: for each kind, then each `window.years` year,
    `PageRequest(f"{kind}-{year}", f"https://en.wikipedia.org/w/api.php?action=parse&page={year}_{kind}_electoral_calendar&prop=text%7Crevid&format=json&formatversion=2&maxlag=5", year, mediawiki=True)`;
  - `fetch` through `fetch_pages`;
  - `parse`.

**Page rules:**
- **Download:**
  - `page_failure` first. Then year rollover (§7): a page that is `api_error` with
    `api_code == "missingtitle"`, or `http_error` with status 404, is
    `not_published_yet` when its year is after `window.today.year`, else
    `required_year_missing`.
  - Every other failure keeps its outcome.
- **Layout:** recognised when all of these hold, else `layout_not_recognised`. This fulfils
  requirement d.
  - `json.loads(result.text())` is a dict;
  - its `"parse"` is a dict with `"text"` a str and `"revid"` an int;
  - the HTML (lxml) has `div.mw-parser-output`;
  - at least one section heading's id is an English month name.
- **Sections:**
  - Walk the children of `div.mw-parser-output`. A heading is an `h2`, or a `div.mw-heading`
    that contains an `h2`.
  - A section is the elements after a heading, up to the next one. Its key is the `h2` id.
  - Sections whose id is in `STOP_IDS` are skipped, and so is anything before the first heading.
- **Units (P1):**
  - Every `li` inside a section's elements, at any depth.
  - The top level is the section's `li`s with no ancestor `li` in that section. The children
    of an `li` are the section's `li`s whose nearest ancestor `li` is that one.
  - IDs: `wikipedia:{kind}-{year}@rev{revid}/{section}/li[i]`, then `/li[j]` for each nesting
    level, all 1-based.
  - Coverage is `PageCoverage(key, year, outcome, f"wikipedia:{key}@rev{revid}/", n, revid, SectionItemsRule(STOP_IDS, ("parse", "text")))`.
  - Zero units with the layout recognised means `valid_empty`.
- **Own text of an `li`:**
  - Take its text nodes (comments excluded), skipping nested `ul`/`ol`, `sup`, `style` and
    `link` elements.
  - An `a.extiw` interlanguage link is dropped together with its surrounding brackets
    (`" [es]"`).
  - Collapse whitespace, then strip spaces and a trailing ",".
  - The first link is the first `a` met in that walk that is not `a.extiw`. Its text is
    collapsed too.
- **Unit text:** the own texts of the ancestors and of the unit, joined by `" > "`. Relevance
  is `relevance(f"{date_text} {unit text}", window.start, default_year=year)`.
- **Date prefix:**
  - For each separator `":"`, then `","`, that the own text contains, take the head: the
    stripped text before its first occurrence.
  - The head is the prefix when it contains a digit or is an English month name, and
    `parse_date_text(head, default_year=year)` is `ok` with at least one span. The first
    separator that gives a prefix wins. The item text is what follows it, stripped.
  - When there is no prefix and the head of the first separator present contains an English
    month name as a word, the unit is unparsed `date_unparsed`. There are none in the fixtures.
- **Spans and their fields:**
  - With a prefix, the spans are its spans, duplicates dropped in order (L82).
    `date_text` = the head; `date_status`, `status_claim` and `previous_date_text` come from
    the parse.
  - With no prefix, the item inherits the nearest ancestor's spans and date fields.
  - With no ancestor either:
    - a month section gives `DateSpan.month(year, m)` with `date_text` = the month name;
    - any other section gives `DateSpan.of_year(year)` with `date_text` = the section id with
      "_" as " ";
    - in both cases `date_status="unknown"` and no status claim.
  - A span that is not `plausible(span, window.today)` makes the unit unparsed
    `implausible_date`.
- **Tokens:** split the item text at top level (not inside parentheses) on `", "` and `": "`.
  Strip " ,:" from each token and drop empty ones.
- **Country.** In this task every item resolves its own country; Task 8 adds inheritance. On
  the national fixtures the two give the same values, because every national container is
  date-only.
  - If the first link's text starts the item text, the country text is that link text
    ("Punjab, India" keeps its comma) and the tokens are re-split from the text after it.
  - Otherwise the country text is the first token, which is used up.
  - `place = places.resolve(country text)`.
  - With no country text: an item with children is ignored `container_item`; otherwise
    unparsed `place_missing`.
  - An unregistered place gives a partial `place_unregistered` unit; its claims are kept.
- **Offices (this task):**
  - The remaining tokens, joined by ", ", are the office text.
  - No tokens left: an item with children is ignored `container_item`; a leaf is unparsed
    `office_missing`.
  - Parts are `split_offices(office text, place_id, institutions)`. Each part is classified
    with `classify(part, place_id, "nationwide", institutions)`, and its level is
    `resolve_level(default, [office.level_hint])`. The default is `national` for national pages
    and `subnational` for local pages.
- **Claims:**
  - One per (part, span), part-major, numbered from `#0`.
  - `link = f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}#{section}"`.
  - `source_event_id=None`, `place_raw` = the country text, `jurisdiction=None`,
    `jurisdiction_kind="nationwide"`.
  - `date_meaning="voting_period"`, `evidence_kind="calendar"`,
    `indirect = (section == "Indirect_elections")`.
  - `kind`, `round` and `aggregate` from the office.

`NATIONAL = raw_pages("wikipedia", [(r, result(fixture("wikipedia", f"{r.key}.json"), url=r.url, content_type="application/json; charset=utf-8")) for r in Wikipedia().requests(WINDOW) if r.key.startswith("national-")])`.

- [ ] **Step 1: Write the failing tests**

```python
def test_requests_cover_both_kinds_for_every_window_year() -> None:
    reqs = Wikipedia().requests(WINDOW)
    assert [(r.key, r.year, r.mediawiki) for r in reqs] == [
        ("national-2026", 2026, True), ("national-2027", 2027, True), ("local-2026", 2026, True), ("local-2027", 2027, True)]
    assert reqs[0].url == ("https://en.wikipedia.org/w/api.php?action=parse&page=2026_national_electoral_calendar"
                           "&prop=text%7Crevid&format=json&formatversion=2&maxlag=5")

def test_national_fixture_ledger_balances() -> None:
    res = Wikipedia().parse(NATIONAL, WINDOW, REGISTRIES)
    assert check(NATIONAL, res).ok and res.reasons == ()
    assert [(c.key, c.outcome, c.units_seen, c.revid, c.unit_prefix) for c in res.coverage] == [
        ("national-2026", "ok", 108, 1380221397, "wikipedia:national-2026@rev1380221397/"),
        ("national-2027", "ok", 46, 1379360216, "wikipedia:national-2027@rev1379360216/")]
    # per page: national-2026 = 97 parsed + 11 ignored container_item, 114 claims;
    #           national-2027 = 44 parsed + 2 ignored container_item, 56 claims; no partial or unparsed unit

def test_national_claim_classes() -> None:
    assert per_page_counter("national-2026", lambda c: (c.office_class, c.level)) == {
        ("general", "national"): 2, ("head_of_state", "national"): 33, ("legislature", "national"): 35,
        ("lower_house", "national"): 18, ("referendum", "national"): 14, ("upper_house", "national"): 12}
    assert per_page_counter("national-2027", lambda c: (c.office_class, c.level)) == {
        ("head_of_state", "national"): 15, ("legislature", "national"): 27, ("lower_house", "national"): 7,
        ("upper_house", "national"): 7}
    assert {c.jurisdiction_kind for c in res.claims} == {"nationwide"}

P = "wikipedia:national-2026@rev1380221397/"
@pytest.mark.parametrize(("claim_id", "place", "label", "office_class", "institution", "rnd", "start", "end"), [
    (P + "September/li[1]#0", "iso:SE", "Parliament", "legislature", "iso:SE/parliament", None, "2026-09-13", "2026-09-13"),
    (P + "September/li[2]#0", "x:south-ossetia", "President", "head_of_state", "x:south-ossetia/president", None, "2026-09-18", "2026-09-18"),
    (P + "September/li[3]#0", "iso:RU", "State Duma", "lower_house", "iso:RU/state-duma", None, "2026-09-18", "2026-09-20"),
    (P + "September/li[4]#0", "iso:MA", "House of Representatives", "lower_house", "iso:MA/house-of-representatives", None, "2026-09-23", "2026-09-23"),
    (P + "September/li[5]#0", "iso:IM", "House of Keys", "lower_house", "iso:IM/house-of-keys", None, "2026-09-24", "2026-09-24"),
    (P + "September/li[6]/li[1]#0", "iso:ST", "Parliament", "legislature", "iso:ST/national-assembly", None, "2026-09-27", "2026-09-27"),
    (P + "October/li[2]/li[2]#0", "iso:BR", "President (1st round)", "head_of_state", "iso:BR/president", 1, "2026-10-04", "2026-10-04"),
    (P + "October/li[2]/li[2]#1", "iso:BR", "Chamber of Deputies", "lower_house", "iso:BR/chamber-of-deputies", None, "2026-10-04", "2026-10-04"),
    (P + "October/li[2]/li[2]#2", "iso:BR", "Senate", "upper_house", "iso:BR/federal-senate", None, "2026-10-04", "2026-10-04"),
    (P + "October/li[6]/li[3]#0", "iso:BR", "President (2nd round)", "head_of_state", "iso:BR/president", 2, "2026-10-25", "2026-10-25"),
    (P + "November/li[2]#0", "iso:GD", "Parliament", "legislature", None, None, "2026-11-05", "2026-11-05"),
    (P + "November/li[3]#0", "iso:NZ", "Parliament", "legislature", "iso:NZ/house-of-representatives", None, "2026-11-07", "2026-11-07"),
    (P + "November/li[4]#0", "iso:CV", "President", "head_of_state", "iso:CV/president", None, "2026-11-15", "2026-11-15"),
    (P + "November/li[5]/li[1]#0", "iso:ES", "Senate", "upper_house", "iso:ES/senate", None, "2026-11-29", "2026-11-29"),
    (P + "November/li[5]/li[1]#1", "iso:ES", "Congress of Deputies", "lower_house", "iso:ES/congress-of-deputies", None, "2026-11-29", "2026-11-29"),
    (P + "November/li[5]/li[2]#0", "iso:CH", "Referendums", "referendum", None, None, "2026-11-29", "2026-11-29"),
    (P + "Indirect_elections/li[2]#0", "iso:IN", "Council of States", "upper_house", "iso:IN/council-of-states", None, "2026-03-16", "2026-03-16"),
    (P + "Indirect_elections/li[2]#1", "iso:IN", "Council of States", "upper_house", "iso:IN/council-of-states", None, "2026-06-18", "2026-06-18"),
    (P + "Indirect_elections/li[2]#2", "iso:IN", "Council of States", "upper_house", "iso:IN/council-of-states", None, "2026-10-16", "2026-10-16"),
    (P + "Indirect_elections/li[14]#0", "iso:CH", "Federal Council", "general", None, None, "2026-12-09", "2026-12-09"),
])
def test_appendix_b_national_claims(...) -> None: ...
    # also: Grenada is aggregate (no institution); Indirect_elections claims have indirect=True, others False;
    # the Swiss referendum's kind is "referendum_day"

def test_one_national_claim_field_by_field() -> None:
    c = claims[P + "September/li[1]#0"]
    assert (c.link, c.place_raw, c.date_text, c.date_status, c.status_claim, c.source_event_id, c.level,
            c.kind, c.aggregate, c.evidence_kind, c.date_meaning) == (
        "https://en.wikipedia.org/wiki/2026_national_electoral_calendar#September", "Sweden", "13 September",
        "unknown", None, None, "national", "candidate_election", False, "calendar", "voting_period")

def test_undated_items_get_the_page_year() -> None:
    c = claims["wikipedia:national-2027@rev1379360216/Unknown_date/li[1]#0"]
    assert (c.place_id, c.office_class, c.aggregate, c.span, c.date_text) == (
        "iso:BH", "legislature", True, DateSpan.of_year(2027), "Unknown date")

def test_year_rollover() -> None:
    # national-2027 as result(b'{"error": {"code": "missingtitle"}}', outcome="api_error", api_code="missingtitle")
    #   -> coverage "not_published_yet", Reason("not_published_yet", "national-2027"); national-2026 still ok
    # the same for national-2026 -> "required_year_missing"
    # national-2027 as result(b"", outcome="http_error", status=404) -> "not_published_yet"

@pytest.mark.parametrize("body", [b"[]", b"null", b'{"parse": []}', b'{"parse": {"text": 5, "revid": 1}}',
    b'{"parse": {"text": "<div class=\\"mw-parser-output\\"><p>x</p></div>", "revid": 1}}', b"\xff{"])
def test_mediawiki_bodies_that_are_not_an_object_fail_the_layout_check(body: bytes) -> None:
    # national-2026 has this body -> its coverage outcome is "layout_not_recognised", no unit from it, ledger ok

def test_a_page_with_month_headings_and_no_items_is_valid_empty() -> None:
    # synthetic page: two month headings, a <p> each, no li -> "valid_empty", units_seen 0, ledger ok

def test_section_items_and_ids() -> None:
    # synthetic national-2026 page (helper wiki_page(sections: dict[str, str]) builds the parse JSON; revid 7):
    #   January:  <ul><li>5 January: <a>Sweden</a>, <a>Parliament</a></li>
    #             <li>11 January:<ul><li><a>Chile</a>, President (2nd round)</li><li><a>Fiji</a>, Parliament</li></ul></li></ul>
    #   Unknown_date: <ul><li><a>Fiji</a>, Parliament</li></ul>
    #   Indirect_elections: <ul><li>9 December: <a>Switzerland</a>, Federal Council</li></ul>
    #   References: <ol><li>a reference</li></ol>
    # -> unit ids /January/li[1], /January/li[2] (ignored container_item), /January/li[2]/li[1] and /li[2]
    #    (11 Jan 2026 each), /Unknown_date/li[1] (year 2026), /Indirect_elections/li[1] (indirect=True);
    #    no unit for the reference; ledger ok

def test_own_text_ignores_footnotes_and_interlanguage_links() -> None:
    # <li>5 January: <a>Sweden</a>, <a>Parliament</a><sup class="reference">[1]</sup> <span>[<a class="extiw">es</a>]</span></li>
    # -> one claim, office_label "Parliament", unit text "5 January: Sweden, Parliament"

def test_date_looking_text_that_does_not_parse_is_unparsed() -> None:
    # <li>31 September: <a>Sweden</a>, Parliament</li> -> unparsed date_unparsed, no claim

def test_identical_spans_give_one_claim() -> None:
    # <li>4, 4 October: <a>Sweden</a>, Parliament</li> -> exactly one claim
```

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/adapters/test_wikipedia_national.py -q`.
  Expected: FAIL on import.
- [ ] **Step 3: Implement.** When a count differs, diff against
  `.scratch/plan2/full_national-202{6,7}.txt`.
- [ ] **Step 4:** Run the gates (lint-imports: `Contracts: 2 kept`) and the mutation table. Then
  commit: `feat(sources): Wikipedia adapter, page machinery and national calendars`.

### Task 8: Wikipedia local calendars: jurisdictions, subdivisions, overrides, article titles

**Files:**
- Modify: `elections_calendar/sources/wikipedia.py`
- Test: `tests/adapters/test_wikipedia_local.py`

**Interfaces:**
- Consumes:
  - Task 7's adapter;
  - `SubdivisionIndex.find` (Task 2) and `PlaceRegistry.resolve_subdivision`;
  - `office_class_of` and `is_by_election` (Task 3);
  - `offices.institution_id` and `InstitutionRegistry.chambers`.
- Produces: no new public names. `parse` now applies the rules below on every page. The
  national pages' values from Task 7 must not change.

**Rules (they replace Task 7's "Country" and "Offices" steps; in order):**
1. **Inheritance:**
   - A nested item inherits from its nearest ancestor that has a place: the place, the place
     text and the jurisdiction tokens.
   - It never resolves its own first token as a country. Georgia under "United States" is
     the US state.
   - Task 7's country step runs only for items with no inherited place.
2. **Article titles (P12):** with no inherited place, when the first token matches
   `^\d{4}\s`, the unit is unparsed `article_title` with no claim.
3. **Registered subdivision (P4):**
   - The place must be registered, tokens must remain, and no jurisdiction token may be
     inherited.
   - If `places.resolve_subdivision(place_id, tokens[0])` finds a place, it becomes the place
     and the token is used up.
4. **Office token:** the first token for which `is_office(token)` holds. `is_office` is false
   when the token is a subdivision of the place (`subdivisions.find(place.country_code, token)`)
   or matches `PLACE_SUFFIX` (below, case-sensitive). Otherwise it is true when
   `office_class_of(token, place_id, institutions)` is not `None`, or when `ELECTION_WORD`
   (below, case-insensitive) matches.

   ```
   PLACE_SUFFIX = r"^(?:[A-Z][\w'’.-]*\s+)+(?:County|District|Region|Prefecture|Province|Parish|Borough)$"
   ELECTION_WORD = r"\b(?:by-?|special )?elections?\b"
   ```

   - The tokens before it are appended to the jurisdiction tokens.
   - The office text is that token and every one after it, joined by ", ".
5. **No office token:**
   - An item with children whose own new tokens are all subdivisions of the place (or that has
     none) is ignored `container_item`. Its tokens become jurisdiction tokens for its children.
   - Another item with children is unparsed `container_text`. There are none in the fixtures.
   - A leaf with inherited jurisdiction tokens, or with exactly one token, uses all its
     tokens, joined, as the office text.
   - A leaf with more than one token appends all but the last to the jurisdiction tokens; the
     last token is the office text.
   - A leaf with no token is unparsed `office_missing`.
6. **Jurisdiction:** the jurisdiction tokens, de-duplicated in order and joined by ", ", or
   `None`. Its kind is one of:
   - `nationwide` when there are no tokens;
   - `subdivision` when the first token is a `subdivisions.find` hit;
   - else `named`.

   Classify each part with that kind.
7. **Overrides (P17, Plan 1 "Plan 2, jurisdictions"),** applied after `classify`. Each sets
   `aggregate=False` and level hint `national`.
   - **Canada:** for place `iso:CA`, kind `named` and a part whose casefold is
     "federal by-election", set `lower_house`, `iso:CA/house-of-commons` and kind `by_election`.
   - **Congressional districts:** a part matching `\bcongressional district\b`
     (case-insensitive), where the place has exactly one active `lower_house` chamber, takes
     that chamber's `institution_id` and class `lower_house`. Its kind is `by_election` when
     `is_by_election(part)`, else `candidate_election`.

`LOCAL` is like `NATIONAL`, for the local pages; `ALL4` holds all four pages.

- [ ] **Step 1: Write the failing tests**

```python
L = "wikipedia:local-2026@rev1380378807/"

def test_local_fixture_ledger_balances() -> None:
    res = Wikipedia().parse(LOCAL, WINDOW, REGISTRIES)
    assert check(LOCAL, res).ok and res.reasons == ()
    # local-2026: 457 units = 360 parsed + 97 ignored container_item, 375 claims;
    #   its October section: 48 units (5 ignored), 44 claims (spec §13.2 "48 list items")
    # local-2027: 53 units = 5 parsed + 2 ignored container_item + 46 unparsed article_title, 5 claims
    assert per_page_counter("local-2026", lambda c: (c.office_class, c.level)) == {
        ("general", "subnational"): 32, ("governor", "subnational"): 71, ("head_of_state", "subnational"): 1,
        ("legislature", "national"): 13, ("legislature", "subnational"): 35, ("local_council", "subnational"): 73,
        ("lower_house", "national"): 30, ("lower_house", "subnational"): 43, ("mayor", "subnational"): 39,
        ("referendum", "subnational"): 18, ("upper_house", "national"): 2, ("upper_house", "subnational"): 18}
    assert per_page_counter("local-2027", lambda c: (c.office_class, c.level)) == {
        ("general", "subnational"): 2, ("governor", "subnational"): 1, ("local_council", "subnational"): 1,
        ("mayor", "subnational"): 1}

def test_national_values_are_unchanged() -> None:
    # Task 7's ledger and class counts hold on ALL4 too; ALL4: 664 units, 550 claims, ledger ok

@pytest.mark.parametrize(("claim_id", "place", "jurisdiction", "jkind", "label", "office_class", "institution", "level", "kind", "start", "end"), [
    (L + "September/li[4]/li[2]#0", "iso:SE", None, "nationwide", "regional and municipal elections", "local_council", None, "subnational", "aggregate", "2026-09-13", "2026-09-13"),
    (L + "September/li[4]/li[1]#0", "iso:DE", "Lower Saxony", "subdivision", "local elections", "local_council", None, "subnational", "aggregate", "2026-09-13", "2026-09-13"),
    (L + "October/li[1]/li[1]#0", "iso:BR", None, "nationwide", "Governors", "governor", None, "subnational", "aggregate", "2026-10-04", "2026-10-04"),
    (L + "October/li[1]/li[1]/li[6]#0", "iso:BR", "Federal District", "subdivision", "Governor", "governor", None, "subnational", "candidate_election", "2026-10-04", "2026-10-04"),
    (L + "October/li[1]/li[3]#0", "iso:PY", None, "nationwide", "municipal elections", "local_council", None, "subnational", "aggregate", "2026-10-04", "2026-10-04"),
    (L + "October/li[1]/li[4]#0", "iso:PE", None, "nationwide", "regional and municipal elections", "local_council", None, "subnational", "aggregate", "2026-10-04", "2026-10-04"),
    (L + "October/li[1]/li[4]/li[1]#0", "iso:PE", "Lima", "subdivision", "Mayor", "mayor", None, "subnational", "candidate_election", "2026-10-04", "2026-10-04"),
    (L + "October/li[3]/li[2]#0", "iso:GB", "Holborn and St Pancras", "named", "House of Commons by-election", "lower_house", "iso:GB/house-of-commons", "national", "by_election", "2026-10-08", "2026-10-08"),
    (L + "October/li[4]#0", "iso:CZ", None, "nationwide", "municipal elections", "local_council", None, "subnational", "aggregate", "2026-10-09", "2026-10-10"),
    (L + "October/li[9]/li[2]#0", "iso:SK", None, "nationwide", "regional and local elections", "local_council", None, "subnational", "aggregate", "2026-10-24", "2026-10-24"),
    (L + "September/li[5]/li[1]#0", "iso:PH", None, "nationwide", "Bangsamoro Parliament", "legislature", None, "subnational", "aggregate", "2026-09-14", "2026-09-14"),
])
def test_appendix_b_local_claims(...) -> None: ...

def test_the_brazil_governors_card_lists_every_state() -> None:
    kids = [c for c in res.claims if c.unit_id.startswith(L + "October/li[1]/li[1]/li[")]
    assert [c.jurisdiction for c in kids] == ["Alagoas", "Amazonas", "Bahia", "Ceará", "Espírito Santo", "Federal District",
        "Goiás", "Maranhão", "Minas Gerais", "Pará", "Paraíba", "Paraná", "Pernambuco", "Rio de Janeiro",
        "Rio Grande do Norte", "Rio Grande do Sul", "Santa Catarina", "São Paulo"]
    assert {(c.office_class, c.jurisdiction_kind, c.aggregate) for c in kids} == {("governor", "subdivision", False)}

def test_a_nested_item_never_re_resolves_its_country() -> None:
    c = claims[L + "May/li[11]/li[2]/li[2]#0"]     # 19 May: United States > Georgia > Court of Appeals
    assert (c.place_id, c.jurisdiction, c.jurisdiction_kind, c.office_label) == ("iso:US", "Georgia", "subdivision", "Court of Appeals")
    assert units[L + "May/li[11]/li[2]"].reason == "container_item"

def test_registered_subdivisions_become_the_place() -> None:     # P4; level as built (open question)
    assert fields(L + "May/li[4]/li[1]#0") == ("iso:GB-SCT", None, "nationwide", "legislature", "iso:GB-SCT/scottish-parliament", "national")
    assert fields(L + "May/li[4]/li[2]#0") == ("iso:GB-WLS", None, "nationwide", "legislature", "iso:GB-WLS/senedd", "national")

def test_jurisdictions_and_their_kinds() -> None:
    # (place, jurisdiction, kind, office_class, institution, level, kind):
    # L+"May/li[2]/li[2]/li[1]/li[1]#0": iso:US, "Texas", subdivision, upper_house, None, subnational, by_election  (L110)
    # L+"February/li[2]/li[2]/li[1]#0": iso:US, "New York", subdivision, legislature, None, subnational, by_election
    # L+"June/li[10]/li[1]#0": iso:AT, "Graz", named, local_council, None, subnational, candidate_election
    # L+"October/li[1]/li[2]/li[1]#0": iso:BA, "Federation of Bosnia and Herzegovina", subdivision, legislature, None, subnational

def test_adapter_overrides() -> None:
    # L+"April/li[6]/li[1]#0" Scarborough Southwest: iso:CA, named, "federal by-election" -> lower_house,
    #   iso:CA/house-of-commons, national, by_election, aggregate False
    # L+"July/li[8]#0" and L+"August/li[11]/li[1]#0": iso:US, "Georgia", subdivision,
    #   "Georgia's 13th congressional district, special election (1st round)" / "(2nd round)" -> lower_house,
    #   iso:US/house-of-representatives, national, by_election, round 1 / 2

def test_article_titles_are_unparsed_and_relevant() -> None:
    u = units["wikipedia:local-2027@rev1379495387/March/li[1]"]
    assert (u.outcome, u.reason, u.relevance, u.text) == (
        "unparsed", "article_title", "in_or_after_window", "7 March: 2027 Lithuanian municipal elections")
    assert not [c for c in res.claims if c.unit_id == u.unit_id]

def test_tokens_that_name_places_are_not_offices() -> None:
    # synthetic local-2026 page: <li>7 May: <a>United States</a>, Orange County, Board of Supervisors</li>
    # -> jurisdiction "Orange County", kind named, label "Board of Supervisors" (PLACE_SUFFIX keeps the county out)
```

- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/adapters -q`. Expected: the new
  tests FAIL and Task 7's still pass.
- [ ] **Step 3: Implement.** When a count differs, diff against
  `.scratch/plan2/full_local-202{6,7}.txt`.
- [ ] **Step 4:** Run the gates and the mutation table. Then commit:
  `feat(sources): Wikipedia local calendars with jurisdictions, subdivisions and overrides`.

### Task 9: Per-source runner under hard deadlines

**Files:**
- Modify (untracked): `.scratch/mutate.py`
- Create: `elections_calendar/runner.py`, `tests/support/slow_adapters.py`
- Modify: `elections_calendar/fetch.py`:
  - `TrustBundleError.variable`;
  - the docstrings that called the runner unbuilt now point at `runner.run_sources`.
- Modify: `tests/support/http_server.py` (`Reply.header_drip`), `importlinter.ini` (layer 4 becomes
  `(health) | (snapshots) | ledger | runner`), `README.md` (one paragraph: how a scrape is bounded)
- Test: `tests/unit/test_runner.py`, `tests/unit/test_fetch.py`

**Interfaces:**
- Consumes:
  - `fetch.Fetcher`, `Deadline`, `trust_bundle`, `TrustBundleError`, `redact_text`,
    `SOURCE_DEADLINE_S`, `SCRAPE_DEADLINE_S`;
  - Task 4's `Adapter`, `RawPage`, `RawPages`, `PageRequest`; `window.Window`.
- Produces in `fetch.py`:
  - `TrustBundleError(message, variable: str)`, with attribute `.variable`, e.g.
    `"REQUESTS_CA_BUNDLE"`;
  - the message is unchanged.
- Produces in `runner.py`:
  - `@dataclass(frozen=True, slots=True) class AdapterSpec`, with fields:
    - `source: str`;
    - `target: str`, as `"module:Class"`;
    - `options: tuple[tuple[str, str], ...] = ()`, keyword arguments for the class.
  - `DEFAULT_ADAPTERS = (AdapterSpec("electionguide", "elections_calendar.sources.electionguide:ElectionGuide"), AdapterSpec("wikipedia", "elections_calendar.sources.wikipedia:Wikipedia"))`.
  - `SourceOutcome = Literal["complete", "deadline", "scrape_deadline", "worker_failed"]`.
  - `@dataclass(frozen=True, slots=True) class SourceRun`, with fields:
    - `source: str`;
    - `raw: RawPages`, whose `unfinished` lists the requests not received;
    - `outcome: SourceOutcome`;
    - `elapsed_ms: int`;
    - `detail: str = ""`.
  - `@dataclass(frozen=True, slots=True) class ScrapeRun`, with fields `trust_sources: tuple[str, ...]`
    and `runs: tuple[SourceRun, ...]` (in spec order).
  - `run_sources(specs: Sequence[AdapterSpec], window: Window, *, workdir: Path, environ: Mapping[str, str] = os.environ, source_deadline_s: float = SOURCE_DEADLINE_S, scrape_deadline_s: float = SCRAPE_DEADLINE_S, parallel: int = 4, grace_s: float = 5.0) -> ScrapeRun`.

**Rules (C15's hard bound, Plan 1 "Plan 2, hard time bound"):**
1. **Trust bundle first.** `trust_bundle(workdir / "ca-bundle.pem", environ)` runs in the parent
   before any worker starts.
   - `TrustBundleError` propagates unchanged; requirement c is that the caller prints its
     message.
   - Only `bundle.sources` goes into `ScrapeRun`.
2. **Deadlines.** The scrape deadline starts when `run_sources` is called.
   - Workers start in spec order, at most `parallel` at once, using
     `multiprocessing.get_context("spawn")`.
   - A worker's deadline is the earlier of its own start + `source_deadline_s` and the scrape
     deadline. Its `Fetcher` gets the remaining seconds as its `Deadline`.
3. **The worker.**
   - It imports `target`, builds the adapter with `options`, and builds a `Fetcher` on the
     bundle path.
   - It sends `("page", RawPage)` over a `Pipe` for each page as soon as it has it, then
     `("done", None)`.
   - On an exception it prints the traceback to its stderr (the operator console) and sends
     `("error", type(exc).__name__)`. It never sends the message, which may carry a URL or a
     path.
4. **The parent.**
   - It waits with `multiprocessing.connection.wait` on the pipes and process sentinels, with a
     timeout until the nearest deadline. It reads every complete message as it arrives.
   - **At a worker's deadline:** stop reading, `terminate()`, `join(grace_s)`, then `kill()` and
     `join()` if it is still alive. The outcome is `scrape_deadline` when the scrape deadline is
     the one that passed, else `deadline`.
   - **Exits without "done":**
     - after an `"error"` message: `worker_failed` with the type name as `detail`;
     - an exit with no message, or a broken pipe: `worker_failed` with `detail = f"exit code {code}"`.
   - **A spec that never started before the scrape deadline:** `scrape_deadline`, no pages,
     `elapsed_ms = 0`.
   - **Nothing late:** pages already received are kept; nothing is read after a deadline.
5. **`raw.unfinished`** is the adapter's `requests(window)` whose keys were not received. The
   parent imports the class for this; `requests` is pure.
6. **No worker outlives `run_sources`,** whatever happens. Use `try/finally`.

- [ ] **Step 1: Fix the mutation helper (requirement e, L47) before any runner test exists.**
  - In `.scratch/mutate.py`, run pytest with `subprocess.Popen` and `communicate(timeout=TIMEOUT_S)`.
  - On `TimeoutExpired`, kill the whole tree: `taskkill /T /F /PID <pid>` on Windows; on POSIX,
    `os.killpg` with `start_new_session=True`. Then `communicate()`.
  - Let `MUTATE_TIMEOUT_S` override `TIMEOUT_S`.
  - Verify: with `MUTATE_TIMEOUT_S=5`, write a one-entry table whose test starts a child process
    that sleeps 60 s. The helper must report `TIMEOUT` within 20 s, and afterwards
    `powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object CommandLine -match 'sleep_probe' | Measure-Object | Select-Object -ExpandProperty Count"`
    prints `0`.
  - Delete the probe table and test afterwards.
- [ ] **Step 2: Write the failing tests.**
  - **The adapters.** `tests/support/slow_adapters.py` holds small adapters. Each takes its
    settings as string options and is built and run in the worker:
    - `Pages(urls)`: fetches the given test-server URLs; keys `one`, `two`, ...;
    - `SlowDns`: patches `socket.getaddrinfo` to sleep 30 s, then fetches `https://slow.test/`;
    - `FailingAddresses`: resolves to 4 addresses, each taking 1 s to fail;
    - `Sleeper(seconds, record)`: writes its start and end `time.time()` to a file, yields
      nothing;
    - `LatePage(seconds)`: sleeps, then yields one page;
    - `Raise`: raises `RuntimeError("https://x.test/?token=abc")`;
    - `Crash`: `os._exit(3)`.
  - **The server.** `Reply.header_drip: float = 0.0` is the time between single bytes of the
    status line and headers. The server writes them by hand when it is set.
  - **The autouse check.** `no_worker_outlives_the_test` asserts
    `multiprocessing.active_children() == []` after each test.

```python
def test_a_complete_source_returns_its_pages(server, ca_env, tmp_path) -> None:
    run = run_sources([spec("Pages", urls=f"{server.route('/a', Reply(body=b'a'))},{server.route('/b', Reply(body=b'b'))}")],
                      WINDOW, workdir=tmp_path, environ=ca_env)
    (r,) = run.runs
    assert (r.outcome, [p.request.key for p in r.raw.pages], r.raw.unfinished) == ("complete", ["one", "two"], ())
    assert run.trust_sources == ("certifi", "REQUESTS_CA_BUNDLE")

@pytest.mark.parametrize("adapter", ["SlowDns", "FailingAddresses", "DripHeaders"])
def test_a_blocked_worker_is_cut_at_the_source_deadline(adapter, server, ca_env, tmp_path) -> None:
    start = time.monotonic()
    (r,) = run_sources([spec(adapter, ...)], WINDOW, workdir=tmp_path, environ=ca_env, source_deadline_s=2, grace_s=2).runs
    assert r.outcome == "deadline" and r.raw.pages == () and len(r.raw.unfinished) == 1
    assert time.monotonic() - start < 2 + 2 + 3      # deadline + grace + spawn slack

def test_the_scrape_budget_ending_mid_source_keeps_finished_pages(server, ca_env, tmp_path) -> None:
    # Pages with /fast and /slow (Reply(delay=30)); scrape_deadline_s=2, source_deadline_s=30
    assert (r.outcome, [p.request.key for p in r.raw.pages], [q.key for q in r.raw.unfinished]) == (
        "scrape_deadline", ["one"], ["two"])

def test_sources_not_started_before_the_scrape_deadline_are_recorded(tmp_path, ca_env) -> None:
    # two Sleeper(5) specs, parallel=1, scrape_deadline_s=2 -> both "scrape_deadline"; the second has elapsed_ms 0

def test_nothing_arrives_after_the_deadline(tmp_path, ca_env) -> None:
    # LatePage(3) with source_deadline_s=1 -> "deadline", raw.pages == ()

def test_a_worker_that_raises_or_crashes_is_worker_failed(tmp_path, ca_env) -> None:
    runs = run_sources([spec("Raise"), spec("Crash")], WINDOW, workdir=tmp_path, environ=ca_env).runs
    assert [(r.outcome, r.detail) for r in runs] == [("worker_failed", "RuntimeError"), ("worker_failed", "exit code 3")]

def test_at_most_parallel_sources_run_at_once(tmp_path, ca_env) -> None:
    # six Sleeper(1) specs, parallel=4: all "complete"; the recorded intervals overlap at most 4 and at least 2 at once

def test_a_bad_trust_bundle_stops_before_any_worker_starts(tmp_path) -> None:
    with pytest.raises(TrustBundleError) as caught:
        run_sources([spec("Sleeper", seconds="0", record=str(tmp_path / "ran"))], WINDOW, workdir=tmp_path,
                    environ={"REQUESTS_CA_BUNDLE": str(tmp_path / "missing.pem")})
    assert caught.value.variable == "REQUESTS_CA_BUNDLE" and not (tmp_path / "ran").exists()
```

  In `tests/unit/test_fetch.py`, add `test_trust_bundle_error_names_its_variable`, using
  `SSL_CERT_FILE` → `.variable == "SSL_CERT_FILE"`.
- [ ] **Step 3: Run** `.venv/Scripts/python.exe -m pytest tests/unit/test_runner.py -q`.
  Expected: FAIL on import.
- [ ] **Step 4: Implement**, then run the file 3 times in a row. Expected: PASS every time, in
  under 60 s per run. A test that passes only sometimes is a bug: fix it with synchronisation,
  never with a longer sleep.
- [ ] **Step 5:** Run the gates and the mutation table (with the fixed helper). Then commit:
  `feat(runner): per-source worker processes under source and scrape deadlines`.

## Requirements for later plans

- **Plan 2b:**
  - Each adapter follows this contract and these Global Constraints, and gets a ledger-balance
    test on its fixtures.
  - Decide M6/M7/L70/L72/L81 from EISA and OSCE text.
  - `redact_url` must also cover path secrets such as A-WEB's `;jsessionid=` (L127d).
  - IPU renewals only for active chambers. Renewal evidence for a suspended or dissolved
    chamber gets an explicit outcome (Plan 1 "Plan 2, renewals").
  - EISA's JSON list needs a third count rule (the list length).
- **Plan 4:**
  - **Stored IDs (Plan 1 C9).** Snapshots store place and institution IDs. Define how
    registries are versioned before the first save, and how stored IDs are re-resolved when an
    `unknown:` name is registered or a chamber is renamed. Never a silent new identity.
  - **Loaders.** Snapshot loaders treat `RecordError`, a non-list or a missing key as a
    corrupt record, then run `ledger.check`'s admission rules on the loaded units and claims.
  - **Caps.** Published `final_url` and `error` are capped (L127d).
  - **Trust error.** `__main__` prints `TrustBundleError`'s message to the console and records
    only `.variable` and `ScrapeRun.trust_sources` (requirement c).
  - **Source outcomes as reasons:** `deadline`/`scrape_deadline` → `deadline`;
    `worker_failed` → `worker_failed`.
  - **Expected file.** The hand-written `tests/expected/2026-10-16.yaml` (§13.2) checks the
    Appendix B items and the October 2026 subnational entries field by field, against these
    adapters.
- **Open questions for the user** (rulings recorded; this plan builds the "as built" choice):
  - the level of chambers of registered subdivision places (the Scottish Parliament and Senedd
    are `national` here);
  - option B for article titles (P12).

## After Plan 2a

- **The branch:** 9 new commits on top of the commit that holds this plan, all gates green.
  Nothing has been pushed or merged.
- **Next:** Plan 2b is written against this code. It consumes the Interfaces blocks above.
