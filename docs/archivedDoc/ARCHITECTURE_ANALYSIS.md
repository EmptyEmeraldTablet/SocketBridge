# SocketBridge 模块依赖关系与数据流动分析(已过期)

## 1. 依赖关系图

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    数据源 (RawMessage)                   │
                    │         (来自 replay 或游戏 TCP 服务器)                   │
                    └─────────────────────────┬───────────────────────────────┘
                                              │
                                              ▼
                    ┌─────────────────────────────────────────────────────────┐
                    │              data_processor.py                          │
                    │         DataProcessor / DataParser                      │
                    │                                                         │
                    │  输入: RawMessage (JSON 字典)                            │
                    │  输出: GameStateData                                    │
                    └─────────────────────────┬───────────────────────────────┘
                                              │
                              ┌───────────────┼───────────────┐
                              │               │               │
                              ▼               ▼               ▼
              ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
              │ environment.py│ │threat_analysis│ │ smart_aiming.py│
              │EnvironmentModel│ │ThreatAnalyzer │ │SmartAimingSys │
              └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
                      │                 │                 │
                      │     ┌───────────┴───────────┐     │
                      │     │                       │     │
                      ▼     ▼                       ▼     ▼
              ┌─────────────────────────────────────────────────────────┐
              │              behavior_tree.py                           │
              │           BehaviorTree / NodeContext                    │
              │                                                         │
              │  输入: GameState, ThreatAssessment, AimResult           │
              │  输出: NodeStatus (决策结果)                             │
              └─────────────────────────┬───────────────────────────────┘
                                        │
                                        ▼
              ┌─────────────────────────────────────────────────────────┐
              │           orchestrator_enhanced.py                      │
              │        EnhancedCombatOrchestrator (主控器)               │
              │                                                         │
              │  整合: DataProcessor, ThreatAnalyzer, BehaviorTree,     │
              │       SmartAiming, StateMachine, StrategyManager,       │
              │       AdaptiveSystem, BasicController, AdvancedControl  │
              │                                                         │
              │  输入: RawMessage                                       │
              │  输出: ControlOutput                                    │
              └─────────────────────────┬───────────────────────────────┘
                                        │
                                        ▼
              ┌─────────────────────────────────────────────────────────┐
              │              evaluation_system.py                       │
              │        PerformanceEvaluator / ParameterOptimizer        │
              │                                                         │
              │  输入: 决策记录、性能指标                                 │
              │  输出: PerformanceMetrics, AdjustmentSuggestion         │
              └─────────────────────────────────────────────────────────┘
```

## 2. 详细数据流动

### 2.1 核心数据类型

```python
# models.py 中定义的核心数据结构

@dataclass
class GameStateData:
    """游戏状态数据 - 所有模块的输入核心"""
    frame: int
    room_index: int
    players: Dict[str, PlayerData]      # 玩家位置、血量等
    enemies: Dict[str, EnemyData]       # 敌人位置、血量、类型
    projectiles: Dict[str, ProjectileData]  # 投射物
    room_info: Optional[RoomInfo]       # 房间布局、尺寸

@dataclass
class ControlOutput:
    """控制输出 - AI 的最终输出"""
    move_x: float = 0.0
    move_y: float = 0.0
    shoot: bool = False
    shoot_x: float = 0.0
    shoot_y: float = 0.0
    confidence: float = 0.0
```

### 2.2 模块间数据流

```
RawMessage (来自 replay 或游戏)
    │
    ▼
┌────────────────────────┐
│   DataProcessor        │
│   process_message()    │
└───────────┬────────────┘
            │ GameStateData
            │
            ├─────────────────────────────────────┐
            │                                     │
            ▼                                     ▼
┌────────────────────────┐         ┌────────────────────────┐
│   EnvironmentModel     │         │   ThreatAnalyzer       │
│   update_room()        │         │   analyze()            │
│                        │         │                        │
│ 输入:                  │         │ 输入:                  │
│   - room_info          │         │   - game_state.players │
│   - enemies            │         │   - game_state.enemies │
│   - projectiles        │         │   - game_state.projectiles│
│                        │         │                        │
│ 输出:                  │         │ 输出:                  │
│   - safe_spots[]       │         │   - ThreatAssessment   │
│   - escape_routes[]    │         │     (threat_level,     │
│   - obstacle_map       │         │      immediate_threats,│
│                        │         │      potential_threats)│
└───────────┬────────────┘         └───────────┬────────────┘
            │                                 │
            │  EnvironmentQuery               │ ThreatAssessment
            │  (安全位置、障碍物)               │ (威胁等级、威胁列表)
            │                                 │
            │         ┌───────────────────────┤
            │         │                       │
            ▼         ▼                       ▼
┌─────────────────────────────────────────────────────────┐
│              BehaviorTree (Combat AI)                    │
│              update() / execute()                        │
│                                                         │
│ 输入:                                                    │
│   - game_state (players, enemies, projectiles)          │
│   - threat_assessment (威胁分析结果)                      │
│   - aim_result (瞄准结果)                                │
│   - environment_query (环境信息)                          │
│                                                         │
│ 输出:                                                    │
│   - NodeStatus.SUCCESS/FAILURE/RUNNING                  │
│   - 决策行为类型 (attack, dodge, retreat, etc.)          │
└───────────────────┬─────────────────────────────────────┘
                    │
                    │ 战术决策 (做什么)
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│              SmartAimingSystem                           │
│              aim()                                       │
│                                                         │
│ 输入:                                                    │
│   - shooter_pos (玩家位置)                               │
│   - target (目标敌人)                                    │
│   - shot_type (射击类型)                                 │
│   - threat_level (威胁等级)                              │
│                                                         │
│ 输出:                                                    │
│   - AimResult (方向、置信度、射击类型)                    │
└───────────────────┬─────────────────────────────────────┘
                    │
                    │ 瞄准参数 (射击方向、置信度)
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│              AdvancedCombatOrchestrator                  │
│              update()                                    │
│                                                         │
│ 整合所有模块的输出，生成最终控制指令:                      │
│                                                         │
│   - move_x, move_y (移动方向 -1~1)                       │
│   - shoot (是否射击)                                     │
│   - shoot_x, shoot_y (射击方向)                          │
│   - confidence (决策置信度 0~1)                          │
│                                                         │
└───────────────────┬─────────────────────────────────────┘
                    │
                    │ ControlOutput
                    │
                    ▼
┌─────────────────────────────────────────────────────────┐
│              EvaluationSystem                            │
│              update() / evaluate_and_optimize()          │
│                                                         │
│ 输入:                                                    │
│   - 决策类型、行动、结果、延迟                            │
│   - 命中/躲避/伤害/击杀记录                               │
│                                                         │
│ 输出:                                                    │
│   - PerformanceMetrics (综合评分)                        │
│   - AdjustmentSuggestion (参数调整建议)                   │
└─────────────────────────────────────────────────────────┘
```

## 3. 测试覆盖分析

### 3.1 当前测试覆盖情况

| 测试模块 | 输入 | 验证内容 | 数据流覆盖 |
|---------|------|---------|-----------|
| **DataProcessorTest** | RawMessage | 解析正确性 | ✅ 输入→GameState |
| **EnvironmentTest** | GameState | 环境更新查询 | ✅ 部分 (room→model→query) |
| **ThreatAnalyzerTest** | GameState | 威胁评估 | ✅ 部分 (state→assessment) |
| **PathfindingTest** | GameState | 路径规划 | ⚠️ 部分 (start→path) |
| **BehaviorTreeTest** | GameState | 树执行 | ⚠️ 部分 (state→status) |
| **SmartAimingTest** | GameState | 瞄准计算 | ⚠️ 部分 (player+target→aim) |
| **OrchestratorTest** | RawMessage | 完整流程 | ✅ 端到端 |
| **IntegrationTest** | RawMessage | 多模块集成 | ✅ 端到端 |

### 3.2 未覆盖的数据流

```
当前测试未验证的模块间数据流动:

1. Environment → ThreatAnalyzer
   ❌ 测试中没有传递 safe_spots / escape_routes 给威胁分析
   
2. ThreatAnalyzer → BehaviorTree
   ⚠️ 测试验证了输出存在，但未验证威胁级别如何影响行为选择
   
3. BehaviorTree → SmartAiming
   ❌ 没有验证战术决策如何影响瞄准参数
   
4. SmartAiming → Orchestrator
   ⚠️ 测试验证了 AimResult 存在，但未验证如何融合到最终控制
   
5. Orchestrator → EvaluationSystem
   ❌ 测试中没有记录决策到评估系统

6. EvaluationSystem → Orchestrator (参数调整)
   ❌ 未测试自适应参数调整闭环
```

## 4. 数据流测试建议

### 4.1 创建数据流验证测试

```python
# test_data_flow.py - 验证模块间数据流动

def test_environment_threat_integration():
    """
    验证: EnvironmentModel → ThreatAnalyzer 的数据流动
    
    预期:
    - EnvironmentModel 返回的 safe_spots 被 ThreatAnalyzer 使用
    - 威胁评估考虑到可用逃跑路线
    """
    # 1. 设置场景: 玩家被敌人包围，只有一个安全出口
    state = create_test_state(
        player_pos=Vector2D(260, 200),
        enemies=[enemy_at(Vector2D(200, 200)), enemy_at(Vector2D(320, 200))],
        safe_spot=Vector2D(260, 100),  # 只有上方安全
    )
    
    # 2. 更新环境模型
    env_model.update_room(room_info, enemies, projectiles)
    
    # 3. 威胁分析时应该考虑到安全位置
    assessment = threat_analyzer.analyze(state)
    
    # 4. 验证: 威胁级别应该反映可用逃跑选项
    assert assessment.overall_threat_level == ThreatLevel.HIGH  # 只有一个出口


def test_behavior_tree_aiming_integration():
    """
    验证: BehaviorTree → SmartAiming 的数据流动
    
    预期:
    - behavior_tree 的 "attack" 决策触发瞄准计算
    - "retreat" 决策应该使用不同瞄准策略
    """
    # 1. 设置场景: 玩家血量低，敌人靠近
    state = create_test_state(
        player_health=0.2,  # 20% 血量
        enemies=[nearby_enemy()],
    )
    
    # 2. 构建行为树上下文
    ctx = NodeContext()
    ctx.game_state = state
    ctx.threat_level = 0.8
    
    # 3. 执行行为树
    tree.context = ctx
    status = tree.update()
    
    # 4. 验证: 应该选择 retreat 而非 aggressive attack
    assert status == NodeStatus.SUCCESS
    assert ctx.chosen_action == "retreat"
    
    # 5. 验证: 瞄准系统使用 defensive 模式
    aim_result = aiming.aim(player, target, shot_type=ShotType.DEFENSIVE)
    assert aim_result.confidence > 0.5


def test_orchestrator_evaluation_feedback():
    """
    验证: Orchestrator → EvaluationSystem → 参数调整
    
    预期:
    - 决策被记录到评估系统
    - 评估系统生成参数调整建议
    - 调整被应用回 Orchestrator
    """
    # 1. 运行 orchestrator 一段时间
    for i in range(100):
        control = orchestrator.update(msg.to_dict())
        evaluation.update(
            decision="attack",
            action=control.action_type,
            outcome="success" if control.confidence > 0.5 else "failure",
            latency_ms=control.latency,
            state=msg.to_dict(),
        )
    
    # 2. 获取性能报告
    report = evaluation.evaluate_and_optimize()
    
    # 3. 验证: 命中率低应该触发瞄准参数调整
    if report["metrics"].hit_rate < 0.3:
        suggestions = report["suggestions"]
        assert any(s["param"] == "aim_lead_factor" for s in suggestions)
    
    # 4. 应用调整
    evaluation.apply_best_adjustments()
    
    # 5. 验证: Orchestrator 使用新参数
    assert orchestrator.aiming_lead_factor == 0.5  # 调整后的值
```

### 4.2 端到端数据追踪测试

```python
def test_full_pipeline_data_trace():
    """
    追踪单个帧的完整数据流动
    
    输入: RawMessage (frame 100)
    期望输出: ControlOutput
    
    追踪:
    1. RawMessage → DataProcessor → GameStateData
    2. GameStateData → EnvironmentModel → EnvironmentQuery
    3. GameStateData → ThreatAnalyzer → ThreatAssessment
    4. + ThreatAssessment → BehaviorTree → NodeStatus
    5. + GameStateData → SmartAiming → AimResult
    6. + 以上 → Orchestrator → ControlOutput
    
    验证每个阶段的中间结果
    """
    # 记录每个阶段的输入输出
    trace = {}
    
    # 1. DataProcessor
    state = processor.process_message(raw_msg)
    trace["processor"] = {
        "input": raw_msg,
        "output": state,
        "player_count": len(state.players),
        "enemy_count": len(state.enemies),
    }
    
    # 2. Environment
    env_query = env_model.update_room(state.room_info, state.enemies, state.projectiles)
    trace["environment"] = {
        "input": (state.room_info, state.enemies),
        "output": env_query,
        "safe_spots": len(env_query.safe_spots) if env_query else 0,
    }
    
    # 3. ThreatAnalyzer
    threat = threat_analyzer.analyze(state)
    trace["threat"] = {
        "input": state,
        "output": threat,
        "level": threat.overall_threat_level.name,
        "immediate_count": len(threat.immediate_threats),
    }
    
    # 4. BehaviorTree
    bt_ctx = NodeContext()
    bt_ctx.game_state = state
    bt_status = behavior_tree.update()
    trace["behavior_tree"] = {
        "input": state,
        "output": bt_status,
        "action": bt_ctx.chosen_action,
    }
    
    # 5. SmartAiming
    aim_result = aiming.aim(player_pos, target, ShotType.NORMAL)
    trace["aiming"] = {
        "input": (player_pos, target),
        "output": aim_result,
        "direction": (aim_result.direction.x, aim_result.direction.y),
        "confidence": aim_result.confidence,
    }
    
    # 6. Orchestrator (已经内部整合了以上)
    control = orchestrator.update(raw_msg)
    trace["orchestrator"] = {
        "input": raw_msg,
        "output": control,
        "move": (control.move_x, control.move_y),
        "shoot": control.shoot,
    }
    
    # 打印完整追踪
    for stage, data in trace.items():
        print(f"\n=== {stage.upper()} ===")
        for key, value in data.items():
            print(f"  {key}: {value}")
    
    # 最终验证
    assert trace["processor"]["player_count"] == 1
    assert trace["threat"]["level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert trace["aiming"]["confidence"] > 0
    assert -1 <= trace["orchestrator"]["move"][0] <= 1
```

## 5. 总结

### 已实现的数据流
- ✅ RawMessage → DataProcessor → GameStateData
- ✅ GameStateData → 各分析模块 (Threat, Environment, Aiming)
- ✅ Orchestrator 整合所有模块输出

### 缺失的数据流验证
- ❌ 模块间中间结果的传递验证
- ❌ 反馈回路 (Evaluation → Orchestrator 参数调整)
- ❌ 条件依赖 (Environment 结果影响 Threat 分析)

### 建议的测试增强
1. **DataFlowTest 类**: 专门验证模块间数据传递
2. **TraceTest 类**: 端到端数据追踪
3. **FeedbackTest 类**: 验证自适应参数调整闭环

当前的测试主要验证每个模块的**独立功能**，而非**模块间的集成**。要全面验证数据流，需要添加专门的集成测试。
