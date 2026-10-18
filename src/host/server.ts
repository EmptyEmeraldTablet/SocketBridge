import { createServer, type Server, type Socket } from "node:net";
import { randomUUID } from "node:crypto";
import { EventEmitter } from "node:events";
import { JsonLines } from "./framing.js";
import { StateStore } from "./state.js";
import { PROTOCOL, MAX_BUFFER_BYTES, MAX_LINE_BYTES, type Clock, type Envelope, type RecordValue, type Snapshot } from "../protocol/types.js";
import { command, integer, isRecord, textValue } from "../protocol/validate.js";
import { snapshotValue } from "./schema.js";

export class BridgeError extends Error {
  constructor(public readonly code: string, message: string, public readonly outcome: "known" | "unknown" = "known") { super(message); }
}
interface Peer {
  socket: Socket; sessionId: string; connectionId: string; rxSeq: number; txSeq: number;
  lastReceived: number; ready: boolean;
}
interface Pending {
  resolve: (value: RecordValue) => void; reject: (error: Error) => void;
  timer: NodeJS.Timeout; method: string;
}
export interface BridgeOptions { port?: number; token: string; heartbeatMs?: number; leaseMs?: number; }
export interface RuntimeRequirements { inGame?: boolean; adapters?: string[]; }
export class BridgeServer extends EventEmitter {
  private server?: Server;
  private peer?: Peer;
  private sockets = new Set<Socket>();
  private pending = new Map<string, Pending>();
  private heartbeat?: NodeJS.Timeout;
  private clock: Clock = { runEpoch: 0, roomEpoch: 0, updateTick: 0, renderTick: 0 };
  readonly state = new StateStore();
  capabilities: RecordValue = {};
  constructor(private readonly options: BridgeOptions) {
    super();
    if (!textValue(options.token, 256)) throw new Error("Nonempty token required");
  }
  get connected(): boolean { return this.peer?.ready === true; }
  get sessionId(): string | undefined { return this.peer?.sessionId; }
  get currentClock(): Clock { return { ...this.clock }; }
  async listen(): Promise<number> {
    if (this.server) throw new Error("Already listening");
    const server = createServer(socket => this.accept(socket));
    this.server = server;
    await new Promise<void>((resolve, reject) => {
      server.once("error", reject);
      server.listen(this.options.port ?? 9527, "127.0.0.1", () => { server.off("error", reject); resolve(); });
    });
    server.on("error", error => this.emit("fault", error));
    this.heartbeat = setInterval(() => {
      const peer = this.peer;
      if (!peer) return;
      if (Date.now() - peer.lastReceived > (this.options.leaseMs ?? 8000)) peer.socket.destroy(new Error("Heartbeat expired"));
      else {
        try { this.send("heartbeat", {}); }
        catch (error) { this.emit("fault", error); peer.socket.destroy(); }
      }
    }, this.options.heartbeatMs ?? 1000);
    this.heartbeat.unref();
    return (server.address() as { port: number }).port;
  }
  private accept(socket: Socket): void {
    if (this.sockets.size >= 16) { socket.destroy(); return; }
    this.sockets.add(socket);
    socket.setNoDelay(true);
    const framing = new JsonLines();
    let peer: Peer | undefined;
    const helloDeadline = setTimeout(() => socket.destroy(new Error("Handshake timeout")), 5000);
    socket.on("data", chunk => {
      try {
        for (const raw of framing.feed(chunk)) {
          if (!peer) {
            if (!isRecord(raw) || raw.protocol !== PROTOCOL || raw.kind !== "hello" || !isRecord(raw.payload)
              || raw.payload.token !== this.options.token) throw new Error("Invalid hello/token/protocol");
            if (this.peer) throw new Error("A game already owns this bridge");
            clearTimeout(helloDeadline);
            peer = { socket, sessionId: randomUUID(), connectionId: randomUUID(), rxSeq: 0, txSeq: 0, lastReceived: Date.now(), ready: false };
            this.peer = peer;
            this.state.clear();
            this.clock = { runEpoch: 0, roomEpoch: 0, updateTick: 0, renderTick: 0 };
            const { token: _token, ...capabilities } = raw.payload;
            this.capabilities = capabilities;
            this.emit("connection", { sessionId: peer.sessionId, connectionId: peer.connectionId });
            this.emit("record", { direction: "in", message: { ...raw, payload: { ...raw.payload, token: "[redacted]" } } });
            this.send("welcome", {});
            continue;
          }
          this.receive(peer, raw);
        }
      } catch (error) { socket.destroy(error instanceof Error ? error : new Error(String(error))); }
    });
    socket.on("error", error => this.emit("fault", error));
    socket.on("close", () => {
      clearTimeout(helloDeadline);
      this.sockets.delete(socket);
      if (this.peer !== peer || !peer) return;
      this.peer = undefined;
      this.capabilities = {};
      this.state.clear();
      this.rejectPending(new BridgeError("DISCONNECTED", "Game disconnected; in-flight effects may have executed", "unknown"));
      this.emit("disconnect", { sessionId: peer.sessionId });
    });
  }
  private receive(peer: Peer, raw: unknown): void {
    if (!isRecord(raw) || raw.protocol !== PROTOCOL || raw.sessionId !== peer.sessionId
      || raw.connectionId !== peer.connectionId || !integer(raw.seq, 1, Number.MAX_SAFE_INTEGER)
      || raw.seq !== peer.rxSeq + 1 || !textValue(raw.kind, 64) || !isRecord(raw.payload)) throw new Error("Invalid envelope or sequence gap");
    for (const field of ["runEpoch", "roomEpoch", "updateTick", "renderTick"]) {
      if (!integer(raw[field], 0, Number.MAX_SAFE_INTEGER)) throw new Error("Invalid clock");
    }
    const message = raw as unknown as Envelope;
    if (message.runEpoch < this.clock.runEpoch || message.roomEpoch < this.clock.roomEpoch
      || (message.runEpoch === this.clock.runEpoch && message.updateTick < this.clock.updateTick)
      || message.renderTick < this.clock.renderTick) throw new Error("Clock regressed within session");
    peer.rxSeq = message.seq;
    peer.lastReceived = Date.now();
    this.clock = { runEpoch: message.runEpoch, roomEpoch: message.roomEpoch, updateTick: message.updateTick, renderTick: message.renderTick };
    this.state.observeClock(this.clock);
    this.emit("record", { direction: "in", message });
    if (message.kind === "ready") { peer.ready = true; this.emit("ready", message.payload); }
    else if (message.kind === "result") {
      if (!textValue(message.requestId, 128)) throw new Error("Result missing requestId");
      const pending = this.pending.get(message.requestId);
      if (message.payload.status === "accepted") return;
      if (!["completed", "failed", "cancelled"].includes(String(message.payload.status))) throw new Error("Invalid result status");
      if (!pending) { this.emit("lateResult", message); return; }
      clearTimeout(pending.timer);
      this.pending.delete(message.requestId);
      if (message.payload.status === "completed") pending.resolve(message.payload);
      else pending.reject(new BridgeError(String(message.payload.code ?? "COMMAND_FAILED"), String(message.payload.error ?? message.payload.status)));
    } else if (message.kind === "telemetry") {
      const snapshot = snapshotValue(message.payload.snapshot);
      if (snapshot.runEpoch !== message.runEpoch || snapshot.roomEpoch !== message.roomEpoch || snapshot.updateTick !== message.updateTick) throw new Error("Snapshot epoch/tick mismatch");
      this.state.apply(snapshot);
    } else if (message.kind === "event") this.emit("event", message);
    else if (message.kind !== "heartbeat") throw new Error("Unknown message kind");
    this.emit("message", message);
  }
  private send(kind: string, payload: RecordValue, requestId?: string): void {
    const peer = this.peer;
    if (!peer) throw new BridgeError("NOT_CONNECTED", "No game connected");
    const message: Envelope = { protocol: PROTOCOL, sessionId: peer.sessionId, connectionId: peer.connectionId,
      seq: peer.txSeq + 1, kind, requestId, payload, ...this.clock };
    const line = JSON.stringify(message) + "\n";
    if (Buffer.byteLength(line) > MAX_LINE_BYTES + 1) throw new BridgeError("MESSAGE_TOO_LARGE", "Command exceeds protocol limit");
    if (peer.socket.writableLength + Buffer.byteLength(line) > MAX_BUFFER_BYTES) {
      peer.socket.destroy(new Error("TX backpressure limit"));
      throw new BridgeError("BACKPRESSURE", "Game is not reading", "unknown");
    }
    peer.txSeq++;
    peer.socket.write(line);
    this.emit("record", { direction: "out", message });
  }
  request(method: string, args: RecordValue = {}, timeoutMs = 5000): Promise<RecordValue> {
    const validated = command(method, args, timeoutMs);
    if (!this.connected) return Promise.reject(new BridgeError("NOT_READY", "Wait for ready before commands"));
    if (this.pending.size >= 128) return Promise.reject(new BridgeError("BUSY", "Too many pending commands"));
    const requestId = randomUUID();
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(requestId);
        reject(new BridgeError("TIMEOUT", `${method} timed out; outcome is unknown`, "unknown"));
      }, timeoutMs + 250);
      this.pending.set(requestId, { resolve, reject, timer, method });
      try { this.send("command", validated as unknown as RecordValue, requestId); }
      catch (error) { clearTimeout(timer); this.pending.delete(requestId); reject(error); }
    });
  }
  waitReady(timeoutMs = 30000): Promise<void> {
    if (this.connected) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const cleanup = () => { clearTimeout(timer); this.off("ready", ready); this.off("closed", closed); };
      const timer = setTimeout(() => { cleanup(); reject(new BridgeError("CONNECT_TIMEOUT", "No runtime ready")); }, timeoutMs);
      const ready = () => { cleanup(); resolve(); };
      const closed = () => { cleanup(); reject(new BridgeError("CLOSED", "Bridge closed before ready")); };
      this.once("ready", ready);
      this.once("closed", closed);
    });
  }
  /** Transport readiness, run initialization and target-mod readiness are separate gates. */
  async waitForRuntime(requirements: RuntimeRequirements = { inGame: true }, timeoutMs = 30000): Promise<RecordValue> {
    if (!integer(timeoutMs, 50, 3600000) || (requirements.inGame !== undefined && typeof requirements.inGame !== "boolean")
      || (requirements.adapters !== undefined && (!Array.isArray(requirements.adapters) || requirements.adapters.length > 64
        || requirements.adapters.some(id => !textValue(id, 96))))) throw new Error("Invalid runtime readiness requirements");
    const deadline = Date.now() + timeoutMs;
    await this.waitReady(timeoutMs);
    const session = this.sessionId;
    while (Date.now() + 50 <= deadline) {
      if (!this.connected || this.sessionId !== session) throw new BridgeError("SESSION_LOST", "Readiness session changed");
      const response = await this.request("runtime.describe", {}, Math.min(5000, deadline - Date.now()));
      const identity = response.result;
      if (!isRecord(identity)) throw new BridgeError("INVALID_IDENTITY", "runtime.describe did not return an object");
      const adaptersReady = (requirements.adapters ?? []).every(id => isRecord(identity.adapters) && Object.hasOwn(identity.adapters, id)
        && isRecord(identity.adapterReadiness) && identity.adapterReadiness[id] === true);
      if (Date.now() <= deadline && (requirements.inGame === undefined || identity.inGame === requirements.inGame) && adaptersReady) return identity;
      await new Promise(resolve => setTimeout(resolve, Math.min(100, Math.max(0, deadline - Date.now()))));
    }
    throw new BridgeError("RUNTIME_NOT_READY", "Run or required mod adapters did not become ready before deadline");
  }
  async snapshot(sensors: string[], timeoutMs = 5000): Promise<Snapshot> {
    const response = await this.request("state.snapshot", { sensors }, timeoutMs);
    const snapshot = snapshotValue(response.result, sensors);
    if (!snapshot || !snapshot.complete) throw new BridgeError("INCOMPLETE_SNAPSHOT", "Required sensor failed");
    if (snapshot.runEpoch !== this.clock.runEpoch || snapshot.roomEpoch !== this.clock.roomEpoch) throw new BridgeError("STALE_SNAPSHOT", "World changed while snapshot was in transit");
    this.state.apply(snapshot);
    return snapshot;
  }
  async step(ticks: number, timeoutMs = 10000): Promise<RecordValue> { return this.request("runtime.step", { ticks }, timeoutMs); }
  private rejectPending(error: Error): void {
    for (const pending of this.pending.values()) { clearTimeout(pending.timer); pending.reject(error); }
    this.pending.clear();
  }
  async close(): Promise<void> {
    clearInterval(this.heartbeat);
    this.emit("closed");
    this.rejectPending(new BridgeError("CLOSED", "Bridge closed", "unknown"));
    for (const socket of this.sockets) socket.destroy();
    const server = this.server;
    this.server = undefined;
    if (server) await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  }
}
