#!/usr/bin/env python3
"""
SocketBridge 集成测试：回放录制数据 + isaac_bridge.py

测试流程（模拟实际使用场景）:
1. 启动 isaac_bridge.py 作为服务器（等待游戏连接）
2. 使用 LuaSimulator.connect() 模拟游戏连接 isaac_bridge
3. LuaSimulator.play() 发送录制数据
4. 验证 isaac_bridge 正确接收和处理数据
"""

import sys
import time
import json
import gzip
import os
import threading
from pathlib import Path

# 添加 python 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from isaac_bridge import IsaacBridge, GameDataAccessor
from data_replay_system import LuaSimulator, RawMessage


class IntegrationTest:
    def __init__(self, session_dir: str = "recordings", listen_port: int = 9602):
        self.session_dir = Path(session_dir)
        self.listen_port = listen_port  # isaac_bridge 监听端口
        self.running = False
        self.connected = threading.Event()

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

        # 查找所有会话的 chunk 文件
        chunk_files = sorted(self.session_dir.glob("*_chunk_*.json.gz"))

        if not chunk_files:
            print(f"   ❌ 在 {self.session_dir} 中找不到录制文件")
            return False

        # 提取会话ID
        session_ids = set()
        for f in chunk_files:
            name = f.name
            if "_chunk_" in name:
                session_id = name.rsplit("_chunk_", 1)[0]
                session_ids.add(session_id)

        if not session_ids:
            print("   ❌ 无法解析会话ID")
            return False

        # 选择最新的会话
        session_id = sorted(session_ids, reverse=True)[0]
        print(f"   会话ID: {session_id}")

        # 获取该会话的所有 chunk 文件
        session_files = sorted(
            [f for f in chunk_files if f.name.startswith(session_id + "_chunk_")]
        )
        print(f"   文件数: {len(session_files)}")

        # 加载消息
        messages = []
        for chunk_file in session_files:
            with gzip.open(chunk_file, "rt", encoding="utf-8") as fp:
                data = json.load(fp)
                for msg_dict in data.get("messages", []):
                    messages.append(RawMessage.from_dict(msg_dict))

        print(f"   总消息数: {len(messages)}")

        if len(messages) == 0:
            print("   ❌ 消息数为0")
            return False

        # 创建模拟器
        self.simulator = LuaSimulator(host="127.0.0.1", port=self.listen_port)
        self.simulator.load_messages(messages)
        print(f"   模拟器已就绪")

        return True

    def setup_bridge(self):
        """设置 isaac_bridge.py 服务器"""
        print("\n" + "=" * 70)
        print("步骤 2: 设置 isaac_bridge.py 服务器")
        print("=" * 70)

        # isaac_bridge 作为服务器，监听端口等待连接
        self.bridge = IsaacBridge(host="127.0.0.1", port=self.listen_port)
        self.data = GameDataAccessor(self.bridge)

        # 设置回调
        @self.bridge.on("connected")
        def on_connected(info):
            print(f"   ✅ 客户端已连接: {info['address']}")
            self.connected.set()

        @self.bridge.on("disconnected")
        def on_disconnected(_):
            print(f"   ❌ 客户端已断开")
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
        print(f"   监听端口: {self.listen_port}")

    def run_test(self, max_messages: int = 1000, timeout: float = 30.0):
        """运行测试

        遵循实际使用场景：
        - isaac_bridge 已启动并等待连接
        - LuaSimulator.connect() 模拟游戏连接并发送数据
        - 等待接收指定数量的消息或超时
        """
        print("\n" + "=" * 70)
        print(
            f"步骤 3: 运行测试 (等待最多 {timeout} 秒，接收最多 {max_messages} 条消息)"
        )
        print("=" * 70)

        self.running = True

        # 1. 启动 isaac_bridge 服务器
        print(f"   启动 isaac_bridge.py 服务器 (端口 {self.listen_port})...")
        self.bridge.start()
        time.sleep(0.3)  # 等待服务器启动

        # 2. LuaSimulator 作为客户端连接到 isaac_bridge
        print(f"   启动 LuaSimulator 客户端，连接到 isaac_bridge...")
        success = self.simulator.connect(
            host="127.0.0.1", port=self.listen_port, timeout=5.0
        )
        if not success:
            print("   ❌ 连接失败")
            self.stop()
            return self.get_results()

        # 3. 开始发送数据
        print(f"   开始发送数据...")
        self.simulator.play()

        # 4. 等待连接建立
        connected = self.connected.wait(timeout=5.0)
        if not connected:
            print("   ❌ 客户端连接超时")
            self.stop()
            return self.get_results()

        print(f"   ✅ 客户端已连接，开始接收数据...")

        # 5. 等待接收数据
        print(f"   接收数据中...")
        start_time = time.time()
        last_progress_time = start_time
        progress_interval = 3

        try:
            while self.running:
                elapsed = time.time() - start_time

                # 检查超时
                if elapsed > timeout:
                    print(f"   ⏱️  超时 ({timeout}秒)，停止测试")
                    break

                # 检查消息数量
                if self.stats["data_received"] >= max_messages:
                    print(f"   ✅ 已接收 {max_messages} 条消息，停止测试")
                    break

                # 检查发送线程是否结束
                if (
                    self.simulator._send_thread
                    and not self.simulator._send_thread.is_alive()
                ):
                    print(f"   ✅ 数据发送完成")
                    break

                # 定期输出进度
                if time.time() - last_progress_time >= progress_interval:
                    print(
                        f"   [{int(elapsed)}s] 数据: {self.stats['data_received']}, "
                        f"事件: {self.stats['event_received']}, "
                        f"帧: {self.data.frame}, "
                        f"房间: {self.data.room_index}"
                    )
                    last_progress_time = time.time()

                time.sleep(0.5)

        except KeyboardInterrupt:
            print("\n   用户中断")

        # 等待发送线程结束
        if self.simulator._send_thread:
            self.simulator._send_thread.join(timeout=5.0)

        # 停止
        self.stop()

        return self.get_results()

    def stop(self):
        """停止测试"""
        print(f"\n   停止测试...")
        self.running = False

        if self.simulator:
            try:
                self.simulator.disconnect()
            except:
                pass

        if self.bridge:
            try:
                self.bridge.stop()
            except:
                pass

        time.sleep(0.2)
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
    print()
    print("测试流程（模拟实际使用场景）:")
    print("1. 启动 isaac_bridge.py 作为服务器")
    print("2. LuaSimulator.connect() 模拟游戏连接")
    print("3. LuaSimulator.play() 发送录制数据")
    print("4. 验证 isaac_bridge 正确接收数据")
    print()

    # 确定录制目录
    session_dir = Path("recordings")
    if not session_dir.exists():
        session_dir = Path(__file__).parent / "recordings"

    if not session_dir.exists():
        print(f"❌ {session_dir} 目录不存在")
        print("请先运行录制脚本：python data_replay_examples.py record")
        return 1

    chunk_files = list(session_dir.glob("*_chunk_*.json.gz"))
    if not chunk_files:
        print(f"❌ {session_dir} 目录中没有录制文件")
        return 1

    # 创建测试（使用端口 9602）
    test = IntegrationTest(session_dir=str(session_dir), listen_port=9602)

    # 步骤 1: 加载会话
    if not test.load_session():
        return 1

    # 步骤 2: 设置桥接器
    test.setup_bridge()

    # 步骤 3: 运行测试
    results = test.run_test(max_messages=1000, timeout=30.0)

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
                first_item = pos[0]
                if isinstance(first_item, dict):
                    p = first_item
                elif isinstance(first_item, (list, tuple)) and len(first_item) > 1:
                    p = first_item[1]
                else:
                    p = first_item
                if isinstance(p, dict):
                    print(f"     玩家位置: {p.get('pos', {})}")
        print(f"     敌人数: {sample['enemy_count']}")

    # 验证
    print(f"\n✅ 验证结果:")
    success = True

    if results["data_received"] > 0:
        print("   ✅ isaac_bridge.py 成功接收 DATA 消息")
    else:
        print("   ❌ 未收到 DATA 消息")
        success = False

    if results["channels_seen"]:
        print(f"   ✅ 成功解析 {len(results['channels_seen'])} 个数据通道")
    else:
        print("   ❌ 未解析到数据通道")
        success = False

    if results["frames_seen"]:
        print(
            f"   ✅ 帧号跟踪正常 (范围: {min(results['frames_seen'])} - {max(results['frames_seen'])})"
        )
    else:
        print("   ❌ 帧号跟踪异常")
        success = False

    # 总结
    print("\n" + "=" * 70)
    if success:
        print("🎉 集成测试通过！回放系统与 isaac_bridge.py 正常工作")
    else:
        print("⚠️ 集成测试有问题，请检查输出")
    print("=" * 70)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
