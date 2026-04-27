# SocketBridge v3.0 数据通信协议

## 目录

1. [消息类型概述](#消息类型概述)
2. [订阅协商](#订阅协商)
3. [数据消息结构 (v3.0)](#数据消息结构-v30)
4. [Sensor 数据格式](#sensor-数据格式)
5. [事件类型](#事件类型)
6. [命令控制](#命令控制)
7. [运行时重配置](#运行时重配置)

---

## 消息类型概述

| 类型 | 值 | 方向 | 说明 |
|------|-----|------|------|
| DATA | `"DATA"` | Lua → Python | 常规数据更新 |
| FULL | `"FULL"` | Lua → Python | 完整状态快照 |
| EVENT | `"EVENT"` | Lua → Python | 游戏事件通知 |
| CMD | `"CMD"` | Lua → Python | 命令执行结果 |
| SUBSCRIBE | `"SUBSCRIBE"` | Python → Lua | Sensor 订阅请求 |
| SUBSCRIBE_ACK | `"SUBSCRIBE_ACK"` | Lua → Python | 订阅确认 |

---

## 订阅协商

Python 端连接后可发送订阅请求，Lua 端仅发送已订阅的 Sensor 数据。

### Python → Lua: SUBSCRIBE

```json
{
    "type": "SUBSCRIBE",
    "sensors": ["ENEMIES", "PLAYER_POSITION", "PROJECTILES", "ROOM_INFO"],
    "config_overrides": {
        "ENEMIES": {
            "throttle": {"combat_interval": 1, "idle_interval": 30}
        }
    }
}
```

### Lua → Python: SUBSCRIBE_ACK

```json
{
    "version": "3.0",
    "type": "SUBSCRIBE_ACK",
    "accepted": ["ENEMIES", "PLAYER_POSITION", "PROJECTILES", "ROOM_INFO"],
    "rejected": [],
    "sensor_configs": {
        "ENEMIES": {"enabled": true, "throttle": {"combat_interval": 1, ...}},
        "PLAYER_POSITION": {...}
    }
}
```

> 注意：如果从未发送 SUBSCRIBE，所有 Sensor 默认启用（空订阅表 = 全部采集）。

---

## 数据消息结构 (v3.0)

```json
{
    "version": "3.0",
    "type": "DATA",
    "timestamp": 123456789000,
    "frame": 123,
    "room_index": 5,

    "seq": 456,
    "game_time": 123456789000,
    "prev_frame": 122,

    "sensors": {
        "PLAYER_POSITION": {
            "collect_frame": 123,
            "collect_time": 123456789000,
            "interval": "fixed",
            "stale_frames": 0,
            "entity_count": 1,
            "hash": "a1b2c3d4"
        },
        "ENEMIES": {
            "collect_frame": 123,
            "collect_time": 123456789000,
            "interval": "dynamic",
            "stale_frames": 0,
            "entity_count": 3,
            "hash": "e5f6g7h8"
        }
    },

    "payload": {
        "PLAYER_POSITION": {...},
        "ENEMIES": [...]
    },
    "channels": ["PLAYER_POSITION", "ENEMIES"]
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `version` | string | 协议版本 `"3.0"` |
| `type` | string | `"DATA"` / `"FULL"` |
| `seq` | int | 消息序列号（递增） |
| `frame` | int | 发送时的游戏帧号 |
| `game_time` | int | 游戏内毫秒时间戳 |
| `prev_frame` | int | 上一条消息的帧号 |
| `room_index` | int | 当前房间索引 |
| `sensors` | object | 各 Sensor 采集元数据 |
| `sensors.*.collect_frame` | int | 该 Sensor 数据实际采集的帧号 |
| `sensors.*.entity_count` | int | 采集到的实体数量 |
| `sensors.*.hash` | string | 数据哈希（变化检测） |
| `sensors.*.stale_frames` | int | 数据过期帧数（当前帧 - 采集帧） |
| `payload` | object | 各 Sensor 的数据负载 |
| `channels` | array | 本条消息包含的 Sensor 名称 |

### v2.x 兼容

v3.0 仍可解析 v2.1 消息（`channel_meta` → `sensors` 自动转换）。`version` 字段从 v2.1 的 `"2.1"` (字符串) 或 v2.0 的 `2` (数字) 均兼容。

---

## Sensor 数据格式

### PLAYER_POSITION

```json
[
    {
        "pos": {"x": 320, "y": 240},
        "vel": {"x": 5.0, "y": -2.0},
        "move_dir": 3,
        "fire_dir": 2,
        "head_dir": 0,
        "aim_dir": {"x": 1.0, "y": 0.0}
    }
]
```

支持列表格式（`[{...}]`）或字典格式（`{"1": {...}}`）。

### ENEMIES

```json
[
    {
        "id": 10,
        "type": 18,
        "variant": 0,
        "subtype": 0,
        "pos": {"x": 400, "y": 300},
        "vel": {"x": 1.0, "y": 0.0},
        "hp": 10.0,
        "max_hp": 10.0,
        "is_boss": false,
        "is_champion": false,
        "state": 3,
        "state_frame": 45,
        "projectile_cooldown": 0,
        "projectile_delay": 30,
        "collision_radius": 15,
        "distance": 150.5,
        "target_pos": {"x": 320, "y": 240},
        "v1": {"x": 0, "y": 0},
        "v2": {"x": 0, "y": 0}
    }
]
```

### PROJECTILES

```json
{
    "enemy_projectiles": [
        {
            "id": 15,
            "pos": {"x": 350, "y": 200},
            "vel": {"x": 3.0, "y": 4.0},
            "variant": 0,
            "collision_radius": 10,
            "height": -5.0,
            "falling_speed": 0.0,
            "falling_accel": 0.0
        }
    ],
    "player_tears": [
        {
            "id": 20,
            "pos": {"x": 320, "y": 240},
            "vel": {"x": 0.0, "y": -10.0},
            "variant": 0,
            "collision_radius": 10,
            "height": -2.0,
            "scale": 1.0
        }
    ],
    "lasers": [
        {
            "id": 25,
            "pos": {"x": 300, "y": 280},
            "angle": 90.0,
            "max_distance": 500,
            "is_enemy": false
        }
    ]
}
```

### ROOM_INFO

```json
{
    "room_type": 2,
    "room_shape": 1,
    "room_idx": 5,
    "stage": 2,
    "stage_type": 0,
    "difficulty": 0,
    "is_clear": false,
    "is_first_visit": true,
    "grid_width": 13,
    "grid_height": 7,
    "top_left": {"x": 0, "y": 0},
    "bottom_right": {"x": 832, "y": 448},
    "has_boss": false,
    "enemy_count": 5,
    "room_variant": 0
}
```

### ROOM_LAYOUT

```json
{
    "grid": {
        "0": {"type": 2, "variant": 0, "state": 0, "collision": 1, "x": 64, "y": 64},
        "1": {"type": 15, "variant": 0, "state": 0, "collision": 1, "x": 128, "y": 64}
    },
    "doors": {
        "0": {"target_room": 3, "target_room_type": 1, "is_open": true, "is_locked": false, "x": 320, "y": 60}
    },
    "grid_size": 91,
    "width": 13,
    "height": 7
}
```

### PICKUPS / BOMBS / FIRE_HAZARDS / INTERACTABLES

与其他实体列表格式一致，详见 `protocol/schema.py` 中的 Pydantic 模型定义。

---

## 事件类型

| 事件名 | 触发时机 | 数据 |
|--------|---------|------|
| `ROOM_ENTER` | 进入新房间 | `{room_index, room_info, room_layout}` |
| `ROOM_CLEAR` | 房间清除 | `{room_index}` |
| `PLAYER_DAMAGE` | 玩家受伤 | `{amount, flags, source_type, hp_after}` |
| `NPC_DEATH` | NPC 死亡 | `{type, variant, subtype, pos, is_boss}` |
| `PLAYER_DEATH` | 玩家死亡 | `{player_idx}` |
| `GAME_START` | 游戏开始 | `{continued}` |
| `GAME_END` | 游戏结束 | `{reason}` |
| `ITEM_COLLECTED` | 获得道具 | `{item_id, first_time, slot, player_idx}` |

事件消息格式：
```json
{
    "version": "3.0",
    "type": "EVENT",
    "event": "PLAYER_DAMAGE",
    "frame": 152,
    "data": {
        "amount": 1,
        "flags": 0,
        "source_type": 18,
        "hp_after": 4
    }
}
```

---

## 命令控制

### 可用命令

| 命令 | 参数 | 说明 |
|------|------|------|
| `CONFIGURE_SENSOR` | `{sensor, throttle?, enabled?}` | 运行时重配置 Sensor |
| `LIST_SENSORS` | — | 列出所有 Sensor |
| `GET_SENSOR_CONFIG` | `{sensor}` | 获取 Sensor 配置 |
| `SUBSCRIBE_SENSORS` | `{sensors: [...]}` | 订阅 Sensor |
| `UNSUBSCRIBE_SENSORS` | `{sensors: [...]}` | 取消订阅 |
| `SET_CHANNEL` | `{channel, enabled}` | 启用/禁用 Sensor（兼容旧版） |
| `GET_FULL_STATE` | — | 请求完整状态 |
| `SET_CONTROL_MODE` | `{mode}` | 控制模式 (MANUAL/AUTO/FORCE_AI) |
| `GET_CONTROL_MODE` | — | 获取当前模式 |
| `EXEC_CONSOLE` | `{command}` | 执行控制台指令 |

### 命令请求/响应格式

```json
// 请求
{"command": "EXEC_CONSOLE", "params": {"command": "giveitem c1"}}

// 响应
{
    "version": "3.0",
    "type": "CMD",
    "frame": 153,
    "result": {"success": true, "command": "giveitem c1", "result": ""}
}
```

### 运行时重配置示例

```json
// 将 ENEMIES Sensor 改为战斗每帧、空闲每30帧采集
{"command": "CONFIGURE_SENSOR", "params": {
    "sensor": "ENEMIES",
    "throttle": {"combat_interval": 1, "idle_interval": 30}
}}

// 禁用 FIRE_HAZARDS Sensor
{"command": "CONFIGURE_SENSOR", "params": {
    "sensor": "FIRE_HAZARDS",
    "enabled": false
}}
```

---

## 时序问题检测

v3.0 的 `TimingMonitor` 在 Python 端检测以下问题：

| 问题类型 | 检测条件 | 严重程度 |
|---------|---------|---------|
| `FRAME_GAP` | seq 跳跃 > 1 | warning |
| `FRAME_JUMP` | 帧号跳跃 > 5 | warning / error |
| `OUT_OF_ORDER` | 帧号回退或 seq 乱序 | error |
| `STALE_DATA` | stale_frames > 间隔 × 2 | info |
| `CHANNEL_DESYNC` | 高频 Sensor 帧差 > 1 | warning |

---

*文档更新: 2026年4月 — v3.0*
