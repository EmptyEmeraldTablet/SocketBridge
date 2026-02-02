"""
Base Data Channel - 数据通道基类

定义所有数据通道的通用接口和行为。
支持时序信息集成和已知问题检测。
"""

from typing import Dict, List, Optional, Any, Type, Generic, TypeVar
from dataclasses import dataclass
from abc import ABC, abstractmethod
import logging

try:
    from core.protocol.timing import ChannelTimingInfo, MessageTimingInfo
    from core.validation.known_issues import KnownIssueRegistry, ValidationIssue
    from models.state import TimingAwareStateManager
except ImportError:
    from python.core.protocol.timing import ChannelTimingInfo, MessageTimingInfo
    from python.core.validation.known_issues import KnownIssueRegistry, ValidationIssue
    from python.models.state import TimingAwareStateManager

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ChannelConfig:
    """通道配置"""

    name: str
    interval: str = "MEDIUM"
    priority: int = 5
    enabled: bool = True
    validation_enabled: bool = True


class DataChannel(ABC, Generic[T]):
    """数据通道基类

    所有具体通道应继承此类并实现抽象方法。
    提供了：
    - 时序信息自动处理
    - 已知问题检测
    - 状态管理集成
    """

    name: str = "BASE_CHANNEL"
    config: ChannelConfig

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.config = ChannelConfig(name=cls.name)

    def __init__(self):
        self._state_manager: Optional[TimingAwareStateManager] = None
        self._known_issues = KnownIssueRegistry()
        self._last_data: Optional[T] = None
        self._last_timing: Optional[ChannelTimingInfo] = None

    def bind_state_manager(self, state_manager: TimingAwareStateManager):
        """绑定状态管理器"""
        self._state_manager = state_manager

    def process(
        self,
        raw_data: Dict[str, Any],
        timing: MessageTimingInfo,
        frame: int,
        validate: bool = True,
    ) -> Optional[T]:
        """处理原始数据

        Args:
            raw_data: 原始数据字典
            timing: 消息时序信息
            frame: 当前帧号
            validate: 是否进行验证

        Returns:
            解析后的数据，或 None（如果处理失败）
        """
        try:
            channel_timing = timing.channel_meta.get(self.name)

            if not channel_timing:
                logger.warning(f"No timing info for channel {self.name}")
                channel_timing = ChannelTimingInfo(
                    channel=self.name,
                    collect_frame=frame,
                    collect_time=timing.game_time,
                    interval="UNKNOWN",
                    stale_frames=0,
                )

            issues: List[ValidationIssue] = []

            if validate and self.config.validation_enabled:
                issues = self._known_issues.detect_issues(self.name, raw_data)
                for issue in issues:
                    logger.debug(f"Validation issue in {self.name}: {issue.message}")

            data = self.parse(raw_data, frame)

            if data is None:
                logger.warning(f"Failed to parse data for channel {self.name}")
                return None

            validation_issues = []
            if self.config.validation_enabled:
                validation_issues = self.validate(data)
                for issue in validation_issues:
                    logger.debug(f"Validation error in {self.name}: {issue.message}")

            self._last_data = data
            self._last_timing = channel_timing

            if self._state_manager:
                self._state_manager.update_channel(
                    self.name, data, channel_timing, frame
                )

            return data

        except Exception as e:
            logger.error(f"Error processing channel {self.name}: {e}")
            return None

    @abstractmethod
    def parse(self, raw_data: Dict[str, Any], frame: int) -> Optional[T]:
        """解析原始数据

        Args:
            raw_data: 原始数据字典
            frame: 当前帧号

        Returns:
            解析后的数据对象，或 None
        """
        pass

    def validate(self, data: T) -> List[ValidationIssue]:
        """验证数据

        子类可重写此方法添加额外验证。

        Args:
            data: 解析后的数据

        Returns:
            验证问题列表
        """
        return []

    def get_data(self) -> Optional[T]:
        """获取最后处理的数据"""
        return self._last_data

    def get_timing(self) -> Optional[ChannelTimingInfo]:
        """获取最后处理的时序信息"""
        return self._last_timing

    def is_fresh(self, max_stale_frames: int = 5) -> bool:
        """检查数据是否新鲜"""
        if not self._state_manager:
            return self._last_timing is not None
        return self._state_manager.is_channel_fresh(self.name, max_stale_frames)

    def get_age(self) -> int:
        """获取数据年龄（帧数）"""
        if not self._state_manager:
            return -1
        return self._state_manager.get_channel_age(self.name)


class ChannelRegistry:
    """通道注册表"""

    _instance: Optional["ChannelRegistry"] = None
    _channels: Dict[str, DataChannel] = {}
    _channel_classes: Dict[str, Type[DataChannel]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._initialized = True

    @classmethod
    def register(cls, channel: DataChannel):
        """注册通道实例"""
        cls._channels[channel.name] = channel
        logger.info(f"Registered channel: {channel.name}")

    @classmethod
    def register_class(cls, channel_class: Type[DataChannel]):
        """注册通道类"""
        cls._channel_classes[channel_class.name] = channel_class
        logger.info(f"Registered channel class: {channel_class.name}")

    @classmethod
    def get(cls, name: str) -> Optional[DataChannel]:
        """获取通道实例"""
        return cls._channels.get(name)

    @classmethod
    def get_class(cls, name: str) -> Optional[Type[DataChannel]]:
        """获取通道类"""
        return cls._channel_classes.get(name)

    @classmethod
    def create(cls, name: str) -> Optional[DataChannel]:
        """创建通道实例"""
        channel_class = cls.get_class(name)
        if channel_class:
            return channel_class()
        return None

    @classmethod
    def get_all_names(cls) -> List[str]:
        """获取所有通道名称"""
        return list(set(cls._channels.keys()) | set(cls._channel_classes.keys()))

    @classmethod
    def bind_state_manager(cls, state_manager: TimingAwareStateManager):
        """为所有通道绑定状态管理器"""
        for channel in cls._channels.values():
            channel.bind_state_manager(state_manager)
