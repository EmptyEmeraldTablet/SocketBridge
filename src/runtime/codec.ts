import type {} from "isaac-typescript-definitions";
import * as json from "socketbridge_v4.dkjson";
import type { RecordValue } from "../protocol/types";
export const nullValue = json.null;

export function array<T>(items: T[] = []): T[] { return setmetatable(items, { __jsontype: "array" } as LuaMetatable<T[]>); }
export function object<T extends object>(value: T): T { return setmetatable(value, { __jsontype: "object" } as LuaMetatable<T>); }
export function isList(value: unknown): value is unknown[] {
  if (type(value) !== "table" || value === json.null) return false;
  const meta = getmetatable(value as object) as { __jsontype?: string } | undefined;
  if (meta?.__jsontype !== undefined) return meta.__jsontype === "array";
  return (value as unknown[])[0] !== undefined;
}
export function isRecord(value: unknown): value is RecordValue {
  return type(value) === "table" && value !== json.null && !isList(value);
}
function check(value: unknown, seen: LuaTable<object, boolean>, depth: number): void {
  if (depth > 32) error("JSON depth exceeded");
  if (value === json.null || value === undefined) return;
  const kind = type(value);
  if (kind === "number") {
    const n = value as number;
    if (n !== n || n === math.huge || n === -math.huge) error("Non-finite JSON number");
  } else if (kind === "table") {
    const tableValue = value as LuaTable<string, unknown>;
    if (seen.get(tableValue)) error("Cyclic JSON value");
    seen.set(tableValue, true);
    const [firstKey] = next(tableValue);
    if (firstKey === undefined && getmetatable(tableValue) === undefined) object(tableValue);
    for (const [key, child] of pairs(tableValue)) {
      if (type(key) !== "string" && type(key) !== "number") error("Invalid JSON key");
      check(child, seen, depth + 1);
    }
    seen.delete(tableValue);
  } else if (kind !== "boolean" && kind !== "string") error("JSON cannot encode " + kind);
}
export function encode(value: unknown): string {
  check(value, new LuaTable<object, boolean>(), 0);
  return json.encode(value);
}
export function decode(line: string): unknown {
  // Reject excessive nesting before entering the recursive vendor parser.
  let depth = 0; let quoted = false; let escaped = false;
  for (let i = 1; i <= line.length; i++) {
    const ch = string.sub(line, i, i);
    if (quoted) { if (escaped) escaped = false; else if (ch === "\\") escaped = true; else if (ch === '"') quoted = false; }
    else if (ch === '"') quoted = true;
    else if (ch === "{" || ch === "[") { depth++; if (depth > 32) error("JSON depth exceeded"); }
    else if (ch === "}" || ch === "]") depth--;
  }
  const [value, position, issue] = json.decode(line, 1, json.null);
  if (issue !== undefined) error(issue);
  const [suffix] = string.match(string.sub(line, position), "^%s*$");
  if (suffix === undefined) error("Trailing JSON bytes");
  check(value, new LuaTable<object, boolean>(), 0);
  return value;
}

/** Stable command fingerprints; dictionary insertion order does not change identity. */
export function canonical(value: unknown): string {
  if (type(value) !== "table" || value === json.null) return encode(value);
  if (isList(value)) {
    const parts: string[] = [];
    for (const item of value) parts.push(canonical(item));
    return "[" + table.concat(parts, ",") + "]";
  }
  const keys: string[] = [];
  for (const [key] of pairs(value as LuaTable<string, unknown>)) keys.push(key);
  table.sort(keys);
  const parts: string[] = [];
  for (const key of keys) parts.push(encode(key) + ":" + canonical((value as RecordValue)[key]));
  return "{" + table.concat(parts, ",") + "}";
}
