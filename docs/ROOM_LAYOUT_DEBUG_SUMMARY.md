# 房间地形处理问题诊断文档

> 创建日期: 2026-01-12  
> 分支: fix/room-layout-processing  
> 状态: 待修复

## 📋 执行摘要

本文档记录了房间地形（ROOM_LAYOUT）数据采集和处理过程中发现的问题。

**核心问题**：AI 无法正确识别房间边界和可行走区域，导致：
- 玩家位置被错误判定为 "out-of-bounds"
- AI 卡在墙边
- 攻击被障碍物阻挡

## 🔧 已修复问题 (2026.1.12)

| 问题 | 根因 | 修复方案 |
|------|------|---------|
| grid_size 不更新 | `update_from_room_layout()` 未存储 `self.grid_size` | 添加 `self.grid_size = grid_size` |
| 初始房间不更新 | `room_index=-1` 时跳过地图更新 | 添加 `first_layout` 条件 |
| 所有位置 out-of-bounds | 误将所有非 grid 数据标记为 VOID | 初始化所有格子为 EMPTY |

## 🚨 待修复问题

### 问题 1: VOID 区域识别不完善 (高优先级)

**现象**：
- L 型房间的缺口区域无法正确识别
- AI 可能尝试穿过不存在的区域

**根因**：
- `ROOM_LAYOUT.grid` 仅包含障碍物和特殊格子
- 稀疏数据无法推断完整房间形状

**数据来源**：
```
ROOM_LAYOUT.grid 只有 3-5 个条目
但实际房间有 15x9 = 135 个格子
```

**解决方案思路**：
1. 利用 `room_shape` 字段确定房间类型
2. 根据 room_shape 预计算 VOID 区域
3. 只在必要时启用 VOID 检查

**room_shape 对照表**：
| 值 | 名称 | 尺寸 | VOID 区域 |
|----|------|------|----------|
| 0 | normal | 13x7 | 无 |
| 1 | closet_h | 13x3 | 上方/下方 4 行 |
| 2 | closet_v | 5x7 | 左侧/右侧 4 列 |
| 3 | tall | 13x14 | 无 |
| 4 | tall_tight | 5x14 | 无 |
| 5 | wide | 26x7 | 无 |
| 6 | wide_tight | 26x3 | 上方/下方 4 行 |
| 7 | large | 26x14 | 无 |
| 8 | L1 | 26x14-13x7 | 右下 13x7 |
| 9 | L2 | 26x14-13x7 | 左下 13x7 |
| 10 | L3 | 26x14-13x7 | 右上 13x7 |
| 11 | L4 | 26x14-13x7 | 左上 13x7 |

### 问题 2: grid_size 不一致 (高优先级)

**发现的值**：
```
grid_size = 135 (shape 1, closet)
grid_size = 252 (shape 6, wide_tight)
grid_size = 40  (默认值)
```

**问题**：
- 不同房间形状使用不同的 grid_size
- 固定碰撞半径 (15px) 可能不适用所有情况

**影响**：
- 坐标转换 (`_get_grid_coords`) 可能出错
- 边界检查结果不可靠

### 问题 3: 边界 margin 固定 (中优先级)

**当前实现**：
```python
margin = 20.0
if not (margin <= position.x <= self.pixel_width - margin):
    return False
```

**问题**：
- margin=20 对于不同 grid_size 可能过大或过小
- 没有考虑碰撞半径的实际需求

## 📊 Debug 数据分析

### 回放数据统计

| 指标 | 值 |
|------|-----|
| 总消息数 | 4126 |
| DATA 消息 | 4086 |
| 含 ROOM_LAYOUT | 4061 (99.4%) |
| room_shape 值 | [1, 6] |
| grid_size 值 | [135, 252] |
| grid 条目数 | ~3-5 (稀疏) |

### 典型数据结构

```json
{
  "ROOM_LAYOUT": {
    "grid_size": 135,
    "width": 15,
    "height": 9,
    "grid": {
      "7": {"x": 320.0, "y": 120.0, "collision": 5, "type": 16},
      "60": {"x": 40.0, "y": 280.0, "collision": 5, "type": 16},
      "127": {"x": 320.0, "y": 440.0, "collision": 5, "type": 16}
    },
    "doors": {}
  }
}
```

**注意**：
- `grid` 只包含有特殊属性的格子（障碍物、门等）
- 普通地板格子没有条目
- collision=5 表示某种障碍物类型

## 🔍 数据采集模块定位

### 采集点 1: main.lua

**文件**: `main.lua:777`

```lua
room_shape = room:GetRoomShape()
```

**问题**：
- 需要确认 `GetRoomShape()` 返回值的含义
- 对照 Isaac 的 RoomShape 枚举

### 采集点 2: main.lua (ROOM_LAYOUT)

**文件**: `main.lua:796-830`

```lua
CollectorRegistry:register("ROOM_LAYOUT", {
    interval = "LOW",
    priority = 2,
    collect = function()
        -- 只采集变化的格子？
    end
})
```

**问题**：
- 采集频率可能过高 (99.4%)
- 只采集了变化的部分，没有完整快照
- grid_size 的计算逻辑未知

### 采集点 3: Python DataProcessor

**文件**: `python/data_processor.py`

```python
def parse_room_layout(data):
    # 解析 grid 字典
    # 但没有利用 room_shape 信息
```

**问题**：
- 没有根据 room_shape 构建完整房间
- VOID 区域计算逻辑缺失

### 采集点 4: EnvironmentModel

**文件**: `python/environment.py`

```python
def update_from_room_layout(self, room_info, layout_data, grid_size):
    # 初始化所有格子为 EMPTY
    # 但没有考虑 room_shape
```

**问题**：
- room_shape 被忽略
- L 型房间的 VOID 无法识别

## 📝 修复计划

### 阶段 1: 数据采集规范化

- [ ] 确认 main.lua 中 `room:GetRoomShape()` 的返回值
- [ ] 确认 `grid_size` 的计算方式
- [ ] 添加完整的 room_shape 对照表到 Python 端
- [ ] 考虑添加完整房间快照模式（可选）

### 阶段 2: 房间形状处理

- [ ] 添加 `room_shape` 到 `RoomInfo` 数据类
- [ ] 实现 `RoomShape` 枚举
- [ ] 根据 room_shape 计算 VOID 区域
- [ ] 更新 `is_in_bounds()` 检查 VOID

### 阶段 3: 边界和碰撞优化

- [ ] 根据 grid_size 动态调整 margin
- [ ] 验证碰撞检测与不同 grid_size 的兼容性
- [ ] 添加更详细的边界调试信息

### 阶段 4: 测试验证

- [ ] 添加 L 型房间测试用例
- [ ] 验证所有 room_shape 的边界检查
- [ ] 测试不同 grid_size 的情况

## 🧪 测试用例

### 用例 1: 普通房间 (shape=0)

```
房间: 13x7, grid_size=40
玩家位置: 任意有效位置
预期: is_in_bounds = True
```

### 用例 2: L1 房间 (shape=8)

```
房间: 26x14, grid_size=40
玩家位置: (100, 100) - 有效区域
预期: is_in_bounds = True
玩家位置: (800, 800) - VOID 区域
预期: is_in_bounds = False
```

### 用例 3: closet (shape=1)

```
房间: 15x9, grid_size=135
有效区域: y >= 540 (下方 4 行)
无效区域: y < 540 (上方 4 行)
```

## 📎 参考资料

- `python/models.py` - RoomInfo 数据类
- `python/environment.py` - GameMap 和 EnvironmentModel
- `python/data_processor.py` - 数据解析
- `main.lua:770-790` - Lua 端数据采集
- `python/DATA_PROTOCOL.md` - 数据协议文档
- `python/test_room_shape.py` - 测试套件 (2026.1.12 分支)

## 🔗 相关分支

| 分支 | 说明 |
|------|------|
| master | 原始代码 |
| 2026.1.12 | 已修复 grid_size 和初始化的 bug |
| fix/room-layout-processing | 当前分支，修复 room_shape 和 VOID |

---

**下一步**: 从 `main.lua` 的数据采集开始，逐模块定位问题。
