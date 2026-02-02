"""
SocketBridge AI 主控器 (增强版)

整合所有 Phase 1-4 模块，提供完整的 AI 控制框架。

功能：
- 集成数据处理、威胁分析、策略选择、控制计算
- 支持多种配置选项
- 提供性能统计和调试信息

根据 reference.md 完整架构设计。
"""

import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

from models import (
    Vector2D,
    GameStateData,
    ControlOutput,
    PlayerData,
    EnemyData,
)

logger = logging.getLogger("EnhancedOrchestrator")


class MovementStyle(Enum):
    """移动风格"""

    KITING = "kiting"  # 放风筝
    AGGRESSIVE = "aggressive"  # 激进
    DEFENSIVE = "defensive"  # 防御
    BALANCED = "balanced"  # 平衡
    RANDOM = "random"  # 随机


@dataclass
class AIConfig:
    """AI 配置"""

    # 决策间隔
    decision_interval: float = 0.05  # 50ms

    # 威胁阈值
    immediate_threat_threshold: float = 0.5

    # 战斗距离
    combat_engage_distance: float = 200.0
    retreat_health_threshold: float = 0.3

    # 行为参数
    attack_aggression: float = 0.7
    defense_preference: float = 0.5
    movement_style: str = "kiting"

    # 模块开关
    enable_pathfinding: bool = True
    enable_threat_analysis: bool = True
    enable_behavior_tree: bool = True
    enable_advanced_control: bool = True
    enable_adaptive_behavior: bool = True


class EnhancedCombatOrchestrator:
    """增强版战斗协调器

    整合所有 AI 模块，提供统一的控制接口。
    """

    def __init__(self, config: AIConfig = None):
        self.config = config or AIConfig()

        # 模块初始化
        self._init_modules()

        # 状态追踪
        self.enabled = True
        self.last_decision_time = 0
        self.decision_count = 0

        # 性能统计
        self.performance_stats = {
            "total_decisions": 0,
            "avg_decision_time_ms": 0,
            "threat_assessments": 0,
            "strategy_changes": 0,
        }

        # 调试信息
        self.debug_info = {}

    def _init_modules(self):
        """初始化所有模块"""
        # Phase 1: 基础模块
        from data_processor import DataProcessor

        self.data_processor = DataProcessor()

        # Phase 2: 分析模块
        from threat_analysis import ThreatAnalyzer

        self.threat_analyzer = ThreatAnalyzer()

        # Phase 3: 决策模块
        from state_machine import HierarchicalStateMachine, StateMachineConfig

        state_config = StateMachineConfig()
        self.state_machine = HierarchicalStateMachine(state_config)

        from strategy_system import StrategyManager

        self.strategy_manager = StrategyManager()

        from behavior_tree import create_combat_behavior_tree

        self.behavior_tree = create_combat_behavior_tree()

        # Phase 4: 控制模块
        from basic_controllers import BasicControllerManager, ControlConfig

        ctrl_config = ControlConfig()
        self.basic_controller = BasicControllerManager(ctrl_config)

        from advanced_control import AdvancedMovementController, PIDConfig

        pos_pid = PIDConfig(kp=0.8, ki=0.05, kd=0.3)
        vel_pid = PIDConfig(kp=0.5, ki=0.02, kd=0.2)
        self.advanced_controller = AdvancedMovementController(pos_pid, vel_pid)

        from smart_aiming import SmartAimingSystem

        self.aiming_system = SmartAimingSystem()

        from adaptive_system import AdaptiveParameterSystem, AdaptiveConfig

        adapt_config = AdaptiveConfig()
        self.adaptive_system = AdaptiveParameterSystem(adapt_config)

    def initialize(self):
        """初始化 AI 系统"""
        logger.info("Initializing Enhanced Combat Orchestrator...")

        # 应用配置到各模块
        self.basic_controller.set_aggression(self.config.attack_aggression)

        from basic_controllers import MovementStyle

        try:
            style = MovementStyle(self.config.movement_style)
            self.basic_controller.set_movement_style(style)
        except ValueError:
            self.basic_controller.set_movement_style(MovementStyle.KITING)

        logger.info("Orchestrator initialized successfully")

    def update(self, raw_message: Dict[str, Any]) -> ControlOutput:
        """更新 AI 控制

        Args:
            raw_message: 原始游戏消息

        Returns:
            控制输出
        """
        if not self.enabled:
            return ControlOutput()

        start_time = time.time()

        # 1. 处理游戏数据
        game_state = self.data_processor.process_message(raw_message)

        # 2. 威胁分析
        threat_assessment = self.threat_analyzer.analyze(game_state)

        # 3. 构建策略上下文
        context = self.strategy_manager.build_context(
            game_state, threat_assessment.overall_threat_level.value / 3
        )

        # 4. 策略选择
        strategy, evaluation = self.strategy_manager.select_best(context)

        # 5. 更新状态机
        states = self.state_machine.update(
            threat_level=threat_assessment.overall_threat_level.value / 3,
            player_health=context.player_health,
            enemy_count=context.enemy_count,
            has_projectiles=context.has_active_projectiles,
            can_heal=context.can_heal,
        )

        # 6. 自适应调整
        adaptive_params = self.adaptive_system.update(game_state)

        # 7. 获取目标敌人
        player = game_state.get_primary_player()
        target_enemy = None
        if player:
            target_enemy = game_state.get_nearest_enemy(player.position)

        # 8. 执行行为树
        bt_context = self._build_behavior_context(
            game_state, threat_assessment, context
        )
        self.behavior_tree.context = bt_context
        bt_result = self.behavior_tree.update()

        # 9. 计算控制输出
        control = self.basic_controller.compute_control(
            game_state=game_state,
            target_enemy=target_enemy,
            evade_threats=threat_assessment.immediate_threats,
        )

        # 10. 高级控制（如果启用）
        if self.config.enable_advanced_control and player:
            control.move_x, control.move_y = self.advanced_controller.update(
                current_pos=player.position,
                current_vel=player.velocity,
            )

        # 11. 智能瞄准（如果启用）
        if self.config.enable_threat_analysis and target_enemy:
            aim_result = self.aiming_system.aim(
                shooter_pos=player.position,
                target=target_enemy,
            )
            if aim_result.confidence > 0.5:
                control.shoot_x, control.shoot_y = self._vector_to_direction(
                    aim_result.direction
                )
                control.shoot = True

        # 更新统计
        decision_time = (time.time() - start_time) * 1000
        self.performance_stats["total_decisions"] += 1
        self.performance_stats["avg_decision_time_ms"] = (
            self.performance_stats["avg_decision_time_ms"] * 0.9 + decision_time * 0.1
        )
        self.performance_stats["threat_assessments"] += 1

        # 保存调试信息
        self.debug_info = {
            "strategy": strategy.value,
            "threat_level": threat_assessment.overall_threat_level.name,
            "battle_state": states.get("battle", "N/A"),
            "movement_state": states.get("movement", "N/A"),
            "decision_time_ms": decision_time,
        }

        return control

    def _build_behavior_context(
        self,
        game_state: GameStateData,
        threat_assessment,
        strategy_context,
    ):
        """构建行为树上下文"""
        from behavior_tree import NodeContext

        player = game_state.get_primary_player()

        context = NodeContext()
        context.game_state = game_state

        if player:
            context.player_health = player.health / max(player.max_health, 1)
            context.player_position = player.position.to_tuple()

        context.enemies = list(game_state.active_enemies)
        context.nearest_enemy = (
            game_state.get_nearest_enemy(player.position) if player else None
        )

        context.threat_level = threat_assessment.overall_threat_level.value / 3
        context.projectiles = list(game_state.enemy_projectiles)

        if game_state.room_info:
            context.room_info = game_state.room_info

        return context

    def _vector_to_direction(self, vec: Vector2D) -> Tuple[int, int]:
        """将向量转换为方向"""
        x = 0
        y = 0
        if vec.x > 0.3:
            x = 1
        elif vec.x < -0.3:
            x = -1
        if vec.y > 0.3:
            y = 1
        elif vec.y < -0.3:
            y = -1
        return (x, y)

    def enable(self):
        """启用 AI"""
        self.enabled = True
        logger.info("Orchestrator enabled")

    def disable(self):
        """禁用 AI"""
        self.enabled = False
        logger.info("Orchestrator disabled")

    def reset(self):
        """重置 AI 状态"""
        self.data_processor.reset()
        self.basic_controller.reset()
        self.advanced_controller.reset()
        self.strategy_manager.reset()
        self.adaptive_system.reset()
        self.state_machine.reset()
        self.aiming_system.reset_stats()

    def set_aggression(self, level: float):
        """设置攻击性"""
        self.config.attack_aggression = max(0, min(1, level))
        self.basic_controller.set_aggression(level)

    def set_movement_style(self, style: str):
        """设置移动风格"""
        self.config.movement_style = style
        try:
            from basic_controllers import MovementStyle

            self.basic_controller.set_movement_style(MovementStyle(style))
        except ValueError:
            pass

    def on_player_damage(self, damage: int, hp_after: int):
        """玩家受伤回调"""
        self.adaptive_system.metrics.damage_taken += damage

    def on_enemy_killed(self, enemy: EnemyData):
        """敌人死亡回调"""
        self.adaptive_system.metrics.enemies_killed += 1
        self.aiming_system.record_hit(True)

    def on_room_entered(self, room_info):
        """进入房间回调"""
        self.adaptive_system.metrics.rooms_cleared += 1

    def on_room_cleared(self):
        """房间清理完成回调"""
        self.adaptive_system.metrics.rooms_cleared += 1

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        return {
            **self.performance_stats,
            "adaptive_scenario": self.adaptive_system.current_scenario.value,
            "current_strategy": self.strategy_manager.current_strategy.value,
        }


class SimpleAI:
    """简单 AI 包装器

    提供简化的 AI 接口，适合快速上手使用。
    """

    def __init__(self, use_enhanced: bool = True):
        self.use_enhanced = use_enhanced

        if use_enhanced:
            self.orchestrator = EnhancedCombatOrchestrator()
            self.orchestrator.initialize()
        else:
            from orchestrator import CombatOrchestrator

            self.orchestrator = CombatOrchestrator()

        # 连接到 isaac_bridge
        self.bridge = None
        self.data_accessor = None

    def connect(self, host: str = "127.0.0.1", port: int = 9527):
        """连接到游戏"""
        from isaac_bridge import IsaacBridge, GameDataAccessor

        self.bridge = IsaacBridge(host=host, port=port)
        self.data_accessor = GameDataAccessor(self.bridge)

        @self.bridge.on("connected")
        def on_connected(info):
            print(f"AI connected to {info['address']}")

        @self.bridge.on("disconnected")
        def on_disconnected():
            print("AI disconnected")

        self.bridge.start()

    def update(
        self, game_data: Dict[str, Any]
    ) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """更新 AI 控制

        Returns:
            (move, shoot) 元组
        """
        control = self.orchestrator.update(game_data)
        return control.to_input()

    def run(self):
        """运行 AI 主循环"""
        if not self.bridge:
            raise ValueError("Not connected. Call connect() first.")

        @self.bridge.on("data")
        def on_data(data):
            move, shoot = self.update(data)
            if any(move) or any(shoot):
                self.bridge.send_input(move=move, shoot=shoot)

        print("AI running... Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(0.016)  # ~60 FPS
        except KeyboardInterrupt:
            print("\nStopping AI...")
            self.stop()

    def stop(self):
        """停止 AI"""
        if self.bridge:
            self.bridge.stop()
        if self.orchestrator:
            self.orchestrator.disable()


def create_orchestrator(config: AIConfig = None) -> EnhancedCombatOrchestrator:
    """创建增强版协调器"""
    return EnhancedCombatOrchestrator(config)


def create_simple_ai(use_enhanced: bool = True) -> SimpleAI:
    """创建简单 AI 实例"""
    return SimpleAI(use_enhanced)
