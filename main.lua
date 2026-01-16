--[[
    The Binding of Isaac: Repentance - 模块化数据采集框架
    
    架构设计:
    1. CollectorRegistry - 可扩展的数据收集器注册系统
    2. Network - 网络通信层
    3. Protocol - 消息协议层
    4. InputExecutor - 输入执行模块
    5. EventSystem - 事件系统
    
    支持功能:
    - 分频采集 (HIGH/MEDIUM/LOW/ON_CHANGE)
    - 动态启用/禁用采集通道
    - 增量数据更新
    - 双向命令通信
]]

local mod = RegisterMod("SocketBridge", 1)
local json = require("json")

-- ============================================================================
-- 配置系统
-- ============================================================================
local Config = {
    HOST = "127.0.0.1",
    PORT = 9527,
    
    -- 采集频率配置（帧数间隔）
    CollectIntervals = {
        HIGH = 1,       -- 每帧采集
        MEDIUM = 5,     -- 5帧一次
        LOW = 30,       -- 30帧一次
        RARE = 90,      -- 90帧一次
        ON_CHANGE = -1  -- 仅在变化时采集
    },
}

-- ============================================================================
-- 全局状态
-- ============================================================================
local State = {
    connected = false,
    socket = nil,
    frameCounter = 0,
    currentRoomIndex = -1,
    
    -- 控制模式
    -- 模式选项:
    --   "MANUAL"      - 手动控制
    --   "AUTO"        - 自动切换（有敌人AI，无敌人手动）
    --   "FORCE_AI"    - 强制AI模式（无敌人也生效）
    controlMode = "AUTO",
    
    -- 内部状态追踪
    lastEnemyCount = 0,
    wasInCombat = false,  -- 上一帧是否在战斗中
    aiActive = false,     -- AI 是否正在发送非零输入
    toggleCooldown = 0,
    showModeMessage = false,
    modeMessageTimer = 0,
}

-- ============================================================================
-- 输入执行模块
-- ============================================================================
local InputExecutor = {
    moveDirection = {x = 0, y = 0},
    shootDirection = {x = 0, y = 0},
    useItem = false,
    useBomb = false,
    useCard = false,
    usePill = false,
    drop = false,
}

function InputExecutor.applyCommand(command)
    if not command then return end
    
    local hasInput = false
    
    if command.move then
        InputExecutor.moveDirection = command.move
        -- 检查是否有非零移动输入
        if command.move.x ~= 0 or command.move.y ~= 0 then
            hasInput = true
        end
    end
    if command.shoot then
        InputExecutor.shootDirection = command.shoot
        -- 检查是否有非零射击输入
        if command.shoot.x ~= 0 or command.shoot.y ~= 0 then
            hasInput = true
        end
    end
    if command.use_item ~= nil then
        InputExecutor.useItem = command.use_item
        if command.use_item then hasInput = true end
    end
    if command.use_bomb ~= nil then
        InputExecutor.useBomb = command.use_bomb
        if command.use_bomb then hasInput = true end
    end
    if command.use_card ~= nil then
        InputExecutor.useCard = command.use_card
        if command.use_card then hasInput = true end
    end
    if command.use_pill ~= nil then
        InputExecutor.usePill = command.use_pill
        if command.use_pill then hasInput = true end
    end
    if command.drop ~= nil then
        InputExecutor.drop = command.drop
        if command.drop then hasInput = true end
    end
    
    -- 标记 AI 是否正在发送有效输入
    State.aiActive = hasInput
end

function InputExecutor.reset()
    InputExecutor.moveDirection = {x = 0, y = 0}
    InputExecutor.shootDirection = {x = 0, y = 0}
    InputExecutor.useItem = false
    InputExecutor.useBomb = false
    InputExecutor.useCard = false
    InputExecutor.usePill = false
    InputExecutor.drop = false
    State.aiActive = false
end

-- 获取当前控制模式
function GetControlMode()
    return State.controlMode
end

-- 设置控制模式
function SetControlMode(mode)
    if mode == "MANUAL" or mode == "AUTO" or mode == "FORCE_AI" then
        State.controlMode = mode
        State.forceAI = (mode == "FORCE_AI")
        -- 切换到手动模式时立即重置输入
        if mode == "MANUAL" then
            InputExecutor.reset()
            State.wasInCombat = false
        end
        print("[SocketBridge] Control mode set to: " .. mode)
    end
end

-- 判断当前是否应该由 AI 控制
local function shouldAIControl()
    local mode = State.controlMode
    
    if mode == "MANUAL" then
        -- 总是确保手动模式下没有残留的 AI 输入
        if State.wasInCombat then
            InputExecutor.reset()
            State.wasInCombat = false
        end
        -- 即使 wasInCombat 为 false，也确保重置输入（处理从未战斗的情况）
        InputExecutor.reset()
        return false
    elseif mode == "FORCE_AI" then
        State.wasInCombat = true
        return true
    end
    
    -- AUTO 模式: 根据敌人存在与否自动切换
    local room = Game():GetRoom()
    local enemyCount = room and room:GetAliveEnemiesCount() or 0
    
    -- 检测战斗状态变化
    local isInCombat = enemyCount > 0
    
    -- 状态变化检测
    -- 只有当 AI 实际发送输入时，才认为 AI 在控制
    if State.aiActive then
        State.wasInCombat = true
    end
    
    -- AI 正在控制且有敌人时，阻止玩家输入
    if isInCombat and State.aiActive then
        return true
    end
    
    -- 如果没有敌人，或者敌人存在但 AI 未发送输入，玩家可以手动控制
    if not isInCombat then
        -- 战斗结束，切换回手动
        if State.wasInCombat then
            InputExecutor.reset()
            State.wasInCombat = false
        end
    end
    
    return false
end

-- ============================================================================
-- 辅助函数
-- ============================================================================
local Helpers = {}

function Helpers.vectorToTable(vec)
    if vec then
        return { x = vec.X, y = vec.Y }
    end
    return { x = 0, y = 0 }
end

function Helpers.colorToTable(color)
    if color then
        return { r = color.R, g = color.G, b = color.B, a = color.A }
    end
    return nil
end

function Helpers.getGame()
    return Game()
end

function Helpers.getRoom()
    return Game():GetRoom()
end

function Helpers.getLevel()
    return Game():GetLevel()
end

function Helpers.getPlayers()
    local game = Game()
    local players = {}
    for i = 0, game:GetNumPlayers() - 1 do
        local player = Isaac.GetPlayer(i)
        if player then
            table.insert(players, player)
        end
    end
    return players
end

-- ============================================================================
-- 网络层
-- ============================================================================
local Network = {
    retryInterval = 60,
    lastRetryFrame = 0,
}

function Network.connect()
    if State.connected then return true end
    
    if State.frameCounter - Network.lastRetryFrame < Network.retryInterval then
        return false
    end
    Network.lastRetryFrame = State.frameCounter
    
    local success, result = pcall(function()
        local socket = require("socket.core")
        local tcp = socket.tcp()
        tcp:settimeout(0.01)
        local connectResult = tcp:connect(Config.HOST, Config.PORT)
        return tcp, connectResult
    end)
    
    if success and result then
        State.socket = result
        State.connected = true
        print("[SocketBridge] Connected to server")
        return true
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
    
    if not success then
        Network.disconnect()
        return false
    end
    return true
end

function Network.receive()
    if not State.connected then return nil end
    
    local success, line, err = pcall(function()
        return State.socket:receive("*l")
    end)
    
    if success and line then
        local ok, data = pcall(json.decode, line)
        if ok then
            return data
        end
    elseif err == "closed" then
        Network.disconnect()
    end
    
    return nil
end

-- ============================================================================
-- 协议层
-- ============================================================================
local Protocol = {
    VERSION = "2.0",
    MessageType = {
        DATA = "DATA",
        FULL_STATE = "FULL",
        EVENT = "EVENT",
        COMMAND = "CMD",
    }
}

function Protocol.createDataMessage(data, channels)
    return {
        version = Protocol.VERSION,
        type = Protocol.MessageType.DATA,
        timestamp = Isaac.GetTime(),
        frame = State.frameCounter,
        room_index = State.currentRoomIndex,
        payload = data,
        channels = channels
    }
end

function Protocol.createEventMessage(eventType, eventData)
    return {
        version = Protocol.VERSION,
        type = Protocol.MessageType.EVENT,
        timestamp = Isaac.GetTime(),
        frame = State.frameCounter,
        event = eventType,
        data = eventData
    }
end

-- ============================================================================
-- 收集器注册系统
-- ============================================================================
local CollectorRegistry = {
    collectors = {},
    cache = {},
    frameCounters = {},
    changeHashes = {},
}

function CollectorRegistry:register(name, config)
    self.collectors[name] = {
        name = name,
        enabled = config.enabled ~= false,
        interval = config.interval or "MEDIUM",
        priority = config.priority or 5,
        collect = config.collect,
        hash = config.hash,
    }
    self.frameCounters[name] = 0
    self.cache[name] = nil
    self.changeHashes[name] = nil
end

function CollectorRegistry:setEnabled(name, enabled)
    if self.collectors[name] then
        self.collectors[name].enabled = enabled
    end
end

function CollectorRegistry:setInterval(name, interval)
    if self.collectors[name] then
        self.collectors[name].interval = interval
    end
end

function CollectorRegistry:shouldCollect(name)
    local collector = self.collectors[name]
    if not collector or not collector.enabled then
        return false
    end
    
    local interval = Config.CollectIntervals[collector.interval]
    if interval == -1 then
        return true -- ON_CHANGE 模式
    end
    
    self.frameCounters[name] = (self.frameCounters[name] or 0) + 1
    if self.frameCounters[name] >= interval then
        self.frameCounters[name] = 0
        return true
    end
    return false
end

-- 简单哈希用于变化检测
local function simpleHash(data)
    if type(data) ~= "table" then
        return tostring(data)
    end
    local str = ""
    for k, v in pairs(data) do
        if type(v) == "table" then
            str = str .. k .. simpleHash(v)
        else
            str = str .. k .. tostring(v)
        end
    end
    return str
end

function CollectorRegistry:collect(name, forceCollect)
    local collector = self.collectors[name]
    if not collector then return nil end
    
    if not forceCollect and not self:shouldCollect(name) then
        return nil
    end
    
    local success, data = pcall(collector.collect)
    if not success or data == nil then
        return nil
    end
    
    -- ON_CHANGE 变化检测
    if collector.interval == "ON_CHANGE" and not forceCollect then
        local hashFunc = collector.hash or simpleHash
        local newHash = hashFunc(data)
        if self.changeHashes[name] == newHash then
            return nil
        end
        self.changeHashes[name] = newHash
    end
    
    self.cache[name] = data
    return data
end

function CollectorRegistry:collectAll()
    local results = {}
    local collectedChannels = {}
    
    for name, _ in pairs(self.collectors) do
        local data = self:collect(name, false)
        if data ~= nil then
            results[name] = data
            table.insert(collectedChannels, name)
        end
    end
    
    return results, collectedChannels
end

function CollectorRegistry:forceCollectAll()
    local results = {}
    for name, _ in pairs(self.collectors) do
        local data = self:collect(name, true)
        if data ~= nil then
            results[name] = data
        end
    end
    return results
end

function CollectorRegistry:getCached(name)
    return self.cache[name]
end

function CollectorRegistry:getAllCached()
    local results = {}
    for name, data in pairs(self.cache) do
        if data ~= nil then
            results[name] = data
        end
    end
    return results
end

function CollectorRegistry:getConfig()
    local config = {}
    for name, collector in pairs(self.collectors) do
        config[name] = {
            enabled = collector.enabled,
            interval = collector.interval,
            priority = collector.priority
        }
    end
    return config
end

-- ============================================================================
-- 数据收集器定义
-- ============================================================================

-- 玩家位置 (高频)
CollectorRegistry:register("PLAYER_POSITION", {
    interval = "HIGH",
    priority = 10,
    collect = function()
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
})

-- 玩家属性 (低频)
CollectorRegistry:register("PLAYER_STATS", {
    interval = "LOW",
    priority = 5,
    collect = function()
        local players = Helpers.getPlayers()
        local data = {}
        for i, player in ipairs(players) do
            local tearRange = player.TearRange
            data[i] = {
                player_type = player:GetPlayerType(),
                damage = player.Damage,
                speed = player.MoveSpeed,
                tears = player.MaxFireDelay,
                range = player.TearRange,
                tear_range = tearRange,
                shot_speed = player.ShotSpeed,
                luck = player.Luck,
                tear_height = player.TearHeight,
                tear_falling_speed = player.TearFallingSpeed,
                can_fly = player.CanFly,
                size = player.Size,
                sprite_scale = player.SpriteScale.X,
            }
        end
        return data
    end
})

-- 玩家生命值 (实时检测，稍低频率)
CollectorRegistry:register("PLAYER_HEALTH", {
    interval = "LOW",
    priority = 8,
    collect = function()
        local players = Helpers.getPlayers()
        local data = {}
        for i, player in ipairs(players) do
            data[i] = {
                red_hearts = player:GetHearts(),
                max_hearts = player:GetMaxHearts(),
                soul_hearts = player:GetSoulHearts(),
                black_hearts = player:GetBlackHearts(),
                bone_hearts = player:GetBoneHearts(),
                golden_hearts = player:GetGoldenHearts(),
                eternal_hearts = player:GetEternalHearts(),
                rotten_hearts = player:GetRottenHearts(),
                broken_hearts = player:GetBrokenHearts(),
                extra_lives = player:GetExtraLives(),
            }
        end
        return data
    end
})

-- 玩家物品栏 (低频采集)
CollectorRegistry:register("PLAYER_INVENTORY", {
    interval = "RARE",
    priority = 3,
    collect = function()
        local players = Helpers.getPlayers()
        local data = {}
        for i, player in ipairs(players) do
            -- 基础资源（这些应该总是能获取到）
            local playerData = {
                -- 消耗品
                coins = player:GetNumCoins(),
                bombs = player:GetNumBombs(),
                keys = player:GetNumKeys(),
                -- 饰品
                trinket_0 = player:GetTrinket(0),
                trinket_1 = player:GetTrinket(1),
                -- 卡牌/药丸
                card_0 = player:GetCard(0),
                pill_0 = player:GetPill(0),
                -- 收集品总数
                collectible_count = player:GetCollectibleCount(),
            }
            
            -- 收集物品（使用安全的固定上限）
            local items = {}
            local maxItemId = 733  -- Repentance 最大物品 ID（固定值避免常量问题）
            
            -- 只在有收集品时才遍历
            if playerData.collectible_count > 0 then
                for itemId = 1, maxItemId do
                    -- 先用 HasCollectible 检查（更快）
                    if player:HasCollectible(itemId, true) then
                        local count = player:GetCollectibleNum(itemId, true)
                        if count > 0 then
                            items[tostring(itemId)] = count
                        end
                    end
                end
            end
            playerData.collectibles = items
            
            -- 主动道具槽位
            local activeSlots = {}
            for slot = 0, 3 do
                local activeItem = player:GetActiveItem(slot)
                if activeItem > 0 then
                    activeSlots[tostring(slot)] = {
                        item = activeItem,
                        charge = player:GetActiveCharge(slot),
                        max_charge = player:GetActiveMaxCharge(slot),
                        battery_charge = player:GetBatteryCharge(slot)
                    }
                end
            end
            playerData.active_items = activeSlots
            
            data[i] = playerData
        end
        return data
    end
})

-- 敌人 (高频)
CollectorRegistry:register("ENEMIES", {
    interval = "HIGH",
    priority = 7,
    collect = function()
        local player = Isaac.GetPlayer(0)
        if not player then return {} end
        
        local playerPos = player.Position
        local enemies = {}
        
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if entity:IsActiveEnemy(false) and entity:IsVulnerableEnemy() then
                local npc = entity:ToNPC()
                
                local targetPos = {x = 0, y = 0}
                if npc then
                    local target = npc:GetPlayerTarget()
                    if target then
                        targetPos = Helpers.vectorToTable(target.Position)
                    end
                end
                
                local dist = playerPos:Distance(entity.Position)
                
                table.insert(enemies, {
                    id = entity.Index,
                    type = entity.Type,
                    variant = entity.Variant,
                    subtype = entity.SubType,
                    pos = Helpers.vectorToTable(entity.Position),
                    vel = Helpers.vectorToTable(entity.Velocity),
                    hp = entity.HitPoints,
                    max_hp = entity.MaxHitPoints,
                    is_boss = entity:IsBoss(),
                    is_champion = npc and npc:IsChampion() or false,
                    state = npc and npc.State or 0,
                    state_frame = npc and npc.StateFrame or 0,
                    projectile_cooldown = npc and npc.ProjectileCooldown or 0,
                    projectile_delay = npc and npc.ProjectileDelay or 0,
                    collision_radius = entity.Size,
                    distance = dist,
                    target_pos = targetPos,
                    v1 = npc and Helpers.vectorToTable(npc.V1) or {x=0, y=0},
                    v2 = npc and Helpers.vectorToTable(npc.V2) or {x=0, y=0},
                })
            end
        end
        
        return enemies
    end
})

-- 投射物 (高频)
CollectorRegistry:register("PROJECTILES", {
    interval = "HIGH",
    priority = 9,
    collect = function()
        local player = Isaac.GetPlayer(0)
        if not player then return {} end
        
        local playerPos = player.Position
        local data = {
            enemy_projectiles = {},
            player_tears = {},
            lasers = {},
        }
        
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if entity.Type == EntityType.ENTITY_PROJECTILE then
                local proj = entity:ToProjectile()
                table.insert(data.enemy_projectiles, {
                    id = entity.Index,
                    pos = Helpers.vectorToTable(entity.Position),
                    vel = Helpers.vectorToTable(entity.Velocity),
                    variant = entity.Variant,
                    collision_radius = entity.Size,
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
                    variant = entity.Variant,
                    collision_radius = entity.Size,
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
                        angle = laser.Angle,
                        max_distance = laser.MaxDistance,
                        is_enemy = entity:IsEnemy(),
                    })
                end
            end
            
            ::continue::
        end
        
        return data
    end
})

-- 房间信息 (中频 - 战斗中 is_clear 状态变化频繁)
CollectorRegistry:register("ROOM_INFO", {
    interval = "LOW",
    priority = 4,
    collect = function()
        local room = Helpers.getRoom()
        local level = Helpers.getLevel()
        if not room then return nil end
        
        local tl = room:GetTopLeftPos()
        local br = room:GetBottomRightPos()
        local roomDesc = level:GetCurrentRoomDesc()
        
        return {
            room_type = room:GetType(),
            room_shape = room:GetRoomShape(),
            room_idx = level:GetCurrentRoomIndex(),
            stage = level:GetStage(),
            stage_type = level:GetStageType(),
            difficulty = Game().Difficulty,
            is_clear = room:IsClear(),
            is_first_visit = room:IsFirstVisit(),
            grid_width = room:GetGridWidth(),
            grid_height = room:GetGridHeight(),
            top_left = Helpers.vectorToTable(tl),
            bottom_right = Helpers.vectorToTable(br),
            has_boss = room:GetBossID() > 0,
            enemy_count = room:GetAliveEnemiesCount(),
            room_variant = roomDesc and roomDesc.Data and roomDesc.Data.Variant or 0,
        }
    end
})

-- 房间布局/障碍物 (变化时)
-- 采集所有 GridEntityType 枚举的实体 (ID 0-27)
-- Python端负责分类逻辑（可破坏物、障碍物、危险区域等）
CollectorRegistry:register("ROOM_LAYOUT", {
    interval = "LOW",
    priority = 2,
    collect = function()
        local room = Helpers.getRoom()
        if not room then return nil end

        local grid = {}
        local doors = {}
        local width = room:GetGridWidth()

        -- GridEntityType 枚举常量 (参考游戏源码)
        -- 0: NULL, 1: DECORATION, 2: ROCK, 3: ROCKB, 4: ROCKT, 5: ROCK_BOMB, 6: ROCK_ALT
        -- 7: PIT, 8: SPIKES, 9: SPIKES_ONOFF, 10: SPIDERWEB, 11: LOCK, 12: TNT, 13: FIREPLACE (not used)
        -- 14: POOP, 15: WALL, 16: DOOR, 17: TRAPDOOR, 18: STAIRS, 19: GRAVITY, 20: PRESSURE_PLATE
        -- 21: STATUE, 22: ROCK_SS, 23: TELEPORTER, 24: PILLAR, 25: ROCK_SPIKED, 26: ROCK_ALT2, 27: ROCK_GOLD

        for i = 0, room:GetGridSize() - 1 do
            local gridEntity = room:GetGridEntity(i)
            if gridEntity then
                local gridType = gridEntity:GetType()

                -- 收集所有 GridEntityType 枚举的实体 (0-27)
                -- 不做排除
                if gridType >= 0 and gridType <= 27  then
                    local collision = gridEntity.CollisionClass
                    local variant = gridEntity:GetVariant()
                    local state = gridEntity.State
                    local pos = room:GetGridPosition(i)

                    -- 发送原始字段，Python端负责分类
                    grid[tostring(i)] = {
                        type = gridType,        -- GridEntityType ID
                        variant = variant,      -- 变体ID (0-255)
                        state = state,          -- 状态值
                        collision = collision,  -- 碰撞类型 (GridCollision)
                        x = pos.X,              -- 世界坐标X
                        y = pos.Y,              -- 世界坐标Y
                    }
                end
            end
        end

        for slot = 0, DoorSlot.NUM_DOOR_SLOTS - 1 do
            local door = room:GetDoor(slot)
            if door then
                -- 获取门的世界坐标
                local doorPos = door.Position
                doors[tostring(slot)] = {
                    target_room = door.TargetRoomIndex,
                    target_room_type = door.TargetRoomType,
                    is_open = door:IsOpen(),
                    is_locked = door:IsLocked(),
                    x = doorPos.X,
                    y = doorPos.Y,
                }
            end
        end

        return {
            grid = grid,
            doors = doors,
            grid_size = room:GetGridSize(),
            width = width,
            height = room:GetGridHeight(),
        }
    end
})

-- 炸弹 (中频)
CollectorRegistry:register("BOMBS", {
    interval = "LOW",
    priority = 5,
    collect = function()
        local player = Isaac.GetPlayer(0)
        if not player then return {} end
        
        local playerPos = player.Position
        local bombs = {}
        
        -- 炸弹变种类型定义
        local BOMB_VARIANTS = {
            [0] = "NORMAL",          -- 普通炸弹
            [1] = "BIG",             -- 大型炸弹
            [2] = "DECOY",           -- 诱饵
            [3] = "TROLL",           -- 即爆炸弹
            [4] = "MEGA_TROLL",      -- 超级即爆炸弹
            [5] = "POISON",          -- 毒性炸弹
            [6] = "BIG_POISON",      -- 大型毒性炸弹
            [7] = "SAD",             -- 伤心炸弹
            [8] = "HOT",             -- 燃烧炸弹
            [9] = "BUTT",            -- 大便炸弹
            [10] = "MR_MEGA",        -- 大爆弹先生炸弹
            [11] = "BOBBY",          -- 波比炸弹
            [12] = "GLITTER",        -- 闪光炸弹
            [13] = "THROWABLE",      -- 可投掷炸弹
            [14] = "SMALL",          -- 小炸弹
            [15] = "BRIMSTONE",      -- 硫磺火炸弹
            [16] = "BLOODY_SAD",     -- 鲜血伤心炸弹
            [17] = "GIGA",           -- 巨型炸弹
            [18] = "GOLDEN_TROLL",   -- 金即爆炸弹
            [19] = "ROCKET",         -- 火箭
            [20] = "GIGA_ROCKET",    -- 巨型火箭
        }
        
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if entity.Type == EntityType.ENTITY_BOMB then
                local variant = entity.Variant
                local bomb = entity:ToBomb()
                local dist = playerPos:Distance(entity.Position)
                
                local bombType = BOMB_VARIANTS[variant] or ("UNKNOWN_" .. tostring(variant))
                
                table.insert(bombs, {
                    id = entity.Index,
                    type = entity.Type,
                    variant = variant,
                    variant_name = bombType,
                    sub_type = entity.SubType,
                    pos = Helpers.vectorToTable(entity.Position),
                    vel = Helpers.vectorToTable(entity.Velocity),
                    explosion_radius = bomb and bomb.ExplosionRadius or 0,
                    timer = bomb and bomb.Timer or 0,
                    distance = dist,
                })
            end
        end
        
        return bombs
    end
})

-- 可互动实体 (中频)
CollectorRegistry:register("INTERACTABLES", {
    interval = "LOW",
    priority = 4,
    collect = function()
        local player = Isaac.GetPlayer(0)
        if not player then return {} end
        
        local playerPos = player.Position
        local interactables = {}
        
        -- 可互动实体变种类型定义
        local INTERACTABLE_VARIANTS = {
            [1] = "SLOT_MACHINE",         -- 赌博机
            [2] = "BLOOD_DONATION",       -- 献血机
            [3] = "FORTUNE_TELLING",      -- 预言机
            [4] = "BEGGAR",               -- 乞丐
            [5] = "DEVIL_BEGGAR",         -- 恶魔乞丐
            [6] = "SHELL_GAME",           -- 赌博乞丐
            [7] = "KEY_MASTER",           -- 钥匙大师
            [8] = "DONATION_MACHINE",     -- 捐款机
            [9] = "BOMB_BUM",             -- 炸弹乞丐
            [10] = "RESTOCK_MACHINE",     -- 补货机
            [11] = "GREED_MACHINE",       -- 贪婪机
            [12] = "MOMS_DRESSING_TABLE", -- 妈妈的梳妆台
            [13] = "BATTERY_BUM",         -- 电池乞丐
            [14] = "ISAAC_SECRET",        -- 以撒（隐藏）
            [15] = "HELL_GAME",           -- 赌命乞丐
            [16] = "CRANE_GAME",          -- 娃娃机
            [17] = "CONFESSIONAL",        -- 忏悔室
            [18] = "ROTTEN_BEGGAR",       -- 腐烂乞丐
            [19] = "REVIVE_MACHINE",      -- 复活机
        }
        
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if entity.Type == EntityType.ENTITY_PLAYER then
                goto continue
            end
            
            -- 检查是否是可互动实体 (Type 6)
            if entity.Type == 6 then
                local variant = entity.Variant
                local npc = entity:ToNPC()
                local dist = playerPos:Distance(entity.Position)
                
                local interactType = INTERACTABLE_VARIANTS[variant] or ("UNKNOWN_" .. tostring(variant))
                
                -- 获取状态信息
                local state = npc and npc.State or 0
                local stateFrame = npc and npc.StateFrame or 0
                local target = npc and npc:GetPlayerTarget()
                local targetPos = target and Helpers.vectorToTable(target.Position) or {x = 0, y = 0}
                
                table.insert(interactables, {
                    id = entity.Index,
                    type = entity.Type,
                    variant = variant,
                    variant_name = interactType,
                    sub_type = entity.SubType,
                    pos = Helpers.vectorToTable(entity.Position),
                    vel = Helpers.vectorToTable(entity.Velocity),
                    state = state,
                    state_frame = stateFrame,
                    target_pos = targetPos,
                    distance = dist,
                })
            end
            
            ::continue::
        end
        
        return interactables
    end
})

-- 可拾取物 (中频)
CollectorRegistry:register("PICKUPS", {
    interval = "LOW",
    priority = 4,
    collect = function()
        local pickups = {}
        
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if entity.Type == EntityType.ENTITY_PICKUP then
                local pickup = entity:ToPickup()
                table.insert(pickups, {
                    id = entity.Index,
                    variant = entity.Variant,
                    sub_type = entity.SubType,
                    pos = Helpers.vectorToTable(entity.Position),
                    price = pickup and pickup.Price or 0,
                    shop_item_id = pickup and pickup.ShopItemId or -1,
                    wait = pickup and pickup.Wait or 0,
                })
            end
        end
        
        return pickups
    end
})

-- 火焰危险物 (中频)
CollectorRegistry:register("FIRE_HAZARDS", {
    interval = "LOW",
    priority = 6,
    collect = function()
        local player = Isaac.GetPlayer(0)
        if not player then return {} end
        
        local playerPos = player.Position
        local fires = {}
        
        local DANGEROUS_FIRE_EFFECTS = {
            [51] = true,  -- HOT_BOMB_FIRE
            [52] = true,  -- RED_CANDLE_FLAME
        }
        
        -- 火堆变种类型定义
        local FIREPLACE_TYPES = {
            [0] = "NORMAL",      -- 普通火堆
            [1] = "RED",         -- 红色火堆
            [2] = "BLUE",        -- 蓝色火堆
            [3] = "PURPLE",      -- 紫色火堆
            [4] = "WHITE",       -- 白色火堆
            [10] = "MOVABLE",    -- 可移动火堆
            [11] = "COAL",       -- 火炭
            [12] = "MOVABLE_BLUE",   -- 可移动蓝色火堆
            [13] = "MOVABLE_PURPLE", -- 可移动紫色火堆
        }
        
        -- 火堆状态常量
        local FIREPLACE_STATE_EXTINGUISHED = 1000
        
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            -- 处理火焰效果（如炸弹火焰、蜡烛火焰）
            if entity.Type == EntityType.ENTITY_EFFECT then
                if DANGEROUS_FIRE_EFFECTS[entity.Variant] then
                    local dist = playerPos:Distance(entity.Position)
                    -- 移除距离限制，收集所有危险火焰
                    table.insert(fires, {
                            id = entity.Index,
                            type = "EFFECT",
                            variant = entity.Variant,
                            pos = Helpers.vectorToTable(entity.Position),
                            collision_radius = entity.Size > 0 and entity.Size or 20,
                            distance = dist,
                        })
                end
            elseif entity.Type == 33 then  -- ENTITY_FIREPLACE
                local dist = playerPos:Distance(entity.Position)
                -- 移除距离限制，收集所有火堆
                local variant = entity.Variant
                local subVariant = entity.SubType
                
                -- 确定火堆类型名称
                local fireplaceType = FIREPLACE_TYPES[variant] or ("UNKNOWN_" .. tostring(variant))
                
                -- 判断火堆是否点燃（State == 1000 表示已熄灭）
                local isExtinguished = entity.State == FIREPLACE_STATE_EXTINGUISHED
                
                -- 红色/紫色火堆发射泪弹状态检测
                local isShooting = false
                local npc = entity:ToNPC()
                if npc and (variant == 1 or variant == 3) then
                    -- 红色和紫色火堆发射状态是 8
                    isShooting = (npc.State == 8)
                end
                
                table.insert(fires, {
                    id = entity.Index,
                    type = "FIREPLACE",
                    fireplace_type = fireplaceType,
                    variant = variant,
                    sub_variant = subVariant,
                    pos = Helpers.vectorToTable(entity.Position),
                    hp = entity.HitPoints,
                    max_hp = entity.MaxHitPoints,
                    state = entity.State,
                    is_extinguished = isExtinguished,
                    collision_radius = entity.Size > 0 and entity.Size or 25,
                    distance = dist,
                    is_shooting = isShooting,
                    sprite_scale = entity.SpriteScale.X,
                })
            end
        end
        
        return fires
    end
})

-- ============================================================================
-- 命令处理器
-- ============================================================================
local CommandHandler = {
    handlers = {}
}

function CommandHandler.register(command, handler)
    CommandHandler.handlers[command] = handler
end

function CommandHandler.process(cmdMessage)
    if not cmdMessage then return nil end
    
    -- 直接是输入指令 (move/shoot)
    if cmdMessage.move or cmdMessage.shoot then
        return nil  -- 由 InputExecutor 处理
    end
    
    -- 命令类型消息
    if cmdMessage.command then
        local handler = CommandHandler.handlers[cmdMessage.command]
        if handler then
            return handler(cmdMessage.params or {})
        end
    end
    
    return nil
end

-- 注册命令
CommandHandler.register("SET_CHANNEL", function(params)
    if params.channel and params.enabled ~= nil then
        CollectorRegistry:setEnabled(params.channel, params.enabled)
        return { success = true, channel = params.channel, enabled = params.enabled }
    end
    return { success = false, error = "Invalid params" }
end)

CommandHandler.register("SET_INTERVAL", function(params)
    if params.channel and params.interval then
        CollectorRegistry:setInterval(params.channel, params.interval)
        return { success = true }
    end
    return { success = false, error = "Invalid params" }
end)

CommandHandler.register("GET_FULL_STATE", function(params)
    local fullState = CollectorRegistry:forceCollectAll()
    Network.send({
        version = Protocol.VERSION,
        type = Protocol.MessageType.FULL_STATE,
        frame = State.frameCounter,
        payload = fullState
    })
    return { success = true }
end)

CommandHandler.register("GET_CONFIG", function(params)
    return { success = true, config = CollectorRegistry:getConfig() }
end)

CommandHandler.register("SET_MANUAL", function(params)
    if params.enabled ~= nil then
        if params.enabled then
            State.controlMode = "MANUAL"
        else
            State.controlMode = "AUTO"  -- 切换回自动模式
        end
        -- 清除正在进行的输入
        InputExecutor.moveDirection = {x = 0, y = 0}
        InputExecutor.shootDirection = {x = 0, y = 0}
        return { success = true, mode = State.controlMode }
    end
    return { success = false, error = "Invalid params" }
end)

-- 强制AI模式（无敌人时也生效）- 保留向后兼容
CommandHandler.register("SET_FORCE_AI", function(params)
    if params.enabled ~= nil then
        State.controlMode = params.enabled and "FORCE_AI" or "AUTO"
        return { success = true, mode = State.controlMode }
    end
    return { success = false, error = "Invalid params" }
end)

-- 设置控制模式（支持三种模式）
CommandHandler.register("SET_CONTROL_MODE", function(params)
    local mode = params.mode
    if mode and (mode == "MANUAL" or mode == "AUTO" or mode == "FORCE_AI") then
        State.controlMode = mode
        -- 清除正在进行的输入
        InputExecutor.moveDirection = {x = 0, y = 0}
        InputExecutor.shootDirection = {x = 0, y = 0}
        return { success = true, mode = mode }
    end
    return { success = false, error = "Invalid mode. Use: MANUAL, AUTO, or FORCE_AI" }
end)

-- 获取当前控制模式
CommandHandler.register("GET_CONTROL_MODE", function(params)
    return { success = true, mode = State.controlMode }
end)

-- 控制台指令执行
CommandHandler.register("EXEC_CONSOLE", function(params)
    if params.command then
        -- 使用 Isaac.ExecuteCommand 执行控制台指令
        local success, result = pcall(function()
            return Isaac.ExecuteCommand(params.command)
        end)
        
        if success then
            return { 
                success = true, 
                command = params.command,
                result = result or ""
            }
        else
            return { 
                success = false, 
                error = result,
                command = params.command
            }
        end
    end
    return { success = false, error = "No command provided" }
end)

-- ============================================================================
-- 事件系统
-- ============================================================================
local EventSystem = {
    pendingEvents = {}
}

function EventSystem.emit(eventType, eventData)
    table.insert(EventSystem.pendingEvents, {
        type = eventType,
        data = eventData or {},
        frame = State.frameCounter
    })
end

function EventSystem.flush()
    for _, event in ipairs(EventSystem.pendingEvents) do
        Network.send(Protocol.createEventMessage(event.type, event.data))
    end
    EventSystem.pendingEvents = {}
end

-- ============================================================================
-- 回调函数
-- ============================================================================

-- 每帧更新
mod:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
    State.frameCounter = State.frameCounter + 1
    
    -- 冷却计时
    if State.toggleCooldown > 0 then State.toggleCooldown = State.toggleCooldown - 1 end
    if State.modeMessageTimer > 0 then State.modeMessageTimer = State.modeMessageTimer - 1 end
    
    -- F3 切换手动/AI模式
    if Input.IsButtonPressed(Keyboard.KEY_F3, 0) and State.toggleCooldown == 0 then
        State.forceManual = not State.forceManual
        State.toggleCooldown = 20
        State.showModeMessage = true
        State.modeMessageTimer = 90
        print("[SocketBridge] Manual mode: " .. (State.forceManual and "ON" or "OFF"))
        
        if State.forceManual then
            InputExecutor.reset()
        end
    end
    
    local player = Isaac.GetPlayer(0)
    if not player then return end
    
    -- 连接服务器
    if not State.connected then
        Network.connect()
    end
    
    -- 检测房间变化
    local currentRoom = Game():GetLevel():GetCurrentRoomIndex()
    if currentRoom ~= State.currentRoomIndex then
        State.currentRoomIndex = currentRoom
        
        -- 强制更新房间相关数据
        CollectorRegistry:collect("ROOM_INFO", true)
        CollectorRegistry:collect("ROOM_LAYOUT", true)
        CollectorRegistry:collect("PICKUPS", true)
        
        EventSystem.emit("ROOM_ENTER", {
            room_index = currentRoom,
            room_info = CollectorRegistry:getCached("ROOM_INFO"),
            room_layout = CollectorRegistry:getCached("ROOM_LAYOUT"),
        })
    end
    
    -- 收集并发送数据
    if State.connected then
        local data, channels = CollectorRegistry:collectAll()
        if next(data) then
            Network.send(Protocol.createDataMessage(data, channels))
        end
        
        -- 发送待处理事件
        EventSystem.flush()
        
        -- 接收并处理命令
        local command = Network.receive()
        if command then
            -- 处理系统命令
            local result = CommandHandler.process(command)
            if result then
                Network.send({
                    version = Protocol.VERSION,
                    type = Protocol.MessageType.COMMAND,
                    frame = State.frameCounter,
                    result = result
                })
            end
            
            -- 处理输入命令
            InputExecutor.applyCommand(command)
        end
    end
end)

-- 输入回调
mod:AddCallback(ModCallbacks.MC_INPUT_ACTION, function(_, entity, hook, action)
    if not entity or entity.Type ~= EntityType.ENTITY_PLAYER then return nil end
    
    -- 非 AI 控制模式：不拦截
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
    
    -- 移动输入
    if action == ButtonAction.ACTION_LEFT then
        return ret(moveDir and moveDir.x == -1)
    elseif action == ButtonAction.ACTION_RIGHT then
        return ret(moveDir and moveDir.x == 1)
    elseif action == ButtonAction.ACTION_UP then
        return ret(moveDir and moveDir.y == -1)
    elseif action == ButtonAction.ACTION_DOWN then
        return ret(moveDir and moveDir.y == 1)
    end
    
    -- 射击输入
    if action == ButtonAction.ACTION_SHOOTLEFT then
        return ret(shootDir and shootDir.x == -1)
    elseif action == ButtonAction.ACTION_SHOOTRIGHT then
        return ret(shootDir and shootDir.x == 1)
    elseif action == ButtonAction.ACTION_SHOOTUP then
        return ret(shootDir and shootDir.y == -1)
    elseif action == ButtonAction.ACTION_SHOOTDOWN then
        return ret(shootDir and shootDir.y == 1)
    end
    
    -- 预留其他操控输入
    if action == ButtonAction.ACTION_ITEM then
        return ret(InputExecutor.useItem)
    elseif action == ButtonAction.ACTION_BOMB then
        return ret(InputExecutor.useBomb)
    elseif action == ButtonAction.ACTION_PILLCARD then
        return ret(InputExecutor.useCard or InputExecutor.usePill)
    elseif action == ButtonAction.ACTION_DROP then
        return ret(InputExecutor.drop)
    end
    
    return nil
end)

-- 房间清除
mod:AddCallback(ModCallbacks.MC_PRE_SPAWN_CLEAN_AWARD, function()
    InputExecutor.reset()
    EventSystem.emit("ROOM_CLEAR", {
        room_index = State.currentRoomIndex,
    })
end)

-- 玩家受伤
mod:AddCallback(ModCallbacks.MC_ENTITY_TAKE_DMG, function(_, entity, amount, flags, source)
    if entity.Type ~= EntityType.ENTITY_PLAYER then return end
    
    local player = entity:ToPlayer()
    EventSystem.emit("PLAYER_DAMAGE", {
        amount = amount,
        flags = flags,
        source_type = source and source.Type or -1,
        hp_after = player:GetHearts() + player:GetSoulHearts(),
    })
end)

-- NPC 死亡
mod:AddCallback(ModCallbacks.MC_POST_NPC_DEATH, function(_, npc)
    EventSystem.emit("NPC_DEATH", {
        type = npc.Type,
        variant = npc.Variant,
        subtype = npc.SubType,
        pos = Helpers.vectorToTable(npc.Position),
        is_boss = npc:IsBoss(),
    })
end)

-- 玩家死亡
mod:AddCallback(ModCallbacks.MC_POST_PLAYER_DEATH, function(_, player)
    EventSystem.emit("PLAYER_DEATH", {
        player_idx = player:GetPlayerIndex(),
    })
    Network.disconnect()
end)

-- 游戏开始
mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, function(_, continued)
    State.frameCounter = 0
    State.currentRoomIndex = -1
    InputExecutor.reset()
    
    -- 重置所有收集器缓存
    for name, _ in pairs(CollectorRegistry.collectors) do
        CollectorRegistry.cache[name] = nil
        CollectorRegistry.changeHashes[name] = nil
    end
    
    EventSystem.emit("GAME_START", {
        continued = continued,
    })
    
    -- 发送完整初始状态
    if State.connected then
        local fullState = CollectorRegistry:forceCollectAll()
        Network.send({
            version = Protocol.VERSION,
            type = Protocol.MessageType.FULL_STATE,
            frame = State.frameCounter,
            payload = fullState
        })
    end
end)

-- 游戏退出
mod:AddCallback(ModCallbacks.MC_PRE_GAME_EXIT, function(_, shouldSave)
    EventSystem.emit("GAME_END", {
        reason = shouldSave and "exit_save" or "exit_nosave",
    })
    EventSystem.flush()
    Network.disconnect()
end)

-- 获得道具
mod:AddCallback(ModCallbacks.MC_POST_ADD_COLLECTIBLE, function(_, itemId, charge, firstTime, slot, varData, player)
    EventSystem.emit("ITEM_COLLECTED", {
        item_id = itemId,
        first_time = firstTime,
        slot = slot,
        player_idx = player:GetPlayerIndex()
    })
end)

-- 渲染 (仅显示模式切换提示)
mod:AddCallback(ModCallbacks.MC_POST_RENDER, function()
    if State.showModeMessage and State.modeMessageTimer > 0 then
        local alpha = math.min(1.0, State.modeMessageTimer / 30)
        local txt = State.forceManual and "MANUAL MODE (F3)" or "AI MODE (F3)"
        local r = State.forceManual and 1.0 or 0.2
        local g = 1.0
        local b = State.forceManual and 0.2 or 1.0
        Isaac.RenderText(txt, 50, 20, r, g, b, alpha)
    end
    
    -- 连接状态小提示 (右上角)
    local connTxt = State.connected and "●" or "○"
    local connR = State.connected and 0.2 or 0.8
    local connG = State.connected and 1.0 or 0.2
    Isaac.RenderText(connTxt, Isaac.GetScreenWidth() - 20, 5, connR, connG, 0.2, 0.8)
end)

-- ============================================================================
-- 调试命令 (控制台输入 sbdebug 测试物品获取)
-- ============================================================================
mod:AddCallback(ModCallbacks.MC_EXECUTE_CMD, function(_, cmd, params)
    if cmd == "sbdebug" then
        local player = Isaac.GetPlayer(0)
        if player then
            print("[SocketBridge Debug] === Player Inventory Test ===")
            print("  Coins: " .. player:GetNumCoins())
            print("  Bombs: " .. player:GetNumBombs())
            print("  Keys: " .. player:GetNumKeys())
            print("  Collectible Count: " .. player:GetCollectibleCount())
            print("  Trinket 0: " .. player:GetTrinket(0))
            print("  Trinket 1: " .. player:GetTrinket(1))
            
            -- 测试几个常见物品
            local testItems = {1, 2, 3, 4, 5, 245, 246}  -- 常见物品 ID
            for _, itemId in ipairs(testItems) do
                local has = player:HasCollectible(itemId, true)
                local count = player:GetCollectibleNum(itemId, true)
                if has or count > 0 then
                    print("  Item " .. itemId .. ": has=" .. tostring(has) .. ", count=" .. count)
                end
            end
            
            print("[SocketBridge Debug] === End ===")
        else
            print("[SocketBridge Debug] No player found")
        end
        return true
    end
end)

-- ============================================================================
-- 公开 API
-- ============================================================================
mod.CollectorRegistry = CollectorRegistry
mod.EventSystem = EventSystem
mod.Protocol = Protocol
mod.Config = Config
mod.InputExecutor = InputExecutor
mod.CommandHandler = CommandHandler
mod.shouldAIControl = shouldAIControl

print("[SocketBridge] v2.0 loaded - Modular Data Collection Framework")
print("[SocketBridge] Server: " .. Config.HOST .. ":" .. Config.PORT)
print("[SocketBridge] F3: Toggle Manual/AI Mode")
print("[SocketBridge] Console: 'sbdebug' to test inventory API")
