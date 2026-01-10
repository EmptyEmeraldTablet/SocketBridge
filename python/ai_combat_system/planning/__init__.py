"""
规划模块 (Planning Module)

将意图转换为具体执行计划。

子模块:
- 路径规划器 (Path Planner): 动态避障A*、平滑路径生成、分段路径规划、备用路线计算
- 攻击规划器 (Attack Planner): 射击角度计算、预判射击、连击规划、特殊攻击模式
- 时序规划器 (Timing Planner): 动作序列编排、时间窗口计算、打断处理
- 风险管理器 (Risk Manager): 风险-收益权衡、安全边界设置、应急计划生成
"""

import math
import time
import heapq
import logging
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

from ..perception import (
    GameState,
    PlayerState,
    EnemyState,
    ProjectileState,
    RoomLayout,
    Obstacle,
    Vector2D,
    ThreatLevel,
)
from ..decision import ActionIntent, ActionType

logger = logging.getLogger("PlanningModule")


class PathSegmentType(Enum):
    """路径段类型"""

    DIRECT = "direct"  # 直接移动
    AVOID = "avoid"  # 规避障碍
    APPROACH = "approach"  # 接近目标
    RETREAT = "retreat"  # 撤退
    CIRCUITOUS = "circuitous"  # 绕行


@dataclass
class PathSegment:
    """路径段"""

    segment_type: PathSegmentType
    start_pos: Vector2D
    end_pos: Vector2D
    waypoints: List[Vector2D] = field(default_factory=list)

    # 预计时间
    estimated_frames: int = 10

    # 风险评估
    risk_level: float = 0.0  # 0-1
    safety_score: float = 1.0  # 0-1

    # 执行参数
    speed_factor: float = 1.0  # 速度因子
    can_interrupt: bool = True


@dataclass
class ExecutionPlan:
    """
    执行计划

    包含移动计划、射击计划、时序安排等。
    """

    # 行动信息
    action_intent: ActionIntent

    # 移动计划
    path_segments: List[PathSegment] = field(default_factory=list)
    total_estimated_frames: int = 0

    # 射击计划
    shoot_targets: List[Dict] = field(default_factory=list)
    shoot_schedule: List[Dict] = field(default_factory=list)  # [(frame, target), ...]

    # 时序安排
    timeline: List[Dict] = field(default_factory=list)  # [(frame, action), ...]

    # 备用计划
    fallback_plans: List["ExecutionPlan"] = field(default_factory=list)

    # 约束检查
    constraints: List[str] = field(default_factory=list)
    constraint_checks: Dict[str, bool] = field(default_factory=dict)

    # 风险评估
    overall_risk: float = 0.0
    success_probability: float = 1.0

    # 状态
    current_frame: int = 0
    is_complete: bool = False

    def to_dict(self) -> Dict:
        return {
            "action_type": self.action_intent.action_type.value,
            "total_frames": self.total_estimated_frames,
            "path_segments": len(self.path_segments),
            "shoot_targets": len(self.shoot_targets),
            "overall_risk": self.overall_risk,
            "success_probability": self.success_probability,
        }


@dataclass
class TimingWindow:
    """时间窗口"""

    start_frame: int
    end_frame: int
    duration_frames: int
    action_type: str
    priority: int
    requirements: List[str] = field(default_factory=list)
    can_extend: bool = False


@dataclass
class RiskAssessment:
    """风险评估"""

    overall_risk: float = 0.0

    # 风险因素
    collision_risk: float = 0.0
    threat_exposure: float = 0.0
    resource_cost: float = 0.0

    # 收益评估
    expected_gain: float = 0.0
    opportunity_cost: float = 0.0

    # 建议
    recommended_safety_margin: float = 0.2
    suggested_alternatives: List[str] = field(default_factory=list)


# ==================== 路径规划器 ====================


class PathPlanner:
    """
    路径规划器

    功能：
    - 动态避障A*（考虑移动惯性）
    - 平滑路径生成（避免急转弯）
    - 分段路径规划（长距离分阶段）
    - 备用路线计算（主路线受阻时）
    """

    def __init__(self, grid_size: float = 20.0):
        """
        初始化路径规划器

        Args:
            grid_size: 网格大小（用于离散化）
        """
        self.grid_size = grid_size

        # A*参数
        self.max_iterations = 500
        self.heuristic_weight = 1.0

        # 路径平滑参数
        self.smoothing_iterations = 3
        self.smoothing_weight = 0.1

        # 障碍物膨胀
        self.obstacle_padding = 10.0

        # 移动惯性
        self.inertia_weight = 0.2

    def plan_path(
        self,
        start: Vector2D,
        goal: Vector2D,
        game_state: GameState,
        obstacles: List[Obstacle] = None,
        current_velocity: Vector2D = None,
    ) -> PathSegment:
        """
        规划路径

        Args:
            start: 起始位置
            goal: 目标位置
            game_state: 游戏状态
            obstacles: 障碍物列表（可选）
            current_velocity: 当前速度（用于惯性）

        Returns:
            路径段
        """
        room = game_state.room
        if not room:
            # 无房间信息，直接返回直线
            return PathSegment(
                segment_type=PathSegmentType.DIRECT,
                start_pos=start,
                end_pos=goal,
                waypoints=[start, goal],
                estimated_frames=self._estimate_frames(start, goal),
            )

        # 获取障碍物
        if obstacles is None:
            obstacles = list(room.obstacles.values())

        # 离散化坐标
        start_grid = self._world_to_grid(start, room)
        goal_grid = self._world_to_grid(goal, room)

        # 检查是否在房间内
        if not room.is_inside_room(goal, self.grid_size):
            goal = self._clamp_to_room(goal, room)
            goal_grid = self._world_to_grid(goal, room)

        # A*寻路
        path = self._astar(start, goal, room, obstacles, start_grid, goal_grid)

        if not path:
            # 无法找到路径，返回直线
            return PathSegment(
                segment_type=PathSegmentType.DIRECT,
                start_pos=start,
                end_pos=goal,
                waypoints=[start, goal],
                estimated_frames=self._estimate_frames(start, goal),
                risk_level=0.5,  # 高风险（无路径）
            )

        # 转换回世界坐标
        world_path = [self._grid_to_world(p, room) for p in path]

        # 路径平滑
        if len(world_path) > 2:
            world_path = self._smooth_path(world_path)

        # 确定路径类型
        path_type = self._classify_path(start, goal, world_path)

        # 计算风险
        risk = self._assess_path_risk(world_path, game_state)

        # 计算时间
        frames = self._estimate_path_frames(world_path, current_velocity)

        return PathSegment(
            segment_type=path_type,
            start_pos=start,
            end_pos=goal,
            waypoints=world_path,
            estimated_frames=frames,
            risk_level=risk,
        )

    def plan_avoidance(
        self, start: Vector2D, threat_pos: Vector2D, game_state: GameState
    ) -> PathSegment:
        """
        规划规避路径

        Args:
            start: 起始位置
            threat_pos: 威胁位置
            game_state: 游戏状态

        Returns:
            规避路径段
        """
        # 计算远离威胁的方向
        to_threat = threat_pos - start
        away_dir = Vector2D(-to_threat.x, -to_threat.y).normalized()

        # 设置规避目标
        avoid_distance = 150.0
        goal = start + away_dir * avoid_distance

        # 限制在房间内
        if game_state.room:
            goal = self._clamp_to_room(goal, game_state.room)

        return self.plan_path(start, goal, game_state)

    def _world_to_grid(self, pos: Vector2D, room: RoomLayout) -> Tuple[int, int]:
        """世界坐标转网格坐标"""
        if not room.top_left:
            return (0, 0)

        grid_x = int((pos.x - room.top_left.x) / self.grid_size)
        grid_y = int((pos.y - room.top_left.y) / self.grid_size)

        return (max(0, grid_x), max(0, grid_y))

    def _grid_to_world(self, grid: Tuple[int, int], room: RoomLayout) -> Vector2D:
        """网格坐标转世界坐标"""
        if not room.top_left:
            return Vector2D(0, 0)

        x = room.top_left.x + grid[0] * self.grid_size + self.grid_size / 2
        y = room.top_left.y + grid[1] * self.grid_size + self.grid_size / 2

        return Vector2D(x, y)

    def _clamp_to_room(self, pos: Vector2D, room: RoomLayout) -> Vector2D:
        """限制位置在房间内"""
        margin = self.grid_size
        return Vector2D(
            max(room.top_left.x + margin, min(room.bottom_right.x - margin, pos.x)),
            max(room.top_left.y + margin, min(room.bottom_right.y - margin, pos.y)),
        )

    def _astar(
        self,
        start: Vector2D,
        goal: Vector2D,
        room: RoomLayout,
        obstacles: List[Obstacle],
        start_grid: Tuple[int, int],
        goal_grid: Tuple[int, int],
    ) -> Optional[List[Tuple[int, int]]]:
        """A*寻路算法"""
        if not room.top_left:
            return None

        # 计算网格尺寸
        grid_width = int((room.bottom_right.x - room.top_left.x) / self.grid_size) + 1
        grid_height = int((room.bottom_right.y - room.top_left.y) / self.grid_size) + 1

        # 检查目标是否可达
        if not self._is_passable(goal_grid, room, obstacles, grid_width, grid_height):
            return None

        # 开放集
        open_set = []
        heapq.heappush(open_set, (0, start_grid))

        # 记录
        came_from = {}
        g_score = {start_grid: 0}
        f_score = {start_grid: self._heuristic(start_grid, goal_grid)}

        iterations = 0
        while open_set and iterations < self.max_iterations:
            iterations += 1

            # 获取f_score最小的节点
            _, current = heapq.heappop(open_set)

            # 到达目标
            if current == goal_grid:
                return self._reconstruct_path(came_from, current)

            # 探索邻居
            for neighbor in self._get_neighbors(current, grid_width, grid_height):
                if not self._is_passable(
                    neighbor, room, obstacles, grid_width, grid_height
                ):
                    continue

                tentative_g = g_score[current] + 1  # 每个移动代价为1

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self._heuristic(
                        neighbor, goal_grid
                    )
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        return None  # 未找到路径

    def _heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        """启发函数（曼哈顿距离）"""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _get_neighbors(
        self, node: Tuple[int, int], width: int, height: int
    ) -> List[Tuple[int, int]]:
        """获取邻居节点（8方向）"""
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue

                nx, ny = node[0] + dx, node[1] + dy
                if 0 <= nx < width and 0 <= ny < height:
                    neighbors.append((nx, ny))

        return neighbors

    def _is_passable(
        self,
        grid: Tuple[int, int],
        room: RoomLayout,
        obstacles: List[Obstacle],
        width: int,
        height: int,
    ) -> bool:
        """检查格子是否可通行"""
        # 边界检查
        if not (0 <= grid[0] < width and 0 <= grid[1] < height):
            return False

        # 障碍物检查
        world_pos = self._grid_to_world(grid, room)
        for obs in obstacles:
            if not obs.has_collision:
                continue

            # 检查是否在障碍物范围内（考虑膨胀）
            obs_left, obs_right = obs.get_bounding_box()
            expanded_left = Vector2D(
                obs_left.x - self.obstacle_padding, obs_left.y - self.obstacle_padding
            )
            expanded_right = Vector2D(
                obs_right.x + self.obstacle_padding, obs_right.y + self.obstacle_padding
            )

            if (
                expanded_left.x <= world_pos.x <= expanded_right.x
                and expanded_left.y <= world_pos.y <= expanded_right.y
            ):
                return False

        return True

    def _reconstruct_path(
        self, came_from: Dict, current: Tuple[int, int]
    ) -> List[Tuple[int, int]]:
        """重建路径"""
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

    def _smooth_path(self, path: List[Vector2D]) -> List[Vector2D]:
        """路径平滑（ Douglas-Peucker 简化）"""
        if len(path) <= 2:
            return path

        # 简化的中点平滑
        smoothed = [path[0]]
        for i in range(1, len(path) - 1):
            prev = smoothed[-1]
            curr = path[i]
            next_p = path[i + 1]

            # 检查是否在直线上
            if self._is_collinear(prev, curr, next_p, 0.5):
                # 在直线上，跳过
                continue
            else:
                smoothed.append(curr)

        smoothed.append(path[-1])
        return smoothed

    def _is_collinear(
        self, a: Vector2D, b: Vector2D, c: Vector2D, threshold: float
    ) -> bool:
        """检查三点是否近似共线"""
        # 计算面积
        area = abs((b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y))
        line_length = max(a.distance_to(b), b.distance_to(c), a.distance_to(c))

        if line_length < 0.1:
            return True

        return (area / line_length) < threshold

    def _classify_path(
        self, start: Vector2D, goal: Vector2D, path: List[Vector2D]
    ) -> PathSegmentType:
        """分类路径类型"""
        direct_distance = start.distance_to(goal)
        path_length = sum(
            path[i].distance_to(path[i + 1]) for i in range(len(path) - 1)
        )

        if path_length < direct_distance * 1.2:
            return PathSegmentType.DIRECT
        elif path_length > direct_distance * 2:
            return PathSegmentType.CIRCUITOUS
        else:
            return PathSegmentType.APPROACH

    def _assess_path_risk(self, path: List[Vector2D], game_state: GameState) -> float:
        """评估路径风险"""
        risk = 0.0

        # 投射物风险
        for proj in game_state.get_enemy_projectiles():
            if not proj.position:
                continue

            proj_pos = proj.position.pos
            for i in range(len(path) - 1):
                dist = self._point_to_segment_distance(proj_pos, path[i], path[i + 1])
                if dist < 50:
                    risk += 0.1 * (1 - dist / 50)

        return min(1.0, risk)

    def _point_to_segment_distance(
        self, point: Vector2D, a: Vector2D, b: Vector2D
    ) -> float:
        """计算点到线段的距离"""
        ab = b - a
        ap = point - a

        t = max(
            0,
            min(1, ap.dot(ab) / ab.length_squared() if ab.length_squared() > 0 else 0),
        )
        closest = a + ab * t

        return point.distance_to(closest)

    def _estimate_frames(self, start: Vector2D, goal: Vector2D) -> int:
        """估计移动帧数"""
        distance = start.distance_to(goal)
        speed = 6.0  # 默认速度
        return max(1, int(distance / speed))

    def _estimate_path_frames(
        self, path: List[Vector2D], velocity: Vector2D = None
    ) -> int:
        """估计路径移动帧数"""
        if len(path) < 2:
            return 1

        total_distance = sum(
            path[i].distance_to(path[i + 1]) for i in range(len(path) - 1)
        )

        speed = 6.0
        if velocity:
            speed = max(3.0, velocity.length())

        return max(1, int(total_distance / speed))


# ==================== 攻击规划器 ====================


class AttackPlanner:
    """
    攻击规划器

    功能：
    - 射击角度计算（考虑弹道、障碍物）
    - 预判射击（敌人移动预测）
    - 连击规划（多个敌人优先级）
    - 特殊攻击模式（如环绕射击）
    """

    def __init__(self):
        # 预测参数
        self.prediction_horizon = 15  # 预测帧数
        self.lead_factor = 0.3  # 预判因子

        # 射击参数
        self.shot_cooldown = 5  # 射击冷却帧数
        self.max_burst_count = 5  # 最大连发数
        self.burst_delay = 3  # 连发间隔

    def plan_attack(
        self, player_pos: Vector2D, target: EnemyState, game_state: GameState
    ) -> Dict:
        """
        规划攻击

        Args:
            player_pos: 玩家位置
            target: 目标敌人
            game_state: 游戏状态

        Returns:
            攻击计划
        """
        if not target.position:
            return {"can_shoot": False}

        # 计算基础方向
        to_target = target.position.pos - player_pos
        base_direction = to_target.normalized()

        # 预测目标位置
        predicted_pos = self._predict_target_position(target, player_pos)

        # 计算最佳射击角度
        shoot_direction = (predicted_pos - player_pos).normalized()

        # 检查是否有障碍物阻挡
        has_clear_shot = self._check_line_of_sight(
            player_pos, predicted_pos, game_state
        )

        # 预测击杀所需时间
        player_damage = game_state.player.damage if game_state.player else 1.0
        shots_to_kill = math.ceil(target.hp / player_damage) if player_damage > 0 else 1

        return {
            "can_shoot": has_clear_shot,
            "direction": shoot_direction,
            "predicted_position": predicted_pos,
            "shots_to_kill": shots_to_kill,
            "estimated_time": shots_to_kill * self.shot_cooldown,
            "target_id": target.entity_id,
        }

    def plan_multi_target_attack(
        self, player_pos: Vector2D, targets: List[EnemyState], game_state: GameState
    ) -> Dict:
        """
        规划多目标攻击

        Args:
            player_pos: 玩家位置
            targets: 目标列表
            game_state: 游戏状态

        Returns:
            攻击计划
        """
        if not targets:
            return {"can_shoot": False, "targets": []}

        # 评估每个目标
        target_evaluations = []
        for target in targets:
            attack = self.plan_attack(player_pos, target, game_state)
            if attack["can_shoot"]:
                # 计算优先级分数
                priority = self._calculate_target_priority(target, attack, game_state)
                target_evaluations.append(
                    {"target": target, "attack": attack, "priority": priority}
                )

        # 按优先级排序
        target_evaluations.sort(key=lambda x: x["priority"], reverse=True)

        # 生成射击序列
        shoot_schedule = []
        current_frame = 0

        for eval_item in target_evaluations[:3]:  # 最多关注3个目标
            target = eval_item["target"]
            attack = eval_item["attack"]

            shoot_schedule.append(
                {
                    "frame": current_frame,
                    "target_id": target.entity_id,
                    "direction": attack["direction"],
                }
            )

            current_frame += self.shot_cooldown

        return {
            "can_shoot": len(target_evaluations) > 0,
            "targets": [t["target"].entity_id for t in target_evaluations],
            "shoot_schedule": shoot_schedule,
            "primary_target": target_evaluations[0]["target"].entity_id
            if target_evaluations
            else None,
        }

    def _predict_target_position(
        self, target: EnemyState, player_pos: Vector2D
    ) -> Vector2D:
        """预测目标位置"""
        if not target.position:
            return player_pos

        # 使用速度外推
        if target.velocity:
            predicted = (
                target.position.pos + target.velocity.vel * self.prediction_horizon
            )
            return predicted

        return target.position.pos

    def _check_line_of_sight(
        self, from_pos: Vector2D, to_pos: Vector2D, game_state: GameState
    ) -> bool:
        """检查视线是否清晰"""
        room = game_state.room
        if not room:
            return True

        # 简化的射线检测
        direction = (to_pos - from_pos).normalized()
        distance = from_pos.distance_to(to_pos)

        # 检查是否穿过障碍物
        for obs in room.obstacles.values():
            if not obs.has_collision:
                continue

            if self._ray_intersects_obstacle(from_pos, direction, distance, obs):
                return False

        return True

    def _ray_intersects_obstacle(
        self, origin: Vector2D, direction: Vector2D, max_dist: float, obstacle: Obstacle
    ) -> bool:
        """检测射线是否与障碍物相交"""
        # 简化的AABB检测
        obs_left, obs_right = obstacle.get_bounding_box()

        # 检查线段是否与AABB相交
        return not (
            direction.x <= 0
            and origin.x <= obs_left.x
            or direction.x >= 0
            and origin.x >= obs_right.x
            or direction.y <= 0
            and origin.y <= obs_left.y
            or direction.y >= 0
            and origin.y >= obs_right.y
        )

    def _calculate_target_priority(
        self, target: EnemyState, attack: Dict, game_state: GameState
    ) -> float:
        """计算目标优先级"""
        priority = 0.0

        # 低血量优先
        hp_ratio = target.hp / target.max_hp if target.max_hp > 0 else 1.0
        priority += (1 - hp_ratio) * 0.4

        # 距离近优先
        if target.distance_to_player < 200:
            priority += 0.3
        elif target.distance_to_player < 300:
            priority += 0.15

        # Boss优先
        if target.is_boss:
            priority += 0.2

        # 快速击杀优先
        priority += (1.0 / attack["shots_to_kill"]) * 0.1

        return priority


# ==================== 时序规划器 ====================


class TimingPlanner:
    """
    时序规划器

    功能：
    - 动作序列编排
    - 时间窗口计算（何时移动/攻击）
    - 打断处理（紧急情况响应）
    """

    def __init__(self):
        self.timing_windows: List[TimingWindow] = []
        self.current_frame = 0
        self.action_queue: deque = deque()

    def plan_timeline(
        self,
        action_intent: ActionIntent,
        path_segments: List[PathSegment],
        shoot_schedule: List[Dict],
    ) -> List[Dict]:
        """
        编排时序

        Args:
            action_intent: 行动意图
            path_segments: 路径段
            shoot_schedule: 射击计划

        Returns:
            时间线 [(frame, action), ...]
        """
        timeline = []
        current_frame = 0

        # 编排移动
        for segment in path_segments:
            for waypoint in segment.waypoints:
                timeline.append(
                    {
                        "frame": current_frame,
                        "type": "move",
                        "target": waypoint,
                        "can_interrupt": segment.can_interrupt,
                    }
                )
                current_frame += 2  # 每2帧一个移动指令

        # 编排射击
        for shot in shoot_schedule:
            timeline.append(
                {
                    "frame": shot["frame"],
                    "type": "shoot",
                    "target_id": shot.get("target_id"),
                    "direction": shot.get("direction"),
                }
            )

        # 按帧排序
        timeline.sort(key=lambda x: x["frame"])

        return timeline

    def find_safe_timing_window(
        self, game_state: GameState, min_duration: int
    ) -> Optional[TimingWindow]:
        """
        寻找安全时间窗口

        Args:
            game_state: 游戏状态
            min_duration: 最小持续时间

        Returns:
            时间窗口或None
        """
        player_pos = (
            game_state.player.position.pos
            if game_state.player and game_state.player.position
            else None
        )
        if not player_pos:
            return None

        # 搜索未来的安全窗口
        for start_frame in range(0, 60, 5):  # 搜索60帧
            is_safe = True
            safe_duration = 0

            for offset in range(min_duration):
                frame = start_frame + offset

                # 检查投射物
                for proj in game_state.get_enemy_projectiles():
                    if not proj.position:
                        continue

                    # 预测投射物位置
                    if proj.velocity:
                        pred_pos = proj.position.pos + proj.velocity.vel * frame
                        if pred_pos.distance_to(player_pos) < 80:
                            is_safe = False
                            break

                if is_safe:
                    safe_duration += 1
                else:
                    break

            if safe_duration >= min_duration:
                return TimingWindow(
                    start_frame=start_frame,
                    end_frame=start_frame + safe_duration,
                    duration_frames=safe_duration,
                    action_type="movement",
                    priority=5,
                )

        return None

    def add_interrupt_handler(self, condition: str, priority: int = 10) -> None:
        """添加打断处理"""
        # 存储打断条件
        pass

    def should_interrupt(
        self, game_state: GameState, current_action: Dict
    ) -> Tuple[bool, str]:
        """
        检查是否应该打断当前行动

        Returns:
            (是否打断, 原因)
        """
        # 检查即时威胁
        for proj in game_state.get_enemy_projectiles():
            if not proj.position:
                continue

            player_pos = (
                game_state.player.position.pos
                if game_state.player and game_state.player.position
                else None
            )
            if not player_pos:
                continue

            dist = proj.position.pos.distance_to(player_pos)
            if dist < 50:
                return True, f"projectile_too_close_{dist}"

        # 检查玩家是否在危险位置
        if game_state.hazard_zones:
            player_pos = (
                game_state.player.position.pos
                if game_state.player and game_state.player.position
                else None
            )
            if player_pos:
                for hazard in game_state.hazard_zones:
                    if hazard.contains_point(player_pos):
                        return True, f"in_hazard_zone_{hazard.hazard_type}"

        return False, ""


# ==================== 风险管理器 ====================


class RiskManager:
    """
    风险管理器

    功能：
    - 风险-收益权衡
    - 安全边界设置
    - 应急计划生成
    """

    def __init__(self):
        # 风险阈值
        self.max_risk_threshold = 0.7
        self.safety_margin = 0.2

        # 风险因素权重
        self.collision_weight = 0.4
        self.threat_weight = 0.4
        self.resource_weight = 0.2

    def assess_risk(
        self, action_intent: ActionIntent, game_state: GameState
    ) -> RiskAssessment:
        """
        评估行动风险

        Args:
            action_intent: 行动意图
            game_state: 游戏状态

        Returns:
            风险评估
        """
        assessment = RiskAssessment()

        # 碰撞风险
        assessment.collision_risk = self._assess_collision_risk(
            action_intent, game_state
        )

        # 威胁暴露
        assessment.threat_exposure = self._assess_threat_exposure(
            action_intent, game_state
        )

        # 资源消耗
        assessment.resource_cost = self._assess_resource_cost(action_intent, game_state)

        # 综合风险
        assessment.overall_risk = (
            assessment.collision_risk * self.collision_weight
            + assessment.threat_exposure * self.threat_weight
            + assessment.resource_cost * self.resource_weight
        )

        # 收益评估
        assessment.expected_gain = self._assess_expected_gain(action_intent, game_state)

        # 生成建议
        if assessment.overall_risk > self.max_risk_threshold:
            assessment.suggested_alternatives.append("使用备用路线")
            assessment.suggested_alternatives.append("等待更安全时机")

        return assessment

    def should_proceed(self, risk: RiskAssessment) -> Tuple[bool, str]:
        """
        判断是否应该执行

        Returns:
            (是否执行, 原因)
        """
        if risk.overall_risk > self.max_risk_threshold:
            return (
                False,
                f"风险过高 ({risk.overall_risk:.2f} > {self.max_risk_threshold})",
            )

        if risk.overall_risk > 0.5 and risk.expected_gain < 0.3:
            return (
                False,
                f"风险收益比不佳 (风险:{risk.overall_risk:.2f}, 收益:{risk.expected_gain:.2f})",
            )

        return True, "风险可接受"

    def generate_fallback_plan(
        self, original_intent: ActionIntent, reason: str, game_state: GameState
    ) -> Optional[ActionIntent]:
        """
        生成备用计划

        Args:
            original_intent: 原始意图
            reason: 原因
            game_state: 游戏状态

        Returns:
            备用行动意图或None
        """
        # 根据原因生成备用计划
        if "collision" in reason.lower():
            # 碰撞风险，寻找替代路径
            return ActionIntent(
                action_type=ActionType.FIND_COVER,
                priority=original_intent.priority,
                parameters={
                    "fallback_reason": reason,
                    "original_action": original_intent.action_type.value,
                },
            )

        elif "threat" in reason.lower():
            # 威胁过高，撤退
            return ActionIntent(
                action_type=ActionType.STRATEGIC_RETREAT,
                priority=original_intent.priority,
                parameters={
                    "fallback_reason": reason,
                    "original_action": original_intent.action_type.value,
                },
            )

        return ActionIntent(
            action_type=ActionType.IDLE,
            priority=0,
            parameters={
                "fallback_reason": reason,
                "original_action": original_intent.action_type.value,
            },
        )

    def _assess_collision_risk(
        self, action_intent: ActionIntent, game_state: GameState
    ) -> float:
        """评估碰撞风险"""
        if not game_state.room:
            return 0.3

        risk = 0.0

        # 移动路径风险
        if action_intent.target_position:
            path_planner = PathPlanner()
            segment = path_planner.plan_path(
                game_state.player.position.pos,
                action_intent.target_position,
                game_state,
            )
            risk += segment.risk_level * 0.5

        # 障碍物风险
        player_pos = (
            game_state.player.position.pos
            if game_state.player and game_state.player.position
            else None
        )
        if player_pos:
            clearance = game_state.room.get_clearance(player_pos)
            if clearance < 30:
                risk += 0.3
            elif clearance < 50:
                risk += 0.1

        return min(1.0, risk)

    def _assess_threat_exposure(
        self, action_intent: ActionIntent, game_state: GameState
    ) -> float:
        """评估威胁暴露"""
        risk = 0.0

        # 投射物暴露
        for proj in game_state.get_enemy_projectiles():
            if not proj.position:
                continue

            if action_intent.target_position:
                # 评估移动到目标位置时的暴露
                dist = proj.position.pos.distance_to(action_intent.target_position)
                if dist < 100:
                    risk += 0.2 * (1 - dist / 100)
            else:
                # 当前暴露
                player_pos = (
                    game_state.player.position.pos
                    if game_state.player and game_state.player.position
                    else None
                )
                if player_pos:
                    dist = proj.position.pos.distance_to(player_pos)
                    if dist < 80:
                        risk += 0.3

        return min(1.0, risk)

    def _assess_resource_cost(
        self, action_intent: ActionIntent, game_state: GameState
    ) -> float:
        """评估资源消耗"""
        cost = 0.0

        # 移动消耗（基于距离）
        if action_intent.target_position:
            player_pos = (
                game_state.player.position.pos
                if game_state.player and game_state.player.position
                else None
            )
            if player_pos:
                distance = player_pos.distance_to(action_intent.target_position)
                cost += min(0.3, distance / 500)

        # 射击消耗
        if action_intent.action_type in [
            ActionType.FOCUS_FIRE,
            ActionType.ELIMINATE_THREAT,
        ]:
            cost += 0.1

        return min(1.0, cost)

    def _assess_expected_gain(
        self, action_intent: ActionIntent, game_state: GameState
    ) -> float:
        """评估预期收益"""
        gain = 0.0

        # 击杀收益
        if action_intent.target_entity_id:
            enemy = game_state.enemies.get(action_intent.target_entity_id)
            if enemy and enemy.is_alive():
                gain += 0.3 * (1 - enemy.hp / enemy.max_hp if enemy.max_hp > 0 else 0)

        # 位置收益
        if action_intent.target_position and game_state.room:
            target_clearance = game_state.room.get_clearance(
                action_intent.target_position
            )
            current_clearance = (
                game_state.room.get_clearance(game_state.player.position.pos)
                if game_state.player and game_state.player.position
                else 0
            )
            gain += min(0.2, (target_clearance - current_clearance) / 100)

        # 战斗进展
        if action_intent.action_type in [
            ActionType.FOCUS_FIRE,
            ActionType.ELIMINATE_THREAT,
        ]:
            gain += 0.2

        return min(1.0, gain)


# ==================== 规划模块主类 ====================


class PlanningModule:
    """
    规划模块主类

    整合路径规划器、攻击规划器、时序规划器和风险管理器，
    将行动意图转换为具体执行计划。

    输入: 行动意图 (ActionIntent) + 游戏状态 (GameState)
    输出: 执行计划 (ExecutionPlan)
    """

    def __init__(self):
        self.path_planner = PathPlanner()
        self.attack_planner = AttackPlanner()
        self.timing_planner = TimingPlanner()
        self.risk_manager = RiskManager()

        # 统计
        self.stats = {
            "total_plans": 0,
            "avg_planning_time_ms": 0.0,
            "fallback_usage_count": 0,
        }

    def plan(self, action_intent: ActionIntent, game_state: GameState) -> ExecutionPlan:
        """
        生成执行计划

        Args:
            action_intent: 行动意图
            game_state: 游戏状态

        Returns:
            执行计划
        """
        start_time = time.time()

        plan = ExecutionPlan(action_intent=action_intent)

        # 1. 规划路径
        if (
            action_intent.target_position
            and game_state.player
            and game_state.player.position
        ):
            path_segment = self.path_planner.plan_path(
                game_state.player.position.pos,
                action_intent.target_position,
                game_state,
                current_velocity=game_state.player.velocity.vel
                if game_state.player.velocity
                else None,
            )
            plan.path_segments.append(path_segment)
            plan.total_estimated_frames = path_segment.estimated_frames

        # 2. 规划攻击
        if action_intent.action_type in [
            ActionType.FOCUS_FIRE,
            ActionType.ELIMINATE_THREAT,
        ]:
            if action_intent.target_entity_id:
                target = game_state.enemies.get(action_intent.target_entity_id)
                if target:
                    attack_plan = self.attack_planner.plan_attack(
                        game_state.player.position.pos, target, game_state
                    )
                    if attack_plan["can_shoot"]:
                        plan.shoot_targets.append(
                            {
                                "target_id": action_intent.target_entity_id,
                                "direction": attack_plan["direction"],
                            }
                        )

        # 3. 编排时序
        plan.timeline = self.timing_planner.plan_timeline(
            action_intent, plan.path_segments, plan.shoot_targets
        )

        # 4. 风险评估
        risk = self.risk_manager.assess_risk(action_intent, game_state)
        plan.overall_risk = risk.overall_risk

        # 检查是否应该执行
        should_proceed, reason = self.risk_manager.should_proceed(risk)

        if not should_proceed:
            # 生成备用计划
            fallback = self.risk_manager.generate_fallback_plan(
                action_intent, reason, game_state
            )
            if fallback:
                plan.fallback_plans.append(self.plan(fallback, game_state))
                self.stats["fallback_usage_count"] += 1
                plan.is_complete = False  # 需要执行备用计划
            else:
                plan.is_complete = True
        else:
            plan.is_complete = True

        # 5. 约束检查
        for constraint in action_intent.constraints:
            plan.constraint_checks[constraint] = self._check_constraint(
                constraint, action_intent, game_state
            )

        # 计算成功率
        plan.success_probability = 1.0 - plan.overall_risk
        for check_result in plan.constraint_checks.values():
            if not check_result:
                plan.success_probability *= 0.8

        # 更新统计
        self.stats["total_plans"] += 1
        planning_time = (time.time() - start_time) * 1000
        self.stats["avg_planning_time_ms"] = (
            self.stats["avg_planning_time_ms"] * 0.9 + planning_time * 0.1
        )

        return plan

    def _check_constraint(
        self, constraint: str, action_intent: ActionIntent, game_state: GameState
    ) -> bool:
        """检查约束"""
        if constraint == "avoid_threat":
            # 检查是否避开了威胁
            for proj in game_state.get_enemy_projectiles():
                if not proj.position:
                    continue

                if action_intent.target_position:
                    dist = proj.position.pos.distance_to(action_intent.target_position)
                    if dist < 80:
                        return False
            return True

        elif constraint == "maintain_distance":
            # 检查是否保持距离
            if action_intent.target_entity_id:
                target = game_state.enemies.get(action_intent.target_entity_id)
                if target and target.position:
                    dist = (
                        action_intent.target_position.distance_to(target.position.pos)
                        if action_intent.target_position
                        else float("inf")
                    )
                    return 100 <= dist <= 400

        return True

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_plans": self.stats["total_plans"],
            "avg_planning_time_ms": self.stats["avg_planning_time_ms"],
            "fallback_usage_count": self.stats["fallback_usage_count"],
        }


# ==================== 便捷函数 ====================


def create_planning_module() -> PlanningModule:
    """创建规划模块实例"""
    return PlanningModule()


# 导出主要类
__all__ = [
    "PlanningModule",
    "PathPlanner",
    "AttackPlanner",
    "TimingPlanner",
    "RiskManager",
    "ExecutionPlan",
    "PathSegment",
    "PathSegmentType",
    "TimingWindow",
    "RiskAssessment",
    "create_planning_module",
]
