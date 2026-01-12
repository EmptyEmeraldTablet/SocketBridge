"""
AI 战斗控制系统 - 主控模块

整合所有子模块，实现完整的AI战斗决策流程：
1. 感知模块 → 数据解析和环境建模
2. 分析模块 → 威胁评估和局势分析
3. 决策模块 → 行动意图生成
4. 规划模块 → 详细执行计划
5. 控制模块 → 游戏输入指令

根据 reference.md 中的系统架构设计，集成了：
- Phase 1: 基础控制 (basic_controllers)
- Phase 2: 威胁分析 (threat_analysis), 路径规划 (pathfinding)
- Phase 3: 状态机 (state_machine), 策略系统 (strategy_system), 行为树 (behavior_tree)
- Phase 4: 高级控制 (advanced_control), 智能瞄准 (smart_aiming), 自适应系统 (adaptive_system)
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
    """战斗状态（保留兼容）"""

    IDLE = "idle"
    EXPLORING = "exploring"
    COMBAT = "combat"
    EVASION = "evasion"
    RETREATING = "retreating"
    HEALING = "healing"


@dataclass
class AIConfig:
    """AI配置"""

    # 决策频率
    decision_interval: float = 0.05  # 50ms = 20Hz

    # 威胁阈值
    immediate_threat_threshold: float = 0.5
    combat_engage_distance: float = 300.0
    retreat_health_threshold: float = 0.3

    # 行为参数
    attack_aggression: float = 0.7  # 攻击倾向 0-1
    defense_preference: float = 0.5  # 防御倾向 0-1
    movement_style: str = "kiting"  # "kiting", "aggressive", "defensive"

    # 启用/禁用模块
    enable_pathfinding: bool = True
    enable_threat_analysis: bool = True
    enable_adaptive_behavior: bool = False


class CombatOrchestrator:
    """战斗系统主控器

    整合所有模块，实现完整的AI战斗控制流程。
    """

    def __init__(self, config: AIConfig = None):
        self.config = config or AIConfig()

        # 子系统
        self.data_processor = DataProcessor()
        self.environment = EnvironmentModel()
        self.controllers = BasicControllerManager()
        self.path_planner = DynamicPathPlanner()
        self.path_executor = PathExecutor(self.path_planner)
        self.threat_analyzer = ThreatAnalyzer()

        # 状态
        self.current_state = CombatState.IDLE
        self.last_decision_time = 0.0
        self.current_target: Optional[EnemyData] = None
        self.is_enabled = True

        # 统计
        self.stats = {
            "decisions": 0,
            "threat_assessments": 0,
            "paths_planned": 0,
            "damage_taken": 0,
            "enemies_killed": 0,
            "start_time": None,
        }

    def initialize(self):
        """初始化"""
        self.stats["start_time"] = time.time()
        logger.info("Combat Orchestrator initialized")

    def update(self, raw_message: Dict[str, Any]) -> ControlOutput:
        """
        主更新循环

        Args:
            raw_message: 来自游戏的原始消息

        Returns:
            控制输出
        """
        if not self.is_enabled:
            return ControlOutput()

        # 1. 解析数据
        game_state = self.data_processor.process_message(raw_message)

        # 2. 更新环境模型
        player = game_state.get_primary_player()
        if not player:
            return ControlOutput()

        self.environment.update_room(
            game_state.room_layout,
            game_state.room_info,
            game_state.enemies,
            game_state.enemy_projectiles,
        )

        # 3. 威胁分析
        threat_assessment = None
        if self.config.enable_threat_analysis:
            threat_assessment = self.threat_analyzer.analyze(
                player.position,
                game_state.enemies,
                game_state.enemy_projectiles,
                current_frame=game_state.frame,
            )

        # 4. 决策
        decision = self._make_decision(game_state, threat_assessment)

        # 5. 执行控制
        control = self._execute_decision(game_state, decision, threat_assessment)

        # 更新统计
        self.stats["decisions"] += 1
        if threat_assessment:
            self.stats["threat_assessments"] += 1

        return control

    def _make_decision(
        self, game_state: GameStateData, threat_assessment: ThreatAssessment
    ) -> Dict[str, Any]:
        """
        做出决策

        Returns:
            决策结果
        """
        player = game_state.get_primary_player()

        # 更新状态
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

        # 根据状态做出具体决策
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

        # 保存当前状态
        self.current_state = new_state

        return decision

    def _update_combat_state(
        self, game_state: GameStateData, threat_assessment: ThreatAssessment
    ) -> CombatState:
        """更新战斗状态"""
        player = game_state.get_primary_player()

        # 检查是否需要躲避
        if threat_assessment:
            if threat_assessment.overall_threat_level in [
                ThreatLevel.CRITICAL,
                ThreatLevel.HIGH,
            ]:
                if len(threat_assessment.immediate_threats) >= 2:
                    return CombatState.EVASION

        # 检查是否需要撤退
        if player.health_percentage < self.config.retreat_health_threshold:
            if game_state.get_active_enemies():
                return CombatState.RETREATING

        # 检查是否需要治疗
        if player.health_percentage < 0.5 and self._has_healing_items(player):
            return CombatState.HEALING

        # 战斗状态
        if game_state.is_combat_active():
            return CombatState.COMBAT

        # 探索状态
        if game_state.enemy_count == 0 and not game_state.is_combat_active():
            return CombatState.EXPLORING

        return CombatState.IDLE

    def _select_target(self, game_state: GameStateData) -> Optional[EnemyData]:
        """选择攻击目标"""
        player = game_state.get_primary_player()

        # 获取活跃敌人
        enemies = game_state.get_active_enemies()
        if not enemies:
            return None

        # 选择策略
        if self.config.attack_aggression > 0.7:
            # 高侵略性：选择最近的敌人
            return game_state.get_nearest_enemy(player.position)

        elif self.config.attack_aggression > 0.4:
            # 中等：选择低血量敌人
            wounded = [e for e in enemies if e.hp < e.max_hp * 0.5]
            if wounded:
                return min(wounded, key=lambda e: e.hp)
            return game_state.get_nearest_enemy(player.position)

        else:
            # 保守：选择最弱的敌人
            return min(enemies, key=lambda e: e.hp)

    def _execute_decision(
        self,
        game_state: GameStateData,
        decision: Dict[str, Any],
        threat_assessment: ThreatAssessment,
    ) -> ControlOutput:
        """执行决策"""
        player = game_state.get_primary_player()

        # 处理躲避
        if decision["should_dodge"] and threat_assessment:
            evade_threats = [
                t
                for t in threat_assessment.immediate_threats
                if t.source_type == "projectile"
            ]
            return self.controllers.compute_control(
                game_state,
                target_enemy=decision["target"],
                evade_threats=[
                    game_state.enemy_projectiles.get(t.source_id)
                    for t in threat_assessment.immediate_threats
                    if t.source_id in game_state.enemy_projectiles
                ],
            )

        # 处理战斗
        if decision["should_attack"]:
            return self.controllers.compute_control(
                game_state, target_enemy=decision["target"]
            )

        # 处理撤退
        if decision["retreat"]:
            return self._handle_retreat(game_state)

        # 处理治疗
        if decision["heal"]:
            return self._handle_healing(game_state)

        # 探索模式
        if decision["movement_type"] == "explore":
            return self._handle_explore(game_state)

        return ControlOutput()

    def _handle_retreat(self, game_state: GameStateData) -> ControlOutput:
        """处理撤退"""
        player = game_state.get_primary_player()

        # 寻找安全位置
        safe_pos = self.environment.get_safe_spot(
            player.position, min_distance=100, max_distance=300
        )

        if safe_pos:
            move = self.path_executor.execute_to(player.position, safe_pos)
            return ControlOutput(
                move_x=move[0], move_y=move[1], confidence=0.9, reasoning="retreat"
            )

        # 无法找到安全位置，向门口移动
        return ControlOutput(
            move_x=-1 if player.position.x > 400 else 1,
            move_y=0,
            confidence=0.7,
            reasoning="retreat_emergency",
        )

    def _handle_healing(self, game_state: GameStateData) -> ControlOutput:
        """处理治疗"""
        # 简化：停止移动
        return ControlOutput(
            move_x=0, move_y=0, use_item=True, confidence=0.9, reasoning="healing"
        )

    def _handle_explore(self, game_state: GameStateData) -> ControlOutput:
        """处理探索"""
        player = game_state.get_primary_player()

        if game_state.room_info:
            center = game_state.room_info.center

            # 向中心移动
            direction = center - player.position
            move_x = 1 if direction.x > 0 else -1 if direction.x < 0 else 0
            move_y = 1 if direction.y > 0 else -1 if direction.y < 0 else 0

            return ControlOutput(
                move_x=move_x, move_y=move_y, confidence=0.6, reasoning="exploring"
            )

        return ControlOutput()

    def _has_healing_items(self, player: PlayerData) -> bool:
        """检查是否有治疗物品"""
        # 检查主动道具（如果有治疗道具）
        for slot, item in player.active_items.items():
            item_id = item.get("item", 0)
            # 简化检查
            if item_id in [2, 3]:  # D4, D5 等
                return True

        return player.red_hearts < player.max_hearts / 2

    def on_player_damage(self, damage: int, hp_after: int):
        """玩家受伤回调"""
        self.stats["damage_taken"] += damage

        # 低血量时增加防御倾向
        if hp_after <= 2:
            self.config.defense_preference = min(
                1.0, self.config.defense_preference + 0.2
            )

    def on_enemy_killed(self, enemy: EnemyData):
        """敌人死亡回调"""
        self.stats["enemies_killed"] += 1

        # 更新目标
        if self.current_target and self.current_target.id == enemy.id:
            self.current_target = None

    def on_room_entered(self, room_info: RoomInfo):
        """进入房间回调"""
        logger.info(f"Entered room {room_info.room_index}")

        # 重置部分状态
        self.current_target = None
        self.path_planner.clear_dynamic_obstacles()

    def on_room_cleared(self):
        """房间清除回调"""
        logger.info("Room cleared!")

        # 切换到探索状态
        self.current_state = CombatState.EXPLORING

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
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
        """
        设置攻击倾向

        Args:
            level: 0-1，0为保守，1为激进
        """
        self.config.attack_aggression = max(0, min(1, level))
        logger.info(f"Aggression set to {level:.2f}")

    def set_movement_style(self, style: str):
        """
        设置移动风格

        Args:
            style: "kiting", "aggressive", "defensive"
        """
        if style in ["kiting", "aggressive", "defensive"]:
            self.config.movement_style = style
            logger.info(f"Movement style set to {style}")

    def enable(self):
        """启用AI"""
        self.is_enabled = True
        logger.info("AI enabled")

    def disable(self):
        """禁用AI"""
        self.is_enabled = False
        logger.info("AI disabled")

    def reset(self):
        """重置状态"""
        self.current_state = CombatState.IDLE
        self.current_target = None
        self.path_planner.clear_dynamic_obstacles()
        logger.info("Orchestrator reset")


class SimpleAI:
    """简单AI包装器

    用于快速集成的简化接口。
    """

    def __init__(self):
        self.orchestrator = CombatOrchestrator()
        self.orchestrator.initialize()
        self._connected = False

    def connect(self):
        """连接（启动AI）"""
        self.orchestrator.enable()
        self._connected = True
        logger.info("AI connected")

    def disconnect(self):
        """断开连接"""
        self.orchestrator.disable()
        self._connected = False
        logger.info("AI disconnected")

    def update(
        self, game_data: Dict[str, Any]
    ) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        更新AI

        Args:
            game_data: 游戏数据

        Returns:
            (移动方向, 射击方向)
        """
        if not self._connected:
            return (0, 0), (0, 0)

        control = self.orchestrator.update(game_data)

        move = (control.move_x, control.move_y)
        shoot = (control.shoot_x, control.shoot_y) if control.shoot else (0, 0)

        return move, shoot

    def on_damage(self, damage: int, hp_after: int):
        """玩家受伤"""
        self.orchestrator.on_player_damage(damage, hp_after)

    def on_room_enter(self, room_data: Dict[str, Any]):
        """进入房间"""
        self.orchestrator.on_room_entered(
            RoomInfo(
                room_index=room_data.get("room_idx", 0),
                enemy_count=room_data.get("enemy_count", 0),
            )
        )

    def on_room_clear(self):
        """房间清除"""
        self.orchestrator.on_room_cleared()

    def set_aggression(self, level: float):
        """设置攻击性"""
        self.orchestrator.set_aggression(level)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return self.orchestrator.get_performance_stats()
