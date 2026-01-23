"""
SocketBridge 状态机模块

实现分层状态机管理系统：
- 战斗状态机
- 移动状态机
- 特殊状态管理
- 状态转换条件

根据 reference.md 第三阶段设计。
"""

import time
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger("StateMachine")


class BattleState(Enum):
    """战斗状态"""

    IDLE = "idle"
    AGGRESSIVE = "aggressive"
    DEFENSIVE = "defensive"
    DODGE = "dodge"
    RETREAT = "retreat"
    HEAL_PRIORITY = "heal_priority"


class MovementState(Enum):
    """移动状态"""

    EXPLORING = "exploring"  # 探索
    CHASING = "chasing"  # 追击
    FLEEING = "fleeing"  # 撤退
    POSITIONING = "positioning"  # 走位
    STATIONARY = "stationary"  # 静止


class SpecialState(Enum):
    """特殊状态"""

    NONE = "none"
    USING_ITEM = "using_item"
    INTERACTING = "interacting"
    CHARGING = "charging"
    BOMBING = "bombing"


@dataclass
class StateTransition:
    """状态转换规则"""

    from_state: Any
    to_state: Any
    condition: Callable[[], bool]
    priority: int = 0  # 转换优先级
    on_enter: Optional[Callable] = None
    on_exit: Optional[Callable] = None


@dataclass
class StateBehavior:
    """状态行为配置"""

    state: Any
    enter_action: Optional[Callable] = None
    exit_action: Optional[Callable] = None
    update_action: Optional[Callable] = None

    # 行为参数
    move_speed_multiplier: float = 1.0
    attack_rate_multiplier: float = 1.0
    dodge_frequency: float = 0.5
    target_priority: str = "nearest"  # "nearest", "weakest", "strongest"


@dataclass
class StateMachineConfig:
    """状态机配置"""

    # 状态持续时间
    min_state_duration: float = 0.5  # 最小状态持续时间（秒）

    # 转换延迟
    transition_cooldown: float = 0.2  # 转换冷却时间

    # 威胁阈值
    high_threat_threshold: float = 0.7
    low_threat_threshold: float = 0.3

    # 血量阈值
    retreat_health_threshold: float = 0.3
    heal_health_threshold: float = 0.5


class StateMachine:
    """基础状态机

    支持分层状态机和状态转换历史。
    """

    def __init__(self, name: str, config: StateMachineConfig = None):
        self.name = name
        self.config = config or StateMachineConfig()

        # 状态管理
        self.current_state: Any = None
        self.previous_state: Any = None
        self.state_history: List[Any] = []

        # 转换规则
        self.transitions: List[StateTransition] = []
        self.behaviors: Dict[Any, StateBehavior] = {}

        # 时间追踪
        self.state_start_time: float = 0
        self.last_transition_time: float = 0

        # 统计
        self.stats = {
            "total_transitions": 0,
            "transition_counts": {},  # 每个状态的转换次数
            "avg_state_duration": {},  # 每个状态的平均持续时间
        }

    def add_transition(self, transition: StateTransition):
        """添加转换规则"""
        self.transitions.append(transition)
        # 按优先级排序
        self.transitions.sort(key=lambda t: -t.priority)

    def set_behavior(self, behavior: StateBehavior):
        """设置状态行为"""
        self.behaviors[behavior.state] = behavior

    def transition_to(self, new_state: Any, reason: str = ""):
        """执行状态转换"""
        if new_state == self.current_state:
            return

        # 记录之前的状态
        self.previous_state = self.current_state

        # 执行退出动作
        if self.current_state and self.current_state in self.behaviors:
            exit_action = self.behaviors[self.current_state].exit_action
            if exit_action:
                exit_action()

        # 记录转换时间
        now = time.time()
        if self.current_state:
            duration = now - self.state_start_time
            # 更新统计
            if self.current_state in self.stats["transition_counts"]:
                self.stats["transition_counts"][self.current_state] += 1
            else:
                self.stats["transition_counts"][self.current_state] = 1

        # 更新状态
        self.current_state = new_state
        self.state_start_time = now
        self.last_transition_time = now

        # 记录历史
        self.state_history.append(new_state)
        if len(self.state_history) > 10:
            self.state_history.pop(0)

        # 执行进入动作
        if new_state in self.behaviors:
            enter_action = self.behaviors[new_state].enter_action
            if enter_action:
                enter_action()

        # 更新统计
        self.stats["total_transitions"] += 1

        logger.debug(
            f"[{self.name}] State transition: {self.previous_state} -> {new_state} ({reason})"
        )

    def update(self) -> Any:
        """更新状态机，返回当前状态"""
        if self.current_state is None:
            return None

        # 检查转换规则
        for transition in self.transitions:
            if transition.from_state != self.current_state:
                continue

            # 检查冷却时间
            if (
                time.time() - self.last_transition_time
                < self.config.transition_cooldown
            ):
                continue

            # 检查状态持续时间
            if time.time() - self.state_start_time < self.config.min_state_duration:
                continue

            # 检查条件
            try:
                if transition.condition():
                    self.transition_to(transition.to_state)
                    break
            except Exception as e:
                logger.error(f"Error checking transition condition: {e}")

        return self.current_state

    def get_current_behavior(self) -> Optional[StateBehavior]:
        """获取当前状态的行为配置"""
        if self.current_state and self.current_state in self.behaviors:
            return self.behaviors[self.current_state]
        return None

    def reset(self):
        """重置状态机"""
        self.current_state = None
        self.previous_state = None
        self.state_history.clear()
        self.state_start_time = 0
        self.last_transition_time = 0

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "current_state": self.current_state,
            "total_transitions": self.stats["total_transitions"],
            "state_counts": dict(self.stats["transition_counts"]),
        }


class HierarchicalStateMachine:
    """分层状态机

    管理多个并行的状态机（战斗、移动、特殊）。
    """

    def __init__(self, config: StateMachineConfig = None):
        self.config = config or StateMachineConfig()

        # 战斗状态机
        self.battle_sm = StateMachine("Battle", self.config)

        # 移动状态机
        self.movement_sm = StateMachine("Movement", self.config)

        # 特殊状态机
        self.special_sm = StateMachine("Special", self.config)

        # 设置默认转换规则
        self._setup_default_transitions()

    def _setup_default_transitions(self):
        """设置默认转换规则"""
        # 战斗状态转换
        self.battle_sm.add_transition(
            StateTransition(
                from_state=BattleState.IDLE,
                to_state=BattleState.AGGRESSIVE,
                condition=lambda: self._should_be_aggressive(),
                priority=1,
            )
        )

        self.battle_sm.add_transition(
            StateTransition(
                from_state=BattleState.IDLE,
                to_state=BattleState.DEFENSIVE,
                condition=lambda: self._should_be_defensive(),
                priority=1,
            )
        )

        self.battle_sm.add_transition(
            StateTransition(
                from_state=BattleState.AGGRESSIVE,
                to_state=BattleState.DEFENSIVE,
                condition=lambda: self._should_retreat(),
                priority=2,
            )
        )

        self.battle_sm.add_transition(
            StateTransition(
                from_state=BattleState.DEFENSIVE,
                to_state=BattleState.RETREAT,
                condition=lambda: self._should_heal(),
                priority=3,
            )
        )

        # 移动状态转换
        self.movement_sm.add_transition(
            StateTransition(
                from_state=MovementState.EXPLORING,
                to_state=MovementState.CHASING,
                condition=lambda: self._has_target(),
                priority=1,
            )
        )

        self.movement_sm.add_transition(
            StateTransition(
                from_state=MovementState.CHASING,
                to_state=MovementState.FLEEING,
                condition=lambda: self._should_flee(),
                priority=2,
            )
        )

        self.movement_sm.add_transition(
            StateTransition(
                from_state=MovementState.CHASING,
                to_state=MovementState.POSITIONING,
                condition=lambda: self._should_reposition(),
                priority=1,
            )
        )

    def _should_be_aggressive(self) -> bool:
        """是否应该采取激进策略"""
        # 子类实现
        return False

    def _should_be_defensive(self) -> bool:
        """是否应该采取防御策略"""
        # 子类实现
        return False

    def _should_retreat(self) -> bool:
        """是否应该撤退"""
        # 子类实现
        return False

    def _should_heal(self) -> bool:
        """是否应该治疗"""
        # 子类实现
        return False

    def _has_target(self) -> bool:
        """是否有目标"""
        # 子类实现
        return False

    def _should_flee(self) -> bool:
        """是否应该逃跑"""
        # 子类实现
        return False

    def _should_reposition(self) -> bool:
        """是否应该重新定位"""
        # 子类实现
        return False

    def update(
        self,
        threat_level: float,
        player_health: float,
        enemy_count: int,
        has_projectiles: bool,
        can_heal: bool,
    ) -> Dict[str, Any]:
        """更新状态机

        Args:
            threat_level: 威胁等级 (0-1)
            player_health: 玩家血量 (0-1)
            enemy_count: 敌人数
            has_projectiles: 是否有投射物
            can_heal: 是否可以治疗

        Returns:
            各状态机当前状态
        """
        # 更新战斗状态机
        self.battle_sm.update()

        # 更新移动状态机
        self.movement_sm.update()

        # 更新特殊状态机
        self.special_sm.update()

        return {
            "battle": self.battle_sm.current_state,
            "movement": self.movement_sm.current_state,
            "special": self.special_sm.current_state,
        }

    def reset(self):
        """重置所有状态机"""
        self.battle_sm.reset()
        self.movement_sm.reset()
        self.special_sm.reset()


def create_hierarchical_state_machine(
    config: StateMachineConfig = None,
) -> HierarchicalStateMachine:
    """创建分层状态机实例"""
    return HierarchicalStateMachine(config)
