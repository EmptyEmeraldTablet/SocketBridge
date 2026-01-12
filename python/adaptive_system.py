"""
SocketBridge 自适应系统模块

实现场景识别和动态参数调整。
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from models import GameStateData, Vector2D

logger = logging.getLogger("AdaptiveSystem")


class ScenarioType(Enum):
    """场景类型"""

    NORMAL = "normal"  # 普通战斗
    BOSS_FIGHT = "boss_fight"  # Boss 战
    SWARM = "swarm"  # 大量敌人
    ONE_VS_ONE = "one_vs_one"  # 1v1
    NARROW_SPACE = "narrow_space"  # 狭窄空间
    OPEN_SPACE = "open_space"  # 开阔空间
    HAZARDOUS = "hazardous"  # 危险环境


@dataclass
class AdaptiveConfig:
    """自适应配置"""

    # 场景阈值
    boss_threshold: int = 1  # Boss 数量阈值
    swarm_threshold: int = 5  # 敌人数量阈值（大量）
    narrow_space_threshold: float = 0.3  # 狭窄空间阈值（房间利用率）
    open_space_threshold: float = 0.7  # 开阔空间阈值

    # 性能阈值
    hit_rate_threshold: float = 0.5  # 命中率阈值
    dodge_rate_threshold: float = 0.6  # 闪避率阈值
    damage_threshold: float = 0.3  # 受伤率阈值

    # 调整参数
    aggression_step: float = 0.1  # 攻击性调整步长
    caution_step: float = 0.1  # 谨慎度调整步长


@dataclass
class PerformanceMetrics:
    """性能指标"""

    hit_rate: float = 0.5  # 命中率
    dodge_rate: float = 0.5  # 闪避率
    damage_taken: float = 0.0  # 受伤次数/帧
    enemies_killed: int = 0  # 杀敌数
    time_survived: float = 0.0  # 生存时间
    rooms_cleared: int = 0  # 房间清理数


class ScenarioDetector:
    """场景检测器

    识别当前游戏场景类型。
    """

    def __init__(self, config: AdaptiveConfig = None):
        self.config = config or AdaptiveConfig()

    def detect(self, game_state: GameStateData) -> ScenarioType:
        """检测场景类型

        Args:
            game_state: 当前游戏状态

        Returns:
            场景类型
        """
        # 检查 Boss 战
        boss_count = sum(1 for e in game_state.active_enemies if e.is_boss)
        if boss_count >= self.config.boss_threshold:
            return ScenarioType.BOSS_FIGHT

        # 检查大量敌人
        if len(game_state.active_enemies) >= self.config.swarm_threshold:
            return ScenarioType.SWARM

        # 检查 1v1
        if len(game_state.active_enemies) == 1:
            return ScenarioType.ONE_VS_ONE

        # 检查房间空间
        if game_state.room_layout and game_state.room_info:
            room_info = game_state.room_info
            if room_info.grid_width * room_info.grid_height > 0:
                # 计算房间利用率（简化计算）
                if room_info.grid_width <= 7 and room_info.grid_height <= 4:
                    return ScenarioType.NARROW_SPACE
                elif room_info.grid_width >= 15 and room_info.grid_height >= 10:
                    return ScenarioType.OPEN_SPACE

        # 检查危险环境（有很多投射物）
        if len(game_state.enemy_projectiles) > 3:
            return ScenarioType.HAZARDOUS

        return ScenarioType.NORMAL


class AdaptiveParameterSystem:
    """自适应参数系统

    根据场景和性能动态调整 AI 参数。
    """

    def __init__(self, config: AdaptiveConfig = None):
        self.config = config or AdaptiveConfig()

        # 场景检测器
        self.detector = ScenarioDetector(self.config)

        # 当前状态
        self.current_scenario: ScenarioType = ScenarioType.NORMAL
        self.current_aggression: float = 0.5  # 攻击性 (0-1)
        self.current_caution: float = 0.5  # 谨慎度 (0-1)

        # 性能追踪
        self.metrics = PerformanceMetrics()

        # 历史数据
        self.metrics_history: List[PerformanceMetrics] = []

    def update(
        self,
        game_state: GameStateData,
        performance_metrics: Dict[str, float] = None,
    ) -> Dict[str, float]:
        """更新系统状态，返回调整后的参数

        Args:
            game_state: 当前游戏状态
            performance_metrics: 性能指标（可选）

        Returns:
            调整后的参数
        """
        # 更新性能指标
        if performance_metrics:
            self._update_metrics(performance_metrics)

        # 检测场景
        self.current_scenario = self.detector.detect(game_state)

        # 根据场景调整参数
        self._adjust_for_scenario()

        # 根据性能调整参数
        self._adjust_for_performance()

        # 返回当前参数
        return {
            "aggression": self.current_aggression,
            "caution": self.current_caution,
            "scenario": self.current_scenario.value,
        }

    def _update_metrics(self, metrics: Dict[str, float]):
        """更新性能指标"""
        self.metrics.hit_rate = metrics.get("hit_rate", 0.5)
        self.metrics.dodge_rate = metrics.get("dodge_rate", 0.5)
        self.metrics.damage_taken = metrics.get("damage_taken", 0.0)

        # 保存历史
        self.metrics_history.append(PerformanceMetrics(**metrics))
        if len(self.metrics_history) > 100:
            self.metrics_history.pop(0)

    def _adjust_for_scenario(self):
        """根据场景调整参数"""
        if self.current_scenario == ScenarioType.BOSS_FIGHT:
            # Boss 战：提高谨慎度，降低攻击性
            self.current_aggression = max(0.3, self.current_aggression - 0.1)
            self.current_caution = min(1.0, self.current_caution + 0.2)

        elif self.current_scenario == ScenarioType.SWARM:
            # 大量敌人：提高谨慎度，群体作战
            self.current_caution = min(1.0, self.current_caution + 0.1)

        elif self.current_scenario == ScenarioType.ONE_VS_ONE:
            # 1v1：提高攻击性
            self.current_aggression = min(1.0, self.current_aggression + 0.1)

        elif self.current_scenario == ScenarioType.NARROW_SPACE:
            # 狭窄空间：提高谨慎度
            self.current_caution = min(1.0, self.current_caution + 0.1)

        elif self.current_scenario == ScenarioType.OPEN_SPACE:
            # 开阔空间：可以提高攻击性
            self.current_aggression = min(1.0, self.current_aggression + 0.05)

        elif self.current_scenario == ScenarioType.HAZARDOUS:
            # 危险环境：大幅提高谨慎度
            self.current_caution = min(1.0, self.current_caution + 0.2)

    def _adjust_for_performance(self):
        """根据性能调整参数"""
        if len(self.metrics_history) < 10:
            return

        # 获取最近平均性能
        recent = self.metrics_history[-10:]
        avg_hit_rate = sum(m.hit_rate for m in recent) / len(recent)
        avg_dodge_rate = sum(m.dodge_rate for m in recent) / len(recent)
        avg_damage = sum(m.damage_taken for m in recent) / len(recent)

        # 如果命中率低，降低攻击性
        if avg_hit_rate < self.config.hit_rate_threshold:
            self.current_aggression = max(
                0.2, self.current_aggression - self.config.aggression_step
            )

        # 如果闪避率低，提高谨慎度
        if avg_dodge_rate < self.config.dodge_rate_threshold:
            self.current_caution = min(
                1.0, self.current_caution + self.config.caution_step
            )

        # 如果受伤率高，大幅提高谨慎度
        if avg_damage > self.config.damage_threshold:
            self.current_caution = min(
                1.0, self.current_caution + self.config.caution_step * 2
            )

        # 如果表现很好，可以稍微提高攻击性
        if avg_hit_rate > 0.7 and avg_dodge_rate > 0.8:
            self.current_aggression = min(
                0.9, self.current_aggression + self.config.aggression_step
            )

    def get_scenario_config(self) -> Dict[str, Any]:
        """获取场景特定的配置

        Returns:
            针对当前场景调整的配置
        """
        if self.current_scenario == ScenarioType.BOSS_FIGHT:
            return {
                "move_style": "defensive",
                "target_priority": "boss",
                "engage_distance": 300,
                "retreat_on_low_health": True,
            }

        elif self.current_scenario == ScenarioType.SWARM:
            return {
                "move_style": "kiting",
                "target_priority": "nearest",
                "engage_distance": 200,
                "retreat_on_low_health": True,
            }

        elif self.current_scenario == ScenarioType.ONE_VS_ONE:
            return {
                "move_style": "aggressive",
                "target_priority": "only",
                "engage_distance": 100,
                "retreat_on_low_health": False,
            }

        elif self.current_scenario == ScenarioType.NARROW_SPACE:
            return {
                "move_style": "defensive",
                "target_priority": "weakest",
                "engage_distance": 250,
                "retreat_on_low_health": True,
            }

        elif self.current_scenario == ScenarioType.OPEN_SPACE:
            return {
                "move_style": "balanced",
                "target_priority": "nearest",
                "engage_distance": 150,
                "retreat_on_low_health": False,
            }

        return {
            "move_style": "balanced",
            "target_priority": "nearest",
            "engage_distance": 200,
            "retreat_on_low_health": False,
        }

    def reset(self):
        """重置系统状态"""
        self.current_scenario = ScenarioType.NORMAL
        self.current_aggression = 0.5
        self.current_caution = 0.5
        self.metrics = PerformanceMetrics()
        self.metrics_history.clear()


def create_adaptive_system(
    config: AdaptiveConfig = None,
) -> AdaptiveParameterSystem:
    """创建自适应参数系统实例"""
    return AdaptiveParameterSystem(config)
