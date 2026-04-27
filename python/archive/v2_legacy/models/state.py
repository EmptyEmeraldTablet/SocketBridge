from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any, Tuple
from collections import deque
import time
import logging

try:
    from core.protocol.timing import ChannelTimingInfo, MessageTimingInfo
except ImportError:
    from python.core.protocol.timing import ChannelTimingInfo, MessageTimingInfo

try:
    from models.entities import (
        PlayerData,
        EnemyData,
        ProjectileData,
        RoomInfo,
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
        Vector2D,
    )
except ImportError:
    from python.models.entities import (
        PlayerData,
        EnemyData,
        ProjectileData,
        RoomInfo,
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
        Vector2D,
    )

logger = logging.getLogger(__name__)


@dataclass
class ChannelState:
    data: Any
    collect_frame: int
    collect_time: int
    receive_frame: int
    receive_time: float
    is_stale: bool = False


class TimingAwareStateManager:
    def __init__(self, max_history: int = 300):
        self.channels: Dict[str, ChannelState] = {}
        self.history: Dict[str, deque] = {}
        self.max_history = max_history
        self.current_frame = 0

    def update_channel(
        self, channel: str, data: Any, timing: ChannelTimingInfo, current_frame: int
    ):
        state = ChannelState(
            data=data,
            collect_frame=timing.collect_frame,
            collect_time=timing.collect_time,
            receive_frame=current_frame,
            receive_time=time.time(),
            is_stale=timing.is_stale,
        )

        if channel not in self.history:
            self.history[channel] = deque(maxlen=self.max_history)
        self.history[channel].append(state)

        self.channels[channel] = state
        self.current_frame = max(self.current_frame, current_frame)

    def get_channel(self, channel: str) -> Optional[ChannelState]:
        return self.channels.get(channel)

    def get_channel_data(self, channel: str) -> Optional[Any]:
        state = self.channels.get(channel)
        return state.data if state else None

    def is_channel_fresh(self, channel: str, max_stale_frames: int = 5) -> bool:
        state = self.channels.get(channel)
        if not state:
            return False
        return (self.current_frame - state.collect_frame) <= max_stale_frames

    def get_channel_age(self, channel: str) -> int:
        state = self.channels.get(channel)
        if not state:
            return -1
        return self.current_frame - state.collect_frame

    def get_synchronized_snapshot(
        self, channels: List[str], max_frame_diff: int = 5
    ) -> Optional[Dict[str, Any]]:
        states = []
        for channel in channels:
            state = self.channels.get(channel)
            if not state:
                return None
            states.append((channel, state))

        frames = [s.collect_frame for _, s in states]
        if max(frames) - min(frames) > max_frame_diff:
            logger.warning(f"Channels not synchronized: {dict(zip(channels, frames))}")
            return None

        return {channel: state.data for channel, state in states}

    def get_state_at_frame(self, channel: str, target_frame: int) -> Optional[Any]:
        history = self.history.get(channel, [])

        best_match = None
        best_diff = float("inf")

        for state in history:
            diff = abs(state.collect_frame - target_frame)
            if diff < best_diff:
                best_diff = diff
                best_match = state

        return best_match.data if best_match else None


@dataclass
class GameStateData:
    frame: int = 0
    timestamp: int = 0
    room_index: int = -1
    room_info: Optional[RoomInfo] = None
    room_layout: Optional[RoomLayout] = None
    raw_room_layout: Optional[Dict[str, Any]] = None
    players: Dict[int, PlayerData] = field(default_factory=dict)
    enemies: Dict[int, EnemyData] = field(default_factory=dict)
    projectiles: Dict[int, ProjectileData] = field(default_factory=dict)
    lasers: Dict[int, LaserData] = field(default_factory=dict)
    pickups: Dict[int, PickupData] = field(default_factory=dict)
    obstacles: Dict[int, DestructibleData] = field(default_factory=dict)
    buttons: Dict[int, ButtonData] = field(default_factory=dict)
    fire_hazards: Dict[int, FireHazardData] = field(default_factory=dict)
    interactables: Dict[int, InteractableData] = field(default_factory=dict)
    bombs: Dict[int, BombData] = field(default_factory=dict)
    player_health: Dict[int, PlayerHealthData] = field(default_factory=dict)
    player_stats: Dict[int, PlayerStatsData] = field(default_factory=dict)
    player_inventory: Dict[int, PlayerInventoryData] = field(default_factory=dict)
    channel_last_update: Dict[str, int] = field(default_factory=dict)
    ENTITY_EXPIRY_FRAMES: int = 60

    @property
    def active_enemies(self) -> List[EnemyData]:
        current_frame = self.frame
        return [
            e
            for e in self.enemies.values()
            if e.state.value == "active"
            and current_frame - e.last_seen_frame < self.ENTITY_EXPIRY_FRAMES
        ]

    @property
    def enemy_projectiles(self) -> List[ProjectileData]:
        current_frame = self.frame
        return [
            p
            for p in self.projectiles.values()
            if p.is_enemy
            and current_frame - p.last_seen_frame < self.ENTITY_EXPIRY_FRAMES
        ]

    @property
    def player_projectiles(self) -> List[ProjectileData]:
        current_frame = self.frame
        return [
            p
            for p in self.projectiles.values()
            if not p.is_enemy
            and current_frame - p.last_seen_frame < self.ENTITY_EXPIRY_FRAMES
        ]

    def get_primary_player(self) -> Optional[PlayerData]:
        return self.players.get(1)

    def get_nearest_enemy(self, player_pos: Vector2D) -> Optional[EnemyData]:
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
        return [
            e
            for e in self.active_enemies
            if e.position.distance_to(player_pos) <= max_distance
        ]

    def get_threat_count(self) -> int:
        return len(self.active_enemies) + len(self.enemy_projectiles)

    def get_primary_player_stats(self) -> Optional[PlayerStatsData]:
        return self.player_stats.get(1)

    def get_primary_player_health_info(self) -> Optional[PlayerHealthData]:
        return self.player_health.get(1)

    def get_primary_player_health_ratio(self) -> float:
        health_info = self.get_primary_player_health_info()
        if health_info:
            max_hearts = health_info.max_hearts
            if max_hearts > 0:
                return health_info.total_hearts / max_hearts
            return 1.0
        player = self.get_primary_player()
        if player:
            return player.health / max(player.max_health, 1)
        return 1.0

    def mark_channel_updated(self, channel: str, frame: int):
        self.channel_last_update[channel] = frame

    def get_channel_last_frame(self, channel: str) -> Optional[int]:
        return self.channel_last_update.get(channel)

    def is_channel_stale(self, channel: str, max_staleness: int = None) -> bool:
        if max_staleness is None:
            max_staleness = self.ENTITY_EXPIRY_FRAMES
        last_frame = self.get_channel_last_frame(channel)
        if last_frame is None:
            return True
        return self.frame - last_frame > max_staleness

    def cleanup_stale_entities(self, frame: int = None):
        if frame is None:
            frame = self.frame
        expiry_threshold = frame - self.ENTITY_EXPIRY_FRAMES

        stale_enemies = [
            enemy_id
            for enemy_id, enemy in self.enemies.items()
            if enemy.last_seen_frame < expiry_threshold
        ]
        for enemy_id in stale_enemies:
            del self.enemies[enemy_id]
            logger.debug(f"[GameStateData] Removed stale enemy {enemy_id}")

        stale_projectiles = [
            proj_id
            for proj_id, proj in self.projectiles.items()
            if proj.last_seen_frame < expiry_threshold
        ]
        for proj_id in stale_projectiles:
            del self.projectiles[proj_id]
            logger.debug(f"[GameStateData] Removed stale projectile {proj_id}")

        stale_pickups = [
            pickup_id
            for pickup_id, pickup in self.pickups.items()
            if pickup.last_seen_frame < expiry_threshold
        ]
        for pickup_id in stale_pickups:
            del self.pickups[pickup_id]
            logger.debug(f"[GameStateData] Removed stale pickup {pickup_id}")

        stale_buttons = [
            btn_id
            for btn_id, btn in self.buttons.items()
            if btn.last_seen_frame < expiry_threshold
        ]
        for btn_id in stale_buttons:
            del self.buttons[btn_id]
            logger.debug(f"[GameStateData] Removed stale button {btn_id}")

        stale_fire = [
            fire_id
            for fire_id, fire in self.fire_hazards.items()
            if fire.last_seen_frame < expiry_threshold
        ]
        for fire_id in stale_fire:
            del self.fire_hazards[fire_id]
            logger.debug(f"[GameStateData] Removed stale fire_hazard {fire_id}")

        stale_interactables = [
            ent_id
            for ent_id, ent in self.interactables.items()
            if ent.last_seen_frame < expiry_threshold
        ]
        for ent_id in stale_interactables:
            del self.interactables[ent_id]
            logger.debug(f"[GameStateData] Removed stale interactable {ent_id}")

        stale_obstacles = [
            obj_id
            for obj_id, obj in self.obstacles.items()
            if obj.last_seen_frame < expiry_threshold
        ]
        for obj_id in stale_obstacles:
            del self.obstacles[obj_id]
            logger.debug(f"[GameStateData] Removed stale obstacle {obj_id}")

        stale_bombs = [
            bomb_id
            for bomb_id, bomb in self.bombs.items()
            if bomb.last_seen_frame < expiry_threshold
        ]
        for bomb_id in stale_bombs:
            del self.bombs[bomb_id]
            logger.debug(f"[GameStateData] Removed stale bomb {bomb_id}")

        stale_lasers = [
            laser_id
            for laser_id, laser in self.lasers.items()
            if laser.last_seen_frame < expiry_threshold
        ]
        for laser_id in stale_lasers:
            del self.lasers[laser_id]
            logger.debug(f"[GameStateData] Removed stale laser {laser_id}")

        stale_players = [
            player_idx
            for player_idx, player in self.players.items()
            if player.last_seen_frame < expiry_threshold
        ]
        for player_idx in stale_players:
            del self.players[player_idx]
            logger.debug(f"[GameStateData] Removed stale player {player_idx}")

        if stale_enemies or stale_projectiles or stale_pickups:
            logger.debug(
                f"[GameStateData] Cleanup: {len(stale_enemies)} enemies, "
                f"{len(stale_projectiles)} projectiles, {len(stale_pickups)} pickups"
            )


@dataclass
class ControlOutput:
    move_x: int = 0
    move_y: int = 0
    shoot: bool = False
    shoot_x: int = 0
    shoot_y: int = 0
    use_item: bool = False
    use_bomb: bool = False
    drop: bool = False
    confidence: float = 1.0
    reasoning: str = ""

    def to_input(self) -> Tuple[Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
        move = None
        if self.move_x != 0 or self.move_y != 0:
            move = (self.move_x, self.move_y)
        shoot = None
        if self.shoot:
            shoot = (self.shoot_x, self.shoot_y)
        return move, shoot
