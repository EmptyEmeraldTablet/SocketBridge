"""
智能瞄准模块

实现智能瞄准系统：
- 移动目标预测
- 弹道计算
- 射击模式优化

根据 reference.md 第四阶段设计。
"""

import math
from typing import Tuple, Optional, List, Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger("SmartAiming")


@dataclass
class AimConfig:
    """瞄准配置"""

    lead_factor: float = 0.3  # 提前量因子
    prediction_frames: int = 10  # 预测帧数
    aim_tolerance: float = 0.1  # 瞄准容差
    max_lead_angle: float = math.pi / 4  # 最大提前角
    projectile_speed: float = 10.0  # 弹速
    use_curved_trajectory: bool = False  # 是否使用曲线弹道


class TargetPredictor:
    """目标位置预测器"""

    def __init__(self):
        self.position_history: List[Tuple[float, float, float]] = []  # (x, y, time)
        self.max_history = 30

    def add_position(self, pos: Tuple[float, float], time: float):
        """添加位置记录"""
        self.position_history.append((pos[0], pos[1], time))
        if len(self.position_history) > self.max_history:
            self.position_history.pop(0)

    def predict_position(self, frames_ahead: int = 10) -> Optional[Tuple[float, float]]:
        """预测未来位置"""
        if len(self.position_history) < 2:
            return None

        # 简单线性预测
        recent = self.position_history[-1]
        prev = self.position_history[-2]

        # 计算速度
        dt = recent[2] - prev[2]
        if dt <= 0:
            return recent[:2]

        vx = (recent[0] - prev[0]) / dt
        vy = (recent[1] - prev[1]) / dt

        # 预测
        predicted_x = recent[0] + vx * frames_ahead
        predicted_y = recent[1] + vy * frames_ahead

        return (predicted_x, predicted_y)

    def get_velocity(self) -> Tuple[float, float]:
        """获取当前速度"""
        if len(self.position_history) < 2:
            return (0, 0)

        recent = self.position_history[-1]
        prev = self.position_history[-2]

        dt = recent[2] - prev[2]
        if dt <= 0:
            return (0, 0)

        return ((recent[0] - prev[0]) / dt, (recent[1] - prev[1]) / dt)

    def reset(self):
        """重置"""
        self.position_history.clear()


class LeadingShotCalculator:
    """提前量射击计算器"""

    def __init__(self, config: AimConfig = None):
        self.config = config or AimConfig()

    def calculate_lead(
        self,
        shooter_pos: Tuple[float, float],
        target_pos: Tuple[float, float],
        target_vel: Tuple[float, float],
        projectile_speed: float = None,
    ) -> Tuple[float, float]:
        """
        计算提前量射击

        Args:
            shooter_pos: 射击者位置
            target_pos: 目标位置
            target_vel: 目标速度
            projectile_speed: 弹速

        Returns:
            瞄准方向（归一化）
        """
        speed = projectile_speed or self.config.projectile_speed

        # 到目标的向量
        to_target_x = target_pos[0] - shooter_pos[0]
        to_target_y = target_pos[1] - shooter_pos[1]
        distance = math.sqrt(to_target_x**2 + to_target_y**2)

        if distance < 1:
            return (0, 0)

        # 简单预测位置
        predicted_x = target_pos[0] + target_vel[0] * self.config.lead_factor * 10
        predicted_y = target_pos[1] + target_vel[1] * self.config.lead_factor * 10

        # 计算射击方向
        aim_x = predicted_x - shooter_pos[0]
        aim_y = predicted_y - shooter_pos[1]

        # 归一化
        aim_mag = math.sqrt(aim_x**2 + aim_y**2)
        if aim_mag < 0.01:
            return (0, 0)

        return (aim_x / aim_mag, aim_y / aim_mag)

    def calculate_intercept(
        self,
        shooter_pos: Tuple[float, float],
        target_pos: Tuple[float, float],
        target_vel: Tuple[float, float],
        projectile_speed: float = None,
    ) -> Tuple[float, float]:
        """
        计算拦截点

        精确计算需要多长时间击中移动目标。
        """
        speed = projectile_speed or self.config.projectile_speed

        dx = target_pos[0] - shooter_pos[0]
        dy = target_pos[1] - shooter_pos[1]

        # 解二次方程: |target_pos + target_vel*t - shooter_pos|^2 = (speed*t)^2
        a = target_vel[0] ** 2 + target_vel[1] ** 2 - speed**2
        b = 2 * (dx * target_vel[0] + dy * target_vel[1])
        c = dx**2 + dy**2

        if abs(a) < 0.001:
            # 线性情况
            if abs(b) < 0.001:
                t = 0
            else:
                t = -c / b
        else:
            discriminant = b**2 - 4 * a * c
            if discriminant < 0:
                # 无解，使用简单预测
                return self.calculate_lead(shooter_pos, target_pos, target_vel, speed)

            t1 = (-b + math.sqrt(discriminant)) / (2 * a)
            t2 = (-b - math.sqrt(discriminant)) / (2 * a)

            # 选择最近的正解
            t = min([t for t in [t1, t2] if t >= 0] or [0])

        # 计算拦截点
        intercept_x = target_pos[0] + target_vel[0] * t
        intercept_y = target_pos[1] + target_vel[1] * t

        # 瞄准拦截点
        aim_x = intercept_x - shooter_pos[0]
        aim_y = intercept_y - shooter_pos[1]

        aim_mag = math.sqrt(aim_x**2 + aim_y**2)
        if aim_mag < 0.01:
            return (0, 0)

        return (aim_x / aim_mag, aim_y / aim_mag)


class AimingPatternSelector:
    """射击模式选择器"""

    def __init__(self):
        self.patterns = {
            "normal": self._normal_pattern,
            "spread": self._spread_pattern,
            "burst": self._burst_pattern,
            "precise": self._precise_pattern,
        }
        self.current_pattern = "normal"

    def select_pattern(
        self, enemy_type: int, distance: float, accuracy_history: List[bool]
    ) -> str:
        """
        选择射击模式

        Args:
            enemy_type: 敌人类型
            distance: 距离

        Returns:
            模式名称
        """
        # 基于距离选择
        if distance > 400:
            return "precise"
        elif distance < 100:
            return "spread"
        elif distance > 250:
            return "burst"

        return "normal"

    def _normal_pattern(self, target: Tuple[float, float]) -> List[Tuple[float, float]]:
        """正常模式：单发"""
        return [target]

    def _spread_pattern(self, target: Tuple[float, float]) -> List[Tuple[float, float]]:
        """散射模式：多发散射"""
        offsets = [
            (0, 0),
            (5, 5),
            (-5, 5),
            (5, -5),
            (-5, -5),
        ]
        return [(target[0] + ox, target[1] + oy) for ox, oy in offsets[:3]]

    def _burst_pattern(self, target: Tuple[float, float]) -> List[Tuple[float, float]]:
        """连发模式：快速多发"""
        return [target, target, target]

    def _precise_pattern(
        self, target: Tuple[float, float]
    ) -> List[Tuple[float, float]]:
        """精确模式：瞄准弱点"""
        return [target]


class SmartAimingSystem:
    """智能瞄准系统整合"""

    def __init__(self, config: AimConfig = None):
        self.config = config or AimConfig()
        self.predictor = TargetPredictor()
        self.lead_calculator = LeadingShotCalculator(config)
        self.pattern_selector = AimingPatternSelector()

        # 命中率历史
        self.hit_history: List[bool] = []
        self.max_history = 20

    def aim(
        self,
        shooter_pos: Tuple[float, float],
        target_pos: Tuple[float, float],
        target_vel: Tuple[float, float],
        enemy_type: int = 0,
        projectile_speed: float = None,
    ) -> Tuple[float, float]:
        """
        获取瞄准方向

        Args:
            shooter_pos: 射击者位置
            target_pos: 目标位置
            target_vel: 目标速度
            enemy_type: 敌人类型
            projectile_speed: 弹速

        Returns:
            瞄准方向（归一化）
        """
        # 更新目标预测
        self.predictor.add_position(target_pos, __import__("time").time())

        # 更新命中率历史
        if self.hit_history:
            recent = self.hit_history[-5:]
            accuracy = sum(recent) / len(recent)

            # 命中率低时增加提前量
            if accuracy < 0.3:
                self.config.lead_factor = min(0.5, self.config.lead_factor + 0.05)
            elif accuracy > 0.7:
                self.config.lead_factor = max(0.2, self.config.lead_factor - 0.02)

        # 选择射击模式
        distance = math.sqrt(
            (target_pos[0] - shooter_pos[0]) ** 2
            + (target_pos[1] - shooter_pos[1]) ** 2
        )
        self.pattern_selector.select_pattern(enemy_type, distance, self.hit_history)

        # 计算提前量
        aim_dir = self.lead_calculator.calculate_lead(
            shooter_pos, target_pos, target_vel, projectile_speed
        )

        return aim_dir

    def record_hit(self, hit: bool):
        """记录命中结果"""
        self.hit_history.append(hit)
        if len(self.hit_history) > self.max_history:
            self.hit_history.pop(0)

    def get_accuracy(self) -> float:
        """获取命中率"""
        if not self.hit_history:
            return 0.5
        return sum(self.hit_history) / len(self.hit_history)

    def reset(self):
        """重置"""
        self.predictor.reset()
        self.hit_history.clear()
