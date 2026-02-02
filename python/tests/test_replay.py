"""
Tests for core.replay module - 录制回放模块测试
"""

import pytest
import json
import tempfile
import time
from pathlib import Path
from typing import Dict, Any

from core.replay.message import (
    RawMessage,
    SessionMetadata,
    FrameData,
    ChannelMeta,
    MessageType,
    CollectInterval,
)
from core.replay.recorder import DataRecorder, RecorderConfig, RecordingSession
from core.replay.replayer import DataReplayer, ReplayerConfig, ReplayState
from core.replay.session import SessionManager, SessionInfo


class TestRawMessage:
    """RawMessage 测试"""

    def test_create_basic_message(self):
        """测试创建基本消息"""
        msg = RawMessage(msg_type="DATA", frame=100, room_index=5)
        assert msg.type == "DATA"
        assert msg.frame == 100
        assert msg.room_index == 5
        assert msg.version == "2.1"

    def test_create_from_dict(self):
        """测试从字典创建"""
        data = {
            "version": 2,
            "type": "DATA",
            "timestamp": 12345,
            "frame": 100,
            "room_index": 5,
            "payload": {"PLAYER_POSITION": {"1": {"pos": {"x": 100, "y": 200}}}},
            "channels": ["PLAYER_POSITION"],
        }
        msg = RawMessage.from_dict(data)
        assert msg.version == "2"
        assert msg.type == "DATA"
        assert msg.frame == 100
        assert msg.payload is not None
        assert "PLAYER_POSITION" in msg.payload

    def test_version_normalization(self):
        """测试版本号标准化"""
        # 整数版本
        msg1 = RawMessage.from_dict({"version": 2, "type": "DATA", "frame": 0, "room_index": 0})
        assert msg1.version == "2"

        # 字符串版本
        msg2 = RawMessage.from_dict({"version": "2.1", "type": "DATA", "frame": 0, "room_index": 0})
        assert msg2.version == "2.1"

    def test_timestamp_filter(self):
        """测试时间戳过滤"""
        # 正常时间戳
        msg1 = RawMessage.from_dict({"version": 2, "type": "DATA", "timestamp": 12345, "frame": 0, "room_index": 0})
        assert msg1.timestamp == 12345

        # Unix 时间戳（过大，应被过滤）
        msg2 = RawMessage.from_dict({"version": 2, "type": "DATA", "timestamp": 1700000000000, "frame": 0, "room_index": 0})
        assert msg2.timestamp == 0

    def test_to_json(self):
        """测试 JSON 序列化"""
        msg = RawMessage(msg_type="DATA", frame=100, room_index=5)
        json_str = msg.to_json()
        parsed = json.loads(json_str)
        assert parsed["frame"] == 100
        assert parsed["room_index"] == 5

    def test_from_json(self):
        """测试 JSON 反序列化"""
        json_str = '{"version": "2.1", "type": "DATA", "timestamp": 0, "frame": 100, "room_index": 5}'
        msg = RawMessage.from_json(json_str)
        assert msg.frame == 100

    def test_is_data_message(self):
        """测试消息类型判断"""
        data_msg = RawMessage(msg_type="DATA", frame=0, room_index=0)
        assert data_msg.is_data_message is True

        event_msg = RawMessage(msg_type="EVENT", frame=0, room_index=0)
        assert event_msg.is_event_message is True

    def test_channel_meta(self):
        """测试通道元数据"""
        msg = RawMessage.from_dict({
            "version": "2.1",
            "type": "DATA",
            "frame": 100,
            "room_index": 5,
            "channel_meta": {
                "PLAYER_POSITION": {
                    "channel": "PLAYER_POSITION",
                    "collect_frame": 100,
                    "collect_time": 12345,
                    "interval": "HIGH",
                    "stale_frames": 0,
                }
            }
        })
        assert msg.is_v21 is True
        assert msg.get_channel_staleness("PLAYER_POSITION") == 0


class TestSessionMetadata:
    """SessionMetadata 测试"""

    def test_create_session_metadata(self):
        """测试创建会话元数据"""
        meta = SessionMetadata(session_id="test_session")
        assert meta.session_id == "test_session"
        assert meta.total_frames == 0
        assert meta.protocol_version == "2.1"

    def test_duration_formatted(self):
        """测试持续时间格式化"""
        meta = SessionMetadata(session_id="test", duration=125.5)
        assert meta.duration_formatted == "02:05"


class TestFrameData:
    """FrameData 测试"""

    def test_create_frame_data(self):
        """测试创建帧数据"""
        frame = FrameData(frame=100, timestamp=12345, room_index=5)
        assert frame.frame == 100
        assert frame.message_count == 0

    def test_get_payload(self):
        """测试获取通道数据"""
        msg = RawMessage(
            msg_type="DATA",
            frame=100,
            room_index=5,
            payload={"PLAYER_POSITION": {"1": {"pos": {"x": 100, "y": 200}}}},
        )
        frame = FrameData(frame=100, messages=[msg])
        payload = frame.get_payload("PLAYER_POSITION")
        assert payload is not None
        assert payload["1"]["pos"]["x"] == 100


class TestDataRecorder:
    """DataRecorder 测试"""

    def test_create_recorder(self):
        """测试创建录制器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = RecorderConfig(output_dir=tmpdir)
            recorder = DataRecorder(config)
            assert recorder.is_recording is False

    def test_start_stop_session(self):
        """测试开始和停止会话"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = RecorderConfig(output_dir=tmpdir, auto_save_interval=1000)
            recorder = DataRecorder(config)

            session = recorder.start_session("test_session")
            assert recorder.is_recording is True
            assert session.session_id == "test_session"

            metadata = recorder.stop_session()
            assert recorder.is_recording is False
            assert metadata is not None

    def test_record_message(self):
        """测试录制消息"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = RecorderConfig(output_dir=tmpdir, buffer_size=10, auto_save_interval=1000)
            recorder = DataRecorder(config)

            recorder.start_session("test_session")

            msg = RawMessage(msg_type="DATA", frame=100, room_index=5)
            result = recorder.record_message(msg)
            assert result is True

            recorder.stop_session()


class TestDataReplayer:
    """DataReplayer 测试"""

    def test_create_replayer(self):
        """测试创建回放器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ReplayerConfig(recordings_dir=tmpdir)
            replayer = DataReplayer(config)
            assert replayer.state == ReplayState.STOPPED


class TestSessionManager:
    """SessionManager 测试"""

    def test_create_manager(self):
        """测试创建会话管理器"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(tmpdir)
            sessions = manager.list_sessions()
            assert len(sessions) == 0

    def test_get_stats(self):
        """测试获取统计信息"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(tmpdir)
            stats = manager.get_stats()
            assert stats["total_sessions"] == 0


class TestEnums:
    """枚举测试"""

    def test_message_type(self):
        """测试消息类型枚举"""
        assert MessageType.DATA.value == "DATA"
        assert MessageType.FULL.value == "FULL"
        assert MessageType.EVENT.value == "EVENT"

    def test_collect_interval(self):
        """测试采集频率枚举"""
        assert CollectInterval.HIGH.value == "HIGH"
        assert CollectInterval.LOW.value == "LOW"
        assert CollectInterval.ON_CHANGE.value == "ON_CHANGE"
