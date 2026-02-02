"""
Room Layout Visualizer - 房间布局字符可视化

将 ROOM_LAYOUT 数据渲染为字符网格，方便与游戏画面对比：
- 显示所有网格实体的位置和类型
- 显示门的位置
- 显示玩家位置（实时模式）
- 支持实时更新或单帧快照

使用方法:
    python -m apps.room_layout_visualizer live       # 实时模式
    python -m apps.room_layout_visualizer snapshot   # 快照模式（进房间后截取一次）
"""

import sys
import os
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Set

# 确保路径正确
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

# 配置日志 - 减少噪音
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("room_visualizer")


# ============================================================
# 字符映射表 - 每种网格类型对应的显示字符
# ============================================================

GRID_TYPE_CHARS = {
    0: ' ',    # NULL - 空
    1: '.',    # DECORATION - 装饰物（可通行）
    2: '#',    # ROCK - 岩石
    3: '#',    # ROCK_BOMB - 可炸岩石
    4: '#',    # ROCK_ALT - 替代岩石
    5: 'T',    # ROCK_TINTED - 染色岩石（有奖励）
    6: '#',    # ROCK_ALT2 - 替代岩石2
    7: 'O',    # PIT - 坑洞
    8: '^',    # SPIKES - 尖刺
    9: '^',    # SPIKES_ON_OFF - 开关尖刺
    10: 'W',   # SPIDER_WEB - 蜘蛛网
    11: '#',   # LOCK - 锁
    12: '?',   # TNT - TNT
    13: 'F',   # FIREPLACE - 火堆
    14: '#',   # POOP - 便便
    15: '█',   # WALL - 墙壁
    16: '#',   # ROCK_SUPER_SPECIAL - 超级特殊岩石
    17: '#',   # ROCK_SPIKED - 尖刺岩石
    18: '#',   # ROCK_GOLD - 金岩石
    19: '?',   # ROCK_BOMB_SET - 已设置炸弹岩石
    20: 'P',   # PRESSURE_PLATE - 压力板
    21: 'S',   # STATUE - 雕像
    22: '#',   # ROCK_MARKED - 标记岩石
    23: 'C',   # CRAWLSPACE - 爬行空间
    24: 'G',   # GRAVITY - 重力
    25: '#',   # PILLAR - 柱子
    26: '?',   # TELEPORTER - 传送门
    27: '?',   # EVENT_RAIL - 事件轨道
}

# 碰撞类型
COLLISION_CHARS = {
    0: ' ',    # 无碰撞
    1: 'x',    # 有碰撞（用于未知类型）
}

# 门方向字符
DOOR_CHARS = {
    0: '◄',    # LEFT
    1: '▲',    # UP  
    2: '►',    # RIGHT
    3: '▼',    # DOWN
}

# 颜色控制码（可选，用于终端美化）
class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'


class RoomLayoutVisualizer:
    """房间布局可视化器"""
    
    def __init__(self):
        from core.connection import BridgeAdapter, AdapterConfig
        
        config = AdapterConfig(
            log_messages=False,
            validation_enabled=True,
            monitoring_enabled=False,
        )
        self.adapter = BridgeAdapter(config)
        
        # 当前房间数据
        self.current_room_info = None
        self.current_room_layout = None
        self.current_player_pos = None
        self.current_frame = 0
        
        # 标记是否已收到完整数据
        self.has_room_info = False
        self.has_room_layout = False
        
        # 上一次渲染的房间
        self.last_rendered_room_idx = None
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """设置消息处理器"""
        
        @self.adapter.on("connected")
        def on_connected(data):
            print(f"\n{'='*60}")
            print(f"游戏已连接: {data.get('address')}")
            print(f"等待进入房间...")
            print(f"{'='*60}\n")
        
        @self.adapter.on("disconnected")
        def on_disconnected(data):
            print(f"\n游戏已断开连接")
        
        @self.adapter.on("message")
        def on_message(msg: dict, processed):
            self._process_message(msg)
    
    def _process_message(self, msg: dict):
        """处理消息，更新当前数据"""
        payload = msg.get("payload", {})
        channels = msg.get("channels", [])
        self.current_frame = msg.get("frame", 0)
        
        # 更新玩家位置
        # PLAYER_POSITION 结构: {"1": {"pos": {...}, ...}, "2": {...}}
        if "PLAYER_POSITION" in channels:
            player_pos_data = payload.get("PLAYER_POSITION", {})
            # 可能是字典或列表
            if isinstance(player_pos_data, dict):
                # 获取玩家1的位置
                player1 = player_pos_data.get("1") or player_pos_data.get(1)
                if player1 and isinstance(player1, dict):
                    pos = player1.get("pos", {})
                    if isinstance(pos, dict):
                        self.current_player_pos = (pos.get("x", 0), pos.get("y", 0))
        
        # 更新房间信息
        if "ROOM_INFO" in channels:
            self.current_room_info = payload.get("ROOM_INFO")
            self.has_room_info = True
        
        # 更新房间布局
        if "ROOM_LAYOUT" in channels:
            self.current_room_layout = payload.get("ROOM_LAYOUT")
            self.has_room_layout = True
    
    def render_grid(self) -> str:
        """渲染当前房间为字符网格"""
        if not self.current_room_info or not self.current_room_layout:
            return "等待房间数据..."
        
        room_info = self.current_room_info
        layout = self.current_room_layout
        
        # 确保 room_info 是字典
        if not isinstance(room_info, dict):
            return f"房间信息类型错误: {type(room_info)}"
        if not isinstance(layout, dict):
            return f"房间布局类型错误: {type(layout)}"
        
        # 获取网格尺寸
        grid_width = room_info.get("grid_width", 15)
        grid_height = room_info.get("grid_height", 9)
        top_left = room_info.get("top_left", {})
        if isinstance(top_left, dict):
            tl_x = top_left.get("x", 0)
            tl_y = top_left.get("y", 0)
        else:
            tl_x, tl_y = 0, 0
        
        # *** 关键修正 ***
        # TopLeft 是可行走区域的左上角（即格子 (1,1) 的左上角）
        # 但网格数据包含边界墙（从格子 (0,0) 开始）
        # 所以需要将 TopLeft 向左上偏移一格（40像素）
        adjusted_tl_x = tl_x - 40
        adjusted_tl_y = tl_y - 40
        
        # 初始化网格 - 全部为空
        grid = [[' ' for _ in range(grid_width)] for _ in range(grid_height)]
        
        # 边框（仅作为后备，数据会覆盖）
        for x in range(grid_width):
            grid[0][x] = '─'
            grid[grid_height-1][x] = '─'
        for y in range(grid_height):
            grid[y][0] = '│'
            grid[y][grid_width-1] = '│'
        # 角落
        grid[0][0] = '┌'
        grid[0][grid_width-1] = '┐'
        grid[grid_height-1][0] = '└'
        grid[grid_height-1][grid_width-1] = '┘'
        
        # 解析网格实体
        grid_data = layout.get("grid", {})
        type_counts: Dict[int, int] = {}
        
        for idx_str, tile_data in grid_data.items():
            if not isinstance(tile_data, dict):
                continue
            
            tile_type = tile_data.get("type", 0)
            tile_x = tile_data.get("x", 0)
            tile_y = tile_data.get("y", 0)
            collision = tile_data.get("collision", 0)
            
            # 统计类型
            type_counts[tile_type] = type_counts.get(tile_type, 0) + 1
            
            # 转换为网格坐标（使用调整后的 TopLeft）
            gx = int((tile_x - adjusted_tl_x) / 40)
            gy = int((tile_y - adjusted_tl_y) / 40)
            
            # 边界检查
            if 0 <= gx < grid_width and 0 <= gy < grid_height:
                # 获取显示字符
                char = GRID_TYPE_CHARS.get(tile_type, '?')
                if tile_type not in GRID_TYPE_CHARS and collision > 0:
                    char = 'x'  # 未知但有碰撞
                grid[gy][gx] = char
        
        # 添加门
        doors_data = layout.get("doors", {})
        for door_idx, door_info in doors_data.items():
            if not isinstance(door_info, dict):
                continue
            
            door_x = door_info.get("x", 0)
            door_y = door_info.get("y", 0)
            is_open = door_info.get("is_open", False)
            
            # 使用调整后的 TopLeft
            gx = int((door_x - adjusted_tl_x) / 40)
            gy = int((door_y - adjusted_tl_y) / 40)
            
            if 0 <= gx < grid_width and 0 <= gy < grid_height:
                try:
                    dir_idx = int(door_idx)
                    char = DOOR_CHARS.get(dir_idx, 'D')
                except ValueError:
                    char = 'D'
                grid[gy][gx] = char if is_open else 'd'
        
        # 添加玩家位置
        if self.current_player_pos:
            px, py = self.current_player_pos
            # 使用调整后的 TopLeft
            pgx = int((px - adjusted_tl_x) / 40)
            pgy = int((py - adjusted_tl_y) / 40)
            if 1 <= pgx < grid_width - 1 and 1 <= pgy < grid_height - 1:
                grid[pgy][pgx] = '@'
        
        # 构建输出字符串
        lines = []
        
        # 标题
        room_idx = room_info.get("room_idx", "?")
        room_shape = room_info.get("room_shape", "?")
        room_type = room_info.get("room_type", "?")
        lines.append(f"Room #{room_idx} | Shape: {room_shape} | Type: {room_type} | Grid: {grid_width}x{grid_height} | Frame: {self.current_frame}")
        
        # 坐标系统信息
        bottom_right = room_info.get("bottom_right", {})
        if isinstance(bottom_right, dict):
            br_x = bottom_right.get("x", 0)
            br_y = bottom_right.get("y", 0)
        else:
            br_x, br_y = 0, 0
        
        lines.append(f"TopLeft: ({tl_x:.1f}, {tl_y:.1f}) | BottomRight: ({br_x:.1f}, {br_y:.1f})")
        lines.append(f"像素范围: {br_x - tl_x:.1f} x {br_y - tl_y:.1f} | 期望: {(grid_width-2)*40} x {(grid_height-2)*40}")
        lines.append("")
        
        # 列号标尺
        col_nums = "   " + "".join(f"{i % 10}" for i in range(grid_width))
        lines.append(col_nums)
        
        # 网格内容
        for y, row in enumerate(grid):
            row_str = f"{y:2d} " + "".join(row)
            lines.append(row_str)
        
        # 图例
        lines.append("")
        lines.append("图例: @ 玩家 | # 岩石/障碍 | █ 墙壁 | O 坑洞 | ^ 尖刺 | D/d 门(开/关)")
        lines.append(f"      T 染色岩石 | W 蜘蛛网 | P 压力板 | S 雕像 | . 装饰物")
        
        # 类型统计
        if type_counts:
            stats = ", ".join(f"T{t}:{c}" for t, c in sorted(type_counts.items()))
            lines.append(f"实体统计: {stats}")
            lines.append(f"总实体数: {sum(type_counts.values())}")
        
        # 诊断信息：显示边缘位置的实体
        lines.append("")
        lines.append("【边缘诊断】检查边缘位置的非墙壁实体:")
        edge_entities = []
        grid_data = layout.get("grid", {})
        for idx_str, tile_data in grid_data.items():
            if not isinstance(tile_data, dict):
                continue
            tile_type = tile_data.get("type", 0)
            if tile_type == 15:  # 跳过墙壁
                continue
            tile_x = tile_data.get("x", 0)
            tile_y = tile_data.get("y", 0)
            # 使用调整后的坐标转换
            gx = int((tile_x - adjusted_tl_x) / 40)
            gy = int((tile_y - adjusted_tl_y) / 40)
            # 检查边缘位置（第0-2行/列 或 最后2行/列）
            if gx <= 2 or gy <= 2 or gx >= grid_width - 2 or gy >= grid_height - 2:
                edge_entities.append({
                    "idx": idx_str,
                    "type": tile_type,
                    "world": (tile_x, tile_y),
                    "grid": (gx, gy),
                })
        
        for e in edge_entities[:15]:
            char = GRID_TYPE_CHARS.get(e["type"], "?")
            lines.append(f"  idx={e['idx']:>3} T{e['type']:>2}'{char}' | world=({e['world'][0]:>7.1f}, {e['world'][1]:>7.1f}) | grid=({e['grid'][0]:>2}, {e['grid'][1]:>2})")
        
        if len(edge_entities) > 15:
            lines.append(f"  ... 还有 {len(edge_entities) - 15} 个边缘实体")
        
        return "\n".join(lines)
    
    def render_detailed_list(self) -> str:
        """渲染详细的实体列表（用于调试）"""
        if not self.current_room_layout:
            return "无布局数据"
        
        layout = self.current_room_layout
        room_info = self.current_room_info or {}
        
        # 类型检查
        if not isinstance(layout, dict):
            return f"布局数据类型错误: {type(layout)}"
        if not isinstance(room_info, dict):
            room_info = {}
        
        top_left = room_info.get("top_left", {})
        if isinstance(top_left, dict):
            tl_x = top_left.get("x", 0)
            tl_y = top_left.get("y", 0)
        else:
            tl_x, tl_y = 0, 0
        
        # 调整 TopLeft 以包含边界墙
        adjusted_tl_x = tl_x - 40
        adjusted_tl_y = tl_y - 40
        
        lines = []
        lines.append("=" * 60)
        lines.append("详细实体列表")
        lines.append("=" * 60)
        
        grid_data = layout.get("grid", {})
        
        # 按类型分组
        by_type: Dict[int, List] = {}
        for idx_str, tile_data in grid_data.items():
            if not isinstance(tile_data, dict):
                continue
            tile_type = tile_data.get("type", 0)
            if tile_type not in by_type:
                by_type[tile_type] = []
            
            tile_x = tile_data.get("x", 0)
            tile_y = tile_data.get("y", 0)
            # 使用调整后的坐标转换
            gx = int((tile_x - adjusted_tl_x) / 40)
            gy = int((tile_y - adjusted_tl_y) / 40)
            
            by_type[tile_type].append({
                "idx": idx_str,
                "world": (tile_x, tile_y),
                "grid": (gx, gy),
                "collision": tile_data.get("collision", 0),
            })
        
        for tile_type in sorted(by_type.keys()):
            tiles = by_type[tile_type]
            type_name = f"Type {tile_type}"
            char = GRID_TYPE_CHARS.get(tile_type, "?")
            lines.append(f"\n[{type_name}] '{char}' - {len(tiles)} 个:")
            for t in tiles[:20]:  # 最多显示20个
                lines.append(f"  idx={t['idx']:>3} | world=({t['world'][0]:>6.1f}, {t['world'][1]:>6.1f}) | grid=({t['grid'][0]:>2}, {t['grid'][1]:>2}) | collision={t['collision']}")
            if len(tiles) > 20:
                lines.append(f"  ... 还有 {len(tiles) - 20} 个")
        
        # 门信息
        doors_data = layout.get("doors", {})
        if doors_data:
            lines.append(f"\n[门] {len(doors_data)} 个:")
            for door_idx, door_info in doors_data.items():
                if isinstance(door_info, dict):
                    dx = door_info.get("x", 0)
                    dy = door_info.get("y", 0)
                    # 使用调整后的坐标转换
                    gx = int((dx - adjusted_tl_x) / 40)
                    gy = int((dy - adjusted_tl_y) / 40)
                    target = door_info.get("target_room", -1)
                    is_open = door_info.get("is_open", False)
                    lines.append(f"  dir={door_idx} | world=({dx:>6.1f}, {dy:>6.1f}) | grid=({gx:>2}, {gy:>2}) | target={target} | open={is_open}")
        
        return "\n".join(lines)
    
    def start(self):
        """启动适配器"""
        self.adapter.start()
    
    def stop(self):
        """停止适配器"""
        self.adapter.stop()
    
    def has_complete_data(self) -> bool:
        """检查是否有完整数据"""
        return self.has_room_info and self.has_room_layout


def clear_screen():
    """清屏"""
    os.system('cls' if os.name == 'nt' else 'clear')


def run_live_mode():
    """实时模式 - 持续更新显示"""
    print("=" * 60)
    print("房间布局可视化 - 实时模式")
    print("=" * 60)
    print("连接游戏后将持续显示房间布局")
    print("按 Ctrl+C 退出")
    print("=" * 60)
    
    viz = RoomLayoutVisualizer()
    
    try:
        viz.start()
        
        last_room_idx = None
        
        while True:
            time.sleep(0.5)
            
            if viz.has_complete_data():
                # 检测房间变化
                current_room_idx = viz.current_room_info.get("room_idx") if viz.current_room_info else None
                
                if current_room_idx != last_room_idx:
                    # 房间变化，重新渲染
                    clear_screen()
                    print(viz.render_grid())
                    print()
                    last_room_idx = current_room_idx
                else:
                    # 同一房间，更新玩家位置
                    # 移动光标到开头重绘（简化处理：重绘全部）
                    clear_screen()
                    print(viz.render_grid())
    
    except KeyboardInterrupt:
        print("\n\n收到退出信号...")
    finally:
        viz.stop()


def run_snapshot_mode():
    """快照模式 - 进入房间后截取一次完整数据"""
    print("=" * 60)
    print("房间布局可视化 - 快照模式")
    print("=" * 60)
    print("等待进入房间后截取布局...")
    print("按 Ctrl+C 退出")
    print("=" * 60)
    
    viz = RoomLayoutVisualizer()
    
    try:
        viz.start()
        
        # 等待数据
        print("\n等待游戏连接和房间数据", end="", flush=True)
        while not viz.has_complete_data():
            print(".", end="", flush=True)
            time.sleep(0.5)
        
        # 再等一下确保数据完整
        time.sleep(0.5)
        
        print("\n\n")
        print(viz.render_grid())
        print()
        print(viz.render_detailed_list())
        
        print("\n按 Enter 继续监控下一个房间，或 Ctrl+C 退出...")
        
        last_room_idx = viz.current_room_info.get("room_idx") if viz.current_room_info else None
        
        while True:
            input()  # 等待用户按 Enter
            
            # 等待房间变化
            print("等待进入新房间", end="", flush=True)
            while True:
                current_room_idx = viz.current_room_info.get("room_idx") if viz.current_room_info else None
                if current_room_idx != last_room_idx:
                    break
                print(".", end="", flush=True)
                time.sleep(0.5)
            
            time.sleep(0.3)
            
            print("\n\n")
            print(viz.render_grid())
            print()
            print(viz.render_detailed_list())
            
            last_room_idx = current_room_idx
            print("\n按 Enter 继续监控下一个房间，或 Ctrl+C 退出...")
    
    except KeyboardInterrupt:
        print("\n\n收到退出信号...")
    finally:
        viz.stop()


def run_compare_mode():
    """对比模式 - 显示网格和详细列表，方便与游戏画面对比"""
    print("=" * 60)
    print("房间布局可视化 - 对比模式")
    print("=" * 60)
    print("显示网格图 + 详细实体列表")
    print("按 Ctrl+C 退出")
    print("=" * 60)
    
    viz = RoomLayoutVisualizer()
    
    try:
        viz.start()
        
        print("\n等待数据", end="", flush=True)
        while not viz.has_complete_data():
            print(".", end="", flush=True)
            time.sleep(0.5)
        
        time.sleep(0.3)
        
        while True:
            clear_screen()
            print(viz.render_grid())
            print()
            
            # 简化的实体统计
            if viz.current_room_layout:
                grid_data = viz.current_room_layout.get("grid", {})
                doors_data = viz.current_room_layout.get("doors", {})
                print(f"Grid 实体总数: {len(grid_data)} | 门数: {len(doors_data)}")
                
                # 显示门的详细信息
                if doors_data:
                    print("门详情:")
                    room_info = viz.current_room_info or {}
                    top_left = room_info.get("top_left", {})
                    tl_x = top_left.get("x", 0) if isinstance(top_left, dict) else 0
                    tl_y = top_left.get("y", 0) if isinstance(top_left, dict) else 0
                    adjusted_tl_x = tl_x - 40
                    adjusted_tl_y = tl_y - 40
                    
                    for door_idx, door_info in doors_data.items():
                        if isinstance(door_info, dict):
                            dx = door_info.get("x", 0)
                            dy = door_info.get("y", 0)
                            gx = int((dx - adjusted_tl_x) / 40)
                            gy = int((dy - adjusted_tl_y) / 40)
                            target = door_info.get("target_room", -1)
                            is_open = door_info.get("is_open", False)
                            print(f"  dir={door_idx} grid=({gx},{gy}) target={target} open={is_open}")
            
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\n收到退出信号...")
        # 退出前打印详细信息
        print(viz.render_detailed_list())
    finally:
        viz.stop()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="房间布局字符可视化 - 对比游戏画面验证数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m apps.room_layout_visualizer live       # 实时更新
  python -m apps.room_layout_visualizer snapshot   # 快照模式
  python -m apps.room_layout_visualizer compare    # 对比模式
        """
    )
    
    parser.add_argument(
        "mode",
        choices=["live", "snapshot", "compare"],
        nargs="?",
        default="live",
        help="运行模式: live=实时更新, snapshot=快照, compare=对比模式"
    )
    
    args = parser.parse_args()
    
    if args.mode == "live":
        run_live_mode()
    elif args.mode == "snapshot":
        run_snapshot_mode()
    elif args.mode == "compare":
        run_compare_mode()


if __name__ == "__main__":
    main()
