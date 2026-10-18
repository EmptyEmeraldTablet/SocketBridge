import { EntityType } from "isaac-typescript-definitions";
import type { CollectibleType } from "isaac-typescript-definitions";
import type { Clock, Json, RecordValue, SensorResult, Snapshot } from "../protocol/types";
import { SENSOR_NAMES } from "../protocol/types";
import { array, object } from "./codec";

const vec = (value: Readonly<Vector>): RecordValue => ({ x: value.X, y: value.Y });
interface EntityEntry { entity: Entity; ref: string; seed: number; }
interface RgonRoomDescriptor { GetDimension?: () => number; }
interface RgonPlayer { GetActiveMaxCharge?: (slot: number) => number; }

export class Engine {
  inGame = false;
  private counter = 0;
  private byPointer = new LuaTable<PtrHash, EntityEntry>();
  private byRef = new LuaTable<string, EntityEntry>();
  reset(): void { this.byPointer = new LuaTable(); this.byRef = new LuaTable(); }
  requireGame(): void { if (!this.inGame) throw new Error("NOT_IN_GAME"); }
  entityRef(entity: Entity): string {
    const pointer = GetPtrHash(entity);
    let entry: EntityEntry | undefined = this.byPointer.get(pointer);
    if (entry !== undefined && (entry.seed !== entity.InitSeed || !entry.entity.Exists())) {
      this.byRef.delete(entry.ref); entry = undefined;
    }
    if (!entry) {
      entry = { entity, ref: "entity-" + tostring(++this.counter), seed: entity.InitSeed };
      this.byPointer.set(pointer, entry); this.byRef.set(entry.ref, entry);
    }
    return entry.ref;
  }
  removed(entity: Entity): string | undefined {
    const entry = this.byPointer.get(GetPtrHash(entity));
    if (!entry) return;
    this.byPointer.delete(GetPtrHash(entity)); this.byRef.delete(entry.ref);
    return entry.ref;
  }
  findEntity(ref: string): Entity {
    this.requireGame();
    const entry = this.byRef.get(ref);
    if (!entry || !entry.entity.Exists()) throw new Error("STALE_ENTITY_REF");
    return entry.entity;
  }
  player(index: number): EntityPlayer {
    this.requireGame();
    if (index >= Game().GetNumPlayers()) throw new Error("PLAYER_NOT_FOUND");
    return Isaac.GetPlayer(index);
  }
  playerIndex(player: Entity): number | undefined {
    if (!this.inGame) return;
    for (let i = 0; i < Game().GetNumPlayers(); i++) if (GetPtrHash(Isaac.GetPlayer(i)) === GetPtrHash(player)) return i;
  }
  private players(inventory: boolean): Json[] {
    const rows = array<Json>();
    for (let i = 0; i < Game().GetNumPlayers(); i++) {
      const p = Isaac.GetPlayer(i);
      const row: RecordValue = { playerIndex: i, entityRef: this.entityRef(p), playerType: p.GetPlayerType() };
      if (!inventory) {
        row.position = vec(p.Position); row.velocity = vec(p.Velocity);
        row.aimDirection = vec(p.GetAimDirection());
        row.damage = p.Damage; row.moveSpeed = p.MoveSpeed; row.maxFireDelay = p.MaxFireDelay;
        row.tearRange = p.TearRange; row.shotSpeed = p.ShotSpeed; row.luck = p.Luck;
        row.canFly = p.CanFly; row.coins = p.GetNumCoins(); row.bombs = p.GetNumBombs(); row.keys = p.GetNumKeys();
        row.health = {
          redHalfHearts: p.GetHearts(), maxRedHalfHearts: p.GetMaxHearts(),
          soulHalfHearts: p.GetSoulHearts(), blackHeartMask: tostring(p.GetBlackHearts()),
          boneHearts: p.GetBoneHearts(), goldenHearts: p.GetGoldenHearts(), eternalHearts: p.GetEternalHearts(),
          rottenHearts: p.GetRottenHearts(), brokenHearts: p.GetBrokenHearts(), extraLives: p.GetExtraLives(),
        };
      } else {
        const config = Isaac.GetItemConfig();
        const size = config.GetCollectibles().Size;
        if (size > 100000) throw new Error("ITEM_CONFIG_TOO_LARGE");
        const items: RecordValue = object({});
        const effects: RecordValue = object({});
        for (let id = 1; id < size; id++) {
          if (config.GetCollectible(id as CollectibleType) === undefined) continue;
          const count = p.GetCollectibleNum(id as CollectibleType, true);
          if (count > 0) items[tostring(id)] = count;
          const effectCount = p.GetEffects().GetCollectibleEffectNum(id as CollectibleType);
          if (effectCount > 0) effects[tostring(id)] = effectCount;
        }
        row.collectibles = items; row.collectibleEffects = effects;
        row.collectibleCount = p.GetCollectibleCount(); row.itemConfigSize = size;
        row.trinkets = array([p.GetTrinket(0), p.GetTrinket(1)]);
        row.cards = array([p.GetCard(0), p.GetCard(1)]); row.pills = array([p.GetPill(0), p.GetPill(1)]);
        const slots = array<Json>();
        for (let slot = 0; slot < 4; slot++) {
          const item: RecordValue = { slot, itemId: p.GetActiveItem(slot), charge: p.GetActiveCharge(slot), batteryCharge: p.GetBatteryCharge(slot) };
          const extended = p as unknown as RgonPlayer;
          if (extended.GetActiveMaxCharge !== undefined) item.maxCharge = extended.GetActiveMaxCharge(slot);
          slots.push(item);
        }
        row.activeSlots = slots;
      }
      rows.push(row);
    }
    return rows;
  }
  private room(): RecordValue {
    const game = Game(); const level = game.GetLevel(); const room = game.GetRoom();
    const descriptor = level.GetCurrentRoomDesc();
    const extended = descriptor as unknown as RgonRoomDescriptor;
    return {
      stage: level.GetStage(), stageType: level.GetStageType(), roomIndex: level.GetCurrentRoomIndex(),
      dimension: extended.GetDimension !== undefined ? extended.GetDimension() : undefined,
      descriptorListIndex: descriptor.ListIndex, spawnSeed: room.GetSpawnSeed(), decorationSeed: room.GetDecorationSeed(),
      roomVariant: descriptor.Data?.Variant, roomType: room.GetType(), roomShape: room.GetRoomShape(),
      isClear: room.IsClear(), isFirstVisit: room.IsFirstVisit(), aliveEnemies: room.GetAliveEnemiesCount(),
      gridWidth: room.GetGridWidth(), gridHeight: room.GetGridHeight(), topLeft: vec(room.GetTopLeftPos()),
      bottomRight: vec(room.GetBottomRightPos()), difficulty: game.Difficulty,
      startSeed: game.GetSeeds().GetStartSeed(), engineFrame: game.GetFrameCount(), nativePaused: game.IsPaused(),
    };
  }
  private grid(): RecordValue {
    const room = Game().GetRoom(); const cells = array<Json>(); const doors = array<Json>();
    for (let i = 0; i < room.GetGridSize(); i++) {
      const grid = room.GetGridEntity(i);
      if (!grid) continue;
      cells.push({ index: i, type: grid.GetType(), variant: grid.GetVariant(), state: grid.State,
        collisionClass: grid.CollisionClass, position: vec(room.GetGridPosition(i)) });
    }
    for (let i = 0; i < 8; i++) {
      const door = room.GetDoor(i);
      if (door) doors.push({ slot: i, targetRoomIndex: door.TargetRoomIndex, targetRoomType: door.TargetRoomType,
        isOpen: door.IsOpen(), isLocked: door.IsLocked(), position: vec(door.Position) });
    }
    return { gridSize: room.GetGridSize(), cells, doors };
  }
  observeEntity(e: Entity): RecordValue {
    const sprite = e.GetSprite();
    const row: RecordValue = {
      entityRef: this.entityRef(e), index: e.Index, initSeed: e.InitSeed, type: e.Type, variant: e.Variant, subtype: e.SubType,
      position: vec(e.Position), velocity: vec(e.Velocity), positionOffset: vec(e.PositionOffset),
      size: e.Size, frameCount: e.FrameCount, hitPoints: e.HitPoints, maxHitPoints: e.MaxHitPoints,
      entityFlags: tostring(e.GetEntityFlags()), collisionClass: e.EntityCollisionClass,
      spawnerType: e.SpawnerType, spawnerVariant: e.SpawnerVariant,
      parentRef: e.Parent !== undefined ? this.entityRef(e.Parent) : undefined,
      sprite: { loaded: sprite.IsLoaded(), filename: sprite.GetFilename(), animation: sprite.GetAnimation(), frame: sprite.GetFrame(), scale: vec(sprite.Scale) },
    };
    const npc = e.ToNPC();
    if (npc !== undefined) {
      row.npc = { state: npc.State, stateFrame: npc.StateFrame, isActiveEnemy: e.IsActiveEnemy(false),
        isVulnerableEnemy: e.IsVulnerableEnemy(), isBoss: e.IsBoss(), isChampion: npc.IsChampion() };
    }
    const pickup = e.ToPickup();
    if (pickup !== undefined) row.pickup = { price: pickup.Price, shopItemId: pickup.ShopItemId, wait: pickup.Wait, touched: pickup.Touched };
    const projectile = e.ToProjectile();
    if (projectile !== undefined) row.projectile = { height: projectile.Height, fallingSpeed: projectile.FallingSpeed,
      fallingAccel: projectile.FallingAccel, scale: projectile.Scale, damage: projectile.Damage, flags: tostring(projectile.ProjectileFlags) };
    const tear = e.ToTear();
    if (tear !== undefined) row.tear = { height: tear.Height, fallingSpeed: tear.FallingSpeed, fallingAccel: tear.FallingAcceleration,
      scale: tear.Scale, collisionDamage: tear.CollisionDamage, flags: tostring(tear.TearFlags) };
    const laser = e.ToLaser();
    if (laser !== undefined) row.laser = { angleDegrees: laser.AngleDegrees, maxDistance: laser.MaxDistance,
      endPoint: vec(laser.GetEndPoint()), timeout: laser.Timeout, flags: tostring(laser.TearFlags) };
    const bomb = e.ToBomb();
    if (bomb !== undefined) row.bomb = { explosionDamage: bomb.ExplosionDamage, radiusMultiplier: bomb.RadiusMultiplier, flags: tostring(bomb.Flags) };
    const familiar = e.ToFamiliar();
    if (familiar !== undefined) row.familiar = { state: familiar.State, ownerRef: this.entityRef(familiar.Player) };
    // Slot entities stay raw entities. No NPC conversion or invented variant names.
    return row;
  }
  supports(name: string): boolean { for (const candidate of SENSOR_NAMES) if (candidate === name) return true; return false; }
  snapshot(names: string[], clock: Clock): Snapshot {
    const sensors: { [name: string]: SensorResult } = object({});
    let entities: Entity[] | undefined;
    let complete = true;
    for (const name of names) {
      if (!this.supports(name)) { sensors[name] = { status: "unsupported", sampleTick: clock.updateTick, error: "Unknown sensor" }; complete = false; continue; }
      const [ok, data] = pcall((): Json => {
        this.requireGame();
        if (name === "players") return this.players(false);
        if (name === "inventory") return this.players(true);
        if (name === "room") return this.room();
        if (name === "grid") return this.grid();
        if (!entities) entities = Isaac.GetRoomEntities();
        const rows = array<Json>();
        for (const entity of entities) {
          if (!entity.Exists()) continue;
          const t = entity.Type;
          const include = name === "entities" || (name === "npcs" && entity.ToNPC() !== undefined)
            || (name === "pickups" && t === EntityType.PICKUP) || (name === "projectiles" && t === EntityType.PROJECTILE)
            || (name === "tears" && t === EntityType.TEAR) || (name === "lasers" && t === EntityType.LASER)
            || (name === "bombs" && t === EntityType.BOMB) || (name === "familiars" && t === EntityType.FAMILIAR)
            || (name === "slots" && t === EntityType.SLOT) || (name === "effects" && t === EntityType.EFFECT);
          if (include) rows.push(this.observeEntity(entity));
        }
        return rows;
      });
      if (ok) sensors[name] = { status: "ok", sampleTick: clock.updateTick, data: data as Json };
      else { sensors[name] = { status: "error", sampleTick: clock.updateTick, error: tostring(data) }; complete = false; }
    }
    return { ...clock, mode: "replace", complete, sensors };
  }
  resolveItem(name: string): RecordValue {
    const id = Isaac.GetItemIdByName(name);
    if (id <= 0) throw new Error("ITEM_NOT_FOUND");
    return { itemId: id, name };
  }
  giveItem(playerIndex: number, itemId: number, remove: boolean): RecordValue {
    const p = this.player(playerIndex);
    if (!Isaac.GetItemConfig().GetCollectible(itemId as CollectibleType)) throw new Error("ITEM_NOT_FOUND");
    if (remove) p.RemoveCollectible(itemId as CollectibleType);
    else p.AddCollectible(itemId as CollectibleType);
    return { itemId, playerIndex, count: p.GetCollectibleNum(itemId as CollectibleType, true), operation: remove ? "removed" : "programmatically-added" };
  }
}
