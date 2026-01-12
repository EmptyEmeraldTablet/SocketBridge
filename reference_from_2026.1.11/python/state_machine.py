"""
状态机模块

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

        # 记录历史
        if self.current_state:
            self.state_history.append(self.current_state)
            duration = time.time() - self.state_start_time

            # 更新统计
            self._update_state_stats(self.current_state, duration)

        # 执行进入动作
        if new_state in self.behaviors:
            enter_action = self.behaviors[new_state].enter_action
            if enter_action:
                enter_action()

        # 更新状态
        self.current_state = new_state
        self.state_start_time = time.time()
        self.last_transition_time = time.time()

        # 更新统计
        self.stats["total_transitions"] += 1
        self.stats["transition_counts"][new_state] = (
            self.stats["transition_counts"].get(new_state, 0) + 1
        )

        logger.debug(
            f"[{self.name}] State transition: {self.previous_state} -> {new_state} ({reason})"
        )

    def _update_state_stats(self, state: Any, duration: float):
        """更新状态统计"""
        if state not in self.stats["avg_state_duration"]:
            self.stats["avg_state_duration"][state] = []

        self.stats["avg_state_duration"][state].append(duration)

        # 只保留最近10次
        if len(self.stats["avg_state_duration"][state]) > 10:
            self.stats["avg_state_duration"][state] = self.stats["avg_state_duration"][
                state
            ][-10:]

    def update(self) -> Any:
        """更新状态机"""
        # 检查是否满足最小状态持续时间
        if time.time() - self.state_start_time < self.config.min_state_duration:
            return self.current_state

        # 检查转换冷却
        if time.time() - self.last_transition_time < self.config.transition_cooldown:
            return self.current_state

        # 检查转换条件
        for transition in self.transitions:
            if (
                transition.from_state is None
                or transition.from_state == self.current_state
            ):
                if transition.condition():
                    self.transition_to(transition.to_state, f"condition met")
                    break

        # 执行更新动作
        if self.current_state in self.behaviors:
            update_action = self.behaviors[self.current_state].update_action
            if update_action:
                update_action()

        return self.current_state

    def get_avg_state_duration(self, state: Any) -> float:
        """获取状态的平均持续时间"""
        if state not in self.stats["avg_state_duration"]:
            return 0.0

        durations = self.stats["avg_state_duration"][state]
        if not durations:
            return 0.0

        return sum(durations) / len(durations)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "current_state": self.current_state.value if self.current_state else None,
            "previous_state": self.previous_state.value
            if self.previous_state
            else None,
            "state_duration": time.time() - self.state_start_time,
        }

    def reset(self):
        """重置状态机"""
        self.current_state = None
        self.previous_state = None
        self.state_history.clear()
        self.state_start_time = time.time()
        self.last_transition_time = 0
        self.stats["total_transitions"] = 0


class BattleStateMachine:
    """战斗状态机

    管理战斗中的状态转换。
    """

    def __init__(self, config: StateMachineConfig = None):
        self.config = config or StateMachineConfig()
        self.state_machine = StateMachine("BattleStateMachine", config)

        # 外部依赖（通过update注入）
        self._threat_level: float = 0.0
        self._player_health: float = 1.0
        self._enemy_count: int = 0
        self._has_projectiles: bool = False
        self._can_heal: bool = False

        self._setup_transitions()
        self._setup_behaviors()

    def _setup_transitions(self):
        """设置转换规则"""
        # 空闲 -> 战斗（发现敌人）
        self.state_machine.add_transition(
            StateTransition(
                from_state=BattleState.IDLE,
                to_state=BattleState.AGGRESSIVE,
                condition=lambda: self._enemy_count > 0,
                priority=10,
            )
        )

        # 激进 -> 防御（受到威胁）
        self.state_machine.add_transition(
            StateTransition(
                from_state=BattleState.AGGRESSIVE,
                to_state=BattleState.DEFENSIVE,
                condition=lambda: self._threat_level
                > self.config.high_threat_threshold,
                priority=20,
            )
        )

        # 任何状态 -> 躲避（投射物来袭）
        self.state_machine.add_transition(
            StateTransition(
                from_state=None,
                to_state=BattleState.DODGE,
                condition=lambda: self._has_projectiles and self._threat_level > 0.6,
                priority=100,  # 最高优先级
            )
        )

        # 任何状态 -> 撤退（低血量）
        self.state_machine.add_transition(
            StateTransition(
                from_state=None,
                to_state=BattleState.RETREAT,
                condition=lambda: self._player_health
                < self.config.retreat_health_threshold,
                priority=90,
            )
        )

        # 任何状态 -> 治疗（需要治疗且可治疗）
        self.state_machine.add_transition(
            StateTransition(
                from_state=None,
                to_state=BattleState.HEAL_PRIORITY,
                condition=lambda: self._can_heal
                and self._player_health < self.config.heal_health_threshold,
                priority=80,
            )
        )

        # 防御 -> 激进（威胁降低）
        self.state_machine.add_transition(
            StateTransition(
                from_state=BattleState.DEFENSIVE,
                to_state=BattleState.AGGRESSIVE,
                condition=lambda: self._threat_level < self.config.low_threat_threshold,
                priority=5,
            )
        )

        # 躲避 -> 防御（躲避完成）
        self.state_machine.add_transition(
            StateTransition(
                from_state=BattleState.DODGE,
                to_state=BattleState.DEFENSIVE,
                condition=lambda: not self._has_projectiles,
                priority=10,
            )
        )

        # 撤退 -> 防御（血量恢复）
        self.state_machine.add_transition(
            StateTransition(
                from_state=BattleState.RETREAT,
                to_state=BattleState.DEFENSIVE,
                condition=lambda: self._player_health > 0.5,
                priority=5,
            )
        )

        # 治疗 -> 激进（治疗完成）
        self.state_machine.add_transition(
            StateTransition(
                from_state=BattleState.HEAL_PRIORITY,
                to_state=BattleState.AGGRESSIVE,
                condition=lambda: self._player_health > 0.7,
                priority=5,
            )
        )

        # 战斗状态 -> 空闲（敌人清除）
        self.state_machine.add_transition(
            StateTransition(
                from_state=None,
                to_state=BattleState.IDLE,
                condition=lambda: self._enemy_count == 0
                and self._threat_level < self.config.low_threat_threshold,
                priority=1,
            )
        )

    def _setup_behaviors(self):
        """设置状态行为"""
        # 激进状态
        self.state_machine.set_behavior(
            StateBehavior(
                state=BattleState.AGGRESSIVE,
                move_speed_multiplier=1.2,
                attack_rate_multiplier=1.3,
                target_priority="nearest",
            )
        )

        # 防御状态
        self.state_machine.set_behavior(
            StateBehavior(
                state=BattleState.DEFENSIVE,
                move_speed_multiplier=0.9,
                attack_rate_multiplier=0.7,
                dodge_frequency=0.7,
                target_priority="weakest",
            )
        )

        # 躲避状态
        self.state_machine.set_behavior(
            StateBehavior(
                state=BattleState.DODGE,
                move_speed_multiplier=1.5,
                attack_rate_multiplier=0.0,  # 不攻击
                dodge_frequency=1.0,
            )
        )

        # 撤退状态
        self.state_machine.set_behavior(
            StateBehavior(
                state=BattleState.RETREAT,
                move_speed_multiplier=1.3,
                attack_rate_multiplier=0.0,
                target_priority="none",
            )
        )

        # 治疗状态
        self.state_machine.set_behavior(
            StateBehavior(
                state=BattleState.HEAL_PRIORITY,
                move_speed_multiplier=0.5,
                attack_rate_multiplier=0.0,
                target_priority="none",
            )
        )

    def update(
        self,
        threat_level: float,
        player_health: float,
        enemy_count: int,
        has_projectiles: bool,
        can_heal: bool,
    ) -> BattleState:
        """更新状态机"""
        self._threat_level = threat_level
        self._player_health = player_health
        self._enemy_count = enemy_count
        self._has_projectiles = has_projectiles
        self._can_heal = can_heal

        self.state_machine.update()

        return self.state_machine.current_state or BattleState.IDLE

    def get_behavior(self) -> Optional[StateBehavior]:
        """获取当前状态的行为配置"""
        if self.state_machine.current_state:
            return self.state_machine.behaviors.get(self.state_machine.current_state)
        return None

    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return self.state_machine.get_stats()


class HierarchicalStateMachine:
    """分层状态机

    组合多个状态机：战斗、移动、特殊状态。
    """

    def __init__(self, config: StateMachineConfig = None):
        self.config = config or StateMachineConfig()

        # 子状态机
        self.battle_sm = BattleStateMachine(config)
        self.movement_sm = StateMachine("MovementState", config)
        self.special_sm = StateMachine("SpecialState", config)

        # 状态同步规则
        self._sync_rules: List[Callable] = []
        self._setup_sync_rules()

    def _setup_sync_rules(self):
        """设置状态同步规则"""
        # 战斗状态影响移动状态
        self._sync_rules.append(lambda: self._sync_battle_to_movement())

        # 特殊状态覆盖其他状态
        self._sync_rules.append(lambda: self._sync_special_state())

    def _sync_battle_to_movement(self):
        """战斗状态同步到移动状态"""
        battle_state = self.battle_sm.state_machine.current_state

        if battle_state == BattleState.RETREAT:
            if self.movement_sm.current_state != MovementState.FLEEING:
                self.movement_sm.transition_to(MovementState.FLEEING, "retreat")

        elif battle_state in [BattleState.AGGRESSIVE, BattleState.HEAL_PRIORITY]:
            if self.movement_sm.current_state != MovementState.CHASING:
                self.movement_sm.transition_to(MovementState.CHASING, "aggressive")

        elif battle_state == BattleState.DEFENSIVE:
            if self.movement_sm.current_state != MovementState.POSITIONING:
                self.movement_sm.transition_to(MovementState.POSITIONING, "defensive")

        elif battle_state == BattleState.DODGE:
            if self.movement_sm.current_state != MovementState.FLEEING:
                self.movement_sm.transition_to(MovementState.FLEEING, "dodge")

        elif battle_state == BattleState.IDLE:
            if self.movement_sm.current_state != MovementState.EXPLORING:
                self.movement_sm.transition_to(MovementState.EXPLORING, "idle")

    def _sync_special_state(self):
        """特殊状态同步"""
        special_state = self.special_sm.current_state

        if special_state == SpecialState.USING_ITEM:
            # 使用道具时停止移动
            if self.movement_sm.current_state != MovementState.STATIONARY:
                self.movement_sm.transition_to(MovementState.STATIONARY, "using_item")

    def update(
        self,
        threat_level: float,
        player_health: float,
        enemy_count: int,
        has_projectiles: bool,
        can_heal: bool,
        has_target: bool = False,
        target_distance: float = 0,
    ) -> Dict[str, Any]:
        """
        更新所有状态机

        Returns:
            各状态机的当前状态
        """
        # 更新战斗状态机
        battle_state = self.battle_sm.update(
            threat_level, player_health, enemy_count, has_projectiles, can_heal
        )

        # 更新移动状态机（基于目标距离）
        self._update_movement_state(has_target, target_distance)

        # 执行状态同步
        for rule in self._sync_rules:
            rule()

        # 更新特殊状态机（简化：自动退出）
        if self.special_sm.current_state:
            duration = time.time() - self.special_sm.state_machine.state_start_time
            if duration > 1.0:  # 1秒后退出特殊状态
                self.special_sm.transition_to(SpecialState.NONE, "timeout")

        return {
            "battle": battle_state,
            "movement": self.movement_sm.current_state,
            "special": self.special_sm.current_state,
        }

    def _update_movement_state(self, has_target: bool, target_distance: float):
        """更新移动状态机内部状态"""
        # 基于目标更新移动状态
        if not has_target:
            if self.movement_sm.current_state != MovementState.EXPLORING:
                self.movement_sm.transition_to(MovementState.EXPLORING, "no_target")
        else:
            if self.movement_sm.current_state == MovementState.EXPLORING:
                if target_distance > 300:
                    self.movement_sm.transition_to(MovementState.CHASING, "target_far")
                else:
                    self.movement_sm.transition_to(
                        MovementState.POSITIONING, "target_near"
                    )

    def trigger_special(self, state: SpecialState):
        """触发特殊状态"""
        self.special_sm.transition_to(state, "triggered")

    def get_all_behaviors(self) -> Dict[str, Optional[StateBehavior]]:
        """获取所有状态机的行为配置"""
        return {
            "battle": self.battle_sm.get_behavior(),
            "movement": self.movement_sm.behaviors.get(
                self.movement_sm.current_state, None
            )
            if self.movement_sm.current_state
            else None,
            "special": self.special_sm.behaviors.get(
                self.special_sm.current_state, None
            )
            if self.special_sm.current_state
            else None,
        }

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """获取所有状态机的统计"""
        return {
            "battle": self.battle_sm.get_stats(),
            "movement": self.movement_sm.get_stats(),
            "special": self.special_sm.get_stats(),
        }

    def reset(self):
        """重置所有状态机"""
        self.battle_sm.state_machine.reset()
        self.movement_sm.reset()
        self.special_sm.reset()
