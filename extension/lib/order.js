// Publication order and status selection (P132). Pure: the clock is always passed in.

import { parseTimestamp } from "./dates.js";

export const WATERMARK_AHEAD_MS = 86_400_000;

function isObject(v) {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

// The ISO string of a valid published_at, else of a valid generated_at, else null.
export function orderKey(doc) {
  if (!isObject(doc)) return null;
  for (const name of ["published_at", "generated_at"]) {
    if (parseTimestamp(doc[name]) !== null) return doc[name];
  }
  return null;
}

// Whether an incoming feed replaces the cached one. A missing or invalid incoming key never
// replaces a cached feed; an equal key is the same publication; a cached key more than one day
// ahead of `nowMs` has stopped counting.
export function accepts(cachedKey, incomingKey, nowMs) {
  const cached = cachedKey === null ? null : parseTimestamp(cachedKey);
  if (cached === null) return true;
  const incoming = incomingKey === null ? null : parseTimestamp(incomingKey);
  if (incoming === null) return false;
  if (cached > nowMs + WATERMARK_AHEAD_MS) return true;
  return incoming > cached;
}

// `status` is the parsed status JSON (not a stored record).
export function isLinked(sha256, status) {
  return status !== null && status.serving_feed_sha256 === sha256;
}

function attemptMs(record) {
  const ms = parseTimestamp(record.data.attempt_at);
  return ms === null ? -Infinity : ms;
}

function failed(record) {
  return record.data.outcome === "validation_failed";
}

// The status record to keep: the cached one (a record or null) or one of `received`, for the feed
// whose digest is `sha256`. Candidates that describe the feed win over the rest; the latest
// attempt_at wins; on a tie a validation_failed outcome wins, then the earlier candidate (the
// cached one first), so an identical status is the cached object itself.
export function pickStatus(cached, received, sha256) {
  const all = cached === null ? [...received] : [cached, ...received];
  const describing = all.filter((c) => isLinked(sha256, c.data));
  const pool = describing.length > 0 ? describing : all;
  let best = null;
  for (const candidate of pool) {
    if (best === null) {
      best = candidate;
      continue;
    }
    const a = attemptMs(candidate);
    const b = attemptMs(best);
    if (a > b || (a === b && failed(candidate) && !failed(best))) best = candidate;
  }
  if (best !== null && cached !== null && best.sha256 === cached.sha256) return cached;
  return best;
}
