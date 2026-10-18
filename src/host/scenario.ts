import { isDeepStrictEqual } from "node:util";
import type { Envelope, Json, RecordValue } from "../protocol/types.js";
import { isRecord, textValue, integer } from "../protocol/validate.js";
import { BridgeError, type BridgeServer, type RuntimeRequirements } from "./server.js";

type Step = { id?: string; op: string; [key: string]: unknown };
export interface Scenario { id: string; requires?: RuntimeRequirements; steps: Step[]; cleanup?: Step[]; }
export interface ScenarioReport {
  id: string; status: "PASS" | "FAIL" | "ERROR"; steps: { id: string; result?: unknown; error?: string }[];
  cleanup: { status: "ok" | "failed"; errors: string[] }; error?: string;
  readiness?: RecordValue;
}
export function readPath(value: unknown, path: string): unknown {
  let current = value;
  for (const part of path.split(".")) {
    if (["__proto__", "prototype", "constructor"].includes(part)) throw new Error("Unsafe property path");
    if (current === null || typeof current !== "object" || !Object.hasOwn(current, part)) throw new Error(`Missing field: ${path}`);
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}
function resolve(value: unknown, context: Record<string, unknown>): unknown {
  if (isRecord(value)) {
    if (typeof value.$ref === "string") return readPath(context, value.$ref);
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, resolve(v, context)]));
  }
  if (Array.isArray(value)) return value.map(v => resolve(v, context));
  return value;
}
class AssertionFailure extends Error {}
export function validateScenario(value: unknown): asserts value is Scenario {
  if (!isRecord(value) || !textValue(value.id) || !Array.isArray(value.steps) || value.steps.length > 256) throw new Error("Invalid scenario");
  if (value.cleanup !== undefined && !Array.isArray(value.cleanup)) throw new Error("cleanup must be an array");
  if (value.requires !== undefined && (!isRecord(value.requires)
    || (value.requires.inGame !== undefined && typeof value.requires.inGame !== "boolean")
    || (value.requires.adapters !== undefined && (!Array.isArray(value.requires.adapters) || value.requires.adapters.length > 64
      || value.requires.adapters.some(id => !textValue(id, 96)))))) throw new Error("Invalid scenario readiness requirements");
  const ids = new Set<string>();
  for (const step of [...value.steps, ...(value.cleanup as unknown[] ?? [])]) {
    if (!isRecord(step) || !["command", "snapshot", "assert", "event", "eventually", "step"].includes(String(step.op))) throw new Error("Unknown scenario step");
    if (step.id !== undefined) {
      if (!textValue(step.id) || ids.has(step.id)) throw new Error("Invalid/duplicate step id");
      ids.add(step.id);
    }
  }
}
export async function runScenario(bridge: BridgeServer, scenario: Scenario, readyTimeoutMs = 30000): Promise<ScenarioReport> {
  validateScenario(scenario);
  const context: Record<string, unknown> = Object.create(null);
  const events: Envelope[] = [];
  let overflow = false;
  const onEvent = (event: Envelope) => { if (events.length >= 4096) overflow = true; else events.push(event); };
  bridge.on("event", onEvent);
  const report: ScenarioReport = { id: scenario.id, status: "PASS", steps: [], cleanup: { status: "ok", errors: [] } };
  const session = bridge.sessionId;
  async function execute(step: Step): Promise<unknown> {
    if (!bridge.connected || bridge.sessionId !== session) throw new BridgeError("SESSION_LOST", "Scenario session changed");
    if (overflow) throw new BridgeError("EVENT_OVERFLOW", "Scenario event evidence incomplete");
    const s = resolve(step, context) as Step;
    const timeout = integer(s.timeoutMs, 50, 120000) ? s.timeoutMs : 5000;
    switch (s.op) {
      case "command": return bridge.request(String(s.method), (s.args ?? {}) as RecordValue, timeout);
      case "snapshot": return bridge.snapshot(s.sensors as string[], timeout);
      case "step": return bridge.step(s.ticks as number, timeout);
      case "assert": {
        let actual = typeof s.path === "string" ? readPath(context, s.path) : s.actual;
        if (Object.hasOwn(s, "deltaFrom")) {
          if (typeof actual !== "number" || typeof s.deltaFrom !== "number") throw new Error("deltaFrom requires numeric operands");
          actual -= s.deltaFrom;
        }
        if (Object.hasOwn(s, "equals") && !isDeepStrictEqual(actual, s.equals)) throw new AssertionFailure(`Expected ${JSON.stringify(s.equals)}, got ${JSON.stringify(actual)}`);
        if (Object.hasOwn(s, "min") && !(typeof actual === "number" && typeof s.min === "number" && actual >= s.min)) throw new AssertionFailure("Below minimum / not numeric");
        if (Object.hasOwn(s, "max") && !(typeof actual === "number" && typeof s.max === "number" && actual <= s.max)) throw new AssertionFailure("Above maximum / not numeric");
        if (!["equals", "min", "max"].some(k => Object.hasOwn(s, k))) throw new Error("Assertion has no expectation");
        return { actual, passed: true };
      }
      case "event": {
        const start = Date.now();
        while (Date.now() - start < timeout) {
          if (!bridge.connected || bridge.sessionId !== session || overflow) throw new Error("Event evidence incomplete");
          const index = events.findIndex(e => e.payload.name === s.name
            && (s.where === undefined || Object.entries(s.where as Record<string, unknown>).every(([key, expected]) => isDeepStrictEqual(readPath(e.payload.data, key), expected))));
          if (index >= 0) return events.splice(index, 1)[0];
          await new Promise(r => setTimeout(r, 20));
        }
        throw new AssertionFailure("Expected event not observed: " + String(s.name));
      }
      case "eventually": {
        if (!integer(s.maxTicks, 1, 3600) || typeof s.path !== "string" || !Object.hasOwn(s, "equals")) throw new Error("Invalid eventually step");
        const deadline = Date.now() + timeout;
        const remaining = () => {
          const left = deadline - Date.now();
          if (left < 50) throw new BridgeError("TIMEOUT", "eventually wall deadline exceeded");
          return Math.min(5000, left);
        };
        await bridge.request("runtime.pause", {}, remaining());
        for (let tick = 0; tick <= s.maxTicks; tick++) {
          if (Date.now() > deadline) throw new BridgeError("TIMEOUT", "eventually wall deadline exceeded");
          const snapshot = await bridge.snapshot(s.sensors as string[], remaining());
          if (Date.now() > deadline) throw new BridgeError("TIMEOUT", "eventually wall deadline exceeded");
          if (isDeepStrictEqual(readPath(snapshot, s.path), s.equals)) return snapshot;
          if (tick < s.maxTicks) await bridge.step(1, remaining());
        }
        throw new AssertionFailure(`Condition not satisfied after ${s.maxTicks} updates`);
      }
      default: throw new Error("Unknown step");
    }
  }
  try {
    if (scenario.requires) report.readiness = await bridge.waitForRuntime(scenario.requires, readyTimeoutMs);
    for (let i = 0; i < scenario.steps.length; i++) {
      const step = scenario.steps[i]; const id = step.id ?? String(i);
      const result = await execute(step); context[id] = result; report.steps.push({ id, result });
    }
    if (overflow) throw new BridgeError("EVENT_OVERFLOW", "Scenario event evidence incomplete");
  } catch (error) {
    report.status = error instanceof AssertionFailure ? "FAIL" : "ERROR";
    report.error = error instanceof Error ? error.message : String(error);
  } finally {
    for (const step of scenario.cleanup ?? []) {
      try { await execute(step); } catch (error) { report.cleanup.errors.push(String(error)); }
    }
    for (const method of ["input.clear", "runtime.resume"]) {
      try { if (bridge.connected && bridge.sessionId === session) await bridge.request(method); else throw new Error("Session lost during cleanup"); }
      catch (error) { report.cleanup.errors.push(String(error)); }
    }
    bridge.off("event", onEvent);
    if (overflow && report.status === "PASS") { report.status = "ERROR"; report.error = "Scenario event evidence incomplete"; }
    if (report.cleanup.errors.length) { report.cleanup.status = "failed"; if (report.status === "PASS") report.status = "ERROR"; }
  }
  return report;
}
export function reportExitCode(report: ScenarioReport): number {
  if (report.cleanup.status !== "ok") return 4;
  return report.status === "PASS" ? 0 : report.status === "FAIL" ? 2 : 1;
}
