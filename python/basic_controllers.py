"""
基础控制层

实现游戏输入的精确控制，包括：
- 基础移动控制器（惯性补偿、碰撞避免）
- 基础攻击控制器（瞄准、射击节奏）
- 输入合成器（指令平滑、优先级仲裁）

根据 reference.md 中的控制模块设计。
"""

import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from models import Vector2D, PlayerData, EnemyData, ProjectileData, GameStateData

logger = logging.getLogger("BasicControllers")


@dataclass
class MovementConfig:
    """移动配置"""

    max_speed: float = 6.0  # 最大速度
    acceleration: float = 0.5  # 加速度
    deceleration: float = 0.3  # 减速度
    stop_threshold: float = 0.5  # 停止阈值
    collision_margin: float = 15.0  # 碰撞边距
    inertia_compensation: float = 0.7  # 惯性补偿系数

    # 紧急躲避
    emergency_dodge_speed: float = 8.0
    emergency_dodge_duration: int = 10

    # 惯性参数
    friction: float = 0.92  # 摩擦系数
    velocity_decay: float = 0.85  # 速度衰减


@dataclass
class AttackConfig:
    """攻击配置"""

    shoot_interval: int = 8  # 射击间隔（帧）
    min_shoot_interval: int = 3  # 最小射击间隔
    aim_tolerance: float = 0.1  # 瞄准容差
    lead_factor: float = 0.3  # 提前量因子
    prediction_frames: int = 5  # 预测帧数

    # 弹道
    projectile_speed: float = 10.0  # 弹速
    projectile_size: float = 8.0  # 投射物大小


@dataclass
class ControlOutput:
    """控制输出"""

    move_x: int = 0  # -1, 0, 1
    move_y: int = 0  # -1, 0, 1
    shoot: bool = False
    shoot_x: int = 0
    shoot_y: int = 0
    use_item: bool = False
    use_bomb: bool = False

    # 额外信息
    confidence: float = 1.0  # 控制置信度
    reasoning: str = ""  # 控制原因

    def is_zero(self) -> bool:
        """是否为空操作"""
        return (
            self.move_x == 0
            and self.move_y == 0
            and not self.shoot
            and not self.use_item
            and not self.use_bomb
        )


class VectorToDiscrete:
    """向量转离散方向工具"""

    # 8方向映射
    DIRECTIONS = [
        (0, -1),  # 上
        (1, -1),  # 右上
        (1, 0),  # 右
        (1, 1),  # 右下
        (0, 1),  # 下
        (-1, 1),  # 左下
        (-1, 0),  # 左
        (-1, -1),  # 左上
    ]

    @staticmethod
    def to_discrete(vec: Vector2D, threshold: float = 0.3) -> Tuple[int, int]:
        """
        将向量转换为离散方向

        Args:
            vec: 输入向量
            threshold: 阈值，低于此值视为0

        Returns:
            (x, y) 方向，值为 -1, 0, 1
        """
        x = 0
        y = 0

        if vec.x > threshold:
            x = 1
        elif vec.x < -threshold:
            x = -1

        if vec.y > threshold:
            y = 1
        elif vec.y < -threshold:
            y = -1

        return (x, y)

    @staticmethod
    def to_8_direction(vec: Vector2D) -> int:
        """
        将向量转换为8方向索引

        Returns:
            0-7 方向索引，或 -1 表示静止
        """
        mag = vec.magnitude()
        if mag < 0.3:
            return -1

        normalized = vec / mag

        best_idx = -1
        best_dot = -1.0

        for idx, (dx, dy) in enumerate(VectorToDiscrete.DIRECTIONS):
            dir_vec = Vector2D(float(dx), float(dy))
            dot = normalized.dot(dir_vec)
            if dot > best_dot:
                best_dot = dot
                best_idx = idx

        return best_idx


class BasicMovementController:
    """基础运动控制器

    实现基于惯性补偿的精确移动控制。
    """

    def __init__(self, config: MovementConfig = None):
        self.config = config or MovementConfig()
        self._velocity = Vector2D(0, 0)
        self._last_move = Vector2D(0, 0)
        self._emergency_dodge_timer = 0
        self._emergency_dodge_dir = Vector2D(0, 0)

    def update(self, move_command: Vector2D, current_vel: Vector2D) -> Vector2D:
        """更新速度（用于内部状态跟踪）"""
        self._velocity = current_vel
        self._last_move = move_command

        if self._emergency_dodge_timer > 0:
            self._emergency_dodge_timer -= 1

        return self._velocity

    def move_to_position(
        self,
        current_pos: Vector2D,
        target_pos: Vector2D,
        current_vel: Vector2D,
        obstacles: List[Vector2D] = None,
    ) -> Tuple[int, int]:
        """
        计算移动到目标位置的控制指令

        Args:
            current_pos: 当前位置
            target_pos: 目标位置
            current_vel: 当前速度
            obstacles: 障碍物位置列表

        Returns:
            (move_x, move_y) 离散方向
        """
        # 计算方向向量
        direction = target_pos - current_pos
        distance = direction.magnitude()

        if distance < self.config.stop_threshold:
            return (0, 0)

        direction = direction / distance

        # 惯性补偿：根据当前速度调整
        velocity_compensation = current_vel * self.config.inertia_compensation

        # 目标速度
        target_speed = min(distance, self.config.max_speed)
        target_velocity = direction * target_speed - velocity_compensation

        # 转换为我们需要的移动向量
        move_vec = target_velocity - current_vel

        # 限制加速度
        move_vec = self._limit_acceleration(move_vec)

        return VectorToDiscrete.to_discrete(move_vec)

    def avoid_collision(
        self, position: Vector2D, obstacles: List[Vector2D], safe_distance: float = 50.0
    ) -> Tuple[int, int]:
        """
        基础碰撞避免

        Args:
            position: 当前位置
            obstacles: 障碍物位置列表
            safe_distance: 安全距离

        Returns:
            躲避方向
        """
        if not obstacles:
            return (0, 0)

        avoidance = Vector2D(0, 0)

        for obs_pos in obstacles:
            to_obs = obs_pos - position
            distance = to_obs.magnitude()

            if 0 < distance < safe_distance:
                # 计算躲避向量（反向）
                weight = (safe_distance - distance) / safe_distance
                avoidance = avoidance - (to_obs / distance) * weight

        return VectorToDiscrete.to_discrete(avoidance)

    def emergency_dodge(
        self, threat_direction: Vector2D, threat_speed: float = 5.0
    ) -> Tuple[int, int]:
        """
        紧急躲避

        Args:
            threat_direction: 威胁方向（从威胁到玩家）
            threat_speed: 威胁速度

        Returns:
            躲避方向
        """
        if self._emergency_dodge_timer > 0:
            return VectorToDiscrete.to_discrete(self._emergency_dodge_dir)

        # 计算躲避方向（垂直于威胁方向）
        dodge_dir = Vector2D(-threat_direction.y, threat_direction.x)

        # 确保躲避方向在地图内
        if dodge_dir.magnitude() == 0:
            dodge_dir = Vector2D(-threat_direction.x, -threat_direction.y)

        dodge_dir = dodge_dir.normalized()

        # 设置紧急躲避状态
        self._emergency_dodge_timer = self.config.emergency_dodge_duration
        self._emergency_dodge_dir = dodge_dir

        return VectorToDiscrete.to_discrete(
            dodge_dir * self.config.emergency_dodge_speed
        )

    def smooth_stop(self, current_vel: Vector2D) -> Tuple[int, int]:
        """
        平滑停止

        Args:
            current_vel: 当前速度

        Returns:
            停止控制
        """
        if current_vel.magnitude() < self.config.stop_threshold:
            return (0, 0)

        # 计算需要的减速向量
        stop_vec = -current_vel * self.config.deceleration

        return VectorToDiscrete.to_discrete(stop_vec)

    def _limit_acceleration(self, move_vec: Vector2D) -> Vector2D:
        """限制加速度"""
        mag = move_vec.magnitude()
        if mag > self.config.acceleration:
            return move_vec / mag * self.config.acceleration
        return move_vec


class BasicAttackController:
    """基础攻击控制器

    实现瞄准、射击节奏控制。
    """

    def __init__(self, config: AttackConfig = None):
        self.config = config or AttackConfig()
        self._last_shoot_frame = 0
        self._shoot_cooldown = 0

    def aim_at_target(
        self, player_pos: Vector2D, target_pos: Vector2D, target_vel: Vector2D = None
    ) -> Tuple[int, int]:
        """
        计算瞄准目标的射击方向

        Args:
            player_pos: 玩家位置
            target_pos: 目标位置
            target_vel: 目标速度（可选，用于预判）

        Returns:
            (shoot_x, shoot_y) 射击方向
        """
        if target_vel is None:
            target_vel = Vector2D(0, 0)

        # 简单预判
        lead_factor = self.config.lead_factor
        predicted_pos = target_pos + target_vel * lead_factor

        direction = predicted_pos - player_pos

        return VectorToDiscrete.to_discrete(direction)

    def should_shoot(self, current_frame: int) -> bool:
        """控制射击节奏"""
        if self._shoot_cooldown > 0:
            self._shoot_cooldown -= 1
            return False

        # 简单的射击间隔控制
        if current_frame - self._last_shoot_frame >= self.config.shoot_interval:
            self._shoot_cooldown = self.config.shoot_interval
            self._last_shoot_frame = current_frame
            return True

        return False

    def get_clear_shot(
        self,
        player_pos: Vector2D,
        target_pos: Vector2D,
        obstacles: List[Vector2D] = None,
    ) -> bool:
        """
        检查是否有清晰的射击线路

        Args:
            player_pos: 玩家位置
            target_pos: 目标位置
            obstacles: 障碍物位置列表

        Returns:
            是否有清晰线路
        """
        # 简单的直线检查（实际需要更复杂的射线检测）
        direction = target_pos - player_pos
        distance = direction.magnitude()

        if distance == 0:
            return False

        direction = direction / distance
        step_size = 20.0
        steps = int(distance / step_size)

        for i in range(1, steps):
            check_pos = player_pos + direction * (step_size * i)

            if obstacles:
                for obs in obstacles:
                    if check_pos.distance_to(obs) < self.config.projectile_size:
                        return False

        return True

    def calculate_lead_shot(
        self,
        shooter_pos: Vector2D,
        target_pos: Vector2D,
        target_vel: Vector2D,
        projectile_speed: float,
    ) -> Vector2D:
        """
        计算提前量射击

        解决移动目标的射击问题。
        """
        to_target = target_pos - shooter_pos
        distance = to_target.magnitude()

        if distance == 0:
            return Vector2D(0, 0)

        # 计算需要的时间
        time_to_target = distance / projectile_speed

        # 预测目标位置
        predicted_pos = target_pos + target_vel * time_to_target

        # 计算射击方向
        shoot_dir = predicted_pos - shooter_pos

        return shoot_dir.normalized()

    def get_shooting_pattern(self, enemy_type: int, distance: float) -> str:
        """
        根据敌人类型选择射击模式

        Args:
            enemy_type: 敌人类型
            distance: 距离

        Returns:
            射击模式: "normal", "spread", "focus"
        """
        # 简单模式选择
        if distance > 300:
            return "focus"  # 远距离集中射击
        elif distance < 100:
            return "spread"  # 近距离散射
        else:
            return "normal"  # 正常射击


class InputSynthesizer:
    """输入合成器

    合并多个控制指令，处理优先级和冲突。
    """

    def __init__(self):
        self._pending_moves: List[ControlOutput] = []
        self._last_output: ControlOutput = ControlOutput()
        self._smoothing_factor = 0.5  # 平滑因子

    def add_movement(self, move: ControlOutput):
        """添加移动指令"""
        self._pending_moves.append(move)

    def add_attack(self, attack: ControlOutput):
        """添加攻击指令"""
        self._pending_moves.append(attack)

    def synthesize(self) -> ControlOutput:
        """
        合成最终控制指令

        优先级：
        1. 紧急躲避（最高）
        2. 攻击
        3. 移动
        4. 道具使用
        """
        if not self._pending_moves:
            return ControlOutput()

        # 按优先级排序
        prioritized = self._prioritize_commands(self._pending_moves)

        # 合并指令
        result = self._merge_commands(prioritized)

        # 平滑处理
        result = self._smooth_output(result)

        # 清除已处理的指令
        self._pending_moves.clear()
        self._last_output = result

        return result

    def _prioritize_commands(
        self, commands: List[ControlOutput]
    ) -> List[ControlOutput]:
        """按优先级排序"""

        def get_priority(cmd: ControlOutput) -> int:
            if "dodge" in cmd.reasoning.lower():
                return 0  # 紧急躲避最高
            if cmd.shoot:
                return 1  # 攻击
            if cmd.move_x != 0 or cmd.move_y != 0:
                return 2  # 移动
            if cmd.use_item or cmd.use_bomb:
                return 3  # 道具
            return 4

        return sorted(commands, key=get_priority)

    def _merge_commands(self, commands: List[ControlOutput]) -> ControlOutput:
        """合并指令"""
        result = ControlOutput()

        for cmd in commands:
            # 移动合并（取非零值，优先使用后面的）
            if cmd.move_x != 0 or cmd.move_y != 0:
                result.move_x = cmd.move_x
                result.move_y = cmd.move_y

            # 射击合并
            if cmd.shoot:
                result.shoot = True
                result.shoot_x = cmd.shoot_x
                result.shoot_y = cmd.shoot_y

            # 道具合并
            if cmd.use_item:
                result.use_item = True
            if cmd.use_bomb:
                result.use_bomb = True

            # 置信度取最小值
            result.confidence = min(result.confidence, cmd.confidence)

            # 合并原因
            if cmd.reasoning:
                result.reasoning = cmd.reasoning

        return result

    def _smooth_output(self, output: ControlOutput) -> ControlOutput:
        """平滑输出"""
        if self._last_output.is_zero():
            return output

        # 移动平滑
        move_x = int(
            output.move_x * (1 - self._smoothing_factor)
            + self._last_output.move_x * self._smoothing_factor
        )
        move_y = int(
            output.move_y * (1 - self._smoothing_factor)
            + self._last_output.move_y * self._smoothing_factor
        )

        # 确保值在 -1 到 1 之间
        move_x = max(-1, min(1, move_x))
        move_y = max(-1, min(1, move_y))

        output.move_x = move_x
        output.move_y = move_y

        return output


class BasicControllerManager:
    """基础控制器管理器

    整合移动、攻击和输入合成器。
    """

    def __init__(
        self, move_config: MovementConfig = None, attack_config: AttackConfig = None
    ):
        self.move_controller = BasicMovementController(move_config)
        self.attack_controller = BasicAttackController(attack_config)
        self.input_synthesizer = InputSynthesizer()

    def compute_control(
        self,
        game_state: GameStateData,
        target_enemy: EnemyData = None,
        evade_threats: List[ProjectileData] = None,
    ) -> ControlOutput:
        """
        计算控制指令

        Args:
            game_state: 当前游戏状态
            target_enemy: 目标敌人
            evade_threats: 需要躲避的投射物

        Returns:
            控制输出
        """
        player = game_state.get_primary_player()
        if not player:
            return ControlOutput()

        current_pos = player.position
        current_vel = player.velocity
        frame = game_state.frame

        # 1. 处理威胁躲避
        if evade_threats:
            dodge_cmd = self._handle_evasion(current_pos, evade_threats, current_vel)
            if dodge_cmd:
                self.input_synthesizer.add_movement(dodge_cmd)

        # 2. 处理移动（朝向目标或安全位置）
        if target_enemy:
            move_cmd = self._handle_combat_movement(
                current_pos, current_vel, target_enemy
            )
            self.input_synthesizer.add_movement(move_cmd)

        # 3. 处理攻击
        if target_enemy and self.attack_controller.should_shoot(frame):
            attack_cmd = self._handle_attack(current_pos, target_enemy)
            self.input_synthesizer.add_attack(attack_cmd)

        # 4. 更新控制器状态
        self.move_controller.update(
            Vector2D(
                self.input_synthesizer._last_output.move_x,
                self.input_synthesizer._last_output.move_y,
            ),
            current_vel,
        )

        # 5. 合成最终输出
        return self.input_synthesizer.synthesize()

    def _handle_evasion(
        self,
        current_pos: Vector2D,
        threats: List[ProjectileData],
        current_vel: Vector2D,
    ) -> ControlOutput:
        """处理躲避"""
        if not threats:
            return None

        # 计算威胁中心
        threat_center = Vector2D(0, 0)
        for proj in threats:
            threat_center = threat_center + proj.position
        threat_center = threat_center / len(threats)

        # 计算威胁方向
        threat_direction = threat_center - current_pos

        # 计算躲避
        move = self.move_controller.emergency_dodge(threat_direction)

        return ControlOutput(
            move_x=move[0], move_y=move[1], confidence=0.9, reasoning="evade_threat"
        )

    def _handle_combat_movement(
        self, current_pos: Vector2D, current_vel: Vector2D, target: EnemyData
    ) -> ControlOutput:
        """处理战斗移动"""
        # 保持适当距离
        optimal_distance = 150.0
        current_distance = current_pos.distance_to(target.position)

        if current_distance < optimal_distance - 50:
            # 太近，后退
            direction = current_pos - target.position
        elif current_distance > optimal_distance + 50:
            # 太近，接近
            direction = target.position - current_pos
        else:
            # 距离合适，围绕移动
            # 计算切线方向
            to_target = target.position - current_pos
            direction = Vector2D(-to_target.y, to_target.x)

        move = self.move_controller.move_to_position(
            current_pos, current_pos + direction, current_vel
        )

        return ControlOutput(
            move_x=move[0], move_y=move[1], confidence=0.7, reasoning="combat_movement"
        )

    def _handle_attack(self, player_pos: Vector2D, target: EnemyData) -> ControlOutput:
        """处理攻击"""
        aim = self.attack_controller.aim_at_target(
            player_pos, target.position, target.velocity
        )

        return ControlOutput(
            shoot=True,
            shoot_x=aim[0],
            shoot_y=aim[1],
            confidence=0.8,
            reasoning="shoot_target",
        )
