"""
Danger Channels - 危险物通道

提供炸弹、火焰危险物等数据。
"""

from typing import Dict, Any, Optional, List
import logging

try:
    from channels.base import DataChannel, ChannelConfig, ChannelRegistry
    from core.protocol.schema import BombData, FireHazardData
    from core.validation.known_issues import ValidationIssue, IssueSeverity
except ImportError:
    from .base import DataChannel, ChannelConfig, ChannelRegistry
    from ..core.protocol.schema import BombData, FireHazardData
    from ..core.validation.known_issues import ValidationIssue, IssueSeverity

logger = logging.getLogger(__name__)


class BombsChannel(DataChannel):
    """炸弹通道

    采集频率: LOW（每30帧）
    优先级: 5
    """

    name = "BOMBS"
    config = ChannelConfig(
        name=name,
        interval="LOW",
        priority=5,
        enabled=True,
        validation_enabled=True,
    )

    def parse(self, raw_data: Any, frame: int) -> Optional[List[BombData]]:
        """解析原始数据"""
        try:
            if not raw_data:
                return []

            bombs = []
            for bomb_raw in raw_data:
                if bomb_raw is not None:
                    bombs.append(BombData(**bomb_raw))
            return bombs
        except Exception as e:
            logger.error(f"Error parsing BOMBS: {e}")
            return None

    def validate(self, data: List[BombData]) -> List[ValidationIssue]:
        """验证数据"""
        issues = []

        for bomb in data:
            if bomb.timer < 0:
                issues.append(
                    ValidationIssue(
                        issue_id="BOMB_NEGATIVE_TIMER",
                        channel=self.name,
                        field_path=f"{bomb.id}.timer",
                        severity=IssueSeverity.WARNING,
                        message=f"Bomb {bomb.id} has negative timer: {bomb.timer}",
                        actual_value=bomb.timer,
                        expected_value=">= 0",
                    )
                )

            if bomb.explosion_radius < 0:
                issues.append(
                    ValidationIssue(
                        issue_id="BOMB_NEGATIVE_RADIUS",
                        channel=self.name,
                        field_path=f"{bomb.id}.explosion_radius",
                        severity=IssueSeverity.WARNING,
                        message=f"Bomb {bomb.id} has negative explosion_radius: {bomb.explosion_radius}",
                        actual_value=bomb.explosion_radius,
                        expected_value=">= 0",
                    )
                )

        return issues


class FireHazardsChannel(DataChannel):
    """火焰危险物通道

    采集频率: LOW（每30帧）
    优先级: 6
    """

    name = "FIRE_HAZARDS"
    config = ChannelConfig(
        name=name,
        interval="LOW",
        priority=6,
        enabled=True,
        validation_enabled=True,
    )

    def parse(self, raw_data: Any, frame: int) -> Optional[List[FireHazardData]]:
        """解析原始数据"""
        try:
            if not raw_data:
                return []

            fires = []
            for fire_raw in raw_data:
                if fire_raw is not None:
                    fires.append(FireHazardData(**fire_raw))
            return fires
        except Exception as e:
            logger.error(f"Error parsing FIRE_HAZARDS: {e}")
            return None

    def validate(self, data: List[FireHazardData]) -> List[ValidationIssue]:
        """验证数据"""
        issues = []

        for fire in data:
            if fire.hp < 0:
                issues.append(
                    ValidationIssue(
                        issue_id="FIRE_HAZARD_NEGATIVE_HP",
                        channel=self.name,
                        field_path=f"{fire.id}.hp",
                        severity=IssueSeverity.WARNING,
                        message=f"Fire hazard {fire.id} has negative HP: {fire.hp}",
                        actual_value=fire.hp,
                        expected_value=">= 0",
                    )
                )

            if fire.distance < 0:
                issues.append(
                    ValidationIssue(
                        issue_id="FIRE_HAZARD_NEGATIVE_DISTANCE",
                        channel=self.name,
                        field_path=f"{fire.id}.distance",
                        severity=IssueSeverity.WARNING,
                        message=f"Fire hazard {fire.id} has negative distance: {fire.distance}",
                        actual_value=fire.distance,
                        expected_value=">= 0",
                    )
                )

        return issues


ChannelRegistry.register_class(BombsChannel)
ChannelRegistry.register_class(FireHazardsChannel)
