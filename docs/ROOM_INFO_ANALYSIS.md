# Room Info 数据分析报告

> 分析日期: 2026-01-12  
> 数据来源: test_frames.json (从 session_20260112_005209 提取)

---

## 1. 数据对比分析

### 1.1 字段对照表

| # | main.lua 采集字段 | test_frames.json 字段 | 类型 | 一致性 | 备注 |
|---|-------------------|----------------------|------|--------|------|
| 1 | `room_type` | `room_type` | int | ✅ 完全一致 | 房间类型枚举 |
| 2 | `room_shape` | `room_shape` | int | ✅ 完全一致 | 房间形状枚举 |
| 3 | `room_idx` | `room_idx` | int | ✅ 完全一致 | 房间索引 |
| 4 | `stage` | `stage` | int | ✅ 完全一致 | 关卡层级 |
| 5 | `stage_type` | `stage_type` | int | ✅ 完全一致 | 关卡类型 |
| 6 | `difficulty` | `difficulty` | int | ✅ 完全一致 | 难度等级 |
| 7 | `is_clear` | `is_clear` | bool | ✅ 完全一致 | 是否清除 |
| 8 | `is_first_visit` | `is_first_visit` | bool | ✅ 完全一致 | 是否首次访问 |
| 9 | `grid_width` | `grid_width` | int | ✅ 完全一致 | 网格宽度 |
| 10 | `grid_height` | `grid_height` | int | ✅ 完全一致 | 网格高度 |
| 11 | `top_left` | `top_left` | object | ✅ 完全一致 | 左上角坐标 |
| 12 | `bottom_right` | `bottom_right` | object | ✅ 完全一致 | 右下角坐标 |
| 13 | `has_boss` | `has_boss` | bool | ✅ 完全一致 | 是否有Boss |
| 14 | `enemy_count` | `enemy_count` | int | ✅ 完全一致 | 存活敌人数 |
| 15 | `room_variant` | `room_variant` | int | ✅ 完全一致 | 房间变种 |

**结论**: main.lua 采集的所有字段都已正确包含在 test_frames.json 中，数据格式完全一致。

### 1.2 实际数据示例

**Frame 1799 (Room 71, Shape 1, 15×9)**:
```json
{
  "room_type": 1,
  "room_shape": 1,
  "room_idx": 71,
  "stage": 1,
  "stage_type": 1,
  "difficulty": 0,
  "is_clear": false,
  "is_first_visit": true,
  "grid_width": 15,
  "grid_height": 9,
  "top_left": {"x": 60, "y": 140},
  "bottom_right": {"x": 580, "y": 420},
  "has_boss": false,
  "enemy_count": 2,
  "room_variant": 47
}
```

**Frame 2639 (Room 110, Shape 6, 28×9)**:
```json
{
  "room_type": 1,
  "room_shape": 6,
  "room_idx": 110,
  "stage": 1,
  "stage_type": 1,
  "difficulty": 0,
  "is_clear": false,
  "is_first_visit": true,
  "grid_width": 28,
  "grid_height": 9,
  "top_left": {"x": 60, "y": 140},
  "bottom_right": {"x": 1100, "y": 420},
  "has_boss": false,
  "enemy_count": 6,
  "room_variant": 378
}
```

---

## 2. 发现的问题

### 2.1 pixel_width/pixel_height 缺失

**问题**: `main.lua` 没有采集 `pixel_width` 和 `pixel_height`

**影响**:
- Python 端无法直接获取像素尺寸
- 需要通过 `grid_width * grid_size` 计算
- 但 `grid_size` 只在 `ROOM_LAYOUT` 中有，`ROOM_INFO` 中没有

**当前解决方案**:
```python
# environment.py
if room_info.pixel_width > 0:
    self.pixel_width = room_info.pixel_width
else:
    self.pixel_width = self.width * self.grid_size
```

**建议修复**:
```lua
-- main.lua ROOM_INFO 采集
pixel_width = room:GetGridWidth() * 40,
pixel_height = room:GetGridHeight() * 40,
```

### 2.2 room_type 缺少字符串映射

**问题**: `room_type` 是 int，但 Python 端可能需要字符串表示

**当前值**:
- `room_type = 1` (普通房间)
- 需要确认其他值的含义

**建议**:
```lua
-- 添加 room_type_name
room_type_name = {
    [0] = "unknown",
    [1] = "normal",
    [2] = "treasure",
    [3] = "shop",
    [4] = "boss",
    [5] = "secret",
    [6] = "devil",
    [7] = "angel",
    -- ...
}
```

### 2.3 room_shape 缺少字符串映射

**问题**: `room_shape` 是 int，但 debug 时需要可读名称

**当前值**:
- `room_shape = 1` (closet horizontal)
- `room_shape = 6` (wide tight)

**建议**:
```lua
room_shape_name = {
    [0] = "normal",
    [1] = "closet_horizontal",
    [2] = "closet_vertical",
    [3] = "tall",
    [4] = "tall_tight",
    [5] = "wide",
    [6] = "wide_tight",
    [7] = "large",
    [8] = "L1",
    [9] = "L2",
    [10] = "L3",
    [11] = "L4",
}
```

### 2.4 坐标偏移不一致

**观察**:
```
top_left: (60, 140)
bottom_right: (580, 420)
grid_width: 15, grid_height: 9
```

**计算验证**:
- 预期宽度: 15 × 40 = 600 像素
- 实际宽度: 580 - 60 = 520 像素
- 差异: 80 像素 (2个格子的偏移)

**问题**: 坐标不是从 (0,0) 开始，存在偏移

**影响**:
- AI 边界检查需要考虑这个偏移
- `is_in_bounds()` 使用像素边界时需要正确计算

### 2.5 ROOM_LAYOUT 与 ROOM_INFO 重复数据

**问题**: `ROOM_LAYOUT` 中也有 `width`, `height`, `grid_size`

| 字段 | ROOM_INFO | ROOM_LAYOUT |
|------|-----------|-------------|
| grid_size | ❌ | ✅ 135/252 |
| width | grid_width | width |
| height | grid_height | height |

**建议**: 统一使用 `ROOM_LAYOUT` 中的值作为权威来源

---

## 3. 建议新增的采集字段

### 3.1 高优先级

| 字段 | 类型 | 来源 | 用途 |
|------|------|------|------|
| `pixel_width` | int | grid_width × 40 | 像素边界计算 |
| `pixel_height` | int | grid_height × 40 | 像素边界计算 |
| `room_type_name` | string | 映射表 | Debug 可读性 |
| `room_shape_name` | string | 映射表 | Debug 可读性 |
| `clear_percent` | float | room:GetClearPercent() | 房间清除进度 |

### 3.2 中优先级

| 字段 | 类型 | 来源 | 用途 |
|------|------|------|------|
| `door_count` | int | 统计 doors | 房间导航 |
| `obstacle_count` | int | 统计 grid | 复杂度评估 |
| `spawn_points` | array | room:GetSpawnPoints() | 安全位置分析 |
| `grids` | array | 完整网格数据 | L型房间支持 |

### 3.3 低优先级

| 字段 | 类型 | 来源 | 用途 |
|------|------|------|------|
| `music` | int | room:GetMusic() | 氛围检测 |
| `ambience` | int | room:GetAmbience() | 环境音检测 |
| `lighting` | float | room:GetLighting() | 视觉效果 |

---

## 4. room_shape 详细说明

### 4.1 当前已知值

| 值 | 名称 | 尺寸 | grid_size | 有效区域 | VOID 区域 |
|----|------|------|-----------|---------|----------|
| 0 | normal | 13×7 | 40 | 全部 | 无 |
| 1 | closet_h | 13×3 | 135 | 下方 4 行 | 上方 4 行 |
| 2 | closet_v | 5×7 | 135 | 右侧 4 列 | 左侧 4 列 |
| 3 | tall | 13×14 | 40 | 全部 | 无 |
| 4 | tall_tight | 5×14 | 40 | 全部 | 无 |
| 5 | wide | 26×7 | 40 | 全部 | 无 |
| 6 | wide_tight | 26×3 | 252 | 下方 4 行 | 上方 4 行 |
| 7 | large | 26×14 | 40 | 全部 | 无 |
| 8 | L1 | 26×14-13×7 | 40 | 左上/右上/左下 | 右下 |
| 9 | L2 | 26×14-13×7 | 40 | 左上/右上/右下 | 左下 |
| 10 | L3 | 26×14-13×7 | 40 | 左上/右下/右上 | 左上 |
| 11 | L4 | 26×14-13×7 | 40 | 右上/右下/左下 | 左上 |

### 4.2 L型房间的 VOID 计算

**问题**: test_frames.json 中没有 L 型房间的数据

**需要**: 补充 L1-L4 房间的测试用例

**计算逻辑**:
```python
def calculate_void_tiles(room_shape, grid_width, grid_height):
    if room_shape == 8:  # L1
        # 右下 13x7 是 VOID
        void_x_start = grid_width // 2  # 13
        void_y_start = grid_height // 2  # 7
        return [(x, y) for x in range(void_x_start, grid_width) 
                      for y in range(void_y_start, grid_height)]
    # ... 其他形状
```

---

## 5. 数据质量问题

### 5.1 grid_size 不一致

**观察**:
- Shape 1 (15×9): grid_size = 135
- Shape 6 (28×9): grid_size = 252

**问题**: grid_size 不是固定值 40

**影响**:
- 坐标转换需要动态获取 grid_size
- 不同房间形状的边界检查不同

### 5.2 collision 值含义不明确

**观察** (ROOM_LAYOUT.grid):
```json
{
  "type": 16,
  "variant": 8,
  "collision": 4  // 或 5
}
```

**问题**: collision 值的含义不明确

**建议**: 添加 collision 类型映射

---

## 6. 修复建议总结

### 6.1 main.lua 修改

```lua
-- 在 ROOM_INFO 采集后添加
pixel_width = room:GetGridWidth() * 40,
pixel_height = room:GetGridHeight() * 40,

-- 添加名称映射
room_type_name = ROOM_TYPE_NAMES[room:GetType()],
room_shape_name = ROOM_SHAPE_NAMES[room:GetRoomShape()],

-- 清除进度
clear_percent = room:GetClearPercent() or 0,
```

### 6.2 Python 端修改

```python
# models.py - RoomInfo 添加
pixel_width: int = 0
pixel_height: int = 0
room_type_name: str = "unknown"
room_shape_name: str = "unknown"
clear_percent: float = 0.0
```

### 6.3 数据采集补充

- 补充 L 型房间 (shape 8-11) 的测试用例
- 添加不同 stage、room_type 的测试数据
- 收集 boss 房间、secret 房间等特殊房间数据

---

## 7. 测试覆盖情况

| 房间类型 | 数量 | 状态 |
|---------|------|------|
| normal (shape 0) | 0 | ❌ 需要补充 |
| closet_h (shape 1) | 4 | ✅ 已覆盖 |
| closet_v (shape 2) | 0 | ❌ 需要补充 |
| tall (shape 3) | 0 | ❌ 需要补充 |
| tall_tight (shape 4) | 0 | ❌ 需要补充 |
| wide (shape 5) | 0 | ❌ 需要补充 |
| wide_tight (shape 6) | 3 | ✅ 已覆盖 |
| large (shape 7) | 0 | ❌ 需要补充 |
| L1-L4 (shape 8-11) | 0 | ❌ 需要补充 |
| boss room | 0 | ❌ 需要补充 |
| secret room | 0 | ❌ 需要补充 |
| shop | 0 | ❌ 需要补充 |

---

## 8. 结论

### 8.1 数据一致性

✅ main.lua 与 test_frames.json 的 `room_info` 字段**完全一致**  
✅ 所有 15 个采集字段都已正确保存

### 8.2 主要问题

1. **缺少 pixel_width/pixel_height** - 需要从 grid 尺寸计算
2. **缺少可读名称映射** - room_type/room_shape 难以 debug
3. **缺少 L 型房间数据** - 无法测试 VOID 区域处理
4. **grid_size 变化** - 不是固定值 40

### 8.3 后续行动

1. 在 main.lua 中添加 pixel_width/pixel_height 采集
2. 添加 room_type_name 和 room_shape_name
3. 补充 L 型房间的测试用例
4. 更新 Python 端 RoomInfo 数据类
5. 完善 VOID 区域计算逻辑
