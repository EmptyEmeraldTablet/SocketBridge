#!/usr/bin/env python3
import json
import gzip
import sys


def check_recording(chunk_path):
    with gzip.open(chunk_path, "rt", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Data type: {type(data)}")

    if isinstance(data, dict):
        print(f"Keys in data: {list(data.keys())}")
        messages = data.get("messages", [])
        print(f"Messages: {len(messages)}")

        for i, msg in enumerate(messages):
            if isinstance(msg, dict):
                payload = msg.get("payload", {})
                if "ROOM_LAYOUT" in payload:
                    layout = payload["ROOM_LAYOUT"]
                    print(f"\nMessage {i}: ROOM_LAYOUT found")
                    print(
                        f"Keys: {list(layout.keys()) if isinstance(layout, dict) else type(layout)}"
                    )

                    if isinstance(layout, dict):
                        grid = layout.get("grid", {})
                        doors = layout.get("doors", {})
                        print(f"Grid entries: {len(grid)}")
                        print(f"Doors entries: {len(doors)}")

                        if isinstance(grid, dict):
                            print(f"\nSample grid entries (first 10):")
                            for j, (k, v) in enumerate(list(grid.items())[:10]):
                                print(f"  {k}: {v}")

                            tile_types = {}
                            for k, v in grid.items():
                                t = v.get("type", "unknown")
                                tile_types[t] = tile_types.get(t, 0) + 1
                            print(f"\nTile type distribution: {tile_types}")
                    break


if __name__ == "__main__":
    chunk_path = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "python/recordings/session_20260112_005209/session_20260112_005209_chunk_0000.json.gz"
    )
    check_recording(chunk_path)
