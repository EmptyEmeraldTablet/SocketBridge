"""
Core Replay Recorder - 数据录制器

提供高性能的游戏数据录制功能：
- 支持 v2.1 协议完整录制
- 自动会话管理
- 增量保存和压缩
- 与 IsaacBridge 集成
"""

import os
import json
import gzip
import time
import threading
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field

from .message import RawMessage, SessionMetadata, MessageType

logger = logging.getLogger(__name__)

# 默认录制目录
DEFAULT_RECORDINGS_DIR = os.environ.get("SOCKETBRIDGE_RECORDINGS_DIR", "./recordings")


@dataclass
class RecorderConfig:
    """录制器配置"""

    output_dir: str = DEFAULT_RECORDINGS_DIR
    buffer_size: int = 1000  # 消息缓冲区大小
    auto_save_interval: float = 60.0  # 自动保存间隔（秒）
    compress: bool = True  # 是否压缩
    include_events: bool = True  # 是否录制事件
    include_commands: bool = False  # 是否录制命令


@dataclass
class RecordingSession:
    """录制会话"""

    session_id: str
    output_dir: Path
    metadata: SessionMetadata
    is_recording: bool = False
    start_frame: int = 0
    current_frame: int = 0

    # 缓冲区
    message_buffer: List[RawMessage] = field(default_factory=list)
    event_buffer: List[RawMessage] = field(default_factory=list)

    # 统计
    frames_recorded: int = 0
    messages_recorded: int = 0
    events_recorded: int = 0
    bytes_written: int = 0


class DataRecorder:
    """
    数据录制器

    使用示例：
    ```python
    from core.replay import DataRecorder
    from isaac_bridge import IsaacBridge

    bridge = IsaacBridge()
    recorder = DataRecorder()

    # 绑定到 bridge
    recorder.bind_to_bridge(bridge)

    # 或手动录制
    recorder.start_session()
    recorder.record_message(raw_message)
    recorder.stop_session()
    ```
    """

    def __init__(self, config: Optional[RecorderConfig] = None):
        self.config = config or RecorderConfig()
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.current_session: Optional[RecordingSession] = None
        self._lock = threading.Lock()
        self._auto_save_thread: Optional[threading.Thread] = None
        self._running = False

        # 回调
        self._on_session_start: Optional[Callable[[RecordingSession], None]] = None
        self._on_session_end: Optional[Callable[[RecordingSession], None]] = None

    @property
    def is_recording(self) -> bool:
        """是否正在录制"""
        return self.current_session is not None and self.current_session.is_recording

    def start_session(
        self,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RecordingSession:
        """开始录制会话"""
        with self._lock:
            if self.current_session and self.current_session.is_recording:
                logger.warning("已有录制会话正在进行，先停止当前会话")
                self._stop_session_internal()

            # 生成会话ID
            if session_id is None:
                session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")

            # 创建会话目录
            session_dir = self.output_dir / session_id
            session_dir.mkdir(parents=True, exist_ok=True)

            # 创建元数据
            session_metadata = SessionMetadata(
                session_id=session_id,
                start_time=time.time(),
                start_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                metadata=metadata or {},
            )

            # 创建会话
            self.current_session = RecordingSession(
                session_id=session_id,
                output_dir=session_dir,
                metadata=session_metadata,
                is_recording=True,
            )

            # 启动自动保存
            self._running = True
            self._auto_save_thread = threading.Thread(
                target=self._auto_save_loop, daemon=True
            )
            self._auto_save_thread.start()

            logger.info(f"开始录制会话: {session_id}")

            if self._on_session_start:
                self._on_session_start(self.current_session)

            return self.current_session

    def stop_session(self) -> Optional[SessionMetadata]:
        """停止录制会话"""
        with self._lock:
            return self._stop_session_internal()

    def _stop_session_internal(self) -> Optional[SessionMetadata]:
        """内部停止会话（需要持有锁）"""
        if not self.current_session:
            return None

        self._running = False
        self.current_session.is_recording = False

        # 刷新缓冲区
        self._flush_buffers()

        # 更新元数据
        metadata = self.current_session.metadata
        metadata.end_time = time.time()
        metadata.duration = metadata.end_time - metadata.start_time
        metadata.total_frames = self.current_session.frames_recorded
        metadata.total_messages = self.current_session.messages_recorded
        metadata.total_events = self.current_session.events_recorded

        # 保存元数据
        self._save_metadata()

        # 保存摘要
        self._save_summary()

        logger.info(
            f"停止录制会话: {self.current_session.session_id}, "
            f"帧数: {metadata.total_frames}, "
            f"消息数: {metadata.total_messages}, "
            f"持续时间: {metadata.duration_formatted}"
        )

        if self._on_session_end:
            self._on_session_end(self.current_session)

        session_metadata = metadata
        self.current_session = None
        return session_metadata

    def record_message(self, message: RawMessage) -> bool:
        """录制消息"""
        if not self.is_recording:
            return False

        with self._lock:
            session = self.current_session
            if not session:
                return False

            # 更新帧信息
            if message.frame > session.current_frame:
                session.current_frame = message.frame
                session.frames_recorded += 1

            # 分类存储
            if message.is_event_message:
                if self.config.include_events:
                    session.event_buffer.append(message)
                    session.events_recorded += 1
            else:
                session.message_buffer.append(message)
                session.messages_recorded += 1

            # 检查缓冲区大小
            if len(session.message_buffer) >= self.config.buffer_size:
                self._flush_buffers()

            return True

    def record_raw(self, data: Dict[str, Any]) -> bool:
        """录制原始字典数据"""
        try:
            message = RawMessage.from_dict(data)
            return self.record_message(message)
        except Exception as e:
            logger.error(f"解析消息失败: {e}")
            return False

    def _flush_buffers(self) -> None:
        """刷新缓冲区到磁盘"""
        if not self.current_session:
            return

        session = self.current_session

        # 保存消息
        if session.message_buffer:
            self._save_messages(session.message_buffer, "messages")
            session.message_buffer.clear()

        # 保存事件
        if session.event_buffer:
            self._save_messages(session.event_buffer, "events")
            session.event_buffer.clear()

    def _save_messages(self, messages: List[RawMessage], prefix: str) -> None:
        """保存消息列表"""
        if not self.current_session or not messages:
            return

        session = self.current_session
        timestamp = int(time.time() * 1000)
        filename = f"{prefix}_{timestamp}.jsonl"

        if self.config.compress:
            filename += ".gz"
            filepath = session.output_dir / filename
            with gzip.open(filepath, "wt", encoding="utf-8") as f:
                for msg in messages:
                    f.write(msg.to_json_line())
        else:
            filepath = session.output_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                for msg in messages:
                    f.write(msg.to_json_line())

        session.bytes_written += filepath.stat().st_size
        logger.debug(f"保存 {len(messages)} 条消息到 {filename}")

    def _save_metadata(self) -> None:
        """保存元数据"""
        if not self.current_session:
            return

        session = self.current_session
        filepath = session.output_dir / "metadata.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session.metadata.model_dump(), f, indent=2, ensure_ascii=False)

    def _save_summary(self) -> None:
        """保存摘要"""
        if not self.current_session:
            return

        session = self.current_session
        summary = {
            "session_id": session.session_id,
            "frames": session.frames_recorded,
            "messages": session.messages_recorded,
            "events": session.events_recorded,
            "bytes": session.bytes_written,
            "duration": session.metadata.duration,
            "start_frame": session.start_frame,
            "end_frame": session.current_frame,
        }

        filepath = session.output_dir / "summary.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    def _auto_save_loop(self) -> None:
        """自动保存循环"""
        while self._running:
            time.sleep(self.config.auto_save_interval)
            if self._running and self.is_recording:
                with self._lock:
                    self._flush_buffers()
                    logger.debug("自动保存完成")

    def bind_to_bridge(self, bridge: Any) -> None:
        """绑定到 IsaacBridge"""
        # 导入 IsaacBridge 事件处理
        try:
            from isaac_bridge import DataMessage, Event

            @bridge.on("data")
            def on_data(msg: DataMessage):
                self.record_raw(msg.to_dict() if hasattr(msg, "to_dict") else msg)

            @bridge.on("event:GAME_START")
            def on_game_start(data):
                self.start_session(metadata={"game_start": data})

            @bridge.on("event:GAME_END")
            def on_game_end(data):
                self.stop_session()

            logger.info("已绑定到 IsaacBridge")

        except ImportError:
            logger.warning("无法导入 IsaacBridge，请手动调用 record_message")

    def on_session_start(
        self, callback: Callable[[RecordingSession], None]
    ) -> Callable:
        """注册会话开始回调"""
        self._on_session_start = callback
        return callback

    def on_session_end(self, callback: Callable[[RecordingSession], None]) -> Callable:
        """注册会话结束回调"""
        self._on_session_end = callback
        return callback
