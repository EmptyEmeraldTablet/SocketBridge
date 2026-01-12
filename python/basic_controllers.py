"""
SocketBridge 基础控制器模块

实现基础控制逻辑：
- 移动控制
- 射击控制
- 闪避控制

根据 reference.md 第一阶段设计。
"""

import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging

from models import (
    Vector2D,
    GameStateData,
    PlayerData,
    EnemyData,
    ProjectileData,
    ControlOutput,
)

# 使用 TYPE_CHECKING 避免循环导入
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from threat_analysis import ThreatInfo

logger = logging.getLogger("BasicControllers")


class MovementStyle(Enum):
    """移动风格"""

    KITING = "kiting"  # 放风筝：保持距离
    AGGRESSIVE = "aggressive"  # 激进：靠近敌人
    DEFENSIVE = "defensive"  # 防御：优先躲避
    BALANCED = "balanced"  # 平衡
    RANDOM = "random"  # 随机移动


@dataclass
class ControlConfig:
    """控制配置"""

    # 距离阈值
    combat_engage_distance: float = 200.0  # 进入战斗的距离
    retreat_distance: float = 100.0  # 撤退的距离
    optimal_distance: float = 150.0  # 最优战斗距离

    # 移动参数
    move_speed: float = 1.0
    strafe_speed: float = 0.8

    # 射击参数
    shoot_cooldown: int = 10  # 射击冷却帧数
    burst_count: int = 3  # 突发射击数量

    # 闪避参数
    dodge_threshold: float = 0.7  # 闪避威胁阈值
    dodge_cooldown: int = 60  # 闪避冷却帧数


class BasicControllerManager:
    """基础控制器管理器

    计算移动、射击、闪避等基础控制输出。
    """

    def __init__(self, config: Optional[ControlConfig] = None):
        self.config = config or ControlConfig()
        self.movement_style = MovementStyle.KITING
        self.aggression = 0.5  # 0-1，攻击性
        self.shoot_cooldown_counter = 0
        self.dodge_cooldown_counter = 0

        # 最后的控制输出（用于平滑）
        self.last_move = Vector2D(0, 0)
        self.last_shoot_dir = Vector2D(0, 0)

    def set_movement_style(self, style: MovementStyle):
        """设置移动风格"""
        self.movement_style = style

    def set_aggression(self, level: float):
        """设置攻击性 (0-1)"""
        self.aggression = max(0, min(1, level))

    def compute_control(
        self,
        game_state: GameStateData,
        target_enemy: Optional[EnemyData] = None,
        evade_threats: Optional[List["ThreatInfo"]] = None,
        shoot_override: Optional[Tuple[float, float]] = None,
    ) -> ControlOutput:
        """计算控制输出

        Args:
            game_state: 当前游戏状态
            target_enemy: 目标敌人
            evade_threats: 需要躲避的威胁
            shoot_override: 射击方向覆盖 (x, y)

        Returns:
            控制输出
        """
        control = ControlOutput()

        player = game_state.get_primary_player()
        if player is None:
            return control

        # 1. 计算闪避
        evasion = self._compute_evasion(player.position, evade_threats or [])
        if evasion.magnitude() > 0:
            control.move_x, control.move_y = self._vector_to_direction(evasion)
            control.reasoning = "evading_threat"
            self.last_move = evasion
            return control

        # 2. 计算移动
        move_dir = self._compute_movement(player, game_state, target_enemy)
        control.move_x, control.move_y = self._vector_to_direction(move_dir)

        # 3. 计算射击
        if shoot_override:
            control.shoot = True
            control.shoot_x, control.shoot_y = (
                int(shoot_override[0]),
                int(shoot_override[1]),
            )
        else:
            shoot_dir = self._compute_shooting(player, game_state, target_enemy)
            if shoot_dir.magnitude() > 0:
                control.shoot = True
                control.shoot_x, control.shoot_y = self._vector_to_direction(shoot_dir)

        # 更新冷却
        if self.shoot_cooldown_counter > 0:
            self.shoot_cooldown_counter -= 1
        if self.dodge_cooldown_counter > 0:
            self.dodge_cooldown_counter -= 1

        return control

    def _compute_evasion(
        self, player_pos: Vector2D, threats: List["ThreatInfo"]
    ) -> Vector2D:
        """计算闪避方向"""
        if not threats or self.dodge_cooldown_counter > 0:
            return Vector2D(0, 0)

        # 计算远离威胁的方向
        evasion = Vector2D(0, 0)
        for threat in threats:
            threat_dir = threat.position - player_pos
            if threat_dir.magnitude() > 0:
                evasion = evasion - threat_dir.normalized()

        if evasion.magnitude() > 0:
            self.dodge_cooldown_counter = self.config.dodge_cooldown

        return evasion.normalized()

    def _compute_movement(
        self,
        player: PlayerData,
        game_state: GameStateData,
        target_enemy: Optional[EnemyData],
    ) -> Vector2D:
        """计算移动方向"""
        move = Vector2D(0, 0)

        if target_enemy:
            to_enemy = target_enemy.position - player.position
            distance = to_enemy.magnitude()

            # 根据移动风格调整
            if self.movement_style == MovementStyle.KITING:
                # 保持距离
                if distance > self.config.combat_engage_distance:
                    move = to_enemy.normalized()
                elif distance < self.config.retreat_distance:
                    move = -to_enemy.normalized()
                else:
                    # 环绕移动
                    move = self._compute_strafe(player, target_enemy)

            elif self.movement_style == MovementStyle.AGGRESSIVE:
                # 靠近敌人
                move = to_enemy.normalized() * (1 + self.aggression)

            elif self.movement_style == MovementStyle.DEFENSIVE:
                # 优先保持距离
                if distance < self.config.optimal_distance * 1.5:
                    move = -to_enemy.normalized()
                else:
                    move = to_enemy.normalized() * 0.5

            elif self.movement_style == MovementStyle.BALANCED:
                # 平衡
                if distance > self.config.optimal_distance:
                    move = to_enemy.normalized()
                elif distance < self.config.optimal_distance * 0.7:
                    move = -to_enemy.normalized()
                else:
                    move = self._compute_strafe(player, target_enemy)

            elif self.movement_style == MovementStyle.RANDOM:
                # 随机移动（用于迷惑敌人）
                import random

                move = Vector2D(
                    random.uniform(-1, 1), random.uniform(-1, 1)
                ).normalized()

        return move.normalized()

    def _compute_strafe(self, player: PlayerData, target_enemy: EnemyData) -> Vector2D:
        """计算环绕移动"""
        # 计算切线方向
        to_enemy = target_enemy.position - player.position
        if to_enemy.magnitude() < 1:
            return Vector2D(0, 0)

        # 垂直向量（环绕方向）
        strafe = Vector2D(-to_enemy.y, to_enemy.x).normalized()

        # 根据攻击性调整环绕方向
        if self.aggression < 0.5:
            strafe = -strafe  # 反向环绕

        return strafe

    def _compute_shooting(
        self,
        player: PlayerData,
        game_state: GameStateData,
        target_enemy: Optional[EnemyData],
    ) -> Vector2D:
        """计算射击方向"""
        if self.shoot_cooldown_counter > 0:
            return Vector2D(0, 0)

        # 检查是否有敌人投射物需要拦截
        for proj in game_state.enemy_projectiles:
            if proj.is_homing and proj.position.distance_to(player.position) < 100:
                # 射击拦截敌人投射物
                self.shoot_cooldown_counter = self.config.shoot_cooldown
                return (proj.position - player.position).normalized()

        if target_enemy:
            # 射击目标
            self.shoot_cooldown_counter = self.config.shoot_cooldown
            return (target_enemy.position - player.position).normalized()

        # 没有目标，不射击
        return Vector2D(0, 0)

    def _vector_to_direction(self, vec: Vector2D) -> Tuple[int, int]:
        """将向量转换为方向值 (-1, 0, 1)"""
        x = 0
        y = 0

        if vec.x > 0.3:
            x = 1
        elif vec.x < -0.3:
            x = -1

        if vec.y > 0.3:
            y = 1
        elif vec.y < -0.3:
            y = -1

        return (x, y)

    def reset(self):
        """重置控制器状态"""
        self.shoot_cooldown_counter = 0
        self.dodge_cooldown_counter = 0
        self.last_move = Vector2D(0, 0)
        self.last_shoot_dir = Vector2D(0, 0)


# 导入 ThreatInfo（放在模块末尾以避免循环引用）
from threat_analysis import ThreatInfo


def create_basic_controller(
    config: Optional[ControlConfig] = None,
) -> BasicControllerManager:
    """创建基础控制器实例"""
    return BasicControllerManager(config or ControlConfig())
