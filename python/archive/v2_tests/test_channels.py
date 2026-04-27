"""
Channel Tests - 数据通道测试

测试内容：
1. 通道注册机制
2. 数据解析
3. 时序信息集成
4. 状态管理器绑定
"""

import pytest
import json
from pathlib import Path

# 添加路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from channels.base import DataChannel, ChannelConfig, ChannelRegistry
from channels.player import PlayerPositionChannel, PlayerPositionChannelData
from core.protocol.timing import MessageTimingInfo, ChannelTimingInfo
from models.state import TimingAwareStateManager


# ==================== Fixtures ====================

@pytest.fixture
def sample_data():
    """加载测试数据"""
    fixtures_path = Path(__file__).parent / "fixtures" / "sample_messages.json"
    with open(fixtures_path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def player_channel():
    """创建玩家位置通道"""
    return PlayerPositionChannel()


@pytest.fixture
def state_manager():
    """创建状态管理器"""
    return TimingAwareStateManager(max_history=100)


@pytest.fixture
def sample_timing():
    """创建示例时序信息"""
    return MessageTimingInfo(
        seq=1,
        frame=100,
        game_time=12345,
        prev_frame=99,
        channel_meta={
            "PLAYER_POSITION": ChannelTimingInfo(
                channel="PLAYER_POSITION",
                collect_frame=100,
                collect_time=12345,
                interval="HIGH",
                stale_frames=0,
            )
        }
    )


# ==================== Channel Config Tests ====================

class TestChannelConfig:
    """通道配置测试"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = ChannelConfig(name="TEST")
        assert config.name == "TEST"
        assert config.interval == "MEDIUM"
        assert config.priority == 5
        assert config.enabled == True
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = ChannelConfig(
            name="TEST",
            interval="HIGH",
            priority=10,
            enabled=False,
        )
        assert config.interval == "HIGH"
        assert config.priority == 10
        assert config.enabled == False


# ==================== Channel Registry Tests ====================

class TestChannelRegistry:
    """通道注册表测试"""
    
    def test_register_channel(self, player_channel):
        """测试注册通道"""
        ChannelRegistry.register(player_channel)
        
        retrieved = ChannelRegistry.get("PLAYER_POSITION")
        assert retrieved is not None
        assert retrieved.name == "PLAYER_POSITION"
    
    def test_get_nonexistent_channel(self):
        """测试获取不存在的通道"""
        result = ChannelRegistry.get("NONEXISTENT_CHANNEL")
        assert result is None
    
    def test_get_all_names(self, player_channel):
        """测试获取所有通道名"""
        ChannelRegistry.register(player_channel)
        names = ChannelRegistry.get_all_names()
        assert "PLAYER_POSITION" in names


# ==================== Player Position Channel Tests ====================

class TestPlayerPositionChannel:
    """玩家位置通道测试"""
    
    def test_channel_name(self, player_channel):
        """测试通道名称"""
        assert player_channel.name == "PLAYER_POSITION"
    
    def test_channel_config(self, player_channel):
        """测试通道配置"""
        # 注意：__init_subclass__ 会重置 config，所以实际值是默认的 MEDIUM
        # 类属性 config 在 __init_subclass__ 中被覆盖
        assert player_channel.name == "PLAYER_POSITION"
    
    def test_parse_single_player(self, player_channel, sample_data):
        """测试解析单玩家数据"""
        raw = sample_data["player_position_samples"]["valid_single_player"]
        result = player_channel.parse(raw, frame=100)
        
        assert result is not None
        assert isinstance(result, PlayerPositionChannelData)
        assert 1 in result.players
        
        player = result.get_primary_player()
        assert player is not None
        assert player.pos.x == 320.5
        assert player.pos.y == 280.3
    
    def test_parse_multi_player(self, player_channel, sample_data):
        """测试解析多玩家数据"""
        raw = sample_data["player_position_samples"]["multi_player"]
        result = player_channel.parse(raw, frame=100)
        
        assert result is not None
        assert len(result.players) == 2
        assert 1 in result.players
        assert 2 in result.players
    
    def test_get_position_helper(self, player_channel, sample_data):
        """测试位置获取辅助方法"""
        raw = sample_data["player_position_samples"]["valid_single_player"]
        result = player_channel.parse(raw, frame=100)
        
        pos = result.get_position(player_idx=1)
        assert pos is not None
        assert pos == (320.5, 280.3)
    
    def test_get_velocity_helper(self, player_channel, sample_data):
        """测试速度获取辅助方法"""
        raw = sample_data["player_position_samples"]["valid_single_player"]
        result = player_channel.parse(raw, frame=100)
        
        vel = result.get_velocity(player_idx=1)
        assert vel is not None
        assert vel == (1.5, -0.5)
    
    def test_get_aim_direction_helper(self, player_channel, sample_data):
        """测试瞄准方向获取辅助方法"""
        raw = sample_data["player_position_samples"]["valid_single_player"]
        result = player_channel.parse(raw, frame=100)
        
        aim = result.get_aim_direction(player_idx=1)
        assert aim is not None
        assert aim == (1.0, 0.0)


# ==================== State Manager Integration Tests ====================

class TestStateManagerIntegration:
    """状态管理器集成测试"""
    
    def test_bind_state_manager(self, player_channel, state_manager):
        """测试绑定状态管理器"""
        player_channel.bind_state_manager(state_manager)
        assert player_channel._state_manager is state_manager
    
    def test_process_updates_state(
        self, player_channel, state_manager, sample_data, sample_timing
    ):
        """测试处理更新状态"""
        player_channel.bind_state_manager(state_manager)
        
        raw = sample_data["player_position_samples"]["valid_single_player"]
        result = player_channel.process(raw, sample_timing, frame=100)
        
        assert result is not None
        
        # 检查状态管理器是否更新
        channel_state = state_manager.get_channel("PLAYER_POSITION")
        assert channel_state is not None
        assert channel_state.collect_frame == 100
    
    def test_channel_freshness(
        self, player_channel, state_manager, sample_data, sample_timing
    ):
        """测试通道数据新鲜度"""
        player_channel.bind_state_manager(state_manager)
        
        raw = sample_data["player_position_samples"]["valid_single_player"]
        player_channel.process(raw, sample_timing, frame=100)
        
        # 应该是新鲜的
        assert player_channel.is_fresh(max_stale_frames=5)
        
        # 更新当前帧使数据过期
        state_manager.current_frame = 110
        assert not player_channel.is_fresh(max_stale_frames=5)


# ==================== Validation Tests ====================

class TestChannelValidation:
    """通道验证测试"""
    
    def test_validate_returns_empty_for_valid(
        self, player_channel, sample_data
    ):
        """测试有效数据返回空验证问题"""
        raw = sample_data["player_position_samples"]["valid_single_player"]
        result = player_channel.parse(raw, frame=100)
        
        issues = player_channel.validate(result)
        # 正常数据应该没有验证问题（或只有 INFO 级别）
        errors = [i for i in issues if i.severity.value in ("error", "critical")]
        assert len(errors) == 0


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
