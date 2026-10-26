// In-memory fakes for lib/load.js and lib/worker.js, driven from Python (tests/support/extension.py).
import { check, loadSchemas } from "../lib/load.js";
import { handlers } from "../lib/worker.js";

const FEED_URL = "https://raw.githubusercontent.com/x/y/main/elections.json";
const STATUS_URL = "https://raw.githubusercontent.com/x/y/main/status.json";

function fromBase64(text) {
  return Uint8Array.from(atob(text), (c) => c.charCodeAt(0));
}

// A response is {b64} | {http: n} | {fail: true} | {hang: true}; the last of a queue repeats.
function scripted(spec, log) {
  const taken = { "elections.json": 0, "status.json": 0 };
  const queues = { "elections.json": spec.feed, "status.json": spec.status };
  return (url) => {
    const name = url.split("/").pop();
    log.push(name);
    const queue = queues[name];
    const response = queue[Math.min(taken[name]++, queue.length - 1)];
    if (response.hang) return new Promise(() => {});
    if (response.fail) return Promise.reject(new TypeError("Failed to fetch"));
    if (response.http !== undefined) return Promise.reject(new Error(`HTTP ${response.http}`));
    return Promise.resolve(fromBase64(response.b64));
  };
}

// spec: {feed, status, stored, now, setFails, timeoutMs, schemas: bool}.
// Returns {result, stored, log, sets}.
export async function runCheck(spec) {
  const log = [];
  const sets = [];
  const stored = structuredClone(spec.stored);
  const schemas = spec.schemas ? await loadSchemas((p) => chrome.runtime.getURL(p)) : null;
  // A check that never ends (a missing deadline) must fail the test, not hang it.
  const watchdog = new Promise((resolve) => {
    setTimeout(() => resolve({ ok: false, error: "watchdog: the check never finished" }), 5000);
  });
  const result = await Promise.race([watchdog, check({
    feedUrl: FEED_URL,
    statusUrl: STATUS_URL,
    fetchBytes: scripted(spec, log),
    get: async (keys) => {
      const out = {};
      for (const key of keys) if (key in stored) out[key] = structuredClone(stored[key]);
      return out;
    },
    set: async (items) => {
      sets.push(Object.keys(items));
      if (spec.setFails && "elections_cache_v2" in items) throw new Error(spec.setFails);
      for (const [key, value] of Object.entries(items)) stored[key] = structuredClone(value);
    },
    now: () => spec.now,
    schemas,
    timeoutMs: spec.timeoutMs,
  })]);
  return { result, stored, log, sets };
}

const RUN_VALUE = { ok: true, changed: true, marker: 1 };

// spec: {call: "installed" | "startup" | "alarm" | "message", arg, due: bool}.
// Each fake settles on a later turn before it logs, so the log shows whether calls wait.
export async function runHandlers(spec) {
  const log = [];
  const later = (name, value) => async () => {
    await new Promise((resolve) => setTimeout(resolve, 5));
    log.push(name);
    return value;
  };
  const h = handlers({
    runCheck: later("runCheck", RUN_VALUE),
    ensureAlarm: later("ensureAlarm"),
    isDue: later("isDue", spec.due),
    openHelp: later("openHelp"),
  });
  const result = await h[spec.call](spec.arg);
  return { log, result: result === undefined ? null : result, undefinedResult: result === undefined };
}
