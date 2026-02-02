# SocketBridge 已知游戏问题文档

> 本文档记录了通过测试发现的《以撒的结合：重生》游戏 API 存在的问题。
> 
> 目的：帮助区分游戏端问题和 Python 端问题，避免在错误的方向上调试。

---

## 1. GRID_FIREPLACE (ID 13) 问题

### 问题描述
游戏 API 已废弃 `GRID_FIREPLACE` (ID 13)，但在某些情况下仍可能在 `ROOM_LAYOUT` 的 `grid` 数据中返回此类型。

### 影响范围
- `ROOM_LAYOUT` 通道
- `grid` 字段

### 检测方法
```lua
-- Lua 端
if grid_data.type == 13 then
    -- 已废弃的类型
end

-- Python 端 (data_validator.py)
if grid_type == 13:
    logger.warning("Deprecated GRID_FIREPLACE (ID 13) in grid data")
```

### 解决方案
- **Python 端**：忽略此类型的数据，或使用 `ENTITY_EFFECT` 通道获取火堆信息
- **Lua 端**：在发送前过滤掉此类型

### 状态
- 🟡 **已知问题** - 游戏端问题，无法修复
- ✅ **已检测** - 可在验证框架中检测

---

## 2. GRID_DOOR (ID 16) 问题

### 问题描述
`GRID_DOOR` (ID 16) 应该出现在 `ROOM_LAYOUT.doors` 字段中，不应该出现在 `grid` 中。但在某些房间中，door 会被错误地包含在 grid 数据中。

### 影响范围
- `ROOM_LAYOUT` 通道
- `grid` 字段 vs `doors` 字段

### 检测方法
```python
# Python 端
if grid_type == 16:
    logger.warning("GRID_DOOR found in grid - should be in doors")
```

### 解决方案
- **Python 端**：检测到 ID 16 时，尝试从 `doors` 字段获取完整信息
- **Lua 端**：确保 door 不被添加到 grid 收集器

### 状态
- 🟡 **已知问题** - 游戏端问题，无法修复
- ✅ **已检测** - 可在验证框架中检测

---

## 3. aim_dir (0, 0) 问题

### 问题描述
当玩家不瞄准时，`PLAYER_POSITION.aim_dir` 可能返回 `(0, 0)` 而不是预期的默认值或 `null`。

### 影响范围
- `PLAYER_POSITION` 通道
- `aim_dir` 字段

### 检测方法
```python
# Python 端
if player_data["aim_dir"]["x"] == 0 and player_data["aim_dir"]["y"] == 0:
    logger.debug("aim_dir is (0, 0) - player not aiming")
```

### 解决方案
- **Python 端**：在 AI 决策时检查 aim_dir，如果为 (0,0) 则使用默认方向
- **Lua 端**：在发送前设置合理的默认值

### 状态
- 🟡 **已知问题** - 游戏端问题
- ✅ **已检测** - 可在验证框架中检测

---

## 4. 负数 HP 问题

### 问题描述
某些敌人类型在受伤或死亡时会短暂报告负数 HP 值。

### 影响范围
- `ENEMIES` 通道
- `hp` 字段

### 检测方法
```python
# Python 端
if enemy["hp"] < 0:
    logger.warning(f"Enemy {enemy['id']} has negative HP: {enemy['hp']}")
```

### 解决方案
- **Python 端**：将负数 HP 视为 0
- **Lua 端**：在发送前将负数 HP 截断为 0

### 状态
- 🟡 **已知问题** - 游戏端问题
- ✅ **已检测** - 可在验证框架中检测

---

## 5. HP > max_hp 问题

### 问题描述
某些情况下敌人报告的 `hp` 可能超过 `max_hp`，这可能是由于游戏内部计算问题。

### 影响范围
- `ENEMIES` 通道
- `hp` 和 `max_hp` 字段

### 检测方法
```python
# Python 端
if enemy["hp"] > enemy["max_hp"]:
    logger.warning(f"Enemy {enemy['id']} HP {enemy['hp']} > max_hp {enemy['max_hp']}")
```

### 解决方案
- **Python 端**：将 HP 截断为 max_hp
- **Lua 端**：确保 hp 不超过 max_hp

### 状态
- 🟡 **已知问题** - 游戏端问题
- ✅ **已检测** - 可在验证框架中检测

---

## 6. 投射物 ID 复用问题

### 问题描述
投射物（子弹、泪弹、激光）销毁后，其 ID 可能在短时间内被新投射物复用。这在 Python 端追踪投射物生命周期时可能造成混淆。

### 影响范围
- `PROJECTILES` 通道
- `enemy_projectiles`, `player_tears`, `lasers` 字段
- `id` 字段

### 检测方法
```python
# Python 端
if projectile_id in recent_projectile_ids and time_since_last_seen < threshold:
    logger.debug(f"Projectile ID {projectile_id} may have been reused")
```

### 解决方案
- **Python 端**：使用更复杂的投射物追踪逻辑（如基于位置和速度）
- **Lua 端**：使用更长的 ID 生命周期

### 状态
- 🟡 **已知问题** - 游戏端问题
- ✅ **已检测** - 可在验证框架中检测

---

## 7. 拾取物 last_seen_frame 缺失问题

### 问题描述
`PICKUPS` 通道的数据可能不包含 `last_seen_frame` 字段，导致 Python 端无法正确清理已拾取的物品。

### 影响范围
- `PICKUPS` 通道
- 个体拾取物数据

### 检测方法
```python
# Python 端
if "last_seen_frame" not in pickup:
    logger.warning("Pickup missing last_seen_frame")
```

### 解决方案
- **Python 端**：使用当前帧作为 last_seen_frame
- **Lua 端**：确保所有拾取物数据包含 last_seen_frame

### 状态
- 🟡 **已知问题** - Lua 端实现问题
- ✅ **已检测** - 可在验证框架中检测

---

## 8. 房间切换数据残留问题

### 问题描述
切换房间时，Python 端的 `DataProcessor` 只更新 payload 中包含的通道，未包含的通道保留旧数据。这导致前一个房间的实体（如敌人、投射物）残留在新房间。

### 影响范围
- 所有数据通道
- 房间切换场景

### 根本原因
```python
# data_processor.py (原代码)
if "ENEMIES" in payload:
    self.current_state.enemies = parse_enemies(payload["ENEMIES"])
# enemies 不会自动清除！
```

### 解决方案
- ✅ **已修复** - 在 `data_processor.py` 中添加 `_handle_room_transition` 方法
- 在检测到房间切换时清除所有非玩家实体

### 状态
- ✅ **已修复** - 问题已解决

---

## 9. 实体过期清理不完整问题

### 问题描述
`cleanup_stale_entities` 方法只清理 `enemies` 和 `projectiles`，其他实体类型（pickups, buttons, fire_hazards 等）永不清理。

### 影响范围
- `models.py` - `cleanup_stale_entities` 方法

### 根本原因
```python
# models.py (原代码)
def cleanup_stale_entities(self, current_frame):
    stale_enemies = [...]    # 只清理敌人
    stale_projectiles = [...]  # 只清理投射物
    # pickups, buttons 等从不清理！
```

### 解决方案
- ✅ **已修复** - 扩展 `cleanup_stale_entities` 清理所有实体类型
- 为所有实体类型设置 `last_seen_frame`

### 状态
- ✅ **已修复** - 问题已解决

---

## 10. 数据格式不一致问题

### 问题描述
Python 端接收到的数据格式与 Lua 端发送的格式可能不一致：
- `PLAYER_POSITION` 可能返回 list 或 dict
- 某些字段可能缺失

### 影响范围
- 所有数据通道

### 检测方法
```python
# Python 端
if isinstance(player_pos, list):
    player_data = player_pos[0] if len(player_pos) > 0 else None
elif isinstance(player_pos, dict):
    player_data = player_pos.get("1") or player_pos.get(1)
```

### 解决方案
- ✅ **已修复** - 在访问代码中添加类型检查和兼容性处理

### 状态
- ✅ **已修复** - 问题已解决

---

## 问题分类总结

| 问题 | 类型 | 状态 | 严重程度 |
|------|------|------|---------|
| GRID_FIREPLACE (ID 13) | 游戏 API | 已检测 | 低 |
| GRID_DOOR (ID 16) | 游戏 API | 已检测 | 低 |
| aim_dir (0, 0) | 游戏 API | 已检测 | 低 |
| 负数 HP | 游戏 API | 已检测 | 中 |
| HP > max_hp | 游戏 API | 已检测 | 中 |
| 投射物 ID 复用 | 游戏 API | 已检测 | 低 |
| 拾取物 last_seen_frame | Lua 实现 | 已检测 | 中 |
| 房间切换数据残留 | Python 实现 | ✅ 已修复 | 高 |
| 实体过期清理不完整 | Python 实现 | ✅ 已修复 | 高 |
| 数据格式不一致 | Python 实现 | ✅ 已修复 | 中 |

---

## 调试建议

### 遇到数据问题时

1. **使用数据验证框架**
   ```bash
   python3 data_validator.py --live
   ```

2. **检查已知问题列表**
   - 查看本文档是否有相关记录
   - 检查是否需要添加新的已知问题

3. **确认问题来源**
   - 运行 Lua 端验证 (`lua_data_validator.lua`)
   - 运行 Python 端验证 (`data_validator.py`)
   - 对比两边的检测结果

4. **记录新发现**
   - 在本文档中添加新问题记录
   - 更新验证框架的检测逻辑

---

## 贡献指南

如果你发现了新的游戏问题，请：

1. 确认问题可复现
2. 记录问题现象和触发条件
3. 检查是否已有相关记录
4. 在本文档中添加记录
5. 更新验证框架的检测逻辑
6. 提交 PR

---

最后更新: 2026-01-23
版本: 1.0
