"""
Room Sensors — ROOM_INFO, ROOM_LAYOUT
"""

from typing import Optional, Any
import logging

from sensors.base import (
    Sensor, SensorRegistry, ThrottleConfig, SensorSearchConfig, ValidationIssue,
)
from protocol.schema import RoomInfo, RoomLayout, GridEntity, Door

logger = logging.getLogger(__name__)


class RoomInfoSensor(Sensor[RoomInfo]):
    """ROOM_INFO — on room entry + every 15 frames."""

    name = "ROOM_INFO"
    throttle_config = ThrottleConfig(base_interval=15, dynamic=False)

    def parse(self, raw_data: Any, frame: int) -> Optional[RoomInfo]:
        try:
            if not isinstance(raw_data, dict):
                return None
            return RoomInfo(**raw_data)
        except Exception as e:
            logger.error("ROOM_INFO parse error: %s", e)
            return None

    def validate(self, data: RoomInfo) -> list[ValidationIssue]:
        issues = []
        if data.grid_width <= 0:
            issues.append(ValidationIssue(
                issue_id="INVALID_GRID_WIDTH", field_path="grid_width",
                severity="error", message="grid_width={}".format(data.grid_width),
            ))
        if data.grid_height <= 0:
            issues.append(ValidationIssue(
                issue_id="INVALID_GRID_HEIGHT", field_path="grid_height",
                severity="error", message="grid_height={}".format(data.grid_height),
            ))
        if data.enemy_count < 0:
            issues.append(ValidationIssue(
                issue_id="NEGATIVE_ENEMY_COUNT", field_path="enemy_count",
                severity="error", message="enemy_count={}".format(data.enemy_count),
            ))
        return issues


class RoomLayoutSensor(Sensor[RoomLayout]):
    """ROOM_LAYOUT — on room entry + when grid changes."""

    name = "ROOM_LAYOUT"
    throttle_config = ThrottleConfig(base_interval=-1, dynamic=False)

    def parse(self, raw_data: Any, frame: int) -> Optional[RoomLayout]:
        try:
            if not isinstance(raw_data, dict):
                return None

            grid_data = raw_data.get("grid", {})
            doors_data = raw_data.get("doors", {})

            grid = {
                k: GridEntity(**v) if isinstance(v, dict) else v
                for k, v in grid_data.items()
            }
            doors = {
                k: Door(**v) if isinstance(v, dict) else v
                for k, v in doors_data.items()
            }

            return RoomLayout(
                grid=grid,
                doors=doors,
                grid_size=raw_data.get("grid_size", 0),
                width=raw_data.get("width", 0),
                height=raw_data.get("height", 0),
            )
        except Exception as e:
            logger.error("ROOM_LAYOUT parse error: %s", e)
            return None


# ── Register ────────────────────────────────────────────────────────────

SensorRegistry.register(RoomInfoSensor())
SensorRegistry.register(RoomLayoutSensor())
