"""
Core Replay Message Types - 消息类型定义

基于 Pydantic 的消息类型，完全兼容 v2.1 协议。
"""

import time
import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator


class MessageType(str, Enum):
    """消息类型枚举"""

    DATA = "DATA"
    FULL = "FULL"
    FULL_STATE = "FULL"  # 别名
    EVENT = "EVENT"
    COMMAND = "CMD"


class CollectInterval(str, Enum):
    """采集频率枚举"""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    RARE = "RARE"
    ON_CHANGE = "ON_CHANGE"


class ChannelMeta(BaseModel):
    """通道采集元数据（v2.1）"""

    model_config = {"extra": "allow"}

    channel: str = Field(default="", description="通道名称")
    collect_frame: int = Field(default=0, ge=0, description="数据采集帧号")
    collect_time: int = Field(default=0, ge=0, description="数据采集时间戳")
    interval: str = Field(default="HIGH", description="采集频率")
    stale_frames: int = Field(default=0, ge=0, description="数据过期帧数")


class RawMessage(BaseModel):
    """
    完整的原始消息结构（v2.1 协议）

    包含从 Lua 端接收的所有元数据，支持时序扩展。
    """

    # 基础字段 (v2.0)
    version: str = Field(default="2.1", description="协议版本")
    type: str = Field(..., alias="msg_type", description="消息类型")
    timestamp: int = Field(default=0, ge=0, description="时间戳")
    frame: int = Field(default=0, ge=0, description="帧号")
    room_index: int = Field(default=-1, description="房间索引")

    # v2.1 时序字段
    seq: Optional[int] = Field(default=None, ge=0, description="消息序列号")
    game_time: Optional[int] = Field(default=None, ge=0, description="游戏时间戳")
    prev_frame: Optional[int] = Field(default=None, description="上一帧号")
    channel_meta: Optional[Dict[str, ChannelMeta]] = Field(
        default=None, description="通道元数据"
    )

    # 数据负载
    payload: Optional[Dict[str, Any]] = Field(default=None, description="数据负载")
    channels: Optional[List[str]] = Field(default=None, description="通道列表")

    # 事件字段
    event_type: Optional[str] = Field(default=None, description="事件类型")
    event_data: Optional[Dict[str, Any]] = Field(default=None, description="事件数据")

    # 元数据
    received_at: float = Field(default_factory=time.time, description="接收时间戳")

    model_config = {"extra": "allow", "populate_by_name": True}

    @field_validator("version", mode="before")
    @classmethod
    def normalize_version(cls, v: Union[int, str, float]) -> str:
        """标准化版本号为字符串格式"""
        if isinstance(v, (int, float)):
            return str(v)
        return str(v)

    @field_validator("timestamp", mode="before")
    @classmethod
    def normalize_timestamp(cls, v: Any) -> int:
        """处理时间戳，过滤异常值"""
        if v is None:
            return 0
        ts = int(v) if isinstance(v, (int, float)) else 0
        # Isaac.GetTime() 返回游戏内毫秒数，通常 < 100,000,000
        # Unix 时间戳（毫秒）通常 > 1,000,000,000,000
        if ts > 1_000_000_000_000:
            return 0  # 使用占位值
        return ts

    @field_validator("channel_meta", mode="before")
    @classmethod
    def parse_channel_meta(cls, v: Any) -> Optional[Dict[str, ChannelMeta]]:
        """解析通道元数据"""
        if v is None:
            return None
        if isinstance(v, dict):
            result = {}
            for key, val in v.items():
                if isinstance(val, dict):
                    result[key] = ChannelMeta(**val)
                elif isinstance(val, ChannelMeta):
                    result[key] = val
            return result if result else None
        return None

    @property
    def is_data_message(self) -> bool:
        """是否为数据消息"""
        return self.type in (MessageType.DATA.value, MessageType.FULL.value)

    @property
    def is_event_message(self) -> bool:
        """是否为事件消息"""
        return self.type == MessageType.EVENT.value

    @property
    def is_v21(self) -> bool:
        """是否为 v2.1 协议"""
        return self.seq is not None or self.channel_meta is not None

    def get_channel_staleness(self, channel: str) -> int:
        """获取通道数据过期帧数"""
        if self.channel_meta and channel in self.channel_meta:
            return self.channel_meta[channel].stale_frames
        return 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = {
            "version": self.version,
            "type": self.type,
            "timestamp": self.timestamp,
            "frame": self.frame,
            "room_index": self.room_index,
            "received_at": self.received_at,
        }

        # 添加可选字段
        if self.seq is not None:
            data["seq"] = self.seq
        if self.game_time is not None:
            data["game_time"] = self.game_time
        if self.prev_frame is not None:
            data["prev_frame"] = self.prev_frame
        if self.channel_meta:
            data["channel_meta"] = {
                k: v.model_dump() for k, v in self.channel_meta.items()
            }
        if self.payload:
            data["payload"] = self.payload
        if self.channels:
            data["channels"] = self.channels
        if self.event_type:
            data["event_type"] = self.event_type
        if self.event_data:
            data["event_data"] = self.event_data

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RawMessage":
        """从字典创建"""
        # 处理 type 字段别名
        if "type" in data and "msg_type" not in data:
            data = data.copy()
            data["msg_type"] = data.pop("type")
        return cls(**data)

    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return json.dumps(self.to_dict())

    def to_json_line(self) -> str:
        """转换为 JSON 行格式（Lua 端发送格式）"""
        return self.to_json() + "\n"

    @classmethod
    def from_json(cls, json_str: str) -> "RawMessage":
        """从 JSON 字符串创建"""
        return cls.from_dict(json.loads(json_str))


class SessionMetadata(BaseModel):
    """录制会话元数据"""

    session_id: str = Field(..., description="会话ID")
    start_time: float = Field(default_factory=time.time, description="开始时间戳")
    start_timestamp: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        description="开始时间",
    )
    end_time: Optional[float] = Field(default=None, description="结束时间戳")
    host: str = Field(default="127.0.0.1", description="主机地址")
    port: int = Field(default=9527, ge=0, description="端口号")

    # 统计信息
    total_frames: int = Field(default=0, ge=0, description="总帧数")
    total_events: int = Field(default=0, ge=0, description="总事件数")
    total_messages: int = Field(default=0, ge=0, description="总消息数")
    duration: float = Field(default=0.0, ge=0, description="持续时间（秒）")

    # 协议信息
    protocol_version: str = Field(default="2.1", description="协议版本")

    # 自定义元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="自定义元数据")

    model_config = {"extra": "allow"}

    @property
    def duration_formatted(self) -> str:
        """格式化持续时间"""
        mins, secs = divmod(int(self.duration), 60)
        return f"{mins:02d}:{secs:02d}"


class FrameData(BaseModel):
    """单帧数据"""

    frame: int = Field(..., ge=0, description="帧号")
    timestamp: int = Field(default=0, ge=0, description="时间戳")
    room_index: int = Field(default=-1, description="房间索引")
    messages: List[RawMessage] = Field(default_factory=list, description="该帧的消息")
    channels: List[str] = Field(default_factory=list, description="该帧包含的通道")

    @property
    def message_count(self) -> int:
        return len(self.messages)

    def get_payload(self, channel: str) -> Optional[Any]:
        """获取指定通道的数据"""
        for msg in self.messages:
            if msg.payload and channel in msg.payload:
                return msg.payload[channel]
        return None

    def get_all_payloads(self) -> Dict[str, Any]:
        """获取所有通道数据"""
        result = {}
        for msg in self.messages:
            if msg.payload:
                result.update(msg.payload)
        return result
