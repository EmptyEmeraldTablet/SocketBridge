"""
以撒的结合 - 数据记录器

用于记录游戏数据以供后续分析或训练使用
"""

import json
import time
import gzip
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from collections import deque
from isaac_bridge import IsaacBridge, GameDataAccessor, Event, DataMessage
import logging
import threading

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("DataRecorder")


class GameDataRecorder:
    """游戏数据记录器"""

    def __init__(self, bridge: IsaacBridge, output_dir: str = "./recordings"):
        self.bridge = bridge
        self.data = GameDataAccessor(bridge)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 记录状态
        self.recording = False
        self.current_session: Optional[Dict] = None
        self.frame_buffer: List[Dict] = []
        self.event_buffer: List[Dict] = []

        # 配置
        self.buffer_size = 1000  # 缓冲区大小
        self.save_interval = 60.0  # 自动保存间隔（秒）

        # 统计
        self.stats = {
            "frames_recorded": 0,
            "events_recorded": 0,
            "sessions": 0,
        }

        self._setup_handlers()

    def _setup_handlers(self):
        """设置事件处理器"""

        @self.bridge.on("event:GAME_START")
        def on_game_start(data):
            self.start_session(continued=data.get("continued", False))

        @self.bridge.on("event:GAME_END")
        def on_game_end(data):
            self.end_session(reason=data.get("reason", "unknown"))

        @self.bridge.on("event_message")
        def on_event_message(event: Event):
            if self.recording:
                self._record_event(event)

        @self.bridge.on("message")
        def on_message(msg: DataMessage):
            if self.recording:
                self._record_frame(msg)

    def start_session(self, continued: bool = False):
        """开始新的记录会话"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.current_session = {
            "id": f"session_{timestamp}",
            "start_time": time.time(),
            "start_timestamp": timestamp,
            "continued": continued,
            "metadata": {},
        }

        self.frame_buffer.clear()
        self.event_buffer.clear()
        self.recording = True
        self.stats["sessions"] += 1

        logger.info(f"Recording session started: {self.current_session['id']}")

    def end_session(self, reason: str = "manual"):
        """结束当前记录会话"""
        if not self.recording or not self.current_session:
            return

        self.recording = False

        self.current_session["end_time"] = time.time()
        self.current_session["end_reason"] = reason
        self.current_session["duration"] = (
            self.current_session["end_time"] - self.current_session["start_time"]
        )
        self.current_session["total_frames"] = self.stats["frames_recorded"]
        self.current_session["total_events"] = self.stats["events_recorded"]

        # 保存数据
        self._save_session()

        logger.info(f"Recording session ended: {self.current_session['id']} ({reason})")
        self.current_session = None

    def _record_frame(self, msg: DataMessage):
        """记录一帧数据"""
        frame_data = {
            "frame": msg.frame,
            "room_index": msg.room_index,
            "timestamp": msg.timestamp / 1000.0,  # 毫秒转秒
            "data": msg.payload,
        }

        self.frame_buffer.append(frame_data)
        self.stats["frames_recorded"] += 1

        # 缓冲区满时保存
        if len(self.frame_buffer) >= self.buffer_size:
            self._flush_buffer()

    def _record_event(self, event: Event):
        """记录事件"""
        event_data = {
            "type": event.type,
            "frame": event.frame,
            "timestamp": event.timestamp,
            "data": event.data,
        }

        self.event_buffer.append(event_data)
        self.stats["events_recorded"] += 1

    def _flush_buffer(self):
        """将缓冲区数据写入临时文件"""
        if not self.current_session or not self.frame_buffer:
            return

        session_id = self.current_session["id"]
        chunk_id = len(list(self.output_dir.glob(f"{session_id}_chunk_*.json.gz")))

        chunk_file = self.output_dir / f"{session_id}_chunk_{chunk_id:04d}.json.gz"

        chunk_data = {
            "session_id": session_id,
            "chunk_id": chunk_id,
            "frames": self.frame_buffer.copy(),
        }

        with gzip.open(chunk_file, "wt", encoding="utf-8") as f:
            json.dump(chunk_data, f)

        self.frame_buffer.clear()
        logger.debug(f"Saved chunk: {chunk_file.name}")

    def _save_session(self):
        """保存会话元数据和剩余数据"""
        if not self.current_session:
            return

        session_id = self.current_session["id"]

        # 保存剩余帧数据
        self._flush_buffer()

        # 保存事件
        events_file = self.output_dir / f"{session_id}_events.json.gz"
        with gzip.open(events_file, "wt", encoding="utf-8") as f:
            json.dump({"events": self.event_buffer}, f)

        # 保存会话元数据
        meta_file = self.output_dir / f"{session_id}_meta.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(self.current_session, f, indent=2)

        logger.info(f"Session saved: {session_id}")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "recording": self.recording,
            "current_session": self.current_session["id"]
            if self.current_session
            else None,
            "buffer_size": len(self.frame_buffer),
        }


class DataInspector:
    """数据检查器 - 定期输出采集数据快照到日志"""

    def __init__(
        self,
        bridge: IsaacBridge,
        interval: float = 10.0,
        log_file: Optional[str] = None,
    ):
        """
        Args:
            bridge: IsaacBridge 实例
            interval: 输出间隔（秒）
            log_file: 可选的日志文件路径，不设置则只输出到控制台
        """
        self.bridge = bridge
        self.data = GameDataAccessor(bridge)
        self.interval = interval
        self.log_file = Path(log_file) if log_file else None

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._snapshot_count = 0

        # 数据通道列表
        self.channels = [
            "PLAYER_POSITION",
            "PLAYER_STATS",
            "PLAYER_HEALTH",
            "PLAYER_INVENTORY",
            "ENEMIES",
            "PROJECTILES",
            "ROOM_INFO",
            "ROOM_LAYOUT",
            "PICKUPS",
            "FIRE_HAZARDS",
            "DESTRUCTIBLES",
        ]

        # 确保日志目录存在
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def start(self):
        """启动定期检查"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._inspect_loop, daemon=True)
        self._thread.start()
        logger.info(f"DataInspector started (interval: {self.interval}s)")

    def stop(self):
        """停止检查"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info("DataInspector stopped")

    def _inspect_loop(self):
        """检查循环"""
        while self._running:
            time.sleep(self.interval)
            if self._running and self.bridge.connected:
                self._take_snapshot()

    def _take_snapshot(self):
        """获取并输出数据快照"""
        self._snapshot_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        lines = [
            "",
            "=" * 80,
            f"[Data Snapshot #{self._snapshot_count}] {timestamp}",
            f"Frame: {self.data.frame} | Room: {self.data.room_index}",
            "=" * 80,
        ]

        # 收集每个通道的数据摘要
        for channel in self.channels:
            raw_data = self.data.state.get(channel)
            summary = self._summarize_data(channel, raw_data)
            lines.append(f"\n[{channel}]")
            lines.append(summary)

        # 添加分隔线
        lines.append("\n" + "=" * 80)

        snapshot_text = "\n".join(lines)

        # 输出到控制台
        logger.info(snapshot_text)

        # 输出到文件
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(snapshot_text + "\n\n")

    def _summarize_data(self, channel: str, data: Any) -> str:
        """生成数据摘要"""
        if data is None:
            return "  (无数据)"

        try:
            if isinstance(data, dict):
                # 处理字典数据（如带数字键的玩家数据）
                if all(k.isdigit() for k in data.keys()):
                    # 数字键字典（如 {"1": {...}}）
                    items = list(data.values())
                    return self._format_list_data(channel, items)
                else:
                    return self._format_dict_data(data)

            elif isinstance(data, list):
                return self._format_list_data(channel, data)

            else:
                return f"  {data}"

        except Exception as e:
            return f"  (解析错误: {e})"

    def _format_dict_data(self, data: Dict) -> str:
        """格式化字典数据"""
        lines = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value, ensure_ascii=False)
                if len(value_str) > 60:
                    value_str = value_str[:60] + "..."
            else:
                value_str = str(value)
            lines.append(f"  {key}: {value_str}")
        return "\n".join(lines) if lines else "  (空字典)"

    def _format_list_data(self, channel: str, items: List) -> str:
        """格式化列表数据"""
        if not items:
            return "  (空列表)"

        lines = [f"  数量: {len(items)}"]

        # 显示前几个元素的详细信息
        max_show = 3
        for i, item in enumerate(items[:max_show]):
            if isinstance(item, dict):
                # 根据通道类型提取关键信息
                key_info = self._extract_key_info(channel, item)
                lines.append(f"  [{i}] {key_info}")
            else:
                lines.append(f"  [{i}] {item}")

        if len(items) > max_show:
            lines.append(f"  ... 还有 {len(items) - max_show} 个")

        return "\n".join(lines)

    def _extract_key_info(self, channel: str, item: Dict) -> str:
        """根据通道类型提取关键信息"""
        if channel in ["PLAYER_POSITION"]:
            pos = item.get("pos", {})
            return f"pos=({pos.get('x', '?'):.1f}, {pos.get('y', '?'):.1f})"

        elif channel == "PLAYER_STATS":
            return f"speed={item.get('speed', '?')}, damage={item.get('damage', '?')}, tears={item.get('tears', '?')}"

        elif channel == "PLAYER_HEALTH":
            return f"red={item.get('red_hearts', '?')}, soul={item.get('soul_hearts', '?')}, max={item.get('max_hearts', '?')}"

        elif channel == "PLAYER_INVENTORY":
            coins = item.get("coins", "?")
            bombs = item.get("bombs", "?")
            keys = item.get("keys", "?")
            count = item.get("collectible_count", 0)
            collectibles = item.get("collectibles", {})
            items_str = f"items={len(collectibles)}" if collectibles else "items=0"
            return (
                f"coins={coins}, bombs={bombs}, keys={keys}, {items_str}, total={count}"
            )

        elif channel == "ENEMIES":
            pos = item.get("pos", {})
            return f"type={item.get('type', '?')}, hp={item.get('hp', '?')}, pos=({pos.get('x', '?'):.1f}, {pos.get('y', '?'):.1f})"

        elif channel == "PROJECTILES":
            pos = item.get("pos", {})
            vel = item.get("vel", {})
            return f"type={item.get('type', '?')}, pos=({pos.get('x', '?'):.1f}, {pos.get('y', '?'):.1f})"

        elif channel == "PICKUPS":
            pos = item.get("pos", {})
            return f"variant={item.get('variant', '?')}, pos=({pos.get('x', '?'):.1f}, {pos.get('y', '?'):.1f})"

        elif channel == "ROOM_INFO":
            return f"type={item.get('type', '?')}, clear={item.get('is_clear', '?')}, enemies={item.get('enemy_count', '?')}"

        else:
            # 默认显示前几个键值对
            preview = ", ".join(f"{k}={v}" for k, v in list(item.items())[:4])
            return preview if preview else "(空)"

    def inspect_now(self) -> str:
        """立即获取一次快照并返回"""
        self._take_snapshot()
        return "Snapshot taken"


class DataReplayer:
    """数据回放器"""

    def __init__(self, recordings_dir: str = "./recordings"):
        self.recordings_dir = Path(recordings_dir)

    def list_sessions(self) -> List[Dict]:
        """列出所有记录会话"""
        sessions = []

        for meta_file in self.recordings_dir.glob("*_meta.json"):
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
                sessions.append(
                    {
                        "id": meta.get("id"),
                        "start_time": meta.get("start_timestamp"),
                        "duration": meta.get("duration", 0),
                        "frames": meta.get("total_frames", 0),
                        "events": meta.get("total_events", 0),
                    }
                )

        return sorted(sessions, key=lambda x: x["start_time"], reverse=True)

    def load_session(self, session_id: str) -> Dict:
        """加载会话数据"""
        # 加载元数据
        meta_file = self.recordings_dir / f"{session_id}_meta.json"
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        # 加载帧数据
        frames = []
        for chunk_file in sorted(
            self.recordings_dir.glob(f"{session_id}_chunk_*.json.gz")
        ):
            with gzip.open(chunk_file, "rt", encoding="utf-8") as f:
                chunk = json.load(f)
                frames.extend(chunk.get("frames", []))

        # 加载事件
        events_file = self.recordings_dir / f"{session_id}_events.json.gz"
        events = []
        if events_file.exists():
            with gzip.open(events_file, "rt", encoding="utf-8") as f:
                events_data = json.load(f)
                events = events_data.get("events", [])

        return {
            "meta": meta,
            "frames": frames,
            "events": events,
        }

    def iterate_frames(self, session_id: str):
        """迭代会话的帧数据（生成器，内存友好）"""
        for chunk_file in sorted(
            self.recordings_dir.glob(f"{session_id}_chunk_*.json.gz")
        ):
            with gzip.open(chunk_file, "rt", encoding="utf-8") as f:
                chunk = json.load(f)
                for frame in chunk.get("frames", []):
                    yield frame


def main():
    """主函数 - 启动数据记录器"""
    import argparse

    parser = argparse.ArgumentParser(description="Isaac Data Recorder & Inspector")
    parser.add_argument(
        "--mode",
        choices=["record", "inspect", "both"],
        default="both",
        help="运行模式: record=只记录, inspect=只检查, both=两者都运行",
    )
    parser.add_argument(
        "--interval", type=float, default=10.0, help="数据检查输出间隔（秒）"
    )
    parser.add_argument(
        "--log-file", type=str, default=None, help="数据快照输出文件路径"
    )
    parser.add_argument(
        "--output-dir", type=str, default="./recordings", help="录制数据输出目录"
    )

    args = parser.parse_args()

    bridge = IsaacBridge(host="127.0.0.1", port=9527)
    recorder = None
    inspector = None

    if args.mode in ["record", "both"]:
        recorder = GameDataRecorder(bridge, output_dir=args.output_dir)

    if args.mode in ["inspect", "both"]:
        log_file = (
            args.log_file
            or f"./logs/data_inspect_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        inspector = DataInspector(bridge, interval=args.interval, log_file=log_file)

    @bridge.on("connected")
    def on_connected(_):
        logger.info("Game connected")
        if inspector:
            inspector.start()

    @bridge.on("disconnected")
    def on_disconnected(_):
        if recorder:
            recorder.end_session(reason="disconnected")
        if inspector:
            inspector.stop()

    bridge.start()
    logger.info(f"Started in '{args.mode}' mode, waiting for game...")
    if inspector:
        logger.info(
            f"Data inspection interval: {args.interval}s, log file: {inspector.log_file}"
        )

    try:
        while True:
            time.sleep(5)
            if recorder and recorder.recording:
                stats = recorder.get_stats()
                logger.info(
                    f"Recording... Frames: {stats['frames_recorded']} | "
                    f"Events: {stats['events_recorded']} | "
                    f"Buffer: {stats['buffer_size']}"
                )
    except KeyboardInterrupt:
        logger.info("Stopping...")
        if recorder:
            recorder.end_session(reason="user_stop")
        if inspector:
            inspector.stop()
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
