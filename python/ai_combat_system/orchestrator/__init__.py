"""
主控模块 (Orchestrator Module)

协调各模块，管理状态。

核心组件:
- 状态机管理器 (State Machine): 战斗状态、移动状态、特殊状态
- 优先级管理器 (Priority Manager): 行动优先级、中断处理、资源分配
- 配置管理器 (Configuration Manager): 难度参数、AI风格、模块开关
- 日志记录器 (Logger): 决策过程、异常事件、性能数据
"""

import math
import time
import logging
import threading
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from dataclasses import dataclass
from enum import Enum
from collections import deque

from ..perception import PerceptionModule, GameState
from ..analysis import AnalysisModule, SituationAssessment
from ..decision import DecisionModule, ActionIntent, StrategyProfile
from ..planning import PlanningModule, ExecutionPlan
from ..control import ControlModule, InputCommand
from ..evaluation import EvaluationModule

logger = logging.getLogger("OrchestratorModule")


class CombatState(Enum):
    """战斗状态"""

    IDLE = "idle"  # 空闲
    COMBAT = "combat"  # 普通战斗
    BOSS = "boss"  # Boss战
    EMERGENCY = "emergency"  # 紧急躲避
    RETREATING = "retreating"  # 撤退中


class MovementState(Enum):
    """移动状态"""

    IDLE = "idle"  # 静止
    EXPLORING = "exploring"  # 探索
    ENGAGING = "engaging"  # 追击
    RETREATING = "retreating"  # 撤退
    KITING = "kiting"  # 走位


class SpecialState(Enum):
    """特殊状态"""

    NONE = "none"  # 无
    USING_ITEM = "using_item"  # 使用道具
    INTERACTING = "interacting"  # 互动中
    DAMAGE_RESPONSE = "damage_response"  # 受伤响应


@dataclass
class SystemConfig:
    """系统配置"""

    # AI设置
    ai_enabled: bool = True
    difficulty: str = "normal"  # "easy", "normal", "hard"
    ai_style: str = "balanced"  # "aggressive", "defensive", "balanced"

    # 模块开关
    perception_enabled: bool = True
    analysis_enabled: bool = True
    decision_enabled: bool = True
    planning_enabled: bool = True
    control_enabled: bool = True
    evaluation_enabled: bool = True

    # 性能设置
    decision_frequency: int = 3  # 每N帧决策一次
    max_planning_time_ms: float = 5.0
    async_evaluation: bool = False

    # 行为参数
    emergency_threshold: float = 0.7  # 紧急状态阈值
    retreat_threshold: float = 0.4  # 撤退阈值
    healing_threshold: float = 0.3  # 治疗阈值

    @classmethod
    def aggressive(cls) -> "SystemConfig":
        return cls(
            difficulty="hard",
            ai_style="aggressive",
            emergency_threshold=0.5,
            retreat_threshold=0.2,
            healing_threshold=0.15,
        )

    @classmethod
    def defensive(cls) -> "SystemConfig":
        return cls(
            difficulty="easy",
            ai_style="defensive",
            emergency_threshold=0.8,
            retreat_threshold=0.6,
            healing_threshold=0.5,
        )


@dataclass
class SystemStatus:
    """系统状态"""

    is_running: bool = False
    is_paused: bool = False

    # 状态机
    combat_state: CombatState = CombatState.IDLE
    movement_state: MovementState = MovementState.IDLE
    special_state: SpecialState = SpecialState.NONE

    # 统计数据
    total_frames: int = 0
    current_frame: int = 0
    last_decision_frame: int = 0

    # 模块状态
    perception_ok: bool = False
    analysis_ok: bool = False
    decision_ok: bool = False
    planning_ok: bool = False
    control_ok: bool = False
    evaluation_ok: bool = False

    # 性能指标
    avg_fps: float = 0.0
    avg_decision_time_ms: float = 0.0
    last_latency_ms: float = 0.0


class StateMachine:
    """
    状态机管理器

    功能：
    - 战斗状态管理（普通战斗、Boss战、紧急躲避）
    - 移动状态管理（探索、追击、撤退）
    - 特殊状态管理（使用道具、互动）
    - 状态转换条件
    """

    def __init__(self):
        self.combat_state = CombatState.IDLE
        self.movement_state = MovementState.IDLE
        self.special_state = SpecialState.NONE

        # 状态历史
        self.state_history: deque = deque(maxlen=50)

        # 转换回调
        self.on_state_change: Optional[Callable] = None

    def update(
        self, situation: SituationAssessment
    ) -> Tuple[CombatState, MovementState, SpecialState]:
        """更新状态"""
        # 检测战斗状态
        self._update_combat_state(situation)

        # 检测移动状态
        self._update_movement_state(situation)

        # 检测特殊状态
        self._update_special_state(situation)

        # 记录状态历史
        self.state_history.append(
            {
                "combat": self.combat_state,
                "movement": self.movement_state,
                "special": self.special_state,
                "timestamp": time.time(),
            }
        )

        return self.combat_state, self.movement_state, self.special_state

    def _update_combat_state(self, situation: SituationAssessment):
        """更新战斗状态"""
        # 紧急状态
        if situation.overall_threat_level.value >= 3:  # CRITICAL
            if self.combat_state != CombatState.EMERGENCY:
                self.combat_state = CombatState.EMERGENCY
        # Boss战
        elif situation.is_boss_fight:
            if self.combat_state != CombatState.BOSS:
                self.combat_state = CombatState.BOSS
        # 普通战斗
        elif situation.is_combat:
            if self.combat_state != CombatState.COMBAT:
                self.combat_state = CombatState.COMBAT
        # 空闲
        else:
            if self.combat_state != CombatState.IDLE:
                self.combat_state = CombatState.IDLE

    def _update_movement_state(self, situation: SituationAssessment):
        """更新移动状态"""
        action = situation.suggested_action

        if action.value in ["retreat", "strategic_retreat"]:
            self.movement_state = MovementState.RETREATING
        elif action.value in ["kiting", "emergency_dodge"]:
            self.movement_state = MovementState.KITING
        elif action.value in ["attack", "focus_fire", "eliminate_threat"]:
            self.movement_state = MovementState.ENGAGING
        elif action.value == "explore":
            self.movement_state = MovementState.EXPLORING
        else:
            self.movement_state = MovementState.IDLE

    def _update_special_state(self, situation: SituationAssessment):
        """更新特殊状态"""
        # 暂时不实现特殊状态检测
        self.special_state = SpecialState.NONE

    def get_state_vector(self) -> List[float]:
        """获取状态向量（用于机器学习）"""
        return [
            self.combat_state.value,
            self.movement_state.value,
            self.special_state.value,
        ]

    def force_state(
        self,
        combat: CombatState = None,
        movement: MovementState = None,
        special: SpecialState = None,
    ):
        """强制设置状态"""
        if combat:
            self.combat_state = combat
        if movement:
            self.movement_state = movement
        if special:
            self.special_state = special


class PriorityManager:
    """
    优先级管理器

    功能：
    - 行动优先级规则
    - 中断处理机制
    - 资源分配决策
    """

    def __init__(self):
        # 优先级表
        self.priority_rules = {
            "emergency_dodge": 100,
            "heal": 90,
            "strategic_retreat": 80,
            "find_cover": 70,
            "eliminate_threat": 60,
            "focus_fire": 50,
            "kiting": 40,
            "position_suppression": 30,
            "position_adjust": 20,
            "flank": 15,
            "use_item": 10,
            "explore": 5,
            "idle": 1,
        }

        # 中断条件
        self.interrupt_conditions = []

        # 资源分配
        self.resource_pool = {
            "cpu_time": 1.0,  # 总CPU时间比例
            "memory": 100,  # 内存配额
            "bandwidth": 100,  # 带宽配额
        }

        self.allocation = {
            "perception": 0.15,
            "analysis": 0.20,
            "decision": 0.10,
            "planning": 0.30,
            "control": 0.15,
            "evaluation": 0.10,
        }

    def calculate_priority(self, action: ActionIntent) -> int:
        """计算行动优先级"""
        base_priority = self.priority_rules.get(action.action_type.value, 50)

        # 根据行动类型调整
        if action.priority > 0:
            base_priority += action.priority

        # 根据持续时间调整
        if action.max_duration_frames > 30:
            base_priority -= 5  # 长时间行动优先级降低

        return max(1, min(100, base_priority))

    def should_interrupt(
        self, current_action: ActionIntent, new_situation: SituationAssessment
    ) -> Tuple[bool, str]:
        """
        判断是否应该中断当前行动

        Returns:
            (是否中断, 原因)
        """
        # 紧急威胁
        if new_situation.immediate_threats:
            return True, "immediate_threat"

        # 血量危急
        if new_situation.resources.critical_hp_warning:
            return True, "critical_hp"

        # 更好的机会
        if new_situation.opportunities:
            top_opp = new_situation.opportunities[0]
            if top_opp.value > 0.8:
                return True, "high_value_opportunity"

        return False, ""

    def get_resource_allocation(self, module: str) -> Dict:
        """获取资源分配"""
        if module not in self.allocation:
            return {"cpu": 0, "memory": 0, "bandwidth": 0}

        cpu = self.resource_pool["cpu_time"] * self.allocation[module]
        memory = self.resource_pool["memory"] * self.allocation[module]
        bandwidth = self.resource_pool["bandwidth"] * self.allocation[module]

        return {"cpu": cpu, "memory": memory, "bandwidth": bandwidth}


class Logger:
    """
    日志记录器

    功能：
    - 决策过程记录
    - 异常事件追踪
    - 性能数据保存
    """

    def __init__(self, log_dir: str = "./logs"):
        self.log_dir = log_dir

        # 日志配置
        self.decision_log: deque = deque(maxlen=1000)
        self.event_log: deque = deque(maxlen=500)
        self.performance_log: deque = deque(maxlen=100)

        # 详细程度
        self.log_level = logging.INFO
        self.log_decisions = True
        self.performance_logging_enabled = True

    def log_decision(
        self, frame: int, situation: Dict, action: ActionIntent, result: str = ""
    ):
        """记录决策"""
        if not self.log_decisions:
            return

        entry = {
            "frame": frame,
            "timestamp": time.time(),
            "situation": situation,
            "action": action.to_dict() if action else None,
            "result": result,
        }

        self.decision_log.append(entry)

        # 记录到系统日志
        logger.debug(
            f"Frame {frame}: Action={action.action_type.value if action else 'None'}"
        )

    def log_event(self, event_type: str, data: Dict):
        """记录事件"""
        entry = {"type": event_type, "timestamp": time.time(), "data": data}

        self.event_log.append(entry)

        # 警告级别的事件记录到系统日志
        if event_type in ["error", "warning", "critical"]:
            logger.warning(f"Event: {event_type}, Data: {data}")

    def log_performance(self, frame: int, metrics: Dict):
        """记录性能"""
        if not self.performance_logging_enabled:
            return

        entry = {"frame": frame, "timestamp": time.time(), "metrics": metrics}

        self.performance_log.append(entry)

    def get_decision_history(self, limit: int = 100) -> List[Dict]:
        """获取决策历史"""
        return list(self.decision_log)[-limit:]

    def get_event_history(self, event_type: str = None) -> List[Dict]:
        """获取事件历史"""
        if event_type:
            return [e for e in self.event_log if e["type"] == event_type]
        return list(self.event_log)


class Orchestrator:
    """
    主控模块主类

    整合所有子模块，协调AI系统的整体运行。

    核心流程:
    1. 感知 -> 分析 -> 决策 -> 规划 -> 控制 -> 评估
    2. 反馈优化 -> 状态更新 -> 循环
    """

    def __init__(self, config: SystemConfig = None):
        # 配置
        self.config = config or SystemConfig()

        # 状态
        self.status = SystemStatus()

        # 子模块
        self.perception = PerceptionModule() if self.config.perception_enabled else None
        self.analysis = AnalysisModule() if self.config.analysis_enabled else None
        self.decision = DecisionModule() if self.config.decision_enabled else None
        self.planning = PlanningModule() if self.config.planning_enabled else None
        self.control = ControlModule() if self.config.control_enabled else None
        self.evaluation = EvaluationModule() if self.config.evaluation_enabled else None

        # 状态机
        self.state_machine = StateMachine()

        # 优先级管理
        self.priority_manager = PriorityManager()

        # 日志
        self.logger = Logger()

        # 状态管理
        self.current_state: Optional[GameState] = None
        self.current_situation: Optional[SituationAssessment] = None
        self.current_action: Optional[ActionIntent] = None
        self.current_plan: Optional[ExecutionPlan] = None

        # 性能监控
        self.frame_times: deque = deque(maxlen=60)
        self.decision_times: deque = deque(maxlen=100)

    def initialize(self):
        """初始化系统"""
        self.status.is_running = True

        # 设置策略
        if self.decision:
            if self.config.ai_style == "aggressive":
                self.decision.set_strategy(StrategyProfile.aggressive())
            elif self.config.ai_style == "defensive":
                self.decision.set_strategy(StrategyProfile.defensive())

        logger.info("Orchestrator initialized")

    def shutdown(self):
        """关闭系统"""
        self.status.is_running = False
        logger.info("Orchestrator shutdown")

    def process_frame(self, raw_data: Dict, frame: int) -> InputCommand:
        """
        处理一帧数据

        Args:
            raw_data: 原始数据
            frame: 当前帧

        Returns:
            输入指令
        """
        start_time = time.time()

        # 1. 感知
        if self.perception and self.config.perception_enabled:
            game_state = self.perception.process_raw_data(raw_data, frame)
            self.current_state = game_state
            self.status.perception_ok = True
        else:
            game_state = self.current_state

        # 2. 分析
        if self.analysis and self.config.analysis_enabled and game_state:
            situation = self.analysis.analyze(game_state)
            self.current_situation = situation
            self.status.analysis_ok = True
        else:
            situation = self.current_situation

        # 更新状态机
        if situation:
            combat, movement, special = self.state_machine.update(situation)
            self.status.combat_state = combat
            self.status.movement_state = movement
            self.status.special_state = special

        # 3. 决策
        decision_time = 0
        if self.decision and self.config.decision_enabled and situation and game_state:
            decision_start = time.time()

            # 检查是否应该决策
            should_decide = (
                frame - self.status.last_decision_frame
                >= self.config.decision_frequency
                or self.current_action is None
            )

            if should_decide:
                # 检查是否应该中断
                should_interrupt, reason = (
                    self.priority_manager.should_interrupt(
                        self.current_action, situation
                    )
                    if self.current_action
                    else (True, "")
                )

                if should_interrupt or self.current_action is None:
                    self.current_action = self.decision.decide(situation, game_state)
                    self.status.last_decision_frame = frame

                    # 记录决策
                    self.logger.log_decision(
                        frame,
                        situation.to_dict(),
                        self.current_action,
                        reason if should_interrupt else "",
                    )

            decision_time = (time.time() - decision_start) * 1000
            self.decision_times.append(decision_time)
            self.status.decision_ok = True
        else:
            self.current_action = None

        # 4. 规划
        plan_time = 0
        if (
            self.planning
            and self.config.planning_enabled
            and self.current_action
            and game_state
        ):
            plan_start = time.time()

            self.current_plan = self.planning.plan(self.current_action, game_state)

            plan_time = (time.time() - plan_start) * 1000
            self.status.planning_ok = True
        else:
            self.current_plan = None

        # 5. 控制
        control_time = 0
        command = InputCommand()
        if (
            self.control
            and self.config.control_enabled
            and self.current_plan
            and game_state
        ):
            control_start = time.time()

            current_state_dict = {
                "position": game_state.player.position.pos
                if game_state.player and game_state.player.position
                else Vector2D(0, 0),
                "velocity": game_state.player.velocity.vel
                if game_state.player and game_state.player.velocity
                else Vector2D(0, 0),
                "in_hazard": len(
                    [
                        h
                        for h in game_state.hazard_zones
                        if h.contains_point(game_state.player.position.pos)
                    ]
                )
                > 0
                if game_state.player and game_state.player.position
                else False,
            }

            command = self.control.execute(self.current_plan, current_state_dict, frame)

            control_time = (time.time() - control_start) * 1000
            self.status.control_ok = True

        # 6. 评估
        if self.evaluation and self.config.evaluation_enabled:
            self.status.evaluation_ok = True

        # 更新状态
        self.status.total_frames += 1
        self.status.current_frame = frame

        # 性能统计
        frame_time = (time.time() - start_time) * 1000
        self.frame_times.append(frame_time)
        self.status.avg_fps = (
            1000 / (sum(self.frame_times) / len(self.frame_times))
            if self.frame_times
            else 0
        )
        self.status.avg_decision_time_ms = (
            sum(self.decision_times) / len(self.decision_times)
            if self.decision_times
            else 0
        )
        self.status.last_latency_ms = frame_time

        # 性能日志
        self.logger.log_performance(
            frame,
            {
                "frame_time_ms": frame_time,
                "decision_time_ms": decision_time,
                "planning_time_ms": plan_time,
                "fps": self.status.avg_fps,
            },
        )

        return command

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "status": {
                "is_running": self.status.is_running,
                "combat_state": self.status.combat_state.value,
                "movement_state": self.status.movement_state.value,
                "total_frames": self.status.total_frames,
                "fps": self.status.avg_fps,
            },
            "modules": {
                "perception": self.perception.get_stats() if self.perception else None,
                "analysis": self.analysis.get_stats() if self.analysis else None,
                "decision": self.decision.get_stats() if self.decision else None,
                "planning": self.planning.get_stats() if self.planning else None,
                "control": self.control.get_stats() if self.control else None,
                "evaluation": self.evaluation.get_stats() if self.evaluation else None,
            },
            "performance": {
                "avg_frame_time_ms": sum(self.frame_times) / len(self.frame_times)
                if self.frame_times
                else 0,
                "avg_decision_time_ms": self.status.avg_decision_time_ms,
            },
        }

    def update_config(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)

        # 如果AI风格改变，更新策略
        if "ai_style" in kwargs and self.decision:
            if kwargs["ai_style"] == "aggressive":
                self.decision.set_strategy(StrategyProfile.aggressive())
            elif kwargs["ai_style"] == "defensive":
                self.decision.set_strategy(StrategyProfile.defensive())
            else:
                self.decision.set_strategy(StrategyProfile.balanced())


# ==================== 便捷函数 ====================


def create_orchestrator(config: SystemConfig = None) -> Orchestrator:
    """创建主控器实例"""
    return Orchestrator(config)


# 导出主要类
__all__ = [
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
