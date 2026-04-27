"""
Sensor Base — ABC for all data sensors and the SensorRegistry singleton.

A Sensor is the Python-side mirror of a Lua Sensor:
- Same name (must match Lua sensor name exactly)
- Knows what Pydantic schema the data should conform to
- Has parse → validate → normalize pipeline
- Optionally produces "entities" that feed into the EntityStateManager
"""

from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class ThrottleConfig:
    """Mirrors Lua throttle configuration."""
    base_interval: int = 1
    dynamic: bool = True
    combat_interval: int = 1
    idle_interval: int = 15


@dataclass
class SensorSearchConfig:
    """Describes HOW Lua finds entities for this sensor."""
    strategy: str = "partition"          # "partition" | "callback" | "hybrid"
    partitions: int = 0                  # EntityPartition bitmask
    type_filter: Optional[int] = None    # EntityType filter
    radius: Optional[float] = None       # nil = full room
    sort_by_distance: bool = False


@dataclass
class ValidationIssue:
    """A data validation issue detected by a sensor."""
    issue_id: str
    field_path: str
    severity: str = "warning"            # info | warning | error
    message: str = ""
    actual_value: Any = None
    expected_value: Any = None


class Sensor(ABC, Generic[T]):
    """
    Abstract base for all data sensors.

    Lifecycle: parse(raw_dict) → validate(parsed) → normalize(validated) → cache

    Subclasses must define:
    - name: str — must match Lua sensor name exactly
    - schema: type[T] — Pydantic model for this sensor's output
    - parse(raw_data, frame) → Optional[T]
    """

    name: str = "__base__"
    throttle_config: ThrottleConfig = field(default_factory=ThrottleConfig)
    search_config: SensorSearchConfig = field(default_factory=SensorSearchConfig)
    produces_entities: bool = False       # True if sensor output feeds EntityStateManager

    def __init__(self):
        self._last_data: Optional[T] = None
        self._last_frame: int = 0
        self._enabled: bool = True

    # ── pipeline ────────────────────────────────────────────────────────

    def process(self, raw_data: Any, frame: int) -> Optional[T]:
        """Full parse → validate → normalize pipeline."""
        try:
            parsed = self.parse(raw_data, frame)
            if parsed is None:
                return None

            issues = self.validate(parsed)
            for issue in issues:
                logger.debug("[%s] %s: %s", self.name, issue.severity, issue.message)

            normalized = self.normalize(parsed)

            self._last_data = normalized
            self._last_frame = frame
            return normalized

        except Exception as e:
            logger.error("[%s] process error: %s", self.name, e)
            return None

    @abstractmethod
    def parse(self, raw_data: Any, frame: int) -> Optional[T]:
        """Parse raw JSON data into structured form."""
        ...

    def validate(self, data: T) -> list[ValidationIssue]:
        """Override to add sensor-specific validation rules."""
        return []

    def normalize(self, data: T) -> T:
        """Override to fix known game-side quirks in the data."""
        return data

    # ── query ───────────────────────────────────────────────────────────

    @property
    def last_data(self) -> Optional[T]:
        return self._last_data

    @property
    def last_frame(self) -> int:
        return self._last_frame

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, v: bool):
        self._enabled = v

    def is_fresh(self, current_frame: int, max_stale: int = 5) -> bool:
        return (current_frame - self._last_frame) <= max_stale


class SensorRegistry:
    """Singleton registry of all sensors."""

    _sensors: dict[str, Sensor] = {}
    _entity_sensors: dict[str, Sensor] = {}

    @classmethod
    def register(cls, sensor: Sensor):
        cls._sensors[sensor.name] = sensor
        if sensor.produces_entities:
            cls._entity_sensors[sensor.name] = sensor
        logger.info("Registered sensor: %s", sensor.name)

    @classmethod
    def get(cls, name: str) -> Optional[Sensor]:
        return cls._sensors.get(name)

    @classmethod
    def get_entity_sensors(cls) -> dict[str, Sensor]:
        return dict(cls._entity_sensors)

    @classmethod
    def all_names(cls) -> list[str]:
        return sorted(cls._sensors.keys())

    @classmethod
    def process_message(cls, payload: dict[str, Any], frame: int) -> dict[str, Any]:
        """Process an entire payload through all matching sensors."""
        results = {}
        for name, raw in payload.items():
            sensor = cls._sensors.get(name)
            if sensor and sensor.enabled:
                result = sensor.process(raw, frame)
                if result is not None:
                    results[name] = result
        return results
