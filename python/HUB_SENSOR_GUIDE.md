# Hub 模式 Sensor 接入规范

> 目标：为未来所有 Python 工具提供统一的 Hub 接入方式，确保通道数据可靠传输、可观测、可排障。

## 1. 核心原则

1. Hub 是唯一 Lua 连接持有者。
2. 上层应用不直接连 Lua，只连 Hub。
3. Sensor 注册在 Lua 侧完成；应用侧只做订阅、消费和可选配置。
4. 每个应用必须显式声明所需通道，禁止“依赖默认全量”。
5. 断线重连后必须自动恢复订阅并主动拉一次快照。

## 2. 职责边界（避免“注册/订阅冲突”）

### 2.1 Lua 侧（数据生产）

- 文件：main.lua
- 职责：
  - SensorRegistry:register(...) 定义可采集通道。
  - 采集、节流、哈希去重、消息发送。
- 结论：
  - 新增通道时，先改 Lua 注册和采集逻辑。

### 2.2 Hub 侧（数据分发）

- 文件：python/bridge_hub_service.py
- 职责：
  - 接收 Lua 数据并维护 snapshot。
  - 按客户端 subscriptions 做本地过滤。
  - 路由命令结果回发起客户端。
- 结论：
  - Hub 不负责“创建新 sensor”，只负责分发和过滤。

### 2.3 应用侧（数据消费）

- 文件：python/hub_bridge.py + apps/*
- 职责：
  - 声明需要的 channels。
  - 在连接后 subscribe(...)。
  - request_full_state() 拉首帧快照。
  - 处理 DATA/SNAPSHOT/EVENT。
- 结论：
  - 应用端的“注册”语义应理解为“注册消息处理器 + 注册所需通道集合”，不是注册 Lua Sensor。

## 3. 标准接入流程（所有新工具都遵循）

1. 定义 REQUIRED_CHANNELS 常量。
2. 构造 HubBridge(client_name=唯一工具名)。
3. 在 on("connected") 中：
   - 调用 subscribe(REQUIRED_CHANNELS)
   - 调用 request_full_state()
4. 在 on("message") 中只解析自己订阅的通道。
5. 对未订阅到的数据做显式告警（开发期）。
6. 工具退出时调用 stop()。

## 4. 推荐代码模板

```python
from hub_bridge import HubBridge

REQUIRED_CHANNELS = [
    "ROOM_INFO",
    "ROOM_LAYOUT",
    "PLAYER_POSITION",
    # 例如需要火焰："FIRE_HAZARDS",
]

bridge = HubBridge(host="127.0.0.1", port=9530, client_name="your_tool_name")

@bridge.on("connected")
def _on_connected(_info):
    bridge.subscribe(REQUIRED_CHANNELS)
    bridge.request_full_state()

@bridge.on("message")
def _on_message(msg, _processed):
    channels = msg.get("channels", [])
    payload = msg.get("payload", {})

    if "ROOM_INFO" in channels:
        room = payload.get("ROOM_INFO")
        # consume room

bridge.start()
```

## 5. 通道设计建议

1. 按工具目标最小订阅：只订阅真正使用的通道。
2. 分层订阅：基础通道（房间/玩家）+ 可选通道（危险物/拾取物）。
3. 不要把渲染刷新条件仅绑定到 room_idx 变化；动态通道应按帧或状态变化刷新。
4. 如果多个通道有同屏字符冲突，优先定义清晰图例和优先级覆盖规则。

## 6. 常见故障模式与对应检查

### 6.1 “某通道一直收不到”

检查顺序：

1. Lua 是否注册该 Sensor（main.lua 中是否存在 SensorRegistry:register）。
2. 应用 REQUIRED_CHANNELS 是否包含该通道。
3. on("connected") 是否执行了 subscribe。
4. Hub 是否过滤掉（客户端 subscriptions 不含该通道）。
5. 消息中 channels 是否含该通道、payload 是否含对应键。

### 6.2 “有数据但工具不更新”

常见原因：

1. UI 刷新触发条件错误（仅房间变化才重绘）。
2. 通道名判断正确，但内部字段名读取错误。
3. 同坐标绘制覆盖，视觉上像“没显示”。

### 6.3 “重连后通道丢失”

必须确认：

1. 订阅集合保存在客户端对象中。
2. 重连后会重发 SUBSCRIBE。
3. 重连后会请求 full state。

## 7. 新工具接入自检清单（上线前）

- 是否定义 REQUIRED_CHANNELS。
- 是否在 connected 回调里 subscribe + request_full_state。
- 是否对关键通道打印一次启动诊断（仅开发环境）。
- 是否覆盖断线重连路径。
- 是否有至少一个“通道缺失”保护分支。
- 是否在文档中写明该工具依赖通道。

## 8. 推荐文档联动

新增工具时，请同步更新：

1. README.md 的应用工具指南（写明该工具的 Hub 模式启动方式）。
2. HUB_USAGE.md 的并行运行示例（如适用）。
3. 本文档中的“通道依赖说明”（如新增通道策略）。

---

维护建议：当某次故障根因属于“订阅漏配、重连未恢复、刷新条件错误”三类之一，请优先更新本文件，避免重复踩坑。
