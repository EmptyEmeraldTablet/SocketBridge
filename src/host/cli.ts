#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { BridgeServer } from "./server.js";
import { Recorder } from "./recorder.js";
import { reportExitCode, runScenario, validateScenario } from "./scenario.js";

export async function main(args = process.argv.slice(2)): Promise<number> {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: {
    config: { type: "string" }, port: { type: "string" }, wait: { type: "string" }, output: { type: "string" },
    sensors: { type: "string" }, interval: { type: "string" }, json: { type: "boolean" }, help: { type: "boolean" },
  } });
  const action = positionals[0];
  if (values.help || !action) {
    console.log("socketbridge serve [--sensors players,room] [--output runs/session]\nsocketbridge run <scenario.json> [--wait 120] [--output runs/session]\nBuild/deploy first; start REPENTOGON separately. Config defaults to config.local.json."); return 0;
  }
  if (!["serve", "run"].includes(action)) throw new Error("Unknown command");
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
  const config = JSON.parse(fs.readFileSync(values.config ?? path.join(root, "config.local.json"), "utf8"));
  const port = Number(values.port ?? config.port);
  const waitMs = Number(values.wait ?? "120") * 1000;
  if (!Number.isInteger(port) || port < 1 || port > 65535 || !Number.isFinite(waitMs) || waitMs < 100 || waitMs > 3600000) throw new Error("Invalid port/wait");
  let scenario: unknown;
  if (action === "run") { if (!positionals[1]) throw new Error("Scenario path required"); scenario = JSON.parse(fs.readFileSync(positionals[1], "utf8")); validateScenario(scenario); }
  const output = path.resolve(values.output ?? path.join(root, "runs", new Date().toISOString().replaceAll(":", "-")));
  const bridge = new BridgeServer({ port, token: config.token });
  const recorder = new Recorder(bridge, path.join(output, "messages.jsonl"));
  let recordingFinalized = false;
  bridge.on("fault", error => { process.stderr.write(`[bridge] ${String(error)}\n`); });
  bridge.on("event", event => { if (action === "serve") console.log(JSON.stringify(event)); });
  bridge.on("message", message => { if (action === "serve" && message.kind === "telemetry") console.log(JSON.stringify(message)); });
  let signalResolve: (() => void) | undefined;
  const stopped = new Promise<void>(resolve => { signalResolve = resolve; });
  const onSignal = () => { signalResolve?.(); void bridge.close().catch(error => process.stderr.write(String(error))); };
  process.once("SIGINT", onSignal); process.once("SIGTERM", onSignal);
  try {
    await bridge.listen();
    process.stderr.write(`[bridge] Listening on 127.0.0.1:${port}; recording ${output}\n`);
    await bridge.waitReady(waitMs);
    if (action === "run") {
      validateScenario(scenario);
      const report = await runScenario(bridge, { ...scenario, requires: { inGame: true, ...scenario.requires } }, waitMs);
      await bridge.close();
      try { await recorder.close(); }
      catch (error) { report.status = "ERROR"; report.error = `Recording incomplete: ${String(error)}`; }
      recordingFinalized = true;
      fs.writeFileSync(path.join(output, "report.json"), JSON.stringify(report, null, 2) + "\n");
      console.log(JSON.stringify(report));
      return reportExitCode(report);
    }
    await bridge.request("telemetry.subscribe", { sensors: (values.sensors ?? "players,room").split(",").filter(Boolean), intervalTicks: Number(values.interval ?? 15) });
    await stopped;
    return 0;
  } finally {
    process.off("SIGINT", onSignal); process.off("SIGTERM", onSignal);
    await bridge.close();
    if (!recordingFinalized) await recorder.close();
  }
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().then(code => { process.exitCode = code; }).catch(error => { console.error(String(error)); process.exitCode = 1; });
}
