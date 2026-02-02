"""
Known Issue Registry - 已知问题检测

提供基于历史数据的问题检测能力，支持：
1. 静态已知问题模式匹配
2. 动态异常检测
3. 问题严重性分级
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class IssueSeverity(Enum):
    """问题严重性"""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueSource(Enum):
    """问题来源"""

    LUA_COLLECTOR = "lua_collector"
    NETWORK = "network"
    VALIDATION = "validation"
    TIMING = "timing"
    LOGIC = "logic"


@dataclass
class KnownIssue:
    """已知问题"""

    id: str
    name: str
    description: str
    channel: str
    severity: IssueSeverity
    source: IssueSource
    pattern: Dict[str, Any]
    workaround: Optional[str] = None
    affected_versions: List[str] = field(default_factory=list)

    def matches(self, data: Dict[str, Any]) -> bool:
        """检查数据是否匹配此问题模式"""
        for key, expected_value in self.pattern.items():
            if key not in data:
                return False
            actual_value = data[key]
            if isinstance(expected_value, list):
                if actual_value not in expected_value:
                    return False
            elif actual_value != expected_value:
                return False
        return True


@dataclass
class ValidationIssue:
    """验证问题"""

    issue_id: str
    channel: str
    field_path: str
    severity: IssueSeverity
    message: str
    actual_value: Any
    expected_value: Optional[Any] = None


class KnownIssueRegistry:
    """已知问题注册表"""

    _instance: Optional["KnownIssueRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.issues: Dict[str, KnownIssue] = {}
        self.issue_counts: Dict[str, int] = defaultdict(int)
        self._register_known_issues()

    def _register_known_issues(self):
        """注册所有已知问题"""

        self._register_issue(
            KnownIssue(
                id="PLAYER_POSITION_NULL",
                name="Player Position Null",
                description="玩家位置数据包含空值",
                channel="PLAYER_POSITION",
                severity=IssueSeverity.WARNING,
                source=IssueSource.LUA_COLLECTOR,
                pattern={"pos": None},
                workaround="使用上一帧位置",
            )
        )

        self._register_issue(
            KnownIssue(
                id="PLAYER_STATS_LUCK_FLOAT",
                name="Player Stats Luck Float",
                description="玩家幸运值应为整数，实际收到浮点数",
                channel="PLAYER_STATS",
                severity=IssueSeverity.INFO,
                source=IssueSource.LUA_COLLECTOR,
                pattern={"luck": lambda v: isinstance(v, float)},
                workaround="自动转换为整数",
                affected_versions=["2.0", "2.1"],
            )
        )

        self._register_issue(
            KnownIssue(
                id="ENEMY_MISSING_TARGET",
                name="Enemy Missing Target",
                description="敌人缺少目标位置信息",
                channel="ENEMIES",
                severity=IssueSeverity.INFO,
                source=IssueSource.LUA_COLLECTOR,
                pattern={"target_pos": None},
                workaround="目标位置默认为(0,0)",
            )
        )

        self._register_issue(
            KnownIssue(
                id="PROJECTILE_HEIGHT_NULL",
                name="Projectile Height Null",
                description="投射物高度为空",
                channel="PROJECTILES",
                severity=IssueSeverity.INFO,
                source=IssueSource.LUA_COLLECTOR,
                pattern={"height": None},
                workaround="使用默认值0",
            )
        )

        self._register_issue(
            KnownIssue(
                id="ROOM_INFO_GRID_NULL",
                name="Room Info Grid Null",
                description="房间信息网格尺寸为空",
                channel="ROOM_INFO",
                severity=IssueSeverity.WARNING,
                source=IssueSource.LUA_COLLECTOR,
                pattern={"grid_width": None},
                workaround="跳过房间处理",
            )
        )

        self._register_issue(
            KnownIssue(
                id="ROOM_LAYOUT_EMPTY",
                name="Room Layout Empty",
                description="房间布局数据为空",
                channel="ROOM_LAYOUT",
                severity=IssueSeverity.WARNING,
                source=IssueSource.LUA_COLLECTOR,
                pattern={"grid": {}},
                workaround="使用空网格",
            )
        )

        self._register_issue(
            KnownIssue(
                id="PICKUP_PRICE_NULL",
                name="Pickup Price Null",
                description="拾取物价格为空",
                channel="PICKUPS",
                severity=IssueSeverity.INFO,
                source=IssueSource.LUA_COLLECTOR,
                pattern={"price": None},
                workaround="使用默认值0",
            )
        )

        self._register_issue(
            KnownIssue(
                id="BOMB_TIMER_NULL",
                name="Bomb Timer Null",
                description="炸弹计时器为空",
                channel="BOMBS",
                severity=IssueSeverity.INFO,
                source=IssueSource.LUA_COLLECTOR,
                pattern={"timer": None},
                workaround="使用默认值0",
            )
        )

        self._register_issue(
            KnownIssue(
                id="FIRE_HAZARD_EXTINGUISHED",
                name="Fire Hazard Extinguished",
                description="火焰危险物已熄灭但仍在检测",
                channel="FIRE_HAZARDS",
                severity=IssueSeverity.INFO,
                source=IssueSource.LOGIC,
                pattern={"is_extinguished": True},
                workaround="忽略已熄灭的火焰",
            )
        )

        self._register_issue(
            KnownIssue(
                id="INTERACTABLE_DISTANT",
                name="Interactable Distant",
                description="可互动实体距离过远，玩家无法交互",
                channel="INTERACTABLES",
                severity=IssueSeverity.INFO,
                source=IssueSource.LOGIC,
                pattern={"distance": lambda v: v > 1000},
                workaround="跳过远距离实体",
            )
        )

    def _register_issue(self, issue: KnownIssue):
        """注册单个已知问题"""
        self.issues[issue.id] = issue

    def detect_issues(self, channel: str, data: Any) -> List[ValidationIssue]:
        """检测数据中的已知问题"""
        if not isinstance(data, dict):
            return []

        issues = []

        for issue in self.issues.values():
            if issue.channel != channel:
                continue

            try:
                if issue.matches(data):
                    self.issue_counts[issue.id] += 1
                    issues.append(
                        ValidationIssue(
                            issue_id=issue.id,
                            channel=channel,
                            field_path="*",
                            severity=issue.severity,
                            message=issue.description,
                            actual_value=data,
                            expected_value=issue.pattern,
                        )
                    )
                    logger.debug(
                        f"Detected known issue: {issue.id} in channel {channel}"
                    )
            except Exception as e:
                logger.warning(f"Error matching issue {issue.id}: {e}")

        return issues

    def get_issue_stats(self) -> Dict[str, Any]:
        """获取问题统计"""
        total = sum(self.issue_counts.values())
        by_severity = defaultdict(int)
        for issue_id, count in self.issue_counts.items():
            issue = self.issues.get(issue_id)
            if issue:
                by_severity[issue.severity.value] += count

        return {
            "total_issues": total,
            "by_severity": dict(by_severity),
            "by_id": dict(self.issue_counts),
        }

    def get_issue(self, issue_id: str) -> Optional[KnownIssue]:
        """获取已知问题定义"""
        return self.issues.get(issue_id)

    def get_workaround(self, issue_id: str) -> Optional[str]:
        """获取问题解决方案"""
        issue = self.get_issue(issue_id)
        return issue.workaround if issue else None


class DynamicAnomalyDetector:
    """动态异常检测器"""

    def __init__(self, history_size: int = 100):
        self.history: Dict[str, List[Any]] = defaultdict(list)
        self.history_size = history_size
        self.thresholds: Dict[str, Dict[str, float]] = {}

    def add_sample(self, channel: str, value: Any):
        """添加样本"""
        self.history[channel].append(value)
        if len(self.history[channel]) > self.history_size:
            self.history[channel].pop(0)

    def detect_anomaly(self, channel: str, value: Any) -> Optional[ValidationIssue]:
        """检测异常"""
        if channel not in self.history or len(self.history[channel]) < 10:
            return None

        history = self.history[channel]

        if isinstance(value, (int, float)) and all(
            isinstance(v, (int, float)) for v in history[-10:]
        ):
            recent_values = [v for v in history[-10:] if isinstance(v, (int, float))]
            if len(recent_values) >= 5:
                mean = sum(recent_values) / len(recent_values)
                variance = sum((v - mean) ** 2 for v in recent_values) / len(
                    recent_values
                )
                std = variance**0.5

                if std > 0 and isinstance(value, (int, float)):
                    z_score = abs(value - mean) / std
                    if z_score > 5:
                        return ValidationIssue(
                            issue_id="ANOMALY_DETECTED",
                            channel=channel,
                            field_path="*",
                            severity=IssueSeverity.WARNING,
                            message=f"Value {value} is {z_score:.1f} std deviations from mean",
                            actual_value=value,
                            expected_value=f"mean={mean:.2f}, std={std:.2f}",
                        )

        return None
