"""
SocketBridge 动态策略调整系统

基于玩家属性和实际输出能力的动态策略调整：
1. DPS计数和输出能力评估
2. 玩家属性权重计算
3. 动态安全范围调整
4. 行为树权重适配
"""

import time
import math
from typing import Dict, List, Optional, Tuple, Any, Deque
from dataclasses import dataclass, field
from collections import deque, defaultdict
import logging

from models import PlayerData, EnemyData, Vector2D, GameStateData, PlayerStatsData

logger = logging.getLogger("DynamicStrategy")


@dataclass
class DPSMeasurement:
    """DPS测量数据"""

    timestamp: float
    damage_dealt: float
    enemy_id: int
    enemy_type: int
    enemy_hp_before: float
    enemy_hp_after: float

    @property
    def actual_damage(self) -> float:
        """实际造成的伤害"""
        return min(self.damage_dealt, self.enemy_hp_before - self.enemy_hp_after)


@dataclass
class PlayerCapabilityProfile:
    """玩家能力剖面

    基于玩家属性和实际表现评估战斗能力。
    """

    # 基础属性评分 (0-1)
    damage_score: float = 0.0  # 攻击力评分
    range_score: float = 0.0  # 射程评分
    fire_rate_score: float = 0.0  # 射速评分
    mobility_score: float = 0.0  # 机动性评分

    # 实战表现评分
    dps_score: float = 0.0  # 实际DPS评分
    accuracy_score: float = 0.0  # 命中率评分
    survival_score: float = 0.0  # 生存能力评分

    # 综合能力评分
    overall_combat_power: float = 0.0

    # 策略倾向
    aggression_bias: float = 0.5  # 攻击性倾向 (0-1, 0=防御, 1=攻击)
    safety_margin_multiplier: float = 1.0  # 安全范围乘数

    # 时间戳
    last_update_time: float = 0.0


@dataclass
class DPSTracker:
    """DPS跟踪器

    跟踪玩家造成的伤害，计算实际DPS。
    """

    def __init__(self, window_size: int = 60):
        self.window_size = window_size  # 时间窗口大小（帧数）
        self.damage_history: Deque[DPSMeasurement] = deque(maxlen=window_size * 2)

        # 统计信息
        self.total_damage: float = 0.0
        self.total_shots: int = 0
        self.total_hits: int = 0

        # 时间跟踪
        self.start_time: float = time.time()
        self.last_damage_time: float = 0.0

        # 敌人状态缓存（用于计算实际伤害）
        self.enemy_hp_cache: Dict[int, float] = {}

    def update_enemy_state(self, enemy: EnemyData):
        """更新敌人状态缓存"""
        self.enemy_hp_cache[enemy.id] = enemy.hp

    def record_shot(self, player_pos: Vector2D, target_pos: Vector2D):
        """记录射击尝试"""
        self.total_shots += 1

    def record_hit(self, player_pos: Vector2D, target_pos: Vector2D):
        """记录命中"""
        self.total_hits += 1

    def record_damage(
        self, damage_dealt: float, enemy: EnemyData, enemy_before_hp: float = None
    ):
        """记录伤害事件

        Args:
            damage_dealt: 理论伤害值
            enemy: 目标敌人
            enemy_before_hp: 敌人受伤前的血量（如果不提供，则从缓存获取）
        """
        current_time = time.time()

        # 获取受伤前的血量
        if enemy_before_hp is None:
            enemy_before_hp = self.enemy_hp_cache.get(enemy.id, enemy.hp + damage_dealt)

        measurement = DPSMeasurement(
            timestamp=current_time,
            damage_dealt=damage_dealt,
            enemy_id=enemy.id,
            enemy_type=enemy.enemy_type,
            enemy_hp_before=enemy_before_hp,
            enemy_hp_after=enemy.hp,
        )

        self.damage_history.append(measurement)
        self.total_damage += measurement.actual_damage
        self.last_damage_time = current_time

        # 更新敌人缓存
        self.enemy_hp_cache[enemy.id] = enemy.hp

    def get_current_dps(self, window_seconds: float = 5.0) -> float:
        """获取当前DPS（指定时间窗口内的平均伤害/秒）

        Args:
            window_seconds: 时间窗口（秒）

        Returns:
            当前DPS
        """
        if not self.damage_history:
            return 0.0

        current_time = time.time()
        window_start = current_time - window_seconds

        # 计算时间窗口内的总伤害
        total_damage = 0.0
        count = 0

        for measurement in reversed(self.damage_history):
            if measurement.timestamp < window_start:
                break
            total_damage += measurement.actual_damage
            count += 1

        if count == 0:
            return 0.0

        # 计算实际时间窗口（可能小于请求的窗口）
        actual_window = min(
            window_seconds, current_time - self.damage_history[0].timestamp
        )
        if actual_window <= 0:
            return 0.0

        return total_damage / actual_window

    def get_accuracy_rate(self) -> float:
        """获取命中率

        Returns:
            命中率 (0-1)
        """
        if self.total_shots == 0:
            return 0.0
        return self.total_hits / self.total_shots

    def get_average_damage_per_hit(self) -> float:
        """获取平均每击伤害

        Returns:
            平均每击伤害
        """
        if self.total_hits == 0:
            return 0.0
        return self.total_damage / self.total_hits

    def reset(self):
        """重置跟踪器"""
        self.damage_history.clear()
        self.enemy_hp_cache.clear()
        self.total_damage = 0.0
        self.total_shots = 0
        self.total_hits = 0
        self.start_time = time.time()
        self.last_damage_time = 0.0


class PlayerCapabilityAnalyzer:
    """玩家能力分析器

    分析玩家属性和实战表现，生成能力剖面。
    """

    # 属性基准值（以游戏初始值为基准）
    BASE_DAMAGE = 3.0
    BASE_TEAR_RANGE = 300.0
    BASE_TEARS = 10.0  # 泪弹发射延迟（越低越快）
    BASE_SPEED = 1.0

    # 最大合理值（防止无限增长）
    MAX_DAMAGE = 50.0
    MAX_TEAR_RANGE = 600.0
    MIN_TEARS = 1.0  # 最高射速
    MAX_SPEED = 2.0

    def __init__(self):
        self.dps_tracker = DPSTracker()
        self.capability_profile = PlayerCapabilityProfile()

    def update_player_stats(
        self, player: PlayerData, player_stats: Optional[PlayerStatsData] = None
    ):
        """更新玩家属性评分

        优先使用 PlayerStatsData（来自 PLAYER_STATS 通道）的属性，
        如果不存在则回退到 PlayerData 中的属性。

        Args:
            player: 玩家位置数据
            player_stats: 玩家属性数据（可选）
        """
        # 确定使用哪个数据源
        stats = player_stats or player

        # 计算属性评分 (0-1)
        damage_norm = min(stats.damage / self.MAX_DAMAGE, 1.0)
        range_norm = min(stats.tear_range / self.MAX_TEAR_RANGE, 1.0)

        # 射速评分（泪弹延迟越低，射速越高）
        fire_rate = self.BASE_TEARS / max(stats.tears, self.MIN_TEARS)
        fire_rate_norm = min(fire_rate / (self.BASE_TEARS / self.MIN_TEARS), 1.0)

        # 机动性评分
        speed_norm = min(stats.speed / self.MAX_SPEED, 1.0)
        if stats.can_fly:
            speed_norm = min(speed_norm * 1.5, 1.0)

        # 更新能力剖面
        self.capability_profile.damage_score = damage_norm
        self.capability_profile.range_score = range_norm
        self.capability_profile.fire_rate_score = fire_rate_norm
        self.capability_profile.mobility_score = speed_norm

        # 更新实战表现评分
        self._update_performance_scores()

        # 计算综合战斗能力
        self._update_overall_combat_power()

        # 更新策略倾向
        self._update_strategy_bias()

        self.capability_profile.last_update_time = time.time()

    def _update_performance_scores(self):
        """更新实战表现评分"""
        # DPS评分（基于当前DPS与理论最大DPS的比值）
        current_dps = self.dps_tracker.get_current_dps()

        # 理论DPS = 伤害 * 射速（简化计算）
        theoretical_dps = (
            self.capability_profile.damage_score
            * self.capability_profile.fire_rate_score
            * 10.0  # 基准缩放因子
        )

        if theoretical_dps > 0:
            self.capability_profile.dps_score = min(current_dps / theoretical_dps, 1.0)
        else:
            self.capability_profile.dps_score = 0.0

        # 命中率评分
        self.capability_profile.accuracy_score = self.dps_tracker.get_accuracy_rate()

        # 生存能力评分（基于最近的伤害事件时间）
        time_since_last_damage = time.time() - self.dps_tracker.last_damage_time
        # 每10秒无伤增加0.1生存评分，最高1.0
        survival_bonus = min(time_since_last_damage / 100.0, 1.0)
        self.capability_profile.survival_score = survival_bonus

    def _update_overall_combat_power(self):
        """计算综合战斗能力评分"""
        # 权重配置
        weights = {
            "damage": 0.25,
            "range": 0.15,
            "fire_rate": 0.20,
            "mobility": 0.10,
            "dps": 0.20,
            "accuracy": 0.10,
        }

        overall_score = (
            self.capability_profile.damage_score * weights["damage"]
            + self.capability_profile.range_score * weights["range"]
            + self.capability_profile.fire_rate_score * weights["fire_rate"]
            + self.capability_profile.mobility_score * weights["mobility"]
            + self.capability_profile.dps_score * weights["dps"]
            + self.capability_profile.accuracy_score * weights["accuracy"]
        )

        self.capability_profile.overall_combat_power = min(overall_score, 1.0)

    def _update_strategy_bias(self):
        """更新策略倾向"""
        # 基础倾向：战斗能力越强，攻击性越高
        base_aggression = self.capability_profile.overall_combat_power

        # 调整因子：
        # 1. 高射程 -> 更安全 -> 可以更激进
        range_bonus = self.capability_profile.range_score * 0.3

        # 2. 高机动性 -> 更容易躲避 -> 可以更激进
        mobility_bonus = self.capability_profile.mobility_score * 0.2

        # 3. 低生存评分 -> 需要更保守
        survival_penalty = (1.0 - self.capability_profile.survival_score) * 0.2

        aggression = base_aggression + range_bonus + mobility_bonus - survival_penalty
        aggression = max(0.0, min(1.0, aggression))

        self.capability_profile.aggression_bias = aggression

        # 安全范围乘数：能力越强，安全范围可以越小
        # 机动性越高，安全范围可以越小（更容易躲避）
        # 基础安全范围：1.0（100%）
        # 综合能力评分 + 机动性评分影响，最低到0.5（50%）
        safety_multiplier = 1.0 - (
            self.capability_profile.overall_combat_power * 0.25
            + self.capability_profile.mobility_score * 0.15
        )
        self.capability_profile.safety_margin_multiplier = max(
            0.5, min(1.0, safety_multiplier)
        )

    def record_combat_event(self, event_type: str, **kwargs):
        """记录战斗事件"""
        if event_type == "shot":
            self.dps_tracker.record_shot(
                kwargs.get("player_pos"), kwargs.get("target_pos")
            )
        elif event_type == "hit":
            self.dps_tracker.record_hit(
                kwargs.get("player_pos"), kwargs.get("target_pos")
            )
        elif event_type == "damage":
            self.dps_tracker.record_damage(
                kwargs.get("damage_dealt"),
                kwargs.get("enemy"),
                kwargs.get("enemy_before_hp"),
            )

    def update_enemy_state(self, enemy: EnemyData):
        """更新敌人状态（用于伤害计算）"""
        self.dps_tracker.update_enemy_state(enemy)

    def get_recommended_combat_distance(self, base_distance: float = 150.0) -> float:
        """获取推荐的战斗距离

        Args:
            base_distance: 基础战斗距离

        Returns:
            调整后的战斗距离
        """
        # 射程因子：射程越长，理想战斗距离可以越远
        range_factor = 1.0 + (self.capability_profile.range_score * 0.5)

        # 机动性因子：机动性越高，战斗距离可以越近（更容易躲避）
        # 飞行能力已包含在机动性评分中，会进一步减少安全距离
        mobility_factor = 1.0 - (self.capability_profile.mobility_score * 0.3)

        # 安全因子：根据安全范围乘数调整
        safety_factor = self.capability_profile.safety_margin_multiplier

        # 综合调整
        adjusted_distance = (
            base_distance * range_factor * mobility_factor * safety_factor
        )

        # 限制范围：最小100，最大400
        return max(100.0, min(400.0, adjusted_distance))

    def get_strategy_adjustments(self) -> Dict[str, float]:
        """获取策略调整参数

        Returns:
            策略调整参数字典
        """
        return {
            "aggression_bias": self.capability_profile.aggression_bias,
            "safety_multiplier": self.capability_profile.safety_margin_multiplier,
            "combat_power": self.capability_profile.overall_combat_power,
            "recommended_combat_distance": self.get_recommended_combat_distance(),
            "damage_score": self.capability_profile.damage_score,
            "range_score": self.capability_profile.range_score,
            "fire_rate_score": self.capability_profile.fire_rate_score,
            "mobility_score": self.capability_profile.mobility_score,
        }

    def reset(self):
        """重置分析器"""
        self.dps_tracker.reset()
        self.capability_profile = PlayerCapabilityProfile()


class DynamicStrategyAdapter:
    """动态策略适配器

    将玩家能力分析结果应用到行为树和决策系统。
    """

    def __init__(self):
        self.capability_analyzer = PlayerCapabilityAnalyzer()
        self.last_adjustment_time: float = 0.0
        self.adjustment_interval: float = 1.0  # 调整间隔（秒）

    def update(self, player: PlayerData, game_state: GameStateData) -> Dict[str, float]:
        """更新策略适配器

        Args:
            player: 玩家数据
            game_state: 游戏状态（包含 player_stats）

        Returns:
            策略调整参数
        """
        current_time = time.time()

        # 更新敌人状态缓存
        for enemy in game_state.enemies.values():
            self.capability_analyzer.update_enemy_state(enemy)

        # 定期更新玩家能力分析
        if current_time - self.last_adjustment_time >= self.adjustment_interval:
            # 从 game_state 获取 player_stats（来自 PLAYER_STATS 通道）
            player_stats = game_state.get_primary_player_stats()
            self.capability_analyzer.update_player_stats(player, player_stats)
            self.last_adjustment_time = current_time

        return self.capability_analyzer.get_strategy_adjustments()

    def record_combat_event(self, event_type: str, **kwargs):
        """记录战斗事件"""
        self.capability_analyzer.record_combat_event(event_type, **kwargs)

    def apply_to_behavior_tree(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """将策略调整应用到行为树上下文

        Args:
            context: 行为树上下文

        Returns:
            更新后的上下文
        """
        adjustments = self.capability_analyzer.get_strategy_adjustments()

        # 在上下文中添加能力评分
        if "debug_info" not in context:
            context["debug_info"] = {}

        context["debug_info"]["player_capability"] = {
            "combat_power": adjustments["combat_power"],
            "aggression_bias": adjustments["aggression_bias"],
            "recommended_distance": adjustments["recommended_combat_distance"],
        }

        # 调整条件检查的阈值
        # 例如：攻击性倾向越高，触发攻击行为的条件越宽松
        if "condition_thresholds" not in context:
            context["condition_thresholds"] = {}

        aggression = adjustments["aggression_bias"]

        # 攻击条件阈值：攻击性越高，阈值越低（更容易攻击）
        context["condition_thresholds"]["attack_distance"] = 200.0 * (
            1.0 - aggression * 0.3
        )
        context["condition_thresholds"]["attack_confidence"] = 0.5 * (
            1.0 - aggression * 0.3
        )

        # 逃跑条件阈值：攻击性越低，阈值越高（更容易逃跑）
        context["condition_thresholds"]["flee_health"] = 0.3 + (aggression * 0.2)
        context["condition_thresholds"]["flee_enemy_count"] = 3 + int(aggression * 3)

        return context

    def get_ai_config_adjustments(self, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """获取AI配置调整

        Args:
            base_config: 基础AI配置

        Returns:
             调整后的配置
        """
        adjustments = self.capability_analyzer.get_strategy_adjustments()

        config_updates = {}

        # 获取动态权重配置，使用默认值如果不存在
        dynamic_weights = base_config.get("dynamic_weights", {})
        fire_rate_factor = dynamic_weights.get("fire_rate_factor", 0.5)
        mobility_threshold_high = dynamic_weights.get("mobility_threshold_high", 0.7)
        mobility_threshold_low = dynamic_weights.get("mobility_threshold_low", 0.3)

        # 调整战斗距离
        if "combat_distance" in base_config:
            config_updates["combat_distance"] = adjustments[
                "recommended_combat_distance"
            ]

        # 调整攻击频率（基于射速评分）
        if "aim_interval" in base_config:
            base_interval = base_config["aim_interval"]
            fire_rate = adjustments["fire_rate_score"]
            # 射速越高，瞄准间隔应该越小（射击更频繁），使用可配置因子
            new_interval = max(
                1, int(base_interval * (1.0 - fire_rate * fire_rate_factor))
            )
            config_updates["aim_interval"] = new_interval

        # 调整移动速度（基于机动性评分）
        if "movement_mode" in base_config:
            mobility = adjustments["mobility_score"]
            if mobility > mobility_threshold_high:
                config_updates["movement_mode"] = "aggressive"
            elif mobility < mobility_threshold_low:
                config_updates["movement_mode"] = "defensive"
            else:
                config_updates["movement_mode"] = "balanced"

        return config_updates

    def reset(self):
        """重置适配器"""
        self.capability_analyzer.reset()
        self.last_adjustment_time = 0.0


def create_dynamic_strategy_adapter() -> DynamicStrategyAdapter:
    """创建动态策略适配器实例"""
    return DynamicStrategyAdapter()
