"""
SocketBridge 策略系统模块

实现多策略评估和选择系统。
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

from models import Vector2D, GameStateData, PlayerData, EnemyData, PlayerStatsData

logger = logging.getLogger("StrategySystem")


class StrategyType(Enum):
    """策略类型"""

    AGGRESSIVE = "aggressive"  # 激进：高攻击性
    DEFENSIVE = "defensive"  # 防御优先
    BALANCED = "balanced"  # 攻守平衡
    EVASIVE = "evasive"  # 闪避优先
    HEALING = "healing"  # 治疗优先


@dataclass
class StrategyEvaluation:
    """策略评估结果"""

    strategy: StrategyType
    utility_score: float  # 效用分数 (0-1)
    factors: Dict[str, float] = field(default_factory=dict)  # 评估因素
    recommended_distance: float = 200.0  # 推荐距离
    move_speed_modifier: float = 1.0  # 移动速度修正
    attack_rate_modifier: float = 1.0  # 攻击频率修正


@dataclass
class GameContext:
    """游戏上下文"""

    player_health: float = 1.0
    enemy_count: int = 0
    nearest_enemy_distance: float = 9999.0
    highest_threat_level: float = 0.0
    in_combat: bool = False
    can_heal: bool = False
    has_active_projectiles: bool = False
    room_clear_percent: float = 0.0

    # 玩家属性数据（来自 PLAYER_STATS 通道，独立更新）
    player_stats: Optional[PlayerStatsData] = None


class StrategyManager:
    """策略管理器

    评估和选择最佳策略。
    """

    # 默认权重配置
    DEFAULT_WEIGHTS = {
        "health_weight": 0.3,
        "threat_weight": 0.25,
        "enemy_count_weight": 0.2,
        "distance_weight": 0.15,
        "heal_availability_weight": 0.1,
    }

    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or dict(self.DEFAULT_WEIGHTS)

        # 策略评估器
        self.evaluators: Dict[StrategyType, callable] = {}

        # 注册默认评估器
        self._register_default_evaluators()

        # 当前策略
        self.current_strategy: StrategyType = StrategyType.BALANCED
        self.strategy_history: List[StrategyType] = []

    def _register_default_evaluators(self):
        """注册默认评估器"""

        def evaluate_aggressive(context: GameContext) -> StrategyEvaluation:
            score = 0.5
            factors = {}

            # 血量高时激进
            if context.player_health > 0.7:
                score += 0.3
                factors["high_health_bonus"] = 0.3

            # 敌人少时激进
            if context.enemy_count < 3:
                score += 0.1
                factors["few_enemies_bonus"] = 0.1

            # 威胁低时激进
            if context.highest_threat_level < 0.3:
                score += 0.1
                factors["low_threat_bonus"] = 0.1

            return StrategyEvaluation(
                strategy=StrategyType.AGGRESSIVE,
                utility_score=min(1.0, score),
                factors=factors,
                recommended_distance=100.0,
                move_speed_modifier=1.2,
                attack_rate_modifier=1.3,
            )

        def evaluate_defensive(context: GameContext) -> StrategyEvaluation:
            score = 0.5
            factors = {}

            # 敌人多时防御
            if context.enemy_count > 3:
                score += 0.2
                factors["many_enemies_bonus"] = 0.2

            # 有投射物时防御
            if context.has_active_projectiles:
                score += 0.2
                factors["projectiles_bonus"] = 0.2

            # 威胁高时防御
            if context.highest_threat_level > 0.5:
                score += 0.2
                factors["high_threat_bonus"] = 0.2

            return StrategyEvaluation(
                strategy=StrategyType.DEFENSIVE,
                utility_score=min(1.0, score),
                factors=factors,
                recommended_distance=250.0,
                move_speed_modifier=0.9,
                attack_rate_modifier=0.8,
            )

        def evaluate_evasive(context: GameContext) -> StrategyEvaluation:
            score = 0.3
            factors = {}

            # 血量低时闪避
            if context.player_health < 0.3:
                score += 0.4
                factors["low_health_bonus"] = 0.4

            # 有投射物时闪避
            if context.has_active_projectiles:
                score += 0.3
                factors["projectiles_bonus"] = 0.3

            # 高威胁时闪避
            if context.highest_threat_level > 0.7:
                score += 0.3
                factors["critical_threat_bonus"] = 0.3

            return StrategyEvaluation(
                strategy=StrategyType.EVASIVE,
                utility_score=min(1.0, score),
                factors=factors,
                recommended_distance=300.0,
                move_speed_modifier=1.1,
                attack_rate_modifier=0.5,
            )

        def evaluate_healing(context: GameContext) -> StrategyEvaluation:
            score = 0.2
            factors = {}

            # 血量低且可治疗时
            if context.player_health < 0.5 and context.can_heal:
                score += 0.5
                factors["heal_opportunity_bonus"] = 0.5

            # 血量极低时
            if context.player_health < 0.25:
                score += 0.3
                factors["critical_health_bonus"] = 0.3

            return StrategyEvaluation(
                strategy=StrategyType.HEALING,
                utility_score=min(1.0, score),
                factors=factors,
                recommended_distance=200.0,
                move_speed_modifier=0.7,
                attack_rate_modifier=0.3,
            )

        def evaluate_balanced(context: GameContext) -> StrategyEvaluation:
            # 平衡策略的分数取决于当前情况的平均
            base_score = 0.5

            # 根据情况调整
            if context.player_health > 0.5:
                base_score += 0.1
            if context.enemy_count > 0:
                base_score += 0.1

            return StrategyEvaluation(
                strategy=StrategyType.BALANCED,
                utility_score=base_score,
                factors={},
                recommended_distance=180.0,
                move_speed_modifier=1.0,
                attack_rate_modifier=1.0,
            )

        self.evaluators[StrategyType.AGGRESSIVE] = evaluate_aggressive
        self.evaluators[StrategyType.DEFENSIVE] = evaluate_defensive
        self.evaluators[StrategyType.EVASIVE] = evaluate_evasive
        self.evaluators[StrategyType.HEALING] = evaluate_healing
        self.evaluators[StrategyType.BALANCED] = evaluate_balanced

    def evaluate_all(
        self, context: GameContext
    ) -> Dict[StrategyType, StrategyEvaluation]:
        """评估所有策略

        Args:
            context: 游戏上下文

        Returns:
            各策略的评估结果
        """
        results = {}
        for strategy_type, evaluator in self.evaluators.items():
            results[strategy_type] = evaluator(context)
        return results

    def select_best(
        self, context: GameContext
    ) -> Tuple[StrategyType, StrategyEvaluation]:
        """选择最佳策略

        Args:
            context: 游戏上下文

        Returns:
            (最佳策略, 评估结果)
        """
        evaluations = self.evaluate_all(context)

        # 选择效用分数最高的策略
        best_strategy = StrategyType.BALANCED
        best_evaluation = evaluations[StrategyType.BALANCED]

        for strategy_type, evaluation in evaluations.items():
            if evaluation.utility_score > best_evaluation.utility_score:
                best_strategy = strategy_type
                best_evaluation = evaluation

        # 策略切换冷却（避免频繁切换）
        if self.strategy_history and self.strategy_history[-1] != best_strategy:
            # 检查是否频繁切换
            if (
                len(self.strategy_history) >= 3
                and self.strategy_history[-3] == best_strategy
            ):
                # 回到之前的策略（避免抖动）
                return (
                    self.strategy_history[-1],
                    evaluations[self.strategy_history[-1]],
                )

        self.strategy_history.append(best_strategy)
        if len(self.strategy_history) > 10:
            self.strategy_history.pop(0)

        self.current_strategy = best_strategy
        return (best_strategy, best_evaluation)

    def get_current_strategy(self) -> StrategyType:
        """获取当前策略"""
        return self.current_strategy

    def build_context(
        self, game_state: GameStateData, threat_level: float = 0.0
    ) -> GameContext:
        """从游戏状态构建上下文

        Args:
            game_state: 游戏状态
            threat_level: 威胁等级 (0-1)

        Returns:
            游戏上下文
        """
        player = game_state.get_primary_player()

        context = GameContext()
        context.enemy_count = len(game_state.active_enemies)
        context.has_active_projectiles = len(game_state.enemy_projectiles) > 0
        context.highest_threat_level = threat_level

        if player:
            context.player_health = game_state.get_primary_player_health_ratio()
            context.nearest_enemy_distance = (
                game_state.get_nearest_enemy(player.position).position.distance_to(
                    player.position
                )
                if game_state.get_nearest_enemy(player.position)
                else 9999.0
            )

        # 从 PLAYER_STATS 通道获取玩家属性数据
        if player:
            context.player_stats = game_state.player_stats.get(player.player_idx)

        context.in_combat = context.enemy_count > 0

        return context

    def reset(self):
        """重置策略管理器"""
        self.current_strategy = StrategyType.BALANCED
        self.strategy_history.clear()


def create_strategy_manager(
    weights: Dict[str, float] = None,
) -> StrategyManager:
    """创建策略管理器实例"""
    return StrategyManager(weights)
