"""
Connection Module - 网络连接层

提供 BridgeAdapter 将现有 IsaacBridge 与新架构集成。

使用示例：
    from core.connection import BridgeAdapter, create_adapter
    
    adapter = create_adapter()
    
    @adapter.on("frame")
    def on_frame(frame, data):
        print(f"Frame: {frame}")
    
    adapter.start()
"""

from .adapter import BridgeAdapter, AdapterConfig, create_adapter

__all__ = [
    "BridgeAdapter",
    "AdapterConfig",
    "create_adapter",
]
