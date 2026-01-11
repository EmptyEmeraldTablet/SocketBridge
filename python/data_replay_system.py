"""
SocketBridge 数据采集与回放系统

功能:
1. 增强版数据录制 - 完整保存每一帧的原始消息格式
2. Lua 模拟发送端 - 按照录制时的规则重现数据发送
3. 回放控制器 - 精确控制回放流程

设计目标:
- 录制: 完整保存原始消息的所有元数据
- 回放: 完全按照 Lua 端的发送规则重现数据流
- 灵活性: 支持任意回放速度、循环播放、跳帧等

环境变量配置:
- SOCKETBRIDGE_RECORDINGS_DIR: 录制文件存储目录 (默认: ./recordings)
- SOCKETBRIDGE_HOST: 模拟服务器监听地址 (默认: 127.0.0.1)
- SOCKETBRIDGE_PORT: 模拟服务器监听端口 (默认: 9527)
"""

import json
import time
import gzip
import socket
import threading
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable, Generator, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("DataReplaySystem")


# ============================================================================
# 环境变量配置
# ============================================================================

# 默认录制目录（可通过环境变量覆盖）
DEFAULT_RECORDINGS_DIR = os.environ.get("SOCKETBRIDGE_RECORDINGS_DIR", "./recordings")

# 默认服务器配置（可通过环境变量覆盖）
DEFAULT_HOST = os.environ.get("SOCKETBRIDGE_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("SOCKETBRIDGE_PORT", "9527"))


class MessageType(Enum):
    """消息类型枚举 (与 Lua 端保持一致)"""

    DATA = "DATA"
    FULL_STATE = "FULL"
    EVENT = "EVENT"
    COMMAND = "CMD"


class CollectInterval(Enum):
    """采集频率枚举 (与 Lua 端保持一致)"""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    ON_CHANGE = "ON_CHANGE"


@dataclass
class RawMessage:
    """
    完整的原始消息结构
    包含从 Lua 端接收的所有元数据

    消息格式与 DATA_PROTOCOL.md 保持一致:
    {
        "version": 2,           # 版本号 (int)
        "type": "DATA",         # 消息类型 (str)
        "frame": 123,           # 帧号 (int)
        "room_index": 5,        # 房间索引 (int)
        "payload": {...},       # 数据负载 (dict)
        "channels": ["..."],    # 数据通道列表 (list)
        "timestamp": 1234567890 # 时间戳 (int, Lua Isaac.GetTime())
    }
    """

    version: int
    msg_type: str
    timestamp: int
    frame: int
    room_index: int
    payload: Optional[Dict[str, Any]] = None
    channels: Optional[List[str]] = None
    event_type: Optional[str] = None
    event_data: Optional[Dict] = None
    received_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "version": self.version,
            "type": self.msg_type,
            "timestamp": self.timestamp,
            "frame": self.frame,
            "room_index": self.room_index,
            "payload": self.payload,
            "channels": self.channels,
            "event_type": self.event_type,
            "event_data": self.event_data,
            "received_at": self.received_at,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "RawMessage":
        return cls(
            version=int(data["version"]),
            msg_type=data["type"],
            timestamp=data["timestamp"],
            frame=data["frame"],
            room_index=data["room_index"],
            payload=data.get("payload"),
            channels=data.get("channels"),
            event_type=data.get("event_type"),
            event_data=data.get("event_data"),
            received_at=data.get("received_at", time.time()),
        )

    def to_json_line(self) -> str:
        """转换为 JSON 行格式（与 Lua 端发送格式一致）

        Lua 端发送格式: json.encode(data) .. "\n"
        每条消息以换行符结尾
        """
        return json.dumps(self.to_dict()) + "\n"


@dataclass
class SessionMetadata:
    """录制会话元数据"""

    session_id: str
    start_time: float
    start_timestamp: str
    lua_host: str = DEFAULT_HOST
    lua_port: int = DEFAULT_PORT
    total_frames: int = 0
    total_events: int = 0
    total_messages: int = 0
    duration: float = 0.0
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "start_timestamp": self.start_timestamp,
            "lua_host": self.lua_host,
            "lua_port": self.lua_port,
            "total_frames": self.total_frames,
            "total_events": self.total_events,
            "total_messages": self.total_messages,
            "duration": self.duration,
            "metadata": self.metadata,
        }

    def save(self, path: Path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: Path) -> "SessionMetadata":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


@dataclass
class FrameInfo:
    """帧信息摘要"""

    frame: int
    room_index: int
    channel_count: int
    message_count: int

    @classmethod
    def from_message(cls, msg: RawMessage) -> "FrameInfo":
        return cls(
            frame=msg.frame,
            room_index=msg.room_index,
            channel_count=len(msg.channels) if msg.channels else 0,
            message_count=1,
        )


class EnhancedDataRecorder:
    """
    增强版数据录制器

    与基础版 DataRecorder 的区别:
    1. 录制完整的原始消息（包括所有元数据）
    2. 支持暂停/恢复录制
    3. 自动生成会话摘要
    4. 支持环境变量配置录制目录
    """

    def __init__(self, output_dir: str = DEFAULT_RECORDINGS_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.recording = False
        self.paused = False
        self.current_session: Optional[SessionMetadata] = None

        self.message_buffer: List[RawMessage] = []
        self.frame_index: Dict[int, List[RawMessage]] = {}
        self.buffer_size = 500

        self.stats = {
            "messages_recorded": 0,
            "frames_recorded": 0,
            "events_recorded": 0,
            "sessions": 0,
            "bytes_written": 0,
        }

        self.on_message: Optional[Callable[[RawMessage], None]] = None
        self.on_frame: Optional[Callable[[int, List[RawMessage]], None]] = None

        self._last_frame = -1
        self._start_wall_time = 0.0

    def start_session(self, metadata: Optional[Dict] = None):
        if self.recording:
            logger.warning("Already recording, stopping current session first")
            self.end_session()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.current_session = SessionMetadata(
            session_id=f"session_{timestamp}",
            start_time=time.time(),
            start_timestamp=timestamp,
            metadata=metadata or {},
        )

        self.message_buffer.clear()
        self.frame_index.clear()
        self._last_frame = -1
        self._start_wall_time = time.time()
        self.recording = True
        self.paused = False

        self.stats["sessions"] += 1
        logger.info(f"Recording session started: {self.current_session.session_id}")
        logger.info(f"Output directory: {self.output_dir}")

    def end_session(self, reason: str = "manual"):
        if not self.recording or not self.current_session:
            return

        self.recording = False
        self.paused = False

        self.current_session.duration = time.time() - self._start_wall_time
        self.current_session.total_messages = self.stats["messages_recorded"]
        self.current_session.total_frames = self.stats["frames_recorded"]
        if self.message_buffer:
            self.current_session.total_events = sum(
                1
                for msg in self.message_buffer
                if msg.msg_type == MessageType.EVENT.value
            )

        self._save_session()

        session_id = (
            self.current_session.session_id if self.current_session else "unknown"
        )
        logger.info(
            f"Recording session ended: {session_id} "
            f"({reason}) - {self.stats['messages_recorded']} messages, "
            f"{self.stats['frames_recorded']} frames"
        )

        self.current_session = None

    def pause(self):
        if self.recording and not self.paused:
            self.paused = True
            logger.info("Recording paused")

    def resume(self):
        if self.recording and self.paused:
            self.paused = False
            logger.info("Recording resumed")

    def record_message(self, msg: RawMessage):
        """录制一条消息"""
        if not self.recording or self.paused:
            return

        self.message_buffer.append(msg)
        self.stats["messages_recorded"] += 1

        if msg.frame not in self.frame_index:
            self.frame_index[msg.frame] = []
            self.stats["frames_recorded"] = max(
                self.stats["frames_recorded"], msg.frame + 1
            )
        self.frame_index[msg.frame].append(msg)

        if self.on_message:
            self.on_message(msg)

        if msg.frame != self._last_frame and self.on_frame:
            self.on_frame(msg.frame, self.frame_index[msg.frame])
        self._last_frame = msg.frame

        if len(self.message_buffer) >= self.buffer_size:
            self._flush_buffer()

    def _flush_buffer(self):
        if not self.current_session or not self.message_buffer:
            return

        session_id = self.current_session.session_id
        chunk_id = len(list(self.output_dir.glob(f"{session_id}_chunk_*.json.gz")))

        chunk_data = {
            "session_id": session_id,
            "chunk_id": chunk_id,
            "messages": [msg.to_dict() for msg in self.message_buffer],
        }

        chunk_file = self.output_dir / f"{session_id}_chunk_{chunk_id:04d}.json.gz"

        with gzip.open(chunk_file, "wt", encoding="utf-8") as f:
            json.dump(chunk_data, f)

        self.message_buffer.clear()
        self.stats["bytes_written"] += chunk_file.stat().st_size

        logger.debug(f"Saved chunk: {chunk_file.name}")

    def _save_session(self):
        if not self.current_session:
            return

        session_id = self.current_session.session_id

        self._flush_buffer()

        meta_file = self.output_dir / f"{session_id}_meta.json"
        self.current_session.save(meta_file)

        summary_file = self.output_dir / f"{session_id}_summary.json"
        self._save_summary(summary_file)

        logger.info(f"Session saved: {session_id}")

    def _save_summary(self, path: Path):
        frames = []
        for frame_num in sorted(self.frame_index.keys()):
            msgs = self.frame_index[frame_num]
            data_channels = [
                m.channels for m in msgs if m.msg_type == MessageType.DATA.value
            ]
            if data_channels:
                frames.append(
                    {
                        "frame": frame_num,
                        "channels": data_channels[0],
                        "message_count": len(msgs),
                    }
                )

        summary = {
            "session_id": self.current_session.session_id
            if self.current_session
            else "unknown",
            "duration": self.current_session.duration if self.current_session else 0,
            "total_frames": self.current_session.total_frames
            if self.current_session
            else 0,
            "total_messages": self.current_session.total_messages
            if self.current_session
            else 0,
            "total_events": self.current_session.total_events
            if self.current_session
            else 0,
            "frame_summary": frames[:100],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    def get_stats(self) -> Dict:
        return {
            **self.stats,
            "recording": self.recording,
            "paused": self.paused,
            "current_session": self.current_session.session_id
            if self.current_session
            else None,
            "buffer_size": len(self.message_buffer),
        }


class LuaSimulator:
    """
    Lua 模拟发送端

    功能:
    1. 作为 TCP 服务器，模拟 Lua 模组的连接行为
    2. 按照录制数据的规则，精确重现数据发送
    3. 支持暂停、恢复、跳帧等控制

    协议兼容性:
    - 与 Lua 端 main.lua 中的 Network 层完全兼容
    - 使用相同的 JSON 格式和换行符分隔
    - 默认端口 9527，与游戏模组一致

    环境变量:
    - SOCKETBRIDGE_HOST: 服务器监听地址 (默认: 127.0.0.1)
    - SOCKETBRIDGE_PORT: 服务器监听端口 (默认: 9527)
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        reuse_addr: bool = True,
    ):
        self.host = host
        self.port = port
        self.reuse_addr = reuse_addr

        self.server: Optional[socket.socket] = None
        self.client: Optional[socket.socket] = None
        self.running = False

        self.messages: List[RawMessage] = []
        self.current_index = 0

        self.playback_speed = 1.0
        self.frame_delay: Dict[int, float] = {}

        self.paused = False
        self.stop_event = threading.Event()

        self.on_connect: Optional[Callable[[], None]] = None
        self.on_disconnect: Optional[Callable[[], None]] = None
        self.on_message_sent: Optional[Callable[[RawMessage], None]] = None
        self.on_playback_complete: Optional[Callable[[], None]] = None

        self._accept_thread: Optional[threading.Thread] = None
        self._send_thread: Optional[threading.Thread] = None

        self.stats = {
            "messages_sent": 0,
            "frames_sent": 0,
            "start_time": 0.0,
        }

        logger.info(
            f"LuaSimulator initialized on {host}:{port} (reuse_addr={reuse_addr})"
        )

    def load_messages(self, messages: List[RawMessage]):
        """加载要回放的消息"""
        self.messages = sorted(messages, key=lambda m: (m.frame, m.timestamp))
        self.current_index = 0
        logger.info(f"Loaded {len(self.messages)} messages for playback")

    def load_from_session(self, session_path: str):
        """从录制会话加载消息"""
        session_dir = Path(session_path)

        messages = []
        for chunk_file in sorted(session_dir.glob("*_chunk_*.json.gz")):
            with gzip.open(chunk_file, "rt", encoding="utf-8") as f:
                chunk_data = json.load(f)
                for msg_dict in chunk_data.get("messages", []):
                    messages.append(RawMessage.from_dict(msg_dict))

        self.load_messages(messages)
        logger.info(f"Loaded session from {session_path}: {len(messages)} messages")

    def start(self):
        """启动模拟服务器"""
        if self.running:
            logger.warning("Server already running")
            return

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # 设置 SO_REUSEADDR（与 isaac_bridge.py 一致）
        if self.reuse_addr:
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server.bind((self.host, self.port))
            self.server.listen(1)
            self.running = True
            self.stop_event.clear()

            self._accept_thread = threading.Thread(
                target=self._accept_loop, daemon=True
            )
            self._accept_thread.start()

            logger.info(f"LuaSimulator server started on {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            self.running = False
            self.server = None
            raise

    def stop(self):
        """停止模拟服务器"""
        if not self.running:
            return

        self.running = False
        self.stop_event.set()

        if self.client:
            try:
                self.client.shutdown(socket.SHUT_RDWR)
            except:
                pass
            try:
                self.client.close()
            except:
                pass
            self.client = None

        if self.server:
            try:
                self.server.shutdown(socket.SHUT_RDWR)
            except:
                pass
            try:
                self.server.close()
            except:
                pass
            self.server = None

        if self._accept_thread and self._accept_thread.is_alive():
            self._accept_thread.join(timeout=1.0)

        logger.info("LuaSimulator server stopped")

    def play(self):
        """开始/恢复回放"""
        if not self.messages:
            logger.warning("No messages loaded")
            return

        if self.paused:
            self.paused = False
            logger.info("Playback resumed")
            return

        self.current_index = 0
        self.stats["start_time"] = time.time()

        self._send_thread = threading.Thread(target=self._send_loop, daemon=True)
        self._send_thread.start()

        logger.info(f"Playback started: {len(self.messages)} messages")

    def pause(self):
        """暂停回放"""
        self.paused = True
        logger.info("Playback paused")

    def stop_playback(self):
        """停止回放"""
        self.paused = False
        self.stop_event.set()
        self.current_index = 0
        logger.info("Playback stopped")

    def seek(self, frame: int):
        """跳转到指定帧"""
        for i, msg in enumerate(self.messages):
            if msg.frame >= frame:
                self.current_index = i
                logger.info(f"Seeked to frame {frame} (message index {i})")
                return
        logger.warning(f"Frame {frame} not found")

    def set_speed(self, speed: float):
        """设置回放速度 (1.0 = 原始速度)"""
        self.playback_speed = max(0.1, min(10.0, speed))
        logger.info(f"Playback speed set to {self.playback_speed}x")

    def _accept_loop(self):
        """接受连接循环（与 isaac_bridge.py 保持一致）"""
        while self.running:
            if not self.server:
                break

            try:
                self.server.settimeout(1.0)
                client, addr = self.server.accept()

                # 关闭旧连接
                if self.client:
                    try:
                        self.client.close()
                    except:
                        pass

                self.client = client
                logger.info(f"Client connected: {addr}")

                if self.on_connect:
                    self.on_connect()

                self.play()

                if self._send_thread:
                    self._send_thread.join()
                self._send_thread = None

            except socket.timeout:
                continue
            except OSError as e:
                if self.running:
                    logger.error(f"Accept error: {e}")
                break
            except Exception as e:
                if self.running:
                    logger.error(f"Accept error: {e}")

    def _send_loop(self):
        """
        发送消息循环

        发送逻辑与 Lua 端一致:
        - JSON 编码 + 换行符分隔
        - 按时间戳计算延迟
        """
        last_frame_time = time.time()
        last_timestamp = 0

        while self.running and self.client and self.current_index < len(self.messages):
            if self.paused:
                time.sleep(0.1)
                continue

            msg = self.messages[self.current_index]

            # 计算发送时机
            if last_timestamp == 0:
                # 第一条消息，立即发送
                delay = 0.0
            else:
                # 根据时间戳计算延迟（Lua Isaac.GetTime() 返回毫秒）
                timestamp_diff = (msg.timestamp - last_timestamp) / 1000.0
                wall_diff = time.time() - last_frame_time
                delay = max(0, timestamp_diff / self.playback_speed - wall_diff)

            if delay > 0:
                time.sleep(delay)

            # 发送消息（与 Lua 端 Network.send 一致）
            try:
                json_line = msg.to_json_line()
                self.client.send(json_line.encode("utf-8"))

                self.stats["messages_sent"] += 1
                self.stats["frames_sent"] = max(self.stats["frames_sent"], msg.frame)

                if self.on_message_sent:
                    self.on_message_sent(msg)

                last_frame_time = time.time()
                last_timestamp = msg.timestamp
                self.current_index += 1

            except Exception as e:
                logger.error(f"Send error: {e}")
                break

        # 回放完成
        if self.current_index >= len(self.messages):
            logger.info(
                f"Playback complete: {self.stats['messages_sent']} messages, "
                f"{self.stats['frames_sent']} frames"
            )
            if self.on_playback_complete:
                self.on_playback_complete()

    def get_stats(self) -> Dict:
        """获取统计信息"""
        elapsed = (
            time.time() - self.stats["start_time"] if self.stats["start_time"] else 0
        )
        return {
            **self.stats,
            "elapsed_time": elapsed,
            "messages_remaining": len(self.messages) - self.current_index,
            "progress": self.current_index / len(self.messages) if self.messages else 0,
            "paused": self.paused,
        }


class SessionReplayer:
    """
    会话回放控制器

    功能:
    1. 协调录制和回放流程
    2. 提供高级 API 控制回放
    3. 支持实时数据处理

    环境变量:
    - SOCKETBRIDGE_RECORDINGS_DIR: 录制文件存储目录
    """

    def __init__(self, recordings_dir: str = DEFAULT_RECORDINGS_DIR):
        self.recordings_dir = Path(recordings_dir)

        self.recorder = EnhancedDataRecorder(recordings_dir)
        self.simulator = LuaSimulator()

        self.replaying = False
        self.current_session_id: Optional[str] = None

        self.on_frame: Optional[Callable[[int, RawMessage], None]] = None
        self.on_event: Optional[Callable[[RawMessage], None]] = None

    def start_recording(self, metadata: Optional[Dict] = None):
        """开始录制"""
        self.recorder.start_session(metadata)
        logger.info("Recording started")

    def stop_recording(self):
        """停止录制"""
        self.recorder.end_session()
        self.current_session_id = (
            self.recorder.current_session.session_id
            if self.recorder.current_session
            else None
        )
        logger.info(f"Recording stopped, session: {self.current_session_id}")

    def record_message(self, msg: RawMessage):
        """录制一条消息"""
        self.recorder.record_message(msg)

    def pause_recording(self):
        """暂停录制"""
        self.recorder.pause()

    def resume_recording(self):
        """恢复录制"""
        self.recorder.resume()

    def load_session(self, session_id: str) -> bool:
        """加载会话用于回放"""
        session_dir = self.recordings_dir / session_id

        if not session_dir.exists():
            logger.error(f"Session not found: {session_id}")
            return False

        try:
            self.simulator.load_from_session(str(session_dir))
            self.current_session_id = session_id
            logger.info(f"Session loaded: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to load session: {e}")
            return False

    def list_sessions(self) -> List[Dict]:
        """列出所有录制会话"""
        sessions = []

        for meta_file in self.recordings_dir.glob("*_meta.json"):
            try:
                meta = SessionMetadata.load(meta_file)
                sessions.append(
                    {
                        "id": meta.session_id,
                        "start_time": meta.start_timestamp,
                        "duration": meta.duration,
                        "frames": meta.total_frames,
                        "messages": meta.total_messages,
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to load session info: {e}")

        return sorted(sessions, key=lambda x: x["start_time"], reverse=True)

    def start_replay(self, session_id: Optional[str] = None, speed: float = 1.0):
        """开始回放"""
        if session_id:
            if not self.load_session(session_id):
                return

        if not self.simulator.messages:
            logger.error("No session loaded")
            return

        self.simulator.set_speed(speed)

        self.simulator.on_message_sent = self._handle_message_sent
        self.simulator.on_playback_complete = self._handle_playback_complete

        self.simulator.start()
        self.replaying = True

        logger.info(f"Replay started: {session_id or 'loaded session'}")

    def stop_replay(self):
        """停止回放"""
        self.simulator.stop_playback()
        self.simulator.stop()
        self.replaying = False
        logger.info("Replay stopped")

    def pause_replay(self):
        """暂停回放"""
        self.simulator.pause()

    def resume_replay(self):
        """恢复回放"""
        self.simulator.play()

    def seek(self, frame: int):
        """跳转到指定帧"""
        self.simulator.seek(frame)

    def set_speed(self, speed: float):
        """设置回放速度"""
        self.simulator.set_speed(speed)

    def _handle_message_sent(self, msg: RawMessage):
        """处理发送的消息"""
        if msg.msg_type == MessageType.DATA.value:
            if self.on_frame:
                self.on_frame(msg.frame, msg)
        elif msg.msg_type == MessageType.EVENT.value:
            if self.on_event:
                self.on_event(msg)

    def _handle_playback_complete(self):
        """回放完成处理"""
        self.replaying = False
        logger.info("Playback completed")

    def replay_session(
        self,
        session_id: str,
        speed: float = 1.0,
        frame_callback: Optional[Callable[[int, RawMessage], None]] = None,
        event_callback: Optional[Callable[[RawMessage], None]] = None,
        complete_callback: Optional[Callable[[], None]] = None,
    ):
        """便捷方法：直接回放一个会话"""
        self.on_frame = frame_callback
        self.on_event = event_callback

        if complete_callback:
            self.simulator.on_playback_complete = complete_callback

        self.start_replay(session_id, speed)

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            "recording": self.recorder.get_stats(),
            "simulator": self.simulator.get_stats(),
            "replaying": self.replaying,
            "current_session": self.current_session_id,
        }


def create_recorder(output_dir: str = DEFAULT_RECORDINGS_DIR) -> EnhancedDataRecorder:
    """创建录制器"""
    return EnhancedDataRecorder(output_dir)


def create_simulator(
    host: str = DEFAULT_HOST, port: int = DEFAULT_PORT
) -> LuaSimulator:
    """创建模拟器"""
    return LuaSimulator(host, port)


def create_replayer(
    recordings_dir: str = DEFAULT_RECORDINGS_DIR,
) -> SessionReplayer:
    """创建回放控制器"""
    return SessionReplayer(recordings_dir)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SocketBridge Data Replay System")
    parser.add_argument(
        "command",
        choices=["list", "replay"],
        help="Command: list=sessions, replay=replay session",
    )
    parser.add_argument("--session", "-s", type=str, default=None, help="Session ID")
    parser.add_argument("--speed", "-v", type=float, default=1.0, help="Playback speed")
    parser.add_argument(
        "--dir",
        "-d",
        type=str,
        default=DEFAULT_RECORDINGS_DIR,
        help="Recordings directory",
    )

    args = parser.parse_args()

    replayer = create_replayer(args.dir)

    if args.command == "list":
        sessions = replayer.list_sessions()
        print(f"Found {len(sessions)} sessions:")
        for s in sessions:
            print(
                f"  {s['id']}: {s['duration']:.1f}s, {s['frames']} frames, {s['messages']} messages"
            )

    elif args.command == "replay":
        if not args.session:
            sessions = replayer.list_sessions()
            if sessions:
                args.session = sessions[0]["id"]
            else:
                print("No sessions found")
                exit(1)

        replayer.replay_session(args.session, args.speed)

        try:
            while replayer.replaying:
                time.sleep(1)
        except KeyboardInterrupt:
            replayer.stop_replay()
