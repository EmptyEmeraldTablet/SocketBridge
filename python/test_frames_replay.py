#!/usr/bin/env python3
"""
Test frames replay utility for SocketBridge room layout testing.

Usage:
    python3 test_frames_replay.py --list          # List all test frames
    python3 test_frames_replay.py --frame 0       # Replay frame 0
    python3 test_frames_replay.py --all           # Replay all frames
    python3 test_frames_replay.py --validate      # Validate data integrity
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from models import RoomInfo, GameStateData, Vector2D
from data_processor import DataProcessor
from environment import EnvironmentModel


def load_test_frames():
    """Load extracted test frames"""
    test_frames_path = Path(__file__).parent / "test_frames.json"
    if not test_frames_path.exists():
        print(f"Error: test_frames.json not found at {test_frames_path}")
        sys.exit(1)

    with open(test_frames_path, "r") as f:
        return json.load(f)


def validate_frame(frame_data):
    """Validate a test frame has all required fields"""
    required_fields = [
        "frame",
        "room_index",
        "player_position",
        "enemies",
        "room_info",
        "room_layout",
    ]
    missing = []

    for field in required_fields:
        if field not in frame_data:
            missing.append(field)

    if missing:
        return False, f"Missing fields: {missing}"

    return True, "OK"


def process_frame(frame_data, verbose=True):
    """Process a single test frame through the pipeline"""
    processor = DataProcessor()
    env_model = EnvironmentModel()

    # Create mock message
    mock_message = {
        "type": "DATA",
        "frame": frame_data["frame"],
        "timestamp": frame_data.get("timestamp", 0),
        "room_index": frame_data["room_index"],
        "payload": {
            "PLAYER_POSITION": [frame_data["player_position"]],
            "ENEMIES": frame_data["enemies"],
            "ROOM_INFO": frame_data["room_info"],
            "ROOM_LAYOUT": frame_data["room_layout"],
        },
    }

    # Process through data processor
    state = processor.process_message(mock_message)

    # Update environment
    if state.room_info:
        env_model.update_room(
            room_info=state.room_info,
            enemies=state.enemies,
            projectiles=state.projectiles,
            room_layout=state.raw_room_layout,
        )

    # Get player position
    player = state.get_primary_player()
    player_pos = player.position if player else None

    # Check bounds
    in_bounds = None
    if player_pos:
        in_bounds = env_model.game_map.is_in_bounds(player_pos)

    result = {
        "player_pos": (player_pos.x, player_pos.y) if player_pos else None,
        "in_bounds": in_bounds,
        "map_size": (env_model.game_map.pixel_width, env_model.game_map.pixel_height),
        "grid_size": env_model.game_map.grid_size,
        "static_obstacles": len(env_model.game_map.static_obstacles),
        "void_tiles": len(env_model.game_map.void_tiles),
    }

    if verbose:
        print(f"  Frame {frame_data['frame']}: Room {frame_data['room_index']}")
        print(f"    Player: {result['player_pos']}")
        print(f"    In Bounds: {result['in_bounds']}")
        print(f"    Map: {result['map_size']} px, grid_size={result['grid_size']}")
        print(
            f"    Obstacles: {result['static_obstacles']}, Void: {result['void_tiles']}"
        )

    return result


def list_frames(data):
    """List all test frames"""
    print("\nExtracted Test Frames:")
    print("-" * 60)

    for i, frame in enumerate(data["test_frames"]):
        desc = frame.get("description", f"Frame {i}")
        room_info = frame.get("room_info", {})
        layout = frame.get("room_layout")

        enemies = frame.get("enemies", [])
        pos = frame.get("player_position", {}).get("pos", {})

        print(f"\n{i}. {desc}")
        print(f"   Frame: {frame['frame']}, Room: {frame['room_index']}")
        print(
            f"   Room: shape={room_info.get('room_shape')}, grid={room_info.get('grid_width')}x{room_info.get('grid_height')}"
        )
        print(f"   Player: ({pos.get('x', 0):.1f}, {pos.get('y', 0):.1f})")
        print(f"   Enemies: {len(enemies)}")
        if layout:
            print(
                f"   Layout: grid_size={layout.get('grid_size')}, entries={len(layout.get('grid', {}))}"
            )
        else:
            print(f"   Layout: None")

    print("\n" + "-" * 60)


def validate_all(data):
    """Validate all test frames"""
    print("\nValidating Test Frames:")
    print("-" * 60)

    all_valid = True
    for i, frame in enumerate(data["test_frames"]):
        valid, message = validate_frame(frame)
        status = "✓" if valid else "✗"
        print(f"{status} Frame {i}: {frame.get('description', 'Unknown')}")
        if not valid:
            print(f"   Error: {message}")
            all_valid = False

    print("\n" + "-" * 60)
    if all_valid:
        print("All frames are valid!")
    else:
        print("Some frames have issues.")

    return all_valid


def replay_frame(data, index):
    """Replay a specific test frame"""
    if index < 0 or index >= len(data["test_frames"]):
        print(
            f"Error: Frame index {index} out of range (0-{len(data['test_frames']) - 1})"
        )
        return False

    print(f"\nReplaying Frame {index}:")
    print("-" * 60)

    frame = data["test_frames"][index]
    result = process_frame(frame)

    print("-" * 60)
    return True


def replay_all(data):
    """Replay all test frames"""
    print("\nReplaying All Test Frames:")
    print("=" * 60)

    results = []
    for i, frame in enumerate(data["test_frames"]):
        print(f"\n[{i + 1}/{len(data['test_frames'])}]")
        result = process_frame(frame, verbose=True)
        results.append(result)

    print("\n" + "=" * 60)
    print("Summary:")

    in_bounds_count = sum(1 for r in results if r["in_bounds"] is True)
    out_bounds_count = sum(1 for r in results if r["in_bounds"] is False)

    print(f"  In bounds: {in_bounds_count}")
    print(f"  Out of bounds: {out_bounds_count}")
    print(f"  Total: {len(results)}")

    return results


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]
    data = load_test_frames()

    if command == "--list":
        list_frames(data)
    elif command == "--validate":
        validate_all(data)
    elif command == "--frame":
        if len(sys.argv) < 3:
            print("Error: --frame requires an index")
            sys.exit(1)
        try:
            index = int(sys.argv[2])
            replay_frame(data, index)
        except ValueError:
            print("Error: Invalid frame index")
            sys.exit(1)
    elif command == "--all":
        replay_all(data)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
