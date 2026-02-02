"""
Player Position Channel - 玩家位置通道

高频采集通道，提供玩家位置、速度、方向等信息。
作为新架构的模板通道实现。
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
import logging

from .base import DataChannel, ChannelConfig, ChannelRegistry
from ..core.protocol.schema import PlayerPositionData, Vector2DSchema
from ..core.validation.known_issues import ValidationIssue, IssueSeverity

logger = logging.getLogger(__name__)


@dataclass
class PlayerPositionChannelData:
    """玩家位置通道数据结构

    提供对玩家数据的统一访问接口。
    支持多玩家（虽然通常只有1个玩家）。
    """

    players: Dict[int, PlayerPositionData]

    def get_primary_player(self) -> Optional[PlayerPositionData]:
        """获取主玩家数据"""
        if 1 in self.players:
            return self.players[1]
        if self.players:
            return list(self.players.values())[0]
        return None

    def get_player(self, player_idx: int) -> Optional[PlayerPositionData]:
        """获取指定玩家数据"""
        return self.players.get(player_idx)

    def get_position(self, player_idx: int = 1) -> Optional[Tuple[float, float]]:
        """获取玩家位置 (x, y)"""
        player = self.get_player(player_idx)
        if player:
            return (player.pos.x, player.pos.y)
        return None

    def get_velocity(self, player_idx: int = 1) -> Optional[Tuple[float, float]]:
        """获取玩家速度 (x, y)"""
        player = self.get_player(player_idx)
        if player:
            return (player.vel.x, player.vel.y)
        return None

    def get_aim_direction(self, player_idx: int = 1) -> Optional[Tuple[float, float]]:
        """获取瞄准方向 (x, y)"""
        player = self.get_player(player_idx)
        if player:
            return (player.aim_dir.x, player.aim_dir.y)
        return None

    def get_all_positions(self) -> Dict[int, Tuple[float, float]]:
        """获取所有玩家位置"""
        return {idx: (p.pos.x, p.pos.y) for idx, p in self.players.items()}


class PlayerPositionChannel(DataChannel[PlayerPositionChannelData]):
    """玩家位置通道

    采集频率: HIGH（每帧）
    优先级: 10
    """

    name = "PLAYER_POSITION"
    config = ChannelConfig(
        name=name,
        interval="HIGH",
        priority=10,
        enabled=True,
        validation_enabled=True,
    )

    def parse(
        self, raw_data: Dict[str, Any], frame: int
    ) -> Optional[PlayerPositionChannelData]:
        """解析原始数据为结构化数据"""
        try:
            players = {}

            for idx_str, player_raw in raw_data.items():
                if player_raw is None:
                    continue

                idx = int(idx_str) if idx_str.isdigit() else int(idx_str)

                pos_data = player_raw.get("pos", {"x": 0, "y": 0})
                vel_data = player_raw.get("vel", {"x": 0, "y": 0})
                aim_data = player_raw.get("aim_dir", {"x": 0, "y": 0})

                if pos_data is None:
                    pos_data = {"x": 0, "y": 0}
                if vel_data is None:
                    vel_data = {"x": 0, "y": 0}
                if aim_data is None:
                    aim_data = {"x": 0, "y": 0}

                player = PlayerPositionData(
                    pos=Vector2DSchema(**pos_data)
                    if pos_data
                    else Vector2DSchema(x=0, y=0),
                    vel=Vector2DSchema(**vel_data)
                    if vel_data
                    else Vector2DSchema(x=0, y=0),
                    move_dir=player_raw.get("move_dir", 0),
                    fire_dir=player_raw.get("fire_dir", 0),
                    head_dir=player_raw.get("head_dir", 0),
                    aim_dir=Vector2DSchema(**aim_data)
                    if aim_data
                    else Vector2DSchema(x=0, y=0),
                )

                players[idx] = player

            return PlayerPositionChannelData(players=players)

        except Exception as e:
            logger.error(f"Error parsing PLAYER_POSITION: {e}")
            return None

    def validate(self, data: PlayerPositionChannelData) -> List[ValidationIssue]:
        """验证数据"""
        issues = []

        for idx, player in data.players.items():
            if player.pos.x < -10000 or player.pos.x > 10000:
                issues.append(
                    ValidationIssue(
                        issue_id="PLAYER_POSITION_OUT_OF_BOUNDS",
                        channel=self.name,
                        field_path=f"{idx}.pos.x",
                        severity=IssueSeverity.WARNING,
                        message=f"Player {idx} X position out of bounds: {player.pos.x}",
                        actual_value=player.pos.x,
                        expected_value="[-10000, 10000]",
                    )
                )

            if player.pos.y < -10000 or player.pos.y > 10000:
                issues.append(
                    ValidationIssue(
                        issue_id="PLAYER_POSITION_OUT_OF_BOUNDS",
                        channel=self.name,
                        field_path=f"{idx}.pos.y",
                        severity=IssueSeverity.WARNING,
                        message=f"Player {idx} Y position out of bounds: {player.pos.y}",
                        actual_value=player.pos.y,
                        expected_value="[-10000, 10000]",
                    )
                )

        return issues


ChannelRegistry.register_class(PlayerPositionChannel)


class PlayerStatsChannel(DataChannel):
    """玩家属性通道

    采集频率: LOW（每30帧）
    优先级: 5
    """

    name = "PLAYER_STATS"
    config = ChannelConfig(
        name=name,
        interval="LOW",
        priority=5,
        enabled=True,
        validation_enabled=True,
    )

    def parse(self, raw_data: Dict[str, Any], frame: int):
        """解析原始数据"""
        from ..core.protocol.schema import PlayerStatsData

        try:
            stats = {}
            for idx_str, stats_raw in raw_data.items():
                idx = int(idx_str) if idx_str.isdigit() else int(idx_str)

                stats[idx] = PlayerStatsData(**stats_raw)
            return stats
        except Exception as e:
            logger.error(f"Error parsing PLAYER_STATS: {e}")
            return None


class PlayerHealthChannel(DataChannel):
    """玩家生命值通道

    采集频率: LOW（每30帧）
    优先级: 8
    """

    name = "PLAYER_HEALTH"
    config = ChannelConfig(
        name=name,
        interval="LOW",
        priority=8,
        enabled=True,
        validation_enabled=True,
    )

    def parse(self, raw_data: Dict[str, Any], frame: int):
        """解析原始数据"""
        from ..core.protocol.schema import PlayerHealthData

        try:
            health = {}
            for idx_str, health_raw in raw_data.items():
                idx = int(idx_str) if idx_str.isdigit() else int(idx_str)
                health[idx] = PlayerHealthData(**health_raw)
            return health
        except Exception as e:
            logger.error(f"Error parsing PLAYER_HEALTH: {e}")
            return None


class PlayerInventoryChannel(DataChannel):
    """玩家物品栏通道

    采集频率: RARE（每90帧）
    优先级: 3
    """

    name = "PLAYER_INVENTORY"
    config = ChannelConfig(
        name=name,
        interval="RARE",
        priority=3,
        enabled=True,
        validation_enabled=True,
    )

    def parse(self, raw_data: Dict[str, Any], frame: int):
        """解析原始数据"""
        from ..core.protocol.schema import PlayerInventoryData

        try:
            inventory = {}
            for idx_str, inv_raw in raw_data.items():
                idx = int(idx_str) if idx_str.isdigit() else int(idx_str)
                inventory[idx] = PlayerInventoryData(**inv_raw)
            return inventory
        except Exception as e:
            logger.error(f"Error parsing PLAYER_INVENTORY: {e}")
            return None


ChannelRegistry.register_class(PlayerStatsChannel)
ChannelRegistry.register_class(PlayerHealthChannel)
ChannelRegistry.register_class(PlayerInventoryChannel)
