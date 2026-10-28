import { KEYS, REQUEST_TIMEOUT_MS, check, due, fetchLimited, loadPlaces, loadSchemas } from "./lib/load.js";
import { editQueue, exclusive, migratePins } from "./lib/pins.js";
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

// The place table is loaded once per worker life, like the schemas; a failed read is not
// remembered.
let tableLoading = null;
function placeTable() {
  if (tableLoading === null) {
    tableLoading = loadPlaces((path) => chrome.runtime.getURL(path)).catch((err) => {
      tableLoading = null;
      throw err;
    });
  }
  return tableLoading;
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

// Only the worker writes the pin keys (P140). The migration and every edit go through one queue,
// so they never overlap; a second migration request joins the one that is running.
const pinStore = {
  get: (keys) => chrome.storage.local.get(keys),
  set: (items) => chrome.storage.local.set(items),
};
const pinQueue = exclusive();

let migrating = null;
function runMigration() {
  if (migrating === null) {
    migrating = (async () => {
      let table;
      try {
        table = await placeTable();
      } catch (err) {
        return { ok: false, error: `the pins could not be migrated: ${err instanceof Error ? err.message : String(err)}` };
      }
      return pinQueue(() => migratePins({ ...pinStore, table }));
    })().finally(() => {
      migrating = null;
    });
  }
  return migrating;
}

let editor = null;
async function editPin(edit) {
  try {
    const table = await placeTable();
    editor ??= editQueue({ ...pinStore, table, run: pinQueue });
  } catch (err) {
    return { ok: false, error: `could not read the pins: ${err instanceof Error ? err.message : String(err)}` };
  }
  return editor(edit);
}

const handle = handlers({ runCheck, ensureAlarm, isDue, openHelp, migratePins: runMigration, editPin });

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
