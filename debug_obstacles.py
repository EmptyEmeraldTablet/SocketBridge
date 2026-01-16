#!/usr/bin/env python3
"""Debug script to trace where obstacles come from"""

import json
import gzip
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "python"))

from models import RoomInfo, GameStateData
from environment import GameMap, TileType
from data_processor import create_data_processor


def analyze_room(chunk_path):
    with gzip.open(chunk_path, "rt", encoding="utf-8") as f:
        data = json.load(f)

    messages = data.get("messages", [])
    print(f"Total messages: {len(messages)}")

    obstacle_counts = []
    prev_count = 0

    for i, msg in enumerate(messages):
        if isinstance(msg, dict):
            payload = msg.get("payload", {})

            if "ROOM_LAYOUT" in payload:
                layout = payload["ROOM_LAYOUT"]
                grid_size = layout.get("grid_size", 40)
                width = layout.get("width", 15)
                height = layout.get("height", 9)

                game_map = GameMap(grid_size=grid_size, width=width, height=height)
                room_info = RoomInfo(
                    room_index=payload.get("room_index", -1),
                    grid_width=width,
                    grid_height=height,
                    room_shape=payload.get("room_shape", 0),
                    top_left=payload.get("top_left"),
                )

                game_map.update_from_room_layout(room_info, layout, grid_size)

                count = len(game_map.static_obstacles)
                print(f"\nMessage {i}: Room {room_info.room_index}")
                print(f"  Grid: {width}x{height}, Shape: {room_info.room_shape}")
                print(f"  Static obstacles: {count}")
                print(
                    f"  Sample obstacles: {sorted(list(game_map.static_obstacles))[:10]}"
                )

                obstacle_counts.append((i, count, room_info.room_index))

                if count > 0 and prev_count == 0:
                    print(f"  ^^^ OBSTACLES APPEARED!")
                prev_count = count

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY: Obstacle counts over time")
    print(f"{'=' * 60}")
    for i, count, room_idx in obstacle_counts:
        print(f"Message {i}: Room {room_idx}, obstacles={count}")


if __name__ == "__main__":
    chunk_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "python/recordings/session_20260112_005209/session_20260112_005209_chunk_0000.json.gz"
    )
    analyze_room(chunk_path)
