// v1.0.2's renderer (applyDataToUI, renderCurrentMonth, buildCard), moved here from popup.js.
// What changed: it takes the feed document and the pinned countries as arguments; its tabs filter
// on upcoming / past (status Held) / all; it no longer writes the footer (the popup does, from
// lib/health.js); and the search box is no longer reset on each load (popup.js used to
// clear it in fetchData). It keeps v1.0.2's innerHTML cards until later tasks
// replace them.

import { pinMatcher, placeOf } from "./pins.js";

const $ = (id) => document.getElementById(id);
const stateLoading   = $("stateLoading");
const stateError     = $("stateError");
const stateEmpty     = $("stateEmpty");
const electionList   = $("electionList");
const searchInput    = $("searchInput");
const prevMonthBtn   = $("prevMonthBtn");
const nextMonthBtn   = $("nextMonthBtn");
const prevMonthLabel = $("prevMonthLabel");
const nextMonthLabel = $("nextMonthLabel");
const currentMonthLabel = $("currentMonthLabel");
const statTotal      = $("statTotal");
const statTotalLabel = $("statTotalLabel");
const levelFilter    = $("levelFilter");
const recordCount    = $("recordCount");
const statHeld       = $("statHeld");
const statHeldLabel  = $("statHeldLabel");
const listTitle      = $("listTitle");
const tabUpcoming    = $("tabUpcoming");
const tabPast        = $("tabPast");
const tabAll         = $("tabAll");
const pinBar         = $("pinBar");
const pinBarText     = $("pinBarText");

let monthsData   = {};   // { "YYYY-MM": [...elections] }
let currentMonth = "";   // "YYYY-MM" currently displayed
let serverCurrentMonth = ""; // what the scraper considers "now"
let availableMonths = []; // sorted list of month keys in the data
let activeTab        = "all"; // "upcoming" | "past" | "all"
let filterQuery      = "";
let pinnedPlaces     = [];  // place ids to show exclusively (empty = show all)
let placeTable       = null; // extension/places.json: maps v1's country strings to place ids

function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }

function monthName(isoMonth) {
  const [y, m] = isoMonth.split("-");
  return new Date(Date.UTC(+y, +m - 1, 1))
    .toLocaleString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
}

function monthShort(isoMonth) {
  const [y, m] = isoMonth.split("-");
  return new Date(Date.UTC(+y, +m - 1, 1))
    .toLocaleString("en-US", { month: "short", timeZone: "UTC" }).toUpperCase();
}

function formatDate(isoStr) {
  const d = new Date(isoStr + "T12:00:00Z");
  const day = String(d.getUTCDate());
  const mon = d.toLocaleString("en-US", { month: "short", timeZone: "UTC" }).toUpperCase();
  return { day, mon };
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function statusChipClass(status) {
  switch ((status || "").toLowerCase()) {
    case "upcoming":  return "chip-upcoming";
    case "held":      return "chip-held";
    case "postponed": return "chip-postponed";
    case "cancelled": return "chip-cancelled";
    case "disputed":  return "chip-disputed";
    default:          return "chip-unknown";
  }
}

// ── Card builder ──────────────────────────────────────────────

// Normalise: support both old schema (source_name/link) and new (sources[])
function getSources(election) {
  if (election.sources && election.sources.length) return election.sources;
  // Legacy fallback
  return [{ name: election.source_name || "?", link: election.link || "#" }];
}

function buildSourceChips(sources) {
  return sources.map(s =>
    `<span class="chip chip-source source-chip-link" data-link="${escHtml(s.link)}"
           title="Open ${escHtml(s.name)}">${escHtml(s.name)}</span>`
  ).join("");
}

function buildCard(election) {
  const { day, mon } = formatDate(election.date);
  const status  = election.status || "Unknown";
  const sources = getSources(election);
  const primaryLink = sources[0].link;

  const li = document.createElement("li");
  li.className = "election-item";
  li.innerHTML = `
    <div class="date-badge">
      <span class="day">${escHtml(day)}</span>
      <span class="mon">${escHtml(mon)}</span>
    </div>
    <div class="election-info">
      <div class="election-top">
        <span class="election-country">${escHtml(election.country)}</span>
        <button class="election-link-icon" aria-label="Open source for ${escHtml(election.country)}">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
               stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
               width="12" height="12">
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
            <polyline points="15 3 21 3 21 9"/>
            <line x1="10" y1="14" x2="21" y2="3"/>
          </svg>
        </button>
      </div>
      <div class="election-type">${escHtml(election.type)}</div>
      <div class="election-chips">
        ${buildSourceChips(sources)}
        <span class="chip ${statusChipClass(status)}">${escHtml(status)}</span>
      </div>
    </div>`;

  // Source chips: each opens its own link
  li.querySelectorAll(".source-chip-link").forEach(chip => {
    chip.addEventListener("click", (e) => {
      e.stopPropagation();
      chrome.tabs.create({ url: chip.dataset.link });
    });
  });

  // External link icon and card body → primary source
  li.querySelector(".election-link-icon").addEventListener("click", (e) => {
    e.stopPropagation();
    chrome.tabs.create({ url: primaryLink });
  });
  li.addEventListener("click", () => chrome.tabs.create({ url: primaryLink }));

  return li;
}

// ── Render ────────────────────────────────────────────────────
function renderCurrentMonth() {
  const elections = monthsData[currentMonth] || [];

  // Apply tab filter
  let filtered = elections;
  if (activeTab === "upcoming") {
    filtered = elections.filter(e =>
      !["held", "postponed", "cancelled", "disputed"].includes(
        (e.status || "").toLowerCase()
      )
    );
  } else if (activeTab === "past") {
    filtered = elections.filter(e =>
      (e.status || "").toLowerCase() === "held"
    );
  }

  // Apply pin filter — if any countries are pinned, show only those
  if (pinnedPlaces.length > 0) {
    const shows = pinMatcher(pinnedPlaces, placeTable);
    filtered = filtered.filter(e => shows(placeOf(e.country, placeTable)));
    show(pinBar);
    const n = pinnedPlaces.length;
    pinBarText.textContent = `Pinned view · ${n} ${n === 1 ? "country" : "countries"}`;
  } else {
    hide(pinBar);
  }

  // Apply search query
  if (filterQuery) {
    const q = filterQuery.toLowerCase();
    filtered = filtered.filter(e => {
      const srcText = e.source_names ? e.source_names.join(" ") : (e.source_name || "");
      return (
        e.country.toLowerCase().includes(q) ||
        e.type.toLowerCase().includes(q) ||
        srcText.toLowerCase().includes(q) ||
        (e.status || "").toLowerCase().includes(q)
      );
    });
  }

  // Update bento stats (always from full list, not filtered)
  statTotalLabel.textContent = "Total Scheduled";
  statTotal.textContent = String(elections.length).padStart(2, "0");
  const heldCount = elections.filter(
    e => (e.status || "").toLowerCase() === "held"
  ).length;
  statHeld.textContent = String(heldCount).padStart(2, "0");

  // Update bento label based on whether current is the "now" month
  if (currentMonth === serverCurrentMonth) {
    statHeldLabel.textContent = "Held This Month";
  } else {
    statHeldLabel.textContent = "Held";
  }

  // Update list title
  listTitle.textContent = monthName(currentMonth) + " Schedule";

  // Update month nav labels
  const idx = availableMonths.indexOf(currentMonth);
  prevMonthLabel.textContent = idx > 0 ? monthShort(availableMonths[idx - 1]) : "";
  nextMonthLabel.textContent = idx < availableMonths.length - 1
    ? monthShort(availableMonths[idx + 1]) : "";
  currentMonthLabel.textContent = monthName(currentMonth).toUpperCase();

  // Nav button visibility
  prevMonthBtn.style.visibility = idx > 0 ? "visible" : "hidden";
  nextMonthBtn.style.visibility = idx < availableMonths.length - 1 ? "visible" : "hidden";

  // Render list
  electionList.innerHTML = "";
  if (filtered.length === 0) {
    hide(electionList);
    show(stateEmpty);
    hide(stateLoading);
    hide(stateError);
    return;
  }
  hide(stateLoading);
  hide(stateError);
  hide(stateEmpty);
  show(electionList);

  const frag = document.createDocumentFragment();
  filtered.forEach((e, i) => {
    const card = buildCard(e);
    card.style.animationDelay = `${i * 18}ms`;
    frag.appendChild(card);
  });
  electionList.appendChild(frag);
}

export function renderLegacy(json, { pinned, table }) {
  pinnedPlaces = pinned;
  placeTable = table;
  // The controls are shared with lib/render.js: take over what a v2 render left on them.
  filterQuery = searchInput.value;
  hide(levelFilter);
  hide(recordCount);
  [tabUpcoming, tabPast, tabAll].forEach(t => {
    t.classList.toggle("active", t.dataset.filter === activeTab);
    t.removeAttribute("aria-selected");
  });
  // Support both old format (json.elections flat) and new format (json.months)
  if (json.months) {
    monthsData = json.months;
    availableMonths = Object.keys(monthsData).sort();
    serverCurrentMonth = json.current_month || availableMonths[Math.floor(availableMonths.length / 2)];
  } else {
    // Legacy fallback: single flat elections array
    const key = json.month || "unknown";
    monthsData = { [key]: json.elections || [] };
    availableMonths = [key];
    serverCurrentMonth = key;
  }

  // Default to the server's current month
  if (!currentMonth || !monthsData[currentMonth]) {
    currentMonth = serverCurrentMonth;
  }

  if (json.errors && json.errors.length > 0) {
    console.warn("Scraper reported errors:", json.errors);
  }

  renderCurrentMonth();
}

// ── Event listeners ───────────────────────────────────────────
// Act only while this renderer is the active one (popup.js sets body.dataset.renderer), since
// lib/render.js listens on the same controls.
function active() {
  return document.body.dataset.renderer === "legacy";
}

searchInput.addEventListener("input", () => {
  if (!active()) return;
  filterQuery = searchInput.value;
  renderCurrentMonth();
});

prevMonthBtn.addEventListener("click", () => {
  if (!active()) return;
  const idx = availableMonths.indexOf(currentMonth);
  if (idx > 0) { currentMonth = availableMonths[idx - 1]; renderCurrentMonth(); }
});

nextMonthBtn.addEventListener("click", () => {
  if (!active()) return;
  const idx = availableMonths.indexOf(currentMonth);
  if (idx < availableMonths.length - 1) {
    currentMonth = availableMonths[idx + 1];
    renderCurrentMonth();
  }
});

[tabUpcoming, tabPast, tabAll].forEach(tab => {
  tab.addEventListener("click", () => {
    if (!active()) return;
    [tabUpcoming, tabPast, tabAll].forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    activeTab = tab.dataset.filter;
    renderCurrentMonth();
  });
});
