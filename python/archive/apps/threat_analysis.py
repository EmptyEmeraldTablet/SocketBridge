"""
SocketBridge 威胁分析模块

实现游戏威胁的评估和分析：
- 威胁等级计算
- 攻击模式识别
- 危险区域标记
- 投射物轨迹预测
"""

import math
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from models import (
    Vector2D,
    EnemyData,
    ProjectileData,
    PlayerData,
    GameStateData,
)

logger = logging.getLogger("ThreatAnalysis")


class ThreatLevel(Enum):
    """威胁等级"""

    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class ThreatInfo:
    """威胁信息"""

    source_id: int
    source_type: str  # enemy, projectile, hazard
    position: Vector2D
    distance: float
    threat_level: ThreatLevel
    estimated_impact_time: Optional[int] = None  # 预计击中时间（帧）
    direction: Vector2D = field(default_factory=lambda: Vector2D(0, 0))
    priority: float = 0.0  # 处理优先级

    # 额外信息
    attack_pattern: Optional[str] = None
    damage_estimate: float = 0.0


@dataclass
class DangerZone:
    """危险区域"""

    center: Vector2D
    radius: float
    danger_type: str  # projectile, aoe, hazard
    intensity: float  # 0-1
    estimated_duration: int  # 预计持续帧数


@dataclass
class ThreatAssessment:
    """威胁评估结果"""

    immediate_threats: List[ThreatInfo] = field(default_factory=list)
    potential_threats: List[ThreatInfo] = field(default_factory=list)
    danger_zones: List[DangerZone] = field(default_factory=list)
    overall_threat_level: ThreatLevel = ThreatLevel.LOW

    # 统计数据
    threat_count: int = 0
    closest_threat_distance: float = 9999.0
    avg_threat_distance: float = 0.0

    # 闪避建议
    suggested_evasion_dir: Vector2D = field(default_factory=lambda: Vector2D(0, 0))
    is_under_attack: bool = False


class ThreatAnalyzer:
    """威胁分析器

    分析游戏中的各种威胁来源。
    """

    def __init__(self):
        # 威胁距离阈值
        self.immediate_threat_distance = 200.0  # 立即威胁距离
        self.potential_threat_distance = 400.0  # 潜在威胁距离

        # 威胁权重
        self.boss_multiplier = 2.0
        self.champion_multiplier = 1.5
        self.projectile_priority = 1.2

        # 攻击预判参数
        self.prediction_frames = 30

    def analyze(
        self,
        game_state: GameStateData,
        current_frame: int = 0,
    ) -> ThreatAssessment:
        """分析当前游戏状态的威胁

        Args:
            game_state: 当前游戏状态
            current_frame: 当前帧号

        Returns:
            威胁评估结果
        """
        player = game_state.get_primary_player()
        if player is None:
            return ThreatAssessment()

        player_pos = player.position
        assessment = ThreatAssessment()

        total_distance = 0.0
        threat_count = 0

        # 评估敌人威胁
        for enemy_id, enemy in game_state.enemies.items():
            if enemy.state.value == "dead":
                continue

            threat = self._assess_enemy_threat(player_pos, enemy)

            if (
                threat.threat_level == ThreatLevel.CRITICAL
                or threat.threat_level == ThreatLevel.HIGH
            ):
                assessment.immediate_threats.append(threat)
            else:
                assessment.potential_threats.append(threat)

            # 统计
            total_distance += threat.distance
            threat_count += 1

        # 评估投射物威胁
        for proj_id, proj in game_state.projectiles.items():
            if not proj.is_enemy:
                continue

            threat = self._assess_projectile_threat(player_pos, proj)

            if threat.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH]:
                assessment.immediate_threats.append(threat)
            elif threat.threat_level == ThreatLevel.MEDIUM:
                assessment.potential_threats.append(threat)

            # 统计
            total_distance += threat.distance
            threat_count += 1

        # 计算统计数据
        assessment.threat_count = threat_count
        if threat_count > 0:
            assessment.avg_threat_distance = total_distance / threat_count

        # 找到最近的威胁
        all_threats = assessment.immediate_threats + assessment.potential_threats
        if all_threats:
            assessment.closest_threat_distance = min(t.distance for t in all_threats)

        # 计算总体威胁等级
        assessment.overall_threat_level = self._calculate_overall_threat(assessment)

        # 计算闪避方向
        assessment.suggested_evasion_dir = self._calculate_evasion_direction(
            player_pos, assessment
        )

        # 检查是否正在被攻击
        assessment.is_under_attack = len(assessment.immediate_threats) > 0

        return assessment

    def _assess_enemy_threat(
        self, player_pos: Vector2D, enemy: EnemyData
    ) -> ThreatInfo:
        """评估单个敌人的威胁"""
        distance = player_pos.distance_to(enemy.position)

        # 基础威胁等级
        base_level = ThreatLevel.LOW

        if distance < self.immediate_threat_distance:
            base_level = ThreatLevel.CRITICAL
        elif distance < self.potential_threat_distance:
            base_level = ThreatLevel.HIGH
        else:
            base_level = ThreatLevel.MEDIUM

        # 应用权重
        multiplier = 1.0
        if enemy.is_boss:
            multiplier = self.boss_multiplier
        elif enemy.is_champion:
            multiplier = self.champion_multiplier

        # 根据距离调整
        if distance < 50:
            multiplier *= 1.5

        # 考虑敌人是否在攻击
        if enemy.is_attacking:
            multiplier *= 1.3

        # 计算优先级
        priority = distance / 100.0
        if enemy.is_boss:
            priority *= 0.5  # Boss 优先级更高

        # 预测攻击时间
        estimated_impact = None
        if distance < 100 and enemy.velocity.magnitude() > 0:
            estimated_impact = int(distance / enemy.velocity.magnitude())

        return ThreatInfo(
            source_id=enemy.id,
            source_type="enemy",
            position=enemy.position,
            distance=distance,
            threat_level=base_level,
            estimated_impact_time=estimated_impact,
            direction=enemy.velocity.normalized(),
            priority=priority,
            attack_pattern=self._identify_attack_pattern(enemy),
            damage_estimate=enemy.damage * multiplier,
        )

    def _assess_projectile_threat(
        self, player_pos: Vector2D, proj: ProjectileData
    ) -> ThreatInfo:
        """评估单个投射物的威胁"""
        distance = player_pos.distance_to(proj.position)

        # 基础威胁等级
        base_level = ThreatLevel.LOW

        # 计算预计击中时间
        estimated_impact = None
        if proj.velocity.magnitude() > 0:
            time_to_hit = distance / proj.velocity.magnitude()
            estimated_impact = int(time_to_hit)

            # 根据预计击中时间调整威胁等级
            if time_to_hit < 15:  # 15帧以内
                base_level = ThreatLevel.CRITICAL
            elif time_to_hit < 30:
                base_level = ThreatLevel.HIGH
            elif time_to_hit < 60:
                base_level = ThreatLevel.MEDIUM
        else:
            # 静止的投射物（如某些特殊攻击）
            if distance < 50:
                base_level = ThreatLevel.HIGH

        # 考虑投射物大小
        if proj.size > 10:
            base_level = ThreatLevel(
                min(base_level.value + 1, ThreatLevel.CRITICAL.value)
            )

        # 计算优先级（投射物优先级更高）
        priority = 1.0 / max(distance, 1) * 100

        return ThreatInfo(
            source_id=proj.id,
            source_type="projectile",
            position=proj.position,
            distance=distance,
            threat_level=base_level,
            estimated_impact_time=estimated_impact,
            direction=proj.velocity.normalized(),
            priority=priority,
            damage_estimate=proj.damage,
        )

    def _identify_attack_pattern(self, enemy: EnemyData) -> Optional[str]:
        """识别敌人攻击模式"""
        if enemy.enemy_type == 10:  # 蒼蠅
            return "rush"
        elif enemy.enemy_type == 18:  # 蜘蛛
            return "web"
        elif enemy.enemy_type == 100:  # Boss
            return "special"

        return None

    def _calculate_overall_threat(self, assessment: ThreatAssessment) -> ThreatLevel:
        """计算总体威胁等级"""
        # 立即威胁的数量
        immediate_count = len(assessment.immediate_threats)

        if immediate_count >= 3:
            return ThreatLevel.CRITICAL
        elif immediate_count == 2:
            return ThreatLevel.HIGH
        elif immediate_count == 1:
            if assessment.closest_threat_distance < 50:
                return ThreatLevel.CRITICAL
            return ThreatLevel.HIGH
        else:
            # 没有立即威胁，看潜在威胁
            potential_count = len(assessment.potential_threats)
            if potential_count >= 5:
                return ThreatLevel.MEDIUM
            elif potential_count >= 2:
                return ThreatLevel.LOW

        return ThreatLevel.LOW

    def _calculate_evasion_direction(
        self, player_pos: Vector2D, assessment: ThreatAssessment
    ) -> Vector2D:
        """计算推荐的闪避方向"""
        # 如果没有威胁，返回静止
        if not assessment.immediate_threats:
            return Vector2D(0, 0)

        # 收集所有威胁向量
        avoidance_vectors = []

        for threat in assessment.immediate_threats:
            # 计算远离威胁的方向
            threat_dir = threat.position - player_pos
            if threat_dir.magnitude() > 0:
                avoidance = -threat_dir.normalized()
                # 根据威胁等级调整权重
                weight = threat.threat_level.value + 1
                avoidance_vectors.append((avoidance, weight))

        if not avoidance_vectors:
            return Vector2D(0, 0)

        # 加权平均
        total_weight = sum(w for _, w in avoidance_vectors)
        result = Vector2D(0, 0)
        for vec, weight in avoidance_vectors:
            result = result + vec * weight

        if total_weight > 0:
            result = result / total_weight

        return result.normalized()

    def get_safe_direction(
        self,
        player_pos: Vector2D,
        threats: List[ThreatInfo],
        room_layout,
    ) -> Vector2D:
        """获取安全的方向（考虑房间边界）"""
        evasion = self._calculate_evasion_direction(
            player_pos, ThreatAssessment(immediate_threats=threats)
        )

        if evasion.magnitude() == 0:
            return Vector2D(0, 0)

        # 检查房间边界
        if room_layout and room_layout.room_info:
            info = room_layout.room_info
            max_x = info.pixel_width
            max_y = info.pixel_height

            # 预测移动后的位置
            test_pos = player_pos + evasion * 50

            # 如果超出边界，反向
            if test_pos.x < 20 or test_pos.x > max_x - 20:
                evasion.x = -evasion.x
            if test_pos.y < 20 or test_pos.y > max_y - 20:
                evasion.y = -evasion.y

        return evasion.normalized()


def create_threat_analyzer() -> ThreatAnalyzer:
    """创建威胁分析器实例"""
    return ThreatAnalyzer()
