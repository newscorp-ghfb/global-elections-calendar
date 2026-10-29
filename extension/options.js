// The options page (P141; D4, R55): the places the feed lists, plus the saved pins, each with a
// pin button. The page never writes storage: the worker prepares the pins ({type: "PINS"}) and
// applies every edit ({type: "PIN_EDIT"}) through its one queue.
//
// Pins are drawn one way only. reconcile() reads the pin keys and draws what is stored; it runs
// after every reply, after every failed message and on every storage change, and an older read
// never overwrites a newer one. A reply's own `pins` are never drawn.
import { KEYS, loadPlaces, loadSchemas, storedFeed } from "./lib/load.js";
import { PIN_KEYS, currentPins, optionPlaces, optionRows } from "./lib/pins.js";

const $ = (id) => document.getElementById(id);
const listEl = $("country-list-container");
const searchEl = $("country-search");
const summaryEl = $("pinSummary");
const statusEl = $("pinStatus");
const failedEl = $("pinsFailed");
const noDataEl = $("noData");
const unresolvedSection = $("unresolvedSection");
const unresolvedList = $("unresolvedList");
const iconTemplate = $("pinIcon");

let table = null;       // the place table
let feedPlaces = [];    // [{id, name}] from the stored feed, read once on load
let generation = 0;     // the number of the latest reconcile() started
let working = 0;        // edits, reads and the load in flight; the page is idle at 0
const pending = new Set(); // keys of the buttons whose edit has no reply yet

const message = (err) => (err instanceof Error ? err.message : String(err));
// Text inserted into a sentence: one trailing full stop is dropped, because Chrome's own messages
// end in one and the sentence supplies its own.
const clause = (text) => String(text).replace(/[.]$/, "");

function syncState() {
  document.body.dataset.pinSync = working > 0 ? "busy" : "idle";
}

function begin() {
  working += 1;
  syncState();
}

function end() {
  working -= 1;
  syncState();
}

const placeKey = (id) => `place:${id}`;
const nameKey = (name) => `name:${name}`;

// Every button shows its own pending state: busy and disabled until its edit has a reply.
function refreshPending() {
  for (const button of document.querySelectorAll("button[data-pin-key]")) {
    if (pending.has(button.dataset.pinKey)) {
      button.disabled = true;
      button.setAttribute("aria-busy", "true");
    } else {
      button.disabled = false;
      button.removeAttribute("aria-busy");
    }
  }
}

function icon() {
  return iconTemplate.content.firstElementChild.cloneNode(true);
}

function pinButton(row) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "pin-btn" + (row.pinned ? " active" : "");
  button.dataset.pinKey = placeKey(row.id);
  button.title = row.pinned
    ? "Unpin — removes from popup-only view"
    : "Pin — popup will show only pinned countries";
  button.setAttribute("aria-label", `${row.pinned ? "Unpin" : "Pin"} ${row.name}`);
  button.setAttribute("aria-pressed", String(row.pinned));
  button.append(icon());
  button.addEventListener("click", () => edit(row.pinned ? "unpin" : "pin", row.id, button));
  return button;
}

function buildRow(row) {
  const item = document.createElement("div");
  item.className = "country-item" + (row.pinned ? " pinned" : "");
  item.dataset.placeId = row.id;
  const text = document.createElement("div");
  text.className = "country-text";
  const name = document.createElement("span");
  name.className = "country-name";
  name.textContent = row.name;
  text.append(name);
  if (row.includes.length > 0) {
    const also = document.createElement("span");
    also.className = "also-shows";
    also.textContent = `Also shows: ${row.includes.join(", ")}`;
    text.append(also);
  }
  item.append(text, pinButton(row));
  return item;
}

function buildUnresolved(name) {
  const item = document.createElement("li");
  item.className = "unresolved-item";
  const label = document.createElement("span");
  label.className = "unresolved-name";
  label.textContent = name;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "remove-btn";
  button.dataset.pinKey = nameKey(name);
  button.textContent = "Remove";
  button.setAttribute("aria-label", `Remove ${name}`);
  button.addEventListener("click", () => edit("forget", name, button));
  item.append(label, button);
  return item;
}

function applySearch() {
  const term = searchEl.value.toLowerCase();
  for (const item of listEl.children) {
    const name = item.querySelector(".country-name").textContent.toLowerCase();
    item.style.display = name.includes(term) ? "" : "none";
  }
}

function drawSummary(count) {
  if (count === 0) {
    summaryEl.textContent = "No countries pinned — popup shows all results.";
    summaryEl.classList.remove("active");
  } else {
    summaryEl.textContent = `${count} ${count === 1 ? "country" : "countries"} pinned — popup shows only these.`;
    summaryEl.classList.add("active");
  }
}

// Draws the lists for `pins`, keeping the focused button focused.
function draw(pins) {
  const focused = document.activeElement;
  const focusKey = focused && focused.dataset ? focused.dataset.pinKey : undefined;
  const { rows, unresolved } = optionRows(feedPlaces, pins, table);
  listEl.replaceChildren(...rows.map(buildRow));
  unresolvedList.replaceChildren(...unresolved.map(buildUnresolved));
  unresolvedSection.hidden = unresolved.length === 0;
  drawSummary(pins.places.length);
  applySearch();
  refreshPending();
  if (focusKey !== undefined) {
    const again = [...document.querySelectorAll("button[data-pin-key]")].find((b) => b.dataset.pinKey === focusKey);
    if (again && !again.disabled) again.focus();
  }
}

// Reads the pin keys and draws them, unless a later reconcile() has started since.
async function reconcile() {
  generation += 1;
  const mine = generation;
  begin();
  try {
    const stored = await chrome.storage.local.get(Object.values(PIN_KEYS));
    if (mine === generation) draw(currentPins(stored, table));
  } catch (err) {
    if (mine === generation) {
      statusEl.textContent = `Your saved pins could not be read: ${clause(message(err))}. Reload this page to try again.`;
    }
  } finally {
    end();
  }
}

// One edit: the button waits for the reply, then the page shows what is stored.
async function edit(op, value, button) {
  const key = button.dataset.pinKey;
  // refreshPending() disables the button and focus falls to <body>: remember to give it back
  const hadFocus = document.activeElement === button;
  pending.add(key);
  begin();
  refreshPending();
  let reply = null;
  try {
    let lost = "no usable reply";
    try {
      reply = await chrome.runtime.sendMessage({ type: "PIN_EDIT", op, value });
    } catch (err) {
      lost = clause(message(err));
    }
    if (reply && reply.ok === true) {
      statusEl.textContent = "";
    } else if (reply && reply.ok === false) {
      statusEl.textContent = `Your change could not be saved: ${clause(reply.error)}. Try again.`;
    } else {
      statusEl.textContent = `Your change could not be confirmed: ${lost}. The list shows your saved pins.`;
    }
  } finally {
    pending.delete(key);
    refreshPending();
    const shown = reconcile(); // starts before end(), so the page is never idle in between
    end();
    await shown;
    // unless the user has moved focus elsewhere meanwhile
    if (hadFocus && (document.activeElement === document.body || document.activeElement === null)) {
      const again = [...document.querySelectorAll("button[data-pin-key]")].find((b) => b.dataset.pinKey === key);
      if (again && !again.disabled) again.focus();
    }
  }
}

function pinsFailed(error) {
  failedEl.textContent = `Your pins could not be prepared: ${clause(error)}. Reload this page to try again.`;
  failedEl.hidden = false;
}

async function start() {
  begin();
  try {
    const getURL = (path) => chrome.runtime.getURL(path);
    let schemas;
    try {
      [schemas, table] = await Promise.all([loadSchemas(getURL), loadPlaces(getURL)]);
    } catch (err) {
      pinsFailed(message(err));
      return;
    }
    // The worker migrates the pins first; they are shown and edited only once it has.
    let reply = null;
    let lost = "no usable reply";
    try {
      reply = await chrome.runtime.sendMessage({ type: "PINS" });
    } catch (err) {
      lost = message(err);
    }
    if (!reply || reply.ok !== true) {
      pinsFailed(reply && typeof reply.error === "string" ? reply.error : lost);
      return;
    }
    const flag = await chrome.storage.local.get(Object.values(PIN_KEYS));
    if (flag[PIN_KEYS.migrated] !== true) {
      pinsFailed("the pins were not migrated");
      return;
    }
    const read = async () => storedFeed((await chrome.storage.local.get([KEYS.feed]))[KEYS.feed], schemas);
    let record = await read();
    if (record === null) {
      try {
        await chrome.runtime.sendMessage({ type: "CHECK" });
      } catch {
        // no data stays no data; the pins are still listed
      }
      record = await read();
    }
    noDataEl.hidden = record !== null;
    feedPlaces = optionPlaces(record, table);
    searchEl.addEventListener("input", applySearch);
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area === "local" && Object.values(PIN_KEYS).some((key) => key in changes)) reconcile();
    });
    await reconcile();
  } catch (err) {
    pinsFailed(message(err));
  } finally {
    end();
  }
}

start();
