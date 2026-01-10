"""
分析模块 (Analysis Module)

评估当前局势，计算关键指标。

子模块:
- 威胁评估器 (Threat Assessor): 即时威胁、潜在威胁、威胁等级分类
- 机会评估器 (Opportunity Evaluator): 安全位置、攻击窗口、弱点识别
- 位置评估器 (Position Evaluator): 掩体价值、机动空间、战略位置评分
- 资源状态分析 (Resource Analyzer): 生命值、弹药/充能、特殊能力冷却
"""

import math
import time
import logging
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

from ..perception import (
    GameState,
    PlayerState,
    EnemyState,
    ProjectileState,
    RoomLayout,
    HazardZone,
    Vector2D,
    ThreatLevel,
    EntityType,
)

logger = logging.getLogger("AnalysisModule")


class ActionPriority(Enum):
    """行动优先级"""

    EMERGENCY_DODGE = 1  # 紧急躲避（最高）
    HEAL = 2  # 治疗
    ESCAPE = 3  # 逃跑
    DEFENSIVE_POSITION = 4  # 防御性位置调整
    ATTACK = 5  # 攻击
    POSITION_ADJUST = 6  # 位置调整
    COLLECT = 7  # 收集物品
    EXPLORE = 8  # 探索（最低）


@dataclass
class ThreatInfo:
    """威胁信息"""

    threat_level: ThreatLevel
    source_entity_id: int
    source_type: str  # "projectile", "enemy", "hazard", "tnt"
    position: Vector2D
    distance: float
    estimated_impact_frames: int  # 预计撞击帧数，-1表示不会撞击
    danger_radius: float
    priority: int  # 威胁处理优先级

    # 详细信息
    direction: Optional[Vector2D] = None  # 威胁来源方向
    can_dodge: bool = True  # 是否可以躲避
    dodge_cost: float = 1.0  # 躲避代价（相对值）

    def to_dict(self) -> Dict:
        return {
            "threat_level": self.threat_level.name,
            "source_entity_id": self.source_entity_id,
            "source_type": self.source_type,
            "position": (self.position.x, self.position.y),
            "distance": self.distance,
            "estimated_impact_frames": self.estimated_impact_frames,
            "danger_radius": self.danger_radius,
            "priority": self.priority,
        }


@dataclass
class OpportunityInfo:
    """机会信息"""

    opportunity_type: str  # "safe_spot", "attack_window", "weak_enemy", "item_pickup"
    position: Vector2D
    value: float  # 机会价值 0-1
    description: str

    # 详细信息
    safety_score: float = 1.0  # 安全性评分
    distance_to_player: float = float("inf")
    time_window: Optional[int] = None  # 可用时间窗口（帧数）
    requirements: List[str] = field(default_factory=list)  # 执行要求


@dataclass
class PositionScore:
    """位置评分"""

    position: Vector2D
    total_score: float
    breakdown: Dict[str, float] = field(default_factory=dict)

    # 详细评分
    safety_score: float = 0.0  # 安全性
    cover_score: float = 0.0  # 掩体价值
    mobility_score: float = 0.0  # 机动性
    strategic_score: float = 0.0  # 战略价值
    escape_score: float = 0.0  # 逃跑路线


@dataclass
class ResourceStatus:
    """资源状态"""

    # 生命值
    current_hp: float = 0.0
    max_hp: float = 0.0
    hp_percentage: float = 1.0
    hp_trend: str = "stable"  # "increasing", "stable", "declining"

    # 特殊资源
    coins: int = 0
    bombs: int = 0
    keys: int = 0

    # 主动道具
    active_items: Dict = field(default_factory=dict)
    has_healing_item: bool = False
    has_damage_item: bool = False

    # 特殊状态
    is_invincible: bool = False
    invincible_timer: float = 0.0
    can_shoot: bool = True

    # 危险信号
    low_hp_warning: bool = False
    critical_hp_warning: bool = False
    no_bombs_warning: bool = False

    def get_healing_need(self) -> float:
        """获取治疗需求（0-1，1表示非常需要治疗）"""
        if self.max_hp <= 0:
            return 1.0
        return 1.0 - self.hp_percentage


@dataclass
class SituationAssessment:
    """局势评估结果"""

    # 整体评估
    overall_threat_level: ThreatLevel = ThreatLevel.LOW
    is_combat: bool = False
    is_boss_fight: bool = False
    room_clear_progress: float = 0.0  # 0-1

    # 威胁信息
    threats: List[ThreatInfo] = field(default_factory=list)
    immediate_threats: List[ThreatInfo] = field(default_factory=list)

    # 机会信息
    opportunities: List[OpportunityInfo] = field(default_factory=list)

    # 位置评估
    current_position_score: Optional[PositionScore] = None
    recommended_positions: List[PositionScore] = field(default_factory=list)

    # 资源状态
    resources: Optional[ResourceStatus] = None

    # 建议行动
    suggested_action: ActionPriority = ActionPriority.EXPLORE
    action_details: Dict = field(default_factory=dict)

    # 额外信息
    enemy_count: int = 0
    active_projectile_count: int = 0
    nearest_enemy_distance: float = float("inf")

    def to_dict(self) -> Dict:
        return {
            "overall_threat_level": self.overall_threat_level.name,
            "is_combat": self.is_combat,
            "is_boss_fight": self.is_boss_fight,
            "room_clear_progress": self.room_clear_progress,
            "threat_count": len(self.threats),
            "immediate_threat_count": len(self.immediate_threats),
            "opportunity_count": len(self.opportunities),
            "enemy_count": self.enemy_count,
            "nearest_enemy_distance": self.nearest_enemy_distance,
            "suggested_action": self.suggested_action.name,
            "hp_percentage": self.resources.hp_percentage if self.resources else 0,
        }


# ==================== 威胁评估器 ====================


class ThreatAssessor:
    """
    威胁评估器

    功能：
    - 即时威胁计算（距离≤X的敌人/投射物）
    - 潜在威胁预测（敌人攻击预判）
    - 威胁等级分类（高/中/低）
    - 威胁来源方向分析
    """

    def __init__(self):
        # 威胁阈值配置
        self.immediate_threat_distance = 150.0  # 即时威胁距离
        self.potential_threat_distance = 300.0  # 潜在威胁距离
        self.critical_threat_distance = 80.0  # 紧急威胁距离

        # 威胁权重
        self.projectile_threat_weight = 1.0
        self.enemy_melee_threat_weight = 0.7
        self.enemy_ranged_threat_weight = 0.9
        self.hazard_threat_weight = 0.8
        self.tnt_threat_weight = 1.0

        # 预测参数
        self.impact_prediction_frames = 30  # 预测帧数

    def assess_threats(
        self, game_state: GameState
    ) -> Tuple[List[ThreatInfo], List[ThreatInfo]]:
        """
        评估所有威胁

        Args:
            game_state: 当前游戏状态

        Returns:
            (所有威胁, 即时威胁)
        """
        threats = []
        immediate_threats = []

        player_pos = self._get_player_position(game_state)
        if not player_pos:
            return threats, immediate_threats

        # 评估投射物威胁
        for proj in game_state.get_enemy_projectiles():
            threat = self._assess_projectile_threat(proj, player_pos)
            if threat:
                threats.append(threat)
                if threat.threat_level == ThreatLevel.CRITICAL:
                    immediate_threats.append(threat)

        # 评估敌人威胁
        for enemy in game_state.get_active_enemies():
            threat = self._assess_enemy_threat(enemy, player_pos)
            if threat:
                threats.append(threat)
                if threat.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH]:
                    immediate_threats.append(threat)

        # 评估危险区域威胁
        for hazard in game_state.hazard_zones:
            threat = self._assess_hazard_threat(hazard, player_pos)
            if threat:
                threats.append(threat)
                if threat.threat_level == ThreatLevel.CRITICAL:
                    immediate_threats.append(threat)

        # 排序
        threats.sort(key=lambda t: (t.priority, t.distance))
        immediate_threats.sort(key=lambda t: (t.priority, t.distance))

        return threats, immediate_threats

    def _get_player_position(self, game_state: GameState) -> Optional[Vector2D]:
        """获取玩家位置"""
        if game_state.player and game_state.player.position:
            return game_state.player.position.pos
        return None

    def _assess_projectile_threat(
        self, projectile: ProjectileState, player_pos: Vector2D
    ) -> Optional[ThreatInfo]:
        """评估投射物威胁"""
        if not projectile.position:
            return None

        proj_pos = projectile.position.pos
        distance = proj_pos.distance_to(player_pos)

        # 检查是否可能击中玩家
        impact_info = self._predict_impact(projectile, player_pos)

        if impact_info:
            impact_pos, frames_to_impact = impact_info

            # 计算威胁等级
            if distance < self.critical_threat_distance or frames_to_impact < 15:
                threat_level = ThreatLevel.CRITICAL
                priority = 1
            elif distance < self.immediate_threat_distance or frames_to_impact < 30:
                threat_level = ThreatLevel.HIGH
                priority = 2
            elif distance < self.potential_threat_distance:
                threat_level = ThreatLevel.MEDIUM
                priority = 3
            else:
                return None  # 太远，忽略

        else:
            # 没有预测到撞击，使用距离判断
            if distance < self.critical_threat_distance:
                threat_level = ThreatLevel.HIGH
                priority = 2
            elif distance < self.immediate_threat_distance:
                threat_level = ThreatLevel.MEDIUM
                priority = 3
            elif distance < self.potential_threat_distance:
                threat_level = ThreatLevel.LOW
                priority = 4
            else:
                return None

        # 计算威胁来源方向
        direction = (player_pos - proj_pos).normalized()

        # 计算躲避代价
        dodge_cost = self._calculate_dodge_cost(
            distance, frames_to_impact if impact_info else None
        )

        return ThreatInfo(
            threat_level=threat_level,
            source_entity_id=projectile.entity_id,
            source_type="projectile",
            position=proj_pos,
            distance=distance,
            estimated_impact_frames=impact_info[1] if impact_info else -1,
            danger_radius=projectile.collision_radius * 2,
            priority=priority,
            direction=direction,
            can_dodge=True,
            dodge_cost=dodge_cost,
        )

    def _assess_enemy_threat(
        self, enemy: EnemyState, player_pos: Vector2D
    ) -> Optional[ThreatInfo]:
        """评估敌人威胁"""
        if not enemy.position:
            return None

        enemy_pos = enemy.position.pos
        distance = enemy.distance_to_player

        if distance > self.potential_threat_distance:
            return None

        # 判断敌人类型和威胁
        if enemy.is_boss:
            threat_level = ThreatLevel.HIGH if distance < 200 else ThreatLevel.MEDIUM
            priority = 2
            weight = self.enemy_ranged_threat_weight * 1.5
        else:
            if distance < self.critical_threat_distance:
                threat_level = ThreatLevel.CRITICAL
                priority = 1
            elif distance < self.immediate_threat_distance:
                threat_level = ThreatLevel.HIGH
                priority = 2
            elif distance < self.potential_threat_distance:
                threat_level = ThreatLevel.MEDIUM
                priority = 3
            else:
                threat_level = ThreatLevel.LOW
                priority = 4

            weight = self.enemy_melee_threat_weight

        # 检查敌人是否在攻击
        is_attacking = enemy.is_attacking or (
            enemy.projectile_cooldown <= 0 and enemy.distance_to_player < 150
        )

        if is_attacking:
            threat_level = ThreatLevel(max(0, threat_level.value - 1))

        # 计算威胁来源方向
        direction = (player_pos - enemy_pos).normalized()

        return ThreatInfo(
            threat_level=threat_level,
            source_entity_id=enemy.entity_id,
            source_type="enemy",
            position=enemy_pos,
            distance=distance,
            estimated_impact_frames=-1,
            danger_radius=enemy.collision_radius + 30,
            priority=priority,
            direction=direction,
            can_dodge=distance > 50,
            dodge_cost=1.0 / (distance / 100),
        )

    def _assess_hazard_threat(
        self, hazard: HazardZone, player_pos: Vector2D
    ) -> Optional[ThreatInfo]:
        """评估危险区域威胁"""
        distance = hazard.position.distance_to(player_pos)

        if distance > hazard.radius + 50:
            return None

        # 计算威胁等级
        if distance < hazard.radius * 0.5:
            threat_level = ThreatLevel.CRITICAL
            priority = 1
        elif distance < hazard.radius:
            threat_level = ThreatLevel.HIGH
            priority = 2
        else:
            threat_level = ThreatLevel.MEDIUM
            priority = 3

        # 计算威胁来源方向
        direction = (player_pos - hazard.position).normalized()

        return ThreatInfo(
            threat_level=threat_level,
            source_entity_id=hazard.source_entity_id or -1,
            source_type=hazard.hazard_type,
            position=hazard.position,
            distance=distance,
            estimated_impact_frames=-1,
            danger_radius=hazard.radius,
            priority=priority,
            direction=direction,
            can_dodge=True,
            dodge_cost=0.8,
        )

    def _predict_impact(
        self, projectile: ProjectileState, target_pos: Vector2D
    ) -> Optional[Tuple[Vector2D, int]]:
        """预测投射物撞击"""
        if not projectile.velocity:
            return None

        proj_pos = projectile.position.pos
        proj_vel = projectile.velocity.vel

        speed = proj_vel.length()
        if speed < 0.1:
            return None

        # 到目标的向量
        to_target = target_pos - proj_pos

        # 检查是否朝向目标
        direction = proj_vel.normalized()
        to_target_dir = to_target.normalized()

        dot = direction.dot(to_target_dir)
        if dot < 0.8:  # 不太朝向目标
            return None

        # 计算距离和时间
        distance = to_target.length()
        frames_to_impact = int(distance / speed) if speed > 0 else -1

        if frames_to_impact > self.impact_prediction_frames:
            return None  # 太远，不考虑

        impact_pos = proj_pos + direction * distance
        return (impact_pos, frames_to_impact)

    def _calculate_dodge_cost(
        self, distance: float, frames_to_impact: Optional[int]
    ) -> float:
        """计算躲避代价"""
        if frames_to_impact is not None and frames_to_impact > 0:
            # 有时间预测，使用撞击前帧数计算
            return max(0.2, 1.0 - frames_to_impact / 60.0)
        else:
            # 使用距离计算
            return max(0.3, 1.0 - distance / 200.0)


# ==================== 机会评估器 ====================


class OpportunityEvaluator:
    """
    机会评估器

    功能：
    - 安全位置识别
    - 攻击窗口分析（敌人攻击间隔）
    - 弱点识别（低血量敌人、位置优势）
    - 道具使用时机评估
    """

    def __init__(self):
        # 配置
        self.safe_distance = 200.0  # 安全距离
        self.attack_window_frames = 60  # 攻击窗口帧数
        self.weak_enemy_threshold = 0.3  # 弱敌人血量阈值
        self.position_advantage_angle = 45  # 位置优势角度（度）

    def evaluate_opportunities(self, game_state: GameState) -> List[OpportunityInfo]:
        """
        评估所有机会

        Args:
            game_state: 当前游戏状态

        Returns:
            机会列表
        """
        opportunities = []

        player_pos = self._get_player_position(game_state)
        if not player_pos:
            return opportunities

        # 评估安全位置
        safe_spots = self._find_safe_spots(game_state, player_pos)
        for spot in safe_spots:
            opportunities.append(spot)

        # 评估攻击窗口
        attack_windows = self._find_attack_windows(game_state, player_pos)
        for window in attack_windows:
            opportunities.append(window)

        # 评估弱点敌人
        weak_enemies = self._find_weak_enemies(game_state, player_pos)
        for enemy in weak_enemies:
            opportunities.append(enemy)

        # 评估道具使用时机
        item_opportunities = self._evaluate_item_opportunities(game_state)
        for item in item_opportunities:
            opportunities.append(item)

        # 按价值排序
        opportunities.sort(key=lambda o: o.value, reverse=True)

        return opportunities

    def _get_player_position(self, game_state: GameState) -> Optional[Vector2D]:
        """获取玩家位置"""
        if game_state.player and game_state.player.position:
            return game_state.player.position.pos
        return None

    def _find_safe_spots(
        self, game_state: GameState, player_pos: Vector2D
    ) -> List[OpportunityInfo]:
        """寻找安全位置"""
        spots = []

        # 评估当前位置的安全性
        current_safety = self._calculate_position_safety(game_state, player_pos)

        if current_safety > 0.7:
            spots.append(
                OpportunityInfo(
                    opportunity_type="safe_spot",
                    position=player_pos,
                    value=current_safety * 0.5,
                    description="当前位置安全",
                    safety_score=current_safety,
                    distance_to_player=0,
                )
            )

        # 寻找更好的安全位置
        room = game_state.room
        if room:
            # 检查房间中心
            center = room.center
            center_safety = self._calculate_position_safety(game_state, center)

            if center_safety > current_safety:
                spots.append(
                    OpportunityInfo(
                        opportunity_type="safe_spot",
                        position=center,
                        value=center_safety * 0.7,
                        description="房间中心较安全",
                        safety_score=center_safety,
                        distance_to_player=center.distance_to(player_pos),
                    )
                )

            # 检查角落
            corners = [
                Vector2D(room.top_left.x + 30, room.top_left.y + 30),
                Vector2D(room.bottom_right.x - 30, room.top_left.y + 30),
                Vector2D(room.top_left.x + 30, room.bottom_right.y - 30),
                Vector2D(room.bottom_right.x - 30, room.bottom_right.y - 30),
            ]

            for corner in corners:
                if room.is_inside_room(corner):
                    corner_safety = self._calculate_position_safety(game_state, corner)
                    if corner_safety > current_safety + 0.2:
                        spots.append(
                            OpportunityInfo(
                                opportunity_type="safe_spot",
                                position=corner,
                                value=corner_safety * 0.6,
                                description=f"角落安全位置",
                                safety_score=corner_safety,
                                distance_to_player=corner.distance_to(player_pos),
                            )
                        )

        return spots

    def _calculate_position_safety(self, game_state: GameState, pos: Vector2D) -> float:
        """计算位置安全性"""
        safety = 1.0

        # 检查投射物威胁
        for proj in game_state.get_enemy_projectiles():
            if not proj.position:
                continue

            dist = pos.distance_to(proj.position.pos)
            if dist < 100:
                safety -= 0.3 * (1 - dist / 100)

        # 检查敌人距离
        for enemy in game_state.get_active_enemies():
            if not enemy.position:
                continue

            dist = pos.distance_to(enemy.position.pos)
            if dist < 80:
                safety -= 0.4 * (1 - dist / 80)
            elif dist < 150:
                safety -= 0.1 * (1 - dist / 150)

        # 检查危险区域
        for hazard in game_state.hazard_zones:
            if hazard.contains_point(pos):
                safety -= 0.5

        return max(0.0, min(1.0, safety))

    def _find_attack_windows(
        self, game_state: GameState, player_pos: Vector2D
    ) -> List[OpportunityInfo]:
        """寻找攻击窗口"""
        windows = []

        for enemy in game_state.get_active_enemies():
            if not enemy.position:
                continue

            # 检查敌人是否在攻击冷却中
            if enemy.projectile_cooldown > self.attack_window_frames:
                # 敌人在冷却，可以安全攻击
                dist = enemy.distance_to_player

                if dist < 300:  # 在攻击范围内
                    windows.append(
                        OpportunityInfo(
                            opportunity_type="attack_window",
                            position=enemy.position.pos,
                            value=0.6 * (1 - dist / 400),
                            description=f"敌人冷却中 ({enemy.projectile_cooldown}帧)",
                            safety_score=0.7,
                            distance_to_player=dist,
                            time_window=enemy.projectile_cooldown,
                            requirements=["shoot_enemy"],
                        )
                    )

        return windows

    def _find_weak_enemies(
        self, game_state: GameState, player_pos: Vector2D
    ) -> List[OpportunityInfo]:
        """寻找弱敌人"""
        weak_enemies = []

        for enemy in game_state.get_active_enemies():
            if enemy.hp <= 0:
                continue

            hp_ratio = enemy.hp / enemy.max_hp if enemy.max_hp > 0 else 1.0

            if hp_ratio < self.weak_enemy_threshold:
                # 低血量敌人
                dist = enemy.distance_to_player

                weak_enemies.append(
                    OpportunityInfo(
                        opportunity_type="weak_enemy",
                        position=enemy.position.pos,
                        value=(1 - hp_ratio) * 0.8,
                        description=f"低血量敌人 (HP: {enemy.hp:.0f}/{enemy.max_hp:.0f})",
                        safety_score=0.6,
                        distance_to_player=dist,
                        requirements=["attack_enemy"],
                    )
                )

        return weak_enemies

    def _evaluate_item_opportunities(
        self, game_state: GameState
    ) -> List[OpportunityInfo]:
        """评估道具使用时机"""
        opportunities = []

        player = game_state.player
        if not player:
            return opportunities

        # 检查治疗道具
        if player.hp < player.max_hp * 0.5:
            opportunities.append(
                OpportunityInfo(
                    opportunity_type="item_pickup",
                    position=Vector2D(0, 0),
                    value=0.7,
                    description="低血量，考虑使用治疗道具",
                    safety_score=0.5,
                    requirements=["use_healing_item"],
                )
            )

        # 检查主动道具充能
        for slot, item in player.active_items.items():
            charge = item.get("charge", 0)
            max_charge = item.get("max_charge", 0)

            if max_charge > 0 and charge >= max_charge:
                opportunities.append(
                    OpportunityInfo(
                        opportunity_type="item_pickup",
                        position=Vector2D(0, 0),
                        value=0.5,
                        description=f"主动道具已充满 ({charge}/{max_charge})",
                        safety_score=0.8,
                        requirements=["use_active_item"],
                    )
                )

        return opportunities


# ==================== 位置评估器 ====================


class PositionEvaluator:
    """
    位置评估器

    功能：
    - 掩体价值评估
    - 机动空间评估
    - 战略位置评分（如房间中心、门口）
    - 逃跑路线质量评估
    """

    def __init__(self):
        # 配置
        self.min_clearance = 30.0  # 最小清空距离
        self.cover_check_radius = 100.0  # 掩体检查半径
        self.escape_route_length = 200.0  # 逃跑路线长度

    def evaluate_position(
        self, game_state: GameState, position: Vector2D
    ) -> PositionScore:
        """
        评估位置得分

        Args:
            game_state: 当前游戏状态
            position: 要评估的位置

        Returns:
            位置评分
        """
        room = game_state.room

        breakdown = {}

        # 1. 安全性评分
        safety_score = self._evaluate_safety(game_state, position)
        breakdown["safety"] = safety_score

        # 2. 掩体价值评分
        cover_score = self._evaluate_cover(game_state, position)
        breakdown["cover"] = cover_score

        # 3. 机动性评分
        mobility_score = self._evaluate_mobility(game_state, position)
        breakdown["mobility"] = mobility_score

        # 4. 战略位置评分
        strategic_score = self._evaluate_strategic(game_state, position)
        breakdown["strategic"] = strategic_score

        # 5. 逃跑路线评分
        escape_score = self._evaluate_escape_routes(game_state, position)
        breakdown["escape"] = escape_score

        # 计算总分
        weights = {
            "safety": 0.35,
            "cover": 0.15,
            "mobility": 0.2,
            "strategic": 0.15,
            "escape": 0.15,
        }

        total_score = sum(breakdown[k] * weights[k] for k in weights)

        return PositionScore(
            position=position,
            total_score=total_score,
            breakdown=breakdown,
            safety_score=safety_score,
            cover_score=cover_score,
            mobility_score=mobility_score,
            strategic_score=strategic_score,
            escape_score=escape_score,
        )

    def _evaluate_safety(self, game_state: GameState, position: Vector2D) -> float:
        """评估安全性"""
        safety = 1.0

        # 投射物距离
        for proj in game_state.get_enemy_projectiles():
            if not proj.position:
                continue

            dist = position.distance_to(proj.position.pos)
            if dist < 80:
                safety -= 0.5
            elif dist < 150:
                safety -= 0.2

        # 敌人距离
        for enemy in game_state.get_active_enemies():
            if not enemy.position:
                continue

            dist = position.distance_to(enemy.position.pos)
            if dist < 60:
                safety -= 0.4
            elif dist < 120:
                safety -= 0.15

        # 危险区域
        for hazard in game_state.hazard_zones:
            if hazard.contains_point(position):
                safety -= 0.6

        return max(0.0, min(1.0, safety))

    def _evaluate_cover(self, game_state: GameState, position: Vector2D) -> float:
        """评估掩体价值"""
        if not game_state.room:
            return 0.5

        # 检查四周是否有障碍物作为掩体
        cover_score = 0.0
        cover_count = 0

        check_directions = [
            Vector2D(-1, 0),
            Vector2D(1, 0),
            Vector2D(0, -1),
            Vector2D(0, 1),
        ]

        for direction in check_directions:
            check_pos = position + direction * 50
            if not game_state.room.is_inside_room(check_pos, 20):
                cover_count += 0.5  # 边界提供部分掩体
                continue

            # 检查是否有障碍物
            clearance = game_state.room.get_clearance(check_pos)
            if clearance < 25:  # 有障碍物
                cover_count += 1

        return min(1.0, cover_count / 4)

    def _evaluate_mobility(self, game_state: GameState, position: Vector2D) -> float:
        """评估机动性"""
        if not game_state.room:
            return 0.5

        # 检查四周是否有空间移动
        mobility = 0.0
        check_count = 0

        check_directions = [
            Vector2D(-1, 0),
            Vector2D(1, 0),
            Vector2D(0, -1),
            Vector2D(0, 1),
            Vector2D(-1, -1),
            Vector2D(1, -1),
            Vector2D(-1, 1),
            Vector2D(1, 1),
        ]

        for direction in check_directions:
            check_pos = position + direction * 50
            if not game_state.room.is_inside_room(check_pos, 20):
                continue

            clearance = game_state.room.get_clearance(check_pos)
            if clearance >= 35:  # 有足够的移动空间
                mobility += 1
            elif clearance >= 20:
                mobility += 0.5
            check_count += 1

        if check_count == 0:
            return 0.0

        return min(1.0, mobility / check_count)

    def _evaluate_strategic(self, game_state: GameState, position: Vector2D) -> float:
        """评估战略位置"""
        if not game_state.room:
            return 0.5

        strategic = 0.5

        # 房间中心加成
        center = game_state.room.center
        dist_to_center = position.distance_to(center)
        room_size = min(game_state.room.width, game_state.room.height)

        if dist_to_center < room_size * 0.2:
            strategic += 0.3
        elif dist_to_center < room_size * 0.3:
            strategic += 0.15

        # 门口位置（方便进出）
        for door_idx, door in game_state.room.doors.items():
            # 门口位置大致在房间边界
            door_pos = self._get_door_position(game_state.room, door_idx)
            if door_pos:
                dist_to_door = position.distance_to(door_pos)
                if dist_to_door < 80:
                    strategic -= 0.2  # 门口容易受到攻击

        # Boss战时，中心位置更有利
        if game_state.room.has_boss:
            if dist_to_center < room_size * 0.25:
                strategic += 0.2

        return max(0.0, min(1.0, strategic))

    def _get_door_position(self, room: RoomLayout, door_idx: int) -> Optional[Vector2D]:
        """获取门口位置"""
        if not room.top_left or not room.bottom_right:
            return None

        width = room.bottom_right.x - room.top_left.x
        height = room.bottom_right.y - room.top_left.y

        # 根据门槽位计算位置
        if door_idx == 0:  # LEFT
            return Vector2D(room.top_left.x, room.top_left.y + height / 2)
        elif door_idx == 1:  # UP
            return Vector2D(room.top_left.x + width / 2, room.top_left.y)
        elif door_idx == 2:  # RIGHT
            return Vector2D(room.bottom_right.x, room.top_left.y + height / 2)
        elif door_idx == 3:  # DOWN
            return Vector2D(room.top_left.x + width / 2, room.bottom_right.y)

        return None

    def _evaluate_escape_routes(
        self, game_state: GameState, position: Vector2D
    ) -> float:
        """评估逃跑路线"""
        if not game_state.room:
            return 0.5

        escape_score = 0.0

        # 检查到各边界的距离
        distances = [
            position.x - game_state.room.top_left.x,
            game_state.room.bottom_right.x - position.x,
            position.y - game_state.room.top_left.y,
            game_state.room.bottom_right.y - position.y,
        ]

        # 最近的边界距离
        min_dist = min(distances)

        if min_dist > 100:
            escape_score = 1.0
        elif min_dist > 50:
            escape_score = 0.7
        elif min_dist > 30:
            escape_score = 0.4
        else:
            escape_score = 0.1

        # 检查边界附近是否有障碍物
        for dist, direction in zip(
            distances,
            [Vector2D(-1, 0), Vector2D(1, 0), Vector2D(0, -1), Vector2D(0, 1)],
        ):
            if dist < 80:
                check_pos = position + direction * dist
                clearance = game_state.room.get_clearance(check_pos)
                if clearance < 25:
                    escape_score -= 0.2

        return max(0.0, min(1.0, escape_score))

    def find_best_positions(
        self, game_state: GameState, count: int = 3
    ) -> List[PositionScore]:
        """寻找最佳位置"""
        positions = []

        if not game_state.room:
            return positions

        room = game_state.room

        # 评估当前位置
        if game_state.player and game_state.player.position:
            current_pos = game_state.player.position.pos
            positions.append(self.evaluate_position(game_state, current_pos))

        # 评估房间中心
        positions.append(self.evaluate_position(game_state, room.center))

        # 评估各角落
        corners = [
            Vector2D(room.top_left.x + 40, room.top_left.y + 40),
            Vector2D(room.bottom_right.x - 40, room.top_left.y + 40),
            Vector2D(room.top_left.x + 40, room.bottom_right.y - 40),
            Vector2D(room.bottom_right.x - 40, room.bottom_right.y - 40),
        ]

        for corner in corners:
            if room.is_inside_room(corner):
                positions.append(self.evaluate_position(game_state, corner))

        # 评估边缘中点
        midpoints = [
            Vector2D(room.top_left.x + 40, (room.top_left.y + room.bottom_right.y) / 2),
            Vector2D(
                room.bottom_right.x - 40, (room.top_left.y + room.bottom_right.y) / 2
            ),
            Vector2D((room.top_left.x + room.bottom_right.x) / 2, room.top_left.y + 40),
            Vector2D(
                (room.top_left.x + room.bottom_right.x) / 2, room.bottom_right.y - 40
            ),
        ]

        for midpoint in midpoints:
            if room.is_inside_room(midpoint):
                positions.append(self.evaluate_position(game_state, midpoint))

        # 排序并返回最佳位置
        positions.sort(key=lambda p: p.total_score, reverse=True)
        return positions[:count]


# ==================== 资源状态分析 ====================


class ResourceAnalyzer:
    """
    资源状态分析

    功能：
    - 生命值风险评估
    - 弹药/充能状态
    - 特殊能力冷却判断
    """

    def __init__(self):
        # 配置
        self.low_hp_threshold = 0.3  # 低血量阈值
        self.critical_hp_threshold = 0.15  # 危险血量阈值
        self.healing_priority_hp = 0.5  # 考虑治疗的血量阈值

    def analyze_resources(self, game_state: GameState) -> ResourceStatus:
        """
        分析资源状态

        Args:
            game_state: 当前游戏状态

        Returns:
            资源状态
        """
        player = game_state.player

        if not player:
            return ResourceStatus()

        # 计算血量百分比
        hp_percentage = player.hp / player.max_hp if player.max_hp > 0 else 0

        # 检查是否有治疗道具
        has_healing = player.passive_items and any(
            item in [33, 44, 52, 68, 118, 290] for item in player.passive_items
        )

        # 主动道具
        active_items = {}
        for slot, item_data in player.active_items.items():
            active_items[slot] = {
                "item_id": item_data.get("item"),
                "charge": item_data.get("charge", 0),
                "max_charge": item_data.get("max_charge", 0),
                "is_full": item_data.get("charge", 0) >= item_data.get("max_charge", 1),
            }

        return ResourceStatus(
            current_hp=player.hp,
            max_hp=player.max_hp,
            hp_percentage=hp_percentage,
            hp_trend="stable",  # 需要历史数据
            coins=player.coins,
            bombs=player.bombs,
            keys=player.keys,
            active_items=active_items,
            has_healing_item=has_healing,
            has_damage_item=False,  # 可以扩展检测
            is_invincible=player.is_invincible,
            invincible_timer=player.invincible_timer,
            can_shoot=player.tear_rate > 0,
            low_hp_warning=hp_percentage < self.low_hp_threshold,
            critical_hp_warning=hp_percentage < self.critical_hp_threshold,
            no_bombs_warning=player.bombs == 0,
        )

    def should_heal(self, resources: ResourceStatus) -> Tuple[bool, str]:
        """
        判断是否应该治疗

        Returns:
            (是否应该治疗, 原因)
        """
        if resources.critical_hp_warning:
            return True, "血量危险"

        if resources.low_hp_warning and resources.has_healing_item:
            return True, "低血量且有治疗道具"

        if resources.hp_percentage < 0.25 and resources.has_healing_item:
            return True, "血量低于25%且有治疗道具"

        return False, ""

    def should_use_active_item(
        self, resources: ResourceStatus
    ) -> List[Tuple[int, str]]:
        """
        判断应该使用哪些主动道具

        Returns:
            [(槽位, 原因), ...]
        """
        recommendations = []

        for slot, item in resources.active_items.items():
            if not item["is_full"]:
                continue

            item_id = item["item_id"]

            # 根据ID判断
            healing_items = [33, 44, 52, 68, 118, 290]  # 治疗相关道具
            damage_items = [118, 145, 200, 229, 230]  # 伤害相关道具

            if resources.critical_hp_warning and item_id in healing_items:
                recommendations.append((slot, "紧急治疗"))
            elif resources.has_damage_item and len(resources.active_items) > 1:
                recommendations.append((slot, "准备使用其他道具"))
            elif item_id == 245:  # Dead Cat - 9条命
                recommendations.append((slot, "可以使用复活道具"))

        return recommendations


# ==================== 分析模块主类 ====================


class AnalysisModule:
    """
    分析模块主类

    整合威胁评估器、机会评估器、位置评估器和资源分析器，
    对当前游戏局势进行全面评估。

    输入: 归一化游戏状态 (GameState)
    输出: 局势评估结果 (SituationAssessment)
    """

    def __init__(self):
        self.threat_assessor = ThreatAssessor()
        self.opportunity_evaluator = OpportunityEvaluator()
        self.position_evaluator = PositionEvaluator()
        self.resource_analyzer = ResourceAnalyzer()

        # 统计
        self.stats = {"total_assessments": 0, "avg_processing_time_ms": 0.0}

    def analyze(self, game_state: GameState) -> SituationAssessment:
        """
        分析当前局势

        Args:
            game_state: 当前游戏状态

        Returns:
            局势评估结果
        """
        start_time = time.time()

        assessment = SituationAssessment()

        # 1. 评估威胁
        assessment.threats, assessment.immediate_threats = (
            self.threat_assessor.assess_threats(game_state)
        )

        # 2. 评估机会
        assessment.opportunities = self.opportunity_evaluator.evaluate_opportunities(
            game_state
        )

        # 3. 评估当前位置
        if game_state.player and game_state.player.position:
            assessment.current_position_score = (
                self.position_evaluator.evaluate_position(
                    game_state, game_state.player.position.pos
                )
            )

            # 寻找最佳位置
            assessment.recommended_positions = (
                self.position_evaluator.find_best_positions(game_state)
            )

        # 4. 分析资源
        assessment.resources = self.resource_analyzer.analyze_resources(game_state)

        # 5. 综合评估
        self._compute_overall_assessment(assessment, game_state)

        # 6. 生成行动建议
        self._generate_action_recommendation(assessment)

        # 更新统计
        self.stats["total_assessments"] += 1
        processing_time = (time.time() - start_time) * 1000
        self.stats["avg_processing_time_ms"] = (
            self.stats["avg_processing_time_ms"] * 0.9 + processing_time * 0.1
        )

        return assessment

    def _compute_overall_assessment(
        self, assessment: SituationAssessment, game_state: GameState
    ):
        """计算整体评估"""
        # 判断是否在战斗
        assessment.is_combat = (
            len(game_state.get_active_enemies()) > 0
            or len(game_state.get_enemy_projectiles()) > 0
        )

        # 判断是否是Boss战
        assessment.is_boss_fight = (
            game_state.room.has_boss if game_state.room else False
        )

        # 计算房间清除进度
        if game_state.room:
            total_enemies = game_state.room.enemy_count + len(
                game_state.get_active_enemies()
            )
            if total_enemies > 0:
                assessment.room_clear_progress = 1.0 - (
                    len(game_state.get_active_enemies()) / total_enemies
                )

        # 确定整体威胁等级
        if assessment.immediate_threats:
            assessment.overall_threat_level = ThreatLevel.CRITICAL
        elif any(t.threat_level == ThreatLevel.HIGH for t in assessment.threats):
            assessment.overall_threat_level = ThreatLevel.HIGH
        elif any(t.threat_level == ThreatLevel.MEDIUM for t in assessment.threats):
            assessment.overall_threat_level = ThreatLevel.MEDIUM
        else:
            assessment.overall_threat_level = ThreatLevel.LOW

        # 更新统计信息
        assessment.enemy_count = len(game_state.get_active_enemies())
        assessment.active_projectile_count = len(game_state.get_enemy_projectiles())

        if game_state.player and game_state.player.position:
            nearest = game_state.get_nearest_enemy(game_state.player.position.pos)
            if nearest:
                assessment.nearest_enemy_distance = nearest.distance_to_player

    def _generate_action_recommendation(self, assessment: SituationAssessment):
        """生成行动建议"""
        # 基于威胁等级确定行动
        if assessment.immediate_threats:
            # 有即时威胁，优先躲避
            if any(
                t.threat_level == ThreatLevel.CRITICAL
                for t in assessment.immediate_threats
            ):
                assessment.suggested_action = ActionPriority.EMERGENCY_DODGE
                assessment.action_details = {
                    "type": "emergency_dodge",
                    "threats": [t.to_dict() for t in assessment.immediate_threats[:3]],
                }
            else:
                assessment.suggested_action = ActionPriority.DEFENSIVE_POSITION
                assessment.action_details = {
                    "type": "defensive_position",
                    "reason": "存在需要躲避的威胁",
                }

        elif assessment.resources.critical_hp_warning:
            assessment.suggested_action = ActionPriority.HEAL
            assessment.action_details = {
                "type": "heal",
                "current_hp": assessment.resources.current_hp,
                "max_hp": assessment.resources.max_hp,
            }

        elif assessment.resources.low_hp_warning:
            assessment.suggested_action = ActionPriority.ESCAPE
            assessment.action_details = {
                "type": "escape",
                "reason": "血量较低，需要保持距离",
            }

        elif assessment.is_combat:
            # 在战斗中
            if assessment.overall_threat_level == ThreatLevel.HIGH:
                assessment.suggested_action = ActionPriority.DEFENSIVE_POSITION
            else:
                assessment.suggested_action = ActionPriority.ATTACK

                # 寻找最佳攻击目标
                if assessment.opportunities:
                    best_opportunity = assessment.opportunities[0]
                    assessment.action_details = {
                        "type": "attack",
                        "target": best_opportunity.opportunity_type,
                        "description": best_opportunity.description,
                    }

        else:
            # 不在战斗，探索模式
            if (
                assessment.current_position_score
                and assessment.current_position_score.strategic_score < 0.4
            ):
                assessment.suggested_action = ActionPriority.POSITION_ADJUST
                assessment.action_details = {
                    "type": "position_adjust",
                    "reason": "当前位置战略价值较低",
                }
            else:
                assessment.suggested_action = ActionPriority.EXPLORE
                assessment.action_details = {
                    "type": "explore",
                    "room_clear": assessment.room_clear_progress,
                }

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_assessments": self.stats["total_assessments"],
            "avg_processing_time_ms": self.stats["avg_processing_time_ms"],
        }


# ==================== 便捷函数 ====================


def create_analysis_module() -> AnalysisModule:
    """创建分析模块实例"""
    return AnalysisModule()


# 导出主要类
__all__ = [
    "AnalysisModule",
    "SituationAssessment",
    "ThreatInfo",
    "OpportunityInfo",
    "PositionScore",
    "ResourceStatus",
    "ActionPriority",
    "ThreatAssessor",
    "OpportunityEvaluator",
    "PositionEvaluator",
    "ResourceAnalyzer",
    "create_analysis_module",
]
