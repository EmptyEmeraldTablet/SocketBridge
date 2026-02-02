#!/usr/bin/env python3
"""
简单的回放测试脚本

用法:
    python apps/replay_test.py                    # 测试最新会话
    python apps/replay_test.py --session <id>    # 测试指定会话
    python apps/replay_test.py --count 20        # 显示前20条消息
"""

import sys
import argparse
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.replay import DataReplayer, ReplayerConfig, list_sessions


def main():
    parser = argparse.ArgumentParser(description="简单的回放测试")
    parser.add_argument(
        "--session", "-s",
        help="会话ID（默认使用最新会话）",
    )
    parser.add_argument(
        "--dir", "-d",
        default="./recordings",
        help="录制目录 (默认: ./recordings)",
    )
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=5,
        help="显示的消息数量 (默认: 5)",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="显示所有消息（慎用）",
    )
    args = parser.parse_args()

    # 列出会话
    sessions = list_sessions(args.dir)
    if not sessions:
        print(f"❌ 在 {args.dir} 中没有找到录制会话")
        return 1

    print(f"找到 {len(sessions)} 个会话:")
    for i, s in enumerate(sessions[:5], 1):
        print(f"  {i}. {s.session_id}  时长: {s.duration_formatted}  帧数: {s.total_frames}")
    if len(sessions) > 5:
        print(f"  ... 还有 {len(sessions) - 5} 个会话")

    # 选择会话
    if args.session:
        session_id = args.session
    else:
        session_id = sessions[0].session_id
        print(f"\n使用最新会话: {session_id}")

    # 创建回放器并加载
    config = ReplayerConfig(recordings_dir=args.dir)
    replayer = DataReplayer(config)

    try:
        session = replayer.load_session(session_id)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1

    print(f"\n会话信息:")
    print(f"  总消息数: {session.total_messages}")
    print(f"  总帧数: {session.total_frames}")

    # 显示消息
    count = session.total_messages if args.all else args.count
    print(f"\n前 {count} 条消息:")
    print("-" * 70)

    for i, msg in enumerate(replayer.iter_messages()):
        channels = msg.channels[:4] if msg.channels else []
        channels_str = ", ".join(channels)
        if len(msg.channels or []) > 4:
            channels_str += f" +{len(msg.channels) - 4}"

        print(f"[{i+1:4d}] frame={msg.frame:5d} | type={msg.type:5s} | {channels_str}")

        if i + 1 >= count:
            break

    print("-" * 70)
    print(f"✓ 回放测试完成! 显示了 {min(count, session.total_messages)} 条消息")

    return 0


if __name__ == "__main__":
    sys.exit(main())
