# API Quick Reference

## 核心导入

```python
# 完整导入
from socketbridge import *

# 或按需导入
from socketbridge import SimpleAI, IsaacBridge, CombatOrchestrator
```

---

## IsaacBridge - 核心桥接

```python
from socketbridge import IsaacBridge

# 创建实例
bridge = IsaacBridge(host="127.0.0.1", port=9527)

# 启动服务器
bridge.start()

# 发送输入
bridge.send_input(
    move=(1, 0),      # (x, y) 方向
    shoot=(1, 0),     # 射击方向
    use_item=False,
    use_bomb=False,
)

# 事件处理
@bridge.on("connected")
def on_connected(info):
    print(f"游戏连接: {info['address']}")

@bridge.on("disconnected")
def on_disconnected():
    print("游戏断开")

@bridge.on("data:PLAYER_POSITION")
def on_position(pos):
    print(f"玩家位置: {pos}")

# 停止
bridge.stop()
```

---

## SimpleAI - 简单AI

```python
from socketbridge import SimpleAI

# 创建AI
ai = SimpleAI(use_enhanced=True)
ai.connect()

# 每帧更新
move, shoot = ai.update(game_data)

# 发送控制
bridge.send_input(move=move, shoot=shoot)
```

---

## EnhancedCombatOrchestrator - 增强版主控

```python
from socketbridge import (
    EnhancedCombatOrchestrator,
    AIConfig,
)

# 配置
config = AIConfig(
    decision_interval=0.05,      # 50ms
    attack_aggression=0.7,       # 0-1
    defense_preference=0.5,      # 0-1
    movement_style="kiting",     # "kiting", "aggressive", "defensive"
    enable_pathfinding=True,
    enable_threat_analysis=True,
    enable_behavior_tree=True,
    enable_advanced_control=True,
    enable_adaptive_behavior=True,
)

# 创建主控
orchestrator = EnhancedCombatOrchestrator(config)
orchestrator.initialize()

# 每帧更新
control = orchestrator.update(raw_message)

# 使用输出
if control.move_x != 0 or control.move_y != 0:
    bridge.send_input(move=(control.move_x, control.move_y))
if control.shoot:
    bridge.send_input(shoot=(control.shoot_x, control.shoot_y))
```

---

## AIConfig - 配置参数

```python
@dataclass
class AIConfig:
    # 决策频率
    decision_interval: float = 0.05      # 秒
    
    # 阈值
    immediate_threat_threshold: float = 0.5
    combat_engage_distance: float = 300.0
    retreat_health_threshold: float = 0.3
    
    # 行为参数
    attack_aggression: float = 0.7        # 0-1
    defense_preference: float = 0.5       # 0-1
    movement_style: str = "kiting"
    
    # 模块开关
    enable_pathfinding: bool = True
    enable_threat_analysis: bool = True
    enable_behavior_tree: bool = True
    enable_advanced_control: bool = True
    enable_adaptive_behavior: bool = True
```

---

## ControlOutput - 控制输出

```python
@dataclass
class ControlOutput:
    move_x: int = 0           # X方向移动 (-1, 0, 1)
    move_y: int = 0           # Y方向移动 (-1, 0, 1)
    shoot: bool = False       # 是否射击
    shoot_x: int = 0          # 射击方向 X
    shoot_y: int = 0          # 射击方向 Y
    use_item: bool = False    # 使用主动道具
    use_bomb: bool = False    # 放置炸弹
    drop: bool = False        # 丢弃物品
    confidence: float = 1.0   # 置信度 (0-1)
    reasoning: str = ""       # 决策原因
```

---

## 常用模块导入

```python
# 数据结构
from socketbridge import Vector2D, PlayerData, EnemyData, ProjectileData

# 控制器
from socketbridge import BasicControllerManager, ControlOutput

# AI决策
from socketbridge import StrategyManager, StrategyType
from socketbridge import BehaviorTree, NodeContext

# 分析
from socketbridge import ThreatAnalyzer, ThreatLevel
from socketbridge import DynamicPathPlanner

# 工具
from socketbridge import SmartAimingSystem, AdaptiveParameterSystem
```

---

## 状态枚举

```python
# 战斗状态
from socketbridge import CombatState
CombatState.IDLE        # 空闲
CombatState.EXPLORING   # 探索
CombatState.COMBAT      # 战斗
CombatState.EVASION     # 闪避
CombatState.RETREATING  # 撤退
CombatState.HEALING     # 治疗

# 策略类型
from socketbridge import StrategyType
StrategyType.AGGRESSIVE  # 激进
StrategyType.DEFENSIVE   # 防御
StrategyType.BALANCED    # 平衡
StrategyType.EVASIVE     # 闪避
StrategyType.HEALING     # 治疗

# 威胁等级
from socketbridge import ThreatLevel
ThreatLevel.LOW      # 低
ThreatLevel.MEDIUM   # 中
ThreatLevel.HIGH     # 高
ThreatLevel.CRITICAL # 紧急
```

---

## 性能统计

```python
# 获取统计信息
stats = orchestrator.get_performance_stats()

print(f"决策次数: {stats['decisions']}")
print(f"击杀数: {stats['enemies_killed']}")
print(f"受到的伤害: {stats['damage_taken']}")
print(f"状态切换: {stats['state_transitions']}")
print(f"策略切换: {stats['strategy_changes']}")
```

---

## 完整示例

```python
from socketbridge import IsaacBridge, SimpleAI

# 创建桥接和AI
bridge = IsaacBridge()
ai = SimpleAI(use_enhanced=True)
ai.connect()

# 数据处理
@bridge.on("data")
def on_game_data(data):
    # AI决策
    move, shoot = ai.update(data)
    
    # 发送控制
    if any(move) or any(shoot):
        bridge.send_input(move=move, shoot=shoot)

# 启动
bridge.start()
```

---

**参考**: [完整系统文档](SYSTEM_DOCUMENTATION.md)
