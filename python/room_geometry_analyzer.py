"""
房间几何分析器 v2.0

根据玩家坐标采样数据推断房间的真实空间属性：
- 墙壁位置和边界
- 房间形状（矩形、L型等）
- 门的位置
- 可行走区域

核心改进 v2.0：
- 通过时间戳匹配采样点到房间（解决多个房间共享边界的问题）
- 独立推断每个房间的真实边界
- 支持特殊形状房间识别

使用方法:
    python room_geometry_analyzer.py [--input-dir ./room_data] [--output-dir ./analyzed_rooms]
"""

import json
import math
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("RoomGeometryAnalyzer")


@dataclass
class WallSegment:
    """墙壁线段"""

    x1: float
    y1: float
    x2: float
    y2: float
    side: str  # "left", "right", "top", "bottom"
    confidence: float = 1.0
    samples: List[dict] = field(default_factory=list)


@dataclass
class RoomGeometry:
    """房间几何信息"""

    room_index: int
    stage: int
    room_type: int

    # 推断的墙壁边界
    min_x: float
    max_x: float
    min_y: float
    max_y: float

    # 墙壁线段
    walls: List[WallSegment] = field(default_factory=list)

    # 门的位置（推断）
    doors: List[Dict] = field(default_factory=list)

    # 房间形状
    shape: str = "unknown"  # "rectangle", "L_shape", "complex"
    shape_confidence: float = 0.0

    # 采样点统计
    sample_count: int = 0
    move_ratio_avg: float = 0.0

    # 原始数据引用
    raw_samples: List[dict] = field(default_factory=list)

    # 时间信息
    first_visited_at: str = ""
    room_shape_code: int = 0  # 游戏报告的房间形状代码


class RoomGeometryAnalyzer:
    """
    房间几何分析器 v2.0

    通过时间戳匹配采样点到房间，推断真实几何
    """

    # 以撒的游戏中标准网格大小
    GRID_SIZE = 40

    # 玩家碰撞箱偏移容差
    OFFSET_TOLERANCE = 5.0

    def __init__(
        self, input_dir: str = "./room_data", output_dir: str = "./analyzed_rooms"
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.positions: List[dict] = []
        self.rooms: Dict[str, dict] = {}
        self.analyzed_rooms: Dict[int, RoomGeometry] = {}

        # 时间范围映射: room_index -> (start_time, end_time)
        self._room_time_ranges: Dict[int, Tuple[datetime, Optional[datetime]]] = {}

    def load_data(self) -> bool:
        """加载收集的数据"""
        positions_file = self.input_dir / "recorded_positions.json"
        rooms_file = self.input_dir / "rooms.json"

        if not positions_file.exists():
            logger.error(f"Positions file not found: {positions_file}")
            return False

        logger.info(f"Loading data from {self.input_dir}...")

        with open(positions_file, "r", encoding="utf-8") as f:
            self.positions = json.load(f)

        if rooms_file.exists():
            with open(rooms_file, "r", encoding="utf-8") as f:
                self.rooms = json.load(f)

        logger.info(
            f"Loaded {len(self.positions)} position samples from {len(self.rooms)} rooms"
        )

        # 构建房间时间范围映射
        self._build_room_time_ranges()

        return True

    def _build_room_time_ranges(self):
        """
        构建房间时间范围映射

        逻辑：
        - 房间的 start_time = first_visited_at
        - 房间的 end_time = 下一个房间的 first_visited_at（如果有）
        - 最后一个房间没有 end_time（使用 None）
        """
        # 按时间排序房间
        sorted_rooms = sorted(
            self.rooms.items(),
            key=lambda x: x[1].get("first_visited_at", ""),
        )

        room_indices = [int(idx) for idx, _ in sorted_rooms]

        for i, (idx, room_data) in enumerate(sorted_rooms):
            room_idx = int(idx)
            start_time_str = room_data.get("first_visited_at", "")

            try:
                start_time = datetime.fromisoformat(start_time_str)
            except ValueError:
                logger.warning(f"Invalid timestamp for room {idx}: {start_time_str}")
                continue

            # 确定结束时间（下一个房间的开始时间）
            if i + 1 < len(sorted_rooms):
                next_room_data = sorted_rooms[i + 1][1]
                next_time_str = next_room_data.get("first_visited_at", "")
                try:
                    end_time = datetime.fromisoformat(next_time_str)
                except ValueError:
                    end_time = None
            else:
                end_time = None  # 最后一个房间

            self._room_time_ranges[room_idx] = (start_time, end_time)
            logger.debug(
                f"Room {room_idx}: {start_time} -> {end_time or 'end of session'}"
            )

        logger.info(f"Built time ranges for {len(self._room_time_ranges)} rooms")

    def _parse_timestamp(self, time_str: str) -> Optional[datetime]:
        """解析 ISO 格式时间戳"""
        try:
            return datetime.fromisoformat(time_str)
        except ValueError:
            return None

    def match_sample_to_room(self, sample: dict) -> Optional[int]:
        """
        通过时间戳将采样点匹配到房间

        逻辑：
        1. 解析采样点的 recorded_at 时间
        2. 遍历所有房间时间范围
        3. 找到采样时间落在范围内的房间
        4. 返回该房间的索引
        """
        recorded_at_str = sample.get("recorded_at", "")
        sample_time = self._parse_timestamp(recorded_at_str)

        if not sample_time:
            logger.warning(f"Cannot parse timestamp: {recorded_at_str}")
            return None

        for room_idx, (start_time, end_time) in self._room_time_ranges.items():
            if sample_time >= start_time:
                if end_time is None or sample_time < end_time:
                    return room_idx

        return None

    def analyze_all(self) -> Dict[int, "RoomGeometry"]:
        """分析所有房间"""
        # 通过时间戳匹配采样点到房间
        samples_by_room: Dict[int, List[dict]] = defaultdict(list)
        unmatched_count = 0

        for sample in self.positions:
            room_idx = self.match_sample_to_room(sample)
            if room_idx is not None:
                samples_by_room[room_idx].append(sample)
            else:
                unmatched_count += 1

        logger.info(f"Matched samples to {len(samples_by_room)} rooms")
        if unmatched_count > 0:
            logger.warning(f"Unmatched samples: {unmatched_count}")

        # 分析每个房间
        for room_idx, samples in samples_by_room.items():
            room_data = self.rooms.get(str(room_idx), {})
            geometry = self.analyze_room(room_idx, samples, room_data)
            self.analyzed_rooms[room_idx] = geometry

            # 获取房间形状代码用于显示
            room_shape = room_data.get("room_shape", 0)
            stage = room_data.get("stage", 0)
            room_type = room_data.get("room_type", 0)

            logger.info(
                f"Room {room_idx} (shape={room_shape}, stage={stage}): "
                f"shape={geometry.shape}, "
                f"bounds=({geometry.min_x:.0f},{geometry.min_y:.0f})-"
                f"({geometry.max_x:.0f},{geometry.max_y:.0f}), "
                f"samples={len(samples)}"
            )

        return self.analyzed_rooms

    def analyze_room(
        self, room_idx: int, samples: List[dict], room_data: dict
    ) -> RoomGeometry:
        """分析单个房间的几何"""

        # 提取玩家位置（考虑碰撞箱偏移）
        player_positions = []
        for sample in samples:
            pos = sample.get("position", [])
            player_size = sample.get("player_size", 15.0)
            room_tl = sample.get("room_top_left", [])
            room_br = sample.get("room_bottom_right", [])

            if pos and len(pos) >= 2:
                # 推断墙壁位置（玩家位置 + 碰撞箱半径）
                wall_pos = self._infer_wall_position(
                    pos[0],
                    pos[1],
                    room_tl[0] if room_tl else 0,
                    room_tl[1] if room_tl else 0,
                    room_br[0] if room_br else 0,
                    room_br[1] if room_br else 0,
                    player_size,
                )
                player_positions.append(
                    {
                        "player_x": pos[0],
                        "player_y": pos[1],
                        "inferred_x": wall_pos[0],
                        "inferred_y": wall_pos[1],
                        "side": wall_pos[2],
                        "sample": sample,
                    }
                )

        # 计算墙壁边界
        left_walls = [p for p in player_positions if p["side"] == "left"]
        right_walls = [p for p in player_positions if p["side"] == "right"]
        top_walls = [p for p in player_positions if p["side"] == "top"]
        bottom_walls = [p for p in player_positions if p["side"] == "bottom"]

        # 推断墙壁位置（使用聚类）
        min_x = (
            self._cluster_coordinate([p["inferred_x"] for p in left_walls])
            if left_walls
            else None
        )
        max_x = (
            self._cluster_coordinate([p["inferred_x"] for p in right_walls])
            if right_walls
            else None
        )
        min_y = (
            self._cluster_coordinate([p["inferred_y"] for p in top_walls])
            if top_walls
            else None
        )
        max_y = (
            self._cluster_coordinate([p["inferred_y"] for p in bottom_walls])
            if bottom_walls
            else None
        )

        # 如果无法从采样点推断，使用游戏报告的边界（仅作为后备）
        fallback_used = False
        if room_data:
            game_tl = room_data.get("top_left", [])
            game_br = room_data.get("bottom_right", [])

            if min_x is None:
                min_x = game_tl[0] if game_tl else 0
                fallback_used = True
            if max_x is None:
                max_x = game_br[0] if game_br else 0
                fallback_used = True
            if min_y is None:
                min_y = game_tl[1] if game_tl else 0
                fallback_used = True
            if max_y is None:
                max_y = game_br[1] if game_br else 0
                fallback_used = True

        if fallback_used:
            logger.debug(f"Room {room_idx}: Used fallback bounds from game data")

        # 创建墙壁线段
        walls = []
        if min_x is not None:
            walls.append(
                WallSegment(
                    x1=min_x,
                    y1=min_y or 0,
                    x2=min_x,
                    y2=max_y or 0,
                    side="left",
                    confidence=self._calculate_confidence(left_walls),
                    samples=left_walls,
                )
            )
        if max_x is not None:
            walls.append(
                WallSegment(
                    x1=max_x,
                    y1=min_y or 0,
                    x2=max_x,
                    y2=max_y or 0,
                    side="right",
                    confidence=self._calculate_confidence(right_walls),
                    samples=right_walls,
                )
            )
        if min_y is not None:
            walls.append(
                WallSegment(
                    x1=min_x or 0,
                    y1=min_y,
                    x2=max_x or 0,
                    y2=min_y,
                    side="top",
                    confidence=self._calculate_confidence(top_walls),
                    samples=top_walls,
                )
            )
        if max_y is not None:
            walls.append(
                WallSegment(
                    x1=min_x or 0,
                    y1=max_y,
                    x2=max_x or 0,
                    y2=max_y,
                    side="bottom",
                    confidence=self._calculate_confidence(bottom_walls),
                    samples=bottom_walls,
                )
            )

        # 识别房间形状（结合采样点分布和游戏报告的形状代码）
        room_shape_code = room_data.get("room_shape", 0)
        shape, shape_confidence = self._detect_room_shape(
            player_positions, min_x, max_x, min_y, max_y, room_data, room_shape_code
        )

        # 计算平均移动比例
        move_ratios = [s.get("move_ratio", 0) for s in samples]
        avg_move_ratio = sum(move_ratios) / len(move_ratios) if move_ratios else 0

        return RoomGeometry(
            room_index=room_idx,
            stage=room_data.get("stage", 0),
            room_type=room_data.get("room_type", 0),
            min_x=min_x or 0,
            max_x=max_x or 0,
            min_y=min_y or 0,
            max_y=max_y or 0,
            walls=walls,
            shape=shape,
            shape_confidence=shape_confidence,
            sample_count=len(samples),
            move_ratio_avg=avg_move_ratio,
            raw_samples=samples,
            first_visited_at=room_data.get("first_visited_at", ""),
            room_shape_code=room_shape_code,
        )

    def _infer_wall_position(
        self,
        player_x: float,
        player_y: float,
        room_x1: float,
        room_y1: float,
        room_x2: float,
        room_y2: float,
        player_size: float,
    ) -> Tuple[float, float, str]:
        """
        根据玩家位置推断墙壁位置

        返回: (墙壁x/y坐标, 墙壁方向)
        """
        # 计算玩家到各墙壁的距离
        dist_left = player_x - room_x1
        dist_right = room_x2 - player_x
        dist_top = player_y - room_y1
        dist_bottom = room_y2 - player_y

        min_dist = min(dist_left, dist_right, dist_top, dist_bottom)

        if min_dist == dist_left:
            # 玩家在左墙附近
            return (room_x1 + player_size, player_y, "left")
        elif min_dist == dist_right:
            # 玩家在右墙附近
            return (room_x2 - player_size, player_y, "right")
        elif min_dist == dist_top:
            # 玩家在上墙附近
            return (player_x, room_y1 + player_size, "top")
        else:
            # 玩家在下墙附近
            return (player_x, room_y2 - player_size, "bottom")

    def _cluster_coordinate(
        self, values: List[float], tolerance: float = 10.0
    ) -> Optional[float]:
        """
        对坐标值进行聚类，返回最可能的值

        使用简单的直方图聚类
        """
        if not values:
            return None

        if len(values) == 1:
            return values[0]

        # 排序
        sorted_values = sorted(values)

        # 找到最密集的聚类
        best_cluster = None
        best_density = 0

        for i, v in enumerate(sorted_values):
            cluster_values = [v]
            for j in range(i + 1, len(sorted_values)):
                if sorted_values[j] - cluster_values[-1] <= tolerance:
                    cluster_values.append(sorted_values[j])
                else:
                    break

            if len(cluster_values) > len(sorted_values) * 0.3:  # 至少30%的点
                density = len(cluster_values) / tolerance
                if density > best_density:
                    best_density = density
                    best_cluster = cluster_values

        if best_cluster:
            return sum(best_cluster) / len(best_cluster)

        return sorted_values[len(sorted_values) // 2]

    def _calculate_confidence(self, samples: List[dict]) -> float:
        """计算墙壁检测置信度"""
        if not samples:
            return 0.0

        if len(samples) == 1:
            return 0.5

        # 计算坐标方差
        x_coords = [s["inferred_x"] for s in samples]
        y_coords = [s["inferred_y"] for s in samples]

        x_var = self._variance(x_coords)
        y_var = self._variance(y_coords)

        # 方差越小，置信度越高
        max_var = 100.0  # 最大允许方差
        confidence = max(0.0, 1.0 - (x_var + y_var) / (2 * max_var))

        return confidence

    def _variance(self, values: List[float]) -> float:
        """计算方差"""
        if len(values) < 2:
            return 0.0
        avg = sum(values) / len(values)
        return sum((v - avg) ** 2 for v in values) / len(values)

    def _detect_room_shape(
        self,
        positions: List[dict],
        min_x: Optional[float],
        max_x: Optional[float],
        min_y: Optional[float],
        max_y: Optional[float],
        room_data: dict,
        room_shape_code: int,
    ) -> Tuple[str, float]:
        """
        检测房间形状

        以撒的房间只有两种形状：
        1. rectangle - 标准矩形
        2. L_shape - 向内折角的L形（某个角落被遮挡）

        通过采样点分布判断哪个角落缺失
        """
        if (
            not positions
            or min_x is None
            or max_x is None
            or min_y is None
            or max_y is None
        ):
            return "unknown", 0.0

        # 统计各墙壁的采样点数量
        left_count = len([p for p in positions if p["side"] == "left"])
        right_count = len([p for p in positions if p["side"] == "right"])
        top_count = len([p for p in positions if p["side"] == "top"])
        bottom_count = len([p for p in positions if p["side"] == "bottom"])

        total_samples = len(positions)

        # 判断各面是否有有效采样（>10%）
        has_left = left_count / total_samples >= 0.1
        has_right = right_count / total_samples >= 0.1
        has_top = top_count / total_samples >= 0.1
        has_bottom = bottom_count / total_samples >= 0.1

        missing_sides = []
        if not has_left:
            missing_sides.append("left")
        if not has_right:
            missing_sides.append("right")
        if not has_top:
            missing_sides.append("top")
        if not has_bottom:
            missing_sides.append("bottom")

        # 四面都有采样 → 矩形
        if len(missing_sides) == 0:
            return "rectangle", 0.95

        # 缺少一面 → L形（向内折角）
        if len(missing_sides) == 1:
            return "L_shape", 0.85

        # 缺少多面 → L形（可能有多个折角）
        if len(missing_sides) <= 3:
            return "L_shape", 0.7

        return "unknown", 0.3

    def _get_l_shape_corner(
        self,
        min_x: float,
        max_x: float,
        min_y: float,
        max_y: float,
        raw_samples: List[dict],
    ) -> str:
        """
        判断L形房间缺失的是哪个角落

        通过分析原始采样点，判断哪些墙壁方向没有采样，从而推断缺失的角落
        """
        # 从原始采样点推断墙壁方向
        player_positions = []
        for sample in raw_samples:
            pos = sample.get("position", [])
            player_size = sample.get("player_size", 15.0)
            room_tl = sample.get("room_top_left", [])
            room_br = sample.get("room_bottom_right", [])

            if pos and len(pos) >= 2 and room_tl and room_br:
                wall_pos = self._infer_wall_position(
                    pos[0],
                    pos[1],
                    room_tl[0],
                    room_tl[1],
                    room_br[0],
                    room_br[1],
                    player_size,
                )
                player_positions.append(
                    {
                        "player_x": pos[0],
                        "player_y": pos[1],
                        "inferred_x": wall_pos[0],
                        "inferred_y": wall_pos[1],
                        "side": wall_pos[2],
                    }
                )

        if not player_positions:
            return "unknown"

        left_count = len([p for p in player_positions if p["side"] == "left"])
        right_count = len([p for p in player_positions if p["side"] == "right"])
        top_count = len([p for p in player_positions if p["side"] == "top"])
        bottom_count = len([p for p in player_positions if p["side"] == "bottom"])

        total = left_count + right_count + top_count + bottom_count
        if total == 0:
            return "unknown"

        # 哪个方向的采样最少，对应的角落就可能缺失
        min_side = min(left_count, right_count, top_count, bottom_count)

        if min_side == left_count and min_side == top_count:
            return "top_left"
        elif min_side == right_count and min_side == top_count:
            return "top_right"
        elif min_side == left_count and min_side == bottom_count:
            return "bottom_left"
        elif min_side == right_count and min_side == bottom_count:
            return "bottom_right"

        # 如果只有一个方向缺失
        if min_side == left_count:
            return "left_side"
        elif min_side == right_count:
            return "right_side"
        elif min_side == top_count:
            return "top_side"
        else:
            return "bottom_side"

    def export_results(self) -> Path:
        """导出分析结果"""
        output_file = self.output_dir / "analyzed_rooms.json"

        results = {}
        for room_idx, geometry in self.analyzed_rooms.items():
            results[room_idx] = {
                "room_index": geometry.room_index,
                "stage": geometry.stage,
                "room_type": geometry.room_type,
                "room_shape_code": geometry.room_shape_code,
                "bounds": {
                    "min_x": round(geometry.min_x, 2),
                    "max_x": round(geometry.max_x, 2),
                    "min_y": round(geometry.min_y, 2),
                    "max_y": round(geometry.max_y, 2),
                },
                "dimensions": {
                    "width": round(geometry.max_x - geometry.min_x, 2),
                    "height": round(geometry.max_y - geometry.min_y, 2),
                },
                "walls": [
                    {
                        "side": w.side,
                        "x1": round(w.x1, 2),
                        "y1": round(w.y1, 2),
                        "x2": round(w.x2, 2),
                        "y2": round(w.y2, 2),
                        "confidence": round(w.confidence, 2),
                    }
                    for w in geometry.walls
                ],
                "shape": geometry.shape,
                "shape_confidence": round(geometry.shape_confidence, 2),
                "sample_count": geometry.sample_count,
                "move_ratio_avg": round(geometry.move_ratio_avg, 2),
                "first_visited_at": geometry.first_visited_at,
            }

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        logger.info(f"Results exported to {output_file}")

        return output_file

    def generate_report(self) -> str:
        """生成分析报告"""
        lines = [
            "=" * 60,
            "Room Geometry Analysis Report v2.0",
            "=" * 60,
            f"Generated: {datetime.now().isoformat()}",
            f"Input: {self.input_dir}",
            f"Rooms analyzed: {len(self.analyzed_rooms)}",
            "",
            "Analysis Method: Time-based sample matching",
            "Improvement: Correctly matches samples to rooms even when",
            "              multiple rooms share the same boundary coordinates",
            "",
        ]

        for room_idx, geometry in sorted(self.analyzed_rooms.items()):
            lines.append("-" * 60)
            lines.append(f"Room {room_idx}")
            lines.append("-" * 60)
            lines.append(f"  Stage: {geometry.stage}, Type: {geometry.room_type}")
            lines.append(f"  Room shape code: {geometry.room_shape_code}")
            lines.append(
                f"  Shape: {geometry.shape} (confidence: {geometry.shape_confidence:.2f})"
            )

            # 如果是L形，添加折角方向分析
            if geometry.shape == "L_shape":
                missing_corner = self._get_l_shape_corner(
                    geometry.min_x,
                    geometry.max_x,
                    geometry.min_y,
                    geometry.max_y,
                    geometry.raw_samples,
                )
                lines.append(f"  Missing corner: {missing_corner}")

            lines.append(
                f"  Bounds: ({geometry.min_x:.0f}, {geometry.min_y:.0f}) - ({geometry.max_x:.0f}, {geometry.max_y:.0f})"
            )
            lines.append(
                f"  Dimensions: {geometry.max_x - geometry.min_x:.0f} x {geometry.max_y - geometry.min_y:.0f}"
            )
            lines.append(f"  Samples: {geometry.sample_count}")
            lines.append(f"  Avg move ratio: {geometry.move_ratio_avg:.2f}")
            lines.append(f"  Walls detected: {len(geometry.walls)}")

            for wall in geometry.walls:
                lines.append(
                    f"    - {wall.side}: confidence={wall.confidence:.2f}, samples={len(wall.samples)}"
                )

            lines.append("")

        # 添加L形房间摘要
        l_shape_rooms = [
            g for g in self.analyzed_rooms.values() if g.shape == "L_shape"
        ]
        if l_shape_rooms:
            lines.append("=" * 60)
            lines.append("L-Shape Rooms Summary (向内折角)")
            lines.append("=" * 60)
            for g in l_shape_rooms:
                missing_corner = self._get_l_shape_corner(
                    g.min_x, g.max_x, g.min_y, g.max_y, g.raw_samples
                )
                lines.append(
                    f"  Room {g.room_index}: {missing_corner} missing "
                    f"({g.max_x - g.min_x:.0f}x{g.max_y - g.min_y:.0f}), "
                    f"samples={g.sample_count}"
                )

        report = "\n".join(lines)

        report_file = self.output_dir / "analysis_report.txt"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)

        logger.info(f"Report saved to {report_file}")

        return report


def main():
    parser = argparse.ArgumentParser(
        description="Analyze room geometry from player position samples v2.0"
    )
    parser.add_argument(
        "--input-dir",
        type=str,
        default="./room_data",
        help="Input directory with collected data (default: ./room_data)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./analyzed_rooms",
        help="Output directory for analyzed results (default: ./analyzed_rooms)",
    )

    args = parser.parse_args()

    analyzer = RoomGeometryAnalyzer(args.input_dir, args.output_dir)

    if not analyzer.load_data():
        return

    analyzer.analyze_all()
    analyzer.export_results()
    report = analyzer.generate_report()

    print("\n" + report)


if __name__ == "__main__":
    main()
