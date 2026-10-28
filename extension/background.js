import { KEYS, REQUEST_TIMEOUT_MS, check, due, fetchLimited, loadSchemas } from "./lib/load.js";
import { ALARM_NAME, handlers } from "./lib/worker.js";

const DATA_URL = "https://raw.githubusercontent.com/newscorp-ghfb/global-elections-calendar/main/elections.json";
const STATUS_URL = new URL("status.json", DATA_URL).href;

// The schema files are read once per worker life; a failed read is not remembered, so the next
// check tries again.
let schemasLoading = null;
function schemas() {
  if (schemasLoading === null) {
    schemasLoading = loadSchemas((path) => chrome.runtime.getURL(path)).catch((err) => {
      schemasLoading = null;
      throw err;
    });
  }
  return schemasLoading;
}

// The body is read in chunks and cut off at `limit` bytes, and `signal` aborts the request.
const fetchBytes = (url, options) => fetchLimited(fetch, url, options);

async function checkOnce() {
  let loaded = null;
  try {
    loaded = await schemas();
  } catch (err) {
    console.error("schemas", err);
  }
  return check({
    feedUrl: DATA_URL,
    statusUrl: STATUS_URL,
    fetchBytes,
    report: console.error,
    get: (keys) => chrome.storage.local.get(keys),
    set: (items) => chrome.storage.local.set(items),
    now: () => Date.now(),
    schemas: loaded,
    timeoutMs: REQUEST_TIMEOUT_MS,
  });
}

// One check at a time: a second request joins the running one. A failed check releases it too.
let running = null;
function runCheck() {
  if (running === null) {
    running = checkOnce().finally(() => {
      running = null;
    });
  }
  return running;
}

async function ensureAlarm() {
  if (!(await chrome.alarms.get(ALARM_NAME))) {
    await chrome.alarms.create(ALARM_NAME, { periodInMinutes: 60 });
  }
}

async function isDue() {
  const stored = await chrome.storage.local.get(KEYS.check);
  return due(stored[KEYS.check], Date.now());
}

async function openHelp() {
  await chrome.tabs.create({ url: chrome.runtime.getURL("help.html") });
}

const handle = handlers({ runCheck, ensureAlarm, isDue, openHelp });

chrome.runtime.onInstalled.addListener((details) => {
  handle.installed(details).catch(console.error);
});

chrome.runtime.onStartup.addListener(() => {
  handle.startup().catch(console.error);
});

chrome.alarms.onAlarm.addListener((alarm) => {
  handle.alarm(alarm).catch(console.error);
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  const reply = handle.message(msg);
  if (reply === undefined) return false;
  reply.then(sendResponse, (err) => {
    sendResponse({ ok: false, error: err instanceof Error ? err.message : String(err) });
  });
  return true; // the reply is asynchronous
});
