import test from "node:test";
import assert from "node:assert/strict";
import { connect } from "node:net";
import { once } from "node:events";
import { JsonLines } from "../dist/host/framing.js";
import { BridgeServer } from "../dist/host/server.js";
import { StateStore } from "../dist/host/state.js";
import { validateCommand } from "../dist/protocol/validate.js";
import { readPath, reportExitCode, runScenario } from "../dist/host/scenario.js";
import { snapshotValue } from "../dist/host/schema.js";
import { Recorder } from "../dist/host/recorder.js";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

async function fixture(t, onCommand = () => {}) {
  const bridge = new BridgeServer({ port: 0, token: "test-token", heartbeatMs: 50 });
  const port = await bridge.listen();
  t.after(() => bridge.close());
  const socket = connect(port, "127.0.0.1");
  socket.on("error", () => {});
  t.after(() => socket.destroy());
  await once(socket, "connect");
  const framing = new JsonLines();
  const peer = { seq: 0, sessionId: "", connectionId: "", send(kind, payload, requestId) {
    socket.write(JSON.stringify({ protocol: "socketbridge/4", sessionId: peer.sessionId, connectionId: peer.connectionId,
      seq: ++peer.seq, runEpoch: 1, roomEpoch: 1, updateTick: 0, renderTick: 0, kind, payload, requestId }) + "\n");
  }, socket };
  socket.on("data", chunk => {
    for (const message of framing.feed(chunk)) {
      if (message.kind === "welcome") { peer.sessionId = message.sessionId; peer.connectionId = message.connectionId; peer.send("ready", {}); }
      else if (message.kind === "command") onCommand(message, peer);
      else if (message.kind === "heartbeat") peer.send("heartbeat", {});
    }
  });
  const ready = bridge.waitReady(1000);
  socket.write(JSON.stringify({ protocol: "socketbridge/4", kind: "hello", payload: { token: "test-token", buildId: "fixture" } }) + "\n");
  await ready;
  return { bridge, peer, port };
}

test("JSONL framing supports every split boundary including multibyte UTF-8", () => {
  const wire = Buffer.from('{"text":"以撒"}\n{"n":2}\n');
  for (let at = 1; at < wire.length; at++) {
    const framing = new JsonLines();
    assert.deepEqual([...framing.feed(wire.subarray(0, at)), ...framing.feed(wire.subarray(at))], [{ text: "以撒" }, { n: 2 }]);
  }
  assert.throws(() => new JsonLines().feed(Buffer.alloc(262145, 65)), /large/);
  assert.throws(() => new JsonLines().feed(Buffer.from([0xff, 10])), /encoded|encoding/i);
});

test("command validator rejects malformed objects, unknown commands and unbounded actions", () => {
  assert.equal(validateCommand({ method: "runtime.pause", args: {}, timeoutMs: 1000 }), undefined);
  for (const command of [
    { method: "runtime.pause", args: [], timeoutMs: 1000 },
    { method: "runtime.step", args: { ticks: 0 }, timeoutMs: 1000 },
    { method: "eval", args: {}, timeoutMs: 1000 },
    { method: "input.pulse", args: { playerIndex: 0, action: 1, value: 1, ticks: Infinity }, timeoutMs: 1000 },
  ]) assert.notEqual(validateCommand(command), undefined);
});

test("requests complete by id, not arrival order; accepted is not completed", async t => {
  const requests = [];
  const { bridge } = await fixture(t, (message, peer) => {
    requests.push(message);
    peer.send("result", { status: "accepted" }, message.requestId);
    if (requests.length === 2) {
      peer.send("result", { status: "completed", result: { method: requests[1].payload.method } }, requests[1].requestId);
      peer.send("result", { status: "completed", result: { method: requests[0].payload.method } }, requests[0].requestId);
    }
  });
  const [a, b] = await Promise.all([bridge.request("runtime.describe"), bridge.request("runtime.pause")]);
  assert.equal(a.result.method, "runtime.describe"); assert.equal(b.result.method, "runtime.pause");
});

test("timeout and disconnect reject with unknown outcome, never auto-replay", async t => {
  let requests = 0;
  const { bridge, peer } = await fixture(t, () => { requests++; });
  await assert.rejects(bridge.request("runtime.pause", {}, 50), error => error.code === "TIMEOUT" && error.outcome === "unknown");
  const pending = bridge.request("runtime.describe");
  peer.socket.destroy();
  await assert.rejects(pending, error => error.code === "DISCONNECTED" && error.outcome === "unknown");
  assert.ok(requests <= 2);
});

test("unrelated/bad second connection cannot evict current owner", async t => {
  const { bridge, port } = await fixture(t, (message, peer) => peer.send("result", { status: "completed", result: {} }, message.requestId));
  const original = bridge.sessionId;
  const second = connect(port, "127.0.0.1"); second.on("error", () => {});
  await once(second, "connect");
  const closed = once(second, "close");
  second.write(JSON.stringify({ protocol: "socketbridge/4", kind: "hello", payload: { token: "test-token" } }) + "\n");
  await closed;
  assert.equal(bridge.sessionId, original);
  await bridge.request("runtime.describe");
});

test("sequence gap invalidates connection and in-flight evidence", async t => {
  const { bridge, peer } = await fixture(t);
  const pending = bridge.request("runtime.describe");
  peer.seq += 2; peer.send("heartbeat", {});
  await assert.rejects(pending, /disconnected/);
  assert.equal(bridge.connected, false);
});

test("state scopes replace empty collections and cannot survive room transition", () => {
  const store = new StateStore();
  const snapshot = { runEpoch: 1, roomEpoch: 1, updateTick: 3, renderTick: 6, mode: "replace", complete: true, sensors: { pickups: { status: "ok", sampleTick: 3, data: [{ id: 1 }] } } };
  store.apply(snapshot);
  store.apply({ ...snapshot, sensors: { pickups: { status: "ok", sampleTick: 4, data: [] } } });
  assert.deepEqual(store.get("pickups", 4, 0).data, []);
  assert.equal(store.get("pickups", 10, 1), undefined);
  store.observeClock({ ...snapshot, roomEpoch: 2 });
  store.apply(snapshot); // A delayed old response must not resurrect the old room.
  assert.equal(store.get("pickups", 4, 10), undefined);
});

test("snapshot cannot claim complete when a required sensor is missing or errored", () => {
  const base = { runEpoch: 1, roomEpoch: 1, updateTick: 3, renderTick: 4, mode: "replace", complete: true, sensors: {} };
  assert.throws(() => snapshotValue(base, ["players"]), /omitted/);
  assert.throws(() => snapshotValue({ ...base, sensors: { players: { status: "error", sampleTick: 3 } } }), /completeness/);
  assert.throws(() => snapshotValue({ ...base, sensors: { players: { status: "ok", sampleTick: 3 } } }), /omitted data/);
});

test("closing a listener cancels pending readiness without waiting for the long timeout", async () => {
  const bridge = new BridgeServer({ port: 0, token: "x" });
  await bridge.listen();
  const waiting = bridge.waitReady(120000);
  const rejected = assert.rejects(waiting, error => error.code === "CLOSED");
  await bridge.close(); await rejected;
});

test("scenario independent assertion fails even if all commands completed; cleanup still runs", async t => {
  const methods = [];
  const { bridge } = await fixture(t, (message, peer) => { methods.push(message.payload.method); peer.send("result", { status: "completed", result: { value: 1 } }, message.requestId); });
  const report = await runScenario(bridge, { id: "negative", steps: [
    { id: "query", op: "command", method: "runtime.describe" }, { op: "assert", path: "query.result.value", equals: 2 },
  ] });
  assert.equal(report.status, "FAIL"); assert.equal(reportExitCode(report), 2);
  assert.deepEqual(methods, ["runtime.describe", "input.clear", "runtime.resume"]);
});

test("unsafe paths and empty assertions are configuration errors", async t => {
  assert.throws(() => readPath({}, "__proto__.value"), /Unsafe/);
  const { bridge } = await fixture(t, (m, p) => p.send("result", { status: "completed", result: {} }, m.requestId));
  const report = await runScenario(bridge, { id: "invalid", steps: [{ op: "assert", actual: 1 }] });
  assert.equal(report.status, "ERROR"); assert.equal(reportExitCode(report), 1);
  assert.equal(reportExitCode({ ...report, cleanup: { status: "failed", errors: ["lost"] } }), 4);
});

test("rejecting an oversized command does not consume a wire sequence number", async t => {
  const sequences = [];
  const { bridge } = await fixture(t, (m, p) => { sequences.push(m.seq); p.send("result", { status: "completed", result: {} }, m.requestId); });
  assert.equal(bridge.capabilities.token, undefined);
  await assert.rejects(bridge.request("mod.observe", { modId: "test", name: "state", params: { large: "x".repeat(270000) } }), error => error.code === "MESSAGE_TOO_LARGE");
  await bridge.request("runtime.describe");
  assert.deepEqual(sequences, [2]); // welcome was seq 1; rejected local payload was never sent.
});

test("recording failure closes the connection and cannot report successful evidence", async t => {
  const { bridge } = await fixture(t);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "socketbridge-recorder-"));
  const file = path.join(dir, "existing.jsonl"); fs.writeFileSync(file, "original");
  const closed = once(bridge, "closed");
  const recorder = new Recorder(bridge, file);
  await closed;
  await assert.rejects(recorder.close(), /EEXIST/);
  await assert.rejects(recorder.close(), /EEXIST/);
  assert.equal(fs.readFileSync(file, "utf8"), "original");
});

test("eventually propagates its wall budget and rejects a late successful snapshot", async t => {
  let budget;
  const { bridge } = await fixture(t, (m, p) => {
    if (m.payload.method === "state.snapshot") {
      budget = m.payload.timeoutMs;
      setTimeout(() => p.send("result", { status: "completed", result: {
        runEpoch: 1, roomEpoch: 1, updateTick: 0, renderTick: 0, mode: "replace", complete: true,
        sensors: { players: { status: "ok", sampleTick: 0, data: [] } },
      } }, m.requestId), 120);
    } else p.send("result", { status: "completed", result: {} }, m.requestId);
  });
  const report = await runScenario(bridge, { id: "bounded", steps: [
    { op: "eventually", sensors: ["players"], path: "sensors.players.data", equals: [], maxTicks: 2, timeoutMs: 80 },
  ] });
  assert.equal(report.status, "ERROR");
  assert.match(report.error, /deadline/); assert.ok(budget <= 80);
});

test("transport ready does not bypass run and target-mod initialization gates", async t => {
  let queries = 0;
  const { bridge } = await fixture(t, (m, p) => {
    queries++;
    p.send("result", { status: "completed", result: { inGame: queries >= 2,
      adapters: { target: "1" }, adapterReadiness: { target: queries >= 3 } } }, m.requestId);
  });
  assert.equal(bridge.connected, true);
  const ready = await bridge.waitForRuntime({ inGame: true, adapters: ["target"] }, 1500);
  assert.equal(queries, 3); assert.equal(ready.adapterReadiness.target, true);
});

test("event overflow during the final action cannot pass an otherwise successful scenario", async t => {
  const { bridge } = await fixture(t, (m, p) => {
    if (m.payload.method === "runtime.describe") for (let i = 0; i < 4097; i++) p.send("event", { name: "burst", data: {} });
    p.send("result", { status: "completed", result: {} }, m.requestId);
  });
  const report = await runScenario(bridge, { id: "overflow", steps: [{ op: "command", method: "runtime.describe" }] });
  assert.equal(report.status, "ERROR"); assert.match(report.error, /evidence incomplete/);
});
