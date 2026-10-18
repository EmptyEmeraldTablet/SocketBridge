import type { Command, Envelope, Json, RecordValue } from "../protocol/types";
import { COMMAND_NAMES, PROTOCOL, SENSOR_NAMES } from "../protocol/types";
import { integer, textValue, validateCommand } from "../protocol/validate";
import { array, canonical, decode, encode, isList, isRecord, nullValue } from "./codec";
import { Engine } from "./engine";
import { InputController } from "./input";
import { StepController } from "./scheduler";
import { Adapters } from "./adapters";
import { Transport } from "./transport";

interface Request { id: string; command: Command; signature: string; deadline: number; runEpoch: number; roomEpoch: number; terminal?: RecordValue; }
export interface RuntimeConfig { port: number; token: string; allowConsole: boolean; buildId: string; }
export class RuntimeBridge {
  readonly engine = new Engine();
  readonly input = new InputController();
  readonly steps = new StepController();
  readonly adapters = new Adapters();
  readonly transport: Transport;
  runEpoch = 0; roomEpoch = 0; updateTick = 0; renderTick = 0;
  private executingTick?: number;
  private sessionId = ""; private connectionId = "";
  private rxSeq = 0; private txSeq = 0; private lastReceived = 0; private lastHeartbeat = 0;
  private requests = new LuaTable<string, Request>();
  private requestCount = 0;
  private retainedBytes = 0;
  private worldQueue: Request[] = [];
  private subscriptions: string[] = [];
  private intervalTicks = 15;
  private lastTelemetry = 0;
  private lastDiagnostic = -10000;
  constructor(private config: RuntimeConfig, factory: () => BridgeSocket, private now: () => number) {
    this.transport = new Transport(factory, config.port, {
      connected: () => {
        this.lastReceived = this.now();
        this.transport.enqueue(encode({ protocol: PROTOCOL, kind: "hello", payload: { token: config.token, ...this.describe() } }));
      },
      disconnected: reason => {
        this.sessionId = ""; this.connectionId = ""; this.rxSeq = 0; this.txSeq = 0;
        this.requests = new LuaTable(); this.requestCount = 0; this.retainedBytes = 0; this.worldQueue = [];
        this.subscriptions = []; this.input.clear(); this.steps.reset(); this.engine.reset();
        if (this.now() - this.lastDiagnostic >= 5000) { print("[SocketBridgeV4] disconnected: " + reason); this.lastDiagnostic = this.now(); }
      },
      line: line => this.receive(line),
    });
    this.adapters.expose((name, data) => this.event("mod." + name, data, "mod-adapter"));
  }
  clock() { return { runEpoch: this.runEpoch, roomEpoch: this.roomEpoch, updateTick: this.updateTick, renderTick: this.renderTick }; }
  describe(): RecordValue {
    return {
      buildId: this.config.buildId, protocol: PROTOCOL, repentogon: REPENTOGON !== undefined && REPENTOGON !== false,
      repentogonVersion: type(REPENTOGON) === "table" ? tostring((REPENTOGON as { Version?: string }).Version) : "unknown",
      phase: this.engine.inGame ? "in-run" : "outside-run", inGame: this.engine.inGame, pausedByBridge: this.steps.paused,
      capabilities: { preUpdate: ModCallbacks.MC_PRE_UPDATE !== undefined, postDamage: ModCallbacks.MC_POST_ENTITY_TAKE_DMG !== undefined,
        postAddCollectible: ModCallbacks.MC_POST_ADD_COLLECTIBLE !== undefined, postUseItem: ModCallbacks.MC_POST_USE_ITEM !== undefined,
        menuPump: ModCallbacks.MC_MAIN_MENU_RENDER !== undefined, console: this.config.allowConsole },
      sensors: array([...SENSOR_NAMES]), commands: array([...COMMAND_NAMES]), adapters: this.adapters.list(), adapterReadiness: this.adapters.readiness(),
    };
  }
  private send(kind: string, payload: RecordValue, requestId?: string): void {
    if (this.sessionId === "") return;
    const envelope: Envelope = { protocol: PROTOCOL, sessionId: this.sessionId, connectionId: this.connectionId,
      seq: ++this.txSeq, kind, payload, requestId, ...this.clock() };
    const [ok, line] = pcall(() => encode(envelope));
    if (!ok) { this.transport.close("ENCODE: " + tostring(line)); return; }
    this.transport.enqueue(line as string);
  }
  event(name: string, data: RecordValue, phase: string): void {
    this.send("event", { name, data, phase });
  }
  private receive(line: string): void {
    const message = decode(line);
    if (!isRecord(message) || message.protocol !== PROTOCOL || !isRecord(message.payload)) throw new Error("INVALID_PROTOCOL");
    if (this.sessionId === "") {
      if (message.kind !== "welcome" || !textValue(message.sessionId, 128) || !textValue(message.connectionId, 128) || message.seq !== 1) throw new Error("INVALID_WELCOME");
      this.sessionId = message.sessionId; this.connectionId = message.connectionId; this.rxSeq = 1;
      this.lastReceived = this.now(); this.lastHeartbeat = this.now();
      this.send("ready", this.describe());
      print("[SocketBridgeV4] ready session=" + this.sessionId + " build=" + this.config.buildId);
      return;
    }
    if (message.sessionId !== this.sessionId || message.connectionId !== this.connectionId || message.seq !== this.rxSeq + 1) throw new Error("SESSION_OR_SEQUENCE_MISMATCH");
    this.rxSeq++; this.lastReceived = this.now();
    if (message.kind === "heartbeat") return;
    if (message.kind !== "command" || !textValue(message.requestId, 128)
      || !integer(message.runEpoch, 0, 2147483647) || !integer(message.roomEpoch, 0, 2147483647)) throw new Error("INVALID_COMMAND_ENVELOPE");
    const id = message.requestId;
    const issue = validateCommand(message.payload, isRecord, isList);
    if (issue !== undefined) { this.send("result", { status: "failed", code: "INVALID_ARGUMENT", error: issue }, id); return; }
    const command = message.payload as unknown as Command;
    const signature = canonical(message.payload);
    const existing = this.requests.get(id);
    if (existing !== undefined) {
      if (existing.signature !== signature) this.send("result", { status: "failed", code: "REQUEST_ID_REUSED", error: "Different parameters for existing requestId" }, id);
      else this.send("result", existing.terminal ?? { status: "accepted" }, id);
      return;
    }
    if (this.requestCount >= 2048 || this.worldQueue.length >= 128 || this.retainedBytes + signature.length * 2 > 4194304) {
      this.send("result", { status: "failed", code: "SESSION_LIMIT", error: "Start a new connection/session" }, id); return;
    }
    const request: Request = { id, command, signature, deadline: this.now() + command.timeoutMs, runEpoch: message.runEpoch, roomEpoch: message.roomEpoch };
    this.requests.set(id, request); this.requestCount++;
    this.retainedBytes += signature.length * 2;
    this.send("result", { status: "accepted" }, id);
    const method = command.method;
    if (method === "runtime.describe" || method === "runtime.pause" || method === "runtime.resume" || method === "runtime.step"
      || method === "telemetry.subscribe" || method === "input.clear") this.execute(request);
    else {
      if (!this.engine.inGame) this.fail(request, "NOT_IN_GAME", "World commands require an active run");
      else if (ModCallbacks.MC_PRE_UPDATE === undefined) this.fail(request, "UNSUPPORTED", "World commands require REPENTOGON MC_PRE_UPDATE");
      else this.worldQueue.push(request);
    }
  }
  pump(): void {
    this.transport.pump(this.now());
    if (!this.transport.connected) return;
    if (this.now() - this.lastReceived > 6000) { this.transport.close("LEASE_EXPIRED"); return; }
    if (this.sessionId !== "" && this.now() - this.lastHeartbeat >= 1000) {
      this.lastHeartbeat = this.now(); this.send("heartbeat", {});
    }
    for (const [, request] of pairs(this.requests)) {
      if (request.terminal === undefined && this.now() > request.deadline) {
        this.input.remove(request.id);
        if (this.steps.requestId === request.id) this.steps.reset();
        this.fail(request, "DEADLINE_EXCEEDED", "Runtime deadline expired");
      }
    }
  }
  render(): void { this.renderTick++; this.pump(); }
  preUpdate(): boolean | undefined {
    this.pump();
    if (!this.engine.inGame) return;
    const pending = this.worldQueue;
    this.worldQueue = [];
    for (let i = 0; i < pending.length; i++) {
      const request = pending[i];
      if (request.terminal) continue;
      if (i >= 8) this.worldQueue.push(request);
      else this.execute(request);
    }
    if (this.steps.blockUpdate()) { this.executingTick = undefined; return true; }
    this.executingTick = this.updateTick + 1;
    return undefined;
  }
  postUpdate(): void {
    if (!this.engine.inGame) return;
    this.updateTick++;
    for (const id of this.input.finishTick(this.updateTick)) {
      const request = this.requests.get(id);
      if (request !== undefined) this.complete(request, { releasedAtTick: this.updateTick });
    }
    const finished = this.steps.afterUpdate();
    if (finished !== undefined) { const request = this.requests.get(finished); if (request !== undefined) this.complete(request, { paused: true, updateTick: this.updateTick }); }
    this.executingTick = undefined;
    if (this.subscriptions.length > 0 && this.sessionId !== "" && this.updateTick - this.lastTelemetry >= this.intervalTicks) {
      this.lastTelemetry = this.updateTick;
      this.send("telemetry", { snapshot: this.engine.snapshot(this.subscriptions, this.clock()) as unknown as Json });
    }
    this.pump();
  }
  inputValue(entity: Entity | undefined, hook: number, action: number): number | boolean | undefined {
    if (!entity || this.executingTick === undefined || !this.engine.inGame) return;
    const playerIndex = this.engine.playerIndex(entity);
    if (playerIndex === undefined) return;
    return this.input.value(playerIndex, action, hook, this.executingTick);
  }
  private execute(request: Request): void {
    const method = request.command.method;
    const globalControl = method === "runtime.describe" || method === "runtime.resume" || method === "input.clear" || method === "telemetry.subscribe";
    if (!globalControl && (request.runEpoch !== this.runEpoch || request.roomEpoch !== this.roomEpoch)) {
      this.fail(request, "STALE_WORLD", "Target run/room changed before command execution"); return;
    }
    const [ok, result] = pcall(() => this.dispatch(request));
    if (!ok) this.fail(request, "COMMAND_ERROR", tostring(result));
    else if (request.command.method !== "runtime.step" && request.command.method !== "input.pulse") this.complete(request, (result === undefined ? nullValue : result) as Json);
  }
  private dispatch(request: Request): Json | undefined {
    const { method, args: a } = request.command;
    switch (method) {
      case "runtime.describe": return this.describe();
      case "runtime.pause":
        this.requireStep(); this.engine.requireGame(); this.steps.pause(); return { paused: true };
      case "runtime.resume": {
        const id = this.steps.reset(); if (id) this.cancel(id, "Resumed before step completed");
        return { paused: false };
      }
      case "runtime.step":
        this.requireStep(); this.engine.requireGame(); this.steps.step(request.id, a.ticks as number); return;
      case "input.clear":
        for (const id of this.input.clear()) this.cancel(id, "Input cleared");
        return { cleared: true };
      case "telemetry.subscribe": {
        const names = a.sensors as string[];
        for (const name of names) if (!this.engine.supports(name)) throw new Error("UNSUPPORTED_SENSOR: " + name);
        this.subscriptions = names; this.intervalTicks = a.intervalTicks as number; this.lastTelemetry = this.updateTick;
        return { sensors: array([...names]), intervalTicks: this.intervalTicks };
      }
      case "state.snapshot": return this.engine.snapshot(a.sensors as string[], this.clock()) as unknown as Json;
      case "input.pulse":
        this.engine.player(a.playerIndex as number);
        this.input.add({ requestId: request.id, playerIndex: a.playerIndex as number, action: a.action as number,
          value: a.value as number, ticks: a.ticks as number, startTick: this.updateTick + 1 }); return;
      case "item.resolve": return this.engine.resolveItem(a.name as string);
      case "entity.spawn": {
        this.engine.requireGame();
        const entity = Isaac.Spawn(a.type as number, a.variant as number, a.subtype as number,
          Vector(a.x as number, a.y as number), Vector(0, 0), undefined);
        return { entityRef: this.engine.entityRef(entity), type: entity.Type, variant: entity.Variant, subtype: entity.SubType };
      }
      case "entity.remove": {
        const entity = this.engine.findEntity(a.entityRef as string);
        if (entity.ToPlayer() !== undefined) throw new Error("Cannot remove players");
        entity.Remove(); return { entityRef: a.entityRef, removed: true };
      }
      case "player.giveCollectible": case "player.removeCollectible":
        return this.engine.giveItem(a.playerIndex as number, a.itemId as number, method === "player.removeCollectible");
      case "mod.observe": case "mod.invoke":
        return this.adapters.call(a.modId as string, a.name as string, a.params as RecordValue, method === "mod.invoke");
      case "console.execute":
        this.engine.requireGame();
        if (!this.config.allowConsole) throw new Error("CONSOLE_DISABLED");
        return { output: Isaac.ExecuteCommand(a.command as string) };
      default: throw new Error("UNSUPPORTED_METHOD");
    }
  }
  private requireStep(): void { if (ModCallbacks.MC_PRE_UPDATE === undefined) throw new Error("UNSUPPORTED_PRE_UPDATE"); }
  private complete(request: Request, result: Json): void {
    if (request.terminal) return;
    // Validate before saving a terminal response, so custom adapters cannot poison the wire.
    const [ok, issue] = pcall(() => encode(result));
    if (!ok) { this.fail(request, "RESULT_ENCODING", tostring(issue)); return; }
    const bytes = (issue as string).length;
    if (bytes > 250000 || this.retainedBytes + bytes > 8388608) {
      this.fail(request, "RESULT_LIMIT", "Result/retention limit exceeded; action may already have executed"); return;
    }
    this.retainedBytes += bytes;
    request.terminal = { status: "completed", appliedAtTick: this.updateTick, result };
    this.send("result", request.terminal, request.id);
  }
  private fail(request: Request, code: string, error: string): void {
    if (request.terminal) return;
    request.terminal = { status: "failed", code, error }; this.send("result", request.terminal, request.id);
  }
  private cancel(id: string, reason: string): void {
    const request = this.requests.get(id);
    if (!request || request.terminal) return;
    request.terminal = { status: "cancelled", code: "CANCELLED", error: reason };
    this.send("result", request.terminal, id);
  }
  private cancelWorld(reason: string): void {
    this.input.clear(); this.steps.reset(); this.worldQueue = [];
    for (const [id, request] of pairs(this.requests)) if (!request.terminal) this.cancel(id, reason);
    this.engine.reset(); this.executingTick = undefined;
  }
  gameStarted(continued: boolean): void {
    this.cancelWorld("New run"); this.runEpoch++; this.roomEpoch++; this.updateTick = 0;
    this.lastTelemetry = 0; this.engine.inGame = true;
    this.event("game.started", { continued }, "MC_POST_GAME_STARTED");
  }
  roomChanged(): void {
    this.cancelWorld("Room changed"); this.roomEpoch++;
    this.event("room.entered", {}, "MC_POST_NEW_ROOM");
  }
  gameExit(): void {
    this.cancelWorld("Game exited"); this.engine.inGame = false; this.roomEpoch++;
    this.event("game.exited", {}, "MC_PRE_GAME_EXIT"); this.pump();
  }
}
