"""
Data Processor - 数据处理器

整合所有数据通道，提供统一的数据处理接口。
"""

from typing import Dict, Any, Optional, List, Callable, TypeVar, Generic
from dataclasses import dataclass
import logging

try:
    from core.protocol.timing import MessageTimingInfo, TimingMonitor
    from core.protocol.schema import DataMessageSchema
    from core.validation.known_issues import KnownIssueRegistry
    from channels.base import DataChannel, ChannelRegistry
    from models.state import TimingAwareStateManager
except ImportError:
    from python.core.protocol.timing import MessageTimingInfo, TimingMonitor
    from python.core.protocol.schema import DataMessageSchema
    from python.core.validation.known_issues import KnownIssueRegistry
    from python.channels.base import DataChannel, ChannelRegistry
    from python.models.state import TimingAwareStateManager

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ProcessedChannel:
    """已处理通道数据"""

    name: str
    data: Any
    is_fresh: bool
    age: int
    issues: List[str] = None


class DataProcessor:
    """数据处理器

    功能：
    - 整合所有通道数据处理
    - 统一时序信息管理
    - 支持通道状态查询
    - 提供回调机制
    """

    def __init__(self, validation_enabled: bool = True):
        self.timing_monitor = TimingMonitor()
        self.state_manager = TimingAwareStateManager()
        self.known_issues = KnownIssueRegistry()

        self._channels: Dict[str, DataChannel] = {}
        self._data_cache: Dict[str, Any] = {}
        self._frame_cache: Dict[str, int] = {}

        self._on_message_callbacks: List[Callable] = []
        self._on_channel_callbacks: Dict[str, List[Callable]] = {}
        self._on_issue_callbacks: List[Callable] = []

        self._validation_enabled = validation_enabled
        self._message_count = 0

        self._init_channels()

    def _init_channels(self):
        """初始化所有通道"""
        channel_names = ChannelRegistry.get_all_names()
        for name in channel_names:
            channel = ChannelRegistry.create(name)
            if channel:
                channel.bind_state_manager(self.state_manager)
                self._channels[name] = channel
                self._on_channel_callbacks[name] = []
                logger.info(f"Initialized channel: {name}")

    def register_message_callback(self, callback: Callable[[Dict, int], None]):
        """注册消息回调"""
        self._on_message_callbacks.append(callback)

    def register_channel_callback(
        self, channel: str, callback: Callable[[Any, int], None]
    ):
        """注册通道回调"""
        if channel in self._on_channel_callbacks:
            self._on_channel_callbacks[channel].append(callback)

    def register_issue_callback(self, callback: Callable[[str, Any], None]):
        """注册问题回调"""
        self._on_issue_callbacks.append(callback)

    def process_message(
        self, msg: Dict[str, Any], validate: Optional[bool] = None
    ) -> Dict[str, ProcessedChannel]:
        """处理消息

        Args:
            msg: 协议消息
            validate: 是否验证（覆盖默认设置）

        Returns:
            已处理通道字典
        """
        validate = validate if validate is not None else self._validation_enabled

        try:
            timing = MessageTimingInfo.from_message(msg)
            frame = msg.get("frame", 0)
            payload = msg.get("payload", {})
            channels = msg.get("channels", [])

            self._message_count += 1

            timing_issues = self.timing_monitor.check_message(timing)
            for issue in timing_issues:
                self._notify_issue("timing", issue.details)

            results = {}

            for channel_name in channels:
                channel_data = payload.get(channel_name)
                if channel_data is None:
                    continue

                channel = self._channels.get(channel_name)
                if not channel:
                    continue

                processed = channel.process(
                    channel_data, timing, frame, validate=validate
                )

                if processed is not None:
                    self._data_cache[channel_name] = processed
                    self._frame_cache[channel_name] = frame

                    is_fresh = channel.is_fresh()
                    age = channel.get_age()

                    results[channel_name] = ProcessedChannel(
                        name=channel_name,
                        data=processed,
                        is_fresh=is_fresh,
                        age=age,
                        issues=[],
                    )

                    for cb in self._on_channel_callbacks.get(channel_name, []):
                        try:
                            cb(processed, frame)
                        except Exception as e:
                            logger.error(
                                f"Channel callback error for {channel_name}: {e}"
                            )

            for cb in self._on_message_callbacks:
                try:
                    cb(msg, frame)
                except Exception as e:
                    logger.error(f"Message callback error: {e}")

            return results

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            self._notify_issue("processing", {"error": str(e)})
            return {}

    def _notify_issue(self, source: str, details: Any):
        """通知问题"""
        for cb in self._on_issue_callbacks:
            try:
                cb(source, details)
            except Exception as e:
                logger.error(f"Issue callback error: {e}")

    def get_channel(self, name: str) -> Optional[ProcessedChannel]:
        """获取通道数据"""
        if name not in self._data_cache:
            return None

        channel = self._channels.get(name)
        if not channel:
            return None

        return ProcessedChannel(
            name=name,
            data=self._data_cache[name],
            is_fresh=channel.is_fresh(),
            age=channel.get_age(),
            issues=[],
        )

    def get_data(self, name: str) -> Optional[Any]:
        """获取通道原始数据"""
        return self._data_cache.get(name)

    def is_fresh(self, name: str, max_stale_frames: int = 5) -> bool:
        """检查通道数据是否新鲜"""
        channel = self._channels.get(name)
        if not channel:
            return False
        return channel.is_fresh(max_stale_frames)

    def get_age(self, name: str) -> int:
        """获取数据年龄"""
        return self._frame_cache.get(name, -1)

    def get_all_channels(self) -> List[str]:
        """获取所有通道名称"""
        return list(self._channels.keys())

    def get_stats(self) -> Dict[str, Any]:
        """获取处理器统计"""
        fresh_channels = sum(1 for c in self._channels.values() if c.is_fresh())
        total_channels = len(self._channels)

        timing_stats = self.timing_monitor.get_stats()

        return {
            "message_count": self._message_count,
            "total_channels": total_channels,
            "fresh_channels": fresh_channels,
            "stale_channels": total_channels - fresh_channels,
            "timing_stats": timing_stats,
        }

    def get_synchronized_data(
        self, channels: List[str], max_frame_diff: int = 5
    ) -> Optional[Dict[str, Any]]:
        """获取同步数据

        Args:
            channels: 通道列表
            max_frame_diff: 最大帧差

        Returns:
            同步的数据字典，或 None（如果不满足同步条件）
        """
        frame_dict = {}
        data_dict = {}

        for name in channels:
            if name not in self._data_cache:
                return None
            if name not in self._frame_cache:
                return None
            frame_dict[name] = self._frame_cache[name]
            data_dict[name] = self._data_cache[name]

        frames = list(frame_dict.values())
        if max(frames) - min(frames) > max_frame_diff:
            logger.warning(f"Channels not synchronized: {frame_dict}")
            return None

        return data_dict

    def get_player_position(self) -> Optional[Dict[str, Any]]:
        """获取玩家位置（快捷方法）"""
        return self.get_data("PLAYER_POSITION")

    def get_player_stats(self) -> Optional[Dict[str, Any]]:
        """获取玩家属性（快捷方法）"""
        return self.get_data("PLAYER_STATS")

    def get_room_info(self) -> Optional[Dict[str, Any]]:
        """获取房间信息（快捷方法）"""
        return self.get_data("ROOM_INFO")

    def get_enemies(self) -> Optional[List[Dict[str, Any]]]:
        """获取敌人列表（快捷方法）"""
        return self.get_data("ENEMIES")
