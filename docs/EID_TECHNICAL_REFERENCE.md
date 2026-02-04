# External Item Descriptions (EID) 模组技术参考文档

## 目录
1. [概述](#概述)
2. [核心架构](#核心架构)
3. [模块系统](#模块系统)
4. [关键技术实现](#关键技术实现)
5. [API参考](#api参考)
6. [数据结构](#数据结构)
7. [扩展与集成](#扩展与集成)

---

## 概述

External Item Descriptions (EID) 是《以撒的结合》的辅助模组，提供了游戏官方 Mod API 未直接提供的信息读取能力，包括：

- **道具描述显示**：为拾取物、卡牌、药丸、饰品等提供详细说明
- **隐藏信息揭示**：识别诅咒之盲下的道具、未识别药丸效果
- **预测系统**：预测随机道具效果（如传送、Void吸收结果等）
- **合成系统**：Bag of Crafting 配方计算
- **变身进度追踪**：显示变身进度
- **条件性描述**：根据当前玩家状态动态调整描述

### 版本兼容性

```lua
EID.isRepentancePlus = REPENTANCE_PLUS or FontRenderSettings ~= nil
EID.isRepentance = REPENTANCE or EID.isRepentancePlus
```

模组支持三个版本：
- Afterbirth+ (AB+)
- Repentance
- Repentance+ (通过检测 `FontRenderSettings` 类或 `REPENTANCE_PLUS` 变量)

---

## 核心架构

### 入口点 (`main.lua`)

```
┌─────────────────────────────────────────────────────────────┐
│                        main.lua                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  1. 初始化 EID 全局表                                 │   │
│  │  2. 检测游戏版本                                      │   │
│  │  3. 加载配置 (eid_config.lua)                        │   │
│  │  4. 加载功能模块 (features/*.lua)                    │   │
│  │  5. 加载语言包 (descriptions/*.lua)                  │   │
│  │  6. 初始化字体和精灵资源                              │   │
│  │  7. 注册回调函数                                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 主要全局变量

```lua
EID = RegisterMod("External Item Descriptions", 1)
EID.descriptions = {}       -- 所有翻译字符串
EID.ItemNames = {}          -- 所有道具名称
EID.BoC = {}                -- Bag of Crafting 数据
EID.player = nil            -- 主要玩家实体
EID.players = {}            -- 玩家1的所有实体（包括以扫、遗忘）
EID.coopAllPlayers = {}     -- 所有玩家实体
EID.itemConfig = Isaac.GetItemConfig()  -- 游戏物品配置
```

### 模块加载顺序

```lua
require("features.eid_api")                    -- 核心API函数
require("features.eid_modular_descriptions")   -- 模块化描述系统
require("features.eid_modular_data_modifiers") -- 模块化数据修改器
require("features.eid_grid_descriptions")      -- 网格实体描述
require("features.eid_language_manager")       -- 语言管理
require("features.eid_mcm")                    -- Mod Config Menu 集成
require("features.eid_data")                   -- 静态数据定义
require("features.eid_xmldata")                -- XML数据解析
require("features.eid_conditionals")           -- 条件描述系统
require("features.eid_modifiers")              -- 描述修改器
require("features.eid_holdmapdesc")            -- 物品提醒功能
require("features.eid_itemprediction")         -- RNG预测系统
require("features.eid_bagofcrafting")          -- 合成袋系统 (Repentance)
require("features.eid_tmtrainer")              -- TMTRAINER 物品描述
require("features.eid_repentogon")             -- REPENTOGON 扩展支持
```

---

## 模块系统

### 1. 核心API模块 (`eid_api.lua`)

提供所有公共API函数，供其他模组调用。

#### 描述添加函数

```lua
-- 添加收藏品描述
EID:addCollectible(id, description, itemName, language)

-- 添加饰品描述
EID:addTrinket(id, description, itemName, language)

-- 添加卡牌描述
EID:addCard(id, description, itemName, language)

-- 添加药丸描述
EID:addPill(id, description, itemName, language)

-- 添加任意实体描述
EID:addEntity(id, variant, subtype, entityName, description, language)

-- 添加自定义变身
EID:createTransformation(uniqueName, displayName, language)

-- 分配变身给实体
EID:assignTransformation(targetType, targetIdentifier, transformationString)
```

#### 描述获取函数

```lua
-- 获取描述对象
function EID:getDescriptionObj(Type, Variant, SubType, entity, checkModifiers)
    -- 返回 EID_DescObj 结构
end

-- 通过实体获取描述
function EID:getDescriptionObjByEntity(entity)
```

### 2. 条件描述系统 (`eid_conditionals.lua`)

根据游戏状态动态修改描述的核心机制。

#### 条件类型

```lua
-- 物品条件：拥有某物品时修改描述
EID:AddItemConditional(targetItems, requiredItem, textKey, options)

-- 玩家条件：特定角色时修改描述
EID:AddPlayerConditional(targetItems, characterID, textKey, options)

-- 协同条件：物品组合效果
EID:AddSynergyConditional(itemA, itemB, textKeyA, textKeyB, options)

-- 贪婪模式条件
EID:AddConditional(items, EID.IsGreedMode, textKey)
```

#### 示例：塔罗牌布条效果

```lua
-- 塔罗布条增强卡牌效果
EID:AddItemConditional("5.300", 451, nil, {
    locTable = "tarotClothBuffs", 
    replaceColor = "ColorShinyPurple", 
    noFallback = false
})
```

### 3. 描述修改器 (`eid_modifiers.lua`)

在描述生成后应用额外修改。

```lua
-- 添加描述修改器
EID:addDescriptionModifier(modifierName, conditionFunction, callbackFunction, layer)

-- 修改器结构
EID.DescModifiers = {
    {
        Name = "modifierName",
        condition = function(descObj) return boolean end,
        callback = function(descObj) return descObj end,
        Layer = priority
    }
}
```

#### 常见修改器

- **Void 效果预览**：显示 Void 吸收后的属性增益
- **Spindown Dice 预测**：显示道具ID减1后的结果
- **Book of Virtues 协同**：显示主动道具对应的精灵效果
- **Flip 预览**：显示翻转后的道具

### 4. 模块化描述系统 (`eid_modular_descriptions.lua`)

自动生成结构化描述的系统。

```lua
-- 模块行为定义
EID.ModuleBehaviors = {
    ["Damage"] = { Priority = 9880, Arrow = true, Icon = "{{Damage}}" },
    ["Tears"] = { Priority = 9980, Arrow = true, Icon = "{{Tears}}" },
    ["Speed"] = { Priority = 9790, Arrow = true, Icon = "{{Speed}}" },
    -- ...更多模块
}

-- 物品数据 (在 descriptions/*/item_data.lua)
EID.ItemData["5.100.1"] = {  -- Sad Onion
    Tears = 0.7,
    -- 自动生成: "↑ {{Tears}} +0.7 Tears"
}
```

### 5. RNG 预测系统 (`eid_itemprediction.lua`)

通过逆向工程游戏RNG算法实现预测。

```lua
-- RNG 推进函数 (基于 xorshift 算法)
function EID:RNGNext(rngNum, shift1, shift2, shift3)
    rngNum = rngNum ~ ((rngNum >> shift1) & 4294967295)
    rngNum = rngNum ~ ((rngNum << shift2) & 4294967295)
    rngNum = rngNum ~ ((rngNum >> shift3) & 4294967295)
    return rngNum >> 0
end

-- 预测函数示例
function EID:MetronomePrediction(rng)     -- 节拍器预测
function EID:Teleport1Prediction(rng)     -- 传送1目标预测
function EID:Teleport2Prediction()        -- 传送2目标预测
```

### 6. Bag of Crafting 系统 (`eid_bagofcrafting.lua`)

实现 Tainted Cain 合成袋配方计算。

```lua
-- 配方计算核心
function EID:simulateBagOfCrafting(componentsTable)
    -- 基于拾取物权重和品质计算可能的配方结果
end

-- 配方搜索
function EID:BoCSearch(components, targetItems)
    -- 根据当前材料搜索可合成物品
end
```

#### 数据来源 (`eid_xmldata.lua`)

```lua
EID.XMLMaxItemID = 732
EID.XMLRecipes = {["29,29,29,29,29,29,29,29"] = 36, ...}  -- 固定配方
EID.XMLItemPools = {...}  -- 物品池数据
```

### 7. 物品提醒系统 (`eid_holdmapdesc.lua`)

按住地图键显示已拥有物品信息。

```lua
-- 分类系统
EID.ItemReminderCategories = {
    { id = "Overview", ... },
    { id = "Character", ... },
    { id = "Actives", ... },
    { id = "Pockets", ... },
    { id = "Trinkets", isScrollable = true, ... },
    { id = "Passives", isScrollable = true, ... },
}
```

### 8. Grid 实体描述 (`eid_grid_descriptions.lua`)

为网格实体（如献祭尖刺、Sanguine Bond尖刺）提供描述。

```lua
-- 添加网格实体描述
EID:addGridEntity(type, variant, name, description, language)

-- 添加条件性网格描述
EID:addGridEntityConditional(type, conditionalFunction, callbackFunction)
```

---

## 关键技术实现

### 1. 房间内拾取物检测与识别 (重点)

EID 检测房间内的道具、卡牌、药丸的核心流程如下：

#### 1.1 实体搜索机制

```lua
-- 在 MC_POST_RENDER 回调中执行
function EID:OnRender()
    for playerNum, player in ipairs(playerSearch) do
        local sourcePos = player.Position
        local searchGroups = {}
        
        -- 方法1: 使用 Isaac.FindInRadius 搜索玩家周围的实体
        -- searchPartitions 默认为 EntityPartition.PICKUP (拾取物分区)
        table.insert(searchGroups, Isaac.FindInRadius(
            sourcePos,                              -- 搜索中心点
            tonumber(EID.Config["MaxDistance"])*40, -- 搜索半径 (格子数 * 40)
            searchPartitions                        -- 实体分区类型
        ))
        
        -- 方法2: 对于特殊效果实体，使用 FindByType 全房间搜索
        for k,_ in pairs(EID.effectList) do
            table.insert(searchGroups, Isaac.FindByType(
                EntityType.ENTITY_EFFECT, 
                tonumber(k), -1, true, false
            ))
        end
        
        -- 遍历所有搜索结果
        for _, entitySearch in ipairs(searchGroups) do
            for _, entity in ipairs(entitySearch) do
                if EID:hasDescription(entity) then
                    -- 找到最近的可描述实体
                    local diff = entity.Position:__sub(sourcePos)
                    if diff:Length() < EID.lastDist then
                        EID.lastDescriptionEntity = entity
                        EID.lastDist = diff:Length()
                    end
                end
            end
        end
    end
end
```

#### 1.2 实体类型识别与ID获取

所有拾取物的 Type 都是 `5` (EntityType.ENTITY_PICKUP)，通过 Variant 区分类型：

```lua
-- 实体属性结构 (Entity / EntityPickup)
entity.Type      -- 实体类型 (拾取物=5, Slot机器=6, 效果=1000)
entity.Variant   -- 变体类型 (见下表)
entity.SubType   -- 子类型 = 物品ID / 卡牌ID / 药丸颜色
entity.InitSeed  -- 初始种子 (用于唯一标识)
entity.DropSeed  -- 掉落种子

-- PickupVariant 枚举 (常用值)
PickupVariant.PICKUP_COLLECTIBLE = 100  -- 收藏品/道具
PickupVariant.PICKUP_TRINKET     = 350  -- 饰品
PickupVariant.PICKUP_TAROTCARD   = 300  -- 卡牌/符文
PickupVariant.PICKUP_PILL        = 70   -- 药丸
```

#### 1.3 分类处理逻辑 (main.lua 第1575-1670行)

```lua
-- 处理收藏品 (道具底座)
if closest.Variant == PickupVariant.PICKUP_COLLECTIBLE then
    -- closest.SubType = 道具ID (CollectibleType)
    if EID:IsItemHidden(closest) then
        EID:addQuestionMarkDescription(closest)  -- 隐藏状态
    else
        local descriptionObj = EID:getDescriptionObjByEntity(closest)
        -- descriptionObj.ObjSubType = 道具ID
        -- descriptionObj.Name = 道具名称
        -- descriptionObj.Description = 道具描述
        EID:addDescriptionToPrint(descriptionObj)
    end

-- 处理饰品
elseif closest.Variant == PickupVariant.PICKUP_TRINKET then
    -- closest.SubType = 饰品ID (TrinketType)
    -- 金色饰品: SubType > TrinketType.TRINKET_GOLDEN_FLAG (32768)
    local descriptionObj = EID:getDescriptionObjByEntity(closest)
    EID:addDescriptionToPrint(descriptionObj)

-- 处理卡牌/符文
elseif closest.Variant == PickupVariant.PICKUP_TAROTCARD then
    -- closest.SubType = 卡牌ID (Card)
    local descriptionObj = EID:getDescriptionObjByEntity(closest)
    EID:addDescriptionToPrint(descriptionObj)

-- 处理药丸
elseif closest.Variant == PickupVariant.PICKUP_PILL then
    -- closest.SubType = 药丸颜色 (PillColor)
    local pillColor = closest.SubType
    local pool = game:GetItemPool()
    
    -- 检查药丸是否已识别
    local identified = pool:IsPillIdentified(pillColor)
    
    -- 获取药丸效果ID
    local pillEffectID = pool:GetPillEffect(pillColor, EID.player)
    -- pillEffectID = PillEffect 枚举值
    
    if identified or EID.Config["ShowUnidentifiedPillDescriptions"] then
        local descEntry = EID:getDescriptionObj(closest.Type, closest.Variant, pillColor, closest)
        EID:addDescriptionToPrint(descEntry)
    end
end
```

#### 1.4 特殊情况处理

**Crane Game 机器内的道具：**
```lua
elseif closest.Type == 6 and closest.Variant == 16 then  -- Slot 机器, Crane Game变体
    -- 普通方式无法直接获取奖品ID，需要追踪
    local collectibleID = EID.CraneItemType[closest.InitSeed.."Drop"..closest.DropSeed] 
                       or EID.CraneItemType[tostring(closest.InitSeed)]
    
    -- REPENTOGON 可直接获取
    if REPENTOGON then
        collectibleID = closest:ToSlot():GetPrizeCollectible()
    end
end
```

**TMTRAINER 损坏道具：**
```lua
-- 损坏道具的ID > 4294960000
elseif closest.Type == 5 and closest.Variant == 100 and closest.SubType > 4294960000 then
    -- 通过 ItemConfig 读取随机生成的效果
    local glitchedName = EID.itemConfig:GetCollectible(closest.SubType).Name
end
```

#### 1.5 通过描述对象获取详细信息

```lua
function EID:getDescriptionObjByEntity(entity)
    local Type = entity.Type
    local Variant = entity.Variant
    local SubType = entity.SubType
    
    -- 对药丸进行特殊处理：获取实际效果ID
    SubType = EID:getAdjustedSubtype(Type, Variant, SubType)
    
    return EID:getDescriptionObj(Type, Variant, SubType, entity)
end

-- 药丸颜色 -> 药丸效果ID 转换
function EID:getAdjustedSubtype(Type, Variant, SubType)
    if Type == 5 and Variant == 70 then  -- 药丸
        local pool = game:GetItemPool()
        -- GetPillEffect 将药丸颜色转换为效果ID
        return pool:GetPillEffect(SubType, EID.pillPlayer or EID.player)
    end
    return SubType
end
```

---

### 2. 玩家已有道具列表获取 (重点)

EID 通过多种方式追踪和获取玩家持有的道具信息：

#### 2.1 核心数据结构

```lua
-- 玩家最近获得的被动道具列表 (按获取顺序)
EID.RecentlyTouchedItems = {
    [playerID] = { itemID1, itemID2, ... }
}

-- 玩家吞噬的饰品列表
EID.GulpedTrinkets = {
    [playerID] = { trinketID1, trinketID2, ... }
}

-- 玩家的 Lemegeton 精灵列表
EID.WispsPerPlayer = {
    [playerID] = { wispItemID1, wispItemID2, ... }
}

-- 玩家物品交互记录 (用于变身追踪)
EID.PlayerItemInteractions = {
    [playerID] = {
        actives = { [itemIDStr] = count, ... },
        rerollItems = { [itemIDStr] = count, ... }
    }
}
```

#### 2.2 获取所有被动道具ID列表

```lua
local passiveItems = nil  -- 缓存

function EID:GetAllPassiveItems()
    if passiveItems then return passiveItems end
    passiveItems = {}
    
    -- 遍历所有收藏品ID
    for i = 1, EID:GetMaxCollectibleID() do
        local config = EID.itemConfig:GetCollectible(i)
        -- 检查是否为被动道具或宠物
        if config ~= nil and 
           (config.Type == ItemType.ITEM_PASSIVE or 
            config.Type == ItemType.ITEM_FAMILIAR) then
            table.insert(passiveItems, i)
        end
    end
    return passiveItems
end
```

#### 2.3 检测玩家是否拥有特定道具

```lua
-- 使用游戏原生 API
player:HasCollectible(collectibleID)     -- 是否拥有收藏品
player:GetCollectibleNum(collectibleID)  -- 拥有数量
player:HasTrinket(trinketID)             -- 是否拥有饰品
player:GetTrinket(slot)                  -- 获取指定槽位饰品 (0-1)

-- EID 封装函数
function EID:PlayerHasItem(player, itemIDStr)
    local Type, Var, Sub = EID:SplitTVS(itemIDStr)
    if Var == 100 then 
        return player:HasCollectible(Sub)
    elseif Var == 350 then 
        return player:HasTrinket(Sub)
    end
end

-- 检查任意玩家是否拥有
function EID:PlayersHaveCollectible(collectibleID)
    for _, player in ipairs(EID.coopAllPlayers) do
        if player:HasCollectible(collectibleID) then
            return true
        end
    end
    return false
end
```

#### 2.4 更新玩家持有道具列表

```lua
function EID:UpdateAllPlayerPassiveItems()
    local passives = EID:GetAllPassiveItems()
    local maxCollID = EID:GetMaxCollectibleID()
    
    for i = 1, #EID.coopAllPlayers do
        local player = EID.coopAllPlayers[i]
        local playerNum = EID:getPlayerID(player, true)
        
        -- 1. 移除玩家不再持有的道具 (反向遍历便于删除)
        for index = #EID.RecentlyTouchedItems[playerNum], 1, -1 do
            local itemID = EID.RecentlyTouchedItems[playerNum][index]
            if itemID > maxCollID or not player:HasCollectible(itemID, true) then
                table.remove(EID.RecentlyTouchedItems[playerNum], index)
            end
        end
        
        -- 2. 添加新获得的道具
        for _, itemID in ipairs(passives) do
            if player:HasCollectible(itemID, true) then
                -- 检查是否已在列表中
                local alreadyInList = false
                for _, heldItemID in ipairs(EID.RecentlyTouchedItems[playerNum]) do
                    if itemID == heldItemID then
                        alreadyInList = true
                        break
                    end
                end
                if not alreadyInList then
                    table.insert(EID.RecentlyTouchedItems[playerNum], itemID)
                end
            end
        end
    end
end
```

#### 2.5 获取主动道具

```lua
-- 主动道具槽位
-- Slot 0: 主主动道具槽
-- Slot 1: 副主动道具槽 (Schoolbag)
-- Slot 2: 口袋主动道具槽
-- Slot 3: 骰子袋临时道具槽

function EID:ItemReminderHandleActiveItems(player)
    for i = 0, 1 do  -- 只处理槽位 0 和 1
        -- 获取主动道具ID，处理损坏道具的负ID
        local heldActive = player:GetActiveItem(i) % GLITCH_ITEM_FLAG
        if heldActive > 0 then
            EID:ItemReminderAddDescription(player, 5, 100, heldActive)
        end
    end
end

-- 口袋主动道具
function EID:ItemReminderHandlePocketActive(player)
    local pocketActive = player:GetActiveItem(2) or 0
    if pocketActive > 0 then
        EID:ItemReminderAddDescription(player, 5, 100, pocketActive)
    end
end
```

#### 2.6 获取口袋物品 (卡牌/药丸)

```lua
function EID:ItemReminderHandlePocketItems(player)
    for i = 0, 2 do  -- 最多3个口袋槽位
        local heldCard = player:GetCard(i)   -- 获取卡牌ID
        local heldPill = player:GetPill(i)   -- 获取药丸颜色
        
        if heldCard > 0 then
            EID:ItemReminderAddDescription(player, 5, 300, heldCard)
        elseif heldPill > 0 then
            -- 检查药丸是否已识别
            local identified = game:GetItemPool():IsPillIdentified(heldPill)
            -- 金色药丸始终识别
            if EID.isRepentance and 
               heldPill % PillColor.PILL_GIANT_FLAG == PillColor.PILL_GOLD then 
                identified = true 
            end
            
            if identified or EID.Config["ShowUnidentifiedPillDescriptions"] then
                EID.pillPlayer = player  -- 设置当前药丸玩家 (用于效果查询)
                EID:ItemReminderAddDescription(player, 5, 70, heldPill)
                EID.pillPlayer = nil
            end
        end
    end
end
```

#### 2.7 获取饰品 (包括吞噬的)

```lua
function EID:ItemReminderHeldPlusGulped(player)
    local playerNum = EID:getPlayerID(player, true)
    local newTable = {}
    
    -- 添加已吞噬的饰品
    if EID.GulpedTrinkets[playerNum] then 
        newTable = {table.unpack(EID.GulpedTrinkets[playerNum])} 
    end
    
    -- 添加当前持有的饰品
    for i = 0, 1 do
        local trinket = player:GetTrinket(i)
        if trinket > 0 then 
            table.insert(newTable, trinket) 
        end
    end
    
    return newTable
end

-- REPENTOGON 可直接获取已吞噬饰品
if REPENTOGON then
    function EID:ItemReminderHeldPlusGulped(player)
        local newTable = {}
        -- 直接读取所有已吞噬饰品
        for id, dataTable in pairs(player:GetSmeltedTrinkets()) do
            for j = 1, (dataTable.goldenCount + dataTable.normalCount) do
                table.insert(newTable, id)
            end
        end
        -- 添加手持饰品
        for i = 0, 1 do
            local trinket = player:GetTrinket(i)
            if trinket > 0 then table.insert(newTable, trinket) end
        end
        return newTable
    end
end
```

#### 2.8 追踪道具获取事件

```lua
-- 在 MC_POST_PEFFECT_UPDATE 回调中检测道具获取
function EID:CheckPlayersCollectibles()
    for _, player in ipairs(EID.coopAllPlayers) do
        local playerID = EID:getPlayerID(player, true)
        
        -- 检查是否有道具在排队等待被拾取
        if player.QueuedItem.Item ~= nil then
            local config = player.QueuedItem.Item
            if config.Type == ItemType.ITEM_PASSIVE or 
               config.Type == ItemType.ITEM_FAMILIAR then
                -- 添加到最近获得的道具列表
                table.insert(EID.RecentlyTouchedItems[playerID], config.ID)
            end
        end
    end
end
```

#### 2.9 获取 ItemConfig 详细信息

```lua
-- 通过 Isaac.GetItemConfig() 获取道具配置
local itemConfig = Isaac.GetItemConfig()
local config = itemConfig:GetCollectible(itemID)

-- ItemConfigItem 属性
config.ID           -- 道具ID
config.Name         -- 道具名称
config.Description  -- 官方描述
config.Type         -- 道具类型 (ItemType枚举)
config.Quality      -- 品质 (0-4)
config.Tags         -- 标签 (用于变身判断)
config.ChargeType   -- 充能类型
config.MaxCharges   -- 最大充能数
config.CacheFlags   -- 缓存标志 (影响的属性)

-- 道具类型枚举
ItemType.ITEM_PASSIVE  = 1   -- 被动道具
ItemType.ITEM_ACTIVE   = 3   -- 主动道具
ItemType.ITEM_FAMILIAR = 4   -- 宠物
ItemType.ITEM_TRINKET  = 2   -- 饰品
```

---

### 3. 条件描述系统 (eid_conditionals.lua)

#### 条件系统概述

条件描述系统动态根据玩家持有的物品、角色、游戏模式等因素修改描述。

#### 3.1 数据结构

```lua
-- 条件存储表
EID.DescriptionConditions = {
    {
        Items = {"5.100", ...},        -- 目标物品ID列表
        Condition = function(),        -- 条件函数或物品ID
        TextKey = "descriptionKey",    -- 本地化文本键
        Options = {                    -- 选项
            locTable = "tableName",    -- 本地化表名
            replaceColor = "ColorName",-- 颜色替换
            noFallback = false,        -- 是否禁用回退
            uniqueID = "identifier",   -- 唯一ID
            layer = 1,                 -- 优先级层级
            useResult = true           -- 是否使用结果
        }
    }
}

-- 需要定期检查的道具列表
EID.collectiblesToCheck = {
    [CollectibleType.COLLECTIBLE_VOID] = true,
    ["5.300.41"] = true,  -- 黑符文
    [356] = true          -- 车电池
}

-- 跟踪协同玩家
EID.DifferentEffectPlayers = {}
```

#### 3.2 添加条件的方法

```lua
-- 物品条件：当玩家拥有 requiredItem 时应用
EID:AddItemConditional(targetItems, requiredItem, textKey, options)
-- 示例: Tarot Cloth 增强卡牌
EID:AddItemConditional("5.300", 451, nil, {
    locTable = "tarotClothBuffs",
    replaceColor = "ColorShinyPurple"
})

-- 玩家条件：特定角色时修改描述
EID:AddPlayerConditional(targetItems, playerType, textKey, options, appendText)

-- 协同条件：两件物品的交互效果
EID:AddSynergyConditional(itemA, itemB, textKeyA, textKeyB, options)

-- 泛用条件：基于任意函数的条件
EID:AddConditional(targetItems, conditionFunction, textKey, options)

-- 贪婪模式条件：游戏模式检测
EID:AddConditional(itemID, EID.IsGreedMode, "No Effect (Greed)")
```

#### 3.3 条件检查实现

```lua
-- 玩家是否拥有物品的检查
function EID:CheckForCarBattery()
    -- 检查玩家是否拥有车电池并返回相应结果
    for _, player in ipairs(EID.coopAllPlayers) do
        if player:HasCollectible(356) then return true end
    end
    return false
end

-- 贪婪模式检测
function EID:IsGreedMode()
    return game:IsGreedMode()
end

-- 角色特定检查
function EID:CheckForBFFS()
    -- 检查是否为特定熟悉家角色
    local closestPlayer = EID.player
    return closestPlayer and closestPlayer:GetPlayerType() == 13  -- Lilith
end
```

---

### 4. RNG 预测系统 (eid_itemprediction.lua)

#### 4.1 Xorshift RNG 实现

```lua
-- XOR 变换表 (来自 Xorshift 论文)
local xortable = {
[0]={ 1, 3,10},{ 1, 5,16},{ 1, 5,19},
     -- ... 更多变换参数
}

-- RNG 推进函数
function EID:RNGNext(rngNum, shift1, shift2, shift3)
    -- 支持两种调用方式:
    -- 1. 直接传入位移值: RNGNext(seed, 5, 9, 7)
    -- 2. 使用 xortable 索引: RNGNext(seed, 35)
    
    if shift1 and not shift2 then
        shift3 = xortable[shift1][3]
        shift2 = xortable[shift1][2]
        shift1 = xortable[shift1][1]
    end
    
    rngNum = rngNum ~ ((rngNum >> (shift1 or 5)) & 4294967295)
    rngNum = rngNum ~ ((rngNum << (shift2 or 9)) & 4294967295)
    rngNum = rngNum ~ ((rngNum >> (shift3 or 7)) & 4294967295)
    return rngNum >> 0
end

-- 种子转浮点数 [0, 1)
function EID:SeedToFloat(seed)
    local multi = 2.3283061589829401E-10  -- 2^-32 的近似值
    return seed * multi
end
```

#### 4.2 预测物品效果

**D Infinity 预测：**
```lua
-- D Infinity 允许的骰子列表
local dinfinityList = { [0] = 105, 166, 284, ... }  -- AB+
-- Repentance: { [0] = 476, 284, 105, 609, ... }

function EID:CurrentDInfinity(rng, player)
    if not EID.isRepentance then
        rng = EID:RNGNext(rng, 0x1, 0x9, 0x1D)
        return dinfinityList[rng % 7]
    else
        local playerID = EID:getPlayerID(player, true)
        return dinfinityList[EID.DInfinityState[playerID]] or 476
    end
end
```

**Metronome 预测：**
```lua
-- 被禁止的物品及其重新掷骰子概率
local metronomeBlacklist = {
    [488] = 1,      -- Metronome (总是重新掷)
    [475] = 1,      -- Plan C
    [628] = 0.85,   -- Death Certificate (85% 重新掷)
    [622] = 0.75    -- Genesis (75% 重新掷)
}

function EID:MetronomePrediction(rng)
    local numCollectibles = EID:GetMaxCollectibleID()
    local rerollChance = 0
    if EID.isRepentance then
        rng = EID:RNGNext(rng)
        rerollChance = rng
    end
    
    local attempts = 15  -- 最多尝试15次
    while attempts > 0 do
        attempts = attempts - 1
        rng = EID:RNGNext(rng)
        local sel = rng % numCollectibles + 1
        
        if EID.itemConfig:GetCollectible(sel) ~= nil then
            if metronomeBlacklist[sel] then
                -- 检查重新掷骰子概率
                if metronomeBlacklist[sel] < 1 then
                    rerollChance = EID:RNGNext(rerollChance, 0x02, 0x0F, 0x11)
                    local rerollFloat = EID:SeedToFloat(rerollChance)
                    if rerollFloat < 1 - metronomeBlacklist[sel] then
                        return sel
                    end
                end
            else
                return sel
            end
        end
    end
    return 488  -- 失败时默认返回 Metronome
end
```

**Sanguine Bond 预测：**
```lua
-- 结果分布: 15% 硬币, 48% 伤害, 58% 红心, 63% 道具, 65% 利维坦, 100% 无
local sanguineResults = { 
    { 0.15, 3 }, { 0.48, 2 }, { 0.58, 4 }, 
    { 0.63, 5 }, { 0.65, 6 }, { 1, 1 }
}

function EID:trimSanguineDesc(spikes, descObj)
    if not spikes then return "" end
    
    local cheatResult = nil
    if spikes and EID.Config["PredictionSanguineBond"] then
        local spikeSeed = spikes:GetRNG():GetSeed()
        spikeSeed = EID:RNGNext(spikeSeed, 5, 9, 7)
        spikeSeed = EID:RNGNext(spikeSeed, 0x01, 0x05, 0x13)
        local nextFloat = EID:SeedToFloat(spikeSeed)
        
        -- 查找结果
        for _, v in ipairs(sanguineResults) do
            if nextFloat < v[1] then 
                cheatResult = v[2] 
                break 
            end
        end
    end
    
    -- 生成描述，高亮下一个结果
    local resultsDesc = ""
    local lineCount = 0
    for w in string.gmatch(descObj.Description, "([^#;]+)") do
        if string.find(w, "%%") then
            lineCount = lineCount + 1
            if cheatResult == lineCount then 
                resultsDesc = resultsDesc .. "{{ColorBagComplete}}" 
            end
            resultsDesc = resultsDesc .. w .. "#"
        end
    end
    return resultsDesc
end
```

**Teleport 目标预测：**
```lua
function EID:Teleport1Prediction(rng)
    local level = game:GetLevel()
    local currentRoomIndex = level:GetCurrentRoomDesc().SafeGridIndex
    local possibleRooms = {}
    
    -- 遍历所有房间获取可能的目标
    for i = 0, level:GetRoomCount() - 1 do
        local roomDesc = level:GetRoomByIdx(i)
        -- 检查房间类型、是否可到达等条件
        if roomDesc and roomDesc.SafeGridIndex ~= currentRoomIndex then
            table.insert(possibleRooms, {
                Index = roomDesc.SafeGridIndex,
                Type = roomDesc.Data.Type
            })
        end
    end
    
    -- 根据 RNG 计算目标房间
    rng = EID:RNGNext(rng)
    local selectedRoom = possibleRooms[rng % #possibleRooms + 1]
    
    return selectedRoom
end
```

---

### 5. Bag of Crafting 系统 (eid_bagofcrafting.lua)

#### 5.1 配方数据获取

```lua
-- 固定配方 (来自 XML 数据)
EID.XMLRecipes = {
    ["29,29,29,29,29,29,29,29"] = 36,   -- 8个蓝苍蝇 -> Eye of Belial
    ["8,8,8,8,8,8,8,8"] = 177,          -- 8个钥匙 -> Oh! Canada
    -- ... 更多配方
}

-- 物品池数据 (ID -> {itemID, weight})
EID.XMLItemPools = {
    [1] = {{1, 1.0}, {2, 1.0}, ...},    -- Treasure Room 池
    [2] = {{21, 1.0}, {33, 1.0}, ...},  -- Shop 池
    -- ... 其他池
}

-- 拾取物与配方材料的映射
EID.BoC.PickupIDLookup = {
    ["100.1"] = {1},   -- Red Heart -> Penny
    ["100.2"] = {2},   -- Blue Heart -> Bomb
    -- ... 更多映射
}

-- 配方材料的权重值
EID.BoC.PickupValues = {
    [1] = 1,    -- Penny 权重
    [2] = 1,    -- Bomb 权重
    -- ...
}
```

#### 5.2 配方模拟

```lua
function EID:simulateBagOfCrafting(componentsTable)
    local components = componentsTable
    local compTotalWeight = 0
    local compCounts = {}
    
    -- 1. 统计各材料数量和总权重
    for i = 1, #EID.BoC.ComponentShifts do
        compCounts[i] = 0
    end
    for _, compId in ipairs(components) do
        if (_ > 8) then break end
        compCounts[compId + 1] = compCounts[compId + 1] + 1
        compTotalWeight = compTotalWeight + EID.BoC.PickupValues[compId + 1]
    end
    
    -- 2. 计算物品池权重
    local poolWeights = {
        {idx = 0, weight = 1, totalWeight = 0},           -- 默认宝藏池
        {idx = 1, weight = 2, totalWeight = 0},           -- 商店池
        {idx = 3, weight = compCounts[4] * 10, ...},      -- Devil Pool
        {idx = 4, weight = compCounts[5] * 10, ...},      -- Angel Pool
        -- ... 更多池
    }
    
    -- 3. 计算品质权重
    local qualityWeights = {[0] = 0, 0, 0, 0, 0}
    
    -- 返回可能的配方结果及其概率
    return {
        Results = {
            {ItemID = 36, Quality = 3, Probability = 0.05},
            {ItemID = 45, Quality = 2, Probability = 0.15},
            -- ...
        }
    }
end
```

---

### 6. 模块化描述系统 (eid_modular_descriptions.lua)

#### 6.1 模块行为定义

```lua
-- 模块行为表，定义每个统计模块的显示方式
EID.ModuleBehaviors = {
    -- 玩家属性模块
    ["Tears"] = {
        Priority = 9980,          -- 显示优先级 (越高越先显示)
        Arrow = true,             -- 显示上/下箭头
        Icon = "{{Tears}}",       -- 图标
        IsMultiplier = false      -- 是否为倍数 (x vs +)
    },
    ["Damage"] = {
        Priority = 9880,
        Arrow = true,
        Icon = "{{Damage}}"
    },
    ["TearsMultiplier"] = {
        Priority = 9990,
        Arrow = true,
        Icon = "{{Tears}}",
        IsMultiplier = true      -- 使用 x 而不是 +/-
    },
    ["Speed"] = {
        Priority = 9790,
        Arrow = true,
        Icon = "{{Speed}}"
    },
    -- 生命值相关
    ["RedHeart"] = {
        Priority = 8990,
        Arrow = true,
        Icon = "{{Heart}}"
    },
    ["SoulHeart"] = {
        Priority = 8960,
        Icon = "{{SoulHeart}}"
    },
    -- 掉落物相关
    ["Spawns"] = {
        Priority = 5500,
        HideSign = true,
        Icon = {
            RandomHeart = "{{UnknownHeart}}",
            RedHeart = "{{Heart}}",
            SoulHeart = "{{SoulHeart}}",
            -- ... 各种掉落物的图标
        }
    }
}

-- 物品数据定义 (在 descriptions/*/item_data.lua)
EID.ItemData = {
    ["5.100.1"] = {              -- Sad Onion
        Tears = 0.7              -- +0.7 眼泪
    },
    ["5.100.2"] = {              -- Spoon Bender
        TearsMultiplier = 1.35   -- x1.35 眼泪倍数
    }
}
```

#### 6.2 生成过程

```lua
function EID:GenerateModularDescription(itemID)
    local itemData = EID.ItemData["5.100."..itemID]
    if not itemData then return "" end
    
    local description = ""
    local modules = {}
    
    -- 1. 收集所有非零的模块
    for moduleName, value in pairs(itemData) do
        if value ~= 0 and value ~= false then
            table.insert(modules, {
                Name = moduleName,
                Value = value,
                Behavior = EID.ModuleBehaviors[moduleName]
            })
        end
    end
    
    -- 2. 按优先级排序
    table.sort(modules, function(a, b)
        return (a.Behavior.Priority or 0) > (b.Behavior.Priority or 0)
    end)
    
    -- 3. 生成每个模块的描述
    for _, module in ipairs(modules) do
        local behavior = module.Behavior
        local text = ""
        
        -- 显示箭头
        if behavior.Arrow then
            if (module.Value > 0 and not behavior.InvertArrow) or
               (module.Value < 0 and behavior.InvertArrow) then
                text = "↑ "
            else
                text = "↓ "
            end
        end
        
        -- 显示图标
        if behavior.Icon then
            text = text .. behavior.Icon .. " "
        end
        
        -- 显示值
        if not behavior.HideSign then
            if module.Value > 0 then text = text .. "+" end
        end
        
        if behavior.IsMultiplier then
            text = text .. string.format("x%.2g", module.Value)
        else
            text = text .. string.format("%.4g", module.Value)
        end
        
        description = description .. text .. "#"
    end
    
    return description
end
```

---

### 7. 描述修改器系统 (eid_modifiers.lua)

#### 7.1 修改器注册

```lua
-- 修改器表
EID.DescModifiers = {
    {
        Name = "Void Callback",
        condition = function(descObj) 
            return descObj.ObjSubType == 477  -- Void
        end,
        callback = function(descObj)
            return VoidCallback(descObj, false)
        end,
        Layer = 1
    }
}

-- 需要检查的物品列表
EID.collectiblesToCheck = {
    [CollectibleType.COLLECTIBLE_VOID] = true,
    [CollectibleType.COLLECTIBLE_BOOK_OF_VIRTUES] = true,
    [CollectibleType.COLLECTIBLE_SPINDOWN_DICE] = true
}
```

#### 7.2 Void 效果计算

```lua
function EID:VoidRoomCheck()
    -- 找到所有房间内的被动道具
    EID.VoidStatIncreases = {{}, {}, {}}
    
    for _, entity in ipairs(Isaac.FindByType(5, 100, -1, true, false)) do
        local itemID = entity.SubType
        local itemConfig = EID.itemConfig:GetCollectible(itemID)
        
        -- 检查这个道具是否会被 Void 吸收
        if itemConfig and 
           (itemConfig.Type == ItemType.ITEM_PASSIVE or
            itemConfig.Type == ItemType.ITEM_FAMILIAR) then
            -- 添加到统计列表
        end
    end
end

function EID:VoidRNGCheck(player, isRune)
    -- 根据房间内的道具和 RNG 计算 Void 的属性增益
    local voidStatUps = { 0.2, 0.5, 1, 0.5, 0.2, 1 }
    local statIncreases = {}
    
    -- 根据被动道具计算属性增益
    for i = 1, 6 do  -- 6个属性
        statIncreases[i] = 0
    end
    
    -- 示例: 每个红心增加 0.2 伤害
    for heartCount = 1, collectedHearts do
        statIncreases[3] = statIncreases[3] + 0.2  -- 伤害
    end
    
    return statIncreases
end
```

---

### 8. XML 数据系统 (eid_xmldata.lua)

#### 8.1 数据结构

```lua
-- 游戏中最大的物品ID
EID.XMLMaxItemID = 732

-- 固定配方表
EID.XMLRecipes = {
    ["29,29,29,29,29,29,29,29"] = 36,   -- 8个蓝苍蝇 -> Eye of Belial
    ["8,8,8,8,8,8,8,8"] = 177,
    -- ... 更多固定配方
}

-- 各物品池的内容和权重
EID.XMLItemPools = {
    -- 索引对应 ItemPoolType
    [1] = {{itemID, weight}, ...},      -- Treasure Room
    [2] = {{itemID, weight}, ...},      -- Shop
    [3] = {{itemID, weight}, ...},      -- Boss
    -- ... 更多池
}

-- 药丸的元数据 (来自 pocketitems.xml)
EID.pillMetadata = {
    [0] = {class = "1+"},   -- 药丸等级分类
    [1] = {class = "2-"},
    -- ...
}

-- Abyss 精灵的效果数据
EID.XMLLocusts = {
    [2] = {3, 1, 1, {-1}, ...},     -- 飞行精灵
    [3] = {1, 1, 1, {-1}, ...},
    -- ... 更多精灵数据
}
```

#### 8.2 访问方式

```lua
-- 获取物品池
local treasurePool = EID.XMLItemPools[ItemPoolType.TREASURE_ROOM]
for _, entry in ipairs(treasurePool) do
    local itemID = entry[1]
    local weight = entry[2]
end

-- 查询固定配方
local formula = "29,29,29,29,29,29,29,29"
local result = EID.XMLRecipes[formula]  -- 返回 36 (Eye of Belial)

-- 获取药丸信息
local pillInfo = EID.pillMetadata[pillEffectID]
print(pillInfo.class)  -- "1+"

-- 获取精灵效果
local locustData = EID.XMLLocusts[itemID]
-- locustData[1] = 伤害倍数
-- locustData[2] = 眼泪倍数
-- locustData[3] = 速度倍数
-- ...
```

---

### 9. 渲染循环与实体检测

#### 渲染循环 (`main.lua`)

```lua
function EID:OnRender()
    -- 1. 设置玩家引用
    EID:setPlayer()
    
    -- 2. 处理快捷键
    EID:HandleRenderingKeys()
    
    -- 3. 检测实体并生成描述
    for _, entity in ipairs(describableEntities) do
        if EID:hasDescription(entity) then
            local descObj = EID:getDescriptionObj(...)
            EID:addDescriptionToPrint(descObj)
        end
    end
    
    -- 4. 打印描述
    EID:printDescriptions()
end
```

#### 路径检测 (使用 A* 算法)

```lua
-- 检查玩家到实体的路径是否可达
function EID:HasPathToPosition(playerPos, targetPos)
    -- 使用 features/pathfinder/luafinding.lua 中的 A* 实现
    return EID.Pathfinder:FindPath(playerPos, targetPos) ~= nil
end
```

### 10. 诅咒之盲检测

#### Alt Path 隐藏道具检测

```lua
function EID:IsAltChoice(pickup)
    -- 通过比较道具精灵与问号精灵的像素来判断
    for i = -1, 1, 1 do
        for j = -40, 10, 3 do
            local qcolor = questionMarkSprite:GetTexel(Vector(i,j), ...)
            local ecolor = entitySprite:GetTexel(Vector(i,j), ...)
            if qcolor.Red ~= ecolor.Red or ... then
                return false  -- 像素不同，不是隐藏道具
            end
        end
    end
    return true  -- 像素相同，是隐藏道具
end
```

### 11. Flip 物品追踪

追踪 Tainted Lazarus 的 Flip 道具需要特殊处理：

```lua
-- 使用回调追踪 Flip 物品
EID:AddCallback(ModCallbacks.MC_POST_GET_COLLECTIBLE, EID.postGetCollectible)
EID:AddCallback(ModCallbacks.MC_PRE_ROOM_ENTITY_SPAWN, EID.preRoomEntitySpawn)
EID:AddCallback(ModCallbacks.MC_POST_PICKUP_INIT, EID.postPickupInitFlip)

-- 存储结构
EID.flipItemPositions = {
    [roomIndex] = {
        [initSeed] = {itemID, gridIndex}
    }
}
```

### 12. Crane Game 物品追踪

```lua
function EID:postGetCollectible(selectedCollectible, itemPoolType)
    if itemPoolType == ItemPoolType.POOL_CRANE_GAME then
        for _, crane in ipairs(Isaac.FindByType(6, 16, -1)) do
            if not EID.CraneItemType[tostring(crane.InitSeed)] then
                EID.CraneItemType[tostring(crane.InitSeed)] = selectedCollectible
                break
            end
        end
    end
end
```

### 13. Void 吸收物品追踪

```lua
-- 追踪已吸收的主动道具
EID.absorbedItems = {
    [playerID] = { [itemID] = true, ... }
}

-- 预测 Void 使用后的属性加成
function EID:VoidRNGCheck(player, isBlackRune)
    -- 遍历房间内的被动物品，计算属性加成
end
```

### 14. REPENTOGON 集成 (`eid_repentogon.lua`)

当检测到 REPENTOGON 时，利用其扩展API获取更精确的数据：

```lua
if not REPENTOGON then return end

-- 直接读取成就解锁状态
function EID:requiredForCollectionPage(itemID)
    return not Isaac.GetPersistentGameData():IsItemInCollection(itemID)
end

-- 直接读取合成袋内容
function EID:BoCCheckForPickups()
    EID.BoC.BagItems = {}
    for key, value in pairs(EID.bagPlayer:GetBagOfCraftingContent()) do
        EID.BoC.BagItems[key] = value
    end
end

-- 直接读取已吞噬饰品
function EID:ItemReminderHeldPlusGulped(player)
    for id, dataTable in pairs(player:GetSmeltedTrinkets()) do
        -- ...
    end
end
```

---

## API参考

### 核心描述对象 (`EID_DescObj`)

```lua
---@class EID_DescObj
---@field ObjType integer           -- 实体类型
---@field ObjVariant integer        -- 实体变体
---@field ObjSubType integer        -- 实体子类型
---@field fullItemString string     -- "Type.Variant.SubType" 格式字符串
---@field Name string               -- 显示名称
---@field Description string        -- 描述文本
---@field Transformation string     -- 变身信息
---@field ModName string            -- 来源模组名
---@field Quality integer           -- 品质 (0-4)
---@field Icon EID_Icon             -- 图标信息
---@field Entity Entity?            -- 关联实体
---@field ItemType integer?         -- 物品类型
---@field ChargeType integer?       -- 充能类型
---@field Charges integer?          -- 最大充能
```

### 内联图标定义

```lua
-- 格式: [快捷方式] = {动画名, 帧数, 宽度, 高度, 左偏移, 上偏移, 精灵对象}
EID.InlineIcons = {
    ["Heart"] = {"hearts", 0, 10, 9, 1, 1},
    ["ArrowUp"] = {"ArrowUp", 0, 10, 9, 1},
    ["Damage"] = {"stats", 0, 10, 9, 1, 1},
    -- ...
}

-- 在描述中使用
"{{Heart}} 获得1颗红心"
```

### 标记替换

```lua
EID.TextReplacementPairs = {
    {"↑", "{{ArrowUp}}"},      -- 向上箭头
    {"↓", "{{ArrowDown}}"},    -- 向下箭头
    {"!!!", "{{Warning}}"},    -- 警告图标
    -- ...
}
```

### 常用函数

```lua
-- 追加描述
EID:appendToDescription(descObj, appendString)

-- 获取当前语言
EID:getLanguage()

-- 检查玩家是否拥有物品
EID:PlayersHaveCollectible(collectibleID)

-- 检查诅咒之盲
EID:hasCurseBlind()

-- 获取物品名称
EID:getObjectName(Type, Variant, SubType)

-- 获取变身名称
EID:getTransformationName(id)

-- 渲染字符串
EID:renderString(text, position, scale, color)

-- 分割 "Type.Variant.SubType" 格式字符串
EID:SplitTVS(typeVarSubString)  -- 返回 Type, Variant, SubType

-- 检查两个描述对象是否相同
EID:areDescriptionObjectsEqual(descObj1, descObj2)

-- 获取描述对象的副本
EID:CopyDescriptionObj(descObj)

-- 获取最大收藏品ID
EID:GetMaxCollectibleID()

-- 检查物品是否隐藏 (诅咒之盲/Alt Path)
EID:IsItemHidden(entity)

-- 获取物品种子
EID:GetItemSeed(player, itemID, variant)
-- 返回物品的 RNG 种子，用于预测

-- 获取描述条目 (多语言)
EID:getDescriptionEntry(category, key, isEnglish)

-- 替换描述中的占位符
EID:ReplaceVariableStr(text, placeholder, value)

-- 生成统计表的描述
EID:GenerateDescriptionFromStatTable(statTable)
```

### 条件描述 API

```lua
-- 添加物品条件
EID:AddItemConditional(targetItems, requiredItem, textKey, options)

-- 添加玩家条件
EID:AddPlayerConditional(targetItems, playerType, textKey, options, appendText)

-- 添加协同条件
EID:AddSynergyConditional(itemA, itemB, textKeyA, textKeyB, options)

-- 添加通用条件
EID:AddConditional(targetItems, conditionFunction, textKey, options)

-- 添加描述修改器
EID:addDescriptionModifier(modifierName, conditionFunction, callbackFunction, layer)

-- 检查玩家是否拥有特定物品
EID:PlayersHaveItem(itemIDString)  -- 返回 hasIt, player, playerNum
```

### RNG 和预测 API

```lua
-- RNG 推进
EID:RNGNext(seed, shift1, shift2, shift3)

-- 种子转浮点数
EID:SeedToFloat(seed)

-- D Infinity 预测
EID:CurrentDInfinity(rng, player)

-- Metronome 预测
EID:MetronomePrediction(rng)

-- Teleport 预测
EID:Teleport1Prediction(rng)
EID:Teleport2Prediction()

-- Sanguine Bond 预测
EID:trimSanguineDesc(spikes, descObj)
```

### Bag of Crafting API

```lua
-- 模拟配方
EID:simulateBagOfCrafting(componentsTable)

-- 搜索可合成物品
EID:BoCSearch(components, targetItems)

-- 获取拾取物对应的材料ID
EID:getBagOfCraftingID(Variant, SubType)

-- 检查合成袋内容
EID:BoCCheckForPickups()
```

---

## 数据结构

### 变身数据 (`EID.TransformationData`)

```lua
EID.TransformationData = {
    ["1"] = { Name = "Guppy", NumNeeded = 3 },
    ["2"] = { Name = "Fun Guy", NumNeeded = 3 },
    -- ...
}
```

### 物品池数据 (`EID.XMLItemPools`)

```lua
-- 索引对应 ItemPoolType 枚举
EID.XMLItemPools = {
    [1] = {{itemID, weight}, ...},  -- Treasure Room
    [2] = {{itemID, weight}, ...},  -- Shop
    -- ...
}
```

### HUD 元素位置

```lua
EID.HUDElements = {
    ["Active1"] = {x=20, y=5, width=65, height=65, anchors={"TOP","LEFT"}, ...},
    ["Trinket1"] = {x=50, y=0, width=55, height=65, anchors={"BOTTOM","LEFT"}, ...},
    -- ...
}
```

---

## 扩展与集成

### 为自定义模组添加描述

```lua
-- 在你的模组中
if EID then
    -- 添加收藏品描述
    EID:addCollectible(
        Isaac.GetItemIdByName("My Item"),
        "这是我的自定义道具描述#↑ {{Damage}} +2 伤害",
        "My Item",
        "zh_cn"
    )
    
    -- 注册模组图标
    EID.ModIndicator["My Mod"] = {
        Name = "我的模组",
        Icon = "MyModIcon"  -- 需要先用 EID:addIcon 注册
    }
end
```

### 添加自定义图标

```lua
EID:addIcon(
    "MyIcon",           -- 快捷方式
    "AnimationName",    -- 动画名称
    0,                  -- 帧号
    16,                 -- 宽度
    16,                 -- 高度
    0,                  -- X偏移
    0,                  -- Y偏移
    mySprite            -- Sprite对象
)
```

### 添加描述修改器

```lua
EID:addDescriptionModifier(
    "My Modifier",
    function(descObj)
        -- 条件检查
        return descObj.ObjSubType == MY_ITEM_ID
    end,
    function(descObj)
        -- 修改描述
        EID:appendToDescription(descObj, "#特殊效果说明")
        return descObj
    end
)
```

### 旧版全局变量兼容

为了兼容旧模组，EID仍支持以下全局变量：

```lua
__eidItemDescriptions[itemID] = "描述"
__eidTrinketDescriptions[trinketID] = "描述"
__eidCardDescriptions[cardID] = "描述"
__eidPillDescriptions[pillEffectID] = "描述"
__eidEntityDescriptions["Type.Variant.SubType"] = {"名称", "描述"}
__eidItemTransformations[itemID] = "变身ID"
```

---

## 性能优化技术

### 描述缓存

```lua
EID.CachedIcons = {}
EID.CachedStrings = {}
EID.CachedRenderPoses = {}
EID.previousDescs = {}

-- 只在描述变化时重新计算
function EID:printDescriptions(useCached)
    if not descriptionsChanged then
        -- 使用缓存渲染
    else
        -- 重新计算并缓存
    end
end
```

### 周期性检查

```lua
-- 每15帧检查一次玩家物品
if EID.GameUpdateCount >= EID.LastCollectibleCheck + 15 then
    EID:CheckPlayersCollectibles()
end

-- 每30帧检查一次Void状态
if EID.GameUpdateCount >= lastVoidCheck + 30 then
    EID:VoidRoomCheck()
end
```

### 路径寻找节流

```lua
-- 限制路径检查频率
if pathsChecked[entity.InitSeed] == false and 
   EID.GameUpdateCount - lastPathfindFrame < 15 then
    return false  -- 跳过检查
end
```

---

## 调试

启用调试模式：

```lua
EID.enableDebug = true
```

写入错误消息：

```lua
EID:WriteErrorMsg("错误信息")
```

---

## 文件结构总结

```
external item descriptions_836319872/
├── main.lua                    # 入口点，初始化和渲染循环
├── eid_config.lua              # 用户配置
├── features/
│   ├── eid_api.lua             # 公共API
│   ├── eid_data.lua            # 静态数据（图标、HUD元素等）
│   ├── eid_xmldata.lua         # 从游戏XML提取的数据
│   ├── eid_conditionals.lua    # 条件描述系统
│   ├── eid_modifiers.lua       # 描述修改器
│   ├── eid_modular_descriptions.lua    # 模块化描述生成
│   ├── eid_bagofcrafting.lua   # 合成袋系统
│   ├── eid_itemprediction.lua  # RNG预测
│   ├── eid_holdmapdesc.lua     # 物品提醒
│   ├── eid_grid_descriptions.lua       # 网格实体
│   ├── eid_repentogon.lua      # REPENTOGON扩展
│   └── pathfinder/             # A*路径寻找
├── descriptions/               # 多语言描述文本
│   ├── ab+/                    # Afterbirth+
│   ├── rep/                    # Repentance
│   ├── rep+/                   # Repentance+
│   └── names/                  # 物品名称
└── resources/
    ├── font/                   # 自定义字体
    └── gfx/                    # 图形资源
```

---

*文档版本: 基于 EID v5.15*
