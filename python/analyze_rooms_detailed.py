"""
房间几何详细分析脚本

功能：
1. 分析每个房间的采样点分布
2. 检查采样点的墙壁方向分布
3. 对比推断边界与游戏边界
4. 识别可靠的L形房间
"""

import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# 配置
INPUT_DIR = Path("./room_data")
OUTPUT_DIR = Path("./analyzed_rooms")

# 加载数据
positions_file = INPUT_DIR / "recorded_positions.json"
rooms_file = INPUT_DIR / "rooms.json"

with open(positions_file, "r") as f:
    positions = json.load(f)

with open(rooms_file, "r") as f:
    rooms = json.load(f)

print("=" * 70)
print("房间几何详细分析")
print("=" * 70)
print(f"采样点总数: {len(positions)}")
print(f"房间总数: {len(rooms)}")
print()


# 解析房间时间范围
def parse_time(time_str):
    try:
        return datetime.fromisoformat(time_str)
    except:
        return None


sorted_rooms = sorted(
    [(idx, data) for idx, data in rooms.items()],
    key=lambda x: parse_time(x[1].get("first_visited_at", "")).min,
)

room_time_ranges = {}
for i, (idx, data) in enumerate(sorted_rooms):
    room_idx = int(idx)
    start_time = parse_time(data.get("first_visited_at", ""))
    if i + 1 < len(sorted_rooms):
        end_time = parse_time(sorted_rooms[i + 1][1].get("first_visited_at", ""))
    else:
        end_time = None
    room_time_ranges[room_idx] = (start_time, end_time)


# 匹配采样点到房间
def match_sample(sample):
    sample_time = parse_time(sample.get("recorded_at", ""))
    if not sample_time:
        return None
    for room_idx, (start, end) in room_time_ranges.items():
        if sample_time >= start:
            if end is None or sample_time < end:
                return room_idx
    return None


samples_by_room = defaultdict(list)
for sample in positions:
    room_idx = match_sample(sample)
    if room_idx is not None:
        samples_by_room[room_idx].append(sample)

print(f"匹配到 {len(samples_by_room)} 个房间")
print()


# 分析每个房间
def infer_wall_side(pos, room_tl, room_br, player_size):
    """推断玩家靠近哪面墙"""
    px, py = pos
    tl_x, tl_y = room_tl
    br_x, br_y = room_br

    dist_left = px - tl_x
    dist_right = br_x - px
    dist_top = py - tl_y
    dist_bottom = br_y - py

    min_dist = min(dist_left, dist_right, dist_top, dist_bottom)

    if min_dist == dist_left:
        return "left"
    elif min_dist == dist_right:
        return "right"
    elif min_dist == dist_top:
        return "top"
    else:
        return "bottom"


def cluster_coordinate(values, tolerance=10.0):
    """聚类坐标，返回主要值"""
    if not values:
        return None
    if len(values) == 1:
        return values[0]

    sorted_vals = sorted(values)
    best_cluster = None
    best_density = 0

    for i, v in enumerate(sorted_vals):
        cluster = [v]
        for j in range(i + 1, len(sorted_vals)):
            if sorted_vals[j] - cluster[-1] <= tolerance:
                cluster.append(sorted_vals[j])
            else:
                break

        if len(cluster) > len(sorted_vals) * 0.3:
            density = len(cluster) / tolerance
            if density > best_density:
                best_density = density
                best_cluster = cluster

    if best_cluster:
        return sum(best_cluster) / len(best_cluster)
    return sorted_vals[len(sorted_vals) // 2]


# 详细分析结果
analysis_results = {}

for room_idx in sorted(samples_by_room.keys()):
    samples = samples_by_room[room_idx]
    room_data = rooms.get(str(room_idx), {})

    print("-" * 70)
    print(f"Room {room_idx}")
    print(
        f"  Stage: {room_data.get('stage')}, Type: {room_data.get('room_type')}, Shape: {room_data.get('room_shape')}"
    )

    # 游戏边界
    game_tl = room_data.get("top_left", [])
    game_br = room_data.get("bottom_right", [])
    game_bounds = (
        (game_tl[0], game_tl[1], game_br[0], game_br[1])
        if game_tl and game_br
        else None
    )

    # 分析采样点
    wall_sides = {"left": 0, "right": 0, "top": 0, "bottom": 0}
    player_positions = []

    for sample in samples:
        pos = sample.get("position", [])
        room_tl = sample.get("room_top_left", [])
        room_br = sample.get("room_bottom_right", [])
        player_size = sample.get("player_size", 15.0)

        if pos and len(pos) >= 2 and room_tl and room_br:
            side = infer_wall_side(pos, room_tl, room_br, player_size)
            wall_sides[side] += 1
            player_positions.append(
                {
                    "pos": pos,
                    "side": side,
                    "inferred_wall": (
                        room_tl[0] + player_size
                        if side == "left"
                        else room_br[0] - player_size
                        if side == "right"
                        else pos[0],
                        room_tl[1] + player_size
                        if side == "top"
                        else room_br[1] - player_size
                        if side == "bottom"
                        else pos[1],
                    ),
                }
            )

    total = sum(wall_sides.values())
    print(f"  采样数: {total}")
    print(
        f"  墙壁分布: left={wall_sides['left']}, right={wall_sides['right']}, top={wall_sides['top']}, bottom={wall_sides['bottom']}"
    )

    # 检查各面采样是否充分（至少2个采样点）
    has_sufficient = {
        "left": wall_sides["left"] >= 2,
        "right": wall_sides["right"] >= 2,
        "top": wall_sides["top"] >= 2,
        "bottom": wall_sides["bottom"] >= 2,
    }

    missing_sides = [s for s, ok in has_sufficient.items() if not ok]
    print(f"  采样不足的面: {missing_sides if missing_sides else '无'}")

    # 推断边界
    left_walls = [
        p["inferred_wall"][0] for p in player_positions if p["side"] == "left"
    ]
    right_walls = [
        p["inferred_wall"][0] for p in player_positions if p["side"] == "right"
    ]
    top_walls = [p["inferred_wall"][1] for p in player_positions if p["side"] == "top"]
    bottom_walls = [
        p["inferred_wall"][1] for p in player_positions if p["side"] == "bottom"
    ]

    min_x = cluster_coordinate(left_walls) if left_walls else None
    max_x = cluster_coordinate(right_walls) if right_walls else None
    min_y = cluster_coordinate(top_walls) if top_walls else None
    max_y = cluster_coordinate(bottom_walls) if bottom_walls else None

    # 推断形状
    if len(missing_sides) == 0:
        shape = "rectangle"
        confidence = "高"
    elif len(missing_sides) == 1:
        shape = "L_shape?"
        confidence = "中低（需验证）"
    else:
        shape = "L_shape?"
        confidence = "低（采样不足）"

    print(f"  推断形状: {shape} ({confidence})")

    if game_bounds:
        print(
            f"  游戏边界: ({game_bounds[0]:.0f}, {game_bounds[1]:.0f}) - ({game_bounds[2]:.0f}, {game_bounds[3]:.0f})"
        )

    if min_x and max_x and min_y and max_y:
        print(f"  推断边界: ({min_x:.0f}, {min_y:.0f}) - ({max_x:.0f}, {max_y:.0f})")
        print(f"  推断尺寸: {max_x - min_x:.0f} x {max_y - min_y:.0f}")

        if game_bounds:
            # 检查边界差异
            diff_x1 = abs(min_x - game_bounds[0])
            diff_y1 = abs(min_y - game_bounds[1])
            diff_x2 = abs(max_x - game_bounds[2])
            diff_y2 = abs(max_y - game_bounds[3])
            max_diff = max(diff_x1, diff_y1, diff_x2, diff_y2)

            if max_diff < 20:
                match = "✅ 匹配"
            elif max_diff < 50:
                match = "⚠️ 接近"
            else:
                match = "❌ 差异大"
            print(f"  边界对比: {match} (最大差异: {max_diff:.0f})")

    # 保存结果
    analysis_results[room_idx] = {
        "stage": room_data.get("stage"),
        "room_type": room_data.get("room_type"),
        "room_shape": room_data.get("room_shape"),
        "game_bounds": game_bounds,
        "sample_count": total,
        "wall_distribution": wall_sides,
        "missing_sides": missing_sides,
        "inferred_bounds": (min_x, min_y, max_x, max_y)
        if all([min_x, max_x, min_y, max_y])
        else None,
        "shape": shape,
        "confidence": confidence,
    }

print()
print("=" * 70)
print("L形房间详细分析")
print("=" * 70)

# 重点分析被标记为L形的房间
l_shape_candidates = [
    (73, "Stage 4, Shape 2 - 标准的L型代码"),
    (45, "Stage 2, Shape 3 - 商店房间"),
    (121, "Stage 3, Shape 1 - 恶魔房"),
]

for room_idx, description in l_shape_candidates:
    if room_idx not in samples_by_room:
        continue

    samples = samples_by_room[room_idx]
    room_data = rooms.get(str(room_idx), {})

    print(f"\nRoom {room_idx}: {description}")
    print("-" * 50)

    # 详细列出采样点
    print("采样点详情:")
    for i, sample in enumerate(samples):
        pos = sample.get("position", [])
        room_tl = sample.get("room_top_left", [])
        room_br = sample.get("room_bottom_right", [])

        side = infer_wall_side(pos, room_tl, room_br, 15.0)

        # 计算玩家到各边的距离
        px, py = pos
        dist_left = px - room_tl[0]
        dist_right = room_br[0] - px
        dist_top = py - room_tl[1]
        dist_bottom = room_br[1] - py

        print(
            f"  [{i + 1}] ({px:>7.1f}, {py:>7.1f}) | 到墙距离: L={dist_left:>5.1f} R={dist_right:>5.1f} T={dist_top:>5.1f} B={dist_bottom:>5.1f} -> {side}"
        )

# 保存详细结果
output_file = OUTPUT_DIR / "detailed_analysis.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(analysis_results, f, indent=2, ensure_ascii=False)
print(f"\n详细分析结果已保存到: {output_file}")
