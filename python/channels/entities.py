"""
Entity Channels - 敌人、投射物、可拾取物通道

提供敌人、投射物、拾取物等游戏实体数据。
"""

from typing import Dict, Any, Optional, List
import logging

from .base import DataChannel, ChannelConfig, ChannelRegistry
from ..core.protocol.schema import EnemyData, ProjectilesData, PickupData
from ..core.validation.known_issues import ValidationIssue, IssueSeverity

logger = logging.getLogger(__name__)


class EnemiesChannel(DataChannel):
    """敌人通道

    采集频率: HIGH（每帧）
    优先级: 7
    """

    name = "ENEMIES"
    config = ChannelConfig(
        name=name,
        interval="HIGH",
        priority=7,
        enabled=True,
        validation_enabled=True,
    )

    def parse(self, raw_data: Any, frame: int) -> Optional[List[EnemyData]]:
        """解析原始数据"""
        try:
            if not raw_data:
                return []

            enemies = []
            for enemy_raw in raw_data:
                if enemy_raw is not None:
                    enemies.append(EnemyData(**enemy_raw))
            return enemies
        except Exception as e:
            logger.error(f"Error parsing ENEMIES: {e}")
            return None

    def validate(self, data: List[EnemyData]) -> List[ValidationIssue]:
        """验证数据"""
        issues = []

        for enemy in data:
            if enemy.hp < 0:
                issues.append(
                    ValidationIssue(
                        issue_id="ENEMY_NEGATIVE_HP",
                        channel=self.name,
                        field_path=f"{enemy.id}.hp",
                        severity=IssueSeverity.ERROR,
                        message=f"Enemy {enemy.id} has negative HP: {enemy.hp}",
                        actual_value=enemy.hp,
                        expected_value=">= 0",
                    )
                )

            if enemy.max_hp <= 0:
                issues.append(
                    ValidationIssue(
                        issue_id="ENEMY_INVALID_MAX_HP",
                        channel=self.name,
                        field_path=f"{enemy.id}.max_hp",
                        severity=IssueSeverity.WARNING,
                        message=f"Enemy {enemy.id} has invalid max_hp: {enemy.max_hp}",
                        actual_value=enemy.max_hp,
                        expected_value="> 0",
                    )
                )

            if enemy.distance < 0:
                issues.append(
                    ValidationIssue(
                        issue_id="ENEMY_NEGATIVE_DISTANCE",
                        channel=self.name,
                        field_path=f"{enemy.id}.distance",
                        severity=IssueSeverity.WARNING,
                        message=f"Enemy {enemy.id} has negative distance: {enemy.distance}",
                        actual_value=enemy.distance,
                        expected_value=">= 0",
                    )
                )

        return issues


class ProjectilesChannel(DataChannel):
    """投射物通道

    采集频率: HIGH（每帧）
    优先级: 9
    """

    name = "PROJECTILES"
    config = ChannelConfig(
        name=name,
        interval="HIGH",
        priority=9,
        enabled=True,
        validation_enabled=True,
    )

    def parse(self, raw_data: Dict[str, Any], frame: int) -> Optional[ProjectilesData]:
        """解析原始数据"""
        try:
            enemy_projectiles = []
            player_tears = []
            lasers = []

            if isinstance(raw_data, dict):
                for proj in raw_data.get("enemy_projectiles", []):
                    if proj is not None:
                        from ..core.protocol.schema import ProjectileData

                        enemy_projectiles.append(ProjectileData(**proj))

                for tear in raw_data.get("player_tears", []):
                    if tear is not None:
                        from ..core.protocol.schema import ProjectileData

                        player_tears.append(ProjectileData(**tear))

                for laser in raw_data.get("lasers", []):
                    if laser is not None:
                        from ..core.protocol.schema import LaserData

                        lasers.append(LaserData(**laser))

            return ProjectilesData(
                enemy_projectiles=enemy_projectiles,
                player_tears=player_tears,
                lasers=lasers,
            )
        except Exception as e:
            logger.error(f"Error parsing PROJECTILES: {e}")
            return None

    def validate(self, data: ProjectilesData) -> List[ValidationIssue]:
        """验证数据"""
        issues = []

        for proj in data.enemy_projectiles:
            if proj.height < -10:
                issues.append(
                    ValidationIssue(
                        issue_id="PROJECTILE_NEGATIVE_HEIGHT",
                        channel=self.name,
                        field_path=f"{proj.id}.height",
                        severity=IssueSeverity.WARNING,
                        message=f"Projectile {proj.id} has unusual height: {proj.height}",
                        actual_value=proj.height,
                        expected_value=">= -10",
                    )
                )

        for laser in data.lasers:
            if laser.max_distance <= 0:
                issues.append(
                    ValidationIssue(
                        issue_id="LASER_INVALID_DISTANCE",
                        channel=self.name,
                        field_path=f"{laser.id}.max_distance",
                        severity=IssueSeverity.WARNING,
                        message=f"Laser {laser.id} has invalid max_distance: {laser.max_distance}",
                        actual_value=laser.max_distance,
                        expected_value="> 0",
                    )
                )

        return issues


class PickupsChannel(DataChannel):
    """可拾取物通道

    采集频率: LOW（每30帧）
    优先级: 4
    """

    name = "PICKUPS"
    config = ChannelConfig(
        name=name,
        interval="LOW",
        priority=4,
        enabled=True,
        validation_enabled=True,
    )

    def parse(self, raw_data: Any, frame: int) -> Optional[List[PickupData]]:
        """解析原始数据"""
        try:
            if not raw_data:
                return []

            pickups = []
            for pickup_raw in raw_data:
                if pickup_raw is not None:
                    pickups.append(PickupData(**pickup_raw))
            return pickups
        except Exception as e:
            logger.error(f"Error parsing PICKUPS: {e}")
            return None

    def validate(self, data: List[PickupData]) -> List[ValidationIssue]:
        """验证数据"""
        issues = []

        for pickup in data:
            if pickup.price < 0:
                issues.append(
                    ValidationIssue(
                        issue_id="PICKUP_NEGATIVE_PRICE",
                        channel=self.name,
                        field_path=f"{pickup.id}.price",
                        severity=IssueSeverity.WARNING,
                        message=f"Pickup {pickup.id} has negative price: {pickup.price}",
                        actual_value=pickup.price,
                        expected_value=">= 0",
                    )
                )

            if pickup.wait < 0:
                issues.append(
                    ValidationIssue(
                        issue_id="PICKUP_NEGATIVE_WAIT",
                        channel=self.name,
                        field_path=f"{pickup.id}.wait",
                        severity=IssueSeverity.WARNING,
                        message=f"Pickup {pickup.id} has negative wait: {pickup.wait}",
                        actual_value=pickup.wait,
                        expected_value=">= 0",
                    )
                )

        return issues


ChannelRegistry.register_class(EnemiesChannel)
ChannelRegistry.register_class(ProjectilesChannel)
ChannelRegistry.register_class(PickupsChannel)
