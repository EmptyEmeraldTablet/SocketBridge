"""
Protocol Messages — RawMessage, session metadata, and frame data types.

Used by the persistence layer for recording and replay.
"""

import time
import json
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator

from protocol.schema import MessageType, SensorMeta


class RawMessage(BaseModel):
    """
    Complete raw message as received from or sent to Lua.

    Supports both v2.x (channel_meta) and v3.0 (sensors) formats.
    Used as the canonical recording format.
    """

    version: str = Field(default="3.0")
    type: str = Field(..., alias="msg_type")
    timestamp: int = 0
    frame: int = 0
    room_index: int = -1

    # v3.0 fields
    seq: Optional[int] = None
    game_time: Optional[int] = None
    prev_frame: Optional[int] = None
    sensors: Optional[dict[str, SensorMeta]] = None

    # v2.x backward compat
    channel_meta: Optional[dict[str, Any]] = None

    # Data
    payload: Optional[dict[str, Any]] = None
    channels: Optional[list[str]] = None

    # Event fields
    event_type: Optional[str] = None
    event_data: Optional[dict[str, Any]] = None

    # Metadata
    received_at: float = Field(default_factory=time.time)

    model_config = {"extra": "allow", "populate_by_name": True}

    @field_validator("version", mode="before")
    @classmethod
    def _normalize_version(cls, v) -> str:
        if isinstance(v, (int, float)):
            return str(v)
        return str(v) if v else "2.0"

    @field_validator("timestamp", mode="before")
    @classmethod
    def _normalize_timestamp(cls, v) -> int:
        if v is None:
            return 0
        ts = int(v) if isinstance(v, (int, float)) else 0
        # Filter out Unix-epoch timestamps (game uses Isaac.GetTime() ms)
        if ts > 1_000_000_000_000:
            return 0
        return ts

    @property
    def is_data(self) -> bool:
        return self.type in ("DATA", "FULL")

    @property
    def is_event(self) -> bool:
        return self.type == "EVENT"

    @property
    def is_command(self) -> bool:
        return self.type in ("CMD", "COMMAND")

    def to_json_line(self) -> str:
        """Serialize as a JSON line (matching Lua's send format)."""
        data = self.model_dump(by_alias=True, exclude_none=True)
        # Remove internal Python fields
        data.pop("received_at", None)
        # Restore 'type' key from alias
        if "msg_type" in data:
            data["type"] = data.pop("msg_type")
        return json.dumps(data, ensure_ascii=False) + "\n"

    @classmethod
    def from_json_line(cls, line: str) -> "RawMessage":
        """Parse from a JSON line."""
        data = json.loads(line)
        if "type" in data and "msg_type" not in data:
            data = data.copy()
            data["msg_type"] = data.pop("type")
        return cls(**data)

    @classmethod
    def from_dict(cls, data: dict) -> "RawMessage":
        if "type" in data and "msg_type" not in data:
            data = data.copy()
            data["msg_type"] = data.pop("type")
        return cls(**data)


class SessionMetadata(BaseModel):
    """Recording session metadata."""

    session_id: str
    start_time: float = Field(default_factory=time.time)
    start_timestamp: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    end_time: Optional[float] = None
    host: str = "127.0.0.1"
    port: int = 9527

    # Stats
    total_frames: int = 0
    total_events: int = 0
    total_messages: int = 0
    duration: float = 0.0

    # Protocol
    protocol_version: str = "3.0"

    # Custom metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}

    @property
    def duration_formatted(self) -> str:
        mins, secs = divmod(int(self.duration), 60)
        return f"{mins:02d}:{secs:02d}"


class FrameData(BaseModel):
    """All messages for a single frame (used in replay)."""

    frame: int = 0
    timestamp: int = 0
    room_index: int = -1
    messages: list[RawMessage] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def get_payload(self, channel: str) -> Optional[Any]:
        for msg in self.messages:
            if msg.payload and channel in msg.payload:
                return msg.payload[channel]
        return None
