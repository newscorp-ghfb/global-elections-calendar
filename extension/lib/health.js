// The summary banner, the health panel and the footer's words (P133). Pure: the clock is always
// passed in, and every function returns plain data for the popup to put on the page as text.

import { parseTimestamp, stamp, stampDate } from "./dates.js";

export const STALE_MS = 129_600_000; // 36 h
export const AHEAD_MS = 600_000; // 10 min
export const AS_OF_GAP_MS = 86_400_000; // 24 h

const HOUR_MS = 3_600_000;
export const NO_HEALTH = "Source health isn't available for this data";

function plural(n, one, many) {
  return `${n} ${n === 1 ? one : many}`;
}

function isNumber(v) {
  return typeof v === "number" && Number.isFinite(v);
}

// Each error or warning reason of a source as {reason, level, until, acknowledged, ended}.
// `until` is the end of the matching acknowledgement (ms), or null. An acknowledgement matches one
// reason on code, stage, year and page, and is used up by it. In-effect ones (`now < until`) are
// matched first; ended ones are then matched against the reasons still unmatched, and such a reason
// counts at its own level (`ended`, not `acknowledged`). Info reasons are left out.
function classify(reasons, acknowledgements, now) {
  const unused = acknowledgements.map((a) => ({ ack: a, until: parseTimestamp(a.until) }));
  const same = (a, reason) =>
    a.code === reason.code &&
    a.stage === reason.stage &&
    a.year === reason.year &&
    a.page === reason.page;
  const found = [];
  for (const reason of reasons) {
    if (reason.level !== "error" && reason.level !== "warning") continue;
    found.push({ reason, level: reason.level, until: null, acknowledged: false, ended: false });
  }
  const match = (entry, inEffect) => {
    const at = unused.findIndex(
      (u) => u.until !== null && (now < u.until) === inEffect && same(u.ack, entry.reason),
    );
    if (at === -1) return;
    entry.until = unused[at].until;
    entry.acknowledged = inEffect;
    entry.ended = !inEffect;
    unused.splice(at, 1);
  };
  for (const entry of found) match(entry, true);
  for (const entry of found) if (!entry.acknowledged) match(entry, false);
  return found;
}

// The error and warning reasons of a v2 feed, by source name (the run's as "Run"), sorted
// into errors, warnings and acknowledged ones. A reason whose acknowledgement has ended is in
// errors or warnings; `now` (ms) says which acknowledgements are in effect.
export function issues(doc, now) {
  const out = { errors: [], warnings: [], acknowledged: [] };
  const take = (source, reasons, acknowledgements) => {
    for (const c of classify(reasons, acknowledgements, now)) {
      const issue = { source, code: c.reason.code, text: c.reason.text, until: c.until };
      if (c.acknowledged) out.acknowledged.push(issue);
      else if (c.level === "error") out.errors.push(issue);
      else out.warnings.push(issue);
    }
  };
  for (const entry of doc.source_health) take(entry.name, entry.reasons, entry.acknowledged);
  take("Run", doc.run.reasons, []);
  return out;
}

function counts(found) {
  const parts = [];
  if (found.errors.length > 0) parts.push(plural(found.errors.length, "error", "errors"));
  if (found.warnings.length > 0) parts.push(plural(found.warnings.length, "warning", "warnings"));
  if (found.acknowledged.length > 0) parts.push(`${found.acknowledged.length} acknowledged`);
  return parts.join(" · ");
}

// The first true row of P133's nine. `status` is the parsed status (or null) and
// `linked` says it describes this feed.
export function bannerState({ format, doc, status, linked, now }) {
  const found = format === "v2" ? issues(doc, now) : null;
  const tally = found === null ? "" : counts(found);
  const generated = parseTimestamp(doc.generated_at);
  const age = generated === null ? 0 : now - generated;
  if (age > STALE_MS) {
    const hours = Math.floor(age / HOUR_MS);
    return {
      level: "red",
      text: `Data is ${hours} hours old — the daily update hasn't arrived`,
      counts: tally,
    };
  }
  if (linked && status !== null && status.outcome === "validation_failed") {
    return {
      level: "red",
      text: "The latest update failed its checks — showing the last good data",
      counts: tally,
    };
  }
  if (found !== null && found.errors.length > 0) {
    return {
      level: "red",
      text: plural(found.errors.length, "source error", "source errors"),
      counts: tally,
    };
  }
  if (format === "update_needed") {
    return {
      level: "amber",
      text: "This data is newer than this extension — update the extension",
      counts: tally,
    };
  }
  if (!linked) {
    return {
      level: "amber",
      text: "Current health can't be confirmed for this data",
      counts: tally,
    };
  }
  if (format === "legacy") {
    return { level: "amber", text: NO_HEALTH, counts: tally };
  }
  if (found.warnings.length > 0) {
    return {
      level: "amber",
      text: plural(found.warnings.length, "warning", "warnings"),
      counts: tally,
    };
  }
  if (found.acknowledged.length > 0) {
    const first = found.acknowledged[0];
    const what = `${first.source} ${first.code.replaceAll("_", " ")}`;
    return {
      level: "grey",
      text: `${plural(found.acknowledged.length, "acknowledged issue", "acknowledged issues")}: ${what}`,
      counts: tally,
    };
  }
  return { level: "ok", text: "All sources OK", counts: tally };
}

// What the footer says about the data and about the last check. `check` is the stored
// check state; anything that is not a finite time counts as absent.
export function footerState({ doc, check, now }) {
  const generated = parseTimestamp(doc.generated_at);
  let data = generated === null ? "Data as of an unknown time" : `Data as of ${stamp(generated)}`;
  const asOf = parseTimestamp(doc.data_as_of);
  if (generated !== null && asOf !== null && generated - asOf > AS_OF_GAP_MS) {
    data += ` · oldest source data ${stamp(asOf)}`;
  }
  if (generated !== null && generated - now > AHEAD_MS) {
    data += " (ahead of this computer's clock)";
  }
  const state = typeof check === "object" && check !== null ? check : {};
  const okAt = isNumber(state.ok_at) ? state.ok_at : null;
  const failedAt = isNumber(state.failed_at) ? state.failed_at : null;
  const why = typeof state.error === "string" && state.error !== "" ? `: ${state.error}` : "";
  let checked = "Not checked yet";
  if (okAt !== null) {
    checked = `Checked ${stamp(okAt)}`;
    if (failedAt !== null && failedAt > okAt) {
      checked += ` · couldn't check at ${stamp(failedAt)}${why}`;
    }
  } else if (failedAt !== null) {
    checked = `Couldn't check at ${stamp(failedAt)}${why}`;
  }
  return { data, checked };
}

function worst(levels) {
  if (levels.includes("error")) return "error";
  return levels.includes("warning") ? "warning" : "ok";
}

// One row per source of a v2 feed (and one for the run when it has reasons), led by the
// latest attempt when the status describes this feed. Legacy and update_needed data have no rows.
export function panelRows({ format, doc, status, linked, now }) {
  if (format !== "v2") return [];
  const rows = [];
  if (linked && status !== null) {
    rows.push({
      source: "latest",
      name: "Latest update",
      severity: status.severity,
      lines: [`Latest attempt ${stamp(parseTimestamp(status.attempt_at))}: ${status.outcome.replaceAll("_", " ")}`],
    });
  }
  const lines = (reasons, acknowledgements) => {
    const marked = new Map(classify(reasons, acknowledgements, now).map((c) => [c.reason, c]));
    return reasons.map((reason) => {
      const c = marked.get(reason);
      if (c === undefined || c.until === null) return reason.text;
      const word = c.ended ? "acknowledgement ended" : "acknowledged until";
      return `${reason.text} (${word} ${stampDate(c.until)})`;
    });
  };
  for (const entry of doc.source_health) {
    rows.push({
      source: entry.source,
      name: entry.name,
      severity: entry.severity,
      lines: lines(entry.reasons, entry.acknowledged),
    });
  }
  if (doc.run.reasons.length > 0) {
    rows.push({
      source: "run",
      name: "Run",
      severity: worst(doc.run.reasons.map((r) => r.level)),
      lines: lines(doc.run.reasons, []),
    });
  }
  return rows;
}
