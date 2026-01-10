# SocketBridge AI Combat System Documentation

## 目录

1. [系统概述](#系统概述)
2. [架构设计](#架构设计)
3. [模块详解](#模块详解)
4. [快速开始](#快速开始)
5. [API 参考](#api-参考)
6. [配置指南](#配置指南)
7. [示例代码](#示例代码)
8. [故障排除](#故障排除)

---

## 系统概述

SocketBridge AI Combat System 是一个为《以撒的结合：重生》游戏开发的完整 AI 控制框架。通过 TCP 套接字实现游戏与 Python 之间的实时数据交换，支持多层次的 AI 决策系统。

### 核心特性

- **实时数据采集**: 高频/中频/低频/变化时四种采集模式
- **双向通信**: 游戏数据实时传输，Python 发送控制指令
- **分层 AI 架构**: 4 阶段渐进式设计
- **模块化设计**: 各模块可独立使用或组合
- **Windows 兼容**: 完整跨平台支持

### 版本信息

- **当前版本**: 2.0
- **Python 要求**: 3.8+
- **依赖**: 仅标准库（无需 pip 安装）

---

## 架构设计

### 整体架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    The Binding of Isaac                      │
│                      (游戏进程)                               │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              main.lua (游戏模组)                       │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │   │
│  │  │   Collector   │  │   Network    │  │   Event    │ │   │
│  │  │   Registry    │  │   Layer      │  │   System   │ │   │
│  │  └──────────────┘  └──────────────┘  └────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          │ TCP Socket (127.0.0.1:9527)      │
│                          ▼                                   │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                    Python 进程                               │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              isaac_bridge.py (核心桥接)               │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ │   │
│  │  │   Network    │  │   GameState  │  │   Event    │ │   │
│  │  │   Server     │  │   Manager    │  │   System   │ │   │
│  │  └──────────────┘  └──────────────┘  └────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                          │                                   │
│          ┌───────────────┼───────────────┐                  │
│          ▼               ▼               ▼                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │orchestrator_ │ │data_recorder │ │     AI       │        │
│  │ enhanced.py  │ │   .py        │ │  Examples    │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### AI 决策层次

```
┌─────────────────────────────────────────────────┐
│           战略层 (Phase 3-4)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────┐  │
│  │  Strategy   │  │  Behavior   │  │Adaptive │  │
│  │  System     │  │  Tree       │  │  System │  │
│  └─────────────┘  └─────────────┘  └─────────┘  │
├─────────────────────────────────────────────────┤
│           战术层 (Phase 2-3)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────┐  │
│  │   Threat    │  │ State       │  │Strategy │  │
│  │  Analysis   │  │  Machine    │  │ Evaluation│ │
│  └─────────────┘  └─────────────┘  └─────────┘  │
├─────────────────────────────────────────────────┤
│           执行层 (Phase 1-2)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────┐  │
│  │   Basic     │  │ Pathfinding │  │  Smart  │  │
│  │ Controllers │  │             │  │  Aiming │  │
│  └─────────────┘  └─────────────┘  └─────────┘  │
├─────────────────────────────────────────────────┤
│           基础层 (Phase 1)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────┐  │
│  │    Data     │  │ Environment │  │Advanced │  │
│  │  Processor  │  │   Model     │  │ Control │  │
│  └─────────────┘  └─────────────┘  └─────────┘  │
└─────────────────────────────────────────────────┘
```

---

## 模块详解

### 核心模块

#### 1. isaac_bridge.py - 核心桥接器

负责与游戏建立 TCP 连接，接收数据并发送控制指令。

**主要类**:

| 类名 | 说明 |
|------|------|
| `IsaacBridge` | 主桥接类，管理连接和通信 |
| `GameState` | 游戏状态容器 |
| `GameDataAccessor` | 便捷数据访问接口 |

**核心方法**:

```python
class IsaacBridge:
    def start(self)           # 启动服务器
    def stop(self)            # 停止服务器
    def send_input(self, ...) # 发送输入指令
    def send_command(self, ...)  # 发送系统命令
    def on(self, event: str)  # 注册事件处理器
```

**使用示例**:

```python
from isaac_bridge import IsaacBridge, GameDataAccessor

bridge = IsaacBridge(host="127.0.0.1", port=9527)
data = GameDataAccessor(bridge)

@bridge.on("data:PLAYER_POSITION")
def on_position(pos):
    print(f"Player at: {pos}")

bridge.start()
```

---

#### 2. orchestrator_enhanced.py - AI 主控器 (增强版)

整合所有 Phase 1-4 模块的完整 AI 控制框架。

**主要类**:

| 类名 | 说明 |
|------|------|
| `EnhancedCombatOrchestrator` | 增强版主控器 |
| `CombatOrchestrator` | 原始主控器（向后兼容） |
| `SimpleAI` | 简单 AI 包装器 |

**增强版特性**:

- ✅ 分层状态机集成
- ✅ 策略系统集成
- ✅ 行为树集成
- ✅ 自适应参数系统
- ✅ 智能瞄准系统
- ✅ 高级运动控制

**配置选项**:

```python
@dataclass
class AIConfig:
    decision_interval: float = 0.05       # 决策间隔 (50ms)
    immediate_threat_threshold: float = 0.5  # 威胁阈值
    combat_engage_distance: float = 300.0 # 战斗距离
    retreat_health_threshold: float = 0.3 # 撤退血量
    
    attack_aggression: float = 0.7        # 攻击倾向 (0-1)
    defense_preference: float = 0.5       # 防御倾向 (0-1)
    movement_style: str = "kiting"        # 移动风格
    
    enable_pathfinding: bool = True       # 启用路径规划
    enable_threat_analysis: bool = True   # 启用威胁分析
    enable_behavior_tree: bool = True     # 启用行为树
    enable_advanced_control: bool = True  # 启用高级控制
    enable_adaptive_behavior: bool = True # 启用自适应系统
```

---

### Phase 1: 基础模块

#### data_processor.py - 数据处理器

解析游戏原始数据，转换为统一格式。

```python
from data_processor import DataProcessor

processor = DataProcessor()

# 处理游戏消息
game_state = processor.process_message(raw_message)

# 获取玩家
player = game_state.get_primary_player()

# 获取敌人
enemies = game_state.get_active_enemies()
```

#### environment.py - 环境模型

管理游戏环境信息，包括房间布局、障碍物、安全位置等。

```python
from environment import EnvironmentModel, GameMap

env = EnvironmentModel()

# 更新房间信息
env.update_room(layout, info, enemies, projectiles)

# 获取安全位置
safe_spot = env.get_safe_spot(player.position, min_distance=50, max_distance=200)

# 搜索路径
path = env.find_path(start, goal)
```

#### basic_controllers.py - 基础控制器

处理移动、射击、攻击等基础控制。

```python
from basic_controllers import BasicControllerManager, ControlOutput

controllers = BasicControllerManager()

# 计算控制输出
control = controllers.compute_control(
    game_state,
    target_enemy=enemy,
    evade_threats=[projectile1, projectile2],
    shoot_override=(1.0, 0.0),  # 可选：覆盖射击方向
)
```

---

### Phase 2: 分析模块

#### pathfinding.py - 路径规划

A* 算法实现，支持动态障碍物避让。

```python
from pathfinding import DynamicPathPlanner, PathExecutor

planner = DynamicPathPlanner()
executor = PathExecutor(planner)

# 规划路径
path = planner.plan_path(start, goal, obstacles)

# 执行路径
move = executor.execute_to(current_pos, target_pos)
```

#### threat_analysis.py - 威胁分析

分析敌人和投射物的威胁等级。

```python
from threat_analysis import ThreatAnalyzer, ThreatLevel

analyzer = ThreatAnalyzer()

# 分析威胁
assessment = analyzer.analyze(
    player_position,
    enemies,
    enemy_projectiles,
    current_frame=frame,
)

# 获取威胁等级
if assessment.overall_threat_level == ThreatLevel.CRITICAL:
    print("紧急躲避!")
```

---

### Phase 3: 决策模块

#### state_machine.py - 状态机

分层状态机管理系统。

```python
from state_machine import (
    HierarchicalStateMachine,
    BattleState,
    MovementState,
    StateMachineConfig,
)

config = StateMachineConfig()
hsm = HierarchicalStateMachine(config)

# 更新状态机
states = hsm.update(
    threat_level=0.5,
    player_health=0.7,
    enemy_count=3,
    has_projectiles=True,
    can_heal=True,
)

print(f"Battle: {states['battle']}")      # BattleState.DEFENSIVE
print(f"Movement: {states['movement']}")  # MovementState.FLEEING
```

**状态类型**:

| 状态机 | 状态值 |
|--------|--------|
| BattleState | IDLE, AGGRESSIVE, DEFENSIVE, DODGE, RETREAT, HEAL_PRIORITY |
| MovementState | EXPLORING, CHASING, FLEEING, POSITIONING, STATIONARY |
| SpecialState | NONE, USING_ITEM, INTERACTING, CHARGING, BOMBING |

#### strategy_system.py - 策略系统

多策略评估和选择系统。

```python
from strategy_system import StrategyManager, StrategyType, GameContext

manager = StrategyManager()

# 构建游戏上下文
context = GameContext(
    player_health=0.7,
    enemy_count=3,
    nearest_enemy_distance=200,
    highest_threat_level=0.3,
    in_combat=True,
)

# 决策并执行
strategy, result = manager.decide_and_execute(context)

print(f"Selected: {strategy.value}")  # "aggressive"
print(f"Utility: {result.utility_score:.2f}")  # 0.85
```

**策略类型**:

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| AGGRESSIVE | 高攻击性 | 敌人少、血量高 |
| DEFENSIVE | 防御优先 | 敌人多、血量中 |
| BALANCED | 攻守平衡 | 一般情况 |
| EVASIVE | 闪避优先 | 投射物多、血量低 |
| HEALING | 治疗优先 | 需要回血 |

#### behavior_tree.py - 行为树

基于优先级行为树的高级决策。

```python
from behavior_tree import CombatBehaviorTree, NodeContext

# 创建战斗行为树
bt = CombatBehaviorTree.create_combat_tree()

# 构建上下文
context = NodeContext(
    player_health=0.7,
    player_position=(400, 300),
    enemies=[enemy1, enemy2],
    threat_level=0.3,
    projectiles=[proj1],
)

# 执行
result = bt.execute(context)

print(f"Action: {bt.get_last_action()}")  # "attack"
```

**行为树优先级**:

1. 紧急躲避（投射物）
2. 低血量治疗
3. 战斗逻辑
4. 移动到有利位置

---

### Phase 4: 高级控制模块

#### advanced_control.py - 高级控制

PID 控制器和轨迹优化。

```python
from advanced_control import (
    AdvancedMovementController,
    TrajectoryOptimizer,
    PIDConfig,
)

# 初始化控制器
movement = AdvancedMovementController(
    position_pid=PIDConfig(kp=0.8, ki=0.05, kd=0.3),
)

# 设置目标
movement.set_target(
    position=(500, 400),
    velocity=(0, 0),
)

# 更新控制
control = movement.update(
    current_pos=(400, 300),
    current_vel=(1, 0),
    dt=0.016,
)

# 生成轨迹
trajectory = TrajectoryOptimizer().generate_trajectory(
    start=(400, 300),
    waypoints=[(450, 350), (500, 400)],
    speed=5.0,
)
```

#### smart_aiming.py - 智能瞄准

目标预测和提前量计算。

```python
from smart_aiming import SmartAimingSystem

aiming = SmartAimingSystem()

# 计算瞄准方向（带预测）
aim_dir = aiming.aim(
    shooter_pos=(400, 300),
    target_pos=(450, 320),
    target_vel=(1.0, 0.5),
    enemy_type=10,
)

# 记录命中结果
aiming.record_hit(True)   # 命中
aiming.record_hit(False)  # 未命中

# 获取命中率
accuracy = aiming.get_accuracy()  # 0.67
```

**特性**:

- 目标位置预测
- 提前量射击计算
- 自适应命中率调整
- 多种射击模式（normal, spread, burst, precise）

#### adaptive_system.py - 自适应系统

场景识别和动态参数调整。

```python
from adaptive_system import AdaptiveParameterSystem, ScenarioType

adaptive = AdaptiveParameterSystem()

# 更新系统
config = adaptive.update(
    game_state={
        "enemies": [{"is_boss": True}],
        "room_info": {"grid_width": 13, "grid_height": 7},
    },
    performance_metrics={
        "hit_rate": 0.4,
        "dodge_rate": 0.6,
        "damage_taken": 1.0,
    },
)

print(f"Scenario: {adaptive.detector.current_scenario.value}")  # "boss_fight"
print(f"Aggression: {config.aggression}")  # 0.6
print(f"Caution: {config.caution}")  # 0.7
```

**场景类型**:

| 场景 | 说明 |
|------|------|
| BOSS_FIGHT | Boss 战 |
| SWARM | 大量敌人 |
| ONE_VS_ONE | 1v1 对战 |
| NARROW_SPACE | 狭窄空间 |
| OPEN_SPACE | 开阔空间 |
| HAZARDOUS | 危险环境 |

---

## 快速开始

### 1. 环境准备

```bash
# 克隆或下载项目
cd SocketBridge/python

# 运行兼容性测试（可选但推荐）
python test_windows_compatibility.py
```

### 2. 启动服务器

```python
# isaac_bridge.py
from isaac_bridge import IsaacBridge

bridge = IsaacBridge(host="127.0.0.1", port=9527)
bridge.start()
```

### 3. 集成 AI

#### 简单模式

```python
from orchestrator_enhanced import SimpleAI

ai = SimpleAI(use_enhanced=True)
ai.connect()

while True:
    # 获取游戏数据
    move, shoot = ai.update(game_data)
    
    # 执行控制
    bridge.send_input(move=move, shoot=shoot)
```

#### 高级模式

```python
from orchestrator_enhanced import EnhancedCombatOrchestrator, AIConfig

config = AIConfig(
    enable_behavior_tree=True,
    enable_advanced_control=True,
    enable_adaptive_behavior=True,
    attack_aggression=0.8,
    movement_style="aggressive",
)

orchestrator = EnhancedCombatOrchestrator(config)
orchestrator.initialize()

# 每帧更新
control = orchestrator.update(raw_message)
```

---

## API 参考

### IsaacBridge

```python
class IsaacBridge:
    def __init__(self, host: str = "127.0.0.1", port: int = 9527)
    
    def start(self) -> None
    def stop(self) -> None
    
    def send_input(
        self,
        move: Tuple[int, int] = None,
        shoot: Tuple[int, int] = None,
        use_item: bool = None,
        use_bomb: bool = None,
        use_card: bool = None,
        use_pill: bool = None,
        drop: bool = None,
    ) -> bool
    
    def send_command(self, command: str, params: dict = None) -> bool
    def on(self, event: str) -> Callable
    def is_connected(self) -> bool
    def get_stats(self) -> dict
```

### EnhancedCombatOrchestrator

```python
class EnhancedCombatOrchestrator:
    def __init__(self, config: AIConfig = None)
    
    def initialize(self) -> None
    def update(self, raw_message: Dict[str, Any]) -> ControlOutput
    def enable(self) -> None
    def disable(self) -> None
    def reset(self) -> None
    
    def set_aggression(self, level: float) -> None
    def set_movement_style(self, style: str) -> None
    
    def on_player_damage(self, damage: int, hp_after: int) -> None
    def on_enemy_killed(self, enemy: EnemyData) -> None
    def on_room_entered(self, room_info: RoomInfo) -> None
    def on_room_cleared(self) -> None
    
    def get_performance_stats(self) -> Dict[str, Any]
```

### ControlOutput

```python
@dataclass
class ControlOutput:
    move_x: int = 0          # X 方向移动 (-1, 0, 1)
    move_y: int = 0          # Y 方向移动 (-1, 0, 1)
    shoot: bool = False      # 是否射击
    shoot_x: int = 0         # 射击方向 X
    shoot_y: int = 0         # 射击方向 Y
    use_item: bool = False   # 使用主动道具
    use_bomb: bool = False   # 放置炸弹
    drop: bool = False       # 丢弃物品
    confidence: float = 1.0  # 置信度 (0-1)
    reasoning: str = ""      # 决策原因
```

---

## 配置指南

### 预设配置

```python
from orchestrator_enhanced import AIConfig

# 激进配置（高伤害输出）
aggressive_config = AIConfig(
    attack_aggression=0.9,
    defense_preference=0.3,
    movement_style="aggressive",
    enable_behavior_tree=True,
    enable_advanced_control=True,
)

# 防御配置（生存优先）
defensive_config = AIConfig(
    attack_aggression=0.4,
    defense_preference=0.8,
    movement_style="kiting",
    enable_behavior_tree=True,
    enable_advanced_control=True,
    enable_adaptive_behavior=True,
)

# 平衡配置
balanced_config = AIConfig(
    attack_aggression=0.6,
    defense_preference=0.5,
    movement_style="balanced",
)
```

### 模块开关

```python
# 完整功能
full_config = AIConfig(
    enable_pathfinding=True,
    enable_threat_analysis=True,
    enable_behavior_tree=True,
    enable_advanced_control=True,
    enable_adaptive_behavior=True,
)

# 轻量模式（仅基础功能）
light_config = AIConfig(
    enable_pathfinding=True,
    enable_threat_analysis=True,
    enable_behavior_tree=False,
    enable_advanced_control=False,
    enable_adaptive_behavior=False,
)

# 仅行为树
bt_only_config = AIConfig(
    enable_pathfinding=True,
    enable_threat_analysis=True,
    enable_behavior_tree=True,
    enable_advanced_control=False,
    enable_adaptive_behavior=False,
)
```

---

## 示例代码

### 示例 1: 基础连接

```python
from isaac_bridge import IsaacBridge

bridge = IsaacBridge()

@bridge.on("connected")
def on_connected(info):
    print(f"Game connected: {info['address']}")

@bridge.on("disconnected")
def on_disconnected():
    print("Game disconnected")

@bridge.on("data:PLAYER_POSITION")
def on_position(pos):
    if pos:
        p = pos[0] if isinstance(pos, list) else pos
        print(f"Player at: {p['pos']['x']:.1f}, {p['pos']['y']:.1f}")

bridge.start()
print("Waiting for game connection...")
```

### 示例 2: 简单自动战斗

```python
from orchestrator_enhanced import SimpleAI

ai = SimpleAI(use_enhanced=True)
ai.connect()

# 连接到 IsaacBridge
@ai.orchestrator.data_processor.bridge.on("data")
def on_game_data(data):
    move, shoot = ai.update(data)
    
    if any(move) or any(shoot):
        ai.orchestrator.data_processor.bridge.send_input(
            move=move,
            shoot=shoot,
        )
```

### 示例 3: 自定义行为树

```python
from behavior_tree import (
    BehaviorTree,
    SelectorNode,
    SequenceNode,
    ConditionNode,
    ActionNode,
)

# 自定义行为树
root = SelectorNode("CustomRoot")

# 优先级1: 躲避投射物
dodge = SequenceNode("DodgeProjectiles")
dodge.add_child(ConditionNode(
    "HasProjectiles",
    lambda ctx: len(ctx.projectiles) > 0
))
dodge.add_child(ActionNode(
    "DodgeAction",
    lambda ctx: self._do_dodge(ctx)
))
root.add_child(dodge)

# 优先级2: 攻击
attack = SequenceNode("AttackTarget")
attack.add_child(ConditionNode(
    "HasTarget",
    lambda ctx: ctx.target is not None
))
attack.add_child(ActionNode(
    "AttackAction",
    lambda ctx: self._do_attack(ctx)
))
root.add_child(attack)

# 创建行为树
bt = BehaviorTree(root)
```

### 示例 4: 自定义策略

```python
from strategy_system import StrategyManager, StrategyType, GameContext

class CustomStrategyManager(StrategyManager):
    def __init__(self, weights=None):
        super().__init__(weights)
        
        # 注册自定义策略执行器
        self.register_executor(
            StrategyType.AGGRESSIVE,
            self.custom_aggressive_executor
        )
    
    def custom_aggressive_executor(self, evaluation, context):
        """自定义激进策略执行"""
        return {
            "move_speed": 1.5,
            "attack_rate": 2.0,
            "target_priority": "nearest",
        }
```

---

## 故障排除

### 常见问题

#### Q1: 连接失败

```
Error: Failed to start server: [Errno 10048] (Windows)
```

**解决方案**:
```bash
# 更换端口
bridge = IsaacBridge(port=9528)

# 或结束占用端口的进程
netstat -ano | findstr :9527
taskkill /PID <PID> /F
```

#### Q2: 模块导入错误

```
ModuleNotFoundError: No module named 'orchestrator_enhanced'
```

**解决方案**:
```bash
# 确保在正确目录
cd SocketBridge/python

# 添加到 Python 路径
import sys
sys.path.insert(0, '/path/to/SocketBridge/python')
```

#### Q3: 控制无响应

**检查步骤**:
```python
# 1. 检查连接状态
print(bridge.is_connected())  # 应返回 True

# 2. 检查 AI 是否启用
print(orchestrator.is_enabled)  # 应返回 True

# 3. 查看统计信息
print(orchestrator.get_performance_stats())
```

#### Q4: 性能问题

**优化建议**:

```python
# 1. 降低决策频率
config = AIConfig(decision_interval=0.1)  # 10Hz

# 2. 禁用不需要的模块
config = AIConfig(
    enable_behavior_tree=False,
    enable_advanced_control=False,
    enable_adaptive_behavior=False,
)

# 3. 减少日志输出
import logging
logging.basicConfig(level=logging.WARNING)
```

### 日志查看

```python
import logging

# 启用详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('ai_debug.log'),
        logging.StreamHandler(),
    ]
)
```

---

## 文件结构

```
SocketBridge/
├── main.lua                    # 游戏模组
├── metadata.xml                # 模组元数据
├── README.md                   # 项目说明
├── README_WINDOWS.md          # Windows 安装指南
└── python/
    ├── isaac_bridge.py         # 核心桥接
    ├── orchestrator_enhanced.py  # AI 主控
    ├── orchestrator.py         # 原始主控
    ├── data_processor.py       # 数据处理
    ├── environment.py          # 环境模型
    ├── basic_controllers.py    # 基础控制
    ├── pathfinding.py          # 路径规划
    ├── threat_analysis.py      # 威胁分析
    ├── state_machine.py        # 状态机
    ├── strategy_system.py      # 策略系统
    ├── behavior_tree.py        # 行为树
    ├── advanced_control.py     # 高级控制
    ├── smart_aiming.py         # 智能瞄准
    ├── adaptive_system.py      # 自适应系统
    ├── data_recorder.py        # 数据记录
    ├── example_ai.py           # AI 示例
    ├── test_integration.py     # 集成测试
    ├── test_windows_compatibility.py  # 兼容性测试
    ├── logs/                   # 日志目录
    └── recordings/             # 录制目录
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 2.0 | 2024-01 | 增强版 AI 架构，集成 Phase 1-4 模块 |
| 1.0 | 2024-01 | 基础框架，核心桥接功能 |

---

## 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交变更
4. 发起 Pull Request

---

**文档最后更新**: 2024年1月
**维护者**: AI Combat System Team
