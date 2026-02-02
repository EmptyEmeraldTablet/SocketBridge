"""
Entity State Manager - 实体级别状态管理

提供实体级别的状态保持，解决不同通道不同采集频率导致的数据不稳定问题。

核心功能：
- 实体跟踪：根据 ID 跟踪实体，而不是每帧替换
- 过期清理：自动清理超过指定帧数未更新的实体
- 状态合并：将新数据合并到现有状态，保持未更新实体
- 历史查询：支持查询实体的历史状态
"""

from typing import Dict, Any, Optional, List, Generic, TypeVar, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import time
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class TrackedEntity(Generic[T]):
    """被跟踪的实体"""

    id: int
    data: T
    first_seen_frame: int
    last_seen_frame: int
    update_count: int = 1

    @property
    def age(self) -> int:
        """实体存在的帧数"""
        return self.last_seen_frame - self.first_seen_frame


@dataclass
class EntityStateConfig:
    """实体状态配置"""

    # 实体过期帧数（超过此帧数未更新则移除）
    # -1 或 None 表示禁用自动过期（适用于静态实体）
    expiry_frames: Optional[int] = 60
    # 是否启用历史记录
    enable_history: bool = False
    # 历史记录最大长度
    max_history: int = 10
    # 获取实体 ID 的函数名或属性名
    id_field: str = "id"

    @property
    def auto_expire_enabled(self) -> bool:
        """是否启用自动过期"""
        return self.expiry_frames is not None and self.expiry_frames > 0


class EntityStateManager(Generic[T]):
    """实体状态管理器

    泛型类，可用于管理任何类型的实体（敌人、投射物、拾取物等）。

    使用示例：
    ```python
    # 创建敌人状态管理器
    enemy_manager = EntityStateManager[EnemyData](
        name="ENEMIES",
        config=EntityStateConfig(expiry_frames=30)
    )

    # 更新（每帧调用）
    enemy_manager.update(enemies_list, current_frame)

    # 获取所有活跃敌人
    active_enemies = enemy_manager.get_active()

    # 获取特定敌人
    enemy = enemy_manager.get(enemy_id)
    ```
    """

    def __init__(
        self,
        name: str,
        config: Optional[EntityStateConfig] = None,
        id_getter: Optional[Callable[[T], int]] = None,
    ):
        self.name = name
        self.config = config or EntityStateConfig()
        self._id_getter = id_getter or (lambda x: getattr(x, self.config.id_field))

        # 实体存储：id -> TrackedEntity
        self._entities: Dict[int, TrackedEntity[T]] = {}

        # 当前帧号
        self._current_frame: int = 0

        # 历史记录：id -> [历史数据]
        self._history: Dict[int, List[T]] = defaultdict(list)

        # 统计
        self._stats = {
            "total_updates": 0,
            "total_added": 0,
            "total_removed": 0,
            "total_expired": 0,
        }

    def update(self, entities: List[T], frame: int) -> Dict[str, List[int]]:
        """更新实体状态

        Args:
            entities: 本帧的实体列表
            frame: 当前帧号

        Returns:
            变更信息 {"added": [...], "updated": [...], "removed": [...]}
        """
        self._current_frame = frame
        self._stats["total_updates"] += 1

        changes = {"added": [], "updated": [], "removed": []}

        # 记录本帧出现的实体 ID
        seen_ids = set()

        for entity in entities:
            entity_id = self._id_getter(entity)
            seen_ids.add(entity_id)

            if entity_id in self._entities:
                # 更新现有实体
                tracked = self._entities[entity_id]
                tracked.data = entity
                tracked.last_seen_frame = frame
                tracked.update_count += 1
                changes["updated"].append(entity_id)
            else:
                # 添加新实体
                self._entities[entity_id] = TrackedEntity(
                    id=entity_id,
                    data=entity,
                    first_seen_frame=frame,
                    last_seen_frame=frame,
                )
                changes["added"].append(entity_id)
                self._stats["total_added"] += 1

            # 记录历史
            if self.config.enable_history:
                history = self._history[entity_id]
                history.append(entity)
                if len(history) > self.config.max_history:
                    history.pop(0)

        # 清理过期实体
        expired = self._cleanup_expired(frame)
        changes["removed"] = expired

        return changes

    def _cleanup_expired(self, current_frame: int) -> List[int]:
        """清理过期实体
        
        如果 expiry_frames <= 0 或 None，则禁用自动过期。
        """
        # 禁用自动过期
        if not self.config.auto_expire_enabled:
            return []

        expired_ids = []
        expiry_threshold = current_frame - self.config.expiry_frames

        for entity_id, tracked in list(self._entities.items()):
            if tracked.last_seen_frame < expiry_threshold:
                expired_ids.append(entity_id)
                del self._entities[entity_id]
                self._stats["total_expired"] += 1

                # 清理历史
                if entity_id in self._history:
                    del self._history[entity_id]

        if expired_ids:
            logger.debug(
                f"[{self.name}] Expired {len(expired_ids)} entities: {expired_ids[:5]}..."
            )

        return expired_ids

    def get(self, entity_id: int) -> Optional[T]:
        """获取单个实体"""
        tracked = self._entities.get(entity_id)
        return tracked.data if tracked else None

    def get_tracked(self, entity_id: int) -> Optional[TrackedEntity[T]]:
        """获取被跟踪的实体（包含元数据）"""
        return self._entities.get(entity_id)

    def get_active(self, max_stale_frames: int = None) -> List[T]:
        """获取所有活跃实体

        Args:
            max_stale_frames: 最大过期帧数（None 使用配置值，-1 返回所有）

        Returns:
            活跃实体列表
        """
        # 如果禁用过期或明确指定 -1，返回所有实体
        if max_stale_frames is None:
            if not self.config.auto_expire_enabled:
                return self.get_all()
            max_stale_frames = self.config.expiry_frames
        elif max_stale_frames < 0:
            return self.get_all()

        threshold = self._current_frame - max_stale_frames
        return [
            tracked.data
            for tracked in self._entities.values()
            if tracked.last_seen_frame >= threshold
        ]

    def get_all(self) -> List[T]:
        """获取所有实体（不考虑过期）"""
        return [tracked.data for tracked in self._entities.values()]

    def get_fresh(self, max_stale_frames: int = 5) -> List[T]:
        """获取新鲜的实体（最近几帧更新过）"""
        threshold = self._current_frame - max_stale_frames
        return [
            tracked.data
            for tracked in self._entities.values()
            if tracked.last_seen_frame >= threshold
        ]

    def get_history(self, entity_id: int) -> List[T]:
        """获取实体历史"""
        return list(self._history.get(entity_id, []))

    def is_entity_active(self, entity_id: int) -> bool:
        """检查实体是否活跃"""
        tracked = self._entities.get(entity_id)
        if not tracked:
            return False
        return (
            self._current_frame - tracked.last_seen_frame <= self.config.expiry_frames
        )

    def get_entity_age(self, entity_id: int) -> int:
        """获取实体年龄（自首次出现以来的帧数）"""
        tracked = self._entities.get(entity_id)
        return tracked.age if tracked else -1

    def get_entity_staleness(self, entity_id: int) -> int:
        """获取实体陈旧度（自上次更新以来的帧数）"""
        tracked = self._entities.get(entity_id)
        if not tracked:
            return -1
        return self._current_frame - tracked.last_seen_frame

    def count(self) -> int:
        """获取实体数量"""
        return len(self._entities)

    def clear(self):
        """清空所有实体"""
        count = len(self._entities)
        self._entities.clear()
        self._history.clear()
        self._stats["total_removed"] += count
        logger.debug(f"[{self.name}] Cleared {count} entities")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "name": self.name,
            "current_count": len(self._entities),
            "current_frame": self._current_frame,
            **self._stats,
        }

    @property
    def current_frame(self) -> int:
        """当前帧号"""
        return self._current_frame


class GameEntityState:
    """游戏实体状态聚合器

    管理所有类型的游戏实体状态。

    使用示例：
    ```python
    state = GameEntityState()

    # 处理消息时更新
    state.update_from_channels(channels_data, frame)

    # 获取数据
    enemies = state.get_enemies()
    projectiles = state.get_enemy_projectiles()
    ```
    """

    def __init__(
        self,
        enemy_expiry: int = 10,         # ENEMIES: HIGH 频率，每帧采集，10帧过期
        projectile_expiry: int = 5,     # PROJECTILES: HIGH 频率，5帧过期（快速移动）
        pickup_expiry: int = 30,        # PICKUPS: LOW 频率（每15帧），30帧过期
        bomb_expiry: int = 30,          # BOMBS: LOW 频率（每15帧），30帧过期
        grid_entity_expiry: int = -1,   # GRID_ENTITIES: 静态障碍物，不自动过期
    ):
        # ========================================
        # 动态实体 - 启用自动过期
        # ========================================
        
        # 敌人状态 (HIGH 频率采集，每帧)
        self.enemies = EntityStateManager(
            name="ENEMIES",
            config=EntityStateConfig(expiry_frames=enemy_expiry),
            id_getter=lambda x: x.id if hasattr(x, "id") else x.get("id", 0),
        )

        # 敌方投射物状态 (HIGH 频率，快速移动)
        self.enemy_projectiles = EntityStateManager(
            name="ENEMY_PROJECTILES",
            config=EntityStateConfig(expiry_frames=projectile_expiry),
            id_getter=lambda x: x.id if hasattr(x, "id") else x.get("id", 0),
        )

        # 玩家泪弹状态 (HIGH 频率)
        self.player_tears = EntityStateManager(
            name="PLAYER_TEARS",
            config=EntityStateConfig(expiry_frames=projectile_expiry),
            id_getter=lambda x: x.id if hasattr(x, "id") else x.get("id", 0),
        )

        # 激光状态 (HIGH 频率)
        self.lasers = EntityStateManager(
            name="LASERS",
            config=EntityStateConfig(expiry_frames=projectile_expiry),
            id_getter=lambda x: x.id if hasattr(x, "id") else x.get("id", 0),
        )

        # 拾取物状态 (LOW 频率，每15帧采集)
        self.pickups = EntityStateManager(
            name="PICKUPS",
            config=EntityStateConfig(expiry_frames=pickup_expiry),
            id_getter=lambda x: x.id if hasattr(x, "id") else x.get("id", 0),
        )

        # 炸弹状态 (LOW 频率，每15帧采集)
        self.bombs = EntityStateManager(
            name="BOMBS",
            config=EntityStateConfig(expiry_frames=bomb_expiry),
            id_getter=lambda x: x.id if hasattr(x, "id") else x.get("id", 0),
        )

        # ========================================
        # 静态实体 - 禁用自动过期
        # ========================================
        
        # 网格实体/障碍物状态 (ON_CHANGE 或 LOW 频率)
        # 障碍物破坏是状态变化（如岩石变碎片），不是移除
        # 使用 grid_index 作为 ID
        self.grid_entities = EntityStateManager(
            name="GRID_ENTITIES",
            config=EntityStateConfig(expiry_frames=grid_entity_expiry),
            id_getter=lambda x: x.grid_index if hasattr(x, "grid_index") else x.get("grid_index", 0),
        )

        # 当前帧
        self._current_frame = 0
        self._current_room = -1

    def update_enemies(self, enemies: List[Any], frame: int):
        """更新敌人状态"""
        self._current_frame = frame
        self.enemies.update(enemies, frame)

    def update_projectiles(
        self,
        enemy_projectiles: List[Any],
        player_tears: List[Any],
        lasers: List[Any],
        frame: int,
    ):
        """更新投射物状态"""
        self._current_frame = frame
        self.enemy_projectiles.update(enemy_projectiles, frame)
        self.player_tears.update(player_tears, frame)
        self.lasers.update(lasers, frame)

    def update_pickups(self, pickups: List[Any], frame: int):
        """更新拾取物状态"""
        self._current_frame = frame
        self.pickups.update(pickups, frame)

    def update_bombs(self, bombs: List[Any], frame: int):
        """更新炸弹状态"""
        self._current_frame = frame
        self.bombs.update(bombs, frame)

    def update_grid_entities(self, grid_entities: List[Any], frame: int):
        """更新网格实体/障碍物状态"""
        self._current_frame = frame
        self.grid_entities.update(grid_entities, frame)

    def on_room_change(self, new_room: int):
        """房间切换时清理状态"""
        if new_room != self._current_room:
            logger.info(
                f"Room changed from {self._current_room} to {new_room}, clearing entity states"
            )
            self._current_room = new_room
            # 清理所有实体状态
            self.enemies.clear()
            self.enemy_projectiles.clear()
            self.player_tears.clear()
            self.lasers.clear()
            self.pickups.clear()
            self.bombs.clear()
            self.grid_entities.clear()

    def get_enemies(self, max_stale_frames: int = 5) -> List[Any]:
        """获取活跃敌人"""
        return self.enemies.get_fresh(max_stale_frames)

    def get_enemy_projectiles(self, max_stale_frames: int = 3) -> List[Any]:
        """获取敌方投射物"""
        return self.enemy_projectiles.get_fresh(max_stale_frames)

    def get_player_tears(self, max_stale_frames: int = 3) -> List[Any]:
        """获取玩家泪弹"""
        return self.player_tears.get_fresh(max_stale_frames)

    def get_lasers(self, max_stale_frames: int = 3) -> List[Any]:
        """获取激光"""
        return self.lasers.get_fresh(max_stale_frames)

    def get_pickups(self, max_stale_frames: int = 30) -> List[Any]:
        """获取拾取物"""
        return self.pickups.get_fresh(max_stale_frames)

    def get_bombs(self, max_stale_frames: int = 30) -> List[Any]:
        """获取炸弹"""
        return self.bombs.get_fresh(max_stale_frames)

    def get_grid_entities(self) -> List[Any]:
        """获取网格实体/障碍物（静态，返回所有）"""
        return self.grid_entities.get_all()

    def get_threat_count(self) -> int:
        """获取威胁数量（敌人 + 敌方投射物）"""
        return self.enemies.count() + self.enemy_projectiles.count()

    def get_stats(self) -> Dict[str, Any]:
        """获取所有状态统计"""
        return {
            "current_frame": self._current_frame,
            "current_room": self._current_room,
            "enemies": self.enemies.get_stats(),
            "enemy_projectiles": self.enemy_projectiles.get_stats(),
            "player_tears": self.player_tears.get_stats(),
            "lasers": self.lasers.get_stats(),
            "pickups": self.pickups.get_stats(),
            "bombs": self.bombs.get_stats(),
            "grid_entities": self.grid_entities.get_stats(),
        }

    @property
    def current_frame(self) -> int:
        return self._current_frame

    @property
    def current_room(self) -> int:
        return self._current_room
