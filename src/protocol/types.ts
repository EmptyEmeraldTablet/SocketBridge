export const PROTOCOL = "socketbridge/4";
export const MAX_LINE_BYTES = 262144;
export const MAX_BUFFER_BYTES = 1048576;
export type Json = null | boolean | number | string | Json[] | { [key: string]: Json | undefined };
export type RecordValue = { [key: string]: Json | undefined };
export type ResultStatus = "accepted" | "completed" | "failed" | "cancelled";
export interface Clock {
  runEpoch: number;
  roomEpoch: number;
  updateTick: number;
  renderTick: number;
}
export interface Envelope extends Clock {
  protocol: string;
  sessionId: string;
  connectionId: string;
  seq: number;
  kind: string;
  requestId?: string;
  payload: RecordValue;
}
export interface Command {
  method: string;
  args: RecordValue;
  timeoutMs: number;
}
export interface SensorResult {
  status: "ok" | "error" | "unsupported";
  sampleTick: number;
  data?: Json;
  error?: string;
}
export interface Snapshot extends Clock {
  mode: "replace";
  complete: boolean;
  sensors: { [name: string]: SensorResult };
}
export const SENSOR_NAMES = [
  "players", "inventory", "room", "grid", "entities", "npcs", "pickups",
  "projectiles", "tears", "lasers", "bombs", "familiars", "slots", "effects",
];

export const COMMAND_NAMES = [
  "runtime.describe", "runtime.pause", "runtime.resume", "runtime.step",
  "state.snapshot", "telemetry.subscribe", "input.pulse", "input.clear",
  "item.resolve", "entity.spawn", "entity.remove", "player.giveCollectible",
  "player.removeCollectible", "mod.observe", "mod.invoke", "console.execute",
];
