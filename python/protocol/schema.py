"""
Protocol Schema — unified Pydantic models for ALL entity and message types.

This is the SINGLE source of truth for data types in SocketBridge v3.0.
Replaces: models/base.py, models/entities.py, core/protocol/schema.py.

Design principles:
- Every entity has exactly ONE Pydantic model (no dataclass duplicates)
- Naming: short, unambiguous (Enemy not EnemyData, PlayerPosition not PlayerPositionData)
- All models use `model_config = {"extra": "allow"}` for forward compatibility
- Field defaults match what the Lua API actually returns
- Validators handle known game-side quirks (negative HP, zero aim_dir, etc.)
"""

from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════════════
# Primitives
# ═══════════════════════════════════════════════════════════════════════════════

class Vector2D(BaseModel):
    """2D vector — used for positions, velocities, directions."""
    x: float = 0.0
    y: float = 0.0

    model_config = {"extra": "forbid"}

    def __add__(self, other: "Vector2D") -> "Vector2D":
        return Vector2D(x=self.x + other.x, y=self.y + other.y)

    def __sub__(self, other: "Vector2D") -> "Vector2D":
        return Vector2D(x=self.x - other.x, y=self.y - other.y)

    def __mul__(self, s: float) -> "Vector2D":
        return Vector2D(x=self.x * s, y=self.y * s)

    def __truediv__(self, s: float) -> "Vector2D":
        if s == 0:
            return Vector2D()
        return Vector2D(x=self.x / s, y=self.y / s)

    def magnitude(self) -> float:
        return (self.x ** 2 + self.y ** 2) ** 0.5

    def distance_to(self, other: "Vector2D") -> float:
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5

    def to_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)

    @field_validator("x", "y", mode="before")
    @classmethod
    def _coerce_float(cls, v):
        if v is None:
            return 0.0
        return float(v)


class CollectInterval(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    RARE = "RARE"
    ON_CHANGE = "ON_CHANGE"


class MessageType(str, Enum):
    DATA = "DATA"
    FULL = "FULL"
    EVENT = "EVENT"
    COMMAND = "CMD"
    SUBSCRIBE = "SUBSCRIBE"
    SUBSCRIBE_ACK = "SUBSCRIBE_ACK"
    CONFIGURE_SENSOR = "CONFIGURE_SENSOR"


class EntityLifecycle(str, Enum):
    APPEARED = "appeared"
    ACTIVE = "active"
    UPDATED = "updated"
    DYING = "dying"
    REMOVED = "removed"


# ═══════════════════════════════════════════════════════════════════════════════
# Player sensors
# ═══════════════════════════════════════════════════════════════════════════════

class PlayerPosition(BaseModel):
    """PLAYER_POSITION — collected every frame."""
    pos: Vector2D = Field(default_factory=Vector2D)
    vel: Vector2D = Field(default_factory=Vector2D)
    move_dir: int = Field(default=0, ge=-1, le=7)
    fire_dir: int = Field(default=0, ge=-1, le=7)
    head_dir: int = Field(default=0, ge=-1, le=7)
    aim_dir: Vector2D = Field(default_factory=Vector2D)

    model_config = {"extra": "allow"}


class PlayerStats(BaseModel):
    """PLAYER_STATS — collected every 30 frames."""
    player_type: int = 0
    damage: float = Field(default=3.5, ge=0.0)
    speed: float = Field(default=1.0, ge=0.0)
    tears: float = Field(default=10.0, ge=0.0)
    range: float = Field(default=300.0, ge=0.0)
    tear_range: float = Field(default=300.0, ge=0.0)
    shot_speed: float = Field(default=1.0, ge=0.0)
    luck: int = Field(default=0, ge=-10, le=120)
    tear_height: float = Field(default=0.0)
    tear_falling_speed: float = Field(default=0.0)
    can_fly: bool = False
    size: float = Field(default=10.0, ge=0.0)
    sprite_scale: float = Field(default=1.0, ge=0.0)

    model_config = {"extra": "allow"}

    @field_validator("luck", mode="before")
    @classmethod
    def _coerce_luck(cls, v):
        if v is None:
            return 0
        return int(float(v))


class PlayerHealth(BaseModel):
    """PLAYER_HEALTH — collected every 30 frames."""
    red_hearts: int = Field(default=0, ge=0)
    max_hearts: float = Field(default=0.0, ge=0.0)
    soul_hearts: int = Field(default=0, ge=0)
    black_hearts: int = Field(default=0, ge=0)
    bone_hearts: int = Field(default=0, ge=0)
    golden_hearts: int = Field(default=0, ge=0)
    eternal_hearts: int = Field(default=0, ge=0)
    rotten_hearts: int = Field(default=0, ge=0)
    broken_hearts: int = Field(default=0, ge=0)
    extra_lives: int = Field(default=0, ge=0)

    model_config = {"extra": "allow"}


class ActiveItem(BaseModel):
    """Active item slot data."""
    item: int = 0
    charge: int = 0
    max_charge: int = 0
    battery_charge: int = 0

    model_config = {"extra": "allow"}


class PlayerInventory(BaseModel):
    """PLAYER_INVENTORY — collected every 90 frames."""
    coins: int = Field(default=0, ge=0)
    bombs: int = Field(default=0, ge=0)
    keys: int = Field(default=0, ge=0)
    trinket_0: int = 0
    trinket_1: int = 0
    card_0: int = 0
    pill_0: int = 0
    collectible_count: int = Field(default=0, ge=0)
    collectibles: dict[str, int] = Field(default_factory=dict)
    active_items: dict[str, ActiveItem] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


# ═══════════════════════════════════════════════════════════════════════════════
# Entity sensors
# ═══════════════════════════════════════════════════════════════════════════════

class Enemy(BaseModel):
    """ENEMIES — collected every frame (combat) or throttled (idle)."""
    id: int = Field(..., ge=0)
    type: int = Field(..., ge=0)
    variant: int = 0
    subtype: int = 0
    pos: Vector2D = Field(default_factory=Vector2D)
    vel: Vector2D = Field(default_factory=Vector2D)
    hp: float = Field(default=0.0, ge=0.0)
    max_hp: float = Field(default=0.0, ge=0.0)
    is_boss: bool = False
    is_champion: bool = False
    state: int = 0
    state_frame: int = 0
    projectile_cooldown: int = 0
    projectile_delay: int = -1
    collision_radius: float = Field(default=10.0, ge=0.0)
    distance: float = Field(default=0.0, ge=0.0)
    target_pos: Vector2D = Field(default_factory=Vector2D)
    v1: Vector2D = Field(default_factory=Vector2D)
    v2: Vector2D = Field(default_factory=Vector2D)

    model_config = {"extra": "allow"}

    @field_validator("hp", mode="before")
    @classmethod
    def _clamp_hp(cls, v):
        """Known game issue: enemies sometimes report negative HP briefly."""
        if v is None:
            return 0.0
        return max(0.0, float(v))

    @field_validator("max_hp", mode="before")
    @classmethod
    def _clamp_max_hp(cls, v):
        if v is None:
            return 0.0
        return max(0.0, float(v))


class Projectile(BaseModel):
    """A single projectile or tear entity."""
    id: int = Field(..., ge=0)
    pos: Vector2D = Field(default_factory=Vector2D)
    vel: Vector2D = Field(default_factory=Vector2D)
    variant: int = 0
    collision_radius: float = Field(default=5.0, ge=0.0)
    height: float = 0.0
    falling_speed: float = 0.0
    falling_accel: float = 0.0
    scale: float = 1.0

    model_config = {"extra": "allow"}


class Laser(BaseModel):
    """A laser beam entity."""
    id: int = Field(..., ge=0)
    pos: Vector2D = Field(default_factory=Vector2D)
    angle: float = 0.0
    max_distance: float = Field(default=0.0, ge=0.0)
    is_enemy: bool = False

    model_config = {"extra": "allow"}


class Projectiles(BaseModel):
    """PROJECTILES — grouped container."""
    enemy_projectiles: list[Projectile] = Field(default_factory=list)
    player_tears: list[Projectile] = Field(default_factory=list)
    lasers: list[Laser] = Field(default_factory=list)

    model_config = {"extra": "allow"}


# ═══════════════════════════════════════════════════════════════════════════════
# Room sensors
# ═══════════════════════════════════════════════════════════════════════════════

class RoomInfo(BaseModel):
    """ROOM_INFO — collected on room entry + every 30 frames."""
    room_type: int = 0
    room_shape: int = 0
    room_idx: int = 0
    stage: int = 0
    stage_type: int = 0
    difficulty: int = 0
    is_clear: bool = False
    is_first_visit: bool = True
    grid_width: int = Field(default=13, ge=0)
    grid_height: int = Field(default=7, ge=0)
    top_left: Vector2D = Field(default_factory=Vector2D)
    bottom_right: Vector2D = Field(default_factory=Vector2D)
    has_boss: bool = False
    enemy_count: int = Field(default=0, ge=0)
    room_variant: int = 0

    model_config = {"extra": "allow"}


class GridEntity(BaseModel):
    """A single grid entity (rock, pit, spikes, etc.) from ROOM_LAYOUT."""
    type: int = Field(..., ge=0, le=27)
    variant: int = 0
    state: int = 0
    collision: int = 0
    x: float = 0.0
    y: float = 0.0

    model_config = {"extra": "allow"}


class Door(BaseModel):
    """Door data from ROOM_LAYOUT."""
    target_room: int = -1
    target_room_type: int = 0
    is_open: bool = False
    is_locked: bool = False
    x: float = 0.0
    y: float = 0.0

    model_config = {"extra": "allow"}


class RoomLayout(BaseModel):
    """ROOM_LAYOUT — collected on room entry + when grid changes."""
    grid: dict[str, GridEntity] = Field(default_factory=dict)
    doors: dict[str, Door] = Field(default_factory=dict)
    grid_size: int = 0
    width: int = 0
    height: int = 0

    model_config = {"extra": "allow"}


# ═══════════════════════════════════════════════════════════════════════════════
# Hazard sensors
# ═══════════════════════════════════════════════════════════════════════════════

class Pickup(BaseModel):
    """PICKUPS — collected on room entry + every 15 frames."""
    id: int = Field(..., ge=0)
    variant: int = 0
    sub_type: int = 0
    pos: Vector2D = Field(default_factory=Vector2D)
    price: int = 0
    shop_item_id: int = -1
    wait: int = 0

    model_config = {"extra": "allow"}

    @field_validator("price", "shop_item_id", "wait", mode="before")
    @classmethod
    def _coerce_none_int(cls, v):
        if v is None: return 0
        return v


class Bomb(BaseModel):
    """BOMBS — collected every 15 frames."""
    id: int = Field(..., ge=0)
    type: int = 0
    variant: int = 0
    variant_name: str = "NORMAL"
    sub_type: int = 0
    pos: Vector2D = Field(default_factory=Vector2D)
    vel: Vector2D = Field(default_factory=Vector2D)
    explosion_radius: float = Field(default=0.0, ge=0.0)
    timer: int = Field(default=0, ge=0)
    distance: float = Field(default=0.0, ge=0.0)

    model_config = {"extra": "allow"}

    @field_validator("explosion_radius", "timer", "distance", "type", "variant", "sub_type", mode="before")
    @classmethod
    def _coerce_none_num(cls, v):
        return 0 if v is None else v


class FireHazard(BaseModel):
    """FIRE_HAZARDS — collected every 15 frames."""
    id: int = Field(..., ge=0)
    type: str = "UNKNOWN"
    fireplace_type: Optional[str] = None
    variant: int = 0
    sub_variant: int = 0
    pos: Vector2D = Field(default_factory=Vector2D)
    hp: float = Field(default=0.0, ge=0.0)
    max_hp: float = Field(default=0.0, ge=0.0)
    state: int = 0
    is_extinguished: bool = False
    collision_radius: float = Field(default=20.0, ge=0.0)
    distance: float = Field(default=0.0, ge=0.0)
    is_shooting: bool = False
    sprite_scale: float = Field(default=1.0, ge=0.0)

    model_config = {"extra": "allow"}


class Interactable(BaseModel):
    """INTERACTABLES — collected every 15 frames."""
    id: int = Field(..., ge=0)
    type: int = 0
    variant: int = 0
    variant_name: str = "UNKNOWN"
    sub_type: int = 0
    pos: Vector2D = Field(default_factory=Vector2D)
    vel: Vector2D = Field(default_factory=Vector2D)
    state: int = 0
    state_frame: int = 0
    target_pos: Vector2D = Field(default_factory=Vector2D)
    distance: float = Field(default=0.0, ge=0.0)

    model_config = {"extra": "allow"}


# ═══════════════════════════════════════════════════════════════════════════════
# Message-level types
# ═══════════════════════════════════════════════════════════════════════════════

class EventData(BaseModel):
    """Game event payload."""
    event: str = ""
    frame: int = 0
    data: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class SensorMeta(BaseModel):
    """Per-sensor metadata in a data message."""
    collect_frame: int = 0
    collect_time: int = 0
    interval: str = "HIGH"
    stale_frames: int = 0
    entity_count: int = 0
    hash: str = ""

    model_config = {"extra": "allow"}


class DataMessage(BaseModel):
    """v3.0 data message — the primary message type."""
    version: str = "3.0"
    type: str = "DATA"
    seq: int = 0
    frame: int = 0
    game_time: int = 0
    room_index: int = -1
    prev_frame: int = 0
    sensors: dict[str, SensorMeta] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    channels: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}

    @classmethod
    def from_dict(cls, data: dict) -> "DataMessage":
        """Parse from raw JSON dict with backward compatibility for v2.x."""
        sensors = {}
        # v2.1 used "channel_meta" → v3.0 uses "sensors"
        raw_meta = data.get("sensors") or data.get("channel_meta") or {}
        for name, meta in raw_meta.items():
            if isinstance(meta, dict):
                sensors[name] = SensorMeta(**meta)

        return cls(
            version=str(data.get("version", "2.0")),
            type=data.get("type", "DATA"),
            seq=data.get("seq", 0),
            frame=data.get("frame", 0),
            game_time=data.get("game_time", data.get("timestamp", 0)),
            room_index=data.get("room_index", -1),
            prev_frame=data.get("prev_frame", 0),
            sensors=sensors,
            payload=data.get("payload", {}),
            channels=data.get("channels", list(data.get("payload", {}).keys())),
        )


class SubscribeRequest(BaseModel):
    """Python → Lua: subscribe to sensors."""
    type: str = "SUBSCRIBE"
    sensors: list[str] = Field(default_factory=list)
    config_overrides: dict[str, dict] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class SubscribeAck(BaseModel):
    """Lua → Python: subscription acknowledgment."""
    type: str = "SUBSCRIBE_ACK"
    accepted: list[str] = Field(default_factory=list)
    rejected: list[str] = Field(default_factory=list)
    sensor_configs: dict[str, dict] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class CommandResult(BaseModel):
    """Lua → Python: command execution result."""
    type: str = "CMD"
    frame: int = 0
    result: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}
