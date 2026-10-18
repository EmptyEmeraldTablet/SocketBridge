/** Explicit, opt-in real-engine check. Starts at the menu, verifies the bridge, closes owned processes. */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawn, execFileSync } from "node:child_process";
import { parseArgs } from "node:util";
import { BridgeServer } from "../dist/host/server.js";
import { Recorder } from "../dist/host/recorder.js";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const game = path.dirname(root);
const { values } = parseArgs({ options: { launcher: { type: "string" }, ini: { type: "string" } } });
if (!values.launcher || !fs.existsSync(values.launcher)) throw new Error("--launcher <REPENTOGONLauncher.exe> required");
const ps = code => execFileSync("powershell.exe", ["-NoProfile", "-NonInteractive", "-Command", code], { encoding: "utf8", windowsHide: true, timeout: 15000 });
const quote = value => "'" + value.replaceAll("'", "''") + "'";
function processes() {
  const output = ps("@(Get-Process isaac-ng -ErrorAction SilentlyContinue | ForEach-Object { [pscustomobject]@{ id=$_.Id; path=$_.Path; started=$_.StartTime.ToUniversalTime().ToString('o') } }) | ConvertTo-Json -Compress").trim();
  return output ? [].concat(JSON.parse(output)) : [];
}
if (processes().length) throw new Error("An Isaac process already exists; refusing to take over");
const config = JSON.parse(fs.readFileSync(path.join(root, "config.local.json"), "utf8"));
const manifest = JSON.parse(fs.readFileSync(path.join(game, "mods/SocketBridge/manifest.json"), "utf8"));
const output = path.join(root, "runs", `menu-${Date.now()}`);
const bridge = new BridgeServer({ port: config.port, token: config.token });
const recorder = new Recorder(bridge, path.join(output, "messages.jsonl"));
bridge.on("fault", error => process.stderr.write(`[menu-check] ${error.message}\n`));
let child;
let launchAt;
const report = { kind: "menu-smoke", status: "ERROR", startedAt: new Date().toISOString(), cleanup: [] };
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
try {
  await bridge.listen();
  const args = ["--stealth-mode", "--skip-wizard", "--skip-repentogon-update", "--luadebug", "--isaac", path.join(game, "isaac-ng.exe")];
  if (values.ini) args.push("--configuration-file", path.resolve(values.ini));
  launchAt = Date.now();
  child = spawn(path.resolve(values.launcher), args, { cwd: path.dirname(path.resolve(values.launcher)), stdio: "ignore", windowsHide: true });
  const launchError = new Promise((_, reject) => child.once("error", reject));
  process.stderr.write("[menu-check] Waiting for REPENTOGON runtime handshake\n");
  await Promise.race([bridge.waitReady(60000), launchError]);
  const identity = await bridge.request("runtime.describe");
  report.identity = identity;
  if (!identity.result.repentogon || identity.result.buildId !== manifest.buildId) throw new Error("Wrong runtime/build identity");
  if (identity.result.inGame) throw new Error("Unexpected active run; menu-only check aborted");
  await bridge.request("telemetry.subscribe", { sensors: [], intervalTicks: 15 });
  const pause = await bridge.request("runtime.pause").then(() => "unexpected-success", error => error.message);
  if (!pause.includes("NOT_IN_GAME")) throw new Error("Menu mutation guard failed: " + pause);
  const snapshot = await bridge.snapshot(["players"]).then(() => "unexpected-success", error => error.code);
  if (!snapshot.includes("NOT_IN_GAME")) throw new Error("Menu snapshot guard failed: " + snapshot);
  await bridge.request("input.clear");
  await bridge.request("runtime.resume");
  report.menuGuard = pause;
  report.status = "PASS";
} catch (error) {
  report.error = String(error);
} finally {
  try {
    await bridge.close();
    if (launchAt !== undefined) {
    const owned = processes().filter(p => p.path && path.resolve(p.path).toLowerCase().startsWith(game.toLowerCase() + path.sep)
      && Date.parse(p.started) >= launchAt - 2000);
    for (const p of owned) {
      const guard = `$p=Get-Process -Id ${p.id} -ErrorAction SilentlyContinue; if ($p -and $p.Path -eq ${quote(p.path)} -and $p.StartTime.ToUniversalTime().ToString('o') -eq ${quote(p.started)})`;
      ps(`${guard} { [void]$p.CloseMainWindow() }`);
      await sleep(1500);
      if (processes().some(active => active.id === p.id && active.started === p.started)) {
        ps(`${guard} { Stop-Process -Id ${p.id} -Force }`);
        report.cleanup.push({ pid: p.id, action: "forced-after-graceful-timeout" });
      } else report.cleanup.push({ pid: p.id, action: "closed-normally" });
    }
    await sleep(2000);
    if (child && child.exitCode === null && !child.killed) { child.kill(); report.cleanup.push({ launcherPid: child.pid, action: "closed-owned-launcher" }); }
    }
  } catch (error) { report.status = "ERROR"; report.cleanup.push({ error: String(error) }); }
  try { await recorder.close(); }
  catch (error) { report.status = "ERROR"; report.recordingError = String(error); }
  const logPath = path.join(process.env.USERPROFILE ?? "", "Documents/My Games/Binding of Isaac Repentance+/log.txt");
  if (fs.existsSync(logPath) && fs.statSync(logPath).mtimeMs >= launchAt) {
    const log = fs.readFileSync(logPath, "utf8");
    report.engineLogEvidence = log.split(/\r?\n/).filter(line => /SocketBridgeV4|playing cutscene 1 \(Intro\)|Menu Manager Init/.test(line));
    report.introCutsceneLogged = log.includes("playing cutscene 1 (Intro)");
  }
  report.durationMs = Date.now() - Date.parse(report.startedAt);
  fs.writeFileSync(path.join(output, "report.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ ...report, output }));
  if (report.status !== "PASS") process.exitCode = 1;
}
