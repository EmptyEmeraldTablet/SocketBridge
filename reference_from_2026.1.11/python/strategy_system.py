"""
策略决策系统

实现多策略评估和效用计算：
- 策略效用函数
- 多目标优化
- 风险收益权衡
- 策略选择和切换

根据 reference.md 第三阶段设计。
"""

import math
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger("StrategySystem")


class StrategyType(Enum):
    """策略类型"""

    AGGRESSIVE = "aggressive"  # 激进
    DEFENSIVE = "defensive"  # 防御
    BALANCED = "balanced"  # 平衡
    EVASIVE = "evasive"  # 闪避
    HEALING = "healing"  # 治疗


@dataclass
class StrategyWeights:
    """策略权重配置"""

    # 核心权重
    safety_weight: float = 0.3  # 安全性权重
    damage_output_weight: float = 0.25  # 输出权重
    resource_efficiency_weight: float = 0.2  # 资源效率权重
    positioning_weight: float = 0.15  # 位置权重
    objective_weight: float = 0.1  # 目标权重

    # 风险偏好
    risk_tolerance: float = 0.5  # 风险容忍度 (0-1)
    conservative_threshold: float = 0.3  # 保守阈值


@dataclass
class StrategyEvaluation:
    """策略评估结果"""

    strategy_type: StrategyType
    utility_score: float = 0.0

    # 分项得分
    safety_score: float = 0.0
    damage_score: float = 0.0
    efficiency_score: float = 0.0
    positioning_score: float = 0.0
    objective_score: float = 0.0

    # 风险评估
    risk_level: float = 0.0
    expected_value: float = 0.0
    variance: float = 0.0

    # 详细信息
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class GameContext:
    """游戏上下文"""

    # 玩家状态
    player_health: float = 1.0
    player_position_x: float = 0.0
    player_position_y: float = 0.0

    # 战斗状态
    enemy_count: int = 0
    nearest_enemy_distance: float = 9999.0
    highest_threat_level: float = 0.0

    # 资源
    has_healing: bool = False
    has_bombs: bool = False
    has_key: bool = False

    # 环境
    room_cleared: bool = False
    room_center_x: float = 0.0
    room_center_y: float = 0.0

    # 战斗状态
    in_combat: bool = False
    projectiles_incoming: int = 0


class StrategyEvaluator:
    """策略评估器

    计算各策略的效用值。
    """

    def __init__(self, weights: StrategyWeights = None):
        self.weights = weights or StrategyWeights()

    def evaluate_strategy(
        self, strategy: StrategyType, context: GameContext
    ) -> StrategyEvaluation:
        """
        评估策略

        Args:
            strategy: 策略类型
            context: 游戏上下文

        Returns:
            策略评估结果
        """
        eval_result = StrategyEvaluation(strategy_type=strategy)

        # 根据策略类型计算各项得分
        if strategy == StrategyType.AGGRESSIVE:
            self._evaluate_aggressive(eval_result, context)
        elif strategy == StrategyType.DEFENSIVE:
            self._evaluate_defensive(eval_result, context)
        elif strategy == StrategyType.BALANCED:
            self._evaluate_balanced(eval_result, context)
        elif strategy == StrategyType.EVASIVE:
            self._evaluate_evasive(eval_result, context)
        elif strategy == StrategyType.HEALING:
            self._evaluate_healing(eval_result, context)

        # 计算加权效用值
        eval_result.utility_score = self._calculate_utility(eval_result)

        # 评估风险
        self._evaluate_risk(eval_result, context)

        # 生成建议
        eval_result.recommendation = self._generate_recommendation(eval_result)

        return eval_result

    def _evaluate_aggressive(self, eval: StrategyEvaluation, context: GameContext):
        """评估激进策略"""
        # 高伤害输出
        eval.damage_score = 1.0 - min(1.0, context.nearest_enemy_distance / 500)
        eval.damage_score *= 1.5  # 激进策略加成

        # 低安全性
        eval.safety_score = max(0, 1.0 - context.highest_threat_level)
        eval.safety_score *= 0.5  # 激进策略降低安全性

        # 高风险高回报
        eval.efficiency_score = 0.8
        eval.positioning_score = 0.7

        # 目标优先
        eval.objective_score = 1.0 if context.in_combat else 0.3

        # 优缺点
        eval.pros = ["高伤害输出", "快速清除敌人", "压制敌人行动"]
        eval.cons = ["暴露在危险中", "容易受到攻击", "资源消耗快"]

    def _evaluate_defensive(self, eval: StrategyEvaluation, context: GameContext):
        """评估防御策略"""
        # 高安全性
        eval.safety_score = 1.0 - min(1.0, context.highest_threat_level)
        eval.safety_score *= 1.2  # 防御策略加成

        # 低伤害输出
        eval.damage_score = 0.5 - min(0.5, context.nearest_enemy_distance / 500)

        # 高效率
        eval.efficiency_score = 0.9
        eval.positioning_score = 0.8

        # 保持距离
        eval.objective_score = 0.6

        eval.pros = ["安全位置选择", "减少受到的伤害", "稳定的战斗节奏"]
        eval.cons = ["清除敌人较慢", "可能错过攻击机会", "被动应战"]

    def _evaluate_balanced(self, eval: StrategyEvaluation, context: GameContext):
        """评估平衡策略"""
        # 均衡各项
        base_safety = 1.0 - min(1.0, context.highest_threat_level)
        base_damage = 1.0 - min(1.0, context.nearest_enemy_distance / 500)

        eval.safety_score = base_safety * 0.9
        eval.damage_score = base_damage * 0.9
        eval.efficiency_score = 0.85
        eval.positioning_score = 0.85
        eval.objective_score = 0.8

        eval.pros = ["攻守平衡", "适应性强", "资源管理好"]
        eval.cons = ["没有明显优势", "特殊情况下表现一般"]

    def _evaluate_evasive(self, eval: StrategyEvaluation, context: GameContext):
        """评估闪避策略"""
        # 最高安全性
        eval.safety_score = 1.0 - min(1.0, context.highest_threat_level)
        if context.projectiles_incoming > 0:
            eval.safety_score *= 1.3  # 有投射物时更注重闪避

        # 最低伤害
        eval.damage_score = 0.2
        eval.efficiency_score = 0.4

        # 移动优先
        eval.positioning_score = 1.0

        # 目标优先级低
        eval.objective_score = 0.2

        eval.pros = ["最大程度避免伤害", "生存能力强", "适合危险情况"]
        eval.cons = ["几乎不造成伤害", "被动挨打", "可能陷入困境"]

    def _evaluate_healing(self, eval: StrategyEvaluation, context: GameContext):
        """评估治疗策略"""
        if context.player_health > 0.5:
            # 满血时不需要治疗
            eval.safety_score = 0.3
            eval.damage_score = 0.3
            eval.efficiency_score = 0.2
            eval.pros = []
            eval.cons = ["不需要治疗"]
        else:
            # 低血量时治疗优先
            eval.safety_score = 0.5
            eval.damage_score = 0.1
            eval.efficiency_score = 0.6

            if context.has_healing:
                eval.safety_score = 1.0
                eval.pros = ["恢复生命值", "提高生存率", "为后续战斗做准备"]
            else:
                eval.pros = ["寻找治疗机会"]

            eval.cons = ["停止攻击", "可能被敌人追击"]

    def _calculate_utility(self, eval: StrategyEvaluation) -> float:
        """计算加权效用值"""
        return (
            eval.safety_score * self.weights.safety_weight
            + eval.damage_score * self.weights.damage_output_weight
            + eval.efficiency_score * self.weights.resource_efficiency_weight
            + eval.positioning_score * self.weights.positioning_weight
            + eval.objective_score * self.weights.objective_weight
        )

    def _evaluate_risk(self, eval: StrategyEvaluation, context: GameContext):
        """评估策略风险"""
        # 基于安全性得分计算风险
        eval.risk_level = max(0, 1.0 - eval.safety_score)

        # 应用风险容忍度调整
        if self.weights.risk_tolerance < 0.5:
            # 保守玩家，风险更低
            eval.risk_level *= 0.5 + self.weights.risk_tolerance

        # 计算期望值（考虑风险调整后的效用）
        eval.expected_value = eval.utility_score * (1.0 - eval.risk_level * 0.5)

        # 方差（不确定性）
        eval.variance = eval.risk_level * 0.2

    def _generate_recommendation(self, eval: StrategyEvaluation) -> str:
        """生成策略建议"""
        if eval.utility_score > 0.8:
            return f"强烈推荐 {eval.strategy_type.value} 策略"
        elif eval.utility_score > 0.6:
            return f"推荐使用 {eval.strategy_type.value} 策略"
        elif eval.utility_score > 0.4:
            return f"可以考虑 {eval.strategy_type.value} 策略"
        else:
            return f"不建议使用 {eval.strategy_type.value} 策略"


class StrategyDecider:
    """策略决策器

    管理策略选择和切换。
    """

    def __init__(self, weights: StrategyWeights = None):
        self.weights = weights or StrategyWeights()
        self.evaluator = StrategyEvaluator(weights)

        # 当前策略
        self.current_strategy: Optional[StrategyType] = None
        self.current_evaluation: Optional[StrategyEvaluation] = None

        # 策略历史
        self.strategy_history: List[Tuple[StrategyType, float]] = []  # (策略, 时间戳)
        self.strategy_durations: Dict[StrategyType, float] = {}  # 各策略累计时间

        # 切换规则
        self.min_strategy_duration: float = 2.0  # 最小策略持续时间
        self.last_switch_time: float = 0

        # 性能追踪
        self.decision_count = 0
        self.successful_decisions = 0

    def evaluate_all_strategies(
        self, context: GameContext
    ) -> Dict[StrategyType, StrategyEvaluation]:
        """评估所有可用策略"""
        evaluations = {}

        for strategy in StrategyType:
            # 根据上下文过滤不可用策略
            if not self._is_strategy_available(strategy, context):
                continue

            eval_result = self.evaluator.evaluate_strategy(strategy, context)
            evaluations[strategy] = eval_result

        return evaluations

    def _is_strategy_available(
        self, strategy: StrategyType, context: GameContext
    ) -> bool:
        """检查策略是否可用"""
        if strategy == StrategyType.HEALING:
            return context.has_healing or context.player_health < 0.5
        return True

    def select_best_strategy(
        self, context: GameContext
    ) -> Tuple[StrategyType, StrategyEvaluation]:
        """
        选择最佳策略

        Returns:
            (最佳策略, 评估结果)
        """
        self.decision_count += 1

        evaluations = self.evaluate_all_strategies(context)

        if not evaluations:
            # 默认使用平衡策略
            default = StrategyType.BALANCED
            eval_result = self.evaluator.evaluate_strategy(default, context)
            self._apply_strategy(default, eval_result)
            return default, eval_result

        # 选择效用最高的策略
        best_strategy = max(
            evaluations.keys(), key=lambda s: evaluations[s].utility_score
        )
        best_evaluation = evaluations[best_strategy]

        # 检查是否需要切换策略
        if self._should_switch_strategy(best_strategy, best_evaluation, context):
            self._apply_strategy(best_strategy, best_evaluation)
        else:
            # 保持当前策略
            best_evaluation = self.current_evaluation

        return self.current_strategy, best_evaluation

    def _should_switch_strategy(
        self,
        candidate: StrategyType,
        evaluation: StrategyEvaluation,
        context: GameContext,
    ) -> bool:
        """判断是否应该切换策略"""
        # 检查最小持续时间
        time_since_switch = self._get_time_since_switch()
        if time_since_switch < self.min_strategy_duration:
            return False

        # 如果当前策略效用太低，切换
        if self.current_strategy and self.current_evaluation:
            if evaluation.utility_score > self.current_evaluation.utility_score + 0.1:
                return True

        # 紧急情况强制切换
        if context.player_health < 0.2:
            if candidate != StrategyType.HEALING and candidate != StrategyType.EVASIVE:
                return True

        # 如果候选策略明显更好
        return evaluation.utility_score > 0.7

    def _apply_strategy(self, strategy: StrategyType, evaluation: StrategyEvaluation):
        """应用策略"""
        self.current_strategy = strategy
        self.current_evaluation = evaluation

        # 记录历史
        self.strategy_history.append((strategy, self._get_time_since_switch()))

        # 记录切换
        self.last_switch_time = __import__("time").time()

        logger.debug(
            f"Strategy switched to {strategy.value} (utility: {evaluation.utility_score:.2f})"
        )

    def _get_time_since_switch(self) -> float:
        """获取上次切换后的时间"""
        return __import__("time").time() - self.last_switch_time

    def record_outcome(self, success: bool):
        """记录决策结果"""
        if success:
            self.successful_decisions += 1

    def get_success_rate(self) -> float:
        """获取成功率"""
        if self.decision_count == 0:
            return 0.0
        return self.successful_decisions / self.decision_count

    def get_strategy_stats(self) -> Dict[str, Any]:
        """获取策略统计"""
        return {
            "current_strategy": self.current_strategy.value
            if self.current_strategy
            else None,
            "total_decisions": self.decision_count,
            "success_rate": self.get_success_rate(),
            "strategy_history": [(s.value, t) for s, t in self.strategy_history[-10:]],
            "evaluations": {
                s.value: {
                    "utility": e.utility_score,
                    "safety": e.safety_score,
                    "damage": e.damage_score,
                }
                for s, e in self.evaluate_all_strategies(GameContext()).items()
            }
            if self.current_evaluation
            else {},
        }

    def adapt_weights(self, performance_metrics: Dict[str, float]):
        """
        根据性能指标调整权重

        Args:
            performance_metrics: {metric_name: value}
                - hit_rate: 命中率 (0-1)
                - dodge_rate: 躲避率 (0-1)
                - damage_taken: 受到的伤害
                - damage_dealt: 造成的伤害
        """
        # 如果命中率低，增加安全性权重
        hit_rate = performance_metrics.get("hit_rate", 0.5)
        if hit_rate < 0.3:
            self.weights.safety_weight = min(0.5, self.weights.safety_weight + 0.05)
            self.weights.damage_output_weight = max(
                0.15, self.weights.damage_output_weight - 0.05
            )

        # 如果躲避率低，增加闪避权重
        dodge_rate = performance_metrics.get("dodge_rate", 0.5)
        if dodge_rate < 0.4:
            self.weights.safety_weight = min(0.5, self.weights.safety_weight + 0.05)

        # 资源消耗快，降低攻击频率
        damage_taken = performance_metrics.get("damage_taken", 0)
        if damage_taken > 2.0:
            self.weights.risk_tolerance = max(0.2, self.weights.risk_tolerance - 0.1)

        logger.debug(
            f"Adapted weights: safety={self.weights.safety_weight:.2f}, "
            f"damage={self.weights.damage_output_weight:.2f}, "
            f"risk_tolerance={self.weights.risk_tolerance:.2f}"
        )


class StrategyManager:
    """策略管理器

    整合策略评估和决策，提供统一接口。
    """

    def __init__(self, weights: StrategyWeights = None):
        self.weights = weights or StrategyWeights()
        self.decider = StrategyDecider(weights)

        # 策略执行器映射
        self._executors: Dict[StrategyType, Callable] = {}

    def register_executor(self, strategy: StrategyType, executor: Callable):
        """注册策略执行器"""
        self._executors[strategy] = executor

    def decide_and_execute(self, context: GameContext) -> Tuple[StrategyType, Any]:
        """
        决策并执行策略

        Args:
            context: 游戏上下文

        Returns:
            (选择的策略, 执行结果)
        """
        strategy, evaluation = self.decider.select_best_strategy(context)

        # 执行策略
        executor = self._executors.get(strategy)
        if executor:
            result = executor(evaluation, context)
            return strategy, result

        return strategy, None

    def get_current_strategy_info(self) -> Dict[str, Any]:
        """获取当前策略信息"""
        return {
            "current_strategy": self.decider.current_strategy.value
            if self.decider.current_strategy
            else None,
            "evaluation": {
                "utility_score": self.decider.current_evaluation.utility_score
                if self.decider.current_evaluation
                else 0,
                "safety_score": self.decider.current_evaluation.safety_score
                if self.decider.current_evaluation
                else 0,
                "damage_score": self.decider.current_evaluation.damage_score
                if self.decider.current_evaluation
                else 0,
                "recommendation": self.decider.current_evaluation.recommendation
                if self.decider.current_evaluation
                else "",
            },
            "stats": self.decider.get_strategy_stats(),
        }

    def adapt_to_performance(self, metrics: Dict[str, float]):
        """根据性能调整策略"""
        self.decider.adapt_weights(metrics)
