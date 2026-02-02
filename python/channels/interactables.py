"""
Interactables Channel - 可互动实体通道

提供老虎机、献血机、商店等可互动实体数据。
"""

from typing import Dict, Any, Optional, List
import logging

try:
    from channels.base import DataChannel, ChannelConfig, ChannelRegistry
    from core.protocol.schema import InteractableData
    from core.validation.known_issues import ValidationIssue, IssueSeverity
except ImportError:
    from .base import DataChannel, ChannelConfig, ChannelRegistry
    from ..core.protocol.schema import InteractableData
    from ..core.validation.known_issues import ValidationIssue, IssueSeverity

logger = logging.getLogger(__name__)


class InteractablesChannel(DataChannel):
    """可互动实体通道

    采集频率: LOW（每30帧）
    优先级: 4
    """

    name = "INTERACTABLES"
    config = ChannelConfig(
        name=name,
        interval="LOW",
        priority=4,
        enabled=True,
        validation_enabled=True,
    )

    def parse(self, raw_data: Any, frame: int) -> Optional[List[InteractableData]]:
        """解析原始数据"""
        try:
            if not raw_data:
                return []

            interactables = []
            for item_raw in raw_data:
                if item_raw is not None:
                    interactables.append(InteractableData(**item_raw))
            return interactables
        except Exception as e:
            logger.error(f"Error parsing INTERACTABLES: {e}")
            return None

    def validate(self, data: List[InteractableData]) -> List[ValidationIssue]:
        """验证数据"""
        issues = []

        for item in data:
            if item.state < 0:
                issues.append(
                    ValidationIssue(
                        issue_id="INTERACTABLE_NEGATIVE_STATE",
                        channel=self.name,
                        field_path=f"{item.id}.state",
                        severity=IssueSeverity.WARNING,
                        message=f"Interactable {item.id} has negative state: {item.state}",
                        actual_value=item.state,
                        expected_value=">= 0",
                    )
                )

            if item.distance < 0:
                issues.append(
                    ValidationIssue(
                        issue_id="INTERACTABLE_NEGATIVE_DISTANCE",
                        channel=self.name,
                        field_path=f"{item.id}.distance",
                        severity=IssueSeverity.WARNING,
                        message=f"Interactable {item.id} has negative distance: {item.distance}",
                        actual_value=item.distance,
                        expected_value=">= 0",
                    )
                )

        return issues


ChannelRegistry.register_class(InteractablesChannel)
