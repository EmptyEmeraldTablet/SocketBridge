# Room Geometry Bug 修复任务清单

> **创建时间**: 2026-01-14
> **来源分析**: `python/analyzed_rooms/ROOM_GEOMETRY_BY_SESSION.md`
> **目标文件**: `python/environment.py`

---

## 概述

基于 `ROOM_GEOMETRY_BY_SESSION.md` 的实测数据分析，发现 `environment.py` 中房间几何属性计算存在多处与游戏实际数据不符的问题。

---

## 问题清单

### 🔴 P0 - 严重 (需立即修复)

| ID | 问题 | 位置 | 严重程度 | 状态 |
|----|------|------|----------|------|
| P0-001 | 像素尺寸计算错误 | `__init__`, `update_from_room_info`, `update_from_room_layout` | 严重 | 待修复 |
| P0-002 | L形房间检测条件错误 | `update_from_room_layout` line 363 | 严重 | 待修复 |
| P0-003 | VOID 区域标记不完整 | `_mark_l_shape_void_tiles` | 严重 | 待修复 |

---

## 详细问题说明

### P0-001: 像素尺寸计算错误

**问题描述**:
像素尺寸计算包含了墙壁厚度，导致 `pixel_width` 和 `pixel_height` 偏大 80px (2格×40px)。

**当前代码**:
```python
# environment.py:149-150 (__init__)
self.pixel_width = width * grid_size
self.pixel_height = height * grid_size

# environment.py:222 (update_from_room_info)
self.pixel_width = self.width * self.grid_size

# environment.py:286-287 (update_from_room_layout)
self.pixel_width = self.width * grid_size
self.pixel_height = self.height * grid_size
```

**正确公式** (来自分析文档):
```
像素宽度  = (grid_width - 2) × 40
像素高度  = (grid_height - 2) × 40
```

**影响范围**:
- `is_in_bounds()` - 边界检查范围偏大 80px
- `get_strategic_positions()` - 房间中心点计算偏移
- `get_danger_level()` - 危险区域检测范围偏大
- 路径规划 - 可能尝试走到墙壁外

**修复方案**:
```python
# 在所有 3 处位置，将
self.pixel_width = self.width * grid_size
# 改为
self.pixel_width = max(0, (self.width - 2) * grid_size)
```

**涉及文件/行号**:
- `environment.py:149-150`
- `environment.py:222`
- `environment.py:286-287`

---

### P0-002: L形房间检测条件错误

**问题描述**:
L 形房间检测条件使用 `room_shape == 2`，但根据分析文档，L 形房间的 Shape Code 是 **9-12**，Shape 2 是横向贮藏室。

**当前代码**:
```python
# environment.py:363
if room_info and room_info.room_shape == 2:  # ❌ 错误
    self._mark_l_shape_void_tiles(room_info)
```

**Shape Code 分类** (来自分析文档):
| Shape Code | 类型 | 是否L形 |
|------------|------|---------|
| 1 | 标准房间 | ❌ |
| 2 | 横向贮藏室 | ❌ |
| 3 | 纵向贮藏室 | ❌ |
| 4 | 两倍高 | ❌ |
| 5 | 竖长走廊 | ❌ |
| 6 | 两倍宽 | ❌ |
| 7 | 横长走廊 | ❌ |
| 8 | 大房间 | ❌ |
| **9** | **L1 (左上缺失)** | **✅** |
| **10** | **L2 (右上缺失)** | **✅** |
| **11** | **L3 (左下缺失)** | **✅** |
| **12** | **L4 (右下缺失)** | **✅** |

**影响**:
- Shape 9-12 的 L 形房间不会被检测 → VOID 区域不标记
- Shape 2 的贮藏室会被错误处理

**修复方案**:
```python
# 将
if room_info and room_info.room_shape == 2:
# 改为
if room_info and room_info.room_shape in [9, 10, 11, 12]:
```

**涉及文件/行号**:
- `environment.py:363`

---

### P0-003: VOID 区域标记不完整

**问题描述**:
`_mark_l_shape_void_tiles` 方法只处理一种 L 形类型（顶部折叠），但 L 形房间有 4 种，每种缺失的角落不同。

**当前实现分析**:
```python
def _mark_l_shape_void_tiles(self, room_info: RoomInfo):
    # 只标记"上方"区域为 VOID
    for gy in range(accessible_grids, self.height):
        # ...
```

这只能正确处理 Shape 9 (L1) 和 Shape 10 (L2)，无法正确处理 Shape 11 和 12。

**L形房间缺角分析** (来自分析文档):
```
         center(center_x, center_y)
           ┌───────┬───────┐
           │  L1   │  L2   │
           │ (520×280)│ (520×280)│
      Y+   ├───────┼───────┤
           │  L3   │  L4   │
           │ (520×280)│ (520×280)│
           └───────┴───────┘
```

| Shape Code | 缺失角落 | 缺角边界 | 标记区域 |
|------------|----------|----------|----------|
| 9 | 左上 | `(top_left) - (center_x, center_y)` | 左上 520×280 |
| 10 | 右上 | `(center_x, top_left) - (bottom_right)` | 右上 520×280 |
| 11 | 左下 | `(top_left) - (center_x, center_y)` | 左下 520×280 |
| 12 | 右下 | `(center_x, center_y) - (bottom_right)` | 右下 520×280 |

**修复方案**:
```python
def _mark_l_shape_void_tiles(self, room_info: RoomInfo):
    if not room_info:
        return

    shape = room_info.room_shape
    top_left = room_info.top_left
    bottom_right = room_info.bottom_right

    # 计算中心点
    center_x = (top_left.x + bottom_right.x) / 2
    center_y = (top_left.y + bottom_right.y) / 2

    # 根据 Shape Code 确定缺角区域
    if shape == 9:  # L1 - 左上缺失
        void_x_range = (0, int(center_x / 40))
        void_y_range = (0, int(center_y / 40))
    elif shape == 10:  # L2 - 右上缺失
        void_x_range = (int(center_x / 40), self.width)
        void_y_range = (0, int(center_y / 40))
    elif shape == 11:  # L3 - 左下缺失
        void_x_range = (0, int(center_x / 40))
        void_y_range = (int(center_y / 40), self.height)
    elif shape == 12:  # L4 - 右下缺失
        void_x_range = (int(center_x / 40), self.width)
        void_y_range = (int(center_y / 40), self.height)
    else:
        return

    # 标记 VOID 区域
    for gy in range(*void_y_range):
        for gx in range(*void_x_range):
            # 跳过边界（门的位置）
            if gy == 0 or gy == self.height - 1:
                continue
            if gx == 0 or gx == self.width - 1:
                continue
            # 跳过已经是墙壁的格子
            if self.grid.get((gx, gy)) == TileType.WALL:
                continue

            self.grid[(gx, gy)] = TileType.VOID
            self.void_tiles.add((gx, gy))
```

**涉及文件/行号**:
- `environment.py:376-430`

---

## 修复验证方案

### 验证数据 (来自分析文档)

| 房间 | Stage | Shape Code | grid | top_left | bottom_right | 期望像素尺寸 |
|------|-------|------------|------|----------|--------------|--------------|
| 97 | 1 | 1 | 13×7 | (60,140) | (580,420) | 440×200 |
| 86 | 1 | 8 | 26×14 | (60,140) | (1100,700) | 960×480 |
| 71 | 2 | 11 | 26×14 | (60,140) | (1100,700) | 960×480 |
| 82 | 3 | 9 | 26×14 | (60,140) | (1100,700) | 960×480 |

**验证公式**:
```
期望 pixel_width  = bottom_right.x - top_left.x
期望 pixel_height = bottom_right.y - top_left.y

实际 pixel_width  = (grid_width - 2) * 40
实际 pixel_height = (grid_height - 2) * 40

验证: 期望值 == 实际值
```

### 测试用例

| 测试场景 | 输入 | 期望结果 |
|----------|------|----------|
| 标准房间 | Room 97, shape=1, grid=13×7 | pixel=440×200, 无 VOID |
| 大房间 | Room 86, shape=8, grid=26×14 | pixel=960×480, 无 VOID |
| L1 房间 | Room 82, shape=9, grid=26×14 | pixel=960×480, 左上 VOID |
| L2 房间 | Room 82, shape=10, grid=26×14 | pixel=960×480, 右上 VOID |
| L3 房间 | Room 71, shape=11, grid=26×14 | pixel=960×480, 左下 VOID |
| L4 房间 | Room 82, shape=12, grid=26×14 | pixel=960×480, 右下 VOID |

---

## 风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 修复后边界检查变严格 | AI 可能被限制在更小区域 | 中 | 更新后测试所有路径规划场景 |
| VOID 标记错误 | AI 可能走进不存在的区域 | 低 | 使用分析文档的验证数据测试 |
| 兼容性问题 | 旧版 room_info 可能缺少字段 | 低 | 添加默认值处理 |

---

## 任务分配

| ID | 任务 | 预估工时 | 优先级 | 依赖 |
|----|------|----------|--------|------|
| T-001 | 修复 P0-001: 像素尺寸计算 | 30min | P0 | 无 |
| T-002 | 修复 P0-002: L形检测条件 | 10min | P0 | T-001 |
| T-003 | 修复 P0-003: VOID 标记完整实现 | 2h | P0 | T-002 |
| T-004 | 添加单元测试 | 1h | P1 | T-001,T-002,T-003 |
| T-005 | 运行集成测试验证 | 30min | P1 | T-004 |

---

## 参考资料

| 文档 | 说明 |
|------|------|
| `python/analyzed_rooms/ROOM_GEOMETRY_BY_SESSION.md` | 房间几何分析报告 v2.1 |
| `python/DATA_PROTOCOL.md` | 数据通道协议文档 |
| `python/models.py` | RoomInfo 数据模型定义 |

---

## 更新日志

| 日期 | 更新内容 | 作者 |
|------|----------|------|
| 2026-01-14 | 初始版本，记录 3 个问题及修复方向 | SocketBridge AI |
