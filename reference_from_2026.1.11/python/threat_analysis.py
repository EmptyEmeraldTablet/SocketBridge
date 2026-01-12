"""
威胁分析模块

实现游戏威胁的评估和分析：
- 威胁等级计算
- 攻击模式识别
- 危险区域标记
- 投射物轨迹预测

根据 reference.md 中的威胁评估需求设计。

=== 调试信息说明 ===
本模块在威胁分析的关键位置添加了调试输出，用于追踪：
1. 威胁评估输入（敌人、投射物、玩家位置）
2. 敌人威胁计算结果
3. 投射物威胁计算结果
4. 危险区域计算
5. 总体威胁等级判定
"""

import math
import traceback
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from models import Vector2D, EnemyData, ProjectileData, PlayerData

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


class ThreatAssessor:
    """威胁评估器

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

    def assess_threats(
        self,
        player_pos: Vector2D,
        enemies: Dict[int, EnemyData],
        projectiles: Dict[int, ProjectileData],
        fire_hazards: Dict = None,
    ) -> ThreatAssessment:
        """
        评估所有威胁

        Args:
            player_pos: 玩家位置
            enemies: 敌人字典
            projectiles: 投射物字典
            fire_hazards: 火焰危险物

        Returns:
            威胁评估结果
        """
        assessment = ThreatAssessment()

        # 评估敌人威胁
        for enemy_id, enemy in enemies.items():
            if enemy.hp <= 0:
                continue

            threat = self._assess_enemy_threat(player_pos, enemy)

            if (
                threat.threat_level == ThreatLevel.CRITICAL
                or threat.threat_level == ThreatLevel.HIGH
            ):
                assessment.immediate_threats.append(threat)
            else:
                assessment.potential_threats.append(threat)

        # 评估投射物威胁
        for proj_id, proj in projectiles.items():
            if not proj.is_enemy:
                continue

            threat = self._assess_projectile_threat(player_pos, proj)

            if threat.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH]:
                assessment.immediate_threats.append(threat)
            elif threat.threat_level == ThreatLevel.MEDIUM:
                assessment.immediate_threats.append(threat)
            else:
                assessment.potential_threats.append(threat)

        # 评估火焰危险物
        if fire_hazards:
            for hazard_id, hazard in fire_hazards.items():
                if hazard.get("is_extinguished", False):
                    continue

                threat = self._assess_hazard_threat(player_pos, hazard)

                if threat.threat_level in [ThreatLevel.CRITICAL, ThreatLevel.HIGH]:
                    assessment.immediate_threats.append(threat)

        # 计算危险区域
        assessment.danger_zones = self._calculate_danger_zones(
            assessment.immediate_threats
        )

        # 计算总体威胁等级
        assessment.overall_threat_level = self._calculate_overall_threat(
            assessment.immediate_threats
        )

        # 统计信息
        assessment.threat_count = len(assessment.immediate_threats) + len(
            assessment.potential_threats
        )

        if assessment.immediate_threats:
            assessment.closest_threat_distance = min(
                t.distance for t in assessment.immediate_threats
            )
            assessment.avg_threat_distance = sum(
                t.distance for t in assessment.immediate_threats
            ) / len(assessment.immediate_threats)

        # 按优先级排序
        assessment.immediate_threats.sort(key=lambda x: x.priority, reverse=True)

        return assessment

    def _assess_enemy_threat(
        self, player_pos: Vector2D, enemy: EnemyData
    ) -> ThreatInfo:
        """评估单个敌人威胁"""
        distance = enemy.position.distance_to(player_pos)

        # 计算基础威胁
        distance_factor = max(0, 1.0 - distance / self.potential_threat_distance)
        health_factor = enemy.hp / max(1.0, enemy.max_hp)

        base_threat = distance_factor * health_factor

        # 应用倍数
        multiplier = 1.0
        if enemy.is_boss:
            multiplier *= self.boss_multiplier
        if enemy.is_champion:
            multiplier *= self.champion_multiplier

        threat_value = base_threat * multiplier

        # 确定威胁等级
        if threat_value > 0.7:
            level = ThreatLevel.CRITICAL
        elif threat_value > 0.5:
            level = ThreatLevel.HIGH
        elif threat_value > 0.3:
            level = ThreatLevel.MEDIUM
        else:
            level = ThreatLevel.LOW

        # 计算优先级
        priority = threat_value * self._get_attack_priority(enemy)

        # 估计攻击时间
        impact_time = None
        if enemy.is_about_to_attack(0):
            # 简单估计：距离/敌人速度
            if enemy.velocity.magnitude() > 0:
                impact_time = int(distance / enemy.velocity.magnitude())

        return ThreatInfo(
            source_id=enemy.id,
            source_type="enemy",
            position=enemy.position,
            distance=distance,
            threat_level=level,
            estimated_impact_time=impact_time,
            direction=player_pos - enemy.position,
            priority=priority,
            attack_pattern=self._recognize_attack_pattern(enemy),
            damage_estimate=self._estimate_enemy_damage(enemy),
        )

    def _assess_projectile_threat(
        self, player_pos: Vector2D, proj: ProjectileData
    ) -> ThreatInfo:
        """评估投射物威胁"""
        distance = proj.position.distance_to(player_pos)

        # 检查是否朝向玩家
        direction = proj.velocity.normalized()
        to_player = (player_pos - proj.position).normalized()
        dot = direction.dot(to_player)

        # 计算威胁值
        if distance < self.immediate_threat_distance and dot > 0.5:
            # 朝向玩家且距离近
            threat_value = 1.0 - distance / self.immediate_threat_distance

            # 速度加成
            speed_factor = proj.velocity.magnitude() / 10.0
            threat_value *= min(1.5, speed_factor)
        else:
            threat_value = 0.0

        # 确定威胁等级
        if threat_value > 0.8:
            level = ThreatLevel.CRITICAL
        elif threat_value > 0.5:
            level = ThreatLevel.HIGH
        elif threat_value > 0.2:
            level = ThreatLevel.MEDIUM
        else:
            level = ThreatLevel.LOW

        # 计算预计击中时间
        impact_time = None
        if dot > 0.5 and proj.velocity.magnitude() > 0:
            impact_time = int(distance / proj.velocity.magnitude())

        # 优先级
        priority = threat_value * self.projectile_priority

        return ThreatInfo(
            source_id=proj.id,
            source_type="projectile",
            position=proj.position,
            distance=distance,
            threat_level=level,
            estimated_impact_time=impact_time,
            direction=proj.velocity,
            priority=priority,
        )

    def _assess_hazard_threat(self, player_pos: Vector2D, hazard: Dict) -> ThreatInfo:
        """评估环境危险物威胁"""
        hazard_pos = Vector2D(hazard.get("x", 0), hazard.get("y", 0))
        distance = hazard_pos.distance_to(player_pos)

        threat_value = max(0, 1.0 - distance / 100.0)

        level = ThreatLevel.MEDIUM if threat_value > 0.3 else ThreatLevel.LOW

        return ThreatInfo(
            source_id=hazard.get("id", 0),
            source_type="hazard",
            position=hazard_pos,
            distance=distance,
            threat_level=level,
            direction=Vector2D(0, 0),
            priority=threat_value,
        )

    def _get_attack_priority(self, enemy: EnemyData) -> float:
        """获取敌人攻击优先级"""
        # 近战敌人优先级高
        if enemy.projectile_delay > 100:
            return 1.5
        return 1.0

    def _recognize_attack_pattern(self, enemy: EnemyData) -> str:
        """识别敌人攻击模式"""
        # 基于敌人类型和状态识别
        if enemy.state == 2:  # 攻击状态
            return "attacking"
        elif enemy.state == 3:  # 追逐状态
            return "chasing"
        elif enemy.projectile_cooldown < 10:
            return "about_to_fire"

        return "passive"

    def _estimate_enemy_damage(self, enemy: EnemyData) -> float:
        """估计敌人伤害"""
        # 基于敌人类型的简单伤害估计
        if enemy.is_boss:
            return 2.0
        elif enemy.enemy_type == 18:  # 普通敌人
            return 1.0
        return 0.5

    def _calculate_danger_zones(self, threats: List[ThreatInfo]) -> List[DangerZone]:
        """计算危险区域"""
        zones = []

        for threat in threats:
            if threat.source_type == "projectile":
                # 投射物危险区域
                zone = DangerZone(
                    center=threat.position,
                    radius=30.0,
                    danger_type="projectile",
                    intensity=0.8,
                    estimated_duration=60,
                )
                zones.append(zone)

        return zones

    def _calculate_overall_threat(self, threats: List[ThreatInfo]) -> ThreatLevel:
        """计算总体威胁等级"""
        if not threats:
            return ThreatLevel.LOW

        # 基于最近威胁和威胁数量
        max_level = ThreatLevel.LOW
        critical_count = 0

        for threat in threats:
            if threat.threat_level.value > max_level.value:
                max_level = threat.threat_level
            if threat.threat_level == ThreatLevel.CRITICAL:
                critical_count += 1

        # 多个高威胁
        high_count = sum(
            1
            for t in threats
            if t.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]
        )

        if critical_count >= 2:
            return ThreatLevel.CRITICAL
        elif critical_count >= 1:
            return ThreatLevel.HIGH
        elif high_count >= 3:
            return ThreatLevel.HIGH
        elif max_level == ThreatLevel.MEDIUM and len(threats) >= 3:
            return ThreatLevel.HIGH

        return max_level


class ProjectilePredictor:
    """投射物轨迹预测器"""

    def __init__(self):
        self.prediction_frames = 60  # 预测帧数
        self.impact_threshold = 20.0  # 击中判定距离

    def predict_trajectory(
        self, proj: ProjectileData, steps: int = None
    ) -> List[Vector2D]:
        """
        预测投射物轨迹

        Args:
            proj: 投射物
            steps: 预测步数

        Returns:
            轨迹点列表
        """
        if steps is None:
            steps = self.prediction_frames

        trajectory = [proj.position]
        current_pos = proj.position
        current_vel = proj.velocity

        for _ in range(steps):
            current_pos = current_pos + current_vel
            trajectory.append(current_pos)

            # 简单处理重力（如果有）
            if proj.falling_speed != 0:
                current_vel = Vector2D(
                    current_vel.x, current_vel.y + proj.falling_speed
                )

        return trajectory

    def will_hit_position(
        self, proj: ProjectileData, target_pos: Vector2D, tolerance: float = None
    ) -> Tuple[bool, int]:
        """
        检查投射物是否会击中目标位置

        Args:
            proj: 投射物
            target_pos: 目标位置
            tolerance: 容差

        Returns:
            (是否击中, 预计击中帧数)
        """
        if tolerance is None:
            tolerance = self.impact_threshold

        trajectory = self.predict_trajectory(proj, 60)

        for i, pos in enumerate(trajectory):
            if pos.distance_to(target_pos) < tolerance:
                return True, i

        return False, -1

    def get_intercept_point(
        self, shooter_pos: Vector2D, proj: ProjectileData, player_speed: float = 6.0
    ) -> Optional[Vector2D]:
        """
        计算拦截点

        用于计算玩家需要移动到的位置来拦截投射物。
        """
        # 简化版本：直接朝向投射物移动
        return proj.position

    def predict_enemy_attack(
        self, enemy: EnemyData, player_pos: Vector2D
    ) -> List[Vector2D]:
        """
        预测敌人攻击轨迹

        返回敌人可能发射的投射物轨迹。
        """
        # 简单预测：假设敌人向玩家方向发射
        direction = player_pos - enemy.position
        direction = direction.normalized()

        speed = 5.0  # 假设弹速

        # 生成几个投射物轨迹
        trajectories = []

        # 主方向
        trajectory = [enemy.position]
        current_pos = enemy.position

        for _ in range(30):
            current_pos = current_pos + direction * speed
            trajectory.append(current_pos)

        trajectories.append(trajectory)

        # 稍微偏左和偏右
        for angle_offset in [0.2, -0.2]:
            # 简化处理
            pass

        return trajectories


class AttackPatternAnalyzer:
    """攻击模式分析器

    分析敌人行为模式，预测攻击。
    """

    def __init__(self):
        self.patterns: Dict[int, List[int]] = {}  # 敌人ID -> 攻击帧历史

    def record_attack(self, enemy_id: int, frame: int):
        """记录攻击"""
        if enemy_id not in self.patterns:
            self.patterns[enemy_id] = []

        self.patterns[enemy_id].append(frame)

        # 保持最近10次
        if len(self.patterns[enemy_id]) > 10:
            self.patterns[enemy_id] = self.patterns[enemy_id][-10:]

    def get_attack_interval(self, enemy_id: int) -> Optional[float]:
        """获取平均攻击间隔"""
        if enemy_id not in self.patterns or len(self.patterns[enemy_id]) < 2:
            return None

        intervals = []
        frames = self.patterns[enemy_id]

        for i in range(1, len(frames)):
            intervals.append(frames[i] - frames[i - 1])

        return sum(intervals) / len(intervals)

    def is_about_to_attack(self, enemy: EnemyData, current_frame: int) -> bool:
        """判断敌人是否即将攻击"""
        interval = self.get_attack_interval(enemy.id)

        if interval is None:
            # 没有历史数据，使用预设值
            return enemy.is_about_to_attack(current_frame)

        # 检查是否接近攻击时间
        last_attack = enemy.last_attack_frame
        time_since = current_frame - last_attack

        return time_since >= interval - 10

    def get_predicted_attack_time(
        self, enemy: EnemyData, current_frame: int
    ) -> Optional[int]:
        """预测下一次攻击时间"""
        interval = self.get_attack_interval(enemy.id)

        if interval is None:
            return None

        last_attack = enemy.last_attack_frame
        time_since = current_frame - last_attack
        time_until = interval - time_since

        if time_until < 0:
            return 0

        return time_until

    def clear(self):
        """清空历史"""
        self.patterns.clear()


class ThreatAnalyzer:
    """威胁分析器（整合版）

    整合威胁评估、轨迹预测和攻击模式分析。
    """

    def __init__(self):
        self.assessor = ThreatAssessor()
        self.predictor = ProjectilePredictor()
        self.pattern_analyzer = AttackPatternAnalyzer()

    def analyze(
        self,
        player_pos: Vector2D,
        enemies: Dict[int, EnemyData],
        projectiles: Dict[int, ProjectileData],
        fire_hazards: Dict = None,
        current_frame: int = 0,
    ) -> ThreatAssessment:
        """
        完整威胁分析

        === 调试信息 ===
        输入:
            - player_pos: 玩家位置
            - enemies: 敌人字典
            - projectiles: 投射物字典
            - fire_hazards: 火焰危险物
            - current_frame: 当前帧
        处理流程:
            1. 记录攻击历史
            2. assess_threats() - 评估所有威胁
            3. 添加预测信息
        输出: ThreatAssessment - 威胁评估结果

        关键跟踪点:
            - 敌人数量和类型
            - 投射物数量和速度
            - 即时威胁数量
            - 最近威胁距离
            - 总体威胁等级
        """
        logger.debug(f"[ThreatAnalysis] === START analyze ===")
        logger.debug(
            f"[ThreatAnalysis] Player pos=({player_pos.x:.1f}, {player_pos.y:.1f}), frame={current_frame}"
        )
        logger.debug(
            f"[ThreatAnalysis] Enemies: {len(enemies)}, Projectiles: {len(projectiles)}"
        )

        # 记录攻击历史
        for enemy in enemies.values():
            if enemy.is_about_to_attack(current_frame):
                self.pattern_analyzer.record_attack(enemy.id, current_frame)

        # 评估威胁
        logger.debug(f"[ThreatAnalysis] Assessing threats...")
        assessment = self.assessor.assess_threats(
            player_pos, enemies, projectiles, fire_hazards
        )

        # 日志威胁统计
        logger.debug(f"[ThreatAnalysis] Assessment results:")
        logger.debug(
            f"[ThreatAnalysis]   Overall threat level: {assessment.overall_threat_level.name}"
        )
        logger.debug(
            f"[ThreatAnalysis]   Immediate threats: {len(assessment.immediate_threats)}"
        )
        logger.debug(
            f"[ThreatAnalysis]   Potential threats: {len(assessment.potential_threats)}"
        )
        logger.debug(f"[ThreatAnalysis]   Threat count: {assessment.threat_count}")
        logger.debug(
            f"[ThreatAnalysis]   Closest threat distance: {assessment.closest_threat_distance:.1f}"
        )
        logger.debug(
            f"[ThreatAnalysis]   Avg threat distance: {assessment.avg_threat_distance:.1f}"
        )
        logger.debug(f"[ThreatAnalysis]   Danger zones: {len(assessment.danger_zones)}")

        # 详细记录即时威胁
        if assessment.immediate_threats:
            logger.debug(f"[ThreatAnalysis] Immediate threats detail:")
            for i, threat in enumerate(assessment.immediate_threats[:5]):  # 最多记录5个
                logger.debug(
                    f"[ThreatAnalysis]   [{i}] type={threat.source_type}, id={threat.source_id}, "
                    f"level={threat.threat_level.name}, dist={threat.distance:.1f}, "
                    f"priority={threat.priority:.2f}"
                )

        # 添加预测信息
        logger.debug(f"[ThreatAnalysis] Adding prediction info...")
        for threat in assessment.immediate_threats:
            if threat.source_type == "projectile":
                proj = projectiles.get(threat.source_id)
                if proj:
                    will_hit, impact_time = self.predictor.will_hit_position(
                        proj, player_pos
                    )
                    threat.estimated_impact_time = impact_time
                    logger.debug(
                        f"[ThreatAnalysis]   Projectile {threat.source_id}: "
                        f"will_hit={will_hit}, impact_time={impact_time}"
                    )

        logger.debug(f"[ThreatAnalysis] === END analyze ===")
        return assessment

    def get_safe_positions(
        self,
        player_pos: Vector2D,
        assessment: ThreatAssessment,
        map_width: float,
        map_height: float,
    ) -> List[Vector2D]:
        """
        获取安全位置列表

        基于当前威胁寻找安全位置。
        """
        safe_positions = []

        # 在房间内采样
        sample_points = []

        # 中心区域
        center_x = map_width / 2
        center_y = map_height / 2

        # 在圆周上采样
        for angle in [i * math.pi / 4 for i in range(8)]:
            for dist in [50, 100, 150]:
                x = center_x + dist * math.cos(angle)
                y = center_y + dist * math.sin(angle)
                sample_points.append(Vector2D(x, y))

        for pos in sample_points:
            is_safe = True
            threat_level = 0.0

            for threat in assessment.immediate_threats:
                if pos.distance_to(threat.position) < 100:
                    is_safe = False
                    break

            if is_safe:
                safe_positions.append(pos)

        return safe_positions
