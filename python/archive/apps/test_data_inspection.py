"""
数据采集测试脚本

用于在手动模式下测试和检查所有数据采集情况
"""

import sys
import time
from pathlib import Path
from isaac_bridge import IsaacBridge, GameDataAccessor
from data_recorder import DataInspector
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("DataTest")


class DataTester:
    """数据采集测试器"""
    
    def __init__(self, bridge: IsaacBridge):
        self.bridge = bridge
        self.data = GameDataAccessor(bridge)
        self.inspector = None
        
        # 测试统计
        self.test_stats = {
            "snapshots_taken": 0,
            "channels_with_data": set(),
            "channels_without_data": set(),
            "last_frame": 0,
        }
    
    def start_inspection(self, interval: float = 5.0, log_file: str = None):
        """启动数据检查"""
        log_path = Path(log_file) if log_file else None
        
        self.inspector = DataInspector(
            bridge=self.bridge,
            interval=interval,
            log_file=log_file
        )
        
        self.inspector.start()
        logger.info(f"Data inspection started (interval: {interval}s)")
        if log_path:
            logger.info(f"Log file: {log_path}")
    
    def stop_inspection(self):
        """停止数据检查"""
        if self.inspector:
            self.inspector.stop()
            logger.info("Data inspection stopped")
    
    def print_summary(self):
        """打印测试摘要"""
        print("\n" + "=" * 80)
        print("数据采集测试摘要")
        print("=" * 80)
        print(f"快照次数: {self.test_stats['snapshots_taken']}")
        print(f"当前帧数: {self.test_stats['last_frame']}")
        print(f"\n有数据通道 ({len(self.test_stats['channels_with_data'])}):")
        for channel in sorted(self.test_stats['channels_with_data']):
            print(f"  ✓ {channel}")
        
        print(f"\n无数据通道 ({len(self.test_stats['channels_without_data'])}):")
        for channel in sorted(self.test_stats['channels_without_data']):
            print(f"  ✗ {channel}")
        print("=" * 80 + "\n")
    
    def check_all_channels(self):
        """检查所有数据通道"""
        channels = [
            "PLAYER_POSITION", "PLAYER_STATS", "PLAYER_HEALTH",
            "PLAYER_INVENTORY", "ENEMIES", "PROJECTILES",
            "ROOM_INFO", "ROOM_LAYOUT", "PICKUPS",
            "FIRE_HAZARDS", "DESTRUCTIBLES"
        ]
        
        print("\n" + "=" * 80)
        print("数据通道检查")
        print("=" * 80)
        
        for channel in channels:
            data = self.data.state.get(channel)
            has_data = data is not None
            
            if has_data:
                self.test_stats['channels_with_data'].add(channel)
                status = "✓ 有数据"
            else:
                self.test_stats['channels_without_data'].add(channel)
                status = "✗ 无数据"
            
            print(f"{channel:25s} {status}")
        
        print("=" * 80)
    
    def monitor_loop(self):
        """监控循环"""
        logger.info("Starting monitoring loop...")
        logger.info("Press Ctrl+C to stop and see summary")
        
        try:
            while True:
                time.sleep(1)
                
                # 更新统计
                if self.data.frame > self.test_stats['last_frame']:
                    self.test_stats['last_frame'] = self.data.frame
                    self.test_stats['snapshots_taken'] = self.inspector._snapshot_count
                
                # 每 30 秒检查一次所有通道
                if self.test_stats['last_frame'] % 1800 == 0 and self.test_stats['last_frame'] > 0:
                    self.check_all_channels()
        
        except KeyboardInterrupt:
            logger.info("\nMonitoring stopped by user")
            self.check_all_channels()
            self.print_summary()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="数据采集测试工具 - 在手动模式下检查所有数据采集情况"
    )
    parser.add_argument(
        "--interval", type=float, default=5.0,
        help="数据快照输出间隔（秒），默认 5 秒"
    )
    parser.add_argument(
        "--log-file", type=str, default=None,
        help="日志文件路径，默认不保存到文件"
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1",
        help="服务器地址，默认 127.0.0.1"
    )
    parser.add_argument(
        "--port", type=int, default=9527,
        help="服务器端口，默认 9527"
    )
    
    args = parser.parse_args()
    
    # 创建日志文件路径
    log_file = args.log_file
    if log_file is None:
        # 自动生成日志文件名
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"./logs/data_test_{timestamp}.log"
    
    # 确保日志目录存在
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    
    # 创建桥接器
    bridge = IsaacBridge(host=args.host, port=args.port)
    
    # 创建测试器
    tester = DataTester(bridge)
    
    # 连接事件处理
    @bridge.on("connected")
    def on_connected(data):
        logger.info("✓ Game connected!")
        logger.info("请在游戏中按 F3 切换到手动模式")
        logger.info("然后进行各种操作来测试数据采集")
        tester.start_inspection(interval=args.interval, log_file=log_file)
    
    @bridge.on("disconnected")
    def on_disconnected(data):
        logger.info("✗ Game disconnected")
        tester.stop_inspection()
    
    # 启动服务器
    bridge.start()
    logger.info(f"Server started on {args.host}:{args.port}")
    logger.info("Waiting for game connection...")
    
    # 进入监控循环
    try:
        tester.monitor_loop()
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    finally:
        tester.stop_inspection()
        bridge.stop()


if __name__ == "__main__":
    main()
