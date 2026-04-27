"""
Quality Monitor — tracks data quality statistics and generates reports.
"""

import time
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class QualityIssue:
    """A recorded quality issue."""
    channel: str
    issue_id: str
    severity: str
    frame: int
    details: dict = field(default_factory=dict)


@dataclass
class QualityReport:
    """Data quality report for a time window."""
    duration_seconds: float
    total_messages: int
    total_issues: int
    channels_active: int
    issues_by_severity: dict[str, int] = field(default_factory=dict)
    issues_by_channel: dict[str, int] = field(default_factory=dict)
    top_issues: list[dict] = field(default_factory=list)


class QualityMonitor:
    """Tracks data quality metrics in real time."""

    def __init__(self):
        self._start_time = time.time()
        self._total_messages = 0
        self._total_issues = 0
        self._issues: list[QualityIssue] = []
        self._active_channels: set[str] = set()
        self._by_severity: dict[str, int] = defaultdict(int)
        self._by_channel: dict[str, int] = defaultdict(int)

    def record_message(self, channels: list[str]):
        self._total_messages += 1
        self._active_channels.update(channels)

    def record_issue(self, channel: str, issue_id: str,
                     severity: str = "info", frame: int = 0,
                     details: Optional[dict] = None):
        self._total_issues += 1
        self._by_severity[severity] += 1
        self._by_channel[channel] += 1
        self._issues.append(QualityIssue(
            channel=channel, issue_id=issue_id,
            severity=severity, frame=frame,
            details=details or {},
        ))
        # Cap issue history
        if len(self._issues) > 1000:
            self._issues = self._issues[-500:]

    def generate_report(self) -> QualityReport:
        duration = time.time() - self._start_time
        # Top issues by count
        issue_counts: dict[str, int] = defaultdict(int)
        for i in self._issues[-200:]:
            issue_counts[i.issue_id] += 1
        top = sorted(
            [{"issue_id": k, "count": v} for k, v in issue_counts.items()],
            key=lambda x: -x["count"],
        )[:5]

        return QualityReport(
            duration_seconds=duration,
            total_messages=self._total_messages,
            total_issues=self._total_issues,
            channels_active=len(self._active_channels),
            issues_by_severity=dict(self._by_severity),
            issues_by_channel=dict(self._by_channel),
            top_issues=top,
        )

    def __str__(self) -> str:
        r = self.generate_report()
        lines = [
            "=" * 50,
            "DATA QUALITY REPORT",
            "=" * 50,
            f"Duration: {r.duration_seconds:.1f}s",
            f"Messages: {r.total_messages}",
            f"Issues:   {r.total_issues}",
            f"Channels: {r.channels_active}",
        ]
        if r.top_issues:
            lines.append("-" * 50)
            lines.append("Top issues:")
            for issue in r.top_issues:
                lines.append(f"  {issue['issue_id']}: {issue['count']}")
        lines.append("=" * 50)
        return "\n".join(lines)
