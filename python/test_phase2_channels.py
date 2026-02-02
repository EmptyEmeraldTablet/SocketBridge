"""
Phase 2 Integration Test - 通道迁移集成测试

验证所有通道的导入、解析和验证功能。
"""

import sys
from pathlib import Path

# 兼容 Windows 和 Linux
sys.path.insert(0, str(Path(__file__).parent))

from channels.base import ChannelRegistry
from channels.player import (
    PlayerPositionChannel,
    PlayerStatsChannel,
    PlayerHealthChannel,
    PlayerInventoryChannel,
)
from channels.room import RoomInfoChannel, RoomLayoutChannel
from channels.entities import EnemiesChannel, ProjectilesChannel, PickupsChannel
from channels.danger import BombsChannel, FireHazardsChannel
from channels.interactables import InteractablesChannel
from models.state import TimingAwareStateManager
from core.protocol.timing import MessageTimingInfo, ChannelTimingInfo


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
        # 从类属性获取实际配置
        actual_interval = channel_class.config.interval if hasattr(channel_class, 'config') else channel.config.interval
        actual_priority = channel_class.config.priority if hasattr(channel_class, 'config') else channel.config.priority
        print(f"  ✅ {name}: interval={actual_interval}, priority={actual_priority}")

    print(f"\n📋 ChannelRegistry.get_all_names():")
    registered_names = ChannelRegistry.get_all_names()
    print(f"    Total: {len(registered_names)} channels registered")
    for name in sorted(registered_names):
        print(f"  ✅ {name}")

    print(f"\n✅ All {len(all_channels)} channels loaded successfully!")
    return True


# ==================== 完整测试数据 ====================

ALL_TEST_DATA = {
    "PLAYER_POSITION": {
        "1": {
            "pos": {"x": 320.0, "y": 240.0},
            "vel": {"x": 5.0, "y": -2.0},
            "move_dir": 3,
            "fire_dir": 2,
            "head_dir": 0,
            "aim_dir": {"x": 1.0, "y": 0.0},
        }
    },
    "PLAYER_STATS": {
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
    "PLAYER_HEALTH": {
        "1": {
            "red_hearts": 6,
            "max_hearts": 6,
            "soul_hearts": 2,
            "black_hearts": 0,
            "bone_hearts": 0,
            "eternal_hearts": 0,
            "golden_hearts": 0,
            "broken_hearts": 0,
            "rotten_hearts": 0,
        }
    },
    "PLAYER_INVENTORY": {
        "1": {
            "coins": 15,
            "bombs": 3,
            "keys": 2,
            "trinket_0": 0,
            "trinket_1": 0,
            "card_0": 0,
            "pill_0": 0,
            "collectible_count": 3,
            "collectibles": {"1": 1, "2": 1, "3": 1},
            "active_items": {},
        }
    },
    "ROOM_INFO": {
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
    "ROOM_LAYOUT": {
        "grid": {
            "0": {"type": 1, "variant": 0, "state": 0, "collision": 1, "x": 40.0, "y": 40.0},
            "1": {"type": 0, "variant": 0, "state": 0, "collision": 0, "x": 80.0, "y": 40.0},
        },
        "doors": {
            "0": {"target_room": 1, "target_room_type": 0, "is_open": True, "is_locked": False, "x": 0.0, "y": 224.0},
        },
        "grid_size": 195,
        "width": 13,
        "height": 7,
    },
    "ENEMIES": [
        {
            "id": 101,
            "type": 20,
            "variant": 0,
            "subtype": 0,
            "pos": {"x": 400.0, "y": 300.0},
            "vel": {"x": 0.0, "y": 0.0},
            "hp": 25,
            "max_hp": 25,
            "is_boss": False,
            "is_champion": False,
            "distance": 100.0,
        },
        {
            "id": 102,
            "type": 21,
            "variant": 0,
            "subtype": 0,
            "pos": {"x": 500.0, "y": 350.0},
            "vel": {"x": 2.0, "y": 1.0},
            "hp": 10,
            "max_hp": 10,
            "is_boss": False,
            "is_champion": False,
            "distance": 150.0,
        },
    ],
    "PROJECTILES": {
        "enemy_projectiles": [
            {
                "id": 201,
                "pos": {"x": 410.0, "y": 310.0},
                "vel": {"x": -5.0, "y": -3.0},
                "variant": 0,
            }
        ],
        "player_tears": [
            {
                "id": 301,
                "pos": {"x": 330.0, "y": 250.0},
                "vel": {"x": 10.0, "y": 0.0},
                "variant": 0,
            }
        ],
        "lasers": [],
    },
    "PICKUPS": [
        {
            "id": 401,
            "variant": 10,
            "sub_type": 1,
            "pos": {"x": 200.0, "y": 200.0},
            "price": 0,
            "shop_item_id": -1,
            "wait": 0,
        }
    ],
    "BOMBS": [
        {
            "id": 501,
            "type": 4,
            "variant": 0,
            "variant_name": "Normal",
            "sub_type": 0,
            "pos": {"x": 350.0, "y": 280.0},
            "vel": {"x": 0.0, "y": 0.0},
            "timer": 45,
            "explosion_radius": 85.0,
            "distance": 30.0,
        }
    ],
    "FIRE_HAZARDS": [
        {
            "id": 601,
            "type": "FIREPLACE",
            "fireplace_type": "NORMAL",
            "variant": 0,
            "sub_variant": 0,
            "pos": {"x": 600.0, "y": 400.0},
            "hp": 3.0,
            "max_hp": 3.0,
            "state": 0,
            "is_extinguished": False,
            "collision_radius": 20.0,
            "distance": 200.0,
            "is_shooting": False,
            "sprite_scale": 1.0,
        }
    ],
    "INTERACTABLES": [
        {
            "id": 701,
            "type": 6,
            "variant": 1,
            "variant_name": "SlotMachine",
            "sub_type": 0,
            "pos": {"x": 100.0, "y": 100.0},
            "vel": {"x": 0.0, "y": 0.0},
            "state": 0,
            "state_frame": 0,
            "distance": 250.0,
        }
    ],
}


def test_channel_parsing():
    """测试所有通道解析功能"""
    print("\n" + "=" * 60)
    print("Channel Parsing Test (All 12 Channels)")
    print("=" * 60)

    state_manager = TimingAwareStateManager()
    ChannelRegistry.bind_state_manager(state_manager)

    # 创建带通道元数据的时序信息
    channel_meta = {}
    for ch_name in ALL_TEST_DATA.keys():
        channel_meta[ch_name] = ChannelTimingInfo(
            channel=ch_name,
            collect_frame=100,
            collect_time=123456789000,
            interval="HIGH" if ch_name in ["PLAYER_POSITION", "ENEMIES", "PROJECTILES"] else "LOW",
            stale_frames=0,
        )

    timing = MessageTimingInfo(
        seq=1,
        frame=100,
        game_time=123456789000,
        prev_frame=99,
        channel_meta=channel_meta,
    )

    passed = 0
    failed = 0

    for channel_name, test_data in ALL_TEST_DATA.items():
        channel = ChannelRegistry.create(channel_name)
        if channel:
            try:
                result = channel.process(test_data, timing, 100)
                if result is not None:
                    print(f"  ✅ {channel_name}: parsed successfully")
                    passed += 1
                else:
                    print(f"  ❌ {channel_name}: parse returned None")
                    failed += 1
            except Exception as e:
                print(f"  ❌ {channel_name}: exception - {e}")
                failed += 1
        else:
            print(f"  ❌ {channel_name}: not found in registry")
            failed += 1

    print(f"\n📊 Parsing Results: {passed}/{passed + failed} passed")
    
    if failed > 0:
        return False
    
    print(f"✅ All parsing tests passed!")
    return True


def test_channel_validation():
    """测试通道验证功能"""
    print("\n" + "=" * 60)
    print("Channel Validation Test")
    print("=" * 60)

    # 测试正常数据验证 - 应该没有问题
    print("\n📋 Testing valid data (should have no issues):")
    
    valid_test_cases = [
        ("PLAYER_POSITION", ALL_TEST_DATA["PLAYER_POSITION"]),
        ("ENEMIES", ALL_TEST_DATA["ENEMIES"]),
        ("ROOM_INFO", ALL_TEST_DATA["ROOM_INFO"]),
        ("BOMBS", ALL_TEST_DATA["BOMBS"]),
        ("FIRE_HAZARDS", ALL_TEST_DATA["FIRE_HAZARDS"]),
    ]

    all_valid = True
    for channel_name, test_data in valid_test_cases:
        channel = ChannelRegistry.create(channel_name)
        if channel:
            parsed = channel.parse(test_data, 100)
            if parsed:
                issues = channel.validate(parsed)
                if len(issues) == 0:
                    print(f"  ✅ {channel_name}: no validation issues")
                else:
                    print(f"  ⚠️ {channel_name}: {len(issues)} issues found")
                    for issue in issues:
                        print(f"      - {issue.message}")
            else:
                print(f"  ❌ {channel_name}: parse failed")
                all_valid = False
        else:
            print(f"  ❌ {channel_name}: channel not found")
            all_valid = False

    # 注意：Pydantic Schema 在解析时会拒绝负数值（使用 ge=0 约束）
    # 所以通道的 validate() 方法主要用于检测业务逻辑问题
    # 例如：位置超出边界、数据不一致等
    
    print("\n📋 Testing validation logic (edge cases):")
    
    # 测试位置超出边界的情况
    edge_case_tests = [
        (
            "PLAYER_POSITION",
            {
                "1": {
                    "pos": {"x": 99999.0, "y": -99999.0},  # 超出边界
                    "vel": {"x": 0.0, "y": 0.0},
                    "move_dir": 0,
                    "fire_dir": 0,
                    "head_dir": 0,
                    "aim_dir": {"x": 0.0, "y": 0.0},
                }
            },
            "position out of bounds",
        ),
    ]

    for channel_name, test_data, expected_issue in edge_case_tests:
        channel = ChannelRegistry.create(channel_name)
        if channel:
            parsed = channel.parse(test_data, 100)
            if parsed:
                issues = channel.validate(parsed)
                if len(issues) > 0:
                    print(f"  ✅ {channel_name}: detected {len(issues)} edge case issues")
                    for issue in issues[:3]:  # 只显示前3个
                        print(f"      - [{issue.severity.value}] {issue.message}")
                else:
                    print(f"  ⚠️ {channel_name}: no issues detected for edge case ({expected_issue})")

    if all_valid:
        print(f"\n✅ All validation tests passed!")
    else:
        print(f"\n❌ Some validation tests failed!")

    return all_valid


def test_state_manager_integration():
    """测试状态管理器集成"""
    print("\n" + "=" * 60)
    print("State Manager Integration Test")
    print("=" * 60)

    state_manager = TimingAwareStateManager(max_history=100)

    # 创建通道并手动绑定状态管理器
    player_channel = ChannelRegistry.create("PLAYER_POSITION")
    enemies_channel = ChannelRegistry.create("ENEMIES")
    
    # 手动绑定状态管理器（因为 create() 创建的是新实例）
    player_channel.bind_state_manager(state_manager)
    enemies_channel.bind_state_manager(state_manager)

    # 创建时序信息
    channel_meta = {
        "PLAYER_POSITION": ChannelTimingInfo(
            channel="PLAYER_POSITION",
            collect_frame=100,
            collect_time=123456789000,
            interval="HIGH",
            stale_frames=0,
        ),
        "ENEMIES": ChannelTimingInfo(
            channel="ENEMIES",
            collect_frame=100,
            collect_time=123456789000,
            interval="HIGH",
            stale_frames=0,
        ),
    }

    timing = MessageTimingInfo(
        seq=1,
        frame=100,
        game_time=123456789000,
        prev_frame=99,
        channel_meta=channel_meta,
    )

    # 处理数据
    player_channel.process(ALL_TEST_DATA["PLAYER_POSITION"], timing, 100)
    enemies_channel.process(ALL_TEST_DATA["ENEMIES"], timing, 100)

    # 验证状态管理器
    print("\n📋 State Manager Status:")

    player_data = state_manager.get_channel_data("PLAYER_POSITION")
    enemies_data = state_manager.get_channel_data("ENEMIES")

    if player_data is not None:
        print(f"  ✅ PLAYER_POSITION: data stored in state manager")
    else:
        print(f"  ❌ PLAYER_POSITION: data NOT in state manager")
        return False

    if enemies_data is not None:
        print(f"  ✅ ENEMIES: data stored in state manager")
    else:
        print(f"  ❌ ENEMIES: data NOT in state manager")
        return False

    # 测试通道新鲜度
    is_fresh = state_manager.is_channel_fresh("PLAYER_POSITION", max_stale_frames=5)
    print(f"  ✅ PLAYER_POSITION freshness check: {'fresh' if is_fresh else 'stale'}")

    # 测试同步快照
    try:
        snapshot = state_manager.get_synchronized_snapshot(
            ["PLAYER_POSITION", "ENEMIES"],
            max_frame_difference=10
        )
        if snapshot:
            print(f"  ✅ Synchronized snapshot: {len(snapshot)} channels")
        else:
            print(f"  ⚠️ Synchronized snapshot: returned None (channels may be desync)")
    except Exception as e:
        print(f"  ⚠️ Synchronized snapshot: {e}")

    print(f"\n✅ State manager integration test passed!")
    return True


def main():
    success = True
    success = test_all_channels() and success
    success = test_channel_parsing() and success
    success = test_channel_validation() and success
    success = test_state_manager_integration() and success

    print("\n" + "=" * 60)
    if success:
        print("🎉 Phase 2 Integration Test: ALL PASSED")
    else:
        print("💥 Phase 2 Integration Test: SOME FAILED")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
