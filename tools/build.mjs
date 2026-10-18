import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
process.chdir(root);
function run(file, args) {
  const result = spawnSync(process.execPath, [file, ...args], { stdio: "inherit", windowsHide: true });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}
run("node_modules/typescript/bin/tsc", ["-p", "tsconfig.host.json"]);
run("node_modules/typescript-to-lua/dist/tstl.js", ["-p", "tsconfig.runtime.json"]);
const files = [];
function collect(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const file = path.join(dir, entry.name);
    if (entry.isDirectory()) collect(file);
    else files.push(file);
  }
}
collect("src"); collect("plugins"); collect("vendor");
files.push("package-lock.json", "tsconfig.host.json", "tsconfig.runtime.json", "tools/build.mjs", "metadata.xml");
const hash = crypto.createHash("sha256");
for (const file of files.sort()) { hash.update(file.replaceAll("\\", "/")); hash.update(fs.readFileSync(file)); }
const buildId = hash.digest("hex").slice(0, 20);
const configPath = path.join(root, "config.local.json");
if (!fs.existsSync(configPath)) fs.writeFileSync(configPath, JSON.stringify({ port: 9527, token: crypto.randomBytes(24).toString("hex"), allowConsole: false }, null, 2) + "\n");
const config = JSON.parse(fs.readFileSync(configPath, "utf8"));
if (!Number.isInteger(config.port) || config.port < 1 || config.port > 65535 || typeof config.token !== "string"
  || !/^[A-Za-z0-9_-]{16,256}$/.test(config.token) || typeof config.allowConsole !== "boolean") throw new Error("Invalid config.local.json");
const mod = path.join(root, "mod");
fs.mkdirSync(path.join(mod, "socketbridge_v4"), { recursive: true });
const compiled = fs.readFileSync(path.join(mod, "main.lua"), "utf8").replaceAll("__SOCKETBRIDGE_BUILD_ID__", buildId);
// Native require failures occur before main(), so diagnostics must wrap the whole bundle.
const lua = `local function diagnostic(message)
  if Isaac and Isaac.DebugString then Isaac.DebugString(message) end
  print(message)
end
diagnostic("[SocketBridgeV4] bootstrap build=${buildId}")
local ok, issue = pcall(function(...)
${compiled}
end, ...)
if not ok then
  diagnostic("[SocketBridgeV4] startup failed: " .. tostring(issue))
  error(issue)
end
`;
fs.writeFileSync(path.join(mod, "main.lua"), lua);
fs.copyFileSync("vendor/dkjson.lua", path.join(mod, "socketbridge_v4/dkjson.lua"));
fs.writeFileSync(path.join(mod, "socketbridge_v4/config.lua"), `return { port = ${config.port}, token = "${config.token}", allowConsole = ${config.allowConsole} }\n`);
fs.copyFileSync("metadata.xml", path.join(mod, "metadata.xml"));
const names = ["main.lua", "metadata.xml", "socketbridge_v4/config.lua", "socketbridge_v4/dkjson.lua"];
fs.writeFileSync(path.join(mod, "manifest.json"), JSON.stringify({ version: 4, buildId, files: names.map(file => ({ path: file,
  sha256: crypto.createHash("sha256").update(fs.readFileSync(path.join(mod, file))).digest("hex") })) }, null, 2) + "\n");
console.log(`Built SocketBridge v4 ${buildId}: ${Buffer.byteLength(lua)} Lua bytes; artifact mod/`);
