# EID 信息获取 vs SocketBridge 现有 Sensor 差异分析

> 目标：基于 External Item Descriptions (EID) 已实现的信息获取能力，对比当前 Lua 端已实现的 Sensor，列出尚未覆盖但可用于采集的部分，为后续工具规划提供依据。

## 1. 参考来源

- EID 技术参考（项目内整理）：docs/EID_TECHNICAL_REFERENCE.md
- EID 官方功能概览：external item descriptions/README.md
- SocketBridge Lua 端 Sensor 定义：main.lua

## 2. SocketBridge 现有 Lua Sensor 列表（已实现）

当前 Lua 端已注册的 12 个 Sensor：

- PLAYER_POSITION
- PLAYER_STATS
- PLAYER_HEALTH
- PLAYER_INVENTORY
- ENEMIES
- PROJECTILES
- ROOM_INFO
- ROOM_LAYOUT
- BOMBS
- INTERACTABLES
- PICKUPS
- FIRE_HAZARDS

覆盖范围：玩家状态/属性、房间结构、主要实体（敌人、投射物、拾取物、交互物、炸弹、火焰危险物）。

## 3. EID 能获取的游戏信息范围（按能力归类）

基于 EID 文档与实现总结，EID 可获取/推导的信息主要包括：

1. 物品与实体描述数据
   - 收藏品、饰品、卡牌、药丸的名称/描述
   - ItemConfig 元信息（品质、充能、标签、类型等）
   - Mod 追加的自定义描述与变身

2. 隐藏信息与识别状态
   - 诅咒之盲下的道具识别
   - 未识别药丸效果推断

3. 玩家持有物品与口袋物品追踪
   - 主动道具槽、口袋道具槽、被动道具列表
   - 吞噬饰品（Gulped）与变身追踪

4. 预测系统 / RNG 逆向
   - Spindown Dice
   - Void 吸收
   - Metronome
   - Teleport 目标

5. Bag of Crafting 合成预测
   - 配方计算与候选结果

6. 条件描述与协同信息
   - 基于玩家物品/角色/模式的描述变化
   - 物品协同提示

7. Grid 实体补充描述
   - 特定网格实体（如献祭尖刺、Sanguine Bond 等）的详细说明

## 4. 差异对照与可新增采集点

下表列出 EID 已具备但 SocketBridge 目前未覆盖的“可采集信息”。这些信息可用于开发新工具或增强现有工具。

| 类别 | EID 能力 | 当前 Sensor 覆盖 | 可新增采集点（建议） | 典型用途 |
|------|----------|------------------|----------------------|----------|
| 物品元信息 | ItemConfig（名称、品质、充能、类型、标签） | 无（仅 ID/位置） | ITEM_CONFIG / ITEM_METADATA | 物品分析、UI 展示、自动化决策 |
| 道具描述 | EID 描述文本与自定义描述 | 无 | ITEM_DESCRIPTIONS / ENTITY_DESCRIPTIONS | 解释器、说明工具、QA 系统 |
| 识别状态 | 未识别药丸、诅咒之盲 | 无 | PILL_ID_STATE / BLIND_ITEM_STATE | 预测与风险提示 |
| 口袋物品 | 卡牌/药丸/口袋主动 | PLAYER_INVENTORY 仅数值 | POCKET_ITEMS / POCKET_ACTIVES | 战术分析、提示工具 |
| 被动道具清单 | 被动道具列表与变化 | PLAYER_INVENTORY 有 collectibles 计数 | PLAYER_PASSIVES / RECENT_ITEMS | 变身追踪、build 分析 |
| 吞噬饰品 | Gulped Trinkets | 无 | PLAYER_GULPED_TRINKETS | build 分析、显示器 |
| 变身进度 | 变身追踪与计数 | 无 | TRANSFORMATION_PROGRESS | 规划/统计工具 |
| RNG 预测 | Spindown/Void/Teleport 等 | 无 | RNG_PREDICTIONS | 预测工具/教学工具 |
| Bag of Crafting | 合成袋配方预测 | 无 | BAG_OF_CRAFTING | 规划工具/推荐系统 |
| 条件协同 | 条件描述/协同判断 | 无 | SYNERGY_HINTS | Build 指导、自动策略 |
| Grid 实体说明 | 网格实体描述 | ROOM_LAYOUT 有结构 | GRID_ENTITY_DETAILS | 地图分析/房间评估 |
| TMTRAINER | 损坏道具解析 | 无 | TMTRAINER_ITEM_INFO | 特殊模式分析 |

## 5. 建议的新增 Sensor 分层

建议以“静态数据”与“动态状态”两层组织新增采集：

### 5.1 静态数据类（低频或启动时一次性）

- ITEM_CONFIG
- ITEM_DESCRIPTIONS
- GRID_ENTITY_DETAILS
- BAG_OF_CRAFTING_DATA（配方表、权重）

### 5.2 动态状态类（按帧或事件）

- POCKET_ITEMS
- PLAYER_PASSIVES / RECENT_ITEMS
- PLAYER_GULPED_TRINKETS
- TRANSFORMATION_PROGRESS
- RNG_PREDICTIONS（按需触发）
- PILL_ID_STATE / BLIND_ITEM_STATE

## 6. 接入注意事项

1. EID 大量信息来源于 ItemConfig 和内部数据表，部分属于“静态数据库”，不必每帧采集。
2. 预测类功能（Spindown/Void/Teleport）依赖 RNG 状态，建议按需请求或在特定交互时触发。
3. 识别状态涉及玩家进度与全局变量（如 ItemPool pill state），需区分“玩家本地状态”和“全局状态”。
4. 通道命名应与现有 Sensor 命名规范一致，便于 Hub 订阅与工具统一。

## 7. 输出结论

当前 SocketBridge 的 12 个 Sensor 主要覆盖“房间与实体的实时状态”，而 EID 还覆盖了“物品知识体系、预测系统、隐藏信息揭示、协同判断、变身与背包合成”。这些部分是未来工具最容易受益且当前未覆盖的可采集内容。

如果要支持“知识型工具 / 预测型工具 / 物品解释器 / 建议系统”，应优先引入：

- ITEM_CONFIG + ITEM_DESCRIPTIONS
- POCKET_ITEMS + PLAYER_PASSIVES
- TRANSFORMATION_PROGRESS
- RNG_PREDICTIONS
- BAG_OF_CRAFTING
