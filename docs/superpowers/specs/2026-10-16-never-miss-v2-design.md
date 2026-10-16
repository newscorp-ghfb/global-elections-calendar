# Global Elections Calendar v2 — "Never miss" design

| | |
|---|---|
| Date | 2026-10-16 |
| Status | All six design sections approved in conversation; this written spec awaits user review |
| Branch / worktree | `feat/never-miss-v2` at `.claude/worktrees/never-miss-v2`, based on `origin/main` `ff30417` (local `main` untouched at `9ad92a8`) |
| Red-team reviews incorporated | `Downloads/global-elections-section-{1,2,3,4,5}-red-team-review.md`, `Downloads/elections_section6_red_team_review.md` |
| Diagnostic evidence | `elections-calendar/.scratch/` (untracked): page snapshots of every source taken 2026-10-16, 182 historical feed snapshots, probe scripts |

Test IDs from the reviews are namespaced by section: `S1-T1`, `S2-T1`, `S3-T1`, `S4-T01`, `S5-T01`, `S6-RT-01`.

---

## 1. Problem (evidence, 2026-10-16)

The scraper (`scraper.py`, 7 sources, daily GitHub Action on `newscorp-ghfb/global-elections-calendar`) has missed elections that its sources clearly list.

**Root causes, each confirmed against today's pages:**

| # | Cause | Effect |
|---|---|---|
| 1 | OSCE/ODIHR table changed to 4 columns; the date cell's text is `25 Oct 2026Upcoming` | Every date fails to parse; country/type are read from the wrong cells; **0 records since 2026-04-22** |
| 2 | Carter Center no longer uses `<dt>/<dd>` | **0 records since 2026-04-22** |
| 3 | IPU parses locally, but yields nothing in CI; logs need repo admin (403) | **0 records since 2026-04-22**; cause unconfirmed |
| 4 | ElectionGuide homepage lists only the next 9 and last 9 elections | Everything else in the window is dropped |
| 5 | Date ranges (`18–20 September`, `02 Nov 2026 - 31 Jan 2027`) don't parse | Multi-day elections dropped |
| 6 | Failures are silent: `_get` returns `None`, unparseable rows are skipped, a source returning 0 is fine | `errors` has been `[]` in all 182 snapshots |
| 7 | Wikipedia: only the *local* calendar is scraped; on dates listing several countries, only the first becomes the country; the URL is hardcoded to 2026 | Sweden appears under "Germany", Slovakia under "Canada", UK Holborn under "Tonga" |
| 8 | EEAS stamps every mission of the year on the 1st of the current month | Fake dates (Colombia, Peru, Bangladesh, Zambia "1 Oct 2026") |

**Missed elections (Sep 2026 – Jan 2027) found in the sources:** see Appendix B. They include Sweden, Russia's Duma, Morocco, New Zealand, Brazil's presidential first round, Spain, and municipal elections in Paraguay, Peru, Czech Republic and Slovenia.

## 2. Goals, non-goals, success criteria

**Goals**

- **G1 No silent drops.** Every input unit a source exposes gets exactly one outcome: parsed, partial, unparsed, or ignored with a reason. Every relevant unresolved unit is visible to users.
- **G2 Visible failure.** Broken, blocked or degraded sources show up within one run: extension banner, `HEALTH.md`, red CI run.
- **G3 Scope = everything the sources list:** national, subnational, municipal, by-elections, referendums (decision D1).
- **G4 Window:** 1 month back, the current month, and 3 months ahead (D2).
- **G5 Backward compatibility:** installed v1.0.2 keeps working against the v2 feed, with documented limitations (§12).
- **G6 Sources:**
  - add Wikipedia national and local calendars (one page per year in the window), NDI and EISA;
  - use ElectionGuide's full lists and A-WEB's "all" view;
  - fix OSCE, IPU, Carter Center and EEAS.

**Non-goals**

- Persistent cross-run election identity, or "date changed" alerts (D6).
- Detecting elections that no source lists.
- Election results.
- A monitor independent of GitHub (D7).
- Automated Chrome Web Store publishing (the user uploads).
- Exporting/importing pins.

**Success criteria**

- **SC1.** An offline end-to-end run on the 2026-10-16 fixtures produces every contest in `tests/expected/2026-10-16.yaml`, including every Appendix B case.
- **SC2.** Every record in the 2026-10-16 production feed maps to exactly one v2 record. The only exceptions are in `tests/expected/legacy-mapping-exceptions.yaml`.
- **SC3.** Every acceptance test in §13 passes, and every gate in §14 is green locally and in CI.
- **SC4.** The real v1.0.2 extension files render the v2 feed (S1-T7 / S5-T17).
- **SC5.** First production run:
  - every source is `ok`, or `warning`/`error` with a reason that is acknowledged or tracked as an open item;
  - the user can open `HEALTH.md`;
  - the deterministic scheduled alert test (§15) reaches the user's inbox.

## 3. Decision log

| ID | Decision | Where decided |
|---|---|---|
| D1 | Scope option C: everything, including municipal and by-elections | Q1 |
| D2 | Window: 1 back + current + 3 ahead | Q2 |
| D3 | Alerts: extension banner + red CI run; data still published | Q3 |
| D4 | Architecture A: a package with one module per source | Q4 |
| D5 | Local entries: grouped cards with structured children | Section 2 |
| D6 | No persistent election/contest ID; IDs are deterministic per run | Section 1 (pushback F2), Section 3 (pushback F1) |
| D7 | Monitoring: the extension's freshness banner only | Section 4 |
| D8 | Install routes: Load unpacked from the ZIP, and the company Chrome Web Store listing (currently v1.0.2, updated May 2026) | Section 5 follow-up |
| D9 | Keep the user's rule: one mutation check per new test, restored via git. The mutation must break the behaviour the test checks | Section 6 |
| D10 | Read-only GETs of public source pages are routine development work. Every write or notify action (push, dispatch, Store upload, alert test) needs the user's go-ahead at the time | Section 6 |
| D11 | Python 3.14 locally and in CI, subject to the wheel check in plan task 1 | Section 6 |
| D12 | Work branches from `origin/main`; local `main` is not modified until the user approves a merge (the Desktop hook blocks merges into `main`) | Spec setup |

### 3.1 Changes from the approved sections (made while writing this spec; please confirm)

| ID | Change | Why |
|---|---|---|
| V1 | Scotland, Wales and Punjab (India) become subdivision places with their historical display names (§6.2). Section 3 required their pins to be redone | Their v1.0.2 pins (38, 39 and 45 historical records) keep working |
| V2 | `child_id` hashes claim IDs, not unit IDs (§5.3) | One Wikipedia line can produce several contests; unit IDs would collide |
| V3 | Month-precision claims have an `end_date` (last day of the end month), and matching uses interval overlap (§5.2, §5.9, §10.3) | Otherwise ranges like EISA "Nov 2026 – Jan 2027" lose their end |
| V4 | `status.json` on `main` records only `published` / `validation_failed`; `superseded` / `paused` show in the run artifact and summary (§5.8) | A superseded run can't push, and a paused run must not commit |
| V5 | `before_window` isn't a reason to ignore a unit; such units keep their outcome and are counted by relevance (§9.1) | The ledger outcome and relevance stay separate, as §5.5 already assumes |

## 4. Architecture

```
scraper.py                      thin entry point (keeps the workflow command shape)
elections_calendar/
  __main__.py                   CLI: --live | --offline DIR, --now ISO, --out DIR, --dry-run
  model.py                      dataclasses: InputUnit, Claim, Child, Card, AttentionItem, SourceHealth, ...
  window.py                     window months, requested years, month bucket rule
  dates.py                      civil-date grammar, ranges, precision, meaning
  places.py                     places.yaml loader, place_id resolution, display names
  offices.py                    institutions.yaml loader, office classes, aggregate labels
  fetch.py                      HTTP: retries, backoff, Retry-After, deadlines, TLS, diagnostics
  sources/
    base.py                     Adapter protocol + ledger helpers
    electionguide.py  wikipedia.py  ndi.py  osce.py  ipu.py
    aweb.py  eisa.py  carter.py  eeas.py
  ledger.py                     unit-outcome accounting checks
  snapshots.py                  baseline / candidate store, acceptance decisions
  health.py                     severity, reasons, acknowledgements, match diagnostic
  merge/
    identity.py  match.py  select.py  cards.py  conservation.py
  feed.py                       v2 feed + legacy projection, status.json, HEALTH.md
  validate.py                   JSON Schema, legacy contract, merge invariants
  publish.py                    generation id, atomic local writes
data/
  places.yaml  institutions.yaml
  certs/emsign-root-ca-g1.pem
  sources/<source>/baseline.json  candidate.json
schemas/feed-v2.schema.json  schemas/status-v1.schema.json
known_issues.yml
tests/  (fixtures/, expected/, unit/, adapters/, merge/, pipeline/, extension/)
extension/  (v2.0.0)
scripts/build_extension_zip.py  scripts/build_places.py
```

**Data flow:** fetch → adapter (input units → claims, plus a ledger) → acceptance decision (baseline vs candidate) → merge (claims → children → cards; attention items) → feed and status built → validation → publish.

**Layering (import-linter, `importlinter.ini`), top to bottom:**
1. `__main__`
2. `feed | publish | validate`
3. `merge`
4. `health | snapshots | ledger`
5. `sources`
6. `fetch | dates | places | offices | window`
7. `model`

`elections_calendar.sources.*` modules are independent of each other. `model` imports no other application layer; the stdlib, `typing` and `dataclasses` are allowed.

**Runtime dependencies:** `requests`, `beautifulsoup4`, `lxml`, `PyYAML`, `jsonschema`. Development: `pytest`, `pytest-playwright`, `playwright`, `hypothesis`, `mypy`, `ruff`, `import-linter`, `types-requests`, `types-PyYAML`, `pip-tools`, `pycountry` (used only by `scripts/build_places.py`).

## 5. Data model

### 5.1 Window and month buckets

- **Window:** the window months are `[M-1, M, M+1, M+2, M+3]`, where `M` is the month of the generation's UTC civil date `T`. The requested years are every calendar year touched by the window. For Oct 2026 that's Sep 2026–Jan 2027, so {2026, 2027}.
- **Bucket rule:** each card goes into exactly one month bucket.
  - A dated card (day or month precision) goes into its start month if that's in the window. Otherwise it goes into the first window month its interval overlaps.
  - Undated items are never bucketed.
- **Inclusion:** a card is in the window when its interval overlaps the window.

### 5.2 Source claim (one emitted record from an input unit)

| Field | Meaning |
|---|---|
| `claim_id` | `<unit_id>#<n>`; one unit may emit 0..N claims |
| `unit_id` | `<source>:<locator>`. Locator: the source event ID if one exists (`electionguide:5259`), otherwise page key + structural path (`wikipedia:national-2026@rev1380378807/September/li[3]/li[1]`) |
| `source` | Source key |
| `link` | Source URL for this claim |
| `source_event_id` | Publisher event ID, namespaced (`electionguide:5259`), or `null` |
| `place_raw`, `place_id` | Raw country text and resolved place (§6.2) |
| `jurisdiction`, `jurisdiction_kind` | Name or `null`; `nationwide` \| `named` \| `unknown` |
| `level` | `national` \| `subnational` \| `unknown` (§6.4) |
| `institution`, `office_class`, `office_label` | §6.3 |
| `kind` | `candidate_election` \| `by_election` \| `referendum_day` \| `referendum_question` \| `aggregate` |
| `round` | Integer, or `null` (not stated) |
| `date`, `end_date`, `date_precision`, `date_meaning`, `date_status` | §6.1. Every dated claim is an interval: `end_date` is the last day of the period. Month precision: `date` = 1st of the start month, `end_date` = last day of the end month (a single month ends on its own last day) |
| `date_text` | Original date text, verbatim |
| `status_claim` | `postponed` \| `cancelled` \| `disputed` \| `held` \| `null` (explicit source statement) |
| `previous_date_text` | For "Postponed from X": the X text |
| `evidence_kind` | `calendar` \| `expected_renewal` \| `observation` \| `umbrella` |
| `indirect` | `true` for indirect elections |
| `fetched_at`, `fallback`, `snapshot_id` | Provenance |

### 5.3 Child (one contest)

A child holds the resolved values plus all its claims.

| Field | Meaning |
|---|---|
| `child_id` | First 12 hex characters of SHA-1 over the sorted `claim_id`s of its anchor claims (all its claims if it has no anchors). Claim IDs, not unit IDs, because one unit can produce several contests. Deterministic per run |
| `place_id`, `country`, `country_code` | `country` is the display name from `places.yaml`; `country_code` is ISO 3166-1 alpha-2 or `null` |
| `jurisdiction`, `jurisdiction_kind`, `level`, `institution`, `office_class`, `office_label`, `kind`, `round`, `indirect` | Resolved (§10.5) |
| `date`, `end_date`, `date_precision`, `date_meaning`, `date_status` | Resolved (§10.5) |
| `status` | Legacy enum (§5.9) |
| `occurrence_confirmed` | `true` only when a claim for *this child* states it was held (ElectionGuide past list, EISA "Held …") |
| `status_conflict`, `date_conflict`, `unverified`, `ambiguous` | Flags (§10) |
| `possible_matches` | List of `child_id`s, provisional |
| `sources` | Its claims as `{name, link, source_event_id, date, end_date, date_text, fetched_at, fallback, evidence_kind, selected, rejected_reason}` |

### 5.4 Card (entry in `months[YYYY-MM]`; doubles as the legacy projection)

**Legacy fields** (types and meaning unchanged):

| Field | Value |
|---|---|
| `date` | Card start date. Month precision: `YYYY-MM-01` (documented limitation for v1.0.2) |
| `country` | Place display name |
| `type` | Summary (§10.7) |
| `status` | Card status (all children share it) |
| `sources` | A **bibliography**: one entry per source name across all children plus umbrella links, link = first claim from that source, ordered by source priority (§10.5). Extra keys are allowed in entries |
| `source_names`, `links` | Generated from `sources` |

**v2 fields:** `group_id` (SHA-1 of the card key, first 12 hex characters), `end_date`, `date_precision`, `date_meaning`, `date_status`, `level`, `place_id`, `country_code`, `children[]` (§5.3), `umbrella_sources[]` (same shape as `sources`).

### 5.5 Undated listings and attention items

- **`undated[]`** holds year-only calendar claims that didn't attach to exactly one contest: `{undated_id, place_id, country, office_label, year, sources[], possible_matches[]}`.
- **`attention_items[]`** is the **complete** list of relevant unresolved items in the data being served:

| Field | Meaning |
|---|---|
| `item_id` | Stable within the generation |
| `kind` | `unparsed_unit` \| `partial_unit` \| `undated_listing` (refers to an `undated_id`) \| `unresolved_evidence` |
| `source`, `link`, `snapshot_id` | Provenance |
| `relevance` | `in_or_after_window` \| `unknown` (only these are attention items; `before_window` units stay in the ledger) |
| `text` | Display text, at most 300 characters, sanitised |
| `reason` | Reason code |
| `possible_matches` | Child IDs, provisional |

- **Cap:** at most 500 attention items. Beyond that, `attention_truncated` holds the overflow count and the run is red.

### 5.6 `source_health[]` (one entry per source)

| Group | Fields |
|---|---|
| Download | `outcome` (`ok`, `http_error`, `timeout`, `tls_error`, `dns_error`, `challenge_page`, `api_error`, `layout_not_recognised`, `not_published_yet`, `deadline`), `stage`, `http_status`, `final_url`, `content_type`, `bytes`, `elapsed_ms`, `attempts`, `pages {requested, ok, failed, stop_reason}` |
| Parse | `parser_version`, `units {seen, parsed, partial, unparsed, ignored}`, `ignored_reasons {code: n}`, `relevance {in_or_after_window, unknown, before_window}` (counts of unparsed + partial units), `unparsed_samples` (≤5, ≤200 characters each, sanitised) |
| Coverage | `per_year {YYYY: {requested, units_seen, outcome}}` |
| Snapshot | `acceptance` (`promoted` \| `quarantined` \| `fallback` \| `unavailable`), `using_fallback`, `served_snapshot_id`, `served_fetched_at` (original fetch time, never refreshed), `baseline_units_seen`, `comparable` |
| Match diagnostic | `eligible`, `peers_fresh`, `matched`, `unmatched`, `informative` (§9.5) |
| Result | `severity` (`ok` \| `warning` \| `error`), `reasons[{code, level: error\|warning\|info, text}]`, `acknowledged[{code, until}]` |

### 5.7 `elections.json` top level

- `schema_version`: `2`
- `generation_id`: SHA-256 over the canonical JSON of `months`, `undated`, `attention_items` and the served snapshot IDs
- `generated_at`: UTC build time of this generation
- `data_as_of`: oldest `served_fetched_at` among sources contributing records
- `current_month`, `window {months[], years[]}`
- `months`, `undated`, `attention_items`, `attention_truncated`
- `source_health`
- `run {parser_version, code_sha, merge_checks{...}, severity}`
- `errors` (legacy: plain-language warning/error lines)

### 5.8 `status.json` (latest attempt)

The publish job writes it to the run artifact on every attempt, but **commits it to `main` only when it commits a generation** (`published` or `validation_failed`). `superseded` and `paused` attempts show in the artifact and the run summary only: a superseded run can't push, and a paused run must not commit.

- `schema_version: 1`, `attempt_id` (`<UTC timestamp>-<run id>`), `attempt_at`, `trigger`, `code_sha`
- `outcome`: `published` \| `validation_failed` \| `superseded` \| `paused`
- `severity`, `reasons[]`
- `serving_generation_id`, `serving_generated_at`
- `sources[{name, severity, using_fallback, served_fetched_at}]`, `acknowledged[]`

`superseded` is not an error for the extension; the CI run is red so the user can re-run that day.

### 5.9 Legacy `status` per child, evaluated at the generation's UTC civil date T

Only the existing values are used: `Upcoming`, `Held`, `Postponed`, `Cancelled`, `Disputed`, `Unknown`. The first matching rule wins:

1. A **resolved** `postponed`/`cancelled` claim (no fresh dated calendar claim contradicts it) → `Postponed` / `Cancelled`.
2. A fresh `disputed` claim → `Disputed`.
3. Day precision: `end_date < T` → `Held`; otherwise `Upcoming`.
4. Month precision: `end_date` before the 1st of T's month → `Held`; the period includes T's month → `Unknown`; otherwise `Upcoming`.

`Held` is documented as "scheduled end passed, no postponement reported". `occurrence_confirmed` carries actual confirmation. An unresolved postponement or cancellation claim sets `status_conflict` and leaves the status to the date rules.

### 5.10 Source snapshots (`data/sources/<source>/`)

- **`candidate.json`:** the latest attempt: `snapshot_id`, `fetched_at`, `parser_version`, `scope {years, pages}`, `units[]` (with outcome and raw text), `claims[]`, plus the download diagnostics.
- **`baseline.json`:** the last promoted complete candidate, with the same shape.
- Both are committed in the same commit as the feed (§11). `snapshot_id` = SHA-256 over the canonical JSON of `units` and `claims`.

## 6. Shared parsing

### 6.1 Civil dates (`dates.py`)

- **Representation:** dates are year/month/day components. Never parse a civil date through a timestamp.
- **Grammar** (every form below is covered by tests):

| Form | Example | Precision / notes |
|---|---|---|
| Day | `25 Oct 2026`, `October 25, 2026`, `2026-10-25`, `5 December 2026` | day |
| Day range, same month | `18–20 September`, `9-10 Oct 2026` | day; hyphen, en dash, em dash or "to" |
| Day range, cross-month or cross-year | `30 Sep – 2 Oct 2026` | day |
| Day list | `16 March, 18 June, and 16 October` | one claim per date (non-consecutive phases) |
| Month | `October 2026`, `Apr 2027` | month |
| Month range | `Nov 2026 - Jan 2027`, `May-June 2022` | month; `end_date` = last day of the end month |
| Year | `2026` | undated (year) |

- **Status words are extracted before they're stripped:** `Upcoming`, `Past`, `Held`, `Postponed from …`, `TBD`, `(d)`, `(t)`, `Date not confirmed`.
- **"Postponed from X [to Y]":** X is a *previous* date; Y, if present, is the new claim.
- **`date_meaning`** is set per source (§7), never by range length: `voting_period` \| `expected_window` \| `unknown`.
- **`date_status`:** `confirmed` only when the source explicitly says so (ElectionGuide `(d)` = "Declared Election Start" / Status "Confirmed"). `tentative` when the source says tentative, TBD or expected. Otherwise `unknown`.
- **Relevance of a unit:**
  - `in_or_after_window` if any date or year in its text is ≥ the window start;
  - `before_window` if every year it mentions is before the window start year and it carries no "postponed"/"to" marker;
  - otherwise `unknown`.

### 6.2 Places (`places.py`, `data/places.yaml`)

- **`place_id`:** `iso:XX` for ISO 3166-1 places, `iso:XX-YYY` for ISO 3166-2 subdivisions that sources treat as places, and `x:<slug>` for places without an ISO code (`x:south-ossetia`, `x:somaliland`, `x:western-sahara`).
- **Each entry:** `display`, `aliases[]`, `country_code`, optional `parent`.
- **Display names are frozen from feed history** (91 strings). Where history has two names for one place, the majority wins; ties go to the old `COUNTRY_SYNONYMS` canonical name:

| Place | Display | Minority aliases (v1.0.2 pins on these must be redone) |
|---|---|---|
| Cape Verde | `Cape Verde` (43) | `Cabo Verde` (2) |
| North Korea | `North Korea` (tie 2/2) | `Democratic People's Republic of Korea` |
| Laos | `Laos` (tie) | `Lao People's Democratic Republic` |
| Vietnam | `Vietnam` (tie) | `Viet Nam` |
| Philippines | `Philippines` (174) | `The Philippines` (16) |
| São Tomé and Príncipe | `Sao Tome and Principe` (154) | `São Tomé e Príncipe` (99) |

- **Subdivisions that appeared as countries keep their own place and display**, so their v1.0.2 pins keep working (a refinement of Section 3, which had required re-pinning):
  - `iso:GB-SCT` "Scotland (part of the United Kingdom)" and `iso:GB-WLS` "Wales (part of the United Kingdom)", both with parent `iso:GB`;
  - `iso:IN-PB` "Punjab, India", parent `iso:IN`.
- **Matching subdivision claims:** a claim with country UK and jurisdiction Scotland resolves to `iso:GB-SCT`. Any source country string `<Name> (part of <Parent>)` resolves to a subdivision place with that display name.
- **Unknown places:**
  - two claims with an unknown country match only on an identical normalised name;
  - such names are logged with reason `place_unregistered`;
  - two `null` codes alone never match;
  - an empty country string makes the unit `partial` (`place_missing`).
- **Generation:** `scripts/build_places.py` produces `places.yaml` from `pycountry` plus the history list. The result is committed and reviewed.

### 6.3 Institutions and office classes (`offices.py`, `data/institutions.yaml`)

- **Office classes:** `head_of_state`, `lower_house`, `upper_house`, `legislature`, `governor`, `mayor`, `local_council`, `referendum`, `general`.
- **Specific institutions** are mapped per place, e.g. `iso:IL` Knesset → legislature, `iso:SE` Riksdag, `iso:RU` State Duma → lower_house, `iso:US` Senate → upper_house.
- **Generic labels are aggregates, not identity:** "Parliament", "Legislative", "General", "municipal elections", "local elections", "regional and local". The one exception: a generic legislature label is identity when exactly one chamber contest exists for that place and date.
- **Mayor and council stay distinct.**
- **Similarity:** within a class, the existing 6-character stem similarity is used only to *generate candidates*.

### 6.4 Level

`level` is the institution being elected:
- the UK Holborn & St Pancras House of Commons by-election is `national`;
- BARMM Parliament is `subnational`.

Sources give a default (ElectionGuide, IPU and Wikipedia national: `national`; Wikipedia local: `subnational`). Office and institution evidence overrides it. Conflicting or absent evidence gives `unknown`. **Filters never hide `unknown`.**

## 7. Source adapters

**Adapter contract:**
- `fetch(window, fetcher) -> RawPages`
- `parse(raw, window) -> (units[], claims[], layout_ok: bool, coverage)`

Every unit gets exactly one outcome. Claims link back to units. Headers are matched by meaning, using normalised header text, never by column position alone.

| Source | Request(s) | Unit | Layout recognised when | Mapping and meaning |
|---|---|---|---|---|
| ElectionGuide | `/elections/type/upcoming/`, `/past/`, `/anticipated/` | Data row of `#electionsTable` with ≥5 `td` | Header contains Country, Election for, Start Date, End Date | Election link `/elections/id/N/` → `source_event_id`. Start/End are ISO with `(d)`/`(t)` → `date_status` per row. Upcoming's Status "Date not confirmed" → tentative. `date_meaning=voting_period`. Past rows → `status_claim=held` / `occurrence_confirmed`. **Coverage check:** past list's oldest row must predate the window start, otherwise reason `coverage_gap`. Rows appearing in several views are linked through `source_event_id` |
| Wikipedia national | MediaWiki API `action=parse&page=<Y>_national_electoral_calendar&prop=text\|revid&format=json&formatversion=2&maxlag=5`, once per requested year | Each `li` with its own text, at any depth, under month sections and "Indirect elections" | Month `h2` headings found with lists; API JSON has no `error` key | Date from the top-level `li` prefix (§6.1, including day lists). Country = first link of the country entry. **Offices are split by their separate links**, and round qualifiers stay with their own office. Leftover text is checked; anything unaccounted makes the unit partial. "Indirect elections" entries get `indirect=true`. `date_meaning=voting_period`. `revid` is recorded |
| Wikipedia local | Same, `<Y>_local_electoral_calendar` | Same, parsed recursively | Same | Country entry → one card grouping; nested items → structured children inheriting the date, country and parent jurisdiction. Default level `subnational`, overridden per §6.4 |
| NDI | `/elections-calendar?page=N` | Card `div.partial.-election.-feed` | Two `.bound` blocks with cards and pagers | Block 1 = upcoming, block 2 = past (archive). Order is verified by date direction. `?page=N` advances both. Continue while upcoming has a next page or the past block's oldest card is ≥ the window start. Cap 10 pages; repeated-page detection by card-name set. Date from the **visible card text**. "TBD" in the title → `date_status=tentative` and month precision. Country = `data-location`. The type label sets the level |
| OSCE | `/odihr/elections` | `tr.search-target` | Header = Date, Country, Election, Activity | Precision from the **visible date `div` text**. `data-filter-date` is only a cross-check for day precision (a mismatch makes the unit partial). Badge span → status words. Year-only → undated. `date_meaning=voting_period` |
| IPU | `data.ipu.org/elections/` | Table row | Header contains "Expected date of next election" and "Principal mode of designation" | `evidence_kind=expected_renewal`, `date_status=tentative`. Designation "appointed" → ignored (`appointed_chamber`); "indirect" → `indirect=true`. CI fallback endpoints (`api.data.ipu.org/v1/reports/elections`, CSV export) depend on open item O1 |
| A-WEB | `list.do?menuNo=300052&option=all` | Table row | Header has country, election, date columns | A single day → `voting_period`, `date_status=unknown`. Ranges → `date_meaning=unknown`. External EMB links are kept as claim links only if they pass the allowlist (§12.6) |
| EISA | Calendar page → find heading "EISA African Election Calendar {Y}" → its `data-footable_id` → `wp-admin/admin-ajax.php?action=wp_ajax_ninja_tables_public_action&table_id=ID&target_action=get-all-data` (no nonce needed, verified) | JSON row | The current year's heading exists and the JSON is a list of rows with `country`, `election`, `date` | A blank country inherits the previous row's country **within the same table only**; blank in the first row → partial. Date grammar: `Held D Month YYYY` (held, voting_period); `D Month YYYY`; `Month YYYY` (month); `YYYY` (undated); `Postponed from X [to Y]`; `Mon YYYY - Mon YYYY` (expected_window); `Stagerred: … - …` (unknown, phased) |
| Carter Center | `/programs/democracy/elections-observed/` | Row of `table.has-fixed-layout` under the headings "Elections Monitored by The Carter Center" or "Expert Missions" | Either heading found with its table | Cells: country link + comma-separated `Month YYYY` / `Month-Month YYYY` tokens, one claim per token. `evidence_kind=observation`, month precision. Expert missions are flagged |
| EEAS | `/eeas/eu-election-observation-missions-1_en` | Link text matching `EOM <Country> <YYYY>`, deduplicated by href | At least one such link | `evidence_kind=observation`, year only. Never sets a date. Unmatched → `unresolved_evidence` |

**Year rollover:**
- A missing **next-year** page (HTTP 404, or the API's `missingtitle`) → `not_published_yet`, an info-level reason. A coverage gap for that year is recorded in `per_year`.
- A missing **current-year** page → error `current_year_missing`.

## 8. Fetching (`fetch.py`)

- **Retries:** up to 3 attempts per request with exponential backoff (2 s, 4 s, 8 s), honouring `Retry-After` (capped at 60 s). Timeout 60 s per request.
- **Deadlines:** 4 min per source, 12 min for the whole scrape. A source that runs out gets outcome `deadline` and its unfinished pages are recorded.
- **Parallelism:** up to 4 sources at once; requests within one source run one at a time.
- **TLS verification is on everywhere.** OSCE's chain ends at emSign Root CA – G1, which isn't in certifi, so for `odihr.osce.org` and `www.osce.org` only, the trust store is certifi **plus** `data/certs/emsign-root-ca-g1.pem`. The SHA-256 fingerprint of that file is pinned in code and checked at load.
- **User-Agent:** Wikipedia requests use `global-elections-calendar/2.0 (+https://github.com/newscorp-ghfb/global-elections-calendar)` (no personal email). Other hosts get a browser User-Agent.
- **Challenge detection:** HTTP 200 with a known challenge marker (Cloudflare/Sucuri interstitial text, or `<title>` matching "Just a moment" / "Access denied") → `challenge_page`.
- **MediaWiki:** an `error` key in the JSON → `api_error`; `maxlag` errors are retried.
- **Diagnostics** per request: stage, exception type, final URL, content type, size, elapsed time, attempts. URLs and error strings are redacted (query-string tokens/keys) before storage.

## 9. Ledger, acceptance, health

### 9.1 Ledger invariants (checked in shared code, per source)

- **Set equality:** the set of `unit_id`s seen equals the union of the four outcome sets. The sets are disjoint and contain no duplicates.
- **Ignored units** carry an allowlisted reason code (`header_row`, `appointed_chamber`, `duplicate_view`).
- **Being before the window is not a reason to ignore a unit.** Such units keep their parsed/partial/unparsed outcome; relevance (§6.1) is recorded separately, and only relevant unparsed/partial units become attention items.
- **Partial units** keep their parsed claims plus the leftover text.
- **Any violation** sets the source's severity to `error` with reason `ledger_mismatch`.

### 9.2 Parser-level checks (independent of merging)

- The country resolves through `places.yaml`; otherwise the unit is partial (`place_unregistered` / `place_missing`).
- Date semantics are plausible for the source: no day precision from OSCE `Apr 2027`, end ≥ start, year within ±5 of T.
- The expected fields are present.
- Frozen fixtures of known column shifts are tested, e.g. the OSCE 5→4 column change.

### 9.3 Acceptance decision (separate from severity)

| Situation | Served | Baseline | Severity |
|---|---|---|---|
| Layout recognised, paging complete, no sudden drop | Candidate; relevant unparsed/partial units become attention items | Promoted | `ok`, or `warning` if any relevant unit is unparsed/partial |
| Sudden drop: `units_seen` more than 50% below the baseline for the same year/page scope, with no recorded explanation (`valid_empty`, `year_rollover`) | Baseline (original age shown) | Kept; candidate quarantined | `warning` (`sudden_drop`) |
| Download failure, incomplete paging, layout not recognised, challenge page, deadline | Baseline, or `unavailable` | Kept | `error` |
| No baseline and the candidate is valid (first run) | Candidate | Promoted | As for row 1 (bootstrap is not an error) |
| No baseline and the candidate is invalid | Nothing; `unavailable` | — | `error` |

- **Parser version change:** a different parser major version marks the baseline `comparable=false`. The drop check is skipped; structural checks still apply.
- **One generation:** baselines and the feed move together in one commit (§11). A failed validation advances nothing.

### 9.4 Severity and reasons

- **Error codes:** `fetch_failed`, `tls_error`, `timeout`, `dns_error`, `http_error`, `challenge_page`, `api_error`, `layout_not_recognised`, `current_year_missing`, `pagination_incomplete`, `deadline`, `unavailable`, `ledger_mismatch`.
- **Warning codes:** `unparsed_relevant`, `partial_relevant`, `sudden_drop`, `coverage_gap`, `no_cross_source_match`, `fallback_stale` (served fallback older than 7 days), `served_mismatch`, `attention_truncated`, `ack_invalid`.
- **Info codes** (reason-level only; never raise severity): `not_published_yet`, `count_change`.
- **Mapping:** source severity = the worst reason level. Run severity = the worst source severity combined with the merge, validation and publish results.

### 9.5 Cross-source match diagnostic

- **Counted:** eligible = the source's in-window national children; peers = other sources that are fresh (not fallback) and cover the same places; matched / unmatched counts.
- **Informative** only if there are ≥2 fresh peers and ≥5 eligible.
- **Warning:** an informative comparison with `matched = 0` gives warning `no_cross_source_match`. A source's own fallback never counts as a peer.

### 9.6 Acknowledgements (`known_issues.yml`)

```yaml
- source: ipu
  reason: http_error
  scope: {stage: fetch, year: null, page: null}
  explanation: "IPU blocks GitHub runner IPs; API fallback being evaluated"
  owner: senescalk
  acknowledged_at: 2026-10-20T09:00:00Z
  expires_at: 2026-11-03T09:00:00Z
```

**Rules:**
- **Validity:**
  - all fields are required;
  - `expires_at - acknowledged_at` must be ≤ 14 days;
  - the entry expires when the current UTC time reaches `expires_at`;
  - there's no auto-renewal;
  - a malformed entry is itself a warning (`ack_invalid`).
- **Matching:** an acknowledgement matches only the exact source + reason + scope. It is voided by any healthy run of that source after `acknowledged_at`, so a recurrence needs a new entry.
- **Effect:** it changes **only the exit code**. Severity, acceptance decisions, the banner (shown as "acknowledged until …") and `HEALTH.md` are unchanged.
- **Never acknowledgeable:** schema, legacy-contract, merge, conservation and publication failures, `fallback_stale`, and `attention_truncated`.

## 10. Merge

### 10.1 Identity

The identity key is:
- `place_id`
- `level` (equal, or either side `unknown`)
- `institution`: specific, or `office_class` for an unresolved specific
- `jurisdiction` (`nationwide` = `nationwide`; equal names; `unknown` never counts as agreement)
- `round` (equal, or either side not stated; two different stated rounds never match)
- `kind`

Referendum questions are children only when a source lists the questions; otherwise there is one `referendum_day` contest per place and date.

### 10.2 Phase A: anchors

- **Anchor claims:** `evidence_kind=calendar`, day precision, `date_meaning=voting_period`, specific institution or kind, and jurisdiction `nationwide` or `named`.
- **Compatibility graph:** an edge joins two anchors with compatible identity keys and overlapping date intervals.
- **Connected components:**
  - a component in which **every pair** is compatible becomes one contest (for intervals that's equivalent to sharing a common day);
  - in any other component, each member becomes its own contest, flagged `ambiguous`, with `possible_matches` pointing at its neighbours.
- **No date tolerance:** exact dates a day apart don't overlap, so they're separate contests linked through `possible_matches`.

### 10.3 Phase B: weak claims

**Weak claims** are every non-anchor claim: month/year precision, unknown round/institution/jurisdiction, expected renewals, observations.

**Candidates** for each weak claim are taken from **all** Phase A contests (before the window is applied), filtered by:
- identity compatibility;
- date compatibility: day and month precision = the intervals overlap; year = same year;
- jurisdiction: equal; or the weak claim's jurisdiction is `unknown` **and** there's exactly one candidate.

**Month disagreement:** when no overlapping candidate exists, a month-precision claim may attach to the **single** contest of the same place, institution and level in the whole year, with `date_conflict=true` (e.g. EISA's "October 2026" Cape Verde entry joins the 15 Nov contest). Two or more contests in that year → unresolved.

**Outcome by number of candidates:**
- **Exactly 1:** attach the claim to that contest.
- **0:**
  - calendar claims and expected renewals become standalone contests (an IPU-only contest is `tentative`);
  - year-only calendar claims go to `undated`;
  - observations become `unresolved_evidence` attention items.
- **2 or more:** `unresolved_evidence` attention item with `possible_matches`.

Weak claims never change Phase A contests.

**Phase C:** standalone weak claims cluster among themselves under the Phase A rules, using precision-appropriate date compatibility.

### 10.4 Umbrellas and aggregates

- **What counts as an umbrella:** claims of class `general`, and aggregate labels that aren't identity (§6.3), become umbrella links.
- **Where they attach:** to the cards of the same place with an overlapping date, compatible level and compatible round. A "2nd round" umbrella never links to a first-round or referendum card.
- **How they're stored:** once, as a scoped link in the card's `umbrella_sources`. They're never a child's own source and never confirm a child.
- **Umbrellas that name their parts:** the adapter emits each named part as its own claim, and the parts go through matching. Unresolved named parts become attention items.
- **Unmatched umbrella:** a standalone `aggregate` contest. Its unknown number of races is shown, and it is counted as one "grouping".

### 10.5 Selecting resolved values

**Order:**
1. **Eligibility:** `calendar` > `expected_renewal` > `observation`; umbrellas are excluded.
2. **Interval coverage:** if one eligible `voting_period` claim's interval contains every other eligible claim's single day, take that interval. A range is never built from min/max of disagreeing single days.
3. **`date_status`:** confirmed > tentative > unknown.
4. **Precision:** day > month.
5. **Freshness:** a fallback claim loses only if it's more than 7 days old.
6. **Source priority:** ElectionGuide, OSCE, Wikipedia national, Wikipedia local, NDI, A-WEB, EISA, IPU, Carter Center, EEAS. Then `source_event_id`, then `unit_id`.

Each claim records whether it was `selected`, or its `rejected_reason`.

**Other fields:**
- `office_label` comes from the highest-priority direct claim (never an umbrella).
- `unverified=true` when every claim supporting the selected date is fallback data older than 7 days.

### 10.6 Status

- **Legacy status:** per §5.9.
- **Postponement or cancellation:** a postponed/cancelled claim is resolved only if no fresh, dated calendar claim for the same contest contradicts it. Otherwise `status_conflict=true` and the status follows the dates. This keeps the contest in v1.0.2's Upcoming tab.

### 10.7 Cards

- **Card key:** `(place_id, level, date, end_date, date_precision, date_meaning, date_status, status)`. Children are ordered by office class, then jurisdiction, then `child_id`.
- **Legacy `type`:**
  - **1 child:** its `office_label`.
  - **All children share an office class but have different jurisdictions:** `<Label>: <jurisdiction list> (<n>)`, e.g. "Governors: Alagoas, Amazonas, Bahia, … (27)".
  - **Otherwise:** labels joined with " · ".
  - Truncated to 200 characters + " (+k more)".

### 10.8 Conservation (identity-based)

- **Dispositions:** every merge input claim ID has exactly one disposition: `anchor_member(child_id)`, `attached(child_id)`, `umbrella_link(group_ids)`, `standalone(child_id)`, `undated(undated_id)` or `attention(item_id)`.
- **Checks:**
  - set(inputs) = set(dispositions), with no duplicates and no unknown IDs;
  - every link target exists;
  - every named umbrella part is resolved, excluded with a reason, or an attention item.
- **Outside the window** is a visibility flag applied after resolution.
- **"No missed merge":** no two output contests have a uniquely justified, admissible union left under §10.1–10.3.
- **"No wrong merge":** no contest contains two office classes, two stated rounds, or two known levels.
- **Any failure blocks publication** (§11).

### 10.9 Determinism

- Inputs are sorted by `unit_id` before merging, and every tie-break is total.
- **Tests:** exhaustive permutations for sets of ≤6 claims; Hypothesis property tests with a fixed seed for larger sets. The output must be byte-identical for identical evidence.

## 11. Publishing and CI

### 11.1 What each trigger can do

| Trigger | `gates` | `scrape` | `publish` |
|---|---|---|---|
| Push to any branch | ✔ | — | — |
| Schedule (default branch `main`) | ✔ | ✔ | ✔ |
| `workflow_dispatch` on a branch | ✔ | ✔ | never: the job condition requires `github.ref == 'refs/heads/main'` |
| `workflow_dispatch` on `main` | ✔ | ✔ | only if `inputs.publish == true` (boolean input, default `false`; missing or malformed counts as false) |

### 11.2 Jobs (`.github/workflows/update-elections.yml`)

Workflow-level `concurrency: {group: publish-elections, cancel-in-progress: false}`. Actions are pinned to full commit SHAs. Python is pinned to an exact 3.14 patch.

- **`gates`** (`contents: read`, 15 min):
  1. Create `.venv` and run `pip install --require-hashes -r requirements-dev.txt`.
  2. Run `python -m playwright install chromium` as a separate setup step.
  3. Run the Linux gates (§14). The extension suite must not skip when `CI=true`. Collected/passed/skipped counts go to the job summary.
- **`scrape`** (`contents: read`, 20 min, needs `gates`):
  - Install `requirements.txt` into `.venv` with `--require-hashes`.
  - `PAUSE_PUBLISHING` present → summary "paused", success, and a `paused` job output that makes `publish` skip; stop.
  - `ALERT_TEST` present → summary "alert test", **fail**, stop.
  - Otherwise run `python scraper.py --live --out out/`. That writes the candidate generation, a verdict file and `HEALTH.md`, all uploaded as an artifact. `HEALTH.md` also goes into the job summary.
  - An `if: always()` step writes a minimal summary even after a crash.
- **`publish`** (`contents: write`, 15 min, needs `scrape`, conditions per §11.1):
  1. Download the artifact.
  2. Push-race check: `git fetch origin main`; if `origin/main != github.sha` → status `superseded` (no data commit), red.
  3. Commit **one** generation:
     - if valid: `elections.json`, `status.json`, `HEALTH.md` and promoted `data/sources/*`;
     - if validation failed: only `status.json` and `HEALTH.md`, with `elections.json` untouched.
  4. Push without rebase or force.
  5. **Served check:** fetch the raw `elections.json` URL every 60 s for up to 10 min until `generation_id` matches; otherwise `served_mismatch`.
  6. Final exit code from run severity after acknowledgements.

### 11.3 Validation before publishing (in `scraper.py`, before writing `out/`)

The **final serialised bytes** of `elections.json` are checked:
1. against `schemas/feed-v2.schema.json`;
2. against the legacy contract: every card has `date` (YYYY-MM-DD), a non-empty `country`, a string `type`, a legacy-enum `status`, and `sources[{name, link}]`, with `source_names`/`links` consistent;
3. against the merge invariants (§10.8);
4. against the size cap: `elections.json` ≤ 2 MB.

`status.json` is checked against its schema. Local writes go to temp files and are renamed into place.

### 11.4 Recovery switches

- **`PAUSE_PUBLISHING`:** a file at the repo root on `main` that stops publishing while recovering (§15).
- **`ALERT_TEST`:** a file at the repo root on `main` that makes the next scheduled run fail on purpose, publishing nothing.

### 11.5 Release record

`RELEASES.md` records, for each release: the code SHA, the `requirements*.txt` hashes, the extension ZIP SHA-256 and file list, the destination, the date, and who approved it.

## 12. Extension v2.0.0

### 12.1 Loading

- **Fetching:** the background script fetches `elections.json` and `status.json` from the same raw base URL. Permissions are unchanged: `storage` and `alarms`, host `https://raw.githubusercontent.com/*`.
- **Refresh:** the hourly alarm is created in `onInstalled` **and** `onStartup`, and checked again when the popup opens.
- **Validation:**
  - both documents are checked for required fields and types;
  - `schema_version: 2` → v2 renderer;
  - no `schema_version` but `months` present → today's renderer;
  - an unknown or malformed version → legacy fields plus an "update the extension" banner.
- **Linking the two:**
  - `status.serving_generation_id == feed.generation_id` → show the relationship;
  - no match → refetch once; if still mismatched, show "current health can't be confirmed for this data";
  - a good feed is never discarded because of `status.json`.
- **Ordering:** a newer `generated_at` is never replaced by an older one.
- **Cache:** keys are `elections_cache_v2` and `status_cache`. A failed write keeps the previous cache.

### 12.2 Banner

**One summary banner** shows the worst condition and the issue counts, and expands into a source health panel:

| Order | Condition | Colour |
|---|---|---|
| 1 | Feed older than 36 h (client clock) | red |
| 2 | Latest attempt `validation_failed` | red |
| 3 | A source error (unless acknowledged) | red |
| 4 | Warnings | amber |
| 5 | Acknowledged issues | grey; still describes the real condition, e.g. "unavailable" |

The footer reads "Data as of `generated_at`" (plus the older `data_as_of` when the gap exceeds 24 h) and "Checked `local time`". Uncertain or future timestamps are shown as uncertain.

### 12.3 Labels (per child; cards summarise their children)

| Evidence | Label |
|---|---|
| Exact future date | Scheduled (+ "Tentative" chip when `date_status=tentative`) |
| `voting_period` includes the user's local civil date, no conflict or postponement | "Scheduled voting period: today (approx.)" |
| Month precision, current month | "October — day unconfirmed" |
| Month precision, past, no confirmation | "Past expected period — not confirmed" |
| `expected_window` | "Expected between 2 Nov and 31 Jan" |
| `occurrence_confirmed` | Held |
| Date passed, not confirmed | Past |
| `status_conflict` | "Possibly postponed — sources disagree" (prominent) |
| `date_conflict` | "Sources disagree on date", with per-source dates in the expanded view |
| Fallback-sourced date | "Using source data from <date>"; escalates to "Unverified since <date>" after 7 days |
| `level=subnational` | "Subnational" chip |

- **Ranges** show as "18–20 SEP". **Month precision** shows the month with "TBC" and never a day.
- **Mixed confirmation in a card** shows e.g. "Past · 2 of 3 confirmed held".
- **Civil dates are compared as components**, never through `Date()`.

### 12.4 "Needs attention & undated" section

- Placed above the empty state and the card list on every month, labelled "N items across the monitored window (Sep–Jan)".
- Lists every `attention_items[]` entry: text, source and link, and its possible matches marked as provisional.
- Never hidden by filters; a search shows "k of N".

### 12.5 Counting, filtering, tabs

- **One pipeline:**
  1. filter children (month bucket, pins, level, search, tab);
  2. count distinct `child_id`s;
  3. group into cards.

  The highlighted tab, the cards and every counter come from the same state.
- **Counter:** "41 election records (incl. 6 groupings)". Attention items have their own count.
- **Partial card matches:** "1 matching of 27".
- **Level filter:** "All" / "National + unclassified" / "Subnational + unclassified".
- **Tabs:**
  - **Upcoming:** Upcoming, Unknown (current-month month precision), tentative, scheduled-today, conflicts, and resolved Postponed (with a chip).
  - **Past** (renamed from "Results"): Held and Past.
  - **All:** everything.
- **Bug fix:** the tab initially highlighted always matches the list shown (today `popup.html:122` highlights Upcoming while `popup.js:42` shows all).

### 12.6 Pins, options, links

- **Pin migration, once:**
  1. Read `pinned_countries` (left untouched).
  2. Map each name through the alias table to a `place_id`.
  3. Write `pinned_places_v2` and verify it.
  4. Set `pins_migrated_v2`.

  Unmappable names are kept as "unresolved pins", shown on the options page. Deleted pins stay deleted. Pinning a parent place also includes its subdivision places.
- **Options list:** feed places plus saved pins.
- **Links:** `https` only, and the host must match the source's allowlist:

  | Source | Allowed hosts |
  |---|---|
  | ElectionGuide | `electionguide.org` |
  | Wikipedia | `en.wikipedia.org` |
  | NDI | `ndi.org` |
  | OSCE | `odihr.osce.org`, `osce.org` |
  | IPU | `data.ipu.org` |
  | A-WEB | `aweb.org` |
  | EISA | `eisa.org` |
  | Carter Center | `cartercenter.org` |
  | EEAS | `eeas.europa.eu` |

  Otherwise the link goes to the source's home page. This applies to the v2 and legacy renderers alike.
- **Text:** all feed text is inserted through `textContent`.

### 12.7 Accessibility and limits

- **Disclosure buttons** use `aria-expanded`; **tabs** use `aria-selected` with matching panels; focus is visible.
- **Tested** at narrow width and 200% zoom, with 10 source issues and 27 expanded children.
- **Rendering is bounded:** children render on expand; at most 200 attention items render before "show more".

### 12.8 Help, release, update

- **Version and help:** `manifest.json` version `2.0.0` with an updated description. `help.html` is updated (banner, chips, 10 sources, 5 months, update instructions).
- **ZIP:** `scripts/build_extension_zip.py` builds `dist/Global_Elections_Calendar_v2.0.0.zip` from an explicit file list. It checks:
  - the manifest is at the root;
  - every referenced asset is present;
  - the version is correct;
  - the permission diff against v1.0.2 is empty.

  It records the SHA-256 in `RELEASES.md`.
- **Load-unpacked update instructions:**
  1. In `chrome://extensions`, note the extension's folder.
  2. **Delete the folder's contents** (keep the folder).
  3. Extract the v2 ZIP into it.
  4. Click Reload.

  **Don't remove the extension**: that deletes pins. The extension ID depends on the folder path, and the manifest gets no `key`.
- **Web Store:** the user uploads the same ZIP. Users auto-update with the same ID and storage. "No permission prompt" is *expected*, and is confirmed only once the update lands (O4).
- **Release notes:** how to update for each install route; the minority-alias pins to redo in v1.0.2 (§6.2); that v1.0.2 counts cards and shows month-only dates as "1 OCT"; and that v1.0.1 users read a dead URL and must update.

## 13. Testing

### 13.1 Fixtures

- **From `.scratch`:** the 2026-10-16 snapshots move to `tests/fixtures/<source>/2026-10-16/`, each with a provenance note (URL, fetch time, HTTP status).
- **Fetched during implementation (read-only):** NDI `?page=1`; Wikipedia API versions of national 2026, national 2027 and local 2027 (local 2026 API is already saved); the emSign root from eMudhra's official repository, fingerprint verified against the issuer of OSCE's served chain.
- **Negative fixtures:** layout changed (including the frozen OSCE column-shift), challenge page with HTTP 200, valid-but-empty, a truncated page, a MediaWiki error with HTTP 200.

### 13.2 Independent expected file

- **`tests/expected/2026-10-16.yaml`** is written **by hand from the source pages, not from the parser**. Each entry has place, office, round, date/range, level, status, and the source with a short quote.
- **Coverage:** all national contests in the window, plus all Appendix B cases and a subnational sample.
- **The user spot-checks it.**
- **Strictness:** a national contest the pipeline produces that isn't in the file fails the test; subnational additions are reported as a count.
- **`tests/expected/legacy-mapping-exceptions.yaml`:** the approved exceptions for SC2, e.g. the EEAS fake-date records and the Brazil 25 Oct duplicate pair.

### 13.3 Acceptance catalogue (all must pass)

| IDs | Requirement (summary) |
|---|---|
| S1-T1…T8 | Month-only vs exact-1st dates; window overlap without double counting; distinct contests in one country stay separate; correction plus one bad row; fallback cannot resurrect a cancellation; honest ageing including first-run failure; v1.0.2 renders the v2 feed; pins survive (T8) |
| S2-T1…T16 | ElectionGuide view variants and row markers; NDI TBD precision; evidence-based ranges; IPU expected renewal vs voting; office splitting with a round on one office; two inputs → one election with a partial unit; 27 children with one postponed; layout variants, empty data, challenge page; pagination repeat/loss/midway failure; January window, missing future page, HTTP-200 API error; EISA blank-country scope; "postponed from" an old year; TLS failures; 429/503/maxlag; level classification; typed mission evidence |
| S3-T1…T19 | Mayor vs council; referendum proposals vs session; office aliases and empty jurisdictions; rescheduling vs rerun; 18/19/20/21 in all orders; unknown round vs rounds 1 and 2; candidate scope outside the window; replay idempotence; 20 Sep vs 18–20; expected renewal vs polling evidence; old cancellation refetched; past unverified date; scoped umbrella; partial umbrella parts; lost-plus-duplicated input caught by ID audit; invariant failure blocks publish; real v1.0.2 pins; card certainty split; child identity through card split/rejoin |
| S4-T01…T19 | 100→40→timeout never makes a partial baseline; bootstrap and justified drops; middle-page failure/repeat/challenge; partial scrape with a correction; validation failure doesn't publish; fallback schema/version honesty; interrupted writes; another writer before push; real raw-URL route; setup/test/deadline/push failure; staleness without new runs; time budget; scheduled email (rollout); acknowledgement expiry/scope/recurrence (T14); malformed acknowledgements and global gates (T15); match-diagnostic limits, and structural checks catching the frozen OSCE column shift (T16); ledger with multi-output units (T17); `publish:false` dispatch can't publish (T18); escaped/redacted diagnostics (T19) |
| S5-T01…T22 | Feed/status relationships; late/out-of-order responses; validation of both documents; sleep/restart/worker termination; freshness thresholds and clock skew; civil dates across time zones and DST; month-only, year-only and expected windows; Held vs Past; conflicts suppress "today"; 20 attention items, 5 samples; attention section always reachable; child counting "1 of 27"; deduplicated totals and aggregates; tabs and counters in one state; pin migration; real ZIP same-folder update; legacy/v2 renderer matrix; hostile text and URLs; keyboard and screen reader; ZIP contents and permissions; large collections and cache-write failure; offline and expired cache |
| S6-RT-01…RT-07 | Clean-environment gates with deliberate failures; dry-run and publish privilege separation, including inert "publish" text in fixtures; approval tied to the exact candidate; independent expectations and first-baseline review; rehearsed rollback with an interleaved publisher; real-artifact upgrade; deterministic alert delivery |

### 13.4 Layers and gates

- **Unit tests:** `dates`, `places`, `offices`, `window`, `fetch` (mock HTTP server, local HTTPS server with bad certificates, fake clock).
- **Adapter tests** per source on fixtures: ledger balance, layout check, expected claims, negative fixtures.
- **Merge tests:** S3 catalogue plus property tests.
- **Pipeline tests:** S4 catalogue using temporary git repos.
- **End-to-end:** the full offline pipeline at `--now 2026-10-16T00:00:00Z` on all fixtures, checked against the expected file (SC1) and against the frozen production feed `tests/fixtures/feed/2026-10-16-ff30417.json` for the old→new mapping (SC2).
- **Extension:** pytest-playwright with a Chromium persistent context and `--load-extension` (`xvfb-run` on Linux CI). Requests to the raw feed URL are routed to fixture files. The legacy matrix uses the real v1.0.2 files from git (`ff30417:extension/`).
- **Mutation checks:** one per new test, per D9. The test's task files are `git add`ed first; a mutation is restored with `git checkout -- <file>` plus `git diff --exit-code -- <file>`; `PYTHONDONTWRITEBYTECODE=1` is set.

### 13.5 Bounded live check (not a gate)

`scraper.py --live --dry-run --out .scratch/live/`, run in the background:
- limits: ≤40 requests, 4 at a time, 3 retries, 60 s per request, 10 min total;
- the output is compared with the fixture expectations;
- for the first rollout, any unexplained material difference pauses the release until the user accepts it on record.

## 14. Gates (canonical; documented in README)

**Windows (local):**

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\mypy.exe
.venv\Scripts\ruff.exe check
.venv\Scripts\lint-imports.exe --config importlinter.ini
```

**Linux (CI):**

```bash
.venv/bin/python -m pytest -q
.venv/bin/mypy
.venv/bin/ruff check
.venv/bin/lint-imports --config importlinter.ini
```

- **Configuration:** mypy (strict) and ruff are configured in `pyproject.toml`; `files` lists `elections_calendar`, `scripts` and `tests`.
- **Not a gate:** `ruff format`.
- **Each gate is proven** with a deliberate failure (RT-01): a layering violation for import-linter, a type error for mypy.

## 15. Rollout and rollback

Every step that writes outside this machine needs the user's go-ahead at the time.

1. **Branch CI:** push `feat/never-miss-v2` to `origin` and let CI run the gates. Then run `workflow_dispatch` on the branch (`publish:false`):
   - read `HEALTH.md` in the run summary, confirming the user can see it (O8);
   - diagnose IPU in CI (O1).
2. **Reviewed first baselines:** from the dry-run artifact, compare the candidate baselines with the live check and the expected file. The user approves them, and they're committed to the branch.
3. **Merge:** a whole-branch review, then tag `pre-v2` on `main`. The user says "merge" and creates `MERGE_APPROVED`; then fast-forward `main` and tag `v2.0.0`. Gates are re-run after any rebase.
4. **Publish the feed:** push `main`. The next scheduled run publishes the v2 feed. Then check the served file, `HEALTH.md`, and v1.0.2 rendering (manual, plus S5-T17 evidence).
5. **Alert test:** commit `ALERT_TEST`, confirm the scheduled-run email, then remove the marker.
6. **Extension:**
   - build the ZIP and record it in `RELEASES.md`;
   - share it with Load-unpacked users along with the update instructions;
   - the user uploads it to the company Web Store listing;
   - confirm the Store update and its permission prompt (O4).
7. **Rollback** (target: same day, under 2 h from the decision; rehearsed in RT-05):
   1. Commit `PAUSE_PUBLISHING`.
   2. Restore the archived last-known-good `elections.json` (hash recorded in `RELEASES.md`).
   3. Revert `pre-v2..v2.0.0` as one commit.
   4. Remove `PAUSE_PUBLISHING`.

   Client/feed combinations covered: v1.0.2 with v1, v1.0.2 with v2, v2 with v2, and v2 with the restored v1 (legacy renderer).

## 16. Housekeeping (after release evidence is retained; separate commits)

- **`.gitignore`:** `.venv/`, `.scratch/`, `dist/`, `__pycache__/`, `.claude/worktrees/`. This goes in the first plan task.
- **README:** architecture, sources, gates for both platforms, and update instructions for both install routes.
- **Old ZIP:** record the v1.0.2 ZIP's SHA-256 (it was never tracked), then move it to `dist/`.
- **`build_elections_pptx.py`:** review it, update its text (5 months, 10 sources), and commit it separately from the core release. It doesn't read the feed.
- **Remote:** remove the dead `dowjones` git remote (local configuration only).
- **`.scratch/`:** delete it only after confirming nothing unique is left.

## 17. Open items and risks

| ID | Item | Resolution point |
|---|---|---|
| O1 | IPU yields nothing in CI; cause unknown | Branch dry run (§15 step 1) → choose its API/CSV, or an acknowledgement |
| O2 | `Mogzauri14/Exp_KS2025` still publishes a v1.0.0 feed daily (generated 2026-10-16 02:24 UTC); owner unknown | Ask the user; outside this change |
| O3 | v1.0.1 Load-unpacked users read a deleted Dow Jones mirror URL (404) | Release note asks everyone to update |
| O4 | Web Store "no permission prompt" is unproven | Confirmed when the Store update lands |
| O5 | Python 3.14 wheels for every pinned dependency | Plan task 1; fall back to 3.13 everywhere if missing |
| O6 | Provenance of the emSign root certificate | Download from eMudhra, verify the fingerprint against OSCE's served issuer, pin it in code (§8) and record it in `RELEASES.md` |
| O7 | Whether the user can see the run summary | §15 step 1; fall back to a `diag` branch commit with the user's go-ahead |
| R1 | Sources change layout without notice | Mitigated by §9; residual risk: detection is next-day |
| R2 | Wikipedia vandalism or edit lag | Cross-source evidence and visible single-source records; not eliminated |
| R3 | EISA's endpoint without a nonce may change | Layout check → fallback to the baseline plus an error |
| R4 | NDI's shared pager semantics may change | Repeated-page and termination checks |
| R5 | Trusting an extra root for OSCE | Scoped to the OSCE hosts only, fingerprint-pinned |

---

## Appendix A — Traceability

| Invariant | Tests | Fixtures | Gate |
|---|---|---|---|
| I1 No silent drops (every unit accounted for, relevant ones visible) | S2-T5–T7, S4-T17, S5-T10–T11, ledger unit tests | all adapters, negative fixtures | pytest |
| I2 Failures visible within one run | S4-T03, S4-T10, S4-T16, S5-T01–T03, RT-07 | negative fixtures | pytest + rollout |
| I3 Baseline integrity | S1-T4–T6, S4-T01–T04, RT-04 | 100/40 synthetic, 2026-10-16 | pytest |
| I4 Only validated generations publish | S3-T16, S4-T05–T09, RT-02–RT-03 | temporary git repos | pytest |
| I5 Merge correctness and determinism | S3-T1–T15, S3-T18–T19, property tests | synthetic + 2026-10-16 | pytest |
| I6 Legacy compatibility | S1-T7, S3-T17, S5-T17, SC2 | v1.0.2 files at `ff30417`, frozen feed | pytest |
| I7 Freshness honesty | S4-T11, S5-T04–T05, S5-T22 | fake clock | pytest |
| I8 Dry runs cannot publish | S4-T18, RT-02 | workflow tests | pytest + rollout |
| I9 Upgrades keep pins | S1-T8, S5-T15–T16, RT-06 | real ZIPs | pytest |
| I10 Alerts are delivered | S4-T13, RT-07 | `ALERT_TEST` | rollout |
| I11 Safe rendering | S5-T18, S4-T19 | hostile-text fixtures | pytest |
| I12 Expected elections present | SC1, Appendix B | `tests/expected/2026-10-16.yaml` | pytest |

## Appendix B — Regression cases (each must appear in the 2026-10-16 end-to-end output)

| Date | Place | Contest | Evidence |
|---|---|---|---|
| 13 Sep 2026 | Sweden | Riksdag | Wikipedia national; OSCE |
| 13 Sep 2026 | Sweden | regional and municipal | Wikipedia local (was under "Germany") |
| 18 Sep 2026 | South Ossetia (`x:south-ossetia`) | President | Wikipedia national |
| 18–20 Sep 2026 | Russia | State Duma | Wikipedia national (range); OSCE "20 Sep" → one contest, 18–20 |
| 23 Sep 2026 | Morocco | House of Representatives | Wikipedia national; NDI; EISA |
| 24 Sep 2026 | Isle of Man | House of Keys | Wikipedia national |
| 27 Sep 2026 | São Tomé and Príncipe | National Assembly | Wikipedia national; NDI; EISA |
| 4 Oct 2026 | Brazil | President (1st round), Chamber of Deputies, Federal Senate (one national card, 3 children) | Wikipedia national; ElectionGuide; NDI umbrella |
| 4 Oct 2026 | Brazil | Governors (one subnational card, children per state as listed) | Wikipedia local |
| 4 Oct 2026 | Paraguay | municipal | Wikipedia local |
| 4 Oct 2026 | Peru | regional and municipal (+ Lima Mayor child) | Wikipedia local; NDI |
| 8 Oct 2026 | United Kingdom | Holborn and St Pancras, House of Commons by-election (`national`, named jurisdiction) | Wikipedia local (was under "Tonga") |
| 9–10 Oct 2026 | Czech Republic | municipal | Wikipedia local |
| 24 Oct 2026 | Slovakia | regional and local | Wikipedia local (was under "Canada") |
| 25 Oct 2026 | Brazil | President (2nd round): **one** contest (ElectionGuide + Wikipedia + A-WEB umbrella by round) | — |
| 25 Oct 2026 | Serbia | National Assembly: one contest, `confirmed` (ElectionGuide `(d)`); NDI TBD and IPU don't count as independent confirmation | — |
| 5 Nov 2026 | Grenada | Parliament | Wikipedia national; IPU |
| 7 Nov 2026 | New Zealand | House of Representatives | Wikipedia national; IPU |
| 15 Nov 2026 | Cape Verde | President (EISA "October 2026" attached with `date_conflict`) | Wikipedia national; NDI |
| 15 Nov 2026 | Slovenia | local elections | OSCE |
| 29 Nov 2026 | Spain | Congress of Deputies, Senate | Wikipedia national; OSCE; IPU |
| 29 Nov 2026 | Switzerland | Referendums (one `referendum_day` grouping; no invented questions) | Wikipedia national |

## Appendix C — Fixture inventory (captured 2026-10-16, `.scratch/`)

| Path | Content |
|---|---|
| `pages/osce.html`, `eeas.html`, `carter.html`, `eguide.html`, `aweb.html`, `ipu.html`, `wiki_local.html`, `wiki_national.html` | Current source pages |
| `pages2/eg_upcoming.html`, `eg_past.html`, `eg_anticipated.html` | ElectionGuide full lists |
| `pages3/eisa.html`, `wiki_nat_2027.html`, `wiki_loc_2027.html`, `wiki_api_nat.html` (API wikitext JSON) | Calendar page and 2027 pages |
| `pages4/eisa_26151.json`, `eisa_34700.json`, `eisa_38978.json` | EISA Ninja Tables JSON (38978 = 2026 calendar) |
| `pages5/ndi.html` | NDI page 0 (both blocks) |
| `pages6/wiki_local_api.html` | Wikipedia API HTML, local 2026 (revid 1380378807) |
| `pages7/aweb_all.html` | A-WEB `option=all` (32 rows) |
| `hist/*.json` | 182 historical production feeds (pins, aliases, SC2 baseline) |
