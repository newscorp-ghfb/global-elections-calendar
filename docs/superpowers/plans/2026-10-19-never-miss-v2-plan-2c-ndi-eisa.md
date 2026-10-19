# Never-miss v2, Plan 2c: NDI, EISA and chained requests — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Revision 3 (2026-10-19).** A narrow amendment after the red-team follow-up
(`Downloads/claude-code-plan-2c-revision-response-2026-10-19.md`), on revision 2 (SHA-256
`01972b16…`):
- **P63, sibling scope:** revision 2 gave every part of a split label the whole label's
  subdivisions. "Nigeria Presidential and Osun Gubernatorial" made the presidential claim
  Osun's, and "Osun Governor and Lagos State Assembly" gave both claims "Osun, Lagos State" with
  a clean `parsed` unit. Now each part keeps its own subdivision. A part that names none takes
  only a subdivision that leads the first part (`base.part_scopes`, Task 3). Measured: no real
  split label names a subdivision (0 of 37 EISA 2023–2026 split rows; no NDI title splits), so
  no real output and no earlier expected value changes.
- **The user's three choices are settled** as the follow-up recommends:
  - the "10 or more cards and no pager" layout error is kept, with `PAGE_SIZE` stated as a
    source assumption and an 11-card case added;
  - the real `p3`/`p4` fixtures are added;
  - the inherited country goes into the unit text, with its meaning defined (P53).
- C07's all-implausible wrong-year table was already in `test_table_year_check`.

**Revision 2 (2026-10-19).** It folded in the red-team review of revision 1
(`Downloads/never-miss-v2-plan-2c-red-team-review-2026-10-19.md`; revision 1's SHA-256 was
`99b8dd89…`).
- All eight findings, C01–C08, were reproduced on the revision 1 prototypes, and all are taken:
  - new decisions P63 and P64;
  - changes to P47–P50, P53, P56, P57, P61 and P62.
- The review's rulings on P47, P51, P52 and P57 are taken too.
- Re-measured on every real window: the counts, coverage, notes and claims are unchanged. Only
  unit texts change. NDI texts gain the `data-location`, and EISA texts gain the inherited
  country (see "Review record").
- Two NDI pages, `p3` and `p4`, join the fixtures. A window that reaches back to December 2025
  needs them (C06).

The semantic items under "Spec corrections" need the user's approval before Task 2 starts.

**Goal:** Add NDI and EISA as adapters. Their later pages depend on earlier ones: NDI's pager,
and EISA's table id per year. A chained-request contract leaves the runner unchanged and makes
every page that was expected but never received loud. Pay off Plan 2b's final-review minors
(M1–M5, M9) and N-8. v1 keeps running unchanged.

**Architecture:**
- **`sources/base.py`** gains `fetch_chain` and `missing_pages` (the chained-request contract,
  P46). The runner, `RawPages` and the worker protocol do not change.
- **`ledger.py`** gains two discovery rule types: `CardBlocksRule` (NDI) and `JsonListRule` (EISA).
  `discover` takes the page key.
- **Shared label helpers:**
  - `places.py` gains `named_places` (P48);
  - `base.label_scope` gains an `office_text` keyword, and `base.part_scopes` scopes the parts
    of a split label (P63);
  - `offices.py` gains `unnamed_parts` (P64);
  - `data/subdivisions_manual.yaml` gains the BARMM and Bangsamoro names (P51).
- **`tests/support/slow_adapters.py`** gains `Chain`, a chained test adapter for the runner
  integration case (P46, C01).
- **Two adapters,** `sources/ndi.py` and `sources/eisa.py`. Each is registered in `COUNT_RULES`,
  `runner.DEFAULT_ADAPTERS` and the import-linter independence contract.
- **Carry-overs** in `tables.py`, `electionguide.py`, `osce.py`, `carter.py`, `offices.py` and
  `ledger.py`.

**Tech Stack:**
- Python 3.14.1;
- `beautifulsoup4` 4.15.0 + `lxml` 6.1.3 (adapters);
- stdlib `html.parser` and `json` (ledger, EISA).

No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-16-never-miss-v2-design.md`.
- Read these sections before you start:
  - §5.2, §6.1–§6.4;
  - §7: its introduction, and the NDI and EISA rows;
  - §9.1–§9.4, §10.5 (source priority);
  - §12.6 "Links";
  - §16 (the S2 tests);
  - Appendix B: the Morocco, São Tomé, Brazil, Peru, Serbia and Cape Verde rows.
- Where this plan and the spec differ, the plan wins *only* for the items under "Spec
  corrections".
- Plan 2b (`docs/superpowers/plans/2026-10-18-never-miss-v2-plan-2b-table-sources.md`) is built
  at `94ac45a`. Its Interfaces blocks describe the code, except where the errata below say
  otherwise.

## "As built" errata (read first)

**Plan 2b** (built at `94ac45a`: 1005 tests, mypy 57 files, ruff clean, `Contracts: 2 kept, 0 broken`):
- **`tables.py` has two helpers its Interfaces block does not list:**
  - `anchor_href(anchor) -> str | None`: the `href` as written, if it is a non-blank string. A
    blank href counts as missing, never as rejected.
  - `one_header_table(text, headers) -> tuple[Tag, dict[str, int], list[Tag]] | str`: the page
    check that OSCE, IPU and A-WEB share. It returns the table, its columns and its body rows,
    or the `layout_not_recognised` detail.
- **"One day" (`voting_period`) means `span.start == span.end`.** In A-WEB and OSCE, a range of
  days or a month gives `unknown`.
- **I1:** an IPU expected date with a status word is unparsed `date_unparsed`, with the cell text
  as leftover.
- **I2:** a Carter token with a status word goes to leftover, like any unparsed token.
- **Carter** passes no `default_year`.
- **`COUNT_RULES["eeas"]`** repeats `eeas.MISSION.pattern`. A drift test pins the two together.
- **M10:** `tests/unit/test_text_hygiene.py` guards the source files against control bytes.
- **`test_importlinter_adapters_contract_lists_every_default_adapter`** (`test_runner.py:445`)
  ties `importlinter.ini` to `DEFAULT_ADAPTERS`. M9 widens it to every module (Task 1).
- **Still deferred:** `\d` matches non-ASCII digits in the Plan 1–2b regexes. New code in this
  plan uses `[0-9]`.

## Plan series

1. **Foundations** (done, `8632297`).
2. **Sources:**
   - 2a: contract, ledger, runner, ElectionGuide, Wikipedia (done, `f5f3a1c`).
   - 2b: OSCE, IPU, A-WEB, Carter Center, EEAS (done, `94ac45a`).
   - **2c (this plan):** NDI and EISA with the chained-request contract, Plan 2b's final-review
     minors, N-8, and the Plan 1 date minors (settled, no code change).
3. **Merge.**
4. **Health, snapshots, feed and publishing.**
5. **Workflow, extension v2.0.0 and rollout.**

**Not in this plan:**
- no change to `scraper.py`, `elections.json`, `.github/workflows/` or `extension/`;
- nothing is pushed or merged;
- no network access.

The fixtures were captured during plan writing on 2026-10-19, through `Fetcher` with
`trust_bundle`. They are copied from `.scratch/plan2c/captures-2026-10-19/` in this worktree
(git-ignored).

## Global Constraints

Plan 1's, Plan 2a's and Plan 2b's Global Constraints all still hold:
- **Code:**
  - the layering;
  - civil dates;
  - no network in tests;
  - content never raises;
  - adapters take no options.
- **Process:**
  - the four gates, each in its own shell call;
  - mutation checks;
  - `.scratch/` for scratch files.
- **Git:**
  - work on `feat/never-miss-v2` only;
  - check `git rev-parse --abbrev-ref HEAD` in its own call before every commit;
  - end each commit with the `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`
    trailer (or the implementer's own model name).
- **Units and claims:**
  - one outcome per unit;
  - no guessed certainty;
  - no units from a failed page;
  - a duplicate names its original;
  - a unit that gave no claim reserves nothing (P42);
  - relevance comes from the date text (P24);
  - no `valid_empty` (P23);
  - `label_scope` for every label (P38).
- **Fixtures:** byte-exact.

This plan amends two of them:

- **Page keys (amends "page keys are static", P46).** A chained adapter's `requests(window)`
  returns its first page only: NDI `p0`, EISA `calendar`. That request is the same for every
  window. The later keys come from the adapter's module-level `expected(window, pages)`.
- **Claim links (amends P44, P60).** NDI cards and EISA rows hold no links (measured). The claim
  link is therefore the source's calendar URL constant, and the adapter makes no `source_link`
  call, as in A-WEB.

This plan adds:

- **Unit IDs and page keys (P58):**

  | Source | Page key | Unit ID |
  |---|---|---|
  | `ndi` | `p<n>`, n = 0…9 | `ndi:p<n>/<block>-c<i>`, block `upcoming` or `past` |
  | `eisa` | `calendar` (no units) | — |
  | `eisa` | `y<YYYY>` (`PageRequest.year = YYYY`) | `eisa:y<YYYY>/r<i>` |

- **New unit reasons** (free strings; no model change):
  - NDI: `title_missing`, `place_conflict`, `place_ambiguous`, `type_unrecognised`;
  - EISA: `row_unrecognised`, `office_missing`, `no_new_date`;
  - NDI and EISA: `round_conflict`;
  - Carter (Task 1): `extra_cells`.
- **A unit's text names every input the adapter read** (C02, C08). An NDI text ends with the
  card's `data-location`. An EISA row that inherits its country starts with
  `<country> (from the row above)`. The text is what a reviewer sees. Duplicates compare the
  same inputs (P61): NDI's four card fields, and EISA's country after inheritance, election and
  date. The text is deterministic: it holds nothing volatile (no fetch time, page number or
  position), so an acknowledgement can rely on it (R16).
- **Every office a label names is kept** (C03). A label that names two offices gives one claim
  per office. A part that names no office makes the unit partial `office_unrecognised` (P64).
  A subdivision named for one part is never copied to a sibling, unless it leads the label
  (P63).
- **Page order.** Pages arrive in fetch order (the runner numbers them). Cross-page state flows
  in that order:
  - NDI's repeat and order checks, on non-empty blocks only (P50);
  - the duplicate checks of both adapters.
- **Regexes** written in this plan use `[0-9]`, never `\d`.
- **EISA's calendar page is `ok` with no units.** It only navigates to the year tables. This is
  not `valid_empty`: no unit was expected on it.

## Review Focus

These are the five inputs most likely to hurt a user that the spec implies but no step spells
out. Each one is pinned by the named tests, in the task that owns the code.

1. **Pagination that drifts, is cut short, or loses its navigation.** For example:
   - NDI ignores `?page=` and serves page 0 again;
   - NDI clamps a short block, or repeats a block's cards;
   - a full block's pager disappears, or its next link loses `rel="next"` (C01);
   - the list shifts between two page fetches;
   - the worker is cut mid-chain;
   - a later page times out;
   - the 10-page cap is reached.

   Each gives a named `layout_not_recognised`, a download outcome, an ignored `duplicate` or a
   `pagination_incomplete` note. None gives a silent short result. The empty, clamped upcoming
   block of `p2`–`p4` is a recognised end state, not a repeat (C06). Pinned by:
   - `test_chain_by_window` and `test_pagination_failures_are_loud` (Task 4);
   - `test_pagination_failures_are_loud` (Task 5);
   - `test_fetch_chain`, `test_missing_pages` and `test_a_chained_source_cut_mid_chain`
     (Task 2).

   **Residual risk:** a card *deleted* between two page fetches (about 0.4 s apart) moves one
   card off the end of the earlier page unseen. No ordering or overlap check can see that.
2. **NDI placeholder dates.** 31 December and month-end days often stand in for unknown dates.
   Measured on p0–p4:
   - all 10 of the 31 December cards are placeholders (9 in 2025, plus Haiti 2026 "Date TBD");
   - 2 non-TBD month ends are placeholders (31 October 2025: Georgia and Côte d'Ivoire), against
     3 genuine month-end days.

   Rule P47 is a source-specific, conservative inference, not proof that every month end is a
   placeholder: 31 December → year; TBD or a month end → month. A month still contains the real
   day, so the merge can match it. A genuine month-end day loses its day precision; `date_text`
   keeps the visible text. Pinned by `test_dates` (Task 4), and downstream by R13.
3. **Year rollover.**
   - EISA has no 2027 table in October (measured). A missing future year is `not_published_yet`
     (info); a missing current or past year is `required_year_missing` (error, P52).
   - Inheritance never crosses tables.
   - NDI's chain gets longer as the window moves back into the archive.

   Pinned by `test_calendar_headings` and `test_chain_by_window` (Task 5), and
   `test_chain_by_window` (Task 4).
4. **Inherited and compound labels.**
   - EISA rows with a blank country inherit the previous row's country, and their text says so
     (C08). A first row with a blank country, or a row after an unreadable one, has no place.
   - Multi-office labels are split, in EISA rows and NDI titles (C03). Each part keeps its own
     subdivision; a part that names none takes only one that leads the label ("Osun Governor and
     State Assembly"), never one named for a sibling ("Presidential and Osun Gubernatorial"). A
     part that names no office is flagged, never dropped (N-8's casefold fix matters here).
   - Round qualifiers sit at either end of the date. They fill a part's missing round, and a part
     whose own round disagrees is flagged (P57).
   - "Postponed from X" carries no new date.

   Pinned by:
   - `test_row_kinds_and_inheritance`, `test_row_grammar` and `test_rounds_and_parts` (Task 5);
   - `test_compound_titles` and `test_type_fallback_keeps_the_title_context` (Task 4);
   - `test_label_scope_office_text`, `test_part_scopes` and `test_unnamed_parts` (Task 3);
   - `test_split_top_level_when_casefold_changes_length` (Task 1).
5. **Words and shapes a source has never used before:**
   - an NDI type term outside the filter vocabulary;
   - a card without a title, a date or a place;
   - two places in one card, or two countries in one title (C04);
   - an EISA row that is not an object with the three string fields;
   - a JSON object instead of a list;
   - new heading wording;
   - a `colspan` or second header row in any header table (M1);
   - a status badge outside the date cell (M4);
   - a third Carter cell (M5).

   Each is a partial or unparsed unit with a reason, or a named layout outcome. Pinned by:
   - `test_card_kinds` and `test_card_places` (Task 4);
   - `test_named_places` (Task 3);
   - `test_row_kinds_and_inheritance` and `test_broken_json` (Task 5);
   - `test_header_problem`, `test_badge_scope` and `test_extra_cells_are_leftover` (Task 1).

**Known limits, by design.** The measured values include each of these, and each is visible:
- **Relevance before September:** units dated January–August of the current year have relevance
  `unknown` (Plan 2a's limit).
- **NDI place text:** an NDI `place_raw` is `data-location`, or the matched title words (one
  title place, or a child that refines `data-location`). In the fixture, Bosnia's
  `data-location` "Bosnia-Herzegovina" does not resolve, so the title's "Bosnia and
  Herzegovina" is used. No alias is added. The unit text still shows "Bosnia-Herzegovina".
- **NDI title vs type:**
  - NDI's title decides the office when it names one. The type terms set the default level, and
    they stand in for the office only when the title names none.
  - Even then, the title's jurisdiction and round are kept (C05).
  - A card whose type contradicts its title (title "Parliamentary", type "Presidential") keeps
    the title's office.
- **NDI's missing pager (C01):** a block with no pager and `PAGE_SIZE` (10) or more cards fails
  the page as a layout error. The detail names the cause ("… cards and no pager"). Plan 4's
  snapshot acceptance then serves the last good snapshot as `fallback`, or reports the source
  `unavailable` (spec: Snapshot `acceptance`).
  - **The assumption:** NDI shows 10 cards per page (measured on p0–p4, 2026-10-19). If NDI
    changes it, revise `PAGE_SIZE` against a new capture.
  - **The false alarm:** if NDI ever lists exactly 10 upcoming elections and drops the pager
    because there is only one page, the run fails loudly. That is a false alarm, never a silent
    loss.
  - **The residual risk:** a block of 9 or fewer cards with no pager is read as complete. That
    is safe only while the page size holds and NDI delivers whole blocks. "Never a silent loss"
    describes the 10-card case, not every case.
  - Whether NDI drops the pager for a single page is not verified on the live site. Every real
    block on p0–p4 has one.
- **NDI duplicates compare visible text:** two cards that differ only by an alias of one place
  ("Ivory Coast" and "Côte d'Ivoire") are two assertions with the same `place_id`. Plan 3's merge
  joins them.
- **EISA scope gaps:** EISA 2025's "Zanzibar President" becomes a national `head_of_state` on
  `iso:TZ`, because Zanzibar is several ISO 3166-2 regions and none is named. It is in no window
  that is requested today.
- **EISA rounds:** a round qualifier fills every part of a split row that has no round of its
  own. Seychelles 2025 "President And National Assembly | First Round: …" gives round 1 to both
  parts.
- **Libya:** EISA's two Libya rows ("Postponed from April 2026") are `no_new_date` units with
  relevance `unknown`. They stay attention items until EISA gives a new date (R16).

## Spec corrections

These were found while measuring the 2026-10-19 captures, and revised after the red-team review
(C01–C08).
- **Semantic decisions:** P46–P57, P63 and P64 change what the calendar says, what it flags, or
  how a run is judged, so they need the user's approval before Task 2 starts. Each one gives the
  alternative and what it would cost. (P50 refines the spec's own layout rule. It is semantic only
  through P46's continuation rule, which it carries out, and through its end-state checks.)
- **The other corrections** refine names, files or details.

| ID | Spec says | This plan does | Why / alternative |
|---|---|---|---|
| P46 (contract) | §7/§9.1: an adapter lists its requests up front; the runner's `unfinished` are the requests whose pages were not received | **Chained requests.** A chained adapter's `requests(window)` is its first page. Its module-level `expected(window, pages) -> tuple[PageRequest, ...]` gives every request that the pages received so far imply, first page first. `fetch` is `base.fetch_chain(lambda pages: expected(window, pages), fetcher, deadline)`. `parse` adds `base.missing_pages(expected(window, raw.pages), raw)`: one `pagination_incomplete` note, "`<key>` was not fetched", per expected request that is neither received nor unfinished. The runner, `RawPages` and the worker stay as they are; three docstrings and the README say that `unfinished` holds only up-front requests | NDI's next page and EISA's table ids are known only from earlier pages. The runner already pickles the pages the worker received, and the adapter re-derives the chain from them in the parent, so a child never writes requests the parent must trust. Alternatives: (a) static NDI `p0`–`p9` every run: 10 fetches, about 4 s, and still no static answer for EISA's table id; (b) the worker writes its request list for the runner: more runner surface, and the parent would trust child-written requests |
| P47 (semantic) | §7 NDI: "Date from the visible card text. 'TBD' in the title → `date_status=tentative` and month precision" | **The visible date must be one day.** Otherwise the unit is unparsed `date_unparsed`, with the date text as leftover. A status word in it gives the same (I1). **Precision:** 31 December → `DateSpan.of_year`. Otherwise "TBD" in the title (`\bTBD\b`, any case) or the month's last day → `DateSpan.month`. Otherwise a day. **Status:** `date_status="tentative"` when the title has TBD, else `"unknown"`. **Meaning:** `date_meaning="voting_period"` for day precision, else `"unknown"`. `date_text` keeps the visible text | A source-specific, conservative inference (the review's ruling), not proof that month ends are placeholders. Measured: every 31 December on p0–p4 is a placeholder (10). Non-TBD month ends: 2 placeholders against 3 genuine days. A month or year still contains the real day; the cost is that a genuine month-end day loses its day precision. As days, Haiti 2026 would get a phantom 31 December polling day. Downstream, an inferred month or year never confirms a day (R13). Alternatives: only 31 December → year (2 phantom days in October 2025); or keep days (P25 chose months for IPU) |
| P48 (semantic) | §7 NDI: "Country = `data-location`" | **The title's places** are `places.named_places(title, places)` (Task 3): every registered place it names, one per place ID, with a parent dropped when its child is also named. **Place, in order:** (1) a registered `data-location` place. A title place that is its child refines it (title "Scotland", location "United Kingdom" → `iso:GB-SCT`, `place_raw="Scotland"`). Any other title place makes the unit partial `place_conflict`; the claim keeps `data-location`, and the leftover is those places' words joined by ", ". (2) Else exactly one title place. (3) Else, with two or more title places, unparsed `place_ambiguous`, leftover = their words joined by ", ", and no claim. (4) Else an unregistered `data-location` place, as partial `place_unregistered`. (5) Else unparsed `place_missing` | 22 of the fixture's 38 cards have `data-location` (32 of 68 on p0–p4), and one of those 22 does not resolve ("Bosnia-Herzegovina"). Without the title fallback, 17 fixture cards would have no place. Each of the 68 real titles names exactly one registered place (measured). **C04:** revision 1 took the first match, so "2026 Niger and Nigeria Elections" became a clean Niger election. Now it is `place_ambiguous`: the title may name two elections, or be malformed, so it is not split. Aliases of one country count once ("Côte d'Ivoire (Ivory Coast)" is one place). Alternatives: `data-location` only, which leaves 17 permanent `place_missing` units; or split a two-country title into two claims |
| P49 (semantic) | §7 NDI: "The type label sets the level" | **Type terms** are the `.date-type` element's own text lines, whitespace-collapsed, casefolded and non-empty. They set the default level: all terms in `SUBNATIONAL_TYPES` → `subnational`; subnational and national terms mixed → `unknown`; otherwise (including no terms) → `national`. A term in neither set does not count; the unit is partial `type_unrecognised`, with those terms as leftover. **Office words:** the title without its named-place runs and four-digit years, then without an empty `()`. **Parts:** `split_offices(office words, …)` when it gives 2 or more parts (C03), else the title alone. **Type fallback:** when the title alone names no office, terms exist and the title did not split, `" and ".join(terms)` (split the same way) replaces the parts if it names an office. **Scope (P63):** one part → `label_scope(title, place, registries, default)`. Parts split from the office words → `part_scopes(parts, place, registries, default)`: each part keeps its own subdivision, or takes one that leads the first part. Fallback parts → `label_scope(title, place, registries, default, office_text=part)`: the terms name no place, so the title's subdivisions apply to each (C05). Office evidence beats the default (`claim_level`). **Round:** the part's own; in the fallback, the title's `extract_round` fills a part that has none, and a part whose own round differs makes the unit partial `round_conflict` (leftover = the terms; that part's round `None`). **Compound check:** `unnamed_parts(office words, …)` (P64) non-empty → partial `office_unrecognised`, leftover = those parts. **Partial `level_unresolved`:** any part's scope is `unresolved`, or its level is `unknown` with a recognised office. **`office_not_modelled`:** an executive title | The type filter is NDI's own vocabulary: 53 terms, 14 of them sub-national (Task 4). "2026 Philippines BSKE Elections" (type "Regional") names no office in its title; the type gives `local_council`. **C03:** revision 1 turned "2026 Chile Presidential and Local Elections" into one clean national `head_of_state` claim. Now it gives `head_of_state` national plus `local_council` subnational (`aggregate=True`). **C05:** revision 1 scoped the fallback on the terms alone, which dropped the title's jurisdiction ("2026 Philippines (BARMM) BSKE Elections" keeps "BARMM" now) and its round ("… BSKE Run-Off" keeps round 2). Measured on the 68 real titles: none splits, none has an unnamed part, and only BSKE uses the fallback, so no fixture claim changes. Alternative: type sets the office too (it would turn "2026 Bulgaria Parliamentary Elections" into whatever the type says) |
| P50 | §7 NDI layout: "Two `.bound` blocks with cards and pagers … Order is verified by date direction. `?page=N` advances both. Continue while upcoming has a next page or the past block's oldest card is ≥ the window start. Cap 10 pages; repeated-page detection by card-name set" | **Blocks** are found by id: `#upcoming-elections` and `#past-elections`. The page checks are in Task 4's Rules, each with its detail. **Continue** while the upcoming block has a `rel="next"` link, or the past block has one and has cards and either no single-day card or an oldest single day ≥ `window.start`. **Cap:** `p9` still wanting more gives the note `pagination_incomplete` "stopped at the 10-page cap". **End states (C01):** a block's last page must look like one. With a pager but no `rel="next"` link, the active `li` must be the pager's last `li`; else `"<slug> block has later pages but no next link"`. With no pager, the block must hold fewer than 10 cards (NDI's page size); else `"<slug> block has <c> cards and no pager"`. **Repeat and order checks** compare non-empty blocks only (C06) | The `.bound` class also wraps the filter form (measured), so the ids are the stable handle. On p2–p4 the upcoming block is clamped: its pager says `?page=1`, and it has no card list (measured). The spec's continue rule needs a next link on the past block too; without one there is no next page. **C01:** in revision 1, a full block with its pager removed read as a last page, so the chain stopped at `p0` with no note; `missing_pages` cannot see a page that was never implied. Measured: every real block on p0–p4 has a pager, and every real last page has its active `li` last. **C06:** revision 1's text did not limit the repeat check to non-empty blocks (its prototype did); the 2025-12-20 window, which needs p0–p4, pins it now. Alternative: no end-state checks, which lets a missing pager cut the chain silently |
| P51 (semantic) | §6.3/§6.4 via P38 | `data/subdivisions_manual.yaml` gains `PH: {BARMM: PH-14, Bangsamoro: PH-14}`. PH-14 is ISO 3166-2's Autonomous Region in Muslim Mindanao, the region BARMM replaced | NDI `p0/past-c6`, "2026 Philippines (BARMM) Parliamentary Elections" (14 Sep 2026), is otherwise a false national Philippine legislature contest, as OSCE r52 was. With the keys it is jurisdiction "BARMM", level `unknown`, partial `level_unresolved`. Measured: no Wikipedia, ElectionGuide, OSCE, A-WEB or IPU output changes; the rebuild adds 2 lines. Alternative: no keys |
| P52 (semantic) | §7 EISA layout: "The current year's heading exists" | **The calendar page** is `layout_not_recognised` only when it is cut, or when a matched heading's tables do not give one valid id. **A window year without a heading** gives a note instead: `not_published_yet` (info) for a year after today's, and `required_year_missing` (error) for today's year or an earlier one | From September the window spans next year, and EISA had no 2027 heading on 2026-10-19 (measured). The spec's rule would turn every autumn run red. A current-year gap stays an error, under its own code. Alternatives: the spec's rule; or a January grace period, which would lose January events while it lasts |
| P53 (semantic) | §7 EISA: "A blank country inherits the previous row's country within the same table only; blank in the first row → partial" | A blank country with nothing to inherit is **unparsed** `place_missing`. Inheritance also stops after a row that is not readable (`row_unrecognised`). **An inheriting row's unit text names the inherited country:** it starts with `<country> (from the row above)`, followed by the election and the date (C08). The phrase means "from the nearest row above that names a country", which can be two rows up. It is fixed text, and the underlying JSON row is kept in the raw page | A partial unit needs a claim, and a claim needs a place. **C08:** in revision 1 the text held only the row's own fields. A `no_new_date` row has no claim, so nothing recorded its country: the Libya row's text stayed the same when the row above became Chad. Measured: 4 fixture texts change (`y2026` r4, r7, r12, r15; 10 on 2025-11-15), and nothing else. Real tables have at most 2 inheriting rows in a row (one 2023/2024 table), so "the row above" is two rows up at most. Alternatives: a claim on an unknown place, which would invent a country; or a separate context field on `InputUnit`, which is a model change |
| P54 (semantic) | §7 EISA grammar: "`Postponed from X [to Y]`" | "Postponed from X to Y" → a claim at Y, `status_claim="postponed"`, `previous_date_text=X`. "Postponed from X" with no new date → unparsed `no_new_date`, with the date text as leftover and no claim | Libya ×2 in 2026 (measured). Alternatives: a claim at X, which is a phantom April 2026 date; or ignored, which hides an election that still has no date |
| P55 (semantic) | §7 EISA grammar: "`Held D Month YYYY` (held, voting_period); … `Mon YYYY - Mon YYYY` (expected_window); `Stagerred: … - …` (unknown, phased)" | **`date_meaning`:** one day and not phased → `voting_period`, with or without "Held". A month-precision span over different months, not phased → `expected_window`. Everything else → `unknown`: one month, a year, a range of days, phased. **`date_status`** is the parse's | It matches A-WEB's "one day" rule (errata). Fixture: 18 `voting_period`, 1 `expected_window` (South Africa, Nov 2026 – Jan 2027), 6 `unknown`. Alternative: plain `D Month YYYY` → `unknown` |
| P56 (semantic) | §7 EISA has no office rule | `offices.split_offices(label, place_id, institutions)` gives one claim per part (`#0`, `#1`, …), scoped together by `part_scopes(parts, place, registries)` (P63): each part keeps its own subdivision, or takes one that leads the first part. `unnamed_parts(label, …)` (P64) non-empty → partial `office_unrecognised`, leftover = those parts | 5 of the 20 parsed 2026 rows name two offices: Benin, Somaliland, South Sudan, Uganda, Zambia (25 claims). Revision 1 scoped each part alone, so "Osun Governor and State Assembly" gave the second part no jurisdiction; now both parts are "Osun", while "Presidential and Osun Governor" keeps the presidential claim nationwide (measured). No 2023–2026 row has an unnamed part or a subdivision in a split label, and no fixture claim changes. Alternative: one umbrella claim per row, which loses each chamber |
| P57 (semantic) | §7 EISA has no round rule | A leading `first round:` or `second round:`, or a trailing `(first round)`, `(second round)`, `(runoff)` or `(run-off)` (any case) is cut from the date text before parsing. First → round 1; second and run-off → round 2. **Per part:** the qualifier fills a part whose office has no round of its own. A part whose own round differs from the qualifier makes the unit partial `round_conflict`, leftover = the qualifier as written (for example `"First Round:"`), and that part's round is `None`; the other parts keep theirs | EISA 2025 has 4 such rows (Egypt Senate ×2, Seychelles ×2); 2026 has none. Without the cut they are `date_unparsed`. The review asked for the conflict case: under revision 1's rule ("the qualifier's, else the office's"), "Presidential Run-off" with "First Round: 13 Sep 2026" was a silent round 1. Measured: the only office round in EISA 2023–2026 is 2024's "President & Governors (first round)". It does not conflict, so no fixture value changes. Alternative: leave them unparsed |
| P58 | §5.2 example `ndi:p2:upcoming` | Page key `p<n>` with the block in the position: `ndi:p<n>/<block>-c<i>`. EISA: `calendar` and `y<YYYY>` (Global Constraints) | One fetched page is one coverage entry |
| P59 | §7 "for JSON, the list length" | `ledger.CardBlocksRule` and `ledger.JsonListRule` (Task 2). `discover(rule, body, key="")` passes the page key so that EISA's calendar page counts no units | Plan 2a's P6: an adapter cannot certify itself |
| P60 | §12.6 allows `ndi.org` and `eisa.org` links | Claim link = `ndi.URL` / `eisa.URL`; no `source_link` call | Cards and rows hold no `<a>` or URL field (measured) |
| P61 | §9.1 `duplicate` | **NDI:** a card whose (title, date text, type terms, `data-location`) equal those of an earlier card that gave a claim, on any page of the run → ignored `duplicate`. This covers a card shifted to the next page between fetches. The key is the visible text, before any place is resolved. **EISA:** an equal (country after inheritance, election, date) of an earlier row that gave a claim, in any table of the run → ignored `duplicate` | Same rule as P42. **C02:** revision 1's NDI key left out `data-location`. Two cards titled "2026 General Election" for Chile and Peru were one claim, and a corrected card after a conflicting one was dropped. Now both survive (measured) |
| P62 | — | An `ok` EISA year page with at least one **readable dated row**, none of whose years is the page's year, adds the note `coverage_gap` "`y<YYYY>` has no `<YYYY>` date". A row's years are those its date's spans touch: start to end year, or the span's year. They are read before the plausibility check, with the round qualifier cut. Rows with no date (TBD, blank) give no evidence either way | Guards against a heading that points at the wrong year's table. **C07:** revision 1 looked at claims, so a `y2026` table of 2018–2019 rows (all `implausible_date`, no claims) passed. Now it gives the note; an all-TBD table does not (its units are already `date_missing`). Measured: dated rows that touch their year are 2026 19 of 20, 2025 21 of 21, 2024 24 of 25, 2023 23 of 23, so it fires on none |
| P63 (semantic) | §6.3/§6.4 via P38 | **Two helpers in `base.py`.** (1) `label_scope(label, place, registries, default="national", *, office_text=None)`: the subdivisions come from `label`; the office is classified from `office_text`, or from `label` when it is `None`. Existing callers pass no `office_text` and do not change. NDI's type fallback uses it: the terms name no place, so the title is the context. (2) `part_scopes(parts, place, registries, default="national") -> list[LabelScope]`, for the parts split from one label. **A part that names a subdivision keeps its own. A part that names none takes the leading subdivisions:** those that the first part's words begin with ("**Osun** Governor", "(**BARMM**) Parliamentary"). With none, it is nationwide. Each office is classified from its own part. For one part, the result equals `label_scope(part, …)` | Each part must keep context that the label shares ("Osun Governor and State Assembly": both Osun), without taking a sibling's own ("Nigeria Presidential and Osun Gubernatorial": the presidency stays nationwide). Revision 2 copied every subdivision to every part (the follow-up review): "Osun Governor and Lagos State Assembly" gave both claims "Osun, Lagos State" and a clean unit. The leading-context rule matches Wikipedia's, where the words before the first office are the jurisdiction. Measured: no real split label names a subdivision. Alternatives: scope each part alone, which loses "Osun" for "State Assembly"; or flag every part that names no subdivision next to one that does, which would make "Osun Governor and State Assembly" partial |
| P64 (semantic) | — | `offices.unnamed_parts(text, place_id, registry) -> list[str]`: split `text` at top-level commas, then at `" and "` / `" & "`. When there are 2 or more parts and some, but not all, name an office class (`office_class_of`), return the parts that name none, in order. Else `[]`. NDI and EISA make such a unit partial `office_unrecognised`, leftover = the parts joined by ", " | `split_offices` keeps a split only when every part names an office, so "President and Xyz" was one clean `head_of_state` claim and "Xyz" vanished. Now the claim stays, and "Xyz" is visible. Measured: no real NDI title or EISA 2023–2026 label has such a part. Alternative: drop the split silently (revision 1) |

**Also settled (no spec change):**
- **M6, M7, L70, L72, L81 (Plan 1 date minors):** decided from the text on NDI p0–p4 and EISA's
  2023–2026 tables (234 texts). Measured:
  - no Cf character, no dash other than `-`, `–` or `—`, no U+FFFD (EISA's JSON escapes "ô" as
    `\u00f4`), no "(postponed)", and no dangling dash;
  - the only "(TBD)" is in an NDI *title* (P47 reads it);
  - the only day list is EISA 2023 "Held 10, 11, 12 Dec 2023". It parses to 3 spans, which EISA
    (like OSCE and A-WEB) treats as `date_unparsed`.

  No change: each stays loud.
- **N-8 (casefold offsets in `_split_top_level`)** was deferred to "before Plan 3". It is fixed
  now (Task 1), because EISA splits labels.
- **Optional items not taken:** P45's bracketed names as extra subdivision keys; a Carter note
  for an unknown `h2` that holds a dated table.
- **NDI's type vocabulary** is pinned by a drift test against the fixture's filter, not checked at
  run time. An unknown term on a card is already a partial unit (P49).
- **Deferred items that stay deferred:**
  - N-4: before Plan 4 renders reasons;
  - F-08: Plan 3, with P38's jurisdictions as input (R7);
  - F-10: before Plan 5;
  - worker tracebacks: before the first CI run;
  - `\d` in the Plan 1–2b regexes;
  - Plan 1's other deferred minors (L64, L71, L91, L94, L101, L109–L112, L118, L127b, L127e).
    None of them is on a code path this plan changes.

## Review record

**Status:** "planned" becomes "verified" only when the SDD ledger records the task's commit, with
the named test passing and its mutation killed.

| ID | Kind | Ruling | Task · test | Status |
|---|---|---|---|---|
| M1, M2 | Agreed fix (Plan 2b final review) | A header table has one `thead` row of `th` cells with no spans. The adapters and the ledger check this independently | T1 `test_header_problem`, `test_irregular_headers_fail_the_page`, `test_an_irregular_header_is_not_a_layout`, `test_header_table_rows_reject_irregular_headers` | planned |
| M3 | Agreed fix | ElectionGuide body cells are `td` and `th` (`row_cells`). Measured: no body `th` in the 3 views | T1 `test_a_th_body_cell_is_a_cell` | planned |
| M4 | Agreed fix | OSCE badges are the date cell's spans outside its date `div`, plus `span.badge` anywhere else in the row | T1 `test_badge_scope` | planned |
| M5 | Agreed fix | A third or later non-empty Carter cell goes to leftover; with claims the unit is partial `extra_cells` | T1 `test_extra_cells_are_leftover` | planned |
| M9 | Agreed fix | Every adapter module is in `DEFAULT_ADAPTERS` and in the independence contract | T1 `test_every_adapter_module_is_registered` | planned |
| N-8 | Agreed fix (pulled forward) | Separators are matched on the original text | T1 `test_split_top_level_when_casefold_changes_length` | planned |
| R9 | Plan 2b requirement | NDI and EISA follow the contract; the dynamic-requests contract is decided first (P46); the date minors are decided ("Also settled"); JSON gets its own rule (P59) | T2–T5 | planned |
| P46 | Decision (needs approval) | Chained requests | T2 `test_fetch_chain`, `test_missing_pages`, `test_a_chained_source_cut_mid_chain`; T4/T5 `test_pagination_failures_are_loud` | planned |
| P47–P51 | Decisions (need approval) | NDI dates, place, office and level, layout, BARMM | T3 `test_named_places`, `test_barmm_names_the_bangsamoro_region`; T4 `test_dates`, `test_card_kinds`, `test_card_places`, `test_compound_titles`, `test_broken_pages_get_an_outcome_never_units`, `test_claims_field_by_field` | planned |
| P52–P57 | Decisions (need approval) | EISA headings, inheritance, postponements, meaning, splits, rounds | T5 `test_calendar_headings`, `test_row_kinds_and_inheritance`, `test_row_grammar`, `test_rounds_and_parts`, `test_claims_field_by_field` | planned |
| P61, P62 | Agreed fixes | Duplicates across pages; the table-year check | T4 `test_pagination_failures_are_loud`, `test_duplicates_compare_every_field`; T5 `test_row_kinds_and_inheritance`, `test_table_year_check` | planned |
| P63, P64 | Decisions (need approval) | Split parts keep their own or the leading subdivision; the type fallback keeps the title's; unnamed parts are flagged | T3 `test_label_scope_office_text`, `test_part_scopes`, `test_unnamed_parts`; T4 `test_compound_titles`; T5 `test_rounds_and_parts` | planned |
| P63 sibling scope | Red-team follow-up | A subdivision named for one part is never copied to a sibling unless it leads the label | T3 `test_part_scopes`; T4 `test_compound_titles` (Nigeria row); T5 `test_rounds_and_parts` (r7, r8) | planned |
| C01 (High) | Red-team finding | End-state checks on every NDI block (P50), with the `PAGE_SIZE` assumption stated; the runner integration case (P46) | T4 `test_pagination_failures_are_loud` (pagers removed, `rel` dropped, 11 cards, 9-card control); T2 `test_a_chained_source_cut_mid_chain` | planned |
| C02 (High) | Red-team finding | NDI's duplicate key includes `data-location` (P61) | T4 `test_duplicates_compare_every_field` | planned |
| C03 (High) | Red-team finding | Compound NDI titles keep every office (P49, P63, P64) | T4 `test_compound_titles` | planned |
| C04 (Medium) | Red-team finding | Two title places → `place_ambiguous`; a child refines its parent (P48) | T3 `test_named_places`; T4 `test_card_places` | planned |
| C05 (Medium) | Red-team finding | The type fallback keeps the title's jurisdiction and round, and flags a round conflict (P49) | T4 `test_type_fallback_keeps_the_title_context` | planned |
| C06 (Medium) | Red-team finding | Repeat and order checks on non-empty blocks only (P50); fixtures `p3`, `p4` | T4 `test_chain_by_window` (the 2025-12-20 row) | planned |
| C07 (Medium) | Red-team finding | The table-year check reads dates before plausibility (P62) | T5 `test_table_year_check` | planned |
| C08 (Medium) | Red-team finding | Inherited country in the unit text (P53); R16 extended | T5 `test_row_kinds_and_inheritance`, `test_claims_field_by_field` (r7, r12 texts) | planned |
| P57 conflict | Red-team ruling | A qualifier that disagrees with a part's own round → `round_conflict` | T5 `test_rounds_and_parts` | planned |

## How to execute this plan

- **Where:** the worktree `C:/Users/senescalk/Desktop/elections-calendar/.claude/worktrees/never-miss-v2`,
  branch `feat/never-miss-v2`.
  - Do not create worktrees, do not switch branches, do not commit to `main`.
  - Keep the shell in the worktree. Use `( cd … && … )` subshells for anything elsewhere.
- **Style:** this plan pins names, signatures, rules and test values; you write the bodies.
  Private helpers are yours. If a rule is ambiguous, stop and ask the controller. Never guess a
  value.
- **Measured values:** every count in the tests was measured by prototypes that implement exactly
  these rules.
  - Prototypes (revision 3), in `.scratch/plan2c/proto/`:
    - `ndi2c.py`, `eisa2c.py` (adapters);
    - `scope2c.py` (`label_scope` with `office_text`, `part_scopes`, `named_places`, the NDI
      office words, `unnamed_parts`);
    - `chain2c.py` (`fetch_chain`, `missing_pages`);
    - `rules2c.py` (the two counters);
    - `barmm_patch.py` (the P51 keys, patched in at import).

    `*_r1.py` and `*_r2.py` are revisions 1 and 2, kept for comparison.
  - Fixture dumps: `.scratch/plan2c/r3_ndi_<day>.txt` and `r3_eisa_<day>.txt`, from
    `dump2c.py <source> <day>`. `U` lines are units, `C` lines are claims, and `COUNT` lines show
    the counter agreeing. They are byte-identical to revision 2's `r2_*` dumps.
  - Synthetic cases:
    - `synth2c.py` → `.scratch/plan2c/synth_r3_full.txt`;
    - `synth_r2.py` → `synth_r3.txt` (the review's cases, C01–C08 and P57);
    - `synth_r2b.py` … `synth_r2e.py` (texts, scopes, aliases, fallback rounds, labels);
    - `synth_r3f.py` (`test_rounds_and_parts`);
    - `p63_check.py` and `task3_r3.py` (sibling scope); `p63_real.py` (no real split label
      names a subdivision); `c01_larger.py` (11 cards, no pager);
    - `synth_dup.py`, `synth_new.py` and `synth_exec.py`.

    Each script prints its own cases.
  - **Prototypes confirm the values; the rules define them.** Each expected value in a test
    table follows from its input and the rule named next to it. If a value cannot be explained
    that way, stop and report it, even when the prototype agrees.
  - The runner integration case: `.scratch/plan2c/runnerproto/` (`chain_adapter.py`,
    `test_chain_runner.py`). Run it from the worktree root with
    `.venv/Scripts/python.exe -m pytest .scratch/plan2c/runnerproto/test_chain_runner.py -p tests.unit.conftest -p no:cacheprovider`.
  - Other checks:
    - `task1_2c.py`: Task 1's cases before and after, on patched copies of the adapters;
    - `ledger_m1.py`: the M1/M2 counter rule, on synthetic pages and every header-table fixture;
    - `counters2c.py`: Task 2's synthetic counter cases;
    - `ajax0_2c.py`: EISA's year page on admin-ajax error bodies;
    - `vocab2c.py`: the type filter;
    - `xorder2c.py`: cross-page order;
    - `eisayear2c.py`: the table years;
    - `minors2c.py`: the date minors;
    - `review2c.py`, `review2c_b.py`, `review2c_c.py`: the real pagers, title places, office
      words, EISA rounds and table years behind C01–C08;
    - `diff2c.py`: revision 1 against revision 2 on every real window;
    - `midway2c.py`: a missing `p3`;
    - `.scratch/plan2c/barmm_build.py`: the subdivisions diff.
  - Run them as `( cd .scratch/plan2c/proto && PYTHONIOENCODING=utf-8 PYTHONDONTWRITEBYTECODE=1 ../../../.venv/Scripts/python.exe <script> … )`.

  The prototypes are measurement tools, not code to copy. When a count differs, diff your units
  and claims against the dump to find the rule that differs, then stop and report. Never change
  the expected value to match.
- **Per task:** follow the Implement-Review loop in the user's CLAUDE.md (at most 3 rounds):
  1. Pre-flight against the current source.
  2. Write the failing test.
  3. Implement.
  4. Run the four gates:
     - `.venv/Scripts/python.exe -m pytest -q`
     - `.venv/Scripts/mypy.exe`
     - `.venv/Scripts/ruff.exe check`
     - `.venv/Scripts/lint-imports.exe --config importlinter.ini`
  5. Run the mutation table.
  6. Commit.
- **Mutations:** one per new test, in `.scratch/mutations/plan2c-task-<N>.json`, in the format of
  `.scratch/mutate.py`.
  - Stage the task's files with `git add` first, and run with `PYTHONDONTWRITEBYTECODE=1`.
  - Choose mutations that fail fast. A loop that runs into `MUTATE_TIMEOUT_S` is a timeout, not a
    kill.
- **Handover:** after every task, record the commit, the Review record rows it verified and the
  next task in two files:
  - `C:/Users/senescalk/Desktop/handovers/elections-v2-plan2c-sdd-ledger.md` (new);
  - `C:/Users/senescalk/Desktop/handovers/elections-v2-RESUME.md`.
- **Hook:** the Desktop PostToolUse hook runs `ruff check --fix` on each edited `.py`. Check
  `git diff --stat` for unrelated rewrites.

## File structure

| Path | Responsibility | Task |
|---|---|---|
| `elections_calendar/sources/tables.py`, `electionguide.py`, `osce.py`, `carter.py`, `elections_calendar/ledger.py`, `elections_calendar/offices.py`, `tests/unit/test_runner.py` | M1–M5, M9, N-8 | 1 |
| `tests/fixtures/{ndi,eisa}/2026-10-19/` | byte-exact captures + `PROVENANCE.md` | 2 |
| `elections_calendar/sources/base.py` | `fetch_chain`, `missing_pages`; the `RawPages` docstring | 2 |
| `elections_calendar/runner.py`, `README.md` | docstring and README sentence for P46 | 2 |
| `elections_calendar/ledger.py` | `CardBlocksRule`, `JsonListRule`, their counters, `discover(…, key)` | 2 |
| `tests/support/pages.py` | `Served`, a fixture-serving getter | 2 |
| `tests/support/slow_adapters.py`, `tests/unit/test_runner.py` | `Chain` and the runner integration case | 2 |
| `elections_calendar/places.py` | `named_places` | 3 |
| `elections_calendar/sources/base.py`, `elections_calendar/offices.py` | `label_scope(…, office_text=)`, `part_scopes`, `unnamed_parts` | 3 |
| `data/subdivisions_manual.yaml`, `data/subdivisions.yaml` | P51 keys | 3 |
| `elections_calendar/sources/ndi.py`, `tests/adapters/test_ndi.py` | NDI adapter | 4 |
| `elections_calendar/sources/eisa.py`, `tests/adapters/test_eisa.py` | EISA adapter | 5 |
| `ledger.COUNT_RULES`, `runner.DEFAULT_ADAPTERS`, `importlinter.ini` | one entry per adapter | 4, 5 |

## Tasks

### Task 1: Plan 2b final-review minors (M1–M5, M9) and N-8

**Files:**
- Modify:
  - `elections_calendar/sources/tables.py` (new `header_problem`, `one_header_table`);
  - `elections_calendar/sources/electionguide.py` (`_columns`; the body-row cells at `:187`);
  - `elections_calendar/ledger.py` (`_HeadTable`, `_HeaderTables`, `_header_rows`);
  - `elections_calendar/sources/osce.py` (the badge list at `:124-126`);
  - `elections_calendar/sources/carter.py` (the row parse);
  - `elections_calendar/offices.py` (`_split_top_level`).
- Test: `tests/unit/test_tables.py`, `tests/adapters/test_osce.py`,
  `tests/adapters/test_electionguide.py`, `tests/unit/test_ledger.py`,
  `tests/adapters/test_carter.py`, `tests/unit/test_runner.py`, `tests/unit/test_offices.py`

**Interfaces:**
- Consumes: `tables.own_rows`, `row_cells`, `cell_text`, `header_columns`; the test builders
  `osce_row`/`osce_page`/`one` (`test_osce.py`), `row`/`carter_page`/`one`/`shape`
  (`test_carter.py`), and the table builder used by ElectionGuide's
  `test_a_repeated_header_is_not_a_layout`.
- Produces:
  - `tables.header_problem(table: Tag) -> str | None`. It returns `None` when the table's own
    `thead` has exactly one own row and every cell in that row is a `th` with no `colspan` or
    `rowspan` other than `"1"`. Otherwise it returns the first failing check's detail:
    1. `"thead has <n> rows"`;
    2. `"thead has a data cell"`;
    3. `"spanned header: <casefolded cell text>"`, for the first such cell.
  - `one_header_table` returns that detail after the "`<n>` tables with headers …" check and
    before the repeated-header check.

**Rules:**
- **M1/M2, the adapters:** `one_header_table` (OSCE, IPU, A-WEB) applies `header_problem`.
  ElectionGuide's `_columns` returns `None` when `header_problem` is not `None`, so the view is
  `layout_not_recognised` as for a missing header.
- **M1/M2, the ledger:** `_header_rows` returns `None` for the same three shapes, on its own parse.
  - `_HeadTable` gains `head_rows: int = 0`, `head_td: bool = False` and
    `head_span: bool = False`.
  - A `tr` start tag inside the table's own `thead` counts a row.
  - A `td` there sets `head_td`.
  - A `th` or `td` there with a `colspan` or `rowspan` whose stripped value is not `"1"` sets
    `head_span`.
- **M3:** ElectionGuide reads `row_cells(tr)`.
- **M4:** OSCE's badge texts are collected in page order, cell by cell. In the date cell they are
  the non-empty texts of the `span`s that are not inside its date `div`. In every other cell they
  are the non-empty texts of `span` elements with class `badge`. The rest of P30 is unchanged.
- **M5:** Carter's `extra` is the non-empty texts of the third and later cells.
  - The leftover becomes `", ".join(bad + future + extra)`.
  - With claims, the partial reasons are, in order: `date_unparsed`, `implausible_date`,
    `extra_cells`, `place_unregistered`, `link_rejected`.
  - In the no-claims (`not made`) path the reason is unchanged, and the leftover holds `extra`
    too.
- **N-8:** at each position, a separator matches when `text[i : i + len(sep)].casefold() == sep`.
- **Fixtures are unchanged** (measured by `task1_2c.py` and `ledger_m1.py`):
  - all 10 fixture tables with a `thead` of `th` cells pass `header_problem`;
  - the ledger counts stay OSCE 634, A-WEB 32 and IPU 281 (both captures);
  - OSCE's 634 date cells each hold one `span.badge` outside the date `div`, and the country
    cells hold `span.elections-country`;
  - every Carter row has 2 cells, apart from the one-cell footnote;
  - ElectionGuide has no body `th`;
  - the OSCE, ElectionGuide and Carter fixture results are identical before and after.

  Every existing test passes unchanged.

- [ ] **Step 1: Write the failing tests.**
  - **`test_tables.py`, `test_header_problem`** (parametrized; the `thead` content of
    `<table><thead>…</thead><tbody><tr><td>x</td></tr></tbody></table>`):

    | `thead` | result |
    |---|---|
    | `<tr><th>Date</th><th>Country</th></tr>` | `None` |
    | `<tr><th colspan="1">Date</th></tr>` | `None` |
    | `<tr><th>Date</th></tr><tr><th>Country</th></tr>` | `"thead has 2 rows"` |
    | `<tr><th>Date</th></tr><tr><td>25 Oct 2026</td></tr>` | `"thead has 2 rows"` (M2) |
    | `<tr><th>Date</th><td>Country</td></tr>` | `"thead has a data cell"` |
    | `<tr><th colspan="2">Date</th></tr>` | `"spanned header: date"` |
    | `<tr><th rowspan=" 2 ">Start Date</th></tr>` | `"spanned header: start date"` |
    | (a table with no `thead`) | `"thead has 0 rows"` |

    A nested table's `thead` rows are not the outer table's: an outer `thead` of one row whose
    `th` holds `<table><thead><tr><th>a</th></tr><tr><th>b</th></tr></thead></table>` → `None`.
  - **`test_osce.py`, `test_irregular_headers_fail_the_page`** (`osce_page([osce_row()])`, edited;
    both are `ok` and parsed today):
    - `<th>Date</th>` → `<th colspan="2">Date</th>` → `layout_not_recognised`,
      `"spanned header: date"`, no units;
    - a second `thead` row `<tr><th>Note</th></tr>` → `"thead has 2 rows"`, no units.
  - **`test_electionguide.py`, `test_an_irregular_header_is_not_a_layout`** (`eg_page(HEADERS, [row()])`
    as the `upcoming` view, edited; both are `ok` and parsed today):
    - `colspan="2"` on "Start Date" → `upcoming` coverage `layout_not_recognised`, no
      `electionguide:upcoming/` units;
    - a second `thead` row `<tr><th>x</th></tr>` → the same.
  - **`test_electionguide.py`, `test_a_th_body_cell_is_a_cell`:** the `row()` page with
    `<td>Sweden</td>` replaced by `<th scope="row">Sweden</th>` gives the same unit (parsed, text
    `"Sweden | Swedish Riksdag | 2026-11-01 (d) | 2026-11-01 (d) | Confirmed | No"`) and the same
    claim as the plain page. Today the unit is unparsed `date_unparsed`, without "Sweden" in its
    text.
  - **`test_ledger.py`, `test_header_table_rows_reject_irregular_headers`:**
    `discover(HeaderTableRowsRule(frozenset({"date", "country"})), page)`, where `page` is one table
    with the given `thead` and 3 body rows of 2 `td` cells each:
    - `<tr><th>Date</th><th>Country</th></tr><tr><th>a</th><th>b</th></tr>` → `None`;
    - `<tr><th colspan="2">Date</th><th>Country</th></tr>` → `None`;
    - `<tr><th>Date</th><th>Country</th><td>x</td></tr>` → `None`;
    - `<tr><th>Date</th><th>Country</th></tr>` → `("r1", "r2", "r3")`.

    The first three give `("r1", "r2", "r3")` today.
  - **`test_osce.py`, `test_badge_scope`** (`one(**kw)`):

    | `osce_row` argument | Result after M4 | Today |
    |---|---|---|
    | `date_cell='<td><div><span>25 Oct</span> 2026</div><span class="badge">Upcoming</span></td>'` | parsed, leftover `""`, `status_claim is None` | partial `status_unrecognised`, leftover `"25 Oct"` |
    | `label='Presidential Election <span class="badge">Postponed</span>'` | parsed, `status_claim == "postponed"`, `office_label == "Presidential Election Postponed"` | parsed, `status_claim is None` |
    | `activity='<span>Report</span>'` | parsed, `status_claim is None` (a plain span outside the date cell is not a badge) | the same |
    | `activity='<span class="badge">Rescheduled</span>'` | partial `status_unrecognised`, leftover `"Rescheduled"` | parsed |

  - **`test_carter.py`, `test_extra_cells_are_leftover`** (`row(country, dates)` with
    `<td>{extra}</td>` added before `</tr>`, in `carter_page`; `parse` checks the ledger):

    | country, dates, extra | Result after M5 | Today |
    |---|---|---|
    | "Chile", "May 2026", "with the OAS" | partial `extra_cells`, leftover `"with the OAS"`, 1 claim | parsed |
    | "Chile", "May 2026, Bogus", "note" | partial `date_unparsed`, leftover `"Bogus, note"` | leftover `"Bogus"` |
    | "Chile", "TBC", "note" | unparsed `date_unparsed`, leftover `"TBC, note"` | leftover `"TBC"` |
    | "Chile", "May 2026", `" "` | parsed, leftover `""` | the same |
    | "Atlantis", "May 2026", "note" | partial `extra_cells`, leftover `"note"`, claim `unknown:atlantis` | partial `place_unregistered` |
  - **`test_runner.py`, `test_every_adapter_module_is_registered`:** the modules
    `elections_calendar.sources.<stem>` for each `elections_calendar/sources/*.py`, except
    `__init__`, `base` and `tables`, equal the importlinter `adapters` modules and the
    `DEFAULT_ADAPTERS` target modules.
  - **`test_offices.py`, `test_split_top_level_when_casefold_changes_length`:**
    - `_split_top_level("Großrat and Senate", (" and ",)) == ["Großrat", "Senate"]`;
    - `_split_top_level("İl Genel Meclisi and Senate", (" and ",)) == ["İl Genel Meclisi", "Senate"]`;
    - today they give `["Großrat ", "enate"]` and `["İl Genel Meclisi ", "enate"]` (measured).
- [ ] **Step 2: Run** the seven files. Expected: the new tests FAIL; `test_every_adapter_module_is_registered`
  passes today and must still pass.
- [ ] **Step 3: Implement** the rules above.
- [ ] **Step 4: Run** the seven files. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:**
  `fix(sources): header shape checks, row-header cells, badge scope, Carter extra cells, casefold offsets`.

  Mutations, one each:
  - drop the span check in `header_problem`;
  - drop the `header_problem` call in `one_header_table`;
  - drop it in ElectionGuide's `_columns`;
  - ElectionGuide body cells back to `td` only;
  - drop the counter's `head_rows != 1` condition;
  - badges back to every `span` in the date cell;
  - drop `extra` from Carter's leftover and reasons;
  - remove `elections_calendar.sources.eeas` from `importlinter.ini`;
  - restore `lowered.startswith(sep, i)`.

---

### Task 2: Fixtures, the chain contract, the served getter and two discovery rules

**Files:**
- Create:
  - `tests/fixtures/ndi/2026-10-19/p0.html` … `p4.html` and `PROVENANCE.md`;
  - `tests/fixtures/eisa/2026-10-19/calendar.html`, `y2026.json`, `y2025.json` and
    `PROVENANCE.md`.
- Modify:
  - `elections_calendar/sources/base.py` (new functions; the `RawPages` docstring);
  - `elections_calendar/runner.py` (the `SourceRun` docstring);
  - `README.md:102`;
  - `elections_calendar/ledger.py`;
  - `tests/support/pages.py`;
  - `tests/support/slow_adapters.py` (`Chain`).
- Test: `tests/unit/test_fixtures.py`, `tests/unit/test_sources_base.py`, `tests/unit/test_ledger.py`,
  `tests/unit/test_runner.py`

**Interfaces:**
- Consumes: `base.Getter`, `PageRequest`, `RawPage`, `RawPages`, `model.Reason`,
  `fetch.Deadline`, `fetch.FetchResult`, `tests.support.pages.result`.
- Produces, in `base.py`:
  - `fetch_chain(expected: Callable[[Sequence[RawPage]], Sequence[PageRequest]], fetcher: Getter, deadline: Deadline, *, now: Callable[[], datetime] = lambda: datetime.now(UTC)) -> Iterator[RawPage]`.
    It is lazy. Each step takes the first request in `expected(pages so far)` whose key has not
    been fetched, fetches it and yields its `RawPage`. It stops when there is none.
  - `missing_pages(expected: Sequence[PageRequest], raw: RawPages) -> list[Reason]`: one
    `Reason("pagination_incomplete", f"{request.key} was not fetched")` per expected request
    whose key is in neither `raw.pages` nor `raw.unfinished`, in `expected` order.
- Produces, in `ledger.py`:
  - `CardBlocksRule(blocks: tuple[tuple[str, str], ...], wrapper: str)`: pairs of (element id,
    slug), and the wrapper's class. The units are `<slug>-c<i>`.
  - `JsonListRule(skip_keys: frozenset[str])`: the units are `r1 … rn`, and `()` for a page key
    in `skip_keys`.
  - `CountRule` gains both types.
  - `discover(rule: CountRule, body: bytes, key: str = "") -> tuple[str, ...] | None`. Only
    `JsonListRule` reads `key`, and `_discovery_problems` passes `entry.key`. The existing 30
    call sites do not change.
- Produces, in `tests/support/pages.py`:
  - `Served(bodies: Mapping[str, bytes], content_type: str = "text/html; charset=UTF-8")`, with
    `asked: list[str]` and `get(url, *, deadline, mediawiki=False) -> FetchResult`.
  - A known URL gives `ok`, status 200, its body, `content_type`, and `url == final_url == url`.
  - Any other URL gives `http_error`, status 404, an empty body.
  - One content type serves every URL. Only its charset matters (`FetchResult.text`); EISA's
    JSON is read from the body bytes.
- Produces, in `tests/support/slow_adapters.py`:
  - `Chain(urls: str)`, a `_Base` adapter. `urls` is comma-separated; request `i` is
    `PageRequest(KEYS[i], url_i)`.
  - `requests(window)` is the first request only. `expected(pages)` is the first
    `len(pages) + 1` requests. `fetch` is `fetch_chain(self.expected, fetcher, deadline)`.

- [ ] **Step 1: Copy the captures byte for byte** with `cp`, never through an editor:

  | From `.scratch/plan2c/captures-2026-10-19/` | To |
  |---|---|
  | `ndi_p0.html` … `ndi_p4.html` | `tests/fixtures/ndi/2026-10-19/p0.html` … `p4.html` |
  | `eisa_calendar.html` | `tests/fixtures/eisa/2026-10-19/calendar.html` |
  | `eisa_38978.json` | `tests/fixtures/eisa/2026-10-19/y2026.json` |
  | `eisa_34700.json` | `tests/fixtures/eisa/2026-10-19/y2025.json` |

  Then `sha256sum tests/fixtures/{ndi,eisa}/2026-10-19/*.*` must print the digests below. Leave
  out `PROVENANCE.md`, which is not written yet.
- [ ] **Step 2: Write the two notes,** following Plan 2b's OSCE note
  (`tests/fixtures/osce/2026-10-18/PROVENANCE.md`).
  - Each note lists, per file: the URL (the final URL is the same, no redirect), the fetched
    time, HTTP 200 after 1 attempt, the content type, the bytes and the SHA-256.
  - The digest goes on a line `- **SHA-256 of `<file>`:** <digest>`, which is the format
    `test_fixtures.SHA_LINE` reads.
  - Both notes name `Fetcher` + `trust_bundle` (certifi + REQUESTS_CA_BUNDLE) and the tests
    that use the files.

  | File | URL | Fetched (UTC) | Content type | Bytes | SHA-256 |
  |---|---|---|---|---|---|
  | `ndi/…/p0.html` | `https://www.ndi.org/elections-calendar?page=0` | 2026-10-19T08:57:34 | `text/html; charset=UTF-8` | 310524 | 06972eace847fd60638d3546e46c72b35d0fb646af08564c4716e22458ebcca0 |
  | `ndi/…/p1.html` | `…?page=1` | 2026-10-19T08:57:36 | same | 306453 | e2ec1cfdb5f1a200f631c4e66d7ec15c390698a5b70b882328f93fb88a0b5e0f |
  | `ndi/…/p2.html` | `…?page=2` | 2026-10-19T08:57:37 | same | 290465 | f9509d1e1081dda53ab2d52c97c32ff1132d44fafd6a9336cfefbb2e2fce7d9c |
  | `ndi/…/p3.html` | `…?page=3` | 2026-10-19T08:57:38 | same | 291599 | b915d2aeb76997652d599fa476a8dfb35190a5678475e18e4c735aca38c0c1d4 |
  | `ndi/…/p4.html` | `…?page=4` | 2026-10-19T08:57:40 | same | 291701 | b75b81d98dae07f2e973044440cb937cade8487926cd6e9f472b45823431cfd6 |
  | `eisa/…/calendar.html` | `https://www.eisa.org/election-calendar/` | 2026-10-19T08:57:41 | `text/html; charset=UTF-8` | 533005 | 279af67ad407f4b449a922becfb6cdd605192852e442ae4d7ceef3edeb213de7 |
  | `eisa/…/y2026.json` | `https://www.eisa.org/wp-admin/admin-ajax.php?action=wp_ajax_ninja_tables_public_action&table_id=38978&target_action=get-all-data` | 2026-10-19T08:57:53 | `application/json; charset=UTF-8` | 4596 | ab511342bbf04e9d5736f939ca2c488bccef56719f25f62c351d3a96322e84f0 |
  | `eisa/…/y2025.json` | the same with `table_id=34700` | 2026-10-19T08:57:50 | same | 4872 | bfd5c134a15dfe303a3a51dcffc3b345c6a90ae185a6d2ffb636fc7563473b3c |

- [ ] **Step 3: Write the failing tests.**
  - **`test_fixtures.py`, `test_every_fixture_file_matches_its_provenance_note`:** the expected
    directory list gains `"eisa/2026-10-19"` (after `"eeas/2026-10-18"`) and `"ndi/2026-10-19"`
    (after `"ipu/2026-10-18"`).
  - **`test_sources_base.py`:**
    - **`test_fetch_chain`:** `expected` returns `p0` and, for each received page whose body is
      `b"more"`, the next key's request. With `Served` holding `u0`/`u1` = `b"more"` and
      `u2` = `b"end"`:
      - the chain yields 3 pages, in order;
      - `asked == [u0, u1, u2]`;
      - each `fetched_at` is the `now` stub's value.

      With an `expected` that always returns `[p0]`, there is exactly one fetch, then the
      iterator ends.
    - **`test_fetch_chain_is_lazy`:** `next()` on the iterator asks exactly one URL.
    - **`test_missing_pages`:** with `expected` (a, b, c), page a received and b unfinished →
      `[Reason("pagination_incomplete", "c was not fetched")]`. With all three received → `[]`.
  - **`test_ledger.py`:**
    - **`test_card_blocks_and_json_lists_count_the_fixtures`:**
      - with `CardBlocksRule((("upcoming-elections", "upcoming"), ("past-elections", "past")), "election-wrapper")`:
        - `p0` → 20 IDs, `upcoming-c1 … upcoming-c10, past-c1 … past-c10`;
        - `p1` → 18 IDs, `upcoming-c1 … upcoming-c8, past-c1 … past-c10`;
        - `p2`, `p3` and `p4` → 10 IDs each, `past-c1 … past-c10`;
      - with `JsonListRule(frozenset({"calendar"}))`:
        - `y2026.json` → 22 IDs (`r1 … r22`);
        - `y2025.json` → 23 IDs;
        - `calendar.html` with key `"calendar"` → `()`;
        - `calendar.html` with key `"y2026"` → `None`.
    - **`test_card_blocks_on_synthetic_pages`** (each block is
      `<div id="…"><div class="bound">…</div></div>`; a card is
      `<div class="partial"><div class="text"><div>x</div></div>text</div>`; the past block
      holds one card unless noted; measured by `counters2c.py`):
      - two wrappers in the upcoming block → `None`;
      - a second `id="upcoming-elections"` element → `None`;
      - no `id="past-elections"` → `None`;
      - the upcoming block holding only `<p>No Results Found</p>` → `("past-c1",)`;
      - two cards with loose text between them → `("upcoming-c1", "upcoming-c2", "past-c1")`:
        a card's own `div`s and text nodes do not count;
      - two cards with a `<br>` between them →
        `("upcoming-c1", "upcoming-c2", "upcoming-c3", "past-c1")`;
      - a wrapper with `class="x election-wrapper"` → `("upcoming-c1", "past-c1")`.
    - **`test_json_lists_on_synthetic_bodies`** (`JsonListRule(frozenset({"calendar"}))`, key
      `"y2026"` unless noted):
      - `b"[]"` → `()`;
      - `b'[1, {"a": 2}]'` → `("r1", "r2")`;
      - `b"{}"` → `None`;
      - `b"<html>"` → `None`;
      - `b"garbage"` with key `"calendar"` → `()`.
    - **`test_discovery_uses_the_page_key`:** `check(raw, result, rules={"eisa": JsonListRule(frozenset({"calendar"}))})`,
      built with `tests.support.pages.raw_pages` and `unit`.
      - `raw` holds a `calendar` page (an HTML body) and a `y2026` page (`b'[{}, {}]'`).
      - `result` has coverage `calendar` (`ok`, prefix `eisa:calendar/`, 0 units seen) and
        `y2026` (`ok`, prefix `eisa:y2026/`, 2 units seen), and the units `eisa:y2026/r1` and
        `r2`.
      - The report is `ok`.
      - With an extra unit `eisa:calendar/r1`, the reasons are `["discovery_mismatch"]`.
  - **`test_runner.py`, `test_a_chained_source_cut_mid_chain`** (C01; uses the existing
    `server` and `ca_env` fixtures; measured by `.scratch/plan2c/runnerproto/`, 2.9 s):
    - routes `/a` and `/b` reply at once; `/c` replies with `header_drip=0.5`;
    - `run_sources([AdapterSpec("chain", "tests.support.slow_adapters:Chain", (("urls", "<a>,<b>,<c>"),))], WINDOW, workdir=tmp_path, environ=ca_env, source_deadline_s=2, grace_s=2)`;
    - the one run's outcome is `"deadline"`;
    - its page keys are `["one", "two"]` (the chained page `two` is kept);
    - `raw.unfinished == ()` (only `one` was named up front, and it was received);
    - `missing_pages(Chain(urls).expected(raw.pages), raw) == [Reason("pagination_incomplete", "three was not fetched")]`.

    This pins the runner as it is today: it needs no change for chained pages.
- [ ] **Step 4: Run** the four files. Expected: FAIL on import.
- [ ] **Step 5: Implement.**
  - **The counters** share nothing with the adapters (P6).
    - `CardBlocksRule` uses stdlib `html.parser`, with a tag stack and the void elements.
      - Inside the element whose `id` is a block id, it finds the `div` whose `class` list holds
        `wrapper`, and counts that div's direct element children.
      - It returns `None` when a block id appears other than exactly once, or a block holds
        more than one wrapper.
    - `JsonListRule` uses `json.loads`. It returns `None` on `ValueError` or `RecursionError`,
      and for a body that is not a list.
  - **Docstrings and README** (P46):
    - **`RawPages`** and **`SourceRun`:** `unfinished` lists only up-front requests (those of
      `requests(window)`). A chained adapter reports a later page it expected but did not
      receive as `pagination_incomplete`.
    - **`README.md:102`:** after the sentence "A received page that cannot be read stays
      unfinished, and its source becomes `worker_failed`.", add: "A source whose later pages depend on earlier
      ones (NDI's pager, EISA's year tables) names only its first page up front; its adapter
      reports any later page it expected but did not receive as `pagination_incomplete`."
- [ ] **Step 6: Run** the four files. Expected: PASS.
- [ ] **Step 7: Gates, mutation table, commit:**
  `feat(sources): chained requests, NDI and EISA fixtures, card-block and JSON-list rules`.

  Mutations, one each (`test_fixtures.py` lists files and needs none):
  - stop `fetch_chain` after its first page;
  - build the chain's list before yielding;
  - drop the `unfinished` keys from `missing_pages`;
  - count every descendant of the wrapper;
  - count a skip key's page;
  - drop the `key` from `_discovery_problems`'s `discover` call;
  - in `runner._collect`, keep only the pages whose key is in the slot's up-front requests.

---

### Task 3: Shared label helpers, and the BARMM names (P48, P51, P63, P64)

**Files:**
- Modify:
  - `elections_calendar/places.py` (`named_places`);
  - `elections_calendar/sources/base.py` (`label_scope`);
  - `elections_calendar/offices.py` (`unnamed_parts`);
  - `data/subdivisions_manual.yaml`, then rebuild `data/subdivisions.yaml`
    (`.venv/Scripts/python.exe -m scripts.build_subdivisions`).
- Test: `tests/unit/test_places.py`, `tests/unit/test_subdivisions.py`,
  `tests/unit/test_sources_base.py`, `tests/unit/test_offices.py`

**Interfaces:**
- Consumes: `places._LABEL_WORD`, `_MAX_RUN`, `named_subdivisions`, `PlaceRegistry.resolve`,
  `Place.parent`, `base.label_scope`, `offices.classify`, `claim_level`, `_split_top_level`,
  `office_class_of`, `text.collapse_ws`.
- Produces:
  - `named_places(text: str, places: PlaceRegistry) -> list[tuple[str, Place]]`:
    - the words are `_LABEL_WORD.findall(text)`;
    - runs of `_MAX_RUN` words down to 1 are tried, leftmost first within one length;
    - a run is taken when none of its words is taken yet and `places.resolve` gives a
      registered place; its words become taken;
    - only the first run per place ID is kept;
    - a place that is the `parent` of another kept place is dropped (the child refines it);
    - the result is (the run's words joined by one space, the place), in text order.
  - `label_scope(label: str, place: Place, registries: Registries, default: Level = "national", *, office_text: str | None = None) -> LabelScope`.
    The subdivisions still come from `label`. The office is `classify(office_text if office_text is not None else label, …)`.
    The docstring says so.
  - `part_scopes(parts: Sequence[str], place: Place, registries: Registries, default: Level = "national") -> list[LabelScope]`
    in `base.py`, one scope per part, in order (P63):
    - **leading subdivisions:** walk `named_subdivisions(parts[0], …)` in order while each run's
      words (`run.split(" ")`) continue the first part's `_LABEL_WORD` words from the start;
    - a part's subdivisions are `named_subdivisions(part, …)`, or the leading ones when it names
      none;
    - each scope is built as `label_scope` builds one, with those subdivisions and
      `classify(part, …)`;
    - `part_scopes([label], …) == [label_scope(label, …)]`.

    `label_scope` and `part_scopes` share one private builder, so the two cannot drift.
  - `unnamed_parts(text: str, place_id: str, registry: InstitutionRegistry) -> list[str]`:
    - the parts are `_split_top_level` at `","`, then each piece at `" and "` and `" & "`, all
      `collapse_ws`'d, empty ones dropped;
    - with 2 or more parts, of which some but not all have an `office_class_of`, it returns the
      parts that have none, in order;
    - else `[]`.
  - `data/subdivisions.yaml` gains `bangsamoro: PH-14` and `barmm: PH-14`, after
    `autonomous region in muslim mindanao: PH-14`.

- [ ] **Step 1: Write the failing tests.**
  - **`test_places.py`, `test_named_places`** (parametrized; measured by `task3_r2.py`):

    | text | result |
    |---|---|
    | `"2026 Bosnia and Herzegovina General Elections"` | `[("Bosnia and Herzegovina", "iso:BA")]` |
    | `"2026 Philippines (BARMM) Parliamentary Elections"` | `[("Philippines", "iso:PH")]` |
    | `"2027 El Salvador General Election"` | `[("El Salvador", "iso:SV")]` |
    | `"2026 Republic of the Congo Presidential Election"` | `[("Republic of the Congo", "iso:CG")]` (the longer run takes "Congo") |
    | `"Guinea-Bissau 2026 General Elections"` | `[("Guinea-Bissau", "iso:GW")]` |
    | `"2026 Trinidad and Tobago Presidential and Local Elections"` | `[("Trinidad and Tobago", "iso:TT")]` |
    | `"2026 Niger and Nigeria Elections"` | `[("Niger", "iso:NE"), ("Nigeria", "iso:NG")]` |
    | `"2026 DRC Congo Elections"` | `[("DRC", "iso:CD"), ("Congo", "iso:CG")]` |
    | `"2026 United Kingdom Scotland Parliamentary Election"` | `[("Scotland", "iso:GB-SCT")]` (the parent is dropped) |
    | `"2026 Côte d'Ivoire (Ivory Coast) Presidential Election"` | `[("Côte d'Ivoire", "iso:CI")]` (one per place ID) |
    | `"2026 Narnia General Election"` | `[]` (unregistered places are never returned) |
    | `""` | `[]` |

    The test compares `[(words, place.place_id), …]`.
  - **`test_sources_base.py`, `test_label_scope_office_text`** (`REGISTRIES` with the P51
    keys; `<NG>` etc. are `REGISTRIES.places.resolve("Nigeria")` etc.):

    | label, place, default, `office_text` | `office_class`, `level`, `jurisdiction`, `jurisdiction_kind`, `unresolved` |
    |---|---|
    | "Osun Governor and State Assembly", `<NG>`, national, "State Assembly" | legislature, subnational, "Osun", subdivision, `False` |
    | the same, "Osun Governor" | governor, subnational, "Osun", subdivision, `False` |
    | "2026 Philippines (BARMM) BSKE Elections", `<PH>`, subnational, "Regional" | local_council (`aggregate=True`), subnational, "BARMM", subdivision, `False` |
    | "President and National Assembly", `<TD>`, national, "National Assembly" | lower_house (`iso:TD/national-assembly`), national, `None`, nationwide, `False` |

    With `office_text=None`, the result equals the call without the keyword, for each of the
    three labels.
  - **`test_sources_base.py`, `test_part_scopes`** (the follow-up review's sibling-scope
    boundary; `<NG>` Nigeria, `<PH>` Philippines, default national; measured by `task3_r3.py`):

    | parts, place | per part: `office_class`, `level`, `jurisdiction` (`jurisdiction_kind`) |
    |---|---|
    | ["Presidential", "Osun Governor"], `<NG>` | head_of_state, national, `None` (nationwide); governor, subnational, "Osun" (subdivision) |
    | ["President", "Osun State Assembly"], `<NG>` | head_of_state, national, `None`; legislature, subnational, "Osun State" |
    | ["Osun Governor", "State Assembly"], `<NG>` | governor, subnational, "Osun"; legislature, subnational, "Osun" (leading) |
    | ["Osun Governor", "Lagos State Assembly"], `<NG>` | governor, subnational, "Osun"; legislature, subnational, "Lagos State" (its own wins) |
    | ["(BARMM) Parliamentary", "Local Elections"], `<PH>` | legislature, unknown, "BARMM" (`unresolved=True`); local_council, subnational, "BARMM" |
    | ["Presidential", "Local Elections"], `<PH>` | head_of_state, national, `None`; local_council, subnational, `None` |

    `part_scopes([label], …) == [label_scope(label, …)]` for "Osun Governor",
    "2026 Philippines (BARMM) Parliamentary Elections" and "Presidential".
  - **`test_offices.py`, `test_unnamed_parts`** (parametrized; place `iso:TD` unless noted):

    | text | result |
    |---|---|
    | "President and Xyz" | `["Xyz"]` |
    | "Presidential and Xyz Elections" (`iso:CL`) | `["Xyz Elections"]` |
    | "President, Senate and Xyz" | `["Xyz"]` |
    | "President & Xyz" | `["Xyz"]` |
    | "President and National Assembly" | `[]` (both name an office) |
    | "Regional and local" | `[]` |
    | "Xyz and Abc" | `[]` (neither names an office: `office_unrecognised` covers it) |
    | "President (first and second round)" | `[]` (the "and" is not top level) |
    | "General Elections", "" | `[]` |
  - **`test_subdivisions.py`, `test_barmm_names_the_bangsamoro_region`:** in the loaded
    `SubdivisionIndex`, `find("PH", "BARMM")` and `find("PH", "Bangsamoro")` are both `"PH-14"`.
    `test_committed_subdivisions_yaml_is_up_to_date` must pass after the rebuild.
  - **`test_sources_base.py`, `test_label_scope_names_barmm`:** `label_scope("2026 Philippines (BARMM) Parliamentary Elections", <iso:PH>, REGISTRIES)`
    gives:
    - `office.office_class == "legislature"`;
    - `level == "unknown"`;
    - `jurisdiction == "BARMM"`;
    - `jurisdiction_kind == "subdivision"`;
    - `unresolved is True`.
- [ ] **Step 2: Run** the four files. Expected: FAIL.
- [ ] **Step 3: Implement** `named_places`, the `office_text` keyword, `part_scopes` and
  `unnamed_parts`. Add
  the manual line and rebuild. `git diff --stat data/subdivisions.yaml` must show 2 insertions
  and nothing else (measured by `.scratch/plan2c/barmm_build.py`).
- [ ] **Step 4: Run** the full suite. Expected: PASS, with every existing test unchanged
  (measured: no other adapter's output changes; no existing caller passes `office_text`).
- [ ] **Step 5: Gates, mutation table, commit:**
  `feat(places): title places, label scope by part, unnamed parts and the BARMM names`.

  Mutations, one each:
  - return unregistered places from `named_places`;
  - keep a parent next to its child in `named_places`;
  - return only the first place from `named_places`;
  - classify `label` even when `office_text` is given;
  - `part_scopes` gives every part the subdivisions of all the parts (revision 2's rule);
  - `part_scopes` ignores the leading subdivisions;
  - `unnamed_parts` returns `[]` when any part names an office;
  - delete the manual line (then rebuild in the scratch copy only, or mutate the yaml);
  - drop the subdivision pass in `label_scope` (`subs = ()`).

---

### Task 4: NDI adapter

**Files:**
- Create: `elections_calendar/sources/ndi.py`, `tests/adapters/test_ndi.py`
- Modify:
  - `COUNT_RULES` (add `"ndi"`);
  - `DEFAULT_ADAPTERS` (after `wikipedia`, before `aweb`, §10.5);
  - `importlinter.ini`;
  - `test_runner.py:392`.

**Interfaces:**
- Consumes:
  - from Task 2: `base.fetch_chain`, `missing_pages`, `Served`;
  - from Task 3: `places.named_places`, `label_scope(…, office_text=)`, `part_scopes`,
    `offices.unnamed_parts`;
  - `base.parse_pages`, `PageParse`, `page_failure`;
  - `tables.complete_html`, `cell_text`;
  - `dates.parse_date_text`, `plausible`, `relevance`;
  - `offices.is_executive_title`, `split_offices`, `extract_round`;
  - `text.collapse_ws`;
  - `model.DateSpan`, `month_end`.
- Produces:
  - `class Ndi` with `source = "ndi"`;
  - `URL = "https://www.ndi.org/elections-calendar"`, `CAP = 10`;
  - `PAGE_SIZE = 10`: NDI's cards per page. This is a source assumption, measured on p0–p4
    (2026-10-19). Its comment says so, and that it must be revised against a new capture if NDI
    changes it;
  - `BLOCKS = (("upcoming-elections", "upcoming"), ("past-elections", "past"))`,
    `WRAPPER = "election-wrapper"`;
  - `request(n: int) -> PageRequest` = `PageRequest(f"p{n}", f"{URL}?page={n}")`;
  - `expected(window: Window, pages: Sequence[RawPage]) -> tuple[PageRequest, ...]`;
  - `SUBNATIONAL_TYPES` and `NATIONAL_TYPES` (frozensets of casefolded terms):
    - `SUBNATIONAL_TYPES` = commune council, gubernatorial, local, local runoff, local phase 1,
      local phase 2, local phase 3, local phase 4, municipal, municipal runoff, parochial,
      provincial assembly, regional, state assembly (14);
    - `NATIONAL_TYPES` = by-election, constitutional assembly, executive, general,
      general runoff, legislative, legislative runoff, national assembly, national council,
      parliamentary, parliamentary by-election, parliamentary phase 1, parliamentary phase 2,
      parliamentary phase 3, parliamentary phase 4, parliamentary re-run, parliamentary runoff,
      presidential, presidential and parliamentary,
      presidential and parliamentary by-election, presidential and parliamentary phase 1,
      presidential and parliamentary phase 2, presidential and parliamentary phase 3,
      presidential and parliamentary phase 4, presidential and parliamentary re-run,
      presidential and parliamentary runoff, presidential by-election, presidential phase 1,
      presidential phase 2, presidential phase 3, presidential re-run, presidential referendum,
      presidential runoff, re-run presidential runoff, referendum, referendum phase 1,
      referendum phase 2, senatorial, senatorial by-election (39).

**Rules:**
- **Requests and fetch (P46):**
  - `requests(window)` is `(request(0),)`.
  - `fetch` is `fetch_chain(lambda pages: expected(window, pages), fetcher, deadline)`.
  - `expected` starts with `request(0)`. While `n < CAP - 1`, it adds `request(n + 1)` when page
    `p<n>` is received, its download is clean, it reads (below), and it wants more (P50).
  - A `RecursionError` while reading ends the chain.
- **A card** is one direct element child of a block's wrapper. Its fields:
  - **title:** `cell_text` of its `h3.heading`;
  - **date text:** `cell_text` of `.date-type .date`;
  - **type terms:** the `.date-type` element's own (non-tag) text, split into lines, each line
    whitespace-collapsed, empty ones dropped;
  - **location:** the whitespace-collapsed `data-location` of its `button.add-to-cal`.

  Each field is `""` when its element is missing. The card's **raw day** is set only when
  `parse_date_text(date text)` is `ok` with one span of day precision whose start equals its end.
- **Reading a page `p<n>`** gives the blocks, or the first failing check's
  `layout_not_recognised` detail:

  | Check | Detail |
  |---|---|
  | the text is complete HTML | `"page does not end with </html>"` |
  | each block id appears exactly once | `"block #<id> appears <k> times"` |
  | at most one wrapper `div` per block | `"<slug> block has <k> card lists"` |
  | at most one `nav.pager` per block | `"<slug> block has <k> pagers"` |
  | with a pager: its one `li.is-active > a` href fullmatches `\?page=([0-9]{1,3})` | `"<slug> block has no current page"` |
  | with a pager and no `rel="next"` link: the active `li` is the pager's last `li` (C01) | `"<slug> block has later pages but no next link"` |
  | with no pager: fewer than `PAGE_SIZE` cards (C01) | `"<slug> block has <c> cards and no pager"` |
  | (active page = that number; 0 with no pager) the block is on page `n` with cards, or on an earlier page with none | `"<slug> block is page <active> with <c> cards"` |
  | raw days ascend (upcoming) or descend (past), ties allowed | `"<slug> block is not in date order"` |

  A block has a next page when a pager link has `rel="next"`.
- **Parse, per received page, in fetch order,** after reading. Steps 1 and 2 look only at
  blocks that have cards, and only those blocks update the state (C06):
  1. **Repeats:** a block's set of card titles equal to the set of that block on an earlier
     accepted page → `"<slug> block repeats p<m>"`.
  2. **Order across pages:** a block's first raw day out of order against its last raw day on
     the most recent accepted page that had one → `"<slug> block is not in date order after p<m>"`.
  3. **Cards:** `ndi:p<n>/<slug>-c<i>`, upcoming first, `i` from 1.

  Then the notes: `missing_pages(expected(window, raw.pages), raw)`, and the cap note when `p9`
  is received, clean, readable and still wants more.
- **A card's unit:**
  - **Text:** `" | ".join` of the title, the date text, `", ".join(terms)` and the location,
    skipping empty parts (C02).
  - **Relevance:** `relevance(date text, window.start)`.
  - **Checks, in order:**
    1. **ignored `duplicate`** (P61): (title, date text, terms, location) equal those of an
       earlier card that gave a claim; `duplicate_of` is that card's unit ID;
    2. **unparsed `title_missing`;**
    3. **unparsed `date_missing`:** no date text;
    4. **unparsed `place_ambiguous`** (two or more title places and no registered location;
       leftover = their words joined by ", ") or **`place_missing`** (no place), per P48;
    5. **unparsed `date_missing`:** the parse is `ok` with no span;
    6. **unparsed `date_unparsed`:** no raw day, or a status word; leftover = the parse's
       leftover, or else the date text;
    7. **unparsed `implausible_date`:** the raw day is not `plausible`;
    8. **unparsed `office_not_modelled`:** `is_executive_title(title)`; leftover = the title.
  - **Office words** (P49): the title with each `named_places` run removed, then every
    `\b[0-9]{4}\b`, then every empty `()`, then `collapse_ws`. A run is removed with its words
    joined by any non-word separators (`[^\w'’-]+`), and only where it is not part of a longer
    word.
  - **Parts** (P49): `split_offices(office words, …)` when it gives 2 or more, else `[title]`.
    The type fallback replaces them with `split_offices(joined terms, …) or [joined terms]` under
    P49's condition.
  - **Partial reasons, in order:**
    1. `place_conflict` (leftover = the other title places' words, joined by ", ");
    2. `place_unregistered`;
    3. `type_unrecognised` (leftover = the unknown terms joined by ", ");
    4. `round_conflict` (fallback only; leftover = the terms joined by ", ");
    5. `office_unrecognised` from `unnamed_parts(office words, …)` (leftover = those parts
       joined by ", ");
    6. `office_unrecognised` (any part's office unrecognised, leftover `""`);
    7. `level_unresolved` (P49).
- **The claims** (one per part, `#0`, `#1`, …, for each claimed card):
  - **Link and IDs:** `link=URL`, `source_event_id=None`.
  - **Place:** `place_raw` is the `data-location` text, a refining child's title words, or the
    one title place's words (P48).
  - **Office and scope (P63):** one part → `label_scope(title, place, registries, default)`;
    parts split from the office words → `part_scopes(parts, place, registries, default)`;
    fallback parts → `label_scope(title, place, registries, default, office_text=part)`.
    `office_label` is the title when there is one part, else the part.
  - **Round:** the part's office round. In the fallback, the title's `extract_round` fills a
    part without one; a part whose own round differs gets `None` (and the unit is
    `round_conflict`).
  - **Date:** span, `date_status` and `date_meaning` per P47; `date_text` is the visible date
    text.
  - **Other fields:** `status_claim=None`, `previous_date_text=None`, `evidence_kind="calendar"`,
    `indirect=False`.
- **Ledger:** `COUNT_RULES["ndi"] = CardBlocksRule((("upcoming-elections", "upcoming"), ("past-elections", "past")), "election-wrapper")`,
  written as a literal and pinned by a drift test.

**Test setup** (`test_ndi.py`):
- `WINDOW = window_for(datetime(2026, 10, 19, tzinfo=UTC))`.
- `SERVED` maps `request(n).url` to the fixtures `p0`–`p4`.
- `RAW` is `RawPages("ndi", tuple(Ndi().fetch(WINDOW, Served(SERVED), Deadline.after(60))), ())`.
- `RES = Ndi().parse(RAW, WINDOW, REGISTRIES)`.
- A `parse` helper asserts `check(raw, res).ok`, as in Plan 2b.
- Synthetic pages use these builders, which mirror the captured markup:
  - `card(title, date, types="General", location=None)`:
    `<div class="partial -election -feed">` holding `h3.heading > span`,
    `div.date-type > div.date` + `<span>|</span>` + the types (one per line), and
    `button.add-to-cal` with `data-location` when given;
  - `pager(active, has_next)`;
  - `ndi_page(up, past, *, up_page=0, past_page=0, up_next=False, past_next=False)`:
    `div.tab_panel#<id> > div > form + div.bound.boundwide > (div.election-wrapper | <p>No Results Found</p>) + nav.pager`,
    with `up`/`past` set to `None` for the no-wrapper variant.

  `PAST = [card("2026 Morocco Parliamentary Election", "September 23, 2026 (ALL DAY)", "Parliamentary")]`
  fills the past block when a test needs only the upcoming one. `.scratch/plan2c/proto/synth2c.py`
  has the measured builders.

- [ ] **Step 1: Write the failing tests.**

```python
def test_fixture_ledger_balances() -> None:
    report = check(RAW, RES)
    assert report.ok and RES.reasons == ()
    assert report.outcomes == {"parsed": 37, "partial": 1, "unparsed": 0, "ignored": 0}
    assert [(c.key, c.outcome, c.units_seen, c.year) for c in RES.coverage] == [
        ("p0", "ok", 20, None), ("p1", "ok", 18, None)]
    assert len(RES.claims) == 38

def test_fixture_values() -> None:
    C = RES.claims
    assert Counter(c.level for c in C) == {"national": 33, "subnational": 4, "unknown": 1}
    assert Counter(c.office_class for c in C) == {"legislature": 14, "general": 13, "head_of_state": 7, "local_council": 2, "governor": 2}
    assert Counter(c.span.precision for c in C) == {"day": 26, "month": 11, "year": 1}
    assert Counter(c.date_status for c in C) == {"unknown": 28, "tentative": 10}
    assert Counter(c.date_meaning for c in C) == {"voting_period": 26, "unknown": 12}
    assert {c.link for c in C} == {URL} and {c.status_claim for c in C} == {None}
    assert Counter(u.relevance for u in RES.units) == {"in_or_after_window": 24, "unknown": 14}
    assert [(c.claim_id, c.jurisdiction) for c in C if c.jurisdiction] == [
        ("ndi:p0/past-c6#0", "BARMM"), ("ndi:p0/past-c8#0", "Osun"), ("ndi:p0/past-c10#0", "Ekiti")]
    assert [(c.claim_id, c.round) for c in C if c.round] == [("ndi:p1/past-c2#0", 2)]
    assert [(u.unit_id, u.reason) for u in RES.units if u.outcome != "parsed"] == [
        ("ndi:p0/past-c6", "level_unresolved")]

def test_in_window_claims() -> None:
    assert sorted((c.span.start.isoformat(), c.place_id, c.office_class, c.level, c.span.precision)
                  for c in RES.claims if WINDOW.overlaps(c.span)) == [
        ("2026-09-14", "iso:PH", "legislature", "unknown", "day"), ("2026-09-23", "iso:MA", "legislature", "national", "day"),
        ("2026-09-27", "iso:ST", "legislature", "national", "day"), ("2026-10-01", "iso:RS", "legislature", "national", "month"),
        ("2026-10-04", "iso:BA", "general", "national", "day"), ("2026-10-04", "iso:BR", "general", "national", "day"),
        ("2026-10-04", "iso:PE", "local_council", "subnational", "day"), ("2026-10-25", "iso:BG", "legislature", "national", "day"),
        ("2026-11-02", "iso:PH", "local_council", "subnational", "day"), ("2026-11-15", "iso:CV", "head_of_state", "national", "day"),
        ("2026-12-05", "iso:GM", "head_of_state", "national", "day"), ("2026-12-22", "iso:SS", "general", "national", "day"),
        ("2027-01-16", "iso:NG", "general", "national", "day"), ("2027-01-24", "iso:KG", "head_of_state", "national", "day"),
    ]
```

  - **`test_claims_field_by_field`** (values from `.scratch/plan2c/r3_ndi_2026-10-19.txt`):
    - **`ndi:p0/upcoming-c1#0`** (Bulgaria):
      - place: `place_raw="Bulgaria"`, `place_id="iso:BG"`;
      - office: `institution="iso:BG/national-assembly"`, `office_class="legislature"`,
        `level="national"`;
      - date: `span=DateSpan.day(date(2026, 10, 25))`, `voting_period`, `unknown`,
        `date_text="October 25, 2026 (ALL DAY)"`;
      - `office_label="2026 Bulgaria Parliamentary Elections"`.

      Its unit text is `"2026 Bulgaria Parliamentary Elections | October 25, 2026 (ALL DAY) | Parliamentary | Bulgaria"`.
    - **`ndi:p0/upcoming-c2#0`** (Serbia, "(exact date TBD)"):
      `span=DateSpan.month(2026, 10)`, `date_status="tentative"`, `date_meaning="unknown"`.
    - **`ndi:p0/upcoming-c7#0`** (Haiti, "December 31, 2026", "(Date TBD)"):
      `span=DateSpan.of_year(2026)`, `tentative`, `office_class="general"`, `aggregate=True`.
    - **`ndi:p0/upcoming-c10#0`** (El Salvador, "February 28, 2027"):
      `span=DateSpan.month(2027, 2)`, `date_status="unknown"`.
    - **`ndi:p0/upcoming-c5#0`** (Gambia): `place_raw="The Gambia"` (from `data-location`).
    - **`ndi:p0/upcoming-c3#0`** (BSKE, type "Regional"):
      `office_class="local_council"`, `level="subnational"`, `aggregate=True`.
    - **`ndi:p0/past-c3#0`** (Bosnia; its `data-location` "Bosnia-Herzegovina" does not
      resolve): `place_raw="Bosnia and Herzegovina"`, `place_id="iso:BA"`; the unit is parsed,
      and its text is
      `"2026 Bosnia and Herzegovina General Elections | October 04, 2026 (ALL DAY) | General | Bosnia-Herzegovina"`.
    - **`ndi:p0/past-c6#0`** (BARMM): `place_id="iso:PH"`, `office_class="legislature"`,
      `level="unknown"`, `jurisdiction="BARMM"`, `jurisdiction_kind="subdivision"`.
    - **`ndi:p0/past-c8#0`** (Osun): `office_class="governor"`, `level="subnational"`,
      `jurisdiction="Osun"`, `place_raw="Nigeria"`.
    - **`ndi:p1/past-c2#0`** (Peru run-off "(TBD)"): `round=2`, `span=DateSpan.month(2026, 6)`,
      `tentative`.
  - **`test_chain_by_window`** (`SERVED` unless noted; `requests(w) == (request(0),)` for each
    window; measured by `dump2c.py` and `midway2c.py`):

    | Window date | Asked | Coverage `(key, outcome, units_seen)` | `reasons` | Units / claims |
    |---|---|---|---|---|
    | 2026-10-19 | p0, p1 | `p0 ok 20`, `p1 ok 18` | `()` | 38 / 38 |
    | 2026-05-15 | p0, p1, p2 | … `p2 ok 10` | `()` | 48 / 48 |
    | 2026-01-20 | p0 … p3 | … `p3 ok 10` | `()` | 58 / 58 |
    | 2025-12-20 (C06) | p0 … p4 | … `p3 ok 10`, `p4 ok 10` | `()` | 68 / 67 |
    | 2026-01-20, `p3` left out of `Served` | p0 … p3 | … `p2 ok 10`, `p3 http_error 0` | `(Reason("http_error", "p3"),)` | 48 / 48 |

    On 2025-12-20, `p2`–`p4` each have the empty, clamped upcoming block, and none of them is a
    repeat. The outcomes are 66 parsed, 1 partial (`p0/past-c6`, `level_unresolved`) and
    1 unparsed: `p4/past-c7`, Jamaica, `date_unparsed`, leftover
    `"September 03, 2025 4:00 AM - December 03, 2025 5:00 AM EDT"`, relevance
    `in_or_after_window`.

  - **`test_pagination_failures_are_loud`** (measured in `synth_r3_full.txt`, `synth_r3.txt`,
    `synth_dup.py` and `synth_new.py`):
    - **missing navigation (C01),** on fixture `p0` with its `nav.pager` elements cut out of the
      bytes (each case: `p0` `layout_not_recognised`, no units, `expected == (request(0),)`, and
      the counter still sees 20):
      - both pagers removed → `"upcoming block has 10 cards and no pager"`;
      - only the past pager → `"past block has 10 cards and no pager"`;
      - only the upcoming pager → `"upcoming block has 10 cards and no pager"`;
      - the first `rel="next"` changed to `rel="x"` →
        `"upcoming block has later pages but no next link"`;
      - a larger block: 11 upcoming cards, no upcoming pager, `PAST` →
        `"upcoming block has 11 cards and no pager"` (the counter sees 12; `c01_larger.py`);
      - the control: 9 upcoming cards, no upcoming pager, `PAST` → `ok`, 10 units parsed, and
        `expected == (request(0),)` with no note (a recognised last page, under the `PAGE_SIZE`
        assumption);
    - fixture `p0` received and nothing else → note `pagination_incomplete` `"p1 was not fetched"`;
    - fixture `p0` plus `p1` with outcome `timeout` → `p1` coverage `timeout`, no note;
    - `RawPages("ndi", (), (request(0),))` → one `unfinished` coverage entry and no note;
    - `p1` served `p0`'s body → `p1` `layout_not_recognised`
      `"upcoming block is page 0 with 10 cards"`;
    - the same past card on `p0` and `p1` (`p1` `past_page=1`) → `"past block repeats p0"`;
    - a `p1` upcoming card dated before `p0`'s last upcoming day →
      `"upcoming block is not in date order after p0"`; the past block likewise →
      `"past block is not in date order after p0"`;
    - `p0`'s last upcoming card repeated first on `p1` → `p1` is `ok`, and its first unit is
      ignored `duplicate` with `duplicate_of="ndi:p0/upcoming-c1"`;
    - ten synthetic pages that all want more → `expected` lists `p0`…`p9`, and the note
      `"stopped at the 10-page cap"`.
  - **`test_broken_pages_get_an_outcome_never_units`** (`p0`; change → detail):
    - the fixture cut at 200000 bytes → `"page does not end with </html>"`;
    - `id="upcoming-elections"` renamed → `"block #upcoming-elections appears 0 times"`;
    - an upcoming block with no cards, with or without an empty wrapper →
      `"upcoming block is page 0 with 0 cards"`;
    - two wrappers → `"upcoming block has 2 card lists"`;
    - two pagers → `"upcoming block has 2 pagers"`;
    - Bulgaria 25 Oct then Serbia 1 Oct upcoming → `"upcoming block is not in date order"`;
      Morocco 23 Sep then Peru 4 Oct past → `"past block is not in date order"`;
    - the `is-active` class removed → `"upcoming block has no current page"`;
    - `href="?page=٠"` (an Arabic-Indic zero) → the same.

    Two variants are `ok`: an empty, clamped upcoming block on `p1` (no wrapper, pager page 0),
    and a synthetic `p0` with no pagers and one card per block (fewer than `PAGE_SIZE`).
  - **`test_card_kinds`** (one card on `p0` upcoming, with `PAST`; measured):

    | Card (title, date, types, location) | Outcome, reason, leftover | Claim |
    |---|---|---|
    | "2026 Bulgaria Parliamentary Elections", 25 Oct, Parliamentary, "Bulgaria" — twice on one page | c1 parsed; c2 ignored `duplicate`, `duplicate_of` c1 | one |
    | the same title and day, type "Presidential", next to the first | both parsed | two, both `legislature` |
    | "", 25 Oct | unparsed `title_missing` | — |
    | "2026 Chile General Election", "" | unparsed `date_missing` | — |
    | "2026 Chile General Election", 25 Oct, General, "Peru" | partial `place_conflict`, `"Chile"` | `iso:PE` |
    | "2026 Narnia General Election", 25 Oct | unparsed `place_missing` | — |
    | "2026 General Election", 25 Oct, General, "Narnia" | partial `place_unregistered` | `unknown:narnia` |
    | "2026 Jamaica General Election", "September 03, 2026 4:00 AM - December 03, 2026 5:00 AM EDT" | unparsed `date_unparsed`, the date text | — |
    | "2026 Chile General Election", "Postponed October 25, 2026" | unparsed `date_unparsed`, the date text | — |
    | "2026 Chile General Election", "TBD" | unparsed `date_missing` | — |
    | "2036 Chile General Election", "October 25, 2036 (ALL DAY)" | unparsed `implausible_date` | — |
    | "2026 Chile Attorney General Election", 25 Oct, Local | unparsed `office_not_modelled`, the title | — |
    | "2026 Chile Senatorial Recall", 25 Oct, "Recall" | partial `type_unrecognised`, `"Recall"` | `upper_house`, national |
    | "2026 Chile Local Elections", "Municipal\n Regional" | parsed | `local_council`, subnational |
    | "2026 Chile Elections", 25 Oct, "" | partial `office_unrecognised` | `general`, level `unknown` |
    | "2026 Chile Mayor", 25 Oct, "Local" | parsed | `mayor`, subnational |

    "25 Oct" is `"October 25, 2026 (ALL DAY)"`. Revision 1's row for "2026 Chile Presidential and
    Local Elections" moves to `test_compound_titles`, with two claims (C03).
  - **`test_card_places`** (C04; one card on `p0` upcoming, 25 Oct, type "General", with
    `PAST`; measured in `synth_r3.txt` and by `synth_r2c.py`):

    | Title / `data-location` | Outcome, reason, leftover | Claim `place_id`, `place_raw` |
    |---|---|---|
    | "2026 Niger and Nigeria Elections" / — | unparsed `place_ambiguous`, `"Niger, Nigeria"` | — |
    | "2026 DRC Congo Elections" / — | unparsed `place_ambiguous`, `"DRC, Congo"` | — |
    | "2026 Republic of the Congo Presidential Election" / — | parsed | `iso:CG`, "Republic of the Congo" |
    | "2026 United Kingdom Scotland Parliamentary Election" / — | parsed | `iso:GB-SCT`, "Scotland" |
    | "2026 Scotland Parliamentary Election" / "United Kingdom" | parsed | `iso:GB-SCT`, "Scotland" |
    | "2026 Niger and Nigeria Elections" / "Niger" | partial `place_conflict`, `"Nigeria"` | `iso:NE`, "Niger" |
    | "2026 Ivory Coast Presidential Election" / "Côte d'Ivoire" | parsed | `iso:CI`, "Côte d'Ivoire" |
    | "2026 Côte d'Ivoire (Ivory Coast) Presidential Election" / —, type "Presidential" | parsed | `iso:CI`, "Côte d'Ivoire" |
  - **`test_duplicates_compare_every_field`** (C02, P61; two cards on `p0` upcoming, 25 Oct,
    with `PAST`):

    | Cards (title / `data-location`) | Units | Claims |
    |---|---|---|
    | "2026 General Election" / "Chile", then the same / "Peru" | both parsed | `iso:CL`, `iso:PE` |
    | "2026 Chile General Election" / "Peru", then the same / "Chile" | c1 partial `place_conflict`, `"Chile"`; c2 parsed | `iso:PE`, `iso:CL` |
    | "2026 Chile Presidential Election" / "Chile", twice (type "Presidential") | c1 parsed; c2 ignored `duplicate`, `duplicate_of="ndi:p0/upcoming-c1"` | one, `iso:CL` |
    | "2026 Narnia General Election" / —, twice | both unparsed `place_missing` (a unit that gave no claim reserves nothing) | — |
    | "2026 Presidential Election" / "Ivory Coast", then the same / "Côte d'Ivoire" | both parsed (the key is the visible text) | two, both `iso:CI` |
  - **`test_compound_titles`** (C03, P49, P64; one card, 25 Oct, with `PAST`):

    | Title, types | Unit | Claims (`office_class`, `level`, `office_label`, `aggregate`) |
    |---|---|---|
    | "2026 Chile Presidential and Local Elections", "Presidential\n Local" | parsed | `#0` head_of_state, national, "Presidential", `False`; `#1` local_council, subnational, "Local Elections", `True` |
    | "2026 Chile Presidential and Parliamentary Elections", "Presidential and Parliamentary" | parsed | `#0` head_of_state, national; `#1` legislature, national |
    | "2026 Trinidad and Tobago Presidential and Local Elections", "Presidential\n Local" | parsed | `#0` head_of_state, `#1` local_council, both on `iso:TT` |
    | "2026 Chile Presidential and Xyz Elections", "Presidential" | partial `office_unrecognised`, `"Xyz Elections"` | `#0` head_of_state, national, label = the title |
    | "2026 Brazil General Elections", "General" | parsed | `#0` general, national (an umbrella; nothing is invented) |
    | "2026 Nigeria Presidential and Osun Gubernatorial Elections", "Presidential\n Gubernatorial" | parsed | `#0` head_of_state, national, jurisdiction `None`; `#1` governor, subnational, "Osun" (P63: no sibling copy) |
    | "2026 Nigeria Osun Gubernatorial and State Assembly Elections", "Gubernatorial\n State Assembly" | parsed | `#0` governor, `#1` legislature; both subnational, "Osun" (leading) |

    The last two rows are measured by `p63_check.py`.
  - **`test_type_fallback_keeps_the_title_context`** (C05; one card, 25 Oct, on `iso:PH`, with
    `PAST`; measured in `synth_r3.txt` and by `synth_r2b.py` and `synth_r2d.py`):

    | Title, types | Unit | Claim (`office_class`, `level`, `jurisdiction`, `round`) |
    |---|---|---|
    | "2026 Philippines (BARMM) BSKE Elections", "Regional" | parsed | local_council, subnational, "BARMM" (`subdivision`), `None`; `aggregate=True` |
    | "2026 Philippines BSKE Run-Off", "Regional" | parsed | local_council, subnational, `None`, 2 |
    | "2026 Philippines BSKE Elections", "Presidential Runoff" | parsed | head_of_state, national, `None`, 2 |
    | "2026 Philippines BSKE First Round", "Presidential Runoff" | partial `round_conflict`, `"Presidential Runoff"` | head_of_state, national, `None`, `None` |

    In each, `office_label` is the title.
  - **`test_dates`** (title, date → precision and span, `date_status`, `date_meaning`; measured):

    | Title | Date | Result |
    |---|---|---|
    | "2026 Chile General Election" | "October 25, 2026 (ALL DAY)" | day 2026-10-25, unknown, voting_period |
    | "… (exact date TBD)" | "October 25, 2026 (ALL DAY)" | month 2026-10, tentative, unknown |
    | "…" | "December 31, 2026 (ALL DAY)" | year 2026, unknown, unknown |
    | "… (date TBD)" | "December 31, 2026 (ALL DAY)" | year 2026, tentative, unknown |
    | "…" | "November 30, 2026 (ALL DAY)" | month 2026-11, unknown, unknown |
    | "2027 …" | "February 28, 2027 (ALL DAY)" | month 2027-02 |
    | "2028 …" | "February 28, 2028 (ALL DAY)" | day 2028-02-28 (2028 is a leap year) |
    | "2028 …" | "February 29, 2028 (ALL DAY)" | month 2028-02 |
    | "2027 … (TBD)" | "June 01, 2027 (ALL DAY)" | month 2027-06, tentative |
    | "2027 …" | "June 01, 2027 (ALL DAY)" | day 2027-06-01, voting_period |
    | "… (Tbd)" | "October 25, 2026" | month 2026-10, tentative |

  - **`test_type_vocabulary_matches_the_page_filter`:** the casefolded, whitespace-collapsed
    option texts of every `select[name=type]` in fixture `p0`, minus the option whose value is
    `"All"`, equal `SUBNATIONAL_TYPES | NATIONAL_TYPES`. The two sets are disjoint and have 14
    and 39 terms.
  - **`test_count_rule_matches_the_adapter`:**
    `COUNT_RULES["ndi"] == CardBlocksRule(ndi.BLOCKS, ndi.WRAPPER)`.
  - **`test_download_failures_keep_their_own_outcome`:** `raw_pages("ndi", [(request(0), result(<fixture p0>, status=302))])`
    → `p0` coverage `http_error`, no units, no notes, and `expected(WINDOW, raw.pages) == (request(0),)`.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/adapters/test_ndi.py -q`.
  Expected: FAIL on import.
- [ ] **Step 3: Implement `Ndi`.** Register it. The runner list becomes
  `["electionguide", "osce", "wikipedia", "ndi", "aweb", "ipu", "carter", "eeas"]`.
- [ ] **Step 4: Run** the file and `tests/unit/test_runner.py`. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:** `feat(sources): NDI elections calendar adapter`.

  Mutations, one each:
  - `data-location` only (no title place);
  - take the first title place (no `place_ambiguous`);
  - drop the child refinement of `data-location`;
  - the "TBD" check against the date instead of the title;
  - drop the 31 December rule;
  - drop the type fallback;
  - scope the fallback on the terms alone (`label_scope(joined terms, …)`);
  - drop the title round in the fallback;
  - drop the `round_conflict` check;
  - parts are always `[title]` (no split);
  - scope split parts with `label_scope(title, …, office_text=part)` instead of `part_scopes`;
  - drop the `unnamed_parts` check;
  - drop the "later pages but no next link" end state;
  - drop the "cards and no pager" end state;
  - `len(cards) == PAGE_SIZE` instead of `>=` in that end state;
  - drop the cross-page order check;
  - drop the repeat check;
  - run the repeat check on empty blocks too;
  - drop the duplicate check;
  - drop the location from the duplicate key;
  - drop the location from the unit text;
  - drop the cap note;
  - continue only on the upcoming block's next link;
  - drop `missing_pages` from `parse`;
  - remove one term from `SUBNATIONAL_TYPES`;
  - `[0-9]` → `\d` in the active-page pattern;
  - a different wrapper class in `COUNT_RULES`.

---

### Task 5: EISA adapter

**Files:**
- Create: `elections_calendar/sources/eisa.py`, `tests/adapters/test_eisa.py`
- Modify:
  - `COUNT_RULES` (add `"eisa"`);
  - `DEFAULT_ADAPTERS` (after `aweb`, before `ipu`, §10.5);
  - `importlinter.ini`;
  - `test_runner.py:392`.

**Interfaces:**
- Consumes:
  - as Task 4 (including Task 3's `label_scope(…, office_text=)` and `unnamed_parts`);
  - `model.MAX_DETAIL`.
- Produces:
  - `class Eisa` with `source = "eisa"`;
  - `URL = "https://www.eisa.org/election-calendar/"`;
  - `AJAX = "https://www.eisa.org/wp-admin/admin-ajax.php?action=wp_ajax_ninja_tables_public_action&table_id={table_id}&target_action=get-all-data"`;
  - `HEADING = "eisa african election calendar {year}"`;
  - `FIELDS = ("country", "election", "date")`;
  - `expected(window: Window, pages: Sequence[RawPage]) -> tuple[PageRequest, ...]`.

**Rules:**
- **Requests and fetch (P46):**
  - `requests(window)` is `(PageRequest("calendar", URL),)`.
  - `fetch` is `fetch_chain(...)`, as in Task 4.
  - `expected` lists the calendar request, then, when the calendar page is received, clean and
    readable, `PageRequest(f"y{year}", AJAX.format(table_id=id), year)` for each window year
    that has an id, in `window.years` order.
- **Reading the calendar** (P52):
  1. Not complete HTML → `"page does not end with </html>"`.
  2. For each window year, the headings (`h1`–`h6`) whose `cell_text(…).casefold()` equals
     `HEADING.format(year=year)` are matched.
  3. For each matched heading, the ids are the stripped `data-footable_id` of every `table` under
     the heading's parent element that has that attribute, or `"(none)"` when there is none.
  4. A year with matched headings needs exactly one distinct id that fullmatches `[0-9]{1,9}`,
     and exactly one id per heading. Else →
     `"heading '<heading>' has table ids <sorted distinct ids, joined by ', '>"`.
  5. The calendar page is `ok` with no units. Each window year without a heading adds a note:
     `not_published_yet` if the year is after `window.today.year`, else `required_year_missing`;
     the detail is `"no heading '<heading>'"`.
- **A year page `y<YYYY>`** has coverage year `YYYY`. It gives the first failing detail:
  - the body is not JSON (`ValueError` or `RecursionError`) → `"the body is not JSON"`;
  - not a list → `"the body is not a JSON list"`;
  - an empty list → `"the table has no rows"`;
  - no element gives fields → `"no row has country, election and date"`.

  An element **gives fields** when it is a `dict` whose `"value"` is a `dict` with a `str` under
  each of `FIELDS`. Each field is `collapse_ws`'d.
- **Rows** are `eisa:y<YYYY>/r<i>` for every element, `i` from 1.
  - **An element that gives no fields** is unparsed `row_unrecognised`, relevance `unknown`. Its
    text is `json.dumps(element, ensure_ascii=False, sort_keys=True)[:MAX_DETAIL]`, and it ends
    the inheritance.
  - **The country** is the row's own country when it has one. Otherwise it inherits the last own
    country in this table since the last `row_unrecognised` (P53).
  - **Text:** `" | ".join` of the shown country, election and date, skipping empty ones. The
    shown country is the own country, or `f"{country} (from the row above)"` for an inherited
    one, or nothing (C08, P53).
  - **Relevance:** `relevance(date, window.start)`.
- **A row's checks, in order:**
  1. **unparsed `place_missing`:** no country (P53);
  2. **ignored `duplicate`** (P61);
  3. **unparsed `office_missing`:** blank election;
  4. **The round** (P57) is cut from the date. The rest goes to `parse_date_text`, with no
     `default_year`;
  5. **unparsed `no_new_date`:** `ok`, no spans, status `postponed`; leftover = the date text
     (P54);
  6. **unparsed `date_missing`:** `ok` and no spans;
  7. **unparsed `date_unparsed`:** not `ok`, or other than one span; leftover = the parse's
     leftover, or else the date text;
  8. **unparsed `implausible_date`;**
  9. **unparsed `office_not_modelled`:** `is_executive_title(election)`; leftover = the election.
- **The claims** (P56): one per `split_offices(election, place.place_id, registries.institutions) or [election]`
  part, `#0`, `#1`, ….
  - **Scope:** `part_scopes(parts, place, registries)` (P63), with the default level
    `national`. For one part this is `label_scope(election, …)`.
  - **Partial reasons, in order:**
    1. `place_unregistered`;
    2. `round_conflict` (P57): a qualifier, and some part's own office round differs from it;
       leftover = the qualifier as written, stripped (`"First Round:"`, `"(runoff)"`);
    3. `office_unrecognised` from `unnamed_parts(election, …)` (P64); leftover = those parts
       joined by ", ";
    4. `office_unrecognised` (any part), leftover `""`;
    5. `level_unresolved` (any part's scope is `unresolved`).
  - **Fields:**
    - `link=URL`, `source_event_id=None`;
    - `place_raw` = the country (inherited or not); `office_label` = the part;
    - `round` = the qualifier when the part's office has none; the office's when there is no
      qualifier or the two agree; `None` when they differ;
    - `date_meaning` per P55; `date_status` = the parse's; `date_text` = the full date text;
    - `status_claim` and `previous_date_text` = the parse's;
    - `evidence_kind="calendar"`, `indirect=False`.
- **Notes:**
  1. the calendar's year notes;
  2. P62 (C07): an `ok` year page with at least one readable dated row, none of whose years is
     the page's year → `Reason("coverage_gap", f"y{year} has no {year} date")`. A row is read
     for this when it gives fields: the qualifier is cut, and `parse_date_text` must be `ok` with
     spans. Its years run from each span's start year to its end year, or are the span's `year`.
     This happens before the plausibility check and whatever the row's outcome;
  3. `missing_pages(expected(window, raw.pages), raw)`.
- **Ledger:** `COUNT_RULES["eisa"] = JsonListRule(frozenset({"calendar"}))`.

**Test setup** (`test_eisa.py`):
- `WINDOW = window_for(datetime(2026, 10, 19, tzinfo=UTC))`.
- `SERVED` maps `URL` → `calendar.html`, `AJAX.format(table_id="38978")` → `y2026.json`, and
  `table_id="34700"` → `y2025.json`.
- `RAW`, `RES` and `parse` follow Task 4's setup.
- Synthetic calendars use `eisa_cal([(title, table_id or None), …])`: each pair becomes
  `div.footable_parent.ninja_table_wrapper > h3.table_title.footable_title + table[data-footable_id]`.
- Synthetic tables use `rows((country, election, date), …)`, the Ninja Tables shape
  `{"options": {"classes": ""}, "value": {"country": …, "election": …, "date": …, "___id___": i}}`.

`synth2c.py` has both builders.

- [ ] **Step 1: Write the failing tests.**

```python
NOTE_2027 = Reason("not_published_yet", "no heading 'eisa african election calendar 2027'")

def test_fixture_ledger_balances() -> None:
    report = check(RAW, RES)
    assert report.ok and RES.reasons == (NOTE_2027,)
    assert report.outcomes == {"parsed": 20, "partial": 0, "unparsed": 2, "ignored": 0}
    assert [(c.key, c.outcome, c.units_seen, c.year) for c in RES.coverage] == [
        ("calendar", "ok", 0, None), ("y2026", "ok", 22, 2026)]
    assert len(RES.claims) == 25

def test_fixture_values() -> None:
    C = RES.claims
    assert Counter(c.level for c in C) == {"national": 22, "subnational": 3}
    assert Counter(c.office_class for c in C) == {"head_of_state": 9, "legislature": 6, "lower_house": 5, "local_council": 3, "general": 1, "upper_house": 1}
    assert Counter(c.span.precision for c in C) == {"day": 19, "month": 3, "year": 3}
    assert Counter(c.date_meaning for c in C) == {"voting_period": 18, "unknown": 6, "expected_window": 1}
    assert Counter(c.status_claim for c in C) == {"held": 13, None: 10, "postponed": 2}
    assert {c.link for c in C} == {URL} and {c.jurisdiction for c in C} == {None}
    assert Counter(u.relevance for u in RES.units) == {"unknown": 13, "in_or_after_window": 9}
    assert [(u.unit_id, u.reason, u.leftover, u.relevance) for u in RES.units if u.outcome != "parsed"] == [
        ("eisa:y2026/r11", "no_new_date", "Postponed from April 2026", "unknown"),
        ("eisa:y2026/r12", "no_new_date", "Postponed from April 2026", "unknown")]

def test_in_window_claims() -> None:
    assert sorted((c.span.start.isoformat(), c.place_id, c.office_class, c.level, c.span.precision)
                  for c in RES.claims if WINDOW.overlaps(c.span)) == [
        ("2026-09-23", "iso:MA", "lower_house", "national", "day"), ("2026-09-27", "iso:ST", "legislature", "national", "day"),
        ("2026-10-01", "iso:CV", "head_of_state", "national", "month"), ("2026-11-01", "iso:ZA", "local_council", "subnational", "month"),
        ("2026-12-01", "iso:CM", "lower_house", "national", "month"), ("2026-12-05", "iso:GM", "head_of_state", "national", "day"),
        ("2026-12-22", "iso:SS", "head_of_state", "national", "day"), ("2026-12-22", "iso:SS", "legislature", "national", "day"),
    ]
```

  - **`test_claims_field_by_field`** (values from `.scratch/plan2c/r3_eisa_2026-10-19.txt`):
    - **`r3#0` and `r3#1`** (Benin, "National Assembly and local", "Held 11 January 2026"):
      - `#0`: `lower_house`, `iso:BJ/national-assembly`, national;
      - `#1`: `local_council`, institution `None`, subnational, `aggregate=True`, label `"local"`;
      - both: `span=DateSpan.day(date(2026, 1, 11))`, `voting_period`, `status_claim="held"`.
    - **`r7#0`** (Cape Verde, inherited; the unit text is
      `"Cape Verde (from the row above) | Presidential | October 2026"`):
      `place_raw="Cape Verde"`, `span=DateSpan.month(2026, 10)`, `date_meaning="unknown"`,
      `head_of_state`.
    - **The unit `r12`** (Libya, inherited, no claim): text
      `"Libya (from the row above) | House of Representatives | Postponed from April 2026"`.
      The inheriting rows are exactly r4, r7, r12 and r15 (C08).
    - **`r10#0`** (Gambia): `iso:GM/president`, `DateSpan.day(date(2026, 12, 5))`,
      `voting_period`, `status_claim=None`, `date_text="5 December 2026"`.
    - **`r16#0` and `r16#1`** (Somaliland, "Postponed from June 2026 to 2028"):
      - both: `place_id="x:somaliland"`, `span=DateSpan.of_year(2028)`, `status_claim="postponed"`,
        `previous_date_text="June 2026"`;
      - `#0`: `lower_house`, label "House of Representatives";
      - `#1`: `upper_house`, label "House of Elders (Guitr)".
    - **`r17#0`** (Somalia, "Stagerred: 10 May 2026 - 30 July 2026"):
      `span=DateSpan.days(date(2026, 5, 10), date(2026, 7, 30))`, `date_meaning="unknown"`,
      `local_council`, subnational.
    - **`r18#0`** (South Africa, "Nov 2026 - Jan 2027"): a month-precision span from 2026-11-01
      to 2027-01-31, `expected_window`.
    - **`r19#0` and `r19#1`** (South Sudan): `head_of_state` `iso:SS/president`, and
      `legislature`, institution `None`, `aggregate=True`; both national, 22 Dec 2026.
    - **`r22#0`** (Western Sahara, "2026"): `place_id="iso:EH"`, `DateSpan.of_year(2026)`,
      `legislature`.
  - **`test_chain_by_window`:**

    | Window date | Requested | Coverage `(key, outcome, units_seen, year)` | `reasons` | Units / claims |
    |---|---|---|---|---|
    | 2026-10-19 | calendar, y2026 (`table_id=38978`) | `calendar ok 0 None`, `y2026 ok 22 2026` | `(NOTE_2027,)` | 22 / 25 |
    | 2027-01-10 | calendar, y2026 | the same | `(Reason("required_year_missing", "no heading 'eisa african election calendar 2027'"),)` | 22 / 25 |
    | 2025-11-15 | calendar, y2025 (`34700`), y2026 | … `y2025 ok 23 2025`, `y2026 ok 22 2026` | `()` | 45 / 57 |

    On 2025-11-15:
    - the outcomes are 41 parsed and 4 unparsed;
    - `y2025/r4` is `date_unparsed`, leftover `"Extended to 2026"`;
    - `y2025/r18` is `date_unparsed`, leftover `"Postponed indefinitely from 2025"`;
    - the rounds are `y2025/r9#0` 1, `r10#0` 2, `r19#0` and `r19#1` 1, `r20#0` and `r20#1` 2.
  - **`test_calendar_headings`** (synthetic calendars, title "EISA African Election Calendar
    <year>" unless noted; measured):

    | Calendar | Result |
    |---|---|
    | the fixture cut at 100000 bytes | `layout_not_recognised`, `"page does not end with </html>"` |
    | 2026 → 38978 and 2026 → 99999 | `"heading 'eisa african election calendar 2026' has table ids 38978, 99999"` |
    | 2026 with no table | `"… has table ids (none)"` |
    | 2026 → `abc` | `"… has table ids abc"` |
    | 2026 → 38978 twice | `ok`; requests `y2026` once |
    | 2025 only, window 2026-10-19 | `ok`; notes `required_year_missing` 2026, then `not_published_yet` 2027 |
    | 2026 → 38978 and 2027 → 40001 | requests y2026 and y2027 (`table_id=40001`); no year note |
    | `"  eisa  AFRICAN election calendar 2026 "` | matches |
    | "EISA Comprehensive African Election Calendar" and "Election Calendar 2026" | no match: the two year notes |

  - **`test_broken_json`** (`y2026` body → detail; spec S2's "HTTP-200 API error"):
    - `b"<html>error</html>"` → `"the body is not JSON"`;
    - `b"0"`, `b"-1"` (WordPress admin-ajax's HTTP-200 answers to an unknown action) and
      `b'{"success": false}'` → `"the body is not a JSON list"` (measured by `ajax0_2c.py`);
    - `b'{"data": []}'` → `"the body is not a JSON list"`;
    - `b"[]"` → `"the table has no rows"`;
    - `b'[{"value": {"name": "x"}}, 3]'` → `"no row has country, election and date"`.

    Each has no units.
  - **`test_row_kinds_and_inheritance`:**
    - rows Chad/Presidential/"5 December 2026", then `"junk"`, then (blank)/National Assembly,
      then `{"value": {"country": 7, …}}` →
      r1 parsed, r2 `row_unrecognised` (text `'"junk"'`), r3 `place_missing`,
      r4 `row_unrecognised`;
    - two tables: 2026 holds Chad/Local/"Nov 2026 - Jan 2027"; 2027 holds
      (blank)/Senate/"5 January 2027" and Chad/Local/"Nov 2026 - Jan 2027" →
      `y2027/r1` `place_missing` (no inheritance across tables), and `y2027/r2` ignored
      `duplicate` with `duplicate_of="eisa:y2026/r1"`;
    - **C08:** rows `(<first>, "Presidential", "Postponed from April 2026")` then
      `("", "House of Representatives", "Postponed from April 2026")`. With `<first>` = Libya,
      r2's text is `"Libya (from the row above) | House of Representatives | Postponed from April 2026"`;
      with Chad, `"Chad (from the row above) | …"`. Both rows are `no_new_date` in each case, and
      the two r2 texts differ (measured by `synth_r2b.py`).
  - **`test_row_grammar`** (one `y2026` table; country "Chad" unless noted; measured):

    | r | Election | Date | Outcome, reason, leftover | Claim |
    |---|---|---|---|---|
    | 1 | Presidential (country blank) | 5 December 2026 | unparsed `place_missing` | — |
    | 2 | Presidential | Postponed from April 2026 | unparsed `no_new_date`, the date | — |
    | 3 | Senate | Postponed from June 2026 to 2028 | parsed | year 2028, postponed, previous "June 2026" |
    | 4 | Presidential | Held 2 July 2026 | parsed | day, voting_period, held |
    | 5 | Local | Nov 2026 - Jan 2027 | parsed | month span, expected_window, subnational |
    | 6 | Regional and local | Stagerred: 10 May 2026 - 30 July 2026 | parsed | 10 May–30 Jul, unknown; one claim |
    | 7 | Senate | 2026 | parsed | year 2026, unknown |
    | 8 | Senate | TBD | unparsed `date_missing` | — |
    | 9 | Senate | (blank) | unparsed `date_missing` | — |
    | 10 | (blank) | 5 December 2026 | unparsed `office_missing` | — |
    | 11 | President | Second Round: Held 9 - 11 Oct 2026 | parsed | 9–11 Oct, unknown, held, round 2 |
    | 12 | President | First Round: 13 Sep 2026 | parsed | voting_period, round 1 |
    | 13 | National Assembly | Held 13 May 2026 (first round) | parsed | round 1 |
    | 14 | National Assembly | Held 27 May 2026 (second round) | parsed | round 2 |
    | 15 | House of Assembly | Held 29 Jan 2026 (runoff) | parsed | round 2 |
    | 16 | House of Assembly | Held18 June 2026 | unparsed `date_unparsed`, `"Held18 June 2026"` | — |
    | 17 | President and National Assembly | 5 December 2026 | parsed | `#0` head_of_state, `#1` lower_house |
    | 18 | Regional and local | 5 December 2026 | parsed | one `local_council` claim |
    | 19 | Presidential (country "Narnia") | 5 December 2026 | partial `place_unregistered` | `unknown:narnia` |
    | 20 | Presidential | 5 December 2036 | unparsed `implausible_date` | — |
    | 21 | Presidential | Cancelled 5 December 2026 | parsed | voting_period, cancelled |
    | 22 | Presidential | December 2026 | parsed | month, unknown |
    | 23 | Prime Minister | 5 December 2026 | partial `office_unrecognised` | general, level unknown |
    | 24 | Presidential | 10, 11, 12 Dec 2026 | unparsed `date_unparsed`, the date | — |
    | 25 | Lieutenant Governor | 5 December 2026 | unparsed `office_not_modelled`, `"Lieutenant Governor"` | — |

    Row 25 is measured separately (`synth_exec.py`); appending it changes no earlier row.
  - **`test_table_year_check`** (P62, C07; one `y2026` table, country "Chad"; measured in
    `synth_r3.txt`):

    | Rows (election, date) | Units | `coverage_gap` note |
    |---|---|---|
    | Presidential, "10 January 2027" | parsed | `"y2026 has no 2026 date"` (the notes end with it) |
    | Presidential, "5 December 2018"; Senate, "10 May 2019" | both unparsed `implausible_date`, relevance `before_window` | `"y2026 has no 2026 date"` |
    | Presidential, "TBD"; Senate, "TBD" | both unparsed `date_missing` | none |
    | Presidential, "5 December 2026"; Senate, "Postponed from June 2026 to 2028" | both parsed | none |
    | Local, "Nov 2025 - Jan 2026" | parsed | none (the span touches 2026) |
  - **`test_rounds_and_parts`** (P57, P63, P64; one `y2026` table of these eight rows; measured
    by `synth_r3f.py`):

    | r | Country, election, date | Unit | Claims |
    |---|---|---|---|
    | 1 | Chad, "Presidential Run-off", "First Round: 13 Sep 2026" | partial `round_conflict`, `"First Round:"` | `#0` head_of_state, round `None` |
    | 2 | Chad, "President (2nd round)", "Held 27 May 2026 (second round)" | parsed | `#0` head_of_state, round 2 |
    | 3 | Chad, "President and Xyz", "5 December 2026" | partial `office_unrecognised`, `"Xyz"` | `#0` head_of_state, label "President and Xyz" |
    | 4 | Nigeria, "Osun Governor and State Assembly", "5 December 2026" | parsed | `#0` governor, `#1` legislature; both subnational, jurisdiction "Osun", `subdivision` |
    | 5 | Chad, "President (runoff) and National Assembly", "First Round: 13 Sep 2026" | partial `round_conflict`, `"First Round:"` | `#0` head_of_state, round `None`; `#1` lower_house `iso:TD/national-assembly`, round 1 |
    | 6 | Nigeria, "State Assembly", "5 December 2026" (the control) | parsed | `#0` legislature, subnational, jurisdiction `None`, `nationwide` (its label names no Osun) |
    | 7 | Nigeria, "Presidential and Osun Governor", "5 December 2026" | parsed | `#0` head_of_state `iso:NG/president`, national, jurisdiction `None`; `#1` governor, subnational, "Osun" (no sibling copy) |
    | 8 | Nigeria, "Osun Governor and Lagos State Assembly", "7 December 2026" | parsed | `#0` governor, "Osun"; `#1` legislature, "Lagos State"; both subnational (each keeps its own) |

  - **`test_pagination_failures_are_loud`:**
    - the calendar received and `y2026` not received → note `pagination_incomplete`
      `"y2026 was not fetched"`;
    - `y2026` with outcome `timeout` → coverage `("y2026", "timeout")` with year 2026, and no
      note;
    - the calendar `unfinished` → one `unfinished` entry, no note.
  - **`test_count_rule_matches_the_adapter`:**
    `COUNT_RULES["eisa"] == JsonListRule(frozenset({"calendar"}))`.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/adapters/test_eisa.py -q`.
  Expected: FAIL on import.
- [ ] **Step 3: Implement `Eisa`.** Register it. The runner list becomes
  `["electionguide", "osce", "wikipedia", "ndi", "aweb", "eisa", "ipu", "carter", "eeas"]`.
- [ ] **Step 4: Run** the file and `tests/unit/test_runner.py`. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:** `feat(sources): EISA African election calendar adapter`.

  Mutations, one each:
  - a missing current year becomes `not_published_yet`;
  - accept two different ids for one year;
  - inherit across a `row_unrecognised` row;
  - inherit across tables;
  - drop `no_new_date` (it falls through to `date_missing`);
  - drop the trailing round qualifier;
  - the qualifier overrides a part's own round (no `round_conflict`);
  - drop `split_offices`;
  - scope each part on the part alone (`label_scope(part, …)`, which loses r4's leading "Osun");
  - scope each part with the whole label (`label_scope(election, …, office_text=part)`, revision
    2's rule);
  - drop the `unnamed_parts` check;
  - `expected_window` for a single month;
  - drop the P62 note;
  - P62 reads the claims instead of the dated rows;
  - drop the inherited country from the unit text;
  - drop `missing_pages` from `parse`;
  - the `row_unrecognised` text becomes `""`.

---

## Requirements for later plans

Each later plan's pre-flight must pull its rows from this table into its own tasks, with the
named acceptance test. A row is closed only when that test is green in the owning plan.

| ID | Requirement | Owner | Acceptance test (name and result) | Completion stage |
|---|---|---|---|---|
| R7 (extended) | Plan 2b's R7 test set gains NDI `ndi:p0/past-c6#0` (BARMM, level `unknown`, jurisdiction "BARMM") | Plan 3 | `test_subdivision_claim_never_joins_a_nationwide_contest` includes it | Plan 3's identity task |
| R10 (updated) | The runner now starts 9 sources, at most 4 at once. Measured fetch times (2026-10-19): NDI 0.4–0.6 s per page (2 pages today, cap 10); EISA calendar 3.8 s plus about 1.1 s per year table | Plan 5 | the workflow's deadline test | Plan 5 |
| R12 | §10.3 month disagreement: EISA `eisa:y2026/r7#0` (Cape Verde, October 2026) attaches to the single 15 Nov 2026 Cape Verde presidential contest with `date_conflict=true` (Appendix B) | Plan 3 | `test_month_claim_attaches_with_date_conflict` uses the EISA and NDI fixtures | Plan 3's matching task |
| R13 (extended) | NDI TBD claims (`tentative`, month or year precision) never confirm a date. Appendix B Serbia: "NDI TBD and IPU don't count as independent confirmation" (`ndi:p0/upcoming-c2#0`). **Also (P47 ruling):** a month or year that P47 *inferred* from a visible day (31 December, a month end) never counts as an independent exact-day confirmation, and a year-only calendar claim stays visible as undated evidence, never silently dropped (`ndi:p0/upcoming-c7#0` Haiti, `ndi:p0/upcoming-c10#0` El Salvador) | Plan 3 | `test_ndi_tbd_never_confirms_a_date`, `test_an_inferred_month_never_confirms_a_day`, `test_a_year_only_claim_stays_visible` | Plan 3's date selection |
| R14 (extended) | EISA year rollover: a January run without the new year's heading reports `required_year_missing` (P52). The previous year's EISA claims that still overlap the window stay as fallback evidence, or the gap is reported (as R2). **Also (P52 ruling):** a future year's table that was never published (`not_published_yet`) is told apart from one that an earlier snapshot had and that has now disappeared, which is an error | Plan 4 | `test_eisa_january_without_a_new_table_keeps_december`, `test_a_disappeared_year_table_is_an_error` | Plan 4's snapshot task |
| R15 (extended) | Health counts `pagination_incomplete` notes and the chained page count per source. A shorter NDI chain at an equal window is visible in `HEALTH.md`. This needs a baseline; on first ingestion, completeness rests on the adapter's end-state checks (P50, C01), which this plan pins | Plan 4 | `test_health_reports_chain_length_and_missing_pages` | Plan 4's health task |
| R16 (extended) | EISA's Libya rows are `no_new_date`, relevance `unknown` (P54). Attention handling must let a reviewer acknowledge such a unit until its text changes, without hiding a new one. **Also (C08):** the comparison uses the unit's text, which names the inherited country (P53). A change of the inherited country alone reopens the acknowledgement; an unchanged item stays acknowledged; reordering rows (a new unit ID for the same text, or the same ID for a new text) never moves an acknowledgement to a different item | Plan 4 | `test_a_no_new_date_unit_can_be_acknowledged_until_it_changes`, `test_an_inherited_country_change_reopens_an_acknowledgement` | Plan 4's attention task |

## After Plan 2c

- **The branch** has the Plan 2c commits on top of the commit that holds this plan, with all
  gates green. Nothing is pushed or merged.
- **The Review record** shows every row as "verified", with its commit in the SDD ledger. R7,
  R10 and R12–R16 stay open until their own plans' acceptance tests pass.
- **Next:** Plan 3 (merge), written against this code.
