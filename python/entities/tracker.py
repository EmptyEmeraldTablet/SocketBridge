"""
Entity State Manager — unified entity tracking across frames.

Replaces: services/entity_state.py + models/state.py GameStateData

Key concepts:
- Entity identity persists across frames via game entity.Index
- Lifecycle: appeared → active (updated) → removed (expired or died)
- History: optional per-entity position/velocity history for prediction
- Expiry: configurable per entity type (dynamic entities expire, static don't)
- Room-change: all dynamic entities cleared on room transition
"""

from typing import TypeVar, Generic, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import logging

from protocol.schema import Enemy, Projectile, Laser, Pickup, Bomb, GridEntity

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class TrackedEntity(Generic[T]):
    """An entity being tracked across frames."""

    id: int
    data: T
    first_seen_frame: int
    last_seen_frame: int
    update_count: int = 1

    @property
    def age(self) -> int:
        return self.last_seen_frame - self.first_seen_frame


@dataclass
class EntityChanges:
    """Result of an entity update."""
    added: list[int] = field(default_factory=list)
    updated: list[int] = field(default_factory=list)
    removed: list[int] = field(default_factory=list)


@dataclass
class EntityStateConfig:
    """Configuration for an entity state manager."""

    expiry_frames: int = 60           # Auto-remove after N frames unseen (-1 disables)
    enable_history: bool = False      # Store position/velocity history
    max_history: int = 10             # Max history entries per entity
    id_field: str = "id"              # Field name for entity identity

    @property
    def auto_expire_enabled(self) -> bool:
        return self.expiry_frames > 0


class EntityStateManager(Generic[T]):
    """
    Generic entity state tracker.

    Tracks entity identity across frames:
    - New entities are "added"
    - Existing entities are "updated"
    - Unseen entities are auto-expired (if enabled)

    For static entities (grid/obstacles), set expiry_frames=-1 to disable auto-expiry.
    """

    def __init__(
        self,
        name: str,
        config: Optional[EntityStateConfig] = None,
        id_getter: Optional[Callable[[T], int]] = None,
    ):
        self.name = name
        self.config = config or EntityStateConfig()
        self._id_getter = id_getter or (lambda x: getattr(x, self.config.id_field, 0))
        self._entities: dict[int, TrackedEntity[T]] = {}
        self._history: dict[int, list[T]] = defaultdict(list)
        self._current_frame: int = 0

        self._stats = {
            "total_updates": 0,
            "total_added": 0,
            "total_removed": 0,
            "total_expired": 0,
        }

    # ── update ──────────────────────────────────────────────────────────

    def update(self, entities: list[T], frame: int) -> EntityChanges:
        """
        Update tracked entities from a new list.

        Returns changes: {added: [id], updated: [id], removed: [id]}
        """
        self._current_frame = frame
        self._stats["total_updates"] += 1

        changes = EntityChanges()
        seen_ids: set[int] = set()

        for entity in entities:
            eid = self._id_getter(entity)
            seen_ids.add(eid)

            if eid in self._entities:
                tracked = self._entities[eid]
                tracked.data = entity
                tracked.last_seen_frame = frame
                tracked.update_count += 1
                changes.updated.append(eid)
            else:
                self._entities[eid] = TrackedEntity(
                    id=eid, data=entity,
                    first_seen_frame=frame, last_seen_frame=frame,
                )
                changes.added.append(eid)
                self._stats["total_added"] += 1

            if self.config.enable_history:
                hist = self._history[eid]
                hist.append(entity)
                if len(hist) > self.config.max_history:
                    hist.pop(0)

        expired = self._cleanup_expired(frame)
        changes.removed = expired
        return changes

    def _cleanup_expired(self, frame: int) -> list[int]:
        if not self.config.auto_expire_enabled:
            return []

        threshold = frame - self.config.expiry_frames
        expired = [
            eid for eid, e in list(self._entities.items())
            if e.last_seen_frame < threshold
        ]
        for eid in expired:
            del self._entities[eid]
            self._history.pop(eid, None)
            self._stats["total_expired"] += 1

        if expired:
            logger.debug("[%s] Expired %d: %s...", self.name, len(expired), expired[:5])
        return expired

    # ── query ───────────────────────────────────────────────────────────

    def get(self, entity_id: int) -> Optional[T]:
        t = self._entities.get(entity_id)
        return t.data if t else None

    def get_tracked(self, entity_id: int) -> Optional[TrackedEntity[T]]:
        return self._entities.get(entity_id)

    def get_active(self, max_stale_frames: Optional[int] = None) -> list[T]:
        """Get active entities. If max_stale_frames is None, uses config default."""
        if max_stale_frames is None:
            if not self.config.auto_expire_enabled:
                return self.get_all()
            max_stale_frames = self.config.expiry_frames
        elif max_stale_frames < 0:
            return self.get_all()

        threshold = self._current_frame - max_stale_frames
        return [e.data for e in self._entities.values() if e.last_seen_frame >= threshold]

    def get_all(self) -> list[T]:
        return [e.data for e in self._entities.values()]

    def get_fresh(self, max_stale_frames: int = 5) -> list[T]:
        threshold = self._current_frame - max_stale_frames
        return [e.data for e in self._entities.values() if e.last_seen_frame >= threshold]

    def get_history(self, entity_id: int) -> list[T]:
        return list(self._history.get(entity_id, []))

    # ── lifecycle ───────────────────────────────────────────────────────

    def is_active(self, entity_id: int, max_stale: Optional[int] = None) -> bool:
        if max_stale is None:
            max_stale = self.config.expiry_frames
        t = self._entities.get(entity_id)
        if not t:
            return False
        return (self._current_frame - t.last_seen_frame) <= max_stale

    def get_staleness(self, entity_id: int) -> int:
        t = self._entities.get(entity_id)
        return (self._current_frame - t.last_seen_frame) if t else -1

    # ── mutation ────────────────────────────────────────────────────────

    def remove(self, entity_id: int) -> bool:
        if entity_id in self._entities:
            del self._entities[entity_id]
            self._history.pop(entity_id, None)
            self._stats["total_removed"] += 1
            return True
        return False

    def clear(self):
        count = len(self._entities)
        self._entities.clear()
        self._history.clear()
        self._stats["total_removed"] += count
        logger.debug("[%s] Cleared %d entities", self.name, count)

    @property
    def count(self) -> int:
        return len(self._entities)

    def get_stats(self) -> dict[str, Any]:
        return {"name": self.name, "current_count": self.count, **self._stats}


# ═══════════════════════════════════════════════════════════════════════════════
# GameEntityStore — aggregates all entity managers
# ═══════════════════════════════════════════════════════════════════════════════

class GameEntityStore:
    """
    Aggregates all entity state managers.

    Provides:
    - Per-type entity tracking (enemies, projectiles, etc.)
    - Room-change cleanup
    - Threat counting
    - Unified stats
    """

    def __init__(
        self,
        enemy_expiry: int = 10,
        projectile_expiry: int = 5,
        pickup_expiry: int = 30,
        bomb_expiry: int = 30,
        grid_entity_expiry: int = -1,    # static — no auto-expire
    ):
        # Dynamic entities
        self.enemies = EntityStateManager[Enemy](
            name="enemies",
            config=EntityStateConfig(expiry_frames=enemy_expiry, id_field="id"),
            id_getter=lambda e: e.id,
        )
        self.enemy_projectiles = EntityStateManager[Projectile](
            name="enemy_projectiles",
            config=EntityStateConfig(expiry_frames=projectile_expiry, id_field="id"),
            id_getter=lambda e: e.id,
        )
        self.player_tears = EntityStateManager[Projectile](
            name="player_tears",
            config=EntityStateConfig(expiry_frames=projectile_expiry, id_field="id"),
            id_getter=lambda e: e.id,
        )
        self.lasers = EntityStateManager[Laser](
            name="lasers",
            config=EntityStateConfig(expiry_frames=projectile_expiry, id_field="id"),
            id_getter=lambda e: e.id,
        )
        self.pickups = EntityStateManager[Pickup](
            name="pickups",
            config=EntityStateConfig(expiry_frames=pickup_expiry, id_field="id"),
            id_getter=lambda e: e.id,
        )
        self.bombs = EntityStateManager[Bomb](
            name="bombs",
            config=EntityStateConfig(expiry_frames=bomb_expiry, id_field="id"),
            id_getter=lambda e: e.id,
        )
        # Static entities
        self.grid_entities = EntityStateManager[GridEntity](
            name="grid_entities",
            config=EntityStateConfig(expiry_frames=grid_entity_expiry, id_field="grid_index"),
            id_getter=lambda e: getattr(e, "grid_index", 0),
        )

        self._current_frame = 0
        self._current_room = -1

    # ── update helpers ──────────────────────────────────────────────────

    def update_enemies(self, data: list[Any], frame: int) -> EntityChanges:
        self._current_frame = frame
        enemies = [Enemy(**e) if isinstance(e, dict) else e for e in data]
        return self.enemies.update(enemies, frame)

    def update_projectiles(self, enemy_proj: list[Any], player_tears: list[Any],
                           lasers: list[Any], frame: int) -> dict[str, EntityChanges]:
        self._current_frame = frame
        return {
            "enemy_projectiles": self.enemy_projectiles.update(
                [Projectile(**p) if isinstance(p, dict) else p for p in enemy_proj], frame
            ),
            "player_tears": self.player_tears.update(
                [Projectile(**p) if isinstance(p, dict) else p for p in player_tears], frame
            ),
            "lasers": self.lasers.update(
                [Laser(**l) if isinstance(l, dict) else l for l in lasers], frame
            ),
        }

    def update_pickups(self, data: list[Any], frame: int) -> EntityChanges:
        self._current_frame = frame
        pickups = [Pickup(**p) if isinstance(p, dict) else p for p in data]
        return self.pickups.update(pickups, frame)

    def update_bombs(self, data: list[Any], frame: int) -> EntityChanges:
        self._current_frame = frame
        bombs = [Bomb(**b) if isinstance(b, dict) else b for b in data]
        return self.bombs.update(bombs, frame)

    def update_grid_entities(self, data: list[Any], frame: int) -> EntityChanges:
        self._current_frame = frame
        entities = [GridEntity(**g) if isinstance(g, dict) else g for g in data]
        return self.grid_entities.update(entities, frame)

    # ── room lifecycle ──────────────────────────────────────────────────

    def on_room_change(self, new_room: int):
        if new_room != self._current_room:
            logger.info("Room %d → %d — clearing dynamic entities", self._current_room, new_room)
            self._current_room = new_room
            self.enemies.clear()
            self.enemy_projectiles.clear()
            self.player_tears.clear()
            self.lasers.clear()
            self.pickups.clear()
            self.bombs.clear()
            # Static grid entities persist across rooms until re-collected

    def on_new_room(self, new_room: int):
        """Full reset including static entities (for new run)."""
        self._current_room = new_room
        for mgr in [self.enemies, self.enemy_projectiles, self.player_tears,
                     self.lasers, self.pickups, self.bombs, self.grid_entities]:
            mgr.clear()

    # ── query ───────────────────────────────────────────────────────────

    def get_threat_count(self) -> int:
        return self.enemies.count + self.enemy_projectiles.count

    def get_stats(self) -> dict[str, Any]:
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
