#!/usr/bin/env python3
"""Extract ROOM_INFO, ROOM_LAYOUT, INTERACTABLES, and FIRE_HAZARDS from gzipped recording files."""

import gzip
import json
import glob
import os
from collections import defaultdict
from datetime import datetime


def process_gzipped_chunk(filepath):
    """Process a single gzipped chunk file and extract all target data."""
    rooms = []
    layouts = []
    interactables = []
    fire_hazards = []

    session_name = os.path.basename(filepath).split("_chunk_")[0]

    try:
        with gzip.open(filepath, "rt", encoding="utf-8") as f:
            for line_num, line in enumerate(f):
                try:
                    data = json.loads(line.strip())

                    # Extract messages array
                    messages = data.get("messages", [])
                    for msg in messages:
                        if not isinstance(msg, dict):
                            continue
                        payload = msg.get("payload") or {}

                        # Extract ROOM_INFO
                        room_info = payload.get("ROOM_INFO")
                        if room_info:
                            room_record = {
                                "session": session_name,
                                "chunk_id": data.get("chunk_id", 0),
                                "frame": msg.get("frame", 0),
                                "room_index": room_info.get("room_idx"),
                                "stage": room_info.get("stage"),
                                "room_shape": room_info.get("room_shape"),
                                "room_type": room_info.get("room_type"),
                                "room_variant": room_info.get("room_variant"),
                                "grid_width": room_info.get("grid_width"),
                                "grid_height": room_info.get("grid_height"),
                                "top_left": room_info.get("top_left"),
                                "bottom_right": room_info.get("bottom_right"),
                                "is_first_visit": room_info.get("is_first_visit"),
                                "is_clear": room_info.get("is_clear"),
                                "first_visited_at": msg.get("timestamp"),
                            }
                            rooms.append(room_record)

                            # Extract ROOM_LAYOUT
                            room_layout = payload.get("ROOM_LAYOUT")
                            if room_layout:
                                layout_record = {
                                    "session": session_name,
                                    "room_index": room_info.get("room_idx"),
                                    "stage": room_info.get("stage"),
                                    "grid": room_layout.get("grid"),
                                    "doors": room_layout.get("doors"),
                                    "grid_size": room_layout.get("grid_size"),
                                    "width": room_layout.get("width"),
                                    "height": room_layout.get("height"),
                                    "obstacles": room_layout.get("obstacles", []),
                                }
                                layouts.append(layout_record)

                            # Extract INTERACTABLES
                            interactables_data = payload.get("INTERACTABLES", [])
                            if interactables_data:
                                for item in interactables_data:
                                    interactable_record = {
                                        "session": session_name,
                                        "room_index": room_info.get("room_idx"),
                                        "stage": room_info.get("stage"),
                                        "type": item.get("type"),
                                        "variant": item.get("variant"),
                                        "pos": item.get("pos"),
                                        "sub_type": item.get("sub_type"),
                                        "grid_position": item.get("grid_position"),
                                    }
                                    interactables.append(interactable_record)

                            # Extract FIRE_HAZARDS
                            fire_hazards_data = payload.get("FIRE_HAZARDS", [])
                            if fire_hazards_data:
                                for hazard in fire_hazards_data:
                                    hazard_record = {
                                        "session": session_name,
                                        "room_index": room_info.get("room_idx"),
                                        "stage": room_info.get("stage"),
                                        "type": hazard.get("type"),
                                        "pos": hazard.get("pos"),
                                        "variant": hazard.get("variant"),
                                    }
                                    fire_hazards.append(hazard_record)

                except json.JSONDecodeError as e:
                    continue

    except Exception as e:
        print(f"Error processing {filepath}: {e}")

    return rooms, layouts, interactables, fire_hazards


def deduplicate_rooms(rooms):
    """Remove duplicate rooms based on room_index and stage."""
    seen = set()
    unique_rooms = []
    for room in rooms:
        key = (room["session"], room["room_index"], room["stage"])
        if key not in seen:
            seen.add(key)
            unique_rooms.append(room)
    return unique_rooms


def deduplicate_layouts(layouts):
    """Remove duplicate layouts."""
    seen = set()
    unique_layouts = []
    for layout in layouts:
        key = (layout["session"], layout["room_index"], layout["stage"])
        if key not in seen:
            seen.add(key)
            unique_layouts.append(layout)
    return unique_layouts


def deduplicate_interactables(interactables):
    """Remove duplicate interactables."""
    seen = set()
    unique_interactables = []
    for item in interactables:
        key = (
            item["session"],
            item["room_index"],
            item["stage"],
            item["type"],
            item["variant"],
            item["pos"].get("x") if item["pos"] else None,
            item["pos"].get("y") if item["pos"] else None,
        )
        if key not in seen:
            seen.add(key)
            unique_interactables.append(item)
    return unique_interactables


def deduplicate_fire_hazards(fire_hazards):
    """Remove duplicate fire hazards."""
    seen = set()
    unique_hazards = []
    for hazard in fire_hazards:
        key = (
            hazard["session"],
            hazard["room_index"],
            hazard["stage"],
            hazard["type"],
            hazard["pos"].get("x") if hazard["pos"] else None,
            hazard["pos"].get("y") if hazard["pos"] else None,
        )
        if key not in seen:
            seen.add(key)
            unique_hazards.append(hazard)
    return unique_hazards


def main():
    # Find all chunk files from both sessions
    chunk_pattern = "/home/yolo_dev/newGym/SocketBridge/**/session_*_chunk_*.json.gz"
    chunk_files = sorted(glob.glob(chunk_pattern, recursive=True))

    print(f"Found {len(chunk_files)} chunk files to process")

    # Process all chunks
    all_rooms = []
    all_layouts = []
    all_interactables = []
    all_fire_hazards = []

    for filepath in chunk_files:
        print(f"Processing: {os.path.basename(filepath)}")
        rooms, layouts, interactables, fire_hazards = process_gzipped_chunk(filepath)
        all_rooms.extend(rooms)
        all_layouts.extend(layouts)
        all_interactables.extend(interactables)
        all_fire_hazards.extend(fire_hazards)

    # Deduplicate
    unique_rooms = deduplicate_rooms(all_rooms)
    unique_layouts = deduplicate_layouts(all_layouts)
    unique_interactables = deduplicate_interactables(all_interactables)
    unique_fire_hazards = deduplicate_fire_hazards(all_fire_hazards)

    # Build output structure
    output = {
        "metadata": {
            "extracted_at": datetime.now().isoformat(),
            "source_session": "session_20260112_005209",
            "chunks_processed": len(chunk_files),
            "total_frames_processed": len(all_rooms),
        },
        "rooms": unique_rooms,
        "layouts": unique_layouts,
        "interactables": unique_interactables,
        "fire_hazards": unique_fire_hazards,
    }

    # Write output
    output_path = (
        "/home/yolo_dev/newGym/SocketBridge/python/recordings/extracted_room_data.json"
    )
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    # Print summary
    print(f"\n=== EXTRACTION SUMMARY ===")
    print(f"Unique rooms: {len(unique_rooms)}")
    print(f"Unique layouts: {len(unique_layouts)}")
    print(f"Unique interactables: {len(unique_interactables)}")
    print(f"Unique fire_hazards: {len(unique_fire_hazards)}")
    print(f"\nOutput written to: {output_path}")

    # Count interactable types
    if unique_interactables:
        type_counts = defaultdict(int)
        for item in unique_interactables:
            type_counts[item["type"]] += 1
        print(f"\nInteractable types found:")
        for itype, count in sorted(type_counts.items()):
            print(f"  {itype}: {count}")

    # Count fire hazard types
    if unique_fire_hazards:
        hazard_counts = defaultdict(int)
        for hazard in unique_fire_hazards:
            hazard_counts[hazard["type"]] += 1
        print(f"\nFire hazard types found:")
        for htype, count in sorted(hazard_counts.items()):
            print(f"  {htype}: {count}")


if __name__ == "__main__":
    main()
