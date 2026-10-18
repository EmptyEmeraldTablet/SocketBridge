import { integer, isRecord } from "../protocol/validate.js";
import type { Snapshot } from "../protocol/types.js";
export function snapshotValue(value: unknown, required: string[] = []): Snapshot {
  if (!isRecord(value) || value.mode !== "replace" || typeof value.complete !== "boolean" || !isRecord(value.sensors)) throw new Error("Invalid snapshot envelope");
  for (const field of ["runEpoch", "roomEpoch", "updateTick", "renderTick"]) if (!integer(value[field], 0, Number.MAX_SAFE_INTEGER)) throw new Error("Invalid snapshot clock");
  for (const name of required) if (!Object.hasOwn(value.sensors, name)) throw new Error(`Snapshot omitted required sensor: ${name}`);
  let complete = true;
  for (const result of Object.values(value.sensors)) {
    if (!isRecord(result) || !["ok", "error", "unsupported"].includes(String(result.status)) || !integer(result.sampleTick, 0, value.updateTick as number)) throw new Error("Invalid sensor result");
    if (result.status === "ok" && !Object.hasOwn(result, "data")) throw new Error("Successful sensor omitted data");
    if (result.status !== "ok") complete = false;
  }
  if (value.complete !== complete) throw new Error("Inconsistent snapshot completeness");
  return value as unknown as Snapshot;
}
