"""
AI Combat System

以撒的结合 AI 战斗控制系统 - 完整实现

模块结构:
- perception: 感知模块 (数据解析、环境建模、状态追踪)
- analysis: 分析模块 (威胁评估、机会评估、位置评估、资源分析)
- decision: 决策模块 (高层策略、行动意图生成)
- planning: 规划模块 (路径规划、攻击规划、时序规划、风险管理)
- control: 控制模块 (运动控制、攻击控制、输入合成)
- evaluation: 评估模块 (效果评估、错误分析、学习适配)
- orchestrator: 主控模块 (状态机、优先级管理、配置管理)

使用示例:
    from ai_combat_system import create_orchestrator, SystemConfig

    # 创建系统
    config = SystemConfig()
    orchestrator = create_orchestrator(config)
    orchestrator.initialize()

    # 处理游戏帧
    command = orchestrator.process_frame(raw_data, frame)

    # 发送输入
    bridge.send_input(
        move=command.move,
        shoot=command.shoot,
        use_item=command.use_item
    )
"""

from .perception import (
    PerceptionModule,
    GameState,
    PlayerState,
    EnemyState,
    ProjectileState,
    RoomLayout,
    Obstacle,
    HazardZone,
    Vector2D,
    ThreatLevel,
    EntityType,
    MovementPattern,
    create_perception_module,
)

from .analysis import (
    AnalysisModule,
    SituationAssessment,
    ThreatInfo,
    OpportunityInfo,
    PositionScore,
    ResourceStatus,
    ActionPriority,
    create_analysis_module,
)

from .decision import (
    DecisionModule,
    ActionIntent,
    ActionType,
    StrategyProfile,
    DecisionContext,
    create_decision_module,
)

from .planning import (
    PlanningModule,
    ExecutionPlan,
    PathSegment,
    PathSegmentType,
    TimingWindow,
    RiskAssessment,
    create_planning_module,
)

from .control import (
    ControlModule,
    InputCommand,
    MovementState,
    MovementController,
    AttackController,
    InputSynthesizer,
    create_control_module,
)

from .evaluation import (
    EvaluationModule,
    PerformanceStats,
    ErrorReport,
    PerformanceMetric,
    EffectivenessEvaluator,
    ErrorAnalyzer,
    LearningAdapter,
    PerformanceMonitor,
    create_evaluation_module,
)

from .orchestrator import (
    Orchestrator,
    StateMachine,
    PriorityManager,
    Logger,
    CombatState,
    MovementState,
    SpecialState,
    SystemConfig,
    SystemStatus,
    create_orchestrator,
)

__version__ = "1.0.0"
__author__ = "AI Combat System"

__all__ = [
    # 版本
    "__version__",
    # 感知模块
    "PerceptionModule",
    "GameState",
    "PlayerState",
    "EnemyState",
    "ProjectileState",
    "RoomLayout",
    "Obstacle",
    "HazardZone",
    "Vector2D",
    "ThreatLevel",
    "EntityType",
    "MovementPattern",
    "create_perception_module",
    # 分析模块
    "AnalysisModule",
    "SituationAssessment",
    "ThreatInfo",
    "OpportunityInfo",
    "PositionScore",
    "ResourceStatus",
    "ActionPriority",
    "create_analysis_module",
    # 决策模块
    "DecisionModule",
    "ActionIntent",
    "ActionType",
    "StrategyProfile",
    "DecisionContext",
    "create_decision_module",
    # 规划模块
    "PlanningModule",
    "ExecutionPlan",
    "PathSegment",
    "PathSegmentType",
    "TimingWindow",
    "RiskAssessment",
    "create_planning_module",
    # 控制模块
    "ControlModule",
    "InputCommand",
    "MovementState",
    "MovementController",
    "AttackController",
    "InputSynthesizer",
    "create_control_module",
    # 评估模块
    "EvaluationModule",
    "PerformanceStats",
    "ErrorReport",
    "PerformanceMetric",
    "EffectivenessEvaluator",
    "ErrorAnalyzer",
    "LearningAdapter",
    "PerformanceMonitor",
    "create_evaluation_module",
    # 主控模块
    "Orchestrator",
    "StateMachine",
    "PriorityManager",
    "Logger",
    "CombatState",
    "MovementState",
    "SpecialState",
    "SystemConfig",
    "SystemStatus",
    "create_orchestrator",
]
