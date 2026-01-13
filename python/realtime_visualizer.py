"""
SocketBridge 实时房间可视化工具

直接从游戏数据实时读取并显示房间布局。
从各通道读取：ROOM_LAYOUT, FIRE_HAZARDS, BUTTONS, DESTRUCTIBLES, INTERACTABLES等
使用刷新方式在控制台显示，便于观察。

符号说明:
- .  空地（可行走）
- #  墙壁
- X  VOID区域（L型房间缺口）
- D  门
- E  实体（障碍物/可破坏物/可交互物/火堆等）
- P  玩家

使用方法:
    python realtime_visualizer.py
"""

import os
import sys
import time
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Vector2D, RoomInfo, GameStateData
from environment import GameMap, TileType
from data_processor import create_data_processor


class RealtimeVisualizer:
    """实时房间可视化器"""

    WALL = "#"
    VOID = "X"
    FLOOR = "."
    DOOR = "D"
    ENTITY = "E"
    PLAYER = "P"

    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors
        self.grid_size = 40.0

        if use_colors and os.name != "nt":
            self.COLOR_WALL = "\033[90m"
            self.COLOR_VOID = "\033[95m"
            self.COLOR_FLOOR = "\033[37m"
            self.COLOR_DOOR = "\033[93m"
            self.COLOR_ENTITY = "\033[94m"
            self.COLOR_PLAYER = "\033[92m"
            self.COLOR_RESET = "\033[0m"
        else:
            self.COLOR_WALL = self.COLOR_VOID = self.COLOR_FLOOR = ""
            self.COLOR_DOOR = self.COLOR_ENTITY = self.COLOR_PLAYER = ""
            self.COLOR_RESET = ""

    def world_to_grid(self, pos: Vector2D) -> Tuple[int, int]:
        return (int(pos.x / self.grid_size), int(pos.y / self.grid_size))

    def get_color(self, symbol: str) -> str:
        colors = {
            self.WALL: self.COLOR_WALL,
            self.VOID: self.COLOR_VOID,
            self.FLOOR: self.COLOR_FLOOR,
            self.DOOR: self.COLOR_DOOR,
            self.ENTITY: self.COLOR_ENTITY,
            self.PLAYER: self.COLOR_PLAYER,
        }
        return colors.get(symbol, "")

    def clear_screen(self):
        os.system("cls" if os.name == "nt" else "clear")

    def build_map_from_state(
        self, game_state: GameStateData
    ) -> Tuple[GameMap, Vector2D]:
        """从游戏状态构建地图"""

        room_info = game_state.room_info
        layout = game_state.raw_room_layout

        if room_info:
            grid_size = layout.get("grid_size", 40.0) if layout else 40.0
            self.grid_size = grid_size

            game_map = GameMap(
                grid_size=grid_size,
                width=room_info.grid_width,
                height=room_info.grid_height,
            )

            if layout:
                game_map.update_from_room_layout(room_info, layout, grid_size)
            else:
                game_map.update_from_room_info(room_info)
        else:
            game_map = GameMap(grid_size=40.0, width=13, height=7)

        player = game_state.get_primary_player()
        player_pos = player.position if player else Vector2D(0, 0)

        return game_map, player_pos

    def render(self, game_state: GameStateData) -> str:
        """渲染房间为ASCII字符串"""

        game_map, player_pos = self.build_map_from_state(game_state)
        width, height = game_map.width, game_map.height

        display: List[List[str]] = [
            [self.FLOOR for _ in range(width)] for _ in range(height)
        ]

        # 墙壁和VOID
        for (gx, gy), tile_type in game_map.grid.items():
            if tile_type == TileType.WALL:
                display[gy][gx] = self.WALL
            elif tile_type == TileType.VOID:
                display[gy][gx] = self.VOID

        # 门
        if game_state.raw_room_layout:
            doors = game_state.raw_room_layout.get("doors", {})
            for door_idx, door_info in doors.items():
                try:
                    direction = int(door_idx) if door_idx.isdigit() else 0
                    if direction == 0:
                        gx, gy = width // 2, 0
                    elif direction == 4:
                        gx, gy = width // 2, height - 1
                    elif direction == 2:
                        gx, gy = width - 1, height // 2
                    elif direction == 6:
                        gx, gy = 0, height // 2
                    else:
                        continue
                    if 0 <= gx < width and 0 <= gy < height:
                        display[gy][gx] = self.DOOR
                except (ValueError, TypeError):
                    pass

        # 实体 - 从game_state各通道读取
        self._mark_entities(display, game_state)

        # 玩家
        gx, gy = self.world_to_grid(player_pos)
        if 0 <= gx < width and 0 <= gy < height:
            display[gy][gx] = self.PLAYER

        return self._build_string(display, game_state, player_pos)

    def _mark_entities(self, display: List[List[str]], game_state: GameStateData):
        """标记所有实体（不区分类型）"""

        # 火堆
        for fh in game_state.fire_hazards.values():
            gx, gy = self.world_to_grid(fh.position)
            if 0 <= gx < len(display[0]) and 0 <= gy < len(display):
                display[gy][gx] = self.ENTITY

        # 按钮
        for btn in game_state.buttons.values():
            gx, gy = self.world_to_grid(btn.position)
            if 0 <= gx < len(display[0]) and 0 <= gy < len(display):
                display[gy][gx] = self.ENTITY

        # 可破坏物
        for dest in game_state.obstacles.values():
            gx, gy = self.world_to_grid(dest.position)
            if 0 <= gx < len(display[0]) and 0 <= gy < len(display):
                display[gy][gx] = self.ENTITY

        # 可交互实体
        for ent in game_state.interactables.values():
            gx, gy = self.world_to_grid(ent.position)
            if 0 <= gx < len(display[0]) and 0 <= gy < len(display):
                display[gy][gx] = self.ENTITY

        # 拾取物
        for p in game_state.pickups.values():
            gx, gy = self.world_to_grid(p.position)
            if 0 <= gx < len(display[0]) and 0 <= gy < len(display):
                display[gy][gx] = self.ENTITY

    def _build_string(
        self, display: List[List[str]], game_state: GameStateData, player_pos: Vector2D
    ) -> str:
        """构建输出字符串"""
        lines = []

        room_idx = game_state.room_index or -1
        frame = game_state.frame or 0
        lines.append(
            f"[Frame:{frame:06d}] Room:{room_idx:03d} ({len(display[0])}x{len(display)})"
        )
        lines.append("=" * (len(display[0]) + 2))

        for gy in range(len(display)):
            line = ""
            for gx in range(len(display[0])):
                symbol = display[gy][gx]
                color = self.get_color(symbol)
                if color and self.use_colors:
                    line += f"{color}{symbol}{self.COLOR_RESET}"
                else:
                    line += symbol
            lines.append("|" + line + "|")

        lines.append("=" * (len(display[0]) + 2))

        # 统计
        entity_count = (
            len(game_state.fire_hazards)
            + len(game_state.buttons)
            + len(game_state.obstacles)
            + len(game_state.interactables)
            + len(game_state.pickups)
        )
        lines.append(
            f"Entities: {entity_count} | Player: ({player_pos.x:.0f},{player_pos.y:.0f})"
        )
        lines.append(
            f"Fire:{len(game_state.fire_hazards)} Buttons:{len(game_state.buttons)} Destruct:{len(game_state.obstacles)}"
        )
        lines.append("")
        lines.append("Legend: .path  #wall  Xvoid  Ddoor  Eentity  Pplayer")

        return "\n".join(lines)

    def show(self, game_state: GameStateData, clear: bool = True):
        """显示（清屏刷新）"""
        if clear:
            self.clear_screen()
        print(self.render(game_state))

    def refresh(self, game_state: GameStateData):
        """刷新显示（覆盖上一帧）"""
        frame_str = self.render(game_state)
        lines = frame_str.split("\n")
        for line in lines:
            print(f"\r{' ' * 100}\r{line}", end="", flush=True)
        print()


def run_with_bridge(bridge, interval: float = 0.1):
    """配合isaac_bridge运行"""
    visualizer = RealtimeVisualizer()
    processor = create_data_processor()

    print("Starting real-time visualization...")
    print("Press Ctrl+C to stop")
    print("-" * 50)

    try:
        while True:
            raw_message = bridge.state
            if raw_message:
                try:
                    game_state = processor.process_message(raw_message)
                    visualizer.refresh(game_state)
                except Exception as e:
                    pass
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nStopped.")


def demo():
    """演示"""
    visualizer = RealtimeVisualizer()

    game_state = GameStateData()
    game_state.frame = 1234
    game_state.room_index = 42

    from models import (
        PlayerData,
        FireHazardData,
        ButtonData,
        DestructibleData,
        InteractableData,
        PickupData,
    )

    room_info = RoomInfo()
    room_info.grid_width = 13
    room_info.grid_height = 7
    game_state.room_info = room_info

    player = PlayerData(player_idx=1)
    player.position = Vector2D(260, 300)
    game_state.players[1] = player

    # 添加实体
    game_state.fire_hazards[1] = FireHazardData(fire_id=1, position=Vector2D(100, 100))
    game_state.fire_hazards[1].fire_type = "FIREPLACE"

    game_state.buttons[1] = ButtonData(button_id=1, position=Vector2D(400, 100))
    game_state.buttons[1].variant_name = "BOMB"

    game_state.obstacles[1] = DestructibleData(obj_id=1, position=Vector2D(100, 400))
    game_state.obstacles[1].obj_type = 9

    game_state.interactables[1] = InteractableData(
        entity_id=1, position=Vector2D(400, 400)
    )
    game_state.interactables[1].variant_name = "SLOT"

    game_state.pickups[1] = PickupData(pickup_id=1, position=Vector2D(260, 100))
    game_state.pickups[1].variant = 10

    print("Realtime Visualizer Demo - Normal Room")
    print("=" * 50)
    print()

    visualizer.show(game_state, clear=True)

    print("\n" + "-" * 50)
    print("Demo complete!")


def demo_l_shape():
    """演示L-shape房间（带VOID区域）"""
    visualizer = RealtimeVisualizer()

    from models import PlayerData
    from environment import GameMap, TileType

    # 创建L-shape房间状态
    game_state = GameStateData()
    game_state.frame = 5678
    game_state.room_index = 100

    room_info = RoomInfo()
    room_info.grid_width = 26  # L-shape大房间
    room_info.grid_height = 14
    room_info.room_shape = 9  # L1 (左上缺失)
    game_state.room_info = room_info

    # 手动创建layout数据
    layout = {
        "grid_size": 40.0,
        "doors": {
            "0": {"target_room": 99, "is_open": False},
            "2": {"target_room": 101, "is_open": False},
            "4": {"target_room": 102, "is_open": False},
        },
    }
    game_state.raw_room_layout = layout

    # 手动创建GameMap并应用L-shape处理
    game_map = GameMap(grid_size=40.0, width=26, height=14)
    game_map.update_from_room_layout(room_info, layout, 40.0)

    player = PlayerData(player_idx=1)
    player.position = Vector2D(540, 260)  # L1房间的可用区域
    game_state.players[1] = player

    print("L-Shape Room Demo (Shape 9 - Top-Left Missing)")
    print("=" * 50)
    print()

    # 渲染
    frame_str = visualizer.render(game_state)
    print(frame_str)

    print("\n" + "-" * 50)
    print("Note: X = VOID (L-shape missing corner area)")
    print("Demo complete!")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--lshape":
        demo_l_shape()
    else:
        demo()
