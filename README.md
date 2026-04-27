# SocketBridge 项目文档

> **版本**: 3.0
> **更新日期**: 2026年4月
> **状态**: 架构重构完成 — Sensor-based 数据采集框架
> **English**: [README_EN.md](README_EN.md)

---

## 目录

1. [项目概述](#项目概述)
2. [快速开始](#快速开始)
3. [应用工具指南](#应用工具指南)
4. [开发者指南](#开发者指南)
5. [新 Sensor 注册流程](#新-sensor-注册流程)
6. [架构参考](#架构参考)
7. [相关文档](#相关文档)

---

## 项目概述

**SocketBridge** 是为《以撒的结合：重生》（The Binding of Isaac: Repentance）开发的模组，实现游戏与 Python 程序之间的实时数据桥接。

### 核心特性

| 特性 | 说明 |
|------|------|
| **Sensor 数据采集** | 12 个 Sensor，支持 EntityPartition 分区搜索、动态节流（战斗/空闲）、回调驱动触发 |
| **双向通信** | 游戏数据实时传输 + Python 控制指令发送 + 运行时 Sensor 重配置 |
| **订阅协商** | Python 端告知 Lua 端需要哪些 Sensor 及采集频率，按需发送 |
| **实体识别** | 跨帧实体身份追踪、生命周期管理、历史记录、位置预测 |
| **数据录制** | 完整的游戏会话录制与回放系统，支持帧精确定位 |
| **时序感知** | 消息序列号、通道级采集元数据、过期检测 |
| **质量监控** | 自动检测游戏端数据问题，生成质量报告 |

### v3.0 架构亮点

```
┌─────────────────────┐     TCP/IP :9527     ┌──────────────────────────┐
│   Lua (main.lua)    │ ◄──────────────────► │   Python                  │
│                     │                       │                           │
│  SensorRegistry     │   SUBSCRIBE ←         │  connection/ (asyncio)    │
│  ├─ 12 Sensors      │   DATA →              │  protocol/ (Pydantic)     │
│  │  ├─ partition    │   CMD ←→              │  sensors/ (12 mirrors)    │
│  │  ├─ callback     │   CONFIGURE_SENSOR ←  │  entities/ (tracker)      │
│  │  └─ hybrid       │                       │  facade.py (API)          │
│  │  ├─ dynamic      │                       │  persistence/ (record)    │
│  │  └─ throttle     │                       │  validation/ (quality)    │
│  │  ├─ hash cache   │                       │                           │
│  │  └─ forcePending │                       │                           │
│  └──────────────────┘                       └──────────────────────────┘
```

### 目录结构

```
SocketBridge/
├── main.lua                    # 游戏模组主文件（Sensor 系统）
├── metadata.xml
├── README.md
├── README_EN.md
├── LICENCE
├── .gitignore
│
├── docs/                       # 参考文档
│
└── python/                     # Python 端
    ├── facade.py               # 统一入口 API
    ├── isaac_bridge.py         # 向后兼容包装
    ├── requirements.txt
    │
    ├── connection/             # Layer 0: asyncio TCP 服务器
    │   └── server.py
    │
    ├── protocol/               # Layer 1: 消息协议 + 实体 Schema（Pydantic）
    │   ├── schema.py           # 所有实体类型的统一定义
    │   └── messages.py         # RawMessage, SessionMetadata
    │
    ├── sensors/                # Layer 2: Sensor 管线（与 Lua Sensor 镜像）
    │   ├── base.py             # Sensor ABC, SensorRegistry
    │   ├── player.py           # PLAYER_POSITION, PLAYER_STATS, etc.
    │   ├── entities.py         # ENEMIES, PROJECTILES, PICKUPS
    │   ├── room.py             # ROOM_INFO, ROOM_LAYOUT
    │   └── hazards.py          # BOMBS, FIRE_HAZARDS, INTERACTABLES
    │
    ├── entities/               # Layer 3: 实体识别与状态管理
    │   └── tracker.py          # EntityStateManager[T], GameEntityStore
    │
    ├── persistence/            # Layer 4: 录制回放
    │   ├── recorder.py
    │   ├── replayer.py
    │   └── session.py
    │
    ├── validation/             # 数据验证与质量监控
    │   ├── rules.py
    │   └── monitor.py
    │
    ├── apps/                   # 应用工具
    │   ├── console.py
    │   ├── recorder.py
    │   ├── replay_test.py
    │   ├── room_layout_visualizer.py
    │   └── terrain_validator.py
    │
    ├── tests/                  # 测试
    │   ├── test_schema.py
    │   ├── test_entities.py
    │   └── test_sensors.py
    │
    └── archive/                # v2.x 归档代码
        ├── v2_legacy/          # core/, channels/, services/, models/
        └── v2_tests/           # 旧测试文件
```

---

## 快速开始

### 环境要求

- 《以撒的结合：重生》（Repentance DLC / Repentance+）
- **Steam 启动选项必须添加 `--luadebug`**
- Python 3.10+
- `pydantic>=2.0`

```bash
pip install pydantic
```

### 安装步骤

#### 1. 安装游戏模组

将 `SocketBridge` 文件夹复制到游戏 mods 目录：
```
%USERPROFILE%\Documents\My Games\Binding of Isaac Repentance\mods\
```

#### 2. 启动 Python 端

```bash
cd python
python apps/console.py
```

#### 3. 验证连接

启动游戏后，Python 端显示：
```
✓ 游戏已连接: ('127.0.0.1', xxxxx)
```

Lua 端每 ~5 秒输出调试信息：
```
[SB DEBUG] frame=150 connected=YES room=5 subscribed=0 cached=3 sent=150
[SB SEND] frame=150 channels=[PLAYER_POSITION,ENEMIES,PROJECTILES] sizes={...}
```

---

## 应用工具指南

### 1. 交互式控制台 (console.py)

```bash
python apps/console.py
```

**使用：**
```
isaac> giveitem c1       # 给予道具
isaac> spawn 13          # 生成实体
isaac> stage 5a          # 传送到第5层
isaac> help              # 帮助
isaac> quit              # 退出
```

**常用命令：**
| 命令 | 说明 |
|------|------|
| `giveitem c<ID>` | 给予收藏品 |
| `spawn <ID>` | 生成实体 |
| `goto s.boss.0` | 跳转到 Boss 房间 |
| `debug 3` | 开启调试地图 |

### 2. 游戏数据录制器 (recorder.py)

```bash
python apps/recorder.py              # 手动控制
python apps/recorder.py --auto       # 自动录制
python apps/recorder.py --list       # 列出现有录制
python apps/recorder.py --cleanup --keep 5
```

### 3. 回放测试 (replay_test.py)

```bash
python apps/replay_test.py                    # 测试最新会话
python apps/replay_test.py --session <id>    # 指定会话
```

### 4. 房间布局可视化 (room_layout_visualizer.py)

```bash
python apps/room_layout_visualizer.py live       # 实时模式
python apps/room_layout_visualizer.py snapshot   # 快照模式
```

---

## 开发者指南

### 基础数据接收 (新 API)

```python
import asyncio
from facade import SocketBridge

async def main():
    bridge = SocketBridge()
    await bridge.start()

    @bridge.on_frame
    def on_frame(frame, room):
        player = bridge.get_player()
        if player:
            print(f"Frame {frame}: ({player.pos.x:.0f}, {player.pos.y:.0f})")

    await asyncio.Event().wait()  # run forever

asyncio.run(main())
```

### 同步 API (向后兼容)

```python
from isaac_bridge import IsaacBridge, GameDataAccessor

bridge = IsaacBridge()
data = GameDataAccessor(bridge)

@bridge.on("connected")
def on_connected(_):
    print("游戏已连接!")

bridge.start()
```

### 使用 Facade API (推荐)

```python
from facade import SocketBridgeSync

bridge = SocketBridgeSync()

@bridge.on_frame
def on_frame(frame, room):
    enemies = bridge.get_enemies()
    player = bridge.get_player()
    room_info = bridge.get_room()

    if enemies and player:
        nearest = min(enemies, key=lambda e: e.distance)
        print(f"最近敌人: ID={nearest.id} 距离={nearest.distance:.0f}")

bridge.start()
```

### 实体状态管理

```python
from facade import SocketBridgeSync

bridge = SocketBridgeSync()

@bridge.on_frame
def on_frame(frame, room):
    # 获取敌人（有状态保持，跨帧跟踪）
    enemies = bridge.get_enemies(max_stale=5)

    # 获取投射物（有状态保持）
    enemy_proj = bridge.get_enemy_projectiles(max_stale=3)
    player_tears = bridge.get_player_tears(max_stale=3)
    lasers = bridge.get_lasers(max_stale=3)

    # 获取拾取物（有状态保持）
    pickups = bridge.get_pickups(max_stale=30)

    # 威胁数量
    threat = bridge.get_threat_count()
```

### 控制指令

```python
# 移动 + 射击
bridge.send_input(move=(1, 0), shoot=(0, -1))

# 使用道具 / 炸弹
bridge.send_input(use_item=True, use_bomb=True)

# 控制台命令
bridge.send_console("giveitem c1")
```

### 录制回放

```python
from persistence import SessionReplayer, ReplayerConfig, list_sessions

sessions = list_sessions("./recordings")
replayer = SessionReplayer(ReplayerConfig(recordings_dir="./recordings"))
session = replayer.load_session(sessions[0].session_id)

for msg in replayer.iter_messages():
    print(f"Frame {msg.frame}: {msg.channels}")
```

---

## 新 Sensor 注册流程

当需要添加新的数据采集 Sensor 时：

### 步骤 1: Lua 端 — 注册 Sensor

在 `main.lua` 中找到 **Sensor Definitions** 区域：

```lua
SensorRegistry:register("MY_SENSOR", {
    name = "MY_SENSOR",
    search = {
        strategy = "partition",       -- "partition" | "callback" | "hybrid"
        partitions = EntityPartition.ENEMY,
        type_filter = nil,            -- 可选 EntityType
        radius = nil,                 -- nil = 全房间
        sort_by_distance = true,
    },
    throttle = {
        base_interval = 1,
        dynamic = true,               -- 战斗/空闲切换
        combat_interval = 1,
        idle_interval = 15,
    },
    extract = function(entity, player)
        return {
            id = entity.Index,
            pos = Helpers.vectorToTable(entity.Position),
        }
    end,
    cache = { strategy = "hash" },
    triggers = { "MC_POST_NEW_ROOM" },
})
```

如果是直接 API 查询（非实体搜索），定义 `CustomCollectors`：

```lua
function CustomCollectors.MY_SENSOR()
    -- 直接 API 查询
    return { value = someApiCall() }
end
```

### 步骤 2: Python 端 — Pydantic Schema

在 `protocol/schema.py` 中添加：

```python
class MySensorData(BaseModel):
    id: int = Field(..., ge=0)
    pos: Vector2D = Field(default_factory=Vector2D)

    model_config = {"extra": "allow"}
```

### 步骤 3: Python 端 — Sensor 类

在 `sensors/` 目录下创建或修改文件：

```python
# sensors/my_module.py
from sensors.base import Sensor, SensorRegistry, ThrottleConfig
from protocol.schema import MySensorData

class MySensor(Sensor[list[MySensorData]]):
    name = "MY_SENSOR"
    throttle_config = ThrottleConfig(base_interval=1, dynamic=True)
    produces_entities = True  # 如果输出实体

    def parse(self, raw_data, frame):
        if not isinstance(raw_data, list):
            return None
        return [MySensorData(**item) for item in raw_data if isinstance(item, dict)]

SensorRegistry.register(MySensor())
```

### Sensor 采集频率说明

| 策略 | 说明 |
|------|------|
| `partition` | 使用 EntityPartition 位掩码进行分区实体搜索（高效） |
| `callback` | 仅通过游戏回调触发（如 MC_POST_NEW_ROOM） |
| `hybrid` | 分区搜索 + 回调触发 |

**节流模式：**

| 模式 | 战斗 | 空闲 |
|------|------|------|
| HIGH | 每帧 | 15帧 |
| LOW | 每30帧 | 30帧 |
| RARE | 每90帧 | 90帧 |
| callback-only | -1（禁用轮询） | -1 |

---

## 架构参考

### 数据流程

```
Lua MC_POST_UPDATE (30 tps)
    │
    ├─ SensorRegistry:collectAll()
    │   ├─ _shouldCollect() → per-sensor frame counter + dynamic throttle
    │   ├─ CustomCollector or searchEntities()
    │   │   ├─ EntityPartition search (efficient)
    │   │   └─ extract() per entity
    │   ├─ hash cache check
    │   └─ forcePending → include force-collected data
    │
    ├─ Protocol.createDataMessage()
    │   └─ sensor metadata + payload + channels
    │
    └─ Network.send(json)
            │
            ▼ TCP :9527
            │
Python BridgeServer (asyncio)
    │
    ├─ JSON-line parse → dict
    │
    ├─ SocketBridge._handle_message()
    │   ├─ EVENT → dispatch to callbacks
    │   ├─ CMD → dispatch command_result
    │   └─ DATA →
    │       ├─ DataMessage.from_dict()
    │       ├─ SensorRegistry.process_message()
    │       │   └─ per-sensor: parse → validate → normalize
    │       ├─ GameEntityStore.update_*()
    │       │   └─ track identity across frames
    │       └─ fire on_frame callbacks
    │
    └─ Apps receive typed data via Facade API
```

### Sensor 列表

| Sensor | 搜索策略 | 节流 | 实体追踪 | 说明 |
|--------|---------|------|---------|------|
| `PLAYER_POSITION` | callback | 1帧 | — | 玩家位置、速度、朝向 |
| `PLAYER_STATS` | callback | 30帧 | — | 伤害、速度、射程等 |
| `PLAYER_HEALTH` | callback | 30帧 | — | 各种心之容器 |
| `PLAYER_INVENTORY` | callback | 90帧 | — | 金币、炸弹、钥匙、收集品 |
| `ENEMIES` | partition | 1/15帧 | ✅ | 敌人（战斗1帧/空闲15帧） |
| `PROJECTILES` | partition | 1/15帧 | ✅ | 投射物、泪弹、激光 |
| `ROOM_INFO` | callback | 15帧 | — | 房间类型、尺寸、敌人数量 |
| `ROOM_LAYOUT` | callback | 仅回调 | — | 网格实体、门 |
| `BOMBS` | partition | 15帧 | ✅ | 炸弹（类型、计时器） |
| `FIRE_HAZARDS` | hybrid | 15帧 | — | 火焰危险物 |
| `PICKUPS` | partition | 15帧 | ✅ | 可拾取物 |
| `INTERACTABLES` | partition | 15帧 | — | 机器、乞丐等 |

### 命令参考

| 命令 | 参数 | 说明 |
|------|------|------|
| `CONFIGURE_SENSOR` | `{sensor, throttle, enabled}` | 运行时重配置 Sensor |
| `LIST_SENSORS` | — | 列出所有 Sensor |
| `SUBSCRIBE_SENSORS` | `{sensors: [...]}` | 订阅指定 Sensor |
| `UNSUBSCRIBE_SENSORS` | `{sensors: [...]}` | 取消订阅 |
| `EXEC_CONSOLE` | `{command}` | 执行控制台指令 |
| `SET_CONTROL_MODE` | `{mode}` | 设置控制模式 (MANUAL/AUTO/FORCE_AI) |
| `GET_FULL_STATE` | — | 请求完整状态快照 |

---

## 相关文档

- [DATA_PROTOCOL.md](python/DATA_PROTOCOL.md) — 数据协议详细文档
- [CONSOLE_COMMANDS.md](python/CONSOLE_COMMANDS.md) — 控制台命令参考
- [docs/EID_TECHNICAL_REFERENCE.md](docs/EID_TECHNICAL_REFERENCE.md) — EID 技术参考
- [docs/archivedDoc/KNOWN_GAME_ISSUES.md](docs/archivedDoc/KNOWN_GAME_ISSUES.md) — 已知游戏问题

---

**最后更新：** 2026年4月
**版本：** 3.0
