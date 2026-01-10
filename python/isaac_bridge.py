"""
The Binding of Isaac: Repentance - 数据接收与控制框架
Python 端实现

功能:
1. 接收游戏实时数据
2. 维护游戏状态
3. 发送控制指令
4. 事件处理系统
5. 数据通道配置
"""

import socket
import json
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, List, Tuple
from queue import Queue, Empty
from enum import Enum
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("IsaacBridge")


class MessageType(Enum):
    """消息类型枚举"""

    DATA = "DATA"
    FULL_STATE = "FULL"
    EVENT = "EVENT"
    COMMAND = "CMD"


class CollectInterval(Enum):
    """采集频率枚举"""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    ON_CHANGE = "ON_CHANGE"


@dataclass
class GameState:
    """游戏状态容器，支持增量更新"""

    data: Dict[str, Any] = field(default_factory=dict)
    last_update: Dict[str, int] = field(default_factory=dict)
    frame: int = 0
    room_index: int = -1

    def update(self, channel: str, payload: Any, frame: int):
        """更新单个通道数据"""
        self.data[channel] = payload
        self.last_update[channel] = frame
        self.frame = max(self.frame, frame)

    def update_batch(self, payload: Dict[str, Any], frame: int, room_index: int = None):
        """批量更新多个通道数据"""
        for channel, data in payload.items():
            self.data[channel] = data
            self.last_update[channel] = frame
        self.frame = max(self.frame, frame)
        if room_index is not None:
            self.room_index = room_index

    def get(self, channel: str) -> Optional[Any]:
        """获取单个通道数据"""
        return self.data.get(channel)

    def get_full_state(self) -> Dict[str, Any]:
        """获取完整状态"""
        return {
            "frame": self.frame,
            "room_index": self.room_index,
            "channels": dict(self.data),
            "last_update": dict(self.last_update),
        }

    def clear(self):
        """清空状态"""
        self.data.clear()
        self.last_update.clear()
        self.frame = 0
        self.room_index = -1


@dataclass
class Event:
    """游戏事件"""

    type: str
    data: Dict[str, Any]
    frame: int
    timestamp: float = field(default_factory=time.time)


class IsaacBridge:
    """
    以撒的结合数据桥接器

    主要功能:
    - TCP 服务器接收游戏数据
    - 维护实时游戏状态
    - 事件回调系统
    - 发送控制指令
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9527):
        self.host = host
        self.port = port

        # 网络
        self.server: Optional[socket.socket] = None
        self.client: Optional[socket.socket] = None
        self.client_addr: Optional[Tuple[str, int]] = None
        self.running = False

        # 状态
        self.state = GameState()
        self.connected = False

        # 事件系统
        self.event_queue: Queue[Event] = Queue()
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)

        # 线程
        self._accept_thread: Optional[threading.Thread] = None
        self._receive_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # 统计
        self.stats = {
            "messages_received": 0,
            "events_received": 0,
            "commands_sent": 0,
            "errors": 0,
        }

    def start(self):
        """启动服务器"""
        # 检查是否已在运行
        if self.running and self.server:
            logger.info("Server already running")
            return

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server.bind((self.host, self.port))
            self.server.listen(1)
            self.running = True

            # 创建新的接受线程
            self._accept_thread = threading.Thread(
                target=self._accept_loop, daemon=True
            )
            self._accept_thread.start()

            logger.info(f"Server started on {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            self.running = False
            self.server = None
            raise

    def stop(self):
        """停止服务器"""
        if not self.running:
            return

        self.running = False
        self.connected = False

        # 先关闭客户端连接
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

        # 关闭服务器 socket
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

        # 等待接受线程结束（最多1秒）
        if self._accept_thread and self._accept_thread.is_alive():
            self._accept_thread.join(timeout=1.0)

        self._accept_thread = None

        logger.info("Server stopped")

    def _accept_loop(self):
        """接受连接循环"""
        while self.running:
            if not self.server:
                break

            try:
                self.server.settimeout(1.0)
                client, addr = self.server.accept()

                # 关闭旧连接
                if self.client:
                    try:
                        self.client.shutdown(socket.SHUT_RDWR)
                    except:
                        pass
                    try:
                        self.client.close()
                    except:
                        pass

                self.client = client
                self.client_addr = addr
                self.connected = True
                self.state.clear()

                logger.info(f"Client connected: {addr}")
                self._trigger_handlers("connected", {"address": addr})

                # 启动接收线程
                self._receive_thread = threading.Thread(
                    target=self._receive_loop, daemon=True
                )
                self._receive_thread.start()

                # 等待接收线程结束
                self._receive_thread.join()
                self._receive_thread = None

            except socket.timeout:
                continue
            except OSError as e:
                if self.running:
                    logger.error(f"Accept error: {e}")
                    self.stats["errors"] += 1
                break
            except Exception as e:
                if self.running:
                    logger.error(f"Accept error: {e}")
                    self.stats["errors"] += 1

    def _receive_loop(self):
        """接收数据循环"""
        buffer = ""
        last_data_time = time.time()
        heartbeat_interval = 5.0  # 5秒没有数据视为断开

        while self.running and self.connected and self.client:
            try:
                self.client.settimeout(0.5)
                data = self.client.recv(65536)

                if not data:
                    # 对方关闭连接（游戏正常退出）
                    logger.info("Game closed connection")
                    break

                last_data_time = time.time()
                buffer += data.decode("utf-8")

                # 处理完整的 JSON 行
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        try:
                            msg = json.loads(line)
                            self._process_message(msg)
                            self.stats["messages_received"] += 1
                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON decode error: {e}")
                            self.stats["errors"] += 1

            except socket.timeout:
                # 检查心跳超时（游戏可能异常退出）
                if time.time() - last_data_time > heartbeat_interval:
                    logger.warning(
                        "No data received for 5 seconds, game may have exited"
                    )
                    break
                continue
            except ConnectionResetError:
                logger.info("Connection reset by game (likely closed)")
                break
            except BrokenPipeError:
                logger.info("Connection broken (game exited)")
                break
            except OSError as e:
                if e.errno == 10054:  # WSAECONNRESET
                    logger.info("Connection reset by peer")
                else:
                    logger.error(f"Network error: {e}")
                break
            except Exception as e:
                logger.error(f"Receive error: {e}")
                self.stats["errors"] += 1
                break

        # 连接断开处理
        self._handle_disconnect()

    def _handle_disconnect(self):
        """处理连接断开，清理资源并触发事件"""
        if self.connected:
            self.connected = False

            # 清理客户端连接
            if self.client:
                try:
                    self.client.close()
                except:
                    pass
                self.client = None

            logger.info("Disconnected from game, waiting for reconnection...")
            self._trigger_handlers("disconnected", {})

    def _process_message(self, msg: dict):
        """处理接收到的消息"""
        msg_type = msg.get("type")
        frame = msg.get("frame", 0)
        room_index = msg.get("room_index", -1)

        if msg_type == MessageType.DATA.value:
            # 增量数据更新
            payload = msg.get("payload", {})
            channels = msg.get("channels", [])

            self.state.update_batch(payload, frame, room_index)

            # 触发数据更新回调
            for channel in channels:
                self._trigger_handlers(f"data:{channel}", payload.get(channel))

            self._trigger_handlers("data", payload)

        elif msg_type == MessageType.FULL_STATE.value:
            # 完整状态更新
            payload = msg.get("payload", {})
            self.state.update_batch(payload, frame, room_index)
            self._trigger_handlers("full_state", self.state.get_full_state())

        elif msg_type == MessageType.EVENT.value:
            # 游戏事件
            event_type = msg.get("event")
            event_data = msg.get("data", {})

            event = Event(type=event_type, data=event_data, frame=frame)
            self.event_queue.put(event)
            self.stats["events_received"] += 1

            self._trigger_handlers(f"event:{event_type}", event_data)
            self._trigger_handlers("event", event)

        elif msg_type == MessageType.COMMAND.value:
            # 命令响应
            result = msg.get("result", {})
            self._trigger_handlers("command_result", result)

    def _trigger_handlers(self, event: str, data: Any):
        """触发事件处理器"""
        for handler in self.handlers.get(event, []):
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Handler error for '{event}': {e}")
                self.stats["errors"] += 1

    # ==================== 公共 API ====================

    def on(self, event: str):
        """
        注册事件处理器（支持装饰器用法）

        事件类型:
        - "connected": 客户端连接
        - "disconnected": 客户端断开
        - "data": 任意数据更新
        - "data:{channel}": 特定通道数据更新 (如 "data:PLAYER_POSITION")
        - "event:{type}": 游戏事件 (如 "event:PLAYER_DAMAGE")
        - "event": 任意游戏事件
        - "full_state": 完整状态更新
        - "command_result": 命令执行结果
        """

        def decorator(handler: Callable):
            self.handlers[event].append(handler)
            return handler

        return decorator

    def off(self, event: str, handler: Callable = None):
        """移除事件处理器"""
        if handler:
            if handler in self.handlers[event]:
                self.handlers[event].remove(handler)
        else:
            self.handlers[event].clear()

    def send_input(
        self,
        move: Tuple[int, int] = None,
        shoot: Tuple[int, int] = None,
        use_item: bool = None,
        use_bomb: bool = None,
        use_card: bool = None,
        use_pill: bool = None,
        drop: bool = None,
    ):
        """
        发送输入指令

        Args:
            move: 移动方向 (-1, 0, 1)
            shoot: 射击方向 (-1, 0, 1)
            use_item: 使用主动道具
            use_bomb: 放置炸弹
            use_card: 使用卡牌
            use_pill: 使用药丸
            drop: 丢弃
        """
        if not self.connected:
            return False

        command = {}

        if move is not None:
            command["move"] = {"x": move[0], "y": move[1]}
        if shoot is not None:
            command["shoot"] = {"x": shoot[0], "y": shoot[1]}
        if use_item is not None:
            command["use_item"] = use_item
        if use_bomb is not None:
            command["use_bomb"] = use_bomb
        if use_card is not None:
            command["use_card"] = use_card
        if use_pill is not None:
            command["use_pill"] = use_pill
        if drop is not None:
            command["drop"] = drop

        return self._send(command)

    def send_command(self, command: str, params: dict = None):
        """
        发送系统命令

        可用命令:
        - SET_CHANNEL: 启用/禁用数据通道 {"channel": str, "enabled": bool}
        - SET_INTERVAL: 设置采集频率 {"channel": str, "interval": str}
        - GET_FULL_STATE: 请求完整状态
        - GET_CONFIG: 获取当前配置
        - SET_MANUAL: 设置手动模式 {"enabled": bool}
        """
        if not self.connected:
            return False

        msg = {"command": command, "params": params or {}}
        self.stats["commands_sent"] += 1
        return self._send(msg)

    def set_channel(self, channel: str, enabled: bool):
        """启用/禁用数据通道"""
        return self.send_command(
            "SET_CHANNEL", {"channel": channel, "enabled": enabled}
        )

    def set_interval(self, channel: str, interval: CollectInterval):
        """设置数据通道采集频率"""
        return self.send_command(
            "SET_INTERVAL", {"channel": channel, "interval": interval.value}
        )

    def request_full_state(self):
        """请求完整游戏状态"""
        return self.send_command("GET_FULL_STATE")

    def set_manual_mode(self, enabled: bool):
        """设置手动模式"""
        return self.send_command("SET_MANUAL", {"enabled": enabled})

    def send_console_command(self, command: str) -> bool:
        """
        发送控制台指令到游戏执行

        支持的控制台指令（参考 IsaacGuru Wiki）:
        - spawn <entity_id>.[type].[subtype].[champion] - 生成实体 (如: spawn 10.0.0, spawn fatty)
        - g <item> - 给予物品 (如: g c1, g t12, g cricket)
        - g2 <item> - 给予次要角色物品 (如: g2 c1)
        - r <item> - 移除物品 (如: r c273, r *)
        - r2 <item> - 移除次要角色物品
        - stage <id>[type] - 传送到楼层 (如: stage 1, stage 2c)
        - goto d.<id> 或 goto s.<type>.<id> - 传送
        - gridspawn <grid_id> [location] - 生成网格实体 (障碍物等)
        - debug <mode> - 调试模式 (debug 10 = 秒杀所有敌人)
        - achievement <id> 或 <name> - 解锁成就
        - seed <seed> - 设置种子
        - restart [character] - 重新开始
        - lua <code> - 执行Lua代码
        - luarun <path> - 运行Lua文件
        - clear - 清空控制台文字
        - time - 显示游戏时间
        - restock - 补货商店

        Args:
            command: 控制台指令字符串，如 "giveitem c1" 或 "spawn 10.0.0"

        Returns:
            bool: 发送是否成功

        Examples:
            >>> bridge.send_console_command("g c1")  -- 给予以撒的眼泪
            >>> bridge.send_console_command("spawn 10.0.0")  -- 生成 Fly
            >>> bridge.send_console_command("stage 5a")  -- 传送到第5层
            >>> bridge.send_console_command("goto d.10")  -- 传送到房间10
            >>> bridge.send_console_command("lua print('Hello')")  -- 执行Lua代码
        """
        if not self.connected:
            return False

        msg = {"command": "EXEC_CONSOLE", "params": {"command": command}}
        self.stats["commands_sent"] += 1
        return self._send(msg)

    def _send(self, data: dict) -> bool:
        """发送数据"""
        if not self.connected or not self.client:
            return False

        try:
            msg = json.dumps(data) + "\n"
            self.client.send(msg.encode("utf-8"))
            return True
        except Exception as e:
            logger.error(f"Send error: {e}")
            self.stats["errors"] += 1
            return False

    def get_event(self, timeout: float = None) -> Optional[Event]:
        """获取下一个事件"""
        try:
            return self.event_queue.get(timeout=timeout)
        except Empty:
            return None

    def get_state(self) -> GameState:
        """获取当前游戏状态"""
        return self.state

    def get_channel(self, channel: str) -> Optional[Any]:
        """获取特定通道数据"""
        return self.state.get(channel)

    def get_stats(self) -> dict:
        """获取统计信息"""
        return dict(self.stats)

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.connected


# ==================== 便捷类 ====================


class GameDataAccessor:
    """游戏数据访问器，提供便捷的数据访问方法"""

    def __init__(self, bridge: IsaacBridge):
        self.bridge = bridge

    @property
    def state(self) -> GameState:
        return self.bridge.state

    @property
    def frame(self) -> int:
        return self.state.frame

    @property
    def room_index(self) -> int:
        return self.state.room_index

    def _get_player_data(self, channel: str, player_idx: int = 1) -> Optional[dict]:
        """
        通用的玩家数据获取方法
        处理 JSON 数组（list）和对象（dict）两种格式

        Lua 数组 {[1]=...} 序列化后可能是:
        - JSON 数组 [...] -> Python list (索引 0-based)
        - JSON 对象 {"1": ...} -> Python dict (键是字符串)
        """
        data = self.state.get(channel)
        if not data:
            return None

        # 如果是列表（JSON 数组），Lua 索引 1 对应 Python 索引 0
        if isinstance(data, list):
            idx = player_idx - 1  # Lua 1-based -> Python 0-based
            if 0 <= idx < len(data):
                return data[idx]
            return None

        # 如果是字典（JSON 对象）
        if isinstance(data, dict):
            # 尝试字符串键
            if str(player_idx) in data:
                return data[str(player_idx)]
            # 尝试整数键
            if player_idx in data:
                return data[player_idx]

        return None

    # 玩家数据
    def get_player_position(self, player_idx: int = 1) -> Optional[dict]:
        """获取玩家位置"""
        return self._get_player_data("PLAYER_POSITION", player_idx)

    def get_player_stats(self, player_idx: int = 1) -> Optional[dict]:
        """获取玩家属性"""
        return self._get_player_data("PLAYER_STATS", player_idx)

    def get_player_health(self, player_idx: int = 1) -> Optional[dict]:
        """获取玩家生命值"""
        return self._get_player_data("PLAYER_HEALTH", player_idx)

    def get_player_inventory(self, player_idx: int = 1) -> Optional[dict]:
        """获取玩家物品栏"""
        return self._get_player_data("PLAYER_INVENTORY", player_idx)

    # 房间数据
    def get_room_info(self) -> Optional[dict]:
        """获取房间信息"""
        return self.state.get("ROOM_INFO")

    def get_room_layout(self) -> Optional[dict]:
        """获取房间布局"""
        return self.state.get("ROOM_LAYOUT")

    def is_room_clear(self) -> bool:
        """房间是否已清空"""
        info = self.get_room_info()
        return info.get("is_clear", False) if info else False

    # 实体数据
    def get_enemies(self) -> List[dict]:
        """获取敌人列表"""
        return self.state.get("ENEMIES") or []

    def get_projectiles(self) -> dict:
        """获取投射物数据"""
        return self.state.get("PROJECTILES") or {
            "enemy_projectiles": [],
            "player_tears": [],
            "lasers": [],
        }

    def get_enemy_projectiles(self) -> List[dict]:
        """获取敌方投射物"""
        proj = self.get_projectiles()
        return proj.get("enemy_projectiles", [])

    def get_pickups(self) -> List[dict]:
        """获取可拾取物"""
        return self.state.get("PICKUPS") or []

    def get_fire_hazards(self) -> List[dict]:
        """获取火焰危险物"""
        return self.state.get("FIRE_HAZARDS") or []

    def get_destructibles(self) -> List[dict]:
        """获取可破坏物"""
        return self.state.get("DESTRUCTIBLES") or []

    def get_buttons(self) -> dict:
        """获取按钮状态"""
        return self.state.get("BUTTONS") or {}

    def get_bombs(self) -> List[dict]:
        """获取炸弹"""
        return self.state.get("BOMBS") or []

    def get_interactables(self) -> List[dict]:
        """获取可互动实体"""
        return self.state.get("INTERACTABLES") or []


# ==================== 示例用法 ====================


def main():
    """示例: 基础数据接收"""
    bridge = IsaacBridge(host="127.0.0.1", port=9527)
    data = GameDataAccessor(bridge)

    # 注册事件处理器
    @bridge.on("connected")
    def on_connected(info):
        logger.info(f"Game connected from {info['address']}")
        # 请求完整状态
        bridge.request_full_state()

    @bridge.on("disconnected")
    def on_disconnected(_):
        logger.info("Game disconnected")

    @bridge.on("data:PLAYER_POSITION")
    def on_player_position(pos_data):
        # pos_data 是列表 (JSON 数组)，索引 0 是第一个玩家
        if pos_data and isinstance(pos_data, list) and len(pos_data) > 0:
            pos = pos_data[0].get("pos", {})
            # logger.debug(f"Player at ({pos.get('x', 0):.1f}, {pos.get('y', 0):.1f})")

    @bridge.on("event:PLAYER_DAMAGE")
    def on_player_damage(event_data):
        logger.warning(f"Player took {event_data.get('amount', 0)} damage!")

    @bridge.on("event:ROOM_ENTER")
    def on_room_enter(event_data):
        logger.info(f"Entered room {event_data.get('room_index', -1)}")

    @bridge.on("event:ROOM_CLEAR")
    def on_room_clear(event_data):
        logger.info("Room cleared!")

    @bridge.on("event:GAME_START")
    def on_game_start(event_data):
        logger.info(f"Game started (continued={event_data.get('continued', False)})")

    @bridge.on("event:GAME_END")
    def on_game_end(event_data):
        logger.info(f"Game ended: {event_data.get('reason', 'unknown')}")

    # 启动服务器
    bridge.start()

    try:
        logger.info("Waiting for game connection... (Ctrl+C to stop)")

        frame_count = 0
        while True:
            time.sleep(1)

            if bridge.is_connected():
                frame_count += 1

                # 每5秒输出一次状态摘要
                if frame_count % 5 == 0:
                    enemies = data.get_enemies()
                    projectiles = data.get_enemy_projectiles()
                    pos = data.get_player_position()

                    pos_str = (
                        f"({pos['pos']['x']:.0f}, {pos['pos']['y']:.0f})"
                        if pos
                        else "N/A"
                    )
                    logger.info(
                        f"Frame {data.frame} | Room {data.room_index} | "
                        f"Pos: {pos_str} | "
                        f"Enemies: {len(enemies)} | Projectiles: {len(projectiles)}"
                    )

                    # 示例: 发送简单输入
                    # bridge.send_input(move=(0, 0), shoot=(0, 0))

    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
