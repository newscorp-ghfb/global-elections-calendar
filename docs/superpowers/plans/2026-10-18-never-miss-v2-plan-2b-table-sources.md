# Never-miss v2, Plan 2b: OSCE, IPU, A-WEB, Carter Center and EEAS — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Revision 3 (2026-10-18).** This revision folds in three documents:
- the red-team review of revision 1 (plan SHA-256 `92b307b5…`,
  `Downloads/never-miss-v2-plan-2b-red-team-review-2026-10-18.md`);
- its follow-up on B06/B07 (`Downloads/claude-code-plan-2b-response-2026-10-18.md`);
- the review of revision 2 (SHA-256 `c0dfa0b7…`,
  `Downloads/never-miss-v2-plan-2b-revision-2-review-2026-10-18.md`): U01 repeated headers
  (Task 2), U02 yearless Carter rows (Task 7), U03 terminal status conflicts (Task 4), and two
  documentation clarifications (R3 and the verification status).

"Review record" lists every review finding with its ruling, owning task, test and status.

**Goal:** Add the five single-page table sources (OSCE, IPU, A-WEB, Carter Center, EEAS) as
adapters that account for every row or cell as an input unit. Pay off the Plan 1 and Plan 2a
items deferred to this plan. v1 keeps running unchanged.

**Architecture:**
- **`sources/tables.py`** (new, layer 5) holds the bs4 helpers that the five adapters and
  ElectionGuide share:
  - a check that the page is complete;
  - a table's own rows and each row's cells;
  - tables found by their header text;
  - the §12.6 source-link rule;
  - a check for dated text beside a table.
- **`sources/base.py`** gains:
  - `PageParse` and `parse_pages`, the per-page driver;
  - `label_scope`, the one rule for a label that names a subdivision, used by ElectionGuide,
    OSCE and A-WEB.
- **`places.py`** gains `named_subdivisions`.
- **`ledger.py`** gains three discovery rule types:
  - the rows of a table found by its headers;
  - the table in each named heading's section;
  - the cells of the table that holds a matching link.

  Each rule has its own stdlib `html.parser` counter. The counters share no code with the
  adapters.
- **Each adapter** is one module, `sources/<source>.py`, registered in `COUNT_RULES`,
  `runner.DEFAULT_ADAPTERS` and the import-linter independence contract.

**Tech Stack:**
- Python 3.14.1;
- `beautifulsoup4` 4.15.0 + `lxml` 6.1.3 (adapters);
- stdlib `html.parser` (ledger);
- `pycountry`, used only by `scripts/build_subdivisions.py`.

No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-16-never-miss-v2-design.md`.
- Read these sections before you start:
  - §5.2, §6.1–§6.4;
  - §7 (the OSCE, IPU, A-WEB, Carter Center and EEAS rows);
  - §9.1–§9.3, §10.2–§10.5;
  - §12.6 "Links".
- Where this plan and the spec differ, the plan wins *only* for the items under "Spec
  corrections".
- Plan 2a (`docs/superpowers/plans/2026-10-17-never-miss-v2-plan-2a-sources-core.md`) is built
  at `f5f3a1c`. Its Interfaces blocks describe the code, except where the errata below say
  otherwise.

## "As built" errata (read first)

Neither earlier plan document was re-rendered after its review rounds. The code differs from
their text in these places.

**Plan 1** (built at `8632297`; Plan 2a's preamble has the full list):
- The test count is 415, not 379.
- Task 5's Interfaces sentence "<Name> (part of <Parent>) → `unknown:<key>@<parent ID>`" is
  stale. A name that is one of the parent's registered subdivisions resolves to that subdivision.
- These also changed:
  - the T4 date rules (wraps of at most 5 months, ascending day lists);
  - the T6 rule for a body named inside another body's name;
  - T7's RecursionError → `api_error`;
  - the final-round items.

**Plan 2a** (built at `f5f3a1c`: 753 tests, mypy 44 files, ruff clean, `Contracts: 2 kept, 0 broken`):
- **F-02 and F-03 follow spec §7, not the plan text.**
  - A Wikipedia page with text outside an allowed place is `layout_not_recognised`, never
    `valid_empty`.
  - ElectionGuide adds its `coverage_gap` note ("past list starts empty") whenever the past view
    is `ok` or `valid_empty` and no start was kept.
- **The Wikipedia text grammar is strict.** Text in a counted section must sit in one of:
  - an `li`;
  - a maintenance box;
  - a sub-heading's `h3`–`h6` or its edit link;
  - a `style` element.

  A maintenance box is only a `table` or `div` with class `ambox`, `metadata` or `navbox`, or
  an element inside one (N-3). A `div.mw-heading` may hold only its heading (N-2).
- **`PageCoverage.detail`** says where a page failed. Only a page without units has one.
- **`base.PAGE_REASONS`** maps each unit-less page outcome to its reason code;
  `coverage_reasons()` builds the reasons.
- **Ledger rules:**
  - F-04: a unit-less page outcome must agree with the download (`_non_unit_problems`).
  - N-5: `unfinished` coverage is accepted only for a request in `raw.unfinished`.
- **Runner (F-05, N-1):**
  - each slot has its own failure handling;
  - `(_work, args)` is pickled with `ForkingPickler` before the `Process` starts;
  - `AdapterSpec.source` must match `[a-z0-9_-]+`.
- **F-09/N-6:** place inheritance follows `_item_body(...)[3]`; `_place_for_children` is gone.
- **Other fixes:**
  - F-01: `dates.py` and `offices.py` use `.get` lookups.
  - F-07: `_GOVERNOR` matches "vice gubernatorial".
  - `build_subdivisions` raises `BuildError` on a name collision.
  - ElectionGuide's coverage check runs only when the past view's outcome is `ok` or
    `valid_empty`.

## Plan series

1. **Foundations** (done, `8632297`).
2. **Sources:**
   - 2a: contract, ledger, runner, ElectionGuide, Wikipedia (done, `f5f3a1c`).
   - **2b (this plan):** OSCE, IPU, A-WEB, Carter Center, EEAS, the shared label and link rules,
     and the deferred items.
   - 2c: NDI and EISA, with the dynamic-requests contract they need (pagination, EISA's table
     id). Plan 2c also settles the Plan 1 date minors (M6, M7, L70, L72, L81) against EISA's
     text.
3. **Merge.**
4. **Health, snapshots, feed and publishing.**
5. **Workflow, extension v2.0.0 and rollout.**

**Not in this plan:**
- no change to `scraper.py`, `elections.json`, `.github/workflows/` or `extension/`;
- nothing is pushed or merged;
- no network access.

The fixtures were captured during plan writing, through `Fetcher` with `trust_bundle`. They are
copied from `.scratch/plan2b/captures-2026-10-18/` in this worktree (git-ignored).

## Global Constraints

Plan 1's and Plan 2a's Global Constraints all still hold:
- **Code:**
  - the layering;
  - civil dates;
  - no network in tests.
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
  - adapters never raise on page content;
  - no units from a failed page;
  - claim links come from the page's own content;
  - a duplicate names its original.
- **Fixtures:** byte-exact.

This plan adds:

- **No `valid_empty` from these five adapters (P23).** Each list is cumulative or year-long.
  - A matched table with no rows is `layout_not_recognised`, detail `"the table has no rows"`.
  - For Carter, a page with no usable section gets the detail `"no section found"`.

  §9.3 counts `valid_empty` as a drop explanation, so a wrong one would promote an empty
  baseline.
- **Relevance comes from the date cell (P24),** not the whole row. An election label such as
  "By-elections to the Senate" must not trip §6.1's "to" marker. An empty, unreadable or missing
  date cell gives `unknown` (`relevance("")` is `unknown`), never `before_window`.
- **A row's cells are its own `td` and `th` children, in order (P41).** A row header
  (`<th scope="row">`) is data.
- **Every claim link goes through `tables.source_link` with the source's §12.6 hosts (P44).** The
  rule is the extension's rule:
  - `https`;
  - no user info;
  - port empty or 443;
  - the lower-cased IDNA hostname equals an allowed host or ends in `.` + an allowed host.

  How each case is handled:
  - A missing href gives the page URL.
  - A rejected href gives the page URL, and the unit is partial `link_rejected` unless a stronger
    partial reason applies.
  - A malformed href never raises.
  - A-WEB never uses page links: its claim link is always the list URL.
- **Content never raises.** Hrefs, years, dates and ports from the page are parsed by code that
  turns failure into an outcome. `DateSpan` raises `RecordError` outside 1900–2199, so every year
  is checked before a span is built (P43).
- **A label that names a registered subdivision goes through `base.label_scope` (P38):**
  ElectionGuide, OSCE and A-WEB. IPU, Carter and EEAS name no sub-national body.
- **Adapters take no options.**
  - Their `AdapterSpec.options` stay `()`.
  - Worker arguments stay plain picklable data: the pre-pickle (N-1) runs outside the spawning
    context.
  - Page keys are static: `requests(window)` returns the same one request for every window.
- **Unit IDs and page keys:**

  | Source | Page key | Unit ID |
  |---|---|---|
  | `osce` | `elections` | `osce:elections/r<n>` |
  | `ipu` | `elections` | `ipu:elections/r<n>` |
  | `aweb` | `calendar` | `aweb:calendar/r<n>` |
  | `carter` | `observed` | `carter:observed/<section>-r<n>`, section `monitored` or `expert` |
  | `eeas` | `missions` | `eeas:missions/r<i>c<j>` |

- **Headers are matched by exact normalised text (P33).** Each header is
  `collapse_ws(text).casefold()` of a `th` in the table's own `thead`. Columns are found by
  header, never by position.
- **Every header a source reads must appear exactly once in its table (U01).** A repeated one is
  `layout_not_recognised`, detail `"repeated header: <h>"` (several are joined by ", "). The
  ledger's header rule applies the same check independently. Extra columns with other names
  are fine. ElectionGuide applies it to the five headers it reads.

## Review Focus

These are the five inputs most likely to hurt a user that the spec implies but no step spells
out. Each one is pinned by the named tests, in the task that owns the code.

1. **A source page that changes shape.** For example:
   - a column added, reordered, renamed or repeated (OSCE's 5→4 change broke v1);
   - two tables with the same headers;
   - a section heading kept while its table is removed, repeated or joined by a second table;
   - rows emptied out;
   - an event written as text beside the table;
   - a body cut off mid-table.

   Each gives a named `layout_not_recognised` with a detail, or a `coverage_gap` note. None gives
   a silent clean result or an exception. Pinned by:
   - `test_columns_are_found_by_header_not_position` (Task 4);
   - `test_sections_are_bound_to_their_heading` (Task 7);
   - `test_dated_text_beside_the_table_is_a_coverage_gap` (Tasks 4–8);
   - `test_broken_pages_get_an_outcome_never_units` (Tasks 4–8).

   **Residual risk:** an event moved further away than the table's own parent element, or
   dropped from the page entirely, is not detected here. Plan 4's drop checks see only large
   losses.
2. **IPU dates that are month placeholders.** 197 of the 234 IPU claims fall on a month's last
   day ("31 Dec 2026"), including 28 and 29 February.
   - They become months: a documented conservative inference (P25). `date_text` keeps the raw
     day.
   - A genuine 31st also becomes a month. That is the safe direction, because a month still
     overlaps the real day in the merge.

   Pinned by `test_month_end_dates_are_months` (Task 5), with a day that is not a month end as
   the negative control.
3. **Year rollover.**
   - A-WEB's "all" view shows one year, so its row count falls each January. Its coverage
     carries the list's year (P31). Plan 4 keeps December events through January (R2).
   - EEAS adds a "2027" year heading.

   Pinned by `test_coverage_year_is_the_lists_year` (Task 6) and
   `test_a_new_year_heading_is_ignored_and_its_missions_parsed` (Task 8).
4. **Encoded, look-alike and hostile text:**
   - `Cote d&#8217;Ivoire`, `São Tomé e Príncipe`, `People’s Legislative Assembly` (U+2019);
   - NBSP and newlines inside a date cell;
   - en-dash ranges;
   - `javascript:` and `//[` hrefs;
   - deceptive hosts such as `cartercenter.org.evil.example`;
   - years such as `0000` and `9999`.

   Each one either resolves or parses the way a reader would read it, or becomes a named outcome.
   Pinned by:
   - `test_entity_and_curly_quote_names_resolve` (Task 7);
   - `test_source_link` (Task 2);
   - `test_token_grammar` (Task 7);
   - `test_mission_years_outside_the_model_are_outcomes` (Task 8).
5. **Words and shapes a source has never used before:**
   - an OSCE badge other than Upcoming/Past, or two contradictory statuses;
   - an IPU designation other than direct, indirect or appointed;
   - a Carter row that is not a country row, a `thead` header or the known footnote, including
     a yearless row such as "Chile | TBC";
   - an EEAS cell that is not a year, a blank or `EOM <Country> <YYYY>`;
   - a subdivision named in a national-calendar label ("Republika Srpska Early Presidential
     election").

   Each is a partial or unparsed unit with a reason. None is silently dropped, and none gets a
   false national identity. Pinned by:
   - `test_badges` (Task 4);
   - `test_designations` (Task 5);
   - `test_row_kinds` (Task 7);
   - `test_cell_kinds` (Task 8);
   - `test_label_scope_precedence` (Task 3).

**Known limits, by design.** The measured values include each of these, and each is visible:
- **Relevance before September:** units dated January–August of the current year have relevance
  `unknown`, not `before_window`. This is Plan 2a's limit: §6.1 works on years.
- **Default level:** A-WEB and ElectionGuide default to level `national` for a label that names
  no subdivision. This is a documented source assumption, kept as Plan 2a approved it for
  ElectionGuide.
- **Demonyms:** `named_subdivisions` finds names, not demonyms. "Scottish Parliament election"
  names no subdivision, so it keeps the default. Wikipedia's P4 handles that case through the
  page structure.
- **Matched words:** `named_subdivisions` reports the words that matched. For "Ohio State Senate
  election" that is "Ohio State", because the index strips " state".
- **Old rows:** OSCE has 454 rows and Carter has 42 rows older than ±5 years. They are
  `unparsed implausible_date` with relevance `before_window`, which raises no attention.
- **A-WEB lists only the current year.** December events drop out of A-WEB in January. January
  events appear only once A-WEB publishes the next year (R2).

## Spec corrections

These were found while measuring the 2026-10-18 captures, or in the review of revision 1.
- **Semantic decisions:** P22–P31, P38, P39 and P43 change what the calendar says or flags, so
  they need the user's approval before Task 3 starts. Each one gives the alternative and what it
  would cost. The review's conditions on them are in "Review record".
- **The other corrections** refine names, files or details.

| ID | Spec says | This plan does | Why / alternative |
|---|---|---|---|
| P22 (semantic) | §9.1 ignored reasons: `header_row`, `year_heading`, `empty_cell`, `container_item`, `appointed_chamber`, `duplicate` | Adds `inactive_chamber`: an IPU chamber named "… (Suspended)" or "… (Dissolved)" (10 rows). Adds `no_expected_date`: an IPU expected date of "-" (5 rows). Adds `footnote`: Carter's "*These missions were targeted…" row (1) | Each is a fact, not a failure. The rows stay in the source's accounting (`ignored_reasons`), and Plan 4 watches their counts (R1). Alternative: make them unparsed. Then Kuwait, Sudan and the 5 "-" rows become permanent attention items |
| P23 (semantic) | §7/§9.3 allow `valid_empty` | These five never return `valid_empty`. A page with zero units is `layout_not_recognised` | `valid_empty` explains a drop (§9.3), so an empty render would promote an empty baseline. This does not catch a populated table whose rows are all wrongly ignored; that is R1. The only plausible genuinely empty page is A-WEB in early January, which costs a red run until A-WEB publishes |
| P24 (semantic) | §6.1 relevance comes from "its text" (the unit's text) | Relevance comes from the date cell: OSCE's date `div`, IPU's expected-date cell, A-WEB's date cell, Carter's date cell. For EEAS the unit is the cell. The full row stays the unit's text | OSCE's "4 Oct 2008 … By-elections to the Senate" is `unknown` by row text and `before_window` by date |
| P25 (semantic) | §7 IPU has no date-precision rule | An expected date on its month's last day becomes `DateSpan.month`; `date_text` keeps the day. Any other day stays a day. Both stay `expected_renewal`/`tentative` and are never an announced date (R4) | 197 of 234 dates are month ends. As days, "31 Dec 2026" gives Fiji, Haiti ×2, Libya, Madagascar and Somalia ×2 a phantom polling day. IPU says its expected dates are calculated from terms. This is a conservative inference, not proof that every month end is a placeholder. Alternative: keep days |
| P26 (semantic) | §9.2 "year within ±5 of T" | IPU expected renewals use ±10 years. This is only a plausibility bound, separate from display-window filtering | Benin (31 Jan 2033) and the Central African Republic (31 Dec 2032) have 7-year terms. At ±5 they become 2 permanent relevant attention items. Alternative: keep ±5 |
| P27 (semantic) | §7 IPU names only "appointed" and "indirect" | Any designation other than "Directly elected", "Indirectly elected" or "Appointed" → `unparsed designation_unrecognised`, with the designation in `leftover` | There are 4 "Other" rows: Benin Senate, Burkina Faso's PLA, Lesotho Senate, UAE FNC. Alternative: partial with a claim, which would create renewal contests for mostly appointed bodies |
| P28 (semantic) | §7 Carter/EEAS: `evidence_kind=observation`, no office fields. §10.2 rule 2: class `general` → umbrella | Observation claims carry `office_class="general"`, `aggregate=True`, `kind="aggregate"`, `level="unknown"`, `institution=None`, `jurisdiction_kind="nationwide"` and `date_meaning="unknown"` (P39). Plan 3 gives `evidence_kind=observation` the role `weak` before the umbrella rule (R5, R6) | The sources name no office. As umbrellas, an unmatched month-only Carter claim would become a standalone `aggregate` contest (§10.4). No new office class is needed |
| P29 (semantic) | §7 Carter: "comma-separated `Month YYYY` / `Month-Month YYYY` tokens, one claim per token … Expert missions are flagged" | **Tokens:** split on `,` and `;`. A leading "and " is dropped, and a trailing `*` means a targeted mission. Each token must parse to exactly one span; one that does not goes to `leftover`. Tokens outside ±5 years follow P43. A repeat of an earlier (span, targeted) pair in the row is dropped. **The flag** goes in `office_label`: "Carter Center election observation" or "Carter Center expert mission", plus " (targeted)" for a starred token. **Sections** follow P40 | The page has decades of history (1989–2026) and 4 free-text cells (Egypt, Nepal, Nigeria, the US). The model has no flag field, and the label is what the extension shows |
| P30 (semantic) | §7 OSCE: "Badge span → status words … Year-only → undated" | **Badges:** "Upcoming" and "Past" set nothing; "Past" is not evidence that the election was held. "Postponed" → `postponed`; "Cancelled" or "Canceled" → `cancelled`. Any other badge → partial `status_unrecognised`. **Statuses (U03):** the row's statuses are its badges' statuses plus the date text's own status (`parse.status_claim`, e.g. "Held 25 Oct 2026"). Two or more different ones → partial `status_conflict` with `status_claim=None`. This is terminal: no other field supplies a status. One status → that status; none → `None`. **Evidence:** whenever a conflict or an unrecognised badge exists, every badge text other than Upcoming/Past goes in `leftover`, in page order, whichever reason the unit ends with. **"(indirect)"** in the label → `indirect=true`. **A date cell without a `div`** → unparsed `date_unparsed` | Badge order, or which field holds a status, must not choose the answer. v1 read the badge into the date ("25 Oct 2026Upcoming"). The date-text status is part of the set because a "Postponed" badge beside "Held 25 Oct 2026" is the same kind of contradiction. OSCE's date text holds no status today (measured) |
| P31 (semantic) | §7 A-WEB has no level, office or year rule | **Level:** default `national` (P38 withholds it when a subdivision is named). **Primaries:** a label matching `\bprimar(?:y\|ies)\b` → unparsed `office_not_modelled`. **Year:** `PageCoverage.year` is the year of every parsed claim when they all share one, else `None` | A primary as a claim would be a phantom Ghana presidential anchor. The year lets Plan 4 compare drops within one year. It is inferred from the claims, not verified page scope, so Plan 4 must still keep December evidence (R2) |
| P32 | §7 IPU has no IDs | `source_event_id = "ipu:<chamber code>"`, taken from an accepted chamber link `/parliament/XX/(XX-YY99)/`; the link is the chamber's page | It is stable per chamber (all 234 claims). It identifies a chamber, not an election cycle (R3) |
| P33 | §7 IPU layout: header "contains" two phrases | Every source matches whole header texts; IPU's are `expected date of next elections` and `principal mode of designation of members`. Each header a source reads must appear exactly once (U01) | One rule for all sources, and a renamed or repeated header is loud (`layout_not_recognised`). With a first-match rule, "Date \| Country \| Election \| Activity \| Date" read the first date and never looked at the second (review U01). No fixture table repeats a header it reads (measured); ElectionGuide's two blank `th`s are not read |
| P34 | §7 "a second pass counts the same container's rows/items" | Three new ledger rule types (Task 2). Each source's rule is in `ledger.COUNT_RULES`, not in its adapter | Plan 2a's P6: an adapter cannot certify itself |
| P35 | §16 fixtures | `tests/fixtures/<source>/2026-10-18/<page key>.html`, with a `PROVENANCE.md` built from the capture's `provenance.json`. The 2026-10-16 IPU file stays, for `build_institutions` | That old file is older and CRLF-converted. The new captures are byte-exact `Fetcher` bodies |
| P36 | §7 EEAS | A cell that does not match → unparsed `unrecognised_cell`. `date_text` is the year. Duplicates follow P42 | This names the spec's unnamed reason |
| P37 | Plan 1 L127d | `redact_url` also redacts path parameters: every `;…` in a path segment → `;REDACTED`. `redact_text` redacts `;name=value` in bare paths | A-WEB is a `.do` site, where `;jsessionid=` is common. The capture had none (measured), so this is defensive (Task 1) |
| P38 (semantic, B07) | §6.3/§6.4, with Plan 1 C18: "a `subdivision` is geography, not evidence of level" | `base.label_scope`, for ElectionGuide, OSCE and A-WEB. (1) `named_subdivisions` finds the registered subdivisions of the place named in the label, skipping the place's own name. (2) If there are any, `jurisdiction` is their names joined by ", ", `jurisdiction_kind="subdivision"`, and the source default is **withheld** (`unknown`). (3) `classify` runs with that jurisdiction kind, so its existing evidence wins: a distinctive national chamber stays national; a qualified chamber, governor, mayor or referendum stays subnational. (4) The level is `unknown`, and the unit partial `level_unresolved`, only when the office is recognised and gives no level hint. A label that names no subdivision changes nothing | OSCE r52 "Republika Srpska Early Presidential election" is today `iso:BA/president`, a false Bosnia-wide presidential contest. A-WEB r5 "2026 Gilgit Baltistan Assembly Election" is today a national aggregate. This keeps C18 (no new level evidence) and P4. The user chose it on 2026-10-18 (option 1). Alternatives: subnational (reverses C18), or national (r52 stays false) |
| P39 (semantic, B06) | §7 Carter: month tokens. EEAS: "Never sets a date" | Carter and EEAS claims have `date_meaning="unknown"`; `date_text` keeps the raw token or year | A mission's year or observation month is not a polling period. Whether an observation may ever be the selected date is an open Plan 3 decision (R5) |
| P40 (B01) | §7 Carter: "the tables under the headings" | **Section:** the part of the page between its `h2` and the next `h2`. **Heading:** must appear exactly once, else `layout_not_recognised` ("heading '<h>' appears <n> times"). **Table:** the section must hold exactly one top-level table. Two or more → `layout_not_recognised` ("section '<h>' has <n> tables"). None → the section is missing, with note `coverage_gap` "section has no table: <h>". **Missing heading** → note "section not found: <h>". **No usable section** → `layout_not_recognised` "no section found". **Every adapter:** dated text in the table's parent element, outside the table → note `coverage_gap` "dated text beside the table: <text>" | `find_next("table")` reused the Expert table for both sections when the first table was removed (measured). The dated-text check covers only the table's own parent, because Carter's wider section text holds "(Updated Sept. 25, 2025)" |
| P41 (B02, U02) | §7 Carter: "header rows → ignored `header_row`" | A row is `header_row` only if it sits in the table's own `thead` and every cell is a `th`. A one-cell row is `footnote` only if its casefolded text equals the page's own footnote (`FOOTNOTE`, Task 7). Every other row is data: an all-`th` body row is parsed like any row, and any other one-cell row is unparsed `too_few_cells`. All adapters read `td` and `th` cells alike | `<tr><th scope="row">Chile</th><td>May 2026</td></tr>` is data. Revision 2's "no digit" test ignored yearless evidence such as "Chile \| TBC" and "*Chile mission postponed; date TBD" (review U02). The page has no `thead` and no `th` cell today, so no header label exists to match; markup is the only evidence a row is a header (measured). A reworded footnote becomes a visible `too_few_cells` unit, which is the intended direction |
| P42 (B03) | §7 EEAS: "a repeated href → ignored `duplicate`" | A cell is a duplicate only when its text and its claim link both equal those of an earlier cell that gave a claim. A cell that gave no claim reserves nothing. Carter drops only a repeated (span, targeted) pair | A shared archive or country link must not hide a different country or year. ElectionGuide's duplicate rule already compares the whole assertion |
| P43 (semantic, B04) | §9.2 ±5 years | **Carter:** an implausible token whose last year is before the current year is history: no claim, and the unit is not marked. An implausible token that reaches the current year or later is future: it goes to `leftover`, and the unit is partial (with claims) or unparsed `implausible_date`. **EEAS:** a year outside ±5 → unparsed `implausible_date`, checked before `DateSpan.of_year` | "May 2026, May 2032" kept only May 2026 and stayed parsed (measured). `DateSpan.of_year(0)` raises `RecordError` |
| P44 (B05) | §12.6: the extension checks the hosts | `tables.source_link` applies the same rule in the adapters (Global Constraints) | `urljoin` resolves a URL; it does not restrict it. `//example.invalid/x` and `javascript:` passed, and `//[` raised `ValueError` (review E6) |
| P45 | Plan 2a `build_subdivisions` keys strip a trailing `(…)` | They also strip a trailing `[…]` | 27 pycountry names carry one: "Wales [Cymru GB-CYM]", 21 Swedish counties ("Blekinge län [SE-10]"), Catalonia, Galicia, Illes Balears, Bender and Sana'a city. Their keys were `wales cymru gb cym`, `blekinge lan se 10`, …, so `find("GB", "Wales")` failed. Measured: 27 keys renamed, no other key added or removed, and the other 752 tests unchanged |

**Also settled (no spec change):**
- **M6, M7, L70, L72, L81 (Plan 1 date minors):** these move to Plan 2c, with EISA's text.
  OSCE's 634 date `div`s hold only 4 shapes: `D Mon YYYY`, `DD Mon YYYY`, `Mon YYYY` and
  `YYYY`. They contain no Cf character, no other dash, and no "(postponed)" or "(TBC)"
  (measured).
- **L82 (identical spans):** Carter drops a repeated (span, targeted) pair within a row (P29).
- **A-WEB links:** §7 says external EMB links are "kept as claim links only if they pass the
  allowlist". A-WEB's §12.6 allowlist is `aweb.org` only, so no EMB link can pass. The claim
  link is therefore always the list URL, and A-WEB calls no `source_link`.
- **Dynamic pagination vs static `requests()`:** none of these five pages paginates. The decision
  moves to Plan 2c, before NDI.
- **Deferred items that stay deferred:**
  - N-4: before Plan 4 renders reasons;
  - N-8: before Plan 3 relies on office splitting;
  - F-08: Plan 3, with P38's jurisdictions as input (R7);
  - F-10: before Plan 5;
  - worker tracebacks: before the first CI run;
  - Plan 1's other deferred minors (L64, L71, L91, L94, L101, L109–L112, L118, L127b, L127e).
    None of them is on a code path this plan changes.

## Review record

The review findings come in three kinds:
- **Agreed fix:** this plan changes code, and the named test will pin the change.
- **Agreed decision:** a semantic ruling.
- **Open Plan 3 policy:** deliberately left to Plan 3, with its completion stage.

**Status:** no fix is verified yet. A row becomes *verified* only when the SDD ledger records its
task's commit, with the named test passing and its mutation killed. A row with a later-plan part
(R1–R11) is split: its Plan 2b part becomes verified here, and its later part stays open until
that plan's own test passes. The column "Review test" maps the first review's acceptance tests
B-T01 to B-T10. U01–U03, D1 and D2 come from the revision 2 review.

| ID | Kind | Ruling | Task · test | Review test | Status |
|---|---|---|---|---|---|
| B01 | Agreed fix | P40: sections are bound to their heading; ambiguity fails; a missing table is a gap; dated text beside a table is a gap | T2 `test_new_rules_on_synthetic_pages`; T7 `test_sections_are_bound_to_their_heading`; T4–T8 `test_dated_text_beside_the_table_is_a_coverage_gap` | B-T01, B-T02 | planned |
| B02 | Agreed fix | P41: `th` row headers are data; strict header and footnote rules | T2 `test_row_cells`; T7 `test_row_kinds`, `test_row_header_markup_gives_the_same_claims` | B-T03 | planned |
| U01 | Agreed fix | U01: a header a source reads must appear once, in the adapters and independently in the ledger | T2 `test_header_columns`, `test_new_rules_on_synthetic_pages`, ElectionGuide `test_a_repeated_header_is_not_a_layout`; T4 `test_columns_are_found_by_header_not_position`; T5, T6 `test_broken_pages_get_an_outcome_never_units` | B-T01 | planned |
| U02 | Agreed fix | P41 revised: `header_row` only in `thead`; `footnote` only by its exact text; yearless rows stay visible | T7 `test_row_kinds`, `test_fixture_ledger_balances` (the real footnote still ignored) | B-T03 | planned |
| U03 | Agreed fix | P30 revised: a status conflict is terminal and keeps its evidence under any reason | T4 `test_badges` | — | planned |
| D1 | Documentation | R3: a reschedule needs evidence of the same cycle; date proximity plus a chamber ID is not enough | R3 | — | done in this revision |
| D2 | Documentation | Plan 2b parts verified separately from later-plan parts; R5 names say "unknown-meaning" | this section, R5, "After Plan 2b" | — | done in this revision |
| B03 | Agreed fix | P42: a duplicate needs the same text and link; Carter keeps targeted repeats | T7 `test_token_grammar`; T8 `test_cell_kinds` | B-T04 | planned |
| B04 | Agreed decision + fix | P43: future tokens are visible; EEAS years are checked before spans | T7 `test_token_grammar`; T8 `test_mission_years_outside_the_model_are_outcomes` | B-T05, B-T07 | planned |
| B05 | Agreed fix | P44: one `source_link` with the §12.6 rule | T2 `test_source_link`; T4, T5, T7, T8 `test_off_host_links_fall_back` | B-T06 | planned |
| B06 | Agreed decision (adapter) | P39: observations get `date_meaning="unknown"` | T7/T8 `test_fixture_claims` | — | planned |
| B06 | Open Plan 3 policy | Can an observation be the selected date? §10.5 step 1 lists it last. It is never a polling date, and never makes a contest Held/Ongoing | R5 | B-T09 | open, owner Plan 3 |
| B07 | Agreed decision (user, option 1) | P38: a subdivision becomes the jurisdiction; the default is withheld; existing evidence wins | T3 `test_label_scope_precedence`, `test_named_subdivisions`; T4 `test_one_claim_field_by_field` (r52); T6 `test_claims_field_by_field` (r5) | B-T08 | planned |
| B07 | Requirement | An unknown level never bypasses jurisdiction in matching | R7 | — | owner Plan 3 |
| P22 | Agreed decision, condition | Ignored facts stay in the accounting; a shift into them is visible | R1 | B-T10 | planned + Plan 4 |
| P23 | Agreed decision, condition | Conservative; a populated table with every row ignored is Plan 4's case | R1 | B-T10 | planned + Plan 4 |
| P24 | Agreed decision | Date cell only; the full row is kept; empty → `unknown` | T4 `test_date_cell_rules` | — | planned |
| P25 | Agreed decision, condition | A conservative month inference that keeps the raw day; an expected date is never announced | T5 `test_month_end_dates_are_months`; R4 | — | planned + Plan 3/5 |
| P26 | Agreed decision | Plausibility bound only | T5 `test_far_renewals` | — | planned |
| P27 | Agreed decision | Unparsed, visible | T5 `test_designations` | — | planned |
| P28 | Agreed decision | Weak role before umbrella | R6 | B-T09 | Plan 3 |
| P29 | Agreed decision, revised | Tokens follow P40, P41, P42 and P43 | T7 | B-T05 | planned |
| P30 | Agreed decision, revised | Conflicting statuses have their own terminal outcome (U03) | T4 `test_badges` | — | planned |
| P31 | Agreed decision, condition | Drops are compared within one year; December evidence is kept | T6 `test_coverage_year_is_the_lists_year`; R2 | B-T10 | planned + Plan 4 |
| P45 | Agreed fix (found while re-measuring) | Subdivision names with a trailing bracket | T1 `test_keys_strip_a_trailing_bracket` | — | planned |

## How to execute this plan

- **Where:** the worktree `C:/Users/senescalk/Desktop/elections-calendar/.claude/worktrees/never-miss-v2`,
  branch `feat/never-miss-v2`.
  - Do not create worktrees, do not switch branches, do not commit to `main`.
  - Keep the shell in the worktree. Use `( cd … && … )` subshells for anything elsewhere.
- **Style:** this plan pins names, signatures, rules and test values; you write the bodies.
  Private helpers are yours. If a rule is ambiguous, stop and ask the controller. Never guess a
  value.
- **Measured values:** every count in the tests was measured on the fixtures, by prototypes that
  implement exactly these rules.
  - Adapter prototypes: `.scratch/plan2b/proto/<source>3.py` and `common3.py`; Carter's is
    `carter4.py` (U02), whose fixture dump `v4_carter.txt` equals `v3_carter.txt`. The U02
    synthetic page is `.scratch/plan2b/check/u02_carter.html`, its dump
    `.scratch/plan2b/u02_carter.txt`.
  - Counter prototype: `.scratch/plan2b/proto/rules3.py`.
  - P38 check: `check_precedence.py`.
  - Dumps: `.scratch/plan2b/v3_<source>.txt`, where `U` lines are units and `C` lines are claims.
  - Expected P45 output: `.scratch/plan2b/check/subdivisions_fixed.yaml`.

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
- **Mutations:** one per new test, in `.scratch/mutations/plan2b-task-<N>.json`, in the format of
  `.scratch/mutate.py`. Stage the task's files with `git add` first, and run with
  `PYTHONDONTWRITEBYTECODE=1`.
- **Handover:** after every task, record the commit, the Review record rows it verified and the
  next task in two files:
  - `C:/Users/senescalk/Desktop/handovers/elections-v2-plan2b-sdd-ledger.md`;
  - `C:/Users/senescalk/Desktop/handovers/elections-v2-RESUME.md`.
- **Hook:** the Desktop PostToolUse hook runs `ruff check --fix` on each edited `.py`. Check
  `git diff --stat` for unrelated rewrites.

## File structure

| Path | Responsibility | Task |
|---|---|---|
| `elections_calendar/sources/wikipedia.py`, `ledger.py`, `sources/base.py`, `runner.py`, `README.md` | F-16, N-7, R2-2, R2-3 | 1 |
| `elections_calendar/fetch.py` | L127d path parameters | 1 |
| `scripts/build_subdivisions.py`, `data/subdivisions.yaml` | P45 bracketed names | 1 |
| `tests/fixtures/{osce,ipu,aweb,carter,eeas}/2026-10-18/` | byte-exact captures + `PROVENANCE.md` | 2 |
| `elections_calendar/sources/tables.py` | shared bs4 helpers, `source_link`, `dated_text_beside` | 2 |
| `elections_calendar/sources/base.py` | `PageParse` and `parse_pages` (Task 2); `LabelScope` and `label_scope` (Task 3) | 2, 3 |
| `elections_calendar/sources/electionguide.py` | uses `tables.py` (Task 2) and `label_scope` (Task 3) | 2, 3 |
| `elections_calendar/ledger.py` | `HeaderTableRowsRule`, `HeadingTablesRule`, `LinkTableCellsRule` and their counters | 2 |
| `elections_calendar/model.py` | `IgnoredReason` gains `inactive_chamber`, `no_expected_date`, `footnote` | 2 |
| `elections_calendar/places.py` | `named_subdivisions` | 3 |
| `elections_calendar/sources/osce.py` … `eeas.py` | one adapter each | 4–8 |
| `ledger.COUNT_RULES`, `runner.DEFAULT_ADAPTERS`, `importlinter.ini` | one entry per adapter | 4–8 |
| `tests/unit/test_tables.py`, `tests/unit/test_places.py`, `tests/adapters/test_<source>.py` | tests | 2–8 |

## Tasks

### Task 1: Plan 1 and Plan 2a carry-overs (F-16, N-7, R2-1, R2-2, R2-3, L127d, P45)

**Files:**
- Modify:
  - `elections_calendar/sources/wikipedia.py` (the item walk, `_has_data_table`, docstrings);
  - `elections_calendar/ledger.py` (`SectionItemsRule`, `_SectionItems`, `_page_problems`);
  - `elections_calendar/sources/base.py:86-89`, `elections_calendar/runner.py:88,235`,
    `README.md:101`;
  - `elections_calendar/fetch.py` (`redact_url`, `redact_text`);
  - `scripts/build_subdivisions.py` (`_keys`, the module docstring), then regenerate
    `data/subdivisions.yaml`.
- Test: `tests/adapters/test_wikipedia_national.py`, `tests/unit/test_ledger.py`,
  `tests/unit/test_fetch.py`, `tests/unit/test_subdivisions.py`

**Interfaces:**
- Consumes:
  - `wikipedia._is_maintenance(tag) -> bool`, `_MAINTENANCE_TABLES`;
  - the test helpers `synth`, `one_page`, `wiki_page`, `of` and `ENTRY` in
    `test_wikipedia_national.py`;
  - `build_subdivisions._keys(name) -> set[str]`.
- Produces:
  - `SectionItemsRule.box_classes: frozenset[str] = frozenset()`. The `"wikipedia"` rule sets
    `frozenset({"ambox", "metadata", "navbox"})`.
  - The Wikipedia data-table outcome gets the detail `"section <key>: data table <dl>"` (or
    `<table>`).
  - `data/subdivisions.yaml` with `wales: GB-WLS`, `blekinge lan: SE-K`, …; Task 3 relies on
    it.

- [ ] **Step 1: Write the failing tests.**

```python
# test_wikipedia_national.py
@pytest.mark.parametrize("box", [
    '<table class="ambox"><tr><td><ul><li>This section needs additional citations.</li></ul></td></tr></table>',
    '<div class="navbox"><ul><li>Elections in Sweden</li></ul></div>',
    '<div class="metadata"><ul><li>5 March: <a>Fiji</a>, Parliament</li></ul></div>',
])
def test_list_items_in_a_maintenance_box_are_not_units(box: str) -> None:   # F-16
    _, res = synth({"January": box + ENTRY})   # synth asserts check(raw, res).ok: adapter and ledger agree
    assert (res.coverage[0].outcome, res.coverage[0].units_seen, len(of(res))) == ("ok", 1, 1)

def test_a_data_table_names_its_section() -> None:      # N-7
    res = one_page(wiki_page({"January": "<dl><dt>5 January</dt></dl>"}))
    assert (res.coverage[0].outcome, res.coverage[0].detail) == (
        "layout_not_recognised", "section January: data table <dl>")
    res = one_page(wiki_page({"March": '<table class="wikitable"><tr><td>x</td></tr></table>'}))
    assert res.coverage[0].detail == "section March: data table <table>"
```

  - **R2-1:** in `test_a_data_table_in_a_calendar_section_is_not_valid_empty`, replace the row
    `'<p class="metadata"><dl><dt>x</dt></dl></p>'` with
    `'<span class="metadata"><dl><dt>x</dt></dl></span>'`. The expected outcome is unchanged.
  - **R2-2:** in `test_ledger.py`, add `test_coverage_for_an_unknown_key_is_one_problem`.
    `PageCoverage("z", None, "unfinished", None, 0)`, next to the fixture pages, gives exactly the
    problems `["coverage for 'z', which is no page or unfinished request"]`.
  - **L127d:** in `test_fetch.py`, add these rows to `test_redact_url`'s table:

```python
("https://www.aweb.org/eng/bbs/B0000007/list.do;jsessionid=AB12CD?menuNo=300052&option=all",
 "https://www.aweb.org/eng/bbs/B0000007/list.do;REDACTED?menuNo=300052&option=all"),
("https://x.org/a;v=1/b;sid=2", "https://x.org/a;REDACTED/b;REDACTED"),
```

    Then add `test_redact_text_redacts_path_parameters`. For
    `redact_text("url: /eng/list.do;jsessionid=s3cr3tMARKER?menuNo=1 (Caused by x; y)")`:
    - the result must not contain `s3cr3tMARKER`;
    - it must end with `"list.do;REDACTED?menuNo=1 (Caused by x; y)"`;
    - a `;` that is not followed by `name=` is left alone.
  - **P45:** in `test_subdivisions.py`, add `test_keys_strip_a_trailing_bracket`:
    - `_keys("Wales [Cymru GB-CYM]") == {"wales"}`;
    - `_keys("Blekinge län [SE-10]") == {"blekinge lan"}`;
    - `_keys("Madrid, Comunidad de") == {"madrid comunidad de", "madrid"}` (unchanged);
    - `SubdivisionIndex.load().find("GB", "Wales") == "GB-WLS"`;
    - `find("SE", "Skåne län") == "SE-M"`.

- [ ] **Step 2: Run the tests.**

  ```bash
  .venv/Scripts/python.exe -m pytest tests/adapters/test_wikipedia_national.py tests/unit/test_ledger.py tests/unit/test_fetch.py tests/unit/test_subdivisions.py -q
  ```

  Expected: FAIL for five reasons:
  - the boxed `li` is a unit;
  - there is no data-table detail;
  - there are two problems for `z`;
  - the path parameter is kept;
  - the bracketed keys are wrong.

  The R2-1 row passes before and after: it is a test fix.
- [ ] **Step 3: Implement.**
  - **F-16, adapter:** the `items` comprehension in `_parse_body` drops every `li` for which
    `_is_maintenance(li)` holds.
  - **F-16, ledger:**
    - `_SectionItems` gets the rule's `box_classes`;
    - it keeps a stack of the open `table` and `div` tags, each with a flag for "has a box class
      or is inside one";
    - an `li` opened while that flag is set gets no path, and neither does anything under it.
  - **N-7, the detail:** `_has_data_table` becomes `_data_table(elements) -> str | None`,
    returning the tag name. The caller builds the detail with `_MAX_KEY`, the way the stray-text
    detail is built.
  - **R2-2:** add the "is unfinished but its page was fetched" problem only when
    `entry.key in pages`.
  - **R2-3:**
    - in the module docstring, "a maintenance box" becomes "a maintenance box (a `table` or `div`
      with a box class)";
    - `_item_body`'s docstring says it also serves items whose date failed;
    - at `runner.py:235`, "then reads" becomes "can read";
    - remove the third blank line before `NESTED`.
  - **N-7, the docs:** add to three places that a received page that cannot be read stays
    unfinished, and its source becomes `worker_failed`:
    - the `RawPages` docstring (`base.py`);
    - the `SourceRun` docstring (`runner.py:88`);
    - `README.md:101`.
  - **L127d:**
    - `redact_url` replaces each `;` and the rest of its path segment with `;REDACTED`;
    - `redact_text` also replaces each `;name=value` run (`;[^\s/?#;=]+=[^\s/?#'"<>]*`) with
      `;REDACTED`.
  - **P45:**
    - `_keys` strips a trailing `\s*\[[^\]]*\]$` before the parenthesis rule, and the module
      docstring says so;
    - run `.venv\Scripts\python.exe -m scripts.build_subdivisions`;
    - `git diff --stat data/subdivisions.yaml` must show 27 insertions and 27 deletions, and the
      file must equal `.scratch/plan2b/check/subdivisions_fixed.yaml`.
- [ ] **Step 4: Run** the same command. Expected: PASS, including
  `test_committed_subdivisions_yaml_is_up_to_date`.
- [ ] **Step 5: Gates, mutation table, commit:**
  `fix(sources): skip maintenance-box items; name data-table sections; redact path parameters; strip bracketed subdivision names`.

  Mutations, one each:
  - drop the adapter skip;
  - drop the ledger skip;
  - drop the detail;
  - drop the R2-2 condition;
  - drop the path rule in `redact_url`;
  - drop the path rule in `redact_text`;
  - drop the bracket strip.

---

### Task 2: Fixtures, table helpers, the page driver and three discovery rules

**Files:**
- Create:
  - `tests/fixtures/osce/2026-10-18/elections.html`;
  - `tests/fixtures/ipu/2026-10-18/elections.html`;
  - `tests/fixtures/aweb/2026-10-18/calendar.html`;
  - `tests/fixtures/carter/2026-10-18/observed.html`;
  - `tests/fixtures/eeas/2026-10-18/missions.html`;
  - a `PROVENANCE.md` in each of those directories;
  - `elections_calendar/sources/tables.py` and `tests/unit/test_tables.py`.
- Modify: `elections_calendar/sources/base.py`, `elections_calendar/sources/electionguide.py`,
  `elections_calendar/ledger.py`, `elections_calendar/model.py:45-47`
- Test: `tests/unit/test_fixtures.py`, `tests/unit/test_sources_base.py`, `tests/unit/test_ledger.py`

**Interfaces:**
- Consumes: `fetch.FetchResult`, `base.page_failure`, `model.MAX_DETAIL`, `text.collapse_ws`.
- Produces, in `tables.py`:
  - `complete_html(text: str) -> bool`: the text ends with `</html>`, ignoring trailing
    whitespace and HTML comments (ElectionGuide's `_strip_trailer` rule).
  - `cell_text(tag: Tag) -> str`: `collapse_ws(tag.get_text(" "))`.
  - `row_cells(tr: Tag) -> list[Tag]`: the row's own `td` and `th` children, in order (P41).
  - `own_rows(table: Tag, *, head: bool = False) -> list[Tag]`: each `tr` whose nearest `table`
    is `table`. Rows inside its `thead` are left out unless `head` is set.
  - `header_cells(table: Tag) -> list[str]`: `cell_text(th).casefold()` of each `th` in the
    table's own `thead`.
  - `header_tables(soup: BeautifulSoup, headers: Collection[str]) -> list[Tag]`: in document
    order, each table whose header cells include every header.
  - `header_columns(table: Tag, headers: Collection[str]) -> tuple[dict[str, int], tuple[str, ...]]`
    (U01): the column index of each header that appears exactly once, and the headers that
    appear more than once, in `headers` order. A caller with a non-empty second element fails
    the page with detail `"repeated header: " + ", ".join(repeated)`.
  - `source_link(base: str, href: object, hosts: Collection[str]) -> str | None` (P44):
    - a non-`str` or blank href → `None`;
    - otherwise `urljoin(base, href.strip())`;
    - `None` when any step raises (`ValueError`, `UnicodeError`);
    - `None` when any of these fails:
      - the scheme is `https`;
      - there is no username or password;
      - the port is `None` or 443;
      - the hostname, IDNA-encoded, equals a host or ends in `"." + host`.
  - `dated_text_beside(table: Tag) -> str | None` (P40): the first text node in `table.parent`
    that matches `\b(?:19|20|21)\d{2}\b` after `collapse_ws`, cut to 80 characters. The text node
    must not be a comment, must be outside `table`, and must be outside `script`, `style`,
    `noscript` and `template`.
- Produces, in `base.py`:
  - `PageParse`, a mutable dataclass:
    - `outcome: PageOutcome`;
    - `units: list[InputUnit] = field(default_factory=list)`;
    - `claims: list[Claim] = field(default_factory=list)`;
    - `detail: str = ""`;
    - `year: int | None = None`;
    - `notes: list[Reason] = field(default_factory=list)`.
  - `parse_pages(source: str, raw: RawPages, parse_page: Callable[[RawPage], PageParse]) -> ParseResult`.
    Each adapter's `parse` passes a closure over its `window` and `registries`.
- Produces, elsewhere:
  - `ledger.py`: `HeaderTableRowsRule(headers: frozenset[str])`,
    `HeadingTablesRule(sections: tuple[tuple[str, str], ...])` and
    `LinkTableCellsRule(link_text: str)`. `CountRule` becomes the union of all five rule types.
  - `model.IgnoredReason` gains `"inactive_chamber"`, `"no_expected_date"` and `"footnote"`.
  - `tests.support.fixtures.fixture(source, name, day)`: these tests pass `day="2026-10-18"`.

- [ ] **Step 1: Copy the captures byte for byte.** Copy each
  `.scratch/plan2b/captures-2026-10-18/<source>.html` to its path above with `cp`, never through
  an editor. Then `sha256sum tests/fixtures/*/2026-10-18/*.html` must print the digests given in
  the notes below.
- [ ] **Step 2: Write the five notes.** This is the OSCE note; the others follow it with their own
  values.

```markdown
# OSCE/ODIHR elections table, captured 2026-10-18

- **URL:** https://odihr.osce.org/odihr/elections (final URL the same, no redirect)
- **Fetched:** 2026-10-18T11:18:37+00:00 through `Fetcher` + `trust_bundle` (certifi + REQUESTS_CA_BUNDLE)
- **HTTP status:** 200, `text/html; charset=utf-8`, 754466 bytes, 1 attempt
- **SHA-256 of `elections.html`:** 695c51726b7bf2980889c60377e1c07a9fa0949102ef508597913cb584580f86
- **Used by:** `tests/adapters/test_osce.py`, `tests/unit/test_ledger.py`
```

| Source | Fetched (UTC) | Content type | Bytes | SHA-256 |
|---|---|---|---|---|
| ipu | 2026-10-18T11:18:37 | `text/html; charset=UTF-8` | 393021 | 4ad0422007e9a3d9c8ddfecd3a480d94806c556eaea02cee2cc84441143c67f5 |
| aweb | 2026-10-18T11:18:38 | `text/html;charset=utf-8` | 48062 | 9800ebbed7cfcfb3f030b4c13a4d9aea41808f2c3c46cd215f1b994e821a7a4c |
| carter | 2026-10-18T11:18:40 | `text/html; charset=UTF-8` | 145668 | eefb55c99a49872a600c5324caa11d19530e5bbb8b707373f39987f52f9cb417 |
| eeas | 2026-10-18T11:18:40 | `text/html; charset=utf-8` | 184325 | 9a806595d79537ee73d425905b18f5151721e50bde021e6275c1cd9aca938eab |

  Every capture is HTTP 200 after 1 attempt, with no redirect. The URLs are the `requests()` URLs
  of Tasks 4–8.

- [ ] **Step 3: Write the failing tests.**
  - **`test_fixtures.py`:** the expected directory list becomes
    `["aweb/2026-10-18", "carter/2026-10-18", "eeas/2026-10-18", "electionguide/2026-10-16", "ipu/2026-10-16", "ipu/2026-10-18", "osce/2026-10-18", "wikipedia/2026-10-16"]`.
  - **`test_tables.py`:**
    - **`test_complete_html`:** the same cases as ElectionGuide's trailer rows.
    - **`test_own_rows`:**
      - a nested table's rows are not the outer table's;
      - rows without a `tbody` count;
      - `thead` rows are left out unless `head=True`.
    - **`test_row_cells`:**
      `<tr><th scope="row">Chile</th><td>May 2026</td><td><table><tr><td>x</td></tr></table></td></tr>`
      gives 3 cells (`th`, `td`, `td`); the nested table's `td` is not one of them.
    - **`test_header_tables_match_whole_header_texts`:**
      - `"date"` does not match `"start date"`;
      - two matching tables give two entries;
      - `<th>Expected date<br>of next elections</th>` matches `"expected date of next elections"`.
    - **`test_header_columns`** (headers `("date", "country", "election", "activity")`):
      - `Date | Country | Election | Activity` → `({"date": 0, "country": 1, "election": 2, "activity": 3}, ())`;
      - a reordered header gives the new indexes and `()`;
      - an extra distinct column (`Type`) shifts the indexes and gives `()`;
      - `Date | Country | Election | Activity | Date` → second element `("date",)`;
      - `Date | Country | Country | Election | Activity` → `("country",)`;
      - both repeated → `("date", "country")`;
      - two blank `th`s (as in ElectionGuide) → `()`, since blank is not a header that is read.
    - **`test_source_link`** (parametrized; base `https://www.eeas.europa.eu/eeas/x_en`, hosts
      `("eeas.europa.eu",)`):

      | href | result |
      |---|---|
      | `"/eom-colombia-2026_en"` | `"https://www.eeas.europa.eu/eom-colombia-2026_en"` |
      | `"//www.eeas.europa.eu/eom-peru-2026_en"` | `"https://www.eeas.europa.eu/eom-peru-2026_en"` |
      | `"https://eeas.europa.eu/a"` | the same URL |
      | `"https://WWW.EEAS.EUROPA.EU:443/a"` | the same URL |
      | `"//example.invalid/x"`, `"https://eeas.europa.eu.evil.example/a"`, `"https://evileeas.europa.eu/a"` | `None` |
      | `"http://www.eeas.europa.eu/a"`, `"javascript:void(0)"`, `"mailto:x@eeas.europa.eu"` | `None` |
      | `"https://user:pw@www.eeas.europa.eu/a"`, `"https://www.eeas.europa.eu:8443/a"` | `None` |
      | `"//["`, `"https://www.eeas.europa.eu:99999/a"` | `None`, no exception |
      | `None`, `""`, `"  "`, `["a"]` | `None` |

    - **`test_dated_text_beside`:**
      - `<div><p>12 Dec 2026 Croatia, Local</p><table>…</table></div>` →
        `"12 Dec 2026 Croatia, Local"`;
      - `<div><a>See All</a><table>…2026…</table></div>` → `None`, because the year is inside
        the table;
      - `<div><script>var y = 2026;</script><!-- 2026 --><table>…</table></div>` → `None`;
      - a table with no parent text → `None`.
  - **`test_sources_base.py`, `test_parse_pages`:**
    - the coverage keeps page order, with prefix `f"{source}:{key}/"` and `units_seen` for `ok`
      pages;
    - a failed download keeps its own outcome, and `parse_page` is never called;
    - a `RecursionError` gives `layout_not_recognised` with detail `"nested too deep"`;
    - a `layout_not_recognised` page loses its units, claims and notes, but keeps its detail, cut
      to `MAX_DETAIL`;
    - `year` passes through;
    - the `notes` of `ok` pages are collected;
    - `raw.unfinished` requests come last, as `unfinished`.
  - **`test_ledger.py`:**

```python
@pytest.mark.parametrize(("source", "name", "rule", "n", "first", "last"), [
    ("osce", "elections.html", HeaderTableRowsRule(frozenset({"date", "country", "election", "activity"})), 634, "r1", "r634"),
    ("ipu", "elections.html", HeaderTableRowsRule(frozenset({"country", "chamber", "principal mode of designation of members", "expected date of next elections"})), 281, "r1", "r281"),
    ("aweb", "calendar.html", HeaderTableRowsRule(frozenset({"country", "election", "date"})), 32, "r1", "r32"),
    ("carter", "observed.html", HeadingTablesRule((("elections monitored by the carter center", "monitored"), ("expert missions", "expert"))), 61, "monitored-r1", "expert-r18"),
    ("eeas", "missions.html", LinkTableCellsRule(r"EOM .+ \d{4}"), 34, "r1c1", "r17c2"),
])
def test_new_rules_count_the_fixtures(source, name, rule, n, first, last) -> None:
    found = discover(rule, fixture(source, name, "2026-10-18"))
    assert found is not None and (len(found), found[0], found[-1]) == (n, first, last)
```

    Also add `test_new_rules_on_synthetic_pages`, with values measured by `rules3.py`.

    On the Carter fixture:
    - the first `<table>…</table>` removed → 18 IDs, `"expert-r1"` to `"expert-r18"`, never a
      `monitored-` ID (B-T01);
    - the "Expert Missions" `h2` repeated right after itself → `None`;
    - `<table><tr><td>Note</td></tr></table>` inserted before the first table → `None`;
    - that table inserted before the first `h2` → 61 IDs, unchanged;
    - every `<tr><td …>` country cell turned into `<th scope="row" …>` → 61 IDs.

    On synthetic pages:
    - two header-matched tables → `None`;
    - no matching table → `None`;
    - one matching table that repeats a required header (`date` twice) → `None` (U01);
    - one matching table with an extra distinct column → its rows are counted;
    - a nested table's rows are not counted;
    - `thead` rows are not counted by `HeaderTableRowsRule`, but are counted by
      `HeadingTablesRule`;
    - none of the rule's headings found → `None`;
    - `LinkTableCellsRule` numbers its units `r<i>c<j>` over every `tr`, and counts every `td`
      **and** `th` of the target table only;
    - two link-matched tables → `None`.
- [ ] **Step 4: Run** the four test files. Expected: FAIL on import.
- [ ] **Step 5: Implement.**
  - **The counters:** stdlib `html.parser`. A `tr`, `td` or `th` belongs to the innermost open
    `table`.
  - **Text:** header and heading text is the data pieces inside the element, joined with a
    space, then put through `collapse_ws` and `casefold`. Link text is built the same way without
    `casefold`, and must `re.fullmatch` the rule's pattern.
  - **`HeaderTableRowsRule`:** a table matches when its `thead` `th` texts include every header.
    In the one matching table, each header must occur exactly once, else the rule returns `None`
    (U01). The counter checks this on its own parse, not through `tables.py`.
  - **`HeadingTablesRule`** (P40) works in regions:
    - each `</h2>` opens a region named by the heading's text, and each `<h2>` start tag closes
      the current region;
    - a region's tables are the `<table>` start tags seen while no table is open;
    - if a section's heading appears more than once, or its region holds more than one table, the
      rule returns `None`;
    - a section with no heading or no table has no units;
    - with no section left, the rule returns `None`.
  - **`LinkTableCellsRule`:** the target is the innermost open table when a matching `a` closes.
  - **`discover`:** returns `None` in the heading cases above, and when a header or link rule
    finds a number of tables other than 1.
  - **The other ledger functions:** `page_revid` and `_expected_prefix` do not change; the new
    rules have no revision.
  - **ElectionGuide:** switch to `complete_html`, `cell_text`, `own_rows` and `header_cells`, and
    delete its private copies.
    - U01: `_columns` also returns `None`, so the page is `layout_not_recognised` as today, when
      a header it reads (`country`, `election for`, `start date`, `end date`, `status`) appears
      more than once. Its counter finds the table by id, so it needs no change.
    - Add `test_a_repeated_header_is_not_a_layout` to `test_electionguide.py`: `start date` twice
      → `layout_not_recognised` with no units; `status` twice → the same.
    - The rest of its test file must pass unchanged. No fixture view repeats a header it reads
      (measured).
- [ ] **Step 6: Run** the four files and `tests/adapters/test_electionguide.py`. Expected: PASS.
- [ ] **Step 7: Gates, mutation table, commit:**
  `feat(sources): table helpers, source links, page driver, fixtures and three discovery rules`.

---

### Task 3: Labels that name a subdivision (P38), shared by ElectionGuide, OSCE and A-WEB

**Files:**
- Modify:
  - `elections_calendar/places.py` (`named_subdivisions`);
  - `elections_calendar/sources/base.py` (`LabelScope`, `label_scope`);
  - `elections_calendar/sources/electionguide.py`.
- Test: `tests/unit/test_places.py`, `tests/unit/test_sources_base.py`, `tests/adapters/test_electionguide.py`

**Interfaces:**
- Consumes:
  - `PlaceRegistry.resolve` and `SubdivisionIndex.find(country_code, name)`, with Task 1's fixed
    `data/subdivisions.yaml`;
  - `offices.classify(label, place_id, jurisdiction_kind, institutions)`,
    `claim_level(default, office)`, `Office.level_hint` and `Office.recognised`.
- Produces:
  - `places.named_subdivisions(text: str, place: Place, places: PlaceRegistry, subdivisions: SubdivisionIndex) -> tuple[str, ...]`;
  - `base.LabelScope`, frozen: `office: Office`, `level: Level`, `jurisdiction: str | None`,
    `jurisdiction_kind: JurisdictionKind`, `unresolved: bool`;
  - `base.label_scope(label: str, place: Place, registries: Registries, default: Level = "national") -> LabelScope`.

**Rules:**
- **`named_subdivisions`:**
  1. Words are `re.findall(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*", text)`.
  2. Pass 1 takes every run of 5 down to 1 consecutive words that `places.resolve`s to
     `place.place_id`, so the place's own name ("Mexico", "Trinidad and Tobago") never counts.
  3. Pass 2, longest runs first, takes the runs of 5 down to 1 untaken words that
     `subdivisions.find(place.country_code, run)` resolves.
  4. It returns the matched runs in text order, one per subdivision code.
- **`label_scope`:**
  - `subs = named_subdivisions(...)`;
  - `kind = "subdivision" if subs else "nationwide"`;
  - `office = classify(label, place.place_id, kind, registries.institutions)`;
  - `level = claim_level("unknown" if subs else default, office)`;
  - `jurisdiction = ", ".join(subs) or None`;
  - `unresolved = bool(subs) and office.recognised and office.level_hint is None`.
- **ElectionGuide** builds its claim's office, `level`, `jurisdiction` and `jurisdiction_kind`
  from `label_scope`. A unit with `unresolved` and no other reason is partial `level_unresolved`;
  that reason ranks after `status_unrecognised`.

- [ ] **Step 1: Write the failing tests.**
  - **`test_named_subdivisions`** (parametrized: country, text → result). Every row was measured
    with Task 1's data:

    | Country | Text | Result |
    |---|---|---|
    | Pakistan | `"2026 Gilgit Baltistan Assembly Election"` | `("Gilgit Baltistan",)` |
    | Bosnia and Herzegovina | `"Republika Srpska Early Presidential election"` | `("Republika Srpska",)` |
    | United Kingdom | `"Scotland and Wales local elections"` | `("Scotland", "Wales")` |
    | United Kingdom | `"Parliamentary Elections (Wales/United Kingdom)"` | `("Wales",)` |
    | Mexico | `"Mexico General Election"` | `()` |
    | Trinidad and Tobago | `"Trinidad and Tobago House of Representatives"` | `()` |
    | United Kingdom | `"Scottish Parliament election"` | `()` |
    | Bulgaria | `"Presidential Election"` | `()` |

  - **`test_label_scope_precedence`** (parametrized, measured by `check_precedence.py`):

    | Country | Label | Office class | Institution | Level | `unresolved` |
    |---|---|---|---|---|---|
    | Bulgaria | Presidential Election | `head_of_state` | `iso:BG/president` | `national` | `False` |
    | United States | United States Senate election in Ohio | `upper_house` | `iso:US/senate` | `national` | `False` |
    | United States | Ohio State Senate election | `upper_house` | `None` | `subnational` | `False` |
    | United Kingdom | Referendum in Scotland | `referendum` | `None` | `subnational` | `False` |
    | Moldova | Election of Governor of Gagauzia | `governor` | `None` | `subnational` | `False` |
    | Bosnia and Herzegovina | Republika Srpska Early Presidential election | `head_of_state` | `None` | `unknown` | `True` |
    | Pakistan | 2026 Gilgit Baltistan Assembly Election | `legislature` | `None` | `unknown` | `True` |
    | Mexico | Mexico General Election | `general` | `None` | `national` | `False` |
    | Trinidad and Tobago | Trinidad and Tobago House of Representatives | `lower_house` | `iso:TT/house-of-representatives` | `national` | `False` |

    Gilgit-Baltistan's scope also has `jurisdiction_kind="subdivision"`,
    `jurisdiction="Gilgit Baltistan"` and `office.aggregate is False`.
  - **`test_a_label_naming_a_subdivision_keeps_its_jurisdiction`** (`test_electionguide.py`):
    - `one_row(row(country="Bosnia and Herzegovina", label="Republika Srpska Early Presidential election"))`
      gives a partial `level_unresolved` unit. Its claim has `jurisdiction="Republika Srpska"`,
      `jurisdiction_kind="subdivision"`, `level="unknown"` and `institution=None`.
    - `row(country="Moldova", label="Election of Governor of Gagauzia")` is parsed, with level
      `subnational`.
  - **The existing `test_electionguide.py` stays unchanged:** none of the three fixture views
    names a subdivision (measured).
- [ ] **Step 2: Run the tests.**

  ```bash
  .venv/Scripts/python.exe -m pytest tests/unit/test_places.py tests/unit/test_sources_base.py tests/adapters/test_electionguide.py -q
  ```

  Expected: FAIL on import.
- [ ] **Step 3: Implement** the three functions, and switch ElectionGuide to `label_scope`.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:** `feat(sources): keep the subdivision a label names (P38)`.

  Mutations, one each:
  - drop pass 1;
  - drop the withheld default;
  - drop the `level_hint` condition;
  - drop ElectionGuide's `level_unresolved`.

---

### Task 4: OSCE adapter

**Files:**
- Create: `elections_calendar/sources/osce.py`, `tests/adapters/test_osce.py`
- Modify:
  - `ledger.COUNT_RULES` (add `"osce"`);
  - `runner.DEFAULT_ADAPTERS` (after `electionguide`);
  - `importlinter.ini` (the adapters contract);
  - `tests/unit/test_runner.py:392`.

**Interfaces:**
- Consumes:
  - Task 2's `tables` helpers and `parse_pages`;
  - Task 3's `label_scope`;
  - `parse_date_text`, `plausible`, `relevance`, `is_executive_title`, `Registries`.
- Produces:
  - `class Osce` with `source = "osce"`;
  - `URL = "https://odihr.osce.org/odihr/elections"`;
  - `HOSTS = ("odihr.osce.org", "osce.org")`;
  - `HEADERS = ("date", "country", "election", "activity")`;
  - `requests(window)` returns `(PageRequest("elections", URL),)`.

**Rules:**
- **Layout:**
  - There must be exactly one `header_tables(soup, HEADERS)` table, else `layout_not_recognised`
    with detail `f"{n} tables with headers {', '.join(HEADERS)}"` (for example
    `"0 tables with headers date, country, election, activity"`). Tasks 5 and 6 use the same
    format with their own `HEADERS`.
  - The page must pass `complete_html`, else detail `"page does not end with </html>"`.
  - The columns come from `header_columns(table, HEADERS)`. A repeated header fails the page
    with detail `"repeated header: <h>"` (U01), before any row is read. Tasks 5 and 6 do the
    same.
  - If `dated_text_beside(table)` finds text, add the note
    `Reason("coverage_gap", f"dated text beside the table: {text}")`.
- **Units:** `own_rows(table)`; the cells are `row_cells(tr)`.
- **Unparsed rows**, checked in this order:
  1. fewer cells than the largest mapped column + 1 → `too_few_cells`;
  2. the country cell resolves to no place → `place_missing`;
  3. no `div` in the date cell → `date_unparsed`, with the cell text as `leftover`;
  4. `parse_date_text(div text)` is `ok` with no spans → `date_missing`;
  5. the parse is not `ok`, or has more than one span → `date_unparsed`, with the parse's
     leftover;
  6. not `plausible(span, window.today)` → `implausible_date`;
  7. `is_executive_title(label)` → `office_not_modelled`, with the label as `leftover`.
- **Badges** are the date cell's `span`s (P30).
- **Statuses (P30, U03):**
  - Map each badge with `STATUS = {"postponed": "postponed", "cancelled": "cancelled", "canceled": "cancelled"}`
    on its casefolded text. "upcoming" and "past" map to nothing; any other badge is
    unrecognised.
  - The row's statuses are the distinct mapped badge statuses, plus `parse.status_claim` when it
    is not `None`.
  - Two or more → conflict: `status_claim=None`, and no other field can supply one. One →
    `status_claim` is that status. None → `None`.
  - When a conflict or an unrecognised badge exists, `leftover` holds every badge text other
    than Upcoming/Past, in page order, joined by a space. This holds whichever reason the unit
    ends with, so a `filter_date_mismatch` unit keeps the conflicting badges.
- **Partial reasons** (the first that applies wins):
  1. `filter_date_mismatch`: a single-day span whose `tr["data-filter-date"]` is missing or
     differs from `span.start.isoformat()`;
  2. `status_conflict`;
  3. `status_unrecognised`;
  4. `place_unregistered`;
  5. `office_unrecognised`;
  6. `level_unresolved`;
  7. `link_rejected`.
- **The claim:**
  - **Office and scope:** the office, `level`, `jurisdiction` and `jurisdiction_kind` come from
    `scope = label_scope(label, place, registries)`.
  - **Text fields:** `office_label` is the label; `place_raw` is the country cell text. Tasks 5
    and 6 fill these two fields the same way.
  - **`link`:** the first href that `source_link(URL, href, HOSTS)` accepts, from the activity
    cell's `a`, then the country cell's `a`; else `URL`.
  - **Date fields:** `date_meaning="voting_period"`, `date_status=parse.date_status`,
    `date_text` = the `div` text.
  - **Status:** `status_claim` from the status rule above;
    `previous_date_text=parse.previous_text`.
  - **Other fields:** `source_event_id=None`, `evidence_kind="calendar"`,
    `indirect="(indirect)" in label.casefold()`.
- **Relevance** comes from the `div` text (P24).
- **Unit text** is the non-empty cell texts joined by `" | "`.

- [ ] **Step 1: Write the failing tests.** Module constants (Tasks 5–8 use the same ones with
  their own adapter and fixture):
  - `WINDOW = window_for(datetime(2026, 10, 18, tzinfo=UTC))`, `REGISTRIES = Registries.load()`;
  - `ALL` = the fixture as `RawPages`, built as in `test_electionguide.py` from
    `fixture("osce", "elections.html", "2026-10-18")`;
  - `RES = Osce().parse(ALL, WINDOW, REGISTRIES)`, with `UNITS` and `CLAIMS` keyed by ID;
  - `parse(raw)` asserts `check(raw, res).ok`.

  Synthetic builders:
  - `osce_page(rows, headers=("Date", "Country", "Election", "Activity"), beside="")`. The table
    sits in `<div class="table-wrapper">{beside}<table>…</table></div>`.
  - `osce_row(date="25 Oct 2026", badges=("Upcoming",), country="Bulgaria", label="Presidential Election", activity="-", filter_date="2026-10-25", country_href="/odihr/elections/bulgaria", activity_href=None)`,
    shaped like the fixture's rows:
    `<tr class="search-target" data-filter-date=…><td><div>…</div><span class="badge">…</span></td>…`,
    with one `span` per badge and no `data-filter-date` attribute when `filter_date` is `None`.

```python
def test_fixture_ledger_balances() -> None:
    res = parse(ALL); report = check(ALL, res)
    assert report.ok and res.reasons == ()
    assert report.outcomes == {"parsed": 173, "partial": 7, "unparsed": 454, "ignored": 0}
    assert [(c.key, c.outcome, c.units_seen, c.year) for c in res.coverage] == [("elections", "ok", 634, None)]
    assert len(res.claims) == 180

def test_fixture_values() -> None:
    assert Counter(c.span.precision for c in RES.claims) == {"day": 165, "month": 7, "year": 8}
    assert Counter(c.level for c in RES.claims) == {"national": 144, "subnational": 29, "unknown": 7}
    assert Counter(c.office_class for c in RES.claims) == {"legislature": 91, "head_of_state": 43, "local_council": 29, "general": 12, "referendum": 5}
    assert Counter((u.outcome, u.reason) for u in RES.units if u.reason) == {
        ("unparsed", "implausible_date"): 454, ("partial", "office_unrecognised"): 6, ("partial", "level_unresolved"): 1}
    assert {u.relevance for u in RES.units if u.outcome != "parsed"} == {"before_window"}
    assert {c.status_claim for c in RES.claims} == {None} and not any(c.indirect for c in RES.claims)
    assert {urlsplit(c.link).hostname for c in RES.claims} == {"odihr.osce.org"}

def test_in_window_claims() -> None:
    assert sorted((c.span.start.isoformat(), c.place_id, c.office_class, c.institution)
                  for c in RES.claims if WINDOW.overlaps(c.span)) == [
        ("2026-09-13", "iso:SE", "legislature", "iso:SE/parliament"),
        ("2026-09-20", "iso:RU", "legislature", None),
        ("2026-10-03", "iso:LV", "legislature", "iso:LV/parliament"),
        ("2026-10-04", "iso:BA", "general", None),
        ("2026-10-25", "iso:BG", "head_of_state", "iso:BG/president"),
        ("2026-10-25", "iso:RS", "legislature", "iso:RS/national-assembly"),
        ("2026-11-03", "iso:US", "legislature", None),
        ("2026-11-15", "iso:SI", "local_council", None),
        ("2026-11-29", "iso:ES", "legislature", None),
        ("2027-01-27", "iso:KG", "head_of_state", "iso:KG/president"),
    ]
```

  - **`test_one_claim_field_by_field`:**
    - **`osce:elections/r1#0`:**
      - `place_id="iso:BG"`, `level="national"`, `jurisdiction_kind="nationwide"`;
      - `office_class="head_of_state"`, `institution="iso:BG/president"`,
        `kind="candidate_election"`;
      - `span=DateSpan.day(date(2026, 10, 25))`, `date_meaning="voting_period"`,
        `date_status="unknown"`, `date_text="25 Oct 2026"`;
      - `link="https://odihr.osce.org/odihr/elections/bulgaria"`, `status_claim=None`.

      Its unit text is `"25 Oct 2026 Upcoming | Bulgaria | Presidential Election | -"`, with
      relevance `in_or_after_window`.
    - **`osce:elections/r52#0`** ("Republika Srpska Early Presidential election", 23 Nov 2025):
      `office_class="head_of_state"`, `institution=None`, `level="unknown"`,
      `jurisdiction="Republika Srpska"` and `jurisdiction_kind="subdivision"`. Its unit is partial
      `level_unresolved`.
  - **`test_badges`** (parametrized; each case is a synthetic one-row page; the date is
    `"25 Oct 2026"` and `data-filter-date` matches it unless the case says otherwise):

    | Badges (one `span` each) | Case | Unit | `status_claim` | Leftover |
    |---|---|---|---|---|
    | Upcoming; Past | — | parsed | `None` | `""` |
    | Postponed | — | parsed | `postponed` | `""` |
    | Cancelled; Canceled (each alone) | — | parsed | `cancelled` | `""` |
    | Cancelled, Canceled | — | parsed | `cancelled` | `""` |
    | Upcoming, Postponed | — | parsed | `postponed` | `""` |
    | Postponed, Cancelled | — | partial `status_conflict` | `None` | `"Postponed Cancelled"` |
    | Cancelled, Postponed | — | partial `status_conflict` | `None` | `"Cancelled Postponed"` |
    | Postponed, Cancelled | date `"Held 25 Oct 2026"` | partial `status_conflict` | `None` | `"Postponed Cancelled"` |
    | Postponed | date `"Held 25 Oct 2026"` | partial `status_conflict` | `None` | `"Postponed"` |
    | Upcoming | date `"Held 25 Oct 2026"` | parsed | `held` | `""` |
    | Postponed, Cancelled | `filter_date="2026-10-24"` | partial `filter_date_mismatch` | `None` | `"Postponed Cancelled"` |
    | Rescheduled | — | partial `status_unrecognised`, claim kept | `None` | `"Rescheduled"` |

    `parse_date_text("Held 25 Oct 2026")` is `ok` with one day and `status_claim="held"`
    (measured).

  - **`test_date_cell_rules`:**
    - no `div` → unparsed `date_unparsed`;
    - `"-"` → `date_missing`;
    - `"Apr 2027"` → a month claim, which `data-filter-date` cannot change;
    - `"2027"` → a year claim;
    - `"25 Oct 2032"` → `implausible_date`, relevance `in_or_after_window`;
    - `"25 Oct 9999"` → `date_unparsed`, no exception;
    - an empty `div` → relevance `unknown`;
    - `data-filter-date="2026-10-24"` on a 25 Oct row → partial `filter_date_mismatch`;
    - a missing `data-filter-date` → partial `filter_date_mismatch` as well.
  - **`test_columns_are_found_by_header_not_position`:**
    - headers `("Country", "Type", "Date", "Activity", "Election")`, with the cells in that
      order, give the same claim as the default row (reordered, plus a distinct extra column);
    - a `<th scope="row">` date cell gives the same claim;
    - a page without "Activity" is `layout_not_recognised`;
    - **U01** (each is `layout_not_recognised` with no units, no claims and no notes):
      - `("Date", "Country", "Election", "Activity", "Date")` with dates `25 Oct 2026` and
        `25 Oct 2026` (agreeing) → `"repeated header: date"`;
      - the same headers with `25 Oct 2026` and `8 Nov 2026` (disagreeing) → the same detail;
      - `("Date", "Country", "Country", "Election", "Activity")` with `Chile`/`Peru`, and with
        `Chile`/`Chile` → `"repeated header: country"`.
  - **`test_off_host_links_fall_back`:**
    - `activity_href="https://example.invalid/r"` with the default country href → the country
      link, parsed;
    - both hrefs off host (`"javascript:void(0)"`, `"//["`) → `link == URL`, partial
      `link_rejected`, no exception.
  - **`test_rows_that_do_not_fit`:**
    - 3 cells → `too_few_cells`;
    - an empty country → `place_missing`;
    - "Narnia" → partial `place_unregistered`;
    - "Lieutenant Governor election" → `office_not_modelled`;
    - "Presidential (Indirect) Election" → `indirect=True`.
  - **`test_dated_text_beside_the_table_is_a_coverage_gap`:** with
    `beside="<p>12 Dec 2026 Croatia, Local Elections</p>"`, the page is `ok` with its row, and
    `res.notes == (Reason("coverage_gap", "dated text beside the table: 12 Dec 2026 Croatia, Local Elections"),)`.
  - **`test_broken_pages_get_an_outcome_never_units`** (parametrized: change → detail):
    - no table → `"0 tables with headers date, country, election, activity"`;
    - "Activity" renamed → the same detail;
    - the table duplicated → `"2 tables …"`;
    - the body cut in half → `"page does not end with </html>"`;
    - `b""` and garbage → the `</html>` detail;
    - the `tbody` emptied → `"the table has no rows"`.
  - **`test_download_failures_keep_their_own_outcome`:** a 302 gives `http_error`;
    `challenge_page` stays `challenge_page`; neither has units.
  - **`test_requests_and_fetch`:** there is one request, and `fetch` gets it through the stub.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/adapters/test_osce.py -q`.
  Expected: FAIL on import.
- [ ] **Step 3: Implement `Osce`** with the rules above. Register `"osce"`:
  - `COUNT_RULES["osce"] = HeaderTableRowsRule(frozenset(HEADERS))`;
  - `AdapterSpec("osce", "elections_calendar.sources.osce:Osce")`, after `electionguide`;
  - the importlinter adapters list;
  - `test_runner.py:392` expects `["electionguide", "osce", "wikipedia"]`.
- [ ] **Step 4: Run** the file and `tests/unit/test_runner.py`. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:** `feat(sources): OSCE/ODIHR elections adapter`.

---

### Task 5: IPU adapter

**Files:**
- Create: `elections_calendar/sources/ipu.py`, `tests/adapters/test_ipu.py`
- Modify:
  - `COUNT_RULES` (add `"ipu"`);
  - `DEFAULT_ADAPTERS` (after `wikipedia`);
  - `importlinter.ini`;
  - `test_runner.py:392`.

**Interfaces:**
- Consumes:
  - what Task 4 consumes, except `label_scope` (IPU lists national chambers);
  - `classify`, `claim_level`, `DateSpan.month` and `model.month_end(year, month)`.
- Produces:
  - `class Ipu` with `source = "ipu"`;
  - `URL = "https://data.ipu.org/elections/"`;
  - `HOSTS = ("data.ipu.org",)`;
  - `HEADERS = ("country", "chamber", "principal mode of designation of members", "expected date of next elections")`;
  - one request, `"elections"`.

**Rules:**
- **Layout:** as in Task 4: one header table, `complete_html`, a table with rows, and the
  dated-text note.
- **Per row**, checked in this order:
  1. too few cells → unparsed `too_few_cells`;
  2. the chamber text ends with `(Suspended)` or `(Dissolved)` (case-insensitive) → ignored
     `inactive_chamber`;
  3. designation "Appointed" → ignored `appointed_chamber`;
  4. a designation other than "Directly elected" or "Indirectly elected" → unparsed
     `designation_unrecognised`, with the designation as `leftover`;
  5. no place → unparsed `place_missing`;
  6. the expected date parses `ok` with no spans → ignored `no_expected_date`;
  7. anything other than exactly one single-day span → unparsed `date_unparsed`, with the cell
     text as `leftover`;
  8. not `plausible(span, today, years=10)` → unparsed `implausible_date`;
  9. `is_executive_title(chamber)` → unparsed `office_not_modelled`.
- **The span:** a day equal to `month_end(year, month)` becomes `DateSpan.month(year, month)`
  (P25).
- **Partial reasons**, in this order: `place_unregistered`, `office_unrecognised`,
  `link_rejected`.
- **The claim:**
  - **Office:** `classify(chamber, place.place_id, "nationwide", registries.institutions)`, with
    `level=claim_level("national", office)` and `office_label` = the chamber text.
  - **`link`:** `source_link(URL, chamber a href, HOSTS)`, else `URL`.
  - **`source_event_id`:** `f"ipu:{code}"`, taken from
    `/parliament/[A-Z]{2}/([A-Z]{2}-[A-Z]{2}\d{2})/` in the **accepted** link, else `None`.
  - **Date fields:** `date_meaning="expected_window"`, `date_status="tentative"`, `date_text` =
    the cell text.
  - **Other fields:** `evidence_kind="expected_renewal"`; `indirect` is true when the designation
    is "Indirectly elected".
- **Relevance** comes from the expected-date cell.

- [ ] **Step 1: Write the failing tests.**

```python
def test_fixture_ledger_balances() -> None:
    res = parse(ALL); report = check(ALL, res)
    assert report.ok and res.reasons == ()
    assert report.outcomes == {"parsed": 234, "partial": 0, "unparsed": 4, "ignored": 43}
    assert report.ignored_reasons == {"inactive_chamber": 10, "appointed_chamber": 28, "no_expected_date": 5}
    assert len(res.claims) == 234

def test_fixture_values() -> None:
    assert Counter(c.span.precision for c in RES.claims) == {"month": 197, "day": 37}
    assert Counter(c.office_class for c in RES.claims) == {"legislature": 96, "lower_house": 80, "upper_house": 58}
    assert {c.level for c in RES.claims} == {"national"} and sum(c.indirect for c in RES.claims) == 32
    assert all(c.institution and c.source_event_id for c in RES.claims)
    assert {urlsplit(c.link).hostname for c in RES.claims} == {"data.ipu.org"}
    assert {(c.date_meaning, c.date_status, c.evidence_kind) for c in RES.claims} == {("expected_window", "tentative", "expected_renewal")}
    assert [(u.unit_id, u.leftover) for u in RES.units if u.reason == "designation_unrecognised"] == [
        ("ipu:elections/r32", "Other"), ("ipu:elections/r44", "Other"), ("ipu:elections/r143", "Other"), ("ipu:elections/r264", "Other")]
    assert {u.relevance for u in RES.units if u.outcome == "unparsed"} == {"in_or_after_window"}

def test_in_window_claims() -> None:
    assert sorted((c.place_id, c.office_class, c.span.precision, c.span.start.isoformat())
                  for c in RES.claims if WINDOW.overlaps(c.span)) == [
        ("iso:CM", "lower_house", "month", "2027-01-01"), ("iso:ES", "lower_house", "day", "2026-11-29"),
        ("iso:ES", "upper_house", "day", "2026-11-29"), ("iso:FJ", "legislature", "month", "2026-12-01"),
        ("iso:GD", "lower_house", "day", "2026-11-05"), ("iso:HT", "lower_house", "month", "2026-12-01"),
        ("iso:HT", "upper_house", "month", "2026-12-01"), ("iso:IL", "legislature", "day", "2026-10-27"),
        ("iso:LY", "legislature", "month", "2026-12-01"), ("iso:MG", "upper_house", "month", "2026-12-01"),
        ("iso:NZ", "legislature", "day", "2026-11-07"), ("iso:RS", "legislature", "day", "2026-10-25"),
        ("iso:SO", "lower_house", "month", "2026-12-01"), ("iso:SO", "upper_house", "month", "2026-12-01"),
        ("iso:US", "lower_house", "day", "2026-11-03"), ("iso:US", "upper_house", "day", "2026-11-03"),
    ]
```

  - **`test_claims_field_by_field`:**
    - **`ipu:elections/r180#0`** (New Zealand):
      - `institution="iso:NZ/house-of-representatives"`, `office_class="legislature"`;
      - `span=DateSpan.day(date(2026, 11, 7))`, `date_text="07 Nov 2026"`;
      - `source_event_id="ipu:NZ-LC01"`,
        `link="https://data.ipu.org/parliament/NZ/NZ-LC01/elections/elections"`.
    - **`ipu:elections/r50#0`** (Cameroon): `span=DateSpan.month(2027, 1)`,
      `date_text="31 Jan 2027"`, `source_event_id="ipu:CM-LC01"`.
  - **`test_month_end_dates_are_months`** (synthetic, parametrized). Every case keeps `date_text`
    as written and `date_status="tentative"`:

    | Expected date | Span |
    |---|---|
    | `"31 Dec 2026"` | month 2026-12 |
    | `"30 Nov 2026"` | month 2026-11 |
    | `"28 Feb 2027"` | month 2027-02 |
    | `"29 Feb 2028"` | month 2028-02 |
    | `"28 Feb 2028"` | day |
    | `"29 Nov 2026"` | day |
    | `"01 Jan 2027"` | day |

  - **`test_far_renewals`:**
    - the fixture's Benin row `r31` gives a month claim for January 2033;
    - a synthetic "31 Jan 2037" → unparsed `implausible_date`;
    - "31 Jan 2016" → a claim (10 years back is still plausible).
  - **`test_designations`:**
    - "Indirectly elected" → `indirect=True`;
    - "Appointed" → ignored `appointed_chamber`;
    - "Other" and "Mixed" → unparsed `designation_unrecognised`;
    - "(Suspended)" on an appointed row → `inactive_chamber`, which wins;
    - "Senate (Dissolved)" → `inactive_chamber`.
  - **`test_expected_date_cells`:**
    - `"-"` → ignored `no_expected_date`;
    - `"Nov 2026"` and `"01 Nov 2026 - 02 Nov 2026"` → unparsed `date_unparsed`;
    - a row without a chamber link → a claim with `source_event_id=None` and `link=URL`.
  - **`test_off_host_links_fall_back`:** the chamber href
    `"https://evil.example/parliament/NZ/NZ-LC01/x"` gives `link == URL`,
    `source_event_id is None` and partial `link_rejected`.
  - **`test_dated_text_beside_the_table_is_a_coverage_gap`** and
    **`test_broken_pages_get_an_outcome_never_units`:** as in Task 4, with the IPU header detail
    `"0 tables with headers country, chamber, principal mode of designation of members, expected date of next elections"`.
    Add one U01 case: a second `Chamber` header → `"repeated header: chamber"`, with no units.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/adapters/test_ipu.py -q`.
  Expected: FAIL on import.
- [ ] **Step 3: Implement `Ipu`.** Register it:
  - `COUNT_RULES["ipu"]`;
  - `AdapterSpec("ipu", "elections_calendar.sources.ipu:Ipu")`, after `wikipedia`;
  - importlinter;
  - the runner list becomes `["electionguide", "osce", "wikipedia", "ipu"]`.
- [ ] **Step 4: Run** the file and `tests/unit/test_runner.py`. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:** `feat(sources): IPU Parline expected-renewals adapter`.

---

### Task 6: A-WEB adapter

**Files:**
- Create: `elections_calendar/sources/aweb.py`, `tests/adapters/test_aweb.py`
- Modify:
  - `COUNT_RULES` (add `"aweb"`);
  - `DEFAULT_ADAPTERS` (after `wikipedia`, before `ipu`);
  - `importlinter.ini`;
  - `test_runner.py:392`.

**Interfaces:**
- Consumes: as in Task 4.
- Produces:
  - `class Aweb` with `source = "aweb"`;
  - `URL = "https://www.aweb.org/eng/bbs/B0000007/list.do?menuNo=300052&option=all"`;
  - `HEADERS = ("country", "election", "date")`;
  - one request, `"calendar"`.

**Rules:**
- **Layout:** as in Task 4, with the dated-text note.
- **Unparsed rows**, checked in this order:
  1. `too_few_cells`;
  2. `place_missing`;
  3. `date_missing`;
  4. `date_unparsed`: the parse is not `ok`, or has more than one span;
  5. `implausible_date`;
  6. `office_not_modelled`: an executive title, or a label matching `\bprimar(?:y|ies)\b`
     (case-insensitive).
- **Partial reasons**, in this order: `place_unregistered`, `office_unrecognised`,
  `level_unresolved`.
- **The claim:**
  - **Office and scope:** the office, `level`, `jurisdiction` and `jurisdiction_kind` come from
    `label_scope(label, place, registries)`. `office_label` is the election cell text.
  - **`link`:** always `URL`, with no `source_link` call, because A-WEB's page links point to
    news and EMB sites.
  - **Date fields:** `date_meaning="voting_period"` for one day, otherwise `"unknown"`;
    `date_status="unknown"`.
  - **Status:** `status_claim=parse.status_claim`, `previous_date_text=parse.previous_text`.
  - **Other fields:** `evidence_kind="calendar"`, `indirect=False`.
- **Coverage `year` (P31):** when all of the page's claims share one `span.year`, that year;
  otherwise `None`.
- **Relevance** comes from the date cell.

- [ ] **Step 1: Write the failing tests.**

```python
def test_fixture_ledger_balances() -> None:
    res = parse(ALL); report = check(ALL, res)
    assert report.ok and res.reasons == ()
    assert report.outcomes == {"parsed": 29, "partial": 2, "unparsed": 1, "ignored": 0}
    assert [(c.key, c.outcome, c.units_seen, c.year) for c in res.coverage] == [("calendar", "ok", 32, 2026)]
    assert len(res.claims) == 31

def test_fixture_values() -> None:
    assert Counter(c.level for c in RES.claims) == {"national": 24, "subnational": 5, "unknown": 2}
    assert Counter(c.office_class for c in RES.claims) == {"general": 13, "legislature": 7, "head_of_state": 6, "local_council": 5}
    assert {c.link for c in RES.claims} == {URL}
    assert Counter(c.date_meaning for c in RES.claims) == {"voting_period": 30, "unknown": 1}
    ghana = UNITS["aweb:calendar/r6"]
    assert (ghana.outcome, ghana.reason, ghana.leftover, ghana.relevance) == (
        "unparsed", "office_not_modelled", "2026 The Presidential Primaries", "unknown")
    assert [(u.unit_id, u.reason) for u in RES.units if u.outcome == "partial"] == [
        ("aweb:calendar/r5", "level_unresolved"), ("aweb:calendar/r29", "office_unrecognised")]

def test_in_window_claims() -> None:
    assert sorted((c.span.start.isoformat(), c.place_id, c.office_class, c.level)
                  for c in RES.claims if WINDOW.overlaps(c.span)) == [
        ("2026-09-20", "iso:RU", "legislature", "national"), ("2026-10-03", "iso:LV", "legislature", "national"),
        ("2026-10-04", "iso:BA", "general", "national"), ("2026-10-04", "iso:BR", "general", "national"),
        ("2026-10-25", "iso:BR", "general", "national"), ("2026-11-02", "iso:PH", "general", "unknown"),
        ("2026-11-02", "iso:ZA", "local_council", "subnational"), ("2026-11-28", "iso:TW", "local_council", "subnational"),
        ("2026-12-05", "iso:GM", "head_of_state", "national"), ("2026-12-22", "iso:SS", "general", "national"),
    ]
```

  - **`test_claims_field_by_field`:**
    - **`aweb:calendar/r31#0`** (Gambia): `institution="iso:GM/president"`,
      `span=DateSpan.day(date(2026, 12, 5))`, `date_meaning="voting_period"`,
      `date_status="unknown"`, `date_text="05 Dec 2026"`.
    - **`aweb:calendar/r28#0`** (South Africa):
      `span=DateSpan.days(date(2026, 11, 2), date(2027, 1, 31))`, `date_meaning="unknown"`,
      `date_text="02 Nov 2026 -31 Jan 2027"`.
    - **`aweb:calendar/r5#0`** (Pakistan, "2026 Gilgit Baltistan Assembly Election", 24 Jan 2026):
      - `office_class="legislature"`, `institution=None`, `aggregate=False`,
        `kind="candidate_election"`;
      - `level="unknown"`, `jurisdiction="Gilgit Baltistan"`, `jurisdiction_kind="subdivision"`.

      Its unit is partial `level_unresolved`, with relevance `unknown`.
  - **`test_coverage_year_is_the_lists_year`:**
    - a synthetic list with dates in 2027 only → `year == 2027`;
    - one 2026 date and one 2027 date → `None`;
    - every row unparsed → `None`.
  - **`test_external_links_are_never_claim_links`:** a row with
    `<a href="https://reuters.com/x">` gives `link == URL`.
  - **`test_rows_that_do_not_fit`:** the Task 4 cases, plus "2026 Democratic primary" →
    `office_not_modelled`.
  - **`test_dated_text_beside_the_table_is_a_coverage_gap`** and
    **`test_broken_pages_get_an_outcome_never_units`:** as in Task 4, with the A-WEB header
    detail. Add one U01 case: a second `Date` header → `"repeated header: date"`, with no units.
    The fixture's own neighbours ("4 depth tab", "Upcoming Election", "See All") hold no year, so
    they give no note.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/adapters/test_aweb.py -q`.
  Expected: FAIL on import.
- [ ] **Step 3: Implement `Aweb`.** Register it; the runner list becomes
  `["electionguide", "osce", "wikipedia", "aweb", "ipu"]`.
- [ ] **Step 4: Run** the file and `tests/unit/test_runner.py`. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:** `feat(sources): A-WEB world election calendar adapter`.

---

### Task 7: Carter Center adapter

**Files:**
- Create: `elections_calendar/sources/carter.py`, `tests/adapters/test_carter.py`
- Modify:
  - `COUNT_RULES` (add `"carter"`);
  - `DEFAULT_ADAPTERS` (after `ipu`);
  - `importlinter.ini`;
  - `test_runner.py:392`.

**Interfaces:**
- Consumes: as in Task 4, without `classify` or `label_scope`, since observations name no office.
- Produces:
  - `class Carter` with `source = "carter"`;
  - `URL = "https://www.cartercenter.org/programs/democracy/elections-observed/"`;
  - `HOSTS = ("cartercenter.org",)`;
  - `SECTIONS = (("elections monitored by the carter center", "monitored", "Carter Center election observation"), ("expert missions", "expert", "Carter Center expert mission"))`;
  - `FOOTNOTE = "*these missions were targeted or focused observations and did not result in statements on the overall administration of the electoral process."`
    (the page's footnote, casefolded, measured);
  - one request, `"observed"`.

**Rules:**
- **Sections (P40):**
  - A heading matches when `cell_text(h2).casefold()` equals it.
  - Its section runs, in document order, until the next `h2`. Its tables are the section's tables
    that have no `table` ancestor.
  - Outcomes:

    | Case | Result |
    |---|---|
    | heading found more than once | `layout_not_recognised`, `"heading '<h>' appears <n> times"` |
    | two or more tables in a section | `layout_not_recognised`, `"section '<h>' has <n> tables"` |
    | a usable section's table has no rows | `layout_not_recognised`, `"the table has no rows"` |
    | heading missing | note `"section not found: <h>"` |
    | section has no table | note `"section has no table: <h>"` |
    | no usable section | `layout_not_recognised`, `"no section found"` |

  - Each usable table also gets the dated-text note. Every note is a
    `Reason("coverage_gap", …)`.
- **Units:** `own_rows(table, head=True)`; the cells are `row_cells(tr)`.
- **Per row** (P41, U02), checked in this order:
  1. the row sits in the table's own `thead` and every cell is a `th` → ignored `header_row`;
  2. exactly one cell whose `cell_text(...).casefold()` equals `FOOTNOTE` → ignored `footnote`;
  3. fewer than 2 cells → unparsed `too_few_cells`;
  4. no place → unparsed `place_missing`;
  5. no tokens → unparsed `date_missing`;
  6. otherwise, the token rules of P29 and P43.
- **Row outcome:**
  - With claims, the first reason that applies makes the unit partial:
    1. `date_unparsed`, if a token did not parse;
    2. `implausible_date`, if there is a future token;
    3. `place_unregistered`;
    4. `link_rejected`.

    If none applies, the unit is parsed.
  - Without claims, the unit is unparsed: `date_unparsed` if a token did not parse, else
    `implausible_date`.
  - `leftover` is the unparsed tokens, then the future tokens, joined by ", ".
- **The claims** are numbered `#0…` in token order. Each has:
  - the P28 office fields;
  - `office_label` = the section label, plus `" (targeted)"` for a starred token;
  - `link`: `source_link(URL, country cell a href, HOSTS)`, else `URL`;
  - `date_meaning="unknown"` (P39), `date_status="unknown"`, `date_text` = the token;
  - `evidence_kind="observation"`.
- **Relevance** comes from the date cell. A row with no second cell has relevance `unknown`.

- [ ] **Step 1: Write the failing tests.**

```python
def test_fixture_ledger_balances() -> None:
    res = parse(ALL); report = check(ALL, res)
    assert report.ok and res.reasons == ()
    assert report.outcomes == {"parsed": 14, "partial": 0, "unparsed": 46, "ignored": 1}
    assert report.ignored_reasons == {"footnote": 1}
    assert Counter(u.reason for u in res.units if u.outcome == "unparsed") == {"implausible_date": 42, "date_unparsed": 4}
    assert {u.relevance for u in res.units if u.outcome == "unparsed"} == {"before_window"}
    assert [(c.key, c.outcome, c.units_seen) for c in res.coverage] == [("observed", "ok", 61)]

def test_fixture_claims() -> None:
    assert [(c.claim_id.removeprefix("carter:observed/"), c.place_id, c.span.start.isoformat(), c.span.end.isoformat())
            for c in RES.claims] == [
        ("monitored-r6#0", "iso:CD", "2023-12-01", "2023-12-31"), ("monitored-r14#0", "iso:GY", "2025-09-01", "2025-09-30"),
        ("monitored-r39#0", "iso:TN", "2022-12-01", "2022-12-31"), ("monitored-r39#1", "iso:TN", "2023-01-01", "2023-01-31"),
        ("monitored-r41#0", "iso:VE", "2024-07-01", "2024-07-31"), ("monitored-r43#0", "iso:ZW", "2023-08-01", "2023-08-31"),
        ("expert-r2#0", "iso:BR", "2022-10-01", "2022-10-31"), ("expert-r3#0", "iso:CO", "2022-05-01", "2022-06-30"),
        ("expert-r3#1", "iso:CO", "2026-05-01", "2026-05-31"), ("expert-r3#2", "iso:CO", "2026-06-01", "2026-06-30"),
        ("expert-r7#0", "iso:KE", "2022-08-01", "2022-08-31"), ("expert-r9#0", "iso:LR", "2023-10-01", "2023-11-30"),
        ("expert-r11#0", "iso:PE", "2026-04-01", "2026-04-30"), ("expert-r11#1", "iso:PE", "2026-06-01", "2026-06-30"),
        ("expert-r12#0", "iso:PH", "2022-05-01", "2022-05-31"), ("expert-r14#0", "iso:TN", "2022-07-01", "2022-07-31"),
        ("expert-r15#0", "iso:VE", "2021-11-01", "2021-11-30"), ("expert-r16#0", "iso:ZM", "2021-08-01", "2021-08-31"),
    ]
    assert [c.claim_id for c in RES.claims if c.office_label.endswith("(targeted)")] == [
        "carter:observed/monitored-r6#0", "carter:observed/monitored-r39#1"]
    assert {(c.office_class, c.aggregate, c.kind, c.level, c.institution, c.evidence_kind, c.date_meaning) for c in RES.claims} == {
        ("general", True, "aggregate", "unknown", None, "observation", "unknown")}
    assert {urlsplit(c.link).hostname for c in RES.claims} == {"www.cartercenter.org"}
```

  - **`test_one_claim_field_by_field`:** `monitored-r6#0` has:
    - `office_label="Carter Center election observation (targeted)"`, `date_text="December 2023*"`;
    - `link="https://www.cartercenter.org/country/democratic-republic-of-the-congo/"`;
    - `span=DateSpan.month(2023, 12)`, `date_meaning="unknown"`.
  - **`test_token_grammar`** (synthetic rows; today is 2026-10-18; ✓ marks a targeted token):

    | Date cell | Unit | Claims (span, targeted) | Leftover |
    |---|---|---|---|
    | `"May 2026, June 2026*; and July 2026, Georgia (RLA) 2026, May 2026, October – November 2025"` | partial `date_unparsed` | May, June ✓, July 2026; Oct–Nov 2025 | `"Georgia (RLA) 2026"` |
    | `"May 2026, May 2026*"` | parsed | May 2026; May 2026 ✓ | `""` |
    | `"May 2026, May 2032"` | partial `implausible_date` | May 2026 | `"May 2032"` |
    | `"May 2032"` | unparsed `implausible_date`, relevance `in_or_after_window` | — | `"May 2032"` |
    | `"October 1991, December 2001"` | unparsed `implausible_date`, relevance `before_window` | — | `""` |
    | `"May 2021, May 2020"` | parsed | May 2021 (May 2020 is history) | `""` |
    | `"December 2031, January 2032"` | partial `implausible_date` | Dec 2031 | `"January 2032"` |
    | `"May 0000, May 2200"` | unparsed `date_unparsed` | — | `"May 0000, May 2200"` |

  - **`test_row_kinds`** (P41, U02; measured by `carter4.py` on `u02_carter.html`; every
    relevance below is `unknown`):

    | Row | Unit | Leftover |
    |---|---|---|
    | `<thead><tr><th>Country</th><th>Dates</th></tr></thead>` | ignored `header_row` | `""` |
    | `<tr><th>Country</th><th>Dates</th></tr>` in the body | unparsed `date_unparsed` | `"Dates"` |
    | `<tr><th scope="row">Chile</th><td>May 2026</td></tr>` | parsed, claim `iso:CL` May 2026 | `""` |
    | `<tr><th>Chile</th><th>May 2026</th></tr>` | parsed, claim `iso:CL` May 2026 | `""` |
    | `<tr><th scope="row">Chile</th><th>TBC</th></tr>` | unparsed `date_unparsed` | `"TBC"` |
    | `<tr><th scope="row">Chile</th><th></th></tr>` | unparsed `date_missing` | `""` |
    | one cell, `*Chile mission postponed; date TBD` | unparsed `too_few_cells` | `""` |
    | one cell, `*Chile May 2026` | unparsed `too_few_cells` | `""` |
    | one cell, the page's footnote text | ignored `footnote` | `""` |
    | one cell, `*These missions were targeted observations.` (reworded) | unparsed `too_few_cells` | `""` |

    Also: the single cell `"See also"` → unparsed `too_few_cells`; an empty country →
    `place_missing`. `test_fixture_ledger_balances` keeps the real footnote as the one ignored
    unit.
  - **`test_row_header_markup_gives_the_same_claims`:** the fixture, with every `<tr><td …>`
    country cell turned into `<th scope="row" …>`, gives the same 18 claims line for line
    (measured).
  - **`test_entity_and_curly_quote_names_resolve`:**
    - the fixture's `Cote d&#8217;Ivoire` row (`monitored-r5`) has the unit text
      `"Cote d’Ivoire | November 2010, December 2011, October 2020"` (U+2019);
    - that row and `Cherokee Nation` are history only (unparsed `implausible_date`), so their
      places are checked on synthetic rows dated `May 2026`:
      - `Cote d&#8217;Ivoire` → `iso:CI`;
      - `Cherokee Nation` → `x:cherokee-nation`;
      - `S&atilde;o Tom&eacute; and Pr&iacute;ncipe` → `iso:ST`.
  - **`test_sections_are_bound_to_their_heading`** (fixture edits, measured):

    | Edit | Outcome | Detail or notes |
    |---|---|---|
    | the first `<table>…</table>` removed | `ok`, 18 units (all `expert-`), 12 claims | notes `(Reason("coverage_gap", "section has no table: elections monitored by the carter center"),)` |
    | the "Expert Missions" `h2` repeated | `layout_not_recognised` | `"heading 'expert missions' appears 2 times"` |
    | an extra table before the first table | `layout_not_recognised` | `"section 'elections monitored by the carter center' has 2 tables"` |
    | "Expert Missions" renamed | `ok`, 43 units | notes `(Reason("coverage_gap", "section not found: expert missions"),)` |
    | both headings renamed | `layout_not_recognised` | `"no section found"` |
    | the Expert table's rows removed | `layout_not_recognised` | `"the table has no rows"` |

  - **`test_off_host_links_fall_back`:** the country href
    `"https://cartercenter.org.evil.example/x"` gives `link == URL` and partial `link_rejected`.
  - **`test_dated_text_beside_the_table_is_a_coverage_gap`:** a `<p>Chile May 2026</p>` inside
    the table's `figure` gives the note `"dated text beside the table: Chile May 2026"`.
  - **`test_broken_pages_get_an_outcome_never_units`:** truncated, empty and garbage bodies give
    the `</html>` detail.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/adapters/test_carter.py -q`.
  Expected: FAIL on import.
- [ ] **Step 3: Implement `Carter`.** Register it with
  `HeadingTablesRule(tuple((h, slug) for h, slug, _ in SECTIONS))`. The runner list becomes
  `["electionguide", "osce", "wikipedia", "aweb", "ipu", "carter"]`.
- [ ] **Step 4: Run** the file and `tests/unit/test_runner.py`. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:** `feat(sources): Carter Center observed-elections adapter`.

---

### Task 8: EEAS adapter

**Files:**
- Create: `elections_calendar/sources/eeas.py`, `tests/adapters/test_eeas.py`
- Modify:
  - `COUNT_RULES` (add `"eeas"`);
  - `DEFAULT_ADAPTERS` (last);
  - `importlinter.ini`;
  - `test_runner.py:392`.

**Interfaces:**
- Consumes: as in Task 7.
- Produces:
  - `class Eeas` with `source = "eeas"`;
  - `URL = "https://www.eeas.europa.eu/eeas/eu-election-observation-missions-1_en"`;
  - `HOSTS = ("eeas.europa.eu",)`;
  - `MISSION = re.compile(r"EOM (?P<country>.+) (?P<year>\d{4})")`;
  - one request, `"missions"`.

**Rules:**
- **Layout:**
  - There must be exactly one table holding an `a` whose `cell_text` fullmatches `MISSION`, else
    `layout_not_recognised` with detail `f"{n} tables with EOM links"`.
  - The page must also pass `complete_html`, and gets the dated-text note.
- **Units:** every cell of `row_cells(tr)`, for each `tr` in `own_rows(table, head=True)`,
  numbered `r<i>c<j>`.
- **Per cell**, checked in this order:
  1. empty text → ignored `empty_cell`;
  2. the text is `\d{4}` → ignored `year_heading`;
  3. the text does not fullmatch `MISSION` → unparsed `unrecognised_cell`;
  4. the text and the claim link both equal those of an earlier cell that gave a claim → ignored
     `duplicate`, with `duplicate_of` naming that cell (P42). The claim link here is the accepted
     `source_link`, else `URL`;
  5. no place → unparsed `place_missing`;
  6. `abs(year - window.today.year) > 5` → unparsed `implausible_date`. This is checked before any
     `DateSpan` is built (P43);
  7. an unregistered place → partial `place_unregistered`;
  8. an href that is present but rejected → partial `link_rejected`.
- **The claim:**
  - the P28 office fields, with `office_label="EU election observation mission"`;
  - `span=DateSpan.of_year(year)`;
  - `date_meaning="unknown"` (P39), `date_status="unknown"`, `date_text` = the year;
  - `evidence_kind="observation"`.
- **Relevance** comes from the cell text.

- [ ] **Step 1: Write the failing tests.**

```python
def test_fixture_ledger_balances() -> None:
    res = parse(ALL); report = check(ALL, res)
    assert report.ok and res.reasons == ()
    assert report.outcomes == {"parsed": 23, "partial": 0, "unparsed": 0, "ignored": 11}
    assert report.ignored_reasons == {"year_heading": 4, "empty_cell": 7}
    assert [(c.key, c.outcome, c.units_seen) for c in res.coverage] == [("missions", "ok", 34)]

def test_fixture_claims() -> None:      # v1 root cause 8: missions are years, never dates
    assert {(c.span.precision, c.date_meaning) for c in RES.claims} == {("year", "unknown")}
    assert Counter(c.span.year for c in RES.claims) == {2026: 5, 2025: 7, 2024: 4, 2023: 7}
    assert [c.place_id for c in RES.claims] == [
        "iso:CO", "iso:PE", "iso:BD", "iso:ZM", "iso:ST", "iso:MW", "iso:BO", "iso:PH", "iso:GY", "x:kosovo", "iso:EC",
        "iso:HN", "iso:LK", "iso:MZ", "iso:JO", "iso:SN", "iso:GT", "iso:LR", "iso:MV", "iso:NG", "iso:PY", "iso:SL", "iso:ZW"]
    assert {urlsplit(c.link).hostname for c in RES.claims} == {"www.eeas.europa.eu"}
```

  - **`test_one_claim_field_by_field`:** `eeas:missions/r2c1#0` has `place_id="iso:CO"`,
    `span=DateSpan.of_year(2026)`, `link="https://www.eeas.europa.eu/eom-colombia-2026_en"`,
    `date_text="2026"`, `date_meaning="unknown"` and the P28 fields.
  - **`test_cell_kinds`** (B-T04):
    - the same text and href twice → the second is ignored `duplicate`, naming the first;
    - `EOM Chile 2026` and `EOM Peru 2026` sharing one href → two claims;
    - `EOM Chile 2026` and `EOM Chile 2025` sharing one href → two claims;
    - `EOM Chile 2040`, then `EOM Chile 2026`, sharing one href → unparsed `implausible_date`,
      then a claim (not a duplicate);
    - "Election Observation Missions archive" → unparsed `unrecognised_cell`;
    - "EOM Narnia 2026" → partial `place_unregistered`;
    - a matching cell without a link → `link == URL`;
    - a `<th>2026</th>` cell → ignored `year_heading`, and the ledger counts it.
  - **`test_mission_years_outside_the_model_are_outcomes`** (B-T07):
    - `EOM Chile 0000`, `1899`, `2200` and `9999` → unparsed `implausible_date`, no exception;
    - `EOM Chile 2021` → a claim; `EOM Chile 2020` → `implausible_date`.
  - **`test_off_host_links_fall_back`:** `href="//example.invalid/eom"` gives `link == URL` and
    partial `link_rejected`.
  - **`test_a_new_year_heading_is_ignored_and_its_missions_parsed`:** a synthetic `2027` row
    before the 2026 rows is `year_heading`, and its "EOM Chile 2027" gives a 2027 claim.
  - **`test_dated_text_beside_the_table_is_a_coverage_gap`:** as in Task 4.
  - **`test_broken_pages_get_an_outcome_never_units`:**
    - no EOM links → `"0 tables with EOM links"`;
    - the table duplicated → `"2 tables with EOM links"`;
    - truncated, empty and garbage bodies → the `</html>` detail.
- [ ] **Step 2: Run** `.venv/Scripts/python.exe -m pytest tests/adapters/test_eeas.py -q`.
  Expected: FAIL on import.
- [ ] **Step 3: Implement `Eeas`.** Register it; the runner list becomes
  `["electionguide", "osce", "wikipedia", "aweb", "ipu", "carter", "eeas"]`.
- [ ] **Step 4: Run** the file and `tests/unit/test_runner.py`. Expected: PASS.
- [ ] **Step 5: Gates, mutation table, commit:** `feat(sources): EEAS election observation missions adapter`.

## Requirements for later plans

Each later plan's pre-flight must pull its rows from this table into its own tasks, with the
named acceptance test. A row is closed only when that test is green in the owning plan.

| ID | Requirement | Owner | Acceptance test (name and result) | Completion stage |
|---|---|---|---|---|
| R1 | Health compares, per source, usable claims, ignored-reason counts and section coverage, not only unit totals (P22, P23) | Plan 4 | `test_a_shift_into_ignored_reasons_is_a_warning`: IPU rows moving from dated to `no_expected_date` at equal totals → warning. `test_claims_falling_while_units_hold_is_a_warning`: a header-only or all-ignored table → warning | Plan 4's health task |
| R2 | Year rollover never silently loses December evidence. A-WEB's previous-year claims that still overlap the window stay as fallback evidence, or the coverage limit is reported (P31) | Plan 4 | `test_aweb_rollover_keeps_december_events`: when a 2026 list is replaced by an empty or a 2027 list on 2 January, the 5 December 2026 Gambia claim stays as fallback, or the limit is reported | Plan 4's snapshot task |
| R3 | `ipu:<code>` identifies a chamber, not an election cycle. A new expected date for the same chamber is told apart from a rescheduling (P32) | Plan 3 | `test_ipu_chamber_id_is_not_an_election_cycle`: (a) the same `source_event_id` with two dates a term apart and no other evidence → two cycles; (b) the same `source_event_id` with dates days apart, where a fixture assertion says they concern the same cycle (for example an announced postponement naming the previous date) → one rescheduled cycle; (c) the same `source_event_id` with dates days apart and no such evidence → never merged on date proximity plus chamber ID alone (Plan 3 decides whether that is two cycles or unresolved). Plan 3 settles the identity rules | Plan 3's identity task |
| R4 | An unmatched IPU renewal stays an expected renewal (`tentative`, `expected_window`) in the merge, the feed and the extension, and is never an announced date (P25) | Plans 3 and 5 | `test_unmatched_renewal_is_expected_not_announced` (Plan 3); the extension's label test for a renewal-only contest (Plan 5) | Plan 3's merge; Plan 5's extension |
| R5 | **Open policy.** Spec §10.5 step 1 says: "Eligibility: `calendar` > `expected_renewal` > `observation`; umbrella and provisional claims are excluded." Plan 3 decides whether an observation can ever be the selected date. Its rule must tell a mission's year or observation period apart from a source that names an election's polling date. Whatever it decides, a `date_meaning="unknown"` observation never becomes a polling date, and never makes a contest Held/Ongoing through date precedence or elapsed time, including in the legacy feed (P39) | Plans 3 and 4 | `test_unknown_meaning_observation_is_never_a_polling_date` and `test_unknown_meaning_observation_never_makes_held_or_ongoing` (Plan 3), plus the legacy-feed case (Plan 4) | Decided before Plan 3 implements date selection; legacy-feed test in Plan 4 |
| R6 | Observations get the role `weak`, decided before the umbrella rule. They match on place and a compatible date only. Zero candidates → `unresolved_evidence` when in or after the window; several → unresolved (§10.3). Year-only observations use the unit's year-aware relevance, never `Window.overlaps` alone (P28) | Plan 3 | `test_observation_with_zero_one_and_several_candidates`; `test_year_only_observation_stays_accounted_for` | Plan 3's matching task |
| R7 | A claim with a subdivision `jurisdiction` and level `unknown` never joins a nationwide contest through generic office wording (P38, F-08). The test uses OSCE r52 and A-WEB r5 | Plan 3 | `test_subdivision_claim_never_joins_a_nationwide_contest` | Plan 3's identity task |
| R8 | OSCE's 8 year-only claims, and every EEAS claim, have year precision. Spec §7's "Year-only → undated" is the merge's rule: these claims reach the undated list, never a dated contest | Plan 3 | `test_year_precision_claims_are_undated` | Plan 3's merge |
| R9 | NDI and EISA follow this contract (`parse_pages`, `source_link`, `label_scope`, P40–P44). The dynamic-requests contract is decided before either adapter; M6/M7/L70/L72/L81 are decided from EISA's text. EISA's JSON list needs a fourth rule type | Plan 2c | Plan 2c's own tests | Plan 2c |
| R10 | The runner now starts 7 sources, at most 4 at once. Check the scrape deadline against the measured fetch times: OSCE 0.5 s, IPU 0.5 s, A-WEB 1.6 s, Carter 0.9 s, EEAS 0.5 s (2026-10-18) | Plan 5 | the workflow's deadline test | Plan 5 |
| R11 | Carter's `coverage_gap` notes name the missing section. The three new ignored reasons appear in `ignored_reasons` and `HEALTH.md` like the others | Plan 4 | `test_health_lists_coverage_gaps_and_ignored_reasons` | Plan 4's health task |

## After Plan 2b

- **The branch** has 8 new commits on top of the commit that holds this plan, with all gates
  green. Nothing is pushed or merged.
- **The Review record** shows the Plan 2b part of every "planned" row as "verified", with its
  commit in the ledger. Each later-plan part (R1–R11, and the B06/B07/P22/P23/P25/P28/P31
  conditions that point to them) stays open until its own plan's acceptance test passes.
- **Next:** Plan 2c (NDI, EISA, dynamic requests), written against this code.
