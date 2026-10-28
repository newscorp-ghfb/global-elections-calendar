// A validator for exactly the JSON Schema keywords the two schema files use (P130). Pure.
// Keywords that only bound size, or forbid fields (additionalProperties: false, maxLength,
// maxItems), are ignored on purpose: a newer producer may add a field or a longer text without
// breaking an older client.

export const ENFORCED_KEYWORDS = [
  "type", "properties", "required", "items", "$ref", "$defs", "enum", "const",
  "pattern", "anyOf", "additionalProperties", "propertyNames", "minimum", "minItems",
];
export const IGNORED_KEYWORDS = [
  "$schema", "$id", "title", "description", "maxLength", "maxItems",
];

const MAX_PROBLEMS = 20;
const REF = /^#\/\$defs\/([^/]+)$/;
const patterns = new Map();

function compiled(pattern) {
  let re = patterns.get(pattern);
  if (re === undefined) {
    re = new RegExp(pattern, "u");
    patterns.set(pattern, re);
  }
  return re;
}

function escapeKey(key) {
  return key.replace(/~/g, "~0").replace(/\//g, "~1");
}

function isObject(v) {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function hasType(value, type) {
  switch (type) {
    case "object": return isObject(value);
    case "array": return Array.isArray(value);
    case "string": return typeof value === "string";
    case "integer": return Number.isInteger(value);
    case "number": return typeof value === "number" && Number.isFinite(value);
    case "boolean": return typeof value === "boolean";
    case "null": return value === null;
    default: return false;
  }
}

function walk(value, schema, p, root, refChecks, out) {
  if (out.problems.length >= out.limit || !isObject(schema)) return;
  const add = (what) => {
    if (out.problems.length < out.limit) out.problems.push(`${p === "" ? "/" : p}: ${what}`);
  };

  if (schema.$ref !== undefined) {
    const found = REF.exec(schema.$ref);
    const target = found === null || !isObject(root.$defs) ? undefined : root.$defs[found[1]];
    if (target === undefined) {
      add(`cannot resolve ${schema.$ref}`);
      return;
    }
    const before = out.problems.length;
    walk(value, target, p, root, refChecks, out);
    const check = refChecks[found[1]];
    if (out.problems.length === before && typeof check === "function" && !check(value)) {
      add(`not a real ${found[1]}`);
    }
  }

  if (schema.type !== undefined && !hasType(value, schema.type)) add(`expected ${schema.type}`);
  if (Object.hasOwn(schema, "const") && value !== schema.const) add("not an allowed value");
  if (Array.isArray(schema.enum) && !schema.enum.includes(value)) add("not an allowed value");

  if (Array.isArray(schema.anyOf)) {
    const passes = schema.anyOf.some((branch) => {
      const sub = { problems: [], limit: 1 };
      walk(value, branch, p, root, refChecks, sub);
      return sub.problems.length === 0;
    });
    if (!passes) add("matches none of the allowed forms");
  }

  if (typeof value === "string" && schema.pattern !== undefined) {
    if (!compiled(schema.pattern).test(value)) add(`does not match ${schema.pattern}`);
  }
  if (typeof value === "number" && schema.minimum !== undefined && value < schema.minimum) {
    add(`below ${schema.minimum}`);
  }

  if (Array.isArray(value)) {
    if (schema.minItems !== undefined && value.length < schema.minItems) {
      add(`fewer than ${schema.minItems} items`);
    }
    if (isObject(schema.items)) {
      value.forEach((item, i) => walk(item, schema.items, `${p}/${i}`, root, refChecks, out));
    }
  }

  if (isObject(value)) {
    if (Array.isArray(schema.required)) {
      for (const key of schema.required) {
        if (!Object.hasOwn(value, key)) add(`missing ${key}`);
      }
    }
    const props = isObject(schema.properties) ? schema.properties : {};
    for (const [key, sub] of Object.entries(value)) {
      const at = `${p}/${escapeKey(key)}`;
      if (isObject(schema.propertyNames)) {
        walk(key, schema.propertyNames, at, root, refChecks, out);
      }
      if (Object.hasOwn(props, key)) {
        walk(sub, props[key], at, root, refChecks, out);
      } else if (isObject(schema.additionalProperties)) {
        walk(sub, schema.additionalProperties, at, root, refChecks, out);
      }
    }
  }
}

// At most 20 problems, each "<pointer>: <what>"; [] when the value passes.
export function schemaProblems(value, schema, refChecks = {}) {
  if (!isObject(schema)) return ["/: no schema"];
  const out = { problems: [], limit: MAX_PROBLEMS };
  walk(value, schema, "", schema, refChecks, out);
  return out.problems;
}
