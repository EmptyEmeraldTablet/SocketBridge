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
from .protocol.schema import (
    DataMessageSchema,
    EventMessageSchema,
    Vector2DSchema,
    PlayerPositionData,
    PlayerStatsData,
    PlayerHealthData,
    PlayerInventoryData,
    EnemyData,
    ProjectilesData,
    RoomInfoData,
    RoomLayoutData,
    PickupData,
    BombData,
    FireHazardData,
    InteractableData,
)
from .validation.known_issues import (
    KnownIssueRegistry,
    KnownIssue,
    ValidationIssue,
    IssueSeverity,
    IssueSource,
)

__all__ = [
    "MessageTimingInfo",
    "TimingMonitor",
    "TimingIssue",
    "ChannelTimingInfo",
    "TimingIssueType",
    "DataMessageSchema",
    "EventMessageSchema",
    "Vector2DSchema",
    "PlayerPositionData",
    "PlayerStatsData",
    "PlayerHealthData",
    "PlayerInventoryData",
    "EnemyData",
    "ProjectilesData",
    "RoomInfoData",
    "RoomLayoutData",
    "PickupData",
    "BombData",
    "FireHazardData",
    "InteractableData",
    "KnownIssueRegistry",
    "KnownIssue",
    "ValidationIssue",
    "IssueSeverity",
    "IssueSource",
]
