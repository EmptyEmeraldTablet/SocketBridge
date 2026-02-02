"""
Core Replay Module - 录制与回放系统

提供基于新架构的录制和回放功能：
- message: 消息类型定义（基于 Pydantic）
- recorder: 数据录制器
- replayer: 数据回放器
- session: 会话管理
"""

from .message import (
    RawMessage,
    SessionMetadata,
    FrameData,
    MessageType,
    CollectInterval,
)
from .recorder import (
    DataRecorder,
    RecorderConfig,
    RecordingSession,
)
from .replayer import (
    DataReplayer,
    ReplayerConfig,
    ReplaySession,
    create_replayer,
)
from .session import (
    SessionManager,
    SessionInfo,
    list_sessions,
    get_latest_session,
)

__all__ = [
    # Message types
    "RawMessage",
    "SessionMetadata",
    "FrameData",
    "MessageType",
    "CollectInterval",
    # Recorder
    "DataRecorder",
    "RecorderConfig",
    "RecordingSession",
    # Replayer
    "DataReplayer",
    "ReplayerConfig",
    "ReplaySession",
    "create_replayer",
    # Session
    "SessionManager",
    "SessionInfo",
    "list_sessions",
    "get_latest_session",
]
