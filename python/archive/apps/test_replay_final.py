#!/usr/bin/env python3
"""
回放功能测试
"""

import gzip
import json
import os
import socket
import time
import threading
import sys
from pathlib import Path

# 添加 python 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from data_replay_system import LuaSimulator, RawMessage, MessageType


def test_replay():
    session_dir = "python/recordings"
    session_id = "session_20260111_170431"

    print("=" * 70)
    print("回放功能测试")
    print("=" * 70)

    # 1. 加载会话数据
    print("\n1. 加载会话数据...")
    messages = []
    for f in sorted(
        [f for f in os.listdir(session_dir) if f.endswith(".json.gz") and "chunk" in f]
    ):
        with gzip.open(f"{session_dir}/{f}", "rt", encoding="utf-8") as fp:
            data = json.load(fp)
            for msg_dict in data.get("messages", []):
                messages.append(RawMessage.from_dict(msg_dict))

    print(f"   加载了 {len(messages)} 条消息")

    # 2. 验证消息结构
    print("\n2. 验证消息结构...")
    sample = messages[0]
    print(f"   version: {sample.version} (type: {type(sample.version).__name__})")
    print(f"   msg_type: {sample.msg_type}")
    print(f"   frame: {sample.frame}")
    print(f"   room_index: {sample.room_index}")
    print(f"   payload keys: {list(sample.payload.keys()) if sample.payload else None}")
    print(f"   channels: {sample.channels}")

    # 验证数据通道
    data_msgs = [m for m in messages if m.msg_type == MessageType.DATA.value]
    channels_found = set()
    for msg in data_msgs[:100]:
        if msg.channels:
            channels_found.update(msg.channels)
    print(f"\n   验证的数据通道: {sorted(channels_found)}")

    if sample.payload and sample.channels:
        print("   ✅ 消息结构验证通过")
    else:
        print("   ❌ 消息结构异常")
        return False

    # 3. 创建模拟器并加载
    print("\n3. 创建 LuaSimulator...")
    simulator = LuaSimulator(host="127.0.0.1", port=9529)
    simulator.load_messages(messages)
    print(f"   模拟器已加载 {len(simulator.messages)} 条消息")

    # 4. 测试回放
    print("\n4. 测试回放...")

    received_count = 0
    receive_data = []

    def client_thread():
        global received_count, receive_data
        time.sleep(0.5)  # 等待服务器启动

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(10)
        client.connect(("127.0.0.1", 9529))

        buffer = ""
        start = time.time()
        while time.time() - start < 5 and received_count < 50:  # 最多5秒或50条消息
            try:
                data = client.recv(4096)
                if not data:
                    break
                buffer += data.decode("utf-8")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        msg = json.loads(line)
                        received_count += 1
                        receive_data.append(msg)
                        if received_count <= 3:
                            print(
                                f"   收到 #{received_count}: frame={msg.get('frame')}, type={msg.get('type')}"
                            )
                            if "channels" in msg:
                                print(
                                    f"             channels={msg.get('channels')[:3]}..."
                                )
            except socket.timeout:
                continue

        client.close()

    # 启动服务器和客户端
    simulator.start()

    # 启动客户端线程
    thread = threading.Thread(target=client_thread)
    thread.start()
    thread.join(timeout=10)

    simulator.stop()

    # 5. 结果
    print("\n" + "=" * 70)
    print("测试结果")
    print("=" * 70)
    print(f"  加载消息: {len(messages)}")
    print(f"  接收消息: {received_count}")
    print(
        f"  回放成功率: {received_count}/{min(50, len(messages))} ({100 * received_count / max(1, min(50, len(messages))):.1f}%)"
    )

    if received_count > 0:
        print("\n  接收的消息示例:")
        for msg in receive_data[:3]:
            print(f"    Frame {msg.get('frame')}: type={msg.get('type')}")
            if msg.get("channels"):
                print(f"      Channels: {msg.get('channels')}")
            if msg.get("payload"):
                keys = list(msg.get("payload", {}).keys())
                print(f"      Payload keys: {keys[:5]}...")

        print("\n✅ 回放功能测试通过")
        return True
    else:
        print("\n❌ 回放功能测试失败")
        return False


if __name__ == "__main__":
    success = test_replay()
    sys.exit(0 if success else 1)
