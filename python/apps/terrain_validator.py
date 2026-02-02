"""
Terrain Validator - 地形数据验证工具

专门用于验证游戏地形数据的正确性，帮助区分：
- Lua 端数据发送问题
- Python 端数据处理问题

使用新架构（BridgeAdapter + SocketBridgeFacade）

使用方法:
    python -m apps.terrain_validator live       # 实时模式
    python -m apps.terrain_validator dump       # 打印原始数据
"""

import sys
import os
import time
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

# 确保路径正确
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("terrain_validator")


class TerrainValidator:
    """地形数据验证器
    
    验证流程：
    1. 接收原始 Lua 数据
    2. 通过新架构处理
    3. 对比验证结果
    """
    
    def __init__(self):
        from core.connection import BridgeAdapter, AdapterConfig
        
        config = AdapterConfig(
            log_messages=False,
            validation_enabled=True,
            monitoring_enabled=True,
        )
        self.adapter = BridgeAdapter(config)
        
        # 存储最后的原始数据用于对比
        self.last_raw_room_info = None
        self.last_raw_room_layout = None
        self.last_parsed_room_info = None
        self.last_raw_msg = None
        
        # 统计
        self.room_info_count = 0
        self.room_layout_count = 0
        self.parse_errors = []
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """设置消息处理器"""
        
        @self.adapter.on("connected")
        def on_connected(data):
            print(f"\n[CONNECTED] 游戏已连接: {data.get('address')}")
            print("开始监控地形数据...\n")
        
        @self.adapter.on("disconnected")
        def on_disconnected(data):
            print(f"\n[DISCONNECTED] 游戏已断开")
            self._print_summary()
        
        @self.adapter.on("message")
        def on_message(msg: dict, processed):
            self._process_raw_message(msg)
    
    def _process_raw_message(self, msg: dict):
        """处理原始消息，提取地形数据"""
        self.last_raw_msg = msg
        payload = msg.get("payload", {})
        channels = msg.get("channels", [])
        frame = msg.get("frame", 0)
        
        # 检查 ROOM_INFO
        if "ROOM_INFO" in channels:
            raw_room_info = payload.get("ROOM_INFO")
            if raw_room_info:
                self.last_raw_room_info = raw_room_info
                self.room_info_count += 1
                self._validate_room_info(raw_room_info, frame)
        
        # 检查 ROOM_LAYOUT
        if "ROOM_LAYOUT" in channels:
            raw_room_layout = payload.get("ROOM_LAYOUT")
            if raw_room_layout:
                self.last_raw_room_layout = raw_room_layout
                self.room_layout_count += 1
                self._validate_room_layout(raw_room_layout, frame)
    
    def _validate_room_info(self, raw: dict, frame: int):
        """验证 ROOM_INFO 数据"""
        # 必需字段检查
        required_fields = [
            "room_type", "room_shape", "room_idx", "stage",
            "grid_width", "grid_height", "top_left", "bottom_right"
        ]
        
        missing = [f for f in required_fields if f not in raw]
        if missing:
            error = f"Frame {frame}: ROOM_INFO 缺少字段: {missing}"
            self.parse_errors.append(error)
            logger.warning(error)
            return
        
        # 值范围检查
        issues = []
        
        room_idx = raw.get("room_idx")
        if room_idx is None:
            issues.append("room_idx 为 None")
        
        grid_width = raw.get("grid_width", 0)
        grid_height = raw.get("grid_height", 0)
        if grid_width <= 0 or grid_height <= 0:
            issues.append(f"无效网格尺寸: {grid_width}x{grid_height}")
        
        top_left = raw.get("top_left", {})
        bottom_right = raw.get("bottom_right", {})
        
        tl_x = top_left.get("x", 0) if isinstance(top_left, dict) else 0
        tl_y = top_left.get("y", 0) if isinstance(top_left, dict) else 0
        br_x = bottom_right.get("x", 0) if isinstance(bottom_right, dict) else 0
        br_y = bottom_right.get("y", 0) if isinstance(bottom_right, dict) else 0
        
        # 验证坐标一致性
        expected_pixel_width = (grid_width - 2) * 40
        expected_pixel_height = (grid_height - 2) * 40
        actual_pixel_width = br_x - tl_x
        actual_pixel_height = br_y - tl_y
        
        if abs(actual_pixel_width - expected_pixel_width) > 1:
            issues.append(f"像素宽度不匹配: 期望 {expected_pixel_width}, 实际 {actual_pixel_width}")
        
        if abs(actual_pixel_height - expected_pixel_height) > 1:
            issues.append(f"像素高度不匹配: 期望 {expected_pixel_height}, 实际 {actual_pixel_height}")
        
        if issues:
            for issue in issues:
                error = f"Frame {frame}: ROOM_INFO 问题 - {issue}"
                self.parse_errors.append(error)
                logger.warning(error)
        
        # 尝试使用新架构解析
        try:
            from core.protocol.schema import RoomInfoData
            parsed = RoomInfoData(**raw)
            self.last_parsed_room_info = parsed
        except Exception as e:
            error = f"Frame {frame}: ROOM_INFO 解析失败 - {e}"
            self.parse_errors.append(error)
            logger.error(error)
    
    def _validate_room_layout(self, raw: dict, frame: int):
        """验证 ROOM_LAYOUT 数据"""
        # 字段检查
        grid = raw.get("grid", {})
        doors = raw.get("doors", {})
        width = raw.get("width", 0)
        height = raw.get("height", 0)
        
        issues = []
        
        if not isinstance(grid, dict):
            issues.append(f"grid 类型错误: {type(grid)}")
        
        if not isinstance(doors, dict):
            issues.append(f"doors 类型错误: {type(doors)}")
        
        # 验证 grid 数据
        tile_types = {}
        invalid_tiles = []
        
        for idx_str, tile_data in grid.items():
            if not isinstance(tile_data, dict):
                invalid_tiles.append(idx_str)
                continue
            
            tile_type = tile_data.get("type", -1)
            tile_types[tile_type] = tile_types.get(tile_type, 0) + 1
            
            # 检查必需字段
            if "x" not in tile_data or "y" not in tile_data:
                issues.append(f"Tile {idx_str} 缺少坐标")
        
        if invalid_tiles:
            issues.append(f"{len(invalid_tiles)} 个无效 tile 数据")
        
        # 验证 doors 数据
        for door_key, door_data in doors.items():
            if not isinstance(door_data, dict):
                issues.append(f"Door {door_key} 数据无效")
                continue
            
            required = ["x", "y", "target_room"]
            missing = [f for f in required if f not in door_data]
            if missing:
                issues.append(f"Door {door_key} 缺少字段: {missing}")
        
        if issues:
            for issue in issues:
                error = f"Frame {frame}: ROOM_LAYOUT 问题 - {issue}"
                self.parse_errors.append(error)
                logger.warning(error)
        
        # 输出统计
        if tile_types:
            logger.info(f"Frame {frame}: ROOM_LAYOUT grid 类型分布: {tile_types}")
    
    def _print_summary(self):
        """打印验证总结"""
        print("\n" + "=" * 60)
        print("地形数据验证总结")
        print("=" * 60)
        print(f"ROOM_INFO 消息数: {self.room_info_count}")
        print(f"ROOM_LAYOUT 消息数: {self.room_layout_count}")
        print(f"错误数: {len(self.parse_errors)}")
        
        if self.parse_errors:
            print("\n错误列表:")
            for err in self.parse_errors[-10:]:  # 最后10个错误
                print(f"  - {err}")
        
        print("=" * 60)
    
    def dump_last_data(self):
        """打印最后收到的原始数据"""
        print("\n" + "=" * 60)
        print("最后收到的原始数据")
        print("=" * 60)
        
        if self.last_raw_room_info:
            print("\n--- ROOM_INFO (Lua 发送) ---")
            print(json.dumps(self.last_raw_room_info, indent=2, ensure_ascii=False))
        else:
            print("\n未收到 ROOM_INFO 数据")
        
        if self.last_raw_room_layout:
            print("\n--- ROOM_LAYOUT (Lua 发送) ---")
            layout = self.last_raw_room_layout.copy()
            # 简化 grid 输出
            if "grid" in layout and len(layout["grid"]) > 10:
                grid = layout["grid"]
                layout["grid"] = f"<{len(grid)} tiles, first 5: {dict(list(grid.items())[:5])}>"
            print(json.dumps(layout, indent=2, ensure_ascii=False, default=str))
        else:
            print("\n未收到 ROOM_LAYOUT 数据")
        
        if self.last_parsed_room_info:
            print("\n--- ROOM_INFO (Python 解析后) ---")
            print(f"  room_idx: {self.last_parsed_room_info.room_idx}")
            print(f"  room_type: {self.last_parsed_room_info.room_type}")
            print(f"  room_shape: {self.last_parsed_room_info.room_shape}")
            print(f"  grid: {self.last_parsed_room_info.grid_width}x{self.last_parsed_room_info.grid_height}")
            print(f"  top_left: ({self.last_parsed_room_info.top_left.x}, {self.last_parsed_room_info.top_left.y})")
            print(f"  bottom_right: ({self.last_parsed_room_info.bottom_right.x}, {self.last_parsed_room_info.bottom_right.y})")
        
        print("=" * 60)
    
    def start(self):
        """启动验证器"""
        self.adapter.start()
    
    def stop(self):
        """停止验证器"""
        self.adapter.stop()


def run_live_mode():
    """实时模式"""
    print("=" * 60)
    print("地形数据验证器 - 实时模式")
    print("=" * 60)
    print()
    print("连接游戏后，将验证以下数据：")
    print("  - ROOM_INFO: 房间基本信息")
    print("  - ROOM_LAYOUT: 房间布局（网格、门）")
    print()
    print("按 Ctrl+C 退出并查看总结")
    print("=" * 60)
    
    validator = TerrainValidator()
    
    try:
        validator.start()
        
        while True:
            time.sleep(1)
            
            # 每 5 秒打印一次状态
            if validator.room_info_count > 0 and validator.room_info_count % 5 == 0:
                room_info = validator.adapter.get_room_info()
                if room_info:
                    print(f"\r[Room {room_info.room_idx}] "
                          f"Info: {validator.room_info_count}, "
                          f"Layout: {validator.room_layout_count}, "
                          f"Errors: {len(validator.parse_errors)}",
                          end="", flush=True)
    
    except KeyboardInterrupt:
        print("\n\n收到退出信号...")
    finally:
        validator.stop()
        validator._print_summary()


def run_dump_mode():
    """Dump 模式 - 收集一次数据后打印"""
    print("=" * 60)
    print("地形数据验证器 - Dump 模式")
    print("=" * 60)
    print()
    print("等待收到 ROOM_INFO 和 ROOM_LAYOUT 数据后打印...")
    print("按 Ctrl+C 提前退出")
    print("=" * 60)
    
    validator = TerrainValidator()
    
    try:
        validator.start()
        
        # 等待收到数据
        timeout = 60  # 60秒超时
        start = time.time()
        
        while time.time() - start < timeout:
            if validator.room_info_count > 0 and validator.room_layout_count > 0:
                print("\n收到完整地形数据!")
                break
            time.sleep(0.5)
            print(".", end="", flush=True)
        
        validator.dump_last_data()
    
    except KeyboardInterrupt:
        print("\n\n收到退出信号...")
        validator.dump_last_data()
    finally:
        validator.stop()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="地形数据验证工具 - 验证 Lua 发送的地形数据",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m apps.terrain_validator live    # 实时验证
  python -m apps.terrain_validator dump    # 打印原始数据
        """
    )
    
    parser.add_argument(
        "mode",
        choices=["live", "dump"],
        help="运行模式: live=实时验证, dump=打印原始数据"
    )
    
    args = parser.parse_args()
    
    if args.mode == "live":
        run_live_mode()
    elif args.mode == "dump":
        run_dump_mode()


if __name__ == "__main__":
    main()
