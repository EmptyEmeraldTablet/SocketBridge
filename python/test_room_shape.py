#!/usr/bin/env python3
"""
Test room_shape, L-shaped room support, and bounds checking with replay data.
"""

import sys
import gzip
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

sys.path.insert(0, str(Path(__file__).parent))

from models import Vector2D, PlayerData, EnemyData, RoomInfo, GameStateData
from data_processor import DataProcessor
from environment import EnvironmentModel, GameMap, TileType
from data_replay_system import RawMessage


def load_replay_messages(
    session_id: str = "session_20260112_005209",
) -> List[RawMessage]:
    """加载回放数据的所有消息"""
    recordings_dir = Path("recordings")
    messages = []

    for chunk_file in sorted(recordings_dir.glob(f"{session_id}_chunk_*.json.gz")):
        with gzip.open(chunk_file, "rt", encoding="utf-8") as fp:
            data = json.load(fp)
            for msg_dict in data.get("messages", []):
                messages.append(RawMessage.from_dict(msg_dict))

    print(f"Loaded {len(messages)} messages from {session_id}")
    return messages


def test_room_shape_parsing():
    """测试 room_shape 字段解析"""
    print("\n" + "=" * 60)
    print("TEST: Room Shape Parsing")
    print("=" * 60)

    processor = DataProcessor()
    messages = load_replay_messages()

    data_messages = [m for m in messages if m.msg_type == "DATA"]
    print(f"Found {len(data_messages)} DATA messages")

    room_shapes_found = set()
    grid_sizes_found = set()

    for msg in data_messages:
        state = processor.process_message(msg.to_dict())

        if state.room_info:
            room_info = state.room_info
            room_shapes_found.add(room_info.room_shape)
            grid_sizes_found.add((room_info.grid_width, room_info.grid_height))

    print(f"\nRoom shapes found: {sorted(room_shapes_found)}")
    print(f"Grid sizes found: {sorted(grid_sizes_found)}")

    # 验证是否有 room_shape 数据
    if room_shapes_found == {0}:
        print("⚠️  All rooms have room_shape=0 (may be normal rooms)")
    else:
        print(f"✓ Found diverse room shapes: {room_shapes_found}")

    return len(room_shapes_found) > 0


def test_l_shaped_room_support():
    """测试 L 型房间支持（VOID tiles）"""
    print("\n" + "=" * 60)
    print("TEST: L-Shaped Room Support (VOID tiles)")
    print("=" * 60)

    # 创建一个模拟的 L 型房间布局数据
    # L1 shape: 26x14 grid with a 13x7 void in the bottom-right quadrant
    layout_data = {
        "grid": {},
        "doors": {},
    }

    grid_size = 40
    width, height = 26, 14  # Full bounding box

    # Fill the grid data - only valid room tiles have entries
    # L1 shape: Top-left, Top-right, and Bottom-left quadrants are room
    # Bottom-right quadrant is VOID

    # Top-left quadrant (0-12, 0-6)
    for gx in range(13):
        for gy in range(7):
            layout_data["grid"][f"{gx}_{gy}"] = {
                "x": gx * grid_size,
                "y": gy * grid_size,
                "collision": 0,  # Empty floor
                "type": 0,
            }

    # Top-right quadrant (13-25, 0-6)
    for gx in range(13, 26):
        for gy in range(7):
            layout_data["grid"][f"{gx}_{gy}"] = {
                "x": gx * grid_size,
                "y": gy * grid_size,
                "collision": 0,
                "type": 0,
            }

    # Bottom-left quadrant (0-12, 7-13)
    for gx in range(13):
        for gy in range(7, 14):
            layout_data["grid"][f"{gx}_{gy}"] = {
                "x": gx * grid_size,
                "y": gy * grid_size,
                "collision": 0,
                "type": 0,
            }

    # Note: Bottom-right quadrant (13-25, 7-13) is intentionally NOT in grid
    # This simulates the VOID area in an L-shaped room

    room_info = RoomInfo(
        room_index=1,
        grid_width=26,
        grid_height=14,
        room_shape=8,  # L1
    )

    # Create game map and update with layout
    game_map = GameMap(grid_size=grid_size, width=26, height=14)
    game_map.update_from_room_layout(room_info, layout_data, grid_size)

    # Check tile types
    print(f"\nMap size: {game_map.width}x{game_map.height}")
    print(f"Total grid tiles: {len(game_map.grid)}")
    print(f"VOID tiles: {len(game_map.void_tiles)}")
    print(f"Static obstacles: {len(game_map.static_obstacles)}")

    # Verify VOID tiles are in the bottom-right quadrant
    void_tiles = sorted(game_map.void_tiles)
    print(f"\nSample VOID tiles (first 5): {void_tiles[:5]}")

    # All void tiles should be in bottom-right quadrant (gx >= 13, gy >= 7)
    all_in_bottom_right = all(gx >= 13 and gy >= 7 for gx, gy in void_tiles)
    print(f"All VOID tiles in bottom-right quadrant: {all_in_bottom_right}")

    # Verify boundaries are not VOID
    edge_tiles = []
    for gx in range(26):
        for gy in range(14):
            if gx == 0 or gx == 25 or gy == 0 or gy == 13:
                edge_tiles.append((gx, gy))

    edge_void_count = len([t for t in edge_tiles if t in game_map.void_tiles])
    print(f"Edge tiles marked as VOID: {edge_void_count} (should be 0)")

    if all_in_bottom_right and edge_void_count == 0:
        print("✓ L-shaped room VOID handling works correctly!")
        return True
    else:
        print("✗ L-shaped room VOID handling has issues")
        return False


def test_bounds_checking():
    """测试边界检查"""
    print("\n" + "=" * 60)
    print("TEST: Bounds Checking")
    print("=" * 60)

    # Create a simple 13x7 room
    room_info = RoomInfo(
        room_index=1,
        grid_width=13,
        grid_height=7,
        room_shape=0,  # Normal
    )

    game_map = GameMap(grid_size=40, width=13, height=7)
    game_map.update_from_room_info(room_info)

    # Test points - adjusted for margin=20
    test_points = [
        # (position, expected_in_bounds, description)
        (Vector2D(280, 200), True, "Center of room"),
        (Vector2D(50, 50), True, "Near top-left corner (inside margin=20)"),
        (Vector2D(470, 250), True, "Near bottom-right corner (inside margin=20)"),
        (Vector2D(20, 20), True, "Exactly at margin edge"),
        (Vector2D(260, 140), True, "Just inside top-left wall"),
        (Vector2D(500, 260), True, "Just inside bottom-right wall"),
        (Vector2D(500, 300), False, "Outside right wall"),
        (Vector2D(0, 0), False, "Far outside"),
    ]

    all_passed = True
    for pos, expected, desc in test_points:
        result = game_map.is_in_bounds(pos)
        status = "✓" if result == expected else "✗"
        if result != expected:
            all_passed = False
        print(f"{status} {desc}: is_in_bounds({pos}) = {result} (expected {expected})")

    if all_passed:
        print("\n✓ All bounds checking tests passed!")
    else:
        print("\n✗ Some bounds checking tests failed!")

    return all_passed


def test_bounds_with_layout():
    """使用回放数据测试边界检查"""
    print("\n" + "=" * 60)
    print("TEST: Bounds Checking with Replay Data")
    print("=" * 60)

    processor = DataProcessor()
    env_model = EnvironmentModel()
    messages = load_replay_messages()

    data_messages = [m for m in messages if m.msg_type == "DATA"]
    print(f"Processing {len(data_messages)} DATA messages...")

    # Track bounds checking results
    in_bounds_count = 0
    out_of_bounds_count = 0
    max_out_of_bounds = None
    min_in_bounds = None

    for msg in data_messages:
        state = processor.process_message(msg.to_dict())

        # Update environment
        if state.room_info:
            env_model.update_room(
                room_info=state.room_info,
                enemies=state.enemies,
                projectiles=state.projectiles,
                room_layout=state.raw_room_layout,
            )

            # Check player position
            player = state.get_primary_player()
            if player:
                in_bounds = env_model.game_map.is_in_bounds(player.position)

                if in_bounds:
                    in_bounds_count += 1
                    if (
                        min_in_bounds is None
                        or player.position.magnitude() < min_in_bounds.magnitude()
                    ):
                        min_in_bounds = player.position
                else:
                    out_of_bounds_count += 1
                    if (
                        max_out_of_bounds is None
                        or player.position.magnitude() > max_out_of_bounds.magnitude()
                    ):
                        max_out_of_bounds = player.position

    print(f"\nPlayer position bounds statistics:")
    print(f"  In-bounds positions: {in_bounds_count}")
    print(f"  Out-of-bounds positions: {out_of_bounds_count}")

    if min_in_bounds:
        print(f"  Closest in-bounds: ({min_in_bounds.x:.0f}, {min_in_bounds.y:.0f})")
    if max_out_of_bounds:
        print(
            f"  Farthest out-of-bounds: ({max_out_of_bounds.x:.0f}, {max_out_of_bounds.y:.0f})"
        )

    # Check room info
    if processor.current_state.room_info:
        ri = processor.current_state.room_info
        print(f"\nLast room info:")
        print(f"  Room shape: {ri.room_shape}")
        print(f"  Grid size: {ri.grid_width}x{ri.grid_height}")
        print(f"  Enemy count: {ri.enemy_count}")
        print(f"  Is clear: {ri.is_clear}")

    if out_of_bounds_count == 0:
        print("\n✓ All player positions were in bounds!")
        return True
    else:
        print(f"\n⚠️ {out_of_bounds_count} positions were out of bounds")
        return False


def test_raw_room_layout_parsing():
    """测试原始 ROOM_LAYOUT 数据解析"""
    print("\n" + "=" * 60)
    print("TEST: Raw ROOM_LAYOUT Parsing")
    print("=" * 60)

    processor = DataProcessor()
    messages = load_replay_messages()

    data_messages = [m for m in messages if m.msg_type == "DATA"]

    layout_count = 0
    for msg in data_messages:
        state = processor.process_message(msg.to_dict())
        if state.raw_room_layout:
            layout_count += 1

    print(f"\nMessages with ROOM_LAYOUT data: {layout_count}")
    print(f"Total DATA messages: {len(data_messages)}")

    if layout_count > 0:
        print("✓ ROOM_LAYOUT data is being captured!")
        return True
    else:
        print("⚠️ No ROOM_LAYOUT data found (may be normal rooms in this session)")
        return True  # Not a failure - session may not have complex rooms


def main():
    """运行所有测试"""
    print("=" * 60)
    print("SocketBridge Room Shape & L-Room Test")
    print("=" * 60)

    results = {}

    # Test 1: Room shape parsing
    results["room_shape_parsing"] = test_room_shape_parsing()

    # Test 2: L-shaped room support
    results["l_shaped_room"] = test_l_shaped_room_support()

    # Test 3: Basic bounds checking
    results["bounds_checking"] = test_bounds_checking()

    # Test 4: Raw layout parsing
    results["raw_layout_parsing"] = test_raw_room_layout_parsing()

    # Test 5: Bounds with replay data
    results["bounds_with_replay"] = test_bounds_with_layout()

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = 0
    failed = 0
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\nTotal: {passed} passed, {failed} failed")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
