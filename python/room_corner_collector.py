"""
房间角落自动采集器

功能：
1. 自动检测玩家是否靠近房间角落
2. 15秒位置稳定性验证
3. 自动记录房间角落坐标
4. 数据导出到JSON格式

使用方法：
1. 启动脚本
2. 在游戏中启用debug模式并飞行
3. 飞到房间角落处并停留15秒以上
4. 脚本会自动检测并记录角落坐标

注意事项：
- 确保游戏和Python脚本都已连接
- 角落检测阈值可配置（默认50像素）
- 稳定性验证时间可配置（默认15秒）
"""

import json
import time
import math
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from collections import deque
import logging
import threading

from isaac_bridge import IsaacBridge, GameDataAccessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("RoomCornerCollector")


# ============================================================================
# 配置参数
# ============================================================================


@dataclass
class CollectorConfig:
    """采集器配置"""

    # 角落检测阈值（像素）：玩家距离角落多少像素内认为是在角落
    corner_detection_threshold: float = 50.0

    # 稳定性验证时间（秒）：位置需要稳定多久才记录
    stability_duration: float = 5.0

    # 稳定性偏差阈值（像素）：5秒内位置偏差小于此值才认为稳定
    stability_threshold: float = 20.0

    # 位置历史记录帧数（用于稳定性计算）
    position_history_frames: int = 300  # 60fps * 5s = 300帧

    # 数据输出目录
    output_dir: str = "./room_data"


# 默认配置
DEFAULT_CONFIG = CollectorConfig()


# ============================================================================
# 数据结构
# ============================================================================


@dataclass
class CornerPosition:
    """角落位置数据"""

    corner_name: str  # 角落名称: top_left, top_right, bottom_left, bottom_right, extra
    player_position: Tuple[float, float]  # 玩家中心坐标
    room_top_left: Tuple[float, float]  # 房间左上角坐标
    room_bottom_right: Tuple[float, float]  # 房间右下角坐标
    theoretical_corner: Tuple[float, float]  # 理论角落坐标
    distance_to_corner: float  # 玩家到理论角落的距离
    player_size: float  # 玩家碰撞箱大小
    recorded_at: str  # 记录时间
    frame: int  # 帧号
    is_stable: bool  # 是否通过稳定性验证
    stability_duration: float  # 稳定性验证持续时间
    position_variance: float  # 位置方差


@dataclass
class RoomData:
    """房间数据"""

    room_index: int
    stage: int
    stage_type: int
    room_type: int
    room_shape: int

    # 房间几何信息
    grid_width: int
    grid_height: int
    top_left: Tuple[float, float]
    bottom_right: Tuple[float, float]

    # 角落数据
    auto_detected_corners: List[Dict] = field(default_factory=list)
    manual_verified_corners: List[Dict] = field(default_factory=list)

    # 元数据
    first_visited_at: str = ""
    last_updated_at: str = ""
    visit_count: int = 0
    notes: str = ""
    is_first_visit: bool = True  # 是否是首次访问


@dataclass
class CollectionSession:
    """采集会话"""

    session_id: str
    start_time: str
    config: Dict[str, Any] = field(default_factory=dict)
    rooms: Dict[str, RoomData] = field(default_factory=dict)
    total_corners_recorded: int = 0
    total_rooms_visited: int = 0


# ============================================================================
# 核心采集器
# ============================================================================


class RoomCornerCollector:
    """
    房间角落自动采集器

    工作流程：
    1. 监听 PLAYER_POSITION 和 ROOM_INFO 数据
    2. 根据 ROOM_INFO 计算房间的4个理论角落
    3. 检测玩家是否靠近某个角落
    4. 记录玩家位置历史，进行稳定性验证
    5. 稳定性验证通过后，自动记录该角落
    """

    def __init__(self, bridge: IsaacBridge, config: CollectorConfig = None):
        """
        初始化采集器

        Args:
            bridge: IsaacBridge 实例
            config: 采集器配置
        """
        self.bridge = bridge
        self.data = GameDataAccessor(bridge)
        self.config = config or DEFAULT_CONFIG

        # 输出目录
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 当前房间数据
        self.current_room: Optional[RoomData] = None
        self.current_room_idx: int = -1
        self.current_room_first_visit: bool = True

        # 角落检测状态
        self.position_history: deque = deque(maxlen=self.config.position_history_frames)
        self.current_corner: Optional[str] = None
        self.corner_stabilize_start_time: Optional[float] = None
        self._last_countdown_second: int = -1  # 用于倒计时显示
        self.recorded_corners: Set[Tuple[int, str]] = set()  # (room_idx, corner_name)

        # 已记录的角落数据
        self.recorded_corners_data: List[CornerPosition] = []

        # 统计信息
        self.stats = {
            "frames_processed": 0,
            "corners_recorded": 0,
            "rooms_visited": 0,
            "stability_checks": 0,
        }

        # 会话数据
        self.session: Optional[CollectionSession] = None

        # 线程控制
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # 设置事件处理器
        self._setup_handlers()

    def _setup_handlers(self):
        """设置事件处理器"""

        @self.bridge.on("message")
        def on_message(msg):
            """处理数据消息"""
            if not self._running:
                return

            # 获取 payload（可能是 DataMessage 对象或字典）
            payload = msg.payload if hasattr(msg, "payload") else msg.get("payload")
            if not payload:
                return

            # 检查是否有 PLAYER_POSITION
            if "PLAYER_POSITION" not in payload:
                return

            player_pos = payload["PLAYER_POSITION"]
            if not player_pos:
                return

            # 获取第一个玩家的位置（处理 list 和 dict 两种格式）
            player_data = None
            if isinstance(player_pos, list):
                if len(player_pos) > 0:
                    player_data = player_pos[0]
            elif isinstance(player_pos, dict):
                player_data = player_pos.get("1") or player_pos.get(1)

            if not player_data:
                return

            pos_x = (
                player_data.get("pos", {}).get("x", 0) if player_data.get("pos") else 0
            )
            pos_y = (
                player_data.get("pos", {}).get("y", 0) if player_data.get("pos") else 0
            )

            channels = (
                msg.channels if hasattr(msg, "channels") else msg.get("channels", [])
            )
            room_info = None
            if "ROOM_INFO" in channels and "ROOM_INFO" in payload:
                room_info = payload["ROOM_INFO"]
            else:
                room_info = self.data.get_room_info()

            if not room_info:
                return

            room_idx = room_info.get("room_idx", -1)
            is_first_visit = room_info.get("is_first_visit", True)
            top_left = (
                room_info.get("top_left", {}).get("x", 0),
                room_info.get("top_left", {}).get("y", 0),
            )
            bottom_right = (
                room_info.get("bottom_right", {}).get("x", 0),
                room_info.get("bottom_right", {}).get("y", 0),
            )

            # 检测房间变化
            if room_idx != self.current_room_idx:
                logger.info(
                    f"[ROOM] Entered room {room_idx} (first_visit={is_first_visit})"
                )
                self._on_room_change(room_idx, room_info)

            # 如果不是首次访问的房间，不进行采样
            if not self.current_room_first_visit:
                return

            # 处理角落检测
            self._process_position(
                pos_x=pos_x,
                pos_y=pos_y,
                room_info=room_info,
                player_stats=player_data,
            )

    def _on_room_change(self, room_idx: int, room_info: dict):
        """处理房间变化"""
        # 检查是否是首次访问，非首次访问不需要采样
        is_first_visit = room_info.get("is_first_visit", True)
        self.current_room_first_visit = is_first_visit

        # 重置角落检测状态
        self.current_corner = None
        self.corner_stabilize_start_time = None
        self.position_history.clear()

        # 创建新的房间数据
        self.current_room = RoomData(
            room_index=room_idx,
            stage=room_info.get("stage", 0),
            stage_type=room_info.get("stage_type", 0),
            room_type=room_info.get("room_type", 0),
            room_shape=room_info.get("room_shape", 0),
            grid_width=room_info.get("grid_width", 0),
            grid_height=room_info.get("grid_height", 0),
            top_left=(
                room_info.get("top_left", {}).get("x", 0),
                room_info.get("top_left", {}).get("y", 0),
            ),
            bottom_right=(
                room_info.get("bottom_right", {}).get("x", 0),
                room_info.get("bottom_right", {}).get("y", 0),
            ),
            first_visited_at=datetime.now().isoformat(),
            last_updated_at=datetime.now().isoformat(),
            visit_count=1,
            is_first_visit=is_first_visit,
        )

        # 更新当前房间索引
        self.current_room_idx = room_idx

        # 更新统计
        self.stats["rooms_visited"] += 1

        # 初始化会话
        if self.session is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.session = CollectionSession(
                session_id=f"room_corner_session_{timestamp}",
                start_time=datetime.now().isoformat(),
                config=asdict(self.config),
            )

        # 添加到会话
        if str(room_idx) not in self.session.rooms:
            self.session.rooms[str(room_idx)] = self.current_room
            self.session.total_rooms_visited += 1

    def _process_position(
        self,
        pos_x: float,
        pos_y: float,
        room_info: dict,
        player_stats: dict,
    ):
        """处理玩家位置"""
        self.stats["frames_processed"] += 1

        # 获取房间边界
        top_left = (
            room_info.get("top_left", {}).get("x", 0),
            room_info.get("top_left", {}).get("y", 0),
        )
        bottom_right = (
            room_info.get("bottom_right", {}).get("x", 0),
            room_info.get("bottom_right", {}).get("y", 0),
        )

        # 计算4个理论角落
        corners = {
            "top_left": top_left,
            "top_right": (bottom_right[0], top_left[1]),
            "bottom_left": (top_left[0], bottom_right[1]),
            "bottom_right": bottom_right,
        }

        # 获取玩家碰撞箱大小
        player_size = player_stats.get("size", 15.0)

        # 检测玩家靠近哪个角落
        nearest_corner, distance = self._find_nearest_corner(pos_x, pos_y, corners)

        # 更新位置历史
        self.position_history.append((pos_x, pos_y))

        # 如果靠近角落，开始稳定性验证
        if nearest_corner and distance <= self.config.corner_detection_threshold:
            self._check_corner_stability(
                corner_name=nearest_corner,
                corner_pos=corners[nearest_corner],
                player_pos=(pos_x, pos_y),
                player_size=player_size,
                top_left=top_left,
                bottom_right=bottom_right,
                room_idx=room_info.get("room_idx", -1),
            )
        else:
            # 重置角落检测状态
            self.current_corner = None
            self.corner_stabilize_start_time = None

    def _find_nearest_corner(
        self, pos_x: float, pos_y: float, corners: Dict[str, Tuple[float, float]]
    ) -> Tuple[Optional[str], float]:
        """找到最近的角落"""
        min_distance = float("inf")
        nearest = None

        for name, (cx, cy) in corners.items():
            distance = math.sqrt((pos_x - cx) ** 2 + (pos_y - cy) ** 2)
            if distance < min_distance:
                min_distance = distance
                nearest = name

        return nearest, min_distance

    def _check_corner_stability(
        self,
        corner_name: str,
        corner_pos: Tuple[float, float],
        player_pos: Tuple[float, float],
        player_size: float,
        top_left: Tuple[float, float],
        bottom_right: Tuple[float, float],
        room_idx: int,
    ):
        """检查角落位置稳定性"""

        # 如果是新的角落，重置计时器并开始追踪
        if self.current_corner != corner_name:
            self.current_corner = corner_name
            self.corner_stabilize_start_time = time.time()
            self._last_countdown_second = -1
            print(
                f"\n[START] Room {room_idx} tracking '{corner_name}' at ({player_pos[0]:.0f}, {player_pos[1]:.0f})"
            )
            return

        # 检查是否已经稳定足够时间
        if self.corner_stabilize_start_time is None:
            return

        elapsed = time.time() - self.corner_stabilize_start_time
        remaining = self.config.stability_duration - elapsed

        # 显示倒计时
        if remaining > 0:
            # 每秒更新一次倒计时
            if int(remaining) != self._last_countdown_second:
                self._last_countdown_second = int(remaining)
                print(
                    f"\r[COUNTDOWN] Room {room_idx} | {remaining:5.1f}s | {corner_name:12} ",
                    end="",
                    flush=True,
                )
            return

        # 时间到，检测位置稳定性
        self._last_countdown_second = -1

        # 计算位置方差
        variance = self._calculate_position_variance()

        if variance > self.config.stability_threshold:
            # 位置不稳定，继续计时
            print(
                f"\r[WAIT] Position unstable (variance={variance:.1f}), continuing...    "
            )
            self.corner_stabilize_start_time = time.time()
            self.position_history.clear()
            return

        # 稳定性验证通过，记录坐标（不检查是否已记录，允许重复记录）
        print(
            f"\n[RECORD] Room {room_idx} | {corner_name} | ({player_pos[0]:.0f}, {player_pos[1]:.0f}) | variance={variance:.1f}"
        )

        # 记录角落
        self._record_corner(
            corner_name=corner_name,
            corner_pos=corner_pos,
            player_pos=player_pos,
            player_size=player_size,
            top_left=top_left,
            bottom_right=bottom_right,
            room_idx=room_idx,
            stability_duration=elapsed,
            position_variance=variance,
        )

        # 重置状态，继续记录其他位置
        self.corner_stabilize_start_time = time.time()
        self.position_history.clear()

    def _calculate_position_variance(self) -> float:
        """计算位置方差"""
        history_len = len(self.position_history)
        if history_len < 10:
            return float("inf")

        # 计算平均位置
        avg_x = sum(p[0] for p in self.position_history) / history_len
        avg_y = sum(p[1] for p in self.position_history) / history_len

        # 计算方差
        variance = (
            sum(
                (px - avg_x) ** 2 + (py - avg_y) ** 2
                for px, py in self.position_history
            )
            / history_len
        )

        return math.sqrt(variance)

    def _record_corner(
        self,
        corner_name: str,
        corner_pos: Tuple[float, float],
        player_pos: Tuple[float, float],
        player_size: float,
        top_left: Tuple[float, float],
        bottom_right: Tuple[float, float],
        room_idx: int,
        stability_duration: float,
        position_variance: float,
    ):
        """记录角落数据"""
        # 计算到理论角落的距离
        distance_to_corner = math.sqrt(
            (player_pos[0] - corner_pos[0]) ** 2 + (player_pos[1] - corner_pos[1]) ** 2
        )

        logger.info(
            f"[RECORD] Room {room_idx}, '{corner_name}': player=({player_pos[0]:.0f},{player_pos[1]:.0f}), "
            f"corner=({corner_pos[0]:.0f},{corner_pos[1]:.0f}), distance={distance_to_corner:.1f}"
        )

        # 创建角落位置数据
        corner_data = CornerPosition(
            corner_name=corner_name,
            player_position=player_pos,
            room_top_left=top_left,
            room_bottom_right=bottom_right,
            theoretical_corner=corner_pos,
            distance_to_corner=distance_to_corner,
            player_size=player_size,
            recorded_at=datetime.now().isoformat(),
            frame=self.data.frame,
            is_stable=True,
            stability_duration=stability_duration,
            position_variance=position_variance,
        )

        # 保存到列表
        self.recorded_corners_data.append(corner_data)

        # 更新记录集合
        self.record_key = (room_idx, corner_name)
        self.recorded_corners.add(self.record_key)

        # 更新房间数据
        if self.current_room:
            self.current_room.auto_detected_corners.append(
                {
                    "corner_name": corner_name,
                    "player_position": player_pos,
                    "theoretical_corner": corner_pos,
                    "distance_to_corner": round(distance_to_corner, 2),
                    "player_size": player_size,
                    "recorded_at": corner_data.recorded_at,
                    "frame": corner_data.frame,
                    "is_stable": True,
                    "stability_duration": round(stability_duration, 2),
                    "position_variance": round(position_variance, 2),
                }
            )
            self.current_room.last_updated_at = datetime.now().isoformat()

        # 更新统计
        self.stats["corners_recorded"] += 1
        self.stats["stability_checks"] += 1

        if self.session:
            self.session.total_corners_recorded += 1

        # 重置状态，避免重复记录
        self.current_corner = None
        self.corner_stabilize_start_time = None

    def start(self):
        """启动采集器"""
        if self._running:
            logger.warning("Collector already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._save_loop, daemon=True)
        self._thread.start()

        logger.info(
            f"RoomCornerCollector started (threshold={self.config.corner_detection_threshold}px, "
            f"stability={self.config.stability_duration}s)"
        )

    def stop(self):
        """停止采集器并保存数据"""
        if not self._running:
            return

        self._running = False

        # 等待保存线程
        if self._thread:
            self._thread.join(timeout=2.0)

        # 保存数据
        self._save_data()

        logger.info(
            f"RoomCornerCollector stopped. "
            f"Corners recorded: {self.stats['corners_recorded']}, "
            f"Rooms visited: {self.stats['rooms_visited']}"
        )

    def _save_loop(self):
        """定期保存数据的线程"""
        while self._running:
            time.sleep(30)  # 每30秒保存一次
            if self._running:
                self._save_data()

    def _save_data(self):
        """保存采集的数据"""
        if not self.recorded_corners_data and not self.session:
            return

        # 保存角落数据
        corners_file = self.output_dir / "recorded_corners.json"
        corners_data = [
            {
                "corner_name": c.corner_name,
                "room_index": self.current_room_idx if self.current_room else -1,
                "player_position": list(c.player_position),
                "room_top_left": list(c.room_top_left),
                "room_bottom_right": list(c.room_bottom_right),
                "theoretical_corner": list(c.theoretical_corner),
                "distance_to_corner": round(c.distance_to_corner, 2),
                "player_size": c.player_size,
                "recorded_at": c.recorded_at,
                "frame": c.frame,
                "is_stable": c.is_stable,
                "stability_duration": round(c.stability_duration, 2),
                "position_variance": round(c.position_variance, 2),
            }
            for c in self.recorded_corners_data
        ]

        with open(corners_file, "w", encoding="utf-8") as f:
            json.dump(corners_data, f, indent=2, ensure_ascii=False)

        # 保存房间数据
        if self.session:
            rooms_file = self.output_dir / "rooms.json"
            rooms_data = {}
            for room_idx, room in self.session.rooms.items():
                rooms_data[room_idx] = {
                    "room_index": room.room_index,
                    "stage": room.stage,
                    "stage_type": room.stage_type,
                    "room_type": room.room_type,
                    "room_shape": room.room_shape,
                    "grid_width": room.grid_width,
                    "grid_height": room.grid_height,
                    "top_left": list(room.top_left),
                    "bottom_right": list(room.bottom_right),
                    "auto_detected_corners": room.auto_detected_corners,
                    "manual_verified_corners": room.manual_verified_corners,
                    "is_first_visit": room.is_first_visit,
                    "first_visited_at": room.first_visited_at,
                    "last_updated_at": room.last_updated_at,
                    "visit_count": room.visit_count,
                    "notes": room.notes,
                }

            with open(rooms_file, "w", encoding="utf-8") as f:
                json.dump(rooms_data, f, indent=2, ensure_ascii=False)

        # 保存会话数据
        if self.session:
            session_file = self.output_dir / f"{self.session.session_id}.json"
            session_data = {
                "session_id": self.session.session_id,
                "start_time": self.session.start_time,
                "config": self.session.config,
                "rooms": list(self.session.rooms.keys()),
                "total_corners_recorded": self.session.total_corners_recorded,
                "total_rooms_visited": self.session.total_rooms_visited,
            }

            with open(session_file, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)

        logger.debug(f"Data saved to {self.output_dir}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "running": self._running,
            "current_room": self.current_room_idx,
            "recorded_corners_count": len(self.recorded_corners_data),
            "pending_corners": len({k[1] for k in self.recorded_corners} - set()),
        }

    def get_room_summary(self) -> Dict[str, Any]:
        """获取当前房间摘要"""
        if not self.current_room:
            return {}

        return {
            "room_index": self.current_room.room_index,
            "stage": self.current_room.stage,
            "grid_size": f"{self.current_room.grid_width}x{self.current_room.grid_height}",
            "bounds": f"({self.current_room.top_left[0]:.0f}, {self.current_room.top_left[1]:.0f}) "
            f"- ({self.current_room.bottom_right[0]:.0f}, {self.current_room.bottom_right[1]:.0f})",
            "corners_recorded": len(self.current_room.auto_detected_corners),
        }


# ============================================================================
# 主函数
# ============================================================================


def main():
    """主函数 - 启动房间角落采集器"""
    import argparse

    parser = argparse.ArgumentParser(description="Room Corner Collector")
    parser.add_argument(
        "--threshold",
        type=float,
        default=50.0,
        help="Corner detection threshold in pixels (default: 50)",
    )
    parser.add_argument(
        "--stability",
        type=float,
        default=5.0,
        help="Stability verification duration in seconds (default: 5)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./room_data",
        help="Output directory for collected data (default: ./room_data)",
    )

    args = parser.parse_args()

    # 创建配置
    config = CollectorConfig(
        corner_detection_threshold=args.threshold,
        stability_duration=args.stability,
        output_dir=args.output_dir,
    )

    # 创建桥接器
    bridge = IsaacBridge()

    # 创建采集器
    collector = RoomCornerCollector(bridge, config)

    # 注册事件
    @bridge.on("connected")
    def on_connected(info):
        logger.info(f"Game connected: {info['address']}")

    @bridge.on("disconnected")
    def on_disconnected(_):
        logger.info("Game disconnected")

    # 启动
    bridge.start()
    collector.start()

    try:
        # 主循环：定期输出状态
        last_stats_time = time.time()
        while True:
            time.sleep(1)

            # 每10秒输出一次状态
            if time.time() - last_stats_time >= 10:
                stats = collector.get_stats()
                summary = collector.get_room_summary()

                logger.info(
                    f"Stats: corners={stats['corners_recorded']}, "
                    f"rooms={stats['rooms_visited']}, "
                    f"frames={stats['frames_processed']}"
                )

                if summary:
                    logger.info(
                        f"Current room: {summary['room_index']}, "
                        f"stage={summary['stage']}, "
                        f"size={summary['grid_size']}, "
                        f"corners={summary['corners_recorded']}"
                    )

                last_stats_time = time.time()

    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        collector.stop()
        bridge.stop()

    logger.info("Done!")


if __name__ == "__main__":
    main()
