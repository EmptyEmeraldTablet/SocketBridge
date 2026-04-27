"""Sensor layer — Python mirrors of Lua data collection sensors."""

from sensors.base import Sensor, SensorRegistry, SensorSearchConfig, ThrottleConfig

# Auto-register all sensors on import
import sensors.player    # noqa: F401 — side-effect: registers PLAYER_POSITION, PLAYER_STATS, etc.
import sensors.entities  # noqa: F401 — side-effect: registers ENEMIES, PROJECTILES, PICKUPS
import sensors.room      # noqa: F401 — side-effect: registers ROOM_INFO, ROOM_LAYOUT
import sensors.hazards   # noqa: F401 — side-effect: registers BOMBS, FIRE_HAZARDS, INTERACTABLES

__all__ = ["Sensor", "SensorRegistry", "SensorSearchConfig", "ThrottleConfig"]
