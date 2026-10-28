// One pipeline for the tabs, the filters and the counters (spec correction P135, P138).
// Pure: the civil date and the instant are passed in; civil dates are compared as strings.
import { cardLabel, childLabel } from "./labels.js";

// The label kinds that belong to each tab. Every kind is also under "all".
export const TAB_KINDS = {
  upcoming: [
    "scheduled", "today", "day_unconfirmed", "expected",
    "possibly_postponed", "possibly_cancelled", "postponed",
  ],
  past: ["held", "past", "past_expected"],
};

const LEVELS = {
  all: () => true,
  national: (level) => level !== "subnational", // national and unclassified
  subnational: (level) => level !== "national", // subnational and unclassified
};

// The tabs a child with this label is under. A disputed child follows its card's end date.
export function tabsOf(label, card, today) {
  const tabs = new Set(["all"]);
  if (label.kind === "disputed") {
    tabs.add(card.end_date < today ? "past" : "upcoming");
    return tabs;
  }
  for (const tab of Object.keys(TAB_KINDS)) {
    if (TAB_KINDS[tab].includes(label.kind)) tabs.add(tab);
  }
  return tabs;
}

// P138, option B: a month shows every card whose dates overlap it. Civil dates compare as
// strings, so "YYYY-MM-01" and "YYYY-MM-31" bound every month, short ones too.
function overlaps(card, month) {
  return card.date <= `${month}-31` && card.end_date >= `${month}-01`;
}

function searchText(card, child, label) {
  return [
    card.country,
    child.office_label,
    child.jurisdiction ?? "",
    ...child.sources.map((s) => s.name),
    label.text,
  ].join(" ").toLowerCase();
}

// `pins` is a (placeId) => boolean (lib/pins.js `pinMatcher`).
export function view(doc, { month, tab, level, query, pins, today, now }) {
  const needle = query.trim().toLowerCase();
  const cards = [];
  const kept = new Map(); // child_id -> {aggregate, held}, so a child is counted once
  for (const bucket of Object.keys(doc.months).sort()) {
    for (const card of doc.months[bucket]) {
      if (!overlaps(card, month)) continue;
      if (!pins(card.place_id)) continue;
      if (!LEVELS[level](card.level)) continue;
      const children = [];
      for (const child of card.children) {
        const label = childLabel(card, child, { today, now });
        if (!tabsOf(label, card, today).has(tab)) continue;
        if (needle !== "" && !searchText(card, child, label).includes(needle)) continue;
        children.push({ child, label });
      }
      if (children.length === 0) continue;
      for (const { child, label } of children) {
        if (!kept.has(child.child_id)) {
          kept.set(child.child_id, {
            aggregate: child.aggregate === true,
            held: label.kind === "held",
          });
        }
      }
      const total = card.children.length;
      cards.push({
        card,
        children,
        total,
        label: cardLabel(card, children.map((c) => c.label)),
        match: children.length < total ? `${children.length} matching of ${total}` : "",
      });
    }
  }
  const all = [...kept.values()];
  return {
    cards,
    records: all.length,
    groupings: all.filter((k) => k.aggregate).length,
    held: all.filter((k) => k.held).length,
  };
}

function plural(n, word) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

export function recordText(records, groupings) {
  const base = plural(records, "election record");
  return groupings > 0 ? `${base} (incl. ${plural(groupings, "grouping")})` : base;
}
