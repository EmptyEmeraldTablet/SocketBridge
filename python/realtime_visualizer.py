"""
SocketBridge 实时房间可视化工具

功能:
1. 从录制数据回放并实时显示房间布局
2. 支持两种模式:
   - 回放模式: 从录制的数据回放
   - 实时模式: 连接游戏实时显示

数据来源:
- ROOM_LAYOUT: 房间几何信息
- ROOM_INFO: 房间元数据
- FIRE_HAZARDS: 火堆
- BUTTONS: 按钮
- DESTRUCTIBLES: 可破坏物
- INTERACTABLES: 可交互实体
- PICKUPS: 拾取物
- PLAYER_POSITION: 玩家位置

使用方法:
    # 回放模式
    python realtime_visualizer.py replay <session_id>
    python realtime_visualizer.py replay --speed 2.0
    python realtime_visualizer.py replay --latest  # 最新录制

    # 实时模式 (连接游戏)
    python realtime_visualizer.py live

    # 列出所有录制会话
    python realtime_visualizer.py list
"""

import os
import sys
import time
import argparse
from typing import Dict, List, Optional, Tuple
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Vector2D, RoomInfo, GameStateData
from environment import GameMap, TileType
from data_processor import create_data_processor
from isaac_bridge import IsaacBridge, GameDataAccessor
from data_replay_system import SessionReplayer, create_replayer


class RoomVisualizer:
    """房间实时可视化器"""

    # 符号定义
    WALL = "#"
    VOID = "X"
    FLOOR = "."
    DOOR = "D"
    ENTITY = "E"
    PLAYER = "P"

    def __init__(self, use_colors: bool = True):
        self.use_colors = use_colors
        self.grid_size = 40.0

        # 颜色配置
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
        """世界坐标转网格坐标"""
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

    def render(self, game_state: GameStateData, game_map: GameMap) -> str:
        """渲染房间为ASCII字符串"""
        self.grid_size = game_map.grid_size
        width, height = game_map.width, game_map.height

        # 初始化显示网格
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
            for door_idx in doors:
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

        # 实体 (不区分类型)
        self._mark_entities(display, game_state)

        # 玩家
        player = game_state.get_primary_player()
        if player:
            gx, gy = self.world_to_grid(player.position)
            if 0 <= gx < width and 0 <= gy < height:
                display[gy][gx] = self.PLAYER

        return self._build_output(display, game_state, player)

    def _mark_entities(self, display: List[List[str]], game_state: GameStateData):
        """标记所有实体"""
        for fh in game_state.fire_hazards.values():
            gx, gy = self.world_to_grid(fh.position)
            if 0 <= gx < len(display[0]) and 0 <= gy < len(display):
                display[gy][gx] = self.ENTITY

        for btn in game_state.buttons.values():
            gx, gy = self.world_to_grid(btn.position)
            if 0 <= gx < len(display[0]) and 0 <= gy < len(display):
                display[gy][gx] = self.ENTITY

        for dest in game_state.obstacles.values():
            gx, gy = self.world_to_grid(dest.position)
            if 0 <= gx < len(display[0]) and 0 <= gy < len(display):
                display[gy][gx] = self.ENTITY

        for ent in game_state.interactables.values():
            gx, gy = self.world_to_grid(ent.position)
            if 0 <= gx < len(display[0]) and 0 <= gy < len(display):
                display[gy][gx] = self.ENTITY

        for p in game_state.pickups.values():
            gx, gy = self.world_to_grid(p.position)
            if 0 <= gx < len(display[0]) and 0 <= gy < len(display):
                display[gy][gx] = self.ENTITY

    def _build_output(
        self, display: List[List[str]], game_state: GameStateData, player
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

        player_pos = player.position if player else None
        if player_pos:
            lines.append(
                f"Entities: {entity_count} | Player: ({player_pos.x:.0f},{player_pos.y:.0f})"
            )
        else:
            lines.append(f"Entities: {entity_count}")

        lines.append(
            f"Fire:{len(game_state.fire_hazards)} Buttons:{len(game_state.buttons)} "
            f"Destruct:{len(game_state.obstacles)} Inter:{len(game_state.interactables)} Pickup:{len(game_state.pickups)}"
        )
        lines.append("")
        lines.append("Legend: .path  #wall  Xvoid  Ddoor  Eentity  Pplayer")

        return "\n".join(lines)

    def display(self, game_state: GameStateData, game_map: GameMap, clear: bool = True):
        """清屏刷新显示"""
        if clear:
            self.clear_screen()
        print(self.render(game_state, game_map))

    def refresh(self, game_state: GameStateData, game_map: GameMap) -> str:
        """滚动刷新显示 - 返回完整的帧字符串供外部打印

        Returns:
            完整的帧字符串（包含所有行）
        """
        return self.render(game_state, game_map)


def build_game_map(game_state: GameStateData) -> Tuple[GameMap, GameStateData]:
    """从游戏状态构建地图"""
    room_info = game_state.room_info
    layout = game_state.raw_room_layout

    if room_info:
        grid_size = layout.get("grid_size", 40.0) if layout else 40.0
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

    return game_map, game_state


def run_replay_mode(
    session_id: Optional[str] = None,
    speed: float = 1.0,
    recordings_dir: str = "./recordings",
):
    """回放模式: 从录制数据回放并显示"""
    print("=" * 60)
    print("Room Visualizer - Replay Mode")
    print("=" * 60)

    # 创建组件 (使用正确的录制目录)
    recordings_path = Path(recordings_dir)

    # 检查是否有meta文件（直接在该目录下或子目录中）
    def has_meta_files(path):
        if not path.exists():
            return False
        direct = list(path.glob("*_meta.json"))
        subdir = list(path.glob("*/*_meta.json"))
        return len(direct) > 0 or len(subdir) > 0

    if not has_meta_files(recordings_path):
        # 尝试python子目录
        recordings_path = Path(__file__).parent / "recordings"
        if not has_meta_files(recordings_path):
            # 最终检查：如果还是找不到，尝试python/recordings
            recordings_path = Path(__file__).parent / "python" / "recordings"

    print(f"Recordings directory: {recordings_path}")

    replayer = create_replayer(str(recordings_path))
    processor = create_data_processor()
    visualizer = RoomVisualizer()

    # 列出会话
    sessions = replayer.list_sessions()
    if not sessions:
        print("No recorded sessions found!")
        print(f"Looking in: {recordings_path}")
        print("Record a session first with: python data_replay_examples.py record")
        return

    # 选择会话
    if session_id is None or session_id == "--latest" or session_id == "latest":
        session_id = sessions[0]["id"]
        print(f"Using latest session: {session_id}")
    else:
        print(f"Using session: {session_id}")

    # 显示会话信息
    for s in sessions:
        if s["id"] == session_id:
            print(f"  Duration: {s['duration']:.1f}s")
            print(f"  Frames: {s['frames']}")
            print(f"  Messages: {s['messages']}")
            break

    # 加载会话
    if not replayer.load_session(session_id or ""):
        print(f"Failed to load session: {session_id}")
        return

    print(f"\nLoaded {len(replayer.simulator.messages)} messages for playback")

    # 处理消息的回调
    current_game_state = None
    current_game_map = None

    def process_message(msg):
        nonlocal current_game_state, current_game_map
        try:
            raw_message = {
                "type": msg.msg_type,
                "frame": msg.frame,
                "room_index": msg.room_index,
                "payload": msg.payload,
                "channels": msg.channels,
                "timestamp": msg.timestamp,
            }
            current_game_state = processor.process_message(raw_message)
            if current_game_state:
                current_game_map, _ = build_game_map(current_game_state)
        except Exception as e:
            pass

    print("\nVisualizing... Press Ctrl+C to stop")
    print("-" * 60)

    # 直接遍历消息并处理（不通过网络）
    messages = replayer.simulator.messages
    total_messages = len(messages)
    last_timestamp = 0
    start_time = time.time()

    try:
        visualizer.clear_screen()

        for i, msg in enumerate(messages):
            # 处理消息
            if msg.msg_type == "DATA":
                process_message(msg)

            # 构建并显示输出
            if current_game_state and current_game_map:
                frame_output = visualizer.refresh(current_game_state, current_game_map)
                progress = (i + 1) / total_messages * 100
                progress_line = (
                    f"\nProgress: {progress:.1f}% | Messages: {i + 1}/{total_messages}"
                )
                print(f"\033[H\033[J{frame_output}{progress_line}", end="", flush=True)

            # 计算延迟（基于时间戳）
            if last_timestamp > 0 and speed > 0:
                timestamp_diff = (msg.timestamp - last_timestamp) / 1000.0
                delay = timestamp_diff / speed
                if delay > 0 and delay < 1.0:
                    time.sleep(delay)
            last_timestamp = msg.timestamp

    except KeyboardInterrupt:
        print("\nStopping...")

    print("\nReplay visualization complete!")


def run_live_mode():
    """实时模式: 连接游戏实时显示"""
    print("=" * 60)
    print("Room Visualizer - Live Mode")
    print("=" * 60)
    print("Waiting for game connection...")
    print("Make sure SocketBridge mod is running in-game")
    print("-" * 60)

    # 创建组件
    processor = create_data_processor()
    visualizer = RoomVisualizer()

    # IsaacBridge作为服务器等待游戏连接
    bridge = IsaacBridge()

    current_game_state = None
    current_game_map = None

    @bridge.on("connected")
    def on_connected(info):
        print(f"Game connected: {info['address']}")

    @bridge.on("disconnected")
    def on_disconnected(_):
        print("\nGame disconnected")
        nonlocal current_game_state
        current_game_state = None

    @bridge.on("message")
    def on_message(msg):
        nonlocal current_game_state, current_game_map
        try:
            raw_message = {
                "type": msg.msg_type,
                "frame": msg.frame,
                "room_index": msg.room_index,
                "payload": msg.payload,
                "channels": msg.channels,
                "timestamp": msg.timestamp,
            }
            current_game_state = processor.process_message(raw_message)
            if current_game_state:
                current_game_map, _ = build_game_map(current_game_state)
        except Exception as e:
            pass

    # 启动桥接器
    bridge.start()

    try:
        while True:
            if current_game_state and current_game_map:
                frame_output = visualizer.refresh(current_game_state, current_game_map)
                output = f"\033[H\033[J{frame_output}\n"
                print(output, end="", flush=True)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping...")
        bridge.stop()

    print("Live visualization stopped.")


def list_sessions():
    """列出所有录制会话"""
    replayer = create_replayer()
    sessions = replayer.list_sessions()

    print(f"Found {len(sessions)} sessions:")
    for s in sessions:
        print(f"  {s['id']}:")
        print(f"    Duration: {s['duration']:.1f}s")
        print(f"    Frames: {s['frames']}")
        print(f"    Messages: {s['messages']}")


def main():
    parser = argparse.ArgumentParser(
        description="SocketBridge Room Visualizer - Real-time ASCII room display",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all recorded sessions
  python realtime_visualizer.py list
  
  # Replay latest session
  python realtime_visualizer.py replay --latest
  
  # Replay specific session at 2x speed
  python realtime_visualizer.py replay session_xxx --speed 2.0
  
  # Live mode (wait for game connection)
  python realtime_visualizer.py live
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # List command
    list_parser = subparsers.add_parser("list", help="List recorded sessions")

    # Replay command
    replay_parser = subparsers.add_parser("replay", help="Replay recorded session")
    replay_parser.add_argument(
        "session_id", nargs="?", default=None, help="Session ID (default: latest)"
    )
    replay_parser.add_argument(
        "--speed", "-v", type=float, default=1.0, help="Playback speed (default: 1.0)"
    )
    replay_parser.add_argument(
        "--latest", action="store_true", help="Use latest session"
    )
    replay_parser.add_argument(
        "--dir",
        "-d",
        type=str,
        default=None,
        help="Recordings directory (default: python/recordings)",
    )

    # Live command
    live_parser = subparsers.add_parser(
        "live", help="Connect to game and visualize live"
    )

    args = parser.parse_args()

    if args.command == "list":
        list_sessions()
    elif args.command == "replay":
        session_id = args.session_id
        if args.latest:
            session_id = "--latest"
        recordings_dir = args.dir or "./recordings"
        run_replay_mode(session_id, args.speed, recordings_dir)
    elif args.command == "live":
        run_live_mode()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
