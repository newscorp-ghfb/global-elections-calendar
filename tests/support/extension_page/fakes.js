// In-memory fakes for lib/load.js and lib/worker.js, driven from Python (tests/support/extension.py).
import { check, loadPlaces, loadSchemas } from "../lib/load.js";
import { editQueue, migratePins } from "../lib/pins.js";
import { handlers } from "../lib/worker.js";

const FEED_URL = "https://raw.githubusercontent.com/x/y/main/elections.json";
const STATUS_URL = "https://raw.githubusercontent.com/x/y/main/status.json";

function fromBase64(text) {
  return Uint8Array.from(atob(text), (c) => c.charCodeAt(0));
}

// A response is {b64} | {http: n} | {fail: true} | {hang: true}; the last of a queue repeats.
// A hung request settles only when its signal aborts: it logs `<name>:aborted` and rejects.
function scripted(spec, log) {
  const taken = { "elections.json": 0, "status.json": 0 };
  const queues = { "elections.json": spec.feed, "status.json": spec.status };
  return (url, options) => {
    const name = url.split("/").pop();
    log.push(name);
    const queue = queues[name];
    const response = queue[Math.min(taken[name]++, queue.length - 1)];
    if (response.hang) {
      return new Promise((_, reject) => {
        options?.signal?.addEventListener("abort", () => {
          log.push(`${name}:aborted`);
          reject(new DOMException("aborted", "AbortError"));
        });
      });
    }
    if (response.fail) return Promise.reject(new TypeError("Failed to fetch"));
    if (response.http !== undefined) return Promise.reject(new Error(`HTTP ${response.http}`));
    return Promise.resolve(fromBase64(response.b64));
  };
}

// An object whose every property read throws (except `then`, so awaiting it still resolves).
function hostile(message) {
  return new Proxy({}, {
    get(_, prop) {
      if (prop === "then") return undefined;
      throw new Error(message);
    },
  });
}

// spec: {feed, status, stored, now, setFails, setFailsAll, timeoutMs, schemas: bool, throw,
// reportThrows, storedThrows}. `throw` makes the feed schema an object whose reads throw that message;
// `storedThrows` makes the first `get` resolve to such an object.
// Returns {result, stored, log, sets, reported}.
export async function runCheck(spec) {
  const log = [];
  const sets = [];
  const reported = [];
  let gets = 0;
  const stored = structuredClone(spec.stored);
  let schemas = spec.schemas ? await loadSchemas((p) => chrome.runtime.getURL(p)) : null;
  if (spec.throw) schemas = { ...schemas, feed: hostile(spec.throw) };
  // A check that never ends (a missing deadline) must fail the test, not hang it.
  const watchdog = new Promise((resolve) => {
    setTimeout(() => resolve({ ok: false, error: "watchdog: the check never finished" }), 5000);
  });
  const result = await Promise.race([watchdog, check({
    feedUrl: FEED_URL,
    statusUrl: STATUS_URL,
    fetchBytes: scripted(spec, log),
    get: async (keys) => {
      gets += 1;
      if (spec.storedThrows && gets === 1) return hostile("boom");
      const out = {};
      for (const key of keys) if (key in stored) out[key] = structuredClone(stored[key]);
      return out;
    },
    set: async (items) => {
      sets.push(Object.keys(items));
      if (spec.setFailsAll) throw new Error("set failed");
      if (spec.setFails && "elections_cache_v2" in items) throw new Error(spec.setFails);
      for (const [key, value] of Object.entries(items)) stored[key] = structuredClone(value);
    },
    now: () => spec.now,
    schemas,
    timeoutMs: spec.timeoutMs,
    report: (err) => {
      reported.push(err instanceof Error ? err.message : String(err));
      if (spec.reportThrows) throw new Error("report failed");
    },
  })]);
  return { result, stored, log, sets, reported };
}

const RUN_VALUE = { ok: true, changed: true, marker: 1 };
const MIGRATE_VALUE = { ok: true, migrated: true, marker: 2 };

// spec: {call: "installed" | "startup" | "alarm" | "message", arg, due: bool, helpRejects: bool,
// runCheckRejects: bool, migrateRejects: bool}. Returns {log, result, undefinedResult, rejected}: `rejected` is the
// message the handler rejected with, or null.
// Each fake logs `name:start` when called and `name:end` when it settles. The delays shrink along
// the usual call order (openHelp longest), so a handler that does not wait for a call would show
// the next call starting before the earlier one ended. `editPin` logs `editPin:start` and
// `editPin:end` and returns {ok: true, edited: <the edit>}.
export async function runHandlers(spec) {
  const log = [];
  const later = (name, ms, value, rejects = false) => async () => {
    log.push(`${name}:start`);
    await new Promise((resolve) => setTimeout(resolve, ms));
    log.push(`${name}:end`);
    if (rejects) throw new Error(`${name} failed`);
    return value;
  };
  const h = handlers({
    openHelp: later("openHelp", 40, undefined, spec.helpRejects === true),
    migratePins: later("migratePins", 10, MIGRATE_VALUE, spec.migrateRejects === true),
    editPin: async (edit) => later("editPin", 5, { ok: true, edited: edit })(),
    ensureAlarm: later("ensureAlarm", 25),
    isDue: later("isDue", 15, spec.due),
    runCheck: later("runCheck", 5, RUN_VALUE, spec.runCheckRejects === true),
  });
  let result;
  let rejected = null;
  try {
    result = await h[spec.call](spec.arg);
  } catch (err) {
    rejected = err.message;
  }
  return {
    log,
    result: result === undefined ? null : result,
    undefinedResult: result === undefined,
    rejected,
  };
}

// A fake chrome.storage.local over `stored` (cloned): `get(keys)` and `set(items)`. `sets` logs the
// keys of every `set`; `setDelayMs` makes a `set` take that long; `setFails` holds the indexes
// (in call order, from 0) of the `set`s that reject, `setFailsAll` makes every `set` reject, with
// the message `setFailsWith`; `getFails` is a message that rejects every `get`.
function pinStorage(spec, stored, sets) {
  let calls = 0;
  const failing = new Set(spec.setFails ?? []);
  return {
    get: async (keys) => {
      if (spec.getFails) throw new Error(spec.getFails);
      const out = {};
      for (const key of keys) if (key in stored) out[key] = structuredClone(stored[key]);
      return out;
    },
    set: async (items) => {
      const index = calls;
      calls += 1;
      sets.push(Object.keys(items));
      if (spec.setDelayMs) await new Promise((resolve) => setTimeout(resolve, spec.setDelayMs));
      if (spec.setFailsAll || failing.has(index)) throw new Error(spec.setFailsWith ?? "set failed");
      for (const [key, value] of Object.entries(items)) {
        // verifyMismatch stores a different list than the one written, so the read-back differs
        stored[key] = structuredClone(spec.verifyMismatch && key === "pinned_places_v2" ? ["x:garbled"] : value);
      }
    },
  };
}

// One migration over a fake storage. spec: {stored, verifyMismatch, getFails, setFailsAll,
// setFailsWith}. Returns {result, stored, sets}.
export async function runPins(spec) {
  const sets = [];
  const stored = structuredClone(spec.stored);
  const table = await loadPlaces((p) => chrome.runtime.getURL(p));
  const { get, set } = pinStorage(spec, stored, sets);
  const result = await migratePins({ get, set, table });
  return { result, stored, sets };
}

// Every edit goes to one editQueue without waiting. spec: {stored, edits, setDelayMs, setFails:
// [index of the sets that reject], setFailsWith}. Returns {replies (in edit order), stored, sets}.
export async function runPinEdits(spec) {
  const sets = [];
  const stored = structuredClone(spec.stored);
  const table = await loadPlaces((p) => chrome.runtime.getURL(p));
  const { get, set } = pinStorage(spec, stored, sets);
  const edit = editQueue({ get, set, table });
  const replies = await Promise.all(spec.edits.map((e) => edit(e)));
  return { replies, stored, sets };
}
