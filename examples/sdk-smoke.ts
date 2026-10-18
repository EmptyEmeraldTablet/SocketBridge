import { BridgeServer, Recorder } from "../dist/host/index.js";
import fs from "node:fs";
const config = JSON.parse(fs.readFileSync(new URL("../config.local.json", import.meta.url), "utf8"));
const bridge = new BridgeServer({ port: config.port, token: config.token });
const recorder = new Recorder(bridge, `runs/sdk-${Date.now()}/messages.jsonl`);
bridge.on("event", event => console.log(event.payload.name, event.payload.data));
try {
  await bridge.listen();
  await bridge.waitReady(120000);
  await bridge.waitForRuntime({ inGame: true }, 120000);
  await bridge.request("runtime.pause");
  const before = await bridge.snapshot(["players", "room"]);
  await bridge.step(5);
  const after = await bridge.snapshot(["players", "room"]);
  if (after.updateTick - before.updateTick !== 5) throw new Error("Unexpected update count");
  console.log({ before, after });
} finally {
  try {
    if (bridge.connected) {
      try { await bridge.request("input.clear"); }
      finally { await bridge.request("runtime.resume"); }
    }
  } finally {
    try { await bridge.close(); }
    finally { await recorder.close(); }
  }
}
