import { ModCallback } from "isaac-typescript-definitions";
import { RuntimeBridge, type RuntimeConfig } from "./bridge";
import type { RecordValue } from "../protocol/types";

interface SocketLibrary { tcp(this: void): BridgeSocket; gettime(this: void): number; }
function diagnostic(message: string): void { Isaac.DebugString(message); print(message); }
export function main(): void {
  const mod = RegisterMod("SocketBridge v4", 1);
  if (REPENTOGON === undefined || REPENTOGON === false) { diagnostic("[SocketBridgeV4] REPENTOGON required; bridge disabled"); return; }
  const [hasSocket, library] = pcall(() => require("socket.core"));
  if (!hasSocket) { diagnostic("[SocketBridgeV4] socket.core unavailable: " + tostring(library)); return; }
  const [hasConfig, loaded] = pcall(() => require("socketbridge_v4.config"));
  if (!hasConfig) { diagnostic("[SocketBridgeV4] missing config; deploy the complete mod/ artifact"); return; }
  const config = loaded as RuntimeConfig;
  if (type(config.token) !== "string" || type(config.port) !== "number") { diagnostic("[SocketBridgeV4] invalid config"); return; }
  config.buildId = "__SOCKETBRIDGE_BUILD_ID__";
  const socket = library as SocketLibrary;
  const bridge = new RuntimeBridge(config, () => socket.tcp(), () => socket.gettime() * 1000);
  const event = (name: string, data: RecordValue, phase: string) => bridge.event(name, data, phase);
  // Keep the standard Isaac callback hidden-self convention. Never enable global noImplicitSelf.
  mod.AddCallback(ModCallback.POST_GAME_STARTED, (_continued: boolean) => bridge.gameStarted(_continued));
  mod.AddCallback(ModCallback.POST_NEW_ROOM, () => bridge.roomChanged());
  mod.AddCallback(ModCallback.PRE_GAME_EXIT, () => bridge.gameExit());
  mod.AddCallback(ModCallback.POST_UPDATE, () => bridge.postUpdate());
  mod.AddCallback(ModCallback.POST_RENDER, () => bridge.render());
  mod.AddCallback(ModCallback.INPUT_ACTION, (entity: Entity | undefined, hook: number, action: number) => bridge.inputValue(entity, hook, action));
  mod.AddCallback(ModCallback.POST_ENTITY_REMOVE, (entity: Entity) => {
    const entityRef = bridge.engine.removed(entity);
    if (entityRef) event("entity.removed", { entityRef, type: entity.Type, variant: entity.Variant, subtype: entity.SubType }, "MC_POST_ENTITY_REMOVE");
  });
  mod.AddCallback(ModCallback.POST_NPC_DEATH, (npc: EntityNPC) => event("npc.died", { entityRef: bridge.engine.entityRef(npc), type: npc.Type }, "MC_POST_NPC_DEATH"));
  mod.AddCallback(ModCallback.POST_PICKUP_INIT, (pickup: EntityPickup) => event("pickup.initialized", {
    entityRef: bridge.engine.entityRef(pickup), variant: pickup.Variant, subtype: pickup.SubType,
  }, "MC_POST_PICKUP_INIT"));
  function extended(name: string, fn: (...args: any[]) => unknown): void {
    const id = ModCallbacks[name];
    if (id !== undefined) (mod as unknown as { AddCallback(id: number, fn: (...args: any[]) => unknown): void }).AddCallback(id, fn);
  }
  extended("MC_PRE_UPDATE", () => bridge.preUpdate());
  extended("MC_MAIN_MENU_RENDER", () => bridge.render());
  extended("MC_POST_ENTITY_TAKE_DMG", (entity: Entity, damage: number, flags: unknown, source: EntityRef, countdown: number, extraSource?: EntityRef) => {
    if (!bridge.engine.inGame) return;
    const data: RecordValue = { entityRef: bridge.engine.entityRef(entity), damage, flags: tostring(flags), countdown,
      hitPointsAtCallback: entity.HitPoints, sourceType: source.Type,
      sourceRef: source.Entity !== undefined ? bridge.engine.entityRef(source.Entity) : undefined,
      extraSourceRef: extraSource?.Entity !== undefined ? bridge.engine.entityRef(extraSource.Entity) : undefined };
    const player = entity.ToPlayer();
    if (player !== undefined) data.healthAtCallback = { redHalfHearts: player.GetHearts(), soulHalfHearts: player.GetSoulHearts() };
    event("entity.damageApplied", data, "MC_POST_ENTITY_TAKE_DMG");
  });
  extended("MC_POST_ADD_COLLECTIBLE", (itemId: number, charge: number, firstTime: boolean, slot: number, varData: number, player: EntityPlayer) => {
    event("collectible.added", { itemId, charge, firstTime, slot, varData, playerIndex: bridge.engine.playerIndex(player) }, "MC_POST_ADD_COLLECTIBLE");
  });
  extended("MC_POST_USE_ITEM", (itemId: number, _rng: RNG, player: EntityPlayer, flags: unknown, slot: number, varData: number) => {
    event("item.used", { itemId, playerIndex: bridge.engine.playerIndex(player), flags: tostring(flags), slot, varData }, "MC_POST_USE_ITEM");
  });
  diagnostic("[SocketBridgeV4] loaded build=" + config.buildId + " port=" + tostring(config.port));
}
