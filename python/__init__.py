"""
SocketBridge AI Combat System

A complete AI control framework for The Binding of Isaac: Repentance.

Quick Start:
    from socketbridge import SimpleAI, IsaacBridge
"""

__version__ = "2.0.0"

# Core - Data structures and processing
from .models import (
    Vector2D,
    PlayerData,
    EnemyData,
    ProjectileData,
    GameStateData,
    RoomInfo,
    RoomLayout,
)

# Bridge - Game communication
from .isaac_bridge import IsaacBridge, GameDataAccessor, GameState, Event
from .data_recorder import GameDataRecorder, DataInspector

# Combat - Main orchestrators
from .orchestrator import CombatOrchestrator, SimpleAI, AIConfig, CombatState
from .orchestrator_enhanced import EnhancedCombatOrchestrator

# Controllers - Movement and attack control
from .basic_controllers import BasicControllerManager, ControlOutput
from .advanced_control import AdvancedMovementController, TrajectoryOptimizer, PIDConfig

# AI Decision - Strategy selection
from .state_machine import (
    HierarchicalStateMachine,
    BattleState,
    MovementState,
    SpecialState,
    StateMachineConfig,
)
from .strategy_system import (
    StrategyManager,
    StrategyType,
    StrategyWeights,
    StrategyEvaluation,
    GameContext,
)

# AI Behavior - Behavior tree framework
from .behavior_tree import (
    BehaviorTree,
    CombatBehaviorTree,
    NodeStatus,
    NodeContext,
    SelectorNode,
    SequenceNode,
    ConditionNode,
    ActionNode,
)
from .evaluation_system import PerformanceMetrics, AdjustmentSuggestion

# Analysis - Threat assessment and path planning
from .threat_analysis import (
    ThreatAnalyzer,
    ThreatAssessment,
    ThreatLevel,
    ThreatAssessor,
    ThreatInfo,
)
from .pathfinding import (
    DynamicPathPlanner,
    PathExecutor,
    AStarPathfinder,
    PathfindingConfig,
)

# Utils - Advanced control systems
from .smart_aiming import SmartAimingSystem, AimConfig, AimingPatternSelector
from .adaptive_system import (
    AdaptiveParameterSystem,
    ScenarioType,
    ScenarioConfig,
    ScenarioDetector,
)

__all__ = [
    # Version
    "__version__",
    # Core
    "Vector2D",
    "PlayerData",
    "EnemyData",
    "ProjectileData",
    "GameStateData",
    "RoomInfo",
    "RoomLayout",
    # Bridge
    "IsaacBridge",
    "GameDataAccessor",
    "GameState",
    "Event",
    "GameDataRecorder",
    "DataInspector",
    # Combat
    "CombatOrchestrator",
    "SimpleAI",
    "AIConfig",
    "CombatState",
    "EnhancedCombatOrchestrator",
    # Controllers
    "BasicControllerManager",
    "ControlOutput",
    "AdvancedMovementController",
    "TrajectoryOptimizer",
    "PIDConfig",
    # AI Decision
    "HierarchicalStateMachine",
    "BattleState",
    "MovementState",
    "SpecialState",
    "StateMachineConfig",
    "StrategyManager",
    "StrategyType",
    "StrategyWeights",
    "StrategyEvaluation",
    "GameContext",
    # AI Behavior
    "BehaviorTree",
    "CombatBehaviorTree",
    "NodeStatus",
    "NodeContext",
    "SelectorNode",
    "SequenceNode",
    "ConditionNode",
    "ActionNode",
    "PerformanceMetrics",
    "AdjustmentSuggestion",
    # Analysis
    "ThreatAnalyzer",
    "ThreatAssessment",
    "ThreatLevel",
    "ThreatAssessor",
    "ThreatInfo",
    "DynamicPathPlanner",
    "PathExecutor",
    "AStarPathfinder",
    "PathfindingConfig",
    # Utils
    "SmartAimingSystem",
    "AimConfig",
    "AimingPatternSelector",
    "AdaptiveParameterSystem",
    "ScenarioType",
    "ScenarioConfig",
    "ScenarioDetector",
]
