"""
Bridge Adapter - 连接适配器

将现有 IsaacBridge 与新架构（services/facade）集成。
提供统一的接口访问游戏数据。
"""

from typing import Dict, Any, Optional, List, Callable, Tuple
from dataclasses import dataclass
import logging
import time
import sys
from pathlib import Path

# 确保 python/ 目录在路径中
_python_root = Path(__file__).parent.parent.parent
if str(_python_root) not in sys.path:
    sys.path.insert(0, str(_python_root))

from isaac_bridge import IsaacBridge, DataMessage, Event, CollectInterval
from services.facade import SocketBridgeFacade, BridgeConfig
from services.monitor import DataQualityMonitor, QualityIssue
from services.processor import ProcessedChannel

logger = logging.getLogger(__name__)


@dataclass
class AdapterConfig:
    """适配器配置"""
    host: str = "127.0.0.1"
    port: int = 9527
    validation_enabled: bool = True
    monitoring_enabled: bool = True
    auto_reconnect: bool = True
    log_messages: bool = False


class BridgeAdapter:
    """
    连接适配器 - 将 IsaacBridge 消息路由到新架构
    
    功能：
    - 复用现有 IsaacBridge 网络层
    - 使用新的 SocketBridgeFacade 处理数据
    - 提供统一的 API 访问游戏数据
    - 支持质量监控
    
    使用示例：
    ```python
    adapter = BridgeAdapter()
    
    @adapter.on("connected")
    def on_connected():
        print("游戏已连接!")
    
    @adapter.on("frame")
    def on_frame(frame, data):
        pos = adapter.get_player_position()
        print(f"Frame {frame}: Player at {pos}")
    
    adapter.start()
    ```
    """
    
    def __init__(self, config: Optional[AdapterConfig] = None):
        self.config = config or AdapterConfig()
        
        # 底层网络桥接
        self.bridge = IsaacBridge(self.config.host, self.config.port)
        
        # 新架构服务层
        facade_config = BridgeConfig(
            host=self.config.host,
            port=self.config.port,
            validation_enabled=self.config.validation_enabled,
            monitoring_enabled=self.config.monitoring_enabled,
        )
        self.facade = SocketBridgeFacade(facade_config)
        
        # 状态
        self._connected = False
        self._last_frame = 0
        self._message_count = 0
        self._start_time = time.time()
        
        # 用户回调
        self._callbacks: Dict[str, List[Callable]] = {
            "connected": [],
            "disconnected": [],
            "frame": [],
            "room_change": [],
            "issue": [],
            "message": [],
        }
        
        # 注册内部处理器
        self._setup_handlers()
    
    def _setup_handlers(self):
        """设置内部消息处理器"""
        
        @self.bridge.on("connected")
        def on_connected(data):
            self._connected = True
            self._start_time = time.time()
            logger.info(f"Game connected from {data.get('address')}")
            self._emit("connected", data)
        
        @self.bridge.on("disconnected")
        def on_disconnected(data):
            self._connected = False
            logger.info("Game disconnected")
            self._emit("disconnected", data)
        
        @self.bridge.on("raw_message")
        def on_raw_message(msg: dict):
            self._process_raw_message(msg)
    
    def _process_raw_message(self, msg: dict):
        """处理原始消息，路由到新架构"""
        msg_type = msg.get("type")
        
        if msg_type in ("DATA", "FULL"):
            # 使用新架构处理
            try:
                result = self.facade.process_message(msg)
                
                frame = msg.get("frame", 0)
                room = msg.get("room_index", -1)
                
                self._message_count += 1
                self._last_frame = frame
                
                # 触发帧回调
                self._emit("frame", frame, result)
                
                # 触发消息回调
                self._emit("message", msg, result)
                
                # 日志输出（调试用）
                if self.config.log_messages:
                    channels = msg.get("channels", [])
                    logger.debug(f"Frame {frame}: {channels}")
                    
            except Exception as e:
                logger.error(f"Error processing message: {e}")
    
    def _emit(self, event: str, *args, **kwargs):
        """触发用户回调"""
        for cb in self._callbacks.get(event, []):
            try:
                cb(*args, **kwargs)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")
    
    # ==================== 公共 API ====================
    
    def on(self, event: str):
        """
        注册事件回调（装饰器用法）
        
        事件类型：
        - "connected": 游戏连接
        - "disconnected": 游戏断开
        - "frame": 每帧数据 (frame, processed_channels)
        - "room_change": 房间切换 (new_room, old_room)
        - "issue": 质量问题 (QualityIssue)
        - "message": 原始消息 (msg_dict, processed_channels)
        
        使用示例：
        ```python
        @adapter.on("frame")
        def on_frame(frame, data):
            print(f"Frame: {frame}")
        ```
        """
        def decorator(handler: Callable):
            if event in self._callbacks:
                self._callbacks[event].append(handler)
            else:
                # 直接转发到底层 bridge
                self.bridge.handlers[event].append(handler)
            return handler
        return decorator
    
    def off(self, event: str, handler: Callable = None):
        """移除事件回调"""
        if event in self._callbacks:
            if handler:
                if handler in self._callbacks[event]:
                    self._callbacks[event].remove(handler)
            else:
                self._callbacks[event].clear()
        else:
            self.bridge.off(event, handler)
    
    def start(self):
        """启动适配器（开始监听连接）"""
        logger.info(f"Starting BridgeAdapter on {self.config.host}:{self.config.port}")
        self.bridge.start()
    
    def stop(self):
        """停止适配器"""
        logger.info("Stopping BridgeAdapter")
        self.bridge.stop()
    
    @property
    def connected(self) -> bool:
        """是否已连接"""
        return self._connected and self.bridge.connected
    
    @property
    def last_frame(self) -> int:
        """最后处理的帧号"""
        return self._last_frame
    
    @property
    def message_count(self) -> int:
        """已处理消息数"""
        return self._message_count
    
    # ==================== 数据访问 API ====================
    
    def get_player_position(self, player_idx: int = 1) -> Optional[Tuple[float, float]]:
        """
        获取玩家位置
        
        Returns:
            (x, y) 坐标元组，或 None
        """
        data = self.facade.get_player_position()
        if data and hasattr(data, 'get_position'):
            return data.get_position(player_idx)
        elif data and hasattr(data, 'players'):
            player = data.players.get(player_idx)
            if player:
                return (player.pos.x, player.pos.y)
        return None
    
    def get_player_velocity(self, player_idx: int = 1) -> Optional[Tuple[float, float]]:
        """获取玩家速度"""
        data = self.facade.get_player_position()
        if data and hasattr(data, 'get_velocity'):
            return data.get_velocity(player_idx)
        elif data and hasattr(data, 'players'):
            player = data.players.get(player_idx)
            if player:
                return (player.vel.x, player.vel.y)
        return None
    
    def get_player_stats(self) -> Optional[Dict[str, Any]]:
        """获取玩家属性"""
        return self.facade.get_player_stats()
    
    def get_room_info(self) -> Optional[Dict[str, Any]]:
        """获取房间信息"""
        return self.facade.get_room_info()
    
    def get_enemies(self) -> Optional[List[Dict[str, Any]]]:
        """获取敌人列表"""
        data = self.facade.processor.get_data("ENEMIES")
        if data:
            return data
        return None
    
    def get_projectiles(self) -> Optional[Dict[str, Any]]:
        """获取投射物"""
        return self.facade.processor.get_data("PROJECTILES")
    
    def get_pickups(self) -> Optional[List[Dict[str, Any]]]:
        """获取拾取物"""
        return self.facade.processor.get_data("PICKUPS")
    
    def get_bombs(self) -> Optional[List[Dict[str, Any]]]:
        """获取炸弹"""
        return self.facade.processor.get_data("BOMBS")
    
    def get_channel(self, name: str) -> Optional[Any]:
        """获取任意通道数据"""
        return self.facade.get_data(name)
    
    def is_channel_fresh(self, name: str, max_stale_frames: int = 5) -> bool:
        """检查通道数据是否新鲜"""
        return self.facade.is_channel_fresh(name, max_stale_frames)
    
    def get_synchronized_data(
        self, 
        channels: List[str], 
        max_frame_diff: int = 5
    ) -> Optional[Dict[str, Any]]:
        """获取同步数据（多通道数据帧对齐）"""
        return self.facade.get_synchronized_data(channels, max_frame_diff)
    
    # ==================== 控制 API ====================
    
    def send_input(
        self,
        move: Tuple[int, int] = None,
        shoot: Tuple[int, int] = None,
        use_item: bool = None,
        use_bomb: bool = None,
    ) -> bool:
        """
        发送输入指令
        
        Args:
            move: 移动方向 (x, y)，值为 -1, 0, 1
            shoot: 射击方向 (x, y)，值为 -1, 0, 1
            use_item: 使用主动道具
            use_bomb: 放置炸弹
        
        Returns:
            是否发送成功
        """
        return self.bridge.send_input(
            move=move,
            shoot=shoot,
            use_item=use_item,
            use_bomb=use_bomb,
        )
    
    def set_channel(self, channel: str, enabled: bool) -> bool:
        """启用/禁用数据通道"""
        return self.bridge.set_channel(channel, enabled)
    
    def set_interval(self, channel: str, interval: str) -> bool:
        """设置通道采集频率"""
        interval_enum = CollectInterval(interval)
        return self.bridge.set_interval(channel, interval_enum)
    
    def request_full_state(self) -> bool:
        """请求完整游戏状态"""
        return self.bridge.request_full_state()
    
    def set_manual_mode(self, enabled: bool) -> bool:
        """设置手动模式（禁用 AI 控制）"""
        return self.bridge.set_manual_mode(enabled)
    
    # ==================== 监控 API ====================
    
    def get_quality_report(self) -> str:
        """获取数据质量报告"""
        return self.facade.get_quality_report()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = time.time() - self._start_time
        return {
            "connected": self.connected,
            "uptime_seconds": uptime,
            "last_frame": self._last_frame,
            "message_count": self._message_count,
            "messages_per_second": self._message_count / max(uptime, 1),
            "bridge_stats": self.bridge.stats,
            "facade_stats": self.facade.get_stats(),
        }
    
    def print_status(self):
        """打印当前状态（调试用）"""
        stats = self.get_stats()
        print("\n" + "=" * 50)
        print("BridgeAdapter Status")
        print("=" * 50)
        print(f"Connected: {stats['connected']}")
        print(f"Uptime: {stats['uptime_seconds']:.1f}s")
        print(f"Last Frame: {stats['last_frame']}")
        print(f"Messages: {stats['message_count']}")
        print(f"Rate: {stats['messages_per_second']:.1f} msg/s")
        print("=" * 50)


# 便捷函数
def create_adapter(
    host: str = "127.0.0.1",
    port: int = 9527,
    **kwargs
) -> BridgeAdapter:
    """创建适配器的便捷函数"""
    config = AdapterConfig(host=host, port=port, **kwargs)
    return BridgeAdapter(config)
