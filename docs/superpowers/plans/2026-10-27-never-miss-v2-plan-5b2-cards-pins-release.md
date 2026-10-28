# Never-miss v2, Plan 5b-2: Extension cards, pins, safety and release — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Revision 3 (2026-10-27), APPROVED by the user on 2026-10-27.** **The open choices were
confirmed on 2026-10-28, and the execution method is subagent-driven** (see "Rulings on the open
choices (2026-10-28)"; rows marked **(2026-10-28)**). It is revision 2 plus a Task 2 addendum from the red-team
review of revision 2 (`Downloads/plan-5b2-r2-red-team-review-2026-10-27.md`, which reviewed
revision 2 at SHA-256 `f125ae38…`). Nothing else changes except one Task 7 mutation row:
- **N01:** the options page repaints pins only from a fresh storage read, guarded by a
  generation number, so a late reply or an older read never replaces a newer state (P141).
- **N02:** a rejected or unusable `PIN_EDIT` message is "not confirmed", not "not saved";
  the button is released and the page reconciles with storage (P141).
- **Task 7:** the `create_system` mutation forces 0, because Python's default is 0 only on
  Windows and 3 elsewhere, so "left at the default" would survive on Linux.

The rows changed in revision 3 are marked **(rev 3)**.

**Revision 2 (2026-10-27).** It answers the red-team review
of revision 1 (`Downloads/plan-5b2-red-team-review-2026-10-27.md`). All five findings and the eight
smaller corrections were checked against the code and accepted:
- **C01:** source lines name each source's claim, evidence kind and saved-data age (P143, Task 4).
- **C02:** the worker applies pin edits one at a time, and the options page shows pending, failed
  and saved states (P140, P141, Task 2).
- **C03:** `childDetails` is time-free; expanded entries reuse the view's labels, and the popup
  reads `now` once per render (P143, Tasks 1 and 4).
- **C04:** attention counts separate total, included, matched and shown items. The full list is
  named as `attention_full.json` in the run's `generation` artifact, kept 14 days (P144, Task 5).
- **C05:**
  - streaming is proven through `load.fetchLimited` with an endless body;
  - the ZIP is proven across different file times;
  - ZIP metadata is normalised, and reproducibility is scoped to one Python and zlib (P147, P148,
    Tasks 1 and 7).
- **The smaller corrections:**
  - a guarded `report`, and an end-to-end worker recovery test (P147);
  - a 25 s deadline (P147);
  - R56 inside an open popup (P139);
  - pins listed without a feed (P141);
  - Open-button names, focus after a redraw, "ARIA semantics" rather than "screen reader" (P146);
  - zoom wording;
  - the manifest test (P148);
  - ruling numbers (now those of the 5b-1 completion report).

The rows changed in revision 2 are marked **(rev 2)**.

**Revision 1 (2026-10-27).** Written against `eeffa31` (Plan 5b-1
complete: 2835 tests, mypy 169 files, ruff clean, `Contracts: 3 kept, 0 broken`).
- **Inputs:**
  - the discovery's 5b-2 outline (Tasks 7–13), `C:/Users/senescalk/Desktop/handovers/elections-v2-plan5b-discovery.md`;
  - Plan 5b-1's "Requirements for later plans" (R47–R52, R54–R61);
  - the user's completion review (2026-10-26) and decisions review (2026-10-27,
    `Downloads/plan-5b2-handover-decisions-and-reply-2026-10-27.md`), both checked against the
    code and recorded in `handovers/elections-v2-plan5b1-sdd-ledger.md`'s last two sections.
- **The seven corrections:**
  - R55 and R56 come first (Tasks 1–2), and R56 has its own P-row (P139);
  - R58 has a fixed owner (Task 1), split into a final error boundary, worker cleanup and recovery
    tests, and a real Chromium storage measurement (P147);
  - the ruling-8 case reuses the existing unknown-date text (P143);
  - Q1 has a deterministic fallback (P145), because an accepted path exists;
  - B2 gains its cached-F0 row (Task 1);
  - R47–R61 are mapped to tasks and tests in "Requirements traceability".
- **Nothing is implemented until the user approves this plan.** The semantic P-rows (P139–P146,
  P148) need that approval; Task 1 starts only after it. No merge, no push, no release.
- **Measured for this draft** (local headless Chromium, throwaway profiles, synthetic data, nothing
  left the machine): `.scratch/plan5b2/` `probe_r58.py`, `probe_r58b.py`, `probe_matrix.py`,
  `feed_facts.py`, `places_facts.py` and `facts2.py`, each with its `.txt` output. The results are in
  "As built" errata.

**Goal:** The extension shows each contest in full (children, sources, umbrellas, possible matches),
lists every item that needs attention, opens only safe links, and keeps v1.0.2's pins as places. It
works by keyboard and in a narrow or short popup (the automated stand-in for 200 % zoom; R63
checks the real popup). It ships as a checked, reproducible v2.0.0 ZIP that upgrades a v1.0.2
folder in place.

**Architecture:**
- **New pure modules** in `extension/lib/`: `links.js` (the §12.6 allowlist), `pins.js` (the
  place table lookups, the one-time migration, the parent rule, the options rows), `details.js`
  (a card's expanded rows) and `attention.js` (the attention section's rows). Like 5b-1's, they
  take everything as arguments. `pins.migratePins` gets its storage passed in, as `load.check` does.
- **`extension/places.json`** is generated from `data/places.yaml` by
  `scripts/build_extension_places.py`, with a sync test against `PlaceRegistry` (D3).
- **The worker** gains:
  - the pin migration (on install, update and startup, and on a `PINS` message);
  - **(rev 2)** the one queue that applies pin edits (`PIN_EDIT`);
  - a final error boundary in `load.check`;
  - request aborts and a streamed size cap (`load.fetchLimited`).
- **The renderers:**
  - `lib/render.js` gains expandable cards, source links and the attention section;
  - `lib/legacy.js` is rebuilt without `innerHTML` and opens only safe links;
  - `options.js` becomes a module that lists feed places and pins.
- **Release:** manifest 2.0.0, a new `help.html`, release notes, and
  `scripts/build_extension_zip.py`, which checks and builds a byte-reproducible ZIP.

**Tech Stack:** as Plan 5b-1:
- Chrome MV3, ES modules, no build step, no dependencies;
- Python 3.14.1, pytest 9, `playwright==1.64.0`, `pytest-playwright==0.10.0`;
- Chromium build 1248 (Chrome for Testing 156.0.8078.4), headless with `channel="chromium"`.

The ZIP is built with the standard library's `zipfile`. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-16-never-miss-v2-design.md`.
- Read these sections first:
  - §6.2 (places and minority aliases);
  - §12.3–§12.8;
  - §13.3 (S1-T8, S3-T17, S5-T10, T11, T15–T21, RT-06);
  - §15 step 7;
  - Appendix A (I1, I6, I9, I11).
- Plan 5b-1 (`docs/superpowers/plans/2026-10-26-never-miss-v2-plan-5b1-extension-core.md`) is in
  force: its Global Constraints and its P128–P138 still hold.
- Where this plan and the spec differ, the plan wins *only* for the items under "Spec corrections".

## "As built" errata (read first)

**Plan 5b-1** (built at `eeffa31`; record: `handovers/elections-v2-plan5b1-sdd-ledger.md`):
- **`lib/labels.js`:**
  - `childLabel(card, child, {today, now})` returns `{kind, text, chips, notes}`, where `chips` is
    a list of **strings** ("Tentative", "Subnational").
  - Note 3 (a selected fallback source) gives "Unverified: the source data's date is unknown" when
    one has `fetched_at: null`.
  - Note 4 ("Confirmed by source data from <date>") needs a dated held source. **A held child
    whose held sources are all fallbacks with no `fetched_at`, and which has no selected undated
    fallback, gets no note** (`labels.js:105-112`; ruling 8's remaining case).
  - `sourceNote(source)` gives the incomplete-fetch note; nothing shows it yet.
- **`lib/render.js`:**
  - `buildCard` builds flat cards with `textContent`, and sets the chip class from
    `chip.toLowerCase()`.
  - Cards open no link (R47). `test_v2_cards_show_labels_and_badges` clicks a card and asserts that
    no page opens (ruling 30).
  - `renderV2(feed, {pinned, today, now})` falls back to `doc.current_month` when the month is not
    in the window, and does no other check (Q1).
- **`lib/count.js`:**
  - `view(doc, {month, tab, level, query, pinned, today, now})` returns `{cards: [{card, children:
    [{child, label}], total, label, match}], records, groupings, held}`.
  - Its pin filter is `pinned.includes(card.country)` (R48).
- **`lib/health.js`:**
  - `classify(reasons, acknowledgements)` never compares `until` with `now` (R56).
  - `issues(doc)` and `panelRows({format, doc, status, linked})` take no `now`.
  - `bannerState(...)` takes `now`, and its row 7 text equals its counts ("7 warnings", R57).
- **`lib/load.js`:**
  - `check(deps)` says "Never rejects" but has no final catch.
  - `fetchFeed` runs `feedFormat` outside a `try`.
  - `withDeadline` races the request without aborting it, and the size check runs after the whole
    body is buffered (`background.js` `fetchBytes` reads `response.arrayBuffer()`).
  - `fail()` catches its own `set`, but reads `stored[KEYS.check]` from the object `get` returned.
  - **(rev 2)** A `get` that rejects is already handled: "could not read the stored data: …",
    and nothing is written. The unguarded paths run after `get`.
  - **(rev 2)** `REQUEST_TIMEOUT_MS = 30_000` comes from Plan 5b-1, not from the spec. Chrome's
    service-worker lifecycle documentation ends a worker whose `fetch()` response takes more than
    30 s to arrive.
- **`lib/worker.js`:** `alarm()` runs `await runCheck(); await ensureAlarm();`, so a rejected check
  skips `ensureAlarm` there. The three other paths call `ensureAlarm` first.
- **The popup:**
  - `popup.js` reads `pinned_countries` as display strings.
  - `body[data-renderer]` names the active renderer (ruling 27), and each render sets both bento
    labels (ruling 28).
  - v2 shares legacy's states and the pin bar ("Pinned view · n country/countries", ruling 29).
  - The banner and panel stay hidden until a feed is drawn (ruling 22).
  - **(rev 2)** `render()` reads `Date.now()` twice: once for `renderV2` and once in `drawHealth`.
    The popup renders on open and after each check it starts (on open when due, Refresh, Retry);
    there is no timer and no `storage.onChanged` listener.
- **`lib/legacy.js`:** v1.0.2's renderer. Its cards are `innerHTML` templates with `escHtml`, and
  its source chips and card body call `chrome.tabs.create({url})` with the feed's link as given
  (R52).
- **`options.js`** is v1.0.2's classic script, unchanged:
  - it reads `elections_cache` or sends `FETCH_DATA`, which the v2 worker ignores (R55);
  - it writes `pinned_countries` and `selected_countries` (D4);
  - it uses `innerHTML` for the pin icon and the "no data" text.
- **The harness** (`tests/support/extension.py`, `extension_page/fakes.js`):
  - `run_check(lab, *, feed, status, stored, now, set_fails, timeout_ms, schemas)`; its fake
    rejects only `set`s holding the feed key;
  - `runHandlers(spec)` logs each fake's start and end;
  - `Ext.open(path, now=PAGE_NOW)` fixes the context clock, and the clock stays installed for
    every later page of that context;
  - fixtures `ext`, `legacy_ext`, `fresh_ext` (its own launch; its clock is never fixed) and `lab`.
- **The manifest** is still `1.0.2`, with `"type": "module"` (P137).
  - **(rev 2)** `test_permissions_are_v1_0_2s` pops `background.type` and then asserts that the
    whole manifest equals v1.0.2's (`now == was`), so a new version or description fails it.
- **(rev 2) Ruling numbers** in this plan are those of the 37-item list in the Plan 5b-1
  completion report (2026-10-26), which the user's reviews use:
  - 8: note 4 needs a dated held source;
  - 9: the purity scan;
  - 17: the options page left on `FETCH_DATA`;
  - 22: no banner without data;
  - 27–30: one renderer, the bento labels, shared states, R47 tested;
  - 31: Q1 parked;
  - 35: m3 and m4 left for 5b-2;
  - 37: the deep-nesting gap parked into R58.

  The ledger's own entries are numbered per task, and `.scratch/plan5b2/rulings.txt` numbers them
  differently again; neither numbering is used here.

**The fixture pair** (`artifact_pair()`; `.scratch/plan5b2/feed_facts.txt`, `places_facts.txt`,
`facts2.txt`):
- **Size:** 100 cards, 202 children. Sources per child: one (160), two (21), three (14), four (5),
  five (2). Child source names: A-WEB, EISA, ElectionGuide, IPU, NDI, OSCE/ODIHR, Wikipedia.
- **Date conflicts (per-source dates):**
  - Cape Verde 2026-11-15, child `eae5cc187a1a`: ElectionGuide "2026-11-15 (d) to 2026-11-15 (d)"
    (selected), Wikipedia "15 November", NDI "November 15, 2026 (ALL DAY)", EISA "October 2026";
  - Nigeria 2027-01-16, House `dd48097e3357` and Senate `fcd8572f383a`: ElectionGuide (selected),
    Wikipedia "16 January", IPU "28 Feb 2027".
- **Possible matches (four children):**
  - Cameroon National Assembly: 2026-12 (month, `unknown`) ↔ 2027-01 (month, `expected_window`);
  - Kyrgyzstan: 2027-01-24 "2027 Kyrgyzstan Presidential Election" ↔ 2027-01-27 "Kyrgyz
    Presidency".

  No child has `possible_matches_outside` > 0, a `rescheduled_from` or a `provisional_date`.
- **(rev 2) Source claims and evidence** (schema `childSource`):
  - `status_claim` is one of `postponed`, `cancelled`, `disputed`, `held` or null; the fixture has
    only `held` (13);
  - `evidence_kind` is one of `calendar`, `expected_renewal`, `observation`, `umbrella`; the fixture
    has calendar 256 and expected renewal 18;
  - `fallback` and `fetched_at` give saved data and its age.

  `labels.js` uses `status_claim` only to pick "Possibly cancelled" or "Possibly postponed", and no
  line says which source made the claim. Tests for other claims edit the fixture, keeping it
  schema-valid.
- **Umbrellas:** 16 on 10 cards. Exactly one covers a strict subset: South Sudan 2026-12-22, where
  EISA "National Legislative Assembly" covers the Transitional National Legislative Assembly
  (`31ce89602954`) and the Council of States (`6f60dcabc9d2`), not the Presidency (`512ac66dc2b0`).
  NDI and A-WEB cover all three.
- **Attention:**
  - 157 items, `attention_truncated` 0, in feed order (not sorted by `item_id`). Longest text 161
    characters.
  - Kinds: `partial_unit` 63, `unparsed_unit` 58, `undated_listing` 31, `unresolved_evidence` 5.
  - `source` is the source **key** (wikipedia 131, osce 7, eeas 5, eisa 5, ipu 4, aweb 3, ndi 2),
    whereas cards and children carry display names.
  - One item has a possible match: `612356b9548b` (EEAS, Sao Tome and Principe, match
    `2b76c271e7be`, outside 1).
  - Four more have only an outside count: `36ad1dcad007` 4, `b98546e8d6db` 3, `c8534f5327a6` 3,
    `ed745bd6cbe3` 4.
  - **(rev 2) Where the full list is:** when items are cut, the producer writes every item to
    `attention_full.json` (`feed.py:506`, `pipeline.py:763`). That file is artifact-only
    (`ci/artifact.py` `ARTIFACT_ONLY`), so it is never committed. The workflow uploads it in the
    run's `generation` artifact, with `retention-days: 14` (`update-elections.yml:87-93`).
    `HEALTH.md` lists only the included items, plus "and N more in attention_full.json". The feed
    carries no run id.
- **Undated listings:** 31, one per `undated_listing` item. 15 places are in a listing only, among
  them Lesotho (`iso:LS`, "Parliament", 2027), Greece, Bahrain and Somaliland (`x:somaliland`, two
  listings, 2028).
- **Places:**
  - 58 distinct card places (97 `iso:` cards, 3 `x:` cards: Kosovo, South Ossetia `2026-09-18`,
    Transnistria `2026-12-13`). With the listing-only ones that makes 73.
  - Moldova has a card on 2026-11-15 ("Gagauzia: general election").
  - The largest cards are the United States 2026-11-03 (59 children) and Brazil 2026-10-04
    `c8c9844ab7a8` (18). Brazil has a second 2026-10-04 card, `54b356d5b5ea`, with 3 children.
- **Links:** every card, child, umbrella and listing link passes §12.6's allowlist by display name.
  Every item link passes by key. In the v1 feed, two A-WEB links fail: `focustaiwan.tw` and
  `pco.gov.ph`.

**The place registry** (`data/places.yaml`, `places_facts.txt`):
- 264 places and 487 aliases; the display is always one of the aliases.
- **13 places have a parent:** `iso:GB-SCT`, `iso:GB-WLS` → `iso:GB`; `iso:IN-PB` → `iso:IN`;
  `iso:PG-NSB` → `iso:PG`; `x:abkhazia`, `x:south-ossetia` → `iso:GE`;
  `x:cherokee-nation`, `x:cheyenne-and-arapaho-tribes`, `x:muscogee-creek-nation` → `iso:US`;
  `x:northern-cyprus` → `iso:CY`; `x:somaliland` → `iso:SO`; `x:transnistria` → `iso:MD`;
  `x:zanzibar` → `iso:TZ`.
  - The nine `x:` places have `country_code: null`, so D3's "match on `country_code`" fails, and
    the parent rule needs `parent`.
  - No parent has a parent.
- **All 90 strings in `data/feed_country_history.tsv`** (the real v1.0.2 pin strings) are exact
  aliases of registered places.
  - Six places have two history strings: Cabo Verde / Cape Verde, Democratic People's Republic of
    Korea / North Korea, Lao People's Democratic Republic / Laos, Philippines / The Philippines,
    Sao Tome and Principe / São Tomé e Príncipe, Viet Nam / Vietnam.
  - An exact-name table `{places: {id: {display, parent}}, names: {string: id}}` is 26,506 bytes.
- `elections_calendar.model.SOURCE_NAMES` maps the nine source keys to the display names above.

**Measured this session** (Chromium 156.0.8078.4):
- **R58, `feedFormat`** (`probe_r58.txt`, median of 7 on the 377,411-byte fixture feed):
  - `JSON.parse` 3.7 ms, `feedFormat` 26.8 ms, of which the legacy checks are 0.2 ms; the digest is
    0.9 ms.
  - So a single walk would save under 1 %. **Decision: keep the two walks.**
  - `feedFormat` returns `v2` with a 10,000-deep value under an unknown key; it never throws (the
    Node probe of 2026-10-26 agrees).
- **R58, real storage** (`probe_r58.txt`, `probe_r58b.txt`):
  - `chrome.storage.local.set` **resolves** for a deep value at any depth tried (up to 10,000).
  - `get` returns it **silently cut at depth 98**: below that, an array's leaf is `null` and an
    object's key is gone. Nothing rejects.
  - A round trip of the fixture feed changes **no value**, but returns every object's keys sorted.
    That is why the first probe's `JSON.stringify` comparison failed.
  - The popup renders a cached record holding a 10,000-deep unknown value: 30 October cards, no
    page error.
  - `JSON.stringify` throws `RangeError` at depth 10,000.
- **R51 baseline** (`probe_r58b.txt`, a launch whose clock is never fixed, the fixture pair cached,
  no check due): the popup reaches its ready state 205–318 ms after navigation starts.
  - Under a fixed context clock, `performance.now()` drifts (418 → 2737 ms in `probe_r58.txt`), so
    a timing test must use its own launch.
  - The `elections.json` request seen in the first probe was the install check: `Served.log`
    accumulates until `reset()`.
- **The renderer matrix's malformed cells** (`probe_matrix.txt`):
  - **v1.0.2's files:**
    - with `{not json`: the error state, "Could not load data: Expected property name or '}' in
      JSON at position 1 (line 1 column 2)";
    - with `{"schema_version": 2, "months": {}}`: **stuck on the loading state** with an uncaught
      "Cannot read properties of undefined (reading 'split')".
  - **The v2 files:**
    - "Could not load data: elections.json: not UTF-8 JSON";
    - "Could not load data: elections.json: unreadable feed: : missing content_id". The doubled
      colon comes from `schema.js:51`, which writes the root pointer as "" (fixed in Task 3).

## Plan series

1. **Foundations** (done, `8632297`).
2. **Sources:** 2a (done, `f5f3a1c`), 2b (done, `94ac45a`), 2c (done, `fa4d0a2`).
3. **Merge** (done, `6ba511b`).
4. **Health, snapshots, feed and publishing** (done, `2927bb0`).
5. **Workflow, extension and rollout:**
   - **5a:** run and publish (done, `319a292`);
   - **5b-1:** the extension core (done, `eeffa31`);
   - **5b-2: cards, pins, safety and release (this plan);**
   - **5c:** rollout and housekeeping (R41–R46, R53, F5, F6, Somalia, the RELEASES.md row,
     publishing v2.0.0).

**Not in this plan:**
- **Nothing leaves this machine.** No push, no workflow run on GitHub, no Store upload.
- Nothing is merged, and no release row is written in `RELEASES.md` (P148).
- The South Sudan alias (the user's, later), the Plan 3 I2 veto (no 5b-2 dependency), R37
  (parked).

## Global Constraints

Plans 1–5b-1's Global Constraints still hold:
- **Code:**
  - the layering (`Contracts: 3 kept, 0 broken`);
  - no network in tests;
  - `[0-9]`, never `\d`, in new regexes;
  - time is passed in;
  - pure modules stay pure;
  - civil dates are strings;
  - no defaults for fields Plan 4 always writes.
- **Extension:**
  - permissions do not change;
  - `DATA_URL` stays in `background.js` (R38);
  - the v1.0.2 keys are never written or removed;
  - copy is verbatim (including `–`, `—`, `·`).
- **Tests:** hermetic and deterministic, with `GIT_ALLOW_PROTOCOL=file`.
- **Git and process:**
  - work on `feat/never-miss-v2` only;
  - check the branch before every commit;
  - one mutation per new test;
  - each gate in its own shell call;
  - `.scratch/` for scratch files.

**This plan adds:**
- **The pure-module list grows.** `test_pure_modules_use_no_browser_api`'s `PURE_MODULES` gains
  `links.js`, `pins.js`, `details.js` and `attention.js`, under the same token rules (ruling 9 of
  Plan 5b-1).
- **No markup from strings anywhere in the extension.** Every `extension/**/*.js` file, including
  `lib/legacy.js` and `options.js`, contains none of `innerHTML`, `outerHTML`,
  `insertAdjacentHTML`, `document.write`, `DOMParser` and `createContextualFragment` (R60).
  `test_no_feed_text_through_inner_html_in_v2_code` checks this.
- **Links open only through `links.safeLink`.**
  - Every `chrome.tabs.create` call for a feed link takes `safeLink`'s result. When that result is
    `null`, nothing opens.
  - The only other `chrome.tabs.create` calls are `help.html`'s.
- **`extension/places.json` is generated, never hand-edited.** `scripts/build_extension_places.py`
  writes it, and `test_places_table_matches_the_registry` proves it current.
- **Pins:**
  - **(rev 2) Only the worker writes the pin keys:** the migration, and every later edit through
    its single `PIN_EDIT` queue.
  - The options page asks the worker and never writes storage. The popup never writes a pin key.
  - `pinned_countries` is read once, by the migration, and never written.
- **The ZIP's file list is explicit** (`build_extension_zip.FILES`). Every file under `extension/`
  is in it, and the ZIP holds nothing else.
- **Layout tests open `popup.html` as a tab with a set viewport.** The real action popup is not
  driven (discovery Step 1).
  - **(rev 2) A surrogate, not a measurement.** Chrome caps an action popup at 800 × 600. At 200 %
    zoom that cap would be 400 × 300 CSS pixels, if it applies before zoom. That is reasoning and
    has not been measured.
  - So a 380 × 300 viewport stands in for 200 % zoom, and 320 × 600 for "narrow".
  - The real popup at 200 % is R63's manual check before release, and nothing in this plan claims
    more than the surrogate.

## Review Focus

These are the five inputs most likely to hurt a reader that the spec implies but no step spells
out. Each is pinned by the named tests, in the task that owns the code.

1. **A v1.0.2 user's real pins across versions.** The pins include a minority alias ("Cabo
   Verde"), a subdivision that appeared as a country ("Scotland (part of the United Kingdom)"), a
   string the table does not know, a non-string and `"constructor"`. Then: a pin deleted after the
   migration; a rollback to v1.0.2 (which edits `pinned_countries`) and back; a corrupted
   `pinned_places_v2`.
   - **What happens:**
     - the migration runs once;
     - a deleted pin stays deleted;
     - the v1 keys stay byte-equal;
     - unknown strings show as unresolved and never filter;
     - a bad stored value counts as no pins and never crashes.
   - **(rev 2) Then two options pages edit at once.** One removes Cape Verde while the other adds
     Lesotho; one save is rejected and then retried.
     - Neither edit is lost, and a removed pin never comes back.
     - A rejected save is reported, and the button shows the stored state.
     - Every open page ends up showing what is stored.
   - **(rev 3) Then a reply arrives late, or never.** A's reply is held until B's edit is
     stored and shown; a reply is lost before or after the save.
     - A late reply or an older read never repaints an older state.
     - A lost reply says the change could not be confirmed, releases the button, and shows
       what is stored; it never undoes a saved edit.
   - **Pinned by** `test_pin_migration`, `test_every_v1_pin_string_migrates`,
     `test_pins_survive_and_filter_the_popup`, `test_pin_edits_are_applied_in_order`,
     `test_two_options_pages_edit_pins` (Task 2) and `test_real_zip_same_folder_upgrade` (Task 8).
2. **Hostile or odd links, in both renderers and the attention section:**
   - `javascript:`, `data:`, `http:`;
   - user info, a port other than 443;
   - a lookalike host (`en.wikipedia.org.evil.example`, `evilwikipedia.org`), an upper-case host,
     a punycode host;
   - an empty or relative URL, a non-string;
   - a source the table does not know;
   - v1's off-allowlist A-WEB links.

   **What happens:** the source's home page opens, or nothing does (unknown source). Never the
   raw URL. **Pinned by** `test_safe_links` (Task 3), `test_legacy_opens_only_safe_links`
   (Task 3), `test_source_entries_open_only_safe_links` (Task 4) and
   `test_attention_links_are_safe` (Task 5).
3. **A format change while the popup is open,** through successful checks (legacy → v2 → legacy →
   v2), with a search typed, a card expanded and the attention section open.
   - **What happens:**
     - one renderer answers the controls;
     - no element of the other format remains;
     - the tab highlight, the cards and the counters agree;
     - the attention section shows only for v2.
   - **Pinned by** `test_renderer_switches_inside_one_popup` (Task 3, extended in Tasks 4–5).
4. **A zoomed or narrow popup** with a long health panel (10 source issues), an expanded card with
   27 children, the attention section open and a two-line footer.
   - **What happens:**
     - nothing scrolls sideways;
     - every control can be scrolled into view and is not covered by the footer or the tabs;
     - everything is reachable by keyboard;
     - focus is visible.
   - **Pinned by** `test_layout_in_a_narrow_or_short_popup` and
     `test_keyboard_and_aria_semantics` (Task 6). These are automated layout, keyboard and ARIA
     checks; no screen reader is run.
5. **A check that throws, hangs or streams without end.**
   - **What happens:**
     - it settles as a failed check with a bounded message;
     - the request is aborted;
     - the stored pair is kept;
     - the alarm is still ensured;
     - the next normal check succeeds;
     - a failure that cannot be saved still settles;
     - **(rev 2)** in the real worker, the popup leaves its checking state and the in-flight check
       is released.
   - **Pinned by** `test_an_unexpected_error_fails_the_check`,
     `test_a_failure_that_cannot_be_saved_still_settles`,
     `test_the_alarm_is_kept_when_a_check_rejects`, `test_a_hung_request_is_aborted`,
     `test_a_body_is_read_up_to_its_limit`, `test_the_real_fetch_reads_a_bounded_body` and
     `test_the_worker_recovers_after_an_unexpected_failure` (Task 1).

**Known limits, by design.** Each is visible:
- **The real action popup is not driven.** Layout is tested on `popup.html` in a tab at the
  viewports above. Chrome's own popup sizing under zoom is not measured.
- **Chrome's Reload button is not driven** (R49). The same-folder upgrade relaunches the browser
  on the same profile, which reports `install`. The `update` path is tested through
  `lib/worker.js`.
- **(rev 2) The real worker's 25 s abort is not waited for.**
  - `load.check`'s abort is tested on fakes with a short deadline, and `load.fetchLimited` passes
    the signal to the `fetch` it is given.
  - Which comes first in real Chrome is not measured: our 25 s abort, or Chrome ending a worker
    whose `fetch()` response takes more than 30 s.
  - If Chrome ends the worker first, nothing is recorded. The popup's message rejects, so the popup
    leaves its checking state. The next opening or alarm checks again, because nothing marks a
    check as running in storage.
- **Storage keeps no deep values:** `get` cuts nesting at depth 98 under an unknown key (measured
  in Chromium 156, not a documented limit). The client never reads unknown keys, the stored digest
  stays the received bytes' digest, and the popup renders. So this is recorded, not handled.
- **Pin lookup is exact.** A pin string that is not exactly an alias stays unresolved. Every
  recorded v1 pin string is exact (measured).
- **Pins changed in v1.0.2 after the migration** (a rollback, then an upgrade again) are not
  migrated again. The release notes say so.

## Spec corrections

These were found while measuring the fixtures, the registry and the browser, and while reconciling
the spec, the 5b-1 code and the two user reviews.
- **Semantic decisions** change what a reader sees or what the client accepts: P139–P146 and
  P148. **They need the user's approval before Task 1 starts.**
- **P147** refines interfaces and error handling, and records a measurement.

| ID | Spec says | This plan does | Why / alternative |
|---|---|---|---|
| P139 (semantic; R56; §9.6, §12.2) | §9.6: an acknowledgement is in effect while `acknowledged_at <= now < expires_at`. §12.2 and P133 do not say what the client does when one ends | <ul><li>**In effect while `now < until`**, comparing instants (`parseTimestamp(until)` with the popup's `now` in ms). The comparison has no time zone; only the date shown is local, as every other stamp in the popup (`stampDate`). The exact `until` instant ends it (NM-T07's boundary). The feed carries no `acknowledged_at`, and the producer publishes only acknowledgements in effect at generation (`health.py:489-491`).</li><li>**Matching:** in-effect acknowledgements are matched first, one-to-one on code, stage, year and page. Ended ones are then matched against the reasons still unmatched.</li><li>**A reason matched only by an ended acknowledgement counts at its own level:** error → P133 row 3, warning → row 7. It is not among "N acknowledged".</li><li>**Panel line** for it: `<reason text> (acknowledgement ended <stampDate(until)>)`. An in-effect one keeps `<reason text> (acknowledged until <stampDate(until)>)`.</li><li>**The banner, the counts and the panel** take the same `now`, so they always agree.</li><li>**(rev 2) When `now` is read:** once per render, by `render()`, which passes it to the cards (`renderV2`) and to `drawHealth`. The popup renders on open and after every check it starts (on open when due, Refresh, Retry). It has no timer, so a popup left open across `until` changes at its next render, not at the instant.</li></ul> | Alert correctness (the user, 2026-10-26). An ended acknowledgement must not mute an error or warning on cached data. Keeping the line, worded as ended, shows that an acknowledgement existed. Alternative: hide ended acknowledgements entirely; keep them muted until the next feed (the stale banner shows after 36 h) |
| P140 (semantic; §12.6 pins; D3, R48) | §12.6: read `pinned_countries` (untouched), map through the alias table, write `pinned_places_v2` and verify, set `pins_migrated_v2`; unmappable names are "unresolved pins"; deleted pins stay deleted; a parent pin includes its subdivisions | <ul><li>**`extension/places.json`** is `{"names": {<every alias, exactly as written>: place_id}, "places": {place_id: {"display": …, "parent": … or null}}}`. Keys are sorted, separators compact, UTF-8 without escapes, with a final newline. It is generated from `data/places.yaml`: 264 places and 487 names, about 26.5 KB.</li><li>**Lookup is exact** (`Object.hasOwn`), so `"constructor"` and `"__proto__"` never resolve.</li><li>**Migration, once:**<ul><li>Each string of `pinned_countries` goes through `names`.</li><li>Place ids are deduplicated in first-seen order: "Cabo Verde" and "Cape Verde" make one `iso:CV`.</li><li>Unknown strings go to `unresolved_pins_v2`, deduplicated and in order. Non-strings are dropped. A `pinned_countries` that is not a list counts as empty.</li><li>`pinned_places_v2` and `unresolved_pins_v2` are written in one `set` and read back. If they read back equal, `pins_migrated_v2: true` is set. Otherwise the error is reported, and the next run tries again.</li></ul></li><li>**Only the worker migrates:**<ul><li>on `onInstalled` (any reason) and `onStartup`, before `ensureAlarm`;</li><li>on a `{type: "PINS"}` message, one run at a time.</li></ul>A migration failure is logged and never stops the check.</li><li>**The popup never writes pins.** Until the flag is set, it derives the same result in memory.</li><li>**(rev 2) Later edits go through the worker, one at a time.**<ul><li>The worker keeps one queue (a promise chain) for `{type: "PIN_EDIT", op, value}`. `op` is one of: `pin` (a place id), `unpin` (a place id) or `forget` (an unresolved string).</li><li>Each edit, in arrival order:<ol><li>runs the migration first if the flag is not set;</li><li>reads the pin keys as they are now;</li><li>applies the op. `pin` appends the id when absent; `unpin` and `forget` remove the value when present, so each op is idempotent;</li><li>writes the changed key in one `set` and reads it back;</li><li>replies `{ok: true, pins: {places, unresolved}}`.</li></ol></li><li>**Failures** reply `{ok: false, error}`, where `error` is one of: "could not read the pins: <message>", "could not save the pins: <message>", "the saved pins could not be verified" or "not a pin" (a value that is not a non-empty string). The queue moves on, and the next edit reads storage afresh.</li><li>**Two edits of the same pin** apply in arrival order, so the later one wins.</li></ul></li><li>**Once the flag is set, `pinned_countries` is never read again.** A stored `pinned_places_v2` or `unresolved_pins_v2` that is not a list of strings counts as empty.</li><li>**The parent rule:** a pin matches a place when it is that place or one of its ancestors through `parent`, following at most 8 steps. A place id the table does not know matches only itself.<ul><li>So pinning Georgia also shows Abkhazia and South Ossetia (the fixture's 2026-09-18 card).</li><li>Moldova also shows Transnistria; Cyprus, Northern Cyprus; Somalia, Somaliland; Tanzania, Zanzibar; the United States, its three tribal nations.</li><li>The United Kingdom also shows Scotland and Wales; India, Punjab; Papua New Guinea, its `iso:PG-NSB` place.</li></ul>This is the registry's §6.2 structure. The options page names the included places (P141).</li><li>**Unresolved pins never filter the popup.**</li><li>**The pin bar counts pinned places,** with ruling 29's copy: "Pinned view · n country/countries".</li><li>**Legacy feeds:** each card's `country` goes through `names` before the parent rule.</li></ul> | D3 (approved): the feed carries no aliases. `country_code` cannot carry the parent rule, because the nine `x:` places have none (measured). Migrating only in the worker means no two contexts race, so a deleted pin cannot come back. **(rev 2)** With one queue applying each intent to the current state, two options pages cannot lose each other's edits (the red-team review's C02). A page writing its whole list would, and so would one re-reading before each write. Alternatives: normalised lookup (`norm_name`), which no recorded pin needs; migrating in every page |
| P141 (semantic; §12.6 options; D4, R55) | §12.6: "Options list: feed places plus saved pins"; D4: drop the dead "selected countries" UI | <ul><li>**The options page asks the worker first:** it sends `{type: "PINS"}`. It shows and edits pins only when `pins_migrated_v2` is true afterwards. Otherwise it shows "Your pins could not be prepared: <error>. Reload this page to try again."</li><li>**It then lists** the places of the stored `elections_cache_v2` record, validated as the popup does:<ul><li>`v2`: every card's and every undated listing's `place_id`;</li><li>`legacy` and `update_needed`: each card's `country` through `names` (unmapped names are left out).</li></ul>Saved pins are added. That is 73 rows on the fixture: 58 card places and 15 listing-only places, Lesotho among them.</li><li>**With no valid record,** it sends `{type: "CHECK"}` and reads again. If there is still none, it shows "No election data is available yet. Open the popup to load it, then come back here." **(rev 2)** That text sits above the list. The saved pins and the unresolved pins are still listed and editable; only the feed's places are missing.</li><li>**(rev 2) Editing:**<ul><li>Each click sends one `PIN_EDIT` (P140).</li><li>Until the reply, that button has `aria-busy="true"` and is disabled. Other buttons stay usable, and their edits queue behind it.</li><li>**(rev 3) One way to repaint.** The page draws pins only through `reconcile()`:<ul><li>each call takes the next generation number and reads the pin keys with one `get`;</li><li>it draws only if no later `reconcile()` has started, so an older read is dropped;</li><li>it runs after every reply, after every failed message, and on every `chrome.storage.onChanged` for the pin keys;</li><li>a reply's `pins` are never drawn.</li></ul>The feed's places are read once, on load.</li><li>**(rev 3) Pending state** is kept per value (the place id or the unresolved name), outside the drawing, and every draw re-applies it.</li><li>**(rev 3) `body[data-pin-sync]`** is "busy" while an edit or a `reconcile()` is in flight and "idle" otherwise, like the popup's `data-checking`.</li><li>**(rev 3) Replies.** In every case the button's pending state ends, then `reconcile()` runs. `#pinStatus` (`role="status"`) reads:<ul><li>`{ok: true}`: empty;</li><li>`{ok: false, error}`, a failure the worker reports: "Your change could not be saved: <error>. Try again.";</li><li>a rejected `sendMessage`, or a reply that is neither: "Your change could not be confirmed: <message>. The list shows your saved pins." The message is the rejection's, or "no usable reply".</li></ul>The page never undoes an edit because its reply was lost: the stored state is what it shows.</li><li>**(rev 3) A failed read** keeps the last drawing, and `#pinStatus` reads "Your saved pins could not be read: <error>. Reload this page to try again."</li><li>`options.js` calls `chrome.runtime.sendMessage` at each send, with no saved reference.</li><li>Every open options page listens to `chrome.storage.onChanged` for the pin keys and reconciles. That keeps other pages current; the worker's queue, not the event, keeps edits from being lost.</li></ul></li><li>It never reads `elections_cache` and never sends `FETCH_DATA`.</li><li>**Names:** the table's `display`, else the feed's `country`, else the place id.</li><li>**Order:** pinned rows first, then the rest, each by name (`localeCompare(…, "en")`).</li><li>A row whose place has places below it in the table adds "Also shows: <their display names, sorted, joined ", ">".</li><li>**Unresolved pins** get their own list, each with a Remove button.</li><li>**No checkboxes and no Select All, Clear All or Save** (D4). `selected_countries` stays as it is.</li><li>**Copy, verbatim:** the table under Task 2.</li></ul> | R55: v1.0.2's page lists nothing on a fresh install, and a frozen v1 list after an upgrade. The page must not edit pins before the migration, or the migration could overwrite the edit. **(rev 2)** Preferences stay editable without election data. A rejected save is shown, never silently accepted (C02). **(rev 3)** Replies and storage events arrive on different channels in no fixed order, so painting from both lets a late reply undo a newer state. One guarded path through storage cannot. A lost reply may follow a save, so it is "not confirmed", never "not saved" (the r2 review's N01, N02). Alternative: the page migrates by itself (two writers) |
| P142 (semantic; §12.6 links; R52) | §12.6's allowlist by source; `https`, no user info, port empty or 443, host equal to an allowed host or ending in "." + one, else "the source's home page"; v2 and legacy alike | <ul><li>**`links.SOURCES`** has nine rows: `key`, `name` (as `SOURCE_NAMES`), `hosts` (§12.6) and `home`.</li><li>**The home pages:** `https://www.electionguide.org/`, `https://en.wikipedia.org/`, `https://www.ndi.org/`, `https://odihr.osce.org/`, `https://data.ipu.org/`, `https://www.aweb.org/`, `https://www.eisa.org/`, `https://www.cartercenter.org/`, `https://www.eeas.europa.eu/`. Each passes its own allowlist.</li><li>**A source is found by key or by display name.** Cards, children and v1 use names; attention items use keys.</li><li>**`safeLink(source, url)`:**<ul><li>an unknown source gives `null`: no link, the name shows as plain text;</li><li>otherwise it parses `new URL(url)` with no base. When the protocol is `https:`, the username and password are empty, the port is `""` and the hostname is allowed, the result is `parsed.href`;</li><li>anything else, including a parse error or a non-string, gives the home page.</li></ul></li><li>**Also,** a schema problem at the document's root reads "/: …" (for example "unreadable feed: /: missing content_id"), as the legacy checks already write it.</li></ul> | §12.6 names no home pages, and says nothing about a source outside the table, where no home page exists. Alternative: open an unknown source's URL when it is `https:` (an open redirect for a new producer source) |
| P143 (semantic; §12.3 cards; R25, R22, R47, ruling 8) | §12.3: per-child labels; "per-source dates in the expanded view"; chips Tentative, Subnational, "Rescheduled from <date>", "newer data from an incomplete fetch on <date>"; children render on expand (§12.7) | <ul><li>**Each card gets a disclosure button:** "Show details" / "Hide details", with `aria-expanded` and `aria-controls="details-<group_id>"`.</li><li>**The details are built on the first expand.** A redraw while a card is open rebuilds them. Open cards are remembered by `group_id` for the popup's life, so a search or a tab change does not close them.</li><li>**The details list the kept children** (those passing the filters). Each child shows:<ul><li>the heading;</li><li>its label, chips and notes. **(rev 2)** These are the kept child's `label` from the same `count.view` call that drew the card face, so face and entry share one `today` and one `now`. `childDetails` takes no time and returns no label;</li><li>one line per source (**rev 2**). The line is `<name>: <date_text>`, then " (used)" on the selected source, then each tag as " · <tag>", in this order:<ul><li>the claim: `status_claim` `held` → "reports it held", `postponed` → "reports it postponed", `cancelled` → "reports it cancelled", `disputed` → "reports it disputed";</li><li>the evidence: `evidence_kind` `expected_renewal` → "expected renewal, not an announced date", `observation` → "observation mission dates", `umbrella` → "a listing covering several contests"; `calendar` adds nothing;</li><li>saved data: `fallback` true → "saved data from <stampDate(fetched_at)>", or "saved data, date unknown" when `fetched_at` is null;</li><li>its `sourceNote`, when it has one.</li></ul>For example: "NDI: 15 November 2026 · reports it postponed". The line ends with an Open button when `safeLink` gives a link;</li><li>for each umbrella that covers it, "Also listed by <name>: <office_label>, <date_text>", with an Open button;</li><li>its possible matches.</li></ul></li><li>**The heading** is `office_label`, then " · <jurisdiction>" when `jurisdiction` is not null and `office_label` does not contain it (case-insensitive), then " · Round <n>" when `round` is not null, then " · Indirect" when `indirect` is true.</li><li>**A possible match:** "Provisional: may be the same contest as <country> <office_label>, <when>". `<when>` is `dayMonthYear` for a day date, `monthYear` for a month date, or the year. An id not in the feed gives no line.</li><li>**Matches outside the window:** "Provisional: <n> possible match(es) outside the monitored window", written "match" for 1 and "matches" otherwise.</li><li>**Chips become `{kind, text}`.** Kinds are `tentative`, `subnational` and `rescheduled`. The rescheduled chip reads "Rescheduled from " + `rescheduled_from` joined with ", ", and shows whenever the list is not empty.</li><li>**The card face shows the kept children's chips,** deduplicated by text, in first-seen order.</li><li>**Ruling 8:** a `held` child whose held sources are all fallbacks with `fetched_at: null` gets "Unverified: the source data's date is unknown", once, even when note 3 already gave it.</li><li>**The card body still opens nothing** (ruling 30). Only Open buttons open links.</li><li>**(rev 2) Open buttons are named** `Open <name> for <heading> (new tab)` for a source line, and `Open <name> (<umbrella office_label>) for <heading> (new tab)` for an umbrella line. `<heading>` is the child's. One umbrella covering 18 children therefore gives 18 different names.</li></ul> | The spec shows the label table, not the expanded view. Showing every source's own date text makes `date_conflict` visible without new rules. **(rev 2)** The claim and evidence tags say which source reports what. A raw date cannot, because two sources with the same date may still disagree on the status (the red-team review's C01). Reusing the view's label keeps one set of label rules and one snapshot of time (C03). The per-child umbrella rule is R25's. Alternative: show the selected source only (hides the disagreement) |
| P144 (semantic; §12.4; R50) | §12.4: above the empty state and the list on every month, "N items across the monitored window (Sep–Jan)"; text, source, link, provisional matches; never hidden by filters; a search shows "k of N"; "Showing 500 of N; the full list is in the run report"; at most 200 before "show more" (§12.7) | <ul><li>**The section `#attention`** sits between the filter bar and the states, for a `v2` feed only. It is hidden for `legacy` and `update_needed`, and with no data (ruling 22's rule).</li><li>**It is collapsed by default.** Its toggle button reads the title and carries `aria-expanded`.</li><li>**(rev 2) Four counts, kept apart:**<ul><li>the total N = `attention_items.length + attention_truncated`;</li><li>the included A = `attention_items.length`;</li><li>the cut T = `attention_truncated`;</li><li>the matched k (with a search) and the shown d (rows rendered).</li></ul>The months are the window's first and last, as three-letter names joined by "–". One month gives "(Oct)"; no months gives no parentheses. 1 gives "item".</li><li>**Only the popup's search box filters the section:** it matches an item's text, its source's name, and its listing's country and office. Pins, level, tab and month never filter it.</li><li>**The toggle's text (rev 2):**<ul><li>no search: "N items across the monitored window (Sep–Jan)";</li><li>a search with T = 0: "k of N items across the monitored window (Sep–Jan)";</li><li>a search with T > 0: "k of the A items in this data match (N in total, Sep–Jan)".</li></ul></li><li>**(rev 2) When T > 0,** `#attentionNote` shows below the toggle, whether the section is collapsed or open: "This data includes A of the N items. The other T are in attention_full.json, in the "generation" artifact of the GitHub Actions run that published it (kept 14 days). Searches here do not cover them."</li><li>**(rev 2) Shown rows:** while open and d < m (m = k with a search, else A), a line "Showing d of m" sits above the more button. A change to the search resets d to 200.</li><li>**Each row:**<ul><li>the item's text;</li><li>its source's display name;</li><li>"Undated: <country>, <office_label>, <year>" when it has an undated listing;</li><li>its possible-match lines (P143);</li><li>an Open button through `safeLink(item.source, item.link)`, named `Open <source name>: <text cut to 80 characters> (new tab)` (**rev 2**).</li></ul></li><li>**At most 200 rows** are rendered. A "Show 200 more" button (or "Show <k> more" for the rest) adds the next ones.</li><li>**The count is the toggle's own text,** in the section under the list header. `#recordCount` never counts items: this is R50's "own count".</li><li>Its open state is kept within the popup.</li></ul> | Collapsed keeps the cards visible while the count stays on every month. The search reads the fields a reader sees. **(rev 2)** A search over the included items cannot speak for the cut ones, so the copy says what was searched (the red-team review's C04). The spec's "Showing 500 of N; the full list is in the run report" mixed included and shown items and named no file. The file, artifact and retention are the producer's own (errata). Alternatives: open by default; filter items by pins through their possible matches (most items have none) |
| P145 (semantic; Q1; §12.5) | §5: `current_month` is in the window (a producer guarantee; the client does not check it) | **`count.startMonth(doc, today)`** gives the first of these that applies: `current_month` if it is in `window.months`; else today's month if it is in the window; else the window's first month; else `current_month` (an empty window, which shows the empty state). The popup opens on it, and keeps the reader's month while it stays in the window | An accepted path exists: neither `validate.js` nor the publish gate checks it, and a hand commit to `main` would give an empty view. Alternative: refuse the feed (it is valid by the schema) |
| P146 (semantic; §12.7, R59) | §12.7: `aria-expanded` disclosures, tabs with `aria-selected` and matching panels, visible focus; tested at narrow width and 200 % zoom with 10 source issues and 27 expanded children; bounded rendering | <ul><li>**Tabs:**<ul><li>`#tabs` gets `role="tablist"` and `aria-label="Show"`, and each tab gets `role="tab"`, `aria-selected`, and `aria-controls="listPanel"`.</li><li>A roving `tabindex`: 0 on the selected tab, −1 on the others.</li><li>ArrowLeft and ArrowRight (wrapping), Home and End select and focus a tab.</li><li>The states and the list sit in `<div id="listPanel" role="tabpanel">`, whose `aria-labelledby` names the selected tab.</li><li>The legacy renderer sets the same attributes.</li></ul></li><li>**Disclosures:** the banner, `#filterToggle` (`aria-controls="filterBar"`), the card toggles and the attention toggle all carry `aria-expanded`.</li><li>**`#recordCount`** gets `aria-live="polite"`.</li><li>**Focus:** `:focus-visible` gives every button, input, select and link a 2 px outline in `var(--primary)`, offset 2 px. No rule removes an outline without a replacement.</li><li>**(rev 2) Focus survives a redraw.**<ul><li>Each focusable control the renderers build carries a `data-focus` key: `tab:<name>`, `toggle:<group_id>`, `open:<child_id>:<n>`, `umbrella:<child_id>:<n>`, `attention-toggle`, `attention-open:<item_id>` or `more`.</li><li>A render notes the focused key. After drawing, it focuses the element with the same key; if that element is gone, it focuses `#listPanel` (`tabindex="-1"`).</li><li>A render that finds focus outside the list (the search box, Refresh) leaves it alone.</li></ul></li><li>**Layout:**<ul><li>The footer and the bottom nav move into `<div class="dock">`, at the end of the body's flex column and in the flow, not `position: fixed`. The list's 96 px bottom padding goes, so a footer of any height ends the list above it (R59).</li><li>Under `@media (max-height: 520px)`, the body is no longer a fixed-height column: the document scrolls, and `.dock` is `position: sticky; bottom: 0`.</li><li>`body` width is `min(380px, 100vw)`, and long words wrap (`overflow-wrap: anywhere`).</li></ul></li></ul> | At 200 % zoom the fixed 600 px body with `overflow: hidden` leaves a 300 px viewport in which the fixed dock covers most of the list. Alternatives: keep the fixed dock and pad the list by a measured height (needs a resize observer) |
| P147 (interfaces; R58) | — | <ul><li>**`load.check`'s final boundary:** any exception after the start becomes a failed check. The error reads "the check failed unexpectedly: <message>", with the message cut to 200 characters and "…" added when cut. It is recorded like other failures (`ok_at` kept, `failed_at` = now). The raw error goes to `deps.report` (the worker passes `console.error`). Recording the failure cannot throw again, so the check always settles.<ul><li>**(rev 2) Recording rule:** the boundary re-reads `check_state_v2` through `deps.get`, because the first read's result may be what failed. It keeps a finite `ok_at` from that read and writes `{ok_at, failed_at: now, error}`. When that read or the write fails, it writes nothing.</li><li>**(rev 2)** `deps.report` runs inside its own `try`, so a throwing report cannot escape either.</li></ul></li><li>**`worker.alarm`** runs `ensureAlarm` in a `finally`.</li><li>**Request limits:**<ul><li>each request gets an `AbortController`, and the deadline aborts it. **(rev 2)** `REQUEST_TIMEOUT_MS` becomes 25 000, leaving headroom below Chrome's 30 s `fetch()` limit for workers (errata);</li><li>`deps.fetchBytes(url, {signal, limit})`;</li><li>**(rev 2)** the real `fetchBytes` is `load.fetchLimited(fetchImpl, url, {signal, limit})`. It calls `fetchImpl(url, {cache: "no-store", signal})`, throws `HTTP <status>` when the response is not ok, and returns `readLimited(response, limit)`. `background.js` binds it to the global `fetch`, so tests can hand it a fake `fetch`;</li><li>`readLimited(response, limit)` stops and cancels the stream as soon as it passes `limit`, with `OverLimit` and the error "over the limit of <limit> bytes";</li><li>the aborted request's own rejection is handled, so there is no unhandled rejection.</li></ul></li><li>**The post-buffer size check stays** for fakes and as a backstop. Its text becomes the stream's: "<name>: over the limit of <limit> bytes", so one condition has one message. A stopped stream does not know the total size. `test_check_records_failures_and_keeps_the_cache`'s row "elections.json: 4000001 bytes is over the limit of 4000000" changes to match. **(rev 2)** Because of this backstop, no end-to-end oversize test can tell streaming from buffering. Streaming is proven by `test_the_real_fetch_reads_a_bounded_body` (an endless body through `fetchLimited`).</li><li>**One walk or two:** two (errata: the legacy checks are under 1 % of `feedFormat`).</li><li>**Storage:** measured, nothing changes (errata). `test_a_deeply_nested_unknown_value_is_stored_safely` pins the outcome without pinning Chrome's depth.</li></ul> | The user's decisions review: a final error boundary, worker cleanup and recovery tests, and a real storage measurement, each with its own acceptance. A monkeypatched rejection tests the client's handling, while the real-storage test measures Chrome. Alternative: a depth limit in `feedFormat` (no reachable failure needs one) |
| P148 (semantic; §12.8) | §12.8: version 2.0.0 and a new description; help (banner, chips, 10 sources, 5 months, update instructions); the ZIP from an explicit list with four checks; "It records the SHA-256 in `RELEASES.md`"; release notes | <ul><li>**The manifest:** `"version": "2.0.0"`, `"description": "Global elections month by month from 10 monitoring sources, with data health checks, honest date labels and items to review."` (124 characters; Chrome's limit is 132).</li><li>**The ten sources** are the ten adapters of §7: ElectionGuide, Wikipedia (national calendar), Wikipedia (local calendar), NDI, OSCE/ODIHR, IPU, A-WEB, EISA, Carter Center, EEAS.</li><li>**The ZIP** is byte-reproducible: entries in `FILES` order; each dated 1980-01-01 00:00:00 with mode 0644; `ZIP_DEFLATED` at level 9; no directory entries.<ul><li>**(rev 2) Metadata is normalised:** every entry has `create_system = 3` and `external_attr = 0o100644 << 16`, whatever the build platform. Python sets `create_system` to 0 on Windows by default.</li><li>**(rev 2) The promise is scoped:** identical bytes for one Python minor version and one zlib version. `main()`'s printed row names `platform.python_version()` and `zlib.ZLIB_RUNTIME_VERSION`. Deflate output may differ across zlib versions, and nothing here claims otherwise.</li></ul></li><li>**(rev 2) The manifest test:** `test_permissions_are_v1_0_2s` also pops `version` and `description`, then still compares every other field with v1.0.2's. `test_the_manifest_is_2_0_0` checks those two fields.</li><li>**`build_extension_zip.py` prints the `RELEASES.md` row and does not write it.** The row needs the release's code SHA, date and approval (`RELEASES.md`: "recorded here by hand, with the user's approval"), so 5c writes it at release.</li><li>**The release notes** are `docs/extension/v2.0.0-release-notes.md`.</li><li>D7 stands: help opens on install only.</li></ul> | `RELEASES.md` (Plan 5a) and §12.8 differ on who writes the row. The ZIP of an unreleased commit is not a release. Alternative: the script writes the row now, and 5c edits it |

## Requirements traceability

Every requirement 5b-2 owns, with its exact text where an earlier plan gave one. **Disposition:**
"ships" = in the v2.0.0 ZIP; "test" = test or harness only; "process" = recorded, no code.

The texts name the discovery outline's task numbers. They map to this plan's tasks as follows:

| Discovery task | This plan |
|---|---|
| 7 (cards) | T4 |
| 8 (attention) | T5 |
| 9 (links, legacy) | T3 |
| 10 (pins, options) | T2 |
| 11 (accessibility, limits) | T6, with R58 moved to T1 |
| 12 (release, help) | T7, with R56 and R57 moved to T1 |
| 13 (upgrade) | T8 |

The user's decisions review set the T1 order.

**One acceptance changes.** R58's 5b-1 acceptance "a 10,000-deep array gives a failed check, not a
rejection" does not hold as written: the measurements show that such a feed is valid by the schema,
`feedFormat` returns `v2`, and storage accepts it. So:
- `test_a_deeply_nested_unknown_value_is_stored_safely` pins the measured outcome: an ok check, the
  right digest, a working popup;
- `test_an_unexpected_error_fails_the_check` pins "a failed check, not a rejection" for every
  exception.

The completion review accepted this narrowing.

| ID | Requirement (exact text) | Owner task | Acceptance test | Disposition | Depends on |
|---|---|---|---|---|---|
| R47 | v2 cards open no link in 5b-1 (P135). 5b-2 Task 7 adds the source entries, and Task 9 opens them only through the §12.6 allowlist | T4 (source entries), T3 (`links.js`) | `test_source_entries_open_only_safe_links`; `test_v2_cards_show_labels_and_badges` (the body opens nothing) | ships | T3 |
| R48 | `count.view`'s pin filter compares v1's `pinned_countries` with the card's `country` (P135). 5b-2 Task 10 switches it to `pinned_places_v2` and a parent pin that includes its subdivisions | T2 | `test_a_parent_pin_includes_its_places`, `test_pins_survive_and_filter_the_popup` (S5-T15), `test_every_v1_pin_string_migrates` (S3-T17) | ships | — |
| R49 | `chrome.runtime.reload()` loses the extension under `--load-extension` (P136). S5-T16 and RT-06 replace the folder's contents, then relaunch the browser on the same profile. That relaunch fires `onInstalled` with reason `install`, not `update` (probe5), so the test checks the kept storage and pins, never the reason. The `update` path is tested through `lib/worker.js`. Chrome's Reload button itself is not driven; the release notes' evidence says so | T8 (T2 for the `update` path) | `test_real_zip_same_folder_upgrade`; `test_the_worker_migrates_pins_on_install_update_and_startup` | test | T2, T7 |
| R50 | The attention section's own count sits beside `#recordCount`, and the records counter never includes attention items | T5 | `test_attention_section_is_always_reachable` (the counter rows) | ships | T4 |
| R51 | R26's popup measurement times the v2 path from storage read to first render, including `feedFormat` on the full feed | T6 | `test_popup_renders_the_fixture_feed_within_the_budget` | ships (marks) + test | — |
| R52 | `lib/legacy.js` still builds cards with `innerHTML` and `escHtml`, and opens feed links as they are. 5b-2 Task 9 removes both | T3 | `test_legacy_opens_only_safe_links`, `test_legacy_text_is_inserted_as_text` | ships | — |
| R54 | `help.html` explains the nine banner conditions (P133), the label texts (P134), the tabs (P135), the month rule (P138) and the Past tab's rename | T7 | `test_help_explains_v2` | ships | T1–T6 (the texts) |
| R55 | `options.js` (v1.0.2) still sends `FETCH_DATA`, which the v2 worker ignores. On a fresh install the options page lists no countries; after an upgrade it lists v1.0.2's last `elections_cache`, frozen for good, so a new country can never be pinned. The options page reads `elections_cache_v2` (or asks the worker with `CHECK`) and never relies on `FETCH_DATA` (Plan 5b-1 Task 4 ruling; final review I2). **Decisions review (2026-10-27):** test populated, absent and invalid caches, a place present only in an undated listing, and that saved pins are kept. **Red-team review (rev 2):** edits from two pages are serialised; a rejected save is reported; pins stay editable without a feed. **Red-team review (rev 3):** a late or lost reply never repaints an older state or reports a saved edit as unsaved | T2 | `test_options_lists_feed_places_and_pins`, `test_pin_edits_are_applied_in_order`, `test_two_options_pages_edit_pins`, `test_a_rejected_pin_save_is_reported`, `test_a_late_pin_reply_never_repaints_an_older_state`, `test_a_lost_pin_reply_is_reconciled` | ships | — |
| R56 | An acknowledgement whose `until` has passed still counts (grey, "(acknowledged until <past date>)"); `health.issues` never compares `until` with `now`. P133 and the spec are silent, so 5b-2 rules on it in a new P-row before changing what readers see (final review m3). **Decisions review:** define the boundary; test just before, at and after it with cached data; the banner and the panel agree; an ended acknowledgement is told apart from one in effect | T1 (P139) | `test_ended_acknowledgements_count_again`, `test_ended_acknowledgements_in_the_popup` (including the open-popup row, rev 2) | ships | — |
| R57 | With warnings the banner reads "7 warnings 7 warnings": P133 row 7's text equals its counts. Hide `#bannerCounts` when it equals the text (final review m4) | T1 | `test_banner_counts_are_not_repeated` | ships | — |
| R58 | `feedFormat` runs the legacy checks before the schema walk (decide on a single walk with R51's numbers). The 30 s deadline does not abort the fetch, and the size limit applies after buffering (an `AbortController` and a streamed cap). `fetchFeed` runs `feedFormat` outside a `try`, so a pathological (deeply nested) feed could still reject `check` (Plan 5b-1 O5, M6; fix-wave re-review). **Completion and decisions reviews:** the deep-nesting route through `feedFormat` is ruled out (probe); the real gap is a missing final boundary; owner fixed; three separate claims (boundary, worker cleanup and recovery, real storage) | T1 (P147) | `test_an_unexpected_error_fails_the_check`, `test_a_failure_that_cannot_be_saved_still_settles`, `test_the_alarm_is_kept_when_a_check_rejects`, `test_a_hung_request_is_aborted`, `test_a_body_is_read_up_to_its_limit`, `test_an_oversized_feed_fails_the_check_in_the_worker`, `test_a_deeply_nested_unknown_value_is_stored_safely`, **(rev 2)** `test_the_real_fetch_reads_a_bounded_body`, `test_the_worker_recovers_after_an_unexpected_failure`; the single walk decided by the errata's numbers | ships | — |
| R59 | The two-line footer at narrow width and 200 % zoom (§12.7): the list's 96 px bottom padding assumes one line (Plan 5b-1 P5) | T6 (P146) | `test_layout_in_a_narrow_or_short_popup` | ships | T4, T5 |
| R60 | When R52 removes `innerHTML`, `test_no_feed_text_through_inner_html_in_v2_code` covers `legacy.js` too and also rejects `DOMParser` and `createContextualFragment` (Plan 5b-1 P6) | T3 | that test, widened to every `extension/**/*.js` | test | T2 (options.js rewritten first) |
| R61 | The renderer × feed matrix includes legacy → v2 and v2 → legacy → v2 inside one open popup, and a format change through a successful check (a real rollback), not only the failed-check path (Plan 5b-1 Q2, Q5) | T3 (extended in T4, T5) | `test_renderer_switches_inside_one_popup`, `test_renderer_matrix` (S5-T17) | test | — |
| R53 | The gates job's measured time (R41) includes `playwright install --with-deps chromium` and the extension suite | 5c | the branch run's step times | process (5c) | — |
| R22 (Plan 3; possible matches, umbrellas and pins parts) | The extension shows possible matches, umbrella sources, a stale fetch date (§12.3) and the S3-T17 v1.0.2 pins | T4, T2 | `test_possible_matches_and_umbrellas_are_labelled`; `test_every_v1_pin_string_migrates` | ships | T3 |
| R25 (Plan 3; umbrella and chip parts) | The extension shows an umbrella only on the children it covers, a "Rescheduled from <date>" chip … | T4 | `test_umbrella_shown_per_child`, `test_rescheduled_chip` | ships | — |
| R26 (Plan 3; the popup part) | Plan 5 measures the popup's parse and first render on that feed | T6 | `test_popup_renders_the_fixture_feed_within_the_budget` (D6: 1000 ms ceiling, the number in the report) | test | — |
| Ruling 8 (Plan 5b-1 note 4; completion and decisions reviews) | Only held claims from non-selected undated fallback sources get no note; reuse the existing string, no new copy | T4 (P143) | `test_an_undated_fallback_confirmation_is_flagged` | ships | — |
| Q1 (Plan 5b-1 Task 6; decisions review) | An accepted path exists; a deterministic fallback | T4 (P145) | `test_a_month_outside_the_window_falls_back` | ships | — |
| B2 row (decisions review) | F0 cached at t0 with its status; F2 (t2) first with a mismatching status; F1 (t1) on the retry with a status linking only F1: F2 stays selected and stored, and F1's status is not health evidence for F2 | T1 | `test_a_retry_keeps_the_best_feed` (new row) | test | — |
| Tooling preservation (decisions review) | Keep the mutation runner, its tables and the reproduction instructions beyond their only scratch copy; do not commit the whole directory or delete it | Step 0 (controller) | the copied runner kills one Plan 5b-1 table's rows from its new place | process | — |

## Review record

**Status:** "planned" becomes "verified" only when the SDD ledger records the task's commit, with
the named test passing and its mutation killed.

| ID | Kind | Ruling | Task · test | Status |
|---|---|---|---|---|
| P139, R56 | Decision, requirement | As in Spec corrections | T1 `test_ended_acknowledgements_count_again`, `test_ended_acknowledgements_in_the_popup` | planned |
| R57 | Requirement | Counts hidden when equal to the text | T1 `test_banner_counts_are_not_repeated` | planned |
| P147, R58 | Interfaces, requirement | As in Spec corrections | T1 the nine R58 tests (rev 2: + `test_the_real_fetch_reads_a_bounded_body`, `test_the_worker_recovers_after_an_unexpected_failure`) | planned |
| B2 row | Review correction | F2 kept over a later F1, unlinked | T1 `test_a_retry_keeps_the_best_feed` | planned |
| P140, R48, S5-T15, S1-T8, S3-T17 | Decision, requirement, spec acceptance | As in Spec corrections | T2 `test_places_table_matches_the_registry`, `test_every_v1_pin_string_migrates`, `test_pin_migration`, `test_a_parent_pin_includes_its_places`, `test_pins_survive_and_filter_the_popup`, `test_the_worker_migrates_pins_on_install_update_and_startup`, **(rev 2)** `test_pin_edits_are_applied_in_order`, `test_only_the_worker_writes_pins` | planned |
| P141, R55, D4 | Decision, requirement | As in Spec corrections | T2 `test_options_lists_feed_places_and_pins`, `test_options_pins_and_unpins`, `test_options_text_is_inserted_as_text`, **(rev 2)** `test_two_options_pages_edit_pins`, `test_a_rejected_pin_save_is_reported`, **(rev 3)** `test_a_late_pin_reply_never_repaints_an_older_state`, `test_a_lost_pin_reply_is_reconciled` | planned |
| P142, R52, R60, S5-T18 | Decision, requirements, spec acceptance | As in Spec corrections | T3 `test_safe_links`, `test_links_match_the_producers_sources`, `test_legacy_opens_only_safe_links`, `test_legacy_text_is_inserted_as_text`, `test_no_feed_text_through_inner_html_in_v2_code` | planned |
| S5-T17, R61 | Spec acceptance, requirement | The matrix and the switches | T3 `test_renderer_matrix`, `test_renderer_switches_inside_one_popup` | planned |
| P143, R25, R22, R47, ruling 8 | Decision, requirements | As in Spec corrections | T4 `test_rescheduled_chip`, `test_an_undated_fallback_confirmation_is_flagged`, `test_umbrella_shown_per_child`, `test_possible_matches_and_umbrellas_are_labelled`, `test_per_source_dates_for_date_conflicts`, `test_cards_expand_on_demand`, `test_source_entries_open_only_safe_links`, `test_card_details_text_is_inserted_as_text`, **(rev 2)** `test_source_lines_say_who_claims_what`, `test_expanded_labels_match_the_card_face` | planned |
| P145, Q1 | Decision | As in Spec corrections | T4 `test_a_month_outside_the_window_falls_back` | planned |
| P144, S5-T10, S5-T11, R50 | Decision, spec acceptance, requirement | As in Spec corrections | T5 `test_attention_items_are_listed`, `test_attention_section_is_always_reachable`, `test_attention_rendering_is_bounded`, `test_attention_links_are_safe`, `test_attention_text_is_inserted_as_text`, **(rev 2)** `test_a_search_over_cut_items_says_what_it_searched` | planned |
| P146, S5-T19, S5-T21 (large collections), R59, R51, R26 | Decision, spec acceptance, requirements | As in Spec corrections | T6 `test_keyboard_and_aria_semantics`, **(rev 2)** `test_focus_survives_a_redraw`, `test_layout_in_a_narrow_or_short_popup`, `test_large_collections_render_bounded`, `test_popup_renders_the_fixture_feed_within_the_budget` | planned |
| P148, S5-T20, R54 | Decision, spec acceptance, requirement | As in Spec corrections | T7 `test_the_zip_is_built_from_the_explicit_list`, `test_the_zip_is_reproducible`, `test_zip_checks_refuse`, `test_every_extension_file_is_listed`, `test_help_explains_v2`, `test_release_notes_cover_the_update`, `test_the_manifest_is_2_0_0` | planned |
| S5-T16, RT-06, R49 | Spec acceptance, requirement | Relaunch on the same profile | T8 `test_real_zip_same_folder_upgrade` | planned |
| Tooling preservation | Review correction | Out-of-repo copy, confirmed 2026-10-28, refreshed after every task that adds or changes a table | Step 0, then every task | planned |
| I2 (Plan 3 final review) | A ruling for the user's veto | Unchanged; no 5b-2 dependency | — | open (the user's) |
| R37 | Parked by the user | Unchanged | — | open (parked) |

## Plan 5b-1 rulings this plan relies on or changes

Numbers are those of the 37-item list in the Plan 5b-1 completion report (errata). The other
rulings stay as recorded in the ledger; none of them binds a 5b-2 task. This plan does not approve
them: they remain the user's to veto, as I2 does.

| Plan 5b-1 ruling | Here |
|---|---|
| Ruling 8 (note 4 needs a dated held source) | **Changed** by P143 for the undated case (the user's narrowing, 2026-10-26/27) |
| Ruling 17 (the options page left on `FETCH_DATA`) | **Replaced** by P141 (R55) |
| Ruling 22 (no banner without data) | **Kept and extended:** the attention section follows it (P144) |
| Rulings 27, 28, 29 (one active renderer, bento labels per renderer, shared states and the pin bar copy) | **Kept.** Every new listener (card toggles, attention, Open buttons, tab keys) checks `body[data-renderer]`; the pin bar now counts places (P140) |
| Ruling 30 (R47 tested: a card body opens nothing) | **Kept** for the body. Open buttons now open safe links (P143) |
| Ruling 31 (Q1–Q5 parked) | **Q1 closed** by P145 (Task 4) |
| Ruling 35 (m3 and m4 left for 5b-2) | **Closed** by Task 1: m3 is R56/P139, m4 is R57 |
| Ruling 37 (the deep-nesting gap parked into R58) | **Closed** by Task 1 (P147) |

## Rulings on the open choices (2026-10-28)

The user confirmed all ten open choices and the help sentence, following
`Downloads/plan-5b2-open-decisions-2026-10-28.md`, and chose subagent-driven execution. Each
condition below was checked against this plan's text, the code and the workflow. Where a
condition was not yet pinned by a test or a step, the row names the addition, marked
**(2026-10-28)** in its task. These are recorded decisions: they are not reopened.

| Choice | Ruling | Conditions kept, and where they are pinned |
|---|---|---|
| P147: a 25 s deadline | Confirmed | Per request, and it covers the body: the deadline races the whole `fetchBytes` call, which is `fetchLimited` reading the body through `readLimited`, and it aborts that request's `AbortController` (Task 1 Step 5). The cache is kept, the checking state clears and the next check runs (`test_a_hung_request_is_aborted`, `test_the_worker_recovers_after_an_unexpected_failure`). Not a guarantee that Chrome cannot end the worker first ("Known limits") |
| P140/P141: only the worker writes pins | Confirmed | The migration's coordination, fresh reads, idempotent ops and read-back verification (P140). N01 and N02 stay: a late reply never repaints an older state, and a rejected or lost reply releases the button and reconciles, also after a save that succeeded (`test_a_late_pin_reply_never_repaints_an_older_state`, `test_a_lost_pin_reply_is_reconciled`) |
| P144: the attention wording departs from §12.4 | Confirmed as a spec correction | Total, included, matched and shown counts stay distinct. **(2026-10-28)** Spec §12.4's last bullet now points to P144, so the old wording is no longer a competing requirement |
| P148: ZIP reproducibility for one Python and zlib | Confirmed | Fixed entry order, times, `create_system` and `external_attr`; identical bytes across trees with different mtimes (`test_the_zip_is_reproducible`); the printed row names `platform.python_version()` and `zlib.ZLIB_RUNTIME_VERSION`. **(2026-10-28)** Task 7's ledger entry records them with the ZIP's SHA-256. Another toolchain carries no identical-byte promise |
| R48: a parent pin includes its subdivisions | Confirmed, through the registry's `parent` only | "Also shows" and each place's own name (P141). No relationship is inferred from names. **(2026-10-28)** `test_a_parent_pin_includes_its_places` also checks that a subdivision pin matches neither its parent nor a sibling |
| P142: an unknown source opens nothing | Confirmed | Its source text and evidence stay, with no Open control. A known source with an unacceptable URL opens its home page (`test_safe_links`, `test_source_entries_open_only_safe_links`, `test_attention_links_are_safe`) |
| R62: the `RELEASES.md` row moves to Plan 5c | Confirmed | **(2026-10-28)** Task 7 records the build's code SHA, ZIP SHA-256, file count, Python and zlib versions and the four checks' results in the 5b-2 ledger. 5c writes the row against the final release build; R62 stays open until then |
| The attention section is collapsed by default | Confirmed | The toggle, its count and `#attentionNote` stay visible while collapsed, also when no card matches. **(2026-10-28)** `test_a_search_over_cut_items_says_what_it_searched` checks that case. Keyboard access (Task 6), the open state kept within the popup, and the health banners under their own rules |
| R58: the narrowed acceptance | Confirmed | `test_a_deeply_nested_unknown_value_is_stored_safely` compares `months` only, and never claims that unknown values round-trip. Every boundary, abort, cache, cleanup and recovery test stays (Task 1) |
| The tooling in `handovers/elections-v2-tooling/` | Confirmed | Step 0 copies it and proves the copied runner. **(2026-10-28)** After every task that adds or changes a mutation table (and `supp5b2.py`), the controller refreshes the copy and records that in the ledger. `.scratch/` is kept |
| The help sentence | Added **(2026-10-28)** | Task 7's `help.html` states it, and `test_help_explains_v2` pins it. Checked against `update-elections.yml`: the `generation` artifact uploads `out/` with `retention-days: 14`, and `pipeline.py` writes `out/attention_full.json`. The limit is the artifact's; items already in the extension do not expire |

## How to execute this plan

- **Where:** the worktree `C:/Users/senescalk/Desktop/elections-calendar/.claude/worktrees/never-miss-v2`,
  branch `feat/never-miss-v2`.
  - Do not create worktrees, do not switch branches, do not commit to `main`.
  - Keep the shell in the worktree; use `( cd … && … )` subshells for anything elsewhere.
- **Style:** as Plan 5b-1.
  - This plan pins names, signatures, rules, copy and test values; you write the bodies.
  - If a rule is ambiguous, stop and ask the controller. Never change an expected value to match
    the output.
  - JS is plain ES2022 modules with `export function` and `const`; classes only where a step names
    one (`OverLimit`). Files use LF.
- **Step 0 (the controller, before Task 1, no commit): preserve the mutation tooling.**
  - Copy these to `C:/Users/senescalk/Desktop/handovers/elections-v2-tooling/`, outside the repo:
    - `.scratch/mutate.py` (4,999 B);
    - `.scratch/mutations/*.json` (the 96 tables);
    - `.scratch/supp5b1.py`;
    - `.scratch/plan5a/mut_unique.py`;
    - `.scratch/plan5b1/{review_record.py, rulings.py}`;
    - `.scratch/plan5b2/*.py` and `*.txt`.

    That is about 2 MB of the 167 MB.
  - Add a `README.md` there:
    - what each file is;
    - the invocation (`PYTHONDONTWRITEBYTECODE=1 GIT_ALLOW_PROTOCOL=file .venv/Scripts/python.exe
      <copy>/mutate.py <table>`, run from the worktree, with the task's files staged first);
    - Python 3.14.1;
    - the restore rule (`git checkout -- <file>` + `git diff --exit-code -- <file>`);
    - that the main checkout's `.scratch/planbuild/mutate.py` is the older Plan 1 version.
  - **Check:** run the copied `mutate.py` on `plan5b1-final.json` from the worktree. All 16 rows
    must be KILLED, and the tree must be clean afterwards.
  - Link the folder from the ledger and the RESUME doc. `.scratch/` stays as it is: nothing is
    deleted.
  - Committing `mutate.py` instead would reverse Plan 1's user-approved pushback, so it is the
    user's call.
- **Per task:** the Implement-Review loop in the user's CLAUDE.md, at most 3 rounds:
  1. pre-flight against the current source;
  2. write the failing test;
  3. implement;
  4. run the gates, each in its own shell call:
     - `GIT_ALLOW_PROTOCOL=file .venv/Scripts/python.exe -m pytest -q`
     - `.venv/Scripts/mypy.exe`
     - `.venv/Scripts/mypy.exe --platform linux`
     - `.venv/Scripts/ruff.exe check`
     - `.venv/Scripts/lint-imports.exe --config importlinter.ini`
  5. run the mutation table;
  6. commit.
- **The extension suite on its own:**
  `GIT_ALLOW_PROTOCOL=file .venv/Scripts/python.exe -m pytest tests/extension -q`. It takes about 3 min
  today; expect about 6 min after this plan.
- **Mutations:** one per new test, in `.scratch/mutations/plan5b2-task-<N>.json`, in
  `.scratch/mutate.py`'s format (`{test, file, old, new}`, `old` unique in the file).
  - Stage the task's files first, and run with `PYTHONDONTWRITEBYTECODE=1` and
    `GIT_ALLOW_PROTOCOL=file`.
  - Each task names a mutation for each test; pick the `old` text yourself.
  - After every task, run `.scratch/plan5a/mut_unique.py` over `plan5b2-*.json`, and re-run every
    earlier `plan5b1-*` and `plan5b2-*` table whose file the task touched.
  - **(2026-10-28)** Then the controller copies every new or changed table (and `supp5b2.py`
    when it changed) to `handovers/elections-v2-tooling/`, and records the refresh in the
    ledger.
- **Supplements:** `.scratch/supp5b2.py` (a copy of `supp5b1.py` pointed at this plan) gives each
  brief the Global Constraints, the errata and the cited P-rows verbatim.
- **Runtime:**
  - **A browser launch** costs about 2 s. Tests that install, relaunch, time the popup or change
    the viewport's clock state launch their own (`fresh_ext`, or `launch` in the test).
  - **The fixture artifact** costs 3.4 s, once per session.
- **Cost (an estimate by analogy with Plan 5b-1's, not a measurement):**
  - eight tasks, at one implementer and one reviewer each;
  - about one fix round per task with its scoped re-review. Tasks 1, 2, 3 and 6 are the
    largest;
  - then a whole-branch review with one fix wave and its re-review.

  **(rev 2)** The revision adds about ten tests, mostly in Tasks 1, 2 and 6. That is about 29–38
  agent runs, roughly **USD 260–420**, about two to three days of the USD 150 daily budget. Every task ends at a green commit, so work can be parked between tasks.
- **Bounds:**
  - One task at a time.
  - One reviewer per round, fresh each round; at most 3 fix rounds per task.
  - If round 3 ends with a gate red, a Critical or Important finding open, or a mutation alive,
    stop: commit nothing that is not green, and report what is open.
  - An AWS, Bedrock or budget error stops all work at the last green commit, with uncommitted work
    in a named stash.
  - No merge and no push.
- **Handover:** after every task, record the commit, the Review record rows it verified and the
  next task in two files:
  - `C:/Users/senescalk/Desktop/handovers/elections-v2-plan5b2-sdd-ledger.md` (new);
  - `C:/Users/senescalk/Desktop/handovers/elections-v2-RESUME.md`.
- **Hook:** the Desktop PostToolUse hook runs `ruff check --fix` on each edited `.py`; check
  `git diff --stat` for unrelated rewrites. Never write source files through shell heredocs.
- **Reviewers check, besides CLAUDE.md's list:**
  - a feed link opened without `safeLink`;
  - **(rev 2)** a pin key written outside the worker (its migration and its `PIN_EDIT` queue),
    or a pin edit that skips the queue;
  - markup built from a string;
  - a listener that does not check `body[data-renderer]`;
  - a details or attention list rendered before it is opened;
  - copy that differs from this plan;
  - a test that passes against v1.0.2's files too.

## File structure

| Path | Responsibility | Task |
|---|---|---|
| `extension/lib/health.js`, `extension/popup.js`; `tests/extension/test_banner.py` | ended acknowledgements (P139); counts not repeated (R57) | 1 |
| `extension/lib/load.js`, `extension/background.js`, `extension/lib/worker.js`; `tests/extension/test_loading.py`; `tests/support/extension.py`, `tests/support/extension_page/fakes.js` | the final boundary, aborts, the streamed cap, the alarm `finally` (P147); the B2 row | 1 |
| `scripts/build_extension_places.py`, `extension/places.json`; `tests/scripts/test_build_extension_places.py` | the place table (D3) | 2 |
| `extension/lib/pins.js`, `extension/lib/worker.js`, `extension/background.js`, `extension/lib/load.js` (`loadPlaces`), `extension/popup.js`, `extension/lib/count.js`, `extension/lib/render.js`, `extension/lib/legacy.js`; `tests/extension/test_pins.py`, `tests/extension/test_counting.py` | migration, the parent rule, the pin filter (P140) | 2 |
| `extension/options.html`, `extension/options.js`, `extension/options.css`; `tests/extension/test_options.py` | the options page (P141) | 2 |
| `extension/lib/links.js`, `extension/lib/legacy.js`, `extension/lib/schema.js`; `tests/extension/test_links.py`, `tests/extension/test_renderers.py`, `tests/extension/test_extension_files.py` | the allowlist; the legacy rebuild; the matrix and the switches (P142) | 3 |
| `extension/lib/labels.js`, `extension/lib/details.js`, `extension/lib/count.js`, `extension/lib/render.js`, `extension/styles.css`; `tests/extension/test_cards.py`, `tests/extension/test_labels.py`, `tests/extension/test_counting.py` | expandable cards, chips, source links, the start month (P143, P145) | 4 |
| `extension/lib/attention.js`, `extension/lib/render.js`, `extension/popup.html`, `extension/popup.js`, `extension/styles.css`; `tests/extension/test_attention.py` | the attention section (P144) | 5 |
| `extension/popup.html`, `extension/styles.css`, `extension/lib/render.js`, `extension/lib/legacy.js`, `extension/popup.js`, `extension/options.css`; `tests/extension/test_accessibility.py`, `tests/extension/test_limits.py` | tabs, disclosures, focus, the dock, timing marks (P146, R51) | 6 |
| `extension/manifest.json`, `extension/help.html`, `scripts/build_extension_zip.py`, `docs/extension/v2.0.0-release-notes.md`, `README.md`; `tests/scripts/test_build_extension_zip.py`, `tests/extension/test_release_files.py` | version, help, release notes, the ZIP (P148) | 7 |
| `tests/extension/test_upgrade.py` | the real-ZIP same-folder upgrade | 8 |

## Tasks

### Task 1: Expired acknowledgements, banner counts, and the check's error boundary (R56, R57, R58; P139, P147; the B2 row)

**Files:**
- Modify: `extension/lib/health.js`, `extension/popup.js`, `extension/lib/load.js`,
  `extension/background.js`, `extension/lib/worker.js`
- Modify: `tests/support/extension_page/fakes.js`, `tests/support/extension.py`
- Test: `tests/extension/test_banner.py`, `tests/extension/test_loading.py`,
  `tests/extension/test_extension_files.py`

**Interfaces:**
- Consumes: `dates.parseTimestamp`, `stampDate`; `order.isLinked`; the harness's `run_check` and
  `runHandlers`.
- Produces:
  - `health.issues(doc, now)`;
  - `health.panelRows({format, doc, status, linked, now})`;
  - `health.bannerState({format, doc, status, linked, now})` (signature unchanged).
  - `load.UNEXPECTED = "the check failed unexpectedly"`;
  - `export class OverLimit extends Error` with `.limit`;
  - `load.readLimited(response, limit) -> Promise<Uint8Array>`;
  - **(rev 2)** `load.fetchLimited(fetchImpl, url, {signal, limit}) -> Promise<Uint8Array>`, and
    `REQUEST_TIMEOUT_MS = 25_000`;
  - `deps.fetchBytes(url, {signal, limit})` and an optional `deps.report(err)`.
  - `run_check(...)` gains:
    - `set_fails_all: bool = False`;
    - `throw: str | None = None`: the fake feed schema becomes a `Proxy` whose every property read
      throws `new Error(throw)`;
    - **(rev 2)** `report_throws: bool = False`: `deps.report` throws;
    - **(rev 2)** `stored_throws: bool = False`: the first `get` resolves to an object whose every
      property read throws `new Error("boom")`, and later `get`s are normal.
  - `runHandlers` specs gain `runCheckRejects: bool`.

- [ ] **Step 1: Write the failing tests**
  - **`test_ended_acknowledgements_count_again`** (`lab`, UTC; pure). Take the fixture feed
    (7 warnings: Wikipedia 2, NDI 1, A-WEB 2, EISA 1, IPU 1; no errors).
    - Acknowledge Wikipedia's first warning (`unparsed_relevant`, stage `parse`, year and page
      null) until U = "2026-10-20T00:00:00Z".
    - Give Carter Center one schema-valid error reason (severity "error"), acknowledged until U.
    - **At `now` = U − 1 ms:**
      - `issues(doc, now)` has errors 0, warnings 6 and acknowledged 2;
      - `bannerState` (linked) gives level `amber`, text "6 warnings" and counts "6 warnings · 2
        acknowledged";
      - the two lines read "<text> (acknowledged until 20 Oct 2026)".
    - **At `now` = U and U + 1 ms:**
      - errors 1, warnings 7, acknowledged 0;
      - level `red`, text "1 source error", counts "1 error · 7 warnings";
      - the two lines read "<text> (acknowledgement ended 20 Oct 2026)".
    - **One-to-one matching:** with two acknowledgements of the same key (one ended, one in
      effect), the reason is acknowledged at U + 1 ms.
  - **`test_ended_acknowledgements_in_the_popup`** (its own `launch` with
    `timezone_id="America/Los_Angeles"`). The same feed bytes, cached with a status linking them.
    The popup is opened at page clocks U − 1 s and U + 1 s.
    - `#bannerText`, `#bannerCounts` and the panel lines (after one click on the banner) equal the
      pure rows at those instants.
    - The exception is the date: "19 Oct 2026", because U is 17:00 on 19 October in Los Angeles.
      So the boundary follows the instant, and the shown date follows the reader's zone.
    - **(rev 2) An open popup across `until`:**
      1. Open at U − 1 s.
      2. Set the page clock to U + 1 s: the banner is still amber, because there is no timer
         (P139).
      3. Click Refresh, with the same pair routed, so the check comes back unchanged.
      4. The banner is red, and the line reads "acknowledgement ended".
  - **`test_banner_counts_are_not_repeated`** (`ext`, R57):
    - the artifact pair cached: `#bannerText` "7 warnings", and `#bannerCounts` hidden;
    - the U − 1 s case above: `#bannerCounts` visible with "6 warnings · 2 acknowledged".
  - **`test_an_unexpected_error_fails_the_check`** (`lab`; `run_check(..., throw="boom")`). Rows:
    - **no cache:** result `{"ok": False, "error": "the check failed unexpectedly: boom"}`;
      stored check `{ok_at: None, failed_at: now, error: <same>}`;
    - **a cached pair:** the same result; the feed and status records equal the seeded ones; the
      check record keeps `ok_at`;
    - **`throw` = "x" × 1000:** error = `"the check failed unexpectedly: " + "x" * 200 + "…"`;
    - **recovery:** a check with real schemas on the second row's resulting storage, with the
      pair served, gives `ok` True and stores the served feed.
    - **(rev 2) `report_throws`:** the same result as the cached-pair row.
    - **(rev 2) `stored_throws`,** with a cached pair and `ok_at` T0: the same result. The check
      record is `{ok_at: T0, failed_at: now, error: <same>}`, taken from the boundary's own re-read,
      and the feed and status records are unchanged.
  - **`test_a_failure_that_cannot_be_saved_still_settles`** (`lab`; `set_fails_all=True`). Rows:
    - feed HTTP 503 → `{"ok": False, "error": "elections.json: HTTP 503"}`;
    - `throw="boom"` → `{"ok": False, "error": "the check failed unexpectedly: boom"}`.

    In both, the stored values equal the seeded ones, and the fake saw the failed `set`s.
  - **`test_the_alarm_is_kept_when_a_check_rejects`** (`lab`; `runHandlers({call: "alarm", arg:
    {name: "elections-refresh"}, runCheckRejects: true})`):
    - the log is `["runCheck:start", "runCheck:end", "ensureAlarm:start", "ensureAlarm:end"]`;
    - the handler rejects with "runCheck failed".
  - **`test_a_hung_request_is_aborted`** (`lab`). The fake `fetchBytes` records `"<name>:aborted"`
    when its signal aborts, then rejects with an `AbortError`. Rows:
    - a hung feed → "elections.json: no response in time", and the log holds
      "elections.json:aborted";
    - a hung status → the check succeeds unlinked, and the log holds "status.json:aborted".

    In both, `ext.page_errors` is empty (no unhandled rejection).
  - **`test_a_body_is_read_up_to_its_limit`** (`lab`; `readLimited`):
    - `new Response(new Uint8Array(10))` with limit 10 → 10 bytes;
    - with limit 9 → `OverLimit`, message "over the limit of 9 bytes";
    - an endless `ReadableStream` (64 KiB chunks) with limit 1,000,000 → `OverLimit` within 2 s,
      and the stream's `cancel` ran.
  - **(rev 2) `test_the_real_fetch_reads_a_bounded_body`** (`lab`; `fetchLimited` with a fake
    `fetchImpl`):
    - an endless `ReadableStream` body (64 KiB chunks), limit 1,000,000 → `OverLimit` within 2 s,
      and the stream's `cancel` ran;
    - the fake received `(url, {cache: "no-store", signal})`, with the very signal passed in;
    - a 503 response → an error "HTTP 503";
    - a 10-byte body with limit 10 → those 10 bytes.

    This is the test that tells streaming from buffering. The worker test below cannot, because
    the post-buffer backstop gives the same message (P147).
  - **`test_an_oversized_feed_fails_the_check_in_the_worker`** (`ext`):
    - `elections.json` served as 4,000,001 bytes;
    - a forced check replies `{ok: false, error: "elections.json: over the limit of 4000000 bytes"}`.
  - **(rev 2) `test_the_worker_recovers_after_an_unexpected_failure`** (`ext`; the real worker):
    - **Set up:** the pair cached, with `check_state_v2.ok_at` T0. Open the popup; no check is
      due.
    - **Inject** through `Ext.worker().evaluate`: for one call, `chrome.storage.local.get` resolves
      to an object whose every property read throws `new Error("boom")`.
    - **Click Refresh.** Then:
      - `body[data-checking]` returns to "false";
      - the popup still shows its 30 October cards;
      - `check_state_v2` is `{ok_at: T0, failed_at: <now>, error: "the check failed
        unexpectedly: boom"}`;
      - the feed and status records are unchanged;
      - the alarm `elections-refresh` exists.
    - **Click Refresh again:** `check_state_v2.error` is null and `failed_at` is null. A new check
      ran, so the in-flight promise was released.
  - **`test_a_deeply_nested_unknown_value_is_stored_safely`** (`ext`; the real storage, P147):
    - the fixture feed's bytes with `"x_probe_extra": [[…0…]]` (10,000 deep, built as text),
      served with a status linking those bytes;
    - a forced check is `ok`;
    - the stored record's `sha256` is the served bytes' digest, and its `months` equal the
      fixture's (compared with `json.dumps(sort_keys=True)`);
    - the popup shows 30 October cards, with no page errors;
    - a second forced check replies `changed: false`.
  - **`test_check_records_failures_and_keeps_the_cache`'s oversize row** now expects
    "elections.json: over the limit of 4000000 bytes" (P147).
  - **`test_a_retry_keeps_the_best_feed`** gains the B2 row:
    - stored `{FEED: feed_record(f0), STATUS: status_record(s0)}`, where s0 =
      `_links(f0, status, "2026-10-19T05:00:00Z")`;
    - feeds `[f2, f1]`, statuses `[stale, s1]`;
    - want feed f2, want status s1 (P132: none describes f2, so the latest attempt), linked False.
  - **`test_the_worker_wires_its_handlers`** (**rev 2**) gains two checks:
    - `background.js`'s `fetchBytes` calls `fetchLimited(fetch, …)`;
    - `load.js` sets `REQUEST_TIMEOUT_MS = 25_000`.

- [ ] **Step 2: Run them and see them fail.**
  `GIT_ALLOW_PROTOCOL=file .venv/Scripts/python.exe -m pytest tests/extension/test_banner.py tests/extension/test_loading.py tests/extension/test_extension_files.py -q`.
  Expected: the new tests and rows FAIL. The ended-acknowledgement rows show "acknowledged until";
  the unexpected rows reject with "boom".

- [ ] **Step 3: Implement P139 in `health.js`**
  - `classify(reasons, acknowledgements, now)`: in-effect matches first, then ended ones.
  - Each found entry is `{reason, level, until, acknowledged, ended}`.
  - `issues` and `panelRows` take `now`, and `popup.js` passes its `now` to both.
  - Panel copy as P139.

- [ ] **Step 4: Implement R57 in `popup.js`:** `#bannerCounts` is hidden when `counts` is "" or
  equals `text`. **(rev 2)** `render()` reads `Date.now()` once and passes that `now` to
  `renderV2` and `drawHealth` (P139).

- [ ] **Step 5: Implement P147:**
  - **`load.js`:**
    - `check` wraps its body. On an exception it records the failure under P147's recording
      rule, through a guarded `fail` that never throws, and returns the bounded text. It calls
      `deps.report` inside its own `try`.
    - `withDeadline` becomes per request: an `AbortController`, `fetchBytes(url, {signal,
      limit})`, abort on the deadline, and the loser's rejection caught.
    - `readLimited`, `OverLimit` and `fetchLimited`, as above; `fetchDocument` maps `OverLimit`
      to its message; `REQUEST_TIMEOUT_MS = 25_000`.
  - **`background.js`:**
    - `fetchBytes = (url, options) => fetchLimited(fetch, url, options)`;
    - `report: console.error`.
  - **`worker.js`:** `alarm` runs `try { return await runCheck(); } finally { await ensureAlarm(); }`.
  - **`fakes.js`:**
    - `setFailsAll`, `throw`, `reportThrows` and `storedThrows`;
    - the hang response listens to `signal`;
    - `runHandlers`'s `runCheckRejects`.

- [ ] **Step 6: Run the tests until they pass, then the full extension suite three times**
  (flakiness check).

- [ ] **Step 7: Mutations** (`plan5b2-task-1.json`), one per test:

  | Test | Mutation |
  |---|---|
  | `test_ended_acknowledgements_count_again` | `now < until` → `true` |
  | `test_ended_acknowledgements_in_the_popup` | `popup.js` passes no `now` to `panelRows` |
  | its open-popup row (rev 2) | `drawHealth` uses the `now` of the popup's first render |
  | `test_banner_counts_are_not_repeated` | drop the "equals the text" condition |
  | `test_an_unexpected_error_fails_the_check` | the boundary rethrows |
  | its `report_throws` row (rev 2) | `deps.report` called outside its `try` |
  | its `stored_throws` row (rev 2) | the boundary keeps `ok_at` from the first read's object, not its own re-read |
  | `test_a_failure_that_cannot_be_saved_still_settles` | the guarded `fail` lets its `set` error escape |
  | `test_the_alarm_is_kept_when_a_check_rejects` | `finally` → after the `await` |
  | `test_a_hung_request_is_aborted` | no `abort()` on the deadline |
  | `test_a_body_is_read_up_to_its_limit` | `>` limit → `>=` limit |
  | `test_the_real_fetch_reads_a_bounded_body` (rev 2) | `fetchLimited` returns `new Uint8Array(await response.arrayBuffer())` (the endless body never ends, so the test times out) |
  | `test_an_oversized_feed_fails_the_check_in_the_worker` | **(rev 2)** `fetchDocument` maps `OverLimit` to "the request failed" |
  | `test_the_worker_recovers_after_an_unexpected_failure` (rev 2) | `runCheck` releases `running` only when the result is `ok`. The second Refresh then joins the settled failure, and `error` stays set |
  | `test_a_deeply_nested_unknown_value_is_stored_safely` | `feedFormat` reports unknown top-level keys as problems |
  | the B2 row | the retry compared with `cached?.order_key` |
  | the wiring check | **(rev 2)** `REQUEST_TIMEOUT_MS = 30_000` |

  Where a mutation is also killed by another test, record that test's kill as its own evidence,
  not as this row's.

  Re-run `plan5b1-task-4.json`, `plan5b1-task-5.json` and `plan5b1-final.json`.

- [ ] **Step 8: Run the gates, then commit.**
  `git commit -m "fix(extension): ended acknowledgements, banner counts, the check's error boundary and request limits (Plan 5b-2 Task 1)"`.

### Task 2: Pins as places and the options page (D3, D4, R48, R55; P140, P141; S5-T15, S1-T8, S3-T17)

**Files:**
- Create: `scripts/build_extension_places.py`, `extension/places.json`, `extension/lib/pins.js`
- Modify: `extension/lib/load.js` (`loadPlaces`), `extension/lib/worker.js`,
  `extension/background.js`, `extension/popup.js`, `extension/lib/count.js`,
  `extension/lib/render.js`, `extension/lib/legacy.js`
- Rewrite: `extension/options.html`, `extension/options.js` (a module), `extension/options.css`
- Modify: `tests/support/extension_page/fakes.js` (`runPins`), `tests/support/extension.py`
  (`run_pins`; rev 3: `wrap_pin_messages`, `wrap_pin_reads`)
- Test: `tests/scripts/test_build_extension_places.py`, `tests/extension/test_pins.py`,
  `tests/extension/test_options.py`, `tests/extension/test_counting.py`,
  `tests/extension/test_loading.py`, `tests/extension/test_extension_files.py`

**Interfaces:**
- Consumes: `elections_calendar.places.PlaceRegistry` (`load`, `get`, `resolve`); `load.storedFeed`,
  `loadSchemas`; `count.view`.
- Produces:
  - **`scripts/build_extension_places.py`:** `build(places: Path = DEFAULT_PLACES) -> bytes` and
    `OUT = ROOT / "extension" / "places.json"`. `main()` writes `OUT`, run as
    `.venv/Scripts/python.exe -m scripts.build_extension_places`.
  - **`load.loadPlaces(getURL) -> Promise<{names, places}>`.**
  - **`pins.js`:**
    - `PIN_KEYS = {legacy: "pinned_countries", places: "pinned_places_v2", unresolved: "unresolved_pins_v2", migrated: "pins_migrated_v2"}`;
    - `placeOf(name, table) -> string | null`;
    - `migration(stored, table) -> {places: string[], unresolved: string[]} | null` (null when
      migrated);
    - `currentPins(stored, table) -> {places, unresolved}`;
    - `pinMatcher(places, table) -> (placeId: string | null) => boolean`; an empty list matches
      everything;
    - `migratePins({get, set, table}) -> Promise<{ok: true, migrated: boolean} | {ok: false, error: string}>`,
      which never rejects;
    - `optionPlaces(record, table) -> [{id, name}]`;
    - `optionRows(feedPlaces, pins, table) -> {rows: [{id, name, pinned, includes: string[]}], unresolved: string[]}`;
    - **(rev 2)** `applyEdit(pins, {op, value}) -> {places, unresolved} | {error}`, pure (P140's
      ops);
    - **(rev 2)** `editQueue({get, set, table}) -> (edit) => Promise<{ok: true, pins} | {ok: false, error}>`.
      It returns one editor that applies edits strictly one after another, each on freshly read
      storage, and never rejects.
  - **`worker.handlers({runCheck, ensureAlarm, isDue, openHelp, migratePins, editPin})`:**
    - `message({type: "PINS"})` returns `migratePins()`'s reply;
    - **(rev 2)** `message({type: "PIN_EDIT", op, value})` returns `editPin({op, value})`'s reply.
    - `background.js` makes one `editPin = editQueue(...)` per worker life.
  - **The views:**
    - `count.view(doc, {month, tab, level, query, pins, today, now})`, where `pins` is a
      `(placeId) => boolean`;
    - `renderV2(feed, {pinned, table, today, now})` and `renderLegacy(json, {pinned, table})`,
      where `pinned` is the list of place ids.
  - **`run_pins(lab, *, stored, verify_mismatch=False, get_fails=None, set_fails=None) -> {result, stored, sets}`.**
  - **`runHandlers` specs** gain a logged `migratePins` fake (delay 10) and `migrateRejects: bool`.
  - **(rev 2)** `run_pin_edits(lab, *, stored, edits, set_delay_ms=30, set_fails=()) -> {replies, stored, sets}`.
    It sends every edit to one `editQueue` without waiting, over a fake storage whose `set`s take
    `set_delay_ms`. `set_fails` holds the indexes of the `set` calls that reject. It returns the
    replies in edit order.
  - **(rev 3) The options-page wrappers,** installed with `page.evaluate` after load:
    - `wrap_pin_messages(page, mode)` changes the next `PIN_EDIT` only, with `mode` one of:
      - `"hold"`: forward it, then keep the real reply until `release_pin_reply(page)`;
      - `"reject-before"`: reject with "Could not establish connection. Receiving end does
        not exist." without forwarding;
      - `"reject-after"`: forward it, await the real reply, then reject with "The message
        port closed before a response was received.";
      - `"no-reply"`: resolve `undefined` without forwarding.
    - `wrap_pin_reads(page, mode)` changes `chrome.storage.local.get` calls for the pin keys:
      - `"hold-next"`: hold the next one's result until `release_pin_read(page)`. Once the real
        read returns, `window.__pinReadHeld` holds its value;
      - `"fail"`: reject every one with "boom".
    - Each `release_*` resolves after the held value is delivered and one task has passed.

**Copy (verbatim, P141):**

| Where | Text |
|---|---|
| `<title>` | Elections Calendar — Pinned countries |
| heading | Pinned countries |
| subtitle | Pin countries to show only their elections in the popup. A pinned country also shows the places that belong to it. |
| search placeholder | Search for a country... |
| summary, none | No countries pinned — popup shows all results. |
| summary, n | `<n> country/countries pinned — popup shows only these.` ("country" for 1) |
| pin button title | Pin — popup will show only pinned countries / Unpin — removes from popup-only view |
| pin button `aria-label` | `Pin <name>` / `Unpin <name>`, with `aria-pressed` |
| included places | `Also shows: <names>` |
| unresolved heading | Pins from version 1 that match no known country |
| unresolved note | These do not filter the popup. Remove them, then pin the country again from the list. |
| unresolved button | Remove (`aria-label` `Remove <name>`) |
| no data | No election data is available yet. Open the popup to load it, then come back here. |
| pins failed | `Your pins could not be prepared: <error>. Reload this page to try again.` |
| a save failed (rev 2, `#pinStatus`) | `Your change could not be saved: <error>. Try again.` |
| a change not confirmed (rev 3, `#pinStatus`) | `Your change could not be confirmed: <message>. The list shows your saved pins.` |
| the pins not readable (rev 3, `#pinStatus`) | `Your saved pins could not be read: <error>. Reload this page to try again.` |

The pin icon is an inline `<svg>` in a `<template>` in `options.html`, cloned per button (no
markup from strings).

- [ ] **Step 1: Write the failing tests**
  - **`test_places_table_matches_the_registry`:**
    - `build()` equals the committed `extension/places.json` byte for byte;
    - every `names` entry resolves through `PlaceRegistry.load().resolve` to its id;
    - `places` equals the registry's `display` and `parent` for all 264;
    - every string in `feed_country_history.tsv` is a key of `names`.
  - **`test_every_v1_pin_string_migrates`** (S3-T17; `lab`; pure): `migration({pinned_countries:
    <all 90 history strings>}, table)` gives no unresolved pins. Its places equal the registry's
    resolutions of the 90 strings, deduplicated in order: 84 ids, since six places have two
    strings.
  - **`test_pin_migration`** (`run_pins`). Rows:
    - **Not migrated,** with `["Cabo Verde", "Scotland (part of the United Kingdom)", "Atlantis",
      "Cape Verde", 7, "constructor"]`:
      - places `["iso:CV", "iso:GB-SCT"]`;
      - unresolved `["Atlantis", "constructor"]`;
      - flag true;
      - `pinned_countries` deep-equal to the seed;
      - `sets` = `[[places, unresolved], [migrated]]`.
    - **Already migrated:** no `set`.
    - **`verify_mismatch`:** `{ok: false, error: "the migrated pins could not be verified"}`, and no
      flag.
    - **`get_fails` / `set_fails`:** `{ok: false, error: "the pins could not be migrated: <msg>"}`,
      without rejecting.
    - **Deleted stays deleted:** migrate; set `pinned_places_v2` to `["iso:GB-SCT"]`; migrate
      again → still `["iso:GB-SCT"]`.
    - **A rollback edit:** after the flag, add "Brazil" to `pinned_countries` → no change.
    - **A non-list `pinned_countries`** (`"Brazil"`) → places [].
  - **`test_a_parent_pin_includes_its_places`** (`lab`; pure, then `view` on the fixture):
    - `pinMatcher(["iso:GE"], table)` matches `x:south-ossetia` and `x:abkhazia`, but not
      `iso:RU` or `null`;
    - `pinMatcher(["x:south-ossetia"])` does not match `iso:GE`, nor its sibling `x:abkhazia`
      **(2026-10-28)**;
    - an id not in the table matches only itself;
    - on the fixture, `view` with `[iso:GE]` in 2026-09 shows the one South Ossetia card;
    - `[iso:MD]` in 2026-11 shows Moldova's card, and in 2026-12 Transnistria's;
    - `[]` shows everything.
  - **`test_pins_survive_and_filter_the_popup`** (S1-T8; `ext`). Seed `pinned_countries` `["Cabo
    Verde", "Moldova"]` with no flag, plus the cached pair.
    - The popup, on November: only Cape Verde's and Moldova's cards, and the pin bar "Pinned view ·
      2 countries".
    - The popup wrote no pin key.
    - After the options page opens: `pinned_places_v2` `["iso:CV", "iso:MD"]`, the flag true, and
      `pinned_countries` unchanged.
    - The legacy renderer with the v1 feed and the same pins: only Cape Verde's and Moldova's v1
      cards.
  - **`test_the_worker_migrates_pins_on_install_update_and_startup`** (`lab`; `runHandlers`):
    - the order is:
      - `installed` with `install`: `openHelp`, `migratePins`, `ensureAlarm`, `runCheck`;
      - `installed` with `update`, and `startup`: `migratePins`, `ensureAlarm`, `runCheck`;

      Each runs after the previous one's `:end`. The existing `test_worker_handlers` rows change
      to match;
    - `migrateRejects: true` still runs `ensureAlarm` and `runCheck`;
    - `message({type: "PINS"})` waits for and returns the fake's value (the listener returns true).
  - **`test_options_lists_feed_places_and_pins`** (R55; `ext`). Rows:
    - **(a) Fresh** (no cache, the pair routed): 73 rows. "Lesotho" is present (listing-only);
      there is no unresolved list.
    - **(b) After an upgrade** (`elections_cache` = the v1 feed, `elections_cache_v2` = the
      artifact): 73 rows, including Lesotho. A country that only the v1 feed has (the test computes
      it) is absent.
    - **(c) An invalid v2 cache** (a string), with no route: the no-data text.
    - **(c2, rev 2) The same, with saved pins:** `pinned_places_v2` `["iso:CV"]` and
      `unresolved_pins_v2` `["Atlantis"]`, with no route.
      - The no-data text shows above the list.
      - Cape Verde is listed as pinned, and can be unpinned.
      - "Atlantis" is under the unresolved heading.
    - **(d) Pins kept:** `pinned_places_v2` `["iso:CV", "iso:IS"]` and `unresolved_pins_v2`
      `["Atlantis"]`. Cape Verde and Iceland are listed first (Iceland from the table's display);
      74 rows; the unresolved list holds "Atlantis".
    - **(e) D4:** no `input[type=checkbox]`, no `#save-btn`, and `selected_countries` unchanged.
    - **(f) The worker unreachable** (the `PINS` reply fails, simulated by rejecting
      `chrome.runtime.sendMessage` in the page): the pins-failed text, and no pin buttons.
  - **`test_options_pins_and_unpins`** (`ext`):
    - pin "Lesotho" → `pinned_places_v2` gains `iso:LS`, and a second click removes it;
    - "Remove" on "Atlantis" → `unresolved_pins_v2` [];
    - Moldova's row reads "Also shows: <Transnistria's display>", and Somalia's "Also shows:
      <Somaliland's display>";
    - `pinned_countries` is unchanged throughout.
  - **`test_options_text_is_inserted_as_text`:** a v2 card with an unknown place `x:evil` and
    country `<img src=x onerror=alert(1)>` lists that text literally, and creates no `img`.
  - **(rev 2) `test_pin_edits_are_applied_in_order`** (`run_pin_edits`; migrated, places
    `["iso:CV", "iso:MD"]`). Rows:
    - **overlapping:** `[unpin iso:CV, pin iso:LS]` → stored places `["iso:MD", "iso:LS"]`; the
      first reply's pins are `["iso:MD"]`, the second's `["iso:MD", "iso:LS"]`;
    - **rapid:** `[pin iso:LS, unpin iso:LS, pin iso:LS]` → `["iso:CV", "iso:MD", "iso:LS"]`;
    - **the same pin, conflicting:** `[unpin iso:CV, pin iso:CV]` → `["iso:MD", "iso:CV"]` (arrival
      order);
    - **idempotent:** `pin iso:CV` again → unchanged, and no `set`;
    - **rejected, then retried:** `set_fails=(0,)` with `[pin iso:LS, pin iso:LS]` → the first
      reply is `{ok: false, error: "could not save the pins: <msg>"}`, the second is ok, and the
      places end as `["iso:CV", "iso:MD", "iso:LS"]`;
    - **forget:** `forget "Atlantis"` on unresolved `["Atlantis"]` → `[]`;
    - **bad value:** `pin 7` → `{ok: false, error: "not a pin"}`.

    No reply rejects, and `pinned_countries` is never in a `set`.
  - **(rev 2) `test_two_options_pages_edit_pins`** (`ext`; migrated, places `["iso:CV",
    "iso:MD"]`, the pair cached):
    - Open two options pages, A and B. A clicks Unpin on Cape Verde, and B clicks Pin on Lesotho
      without waiting.
    - Stored `pinned_places_v2` is `["iso:MD", "iso:LS"]`.
    - Within 2 s, both pages show Moldova and Lesotho pinned and Cape Verde unpinned. B learns
      about A's edit through `storage.onChanged`.
  - **(rev 2) `test_a_rejected_pin_save_is_reported`** (`ext`). Inject through
    `Ext.worker().evaluate`: the next `chrome.storage.local.set` rejects once with "quota". Then:
    - Click Pin on Lesotho. `#pinStatus` reads "Your change could not be saved: could not save
      the pins: quota. Try again."
    - Lesotho's button shows unpinned (`aria-pressed="false"`) and is enabled again, and the
      stored places are unchanged.
    - Click again: Lesotho is pinned and stored, and `#pinStatus` is empty.
  - **(rev 3) `test_a_late_pin_reply_never_repaints_an_older_state`** (`ext`; migrated,
    places `["iso:CV", "iso:MD"]`, the pair cached; pages A and B). Rows:
    - **A late reply:**
      1. `wrap_pin_messages(A, "hold")`; A clicks Unpin on Cape Verde.
      2. Stored places become `["iso:MD"]`, and A's Cape Verde button stays
         `aria-busy="true"`.
      3. B clicks Pin on Lesotho. Wait until stored places are `["iso:MD", "iso:LS"]` and
         A shows Lesotho pinned.
      4. `release_pin_reply(A)`, then wait for A's `data-pin-sync` "idle".
      5. A and B both show Moldova and Lesotho pinned and Cape Verde unpinned. A's Cape Verde
         button is enabled with no `aria-busy`, and `#pinStatus` is empty.
    - **An older read:**
      1. Start from `["iso:MD", "iso:LS"]`, both pages idle. `wrap_pin_reads(A,
         "hold-next")`, then A clicks Unpin on Moldova. Wait until `window.__pinReadHeld` has
         places `["iso:LS"]` and A shows Moldova unpinned (A's other `reconcile()`, from the
         reply or the storage event, drew it). Waiting first means the held read cannot see
         B's edit.
      2. B clicks Pin on Cape Verde. Wait until A shows `["iso:LS", "iso:CV"]`, drawn by a
         later `reconcile()`.
      3. `release_pin_read(A)`, then wait for A's "idle".
      4. A still shows Lesotho and Cape Verde pinned, which is what is stored.
  - **(rev 3) `test_a_lost_pin_reply_is_reconciled`** (`ext`; migrated, places
    `["iso:CV", "iso:MD"]`, the pair cached). After each click, wait for
    `data-pin-sync` "idle". Rows, in order:
    - **Lost before the save** (`"reject-before"`):
      - click Unpin on Cape Verde;
      - `#pinStatus` reads "Your change could not be confirmed: Could not establish
        connection. Receiving end does not exist. The list shows your saved pins.";
      - Cape Verde still shows pinned (`aria-pressed="true"`), enabled, with no `aria-busy`;
      - the stored places are unchanged;
      - click Unpin again: stored `["iso:MD"]`, and `#pinStatus` is empty.
    - **Lost after the save** (`"reject-after"`):
      - click Pin on Lesotho;
      - `#pinStatus` reads "Your change could not be confirmed: The message port closed
        before a response was received. The list shows your saved pins.";
      - Lesotho shows pinned, from storage, and is enabled;
      - stored `["iso:MD", "iso:LS"]`, with `iso:LS` once;
      - a later edit, Unpin on Moldova, works: stored `["iso:LS"]`, and `#pinStatus` is
        empty.
    - **No usable reply** (`"no-reply"`):
      - click Pin on Moldova;
      - `#pinStatus` reads "Your change could not be confirmed: no usable reply. The list
        shows your saved pins.";
      - Moldova shows unpinned and enabled, and the stored places are unchanged.
    - **A failed read** (`wrap_pin_reads(page, "fail")`):
      - click Pin on Cape Verde;
      - stored `["iso:LS", "iso:CV"]`;
      - `#pinStatus` reads "Your saved pins could not be read: boom. Reload this page to try
        again.", and the button is enabled;
      - after a reload, Cape Verde shows pinned.

    Retrying the same intent can only come from a page that still shows the old state, and
    there the worker's idempotent ops apply: `test_pin_edits_are_applied_in_order`'s
    idempotent row.
  - **(rev 2) `test_only_the_worker_writes_pins`** (static): `options.js`, `popup.js`,
    `lib/render.js` and `lib/legacy.js` contain no `storage.local.set` and no `storage.local.remove`.
  - **Existing tests:**
    - the `test_counting.py` pin rows switch to place ids;
    - `test_the_v1_cache_and_pins_are_left_alone` also asserts that `pinned_countries` and
      `selected_countries` are unchanged after a migration;
    - `PURE_MODULES` gains `pins.js`.

- [ ] **Step 2: Run them and see them fail** (missing module, missing `places.json`, the v1 options
  page).

- [ ] **Step 3: Write `scripts/build_extension_places.py`**, then run it to create `places.json`.

- [ ] **Step 4: Implement `pins.js` as P140,** then `loadPlaces`.
  - `background.js` single-flights `migratePins` and loads the table once per worker life, like
    the schemas.
  - **(rev 2)** Implement `applyEdit` and `editQueue`. `background.js` makes one `editPin`.
  - Wire the worker's new handler order and the `PIN_EDIT` message.

- [ ] **Step 5: Switch the views to place pins.**
  - `popup.js` reads the four pin keys and the table, computes `currentPins`, and passes `pinned`
    and `table`.
  - `count.view` uses `pins`; `render.js` builds `pinMatcher`.
  - `legacy.js` filters with `pinMatcher(pinned, table)(placeOf(e.country, table))`.

- [ ] **Step 6: Rewrite the options page** as P141, with the copy above, `textContent` only.
  **(rev 2)** Edits go through `PIN_EDIT` with P141's pending, failed and saved states, plus the
  `storage.onChanged` redraw. The page never writes storage.
  **(rev 3)** All pin drawing goes through the guarded `reconcile()`, with `data-pin-sync`, the
  "not confirmed" and "could not be read" texts, and pending state kept per value.

- [ ] **Step 7: Run the tests until they pass, then the extension suite three times.**

- [ ] **Step 8: Mutations** (`plan5b2-task-2.json`):

  | Test | Mutation |
  |---|---|
  | `test_places_table_matches_the_registry` | the generator drops the display from `names` |
  | `test_every_v1_pin_string_migrates` | the lookup lower-cases the name |
  | `test_pin_migration` | the flag is set without the read-back |
  | `test_a_parent_pin_includes_its_places` | the matcher checks the place only |
  | `test_pins_survive_and_filter_the_popup` | `popup.js` reads `pinned_countries` |
  | `test_the_worker_migrates_pins_on_install_update_and_startup` | `startup` skips `migratePins` |
  | `test_options_lists_feed_places_and_pins` | `optionPlaces` skips the listings |
  | its row (c2) (rev 2) | without a valid record, the page lists nothing |
  | `test_options_pins_and_unpins` | **(rev 2)** the `pin` op writes `pinned_countries` instead of `pinned_places_v2` |
  | `test_options_text_is_inserted_as_text` | the name through a markup sink (the static test then fails too; record both) |
  | `test_pin_edits_are_applied_in_order` (rev 2) | `editQueue` runs each edit as it arrives, without waiting for the previous one |
  | `test_two_options_pages_edit_pins` (rev 2) | the options page adds no `storage.onChanged` listener, so page B never shows A's edit |
  | `test_a_rejected_pin_save_is_reported` (rev 2) | on a failed reply the page leaves `#pinStatus` empty |
  | `test_a_late_pin_reply_never_repaints_an_older_state` (rev 3), the late-reply row | on `ok` the page draws the reply's `pins` (revision 2's rule) |
  | `test_a_late_pin_reply_never_repaints_an_older_state` (rev 3), the older-read row | `reconcile()` draws without checking its generation |
  | `test_a_lost_pin_reply_is_reconciled` (rev 3) | a rejected `sendMessage` is not caught, so the button stays busy and nothing reconciles |
  | `test_only_the_worker_writes_pins` (rev 2) | `options.js` writes `pinned_places_v2` with `chrome.storage.local.set` |

  Re-run `plan5b1-task-6.json` (`count.js`, `render.js`, `legacy.js`).

- [ ] **Step 9: Run the gates, then commit.**
  `git commit -m "feat(extension): pins as places, one-time migration, the options page lists feed places (Plan 5b-2 Task 2)"`.

### Task 3: Safe links, text in both renderers, and the renderer matrix (R52, R60, R61; P142; S5-T18, S5-T17)

**Files:**
- Create: `extension/lib/links.js`
- Modify: `extension/lib/legacy.js` (rebuilt with DOM calls), `extension/lib/schema.js` (the
  root pointer)
- Modify: `tests/support/extension.py` (`Ext.opened`)
- Test: `tests/extension/test_links.py`, `tests/extension/test_renderers.py`,
  `tests/extension/test_extension_files.py`, `tests/extension/test_validate.py` (root-pointer rows)

**Interfaces:**
- Consumes: `elections_calendar.model.SOURCE_NAMES`; the fixture pair; `v1_feed()`;
  `republication`.
- Produces:
  - **`links.js`:**
    - `SOURCES` (P142's nine rows);
    - `sourceOf(nameOrKey) -> {key, name, hosts, home} | null`;
    - `sourceName(nameOrKey) -> string` (the display name, else its argument);
    - `safeLink(nameOrKey, url) -> string | null`.
  - **`Ext.opened(action: Callable[[], None]) -> list[str]`:** the URLs of the tabs the action
    opens within 5 s. While it runs, every `https` request outside the raw host is answered by a
    stub page, and the opened tabs are closed after.

- [ ] **Step 1: Write the failing tests**
  - **`test_safe_links`** (`lab`; pure). Rows (source, url) → result:
    - ("Wikipedia", "https://en.wikipedia.org/wiki/X") → the same;
    - ("wikipedia", same) → the same;
    - ("Wikipedia", "https://EN.WIKIPEDIA.ORG/wiki/X") → "https://en.wikipedia.org/wiki/X";
    - ("NDI", "https://ndi.org/a") and ("NDI", "https://www.ndi.org/a") → the same;
    - ("OSCE/ODIHR", "https://www.osce.org/x") → the same;
    - each of these gives the home page:
      - "javascript:alert(1)", "data:text/html,x", "http://en.wikipedia.org/";
      - "https://u:p@en.wikipedia.org/", "https://en.wikipedia.org:8443/";
      - "https://en.wikipedia.org.evil.example/", "https://evilwikipedia.org/",
        "https://de.wikipedia.org/";
      - "https://xn--wkipedia-c6a.org/";
      - "", "/wiki/X", `null`, 42;
    - ("https://en.wikipedia.org:443/x") → "https://en.wikipedia.org/x";
    - ("Unknown", "https://example.org/") → `null`;
    - every `home` gives itself.
  - **`test_links_match_the_producers_sources`:** `SOURCES`' keys and names equal
    `SOURCE_NAMES`, and each row's `hosts` equal §12.6's table.
  - **`test_legacy_opens_only_safe_links`** (`ext`). The v1 feed, cached.
    - Clicking the chip of the `focustaiwan.tw` A-WEB link opens `["https://www.aweb.org/"]`.
    - A v1 card edited to have Wikipedia's link `javascript:alert(1)`: its chip and its body open
      `["https://en.wikipedia.org/"]`.
    - A source named "Unknown": its chip is not a button, and clicking it opens `[]`.
  - **`test_legacy_text_is_inserted_as_text`** (`ext`): a v1 card whose country, type and source
    name are `<img src=x onerror=alert(1)>` shows them literally; the list has no `img`.
  - **`test_no_feed_text_through_inner_html_in_v2_code`** (widened, R60): every
    `extension/**/*.js`; the six sinks; no exemption.
  - **`test_renderer_matrix`** (S5-T17; parametrised). The files are `legacy_ext` (v1.0.2) or
    `ext` (v2); each cell clears storage, routes `elections.json` (no `status.json`) and opens the
    popup.

    | Files | v1 feed | v2 feed (artifact) | `{"schema_version": 2, "months": {}}` | `{not json` |
    |---|---|---|---|---|
    | v1.0.2 | 27 October cards, "OCTOBER 2026" | 30 October cards (S1-T7) | stays on loading; one page error "Cannot read properties of undefined (reading 'split')" (v1.0.2's own failure, recorded) | error state, the v1.0.2 parse message |
    | v2 | `data-renderer` legacy, 27 cards, banner "Current health can't be confirmed for this data" | `data-renderer` v2, 30 cards, banner "Current health can't be confirmed for this data" | error state "Could not load data: elections.json: unreadable feed: /: missing content_id" | error state "Could not load data: elections.json: not UTF-8 JSON" |

    In the v2 row, no page errors, and nothing is stored for the two malformed cells.
  - **`test_renderer_switches_inside_one_popup`** (R61; `ext`). One open popup, each step through
    a forced Refresh:
    1. Start with the v1 feed (legacy).
    2. Serve the artifact pair → v2.
    3. Serve the real rollback, `republication(v1_feed(), now=<after the pair's generated_at>)`
       → legacy, with the banner "Source health isn't available for this data" (linked legacy).
    4. Serve a v2 pair newer than step 3: the fixture feed through `_at`, with a status through
       `_links`. Move both helpers from `test_loading.py` to `tests/support/extension.py` as
       `published_at(feed, key)` and `linking(feed, status, attempt_at=None)`. → v2.

    At each step:
    - `body[data-renderer]` names the format;
    - the bento labels are the format's ("Election records"/"Confirmed held", or "Total
      Scheduled"/"Held This Month");
    - `#recordCount` shows only for v2;
    - one card list of the format's class;
    - the highlighted tab equals the shown list;
    - a search typed before the step filters the new list, and only the active renderer answers it;
    - no page errors.
  - **`test_validate.py`:** the root rows read "/: missing content_id".
  - **`PURE_MODULES`** gains `links.js`.

- [ ] **Step 2: Run them and see them fail.**

- [ ] **Step 3: Implement `links.js`** (P142).

- [ ] **Step 4: Rebuild `legacy.js`'s cards with `createElement`/`textContent`.**
  - Keep every class and v1.0.2's visible text.
  - Chips and the card body open `safeLink(source.name, source.link)` and nothing when that is
    null.
  - Remove `escHtml`.
  - Every listener still checks `active()`.

- [ ] **Step 5: Fix the root pointer in `schema.js`:** `p === "" ? "/" : p`.

- [ ] **Step 6: Add `Ext.opened`,** then run the tests until they pass, then the extension suite
  three times.

- [ ] **Step 7: Mutations** (`plan5b2-task-3.json`):

  | Test | Mutation |
  |---|---|
  | `test_safe_links` | the host check `endsWith(host)` without the dot |
  | `test_links_match_the_producers_sources` | EEAS's name "EU EEAS" |
  | `test_legacy_opens_only_safe_links` | the chip opens `source.link` |
  | `test_legacy_text_is_inserted_as_text` | the country set with `innerHTML` |
  | the widened static test | `legacy.js` gains `new DOMParser()` in a comment-free line |
  | `test_renderer_matrix` | `feedFormat`'s legacy branch accepts a `schema_version` key |
  | `test_renderer_switches_inside_one_popup` | `popup.js` sets `data-renderer` after rendering legacy |
  | the root rows | the pointer fix reverted |

  Re-run `plan5b1-task-3.json` (`schema.js`) and `plan5b1-task-6.json` (`legacy.js`).

- [ ] **Step 8: Run the gates, then commit.**
  `git commit -m "feat(extension): safe links and text in both renderers; the renderer matrix (Plan 5b-2 Task 3)"`.

### Task 4: v2 cards: details on expand, sources, umbrellas, possible matches, chips (R25, R22, R47, ruling 8, Q1; P143, P145)

**Files:**
- Create: `extension/lib/details.js`
- Modify: `extension/lib/labels.js`, `extension/lib/count.js`, `extension/lib/render.js`,
  `extension/styles.css`
- Test: `tests/extension/test_cards.py`, `tests/extension/test_labels.py` (chip shape),
  `tests/extension/test_counting.py`, `tests/extension/test_renderers.py` (the switch test gains an
  expanded card)

**Interfaces:**
- Consumes: `links.safeLink`; `labels.sourceNote`; `dates.dayMonthYear`, `monthYear`;
  `count.view`.
- Produces:
  - **`labels.childLabel` chips:** `{kind: "tentative" | "subnational" | "rescheduled", text}`.
  - **`details.js`:**
    - `childIndex(doc) -> Map<child_id, {card, child}>`;
    - `possibleLines(ids, outside, index) -> string[]`;
    - **(rev 2)** `sourceLine(source) -> string` (P143's line and tags);
    - **(rev 2)** `childDetails(card, child, {index}) -> {heading, sources: [{name, text, link}], umbrellas: [{name, text, link}], possible: string[]}`.
      It is time-free and returns no label.
  - **`count.startMonth(doc, today) -> string`.**
  - **Card DOM:** `button.card-toggle` (`aria-expanded`, `aria-controls`) and
    `div.card-details#details-<group_id>`, one `.child-entry` per kept child. In an entry:
    `.child-heading`, `.child-label` (**rev 2:** the view's `label` for that child), `.source-line`
    (`.source-open` buttons, named as P143) and `.umbrella-line`.

- [ ] **Step 1: Write the failing tests**
  - **`test_rescheduled_chip`** (R25; `lab`): `rescheduled_from` `["15 November", "22 November"]`
    gives the chip `{kind: "rescheduled", text: "Rescheduled from 15 November, 22 November"}`.
    `[]` gives none. The `test_exact_dates` chip rows become objects.
  - **`test_an_undated_fallback_confirmation_is_flagged`** (ruling 8; `lab`). Rows:
    - a held child with the template's selected non-fallback source, plus a non-selected
      `fallback: true`, `status_claim: "held"`, `fetched_at: null` source → notes ["Unverified: the
      source data's date is unknown"];
    - the same with the selected source also a null-time fallback → the note once;
    - a dated held fallback → "Confirmed by source data from <date>", unchanged.
  - **`test_umbrella_shown_per_child`** (R25; `lab`; `childDetails` on the fixture). South Sudan
    2026-12-22:
    - the Presidency's umbrella lines name NDI and A-WEB;
    - the Assembly's and the Council's name NDI, A-WEB and EISA;
    - EISA's line reads "Also listed by EISA: National Legislative Assembly, 22 December 2026".
  - **`test_possible_matches_and_umbrellas_are_labelled`** (R22; `lab`):
    - Cameroon 2026-12: ["Provisional: may be the same contest as Cameroon National Assembly,
      January 2027"];
    - Kyrgyzstan 2027-01-24: ["Provisional: may be the same contest as Kyrgyzstan Kyrgyz
      Presidency, 27 January 2027"];
    - an edited child with `possible_matches_outside` 1 adds "Provisional: 1 possible match
      outside the monitored window", and with 3, "… 3 possible matches …";
    - an unknown id gives no line;
    - Brazil has two cards on 2026-10-04. NDI's and A-WEB's umbrellas show on each of the three
      children of card `54b356d5b5ea`. Wikipedia's "Governors" shows on each of the 18 children of
      card `c8c9844ab7a8`. Neither card shows the other's.
  - **`test_per_source_dates_for_date_conflicts`** (`lab`):
    - Cape Verde's child source lines are, in feed order, "ElectionGuide: 2026-11-15 (d) to
      2026-11-15 (d) (used)", "Wikipedia: 15 November", "NDI: November 15, 2026 (ALL DAY)",
      "EISA: October 2026";
    - Nigeria's two children each list ElectionGuide (used), Wikipedia and **(rev 2)** "IPU: 28
      Feb 2027 · expected renewal, not an announced date" (that IPU source's `evidence_kind` is
      `expected_renewal`);
    - each line's `link` equals its `safeLink`.
  - **(rev 2) `test_source_lines_say_who_claims_what`** (C01; `lab`; `sourceLine` and
    `childDetails`). Edited children stay schema-valid.
    - **Sweden** `451e4f4c0054`, as it is: ["ElectionGuide: 2026-09-13 (d) to 2026-09-13 (d)
      (used) · reports it held", "OSCE/ODIHR: 13 Sep 2026", "Wikipedia: 13 September"].
    - **The same date, a different claim:** Cape Verde's child, edited.
      - Wikipedia's and NDI's `date_text` are both "15 November 2026"; NDI has `status_claim:
        "postponed"`, and the child has `status_conflict: true`.
      - The lines are "Wikipedia: 15 November 2026" and "NDI: 15 November 2026 · reports it
        postponed".
      - Swap which source carries the claim: the tags swap, so the two line lists differ.
    - **Saved data beside fresh:** Wikipedia with `fallback: true`.
      - With `fetched_at` "2026-10-01T06:00:00Z": "Wikipedia: 15 November · saved data from 1 Oct
        2026".
      - With `fetched_at` null: "… · saved data, date unknown".
    - **Observation:** OSCE/ODIHR with `evidence_kind: "observation"` → "OSCE/ODIHR: 13 Sep 2026 ·
      observation mission dates".
    - **Several tags, in order:** `status_claim` "cancelled", `fallback` with a date and
      `provisional: true` → "<name>: <date_text> · reports it cancelled · saved data from <d> · Newer
      data from an incomplete fetch on <d>".
    - **Ordinary sources stay plain:** every Cape Verde line as it is.
  - **(rev 2) `test_expanded_labels_match_the_card_face`** (C03; `ext`). One-child cards, opened at
    a fixed page clock P. In each row, the expanded entry's label text, chips and notes equal the
    card face's, and both equal `childLabel(card, child, {today, now: P})` computed in the lab.
    - **(a) The week boundary:** a selected fallback source fetched 7 days − 1 min before P
      ("Using source data from …"), and one fetched 7 days + 1 min before P ("Unverified since
      …").
    - **(b) The local date:** a day card dated the page's local today, with the clock at 23:59
      local ("Scheduled voting period: today (approx.)").
    - **(c) A change of view:** after a search and a tab change that keep the card, the open
      entry still matches its face.
  - **`test_cards_expand_on_demand`** (`ext`; the pair cached, October):
    - no `.child-entry` before any click;
    - the toggle of card `c8c9844ab7a8` (Brazil 2026-10-04, 18 children): `aria-expanded` "true",
      "Hide details", 18 entries;
    - a search matching one Brazil child (the test picks a word from one `office_label`): "1
      matching of 18", and the open details show 1 entry;
    - clearing it gives 18 again, still open;
    - the toggle again: details hidden, `aria-expanded` "false";
    - Enter on the focused toggle opens it;
    - the card face shows no chip twice.
  - **`test_source_entries_open_only_safe_links`** (R47; `ext`):
    - the ElectionGuide Open of child `451e4f4c0054` (Sweden 2026-09-13, card `fcd48da30f32`) →
      `["https://www.electionguide.org/elections/id/5079/"]`;
    - an edited child with Wikipedia `javascript:alert(1)` → `["https://en.wikipedia.org/"]`;
    - a source named "Evil" has no `.source-open` button;
    - an umbrella's Open goes through `safeLink`;
    - **(rev 2)** the Sweden button's accessible name is `Open ElectionGuide for <its heading>
      (new tab)`. In card `c8c9844ab7a8`, the 18 Wikipedia "Governors" umbrella buttons have 18
      distinct names, provided the 18 child headings are distinct (the test asserts that first);
    - clicking the card body still opens `[]` (ruling 30).
  - **`test_card_details_text_is_inserted_as_text`:** hostile `office_label`, `jurisdiction`,
    `date_text`, umbrella `office_label` and source name show literally, with no element created.
    `PURE_MODULES` gains `details.js`.
  - **`test_a_month_outside_the_window_falls_back`** (Q1). `startMonth` rows:
    - in window → `current_month`;
    - "2027-05" with today 2026-10-19 → "2026-10";
    - "2027-05" with today 2027-06-01 → "2026-09";
    - empty window → `current_month`.

    In the popup, the artifact with `current_month` "2027-05" cached opens on "OCTOBER 2026" with
    30 cards.
  - **`test_renderer_switches_inside_one_popup`:** a Brazil card expanded before step 3 leaves no
    `.card-details` in the legacy list; after step 4 the card is open again (remembered by
    `group_id`).

- [ ] **Step 2: Run them and see them fail.**

- [ ] **Step 3: Implement the label changes** (chips, the ruling-8 note) in `labels.js`.

- [ ] **Step 4: Implement `details.js` and `count.startMonth`.** **(rev 2)** `render.js` fills
  each entry's `.child-label` from the view's `label` for that child; `details.js` computes no
  label.

- [ ] **Step 5: Implement the disclosure in `render.js`:**
  - the open set and the toggle;
  - entries built only for open cards;
  - Open buttons calling `chrome.tabs.create({url})` with `safeLink`'s non-null result;
  - listeners checking `active()`;
  - the CSS for entries, which wrap.

- [ ] **Step 6: Run the tests until they pass, then the extension suite three times.**

- [ ] **Step 7: Mutations** (`plan5b2-task-4.json`):

  | Test | Mutation |
  |---|---|
  | `test_rescheduled_chip` | join with " · " |
  | `test_an_undated_fallback_confirmation_is_flagged` | no note when `times` is empty |
  | `test_umbrella_shown_per_child` | every umbrella on every child |
  | `test_possible_matches_and_umbrellas_are_labelled` | `monthYear` → `dayMonthYear` for month dates |
  | `test_per_source_dates_for_date_conflicts` | the selected source only |
  | `test_source_lines_say_who_claims_what` (rev 2) | `sourceLine` leaves out the claim tag |
  | `test_expanded_labels_match_the_card_face` (rev 2) | the entry computes its own label with `childLabel(card, child, {today, now: 0})` |
  | `test_cards_expand_on_demand` | details built at draw time |
  | `test_source_entries_open_only_safe_links` | Open uses `source.link` (rev 2: and a second mutation, the umbrella button named without `for <heading>`, killed by the distinct-names row) |
  | `test_card_details_text_is_inserted_as_text` | the heading set as markup (the static test also fails; record both) |
  | `test_a_month_outside_the_window_falls_back` | `startMonth` returns `current_month` |
  | the switch-test addition | the open set cleared on every render |

  Re-run `plan5b1-task-2.json` and `plan5b1-task-6.json`.

- [ ] **Step 8: Run the gates, then commit.**
  `git commit -m "feat(extension): v2 card details, chips, source links and the start month (Plan 5b-2 Task 4)"`.

### Task 5: The attention and undated section (S5-T10, S5-T11, R50; P144)

**Files:**
- Create: `extension/lib/attention.js`
- Modify: `extension/lib/render.js`, `extension/popup.html` (`#attention`), `extension/popup.js`
  (hidden for non-v2), `extension/styles.css`
- Test: `tests/extension/test_attention.py`, `tests/extension/test_renderers.py`

**Interfaces:**
- Consumes: `details.childIndex`, `possibleLines`; `links.safeLink`, `sourceName`;
  `dates.monthName`.
- Produces:
  - **(rev 2) `attention.attentionTitle({k, included, total, months}) -> string`.** `k` is
    `null` without a search (P144's three forms).
  - **(rev 2) `attention.truncationNote({included, total}) -> string`.** It is "" when nothing
    was cut.
  - **(rev 2) `attention.shownLine(shown, of) -> string`.** It gives "Showing <shown> of <of>",
    or "" when they are equal.
  - **`attention.attentionView(doc, {query, index}) -> {title, note, rows: [{id, text, source, undated, possible, link, label}]}`.**
    `label` is the Open button's name (P144).
  - **`ATTENTION_PAGE = 200`.**
  - **The DOM:** `#attention` > `button#attentionToggle` (`aria-expanded`,
    `aria-controls="attentionList"`) + `p#attentionNote` (visible while collapsed) +
    `ul#attentionList` (`.attention-row`) + `p#attentionShown` + `button#attentionMore`.

- [ ] **Step 1: Write the failing tests**
  - **`test_attention_items_are_listed`** (S5-T10: 20 items, 5 samples; `lab` and `ext`). The
    artifact with `attention_items` cut to 20, chosen by `item_id`, including `612356b9548b`, one
    `undated_listing` item (Lesotho's) and `36ad1dcad007`.
    - The title is "20 items across the monitored window (Sep–Jan)".
    - There are 20 rows.
    - Five samples, field by field:
      - `612356b9548b`: source "EEAS"; possible lines ["Provisional: may be the same contest as
        <its match's country office, date>", "Provisional: 1 possible match outside the monitored
        window"];
      - Lesotho's: "Undated: Lesotho, Parliament, 2027";
      - `36ad1dcad007`: "Provisional: 4 possible matches outside the monitored window";
      - two Wikipedia rows: their text and the link as given.
  - **`test_attention_section_is_always_reachable`** (S5-T11, R50; `ext`; the pair cached):
    - for each month Sep–Jan × tab × level, `#attentionToggle` is visible with "157 items across
      the monitored window (Sep–Jan)";
    - with a search matching no card: the empty state shows below the section;
    - with pins matching nothing: still 157;
    - a search "Lesotho": "<k> of 157 items …", where `k` is computed by the test from the item
      fields P144 searches;
    - opening the section leaves `#recordCount`'s text unchanged;
    - the legacy renderer hides the section;
    - no data hides it (ruling 22);
    - **(rev 2)** with nothing cut, there is no `#attentionNote` and no "in this data" wording.
  - **`test_attention_rendering_is_bounded`** (`ext`). A synthetic feed with 500 items and
    `attention_truncated` 1,200. **(rev 2)** The copy is P144's:
    - **collapsed:** the toggle reads "1700 items across the monitored window (Sep–Jan)". The
      note reads "This data includes 500 of the 1700 items. The other 1200 are in
      attention_full.json, in the "generation" artifact of the GitHub Actions run that published
      it (kept 14 days). Searches here do not cover them." No rows are rendered;
    - **after opening:** 200 rows, and "Showing 200 of 500";
    - "Show 200 more" → 400 rows, "Showing 400 of 500";
    - "Show 100 more" → 500 rows; the button and the shown line are hidden.
  - **(rev 2) `test_a_search_over_cut_items_says_what_it_searched`** (C04; `ext`; the same
    synthetic feed, where one included item mentions "Lesotho" and 250 mention "Peru"). Rows:
    - **a match only among the cut items** (a word no included item has): "0 of the 500 items in
      this data match (1700 in total, Sep–Jan)", and the note still says searches do not cover
      the other 1200. **(2026-10-28)** With the section collapsed, no card matches either: the
      empty state shows below the section, and the toggle with its count and `#attentionNote`
      stay visible;
    - **one match:** "1 of the 500 items in this data match (1700 in total, Sep–Jan)", 1 row, no
      shown line;
    - **250 matches:** 200 rows, "Showing 200 of 250"; "Show 50 more" → 250 rows;
    - **reset:** the 250 "Peru" items also mention "Lima". After "Show 50 more", changing the
      search to "Lima" shows 200 rows again;
    - **untruncated** (the fixture pair): "<k> of 157 items across the monitored window (Sep–Jan)"
      for "Lesotho" (k computed by the test, as above), with no note.
  - **`test_attention_links_are_safe`:** an item with `source` "wikipedia" and link
    `javascript:x` opens `["https://en.wikipedia.org/"]`; an item with source "nope" has no Open
    button. **(rev 2)** The Open button's name is `Open Wikipedia: <the item's text, cut to 80
    characters> (new tab)`.
  - **`test_attention_text_is_inserted_as_text`:** hostile item text and listing fields show
    literally. `PURE_MODULES` gains `attention.js`.
  - **`test_renderer_switches_inside_one_popup`:** the section open before step 3 is hidden in
    legacy, and open again at step 4.

- [ ] **Step 2: Run them and see them fail.**

- [ ] **Step 3: Implement `attention.js`** (P144's copy and rules).

- [ ] **Step 4: Add the section to `popup.html` and `render.js`:**
  - rows built only while open;
  - the page size 200;
  - the open state kept;
  - listeners checking `active()`;
  - `popup.js` hiding it for non-v2.

- [ ] **Step 5: Run the tests until they pass, then the extension suite three times.**

- [ ] **Step 6: Mutations** (`plan5b2-task-5.json`):

  | Test | Mutation |
  |---|---|
  | `test_attention_items_are_listed` | the source key shown instead of the name |
  | `test_attention_section_is_always_reachable` | the section hidden when the month has no cards |
  | `test_attention_rendering_is_bounded` | page size 500 |
  | `test_a_search_over_cut_items_says_what_it_searched` (rev 2) | with a search, the title uses N (total) in place of A (included): "0 of 1700 items …" |
  | `test_attention_links_are_safe` | Open uses `item.link` |
  | `test_attention_text_is_inserted_as_text` | the text set as markup (the static test also fails; record both) |
  | the switch-test addition | `popup.js` leaves the section visible for legacy |

- [ ] **Step 7: Run the gates, then commit.**
  `git commit -m "feat(extension): the attention and undated section (Plan 5b-2 Task 5)"`.

### Task 6: Accessibility, layout and limits (S5-T19, S5-T21, R26/R51, R59; P146)

**Files:**
- Modify: `extension/popup.html` (the tablist, `#listPanel`, `.dock`), `extension/styles.css`,
  `extension/lib/render.js`, `extension/lib/legacy.js` (tab attributes and keys),
  `extension/popup.js` (performance marks), `extension/options.css` (focus)
- Modify: `tests/support/extension.py` (`synthetic_feed`; rev 2: `Served`'s `"hold"` and
  `release`)
- Test: `tests/extension/test_accessibility.py`, `tests/extension/test_limits.py`

**Interfaces:**
- Consumes: Tasks 4–5's DOM.
- Produces:
  - **The performance marks** `popup:read` (before the first storage read of `render()`) and
    `popup:drawn` (after `drawHealth`), and the measure `popup:first-render`, made on the first
    render only.
  - **(rev 2) `Served` holds a response:** the `Response` type gains `"hold"`. The route is
    kept, unanswered, until `Served.release(name: str, response: bytes | int) -> None`
    fulfills it as a queued response would. `release` with nothing held raises
    `AssertionError`.
  - **`synthetic_feed(base: bytes, *, cards: int = 0, children: int = 0, items: int = 0, truncated: int = 0) -> bytes`:**
    October gains `cards` one-child cards, and one card with `children` children; the feed gets
    `items` attention items. Ids are fresh 12-hex values, and the result is schema-valid and
    under 4,000,000 bytes.

- [ ] **Step 1: Write the failing tests**
  - **`test_keyboard_and_aria_semantics`** (S5-T19; `ext`; **rev 2:** renamed. These are
    automated role, state, keyboard and focus checks; no screen reader is run):
    - `get_by_role("tablist", name="Show")` holds tabs "Upcoming", "Past" and "All"; "All" has
      `aria-selected="true"` and `tabindex="0"`, the others "false" and "-1";
    - on "All", ArrowRight selects "Upcoming" (wrapping), Home selects "Upcoming" and End selects
      "All"; the selection changes the list and `#listPanel`'s `aria-labelledby`;
    - `get_by_role("button", name="Show details")` exposes `expanded=False`, then `True`; so do
      the attention toggle, the banner and `#filterToggle`;
    - after keyboard focus (Tab) on each of: a tab, `#refreshBtn`, a card toggle, an Open button
      and the attention toggle, the computed `outline-style` is not "none" and `outline-width` is
      "2px";
    - `#recordCount` has `aria-live="polite"`;
    - the same tab attributes after a legacy render;
    - the options page's pin buttons expose `aria-pressed`;
    - **(rev 2)** with Sweden's card open, its child's Open control is found by
      `get_by_role("button", name="Open ElectionGuide for <heading> (new tab)")`, the name
      Task 4 builds; each attention row's Open control is found by its P144 name.
  - **(rev 2) `test_focus_survives_a_redraw`** (`ext`):
    - **Set up:** the pair cached, with a check due. `elections.json` is served `"hold"`, so
      the popup draws the cache and its check waits. The test acts, then calls
      `ext.served.release("elections.json", <bytes>)` and waits for `data-checking` "false",
      the second draw. No sleeps.
    - **Toggle row:** focus (`locator.focus()`) the toggle of card `c8c9844ab7a8` and press
      Enter, then release the same bytes. After the redraw, `document.activeElement` is that
      toggle (its `data-focus` is `toggle:c8c9844ab7a8`), and it is still expanded.
    - **Open-button row:** the same with the first Open button inside that open card
      (`open:<child_id>:0`).
    - **A focused control that is gone:** with that toggle focused, release the real rollback,
      `republication(v1_feed(), now=<after the pair's generated_at>)` as in
      `test_renderer_switches_inside_one_popup`. The redraw is the legacy view, which has no
      card toggles, and focus lands on `#listPanel`.
    - **The search box:** type "Bra", leave it focused, release the same bytes. It keeps focus,
      its value and its caret (`selectionStart` 3).
  - **`test_layout_in_a_narrow_or_short_popup`** (R59; `ext`). Viewports 320 × 600 and
    380 × 300. The data:
    - the artifact with 10 source issues (warnings and errors added across four sources);
    - the US 2026-11-03 card cut to 27 children;
    - opened on November, with the panel open, that card expanded and the attention section open.

    The assertions:
    - `scrollWidth <= innerWidth`;
    - each of these, after `scrollIntoView`, lies inside the viewport, and
      `document.elementFromPoint` at its centre is it or inside it: every tab, `#refreshBtn`,
      `#helpBtn`, both month arrows, the banner, `#filterToggle`, the card's toggle, the 27th
      entry's last Open button, the first attention row, and both footer lines;
    - Tab reaches the 27th entry's last Open button within 400 presses.
  - **`test_popup_renders_the_fixture_feed_within_the_budget`** (R51, R26, D6; `fresh_ext`):
    - the pair cached, with `check_state_v2.ok_at` = the real now, opened with `now=None`;
    - `popup:first-render`'s duration is recorded with `record_property("popup_first_render_ms",
      …)` and printed;
    - it is under 1000 ms.
  - **`test_large_collections_render_bounded`** (S5-T21; `ext`). `synthetic_feed(cards=1000,
    children=500, items=500, truncated=1200)`:
    - it validates as `v2`;
    - October shows 1,001 cards and 0 `.child-entry`;
    - expanding the big card gives 500 entries;
    - the attention section shows 200 rows once opened;
    - no page errors;
    - the first-render time is recorded, not asserted.

- [ ] **Step 2: Run them and see them fail.**

- [ ] **Step 3: Implement P146:**
  - the tab ARIA and the keys in both renderers;
  - the disclosures;
  - `:focus-visible`;
  - the dock and the small-height mode;
  - the width rule.

  Then add the marks in `popup.js`.

- [ ] **Step 4: Run the tests until they pass, then the extension suite three times.**

- [ ] **Step 5: Mutations** (`plan5b2-task-6.json`):

  | Test | Mutation |
  |---|---|
  | `test_keyboard_and_aria_semantics` | ArrowRight not handled |
  | `test_focus_survives_a_redraw` (rev 2) | the render does not restore the focused key |
  | `test_layout_in_a_narrow_or_short_popup` | `.dock` back to `position: fixed` |
  | `test_popup_renders_the_fixture_feed_within_the_budget` | the marks removed (the test fails on a missing measure) |
  | `test_large_collections_render_bounded` | details built for every card at draw time |

  Re-run `plan5b2-task-4.json` and `plan5b2-task-5.json`.

- [ ] **Step 6: Run the gates, then commit.**
  `git commit -m "feat(extension): keyboard and ARIA semantics, focus across redraws, a layout for narrow and short popups, and the popup budget (Plan 5b-2 Task 6)"`.

### Task 7: Release files: version, help, release notes, the ZIP (S5-T20, R54; P148)

**Files:**
- Modify: `extension/manifest.json`, `extension/help.html`, `README.md` (building the ZIP)
- Create: `scripts/build_extension_zip.py`, `docs/extension/v2.0.0-release-notes.md`
- Test: `tests/scripts/test_build_extension_zip.py`, `tests/extension/test_release_files.py`,
  `tests/extension/test_extension_files.py`

**Interfaces:**
- Consumes: every earlier task's files.
- Produces:
  - `VERSION = "2.0.0"`;
  - `ZIP_NAME = "Global_Elections_Calendar_v2.0.0.zip"`;
  - `FILES: Final[tuple[str, ...]]`, relative to `extension/`, with `manifest.json` first;
  - `V1_PERMISSIONS`, the v1.0.2 manifest's permission keys and values;
  - `class ZipCheckError(Exception)`;
  - `problems(folder: Path) -> list[str]`;
  - `build(folder: Path = EXTENSION, out_dir: Path = DIST) -> tuple[Path, str]` (the path and its
    SHA-256);
  - `release_row(sha256: str, count: int) -> str`, which names `platform.python_version()` and
    `zlib.ZLIB_RUNTIME_VERSION` (rev 2, P148's scope);
  - `main()`, run as `.venv/Scripts/python.exe -m scripts.build_extension_zip`.

**`problems()` reports, one line each:**
- the manifest not at the root;
- a version other than `VERSION`;
- a `FILES` entry missing;
- a file under `extension/` not in `FILES`;
- an asset that is referenced but absent: the manifest's icons, popup, options page and worker;
  `src`/`href` in each HTML file; static `import` specifiers in each JS file, followed
  recursively;
- any difference from `V1_PERMISSIONS` in `permissions`, `host_permissions`,
  `optional_permissions`, `optional_host_permissions`, `content_scripts`,
  `externally_connectable`, `web_accessible_resources`, `key`, `content_security_policy` or
  `update_url`.

- [ ] **Step 1: Write the failing tests**
  - **`test_the_manifest_is_2_0_0`:** version "2.0.0"; the description equals P148's and is at
    most 132 characters.
  - **(rev 2) `test_permissions_are_v1_0_2s` changes:** it pops `background.type`, `version`
    and `description`, then asserts that every other field equals v1.0.2's. The
    security-relevant fields stay compared in full, and the two changed fields are
    `test_the_manifest_is_2_0_0`'s.
  - **`test_the_zip_is_built_from_the_explicit_list`** (`tmp_path`):
    - the entry names equal `FILES`, with `manifest.json` first;
    - each entry's bytes equal the source file's;
    - there are no directory entries;
    - each `date_time` is (1980, 1, 1, 0, 0, 0);
    - **(rev 2)** each entry's `create_system` is 3 and its `external_attr` is
      `0o100644 << 16`.
  - **`test_the_zip_is_reproducible`** (**rev 2**):
    - copy `extension/` into two `tmp_path` trees;
    - set every file's mtime with `os.utime`: 2001-01-01 in one tree, 2031-06-15 in the other;
    - build each; the two SHA-256s are equal.

    Two builds of one unchanged tree would not detect a build that reads file times.
  - **`test_zip_checks_refuse`** (a copy of `extension/` in `tmp_path`, edited per row). Each row
    raises `ZipCheckError` naming its problem:
    - `popup.html` references `missing.js`;
    - the version "1.0.2";
    - `"tabs"` added to `permissions`;
    - a host added;
    - a `key`;
    - a stray `notes.txt`;
    - a `FILES` entry deleted.
  - **`test_every_extension_file_is_listed`:** `problems(EXTENSION) == []` on the real folder.
  - **`test_help_explains_v2`** (S5-T20's doc check, R54). `help.html`'s text contains each of:
    - the banner texts: "hours old — the daily update hasn't arrived", "The latest update failed
      its checks — showing the last good data", "source error", "This data is newer than this
      extension — update the extension", "Current health can't be confirmed for this data",
      "Source health isn't available for this data", "warning", "acknowledged", "All sources OK";
    - the labels: "Scheduled voting period: today (approx.)", "day unconfirmed", "Past expected
      period — not confirmed", "Expected between", "Possibly postponed — sources disagree",
      "Possibly cancelled — sources disagree", "Sources disagree on date", "Using source data
      from", "Unverified since";
    - the chips: "Tentative", "Subnational", "Rescheduled from";
    - the tabs: "Upcoming", "Past (formerly Results)", "All";
    - the month rule: "A month shows every election whose dates overlap it";
    - the sources: the ten names of P148, and "five months";
    - the attention section: "items across the monitored window";
    - **(2026-10-28)** the full list: "When items are omitted from the feed, the full attention
      list is in attention_full.json in the publishing run's generation artifact; retrieving it
      may require operator access, and the artifact is retained for 14 days after upload.";
    - the pins: "A pinned country also shows the places that belong to it";
    - the update: "Delete the folder's contents", "Click Reload", "Don't remove the extension".

    It contains no "Results" tab heading and no "7 international monitoring sources".
  - **`test_release_notes_cover_the_update`.** The release notes contain:
    - "Load unpacked" and "Chrome Web Store";
    - each minority alias of §6.2 (Cabo Verde, Democratic People's Republic of Korea, Lao People's
      Democratic Republic, Viet Nam, The Philippines, São Tomé e Príncipe);
    - "1 OCT";
    - "v1.0.1";
    - "Select All", "Save" (D4: removed);
    - "not migrated again";
    - "Also shows".

- [ ] **Step 2: Run them and see them fail.**

- [ ] **Step 3: Implement the manifest, `help.html`, the release notes and
  `build_extension_zip.py` as P148.**
  - The help prose outside the pinned phrases is yours. The reviewer checks it against the code.
  - The release notes cover §12.8's list, D4, P140's parent rule and its version-1 caveat, D7,
    and the evidence limits:
    - Chrome's Reload button is not driven (R49);
    - "no permission prompt" is expected, and confirmed only once a Store update lands (O4).
  - `README.md` gains "Building the extension ZIP" (the command; that it prints the
    `RELEASES.md` row and does not write it).

- [ ] **Step 4: Run the tests until they pass, then build once and keep the printed SHA-256 for
  the ledger.** `dist/` is ignored.

- [ ] **Step 5: Mutations** (`plan5b2-task-7.json`):

  | Test | Mutation |
  |---|---|
  | `test_the_manifest_is_2_0_0` | the version "2.0.0-rc" |
  | `test_the_zip_is_built_from_the_explicit_list` | `sorted(FILES)` |
  | `test_the_zip_is_built_from_the_explicit_list` (rev 2 rows) | **(rev 3)** `create_system` set to 0 instead of 3. Python's default is 0 only on Windows, so "left at the default" would survive on Linux |
  | `test_the_zip_is_reproducible` | the entry time from the file's mtime (rev 2: killed only because the two trees differ in mtime) |
  | `test_zip_checks_refuse` | the permission comparison skips `host_permissions` |
  | `test_every_extension_file_is_listed` | `places.json` removed from `FILES` |
  | `test_help_explains_v2` | "Past (formerly Results)" → "Past" |
  | `test_release_notes_cover_the_update` | the minority-alias list removed |

- [ ] **Step 6: Run the gates, then commit.**
  `git commit -m "feat(extension): v2.0.0 manifest, help, release notes and the checked ZIP build (Plan 5b-2 Task 7)"`.
  - **(2026-10-28, the controller, R62):** run `build_extension_zip.py` at the task's commit and
    record in the 5b-2 ledger the code SHA, the ZIP's SHA-256 and file count, the Python and zlib
    versions from the printed row, and the four checks' results. This is build evidence, not the
    release row, which 5c writes against the final release build.

### Task 8: The real-ZIP same-folder upgrade (S5-T16, RT-06, R49)

**Files:**
- Test: `tests/extension/test_upgrade.py`

**Interfaces:**
- Consumes: `build_extension_zip.build`; `extension_copy(dest, legacy=True)` (the v1.0.2
  fixture); `launch(playwright, profile, folder, settle_install_check=...)`, following
  `Ext.relaunch`'s pattern; `artifact_pair`, `v1_feed`.
- Produces: nothing new.

- [ ] **Step 1: Write the test `test_real_zip_same_folder_upgrade`** (`tmp_path`; about 15 s):
  1. Copy the v1.0.2 fixture into the folder `X` and launch it on the profile `P`. Route the v1
     feed.
  2. Open v1.0.2's popup, so it stores `elections_cache`.
  3. Seed `pinned_countries` `["Cabo Verde", "Moldova", "Scotland (part of the United Kingdom)",
     "Atlantis"]` and `selected_countries` `["Brazil"]`.
  4. Record the extension id and the three v1 values.
  5. Close the browser. Delete `X`'s contents (keep `X`), and extract `build()`'s ZIP into it.
  6. Relaunch on `P` and `X` with `settle_install_check=True`, then route the artifact pair and
     force a check.
  7. Assert:
     - the same id;
     - `chrome.runtime.getManifest().version` "2.0.0";
     - the three v1 values deep-equal to before;
     - `pins_migrated_v2` true, `pinned_places_v2` `["iso:CV", "iso:MD", "iso:GB-SCT"]` and
       `unresolved_pins_v2` `["Atlantis"]`;
     - the popup on November shows only Cape Verde's and Moldova's cards, with "Pinned view · 3
       countries";
     - the options page lists the three pins first, and "Atlantis" under the unresolved heading.

     Do not assert the install reason (R49).

- [ ] **Step 2: Run it.** It should pass on Tasks 1–7's code; a failure is a bug in those tasks,
  fixed in this task's commit with its own test row.

- [ ] **Step 3: Mutation** (`plan5b2-task-8.json`): the migration maps through a table without
  `"Cabo Verde"` (expected: the test fails on `pinned_places_v2`).

- [ ] **Step 4: Run the gates, then commit.**
  `git commit -m "test(extension): the real ZIP upgrades a v1.0.2 folder in place (Plan 5b-2 Task 8)"`.

- [ ] **Step 5: The controller marks the Review record verified,** from the ledger's commits, the
  passing tests and the killed mutations.

---

## Requirements for later plans

| ID | Requirement | Owner | Acceptance test | Stage |
|---|---|---|---|---|
| R53 | (unchanged) The gates job's measured time (R41) includes `playwright install --with-deps chromium` and the extension suite | Plan 5c | the branch run's step times, in the ledger | 5c |
| R62 | The `RELEASES.md` row for v2.0.0 (P148): the code SHA, `requirements*.txt` SHA-256s, the ZIP's SHA-256 and file count from `build_extension_zip`, the destination, the date and the user's approval | Plan 5c | the row, checked against a rebuild at the release commit | 5c release |
| R63 | The real action popup at 200 % zoom (P146's Known limit): one manual check on the user's Chrome, recorded in the ledger | Plan 5c | the user's note | 5c rollout |

## After Plan 5b-2

- **The branch** has Plan 5b-2's commits on top of the commit that holds this plan, with every gate
  green. Nothing is pushed or merged.
- **The Review record** shows every Plan 5b-2 row as "verified", with its commit in the SDD ledger.
- **Loaded unpacked from `extension/`,** v2.0.0 shows:
  - expandable cards with every source's date, umbrellas and provisional matches;
  - the attention section on every month;
  - only safe links;
  - pins kept as places;
  - **(rev 2)** a layout that passes the automated narrow and short popup checks
    (`test_layout_in_a_narrow_or_short_popup`, 320 × 600 and 380 × 300). That is a surrogate
    for 200 % zoom; the real popup at 200 % stays R63's check in Plan 5c, and until it passes
    nothing here claims the popup holds at 200 % zoom.

  `build_extension_zip` gives a checked, reproducible ZIP that upgrades a v1.0.2 folder in place.
- **The mutation tooling** has a preserved copy outside `.scratch/` (Step 0).
- **Next:** a whole-branch review of Plan 5b-2, then Plan 5c (rollout).
