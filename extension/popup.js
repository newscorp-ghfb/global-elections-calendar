import { KEYS, loadPlaces, loadSchemas, storedFeed, storedStatus } from "./lib/load.js";
import { bannerState, footerState, NO_HEALTH, panelRows } from "./lib/health.js";
import { isLinked } from "./lib/order.js";
import { PIN_KEYS, currentPins } from "./lib/pins.js";
// render.js loads before legacy.js, so on a click its listener runs first and legacy's second.
import { renderV2 } from "./lib/render.js";
import { renderLegacy } from "./lib/legacy.js";
import { localToday } from "./lib/dates.js";

const $ = (id) => document.getElementById(id);
const stateLoading = $("stateLoading");
const stateError   = $("stateError");
const errorMsgEl   = $("errorMsg");
const searchInput  = $("searchInput");
const filterBar    = $("filterBar");
const refreshBtn   = $("refreshBtn");
const helpBtn      = $("helpBtn");
const retryBtn     = $("retryBtn");
const filterToggle = $("filterToggle");
const banner       = $("banner");
const healthPanel  = $("healthPanel");

let schemas = null;
let table = null; // the place table (extension/places.json)
let inFlight = 0; // checks started and not finished; the page is settled at 0

function showError(message) {
  errorMsgEl.textContent = `Could not load data: ${message}`;
  stateLoading.classList.add("hidden");
  stateError.classList.remove("hidden");
  document.body.dataset.state = "error";
}

// The panel's rows, as text only. Rebuilt on every render, so an open panel is never out of date.
function drawPanel(rows, note) {
  const noteEl = $("healthNote");
  noteEl.textContent = note;
  noteEl.hidden = note === "";
  const list = $("healthList");
  list.replaceChildren();
  for (const row of rows) {
    const item = document.createElement("li");
    item.dataset.source = row.source;
    item.dataset.severity = row.severity;
    const title = document.createElement("strong");
    title.textContent = row.name;
    item.append(title);
    for (const line of row.lines) {
      const para = document.createElement("div");
      para.textContent = line;
      item.append(para);
    }
    list.append(item);
  }
}

// The banner, the panel and the footer for the feed just drawn, all at the render's `now` (P139).
function drawHealth(record, statusRecord, check, now) {
  const status = statusRecord === null ? null : statusRecord.data;
  const linked = isLinked(record.sha256, status);
  const args = { format: record.format, doc: record.data, status, linked, now };
  const state = bannerState(args);
  banner.dataset.level = state.level;
  $("bannerText").textContent = state.text;
  // the counts are shown only when they say more than the banner's own text (R57)
  $("bannerCounts").textContent = state.counts;
  $("bannerCounts").hidden = state.counts === "" || state.counts === state.text;
  banner.classList.remove("hidden");
  const rows = panelRows(args);
  drawPanel(rows, record.format === "v2" ? "" : NO_HEALTH);
  const foot = footerState({ doc: record.data, check, now });
  $("footerData").textContent = foot.data;
  $("footerChecked").textContent = foot.checked;
}

// Render the cached feed, if the stored record is valid. True when something was drawn.
async function render() {
  const stored = await chrome.storage.local.get([
    KEYS.feed, KEYS.status, KEYS.check, ...Object.values(PIN_KEYS),
  ]);
  const record = storedFeed(stored[KEYS.feed], schemas);
  if (record === null) return false;
  // The popup never writes pins: until the worker has migrated them, it derives them here.
  const pinned = currentPins(stored, table).places;
  const now = Date.now(); // read once: the cards, the banner and the panel agree (P139)
  if (record.format === "v2") {
    document.body.dataset.renderer = "v2";
    renderV2(record.data, { pinned, table, today: localToday(now), now });
  } else {
    document.body.dataset.renderer = "legacy";
    $("attention").classList.add("hidden"); // the section is v2's only
    renderLegacy(record.data, { pinned, table });
  }
  drawHealth(record, storedStatus(stored[KEYS.status], schemas), stored[KEYS.check], now);
  document.body.dataset.state = "ready";
  return true;
}

async function check(force) {
  inFlight += 1;
  document.body.dataset.checking = "true";
  refreshBtn.classList.add("spinning");
  try {
    let reply = null;
    let failure = null;
    try {
      reply = await chrome.runtime.sendMessage({ type: "CHECK", force });
    } catch (err) {
      failure = err instanceof Error ? err.message : String(err);
    }
    if (await render()) return;
    if (failure !== null) showError(failure);
    else if (reply && reply.ok === false) showError(reply.error);
    else showError("no data yet");
  } catch (err) {
    showError(err instanceof Error ? err.message : String(err));
  } finally {
    inFlight -= 1;
    if (inFlight === 0) {
      refreshBtn.classList.remove("spinning");
      document.body.dataset.checking = "false";
    }
  }
}

function again() {
  if (document.body.dataset.state === "error") {
    document.body.dataset.state = "loading";
    stateError.classList.add("hidden");
    stateLoading.classList.remove("hidden");
  }
  return check(true);
}

refreshBtn.addEventListener("click", again);
retryBtn.addEventListener("click", again);
helpBtn.addEventListener("click", () => chrome.tabs.create({ url: chrome.runtime.getURL("help.html") }));

banner.addEventListener("click", () => {
  const open = healthPanel.classList.toggle("hidden") === false;
  banner.setAttribute("aria-expanded", String(open));
});

filterToggle.addEventListener("click", () => {
  filterBar.classList.toggle("hidden");
  if (!filterBar.classList.contains("hidden")) searchInput.focus();
});

async function start() {
  try {
    const getURL = (path) => chrome.runtime.getURL(path);
    [schemas, table] = await Promise.all([loadSchemas(getURL), loadPlaces(getURL)]);
    await render();
  } catch (err) {
    console.error("popup", err);
  }
  await check(false);
}

start();
