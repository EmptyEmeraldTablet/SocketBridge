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

    def __init__(self, bridge: IsaacBridge, config: Optional[CollectorConfig] = None):
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
        self.recorded_corners_data: List[dict] = []

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

        # 获取玩家速度（用于判断是否静止）
        velocity = player_stats.get("vel", {})
        vel_x = velocity.get("x", 0) if velocity else 0
        vel_y = velocity.get("y", 0) if velocity else 0
        is_moving = abs(vel_x) > 0.1 or abs(vel_y) > 0.1

        # 更新位置历史
        self.position_history.append((pos_x, pos_y, is_moving))

        # 开始新的稳定性检查（无条件触发）
        if self.corner_stabilize_start_time is None:
            self.corner_stabilize_start_time = time.time()
            self._last_countdown_second = -1
            return

        elapsed = time.time() - self.corner_stabilize_start_time
        remaining = self.config.stability_duration - elapsed

        # 显示倒计时
        if remaining > 0:
            # 每秒更新一次倒计时
            if int(remaining) != self._last_countdown_second:
                self._last_countdown_second = int(remaining)
                move_status = "[MOVING]" if is_moving else "[STILL  ]"
                print(
                    f"\r[COUNTDOWN] Room {room_info.get('room_idx', -1)} | {remaining:5.1f}s | {move_status} | ({pos_x:.0f}, {pos_y:.0f})   ",
                    end="",
                    flush=True,
                )
            return

        # 时间到，检测位置稳定性
        self._last_countdown_second = -1

        # 计算位置方差（只统计静止帧）
        history_len = len(self.position_history)
        if history_len < 10:
            self.corner_stabilize_start_time = time.time()
            self.position_history.clear()
            return

        # 统计静止帧的比例
        still_frames = sum(1 for _, _, moving in self.position_history if not moving)
        move_ratio = 1.0 - (still_frames / history_len)

        # 如果移动超过30%，认为不稳定
        if move_ratio > 0.3:
            self.corner_stabilize_start_time = time.time()
            self.position_history.clear()
            return

        # 稳定性验证通过，记录坐标
        print(
            f"\n[RECORD] Room {room_info.get('room_idx', -1)} | ({pos_x:.0f}, {pos_y:.0f}) | still={still_frames}/{history_len} frames"
        )

        # 获取房间边界
        top_left = (
            room_info.get("top_left", {}).get("x", 0),
            room_info.get("top_left", {}).get("y", 0),
        )
        bottom_right = (
            room_info.get("bottom_right", {}).get("x", 0),
            room_info.get("bottom_right", {}).get("y", 0),
        )

        # 获取玩家碰撞箱大小
        player_size = player_stats.get("size", 15.0)

        # 记录位置
        self._record_corner(
            corner_name="detected_position",
            corner_pos=(pos_x, pos_y),
            player_pos=(pos_x, pos_y),
            player_size=player_size,
            top_left=top_left,
            bottom_right=bottom_right,
            room_idx=room_info.get("room_idx", -1),
            stability_duration=elapsed,
            position_variance=move_ratio,
        )

        # 重置状态，继续记录
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
        """记录位置数据"""
        # 创建位置数据
        position_data = {
            "recorded_name": corner_name,
            "position": player_pos,
            "room_top_left": top_left,
            "room_bottom_right": bottom_right,
            "player_size": player_size,
            "recorded_at": datetime.now().isoformat(),
            "frame": self.data.frame,
            "stability_duration": round(stability_duration, 2),
            "move_ratio": round(position_variance, 2),
        }

        # 保存到列表
        self.recorded_corners_data.append(position_data)

        # 更新统计
        self.stats["corners_recorded"] += 1

        if self.session:
            self.session.total_corners_recorded += 1

        # 重置状态，继续记录
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

        # 保存位置数据
        positions_file = self.output_dir / "recorded_positions.json"
        with open(positions_file, "w", encoding="utf-8") as f:
            json.dump(self.recorded_corners_data, f, indent=2, ensure_ascii=False)

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
        # 主循环
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        collector.stop()
        bridge.stop()


if __name__ == "__main__":
    main()
