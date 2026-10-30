// The attention and undated section's text and rows (spec correction P144). Pure and time-free:
// it builds counts, copy and row data from the feed; render.js draws them.
import { MONTHS_SHORT } from "./dates.js";
import { possibleLines } from "./details.js";
import { safeLink, sourceName } from "./links.js";

export const ATTENTION_PAGE = 200;
const LABEL_TEXT_CHARS = 80;

function plural(n, word) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

// "Sep–Jan" for the first and last month listed, "Oct" for one, "" for none.
function monthsText(months) {
  if (months.length === 0) return "";
  const name = (m) => MONTHS_SHORT[Number(m.slice(5, 7)) - 1];
  const first = name(months[0]);
  const last = name(months[months.length - 1]);
  return months.length === 1 ? first : `${first}–${last}`;
}

function inParens(...parts) {
  const kept = parts.filter((p) => p !== "");
  return kept.length === 0 ? "" : ` (${kept.join(", ")})`;
}

// The toggle's text. `k` is the matched count with a search, else null; `included` is A, `total`
// is N (A plus the cut ones).
export function attentionTitle({ k, included, total, months }) {
  const span = monthsText(months);
  if (k === null) return `${plural(total, "item")} across the monitored window${inParens(span)}`;
  if (total === included) {
    return `${k} of ${plural(total, "item")} across the monitored window${inParens(span)}`;
  }
  return `${k} of the ${plural(included, "item")} in this data match${inParens(`${total} in total`, span)}`;
}

// "" when nothing was cut.
export function truncationNote({ included, total }) {
  if (total === included) return "";
  return (
    `This data includes ${included} of the ${total} items. The other ${total - included} are in ` +
    'attention_full.json, in the "generation" artifact of the GitHub Actions run that published ' +
    "it (kept 14 days). Searches here do not cover them."
  );
}

// "" when everything is shown.
export function shownLine(shown, of) {
  return shown === of ? "" : `Showing ${shown} of ${of}`;
}

function cut(text) {
  return Array.from(text).slice(0, LABEL_TEXT_CHARS).join("");
}

// The items to list: the title, the note and a row per item matching the search (all of them
// without one). `index` is details.childIndex(doc). Only the search box filters them. With
// `withRows: false` it only counts the matches (rows is null, `index` is not read): the same
// predicate picks the items, so the title cannot drift from the rows.
export function attentionView(doc, { query, index, withRows = true }) {
  const items = doc.attention_items;
  const included = items.length;
  const total = included + doc.attention_truncated;
  const listings = new Map(doc.undated.map((u) => [u.undated_id, u]));
  const needle = query.trim().toLowerCase();
  const matches = (item, listing, source) => {
    if (needle === "") return true;
    const fields = [item.text, source];
    if (listing !== undefined) fields.push(listing.country, listing.office_label);
    return fields.some((f) => f.toLowerCase().includes(needle));
  };
  const rows = [];
  let count = 0;
  for (const item of items) {
    const listing = item.undated_id === null ? undefined : listings.get(item.undated_id);
    const source = sourceName(item.source);
    if (!matches(item, listing, source)) continue;
    count += 1;
    if (!withRows) continue;
    const link = safeLink(item.source, item.link);
    rows.push({
      id: item.item_id,
      text: item.text,
      source,
      undated: listing === undefined
        ? null
        : `Undated: ${listing.country}, ${listing.office_label}, ${listing.year}`,
      possible: possibleLines(item.possible_matches, item.possible_matches_outside, index),
      link,
      label: link === null ? null : `Open ${source}: ${cut(item.text)} (new tab)`,
    });
  }
  const k = needle === "" ? null : count;
  return {
    title: attentionTitle({ k, included, total, months: doc.window.months }),
    note: truncationNote({ included, total }),
    rows: withRows ? rows : null,
  };
}
