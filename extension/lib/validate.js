// The client's validation of the two documents and the four-way format dispatch (P130). Pure.
// The schema files are the contract: schema.js reads them; this module adds the real-moment and
// real-day checks and the v1 ("legacy") checks of elections_calendar/validate.py.

import { isCivilDate, parseTimestamp } from "./dates.js";
import { schemaProblems } from "./schema.js";

export const MAX_FEED_BYTES = 4_000_000;
export const MAX_STATUS_BYTES = 1_000_000;
export const REAL = {
  timestamp: (s) => parseTimestamp(s) !== null,
  date: isCivilDate,
};

const MONTH = /^[0-9]{4}-[0-9]{2}$/;
const HASH = /^[0-9a-f]{64}$/;
const LEGACY_STATUS = ["Upcoming", "Held", "Postponed", "Cancelled", "Disputed", "Unknown"];
const LEGACY_REQUIRED = ["current_month", "errors", "generated_at", "months"];
const MAX_PROBLEM = 300;

function isObject(v) {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function same(a, b) {
  return Array.isArray(b) && a.length === b.length && a.every((x, i) => x === b[i]);
}

function text(v) {
  return typeof v === "string" ? v : "";
}

function cardProblems(card, who) {
  const problems = [];
  if (!isCivilDate(card.date)) problems.push(`${who}: date is not a real YYYY-MM-DD day`);
  if (!(typeof card.country === "string" && card.country !== "")) {
    problems.push(`${who}: country is empty`);
  }
  if (typeof card.type !== "string") problems.push(`${who}: type is not a string`);
  if (typeof card.status !== "string" || !LEGACY_STATUS.includes(card.status)) {
    problems.push(`${who}: status is not a legacy value`);
  }
  const names = [];
  const links = [];
  let wellFormed = Array.isArray(card.sources);
  for (const source of Array.isArray(card.sources) ? card.sources : []) {
    if (isObject(source) && typeof source.name === "string" && typeof source.link === "string") {
      names.push(source.name);
      links.push(source.link);
    } else {
      wellFormed = false;
    }
  }
  if (!wellFormed) problems.push(`${who}: sources is not a list of name and link strings`);
  if (!same(names, card.source_names)) problems.push(`${who}: source_names differ from sources`);
  if (!same(links, card.links)) problems.push(`${who}: links differ from sources`);
  return problems;
}

// The v1 checks as v1.0.2 reads a feed. Not ported: the producer-only rules (an unexpected
// top-level key, a time ahead of the wall clock, the size cap).
export function legacyProblems(doc) {
  if (!isObject(doc)) return ["/: not an object"];
  const problems = [];
  for (const key of LEGACY_REQUIRED) {
    if (!Object.hasOwn(doc, key)) problems.push(`/${key}: missing`);
  }
  for (const key of ["generated_at", "published_at"]) {
    if (Object.hasOwn(doc, key) && parseTimestamp(doc[key]) === null) {
      problems.push(`/${key}: not a real timestamp`);
    }
  }
  if (Object.hasOwn(doc, "republished_from_sha256")) {
    const digest = doc.republished_from_sha256;
    if (!(typeof digest === "string" && HASH.test(digest))) {
      problems.push("/republished_from_sha256: not 64 lowercase hex characters");
    }
  }
  if (Object.hasOwn(doc, "current_month")) {
    if (!(typeof doc.current_month === "string" && MONTH.test(doc.current_month))) {
      problems.push("/current_month: not YYYY-MM");
    }
  }
  if (Object.hasOwn(doc, "errors") && !Array.isArray(doc.errors)) {
    problems.push("/errors: not a list");
  }
  if (Object.hasOwn(doc, "months")) {
    if (!isObject(doc.months)) {
      problems.push("/months: not an object");
    } else {
      for (const [key, cards] of Object.entries(doc.months)) {
        if (!MONTH.test(key)) problems.push(`/months/${key.slice(0, 40)}: key is not YYYY-MM`);
        if (!(Array.isArray(cards) && cards.every(isObject))) {
          problems.push(`/months/${key.slice(0, 40)}: not a list of objects`);
        }
      }
      for (const cards of Object.values(doc.months)) {
        for (const card of Array.isArray(cards) ? cards.filter(isObject) : []) {
          problems.push(...cardProblems(card, `card ${text(card.group_id) || "?"}`));
        }
      }
    }
  }
  return problems.map((p) => p.slice(0, MAX_PROBLEM));
}

// {format, problems}: "v2" (schema_version 2 and the schema passes), "legacy" (no schema_version
// key and the legacy checks pass), "update_needed" (any other schema_version, or a 2 that fails
// the schema, while the legacy checks pass), else "invalid" (never stored or rendered).
export function feedFormat(doc, feedSchema) {
  if (!isObject(doc)) return { format: "invalid", problems: ["/: not an object"] };
  const legacy = legacyProblems(doc);
  if (!Object.hasOwn(doc, "schema_version")) {
    return { format: legacy.length === 0 ? "legacy" : "invalid", problems: legacy };
  }
  const schema = schemaProblems(doc, feedSchema, REAL);
  if (schema.length === 0) return { format: "v2", problems: [] };
  if (legacy.length === 0) return { format: "update_needed", problems: schema };
  return { format: "invalid", problems: [...schema, ...legacy] };
}

export function statusProblems(doc, statusSchema) {
  return schemaProblems(doc, statusSchema, REAL);
}
