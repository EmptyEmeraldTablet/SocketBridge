"""Models Module - 数据模型层

此模块包含游戏实体的标准化数据结构。
从 v2.1 版本开始，推荐使用新模块结构：
- models.base: 基础类型 (Vector2D, Enums)
- models.entities: 实体数据类
- models.state: 状态管理

旧版 models.py 仍保留以保持向后兼容。
"""

from .base import (
    Vector2D,
    EntityType,
    ObjectState,
)

from .entities import (
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

from .state import (
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
