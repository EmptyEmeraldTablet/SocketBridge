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

### 3. 渲染循环与实体检测

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

### 2. 诅咒之盲检测

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

### 3. Flip 物品追踪

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

### 4. Crane Game 物品追踪

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

### 5. Void 吸收物品追踪

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

### 6. REPENTOGON 集成 (`eid_repentogon.lua`)

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
