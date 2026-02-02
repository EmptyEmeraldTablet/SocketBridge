"""
Test Bridge Adapter - 测试连接适配器

验证 BridgeAdapter 的基础功能。
"""

import pytest
import sys
from pathlib import Path

# 确保路径正确
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestAdapterImports:
    """测试适配器模块导入"""
    
    def test_import_from_package(self):
        """测试从包导入"""
        from core.connection import BridgeAdapter, AdapterConfig, create_adapter
        assert BridgeAdapter is not None
        assert AdapterConfig is not None
        assert create_adapter is not None
    
    def test_import_from_adapter(self):
        """测试从模块直接导入"""
        from core.connection.adapter import BridgeAdapter, AdapterConfig, create_adapter
        assert BridgeAdapter is not None


class TestAdapterConfig:
    """测试适配器配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        from core.connection import AdapterConfig
        config = AdapterConfig()
        
        assert config.host == "127.0.0.1"
        assert config.port == 9527
        assert config.validation_enabled is True
        assert config.monitoring_enabled is True
        assert config.auto_reconnect is True
        assert config.log_messages is False
    
    def test_custom_config(self):
        """测试自定义配置"""
        from core.connection import AdapterConfig
        config = AdapterConfig(
            host="0.0.0.0",
            port=8888,
            validation_enabled=False,
            log_messages=True,
        )
        
        assert config.host == "0.0.0.0"
        assert config.port == 8888
        assert config.validation_enabled is False
        assert config.log_messages is True


class TestAdapterCreation:
    """测试适配器创建"""
    
    def test_create_adapter_default(self):
        """测试默认创建"""
        from core.connection import create_adapter
        adapter = create_adapter()
        
        assert adapter is not None
        assert adapter.config.host == "127.0.0.1"
        assert adapter.config.port == 9527
        
        # 验证内部组件
        assert adapter.bridge is not None
        assert adapter.facade is not None
    
    def test_create_adapter_custom(self):
        """测试自定义创建"""
        from core.connection import create_adapter
        adapter = create_adapter(
            host="0.0.0.0",
            port=9999,
            log_messages=True,
        )
        
        assert adapter.config.host == "0.0.0.0"
        assert adapter.config.port == 9999
        assert adapter.config.log_messages is True
    
    def test_adapter_with_config(self):
        """测试使用配置对象创建"""
        from core.connection import BridgeAdapter, AdapterConfig
        
        config = AdapterConfig(port=8080)
        adapter = BridgeAdapter(config)
        
        assert adapter.config.port == 8080


class TestAdapterState:
    """测试适配器状态"""
    
    def test_initial_state(self):
        """测试初始状态"""
        from core.connection import create_adapter
        adapter = create_adapter()
        
        assert adapter.connected is False
        assert adapter.last_frame == 0
        assert adapter.message_count == 0
    
    def test_callbacks_registration(self):
        """测试回调注册"""
        from core.connection import create_adapter
        adapter = create_adapter()
        
        callback_called = [False]
        
        @adapter.on("connected")
        def on_connected(data):
            callback_called[0] = True
        
        # 验证回调已注册
        assert len(adapter._callbacks["connected"]) == 1
    
    def test_multiple_callbacks(self):
        """测试多个回调"""
        from core.connection import create_adapter
        adapter = create_adapter()
        
        @adapter.on("frame")
        def callback1(frame, data):
            pass
        
        @adapter.on("frame")
        def callback2(frame, data):
            pass
        
        assert len(adapter._callbacks["frame"]) == 2
    
    def test_remove_callback(self):
        """测试移除回调"""
        from core.connection import create_adapter
        adapter = create_adapter()
        
        def my_callback(data):
            pass
        
        adapter._callbacks["connected"].append(my_callback)
        assert len(adapter._callbacks["connected"]) == 1
        
        adapter.off("connected", my_callback)
        assert len(adapter._callbacks["connected"]) == 0


class TestAdapterDataAccess:
    """测试适配器数据访问（无连接状态）"""
    
    def test_get_player_position_no_data(self):
        """测试无数据时获取玩家位置"""
        from core.connection import create_adapter
        adapter = create_adapter()
        
        pos = adapter.get_player_position()
        assert pos is None
    
    def test_get_enemies_no_data(self):
        """测试无数据时获取敌人"""
        from core.connection import create_adapter
        adapter = create_adapter()
        
        enemies = adapter.get_enemies()
        assert enemies is None
    
    def test_get_room_info_no_data(self):
        """测试无数据时获取房间信息"""
        from core.connection import create_adapter
        adapter = create_adapter()
        
        room = adapter.get_room_info()
        assert room is None


class TestAdapterStats:
    """测试适配器统计"""
    
    def test_get_stats(self):
        """测试获取统计信息"""
        from core.connection import create_adapter
        adapter = create_adapter()
        
        stats = adapter.get_stats()
        
        assert "connected" in stats
        assert "uptime_seconds" in stats
        assert "last_frame" in stats
        assert "message_count" in stats
        assert "messages_per_second" in stats
        
        assert stats["connected"] is False
        assert stats["message_count"] == 0
    
    def test_quality_report(self):
        """测试质量报告"""
        from core.connection import create_adapter
        adapter = create_adapter()
        
        report = adapter.get_quality_report()
        
        assert report is not None
        assert isinstance(report, str)


class TestAdapterChannelAccess:
    """测试通道数据访问"""
    
    def test_get_channel_no_data(self):
        """测试无数据时获取通道"""
        from core.connection import create_adapter
        adapter = create_adapter()
        
        data = adapter.get_channel("PLAYER_POSITION")
        assert data is None
    
    def test_is_channel_fresh_no_data(self):
        """测试无数据时检查通道新鲜度"""
        from core.connection import create_adapter
        adapter = create_adapter()
        
        fresh = adapter.is_channel_fresh("PLAYER_POSITION")
        assert fresh is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
