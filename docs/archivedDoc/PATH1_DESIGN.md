# 路线 1 实施计划: 统一消息回调格式

## 问题定义

**核心问题**: `isaac_bridge.py` 的 `on("data")` 回调只传递 `payload`，丢失了 `frame`, `room_index`, `channels`, `timestamp` 等元数据。

**当前流程**:
```
Lua 端发送完整消息 → Python 端收到 → 只提取 payload 传递 → 录制代码丢失元数据
```

## 设计方案

### 方案: 向后兼容的消息对象

新增 `DataMessage` 类，包含完整消息信息和便捷属性。

### 设计原则

1. **向后兼容**: 现有 `on("data")` 回调仍接收 `payload` (dict)
2. **新回调**: `on("message")` 回调接收完整消息对象
3. **便捷访问**: `DataMessage.payload` 直接访问 payload
4. **统一格式**: 使用 `RawMessage` dataclass 作为消息格式

### 新增类设计

```python
# python/isaac_bridge.py

@dataclass
class DataMessage:
    """
    完整的数据消息对象
    
    传递完整消息给录制系统，同时保持向后兼容。
    """
    version: int
    msg_type: str  # "DATA", "EVENT", etc.
    timestamp: int  # 毫秒级时间戳
    frame: int
    room_index: int
    payload: Dict[str, Any]
    channels: List[str]
    
    # 便捷属性
    @property
    def is_data(self) -> bool:
        return self.msg_type == "DATA"
    
    @property
    def is_event(self) -> bool:
        return self.msg_type == "EVENT"
    
    @property
    def is_full_state(self) -> bool:
        return self.msg_type == "FULL"
    
    # 兼容旧代码
    def __iter__(self):
        """使 DataMessage 可像 dict 一样迭代 (for backwards compat)"""
        yield from self.payload.items()
    
    def __getitem__(self, key):
        """使 DataMessage 可像 dict 一样访问 (for backwards compat)"""
        return self.payload[key]
    
    def get(self, key, default=None):
        """dict.get() 兼容"""
        return self.payload.get(key, default)
```

### 回调机制修改

```python
# python/isaac_bridge.py

def _process_message(self, msg: dict):
    """处理接收到的消息"""
    msg_type = msg.get('type')
    frame = msg.get('frame', 0)
    room_index = msg.get('room_index', -1)
    
    if msg_type == MessageType.DATA.value:
        payload = msg.get('payload', {})
        channels = msg.get('channels', [])
        timestamp = msg.get('timestamp', 0)
        
        self.state.update_batch(payload, frame, room_index)
        
        # 创建完整消息对象
        data_msg = DataMessage(
            version=msg.get('version', 2),
            msg_type=msg_type,
            timestamp=timestamp,
            frame=frame,
            room_index=room_index,
            payload=payload,
            channels=channels,
        )
        
        # 1. 向后兼容: 触发 "data" 回调 (传递 payload)
        self._trigger_handlers("data", payload)
        
        # 2. 新回调: 触发 "message" 回调 (传递完整消息)
        self._trigger_handlers("message", data_msg)
        
        # 3. 通道回调: 触发 "data:{channel}" 回调
        for channel in channels:
            self._trigger_handlers(f"data:{channel}", payload.get(channel))
    
    elif msg_type == MessageType.EVENT.value:
        # 类似地，为事件也添加新回调
        event_type = msg.get('event')
        event_data = msg.get('data', {})
        timestamp = msg.get('timestamp', 0)
        
        event = Event(
            type=event_type,
            data=event_data,
            frame=frame
        )
        self.event_queue.put(event)
        self.stats["events_received"] += 1
        
        # 向后兼容
        self._trigger_handlers(f"event:{event_type}", event_data)
        self._trigger_handlers("event", event)
        
        # 新回调: 传递完整事件消息
        self._trigger_handlers("event_message", event)
    
    # ... 其他消息类型
```

### 录制代码修改

```python
# python/data_replay_examples.py

# 新方式: 使用完整消息
@bridge.on("message")
def on_message(msg: DataMessage):
    """录制完整消息 (推荐方式)"""
    if recorder.recording:
        raw_msg = RawMessage(
            version=msg.version,
            msg_type=msg.msg_type,
            timestamp=msg.timestamp,
            frame=msg.frame,
            room_index=msg.room_index,
            payload=msg.payload,
            channels=msg.channels,
        )
        recorder.record_message(raw_msg)

# 旧方式仍然工作 (向后兼容)
@bridge.on("data")
def on_data(payload):
    """使用 payload 的代码仍然正常工作"""
    # payload 可以直接使用
    pass
```

### 回放系统修改

```python
# python/data_replay_system.py - LuaSimulator

class LuaSimulator:
    def _send_loop(self):
        # ... 发送逻辑不变
        
        # 发送时使用完整的 RawMessage.to_json_line()
        json_line = msg.to_json_line()
        self.client.send(json_line.encode("utf-8"))
```

## 实施步骤

### Phase 1: 核心修改

1. [ ] 在 `isaac_bridge.py` 中添加 `DataMessage` dataclass
2. [ ] 修改 `_process_message()` 方法创建 `DataMessage` 对象
3. [ ] 添加新的 `on("message")` 回调
4. [ ] 保持 `on("data")` 回调的向后兼容

### Phase 2: 更新录制代码

1. [ ] 更新 `data_replay_examples.py` 使用新回调
2. [ ] 更新 `data_recorder.py` 使用新回调
3. [ ] 验证录制功能正常

### Phase 3: 测试

1. [ ] 运行 `test_integration.py`
2. [ ] 验证数据完整性 (payload, channels 都不为 None)
3. [ ] 验证回放功能正常

### Phase 4: 文档

1. [ ] 更新 API 文档
2. [ ] 添加迁移指南
3. [ ] 更新示例代码

## 向后兼容性

| 现有代码 | 兼容性 | 说明 |
|---------|--------|------|
| `on("data")` | ✅ 完全兼容 | 仍然接收 `payload` dict |
| `on("event")` | ✅ 完全兼容 | 仍然接收 `Event` 对象 |
| `on("data:{channel}")` | ✅ 完全兼容 | 仍然接收通道数据 |
| `bridge.state` | ✅ 完全兼容 | 无变化 |
| `data.get_player_position()` | ✅ 完全兼容 | 无变化 |

## 新 API

| 新回调 | 参数 | 用途 |
|--------|------|------|
| `on("message")` | `DataMessage` | 录制完整消息 |
| `on("event_message")` | `Event` | 录制完整事件 |

## 优点

1. **零破坏**: 现有代码完全无需修改
2. **功能增强**: 录制系统可以获得完整元数据
3. **清晰分离**: 消息处理与业务逻辑分离
4. **未来扩展**: 可轻松添加更多消息类型
