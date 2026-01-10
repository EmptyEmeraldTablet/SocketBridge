"""
高级控制模块

实现精细化控制算法：
- PID控制器
- 运动轨迹优化
- 精确位置控制

根据 reference.md 第四阶段设计。
"""

import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger("AdvancedControl")


@dataclass
class PIDConfig:
    """PID控制器配置"""

    kp: float = 0.5  # 比例系数
    ki: float = 0.1  # 积分系数
    kd: float = 0.2  # 微分系数

    # 限制
    integral_limit: float = 10.0
    output_limit: float = 10.0

    # 死区
    dead_zone: float = 0.1


@dataclass
class TrajectoryPoint:
    """轨迹点"""

    position: Tuple[float, float]
    velocity: Tuple[float, float]
    time: float
    acceleration: Tuple[float, float] = (0, 0)


class PIDController:
    """PID控制器

    实现精确的位置和速度控制。
    """

    def __init__(self, config: PIDConfig = None):
        self.config = config or PIDConfig()
        self.reset()

    def reset(self):
        """重置控制器状态"""
        self.prev_error = 0.0
        self.integral = 0.0
        self.last_time = None
        self.prev_output = 0.0

    def compute(self, current: float, target: float, dt: float) -> float:
        """
        计算PID输出

        Args:
            current: 当前值
            target: 目标值
            dt: 时间增量

        Returns:
            控制输出
        """
        # 计算误差
        error = target - current

        # 死区处理
        if abs(error) < self.config.dead_zone:
            return 0.0

        # 比例项
        p_term = self.config.kp * error

        # 积分项（带限制）
        self.integral += error * dt
        self.integral = max(
            -self.config.integral_limit, min(self.config.integral_limit, self.integral)
        )
        i_term = self.config.ki * self.integral

        # 微分项
        if dt > 0:
            derivative = (error - self.prev_error) / dt
        else:
            derivative = 0
        d_term = self.config.kd * derivative

        # 计算输出
        output = p_term + i_term + d_term

        # 输出限制
        output = max(-self.config.output_limit, min(self.config.output_limit, output))

        # 更新状态
        self.prev_error = error
        self.prev_output = output

        return output

    def compute_2d(
        self, current: Tuple[float, float], target: Tuple[float, float], dt: float
    ) -> Tuple[float, float]:
        """计算2D PID输出"""
        x_out = self.compute(current[0], target[0], dt)
        y_out = self.compute(current[1], target[1], dt)
        return (x_out, y_out)


class AdvancedMovementController:
    """高级运动控制器

    使用PID控制实现精确移动。
    """

    def __init__(self):
        # PID控制器（位置和速度）
        self.position_pid = PIDController(PIDConfig(kp=0.8, ki=0.05, kd=0.3))
        self.velocity_pid = PIDController(PIDConfig(kp=0.5, ki=0.1, kd=0.2))

        # 状态
        self.current_position = (0.0, 0.0)
        self.current_velocity = (0.0, 0.0)
        self.target_position = (0.0, 0.0)
        self.target_velocity = (0.0, 0.0)

        # 配置
        self.max_acceleration = 0.5
        self.max_speed = 6.0
        self.stop_tolerance = 2.0

    def set_target(
        self, position: Tuple[float, float], velocity: Tuple[float, float] = (0, 0)
    ):
        """设置目标"""
        self.target_position = position
        self.target_velocity = velocity

    def update(
        self,
        current_pos: Tuple[float, float],
        current_vel: Tuple[float, float],
        dt: float,
    ) -> Tuple[float, float]:
        """
        更新控制器

        Args:
            current_pos: 当前位置
            current_vel: 当前速度
            dt: 时间增量

        Returns:
            控制输出（加速度）
        """
        self.current_position = current_pos
        self.current_velocity = current_vel

        # 第一阶段：位置PID
        pos_error = (
            self.target_position[0] - current_pos[0],
            self.target_position[1] - current_pos[1],
        )
        pos_error_mag = math.sqrt(pos_error[0] ** 2 + pos_error[1] ** 2)

        # 如果接近目标，切换到速度控制
        if pos_error_mag < self.stop_tolerance:
            # 目标是停止
            if self.target_velocity == (0, 0):
                # 速度PID
                vel_output = self.velocity_pid.compute_2d(
                    current_vel, self.target_velocity, dt
                )
                return (-vel_output[0], -vel_output[1])
            else:
                # 减速到目标速度
                target_vel = self.target_velocity
                vel_error = (
                    target_vel[0] - current_vel[0],
                    target_vel[1] - current_vel[1],
                )
                # 简单的速度调整
                return (-vel_error[0] * 0.3, -vel_error[1] * 0.3)

        # 位置PID控制
        pos_correction = self.position_pid.compute_2d(
            current_pos, self.target_position, dt
        )

        # 限制加速度
        accel_mag = math.sqrt(pos_correction[0] ** 2 + pos_correction[1] ** 2)
        if accel_mag > self.max_acceleration:
            scale = self.max_acceleration / accel_mag
            pos_correction = (pos_correction[0] * scale, pos_correction[1] * scale)

        return pos_correction

    def smooth_stop(
        self,
        current_pos: Tuple[float, float],
        current_vel: Tuple[float, float],
        dt: float,
    ) -> Tuple[float, float]:
        """平滑停止"""
        self.target_position = current_pos
        self.target_velocity = (0, 0)

        # 使用速度PID减速
        vel_output = self.velocity_pid.compute_2d(current_vel, (0, 0), dt)

        return (-vel_output[0], -vel_output[1])

    def follow_trajectory(
        self, trajectory: List[TrajectoryPoint], current_idx: int
    ) -> Tuple[float, float]:
        """
        跟随轨迹

        Args:
            trajectory: 轨迹点列表
            current_idx: 当前索引

        Returns:
            控制输出
        """
        if current_idx >= len(trajectory) - 1:
            return (0, 0)

        next_point = trajectory[current_idx + 1]

        # 设置目标
        self.set_target(next_point.position, next_point.velocity)

        # 使用时间进行更新
        dt = next_point.time - trajectory[current_idx].time

        return self.update(
            trajectory[current_idx].position,
            trajectory[current_idx].velocity,
            dt if dt > 0 else 0.016,
        )


class TrajectoryOptimizer:
    """轨迹优化器

    生成平滑的运动轨迹。
    """

    def __init__(self):
        self.waypoint_tolerance = 10.0
        self.max_curvature = 0.5

    def generate_trajectory(
        self,
        start: Tuple[float, float],
        waypoints: List[Tuple[float, float]],
        speed: float = 5.0,
    ) -> List[TrajectoryPoint]:
        """
        生成轨迹

        Args:
            start: 起始位置
            waypoints: 关键点列表
            speed: 目标速度

        Returns:
            轨迹点列表
        """
        trajectory = []

        # 添加起始点
        trajectory.append(TrajectoryPoint(position=start, velocity=(0, 0), time=0))

        # 生成路径点
        all_points = [start] + waypoints
        total_distance = 0
        current_time = 0

        for i in range(1, len(all_points)):
            prev = all_points[i - 1]
            curr = all_points[i]

            # 计算方向和距离
            dx = curr[0] - prev[0]
            dy = curr[1] - prev[1]
            distance = math.sqrt(dx**2 + dy**2)

            if distance < 1:
                continue

            # 插值生成点
            num_points = max(2, int(distance / 10))
            for j in range(1, num_points + 1):
                t = j / num_points

                # 线性插值位置
                x = prev[0] + dx * t
                y = prev[1] + dy * t

                # 计算速度（朝向下一个点）
                if i < len(all_points) - 1:
                    next_p = all_points[i + 1]
                    vx = (next_p[0] - curr[0]) / max(0.1, distance)
                    vy = (next_p[1] - curr[1]) / max(0.1, distance)
                else:
                    vx, vy = 0, 0

                # 速度大小
                speed_factor = min(speed, distance / 0.1)
                vx *= speed_factor
                vy *= speed_factor

                time_step = distance / (speed_factor * num_points)
                current_time += time_step

                trajectory.append(
                    TrajectoryPoint(
                        position=(x, y), velocity=(vx, vy), time=current_time
                    )
                )

            total_distance += distance

        return trajectory

    def smooth_trajectory(
        self, trajectory: List[TrajectoryPoint]
    ) -> List[TrajectoryPoint]:
        """
        平滑轨迹

        使用简单移动平均平滑速度。
        """
        if len(trajectory) < 3:
            return trajectory

        smoothed = []

        for i, point in enumerate(trajectory):
            # 计算平均速度
            if i == 0 or i == len(trajectory) - 1:
                avg_vel = point.velocity
            else:
                prev = trajectory[i - 1]
                next_p = trajectory[i + 1]
                avg_vel = (
                    (prev.velocity[0] + next_p.velocity[0]) / 2,
                    (prev.velocity[1] + next_p.velocity[1]) / 2,
                )

            smoothed.append(
                TrajectoryPoint(
                    position=point.position,
                    velocity=avg_vel,
                    time=point.time,
                    acceleration=point.acceleration,
                )
            )

        return smoothed

    def optimize_for_obstacles(
        self,
        trajectory: List[TrajectoryPoint],
        obstacles: List[Tuple[float, float, float]],
        radius: float = 20.0,
    ) -> List[TrajectoryPoint]:
        """
        优化轨迹以避开障碍物

        Args:
            trajectory: 原始轨迹
            obstacles: 障碍物列表 (x, y, radius)
            radius: 碰撞半径

        Returns:
            优化后的轨迹
        """
        optimized = []

        for point in trajectory:
            safe = True

            for ox, oy, oradius in obstacles:
                dx = point.position[0] - ox
                dy = point.position[1] - oy
                dist = math.sqrt(dx**2 + dy**2)

                if dist < oradius + radius:
                    safe = False
                    break

            if safe:
                optimized.append(point)

        # 如果优化后轨迹太短，返回原轨迹
        if len(optimized) < len(trajectory) * 0.5:
            return trajectory

        return optimized


class VelocityProfiler:
    """速度剖面生成器

    为轨迹生成合适的速度剖面。
    """

    def __init__(self):
        self.max_speed = 6.0
        self.max_acceleration = 0.5
        self.max_deceleration = 0.8

    def compute_velocity_profile(
        self, trajectory: List[TrajectoryPoint]
    ) -> List[TrajectoryPoint]:
        """
        计算速度剖面

        实现：
        1. 加速到巡航速度
        2. 保持巡航速度
        3. 减速停止
        """
        if len(trajectory) < 2:
            return trajectory

        # 第一遍：从后往前计算最大允许速度
        max_allowed = [self.max_speed] * len(trajectory)

        for i in range(len(trajectory) - 2, -1, -1):
            curr = trajectory[i]
            next_p = trajectory[i + 1]

            # 计算距离和方向
            dx = next_p.position[0] - curr.position[1]
            dy = next_p.position[1] - curr.position[1]
            dist = math.sqrt(dx**2 + dy**2)

            if dist < 0.01:
                continue

            # 计算制动距离
            curr_speed = math.sqrt(next_p.velocity[0] ** 2 + next_p.velocity[1] ** 2)
            brake_dist = curr_speed**2 / (2 * self.max_deceleration)

            # 如果距离不足以制动，降低速度
            if dist < brake_dist:
                max_allowed[i] = math.sqrt(2 * self.max_deceleration * dist)

        # 第二遍：应用速度限制
        for i in range(len(trajectory)):
            curr_vel = trajectory[i].velocity
            curr_speed = math.sqrt(curr_vel[0] ** 2 + curr_vel[1] ** 2)

            if curr_speed > max_allowed[i]:
                scale = max_allowed[i] / max(curr_speed, 0.01)
                trajectory[i].velocity = (curr_vel[0] * scale, curr_vel[1] * scale)

        return trajectory

    def compute_time_optimal(
        self, trajectory: List[TrajectoryPoint]
    ) -> List[TrajectoryPoint]:
        """
        计算时间最优速度剖面

        以最大加速度加速，然后以最大减速度制动。
        """
        if len(trajectory) < 2:
            return trajectory

        # 计算距离
        total_dist = 0
        for i in range(1, len(trajectory)):
            dx = trajectory[i].position[0] - trajectory[i - 1].position[0]
            dy = trajectory[i].position[1] - trajectory[i - 1].position[1]
            total_dist += math.sqrt(dx**2 + dy**2)

        # 简单加速-匀速-减速剖面
        t_accel = self.max_speed / self.max_acceleration
        d_accel = 0.5 * self.max_acceleration * t_accel**2

        t_decel = self.max_speed / self.max_deceleration
        d_decel = 0.5 * self.max_deceleration * t_decel**2

        d_cruise = max(0, total_dist - d_accel - d_decel)
        t_cruise = d_cruise / self.max_speed

        # 应用到轨迹
        current_time = 0
        current_speed = 0
        phase = "accel"  # accel, cruise, decel

        for i, point in enumerate(trajectory):
            if i == 0:
                point.velocity = (0, 0)
                point.time = 0
                continue

            prev = trajectory[i - 1]
            dx = point.position[0] - prev.position[0]
            dy = point.position[1] - prev.position[1]
            dist = math.sqrt(dx**2 + dy**2)

            if dist < 0.01:
                point.velocity = prev.velocity
                point.time = prev.time
                continue

            # 更新速度
            dt = dist / max(current_speed, 0.1)

            if phase == "accel":
                current_speed = min(
                    self.max_speed, current_speed + self.max_acceleration * dt
                )
                if current_speed >= self.max_speed:
                    phase = "cruise"
                    t_accel = current_time

            elif phase == "cruise":
                if current_time - t_accel >= t_cruise:
                    phase = "decel"

            elif phase == "decel":
                current_speed = max(0, current_speed - self.max_deceleration * dt)

            # 设置速度方向
            if dist > 0:
                point.velocity = (
                    (dx / dist) * current_speed,
                    (dy / dist) * current_speed,
                )
            else:
                point.velocity = (0, 0)

            current_time += dt
            point.time = current_time

        return trajectory
