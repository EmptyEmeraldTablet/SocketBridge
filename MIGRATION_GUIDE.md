# SocketBridge v2.1 迁移指南

> 本指南帮助您从旧版 API 迁移到 SocketBridge v2.1

## 目录

- [变更概述](#变更概述)
- [导入路径变更](#导入路径变更)
- [数据模型迁移](#数据模型迁移)
- [新架构说明](#新架构说明)
- [常见问题](#常见问题)

---

## 变更概述

v2.1 版本引入了全新的模块化架构，主要变更：

| 变更类型 | 描述 |
|---------|------|
| **模块化重构** | `models.py` 拆分为 `models/base.py`, `models/entities.py`, `models/state.py` |
| **时序支持** | 新增 `TimingAwareStateManager`，支持数据时序监控 |
| **通道注册** | 新增 `channels/` 目录，统一管理数据通道 |
| **服务层** | 新增 `services/` 目录，提供 Facade API |

---

## 导入路径变更

### 旧版导入（仍可用，但不推荐）

```python
from models import Vector2D, PlayerData, EnemyData, GameStateData
```

### 新版导入（推荐）

```python
# 基础类型
from models.base import Vector2D, EntityType, ObjectState

# 实体数据类
from models.entities import PlayerData, EnemyData, ProjectileData, RoomInfo

# 状态管理
from models.state import GameStateData, TimingAwareStateManager

# 或者一次性导入所有
from models import Vector2D, PlayerData, GameStateData  # 兼容旧版
```

---

## 数据模型迁移

### Vector2D

```python
# 旧版
from models import Vector2D
v = Vector2D(100, 200)

# 新版（相同）
from models.base import Vector2D
v = Vector2D(100, 200)

# 新增方法
v2 = Vector2D(50, 50)
distance = v.distance_to(v2)  # 新增：计算距离
normalized = v.normalized()   # 新增：归一化向量
```

### PlayerData

```python
# 旧版
from models import PlayerData
player = PlayerData(player_idx=1)
player.health = 3.0

# 新版（相同）
from models.entities import PlayerData
player = PlayerData(player_idx=1)
player.health = 3.0

# 新增功能
player_stats = player.get_stats()  # 获取 PlayerStatsData
```

### GameStateData

```python
# 旧版
from models import GameStateData
state = GameStateData()
player = state.players.get(1)

# 新版（相同）
from models.state import GameStateData
state = GameStateData()
player = state.players.get(1)

# 新增方法
is_fresh = state.is_channel_stale("PLAYER_STATS")  # 检查通道新鲜度
state.cleanup_stale_entities()  # 清理过期实体
```

---

## 新架构说明

### 目录结构

```
python/
├── models/
│   ├── __init__.py          # 统一导出
│   ├── base.py              # 基础类型 (Vector2D, Enums)
│   ├── entities.py          # 实体数据类
│   └── state.py             # 状态管理
├── channels/
│   ├── __init__.py
│   ├── base.py              # DataChannel 基类
│   ├── player.py            # 玩家相关通道
│   ├── room.py              # 房间相关通道
│   └── ...
├── services/
│   ├── processor.py         # 数据处理服务
│   ├── monitor.py           # 质量监控服务
│   └── facade.py            # 统一 API 门面
└── core/
    ├── protocol/
    │   ├── schema.py        # Pydantic 模式定义
    │   └── timing.py        # 时序处理
    └── validation/
        └── known_issues.py  # 已知问题注册
```

### 新增功能

#### 1. 时序感知状态管理

```python
from models.state import TimingAwareStateManager

state_manager = TimingAwareStateManager()

# 更新通道（带时序信息）
state_manager.update_channel("PLAYER_POSITION", data, timing_info, frame=300)

# 检查数据新鲜度
is_fresh = state_manager.is_channel_fresh("PLAYER_POSITION", max_stale_frames=5)

# 获取同步快照
snapshot = state_manager.get_synchronized_snapshot(
    ["PLAYER_POSITION", "ENEMIES"],
    max_frame_diff=5
)
```

#### 2. 数据质量监控

```python
from services.monitor import DataQualityMonitor

monitor = DataQualityMonitor()

# 记录消息
monitor.record_message("PLAYER_POSITION", frame=300, processing_time_ms=0.5)

# 记录验证结果
monitor.record_validation("PLAYER_POSITION", passed=True)

# 生成报告
report = monitor.generate_report()
print(f"Issue rate: {report.game_side_issue_rate:.1%}")
```

#### 3. Facade API

```python
from services.facade import SocketBridgeFacade

facade = SocketBridgeFacade()
facade.start()

# 简化数据访问
player = facade.get_player()
enemies = facade.get_enemies()

# 危险判断
if facade.is_in_danger():
    facade.send_move(-1, 0)

# 质量报告
report = facade.get_quality_report()
```

---

## 常见问题

### Q1: 旧代码还能用吗？

可以。`models.py` 保留作为兼容层，所有旧版导入仍正常工作：

```python
# 仍然可用
from models import Vector2D, PlayerData, GameStateData
```

但建议逐步迁移到新架构。

### Q2: 如何判断数据是否过期？

```python
from models.state import GameStateData

state = GameStateData()

# 方法1: 检查通道新鲜度
is_stale = state.is_channel_stale("PLAYER_STATS", max_staleness=30)

# 方法2: 使用 TimingAwareStateManager
from models.state import TimingAwareStateManager
manager = TimingAwareStateManager()
is_fresh = manager.is_channel_fresh("PLAYER_POSITION", max_stale_frames=5)
```

### Q3: 如何获取同步的多通道数据？

```python
from models.state import TimingAwareStateManager

manager = TimingAwareStateManager()

# 获取同步快照（所有通道采集帧差异在5帧内）
snapshot = manager.get_synchronized_snapshot(
    ["PLAYER_POSITION", "ENEMIES"],
    max_frame_diff=5
)

if snapshot:
    player_pos = snapshot["PLAYER_POSITION"]
    enemies = snapshot["ENEMIES"]
```

### Q4: 如何注册新的数据通道？

```python
from channels.base import DataChannel, ChannelRegistry
from protocol.schema import BaseModel

class MyChannelData(BaseModel):
    value: int

class MyChannel(DataChannel[MyChannelData]):
    name = "MY_CHANNEL"
    schema = MyChannelData
    
    def parse(self, raw_data, frame):
        return MyChannelData(**raw_data)
    
    def validate(self, data):
        return []

# 注册通道
ChannelRegistry.register(MyChannel())
```

---

## 迁移检查清单

- [ ] 更新导入路径
- [ ] 替换 `from models import ...` 为模块化导入
- [ ] 使用 `is_channel_stale()` 替代手动检查
- [ ] 考虑使用 `TimingAwareStateManager` 进行时序管理
- [ ] 评估是否需要 `DataQualityMonitor` 进行质量监控
- [ ] 评估是否需要 `SocketBridgeFacade` 简化代码

---

## 获取帮助

- 查看 [DATA_PROTOCOL.md](DATA_PROTOCOL.md) 了解协议详情
- 查看 [REFACTORING_PLAN.md](REFACTORING_PLAN.md) 了解架构设计
- 提交 [GitHub Issue](https://github.com/anomalyco/SocketBridge/issues) 报告问题
