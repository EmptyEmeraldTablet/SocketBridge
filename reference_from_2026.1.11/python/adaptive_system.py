"""
自适应系统模块

实现动态参数调整：
- 场景识别
- 参数调节
- 配置管理

根据 reference.md 第四阶段设计。
"""

import json
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger("AdaptiveSystem")


class ScenarioType(Enum):
    """场景类型"""

    UNKNOWN = "unknown"
    BOSS_FIGHT = "boss_fight"
    SWARM = "swarm"
    ONE_VS_ONE = "1v1"
    NARROW_SPACE = "narrow_space"
    OPEN_SPACE = "open_space"
    HAZARDOUS = "hazardous"


@dataclass
class ScenarioConfig:
    """场景配置"""

    name: str
    aggression: float = 0.5
    caution: float = 0.5
    move_speed: float = 1.0
    attack_rate: float = 1.0
    dodge_frequency: float = 0.5
    safe_distance: float = 100.0
    lead_factor: float = 0.3

    def apply_overrides(self, overrides: Dict[str, float]):
        """应用覆盖"""
        for key, value in overrides.items():
            if hasattr(self, key):
                setattr(self, key, value)


class ScenarioDetector:
    """场景检测器"""

    def __init__(self):
        self.current_scenario = ScenarioType.UNKNOWN

    def detect(self, game_state: Dict[str, Any]) -> ScenarioType:
        """检测当前场景"""
        enemies = game_state.get("enemies", [])
        enemy_count = len(enemies)

        # 检查Boss
        has_boss = any(e.get("is_boss", False) for e in enemies)
        if has_boss:
            self.current_scenario = ScenarioType.BOSS_FIGHT
            return self.current_scenario

        # 检查敌人数量
        if enemy_count >= 5:
            self.current_scenario = ScenarioType.SWARM
        elif enemy_count == 1:
            self.current_scenario = ScenarioType.ONE_VS_ONE

        # 检查空间（基于房间信息）
        room_info = game_state.get("room_info", {})
        grid_width = room_info.get("grid_width", 13)
        grid_height = room_info.get("grid_height", 7)

        if grid_width * grid_height < 50:
            self.current_scenario = ScenarioType.NARROW_SPACE
        elif grid_width * grid_height > 100:
            self.current_scenario = ScenarioType.OPEN_SPACE

        # 检查危险物
        hazards = game_state.get("fire_hazards", [])
        if len(hazards) > 2:
            self.current_scenario = ScenarioType.HAZARDOUS

        return self.current_scenario

    def get_config_for_scenario(self, scenario: ScenarioType) -> ScenarioConfig:
        """获取场景配置"""
        configs = {
            ScenarioType.BOSS_FIGHT: ScenarioConfig(
                name="boss_fight",
                aggression=0.6,
                caution=0.7,
                move_speed=0.8,
                attack_rate=1.2,
                dodge_frequency=0.6,
                safe_distance=150.0,
            ),
            ScenarioType.SWARM: ScenarioConfig(
                name="swarm",
                aggression=0.8,
                caution=0.4,
                move_speed=1.2,
                attack_rate=1.5,
                dodge_frequency=0.3,
                safe_distance=80.0,
                lead_factor=0.1,
            ),
            ScenarioType.ONE_VS_ONE: ScenarioConfig(
                name="1v1",
                aggression=0.7,
                caution=0.5,
                move_speed=1.0,
                attack_rate=1.0,
                dodge_frequency=0.5,
                safe_distance=120.0,
            ),
            ScenarioType.NARROW_SPACE: ScenarioConfig(
                name="narrow_space",
                aggression=0.4,
                caution=0.7,
                move_speed=0.9,
                attack_rate=0.8,
                dodge_frequency=0.6,
                safe_distance=60.0,
            ),
            ScenarioType.OPEN_SPACE: ScenarioConfig(
                name="open_space",
                aggression=0.6,
                caution=0.4,
                move_speed=1.1,
                attack_rate=1.1,
                dodge_frequency=0.4,
                safe_distance=100.0,
            ),
            ScenarioType.HAZARDOUS: ScenarioConfig(
                name="hazardous",
                aggression=0.3,
                caution=0.9,
                move_speed=0.7,
                attack_rate=0.5,
                dodge_frequency=0.8,
                safe_distance=200.0,
            ),
            ScenarioType.UNKNOWN: ScenarioConfig(name="unknown"),
        }

        return configs.get(scenario, ScenarioConfig(name="unknown"))


class AdaptiveParameterSystem:
    """自适应参数系统"""

    def __init__(self):
        self.detector = ScenarioDetector()
        self.current_config: Optional[ScenarioConfig] = None
        self.parameter_overrides: Dict[str, float] = {}

        # 性能回调
        self.on_parameter_change: Optional[Callable[[str, float], None]] = None

    def update(
        self, game_state: Dict[str, Any], performance_metrics: Dict[str, float]
    ) -> ScenarioConfig:
        """更新系统"""
        # 检测场景
        scenario = self.detector.detect(game_state)

        # 获取配置
        config = self.detector.get_config_for_scenario(scenario)

        # 应用性能调整
        self._apply_performance_adjustments(config, performance_metrics)

        self.current_config = config
        return config

    def _apply_performance_adjustments(
        self, config: ScenarioConfig, metrics: Dict[str, float]
    ):
        """应用性能调整"""
        hit_rate = metrics.get("hit_rate", 0.5)
        dodge_rate = metrics.get("dodge_rate", 0.5)
        damage_taken = metrics.get("damage_taken", 0)

        # 命中率低
        if hit_rate < 0.3:
            config.lead_factor = min(0.5, config.lead_factor + 0.05)
            config.attack_rate = max(0.7, config.attack_rate - 0.1)

        # 躲避率低
        if dodge_rate < 0.4:
            config.safe_distance = min(200, config.safe_distance + 20)
            config.dodge_frequency = min(1.0, config.dodge_frequency + 0.1)

        # 受伤太多
        if damage_taken > 2.0:
            config.caution = min(1.0, config.caution + 0.1)
            config.move_speed = max(0.7, config.move_speed - 0.1)

    def set_override(self, parameter: str, value: float):
        """设置参数覆盖"""
        self.parameter_overrides[parameter] = value

        if self.current_config:
            self.current_config.apply_overrides(self.parameter_overrides)

        if self.on_parameter_change:
            self.on_parameter_change(parameter, value)

    def get_parameter(self, name: str, default: float = 0.0) -> float:
        """获取参数"""
        if self.current_config and hasattr(self.current_config, name):
            return getattr(self.current_config, name)
        return default

    def save_config(self, filename: str) -> bool:
        """保存配置"""
        if not self.current_config:
            return False

        config_dict = {
            "scenario": self.detector.current_scenario.value,
            "aggression": self.current_config.aggression,
            "caution": self.current_config.caution,
            "move_speed": self.current_config.move_speed,
            "attack_rate": self.current_config.attack_rate,
            "dodge_frequency": self.current_config.dodge_frequency,
            "safe_distance": self.current_config.safe_distance,
            "lead_factor": self.current_config.lead_factor,
            "overrides": self.parameter_overrides,
        }

        try:
            with open(filename, "w") as f:
                json.dump(config_dict, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False

    def load_config(self, filename: str) -> bool:
        """加载配置"""
        try:
            with open(filename, "r") as f:
                config_dict = json.load(f)

            scenario = ScenarioType(config_dict.get("scenario", "unknown"))
            config = self.detector.get_config_for_scenario(scenario)

            config.aggression = config_dict.get("aggression", config.aggression)
            config.caution = config_dict.get("caution", config.caution)
            config.move_speed = config_dict.get("move_speed", config.move_speed)
            config.attack_rate = config_dict.get("attack_rate", config.attack_rate)
            config.dodge_frequency = config_dict.get(
                "dodge_frequency", config.dodge_frequency
            )
            config.safe_distance = config_dict.get(
                "safe_distance", config.safe_distance
            )
            config.lead_factor = config_dict.get("lead_factor", config.lead_factor)

            self.parameter_overrides = config_dict.get("overrides", {})
            self.current_config = config

            return True
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return False

    def reset(self):
        """重置"""
        self.parameter_overrides.clear()
        self.current_config = None


class PerformanceOptimizer:
    """性能优化器"""

    def __init__(self):
        self.update_interval = 1.0
        self.last_update = 0
        self.enabled = True

        # 优化阈值
        self.lag_threshold_ms = 16.0  # 60fps = 16.67ms per frame
        self.cpu_threshold_percent = 80.0

    def check_and_optimize(
        self, frame_time_ms: float, cpu_percent: float
    ) -> Dict[str, Any]:
        """检查并优化"""
        suggestions = {}

        # 检测卡顿
        if frame_time_ms > self.lag_threshold_ms:
            suggestions["reduce_update_rate"] = True
            suggestions["skip_frames"] = True

        # CPU使用率高
        if cpu_percent > self.cpu_threshold_percent:
            suggestions["disable_advanced_features"] = True
            suggestions["reduce_ai_complexity"] = True

        return suggestions

    def get_optimization_report(self) -> Dict[str, Any]:
        """获取优化报告"""
        return {
            "lag_threshold_ms": self.lag_threshold_ms,
            "cpu_threshold_percent": self.cpu_threshold_percent,
            "enabled": self.enabled,
        }
