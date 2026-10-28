// Pins as places (P140, P141; D3, R48). Pure: storage comes in as `get`/`set` functions, and the
// place table (`{names, places}`, extension/places.json) as an argument.
//
// Only the worker writes the pin keys: the one-time migration of v1.0.2's `pinned_countries`, and
// every later edit through one queue. `pinned_countries` is read once, by the migration, and
// never written.

export const PIN_KEYS = {
  legacy: "pinned_countries",
  places: "pinned_places_v2",
  unresolved: "unresolved_pins_v2",
  migrated: "pins_migrated_v2",
};

const MAX_ANCESTORS = 8;
const OPS = ["pin", "unpin", "forget"];

function messageOf(err) {
  return err instanceof Error ? err.message : String(err);
}

function isStringList(value) {
  return Array.isArray(value) && value.every((v) => typeof v === "string");
}

function unique(values) {
  return [...new Set(values)];
}

// The place id a v1.0.2 country string stands for, or null. The lookup is exact, and own
// properties only, so "constructor" and "__proto__" never resolve.
export function placeOf(name, table) {
  if (typeof name !== "string" || !Object.hasOwn(table.names, name)) return null;
  return table.names[name];
}

// What the migration would store, or null when it has already run.
export function migration(stored, table) {
  if (stored[PIN_KEYS.migrated] === true) return null;
  const old = Array.isArray(stored[PIN_KEYS.legacy]) ? stored[PIN_KEYS.legacy] : [];
  const places = [];
  const unresolved = [];
  for (const name of old) {
    if (typeof name !== "string") continue;
    const id = placeOf(name, table);
    if (id === null) unresolved.push(name);
    else places.push(id);
  }
  return { places: unique(places), unresolved: unique(unresolved) };
}

// The pins in force: the migration's result until the flag is set (the popup derives it in
// memory), then the stored lists. A stored list that is not a list of strings counts as empty.
export function currentPins(stored, table) {
  const derived = migration(stored, table);
  if (derived !== null) return derived;
  const list = (key) => (isStringList(stored[key]) ? unique(stored[key]) : []);
  return { places: list(PIN_KEYS.places), unresolved: list(PIN_KEYS.unresolved) };
}

// The place ids that stand for `placeId`: itself, then its ancestors through `parent`, at most
// MAX_ANCESTORS steps. An id the table does not know stands for itself only.
function lineage(placeId, table) {
  const out = [placeId];
  let at = placeId;
  for (let step = 0; step < MAX_ANCESTORS; step += 1) {
    if (!Object.hasOwn(table.places, at)) break;
    const parent = table.places[at].parent;
    if (typeof parent !== "string") break;
    out.push(parent);
    at = parent;
  }
  return out;
}

// (placeId) => does the popup show a card of this place? An empty list matches everything.
export function pinMatcher(places, table) {
  if (places.length === 0) return () => true;
  const pinned = new Set(places);
  return (placeId) => typeof placeId === "string" && lineage(placeId, table).some((id) => pinned.has(id));
}

// Reads the pin keys; resolves to the stored values.
function readAll(get) {
  return get(Object.values(PIN_KEYS));
}

function sameList(a, b) {
  return isStringList(b) && a.length === b.length && a.every((v, i) => v === b[i]);
}

// One migration (P140). Never rejects: {ok: true, migrated} or {ok: false, error}.
export async function migratePins({ get, set, table }) {
  try {
    const wanted = migration(await readAll(get), table);
    if (wanted === null) return { ok: true, migrated: false };
    await set({
      [PIN_KEYS.places]: wanted.places,
      [PIN_KEYS.unresolved]: wanted.unresolved,
    });
    const back = await get([PIN_KEYS.places, PIN_KEYS.unresolved]);
    if (!sameList(wanted.places, back[PIN_KEYS.places]) || !sameList(wanted.unresolved, back[PIN_KEYS.unresolved])) {
      return { ok: false, error: "the migrated pins could not be verified" };
    }
    await set({ [PIN_KEYS.migrated]: true });
    return { ok: true, migrated: true };
  } catch (err) {
    return { ok: false, error: `the pins could not be migrated: ${messageOf(err)}` };
  }
}

// Runs its tasks strictly one after another, whatever they return or throw.
export function exclusive() {
  let tail = Promise.resolve();
  return (task) => {
    const run = tail.then(task, task);
    tail = run.then(() => {}, () => {});
    return run;
  };
}

// {places, unresolved} after one edit, or {error}. `pin` appends an id that is absent; `unpin`
// and `forget` remove a value that is present, so every op is idempotent.
export function applyEdit(pins, { op, value } = {}) {
  if (!OPS.includes(op) || typeof value !== "string" || value === "") return { error: "not a pin" };
  if (op === "pin") {
    return {
      places: pins.places.includes(value) ? pins.places : [...pins.places, value],
      unresolved: pins.unresolved,
    };
  }
  if (op === "unpin") return { places: pins.places.filter((v) => v !== value), unresolved: pins.unresolved };
  return { places: pins.places, unresolved: pins.unresolved.filter((v) => v !== value) };
}

// An editor that applies pin edits strictly one after another, each on freshly read storage.
// Never rejects. `run` is the worker's shared queue, so a migration cannot overlap an edit.
export function editQueue({ get, set, table, run = exclusive() }) {
  async function apply(edit) {
    const bad = applyEdit({ places: [], unresolved: [] }, edit);
    if (bad.error !== undefined) return { ok: false, error: bad.error };
    let stored;
    try {
      stored = await readAll(get);
      if (stored[PIN_KEYS.migrated] !== true) {
        const migrated = await migratePins({ get, set, table });
        if (!migrated.ok) return { ok: false, error: migrated.error };
        stored = await readAll(get);
      }
    } catch (err) {
      return { ok: false, error: `could not read the pins: ${messageOf(err)}` };
    }
    const before = currentPins(stored, table);
    const after = applyEdit(before, edit);
    const key = edit.op === "forget" ? PIN_KEYS.unresolved : PIN_KEYS.places;
    const field = edit.op === "forget" ? "unresolved" : "places";
    const pins = { places: after.places, unresolved: after.unresolved };
    if (sameList(before[field], after[field])) return { ok: true, pins };
    try {
      await set({ [key]: after[field] });
    } catch (err) {
      return { ok: false, error: `could not save the pins: ${messageOf(err)}` };
    }
    try {
      const back = await get([key]);
      if (!sameList(after[field], back[key])) return { ok: false, error: "the saved pins could not be verified" };
    } catch {
      return { ok: false, error: "the saved pins could not be verified" };
    }
    return { ok: true, pins };
  }
  return (edit) => run(() => apply(edit)).catch((err) => ({ ok: false, error: messageOf(err) }));
}

// The places an options page lists from a valid stored feed record: [{id, name}], in first-seen
// order. A v2 record lists its cards' and its undated listings' places; a legacy or
// update_needed record lists each card's `country` through the table (unmapped names are left
// out). The name is the table's display, else the feed's country, else the id.
export function optionPlaces(record, table) {
  if (typeof record !== "object" || record === null) return [];
  const doc = record.data;
  const found = new Map();
  const add = (id, country) => {
    if (typeof id !== "string" || found.has(id)) return;
    const known = Object.hasOwn(table.places, id) ? table.places[id].display : null;
    found.set(id, known ?? (typeof country === "string" && country !== "" ? country : id));
  };
  for (const cards of Object.values(doc.months)) {
    for (const card of cards) {
      if (record.format === "v2") add(card.place_id, card.country);
      else add(placeOf(card.country, table), card.country);
    }
  }
  if (record.format === "v2" && Array.isArray(doc.undated)) {
    for (const listing of doc.undated) add(listing.place_id, listing.country);
  }
  return [...found].map(([id, name]) => ({ id, name }));
}

const byName = (a, b) => a.localeCompare(b, "en");

// The rows of the options list and the unresolved pins. Pinned rows first, then the rest, each
// by name. `includes` holds the display names of the places below a row's place.
export function optionRows(feedPlaces, pins, table) {
  const names = new Map(feedPlaces.map(({ id, name }) => [id, name]));
  for (const id of pins.places) {
    if (!names.has(id)) names.set(id, Object.hasOwn(table.places, id) ? table.places[id].display : id);
  }
  const pinned = new Set(pins.places);
  const below = (id) => {
    const matches = pinMatcher([id], table);
    return Object.entries(table.places)
      .filter(([other]) => other !== id && matches(other))
      .map(([, entry]) => entry.display)
      .sort(byName);
  };
  const rows = [...names].map(([id, name]) => ({
    id,
    name,
    pinned: pinned.has(id),
    includes: below(id),
  }));
  rows.sort((a, b) => Number(b.pinned) - Number(a.pinned) || byName(a.name, b.name));
  return { rows, unresolved: pins.unresolved };
}
