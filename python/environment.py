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

        # 像素尺寸
        self.pixel_width = width * grid_size
        self.pixel_height = height * grid_size

        # 网格数据: (grid_x, grid_y) -> TileType
        self.grid: Dict[Tuple[int, int], TileType] = {}

        # 静态障碍物
        self.static_obstacles: Set[Tuple[int, int]] = set()

        # 动态障碍物
        self.dynamic_obstacles: List[Obstacle] = []

        # 危险区域
        self.danger_zones: List[DangerZone] = []

        # 虚空区域（L型房间的缺口），这些位置不属于房间
        self.void_tiles: Set[Tuple[int, int]] = set()

        # 初始化为空地图
        self._initialize_empty_map()

    def _initialize_empty_map(self):
        """初始化空地图"""
        for gx in range(self.width):
            for gy in range(self.height):
                self.grid[(gx, gy)] = TileType.EMPTY

    def update_from_room_info(self, room_info: RoomInfo):
        """从房间信息更新地图（简化版，无布局数据时使用）"""
        if room_info is None:
            return

        # 更新地图尺寸
        if room_info.grid_width > 0:
            self.width = room_info.grid_width
        if room_info.grid_height > 0:
            self.height = room_info.grid_height

        # 像素尺寸优先使用 RoomInfo 中的值，如果为 0 则从网格计算
        if room_info.pixel_width > 0:
            self.pixel_width = room_info.pixel_width
        else:
            self.pixel_width = self.width * self.grid_size

        if room_info.pixel_height > 0:
            self.pixel_height = room_info.pixel_height
        else:
            self.pixel_height = self.height * self.grid_size

        # 重新初始化网格
        self.grid.clear()
        self.static_obstacles.clear()
        self._initialize_empty_map()

        # 默认创建一个空房间（墙壁边界）
        self._create_default_walls()

    def update_from_room_layout(
        self, room_info: RoomInfo, layout_data: Dict[str, Any], grid_size: float = 40.0
    ):
        """从ROOM_LAYOUT数据更新地图（支持L型房间等复杂形状）

        Args:
            room_info: 房间信息
            layout_data: ROOM_LAYOUT原始数据，包含grid和doors
            grid_size: 网格大小（像素）
        """
        if layout_data is None:
            self.update_from_room_info(room_info)
            return

        # 更新地图尺寸
        if room_info.grid_width > 0:
            self.width = room_info.grid_width
        if room_info.grid_height > 0:
            self.height = room_info.grid_height

        # 更新网格大小（关键修复：实际存储新值）
        self.grid_size = grid_size

        # 计算像素尺寸
        self.pixel_width = self.width * grid_size
        self.pixel_height = self.height * grid_size

        # 清空现有数据
        self.grid.clear()
        self.static_obstacles.clear()
        self.void_tiles.clear()

        # 初始化所有格子为EMPTY（ROOM_LAYOUT.grid只包含特殊格子，其他都是地板）
        for gx in range(self.width):
            for gy in range(self.height):
                self.grid[(gx, gy)] = TileType.EMPTY

        # 解析网格数据
        grid_data = layout_data.get("grid", {})
        if isinstance(grid_data, dict):
            # grid是字典格式: {"0": {"x": 64, "y": 64, "type": 1000, "collision": 1}, ...}
            for idx_str, tile_data in grid_data.items():
                tile_x = tile_data.get("x", 0)
                tile_y = tile_data.get("y", 0)
                collision = tile_data.get("collision", 0)
                tile_type = tile_data.get("type", 0)

                # 转换为网格坐标
                gx = int(tile_x / grid_size)
                gy = int(tile_y / grid_size)

                # 检查是否在有效范围内
                if 0 <= gx < self.width and 0 <= gy < self.height:
                    if collision > 0:
                        # 有碰撞，标记为墙壁
                        self.grid[(gx, gy)] = TileType.WALL
                        self.static_obstacles.add((gx, gy))
                    # 无碰撞的不处理（保持EMPTY）

        # 对于L型房间，需要识别VOID区域
        # 如果一个格子不在边界上且没有对应的grid数据，则可能是VOID
        # 但由于ROOM_LAYOUT.grid只包含特殊格子，我们使用启发式方法：
        # 1. 边界上的格子必须是EMPTY（门的位置）
        # 2. 检查是否有格子同时满足：非边界 + 无数据
        # 由于数据稀疏，这个检查对稀疏数据不准确，暂时禁用VOID标记
        # 后续可以通过 room_shape 来精确判断

    def _is_edge_tile(self, gx: int, gy: int) -> bool:
        """检查是否是边界格子（L型房间的边缘必须是实际房间区域）"""
        return gx == 0 or gx == self.width - 1 or gy == 0 or gy == self.height - 1

    def _create_default_walls(self):
        """创建默认墙壁边界"""
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
        self, position: Vector2D, radius: float, obstacle_type: str = "generic"
    ):
        """添加动态障碍物（敌人、投射物等）"""
        obstacle = Obstacle(
            position=position,
            radius=radius,
            is_dynamic=True,
            obstacle_type=obstacle_type,
        )
        self.dynamic_obstacles.append(obstacle)

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

    def update_dynamic_obstacles(
        self, enemies: Dict[int, EnemyData], projectiles: Dict[int, ProjectileData]
    ):
        """更新动态障碍物"""
        self.clear_dynamic_obstacles()

        # 添加敌人
        for enemy_id, enemy in enemies.items():
            if enemy.hp > 0:
                self.add_dynamic_obstacle(
                    position=enemy.position,
                    radius=15.0,  # 默认碰撞半径
                    obstacle_type="enemy",
                )

        # 添加敌方投射物
        for proj_id, proj in projectiles.items():
            if proj.is_enemy:
                self.add_dynamic_obstacle(
                    position=proj.position,
                    radius=proj.size,
                    obstacle_type="projectile",
                )

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

    def is_in_bounds(self, position: Vector2D) -> bool:
        """检查位置是否在地图边界内且属于房间区域

        对于L型房间，还需要检查位置是否在房间的实际区域内（不是虚空）
        """
        # 考虑碰撞半径，留一些边距
        margin = 20.0

        # 首先检查像素边界
        if not (
            margin <= position.x <= self.pixel_width - margin
            and margin <= position.y <= self.pixel_height - margin
        ):
            return False

        # 对于简单房间（无VOID），直接返回True
        if not self.void_tiles:
            return True

        # 检查是否是虚空区域（L型房间的缺口）
        grid_x, grid_y = self._get_grid_coords(position)
        if (grid_x, grid_y) in self.void_tiles:
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
    ):
        """更新环境模型

        Args:
            room_info: 房间信息
            enemies: 敌人数据
            projectiles: 投射物数据
            room_layout: ROOM_LAYOUT原始数据（支持L型房间）
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
