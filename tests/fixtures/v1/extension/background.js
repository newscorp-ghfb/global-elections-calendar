"use strict";

const DATA_URL   = "https://raw.githubusercontent.com/newscorp-ghfb/global-elections-calendar/main/elections.json";
const CACHE_KEY  = "elections_cache";
const ALARM_NAME = "elections-refresh";

async function fetchAndCache() {
  const resp = await fetch(DATA_URL, { cache: "no-store" });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
  const data = await resp.json();
  await chrome.storage.local.set({ [CACHE_KEY]: { ts: Date.now(), data } });
  return data;
}

chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === "install") {
    chrome.tabs.create({ url: chrome.runtime.getURL("help.html") });
  }
  fetchAndCache().catch(console.error);
  chrome.alarms.create(ALARM_NAME, { periodInMinutes: 60 });
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_NAME) fetchAndCache().catch(console.error);
});

// Popup/options pages send {type:"FETCH_DATA"} to trigger a fresh fetch.
// Background is not subject to CORS for host_permissions URLs.
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type !== "FETCH_DATA") return false;
  fetchAndCache()
    .then(data => sendResponse({ ok: true, data }))
    .catch(err  => sendResponse({ ok: false, error: err.message }));
  return true; // keep message channel open for async response
});
