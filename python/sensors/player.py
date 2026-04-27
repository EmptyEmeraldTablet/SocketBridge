"""
Player Sensors — PLAYER_POSITION, PLAYER_STATS, PLAYER_HEALTH, PLAYER_INVENTORY
"""

from typing import Optional, Any
import logging

from sensors.base import (
    Sensor, SensorRegistry, ThrottleConfig, SensorSearchConfig, ValidationIssue,
)
from protocol.schema import (
    PlayerPosition, PlayerStats, PlayerHealth, PlayerInventory,
    Vector2D, ActiveItem,
)

logger = logging.getLogger(__name__)


class PlayerPositionSensor(Sensor[dict[int, PlayerPosition]]):
    """PLAYER_POSITION — collected every frame."""

    name = "PLAYER_POSITION"
    throttle_config = ThrottleConfig(base_interval=1, dynamic=False)
    search_config = SensorSearchConfig(strategy="partition")

    def parse(self, raw_data: Any, frame: int) -> Optional[dict[int, PlayerPosition]]:
        """
        Parse PLAYER_POSITION data.

        Lua sends either:
        - list: [{pos:..., vel:...}, ...]   (actual game data)
        - dict: {"1": {pos:..., vel:...}, ...}
        """
        try:
            players: dict[int, PlayerPosition] = {}

            if isinstance(raw_data, list):
                items = enumerate(raw_data, start=1)
            elif isinstance(raw_data, dict):
                items = ((int(k), v) for k, v in raw_data.items() if k.isdigit())
            else:
                logger.warning("PLAYER_POSITION: unexpected type %s", type(raw_data))
                return None

            for idx, raw in items:
                if not isinstance(raw, dict):
                    continue
                players[idx] = PlayerPosition(
                    pos=Vector2D(**raw.get("pos", {}) or {}),
                    vel=Vector2D(**raw.get("vel", {}) or {}),
                    move_dir=raw.get("move_dir", 0),
                    fire_dir=raw.get("fire_dir", 0),
                    head_dir=raw.get("head_dir", 0),
                    aim_dir=Vector2D(**raw.get("aim_dir", {}) or {}),
                )

            return players

        except Exception as e:
            logger.error("PLAYER_POSITION parse error: %s", e)
            return None

    def validate(self, data: dict[int, PlayerPosition]) -> list[ValidationIssue]:
        issues = []
        for idx, player in data.items():
            if abs(player.pos.x) > 10000 or abs(player.pos.y) > 10000:
                issues.append(ValidationIssue(
                    issue_id="POSITION_OUT_OF_BOUNDS",
                    field_path=f"{idx}.pos",
                    severity="warning",
                    message=f"Player {idx} position out of bounds: ({player.pos.x}, {player.pos.y})",
                ))
            if player.aim_dir.x == 0.0 and player.aim_dir.y == 0.0:
                issues.append(ValidationIssue(
                    issue_id="AIM_DIR_ZERO",
                    field_path=f"{idx}.aim_dir",
                    severity="info",
                    message=f"Player {idx} aim_dir is (0,0) — known game behavior when not aiming",
                ))
        return issues


class PlayerStatsSensor(Sensor[dict[int, PlayerStats]]):
    """PLAYER_STATS — collected every 30 frames."""

    name = "PLAYER_STATS"
    throttle_config = ThrottleConfig(base_interval=30, dynamic=False)

    def parse(self, raw_data: Any, frame: int) -> Optional[dict[int, PlayerStats]]:
        try:
            stats: dict[int, PlayerStats] = {}
            if isinstance(raw_data, list):
                items = enumerate(raw_data, start=1)
            elif isinstance(raw_data, dict):
                items = ((int(k), v) for k, v in raw_data.items() if k.isdigit())
            else:
                return None
            for idx, raw in items:
                if isinstance(raw, dict):
                    stats[idx] = PlayerStats(**raw)
            return stats
        except Exception as e:
            logger.error("PLAYER_STATS parse error: %s", e)
            return None


class PlayerHealthSensor(Sensor[dict[int, PlayerHealth]]):
    """PLAYER_HEALTH — collected every 30 frames."""

    name = "PLAYER_HEALTH"
    throttle_config = ThrottleConfig(base_interval=30, dynamic=False)

    def parse(self, raw_data: Any, frame: int) -> Optional[dict[int, PlayerHealth]]:
        try:
            health: dict[int, PlayerHealth] = {}
            if isinstance(raw_data, list):
                items = enumerate(raw_data, start=1)
            elif isinstance(raw_data, dict):
                items = ((int(k), v) for k, v in raw_data.items() if k.isdigit())
            else:
                return None
            for idx, raw in items:
                if isinstance(raw, dict):
                    health[idx] = PlayerHealth(**raw)
            return health
        except Exception as e:
            logger.error("PLAYER_HEALTH parse error: %s", e)
            return None


class PlayerInventorySensor(Sensor[dict[int, PlayerInventory]]):
    """PLAYER_INVENTORY — collected every 90 frames."""

    name = "PLAYER_INVENTORY"
    throttle_config = ThrottleConfig(base_interval=90, dynamic=False)

    def parse(self, raw_data: Any, frame: int) -> Optional[dict[int, PlayerInventory]]:
        try:
            inv: dict[int, PlayerInventory] = {}
            if isinstance(raw_data, list):
                items = enumerate(raw_data, start=1)
            elif isinstance(raw_data, dict):
                items = ((int(k), v) for k, v in raw_data.items() if k.isdigit())
            else:
                return None
            for idx, raw in items:
                if isinstance(raw, dict):
                    # Parse active items sub-objects
                    if "active_items" in raw:
                        raw = dict(raw)
                        raw["active_items"] = {
                            k: ActiveItem(**v) if isinstance(v, dict) else v
                            for k, v in raw["active_items"].items()
                        }
                    inv[idx] = PlayerInventory(**raw)
            return inv
        except Exception as e:
            logger.error("PLAYER_INVENTORY parse error: %s", e)
            return None


# ── Register ────────────────────────────────────────────────────────────

SensorRegistry.register(PlayerPositionSensor())
SensorRegistry.register(PlayerStatsSensor())
SensorRegistry.register(PlayerHealthSensor())
SensorRegistry.register(PlayerInventorySensor())
