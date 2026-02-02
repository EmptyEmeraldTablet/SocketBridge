"""
Phase 2 Integration Test - 通道迁移集成测试

验证所有通道的导入、解析和验证功能。
"""

import sys

sys.path.insert(0, "/home/yolo_dev/newGym/SocketBridge")

from python.channels.base import ChannelRegistry
from python.channels.player import (
    PlayerPositionChannel,
    PlayerStatsChannel,
    PlayerHealthChannel,
    PlayerInventoryChannel,
)
from python.channels.room import RoomInfoChannel, RoomLayoutChannel
from python.channels.entities import EnemiesChannel, ProjectilesChannel, PickupsChannel
from python.channels.danger import BombsChannel, FireHazardsChannel
from python.channels.interactables import InteractablesChannel
from python.models.state import TimingAwareStateManager
from python.core.protocol.timing import MessageTimingInfo


def test_all_channels():
    """测试所有通道"""
    print("=" * 60)
    print("Phase 2 Channel Migration Integration Test")
    print("=" * 60)

    all_channels = [
        ("PLAYER_POSITION", PlayerPositionChannel),
        ("PLAYER_STATS", PlayerStatsChannel),
        ("PLAYER_HEALTH", PlayerHealthChannel),
        ("PLAYER_INVENTORY", PlayerInventoryChannel),
        ("ROOM_INFO", RoomInfoChannel),
        ("ROOM_LAYOUT", RoomLayoutChannel),
        ("ENEMIES", EnemiesChannel),
        ("PROJECTILES", ProjectilesChannel),
        ("PICKUPS", PickupsChannel),
        ("BOMBS", BombsChannel),
        ("FIRE_HAZARDS", FireHazardsChannel),
        ("INTERACTABLES", InteractablesChannel),
    ]

    print(f"\n📋 Registered Channels: {len(all_channels)}")
    for name, channel_class in all_channels:
        channel = channel_class()
        print(
            f"  ✅ {name}: interval={channel.config.interval}, priority={channel.config.priority}"
        )

    print(f"\n📋 ChannelRegistry.get_all_names():")
    registered_names = ChannelRegistry.get_all_names()
    print(
        f"    _channel_classes keys: {sorted(ChannelRegistry._channel_classes.keys())}"
    )
    for name in sorted(registered_names):
        print(f"  ✅ {name}")

    print(f"\n✅ All {len(all_channels)} channels loaded successfully!")
    return True


def test_channel_parsing():
    """测试通道解析功能"""
    print("\n" + "=" * 60)
    print("Channel Parsing Test")
    print("=" * 60)

    state_manager = TimingAwareStateManager()
    ChannelRegistry.bind_state_manager(state_manager)

    test_cases = [
        (
            "PLAYER_POSITION",
            {
                "1": {
                    "pos": {"x": 320.0, "y": 240.0},
                    "vel": {"x": 5.0, "y": -2.0},
                    "move_dir": 3,
                    "fire_dir": 2,
                    "head_dir": 0,
                    "aim_dir": {"x": 1.0, "y": 0.0},
                }
            },
        ),
        (
            "PLAYER_STATS",
            {
                "1": {
                    "player_type": 0,
                    "damage": 3.5,
                    "speed": 1.0,
                    "tears": 10.0,
                    "range": 300.0,
                    "shot_speed": 1.0,
                    "luck": 0,
                    "can_fly": False,
                    "size": 10.0,
                }
            },
        ),
        (
            "ROOM_INFO",
            {
                "room_type": 2,
                "room_shape": 1,
                "room_idx": 5,
                "stage": 2,
                "grid_width": 13,
                "grid_height": 7,
                "top_left": {"x": 0, "y": 0},
                "bottom_right": {"x": 832, "y": 448},
                "is_clear": False,
                "enemy_count": 5,
            },
        ),
    ]

    timing = MessageTimingInfo(
        seq=1,
        frame=100,
        game_time=123456789000,
        prev_frame=99,
        channel_meta={},
    )

    for channel_name, test_data in test_cases:
        channel = ChannelRegistry.create(channel_name)
        if channel:
            result = channel.process(test_data, timing, 100)
            if result:
                print(f"  ✅ {channel_name}: parsed successfully")
            else:
                print(f"  ❌ {channel_name}: parsing failed")
                return False
        else:
            print(f"  ❌ {channel_name}: not found in registry")
            return False

    print(f"\n✅ All parsing tests passed!")
    return True


def main():
    success = True
    success = test_all_channels() and success
    success = test_channel_parsing() and success

    print("\n" + "=" * 60)
    if success:
        print("🎉 Phase 2 Integration Test: PASSED")
    else:
        print("💥 Phase 2 Integration Test: FAILED")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
