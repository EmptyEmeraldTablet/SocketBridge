"""
SocketBridge 危险系统 (DangerSystem)

处理高频威胁数据的专业模块，负责：
- 投射物轨迹预测
- 实时危险区域计算
- 即时威胁评估
- 躲避建议生成

与 EnvironmentModel 配合使用：
- EnvironmentModel: 处理静态环境（墙壁、房间布局、静态障碍物）
- DangerSystem: 处理动态威胁（投射物、敌人攻击、临时危险区域）
"""

import math
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from models import Vector2D, EnemyData, ProjectileData, PlayerData
from threat_analysis import ThreatLevel, ThreatInfo, ThreatAssessment

logger = logging.getLogger("DangerSystem")


@dataclass
class TrajectoryPrediction:
    """投射物轨迹预测"""

    projectile_id: int
    current_position: Vector2D
    velocity: Vector2D
    predicted_positions: List[Vector2D]  # 未来位置列表
    collision_frame: Optional[int] = None  # 预计碰撞帧
    safe_distance: float = 100.0  # 安全距离


@dataclass
class ImmediateDanger:
    """即时危险"""

    danger_id: int
    danger_type: str  # projectile, enemy_attack, hazard
    position: Vector2D
    radius: float
    intensity: float  # 0-1 危险强度
    estimated_impact_frames: int  # 预计击中帧数
    evasion_priority: float  # 躲避优先级


@dataclass
class EvasionSuggestion:
    """躲避建议"""

    direction: Vector2D  # 推荐移动方向
    urgency: float  # 紧急程度 0-1
    reason: str  # 原因
    confidence: float  # 置信度


class DangerSystem:
    """危险系统

    专门处理高频威胁数据，提供实时危险评估和躲避建议。
    """

    def __init__(self):
        # 投射物追踪
        self.projectile_trajectories: Dict[int, TrajectoryPrediction] = {}
        self.last_projectile_positions: Dict[int, Vector2D] = {}

        # 即时危险
        self.immediate_dangers: Dict[int, ImmediateDanger] = {}

        # 危险区域
        self.danger_zones: List[Tuple[Vector2D, float]] = []  # (中心, 半径)

        # 基础配置（默认值）
        self.base_prediction_frames = 30  # 预测帧数
        self.base_safe_distance = 50.0  # 安全距离
        self.base_high_threshold = 0.7  # 高威胁阈值

        # 动态调整后的配置
        self.prediction_frames = self.base_prediction_frames
        self.safe_distance = self.base_safe_distance
        self.high_threshold = self.base_high_threshold

        # 帧追踪
        self.current_frame = 0
        self.last_update_frame = 0

    def update_config(self, config_updates: Dict[str, float]):
        """更新危险系统配置

        Args:
            config_updates: 配置更新字典，支持以下键：
                - safe_distance_multiplier: 安全距离乘数（默认1.0）
                - high_threshold_adjustment: 高威胁阈值调整（默认0.0）
                - prediction_frames_adjustment: 预测帧数调整（默认0）
                也可以直接设置 safe_distance, high_threshold, prediction_frames
        """
        # 应用乘数调整
        safe_distance_multiplier = config_updates.get("safe_distance_multiplier", 1.0)
        high_threshold_adjustment = config_updates.get("high_threshold_adjustment", 0.0)
        prediction_frames_adjustment = config_updates.get(
            "prediction_frames_adjustment", 0
        )

        # 计算调整后的值
        self.safe_distance = self.base_safe_distance * safe_distance_multiplier
        self.high_threshold = self.base_high_threshold + high_threshold_adjustment
        self.prediction_frames = int(
            self.base_prediction_frames + prediction_frames_adjustment
        )

        # 确保调整后的值在合理范围内
        self.safe_distance = max(20.0, min(100.0, self.safe_distance))
        self.high_threshold = max(0.3, min(1.0, self.high_threshold))
        self.prediction_frames = max(10, min(60, self.prediction_frames))

        # 如果提供了直接值，覆盖调整后的值（优先级更高）
        if "safe_distance" in config_updates:
            self.safe_distance = max(20.0, min(100.0, config_updates["safe_distance"]))
        if "high_threshold" in config_updates:
            self.high_threshold = max(0.3, min(1.0, config_updates["high_threshold"]))
        if "prediction_frames" in config_updates:
            raw = config_updates["prediction_frames"]
            self.prediction_frames = max(10, min(60, int(raw)))

        # 记录配置变更（用于调试）
        logger.debug(
            f"[DangerSystem] Config updated: safe_distance={self.safe_distance:.1f}, "
            f"high_threshold={self.high_threshold:.2f}, prediction_frames={self.prediction_frames}"
        )

    def update(
        self,
        frame: int,
        player_position: Vector2D,
        enemies: Dict[int, EnemyData],
        projectiles: Dict[int, ProjectileData],
        room_bounds: Optional[Tuple[float, float, float, float]] = None,
    ) -> ThreatAssessment:
        """更新危险系统

        Args:
            frame: 当前帧号
            player_position: 玩家位置
            enemies: 敌人数据
            projectiles: 投射物数据
            room_bounds: 房间边界 (min_x, min_y, max_x, max_y)

        Returns:
            威胁评估结果
        """
        self.current_frame = frame

        # 清空危险区域
        self.danger_zones.clear()

        # 更新投射物轨迹预测
        self._update_projectile_trajectories(projectiles, player_position, room_bounds)

        # 评估即时危险
        immediate_threats = self._assess_immediate_dangers(
            player_position, enemies, projectiles
        )

        # 构建威胁评估
        assessment = ThreatAssessment()
        assessment.immediate_threats = immediate_threats

        # 计算总体威胁等级
        assessment.overall_threat_level = self._calculate_overall_threat(assessment)
        assessment.is_under_attack = len(immediate_threats) > 0

        # 生成躲避建议
        if immediate_threats:
            assessment.suggested_evasion_dir = self._calculate_evasion_direction(
                player_position, immediate_threats, room_bounds
            )

        self.last_update_frame = frame
        return assessment

    def _update_projectile_trajectories(
        self,
        projectiles: Dict[int, ProjectileData],
        player_position: Vector2D,
        room_bounds: Optional[Tuple[float, float, float, float]],
    ):
        """更新投射物轨迹预测"""
        current_proj_ids = set()

        for proj_id, proj in projectiles.items():
            if not proj.is_enemy:
                continue

            current_proj_ids.add(proj_id)

            # 创建或更新轨迹预测
            if proj_id in self.projectile_trajectories:
                prediction = self.projectile_trajectories[proj_id]
                prediction.current_position = proj.position
                prediction.velocity = proj.velocity
            else:
                prediction = TrajectoryPrediction(
                    projectile_id=proj_id,
                    current_position=proj.position,
                    velocity=proj.velocity,
                    predicted_positions=[],
                )
                self.projectile_trajectories[proj_id] = prediction

            # 预测未来位置
            prediction.predicted_positions = self._predict_trajectory(
                proj.position, proj.velocity, proj.size, room_bounds
            )

            # 检查与玩家的碰撞
            prediction.collision_frame = self._check_player_collision(
                prediction, player_position
            )

        # 移除已消失的投射物
        to_remove = []
        for proj_id in self.projectile_trajectories:
            if proj_id not in current_proj_ids:
                to_remove.append(proj_id)
        for proj_id in to_remove:
            del self.projectile_trajectories[proj_id]

    def _predict_trajectory(
        self,
        start_pos: Vector2D,
        velocity: Vector2D,
        radius: float,
        room_bounds: Optional[Tuple[float, float, float, float]],
    ) -> List[Vector2D]:
        """预测投射物轨迹"""
        predictions = []

        if velocity.magnitude() == 0:
            return predictions

        # 简单线性预测
        for i in range(1, int(self.prediction_frames) + 1):
            pos = start_pos + velocity * i

            # 检查房间边界
            if room_bounds:
                min_x, min_y, max_x, max_y = room_bounds
                if pos.x < min_x + radius or pos.x > max_x - radius:
                    break
                if pos.y < min_y + radius or pos.y > max_y - radius:
                    break

            predictions.append(pos)

        return predictions

    def _check_player_collision(
        self, prediction: TrajectoryPrediction, player_position: Vector2D
    ) -> Optional[int]:
        """检查投射物与玩家的碰撞"""
        player_radius = 15.0  # 玩家碰撞半径

        for i, pos in enumerate(prediction.predicted_positions):
            distance = pos.distance_to(player_position)
            if distance < (player_radius + prediction.safe_distance):
                return i + 1  # 返回碰撞帧

        return None

    def _assess_immediate_dangers(
        self,
        player_position: Vector2D,
        enemies: Dict[int, EnemyData],
        projectiles: Dict[int, ProjectileData],
    ) -> List[ThreatInfo]:
        """评估即时危险"""
        threats = []

        # 评估投射物威胁
        for proj_id, proj in projectiles.items():
            if not proj.is_enemy:
                continue

            distance = player_position.distance_to(proj.position)

            # 计算威胁等级
            threat_level = ThreatLevel.LOW
            if distance < 50:
                threat_level = ThreatLevel.CRITICAL
            elif distance < 100:
                threat_level = ThreatLevel.HIGH
            elif distance < 200:
                threat_level = ThreatLevel.MEDIUM

            # 如果有轨迹预测，调整威胁等级
            if proj_id in self.projectile_trajectories:
                prediction = self.projectile_trajectories[proj_id]
                if prediction.collision_frame is not None:
                    if prediction.collision_frame < 15:
                        threat_level = ThreatLevel.CRITICAL
                    elif prediction.collision_frame < 30:
                        threat_level = ThreatLevel.HIGH

            threat = ThreatInfo(
                source_id=proj_id,
                source_type="projectile",
                position=proj.position,
                distance=distance,
                threat_level=threat_level,
                estimated_impact_time=self.projectile_trajectories.get(
                    proj_id, TrajectoryPrediction(0, Vector2D(0, 0), Vector2D(0, 0), [])
                ).collision_frame,
                direction=proj.velocity.normalized(),
                priority=1.0 / max(distance, 1) * 100,
                damage_estimate=proj.damage,
            )
            threats.append(threat)

        # 评估近身敌人威胁
        for enemy_id, enemy in enemies.items():
            if enemy.hp <= 0:
                continue

            distance = player_position.distance_to(enemy.position)
            if distance < 100:  # 近身威胁
                threat_level = ThreatLevel.HIGH if distance < 50 else ThreatLevel.MEDIUM

                threat = ThreatInfo(
                    source_id=enemy_id,
                    source_type="enemy",
                    position=enemy.position,
                    distance=distance,
                    threat_level=threat_level,
                    direction=enemy.velocity.normalized(),
                    priority=50.0 / max(distance, 1),
                    damage_estimate=enemy.damage,
                )
                threats.append(threat)

        return threats

    def _calculate_overall_threat(self, assessment: ThreatAssessment) -> ThreatLevel:
        """计算总体威胁等级"""
        if not assessment.immediate_threats:
            return ThreatLevel.LOW

        critical_count = sum(
            1
            for t in assessment.immediate_threats
            if t.threat_level == ThreatLevel.CRITICAL
        )
        high_count = sum(
            1
            for t in assessment.immediate_threats
            if t.threat_level == ThreatLevel.HIGH
        )

        if critical_count >= 1:
            return ThreatLevel.CRITICAL
        elif high_count >= 2:
            return ThreatLevel.HIGH
        elif high_count >= 1:
            return ThreatLevel.MEDIUM

        return ThreatLevel.LOW

    def _calculate_evasion_direction(
        self,
        player_position: Vector2D,
        threats: List[ThreatInfo],
        room_bounds: Optional[Tuple[float, float, float, float]],
    ) -> Vector2D:
        """计算躲避方向"""
        if not threats:
            return Vector2D(0, 0)

        avoidance = Vector2D(0, 0)
        total_weight = 0.0

        for threat in threats:
            # 计算远离威胁的方向
            threat_dir = threat.position - player_position
            if threat_dir.magnitude() > 0:
                evasion_dir = -threat_dir.normalized()

                # 根据威胁等级加权
                weight = threat.threat_level.value + 1

                # 根据距离调整权重（越近权重越高）
                distance_factor = 100.0 / max(threat.distance, 1)
                weight *= distance_factor

                avoidance += evasion_dir * weight
                total_weight += weight

        if total_weight > 0:
            avoidance = avoidance / total_weight

        # 归一化
        if avoidance.magnitude() > 0:
            avoidance = avoidance.normalized()

        # 考虑房间边界
        if room_bounds and avoidance.magnitude() > 0:
            avoidance = self._adjust_for_bounds(player_position, avoidance, room_bounds)

        return avoidance

    def _adjust_for_bounds(
        self,
        position: Vector2D,
        direction: Vector2D,
        room_bounds: Tuple[float, float, float, float],
    ) -> Vector2D:
        """根据房间边界调整方向"""
        min_x, min_y, max_x, max_y = room_bounds
        margin = 30.0

        # 测试移动后的位置
        test_pos = position + direction * 50.0

        new_direction = Vector2D(direction.x, direction.y)

        # 如果接近边界，调整方向
        if test_pos.x < min_x + margin:
            new_direction.x = max(0, new_direction.x)
        elif test_pos.x > max_x - margin:
            new_direction.x = min(0, new_direction.x)

        if test_pos.y < min_y + margin:
            new_direction.y = max(0, new_direction.y)
        elif test_pos.y > max_y - margin:
            new_direction.y = min(0, new_direction.y)

        if new_direction.magnitude() > 0:
            new_direction = new_direction.normalized()

        return new_direction

    def get_danger_zones(self) -> List[Tuple[Vector2D, float]]:
        """获取当前危险区域"""
        return self.danger_zones

    def get_trajectory_predictions(self) -> Dict[int, TrajectoryPrediction]:
        """获取投射物轨迹预测"""
        return self.projectile_trajectories

    def clear(self):
        """清除所有状态"""
        self.projectile_trajectories.clear()
        self.last_projectile_positions.clear()
        self.immediate_dangers.clear()
        self.danger_zones.clear()


def create_danger_system() -> DangerSystem:
    """创建危险系统实例"""
    return DangerSystem()
