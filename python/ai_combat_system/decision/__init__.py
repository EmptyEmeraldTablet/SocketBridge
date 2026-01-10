"""
决策模块 (Decision Module)

制定高层策略，将局势评估转换为行动意图。

功能：
- 防御型行动（紧急躲避、战略性撤退、寻找掩体、治疗优先）
- 进攻型行动（集中攻击、清除威胁、位置压制、道具使用）
- 移动型行动（位置调整、走位规避、绕后攻击）
- 特殊行动（互动操作、环境利用、地形破坏）
"""

import math
import time
import logging
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

from ..perception import (
    GameState,
    PlayerState,
    EnemyState,
    ProjectileState,
    RoomLayout,
    Vector2D,
    ThreatLevel,
    MovementPattern,
)
from ..analysis import (
    SituationAssessment,
    ThreatInfo,
    OpportunityInfo,
    PositionScore,
    ResourceStatus,
    ActionPriority,
)

logger = logging.getLogger("DecisionModule")


class ActionType(Enum):
    """行动类型"""

    # 防御型
    EMERGENCY_DODGE = "emergency_dodge"  # 紧急躲避
    STRATEGIC_RETREAT = "strategic_retreat"  # 战略性撤退
    FIND_COVER = "find_cover"  # 寻找掩体
    HEAL = "heal"  # 治疗

    # 进攻型
    FOCUS_FIRE = "focus_fire"  # 集中攻击
    ELIMINATE_THREAT = "eliminate_threat"  # 清除威胁
    POSITION_SUPPRESSION = "position_suppression"  # 位置压制
    USE_ITEM = "use_item"  # 道具使用
    USE_BOMB = "use_bomb"  # 炸弹使用

    # 移动型
    POSITION_ADJUST = "position_adjust"  # 位置调整
    KITING = "kiting"  # 走位规避
    FLANK = "flank"  # 绕后攻击

    # 特殊
    INTERACT = "interact"  # 互动操作
    USE_ENVIRONMENT = "use_environment"  # 环境利用
    DESTROY_TERRAIN = "destroy_terrain"  # 地形破坏

    # 空操作
    IDLE = "idle"  # 空闲
    CONTINUE = "continue"  # 继续当前行动


@dataclass
class ActionIntent:
    """
    行动意图

    表达高层行动目标，不涉及具体执行细节。
    由规划模块转换为具体计划。
    """

    action_type: ActionType
    priority: int  # 1-10，数字越大优先级越高

    # 目标信息
    target_position: Optional[Vector2D] = None  # 目标位置
    target_entity_id: Optional[int] = None  # 目标实体ID

    # 方向信息
    move_direction: Optional[Vector2D] = None  # 移动方向
    aim_direction: Optional[Vector2D] = None  # 瞄准方向

    # 持续时间
    min_duration_frames: int = 1  # 最小持续帧数
    max_duration_frames: int = 30  # 最大持续帧数

    # 额外参数
    parameters: Dict[str, Any] = field(default_factory=dict)

    # 约束条件
    constraints: List[str] = field(default_factory=list)  # 如 "avoid_projectiles"

    def to_dict(self) -> Dict:
        return {
            "action_type": self.action_type.value,
            "priority": self.priority,
            "target_position": (
                (self.target_position.x, self.target_position.y)
                if self.target_position
                else None
            ),
            "target_entity_id": self.target_entity_id,
            "move_direction": (
                (self.move_direction.x, self.move_direction.y)
                if self.move_direction
                else None
            ),
            "aim_direction": (
                (self.aim_direction.x, self.aim_direction.y)
                if self.aim_direction
                else None
            ),
            "duration": f"{self.min_duration_frames}-{self.max_duration_frames}",
        }


@dataclass
class StrategyProfile:
    """
    策略配置

    控制AI的行为风格。
    """

    # 基础风格
    aggressiveness: float = 0.5  # 0-1，激进程度
    defensiveness: float = 0.5  # 0-1，保守程度
    risk_tolerance: float = 0.5  # 0-1，风险承受能力

    # 行为参数
    prefer_kiting: bool = True  # 喜欢走位而非硬刚
    prioritize_safety: bool = True  # 优先保证安全
    focus_fire_threshold: int = 2  # 集中攻击的敌人数量阈值
    healing_threshold: float = 0.4  # 治疗血量阈值

    # 移动偏好
    keep_distance: bool = True  # 保持距离
    ideal_combat_distance: float = 200.0  # 理想战斗距离
    retreat_when_outnumbered: bool = True  # 寡不敌众时撤退

    # 特殊偏好
    use_items_aggressively: bool = False  # 激进使用道具
    prefer_flanking: bool = True  # 喜欢绕后
    exploit_weaknesses: bool = True  # 攻击弱点

    @classmethod
    def aggressive(cls) -> "StrategyProfile":
        """激进风格"""
        return cls(
            aggressiveness=0.8,
            defensiveness=0.3,
            risk_tolerance=0.7,
            prefer_kiting=False,
            prioritize_safety=False,
            healing_threshold=0.2,
            use_items_aggressively=True,
        )

    @classmethod
    def defensive(cls) -> "StrategyProfile":
        """保守风格"""
        return cls(
            aggressiveness=0.3,
            defensiveness=0.8,
            risk_tolerance=0.3,
            prefer_kiting=True,
            prioritize_safety=True,
            healing_threshold=0.6,
            use_items_aggressively=False,
        )

    @classmethod
    def balanced(cls) -> "StrategyProfile":
        """平衡风格"""
        return cls()


@dataclass
class DecisionContext:
    """决策上下文"""

    game_state: GameState
    situation: SituationAssessment

    # 玩家信息
    player_pos: Vector2D
    player_vel: Vector2D

    # 策略配置
    strategy: StrategyProfile = field(default_factory=StrategyProfile)

    # 决策历史
    last_action: Optional[ActionIntent] = None
    consecutive_same_action: int = 0

    # 状态
    is_in_combat: bool = False
    is_low_hp: bool = False
    is_escaping: bool = False

    def __post_init__(self):
        if self.game_state.player:
            self.player_pos = self.game_state.player.position.pos
            self.player_vel = (
                self.game_state.player.velocity.vel
                if self.game_state.player.velocity
                else Vector2D(0, 0)
            )
            self.is_low_hp = (
                self.game_state.player.hp
                < self.game_state.player.max_hp * self.strategy.healing_threshold
            )


# ==================== 决策引擎 ====================


class DecisionEngine:
    """
    决策引擎

    基于局势评估和策略配置，生成行动意图。

    输入: 局势评估结果 (SituationAssessment)
    输出: 行动意图 (ActionIntent)
    """

    def __init__(self):
        self.strategy = StrategyProfile.balanced()
        self.action_history: deque = deque(maxlen=30)

    def set_strategy(self, strategy: StrategyProfile):
        """设置策略配置"""
        self.strategy = strategy

    def decide(
        self, situation: SituationAssessment, game_state: GameState
    ) -> ActionIntent:
        """
        生成行动意图

        Args:
            situation: 局势评估
            game_state: 游戏状态

        Returns:
            行动意图
        """
        # 创建决策上下文
        context = DecisionContext(
            game_state=game_state,
            situation=situation,
            player_pos=game_state.player.position.pos
            if game_state.player and game_state.player.position
            else Vector2D(0, 0),
            player_vel=game_state.player.velocity.vel
            if game_state.player and game_state.player.velocity
            else Vector2D(0, 0),
            strategy=self.strategy,
            last_action=self.action_history[-1] if self.action_history else None,
            consecutive_same_action=self._count_consecutive(),
        )

        # 决策流程
        action = self._decide_emergency_response(context)
        if action:
            self._record_action(action)
            return action

        action = self._decide_defensive_action(context)
        if action:
            self._record_action(action)
            return action

        action = self._decide_offensive_action(context)
        if action:
            self._record_action(action)
            return action

        action = self._decide_movement_action(context)
        if action:
            self._record_action(action)
            return action

        # 默认继续当前行动或空闲
        return self._decide_default_action(context)

    def _count_consecutive(self) -> int:
        """计算连续相同行动的数量"""
        if not self.action_history:
            return 0

        last_type = self.action_history[-1].action_type
        count = 0
        for action in reversed(self.action_history):
            if action.action_type == last_type:
                count += 1
            else:
                break
        return count

    def _record_action(self, action: ActionIntent):
        """记录行动历史"""
        self.action_history.append(action)

    def _decide_emergency_response(
        self, context: DecisionContext
    ) -> Optional[ActionIntent]:
        """紧急响应决策"""
        situation = context.situation

        # 紧急躲避
        if situation.immediate_threats:
            # 选择最危险的威胁
            most_dangerous = min(
                situation.immediate_threats,
                key=lambda t: (t.threat_level.value, -t.distance),
            )

            # 计算躲避方向
            if most_dangerous.direction:
                dodge_dir = most_dangerous.direction * -1
                dodge_pos = context.player_pos + dodge_dir * 150

                # 限制在房间内
                if context.game_state.room:
                    dodge_pos = self._clamp_to_room(dodge_pos, context.game_state.room)

                return ActionIntent(
                    action_type=ActionType.EMERGENCY_DODGE,
                    priority=10,
                    target_position=dodge_pos,
                    move_direction=dodge_dir.normalized(),
                    min_duration_frames=5,
                    max_duration_frames=15,
                    parameters={
                        "threat": most_dangerous.to_dict(),
                        "dodge_distance": 150,
                    },
                    constraints=["avoid_threat"],
                )

        return None

    def _decide_defensive_action(
        self, context: DecisionContext
    ) -> Optional[ActionIntent]:
        """防御性行动决策"""
        situation = context.situation
        strategy = context.strategy

        # 治疗优先
        if situation.resources.critical_hp_warning or (
            situation.resources.low_hp_warning and situation.resources.has_healing_item
        ):
            return ActionIntent(
                action_type=ActionType.HEAL,
                priority=9,
                parameters={
                    "current_hp": situation.resources.current_hp,
                    "max_hp": situation.resources.max_hp,
                    "has_healing_item": situation.resources.has_healing_item,
                },
            )

        # 战略性撤退
        if situation.overall_threat_level == ThreatLevel.HIGH or (
            strategy.retreat_when_outnumbered and situation.enemy_count > 3
        ):
            retreat_pos = self._find_retreat_position(context)
            if retreat_pos:
                retreat_dir = (retreat_pos - context.player_pos).normalized()

                return ActionIntent(
                    action_type=ActionType.STRATEGIC_RETREAT,
                    priority=8,
                    target_position=retreat_pos,
                    move_direction=retreat_dir,
                    min_duration_frames=10,
                    max_duration_frames=30,
                    parameters={
                        "threat_level": situation.overall_threat_level.name,
                        "enemy_count": situation.enemy_count,
                    },
                )

        # 寻找掩体
        if situation.overall_threat_level in [ThreatLevel.HIGH, ThreatLevel.MEDIUM]:
            cover_pos = self._find_cover_position(context)
            if cover_pos:
                return ActionIntent(
                    action_type=ActionType.FIND_COVER,
                    priority=7,
                    target_position=cover_pos,
                    min_duration_frames=10,
                    max_duration_frames=25,
                    parameters={"reason": "threat_level"},
                )

        return None

    def _decide_offensive_action(
        self, context: DecisionContext
    ) -> Optional[ActionIntent]:
        """进攻性行动决策"""
        situation = context.situation
        strategy = context.strategy

        if not situation.is_combat:
            return None

        # 集中攻击
        if len(situation.enemies) >= strategy.focus_fire_threshold:
            target = self._select_focus_fire_target(context)
            if target:
                aim_dir = (target.position.pos - context.player_pos).normalized()

                return ActionIntent(
                    action_type=ActionType.FOCUS_FIRE,
                    priority=6,
                    target_entity_id=target.entity_id,
                    aim_direction=aim_dir,
                    min_duration_frames=20,
                    max_duration_frames=60,
                    parameters={
                        "target_id": target.entity_id,
                        "target_hp": target.hp,
                        "target_distance": target.distance_to_player,
                    },
                    constraints=["maintain_distance"],
                )

        # 清除威胁
        if situation.threats:
            highest_threat = max(situation.threats, key=lambda t: t.priority)
            if highest_threat.source_type == "enemy":
                enemy = context.game_state.enemies.get(highest_threat.source_entity_id)
                if enemy:
                    aim_dir = (enemy.position.pos - context.player_pos).normalized()

                    return ActionIntent(
                        action_type=ActionType.ELIMINATE_THREAT,
                        priority=5,
                        target_entity_id=enemy.entity_id,
                        aim_direction=aim_dir,
                        parameters={
                            "threat_type": highest_threat.source_type,
                            "reason": "highest_threat",
                        },
                    )

        # 使用道具
        if strategy.use_items_aggressively and situation.opportunities:
            item_opp = next(
                (
                    o
                    for o in situation.opportunities
                    if o.opportunity_type == "item_pickup"
                ),
                None,
            )
            if item_opp and "use" in item_opp.requirements:
                return ActionIntent(
                    action_type=ActionType.USE_ITEM,
                    priority=4,
                    parameters={"opportunity": item_opp.description},
                )

        return None

    def _decide_movement_action(
        self, context: DecisionContext
    ) -> Optional[ActionIntent]:
        """移动型行动决策"""
        situation = context.situation
        strategy = context.strategy

        # 位置调整
        if situation.current_position_score:
            if situation.current_position_score.total_score < 0.4:
                # 当前位置不好，寻找更好的位置
                if situation.recommended_positions:
                    best = situation.recommended_positions[0]
                    if (
                        best.total_score
                        > situation.current_position_score.total_score + 0.2
                    ):
                        move_dir = (best.position - context.player_pos).normalized()

                        return ActionIntent(
                            action_type=ActionType.POSITION_ADJUST,
                            priority=3,
                            target_position=best.position,
                            move_direction=move_dir,
                            min_duration_frames=10,
                            max_duration_frames=30,
                            parameters={
                                "current_score": situation.current_position_score.total_score,
                                "target_score": best.total_score,
                            },
                        )

        # 走位规避（保持距离）
        if strategy.prefer_kiting and situation.enemy_count > 0:
            kite_action = self._decide_kiting(context)
            if kite_action:
                return kite_action

        # 绕后攻击
        if strategy.prefer_flanking and situation.enemy_count == 1:
            flank_action = self._decide_flanking(context)
            if flank_action:
                return flank_action

        return None

    def _decide_kiting(self, context: DecisionContext) -> Optional[ActionIntent]:
        """走位决策"""
        situation = context.situation
        strategy = context.strategy

        # 找最近的敌人
        nearest = situation.game_state.get_nearest_enemy(context.player_pos)
        if not nearest:
            return None

        # 计算理想距离
        ideal_dist = strategy.ideal_combat_distance
        current_dist = nearest.distance_to_player

        if current_dist < ideal_dist * 0.7:
            # 太近，需要后退
            retreat_dir = (context.player_pos - nearest.position.pos).normalized()

            # 找到合适的后退位置
            retreat_pos = self._find_kiting_position(context, retreat_dir)

            return ActionIntent(
                action_type=ActionType.KITING,
                priority=4,
                target_position=retreat_pos,
                move_direction=retreat_dir,
                min_duration_frames=5,
                max_duration_frames=20,
                parameters={
                    "reason": "too_close",
                    "current_distance": current_dist,
                    "ideal_distance": ideal_dist,
                },
            )

        elif current_dist > ideal_dist * 1.3:
            # 太远，需要靠近
            approach_dir = (nearest.position.pos - context.player_pos).normalized()

            return ActionIntent(
                action_type=ActionType.KITING,
                priority=3,
                move_direction=approach_dir,
                min_duration_frames=5,
                max_duration_frames=20,
                parameters={
                    "reason": "too_far",
                    "current_distance": current_dist,
                    "ideal_distance": ideal_dist,
                },
            )

        else:
            # 距离合适，绕圈移动
            circle_dir = self._calculate_circle_direction(context, nearest)

            return ActionIntent(
                action_type=ActionType.KITING,
                priority=2,
                move_direction=circle_dir,
                min_duration_frames=10,
                max_duration_frames=30,
                parameters={"reason": "maintain_distance", "style": "circle"},
            )

    def _decide_flanking(self, context: DecisionContext) -> Optional[ActionIntent]:
        """绕后决策"""
        situation = context.situation

        # 找唯一的敌人
        enemies = situation.game_state.get_active_enemies()
        if len(enemies) != 1:
            return None

        enemy = enemies[0]
        if not enemy.position:
            return None

        # 计算绕后方向（垂直于敌人-玩家连线）
        to_enemy = enemy.position.pos - context.player_pos
        perpendicular = Vector2D(-to_enemy.y, to_enemy.x).normalized()

        # 选择一个方向
        flank_pos = context.player_pos + perpendicular * 100

        # 限制在房间内
        if context.game_state.room:
            flank_pos = self._clamp_to_room(flank_pos, context.game_state.room)

        return ActionIntent(
            action_type=ActionType.FLANK,
            priority=3,
            target_position=flank_pos,
            move_direction=perpendicular,
            min_duration_frames=15,
            max_duration_frames=40,
            parameters={"target_id": enemy.entity_id},
        )

    def _decide_default_action(self, context: DecisionContext) -> ActionIntent:
        """默认行动决策"""
        # 继续当前行动或空闲
        if context.last_action and context.consecutive_same_action < 5:
            # 继续当前行动
            return ActionIntent(
                action_type=ActionType.CONTINUE,
                priority=1,
                parameters={"continued_action": context.last_action.action_type.value},
            )

        # 空闲
        return ActionIntent(
            action_type=ActionType.IDLE,
            priority=0,
            parameters={"reason": "no_threats_or_opportunities"},
        )

    # ==================== 辅助方法 ====================

    def _clamp_to_room(self, pos: Vector2D, room: RoomLayout) -> Vector2D:
        """限制位置在房间内"""
        margin = 40
        return Vector2D(
            max(room.top_left.x + margin, min(room.bottom_right.x - margin, pos.x)),
            max(room.top_left.y + margin, min(room.bottom_right.y - margin, pos.y)),
        )

    def _find_retreat_position(self, context: DecisionContext) -> Optional[Vector2D]:
        """寻找撤退位置"""
        # 撤退到房间中心或角落
        room = context.game_state.room
        if not room:
            return None

        # 计算敌人重心
        enemy_center = Vector2D(0, 0)
        for enemy in context.game_state.get_active_enemies():
            if enemy.position:
                enemy_center = enemy_center + enemy.position.pos
        enemy_center = enemy_center * (
            1.0 / max(1, len(context.game_state.get_active_enemies()))
        )

        # 撤退方向：远离敌人中心
        retreat_dir = (context.player_pos - enemy_center).normalized()

        # 在这个方向上找位置
        search_dist = 150
        for factor in [1.0, 1.5, 2.0]:
            candidate = context.player_pos + retreat_dir * search_dist * factor
            candidate = self._clamp_to_room(candidate, room)

            # 检查安全性
            safety = self._evaluate_position_safety(context, candidate)
            if safety > 0.5:
                return candidate

        # 回退到房间中心
        return room.center

    def _find_cover_position(self, context: DecisionContext) -> Optional[Vector2D]:
        """寻找掩体位置"""
        room = context.game_state.room
        if not room:
            return None

        # 寻找掩体位置
        corners = [
            Vector2D(room.top_left.x + 50, room.top_left.y + 50),
            Vector2D(room.bottom_right.x - 50, room.top_left.y + 50),
            Vector2D(room.top_left.x + 50, room.bottom_right.y - 50),
            Vector2D(room.bottom_right.x - 50, room.bottom_right.y - 50),
        ]

        best_pos = None
        best_score = -1

        for corner in corners:
            if not room.is_inside_room(corner):
                continue

            safety = self._evaluate_position_safety(context, corner)
            cover = self._evaluate_cover(context, corner)

            score = safety * 0.6 + cover * 0.4
            if score > best_score:
                best_score = score
                best_pos = corner

        return best_pos

    def _find_kiting_position(
        self, context: DecisionContext, desired_dir: Vector2D
    ) -> Vector2D:
        """寻找走位位置"""
        room = context.game_state.room
        if not room:
            return context.player_pos

        # 在期望方向上找位置
        search_dist = 100
        for factor in [0.5, 1.0, 1.5]:
            candidate = context.player_pos + desired_dir * search_dist * factor
            candidate = self._clamp_to_room(candidate, room)

            safety = self._evaluate_position_safety(context, candidate)
            if safety > 0.4:
                return candidate

        return context.player_pos + desired_dir * 50

    def _select_focus_fire_target(
        self, context: DecisionContext
    ) -> Optional[EnemyState]:
        """选择集中攻击的目标"""
        situation = context.situation

        # 优先攻击低血量敌人
        enemies = situation.game_state.get_active_enemies()
        if not enemies:
            return None

        # 按血量排序
        sorted_enemies = sorted(
            enemies, key=lambda e: e.hp / e.max_hp if e.max_hp > 0 else 1
        )

        # 考虑距离
        if context.strategy.exploit_weaknesses:
            return sorted_enemies[0]  # 最低血量

        return sorted_enemies[0]

    def _calculate_circle_direction(
        self, context: DecisionContext, enemy: EnemyState
    ) -> Vector2D:
        """计算绕圈移动方向"""
        if not enemy.position:
            return Vector2D(0, 0)

        # 计算垂直方向
        to_enemy = enemy.position.pos - context.player_pos
        perpendicular = Vector2D(-to_enemy.y, to_enemy.x).normalized()

        # 随机选择顺时针或逆时针
        if context.consecutive_same_action % 2 == 0:
            return perpendicular
        else:
            return perpendicular * -1

    def _evaluate_position_safety(
        self, context: DecisionContext, pos: Vector2D
    ) -> float:
        """评估位置安全性"""
        safety = 1.0

        # 投射物威胁
        for proj in context.game_state.get_enemy_projectiles():
            if not proj.position:
                continue

            dist = pos.distance_to(proj.position.pos)
            if dist < 100:
                safety -= 0.3 * (1 - dist / 100)

        # 敌人威胁
        for enemy in context.game_state.get_active_enemies():
            if not enemy.position:
                continue

            dist = pos.distance_to(enemy.position.pos)
            if dist < 80:
                safety -= 0.4 * (1 - dist / 80)

        return max(0.0, min(1.0, safety))

    def _evaluate_cover(self, context: DecisionContext, pos: Vector2D) -> float:
        """评估掩体价值"""
        room = context.game_state.room
        if not room:
            return 0.5

        cover_score = 0.0
        check_count = 0

        for direction in [
            Vector2D(-1, 0),
            Vector2D(1, 0),
            Vector2D(0, -1),
            Vector2D(0, 1),
        ]:
            check_pos = pos + direction * 50
            if not room.is_inside_room(check_pos, 20):
                cover_score += 0.5
            else:
                clearance = room.get_clearance(check_pos)
                if clearance < 25:
                    cover_score += 1
            check_count += 1

        return min(1.0, cover_score / check_count)


# ==================== 决策模块主类 ====================


class DecisionModule:
    """
    决策模块主类

    整合决策引擎和策略配置，
    将局势评估转换为行动意图。

    输入: 局势评估结果 (SituationAssessment)
    输出: 行动意图 (ActionIntent)
    """

    def __init__(self):
        self.engine = DecisionEngine()

        # 统计
        self.stats = {
            "total_decisions": 0,
            "action_distribution": {},  # 行动类型分布
            "avg_decision_time_ms": 0.0,
        }

    def set_strategy(self, strategy: StrategyProfile):
        """设置策略配置"""
        self.engine.set_strategy(strategy)

    def decide(
        self, situation: SituationAssessment, game_state: GameState
    ) -> ActionIntent:
        """
        生成行动意图

        Args:
            situation: 局势评估
            game_state: 游戏状态

        Returns:
            行动意图
        """
        start_time = time.time()

        action = self.engine.decide(situation, game_state)

        # 更新统计
        self.stats["total_decisions"] += 1
        action_type = action.action_type.value
        self.stats["action_distribution"][action_type] = (
            self.stats["action_distribution"].get(action_type, 0) + 1
        )

        decision_time = (time.time() - start_time) * 1000
        self.stats["avg_decision_time_ms"] = (
            self.stats["avg_decision_time_ms"] * 0.9 + decision_time * 0.1
        )

        return action

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_decisions": self.stats["total_decisions"],
            "action_distribution": self.stats["action_distribution"],
            "avg_decision_time_ms": self.stats["avg_decision_time_ms"],
        }


# ==================== 便捷函数 ====================


def create_decision_module(strategy: StrategyProfile = None) -> DecisionModule:
    """创建决策模块实例"""
    module = DecisionModule()
    if strategy:
        module.set_strategy(strategy)
    return module


# 导出主要类
__all__ = [
    "DecisionModule",
    "DecisionEngine",
    "ActionIntent",
    "ActionType",
    "StrategyProfile",
    "DecisionContext",
    "create_decision_module",
]
