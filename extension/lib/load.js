// One ordered, linked check of elections.json and status.json (P131), written in a single set.
// Not pure: it fetches the schema files and digests with crypto.subtle. Everything else it needs
// (fetching the documents, storage, the clock) comes in through `deps`.

import { accepts, isLinked, orderKey, pickStatus } from "./order.js";
import { MAX_FEED_BYTES, MAX_STATUS_BYTES, feedFormat, statusProblems } from "./validate.js";

export const KEYS = {
  feed: "elections_cache_v2",
  status: "status_cache",
  check: "check_state_v2",
};
export const CHECK_INTERVAL_MS = 1_800_000;
export const REQUEST_TIMEOUT_MS = 25_000; // below Chrome's 30 s limit for a worker's fetch()
export const UNEXPECTED = "the check failed unexpectedly";
const MESSAGE_MAX = 200;

const HASH = /^[0-9a-f]{64}$/;
const HTTP = /^HTTP [0-9]+$/;
const NO_SCHEMAS = "the extension's schemas could not be read";

function isObject(v) {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isHash(v) {
  return typeof v === "string" && HASH.test(v);
}

// False only when the last successful check is less than CHECK_INTERVAL_MS old.
export function due(checkState, nowMs) {
  const okAt = isObject(checkState) ? checkState.ok_at : undefined;
  if (typeof okAt !== "number" || !Number.isFinite(okAt)) return true;
  const age = nowMs - okAt;
  return !(age >= 0 && age < CHECK_INTERVAL_MS);
}

export async function sha256Hex(bytes) {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return Array.from(digest, (b) => b.toString(16).padStart(2, "0")).join("");
}

function hasSchemas(schemas) {
  return isObject(schemas) && isObject(schemas.feed) && isObject(schemas.status);
}

// The record when it is a valid stored feed (B3), else null.
export function storedFeed(record, schemas) {
  if (!isObject(record) || !hasSchemas(schemas)) return null;
  const { format } = feedFormat(record.data, schemas.feed);
  if (format === "invalid" || format !== record.format) return null;
  if (orderKey(record.data) !== record.order_key) return null;
  if (!isHash(record.sha256)) return null;
  if (typeof record.received_at !== "number" || !Number.isFinite(record.received_at)) return null;
  return record;
}

export function storedStatus(record, schemas) {
  if (!isObject(record) || !hasSchemas(schemas)) return null;
  if (statusProblems(record.data, schemas.status).length > 0) return null;
  return isHash(record.sha256) ? record : null;
}

export async function loadSchemas(getURL) {
  const read = async (name) => {
    const response = await fetch(getURL(`schemas/${name}`));
    if (!response.ok) throw new Error(`HTTP ${response.status} for ${name}`);
    return response.json();
  };
  const [feed, status] = await Promise.all([
    read("feed-v2.schema.json"),
    read("status-v1.schema.json"),
  ]);
  return { feed, status };
}

// The place table (extension/places.json): {names, places}. Throws when it cannot be read.
export async function loadPlaces(getURL) {
  const response = await fetch(getURL("places.json"));
  if (!response.ok) throw new Error(`HTTP ${response.status} for places.json`);
  const table = await response.json();
  if (!isObject(table) || !isObject(table.names) || !isObject(table.places)) {
    throw new Error("places.json is not a place table");
  }
  return table;
}

class Deadline extends Error {}

export class OverLimit extends Error {
  constructor(limit) {
    super(`over the limit of ${limit} bytes`);
    this.limit = limit;
  }
}

// The body of `response` as bytes, read in chunks: past `limit` bytes the stream is cancelled and
// OverLimit thrown, so an endless body is never buffered whole.
export async function readLimited(response, limit) {
  if (response.body === null) return new Uint8Array(0);
  const reader = response.body.getReader();
  const chunks = [];
  let total = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      total += value.length;
      if (total > limit) throw new OverLimit(limit);
      chunks.push(value);
    }
  } catch (err) {
    await reader.cancel().catch(() => {}); // a stream that cannot be cancelled is dropped anyway
    throw err;
  }
  const out = new Uint8Array(total);
  let at = 0;
  for (const chunk of chunks) {
    out.set(chunk, at);
    at += chunk.length;
  }
  return out;
}

// The real request: `fetchImpl` is the global fetch in the worker, a fake in tests.
export async function fetchLimited(fetchImpl, url, { signal, limit }) {
  const response = await fetchImpl(url, { cache: "no-store", signal });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return readLimited(response, limit);
}

// Runs `start(signal)` for at most `ms`; the deadline aborts the request, and the request's own
// late rejection is handled here, so it is never an unhandled rejection.
function withDeadline(start, ms) {
  const controller = new AbortController();
  const request = (async () => start(controller.signal))();
  request.catch(() => {});
  let timer;
  const deadline = new Promise((_, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      reject(new Deadline("no response in time"));
    }, ms);
  });
  return Promise.race([request, deadline]).finally(() => clearTimeout(timer));
}

// {data, sha256} or {error}: the error is the text after "<name>: ".
async function fetchDocument(deps, url, limit) {
  let bytes;
  try {
    bytes = await withDeadline((signal) => deps.fetchBytes(url, { signal, limit }), deps.timeoutMs);
  } catch (err) {
    if (err instanceof Deadline) return { error: "no response in time" };
    if (err instanceof OverLimit) return { error: err.message };
    const message = err instanceof Error ? err.message : "";
    return { error: HTTP.test(message) ? message : "the request failed" };
  }
  if (bytes.length > limit) return { error: `over the limit of ${limit} bytes` };
  let data;
  try {
    data = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch {
    return { error: "not UTF-8 JSON" };
  }
  try {
    return { data, sha256: await sha256Hex(bytes) };
  } catch {
    return { error: "the response could not be checked" };
  }
}

// {record} or {error: "elections.json: ..."}.
async function fetchFeed(deps, t) {
  const got = await fetchDocument(deps, deps.feedUrl, MAX_FEED_BYTES);
  if (got.error !== undefined) return { error: `elections.json: ${got.error}` };
  const { format, problems } = feedFormat(got.data, deps.schemas.feed);
  if (format === "invalid") return { error: `elections.json: unreadable feed: ${problems[0]}` };
  const record = {
    data: got.data,
    sha256: got.sha256,
    order_key: orderKey(got.data),
    format,
    received_at: t,
  };
  return { record };
}

// A valid status record, or null: any failure means "no status".
async function fetchStatus(deps, t) {
  const got = await fetchDocument(deps, deps.statusUrl, MAX_STATUS_BYTES);
  if (got.error !== undefined) return null;
  if (statusProblems(got.data, deps.schemas.status).length > 0) return null;
  return { data: got.data, sha256: got.sha256, received_at: t };
}

// Records a failed check, keeping the last good time. Never throws: a failure that cannot be
// saved is still returned.
async function fail(deps, stored, t, error) {
  try {
    const previous = stored[KEYS.check];
    const okAt =
      isObject(previous) && typeof previous.ok_at === "number" && Number.isFinite(previous.ok_at)
        ? previous.ok_at
        : null;
    await deps.set({ [KEYS.check]: { ok_at: okAt, failed_at: t, error } });
  } catch {
    // the failure is reported either way
  }
  return { ok: false, error };
}

// The final boundary (P147). The first read's result may be what failed, so the check state is
// read again; when that read or the write fails, nothing is written.
async function unexpected(deps, t, err) {
  const error = `${UNEXPECTED}: ${bounded(errorText(err))}`;
  try {
    deps.report?.(err);
  } catch {
    // a failing report must not escape either
  }
  if (t === null) return { ok: false, error };
  let again;
  try {
    again = await deps.get([KEYS.check]);
  } catch {
    return { ok: false, error };
  }
  return fail(deps, again, t, error);
}

function bounded(text) {
  return text.length > MESSAGE_MAX ? `${text.slice(0, MESSAGE_MAX)}…` : text;
}

// {ok: true, changed} or {ok: false, error}. Never rejects.
export async function check(deps) {
  let t = null;
  try {
    t = deps.now();
    return await checkOnce(deps, t);
  } catch (err) {
    return unexpected(deps, t, err);
  }
}

async function checkOnce(deps, t) {
  let stored;
  try {
    stored = await deps.get([KEYS.feed, KEYS.status, KEYS.check]);
  } catch (err) {
    return { ok: false, error: `could not read the stored data: ${errorText(err)}` };
  }
  if (!hasSchemas(deps.schemas)) return fail(deps, stored, t, NO_SCHEMAS);

  const cached = storedFeed(stored[KEYS.feed], deps.schemas);
  const cachedStatus = storedStatus(stored[KEYS.status], deps.schemas);

  const first = await fetchFeed(deps, t);
  if (first.error !== undefined) return fail(deps, stored, t, first.error);
  let best = accepts(cached?.order_key ?? null, first.record.order_key, t) ? first.record : cached;
  const received = [];
  const status = await fetchStatus(deps, t);
  if (status !== null) received.push(status);

  if (status !== null && !isLinked(best.sha256, status.data)) {
    const again = await fetchFeed(deps, t);
    if (again.error === undefined && accepts(best.order_key, again.record.order_key, t)) {
      best = again.record;
    }
    const second = await fetchStatus(deps, t);
    if (second !== null) received.push(second);
  }

  const chosen = pickStatus(cachedStatus, received, best.sha256);
  const feedChanged = best.sha256 !== cached?.sha256;
  const statusChanged = chosen?.sha256 !== cachedStatus?.sha256;
  const items = {};
  if (feedChanged) items[KEYS.feed] = best;
  if (statusChanged) items[KEYS.status] = chosen;
  items[KEYS.check] = { ok_at: t, failed_at: null, error: null };
  try {
    await deps.set(items);
  } catch (err) {
    return fail(deps, stored, t, `could not save the new data: ${errorText(err)}`);
  }
  return { ok: true, changed: feedChanged || statusChanged };
}

function errorText(err) {
  try {
    return String(err instanceof Error ? err.message : err);
  } catch {
    return "unknown error";
  }
}
