"""
Phase 3 Services Test - 服务层测试

测试监控器、处理器和门面功能。
"""

import sys
from pathlib import Path

# 兼容 Windows 和 Linux
sys.path.insert(0, str(Path(__file__).parent))

from services.monitor import DataQualityMonitor, ProblemSource
from services.processor import DataProcessor
from services.facade import SocketBridgeFacade, BridgeConfig
from channels.base import ChannelRegistry


def test_monitor():
    """测试监控器"""
    print("=" * 60)
    print("Phase 3 Services Test - Monitor")
    print("=" * 60)

    monitor = DataQualityMonitor()

    test_msg = {
        "version": "2.1",
        "type": "DATA",
        "frame": 100,
        "seq": 1,
        "game_time": 123456789000,
        "prev_frame": 99,
        "channel_meta": {
            "PLAYER_POSITION": {
                "collect_frame": 100,
                "collect_time": 123456789000,
                "interval": "HIGH",
                "stale_frames": 0,
            }
        },
        "payload": {
            "PLAYER_POSITION": {
                "1": {
                    "pos": {"x": 320.0, "y": 240.0},
                    "vel": {"x": 5.0, "y": -2.0},
                    "move_dir": 3,
                    "fire_dir": 2,
                    "head_dir": 0,
                    "aim_dir": {"x": 1.0, "y": 0.0},
                }
            },
            "PLAYER_STATS": {
                "1": {
                    "player_type": 0,
                    "damage": 3.5,
                    "speed": 1.0,
                    "tears": 10.0,
                    "range": 300.0,
                    "shot_speed": 1.0,
                    "luck": 0,
                    "can_fly": False,
                    "size": 10.0,
                }
            },
        },
        "channels": ["PLAYER_POSITION", "PLAYER_STATS"],
    }

    stats = monitor.process_message(test_msg, test_msg["payload"], 100)

    print(f"\n✅ Monitor created and processed message")
    print(f"   Total messages: {stats.total_messages}")
    print(f"   Total issues: {stats.total_issues}")
    print(f"   Issue rate: {stats.issue_rate:.2%}")

    summary = monitor.get_issue_summary()
    print(f"\n✅ Issue summary:")
    print(f"   By severity: {summary['by_severity']}")
    print(f"   By source: {summary['by_source']}")

    report = monitor.generate_report()
    print(f"\n✅ Report generated ({len(report)} chars)")

    return True


def test_processor():
    """测试处理器"""
    print("\n" + "=" * 60)
    print("Phase 3 Services Test - Processor")
    print("=" * 60)

    processor = DataProcessor()

    all_channels = processor.get_all_channels()
    print(f"\n✅ Processor initialized with {len(all_channels)} channels:")
    for ch in sorted(all_channels):
        print(f"   - {ch}")

    test_msg = {
        "version": "2.1",
        "type": "DATA",
        "frame": 200,
        "seq": 2,
        "game_time": 123456790000,
        "prev_frame": 199,
        "channel_meta": {
            "PLAYER_POSITION": {
                "collect_frame": 200,
                "collect_time": 123456790000,
                "interval": "HIGH",
                "stale_frames": 0,
            }
        },
        "payload": {
            "PLAYER_POSITION": {
                "1": {
                    "pos": {"x": 350.0, "y": 280.0},
                    "vel": {"x": 0.0, "y": 0.0},
                    "move_dir": 0,
                    "fire_dir": 4,
                    "head_dir": 1,
                    "aim_dir": {"x": 0.0, "y": -1.0},
                }
            },
        },
        "channels": ["PLAYER_POSITION"],
    }

    results = processor.process_message(test_msg)
    print(f"\n✅ Processed message with {len(results)} channels")

    player_pos = processor.get_player_position()
    print(f"   Player position: {player_pos}")

    is_fresh = processor.is_fresh("PLAYER_POSITION")
    print(f"   Is fresh: {is_fresh}")

    stats = processor.get_stats()
    print(f"\n✅ Processor stats:")
    print(f"   Message count: {stats['message_count']}")
    print(f"   Fresh channels: {stats['fresh_channels']}/{stats['total_channels']}")

    return True


def test_facade():
    """测试门面"""
    print("\n" + "=" * 60)
    print("Phase 3 Services Test - Facade")
    print("=" * 60)

    config = BridgeConfig(host="127.0.0.1", port=9527, monitoring_enabled=True)
    facade = SocketBridgeFacade(config)

    issues_received = []

    def on_issue(issue):
        issues_received.append(issue)

    facade.on("issue", on_issue)
    facade.on("frame", lambda frame, data: None)

    print(f"\n✅ Facade created with config:")
    print(f"   Host: {config.host}")
    print(f"   Port: {config.port}")
    print(f"   Validation: {config.validation_enabled}")
    print(f"   Monitoring: {config.monitoring_enabled}")

    test_msg = {
        "version": "2.1",
        "type": "DATA",
        "frame": 300,
        "seq": 3,
        "game_time": 123456791000,
        "prev_frame": 299,
        "channel_meta": {
            "PLAYER_POSITION": {
                "collect_frame": 300,
                "collect_time": 123456791000,
                "interval": "HIGH",
                "stale_frames": 0,
            }
        },
        "payload": {
            "PLAYER_POSITION": {
                "1": {
                    "pos": {"x": 400.0, "y": 300.0},
                    "vel": {"x": 2.0, "y": 1.0},
                    "move_dir": 2,
                    "fire_dir": 2,
                    "head_dir": 1,
                    "aim_dir": {"x": 1.0, "y": 0.0},
                }
            },
        },
        "channels": ["PLAYER_POSITION"],
    }

    results = facade.process_message(test_msg)
    print(f"\n✅ Processed message: {len(results)} channels")

    pos = facade.get_player_position()
    print(f"   Get player position: {pos}")

    channels = facade.get_all_channels()
    print(f"   All channels: {len(channels)}")

    fresh = facade.is_channel_fresh("PLAYER_POSITION")
    print(f"   Is fresh: {fresh}")

    stats = facade.get_stats()
    print(f"\n✅ Facade stats:")
    print(f"   Last frame: {stats['last_frame']}")
    print(f"   Last room: {stats['last_room']}")

    report = facade.get_quality_report()
    print(f"\n✅ Quality report generated ({len(report)} chars)")

    return True


def main():
    success = True
    success = test_monitor() and success
    success = test_processor() and success
    success = test_facade() and success

    print("\n" + "=" * 60)
    if success:
        print("🎉 Phase 3 Services Test: PASSED")
    else:
        print("💥 Phase 3 Services Test: FAILED")
    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
