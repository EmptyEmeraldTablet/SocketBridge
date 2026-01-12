# SocketBridge Future Implementation Plan

**基于 2026.1.11 架构迁移与 2026.1.12 测试基础设施**

**创建日期**: 2026-01-12
**参考来源**: `reference_from_2026.1.11/` (2026.1.11 分支完整架构)
**测试框架**: 2026.1.12 当前测试工具 (`test_integration.py`, `data_replay_system.py`)

---

## 目录

1. [架构概览](#架构概览)
2. [Phase 0: 基础设施增强](#phase-0-基础设施增强)
3. [Phase 1: 基础模块迁移](#phase-1-基础模块迁移)
4. [Phase 2: 分析模块迁移](#phase-2-分析模块迁移)
5. [Phase 3: 决策模块迁移](#phase-3-决策模块迁移)
6. [Phase 4: 高级控制模块迁移](#phase-4-高级控制模块迁移)
7. [测试框架增强](#测试框架增强)
8. [文档与示例](#文档与示例)
9. [优先级与依赖关系](#优先级与依赖关系)
10. [验收标准](#验收标准)

---

## 架构概览

### 当前状态对比

| 组件 | 2026.1.12 (当前) | 2026.1.11 (参考) | 状态 |
|------|------------------|------------------|------|
| **核心桥接** | isaac_bridge.py (增强版) | isaac_bridge.py | ✅ 已具备 |
| **数据录制** | data_recorder.py, data_replay_system.py | - | ✅ 2026.1.12 优势 |
| **数据处理** | 部分功能 | data_processor.py | ❌ 待迁移 |
| **环境模型** | 部分功能 | environment.py | ❌ 待迁移 |
| **基础控制** | - | basic_controllers.py | ❌ 待迁移 |
| **路径规划** | - | pathfinding.py | ❌ 待迁移 |
| **威胁分析** | - | threat_analysis.py | ❌ 待迁移 |
| **状态机** | - | state_machine.py | ❌ 待迁移 |
| **策略系统** | - | strategy_system.py | ❌ 待迁移 |
| **行为树** | - | behavior_tree.py | ❌ 待迁移 |
| **高级控制** | - | advanced_control.py | ❌ 待迁移 |
| **智能瞄准** | - | smart_aiming.py | ❌ 待迁移 |
| **自适应系统** | - | adaptive_system.py | ❌ 待迁移 |
| **AI 主控** | - | orchestrator_enhanced.py | ❌ 待迁移 |

### 分层架构目标

```
┌─────────────────────────────────────────────────────────────┐
│                    Phase 4: 高级控制                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Adaptive   │  │    Smart    │  │    PID +    │         │
│  │   System    │  │   Aiming    │  │  Trajectory │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│                    Phase 3: 决策系统                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Strategy   │  │   Behavior  │  │   State     │         │
│  │   System    │  │    Tree     │  │   Machine   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│                    Phase 2: 分析系统                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Threat    │  │ Pathfinding │  │  Evaluation │         │
│  │  Analysis   │  │             │  │   System    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│                    Phase 1: 基础模块                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │    Data     │  │ Environment │  │    Basic    │         │
│  │  Processor  │  │    Model    │  │ Controllers │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
├─────────────────────────────────────────────────────────────┤
│                    Phase 0: 基础设施                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ IsaacBridge │  │   Recorder  │  │  Replay +   │         │
│  │  (核心)     │  │   (已有)    │  │  Testing    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 0: 基础设施增强

### 目标
建立坚实的测试基础，确保后续模块迁移时能够快速验证。

### 任务列表

#### TODO-0.1: 测试工具标准化
**优先级**: 🔴 高
**依赖**: 无
**状态**: ⏳ 待开始

**任务描述**:
- [ ] 统一所有测试工具的接口风格
- [ ] 创建 `TestRunner` 基类
- [ ] 标准化测试报告格式

**参考实现**: 
- `reference_from_2026.1.11/python/test_integration.py`
- `reference_from_2026.1.11/python/test_windows_compatibility.py`

**验收标准**:
- [ ] 所有测试可通过 `python test_runner.py` 运行
- [ ] 测试报告包含覆盖率信息
- [ ] 支持 `--verbose`, `--quiet`, `--report` 参数

**测试验证**:
```bash
# 运行所有测试
python test_runner.py --all

# 运行特定模块测试
python test_runner.py --module data_processor

# 生成报告
python test_runner.py --all --report
```

---

#### TODO-0.2: 录制回放系统增强
**优先级**: 🔴 高
**依赖**: TODO-0.1
**状态**: ⏳ 待开始

**任务描述**:
- [ ] 增强 `LuaSimulator` 支持更多消息类型
- [ ] 添加消息注入功能（用于故障注入测试）
- [ ] 创建合成数据生成器

**参考实现**: 
- `reference_from_2026.1.11/python/data_recorder.py`
- `reference_from_2026.1.11/python/isaac_bridge.py`

**验收标准**:
- [ ] 支持模拟所有已知消息类型
- [ ] 可注入错误消息测试错误处理
- [ ] 录制回放速度可调节（0.1x - 10x）

**测试验证**:
```python
# 合成测试数据
from test_utils import SyntheticDataGenerator

gen = SyntheticDataGenerator()
gen.add_player_position_trajectory("linear", duration=10)
gen.add_enemies("random", count=5)
session = gen.build_session()

# 回放测试
simulator = LuaSimulator()
simulator.load_session(session)
simulator.play(speed=2.0)  # 2倍速
```

---

#### TODO-0.3: 性能基准测试套件
**优先级**: 🟡 中
**依赖**: TODO-0.1
**状态**: ⏳ 待开始

**任务描述**:
- [ ] 创建基准测试框架
- [ ] 定义性能指标（延迟、吞吐量、资源占用）
- [ ] 建立性能回归检测

**验收标准**:
- [ ] 每次代码变更自动运行基准测试
- [ ] 性能下降 > 5% 触发警告
- [ ] 生成性能趋势图表

---

## Phase 1: 基础模块迁移

### 目标
迁移数据处理、环境模型、基础控制器模块。

### 任务列表

#### TODO-1.1: Data Processor 模块
**优先级**: 🔴 高
**依赖**: TODO-0.1
**状态**: ⏳ 待开始

**任务描述**:
迁移 `reference_from_2026.1.11/python/data_processor.py`

- [ ] 创建 `DataProcessor` 类
- [ ] 实现消息解析（DATA, EVENT, FULL_STATE）
- [ ] 实现游戏状态构建
- [ ] 实现便捷数据访问接口

**参考实现**: 
- `reference_from_2026.1.11/python/data_processor.py`
- `reference_from_2026.1.11/python/models.py`

**核心接口**:
```python
class DataProcessor:
    def process_message(self, raw_message: Dict[str, Any]) -> GameState
    def get_primary_player(self, state: GameState) -> Optional[Player]
    def get_active_enemies(self, state: GameState) -> List[Enemy]
    def get_projectiles(self, state: GameState) -> List[Projectile]
```

**验收标准**:
- [ ] 处理 `test_integration.py` 中的所有录制数据
- [ ] 单元测试覆盖率 > 90%
- [ ] 处理时间 < 1ms 每条消息

**测试验证**:
```python
from data_processor import DataProcessor

processor = DataProcessor()
# 使用录制数据测试
session = load_test_session()
for msg in session.messages:
    state = processor.process_message(msg.raw)
    assert state.frame >= 0
    assert state.player is not None or state.enemies
```

---

#### TODO-1.2: Environment Model 模块
**优先级**: 🔴 高
**依赖**: TODO-1.1
**状态**: ⏳ 待开始

**任务描述**:
迁移 `reference_from_2026.1.11/python/environment.py`

- [ ] 创建 `EnvironmentModel` 类
- [ ] 实现房间布局解析
- [ ] 实现障碍物检测
- [ ] 实现安全位置计算
- [ ] 实现路径规划接口

**核心接口**:
```python
class EnvironmentModel:
    def update_room(self, layout: RoomLayout, info: RoomInfo, 
                    enemies: List[Enemy], projectiles: List[Projectile])
    def get_safe_spot(self, player_pos: Position, 
                      min_distance: float, max_distance: float) -> Optional[Position]
    def find_path(self, start: Position, goal: Position) -> List[Position]
    def is_blocked(self, pos: Position) -> bool
```

**验收标准**:
- [ ] 正确解析房间布局数据
- [ ] 安全位置计算正确
- [ ] 路径规划返回合理路径

**测试验证**:
```python
from environment import EnvironmentModel

env = EnvironmentModel()
env.update_room(layout, info, enemies, [])

# 测试安全位置
safe = env.get_safe_spot(player_pos, min_distance=50, max_distance=200)
assert safe is not None

# 测试路径规划
path = env.find_path(start, goal)
assert len(path) > 0
```

---

#### TODO-1.3: Basic Controllers 模块
**优先级**: 🔴 高
**依赖**: TODO-1.1, TODO-1.2
**状态**: ⏳ 待开始

**任务描述**:
迁移 `reference_from_2026.1.11/python/basic_controllers.py`

- [ ] 创建 `BasicControllerManager` 类
- [ ] 实现移动控制计算
- [ ] 实现射击控制计算
- [ ] 实现闪避控制

**核心接口**:
```python
class BasicControllerManager:
    def compute_control(self, game_state: GameState,
                        target_enemy: Enemy = None,
                        evade_threats: List[Threat] = None,
                        shoot_override: Tuple[float, float] = None) -> ControlOutput
```

**验收标准**:
- [ ] 控制输出符合游戏输入格式
- [ ] 闪避逻辑正确
- [ ] 单元测试覆盖率 > 85%

---

## Phase 2: 分析模块迁移

### 目标
迁移路径规划、威胁分析、评估系统模块。

### 任务列表

#### TODO-2.1: Pathfinding 模块
**优先级**: 🟡 中
**依赖**: TODO-1.2
**状态**: ⏳ 待开始

**任务描述**:
迁移 `reference_from_2026.1.11/python/pathfinding.py`

- [ ] 实现 A* 路径规划
- [ ] 实现动态障碍物避让
- [ ] 实现路径执行器

**核心接口**:
```python
class DynamicPathPlanner:
    def plan_path(self, start: Position, goal: Position,
                  obstacles: List[Obstacle]) -> List[Position]
    def update_obstacles(self, obstacles: List[Obstacle])

class PathExecutor:
    def execute_to(self, current: Position, target: Position) -> MovementCommand
```

**验收标准**:
- [ ] 路径规划成功率 > 95%
- [ ] 规划时间 < 10ms
- [ ] 正确处理动态障碍物

---

#### TODO-2.2: Threat Analysis 模块
**优先级**: 🟡 中
**依赖**: TODO-1.1, TODO-1.2
**状态**: ⏳ 待开始

**任务描述**:
迁移 `reference_from_2026.1.11/python/threat_analysis.py`

- [ ] 创建 `ThreatAnalyzer` 类
- [ ] 实现敌人威胁评估
- [ ] 实现投射物威胁评估
- [ ] 实现综合威胁等级计算

**核心接口**:
```python
class ThreatAnalyzer:
    def analyze(self, player_position: Position,
                enemies: List[Enemy],
                enemy_projectiles: List[Projectile],
                current_frame: int) -> ThreatAssessment
    def get_evasion_vector(self, player_pos: Position,
                           threats: List[Threat]) -> Vector
```

**验收标准**:
- [ ] 威胁等级计算正确
- [ ] 闪避建议可行
- [ ] 单元测试覆盖所有威胁类型

---

#### TODO-2.3: Evaluation System 模块
**优先级**: 🟡 中
**依赖**: TODO-1.1, TODO-2.1, TODO-2.2
**状态**: ⏳ 待开始

**任务描述**:
迁移 `reference_from_2026.1.11/python/evaluation_system.py`

- [ ] 创建 `EvaluationSystem` 类
- [ ] 实现战斗评估
- [ ] 实现移动评估
- [ ] 实现命中率统计

---

## Phase 3: 决策模块迁移

### 目标
迁移状态机、策略系统、行为树模块。

### 任务列表

#### TODO-3.1: State Machine 模块
**优先级**: 🟡 中
**依赖**: TODO-1.1, TODO-2.2
**状态**: ⏳ 待开始

**任务描述**:
迁移 `reference_from_2026.1.11/python/state_machine.py`

- [ ] 实现分层状态机
- [ ] 实现战斗状态管理
- [ ] 实现移动状态管理

**核心接口**:
```python
class HierarchicalStateMachine:
    def update(self, threat_level: float, player_health: float,
               enemy_count: int, has_projectiles: bool,
               can_heal: bool) -> Dict[str, Enum]
```

**状态类型**:
- BattleState: IDLE, AGGRESSIVE, DEFENSIVE, DODGE, RETREAT, HEAL_PRIORITY
- MovementState: EXPLORING, CHASING, FLEEING, POSITIONING, STATIONARY
- SpecialState: NONE, USING_ITEM, INTERACTING, CHARGING, BOMBING

---

#### TODO-3.2: Strategy System 模块
**优先级**: 🟡 中
**依赖**: TODO-1.1, TODO-2.3
**状态**: ⏳ 待开始

**任务描述**:
迁移 `reference_from_2026.1.11/python/strategy_system.py`

- [ ] 实现 `StrategyManager` 类
- [ ] 实现多策略评估
- [ ] 实现策略执行

**策略类型**:
- AGGRESSIVE: 高攻击性
- DEFENSIVE: 防御优先
- BALANCED: 攻守平衡
- EVASIVE: 闪避优先
- HEALING: 治疗优先

---

#### TODO-3.3: Behavior Tree 模块
**优先级**: 🟡 中
**依赖**: TODO-1.1, TODO-2.2, TODO-3.1
**状态**: ⏳ 待开始

**任务描述**:
迁移 `reference_from_2026.1.11/python/behavior_tree.py`

- [ ] 实现节点基类（Selector, Sequence, Condition, Action）
- [ ] 实现战斗行为树
- [ ] 实现行为树执行器

**行为树优先级**:
1. 紧急躲避（投射物）
2. 低血量治疗
3. 战斗逻辑
4. 移动到有利位置

---

## Phase 4: 高级控制模块迁移

### 目标
迁移高级控制、智能瞄准、自适应系统模块。

### 任务列表

#### TODO-4.1: Advanced Control 模块
**优先级**: 🟢 低
**依赖**: TODO-1.3, TODO-3.1
**状态**: ⏳ 待开始

**任务描述**:
迁移 `reference_from_2026.1.11/python/advanced_control.py`

- [ ] 实现 PID 控制器
- [ ] 实现轨迹优化
- [ ] 实现平滑移动

---

#### TODO-4.2: Smart Aiming 模块
**优先级**: 🟢 低
**依赖**: TODO-1.1, TODO-2.2
**状态**: ⏳ 待开始

**任务描述**:
迁移 `reference_from_2026.1.11/python/smart_aiming.py`

- [ ] 实现目标位置预测
- [ ] 实现提前量计算
- [ ] 实现自适应命中率调整

**特性**:
- 目标位置预测
- 提前量射击计算
- 多种射击模式（normal, spread, burst, precise）

---

#### TODO-4.3: Adaptive System 模块
**优先级**: 🟢 低
**依赖**: TODO-2.3, TODO-3.2
**状态**: ⏳ 待开始

**任务描述**:
迁移 `reference_from_2026.1.11/python/adaptive_system.py`

- [ ] 实现场景识别
- [ ] 实现动态参数调整
- [ ] 实现性能指标监控

**场景类型**:
- BOSS_FIGHT: Boss 战
- SWARM: 大量敌人
- ONE_VS_ONE: 1v1 对战
- NARROW_SPACE: 狭窄空间
- OPEN_SPACE: 开阔空间
- HAZARDOUS: 危险环境

---

## Phase 5: AI 主控集成

### 目标
创建统一的 AI 主控器，整合所有模块。

### 任务列表

#### TODO-5.1: Enhanced Orchestrator
**优先级**: 🔴 高
**依赖**: TODO-1.3, TODO-2.1, TODO-2.2, TODO-3.1, TODO-3.2, TODO-3.3
**状态**: ⏳ 待开始

**任务描述**:
迁移 `reference_from_2026.1.11/python/orchestrator_enhanced.py`

- [ ] 实现 `EnhancedCombatOrchestrator` 类
- [ ] 集成所有 Phase 1-4 模块
- [ ] 实现配置系统
- [ ] 实现性能统计

**核心接口**:
```python
class EnhancedCombatOrchestrator:
    def __init__(self, config: AIConfig = None)
    def initialize(self) -> None
    def update(self, raw_message: Dict[str, Any]) -> ControlOutput
    def set_aggression(self, level: float) -> None
    def set_movement_style(self, style: str) -> None
```

**配置选项**:
```python
@dataclass
class AIConfig:
    decision_interval: float = 0.05
    immediate_threat_threshold: float = 0.5
    combat_engage_distance: float = 300.0
    retreat_health_threshold: float = 0.3
    attack_aggression: float = 0.7
    defense_preference: float = 0.5
    movement_style: str = "kiting"
    enable_pathfinding: bool = True
    enable_threat_analysis: bool = True
    enable_behavior_tree: bool = True
    enable_advanced_control: bool = True
    enable_adaptive_behavior: bool = True
```

---

## 测试框架增强

### 目标
基于 2026.1.12 的测试基础设施，为新模块创建测试。

### 任务列表

#### TEST-1: Data Processor 测试
**优先级**: 🔴 高
**依赖**: TODO-1.1
**状态**: ⏳ 待开始

**测试用例**:
1. 消息解析正确性
2. 游戏状态构建
3. 边界条件处理
4. 错误数据容错

**测试数据**:
- 使用 `python/recordings/` 中的录制数据
- 使用合成测试数据

---

#### TEST-2: Environment Model 测试
**优先级**: 🔴 高
**依赖**: TODO-1.2
**状态**: ⏳ 待开始

**测试用例**:
1. 房间布局解析
2. 障碍物检测
3. 安全位置计算
4. 路径规划

---

#### TEST-3: Threat Analysis 测试
**优先级**: 🟡 中
**依赖**: TODO-2.2
**状态**: ⏳ 待开始

**测试用例**:
1. 敌人威胁等级计算
2. 投射物威胁计算
3. 综合威胁评估
4. 闪避建议

---

#### TEST-4: Integration 测试
**优先级**: 🔴 高
**依赖**: TODO-5.1
**状态**: ⏳ 待开始

**测试用例**:
1. 完整战斗流程
2. 状态转换测试
3. 策略选择测试
4. 性能测试

---

## 文档与示例

### 目标
创建完整的文档和使用示例。

### 任务列表

#### DOC-1: 系统文档
**优先级**: 🟡 中
**依赖**: TODO-5.1
**状态**: ⏳ 待开始

**文档结构**:
- 系统概述
- 架构设计
- 模块详解
- API 参考
- 配置指南
- 示例代码
- 故障排除

---

#### DOC-2: 快速开始指南
**优先级**: 🟡 中
**依赖**: DOC-1
**状态**: ⏳ 待开始

**内容**:
1. 环境准备
2. 安装步骤
3. 基础使用
4. 高级配置

---

#### DOC-3: 示例代码
**优先级**: 🟡 中
**依赖**: TODO-5.1
**状态**: ⏳ 待开始

**示例**:
1. 基础连接
2. 简单自动战斗
3. 自定义行为树
4. 自定义策略

---

## 优先级与依赖关系

### 优先级顺序

```
P0 (必须优先):
├── TODO-0.1: 测试工具标准化
├── TODO-0.2: 录制回放系统增强
├── TODO-1.1: Data Processor 模块
└── TODO-5.1: Enhanced Orchestrator

P1 (重要):
├── TODO-1.2: Environment Model 模块
├── TODO-1.3: Basic Controllers 模块
├── TODO-2.1: Pathfinding 模块
├── TODO-2.2: Threat Analysis 模块
└── TODO-3.1: State Machine 模块

P2 (有用):
├── TODO-0.3: 性能基准测试套件
├── TODO-2.3: Evaluation System 模块
├── TODO-3.2: Strategy System 模块
└── TODO-3.3: Behavior Tree 模块

P3 (增强):
├── TODO-4.1: Advanced Control 模块
├── TODO-4.2: Smart Aiming 模块
├── TODO-4.3: Adaptive System 模块
└── DOC-*: 文档与示例
```

### 依赖图

```
TODO-0.1 ──┬── TODO-0.2 ──┬── TODO-1.1 ──┬── TODO-1.2 ──┬── TODO-2.1
           │              │              │              │
           │              │              │              └── TODO-3.1
           │              │              │
           │              │              └── TODO-1.3 ──┬── TODO-4.1
           │              │                             │
           │              └── TODO-2.2 ──┬── TODO-2.3 ──┴── TODO-3.3
                                      │
                                      └── TODO-3.2 ──┘
                                                  │
                                                  └── TODO-5.1
```

---

## 验收标准

### 通用标准
所有模块必须满足：
- [ ] 单元测试覆盖率 > 85%
- [ ] 类型注解完整
- [ ] 文档字符串完整
- [ ] 通过静态类型检查（mypy）
- [ ] 通过代码风格检查（ruff/flake8）

### 性能标准
- [ ] 消息处理延迟 < 1ms
- [ ] 决策延迟 < 50ms
- [ ] 内存占用稳定

### 集成标准
- [ ] 与 `isaac_bridge.py` 正确集成
- [ ] 与 `data_replay_system.py` 兼容
- [ ] 通过 `test_integration.py` 测试

---

## 测试执行指南

### 环境准备
```bash
# 进入 python 目录
cd SocketBridge/python

# 安装测试依赖（如果需要）
pip install pytest pytest-cov

# 运行所有测试
python -m pytest test_integration.py -v

# 运行特定模块测试
python -m pytest test_data_processor.py -v
```

### 录制数据测试
```python
# 使用录制数据进行集成测试
from test_integration import IntegrationTest

test = IntegrationTest(session_dir="recordings/session_20260112_005209")
test.run(timeout=30.0)
test.print_stats()
```

### 性能测试
```python
from performance_benchmark import run_benchmark

results = run_benchmark(iterations=1000)
print(f"Average latency: {results.avg_latency_ms}ms")
print(f"P95 latency: {results.p95_latency_ms}ms")
```

---

## 后续工作

### 潜在增强
1. **机器学习集成**: 使用录制数据训练模型
2. **多智能体支持**: 支持多个 AI 实例
3. **云端部署**: 支持远程推理
4. **可视化工具**: 实时状态监控

### 技术债务
1. 统一错误处理
2. 完善日志系统
3. 配置管理优化
4. 文档持续更新

---

**文档版本**: 1.0
**最后更新**: 2026-01-12
**维护者**: SocketBridge Development Team
