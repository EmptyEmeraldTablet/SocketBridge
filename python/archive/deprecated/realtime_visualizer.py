"""
SocketBridge 房间坐标输出工具

功能:
1. 计算并输出当前房间内各类实体的网格坐标
2. 支持回放模式和实时模式
3. 保持输出刷新，便于使用

实体类型:
- fire_hazards: 火焰危险物
- buttons: 按钮
- obstacles: 可破坏物/障碍物
- interactables: 可交互实体
- pickups: 拾取物
- enemies: 敌人
- projectiles: 投射物
- player: 玩家

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
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# 配置日志级别，确保DEBUG信息能输出
logging.basicConfig(
    level=logging.DEBUG, format="%(name)s - %(levelname)s - %(message)s"
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Vector2D, RoomInfo, GameStateData
from environment import GameMap, TileType
from data_processor import create_data_processor
from isaac_bridge import IsaacBridge, GameDataAccessor
from data_replay_system import SessionReplayer, create_replayer

logger = logging.getLogger("RealtimeVisualizer")


class RoomCoordinatePrinter:
    """房间坐标输出器 - 计算并输出实体的网格坐标"""

    def __init__(self):
        self.grid_size = 40.0

        # 房间边界偏移（来自 room_info.top_left）
        self.top_left_x = 0.0
        self.top_left_y = 0.0

    def world_to_grid(self, pos: Vector2D) -> Tuple[int, int]:
        """世界坐标转网格坐标

        基于 ROOM_GEOMETRY_BY_SESSION.md 的坐标系统：
        - top_left 是墙壁内边界左上角坐标（可移动区域左上角）
        - 房间整体世界坐标 = (top_left_x - 40, top_left_y - 40)

        对于任意点 (x, y)，对应的格点坐标：
        adjusted_top_left = top_left - 40  # 偏移以包含边界墙
        gx = floor((x - adjusted_top_left_x) / 40)
        gy = floor((y - adjusted_top_left_y) / 40)

        验证：玩家靠近左上角时，中心坐标约为 (75, 155)，top_left = (60, 140)
        adjusted = (20, 100)
        gx = floor((75 - 20) / 40) = 1
        gy = floor((155 - 100) / 40) = 1
        结果：(1, 1) ✅

        房间范围：
        - 15×9 房间: gx ∈ [0, 14], gy ∈ [0, 8]
        - 可移动区域: gx ∈ [1, 13], gy ∈ [1, 7]
        """
        # 调整 top_left 以包含边界墙
        adjusted_tl_x = self.top_left_x - self.grid_size
        adjusted_tl_y = self.top_left_y - self.grid_size
        grid_x = int((pos.x - adjusted_tl_x) / self.grid_size)
        grid_y = int((pos.y - adjusted_tl_y) / self.grid_size)
        return (grid_x, grid_y)

    def set_top_left(self, top_left: Tuple[float, float]):
        """设置 top_left 偏移"""
        self.top_left_x = top_left[0]
        self.top_left_y = top_left[1]

    def get_coordinates(
        self, game_state: GameStateData, game_map: GameMap
    ) -> Dict[str, List[Tuple[int, int]]]:
        """获取所有实体的网格坐标

        Returns:
            按类型分组的坐标字典
        """
        self.grid_size = game_map.grid_size
        # 从 game_map 获取 top_left
        self.set_top_left(game_map.top_left)

        coords = {
            "fire_hazards": [],
            "buttons": [],
            "obstacles": [],
            "interactables": [],
            "pickups": [],
            "enemies": [],
            "projectiles": [],
            "player": [],
        }

        # 玩家
        player = game_state.get_primary_player()
        if player:
            gx, gy = self.world_to_grid(player.position)
            coords["player"].append((gx, gy))

        # 敌人
        for enemy_id, enemy in game_state.enemies.items():
            if enemy.state.value == "active":
                gx, gy = self.world_to_grid(enemy.position)
                coords["enemies"].append((gx, gy))

        # 投射物
        for proj_id, proj in game_state.projectiles.items():
            gx, gy = self.world_to_grid(proj.position)
            coords["projectiles"].append((gx, gy))

        # 拾取物
        for pickup_id, pickup in game_state.pickups.items():
            gx, gy = self.world_to_grid(pickup.position)
            coords["pickups"].append((gx, gy))

        # 障碍物 - 从 game_map.static_obstacles 获取
        # static_obstacles 包含所有 WALL 类型的障碍物（包括边界墙）
        # 但边界墙不需要在可视化中显示（默认存在，不影响游戏逻辑）
        obstacle_coords = set()
        if hasattr(game_map, "static_obstacles"):
            # DEBUG: Log raw static_obstacles
            if logger.isEnabledFor(logging.DEBUG):
                raw_obstacles = sorted(game_map.static_obstacles)
                logger.debug(
                    f"[Visualizer] Raw static_obstacles ({len(raw_obstacles)}): {raw_obstacles[:10]}..."
                )

            for gx, gy in game_map.static_obstacles:
                # 排除边界墙 (gx=0 或 gx=width-1 或 gy=0 或 gy=height-1)
                if 0 < gx < game_map.width - 1 and 0 < gy < game_map.height - 1:
                    obstacle_coords.add((gx, gy))
        coords["obstacles"] = list(obstacle_coords)

        # 按钮 - 从 ROOM_LAYOUT.grid 获取 (type=20: PRESSURE_PLATE)
        buttons_coords = set()
        raw_layout = game_state.raw_room_layout
        # DEBUG: Log raw_layout
        if logger.isEnabledFor(logging.DEBUG) and raw_layout:
            grid = raw_layout.get("grid", {})
            if isinstance(grid, dict):
                tile_types = {}
                for k, v in grid.items():
                    if isinstance(v, dict):
                        t = v.get("type", "unknown")
                        tile_types[t] = tile_types.get(t, 0) + 1
                logger.debug(f"[Visualizer] ROOM_LAYOUT.grid tile types: {tile_types}")
                logger.debug(
                    f"[Visualizer] ROOM_LAYOUT.grid sample: {list(grid.items())[:5]}"
                )
        if raw_layout and "grid" in raw_layout:
            for idx_str, tile_data in raw_layout["grid"].items():
                if tile_data.get("type") == 20:  # PRESSURE_PLATE
                    tile_x = tile_data.get("x", 0)
                    tile_y = tile_data.get("y", 0)
                    # 按钮是世界坐标，需要减去 top_left 偏移后再除以 grid_size
                    gx = int((tile_x - self.top_left_x) / game_map.grid_size)
                    gy = int((tile_y - self.top_left_y) / game_map.grid_size)
                    buttons_coords.add((gx, gy))
        coords["buttons"] = list(buttons_coords)

        # 火焰危险物
        for fire_id, fire in game_state.fire_hazards.items():
            gx, gy = self.world_to_grid(fire.position)
            coords["fire_hazards"].append((gx, gy))

        # 可交互实体
        for ent_id, ent in game_state.interactables.items():
            gx, gy = self.world_to_grid(ent.position)
            coords["interactables"].append((gx, gy))

        return coords

    def format_output(
        self, game_state: GameStateData, coords: Dict[str, List[Tuple[int, int]]]
    ) -> str:
        """简化坐标输出"""
        lines = []

        frame = game_state.frame or 0
        room_idx = game_state.room_index or -1
        lines.append(f"[Frame:{frame:06d} Room:{room_idx:03d}]")

        # 按类型输出坐标（只显示非空类型）
        type_names = {
            "player": "Player",
            "enemies": "Enemies",
            "projectiles": "Projectiles",
            "fire_hazards": "Fire",
            "buttons": "Buttons",
            "obstacles": "Obstacles",
            "interactables": "Interactables",
            "pickups": "Pickups",
        }

        total_count = 0
        for entity_type, type_name in type_names.items():
            positions = coords.get(entity_type, [])
            if positions:
                unique_positions = sorted(set(positions))
                count = len(unique_positions)
                total_count += count
                pos_strs = [f"({gx},{gy})" for gx, gy in unique_positions]
                lines.append(f"{type_name} [{count}]: {', '.join(pos_strs)}")

        lines.append(f"Total: {total_count}")

        return "\n".join(lines)

    def print(self, game_state: GameStateData, game_map: GameMap, clear: bool = True):
        """打印坐标（清屏刷新）"""
        if clear:
            os.system("cls" if os.name == "nt" else "clear")

        coords = self.get_coordinates(game_state, game_map)
        output = self.format_output(game_state, coords)
        print(output)

    def refresh(self, game_state: GameStateData, game_map: GameMap) -> str:
        """刷新输出 - 返回完整的输出字符串

        Returns:
            完整的输出字符串（包含所有行）
        """
        coords = self.get_coordinates(game_state, game_map)
        return self.format_output(game_state, coords)


def build_game_map(game_state: GameStateData) -> Tuple[GameMap, GameStateData]:
    """从游戏状态构建地图

    关键：raw_room_layout 可能包含旧房间的数据（当消息不包含 ROOM_LAYOUT 时）
    需要检测房间变化并清除旧数据
    """
    room_info = game_state.room_info
    layout = game_state.raw_room_layout

    if room_info:
        grid_size = 40.0
        game_map = GameMap(
            grid_size=grid_size,
            width=room_info.grid_width,
            height=room_info.grid_height,
        )

        # 检测房间变化：当前消息是否有 ROOM_LAYOUT？
        # 如果当前消息不包含 ROOM_LAYOUT，说明 layout 可能来自之前的房间
        # 需要验证 layout 是否有效（属于当前房间）
        has_current_layout = False
        if layout:
            # 检查当前消息是否包含 ROOM_LAYOUT
            # 可以通过检查 layout 的完整性来判断
            if isinstance(layout, dict):
                has_required_fields = (
                    ("grid" in layout or "doors" in layout)
                    and "width" in layout
                    and "height" in layout
                )
                if has_required_fields:
                    # 有完整的 layout 数据，尝试判断是否属于当前房间
                    # 如果 layout 有房间标识，验证它
                    layout_room = layout.get("room_index")
                    if layout_room is not None:
                        # Mod 发送了 room_index，验证匹配
                        has_current_layout = layout_room == room_info.room_index
                    else:
                        # Mod 没有发送 room_index，保守处理：
                        # 只有当 layout 的尺寸与当前房间匹配时才使用
                        layout_width = layout.get("width", 0)
                        layout_height = layout.get("height", 0)
                        has_current_layout = (
                            layout_width == room_info.grid_width
                            and layout_height == room_info.grid_height
                        )

        if layout and has_current_layout:
            game_map.update_from_room_layout(room_info, layout, grid_size)
        else:
            # Layout 无效或不属于当前房间，使用简化的房间信息
            game_map.update_from_room_info(room_info)
    else:
        game_map = GameMap(grid_size=40.0, width=13, height=7)

    return game_map, game_state


def run_replay_mode(
    session_id: Optional[str] = None,
    speed: float = 1.0,
    recordings_dir: str = "./recordings",
):
    """回放模式: 从录制数据回放并输出坐标"""
    print("=" * 60)
    print("Room Coordinate Printer - Replay Mode")
    print("=" * 60)

    # 创建组件
    recordings_path = Path(recordings_dir)

    def has_meta_files(path):
        if not path.exists():
            return False
        direct = list(path.glob("*_meta.json"))
        subdir = list(path.glob("*/*_meta.json"))
        return len(direct) > 0 or len(subdir) > 0

    if not has_meta_files(recordings_path):
        recordings_path = Path(__file__).parent / "recordings"
        if not has_meta_files(recordings_path):
            recordings_path = Path(__file__).parent / "python" / "recordings"

    print(f"Recordings directory: {recordings_path}")

    replayer = create_replayer(str(recordings_path))
    processor = create_data_processor()
    printer = RoomCoordinatePrinter()

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
            logger.debug(f"[Visualizer] Received channels: {msg.channels}")
            logger.debug(
                f"[Visualizer] Payload keys: {list(msg.payload.keys()) if isinstance(msg.payload, dict) else 'N/A'}"
            )
            current_game_state = processor.process_message(raw_message)
            if current_game_state:
                logger.debug(
                    f"[Visualizer] After processing - projectiles: {len(current_game_state.projectiles)}, bombs: {len(current_game_state.bombs)}, obstacles: {len(current_game_state.obstacles)}"
                )
                current_game_map, _ = build_game_map(current_game_state)
        except Exception as e:
            logger.error(f"[Visualizer] Error processing message: {e}")

    print("\nPrinting coordinates... Press Ctrl+C to stop")
    print("-" * 60)

    # 直接遍历消息并处理
    messages = replayer.simulator.messages
    total_messages = len(messages)
    last_timestamp = 0
    start_time = time.time()

    try:
        for i, msg in enumerate(messages):
            # 处理消息
            if msg.msg_type == "DATA":
                process_message(msg)

            # 构建并显示输出
            if current_game_state and current_game_map:
                frame_output = printer.refresh(current_game_state, current_game_map)
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

    print("\nReplay complete!")


def run_live_mode():
    """实时模式: 连接游戏实时输出坐标"""
    print("=" * 60)
    print("Room Coordinate Printer - Live Mode")
    print("=" * 60)
    print("Waiting for game connection...")
    print("Make sure SocketBridge mod is running in-game")
    print("-" * 60)

    # 创建组件
    processor = create_data_processor()
    printer = RoomCoordinatePrinter()

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
            logger.debug(f"[Visualizer] Received channels: {msg.channels}")
            logger.debug(
                f"[Visualizer] Payload keys: {list(msg.payload.keys()) if isinstance(msg.payload, dict) else 'N/A'}"
            )
            current_game_state = processor.process_message(raw_message)
            if current_game_state:
                logger.debug(
                    f"[Visualizer] After processing - projectiles: {len(current_game_state.projectiles)}, bombs: {len(current_game_state.bombs)}, obstacles: {len(current_game_state.obstacles)}"
                )
                current_game_map, _ = build_game_map(current_game_state)
        except Exception as e:
            logger.error(f"[Visualizer] Error processing message: {e}")

    # 启动桥接器
    bridge.start()

    try:
        while True:
            if current_game_state and current_game_map:
                frame_output = printer.refresh(current_game_state, current_game_map)
                output = f"\033[H\033[J{frame_output}\n"
                print(output, end="", flush=True)
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping...")
        bridge.stop()

    print("Live mode stopped.")


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
        description="SocketBridge Room Coordinate Printer - Calculate and output entity grid coordinates",
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
        "live", help="Connect to game and print coordinates live"
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
