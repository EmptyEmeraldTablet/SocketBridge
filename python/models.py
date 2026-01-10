"""
数据模型层

定义游戏实体的标准化数据结构，包括玩家、敌人、投射物等。
提供统一的数据访问接口，支持增量更新。

根据 DATA_PROTOCOL.md 中的数据格式定义。
"""

import math
from typing import Dict, List, Optional, Tuple, Any
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

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "Vector2D":
        """从字典创建"""
        return cls(x=data.get("x", 0), y=data.get("y", 0))

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
            return Vector2D(float(dx), float(dy))
        return Vector2D(0, 0)


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
        return self.position + self.velocity * frames_ahead

    def get_avg_velocity(self, recent_frames: int = 10) -> Vector2D:
        """获取最近几帧的平均速度"""
        if not self.velocity_history:
            return self.velocity

        recent = self.velocity_history[-recent_frames:]
        avg_x = sum(v.x for v in recent) / len(recent)
        avg_y = sum(v.y for v in recent) / len(recent)
        return Vector2D(avg_x, avg_y)

    def is_alive(self) -> bool:
        """是否存活"""
        return self.state == ObjectState.ACTIVE


@dataclass
class PlayerData:
    """玩家数据"""

    player_idx: int

    # 位置信息
    position: Vector2D = field(default_factory=lambda: Vector2D(0, 0))
    velocity: Vector2D = field(default_factory=lambda: Vector2D(0, 0))
    move_direction: int = 0
    fire_direction: int = 0
    head_direction: int = 0
    aim_direction: Vector2D = field(default_factory=lambda: Vector2D(0, 0))

    # 属性
    player_type: int = 0
    damage: float = 3.0
    speed: float = 1.0
    tears: float = 10.0
    shot_range: int = 300
    tear_range: int = 300
    shot_speed: float = 1.0
    luck: int = 0
    can_fly: bool = False
    size: float = 10.0
    sprite_scale: float = 1.0

    # 生命值
    red_hearts: int = 0
    max_hearts: int = 6
    soul_hearts: int = 0
    black_hearts: int = 0
    bone_hearts: int = 0
    golden_hearts: int = 0
    eternal_hearts: int = 0
    rotten_hearts: int = 0
    broken_hearts: int = 0
    extra_lives: int = 0

    # 物品栏
    coins: int = 0
    bombs: int = 0
    keys: int = 0
    collectibles: Dict[str, int] = field(default_factory=dict)
    active_items: Dict[str, Dict] = field(default_factory=dict)

    @property
    def total_hearts(self) -> int:
        """获取总心数"""
        return self.red_hearts + self.soul_hearts + self.black_hearts + self.bone_hearts

    @property
    def health_percentage(self) -> float:
        """获取血量百分比"""
        if self.max_hearts == 0:
            return 0.0
        return min(1.0, self.total_hearts / self.max_hearts)

    def has_black_heart(self) -> bool:
        """是否有黑心（可以触发恶魔房交易）"""
        return self.black_hearts > 0

    def has_active_item(self, item_id: int) -> bool:
        """检查是否有特定主动道具"""
        item_str = str(item_id)
        return item_str in self.active_items


@dataclass
class EnemyData:
    """敌人数据"""

    id: int
    enemy_type: int  # 游戏内类型
    variant: int = 0
    subtype: int = 0

    position: Vector2D = field(default_factory=lambda: Vector2D(0, 0))
    velocity: Vector2D = field(default_factory=lambda: Vector2D(0, 0))

    hp: float = 0.0
    max_hp: float = 0.0

    is_boss: bool = False
    is_champion: bool = False

    # 状态
    state: int = 0
    state_frame: int = 0

    # 攻击相关
    projectile_cooldown: int = 0
    projectile_delay: int = 60
    collision_radius: float = 15.0

    # 额外字段（来自DATA_PROTOCOL）
    target_position: Vector2D = field(default_factory=lambda: Vector2D(0, 0))
    distance: float = 9999.0

    def get_threat_level(self) -> float:
        """计算威胁等级 (0-1)"""
        if self.hp <= 0:
            return 0.0

        # 基于距离和HP计算威胁
        distance_factor = max(0, 1.0 - self.distance / 500)  # 500像素内才有威胁
        health_factor = self.hp / max(1.0, self.max_hp)

        # Boss更高威胁
        boss_factor = 2.0 if self.is_boss else 1.0
        champion_factor = 1.5 if self.is_champion else 1.0

        threat = distance_factor * health_factor * boss_factor * champion_factor
        return min(1.0, threat)

    def is_about_to_attack(self, current_frame: int) -> bool:
        """是否即将攻击"""
        return self.projectile_cooldown <= 10 and self.projectile_cooldown > 0


@dataclass
class ProjectileData:
    """投射物数据"""

    id: int
    is_enemy: bool

    position: Vector2D = field(default_factory=lambda: Vector2D(0, 0))
    velocity: Vector2D = field(default_factory=lambda: Vector2D(0, 0))

    variant: int = 0
    collision_radius: float = 8.0

    # 特殊属性
    height: float = 0.0  # 用于抛物线
    falling_speed: float = 0.0
    falling_acceleration: float = 0.0
    scale: float = 1.0

    def predict_position(self, frames: int = 1) -> Vector2D:
        """预测未来位置（简单线性预测）"""
        return self.position + self.velocity * frames

    def get_time_to_impact(self, target_pos: Vector2D) -> Optional[float]:
        """计算到达目标位置的预估时间"""
        if self.velocity.magnitude() == 0:
            return None

        direction = self.velocity.normalized()
        to_target = target_pos - self.position

        # 检查是否朝向目标
        dot = direction.dot(to_target)
        if dot < 0:
            return None

        distance = to_target.magnitude()
        speed = self.velocity.magnitude()

        return distance / speed if speed > 0 else None


@dataclass
class LaserData:
    """激光数据"""

    id: int
    is_enemy: bool

    position: Vector2D = field(default_factory=lambda: Vector2D(0, 0))
    angle: float = 0.0  # 度
    max_distance: float = 500.0

    def get_direction_vector(self) -> Vector2D:
        """获取激光方向向量"""
        rad = math.radians(self.angle)
        return Vector2D(math.cos(rad), math.sin(rad))

    def get_end_position(self) -> Vector2D:
        """获取激光终点"""
        direction = self.get_direction_vector()
        return self.position + direction * self.max_distance


@dataclass
class RoomInfo:
    """房间信息"""

    room_type: int = 0
    room_shape: int = 0
    room_index: int = 0
    stage: int = 0
    stage_type: int = 0
    difficulty: int = 0
    is_clear: bool = False
    is_first_visit: bool = True

    grid_width: int = 13
    grid_height: int = 7

    top_left: Vector2D = field(default_factory=lambda: Vector2D(0, 0))
    bottom_right: Vector2D = field(default_factory=lambda: Vector2D(832, 448))

    has_boss: bool = False
    enemy_count: int = 0
    room_variant: int = 0

    @property
    def center(self) -> Vector2D:
        """获取房间中心点"""
        return (self.top_left + self.bottom_right) / 2

    @property
    def width(self) -> float:
        """获取房间宽度"""
        return self.bottom_right.x - self.top_left.x

    @property
    def height(self) -> float:
        """获取房间高度"""
        return self.bottom_right.y - self.top_left.y


@dataclass
class GridTile:
    """网格瓷砖数据"""

    grid_index: int
    tile_type: int
    variant: int = 0
    variant_name: str = "UNKNOWN"
    state: int = 0
    has_collision: bool = True
    position: Vector2D = field(default_factory=lambda: Vector2D(0, 0))

    # 障碍物类型常量
    TYPE_ROCK = 1000
    TYPE_STONE = 1001
    TYPE_CRACKED = 1002
    TYPE_SPIKES = 8
    TYPE_POISON_SPIKES = 9
    TYPE_WEB = 10

    def is_solid(self) -> bool:
        """是否为固体障碍物"""
        return self.has_collision and self.tile_type >= 1000

    def is_hazard(self) -> bool:
        """是否为危险物（尖刺等）"""
        return self.tile_type in [
            self.TYPE_SPIKES,
            self.TYPE_POISON_SPIKES,
            self.TYPE_WEB,
        ]


@dataclass
class DoorData:
    """门数据"""

    door_slot: int  # 0=左, 1=上, 2=右, 3=下
    target_room: int = -1
    target_room_type: int = 0
    is_open: bool = False
    is_locked: bool = False

    @property
    def direction(self) -> Vector2D:
        """获取门的方向"""
        directions = [
            Vector2D(-1, 0),  # 0: 左
            Vector2D(0, -1),  # 1: 上
            Vector2D(1, 0),  # 2: 右
            Vector2D(0, 1),  # 3: 下
        ]
        if 0 <= self.door_slot < len(directions):
            return directions[self.door_slot]
        return Vector2D(0, 0)


@dataclass
class RoomLayout:
    """房间布局"""

    grid_size: float = 91.0
    width: int = 13
    height: int = 7

    tiles: Dict[int, GridTile] = field(default_factory=dict)
    doors: Dict[int, DoorData] = field(default_factory=dict)

    def get_tile_at_position(self, pos: Vector2D) -> Optional[GridTile]:
        """根据位置获取对应的瓷砖"""
        grid_x = int(pos.x / self.grid_size)
        grid_y = int(pos.y / self.grid_size)
        grid_index = grid_y * self.width + grid_x
        return self.tiles.get(grid_index)

    def is_walkable(self, pos: Vector2D, player_radius: float = 15.0) -> bool:
        """检查位置是否可通行"""
        # 检查中心点
        center_tile = self.get_tile_at_position(pos)
        if center_tile and center_tile.is_solid():
            return False

        # 检查边缘（考虑碰撞半径）
        margin = player_radius
        offsets = [
            Vector2D(margin, 0),
            Vector2D(-margin, 0),
            Vector2D(0, margin),
            Vector2D(0, -margin),
        ]

        for offset in offsets:
            check_pos = pos + offset
            tile = self.get_tile_at_position(check_pos)
            if tile and tile.is_solid():
                return False

        return True


@dataclass
class ButtonData:
    """按钮数据"""

    button_idx: int
    button_type: int
    variant: int = 0
    variant_name: str = "NORMAL"
    state: int = 0
    is_pressed: bool = False
    position: Vector2D = field(default_factory=lambda: Vector2D(0, 0))
    distance: float = 0.0


@dataclass
class BombData:
    """炸弹数据"""

    id: int
    bomb_type: int
    variant: int = 0
    variant_name: str = "NORMAL"
    sub_type: int = 0

    position: Vector2D = field(default_factory=lambda: Vector2D(0, 0))
    velocity: Vector2D = field(default_factory=lambda: Vector2D(0, 0))

    explosion_radius: float = 80.0
    timer: int = 60
    distance: float = 0.0

    def is_dangerous(self) -> bool:
        """是否危险（即将爆炸）"""
        return self.timer < 30 or "TROLL" in self.variant_name


@dataclass
class InteractableData:
    """可互动实体数据"""

    id: int
    entity_type: int
    variant: int = 0
    variant_name: str = "UNKNOWN"
    sub_type: int = 0

    position: Vector2D = field(default_factory=lambda: Vector2D(0, 0))
    velocity: Vector2D = field(default_factory=lambda: Vector2D(0, 0))

    state: int = 0
    state_frame: int = 0
    distance: float = 0.0

    # 特殊属性
    target_position: Vector2D = field(default_factory=lambda: Vector2D(0, 0))


@dataclass
class PickupData:
    """可拾取物数据"""

    id: int
    variant: int = 0
    sub_type: int = 0

    position: Vector2D = field(default_factory=lambda: Vector2D(0, 0))

    price: int = 0
    shop_item_id: int = -1
    wait: int = 0

    # 拾取物类型常量
    TYPE_HEART = 10
    TYPE_COIN = 12
    TYPE_KEY = 15
    TYPE_BOMB = 17
    TYPE_COLLECTIBLE = 20
    TYPE_SHOP_ITEM = 21

    def is_free(self) -> bool:
        """是否免费"""
        return self.price == 0


@dataclass
class FireHazardData:
    """火焰危险物数据"""

    id: int
    fire_type: str = "NORMAL"
    variant: int = 0
    sub_variant: int = 0

    position: Vector2D = field(default_factory=lambda: Vector2D(0, 0))

    hp: float = 5.0
    max_hp: float = 10.0
    state: int = 0
    is_extinguished: bool = False
    is_shooting: bool = False

    collision_radius: float = 25.0
    distance: float = 0.0
    sprite_scale: float = 1.0


@dataclass
class DestructibleData:
    """可破坏障碍物数据"""

    grid_index: int
    obj_type: int
    name: str = "UNKNOWN"

    position: Vector2D = field(default_factory=lambda: Vector2D(0, 0))

    state: int = 0
    distance: float = 0.0
    variant: int = 0
    variant_name: str = "NORMAL"

    # 类型常量
    TYPE_TNT = 12
    TYPE_POOP = 14

    def is_explosive(self) -> bool:
        """是否可爆炸"""
        return self.obj_type == self.TYPE_TNT


@dataclass
class GameStateData:
    """完整游戏状态数据容器

    整合所有游戏数据，为AI系统提供统一的数据访问接口。
    """

    # 帧信息
    frame: int = 0
    room_index: int = -1

    # 玩家数据 (1-based index)
    players: Dict[int, PlayerData] = field(default_factory=dict)

    # 房间数据
    room_info: Optional[RoomInfo] = None
    room_layout: Optional[RoomLayout] = None

    # 敌人
    enemies: Dict[int, EnemyData] = field(default_factory=dict)

    # 投射物
    enemy_projectiles: Dict[int, ProjectileData] = field(default_factory=dict)
    player_projectiles: Dict[int, ProjectileData] = field(default_factory=dict)
    lasers: Dict[int, LaserData] = field(default_factory=dict)

    # 环境物体
    buttons: Dict[int, ButtonData] = field(default_factory=dict)
    bombs: Dict[int, BombData] = field(default_factory=dict)
    interactables: Dict[int, InteractableData] = field(default_factory=dict)
    pickups: Dict[int, PickupData] = field(default_factory=dict)
    fire_hazards: Dict[int, FireHazardData] = field(default_factory=dict)
    destructibles: Dict[int, DestructibleData] = field(default_factory=dict)

    # 便捷方法
    def get_primary_player(self) -> Optional[PlayerData]:
        """获取主要玩家（索引1）"""
        return self.players.get(1)

    def get_active_enemies(self) -> List[EnemyData]:
        """获取所有存活的敌人"""
        return [e for e in self.enemies.values() if e.hp > 0]

    def get_nearest_enemy(self, pos: Vector2D) -> Optional[EnemyData]:
        """获取最近的敌人"""
        enemies = self.get_active_enemies()
        if not enemies:
            return None
        return min(enemies, key=lambda e: e.position.distance_to(pos))

    def get_threatening_projectiles(
        self, pos: Vector2D, max_distance: float = 200.0
    ) -> List[ProjectileData]:
        """获取有威胁的敌方投射物"""
        threats = []
        for proj in self.enemy_projectiles.values():
            dist = proj.position.distance_to(pos)
            if dist <= max_distance:
                # 检查是否朝向玩家
                direction = proj.velocity.normalized()
                to_player = (pos - proj.position).normalized()
                dot = direction.dot(to_player)
                if dot > 0.7:
                    threats.append(proj)
        return threats

    def is_combat_active(self) -> bool:
        """是否有活跃的战斗"""
        return (
            len(self.get_active_enemies()) > 0
            or len(self.get_threatening_projectiles(Vector2D(0, 0))) > 0
        )
