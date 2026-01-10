"""
评估模块 (Evaluation Module)

实时反馈，优化决策。

子模块:
- 效果评估器 (Effectiveness Evaluator): 命中率、伤害效率、躲避成功率
- 错误分析器 (Error Analyzer): 碰撞原因、攻击失误、时机错误
- 学习适配器 (Learning Adapter): 参数自适应、策略权重更新
- 性能监控器 (Performance Monitor): 实时指标、瓶颈分析
"""

import math
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from dataclasses import dataclass
from enum import Enum
from collections import deque

from ..perception import Vector2D, GameState

logger = logging.getLogger("EvaluationModule")


class PerformanceMetric(Enum):
    """性能指标"""

    HIT_RATE = "hit_rate"  # 命中率
    DAMAGE_EFFICIENCY = "damage_efficiency"  # 伤害效率
    DODGE_SUCCESS_RATE = "dodge_success_rate"  # 躲避成功率
    MOVEMENT_EFFICIENCY = "movement_efficiency"  # 移动效率
    SURVIVAL_TIME = "survival_time"  # 生存时间
    ENEMIES_KILLED = "enemies_killed"  # 击杀数
    DAMAGE_TAKEN = "damage_taken"  # 受到伤害
    ROOMS_CLEARED = "rooms_cleared"  # 清理房间数


@dataclass
class PerformanceStats:
    """性能统计"""

    # 战斗统计
    total_shots: int = 0
    hits: int = 0
    damage_dealt: float = 0.0
    enemies_killed: int = 0

    # 移动统计
    total_movement_distance: float = 0.0
    efficient_movement: float = 0.0  # 有效移动距离
    collisions: int = 0

    # 生存统计
    damage_taken: float = 0.0
    dodge_attempts: int = 0
    successful_dodges: int = 0

    # 时间统计
    total_time: float = 0.0
    combat_time: float = 0.0
    rooms_cleared: int = 0

    # 效率计算
    def get_hit_rate(self) -> float:
        if self.total_shots == 0:
            return 0.0
        return self.hits / self.total_shots

    def get_damage_efficiency(self) -> float:
        if self.damage_dealt == 0:
            return 0.0
        return min(1.0, self.damage_dealt / max(1, self.enemies_killed * 10))

    def get_dodge_success_rate(self) -> float:
        if self.dodge_attempts == 0:
            return 0.0
        return self.successful_dodges / self.dodge_attempts

    def get_movement_efficiency(self) -> float:
        if self.total_movement_distance == 0:
            return 0.0
        return self.efficient_movement / self.total_movement_distance


@dataclass
class ErrorReport:
    """错误报告"""

    error_type: str
    timestamp: float
    frame: int

    # 详细信息
    description: str
    severity: str  # "low", "medium", "high", "critical"

    # 上下文
    action_attempted: str = ""
    actual_result: str = ""
    expected_result: str = ""

    # 位置信息
    position: Optional[Vector2D] = None
    target_position: Optional[Vector2D] = None

    # 原因分析
    root_cause: str = ""
    contributing_factors: List[str] = field(default_factory=list)

    # 建议
    suggestions: List[str] = field(default_factory=list)


class EffectivenessEvaluator:
    """
    效果评估器

    功能：
    - 命中率统计
    - 伤害效率计算
    - 躲避成功率
    - 移动效率评估
    """

    def __init__(self):
        self.stats = PerformanceStats()

        # 历史记录
        self.shot_history: deque = deque(maxlen=100)
        self.damage_history: deque = deque(maxlen=50)
        self.movement_history: deque = deque(maxlen=200)

        # 评估窗口
        self.evaluation_window = 300  # 评估帧数

    def record_shot(
        self, fired: bool, hit: bool, target_id: int = None, damage: float = 0.0
    ):
        """记录射击"""
        self.stats.total_shots += 1
        if hit:
            self.stats.hits += 1
            self.stats.damage_dealt += damage

            self.shot_history.append(
                {
                    "hit": True,
                    "target": target_id,
                    "damage": damage,
                    "timestamp": time.time(),
                }
            )
        else:
            self.shot_history.append(
                {"hit": False, "target": target_id, "timestamp": time.time()}
            )

    def record_movement(
        self,
        start_pos: Vector2D,
        end_pos: Vector2D,
        intended_direction: Vector2D = None,
    ):
        """记录移动"""
        distance = start_pos.distance_to(end_pos)
        self.stats.total_movement_distance += distance

        # 计算有效移动
        if intended_direction:
            actual_direction = (end_pos - start_pos).normalized()
            intended = intended_direction.normalized()

            # 计算方向一致性
            alignment = actual_direction.dot(intended)
            if alignment > 0.7:  # 方向基本一致
                self.stats.efficient_movement += distance

        self.movement_history.append({"distance": distance, "timestamp": time.time()})

    def record_dodge(self, attempt: bool, success: bool):
        """记录躲避"""
        if attempt:
            self.stats.dodge_attempts += 1
            if success:
                self.stats.successful_dodges += 1

    def record_damage_taken(self, amount: float, source: str):
        """记录受到的伤害"""
        self.stats.damage_taken += amount
        self.damage_history.append(
            {"amount": amount, "source": source, "timestamp": time.time()}
        )

    def record_enemy_killed(self, enemy_id: int, hp: float):
        """记录击杀"""
        self.stats.enemies_killed += 1

    def get_hit_rate(self) -> float:
        """获取命中率"""
        return self.stats.get_hit_rate()

    def get_damage_efficiency(self) -> float:
        """获取伤害效率"""
        return self.stats.get_damage_efficiency()

    def get_dodge_success_rate(self) -> float:
        """获取躲避成功率"""
        return self.stats.get_dodge_success_rate()

    def get_movement_efficiency(self) -> float:
        """获取移动效率"""
        return self.stats.get_movement_efficiency()

    def get_overall_effectiveness(self) -> float:
        """获取整体效果评分"""
        hit_rate = self.get_hit_rate()
        dodge_rate = self.get_dodge_success_rate()
        move_efficiency = self.get_movement_efficiency()

        # 加权平均
        weights = {"hit": 0.4, "dodge": 0.3, "move": 0.3}

        return (
            hit_rate * weights["hit"]
            + dodge_rate * weights["dodge"]
            + move_efficiency * weights["move"]
        )


class ErrorAnalyzer:
    """
    错误分析器

    功能：
    - 碰撞原因分析
    - 攻击失误分析
    - 时机错误识别
    - 路径规划问题
    """

    def __init__(self):
        self.error_history: deque = deque(maxlen=100)
        self.error_patterns: Dict[str, int] = {}

        # 错误阈值
        self.collision_threshold = 3  # 碰撞次数阈值
        self.miss_threshold = 5  # 失误次数阈值

    def analyze_collision(
        self,
        position: Vector2D,
        obstacle_pos: Vector2D,
        planned_path: List[Vector2D] = None,
    ) -> ErrorReport:
        """分析碰撞"""
        error = ErrorReport(
            error_type="collision",
            timestamp=time.time(),
            frame=0,
            description="发生碰撞",
            severity="medium",
            position=position,
            target_position=obstacle_pos,
        )

        # 分析原因
        if planned_path:
            # 检查是否偏离计划路径
            deviation = self._calculate_path_deviation(position, planned_path)
            if deviation > 30:
                error.root_cause = "偏离计划路径"
                error.suggestions.append("提高路径跟随精度")
            else:
                error.root_cause = "路径规划不准确"
                error.suggestions.append("更新障碍物地图")
        else:
            error.root_cause = "无计划路径"
            error.suggestions.append("启用路径规划")

        # 更新模式统计
        self._record_error(error)

        return error

    def analyze_miss(
        self,
        shot_direction: Vector2D,
        target_pos: Vector2D,
        predicted_pos: Vector2D = None,
    ) -> ErrorReport:
        """分析射击失误"""
        error = ErrorReport(
            error_type="miss",
            timestamp=time.time(),
            frame=0,
            description="射击未命中",
            severity="low",
            target_position=target_pos,
        )

        # 计算偏差
        to_target = target_pos - Vector2D(0, 0)  # 假设从原点射击
        direction = to_target.normalized()

        deviation = 1 - abs(shot_direction.dot(direction))

        if predicted_pos:
            # 如果有预测位置，检查预测误差
            prediction_error = predicted_pos.distance_to(target_pos)
            if prediction_error > 20:
                error.root_cause = "位置预测不准确"
                error.contributing_factors.append(f"预测误差: {prediction_error:.1f}")
                error.suggestions.append("提高目标移动预测精度")

        if deviation > 0.2:
            error.root_cause = "瞄准偏差过大"
            error.contributing_factors.append(f"方向偏差: {deviation:.2f}")
            error.suggestions.append("提高瞄准精度")

        self._record_error(error)

        return error

    def analyze_timing_error(
        self, expected_time: float, actual_time: float, action_type: str
    ) -> ErrorReport:
        """分析时机错误"""
        error = ErrorReport(
            error_type="timing",
            timestamp=time.time(),
            frame=0,
            description=f"{action_type}时机错误",
            severity="medium",
            action_attempted=action_type,
        )

        timing_diff = abs(expected_time - actual_time)

        if timing_diff > expected_time * 0.5:
            error.root_cause = "时机偏差过大"
            error.contributing_factors.append(f"时间偏差: {timing_diff:.1f}帧")
            error.suggestions.append("优化时机预测")

        self._record_error(error)

        return error

    def analyze_path_failure(
        self, start: Vector2D, goal: Vector2D, path: List[Vector2D], failure_reason: str
    ) -> ErrorReport:
        """分析路径规划失败"""
        error = ErrorReport(
            error_type="path_failure",
            timestamp=time.time(),
            frame=0,
            description=f"路径规划失败: {failure_reason}",
            severity="high",
            position=start,
            target_position=goal,
        )

        error.root_cause = "无法找到可行路径"
        error.contributing_factors.append(f"原因: {failure_reason}")
        error.suggestions.append(
            ["检查障碍物地图", "扩大搜索范围", "允许更长的绕行路径"]
        )

        self._record_error(error)

        return error

    def _calculate_path_deviation(
        self, position: Vector2D, path: List[Vector2D]
    ) -> float:
        """计算位置偏离路径的距离"""
        if not path:
            return 0.0

        min_dist = float("inf")
        for i in range(len(path) - 1):
            dist = self._point_to_segment_distance(position, path[i], path[i + 1])
            min_dist = min(min_dist, dist)

        return min_dist

    def _point_to_segment_distance(
        self, point: Vector2D, a: Vector2D, b: Vector2D
    ) -> float:
        """计算点到线段的距离"""
        ab = b - a
        ap = point - a

        t = max(
            0,
            min(1, ap.dot(ab) / ab.length_squared() if ab.length_squared() > 0 else 0),
        )
        closest = a + ab * t

        return point.distance_to(closest)

    def _record_error(self, error: ErrorReport):
        """记录错误"""
        self.error_history.append(error)

        # 更新模式统计
        error_type = error.error_type
        self.error_patterns[error_type] = self.error_patterns.get(error_type, 0) + 1

    def get_error_summary(self) -> Dict:
        """获取错误摘要"""
        return {
            "total_errors": len(self.error_history),
            "error_patterns": dict(self.error_patterns),
            "recent_errors": [e.to_dict() for e in list(self.error_history)[-5:]],
        }


class LearningAdapter:
    """
    学习适配器

    功能：
    - 参数自适应调整
    - 策略权重更新
    - 模式识别改进
    - 经验库积累
    """

    def __init__(self):
        # 经验库
        self.experience: Dict[str, List[Dict]] = {}

        # 参数调整历史
        self.parameter_history: deque = deque(maxlen=50)

        # 策略权重
        self.strategy_weights = {
            "aggressive": 0.5,
            "defensive": 0.5,
            "kiting": 0.5,
            "focus_fire": 0.5,
        }

        # 学习参数
        self.learning_rate = 0.1
        self.discount_factor = 0.95
        self.exploration_rate = 0.2

    def update_from_performance(self, performance: Dict, action_taken: str) -> Dict:
        """
        根据性能更新

        Args:
            performance: 性能指标
            action_taken: 执行的动作

        Returns:
            更新后的参数
        """
        # 计算奖励
        reward = self._calculate_reward(performance)

        # 更新经验
        self._add_experience(action_taken, performance, reward)

        # 调整参数
        updated_params = self._adjust_parameters(action_taken, reward)

        return updated_params

    def _calculate_reward(self, performance: Dict) -> float:
        """计算奖励"""
        reward = 0.0

        # 正向奖励
        if performance.get("hit_rate", 0) > 0.5:
            reward += 0.3
        if performance.get("dodge_success_rate", 0) > 0.7:
            reward += 0.3
        if performance.get("enemy_killed", False):
            reward += 0.4

        # 负向惩罚
        if performance.get("collision", False):
            reward -= 0.2
        if performance.get("damage_taken", 0) > 0:
            reward -= min(0.3, performance["damage_taken"] * 0.1)

        return max(-1.0, min(1.0, reward))

    def _add_experience(self, action: str, outcome: Dict, reward: float):
        """添加经验"""
        if action not in self.experience:
            self.experience[action] = []

        self.experience[action].append(
            {"outcome": outcome, "reward": reward, "timestamp": time.time()}
        )

        # 保持经验库大小
        if len(self.experience[action]) > 100:
            self.experience[action].pop(0)

    def _adjust_parameters(self, action: str, reward: float) -> Dict:
        """调整参数"""
        updated = {}

        # 根据动作类型调整对应参数
        if "kiting" in action or "move" in action:
            # 调整移动相关参数
            self.parameter_history.append(
                {
                    "param": "move_speed",
                    "old": 0.5,
                    "new": 0.5 + reward * self.learning_rate,
                }
            )
            updated["move_speed"] = 0.5 + reward * self.learning_rate

        elif "attack" in action or "shoot" in action:
            # 调整攻击相关参数
            self.parameter_history.append(
                {
                    "param": "aim_precision",
                    "old": 0.5,
                    "new": 0.5 + reward * self.learning_rate,
                }
            )
            updated["aim_precision"] = 0.5 + reward * self.learning_rate

        return updated

    def get_optimal_action(self, state: Dict) -> str:
        """获取最优动作"""
        if not self.experience:
            return "explore"

        # 简单的探索-利用策略
        if len(self.experience) < 5 or self.exploration_rate > 0.3:
            return "explore"

        # 计算每个动作的平均奖励
        action_rewards = {}
        for action, experiences in self.experience.items():
            if experiences:
                avg_reward = sum(e["reward"] for e in experiences) / len(experiences)
                action_rewards[action] = avg_reward

        # 选择最高奖励的动作
        if action_rewards:
            best_action = max(action_rewards, key=action_rewards.get)
            return best_action

        return "explore"

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "experience_count": sum(len(v) for v in self.experience.values()),
            "action_types": list(self.experience.keys()),
            "strategy_weights": dict(self.strategy_weights),
            "exploration_rate": self.exploration_rate,
        }


class PerformanceMonitor:
    """
    性能监控器

    功能：
    - 实时指标显示
    - 瓶颈分析
    - 系统健康检查
    """

    def __init__(self):
        # 实时指标
        self.fps_history: deque = deque(maxlen=60)
        self.latency_history: deque = deque(maxlen=60)
        self.frame_times: deque = deque(maxlen=60)

        # 阈值
        self.fps_threshold = 20
        self.latency_threshold = 50  # ms
        self.frame_time_threshold = 50  # ms

    def record_frame_time(self, frame_time: float):
        """记录帧时间"""
        self.frame_times.append(frame_time)

        # 计算FPS
        fps = 1.0 / frame_time if frame_time > 0 else 0
        self.fps_history.append(fps)

    def record_latency(self, latency: float):
        """记录延迟"""
        self.latency_history.append(latency)

    def get_current_fps(self) -> float:
        """获取当前FPS"""
        if not self.fps_history:
            return 0.0
        return sum(self.fps_history) / len(self.fps_history)

    def get_average_latency(self) -> float:
        """获取平均延迟"""
        if not self.latency_history:
            return 0.0
        return sum(self.latency_history) / len(self.latency_history)

    def get_frame_time_stats(self) -> Dict:
        """获取帧时间统计"""
        if not self.frame_times:
            return {}

        times = list(self.frame_times)
        return {
            "avg": sum(times) / len(times),
            "min": min(times),
            "max": max(times),
            "p95": sorted(times)[int(len(times) * 0.95)],
        }

    def check_health(self) -> Dict:
        """检查系统健康"""
        health = {"status": "healthy", "issues": [], "recommendations": []}

        # 检查FPS
        avg_fps = self.get_current_fps()
        if avg_fps < self.fps_threshold:
            health["status"] = "degraded"
            health["issues"].append(f"低FPS: {avg_fps:.1f}")
            health["recommendations"].append("减少计算量或优化算法")

        # 检查延迟
        avg_latency = self.get_average_latency()
        if avg_latency > self.latency_threshold:
            health["status"] = "degraded"
            health["issues"].append(f"高延迟: {avg_latency:.1f}ms")
            health["recommendations"].append("优化数据处理流程")

        # 检查帧时间
        frame_stats = self.get_frame_time_stats()
        if frame_stats.get("avg", 0) > self.frame_time_threshold / 1000:
            health["status"] = "degraded"
            health["issues"].append("帧时间过长")

        return health

    def get_report(self) -> Dict:
        """获取完整报告"""
        return {
            "fps": self.get_current_fps(),
            "latency": self.get_average_latency(),
            "frame_stats": self.get_frame_time_stats(),
            "health": self.check_health(),
        }


class EvaluationModule:
    """
    评估模块主类

    整合效果评估器、错误分析器、学习适配器和性能监控器，
    提供实时反馈和自适应优化。

    输入: 执行结果 + 新游戏状态
    输出: 性能评估 + 参数调整
    """

    def __init__(self):
        self.effectiveness_evaluator = EffectivenessEvaluator()
        self.error_analyzer = ErrorAnalyzer()
        self.learning_adapter = LearningAdapter()
        self.performance_monitor = PerformanceMonitor()

        # 统计
        self.stats = {
            "total_evaluations": 0,
            "errors_detected": 0,
            "parameters_adjusted": 0,
        }

    def evaluate_execution(self, execution_result: Dict, new_state: GameState) -> Dict:
        """
        评估执行结果

        Args:
            execution_result: 执行结果
            new_state: 新游戏状态

        Returns:
            评估报告
        """
        self.stats["total_evaluations"] += 1

        report = {
            "performance": self._get_performance_summary(),
            "errors": [],
            "recommendations": [],
            "parameter_updates": {},
        }

        # 分析执行结果
        if execution_result.get("collision"):
            error = self.error_analyzer.analyze_collision(
                execution_result.get("position"),
                execution_result.get("obstacle_position"),
                execution_result.get("planned_path"),
            )
            report["errors"].append(error.to_dict())
            self.stats["errors_detected"] += 1

        if execution_result.get("miss"):
            error = self.error_analyzer.analyze_miss(
                execution_result.get("shot_direction"),
                execution_result.get("target_position"),
                execution_result.get("predicted_position"),
            )
            report["errors"].append(error.to_dict())

        # 更新参数
        performance_summary = self._get_performance_summary()
        action = execution_result.get("action", "unknown")

        updates = self.learning_adapter.update_from_performance(
            performance_summary, action
        )
        report["parameter_updates"] = updates

        if updates:
            self.stats["parameters_adjusted"] += len(updates)

        # 生成建议
        report["recommendations"] = self._generate_recommendations(
            performance_summary, report["errors"]
        )

        return report

    def _get_performance_summary(self) -> Dict:
        """获取性能摘要"""
        return {
            "hit_rate": self.effectiveness_evaluator.get_hit_rate(),
            "damage_efficiency": self.effectiveness_evaluator.get_damage_efficiency(),
            "dodge_success_rate": self.effectiveness_evaluator.get_dodge_success_rate(),
            "movement_efficiency": self.effectiveness_evaluator.get_movement_efficiency(),
        }

    def _generate_recommendations(
        self, performance: Dict, errors: List[Dict]
    ) -> List[str]:
        """生成建议"""
        recommendations = []

        # 基于性能的建议
        if performance.get("hit_rate", 0) < 0.3:
            recommendations.append("提高瞄准精度，考虑预判目标移动")

        if performance.get("dodge_success_rate", 0) < 0.5:
            recommendations.append("优化躲避算法，提前预判威胁")

        if performance.get("movement_efficiency", 0) < 0.6:
            recommendations.append("改进路径规划，减少无效移动")

        # 基于错误的建议
        error_types = [e.get("error_type") for e in errors]
        if "collision" in error_types:
            recommendations.append("更新障碍物地图，提高碰撞检测精度")

        if "miss" in error_types:
            recommendations.append("调整射击时机，优化预判参数")

        return recommendations

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "effectiveness": self._get_performance_summary(),
            "errors": self.error_analyzer.get_error_summary(),
            "learning": self.learning_adapter.get_stats(),
            "performance": self.performance_monitor.get_report(),
        }


# ==================== 便捷函数 ====================


def create_evaluation_module() -> EvaluationModule:
    """创建评估模块实例"""
    return EvaluationModule()


# 导出主要类
__all__ = [
    "EvaluationModule",
    "EffectivenessEvaluator",
    "ErrorAnalyzer",
    "LearningAdapter",
    "PerformanceMonitor",
    "PerformanceStats",
    "ErrorReport",
    "PerformanceMetric",
    "create_evaluation_module",
]
