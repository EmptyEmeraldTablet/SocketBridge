# 数据同步时间戳修复方案

## 问题描述

由于Lua端不同数据通道的采集频率不同，Python端无法区分数据的实际采集时间，导致：

1. **敌人数量不一致**: `active_enemies` (实时) vs `room_info.enemy_count` (30帧缓存)
2. **数据过期**: Python端使用消息frame作为更新时间戳，但实际数据可能是30帧前的
3. **决策错误**: AI基于过期的房间状态做出错误决策

## 解决方案

**方案A**: 为每条数据添加采集帧时间戳

## 实现步骤

### Step 1: Lua端 - 添加采集帧标记

**文件**: `main.lua`

**修改位置**: `main.lua:1550-1555` (Network.send 之前的处理)

**修改内容**:
```lua
-- 在 collectAll() 之后，为每条数据添加采集帧标记
local data, channels = CollectorRegistry:collectAll()
for name, channel_data in pairs(data) do
    -- 为每条数据添加采集帧信息
    if type(channel_data) == "table" then
        channel_data._collect_frame = State.frameCounter
    end
end
if next(data) then
    Network.send(Protocol.createDataMessage(data, channels))
end
```

**验证标准**:
- 发送的消息payload中每个channel数据都包含 `_collect_frame` 字段
- 字段值为Lua端的 `State.frameCounter`

### Step 2: Python端 - 使用实际采集帧

**文件**: `python/isaac_bridge.py`

**修改位置**: `GameState.update_batch()` 方法 (line 64-71)

**修改内容**:
```python
def update_batch(self, payload: Dict[str, Any], frame: int, room_index: int = None):
    """批量更新多个通道数据"""
    for channel, data in payload.items():
        # 提取数据的实际采集帧（Lua端添加的时间戳）
        if isinstance(data, dict) and "_collect_frame" in data:
            actual_frame = data.pop("_collect_frame")  # 移除标记字段
        else:
            # 兼容旧数据：使用消息frame
            actual_frame = frame
        
        self.data[channel] = data
        self.last_update[channel] = actual_frame
    self.frame = max(self.frame, frame)
    if room_index is not None:
        self.room_index = room_index
```

**验证标准**:
- `last_update[channel]` 存储的是实际采集帧，而非消息frame
- 旧数据（无 `_collect_frame`）仍能正常工作

### Step 3: 添加日志验证 (可选)

**文件**: `python/socket_ai_agent.py`

**修改位置**: DEBUG-ROOM 日志输出 (line 250-257)

**修改内容**:
```python
print(
    f"[FRAME {self.current_frame} {time.strftime('%H:%M:%S')}] [DEBUG-ROOM] "
    f"grid={game_state.room_info.grid_width}x{game_state.room_info.grid_height}, "
    f"bounds=({room_left},{room_top})-({room_right},{room_bottom}), "
    f"active_enemies={len(game_state.active_enemies)}, "
    f"room_enemy_count={game_state.room_info.enemy_count}, "
    f"lua_frame={game_state.frame}"
)
```

**验证标准**:
- 日志显示 `lua_frame` 应该是Lua端的实际帧号
- `room_enemy_count` 和 `active_enemies` 数量应该一致

### Step 4: 测试验证

1. 启动游戏debug模式
2. 启动Python端
3. 观察DEBUG-ROOM日志，验证:
   - `room_enemy_count` 与 `active_enemies` 数量一致
   - `[DEBUG-ROOM]` 和 Frame日志的enemy_count一致
   - 日志显示 `lua_frame` 随时间递增（不是固定的旧值）

## 预期效果

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 数据新鲜度 | 过期30帧 | 实时 |
| 敌人数量一致性 | 7 vs 0 | 7 vs 7 |
| AI决策准确性 | 可能错误 | 基于最新数据 |

## 回滚计划

如需回滚：
1. 撤销 `main.lua` 的 `collectAll()` 修改
2. 撤销 `python/isaac_bridge.py` 的 `update_batch()` 修改
3. 撤销 `python/socket_ai_agent.py` 的日志修改

## 风险评估

- **低风险**: 纯添加字段，不修改现有数据结构
- **向后兼容**: Python端处理旧数据（无 `_collect_frame`）
- **性能影响**: 极小（每个消息增加一个整数字段）
