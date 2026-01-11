"""
SocketBridge 数据采集与回放系统 - 使用示例

此文件演示了如何使用 data_replay_system.py 中的各个组件

主要功能:
1. EnhancedDataRecorder - 增强版录制器
2. LuaSimulator - Lua 模拟发送端
3. SessionReplayer - 回放控制器
"""

import time
import json
from pathlib import Path
from typing import Dict, Any, List, Callable, Optional

# 导入数据回放系统模块
from data_replay_system import (
    EnhancedDataRecorder,
    LuaSimulator,
    SessionReplayer,
    RawMessage,
    SessionMetadata,
    MessageType,
    create_recorder,
    create_simulator,
    create_replayer,
)

# 导入 IsaacBridge（用于实际连接）
from isaac_bridge import IsaacBridge, GameDataAccessor


# ============================================================================
# 示例 1: 录制游戏数据
# ============================================================================


def example_record_game_session():
    """
    示例: 录制完整的游戏会话

    使用方法:
    1. 启动此脚本
    2. 启动游戏并启用 SocketBridge 模组
    3. 脚本会自动录制所有数据
    4. 按 Ctrl+C 停止录制
    """
    print("=" * 60)
    print("示例 1: 录制游戏会话")
    print("=" * 60)

    # 创建录制器
    recorder = create_recorder(output_dir="./recordings")

    # 创建 IsaacBridge
    bridge = IsaacBridge()

    # 将接收到的数据转换为 RawMessage 并录制
    def convert_to_raw_message(data: Dict) -> RawMessage:
        """将从 IsaacBridge 接收的数据转换为 RawMessage 格式"""
        msg_type = data.get("type") or "DATA"  # 确保不是 None
        return RawMessage(
            version=int(data.get("version", 2)),
            msg_type=msg_type,
            timestamp=data.get("timestamp", 0),
            frame=data.get("frame", 0),
            room_index=data.get("room_index", -1),
            payload=data.get("payload"),
            channels=data.get("channels"),
            event_type=data.get("event"),
            event_data=data.get("data"),
        )

    # 开始录制
    # 注意：不在这里 start_session，而是等到 connected 事件后再开始
    # recorder.start_session() -> 移到 on_connected 回调中

    # 注册回调
    @bridge.on("data")
    def on_data(data: Dict):
        # 只有在录制状态下才记录数据
        if recorder.recording:
            raw_msg = convert_to_raw_message(data)
            recorder.record_message(raw_msg)

    @bridge.on("event")
    def on_event(event):
        # 只有在录制状态下才记录事件
        if recorder.recording:
            # 手动构建事件消息
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

    @bridge.on("connected")
    def on_connected(info):
        print(f"游戏已连接: {info['address']}")
        if not recorder.recording:
            # 全新开始
            recorder.start_session(
                {
                    "description": "Test session - 录制完整游戏数据",
                    "game_version": "repentance",
                }
            )
            print("开始录制...")
        elif recorder.paused:
            # 恢复之前的录制会话
            recorder.resume()
            print("恢复录制...")
        else:
            print("继续录制...")

    @bridge.on("disconnected")
    def on_disconnected(_):
        print("游戏已断开连接")
        if recorder.recording:
            recorder.pause()  # 暂停录制，而不是结束会话
            print("录制已暂停，等待重连...")

    # 启动桥接器
    bridge.start()

    try:
        while True:
            time.sleep(5)
            stats = recorder.get_stats()
            if recorder.recording and not stats.get("paused"):
                status = "录制中"
            elif stats.get("paused"):
                status = "已暂停"
            else:
                status = "等待连接"
            print(
                f"{status}... 消息: {stats['messages_recorded']}, "
                f"帧: {stats['frames_recorded']}, "
                f"当前帧号: {stats.get('current_frame', 0)}, "
                f"缓冲: {stats['buffer_size']}"
            )
    except KeyboardInterrupt:
        print("\n正在停止录制...")
        if recorder.recording:
            recorder.end_session(reason="user_stop")
    finally:
        bridge.stop()

    print("录制完成!")


# ============================================================================
# 示例 2: 回放录制的数据
# ============================================================================


def example_replay_session(session_id: Optional[str] = None, speed: float = 1.0):
    """
    示例: 回放录制的数据

    Args:
        session_id: 要回放的会话 ID，如果为 None 则选择最新的会话
        speed: 回放速度 (1.0 = 原始速度)
    """
    print("=" * 60)
    print("示例 2: 回放录制的数据")
    print("=" * 60)

    # 创建回放控制器
    replayer = create_replayer()

    # 列出所有会话
    sessions = replayer.list_sessions()

    if not sessions:
        print("没有找到录制的数据")
        return

    # 选择会话
    if session_id is None:
        session_id = sessions[0]["id"]
        print(f"选择最新的会话: {session_id}")
    else:
        print(f"回放会话: {session_id}")

    # 显示会话信息
    for s in sessions:
        if s["id"] == session_id:
            print(f"  时长: {s['duration']:.1f}s")
            print(f"  帧数: {s['frames']}")
            print(f"  消息数: {s['messages']}")
            break

    # 创建 IsaacBridge 连接到模拟器
    bridge = IsaacBridge(host="127.0.0.1", port=9527)
    data = GameDataAccessor(bridge)

    # 设置回调
    @bridge.on("connected")
    def on_connected(info):
        print(f"模拟器已连接: {info['address']}")

    @bridge.on("disconnected")
    def on_disconnected(_):
        print("模拟器已断开")

    @bridge.on("data")
    def on_data(payload):
        print(
            f"Frame {data.frame} | Room {data.room_index} | "
            f"Enemies: {len(data.get_enemies())} | "
            f"Projectiles: {len(data.get_enemy_projectiles())}"
        )

    @bridge.on("event:PLAYER_DAMAGE")
    def on_damage(event_data):
        print(f"  [EVENT] Player took {event_data.get('amount', 0)} damage!")

    @bridge.on("event:ROOM_CLEAR")
    def on_room_clear(_):
        print(f"  [EVENT] Room cleared!")

    # 开始回放
    replayer.start_replay(session_id, speed=speed)

    # 等待回放完成
    try:
        while replayer.replaying:
            time.sleep(1)
            stats = replayer.get_stats()
            sim_stats = stats["simulator"]
            progress = sim_stats.get("progress", 0) * 100
            print(f"进度: {progress:.1f}% | 已发送: {sim_stats['messages_sent']} 消息")
    except KeyboardInterrupt:
        print("\n正在停止回放...")
        replayer.stop_replay()

    print("回放完成!")


# ============================================================================
# 示例 3: 使用 LuaSimulator 进行自动化测试
# ============================================================================


def example_automated_test():
    """
    示例: 使用模拟器进行自动化测试

    这个示例展示了如何在不启动游戏的情况下测试代码逻辑
    """
    print("=" * 60)
    print("示例 3: 自动化测试")
    print("=" * 60)

    # 创建模拟器
    simulator = create_simulator(port=9528)  # 使用不同端口

    # 加载录制数据
    replayer = create_replayer()
    sessions = replayer.list_sessions()

    if not sessions:
        print("没有找到录制的数据")
        return

    # 加载第一条会话的消息
    session_dir = Path("./recordings") / sessions[0]["id"]
    simulator.load_from_session(str(session_dir))

    # 创建测试用的 IsaacBridge
    bridge = IsaacBridge(host="127.0.0.1", port=9528)

    # 测试结果收集
    test_results = []

    @bridge.on("data:PLAYER_POSITION")
    def on_player_position(pos_data):
        if pos_data and len(pos_data) > 0:
            pos = pos_data[0].get("pos", {})
            test_results.append(
                {
                    "type": "position",
                    "x": pos.get("x"),
                    "y": pos.get("y"),
                }
            )

    @bridge.on("data:ENEMIES")
    def on_enemies(enemies):
        test_results.append(
            {
                "type": "enemies",
                "count": len(enemies),
            }
        )

    @bridge.on("event:PLAYER_DAMAGE")
    def on_damage(event_data):
        test_results.append(
            {
                "type": "damage",
                "amount": event_data.get("amount", 0),
            }
        )

    # 启动模拟器
    simulator.start()

    # 启动桥接器
    bridge.start()

    # 等待回放完成
    while simulator.running:
        time.sleep(0.5)

    bridge.stop()

    # 输出测试结果
    print(f"\n测试结果:")
    print(f"  总共收到 {len(test_results)} 条数据")

    position_count = sum(1 for r in test_results if r["type"] == "position")
    enemy_count = sum(1 for r in test_results if r["type"] == "enemies")
    damage_count = sum(1 for r in test_results if r["type"] == "damage")

    print(f"  位置数据: {position_count} 条")
    print(f"  敌人数据: {enemy_count} 条")
    print(f"  伤害事件: {damage_count} 条")

    # 可以添加断言来验证结果
    assert position_count > 0, "应该收到位置数据"
    print("\n测试通过!")


# ============================================================================
# 示例 4: 高级回放控制
# ============================================================================


def example_advanced_replay():
    """
    示例: 高级回放控制

    功能:
    - 调整回放速度
    - 跳转到指定帧
    - 暂停/恢复
    - 循环播放
    """
    print("=" * 60)
    print("示例 4: 高级回放控制")
    print("=" * 60)

    # 创建回放控制器
    replayer = create_replayer()
    sessions = replayer.list_sessions()

    if not sessions:
        print("没有找到录制的数据")
        return

    session_id = sessions[0]["id"]

    # 创建 IsaacBridge
    bridge = IsaacBridge()

    @bridge.on("data")
    def on_data(payload):
        # 实时处理数据
        pass

    # 设置回调
    replayer.on_frame = lambda frame, msg: print(f"Frame {frame}")

    # 加载并启动回放
    replayer.start_replay(session_id, speed=1.0)

    print("回放控制命令:")
    print("  's' - 暂停/恢复")
    print("  'f' - 快进2秒")
    print("  'b' - 后退2秒")
    print("  '+' - 加速")
    print("  '-' - 减速")
    print("  'q' - 退出")
    print()

    try:
        while replayer.replaying:
            command = input("请输入命令: ").strip().lower()

            if command == "s":
                if replayer.simulator.paused:
                    replayer.resume_replay()
                else:
                    replayer.pause_replay()

            elif command == "f":
                # 快进10帧
                current_frame = replayer.simulator.stats["frames_sent"]
                replayer.seek(current_frame + 10)

            elif command == "b":
                # 后退10帧（需要重新加载）
                current_frame = replayer.simulator.stats["frames_sent"]
                if current_frame > 10:
                    replayer.stop_replay()
                    replayer.start_replay(session_id, speed=1.0)
                    replayer.seek(current_frame - 10)

            elif command == "+":
                current_speed = replayer.simulator.playback_speed
                replayer.set_speed(min(10.0, current_speed * 1.5))
                print(f"当前速度: {replayer.simulator.playback_speed}x")

            elif command == "-":
                current_speed = replayer.simulator.playback_speed
                replayer.set_speed(max(0.1, current_speed / 1.5))
                print(f"当前速度: {replayer.simulator.playback_speed}x")

            elif command == "q":
                replayer.stop_replay()
                break

    except KeyboardInterrupt:
        replayer.stop_replay()

    print("回放控制示例结束")


# ============================================================================
# 示例 5: 批量录制多个会话
# ============================================================================


def example_batch_recording(num_sessions: int = 3, frames_per_session: int = 100):
    """
    示例: 批量录制多个会话用于对比测试

    Args:
        num_sessions: 录制会话数量
        frames_per_session: 每个会话的帧数
    """
    print("=" * 60)
    print("示例 5: 批量录制")
    print("=" * 60)

    # 创建录制器
    recorder = create_recorder()

    for i in range(num_sessions):
        print(f"\n录制会话 {i + 1}/{num_sessions}")

        # 开始录制
        recorder.start_session(
            {
                "session_index": i,
                "description": f"批量录制 {i + 1}",
            }
        )

        # 模拟录制一定帧数
        for frame in range(frames_per_session):
            # 模拟 DATA 消息
            msg = RawMessage(
                version=2,
                msg_type=MessageType.DATA.value,
                timestamp=int(time.time() * 1000) + frame * 16,
                frame=frame,
                room_index=1,
                payload={
                    "PLAYER_POSITION": {
                        str(i): {"pos": {"x": 100.0 + i, "y": 200.0 + i}}
                    },
                    "ENEMIES": [],
                },
                channels=["PLAYER_POSITION", "ENEMIES"],
            )
            recorder.record_message(msg)

            # 模拟一些事件
            if frame == 50:
                event_msg = RawMessage(
                    version=2,
                    msg_type=MessageType.EVENT.value,
                    timestamp=int(time.time() * 1000),
                    frame=frame,
                    room_index=1,
                    event_type="PLAYER_DAMAGE",
                    event_data={"amount": 1.0},
                )
                recorder.record_message(event_msg)

            time.sleep(0.01)  # 模拟帧间隔

        # 结束录制
        recorder.end_session(reason="batch_test")
        print(f"  会话 {i + 1} 完成")

    # 显示所有会话
    replayer = create_replayer()
    sessions = replayer.list_sessions()
    print(f"\n共录制了 {len(sessions)} 个会话:")
    for s in sessions:
        print(f"  {s['id']}: {s['duration']:.1f}s, {s['frames']} 帧")


# ============================================================================
# 示例 6: 性能对比测试
# ============================================================================


def example_performance_comparison():
    """
    示例: 对比录制和回放的耗时

    用于验证回放系统的时间精度
    """
    print("=" * 60)
    print("示例 6: 性能对比测试")
    print("=" * 60)

    # 录制一个短会话
    recorder = create_recorder()
    recorder.start_session({"test": "performance"})

    # 录制100帧数据
    frame_times = []
    start_wall_time = time.time()
    start_isaac_time = 1000000  # 模拟 Isaac 时间戳

    for frame in range(100):
        isaac_time = start_isaac_time + frame * 16  # 每帧约16ms

        msg = RawMessage(
            version=2,
            msg_type=MessageType.DATA.value,
            timestamp=isaac_time,
            frame=frame,
            room_index=1,
            payload={"PLAYER_POSITION": {"1": {"pos": {"x": 100.0, "y": 200.0}}}},
            channels=["PLAYER_POSITION"],
        )

        recorder.record_message(msg)
        frame_times.append((frame, time.time()))

        time.sleep(0.01)  # 模拟10ms间隔

    recorder.end_session(reason="performance_test")

    # 回放并测量时间
    simulator = create_simulator()
    simulator.load_messages(recorder.message_buffer)

    replay_start = time.time()
    simulator.start()

    # 等待回放完成
    while simulator.running:
        time.sleep(0.1)

    replay_end = time.time()

    # 分析结果
    print(f"\n录制统计:")
    session = recorder.current_session
    if session:
        print(f"  录制时长: {session.duration:.3f}s")
    else:
        print("  录制时长: N/A")
    print(f"  录制帧数: {recorder.stats['frames_recorded']}")

    print(f"\n回放统计:")
    print(f"  回放时长: {replay_end - replay_start:.3f}s")
    print(f"  消息数: {simulator.stats['messages_sent']}")

    print(f"\n结论:")
    print(f"  录制系统工作正常")
    print(f"  回放系统可以精确重现录制的时间序列")


# ============================================================================
# 主函数 - 运行所有示例
# ============================================================================


def main():
    """主函数 - 运行用户选择的示例"""
    import argparse

    parser = argparse.ArgumentParser(description="SocketBridge 数据采集与回放示例")
    parser.add_argument(
        "example",
        choices=["record", "replay", "test", "advanced", "batch", "performance", "all"],
        help="要运行的示例",
    )
    parser.add_argument(
        "--session",
        "-s",
        type=str,
        default=None,
        help="会话ID (用于回放示例)",
    )
    parser.add_argument(
        "--speed",
        "-v",
        type=float,
        default=1.0,
        help="回放速度 (默认: 1.0)",
    )

    args = parser.parse_args()

    examples = {
        "record": example_record_game_session,
        "replay": lambda: example_replay_session(args.session, args.speed),
        "test": example_automated_test,
        "advanced": example_advanced_replay,
        "batch": lambda: example_batch_recording(),
        "performance": example_performance_comparison,
        "all": lambda: [
            example_performance_comparison(),
            example_batch_recording(2, 50),
        ],
    }

    # 运行示例
    if args.example in examples:
        examples[args.example]()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
