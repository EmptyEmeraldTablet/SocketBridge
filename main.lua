--[[
    SocketBridge v3.0 — Sensor-based modular data collection framework

    Key improvements over v2.x:
    1. Sensors, not Collectors — each Sensor knows HOW to find entities
       (EntityPartition, FindInRadius, FindByType) instead of brute-force
       full-room traversal via Isaac.GetRoomEntities().
    2. Dynamic throttle — combat vs idle collection rates.
    3. Callback-driven triggers — MC_POST_NEW_ROOM, MC_POST_NPC_DEATH, etc.
    4. Subscription negotiation — Python tells Lua what data it needs.
    5. Runtime reconfiguration — CONFIGURE_SENSOR command.
    6. Dual frame counters (from EID) for accurate pause handling.

    Architecture:
    SensorRegistry → Protocol v3.0 → Network → Python
    Python → Network → CommandExecutor → Input injection / Sensor config
]]

local mod = RegisterMod("SocketBridge", 1)
local json = require("json")

-- ============================================================================
-- Configuration
-- ============================================================================
local Config = {
    HOST = "127.0.0.1",
    PORT = 9527,
    PROTOCOL_VERSION = "3.0",
    DEBUG = true,               -- Enable debug logging for data flow
    DEBUG_INTERVAL = 150,       -- Debug output every N frames (~5 sec)
}

-- ============================================================================
-- Global State
-- ============================================================================
local State = {
    connected = false,
    socket = nil,

    -- Dual counters (from EID pattern)
    updateCount = 0,       -- MC_POST_UPDATE (30 tps, respects pause)
    renderCount = 0,       -- MC_POST_RENDER (60 tps, ignores pause)

    -- Message sequencing
    messageSeq = 0,
    prevFrameSent = 0,

    -- Room tracking
    currentRoom = -1,
    roomEntered = false,

    -- Subscription
    subscribedSensors = {},  -- {["ENEMIES"] = true, ...}

    -- Control mode
    controlMode = "AUTO",    -- "MANUAL" | "AUTO" | "FORCE_AI"
    lastEnemyCount = 0,
    wasInCombat = false,
    aiActive = false,
    toggleCooldown = 0,
    showModeMessage = false,
    modeMessageTimer = 0,
}

-- ============================================================================
-- Helpers
-- ============================================================================
local Helpers = {}

function Helpers.vectorToTable(vec)
    if vec then return { x = vec.X, y = vec.Y } end
    return { x = 0, y = 0 }
end

function Helpers.getPlayers()
    local game = Game()
    local players = {}
    for i = 0, game:GetNumPlayers() - 1 do
        local player = Isaac.GetPlayer(i)
        if player then table.insert(players, player) end
    end
    return players
end

function Helpers.simpleHash(data)
    if type(data) ~= "table" then return tostring(data) end
    local str = ""
    for k, v in pairs(data) do
        if type(v) == "table" then str = str .. k .. Helpers.simpleHash(v)
        else str = str .. k .. tostring(v) end
    end
    return str
end

-- ============================================================================
-- Network Layer (unchanged from v2.x — proven stable)
-- ============================================================================
local Network = {
    retryInterval = 60,
    lastRetryFrame = 0,
}

function Network.connect()
    if State.connected then return true end
    if State.updateCount - Network.lastRetryFrame < Network.retryInterval then
        return false
    end
    Network.lastRetryFrame = State.updateCount

    local requireOk, socketMod = pcall(function()
        return require("socket.core")
    end)
    if not requireOk then
        if State.updateCount <= 60 then
            print("[SocketBridge] ERROR: require('socket.core') failed: " .. tostring(socketMod))
            print("[SocketBridge] Ensure --luadebug launch option is enabled in Steam")
        end
        return false
    end

    local success, tcp = pcall(function()
        local s = socketMod
        local t = s.tcp()
        t:settimeout(0.01)
        local r = t:connect(Config.HOST, Config.PORT)
        return t, r
    end)

    if success and tcp then
        State.socket = tcp
        State.connected = true
        print("[SocketBridge] Connected to " .. Config.HOST .. ":" .. Config.PORT)
        return true
    end

    if State.updateCount <= 60 then
        if not success then
            print("[SocketBridge] Connection attempt failed: " .. tostring(tcp))
        else
            print("[SocketBridge] Connection refused — Python server not running?")
        end
    end
    return false
end

function Network.disconnect()
    if State.socket then
        pcall(function() State.socket:close() end)
        State.socket = nil
    end
    State.connected = false
end

function Network.send(data)
    if not State.connected then return false end
    local success, err = pcall(function()
        local payload = json.encode(data) .. "\n"
        State.socket:send(payload)
    end)
    if not success then Network.disconnect(); return false end
    return true
end

function Network.receive()
    if not State.connected then return nil end
    local success, line, err = pcall(function()
        return State.socket:receive("*l")
    end)
    if success and line then
        local ok, data = pcall(json.decode, line)
        if ok then return data end
    elseif err == "closed" then
        Network.disconnect()
    end
    return nil
end

-- ============================================================================
-- Protocol v3.0
-- ============================================================================
local Protocol = {
    VERSION = Config.PROTOCOL_VERSION,
    MessageType = {
        DATA = "DATA",
        FULL = "FULL",
        EVENT = "EVENT",
        COMMAND = "CMD",
        SUBSCRIBE_ACK = "SUBSCRIBE_ACK",
    }
}

function Protocol.createDataMessage(payload, sensorNames, sensorMeta)
    State.messageSeq = State.messageSeq + 1

    local msg = {
        version = Protocol.VERSION,
        type = Protocol.MessageType.DATA,
        timestamp = Isaac.GetTime(),
        frame = State.updateCount,
        room_index = State.currentRoom,
        seq = State.messageSeq,
        game_time = Isaac.GetTime(),
        prev_frame = State.prevFrameSent,
        sensors = sensorMeta or {},
        payload = payload,
        channels = sensorNames,
    }

    State.prevFrameSent = State.updateCount
    return msg
end

function Protocol.createFullStateMessage(payload, sensorNames, sensorMeta)
    State.messageSeq = State.messageSeq + 1

    local msg = {
        version = Protocol.VERSION,
        type = Protocol.MessageType.FULL,
        timestamp = Isaac.GetTime(),
        frame = State.updateCount,
        seq = State.messageSeq,
        game_time = Isaac.GetTime(),
        prev_frame = State.prevFrameSent,
        sensors = sensorMeta or {},
        payload = payload,
        channels = sensorNames,
    }

    State.prevFrameSent = State.updateCount
    return msg
end

function Protocol.createEventMessage(eventType, eventData)
    return {
        version = Protocol.VERSION,
        type = Protocol.MessageType.EVENT,
        timestamp = Isaac.GetTime(),
        frame = State.updateCount,
        event = eventType,
        data = eventData,
    }
end

-- ============================================================================
-- Sensor Registry (NEW — replaces CollectorRegistry)
-- ============================================================================
--
-- Sensor definition:
-- {
--     name = "ENEMIES",
--     search = {
--         strategy = "partition" | "callback" | "hybrid",
--         partitions = EntityPartition.ENEMY,   -- bitmask
--         type_filter = nil,                     -- optional EntityType
--         radius = nil,                          -- nil = full room
--         sort_by_distance = true,
--     },
--     throttle = {
--         base_interval = 1,       -- Frames between non-dynamic collection
--         dynamic = true,           -- Switch intervals based on combat
--         combat_interval = 1,
--         idle_interval = 15,
--     },
--     extract = function(entity, player) ... end,  -- Per-entity data
--     cache = {
--         strategy = "hash" | "none" | "snapshot",
--     },
--     triggers = { "MC_POST_NPC_DEATH", ... },  -- Callback-driven triggers
-- }
--
-- ============================================================================
-- Sensor Triggers (callback-driven forced collection)
-- ============================================================================
-- Sensor Triggers (callback-driven forced collection)
-- ============================================================================
local SensorTriggers = {
    triggers = {},  -- {triggerName: [{sensorName, onTriggerFn}]}
}

function SensorTriggers:register(triggerName, sensorName, onTriggerFn)
    if not self.triggers[triggerName] then
        self.triggers[triggerName] = {}
    end
    table.insert(self.triggers[triggerName], {
        sensorName = sensorName,
        onTrigger = onTriggerFn,
    })
end

function SensorTriggers:fire(triggerName, entity, forceCollectFn)
    local entries = self.triggers[triggerName]
    if not entries then return end
    for _, entry in ipairs(entries) do
        if entry.onTrigger then
            entry.onTrigger(entity)
        end
        -- Delegate to callback to avoid circular dependency with SensorRegistry
        if forceCollectFn then
            forceCollectFn(entry.sensorName)
        end
    end
end

-- ============================================================================
-- Sensor Registry (NEW — replaces CollectorRegistry)
-- ============================================================================
local SensorRegistry = {
    sensors = {},
    cache = {},
    changeHashes = {},
    lastCollect = {},
    lastCollectFrame = {},
    frameCounters = {},    -- per-sensor frame counters for throttle
    forcePending = {},      -- sensors force-collected this frame (always sent)
}

function SensorRegistry:register(name, def)
    self.sensors[name] = {
        name = name or def.name,
        enabled = def.enabled ~= false,
        search = def.search or { strategy = "partition" },
        throttle = def.throttle or {
            base_interval = 1, dynamic = false,
            combat_interval = 1, idle_interval = 15,
        },
        extract = def.extract or function(e, p) return {} end,
        cache = def.cache or {},
        triggers = def.triggers or {},
    }
    self.cache[name] = nil
    self.changeHashes[name] = nil
    self.lastCollect[name] = nil
    self.lastCollectFrame[name] = 0

    -- Register callback triggers
    if def.triggers then
        for _, triggerName in ipairs(def.triggers) do
            SensorTriggers:register(triggerName, name, def.onTrigger)
        end
    end
end

-- ── Search strategies ────────────────────────────────────────────────

function SensorRegistry:_searchEntities(sensor)
    local player = Isaac.GetPlayer(0)
    if not player then return {} end

    local search = sensor.search
    local strategy = search.strategy or "partition"
    local results = {}

    if strategy == "callback" then
        -- Purely callback-driven, no polled search
        return {}
    end

    if strategy == "partition" or strategy == "hybrid" then
        if search.partitions and search.radius and player then
            -- Use FindInRadius with EntityPartition mask (EID technique)
            local radius = search.radius * 40  -- grid units → pixels
            local entities = Isaac.FindInRadius(player.Position, radius, search.partitions)
            for i = 1, #entities do
                local e = entities[i]
                if not search.type_filter or e.Type == search.type_filter then
                    table.insert(results, e)
                end
            end
        elseif search.partitions and not search.radius then
            -- Full room but filtered by partition
            local entities = Isaac.GetRoomEntities()
            for _, e in ipairs(entities) do
                -- Check if entity type matches partition mask
                -- (Simplified: include all for broad partitions)
                if not search.type_filter or e.Type == search.type_filter then
                    table.insert(results, e)
                end
            end
        elseif search.type_filter then
            -- Use FindByType for specific entity type (EID technique)
            local entities = Isaac.FindByType(search.type_filter, -1, -1, true, false)
            for i = 1, #entities do
                table.insert(results, entities[i])
            end
        else
            -- Fallback: full room traversal
            local entities = Isaac.GetRoomEntities()
            for _, e in ipairs(entities) do
                table.insert(results, e)
            end
        end
    end

    -- Sort by distance if requested
    if search.sort_by_distance and player and #results > 0 then
        local playerPos = player.Position
        table.sort(results, function(a, b)
            return playerPos:Distance(a.Position) < playerPos:Distance(b.Position)
        end)
    end

    return results
end

-- ── Throttle ──────────────────────────────────────────────────────────

function SensorRegistry:_shouldCollect(sensor)
    if not sensor.enabled then return false end

    -- Check subscription
    if next(State.subscribedSensors) and not State.subscribedSensors[sensor.name] then
        return false
    end

    local throttle = sensor.throttle
    local interval = throttle.base_interval

    if throttle.dynamic then
        local room = Game():GetRoom()
        local inCombat = room and room:GetAliveEnemiesCount() > 0
        interval = inCombat and throttle.combat_interval or throttle.idle_interval
    end

    if interval <= 0 then
        return false  -- Disabled throttle (callback-only)
    end

    -- Per-sensor frame counter (resets on force-collect)
    local name = sensor.name
    if not self.frameCounters[name] then self.frameCounters[name] = 0 end
    self.frameCounters[name] = self.frameCounters[name] + 1
    if self.frameCounters[name] >= interval then
        self.frameCounters[name] = 0
        return true
    end
    return false
end

-- ── Collect ───────────────────────────────────────────────────────────

function SensorRegistry:collect(name, forceCollect)
    local sensor = self.sensors[name]
    if not sensor then return nil, nil end

    if not forceCollect and not self:_shouldCollect(sensor) then
        return nil, nil
    end

    -- Run extract on searched entities (or custom collect function)
    local success, data = pcall(function()
        local player = Isaac.GetPlayer(0)
        local entities = self:_searchEntities(sensor)
        local results = {}
        for _, entity in ipairs(entities) do
            local entry = sensor.extract(entity, player)
            if entry then
                table.insert(results, entry)
            end
        end
        return results
    end)

    if not success then
        return nil, nil
    end

    if data == nil or (type(data) == "table" and #data == 0 and next(data) == nil) then
        return nil, nil
    end

    -- Hash-based change detection
    if not forceCollect and sensor.cache.strategy == "hash" then
        local newHash = Helpers.simpleHash(data)
        if self.changeHashes[name] == newHash then
            return nil, nil  -- Unchanged
        end
        self.changeHashes[name] = newHash
    end

    self.cache[name] = data
    self.lastCollectFrame[name] = State.updateCount

    local meta = {
        collect_frame = State.updateCount,
        collect_time = Isaac.GetTime(),
        interval = sensor.throttle.dynamic and "dynamic" or "fixed",
        stale_frames = 0,
        entity_count = #data,
        hash = self.changeHashes[name] or "",
    }
    SensorRegistry.lastCollect[name] = meta

    return data, meta
end

function SensorRegistry:collectAll()
    local results = {}
    local collectedNames = {}
    local collectedMeta = {}

    for name, _ in pairs(self.sensors) do
        local data, meta = self:collect(name, false)
        if data ~= nil then
            results[name] = data
            table.insert(collectedNames, name)
            collectedMeta[name] = meta
        end
    end

    -- Include force-pending sensors (force-collected this frame)
    -- These have cached data but throttle may have blocked them
    for name, _ in pairs(self.forcePending) do
        local cached = self.cache[name]
        if cached ~= nil and results[name] == nil then
            results[name] = cached
            table.insert(collectedNames, name)
            collectedMeta[name] = self.lastCollect[name] or {
                collect_frame = State.updateCount,
                collect_time = Isaac.GetTime(),
                interval = "forced",
                stale_frames = 0,
                entity_count = (type(cached) == "table" and #cached) or 0,
                hash = self.changeHashes[name] or "",
            }
        end
    end

    -- Clear force-pending for next frame
    self.forcePending = {}

    return results, collectedNames, collectedMeta
end

function SensorRegistry:forceCollectAll()
    local results = {}
    local names = {}
    local meta = {}
    for name, _ in pairs(self.sensors) do
        local data, m = self:collect(name, true)
        if data ~= nil then
            results[name] = data
            table.insert(names, name)
            meta[name] = m
        end
    end
    return results, names, meta
end

function SensorRegistry:getCached(name)
    return self.cache[name]
end

function SensorRegistry:getConfig(name)
    local sensor = self.sensors[name]
    if not sensor then return nil end
    return {
        name = sensor.name,
        enabled = sensor.enabled,
        throttle = sensor.throttle,
        search = sensor.search,
    }
end

function SensorRegistry:getAllConfigs()
    local configs = {}
    for name, _ in pairs(self.sensors) do
        configs[name] = self:getConfig(name)
    end
    return configs
end

function SensorRegistry:setEnabled(name, enabled)
    if self.sensors[name] then
        self.sensors[name].enabled = enabled
    end
end

function SensorRegistry:setThrottle(name, throttleConfig)
    local sensor = self.sensors[name]
    if sensor then
        for k, v in pairs(throttleConfig) do
            sensor.throttle[k] = v
        end
    end
end

-- ============================================================================
-- Sensor Definitions (all 12 sensors ported from v2.x + enhanced)
-- ============================================================================

-- 1. PLAYER_POSITION (HIGH frequency, single entity — no search needed)
SensorRegistry:register("PLAYER_POSITION", {
    name = "PLAYER_POSITION",
    search = { strategy = "callback" },  -- Direct API, no entity search
    throttle = { base_interval = 1, dynamic = false },
    cache = { strategy = "hash" },
    extract = function()  -- Override collect behavior per-sensor
        -- This sensor uses a custom collect function, defined below
    end,
})

-- 2. PLAYER_STATS (LOW frequency)
SensorRegistry:register("PLAYER_STATS", {
    name = "PLAYER_STATS",
    search = { strategy = "callback" },
    throttle = { base_interval = 30, dynamic = false },
    cache = { strategy = "hash" },
})

-- 3. PLAYER_HEALTH (LOW frequency)
SensorRegistry:register("PLAYER_HEALTH", {
    name = "PLAYER_HEALTH",
    search = { strategy = "callback" },
    throttle = { base_interval = 30, dynamic = false },
    cache = { strategy = "hash" },
})

-- 4. PLAYER_INVENTORY (RARE frequency)
SensorRegistry:register("PLAYER_INVENTORY", {
    name = "PLAYER_INVENTORY",
    search = { strategy = "callback" },
    throttle = { base_interval = 90, dynamic = false },
    cache = { strategy = "hash" },
})

-- 5. ENEMIES (HIGH in combat, LOW idle)
SensorRegistry:register("ENEMIES", {
    name = "ENEMIES",
    search = {
        strategy = "partition",
        partitions = EntityPartition.ENEMY,
        sort_by_distance = true,
    },
    throttle = {
        base_interval = 1, dynamic = true,
        combat_interval = 1, idle_interval = 15,
    },
    cache = { strategy = "hash" },
    triggers = { "MC_POST_NPC_DEATH", "MC_POST_NEW_ROOM" },
    extract = function(entity, player)
        if not entity:IsActiveEnemy(false) or not entity:IsVulnerableEnemy() then
            return nil
        end
        local npc = entity:ToNPC()
        local targetPos = { x = 0, y = 0 }
        if npc then
            local target = npc:GetPlayerTarget()
            if target then targetPos = Helpers.vectorToTable(target.Position) end
        end
        return {
            id = entity.Index,
            type = entity.Type, variant = entity.Variant, subtype = entity.SubType,
            pos = Helpers.vectorToTable(entity.Position),
            vel = Helpers.vectorToTable(entity.Velocity),
            hp = entity.HitPoints, max_hp = entity.MaxHitPoints,
            is_boss = entity:IsBoss(),
            is_champion = npc and npc:IsChampion() or false,
            state = npc and npc.State or 0,
            state_frame = npc and npc.StateFrame or 0,
            projectile_cooldown = npc and npc.ProjectileCooldown or 0,
            projectile_delay = npc and npc.ProjectileDelay or 0,
            collision_radius = entity.Size,
            distance = player and player.Position:Distance(entity.Position) or 0,
            target_pos = targetPos,
            v1 = npc and Helpers.vectorToTable(npc.V1) or { x = 0, y = 0 },
            v2 = npc and Helpers.vectorToTable(npc.V2) or { x = 0, y = 0 },
        }
    end,
})

-- 6. PROJECTILES (HIGH in combat, LOW idle)
SensorRegistry:register("PROJECTILES", {
    name = "PROJECTILES",
    search = {
        strategy = "partition",
        partitions = EntityPartition.BULLET + EntityPartition.EFFECT,
    },
    throttle = {
        base_interval = 1, dynamic = true,
        combat_interval = 1, idle_interval = 15,
    },
    cache = { strategy = "hash" },
    triggers = { "MC_POST_NEW_ROOM" },
    extract = function(entity, player)
        -- We override this with a custom collect — see custom sensor handlers below
    end,
})

-- 7. ROOM_INFO (on room change + LOW)
SensorRegistry:register("ROOM_INFO", {
    name = "ROOM_INFO",
    search = { strategy = "callback" },
    throttle = { base_interval = 15, dynamic = false },
    cache = { strategy = "hash" },
    triggers = { "MC_POST_NEW_ROOM" },
})

-- 8. ROOM_LAYOUT (on room change)
SensorRegistry:register("ROOM_LAYOUT", {
    name = "ROOM_LAYOUT",
    search = { strategy = "callback" },
    throttle = { base_interval = -1, dynamic = false },  -- Callback-only
    cache = { strategy = "snapshot" },
    triggers = { "MC_POST_NEW_ROOM" },
})

-- 9. BOMBS (LOW frequency)
SensorRegistry:register("BOMBS", {
    name = "BOMBS",
    search = {
        strategy = "partition",
        type_filter = EntityType.ENTITY_BOMB,
    },
    throttle = { base_interval = 15, dynamic = false },
    cache = { strategy = "hash" },
    extract = function(entity, player)
        if entity.Type ~= EntityType.ENTITY_BOMB then return nil end
        local bomb = entity:ToBomb()
        local dist = player and player.Position:Distance(entity.Position) or 0
        local BOMB_VARIANTS = {
            [0]="NORMAL",[1]="BIG",[2]="DECOY",[3]="TROLL",[4]="MEGA_TROLL",
            [5]="POISON",[6]="BIG_POISON",[7]="SAD",[8]="HOT",[9]="BUTT",
            [10]="MR_MEGA",[11]="BOBBY",[12]="GLITTER",[13]="THROWABLE",
            [14]="SMALL",[15]="BRIMSTONE",[16]="BLOODY_SAD",[17]="GIGA",
            [18]="GOLDEN_TROLL",[19]="ROCKET",[20]="GIGA_ROCKET",
        }
        return {
            id = entity.Index, type = entity.Type,
            variant = entity.Variant,
            variant_name = BOMB_VARIANTS[entity.Variant] or ("UNKNOWN_" .. entity.Variant),
            sub_type = entity.SubType,
            pos = Helpers.vectorToTable(entity.Position),
            vel = Helpers.vectorToTable(entity.Velocity),
            explosion_radius = bomb and bomb.ExplosionRadius or 0,
            timer = bomb and bomb.Timer or 0,
            distance = dist,
        }
    end,
})

-- 10. INTERACTABLES (LOW frequency)
SensorRegistry:register("INTERACTABLES", {
    name = "INTERACTABLES",
    search = {
        strategy = "partition",
        type_filter = 6,  -- EntityType 6 = interactable entities
    },
    throttle = { base_interval = 15, dynamic = false },
    cache = { strategy = "hash" },
    extract = function(entity, player)
        if entity.Type ~= 6 then return nil end
        local npc = entity:ToNPC()
        local dist = player and player.Position:Distance(entity.Position) or 0
        local INTERACTABLE_VARIANTS = {
            [1]="SLOT_MACHINE",[2]="BLOOD_DONATION",[3]="FORTUNE_TELLING",
            [4]="BEGGAR",[5]="DEVIL_BEGGAR",[6]="SHELL_GAME",
            [7]="KEY_MASTER",[8]="DONATION_MACHINE",[9]="BOMB_BUM",
            [10]="RESTOCK_MACHINE",[11]="GREED_MACHINE",[12]="MOMS_DRESSING_TABLE",
            [13]="BATTERY_BUM",[14]="ISAAC_SECRET",[15]="HELL_GAME",
            [16]="CRANE_GAME",[17]="CONFESSIONAL",[18]="ROTTEN_BEGGAR",
            [19]="REVIVE_MACHINE",
        }
        local target = npc and npc:GetPlayerTarget()
        return {
            id = entity.Index, type = entity.Type,
            variant = entity.Variant,
            variant_name = INTERACTABLE_VARIANTS[entity.Variant] or ("UNKNOWN_" .. entity.Variant),
            sub_type = entity.SubType,
            pos = Helpers.vectorToTable(entity.Position),
            vel = Helpers.vectorToTable(entity.Velocity),
            state = npc and npc.State or 0,
            state_frame = npc and npc.StateFrame or 0,
            target_pos = target and Helpers.vectorToTable(target.Position) or { x = 0, y = 0 },
            distance = dist,
        }
    end,
})

-- 11. PICKUPS (LOW frequency + callback on pickup init)
SensorRegistry:register("PICKUPS", {
    name = "PICKUPS",
    search = {
        strategy = "partition",
        partitions = EntityPartition.PICKUP,
    },
    throttle = { base_interval = 15, dynamic = false },
    cache = { strategy = "hash" },
    triggers = { "MC_POST_PICKUP_INIT", "MC_POST_NEW_ROOM" },
    extract = function(entity, player)
        if entity.Type ~= EntityType.ENTITY_PICKUP then return nil end
        local pickup = entity:ToPickup()
        return {
            id = entity.Index,
            variant = entity.Variant,
            sub_type = entity.SubType,
            pos = Helpers.vectorToTable(entity.Position),
            price = pickup and pickup.Price or 0,
            shop_item_id = pickup and pickup.ShopItemId or -1,
            wait = pickup and pickup.Wait or 0,
        }
    end,
})

-- 12. FIRE_HAZARDS (LOW frequency)
SensorRegistry:register("FIRE_HAZARDS", {
    name = "FIRE_HAZARDS",
    search = { strategy = "hybrid" },
    throttle = { base_interval = 15, dynamic = false },
    cache = { strategy = "hash" },
    extract = function(entity, player)
        local dist = player and player.Position:Distance(entity.Position) or 0
        -- Handle fire effects (bomb fire, candle flame)
        local DANGEROUS_FIRE = { [51] = true, [52] = true }
        local FIREPLACE_TYPES = {
            [0]="NORMAL",[1]="RED",[2]="BLUE",[3]="PURPLE",[4]="WHITE",
            [10]="MOVABLE",[11]="COAL",[12]="MOVABLE_BLUE",[13]="MOVABLE_PURPLE",
        }
        if entity.Type == EntityType.ENTITY_EFFECT then
            if DANGEROUS_FIRE[entity.Variant] then
                return {
                    id = entity.Index, type = "EFFECT", variant = entity.Variant,
                    pos = Helpers.vectorToTable(entity.Position),
                    collision_radius = entity.Size > 0 and entity.Size or 20,
                    distance = dist,
                }
            end
        elseif entity.Type == 33 then  -- ENTITY_FIREPLACE
            local variant = entity.Variant
            local isExtinguished = entity.State == 1000
            local isShooting = false
            local npc = entity:ToNPC()
            if npc and (variant == 1 or variant == 3) then
                isShooting = (npc.State == 8)
            end
            return {
                id = entity.Index, type = "FIREPLACE",
                fireplace_type = FIREPLACE_TYPES[variant] or ("UNKNOWN_" .. variant),
                variant = variant, sub_variant = entity.SubType,
                pos = Helpers.vectorToTable(entity.Position),
                hp = entity.HitPoints, max_hp = entity.MaxHitPoints,
                state = entity.State, is_extinguished = isExtinguished,
                collision_radius = entity.Size > 0 and entity.Size or 25,
                distance = dist, is_shooting = isShooting,
                sprite_scale = entity.SpriteScale.X,
            }
        end
        return nil
    end,
})

-- ═══════════════════════════════════════════════════════════════════════
-- Custom sensor collect functions (override search-based collection)
-- These sensors don't use entity search — they query the API directly.
-- ═══════════════════════════════════════════════════════════════════════

local CustomCollectors = {}

function CustomCollectors.PLAYER_POSITION()
    local players = Helpers.getPlayers()
    local data = {}
    for i, player in ipairs(players) do
        data[i] = {
            pos = Helpers.vectorToTable(player.Position),
            vel = Helpers.vectorToTable(player.Velocity),
            move_dir = player:GetMovementDirection(),
            fire_dir = player:GetFireDirection(),
            head_dir = player:GetHeadDirection(),
            aim_dir = Helpers.vectorToTable(player:GetAimDirection()),
        }
    end
    return data
end

function CustomCollectors.PLAYER_STATS()
    local players = Helpers.getPlayers()
    local data = {}
    for i, player in ipairs(players) do
        data[i] = {
            player_type = player:GetPlayerType(),
            damage = player.Damage, speed = player.MoveSpeed,
            tears = player.MaxFireDelay,
            range = player.TearRange, tear_range = player.TearRange,
            shot_speed = player.ShotSpeed, luck = player.Luck,
            tear_height = player.TearHeight,
            tear_falling_speed = player.TearFallingSpeed,
            can_fly = player.CanFly, size = player.Size,
            sprite_scale = player.SpriteScale.X,
        }
    end
    return data
end

function CustomCollectors.PLAYER_HEALTH()
    local players = Helpers.getPlayers()
    local data = {}
    for i, player in ipairs(players) do
        data[i] = {
            red_hearts = player:GetHearts(), max_hearts = player:GetMaxHearts(),
            soul_hearts = player:GetSoulHearts(), black_hearts = player:GetBlackHearts(),
            bone_hearts = player:GetBoneHearts(), golden_hearts = player:GetGoldenHearts(),
            eternal_hearts = player:GetEternalHearts(), rotten_hearts = player:GetRottenHearts(),
            broken_hearts = player:GetBrokenHearts(), extra_lives = player:GetExtraLives(),
        }
    end
    return data
end

function CustomCollectors.PLAYER_INVENTORY()
    local players = Helpers.getPlayers()
    local data = {}
    for i, player in ipairs(players) do
        local playerData = {
            coins = player:GetNumCoins(), bombs = player:GetNumBombs(),
            keys = player:GetNumKeys(),
            trinket_0 = player:GetTrinket(0), trinket_1 = player:GetTrinket(1),
            card_0 = player:GetCard(0), pill_0 = player:GetPill(0),
            collectible_count = player:GetCollectibleCount(),
        }
        -- Collectibles
        local items = {}
        if playerData.collectible_count > 0 then
            for itemId = 1, 733 do
                if player:HasCollectible(itemId, true) then
                    local count = player:GetCollectibleNum(itemId, true)
                    if count > 0 then items[tostring(itemId)] = count end
                end
            end
        end
        playerData.collectibles = items
        -- Active items
        local activeSlots = {}
        for slot = 0, 3 do
            local activeItem = player:GetActiveItem(slot)
            if activeItem > 0 then
                activeSlots[tostring(slot)] = {
                    item = activeItem,
                    charge = player:GetActiveCharge(slot),
                    max_charge = player:GetActiveMaxCharge(slot),
                    battery_charge = player:GetBatteryCharge(slot),
                }
            end
        end
        playerData.active_items = activeSlots
        data[i] = playerData
    end
    return data
end

function CustomCollectors.PROJECTILES()
    local player = Isaac.GetPlayer(0)
    if not player then return { enemy_projectiles = {}, player_tears = {}, lasers = {} } end
    local data = { enemy_projectiles = {}, player_tears = {}, lasers = {} }
    for _, entity in ipairs(Isaac.GetRoomEntities()) do
        if entity.Type == EntityType.ENTITY_PROJECTILE then
            local proj = entity:ToProjectile()
            table.insert(data.enemy_projectiles, {
                id = entity.Index,
                pos = Helpers.vectorToTable(entity.Position),
                vel = Helpers.vectorToTable(entity.Velocity),
                variant = entity.Variant, collision_radius = entity.Size,
                height = proj and proj.Height or 0,
                falling_speed = proj and proj.FallingSpeed or 0,
                falling_accel = proj and proj.FallingAccel or 0,
            })
        elseif entity.Type == EntityType.ENTITY_TEAR then
            local tear = entity:ToTear()
            local tearData = {
                id = entity.Index,
                pos = Helpers.vectorToTable(entity.Position),
                vel = Helpers.vectorToTable(entity.Velocity),
                variant = entity.Variant, collision_radius = entity.Size,
                height = tear and tear.Height or 0,
                scale = tear and tear.Scale or 1,
            }
            if entity.SpawnerType == EntityType.ENTITY_PLAYER then
                table.insert(data.player_tears, tearData)
            else
                table.insert(data.enemy_projectiles, tearData)
            end
        elseif entity.Type == EntityType.ENTITY_LASER then
            local laser = entity:ToLaser()
            if laser then
                table.insert(data.lasers, {
                    id = entity.Index,
                    pos = Helpers.vectorToTable(entity.Position),
                    angle = laser.Angle, max_distance = laser.MaxDistance,
                    is_enemy = entity:IsEnemy(),
                })
            end
        end
    end
    return data
end

function CustomCollectors.ROOM_INFO()
    local room = Game():GetRoom()
    local level = Game():GetLevel()
    if not room then return nil end
    local tl = room:GetTopLeftPos()
    local br = room:GetBottomRightPos()
    local roomDesc = level:GetCurrentRoomDesc()
    return {
        room_type = room:GetType(), room_shape = room:GetRoomShape(),
        room_idx = level:GetCurrentRoomIndex(),
        stage = level:GetStage(), stage_type = level:GetStageType(),
        difficulty = Game().Difficulty,
        is_clear = room:IsClear(), is_first_visit = room:IsFirstVisit(),
        grid_width = room:GetGridWidth(), grid_height = room:GetGridHeight(),
        top_left = Helpers.vectorToTable(tl), bottom_right = Helpers.vectorToTable(br),
        has_boss = room:GetBossID() > 0, enemy_count = room:GetAliveEnemiesCount(),
        room_variant = roomDesc and roomDesc.Data and roomDesc.Data.Variant or 0,
    }
end

function CustomCollectors.ROOM_LAYOUT()
    local room = Game():GetRoom()
    if not room then return nil end
    local grid, doors = {}, {}
    local width = room:GetGridWidth()
    for i = 0, room:GetGridSize() - 1 do
        local gridEntity = room:GetGridEntity(i)
        if gridEntity then
            local gridType = gridEntity:GetType()
            if gridType >= 0 and gridType <= 27 and gridType ~= 13 and gridType ~= 16 and gridType ~= 20 then
                local pos = room:GetGridPosition(i)
                grid[tostring(i)] = {
                    type = gridType, variant = gridEntity:GetVariant(),
                    state = gridEntity.State, collision = gridEntity.CollisionClass,
                    x = pos.X, y = pos.Y,
                }
            end
        end
    end
    for slot = 0, DoorSlot.NUM_DOOR_SLOTS - 1 do
        local door = room:GetDoor(slot)
        if door then
            local doorPos = door.Position
            doors[tostring(slot)] = {
                target_room = door.TargetRoomIndex, target_room_type = door.TargetRoomType,
                is_open = door:IsOpen(), is_locked = door:IsLocked(),
                x = doorPos.X, y = doorPos.Y,
            }
        end
    end
    return {
        grid = grid, doors = doors,
        grid_size = room:GetGridSize(), width = width, height = room:GetGridHeight(),
    }
end

-- Override collect method for custom sensors
local origCollect = SensorRegistry.collect
function SensorRegistry:collect(name, forceCollect)
    local sensor = self.sensors[name]
    if not sensor then return nil, nil end
    if not forceCollect and not self:_shouldCollect(sensor) then
        return nil, nil
    end

    -- Check for custom collector
    local customFn = CustomCollectors[name]
    local success, data
    if customFn then
        success, data = pcall(customFn)
    elseif sensor.search.strategy ~= "callback" then
        success, data = pcall(function()
            local player = Isaac.GetPlayer(0)
            local entities = self:_searchEntities(sensor)
            local results = {}
            for _, entity in ipairs(entities) do
                local entry = sensor.extract(entity, player)
                if entry then table.insert(results, entry) end
            end
            return results
        end)
    else
        return nil, nil  -- Callback-only sensors without customFn
    end

    if not success or data == nil then return nil, nil end

    -- On force-collect: reset frame counter and mark for immediate send
    if forceCollect then
        self.frameCounters[name] = 0
        self.forcePending[name] = true
    end

    -- Hash-based change detection
    if not forceCollect and sensor.cache.strategy == "hash" then
        local newHash = Helpers.simpleHash(data)
        if self.changeHashes[name] == newHash then
            return nil, nil
        end
        self.changeHashes[name] = newHash
    end

    self.cache[name] = data
    self.lastCollectFrame[name] = State.updateCount

    local meta = {
        collect_frame = State.updateCount,
        collect_time = Isaac.GetTime(),
        interval = sensor.throttle.dynamic and "dynamic" or "fixed",
        stale_frames = 0,
        entity_count = (type(data) == "table" and #data) or 0,
        hash = self.changeHashes[name] or "",
    }
    self.lastCollect[name] = meta
    return data, meta
end

-- ============================================================================
-- Input Executor (unchanged from v2.x)
-- ============================================================================
local InputExecutor = {
    moveDirection = { x = 0, y = 0 },
    shootDirection = { x = 0, y = 0 },
    useItem = false, useBomb = false,
    useCard = false, usePill = false, drop = false,
}

function InputExecutor.applyCommand(command)
    if not command then return end
    local hasInput = false
    if command.move then
        InputExecutor.moveDirection = command.move
        if command.move.x ~= 0 or command.move.y ~= 0 then hasInput = true end
    end
    if command.shoot then
        InputExecutor.shootDirection = command.shoot
        if command.shoot.x ~= 0 or command.shoot.y ~= 0 then hasInput = true end
    end
    if command.use_item ~= nil then InputExecutor.useItem = command.use_item; if command.use_item then hasInput = true end end
    if command.use_bomb ~= nil then InputExecutor.useBomb = command.use_bomb; if command.use_bomb then hasInput = true end end
    if command.use_card ~= nil then InputExecutor.useCard = command.use_card; if command.use_card then hasInput = true end end
    if command.use_pill ~= nil then InputExecutor.usePill = command.use_pill; if command.use_pill then hasInput = true end end
    if command.drop ~= nil then InputExecutor.drop = command.drop; if command.drop then hasInput = true end end
    State.aiActive = hasInput
end

function InputExecutor.reset()
    InputExecutor.moveDirection = { x = 0, y = 0 }
    InputExecutor.shootDirection = { x = 0, y = 0 }
    InputExecutor.useItem = false; InputExecutor.useBomb = false
    InputExecutor.useCard = false; InputExecutor.usePill = false
    InputExecutor.drop = false
    State.aiActive = false
end

local function shouldAIControl()
    local mode = State.controlMode
    if mode == "MANUAL" then
        InputExecutor.reset()
        return false
    elseif mode == "FORCE_AI" then
        return true
    end
    -- AUTO mode
    local room = Game():GetRoom()
    local enemyCount = room and room:GetAliveEnemiesCount() or 0
    if State.aiActive then State.wasInCombat = true end
    if enemyCount > 0 and State.aiActive then return true end
    if enemyCount == 0 and State.wasInCombat then
        InputExecutor.reset()
        State.wasInCombat = false
    end
    return false
end

-- ============================================================================
-- Event System
-- ============================================================================
local EventSystem = { pendingEvents = {} }

function EventSystem.emit(eventType, eventData)
    table.insert(EventSystem.pendingEvents, {
        type = eventType, data = eventData or {},
        frame = State.updateCount,
    })
end

function EventSystem.flush()
    for _, event in ipairs(EventSystem.pendingEvents) do
        Network.send(Protocol.createEventMessage(event.type, event.data))
    end
    EventSystem.pendingEvents = {}
end

-- ============================================================================
-- Command Handler (extended for v3.0)
-- ============================================================================
local CommandHandler = { handlers = {} }

function CommandHandler.register(command, handler)
    CommandHandler.handlers[command] = handler
end

function CommandHandler.process(cmdMessage)
    if not cmdMessage then return nil end
    -- Input commands
    if cmdMessage.move or cmdMessage.shoot or cmdMessage.use_item or cmdMessage.use_bomb then
        return nil  -- Handled by InputExecutor
    end
    -- Named commands
    if cmdMessage.command then
        local handler = CommandHandler.handlers[cmdMessage.command]
        if handler then return handler(cmdMessage.params or {}) end
    end
    -- v3.0 subscription
    if cmdMessage.type == "SUBSCRIBE" then
        return CommandHandler._handleSubscribe(cmdMessage)
    end
    return nil
end

function CommandHandler._handleSubscribe(msg)
    local requested = msg.sensors or {}
    local accepted, rejected = {}, {}
    for _, name in ipairs(requested) do
        if SensorRegistry.sensors[name] then
            table.insert(accepted, name)
            State.subscribedSensors[name] = true
        else
            table.insert(rejected, name)
        end
    end
    -- Apply config overrides
    local overrides = msg.config_overrides or {}
    for name, config in pairs(overrides) do
        if config.throttle then
            SensorRegistry:setThrottle(name, config.throttle)
        end
        if config.enabled ~= nil then
            SensorRegistry:setEnabled(name, config.enabled)
        end
    end
    -- Send ACK
    Network.send({
        version = Protocol.VERSION,
        type = "SUBSCRIBE_ACK",
        accepted = accepted,
        rejected = rejected,
        sensor_configs = SensorRegistry:getAllConfigs(),
    })
    return { success = true, accepted = accepted, rejected = rejected }
end

-- ── Register system commands ──────────────────────────────────────────

CommandHandler.register("SET_CHANNEL", function(params)
    if params.channel and params.enabled ~= nil then
        SensorRegistry:setEnabled(params.channel, params.enabled)
        return { success = true, channel = params.channel, enabled = params.enabled }
    end
    return { success = false, error = "Invalid params" }
end)

CommandHandler.register("SET_INTERVAL", function(params)
    if params.channel and params.interval then
        SensorRegistry:setThrottle(params.channel, { base_interval = params.interval })
        return { success = true }
    end
    return { success = false, error = "Invalid params" }
end)

CommandHandler.register("CONFIGURE_SENSOR", function(params)
    local sensor = params.sensor
    if not sensor or not SensorRegistry.sensors[sensor] then
        return { success = false, error = "Unknown sensor: " .. (sensor or "nil") }
    end
    if params.enabled ~= nil then
        SensorRegistry:setEnabled(sensor, params.enabled)
    end
    if params.throttle then
        SensorRegistry:setThrottle(sensor, params.throttle)
    end
    return { success = true, config = SensorRegistry:getConfig(sensor) }
end)

CommandHandler.register("LIST_SENSORS", function()
    local names = {}
    for name, _ in pairs(SensorRegistry.sensors) do table.insert(names, name) end
    return { success = true, sensors = names }
end)

CommandHandler.register("GET_SENSOR_CONFIG", function(params)
    local config = SensorRegistry:getConfig(params.sensor)
    if config then return { success = true, config = config }
    else return { success = false, error = "Unknown sensor" } end
end)

CommandHandler.register("SUBSCRIBE_SENSORS", function(params)
    local sensors = params.sensors or {}
    for _, name in ipairs(sensors) do
        State.subscribedSensors[name] = true
    end
    return { success = true, subscribed = sensors }
end)

CommandHandler.register("UNSUBSCRIBE_SENSORS", function(params)
    local sensors = params.sensors or {}
    for _, name in ipairs(sensors) do
        State.subscribedSensors[name] = nil
    end
    return { success = true, unsubscribed = sensors }
end)

CommandHandler.register("GET_FULL_STATE", function()
    local fullState, channels, meta = SensorRegistry:forceCollectAll()
    Network.send(Protocol.createFullStateMessage(fullState, channels, meta))
    return { success = true }
end)

CommandHandler.register("GET_CONFIG", function()
    return { success = true, config = SensorRegistry:getAllConfigs() }
end)

CommandHandler.register("SET_MANUAL", function(params)
    if params.enabled ~= nil then
        State.controlMode = params.enabled and "MANUAL" or "AUTO"
        InputExecutor.reset()
        return { success = true, mode = State.controlMode }
    end
    return { success = false, error = "Invalid params" }
end)

CommandHandler.register("SET_FORCE_AI", function(params)
    if params.enabled ~= nil then
        State.controlMode = params.enabled and "FORCE_AI" or "AUTO"
        return { success = true, mode = State.controlMode }
    end
    return { success = false, error = "Invalid params" }
end)

CommandHandler.register("SET_CONTROL_MODE", function(params)
    local mode = params.mode
    if mode and (mode == "MANUAL" or mode == "AUTO" or mode == "FORCE_AI") then
        State.controlMode = mode
        InputExecutor.reset()
        return { success = true, mode = mode }
    end
    return { success = false, error = "Invalid mode. Use: MANUAL, AUTO, or FORCE_AI" }
end)

CommandHandler.register("GET_CONTROL_MODE", function()
    return { success = true, mode = State.controlMode }
end)

CommandHandler.register("EXEC_CONSOLE", function(params)
    if params.command then
        local success, result = pcall(function() return Isaac.ExecuteCommand(params.command) end)
        if success then
            return { success = true, command = params.command, result = result or "" }
        else
            return { success = false, error = result, command = params.command }
        end
    end
    return { success = false, error = "No command provided" }
end)

-- ============================================================================
-- Mod Callbacks
-- ============================================================================

-- MC_POST_UPDATE — main game loop (30 tps, respects pause)
mod:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
    State.updateCount = State.updateCount + 1

    -- Cooldown timers
    if State.toggleCooldown > 0 then State.toggleCooldown = State.toggleCooldown - 1 end
    if State.modeMessageTimer > 0 then State.modeMessageTimer = State.modeMessageTimer - 1 end

    -- F3 toggle manual/AI mode
    if Input.IsButtonPressed(Keyboard.KEY_F3, 0) and State.toggleCooldown == 0 then
        if State.controlMode == "MANUAL" then
            State.controlMode = "AUTO"
        else
            State.controlMode = "MANUAL"
        end
        State.toggleCooldown = 20
        State.showModeMessage = true
        State.modeMessageTimer = 90
        if State.controlMode == "MANUAL" then InputExecutor.reset() end
    end

    -- ── Connection (always attempt, even without player) ────────────
    if not State.connected then Network.connect() end

    -- ── Debug: periodic data flow report ────────────────────────────
    if Config.DEBUG and State.updateCount % Config.DEBUG_INTERVAL == 1 then
        local sc = State.connected and "YES" or "NO"
        local sub = 0; for _ in pairs(State.subscribedSensors) do sub = sub + 1 end
        local cacheKeys = 0; for _ in pairs(SensorRegistry.cache) do cacheKeys = cacheKeys + 1 end
        print("[SB DEBUG] frame=" .. State.updateCount ..
              " connected=" .. sc ..
              " room=" .. State.currentRoom ..
              " subscribed=" .. sub ..
              " cached=" .. cacheKeys ..
              " sent=" .. State.messageSeq ..
              " prevSent=" .. State.prevFrameSent)
    end

    -- ── Data collection (only when player exists) ────────────────────
    local player = Isaac.GetPlayer(0)
    if not player then
        -- Still receive commands even without player (for console, etc.)
        if State.connected then
            local command = Network.receive()
            if command then
                local result = CommandHandler.process(command)
                if result then
                    Network.send({
                        version = Protocol.VERSION,
                        type = Protocol.MessageType.COMMAND,
                        frame = State.updateCount,
                        result = result,
                    })
                end
                InputExecutor.applyCommand(command)
            end
        end
        return
    end

    -- Room change detection
    local currentRoom = Game():GetLevel():GetCurrentRoomIndex()
    if currentRoom ~= State.currentRoom then
        State.currentRoom = currentRoom
        State.roomEntered = true

        -- Fire sensor triggers
        SensorTriggers:fire("MC_POST_NEW_ROOM", nil,
            function(name) SensorRegistry:collect(name, true) end)

        -- Force-collect room data
        SensorRegistry:collect("ROOM_INFO", true)
        SensorRegistry:collect("ROOM_LAYOUT", true)
        SensorRegistry:collect("PICKUPS", true)

        EventSystem.emit("ROOM_ENTER", {
            room_index = currentRoom,
            room_info = SensorRegistry:getCached("ROOM_INFO"),
            room_layout = SensorRegistry:getCached("ROOM_LAYOUT"),
        })
    end

    -- Collect and send
    if State.connected then
        local data, channels, meta = SensorRegistry:collectAll()
        if next(data) then
            local ok = Network.send(Protocol.createDataMessage(data, channels, meta))
            if Config.DEBUG and State.updateCount % Config.DEBUG_INTERVAL == 1 then
                local names = table.concat(channels, ",")
                local sizes = {}
                for _, n in ipairs(channels) do
                    local d = data[n]
                    local sz = type(d) == "table" and #d or "?"
                    table.insert(sizes, n .. "=" .. tostring(sz))
                end
                print("[SB SEND] frame=" .. State.updateCount ..
                      " channels=[" .. names .. "]" ..
                      " sizes={" .. table.concat(sizes, " ") .. "}" ..
                      " ok=" .. tostring(ok))
            end
        elseif Config.DEBUG and State.updateCount % Config.DEBUG_INTERVAL == 1 then
            print("[SB SEND] frame=" .. State.updateCount .. " NO DATA — all sensors skipped or empty")
        end

        -- Flush pending events
        EventSystem.flush()

        -- Receive commands
        local command = Network.receive()
        if command then
            local result = CommandHandler.process(command)
            if result then
                Network.send({
                    version = Protocol.VERSION,
                    type = Protocol.MessageType.COMMAND,
                    frame = State.updateCount,
                    result = result,
                })
            end
            InputExecutor.applyCommand(command)
        end
    end
end)

-- MC_POST_RENDER — render loop (60 tps, ignores pause)
mod:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    State.renderCount = State.renderCount + 1

    -- Mode indicator
    if State.showModeMessage and State.modeMessageTimer > 0 then
        local alpha = math.min(1.0, State.modeMessageTimer / 30)
        local modeText = State.controlMode .. " MODE (F3)"
        local r, g, b = 1.0, 1.0, 1.0
        if State.controlMode == "MANUAL" then
            r, g, b = 1.0, 1.0, 0.2
        elseif State.controlMode == "FORCE_AI" then
            r, g, b = 0.2, 1.0, 1.0
        end
        Isaac.RenderText(modeText, 50, 20, r, g, b, alpha)
    end

    -- Connection indicator
    local connTxt = State.connected and "●" or "○"
    local connR = State.connected and 0.2 or 0.8
    local connG = State.connected and 1.0 or 0.2
    Isaac.RenderText(connTxt, Isaac.GetScreenWidth() - 20, 5, connR, connG, 0.2, 0.8)
end)

-- MC_INPUT_ACTION — AI input injection
mod:AddCallback(ModCallbacks.MC_INPUT_ACTION, function(_, entity, hook, action)
    if not entity or entity.Type ~= EntityType.ENTITY_PLAYER then return nil end
    if not shouldAIControl() then return nil end

    local function ret(isActive)
        if hook == InputHook.IS_ACTION_PRESSED or hook == InputHook.IS_ACTION_TRIGGERED then
            return isActive
        end
        if hook == InputHook.GET_ACTION_VALUE then
            return isActive and 1.0 or 0.0
        end
        return nil
    end

    local moveDir = InputExecutor.moveDirection
    local shootDir = InputExecutor.shootDirection

    if action == ButtonAction.ACTION_LEFT then return ret(moveDir.x == -1)
    elseif action == ButtonAction.ACTION_RIGHT then return ret(moveDir.x == 1)
    elseif action == ButtonAction.ACTION_UP then return ret(moveDir.y == -1)
    elseif action == ButtonAction.ACTION_DOWN then return ret(moveDir.y == 1)
    elseif action == ButtonAction.ACTION_SHOOTLEFT then return ret(shootDir.x == -1)
    elseif action == ButtonAction.ACTION_SHOOTRIGHT then return ret(shootDir.x == 1)
    elseif action == ButtonAction.ACTION_SHOOTUP then return ret(shootDir.y == -1)
    elseif action == ButtonAction.ACTION_SHOOTDOWN then return ret(shootDir.y == 1)
    elseif action == ButtonAction.ACTION_ITEM then return ret(InputExecutor.useItem)
    elseif action == ButtonAction.ACTION_BOMB then return ret(InputExecutor.useBomb)
    elseif action == ButtonAction.ACTION_PILLCARD then return ret(InputExecutor.useCard or InputExecutor.usePill)
    elseif action == ButtonAction.ACTION_DROP then return ret(InputExecutor.drop)
    end

    return nil
end)

-- MC_PRE_SPAWN_CLEAN_AWARD — room clear
mod:AddCallback(ModCallbacks.MC_PRE_SPAWN_CLEAN_AWARD, function()
    InputExecutor.reset()
    EventSystem.emit("ROOM_CLEAR", { room_index = State.currentRoom })
end)

-- MC_ENTITY_TAKE_DMG — player damage
mod:AddCallback(ModCallbacks.MC_ENTITY_TAKE_DMG, function(_, entity, amount, flags, source)
    if entity.Type ~= EntityType.ENTITY_PLAYER then return end
    local player = entity:ToPlayer()
    EventSystem.emit("PLAYER_DAMAGE", {
        amount = amount, flags = flags,
        source_type = source and source.Type or -1,
        hp_after = player:GetHearts() + player:GetSoulHearts(),
    })
end)

-- MC_POST_NPC_DEATH — NPC killed
mod:AddCallback(ModCallbacks.MC_POST_NPC_DEATH, function(_, npc)
    SensorTriggers:fire("MC_POST_NPC_DEATH", npc,
        function(name) SensorRegistry:collect(name, true) end)
    EventSystem.emit("NPC_DEATH", {
        type = npc.Type, variant = npc.Variant, subtype = npc.SubType,
        pos = Helpers.vectorToTable(npc.Position), is_boss = npc:IsBoss(),
    })
end)

-- MC_POST_PLAYER_DEATH — player death
mod:AddCallback(ModCallbacks.MC_POST_PLAYER_DEATH, function(_, player)
    EventSystem.emit("PLAYER_DEATH", { player_idx = player:GetPlayerIndex() })
    Network.disconnect()
end)

-- MC_POST_GAME_STARTED — game start
mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function(_, continued)
    State.updateCount = 0
    State.currentRoom = -1
    State.messageSeq = 0
    State.prevFrameSent = 0
    InputExecutor.reset()

    -- Reset sensor caches
    for name, _ in pairs(SensorRegistry.sensors) do
        SensorRegistry.cache[name] = nil
        SensorRegistry.changeHashes[name] = nil
    end

    EventSystem.emit("GAME_START", { continued = continued })

    if State.connected then
        local fullState, channels, meta = SensorRegistry:forceCollectAll()
        Network.send(Protocol.createFullStateMessage(fullState, channels, meta))
    end
end)

-- MC_PRE_GAME_EXIT — game exit
mod:AddCallback(ModCallbacks.MC_PRE_GAME_EXIT, function(_, shouldSave)
    EventSystem.emit("GAME_END", { reason = shouldSave and "exit_save" or "exit_nosave" })
    EventSystem.flush()
    Network.disconnect()
end)

-- MC_POST_ADD_COLLECTIBLE — item collected
mod:AddCallback(ModCallbacks.MC_POST_ADD_COLLECTIBLE, function(_, itemId, charge, firstTime, slot, varData, player)
    EventSystem.emit("ITEM_COLLECTED", {
        item_id = itemId, first_time = firstTime, slot = slot,
        player_idx = player:GetPlayerIndex(),
    })
end)

-- MC_POST_PICKUP_INIT — new pickup spawned (v3.0: callback-driven PICKUPS)
mod:AddCallback(ModCallbacks.MC_POST_PICKUP_INIT, function(_, pickup)
    SensorTriggers:fire("MC_POST_PICKUP_INIT", pickup,
        function(name) SensorRegistry:collect(name, true) end)
end)

-- ============================================================================
-- Debug command
-- ============================================================================
mod:AddCallback(ModCallbacks.MC_EXECUTE_CMD, function(_, cmd, params)
    if cmd == "sbdebug" then
        local player = Isaac.GetPlayer(0)
        if player then
            print("[SocketBridge Debug] Coins: " .. player:GetNumCoins() ..
                  ", Bombs: " .. player:GetNumBombs() .. ", Keys: " .. player:GetNumKeys())
            print("[SocketBridge Debug] Collectible Count: " .. player:GetCollectibleCount())
        end
        return true
    end
end)

-- ============================================================================
-- Public API
-- ============================================================================
mod.SensorRegistry = SensorRegistry
mod.EventSystem = EventSystem
mod.Protocol = Protocol
mod.Config = Config
mod.InputExecutor = InputExecutor
mod.CommandHandler = CommandHandler
mod.shouldAIControl = shouldAIControl

print("[SocketBridge] v3.0 loaded — Sensor-based Data Collection Framework")
print("[SocketBridge] Server: " .. Config.HOST .. ":" .. Config.PORT)
print("[SocketBridge] F3: Toggle Manual/AI Mode")
print("[SocketBridge] Console: 'sbdebug' to test inventory API")
