# 地形验证工具分析报告

## 问题背景

需要验证游戏地形数据的正确性，区分：
1. **Lua 端问题**: 数据发送本身不正确
2. **Python 端问题**: 数据处理/解析出错

---

## 数据流分析

### Lua → Python 数据流

```
Lua                    TCP Socket              Python
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. main.lua 收集数据
   ↓
2. ROOM_INFO 通道:
   - room_type, room_shape
   - room_idx (负数=特殊房间)
   - grid_width, grid_height  ← 网格尺寸
   - top_left, bottom_right   ← 像素边界
   ↓
3. ROOM_LAYOUT 通道:
   - grid[index] = {type, x, y, collision}  ← 每个格子
   - doors[dir] = {target_room, is_open}    ← 门信息
   ↓
                    JSON 序列化传输
   ↓
4. isaac_bridge.py 接收 JSON
   ↓
5. core/protocol/schema.py 验证
   - RoomInfoData
   - RoomLayoutData
   ↓
6. environment.py 处理
   - GameMap.update_from_room_layout()
   - 坐标转换: gx = (x - top_left) / 40 + 1
   ↓
7. realtime_visualizer.py 显示
```

---

## 关键坐标转换公式

### 1. Lua 端 (main.lua)
```lua
-- 网格索引转世界坐标
local grid_x = idx % room_width
local grid_y = math.floor(idx / room_width)
-- 或使用 Room:GetGridPosition(idx)
```

### 2. Python 端 (environment.py)
```python
# 世界坐标转网格坐标
ACTUAL_GRID_SIZE = 40.0  # 每格 40 像素

# TopLeft 是可行走区域的左上角（即格子 (1,1) 的左上角）
# 但网格数据包含边界墙（从格子 (0,0) 开始）
# 所以需要将 TopLeft 向左上偏移一格（40像素）
adjusted_tl_x = top_left_x - ACTUAL_GRID_SIZE
adjusted_tl_y = top_left_y - ACTUAL_GRID_SIZE

gx = int((tile_x - adjusted_tl_x) / ACTUAL_GRID_SIZE)
gy = int((tile_y - adjusted_tl_y) / ACTUAL_GRID_SIZE)
```

### 3. 像素边界与网格尺寸关系
```
expected_pixel_width = (grid_width - 2) * 40
expected_pixel_height = (grid_height - 2) * 40

验证: 
  actual_pixel_width = bottom_right.x - top_left.x
  若不匹配 → 数据不一致
```

---

## 已知的网格类型 (GridEntityType)

| Type | 名称 | 碰撞 | 处理方式 |
|------|------|------|----------|
| 0 | NULL | 无 | 空地 |
| 2 | ROCK | 是 | 障碍物 (static_obstacle) |
| 7 | PIT | 特殊 | 坑洞 (pit_tiles) |
| 8 | SPIKES | 特殊 | 尖刺 (hazard_tiles) |
| 15 | WALL | 是 | 墙壁 (static_obstacle) |
| 20 | PRESSURE_PLATE | 无 | 压力板 (interactable) |
| 24 | GRAVITY | 无 | 重力区域 |
| 其他 | 未知 | 检查 collision | 根据碰撞值处理 |

---

## 潜在问题点

### Python 端可能问题

1. **坐标转换精度**
   - `int((x - top_left) / 40) + 1` 可能有边界精度问题
   - 特别是 top_left 本身就是浮点数时

2. **L 形房间 VOID 区域计算**
   - Shape 9-12 是 L 形房间
   - 需要正确标记缺失区域为 VOID
   - 见 `environment.py:_mark_l_shape_void_tiles()`

3. **门位置解析**
   - 门需要从 ROOM_LAYOUT.doors 解析
   - 坐标同样需要转换

### Lua 端可能问题

1. **网格索引计算**
   - Isaac 的 GridIndex 是一维的
   - 转换公式需要使用正确的 room_width

2. **世界坐标**
   - `Room:GetGridPosition(idx)` 返回的是世界坐标
   - 需要确保与 top_left 边界一致

3. **特殊房间 (room_idx < 0)**
   - 起始房间等特殊房间可能有负索引
   - Schema 已修复支持负数

---

## 验证工具使用

### 方式 1: terrain_validator.py (新架构)

```bash
cd python

# 实时验证
python -m apps.terrain_validator live

# 打印原始数据
python -m apps.terrain_validator dump
```

功能：
- 验证 ROOM_INFO 和 ROOM_LAYOUT 字段完整性
- 检查像素边界与网格尺寸一致性
- 统计 grid 类型分布
- 检测解析错误

### 方式 2: realtime_visualizer.py (旧架构)

```bash
cd python

# 实时可视化
python realtime_visualizer.py --live

# 回放录像
python realtime_visualizer.py --replay <session_id>
```

---

## 调试建议

### 步骤 1: 收集原始数据
```bash
python -m apps.terrain_validator dump
```
观察 Lua 发送的原始 ROOM_INFO 和 ROOM_LAYOUT

### 步骤 2: 检查关键字段
- `room_shape`: 确定房间形状
- `grid_width`, `grid_height`: 网格尺寸
- `top_left`, `bottom_right`: 像素边界
- `grid` 中各 tile 的 `x`, `y`, `type`, `collision`

### 步骤 3: 验证坐标转换
```python
# 期望关系
pixel_width = (grid_width - 2) * 40
pixel_height = (grid_height - 2) * 40

# 实际计算
actual_width = bottom_right.x - top_left.x
actual_height = bottom_right.y - top_left.y

# 应该匹配
assert abs(pixel_width - actual_width) < 2
assert abs(pixel_height - actual_height) < 2
```

### 步骤 4: 检查特定格子
对于问题格子，验证：
```python
# Lua 发送的
raw_tile = room_layout.grid["123"]  # 某个索引
tile_x, tile_y = raw_tile["x"], raw_tile["y"]

# Python 转换后（使用调整后的 top_left）
adjusted_tl_x = top_left.x - 40
adjusted_tl_y = top_left.y - 40
gx = int((tile_x - adjusted_tl_x) / 40)
gy = int((tile_y - adjusted_tl_y) / 40)

# 期望位置
expected_gx = 123 % grid_width
expected_gy = 123 // grid_width

# 验证一致性
assert gx == expected_gx
assert gy == expected_gy
```

---

## 房间形状参考

| Shape | 名称 | 尺寸 | 说明 |
|-------|------|------|------|
| 1 | 1x1 | 15×9 | 标准小房间 |
| 4 | 1x2 | 15×15 | 竖长房间 |
| 6 | 2x1 | 26×9 | 横长房间 |
| 8 | 2x2 | 26×14 | 大房间 |
| 9 | L1 | 26×14 | L形 (左上缺) |
| 10 | L2 | 26×14 | L形 (右上缺) |
| 11 | L3 | 26×14 | L形 (左下缺) |
| 12 | L4 | 26×14 | L形 (右下缺) |

---

## 文件参考

- [terrain_validator.py](python/apps/terrain_validator.py) - 新验证工具
- [realtime_visualizer.py](python/realtime_visualizer.py) - 原可视化工具
- [environment.py](python/environment.py) - GameMap 实现
- [core/protocol/schema.py](python/core/protocol/schema.py) - 数据模式
- [isaac_bridge.py](python/isaac_bridge.py) - TCP 连接

