# 对象跟踪系统文档

## 📋 概述

本系统为《以撒的结合：重生》游戏提供对象跟踪能力，将实时流式数据转换为稳定的、可追踪的抽象模型。

### 核心特性

- **唯一标识符** - 使用 `entity.Index` 作为唯一标识符，每个房间内的实体都有独立ID
- **同类型多敌人支持** - 同一房间可以同时跟踪多个同类型敌人（如多只苍蝇）
- **生命周期管理** - 维护对象从出现到消失/死亡的完整生命周期
- **历史轨迹记录** - 记录位置和速度历史（最多60帧）
- **行为模式分析** - 分析敌人移动模式（stationary/chasing/erratic）

---

## 📦 核心模块

### game_tracker.py - 对象跟踪器

#### 核心类

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
    id: int                      # entity.Index (唯一标识符)
    type: ObjectType             # 对象类型
    pos: Position                # 当前位置
    vel: Velocity                # 当前速度
    state: ObjectState           # 对象状态
    
    # 对象属性
    obj_type: int = 0            # 游戏内类型 (EntityType)
    variant: int = 0             # 变体
    hp: float = 0.0              # 当前生命值
    max_hp: float = 0.0          # 最大生命值
    is_boss: bool = False        # 是否为Boss
    
    # 跟踪信息
    first_seen_frame: int        # 首次出现的帧
    last_seen_frame: int         # 最后出现的帧
    frames_not_seen: int        # 连续未看到的帧数
    
    # 历史轨迹（最多保存最近60帧）
    position_history: deque      # 位置历史
    velocity_history: deque      # 速度历史
    
    # 行为分析
    avg_velocity: Velocity       # 平均速度
    movement_pattern: str        # 移动模式
    
    def update(self, pos, vel, frame, **kwargs)
    def predict_position(self, frames_ahead: int) -> Position
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
    collision_radius: float      # 碰撞半径
    
    # 行为分析
    last_attack_frame: int       # 最后攻击帧
    attack_pattern: List[int]    # 攻击间隔历史
    
    def can_attack(self, current_frame: int) -> bool
    def get_avg_attack_interval(self) -> float
```

**Projectile** - 投射物对象
```python
@dataclass
class Projectile(TrackedObject):
    variant: int
    collision_radius: float
    height: float
    is_enemy: bool               # 是否为敌方投射物
    
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

#### 工作原理

**对象识别与跟踪**
1. 每帧接收敌人和投射物数据
2. 根据 `entity.Index` 识别新对象或更新现有对象
3. 记录位置和速度历史
4. 分析移动模式（stationary/chasing/erratic）
5. 检测对象死亡（HP <= 0）

**生命周期管理**
1. 对象首次出现时记录 `first_seen_frame`
2. 每帧更新 `last_seen_frame`
3. 如果对象连续 `max_missing_frames` 帧未出现，标记为消失
4. 维护对象从出现到消失的完整生命周期

**移动模式分析**
- **stationary** - 速度方差 < 0.5（几乎不动）
- **chasing** - 速度方差 0.5-3.0（正常移动）
- **erratic** - 速度方差 > 3.0（快速变化或非线性运动）

---

## 🚀 快速开始

### 基本使用

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
    player_data = bridge.data.get_player_position()
    if player_data:
        player_pos = Position(
            player_data.get("x", 0),
            player_data.get("y", 0)
        )
        nearest_enemy = tracker.get_nearest_enemy(player_pos)
        if nearest_enemy:
            dist = nearest_enemy.pos.distance_to(player_pos)
            print(f"Nearest enemy: ID={nearest_enemy.id}, "
                  f"distance={dist:.1f}, pattern={nearest_enemy.movement_pattern}")
```

### 高级用法

```python
# 获取特定敌人
enemy = tracker.get_enemy_by_id(12345)
if enemy:
    print(f"Enemy HP: {enemy.hp}/{enemy.max_hp}")
    print(f"Movement pattern: {enemy.movement_pattern}")
    print(f"Position history: {len(enemy.position_history)} frames")

# 获取危险投射物（朝向玩家且距离近）
player_pos = Position(100, 200)
dangerous = tracker.get_dangerous_projectiles(player_pos, max_distance=200.0)
print(f"Dangerous projectiles: {len(dangerous)}")

# 获取统计数据
stats = tracker.get_stats()
print(f"Total enemies seen: {stats['total_enemies_seen']}")
print(f"Enemies killed: {stats['enemies_killed']}")
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
  "target_pos": {"x": 100.0, "y": 200.0}
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
  "height": 0.0
}
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
- 显示统计数据
- 导出跟踪数据到JSON

**输出示例：**
```
============================================================
帧数: 1234
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

---

## ⚠️ 注意事项

### 关于 entity.Index

- `entity.Index` 是游戏内每个实体的唯一标识符
- 在**同一房间内**可以唯一标识每个敌人
- 离开房间后 Index 可能会被重用（新房间重新从0开始）

### 关于非线性运动敌人

对于传送、钻地等非线性运动的敌人：
- 速度预测功能可能不准确
- 移动模式分析可能输出 "erratic"
- 建议仅使用最后已知位置，不依赖轨迹预测

### 关于母体敌人

母体生成的子敌人会获得新的 `entity.Index`：
- 跟踪器会将其识别为新敌人
- 不会与母体混淆

---

## 📝 开发路线图

### 已完成 ✅

- ✅ 对象跟踪系统
- ✅ 生命周期管理
- ✅ 历史轨迹记录
- ✅ 行为模式分析
- ✅ 唯一实体标识（entity.Index）

### 计划中 🚧

- [ ] 改进非线性运动敌人的跟踪
- [ ] 攻击模式预测
- [ ] 性能优化

---

**最后更新：** 2026年1月7日
**版本：** 2.0
