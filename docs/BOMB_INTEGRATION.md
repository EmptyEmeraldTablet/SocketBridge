# BOMBS 通道集成文档

> **创建时间**: 2026-01-14
> **作者**: SocketBridge AI System
> **版本**: 1.0

---

## 概述

本文档描述 BOMBS 数据通道如何集成到 AI 威胁检测系统，以及炸弹危险判定的完整逻辑。

## 数据流

```
Lua端 (main.lua)
    │
    ▼
BOMBS 通道数据 (JSON)
    │
    ▼
data_processor.py → game_state.bombs
    │
    ▼
socket_ai_agent.py → entity_data["BOMBS"]
    │
    ▼
environment.py → update_bombs() → RoomEntity
    │
    ▼
DangerSystem → bomb threat detection → ThreatInfo → evasion direction
```

---

## 炸弹危险判定逻辑

### 1. 危险范围判定

**爆炸半径检测**：
- 炸弹危险范围 = `bomb.radius + 15.0`（15.0为玩家碰撞半径）
- 只有当玩家进入危险范围内时，才会产生威胁

### 2. 威胁等级计算

| 条件 | 威胁等级 | 说明 |
|------|----------|------|
| `timer < 15` | CRITICAL | 即将爆炸，必须立即躲避 |
| `timer < 30` | HIGH | 很快爆炸，需要优先躲避 |
| `timer < 60` | MEDIUM | 有一定危险，需要注意 |
| `timer >= 60` | LOW | 危险较低 |
| `is_player_bomb = True` | LOW | 玩家炸弹降低优先级（可能误伤） |

### 3. 特殊炸弹类型

以下炸弹类型具有即时爆炸特性，视为 **CRITICAL** 威胁：

- `TROLL` - 陷阱炸弹
- `MEGA_TROL`L - 大型陷阱炸弹
- `HOT` - 燃烧炸弹

---

## 代码实现

### 1. environment.py - update_bombs()

```python
def update_bombs(self, bomb_data: List[Dict[str, Any]]):
    """更新炸弹数据

    炸弹危险判定逻辑:
    - TROLL/MEGA_TROLL (即时爆炸): 威胁等级 CRITICAL
    - 计时器 < 30 帧: 威胁等级 HIGH
    - 计时器 < 60 帧: 威胁等级 MEDIUM
    - 爆炸半径内危险
    """
    self.entities[EntityType.BOMB].clear()
    count = 0
    for bomb in bomb_data:
        try:
            timer = bomb.get("timer", 90)
            variant_name = bomb.get("variant_name", "")
            explosion_radius = bomb.get("explosion_radius", bomb.get("radius", 80))

            # 特殊炸弹类型（立即爆炸）
            is_instant = variant_name in ["TROLL", "MEGA_TROLL", "HOT"]

            # 危险等级基于计时器
            if is_instant:
                danger_level = 1.0  # 立即爆炸，最高级别
            elif timer < 30:
                danger_level = 0.8  # 即将爆炸
            elif timer < 60:
                danger_level = 0.5  # 中等危险
            else:
                danger_level = 0.2  # 低危险

            entity = RoomEntity(
                entity_type=EntityType.BOMB,
                entity_id=bomb.get("id", 0),
                position=Vector2D(bomb.get("pos", {}).get("x", 0), ...),
                variant_name=variant_name,
                state=timer,
                distance=bomb.get("distance", 0.0),
                radius=explosion_radius,
                is_active=True,
                extra_data={
                    "timer": timer,
                    "explosion_radius": explosion_radius,
                    "is_player_bomb": bomb.get("is_player_bomb", False),
                    "danger_level": danger_level,
                    "is_instant": is_instant,
                },
            )
            self.entities[EntityType.BOMB].append(entity)
            count += 1
        except (ValueError, TypeError) as e:
            logger.warning(f"[GameMap] Failed to parse bomb: {e}")

    logger.debug(f"[GameMap] Updated {count} bombs")
```

### 2. danger_system.py - 炸弹威胁检测

```python
def _assess_immediate_dangers(
    self,
    player_position: Vector2D,
    enemies: Dict[int, EnemyData],
    projectiles: Dict[int, ProjectileData],
    bombs: Optional[Dict[int, BombData]] = None,
) -> List[ThreatInfo]:
    """评估即时危险（包含炸弹威胁）"""
    threats = []

    # 评估炸弹威胁
    if bombs:
        for bomb_id, bomb in bombs.items():
            distance = player_position.distance_to(bomb.position)
            explosion_radius = bomb.radius

            # 检查玩家是否在爆炸范围内
            if distance > explosion_radius + 15.0:
                continue  # 玩家不在危险范围内

            # 计算威胁等级
            threat_level = ThreatLevel.LOW
            estimated_impact = bomb.timer

            # 炸弹类型判断
            if bomb.is_player_bomb:
                # 玩家自己的炸弹降低优先级
                threat_level = ThreatLevel.LOW
            else:
                # 敌人炸弹
                if bomb.timer < 15:
                    threat_level = ThreatLevel.CRITICAL
                elif bomb.timer < 30:
                    threat_level = ThreatLevel.HIGH
                elif bomb.timer < 60:
                    threat_level = ThreatLevel.MEDIUM

            threat = ThreatInfo(
                source_id=bomb_id,
                source_type="bomb",
                position=bomb.position,
                distance=distance,
                threat_level=threat_level,
                estimated_impact_time=estimated_impact,
                direction=Vector2D(0, 0),  # 炸弹是静态的
                priority=100.0 / max(distance, 1),
                damage_estimate=bomb.damage,
            )
            threats.append(threat)

    # ... 投射物和敌人威胁评估
    return threats
```

### 3. socket_ai_agent.py - 数据集成

```python
# 构建 entity_data 时包含 BOMBS
if game_state.bombs:
    entity_data["BOMBS"] = [
        {
            "id": bid,
            "type": b.damage,
            "pos": {"x": b.position.x, "y": b.position.y},
            "timer": b.timer,
            "radius": b.radius,
            "explosion_radius": b.radius,
            "is_player_bomb": b.is_player_bomb,
            "distance": b.position.distance_to(player.position) if player else 0.0,
        }
        for bid, b in game_state.bombs.items()
    ]

# 传递给 DangerSystem
threat = self.danger_system.update(
    frame=self.current_frame,
    player_position=player.position,
    enemies=game_state.enemies,
    projectiles=game_state.projectiles,
    room_bounds=room_bounds,
    bombs=game_state.bombs,  # 新增参数
)
```

---

## 躲避策略

当检测到炸弹威胁时，AI 会：

1. **计算躲避方向**：
   - 方向 = `玩家位置 - 炸弹位置`（远离炸弹）
   - 根据威胁等级加权（CRITICAL 权重更高）

2. **房间边界处理**：
   - 避免躲避方向将玩家推向房间边界

3. **优先级排序**：
   - 优先躲避 CRITICAL 威胁
   - 多炸弹时，综合计算躲避方向

---

## 测试用例

| 测试场景 | 预期结果 |
|----------|----------|
| 炸弹 timer=10, 玩家在爆炸范围内 | 威胁等级 CRITICAL |
| 炸弹 timer=45, 玩家在爆炸范围内 | 威胁等级 MEDIUM |
| 炸弹 timer=90, 玩家在爆炸范围内 | 威胁等级 LOW |
| 炸弹 timer=10, 玩家在爆炸范围外 | 不产生威胁 |
| TROLL 炸弹, 玩家在爆炸范围内 | 威胁等级 CRITICAL |
| 玩家炸弹, 玩家在爆炸范围内 | 威胁等级 LOW |

---

## 已知限制

1. **variant_name 缺失**：当前 BombData 没有 variant 字段，entity_data 中 variant_name 硬编码为 "NORMAL"
   - 需要在 Lua 端添加 bomb variant 数据采集

2. **玩家炸弹处理**：当前将玩家炸弹视为低优先级威胁，但实际游戏中玩家可能被自己的炸弹炸到
   - 后续可考虑添加配置选项

---

## 相关文件

| 文件 | 修改内容 |
|------|----------|
| `python/models.py` | BombData 类定义 |
| `python/environment.py` | update_bombs() 方法，RoomEntity 存储 |
| `python/danger_system.py` | 炸弹威胁检测逻辑 |
| `python/socket_ai_agent.py` | entity_data 构建，参数传递 |
| `python/data_processor.py` | BOMBS 通道解析 |

---

## 更新日志

| 日期 | 更新内容 | 作者 |
|------|----------|------|
| 2026-01-14 | 初始版本，添加 BOMBS 集成 | SocketBridge AI |
