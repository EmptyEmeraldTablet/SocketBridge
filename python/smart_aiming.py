"""
SocketBridge 智能瞄准模块

实现目标预测和提前量计算。
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

from models import Vector2D, EnemyData, ProjectileData

logger = logging.getLogger("SmartAiming")


class ShotType(Enum):
    """射击类型"""

    NORMAL = "normal"  # 普通射击
    SPREAD = "spread"  # 散射
    BURST = "burst"  # 突发
    PRECISE = "precise"  # 精确


@dataclass
class AimResult:
    """瞄准结果"""

    direction: Vector2D  # 射击方向
    confidence: float = 1.0  # 置信度 (0-1)
    predicted_hit_pos: Optional[Vector2D] = None  # 预测命中位置
    lead_amount: Vector2D = field(default_factory=lambda: Vector2D(0, 0))  # 提前量
    shot_type: ShotType = ShotType.NORMAL
    reasoning: str = ""  # 决策原因


class SmartAimingSystem:
    """智能瞄准系统

    实现目标预测、提前量计算和自适应射击。
    """

    def __init__(self):
        # 瞄准参数
        self.prediction_frames = 15  # 预测帧数
        self.lead_factor = 0.5  # 提前量系数
        self.hit_history: List[bool] = []  # 命中历史
        self.max_history = 100  # 最大历史记录数

        # 准确率统计
        self.hit_count = 0
        self.total_shots = 0

        # 射击模式参数
        self.spread_count = 3  # 散射数量
        self.spread_angle = 15  # 散射角度（度）
        self.burst_count = 3  # 突发数量
        self.burst_interval = 5  # 突发间隔（帧）

        # DEBUG: 用于检查视线
        self.last_los_check = None
        self.last_los_result = None
        self.last_aim_direction = None
        self.last_target_pos = None

    def aim(
        self,
        shooter_pos: Vector2D,
        target: EnemyData,
        target_vel: Optional[Vector2D] = None,
        shot_type: ShotType = ShotType.NORMAL,
        check_los: bool = False,
        environment_los_checker=None,
    ) -> AimResult:
        """计算瞄准方向

        Args:
            shooter_pos: 射击者位置
            target: 目标敌人
            target_vel: 目标速度（可选，如果未提供则使用目标的当前速度）
            shot_type: 射击类型
            check_los: 是否检查视线（DEBUG）
            environment_los_checker: 环境模型用于检查视线（DEBUG）

        Returns:
            瞄准结果
        """
        # DEBUG: 记录瞄准信息
        self.last_target_pos = target.position

        # 获取目标速度
        if target_vel is None:
            target_vel = target.velocity

        # 计算到目标的向量
        to_target = target.position - shooter_pos
        distance = to_target.magnitude()

        if distance < 1:
            self.last_aim_direction = Vector2D(0, 0)
            self.last_los_result = "target_too_close"
            return AimResult(
                direction=Vector2D(0, 0),
                confidence=0.0,
                reasoning="target_too_close",
            )

        # DEBUG: 检查视线（如果提供了环境检查器）
        if check_los and environment_los_checker is not None:
            has_los = environment_los_checker.spatial_query.find_line_of_sight(
                shooter_pos, target.position
            )
            self.last_los_check = (shooter_pos, target.position)
            self.last_los_result = "BLOCKED" if not has_los else "CLEAR"

            if not has_los:
                # 视线被遮挡，降低置信度
                self.last_aim_direction = to_target.normalized()
                return AimResult(
                    direction=to_target.normalized(),
                    confidence=0.1,  # 低置信度表示无法击中
                    reasoning=f"los_blocked_target_{target.id}",
                )

        # 计算提前量
        lead = self._calculate_lead(shooter_pos, target, target_vel, distance)

        # 预测命中位置
        predicted_hit = target.position + lead

        # 计算瞄准方向
        aim_direction = (predicted_hit - shooter_pos).normalized()

        # 计算置信度
        confidence = self._calculate_confidence(distance, target_vel.magnitude())

        # 根据射击类型调整
        if shot_type == ShotType.SPREAD:
            return self._compute_spread_aim(
                shooter_pos, target, aim_direction, confidence
            )
        elif shot_type == ShotType.BURST:
            return self._compute_burst_aim(shooter_pos, aim_direction, confidence)

        return AimResult(
            direction=aim_direction,
            confidence=confidence,
            predicted_hit_pos=predicted_hit,
            lead_amount=lead,
            shot_type=shot_type,
            reasoning=f"aiming_at_enemy_{target.id}",
        )

    def _calculate_lead(
        self,
        shooter_pos: Vector2D,
        target: EnemyData,
        target_vel: Vector2D,
        distance: float,
    ) -> Vector2D:
        """计算提前量

        Args:
            shooter_pos: 射击者位置
            target: 目标
            target_vel: 目标速度
            distance: 到目标的距离

        Returns:
            提前量向量
        """
        # 假设投射物速度固定（需要根据实际武器调整）
        projectile_speed = 10.0  # 投射物速度

        # 计算碰撞时间
        time_to_collision = distance / projectile_speed

        # 限制预测时间
        time_to_collision = min(time_to_collision, self.prediction_frames)

        # 计算提前量
        lead = target_vel * time_to_collision * self.lead_factor

        return lead

    def _calculate_confidence(self, distance: float, target_speed: float) -> float:
        """计算瞄准置信度

        Args:
            distance: 距离
            target_speed: 目标速度

        Returns:
            置信度 (0-1)
        """
        # 基础置信度
        confidence = 1.0

        # 距离惩罚
        if distance > 300:
            confidence -= 0.2
        elif distance > 500:
            confidence -= 0.4

        # 速度惩罚
        if target_speed > 3:
            confidence -= 0.2
        elif target_speed > 5:
            confidence -= 0.4

        # 基于历史准确率调整
        if self.total_shots > 10:
            accuracy = self.hit_count / self.total_shots
            confidence = (confidence + accuracy) / 2

        return max(0.1, confidence)

    def _compute_spread_aim(
        self,
        shooter_pos: Vector2D,
        target: EnemyData,
        base_direction: Vector2D,
        confidence: float,
    ) -> AimResult:
        """计算散射瞄准"""
        directions = []

        # 计算角度
        angle = math.atan2(base_direction.y, base_direction.x)

        # 生成散射方向
        for i in range(self.spread_count):
            spread = (i - (self.spread_count - 1) / 2) * math.radians(self.spread_angle)
            new_angle = angle + spread
            directions.append(Vector2D(math.cos(new_angle), math.sin(new_angle)))

        # 返回第一个方向作为主方向
        return AimResult(
            direction=directions[0],
            confidence=confidence * 0.9,  # 散射降低置信度
            shot_type=ShotType.SPREAD,
            reasoning=f"spread_aim_{self.spread_count}_shots",
        )

    def _compute_burst_aim(
        self,
        shooter_pos: Vector2D,
        base_direction: Vector2D,
        confidence: float,
    ) -> AimResult:
        """计算突发瞄准"""
        return AimResult(
            direction=base_direction,
            confidence=confidence * 0.8,  # 突发降低置信度
            shot_type=ShotType.BURST,
            reasoning=f"burst_aim_{self.burst_count}_shots",
        )

    def record_hit(self, hit: bool):
        """记录射击结果

        Args:
            hit: 是否命中
        """
        self.hit_history.append(hit)

        # 限制历史长度
        if len(self.hit_history) > self.max_history:
            self.hit_history.pop(0)

        # 更新统计
        if hit:
            self.hit_count += 1
        self.total_shots += 1

    def get_accuracy(self) -> float:
        """获取命中率

        Returns:
            命中率 (0-1)
        """
        if self.total_shots == 0:
            return 0.5  # 默认50%
        return self.hit_count / self.total_shots

    def adjust_aim_parameters(self):
        """根据命中率调整瞄准参数"""
        if self.total_shots < 10:
            return

        accuracy = self.get_accuracy()

        # 根据准确率调整提前量
        if accuracy < 0.3:
            # 准确率太低，减少提前量
            self.lead_factor = max(0.1, self.lead_factor - 0.1)
        elif accuracy > 0.7:
            # 准确率很高，增加提前量
            self.lead_factor = min(1.0, self.lead_factor + 0.05)

    def reset_stats(self):
        """重置统计信息"""
        self.hit_history.clear()
        self.hit_count = 0
        self.total_shots = 0


def create_smart_aiming_system() -> SmartAimingSystem:
    """创建智能瞄准系统实例"""
    return SmartAimingSystem()
