# 对象跟踪与空间感知系统 - 快速入门指南

## 🎯 系统概述

这个系统将《以撒的结合：重生》的实时游戏数据转换为稳定的、可追踪的抽象模型，为AI智能体提供可靠的游戏空间感知能力。

### 核心问题解决

**问题：** 游戏每帧都在变化，敌人位置、投射物位置都在实时更新，如何从这些流式数据中构建出稳定的对象模型？

**解决方案：**
1. **对象跟踪** - 通过ID识别和跟踪每个对象，维护完整的生命周期
2. **历史轨迹** - 记录对象的位置和行为历史，支持行为模式分析
3. **抽象空间** - 将连续空间离散化为网格，每个网格单元包含威胁信息
4. **威胁分析** - 实时分析空间中的威胁分布，为决策提供依据

---

## 📦 文件结构

```
python/
├── game_tracker.py          # 对象跟踪器（核心）
├── game_space.py            # 游戏空间模型（核心）
├── advanced_ai_example.py   # 高级AI示例
├── test_tracker.py          # 测试工具
├── visualize_space.py       # 可视化工具
├── TRACKING_SYSTEM.md       # 完整文档
└── QUICKSTART_TRACKING.md    # 本文件
```

---

## 🚀 5分钟快速开始

### 步骤1：测试对象跟踪器

```bash
cd python
python test_tracker.py
```

**预期输出：**
```
============================================================
帧数: 1234
房间: 42
============================================================

跟踪器统计:
  总敌人数: 15
  活跃敌人: 5
  击杀敌人: 10
  总投射物: 120
  活跃投射物: 8

活跃敌人详情:
  ID=12345, 类型=10, 血量=20.0/20.0, 位置=(300.0, 200.0), 模式=chasing
  ID=12346, 类型=10, 血量=15.0/20.0, 位置=(350.0, 250.0), 模式=erratic
```

### 步骤2：查看空间可视化

```bash
python visualize_space.py
```

**预期输出：**
```
================================================================================
空间可视化 - 帧 1234
================================================================================

威胁分析:
  当前威胁等级: 0.345
  威胁分类: medium
  最近敌人距离: 150.0
  最近投射物距离: 80.0
  危险投射物数量: 3

...................E.......................
...................*.......................
...................*.......................
...................@.......................
...................*.......................
...................E.......................
...................*.......................

图例:
  @ - 玩家位置
  E - 敌人
  * - 投射物
  # - 障碍物
  . - 安全区域 (威胁 < 0.2)
```

### 步骤3：运行高级AI

```bash
python advanced_ai_example.py
```

AI会自动根据威胁分析做出移动和射击决策。

---

## 💡 核心概念

### 1. 对象跟踪（Object Tracking）

**问题：** 如何从每帧变化的敌人列表中识别出同一个敌人？

**解决方案：** 使用对象ID进行跟踪

```python
# 每帧更新
tracker.update(frame, enemies_data, projectiles_data)

# 获取活跃敌人
active_enemies = tracker.get_active_enemies()

# 每个敌人都有唯一ID
for enemy in active_enemies:
    print(f"ID={enemy.id}, HP={enemy.hp}")
```

**关键特性：**
- ✅ 通过ID识别对象
- ✅ 维护对象生命周期（从出现到消失）
- ✅ 记录历史轨迹（最近60帧）
- ✅ 分析行为模式（stationary/chasing/erratic）

### 2. 空间网格化（Space Grid）

**问题：** 如何将连续的游戏空间转换为可计算的抽象模型？

**解决方案：** 将空间划分为网格

```python
# 创建空间模型（网格大小40像素）
space = GameSpace(grid_size=40.0)

# 从房间数据初始化
space.initialize_from_room(room_info, room_layout)

# 每帧更新
space.update(player_pos, tracker)

# 获取威胁等级
threat_level = space.get_threat_at(player_pos)
```

**关键特性：**
- ✅ 离散化空间（网格单元）
- ✅ 每个网格单元包含威胁信息
- ✅ 支持路径规划（A*算法）
- ✅ 支持安全区域识别

### 3. 威胁分析（Threat Analysis）

**问题：** 如何量化玩家面临的威胁？

**解决方案：** 计算威胁场

```python
# 创建威胁分析器
analyzer = ThreatAnalyzer(space, tracker)

# 分析玩家威胁
threat_info = analyzer.analyze_player_threat(player_pos)

# 获取推荐行动
recommendation = analyzer.get_recommended_action(player_pos)
```

**威胁等级分类：**
- **critical** - 紧急躲避
- **high** - 谨慎移动
- **medium** - 战术移动
- **low** - 自由移动

---

## 📊 数据流示例

### 输入：实时游戏数据

```json
{
  "frame": 1234,
  "PLAYER_POSITION": {
    "0": {
      "pos": {"x": 100.0, "y": 200.0},
      "vel": {"x": 1.5, "y": 0.0}
    }
  },
  "ENEMIES": [
    {
      "id": 12345,
      "pos": {"x": 300.0, "y": 200.0},
      "vel": {"x": 0.5, "y": 0.0},
      "hp": 20.0,
      "max_hp": 20.0
    }
  ],
  "PROJECTILES": {
    "enemy_projectiles": [
      {
        "id": 67890,
        "pos": {"x": 250.0, "y": 180.0},
        "vel": {"x": -2.0, "y": 0.0}
      }
    ]
  }
}
```

### 输出：稳定的对象模型

```python
# 跟踪器输出
{
  "active_enemies": [
    {
      "id": 12345,
      "pos": Position(300.0, 200.0),
      "vel": Velocity(0.5, 0.0),
      "hp": 20.0,
      "max_hp": 20.0,
      "movement_pattern": "chasing",
      "lifetime_frames": 150
    }
  ],
  "enemy_projectiles": [
    {
      "id": 67890,
      "pos": Position(250.0, 180.0),
      "vel": Velocity(-2.0, 0.0)
    }
  ]
}

# 空间模型输出
{
  "grid": {
    (5, 3): {
      "threat_level": 0.345,
      "threat_sources": [12345, 67890],
      "is_safe": false
    }
  }
}

# 威胁分析输出
{
  "current_threat": 0.345,
  "threat_level": "medium",
  "nearest_enemy_distance": 200.0,
  "nearest_projectile_distance": 150.0,
  "recommended_action": {
    "action": "tactical_move",
    "move_dir": (-0.71, 0.71),
    "shoot_dir": (0.82, -0.57),
    "confidence": 0.60
  }
}
```

---

## 🎮 使用场景

### 场景1：简单的躲避AI

```python
from isaac_bridge import IsaacBridge
from game_tracker import ObjectTracker, Position

bridge = IsaacBridge()
tracker = ObjectTracker()

@bridge.on("data")
def on_data_update(data):
    frame = bridge.state.frame
    
    # 更新跟踪器
    enemies = bridge.data.get_enemies() or []
    projectiles = bridge.data.get_projectiles() or {}
    tracker.update(frame, enemies, projectiles)
    
    # 获取玩家位置
    player_data = bridge.data.get_player_position()
    if not player_data:
        return
    
    player_pos = Position(
        player_data.get("pos", {}).get("x", 0),
        player_data.get("pos", {}).get("y", 0)
    )
    
    # 获取危险的投射物
    dangerous_projs = tracker.get_dangerous_projectiles(player_pos)
    
    if dangerous_projs:
        # 躲避最近的投射物
        nearest_proj = min(dangerous_projs, 
                          key=lambda p: p.pos.distance_to(player_pos))
        
        # 计算躲避方向
        dx = nearest_proj.pos.x - player_pos.x
        dy = nearest_proj.pos.y - player_pos.y
        dist = math.sqrt(dx*dx + dy*dy)
        
        if dist > 0:
            move_dir = (-dx/dist, -dy/dist)
            bridge.send_input(move_dir=move_dir)

bridge.start()
```

### 场景2：基于威胁分析的AI

```python
from isaac_bridge import IsaacBridge
from game_tracker import ObjectTracker, Position
from game_space import GameSpace, ThreatAnalyzer

bridge = IsaacBridge()
tracker = ObjectTracker()
space = GameSpace(grid_size=40.0)
analyzer = None

@bridge.on("data")
def on_data_update(data):
    global analyzer
    
    frame = bridge.state.frame
    room_index = bridge.state.room_index
    
    # 房间变化时初始化空间
    if room_index != space.room_index:
        room_info = bridge.data.get_room_info()
        room_layout = bridge.data.get_room_layout()
        if room_info and room_layout:
            space.initialize_from_room(room_info, room_layout)
            analyzer = ThreatAnalyzer(space, tracker)
    
    # 更新跟踪器和空间
    enemies = bridge.data.get_enemies() or []
    projectiles = bridge.data.get_projectiles() or {}
    tracker.update(frame, enemies, projectiles)
    
    player_data = bridge.data.get_player_position()
    if not player_data:
        return
    
    player_pos = Position(
        player_data.get("pos", {}).get("x", 0),
        player_data.get("pos", {}).get("y", 0)
    )
    
    space.update(player_pos, tracker)
    
    # 获取推荐行动
    if analyzer:
        recommendation = analyzer.get_recommended_action(player_pos)
        
        # 发送控制指令
        move_dir = recommendation["move_dir"]
        shoot_dir = recommendation["shoot_dir"]
        
        bridge.send_input(move_dir=move_dir, shoot_dir=shoot_dir)

bridge.start()
```

---

## 🔧 调试技巧

### 1. 查看跟踪器状态

```python
# 获取跟踪器统计
stats = tracker.get_stats()
print(f"活跃敌人: {stats['active_enemies']}")
print(f"击杀敌人: {stats['enemies_killed']}")

# 获取特定敌人
enemy = tracker.get_enemy_by_id(12345)
if enemy:
    print(f"敌人血量: {enemy.hp}/{enemy.max_hp}")
    print(f"移动模式: {enemy.movement_pattern}")
    print(f"存活帧数: {enemy.get_lifetime_frames()}")
```

### 2. 查看空间信息

```python
# 获取空间特征
features = space.get_space_features()
print(f"平均威胁: {features['avg_threat']:.3f}")
print(f"安全区域比例: {features['safe_cell_ratio']:.1%}")

# 获取威胁等级
threat_level = space.get_threat_at(player_pos)
print(f"当前威胁: {threat_level:.3f}")

# 获取最安全的位置
safest_cell = space.get_safest_cell_nearby(player_pos, max_distance=200.0)
if safest_cell:
    safest_pos = space._grid_to_world(safest_cell.x, safest_cell.y)
    print(f"最安全位置: ({safest_pos.x:.1f}, {safest_pos.y:.1f})")
```

### 3. 查看威胁分析

```python
# 分析玩家威胁
threat_info = analyzer.analyze_player_threat(player_pos)
print(f"威胁等级: {threat_info['threat_level']}")
print(f"最近敌人距离: {threat_info['nearest_enemy_distance']:.1f}")
print(f"危险投射物数量: {threat_info['dangerous_projectiles_count']}")

# 获取推荐行动
recommendation = analyzer.get_recommended_action(player_pos)
print(f"推荐行动: {recommendation['action']}")
print(f"移动方向: {recommendation['move_dir']}")
print(f"置信度: {recommendation['confidence']:.2f}")
```

---

## 📈 性能优化建议

### 1. 调整网格大小

```python
# 较大的网格 = 更快的计算，但精度较低
space = GameSpace(grid_size=60.0)

# 较小的网格 = 更高的精度，但计算更慢
space = GameSpace(grid_size=20.0)
```

### 2. 调整历史轨迹长度

```python
from collections import deque

# 减少历史轨迹长度以节省内存
enemy.position_history = deque(maxlen=30)
enemy.velocity_history = deque(maxlen=30)
```

### 3. 调整威胁分析频率

```python
# 不需要每帧都进行威胁分析
if frame % 3 == 0:  # 每3帧分析一次
    threat_info = analyzer.analyze_player_threat(player_pos)
```

---

## 🐛 常见问题

### Q1: 对象跟踪不准确

**A:** 检查 `max_missing_frames` 设置是否合适

```python
# 如果对象经常被误判为消失，增加这个值
tracker = ObjectTracker(max_missing_frames=60)
```

### Q2: 威胁分析不准确

**A:** 调整威胁源的威胁半径和强度

```python
# 在 game_space.py 中修改威胁源的参数
threat_radius = 200.0  # 增加威胁半径
threat_intensity = 0.8  # 增加威胁强度
```

### Q3: 路径规划失败

**A:** 检查 `max_threat` 参数是否过高

```python
# 降低最大允许威胁等级
path = space.find_path(start, goal, max_threat=0.7)
```

---

## 📚 进一步学习

1. **完整文档** - 查看 `TRACKING_SYSTEM.md` 了解详细API
2. **测试工具** - 运行 `test_tracker.py` 查看实时状态
3. **可视化工具** - 运行 `visualize_space.py` 查看空间可视化
4. **高级AI示例** - 查看 `advanced_ai_example.py` 了解完整实现

---

## 🎯 下一步

1. ✅ 运行测试工具，了解系统工作原理
2. ✅ 运行可视化工具，查看空间和威胁分布
3. ✅ 运行高级AI，观察AI决策过程
4. ✅ 根据需求调整参数，优化AI表现
5. ✅ 基于系统构建自己的AI逻辑

---

**祝您使用愉快！** 🎮

如有问题，请查看完整文档或提交Issue。
