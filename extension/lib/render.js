// The v2 renderer: month, tab, level and search state of a v2 feed document, drawn through
// lib/count.js. Feed text is inserted with textContent only, never as markup. A card body opens
// no link (R47, ruling 30); only an Open button (a source, umbrella or attention row) does,
// through safeLink.
import { view, recordText, startMonth } from "./count.js";
import { attentionView, ATTENTION_PAGE, shownLine } from "./attention.js";
import { badge, monthName, monthYear } from "./dates.js";
import { childDetails, childIndex } from "./details.js";
import { pinMatcher } from "./pins.js";
import { keepFocus, syncTabs, tabTarget } from "./a11y.js";

const $ = (id) => document.getElementById(id);
const stateLoading      = $("stateLoading");
const stateError        = $("stateError");
const stateEmpty        = $("stateEmpty");
const electionList      = $("electionList");
const searchInput       = $("searchInput");
const levelFilter       = $("levelFilter");
const recordCount       = $("recordCount");
const prevMonthBtn      = $("prevMonthBtn");
const nextMonthBtn      = $("nextMonthBtn");
const prevMonthLabel    = $("prevMonthLabel");
const nextMonthLabel    = $("nextMonthLabel");
const currentMonthLabel = $("currentMonthLabel");
const statTotal         = $("statTotal");
const statTotalLabel    = $("statTotalLabel");
const statHeld          = $("statHeld");
const statHeldLabel     = $("statHeldLabel");
const listTitle         = $("listTitle");
const pinBar            = $("pinBar");
const pinBarText        = $("pinBarText");
const attention         = $("attention");
const attentionToggle   = $("attentionToggle");
const attentionNote     = $("attentionNote");
const attentionList     = $("attentionList");
const attentionShown    = $("attentionShown");
const attentionMore     = $("attentionMore");
const tabs = [$("tabUpcoming"), $("tabPast"), $("tabAll")];

let doc = null;       // the v2 feed document drawn last
let pinned = [];     // the pinned place ids
let matches = () => true;
let today = "";
let now = 0;
let month = "";       // "YYYY-MM" shown
let tab = "all";      // "upcoming" | "past" | "all"
let level = "all";    // "all" | "national" | "subnational"
let query = "";
let index = null;     // child_id -> {card, child}, built on the first draw that needs it, per doc
const open = new Set(); // group_ids of the expanded cards, for the popup's life
let attentionOpen = false; // the attention section's open state, for the popup's life
let attentionRows = ATTENTION_PAGE; // rows shown while open; a changed search resets it
let attentionQuery = "";

function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }

function text(tag, className, value) {
  const el = document.createElement(tag);
  el.className = className;
  el.textContent = value;
  return el;
}

function openButton(link, label, onOpen, key) {
  const button = text("button", "open-button " + onOpen, "Open");
  button.type = "button";
  button.dataset.focus = key;
  button.setAttribute("aria-label", label);
  button.addEventListener("click", () => {
    if (document.body.dataset.renderer !== "v2") return;
    chrome.tabs.create({ url: link });
  });
  return button;
}

function line(className, value, button) {
  const el = text("div", className, "");
  el.append(text("span", "line-text", value));
  if (button !== null) el.append(button);
  return el;
}

// One kept child: heading, its label from the view, a line per source and umbrella, and its
// possible matches. The label is the view's, so the face and the entry share one clock (C03).
function buildChild(card, { child, label }) {
  if (index === null) index = childIndex(doc);
  const d = childDetails(card, child, { index });
  const el = document.createElement("div");
  el.className = "child-entry";
  el.dataset.childId = child.child_id;
  el.append(text("div", "child-heading", d.heading));

  const labelEl = document.createElement("div");
  labelEl.className = "child-label";
  labelEl.dataset.kind = label.kind;
  labelEl.append(text("span", "child-label-text", label.text));
  const chips = document.createElement("div");
  chips.className = "child-chips";
  for (const chip of label.chips) chips.append(text("span", `chip chip-${chip.kind}`, chip.text));
  const notes = document.createElement("ul");
  notes.className = "child-notes";
  for (const note of label.notes) notes.append(text("li", "", note));
  labelEl.append(chips, notes);
  el.append(labelEl);

  d.sources.forEach((s, n) => {
    const button = s.link === null ? null : openButton(
      s.link, `Open ${s.name} for ${d.heading} (new tab)`, "source-open", `open:${child.child_id}:${n}`);
    el.append(line("source-line", s.text, button));
  });
  d.umbrellas.forEach((u, n) => {
    const button = u.link === null ? null : openButton(
      u.link, `Open ${u.name} (${u.officeLabel}) for ${d.heading} (new tab)`, "umbrella-open",
      `umbrella:${child.child_id}:${n}`);
    el.append(line("umbrella-line", u.text, button));
  });
  for (const p of d.possible) el.append(text("div", "possible-line", p));
  return el;
}

// The details of an open card: built when it is opened or redrawn, never before.
function fillDetails(box, entry, isOpen) {
  box.replaceChildren();
  box.hidden = !isOpen;
  if (!isOpen) return;
  for (const kept of entry.children) box.append(buildChild(entry.card, kept));
}

function buildCard(entry) {
  const { card, children, label, match } = entry;
  const { day, mon } = badge(card);
  const li = document.createElement("li");
  li.className = "election-item election-item-v2";
  li.dataset.groupId = card.group_id;

  const date = document.createElement("div");
  date.className = "date-badge";
  date.append(text("span", "day", day), text("span", "mon", mon));

  const top = document.createElement("div");
  top.className = "election-top";
  top.append(text("span", "election-country", card.country));

  const labelEl = text("div", "card-label", label.text);
  labelEl.dataset.kind = label.kind;

  const chips = document.createElement("div");
  chips.className = "election-chips";
  const seenChips = new Set();
  for (const { label: childLabel } of children) {
    for (const chip of childLabel.chips) {
      if (seenChips.has(chip.text)) continue;
      seenChips.add(chip.text);
      chips.append(text("span", `chip chip-${chip.kind}`, chip.text));
    }
  }

  const notes = document.createElement("ul");
  notes.className = "card-notes";
  const seen = new Set();
  for (const { label: childLabel } of children) {
    for (const note of childLabel.notes) {
      if (seen.has(note)) continue;
      seen.add(note);
      const item = document.createElement("li");
      item.textContent = note;
      notes.append(item);
    }
  }

  const info = document.createElement("div");
  info.className = "election-info";
  const box = document.createElement("div");
  box.className = "card-details";
  box.id = `details-${card.group_id}`;
  const toggle = text("button", "card-toggle", "");
  toggle.type = "button";
  toggle.dataset.focus = `toggle:${card.group_id}`;
  toggle.setAttribute("aria-controls", box.id);
  const sync = () => {
    const isOpen = open.has(card.group_id);
    toggle.textContent = isOpen ? "Hide details" : "Show details";
    toggle.setAttribute("aria-expanded", String(isOpen));
    fillDetails(box, entry, isOpen);
  };
  toggle.addEventListener("click", () => {
    if (!active()) return;
    if (open.has(card.group_id)) open.delete(card.group_id);
    else open.add(card.group_id);
    sync();
  });
  sync();

  info.append(top, text("div", "election-type", card.type), labelEl, text("div", "card-match", match), chips, notes, toggle);
  li.append(date, info, box);
  return li;
}

function buildAttentionRow(row) {
  const li = document.createElement("li");
  li.className = "attention-row";
  li.dataset.itemId = row.id;
  li.append(text("div", "attention-text", row.text), text("div", "attention-source", row.source));
  if (row.undated !== null) li.append(text("div", "attention-undated", row.undated));
  for (const p of row.possible) li.append(text("div", "possible-line", p));
  if (row.link !== null) li.append(openButton(row.link, row.label, "attention-open", `attention-open:${row.id}`));
  return li;
}

// The section: its count and note always, its rows only while open (never built before).
function drawAttention() {
  if (attentionQuery !== query) {
    attentionQuery = query;
    attentionRows = ATTENTION_PAGE;
  }
  if (index === null) index = childIndex(doc);
  const got = attentionView(doc, { query, index });
  show(attention);
  attentionToggle.textContent = got.title;
  attentionToggle.setAttribute("aria-expanded", String(attentionOpen));
  attentionNote.textContent = got.note;
  attentionNote.hidden = got.note === "";
  attentionList.replaceChildren();
  attentionList.hidden = !attentionOpen;
  const shown = Math.min(attentionRows, got.rows.length);
  const left = got.rows.length - shown;
  const line = attentionOpen ? shownLine(shown, got.rows.length) : "";
  attentionShown.textContent = line;
  attentionShown.hidden = line === "";
  attentionMore.hidden = !attentionOpen || left === 0;
  attentionMore.textContent = `Show ${Math.min(left, ATTENTION_PAGE)} more`;
  if (!attentionOpen) return;
  const frag = document.createDocumentFragment();
  for (const row of got.rows.slice(0, shown)) frag.append(buildAttentionRow(row));
  attentionList.append(frag);
}

// For a non-v2 render: the section is v2's, so its rows go too (the open state is kept).
export function hideAttention() {
  hide(attention);
  attentionList.replaceChildren();
  attentionList.hidden = true;
  attentionShown.hidden = true;
  attentionMore.hidden = true;
}

// Every redraw keeps keyboard focus on the control it had, by data-focus key (P146).
function draw() {
  keepFocus(paint);
}

function paint() {
  const months = doc.window.months;
  const idx = months.indexOf(month);
  const shown = view(doc, { month, tab, level, query, pins: matches, today, now });

  // tabs: the shown one only
  syncTabs(tabs, tab);
  show(levelFilter);
  show(recordCount);
  statTotalLabel.textContent = "Election records";
  statHeldLabel.textContent = "Confirmed held";
  statTotal.textContent = String(shown.records);
  statHeld.textContent = String(shown.held);
  recordCount.textContent = recordText(shown.records, shown.groupings);

  const label = `${month}-01`;
  listTitle.textContent = `${monthYear(label)} Schedule`;
  currentMonthLabel.textContent = monthYear(label).toUpperCase();
  prevMonthLabel.textContent = idx > 0 ? monthName(`${months[idx - 1]}-01`).slice(0, 3).toUpperCase() : "";
  nextMonthLabel.textContent = idx < months.length - 1
    ? monthName(`${months[idx + 1]}-01`).slice(0, 3).toUpperCase() : "";
  prevMonthBtn.style.visibility = idx > 0 ? "visible" : "hidden";
  nextMonthBtn.style.visibility = idx < months.length - 1 ? "visible" : "hidden";

  if (pinned.length > 0) {
    show(pinBar);
    const n = pinned.length;
    pinBarText.textContent = `Pinned view · ${n} ${n === 1 ? "country" : "countries"}`;
  } else {
    hide(pinBar);
  }

  drawAttention(); // before the empty-state return: the section stays on every month

  hide(stateLoading);
  hide(stateError);
  electionList.replaceChildren();
  if (shown.cards.length === 0) {
    hide(electionList);
    show(stateEmpty);
    return;
  }
  hide(stateEmpty);
  show(electionList);
  const frag = document.createDocumentFragment();
  shown.cards.forEach((entry, i) => {
    const li = buildCard(entry);
    li.style.animationDelay = `${i * 18}ms`;
    frag.append(li);
  });
  electionList.append(frag);
}

export function renderV2(feed, opts) {
  if (doc !== feed) index = null;
  doc = feed;
  pinned = opts.pinned;
  matches = pinMatcher(pinned, opts.table);
  today = opts.today;
  now = opts.now;
  if (!doc.window.months.includes(month)) month = startMonth(doc, today);
  query = searchInput.value;
  level = levelFilter.value;
  draw();
}

// Control listeners act only while this module's renderer is the active one (popup.js sets
// body.dataset.renderer before it calls a renderer), so two renderers never both answer.
function active() {
  return document.body.dataset.renderer === "v2";
}

attentionToggle.addEventListener("click", () => {
  if (!active()) return;
  attentionOpen = !attentionOpen;
  keepFocus(drawAttention);
});

attentionMore.addEventListener("click", () => {
  if (!active()) return;
  attentionRows += ATTENTION_PAGE;
  keepFocus(drawAttention);
});

searchInput.addEventListener("input", () => {
  if (!active()) return;
  query = searchInput.value;
  draw();
});

levelFilter.addEventListener("change", () => {
  if (!active()) return;
  level = levelFilter.value;
  draw();
});

function step(by) {
  if (!active()) return;
  const months = doc.window.months;
  const next = months.indexOf(month) + by;
  if (next >= 0 && next < months.length) {
    month = months[next];
    draw();
  }
}
prevMonthBtn.addEventListener("click", () => step(-1));
nextMonthBtn.addEventListener("click", () => step(1));

for (const t of tabs) {
  t.addEventListener("click", () => {
    if (!active()) return;
    tab = t.dataset.filter;
    draw();
  });
}

// ArrowLeft and ArrowRight (wrapping), Home and End select and focus a tab (P146).
$("tabs").addEventListener("keydown", (event) => {
  if (!active()) return;
  const next = tabTarget(event.key, tabs, event.target);
  if (next === null) return;
  event.preventDefault();
  tab = next.dataset.filter;
  draw();
  next.focus();
});
