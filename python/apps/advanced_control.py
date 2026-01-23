"""
SocketBridge 高级控制模块

实现高级控制算法：
- PID 控制器
- 轨迹优化
- 平滑移动
"""

import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

from models import Vector2D

logger = logging.getLogger("AdvancedControl")


@dataclass
class PIDConfig:
    """PID 控制器配置"""

    kp: float = 0.8  # 比例增益
    ki: float = 0.05  # 积分增益
    kd: float = 0.3  # 微分增益

    # 限制
    max_output: float = 1.0  # 最大输出
    max_integral: float = 1.0  # 最大积分
    dead_zone: float = 0.01  # 死区


@dataclass
class TrajectoryPoint:
    """轨迹点"""

    position: Vector2D
    velocity: Vector2D
    time: float  # 时间戳


class PIDController:
    """PID 控制器

    用于平滑的位置/速度控制。
    """

    def __init__(self, config: PIDConfig = None):
        self.config = config or PIDConfig()

        # 内部状态
        self.integral = 0.0
        self.last_error = 0.0
        self.last_time = None

    def reset(self):
        """重置控制器状态"""
        self.integral = 0.0
        self.last_error = 0.0
        self.last_time = None

    def compute(self, setpoint: float, current: float, dt: float = 0.016) -> float:
        """计算 PID 输出

        Args:
            setpoint: 目标值
            current: 当前值
            dt: 时间步长

        Returns:
            控制输出
        """
        error = setpoint - current

        # 死区处理
        if abs(error) < self.config.dead_zone:
            return 0.0

        # 比例项
        p_term = self.config.kp * error

        # 积分项
        self.integral += error * dt
        # 积分限幅
        self.integral = max(
            -self.config.max_integral,
            min(self.config.max_integral, self.integral),
        )
        i_term = self.config.ki * self.integral

        # 微分项
        d_error = (error - self.last_error) / dt if dt > 0 else 0
        d_term = self.config.kd * d_error

        # 更新状态
        self.last_error = error

        # 计算输出
        output = p_term + i_term + d_term

        # 输出限幅
        output = max(-self.config.max_output, min(self.config.max_output, output))

        return output


class AdvancedMovementController:
    """高级移动控制器

    使用 PID 控制器实现平滑移动。
    """

    def __init__(
        self,
        position_pid: PIDConfig = None,
        velocity_pid: PIDConfig = None,
    ):
        self.position_controller = PIDController(position_pid)
        self.velocity_controller = PIDController(velocity_pid)

        # 当前状态
        self.current_position = Vector2D(0, 0)
        self.current_velocity = Vector2D(0, 0)
        self.target_position = Vector2D(0, 0)
        self.target_velocity = Vector2D(0, 0)

        # 时间追踪
        self.last_update_time = None

    def set_target(self, position: Vector2D, velocity: Vector2D = None):
        """设置目标

        Args:
            position: 目标位置
            velocity: 目标速度（可选）
        """
        self.target_position = position
        if velocity:
            self.target_velocity = velocity

    def update(
        self,
        current_pos: Vector2D,
        current_vel: Vector2D,
        dt: float = 0.016,
    ) -> Tuple[int, int]:
        """更新控制器，返回移动方向

        Args:
            current_pos: 当前位置
            current_vel: 当前速度
            dt: 时间步长

        Returns:
            (move_x, move_y) 方向值 (-1, 0, 1)
        """
        # 更新状态
        self.current_position = current_pos
        self.current_velocity = current_vel

        # 计算位置误差
        error = self.target_position - current_pos

        # 使用 PID 控制器计算期望速度
        if hasattr(error, "x"):
            vx = self.position_controller.compute(error.x, 0, dt)
            vy = self.position_controller.compute(error.y, 0, dt)
            desired_velocity = Vector2D(vx, vy)
        else:
            desired_velocity = Vector2D(0, 0)

        # 计算速度控制
        if desired_velocity.magnitude() > 0:
            vel_x = self.velocity_controller.compute(
                desired_velocity.x, current_vel.x, dt
            )
            vel_y = self.velocity_controller.compute(
                desired_velocity.y, current_vel.y, dt
            )

            # 转换为方向
            move_x = self._clamp_to_direction(vel_x)
            move_y = self._clamp_to_direction(vel_y)

            return (move_x, move_y)

        return (0, 0)

    def _clamp_to_direction(self, value: float) -> int:
        """将值转换为方向 (-1, 0, 1)"""
        if value > 0.1:
            return 1
        elif value < -0.1:
            return -1
        return 0

    def reset(self):
        """重置控制器"""
        self.position_controller.reset()
        self.velocity_controller.reset()


class TrajectoryOptimizer:
    """轨迹优化器

    生成平滑的运动轨迹。
    """

    def __init__(self):
        self.max_speed = 5.0  # 最大速度
        self.max_acceleration = 2.0  # 最大加速度
        self.waypoint_threshold = 10.0  # 路径点到达阈值

    def generate_trajectory(
        self,
        start: Vector2D,
        waypoints: List[Vector2D],
        speed: float = None,
    ) -> List[TrajectoryPoint]:
        """生成轨迹

        Args:
            start: 起始位置
            waypoints: 路径点列表
            speed: 目标速度（可选）

        Returns:
            轨迹点列表
        """
        if speed:
            self.max_speed = speed

        trajectory = []
        current_pos = start
        current_vel = Vector2D(0, 0)
        current_time = 0.0

        # 添加起始点
        trajectory.append(
            TrajectoryPoint(
                position=current_pos,
                velocity=current_vel,
                time=current_time,
            )
        )

        # 处理每个路径点
        for waypoint in waypoints:
            # 计算到路径点的向量
            to_waypoint = waypoint - current_pos
            distance = to_waypoint.magnitude()

            if distance < self.waypoint_threshold:
                continue

            direction = to_waypoint.normalized()

            # 生成中间点
            num_points = max(2, int(distance / 20))

            for i in range(1, num_points + 1):
                t = i / num_points

                # 线性插值位置
                new_pos = current_pos + direction * (distance * t)

                # 速度逐渐增加然后减小（梯形速度曲线）
                progress = t if t < 0.5 else 1 - t
                new_speed = self.max_speed * progress * 2

                new_vel = direction * new_speed
                current_time += 1.0  # 每帧

                trajectory.append(
                    TrajectoryPoint(
                        position=new_pos,
                        velocity=new_vel,
                        time=current_time,
                    )
                )

            current_pos = waypoint
            current_vel = Vector2D(0, 0)

        return trajectory

    def smooth_path(
        self, path: List[Vector2D], smoothness: float = 0.5
    ) -> List[Vector2D]:
        """平滑路径

        Args:
            path: 原始路径点列表
            smoothness: 平滑度 (0-1)

        Returns:
            平滑后的路径点列表
        """
        if len(path) < 3:
            return path

        smoothed = [path[0]]

        for i in range(1, len(path) - 1):
            # 计算平滑点
            prev = path[i - 1]
            curr = path[i]
            next_p = path[i + 1]

            # 使用 Catmull-Rom 样条插值
            smooth_x = (
                smoothness * prev.x
                + (1 - 2 * smoothness) * curr.x
                + smoothness * next_p.x
            ) / (1 - smoothness)
            smooth_y = (
                smoothness * prev.y
                + (1 - 2 * smoothness) * curr.y
                + smoothness * next_p.y
            ) / (1 - smoothness)

            smoothed.append(Vector2D(smooth_x, smooth_y))

        smoothed.append(path[-1])

        return smoothed


def create_advanced_controller(
    position_config: PIDConfig = None,
    velocity_config: PIDConfig = None,
) -> AdvancedMovementController:
    """创建高级移动控制器"""
    return AdvancedMovementController(position_config, velocity_config)
