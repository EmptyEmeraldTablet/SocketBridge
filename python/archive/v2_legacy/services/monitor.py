"""
Data Quality Monitor - 数据质量监控服务

提供实时数据质量监控和问题检测功能。
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from collections import defaultdict
import logging
import time

try:
    from core.protocol.timing import TimingMonitor, TimingIssue, TimingIssueType
    from core.validation.known_issues import (
        KnownIssueRegistry,
        ValidationIssue,
        IssueSeverity,
    )
    from models.state import TimingAwareStateManager
except ImportError:
    from python.core.protocol.timing import TimingMonitor, TimingIssue, TimingIssueType
    from python.core.validation.known_issues import (
        KnownIssueRegistry,
        ValidationIssue,
        IssueSeverity,
    )
    from python.models.state import TimingAwareStateManager

logger = logging.getLogger(__name__)


class ProblemSource(Enum):
    """问题来源"""

    GAME_LUA = "game_lua"
    NETWORK = "network"
    VALIDATION = "validation"
    TIMING = "timing"
    LOGIC = "logic"
    UNKNOWN = "unknown"


@dataclass
class QualityIssue:
    """质量问题"""

    id: str
    source: ProblemSource
    channel: str
    severity: str
    message: str
    timestamp: float
    frame: int
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityStats:
    """质量统计"""

    total_messages: int = 0
    total_issues: int = 0
    by_source: Dict[str, int] = field(default_factory=dict)
    by_severity: Dict[str, int] = field(default_factory=dict)
    by_channel: Dict[str, int] = field(default_factory=dict)
    issue_rate: float = 0.0
    last_update: float = 0.0


class DataQualityMonitor:
    """数据质量监控器

    功能：
    - 实时监控所有通道数据质量
    - 区分游戏端和 Python 端问题
    - 统计问题分布
    - 提供质量报告
    """

    def __init__(self, issue_callback: Optional[Callable[[QualityIssue], None]] = None):
        self.timing_monitor = TimingMonitor()
        self.known_issues = KnownIssueRegistry()
        self.state_manager = TimingAwareStateManager()
        self.issue_callback = issue_callback

        self.issues: List[QualityIssue] = []
        self.issue_counts: Dict[str, int] = defaultdict(int)
        self.start_time = time.time()
        self.last_report_time = self.start_time

        self._callbacks: Dict[str, List[Callable]] = defaultdict(list)

    def on_issue(self, channel: str, callback: Callable[[QualityIssue], None]):
        """注册问题回调"""
        self._callbacks[channel].append(callback)

    def on_any_issue(self, callback: Callable[[QualityIssue], None]):
        """注册所有问题回调"""
        self._callbacks["*"].append(callback)

    def process_message(
        self,
        msg: Dict[str, Any],
        raw_data: Dict[str, Any],
        frame: int,
        timestamp: Optional[int] = None,
    ) -> QualityStats:
        """处理消息并更新监控状态

        Args:
            msg: 协议消息（包含时序信息）
            raw_data: 原始数据
            frame: 当前帧号
            timestamp: 时间戳

        Returns:
            当前质量统计
        """
        self.issues = [i for i in self.issues if time.time() - i.timestamp < 300]

        try:
            from core.protocol.timing import MessageTimingInfo

            timing = MessageTimingInfo.from_message(msg)

            timing_issues = self.timing_monitor.check_message(timing)
            for issue in timing_issues:
                self._record_issue(
                    id=f"TIMING_{issue.issue_type.value}",
                    source=ProblemSource.TIMING,
                    channel="*",
                    severity=issue.severity,
                    message=f"{issue.issue_type.value}: {issue.details}",
                    frame=frame,
                    details=issue.details,
                )

            for channel_name, channel_data in raw_data.items():
                if channel_data is None:
                    continue

                known = self.known_issues.detect_issues(channel_name, channel_data)
                for validation_issue in known:
                    source = self._map_severity_to_source(validation_issue.severity)
                    self._record_issue(
                        id=validation_issue.issue_id,
                        source=source,
                        channel=channel_name,
                        severity=validation_issue.severity.value,
                        message=validation_issue.message,
                        frame=frame,
                        details={"field": validation_issue.field_path},
                    )

                if self.state_manager:
                    channel_timing = timing.channel_meta.get(channel_name)
                    if channel_timing:
                        self.state_manager.update_channel(
                            channel_name,
                            channel_data,
                            channel_timing,
                            frame,
                        )

        except Exception as e:
            logger.error(f"Error processing message for monitoring: {e}")
            self._record_issue(
                id="MONITOR_ERROR",
                source=ProblemSource.LOGIC,
                channel="*",
                severity="error",
                message=f"监控处理错误: {str(e)}",
                frame=frame,
                details={"error": str(e)},
            )

        return self.get_stats()

    def _record_issue(
        self,
        id: str,
        source: ProblemSource,
        channel: str,
        severity: str,
        message: str,
        frame: int,
        details: Optional[Dict] = None,
    ):
        """记录问题"""
        issue = QualityIssue(
            id=id,
            source=source,
            channel=channel,
            severity=severity,
            message=message,
            timestamp=time.time(),
            frame=frame,
            details=details or {},
        )

        self.issues.append(issue)
        self.issue_counts[id] += 1

        for cb in self._callbacks.get(channel, []):
            try:
                cb(issue)
            except Exception as e:
                logger.error(f"Issue callback error: {e}")

        for cb in self._callbacks.get("*", []):
            try:
                cb(issue)
            except Exception as e:
                logger.error(f"Global issue callback error: {e}")

        if self.issue_callback:
            try:
                self.issue_callback(issue)
            except Exception as e:
                logger.error(f"Issue callback error: {e}")

    def _map_severity_to_source(self, severity: IssueSeverity) -> ProblemSource:
        """映射严重性到问题来源"""
        mapping = {
            IssueSeverity.CRITICAL: ProblemSource.GAME_LUA,
            IssueSeverity.ERROR: ProblemSource.GAME_LUA,
            IssueSeverity.WARNING: ProblemSource.NETWORK,
            IssueSeverity.INFO: ProblemSource.VALIDATION,
        }
        return mapping.get(severity, ProblemSource.UNKNOWN)

    def get_stats(self) -> QualityStats:
        """获取质量统计"""
        now = time.time()
        duration = now - self.start_time

        by_source = defaultdict(int)
        by_severity = defaultdict(int)
        by_channel = defaultdict(int)

        for issue in self.issues:
            by_source[issue.source.value] += 1
            by_severity[issue.severity] += 1
            by_channel[issue.channel] += 1

        total_messages = self.timing_monitor.total_messages

        return QualityStats(
            total_messages=total_messages,
            total_issues=len(self.issues),
            by_source=dict(by_source),
            by_severity=dict(by_severity),
            by_channel=dict(by_channel),
            issue_rate=len(self.issues) / max(total_messages, 1),
            last_update=now,
        )

    def get_recent_issues(
        self, limit: int = 20, since: Optional[float] = None
    ) -> List[QualityIssue]:
        """获取最近问题"""
        since = since or (time.time() - 60)
        return [i for i in self.issues if i.timestamp >= since][-limit:]

    def get_issue_summary(self) -> Dict[str, Any]:
        """获取问题摘要"""
        stats = self.get_stats()

        critical = [i for i in self.issues if i.severity == "critical"]
        errors = [i for i in self.issues if i.severity == "error"]
        warnings = [i for i in self.issues if i.severity == "warning"]

        return {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": time.time() - self.start_time,
            "total_messages": stats.total_messages,
            "total_issues": stats.total_issues,
            "issue_rate": f"{stats.issue_rate:.2%}",
            "by_severity": {
                "critical": len(critical),
                "error": len(errors),
                "warning": len(warnings),
            },
            "by_source": stats.by_source,
            "top_issues": sorted(self.issue_counts.items(), key=lambda x: -x[1])[:10],
        }

    def generate_report(self) -> str:
        """生成质量报告"""
        summary = self.get_issue_summary()

        lines = [
            "=" * 60,
            "数据质量监控报告",
            f"生成时间: {summary['timestamp']}",
            "=" * 60,
            "",
            f"运行时间: {summary['uptime_seconds']:.0f} 秒",
            f"总消息数: {summary['total_messages']}",
            f"总问题数: {summary['total_issues']}",
            f"问题率: {summary['issue_rate']}",
            "",
            "按严重性分类:",
            f"  严重: {summary['by_severity']['critical']}",
            f"  错误: {summary['by_severity']['error']}",
            f"  警告: {summary['by_severity']['warning']}",
            "",
            "按来源分类:",
        ]

        for source, count in summary["by_source"].items():
            lines.append(f"  {source}: {count}")

        lines.extend(
            [
                "",
                "TOP 10 问题:",
            ]
        )

        for issue_id, count in summary["top_issues"]:
            lines.append(f"  {issue_id}: {count}")

        lines.extend(
            [
                "",
                "=" * 60,
            ]
        )

        return "\n".join(lines)
