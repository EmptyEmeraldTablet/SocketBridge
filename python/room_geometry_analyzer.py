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
        检测房间形状 v2.0

        基于参考算法实现：从边界采样点还原图形

        核心策略：
        1. 先推断每个采样点所在的墙壁
        2. 分析各面墙的采样覆盖范围
        3. 使用网格密度分析检测稀疏区域（内角区域）
        4. 综合判断房间形状

        以撒的房间只有两种形状：
        - rectangle - 标准矩形
        - L_shape - 向内折角的L形（某个角落被遮挡）

        房间大小约束：
        - 只有大房间（网格 >= 15x9 或 面积 >= 400x250）才可能是L形
        - 小房间、标准房间、长条走廊只能是矩形
        """
        # 确保所有值都不是 None
        if not positions:
            return "unknown", 0.0
        if min_x is None or max_x is None or min_y is None or max_y is None:
            return "unknown", 0.0

        # 计算房间尺寸
        room_width = max_x - min_x
        room_height = max_y - min_y
        room_area = room_width * room_height

        # === 房间大小约束检查 ===
        # L形房间只存在于大房间中
        # 标准房间(shape=1)、小房间、长条走廊只能是矩形

        # 最小大房间尺寸阈值（以网格单位计算）
        MIN_L_SHAPE_WIDTH = 800.0  # 约20格
        MIN_L_SHAPE_HEIGHT = 400.0  # 约10格
        MIN_L_SHAPE_AREA = 400000.0  # 约400格

        # 允许L形的形状代码（以撒的结合 Rebirth）
        # Shape Code 1-8: 矩形房间
        # Shape Code 9-12: L形房间 (L1, L2, L3, L4)
        L_SHAPE_ALLOWED_CODES = {9, 10, 11, 12}

        is_large_room = (
            room_width >= MIN_L_SHAPE_WIDTH
            and room_height >= MIN_L_SHAPE_HEIGHT
            and room_area >= MIN_L_SHAPE_AREA
        )

        is_l_shape_allowed = room_shape_code in L_SHAPE_ALLOWED_CODES

        # 如果房间太小或形状代码不允许L形，直接返回矩形
        if not is_large_room or not is_l_shape_allowed:
            # 小房间、标准房间只能是矩形
            logger.debug(
                f"Room {room_shape_code} ({room_width:.0f}x{room_height:.0f}): "
                f"large_room={is_large_room}, l_shape_allowed={is_l_shape_allowed} -> rectangle"
            )
            return "rectangle", 0.95

        # === 大房间继续进行L形检测 ===

        # 步骤1：推断每个采样点所在的墙壁
        left_samples = []
        right_samples = []
        top_samples = []
        bottom_samples = []
        all_player_x = []
        all_player_y = []

        for sample in positions:
            # positions contains player_positions with keys: player_x, player_y, inferred_x, inferred_y, side, sample
            player_x = sample.get("player_x", 0)
            player_y = sample.get("player_y", 0)
            player_size = sample.get("player_size", 15.0)

            # Try to get player_size from the original sample if available
            original_sample = sample.get("sample", {})
            if original_sample and isinstance(original_sample, dict):
                ps = original_sample.get("player_size")
                if ps:
                    player_size = ps

            if player_x and player_y:
                all_player_x.append(player_x)
                all_player_y.append(player_y)

                # 推断墙壁位置
                wall_x, wall_y, side = self._infer_wall_position(
                    player_x, player_y, min_x, max_x, min_y, max_y, player_size
                )

                # 根据推断的墙壁方向分类
                if side == "left":
                    left_samples.append(
                        {
                            "player_x": player_x,
                            "player_y": player_y,
                            "inferred_x": wall_x,
                            "inferred_y": wall_y,
                            "sample": sample,
                        }
                    )
                elif side == "right":
                    right_samples.append(
                        {
                            "player_x": player_x,
                            "player_y": player_y,
                            "inferred_x": wall_x,
                            "inferred_y": wall_y,
                            "sample": sample,
                        }
                    )
                elif side == "top":
                    top_samples.append(
                        {
                            "player_x": player_x,
                            "player_y": player_y,
                            "inferred_x": wall_x,
                            "inferred_y": wall_y,
                            "sample": sample,
                        }
                    )
                elif side == "bottom":
                    bottom_samples.append(
                        {
                            "player_x": player_x,
                            "player_y": player_y,
                            "inferred_x": wall_x,
                            "inferred_y": wall_y,
                            "sample": sample,
                        }
                    )

        # 步骤2：计算各面墙的覆盖范围
        def get_coverage(range_min, range_max, total_length):
            if range_min is None or range_max is None:
                return 0.0
            return max(0.0, (range_max - range_min) / total_length)

        left_y_range = self._get_sample_range(left_samples, "inferred_y")
        right_y_range = self._get_sample_range(right_samples, "inferred_y")
        top_x_range = self._get_sample_range(top_samples, "inferred_x")
        bottom_x_range = self._get_sample_range(bottom_samples, "inferred_x")

        left_coverage = get_coverage(left_y_range[0], left_y_range[1], room_height)
        right_coverage = get_coverage(right_y_range[0], right_y_range[1], room_height)
        top_coverage = get_coverage(top_x_range[0], top_x_range[1], room_width)
        bottom_coverage = get_coverage(bottom_x_range[0], bottom_x_range[1], room_width)

        # 步骤3：检测L形特征
        # L形的特征：某面墙的覆盖率偏低，或某面墙的部分区域完全没有采样
        MIN_SAMPLES = 3
        COVERAGE_THRESHOLD = 0.6

        l_shape_indicators = []

        # 左墙覆盖率低 → 可能缺少左下角或左上角
        if left_coverage < COVERAGE_THRESHOLD and len(left_samples) >= MIN_SAMPLES:
            if (
                left_y_range[1] is not None
                and left_y_range[1] < min_y + room_height * 0.6
            ):
                l_shape_indicators.append("bottom_left")
            elif (
                left_y_range[0] is not None
                and left_y_range[0] > min_y + room_height * 0.4
            ):
                l_shape_indicators.append("top_left")

        # 右墙覆盖率低
        if right_coverage < COVERAGE_THRESHOLD and len(right_samples) >= MIN_SAMPLES:
            if (
                right_y_range[1] is not None
                and right_y_range[1] < min_y + room_height * 0.6
            ):
                l_shape_indicators.append("bottom_right")
            elif (
                right_y_range[0] is not None
                and right_y_range[0] > min_y + room_height * 0.4
            ):
                l_shape_indicators.append("top_right")

        # 上墙覆盖率低 → 可能是L形折叠在顶部
        if len(top_samples) >= MIN_SAMPLES:
            # 检查上墙是否有明显的采样缺失（只采样了部分区域）
            if top_coverage < COVERAGE_THRESHOLD:
                if (
                    top_x_range[1] is not None
                    and top_x_range[1] < min_x + room_width * 0.6
                ):
                    l_shape_indicators.append("top_right")
                elif (
                    top_x_range[0] is not None
                    and top_x_range[0] > min_x + room_width * 0.4
                ):
                    l_shape_indicators.append("top_left")
            else:
                # 上墙覆盖率正常，但采样范围可能偏向一侧
                # 检查是否只采样了中间区域（两端缺失）
                if (
                    top_x_range[0] is not None
                    and top_x_range[0] > min_x + room_width * 0.3
                ):
                    l_shape_indicators.append("top_left")
                if (
                    top_x_range[1] is not None
                    and top_x_range[1] < max_x - room_width * 0.3
                ):
                    l_shape_indicators.append("top_right")

        # 下墙覆盖率低
        if bottom_coverage < COVERAGE_THRESHOLD and len(bottom_samples) >= MIN_SAMPLES:
            if (
                bottom_x_range[1] is not None
                and bottom_x_range[1] < min_x + room_width * 0.6
            ):
                l_shape_indicators.append("bottom_right")
            elif (
                bottom_x_range[0] is not None
                and bottom_x_range[0] > min_x + room_width * 0.4
            ):
                l_shape_indicators.append("bottom_left")
            elif (
                left_y_range[0] is not None
                and left_y_range[0] > min_y + room_height * 0.4
            ):
                l_shape_indicators.append("top_left")

        # 右墙覆盖率低
        if right_coverage < COVERAGE_THRESHOLD and len(right_samples) >= MIN_SAMPLES:
            if (
                right_y_range[1] is not None
                and right_y_range[1] < min_y + room_height * 0.6
            ):
                l_shape_indicators.append("bottom_right")
            elif (
                right_y_range[0] is not None
                and right_y_range[0] > min_y + room_height * 0.4
            ):
                l_shape_indicators.append("top_right")

        # 上墙覆盖率低
        if top_coverage < COVERAGE_THRESHOLD and len(top_samples) >= MIN_SAMPLES:
            if top_x_range[1] is not None and top_x_range[1] < min_x + room_width * 0.6:
                l_shape_indicators.append("top_right")
            elif (
                top_x_range[0] is not None and top_x_range[0] > min_x + room_width * 0.4
            ):
                l_shape_indicators.append("top_left")

        # 下墙覆盖率低
        if bottom_coverage < COVERAGE_THRESHOLD and len(bottom_samples) >= MIN_SAMPLES:
            if (
                bottom_x_range[1] is not None
                and bottom_x_range[1] < min_x + room_width * 0.6
            ):
                l_shape_indicators.append("bottom_right")
            elif (
                bottom_x_range[0] is not None
                and bottom_x_range[0] > min_x + room_width * 0.4
            ):
                l_shape_indicators.append("bottom_left")

        # 步骤4：使用网格密度分析检测内角区域（参考算法2.2）
        density_analysis = self._analyze_grid_density(
            all_player_x,
            all_player_y,
            min_x,
            max_x,
            min_y,
            max_y,
            room_width,
            room_height,
        )

        if density_analysis["has_sparse_region"]:
            # 发现稀疏区域，添加内角指示
            for corner in density_analysis["sparse_corners"]:
                if corner not in l_shape_indicators:
                    l_shape_indicators.append(corner)

        # 步骤5：综合判断
        # 游戏形状代码是权威来源，采样数据用于验证
        is_l_shape_code = room_shape_code in {9, 10, 11, 12}

        if l_shape_indicators:
            from collections import Counter

            corner_counts = Counter(l_shape_indicators)
            # 选择最常见的缺失角落
            missing_corner = corner_counts.most_common(1)[0][0]

            # 置信度计算 v2.0
            sampling_confirms = (
                len(l_shape_indicators) >= 2 or density_analysis["has_sparse_region"]
            )

            if is_l_shape_code:
                # 游戏代码指示是L形 - 这是权威信息
                if sampling_confirms:
                    # 采样数据也确认是L形
                    confidence = 0.98
                else:
                    # 采样数据不明确，但游戏代码是权威的
                    confidence = 0.92
            else:
                # 没有L形代码，使用采样数据判断
                base_confidence = 0.6 + len(l_shape_indicators) * 0.1
                if density_analysis["has_sparse_region"]:
                    base_confidence += 0.15
                confidence = min(0.90, base_confidence)

            return "L_shape", confidence

        # 步骤6：后备判断 - 检查各面是否有足够的采样
        left_count = len(left_samples)
        right_count = len(right_samples)
        top_count = len(top_samples)
        bottom_count = len(bottom_samples)
        total_samples = len(positions)

        # 如果游戏代码指示是L形，但采样数据没有明确指示
        # 仍然应该返回L形，因为游戏代码是权威的
        if is_l_shape_code:
            return "L_shape", 0.90

        # 如果所有面都有采样，且覆盖率都较高，则是矩形
        if (
            left_coverage > 0.7
            and right_coverage > 0.7
            and top_coverage > 0.7
            and bottom_coverage > 0.7
        ):
            return "rectangle", 0.95

        # 如果覆盖率普遍较低但没有明确的L形指示，可能是复杂形状
        if (
            left_coverage < 0.3
            and right_coverage < 0.3
            and top_coverage < 0.3
            and bottom_coverage < 0.3
        ):
            return "unknown", 0.3

        # 部分面覆盖率低但没有明确的L形特征，可能是小房间或边界情况
        if left_count > 0 and right_count > 0 and top_count > 0 and bottom_count > 0:
            return "rectangle", 0.70

        # 有面缺失，可能是L形
        return "L_shape", 0.6

    def _get_sample_range(
        self, samples: List[dict], coord: str
    ) -> Tuple[Optional[float], Optional[float]]:
        """获取采样点坐标范围"""
        if not samples:
            return None, None
        coords = [s[coord] for s in samples if s.get(coord) is not None]
        if not coords:
            return None, None
        return min(coords), max(coords)

    def _analyze_grid_density(
        self,
        player_x: List[float],
        player_y: List[float],
        min_x: float,
        max_x: float,
        min_y: float,
        max_y: float,
        room_width: float,
        room_height: float,
    ) -> dict:
        """
        网格密度分析 - 参考算法2.2角点检测

        策略：将房间划分为网格，统计每个网格的采样点密度
        L形的内角区域会有明显的稀疏（玩家无法到达）
        """
        if not player_x or not player_y:
            return {"has_sparse_region": False, "sparse_corners": []}

        # 划分网格 (4x4)
        grid_cols = 4
        grid_rows = 4
        cell_width = room_width / grid_cols
        cell_height = room_height / grid_rows

        # 统计每个网格的采样点数量
        grid_counts = [[0 for _ in range(grid_cols)] for _ in range(grid_rows)]
        total_samples = len(player_x)

        for px, py in zip(player_x, player_y):
            col = int((px - min_x) / cell_width)
            row = int((py - min_y) / cell_height)
            # 边界处理
            col = max(0, min(grid_cols - 1, col))
            row = max(0, min(grid_rows - 1, row))
            grid_counts[row][col] += 1

        # 计算平均密度
        avg_density = total_samples / (grid_cols * grid_rows)

        # 找出稀疏区域（密度低于平均的50%，0样本也算）
        sparse_cells = []
        for row in range(grid_rows):
            for col in range(grid_cols):
                if grid_counts[row][col] < avg_density * 0.5:
                    sparse_cells.append((row, col))

        # 映射稀疏区域到角落
        corner_mapping = {
            (0, 0): "top_left",  # 左上
            (0, 1): "top",  # 上中
            (0, 2): "top",  # 上中
            (0, 3): "top_right",  # 右上
            (1, 0): "left",  # 左中
            (1, 3): "right",  # 右中
            (2, 0): "left",  # 左中
            (2, 3): "right",  # 右中
            (3, 0): "bottom_left",  # 左下
            (3, 1): "bottom",  # 下中
            (3, 2): "bottom",  # 下中
            (3, 3): "bottom_right",  # 右下
        }

        sparse_corners = set()
        for row, col in sparse_cells:
            if (row, col) in corner_mapping:
                sparse_corners.add(corner_mapping[(row, col)])

        # 如果稀疏区域集中在某个角落或边，认为是L形
        # 条件：至少2个稀疏单元格，且它们属于同一个角落区域
        has_sparse = len(sparse_cells) >= 2

        # 进一步检查稀疏区域是否集中在特定角落
        if has_sparse:
            corner_scores = {}
            for corner in ["top_left", "top_right", "bottom_left", "bottom_right"]:
                score = sum(
                    1
                    for r, c in sparse_cells
                    if (r, c)
                    in [
                        (0, 0),
                        (0, 1),
                        (0, 2),
                        (0, 3),  # top row
                        (1, 0),  # left middle
                        (1, 3),  # right middle
                        (2, 0),  # left middle
                        (2, 3),  # right middle
                        (3, 0),
                        (3, 1),
                        (3, 2),
                        (3, 3),  # bottom row
                    ]
                )
                corner_scores[corner] = score

            # 如果某个角落区域得分最高且稀疏单元格>=2，认为是L形
            if corner_scores:
                best_corner = max(corner_scores.items(), key=lambda x: x[1])[0]
                if corner_scores[best_corner] >= 2:
                    has_sparse = True
                    sparse_corners = {best_corner}
                else:
                    has_sparse = False
                    sparse_corners = set()

        return {
            "has_sparse_region": has_sparse,
            "sparse_corners": list(sparse_corners),
            "grid_counts": grid_counts,
            "avg_density": avg_density,
        }

    def _get_l_shape_corner(
        self,
        min_x: float,
        max_x: float,
        min_y: float,
        max_y: float,
        raw_samples: List[dict],
        room_shape_code: int = 0,
    ) -> str:
        """
        判断L形房间缺失的是哪个角落

        策略：
        1. 优先使用游戏形状代码判断
        2. 次选使用采样数据分析

        以撒的房间形状代码：
        - Shape 9 (L1): top-left 缺失
        - Shape 10 (L2): top-right 缺失
        - Shape 11 (L3): bottom-left 缺失
        - Shape 12 (L4): bottom-right 缺失
        """
        # 1. 使用游戏形状代码判断（最可靠）
        if room_shape_code in {9, 10, 11, 12}:
            shape_to_corner = {
                9: "top_left",  # L1 - 左上缺失
                10: "top_right",  # L2 - 右上缺失
                11: "bottom_left",  # L3 - 左下缺失
                12: "bottom_right",  # L4 - 右下缺失
            }
            return shape_to_corner.get(room_shape_code, "unknown")

        # 2. 使用采样数据分析（后备方案）
        if not raw_samples:
            return "unknown"

        # 从原始采样点推断墙壁方向
        left_count = 0
        right_count = 0
        top_count = 0
        bottom_count = 0

        for sample in raw_samples:
            pos = sample.get("position", [])
            player_size = sample.get("player_size", 15.0)
            room_tl = sample.get("room_top_left", [])
            room_br = sample.get("room_bottom_right", [])

            if pos and len(pos) >= 2 and room_tl and room_br:
                _, _, side = self._infer_wall_position(
                    pos[0],
                    pos[1],
                    room_tl[0],
                    room_tl[1],
                    room_br[0],
                    room_br[1],
                    player_size,
                )
                if side == "left":
                    left_count += 1
                elif side == "right":
                    right_count += 1
                elif side == "top":
                    top_count += 1
                elif side == "bottom":
                    bottom_count += 1

        total = left_count + right_count + top_count + bottom_count
        if total == 0:
            return "unknown"

        # 找出覆盖率最低的两个方向组合
        side_counts = {
            "left": left_count,
            "right": right_count,
            "top": top_count,
            "bottom": bottom_count,
        }

        # 找出采样最少的方向
        sorted_sides = sorted(side_counts.items(), key=lambda x: x[1])

        if len(sorted_sides) >= 2:
            min1_name, min1_count = sorted_sides[0]
            min2_name, min2_count = sorted_sides[1]

            # 如果前两个方向的采样数接近（相差不到50%），认为它们组成缺失的角落
            if min1_count > 0 and min2_count / min1_count < 1.5:
                # 组合两个方向判断角落
                corner_sides = {min1_name, min2_name}
                if "left" in corner_sides and "top" in corner_sides:
                    return "top_left"
                elif "right" in corner_sides and "top" in corner_sides:
                    return "top_right"
                elif "left" in corner_sides and "bottom" in corner_sides:
                    return "bottom_left"
                elif "right" in corner_sides and "bottom" in corner_sides:
                    return "bottom_right"

        # 如果只有一个方向明显缺失，使用单个方向判断
        min_side = sorted_sides[0][0]
        if min_side == "left":
            # 左墙缺失，可能是左上或左下
            # 检查上墙和下墙的覆盖率
            if top_count < bottom_count:
                return "top_left"
            else:
                return "bottom_left"
        elif min_side == "right":
            # 右墙缺失，可能是右上或右下
            if top_count < bottom_count:
                return "top_right"
            else:
                return "bottom_right"
        elif min_side == "top":
            return "top_left"  # 默认返回左上
        else:
            return "bottom_left"  # 默认返回左下

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
                    geometry.room_shape_code,
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
                    g.min_x, g.max_x, g.min_y, g.max_y, g.raw_samples, g.room_shape_code
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
