"""
Entity Sensors — ENEMIES, PROJECTILES, PICKUPS
"""

from typing import Optional, Any
import logging

from sensors.base import (
    Sensor, SensorRegistry, ThrottleConfig, SensorSearchConfig, ValidationIssue,
)
from protocol.schema import Enemy, Projectile, Laser, Projectiles, Pickup

logger = logging.getLogger(__name__)


class EnemiesSensor(Sensor[list[Enemy]]):
    """ENEMIES — combat: every frame, idle: every 15 frames."""

    name = "ENEMIES"
    throttle_config = ThrottleConfig(
        base_interval=1, dynamic=True,
        combat_interval=1, idle_interval=15,
    )
    search_config = SensorSearchConfig(
        strategy="partition", sort_by_distance=True,
    )
    produces_entities = True

    def parse(self, raw_data: Any, frame: int) -> Optional[list[Enemy]]:
        try:
            if not raw_data or not isinstance(raw_data, list):
                return None
            return [Enemy(**e) for e in raw_data if isinstance(e, dict)]
        except Exception as e:
            logger.error("ENEMIES parse error: %s", e)
            return None

    def validate(self, data: list[Enemy]) -> list[ValidationIssue]:
        issues = []
        for e in data:
            if e.hp < 0:
                issues.append(ValidationIssue(
                    issue_id="ENEMY_NEGATIVE_HP",
                    field_path=f"{e.id}.hp",
                    severity="error",
                    message=f"Enemy {e.id} has negative HP: {e.hp}",
                    actual_value=e.hp,
                    expected_value=">= 0",
                ))
            if e.max_hp <= 0:
                issues.append(ValidationIssue(
                    issue_id="ENEMY_INVALID_MAX_HP",
                    field_path=f"{e.id}.max_hp",
                    severity="warning",
                    message=f"Enemy {e.id} max_hp={e.max_hp}",
                    actual_value=e.max_hp,
                ))
        return issues


class ProjectilesSensor(Sensor[Projectiles]):
    """PROJECTILES — combat: every frame, idle: every 15 frames."""

    name = "PROJECTILES"
    throttle_config = ThrottleConfig(
        base_interval=1, dynamic=True,
        combat_interval=1, idle_interval=15,
    )
    produces_entities = True

    def parse(self, raw_data: Any, frame: int) -> Optional[Projectiles]:
        try:
            if not isinstance(raw_data, dict):
                return None

            enemy_proj = [Projectile(**p) for p in raw_data.get("enemy_projectiles", []) if p]
            player_tears = [Projectile(**p) for p in raw_data.get("player_tears", []) if p]
            lasers = [Laser(**l) for l in raw_data.get("lasers", []) if l]

            return Projectiles(
                enemy_projectiles=enemy_proj,
                player_tears=player_tears,
                lasers=lasers,
            )
        except Exception as e:
            logger.error("PROJECTILES parse error: %s", e)
            return None

    def validate(self, data: Projectiles) -> list[ValidationIssue]:
        issues = []
        for p in data.enemy_projectiles:
            if p.height < -10:
                issues.append(ValidationIssue(
                    issue_id="PROJECTILE_HEIGHT", field_path=f"{p.id}.height",
                    severity="warning", message=f"Projectile {p.id} height={p.height}",
                ))
        return issues


class PickupsSensor(Sensor[list[Pickup]]):
    """PICKUPS — on room entry + every 15 frames."""

    name = "PICKUPS"
    throttle_config = ThrottleConfig(base_interval=15, dynamic=False)
    search_config = SensorSearchConfig(strategy="hybrid")
    produces_entities = True

    def parse(self, raw_data: Any, frame: int) -> Optional[list[Pickup]]:
        try:
            if not raw_data or not isinstance(raw_data, list):
                return []
            return [Pickup(**p) for p in raw_data if isinstance(p, dict)]
        except Exception as e:
            logger.error("PICKUPS parse error: %s", e)
            return None

    def validate(self, data: list[Pickup]) -> list[ValidationIssue]:
        issues = []
        for p in data:
            if p.price < 0:
                issues.append(ValidationIssue(
                    issue_id="PICKUP_NEGATIVE_PRICE", field_path=f"{p.id}.price",
                    severity="info", message=f"Pickup {p.id} price={p.price}",
                ))
        return issues


# ── Register ────────────────────────────────────────────────────────────

SensorRegistry.register(EnemiesSensor())
SensorRegistry.register(ProjectilesSensor())
SensorRegistry.register(PickupsSensor())
