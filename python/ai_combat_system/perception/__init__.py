"""
感知模块 (Perception Module) - Simplified version without numpy

将原始数据转换为结构化信息，为AI决策系统提供可靠的环境感知能力。
"""

import math
import time
import logging
from typing import Dict, List, Optional, Tuple, Set, Any
from dataclasses import dataclass, field
from collections import deque
from enum import Enum

logger = logging.getLogger("PerceptionModule")


class ThreatLevel(Enum):
    """威胁等级"""

    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


class EntityType(Enum):
    """实体类型"""

    PLAYER = "player"
    ENEMY = "enemy"
    PROJECTILE = "projectile"
    LASER = "laser"
    OBSTACLE = "obstacle"
    PICKUP = "pickup"
    INTERACTABLE = "interactable"
    HAZARD = "hazard"


class MovementPattern(Enum):
    """移动模式"""

    STATIONARY = "stationary"
    CHASING = "chasing"
    FLEING = "fleeing"
    ERRATIC = "erratic"
    PATROL = "patrol"
    UNKNOWN = "unknown"


@dataclass
class Vector2D:
    """二维向量"""

    x: float = 0.0
    y: float = 0.0

    def __add__(self, other: "Vector2D") -> "Vector2D":
        return Vector2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector2D") -> "Vector2D":
        return Vector2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vector2D":
        return Vector2D(self.x * scalar, self.y * scalar)

    def __truediv__(self, scalar: float) -> "Vector2D":
        if scalar == 0:
            return Vector2D(0, 0)
        return Vector2D(self.x / scalar, self.y / scalar)

    def length(self) -> float:
        return math.sqrt(self.x**2 + self.y**2)

    def length_squared(self) -> float:
        return self.x**2 + self.y**2

    def normalized(self) -> "Vector2D":
        length = self.length()
        if length < 0.0001:
            return Vector2D(0, 0)
        return Vector2D(self.x / length, self.y / length)

    def dot(self, other: "Vector2D") -> float:
        return self.x * other.x + self.y * other.y

    def distance_to(self, other: "Vector2D") -> float:
        return (self - other).length()

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class Position:
    """位置信息"""

    pos: Vector2D = field(default_factory=lambda: Vector2D(0, 0))
    grid_x: int = 0
    grid_y: int = 0
    timestamp: float = field(default_factory=time.time)
    frame: int = 0


@dataclass
class Velocity:
    """速度信息"""

    vel: Vector2D = field(default_factory=lambda: Vector2D(0, 0))
    max_speed: float = 10.0
    acceleration: float = 1.0


@dataclass
class PlayerState:
    """玩家状态"""

    player_id: int
    position: Optional[Position] = None
    velocity: Optional[Velocity] = None
    hp: float = 0.0
    max_hp: float = 0.0
    damage: float = 0.0
    speed: float = 0.0
    can_fly: bool = False
    is_alive: bool = True
    # Additional fields expected by analysis module
    active_items: Dict[int, str] = field(default_factory=dict)
    passive_items: List[int] = field(default_factory=list)
    coins: int = 0
    bombs: int = 0
    keys: int = 0
    is_invincible: bool = False
    invincible_timer: float = 0.0
    tear_rate: float = 1.0


@dataclass
class EnemyState:
    """敌人状态"""

    entity_id: int
    enemy_type: int
    variant: int
    subtype: int
    position: Optional[Position] = None
    velocity: Optional[Velocity] = None
    hp: float = 0.0
    max_hp: float = 0.0
    is_boss: bool = False
    is_champion: bool = False
    distance_to_player: float = float("inf")
    # Additional fields expected by analysis module
    is_attacking: bool = False
    projectile_cooldown: int = 0
    collision_radius: float = 15.0

    def is_alive_method(self) -> bool:
        return self.hp > 0


@dataclass
class ProjectileState:
    """投射物状态"""

    entity_id: int
    is_enemy: bool
    position: Optional[Position] = None
    velocity: Optional[Velocity] = None
    collision_radius: float = 8.0
    is_laser: bool = False

    def is_alive(self) -> bool:
        return True


@dataclass
class Obstacle:
    """障碍物"""

    grid_index: int
    obstacle_type: int
    variant: int
    position: Vector2D
    has_collision: bool = True

    def get_bounding_box(self) -> Tuple[Vector2D, Vector2D]:
        half_w, half_h = 20.0, 20.0
        return (
            Vector2D(self.position.x - half_w, self.position.y - half_h),
            Vector2D(self.position.x + half_w, self.position.y + half_h),
        )


@dataclass
class HazardZone:
    """危险区域"""

    hazard_type: str
    position: Vector2D
    radius: float
    damage: float = 1.0
    # Additional field expected by analysis module
    source_entity_id: Optional[int] = None

    def contains_point(self, point: Vector2D) -> bool:
        return point.distance_to(self.position) <= self.radius


@dataclass
class RoomLayout:
    """房间布局"""

    room_index: int = -1
    room_type: int = 0
    top_left: Optional[Vector2D] = None
    bottom_right: Optional[Vector2D] = None
    grid_width: int = 13
    grid_height: int = 7
    obstacles: Dict[int, Obstacle] = field(default_factory=dict)
    doors: Dict[int, Dict] = field(default_factory=dict)
    is_clear: bool = False
    enemy_count: int = 0
    has_boss: bool = False
    # Additional fields expected by analysis module
    width: float = 520.0  # grid_width * 40
    height: float = 280.0  # grid_height * 40

    @property
    def center(self) -> Vector2D:
        if self.top_left and self.bottom_right:
            return Vector2D(
                (self.top_left.x + self.bottom_right.x) / 2,
                (self.top_left.y + self.bottom_right.y) / 2,
            )
        return Vector2D(0, 0)

    def is_inside_room(self, pos: Vector2D, margin: float = 0.0) -> bool:
        if not self.top_left or not self.bottom_right:
            return False
        return (
            self.top_left.x + margin <= pos.x <= self.bottom_right.x - margin
            and self.top_left.y + margin <= pos.y <= self.bottom_right.y - margin
        )

    def get_clearance(self, pos: Vector2D, radius: float = 20.0) -> float:
        """计算某点的最小清空距离"""
        min_clearance = float("inf")

        for obstacle in self.obstacles.values():
            if not obstacle.has_collision:
                continue

            obs_left, obs_right = obstacle.get_bounding_box()

            if pos.x < obs_left.x:
                dist_x = obs_left.x - pos.x
            elif pos.x > obs_right.x:
                dist_x = pos.x - obs_right.x
            else:
                dist_x = 0

            if pos.y < obs_left.y:
                dist_y = obs_left.y - pos.y
            elif pos.y > obs_right.y:
                dist_y = pos.y - obs_right.y
            else:
                dist_y = 0

            if dist_x == 0 and dist_y == 0:
                return 0.0

            clearance = math.sqrt(dist_x**2 + dist_y**2)
            min_clearance = min(min_clearance, clearance)

        if self.top_left and self.bottom_right:
            if pos.x - self.top_left.x < min_clearance:
                min_clearance = pos.x - self.top_left.x
            if self.bottom_right.x - pos.x < min_clearance:
                min_clearance = self.bottom_right.x - pos.x
            if pos.y - self.top_left.y < min_clearance:
                min_clearance = pos.y - self.top_left.y
            if self.bottom_right.y - pos.y < min_clearance:
                min_clearance = self.bottom_right.y - pos.y

        return max(0.0, min_clearance)


@dataclass
class GameState:
    """完整游戏状态"""

    frame: int = 0
    room_index: int = -1
    timestamp: float = field(default_factory=time.time)
    player: Optional[PlayerState] = None
    enemies: Dict[int, EnemyState] = field(default_factory=dict)
    projectiles: Dict[int, ProjectileState] = field(default_factory=dict)
    room: Optional[RoomLayout] = None
    hazard_zones: List[HazardZone] = field(default_factory=list)

    def get_active_enemies(self) -> List[EnemyState]:
        return [e for e in self.enemies.values() if e.is_alive_method()]

    def get_enemy_projectiles(self) -> List[ProjectileState]:
        return [p for p in self.projectiles.values() if p.is_enemy and p.is_alive()]

    def get_nearest_enemy(self, pos: Vector2D) -> Optional[EnemyState]:
        active = self.get_active_enemies()
        if not active:
            return None
        return min(
            active,
            key=lambda e: e.position.pos.distance_to(pos)
            if e.position
            else float("inf"),
        )


class DataParser:
    """数据解析器"""

    def __init__(self):
        self.last_frame = 0

    def parse_player_data(
        self, raw_data: Dict, player_idx: int = 1
    ) -> Optional[PlayerState]:
        if not raw_data:
            return None

        if isinstance(raw_data, list):
            idx = player_idx - 1
            if idx < 0 or idx >= len(raw_data):
                return None
            player_raw = raw_data[idx]
        elif isinstance(raw_data, dict):
            player_raw = raw_data.get(str(player_idx)) or raw_data.get(player_idx)
        else:
            return None

        if not player_raw:
            return None

        pos_data = player_raw.get("pos", {})
        pos = Vector2D(pos_data.get("x", 0.0), pos_data.get("y", 0.0))

        vel_data = player_raw.get("vel", {})
        vel = Vector2D(vel_data.get("x", 0.0), vel_data.get("y", 0.0))

        player = PlayerState(
            player_id=player_idx,
            position=Position(pos=pos, timestamp=time.time(), frame=self.last_frame),
            velocity=Velocity(vel=vel),
            hp=player_raw.get("hp", 0.0),
            max_hp=player_raw.get("max_hp", 0.0),
            damage=player_raw.get("damage", 0.0),
            speed=player_raw.get("speed", 1.0),
            can_fly=player_raw.get("can_fly", False),
        )

        return player

    def parse_enemy_data(self, raw_data: List[Dict]) -> Dict[int, EnemyState]:
        enemies = {}

        for enemy_raw in raw_data:
            entity_id = enemy_raw.get("id")
            if entity_id is None:
                continue

            pos_data = enemy_raw.get("pos", {})
            pos = Vector2D(pos_data.get("x", 0.0), pos_data.get("y", 0.0))

            vel_data = enemy_raw.get("vel", {})
            vel = Vector2D(vel_data.get("x", 0.0), vel_data.get("y", 0.0))

            enemy = EnemyState(
                entity_id=entity_id,
                enemy_type=enemy_raw.get("type", 0),
                variant=enemy_raw.get("variant", 0),
                subtype=enemy_raw.get("subtype", 0),
                position=Position(
                    pos=pos, timestamp=time.time(), frame=self.last_frame
                ),
                velocity=Velocity(vel=vel),
                hp=enemy_raw.get("hp", 0.0),
                max_hp=enemy_raw.get("max_hp", 0.0),
                is_boss=enemy_raw.get("is_boss", False),
                is_champion=enemy_raw.get("is_champion", False),
                distance_to_player=enemy_raw.get("distance", float("inf")),
            )

            enemies[entity_id] = enemy

        return enemies

    def parse_projectile_data(self, raw_data: Dict) -> Dict[int, ProjectileState]:
        projectiles = {}

        for proj_raw in raw_data.get("enemy_projectiles", []):
            proj = self._parse_single_projectile(proj_raw, True)
            if proj:
                projectiles[proj.entity_id] = proj

        for proj_raw in raw_data.get("player_tears", []):
            proj = self._parse_single_projectile(proj_raw, False)
            if proj:
                projectiles[proj.entity_id] = proj

        for laser_raw in raw_data.get("lasers", []):
            proj = self._parse_laser(laser_raw, laser_raw.get("is_enemy", False))
            if proj:
                projectiles[proj.entity_id] = proj

        return projectiles

    def _parse_single_projectile(
        self, raw_data: Dict, is_enemy: bool
    ) -> Optional[ProjectileState]:
        entity_id = raw_data.get("id")
        if entity_id is None:
            return None

        pos_data = raw_data.get("pos", {})
        pos = Vector2D(pos_data.get("x", 0.0), pos_data.get("y", 0.0))

        vel_data = raw_data.get("vel", {})
        vel = Vector2D(vel_data.get("x", 0.0), vel_data.get("y", 0.0))

        return ProjectileState(
            entity_id=entity_id,
            is_enemy=is_enemy,
            position=Position(pos=pos, timestamp=time.time(), frame=self.last_frame),
            velocity=Velocity(vel=vel),
            collision_radius=raw_data.get("collision_radius", 8.0),
        )

    def _parse_laser(self, raw_data: Dict, is_enemy: bool) -> Optional[ProjectileState]:
        entity_id = raw_data.get("id")
        if entity_id is None:
            return None

        pos_data = raw_data.get("pos", {})
        pos = Vector2D(pos_data.get("x", 0.0), pos_data.get("y", 0.0))

        return ProjectileState(
            entity_id=entity_id,
            is_enemy=is_enemy,
            position=Position(pos=pos, timestamp=time.time(), frame=self.last_frame),
            velocity=Velocity(vel=Vector2D(0, 0)),
            is_laser=True,
        )

    def parse_room_layout(self, raw_data: Dict, grid_size: float = 40.0) -> RoomLayout:
        layout = RoomLayout(
            room_index=raw_data.get("room_idx", -1),
            room_type=raw_data.get("room_type", 0),
        )

        top_left_data = raw_data.get("top_left", {})
        bottom_right_data = raw_data.get("bottom_right", {})

        if top_left_data and bottom_right_data:
            layout.top_left = Vector2D(
                top_left_data.get("x", 0.0), top_left_data.get("y", 0.0)
            )
            layout.bottom_right = Vector2D(
                bottom_right_data.get("x", 0.0), bottom_right_data.get("y", 0.0)
            )

        layout.grid_width = raw_data.get("grid_width", 13)
        layout.grid_height = raw_data.get("grid_height", 7)

        return layout

    def set_frame_info(self, frame: int, timestamp: float):
        self.last_frame = frame


class EnvironmentModeler:
    """环境建模器"""

    def __init__(self):
        self.static_obstacles: Dict[int, Obstacle] = {}
        self.dynamic_obstacles: Dict[int, Obstacle] = {}
        self.hazard_zones: List[HazardZone] = []

    def update_static_obstacles(self, room_layout: RoomLayout):
        self.static_obstacles = room_layout.obstacles.copy()

    def update_hazard_zones(
        self, projectiles: Dict[int, ProjectileState], enemies: Dict[int, EnemyState]
    ):
        self.hazard_zones = []

        for proj_id, proj in projectiles.items():
            if not proj.is_enemy or not proj.position:
                continue

            self.hazard_zones.append(
                HazardZone(
                    hazard_type="projectile",
                    position=proj.position.pos,
                    radius=proj.collision_radius * 2,
                )
            )

    def is_position_valid(
        self, pos: Vector2D, collision_radius: float = 20.0
    ) -> Tuple[bool, str]:
        for idx, obstacle in self.static_obstacles.items():
            if not obstacle.has_collision:
                continue

            obs_left, obs_right = obstacle.get_bounding_box()
            expanded_left = Vector2D(
                obs_left.x - collision_radius, obs_left.y - collision_radius
            )
            expanded_right = Vector2D(
                obs_right.x + collision_radius, obs_right.y + collision_radius
            )

            if not (
                pos.x < expanded_left.x
                or pos.x > expanded_right.x
                or pos.y < expanded_left.y
                or pos.y > expanded_right.y
            ):
                return False, f"collision_with_obstacle_{idx}"

        for hazard in self.hazard_zones:
            if hazard.contains_point(pos):
                return False, f"in_hazard_zone_{hazard.hazard_type}"

        return True, "valid"


class StateTracker:
    """状态追踪器"""

    def __init__(self, max_history: int = 60):
        self.max_history = max_history
        self.player_position_history: deque = deque(maxlen=max_history)
        self.enemy_position_history: Dict[int, deque] = {}

    def update_player(self, player: PlayerState):
        if player and player.position:
            self.player_position_history.append(
                {
                    "pos": player.position.pos,
                    "vel": player.velocity.vel if player.velocity else Vector2D(0, 0),
                    "frame": player.position.frame,
                }
            )

    def update_enemy(self, enemy: EnemyState):
        enemy_id = enemy.entity_id

        if enemy_id not in self.enemy_position_history:
            self.enemy_position_history[enemy_id] = deque(maxlen=self.max_history)

        if enemy.position:
            self.enemy_position_history[enemy_id].append(
                {
                    "pos": enemy.position.pos,
                    "vel": enemy.velocity.vel if enemy.velocity else Vector2D(0, 0),
                    "frame": enemy.position.frame,
                }
            )

    def predict_position(
        self, history: deque, frames_ahead: int = 30
    ) -> Optional[Vector2D]:
        if len(history) < 2:
            return None if not history else list(history)[-1]["pos"]

        recent = list(history)[-5:]
        avg_vel = Vector2D(0, 0)
        for entry in recent:
            avg_vel = avg_vel + entry["vel"]
        avg_vel = avg_vel * (1.0 / len(recent))

        current_pos = list(history)[-1]["pos"]
        return current_pos + avg_vel * frames_ahead

    def predict_player_position(self, frames_ahead: int = 30) -> Optional[Vector2D]:
        return self.predict_position(self.player_position_history, frames_ahead)

    def predict_enemy_position(
        self, enemy_id: int, frames_ahead: int = 30
    ) -> Optional[Vector2D]:
        if enemy_id not in self.enemy_position_history:
            return None
        return self.predict_position(
            self.enemy_position_history[enemy_id], frames_ahead
        )


class PerceptionModule:
    """感知模块主类"""

    def __init__(self):
        self.data_parser = DataParser()
        self.environment_modeler = EnvironmentModeler()
        self.state_tracker = StateTracker()

        self.current_state: GameState = GameState()
        self.stats = {"total_updates": 0, "avg_processing_time_ms": 0.0}

    def process_raw_data(
        self, raw_data: Dict, frame: int = 0, room_index: int = -1
    ) -> GameState:
        """处理原始数据，生成结构化游戏状态"""
        start_time = time.time()

        self.data_parser.set_frame_info(frame, start_time)

        state = GameState(frame=frame, room_index=room_index, timestamp=start_time)

        # 解析玩家
        player_data = raw_data.get("PLAYER_POSITION", {})
        state.player = self.data_parser.parse_player_data(player_data)
        if state.player:
            self.state_tracker.update_player(state.player)

        # 解析敌人
        enemies_data = raw_data.get("ENEMIES", [])
        state.enemies = self.data_parser.parse_enemy_data(enemies_data)
        for enemy in state.enemies.values():
            self.state_tracker.update_enemy(enemy)

        # 解析投射物
        projectiles_data = raw_data.get("PROJECTILES", {})
        state.projectiles = self.data_parser.parse_projectile_data(projectiles_data)

        # 解析房间
        room_layout_data = raw_data.get("ROOM_LAYOUT", {})
        state.room = self.data_parser.parse_room_layout(room_layout_data)
        state.room.is_clear = raw_data.get("ROOM_INFO", {}).get("is_clear", False)
        state.room.enemy_count = raw_data.get("ROOM_INFO", {}).get("enemy_count", 0)

        # 更新环境
        if state.room:
            self.environment_modeler.update_static_obstacles(state.room)

        self.environment_modeler.update_hazard_zones(state.projectiles, state.enemies)
        state.hazard_zones = self.environment_modeler.hazard_zones

        # 清理消失的实体
        self._cleanup_missing_entities(state)

        # 统计
        self.stats["total_updates"] += 1
        processing_time = (time.time() - start_time) * 1000
        self.stats["avg_processing_time_ms"] = (
            self.stats["avg_processing_time_ms"] * 0.9 + processing_time * 0.1
        )

        self.current_state = state
        return state

    def _cleanup_missing_entities(self, state: GameState):
        """清理消失的实体"""
        active_enemy_ids = set(state.enemies.keys())
        for enemy_id in list(self.state_tracker.enemy_position_history.keys()):
            if enemy_id not in active_enemy_ids:
                del self.state_tracker.enemy_position_history[enemy_id]

    def get_current_state(self) -> GameState:
        return self.current_state

    def is_position_safe(self, pos: Vector2D) -> Tuple[bool, str]:
        return self.environment_modeler.is_position_valid(pos)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_updates": self.stats["total_updates"],
            "avg_processing_time_ms": self.stats["avg_processing_time_ms"],
            "current_frame": self.current_state.frame,
            "active_enemies": len(self.current_state.get_active_enemies()),
        }


def create_perception_module() -> PerceptionModule:
    return PerceptionModule()


__all__ = [
    "PerceptionModule",
    "GameState",
    "PlayerState",
    "EnemyState",
    "ProjectileState",
    "RoomLayout",
    "Obstacle",
    "HazardZone",
    "Vector2D",
    "ThreatLevel",
    "EntityType",
    "MovementPattern",
    "create_perception_module",
]
