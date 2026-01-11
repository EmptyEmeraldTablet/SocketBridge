#!/usr/bin/env python3
"""
综合测试：回放录制数据 + isaac_bridge.py 集成测试

测试流程：
1. 启动 LuaSimulator 作为模拟服务器
2. 使用 isaac_bridge.py 连接到模拟器
3. 接收并处理回放的数据
4. 验证数据完整性
"""

import sys
import time
import json
import gzip
import os
import socket
import threading
from pathlib import Path

# 添加 python 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from isaac_bridge import IsaacBridge, GameDataAccessor
from data_replay_system import LuaSimulator, RawMessage


class IntegrationTest:
    def __init__(self, session_dir: str = "recordings", port: int = 9530):
        self.session_dir = session_dir
        self.port = port
        self.running = False

        # 统计
        self.stats = {
            "data_received": 0,
            "event_received": 0,
            "channels_seen": set(),
            "frames_seen": set(),
            "errors": 0,
            "samples": [],
        }

        # 组件
        self.simulator = None
        self.bridge = None
        self.data = None

    def load_session(self) -> bool:
        """加载录制会话"""
        print("\n" + "=" * 70)
        print("步骤 1: 加载录制会话")
        print("=" * 70)

        session_files = sorted(
            [
                f
                for f in os.listdir(self.session_dir)
                if f.endswith(".json.gz") and "chunk" in f
            ]
        )

        if not session_files:
            print(f"❌ 在 {self.session_dir} 中找不到录制文件")
            return False

        # 获取会话ID
        if session_files:
            session_id = session_files[0].replace("_chunk_0000.json.gz", "")
            print(f"   会话ID: {session_id}")
            print(f"   文件数: {len(session_files)}")

        # 加载消息
        messages = []
        for f in session_files:
            with gzip.open(f"{self.session_dir}/{f}", "rt", encoding="utf-8") as fp:
                data = json.load(fp)
                # 转换为 RawMessage 对象
                for msg_dict in data.get("messages", []):
                    messages.append(RawMessage.from_dict(msg_dict))

        print(f"   总消息数: {len(messages)}")

        # 创建模拟器
        self.simulator = LuaSimulator(host="127.0.0.1", port=self.port, reuse_addr=True)
        self.simulator.load_messages(messages)
        print(f"   模拟器已就绪")

        return True

    def setup_bridge(self):
        """设置 isaac_bridge.py 连接"""
        print("\n" + "=" * 70)
        print("步骤 2: 设置 isaac_bridge.py")
        print("=" * 70)

        self.bridge = IsaacBridge(host="127.0.0.1", port=self.port)
        self.data = GameDataAccessor(self.bridge)

        # 设置数据接收回调
        @self.bridge.on("connected")
        def on_connected(info):
            print(f"   ✅ isaac_bridge.py 已连接: {info['address']}")

        @self.bridge.on("disconnected")
        def on_disconnected(_):
            print(f"   ❌ isaac_bridge.py 已断开连接")
            self.running = False

        @self.bridge.on("data")
        def on_data(payload):
            self.stats["data_received"] += 1

            # 记录通道
            if isinstance(payload, dict):
                self.stats["channels_seen"].update(payload.keys())

            # 记录帧号
            if self.data.frame > 0:
                self.stats["frames_seen"].add(self.data.frame)

            # 保存样例
            if len(self.stats["samples"]) < 5:
                self.stats["samples"].append(
                    {
                        "frame": self.data.frame,
                        "room": self.data.room_index,
                        "player_pos": self.data.get_player_position(),
                        "enemy_count": len(self.data.get_enemies()),
                    }
                )

        @self.bridge.on("event")
        def on_event(event):
            self.stats["event_received"] += 1
            print(f"   📢 事件: {event.type}")

        print(f"   回调已注册")

    def run_test(self, duration: int = 10):
        """运行测试"""
        print("\n" + "=" * 70)
        print(f"步骤 3: 运行测试 (持续 {duration} 秒)")
        print("=" * 70)

        self.running = True

        # 启动模拟器
        print(f"   启动 LuaSimulator (端口 {self.port})...")
        self.simulator.start()
        time.sleep(0.5)

        # 启动 isaac_bridge.py
        print(f"   启动 isaac_bridge.py...")
        self.bridge.start()

        # 等待测试完成
        print(f"   测试运行中...")
        start_time = time.time()

        try:
            while self.running and (time.time() - start_time) < duration:
                time.sleep(1)

                # 定期输出状态
                elapsed = int(time.time() - start_time)
                if elapsed % 3 == 0:
                    print(
                        f"   [{elapsed}/{duration}s] 数据: {self.stats['data_received']}, "
                        f"事件: {self.stats['event_received']}, "
                        f"帧: {self.data.frame}, "
                        f"房间: {self.data.room_index}"
                    )

        except KeyboardInterrupt:
            print("\n   用户中断")

        # 停止
        self.stop()

        return self.get_results()

    def stop(self):
        """停止测试"""
        print(f"\n   停止测试...")
        self.running = False

        if self.bridge:
            try:
                self.bridge.stop()
            except:
                pass

        if self.simulator:
            try:
                self.simulator.stop()
            except:
                pass

        time.sleep(0.5)
        print(f"   已停止")

    def get_results(self) -> dict:
        """获取测试结果"""
        return {
            "data_received": self.stats["data_received"],
            "event_received": self.stats["event_received"],
            "channels_seen": list(self.stats["channels_seen"]),
            "frames_seen": sorted(self.stats["frames_seen"]),
            "samples": self.stats["samples"],
            "errors": self.stats["errors"],
        }


def main():
    print("=" * 70)
    print("SocketBridge 集成测试：回放 + isaac_bridge.py")
    print("=" * 70)

    # 检查录制文件
    session_dir = "recordings"
    if not os.path.exists(session_dir):
        session_dir = "python/recordings"  # 尝试备选路径

    if not os.path.exists(session_dir):
        print(f"❌ {session_dir} 目录不存在")
        print("请先运行录制脚本：python data_replay_examples.py record")
        return 1

    chunk_files = [
        f for f in os.listdir(session_dir) if f.endswith(".json.gz") and "chunk" in f
    ]
    if not chunk_files:
        print(f"❌ {session_dir} 目录中没有录制文件")
        return 1

    # 创建测试
    test = IntegrationTest(session_dir=session_dir, port=9530)

    # 步骤 1: 加载会话
    if not test.load_session():
        return 1

    # 步骤 2: 设置桥接器
    test.setup_bridge()

    # 步骤 3: 运行测试
    results = test.run_test(duration=15)

    # 输出结果
    print("\n" + "=" * 70)
    print("测试结果")
    print("=" * 70)

    print(f"\n📊 数据统计:")
    print(f"   DATA 消息: {results['data_received']}")
    print(f"   EVENT 消息: {results['event_received']}")

    print(f"\n📡 数据通道:")
    if results["channels_seen"]:
        for ch in sorted(results["channels_seen"]):
            print(f"   - {ch}")
    else:
        print("   (未收到数据)")

    print(f"\n🎬 帧范围:")
    if results["frames_seen"]:
        print(f"   帧: {min(results['frames_seen'])} - {max(results['frames_seen'])}")
        print(f"   不同帧数: {len(results['frames_seen'])}")
    else:
        print("   (未收到帧数据)")

    print(f"\n📝 数据样例:")
    for i, sample in enumerate(results["samples"][:3]):
        print(f"   样例 {i + 1}:")
        print(f"     Frame: {sample['frame']}, Room: {sample['room']}")
        if sample["player_pos"]:
            pos = sample["player_pos"]
            if isinstance(pos, list) and pos:
                p = (
                    pos[0]
                    if isinstance(pos[0], dict)
                    else pos[0][1]
                    if len(pos[0]) > 1
                    else pos[0]
                )
                print(f"     玩家位置: {p.get('pos', {})}")
        print(f"     敌人数: {sample['enemy_count']}")

    # 验证
    print(f"\n✅ 验证结果:")
    if results["data_received"] > 0:
        print("   ✅ isaac_bridge.py 成功接收 DATA 消息")
    else:
        print("   ❌ 未收到 DATA 消息")

    if results["channels_seen"]:
        print(f"   ✅ 成功解析 {len(results['channels_seen'])} 个数据通道")
    else:
        print("   ❌ 未解析到数据通道")

    if results["frames_seen"]:
        print(
            f"   ✅ 帧号跟踪正常 (范围: {min(results['frames_seen'])} - {max(results['frames_seen'])})"
        )
    else:
        print("   ❌ 帧号跟踪异常")

    # 总结
    print("\n" + "=" * 70)
    if results["data_received"] > 0 and results["channels_seen"]:
        print("🎉 集成测试通过！回放系统与 isaac_bridge.py 正常工作")
    else:
        print("⚠️ 集成测试有问题，请检查输出")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
