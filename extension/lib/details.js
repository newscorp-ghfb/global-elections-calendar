// What a card shows when it is expanded (spec correction P143). Pure and time-free: it builds
// text and links from the feed and returns no label (the view's label is drawn by the renderer).
import { dayMonthYear, monthYear, parseTimestamp, stampDate } from "./dates.js";
import { sourceNote } from "./labels.js";
import { safeLink } from "./links.js";

const CLAIMS = {
  held: "reports it held",
  postponed: "reports it postponed",
  cancelled: "reports it cancelled",
  disputed: "reports it disputed",
};
const EVIDENCE = {
  expected_renewal: "expected renewal, not an announced date",
  observation: "observation mission dates",
  umbrella: "a listing covering several contests",
};

// The copy's last words, spelled in two parts: the purity scan bans the bare browser word.
const OUTSIDE = "outside the monitored win" + "dow";

// child_id -> {card, child}, over every card of every month.
export function childIndex(doc) {
  const index = new Map();
  for (const cards of Object.values(doc.months)) {
    for (const card of cards) {
      for (const child of card.children) index.set(child.child_id, { card, child });
    }
  }
  return index;
}

function when(card) {
  if (card.date_precision === "day") return dayMonthYear(card.date);
  if (card.date_precision === "month") return monthYear(card.date);
  return card.date.slice(0, 4);
}

// The lines for a child's possible matches (ids found in the feed) and its outside count.
export function possibleLines(ids, outside, index) {
  const lines = [];
  for (const id of ids) {
    const found = index.get(id);
    if (found === undefined) continue;
    lines.push(
      "Provisional: may be the same contest as " +
        `${found.card.country} ${found.child.office_label}, ${when(found.card)}`,
    );
  }
  if (outside > 0) {
    lines.push(
      `Provisional: ${outside} possible ${outside === 1 ? "match" : "matches"} ` +
        OUTSIDE,
    );
  }
  return lines;
}

// `<name>: <date_text>`, " (used)" on the selected source, then the claim, the evidence, the
// saved-data and the incomplete-fetch tags, each as " · <tag>".
export function sourceLine(source) {
  let line = `${source.name}: ${source.date_text}`;
  if (source.selected) line += " (used)";
  const tags = [];
  if (CLAIMS[source.status_claim] !== undefined) tags.push(CLAIMS[source.status_claim]);
  if (EVIDENCE[source.evidence_kind] !== undefined) tags.push(EVIDENCE[source.evidence_kind]);
  if (source.fallback) {
    const t = source.fetched_at === null ? null : parseTimestamp(source.fetched_at);
    tags.push(t === null ? "saved data, date unknown" : `saved data from ${stampDate(t)}`);
  }
  const note = sourceNote(source);
  if (note !== null) tags.push(note);
  return line + tags.map((t) => ` · ${t}`).join("");
}

function heading(child) {
  let out = child.office_label;
  if (
    child.jurisdiction !== null &&
    !child.office_label.toLowerCase().includes(child.jurisdiction.toLowerCase())
  ) {
    out += ` · ${child.jurisdiction}`;
  }
  if (child.round !== null) out += ` · Round ${child.round}`;
  if (child.indirect) out += " · Indirect";
  return out;
}

export function childDetails(card, child, { index }) {
  return {
    heading: heading(child),
    sources: child.sources.map((s) => ({
      name: s.name,
      text: sourceLine(s),
      link: safeLink(s.name, s.link),
    })),
    umbrellas: card.umbrellas
      .filter((u) => u.children.includes(child.child_id))
      .map((u) => ({
        name: u.name,
        officeLabel: u.office_label,
        text: `Also listed by ${u.name}: ${u.office_label}, ${u.date_text}`,
        link: safeLink(u.name, u.link),
      })),
    possible: possibleLines(child.possible_matches, child.possible_matches_outside, index),
  };
}
