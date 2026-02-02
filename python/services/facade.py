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
    from services.entity_state import GameEntityState, EntityStateConfig
    from channels.base import ChannelRegistry
except ImportError:
    from python.core.protocol.timing import MessageTimingInfo
    from python.core.validation.known_issues import KnownIssueRegistry
    from python.services.monitor import DataQualityMonitor, QualityIssue
    from python.services.processor import DataProcessor, ProcessedChannel
    from python.services.entity_state import GameEntityState, EntityStateConfig
    from python.channels.base import ChannelRegistry

logger = logging.getLogger(__name__)


@dataclass
class BridgeConfig:
    """桥接配置"""

    host: str = "127.0.0.1"
    port: int = 9527
    validation_enabled: bool = True
    monitoring_enabled: bool = True
    # 实体状态保持配置
    entity_state_enabled: bool = True
    # 动态实体过期帧数（应与采集频率匹配）
    enemy_expiry_frames: int = 10        # ENEMIES: HIGH 频率，每帧采集
    projectile_expiry_frames: int = 5    # PROJECTILES: HIGH 频率，快速移动
    pickup_expiry_frames: int = 30       # PICKUPS: LOW 频率（每15帧），30帧过期
    bomb_expiry_frames: int = 30         # BOMBS: LOW 频率（每15帧），30帧过期
    # 静态实体过期帧数（-1 禁用自动过期）
    grid_entity_expiry_frames: int = -1  # GRID_ENTITIES: 静态障碍物，不自动过期


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

        # 实体状态管理器
        if self.config.entity_state_enabled:
            self.entity_state = GameEntityState(
                enemy_expiry=self.config.enemy_expiry_frames,
                projectile_expiry=self.config.projectile_expiry_frames,
                pickup_expiry=self.config.pickup_expiry_frames,
                bomb_expiry=self.config.bomb_expiry_frames,
                grid_entity_expiry=self.config.grid_entity_expiry_frames,
            )
        else:
            self.entity_state = None

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

        # 房间切换时清理实体状态
        if room != self._last_room:
            self._emit("room_change", room, self._last_room)
            if self.entity_state:
                self.entity_state.on_room_change(room)
            self._last_room = room

        # 更新实体状态
        if self.entity_state:
            self._update_entity_state(result, frame)

        self._emit("frame", frame, result)

        self._last_frame = frame

        return result

    def _update_entity_state(
        self, channels: Dict[str, ProcessedChannel], frame: int
    ):
        """更新实体状态

        Args:
            channels: 处理后的通道数据
            frame: 当前帧号
        """
        # 更新敌人
        if "ENEMIES" in channels and channels["ENEMIES"].data:
            enemies = channels["ENEMIES"].data
            if isinstance(enemies, list):
                self.entity_state.update_enemies(enemies, frame)

        # 更新投射物
        if "PROJECTILES" in channels and channels["PROJECTILES"].data:
            proj_data = channels["PROJECTILES"].data
            enemy_projectiles = []
            player_tears = []
            lasers = []
            
            if hasattr(proj_data, "enemy_projectiles"):
                enemy_projectiles = proj_data.enemy_projectiles or []
            elif isinstance(proj_data, dict):
                enemy_projectiles = proj_data.get("enemy_projectiles", [])
            
            if hasattr(proj_data, "player_tears"):
                player_tears = proj_data.player_tears or []
            elif isinstance(proj_data, dict):
                player_tears = proj_data.get("player_tears", [])
            
            if hasattr(proj_data, "lasers"):
                lasers = proj_data.lasers or []
            elif isinstance(proj_data, dict):
                lasers = proj_data.get("lasers", [])
            
            self.entity_state.update_projectiles(
                enemy_projectiles, player_tears, lasers, frame
            )

        # 更新拾取物
        if "PICKUPS" in channels and channels["PICKUPS"].data:
            pickups = channels["PICKUPS"].data
            if isinstance(pickups, list):
                self.entity_state.update_pickups(pickups, frame)

        # 更新炸弹
        if "BOMBS" in channels and channels["BOMBS"].data:
            bombs = channels["BOMBS"].data
            if isinstance(bombs, list):
                self.entity_state.update_bombs(bombs, frame)

        # 更新网格实体/障碍物
        if "GRID_ENTITIES" in channels and channels["GRID_ENTITIES"].data:
            grid_entities = channels["GRID_ENTITIES"].data
            if isinstance(grid_entities, list):
                self.entity_state.update_grid_entities(grid_entities, frame)

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
        """获取敌人列表（无状态保持版）"""
        return self.processor.get_enemies()

    def get_enemies_stateful(self, max_stale_frames: int = 5) -> List[Any]:
        """获取敌人列表（有状态保持版）
        
        使用实体状态管理器，返回最近 max_stale_frames 帧内见过的所有敌人。
        即使某些敌人本帧没有被采集，只要在过期阈值内，仍然会返回。
        
        Args:
            max_stale_frames: 最大过期帧数，默认 5 帧
        
        Returns:
            活跃敌人列表
        """
        if self.entity_state:
            return self.entity_state.get_enemies(max_stale_frames)
        return self.processor.get_enemies() or []

    def get_projectiles_stateful(
        self, max_stale_frames: int = 3
    ) -> Dict[str, List[Any]]:
        """获取投射物（有状态保持版）
        
        Args:
            max_stale_frames: 最大过期帧数
        
        Returns:
            包含 enemy_projectiles, player_tears, lasers 的字典
        """
        if self.entity_state:
            return {
                "enemy_projectiles": self.entity_state.get_enemy_projectiles(max_stale_frames),
                "player_tears": self.entity_state.get_player_tears(max_stale_frames),
                "lasers": self.entity_state.get_lasers(max_stale_frames),
            }
        return {"enemy_projectiles": [], "player_tears": [], "lasers": []}

    def get_pickups_stateful(self, max_stale_frames: int = 30) -> List[Any]:
        """获取拾取物（有状态保持版）"""
        if self.entity_state:
            return self.entity_state.get_pickups(max_stale_frames)
        return []

    def get_bombs_stateful(self, max_stale_frames: int = 30) -> List[Any]:
        """获取炸弹（有状态保持版）"""
        if self.entity_state:
            return self.entity_state.get_bombs(max_stale_frames)
        return []

    def get_grid_entities_stateful(self) -> List[Any]:
        """获取网格实体/障碍物（有状态保持版）
        
        静态实体，返回所有已知的网格实体。
        障碍物破坏是状态变化（如岩石变碎片），不是移除。
        """
        if self.entity_state:
            return self.entity_state.get_grid_entities()
        return []

    def get_threat_count(self) -> int:
        """获取威胁数量（敌人 + 敌方投射物）"""
        if self.entity_state:
            return self.entity_state.get_threat_count()
        enemies = self.processor.get_enemies()
        return len(enemies) if enemies else 0

    def get_entity_state_stats(self) -> Optional[Dict[str, Any]]:
        """获取实体状态统计"""
        if self.entity_state:
            return self.entity_state.get_stats()
        return None

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
        stats = {
            "connected": self._connected,
            "last_frame": self._last_frame,
            "last_room": self._last_room,
            "processor": self.processor.get_stats(),
        }
        if self.entity_state:
            stats["entity_state"] = self.entity_state.get_stats()
        return stats

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
