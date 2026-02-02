#!/usr/bin/env python
"""
Phase 0 P0 时序协议测试脚本

测试内容：
1. 连接到游戏
2. 验证 v2.1 时序字段是否存在
3. 使用 TimingMonitor 检测时序问题
4. 统计数据质量

使用方法：
1. 运行此脚本：python test_timing_protocol.py
2. 启动 The Binding of Isaac 游戏
3. 进入游戏（开始新游戏或继续）
4. 游戏会自动连接到此脚本
"""

import sys
import time
import json
from datetime import datetime

# 添加路径
sys.path.insert(0, ".")

from isaac_bridge import IsaacBridge
from core.protocol import TimingMonitor, MessageTimingInfo, TimingIssueType


class TimingProtocolTester:
    def __init__(self):
        self.bridge = IsaacBridge()
        self.monitor = TimingMonitor()
        
        # 统计
        self.messages_received = 0
        self.v21_messages = 0
        self.v20_messages = 0
        self.full_state_count = 0
        self.data_count = 0
        
        # 采样数据
        self.sample_messages = []
        self.max_samples = 5
        
        # 注册回调
        self._setup_handlers()
        
    def _setup_handlers(self):
        """设置消息处理器"""
        @self.bridge.on("raw_message")
        def on_raw_message(msg):
            self._handle_message(msg)
            
        @self.bridge.on("connected")
        def on_connected(info):
            print(f"✅ 游戏已连接: {info}")
            
        @self.bridge.on("disconnected")
        def on_disconnected(_):
            print("⚠️ 游戏断开连接")
        
    def _handle_message(self, msg: dict):
        """处理接收到的消息"""
        self.messages_received += 1
        msg_type = msg.get("type", "UNKNOWN")
        version = msg.get("version", "?")
        
        # 检查是否有 v2.1 时序字段
        has_seq = "seq" in msg
        has_channel_meta = "channel_meta" in msg
        has_prev_frame = "prev_frame" in msg
        
        is_v21 = has_seq or has_channel_meta
        
        if is_v21:
            self.v21_messages += 1
        else:
            self.v20_messages += 1
            
        if msg_type in ("FULL", "FULL_STATE"):
            self.full_state_count += 1
        elif msg_type == "DATA":
            self.data_count += 1
            
        # 保存采样
        if len(self.sample_messages) < self.max_samples:
            self.sample_messages.append({
                "type": msg_type,
                "version": version,
                "frame": msg.get("frame", 0),
                "has_seq": has_seq,
                "has_channel_meta": has_channel_meta,
                "has_prev_frame": has_prev_frame,
                "seq": msg.get("seq"),
                "channel_meta_keys": list(msg.get("channel_meta", {}).keys()) if msg.get("channel_meta") else [],
            })
            
        # 使用 TimingMonitor 检测问题
        if is_v21:
            timing = MessageTimingInfo.from_message(msg)
            issues = self.monitor.check_message(timing)
            if issues:
                for issue in issues:
                    severity_color = {
                        "error": "\033[91m",  # 红色
                        "warning": "\033[93m",  # 黄色
                        "info": "\033[94m",  # 蓝色
                    }.get(issue.severity, "")
                    reset = "\033[0m"
                    print(f"  {severity_color}[{issue.issue_type.value}]{reset} frame={issue.frame} {issue.details}")
                    
    def print_status(self):
        """打印当前状态"""
        stats = self.monitor.get_stats()
        
        print("\n" + "=" * 60)
        print(f"📊 时序协议测试报告 - {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 60)
        
        print(f"\n📨 消息统计:")
        print(f"   总消息数: {self.messages_received}")
        print(f"   ├─ v2.1 消息: {self.v21_messages} {'✅' if self.v21_messages > 0 else '❌'}")
        print(f"   ├─ v2.0 消息: {self.v20_messages} {'⚠️ 旧版本' if self.v20_messages > 0 else ''}")
        print(f"   ├─ FULL_STATE: {self.full_state_count}")
        print(f"   └─ DATA: {self.data_count}")
        
        print(f"\n⏱️ 时序质量:")
        print(f"   帧间隙: {stats['frame_gaps']}")
        print(f"   乱序消息: {stats['out_of_order']}")
        print(f"   过期通道: {stats['stale_channels']}")
        print(f"   问题率: {stats['issue_rate']:.2%}")
        
        if self.sample_messages:
            print(f"\n📝 消息采样 (前 {len(self.sample_messages)} 条):")
            for i, sample in enumerate(self.sample_messages):
                v21_mark = "✅ v2.1" if sample["has_seq"] else "❌ v2.0"
                print(f"   [{i+1}] {sample['type']} frame={sample['frame']} {v21_mark}")
                if sample["has_seq"]:
                    print(f"       seq={sample['seq']}, channels={sample['channel_meta_keys']}")
                    
        print("\n" + "=" * 60)
        
    def run(self, duration: int = 30):
        """运行测试"""
        print("🎮 Phase 0 P0 时序协议测试")
        print("=" * 60)
        print("请启动游戏并进入游戏中...")
        print(f"测试时长: {duration} 秒")
        print("=" * 60)
        
        # 启动服务器（等待游戏连接）
        print("\n🔌 启动服务器，等待游戏连接...")
        try:
            self.bridge.start()
            print(f"✅ 服务器启动成功! 监听 {self.bridge.host}:{self.bridge.port}")
            print("   请启动游戏...")
        except Exception as e:
            print(f"❌ 服务器启动失败: {e}")
            return False
        
        # 等待连接
        print("\n⏳ 等待游戏连接...")
        wait_start = time.time()
        while not self.bridge.connected and time.time() - wait_start < 60:
            time.sleep(0.5)
            if int(time.time() - wait_start) % 10 == 0:
                print(f"   ... 已等待 {int(time.time() - wait_start)} 秒")
                
        if not self.bridge.connected:
            print("❌ 等待超时，游戏未连接")
            self.bridge.stop()
            return False
            
        print("✅ 游戏已连接!")
            
        # 请求完整状态
        print("\n📤 请求完整状态...")
        try:
            self.bridge.send_command("GET_FULL_STATE", {})
            print("✅ 命令已发送")
        except Exception as e:
            print(f"⚠️ 发送命令失败: {e}")
            
        # 接收数据
        print(f"\n📥 接收数据中... (等待 {duration} 秒)")
        start_time = time.time()
        last_print = start_time
        
        try:
            while time.time() - start_time < duration:
                # 检查连接状态
                if not self.bridge.connected:
                    print("\n⚠️ 游戏断开连接")
                    break
                
                # 每 5 秒打印进度
                if time.time() - last_print >= 5:
                    elapsed = int(time.time() - start_time)
                    print(f"   ... {elapsed}s 已收到 {self.messages_received} 条消息")
                    last_print = time.time()
                    
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n⏹️ 用户中断测试")
            
        # 打印报告
        self.print_status()
        
        # 停止服务器
        print("\n🔌 停止服务器...")
        self.bridge.stop()
        
        # 判断结果
        success = self.v21_messages > 0
        if success:
            print("\n✅ 测试通过! v2.1 时序协议工作正常")
        else:
            if self.messages_received > 0:
                print("\n❌ 测试失败! 收到消息但没有 v2.1 格式")
                print("   请检查 main.lua 是否已更新")
            else:
                print("\n❌ 测试失败! 未收到任何消息")
                print("   请确保游戏中已加载 SocketBridge mod")
            
        return success


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Phase 0 P0 时序协议测试")
    parser.add_argument("-d", "--duration", type=int, default=30, 
                        help="测试时长(秒), 默认 30")
    parser.add_argument("-q", "--quick", action="store_true",
                        help="快速测试模式 (10秒)")
    args = parser.parse_args()
    
    duration = 10 if args.quick else args.duration
    
    tester = TimingProtocolTester()
    success = tester.run(duration)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
