# SocketBridge 数据通信协议文档

本文档详细描述了 SocketBridge mod 与 Python 端之间通信的所有数据格式及使用方法。

## 目录

1. [消息类型概述](#消息类型概述)
2. [数据通道详解](#数据通道详解)
3. [事件类型详解](#事件类型详解)
4. [命令控制](#命令控制)
5. [Python 端使用示例](#python-端使用示例)
6. [完整 JSON 示例](#完整-json-示例)

---

## 消息类型概述

SocketBridge 使用四种基本消息类型进行通信：

| 消息类型 | 类型值 | 说明 |
|---------|-------|------|
| DATA | `"DATA"` | 常规数据更新（增量/全量） |
| FULL_STATE | `"FULL"` | 完整状态快照 |
| EVENT | `"EVENT"` | 游戏事件通知 |
| COMMAND | `"CMD"` | 命令执行结果 |

### 消息结构

```json
{
    "version": 2,
    "type": "DATA",
    "frame": 123,
    "room_index": 5,
    "payload": {
        "PLAYER_POSITION": {...},
        "ENEMIES": [...]
    },
    "channels": ["PLAYER_POSITION", "ENEMIES"]
}
```

---

## 数据通道详解

### 1. PLAYER_POSITION - 玩家位置（高频）

**采集频率**: HIGH（每帧）

**JSON 结构**:
```json
{
    "1": {
        "pos": {"x": 320, "y": 240},
        "vel": {"x": 5.0, "y": -2.0},
        "move_dir": 3,
        "fire_dir": 2,
        "head_dir": 0,
        "aim_dir": {"x": 1.0, "y": 0.0}
    },
    "2": {
        "pos": {"x": 350, "y": 280},
        "vel": {"x": 0.0, "y": 0.0},
        "move_dir": 0,
        "fire_dir": 4,
        "head_dir": 1,
        "aim_dir": {"x": 0.0, "y": -1.0}
    }
}
```

**字段说明**:
| 字段 | 类型 | 说明 |
|-----|------|------|
| `pos` | object | 玩家位置坐标 |
| `vel` | object | 玩家速度向量 |
| `move_dir` | int | 移动方向 (0-7 或 GetMovementDirection 返回值) |
| `fire_dir` | int | 射击方向 |
| `head_dir` | int | 头部朝向 |
| `aim_dir` | object | 瞄准方向向量 |

**使用示例** (Python):
```python
# 获取玩家1位置
pos = bridge.get_channel("PLAYER_POSITION")
if pos and 1 in pos:
    x = pos[1]["pos"]["x"]
    y = pos[1]["pos"]["y"]
    print(f"玩家1位置: ({x}, {y})")

# 获取玩家瞄准方向
if pos and 1 in pos:
    aim_x = pos[1]["aim_dir"]["x"]
    aim_y = pos[1]["aim_dir"]["y"]
```

---

### 2. PLAYER_STATS - 玩家属性（低频）

**采集频率**: LOW

**JSON 结构**:
```json
{
    "1": {
        "player_type": 0,
        "damage": 3.5,
        "speed": 1.0,
        "tears": 10,
        "range": 300,
        "tear_range": 300,
        "shot_speed": 1.0,
        "luck": 0,
        "tear_height": 5.0,
        "tear_falling_speed": 0.0,
        "can_fly": false,
        "size": 10.0,
        "sprite_scale": 1.0
    }
}
```

**字段说明**:
| 字段 | 类型 | 说明 |
|-----|------|------|
| `player_type` | int | 玩家角色类型 |
| `damage` | float | 伤害值 |
| `speed` | float | 移动速度 |
| `tears` | float | 射速（MaxFireDelay） |
| `range` | int | 射程 |
| `shot_speed` | float | 弹速 |
| `luck` | int | 幸运值 |
| `can_fly` | bool | 是否能飞行 |
| `size` | float | 碰撞体积 |
| `sprite_scale` | float | 精灵缩放 |

**使用示例**:
```python
stats = bridge.get_channel("PLAYER_STATS")
if stats and 1 in stats:
    damage = stats[1]["damage"]
    speed = stats[1]["speed"]
    can_fly = stats[1]["can_fly"]
```

---

### 3. PLAYER_HEALTH - 玩家生命值（中频）

**采集频率**: LOW

**JSON 结构**:
```json
{
    "1": {
        "red_hearts": 3,
        "max_hearts": 6,
        "soul_hearts": 2,
        "black_hearts": 0,
        "bone_hearts": 0,
        "golden_hearts": 0,
        "eternal_hearts": 0,
        "rotten_hearts": 0,
        "broken_hearts": 0,
        "extra_lives": 0
    }
}
```

**字段说明**:
| 字段 | 类型 | 说明 |
|-----|------|------|
| `red_hearts` | int | 红心数量 |
| `max_hearts` | int | 最大红心容量 |
| `soul_hearts` | int | 灵魂心数量 |
| `black_hearts` | int | 黑心数量 |
| `bone_hearts` | int | 骨心数量 |
| `golden_hearts` | int | 金心数量 |
| `eternal_hearts` | int | 永恒之心数量 |
| `rotten_hearts` | int | 腐烂之心数量 |
| `broken_hearts` | int | 破碎之心数量 |
| `extra_lives` | int | 额外生命 |

**使用示例**:
```python
health = bridge.get_channel("PLAYER_HEALTH")
if health and 1 in health:
    hp = health[1]["red_hearts"] + health[1]["soul_hearts"]
    max_hp = health[1]["max_hearts"]
    black_hearts = health[1]["black_hearts"]
    print(f"当前血量: {hp}, 最大: {max_hp}, 黑心: {black_hearts}")
```

---

### 4. PLAYER_INVENTORY - 玩家物品栏（低频）（由于API缺乏，此通道暂时不可用）

**采集频率**: RARE

**JSON 结构**:
```json
{
    "1": {
        "coins": 15,
        "bombs": 3,
        "keys": 2,
        "trinket_0": 33,
        "trinket_1": 0,
        "card_0": 1,
        "pill_0": 0,
        "collectible_count": 5,
        "collectibles": {
            "1": 1,
            "33": 1,
            "245": 1,
            "246": 1,
            "412": 1
        },
        "active_items": {
            "0": {
                "item": 33,
                "charge": 6,
                "max_charge": 12,
                "battery_charge": 0
            }
        }
    }
}
```

**字段说明**:
| 字段 | 类型 | 说明 |
|-----|------|------|
| `coins` | int | 金币数量 |
| `bombs` | int | 炸弹数量 |
| `keys` | int | 钥匙数量 |
| `trinket_0` | int | 饰品槽位0 |
| `trinket_1` | int | 饰品槽位1 |
| `card_0` | int | 卡牌槽位 |
| `pill_0` | int | 药丸槽位 |
| `collectible_count` | int | 收集品总数 |
| `collectibles` | object | 收集品字典 {物品ID: 数量} |
| `active_items` | object | 主动道具 {槽位: 信息} |

**主动道具详情**:
| 字段 | 类型 | 说明 |
|-----|------|------|
| `item` | int | 主动道具ID |
| `charge` | int | 当前充能 |
| `max_charge` | int | 最大充能 |
| `battery_charge` | int | 电池充能 |

**使用示例**:
```python
inventory = bridge.get_channel("PLAYER_INVENTORY")
if inventory and 1 in inventory:
    inv = inventory[1]
    coins = inv["coins"]
    bombs = inv["bombs"]
    keys = inv["keys"]
    
    # 检查是否有特定物品
    collectibles = inv["collectibles"]
    has_treasure_map = "33" in collectibles  # 33 是宝藏地图
    num_treasure_map = collectibles.get("33", 0)
    
    # 检查主动道具
    active = inv.get("active_items", {})
    if "0" in active:
        active_item = active["0"]["item"]
        charge = active["0"]["charge"]
        max_charge = active["0"]["max_charge"]
        print(f"主动道具: {active_item}, 充能: {charge}/{max_charge}")
```

---

### 5. ENEMIES - 敌人（高频）

**采集频率**: HIGH

**JSON 结构**:
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

**字段说明**:
| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | int | 实体索引（用于标识） |
| `type` | int | 实体类型 |
| `variant` | int | 变种类型 |
| `subtype` | int | 子类型 |
| `pos` | object | 敌人位置 |
| `vel` | object | 敌人速度 |
| `hp` | float | 当前生命值 |
| `max_hp` | float | 最大生命值 |
| `is_boss` | bool | 是否为Boss |
| `is_champion` | bool | 是否为冠军敌人 |
| `state` | int | NPC状态 |
| `state_frame` | int | 状态帧 |
| `projectile_cooldown` | int | 投射物冷却 |
| `projectile_delay` | int | 投射物延迟 |
| `collision_radius` | int | 碰撞半径 |
| `distance` | float | 到玩家距离 |
| `target_pos` | object | 目标位置（玩家位置） |

**使用示例**:
```python
enemies = bridge.get_channel("ENEMIES")
for enemy in enemies:
    enemy_id = enemy["id"]
    x, y = enemy["pos"]["x"], enemy["pos"]["y"]
    hp = enemy["hp"]
    max_hp = enemy["max_hp"]
    dist = enemy["distance"]
    is_boss = enemy["is_boss"]
    
    # 找出最近的敌人
    nearest = min(enemies, key=lambda e: e["distance"])
    print(f"最近敌人: ID={nearest['id']}, 距离={nearest['distance']:.1f}")

# 按距离排序
enemies_by_dist = sorted(enemies, key=lambda e: e["distance"])

# 只获取非Boss敌人
normal_enemies = [e for e in enemies if not e["is_boss"]]
```

---

### 6. PROJECTILES - 投射物（高频）

**采集频率**: HIGH

**JSON 结构**:
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

**字段说明**:
| 字段 | 类型 | 说明 |
|-----|------|------|
| `enemy_projectiles` | array | 敌方投射物列表 |
| `player_tears` | array | 玩家泪弹列表 |
| `lasers` | array | 激光列表 |

**投射物字段**:
| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | int | 实体索引 |
| `pos` | object | 位置 |
| `vel` | object | 速度 |
| `variant` | int | 变种 |
| `collision_radius` | int | 碰撞半径 |
| `height` | float | 高度（用于抛物线） |
| `falling_speed` | float | 下落速度 |
| `falling_accel` | float | 下落加速度 |

**激光字段**:
| 字段 | 类型 | 说明 |
|-----|------|------|
| `id` | int | 实体索引 |
| `pos` | object | 位置 |
| `angle` | float | 角度（度） |
| `max_distance` | float | 最大距离 |
| `is_enemy` | bool | 是否为敌方激光 |

**使用示例**:
```python
projectiles = bridge.get_channel("PROJECTILES")

# 获取敌方投射物
enemy_projs = projectiles.get("enemy_projectiles", [])
for proj in enemy_projs:
    x, y = proj["pos"]["x"], proj["pos"]["y"]
    vx, vy = proj["vel"]["x"], proj["vel"]["y"]
    # 预测位置：proj_pos + vel * (距离 / |vel|)
    dist = proj["distance"]

# 获取玩家泪弹
player_tears = projectiles.get("player_tears", [])
print(f"发射了 {len(player_tears)} 个泪弹")

# 获取激光
lasers = projectiles.get("lasers", [])
for laser in lasers:
    if laser["is_enemy"]:
        # 躲避敌方激光
        angle = laser["angle"]
        print(f"危险激光方向: {angle}度")
```

---

### 7. ROOM_INFO - 房间信息（中频）

**采集频率**: LOW

**JSON 结构**:
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

**字段说明**:
| 字段 | 类型 | 说明 |
|-----|------|------|
| `room_type` | int | 房间类型 |
| `room_shape` | int | 房间形状 |
| `room_idx` | int | 房间索引 |
| `stage` | int | 关卡层级 |
| `stage_type` | int | 关卡类型 |
| `difficulty` | int | 难度 |
| `is_clear` | bool | 房间是否已清除 |
| `is_first_visit` | bool | 是否首次访问 |
| `grid_width` | int | 网格宽度 |
| `grid_height` | int | 网格高度 |
| `top_left` | object | 左上角坐标 |
| `bottom_right` | object | 右下角坐标 |
| `has_boss` | bool | 是否有Boss |
| `enemy_count` | int | 存活敌人数 |
| `room_variant` | int | 房间变种 |

**使用示例**:
```python
room_info = bridge.get_channel("ROOM_INFO")
if room_info:
    is_clear = room_info["is_clear"]
    enemy_count = room_info["enemy_count"]
    stage = room_info["stage"]
    room_idx = room_info["room_idx"]
    grid_width = room_info["grid_width"]
    grid_height = room_info["grid_height"]
    
    if is_clear:
        print("房间已清除，可以安全移动")
    else:
        print(f"房间还有 {enemy_count} 个敌人")
    
    # 计算房间中心
    center_x = (room_info["top_left"]["x"] + room_info["bottom_right"]["x"]) / 2
    center_y = (room_info["top_left"]["y"] + room_info["bottom_right"]["y"]) / 2
```

---

### 8. ROOM_LAYOUT - 房间布局/障碍物（变化时）

**采集频率**: LOW (ON_CHANGE)

**JSON 结构**:
```json
{
    "grid": {
        "0": {
            "type": 1000,
            "variant": 0,
            "variant_name": "NORMAL",
            "state": 0,
            "collision": 1,
            "x": 64,
            "y": 64
        },
        "1": {
            "type": 1000,
            "variant": 1,
            "variant_name": "TINTED",
            "state": 0,
            "collision": 1,
            "x": 128,
            "y": 64
        }
    },
    "doors": {
        "0": {
            "target_room": 3,
            "target_room_type": 1,
            "is_open": true,
            "is_locked": false
        }
    },
    "grid_size": 91,
    "width": 13,
    "height": 7
}
```

**障碍物类型 (GridType)**:
| GridType | 名称 | 说明 |
|----------|------|------|
| 1000 | ROCK | 普通石头 |
| 1001 | STONE | 石头 |
| 1002 | CRACKED | 破裂石头 |
| 1003 | COBBLE | 鹅卵石 |
| 1004 | WOODEN | 木板 |
| 1005 | URN/BUCKET | 罐子/桶 |
| 1007 | BUCKET_WATER | 水桶 |
| 1008 | BUCKET_POOP | 粪桶 |
| 8 | SPIKES | 尖刺 |
| 9 | POISON_SPIKES | 毒尖刺 |
| 10 | WEB | 蜘蛛网 |
| 16 | METAL/KEY/PILLAR | 方块 |
| 17 | POOL/HOLE | 坑 |

**门槽位 (DoorSlot)**:
| 值 | 说明 |
|---|------|
| 0 | LEFT (左) |
| 1 | UP (上) |
| 2 | RIGHT (右) |
| 3 | DOWN (下) |
| 4-7 | 特殊门 |

**使用示例**:
```python
layout = bridge.get_channel("ROOM_LAYOUT")
if layout:
    # 获取所有障碍物
    grid = layout["grid"]
    for idx, tile in grid.items():
        tile_x = tile["x"]
        tile_y = tile["y"]
        tile_type = tile["type"]
        variant_name = tile["variant_name"]
        collision = tile["collision"]
    
    # 获取门信息
    doors = layout["doors"]
    for slot, door in doors.items():
        if door["is_open"] and not door["is_locked"]:
            print(f"门 {slot} 开启，通向房间 {door['target_room']}")
    
    # 构建碰撞地图用于寻路
    collision_map = {}
    for idx, tile in grid.items():
        if tile["collision"] > 0:  # 有碰撞
            collision_map[(tile["x"], tile["y"])] = True
    
    # 检查某位置是否有障碍
    def has_obstacle(x, y):
        for idx, tile in grid.items():
            if tile["x"] == x and tile["y"] == y:
                return tile["collision"] > 0
        return False
```

---

### 9. BUTTONS - 按钮（中频）

**采集频率**: LOW

**JSON 结构**:
```json
{
    "0": {
        "type": 18,
        "variant": 0,
        "variant_name": "NORMAL",
        "state": 0,
        "is_pressed": false,
        "x": 320,
        "y": 400,
        "distance": 100.5
    },
    "1": {
        "type": 18,
        "variant": 2,
        "variant_name": "RED",
        "state": 1000,
        "is_pressed": true,
        "x": 400,
        "y": 400,
        "distance": 180.2
    }
}
```

**按钮类型**:
| Variant | 名称 | 说明 |
|---------|------|------|
| 0 | NORMAL | 普通按钮 |
| 1 | SILVER | 银按钮 |
| 2 | RED | 击杀按钮 |
| 3 | YELLOW | 铁轨按钮 |
| 4 | BROWN | 事件按钮 |
| 5 | ARENA | 竞技场按钮 |
| 6 | ARENA_BOSS | 竞技场Boss按钮 |
| 7 | ARENA_NIGHTMARE | 竞技场噩梦按钮 |

**使用示例**:
```python
buttons = bridge.get_channel("BUTTONS")
for idx, btn in buttons.items():
    x, y = btn["x"], btn["y"]
    is_pressed = btn["is_pressed"]
    btn_type = btn["variant_name"]
    dist = btn["distance"]

# 检查是否有未按下的按钮在附近
nearby_unpressed = [b for b in buttons.values() 
                   if not b["is_pressed"] and b["distance"] < 200]
```

---

### 10. BOMBS - 炸弹（中频）

**采集频率**: LOW

**JSON 结构**:
```json
[
    {
        "id": 30,
        "type": 4,
        "variant": 0,
        "variant_name": "NORMAL",
        "sub_type": 0,
        "pos": {"x": 350, "y": 300},
        "vel": {"x": 0.0, "y": 0.0},
        "explosion_radius": 80,
        "timer": 60,
        "distance": 80.0
    }
]
```

**炸弹类型**:
| Variant | 名称 | 说明 |
|---------|------|------|
| 0 | NORMAL | 普通炸弹 |
| 1 | BIG | 大型炸弹 |
| 2 | DECOY | 诱饵 |
| 3 | TROLL | 即爆炸弹 |
| 4 | MEGA_TROLL | 超级即爆炸弹 |
| 5 | POISON | 毒性炸弹 |
| 6 | BIG_POISON | 大型毒性炸弹 |
| 7 | SAD | 伤心炸弹 |
| 8 | HOT | 燃烧炸弹 |
| 9 | BUTT | 大便炸弹 |
| 10 | MR_MEGA | 大爆弹先生 |
| 11 | BOBBY | 波比炸弹 |
| 12 | GLITTER | 闪光炸弹 |
| 13 | THROWABLE | 可投掷炸弹 |
| 14 | SMALL | 小炸弹 |
| 15 | BRIMSTONE | 硫磺火炸弹 |
| 16 | BLOODY_SAD | 鲜血伤心炸弹 |
| 17 | GIGA | 巨型炸弹 |
| 18 | GOLDEN_TROLL | 金即爆炸弹 |
| 19 | ROCKET | 火箭 |
| 20 | GIGA_ROCKET | 巨型火箭 |

**使用示例**:
```python
bombs = bridge.get_channel("BOMBS")
for bomb in bombs:
    x, y = bomb["pos"]["x"], bomb["pos"]["y"]
    timer = bomb["timer"]
    explosion_radius = bomb["explosion_radius"]
    bomb_type = bomb["variant_name"]
    
    if timer < 30:  # 即将爆炸
        print(f"警告: {bomb_type} 将在 {timer} 帧后爆炸!")
    
    # 计算危险区域
    if bomb_type in ["TROLL", "MEGA_TROLL"]:
        danger_radius = explosion_radius
        # 立即躲避

# 找出最近的定时炸弹
nearest_bomb = min(bombs, key=lambda b: b["distance"])
print(f"最近炸弹: {nearest_bomb['variant_name']}, 距离: {nearest_bomb['distance']:.1f}")
```

---

### 11. INTERACTABLES - 可互动实体（中频）

**采集频率**: LOW

**JSON 结构**:
```json
[
    {
        "id": 40,
        "type": 6,
        "variant": 1,
        "variant_name": "SLOT_MACHINE",
        "sub_type": 0,
        "pos": {"x": 200, "y": 300},
        "vel": {"x": 0.0, "y": 0.0},
        "state": 0,
        "state_frame": 0,
        "target_pos": {"x": 320, "y": 240},
        "distance": 120.5
    }
]
```

**实体类型**:
| Variant | 名称 | 说明 |
|---------|------|------|
| 1 | SLOT_MACHINE | 赌博机 |
| 2 | BLOOD_DONATION | 献血机 |
| 3 | FORTUNE_TELLING | 预言机 |
| 4 | BEGGAR | 乞丐 |
| 5 | DEVIL_BEGGAR | 恶魔乞丐 |
| 6 | SHELL_GAME | 赌博乞丐 |
| 7 | KEY_MASTER | 钥匙大师 |
| 8 | DONATION_MACHINE | 捐款机 |
| 9 | BOMB_BUM | 炸弹乞丐 |
| 10 | RESTOCK_MACHINE | 补货机 |
| 11 | GREED_MACHINE | 贪婪机 |
| 12 | MOMS_DRESSING_TABLE | 妈妈的梳妆台 |
| 13 | BATTERY_BUM | 电池乞丐 |
| 14 | ISAAC_SECRET | 以撒（隐藏） |
| 15 | HELL_GAME | 赌命乞丐 |
| 16 | CRANE_GAME | 娃娃机 |
| 17 | CONFESSIONAL | 忏悔室 |
| 18 | ROTTEN_BEGGAR | 腐烂乞丐 |
| 19 | REVIVE_MACHINE | 复活机 |

**使用示例**:
```python
interactables = bridge.get_channel("INTERACTABLES")
for entity in interactables:
    entity_type = entity["variant_name"]
    x, y = entity["pos"]["x"], entity["pos"]["y"]
    state = entity["state"]
    dist = entity["distance"]

# 找出附近的机器
nearby_machines = [e for e in interactables if e["distance"] < 200]

# 检查捐款机是否有钱
donation_machine = [e for e in interactables 
                   if e["variant_name"] == "DONATION_MACHINE"]
if donation_machine:
    state = donation_machine[0]["state"]
    # 状态为1000表示已损坏

# 找出所有乞丐
beggars = [e for e in interactables if "BEGGAR" in e["variant_name"]]
```

---

### 12. PICKUPS - 可拾取物（中频）

**采集频率**: LOW

**JSON 结构**:
```json
[
    {
        "id": 50,
        "variant": 20,
        "sub_type": 1,
        "pos": {"x": 350, "y": 300},
        "price": 0,
        "shop_item_id": -1,
        "wait": 0
    }
]
```

**可拾取物类型 (Variant)**:
| Variant | 名称 | 类型 |
|---------|------|------|
| 10 | HEART | 红心 |
| 12 | COIN | 硬币 |
| 15 | KEY | 钥匙 |
| 17 | BOMB | 炸弹 |
| 20 | COLLECTIBLE | 收集品 |
| 21 | SHOP_ITEM | 商店物品 |
| 22 | ENDING | 结局道具 |

**使用示例**:
```python
pickups = bridge.get_channel("PICKUPS")
for item in pickups:
    item_id = item["id"]
    variant = item["variant"]
    sub_type = item["sub_type"]
    x, y = item["pos"]["x"], item["pos"]["y"]
    price = item["price"]
    shop_id = item["shop_item_id"]

# 找出免费物品
free_items = [p for p in pickups if p["price"] == 0]

# 找出商店物品
shop_items = [p for p in pickups if p["shop_item_id"] >= 0]

# 按距离排序拾取物
sorted_pickups = sorted(pickups, key=lambda p: 
    ((p["pos"]["x"] - player_x)**2 + (p["pos"]["y"] - player_y)**2)**0.5)
```

---

### 13. FIRE_HAZARDS - 火焰危险物（中频）

**采集频率**: LOW

**JSON 结构**:
```json
[
    {
        "id": 60,
        "type": "FIREPLACE",
        "fireplace_type": "NORMAL",
        "variant": 0,
        "sub_variant": 0,
        "pos": {"x": 400, "y": 350},
        "hp": 5.0,
        "max_hp": 10.0,
        "state": 0,
        "is_extinguished": false,
        "collision_radius": 25,
        "distance": 100.0,
        "is_shooting": false,
        "sprite_scale": 1.0
    }
]
```

**火堆类型**:
| Variant | 名称 | 说明 |
|---------|------|------|
| 0 | NORMAL | 普通火堆 |
| 1 | RED | 红色火堆（发射泪弹） |
| 2 | BLUE | 蓝色火堆 |
| 3 | PURPLE | 紫色火堆（发射泪弹） |
| 4 | WHITE | 白色火堆 |
| 10 | MOVABLE | 可移动火堆 |
| 11 | COAL | 火炭 |

**使用示例**:
```python
fires = bridge.get_channel("FIRE_HAZARDS")
for fire in fires:
    fire_type = fire["fireplace_type"]
    x, y = fire["pos"]["x"], fire["pos"]["y"]
    hp = fire["hp"]
    max_hp = fire["max_hp"]
    is_extinguished = fire["is_extinguished"]
    is_shooting = fire["is_shooting"]
    dist = fire["distance"]

# 找出危险火堆
dangerous_fires = [f for f in fires 
                  if not f["is_extinguished"] and f["distance"] < 200]

# 找出发射泪弹的火堆
shooting_fires = [f for f in fires if f["is_shooting"]]
for fire in shooting_fires:
    print(f"警告: {fire['fireplace_type']} 火堆正在发射泪弹!")
    # 可以计算泪弹来袭方向
```

---

### 14. DESTRUCTIBLES - 可破坏障碍物（中频）

**采集频率**: LOW

**JSON 结构**:
```json
[
    {
        "grid_index": 10,
        "type": 12,
        "name": "tnt",
        "pos": {"x": 300, "y": 300},
        "state": 0,
        "distance": 50.0,
        "variant": 0,
        "variant_name": "NORMAL"
    }
]
```

**可破坏物类型**:
| Type | 名称 | 说明 |
|------|------|------|
| 12 | TNT | TNT炸药 |
| 14 | POOP | 大便 |

**大便变种**:
| Variant | 名称 | 说明 |
|---------|------|------|
| 0 | NORMAL | 普通大便 |
| 1 | CORN | 玉米大便 |
| 2 | RED | 红大便 |
| 3 | GOLD | 金大便 |
| 4 | RAINBOW | 彩虹大便 |
| 5 | BLACK | 黑大便 |
| 6 | HOLY | 白大便 |
| 7 | GIANT | 巨型大便 |
| 8 | CHARMING | 友好大便 |

**使用示例**:
```python
destructibles = bridge.get_channel("DESTRUCTIBLES")
for obj in destructibles:
    obj_type = obj["name"]
    variant_name = obj.get("variant_name", "")
    x, y = obj["pos"]["x"], obj["pos"]["y"]
    state = obj["state"]
    dist = obj["distance"]

# 找出附近的TNT
nearby_tnt = [d for d in destructibles 
             if d["name"] == "tnt" and d["distance"] < 200]
for tnt in nearby_tnt:
    print(f"警告: 附近有TNT! 距离: {tnt['distance']:.1f}")

# 找出大便
poops = [d for d in destructibles if d["name"] == "poop"]
for poop in poops:
    variant = poop["variant_name"]
    # 可以选择是否打碎
```

---

## 事件类型详解

### 已定义事件

| 事件名称 | 触发时机 | 数据结构 |
|---------|---------|---------|
| `ROOM_ENTER` | 进入新房间 | `{room_index, room_info, room_layout}` |
| `ROOM_CLEAR` | 房间清除 | `{room_index}` |
| `PLAYER_DAMAGE` | 玩家受伤 | `{amount, flags, source_type, hp_after}` |
| `NPC_DEATH` | NPC死亡 | `{type, variant, subtype, pos, is_boss}` |
| `PLAYER_DEATH` | 玩家死亡 | `{player_idx}` |
| `GAME_START` | 游戏开始 | `{continued}` |
| `GAME_END` | 游戏结束 | `{reason}` |
| `ITEM_COLLECTED` | 获得道具 | `{item_id, first_time, slot, player_idx}` |

### 事件 JSON 格式

```json
{
    "type": "EVENT",
    "event": "PLAYER_DAMAGE",
    "frame": 123,
    "data": {
        "amount": 1,
        "flags": 0,
        "source_type": 18,
        "hp_after": 3
    }
}
```

### 事件使用示例

```python
@bridge.on("event:PLAYER_DAMAGE")
def on_player_damage(event):
    amount = event.data["amount"]
    hp_after = event.data["hp_after"]
    source_type = event.data["source_type"]
    print(f"受到 {amount} 点伤害，剩余血量: {hp_after}, 伤害来源类型: {source_type}")

@bridge.on("event:ROOM_ENTER")
def on_room_enter(event):
    room_idx = event.data["room_index"]
    print(f"进入房间 {room_idx}")

@bridge.on("event:NPC_DEATH")
def on_npc_death(event):
    is_boss = event.data["is_boss"]
    if is_boss:
        print("Boss 被击败!")
```

---

## 命令控制

### 可用命令

| 命令 | 参数 | 说明 |
|-----|------|------|
| `SET_CHANNEL` | `{channel, enabled}` | 启用/禁用数据通道 |
| `SET_INTERVAL` | `{channel, interval}` | 设置采集频率 |
| `GET_FULL_STATE` | - | 请求完整状态 |
| `GET_CONFIG` | - | 获取当前配置 |
| `SET_MANUAL` | `{enabled}` | 设置手动模式 |
| `SET_FORCE_AI` | `{enabled}` | 设置强制AI模式 |
| `SET_CONTROL_MODE` | `{mode}` | 设置控制模式 |
| `GET_CONTROL_MODE` | - | 获取当前控制模式 |
| `EXEC_CONSOLE` | `{command}` | 执行控制台命令 |

### 采集频率枚举

| 值 | 说明 |
|---|------|
| `HIGH` | 每帧采集 |
| `MEDIUM` | 每几帧采集 |
| `LOW` | 低频率采集 |
| `RARE` | 很少采集 |
| `ON_CHANGE` | 仅变化时采集 |

### 命令使用示例

```python
# 启用/禁用数据通道
bridge.set_channel("ENEMIES", True)
bridge.set_channel("PICKUPS", False)

# 设置采集频率
from isaac_bridge import CollectInterval
bridge.set_interval("PLAYER_POSITION", CollectInterval.HIGH)
bridge.set_interval("ROOM_LAYOUT", CollectInterval.ON_CHANGE)

# 请求完整状态
bridge.request_full_state()

# 设置控制模式
bridge.send_command("SET_CONTROL_MODE", {"mode": "AUTO"})
bridge.set_manual_mode(False)

# 执行控制台命令
bridge.send_console_command("goto s.storage.1")
```

---

## Python 端使用示例

### 基础连接

```python
from isaac_bridge import IsaacBridge, GameDataAccessor

# 创建桥接器
bridge = IsaacBridge(host="127.0.0.1", port=9527)

# 创建数据访问器
data = GameDataAccessor(bridge)

# 启动服务器
bridge.start()
print("等待游戏连接...")
```

### 注册事件处理器

```python
@bridge.on("connected")
def on_connected():
    print("游戏已连接!")
    bridge.set_channel("ENEMIES", True)
    bridge.set_channel("PLAYER_POSITION", True)

@bridge.on("disconnected")
def on_disconnected():
    print("游戏已断开")

@bridge.on("data:PLAYER_POSITION")
def on_position(data):
    if 1 in data:
        x, y = data[1]["pos"]["x"], data[1]["pos"]["y"]
        # 处理位置数据...

@bridge.on("event:PLAYER_DAMAGE")
def on_damage(event):
    print(f"玩家受到伤害: {event.data}")
```

### 发送输入指令

```python
# 移动 (方向: -1, 0, 1)
bridge.send_input(move=(1, 0))      # 向右
bridge.send_input(move=(0, -1))     # 向上
bridge.send_input(move=(-1, 1))     # 向左下

# 射击
bridge.send_input(shoot=(1, 0))     # 向右射击

# 组合指令
bridge.send_input(move=(0, 1), shoot=(0, -1))  # 向下移动，向上射击

# 使用道具/炸弹
bridge.send_input(use_item=True)
bridge.send_input(use_bomb=True)
```

### 便捷数据访问

```python
# 使用 GameDataAccessor
player_pos = data.get_player_position()
player_stats = data.get_player_stats()
player_health = data.get_player_health()
player_inv = data.get_player_inventory()

room_info = data.get_room_info()
room_layout = data.get_room_layout()
is_clear = data.is_room_clear()

enemies = data.get_enemies()
projectiles = data.get_projectiles()
enemy_projs = data.get_enemy_projectiles()
pickups = data.get_pickups()
fires = data.get_fire_hazards()
destructibles = data.get_destructibles()
buttons = data.get_buttons()
bombs = data.get_bombs()
interactables = data.get_interactables()
```

---

## 完整 JSON 示例

### 完整状态消息

```json
{
    "version": 2,
    "type": "FULL",
    "frame": 0,
    "room_index": 5,
    "payload": {
        "PLAYER_POSITION": {
            "1": {
                "pos": {"x": 320, "y": 240},
                "vel": {"x": 0, "y": 0},
                "move_dir": 0,
                "fire_dir": 4,
                "head_dir": 0,
                "aim_dir": {"x": 1, "y": 0}
            }
        },
        "PLAYER_STATS": {
            "1": {
                "player_type": 0,
                "damage": 3.5,
                "speed": 1.0,
                "tears": 10,
                "range": 300,
                "shot_speed": 1.0,
                "luck": 0,
                "can_fly": false,
                "size": 10
            }
        },
        "PLAYER_HEALTH": {
            "1": {
                "red_hearts": 3,
                "max_hearts": 6,
                "soul_hearts": 2,
                "black_hearts": 0,
                "bone_hearts": 0,
                "extra_lives": 0
            }
        },
        "PLAYER_INVENTORY": {
            "1": {
                "coins": 15,
                "bombs": 3,
                "keys": 2,
                "trinket_0": 0,
                "trinket_1": 0,
                "collectible_count": 5,
                "collectibles": {"1": 1, "33": 1, "245": 1},
                "active_items": {"0": {"item": 33, "charge": 6, "max_charge": 12}}
            }
        },
        "ENEMIES": [
            {
                "id": 10,
                "type": 18,
                "variant": 0,
                "pos": {"x": 400, "y": 300},
                "hp": 10,
                "max_hp": 10,
                "is_boss": false,
                "distance": 120.5
            }
        ],
        "PROJECTILES": {
            "enemy_projectiles": [],
            "player_tears": [],
            "lasers": []
        },
        "ROOM_INFO": {
            "room_type": 2,
            "room_shape": 1,
            "room_idx": 5,
            "stage": 2,
            "is_clear": false,
            "grid_width": 13,
            "grid_height": 7,
            "enemy_count": 5
        },
        "ROOM_LAYOUT": {
            "grid": {},
            "doors": {},
            "grid_size": 91
        },
        "PICKUPS": [],
        "FIRE_HAZARDS": [],
        "DESTRUCTIBLES": []
    }
}
```

### 常规数据消息

```json
{
    "version": 2,
    "type": "DATA",
    "frame": 150,
    "room_index": 5,
    "payload": {
        "PLAYER_POSITION": {
            "1": {
                "pos": {"x": 325, "y": 238},
                "vel": {"x": 2, "y": -1}
            }
        },
        "ENEMIES": [
            {
                "id": 10,
                "pos": {"x": 400, "y": 300},
                "hp": 8,
                "distance": 100.2
            },
            {
                "id": 11,
                "pos": {"x": 450, "y": 320},
                "hp": 10,
                "distance": 150.8
            }
        ]
    },
    "channels": ["PLAYER_POSITION", "ENEMIES"]
}
```

### 事件消息

```json
{
    "version": 2,
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

### 命令消息

```json
// 请求
{
    "command": "SET_CONTROL_MODE",
    "params": {"mode": "AUTO"}
}

// 响应
{
    "version": 2,
    "type": "CMD",
    "frame": 153,
    "result": {"success": true, "mode": "AUTO"}
}
```

---

## 附录

### 常用物品 ID

| ID | 名称 |
|----|------|
| 1 | The D6 |
| 2 | D4 |
| 3 | D5 |
| 33 | Treasure Map |
| 245 | Dead Cat |
| 246 | Blank Card |
| 412 | Isaac's Heart |

### 实体类型 (EntityType)

| 值 | 名称 |
|---|------|
| 1 | ENTITY_PLAYER |
| 2 | ENTITY_FAMILIAR |
| 3 | ENTITY_BOMB |
| 4 | ENTITY_PICKUP |
| 5 | ENTITY_PROJECTILE |
| 6 | ENTITY_NPC |
| 7 | ENTITY_EFFECT |
| 8 | ENTITY_LASER |
| 9 | ENTITY_KNIFE |
| 10 | ENTITY_TEAR |
| 12 | ENTITY_MONITOR |
| 13 | ENTITY_MUSHROOM |
| 15 | ENTITY_RAGMAN_2 |
| 18 | ENTITY_ENEMY |
| 20 | ENTITY_FIREPLACE |
| 21 | ENTITY_CRAWLER |
| 22 | ENTITY_PUSHABLE |

### 房间类型 (RoomType)

| 值 | 名称 |
|---|------|
| 0 | NULL |
| 1 | DEFAULT |
| 2 | ERROR |
| 3 | SHOP |
| 4 | LIBRARY |
| 5 | SACRIFICE |
| 6 | DEVIL |
| 7 | ANGEL |
| 8 | SECRET |
| 9 | SUPERSECRET |
| 10 | ARENA |
| 11 | DOOR |

---



### 未来计划添加

跟班信息采集

完成药品，卡牌，道具，饰品的信息采集。

*文档生成时间: 2026*
