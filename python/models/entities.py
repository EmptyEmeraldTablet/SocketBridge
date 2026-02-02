from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from .base import Vector2D, EntityType, ObjectState


@dataclass
class EntityData:
    id: int
    entity_type: EntityType
    position: Vector2D
    velocity: Vector2D
    collision_radius: float = 10.0
    subtype: int = 0
    first_seen_frame: int = 0
    last_seen_frame: int = 0
    state: ObjectState = ObjectState.ACTIVE
    position_history: List[Vector2D] = field(default_factory=list)
    velocity_history: List[Vector2D] = field(default_factory=list)

    def update_position(self, pos: Vector2D, vel: Vector2D, frame: int):
        self.position = pos
        self.velocity = vel
        self.last_seen_frame = frame
        self.position_history.append(pos)
        self.velocity_history.append(vel)
        max_history = 60
        if len(self.position_history) > max_history:
            self.position_history = self.position_history[-max_history:]
            self.velocity_history = self.velocity_history[-max_history:]

    def predict_position(self, frames_ahead: int = 1) -> Vector2D:
        if len(self.velocity_history) >= frames_ahead:
            vel = self.velocity_history[-frames_ahead]
            return self.position + vel * frames_ahead
        elif self.velocity.magnitude() > 0:
            return self.position + self.velocity * frames_ahead
        return self.position

    def to_dict(self) -> Dict[str, Any]:
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
        self.facing_direction: int = 0
        self.active_item: Optional[int] = None
        self.active_charge: int = 0
        self.is_invincible: bool = False
        self.is_shooting: bool = False
        self.is_charging: bool = False

    def get_stats(
        self, player_stats: Optional["PlayerStatsData"] = None
    ) -> "PlayerStatsData":
        if player_stats is not None:
            return player_stats
        return PlayerStatsData(
            player_idx=self.player_idx,
            player_type=self.player_type,
            damage=self.damage,
            speed=self.speed,
            tears=self.tears,
            tear_range=self.tear_range,
            shot_speed=self.shot_speed,
            luck=self.luck,
            can_fly=self.can_fly,
            size=self.size,
            active_item=self.active_item,
            active_charge=self.active_charge,
        )


@dataclass
class EnemyData(EntityData):
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
        self.enemy_type: int = 0
        self.hp: float = 10.0
        self.max_hp: float = 10.0
        self.damage: float = 1.0
        self.is_boss: bool = False
        self.is_champion: bool = False
        self.is_flying: bool = False
        self.is_attacking: bool = False
        self.attack_cooldown: int = 0
        self.last_attack_frame: int = 0

    def get_threat_level(self) -> float:
        base_threat = min(self.hp / max(self.max_hp, 1), 1.0)
        if self.is_boss:
            base_threat *= 2.0
        if self.is_champion:
            base_threat *= 1.5
        return min(base_threat, 1.0)


@dataclass
class ProjectileData(EntityData):
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
        self.projectile_type: int = 0
        self.damage: float = 1.0
        self.size: float = 5.0
        self.lifetime: int = 300
        self.is_enemy: bool = False
        self.is_spectral: bool = False
        self.is_homing: bool = False
        self.piercing: int = 0

    def predict_position(self, frames_ahead: int = 1) -> Vector2D:
        return self.position + self.velocity * frames_ahead

    def will_hit(self, target_pos: Vector2D, target_radius: float = 10.0) -> bool:
        distance = self.position.distance_to(target_pos)
        return distance <= (self.size + target_radius)


@dataclass
class RoomInfo:
    room_index: int = -1
    stage: int = 1
    stage_type: int = 0
    difficulty: int = 0
    grid_width: int = 13
    grid_height: int = 7
    pixel_width: int = 0
    pixel_height: int = 0
    top_left: Optional[Tuple[float, float]] = None
    bottom_right: Optional[Tuple[float, float]] = None
    room_type: str = "normal"
    room_shape: int = 0
    is_clear: bool = False
    enemy_count: int = 0


@dataclass
class GridTile:
    x: int
    y: int
    tile_type: str = "empty"
    is_solid: bool = False
    danger_level: float = 0.0
    has_spikes: bool = False
    has_poop: bool = False
    has_rock: bool = False


@dataclass
class DoorData:
    direction: int
    door_type: str = "door"
    target_room: int = -1
    is_open: bool = False


@dataclass
class RoomLayout:
    room_info: Optional[RoomInfo] = None
    grid: List[List[GridTile]] = field(default_factory=list)
    doors: List[DoorData] = field(default_factory=list)
    spawn_points: List[Vector2D] = field(default_factory=list)
    danger_zones: List[Tuple[Vector2D, float]] = field(default_factory=list)
    obstacles: List[Tuple[Vector2D, float]] = field(default_factory=list)

    def __post_init__(self):
        if not self.grid and self.room_info:
            self._init_grid()

    def _init_grid(self):
        self.grid = [
            [
                GridTile(x=x, y=y, tile_type="empty", is_solid=False)
                for y in range(self.room_info.grid_height)
            ]
            for x in range(self.room_info.grid_width)
        ]

    def is_wall(self, x: int, y: int) -> bool:
        if 0 <= x < len(self.grid) and 0 <= y < len(self.grid[0]):
            return self.grid[x][y].is_solid
        return True

    def get_tile(self, x: int, y: int) -> Optional[GridTile]:
        if 0 <= x < len(self.grid) and 0 <= y < len(self.grid[0]):
            return self.grid[x][y]
        return None

    def world_to_grid(self, pos: Vector2D) -> Tuple[int, int]:
        tile_size = 40
        return (int(pos.x / tile_size), int(pos.y / tile_size))

    def grid_to_world(self, grid_x: int, grid_y: int) -> Vector2D:
        tile_size = 40
        return Vector2D(
            x=grid_x * tile_size + tile_size / 2,
            y=grid_y * tile_size + tile_size / 2,
        )

    def add_obstacle(self, center: Vector2D, radius: float):
        self.obstacles.append((center, radius))

    def find_nearby_safe_spot(
        self, player_pos: Vector2D, min_distance: float, max_distance: float
    ) -> Optional[Vector2D]:
        grid_pos = self.world_to_grid(player_pos)
        for d in range(int(min_distance / 40), int(max_distance / 40) + 1):
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
class LaserData(EntityData):
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
        self.timer: int = 90
        self.is_player_bomb: bool = True


@dataclass
class ButtonData(EntityData):
    def __init__(
        self,
        button_id: int,
        position: Vector2D = None,
        velocity: Vector2D = None,
    ):
        super().__init__(
            id=button_id,
            entity_type=EntityType.BUTTON,
            position=position or Vector2D(0, 0),
            velocity=velocity or Vector2D(0, 0),
        )
        self.button_type: int = 0
        self.variant: int = 0
        self.variant_name: str = "NORMAL"
        self.state: int = 0
        self.is_pressed: bool = False
        self.distance: float = 0.0


@dataclass
class FireHazardData(EntityData):
    def __init__(
        self,
        fire_id: int,
        position: Vector2D = None,
        velocity: Vector2D = None,
    ):
        super().__init__(
            id=fire_id,
            entity_type=EntityType.FIRE_HAZARD,
            position=position or Vector2D(0, 0),
            velocity=velocity or Vector2D(0, 0),
        )
        self.fire_type: str = "NORMAL"
        self.variant: int = 0
        self.hp: float = 10.0
        self.max_hp: float = 10.0
        self.is_extinguished: bool = False
        self.is_shooting: bool = False
        self.collision_radius: float = 25.0


@dataclass
class InteractableData(EntityData):
    def __init__(
        self,
        entity_id: int,
        position: Vector2D = None,
        velocity: Vector2D = None,
    ):
        super().__init__(
            id=entity_id,
            entity_type=EntityType.INTERACTABLE,
            position=position or Vector2D(0, 0),
            velocity=velocity or Vector2D(0, 0),
        )
        self.entity_type: int = 0
        self.variant: int = 0
        self.variant_name: str = "UNKNOWN"
        self.sub_type: int = 0
        self.state: int = 0
        self.state_frame: int = 0


@dataclass
class PlayerHealthData:
    player_idx: int = 1
    red_hearts: int = 0
    max_red_hearts: int = 0
    soul_hearts: int = 0
    black_hearts: int = 0
    bone_hearts: int = 0
    golden_hearts: int = 0
    eternal_hearts: int = 0
    rotten_hearts: int = 0
    broken_hearts: int = 0
    extra_lives: int = 0

    @property
    def total_hearts(self) -> float:
        return self.red_hearts + self.soul_hearts * 0.5

    @property
    def max_hearts(self) -> int:
        return self.max_red_hearts


@dataclass
class PlayerStatsData:
    player_idx: int = 1
    player_type: int = 0
    damage: float = 3.0
    speed: float = 1.0
    tears: float = 10.0
    tear_range: float = 300.0
    shot_speed: float = 1.0
    luck: int = 0
    can_fly: bool = False
    size: float = 10.0
    active_item: Optional[int] = None
    active_charge: int = 0
    max_charge: int = 0


@dataclass
class PlayerInventoryData:
    player_idx: int = 1
    coins: int = 0
    bombs: int = 0
    keys: int = 0
    trinket_0: int = 0
    trinket_1: int = 0
    card_0: int = 0
    pill_0: int = 0
    collectible_count: int = 0
    collectibles: Dict[str, int] = field(default_factory=dict)
    active_items: Dict[str, Dict[str, int]] = field(default_factory=dict)
