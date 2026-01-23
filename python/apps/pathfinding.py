"""
SocketBridge 路径规划模块

实现动态环境下的路径规划算法：
- A* 寻路算法
- 动态障碍物处理
- 路径平滑处理
- 分段路径规划
"""

import heapq
import math
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging

from models import Vector2D

logger = logging.getLogger("Pathfinding")


class NodeState(Enum):
    """节点状态"""

    OPEN = "open"
    CLOSED = "closed"
    UNVISITED = "unvisited"


@dataclass(order=True)
class PathNode:
    """路径节点"""

    priority: float  # f_score
    g_score: float = field(compare=False)
    h_score: float = field(compare=False)
    position: Tuple[int, int] = field(compare=False)
    parent: Optional["PathNode"] = field(compare=False, default=None)

    @property
    def f_score(self) -> float:
        return self.g_score + self.h_score


@dataclass
class PathfindingConfig:
    """寻路配置"""

    grid_size: float = 40.0  # 网格大小
    allow_diagonal: bool = True  # 允许对角移动
    heuristic_weight: float = 1.0  # 启发函数权重

    # 代价权重
    movement_cost: float = 1.0  # 普通移动代价
    diagonal_cost: float = 1.414  # 对角移动代价
    danger_cost: float = 5.0  # 危险区域额外代价

    # 路径平滑
    smoothing_enabled: bool = True
    smoothing_max_angle: float = math.pi / 3  # 最大转向角

    # 性能限制
    max_iterations: int = 1000  # 最大迭代次数
    max_path_length: int = 50  # 最大路径长度


class AStarPathfinder:
    """A* 寻路器

    实现标准A*算法，支持动态障碍物。
    """

    def __init__(self, config: PathfindingConfig = None):
        self.config = config or PathfindingConfig()
        self._width = 13  # 默认房间宽度
        self._height = 7  # 默认房间高度
        self._obstacles: Set[Tuple[int, int]] = set()
        self._danger_zones: Dict[Tuple[int, int], float] = {}

    def set_map_size(self, width: int, height: int):
        """设置地图尺寸"""
        self._width = width
        self._height = height

    def set_obstacles(self, obstacles: Set[Tuple[int, int]]):
        """设置障碍物"""
        self._obstacles = obstacles.copy()

    def set_danger_zones(self, danger_zones: Dict[Tuple[int, int], float]):
        """设置危险区域"""
        self._danger_zones = danger_zones.copy()

    def add_dynamic_obstacle(self, position: Vector2D, radius: float):
        """添加动态障碍物"""
        grid_x = int(position.x / self.config.grid_size)
        grid_y = int(position.y / self.config.grid_size)

        # 标记周围网格为障碍
        radius_grids = int(radius / self.config.grid_size) + 1
        for dx in range(-radius_grids, radius_grids + 1):
            for dy in range(-radius_grids, radius_grids + 1):
                gx = grid_x + dx
                gy = grid_y + dy
                if 0 <= gx < self._width and 0 <= gy < self._height:
                    self._obstacles.add((gx, gy))

    def clear_dynamic_obstacles(self):
        """清除动态障碍物"""
        self._obstacles.clear()
        self._danger_zones.clear()

    def find_path(
        self, start: Vector2D, goal: Vector2D, obstacles: Set[Tuple[int, int]] = None
    ) -> Optional[List[Vector2D]]:
        """
        寻找路径

        Args:
            start: 起始位置（像素坐标）
            goal: 目标位置（像素坐标）
            obstacles: 额外的障碍物

        Returns:
            路径点列表，或None（无路径）
        """
        # 转换为网格坐标
        start_grid = self._pixel_to_grid(start)
        goal_grid = self._pixel_to_grid(goal)

        # 检查起点和终点
        if not self._is_valid_position(start_grid):
            logger.warning(f"Invalid start position: {start_grid}")
            return None

        if not self._is_valid_position(goal_grid):
            logger.warning(f"Invalid goal position: {goal_grid}")
            return None

        if start_grid == goal_grid:
            return [start]

        # 合并障碍物
        all_obstacles = self._obstacles.copy()
        if obstacles:
            all_obstacles.update(obstacles)

        # A* 搜索
        path = self._astar_search(start_grid, goal_grid, all_obstacles)

        if path is None:
            logger.debug(f"No path found from {start_grid} to {goal_grid}")
            return None

        # 转换回像素坐标
        pixel_path = self._grid_to_pixel_path(path)

        # 路径平滑
        if self.config.smoothing_enabled:
            pixel_path = self._smooth_path(pixel_path)

        return pixel_path

    def _pixel_to_grid(self, pos: Vector2D) -> Tuple[int, int]:
        """像素坐标转网格坐标"""
        return (int(pos.x / self.config.grid_size), int(pos.y / self.config.grid_size))

    def _grid_to_pixel(self, grid_pos: Tuple[int, int]) -> Vector2D:
        """网格坐标转像素坐标（中心点）"""
        gx, gy = grid_pos
        return Vector2D(
            gx * self.config.grid_size + self.config.grid_size / 2,
            gy * self.config.grid_size + self.config.grid_size / 2,
        )

    def _grid_to_pixel_path(self, path: List[Tuple[int, int]]) -> List[Vector2D]:
        """网格路径转像素路径"""
        return [self._grid_to_pixel(pos) for pos in path]

    def _is_valid_position(self, pos: Tuple[int, int]) -> bool:
        """检查位置是否有效"""
        x, y = pos
        return (
            0 <= x < self._width
            and 0 <= y < self._height
            and pos not in self._obstacles
        )

    def _get_neighbors(
        self, pos: Tuple[int, int], obstacles: Set[Tuple[int, int]]
    ) -> List[Tuple[int, int]]:
        """获取相邻节点"""
        neighbors = []

        # 8方向移动
        directions = [
            (0, -1),  # 上
            (1, -1),  # 右上
            (1, 0),  # 右
            (1, 1),  # 右下
            (0, 1),  # 下
            (-1, 1),  # 左下
            (-1, 0),  # 左
            (-1, -1),  # 左上
        ]

        for dx, dy in directions:
            nx, ny = pos[0] + dx, pos[1] + dy
            neighbor = (nx, ny)

            if self._is_valid_position(neighbor) and neighbor not in obstacles:
                # 检查对角移动是否被阻挡
                if dx != 0 and dy != 0:  # 对角移动
                    if (pos[0] + dx, pos[1]) in obstacles or (
                        pos[0],
                        pos[1] + dy,
                    ) in obstacles:
                        continue

                neighbors.append(neighbor)

        return neighbors

    def _heuristic(self, pos: Tuple[int, int], goal: Tuple[int, int]) -> float:
        """启发函数（欧几里得距离）"""
        return (
            math.sqrt((pos[0] - goal[0]) ** 2 + (pos[1] - goal[1]) ** 2)
            * self.config.heuristic_weight
        )

    def _astar_search(
        self,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        obstacles: Set[Tuple[int, int]],
    ) -> Optional[List[Tuple[int, int]]]:
        """A* 搜索算法"""
        # 初始化
        open_set: List[PathNode] = []
        closed_set: Set[Tuple[int, int]] = set()
        g_scores: Dict[Tuple[int, int], float] = {start: 0}

        start_node = PathNode(
            priority=self._heuristic(start, goal),
            g_score=0,
            h_score=self._heuristic(start, goal),
            position=start,
        )
        heapq.heappush(open_set, start_node)

        iterations = 0

        while open_set and iterations < self.config.max_iterations:
            iterations += 1

            # 取出f值最小的节点
            current = heapq.heappop(open_set)
            current_pos = current.position

            # 到达目标
            if current_pos == goal:
                return self._reconstruct_path(current)

            # 跳过已处理的节点
            if current_pos in closed_set:
                continue

            closed_set.add(current_pos)

            # 探索邻居
            for neighbor in self._get_neighbors(current_pos, obstacles):
                if neighbor in closed_set:
                    continue

                # 计算g值
                is_diagonal = (
                    neighbor[0] != current_pos[0] and neighbor[1] != current_pos[1]
                )
                move_cost = (
                    self.config.diagonal_cost
                    if is_diagonal
                    else self.config.movement_cost
                )

                # 危险区域额外代价
                danger_extra = 0
                if neighbor in self._danger_zones:
                    danger_extra = (
                        self._danger_zones[neighbor] * self.config.danger_cost
                    )

                tentative_g = current.g_score + move_cost + danger_extra

                if tentative_g < g_scores.get(neighbor, float("inf")):
                    g_scores[neighbor] = tentative_g
                    h = self._heuristic(neighbor, goal)

                    neighbor_node = PathNode(
                        priority=tentative_g + h,
                        g_score=tentative_g,
                        h_score=h,
                        position=neighbor,
                        parent=current,
                    )
                    heapq.heappush(open_set, neighbor_node)

        return None

    def _reconstruct_path(self, end_node: PathNode) -> List[Tuple[int, int]]:
        """重建路径"""
        path = []
        current = end_node

        while current is not None:
            path.append(current.position)
            current = current.parent

        return list(reversed(path))

    def _smooth_path(self, path: List[Vector2D]) -> List[Vector2D]:
        """路径平滑处理"""
        if len(path) < 3:
            return path

        smoothed = [path[0]]

        i = 1
        while i < len(path) - 1:
            prev_point = smoothed[-1]
            curr_point = path[i]
            next_point = path[i + 1]

            # 计算角度
            v1 = curr_point - prev_point
            v2 = next_point - curr_point

            angle = self._angle_between(v1, v2)

            # 如果角度太大，保留当前点
            if abs(angle) > self.config.smoothing_max_angle:
                smoothed.append(curr_point)
                i += 1
            else:
                i += 1

        # 添加终点
        smoothed.append(path[-1])

        return smoothed

    def _angle_between(self, v1: Vector2D, v2: Vector2D) -> float:
        """计算两个向量之间的角度"""
        mag1 = v1.magnitude()
        mag2 = v2.magnitude()

        if mag1 == 0 or mag2 == 0:
            return 0

        dot = v1.x * v2.x + v1.y * v2.y
        cos_angle = dot / (mag1 * mag2)

        # 限制在 -1 到 1
        cos_angle = max(-1.0, min(1.0, cos_angle))

        return math.acos(cos_angle)


class DynamicPathPlanner:
    """动态路径规划器

    支持动态障碍物的实时重规划。
    """

    def __init__(self, config: PathfindingConfig = None):
        self.config = config or PathfindingConfig()
        self.astar = AStarPathfinder(config)
        self._current_path: List[Vector2D] = []
        self._path_index = 0
        self._replan_needed = False

    def plan_path(
        self, start: Vector2D, goal: Vector2D, obstacles: Set[Tuple[int, int]] = None
    ) -> Optional[List[Vector2D]]:
        """
        规划路径

        Args:
            start: 起始位置
            goal: 目标位置
            obstacles: 障碍物集合

        Returns:
            路径点列表
        """
        path = self.astar.find_path(start, goal, obstacles)

        if path:
            self._current_path = path
            self._path_index = 0
            self._replan_needed = False

        return path

    def get_next_waypoint(self) -> Optional[Vector2D]:
        """获取下一个路点"""
        if self._path_index < len(self._current_path):
            waypoint = self._current_path[self._path_index]
            self._path_index += 1
            return waypoint
        return None

    def has_reached_goal(
        self, current_pos: Vector2D, goal_tolerance: float = 20.0
    ) -> bool:
        """检查是否到达目标"""
        if not self._current_path:
            return True

        # 简单检查：距离最后一个路点足够近
        if self._current_path:
            last_point = self._current_path[-1]
            return current_pos.distance_to(last_point) < goal_tolerance
        return True

    def needs_replan(
        self,
        current_pos: Vector2D,
        dynamic_obstacles: List[Vector2D],
        obstacle_threshold: float = 30.0,
    ) -> bool:
        """检查是否需要重新规划"""
        if not self._current_path:
            return True

        # 检查路径上是否有障碍物
        for i in range(self._path_index, len(self._current_path)):
            path_point = self._current_path[i]

            for obs_pos in dynamic_obstacles:
                if path_point.distance_to(obs_pos) < obstacle_threshold:
                    self._replan_needed = True
                    return True

        return False

    def get_current_path(self) -> List[Vector2D]:
        """获取当前路径"""
        return self._current_path

    def clear_path(self):
        """清除当前路径"""
        self._current_path = []
        self._path_index = 0
        self._replan_needed = False


class PathExecutor:
    """路径执行器

    将路径转换为控制输出。
    """

    def __init__(self, config: PathfindingConfig = None):
        self.config = config or PathfindingConfig()
        self.planner = DynamicPathPlanner(config)

    def execute_path(
        self,
        current_pos: Vector2D,
        path: List[Vector2D],
        speed: float = 5.0,
    ) -> Tuple[float, float]:
        """
        执行路径，返回移动方向

        Args:
            current_pos: 当前位置
            path: 路径点列表
            speed: 移动速度

        Returns:
            (move_x, move_y) 控制输出
        """
        if not path:
            return (0.0, 0.0)

        # 找到最近的路点
        nearest_idx = 0
        min_dist = float("inf")

        for i, point in enumerate(path):
            dist = current_pos.distance_to(point)
            if dist < min_dist:
                min_dist = dist
                nearest_idx = i

        # 获取下一个路点
        next_idx = min(nearest_idx + 1, len(path) - 1)
        target = path[next_idx]

        # 计算方向
        direction = target - current_pos
        distance = direction.magnitude()

        if distance < 1.0:
            return (0.0, 0.0)

        # 归一化并应用速度
        move_x = (direction.x / distance) * speed
        move_y = (direction.y / distance) * speed

        # 限制在 -1 到 1
        move_x = max(-1.0, min(1.0, move_x))
        move_y = max(-1.0, min(1.0, move_y))

        return (move_x, move_y)

    def follow_path(
        self,
        current_pos: Vector2D,
        path: List[Vector2D],
        speed: float = 5.0,
    ) -> Tuple[float, float]:
        """
        沿路径移动

        Args:
            current_pos: 当前位置
            path: 路径点列表
            speed: 移动速度

        Returns:
            (move_x, move_y) 控制输出
        """
        return self.execute_path(current_pos, path, speed)
