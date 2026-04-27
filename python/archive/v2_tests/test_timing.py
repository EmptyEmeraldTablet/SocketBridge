"""
Timing Tests - 时序模块测试

测试内容：
1. 时序信息解析
2. 时序问题检测
3. 时序感知状态管理
4. 通道同步快照
"""

import pytest
import json
from pathlib import Path

# 添加路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.protocol.timing import (
    TimingIssueType,
    ChannelTimingInfo,
    MessageTimingInfo,
    TimingIssue,
    TimingMonitor,
)
from models.state import TimingAwareStateManager, ChannelState


# ==================== Fixtures ====================

@pytest.fixture
def sample_data():
    """加载测试数据"""
    fixtures_path = Path(__file__).parent / "fixtures" / "sample_messages.json"
    with open(fixtures_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def timing_monitor():
    """创建时序监控器"""
    return TimingMonitor()


@pytest.fixture
def state_manager():
    """创建状态管理器"""
    return TimingAwareStateManager(max_history=100)


# ==================== Channel Timing Info Tests ====================

class TestChannelTimingInfo:
    """通道时序信息测试"""
    
    def test_creation(self):
        """测试创建"""
        info = ChannelTimingInfo(
            channel="TEST",
            collect_frame=100,
            collect_time=12345,
            interval="HIGH",
            stale_frames=0,
        )
        assert info.channel == "TEST"
        assert info.collect_frame == 100
    
    def test_is_stale_high_frequency(self):
        """测试高频通道过期判断"""
        # HIGH 频率阈值 = 1 * 2 = 2 帧
        fresh = ChannelTimingInfo(
            channel="TEST",
            collect_frame=100,
            collect_time=12345,
            interval="HIGH",
            stale_frames=1,
        )
        assert not fresh.is_stale
        
        stale = ChannelTimingInfo(
            channel="TEST",
            collect_frame=100,
            collect_time=12345,
            interval="HIGH",
            stale_frames=5,
        )
        assert stale.is_stale
    
    def test_is_stale_low_frequency(self):
        """测试低频通道过期判断"""
        # LOW 频率阈值 = 30 * 2 = 60 帧
        fresh = ChannelTimingInfo(
            channel="TEST",
            collect_frame=100,
            collect_time=12345,
            interval="LOW",
            stale_frames=50,
        )
        assert not fresh.is_stale
        
        stale = ChannelTimingInfo(
            channel="TEST",
            collect_frame=100,
            collect_time=12345,
            interval="LOW",
            stale_frames=70,
        )
        assert stale.is_stale


# ==================== Message Timing Info Tests ====================

class TestMessageTimingInfo:
    """消息时序信息测试"""
    
    def test_from_message_v21(self, sample_data):
        """测试从 v2.1 消息解析"""
        msg = sample_data["data_message_v21"]
        timing = MessageTimingInfo.from_message(msg)
        
        assert timing.seq == 50
        assert timing.frame == 100
        assert timing.prev_frame == 99
        assert "PLAYER_POSITION" in timing.channel_meta
    
    def test_from_message_v20(self, sample_data):
        """测试从 v2.0 消息解析（兼容）"""
        msg = sample_data["data_message_v20"]
        timing = MessageTimingInfo.from_message(msg)
        
        assert timing.seq == 0  # 默认值
        assert timing.frame == 100
        assert len(timing.channel_meta) == 0  # 无通道元数据


# ==================== Timing Monitor Tests ====================

class TestTimingMonitor:
    """时序监控器测试"""
    
    def test_initial_state(self, timing_monitor):
        """测试初始状态"""
        assert timing_monitor.last_seq == 0
        assert timing_monitor.last_frame == 0
        assert timing_monitor.total_messages == 0
    
    def test_check_normal_sequence(self, timing_monitor):
        """测试正常序列无问题"""
        for i in range(1, 11):
            timing = MessageTimingInfo(
                seq=i,
                frame=i * 2,
                game_time=i * 100,
                prev_frame=(i - 1) * 2,
            )
            issues = timing_monitor.check_message(timing)
            # 正常序列不应有严重问题
            errors = [
                issue for issue in issues
                if issue.severity == "error"
            ]
            assert len(errors) == 0
        
        assert timing_monitor.total_messages == 10
    
    def test_detect_out_of_order(self, timing_monitor):
        """测试检测乱序"""
        # 正常消息
        timing1 = MessageTimingInfo(seq=5, frame=10, game_time=1000, prev_frame=9)
        timing_monitor.check_message(timing1)
        
        # 乱序消息（seq 回退）
        timing2 = MessageTimingInfo(seq=3, frame=6, game_time=600, prev_frame=5)
        issues = timing_monitor.check_message(timing2)
        
        issue_types = [i.issue_type for i in issues]
        assert TimingIssueType.OUT_OF_ORDER in issue_types
    
    def test_detect_frame_gap(self, timing_monitor):
        """测试检测序列号间隙"""
        timing1 = MessageTimingInfo(seq=1, frame=2, game_time=100, prev_frame=1)
        timing_monitor.check_message(timing1)
        
        # 跳过 seq 2, 3, 4
        timing2 = MessageTimingInfo(seq=5, frame=10, game_time=500, prev_frame=9)
        issues = timing_monitor.check_message(timing2)
        
        gap_issues = [i for i in issues if i.issue_type == TimingIssueType.FRAME_GAP]
        assert len(gap_issues) == 1
        assert gap_issues[0].details["missing_count"] == 3
    
    def test_detect_frame_jump(self, timing_monitor):
        """测试检测帧跳跃"""
        timing1 = MessageTimingInfo(seq=1, frame=10, game_time=100, prev_frame=9)
        timing_monitor.check_message(timing1)
        
        # 帧跳跃超过 5
        timing2 = MessageTimingInfo(seq=2, frame=30, game_time=300, prev_frame=29)
        issues = timing_monitor.check_message(timing2)
        
        jump_issues = [i for i in issues if i.issue_type == TimingIssueType.FRAME_JUMP]
        assert len(jump_issues) == 1
        assert jump_issues[0].details["frame_gap"] == 20
    
    def test_detect_stale_data(self, timing_monitor):
        """测试检测过期数据"""
        timing = MessageTimingInfo(
            seq=1,
            frame=100,
            game_time=1000,
            prev_frame=99,
            channel_meta={
                "STALE_CHANNEL": ChannelTimingInfo(
                    channel="STALE_CHANNEL",
                    collect_frame=50,
                    collect_time=500,
                    interval="HIGH",
                    stale_frames=50,  # 远超阈值
                )
            }
        )
        issues = timing_monitor.check_message(timing)
        
        stale_issues = [i for i in issues if i.issue_type == TimingIssueType.STALE_DATA]
        assert len(stale_issues) == 1
    
    def test_get_stats(self, timing_monitor):
        """测试获取统计"""
        # 添加一些消息
        for i in range(1, 6):
            timing = MessageTimingInfo(seq=i, frame=i, game_time=i * 100, prev_frame=i - 1)
            timing_monitor.check_message(timing)
        
        stats = timing_monitor.get_stats()
        assert stats["total_messages"] == 5
        assert "frame_gaps" in stats
        assert "out_of_order" in stats
        assert "issue_rate" in stats


# ==================== Timing Aware State Manager Tests ====================

class TestTimingAwareStateManager:
    """时序感知状态管理器测试"""
    
    def test_update_channel(self, state_manager):
        """测试更新通道"""
        timing = ChannelTimingInfo(
            channel="TEST",
            collect_frame=100,
            collect_time=12345,
            interval="HIGH",
            stale_frames=0,
        )
        
        state_manager.update_channel("TEST", {"value": 42}, timing, current_frame=100)
        
        state = state_manager.get_channel("TEST")
        assert state is not None
        assert state.data["value"] == 42
        assert state.collect_frame == 100
    
    def test_get_channel_data(self, state_manager):
        """测试获取通道数据"""
        timing = ChannelTimingInfo(
            channel="TEST",
            collect_frame=100,
            collect_time=12345,
            interval="HIGH",
            stale_frames=0,
        )
        
        state_manager.update_channel("TEST", {"value": 42}, timing, current_frame=100)
        
        data = state_manager.get_channel_data("TEST")
        assert data["value"] == 42
    
    def test_is_channel_fresh(self, state_manager):
        """测试通道新鲜度"""
        timing = ChannelTimingInfo(
            channel="TEST",
            collect_frame=100,
            collect_time=12345,
            interval="HIGH",
            stale_frames=0,
        )
        
        state_manager.update_channel("TEST", {"value": 42}, timing, current_frame=100)
        
        # 新鲜
        assert state_manager.is_channel_fresh("TEST", max_stale_frames=5)
        
        # 模拟时间流逝
        state_manager.current_frame = 110
        assert not state_manager.is_channel_fresh("TEST", max_stale_frames=5)
    
    def test_get_channel_age(self, state_manager):
        """测试获取通道年龄"""
        timing = ChannelTimingInfo(
            channel="TEST",
            collect_frame=100,
            collect_time=12345,
            interval="HIGH",
            stale_frames=0,
        )
        
        state_manager.update_channel("TEST", {"value": 42}, timing, current_frame=100)
        state_manager.current_frame = 115
        
        age = state_manager.get_channel_age("TEST")
        assert age == 15
    
    def test_get_synchronized_snapshot(self, state_manager):
        """测试获取同步快照"""
        # 添加两个同步的通道
        timing1 = ChannelTimingInfo(
            channel="CHANNEL_A",
            collect_frame=100,
            collect_time=12345,
            interval="HIGH",
            stale_frames=0,
        )
        timing2 = ChannelTimingInfo(
            channel="CHANNEL_B",
            collect_frame=102,
            collect_time=12350,
            interval="HIGH",
            stale_frames=0,
        )
        
        state_manager.update_channel("CHANNEL_A", {"a": 1}, timing1, current_frame=100)
        state_manager.update_channel("CHANNEL_B", {"b": 2}, timing2, current_frame=102)
        
        # 帧差 2，在阈值 5 内
        snapshot = state_manager.get_synchronized_snapshot(
            ["CHANNEL_A", "CHANNEL_B"], max_frame_diff=5
        )
        assert snapshot is not None
        assert snapshot["CHANNEL_A"]["a"] == 1
        assert snapshot["CHANNEL_B"]["b"] == 2
    
    def test_get_synchronized_snapshot_fails_for_desync(self, state_manager):
        """测试不同步时快照失败"""
        timing1 = ChannelTimingInfo(
            channel="CHANNEL_A",
            collect_frame=100,
            collect_time=12345,
            interval="HIGH",
            stale_frames=0,
        )
        timing2 = ChannelTimingInfo(
            channel="CHANNEL_B",
            collect_frame=120,  # 差距 20 帧
            collect_time=12500,
            interval="HIGH",
            stale_frames=0,
        )
        
        state_manager.update_channel("CHANNEL_A", {"a": 1}, timing1, current_frame=100)
        state_manager.update_channel("CHANNEL_B", {"b": 2}, timing2, current_frame=120)
        
        # 帧差 20，超过阈值 5
        snapshot = state_manager.get_synchronized_snapshot(
            ["CHANNEL_A", "CHANNEL_B"], max_frame_diff=5
        )
        assert snapshot is None
    
    def test_history_storage(self, state_manager):
        """测试历史存储"""
        timing = ChannelTimingInfo(
            channel="TEST",
            collect_frame=100,
            collect_time=12345,
            interval="HIGH",
            stale_frames=0,
        )
        
        # 添加多个状态
        for i in range(10):
            timing.collect_frame = 100 + i
            state_manager.update_channel("TEST", {"frame": 100 + i}, timing, current_frame=100 + i)
        
        assert len(state_manager.history["TEST"]) == 10
    
    def test_get_state_at_frame(self, state_manager):
        """测试按帧获取状态"""
        timing = ChannelTimingInfo(
            channel="TEST",
            collect_frame=100,
            collect_time=12345,
            interval="HIGH",
            stale_frames=0,
        )
        
        # 添加多个状态
        for i in range(10):
            t = ChannelTimingInfo(
                channel="TEST",
                collect_frame=100 + i * 5,
                collect_time=12345 + i * 50,
                interval="HIGH",
                stale_frames=0,
            )
            state_manager.update_channel("TEST", {"frame": 100 + i * 5}, t, current_frame=100 + i * 5)
        
        # 获取接近 frame 115 的状态
        data = state_manager.get_state_at_frame("TEST", 115)
        assert data is not None
        assert data["frame"] == 115  # 应该找到 frame=115


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
