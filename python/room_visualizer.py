"""
SocketBridge 房间可视化工具

使用ASCII字符在控制台中实时显示房间布局。
显示障碍物、可破坏物、可交互实体、火堆等静态地图实体。
使用刷新方式显示，便于观察。

符号说明:
- .  空地（可行走）
- #  墙壁
- X  VOID区域（L型房间缺口）
- D  门
- E  实体（任何障碍物/可破坏物/可交互物/火堆等）
- P  玩家
"""

import os
import sys
import time
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum

# 尝试导入项目模块
try:
    from models import Vector2D, RoomInfo, GameStateData
    from environment import GameMap, TileType
except ImportError:
    # 如果作为独立脚本运行，添加项目路径
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from models import Vector2D, RoomInfo, GameStateData
    from environment import GameMap, TileType


class DisplayMode(Enum):
    """显示模式"""

    STATIC = "static"  # 静态显示（仅房间布局）
    DYNAMIC = "dynamic"  # 动态显示（包含玩家和敌人）


@dataclass
class VisualizerConfig:
    """可视化配置"""

    # 显示模式
    display_mode: DisplayMode = DisplayMode.DYNAMIC

    # 符号配置
    wall_symbol: str = "#"
    void_symbol: str = "X"
    floor_symbol: str = "."
    door_symbol: str = "D"
    entity_symbol: str = "E"
    fire_symbol: str = "F"
    player_symbol: str = "P"

    # 颜色配置（ANSI转义码）
    use_colors: bool = True
    color_wall: str = "\033[90m"  # 灰色
    color_void: str = "\033[95m"  # 浅紫
    color_floor: str = "\033[37m"  # 白色
    color_door: str = "\033[93m"  # 黄色
    color_entity: str = "\033[94m"  # 蓝色
    color_fire: str = "\033[91m"  # 红色
    color_player: str = "\033[92m"  # 绿色
    color_reset: str = "\033[0m"

    # 其他配置
    refresh_rate: float = 0.1  # 刷新率（秒）
    auto_clear: bool = True  # 自动清屏
    show_coords: bool = True  # 显示坐标
    show_legend: bool = True  # 显示图例


class RoomVisualizer:
    """房间ASCII可视化器"""

    def __init__(self, config: VisualizerConfig = None):
        """
        初始化可视化器

        Args:
            config: 可视化配置
        """
        self.config = config or VisualizerConfig()
        self.last_frame_str = ""
        self.grid_size = 40.0  # 默认网格大小
        self.top_left: Tuple[float, float] = (0.0, 0.0)  # top_left 偏移

    def world_to_grid(self, pos: Vector2D) -> Tuple[int, int]:
        """将世界坐标转换为网格坐标

        Args:
            pos: 世界坐标
            top_left: top_left 偏移，默认为 (0, 0)
        """
        gx = int((pos.x - self.top_left[0]) / self.grid_size)
        gy = int((pos.y - self.top_left[1]) / self.grid_size)
        return (gx, gy)

    def grid_to_world_center(self, gx: int, gy: int) -> Vector2D:
        """将网格坐标转换为该格子中心的像素坐标"""
        return Vector2D(
            x=gx * self.grid_size + self.grid_size / 2,
            y=gy * self.grid_size + self.grid_size / 2,
        )

    def _get_tile_symbol(self, tile_type: TileType) -> str:
        """获取瓦片类型的显示符号"""
        if tile_type == TileType.WALL:
            return self.config.wall_symbol
        elif tile_type == TileType.VOID:
            return self.config.void_symbol
        elif tile_type == TileType.DOOR:
            return self.config.door_symbol
        elif tile_type == TileType.HAZARD:
            return self.config.entity_symbol  # 危险区域显示为实体
        elif tile_type == TileType.SPECIAL:
            return self.config.entity_symbol  # 特殊区域显示为实体
        else:
            return self.config.floor_symbol

    def _get_color_for_symbol(self, symbol: str) -> str:
        """获取符号对应的颜色"""
        if not self.config.use_colors:
            return ""

        color_map = {
            self.config.wall_symbol: self.config.color_wall,
            self.config.void_symbol: self.config.color_void,
            self.config.floor_symbol: self.config.color_floor,
            self.config.door_symbol: self.config.color_door,
            self.config.entity_symbol: self.config.color_entity,
            self.config.fire_symbol: self.config.color_fire,
            self.config.player_symbol: self.config.color_player,
        }
        return color_map.get(symbol, "")

    def _clear_screen(self):
        """清屏"""
        if self.config.auto_clear:
            os.system("cls" if os.name == "nt" else "clear")

    def _get_door_positions(self, game_map: GameMap) -> Set[Tuple[int, int]]:
        """获取门的位置（网格坐标）"""
        door_positions = set()
        for door in game_map.doors:
            # 根据门的方向确定位置
            if door.direction == 0:  # 上
                gx, gy = game_map.width // 2, 0
            elif door.direction == 4:  # 下
                gx, gy = game_map.width // 2, game_map.height - 1
            elif door.direction == 2:  # 右
                gx, gy = game_map.width - 1, game_map.height // 2
            elif door.direction == 6:  # 左
                gx, gy = 0, game_map.height // 2
            else:
                # 对角线方向
                if door.direction == 1:  # 右上
                    gx, gy = game_map.width - 1, 0
                elif door.direction == 3:  # 右下
                    gx, gy = game_map.width - 1, game_map.height - 1
                elif door.direction == 5:  # 左下
                    gx, gy = 0, game_map.height - 1
                elif door.direction == 7:  # 左上
                    gx, gy = 0, 0
                else:
                    continue
            door_positions.add((gx, gy))
        return door_positions

    def render_game_map(
        self, game_map: GameMap, player_pos: Optional[Vector2D] = None
    ) -> str:
        """
        渲染游戏地图为ASCII字符串

        Args:
            game_map: 游戏地图
            player_pos: 玩家位置（可选）

        Returns:
            ASCII字符串表示
        """
        self.grid_size = game_map.grid_size
        self.top_left = game_map.top_left

        # 创建网格显示缓存
        display_grid: List[List[str]] = []
        color_grid: List[List[str]] = []  # 存储每个格子的颜色

        # 初始化网格
        for gy in range(game_map.height):
            row = []
            color_row = []
            for gx in range(game_map.width):
                tile_type = game_map.grid.get((gx, gy), TileType.EMPTY)
                symbol = self._get_tile_symbol(tile_type)
                color = self._get_color_for_symbol(symbol)
                row.append(symbol)
                color_row.append(color)
            display_grid.append(row)
            color_grid.append(color_row)

        # 标记门的位置
        door_positions = self._get_door_positions(game_map)
        for gx, gy in door_positions:
            if 0 <= gx < game_map.width and 0 <= gy < game_map.height:
                display_grid[gy][gx] = self.config.door_symbol
                color_grid[gy][gx] = self._get_color_for_symbol(self.config.door_symbol)

        # 标记静态实体（不区分类型，统一显示为E）
        for entities in game_map.entities.values():
            for entity in entities:
                if not entity.is_active:
                    continue

                gx, gy = self.world_to_grid(entity.position)
                if 0 <= gx < game_map.width and 0 <= gy < game_map.height:
                    display_grid[gy][gx] = self.config.entity_symbol
                    color_grid[gy][gx] = self._get_color_for_symbol(
                        self.config.entity_symbol
                    )

        # 标记玩家位置
        if player_pos:
            gx, gy = self.world_to_grid(player_pos)
            if 0 <= gx < game_map.width and 0 <= gy < game_map.height:
                display_grid[gy][gx] = self.config.player_symbol
                color_grid[gy][gx] = self._get_color_for_symbol(
                    self.config.player_symbol
                )

        # 构建输出字符串
        lines = []

        # 标题
        title = f"Room Visualization - Grid: {game_map.width}x{game_map.height}"
        lines.append(title)
        lines.append("=" * (game_map.width + 2))

        # 绘制网格
        for gy in range(game_map.height):
            line = ""
            for gx in range(game_map.width):
                symbol = display_grid[gy][gx]
                color = color_grid[gy][gx]
                if color and self.config.use_colors:
                    line += f"{color}{symbol}{self.config.color_reset}"
                else:
                    line += symbol
            lines.append("|" + line + "|")

        lines.append("=" * (game_map.width + 2))

        # 坐标信息
        if self.config.show_coords and player_pos:
            lines.append(f"Player: ({player_pos.x:.1f}, {player_pos.y:.1f})")

        # 图例
        if self.config.show_legend:
            lines.append("")
            lines.append("Legend:")
            lines.append(f"  {self.config.floor_symbol} = Walkable path")
            lines.append(f"  {self.config.wall_symbol} = Wall")
            if self.config.void_symbol in str(display_grid):
                lines.append(f"  {self.config.void_symbol} = VOID (L-shape room gap)")
            if self.config.door_symbol in str(display_grid):
                lines.append(f"  {self.config.door_symbol} = Door")
            lines.append(
                f"  {self.config.entity_symbol} = Entity (any obstacle/interactive)"
            )
            lines.append(f"  {self.config.player_symbol} = Player")

        return "\n".join(lines)

    def render_game_state(
        self, game_state: GameStateData, game_map: Optional[GameMap] = None
    ) -> str:
        """
        从GameStateData渲染房间

        Args:
            game_state: 游戏状态数据
            game_map: 游戏地图（如果为None则从game_state.room_layout获取）

        Returns:
            ASCII字符串表示
        """
        # 获取玩家位置
        player = game_state.get_primary_player()
        player_pos = player.position if player else None

        # 使用提供的game_map或从room_layout创建
        if game_map is None:
            # 创建临时地图
            room_info = game_state.room_info
            if room_info:
                layout = game_state.raw_room_layout
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
                # 默认13x7房间
                game_map = GameMap(grid_size=40.0, width=13, height=7)

        return self.render_game_map(game_map, player_pos)

    def display(
        self,
        game_state: GameStateData,
        game_map: Optional[GameMap] = None,
        clear_first: bool = True,
    ) -> str:
        """
        在控制台显示房间

        Args:
            game_state: 游戏状态数据
            game_map: 游戏地图（可选）
            clear_first: 是否先清屏

        Returns:
            渲染的字符串
        """
        frame_str = self.render_game_state(game_state, game_map)

        if clear_first:
            self._clear_screen()

        print(frame_str)
        self.last_frame_str = frame_str

        return frame_str

    def display_refresh(
        self, game_state: GameStateData, game_map: Optional[GameMap] = None
    ):
        """
        刷新方式显示房间（不清屏，使用换行）

        适合在循环中持续更新显示

        Args:
            game_state: 游戏状态数据
            game_map: 游戏地图（可选）
        """
        frame_str = self.render_game_state(game_state, game_map)

        # 打印多行，每行前加换行符覆盖旧内容
        lines = frame_str.split("\n")
        for line in lines:
            print("\r" + " " * 80 + "\r" + line, end="", flush=True)
        print()  # 最终换行

        self.last_frame_str = frame_str

    def animated_display(
        self,
        frames: List[Tuple[GameStateData, Optional[GameMap]]],
        interval: float = None,
    ):
        """
        动画方式显示多个帧

        Args:
            frames: 帧列表，每个元素为 (game_state, game_map)
            interval: 每帧间隔时间（秒）
        """
        if interval is None:
            interval = self.config.refresh_rate

        for i, (game_state, game_map) in enumerate(frames):
            self._clear_screen()
            print(f"Frame {i + 1}/{len(frames)}")
            self.display(game_state, game_map, clear_first=False)
            time.sleep(interval)

        print(f"\nAnimation complete: {len(frames)} frames")


def create_visualizer(config: VisualizerConfig = None) -> RoomVisualizer:
    """创建可视化器实例"""
    return RoomVisualizer(config)


# ============== 演示和测试代码 ==============


def demo():
    """演示可视化器"""
    from models import GameStateData, RoomInfo, PlayerData, EnemyData, ProjectileData
    from environment import GameMap

    # 创建可视化器
    config = VisualizerConfig()
    visualizer = create_visualizer(config)

    # 创建示例游戏状态
    game_state = GameStateData()
    game_state.frame = 100
    game_state.room_index = 42

    # 创建房间信息
    room_info = RoomInfo()
    room_info.room_index = 42
    room_info.grid_width = 13
    room_info.grid_height = 7
    room_info.room_shape = 0  # 普通房间
    game_state.room_info = room_info

    # 创建玩家
    player = PlayerData(player_idx=1)
    player.position = Vector2D(260, 300)  # 房间中心
    game_state.players[1] = player

    # 创建游戏地图
    game_map = GameMap(grid_size=40.0, width=13, height=7)

    print("Demo: Room Visualization")
    print("=" * 60)
    print()

    # 渲染并显示
    frame = visualizer.render_game_map(game_map, player.position)
    print(frame)

    print()
    print("Demo complete!")
    return game_state, game_map


def demo_with_entities():
    """演示带实体的房间可视化"""
    from models import GameStateData, RoomInfo, PlayerData
    from environment import GameMap, EntityType, RoomEntity

    config = VisualizerConfig()
    visualizer = create_visualizer(config)

    # 创建房间信息
    room_info = RoomInfo()
    room_info.room_index = 42
    room_info.grid_width = 13
    room_info.grid_height = 7
    room_info.room_shape = 0
    game_state = GameStateData()
    game_state.room_info = room_info

    # 创建玩家
    player = PlayerData(player_idx=1)
    player.position = Vector2D(260, 300)
    game_state.players[1] = player

    # 创建游戏地图
    game_map = GameMap(grid_size=40.0, width=13, height=7)

    # 添加一些实体（不区分类型，都显示为E）
    fire = RoomEntity(
        entity_type=EntityType.FIRE_HAZARD,
        entity_id=1,
        position=Vector2D(100, 100),
        variant_name="FIREPLACE",
    )
    game_map.entities[EntityType.FIRE_HAZARD].append(fire)

    rock = RoomEntity(
        entity_type=EntityType.DESTRUCTIBLE,
        entity_id=2,
        position=Vector2D(400, 100),
        variant_name="CRACKED_ROCK",
    )
    game_map.entities[EntityType.DESTRUCTIBLE].append(rock)

    slot = RoomEntity(
        entity_type=EntityType.INTERACTABLE,
        entity_id=3,
        position=Vector2D(100, 400),
        variant_name="SLOT_MACHINE",
    )
    game_map.entities[EntityType.INTERACTABLE].append(slot)

    print("Demo: Room with Entities")
    print("=" * 60)
    print()

    frame = visualizer.render_game_map(game_map, player.position)
    print(frame)


if __name__ == "__main__":
    print("SocketBridge Room Visualizer Demo")
    print("=" * 60)
    print()

    # 运行演示
    game_state, game_map = demo()

    print("\n" + "-" * 60 + "\n")

    demo_with_entities()

    print("\n" + "=" * 60)
    print("All demos completed!")
