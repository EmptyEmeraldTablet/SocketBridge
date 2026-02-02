"""
Core Module - SocketBridge 重构核心层

包含:
- connection: 网络连接与事件系统
- protocol: 协议模式定义与版本管理
- validation: 数据验证与已知问题管理
"""

from .protocol.timing import (
    MessageTimingInfo,
    TimingMonitor,
    TimingIssue,
    ChannelTimingInfo,
    TimingIssueType,
)

__all__ = [
    "MessageTimingInfo",
    "TimingMonitor",
    "TimingIssue",
    "ChannelTimingInfo",
    "TimingIssueType",
]
