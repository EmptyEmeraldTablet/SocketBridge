"""
评估反馈系统

实现性能评估和反馈优化：
- 性能指标收集
- 决策效果评估
- 参数自适应调整
- 性能可视化

根据 reference.md 第三阶段设计。
"""

import time
import math
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import logging

logger = logging.getLogger("EvaluationSystem")


class MetricType(Enum):
    """指标类型"""

    HIT_RATE = "hit_rate"
    DODGE_RATE = "dodge_rate"
    DAMAGE_TAKEN = "damage_taken"
    DAMAGE_DEALT = "damage_dealt"
    ENEMIES_KILLED = "enemies_killed"
    SURVIVAL_TIME = "survival_time"
    DECISION_LATENCY = "decision_latency"


@dataclass
class PerformanceMetrics:
    """性能指标"""

    # 战斗指标
    hit_rate: float = 0.0  # 命中率
    dodge_rate: float = 0.0  # 躲避率
    damage_taken_per_minute: float = 0.0
    damage_dealt_per_minute: float = 0.0
    enemies_killed_per_minute: float = 0.0

    # 效率指标
    decision_latency_avg: float = 0.0  # 平均决策延迟(ms)
    decision_latency_max: float = 0.0  # 最大决策延迟
    frames_per_decision: float = 0.0

    # 生存指标
    survival_time: float = 0.0  # 生存时间(秒)
    rooms_cleared: int = 0

    # 计算综合得分
    @property
    def combat_score(self) -> float:
        """战斗得分"""
        return (
            self.hit_rate * 0.3
            + self.dodge_rate * 0.3
            + max(0, 1 - self.damage_taken_per_minute / 10) * 0.4
        )

    @property
    def efficiency_score(self) -> float:
        """效率得分"""
        return (
            max(0, 1 - self.decision_latency_avg / 50) * 0.5
            + max(0, 1 - self.decision_latency_max / 100) * 0.5
        )

    @property
    def overall_score(self) -> float:
        """综合得分"""
        return self.combat_score * 0.6 + self.efficiency_score * 0.4


@dataclass
class DecisionRecord:
    """决策记录"""

    timestamp: float
    decision_type: str
    input_state: Dict[str, Any]
    action_taken: str
    outcome: str  # "success", "failure", "partial"
    result_metrics: Dict[str, float]
    latency_ms: float


@dataclass
class AdjustmentSuggestion:
    """调整建议"""

    parameter: str
    current_value: float
    suggested_value: float
    reason: str
    confidence: float  # 0-1


class PerformanceEvaluator:
    """性能评估器

    收集和计算性能指标。
    """

    def __init__(self):
        # 指标历史
        self.metric_history: Dict[MetricType, deque] = {
            metric: deque(maxlen=100) for metric in MetricType
        }

        # 决策记录
        self.decision_records: List[DecisionRecord] = []
        self.max_records = 1000

        # 统计
        self.total_damage_taken = 0
        self.total_damage_dealt = 0
        self.total_hits = 0
        self.total_shots = 1
        self.total_dodges = 0
        self.total_dodge_attempts = 1
        self.enemies_killed = 0

        # 时间追踪
        self.start_time = time.time()
        self.last_evaluation_time = time.time()

        # 状态
        self.in_combat = False
        self.current_room = 0

    def record_shot(self, hit: bool):
        """记录射击"""
        self.total_shots += 1
        if hit:
            self.total_hits += 1
            self.metric_history[MetricType.HIT_RATE].append(1.0)
        else:
            self.metric_history[MetricType.HIT_RATE].append(0.0)

    def record_dodge(self, success: bool):
        """记录躲避"""
        self.total_dodge_attempts += 1
        if success:
            self.total_dodges += 1
            self.metric_history[MetricType.DODGE_RATE].append(1.0)
        else:
            self.metric_history[MetricType.DODGE_RATE].append(0.0)

    def record_damage(self, taken: float, dealt: float):
        """记录伤害"""
        self.total_damage_taken += taken
        self.total_damage_dealt += dealt

        elapsed = max(0.1, self.get_elapsed_time() / 60)  # 分钟

        self.metric_history[MetricType.DAMAGE_TAKEN].append(taken / elapsed)
        self.metric_history[MetricType.DAMAGE_DEALT].append(dealt / elapsed)

    def record_enemy_killed(self):
        """记录击杀敌人"""
        self.enemies_killed += 1
        self.metric_history[MetricType.ENEMIES_KILLED].append(1.0)

    def record_decision(self, record: DecisionRecord):
        """记录决策"""
        self.decision_records.append(record)

        # 只保留最近的记录
        if len(self.decision_records) > self.max_records:
            self.decision_records = self.decision_records[-self.max_records :]

        # 更新延迟指标
        self.metric_history[MetricType.DECISION_LATENCY].append(record.latency_ms)

    def record_room_cleared(self):
        """记录房间清除"""
        self.rooms_cleared += 1

    def get_elapsed_time(self) -> float:
        """获取经过时间"""
        return time.time() - self.start_time

    def calculate_metrics(self) -> PerformanceMetrics:
        """计算性能指标"""
        elapsed = max(0.1, self.get_elapsed_time() / 60)  # 分钟
        combat_time = max(0.1, self.get_elapsed_time() / 60)

        metrics = PerformanceMetrics()

        # 计算命中率
        if self.total_shots > 0:
            metrics.hit_rate = self.total_hits / self.total_shots

        # 计算躲避率
        if self.total_dodge_attempts > 0:
            metrics.dodge_rate = self.total_dodges / self.total_dodge_attempts

        # 计算伤害
        metrics.damage_taken_per_minute = self.total_damage_taken / combat_time
        metrics.damage_dealt_per_minute = self.total_damage_dealt / combat_time
        metrics.enemies_killed_per_minute = self.enemies_killed / combat_time

        # 计算延迟
        latencies = list(self.metric_history[MetricType.DECISION_LATENCY])
        if latencies:
            metrics.decision_latency_avg = sum(latencies) / len(latencies)
            metrics.decision_latency_max = max(latencies)

        # 计算每帧决策
        frame_count = (
            self.decision_records[-1].input_state.get("frame", 0)
            if self.decision_records
            else 0
        )
        if frame_count > 0:
            metrics.frames_per_decision = frame_count / max(
                1, len(self.decision_records)
            )

        # 生存时间
        metrics.survival_time = self.get_elapsed_time()
        metrics.rooms_cleared = self.rooms_cleared

        return metrics

    def get_success_rate_by_type(self, decision_type: str) -> float:
        """按类型获取成功率"""
        relevant = [
            r for r in self.decision_records if r.decision_type == decision_type
        ]
        if not relevant:
            return 0.0

        successful = sum(1 for r in relevant if r.outcome in ["success", "partial"])
        return successful / len(relevant)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        metrics = self.calculate_metrics()

        return {
            "metrics": {
                "hit_rate": metrics.hit_rate,
                "dodge_rate": metrics.dodge_rate,
                "damage_taken_pm": metrics.damage_taken_per_minute,
                "damage_dealt_pm": metrics.damage_dealt_per_minute,
                "enemies_killed_pm": metrics.enemies_killed_per_minute,
                "decision_latency_avg": metrics.decision_latency_avg,
                "decision_latency_max": metrics.decision_latency_max,
                "survival_time": metrics.survival_time,
                "rooms_cleared": metrics.rooms_cleared,
                "combat_score": metrics.combat_score,
                "efficiency_score": metrics.efficiency_score,
                "overall_score": metrics.overall_score,
            },
            "totals": {
                "total_hits": self.total_hits,
                "total_shots": self.total_shots,
                "total_dodges": self.total_dodges,
                "total_dodge_attempts": self.total_dodge_attempts,
                "total_damage_taken": self.total_damage_taken,
                "total_damage_dealt": self.total_damage_dealt,
                "enemies_killed": self.enemies_killed,
            },
            "decision_stats": {
                "total_decisions": len(self.decision_records),
                "success_rate": self.get_success_rate_by_type("attack"),
                "dodge_success_rate": self.get_success_rate_by_type("dodge"),
            },
        }

    def reset(self):
        """重置评估器"""
        self.total_damage_taken = 0
        self.total_damage_dealt = 0
        self.total_hits = 0
        self.total_shots = 1
        self.total_dodges = 0
        self.total_dodge_attempts = 1
        self.enemies_killed = 0
        self.rooms_cleared = 0
        self.start_time = time.time()
        self.decision_records.clear()

        for metric in MetricType:
            self.metric_history[metric].clear()


class ParameterOptimizer:
    """参数优化器

    根据性能数据建议参数调整。
    """

    def __init__(self):
        self.suggestions: List[AdjustmentSuggestion] = []
        self.adjustment_history: List[AdjustmentSuggestion] = []

    def analyze_and_suggest(
        self, metrics: PerformanceMetrics
    ) -> List[AdjustmentSuggestion]:
        """
        分析性能并生成调整建议

        Args:
            metrics: 性能指标

        Returns:
            调整建议列表
        """
        suggestions = []

        # 命中率低：建议调整瞄准参数
        if metrics.hit_rate < 0.3:
            suggestions.append(
                AdjustmentSuggestion(
                    parameter="aim_lead_factor",
                    current_value=0.3,
                    suggested_value=0.5,
                    reason="Low hit rate detected, increasing lead factor may help",
                    confidence=0.7,
                )
            )

        # 躲避率低：建议增加安全距离
        if metrics.dodge_rate < 0.4:
            suggestions.append(
                AdjustmentSuggestion(
                    parameter="safe_distance",
                    current_value=50,
                    suggested_value=80,
                    reason="Low dodge rate detected, increasing safe distance may help",
                    confidence=0.6,
                )
            )

        # 受伤太多：建议更保守的策略
        if metrics.damage_taken_per_minute > 3:
            suggestions.append(
                AdjustmentSuggestion(
                    parameter="strategy_aggression",
                    current_value=0.7,
                    suggested_value=0.4,
                    reason="High damage taken, recommend more defensive play",
                    confidence=0.8,
                )
            )

        # 决策延迟高：建议简化决策逻辑
        if metrics.decision_latency_avg > 20:
            suggestions.append(
                AdjustmentSuggestion(
                    parameter="decision_frequency",
                    current_value=20,
                    suggested_value=10,
                    reason="High decision latency, recommend reducing update frequency",
                    confidence=0.5,
                )
            )

        self.suggestions = suggestions
        return suggestions

    def apply_suggestion(self, suggestion: AdjustmentSuggestion) -> bool:
        """应用建议"""
        logger.info(
            f"Applying adjustment: {suggestion.parameter} = {suggestion.suggested_value}"
        )
        self.adjustment_history.append(suggestion)
        return True

    def get_recent_adjustments(self, count: int = 5) -> List[AdjustmentSuggestion]:
        """获取最近的调整"""
        return self.adjustment_history[-count:]

    def reset(self):
        """重置优化器"""
        self.suggestions.clear()
        self.adjustment_history.clear()


class EvaluationSystem:
    """评估系统

    整合性能评估和参数优化。
    """

    def __init__(self):
        self.evaluator = PerformanceEvaluator()
        self.optimizer = ParameterOptimizer()

        # 当前参数
        self.current_params: Dict[str, float] = {
            "aim_lead_factor": 0.3,
            "safe_distance": 50,
            "strategy_aggression": 0.7,
            "decision_frequency": 20,
            "move_speed_multiplier": 1.0,
            "attack_rate_multiplier": 1.0,
            "dodge_frequency": 0.5,
        }

        # 回调
        self.on_adjustment: Optional[Callable] = None

    def update(
        self,
        decision: str,
        action: str,
        outcome: str,
        latency_ms: float,
        state: Dict[str, Any],
    ):
        """更新评估系统"""
        # 记录决策
        record = DecisionRecord(
            timestamp=time.time(),
            decision_type=decision,
            input_state=state,
            action_taken=action,
            outcome=outcome,
            result_metrics={},
            latency_ms=latency_ms,
        )
        self.evaluator.record_decision(record)

    def record_hit(self, hit: bool):
        """记录命中"""
        self.evaluator.record_shot(hit)

    def record_dodge(self, success: bool):
        """记录躲避"""
        self.evaluator.record_dodge(success)

    def record_damage(self, taken: float, dealt: float):
        """记录伤害"""
        self.evaluator.record_damage(taken, dealt)

    def record_enemy_killed(self):
        """记录击杀"""
        self.evaluator.record_enemy_killed()

    def evaluate_and_optimize(self) -> Dict[str, Any]:
        """
        评估并优化

        Returns:
            评估报告
        """
        metrics = self.evaluator.calculate_metrics()
        suggestions = self.optimizer.analyze_and_suggest(metrics)

        # 生成报告
        report = {
            "metrics": metrics,
            "suggestions": [
                {"param": s.parameter, "value": s.suggested_value, "reason": s.reason}
                for s in suggestions
            ],
            "scores": {
                "combat": metrics.combat_score,
                "efficiency": metrics.efficiency_score,
                "overall": metrics.overall_score,
            },
            "needs_adjustment": len(suggestions) > 0,
        }

        return report

    def apply_best_adjustments(self) -> int:
        """应用最佳调整建议"""
        suggestions = self.optimizer.suggestions
        applied = 0

        for suggestion in suggestions:
            # 只应用高置信度的建议
            if suggestion.confidence > 0.6:
                if self._apply_parameter(suggestion):
                    self.optimizer.apply_suggestion(suggestion)
                    applied += 1

        return applied

    def _apply_parameter(self, suggestion: AdjustmentSuggestion) -> bool:
        """应用参数"""
        self.current_params[suggestion.parameter] = suggestion.suggested_value

        if self.on_adjustment:
            self.on_adjustment(suggestion.parameter, suggestion.suggested_value)

        logger.info(f"Adjusted {suggestion.parameter}: {suggestion.suggested_value}")
        return True

    def get_full_report(self) -> Dict[str, Any]:
        """获取完整报告"""
        metrics = self.evaluator.calculate_metrics()

        return {
            "current_params": dict(self.current_params),
            "performance": self.evaluator.get_stats(),
            "optimization_report": self.evaluate_and_optimize(),
            "recent_adjustments": [
                {"param": s.parameter, "from": s.current_value, "to": s.suggested_value}
                for s in self.optimizer.get_recent_adjustments(5)
            ],
        }

    def get_performance_summary(self) -> str:
        """获取性能摘要"""
        metrics = self.evaluator.calculate_metrics()

        lines = [
            "=" * 40,
            "Performance Summary",
            "=" * 40,
            f"Combat Score: {metrics.combat_score:.2f}",
            f"Efficiency Score: {metrics.efficiency_score:.2f}",
            f"Overall Score: {metrics.overall_score:.2f}",
            "-" * 40,
            f"Hit Rate: {metrics.hit_rate:.1%}",
            f"Dodge Rate: {metrics.dodge_rate:.1%}",
            f"Damage Taken/min: {metrics.damage_taken_per_minute:.1f}",
            f"Damage Dealt/min: {metrics.damage_dealt_per_minute:.1f}",
            f"Enemies Killed/min: {metrics.enemies_killed_per_minute:.1f}",
            "-" * 40,
            f"Decision Latency: {metrics.decision_latency_avg:.1f}ms (avg)",
            f"Survival Time: {metrics.survival_time:.1f}s",
            f"Rooms Cleared: {metrics.rooms_cleared}",
            "=" * 40,
        ]

        return "\n".join(lines)

    def reset(self):
        """重置系统"""
        self.evaluator.reset()
        self.optimizer.reset()

    def set_adjustment_callback(self, callback: Callable[[str, float], None]):
        """设置调整回调"""
        self.on_adjustment = callback
