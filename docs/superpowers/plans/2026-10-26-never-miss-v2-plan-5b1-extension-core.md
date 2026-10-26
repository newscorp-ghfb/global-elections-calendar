# Never-miss v2, Plan 5b-1: Extension core (loading, health, counting) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Revision 1 (2026-10-26).** Written against `319a292` (Plan 5a complete: 2647 tests, mypy 156
files, ruff clean, `Contracts: 3 kept, 0 broken`).
- **Plan 5b is split** (the user, D8, 2026-10-24): **5b-1** (this plan: the test harness, the logic
  core, loading, the banner, counting and tabs) and **5b-2** (cards, attention, links and text,
  pins and options, accessibility, the ZIP and help, the real-ZIP upgrade). 5b-2 is written when
  5b-1 has landed.
- **The discovery** is `C:/Users/senescalk/Desktop/handovers/elections-v2-plan5b-discovery.md`. The
  user ruled D1–D8 "all recommended" (2026-10-24). D2 (headless instead of `xvfb-run`) is an
  approved spec deviation, recorded here as P128.
- **The semantic items under "Spec corrections" need the user's approval before Task 2 starts.**
  Task 1 (the harness and Plan 5a's leftovers) depends on none of them.

**Revision 2 (2026-10-26).** Answers the red-team review
(`Downloads/never-miss-v2-plan-5b1-red-team-review-2026-10-26.md`). Every finding was checked
against this plan's text and the source at `319a292`. All four main findings were confirmed:
- **B1:** an older status could replace a newer failure. Statuses are now ordered by `attempt_at`,
  and a status counts as unchanged by its digest (P132, Task 4).
  - A `validation_failed` status links to the still-served feed (`pipeline.py:679-685`), so the
    failure's scenario is real.
- **B2:** the retry could drop the better feed it had already received. The best feed is now kept
  across both rounds (P131, Task 4).
- **B3:** a well-formed cached record holding an invalid document kept its ordering authority. A
  cached record is now validated like a download (P131, Task 4).
- **B4:** a linked legacy feed showed "All sources OK". A new banner row now reads "Source health
  isn't available for this data" (P133, Task 5).

The six smaller items are also folded in:
- the clock wording (Review Focus 1);
- timestamps and dates that name no real moment (P130, Task 3);
- isolating the patched storage API in the worker tests (Task 4);
- the storage claim, now measured with a real quota failure (probe6, Task 4);
- a request deadline and a status size limit (P131, Task 4);
- "Confirmed held" counts the label shown (P135, Task 6).

The month rule is new P138. The user ruled option B (overlap) and approved P130–P135 as revised,
both on 2026-10-26.

**Goal:** The extension loads the v2 feed and its status safely and in order, says honestly how
healthy and how fresh its data is, and counts and filters contests (children), not cards.
- v1.0.2 is proven to render the v2 feed (S1-T7).
- 5b-1 ends at a usable state: v2 loading, the banner and the v2 card list with honest labels and
  counters. Cards are flat, open no links and have no attention section yet (5b-2).

**Architecture:**
- **Pure modules** in `extension/lib/`: `dates.js`, `labels.js`, `schema.js`, `validate.js`,
  `order.js`, `worker.js`, `health.js` and `count.js`. No DOM, no `chrome.*`, no network and no clock: every time
  judgement takes `now` (milliseconds) and `today` (a civil date string) as arguments.
- **`lib/load.js`** is one check (fetch both documents, digest, validate, order, link, write). Its
  fetch, storage and clock are passed in, so tests can run it in a page with fakes.
- **`background.js`** (now an ES module worker) wires the real fetch, storage and clock into
  `load.check`, and Chrome's four events into `lib/worker.js`'s handlers (pure: when to check, when
  to ensure the alarm, when to open help). It runs one check at a time.
- **The popup** (`popup.js`, a module) reads storage, validates again, then renders:
  - `lib/legacy.js` (v1.0.2's renderer, moved) for v1 feeds and feeds that need an update;
  - `lib/render.js` (new) for v2.

  The banner and footer come from `health.js` for every format.
- **Tests** are Python: pytest-playwright drives headless Chromium with the extension loaded. Pure
  modules are imported into an extension test page and called with `page.evaluate` (D1). There is
  no JS toolchain.

**Tech Stack:**
- Chrome MV3, ES modules, no build step and no dependencies;
- Python 3.14.1, pytest 9, `playwright==1.64.0` and `pytest-playwright==0.10.0` (already locked);
- Chromium build 1248 (Chrome for Testing 156), headless with `channel="chromium"`.

No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-16-never-miss-v2-design.md`.
- Read these sections first:
  - §5.3–§5.8 (the records the extension reads);
  - all of §12;
  - §13.3 (the S1-T7, S5, V2-T03 and NM-T03 rows) and §13.4;
  - §15 step 7 ("What existing clients do");
  - Appendix A (I2, I6, I7, I11, I13).
- Where this plan and the spec differ, the plan wins *only* for the items under "Spec corrections".
- The discovery doc (above) maps §12 to the v1.0.2 code, row by row. Its Step 1 is the tooling proof.

## "As built" errata (read first)

**Plan 5a** (built at `e52fbb1`; record: `handovers/elections-v2-plan5a-sdd-ledger.md`):
- **The fixture artifact** (`tests/support/artifact._built("published")`, one nine-source offline run
  at `NOW` = 2026-10-19T12:00:00Z, about 3.4 s) holds a linked pair. Measured by
  `.scratch/plan5b1/feed_stats.py`:
  - `elections.json` is 377,411 bytes, and `status.json` is 3,256 bytes with `serving_feed_sha256`
    equal to the feed's SHA-256.
  - Both carry `generated_at` = `published_at` = 2026-10-19T12:00:00Z. `data_as_of` is
    2026-10-16T14:39:00Z, 69 h older.
  - The window is `2026-09`..`2027-01`, `current_month` `2026-10`, `attention_truncated` 0, with 157
    attention items and 31 undated listings.
  - **Status** `published`, severity `warning`, with 7 warning reasons (Wikipedia 2, NDI 1, A-WEB 2,
    EISA 1, IPU 1). No error, nothing acknowledged, nothing on a fallback.
  - **Cards and children:**

    | Month | Cards | Children | Aggregate |
    |---|---|---|---|
    | 2026-09 | 22 | 27 | 10 |
    | 2026-10 | 30 | 58 | 11 |
    | 2026-11 | 28 | 89 | 13 |
    | 2026-12 | 15 | 21 | 2 |
    | 2027-01 | 5 | 7 | 0 |

    The largest cards are United States 2026-11-03 (59 children) and Brazil 2026-10-04 (18).
  - **Card fields:** all children of a card share the card's date, precision, meaning, date status,
    level and status (they are the card key, `merge/cards.py:_card_key`). A child has no date
    fields of its own.
  - **Month-precision cards (five):**
    - Cameroon 2026-12, meaning `unknown`;
    - IPU expected windows (`tentative`): Libya, Madagascar and Somalia in 2026-12, Cameroon in
      2027-01.

    Every other card has day precision and the meaning `voting_period`.
  - **Day ranges:**
    - Russia 18–20 Sep and Italy 27–28 Sep;
    - Czech Republic 9–10 Oct (twice) and 16–17 Oct;
    - Fiji 24 Dec 2026 – 6 Feb 2027.
  - **Confirmations and conflicts:**
    - 13 children are `occurrence_confirmed`, each with a selected ElectionGuide `held` claim.
    - 3 children have `date_conflict`: Cape Verde 2026-11-15, and two for Nigeria 2027-01-16.
    - None has `status_conflict`, `provisional_date`, a fallback source or a provisional source.
- **Recovery bytes** for NM-T03: `elections_calendar.ci.recovery.republished_feed(original, *,
  now)` and `feed.status_doc(..., outcome="republished", serving=feed)`, as `recovery.republish`
  builds them.
- **The gates job** (`.github/workflows/update-elections.yml`) already runs
  `.venv/bin/python -m playwright install chromium`. Its `pytest -q` runs with `CI=true`, and under
  `CI=true` a skipped test fails the session (`tests/conftest.py`, P126).
  `test_gates_job_runs_the_canonical_gates` pins both steps.
- **R38:** `tests/workflow/test_workflow.py::test_served_check_reads_the_extension_url` reads
  `const DATA_URL = "..."` from `extension/background.js` with a regular expression.
- **The Python validator's `_ecma`** reads a final unescaped `$` as `\Z` (Plan 5a F1). JS `RegExp`
  without the `m` flag already reads `$` as the end of input.

**v1.0.2** (the `extension/` folder at `319a292`, byte-identical to `ff30417`):
- **Files:** `manifest.json` (version 1.0.2, permissions `storage` and `alarms`, host
  `https://raw.githubusercontent.com/*`), `background.js`, `popup.html`, `popup.js`, `styles.css`,
  `options.html`, `options.js`, `options.css`, `help.html` and three icons. The total is
  95,447 bytes.
- **Storage keys:** `elections_cache` (`{ts, data}`), `pinned_countries` (display names) and
  `selected_countries` (never read).
- **Messages:** the popup sends `{type: "FETCH_DATA"}`, and the worker replies
  `{ok, data | error}`.
- **The worker:**
  - creates the alarm `elections-refresh` (60 min) in `onInstalled` only;
  - opens `help.html` on `install`;
  - fetches `elections.json` with `resp.json()`.
- **The popup:**
  - **Tabs:** `#tabUpcoming` (`data-filter="upcoming"`, highlighted), `#tabResults` (`held`,
    labelled "Results") and `#tabAll` (`all`). `popup.js:42` starts on `all`, so the highlighted tab
    does not match the list (§12.5's bug).
  - **The stats and the footer:** `#statTotal` and `#statHeld` count cards, and the footer says
    "Updated …".
  - Cards are built with `innerHTML` and `escHtml`, and any feed link is opened as it is.

**Measured this session** (`.scratch/pw5b/probe3.py`, `probe4.py`; results `probe3.txt`,
`probe4.txt`):
- **Imports and the worker:**
  - an extension page can `import()` a module from `page.evaluate`;
  - a worker declared `"type": "module"` loads its static imports;
  - `context.browser` is set for a persistent context, so a browser CDP session works.
- **Stopping the worker (D5): `Target.closeTarget` on the worker's `service_worker` target stops
  it.**
  - The target disappears from `Target.getTargets`.
  - The next `chrome.runtime.sendMessage` boots a fresh worker: a boot counter in storage went from
    1 to 2.
  - Playwright's `Worker` `close` event does **not** fire, so tests detect a stop through
    `Target.getTargets`.
  - `ServiceWorker.stopAllWorkers` from a page session does not stop the extension's worker.
- **Reloading and relaunching:**
  - **`chrome.runtime.reload()` loses the extension** under `--load-extension`: no extension page
    loaded again within 10 s.
  - **A relaunch on the same profile and folder keeps the extension ID, its storage and its alarm.**
- **The extension's own fetch:** `context.route` on `https://raw.githubusercontent.com/**`
  intercepts the worker's fetch. With `--host-resolver-rules=MAP * ~NOTFOUND`, any request that is
  not routed fails.
- **The test clock:** `context.clock.set_fixed_time` fixes the pages' `Date` but not the worker's
  (discovery Step 1).
- **Alarms and restarts** (`.scratch/pw5b/probe5.py` → `probe5.txt`):
  - **A one-shot alarm 200 ms ahead fires late.** Of three, one fired after about 10 s, one later,
    and one not within 10 s. Tests therefore never wait for an alarm.
  - **A relaunch fires `runtime.onInstalled` with reason `install`, not `onStartup`.** Storage is
    kept. So under `--load-extension`, `onStartup` cannot be exercised, and a relaunch looks like a
    fresh install (it opens `help.html` again).
- **The fixture facts the tests pin** (`.scratch/plan5b1/verify_plan.py` → `verify_plan.txt`):
  - **The v1 feed** (`tests/fixtures/feed/2026-10-16-ff30417.json`) has the four legacy keys only,
    and `generated_at` 2026-10-16T00:02:31Z. It holds 9 / 27 / 14 cards in Sep / Oct / Nov, and 15
    of October's 27 are `Held`.
  - **`source_health` order:** electionguide, osce, wikipedia, ndi, aweb, eisa, ipu, carter, eeas.
    `name`s are ElectionGuide, OSCE/ODIHR, Wikipedia, NDI, A-WEB, EISA, IPU, Carter Center and
    EEAS.
    - The first warning is Wikipedia's `unparsed_relevant` (stage `parse`, year and page null).
    - EISA also has an info reason, `not_published_yet` (year 2027).
    - `run.reasons` is empty.
  - **The 19 Oct card** is "Canada", type "Alberta: Referendum": one child, level `subnational`,
    `date_status` `unknown`, status `Upcoming`.
  - **The one "county elections" child** of the 59-child US card is Tennessee's, with
    `aggregate: true`.
  - **The schemas:**
    - Keywords used: `$defs`, `$id`, `$ref`, `$schema`, `additionalProperties` (`false` or a
      schema), `anyOf`, `const`, `enum`, `items`, `maxItems`, `maxLength`, `minItems`, `minimum`,
      `pattern`, `properties`, `propertyNames`, `required`, `title`, `type`.
    - Every required field has a type.
    - The only object schemas with no instance in the fixture pair are the feed's
      `#/$defs/acknowledged` and the status's `acknowledged` items.
    - **Time and date shapes:** the feed's `$defs` include `timestamp` (the status-v1 pattern) and
      `date` (`^[0-9]{4}-[0-9]{2}-[0-9]{2}$`); the status's include `timestamp`. A pattern cannot
      say whether the value names a real moment or day.
- **A real storage quota failure** (`.scratch/pw5b/probe6.py` → `probe6.txt`):
  - `chrome.storage.local.QUOTA_BYTES` is 10,485,760.
  - With storage filled to 10,185,792 bytes, a two-key `set` that does not fit rejects with
    `Resource::kQuotaBytes quota exceeded`. **It writes neither key**, whichever key comes first.
  - Chrome documents no transaction guarantee, so this is a measurement, not a promise.
- **Month buckets under an "overlap" rule** (`.scratch/plan5b1/overlap_view.py` →
  `overlap_view.txt`): only one fixture card overlaps a later window month than its bucket. That is
  Fiji, 24 Dec 2026 – 6 Feb 2027 (day precision, `voting_period`, 1 child), bucketed in December.
  Under P138 option B, January would show 6 cards and 8 records instead of 5 and 7. Every other
  month's counts stay the same.

**The rules prototype** (`.scratch/plan5b1/proto_view.py` → `proto_view.txt`). It encodes P134's
label kinds and P135's tabs in Python and gives the values the JS must reproduce on the fixture at
today = 2026-10-19:

| Month | Level | All: cards / records / groupings / held | Upcoming | Past |
|---|---|---|---|---|
| 2026-09 | all | 22 / 27 / 10 / 5 | 0 / 0 / 0 / 0 | 22 / 27 / 10 / 5 |
| 2026-09 | national | 15 / 18 / 6 / 5 | — | — |
| 2026-09 | subnational | 12 / 16 / 10 / 0 | — | — |
| 2026-10 | all | 30 / 58 / 11 / 8 | 11 / 15 / 7 / 0 | 19 / 43 / 4 / 8 |
| 2026-10 | national | 15 / 19 / 0 / 8 | 5 / 5 / 0 / 0 | 10 / 14 / 0 / 8 |
| 2026-10 | subnational | 15 / 39 / 11 / 0 | 6 / 10 / 7 / 0 | 9 / 29 / 4 / 0 |
| 2026-11 | all | 28 / 89 / 13 / 0 | 28 / 89 / 13 / 0 | 0 |

- **Label kinds:**
  - Sep: held 5, past 22;
  - Oct: held 8, past 35, scheduled 14, today 1 (Canada's referendum on 2026-10-19);
  - Nov: scheduled 89;
  - Dec: day_unconfirmed 1, expected 3, scheduled 17;
  - Jan: expected 1, scheduled 6.
- **No fixture card mixes held and past children.** The "2 of 3 confirmed held" summary is tested
  on an edited card.
- **Search:** "county elections" matches exactly one child of the 59-child US card. The card's
  `type` is cut ("(+51 more)"), so search never reads `type`.

## Plan series

1. **Foundations** (done, `8632297`).
2. **Sources:** 2a (done, `f5f3a1c`), 2b (done, `94ac45a`), 2c (done, `fa4d0a2`).
3. **Merge** (done, `6ba511b`).
4. **Health, snapshots, feed and publishing** (done, `2927bb0`).
5. **Workflow, extension and rollout:**
   - **5a:** run and publish (done, `319a292`);
   - **5b-1: the extension core (this plan);**
   - **5b-2:** cards, attention, links and text, pins and options, accessibility, the ZIP and help,
     the real-ZIP upgrade;
   - **5c:** rollout and housekeeping.

**Not in this plan (5b-2's):**
- children rendered on expand, umbrellas, chips beyond Tentative and Subnational, and source
  entries;
- the attention and undated section;
- links (the allowlist) and the legacy renderer's `innerHTML`;
- pin migration, the `places.json` table (D3) and the options page (D4);
- `aria-*` beyond what this plan names;
- the R26 popup measurement (D6);
- the manifest version 2.0.0, `help.html`, the ZIP, `RELEASES.md` and the real-ZIP upgrade (D7);
- the matrix of renderers and feeds (S5-T17), beyond this plan's dispatch rows.

**Also not in this plan:**
- **Nothing leaves this machine.** No push, no workflow run on GitHub, no Store upload.
- Nothing is merged.

## Global Constraints

Plans 1–5a's Global Constraints still hold for Python:
- **Code:**
  - the layering (`Contracts: 3 kept, 0 broken`);
  - no network in tests;
  - `[0-9]`, never `\d`, in new regexes;
  - time is passed in, and a naive datetime raises.
- **Process:**
  - the gates, each in its own shell call;
  - one mutation per new test;
  - `.scratch/` for scratch files.
- **Git:**
  - work on `feat/never-miss-v2` only;
  - check `git rev-parse --abbrev-ref HEAD` in its own call before every commit;
  - end each commit with the `Co-Authored-By:` trailer of the model that wrote it.

**This plan adds:**
- **Pure modules stay pure.** `dates.js`, `labels.js`, `schema.js`, `validate.js`, `order.js`,
  `worker.js`, `health.js` and `count.js` contain none of these tokens: `chrome.`, `document`, `window`,
  `fetch(`, `Date.now`, `localStorage`, `innerHTML`. Only `dates.js` contains `new Date(`.
  `test_pure_modules_use_no_browser_api` (Task 2, extended in Tasks 3–6) checks it.
- **Civil dates are strings**, `YYYY-MM-DD`, compared as strings once checked by `isCivilDate`. They
  are never parsed by `Date`. `Date` is used only for instants (feed timestamps, `now`) and for the
  local components of an instant (`dates.localToday`, `dates.stamp`).
- **Feed text is text.** New code (`render.js`, `health.js`'s output, the popup's banner, footer and
  panel) sets text through `textContent` only. It never uses `innerHTML`, `insertAdjacentHTML`,
  `outerHTML` or `document.write`. `lib/legacy.js` keeps v1.0.2's `escHtml` and `innerHTML` until
  5b-2 Task 9 (R52).
- **No defaults for fields Plan 4 always writes** (R35). The popup renders only a document that
  `validate.feedFormat` accepted. It reads the fields the schema requires as they are, never as
  `field || fallback`.
- **Permissions do not change** (§12.1): `storage` and `alarms`, host
  `https://raw.githubusercontent.com/*`, no `key`, no `content_security_policy`.
  `test_permissions_are_v1_0_2s` (Task 4) checks this.
- **The feed URL stays** `const DATA_URL = "https://raw.githubusercontent.com/newscorp-ghfb/global-elections-calendar/main/elections.json";`
  in `extension/background.js` (R38). The status URL is `new URL("status.json", DATA_URL).href`.
- **The v1.0.2 keys stay untouched:** `elections_cache`, `pinned_countries` and
  `selected_countries` are never written or removed. This keeps a rollback to v1.0.2 working.
- **Copy is verbatim.** Every user-visible string in this plan is copied exactly. That includes
  the en dash `–` (U+2013) in ranges, the em dash `—` (U+2014) in labels and the middle dot `·`
  (U+00B7).
- **Tests are hermetic and deterministic:**
  - Every browser context launches with `--host-resolver-rules=MAP * ~NOTFOUND`,
    `timezone_id="UTC"` (unless a test names another zone) and `locale="en-GB"`.
  - The raw host is routed to per-test bytes.
  - Page tests fix the clock with `context.clock.set_fixed_time`.
  - Worker-side code is tested either through `load.check` with fakes and an explicit `now`, or with
    stored times derived from the real clock (never fixed dates the real clock could overtake).
- **Run pytest with `GIT_ALLOW_PROTOCOL=file`.** This worktree's `origin` is the live feed
  repository. Never run `ci publish`, `ci adopt` or `scripts.republish` against the worktree.

## Review Focus

These are the five inputs most likely to hurt a reader that the spec implies but no step spells
out. Each is pinned by the named tests, in the task that owns the code.

1. **A wrong clock on the reader's computer** (hours or days off, either way).
   - **Ages are measured by this computer's clock.** With local time alone, a fast clock cannot be
     told from old data: a clock 30 h fast makes 7-hour-old data look stale. The banner's text
     says "Data is N hours old", which is that measurement.
   - **A slow clock is visible:** a `generated_at` more than 10 minutes ahead of the clock is
     marked "(ahead of this computer's clock)" and is never called stale.
   - Labels use the computer's own civil date.
   - **A wrong clock cannot freeze the cache:** a cached publication key counts only while it is
     not more than one day ahead of `now`. This compares the key with `now + 1 day` on each check;
     it is not a timer.

   Pinned by `test_freshness_thresholds_and_clock_skew` (Task 5) and `test_rollback_ordering`
   (Task 4).
2. **Time zones far from UTC, and DST changes.** At UTC+14 and UTC−11 the local "today" is a
   different date from UTC's. On 25 Oct 2026, London's clock shows 01:30 twice.
   - A civil date's badge never shifts.
   - "Today" follows the local date.

   Pinned by `test_local_today_across_time_zones_and_dst` (Task 2).
3. **A feed and a status from different publications or attempts**, as a CDN can serve them:
   - a stale status beside a new feed, or a new status beside a stale feed;
   - an older `published` status after a newer `validation_failed` one, both about the same feed;
   - a retry that brings back an older feed, or fails;
   - a 404, invalid, oversized or never-answered status;
   - the republication's status beside v1's later feed.

   **What happens:**
   - The pair is refetched once.
   - The newest valid feed seen in the check is kept.
   - The newest valid status that describes it is kept. A later failure is never erased by an
     older success.
   - The banner says when health can't be confirmed.

   Pinned by `test_check_links_and_refetches_once`, `test_a_retry_keeps_the_best_feed` and
   `test_status_selection` (Task 4), and by `test_a_newer_failure_is_not_erased` and
   `test_rollback_v1_feed_shows_the_mismatch_banner` (Task 5).
4. **A bad or foreign cache:**
   - a `elections_cache_v2` value that is a string or holds a number;
   - a well-formed record whose document is invalid, or whose `format` or `order_key` does not
     match its document;
   - v1.0.2's `elections_cache` beside it;
   - a quota error on write;
   - a worker killed in the middle of a check.

   **What happens:**
   - The popup never crashes.
   - An invalid record counts as no cache, and the next valid download replaces it.
   - A rejected write leaves the previous feed and status pair as it was. This is tested with a
     fake rejection and with a real quota failure (probe6). A kill exactly at the write is not
     tested (Known limits).

   Pinned by `test_a_corrupt_cache_is_ignored`, `test_cached_records_are_validated`,
   `test_a_failed_write_keeps_the_previous_pair`, `test_a_real_quota_failure_keeps_the_previous_pair`
   and `test_a_check_cut_short_leaves_the_previous_pair` (Task 4).
5. **Hostile text in the new v2 paths:** a reason text, a country or a card type holding
   `<img src=x onerror=…>`. It shows literally, and no element is created. Pinned by
   `test_health_text_is_inserted_as_text` (Task 5) and `test_v2_card_text_is_inserted_as_text`
   (Task 6).

**Known limits, by design.** Each is visible:
- **The worker's clock is real.** Integration tests seed stored times relative to the real clock.
  The time rules themselves are tested through `load.check`, `order.accepts` and `health.*` with an
  explicit `now`.
- **No alarm is waited for.** A one-shot alarm fires 10 s or more late (probe5). The handlers'
  logic lives in `lib/worker.js` and is tested with fakes; `background.js` only wires the four
  Chrome events to it, and a static test checks the wiring.
- **`onStartup` cannot be exercised.** Under `--load-extension`, a relaunch fires `onInstalled`
  (`install`) instead (probe5). The startup handler is tested through `lib/worker.js`, and its
  registration statically.
- **Status order trusts the producer's `attempt_at`.** A status whose `attempt_at` names no real
  moment is invalid (P130). Two different statuses with the same `attempt_at` are resolved by
  P132's tie rule, not by any truth about which came later.
- **Storage writes are not transactions by contract.** The pair is written in one `set`. A real
  quota rejection wrote neither key (probe6). A worker killed at the write boundary, or a browser
  crash during it, is not tested, so the plan claims no more than this.
- **Acknowledgements are matched one-to-one on (code, stage, year, page).** The feed's reasons and
  acknowledgements carry no `since` (§5.6). Two reasons with the same key, where only one is
  acknowledged, would show both as acknowledged. No producer path makes such a pair today (P91
  keeps one reason per key).

## Spec corrections

These were found while measuring the fixtures and the browser, and while reconciling the spec with
the code at `319a292`.
- **Semantic decisions** change what a reader sees or what the client accepts: P130–P135 and P138.
  **The user approved P130–P135 as revised and ruled P138 option B on 2026-10-26.**
- **P128 is D2,** approved on 2026-10-24.
- **The other corrections** (P129, P136, P137) refine tooling and interfaces.

| ID | Spec says | This plan does | Why / alternative |
|---|---|---|---|
| P128 (D2, approved; R39) | §13.4: "Chromium persistent context … (`xvfb-run` on Linux CI)". R39: "the gates job runs the extension suite under `xvfb-run`" | **Headless Chromium** (`channel="chromium"`, `headless=True`) on every platform. **The gates job's existing pytest step runs `tests/extension/`** with `CI=true`, so a skip fails (P126). **The install step becomes `.venv/bin/python -m playwright install --with-deps chromium`**, so the runner gets Chromium's system libraries (apt, through `sudo`) | Proven in discovery Step 1: the full Chromium in new headless mode loads extensions; the headless shell does not. `--with-deps` is Playwright's documented CI install. It adds about 30–60 s, measured in 5c's first branch run (R53). Alternative: `xvfb-run` with headed Chromium, unproven |
| P129 (interfaces; §13.4) | §13.4: "The legacy matrix uses the real v1.0.2 files from git (`ff30417:extension/`)" | **The v1.0.2 files are a committed fixture copy**, `tests/fixtures/v1/extension/` (95,447 bytes, 12 files). They are copied byte for byte with `git cat-file blob ff30417:extension/<path>`, and every file's SHA-256 is pinned in `PROVENANCE.md` and in `test_v1_extension_fixture_is_v1_0_2` | The gates job checks out one commit (`actions/checkout` depth 1), so `ff30417` is not there in CI. Plan 5a did the same for v1's workflow (`tests/fixtures/v1/update-elections.yml`). Alternative: `fetch-depth: 0` in the gates job, which downloads the whole history on every run |
| P130 (semantic; §12.1 validation) | §12.1: "both documents are checked for required fields and types"; 2 → v2, no version + `months` → legacy, unknown/malformed → legacy fields + "update the extension" | <ul><li>**The extension ships byte copies of the two schema files** (`extension/schemas/`, checked equal to `schemas/`). It validates them with `lib/schema.js`, a validator for exactly the keywords the files use.</li><li>**Enforced keywords:** `type`, `properties`, `required`, `items`, `$ref`, `enum`, `const`, `pattern` (ECMA, `$` = the end of input), `anyOf`, `additionalProperties` when it is a schema, `propertyNames`, `minimum`, `minItems`.</li><li>**Ignored keywords, for forward compatibility:** `additionalProperties: false`, `maxLength` and `maxItems`, plus the annotations `$schema`, `$id`, `title` and `description`. A newer producer may add a field or a longer text without breaking older clients.</li><li>**Four formats** (`validate.feedFormat`):<ul><li>`v2`: `schema_version` is the number 2 and the schema passes;</li><li>`legacy`: no `schema_version` key, and the legacy checks pass;</li><li>`update_needed`: a `schema_version` key that is not 2, or a 2 that fails the schema, while the legacy checks pass;</li><li>`invalid`: anything else, which is never stored or rendered.</li></ul></li><li>**The legacy checks** are `validate.legacy_feed_problems`'s, without its three producer-only rules: unexpected top-level keys, timestamps ahead of the wall clock, and the size cap.</li><li>**Real moments and days** (review item):<ul><li>every value that reaches `$defs/timestamp` must name a real UTC moment (`dates.parseTimestamp`);</li><li>every value that reaches the feed's `$defs/date` must name a real day (`dates.isCivilDate`).</li></ul>A failure is a schema problem, so a v2 document with "2026-02-30T00:00:00Z" is not `v2`. The renderers and the banner therefore never meet a timestamp they cannot read.</li><li>**The client refuses a feed over 4,000,000 bytes, and a status over 1,000,000 bytes**, before parsing them. The status is 3,256 bytes today.</li></ul> | The schema files are the contract, so validating them directly keeps "every required field is checked" true by construction. Two tests guard it: one that deletes every required field in turn, and one that checks every keyword. The copies cost 37 KB in the package, compressed in the ZIP. The size limit is twice the producer's 2,000,000-byte cap, which leaves room under `chrome.storage.local`'s 10 MB. Alternatives: hand-written field tables with a sync test against the schema; enforce `additionalProperties: false`, so that any new producer field breaks every installed v2 client |
| P131 (semantic; §12.1 loading) | §12.1: fetch both; refresh hourly, in `onInstalled` and `onStartup`, "checked again when the popup opens"; on a mismatch "refetch once"; a failed write keeps the previous cache | <ul><li>**One check** is `load.check` (Task 4's algorithm). It refetches **both** documents once when the status it received does not describe the best feed so far.</li><li>**The best feed is kept across both rounds** (B2). It starts as the cached record, and each valid download replaces it only when P132 accepts it. A failed or older second round never discards the first round's feed.</li><li>**The status is chosen by P132's status order** among the valid cached and received ones (B1). The received statuses are always processed, also when the feed is unchanged.</li><li>**It writes the final selection in one `chrome.storage.local.set` call:** the feed record and the status record when they changed, and always the check record. A rejected write leaves every key as it was (measured for a real quota failure, probe6; Known limits).</li><li>**`changed`** is true only when the feed or status record changes. A record is unchanged when its digest is (byte equality, never object identity). Refreshing the check record is not a change.</li><li>**A deadline:** each request that has had no full response within 30 s fails. For the feed the error is "no response in time"; for the status the result is "no status". A check therefore always ends, and the next one can run.</li><li>**One check runs at a time** in the worker: a second request joins the running one. A failed or timed-out check releases it.</li><li>**When it runs:**<ul><li>on install;</li><li>on startup;</li><li>on the alarm, which then makes sure the hourly alarm exists;</li><li>on popup open, when the last successful check is 30 minutes old or more, or there is none, or its time is in the future or unreadable;</li><li>on Refresh and Retry, always.</li></ul></li><li>**The popup always makes sure the alarm exists.**</li><li>**A cached record counts only if it is valid** (B3). Its document passes `feedFormat`, and its `format` and `order_key` equal what its document gives. Its `sha256` is 64 lowercase hex characters, and its `received_at` is a finite number. The status record's document passes `statusProblems`, and its `sha256` is hex. Anything else counts as no cache. The stored digest is trusted as the digest of the bytes once received; it cannot be recomputed from parsed JSON.</li><li>**Error texts** are verbatim (Task 4).</li></ul> | A CDN can serve the two files from different publications, and either one can be the stale one. Keeping the best feed and the newest applicable status means no round can make the result worse. 30 minutes is v1.0.2's cache TTL. Alternatives: refetch the status only; check on every popup open, which costs two requests each time the popup opens |
| P132 (semantic; §12.1 ordering) | §12.1: the key is `published_at` if valid, else `generated_at`; equal = no change; "a cached key more than 1 day ahead of the client clock stops counting" | <ul><li>**Keys are compared as instants** (`dates.parseTimestamp`). A key is valid when it is a whole status-v1 timestamp naming a real moment.</li><li>**A missing or invalid key never replaces a cached feed.** After validation, only a v2 time that fits the pattern but names no real moment (30 February) is invalid. With nothing cached, any validated feed is accepted.</li><li>**"More than 1 day ahead" means strictly greater** than `now + 86,400,000` ms.</li><li>**An equal key is the same publication:** nothing is written and `changed` is false.</li><li>**Statuses have their own order** (`order.pickStatus`, B1). Feed publications and attempts are different things: a `validation_failed` attempt does not change the feed.<ol><li>The candidates are the valid cached status and each valid status received in this check.</li><li>If any candidate describes the feed being kept, only those count.</li><li>Among the ones that count, the latest `attempt_at` wins.</li><li>On equal `attempt_at`: a candidate with the same digest as the cached one is the cached one. Otherwise a `validation_failed` outcome wins over any other, so an ambiguous success never erases a failure. Then the cached one wins (no flapping).</li></ol></li></ul> | It pins the two boundaries the spec leaves open, the key's validity and the exact day, and it orders attempts, which the spec does not. Alternatives: compare the strings, which differs only for fractional seconds; keep the incoming status whenever both describe the feed (revision 1), which let a stale `published` status erase a newer failure |
| P133 (semantic; §12.2) | §12.2: five rows in order (stale, `validation_failed`, source error, warnings, acknowledged); the footer's "Data as of", the `data_as_of` gap over 24 h, and "Checked"; "uncertain or future timestamps are shown as uncertain" | <ul><li>**Nine conditions, worst first:**<ol><li>stale (red);</li><li>latest attempt `validation_failed` (red);</li><li>an unacknowledged source or run error (red);</li><li>`update_needed` (amber);</li><li>the status does not describe this feed (amber);</li><li>a `legacy` feed, whose source health is unknown even when the status describes it (amber, B4);</li><li>an unacknowledged warning (amber);</li><li>an acknowledged issue (grey);</li><li>none ("All sources OK"), which is reachable only for a `v2` feed.</li></ol></li><li>**Rows 3, 7 and 8 read the shown `v2` feed's** `source_health[].reasons` and `run.reasons`. They never apply to `legacy` or `update_needed` data. Info reasons are ignored. A reason counts as acknowledged when an `acknowledged[]` entry of the same source has its code, stage, year and page, matched one-to-one.</li><li>**Row 2 reads the status, and only when the status describes this feed.**</li><li>**Stale** means `now − generated_at` is strictly more than 36 h.</li><li>**A `generated_at` more than 10 minutes ahead of `now` is "ahead of this computer's clock"** in the footer, and it can never be stale.</li><li>**"Checked"** is the last successful check, followed by the last failure when that came later.</li><li>**All texts are verbatim** (Task 5).</li></ul> | The spec's table has no row for a feed that needs an update or a status that does not match, yet §12.1 asks for both banners. A matching digest says which bytes a status describes; it does not supply the source health a legacy feed lacks (row 6). The banner describes the data being shown, which the feed's own `source_health` describes. 10 minutes is the producer's `MAX_AHEAD`. Alternatives: read rows 3–7 from the status (it describes the latest attempt, which a `validation_failed` makes different from the data shown); show the mismatch only in the panel |
| P134 (semantic; §12.3) | §12.3's table of labels, by example | <ul><li>**Label kinds and their order** (`labels.childLabel`, Task 2), first match wins:<ol><li>`cancelled`, `postponed`: the card's resolved status;</li><li>`possibly_cancelled` / `possibly_postponed`: `status_conflict`, cancelled when a source of the child claims `cancelled`;</li><li>`disputed`;</li><li>`held`: `occurrence_confirmed`;</li><li>the date rules: `past`, `past_expected`, `expected`, `today`, `scheduled`, `day_unconfirmed`.</li></ol></li><li>**Texts for months, years and expected windows** (Task 2's table).</li><li>**The card summary:** a conflict first, with "· k of n"; "Past · k of n confirmed held" for a mix of held and past; otherwise the shared label.</li><li>**Notes:**<ul><li>"Sources disagree on date" for `date_conflict` or `provisional_date: moved`;</li><li>the `less_precise` note;</li><li>"Using source data from" or "Unverified since" for a selected fallback source, after strictly more than 7 days;</li><li>"Confirmed by source data from" when every `held` source is a fallback;</li><li>the provisional source note.</li></ul></li><li>**Chips:** "Tentative" (a tentative date that has not passed) and "Subnational".</li></ul> | The spec gives examples ("October — day unconfirmed", "Expected between 2 Nov and 31 Jan"), not the full set. A card status of `Held` is never shown as "Held" without `occurrence_confirmed` (D2, R25). Alternative: show legacy statuses as they are, as v1.0.2 does |
| P135 (semantic; §12.5) | §12.5: one pipeline; tabs Upcoming / Past / All with their members; the highlighted tab matches the list | <ul><li>**Tab membership follows the label kind:**<ul><li>Upcoming: `scheduled`, `today`, `day_unconfirmed`, `expected`, `possibly_postponed`, `possibly_cancelled` and `postponed`, plus `disputed` while its end date has not passed;</li><li>Past: `held`, `past` and `past_expected`, plus `disputed` once its end date has passed;</li><li>`cancelled` appears under All only.</li></ul></li><li>**The popup opens on All**, highlighted, which is the list v1.0.2 actually showed.</li><li>**Search** reads the country, the child's `office_label` and `jurisdiction`, its source names, and its label text, never the card's cut `type`.</li><li>**A grouping** is a child with `aggregate: true`.</li><li>**The stats** read "Election records" (distinct `child_id`s) and "Confirmed held". "Confirmed held" counts the kept children whose label kind is `held`, so it always agrees with the labels. A confirmed child whose label is a conflict, a cancellation, a postponement or a dispute is not counted.</li><li>**Until 5b-2:** v2 cards open no link (R47), and the pin filter matches v1's `pinned_countries` to the card's `country` (R48).</li></ul> | The spec lists the tabs' members by label, so the kinds make them exact. It does not place Cancelled or Disputed. Opening on All keeps what readers see today, now with the right tab highlighted. Alternatives: open on Upcoming (past elections of this month then need a tab change); put Cancelled in Upcoming |
| P136 (interfaces; D5, settled by measurement) | D5: spike a worker stop, with a `chrome.runtime.reload()` fallback | **The worker stop is CDP `Target.closeTarget`** on the extension's `service_worker` target, through `context.browser.new_browser_cdp_session()`. A stop is confirmed by the target leaving `Target.getTargets`. **There is no reload fallback:** `chrome.runtime.reload()` loses the extension under `--load-extension` (probe4). So 5b-2's same-folder upgrade relaunches the browser on the same profile, and that relaunch reports `install`, not `update` (probe5; R49) | Measured (probe4): the stop works, and a message wakes a fresh worker. Alternative: none needed |
| P137 (interfaces) | §12.8: version 2.0.0 | **`manifest.json` gains only `"type": "module"`** under `background` in this plan. The version stays `1.0.2` until 5b-2's release task bumps it to `2.0.0`, together with the description, `help.html` and the ZIP | Version and help change together, once. Alternative: bump now, which would show 2.0.0 in a build with no attention section |
| P138 (semantic; §12.5 step 1; **ruled: option B**, the user, 2026-10-26) | §12.5: "filter children (month bucket, …)"; §5.1: each card is in exactly one bucket, its start month (or the first window month it overlaps) | <ul><li>**Option A, as the spec says:** a month shows the cards of its bucket only. Fiji's 24 Dec – 6 Feb voting period shows in December, with a "24–6 / DEC–FEB" badge, and not in January.</li><li>**Option B, overlap** (the review's preference): a month shows every card whose interval overlaps it. Filters run on those cards, and `child_id`s are counted once within the view. The feed is unchanged, and so are the labels (an expected window stays "Expected …"). Fiji then also shows in January: 6 cards and 8 records instead of 5 and 7. No other fixture count changes (errata).</li></ul>**Ruled B.** `test_month_rule` pins it with Fiji and a synthetic December–February case. | B is the "never miss" reading: a reader browsing January sees a vote still open in January. A follows the spec and v1.0.2's one-card-one-month list. Either way the choice becomes explicit and tested |

## Review record

**Status:** "planned" becomes "verified" only when the SDD ledger records the task's commit, with
the named test passing and its mutation killed.

| ID | Kind | Ruling | Task · test | Status |
|---|---|---|---|---|
| Plan 5a R1 | Re-review minor | An expected entry missing `place`, `office` or `round` is one material line, and the rest are still compared | T1 `test_a_malformed_expected_entry_is_a_material_line_and_does_not_skip_the_rest` (new rows) | planned |
| Plan 5a R2, R3 and the `_write_rejected_pages` nit | Re-review minors | Wording only | T1 (the files' text) | planned |
| Plan 5a R4 | Re-review minor | An unreadable parent of `--out` is a reason, never a traceback | T1 `test_an_unreadable_report_parent_is_a_reason` | planned |
| Plan 5a R5 | Re-review minor | `_ecma` reads an even run of backslashes before the final `$` as an anchor | T1 `test_ecma_reads_an_escaped_backslash_before_the_end` | planned |
| R39 (Plan 5a) | Requirement, amended by P128 | The gates job runs the extension suite, headless, with `CI=true` and no skips | T1 `test_gates_job_runs_the_canonical_gates`, `test_gates_job_runs_the_extension_suite` | planned |
| P129 | Interfaces | The v1.0.2 fixture copy | T1 `test_v1_extension_fixture_is_v1_0_2` | planned |
| P136 | Interfaces | The worker stop | T1 `test_the_worker_can_be_stopped_and_woken` | planned |
| S1-T7 | Spec acceptance | v1.0.2 renders the v2 feed | T1 `test_v1_0_2_renders_the_v2_feed` | planned |
| S5-T06 | Spec acceptance | Civil dates across time zones and DST | T2 `test_local_today_across_time_zones_and_dst`, `test_badges` | planned |
| S5-T07 | Spec acceptance | Month-only, year-only and expected windows | T2 `test_month_year_and_expected_windows` | planned |
| S5-T08 | Spec acceptance | Held vs Past | T2 `test_held_and_past` | planned |
| S5-T09 | Spec acceptance | Conflicts suppress "today" | T2 `test_conflicts_suppress_today` | planned |
| R4 (Plan 2b, extension part) | Requirement | A renewal-only contest is an expected window, never announced | T2 `test_renewal_only_child_is_labelled_expected` | planned |
| R22 (Plan 3, stale-date part) | Requirement | A fallback source's fetch date is shown, then "Unverified since" | T2 `test_stale_fetch_date_is_shown` | planned; the possible matches, umbrellas and pins parts are 5b-2's |
| R25 (Plan 3, label parts) | Requirement | A disputed cancellation; a past rescheduled election is past and unconfirmed; the `less_precise` note; a cached confirmation's date | T2 `test_conflicts_suppress_today` (the cancellation row), `test_held_and_past` (the rescheduled row), `test_less_precise_note`, `test_cached_confirmation_shows_its_date` | planned; the umbrella and chip parts are 5b-2's |
| S5-T03 | Spec acceptance | Both documents validated; version dispatch | T3 `test_versions_are_dispatched`, `test_every_required_field_is_checked`, `test_status_validation`; T5 `test_an_unknown_version_shows_the_update_banner` | planned |
| P130 | Decision | As in Spec corrections | T3 `test_every_schema_keyword_is_handled`, `test_limits_are_not_enforced_on_the_client`, `test_legacy_checks_match_the_producer`, `test_patterns_read_dollar_as_the_end_of_input` | planned |
| S5-T01 | Spec acceptance | The feed/status relationships | T4 `test_check_links_and_refetches_once`, `test_the_worker_checks_and_the_popup_shows_the_result` | planned |
| S5-T02 | Spec acceptance | Late and out-of-order responses | T4 `test_check_orders_responses`, `test_two_checks_at_once_fetch_once` | planned |
| S5-T04 | Spec acceptance | Sleep, restart, worker termination | T4 `test_the_alarm_survives_restart_and_worker_termination`, `test_worker_handlers`, `test_the_worker_wires_its_handlers` | planned; `onStartup` and a real alarm firing are covered through the handlers only (Known limits) |
| S5-T21 (cache-write part) | Spec acceptance | A failed write keeps the previous cache | T4 `test_a_failed_write_keeps_the_previous_pair`, `test_a_failed_write_in_the_worker_keeps_the_cache` | planned; large collections are 5b-2's |
| S5-T22 | Spec acceptance | Offline and an expired cache | T4 `test_check_records_failures_and_keeps_the_cache`, `test_offline_with_and_without_a_cache` | planned |
| V2-T03 | Spec acceptance | The rollback ordering rows | T4 `test_rollback_ordering` | planned |
| NM-T03 | Spec acceptance | A defective newer cache, the republication, a delayed response, the v1 scraper after the revert | T4 `test_recovery_reaches_the_client` | planned |
| R40 (Plan 5a) | Requirement | After a rollback the client accepts the republication, then v1's later feed, and shows the mismatch banner | T4 `test_recovery_reaches_the_client`; T5 `test_rollback_v1_feed_shows_the_mismatch_banner` | planned |
| R38 (Plan 5a) | Requirement | `DATA_URL` unchanged in `background.js` | T4 the existing `test_served_check_reads_the_extension_url`, `test_the_worker_checks_and_the_popup_shows_the_result` (the request log) | planned |
| P131, P132 | Decisions | As in Spec corrections | T4 the tests above, `test_due` | planned |
| P137 | Interfaces | The manifest's one change | T4 `test_permissions_are_v1_0_2s` | planned |
| S5-T05 | Spec acceptance | Freshness thresholds and clock skew | T5 `test_freshness_thresholds_and_clock_skew`, `test_banner_conditions_in_order` | planned |
| R35 (Plan 4) | Requirement | v2 and the status read, linked, text as text, no defaults | T4 (link); T5 `test_health_text_is_inserted_as_text`; the Global Constraint | planned |
| P133 | Decision | As in Spec corrections | T5 `test_banner_conditions_in_order`, `test_the_footer`, `test_acknowledged_issues_describe_the_real_condition` | planned |
| S5-T12 | Spec acceptance | Child counting "1 of 27" | T6 `test_partial_matches`, `test_tabs_and_counters_share_one_state` (the search row) | planned |
| S5-T13 | Spec acceptance | Deduplicated totals and aggregates | T6 `test_children_are_counted_once` | planned |
| S5-T14 | Spec acceptance | Tabs and counters in one state | T6 `test_tabs_and_counters_share_one_state` | planned |
| P134, P135 | Decisions | As in Spec corrections | T2's label tests; T6 `test_tab_membership`, `test_level_filter`, `test_tab_counts_on_the_fixture` | planned |
| Red-team B1 | Review finding (High), confirmed | Statuses are ordered by attempt; an older success never erases a newer failure; identical pairs are idempotent by digest | T4 `test_status_selection`, `test_check_orders_responses`; T5 `test_a_newer_failure_is_not_erased` | planned |
| Red-team B2 | Review finding (Medium), confirmed | The best feed is kept across both rounds | T4 `test_a_retry_keeps_the_best_feed` | planned |
| Red-team B3 | Review finding (Medium), confirmed | A cached record is validated like a download | T4 `test_cached_records_are_validated`, `test_a_corrupt_cache_is_ignored` | planned |
| Red-team B4 | Review finding (Medium), confirmed | A linked legacy feed says source health isn't available | T5 `test_banner_conditions_in_order` (the linked-legacy rows), `test_rollback_v1_feed_shows_the_mismatch_banner` | planned |
| Red-team smaller items | Review corrections | The clock wording; real moments and days; the isolated patch; the measured storage claim; the deadline and status limit; "Confirmed held" | Review Focus 1; T3 `test_timestamps_and_dates_must_be_real`; T4 `test_a_failed_write_in_the_worker_keeps_the_cache`, `test_a_real_quota_failure_keeps_the_previous_pair`, `test_check_has_a_deadline`, `test_due`; T6 `test_children_are_counted_once` (the held row) | planned |
| P138 | Decision, ruled B (2026-10-26) | A month shows every card whose interval overlaps it | T6 `test_month_rule` | planned |
| I2 (Plan 3 final review) | A ruling for the user's veto | Unchanged | — | open (the user's) |
| R37 | Parked by the user | Unchanged | — | open (parked) |

## How to execute this plan

- **Where:** the worktree `C:/Users/senescalk/Desktop/elections-calendar/.claude/worktrees/never-miss-v2`,
  branch `feat/never-miss-v2`.
  - Do not create worktrees, do not switch branches, do not commit to `main`.
  - Keep the shell in the worktree. Use `( cd … && … )` subshells for anything elsewhere.
- **Style:**
  - This plan pins names, signatures, rules, messages and test values. You write the bodies.
    Private helpers are yours.
  - If a rule is ambiguous, stop and ask the controller. Never guess a value, and never change an
    expected value to match the output.
  - JS is plain ES2022 modules, with `export function` and `const`, and no classes unless a step
    names one. Files use LF.
- **Per task:** follow the Implement-Review loop in the user's CLAUDE.md (at most 3 rounds):
  1. Pre-flight against the current source.
  2. Write the failing test.
  3. Implement.
  4. Run the gates, each in its own shell call:
     - `GIT_ALLOW_PROTOCOL=file .venv/Scripts/python.exe -m pytest -q`
     - `.venv/Scripts/mypy.exe`
     - `.venv/Scripts/mypy.exe --platform linux`
     - `.venv/Scripts/ruff.exe check`
     - `.venv/Scripts/lint-imports.exe --config importlinter.ini`
  5. Run the mutation table.
  6. Commit.
- **The extension suite on its own:**
  `GIT_ALLOW_PROTOCOL=file .venv/Scripts/python.exe -m pytest tests/extension -q`. It needs Chromium
  build 1248 (`.venv/Scripts/python.exe -m playwright install chromium`, already done on this
  machine).
- **Mutations:** one per new test, in `.scratch/mutations/plan5b1-task-<N>.json`, in the format of
  `.scratch/mutate.py` (`{test, file, old, new}`; `old` unique in the file). They work on `.js` files
  as on `.py` files.
  - Stage the task's files first, and run with `PYTHONDONTWRITEBYTECODE=1` and
    `GIT_ALLOW_PROTOCOL=file`.
  - The harness copies `extension/` into a temporary folder once per session, so every mutation run
    sees the mutated file.
  - Each task names a mutation for each test. Pick the `old` text yourself.
  - After every task, run `.scratch/plan5a/mut_unique.py` over `plan5b1-*.json` as well.
- **Runtime:**
  - **A browser launch** costs about 2 s. The session shares one context for the working extension,
    one for v1.0.2 and one for the pure modules' test page. Only tests that install, restart or
    change the time zone launch their own.
  - **The fixture artifact** costs 3.4 s, once per session.
- **Cost (an estimate by analogy with Plan 5a, not a measurement):**
  - six tasks at one implementer and one reviewer each;
  - about one fix round per task with its scoped re-review. The JS is new ground, so expect more in
    Tasks 4 and 6; Task 4 is the largest after revision 2;
  - then a whole-branch review with one fix wave.

  That is about 22–30 agent runs, roughly USD 190–330, or about two days of the USD 150 daily
  budget. Every task ends at a green commit.
- **Bounds:**
  - One task at a time.
  - One reviewer per round, fresh each round; at most 3 fix rounds per task.
  - If round 3 ends with a gate red, a Critical or Important finding open, or a mutation alive, stop:
    commit nothing that is not green, and report what is open.
  - An AWS, Bedrock or budget error stops all work at the last green commit, with uncommitted work in
    a named stash.
  - No merge and no push.
- **Handover:** after every task, record the commit, the Review record rows it verified and the next
  task in two files:
  - `C:/Users/senescalk/Desktop/handovers/elections-v2-plan5b1-sdd-ledger.md` (new);
  - `C:/Users/senescalk/Desktop/handovers/elections-v2-RESUME.md`.
- **Hook:** the Desktop PostToolUse hook runs `ruff check --fix` on each edited `.py`. Check
  `git diff --stat` for unrelated rewrites. Never write source files through shell heredocs
  (backslashes collapse); use the Write tool or a bytes script.
- **Reviewers check, besides CLAUDE.md's list:**
  - a `new Date("YYYY-MM-DD")` or `Date.parse` of a civil date;
  - a time judgement that reads the clock instead of `now`;
  - feed text reaching `innerHTML`;
  - a default on a required field;
  - a second `storage.set` in one check;
  - a test that passes against v1.0.2's files too.

## File structure

| Path | Responsibility | Task |
|---|---|---|
| `scripts/live_check.py`, `tests/scripts/test_live_check.py`, `elections_calendar/validate.py`, `tests/feed/test_validate.py`, `elections_calendar/pipeline.py`, `tests/pipeline/test_run.py`, `README.md` | Plan 5a's leftovers (R1–R5, the nit) | 1 |
| `.github/workflows/update-elections.yml`, `tests/workflow/test_workflow.py` | `--with-deps`; the extension suite in the gates job (P128) | 1 |
| `tests/fixtures/v1/extension/**`, `tests/fixtures/v1/PROVENANCE.md` | v1.0.2's files (P129) | 1 |
| `tests/support/extension.py`, `tests/support/extension_page/` (`test.html`, `probe.js`, `fakes.js`) | the harness: copies, launch, routing, storage, the worker stop, module calls, check fakes | 1 (`fakes.js` in 4) |
| `tests/extension/__init__.py`, `conftest.py`, `test_harness.py`, `test_legacy_client.py`, `test_extension_files.py` | the harness's own tests, S1-T7, static checks | 1 (`test_extension_files.py` grows in 2–6) |
| `extension/lib/dates.js`, `extension/lib/labels.js`; `tests/extension/test_dates.py`, `test_labels.py` | civil dates, badges, timestamps; labels, chips, notes, card summaries | 2 |
| `extension/lib/schema.js`, `extension/lib/validate.js`, `extension/schemas/*.json`; `tests/extension/test_validate.py` | the schema subset, formats, legacy and status checks | 3 |
| `extension/lib/order.js`, `extension/lib/load.js`, `extension/background.js`, `extension/manifest.json`, `extension/lib/legacy.js`, `extension/popup.js`, `extension/popup.html`; `tests/extension/test_order.py`, `test_loading.py` | ordering and linking; one check; the module worker; the popup reading storage; v1.0.2's renderer moved | 4 |
| `extension/lib/health.js`, `extension/popup.html`, `extension/popup.js`, `extension/styles.css`; `tests/extension/test_banner.py` | the banner, the health panel, the footer | 5 |
| `extension/lib/count.js`, `extension/lib/render.js`, `extension/popup.html`, `extension/popup.js`, `extension/lib/legacy.js`, `extension/styles.css`; `tests/extension/test_counting.py` | the one pipeline, tabs, the level filter, counters, v2 cards | 6 |
| `README.md` | the extension suite and Chromium (1); the extension's modules (4) | 1, 4 |

## Tasks

### Task 1: Plan 5a's leftovers, the harness, and v1.0.2 on the v2 feed (R1–R5; P128, P129, P136; S1-T7)

**Files:**
- Modify: `scripts/live_check.py` (`_compare_contests.read`, `_make_folders`),
  `tests/scripts/test_live_check.py`, `elections_calendar/validate.py` (`_ecma`),
  `tests/feed/test_validate.py`, `elections_calendar/pipeline.py` (`_write_rejected_pages`
  docstring), `tests/pipeline/test_run.py:491` (docstring), `README.md` (the publish bullet; the
  extension suite under "Gates").
- Modify: `.github/workflows/update-elections.yml` (the "Install Chromium" step),
  `tests/workflow/test_workflow.py`.
- Create: `tests/fixtures/v1/extension/` (12 files) and a `## extension/` section in
  `tests/fixtures/v1/PROVENANCE.md`.
- Create: `tests/support/extension.py`, `tests/support/extension_page/test.html`,
  `tests/support/extension_page/probe.js`.
- Create: `tests/extension/__init__.py`, `tests/extension/conftest.py`,
  `tests/extension/test_harness.py`, `tests/extension/test_legacy_client.py`,
  `tests/extension/test_extension_files.py`.

**Interfaces:**
- Consumes: `tests.support.artifact._built("published")` (the linked pair); the v1 feed
  `tests/fixtures/feed/2026-10-16-ff30417.json`.
- Produces (`tests/support/extension.py`; later tasks use exactly these):

  ```python
  ROOT: Final[Path]                    # the repository root
  V1_EXTENSION: Final[Path]            # tests/fixtures/v1/extension
  RAW_BASE: Final = "https://raw.githubusercontent.com/newscorp-ghfb/global-elections-calendar/main/"
  PAGE_NOW: Final = "2026-10-19T14:00:00Z"   # 2 h after the fixture artifact's generated_at

  def artifact_pair() -> tuple[bytes, bytes]       # (elections.json, status.json), cached
  def v1_feed() -> bytes                            # the 2026-10-16 v1 feed, as committed

  def extension_copy(dest: Path, *, legacy: bool) -> Path
      # legacy: a copy of V1_EXTENSION; else of ROOT/extension. Both get test/ (the files of
      # tests/support/extension_page/). Returns the copy's folder.

  class Served:                                     # the routed raw host
      log: list[str]                                # file names requested, in order
      def set(self, name: str, *responses: bytes | int | None | Literal["hang"]) -> None
          # bytes: 200 with that body; int: that HTTP status, empty body; None: the request
          # fails (route.abort); "hang": never answered. The last response repeats.
      def reset(self) -> None                       # everything None, log cleared

  class Ext:                                        # one launched extension
      context: BrowserContext; ext_id: str; served: Served; profile: Path; folder: Path
      def worker(self) -> Worker                    # the live worker (waits up to 10 s)
      def storage(self) -> dict[str, Any]           # chrome.storage.local.get(null)
      def seed(self, values: Mapping[str, Any]) -> None
      def clear(self) -> None                       # chrome.storage.local.clear()
      def open(self, path: str, *, now: str | None = PAGE_NOW) -> Page
          # sets the context clock to `now` (None: leave it), opens chrome-extension://<id>/<path>
      def lab(self) -> Page                         # test/test.html, opened once per Ext
      def stop_worker(self) -> None                 # CDP Target.closeTarget; waits until gone
      def worker_running(self) -> bool              # an extension service_worker target exists
      def relaunch(self) -> "Ext"                   # close; launch the same profile and folder
      def close(self) -> None

  def launch(playwright: Playwright, profile: Path, folder: Path, *,
             timezone_id: str = "UTC") -> Ext
  def js(page: Page, module: str, name: str, *args: Any) -> Any
      # page.evaluate("async ([m, n, a]) => (await import(m))[n](...a)", ["/" + module, name, args])
  ```

  `tests/extension/conftest.py` fixtures:
  - `ext`: the session's working-extension `Ext`, reset per test (`clear()`, `served.reset()`, every
    page but the lab closed);
  - `legacy_ext`: the same for v1.0.2;
  - `fresh_ext`: a new profile and copy per test, closed after it;
  - `lab`: `ext.lab()`, for the session.

- [ ] **Step 1: Plan 5a's leftovers.** These are small, independent edits, each with its own test
      where there is behaviour:
  - **R1** (`scripts/live_check.py`, `_compare_contests.read`): inside the existing `try`, also read
    `entry["place"]`, `entry["office"]` and `entry["round"]` (the key must exist; `None` is a
    value). A missing one gives the existing line
    `cannot read expected entry <name>: missing key '<key>'`, and the loop continues. Extend
    `test_a_malformed_expected_entry_is_a_material_line_and_does_not_skip_the_rest` with three
    rows, one entry without `place`, one without `office` and one without `round`. Each gives
    exactly its one line, and a valid entry after them is still compared.
    - *Mutation:* drop the `entry["round"]` read; the `round` row then raises out of `read()`, and
      the later entry is skipped.
  - **R4** (`_make_folders`): wrap the `parent.exists()`/`is_dir()` loop in
    `try … except OSError as exc: return f"cannot check {parent}: {exc}"`. New test
    `test_an_unreadable_report_parent_is_a_reason`: it monkeypatches `Path.exists` to raise
    `PermissionError("denied")` for one parent. `_make_folders` returns a string starting with
    `cannot check ` and ending with `denied`, and `main` exits 1 with that line on stderr.
    - *Mutation:* remove the `except`.
  - **R5** (`elections_calendar/validate.py`, `_ecma`): a final `$` is an anchor when it is
    preceded by an even number of backslashes, zero included. New test
    `test_ecma_reads_an_escaped_backslash_before_the_end` (`tests/feed/test_validate.py`). `_ecma`
    returns a compiled pattern; "matches" means `.search(s) is not None`:
    - `_ecma("a\\\\$")` (pattern text `a\\$`) matches `"a\\"` and not `"a\\\n"`;
    - `_ecma("a\\$")` (an escaped dollar) matches `"a$"`;
    - `_ecma("a$")` does not match `"a\n"`.
    - *Mutation:* restore the `endswith("\\$")` test.
  - **R2:** `tests/pipeline/test_run.py:491` docstring:
    `"""The source's own reasons only (P108); test_a_parse_failure_shows_one_worker_failed_and_no_deadline checks the status file."""`
  - **R3:** `README.md` publish bullet: the sentence "It runs only on `main` and only for the
    schedule or a dispatch with `publish: true`." moves to the start of the bullet, right after
    the job's name and concurrency group. Every line of the bullet stays within 100 columns.
  - **The nit:** `_write_rejected_pages`' docstring ends "nothing when no page is listed".
  - Run the three tests, then commit:
    `git commit -m "fix: Plan 5a re-review minors R1-R5 (Plan 5b-1 Task 1)"`.

- [ ] **Step 2: the v1.0.2 fixture copy (P129).**
  - For each of the 12 files of `git ls-tree -r ff30417 extension/`, write
    `git -c core.autocrlf=false cat-file blob ff30417:extension/<path>` to
    `tests/fixtures/v1/extension/<path>`. Use a bytes script, not shell redirection of text.
  - Add a `## extension/` section to `tests/fixtures/v1/PROVENANCE.md`: the command, 95,447 bytes,
    and a table of path, bytes and SHA-256.
  - Test `test_v1_extension_fixture_is_v1_0_2` (`tests/extension/test_extension_files.py`, no
    browser): the file set under `V1_EXTENSION` is exactly the 12 paths, and each SHA-256 equals
    a `V1_SHA256: Final[dict[str, str]]` table in the test, copied from `PROVENANCE.md`.
    - *Mutation:* change one byte of `tests/fixtures/v1/extension/popup.js`.

- [ ] **Step 3: the workflow (P128, R39).**
  - Update `test_gates_job_runs_the_canonical_gates`: its first expected command becomes
    `".venv/bin/python -m playwright install --with-deps chromium"`.
  - New test `test_gates_job_runs_the_extension_suite`:
    - the pytest step's `run` is exactly `.venv/bin/python -m pytest -q` (no `-k`, `-m`,
      `--ignore`, `--deselect` or `-p`), and its `env` is `{"CI": "true"}`;
    - the Chromium step comes before it in the same job;
    - `pyproject.toml`'s `testpaths` is `["tests"]`;
    - `tests/extension/` holds at least one `test_*.py`.
  - Make both pass by changing the step's `run` line only.
    - *Mutation:* remove `--with-deps` from the workflow (the first test fails). For the second
      test: add `--ignore=tests/extension` to the pytest step.

- [ ] **Step 4: the harness.** `tests/support/extension.py` with the Interfaces above.
  - **`launch`:** `playwright.chromium.launch_persistent_context(str(profile), channel="chromium",
    headless=True, timezone_id=timezone_id, locale="en-GB", args=[f"--disable-extensions-except={folder}",
    f"--load-extension={folder}", "--host-resolver-rules=MAP * ~NOTFOUND"])`. Then:
    - `context.set_default_timeout(10_000)`;
    - register `Served.handle` with `context.route(RAW_BASE + "*", …)`;
    - wait for the worker (`context.service_workers` or `context.wait_for_event("serviceworker")`);
    - `ext_id = worker.url.split("/")[2]`.
  - **`Served.handle`** logs the last path segment and answers that file's next response. A file
    that was never set is `None` (an abort).
  - **`stop_worker`:**
    - Through `context.browser.new_browser_cdp_session()`, call `Target.getTargets`.
    - `Target.closeTarget` every target with `type == "service_worker"` whose `url` holds `ext_id`.
    - Poll `Target.getTargets` every 100 ms until none is left, for at most 5 s, else raise.
  - **`relaunch`:** close the context, then call `launch` with the same `profile` and `folder`.
  - **`tests/support/extension_page/test.html`:** `<!doctype html><meta charset="utf-8"><title>test</title>`.
    **`probe.js`:** `export function answer(a, b) { return a + b; }`.
  - **Teardown:** every `Ext` is closed at session end, and `fresh_ext` closes its own.

- [ ] **Step 5: the harness's tests** (`tests/extension/test_harness.py`). Each runs on the
      working extension (v1.0.2's code until Task 4, so it must not depend on the code's version):

  ```python
  def test_pure_modules_import_in_an_extension_page(lab: Page) -> None:
      assert js(lab, "test/probe.js", "answer", 40, 2) == 42

  def test_requests_are_routed_and_nothing_else_resolves(ext: Ext) -> None:
      ext.served.set("elections.json", b'{"x": 1}')
      page = ext.open("test/test.html")
      got = page.evaluate("u => fetch(u).then(r => r.text())", RAW_BASE + "elections.json")
      assert got == '{"x": 1}' and ext.served.log == ["elections.json"]
      failed = page.evaluate(   # no-cors: a reachable host resolves (opaque); only DNS fails
          "() => fetch('https://example.com/', {mode: 'no-cors'}).then(() => 'ok', e => e.name)")
      assert failed == "TypeError"

  def test_the_worker_can_be_stopped_and_woken(ext: Ext) -> None:
      ext.stop_worker()
      assert not ext.worker_running()
      page = ext.open("test/test.html")
      page.evaluate("() => chrome.runtime.sendMessage({type: 'PING'}).catch(() => null)")
      page.wait_for_timeout(500)
      assert ext.worker_running()

  def test_a_relaunch_keeps_the_id_and_storage(fresh_ext: Ext) -> None:
      fresh_ext.seed({"probe": [1, 2]})
      old = fresh_ext.ext_id
      again = fresh_ext.relaunch()
      assert again.ext_id == old and again.storage()["probe"] == [1, 2]
  ```

  - *Mutations:*
    - drop `--host-resolver-rules` from `launch` (example.com then resolves through the network or
      the proxy, so `failed != "TypeError"`). If this machine has no network, the controller records
      that and uses a second mutation instead: route `**/*` instead of the raw host, which logs
      `example.com`;
    - make `stop_worker` skip `Target.closeTarget`;
    - make `relaunch` use a new profile folder;
    - make `js` ignore `name` (it then calls `undefined`).

- [ ] **Step 6: S1-T7** (`tests/extension/test_legacy_client.py`):

  ```python
  def _october(legacy_ext: Ext, feed: bytes) -> tuple[list[str], str, str]:
      legacy_ext.served.set("elections.json", feed)
      page = legacy_ext.open("popup.html")
      page.wait_for_selector("#electionList:not(.hidden) .election-item")
      names = page.locator("#electionList .election-country").all_text_contents()
      month = page.locator("#currentMonthLabel").text_content() or ""
      return names, month, page.locator("#footer").text_content() or ""

  def test_v1_0_2_renders_the_v2_feed(legacy_ext: Ext) -> None:
      feed, _ = artifact_pair()
      names, month, footer = _october(legacy_ext, feed)
      doc = json.loads(feed)
      assert names == [c["country"] for c in doc["months"]["2026-10"]]   # 30 cards
      assert month == "OCTOBER 2026" and "Stale" not in footer

  def test_v1_0_2_renders_the_v1_feed(legacy_ext: Ext) -> None:
      names, month, _ = _october(legacy_ext, v1_feed())
      assert len(names) == 27 and month == "OCTOBER 2026"
  ```

  - **The selectors** are v1.0.2's own: `buildCard` makes `li.election-item` with
    `span.election-country` (`popup.js:111-119`). `#currentMonthLabel` is
    `monthName(currentMonth).toUpperCase()` (`:219`), and the month comes from the feed's
    `current_month` (`:278`). A stale footer starts "⚠️ WARNING: Stale Data." (`:305`).
  - **Both tests** also collect `page.on("pageerror", …)` and assert that it stays empty.
  - *Mutation* (for the first test): in `elections_calendar/feed.py:487`, write `current_month` as
    `window.month_keys[-1]`. Only its format is checked, and v1.0.2 then opens January (5 cards).
  - The second test is the control: it fails if `extension_copy(legacy=True)` copies the working
    folder after Task 4. Its mutation is to copy `ROOT/extension` for `legacy=True` once Task 4 has
    changed it. Until then, use the mutation "`v1_feed()` returns the artifact feed" (30 ≠ 27).

- [ ] **Step 7: README** ("Gates", after the Linux block):
  "The extension suite (`tests/extension/`) runs headless Chromium build 1248; install it once
  with `.venv\Scripts\python.exe -m playwright install chromium` (CI uses `--with-deps`)."

- [ ] **Step 8: Gates, mutations, commit.**
  `git commit -m "test(extension): the Playwright harness, v1.0.2 fixture and S1-T7 (Plan 5b-1 Task 1)"`.

### Task 2: Civil dates and labels (`dates.js`, `labels.js`; P134; S5-T06–T09, R4, R22, R25)

**Files:**
- Create: `extension/lib/dates.js`, `extension/lib/labels.js`.
- Create: `tests/extension/test_dates.py`, `tests/extension/test_labels.py`.
- Modify: `tests/extension/test_extension_files.py` (`test_pure_modules_use_no_browser_api`).

**Interfaces:**
- Consumes: Task 1's `lab`, `js`, `launch`, `artifact_pair`.
- Produces (`extension/lib/dates.js`, all pure):

  ```js
  export const MONTHS        // ["January", …, "December"]
  export const MONTHS_SHORT  // ["Jan", …, "Dec"]
  export function isCivilDate(s)        // boolean: a string YYYY-MM-DD naming a real day (leap years by arithmetic)
  export function parseTimestamp(s)     // ms or null: ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z$ and real (hour<24, minute<60, second<60)
  export function localToday(nowMs)     // "YYYY-MM-DD" of the instant in the browser's time zone
  export function dayMonth(d)           // "2 Nov"
  export function dayMonthYear(d)       // "15 November 2026"
  export function monthName(d)          // "November" (d: YYYY-MM-DD or YYYY-MM)
  export function monthYear(d)          // "November 2026"
  export function badge(card)           // {day, mon} from date, end_date, date_precision
  export function stamp(ms)             // "19 Oct 2026, 14:00" in local time, 24-hour
  export function stampDate(ms)         // "19 Oct 2026" in local time
  ```

  Produces (`extension/lib/labels.js`, pure; imports `dates.js` only):

  ```js
  export const KINDS  // ["cancelled","postponed","possibly_cancelled","possibly_postponed","disputed",
                      //  "held","past","past_expected","expected","today","scheduled","day_unconfirmed"]
  export function childLabel(card, child, { today, now })   // {kind, text, chips: string[], notes: string[]}
  export function cardLabel(card, labels)                   // {kind, text}; labels: the children's childLabel results
  export function sourceNote(source)                        // string | null
  ```

- [ ] **Step 1: Write the date tests** (`tests/extension/test_dates.py`):

  ```python
  @pytest.mark.parametrize("value, ok", [
      ("2026-10-19", True), ("2028-02-29", True), ("2026-02-29", False), ("2100-02-29", False),
      ("2026-13-01", False), ("2026-00-10", False), ("2026-10-32", False), ("2026-1-9", False),
      ("2026-10-19\n", False), ("", False), (20261019, False), (None, False)])
  def test_civil_dates_are_checked_by_components(lab: Page, value: object, ok: bool) -> None:
      assert js(lab, "lib/dates.js", "isCivilDate", value) is ok

  @pytest.mark.parametrize("value, expected", [
      ("2026-10-19T12:00:00Z", datetime(2026, 10, 19, 12, tzinfo=UTC)),
      ("2026-10-19T12:00:00.5Z", datetime(2026, 10, 19, 12, 0, 0, 500000, tzinfo=UTC)),
      ("2026-10-19T12:00:00+00:00", None), ("2026-10-19T24:00:00Z", None),
      ("2026-02-30T00:00:00Z", None), ("2026-10-19T12:00:00Z\n", None), ("x", None), (5, None)])
  def test_timestamps(lab: Page, value: object, expected: datetime | None) -> None:
      got = js(lab, "lib/dates.js", "parseTimestamp", value)
      assert got == (None if expected is None else expected.timestamp() * 1000)

  @pytest.mark.parametrize("date, end, precision, day, mon", [
      ("2026-10-04", "2026-10-04", "day", "4", "OCT"),
      ("2026-09-18", "2026-09-20", "day", "18–20", "SEP"),
      ("2026-09-30", "2026-10-02", "day", "30–2", "SEP–OCT"),
      ("2026-12-24", "2027-02-06", "day", "24–6", "DEC–FEB"),
      ("2026-12-01", "2026-12-31", "month", "TBC", "DEC"),
      ("2026-11-01", "2027-01-31", "month", "TBC", "NOV–JAN"),
      ("2027-01-01", "2027-12-31", "year", "TBC", "2027")])
  def test_badges(lab: Page, date: str, end: str, precision: str, day: str, mon: str) -> None:
      card = {"date": date, "end_date": end, "date_precision": precision}
      assert js(lab, "lib/dates.js", "badge", card) == {"day": day, "mon": mon}

  ZONES: Final = ("Pacific/Kiritimati", "Pacific/Pago_Pago", "Europe/London")  # UTC+14, UTC-11
  DAYS: Final = {   # instant -> the local date in each of ZONES
      "2026-10-19T10:30:00Z": ("2026-10-20", "2026-10-18", "2026-10-19"),
      "2026-10-24T23:30:00Z": ("2026-10-25", "2026-10-24", "2026-10-25"),  # London 00:30 BST
      "2026-03-29T00:30:00Z": ("2026-03-29", "2026-03-28", "2026-03-29"),  # before BST starts
  }
  ONE_DAY: Final = {"date": "2026-10-25", "end_date": "2026-10-25", "date_precision": "day"}

  def ms(instant: str) -> float:
      return datetime.fromisoformat(instant).timestamp() * 1000

  @pytest.mark.parametrize(("col", "zone"), enumerate(ZONES))
  def test_local_today_across_time_zones_and_dst(
      playwright: Playwright, tmp_path: Path, col: int, zone: str
  ) -> None:
      folder = extension_copy(tmp_path / "x", legacy=False)
      e = launch(playwright, tmp_path / "p", folder, timezone_id=zone)
      try:
          page = e.lab()
          for instant, days in DAYS.items():
              assert js(page, "lib/dates.js", "localToday", ms(instant)) == days[col]
          assert js(page, "lib/dates.js", "badge", ONE_DAY) == {"day": "25", "mon": "OCT"}
          if zone == "Europe/London":   # the clock shows 01:30 twice on 25 Oct 2026
              for instant in ("2026-10-25T00:30:00Z", "2026-10-25T01:30:00Z"):
                  assert js(page, "lib/dates.js", "stamp", ms(instant)) == "25 Oct 2026, 01:30"
      finally:
          e.close()
  ```

  - *Mutations:*
    - `isCivilDate` without the leap rule for centuries (`2100-02-29` passes);
    - `parseTimestamp` that skips the range check;
    - `badge` that drops the end of a range;
    - `localToday` using `getUTCDate` (Kiritimati and Pago Pago fail).

- [ ] **Step 2: Write the label tests** (`tests/extension/test_labels.py`).
  - **The template** is `TEMPLATE`, a deep copy of the artifact's Canada referendum card of
    2026-10-19, which has one child. Its `level` is set to `national` and its `date_status` to
    `confirmed` (they are `subnational` and `unknown` in the fixture), so a row's chips come only
    from that row's fields. Helpers `card(**fields)` and `kid(**fields)` copy it and replace
    fields. `label(card, child, today="2026-10-19", now=PAGE_NOW_MS)` calls
    `childLabel`, where `PAGE_NOW_MS` is `PAGE_NOW` in milliseconds.
  - **The rows below are the spec of P134.** Each row asserts `kind`, `text`, and where given
    `chips` and `notes`, exactly.

  | Test | Card fields | Child fields | today, now | kind · text · chips · notes |
  |---|---|---|---|---|
  | `test_exact_dates` | date 2026-10-26 day voting_period confirmed, status Upcoming | — | 2026-10-19 | scheduled · "Scheduled" · [] · [] |
  | ″ | same, date_status tentative, level subnational | — | ″ | scheduled · "Scheduled" · ["Tentative", "Subnational"] · [] |
  | `test_month_year_and_expected_windows` | 2026-10-01..2026-10-31 month unknown | — | 2026-10-19 | day_unconfirmed · "October — day unconfirmed" |
  | ″ | 2026-12-01..2026-12-31 month unknown | — | ″ | day_unconfirmed · "December — day unconfirmed" |
  | ″ | 2026-11-01..2027-01-31 month unknown | — | ″ | day_unconfirmed · "November–January — day unconfirmed" |
  | ″ | 2026-09-01..2026-09-30 month unknown | — | ″ | past_expected · "Past expected period — not confirmed" |
  | ″ | 2026-11-02..2027-01-31 day expected_window tentative | — | ″ | expected · "Expected between 2 Nov and 31 Jan" · ["Tentative"] |
  | ″ | 2026-12-01..2026-12-31 month expected_window | — | ″ | expected · "Expected in December" |
  | ″ | 2026-11-01..2027-01-31 month expected_window | — | ″ | expected · "Expected between November and January" |
  | ″ | 2027-01-01..2027-12-31 year unknown | — | ″ | day_unconfirmed · "2027 — date unconfirmed" |
  | ″ | 2027-01-01..2027-12-31 year expected_window | — | ″ | expected · "Expected in 2027" |
  | ″ | 2026-09-01..2026-10-18 day expected_window | — | ″ | past_expected · "Past expected period — not confirmed" |
  | `test_held_and_past` | 2026-10-04 day, status Held | occurrence_confirmed true | 2026-10-19 | held · "Held" |
  | ″ | 2026-10-04 day, status Held | occurrence_confirmed false | ″ | past · "Past" |
  | ″ (R25 `test_past_rescheduled_is_unconfirmed`) | 2026-10-04 day, status Held | rescheduled_from ["15 September"], occurrence_confirmed false | ″ | past · "Past" |
  | ″ (card) | three children of 2026-10-04: two confirmed, one not | — | ″ | `cardLabel` → past · "Past · 2 of 3 confirmed held" |
  | ″ (card) | three confirmed | — | ″ | `cardLabel` → held · "Held" |
  | `test_conflicts_suppress_today` | 2026-10-18..2026-10-20 day voting_period | — | 2026-10-19 | today · "Scheduled voting period: today (approx.)" |
  | ″ | same | date_conflict true | ″ | scheduled · "Scheduled" · notes ["Sources disagree on date"] |
  | ″ | same | status_conflict true | ″ | possibly_postponed · "Possibly postponed — sources disagree" |
  | ″ (R25 `test_cancellation_conflict_label`) | same | status_conflict true, one source status_claim "cancelled" | ″ | possibly_cancelled · "Possibly cancelled — sources disagree" |
  | ″ | same, status Postponed | — | ″ | postponed · "Postponed" |
  | ″ | same, status Cancelled | status_conflict true | ″ | cancelled · "Cancelled" |
  | ″ | same, status Disputed | — | ″ | disputed · "Disputed" |
  | ″ | 2026-10-18..2026-10-20 day unknown meaning | — | ″ | scheduled · "Scheduled" |
  | ″ (card) | two children, one with status_conflict | — | ″ | `cardLabel` → possibly_postponed · "Possibly postponed — sources disagree · 1 of 2" |
  | `test_renewal_only_child_is_labelled_expected` (R4) | 2026-12-01..2026-12-31 month expected_window tentative | one source, IPU, evidence_kind expected_renewal | 2026-10-19 | expected · "Expected in December" · ["Tentative"] |
  | `test_less_precise_note` (R25) | 2026-11-15 day | provisional_date less_precise; a provisional source 2026-11-01..2026-11-30 month | 2026-10-19 | notes ["The source now gives a less precise date: 15 November 2026 → November 2026"] |
  | ″ | 2026-11-01..2026-11-30 month | provisional_date less_precise; a provisional source 2026-01-01..2026-12-31 year | ″ | notes ["The source now gives a less precise date: November 2026 → 2026"] |
  | ″ | 2026-11-15 day | provisional_date moved; a provisional source 2026-11-22 day | ″ | notes ["Sources disagree on date"] |
  | `test_cached_confirmation_shows_its_date` (R25) | 2026-10-04 day, status Held | occurrence_confirmed; its only `held` source has fallback true, fetched_at 2026-10-16T14:39:00Z | now PAGE_NOW | held · "Held" · notes ["Confirmed by source data from 16 Oct 2026"] |
  | `test_stale_fetch_date_is_shown` (R22) | 2026-10-26 day | the selected source has fallback true, fetched_at 2026-10-16T14:39:00Z | now PAGE_NOW | notes ["Using source data from 16 Oct 2026"] |
  | ″ | same | same | now = fetched_at + 7 days exactly | notes ["Using source data from 16 Oct 2026"] |
  | ″ | same | same | now = fetched_at + 7 days + 1 s | notes ["Unverified since 16 Oct 2026"] |
  | ″ | same | same, fetched_at null | now PAGE_NOW | notes ["Unverified: the source data's date is unknown"] |

  - **`test_provisional_source_note`:**
    - `sourceNote` of a source with `provisional: true` and `fetched_at` 2026-10-19T08:57:34Z is
      `"Newer data from an incomplete fetch on 19 Oct 2026"`;
    - with `provisional: false` it is `null`;
    - with `provisional: true` and `fetched_at` null it is
      `"Newer data from an incomplete fetch"`.
  - **`test_every_fixture_child_has_a_label`:** every child of `artifact_pair()`'s feed, at today
    2026-10-19, has a kind in `KINDS` and a non-empty text. The counts per month and kind equal the
    prototype's (errata: Sep held 5, past 22; Oct held 8, past 35, scheduled 14, today 1; Nov
    scheduled 89; Dec day_unconfirmed 1, expected 3, scheduled 17; Jan expected 1, scheduled 6).
    Call it once with the whole feed through a page-side loop, not 202 calls.
  - *Mutations:* one per test. For example:
    - `test_exact_dates`: drop the "Tentative" chip;
    - `test_month_year_and_expected_windows`: compare `end < today` as `<=`;
    - `test_held_and_past`: read `card.status === "Held"` as held;
    - `test_conflicts_suppress_today`: skip the `date_conflict` test in the `today` rule;
    - `test_renewal_only_child_is_labelled_expected`: check `expected_window` after the day
      rules;
    - `test_less_precise_note`: use the card's date for both sides;
    - `test_cached_confirmation_shows_its_date`: use `some` instead of `every` held source;
    - `test_stale_fetch_date_is_shown`: `>=` for the 7 days;
    - `test_provisional_source_note`: return the note for every source;
    - `test_every_fixture_child_has_a_label`: return `day_unconfirmed` for month precision with
      the meaning `expected_window`.

- [ ] **Step 3: Run the tests to see them fail.**
  `GIT_ALLOW_PROTOCOL=file .venv/Scripts/python.exe -m pytest tests/extension/test_dates.py tests/extension/test_labels.py -q`.
  Expected: they fail on the module import (`Failed to fetch dynamically imported module`).

- [ ] **Step 4: Implement `dates.js`.**
  - `badge`:
    - **day precision:** one day gives `{day: D, mon: MON}`. A range in one month gives
      `"D1–D2"` and `MON`. A range across months gives `"D1–D2"` and `"MON1–MON2"`. `MON` is
      `MONTHS_SHORT` upper-cased.
    - **month precision:** `{day: "TBC", mon: MON}`, or `"MON1–MON2"` across months.
    - **year precision:** `{day: "TBC", mon: "YYYY"}`.
  - `stamp`: `D Mon YYYY, HH:MM` from the local `getDate`/`getMonth`/`getFullYear`/`getHours`/
    `getMinutes` of `new Date(ms)`, zero-padded hours and minutes. `stampDate` is the part before
    the comma.

- [ ] **Step 5: Implement `labels.js`.** `childLabel(card, child, {today, now})`, in this order:
  1. The card's `status` `Cancelled` gives `cancelled`, "Cancelled". `Postponed` gives
     `postponed`, "Postponed".
  2. `child.status_conflict` gives `possibly_cancelled`, "Possibly cancelled — sources disagree",
     when any of `child.sources` has `status_claim === "cancelled"`. Otherwise it gives
     `possibly_postponed`, "Possibly postponed — sources disagree".
  3. The card's `status` `Disputed` gives `disputed`, "Disputed".
  4. `child.occurrence_confirmed` gives `held`, "Held".
  5. **The dates.** `p` = `card.date_precision` and `m` = `card.date_meaning`; `start` and `end` are
     the card's `date` and `end_date`.
     - `end < today`: `past_expected`, "Past expected period — not confirmed", when
       `p !== "day"` or `m === "expected_window"`. Otherwise `past`, "Past".
     - `m === "expected_window"`: `expected`, with this text:
       - day: "Expected between {dayMonth(start)} and {dayMonth(end)}", or "Expected on
         {dayMonth(start)}" for one day;
       - month: "Expected in {monthName(start)}" for one month, else "Expected between
         {monthName(start)} and {monthName(end)}";
       - year: "Expected in {YYYY}".
     - `p === "day"`: `today`, "Scheduled voting period: today (approx.)", when
       `start <= today`, `m === "voting_period"` and `!child.date_conflict`. Otherwise
       `scheduled`, "Scheduled".
     - Otherwise `day_unconfirmed`:
       - month: "{monthName(start)} — day unconfirmed", or
         "{monthName(start)}–{monthName(end)} — day unconfirmed" across months;
       - year: "{YYYY} — date unconfirmed".
  - **Chips:**
    - "Tentative" when `card.date_status === "tentative"` and the kind is `scheduled`, `today`,
      `expected` or `day_unconfirmed`;
    - "Subnational" when `card.level === "subnational"`.
  - **Notes, in this order:**
    1. "Sources disagree on date" when `child.date_conflict` or
       `child.provisional_date === "moved"`.
    2. For `less_precise`: the first source with `provisional: true` gives "The source now gives a
       less precise date: {served} → {new}". Each side is `dayMonthYear` for day precision,
       `monthYear` for month, and `YYYY` for year. `served` is the card's date at the card's
       precision, and `new` is the source's `date` at its `date_precision`.
    3. For a fallback: among the sources with `selected` and `fallback`, take the oldest
       `fetched_at`. A `null` gives "Unverified: the source data's date is unknown".
       `now − fetched > 7 × 86,400,000` gives "Unverified since {stampDate(fetched)}". Otherwise
       "Using source data from {stampDate(fetched)}".
    4. For kind `held`, when every source with `status_claim === "held"` has `fallback`: "Confirmed
       by source data from {stampDate(latest of their fetched_at)}".
  - **`cardLabel(card, labels)`:**
    1. When any label has a `possibly_*` kind, take the first such label, and add " · {k} of {n}"
       when `n > 1`. Here `k` is the number of labels with a `possibly_*` kind, and `n` the number
       of labels.
    2. Otherwise, when every kind is `held` or `past` and both occur: kind `past`,
       "Past · {held} of {n} confirmed held".
    3. Otherwise the first label's kind and text.
  - **`sourceNote(s)`:** `s.provisional` gives "Newer data from an incomplete fetch on
    {stampDate(fetched_at)}", or without " on …" when `fetched_at` is null. Otherwise `null`.

- [ ] **Step 6: Static check.** `test_pure_modules_use_no_browser_api` in
      `test_extension_files.py`:
  - It names every pure module that exists (Task 2: `dates.js`, `labels.js`) and fails when the
    file is missing.
  - It asserts that none of the Global Constraints' tokens occurs, and that `new Date(` occurs
    only in `dates.js`.
  - *Mutation:* add `Date.now()` to `labels.js`.

- [ ] **Step 7: Run the tests to see them pass; gates; mutations; commit.**
  `git commit -m "feat(extension): civil dates and labels (Plan 5b-1 Task 2)"`.

### Task 3: Validation and the format dispatch (`schema.js`, `validate.js`; P130; S5-T03)

**Files:**
- Create: `extension/lib/schema.js`, `extension/lib/validate.js`,
  `extension/schemas/feed-v2.schema.json`, `extension/schemas/status-v1.schema.json` (byte copies).
- Create: `tests/extension/test_validate.py`.
- Modify: `tests/extension/test_extension_files.py` (`test_schema_copies_match`; the pure-module
  list gains `schema.js`, `validate.js`).

**Interfaces:**
- Consumes: Task 2's `dates.isCivilDate`, `dates.parseTimestamp`.
- Produces (`extension/lib/schema.js`):

  ```js
  export const ENFORCED_KEYWORDS  // ["type","properties","required","items","$ref","$defs","enum","const",
                                  //  "pattern","anyOf","additionalProperties","propertyNames","minimum","minItems"]
  export const IGNORED_KEYWORDS   // ["$schema","$id","title","description","maxLength","maxItems"]
  export function schemaProblems(value, schema, refChecks = {})
      // string[], at most 20, each "<pointer>: <what>". refChecks maps a $defs name to a predicate,
      // run after a value has passed $ref "#/$defs/<name>"; false gives "<pointer>: not a real <name>"
  ```

  Produces (`extension/lib/validate.js`):

  ```js
  export const MAX_FEED_BYTES     // 4_000_000
  export const MAX_STATUS_BYTES   // 1_000_000
  export const REAL               // {timestamp: s => parseTimestamp(s) !== null, date: isCivilDate}
                                  // passed as refChecks by feedFormat and statusProblems
  export function legacyProblems(doc)         // string[]
  export function feedFormat(doc, feedSchema) // {format: "v2"|"legacy"|"update_needed"|"invalid", problems: string[]}
  export function statusProblems(doc, statusSchema) // string[]
  ```

- [ ] **Step 1: Write the tests** (`tests/extension/test_validate.py`). A module-scoped fixture
      `schemas` loads both files from `schemas/` as Python objects and passes them to the JS calls.
  - **`test_the_fixture_documents_are_valid`:** these docs dispatch as shown, with `problems == []`:
    - `artifact_pair()`'s feed → `v2`, and its status → `statusProblems == []`;
    - `v1_feed()` → `legacy`;
    - `republished_feed(feed, now=…)` → `v2`;
    - `republished_feed(v1_feed(), now=…)` → `legacy`.
  - **`test_every_required_field_is_checked`:** one page-side loop. For every object schema
    reachable from each root (top level, `$defs`, and the inline objects such as
    `sourceHealth.download.pages`), take its first instance in the fixture document. Then, for
    every `required` key of that schema:
    - (a) deleting the key gives a problem whose text contains the key and the instance's pointer;
    - (b) replacing its value with a value of the wrong type gives a problem. The wrong value is
      `5` when the field's schema accepts some string, and `"x"` otherwise.

    - **Covering every object:** the fixture pair has no acknowledgement (errata). So the test first
      adds one to copies of both documents:
      - IPU's `acknowledged` gets
        `{"code": "unparsed_relevant", "until": "2026-11-01T00:00:00Z", "stage": "parse", "year": null, "page": null}`;
      - the status's `acknowledged` gets the same entry with `"source": "ipu"`.
    - The Python side lists the (pointer, key) pairs from the schema and the documents, and asserts
      that the JS reported every pair. Both documents are covered. The test fails if any object
      schema still has no instance.
  - **`test_every_schema_keyword_is_handled`:**
    - Every key used as a schema keyword in both files (the property names under `properties` and
      `$defs` excluded) is in `ENFORCED_KEYWORDS + IGNORED_KEYWORDS`.
    - `IGNORED_KEYWORDS` is exactly the six above.
    - Every `additionalProperties` value is either `false` or an object.
  - **`test_patterns_read_dollar_as_the_end_of_input`** (F1). Each of these gives a problem:
    - the feed's `generated_at` set to `"2026-10-19T12:00:00Z\n"`;
    - the status's `attempt_at` set to the same value;
    - the first October card's `date` with `"\n"` appended.
  - **`test_timestamps_and_dates_must_be_real`** (P130, review item). Each edit of a copy gives a
    problem that starts with the edited field's pointer, and the edited feed has the format shown.
    A nullable field fails through `anyOf`, so the text of the problem is not pinned. For
    `generated_at` (not nullable), the problem is exactly `/generated_at: not a real timestamp`.
    The edits:
    - the feed's `generated_at` = "2026-02-30T00:00:00Z" (`invalid`: the legacy check also reads it);
    - its `published_at` = "2026-10-19T24:00:00Z" (`invalid`: `legacy_feed_problems` also reads
      `published_at` when present, `validate.py:406-408`);
    - the first child source's `fetched_at` = "2026-10-19T12:60:00Z" (`update_needed`);
    - the first October card's `date` = "2026-02-30" (`invalid`: the legacy card check also reads it);
    - the status's `attempt_at` = "2026-02-30T00:00:00Z" (`statusProblems` gives the problem).
  - **`test_limits_are_not_enforced_on_the_client`** (P130). Each of these is still `v2` with no
    problems:
    - an extra top-level key `"future": 1`;
    - a 301-character `source_health[0].reasons[0].text`;
    - 501 attention items (the first item repeated).
  - **`test_versions_are_dispatched`** (S5-T03):

    | Document | Format |
    |---|---|
    | the feed | v2 |
    | the v1 feed | legacy |
    | the feed with `schema_version` 3 | update_needed |
    | the feed with `schema_version` "2" | update_needed |
    | the feed without `source_health` | update_needed |
    | the feed without `months` | invalid |
    | the v1 feed without `months` | invalid |
    | `[]`, `null`, `"x"` | invalid |
    | the v1 feed with `schema_version` 1 | update_needed |

  - **`test_legacy_checks_match_the_producer`.** For each row, `legacyProblems(doc) != []` exactly
    when `elections_calendar.validate.legacy_feed_problems(bytes, wall_clock=NOW) != ()`. Each row
    edits the v1 feed:
    - delete `generated_at`; `generated_at` = "x"; `generated_at` = "2026-10-16T00:02:31Z\n";
    - `current_month` = "2026-1"; `errors` = "x"; `months` = [];
    - a `months` key "2026-1";
    - a `months` value `[5]`;
    - a card with `date` "2026-02-30", `country` "", `type` 5, or `status` "Held\n";
    - a card with `sources` [{"name": 5, "link": "x"}];
    - a card whose `source_names` differ from its sources' names, or whose `links` differ from its
      sources' links;
    - `republished_from_sha256` = "ABC";
    - the unedited feed (no problems on either side).

    The producer-only rows (an unexpected key, a time ahead of the clock) are listed in a comment
    as excluded.
  - **`test_status_validation`:**
    - the artifact status gives `[]`;
    - without `serving_feed_sha256`, or with `outcome` "banana", it gives a problem;
    - with an extra key `"future": 1` it gives `[]`;
    - with `sources[0].source` "nowhere" it gives a problem.
  - **`test_schema_copies_match`** (`test_extension_files.py`, no browser):
    `extension/schemas/<name>` is byte-equal to `schemas/<name>` for both files.
  - *Mutations:*
    - `required` checking stops after the first missing key, or skips `$defs` objects reached
      through `items`;
    - `ENFORCED_KEYWORDS` without `minItems`;
    - `pattern` built with the `m` flag;
    - `additionalProperties: false` enforced;
    - `feedFormat` returns `invalid` for `schema_version` 3;
    - `legacyProblems` skips the `links` comparison;
    - `statusProblems` ignores `enum`;
    - `REAL.timestamp` accepts any string (for `test_timestamps_and_dates_must_be_real`);
    - change one byte in `extension/schemas/status-v1.schema.json`.

- [ ] **Step 2: Run them to see them fail** (module not found).

- [ ] **Step 3: Implement `schema.js`.** `schemaProblems(value, schema, refChecks)` walks the
      value with `root = schema` for `$ref` (`#/$defs/<name>` only). Pointers are JSON pointers
      (`/months/2026-10/0/date`).
  - **`refChecks`:** after a value passes `$ref: "#/$defs/<name>"` with no problem, it runs
    `refChecks[name]` when there is one. `false` gives `<p>: not a real <name>`.
  - **`type`:** `object` is a non-null, non-array object; `integer` is `Number.isInteger`; plus
    `array`, `string`, `number`, `boolean`, `null`. A failure reads `<p>: expected <type>`.
  - **`required`:** `<p>: missing <key>` for each missing own key.
  - **`properties`:** validate each present key.
  - **`additionalProperties`:** a schema validates every key not in `properties`; `false` is
    ignored.
  - **`propertyNames`:** validate each key as a string.
  - **`items`:** validate each element.
  - **`enum`/`const`:** strict equality. A failure reads `<p>: not an allowed value`.
  - **`pattern`:** `new RegExp(pattern, "u").test(s)`. A failure reads
    `<p>: does not match <pattern>`.
  - **`anyOf`:** passes when any branch has no problems. Otherwise it reports `<p>: matches none of
    the allowed forms`.
  - **`minimum`, `minItems`:** as JSON Schema defines them.
  - Stop at 20 problems.

- [ ] **Step 4: Implement `validate.js`.**
  - **`legacyProblems`** mirrors `legacy_feed_problems` without its three producer-only rules. Its
    per-card checks are `_legacy`'s; dates use `isCivilDate` and timestamps `parseTimestamp`.
  - **`feedFormat`** follows P130's four formats. Its v2 check is
    `schemaProblems(doc, feedSchema, REAL)`.
  - **`statusProblems`** is `schemaProblems(doc, statusSchema, REAL)`.
  - Copy the two schema files byte for byte. Loading them is Task 4's `load.loadSchemas`, since a
    pure module may not fetch.

- [ ] **Step 5: Run them to see them pass; gates; mutations; commit.**
  `git commit -m "feat(extension): validation of both documents and the format dispatch (Plan 5b-1 Task 3)"`.

### Task 4: Loading, ordering and the module worker (`order.js`, `load.js`, `background.js`; P131, P132, P137; S5-T01, T02, T04, T21, T22, V2-T03, NM-T03, R38, R40)

**Files:**
- Create: `extension/lib/order.js`, `extension/lib/load.js`, `extension/lib/worker.js`,
  `extension/lib/legacy.js`.
- Rewrite: `extension/background.js` (a module), `extension/popup.js` (a module, reading storage).
- Modify: `extension/manifest.json` (`"background": {"service_worker": "background.js", "type": "module"}`),
  `extension/popup.html` (`<body data-state="loading" data-checking="true">`;
  `<script type="module" src="popup.js">`; `#tabResults` renamed `#tabPast`, `data-filter="past"`,
  text "Past"; `#tabAll` gets `class="nav-tab active"` and `#tabUpcoming` loses it).
- Create: `tests/support/extension_page/fakes.js`, `tests/extension/test_order.py`,
  `tests/extension/test_loading.py`.
- Modify: `tests/support/extension.py` (`Ext.popup`, `run_check`, `feed_record`,
  `status_record`, `republication`), `tests/extension/conftest.py` (after launch, the session's `ext` waits up to
  10 s until `check_state_v2` is stored, so its install check cannot leak into the first test), `tests/extension/test_extension_files.py` (`test_permissions_are_v1_0_2s`,
  `test_the_worker_wires_its_handlers`; the pure-module list gains `order.js` and `worker.js`),
  `README.md` (the extension's modules, one paragraph).

**Interfaces:**
- Consumes: Task 2's `dates.parseTimestamp`; Task 3's `feedFormat`, `statusProblems`,
  `MAX_FEED_BYTES`, `MAX_STATUS_BYTES`.
- Produces (`extension/lib/order.js`, pure):

  ```js
  export const WATERMARK_AHEAD_MS  // 86_400_000
  export function orderKey(doc)    // the ISO string of a valid published_at, else of a valid generated_at, else null
  export function accepts(cachedKey, incomingKey, nowMs)   // P132
  export function isLinked(sha256, status)                 // status !== null && status.serving_feed_sha256 === sha256
  export function pickStatus(cached, received, sha256)     // P132's status order (B1)
      // cached: a status record {data, sha256, ...} or null; received: an array of such records
      // (this check's valid statuses, in arrival order); sha256: the kept feed's digest.
      // Returns the chosen record (the cached object itself when it wins) or null.
  ```

  Produces (`extension/lib/load.js`):

  ```js
  export const KEYS  // {feed: "elections_cache_v2", status: "status_cache", check: "check_state_v2"}
  export const CHECK_INTERVAL_MS   // 1_800_000
  export const REQUEST_TIMEOUT_MS  // 30_000
  export function due(checkState, nowMs)
      // false only when ok_at is a finite number and 0 <= nowMs - ok_at < CHECK_INTERVAL_MS;
      // true otherwise (no state, a non-number, NaN or Infinity, an ok_at in the future)
  export async function sha256Hex(bytes)   // lowercase hex of crypto.subtle.digest("SHA-256")
  export function storedFeed(record, schemas)    // the record when valid by P131 (B3), else null
  export function storedStatus(record, schemas)  // the record when valid by P131, else null
  export async function loadSchemas(getURL) // {feed, status}: fetch(getURL("schemas/<name>")) and parse both
  export async function check(deps)        // {ok: true, changed: boolean} | {ok: false, error: string}
  // deps: {feedUrl, statusUrl, fetchBytes(url) -> Promise<Uint8Array> (rejects with Error("HTTP <n>") or a TypeError),
  //        get(keys) -> Promise<object>, set(items) -> Promise<void>, now() -> number, schemas: {feed, status},
  //        timeoutMs: number}   // background.js passes REQUEST_TIMEOUT_MS; tests pass e.g. 50
  ```

  Produces (`extension/lib/worker.js`, pure: the event routing, so it can be tested without
  waiting for Chrome's events):

  ```js
  export const ALARM_NAME  // "elections-refresh"
  export function handlers({ runCheck, ensureAlarm, isDue, openHelp })
  // -> {installed(details), startup(), alarm(alarm), message(msg)}, each returning a promise:
  //   installed: openHelp() when details.reason === "install"; then ensureAlarm(); then runCheck()
  //   startup:   ensureAlarm(); then runCheck()
  //   alarm:     for alarm.name === ALARM_NAME only: runCheck(); then ensureAlarm()
  //   message:   for msg.type === "CHECK" only: ensureAlarm(); then runCheck() when msg.force or
  //              await isDue(), else {ok: true, changed: false, skipped: true}; any other message: undefined
  ```

  **The stored records:**
  - `elections_cache_v2`: `{data, sha256, order_key, format, received_at}`. `format` is `v2`,
    `legacy` or `update_needed`; `received_at` is in ms.
  - `status_cache`: `{data, sha256, received_at}`. `sha256` is the digest of the status bytes as
    received, so an identical status is recognised by value.
  - `check_state_v2`: `{ok_at, failed_at, error}`. The two times are ms or null; `error` is a
    string or null.

  **Messages:** `{type: "CHECK", force: boolean}`. The reply is `check`'s result, or
  `{ok: true, changed: false, skipped: true}` when the check is not due.

  Produces (`extension/lib/legacy.js`, DOM): `export function renderLegacy(doc, { pinned })`.
  This is v1.0.2's `applyDataToUI`, `renderCurrentMonth` and `buildCard`, moved unchanged except
  for three things:
  - it takes the document;
  - its tab filters read `upcoming`, `past` (status `Held`) and `all`;
  - it keeps v1.0.2's footer text until Task 5 moves the footer to `health.js`.

  The test side gains:
  - `Ext.popup(*, now: str | None = PAGE_NOW) -> Page`: it opens `popup.html` and waits for
    `document.body.dataset.state !== "loading"` and `document.body.dataset.checking === "false"`.
    `popup.html`'s `<body>` starts with `data-state="loading" data-checking="true"`, so the wait
    cannot pass before the first check has replied;
  - `feed_record(feed: bytes, *, fmt: str = "v2", received_at: int = 0) -> dict[str, Any]` and
    `status_record(status: bytes) -> dict[str, Any]`: valid stored records for `Ext.seed`. The
    digest and `order_key` are computed in Python, by P132's rule;
  - `run_check(lab, *, feed, status, stored, now, set_fails=None, timeout_ms=50) -> dict`: it runs
    `fakes.runCheck` and returns `{result, stored, log}`. `feed` and `status` are lists of
    responses in `Served.set`'s forms (`"hang"` is answered by the deadline). Each request takes
    the next response, and the last repeats. Bytes travel as base64.

- [ ] **Step 1: Write the pure tests** (`tests/extension/test_order.py`):
  - **`test_order_keys`:**

    | Document | Key |
    |---|---|
    | the artifact feed | "2026-10-19T12:00:00Z" (`published_at`) |
    | the v1 feed | its `generated_at` |
    | the republished v1 | its `published_at` |
    | `published_at` "x" | `generated_at` |
    | both invalid | null |
    | not an object | null |

  - **`test_rollback_ordering`** (V2-T03; `accepts(cached, incoming, now)` with the spec's dates):

    | Cached | Incoming | Now | Accepts |
    |---|---|---|---|
    | "2026-10-16T12:00:00Z" (the republication) | "2026-10-15T02:00:00Z" (a delayed v1) | 2026-10-17T12:00Z | false |
    | same | "2026-10-17T00:02:00Z" (v1 after the revert) | same | true |
    | "2026-10-19T12:00:00Z" | "2026-10-20T00:02:00Z" (v2 → v2) | 2026-10-20T01:00Z | true |
    | same | same (equal) | same | false |
    | null | "2026-10-19T12:00:00Z" | any | true |
    | "2026-10-19T12:00:01Z" | "2026-10-18T00:00:00Z" | 2026-10-18T12:00:00Z | true (cached more than 1 day ahead) |
    | "2026-10-19T12:00:00Z" | "2026-10-18T00:00:00Z" | 2026-10-18T12:00:00Z | false (exactly 1 day) |
    | "2026-10-19T12:00:00Z" | null | any | false |

  - **`test_status_selection`** (B1; `pickStatus`, kept feed digest D). In the table:
    - `S(X, outcome, hh)` is a status record that serves digest X, with that outcome and
      `attempt_at` 2026-10-19Thh:00:00Z, and a digest of its own;
    - "same bytes" is a record with the cached one's digest.

    | Cached | Received | Result |
    |---|---|---|
    | null | [S(D, published, 00)] | the received one |
    | S(D, validation_failed, 06) | [S(D, published, 00)] | the cached (an older success never erases a newer failure) |
    | S(D, validation_failed, 06) | [S(D, published, 12)] | the received (a newer recovery) |
    | S(D, published, 00) | [S(D, validation_failed, 06)] | the received (a newer failure, same feed) |
    | S(D, published, 06) | [S(D, validation_failed, 06)] | the received (a tie: the failure wins) |
    | S(D, validation_failed, 06) | [S(D, published, 06)] | the cached (a tie: the failure wins) |
    | S(D, published, 06) | [S(D, published, 06), different bytes] | the cached (a tie: no flapping) |
    | S(D, published, 06) | [same bytes] | the cached object itself |
    | S(D, published, 00) | [S(E, published, 12)] | the cached (only it describes D) |
    | S(E, published, 00) | [S(F, published, 12)] | the received (neither describes D: the latest) |
    | S(E, published, 12) | [S(F, published, 00)] | the cached (neither describes D: the latest) |
    | S(E, published, 00) | [S(E, published, 06), S(D, published, 03)] | the second received (the only one describing D) |
    | S(D, published, 00) | [] | the cached |
    | null | [] | null |

  - **`test_due`:**
    - no state, true;
    - `ok_at` = now − 1,799,999, false;
    - `ok_at` = now − 1,800,000, true;
    - `ok_at` "x", `NaN` or `Infinity`, true;
    - `ok_at` = now + 1 (in the future: the clock went back), true;
    - `failed_at` later than `ok_at` changes nothing.
  - *Mutations:*
    - `orderKey` reads `generated_at` first;
    - `accepts` uses `>=` for the watermark (or `>=` for the incoming key);
    - `pickStatus` ignores `attempt_at` among statuses that describe the feed (revision 1's rule);
    - `pickStatus` lets the cached one win every tie;
    - `due` uses `>` for the interval;
    - `due` accepts an `ok_at` in the future.

- [ ] **Step 2: Write the check tests with fakes** (`tests/extension/test_loading.py`; `fakes.js`
      builds an in-memory storage, a scripted fetch that logs `"elections.json"`/`"status.json"`,
      and calls `load.check`). F = the artifact feed, S = its status (links to F), S′ = a status
      whose `serving_feed_sha256` is 64 zeros, NOW = PAGE_NOW in ms:
  - **`test_check_links_and_refetches_once`** (S5-T01):
    - (a) F, S → log `[elections.json, status.json]`; the stored feed's `sha256` is F's digest;
      `order_key` "2026-10-19T12:00:00Z", `format` "v2"; the stored status is S; `changed` true;
    - (b) F, then S′ then S → log `[elections.json, status.json, elections.json, status.json]`,
      and the stored status is S;
    - (c) F, S′ always → the same four requests, and the stored status is S′ (nothing linked was
      cached);
    - (d) the same as (c), with S cached beside F → the stored status stays S;
    - (e) a status 404, or a status of `b"{"`, or a status without `outcome` → the feed is stored,
      the status is unchanged (null), and `ok` is true.
  - **`test_check_orders_responses`** (S5-T02):
    - Three checks in a row, sharing storage, receive feeds with keys t2, t1 and t3:
      F with `published_at` and `generated_at` set to 2026-10-19T12:00Z, 2026-10-18T12:00Z and
      2026-10-20T12:00Z, each with a status that links to it.
    - The stored keys after each check are t2, t2 and t3; `changed` is true, false and true; the
      stored status after check 2 is still t2's.
    - A fourth check with t3's bytes again gives `changed` false (both records equal by digest),
      and only `check_state_v2` is rewritten.
  - **`test_a_retry_keeps_the_best_feed`** (B2). F1 and F2 are F with keys t1 < t2. S1 and S2 link
    to them, and S′ links to neither. Their `attempt_at`s are ordered S′ < S1 < S2. Each row gives
    the stored feed, the stored status, and whether the two link (`isLinked`):

    | Cache | Round 1 (feed, status) | Round 2 (feed, status) | Stored feed | Stored status | Linked |
    |---|---|---|---|---|---|
    | none | F2, S′ | F1, S1 | F2 | S1 (the latest; neither describes F2) | false |
    | F0 (t0 < t1) | F2, S′ | 503, S′ | F2 | S′ | false |
    | none | F2, S′ | a network failure, S2 | F2 | S2 | true |
    | none | F1, S′ | F2, S2 | F2 (a newer second round wins) | S2 | true |
    | F2 | F2, S′ | F2, `"hang"` | F2 (unchanged) | S′ | false |

    `ok` is true in every row. The check record has `ok_at` = NOW and no error: a failed second
    round after a usable first one is not a failed check.
  - **`test_cached_records_are_validated`** (B3). The cache holds a record, and F (key
    2026-10-19T12:00Z) and S are served at NOW:

    | Cached `elections_cache_v2` | Result |
    |---|---|
    | F's record with `months` deleted from `data`, `order_key` "2026-10-19T13:00:00Z" | F stored (the cached record counted as none) |
    | F's record with `format` "legacy" | F stored |
    | F's record with `order_key` "2026-10-19T13:00:00Z" (it does not match its document) | F stored |
    | F's record with `sha256` "x" or `received_at` "x" | F stored |
    | a valid record of F with key 2026-10-19T13:00Z (published_at and generated_at edited) | that record kept: the control |

    And `status_cache` with `data` lacking `outcome` counts as no cached status.
  - **`test_check_has_a_deadline`** (review item). With `timeout_ms` 50:
    - a feed `"hang"` gives `{ok: false, error: "elections.json: no response in time"}`;
    - a status `"hang"` with F served stores F and no status;
    - a second `run_check` on the same storage then succeeds.
  - **`test_check_records_failures_and_keeps_the_cache`** (S5-T22, S5-T03). With F cached and
    `check_state_v2` `{ok_at: NOW-1, …}`, each case below gives exactly the error shown, leaves the
    stored feed and status as they were, sets `failed_at` = NOW, and keeps `ok_at`:

    | Feed response | Error |
    |---|---|
    | 503 | `"elections.json: HTTP 503"` |
    | a network failure | `"elections.json: the request failed"` |
    | `b"\xff"` | `"elections.json: not UTF-8 JSON"` |
    | `b"[]"` | starts `"elections.json: unreadable feed: "` |
    | 4,000,001 bytes of spaces | `"elections.json: 4000001 bytes is over the limit of 4000000"` |

  - **`test_a_failed_write_keeps_the_previous_pair`** (S5-T21). F(t2) and S(t2) are cached, and
    F(t3) and S(t3) are served. The fake `set` rejects with `Error("QUOTA_BYTES quota exceeded")`
    any call that includes `elections_cache_v2`, as a quota does for the large record, and applies
    every other call.
    - The result is `{ok: false, error: "could not save the new data: QUOTA_BYTES quota exceeded"}`.
    - The stored feed and status are still t2's.
  - **`test_recovery_reaches_the_client`** (NM-T03, R40). The bytes are built in Python, with times
    relative to `datetime.now(UTC)` rounded down to the second (= N):
    - D: the artifact feed, with `generated_at` = `published_at` = N − 2 days;
    - O: the artifact feed, with `generated_at` = `published_at` = N − 5 days;
    - R = `republished_feed(O, now=N − 1 day)`, and RS its status, built exactly as
      `recovery.republish` (`recovery.py:167-176`) builds it:
      `stored_json(status_doc(attempt=Attempt(N − 1 day, "local", "republish", "0" * 40), outcome="republished", severity="ok", sources=(), run_reasons=(), serving=R))`.
      Put this builder in `tests/support/extension.py` as `republication(original: bytes, *, now: datetime) -> tuple[bytes, bytes]`,
      so Task 5 can reuse it;
    - V: `v1_feed()` with `generated_at` = N − 12 hours.

    The steps, with now = N:
    1. D cached, R and RS served → R is stored with format `v2`, and the status RS links.
    2. D served again, a delayed response → nothing changes (`changed` false).
    3. V served with RS → V is stored with format `legacy`, `order_key` = V's `generated_at`. The
       status stays RS, and it does not link to V (`isLinked` false).
  - *Mutations:*
    - `check` refetches only the status (b's log has 3 entries);
    - `check` writes the feed before reading the status (a second `set`);
    - `check` drops the incoming feed's `accepts` test;
    - `check` writes `failed_at` without keeping `ok_at`;
    - `check` compares status records by object identity (the fourth check of
      `test_check_orders_responses` gives `changed` true);
    - `check` writes the status record in its own `set`, before the feed's
      (`test_a_failed_write_keeps_the_previous_pair`: the status becomes t3's);
    - `check` compares round 2's feed with the cached record instead of the best so far;
    - a round-2 feed failure ends the check;
    - `storedFeed` checks the envelope only;
    - the deadline is not applied to the status request.

- [ ] **Step 3: Write the worker tests** (real Chromium, `ext` or `fresh_ext`):
  - **`test_the_worker_checks_and_the_popup_shows_the_result`** (S5-T01, R38):
    - Serve F and S, then open `ext.popup()`.
    - `ext.served.log == ["elections.json", "status.json"]`.
    - `ext.storage()["elections_cache_v2"]["sha256"]` is F's digest.
    - The popup shows 30 `.election-item` cards (the legacy renderer reads the v2 feed's legacy
      fields), `#tabAll` has class `active` and the other tabs do not, and `body[data-state]` is
      `ready`.
  - **`test_two_checks_at_once_fetch_once`** (S5-T02): from a page,
    `Promise.all([send({type: "CHECK", force: true}), send({type: "CHECK", force: true})])` makes
    one `elections.json` request.
  - **`test_the_alarm_survives_restart_and_worker_termination`** (S5-T04, `fresh_ext`):
    1. After install, the alarm `elections-refresh` exists with `periodInMinutes` 60.
    2. `chrome.alarms.clearAll()`, then `stop_worker()`, then open the popup (F seeded with
       `feed_record`): the alarm exists again, and the popup shows 30 cards.
    3. `clearAll()`, then `relaunch()`: the alarm exists again. This relaunch fires `onInstalled`
       (`install`), not `onStartup` (probe5); the test's comment says so.
  - **`test_worker_handlers`** (S5-T04, in the lab with logging fakes; `isDue` returns a set
    value). Each row gives exactly this call order and result:

    | Call | Calls | Result |
    |---|---|---|
    | `installed({reason: "install"})` | openHelp, ensureAlarm, runCheck | — |
    | `installed({reason: "update"})` | ensureAlarm, runCheck | — |
    | `startup()` | ensureAlarm, runCheck | — |
    | `alarm({name: "elections-refresh"})` | runCheck, ensureAlarm | — |
    | `alarm({name: "other"})` | none | — |
    | `message({type: "CHECK", force: false})`, not due | ensureAlarm, isDue | `{ok: true, changed: false, skipped: true}` |
    | `message({type: "CHECK", force: false})`, due | ensureAlarm, isDue, runCheck | runCheck's value |
    | `message({type: "CHECK", force: true})` | ensureAlarm, runCheck | runCheck's value |
    | `message({type: "FETCH_DATA"})` | none | `undefined` |

    An `ensureAlarm` that only logs after its promise settles proves the order (each call waits
    for the one before).
  - **`test_the_worker_wires_its_handlers`** (`test_extension_files.py`, no browser):
    - `background.js` imports `handlers` from `./lib/worker.js`.
    - It registers exactly one listener on each of `chrome.runtime.onInstalled`,
      `chrome.runtime.onStartup`, `chrome.alarms.onAlarm` and `chrome.runtime.onMessage`. Count
      the `.addListener(` occurrences on each.
    - It contains `const DATA_URL = ` exactly once.
  - **`test_a_failed_write_in_the_worker_keeps_the_cache`** (S5-T21, the worker's handling; on
    `fresh_ext`, so the patched API never reaches another test):
    - Seed F(t2) as a valid record; in the worker,
      `chrome.storage.local.set = () => Promise.reject(new Error("QUOTA_BYTES quota exceeded"))`.
    - Serve F(t3), then send CHECK force: the reply's `error` is
      `"could not save the new data: QUOTA_BYTES quota exceeded"`.
    - The stored key is still t2.
    - `stop_worker()` (the next worker has the real API), then CHECK force stores t3.
  - **`test_a_real_quota_failure_keeps_the_previous_pair`** (S5-T21, Chrome's own rejection,
    probe6; `fresh_ext`):
    - Seed F(t2) and S(t2).
    - Fill storage with a `filler` string key so that `QUOTA_BYTES − getBytesInUse(null)` is
      100,000 bytes. Compute the length in the page, as probe6 does.
    - Serve F(t3) with an extra top-level key holding 400,000 characters (P130 ignores it), and
      S(t3). CHECK force replies `ok: false` with an `error` that starts
      `"could not save the new data: "` and contains `quota`. Chrome's text, measured:
      `Resource::kQuotaBytes quota exceeded`.
    - The feed and status records equal the seeded ones.
    - Remove `filler`, then CHECK force stores t3.
  - **`test_offline_with_and_without_a_cache`** (S5-T22). Every response fails (`None`):
    - **With F seeded** and `check_state_v2.ok_at` = the real now − 2 h (an expired cache): the
      popup makes a request (the log holds `elections.json`), shows 30 cards, and keeps
      `#stateError` hidden.
    - **Without a cache:** `#stateError` is visible, `#errorMsg` is
      `Could not load data: elections.json: the request failed`, and `body[data-state]` is `error`.
    - **Then F and S are served and Retry is clicked:** the popup reaches `ready` with 30 cards. A
      failed check has released the single flight.
  - **`test_the_v1_cache_and_pins_are_left_alone`:**
    - Seed `elections_cache` `{ts: 1, data: <v1 doc>}`, `pinned_countries` `["Brazil"]` and
      `selected_countries` `["Brazil"]`.
    - After a check and a popup open, the three values are equal to the seeded ones.
  - **`test_a_corrupt_cache_is_ignored`** (Review Focus 4, B3). Three seeds:
    - `elections_cache_v2` = `"garbage"`;
    - `{"data": 5, "sha256": "x"}`;
    - a well-formed `feed_record` of F with `months` deleted from `data` and `order_key` = the real
      now + 1 h (within the watermark, so only validation can stop it).

    For each, the popup reaches `ready` or `error` with no `pageerror`. With F and S served,
    Refresh then stores F's valid record, and the popup shows 30 cards.
  - **`test_a_check_cut_short_leaves_the_previous_pair`** (Review Focus 4):
    - Seed F(t2) and S(t2). Serve `"hang"` for `elections.json`, then send CHECK force without
      awaiting it, wait until the log holds `elections.json`, then `stop_worker()`.
    - The storage equals the seeded values.
    - With F(t3) and S(t3) served, the next CHECK stores t3.
  - **`test_permissions_are_v1_0_2s`** (`test_extension_files.py`, no browser):
    - `extension/manifest.json` equals `V1_EXTENSION/manifest.json` with one change,
      `background.type` = `"module"`. Compare the parsed JSON after removing that key.
    - It has no `key` and no `content_security_policy`.
  - *Mutations:*
    - `handlers.message` skips `ensureAlarm` (the restart test's step 2);
    - `runCheck` skips the single flight;
    - `handlers.alarm` does not call `ensureAlarm`;
    - `handlers.installed` opens help on `update` too;
    - `background.js` drops its `onStartup` registration;
    - the popup shows `stateError` when a cache exists;
    - `check` treats a rejected write as success (the real-quota test);
    - `storedFeed` accepts any object;
    - `runCheck` releases its single flight only on success (the Retry step of the offline test);
    - `popup.html` keeps `active` on `#tabUpcoming`;
    - `manifest.json` gains `"tabs"`.

- [ ] **Step 4: Run them to see them fail.**

- [ ] **Step 5: Implement `order.js`** (P132 as written, `pickStatus` included), **and
      `load.check`** (P131). The algorithm, with `t = deps.now()` read once:
  1. **Read.** Read `KEYS.feed`, `KEYS.status` and `KEYS.check`.
     `cached = storedFeed(<stored feed>, deps.schemas)` and
     `cachedStatus = storedStatus(<stored status>, deps.schemas)`.
     - **`storedFeed`** returns the record only when all of these hold:
       - it is an object;
       - `feedFormat(record.data)` is not `invalid` and equals `record.format`;
       - `orderKey(record.data) === record.order_key`;
       - `sha256` matches `^[0-9a-f]{64}$`;
       - `received_at` is a finite number.
     - **`storedStatus`** returns the record only when `statusProblems(record.data)` is empty and
       `sha256` is hex.
  2. **Fetch one document** (`get(url, limit)`, used for both):
     - it races `fetchBytes` against `deps.timeoutMs`;
     - it refuses more than `limit` bytes;
     - it decodes with `new TextDecoder("utf-8", {fatal: true})` and `JSON.parse`;
     - it digests with `sha256Hex`.

     For the feed, every failure is an error, verbatim:
     - `elections.json: HTTP <n>` (an `HTTP <n>` rejection);
     - `elections.json: the request failed` (any other rejection);
     - `elections.json: no response in time`;
     - `elections.json: <n> bytes is over the limit of 4000000`;
     - `elections.json: not UTF-8 JSON`;
     - `elections.json: unreadable feed: <first problem>` (`feedFormat` gives `invalid`).

     For the status, any failure is "no status": a rejection, the deadline, more than
     `MAX_STATUS_BYTES`, bad UTF-8 or JSON, or `statusProblems`.
  3. **Round 1.**
     - The feed is fetched. Its error ends the check (step 6).
     - `incoming = {data, sha256, order_key: orderKey(data), format, received_at: t}`.
     - `best = incoming` when `accepts(cached?.order_key ?? null, incoming.order_key, t)`, else
       `cached`.
     - The status is fetched, and if valid, appended to `received` as
       `{data, sha256, received_at: t}`.
  4. **Round 2**, only when round 1's status is valid and does not link to `best.sha256`:
     - The feed is fetched again. A failure is ignored: round 1's `best` stands (B2).
     - A valid feed replaces `best` when `accepts(best?.order_key ?? null, its key, t)`.
     - The status is fetched and appended as in round 1.
  5. **Select and write once.**
     - `status = pickStatus(cachedStatus, received, best.sha256)`.
     - The feed changed when `best.sha256 !== cached?.sha256`. The status changed when
       `status?.sha256 !== cachedStatus?.sha256`.
     - One `set` holds `KEYS.feed` = `best` when the feed changed, `KEYS.status` = `status` when it
       changed, and always `KEYS.check` = `{ok_at: t, failed_at: null, error: null}`.
     - If it resolves, return `{ok: true, changed: <feed changed || status changed>}`.
  6. **A failed check:**
     - a round-1 feed error, or a rejected write (`error` = `could not save the new data: <message>`);
     - one more `set` writes only `KEYS.check` = `{ok_at: <previous ok_at or null>, failed_at: t, error}`,
       and a failure of that write is ignored;
     - return `{ok: false, error}`.

- [ ] **Step 6: Implement `worker.js` and `background.js`** (a module). `worker.handlers` is the
      table in `test_worker_handlers`. `background.js` holds:
  - **The constants:** `const DATA_URL = "…";` exactly as today, and `STATUS_URL`.
  - **The schemas** come from `loadSchemas(chrome.runtime.getURL)`, loaded once per worker life.
  - **`runCheck()`:** a module-level `running` promise, so one check runs at a time. It is cleared
    in a `finally`, so a failed or timed-out check releases it.
  - **What it passes to `check`:**
    - `fetch(url, {cache: "no-store"})` (a non-2xx status rejects with `Error("HTTP <n>")`);
    - `chrome.storage.local`;
    - `Date.now`;
    - `timeoutMs: REQUEST_TIMEOUT_MS`.
  - **`ensureAlarm()`:** `chrome.alarms.get(ALARM_NAME)`, then `create(ALARM_NAME, {periodInMinutes: 60})`
    when it is missing.
  - **`isDue()`:** `due(<stored check_state_v2>, Date.now())`.
  - **`openHelp()`:** `chrome.tabs.create({url: chrome.runtime.getURL("help.html")})`, as v1.0.2
    does (`background.js:17`; no `tabs` permission is needed for that).
  - **The four listeners** call the matching handler. `onMessage` replies with the handler's
    value when it is not `undefined`, and returns `true` only then (the reply is asynchronous).

- [ ] **Step 7: Implement the popup's loading.** In `popup.js` (a module):
  1. The body starts as `data-state="loading" data-checking="true"` (in `popup.html`).
  2. **Read and render:** read the three keys, `pinned_countries` and the schemas, then run
     `feedFormat` on the cached `data`. When a record is valid and not `invalid`, call
     `renderLegacy(data, {pinned})` (Task 6 sends `v2` to `render.js`) and set `state = "ready"`.
  3. **Check:** set `checking = "true"`, send `{type: "CHECK", force: false}`, then repeat step 2.
     - With no rendered data and `{ok: false}`, `#errorMsg` = `Could not load data: <error>`, and
       `state = "error"`.
     - With no rendered data and `{ok: true}` (nothing stored was valid), `state = "error"` too,
       with `#errorMsg` = `Could not load data: no data yet`.
     - Set `checking = "false"` last, after the reply, a failed `sendMessage` included.
  4. **Refresh and Retry** do step 3 with `force: true`.

  The month and filter state are `renderLegacy`'s, as in v1.0.2.

- [ ] **Step 8: Run the tests to see them pass.** The existing
      `test_served_check_reads_the_extension_url` must still pass unchanged (R38). Then the gates,
      the mutations and the commit:
  `git commit -m "feat(extension): ordered, linked loading in a module worker (Plan 5b-1 Task 4)"`.

### Task 5: The banner, the health panel and the footer (`health.js`; P133; S5-T05, R35, R40)

**Files:**
- Create: `extension/lib/health.js`, `tests/extension/test_banner.py`.
- Modify: `extension/popup.html`, `extension/popup.js`, `extension/styles.css`,
  `extension/lib/legacy.js` (it stops writing the footer),
  `tests/extension/test_extension_files.py` (the pure-module list gains `health.js`;
  `test_no_feed_text_through_inner_html_in_v2_code`).

**Interfaces:**
- Consumes: Task 2's `stamp`, `stampDate`, `parseTimestamp`; Task 4's `isLinked` and the stored
  records.
- Produces (`extension/lib/health.js`, pure):

  ```js
  export const STALE_MS            // 129_600_000 (36 h)
  export const AHEAD_MS            // 600_000 (10 min)
  export const AS_OF_GAP_MS        // 86_400_000 (24 h)
  export function issues(doc)      // {errors: Issue[], warnings: Issue[], acknowledged: Issue[]}
                                   // Issue = {source: name or "Run", code, text, until: ms | null}
  export function bannerState({ format, doc, status, linked, now })
                                   // {level: "red"|"amber"|"grey"|"ok", text, counts: string}
  export function footerState({ doc, check, now })   // {data: string, checked: string}
  export function panelRows({ format, doc, status, linked })
                                   // [{source, severity, lines: string[]}] or [] with a note
  ```

  **The popup DOM** (`popup.html`, after the top bar):

  ```html
  <button class="banner" id="banner" data-level="ok" aria-expanded="false" aria-controls="healthPanel">
    <span id="bannerText"></span> <span id="bannerCounts"></span>
  </button>
  <section class="health-panel hidden" id="healthPanel"><p id="healthNote"></p><ul id="healthList"></ul></section>
  ```

  The footer holds `<span id="footerData"></span>` and `<span id="footerChecked"></span>`.

- [ ] **Step 1: Write the pure tests.** F and S are the artifact pair; G is
      `parseTimestamp(F.generated_at)`.
  - **`test_banner_conditions_in_order`** (`bannerState`). Each row gives `level`, `text` and
    `counts` exactly:

    | Case | Level | Text | Counts |
    |---|---|---|---|
    | F, S, linked, now G + 2 h | amber | "7 warnings" | "7 warnings" |
    | same, one IPU reason set to level error and code `unavailable` | red | "1 source error" | "1 error · 6 warnings" |
    | same, an IPU acknowledgement of that reason added | amber | "6 warnings" | "6 warnings · 1 acknowledged" |
    | F with every warning acknowledged, now G + 2 h | grey | "7 acknowledged issues: Wikipedia unparsed relevant" | "7 acknowledged" |
    | F with no reasons | ok | "All sources OK" | "" |
    | S with `outcome` validation_failed, linked | red | "The latest update failed its checks — showing the last good data" | "7 warnings" |
    | the same S, not linked | amber | "Current health can't be confirmed for this data" | "7 warnings" |
    | F, no status | amber | "Current health can't be confirmed for this data" | "7 warnings" |
    | F, now G + 36 h + 1 s | red | "Data is 36 hours old — the daily update hasn't arrived" | "7 warnings" |
    | F with `schema_version` 3 (format update_needed), now G + 2 h | amber | "This data is newer than this extension — update the extension" | "" |
    | the v1 feed (legacy), RS not linked, now = its `generated_at` + 2 h | amber | "Current health can't be confirmed for this data" | "" |
    | L = `republished_feed(v1_feed(), …)` (legacy) with its own status, linked (B4), now = L's `generated_at` + 2 h | amber | "Source health isn't available for this data" | "" |
    | L, no status, now = L's `generated_at` + 2 h | amber | "Current health can't be confirmed for this data" | "" |
    | L, linked, now = L's `generated_at` + 37 h | red | "Data is 37 hours old — the daily update hasn't arrived" | "" |
    | L, linked, its status's `outcome` validation_failed | red | "The latest update failed its checks — showing the last good data" | "" |

    - The grey row's text names the first acknowledged issue's source name and its code with `_`
      read as a space.
    - Plurals: "1 warning", "2 warnings", "1 acknowledged issue: …", "2 source errors".
    - The counts list only non-zero parts, in the order errors, warnings, acknowledged, joined by
      " · ".
  - **`test_freshness_thresholds_and_clock_skew`** (S5-T05):
    - now G + 36 h exactly is not stale; G + 36 h + 1 ms is stale.
    - now G − 2 h is not stale, and `footerState(...).data` ends with
      " (ahead of this computer's clock)".
    - now G − 9 min has no marker; G − 11 min has it.
    - now G + 40 h gives "Data is 40 hours old — the daily update hasn't arrived".
  - **`test_the_footer`** (`footerState`, with `stamp` read in UTC):

    | Case | `data` / `checked` |
    |---|---|
    | F (data_as_of 69 h older) | `data` "Data as of 19 Oct 2026, 12:00 · oldest source data 16 Oct 2026, 14:39" |
    | F with data_as_of = G − 24 h exactly | `data` "Data as of 19 Oct 2026, 12:00" |
    | F with data_as_of null | `data` "Data as of 19 Oct 2026, 12:00" |
    | the v1 feed (`generated_at` 2026-10-16T00:02:31Z, no `data_as_of`) | `data` "Data as of 16 Oct 2026, 00:02" |
    | check {ok_at: 19 Oct 13:58Z, failed_at: null} | `checked` "Checked 19 Oct 2026, 13:58" |
    | check {ok_at: 13:58Z, failed_at: 13:59Z, error: "elections.json: HTTP 503"} | `checked` "Checked 19 Oct 2026, 13:58 · couldn't check at 19 Oct 2026, 13:59: elections.json: HTTP 503" |
    | check {ok_at: null, failed_at: 13:59Z, error: "elections.json: HTTP 503"} | `checked` "Couldn't check at 19 Oct 2026, 13:59: elections.json: HTTP 503" |
    | no check state | `checked` "Not checked yet" |
  - **`test_acknowledged_issues_describe_the_real_condition`** (`issues`):
    - an IPU reason `unavailable` (error), with an acknowledgement of the same code, stage, year
      and page, is in `acknowledged` with its `until` and the reason's own text;
    - the same reason twice with one acknowledgement gives one acknowledged and one error
      (one-to-one);
    - an acknowledgement with another `page` acknowledges nothing;
    - info reasons are in no list.
  - *Mutations:*
    - acknowledged ranked above warnings;
    - stale at `>=`;
    - the ahead check missing;
    - the data_as_of gap at `>=`;
    - acknowledgement matched on code alone;
    - row 2 read without `linked`;
    - row 6 removed (the linked-legacy row then gives "All sources OK").

- [ ] **Step 2: Write the popup tests** (real Chromium):
  - **`test_a_newer_failure_is_not_erased`** (B1, end to end):
    - SF = S with `outcome` "validation_failed" and `attempt_at` = S's + 6 h. It still serves F's
      digest, as the producer's failed attempt does (`pipeline.py:679-685`).
    - Seed `feed_record(F)` and `status_record(SF)`, with no check state, so a check is due.
    - Serve F and S (an older `published` attempt about the same feed).
    - The popup's `#bannerText` is "The latest update failed its checks — showing the last good
      data", and `status_cache` still holds SF.
    - Then serve S2 = S with `attempt_at` = S's + 12 h and click Refresh: `#bannerText` becomes
      "7 warnings".
  - **`test_banner_and_panel_in_the_popup`:**
    - Serve F and S; at `PAGE_NOW`, `#banner[data-level]` is `amber`, and `#bannerText` is
      "7 warnings".
    - **The panel:** clicking the banner makes `aria-expanded` "true" and shows `#healthPanel`.
      `#healthList > li` has 10 rows. The first has `data-source="latest"` (the status is linked);
      the other nine have the `source_health` keys, in feed order. The `wikipedia` row's text
      contains its two reason texts.
    - **The footer:** `#footerData` is
      "Data as of 19 Oct 2026, 12:00 · oldest source data 16 Oct 2026, 14:39", and
      `#footerChecked` starts with "Checked ".
  - **`test_rollback_v1_feed_shows_the_mismatch_banner`** (R40):
    - Seed `elections_cache_v2` with `feed_record(V′, fmt="legacy")`, where V′ is `v1_feed()` with
      `generated_at` = `PAGE_NOW` − 12 h. The popup's clock is the page clock, so this row's times
      are relative to `PAGE_NOW`, not to the real clock.
    - Seed `status_cache` with `status_record` of RS from `republication(<the artifact feed>, now=…)`, and
      `check_state_v2.ok_at` with the real now, so the worker runs no check.
    - The popup shows V′'s 27 October cards, and `#bannerText` is
      "Current health can't be confirmed for this data".
    - `#healthNote` is "Source health isn't available for this data".
  - **`test_an_unknown_version_shows_the_update_banner`** (S5-T03):
    - Seed F with `schema_version` 3, format `update_needed`, and no check due.
    - 30 legacy cards, and `#bannerText` is
      "This data is newer than this extension — update the extension".
  - **`test_health_text_is_inserted_as_text`** (R35, Review Focus 5):
    - F with `source_health[2].reasons[0].text` = `'<img src=x onerror="document.title=1">'`.
    - After opening the panel, the Wikipedia row's text contains that string, and
      `#healthPanel img` counts 0.
  - **`test_no_feed_text_through_inner_html_in_v2_code`** (static): `health.js` and `popup.js`
    contain no `innerHTML`, `outerHTML`, `insertAdjacentHTML` or `document.write` (`legacy.js` is
    exempt until R52).
  - *Mutations:*
    - the panel built with `innerHTML`;
    - `#healthNote` not set for `legacy`;
    - the banner's `aria-expanded` never set;
    - the popup passes `linked: true` always;
    - `order.pickStatus` takes the received status whenever both describe the feed (revision 1's
      rule; `test_a_newer_failure_is_not_erased`).

- [ ] **Step 3: Run them to see them fail.**

- [ ] **Step 4: Implement `health.js`** (P133).
  - **`issues(doc)`:**
    - For each `source_health` entry, and for `run.reasons` as source "Run": every reason of level
      `error` or `warning`.
    - It is acknowledged when an unused entry of that source's `acknowledged[]` has the same code,
      stage, year and page; that entry is then used.
    - For `legacy` and `update_needed` documents, `issues` is not called (no `source_health`).
  - **`bannerState`:** the first true row of P133's nine.
    - **Texts:**
      - "Data is {floor(hours)} hours old — the daily update hasn't arrived";
      - "The latest update failed its checks — showing the last good data";
      - "{n} source error(s)";
      - "This data is newer than this extension — update the extension";
      - "Current health can't be confirmed for this data";
      - "Source health isn't available for this data";
      - "{n} warning(s)";
      - "{n} acknowledged issue(s): {source} {code with _ as space}";
      - "All sources OK" (a `v2` feed only).
    - **Levels:** red, red, red, amber, amber, amber, amber, grey, ok.
  - **`footerState`:**
    - "Data as of {stamp(G)}", plus " · oldest source data {stamp(data_as_of)}" when
      `G − data_as_of > AS_OF_GAP_MS`, plus " (ahead of this computer's clock)" when
      `G − now > AHEAD_MS`;
    - "Checked {stamp(ok_at)}", plus " · couldn't check at {stamp(failed_at)}: {error}" when
      `failed_at > ok_at`. With no `ok_at` but a failure: "Couldn't check at {…}: {error}". With
      neither: "Not checked yet".
  - **`panelRows`:**
    - For `v2`, one row per `source_health` entry: `{source: key, severity, lines}`, where the
      lines are each reason's text, with " (acknowledged until {stampDate(until)})" after an
      acknowledged one.
    - When linked, a first row `{source: "latest", severity: <status severity>, lines: ["Latest attempt {stamp(attempt_at)}: {outcome with _ as space}"]}`.
    - For `legacy` and `update_needed`, `[]`; the popup then sets `#healthNote` to "Source health
      isn't available for this data".

- [ ] **Step 5: Wire the popup.** After each render, set the banner, its counts and level, the
      panel (rendered on expand, `textContent` only) and both footer spans. `now` is `Date.now()`
      in the popup, which the tests' page clock fixes. The banner button toggles the panel and
      `aria-expanded`. The colours go in `styles.css`: `.banner[data-level=red|amber|grey|ok]`.

- [ ] **Step 6: Run them to see them pass; gates; mutations; commit.**
  `git commit -m "feat(extension): the summary banner, health panel and honest footer (Plan 5b-1 Task 5)"`.

### Task 6: One pipeline for tabs, filters and counters; v2 cards (`count.js`, `render.js`; P135; S5-T12–T14)

**Files:**
- Create: `extension/lib/count.js`, `extension/lib/render.js`, `tests/extension/test_counting.py`.
- Modify: `extension/popup.html` (the level filter, `#recordCount`), `extension/popup.js` (a `v2`
  document goes to `render.js`), `extension/styles.css`, `tests/extension/test_extension_files.py` (the pure-module
  list gains `count.js`; the inner-HTML check gains `render.js`), and the Task 4 and 5 popup tests
  whose card counts came from the legacy renderer (`test_the_worker_checks_and_the_popup_shows_the_result`
  and the others reading `.election-item` on a v2 feed). Their numbers stay the same: the v2
  renderer also shows 30 October cards on All.

**Interfaces:**
- Consumes: Task 2's `childLabel`, `cardLabel`, `badge`, `monthName`, `localToday`.
- Produces (`extension/lib/count.js`, pure):

  ```js
  export const TAB_KINDS   // {upcoming: [...P135], past: ["held","past","past_expected"]}
  export function tabsOf(label, card, today)          // Set of "all" | "upcoming" | "past"
  export function view(doc, { month, tab, level, query, pinned, today, now })
      // {cards: [{card, children: [{child, label}], total, label, match}], records, groupings, held}
      // pinned: an array of country names (v1's pinned_countries; empty = no pin filter)
      // match: "" or "{k} matching of {total}" when k < total
  export function recordText(records, groupings)      // "58 election records (incl. 11 groupings)"
  ```

  Produces (`extension/lib/render.js`, DOM, `textContent` only):
  `export function renderV2(doc, { pinned, today, now })`. It owns the month, tab, level and query
  state of a v2 document. Its DOM:
  - `#levelFilter` (a `<select>` in `#filterBar` with options `all` "All", `national`
    "National + unclassified" and `subnational` "Subnational + unclassified");
  - `#recordCount`;
  - the bento labels "Election records" and "Confirmed held", with `#statTotal` and `#statHeld`
    holding the counts as plain numbers;
  - `.election-item[data-group-id]` cards, each holding `.date-badge .day`, `.date-badge .mon`,
    `.election-country`, `.election-type`, `.card-label`, `.card-match` (empty when the card matches
    in full), `.chip-tentative`, `.chip-subnational` and `.card-notes > li`;
  - the tabs set `class="active"` and `aria-selected` on the shown tab only.

  The month navigation walks `doc.window.months` and starts at `doc.current_month`. A month's
  cards follow P138 (`count.view`). Cards open no link (R47).

- [ ] **Step 1: Write the pure tests** (`view` on the artifact feed, today 2026-10-19, now
      PAGE_NOW):
  - **`test_children_are_counted_once`** (S5-T13):
    - Oct, all, all gives 30 cards, records 58, groupings 11, held 8.
    - `recordText(58, 11)` is "58 election records (incl. 11 groupings)". Also:
      `recordText(1, 1)` "1 election record (incl. 1 grouping)", `recordText(2, 0)` "2 election
      records", `recordText(0, 0)` "0 election records".
    - A copy of the feed whose second October card also holds the first card's first child (the
      same `child_id`) still gives records 58.
    - **The held counter** (review item): a copy in which one of October's 8 confirmed children
      also has `status_conflict: true` gives held 7. That child's label is "Possibly postponed —
      sources disagree", so it is not counted as held.
  - **`test_month_rule`** (P138, option B):
    - **A synthetic card**, day precision and `voting_period`, from 2026-12-24 to 2027-02-06, is
      bucketed in 2026-12. It is in December's and January's views, and it is counted once in each.
    - **A synthetic month-precision expected window**, 2026-11-01..2027-01-31, bucketed in 2026-11,
      is in November's, December's and January's views. It is labelled "Expected between November
      and January" in each.
    - **The fixture:**
      - January gives 6 cards and 8 records, Fiji included;
      - December gives 15 cards and 21 records;
      - September, October and November keep the errata's values.
    - **Fiji in January:** its label is still "Scheduled", and its badge is still "24–6" /
      "DEC–FEB".
  - **`test_partial_matches`** (S5-T12):
    - Nov, all, query "county elections" gives one card (United States 2026-11-03) with 1 kept
      child, `total` 59 and `match` "1 matching of 59".
    - Query "COUNTY ELECTIONS" gives the same.
    - Query "United States" keeps all 59 children, and `match` is "".
  - **`test_tab_membership`** (`tabsOf`):
    - every kind of P135 maps to its tabs;
    - `cancelled` gives `{"all"}`;
    - `disputed` with `end_date` 2026-10-18 gives `{"all", "past"}`, and with 2026-10-19 gives
      `{"all", "upcoming"}` at today 2026-10-19.
  - **`test_level_filter`:**

    | Month, level | Cards / records |
    |---|---|
    | Oct, national | 15 / 19 |
    | Oct, subnational | 15 / 39 |
    | Sep, national | 15 / 18 |
    | Sep, subnational | 12 / 16 |

    The 5 `unknown`-level September cards appear in both.
  - **`test_tab_counts_on_the_fixture`:**
    - Oct upcoming: 11 cards, 15 records, 7 groupings, 0 held;
    - Oct past: 19, 43, 4, 8;
    - Sep upcoming: 0 cards;
    - Nov past: 0 cards.

    These are the errata's prototype values.
  - *Mutations:*
    - `view` counts kept children with duplicates;
    - `match` uses `<=`;
    - search reads `card.type`;
    - `cancelled` in Upcoming;
    - `unknown` level dropped from `national`;
    - `held` missing from `past`;
    - `held` counted from `occurrence_confirmed` (the held-counter row);
    - the month's cards read from `doc.months[month]` only (option A; `test_month_rule`).

- [ ] **Step 2: Write the popup tests:**
  - **`test_tabs_and_counters_share_one_state`** (S5-T14, S5-T12). Serve F and S; at `PAGE_NOW`
    the popup opens on October:
    1. **On open:** `#tabAll` is `active`, with `aria-selected` "true" and the others "false". There
       are 30 cards, `#recordCount` is "58 election records (incl. 11 groupings)",
       `#statTotal` "58" and `#statHeld` "8".
    2. **Upcoming:** 11 cards and "15 election records (incl. 7 groupings)"; only `#tabUpcoming`
       is active.
    3. **Past:** 19 cards and "43 election records (incl. 4 groupings)", `#statHeld` "8".
    4. **All, then next month (November), then a search** for "county elections": 1 card whose
       `.card-match` is "1 matching of 59", and `#recordCount` "1 election record (incl. 1
       grouping)" (Tennessee's "county elections" is a grouping; errata).
    5. **The level filter:** "National + unclassified" with an empty search in October gives 15
       cards and "19 election records".
  - **`test_v2_cards_show_labels_and_badges`:**

    | Card | Badge | Label | Other |
    |---|---|---|---|
    | the October card of Canada's referendum | — | "Scheduled voting period: today (approx.)" | — |
    | the first Czech Republic card of 9–10 Oct | "9–10" / "OCT" | — | — |
    | December's Libya card | "TBC" / "DEC" | "Expected in December" | a "Tentative" chip |
    | September's Russia card | "18–20" / "SEP" | — | — |
    | November's Cape Verde card | — | — | `.card-notes` "Sources disagree on date" |

  - **`test_v2_card_text_is_inserted_as_text`** (Review Focus 5):
    - Seed F with the first October card's `country` = `"<b>X</b>"` and its `type` =
      `"<img src=x>"`.
    - The card's `.election-country` text is `"<b>X</b>"`; `#electionList b` and
      `#electionList img` count 0.
  - **`test_legacy_feeds_keep_the_legacy_renderer`:**
    - Seed `feed_record(v1_feed(), fmt="legacy")` and `check_state_v2.ok_at` = the real now (no
      check runs). The popup shows 27 October cards, with `#tabAll` active.
    - The Past tab shows the 15 October cards whose status is `Held` (errata).
    - `#levelFilter` is hidden.
  - *Mutations:*
    - `renderV2` counts cards for `#recordCount`;
    - the initial tab Upcoming;
    - `aria-selected` left on the old tab;
    - the Czech badge built from `date` only;
    - `textContent` replaced by `innerHTML` for the country;
    - `popup.js` sends `v2` to `renderLegacy`.

- [ ] **Step 3: Run them to see them fail.**

- [ ] **Step 4: Implement `count.js`** (P135):
  0. **The month's cards** (P138, option B): every card of every bucket whose `date`..`end_date`
     overlaps the month (`date <= <the month's last day>` and `end_date >= <its first day>`, as
     civil-date strings), in bucket order and then feed order.
  1. Skip a card whose `country` is not in `pinned` (when `pinned` is non-empty), or whose `level`
     is not allowed (`national`: national and unknown; `subnational`: subnational and unknown).
  2. For each child, take `childLabel`. Keep the child when `tabsOf(...)` has `tab`, and when the
     query (trimmed and lower-cased) is empty or occurs in the lower-cased join of `card.country`,
     `child.office_label`, `child.jurisdiction ?? ""`, the source names and `label.text`.
  3. Skip a card with no kept child.
  4. **Counts:**
     - `records` is the number of distinct kept `child_id`s;
     - `groupings` is those with `aggregate`, and `held` those whose label kind is `held` (P135).
  5. The card's `label` is `cardLabel(card, <kept labels>)`.

- [ ] **Step 5: Implement `render.js`.** The popup sends `v2` to `renderV2` and the other formats
      to `renderLegacy`; `#levelFilter` is shown only for `v2`.
  - **The badge and label:** `badge(card)`, then the card label.
  - **The chips** come from the first kept child's label.
  - **The notes** are the kept children's notes, without repeats, in order.

- [ ] **Step 6: Run them to see them pass.** Update Task 4 and 5's popup tests only where the
      shown element names changed (the card counts stay 30). Then the gates, the mutations and
      the commit:
  `git commit -m "feat(extension): one pipeline for tabs, filters and counters; v2 cards (Plan 5b-1 Task 6)"`.

---

## Requirements for later plans

Plan 5b-2 and 5c pull these rows into their own tasks, each with the named acceptance test. The
discovery's 5b-2 outline (Tasks 7–13) stands, with these additions.

| ID | Requirement | Owner | Acceptance test | Stage |
|---|---|---|---|---|
| R47 | v2 cards open no link in 5b-1 (P135). 5b-2 Task 7 adds the source entries, and Task 9 opens them only through the §12.6 allowlist | Plan 5b-2 | S5-T18 | 5b-2 Tasks 7, 9 |
| R48 | `count.view`'s pin filter compares v1's `pinned_countries` with the card's `country` (P135). 5b-2 Task 10 switches it to `pinned_places_v2` and a parent pin that includes its subdivisions | Plan 5b-2 | S5-T15, S3-T17 | 5b-2 Task 10 |
| R49 | `chrome.runtime.reload()` loses the extension under `--load-extension` (P136). S5-T16 and RT-06 replace the folder's contents, then relaunch the browser on the same profile. That relaunch fires `onInstalled` with reason `install`, not `update` (probe5), so the test checks the kept storage and pins, never the reason. The `update` path is tested through `lib/worker.js`. Chrome's Reload button itself is not driven; the release notes' evidence says so | Plan 5b-2 | S5-T16, RT-06 | 5b-2 Task 13 |
| R50 | The attention section's own count sits beside `#recordCount`, and the records counter never includes attention items | Plan 5b-2 | S5-T10, S5-T11 | 5b-2 Task 8 |
| R51 | R26's popup measurement times the v2 path from storage read to first render, including `feedFormat` on the full feed | Plan 5b-2 | `test_popup_renders_the_fixture_feed_within_the_budget` | 5b-2 Task 11 |
| R52 | `lib/legacy.js` still builds cards with `innerHTML` and `escHtml`, and opens feed links as they are. 5b-2 Task 9 removes both | Plan 5b-2 | S5-T18 on the legacy renderer | 5b-2 Task 9 |
| R53 | The gates job's measured time (R41) includes `playwright install --with-deps chromium` and the extension suite | Plan 5c | the branch run's step times, in the ledger | 5c |
| R54 | `help.html` explains the nine banner conditions (P133), the label texts (P134), the tabs (P135), the month rule (P138) and the Past tab's rename | Plan 5b-2 | S5-T20's doc check | 5b-2 Task 12 |
| R55 | `options.js` (v1.0.2) still sends `FETCH_DATA`, which the v2 worker ignores. On a fresh install the options page lists no countries; after an upgrade it lists v1.0.2's last `elections_cache`, frozen for good, so a new country can never be pinned. The options page reads `elections_cache_v2` (or asks the worker with `CHECK`) and never relies on `FETCH_DATA` (Plan 5b-1 Task 4 ruling; final review I2) | Plan 5b-2 | an options-page test listing the v2 feed's countries on a fresh install and after an upgrade | 5b-2 Task 10 |
| R56 | An acknowledgement whose `until` has passed still counts (grey, "(acknowledged until <past date>)"); `health.issues` never compares `until` with `now`. P133 and the spec are silent, so 5b-2 rules on it in a new P-row before changing what readers see (final review m3) | Plan 5b-2 | an `issues`/`bannerState` row with an expired `until` | 5b-2 pre-flight, with Task 12 |
| R57 | With warnings the banner reads "7 warnings 7 warnings": P133 row 7's text equals its counts. Hide `#bannerCounts` when it equals the text (final review m4) | Plan 5b-2 | a popup assertion on the artifact pair | 5b-2 Task 12 |
| R58 | `feedFormat` runs the legacy checks before the schema walk (decide on a single walk with R51's numbers). The 30 s deadline does not abort the fetch, and the size limit applies after buffering (an `AbortController` and a streamed cap). `fetchFeed` runs `feedFormat` outside a `try`, so a pathological (deeply nested) feed could still reject `check` (Plan 5b-1 O5, M6; fix-wave re-review) | Plan 5b-2 / 5c | R51's measurement; a hung response is aborted; a 10,000-deep array gives a failed check, not a rejection | 5b-2 Task 11 or 5c |
| R59 | The two-line footer at narrow width and 200 % zoom (§12.7): the list's 96 px bottom padding assumes one line (Plan 5b-1 P5) | Plan 5b-2 | §12.7's narrow-width and zoom check | 5b-2 Task 11 |
| R60 | When R52 removes `innerHTML`, `test_no_feed_text_through_inner_html_in_v2_code` covers `legacy.js` too and also rejects `DOMParser` and `createContextualFragment` (Plan 5b-1 P6) | Plan 5b-2 | that test | 5b-2 Task 9 |
| R61 | The renderer × feed matrix includes legacy → v2 and v2 → legacy → v2 inside one open popup, and a format change through a successful check (a real rollback), not only the failed-check path (Plan 5b-1 Q2, Q5) | Plan 5b-2 | S5-T17 | 5b-2 (S5-T17's task) |

## After Plan 5b-1

- **The branch** has Plan 5b-1's commits on top of the commit that holds this plan, with every gate
  green. Nothing is pushed or merged.
- **The Review record** shows every Plan 5b-1 row as "verified", with its commit in the SDD ledger.
- **Loaded unpacked from `extension/`,** the popup shows the v2 feed:
  - honest labels;
  - a banner and a health panel;
  - "Data as of" and "Checked";
  - tabs and counters that agree;
  - after a rollback, the legacy renderer and the mismatch banner.
- **Next:** write Plan 5b-2 (discovery Tasks 7–13 plus R47–R52 and R54–R61) against this code.
