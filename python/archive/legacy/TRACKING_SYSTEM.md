# 对象跟踪与空间感知系统文档

## 📋 概述

本系统为《以撒的结合：重生》游戏构建了一个完整的对象跟踪和空间感知框架，将实时流式数据转换为稳定的、可追踪的抽象模型，为AI智能体提供可靠的游戏空间感知能力。

### 核心价值

- **对象跟踪** - 识别并跟踪游戏中的实体（敌人、投射物等），维护完整的生命周期
- **历史轨迹** - 记录对象的位置和行为历史，支持行为模式分析
- **抽象空间** - 将连续的游戏空间转换为离散化的网格模型
- **威胁分析** - 实时分析空间中的威胁分布，为决策提供依据
- **智能决策** - 基于威胁分析提供移动和射击建议

---

## 🏗️ 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    游戏数据流                                 │
│                                                               │
│  实时数据 (每帧)                                              │
│  ├── PLAYER_POSITION (玩家位置)                               │
│  ├── ENEMIES (敌人列表)                                       │
│  ├── PROJECTILES (投射物列表)                                │
│  ├── ROOM_INFO (房间信息)                                     │
│  └── ROOM_LAYOUT (房间布局)                                   │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              ObjectTracker (对象跟踪器)                       │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  对象识别与跟踪                                        │   │
│  │  ├── Enemy (敌人对象)                                 │   │
│  │  │   ├── 位置跟踪                                     │   │
│  │  │   ├── 速度跟踪                                     │   │
│  │  │   ├── 生命周期管理                                 │   │
│  │  │   ├── 历史轨迹 (60帧)                              │   │
│  │  │   └── 行为模式分析                                 │   │
│  │  └── Projectile (投射物对象)                          │   │
│  │      ├── 位置跟踪                                     │   │
│  │      ├── 速度跟踪                                     │   │
│  │      ├── 威胁预测                                     │   │
│  │      └── 击中时间预测                                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  输出: 稳定的对象列表，每个对象包含完整的历史和状态            │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              GameSpace (游戏空间模型)                         │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  空间网格化                                            │   │
│  │  ├── 网格单元 (GridCell)                             │   │
│  │  │   ├── 类型 (空地/障碍物/门/危险)                   │   │
│  │  │   ├── 威胁等级 [0, 1]                              │   │
│  │  │   ├── 威胁源列表                                   │   │
│  │  │   └── 距离信息                                     │   │
│  │  └── 威胁源 (ThreatSource)                            │   │
│  │      ├── 位置                                         │   │
│  │      ├── 速度                                         │   │
│  │      ├── 威胁半径                                     │   │
│  │      └── 威胁强度                                     │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  输出: 离散化的空间模型，每个网格单元包含威胁信息              │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│           ThreatAnalyzer (威胁分析器)                        │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  威胁分析                                              │   │
│  │  ├── 玩家威胁评估                                     │   │
│  │  │   ├── 当前威胁等级                                 │   │
│  │  │   ├── 最近敌人距离                                 │   │
│  │  │   ├── 最近投射物距离                               │   │
│  │  │   └── 威胁向量计算                                 │   │
│  │  ├── 威胁分类 (critical/high/medium/low)              │   │
│  │  └── 推荐行动                                          │   │
│  │      ├── 移动方向                                     │   │
│  │      ├── 射击方向                                     │   │
│  │      └── 置信度                                       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  输出: 威胁分析结果和推荐行动                                 │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              AI决策层                                         │
│                                                               │
│  基于威胁分析结果，做出移动和射击决策                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 核心模块详解

### 1. game_tracker.py - 对象跟踪器

#### 1.1 核心类

**Position** - 位置信息
```python
@dataclass
class Position:
    x: float
    y: float
    
    def distance_to(self, other: Position) -> float
    def direction_to(self, other: Position) -> Tuple[float, float]
```

**Velocity** - 速度信息
```python
@dataclass
class Velocity:
    x: float
    y: float
    
    @property
    def magnitude(self) -> float
    
    @property
    def direction(self) -> Tuple[float, float]
```

**TrackedObject** - 被跟踪的对象基类
```python
@dataclass
class TrackedObject:
    id: int                      # 对象ID
    type: ObjectType             # 对象类型
    pos: Position                # 当前位置
    vel: Velocity                # 当前速度
    state: ObjectState           # 对象状态
    
    # 跟踪信息
    first_seen_frame: int        # 首次出现的帧
    last_seen_frame: int         # 最后出现的帧
    frames_not_seen: int        # 连续未看到的帧数
    
    # 历史轨迹（最多保存最近60帧）
    position_history: deque     # 位置历史
    velocity_history: deque     # 速度历史
    
    # 行为分析
    avg_velocity: Velocity       # 平均速度
    movement_pattern: str        # 移动模式
    
    def update(self, pos, vel, frame, **kwargs)
    def predict_position(self, frames_ahead: int) -> Position
    def get_lifetime_frames(self) -> int
    def is_alive(self) -> bool
```

**Enemy** - 敌人对象
```python
@dataclass
class Enemy(TrackedObject):
    state: int                   # 游戏内状态
    state_frame: int             # 当前状态持续帧数
    projectile_cooldown: int     # 投射物冷却
    projectile_delay: int        # 投射物发射间隔
    
    # 行为分析
    last_attack_frame: int       # 最后攻击帧
    attack_pattern: List[int]    # 攻击间隔历史
    
    def can_attack(self, current_frame: int) -> bool
    def record_attack(self, frame: int)
    def get_avg_attack_interval(self) -> float
```

**Projectile** - 投射物对象
```python
@dataclass
class Projectile(TrackedObject):
    variant: int
    collision_radius: float
    height: float
    is_enemy: bool
    
    def predict_impact_time(self, target_pos: Position) -> Optional[int]
```

**ObjectTracker** - 对象跟踪器核心类
```python
class ObjectTracker:
    def __init__(self, max_missing_frames: int = 30)
    
    def update(self, frame: int, enemies_data: List[dict], 
               projectiles_data: dict)
    
    def get_active_enemies(self) -> List[Enemy]
    def get_enemy_by_id(self, enemy_id: int) -> Optional[Enemy]
    def get_nearest_enemy(self, pos: Position) -> Optional[Enemy]
    def get_enemy_projectiles(self) -> List[Projectile]
    def get_dangerous_projectiles(self, pos: Position, 
                                   max_distance: float = 200.0) -> List[Projectile]
    def get_stats(self) -> Dict[str, Any]
```

#### 1.2 工作原理

**对象识别与跟踪**
1. 每帧接收敌人和投射物数据
2. 根据对象ID识别新对象或更新现有对象
3. 记录位置和速度历史
4. 分析移动模式（stationary/chasing/erratic）
5. 检测对象死亡（HP <= 0）

**生命周期管理**
1. 对象首次出现时记录 `first_seen_frame`
2. 每帧更新 `last_seen_frame`
3. 如果对象连续 `max_missing_frames` 帧未出现，标记为消失
4. 维护对象从出现到消失的完整生命周期

**行为模式分析**
- **stationary** - 速度方差 < 0.5（几乎不动）
- **chasing** - 速度方差 0.5-3.0（正常移动）
- **erratic** - 速度方差 > 3.0（快速变化）

---

### 2. game_space.py - 游戏空间模型

#### 2.1 核心类

**GridCell** - 网格单元
```python
@dataclass
class GridCell:
    x: int                      # 网格X坐标
    y: int                      # 网格Y坐标
    cell_type: CellType         # 单元类型
    
    # 威胁信息
    threat_level: float         # 威胁等级 [0, 1]
    threat_sources: List[int]    # 威胁源对象ID列表
    
    # 距离信息
    distance_to_player: float
    distance_to_nearest_enemy: float
    
    # 路径规划
    path_cost: float
    parent: Optional[Tuple[int, int]]
    
    def is_walkable(self) -> bool
    def is_safe(self, threshold: float = 0.3) -> bool
```

**ThreatSource** - 威胁源
```python
@dataclass
class ThreatSource:
    obj_id: int
    position: Position
    velocity: Velocity
    threat_type: str            # "enemy", "projectile", "laser"
    threat_radius: float
    threat_intensity: float     # 威胁强度 [0, 1]
    
    def get_threat_at(self, pos: Position) -> float
```

**GameSpace** - 游戏空间模型
```python
class GameSpace:
    def __init__(self, grid_size: float = 40.0)
    
    def initialize_from_room(self, room_info: dict, room_layout: dict)
    def update(self, player_pos: Position, tracker: ObjectTracker)
    
    def get_cell(self, world_pos: Position) -> Optional[GridCell]
    def get_safe_cells(self, threshold: float = 0.3) -> List[GridCell]
    def get_safest_cell_nearby(self, world_pos: Position, 
                                max_distance: float = 200.0) -> Optional[GridCell]
    def find_path(self, start: Position, goal: Position, 
                   max_threat: float = 0.5) -> Optional[List[Position]]
    def get_threat_at(self, pos: Position) -> float
    def get_space_features(self) -> Dict[str, Any]
```

**ThreatAnalyzer** - 威胁分析器
```python
class ThreatAnalyzer:
    def __init__(self, space: GameSpace, tracker: ObjectTracker)
    
    def analyze_player_threat(self, player_pos: Position) -> Dict[str, Any]
    def get_recommended_action(self, player_pos: Position) -> Dict[str, Any]
```

#### 2.2 工作原理

**空间网格化**
1. 根据房间边界创建网格
2. 标记障碍物、门、危险区域
3. 每个网格单元保存威胁等级和距离信息

**威胁场计算**
1. 从跟踪器获取所有威胁源（敌人、投射物）
2. 为每个威胁源设置威胁半径和强度
3. 计算每个网格单元的威胁值（随距离衰减）
4. 累加所有威胁源的威胁值

**威胁等级分类**
- **critical** - 威胁 > 0.7 或 投射物距离 < 50
- **high** - 威胁 > 0.4 或 敌人距离 < 100
- **medium** - 威胁 > 0.2 或 敌人距离 < 200
- **low** - 其他情况

**推荐行动**
- **evade** - 紧急躲避（critical威胁）
- **cautious_move** - 谨慎移动（high威胁）
- **tactical_move** - 战术移动（medium威胁）
- **free_move** - 自由移动（low威胁）

---

### 3. advanced_ai_example.py - 高级AI示例

#### 3.1 核心类

**AdvancedAI** - 高级AI控制器
```python
class AdvancedAI:
    def __init__(self, bridge: IsaacBridge)
    
    def update(self) -> Tuple[Tuple[int, int], Tuple[int, int]]
    def get_tracked_objects_info(self) -> Dict[str, Any]
    def get_space_info(self) -> Dict[str, Any]
    def get_threat_info(self) -> Optional[Dict[str, Any]]
    def get_stats(self) -> Dict[str, Any]
```

#### 3.2 工作流程

1. **数据更新** - 每帧接收游戏数据，更新跟踪器和空间模型
2. **房间变化** - 检测房间变化，初始化新的空间模型
3. **威胁分析** - 分析玩家面临的威胁
4. **决策制定** - 根据威胁等级制定移动和射击策略
5. **指令发送** - 将决策转换为游戏指令发送

---

## 🚀 快速开始

### 基本使用

#### 1. 使用对象跟踪器

```python
from isaac_bridge import IsaacBridge, GameDataAccessor
from game_tracker import ObjectTracker, Position

# 创建桥接和跟踪器
bridge = IsaacBridge()
tracker = ObjectTracker(max_missing_frames=30)

# 启动桥接
bridge.start()

# 在数据回调中更新跟踪器
@bridge.on("data")
def on_data_update(data):
    frame = bridge.state.frame
    
    # 获取敌人和投射物数据
    enemies = bridge.data.get_enemies() or []
    projectiles = bridge.data.get_projectiles() or {}
    
    # 更新跟踪器
    tracker.update(frame, enemies, projectiles)
    
    # 获取活跃敌人
    active_enemies = tracker.get_active_enemies()
    print(f"Active enemies: {len(active_enemies)}")
    
    # 获取最近的敌人
    player_pos = Position(100, 200)
    nearest_enemy = tracker.get_nearest_enemy(player_pos)
    if nearest_enemy:
        print(f"Nearest enemy: ID={nearest_enemy.id}, "
              f"distance={nearest_enemy.pos.distance_to(player_pos):.1f}")
```

#### 2. 使用空间模型

```python
from game_space import GameSpace, ThreatAnalyzer

# 创建空间模型
space = GameSpace(grid_size=40.0)

# 初始化空间（在房间变化时）
room_info = bridge.data.get_room_info()
room_layout = bridge.data.get_room_layout()
if room_info and room_layout:
    space.initialize_from_room(room_info, room_layout)

# 更新空间（每帧）
player_pos = Position(100, 200)
space.update(player_pos, tracker)

# 获取威胁等级
threat_level = space.get_threat_at(player_pos)
print(f"Current threat level: {threat_level:.2f}")

# 获取附近最安全的位置
safest_cell = space.get_safest_cell_nearby(player_pos, max_distance=200.0)
if safest_cell:
    safest_pos = space._grid_to_world(safest_cell.x, safest_cell.y)
    print(f"Safest position: ({safest_pos.x:.1f}, {safest_pos.y:.1f})")
```

#### 3. 使用威胁分析器

```python
# 创建威胁分析器
analyzer = ThreatAnalyzer(space, tracker)

# 分析玩家威胁
threat_info = analyzer.analyze_player_threat(player_pos)
print(f"Threat level: {threat_info['threat_level']}")
print(f"Current threat: {threat_info['current_threat']:.2f}")
print(f"Nearest enemy distance: {threat_info['nearest_enemy_distance']:.1f}")

# 获取推荐行动
recommendation = analyzer.get_recommended_action(player_pos)
print(f"Recommended action: {recommendation['action']}")
print(f"Move direction: {recommendation['move_dir']}")
print(f"Shoot direction: {recommendation['shoot_dir']}")
print(f"Confidence: {recommendation['confidence']:.2f}")
```

#### 4. 使用高级AI

```python
from advanced_ai_example import AdvancedAI

# 创建高级AI
ai = AdvancedAI(bridge)

# 主循环
while True:
    # 获取AI决策
    move_dir, shoot_dir = ai.update()
    
    # 发送控制指令
    if move_dir != (0, 0) or shoot_dir != (0, 0):
        bridge.send_input(move_dir=move_dir, shoot_dir=shoot_dir)
    
    # 每60帧输出一次状态
    if bridge.state.frame % 60 == 0:
        print(f"Frame {bridge.state.frame}")
        print(f"Enemies: {len(ai.tracker.get_active_enemies())}")
        print(f"Projectiles: {len(ai.tracker.get_enemy_projectiles())}")
        
        # 输出威胁信息
        threat_info = ai.get_threat_info()
        if threat_info:
            print(f"Threat: {threat_info['threat_level']}")
    
    time.sleep(0.016)  # ~60 FPS
```

---

## 🧪 测试工具

### test_tracker.py - 跟踪器测试工具

```bash
cd python
python test_tracker.py
```

**功能：**
- 实时显示跟踪器状态
- 显示活跃敌人详情
- 显示空间特征和威胁分析
- 显示推荐行动
- 导出跟踪数据到JSON

**输出示例：**
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

空间特征:
  平均威胁: 0.234
  最大威胁: 0.678
  安全区域比例: 65.2%
  威胁源数量: 13

玩家威胁分析:
  当前威胁等级: 0.345
  威胁分类: medium
  最近敌人距离: 150.0
  最近投射物距离: 80.0
  危险投射物数量: 3

推荐行动:
  行动类型: tactical_move
  移动方向: (-0.71, 0.71)
  射击方向: (0.82, -0.57)
  置信度: 0.60
```

---

## 📊 数据结构

### 敌人对象数据结构

```json
{
  "id": 12345,
  "type": 10,
  "variant": 0,
  "subtype": 0,
  "pos": {"x": 300.0, "y": 200.0},
  "vel": {"x": 0.5, "y": 0.0},
  "hp": 20.0,
  "max_hp": 20.0,
  "is_boss": false,
  "is_champion": false,
  "state": 3,
  "state_frame": 10,
  "projectile_cooldown": 30,
  "projectile_delay": 60,
  "collision_radius": 15.0,
  "distance": 250.0,
  "target_pos": {"x": 100.0, "y": 200.0},
  "v1": {"x": 0.0, "y": 0.0},
  "v2": {"x": 0.0, "y": 0.0}
}
```

### 投射物对象数据结构

```json
{
  "id": 67890,
  "pos": {"x": 250.0, "y": 180.0},
  "vel": {"x": -2.0, "y": 0.0},
  "variant": 0,
  "collision_radius": 8.0,
  "height": 0.0,
  "falling_speed": 0.0,
  "falling_accel": 0.0
}
```

### 威胁分析结果数据结构

```json
{
  "current_threat": 0.345,
  "nearest_enemy_distance": 150.0,
  "nearest_projectile_distance": 80.0,
  "dangerous_projectiles_count": 3,
  "safest_position": [120.0, 180.0],
  "safest_threat": 0.123,
  "threat_vector": [0.71, -0.71],
  "threat_level": "medium"
}
```

### 推荐行动数据结构

```json
{
  "action": "tactical_move",
  "move_dir": [-0.71, 0.71],
  "shoot_dir": [0.82, -0.57],
  "threat_level": "medium",
  "confidence": 0.60
}
```

---

## 🔧 高级功能

### 1. 自定义威胁源

```python
from game_space import ThreatSource, Position, Velocity

# 添加自定义威胁源
custom_threat = ThreatSource(
    obj_id=99999,
    position=Position(300, 200),
    velocity=Velocity(0, 0),
    threat_type="custom",
    threat_radius=150.0,
    threat_intensity=0.8
)

space.threat_sources.append(custom_threat)
space._compute_threat_field()
```

### 2. 路径规划

```python
# 使用A*算法寻找路径
start_pos = Position(100, 200)
goal_pos = Position(400, 300)

path = space.find_path(start_pos, goal_pos, max_threat=0.5)

if path:
    print(f"Path found with {len(path)} steps")
    for i, pos in enumerate(path):
        print(f"  Step {i}: ({pos.x:.1f}, {pos.y:.1f})")
else:
    print("No path found")
```

### 3. 行为模式分析

```python
# 获取敌人的移动模式
enemy = tracker.get_enemy_by_id(12345)
print(f"Movement pattern: {enemy.movement_pattern}")

# 获取敌人的攻击模式
if hasattr(enemy, 'attack_pattern') and enemy.attack_pattern:
    avg_interval = enemy.get_avg_attack_interval()
    print(f"Average attack interval: {avg_interval:.1f} frames")
    print(f"Attack count: {len(enemy.attack_pattern)}")
```

### 4. 历史轨迹分析

```python
# 获取敌人的位置历史
enemy = tracker.get_enemy_by_id(12345)
print(f"Position history (last 60 frames):")
for i, pos in enumerate(enemy.position_history):
    print(f"  Frame {i}: ({pos.x:.1f}, {pos.y:.1f})")

# 预测未来位置
future_pos = enemy.predict_position(frames_ahead=10)
print(f"Predicted position in 10 frames: ({future_pos.x:.1f}, {future_pos.y:.1f})")
```

---

## 📈 性能优化

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

## 🐛 故障排除

### 常见问题

1. **对象跟踪不准确**
   - 检查 `max_missing_frames` 设置是否合适
   - 确认游戏数据更新频率是否正常

2. **威胁分析不准确**
   - 调整威胁源的威胁半径和强度
   - 检查网格大小是否合适

3. **路径规划失败**
   - 检查 `max_threat` 参数是否过高
   - 确认起点和终点是否在可通行区域

---

## 📝 开发路线图

### 已完成 ✅

- ✅ 对象跟踪系统
- ✅ 生命周期管理
- ✅ 历史轨迹记录
- ✅ 行为模式分析
- ✅ 空间网格化
- ✅ 威胁场计算
- ✅ 威胁分析器
- ✅ 路径规划（A*算法）
- ✅ 高级AI示例
- ✅ 测试工具

### 计划中 🚧

- [ ] 可视化工具（实时显示空间和威胁）
- [ ] 更多行为模式识别
- [ ] 强化学习集成
- [ ] 多玩家支持
- [ ] 性能优化

---

## 📄 许可证

本项目仅供学习和研究使用。

---

**最后更新：** 2026年1月7日
**版本：** 1.0
