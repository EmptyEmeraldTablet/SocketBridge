#!/usr/bin/env python3
"""
验证 DataMessage 回调机制是否正确工作

测试逻辑：
1. 桥接器 (IsaacBridge) 作为服务器，监听端口
2. 模拟器 (LuaSimulator) 作为客户端，连接到桥接器并发送数据
3. 桥接器接收数据并触发回调
"""

import sys
import time
import json
import gzip
import socket
import threading
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from isaac_bridge import IsaacBridge, DataMessage
from data_replay_system import LuaSimulator, RawMessage


def test_message_callback():
    """测试新的 'message' 回调"""
    print("=" * 70)
    print("测试 DataMessage 回调机制")
    print("=" * 70)

    # 1. 加载录制数据
    session_dir = Path(__file__).parent / "recordings"
    session = "session_20260111_170431"

    messages = []
    for f in sorted(
        [ff for ff in os.listdir(session_dir) if ff.startswith(session) and ff.endswith('.json.gz') and 'chunk' in ff]
    ):
        with gzip.open(session_dir / f, "rt", encoding="utf-8") as fp:
            data = json.load(fp)
            for msg_dict in data.get("messages", []):
                messages.append(RawMessage.from_dict(msg_dict))

    print(f"\n1. 加载了 {len(messages)} 条消息")

    # 2. 创建统计变量
    stats = {
        "message_callback_count": 0,
        "data_callback_count": 0,
        "event_callback_count": 0,
        "samples": [],
    }

    # 3. 端口设置
    listen_port = 9532  # 桥接器监听端口

    # 创建桥接器作为服务器
    bridge = IsaacBridge(host="127.0.0.1", port=listen_port)

    # 注册新回调
    @bridge.on("message")
    def on_message(msg: DataMessage):
        stats["message_callback_count"] += 1
        if len(stats["samples"]) < 5:
            stats["samples"].append({
                "type": msg.msg_type,
                "frame": msg.frame,
                "room_index": msg.room_index,
                "channels": msg.channels,
                "payload_keys": list(msg.payload.keys()) if msg.payload else [],
            })

    # 向后兼容的回调
    @bridge.on("data")
    def on_data(payload):
        stats["data_callback_count"] += 1

    @bridge.on("event")
    def on_event(event):
        stats["event_callback_count"] += 1

    # 4. 启动桥接器服务器
    print(f"2. 启动桥接器服务器 (端口 {listen_port})...")
    bridge.start()
    time.sleep(0.5)

    # 5. 创建客户端线程（模拟游戏发送数据到桥接器）
    received_messages = []
    client_connected = threading.Event()

    def game_client_thread():
        """模拟游戏客户端，连接到桥接器并发送数据"""
        time.sleep(0.3)
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(5)
        try:
            client.connect(("127.0.0.1", listen_port))
            client_connected.set()
            
            # 发送录制数据
            for i, msg in enumerate(messages[:100]):  # 只发送前100条
                if i >= 50:  # 限制数量
                    break
                json_line = msg.to_json_line()
                client.send(json_line.encode("utf-8"))
                received_messages.append(json.loads(json_line))
                time.sleep(0.01)  # 模拟帧间隔
                
            time.sleep(0.5)  # 等待处理完成
        except Exception as e:
            print(f"   客户端错误: {e}")
        finally:
            client.close()

    # 6. 启动游戏客户端线程
    print(f"3. 启动模拟客户端，发送录制数据...")
    game_thread = threading.Thread(target=game_client_thread)
    game_thread.start()
    
    # 等待连接和数据传输
    client_connected.wait(timeout=3)
    game_thread.join(timeout=10)
    
    bridge.stop()

    # 7. 验证结果
    print(f"\n4. 测试结果:")
    print(f"   发送的消息数: {len(received_messages)}")
    print(f"   'message' 回调触发次数: {stats['message_callback_count']}")
    print(f"   'data' 回调触发次数: {stats['data_callback_count']}")

    print(f"\n5. 消息样例:")
    for i, sample in enumerate(stats["samples"][:3]):
        print(f"   样例 {i + 1}:")
        print(f"     类型: {sample['type']}")
        print(f"     帧号: {sample['frame']}")
        print(f"     房间: {sample['room_index']}")
        print(f"     通道数: {len(sample['channels']) if sample['channels'] else 0}")
        if sample['payload_keys']:
            print(f"     Payload 键: {sample['payload_keys'][:5]}...")

    # 8. 验证
    print(f"\n6. 验证结果:")
    success = True

    if stats["message_callback_count"] > 0:
        print("   ✅ 'message' 回调正常工作")
    else:
        print("   ❌ 'message' 回调未触发")
        success = False

    if stats["data_callback_count"] > 0:
        print("   ✅ 'data' 回调（向后兼容）正常工作")
    else:
        print("   ❌ 'data' 回调未触发")
        success = False

    if len(received_messages) > 0:
        print("   ✅ 数据传输正常工作")
        sample = received_messages[0]
        if sample.get("payload") is not None:
            print("   ✅ 发送数据包含完整的 payload")
        else:
            print("   ❌ 发送数据缺少 payload")
            success = False
        if sample.get("channels") is not None:
            print("   ✅ 发送数据包含完整的 channels")
        else:
            print("   ❌ 发送数据缺少 channels")
            success = False
    else:
        print("   ❌ 没有发送数据")
        success = False

    print(f"\n{'=' * 70}")
    if success:
        print("✅ 测试通过！DataMessage 回调机制工作正常")
    else:
        print("❌ 测试失败")
    print(f"{'=' * 70}")

    return success


if __name__ == "__main__":
    success = test_message_callback()
    sys.exit(0 if success else 1)
