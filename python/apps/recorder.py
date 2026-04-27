#!/usr/bin/env python3
"""
SocketBridge 游戏数据录制工具

完整的游戏数据录制应用，用于：
- 实时录制游戏数据（连接游戏）
- 自动会话管理（按游戏开始/结束分割）
- 支持手动控制（开始/停止/暂停）
- 生成录制摘要和统计信息

使用方法:
    # 启动录制器（等待游戏连接）
    python apps/recorder.py

    # 指定输出目录
    python apps/recorder.py --output ./my_recordings

    # 自动录制模式（游戏开始时自动开始录制）
    python apps/recorder.py --auto

    # 列出现有录制
    python apps/recorder.py --list

    # 清理旧录制
    python apps/recorder.py --cleanup --keep 10

快捷键（录制过程中）:
    r - 开始/停止录制
    p - 暂停/恢复录制
    s - 显示当前状态
    l - 列出所有会话
    q - 退出
"""

import os
import sys
import time
import json
import signal
import argparse
import threading
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from isaac_bridge import IsaacBridge, DataMessage, Event
from persistence import (
    SessionRecorder as DataRecorder,
    RecorderConfig,
    SessionManager,
    list_sessions,
    get_latest_session,
)
from protocol.messages import RawMessage

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("GameRecorder")


class Colors:
    """ANSI 颜色代码"""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"

    @classmethod
    def success(cls, text: str) -> str:
        return f"{cls.GREEN}{text}{cls.RESET}"

    @classmethod
    def warning(cls, text: str) -> str:
        return f"{cls.YELLOW}{text}{cls.RESET}"

    @classmethod
    def error(cls, text: str) -> str:
        return f"{cls.RED}{text}{cls.RESET}"

    @classmethod
    def info(cls, text: str) -> str:
        return f"{cls.CYAN}{text}{cls.RESET}"

    @classmethod
    def highlight(cls, text: str) -> str:
        return f"{cls.BOLD}{cls.MAGENTA}{text}{cls.RESET}"


class GameRecorder:
    """
    游戏数据录制器

    完整的录制应用，支持：
    - 自动/手动录制模式
    - 实时状态显示
    - 会话管理
    """

    def __init__(
        self,
        output_dir: str = "./recordings",
        host: str = "127.0.0.1",
        port: int = 9527,
        auto_record: bool = False,
        buffer_size: int = 500,
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.host = host
        self.port = port
        self.auto_record = auto_record

        # 创建桥接
        self.bridge = IsaacBridge(host, port)

        # 创建录制器
        self.recorder = DataRecorder(
            RecorderConfig(
                output_dir=str(self.output_dir),
                buffer_size=buffer_size,
                auto_save_interval=30.0,
                compress=True,
                include_events=True,
            )
        )

        # 状态
        self.connected = False
        self.running = False
        self.paused = False

        # 统计
        self.stats = {
            "messages_received": 0,
            "frames_received": 0,
            "events_received": 0,
            "current_frame": 0,
            "current_room": -1,
            "connect_time": None,
        }

        # 会话管理
        self.session_manager = SessionManager(str(self.output_dir))

        # 设置事件处理
        self._setup_handlers()

    def _setup_handlers(self):
        """设置事件处理器"""

        @self.bridge.on("connected")
        def on_connected(data):
            self.connected = True
            self.stats["connect_time"] = time.time()
            addr = data.get("address", ("unknown", 0)) if isinstance(data, dict) else ("unknown", 0)
            print(Colors.success(f"\n✓ 游戏已连接! ({addr[0]}:{addr[1]})"))
            
            if self.auto_record:
                # 自动录制模式：连接时立即开始/恢复录制
                if not self.recorder.is_recording:
                    self._start_recording(metadata={"trigger": "CONNECTED", "address": str(addr)})
                elif self.paused:
                    # 如果之前暂停了，恢复录制
                    self.paused = False
                    print(Colors.success("▶ 录制已恢复（游戏重新连接）"))
            else:
                print(Colors.info("  按 'r' 开始录制"))

        @self.bridge.on("disconnected")
        def on_disconnected(data=None):
            self.connected = False
            print(Colors.warning("\n⚠ 游戏已断开连接"))
            
            if self.auto_record and self.recorder.is_recording:
                # 自动录制模式：断开时只暂停，不停止
                if not self.paused:
                    self.paused = True
                    print(Colors.warning("⏸ 录制已暂停（等待重新连接...）"))
            elif self.recorder.is_recording:
                # 手动模式：断开时停止录制
                self._stop_recording()

        @self.bridge.on("message")
        def on_message(msg: DataMessage):
            self._handle_data(msg)

        @self.bridge.on("event:GAME_START")
        def on_game_start(data):
            self.stats["events_received"] += 1
            print(Colors.highlight(f"\n🎮 游戏开始! {data}"))
            # 自动模式下已经在连接时开始录制，这里只记录事件

        @self.bridge.on("event:GAME_END")
        def on_game_end(data):
            self.stats["events_received"] += 1
            print(Colors.highlight(f"\n🏁 游戏结束! {data}"))
            # 自动模式下不在此停止录制，只有手动才能停止

        @self.bridge.on("event:ROOM_CHANGED")
        def on_room_changed(data):
            self.stats["events_received"] += 1
            room_idx = data.get("room_index", -1)
            self.stats["current_room"] = room_idx

        @self.bridge.on("event")
        def on_any_event(event):
            # event 是 Event 对象，包含 type, data, frame
            event_type = event.type
            event_data = event.data
            
            # 录制事件
            if self.recorder.is_recording and not self.paused:
                event_msg = RawMessage(
                    msg_type="EVENT",
                    frame=event.frame if event.frame else self.stats["current_frame"],
                    room_index=self.stats["current_room"],
                    event_type=event_type,
                    event_data=event_data,
                )
                self.recorder.record_message(event_msg)

    def _handle_data(self, msg: DataMessage):
        """处理数据消息"""
        self.stats["messages_received"] += 1
        self.stats["current_frame"] = msg.frame
        self.stats["current_room"] = msg.room_index

        if msg.frame > self.stats["frames_received"]:
            self.stats["frames_received"] = msg.frame

        # 录制
        if self.recorder.is_recording and not self.paused:
            raw_msg = RawMessage(
                msg_type=msg.msg_type,
                version=str(msg.version) if hasattr(msg, "version") else "2.0",
                timestamp=msg.timestamp if hasattr(msg, "timestamp") else 0,
                frame=msg.frame,
                room_index=msg.room_index,
                payload=msg.payload,
                channels=msg.channels if hasattr(msg, "channels") else list(msg.payload.keys()),
            )
            self.recorder.record_message(raw_msg)

    def _start_recording(self, metadata: Optional[Dict[str, Any]] = None):
        """开始录制"""
        if self.recorder.is_recording:
            print(Colors.warning("⚠ 已经在录制中"))
            return

        session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")
        meta = metadata or {}
        meta["host"] = self.host
        meta["port"] = self.port

        session = self.recorder.start_session(session_id, meta)
        print(Colors.success(f"\n● 开始录制: {session.session_id}"))
        self.paused = False

    def _stop_recording(self):
        """停止录制"""
        if not self.recorder.is_recording:
            print(Colors.warning("⚠ 没有正在进行的录制"))
            return

        metadata = self.recorder.stop_session()
        if metadata:
            print(Colors.success(f"\n■ 停止录制: {metadata.session_id}"))
            print(f"  帧数: {metadata.total_frames}")
            print(f"  消息数: {metadata.total_messages}")
            print(f"  事件数: {metadata.total_events}")
            print(f"  持续时间: {metadata.duration_formatted}")

    def _toggle_pause(self):
        """切换暂停状态"""
        if not self.recorder.is_recording:
            print(Colors.warning("⚠ 没有正在进行的录制"))
            return

        self.paused = not self.paused
        if self.paused:
            print(Colors.warning("⏸ 录制已暂停"))
        else:
            print(Colors.success("▶ 录制已恢复"))

    def _show_status(self):
        """显示当前状态"""
        print("\n" + "=" * 50)
        print(Colors.highlight("📊 录制器状态"))
        print("=" * 50)

        # 连接状态
        if self.connected:
            print(f"  连接: {Colors.success('已连接')}")
            if self.stats["connect_time"]:
                uptime = time.time() - self.stats["connect_time"]
                print(f"  在线时长: {int(uptime)}秒")
        else:
            print(f"  连接: {Colors.error('未连接')}")

        # 录制状态
        if self.recorder.is_recording:
            session = self.recorder.current_session
            if self.paused:
                print(f"  录制: {Colors.warning('暂停中')} ({session.session_id})")
            else:
                print(f"  录制: {Colors.success('录制中')} ({session.session_id})")
            print(f"  已录制帧: {session.frames_recorded}")
            print(f"  已录制消息: {session.messages_recorded}")
        else:
            print(f"  录制: {Colors.info('未开始')}")

        # 数据统计
        print(f"\n  接收消息总数: {self.stats['messages_received']}")
        print(f"  接收帧总数: {self.stats['frames_received']}")
        print(f"  接收事件数: {self.stats['events_received']}")
        print(f"  当前帧: {self.stats['current_frame']}")
        print(f"  当前房间: {self.stats['current_room']}")
        print("=" * 50)

    def _list_sessions(self):
        """列出所有会话"""
        sessions = self.session_manager.list_sessions()
        print("\n" + "=" * 60)
        print(Colors.highlight("📁 录制会话列表"))
        print("=" * 60)

        if not sessions:
            print("  (无录制会话)")
        else:
            for i, s in enumerate(sessions[:20], 1):
                status = "▶" if s.total_frames > 0 else "○"
                print(
                    f"  {status} {i:2d}. {s.session_id}"
                    f"  {s.duration_formatted}  {s.size_formatted}"
                    f"  ({s.total_frames} frames)"
                )

            if len(sessions) > 20:
                print(f"  ... 还有 {len(sessions) - 20} 个会话")

            # 统计
            stats = self.session_manager.get_stats()
            print("-" * 60)
            print(f"  总计: {stats['total_sessions']} 个会话")
            print(f"  总帧数: {stats['total_frames']}")
            total_mb = stats["total_size"] / (1024 * 1024)
            print(f"  总大小: {total_mb:.1f} MB")

        print("=" * 60)

    def run(self):
        """运行录制器"""
        self.running = True

        # 启动桥接
        print(Colors.info("=" * 50))
        print(Colors.highlight("🎮 SocketBridge 游戏数据录制器"))
        print(Colors.info("=" * 50))
        print(f"  监听地址: {self.host}:{self.port}")
        print(f"  输出目录: {self.output_dir}")
        print(f"  自动录制: {'是' if self.auto_record else '否'}")
        print(Colors.info("-" * 50))
        print("  快捷键:")
        print("    r - 开始/停止录制")
        print("    p - 暂停/恢复录制")
        print("    s - 显示状态")
        print("    l - 列出会话")
        print("    q - 退出")
        print(Colors.info("=" * 50))
        print(Colors.warning("\n等待游戏连接..."))

        # 启动桥接线程
        bridge_thread = threading.Thread(target=self.bridge.start, daemon=True)
        bridge_thread.start()

        # 输入处理
        try:
            self._input_loop()
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()

    def _input_loop(self):
        """输入处理循环"""
        import msvcrt  # Windows

        while self.running:
            if msvcrt.kbhit():
                key = msvcrt.getch().decode("utf-8", errors="ignore").lower()

                if key == "q":
                    print(Colors.info("\n正在退出..."))
                    self.running = False
                elif key == "r":
                    if self.recorder.is_recording:
                        self._stop_recording()
                    else:
                        self._start_recording()
                elif key == "p":
                    self._toggle_pause()
                elif key == "s":
                    self._show_status()
                elif key == "l":
                    self._list_sessions()

            time.sleep(0.1)

    def _shutdown(self):
        """关闭"""
        if self.recorder.is_recording:
            self._stop_recording()
        self.bridge.stop()
        print(Colors.info("录制器已关闭"))


def main():
    parser = argparse.ArgumentParser(
        description="SocketBridge 游戏数据录制工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python apps/recorder.py                    # 启动录制器
  python apps/recorder.py --auto             # 自动录制模式
  python apps/recorder.py --list             # 列出所有录制
  python apps/recorder.py --cleanup --keep 5 # 保留最新5个录制
        """,
    )

    parser.add_argument(
        "--output", "-o",
        default="./recordings",
        help="录制输出目录 (默认: ./recordings)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="监听地址 (默认: 127.0.0.1)",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=9527,
        help="监听端口 (默认: 9527)",
    )
    parser.add_argument(
        "--auto", "-a",
        action="store_true",
        help="自动录制模式（游戏开始时自动开始录制）",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="列出所有录制会话",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="清理旧录制",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=10,
        help="清理时保留的会话数量 (默认: 10)",
    )
    parser.add_argument(
        "--buffer",
        type=int,
        default=500,
        help="消息缓冲区大小 (默认: 500)",
    )

    args = parser.parse_args()

    # 列出会话
    if args.list:
        manager = SessionManager(args.output)
        sessions = manager.list_sessions()
        print(f"\n录制会话 ({args.output}):")
        print("=" * 70)
        if not sessions:
            print("  (无录制会话)")
        else:
            for i, s in enumerate(sessions, 1):
                print(
                    f"  {i:2d}. {s.session_id}  "
                    f"时长: {s.duration_formatted}  "
                    f"大小: {s.size_formatted}  "
                    f"帧数: {s.total_frames}"
                )
            stats = manager.get_stats()
            print("-" * 70)
            print(f"  总计: {stats['total_sessions']} 个会话, {stats['total_size'] / 1024 / 1024:.1f} MB")
        return

    # 清理
    if args.cleanup:
        manager = SessionManager(args.output)
        deleted = manager.cleanup(keep_count=args.keep)
        print(f"已清理 {deleted} 个旧录制会话")
        return

    # 启动录制器
    recorder = GameRecorder(
        output_dir=args.output,
        host=args.host,
        port=args.port,
        auto_record=args.auto,
        buffer_size=args.buffer,
    )
    recorder.run()


if __name__ == "__main__":
    main()
