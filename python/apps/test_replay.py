#!/usr/bin/env python3
"""
测试数据回放功能
"""

import sys
import time
import json
import gzip
from pathlib import Path

# 添加 python 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from data_replay_system import (
    LuaSimulator,
    SessionReplayer,
    create_replayer,
    RawMessage,
    MessageType,
)


def load_session_data(session_dir: str) -> list:
    """加载会话的所有消息"""
    messages = []
    for chunk_file in sorted(Path(session_dir).glob("*_chunk_*.json.gz")):
        with gzip.open(chunk_file, "rt", encoding="utf-8") as fp:
            data = json.load(fp)
            for msg_dict in data.get("messages", []):
                messages.append(RawMessage.from_dict(msg_dict))
    return messages


def test_replay():
    """测试回放功能"""
    print("=" * 60)
    print("SocketBridge 回放功能测试")
    print("=" * 60)

    session_dir = "python/recordings"
    session_files = list(Path(session_dir).glob("session_*"))

    if not session_files:
        print(f"错误: 在 {session_dir} 中找不到录制会话")
        return False

    session_id = session_files[0].name
    print(f"\n会话: {session_id}")

    # 加载数据
    print("\n1. 加载会话数据...")
    messages = load_session_data(session_dir)
    print(f"   加载了 {len(messages)} 条消息")

    # 统计
    data_msgs = [m for m in messages if m.msg_type == MessageType.DATA.value]
    event_msgs = [m for m in messages if m.msg_type == MessageType.EVENT.value]
    valid_msgs = [m for m in messages if m.payload or m.event_type]

    print(f"   DATA 消息: {len(data_msgs)}")
    print(f"   EVENT 消息: {len(event_msgs)}")
    print(f"   有效数据消息: {len(valid_msgs)}")

    if messages:
        frames = sorted(set(m.frame for m in messages))
        print(f"   帧范围: {min(frames)} - {max(frames)}")
        print(f"   不同帧数: {len(frames)}")

    # 创建模拟器
    print("\n2. 创建模拟器...")
    simulator = LuaSimulator(host="127.0.0.1", port=9528)
    simulator.load_messages(messages)
    print(f"   模拟器已加载 {len(simulator.messages)} 条消息")

    # 验证消息格式
    print("\n3. 验证消息格式...")
    sample_msg = simulator.messages[0]
    print(f"   样例消息:")
    print(
        f"     version: {sample_msg.version} (type: {type(sample_msg.version).__name__})"
    )
    print(f"     msg_type: {sample_msg.msg_type}")
    print(f"     frame: {sample_msg.frame}")
    print(f"     room_index: {sample_msg.room_index}")

    # 检查格式是否与协议一致
    if isinstance(sample_msg.version, int):
        print("   ✅ version 类型正确 (int)")
    else:
        print(f"   ❌ version 类型错误: {type(sample_msg.version)}")

    # 启动模拟器并测试回放
    print("\n4. 启动模拟器服务器...")
    simulator.start()

    # 模拟客户端连接并接收数据
    import socket

    received_count = 0
    start_time = time.time()
    timeout = 5.0  # 5秒超时

    try:
        print("   等待客户端连接...")
        time.sleep(0.5)

        # 创建客户端连接
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(timeout)
        client.connect(("127.0.0.1", 9528))
        print("   ✅ 客户端已连接")

        # 接收消息
        buffer = ""
        client.settimeout(2.0)  # 2秒接收超时

        print("   接收消息中...")
        while (
            received_count < min(10, len(messages))
            and time.time() - start_time < timeout
        ):
            try:
                data = client.recv(4096)
                if not data:
                    break
                buffer += data.decode("utf-8")

                # 处理完整的 JSON 行
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        msg = json.loads(line)
                        received_count += 1
                        if received_count <= 3:
                            print(
                                f"   收到消息 {received_count}: frame={msg.get('frame')}, type={msg.get('type')}"
                            )
            except socket.timeout:
                break

        client.close()
        print(f"\n   ✅ 成功接收 {received_count} 条消息")

    except Exception as e:
        print(f"   ❌ 错误: {e}")
        return False
    finally:
        simulator.stop()

    # 总结
    print("\n" + "=" * 60)
    print("测试结果:")
    print(f"  - 加载消息: {len(messages)}")
    print(f"  - 有效消息: {len(valid_msgs)}")
    print(f"  - 接收消息: {received_count}")
    print("=" * 60)

    if received_count > 0:
        print("✅ 回放功能基本正常")
        return True
    else:
        print("❌ 回放功能异常")
        return False


if __name__ == "__main__":
    success = test_replay()
    sys.exit(0 if success else 1)
