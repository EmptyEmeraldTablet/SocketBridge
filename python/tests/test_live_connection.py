"""
Live Connection Test - 实机连接测试

使用 BridgeAdapter 连接真实游戏进行测试。
运行此脚本后启动游戏，Mod 会自动连接到 Python 端。

Usage:
    cd python
    python -m tests.test_live_connection
    
    # 或
    python tests/test_live_connection.py
"""

import sys
import os
import time
import logging
from pathlib import Path
from datetime import datetime

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
logger = logging.getLogger("live_test")


def main():
    """主测试入口"""
    print("=" * 60)
    print("SocketBridge 实机连接测试")
    print("=" * 60)
    print()
    print("启动后请运行游戏（The Binding of Isaac）")
    print("Mod 将自动连接到本服务器...")
    print()
    print("按 Ctrl+C 退出")
    print("=" * 60)
    print()
    
    # 导入适配器
    from core.connection import BridgeAdapter, AdapterConfig
    
    # 创建适配器（启用日志）
    config = AdapterConfig(
        log_messages=False,  # 设为 True 可看到每条消息
        validation_enabled=True,
        monitoring_enabled=True,
    )
    adapter = BridgeAdapter(config)
    
    # 统计
    stats = {
        "connect_time": None,
        "frames_received": 0,
        "last_position": None,
        "enemies_count": 0,
        "rooms_visited": set(),
    }
    
    # ===== 注册事件回调 =====
    
    @adapter.on("connected")
    def on_connected(data):
        stats["connect_time"] = datetime.now()
        addr = data.get("address", "unknown")
        print(f"\n[CONNECTED] 游戏已连接! 地址: {addr}")
        print("开始接收数据...\n")
    
    @adapter.on("disconnected")
    def on_disconnected(data):
        print(f"\n[DISCONNECTED] 游戏已断开")
        if stats["connect_time"]:
            duration = datetime.now() - stats["connect_time"]
            print(f"  连接时长: {duration}")
            print(f"  收到帧数: {stats['frames_received']}")
            print(f"  访问房间: {len(stats['rooms_visited'])}")
        print()
    
    @adapter.on("frame")
    def on_frame(frame: int, processed_data):
        stats["frames_received"] += 1
        
        # 获取玩家位置
        pos = adapter.get_player_position()
        if pos:
            stats["last_position"] = pos
        
        # 获取敌人数量
        enemies = adapter.get_enemies()
        if enemies:
            stats["enemies_count"] = len(enemies)
        
        # 获取房间信息 - 使用安全访问
        room_info = adapter.get_room_info()
        if room_info is not None:
            room_idx = getattr(room_info, 'room_idx', None)
            if room_idx is not None:
                stats["rooms_visited"].add(room_idx)
        
        # 每 60 帧输出一次状态（大约每秒一次）
        if frame % 60 == 0:
            print_frame_status(frame, pos, enemies, room_info)
    
    def print_frame_status(frame, pos, enemies, room_info):
        """打印帧状态"""
        pos_str = f"({pos[0]:.1f}, {pos[1]:.1f})" if pos else "N/A"
        enemy_count = len(enemies) if enemies else 0
        room_idx = getattr(room_info, 'room_idx', 'N/A') if room_info else "N/A"
        room_type = getattr(room_info, 'room_type', '') if room_info else ""
        
        print(f"Frame {frame:5d} | "
              f"Pos: {pos_str:15s} | "
              f"Enemies: {enemy_count:2d} | "
              f"Room: {room_idx} (type={room_type})")
    
    # ===== 启动服务器 =====
    
    try:
        adapter.start()
        print(f"服务器已启动，监听 {config.host}:{config.port}")
        print()
        
        # 主循环
        while True:
            time.sleep(1)
            
            # 每 10 秒输出一次汇总
            if adapter.connected and stats["frames_received"] > 0:
                if stats["frames_received"] % 600 == 0:
                    print_summary(adapter, stats)
                    
    except KeyboardInterrupt:
        print("\n\n收到退出信号...")
    finally:
        adapter.stop()
        print_final_summary(adapter, stats)


def print_summary(adapter, stats):
    """打印周期性汇总"""
    print("\n" + "-" * 50)
    print("周期性汇总:")
    print(f"  总帧数: {stats['frames_received']}")
    print(f"  访问房间数: {len(stats['rooms_visited'])}")
    
    # 质量报告
    if adapter.facade.config.monitoring_enabled:
        quality = adapter.get_quality_report()
        print(f"  数据质量:\n{quality}")
    print("-" * 50 + "\n")


def print_final_summary(adapter, stats):
    """打印最终汇总"""
    print("\n" + "=" * 60)
    print("测试结束 - 最终统计")
    print("=" * 60)
    print(f"总帧数: {stats['frames_received']}")
    print(f"访问房间数: {len(stats['rooms_visited'])}")
    if stats["last_position"]:
        print(f"最后位置: ({stats['last_position'][0]:.1f}, {stats['last_position'][1]:.1f})")
    
    # 详细统计
    if adapter.message_count > 0:
        stats_data = adapter.get_stats()
        print(f"\n消息统计:")
        print(f"  总消息数: {stats_data['message_count']}")
        print(f"  消息速率: {stats_data['messages_per_second']:.1f} msg/s")
        print(f"  运行时间: {stats_data['uptime_seconds']:.1f}s")
    
    print("=" * 60)


if __name__ == "__main__":
    main()
