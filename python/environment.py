"""
SocketBridge 环境建模层

构建和管理游戏环境的二维表示，包括：
- 网格化地图系统
- 静态障碍物标记
- 动态障碍物追踪
- 可通行性判断
- 空间查询功能

适配录制数据的房间格式。
"""

import math
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from models import (
    Vector2D,
    RoomInfo,
    EnemyData,
    ProjectileData,
    DoorData,
)

logger = logging.getLogger("Environment")


class TileType(Enum):
    """瓦片类型"""

    EMPTY = 0  # 空地，可行走
    WALL = 1  # 墙壁，不可行走
    DOOR = 2  # 门
    HAZARD = 3  # 危险区域
    SPECIAL = 4  # 特殊区域
    VOID = 5  # 虚空，不属于房间（L型房间的缺口）


class EntityType(Enum):
    """房间实体类型枚举

    用于分类和注册所有房间内实体，支持扩展新类型。
    """

    # 危险物
    FIRE_HAZARD = "fire_hazard"  # 火堆
    SPIKES = "spikes"  # 尖刺
    BOMB = "bomb"  # 炸弹

    # 可交互物
    BUTTON = "button"  # 按钮
    DESTRUCTIBLE = "destructible"  # 可破坏物
    INTERACTABLE = "interactable"  # 可互动实体（机器、乞丐等）
    PICKUP = "pickup"  # 可拾取物

    # 特殊
    TRAPDOOR = "trapdoor"  # 活板门（下一层）
    CRAWLSPACE = "crawlspace"  # 夹层入口


@dataclass
class RoomEntity:
    """房间实体

    统一存储所有房间内非玩家实体。
    """

    entity_type: EntityType  # 实体类型
    entity_id: int  # 游戏内 ID
    position: Vector2D  # 像素坐标
    variant_name: str = ""  # 变种名称
    state: int = 0  # 状态
    distance: float = 0.0  # 到玩家距离
    radius: float = 20.0  # 碰撞半径
    is_active: bool = True  # 是否激活
    extra_data: Dict[str, Any] = field(default_factory=dict)  # 额外数据

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "type": self.entity_type.value,
            "id": self.entity_id,
            "x": self.position.x,
            "y": self.position.y,
            "variant": self.variant_name,
            "state": self.state,
            "distance": self.distance,
            "active": self.is_active,
        }


@dataclass
class Obstacle:
    """障碍物"""

    position: Vector2D
    radius: float
    is_dynamic: bool = False
    obstacle_type: str = "generic"

    def get_bounding_box(self) -> Tuple[Vector2D, Vector2D]:
        """获取边界框 (左上, 右下)"""
        half = self.radius
        return (
            Vector2D(self.position.x - half, self.position.y - half),
            Vector2D(self.position.x + half, self.position.y + half),
        )

    def intersects(self, pos: Vector2D, radius: float = 0) -> bool:
        """检查是否与给定圆形相交"""
        distance = self.position.distance_to(pos)
        return distance < (self.radius + radius)


@dataclass
class DangerZone:
    """危险区域"""

    center: Vector2D
    radius: float
    danger_type: str = "generic"
    intensity: float = 1.0
    estimated_frames: int = 60


class GameMap:
    """游戏地图模型

    二维网格地图，支持静态和动态障碍物管理。
    """

    def __init__(self, grid_size: float = 40.0, width: int = 13, height: int = 7):
        """
        初始化地图

        Args:
            grid_size: 网格大小（像素）
            width: 网格宽度
            height: 网格高度
        """
        self.grid_size = grid_size
        self.width = width
        self.height = height

        # 像素尺寸（不包含墙壁，可移动区域）
        # 公式: pixel = (grid - 2) * grid_size
        # 来源: python/analyzed_rooms/ROOM_GEOMETRY_BY_SESSION.md
        self.pixel_width = max(0, (width - 2) * grid_size)
        self.pixel_height = max(0, (height - 2) * grid_size)

        # 网格数据: (grid_x, grid_y) -> TileType
        self.grid: Dict[Tuple[int, int], TileType] = {}

        # 静态障碍物
        self.static_obstacles: Set[Tuple[int, int]] = set()

        # 动态障碍物
        self.dynamic_obstacles: List[Obstacle] = []
        self.dynamic_obstacles_dict: Dict[int, Obstacle] = {}

        # 危险区域
        self.danger_zones: List[DangerZone] = []

        # 虚空区域（L型房间的缺口），这些位置不属于房间
        self.void_tiles: Set[Tuple[int, int]] = set()

        # 门数据（从 ROOM_LAYOUT.doors 解析）
        # DoorData: direction (0-7), type, target_room, is_open
        self.doors: List[DoorData] = []

        # 房间实体注册表 (EntityType -> List[RoomEntity])
        # 用于存储: FIRE_HAZARDS, BUTTONS, DESTRUCTIBLES, INTERACTABLES, PICKUPS, etc.
        self.entities: Dict[EntityType, List[RoomEntity]] = {
            EntityType.FIRE_HAZARD: [],
            EntityType.SPIKES: [],
            EntityType.BOMB: [],
            EntityType.BUTTON: [],
            EntityType.DESTRUCTIBLE: [],
            EntityType.INTERACTABLE: [],
            EntityType.PICKUP: [],
            EntityType.TRAPDOOR: [],
            EntityType.CRAWLSPACE: [],
        }

        # 初始化为空地图
        self._initialize_empty_map()

    def _initialize_empty_map(self):
        """初始化空地图"""
        for gx in range(self.width):
            for gy in range(self.height):
                self.grid[(gx, gy)] = TileType.EMPTY

    def update_from_room_info(self, room_info: RoomInfo):
        """从房间信息更新地图（简化版，无布局数据时使用）

        DEBUG: Added room_shape and grid_size handling based on analyzed_rooms.
        """
        if room_info is None:
            return

        logger.debug(
            f"[GameMap] update_from_room_info: room={room_info.room_index}, "
            f"grid={room_info.grid_width}x{room_info.grid_height}, shape={room_info.room_shape}"
        )

        # 更新地图尺寸
        if room_info.grid_width > 0:
            self.width = room_info.grid_width
        if room_info.grid_height > 0:
            self.height = room_info.grid_height

        # grid_size 保持不变（常量 40）
        # DEBUG: Log grid_size verification
        logger.debug(f"[GameMap] grid_size unchanged: {self.grid_size}")

        # 像素尺寸优先使用 RoomInfo 中的值，如果为 0 则从网格计算（不包含墙壁）
        # 公式: pixel = (grid - 2) * grid_size
        # 来源: python/analyzed_rooms/ROOM_GEOMETRY_BY_SESSION.md
        if room_info.pixel_width > 0:
            self.pixel_width = room_info.pixel_width
        else:
            self.pixel_width = max(0, (self.width - 2) * self.grid_size)

        if room_info.pixel_height > 0:
            self.pixel_height = room_info.pixel_height
        else:
            self.pixel_height = max(0, (self.height - 2) * self.grid_size)

        logger.debug(
            f"[GameMap] Pixel dimensions: {self.pixel_width}x{self.pixel_height}"
        )

        # 重新初始化网格
        self.grid.clear()
        self.static_obstacles.clear()
        self.doors.clear()  # DEBUG: Clear doors when no layout data
        self._initialize_empty_map()

        # 默认创建一个空房间（墙壁边界）
        self._create_default_walls()

    def update_from_room_layout(
        self, room_info: RoomInfo, layout_data: Dict[str, Any], grid_size: float = 40.0
    ):
        """从ROOM_LAYOUT数据更新地图（支持L型房间等复杂形状）

        DEBUG: Added comprehensive logging for room_shape and grid_size tracking.
        Key findings from analyzed_rooms:
          - grid_size = 40 (constant for all room types)
          - room_shape 2 = L-shape (top fold), height=120px (not 280px)
          - API grid dimensions include walls (internal = api - 2)

        Args:
            room_info: 房间信息
            layout_data: ROOM_LAYOUT原始数据，包含grid和doors
            grid_size: 网格大小（像素），常量 40
        """
        if layout_data is None:
            logger.debug(
                f"[GameMap] No layout_data for room {room_info.room_index if room_info else 'None'}"
            )
            self.update_from_room_info(room_info)
            return

        # DEBUG: Log input parameters
        logger.debug(
            f"[GameMap] update_from_room_layout: room={room_info.room_index if room_info else 'None'}, "
            f"grid_size={grid_size}, shape={room_info.room_shape if room_info else 'None'}"
        )

        # 更新地图尺寸
        if room_info.grid_width > 0:
            self.width = room_info.grid_width
        if room_info.grid_height > 0:
            self.height = room_info.grid_height

        # DEBUG: Log dimension changes
        logger.debug(
            f"[GameMap] Dimensions: {self.width}x{self.height} grids, input_grid_size={grid_size}"
        )

        # 强制使用 grid_size=40（游戏实际使用的值）
        # 录制数据中的 grid_size=135 是中间值/录制格式，不应用于坐标转换
        # 来源: python/analyzed_rooms/ROOM_GEOMETRY_BY_SESSION.md
        self.grid_size = 40.0
        ACTUAL_GRID_SIZE = 40.0

        # 计算像素尺寸（不包含墙壁，可移动区域）
        # 公式: pixel = (grid - 2) * 40
        # 使用实际游戏 grid_size=40
        self.pixel_width = max(0, (self.width - 2) * ACTUAL_GRID_SIZE)
        self.pixel_height = max(0, (self.height - 2) * ACTUAL_GRID_SIZE)

        logger.debug(
            f"[GameMap] Pixel dimensions: {self.pixel_width}x{self.pixel_height}"
        )

        # 清空现有数据
        self.grid.clear()
        self.static_obstacles.clear()
        self.void_tiles.clear()

        # 初始化所有格子为EMPTY（ROOM_LAYOUT.grid只包含特殊格子，其他都是地板）
        # DEBUG: This matches analyzed_rooms finding - ROOM_LAYOUT.grid only contains obstacles
        for gx in range(self.width):
            for gy in range(self.height):
                self.grid[(gx, gy)] = TileType.EMPTY

        # DEBUG: Log grid parsing
        grid_data = layout_data.get("grid", {})
        tile_count = len(grid_data) if isinstance(grid_data, dict) else 0
        logger.debug(f"[GameMap] Parsing {tile_count} grid tiles from ROOM_LAYOUT")

        if isinstance(grid_data, dict):
            # grid是字典格式: {"0": {"x": 64, "y": 64, "type": 1000, "collision": 1}, ...}
            wall_count = 0
            for idx_str, tile_data in grid_data.items():
                tile_x = tile_data.get("x", 0)
                tile_y = tile_data.get("y", 0)
                collision = tile_data.get("collision", 0)
                tile_type = tile_data.get("type", 0)
                variant = tile_data.get("variant", 0)

                # 转换为网格坐标（使用实际游戏 grid_size=40）
                # 录制数据中的 grid_size=135 是中间值，不应用于坐标转换
                gx = int(tile_x / ACTUAL_GRID_SIZE)
                gy = int(tile_y / ACTUAL_GRID_SIZE)

                # 检查是否在有效范围内
                if 0 <= gx < self.width and 0 <= gy < self.height:
                    # 根据 tile_type 和 variant 判断格子类型
                    # GridEntityType 映射到 TileType
                    # 障碍物 (WALL): 2,3,4,11,15,21,22,24,25,26,27
                    # 危险 (HAZARD): 8,9,10
                    # 特殊 (SPECIAL): 17,18,19,23
                    # 坑 (VOID): 7
                    if tile_type == 7 and collision > 0:
                        self.grid[(gx, gy)] = TileType.VOID
                    elif tile_type == 8 or tile_type == 9:
                        self.grid[(gx, gy)] = TileType.HAZARD
                        center = Vector2D(
                            x=gx * self.grid_size + self.grid_size / 2,
                            y=gy * self.grid_size + self.grid_size / 2,
                        )
                        self.danger_zones.append(
                            DangerZone(
                                center=center,
                                radius=self.grid_size / 2,
                                danger_type="spikes",
                                intensity=1.0,
                            )
                        )
                    elif tile_type == 10:
                        self.grid[(gx, gy)] = TileType.HAZARD
                        center = Vector2D(
                            x=gx * self.grid_size + self.grid_size / 2,
                            y=gy * self.grid_size + self.grid_size / 2,
                        )
                        self.danger_zones.append(
                            DangerZone(
                                center=center,
                                radius=self.grid_size / 2,
                                danger_type="web",
                                intensity=0.5,
                            )
                        )
                    elif tile_type in [2, 3, 4, 11, 15, 21, 22, 24, 25, 26, 27]:
                        # 障碍物: 岩石、方块、染色岩、锁块、墙、雕像、超染岩、柱子、尖刺岩、染色骷髅、聚宝岩
                        if collision > 0:
                            self.grid[(gx, gy)] = TileType.WALL
                            self.static_obstacles.add((gx, gy))
                            wall_count += 1
                    elif tile_type in [17, 18, 19, 23]:
                        # 特殊: 陷阱门、楼梯、重力、传送门
                        self.grid[(gx, gy)] = TileType.SPECIAL
                    elif tile_type == 1 and variant == 8:
                        # DECORATION variant=8: 特殊地面覆盖物，忽略
                        pass
                    else:
                        if collision > 0:
                            self.grid[(gx, gy)] = TileType.WALL
                            self.static_obstacles.add((gx, gy))
                            wall_count += 1

            logger.debug(
                f"[GameMap] Marked {wall_count} walls, {len(self.static_obstacles)} static obstacles"
            )

        # DEBUG: Parse doors from ROOM_LAYOUT
        # Doors format per DATA_PROTOCOL.md:
        # {"0": {"target_room": 3, "target_room_type": 1, "is_open": true, "is_locked": false}, ...}
        doors_data = layout_data.get("doors", {})
        if isinstance(doors_data, dict) and doors_data:
            self.doors.clear()
            for door_idx, door_info in doors_data.items():
                try:
                    door = DoorData(
                        direction=int(door_idx) if door_idx.isdigit() else 0,
                        door_type=door_info.get("type", "door"),
                        target_room=door_info.get("target_room", -1),
                        is_open=door_info.get("is_open", False),
                    )
                    self.doors.append(door)
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"[GameMap] Failed to parse door at index {door_idx}: {e}"
                    )
            logger.debug(f"[GameMap] Parsed {len(self.doors)} doors from ROOM_LAYOUT")
        else:
            self.doors.clear()
            logger.debug(
                f"[GameMap] No doors data in ROOM_LAYOUT (doors_data={doors_data})"
            )

        # L形房间检测 (Shape Code 9-12)
        # Shape 9: L1 (左上缺失), Shape 10: L2 (右上缺失)
        # Shape 11: L3 (左下缺失), Shape 12: L4 (右下缺失)
        # 来源: python/analyzed_rooms/ROOM_GEOMETRY_BY_SESSION.md
        if room_info and room_info.room_shape in [9, 10, 11, 12]:
            logger.debug(
                f"[GameMap] Room shape={room_info.room_shape} (L-shape) - Calculating VOID tiles"
            )
            # L-shaped room - mark missing corner area as VOID
            self._mark_l_shape_void_tiles(room_info)
        else:
            logger.debug(
                f"[GameMap] Room shape={room_info.room_shape if room_info else 'None'} - No VOID marking needed"
            )

        # 创建房间边界墙壁
        # 解析门位置用于跳过墙壁覆盖
        door_positions: Set[Tuple[int, int]] = set()
        doors_data = layout_data.get("doors", {})
        if isinstance(doors_data, dict) and doors_data:
            for door_idx, door_info in doors_data.items():
                try:
                    door_x = door_info.get("x", 0)
                    door_y = door_info.get("y", 0)
                    gx = int(door_x / ACTUAL_GRID_SIZE)
                    gy = int(door_y / ACTUAL_GRID_SIZE)
                    door_positions.add((gx, gy))
                except (ValueError, TypeError):
                    pass
        self._create_default_walls(door_positions)

    def _mark_l_shape_void_tiles(self, room_info: RoomInfo):
        """为L形房间标记VOID区域

        基于 analyzed_rooms 分析结论:
        L形房间基于大房间(26×14)剪去一个象限(13×7)：

        | Shape Code | 缺角位置 | 缺角边界 |
        |------------|----------|----------|
        | 9 | 左上(L1) | 左上 13×7 区域 |
        | 10 | 右上(L2) | 右上 13×7 区域 |
        | 11 | 左下(L3) | 左下 13×7 区域 |
        | 12 | 右下(L4) | 右下 13×7 区域 |

        大房间 L 形: grid=26×14, center=(13,7), 每个缺失区域=13×7
        来源: python/analyzed_rooms/ROOM_GEOMETRY_BY_SESSION.md
        """
        if not room_info:
            return

        shape = room_info.room_shape
        width = self.width
        height = self.height

        # 计算中心点（网格坐标）
        center_gx = width // 2  # 26/2 = 13
        center_gy = height // 2  # 14/2 = 7

        # 根据 Shape Code 确定缺角区域边界（网格坐标）
        # 跳过边界行/列（门的位置）：范围是 1 到 width-1 / height-1
        min_gx, max_gx = 1, width - 1
        min_gy, max_gy = 1, height - 1

        if shape == 9:  # L1 - 左上缺失
            void_gx_range = (min_gx, center_gx)
            void_gy_range = (min_gy, center_gy)
        elif shape == 10:  # L2 - 右上缺失
            void_gx_range = (center_gx, max_gx + 1)
            void_gy_range = (min_gy, center_gy)
        elif shape == 11:  # L3 - 左下缺失
            void_gx_range = (min_gx, center_gx)
            void_gy_range = (center_gy, max_gy + 1)
        elif shape == 12:  # L4 - 右下缺失
            void_gx_range = (center_gx, max_gx + 1)
            void_gy_range = (center_gy, max_gy + 1)
        else:
            logger.warning(f"[GameMap] Unknown L-shape type: {shape}")
            return

        logger.debug(
            f"[GameMap] L-shape VOID: shape={shape}, grid={width}x{height}, "
            f"center=({center_gx}, {center_gy}), "
            f"void_x=({void_gx_range[0]}-{void_gx_range[1]}), void_y=({void_gy_range[0]}-{void_gy_range[1]})"
        )

        # 标记 VOID 区域
        void_count = 0
        for gy in range(*void_gy_range):
            for gx in range(*void_gx_range):
                # 已经是墙壁的不处理
                if self.grid.get((gx, gy)) == TileType.WALL:
                    continue

                self.grid[(gx, gy)] = TileType.VOID
                self.void_tiles.add((gx, gy))
                void_count += 1

        logger.debug(
            f"[GameMap] Marked {void_count} VOID tiles for L-shape room (shape={shape})"
        )

    def clear_entities(self):
        """清除所有房间实体"""
        for entity_list in self.entities.values():
            entity_list.clear()
        logger.debug("[GameMap] Cleared all entities")

    # ========== 实体更新方法 ==========

    def update_fire_hazards(self, fire_data: List[Dict[str, Any]]):
        """更新火堆数据

        Args:
            fire_data: FIRE_HAZARDS 通道数据
                [{"id": 60, "type": "FIREPLACE", "pos": {"x": 400, "y": 350}, ...}]
        """
        self.entities[EntityType.FIRE_HAZARD].clear()
        count = 0
        for fire in fire_data:
            try:
                entity = RoomEntity(
                    entity_type=EntityType.FIRE_HAZARD,
                    entity_id=fire.get("id", 0),
                    position=Vector2D(
                        fire.get("pos", {}).get("x", 0), fire.get("pos", {}).get("y", 0)
                    ),
                    variant_name=fire.get("fireplace_type", fire.get("type", "")),
                    state=fire.get("state", 0),
                    distance=fire.get("distance", 0.0),
                    radius=fire.get("collision_radius", 25.0),
                    is_active=not fire.get("is_extinguished", False),
                    extra_data={
                        "hp": fire.get("hp", 0),
                        "max_hp": fire.get("max_hp", 0),
                        "is_shooting": fire.get("is_shooting", False),
                    },
                )
                self.entities[EntityType.FIRE_HAZARD].append(entity)
                count += 1
            except (ValueError, TypeError) as e:
                logger.warning(f"[GameMap] Failed to parse fire_hazard: {e}")

        logger.debug(f"[GameMap] Updated {count} fire_hazards")

    def update_buttons(self, button_data: Dict[str, Dict[str, Any]]):
        """更新按钮数据

        Args:
            button_data: BUTTONS 通道数据
                {"0": {"type": 18, "variant_name": "NORMAL", "x": 320, "y": 400, ...}, ...}
        """
        self.entities[EntityType.BUTTON].clear()
        count = 0
        for idx, btn in button_data.items():
            try:
                entity = RoomEntity(
                    entity_type=EntityType.BUTTON,
                    entity_id=int(idx) if idx.isdigit() else 0,
                    position=Vector2D(btn.get("x", 0), btn.get("y", 0)),
                    variant_name=btn.get("variant_name", ""),
                    state=btn.get("state", 0),
                    distance=btn.get("distance", 0.0),
                    radius=15.0,
                    is_active=not btn.get("is_pressed", False),
                    extra_data={
                        "btn_type": btn.get("type", 0),
                        "btn_variant": btn.get("variant", 0),
                    },
                )
                self.entities[EntityType.BUTTON].append(entity)
                count += 1
            except (ValueError, TypeError) as e:
                logger.warning(f"[GameMap] Failed to parse button: {e}")

        logger.debug(f"[GameMap] Updated {count} buttons")

    def update_destructibles(self, destructible_data: List[Dict[str, Any]]):
        """更新可破坏物数据

        Args:
            destructible_data: DESTRUCTIBLES 通道数据
                [{"id": 30, "type": 20, "variant_name": "CRACKED_ROCK", "pos": {...}, ...}]
        """
        self.entities[EntityType.DESTRUCTIBLE].clear()
        count = 0
        for dest in destructible_data:
            try:
                entity = RoomEntity(
                    entity_type=EntityType.DESTRUCTIBLE,
                    entity_id=dest.get("id", 0),
                    position=Vector2D(
                        dest.get("pos", {}).get("x", 0), dest.get("pos", {}).get("y", 0)
                    ),
                    variant_name=dest.get("variant_name", ""),
                    state=dest.get("state", 0),
                    distance=dest.get("distance", 0.0),
                    radius=dest.get("collision_radius", 20.0),
                    is_active=dest.get("state", 0) == 0,  # state=0 表示未破坏
                    extra_data={
                        "dest_type": dest.get("type", 0),
                        "dest_variant": dest.get("variant", 0),
                    },
                )
                self.entities[EntityType.DESTRUCTIBLE].append(entity)
                count += 1
            except (ValueError, TypeError) as e:
                logger.warning(f"[GameMap] Failed to parse destructible: {e}")

        logger.debug(f"[GameMap] Updated {count} destructibles")

    def update_interactables(self, interactable_data: List[Dict[str, Any]]):
        """更新可交互实体数据

        Args:
            interactable_data: INTERACTABLES 通道数据
                [{"id": 40, "variant_name": "SLOT_MACHINE", "pos": {...}, ...}]
        """
        self.entities[EntityType.INTERACTABLE].clear()
        count = 0
        for entity_data in interactable_data:
            try:
                entity = RoomEntity(
                    entity_type=EntityType.INTERACTABLE,
                    entity_id=entity_data.get("id", 0),
                    position=Vector2D(
                        entity_data.get("pos", {}).get("x", 0),
                        entity_data.get("pos", {}).get("y", 0),
                    ),
                    variant_name=entity_data.get("variant_name", ""),
                    state=entity_data.get("state", 0),
                    distance=entity_data.get("distance", 0.0),
                    radius=25.0,  # 机器通常较大
                    is_active=True,
                    extra_data={
                        "entity_type": entity_data.get("type", 0),
                        "entity_variant": entity_data.get("variant", 0),
                        "sub_type": entity_data.get("sub_type", 0),
                    },
                )
                self.entities[EntityType.INTERACTABLE].append(entity)
                count += 1
            except (ValueError, TypeError) as e:
                logger.warning(f"[GameMap] Failed to parse interactable: {e}")

        logger.debug(f"[GameMap] Updated {count} interactables")

    def update_pickups(self, pickup_data: List[Dict[str, Any]]):
        """更新可拾取物数据

        Args:
            pickup_data: PICKUPS 通道数据
                [{"id": 50, "variant": 20, "sub_type": 1, "pos": {...}, ...}]
        """
        self.entities[EntityType.PICKUP].clear()
        count = 0
        for pickup in pickup_data:
            try:
                entity = RoomEntity(
                    entity_type=EntityType.PICKUP,
                    entity_id=pickup.get("id", 0),
                    position=Vector2D(
                        pickup.get("pos", {}).get("x", 0)
                        if "pos" in pickup
                        else pickup.get("x", 0),
                        pickup.get("pos", {}).get("y", 0)
                        if "pos" in pickup
                        else pickup.get("y", 0),
                    ),
                    variant_name=self._get_pickup_name(pickup.get("variant", 0)),
                    state=pickup.get("sub_type", 0),
                    distance=pickup.get("distance", 0.0),
                    radius=15.0,
                    is_active=True,
                    extra_data={
                        "pickup_variant": pickup.get("variant", 0),
                        "price": pickup.get("price", 0),
                        "shop_id": pickup.get("shop_item_id", -1),
                    },
                )
                self.entities[EntityType.PICKUP].append(entity)
                count += 1
            except (ValueError, TypeError) as e:
                logger.warning(f"[GameMap] Failed to parse pickup: {e}")

        logger.debug(f"[GameMap] Updated {count} pickups")

    def _get_pickup_name(self, variant: int) -> str:
        """获取拾取物名称"""
        pickup_names = {
            10: "HEART",
            12: "COIN",
            15: "KEY",
            17: "BOMB",
            20: "COLLECTIBLE",
            21: "SHOP_ITEM",
            22: "ENDING",
        }
        return pickup_names.get(variant, f"UNKNOWN_{variant}")

    def update_bombs(self, bomb_data: List[Dict[str, Any]]):
        """更新炸弹数据

        Args:
            bomb_data: BOMBS 通道数据
                [{"id": 30, "variant_name": "NORMAL", "timer": 60, "radius": 80, "pos": {...}}, ...]

        炸弹危险判定逻辑:
        - TROLL/MEGA_TROLL (即时爆炸): 威胁等级 CRITICAL
        - 计时器 < 30 帧: 威胁等级 HIGH
        - 计时器 < 60 帧: 威胁等级 MEDIUM
        - 爆炸半径内危险
        """
        self.entities[EntityType.BOMB].clear()
        count = 0
        for bomb in bomb_data:
            try:
                # 计算危险等级
                timer = bomb.get("timer", 90)
                variant_name = bomb.get("variant_name", "")
                explosion_radius = bomb.get("explosion_radius", bomb.get("radius", 80))

                # 特殊炸弹类型（立即爆炸）
                is_instant = variant_name in ["TROLL", "MEGA_TROLL", "HOT"]

                # 危险等级基于计时器
                if is_instant:
                    danger_level = 1.0  # 立即爆炸，最高级别
                elif timer < 30:
                    danger_level = 0.8  # 即将爆炸
                elif timer < 60:
                    danger_level = 0.5  # 中等危险
                else:
                    danger_level = 0.2  # 低危险

                entity = RoomEntity(
                    entity_type=EntityType.BOMB,
                    entity_id=bomb.get("id", 0),
                    position=Vector2D(
                        bomb.get("pos", {}).get("x", 0), bomb.get("pos", {}).get("y", 0)
                    ),
                    variant_name=variant_name,
                    state=timer,  # 使用 timer 作为 state
                    distance=bomb.get("distance", 0.0),
                    radius=explosion_radius,
                    is_active=True,
                    extra_data={
                        "timer": timer,
                        "explosion_radius": explosion_radius,
                        "is_player_bomb": bomb.get("is_player_bomb", False),
                        "danger_level": danger_level,
                        "is_instant": is_instant,
                    },
                )
                self.entities[EntityType.BOMB].append(entity)
                count += 1
            except (ValueError, TypeError) as e:
                logger.warning(f"[GameMap] Failed to parse bomb: {e}")

        logger.debug(f"[GameMap] Updated {count} bombs")

    def get_entities_by_type(self, entity_type: EntityType) -> List[RoomEntity]:
        """按类型获取实体列表"""
        return self.entities.get(entity_type, [])

    def get_all_entities(self) -> List[RoomEntity]:
        """获取所有实体"""
        all_entities = []
        for entity_list in self.entities.values():
            all_entities.extend(entity_list)
        return all_entities

    def _is_edge_tile(self, gx: int, gy: int) -> bool:
        """检查是否是边界格子（L型房间的边缘必须是实际房间区域）"""
        return gx == 0 or gx == self.width - 1 or gy == 0 or gy == self.height - 1

    def _create_default_walls(
        self, door_positions: Optional[Set[Tuple[int, int]]] = None
    ):
        """创建默认墙壁边界

        Args:
            door_positions: 门的位置集合，用于跳过门位置的墙壁创建
        """
        if door_positions is None:
            door_positions = set()
        for gx in range(self.width):
            self.grid[(gx, 0)] = TileType.WALL
            self.grid[(gx, self.height - 1)] = TileType.WALL
        for gy in range(self.height):
            self.grid[(0, gy)] = TileType.WALL
            self.grid[(self.width - 1, gy)] = TileType.WALL

        # 添加静态障碍物
        for gx in range(self.width):
            for gy in range(self.height):
                if self.grid.get((gx, gy)) == TileType.WALL:
                    self.static_obstacles.add((gx, gy))

    def add_dynamic_obstacle(
        self,
        position: Vector2D,
        radius: float,
        obstacle_type: str = "generic",
        entity_id: Optional[int] = None,
    ):
        """添加动态障碍物（敌人、投射物等）

        Args:
            position: 位置
            radius: 碰撞半径
            obstacle_type: 障碍物类型
            entity_id: 实体ID，如果提供则存储到字典中用于增量更新
        """
        obstacle = Obstacle(
            position=position,
            radius=radius,
            is_dynamic=True,
            obstacle_type=obstacle_type,
        )
        self.dynamic_obstacles.append(obstacle)
        if entity_id is not None:
            self.dynamic_obstacles_dict[entity_id] = obstacle

    def remove_dynamic_obstacle(self, position: Vector2D, radius: float):
        """移除动态障碍物"""
        to_remove = None
        for obs in self.dynamic_obstacles:
            if obs.position.distance_to(position) < 1.0:
                to_remove = obs
                break

        if to_remove:
            self.dynamic_obstacles.remove(to_remove)

    def clear_dynamic_obstacles(self):
        """清除所有动态障碍物"""
        self.dynamic_obstacles.clear()
        self.dynamic_obstacles_dict.clear()

    def update_dynamic_obstacles(
        self, enemies: Dict[int, EnemyData], projectiles: Dict[int, ProjectileData]
    ):
        """更新动态障碍物（增量更新）

        避免每次全量清除和重建，提高性能。
        """
        current_ids: Set[int] = set()

        # 更新敌人
        for enemy_id, enemy in enemies.items():
            if enemy.hp > 0:
                current_ids.add(enemy_id)
                if enemy_id in self.dynamic_obstacles_dict:
                    # 更新现有障碍物位置
                    obs = self.dynamic_obstacles_dict[enemy_id]
                    obs.position = enemy.position
                    obs.radius = 15.0
                else:
                    # 创建新障碍物
                    self.add_dynamic_obstacle(
                        position=enemy.position,
                        radius=15.0,
                        obstacle_type="enemy",
                        entity_id=enemy_id,
                    )

        # 更新敌方投射物
        for proj_id, proj in projectiles.items():
            if proj.is_enemy:
                current_ids.add(proj_id)
                if proj_id in self.dynamic_obstacles_dict:
                    obs = self.dynamic_obstacles_dict[proj_id]
                    obs.position = proj.position
                    obs.radius = proj.size
                else:
                    self.add_dynamic_obstacle(
                        position=proj.position,
                        radius=proj.size,
                        obstacle_type="projectile",
                        entity_id=proj_id,
                    )

        # 移除已消失的实体
        to_remove = []
        for entity_id in self.dynamic_obstacles_dict:
            if entity_id not in current_ids:
                to_remove.append(entity_id)
        for entity_id in to_remove:
            del self.dynamic_obstacles_dict[entity_id]

        # 同步列表
        self.dynamic_obstacles.clear()
        self.dynamic_obstacles.extend(self.dynamic_obstacles_dict.values())

    def add_danger_zone(
        self,
        center: Vector2D,
        radius: float,
        danger_type: str = "generic",
        intensity: float = 1.0,
        estimated_frames: int = 60,
    ):
        """添加危险区域"""
        zone = DangerZone(
            center=center,
            radius=radius,
            danger_type=danger_type,
            intensity=intensity,
            estimated_frames=estimated_frames,
        )
        self.danger_zones.append(zone)

    def clear_danger_zones(self):
        """清除危险区域"""
        self.danger_zones.clear()

    def is_obstacle(self, position: Vector2D, margin: float = 0) -> bool:
        """
        检查位置是否有障碍物

        Args:
            position: 像素坐标
            margin: 额外边距

        Returns:
            是否有障碍物
        """
        # 检查是否超出地图边界
        if not self.is_in_bounds(position):
            return True

        # 检查静态障碍物
        if self._has_static_obstacle(position, margin):
            return True

        # 检查动态障碍物
        if self._has_dynamic_obstacle(position, margin):
            return True

        return False

    def is_in_bounds(self, position: Vector2D, margin: float = 15.0) -> bool:
        """检查位置是否在地图边界内且属于房间区域

        对于L型房间，还需要检查位置是否在房间的实际区域内（不是虚空）

        DEBUG: margin 默认为 15px，基于 analyzed_rooms 分析:
        - 玩家位置 x 范围: ~70-570 (左墙 60，间距 ~10-15px)
        - 玩家位置 y 范围: ~150-410 (上墙 140，间距 ~10-15px)
        - 使用 15px 边距更准确（20px 可能过于保守）

        Args:
            position: 像素坐标
            margin: 边距（默认 15px）
        """
        # DEBUG: Use configurable margin based on analysis findings
        effective_margin = getattr(self, "_bounds_margin", margin)

        # 首先检查像素边界
        if not (
            effective_margin <= position.x <= self.pixel_width - effective_margin
            and effective_margin <= position.y <= self.pixel_height - effective_margin
        ):
            logger.debug(
                f"[GameMap] is_in_bounds=False: pos={position}, margin={effective_margin}, "
                f"bounds=({effective_margin}, {self.pixel_width - effective_margin}) x "
                f"({effective_margin}, {self.pixel_height - effective_margin})"
            )
            return False

        # 对于简单房间（无VOID），直接返回True
        if not self.void_tiles:
            return True

        # 检查是否是虚空区域（L型房间的缺口）
        grid_x, grid_y = self._get_grid_coords(position)
        if (grid_x, grid_y) in self.void_tiles:
            logger.debug(
                f"[GameMap] is_in_bounds=False: VOID tile at ({grid_x}, {grid_y})"
            )
            return False

        return True

    def _get_grid_coords(self, position: Vector2D) -> Tuple[int, int]:
        """获取位置对应的网格坐标"""
        gx = int(position.x / self.grid_size)
        gy = int(position.y / self.grid_size)
        return (gx, gy)

    def _has_static_obstacle(self, position: Vector2D, margin: float) -> bool:
        """检查静态障碍物"""
        gx, gy = self._get_grid_coords(position)

        # 检查中心点
        if self.grid.get((gx, gy)) == TileType.WALL:
            return True

        # 检查边缘（考虑碰撞半径）
        points_to_check = [
            (position.x - margin, position.y),
            (position.x + margin, position.y),
            (position.x, position.y - margin),
            (position.x, position.y + margin),
        ]

        for x, y in points_to_check:
            check_gx = int(x / self.grid_size)
            check_gy = int(y / self.grid_size)
            if self.grid.get((check_gx, check_gy)) == TileType.WALL:
                return True

        return False

    def _has_dynamic_obstacle(self, position: Vector2D, margin: float) -> bool:
        """检查动态障碍物"""
        for obs in self.dynamic_obstacles:
            if obs.intersects(position, margin):
                return True
        return False

    def get_nearest_walkable_position(
        self, target: Vector2D, search_radius: float = 100.0
    ) -> Optional[Vector2D]:
        """
        获取最近的可行走位置

        Args:
            target: 目标位置
            search_radius: 搜索半径

        Returns:
            最近的可行走位置，或None
        """
        # 优先检查目标位置本身
        if not self.is_obstacle(target):
            return target

        # 搜索周围位置
        angles = [i * math.pi / 4 for i in range(8)]  # 8个方向

        for radius in range(10, int(search_radius), 10):
            for angle in angles:
                x = target.x + radius * math.cos(angle)
                y = target.y + radius * math.sin(angle)
                candidate = Vector2D(x, y)

                if not self.is_obstacle(candidate):
                    return candidate

        return None

    def get_path_to(
        self, start: Vector2D, end: Vector2D, max_path_length: int = 100
    ) -> Optional[List[Vector2D]]:
        """
        获取到目标的简单路径（直线，无障碍检查）

        Args:
            start: 起始位置
            end: 目标位置
            max_path_length: 最大路径长度

        Returns:
            路径点列表，或None
        """
        direction = end - start
        distance = direction.magnitude()

        if distance == 0:
            return [start]

        direction = direction / distance

        # 简单的步进路径
        path = [start]
        step_size = self.grid_size / 2  # 半个网格

        for i in range(1, max_path_length + 1):
            new_pos = start + direction * (step_size * i)
            path.append(new_pos)

            if new_pos.distance_to(end) < step_size:
                break

            if not self.is_in_bounds(new_pos):
                break

        return path

    def get_safe_positions(
        self,
        player_pos: Vector2D,
        min_distance: float = 100.0,
        max_distance: float = 300.0,
        count: int = 5,
    ) -> List[Vector2D]:
        """
        获取安全位置列表

        用于躲避时寻找安全位置。

        Args:
            player_pos: 玩家当前位置
            min_distance: 最小距离
            max_distance: 最大距离
            count: 返回数量

        Returns:
            安全位置列表
        """
        safe_positions = []

        # 在圆周上采样
        angles = [i * 2 * math.pi / count for i in range(count)]

        for angle in angles:
            for distance in range(int(min_distance), int(max_distance), 20):
                x = player_pos.x + distance * math.cos(angle)
                y = player_pos.y + distance * math.sin(angle)
                pos = Vector2D(x, y)

                if self.is_in_bounds(pos) and not self.is_obstacle(pos, margin=15.0):
                    safe_positions.append(pos)
                    break

        return safe_positions

    def get_danger_level(self, position: Vector2D) -> float:
        """
        获取位置的 danger_level

        Returns:
            危险等级 0-1
        """
        max_danger = 0.0

        for zone in self.danger_zones:
            distance = position.distance_to(zone.center)
            if distance < zone.radius:
                # 越靠近中心越危险
                danger = (1 - distance / zone.radius) * zone.intensity
                max_danger = max(max_danger, danger)

        return max_danger

    def update(
        self, enemies: Dict[int, EnemyData], projectiles: Dict[int, ProjectileData]
    ):
        """更新地图的动态部分"""
        self.update_dynamic_obstacles(enemies, projectiles)


class SpatialQuery:
    """空间查询工具

    提供高效的空间查询功能。
    """

    def __init__(self, game_map: GameMap):
        self.game_map = game_map

    def get_entities_in_range(
        self, position: Vector2D, radius: float, entities: Dict[int, Any]
    ) -> List[Any]:
        """
        获取范围内的实体

        Args:
            position: 中心位置
            radius: 查询半径
            entities: 实体字典

        Returns:
            范围内的实体列表
        """
        result = []
        for entity in entities.values():
            if entity.position.distance_to(position) <= radius:
                result.append(entity)
        return result

    def get_nearest_entity(
        self, position: Vector2D, entities: Dict[int, Any]
    ) -> Optional[Any]:
        """获取最近的实体"""
        if not entities:
            return None

        min_dist = float("inf")
        nearest = None

        for entity in entities.values():
            dist = entity.position.distance_to(position)
            if dist < min_dist:
                min_dist = dist
                nearest = entity

        return nearest

    def get_entities_in_sector(
        self,
        position: Vector2D,
        direction: Vector2D,
        angle: float,
        radius: float,
        entities: Dict[int, Any],
    ) -> List[Any]:
        """
        获取扇形区域内的实体

        Args:
            position: 中心位置
            direction: 方向向量（归一化）
            angle: 扇形角度（弧度）
            radius: 查询半径
            entities: 实体字典

        Returns:
            扇形区域内的实体
        """
        result = []
        cos_half_angle = math.cos(angle / 2)

        for entity in entities.values():
            to_entity = entity.position - position
            dist = to_entity.magnitude()

            if dist > radius:
                continue

            # 检查角度
            if dist > 0:
                to_entity_normalized = to_entity / dist
                dot = direction.dot(to_entity_normalized)
                if dot >= cos_half_angle:
                    result.append(entity)

        return result

    def find_line_of_sight(self, start: Vector2D, end: Vector2D) -> bool:
        """
        检查两点之间是否有视线（直线无障碍）

        Args:
            start: 起始位置
            end: 结束位置

        Returns:
            是否有视线
        """
        direction = end - start
        distance = direction.magnitude()

        if distance == 0:
            return True

        direction = direction / distance

        # 步进检查
        step_size = self.game_map.grid_size / 4
        steps = int(distance / step_size)

        for i in range(steps + 1):
            check_pos = start + direction * (step_size * i)
            if self.game_map.is_obstacle(check_pos):
                return False

        return True

    def find_clear_shot_positions(
        self, shooter_pos: Vector2D, target_pos: Vector2D, enemies: Dict[int, EnemyData]
    ) -> List[Vector2D]:
        """
        寻找可以射击目标的清晰位置

        Args:
            shooter_pos: 射击者位置
            target_pos: 目标位置
            enemies: 敌人字典

        Returns:
            可以射击的位置列表
        """
        positions = []

        # 考虑在目标周围采样
        sample_dist = 50.0
        angles = [i * math.pi / 4 for i in range(8)]

        for angle in angles:
            # 从目标向外采样
            for dist in [50, 100, 150]:
                # 尝试位置
                test_pos = target_pos + Vector2D(
                    dist * math.cos(angle), dist * math.sin(angle)
                )

                if not self.game_map.is_in_bounds(test_pos):
                    continue

                if self.game_map.is_obstacle(test_pos):
                    continue

                # 检查从这个位置能否看到目标
                if self.find_line_of_sight(test_pos, target_pos):
                    positions.append(test_pos)

        return positions


class EnvironmentModel:
    """环境模型

    整合GameMap和SpatialQuery，提供完整的环境建模功能。
    """

    def __init__(self, grid_size: float = 40.0, width: int = 13, height: int = 7):
        self.game_map = GameMap(grid_size, width, height)
        self.spatial_query = SpatialQuery(self.game_map)

        # 玩家碰撞半径
        self.player_radius = 15.0

        # 当前房间索引
        self.current_room_index = -1

    def update_room(
        self,
        room_info: RoomInfo,
        enemies: Dict[int, EnemyData],
        projectiles: Dict[int, ProjectileData],
        room_layout: Optional[Dict[str, Any]] = None,
        entity_data: Optional[Dict[str, Any]] = None,
    ):
        """更新环境模型

        Args:
            room_info: 房间信息
            enemies: 敌人数据
            projectiles: 投射物数据
            room_layout: ROOM_LAYOUT原始数据（支持L型房间）
            entity_data: 其他实体数据（可选）
                {
                    "FIRE_HAZARDS": [...],
                    "BUTTONS": {...},
                    "DESTRUCTIBLES": [...],
                    "INTERACTABLES": [...],
                    "PICKUPS": [...],
                }
        """
        # 如果房间变化了，或者第一次有布局数据，重置地图
        # 注意：初始房间的room_index可能是-1，需要特殊处理
        room_changed = room_info and room_info.room_index != self.current_room_index
        first_layout = (
            room_layout
            and self.current_room_index == -1
            and self.game_map.grid_size == 40.0
        )

        if room_changed or first_layout:
            self.current_room_index = room_info.room_index if room_info else -1
            if room_layout:
                # Extract grid_size from layout data (135 or 252 in replay data)
                layout_grid_size = room_layout.get("grid_size", 40.0)
                self.game_map.update_from_room_layout(
                    room_info, room_layout, layout_grid_size
                )
            else:
                self.game_map.update_from_room_info(room_info)

        # 更新动态障碍物
        self.game_map.update_dynamic_obstacles(enemies, projectiles)

        # 更新房间实体（如果提供）
        if entity_data:
            self.game_map.clear_entities()

            if "FIRE_HAZARDS" in entity_data:
                self.game_map.update_fire_hazards(entity_data["FIRE_HAZARDS"])

            if "BUTTONS" in entity_data:
                self.game_map.update_buttons(entity_data["BUTTONS"])

            if "DESTRUCTIBLES" in entity_data:
                self.game_map.update_destructibles(entity_data["DESTRUCTIBLES"])

            if "INTERACTABLES" in entity_data:
                self.game_map.update_interactables(entity_data["INTERACTABLES"])

            if "PICKUPS" in entity_data:
                self.game_map.update_pickups(entity_data["PICKUPS"])

    def is_safe(self, position: Vector2D) -> Tuple[bool, float]:
        """
        检查位置是否安全

        Returns:
            (是否安全, 危险等级)
        """
        # 检查障碍物
        if self.game_map.is_obstacle(position, self.player_radius):
            return False, 1.0

        # 检查危险区域
        danger_level = self.game_map.get_danger_level(position)

        return danger_level < 0.3, danger_level

    def get_safe_spot(
        self,
        near_position: Vector2D,
        min_distance: float = 50.0,
        max_distance: float = 200.0,
    ) -> Optional[Vector2D]:
        """获取附近的安全位置"""
        return self.game_map.get_nearest_walkable_position(near_position, max_distance)

    def find_escape_route(
        self, player_pos: Vector2D, threat_positions: List[Vector2D]
    ) -> List[Vector2D]:
        """
        寻找逃跑路线

        Args:
            player_pos: 玩家位置
            threat_positions: 威胁位置列表

        Returns:
            逃跑路径
        """
        # 简单策略：向威胁的反方向移动
        escape_direction = Vector2D(0, 0)

        for threat_pos in threat_positions:
            direction = player_pos - threat_pos
            dist = direction.magnitude()
            if dist > 0:
                escape_direction = escape_direction + (direction / dist)

        if escape_direction.magnitude() == 0:
            return []

        escape_direction = escape_direction.normalized()

        # 生成逃跑路径
        path = []
        step_size = 20.0
        max_steps = 20

        for i in range(1, max_steps + 1):
            new_pos = player_pos + escape_direction * (step_size * i)

            if not self.game_map.is_in_bounds(new_pos):
                break

            if self.game_map.is_obstacle(new_pos, self.player_radius):
                break

            path.append(new_pos)

        return path

    def get_cover_value(
        self, position: Vector2D, enemy_positions: List[Vector2D]
    ) -> float:
        """
        获取位置的掩体价值

        值越高表示越好的掩体位置。

        Args:
            position: 要评估的位置
            enemy_positions: 敌人位置列表

        Returns:
            掩体价值 0-1
        """
        if not enemy_positions:
            return 0.0

        # 简单策略：检查是否在敌人和房间中心的连线上
        room_center = Vector2D(
            self.game_map.pixel_width / 2, self.game_map.pixel_height / 2
        )

        # 检查到房间中心的路径上有多少障碍物
        if self.spatial_query.find_line_of_sight(position, room_center):
            return 0.3  # 能看到中心

        # 检查到各个敌人的视线
        visible_enemies = 0
        for enemy_pos in enemy_positions:
            if self.spatial_query.find_line_of_sight(position, enemy_pos):
                visible_enemies += 1

        if visible_enemies == 0:
            return 1.0  # 完全看不到敌人，最好的掩体

        if visible_enemies < len(enemy_positions) / 2:
            return 0.6  # 只能看到部分敌人

        return 0.1  # 能看到大部分敌人，掩体价值低

    def can_reach_position(self, start: Vector2D, end: Vector2D) -> bool:
        """检查是否能够到达目标位置"""
        if not self.game_map.is_in_bounds(end):
            return False

        if self.game_map.is_obstacle(end, self.player_radius):
            return False

        # 简单的视线检查
        return self.spatial_query.find_line_of_sight(start, end)

    def get_strategic_positions(
        self, player_pos: Vector2D, enemies: Dict[int, EnemyData]
    ) -> List[Vector2D]:
        """
        获取战略位置列表

        用于选择最佳的移动位置。

        Args:
            player_pos: 玩家当前位置
            enemies: 敌人字典

        Returns:
            按价值排序的位置列表
        """
        positions = []

        # 获取房间中心区域的位置
        center = Vector2D(self.game_map.pixel_width / 2, self.game_map.pixel_height / 2)

        # 在中心区域采样
        sample_radius = 100.0
        angles = [i * math.pi / 6 for i in range(12)]

        for angle in angles:
            pos = Vector2D(
                center.x + sample_radius * math.cos(angle),
                center.y + sample_radius * math.sin(angle),
            )

            if self.game_map.is_in_bounds(pos) and not self.game_map.is_obstacle(
                pos, self.player_radius
            ):
                # 计算位置价值
                value = self._calculate_position_value(pos, player_pos, enemies)
                positions.append((pos, value))

        # 排序并返回
        positions.sort(key=lambda x: x[1], reverse=True)
        return [p[0] for p in positions[:5]]

    def _calculate_position_value(
        self, position: Vector2D, player_pos: Vector2D, enemies: Dict[int, EnemyData]
    ) -> float:
        """计算位置价值"""
        value = 0.0

        # 距离因素：不要太远也不要太近
        dist_to_player = position.distance_to(player_pos)
        if 50 < dist_to_player < 200:
            value += 0.3
        elif dist_to_player <= 50:
            value += 0.1

        # 掩体因素
        enemy_positions = [e.position for e in enemies.values() if e.hp > 0]
        cover_value = self.get_cover_value(position, enemy_positions)
        value += cover_value * 0.4

        # 距离敌人适中
        if enemies:
            min_enemy_dist = min(
                position.distance_to(e.position) for e in enemies.values()
            )
            if 100 < min_enemy_dist < 300:
                value += 0.3

        return value
