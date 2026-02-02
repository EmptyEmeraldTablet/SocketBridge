"""
SocketBridge Facade - 简化 API 接口

提供简洁的 API 用于访问 SocketBridge 功能。
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
import logging

try:
    from core.protocol.timing import MessageTimingInfo
    from core.validation.known_issues import KnownIssueRegistry
    from services.monitor import DataQualityMonitor, QualityIssue
    from services.processor import DataProcessor, ProcessedChannel
    from channels.base import ChannelRegistry
except ImportError:
    from python.core.protocol.timing import MessageTimingInfo
    from python.core.validation.known_issues import KnownIssueRegistry
    from python.services.monitor import DataQualityMonitor, QualityIssue
    from python.services.processor import DataProcessor, ProcessedChannel
    from python.channels.base import ChannelRegistry

logger = logging.getLogger(__name__)


@dataclass
class BridgeConfig:
    """桥接配置"""

    host: str = "127.0.0.1"
    port: int = 9527
    validation_enabled: bool = True
    monitoring_enabled: bool = True


class SocketBridgeFacade:
    """SocketBridge 门面类

    提供简化的 API 用于：
    - 连接管理
    - 数据访问
    - 状态查询
    - 质量监控
    """

    def __init__(self, config: Optional[BridgeConfig] = None):
        self.config = config or BridgeConfig()
        self.processor = DataProcessor(
            validation_enabled=self.config.validation_enabled
        )
        self.monitor = DataQualityMonitor() if self.config.monitoring_enabled else None

        self._connected = False
        self._last_frame = 0
        self._last_room = -1

        self._callbacks: Dict[str, List[Callable]] = {
            "connected": [],
            "disconnected": [],
            "frame": [],
            "room_change": [],
            "issue": [],
        }

    def on(self, event: str, callback: Callable):
        """注册事件回调

        Args:
            event: 事件类型 (connected, disconnected, frame, room_change, issue)
            callback: 回调函数
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _emit(self, event: str, *args, **kwargs):
        """触发事件"""
        for cb in self._callbacks.get(event, []):
            try:
                cb(*args, **kwargs)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")

    def process_message(self, msg: Dict[str, Any]) -> Dict[str, ProcessedChannel]:
        """处理消息

        Args:
            msg: 协议消息

        Returns:
            已处理通道字典
        """
        frame = msg.get("frame", 0)
        room = msg.get("room_index", -1)

        if self.monitor:
            self.monitor.process_message(msg, msg.get("payload", {}), frame)

        result = self.processor.process_message(msg)

        if room != self._last_room:
            self._emit("room_change", room, self._last_room)
            self._last_room = room

        self._emit("frame", frame, result)

        self._last_frame = frame

        return result

    def get_player_position(self) -> Optional[Dict[str, Any]]:
        """获取玩家位置"""
        return self.processor.get_player_position()

    def get_player_stats(self) -> Optional[Dict[str, Any]]:
        """获取玩家属性"""
        return self.processor.get_player_stats()

    def get_room_info(self) -> Optional[Dict[str, Any]]:
        """获取房间信息"""
        return self.processor.get_room_info()

    def get_enemies(self) -> Optional[List[Dict[str, Any]]]:
        """获取敌人列表"""
        return self.processor.get_enemies()

    def get_channel(self, name: str) -> Optional[ProcessedChannel]:
        """获取通道数据"""
        return self.processor.get_channel(name)

    def get_data(self, name: str) -> Optional[Any]:
        """获取通道原始数据"""
        return self.processor.get_data(name)

    def is_channel_fresh(self, name: str, max_stale_frames: int = 5) -> bool:
        """检查通道数据是否新鲜"""
        return self.processor.is_fresh(name, max_stale_frames)

    def get_all_channels(self) -> List[str]:
        """获取所有通道名称"""
        return self.processor.get_all_channels()

    def get_synchronized_data(
        self, channels: List[str], max_frame_diff: int = 5
    ) -> Optional[Dict[str, Any]]:
        """获取同步数据"""
        return self.processor.get_synchronized_data(channels, max_frame_diff)

    def get_quality_report(self) -> str:
        """获取质量报告"""
        if self.monitor:
            return self.monitor.generate_report()
        return "Monitoring is disabled"

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "connected": self._connected,
            "last_frame": self._last_frame,
            "last_room": self._last_room,
            "processor": self.processor.get_stats(),
        }

    def set_enabled(self, channel: str, enabled: bool):
        """启用/禁用通道"""
        channel = ChannelRegistry.get(channel)
        if channel:
            channel.config.enabled = enabled

    def set_interval(self, channel: str, interval: str):
        """设置通道采集间隔"""
        channel = ChannelRegistry.get(channel)
        if channel:
            channel.config.interval = interval
