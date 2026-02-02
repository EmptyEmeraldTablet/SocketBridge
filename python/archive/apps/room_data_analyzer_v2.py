"""
房间数据分析器 - 仅使用 ROOM_INFO 数据判定房间类型
并验证实体位置（INTERACTABLES, FIRE_HAZARDS）是否合法
"""

import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RoomInfo:
    """房间基本信息"""

    session: str
    room_index: int
    stage: int
    room_shape: int  # 1-8: 矩形, 9-12: L形
    room_type: int
    room_variant: int
    grid_width: int
    grid_height: int
    top_left: Tuple[float, float]
    bottom_right: Tuple[float, float]
    first_visited_at: int
    is_first_visit: bool
    is_clear: bool


@dataclass
class Entity:
    """实体信息"""

    session: str
    room_index: int
    stage: int
    entity_type: str
    pos: Tuple[float, float]
    variant: int = 0
    extra: Dict = field(default_factory=dict)


@dataclass
class LayoutObstacle:
    """布局障碍物"""

    session: str
    room_index: int
    stage: int
    grid_key: str
    obj_type: int
    variant: int
    pos: Tuple[float, float]
    collision: int
    state: int


class RoomDataAnalyzer:
    """房间数据分析器"""

    # 以撒的房间形状代码分类
    RECTANGLE_SHAPES = {1, 2, 3, 4, 5, 6, 7, 8}
    L_SHAPE_SHAPES = {9, 10, 11, 12}

    # 房间类型名称映射
    ROOM_TYPE_NAMES = {
        0: "UNKNOWN",
        1: "BEDROOM",
        2: "TREASURE",
        3: "SHOP",
        4: "MINIBOSS",
        5: "BOSS",
        6: "SECRET",
        7: "DEVIL",
        8: "ANGEL",
        9: "Sacrifice Room",
        10: "CHALLENGE",
        11: "CHALLENGE_ENTRY",
        12: "CLEAN_BEDROOM",
        13: "DIRTY_BEDROOM",
    }

    def __init__(self, input_file: str):
        self.input_file = Path(input_file)
        self.rooms: List[RoomInfo] = []
        self.interactables: List[Entity] = []
        self.fire_hazards: List[Entity] = []
        self.obstacles: List[LayoutObstacle] = []

    def load_data(self):
        """加载提取的数据"""
        with open(self.input_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 解析房间数据
        for room_data in data.get("rooms", []):
            self.rooms.append(
                RoomInfo(
                    session=room_data["session"],
                    room_index=room_data["room_index"],
                    stage=room_data["stage"],
                    room_shape=room_data["room_shape"],
                    room_type=room_data["room_type"],
                    room_variant=room_data["room_variant"],
                    grid_width=room_data["grid_width"],
                    grid_height=room_data["grid_height"],
                    top_left=(room_data["top_left"]["x"], room_data["top_left"]["y"]),
                    bottom_right=(
                        room_data["bottom_right"]["x"],
                        room_data["bottom_right"]["y"],
                    ),
                    first_visited_at=room_data["first_visited_at"],
                    is_first_visit=room_data["is_first_visit"],
                    is_clear=room_data["is_clear"],
                )
            )

        # 解析交互实体
        for item in data.get("interactables", []):
            self.interactables.append(
                Entity(
                    session=item["session"],
                    room_index=item["room_index"],
                    stage=item["stage"],
                    entity_type=f"INTERACTABLE_{item['type']}_{item['variant']}",
                    pos=(item["pos"]["x"], item["pos"]["y"]),
                    variant=item["variant"],
                    extra={"sub_type": item.get("sub_type", 0)},
                )
            )

        # 解析火焰危险物
        for item in data.get("fire_hazards", []):
            self.fire_hazards.append(
                Entity(
                    session=item["session"],
                    room_index=item["room_index"],
                    stage=item["stage"],
                    entity_type=item["type"],
                    pos=(item["pos"]["x"], item["pos"]["y"]),
                    variant=item["variant"],
                )
            )

        # 解析布局障碍物
        for layout in data.get("layouts", []):
            room_idx = layout["room_index"]
            stage = layout["stage"]
            session = layout["session"]
            for grid_key, grid_item in layout.get("grid", {}).items():
                self.obstacles.append(
                    LayoutObstacle(
                        session=session,
                        room_index=room_idx,
                        stage=stage,
                        grid_key=grid_key,
                        obj_type=grid_item["type"],
                        variant=grid_item["variant"],
                        pos=(grid_item["x"], grid_item["y"]),
                        collision=grid_item["collision"],
                        state=grid_item["state"],
                    )
                )

        print(
            f"加载完成: {len(self.rooms)} 房间, {len(self.interactables)} 交互实体, "
            f"{len(self.fire_hazards)} 火焰, {len(self.obstacles)} 障碍物"
        )

    def get_room_by_index(self, room_idx: int, stage: int) -> Optional[RoomInfo]:
        """根据房间索引和关卡获取房间信息"""
        for room in self.rooms:
            if room.room_index == room_idx and room.stage == stage:
                return room
        return None

    def determine_room_type(self, room: RoomInfo) -> Tuple[str, float, str]:
        """
        判定房间类型（仅使用 room_shape 代码）

        返回: (类型, 置信度, 判断依据)
        """
        shape_code = room.room_shape

        if shape_code in self.RECTANGLE_SHAPES:
            shape_name = self._get_rectangle_shape_name(shape_code)
            return ("rectangle", 1.0, f"Shape Code {shape_code} = {shape_name}")

        elif shape_code in self.L_SHAPE_SHAPES:
            corner_names = {
                9: "左上 (top-left)",
                10: "右上 (top-right)",
                11: "左下 (bottom-left)",
                12: "右下 (bottom-right)",
            }
            return (
                "L_shape",
                1.0,
                f"Shape Code {shape_code} = L形, 缺失{corner_names.get(shape_code, 'unknown')}",
            )

        else:
            return ("unknown", 0.5, f"未知 Shape Code: {shape_code}")

    def _get_rectangle_shape_name(self, shape_code: int) -> str:
        """获取矩形房间形状名称"""
        names = {
            1: "标准房间 (normal)",
            2: "横向贮藏室 (closet)",
            3: "纵向贮藏室 (closet)",
            4: "两倍高 (tall)",
            5: "竖长走廊 (tight)",
            6: "两倍宽 (wide)",
            7: "横长走廊 (tight)",
            8: "大房间 (large)",
        }
        return names.get(shape_code, "unknown")

    def validate_entity_position(self, entity: Entity) -> Tuple[bool, str]:
        """
        验证实体位置是否在房间边界内

        返回: (是否合法, 错误信息)
        """
        room = self.get_room_by_index(entity.room_index, entity.stage)

        if not room:
            return (
                False,
                f"未找到房间 (index={entity.room_index}, stage={entity.stage})",
            )

        min_x, min_y = room.top_left
        max_x, max_y = room.bottom_right

        x, y = entity.pos

        # 考虑碰撞箱偏移（玩家约15px，实体约20px）
        offset = 25.0

        # 检查是否在边界内（允许一定误差）
        if x < min_x - offset or x > max_x + offset:
            return False, f"X坐标 {x} 超出房间边界 [{min_x}, {max_x}]"

        if y < min_y - offset or y > max_y + offset:
            return False, f"Y坐标 {y} 超出房间边界 [{min_y}, {max_y}]"

        return True, "位置合法"

    def validate_obstacle_position(self, obstacle: LayoutObstacle) -> Tuple[bool, str]:
        """验证障碍物位置是否在房间边界内"""
        room = self.get_room_by_index(obstacle.room_index, obstacle.stage)

        if not room:
            return False, f"未找到房间"

        min_x, min_y = room.top_left
        max_x, max_y = room.bottom_right

        x, y = obstacle.pos

        # 障碍物应该在边界附近（门、墙等）
        # 但不应该严重超出边界
        tolerance = 60.0  # 1.5格

        if x < min_x - tolerance or x > max_x + tolerance:
            return False, f"障碍物 X={x} 超出房间边界 [{min_x}, {max_x}]"

        if y < min_y - tolerance or y > max_y + tolerance:
            return False, f"障碍物 Y={y} 超出房间边界 [{min_y}, {max_y}]"

        return True, "位置合法"

    def analyze_all(self) -> Dict:
        """分析所有房间和验证所有实体"""
        results = {
            "analysis_time": datetime.now().isoformat(),
            "summary": {
                "total_rooms": len(self.rooms),
                "rectangle_rooms": 0,
                "l_shape_rooms": 0,
                "unknown_rooms": 0,
            },
            "rooms": [],
            "entity_validation": {
                "interactables": [],
                "fire_hazards": [],
                "obstacles": [],
            },
            "errors": [],
        }

        # 分析房间类型
        for room in self.rooms:
            room_type, confidence, reason = self.determine_room_type(room)

            results["rooms"].append(
                {
                    "session": room.session,
                    "room_index": room.room_index,
                    "stage": room.stage,
                    "room_shape": room.room_shape,
                    "room_type_code": room.room_type,
                    "room_type_name": self.ROOM_TYPE_NAMES.get(
                        room.room_type, f"TYPE_{room.room_type}"
                    ),
                    "grid_size": f"{room.grid_width}x{room.grid_height}",
                    "detected_shape": room_type,
                    "confidence": confidence,
                    "reason": reason,
                    "bounds": {
                        "min_x": room.top_left[0],
                        "min_y": room.top_left[1],
                        "max_x": room.bottom_right[0],
                        "max_y": room.bottom_right[1],
                    },
                }
            )

            if room_type == "rectangle":
                results["summary"]["rectangle_rooms"] += 1
            elif room_type == "L_shape":
                results["summary"]["l_shape_rooms"] += 1
            else:
                results["summary"]["unknown_rooms"] += 1

        # 验证交互实体
        for entity in self.interactables:
            is_valid, message = self.validate_entity_position(entity)
            results["entity_validation"]["interactables"].append(
                {
                    "type": entity.entity_type,
                    "room_index": entity.room_index,
                    "stage": entity.stage,
                    "pos": {"x": entity.pos[0], "y": entity.pos[1]},
                    "valid": is_valid,
                    "message": message,
                }
            )
            if not is_valid:
                results["errors"].append(
                    {
                        "type": "INTERACTABLE",
                        "entity": entity.entity_type,
                        "room": entity.room_index,
                        "stage": entity.stage,
                        "message": message,
                    }
                )

        # 验证火焰危险物
        for entity in self.fire_hazards:
            is_valid, message = self.validate_entity_position(entity)
            results["entity_validation"]["fire_hazards"].append(
                {
                    "type": entity.entity_type,
                    "room_index": entity.room_index,
                    "stage": entity.stage,
                    "pos": {"x": entity.pos[0], "y": entity.pos[1]},
                    "valid": is_valid,
                    "message": message,
                }
            )
            if not is_valid:
                results["errors"].append(
                    {
                        "type": "FIRE_HAZARD",
                        "entity": entity.entity_type,
                        "room": entity.room_index,
                        "stage": entity.stage,
                        "message": message,
                    }
                )

        # 验证障碍物
        for obstacle in self.obstacles:
            is_valid, message = self.validate_obstacle_position(obstacle)
            results["entity_validation"]["obstacles"].append(
                {
                    "type": f"GRID_{obstacle.obj_type}_{obstacle.variant}",
                    "room_index": obstacle.room_index,
                    "stage": obstacle.stage,
                    "grid_key": obstacle.grid_key,
                    "pos": {"x": obstacle.pos[0], "y": obstacle.pos[1]},
                    "collision": obstacle.collision,
                    "valid": is_valid,
                    "message": message,
                }
            )
            if not is_valid:
                results["errors"].append(
                    {
                        "type": "OBSTACLE",
                        "entity": f"GRID_{obstacle.obj_type}_{obstacle.variant}",
                        "room": obstacle.room_index,
                        "stage": obstacle.stage,
                        "message": message,
                    }
                )

        return results

    def print_report(self, results: Dict):
        """打印分析报告"""
        print("\n" + "=" * 70)
        print("房间数据分析报告 - 仅使用 ROOM_INFO 数据")
        print("=" * 70)

        # 摘要
        summary = results["summary"]
        print(f"\n【房间统计】")
        print(f"  总房间数: {summary['total_rooms']}")
        print(f"  矩形房间: {summary['rectangle_rooms']}")
        print(f"  L形房间: {summary['l_shape_rooms']}")
        print(f"  未知类型: {summary['unknown_rooms']}")

        # 房间详情
        print(f"\n【房间详情】")
        print("-" * 70)
        for room in results["rooms"]:
            print(
                f"Room {room['room_index']:3d} (Stage {room['stage']}): "
                f"Shape={room['room_shape']}, {room['grid_size']}, "
                f"→ {room['detected_shape']} ({room['confidence']:.0%})"
            )
            print(f"    房间类型: {room['room_type_name']}")
            print(f"    判断依据: {room['reason']}")

        # 实体验证
        print(f"\n【实体位置验证】")
        print("-" * 70)

        # 交互实体
        interactables = results["entity_validation"]["interactables"]
        valid_count = sum(1 for i in interactables if i["valid"])
        print(f"交互实体: {len(interactables)} 个, {valid_count} 个合法")
        for item in interactables:
            status = "✅" if item["valid"] else "❌"
            print(
                f"  {status} {item['type']} @ Room {item['room_index']}: {item['message']}"
            )

        # 火焰危险物
        fire_hazards = results["entity_validation"]["fire_hazards"]
        valid_count = sum(1 for f in fire_hazards if f["valid"])
        print(f"\n火焰危险物: {len(fire_hazards)} 个, {valid_count} 个合法")
        for item in fire_hazards:
            status = "✅" if item["valid"] else "❌"
            print(
                f"  {status} {item['type']} @ Room {item['room_index']} ({item['pos']['x']:.0f}, {item['pos']['y']:.0f}): {item['message']}"
            )

        # 障碍物
        obstacles = results["entity_validation"]["obstacles"]
        valid_count = sum(1 for o in obstacles if o["valid"])
        print(f"\n布局障碍物: {len(obstacles)} 个, {valid_count} 个合法")

        # 错误汇总
        errors = results["errors"]
        if errors:
            print(f"\n【❌ 错误检测】")
            print("-" * 70)
            for error in errors:
                print(f"  {error['type']}: Room {error['room']} - {error['message']}")
        else:
            print(f"\n✅ 所有实体位置验证通过!")

        print("\n" + "=" * 70)

    def save_results(self, results: Dict, output_file: str):
        """保存分析结果"""
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n结果已保存到: {output_file}")


def main():
    input_file = (
        "/home/yolo_dev/newGym/SocketBridge/python/recordings/extracted_room_data.json"
    )
    output_file = (
        "/home/yolo_dev/newGym/SocketBridge/python/recordings/room_analysis_report.json"
    )

    analyzer = RoomDataAnalyzer(input_file)
    analyzer.load_data()

    results = analyzer.analyze_all()
    analyzer.print_report(results)
    analyzer.save_results(results, output_file)


if __name__ == "__main__":
    main()
