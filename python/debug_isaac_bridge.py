"""
调试版本的 isaac_bridge.py 片段
用于诊断数据接收问题

使用方法：
1. 将此文件保存到 python/debug_isaac_bridge.py
2. 在调试录制脚本中导入此模块替代 isaac_bridge
3. 运行并观察输出
"""

import sys
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from queue import Queue, Empty
from enum import Enum
import socket
import threading
import time

# 设置调试日志
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s [%(levelname)s] [DEBUG_BRIDGE] %(message)s"
)
logger = logging.getLogger("DEBUG_BRIDGE")


class MessageType(Enum):
    """消息类型"""

    DATA = "DATA"
    FULL_STATE = "FULL"
    EVENT = "EVENT"
    COMMAND = "CMD"


class Event:
    """游戏事件"""

    def __init__(self, type: str, data: Dict, frame: int):
        self.type = type
        self.data = data
        self.frame = frame
        self.timestamp = time.time()


class GameState:
    """游戏状态管理"""

    def __init__(self):
        self._data = {}
        self._frame = 0
        self._room_index = -1
        self._lock = threading.Lock()

    def update_batch(self, payload: Dict, frame: int, room_index: int):
        with self._lock:
            self._frame = frame
            self._room_index = room_index
            for key, value in payload.items():
                self._data[key] = value

    def __getattr__(self, name: str) -> Any:
        with self._lock:
            return self._data.get(name, {})

    def get_full_state(self) -> Dict:
        with self._lock:
            return {
                "data": self._data.copy(),
                "frame": self._frame,
                "room_index": self._room_index,
            }


class DebugIsaacBridge:
    """
    调试版 IsaacBridge - 增强日志输出
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9527):
        self.host = host
        self.port = port
        self.server: Optional[socket.socket] = None
        self.client: Optional[socket.socket] = None
        self.client_addr: Optional[Tuple[str, int]] = None
        self.running = False
        self.connected = False

        self.handlers: Dict[str, List[Callable]] = {
            "connected": [],
            "disconnected": [],
            "data": [],
            "data:PLAYER_POSITION": [],
            "data:ENEMIES": [],
            "data:PROJECTILES": [],
            "data:ROOM_INFO": [],
            "data:ROOM_LAYOUT": [],
            "event": [],
            "event:PLAYER_DAMAGE": [],
            "event:ROOM_ENTER": [],
            "event:ROOM_CLEAR": [],
            "event:NPC_DEATH": [],
            "full_state": [],
            "command_result": [],
        }

        self.state = GameState()
        self.event_queue: Queue = Queue()
        self.stats = {
            "messages_received": 0,
            "events_received": 0,
            "errors": 0,
        }

        self._accept_thread: Optional[threading.Thread] = None
        self._receive_thread: Optional[threading.Thread] = None

    def _trigger_handlers(self, event: str, data: Any):
        """触发事件处理器"""
        for handler in self.handlers.get(event, []):
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Handler error for '{event}': {e}")
                self.stats["errors"] += 1

    def _process_message(self, msg: dict):
        """处理接收到的消息"""
        logger.debug(f"[_process_message] 收到原始消息:")
        logger.debug(f"  keys: {list(msg.keys())}")
        logger.debug(f"  msg: {json.dumps(msg, indent=4, ensure_ascii=False)[:500]}...")

        msg_type = msg.get("type")
        frame = msg.get("frame", 0)
        room_index = msg.get("room_index", -1)

        logger.debug(f"[_process_message] 解析结果:")
        logger.debug(f"  msg_type: {msg_type}")
        logger.debug(f"  frame: {frame}")
        logger.debug(f"  room_index: {room_index}")

        if msg_type == MessageType.DATA.value:
            # 增量数据更新
            payload = msg.get("payload", {})
            channels = msg.get("channels", [])

            logger.debug(f"[_process_message] DATA 消息:")
            logger.debug(f"  payload type: {type(payload)}")
            logger.debug(
                f"  payload keys: {list(payload.keys()) if payload else 'None/Empty'}"
            )
            logger.debug(f"  channels: {channels}")

            self.state.update_batch(payload, frame, room_index)

            # 触发数据更新回调
            for channel in channels:
                logger.debug(f"[_process_message] 触发 data:{channel}")
                self._trigger_handlers(f"data:{channel}", payload.get(channel))

            logger.debug(f"[_process_message] 触发 data (payload)")
            self._trigger_handlers("data", payload)

        elif msg_type == MessageType.FULL_STATE.value:
            # 完整状态更新
            payload = msg.get("payload", {})
            logger.debug(
                f"[_process_message] FULL_STATE 消息: payload keys = {list(payload.keys())}"
            )
            self.state.update_batch(payload, frame, room_index)
            self._trigger_handlers("full_state", self.state.get_full_state())

        elif msg_type == MessageType.EVENT.value:
            # 游戏事件
            event_type = msg.get("event")
            event_data = msg.get("data", {})

            logger.debug(f"[_process_message] EVENT 消息:")
            logger.debug(f"  event_type: {event_type}")
            logger.debug(
                f"  event_data: {json.dumps(event_data, ensure_ascii=False)[:200]}"
            )

            event = Event(type=event_type, data=event_data, frame=frame)
            self.event_queue.put(event)
            self.stats["events_received"] += 1

            self._trigger_handlers(f"event:{event_type}", event_data)
            self._trigger_handlers("event", event)

        elif msg_type == MessageType.COMMAND.value:
            # 命令响应
            result = msg.get("result", {})
            logger.debug(f"[_process_message] COMMAND 响应: {result}")
            self._trigger_handlers("command_result", result)
        else:
            logger.warning(f"[_process_message] 未知消息类型: {msg_type}")

    def on(self, event: str):
        """注册事件处理器"""

        def decorator(handler: Callable):
            self.handlers[event].append(handler)
            return handler

        return decorator

    def start(self):
        """启动服务器"""
        if self.running and self.server:
            logger.info("Server already running")
            return

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server.bind((self.host, self.port))
            self.server.listen(1)
            self.running = True

            self._accept_thread = threading.Thread(
                target=self._accept_loop, daemon=True
            )
            self._accept_thread.start()

            logger.info(f"Debug server started on {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            self.running = False
            self.server = None
            raise

    def _accept_loop(self):
        """接受连接循环"""
        while self.running:
            if not self.server:
                break

            try:
                self.server.settimeout(1.0)
                client, addr = self.server.accept()

                if self.client:
                    try:
                        self.client.close()
                    except:
                        pass

                self.client = client
                self.client_addr = addr
                self.connected = True

                logger.info(f"Client connected: {addr}")
                self._trigger_handlers("connected", {"address": addr})

                # 启动接收线程
                self._receive_thread = threading.Thread(
                    target=self._receive_loop, daemon=True
                )
                self._receive_thread.start()

                self._receive_thread.join()
                self._receive_thread = None

            except socket.timeout:
                continue
            except OSError as e:
                if self.running:
                    logger.error(f"Accept error: {e}")
                break
            except Exception as e:
                if self.running:
                    logger.error(f"Accept error: {e}")

    def _receive_loop(self):
        """接收数据循环"""
        buffer = ""
        last_data_time = time.time()
        heartbeat_interval = 5.0

        while self.running and self.connected and self.client:
            try:
                self.client.settimeout(0.5)
                data = self.client.recv(65536)

                if not data:
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
                            self.stats["messages_received"] += 1
                            self._process_message(msg)
                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON decode error: {e}")
                            self.stats["errors"] += 1

            except socket.timeout:
                # 检查心跳超时
                if time.time() - last_data_time > heartbeat_interval:
                    logger.warning(
                        "No data received for 5 seconds, game may have exited"
                    )
                    break
                continue

            except Exception as e:
                if self.running and self.connected:
                    logger.error(f"Receive error: {e}")
                break

        # 连接断开
        if self.connected:
            self.connected = False
            if self.client:
                try:
                    self.client.close()
                except:
                    pass
                self.client = None
            logger.info("Disconnected from game, waiting for reconnection...")
            self._trigger_handlers("disconnected", {})

    def stop(self):
        """停止服务器"""
        if not self.running:
            return

        self.running = False
        self.connected = False

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

        logger.info("Server stopped")


if __name__ == "__main__":
    print("这是一个调试模块，不能直接运行")
    print("请从 debug_record.py 导入使用")
