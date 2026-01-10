"""
控制模块 (Control Module)

精确执行计划，考虑游戏物理特性。

子模块:
- 运动控制器 (Movement Controller): 惯性补偿、微调控制、紧急制动
- 攻击控制器 (Attack Controller): 方向微调、射击节奏、多目标切换
- 输入合成器 (Input Synthesizer): 指令平滑、优先级仲裁、容错处理
"""

import math
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from dataclasses import dataclass
from enum import Enum

from ..perception import Vector2D
from ..planning import ExecutionPlan, PathSegment
from ..decision import ActionIntent, ActionType

logger = logging.getLogger("ControlModule")


class InputCommand:
    """输入指令"""

    def __init__(self):
        self.move: Optional[Tuple[int, int]] = None  # (-1, 0, 1)
        self.shoot: Optional[Tuple[int, int]] = None  # (-1, 0, 1)
        self.use_item: bool = False
        self.use_bomb: bool = False
        self.use_card: bool = False
        self.use_pill: bool = False
        self.drop: bool = False

    def to_dict(self) -> Dict:
        return {
            "move": self.move,
            "shoot": self.shoot,
            "use_item": self.use_item,
            "use_bomb": self.use_bomb,
            "use_card": self.use_card,
            "use_pill": self.use_pill,
            "drop": self.drop,
        }

    def is_empty(self) -> bool:
        """检查是否为空指令"""
        return (
            self.move is None
            and self.shoot is None
            and not any(
                [self.use_item, self.use_bomb, self.use_card, self.use_pill, self.drop]
            )
        )


@dataclass
class MovementState:
    """运动状态"""

    position: Vector2D
    velocity: Vector2D
    target_position: Optional[Vector2D] = None
    target_direction: Optional[Vector2D] = None

    # 状态
    is_moving: bool = False
    is_at_target: bool = False
    overshoot_detected: bool = False

    # 误差
    position_error: float = 0.0
    direction_error: float = 0.0


class MovementController:
    """
    运动控制器

    功能：
    - 惯性补偿算法（精确停靠）
    - 微调控制系统（小幅度调整）
    - 紧急制动处理
    - 速度曲线优化（加速/减速）
    """

    def __init__(self):
        # PID参数
        self.kp_position = 0.5  # 位置比例
        self.ki_position = 0.1  # 位置积分
        self.kd_position = 0.2  # 位置微分

        self.kp_velocity = 0.3  # 速度比例
        self.kd_velocity = 0.1  # 速度微分

        # 控制参数
        self.position_tolerance = 5.0  # 位置容差
        self.direction_tolerance = 0.1  # 方向容差
        self.max_speed = 8.0  # 最大速度
        self.acceleration = 0.5  # 加速度
        self.deceleration = 0.8  # 减速度

        # 惯性参数
        self.inertia_factor = 0.3  # 惯性因子
        self.brake_threshold = 50.0  # 制动距离阈值

        # 状态
        self.integral_error = Vector2D(0, 0)  # 积分误差
        self.last_error = Vector2D(0, 0)  # 上次误差
        self.last_time = 0.0

    def compute_movement(
        self,
        current_pos: Vector2D,
        current_vel: Vector2D,
        target_pos: Vector2D,
        target_dir: Vector2D = None,
        dt: float = 1.0 / 30.0,
    ) -> Tuple[Tuple[int, int], MovementState]:
        """
        计算移动指令

        Args:
            current_pos: 当前位置
            current_vel: 当前速度
            target_pos: 目标位置
            target_dir: 目标方向（可选）
            dt: 时间步长

        Returns:
            (移动方向, 运动状态)
        """
        # 计算到目标的向量
        to_target = target_pos - current_pos
        distance = to_target.length()

        # 更新状态
        state = MovementState(
            position=current_pos,
            velocity=current_vel,
            target_position=target_pos,
            target_direction=target_dir,
        )

        # 检查是否到达
        if distance < self.position_tolerance:
            state.is_at_target = True
            return (0, 0), state

        state.position_error = distance

        # 计算理想速度
        if target_dir:
            # 有方向偏好
            direction = target_dir.normalized()
        else:
            # 朝向目标
            direction = to_target.normalized()

        state.target_direction = direction

        # 计算方向误差
        if current_vel.length() > 0.1:
            current_dir = current_vel.normalized()
            error = 1 - direction.dot(current_dir)
            state.direction_error = error

        # 惯性补偿
        adjusted_direction = self._apply_inertia_compensation(
            direction, current_vel, distance
        )

        # 计算期望速度
        desired_speed = self._compute_desired_speed(distance, current_vel.length())

        # PID控制
        velocity_command = self._pid_control(
            adjusted_direction * desired_speed, current_vel, dt
        )

        # 转换到离散方向
        move_dir = self._velocity_to_discrete(velocity_command)

        state.is_moving = move_dir != (0, 0)

        return move_dir, state

    def _apply_inertia_compensation(
        self, desired_dir: Vector2D, current_vel: Vector2D, distance: float
    ) -> Vector2D:
        """惯性补偿"""
        speed = current_vel.length()
        if speed < 0.1:
            return desired_dir

        # 计算当前运动方向
        current_dir = current_vel.normalized()

        # 如果需要反转方向
        dot = desired_dir.dot(current_dir)
        if dot < 0:
            # 需要完全反转
            return desired_dir

        # 平滑过渡
        compensation = current_dir * self.inertia_factor
        adjusted = desired_dir * (1 - self.inertia_factor) + compensation
        return adjusted.normalized()

    def _compute_desired_speed(self, distance: float, current_speed: float) -> float:
        """计算期望速度"""
        # 接近目标时减速
        if distance < self.brake_threshold:
            # 制动
            ratio = distance / self.brake_threshold
            return min(self.max_speed, current_speed * ratio + 1)

        # 远距离加速
        if current_speed < self.max_speed:
            return min(self.max_speed, current_speed + self.acceleration)

        return current_speed

    def _pid_control(
        self, desired_vel: Vector2D, current_vel: Vector2D, dt: float
    ) -> Vector2D:
        """PID控制"""
        error = desired_vel - current_vel

        # 积分项
        self.integral_error += error * dt
        self.integral_error = self._clamp_vector(self.integral_error, 1.0)

        # 微分项
        derivative = (error - self.last_error) / dt if dt > 0 else Vector2D(0, 0)
        self.last_error = error

        # PID输出
        output = (
            error * self.kp_velocity
            + self.integral_error * self.ki_position
            + derivative * self.kd_velocity
        )

        # 限制最大输出
        output = self._clamp_vector(output, self.max_speed)

        self.last_time = 0

        return output

    def _clamp_vector(self, vec: Vector2D, max_length: float) -> Vector2D:
        """限制向量长度"""
        length = vec.length()
        if length > max_length and length > 0:
            return vec * (max_length / length)
        return vec

    def _velocity_to_discrete(self, velocity: Vector2D) -> Tuple[int, int]:
        """将速度转换为离散方向"""
        x = 0
        y = 0

        if velocity.x > 0.1:
            x = 1
        elif velocity.x < -0.1:
            x = -1

        if velocity.y > 0.1:
            y = 1
        elif velocity.y < -0.1:
            y = -1

        return (x, y)

    def emergency_brake(self, current_vel: Vector2D) -> Tuple[int, int]:
        """
        紧急制动

        Returns:
            制动方向（用于停止移动）
        """
        speed = current_vel.length()
        if speed < 0.1:
            return (0, 0)

        # 计算制动方向（与速度相反）
        direction = current_vel.normalized() * -1

        return self._velocity_to_discrete(direction * speed)


class AttackController:
    """
    攻击控制器

    功能：
    - 方向微调（精确瞄准）
    - 射击节奏控制（优化射速）
    - 多目标切换
    - 特殊攻击执行
    """

    def __init__(self):
        # 射击参数
        self.fire_rate = 15  # 帧间隔
        self.burst_count = 3  # 连发数
        self.burst_delay = 3  # 连发间隔

        # 瞄准参数
        self.aim_smoothing = 0.8  # 瞄准平滑因子
        self.max_aim_correction = 0.3  # 最大瞄准校正

        # 状态
        self.last_shot_frame = 0
        self.current_burst = 0
        self.burst_cooldown = 0

    def compute_shoot_command(
        self,
        aim_direction: Vector2D,
        current_frame: int,
        is_burst_mode: bool = False,
        burst_target: int = None,
    ) -> Tuple[Optional[Tuple[int, int]], bool]:
        """
        计算射击指令

        Args:
            aim_direction: 瞄准方向
            current_frame: 当前帧
            is_burst_mode: 是否连发模式
            burst_target: 连发目标ID

        Returns:
            (射击方向, 是否射击)
        """
        # 检查冷却
        if current_frame - self.last_shot_frame < self.fire_rate:
            return None, False

        # 检查连发模式
        if is_burst_mode:
            if self.burst_cooldown > 0:
                self.burst_cooldown -= 1
                return None, False

            if self.current_burst >= self.burst_count:
                # 连发结束，进入冷却
                self.burst_cooldown = self.fire_rate * 2
                self.current_burst = 0
                return None, False

        # 转换为离散方向
        shoot_dir = self._direction_to_discrete(aim_direction)

        self.last_shot_frame = current_frame

        if is_burst_mode:
            self.current_burst += 1
            if self.current_burst < self.burst_count:
                self.burst_cooldown = self.burst_delay

        return shoot_dir, True

    def compute_multi_target_sequence(
        self, targets: List[Dict], current_frame: int
    ) -> List[Dict]:
        """
        计算多目标射击序列

        Args:
            targets: 目标列表 [{id, direction, priority}, ...]
            current_frame: 当前帧

        Returns:
            射击序列 [{frame, target_id, direction}, ...]
        """
        # 按优先级排序
        sorted_targets = sorted(
            targets, key=lambda t: t.get("priority", 0), reverse=True
        )

        sequence = []
        frame = current_frame

        for target in sorted_targets[:3]:  # 最多3个目标
            sequence.append(
                {
                    "frame": frame,
                    "target_id": target["id"],
                    "direction": target["direction"],
                }
            )
            frame += self.fire_rate

        return sequence

    def _direction_to_discrete(self, direction: Vector2D) -> Tuple[int, int]:
        """将方向转换为离散方向"""
        x = 0
        y = 0

        # 8方向
        angle = math.atan2(direction.y, direction.x)

        # 对齐到8方向
        if -0.392 <= angle < 0.392:  # 右
            x, y = 1, 0
        elif 0.392 <= angle < 1.178:  # 右下
            x, y = 1, 1
        elif 1.178 <= angle < 2.356:  # 下
            x, y = 0, 1
        elif 2.356 <= angle < 3.534 or -3.534 <= angle < -2.356:  # 左
            x, y = -1, 0
        elif -2.356 <= angle < -1.178:  # 左上
            x, y = -1, -1
        elif -1.178 <= angle < -0.392:  # 左下
            x, y = -1, -1
        elif -0.392 <= angle < 0:  # 右上
            x, y = 1, -1
        else:  # 上
            x, y = 0, -1

        return (x, y)


class InputSynthesizer:
    """
    输入合成器

    功能：
    - 指令平滑处理（避免输入突变）
    - 优先级仲裁（多指令冲突）
    - 容错处理（计划与实际偏差）
    """

    def __init__(self):
        self.movement_controller = MovementController()
        self.attack_controller = AttackController()

        # 平滑参数
        self.move_smoothing = 0.7  # 移动平滑
        self.shoot_smoothing = 0.9  # 射击平滑

        # 历史记录
        self.last_move: Optional[Tuple[int, int]] = None
        self.last_shoot: Optional[Tuple[int, int]] = None
        self.last_use_item: bool = False
        self.last_use_bomb: bool = False

        # 优先级
        self.priority_order = ["emergency_stop", "move", "shoot", "item"]

    def synthesize(
        self, plan: ExecutionPlan, current_state: Dict, current_frame: int
    ) -> InputCommand:
        """
        合成输入指令

        Args:
            plan: 执行计划
            current_state: 当前状态
            current_frame: 当前帧

        Returns:
            输入指令
        """
        command = InputCommand()

        # 1. 紧急停止检查
        if self._check_emergency_stop(current_state):
            command.move = self.movement_controller.emergency_brake(
                current_state.get("velocity", Vector2D(0, 0))
            )
            return command

        # 2. 处理移动
        move_dir = self._process_movement(plan, current_state)
        command.move = move_dir

        # 3. 处理射击
        shoot_dir, should_shoot = self._process_shooting(
            plan, current_state, current_frame
        )
        if should_shoot:
            command.shoot = shoot_dir

        # 4. 处理道具使用
        self._process_items(plan, command)

        return command

    def _check_emergency_stop(self, current_state: Dict) -> bool:
        """检查是否需要紧急停止"""
        # 检查是否在危险区域
        if current_state.get("in_hazard", False):
            return True

        # 检查是否有投射物在极近距离
        projectiles = current_state.get("nearby_projectiles", [])
        for proj in projectiles:
            if proj.get("distance", 100) < 30:
                return True

        return False

    def _process_movement(
        self, plan: ExecutionPlan, current_state: Dict
    ) -> Tuple[int, int]:
        """处理移动"""
        current_pos = current_state.get("position", Vector2D(0, 0))
        current_vel = current_state.get("velocity", Vector2D(0, 0))

        if not plan.path_segments:
            return (0, 0)

        # 获取第一个路径段的目标
        target_pos = plan.path_segments[0].end_pos if plan.path_segments else None
        target_dir = None

        if plan.action_intent.move_direction:
            target_dir = plan.action_intent.move_direction

        # 计算移动
        move_dir, state = self.movement_controller.compute_movement(
            current_pos, current_vel, target_pos, target_dir
        )

        # 平滑处理
        if self.last_move is not None:
            move_dir = self._smooth_direction(
                move_dir, self.last_move, self.move_smoothing
            )

        self.last_move = move_dir

        return move_dir

    def _process_shooting(
        self, plan: ExecutionPlan, current_state: Dict, current_frame: int
    ) -> Tuple[Optional[Tuple[int, int]], bool]:
        """处理射击"""
        if not plan.shoot_targets:
            return None, False

        # 获取当前目标
        target = plan.shoot_targets[0]
        aim_dir = target.get("direction", Vector2D(1, 0))

        # 平滑瞄准方向
        if self.last_shoot is not None:
            last_aim = Vector2D(self.last_shoot[0], self.last_shoot[1])
            aim_dir = last_aim * self.shoot_smoothing + aim_dir * (
                1 - self.shoot_smoothing
            )
            aim_dir = aim_dir.normalized()

        # 计算射击
        shoot_dir, should_shoot = self.attack_controller.compute_shoot_command(
            aim_dir, current_frame, is_burst_mode=len(plan.shoot_targets) > 1
        )

        if should_shoot:
            self.last_shoot = shoot_dir

        return shoot_dir, should_shoot

    def _process_items(self, plan: ExecutionPlan, command: InputCommand):
        """处理道具使用"""
        action_type = plan.action_intent.action_type

        if action_type == ActionType.USE_ITEM:
            command.use_item = True

        elif action_type == ActionType.USE_BOMB:
            command.use_bomb = True

    def _smooth_direction(
        self, current: Tuple[int, int], last: Tuple[int, int], factor: float
    ) -> Tuple[int, int]:
        """平滑方向变化"""
        # 简单的平滑：如果方向改变太大，平滑过渡
        if current == last:
            return current

        # 检查是否应该平滑
        change_count = sum(1 for c, l in zip(current, last) if c != l)

        if change_count == 2:
            # 突然转向，可能需要平滑
            return last  # 保持上一帧的方向

        return current

    def reset(self):
        """重置状态"""
        self.last_move = None
        self.last_shoot = None
        self.last_use_item = False
        self.last_use_bomb = False
        self.movement_controller.integral_error = Vector2D(0, 0)
        self.movement_controller.last_error = Vector2D(0, 0)


class ControlModule:
    """
    控制模块主类

    整合运动控制器、攻击控制器和输入合成器，
    将执行计划转换为游戏输入指令。

    输入: 执行计划 (ExecutionPlan) + 当前状态
    输出: 游戏输入指令 (InputCommand)
    """

    def __init__(self):
        self.input_synthesizer = InputSynthesizer()

        # 统计
        self.stats = {
            "total_commands": 0,
            "move_commands": 0,
            "shoot_commands": 0,
            "item_commands": 0,
            "avg_command_latency_ms": 0.0,
        }

    def execute(
        self, plan: ExecutionPlan, current_state: Dict, current_frame: int
    ) -> InputCommand:
        """
        执行计划，生成输入指令

        Args:
            plan: 执行计划
            current_state: 当前状态
            current_frame: 当前帧

        Returns:
            输入指令
        """
        import time

        start_time = time.time()

        command = self.input_synthesizer.synthesize(plan, current_state, current_frame)

        # 更新统计
        self.stats["total_commands"] += 1
        if command.move:
            self.stats["move_commands"] += 1
        if command.shoot:
            self.stats["shoot_commands"] += 1
        if command.use_item or command.use_bomb:
            self.stats["item_commands"] += 1

        latency = (time.time() - start_time) * 1000
        self.stats["avg_command_latency_ms"] = (
            self.stats["avg_command_latency_ms"] * 0.9 + latency * 0.1
        )

        return command

    def reset(self):
        """重置控制器状态"""
        self.input_synthesizer.reset()

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return dict(self.stats)


# ==================== 便捷函数 ====================


def create_control_module() -> ControlModule:
    """创建控制模块实例"""
    return ControlModule()


# 导出主要类
__all__ = [
    "ControlModule",
    "MovementController",
    "AttackController",
    "InputSynthesizer",
    "InputCommand",
    "MovementState",
    "create_control_module",
]
