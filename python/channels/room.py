"""
Room Channels - 房间信息与布局通道

提供房间信息、布局、门状态等数据。
"""

from typing import Dict, Any, Optional, List
import logging

try:
    from channels.base import DataChannel, ChannelConfig, ChannelRegistry
    from core.protocol.schema import RoomInfoData, RoomLayoutData
    from core.validation.known_issues import ValidationIssue, IssueSeverity
except ImportError:
    from .base import DataChannel, ChannelConfig, ChannelRegistry
    from ..core.protocol.schema import RoomInfoData, RoomLayoutData
    from ..core.validation.known_issues import ValidationIssue, IssueSeverity

logger = logging.getLogger(__name__)


class RoomInfoChannel(DataChannel):
    """房间信息通道

    采集频率: LOW（每30帧）
    优先级: 4
    """

    name = "ROOM_INFO"
    config = ChannelConfig(
        name=name,
        interval="LOW",
        priority=4,
        enabled=True,
        validation_enabled=True,
    )

    def parse(self, raw_data: Dict[str, Any], frame: int) -> Optional[RoomInfoData]:
        """解析原始数据"""
        try:
            return RoomInfoData(**raw_data)
        except Exception as e:
            logger.error(f"Error parsing ROOM_INFO: {e}")
            return None

    def validate(self, data: RoomInfoData) -> List[ValidationIssue]:
        """验证数据"""
        issues = []

        if data.grid_width <= 0:
            issues.append(
                ValidationIssue(
                    issue_id="ROOM_INFO_INVALID_GRID_WIDTH",
                    channel=self.name,
                    field_path="grid_width",
                    severity=IssueSeverity.ERROR,
                    message=f"Invalid grid_width: {data.grid_width}",
                    actual_value=data.grid_width,
                    expected_value="> 0",
                )
            )

        if data.grid_height <= 0:
            issues.append(
                ValidationIssue(
                    issue_id="ROOM_INFO_INVALID_GRID_HEIGHT",
                    channel=self.name,
                    field_path="grid_height",
                    severity=IssueSeverity.ERROR,
                    message=f"Invalid grid_height: {data.grid_height}",
                    actual_value=data.grid_height,
                    expected_value="> 0",
                )
            )

        if data.enemy_count < 0:
            issues.append(
                ValidationIssue(
                    issue_id="ROOM_INFO_NEGATIVE_ENEMY_COUNT",
                    channel=self.name,
                    field_path="enemy_count",
                    severity=IssueSeverity.ERROR,
                    message=f"Negative enemy count: {data.enemy_count}",
                    actual_value=data.enemy_count,
                    expected_value=">= 0",
                )
            )

        return issues


class RoomLayoutChannel(DataChannel):
    """房间布局通道

    采集频率: LOW（每30帧，变化时）
    优先级: 2
    """

    name = "ROOM_LAYOUT"
    config = ChannelConfig(
        name=name,
        interval="LOW",
        priority=2,
        enabled=True,
        validation_enabled=True,
    )

    def parse(self, raw_data: Dict[str, Any], frame: int) -> Optional[RoomLayoutData]:
        """解析原始数据"""
        try:
            grid = raw_data.get("grid", {})
            doors = raw_data.get("doors", {})

            parsed_grid = {}
            for key, value in grid.items():
                if value is not None:
                    parsed_grid[key] = value

            parsed_doors = {}
            for key, value in doors.items():
                if value is not None:
                    parsed_doors[key] = value

            return RoomLayoutData(
                grid=parsed_grid,
                doors=parsed_doors,
                grid_size=raw_data.get("grid_size", 0),
                width=raw_data.get("width", 0),
                height=raw_data.get("height", 0),
            )
        except Exception as e:
            logger.error(f"Error parsing ROOM_LAYOUT: {e}")
            return None

    def validate(self, data: RoomLayoutData) -> List[ValidationIssue]:
        """验证数据"""
        issues = []

        if data.grid_size <= 0 and data.width > 0 and data.height > 0:
            issues.append(
                ValidationIssue(
                    issue_id="ROOM_LAYOUT_MISSING_GRID_SIZE",
                    channel=self.name,
                    field_path="grid_size",
                    severity=IssueSeverity.WARNING,
                    message="grid_size is 0 but width and height are set",
                    actual_value=data.grid_size,
                    expected_value="> 0 or calculated from width/height",
                )
            )

        return issues


ChannelRegistry.register_class(RoomInfoChannel)
ChannelRegistry.register_class(RoomLayoutChannel)
