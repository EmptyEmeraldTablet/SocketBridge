# SocketBridge 调试信息使用指南

## 概述

本指南描述了如何在 SocketBridge 项目中使用调试信息来定位问题。项目已在关键数据传递位置添加了详细的日志输出。

## 调试日志级别

| 级别 | 说明 | 标记 |
|------|------|------|
| DEBUG | 详细的数据流追踪 | `[模块名]` |
| INFO | 关键处理节点 | `[模块名]` |
| WARNING | 数据异常 | `[模块名]` |
| ERROR | 解析/处理错误 | `[模块名]` |

## 数据流追踪

### 完整数据流路径

```
Lua端 (main.lua)
    ↓ [TCP Socket]
Python端 (isaac_bridge.py)
    ↓ [事件触发]
data_processor.py
    ↓ [GameStateData]
orchestrator_enhanced.py
    ↓ [决策生成]
basic_controllers.py
    ↓ [ControlOutput]
isaac_bridge.py
    ↓ [send_input]
Lua端 (main.lua)
    ↓ [InputExecutor]
游戏执行
```

## 各模块调试信息

### 1. data_processor.py

**关键跟踪点:**

| 位置 | 调试内容 |
|------|---------|
| `process_message()` 开始 | 消息类型、帧号、房间索引、payload通道列表 |
| 每个通道数据 | 列表长度、字典键、数据类型 |
| 玩家数据 | 位置、血量、属性 |
| 敌人数据 | 数量、最近敌人信息 |
| 投射物数据 | 敌方/玩家/激光数量 |
| 房间信息 | 索引、关卡、敌人数、清空状态 |
| 房间布局 | 瓷砖数量、门数量 |
| 异常 | 完整错误堆栈和payload内容 |

**日志示例:**
```
[DataProcessor] === START process_message ===
[DataProcessor] type=DATA, frame=1234, room_index=5
[DataProcessor] payload keys=['PLAYER_POSITION', 'ENEMIES', 'PROJECTILES']
[DataProcessor] Channel PLAYER_POSITION: list length=1
[DataProcessor] Player 1 position: (400.5, 300.2)
[DataProcessor] Enemies parsed: count=3
[DataProcessor] Nearest enemy: id=10, dist=150.5, hp=10.0/10.0
[DataProcessor] Projectiles parsed: enemy=2, player=0, lasers=0
```

### 2. orchestrator_enhanced.py

**关键跟踪点:**

| 位置 | 调试内容 |
|------|---------|
| `update()` 开始 | 原始消息键 |
| Phase 1 数据解析 | 帧号、房间、玩家位置、敌人/投射物数量 |
| Phase 2 威胁分析 | 威胁等级、即刻威胁数量、最近威胁距离 |
| Phase 3-4 决策 | 战斗状态、移动状态、策略、行为树动作 |
| 最终控制 | 移动、射击、使用物品、置信度、原因 |

**日志示例:**
```
[Orchestrator] === START update ===
[Orchestrator] raw_message keys: ['type', 'frame', 'room_index', 'payload']
[Orchestrator] [Phase 1] Frame=1234, Room=5
[Orchestrator] [Phase 1] Player pos=(400.5, 300.2), hp=6/6
[Orchestrator] [Phase 1] Environment updated: enemies=3, projectiles=2
[Orchestrator] [Phase 2] Threat level=HIGH, immediate_threats=2, closest_threat=100.5
[Orchestrator] [Phase 3] Battle state: BattleState.AGGRESSIVE, Movement: MovementState.CHASING
[Orchestrator] [Phase 3] Strategy: StrategyType.AGGRESSIVE
[Orchestrator] [Phase 3] Behavior tree action: attack
[Orchestrator] Target selected: id=10, pos=(500.5, 350.2), hp=10.0/10.0
[Orchestrator] [Phase 5] Control output: move=(1, 0), shoot=True, confidence=0.80
```

### 3. basic_controllers.py

**关键跟踪点:**

| 位置 | 调试内容 |
|------|---------|
| `compute_control()` 开始 | 玩家位置、速度、帧号 |
| 敌人信息 | 目标敌人位置、距离、血量 |
| 威胁躲避 | 威胁数量、躲避命令 |
| 战斗移动 | 移动命令 |
| 攻击 | 是否射击、攻击命令 |
| 最终输出 | 完整控制指令 |

**日志示例:**
```
[BasicControllers] === START compute_control ===
[BasicControllers] Player pos=(400.5, 300.2), vel=(1.0, 0.0), frame=1234
[BasicControllers] Enemies: 3, Target: <EnemyData>
[BasicControllers] Target enemy: id=10, pos=(500.5, 350.2), dist=150.5, hp=10.0
[BasicControllers] Processing evasion for 2 threats...
[BasicControllers] Evasion command: move=(0, -1), reasoning=evade_threat
[BasicControllers] Processing combat movement...
[BasicControllers] Movement command: move=(1, 0), reasoning=combat_movement
[BasicControllers] Should shoot: True
[BasicControllers] Attack command: shoot=True, direction=(1, 0), reasoning=shoot_target
[BasicControllers] Final output: move=(1, 0), shoot=True, confidence=0.80, reasoning=combat_movement
```

### 4. threat_analysis.py

**关键跟踪点:**

| 位置 | 调试内容 |
|------|---------|
| `analyze()` 开始 | 玩家位置、帧号、敌人/投射物数量 |
| 威胁统计 | 总体等级、即刻/潜在威胁数量、最近距离 |
| 即刻威胁详情 | 类型、ID、等级、距离、优先级 |
| 投射物预测 | 是否击中、预计击中时间 |

**日志示例:**
```
[ThreatAnalysis] === START analyze ===
[ThreatAnalysis] Player pos=(400.5, 300.2), frame=1234
[ThreatAnalysis] Enemies: 3, Projectiles: 2
[ThreatAnalysis] Assessment results:
[ThreatAnalysis]   Overall threat level: HIGH
[ThreatAnalysis]   Immediate threats: 2
[ThreatAnalysis]   Potential threats: 1
[ThreatAnalysis]   Closest threat distance: 100.5
[ThreatAnalysis] Immediate threats detail:
[ThreatAnalysis]   [0] type=projectile, id=20, level=HIGH, dist=80.5, priority=0.95
[ThreatAnalysis]   [1] type=enemy, id=10, level=MEDIUM, dist=150.5, priority=0.45
[ThreatAnalysis]   Projectile 20: will_hit=True, impact_time=15
```

## 启用调试日志

### 方法1: 代码中配置

```python
import logging

# 设置DEBUG级别日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
```

### 方法2: 环境变量

```bash
export LOG_LEVEL=DEBUG
```

### 方法3: 只启用特定模块

```python
import logging

# 只启用DataProcessor的DEBUG日志
logging.getLogger("DataProcessor").setLevel(logging.DEBUG)

# 其他模块保持INFO级别
logging.getLogger("Orchestrator").setLevel(logging.INFO)
logging.getLogger("BasicControllers").setLevel(logging.INFO)
logging.getLogger("ThreatAnalysis").setLevel(logging.INFO)
```

## 问题定位场景

### 场景1: 数据接收问题

**症状:** 玩家位置不更新

**调试步骤:**
1. 启用 `[DataProcessor]` DEBUG日志
2. 查看是否有 `PLAYER_POSITION` 通道数据
3. 检查 `payload keys` 是否包含该通道
4. 检查玩家位置解析是否正确

### 场景2: AI不响应

**症状:** AI没有生成控制指令

**调试步骤:**
1. 启用 `[Orchestrator]` DEBUG日志
2. 检查 `update()` 是否被调用
3. 检查玩家数据是否存在 (`No player found`)
4. 检查威胁分析结果
5. 检查最终控制输出是否为空

### 场景3: 移动异常

**症状:** 角色移动方向错误

**调试步骤:**
1. 启用 `[BasicControllers]` DEBUG日志
2. 检查 `compute_control()` 输入参数
3. 查看目标敌人位置
4. 检查最终输出 `move=(x, y)` 值

### 场景4: 威胁判断错误

**症状:** 没有躲避即将命中的投射物

**调试步骤:**
1. 启用 `[ThreatAnalysis]` DEBUG日志
2. 检查投射物是否被正确解析
3. 检查 `will_hit` 预测结果
4. 检查 `impact_time` 是否在合理范围

## 异常追踪

当发生异常时，调试信息会记录:

1. 错误消息
2. 完整堆栈跟踪
3. 当时的payload数据

示例:
```
[DataProcessor] Error processing message at frame 1234: KeyError 'PLAYER_POSITION'
[DataProcessor] Traceback: (完整堆栈)
[DataProcessor] Payload at error: {'ENEMIES': [...], 'ROOM_INFO': {...}}
```

## 性能考虑

调试日志可能影响性能，生产环境建议:

```python
import logging

# 生产环境设置
logging.basicConfig(
    level=logging.WARNING,  # 只显示警告和错误
    format='%(asctime)s [%(levelname)s] %(message)s'
)
```

## 日志文件输出

```python
import logging

# 输出到文件
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('socketbridge_debug.log'),
        logging.StreamHandler(),
    ]
)
```

## 关键标识符说明

| 标识符 | 含义 | 模块 |
|--------|------|------|
| `[DataProcessor]` | 数据处理阶段 | data_processor.py |
| `[Orchestrator]` | AI决策主循环 | orchestrator_enhanced.py |
| `[BasicControllers]` | 控制指令计算 | basic_controllers.py |
| `[ThreatAnalysis]` | 威胁分析 | threat_analysis.py |
| `[Phase 1]` | 基础层（数据/环境） | orchestrator_enhanced.py |
| `[Phase 2]` | 分析层（威胁） | orchestrator_enhanced.py |
| `[Phase 3]` | 决策层（状态机/策略/行为树） | orchestrator_enhanced.py |
| `[Phase 4]` | 控制层（高级控制） | orchestrator_enhanced.py |

## 常见问题

### Q: 日志太多找不到关键信息
A: 使用grep过滤特定模块:
```bash
grep "DataProcessor" socketbridge_debug.log
```

### Q: 帧号不连续
A: 这可能表示:
- 数据丢失
- 处理延迟
- Lua端采集频率设置

### Q: 敌人数量突然变为0
A: 可能原因:
- 进入新房间
- 敌人被清除
- 数据解析错误

## 结论

通过这些调试信息，你可以:

1. **追踪数据流**: 了解数据从接收到的处理全过程
2. **定位问题**: 快速找到哪个环节出了问题
3. **验证假设**: 检查中间结果是否符合预期
4. **性能分析**: 识别处理瓶颈

建议在实际测试中根据具体问题启用相应模块的DEBUG日志。
