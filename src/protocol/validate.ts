import type { Command, RecordValue } from "./types.js";

export function isRecord(value: unknown): value is RecordValue {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function integer(value: unknown, min: number, max: number): value is number {
  return typeof value === "number" && value === value && value >= min && value <= max && value % 1 === 0;
}

export function finite(value: unknown, min: number, max: number): value is number {
  return typeof value === "number" && value === value && value >= min && value <= max;
}

export function textValue(value: unknown, max = 128): value is string {
  return typeof value === "string" && value.length > 0 && value.length <= max;
}

export function isList(value: unknown): value is unknown[] { return Array.isArray(value); }
function sensorList(value: unknown, list: typeof isList): boolean {
  if (!list(value) || value.length > 16) return false;
  for (const name of value) if (!textValue(name, 48)) return false;
  return true;
}

/** Shared validation, compiled for both Node and Lua. Engine-specific validation follows this. */
export function validateCommand(value: unknown, record = isRecord, list = isList): string | undefined {
  if (!record(value) || !textValue(value.method, 64) || !record(value.args)) return "Expected method and args object";
  if (!integer(value.timeoutMs, 50, 120000)) return "timeoutMs must be 50..120000";
  const a = value.args;
  switch (value.method) {
    case "runtime.describe": case "runtime.pause": case "runtime.resume": case "input.clear": return;
    case "runtime.step": return integer(a.ticks, 1, 3600) ? undefined : "ticks must be 1..3600";
    case "state.snapshot": return sensorList(a.sensors, list) ? undefined : "sensors must be a bounded list";
    case "telemetry.subscribe": return sensorList(a.sensors, list) && integer(a.intervalTicks, 1, 3600) ? undefined : "Invalid subscription";
    case "input.pulse":
      return integer(a.playerIndex, 0, 15) && integer(a.action, 0, 15)
        && finite(a.value, 0, 1) && integer(a.ticks, 1, 3600) ? undefined : "Invalid input pulse";
    case "item.resolve": return textValue(a.name, 256) ? undefined : "name required";
    case "entity.spawn":
      return integer(a.type, 1, 10000) && integer(a.variant, 0, 100000)
        && integer(a.subtype, 0, 2147483647) && finite(a.x, -10000, 10000)
        && finite(a.y, -10000, 10000) ? undefined : "Invalid entity spawn";
    case "entity.remove": return textValue(a.entityRef, 128) ? undefined : "entityRef required";
    case "player.giveCollectible": case "player.removeCollectible":
      return integer(a.playerIndex, 0, 15) && integer(a.itemId, 1, 2147483647) ? undefined : "Invalid player/item";
    case "mod.observe": case "mod.invoke":
      return textValue(a.modId, 96) && textValue(a.name, 96) && record(a.params) ? undefined : "Invalid mod adapter request";
    case "console.execute": return textValue(a.command, 1024) ? undefined : "command required";
    default: return "Unknown method: " + value.method;
  }
}

export function command(method: string, args: RecordValue = {}, timeoutMs = 5000): Command {
  const result = { method, args, timeoutMs };
  const issue = validateCommand(result);
  if (issue !== undefined) throw new Error(issue);
  return result;
}
