"""
SocketBridge 数据模型层

定义游戏实体的标准化数据结构，包括玩家、敌人、投射物等。
提供统一的数据访问接口，支持增量更新。

根据 DATA_PROTOCOL.md 中的数据格式定义。
"""

import math
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger("Models")


class EntityType(Enum):
    """实体类型枚举"""

    PLAYER = "player"
    ENEMY = "enemy"
    PROJECTILE = "projectile"
    LASER = "laser"
    PICKUP = "pickup"
    OBSTACLE = "obstacle"
    BUTTON = "button"
    BOMB = "bomb"
    INTERACTABLE = "interactable"
    FIRE_HAZARD = "fire_hazard"
    DESTRUCTIBLE = "destructible"


class ObjectState(Enum):
    """对象状态"""

    ACTIVE = "active"
    DYING = "dying"
    DEAD = "dead"
    ESCAPED = "escaped"


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

    def __neg__(self) -> "Vector2D":
        return Vector2D(-self.x, -self.y)

    def __eq__(self, other: "Vector2D") -> bool:
        return abs(self.x - other.x) < 0.001 and abs(self.y - other.y) < 0.001

    def __hash__(self) -> int:
        return hash((round(self.x, 3), round(self.y, 3)))

    def magnitude(self) -> float:
        """获取向量长度"""
        return math.sqrt(self.x**2 + self.y**2)

    def normalized(self) -> "Vector2D":
        """返回归一化向量"""
        mag = self.magnitude()
        if mag == 0:
            return Vector2D(0, 0)
        return self / mag

    def dot(self, other: "Vector2D") -> float:
        """点积"""
        return self.x * other.x + self.y * other.y

    def distance_to(self, other: "Vector2D") -> float:
        """计算到另一个点的距离"""
        return (self - other).magnitude()

    def to_tuple(self) -> Tuple[float, float]:
        """转换为元组"""
        return (self.x, self.y)

    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "Vector2D":
        """从字典创建"""
        return cls(x=data.get("x", 0), y=data.get("y", 0))

    @classmethod
    def from_tuple(cls, data: Tuple[float, float]) -> "Vector2D":
        """从元组创建"""
        return cls(x=data[0], y=data[1])

    @classmethod
    def from_player_dir(cls, direction: int) -> "Vector2D":
        """从玩家方向值创建向量 (0-7 方向)"""
        directions = [
            (0, -1),  # 0: 上
            (1, -1),  # 1: 右上
            (1, 0),  # 2: 右
            (1, 1),  # 3: 右下
            (0, 1),  # 4: 下
            (-1, 1),  # 5: 左下
            (-1, 0),  # 6: 左
            (-1, -1),  # 7: 左上
        ]
        if 0 <= direction < len(directions):
            dx, dy = directions[direction]
            return cls(x=float(dx), y=float(dy))
        return cls(0, 0)

    @staticmethod
    def direction_to_vector(dx: int, dy: int) -> Tuple[int, int]:
        """将移动方向转换为 0-7 方向值"""
        if dx == 0 and dy == -1:
            return 0  # 上
        elif dx == 1 and dy == -1:
            return 1  # 右上
        elif dx == 1 and dy == 0:
            return 2  # 右
        elif dx == 1 and dy == 1:
            return 3  # 右下
        elif dx == 0 and dy == 1:
            return 4  # 下
        elif dx == -1 and dy == 1:
            return 5  # 左下
        elif dx == -1 and dy == 0:
            return 6  # 左
        elif dx == -1 and dy == -1:
            return 7  # 左上
        return 0


@dataclass
class EntityData:
    """实体基础数据"""

    id: int
    entity_type: EntityType
    position: Vector2D
    velocity: Vector2D

    # 可选的额外属性
    collision_radius: float = 10.0
    subtype: int = 0

    # 跟踪信息
    first_seen_frame: int = 0
    last_seen_frame: int = 0
    state: ObjectState = ObjectState.ACTIVE

    # 历史轨迹 (最多保存最近60帧)
    position_history: List[Vector2D] = field(default_factory=list)
    velocity_history: List[Vector2D] = field(default_factory=list)

    def update_position(self, pos: Vector2D, vel: Vector2D, frame: int):
        """更新位置信息"""
        self.position = pos
        self.velocity = vel
        self.last_seen_frame = frame

        # 保存历史
        self.position_history.append(pos)
        self.velocity_history.append(vel)

        # 限制历史长度
        max_history = 60
        if len(self.position_history) > max_history:
            self.position_history = self.position_history[-max_history:]
            self.velocity_history = self.velocity_history[-max_history:]

    def predict_position(self, frames_ahead: int = 1) -> Vector2D:
        """预测未来位置"""
        if len(self.velocity_history) >= frames_ahead:
            # 使用最近的速度预测
            vel = self.velocity_history[-frames_ahead]
            return self.position + vel * frames_ahead
        elif self.velocity.magnitude() > 0:
            return self.position + self.velocity * frames_ahead
        return self.position

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "type": self.entity_type.value,
            "position": self.position.to_dict(),
            "velocity": self.velocity.to_dict(),
            "collision_radius": self.collision_radius,
            "subtype": self.subtype,
            "state": self.state.value,
        }


@dataclass
class PlayerData(EntityData):
    """玩家数据"""

    def __init__(
        self,
        player_idx: int = 1,
        position: Vector2D = None,
        velocity: Vector2D = None,
    ):
        super().__init__(
            id=player_idx,
            entity_type=EntityType.PLAYER,
            position=position or Vector2D(0, 0),
            velocity=velocity or Vector2D(0, 0),
        )
        self.player_idx = player_idx

        # 玩家属性
        self.player_type: int = 0
        self.health: float = 3.0
        self.max_health: float = 3.0
        self.damage: float = 3.0
        self.speed: float = 1.0
        self.tears: float = 10.0
        self.tear_range: float = 300.0
        self.shot_speed: float = 1.0
        self.luck: float = 0
        self.can_fly: bool = False
        self.size: float = 10.0

        # 方向 (0-7)
        self.facing_direction: int = 0

        # 主动道具
        self.active_item: Optional[int] = None
        self.active_charge: int = 0

        # 状态
        self.is_invincible: bool = False
        self.is_shooting: bool = False
        self.is_charging: bool = False


@dataclass
class EnemyData(EntityData):
    """敌人数据"""

    def __init__(
        self,
        enemy_id: int,
        position: Vector2D = None,
        velocity: Vector2D = None,
    ):
        super().__init__(
            id=enemy_id,
            entity_type=EntityType.ENEMY,
            position=position or Vector2D(0, 0),
            velocity=velocity or Vector2D(0, 0),
        )

        # 敌人属性
        self.enemy_type: int = 0
        self.hp: float = 10.0
        self.max_hp: float = 10.0
        self.damage: float = 1.0

        # 状态
        self.is_boss: bool = False
        self.is_champion: bool = False
        self.is_flying: bool = False

        # 攻击相关
        self.is_attacking: bool = False
        self.attack_cooldown: int = 0
        self.last_attack_frame: int = 0

    def get_threat_level(self) -> float:
        """获取威胁等级 (0-1)"""
        base_threat = min(self.hp / max(self.max_hp, 1), 1.0)

        # Boss 加成
        if self.is_boss:
            base_threat *= 2.0

        # Champion 加成
        if self.is_champion:
            base_threat *= 1.5

        return min(base_threat, 1.0)


@dataclass
class ProjectileData(EntityData):
    """投射物数据"""

    def __init__(
        self,
        projectile_id: int,
        position: Vector2D = None,
        velocity: Vector2D = None,
    ):
        super().__init__(
            id=projectile_id,
            entity_type=EntityType.PROJECTILE,
            position=position or Vector2D(0, 0),
            velocity=velocity or Vector2D(0, 0),
        )

        # 投射物属性
        self.projectile_type: int = 0
        self.damage: float = 1.0
        self.size: float = 5.0
        self.lifetime: int = 300  # 帧数
        self.is_enemy: bool = False  # 是否是敌人投射物

        # 特殊属性
        self.is_spectral: bool = False  # 是否穿墙
        self.is_homing: bool = False  # 是否追踪
        self.piercing: int = 0  # 穿透次数

    def predict_position(self, frames_ahead: int = 1) -> Vector2D:
        """预测未来位置（投射物使用匀速直线运动）"""
        return self.position + self.velocity * frames_ahead

    def will_hit(self, target_pos: Vector2D, target_radius: float = 10.0) -> bool:
        """检查是否会击中目标"""
        # 简化的碰撞检测
        distance = self.position.distance_to(target_pos)
        return distance <= (self.size + target_radius)


@dataclass
class RoomInfo:
    """房间信息"""

    room_index: int = -1
    stage: int = 1
    stage_type: int = 0
    difficulty: int = 0

    # 房间尺寸 (网格单位)
    grid_width: int = 13
    grid_height: int = 7

    # 像素尺寸
    pixel_width: int = 0
    pixel_height: int = 0

    # 房间类型
    room_type: str = "normal"  # normal, treasure, shop, boss, secret, etc.

    # 状态
    is_clear: bool = False
    enemy_count: int = 0


@dataclass
class GridTile:
    """网格瓦片"""

    x: int
    y: int
    tile_type: str = "empty"  # empty, wall, pit, door, spike, etc.
    is_solid: bool = False
    danger_level: float = 0.0

    # 特殊属性
    has_spikes: bool = False
    has_poop: bool = False
    has_rock: bool = False


@dataclass
class DoorData:
    """门数据"""

    direction: int  # 0-7 方向
    door_type: str = "door"  # door, gate, hidden, locked, etc.
    target_room: int = -1
    is_open: bool = False


@dataclass
class RoomLayout:
    """房间布局"""

    room_info: Optional[RoomInfo] = None

    # 网格数据
    grid: List[List[GridTile]] = field(default_factory=list)

    # 门
    doors: List[DoorData] = field(default_factory=list)

    # 特殊位置
    spawn_points: List[Vector2D] = field(default_factory=list)
    danger_zones: List[Tuple[Vector2D, float]] = field(
        default_factory=list
    )  # (中心, 半径)

    # 障碍物列表 (用于路径规划)
    obstacles: List[Tuple[Vector2D, float]] = field(
        default_factory=list
    )  # (中心, 半径)

    def __post_init__(self):
        if not self.grid and self.room_info:
            self._init_grid()

    def _init_grid(self):
        """初始化网格"""
        self.grid = [
            [
                GridTile(x=x, y=y, tile_type="empty", is_solid=False)
                for y in range(self.room_info.grid_height)
            ]
            for x in range(self.room_info.grid_width)
        ]

    def is_wall(self, x: int, y: int) -> bool:
        """检查位置是否为墙"""
        if 0 <= x < len(self.grid) and 0 <= y < len(self.grid[0]):
            return self.grid[x][y].is_solid
        return True

    def get_tile(self, x: int, y: int) -> Optional[GridTile]:
        """获取瓦片"""
        if 0 <= x < len(self.grid) and 0 <= y < len(self.grid[0]):
            return self.grid[x][y]
        return None

    def world_to_grid(self, pos: Vector2D) -> Tuple[int, int]:
        """世界坐标转网格坐标"""
        tile_size = 40  # 每个瓦片 40 像素
        return (int(pos.x / tile_size), int(pos.y / tile_size))

    def grid_to_world(self, grid_x: int, grid_y: int) -> Vector2D:
        """网格坐标转世界坐标"""
        tile_size = 40
        return Vector2D(
            x=grid_x * tile_size + tile_size / 2,
            y=grid_y * tile_size + tile_size / 2,
        )

    def add_obstacle(self, center: Vector2D, radius: float):
        """添加障碍物"""
        self.obstacles.append((center, radius))

    def find_nearby_safe_spot(
        self, player_pos: Vector2D, min_distance: float, max_distance: float
    ) -> Optional[Vector2D]:
        """寻找附近的安全位置"""
        # 简化的安全位置查找
        grid_pos = self.world_to_grid(player_pos)

        for d in range(int(min_distance / 40), int(max_distance / 40) + 1):
            # 检查周围环
            for dx in range(-d, d + 1):
                for dy in range(-d, d + 1):
                    if abs(dx) != d and abs(dy) != d:
                        continue

                    check_x = grid_pos[0] + dx
                    check_y = grid_pos[1] + dy

                    if not self.is_wall(check_x, check_y):
                        return self.grid_to_world(check_x, check_y)

        return None


@dataclass
class GameStateData:
    """游戏状态数据 (增量更新)"""

    # 时间信息
    frame: int = 0
    timestamp: int = 0

    # 房间信息
    room_index: int = -1
    room_info: Optional[RoomInfo] = None
    room_layout: Optional[RoomLayout] = None

    # 玩家 (key: player_idx)
    players: Dict[int, PlayerData] = field(default_factory=dict)

    # 敌人 (key: enemy_id)
    enemies: Dict[int, EnemyData] = field(default_factory=dict)

    # 投射物 (key: projectile_id)
    projectiles: Dict[int, ProjectileData] = field(default_factory=dict)

    # 激光 (key: laser_id)
    lasers: Dict[int, "LaserData"] = field(default_factory=dict)

    # 拾取物 (key: pickup_id)
    pickups: Dict[int, "PickupData"] = field(default_factory=dict)

    # 障碍物 (key: obstacle_id)
    obstacles: Dict[int, "DestructibleData"] = field(default_factory=dict)

    # 按类型分组（便于访问）
    @property
    def active_enemies(self) -> List[EnemyData]:
        """获取活跃敌人列表"""
        return [e for e in self.enemies.values() if e.state == ObjectState.ACTIVE]

    @property
    def enemy_projectiles(self) -> List[ProjectileData]:
        """获取敌人投射物列表"""
        return [p for p in self.projectiles.values() if p.is_enemy]

    @property
    def player_projectiles(self) -> List[ProjectileData]:
        """获取玩家投射物列表"""
        return [p for p in self.projectiles.values() if not p.is_enemy]

    # 便捷方法
    def get_primary_player(self) -> Optional[PlayerData]:
        """获取主玩家"""
        return self.players.get(1)

    def get_nearest_enemy(self, player_pos: Vector2D) -> Optional[EnemyData]:
        """获取最近的敌人"""
        nearest = None
        min_dist = float("inf")

        for enemy in self.active_enemies:
            dist = enemy.position.distance_to(player_pos)
            if dist < min_dist:
                min_dist = dist
                nearest = enemy

        return nearest

    def get_enemies_in_range(
        self, player_pos: Vector2D, max_distance: float
    ) -> List[EnemyData]:
        """获取范围内的敌人"""
        return [
            e
            for e in self.active_enemies
            if e.position.distance_to(player_pos) <= max_distance
        ]

    def get_threat_count(self) -> int:
        """获取威胁数量（活跃敌人 + 敌人投射物）"""
        return len(self.active_enemies) + len(self.enemy_projectiles)


@dataclass
class ControlOutput:
    """控制输出"""

    move_x: int = 0  # X 方向移动 (-1, 0, 1)
    move_y: int = 0  # Y 方向移动 (-1, 0, 1)
    shoot: bool = False  # 是否射击
    shoot_x: int = 0  # 射击方向 X
    shoot_y: int = 0  # 射击方向 Y
    use_item: bool = False  # 使用主动道具
    use_bomb: bool = False  # 放置炸弹
    drop: bool = False  # 丢弃物品
    confidence: float = 1.0  # 置信度 (0-1)
    reasoning: str = ""  # 决策原因

    def to_input(self) -> Tuple[Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
        """转换为 isaac_bridge 输入格式"""
        move = None
        if self.move_x != 0 or self.move_y != 0:
            move = (self.move_x, self.move_y)

        shoot = None
        if self.shoot:
            shoot = (self.shoot_x, self.shoot_y)

        return move, shoot


# 为了向后兼容，添加简化的类型别名
@dataclass
class LaserData(EntityData):
    """激光数据"""

    def __init__(
        self,
        laser_id: int,
        position: Vector2D = None,
        velocity: Vector2D = None,
    ):
        super().__init__(
            id=laser_id,
            entity_type=EntityType.LASER,
            position=position or Vector2D(0, 0),
            velocity=velocity or Vector2D(0, 0),
        )
        self.width: float = 10.0
        self.length: float = 100.0
        self.damage: float = 1.0
        self.duration: int = 30


@dataclass
class PickupData(EntityData):
    """拾取物数据"""

    def __init__(
        self,
        pickup_id: int,
        position: Vector2D = None,
        velocity: Vector2D = None,
    ):
        super().__init__(
            id=pickup_id,
            entity_type=EntityType.PICKUP,
            position=position or Vector2D(0, 0),
            velocity=velocity or Vector2D(0, 0),
        )
        self.pickup_type: int = 0
        self.sub_type: int = 0
        self.variant: int = 0
        self.is_shop_item: bool = False
        self.price: int = 0


@dataclass
class DestructibleData(EntityData):
    """可破坏物数据"""

    def __init__(
        self,
        obj_id: int,
        position: Vector2D = None,
        velocity: Vector2D = None,
    ):
        super().__init__(
            id=obj_id,
            entity_type=EntityType.DESTRUCTIBLE,
            position=position or Vector2D(0, 0),
            velocity=velocity or Vector2D(0, 0),
        )
        self.obj_type: int = 0
        self.variant: int = 0
        self.hp: int = 1


@dataclass
class BombData(EntityData):
    """炸弹数据"""

    def __init__(
        self,
        bomb_id: int,
        position: Vector2D = None,
        velocity: Vector2D = None,
    ):
        super().__init__(
            id=bomb_id,
            entity_type=EntityType.BOMB,
            position=position or Vector2D(0, 0),
            velocity=velocity or Vector2D(0, 0),
        )
        self.damage: float = 100.0
        self.radius: float = 100.0
        self.timer: int = 90  # 帧数
        self.is_player_bomb: bool = True
