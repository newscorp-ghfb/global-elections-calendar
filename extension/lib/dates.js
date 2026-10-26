// Civil dates, instants and badges. Pure: the clock is always passed in.
// A civil date is a "YYYY-MM-DD" string, compared as a string once isCivilDate accepts it; it is
// never turned into a Date. Date is used only for the local parts of an instant.

export const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
export const MONTHS_SHORT = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

const CIVIL = /^([0-9]{4})-([0-9]{2})-([0-9]{2})$/;
const TIMESTAMP =
  /^([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})(\.[0-9]+)?Z$/;

function leap(y) {
  return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
}

function daysIn(y, m) {
  if (m === 2) return leap(y) ? 29 : 28;
  return [4, 6, 9, 11].includes(m) ? 30 : 31;
}

function real(y, m, d) {
  return m >= 1 && m <= 12 && d >= 1 && d <= daysIn(y, m);
}

export function isCivilDate(s) {
  if (typeof s !== "string") return false;
  const g = CIVIL.exec(s);
  return g !== null && real(Number(g[1]), Number(g[2]), Number(g[3]));
}

// Days since 1970-01-01 of a civil date, by arithmetic (no Date).
function epochDay(y, m, d) {
  const yy = m <= 2 ? y - 1 : y;
  const era = Math.floor(yy / 400);
  const yoe = yy - era * 400;
  const doy = Math.floor((153 * (m + (m > 2 ? -3 : 9)) + 2) / 5) + d - 1;
  const doe = yoe * 365 + Math.floor(yoe / 4) - Math.floor(yoe / 100) + doy;
  return era * 146097 + doe - 719468;
}

export function parseTimestamp(s) {
  if (typeof s !== "string") return null;
  const g = TIMESTAMP.exec(s);
  if (g === null) return null;
  const [y, mo, d, h, mi, se] = g.slice(1, 7).map(Number);
  if (!real(y, mo, d) || h > 23 || mi > 59 || se > 59) return null;
  const frac = g[7] === undefined ? 0 : Math.floor(Number("0" + g[7]) * 1000);
  return ((epochDay(y, mo, d) * 24 + h) * 60 + mi) * 60000 + se * 1000 + frac;
}

function pad2(n) {
  return String(n).padStart(2, "0");
}

export function localToday(nowMs) {
  const t = new Date(nowMs);
  return `${String(t.getFullYear()).padStart(4, "0")}-${pad2(t.getMonth() + 1)}-${pad2(t.getDate())}`;
}

function dayOf(d) {
  return Number(d.slice(8, 10));
}

function monthIndex(d) {
  return Number(d.slice(5, 7)) - 1;
}

export function dayMonth(d) {
  return `${dayOf(d)} ${MONTHS_SHORT[monthIndex(d)]}`;
}

export function dayMonthYear(d) {
  return `${dayOf(d)} ${MONTHS[monthIndex(d)]} ${d.slice(0, 4)}`;
}

export function monthName(d) {
  return MONTHS[monthIndex(d)];
}

export function monthYear(d) {
  return `${MONTHS[monthIndex(d)]} ${d.slice(0, 4)}`;
}

export function badge(card) {
  const start = card.date;
  const end = card.end_date;
  const mon = (d) => MONTHS_SHORT[monthIndex(d)].toUpperCase();
  const months = start.slice(0, 7) === end.slice(0, 7) ? mon(start) : `${mon(start)}–${mon(end)}`;
  if (card.date_precision === "year") return { day: "TBC", mon: start.slice(0, 4) };
  if (card.date_precision === "month") return { day: "TBC", mon: months };
  if (start === end) return { day: String(dayOf(start)), mon: mon(start) };
  return { day: `${dayOf(start)}–${dayOf(end)}`, mon: months };
}

export function stampDate(ms) {
  const t = new Date(ms);
  return `${t.getDate()} ${MONTHS_SHORT[t.getMonth()]} ${t.getFullYear()}`;
}

export function stamp(ms) {
  const t = new Date(ms);
  return `${stampDate(ms)}, ${pad2(t.getHours())}:${pad2(t.getMinutes())}`;
}
