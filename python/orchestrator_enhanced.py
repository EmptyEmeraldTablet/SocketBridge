"""
Enhanced AI Combat Control System - Main Controller Module

Integrates all sub-modules to implement a complete AI combat decision-making process:
1. Perception Module → Data parsing and environment modeling
2. Analysis Module → Threat assessment and situation analysis
3. Decision Module → Action intention generation
4. Planning Module → Detailed execution plan
5. Control Module → Game input commands

Architecture based on reference.md, integrating:
- Phase 1: Basic Control (basic_controllers)
- Phase 2: Threat Analysis (threat_analysis), Path Planning (pathfinding)
- Phase 3: State Machine (state_machine), Strategy System (strategy_system), Behavior Tree (behavior_tree)
- Phase 4: Advanced Control (advanced_control), Smart Aiming (smart_aiming), Adaptive System (adaptive_system)
"""

import math
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from models import (
    Vector2D,
    GameStateData,
    PlayerData,
    EnemyData,
    ProjectileData,
    RoomInfo,
    RoomLayout,
)
from data_processor import DataProcessor
from environment import GameMap, EnvironmentModel
from basic_controllers import BasicControllerManager, ControlOutput
from pathfinding import DynamicPathPlanner, PathExecutor
from threat_analysis import ThreatAnalyzer, ThreatAssessment, ThreatLevel

# Phase 3 modules
from state_machine import (
    HierarchicalStateMachine,
    BattleState,
    MovementState,
    SpecialState,
    StateMachineConfig,
)
from strategy_system import (
    StrategyManager,
    StrategyType,
    StrategyWeights,
    GameContext,
)
from behavior_tree import (
    BehaviorTree,
    CombatBehaviorTree,
    NodeContext,
    NodeStatus,
)

# Phase 4 modules
from advanced_control import (
    AdvancedMovementController,
    TrajectoryOptimizer,
    TrajectoryPoint,
)
from smart_aiming import (
    SmartAimingSystem,
    AimConfig,
)
from adaptive_system import (
    AdaptiveParameterSystem,
    ScenarioType,
)

logger = logging.getLogger("EnhancedOrchestrator")


class CombatState(Enum):
    """Combat state (backward compatibility)"""

    IDLE = "idle"
    EXPLORING = "exploring"
    COMBAT = "combat"
    EVASION = "evasion"
    RETREATING = "retreating"
    HEALING = "healing"


@dataclass
class AIConfig:
    """AI Configuration"""

    # Decision frequency
    decision_interval: float = 0.05  # 50ms = 20Hz

    # Threat thresholds
    immediate_threat_threshold: float = 0.5
    combat_engage_distance: float = 300.0
    retreat_health_threshold: float = 0.3

    # Behavior parameters
    attack_aggression: float = 0.7  # Attack tendency 0-1
    defense_preference: float = 0.5  # Defense tendency 0-1
    movement_style: str = "kiting"  # "kiting", "aggressive", "defensive"

    # Module enable/disable
    enable_pathfinding: bool = True
    enable_threat_analysis: bool = True
    enable_adaptive_behavior: bool = True  # Enable Phase 4 adaptive system
    enable_behavior_tree: bool = True  # Enable Phase 3 behavior tree
    enable_advanced_control: bool = True  # Enable Phase 4 advanced control


class EnhancedCombatOrchestrator:
    """Enhanced Combat System Controller

    Integrates all Phase 1-4 modules for complete AI combat control.
    """

    def __init__(self, config: AIConfig = None):
        self.config = config or AIConfig()

        # Phase 1: Basic subsystems
        self.data_processor = DataProcessor()
        self.environment = EnvironmentModel()
        self.controllers = BasicControllerManager()
        self.path_planner = DynamicPathPlanner()
        self.path_executor = PathExecutor(self.path_planner)
        self.threat_analyzer = ThreatAnalyzer()

        # Phase 3: Advanced decision modules
        state_config = StateMachineConfig()
        self.hierarchical_sm = HierarchicalStateMachine(state_config)
        self.strategy_manager = StrategyManager(StrategyWeights())
        self.behavior_tree: Optional[BehaviorTree] = None
        if self.config.enable_behavior_tree:
            self.behavior_tree = CombatBehaviorTree.create_combat_tree()

        # Phase 4: Advanced control modules
        if self.config.enable_advanced_control:
            self.advanced_movement = AdvancedMovementController()
            self.trajectory_optimizer = TrajectoryOptimizer()
            self.smart_aiming = SmartAimingSystem(AimConfig())
        if self.config.enable_adaptive_behavior:
            self.adaptive_system = AdaptiveParameterSystem()

        # State
        self.current_state = CombatState.IDLE
        self.last_decision_time = 0.0
        self.current_target: Optional[EnemyData] = None
        self.is_enabled = True

        # Statistics
        self.stats = {
            "decisions": 0,
            "threat_assessments": 0,
            "paths_planned": 0,
            "damage_taken": 0,
            "enemies_killed": 0,
            "state_transitions": 0,
            "strategy_changes": 0,
            "behavior_tree_executions": 0,
            "adaptive_adjustments": 0,
            "start_time": None,
        }

    def initialize(self):
        """Initialize"""
        self.stats["start_time"] = time.time()
        logger.info("Enhanced Combat Orchestrator initialized")

    def update(self, raw_message: Dict[str, Any]) -> ControlOutput:
        """
        Main update loop

        Args:
            raw_message: Raw message from game

        Returns:
            Control output
        """
        if not self.is_enabled:
            return ControlOutput()

        # 1. Parse data
        game_state = self.data_processor.process_message(raw_message)

        # 2. Update environment model
        player = game_state.get_primary_player()
        if not player:
            return ControlOutput()

        self.environment.update_room(
            game_state.room_layout,
            game_state.room_info,
            game_state.enemies,
            game_state.enemy_projectiles,
        )

        # 3. Threat analysis
        threat_assessment = None
        if self.config.enable_threat_analysis:
            threat_assessment = self.threat_analyzer.analyze(
                player.position,
                game_state.enemies,
                game_state.enemy_projectiles,
                current_frame=game_state.frame,
            )

        # 4. Enhanced decision making (Phase 3 + Phase 4)
        decision = self._make_enhanced_decision(game_state, threat_assessment)

        # 5. Execute control
        control = self._execute_enhanced_decision(
            game_state, decision, threat_assessment
        )

        # Update statistics
        self.stats["decisions"] += 1
        if threat_assessment:
            self.stats["threat_assessments"] += 1

        return control

    def _make_enhanced_decision(
        self,
        game_state: GameStateData,
        threat_assessment: Optional[ThreatAssessment],
    ) -> Dict[str, Any]:
        """Make enhanced decision using Phase 3 modules"""
        player = game_state.get_primary_player()
        if not player:
            return {"state": CombatState.IDLE, "action": "idle"}

        # Phase 4: Update adaptive system
        if self.config.enable_adaptive_behavior:
            self._update_adaptive_system(game_state)

        # Phase 3: Update hierarchical state machine
        battle_states = self._update_hierarchical_state_machine(
            game_state, threat_assessment
        )

        # Phase 3: Evaluate strategies
        strategy, strategy_eval = self._evaluate_strategy(game_state, threat_assessment)

        # Phase 3: Execute behavior tree
        bt_action = self._execute_behavior_tree(game_state, threat_assessment)

        # Determine final state based on all inputs
        new_state = self._determine_final_state(
            battle_states, threat_assessment, player
        )

        # Build comprehensive decision
        decision = {
            "state": new_state,
            "battle_state": battle_states.get("battle"),
            "movement_state": battle_states.get("movement"),
            "special_state": battle_states.get("special"),
            "strategy": strategy,
            "strategy_evaluation": strategy_eval,
            "behavior_tree_action": bt_action,
            "target": self._select_target(game_state),
            "movement_type": self._get_movement_type(battle_states, strategy),
            "should_attack": self._should_attack(battle_states, strategy),
            "should_dodge": self._should_dodge(threat_assessment),
            "retreat": self._should_retreat(player, threat_assessment),
            "heal": self._should_heal(player),
        }

        # Update current state
        if self.current_state != new_state:
            self.stats["state_transitions"] += 1
            self.current_state = new_state

        return decision

    def _update_hierarchical_state_machine(
        self,
        game_state: GameStateData,
        threat_assessment: Optional[ThreatAssessment],
    ) -> Dict[str, Any]:
        """Update hierarchical state machine"""
        player = game_state.get_primary_player()
        if not player:
            return {
                "battle": BattleState.IDLE,
                "movement": MovementState.EXPLORING,
                "special": SpecialState.NONE,
            }

        threat_level = (
            threat_assessment.overall_threat_level.value if threat_assessment else 0.0
        )
        enemy_count = len(game_state.enemies) if game_state.enemies else 0
        has_projectiles = (
            len(game_state.enemy_projectiles) > 0
            if game_state.enemy_projectiles
            else False
        )
        can_heal = self._has_healing_items(player)

        target = self._select_target(game_state)
        target_distance = 0.0
        if target and player:
            target_distance = math.sqrt(
                (target.position.x - player.position.x) ** 2
                + (target.position.y - player.position.y) ** 2
            )

        return self.hierarchical_sm.update(
            threat_level=threat_level,
            player_health=player.health_percentage,
            enemy_count=enemy_count,
            has_projectiles=has_projectiles,
            can_heal=can_heal,
            has_target=target is not None,
            target_distance=target_distance,
        )

    def _evaluate_strategy(
        self,
        game_state: GameStateData,
        threat_assessment: Optional[ThreatAssessment],
    ) -> Tuple[Optional[StrategyType], Any]:
        """Evaluate and select strategy"""
        player = game_state.get_primary_player()
        if not player:
            return None, None

        # Build game context
        context = GameContext(
            player_health=player.health_percentage,
            player_position_x=player.position.x,
            player_position_y=player.position.y,
            enemy_count=len(game_state.enemies) if game_state.enemies else 0,
            nearest_enemy_distance=self._get_nearest_enemy_distance(player, game_state),
            highest_threat_level=threat_assessment.overall_threat_level.value
            if threat_assessment
            else 0.0,
            has_healing=self._has_healing_items(player),
            room_cleared=game_state.room_info.is_clear
            if game_state.room_info
            else True,
            room_center_x=game_state.room_info.center.x
            if game_state.room_info and hasattr(game_state.room_info, "center")
            else 0,
            room_center_y=game_state.room_info.center.y
            if game_state.room_info and hasattr(game_state.room_info, "center")
            else 0,
            in_combat=len(game_state.enemies) > 0 if game_state.enemies else False,
            projectiles_incoming=len(game_state.enemy_projectiles)
            if game_state.enemy_projectiles
            else 0,
        )

        strategy, evaluation = self.strategy_manager.decide_and_execute(context)

        if strategy != self.strategy_manager.decider.current_strategy:
            if self.strategy_manager.decider.current_strategy is not None:
                self.stats["strategy_changes"] += 1

        return strategy, evaluation

    def _execute_behavior_tree(
        self,
        game_state: GameStateData,
        threat_assessment: Optional[ThreatAssessment],
    ) -> str:
        """Execute behavior tree and return action"""
        if not self.behavior_tree or not self.config.enable_behavior_tree:
            return "disabled"

        player = game_state.get_primary_player()
        if not player:
            return "no_player"

        # Build node context
        node_context = NodeContext(
            game_state=game_state,
            player_health=player.health_percentage,
            player_position=(player.position.x, player.position.y),
            enemies=[e for e in game_state.enemies.values()]
            if game_state.enemies
            else [],
            threat_level=threat_assessment.overall_threat_level.value
            if threat_assessment
            else 0.0,
            projectiles=list(game_state.enemy_projectiles.values())
            if game_state.enemy_projectiles
            else [],
            room_info=game_state.room_info,
        )

        # Execute behavior tree
        result = self.behavior_tree.execute(node_context)
        self.stats["behavior_tree_executions"] += 1

        return self.behavior_tree.get_last_action() or result.value

    def _update_adaptive_system(self, game_state: GameStateData):
        """Update adaptive parameter system"""
        if (
            not hasattr(self, "adaptive_system")
            or not self.config.enable_adaptive_behavior
        ):
            return

        # Build game state dict for detector
        game_state_dict = {
            "enemies": [
                {
                    "is_boss": getattr(e, "is_boss", False),
                    "type": getattr(e, "type", 0),
                }
                for e in game_state.enemies.values()
            ]
            if game_state.enemies
            else [],
            "room_info": {
                "grid_width": game_state.room_info.grid_width
                if game_state.room_info
                else 13,
                "grid_height": game_state.room_info.grid_height
                if game_state.room_info
                else 7,
            }
            if game_state.room_info
            else {},
        }

        # Performance metrics
        performance_metrics = {
            "hit_rate": self.smart_aiming.get_accuracy()
            if hasattr(self, "smart_aiming")
            else 0.5,
            "dodge_rate": 0.5,  # Simplified - would need actual tracking
            "damage_taken": self.stats["damage_taken"],
        }

        self.adaptive_system.update(game_state_dict, performance_metrics)
        self.stats["adaptive_adjustments"] += 1

    def _determine_final_state(
        self,
        battle_states: Dict[str, Any],
        threat_assessment: Optional[ThreatAssessment],
        player: PlayerData,
    ) -> CombatState:
        """Determine final combat state from all inputs"""
        # Priority 1: Evasion
        if threat_assessment:
            if threat_assessment.overall_threat_level in [
                ThreatLevel.CRITICAL,
                ThreatLevel.HIGH,
            ]:
                if len(threat_assessment.immediate_threats) >= 2:
                    return CombatState.EVASION

        # Priority 2: Healing
        if player.health_percentage < 0.5 and self._has_healing_items(player):
            return CombatState.HEALING

        # Priority 3: Retreat
        if player.health_percentage < self.config.retreat_health_threshold:
            if battle_states.get("battle") == BattleState.RETREAT:
                return CombatState.RETREATING

        # Priority 4: Combat
        battle_state = battle_states.get("battle")
        if battle_state in [BattleState.AGGRESSIVE, BattleState.DEFENSIVE]:
            return CombatState.COMBAT

        # Priority 5: Evasion from behavior tree
        if battle_states.get("battle") == BattleState.DODGE:
            return CombatState.EVASION

        # Priority 6: Exploration
        if battle_state == BattleState.IDLE:
            return CombatState.EXPLORING

        return CombatState.IDLE

    def _get_movement_type(
        self, battle_states: Dict[str, Any], strategy: Optional[StrategyType]
    ) -> str:
        """Determine movement type from state and strategy"""
        movement_state = battle_states.get("movement")

        if movement_state == MovementState.FLEEING:
            return "evade"
        elif movement_state == MovementState.CHASING:
            return "aggressive" if strategy == StrategyType.AGGRESSIVE else "kiting"
        elif movement_state == MovementState.POSITIONING:
            return "defensive"
        elif movement_state == MovementState.EXPLORING:
            return "explore"

        return "idle"

    def _should_attack(
        self, battle_states: Dict[str, Any], strategy: Optional[StrategyType]
    ) -> bool:
        """Determine if should attack"""
        battle_state = battle_states.get("battle")

        if battle_state in [BattleState.AGGRESSIVE]:
            return True
        elif battle_state in [BattleState.DEFENSIVE, BattleState.IDLE]:
            return False
        elif battle_state in [
            BattleState.DODGE,
            BattleState.RETREAT,
            BattleState.HEAL_PRIORITY,
        ]:
            return False

        return False

    def _should_dodge(self, threat_assessment: Optional[ThreatAssessment]) -> bool:
        """Determine if should dodge"""
        if not threat_assessment:
            return False

        return threat_assessment.overall_threat_level in [
            ThreatLevel.CRITICAL,
            ThreatLevel.HIGH,
        ]

    def _should_retreat(
        self,
        player: PlayerData,
        threat_assessment: Optional[ThreatAssessment],
    ) -> bool:
        """Determine if should retreat"""
        if not player:
            return False

        # Low health
        if player.health_percentage < self.config.retreat_health_threshold:
            return True

        # Critical threat with multiple projectiles
        if threat_assessment:
            if threat_assessment.overall_threat_level == ThreatLevel.CRITICAL:
                if len(threat_assessment.immediate_threats) >= 3:
                    return True

        return False

    def _should_heal(self, player: PlayerData) -> bool:
        """Determine if should heal"""
        if not player:
            return False

        return player.health_percentage < 0.5 and self._has_healing_items(player)

    def _select_target(self, game_state: GameStateData) -> Optional[EnemyData]:
        """Select attack target"""
        player = game_state.get_primary_player()
        if not player:
            return None

        enemies = game_state.get_active_enemies()
        if not enemies:
            return None

        # Use strategy-based selection
        strategy = self.strategy_manager.decider.current_strategy

        if strategy == StrategyType.AGGRESSIVE:
            # Select nearest
            return game_state.get_nearest_enemy(player.position)
        elif strategy == StrategyType.DEFENSIVE:
            # Select weakest
            wounded = [e for e in enemies if e.hp < e.max_hp * 0.5]
            if wounded:
                return min(wounded, key=lambda e: e.hp)
            return min(enemies, key=lambda e: e.hp)
        elif strategy == StrategyType.EVASIVE:
            # Select furthest
            return max(enemies, key=lambda e: e.distance)
        else:
            # Default: balanced approach
            return game_state.get_nearest_enemy(player.position)

    def _get_nearest_enemy_distance(
        self, player: PlayerData, game_state: GameStateData
    ) -> float:
        """Get distance to nearest enemy"""
        enemies = game_state.get_active_enemies()
        if not enemies or not player:
            return 9999.0

        nearest = game_state.get_nearest_enemy(player.position)
        if not nearest:
            return 9999.0

        return math.sqrt(
            (nearest.position.x - player.position.x) ** 2
            + (nearest.position.y - player.position.y) ** 2
        )

    def _execute_enhanced_decision(
        self,
        game_state: GameStateData,
        decision: Dict[str, Any],
        threat_assessment: Optional[ThreatAssessment],
    ) -> ControlOutput:
        """Execute enhanced decision using Phase 4 modules"""
        player = game_state.get_primary_player()
        if not player:
            return ControlOutput()

        # Phase 4: Advanced movement control
        if self.config.enable_advanced_control and decision["movement_type"] in [
            "defensive",
            "positioning",
        ]:
            return self._execute_advanced_movement(game_state, decision)

        # Phase 4: Smart aiming
        if decision["should_attack"] and decision["target"]:
            return self._execute_smart_aiming(game_state, decision)

        # Standard execution for other cases
        return self._execute_standard_decision(game_state, decision, threat_assessment)

    def _execute_advanced_movement(
        self,
        game_state: GameStateData,
        decision: Dict[str, Any],
    ) -> ControlOutput:
        """Execute advanced movement control"""
        if (
            not hasattr(self, "advanced_movement")
            or not self.config.enable_advanced_control
        ):
            return self._execute_standard_decision(game_state, decision, None)

        player = game_state.get_primary_player()
        if not player:
            return ControlOutput()

        # Determine target position based on decision
        target_pos = self._get_movement_target(game_state, decision)
        if not target_pos:
            return ControlOutput()

        # Set target for advanced controller
        self.advanced_movement.set_target(
            position=(target_pos.x, target_pos.y),
            velocity=(0, 0),
        )

        # Get current velocity
        current_vel = (player.velocity.x, player.velocity.y)

        # Compute control output
        control_output = self.advanced_movement.update(
            current_pos=(player.position.x, player.position.y),
            current_vel=current_vel,
            dt=0.016,  # Approximate 60fps
        )

        return ControlOutput(
            move_x=control_output[0],
            move_y=control_output[1],
            confidence=0.85,
            reasoning=f"advanced_movement_{decision['movement_type']}",
        )

    def _execute_smart_aiming(
        self,
        game_state: GameStateData,
        decision: Dict[str, Any],
    ) -> ControlOutput:
        """Execute smart aiming with prediction"""
        if not hasattr(self, "smart_aiming") or not self.config.enable_advanced_control:
            return self._execute_standard_decision(game_state, decision, None)

        player = game_state.get_primary_player()
        target = decision["target"]
        if not player or not target:
            return ControlOutput()

        # Get target velocity
        target_vel = (target.velocity.x, target.velocity.y)

        # Calculate smart aim direction
        aim_dir = self.smart_aiming.aim(
            shooter_pos=(player.position.x, player.position.y),
            target_pos=(target.position.x, target.position.y),
            target_vel=target_vel,
            enemy_type=target.type,
        )

        return self.controllers.compute_control(
            game_state,
            target_enemy=target,
            shoot_override=aim_dir,
        )

    def _get_movement_target(
        self,
        game_state: GameStateData,
        decision: Dict[str, Any],
    ) -> Optional[Vector2D]:
        """Get movement target position"""
        player = game_state.get_primary_player()
        if not player:
            return None

        # Get safe spot for positioning
        safe_spot = self.environment.get_safe_spot(
            player.position, min_distance=50, max_distance=200
        )

        if safe_spot:
            return Vector2D(x=safe_spot[0], y=safe_spot[1])

        # Default to room center
        if game_state.room_info and hasattr(game_state.room_info, "center"):
            return game_state.room_info.center

        return None

    def _execute_standard_decision(
        self,
        game_state: GameStateData,
        decision: Dict[str, Any],
        threat_assessment: Optional[ThreatAssessment],
    ) -> ControlOutput:
        """Execute standard decision (fallback)"""
        player = game_state.get_primary_player()
        if not player:
            return ControlOutput()

        # Handle evasion
        if decision["should_dodge"] and threat_assessment:
            evade_threats = [
                game_state.enemy_projectiles.get(t.source_id)
                for t in threat_assessment.immediate_threats
                if t.source_id in game_state.enemy_projectiles
            ]
            return self.controllers.compute_control(
                game_state,
                target_enemy=decision["target"],
                evade_threats=[t for t in evade_threats if t is not None],
            )

        # Handle combat
        if decision["should_attack"]:
            return self.controllers.compute_control(
                game_state, target_enemy=decision["target"]
            )

        # Handle retreat
        if decision["retreat"]:
            return self._handle_retreat(game_state)

        # Handle healing
        if decision["heal"]:
            return self._handle_healing(game_state)

        # Handle exploration
        if decision["movement_type"] == "explore":
            return self._handle_explore(game_state)

        return ControlOutput()

    def _handle_retreat(self, game_state: GameStateData) -> ControlOutput:
        """Handle retreat"""
        player = game_state.get_primary_player()
        if not player:
            return ControlOutput()

        safe_pos = self.environment.get_safe_spot(
            player.position, min_distance=100, max_distance=300
        )

        if safe_pos:
            move = self.path_executor.execute_to(player.position, safe_pos)
            return ControlOutput(
                move_x=move[0],
                move_y=move[1],
                confidence=0.9,
                reasoning="retreat",
            )

        # Emergency fallback
        return ControlOutput(
            move_x=-1 if player.position.x > 400 else 1,
            move_y=0,
            confidence=0.7,
            reasoning="retreat_emergency",
        )

    def _handle_healing(self, game_state: GameStateData) -> ControlOutput:
        """Handle healing"""
        return ControlOutput(
            move_x=0,
            move_y=0,
            use_item=True,
            confidence=0.9,
            reasoning="healing",
        )

    def _handle_explore(self, game_state: GameStateData) -> ControlOutput:
        """Handle exploration"""
        player = game_state.get_primary_player()
        if not player:
            return ControlOutput()

        if game_state.room_info and hasattr(game_state.room_info, "center"):
            center = game_state.room_info.center
            direction = center - player.position
            move_x = 1 if direction.x > 0 else -1 if direction.x < 0 else 0
            move_y = 1 if direction.y > 0 else -1 if direction.y < 0 else 0

            return ControlOutput(
                move_x=move_x,
                move_y=move_y,
                confidence=0.6,
                reasoning="exploring",
            )

        return ControlOutput()

    def _has_healing_items(self, player: PlayerData) -> bool:
        """Check if player has healing items"""
        for slot, item in player.active_items.items():
            item_id = item.get("item", 0)
            if item_id in [2, 3]:
                return True
        return player.red_hearts < player.max_hearts / 2

    def on_player_damage(self, damage: int, hp_after: int):
        """Player damage callback"""
        self.stats["damage_taken"] += damage

        if hp_after <= 2:
            self.config.defense_preference = min(
                1.0, self.config.defense_preference + 0.2
            )

    def on_enemy_killed(self, enemy: EnemyData):
        """Enemy killed callback"""
        self.stats["enemies_killed"] += 1

        if self.current_target and self.current_target.id == enemy.id:
            self.current_target = None

    def on_room_entered(self, room_info: RoomInfo):
        """Room entered callback"""
        logger.info(f"Entered room {room_info.room_index}")

        self.current_target = None
        self.path_planner.clear_dynamic_obstacles()

        # Reset behavior tree
        if self.behavior_tree:
            self.behavior_tree.reset()

    def on_room_cleared(self):
        """Room cleared callback"""
        logger.info("Room cleared!")
        self.current_state = CombatState.EXPLORING

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        uptime = time.time() - (self.stats["start_time"] or time.time())

        return {
            **self.stats,
            "uptime": uptime,
            "decisions_per_second": self.stats["decisions"] / max(1, uptime),
            "current_state": self.current_state.value,
            "config": {
                "attack_aggression": self.config.attack_aggression,
                "defense_preference": self.config.defense_preference,
                "movement_style": self.config.movement_style,
            },
            "hierarchical_state": self.hierarchical_sm.get_comprehensive_stats()
            if hasattr(self, "hierarchical_sm")
            else {},
            "strategy": self.strategy_manager.get_current_strategy_info()
            if hasattr(self, "strategy_manager")
            else {},
        }

    def set_aggression(self, level: float):
        """Set attack aggression"""
        self.config.attack_aggression = max(0, min(1, level))
        logger.info(f"Aggression set to {level:.2f}")

    def set_movement_style(self, style: str):
        """Set movement style"""
        if style in ["kiting", "aggressive", "defensive"]:
            self.config.movement_style = style
            logger.info(f"Movement style set to {style}")

    def enable(self):
        """Enable AI"""
        self.is_enabled = True
        logger.info("AI enabled")

    def disable(self):
        """Disable AI"""
        self.is_enabled = False
        logger.info("AI disabled")

    def reset(self):
        """Reset state"""
        self.current_state = CombatState.IDLE
        self.current_target = None
        self.path_planner.clear_dynamic_obstacles()

        if hasattr(self, "hierarchical_sm"):
            self.hierarchical_sm.reset()
        if self.behavior_tree:
            self.behavior_tree.reset()

        logger.info("Enhanced Orchestrator reset")


class SimpleAI:
    """Simple AI wrapper for quick integration"""

    def __init__(self, use_enhanced: bool = True):
        if use_enhanced:
            self.orchestrator = EnhancedCombatOrchestrator()
        else:
            self.orchestrator = CombatOrchestrator()
        self.orchestrator.initialize()
        self._connected = False

    def connect(self):
        """Connect (start AI)"""
        self.orchestrator.enable()
        self._connected = True
        logger.info("AI connected")

    def disconnect(self):
        """Disconnect"""
        self.orchestrator.disable()
        self._connected = False
        logger.info("AI disconnected")

    def update(
        self, game_data: Dict[str, Any]
    ) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        Update AI

        Args:
            game_data: Game data

        Returns:
            (movement direction, shooting direction)
        """
        if not self._connected:
            return (0, 0), (0, 0)

        control = self.orchestrator.update(game_data)

        move = (control.move_x, control.move_y)
        shoot = (control.shoot_x, control.shoot_y) if control.shoot else (0, 0)

        return move, shoot

    def on_damage(self, damage: int, hp_after: int):
        """Player damage"""
        self.orchestrator.on_player_damage(damage, hp_after)

    def on_room_enter(self, room_data: Dict[str, Any]):
        """Enter room"""
        self.orchestrator.on_room_entered(
            RoomInfo(
                room_index=room_data.get("room_idx", 0),
                enemy_count=room_data.get("enemy_count", 0),
            )
        )

    def on_room_clear(self):
        """Room clear"""
        self.orchestrator.on_room_cleared()

    def set_aggression(self, level: float):
        """Set aggression"""
        self.orchestrator.set_aggression(level)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics"""
        return self.orchestrator.get_performance_stats()


# Backward compatibility class
class CombatOrchestrator:
    """Original Combat Orchestrator (backward compatibility)"""

    def __init__(self, config: AIConfig = None):
        self.config = config or AIConfig()
        self.data_processor = DataProcessor()
        self.environment = EnvironmentModel()
        self.controllers = BasicControllerManager()
        self.path_planner = DynamicPathPlanner()
        self.path_executor = PathExecutor(self.path_planner)
        self.threat_analyzer = ThreatAnalyzer()
        self.current_state = CombatState.IDLE
        self.last_decision_time = 0.0
        self.current_target: Optional[EnemyData] = None
        self.is_enabled = True
        self.stats = {
            "decisions": 0,
            "threat_assessments": 0,
            "paths_planned": 0,
            "damage_taken": 0,
            "enemies_killed": 0,
            "start_time": None,
        }

    def initialize(self):
        self.stats["start_time"] = time.time()
        logger.info("Combat Orchestrator initialized")

    def update(self, raw_message: Dict[str, Any]) -> ControlOutput:
        if not self.is_enabled:
            return ControlOutput()

        game_state = self.data_processor.process_message(raw_message)
        player = game_state.get_primary_player()
        if not player:
            return ControlOutput()

        self.environment.update_room(
            game_state.room_layout,
            game_state.room_info,
            game_state.enemies,
            game_state.enemy_projectiles,
        )

        threat_assessment = None
        if self.config.enable_threat_analysis:
            threat_assessment = self.threat_analyzer.analyze(
                player.position,
                game_state.enemies,
                game_state.enemy_projectiles,
                current_frame=game_state.frame,
            )

        decision = self._make_decision(game_state, threat_assessment)
        control = self._execute_decision(game_state, decision, threat_assessment)

        self.stats["decisions"] += 1
        if threat_assessment:
            self.stats["threat_assessments"] += 1

        return control

    def _make_decision(
        self,
        game_state: GameStateData,
        threat_assessment: Optional[ThreatAssessment],
    ) -> Dict[str, Any]:
        player = game_state.get_primary_player()
        new_state = self._update_combat_state(game_state, threat_assessment)

        decision = {
            "state": new_state,
            "target": None,
            "movement_type": "idle",
            "should_attack": False,
            "should_dodge": False,
            "retreat": False,
            "heal": False,
        }

        if new_state == CombatState.EVASION:
            decision["should_dodge"] = True
            decision["movement_type"] = "evade"
        elif new_state == CombatState.COMBAT:
            decision["should_attack"] = True
            decision["target"] = self._select_target(game_state)
            decision["movement_type"] = self.config.movement_style
        elif new_state == CombatState.RETREATING:
            decision["retreat"] = True
            decision["movement_type"] = "retreat"
        elif new_state == CombatState.HEALING:
            decision["heal"] = True
        elif new_state == CombatState.EXPLORING:
            decision["movement_type"] = "explore"

        self.current_state = new_state
        return decision

    def _update_combat_state(
        self,
        game_state: GameStateData,
        threat_assessment: Optional[ThreatAssessment],
    ) -> CombatState:
        player = game_state.get_primary_player()
        if not player:
            return CombatState.IDLE

        if threat_assessment:
            if threat_assessment.overall_threat_level in [
                ThreatLevel.CRITICAL,
                ThreatLevel.HIGH,
            ]:
                if len(threat_assessment.immediate_threats) >= 2:
                    return CombatState.EVASION

        if player.health_percentage < self.config.retreat_health_threshold:
            enemies = game_state.get_active_enemies()
            if enemies:
                return CombatState.RETREATING

        if player.health_percentage < 0.5 and self._has_healing_items(player):
            return CombatState.HEALING

        if game_state.is_combat_active():
            return CombatState.COMBAT

        if game_state.enemies is None or len(game_state.enemies) == 0:
            return CombatState.EXPLORING

        return CombatState.IDLE

    def _select_target(self, game_state: GameStateData) -> Optional[EnemyData]:
        player = game_state.get_primary_player()
        if not player:
            return None

        enemies = game_state.get_active_enemies()
        if not enemies:
            return None

        if self.config.attack_aggression > 0.7:
            return game_state.get_nearest_enemy(player.position)
        elif self.config.attack_aggression > 0.4:
            wounded = [e for e in enemies if e.hp < e.max_hp * 0.5]
            if wounded:
                return min(wounded, key=lambda e: e.hp)
            return game_state.get_nearest_enemy(player.position)
        else:
            return min(enemies, key=lambda e: e.hp)

    def _execute_decision(
        self,
        game_state: GameStateData,
        decision: Dict[str, Any],
        threat_assessment: Optional[ThreatAssessment],
    ) -> ControlOutput:
        player = game_state.get_primary_player()
        if not player:
            return ControlOutput()

        if decision["should_dodge"] and threat_assessment:
            evade_threats = [
                game_state.enemy_projectiles.get(t.source_id)
                for t in threat_assessment.immediate_threats
                if t.source_id in game_state.enemy_projectiles
            ]
            return self.controllers.compute_control(
                game_state,
                target_enemy=decision["target"],
                evade_threats=[t for t in evade_threats if t is not None],
            )

        if decision["should_attack"]:
            return self.controllers.compute_control(
                game_state, target_enemy=decision["target"]
            )

        if decision["retreat"]:
            return self._handle_retreat(game_state)

        if decision["heal"]:
            return self._handle_healing(game_state)

        if decision["movement_type"] == "explore":
            return self._handle_explore(game_state)

        return ControlOutput()

    def _handle_retreat(self, game_state: GameStateData) -> ControlOutput:
        player = game_state.get_primary_player()
        if not player:
            return ControlOutput()

        safe_pos = self.environment.get_safe_spot(
            player.position, min_distance=100, max_distance=300
        )

        if safe_pos:
            move = self.path_executor.execute_to(player.position, safe_pos)
            return ControlOutput(
                move_x=move[0],
                move_y=move[1],
                confidence=0.9,
                reasoning="retreat",
            )

        return ControlOutput(
            move_x=-1 if player.position.x > 400 else 1,
            move_y=0,
            confidence=0.7,
            reasoning="retreat_emergency",
        )

    def _handle_healing(self, game_state: GameStateData) -> ControlOutput:
        return ControlOutput(
            move_x=0,
            move_y=0,
            use_item=True,
            confidence=0.9,
            reasoning="healing",
        )

    def _handle_explore(self, game_state: GameStateData) -> ControlOutput:
        player = game_state.get_primary_player()
        if not player:
            return ControlOutput()

        if game_state.room_info and hasattr(game_state.room_info, "center"):
            center = game_state.room_info.center
            direction = center - player.position
            move_x = 1 if direction.x > 0 else -1 if direction.x < 0 else 0
            move_y = 1 if direction.y > 0 else -1 if direction.y < 0 else 0

            return ControlOutput(
                move_x=move_x,
                move_y=move_y,
                confidence=0.6,
                reasoning="exploring",
            )

        return ControlOutput()

    def _has_healing_items(self, player: PlayerData) -> bool:
        for slot, item in player.active_items.items():
            item_id = item.get("item", 0)
            if item_id in [2, 3]:
                return True
        return player.red_hearts < player.max_hearts / 2

    def on_player_damage(self, damage: int, hp_after: int):
        self.stats["damage_taken"] += damage
        if hp_after <= 2:
            self.config.defense_preference = min(
                1.0, self.config.defense_preference + 0.2
            )

    def on_enemy_killed(self, enemy: EnemyData):
        self.stats["enemies_killed"] += 1
        if self.current_target and self.current_target.id == enemy.id:
            self.current_target = None

    def on_room_entered(self, room_info: RoomInfo):
        logger.info(f"Entered room {room_info.room_index}")
        self.current_target = None
        self.path_planner.clear_dynamic_obstacles()

    def on_room_cleared(self):
        logger.info("Room cleared!")
        self.current_state = CombatState.EXPLORING

    def get_performance_stats(self) -> Dict[str, Any]:
        uptime = time.time() - (self.stats["start_time"] or time.time())
        return {
            **self.stats,
            "uptime": uptime,
            "decisions_per_second": self.stats["decisions"] / max(1, uptime),
            "current_state": self.current_state.value,
            "config": {
                "attack_aggression": self.config.attack_aggression,
                "defense_preference": self.config.defense_preference,
                "movement_style": self.config.movement_style,
            },
        }

    def set_aggression(self, level: float):
        self.config.attack_aggression = max(0, min(1, level))
        logger.info(f"Aggression set to {level:.2f}")

    def set_movement_style(self, style: str):
        if style in ["kiting", "aggressive", "defensive"]:
            self.config.movement_style = style
            logger.info(f"Movement style set to {style}")

    def enable(self):
        self.is_enabled = True
        logger.info("AI enabled")

    def disable(self):
        self.is_enabled = False
        logger.info("AI disabled")

    def reset(self):
        self.current_state = CombatState.IDLE
        self.current_target = None
        self.path_planner.clear_dynamic_obstacles()
        logger.info("Orchestrator reset")
