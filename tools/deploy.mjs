import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";
import { parseArgs } from "node:util";
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { values } = parseArgs({ options: { "game-root": { type: "string" }, restore: { type: "string" } } });
const game = fs.realpathSync(values["game-root"] ?? path.dirname(root));
const mods = path.join(game, "mods");
if (!fs.existsSync(path.join(game, "isaac-ng.exe")) || fs.realpathSync(mods).toLowerCase() !== mods.toLowerCase()) throw new Error("Invalid game root / mods junction");
const target = path.resolve(mods, "SocketBridge");
if (path.dirname(target).toLowerCase() !== mods.toLowerCase()) throw new Error("Target outside mods");
if (fs.existsSync(target) && fs.lstatSync(target).isSymbolicLink()) throw new Error("Refuse deployment through junction/symlink");
if (process.platform === "win32") {
  const processes = execFileSync("powershell.exe", ["-NoProfile", "-NonInteractive", "-Command", "@(Get-Process isaac-ng -ErrorAction SilentlyContinue).Count"], { encoding: "utf8", windowsHide: true });
  if (Number(processes.trim()) !== 0) throw new Error("Exit the game before deploying/restoring SocketBridge");
}
// Keep renames on the target filesystem even when the source checkout is on another drive.
const backups = path.join(game, ".socketbridge-deploy-backups");
const sha = file => crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex");
function safeFile(base, relative) {
  const file = path.resolve(base, relative);
  if (!file.startsWith(path.resolve(base) + path.sep) || path.isAbsolute(relative)) throw new Error("Unsafe manifest path");
  return file;
}
function validateArtifact(dir, manifest) {
  if (manifest.version !== 4 || !Array.isArray(manifest.files)) throw new Error("Invalid build manifest");
  for (const file of manifest.files) if (sha(safeFile(dir, file.path)) !== file.sha256) throw new Error(`Artifact modified: ${file.path}`);
}
if (values.restore) {
  if (!/^[A-Za-z0-9_-]+$/.test(values.restore)) throw new Error("Invalid backup id");
  const backup = path.resolve(backups, values.restore);
  if (path.dirname(backup) !== backups) throw new Error("Backup outside workspace");
  const journalPath = path.join(backup, "journal.json");
  const journal = JSON.parse(fs.readFileSync(journalPath, "utf8"));
  if (journal.target !== target || journal.status !== "deployed") throw new Error("Backup does not match deployed target");
  // Allow restoring an older backup after subsequent builds, but only over an intact
  // installation recorded in one of this tool's journals.
  const current = JSON.parse(fs.readFileSync(path.join(target, "manifest.json"), "utf8"));
  const known = fs.readdirSync(backups).some(id => {
    try {
      const saved = JSON.parse(fs.readFileSync(path.join(backups, id, "journal.json"), "utf8"));
      return saved.target === target && JSON.stringify(saved.manifest) === JSON.stringify(current);
    } catch { return false; }
  });
  if (!known) throw new Error("Installed artifact is not recorded in a deployment journal");
  validateArtifact(target, current);
  const withdrawn = path.join(backup, "withdrawn-v4");
  if (fs.existsSync(withdrawn)) throw new Error("Restore destination already exists");
  if (journal.hadPrevious && !fs.existsSync(path.join(backup, "previous"))) throw new Error("Previous installation missing");
  fs.renameSync(target, withdrawn);
  try { if (journal.hadPrevious) fs.renameSync(path.join(backup, "previous"), target); }
  catch (error) { fs.renameSync(withdrawn, target); throw error; }
  journal.status = "restored"; fs.writeFileSync(journalPath, JSON.stringify(journal, null, 2));
  console.log(JSON.stringify({ restored: true, target, backupId: values.restore, backupRoot: backups }));
} else {
  const source = path.join(root, "mod");
  const manifest = JSON.parse(fs.readFileSync(path.join(source, "manifest.json"), "utf8"));
  validateArtifact(source, manifest);
  const id = new Date().toISOString().replace(/[:.]/g, "-");
  const backup = path.resolve(backups, id);
  if (path.dirname(backup) !== backups) throw new Error("Backup outside workspace");
  fs.mkdirSync(backup, { recursive: true });
  const stage = path.join(backup, "staged"); fs.mkdirSync(stage);
  for (const file of manifest.files) {
    const output = safeFile(stage, file.path); fs.mkdirSync(path.dirname(output), { recursive: true });
    fs.copyFileSync(safeFile(source, file.path), output);
  }
  fs.copyFileSync(path.join(source, "manifest.json"), path.join(stage, "manifest.json"));
  validateArtifact(stage, manifest);
  const journal = { target, manifest, hadPrevious: fs.existsSync(target), status: "prepared" };
  const journalPath = path.join(backup, "journal.json");
  const save = () => fs.writeFileSync(journalPath, JSON.stringify(journal, null, 2));
  save();
  let previousSaved = false;
  let newInstalled = false;
  try {
    if (journal.hadPrevious) { fs.renameSync(target, path.join(backup, "previous")); previousSaved = true; }
    journal.status = "previous-saved"; save();
    fs.renameSync(stage, target);
    newInstalled = true;
    validateArtifact(target, manifest);
    journal.status = "deployed"; save();
  } catch (error) {
    if (newInstalled) fs.renameSync(target, path.join(backup, "failed-install"));
    if (previousSaved) fs.renameSync(path.join(backup, "previous"), target);
    journal.status = "rolled-back"; save(); throw error;
  }
  console.log(JSON.stringify({ deployed: true, target, buildId: manifest.buildId, backupId: id, backupRoot: backups }));
}
