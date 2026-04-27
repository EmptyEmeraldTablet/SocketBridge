"""
Core Module - SocketBridge 重构核心层

包含:
- connection: 网络连接与事件系统
- protocol: 协议模式定义与版本管理
- validation: 数据验证与已知问题管理
- replay: 录制与回放系统
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
from .replay import (
    RawMessage,
    SessionMetadata,
    FrameData,
    MessageType,
    CollectInterval,
    DataRecorder,
    RecorderConfig,
    RecordingSession,
    DataReplayer,
    ReplayerConfig,
    ReplaySession,
    create_replayer,
    SessionManager,
    SessionInfo,
    list_sessions,
    get_latest_session,
)

__all__ = [
    # Timing
    "MessageTimingInfo",
    "TimingMonitor",
    "TimingIssue",
    "ChannelTimingInfo",
    "TimingIssueType",
    # Schema
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
    # Validation
    "KnownIssueRegistry",
    "KnownIssue",
    "ValidationIssue",
    "IssueSeverity",
    "IssueSource",
    # Replay
    "RawMessage",
    "SessionMetadata",
    "FrameData",
    "MessageType",
    "CollectInterval",
    "DataRecorder",
    "RecorderConfig",
    "RecordingSession",
    "DataReplayer",
    "ReplayerConfig",
    "ReplaySession",
    "create_replayer",
    "SessionManager",
    "SessionInfo",
    "list_sessions",
    "get_latest_session",
]
