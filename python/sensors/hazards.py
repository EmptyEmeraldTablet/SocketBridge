"""
Hazard Sensors — BOMBS, FIRE_HAZARDS, INTERACTABLES
"""

from typing import Optional, Any
import logging

from sensors.base import (
    Sensor, SensorRegistry, ThrottleConfig, SensorSearchConfig, ValidationIssue,
)
from protocol.schema import Bomb, FireHazard, Interactable

logger = logging.getLogger(__name__)


class BombsSensor(Sensor[list[Bomb]]):
    """BOMBS — every 15 frames."""

    name = "BOMBS"
    throttle_config = ThrottleConfig(base_interval=15, dynamic=False)
    produces_entities = True

    def parse(self, raw_data: Any, frame: int) -> Optional[list[Bomb]]:
        try:
            if not raw_data or not isinstance(raw_data, list):
                return []
            return [Bomb(**b) for b in raw_data if isinstance(b, dict)]
        except Exception as e:
            logger.error("BOMBS parse error: %s", e)
            return None

    def validate(self, data: list[Bomb]) -> list[ValidationIssue]:
        issues = []
        for b in data:
            if b.timer < 0:
                issues.append(ValidationIssue(
                    issue_id="BOMB_NEGATIVE_TIMER", field_path=f"{b.id}.timer",
                    severity="warning", message=f"Bomb {b.id} timer={b.timer}",
                ))
        return issues


class FireHazardsSensor(Sensor[list[FireHazard]]):
    """FIRE_HAZARDS — every 15 frames."""

    name = "FIRE_HAZARDS"
    throttle_config = ThrottleConfig(base_interval=15, dynamic=False)
    search_config = SensorSearchConfig(strategy="hybrid")

    def parse(self, raw_data: Any, frame: int) -> Optional[list[FireHazard]]:
        try:
            if not raw_data or not isinstance(raw_data, list):
                return []
            return [FireHazard(**f) for f in raw_data if isinstance(f, dict)]
        except Exception as e:
            logger.error("FIRE_HAZARDS parse error: %s", e)
            return None

    def validate(self, data: list[FireHazard]) -> list[ValidationIssue]:
        issues = []
        for f in data:
            if f.hp < 0:
                issues.append(ValidationIssue(
                    issue_id="FIRE_NEGATIVE_HP", field_path=f"{f.id}.hp",
                    severity="warning", message=f"Fire {f.id} hp={f.hp}",
                ))
        return issues


class InteractablesSensor(Sensor[list[Interactable]]):
    """INTERACTABLES — every 15 frames."""

    name = "INTERACTABLES"
    throttle_config = ThrottleConfig(base_interval=15, dynamic=False)

    def parse(self, raw_data: Any, frame: int) -> Optional[list[Interactable]]:
        try:
            if not raw_data or not isinstance(raw_data, list):
                return []
            return [Interactable(**i) for i in raw_data if isinstance(i, dict)]
        except Exception as e:
            logger.error("INTERACTABLES parse error: %s", e)
            return None


# ── Register ────────────────────────────────────────────────────────────

SensorRegistry.register(BombsSensor())
SensorRegistry.register(FireHazardsSensor())
SensorRegistry.register(InteractablesSensor())
