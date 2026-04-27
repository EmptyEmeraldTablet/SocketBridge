"""
SocketBridge 数据模型层

v2.1+ 版本说明:
    此文件已弃用。请使用新的模块结构:

    - from models.base import Vector2D, EntityType, ObjectState
    - from models.entities import PlayerData, EnemyData, RoomInfo, etc.
    - from models.state import GameStateData, TimingAwareStateManager

    或者直接使用:
    - from models import Vector2D, PlayerData, GameStateData

此文件保留用于向后兼容，旧代码仍可正常工作。
"""

from models.base import (
    Vector2D,
    EntityType,
    ObjectState,
)

from models.entities import (
    EntityData,
    PlayerData,
    EnemyData,
    ProjectileData,
    RoomInfo,
    GridTile,
    DoorData,
    RoomLayout,
    LaserData,
    PickupData,
    DestructibleData,
    BombData,
    ButtonData,
    FireHazardData,
    InteractableData,
    PlayerHealthData,
    PlayerStatsData,
    PlayerInventoryData,
)

from models.state import (
    ChannelState,
    TimingAwareStateManager,
    GameStateData,
    ControlOutput,
)

__all__ = [
    "Vector2D",
    "EntityType",
    "ObjectState",
    "EntityData",
    "PlayerData",
    "EnemyData",
    "ProjectileData",
    "RoomInfo",
    "GridTile",
    "DoorData",
    "RoomLayout",
    "LaserData",
    "PickupData",
    "DestructibleData",
    "BombData",
    "ButtonData",
    "FireHazardData",
    "InteractableData",
    "PlayerHealthData",
    "PlayerStatsData",
    "PlayerInventoryData",
    "ChannelState",
    "TimingAwareStateManager",
    "GameStateData",
    "ControlOutput",
]
