"""
调试版录制脚本 - 用于诊断数据录制问题
"""

import sys
import time
import json
from pathlib import Path

# 添加 python 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from isaac_bridge import IsaacBridge
from data_replay_system import (
    create_recorder,
    RawMessage,
    MessageType,
)


def main():
    print("=" * 70)
    print("调试版录制脚本 - 诊断数据录制问题")
    print("=" * 70)

    # 创建录制器
    recorder = create_recorder(output_dir="python/recordings")

    # 统计数据接收
    stats = {
        "data_callbacks": 0,
        "event_callbacks": 0,
        "data_types": {},  # type -> count
        "data_keys": {},  # data.keys() -> count
        "samples": [],  # 前几条数据的样例
    }

    # 创建 IsaacBridge
    bridge = IsaacBridge()

    print("\n[DEBUG] 1. 准备开始录制...")
    print(f"[DEBUG] recorder.recording = {recorder.recording}")

    # 在 on_connected 中开始录制
    @bridge.on("connected")
    def on_connected(info):
        print(f"\n[DEBUG] === connected 事件触发 ===")
        print(f"[DEBUG] address: {info['address']}")
        print(f"[DEBUG] recorder.recording before: {recorder.recording}")

        if not recorder.recording:
            recorder.start_session(
                {
                    "description": "Debug session - 诊断数据录制问题",
                    "game_version": "repentance",
                }
            )
            print(
                f"[DEBUG] recorder.recording after start_session: {recorder.recording}"
            )
            print("[DEBUG] 开始录制...")
        else:
            print("[DEBUG] 恢复录制...")
        print("[DEBUG] === connected 结束 ===\n")

    # 关键：检查 on_data 接收到的数据
    @bridge.on("data")
    def on_data(data):
        stats["data_callbacks"] += 1

        print(f"\n[DEBUG] === data 事件 #{stats['data_callbacks']} ===")
        print(f"[DEBUG] recorder.recording = {recorder.recording}")

        # 详细记录数据类型
        print(f"[DEBUG] data type: {type(data).__name__}")
        print(
            f"[DEBUG] data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict!'}"
        )

        # 记录数据类型分布
        if isinstance(data, dict):
            stats["data_keys"][str(sorted(data.keys()))] = (
                stats["data_keys"].get(str(sorted(data.keys())), 0) + 1
            )

        # 保存前3条样例
        if len(stats["samples"]) < 3:
            stats["samples"].append(
                {
                    "time": time.time(),
                    "type": type(data).__name__,
                    "keys": list(data.keys()) if isinstance(data, dict) else None,
                    "value": data if not isinstance(data, dict) else None,
                    "str": str(data)[:200],
                }
            )

        # 只有在录制状态下才记录
        if recorder.recording:
            print(f"[DEBUG] 开始录制消息...")
            print(f"[DEBUG] data preview: {str(data)[:150]}...")

            try:
                # 尝试直接记录原始数据
                if isinstance(data, dict):
                    raw_msg = RawMessage(
                        version=data.get("version", 2),
                        msg_type=data.get("type", "DATA"),
                        timestamp=data.get("timestamp", 0),
                        frame=data.get("frame", 0),
                        room_index=data.get("room_index", -1),
                        payload=data.get("payload"),
                        channels=data.get("channels"),
                    )
                else:
                    print(f"[DEBUG] ⚠️ data 不是 dict 类型: {type(data)}")
                    raw_msg = RawMessage(
                        version=2,
                        msg_type="DATA",
                        timestamp=int(time.time() * 1000),
                        frame=0,
                        room_index=-1,
                        payload={"raw": str(data)[:1000]},
                        channels=["RAW"],
                    )

                print(f"[DEBUG] 转换后的消息:")
                print(
                    f"  version: {raw_msg.version} (type: {type(raw_msg.version).__name__})"
                )
                print(f"  msg_type: {raw_msg.msg_type}")
                print(f"  timestamp: {raw_msg.timestamp}")
                print(f"  frame: {raw_msg.frame}")
                print(f"  room_index: {raw_msg.room_index}")
                print(f"  payload: {raw_msg.payload}")
                print(f"  channels: {raw_msg.channels}")

                recorder.record_message(raw_msg)
                print(f"[DEBUG] ✅ 消息已录制")

            except Exception as e:
                print(f"[DEBUG] ❌ 录制失败: {e}")
        else:
            print("[DEBUG] 跳过录制 (recording=False)")

        print("[DEBUG] === data 事件结束 ===\n")

    @bridge.on("event")
    def on_event(event):
        stats["event_callbacks"] += 1
        print(f"\n[DEBUG] === event 事件 #{stats['event_callbacks']} ===")
        print(f"[DEBUG] event type: {event.type}")
        print(f"[DEBUG] event frame: {event.frame}")

        if recorder.recording:
            raw_msg = RawMessage(
                version=2,
                msg_type=MessageType.EVENT.value,
                timestamp=int(time.time() * 1000),
                frame=event.frame,
                room_index=-1,
                event_type=event.type,
                event_data=event.data,
            )
            recorder.record_message(raw_msg)
            print(f"[DEBUG] ✅ 事件已录制")
        print("[DEBUG] === event 结束 ===\n")

    @bridge.on("disconnected")
    def on_disconnected(_):
        print(f"\n[DEBUG] === disconnected 事件 ===")
        print(f"[DEBUG] recorder.recording = {recorder.recording}")
        if recorder.recording:
            recorder.pause()
            print("[DEBUG] 录制已暂停")
        print("[DEBUG] === disconnected 结束 ===\n")

    # 启动
    print("\n[DEBUG] 2. 启动 IsaacBridge...")
    bridge.start()

    print("\n[DEBUG] 3. 等待连接和数据...")
    print("=" * 70)

    try:
        while True:
            time.sleep(2)

            # 每5秒输出统计
            if stats["data_callbacks"] > 0 or stats["event_callbacks"] > 0:
                print("\n" + "=" * 70)
                print("[STATS] 当前统计:")
                print(f"  data 回调次数: {stats['data_callbacks']}")
                print(f"  event 回调次数: {stats['event_callbacks']}")
                print(f"  数据结构分布:")
                for key, count in sorted(stats["data_keys"].items()):
                    print(f"    {key}: {count} 次")
                print(f"  录制统计: {recorder.get_stats()}")
                print("=" * 70)

            # 如果有样例数据，输出样例
            if stats["samples"]:
                print("\n[SAMPLE] 数据样例:")
                for i, sample in enumerate(stats["samples"]):
                    print(f"  样例 {i + 1}:")
                    print(f"    类型: {sample['type']}")
                    print(f"    Keys: {sample['keys']}")
                    print(f"    内容: {sample['str'][:100]}...")

    except KeyboardInterrupt:
        print("\n\n[DEBUG] 用户中断，正在停止...")
        if recorder.recording:
            recorder.end_session(reason="user_stop")
        bridge.stop()

        # 最终统计
        print("\n" + "=" * 70)
        print("[FINAL_STATS] 最终统计:")
        print(f"  data 回调总数: {stats['data_callbacks']}")
        print(f"  event 回调总数: {stats['event_callbacks']}")
        print(f"  数据结构分布:")
        for key, count in sorted(stats["data_keys"].items()):
            print(f"    {key}: {count} 次")
        print("=" * 70)


if __name__ == "__main__":
    main()
