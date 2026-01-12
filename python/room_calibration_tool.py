#!/usr/bin/env python3
"""
Room Calibration Tool - 房间校准工具

Usage:
    # 交互模式
    python3 room_calibration_tool.py

    # 批处理模式 (从文件读取)
    python3 room_calibration_tool.py --file measurements.txt

    # 直接提供数据
    python3 room_calibration_tool.py --data "71,1,320.5,395.7 71,2,280.5,280.5"

Features:
    1. 手动记录房间角落坐标
    2. 计算房间边界
    3. 导出JSON格式数据
"""

import json
import time
import math
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class Vector2D:
    x: float = 0.0
    y: float = 0.0

    def magnitude(self) -> float:
        return math.sqrt(self.x**2 + self.y**2)


# ==================== 角落配置 ====================

NORMAL_CORNERS = [
    ("1", "top_left", "左上角"),
    ("2", "top_right", "右上角"),
    ("3", "bottom_left", "左下角"),
    ("4", "bottom_right", "右下角"),
]

L_SHAPED_CORNERS = [
    ("1", "top_left", "左上角"),
    ("2", "top_right", "右上角"),
    ("3", "inner_corner", "内角(L型)"),
    ("4", "bottom_left", "左下角"),
    ("5", "bottom_right", "右下角"),
]


# ==================== 主程序 ====================


def parse_measurement(line: str) -> Optional[Dict]:
    """解析测量数据行"""
    parts = line.strip().split(",")
    if len(parts) < 3:
        return None

    try:
        room_idx = int(parts[0].strip())
        corner_num = parts[1].strip()
        coords = parts[2].strip().split()

        if len(coords) < 2:
            return None

        x = float(coords[0])
        y = float(coords[1])
        radius = float(parts[3].strip()) if len(parts) > 3 else 20.0

        # 确定角落名称
        corners = L_SHAPED_CORNERS if corner_num == "3" else NORMAL_CORNERS
        corner_name = None
        for num, name, desc in corners:
            if num == corner_num:
                corner_name = name
                break

        if not corner_name:
            return None

        return {
            "room_index": room_idx,
            "corner": corner_name,
            "corner_num": corner_num,
            "x": x,
            "y": y,
            "radius": radius,
            "timestamp": time.time(),
        }
    except (ValueError, IndexError):
        return None


def run_interactive():
    """交互模式"""
    print("=" * 60)
    print("Room Calibration Tool - 房间校准工具")
    print("=" * 60)
    print()
    print("输入格式: 房间索引,角落编号,X坐标 Y坐标,[碰撞半径]")
    print("示例: 71,1,320.5 395.7,20.0")
    print()
    print("角落编号:")
    print("  1=左上, 2=右上, 3=左下, 4=右下 (普通房间)")
    print("  1=左上, 2=右上, 3=内角, 4=左下, 5=右下 (L型房间)")
    print()
    print("直接回车结束输入")
    print("=" * 60)

    calibrations: Dict[int, Dict] = {}

    while True:
        try:
            line = input("> ").strip()
            if not line:
                break

            m = parse_measurement(line)
            if not m:
                print("  错误: 格式错误")
                continue

            room_idx = m["room_index"]

            if room_idx not in calibrations:
                calibrations[room_idx] = {"measurements": {}, "corners_recorded": set()}

            calibrations[room_idx]["measurements"][m["corner"]] = {
                "x": m["x"],
                "y": m["y"],
                "radius": m["radius"],
                "timestamp": m["timestamp"],
            }
            calibrations[room_idx]["corners_recorded"].add(m["corner"])

            print(
                f"  ✓ {m['corner']}: ({m['x']:.1f}, {m['y']:.1f}) r={m['radius']:.1f}"
            )

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"  错误: {e}")

    return calibrations


def run_batch(data_lines: List[str]) -> Dict:
    """批处理模式"""
    calibrations: Dict[int, Dict] = {}

    for line in data_lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        m = parse_measurement(line)
        if not m:
            print(f"  跳过无效行: {line}")
            continue

        room_idx = m["room_index"]

        if room_idx not in calibrations:
            calibrations[room_idx] = {"measurements": {}, "corners_recorded": set()}

        calibrations[room_idx]["measurements"][m["corner"]] = {
            "x": m["x"],
            "y": m["y"],
            "radius": m["radius"],
            "timestamp": m["timestamp"],
        }
        calibrations[room_idx]["corners_recorded"].add(m["corner"])

        print(f"  ✓ 房间 {room_idx} {m['corner']}: ({m['x']:.1f}, {m['y']:.1f})")

    return calibrations


def export_data(calibrations: Dict):
    """导出校准数据"""
    if not calibrations:
        print("\n没有数据可导出")
        return

    output = {
        "metadata": {
            "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_rooms": len(calibrations),
        },
        "calibrations": [],
    }

    for room_idx, data in calibrations.items():
        room_entry = {
            "room_index": room_idx,
            "corners_recorded": sorted(list(data["corners_recorded"])),
            "measurements": data["measurements"],
        }

        # 计算边界
        if len(data["measurements"]) >= 2:
            positions = [(m["x"], m["y"]) for m in data["measurements"].values()]
            min_x = min(p[0] for p in positions)
            max_x = max(p[0] for p in positions)
            min_y = min(p[1] for p in positions)
            max_y = max(p[1] for p in positions)

            room_entry["calculated_bounds"] = {
                "top_left": {"x": min_x, "y": min_y},
                "bottom_right": {"x": max_x, "y": max_y},
            }

            # 计算尺寸
            width = max_x - min_x
            height = max_y - min_y
            room_entry["calculated_size"] = {"width": width, "height": height}

        output["calibrations"].append(room_entry)

    output_path = Path(__file__).parent / "room_calibration_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n✓ 数据已保存到: {output_path}")
    print(f"  共 {len(calibrations)} 个房间")


def main():
    import sys

    # 解析命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--file" and len(sys.argv) > 2:
            # 从文件读取
            input_file = Path(sys.argv[2])
            if input_file.exists():
                with open(input_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                print(f"从文件读取: {input_file}")
                calibrations = run_batch(lines)
            else:
                print(f"文件不存在: {input_file}")
                return
        elif sys.argv[1] == "--data" and len(sys.argv) > 2:
            # 直接提供数据
            data_str = " ".join(sys.argv[2:])
            lines = data_str.split("\n")
            calibrations = run_batch(lines)
        else:
            print("用法:")
            print("  交互模式: python3 room_calibration_tool.py")
            print(
                "  批处理:   python3 room_calibration_tool.py --file measurements.txt"
            )
            print(
                "  直接:    python3 room_calibration_tool.py --data '71,1,320.5 395.7'"
            )
            return
    else:
        # 交互模式
        calibrations = run_interactive()

    # 导出
    export_data(calibrations)


if __name__ == "__main__":
    main()
