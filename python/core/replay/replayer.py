"""
Core Replay Replayer - 数据回放器

提供灵活的游戏数据回放功能：
- 支持 v2.0/v2.1 协议回放
- 可变速回放
- 帧级别控制
- 循环播放
- 实时数据流模拟
"""

import os
import json
import gzip
import time
import socket
import threading
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Generator, Iterator
from dataclasses import dataclass, field
from enum import Enum

from .message import RawMessage, SessionMetadata, FrameData, MessageType

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_RECORDINGS_DIR = os.environ.get("SOCKETBRIDGE_RECORDINGS_DIR", "./recordings")
DEFAULT_HOST = os.environ.get("SOCKETBRIDGE_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("SOCKETBRIDGE_PORT", "9527"))


class ReplayState(str, Enum):
    """回放状态"""

    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"
    FINISHED = "finished"


@dataclass
class ReplayerConfig:
    """回放器配置"""

    recordings_dir: str = DEFAULT_RECORDINGS_DIR
    speed: float = 1.0  # 回放速度倍数
    loop: bool = False  # 是否循环播放
    start_frame: int = 0  # 起始帧
    end_frame: int = -1  # 结束帧（-1 表示到末尾）
    frame_delay: float = 1.0 / 30  # 帧间隔（秒）


@dataclass
class ReplaySession:
    """回放会话"""

    session_id: str
    session_dir: Path
    metadata: SessionMetadata
    state: ReplayState = ReplayState.STOPPED

    # 消息列表
    messages: List[RawMessage] = field(default_factory=list)
    current_index: int = 0

    # 帧索引
    frame_index: Dict[int, List[int]] = field(default_factory=dict)  # frame -> [msg indices]

    # 统计
    frames_played: int = 0
    messages_played: int = 0

    @property
    def total_messages(self) -> int:
        return len(self.messages)

    @property
    def total_frames(self) -> int:
        return len(self.frame_index)

    @property
    def progress(self) -> float:
        if self.total_messages == 0:
            return 0.0
        return self.current_index / self.total_messages

    @property
    def current_frame(self) -> int:
        if self.current_index < len(self.messages):
            return self.messages[self.current_index].frame
        return 0


class DataReplayer:
    """
    数据回放器

    使用示例：
    ```python
    from core.replay import DataReplayer, create_replayer

    # 方式1: 直接创建
    replayer = DataReplayer()
    session = replayer.load_session("session_20260101_120000")

    # 迭代回放
    for message in replayer.iter_messages():
        process(message)

    # 方式2: 快捷函数
    replayer = create_replayer("session_20260101_120000")
    for msg in replayer.iter_messages():
        print(msg.frame, msg.channels)
    ```
    """

    def __init__(self, config: Optional[ReplayerConfig] = None):
        self.config = config or ReplayerConfig()
        self.recordings_dir = Path(self.config.recordings_dir)

        self.current_session: Optional[ReplaySession] = None
        self._lock = threading.Lock()
        self._play_thread: Optional[threading.Thread] = None
        self._running = False

        # 回调
        self._on_message: Optional[Callable[[RawMessage], None]] = None
        self._on_frame: Optional[Callable[[int, List[RawMessage]], None]] = None
        self._on_finish: Optional[Callable[[], None]] = None

    @property
    def state(self) -> ReplayState:
        """当前状态"""
        if self.current_session:
            return self.current_session.state
        return ReplayState.STOPPED

    @property
    def is_playing(self) -> bool:
        return self.state == ReplayState.PLAYING

    def load_session(self, session_id: str) -> ReplaySession:
        """加载会话"""
        session_dir = self.recordings_dir / session_id

        if not session_dir.exists():
            # 尝试查找匹配的目录
            matches = list(self.recordings_dir.glob(f"*{session_id}*"))
            if matches:
                session_dir = matches[0]
                session_id = session_dir.name
            else:
                raise FileNotFoundError(f"找不到会话: {session_id}")

        # 加载元数据
        metadata_path = session_dir / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = SessionMetadata(**json.load(f))
        else:
            # 尝试旧格式
            meta_files = list(session_dir.glob("*_meta.json"))
            if meta_files:
                with open(meta_files[0], "r", encoding="utf-8") as f:
                    data = json.load(f)
                    metadata = SessionMetadata(
                        session_id=session_id,
                        start_time=data.get("start_time", 0),
                        start_timestamp=data.get("start_timestamp", ""),
                        total_frames=data.get("total_frames", 0),
                        total_messages=data.get("total_messages", 0),
                        duration=data.get("duration", 0),
                    )
            else:
                metadata = SessionMetadata(session_id=session_id)

        # 创建会话
        session = ReplaySession(
            session_id=session_id,
            session_dir=session_dir,
            metadata=metadata,
        )

        # 加载消息
        self._load_messages(session)

        # 构建帧索引
        self._build_frame_index(session)

        self.current_session = session
        logger.info(
            f"加载会话: {session_id}, "
            f"消息数: {session.total_messages}, "
            f"帧数: {session.total_frames}"
        )

        return session

    def _load_messages(self, session: ReplaySession) -> None:
        """加载所有消息"""
        messages = []

        # 查找所有消息文件
        patterns = ["messages_*.jsonl", "messages_*.jsonl.gz", "*.jsonl", "*.jsonl.gz"]

        for pattern in patterns:
            for filepath in sorted(session.session_dir.glob(pattern)):
                if "events" in filepath.name:
                    continue  # 跳过事件文件（可选加载）

                try:
                    if filepath.suffix == ".gz":
                        with gzip.open(filepath, "rt", encoding="utf-8") as f:
                            for line in f:
                                if line.strip():
                                    messages.append(RawMessage.from_json(line))
                    else:
                        with open(filepath, "r", encoding="utf-8") as f:
                            for line in f:
                                if line.strip():
                                    messages.append(RawMessage.from_json(line))
                except Exception as e:
                    logger.warning(f"加载消息文件失败 {filepath}: {e}")

        # 按帧排序
        messages.sort(key=lambda m: (m.frame, m.received_at))
        session.messages = messages

    def _build_frame_index(self, session: ReplaySession) -> None:
        """构建帧索引"""
        frame_index: Dict[int, List[int]] = {}

        for idx, msg in enumerate(session.messages):
            frame = msg.frame
            if frame not in frame_index:
                frame_index[frame] = []
            frame_index[frame].append(idx)

        session.frame_index = frame_index

    def iter_messages(
        self, speed: Optional[float] = None
    ) -> Generator[RawMessage, None, None]:
        """迭代消息生成器"""
        if not self.current_session:
            raise RuntimeError("没有加载会话")

        session = self.current_session
        speed = speed or self.config.speed
        frame_delay = self.config.frame_delay / speed if speed > 0 else 0

        last_frame = -1
        for idx, msg in enumerate(session.messages):
            # 检查帧范围
            if self.config.start_frame > 0 and msg.frame < self.config.start_frame:
                continue
            if self.config.end_frame > 0 and msg.frame > self.config.end_frame:
                break

            # 帧间延迟
            if speed > 0 and msg.frame != last_frame:
                if last_frame >= 0:
                    time.sleep(frame_delay)
                last_frame = msg.frame

            session.current_index = idx
            session.messages_played += 1

            yield msg

        session.state = ReplayState.FINISHED

    def iter_frames(
        self, speed: Optional[float] = None
    ) -> Generator[FrameData, None, None]:
        """按帧迭代生成器"""
        if not self.current_session:
            raise RuntimeError("没有加载会话")

        session = self.current_session
        speed = speed or self.config.speed
        frame_delay = self.config.frame_delay / speed if speed > 0 else 0

        sorted_frames = sorted(session.frame_index.keys())

        for frame in sorted_frames:
            # 检查帧范围
            if self.config.start_frame > 0 and frame < self.config.start_frame:
                continue
            if self.config.end_frame > 0 and frame > self.config.end_frame:
                break

            # 帧间延迟
            if speed > 0:
                time.sleep(frame_delay)

            # 获取该帧的所有消息
            indices = session.frame_index[frame]
            messages = [session.messages[i] for i in indices]

            # 构建帧数据
            frame_data = FrameData(
                frame=frame,
                timestamp=messages[0].timestamp if messages else 0,
                room_index=messages[0].room_index if messages else -1,
                messages=messages,
                channels=list(
                    set(
                        ch
                        for msg in messages
                        if msg.channels
                        for ch in msg.channels
                    )
                ),
            )

            session.frames_played += 1
            yield frame_data

        session.state = ReplayState.FINISHED

    def get_frame(self, frame: int) -> Optional[FrameData]:
        """获取指定帧数据"""
        if not self.current_session:
            return None

        session = self.current_session
        if frame not in session.frame_index:
            return None

        indices = session.frame_index[frame]
        messages = [session.messages[i] for i in indices]

        return FrameData(
            frame=frame,
            timestamp=messages[0].timestamp if messages else 0,
            room_index=messages[0].room_index if messages else -1,
            messages=messages,
            channels=list(
                set(ch for msg in messages if msg.channels for ch in msg.channels)
            ),
        )

    def get_state_at_frame(self, frame: int) -> Dict[str, Any]:
        """获取指定帧的完整状态（累积所有通道数据）"""
        if not self.current_session:
            return {}

        session = self.current_session
        state: Dict[str, Any] = {}

        # 累积到指定帧的所有数据
        sorted_frames = sorted(session.frame_index.keys())
        for f in sorted_frames:
            if f > frame:
                break

            indices = session.frame_index[f]
            for idx in indices:
                msg = session.messages[idx]
                if msg.payload:
                    state.update(msg.payload)

        return state

    def play_async(
        self,
        on_message: Optional[Callable[[RawMessage], None]] = None,
        on_frame: Optional[Callable[[int, List[RawMessage]], None]] = None,
        on_finish: Optional[Callable[[], None]] = None,
    ) -> None:
        """异步播放"""
        if not self.current_session:
            raise RuntimeError("没有加载会话")

        self._on_message = on_message
        self._on_frame = on_frame
        self._on_finish = on_finish

        self._running = True
        self.current_session.state = ReplayState.PLAYING

        self._play_thread = threading.Thread(target=self._play_loop, daemon=True)
        self._play_thread.start()

    def _play_loop(self) -> None:
        """播放循环"""
        try:
            while self._running:
                for frame_data in self.iter_frames():
                    if not self._running:
                        break

                    # 调用回调
                    if self._on_frame:
                        self._on_frame(frame_data.frame, frame_data.messages)

                    if self._on_message:
                        for msg in frame_data.messages:
                            self._on_message(msg)

                if not self.config.loop:
                    break

                # 循环播放，重置索引
                if self.current_session:
                    self.current_session.current_index = 0
                    self.current_session.frames_played = 0

        finally:
            if self._on_finish:
                self._on_finish()

    def pause(self) -> None:
        """暂停播放"""
        if self.current_session:
            self.current_session.state = ReplayState.PAUSED

    def resume(self) -> None:
        """恢复播放"""
        if self.current_session and self.current_session.state == ReplayState.PAUSED:
            self.current_session.state = ReplayState.PLAYING

    def stop(self) -> None:
        """停止播放"""
        self._running = False
        if self.current_session:
            self.current_session.state = ReplayState.STOPPED

    def seek_to_frame(self, frame: int) -> bool:
        """跳转到指定帧"""
        if not self.current_session:
            return False

        session = self.current_session
        if frame not in session.frame_index:
            # 找最接近的帧
            sorted_frames = sorted(session.frame_index.keys())
            for f in sorted_frames:
                if f >= frame:
                    frame = f
                    break
            else:
                return False

        # 更新索引
        indices = session.frame_index[frame]
        session.current_index = indices[0] if indices else 0
        return True

    def on_message(self, callback: Callable[[RawMessage], None]) -> Callable:
        """注册消息回调装饰器"""
        self._on_message = callback
        return callback

    def on_frame(
        self, callback: Callable[[int, List[RawMessage]], None]
    ) -> Callable:
        """注册帧回调装饰器"""
        self._on_frame = callback
        return callback

    def on_finish(self, callback: Callable[[], None]) -> Callable:
        """注册完成回调装饰器"""
        self._on_finish = callback
        return callback


def create_replayer(
    session_id: str,
    speed: float = 1.0,
    recordings_dir: Optional[str] = None,
) -> DataReplayer:
    """
    快捷创建回放器

    Args:
        session_id: 会话ID
        speed: 回放速度
        recordings_dir: 录制目录

    Returns:
        已加载会话的回放器
    """
    config = ReplayerConfig(
        speed=speed,
        recordings_dir=recordings_dir or DEFAULT_RECORDINGS_DIR,
    )
    replayer = DataReplayer(config)
    replayer.load_session(session_id)
    return replayer


class LuaSimulator:
    """
    Lua 端模拟器 - 模拟游戏发送数据

    用于测试 Python 端接收逻辑，无需真实游戏连接。
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self._connected = False

    def connect(self, timeout: float = 5.0) -> bool:
        """连接到 Python 服务器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(timeout)
            self.socket.connect((self.host, self.port))
            self._connected = True
            logger.info(f"已连接到 {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"连接失败: {e}")
            return False

    def disconnect(self) -> None:
        """断开连接"""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        self._connected = False

    def send_message(self, message: RawMessage) -> bool:
        """发送消息"""
        if not self._connected or not self.socket:
            return False

        try:
            data = message.to_json_line().encode("utf-8")
            self.socket.sendall(data)
            return True
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False

    def replay_session(
        self,
        replayer: DataReplayer,
        speed: float = 1.0,
    ) -> None:
        """回放会话"""
        if not self._connected:
            if not self.connect():
                return

        for msg in replayer.iter_messages(speed=speed):
            if not self.send_message(msg):
                break

        self.disconnect()
