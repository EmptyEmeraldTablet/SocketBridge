import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import test from "node:test";
import assert from "node:assert/strict";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
test("deployment preserves an existing installation and restores its complete contents", () => {
  const game = fs.mkdtempSync(path.join(os.tmpdir(), "socketbridge-deploy-test-"));
  fs.writeFileSync(path.join(game, "isaac-ng.exe"), "fixture");
  fs.mkdirSync(path.join(game, "mods/SocketBridge"), { recursive: true });
  fs.writeFileSync(path.join(game, "mods/SocketBridge/main.lua"), "original");
  fs.writeFileSync(path.join(game, "mods/SocketBridge/custom.txt"), "user-added-file");
  const run = args => {
    const result = spawnSync(process.execPath, ["tools/deploy.mjs", "--game-root", game, ...args], { cwd: root, encoding: "utf8", windowsHide: true });
    assert.equal(result.status, 0, result.stderr || result.error?.message);
    return JSON.parse(result.stdout);
  };
  const deployed = run([]);
  assert.equal(fs.existsSync(path.join(game, "mods/SocketBridge/custom.txt")), false);
  assert.ok(fs.existsSync(path.join(game, "mods/SocketBridge/manifest.json")));
  run([]); // Restoring the original remains supported after subsequent deployments.
  run(["--restore", deployed.backupId]);
  assert.equal(fs.readFileSync(path.join(game, "mods/SocketBridge/main.lua"), "utf8"), "original");
  assert.equal(fs.readFileSync(path.join(game, "mods/SocketBridge/custom.txt"), "utf8"), "user-added-file");
  // Small test artifacts are kept in the OS temp directory; no recursive delete of computed game paths.
});
