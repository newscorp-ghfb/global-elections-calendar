// Label rules (spec correction P134). Pure: today and now are passed in.
import {
  dayMonth, dayMonthYear, monthName, monthYear, parseTimestamp, stampDate,
} from "./dates.js";

export const KINDS = [
  "cancelled", "postponed", "possibly_cancelled", "possibly_postponed", "disputed",
  "held", "past", "past_expected", "expected", "today", "scheduled", "day_unconfirmed",
];

const WEEK_MS = 7 * 86400000;
const UNDATED = "Unverified: the source data's date is unknown";
const TENTATIVE_KINDS = ["scheduled", "today", "expected", "day_unconfirmed"];

function sameMonth(a, b) {
  return a.slice(0, 7) === b.slice(0, 7);
}

function datesLabel(card, child, today) {
  const p = card.date_precision;
  const m = card.date_meaning;
  const start = card.date;
  const end = card.end_date;
  if (end < today) {
    if (p !== "day" || m === "expected_window") {
      return { kind: "past_expected", text: "Past expected period — not confirmed" };
    }
    return { kind: "past", text: "Past" };
  }
  if (m === "expected_window") {
    let text;
    if (p === "day") {
      text = start === end
        ? `Expected on ${dayMonth(start)}`
        : `Expected between ${dayMonth(start)} and ${dayMonth(end)}`;
    } else if (p === "month") {
      text = sameMonth(start, end)
        ? `Expected in ${monthName(start)}`
        : `Expected between ${monthName(start)} and ${monthName(end)}`;
    } else {
      text = `Expected in ${start.slice(0, 4)}`;
    }
    return { kind: "expected", text };
  }
  if (p === "day") {
    if (start <= today && m === "voting_period" && !child.date_conflict) {
      return { kind: "today", text: "Scheduled voting period: today (approx.)" };
    }
    return { kind: "scheduled", text: "Scheduled" };
  }
  if (p === "month") {
    const text = sameMonth(start, end)
      ? monthName(start)
      : `${monthName(start)}–${monthName(end)}`;
    return { kind: "day_unconfirmed", text: `${text} — day unconfirmed` };
  }
  return { kind: "day_unconfirmed", text: `${start.slice(0, 4)} — date unconfirmed` };
}

function kindAndText(card, child, today) {
  if (card.status === "Cancelled") return { kind: "cancelled", text: "Cancelled" };
  if (card.status === "Postponed") return { kind: "postponed", text: "Postponed" };
  if (child.status_conflict) {
    if (child.sources.some((s) => s.status_claim === "cancelled")) {
      return { kind: "possibly_cancelled", text: "Possibly cancelled — sources disagree" };
    }
    return { kind: "possibly_postponed", text: "Possibly postponed — sources disagree" };
  }
  if (card.status === "Disputed") return { kind: "disputed", text: "Disputed" };
  if (child.occurrence_confirmed) return { kind: "held", text: "Held" };
  return datesLabel(card, child, today);
}

function shown(date, precision) {
  if (precision === "day") return dayMonthYear(date);
  if (precision === "month") return monthYear(date);
  return date.slice(0, 4);
}

function notesOf(card, child, kind, now) {
  const notes = [];
  if (child.date_conflict || child.provisional_date === "moved") {
    notes.push("Sources disagree on date");
  }
  if (child.provisional_date === "less_precise") {
    const newer = child.sources.find((s) => s.provisional === true);
    if (newer !== undefined) {
      notes.push(
        "The source now gives a less precise date: " +
          `${shown(card.date, card.date_precision)} → ${shown(newer.date, newer.date_precision)}`,
      );
    }
  }
  const used = child.sources.filter((s) => s.selected && s.fallback);
  if (used.length > 0) {
    if (used.some((s) => s.fetched_at === null)) {
      notes.push(UNDATED);
    } else {
      const fetched = Math.min(...used.map((s) => parseTimestamp(s.fetched_at)));
      notes.push(
        now - fetched > WEEK_MS
          ? `Unverified since ${stampDate(fetched)}`
          : `Using source data from ${stampDate(fetched)}`,
      );
    }
  }
  if (kind === "held") {
    const held = child.sources.filter((s) => s.status_claim === "held");
    if (held.length > 0 && held.every((s) => s.fallback)) {
      const times = held.map((s) => parseTimestamp(s.fetched_at)).filter((t) => t !== null);
      if (times.length > 0) {
        notes.push(`Confirmed by source data from ${stampDate(Math.max(...times))}`);
      } else if (!notes.includes(UNDATED)) {
        notes.push(UNDATED); // ruling 8: held only by saved data of unknown date
      }
    }
  }
  return notes;
}

export function childLabel(card, child, { today, now }) {
  const { kind, text } = kindAndText(card, child, today);
  const chips = [];
  if (card.date_status === "tentative" && TENTATIVE_KINDS.includes(kind)) {
    chips.push({ kind: "tentative", text: "Tentative" });
  }
  if (card.level === "subnational") chips.push({ kind: "subnational", text: "Subnational" });
  if (child.rescheduled_from.length > 0) {
    chips.push({ kind: "rescheduled", text: `Rescheduled from ${child.rescheduled_from.join(", ")}` });
  }
  return { kind, text, chips, notes: notesOf(card, child, kind, now) };
}

export function cardLabel(card, labels) {
  const possibly = labels.filter((l) => l.kind.startsWith("possibly_"));
  if (possibly.length > 0) {
    const n = labels.length;
    return {
      kind: possibly[0].kind,
      text: n > 1 ? `${possibly[0].text} · ${possibly.length} of ${n}` : possibly[0].text,
    };
  }
  const held = labels.filter((l) => l.kind === "held").length;
  const past = labels.filter((l) => l.kind === "past").length;
  if (held > 0 && past > 0 && held + past === labels.length) {
    return { kind: "past", text: `Past · ${held} of ${labels.length} confirmed held` };
  }
  return { kind: labels[0].kind, text: labels[0].text };
}

export function sourceNote(source) {
  if (!source.provisional) return null;
  const t = source.fetched_at === null ? null : parseTimestamp(source.fetched_at);
  return t === null
    ? "Newer data from an incomplete fetch"
    : `Newer data from an incomplete fetch on ${stampDate(t)}`;
}
