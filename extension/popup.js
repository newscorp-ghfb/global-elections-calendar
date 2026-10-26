import { KEYS, loadSchemas, storedFeed } from "./lib/load.js";
import { renderLegacy } from "./lib/legacy.js";

const PINNED_COUNTRIES_KEY = "pinned_countries";

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

let schemas = null;

function showError(message) {
  errorMsgEl.textContent = `Could not load data: ${message}`;
  stateLoading.classList.add("hidden");
  stateError.classList.remove("hidden");
  document.body.dataset.state = "error";
}

// Render the cached feed, if the stored record is valid. True when something was drawn.
async function render() {
  const stored = await chrome.storage.local.get([KEYS.feed, PINNED_COUNTRIES_KEY]);
  const record = storedFeed(stored[KEYS.feed], schemas);
  if (record === null) return false;
  const pinned = Array.isArray(stored[PINNED_COUNTRIES_KEY]) ? stored[PINNED_COUNTRIES_KEY] : [];
  renderLegacy(record.data, { pinned });
  document.body.dataset.state = "ready";
  return true;
}

async function check(force) {
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
    refreshBtn.classList.remove("spinning");
    document.body.dataset.checking = "false";
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

filterToggle.addEventListener("click", () => {
  filterBar.classList.toggle("hidden");
  if (!filterBar.classList.contains("hidden")) searchInput.focus();
});

async function start() {
  try {
    schemas = await loadSchemas((path) => chrome.runtime.getURL(path));
    await render();
  } catch (err) {
    console.error("popup", err);
  }
  await check(false);
}

start();
