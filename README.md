# SocketBridge 项目说明文档

## 项目概述

**SocketBridge** 是一个为《以撒的结合：重生》（The Binding of Isaac: Repentance）游戏开发的模组，实现了游戏与 Python 程序之间的实时数据桥接。该项目旨在为游戏 AI 开发、数据分析和自动化测试提供强大的基础设施。

### 核心特性

- **实时数据采集** - 高效采集游戏内各类数据（玩家、敌人、投射物、房间等）
- **多频率采集** - 支持高频/中频/低频/变化时四种采集模式
- **双向通信** - 游戏数据实时传输到 Python，Python 可发送控制指令回游戏
- **事件系统** - 完整的游戏事件监听与回调机制
- **AI 控制支持** - 内置 AI 控制框架，支持手动/AI 模式切换（F3 键）
- **数据记录** - 内置数据记录器，支持游戏会话录制与回放
- **模块化设计** - 可扩展的收集器注册系统，易于添加新的数据通道
- **时序感知** - v2.1 新增数据时序监控，解决数据同步问题
- **质量监控** - v2.1 新增数据质量监控，自动检测游戏端和 Python 端问题

---

## v2.1 新架构

### 目录结构

```
SocketBridge/
├── main.lua                 # 游戏模组主文件（Lua）
├── metadata.xml             # 模组元数据
├── MIGRATION_GUIDE.md       # v2.1 迁移指南
├── REFACTORING_PLAN.md      # 重构计划文档
└── python/                  # Python 端代码
    ├── models/              # 数据模型层
    │   ├── __init__.py      # 统一导出
    │   ├── base.py          # 基础类型 (Vector2D, EntityType)
    │   ├── entities.py      # 实体数据类 (PlayerData, EnemyData)
    │   └── state.py         # 状态管理 (GameStateData)
    ├── channels/            # 数据通道层
    │   ├── base.py          # DataChannel 基类, ChannelRegistry
    │   ├── player.py        # 玩家相关通道
    │   ├── room.py          # 房间相关通道
    │   ├── entities.py      # 实体通道
    │   ├── danger.py        # 危险物通道
    │   └── interactables.py # 可交互实体通道
    ├── services/            # 服务层
    │   ├── processor.py     # 数据处理服务
    │   ├── monitor.py       # 质量监控服务
    │   └── facade.py        # 统一 API 门面
    ├── core/                # 核心层
    │   ├── protocol/
    │   │   ├── schema.py    # Pydantic 模式定义
    │   │   └── timing.py    # 时序处理
    │   └── validation/
    │       └── known_issues.py  # 已知问题注册
    ├── isaac_bridge.py      # 核心桥接库
    ├── data_recorder.py     # 数据记录器
    ├── example_ai.py        # AI 控制示例
    ├── DATA_PROTOCOL.md     # 数据协议文档
    └── recordings/          # 录制数据目录
```

---

## 快速开始

### 环境要求

- 《以撒的结合：重生》游戏
- Python 3.8+
- 依赖：`pip install pydantic`

### 安装步骤

1. **安装游戏模组**
   - 将 `SocketBridge` 文件夹复制到游戏 mods 目录
   - 在游戏中启用 SocketBridge 模组

2. **启动 Python 端**
   ```bash
   cd python
   python isaac_bridge.py
   ```

3. **启动游戏**
   - 启动《以撒的结合：重生》
   - 模组会自动连接到 Python 服务器

---

## 使用示例

### 基本数据接收

```python
from services.facade import SocketBridgeFacade

facade = SocketBridgeFacade()

@facade.on_data
def on_data(frame, room):
    player = facade.get_player()
    if player:
        print(f"Frame {frame}: Player at ({player.x}, {player.y})")

facade.start()
```

### AI 控制

```python
from services.facade import SocketBridgeFacade

facade = SocketBridgeFacade()

@facade.on_data
def on_update(frame, room):
    player = facade.get_player()
    enemies = facade.get_enemies()

    if enemies and player:
        nearest = enemies[0]
        dx = nearest.x - player.x
        dy = nearest.y - player.y

        move_dir = (1 if dx > 0 else -1 if dx < 0 else 0,
                    1 if dy > 0 else -1 if dy < 0 else 0)
        shoot_dir = move_dir

        facade.send_move_and_shoot(move_dir[0], move_dir[1],
                                   shoot_dir[0], shoot_dir[1])

facade.start()
```

### 数据质量监控

```python
from services.facade import SocketBridgeFacade

facade = SocketBridgeFacade()

# 获取质量报告
report = facade.get_quality_report()
print(f"Game-side issue rate: {report['game_side_issue_rate']:.1%}")
print(f"Python-side issue rate: {report['python_side_issue_rate']:.1%}")
print(f"Top issues: {report['top_issues']}")
```

---

## 数据通道

| 通道名称 | 频率 | 优先级 | 说明 |
|---------|------|--------|------|
| PLAYER_POSITION | HIGH | 10 | 玩家位置、速度、朝向 |
| PLAYER_STATS | LOW | 5 | 玩家属性（伤害、速度、射程等） |
| PLAYER_HEALTH | ON_CHANGE | 8 | 玩家生命值 |
| PLAYER_INVENTORY | ON_CHANGE | 3 | 玩家物品栏、道具、消耗品 |
| ENEMIES | HIGH | 7 | 敌人信息（位置、血量、状态） |
| PROJECTILES | HIGH | 9 | 投射物 |
| ROOM_INFO | LOW | 4 | 房间信息 |
| ROOM_LAYOUT | ON_CHANGE | 2 | 房间布局 |
| BOMBS | LOW | 5 | 炸弹 |
| FIRE_HAZARDS | LOW | 6 | 火焰危险物 |
| PICKUPS | LOW | 4 | 拾取物 |
| INTERACTABLES | LOW | 4 | 可互动实体 |

---

## 协议版本

当前版本：**v2.1**

### v2.1 新增特性

- **时序字段**：每条消息包含 `seq`（序列号）、`game_time`、`prev_frame`
- **通道元数据**：`channel_meta` 记录每个通道的采集帧号、时间、间隔
- **过期检测**：自动检测过期数据，`stale_frames` 字段
- **乱序检测**：通过序列号检测消息乱序
- **帧跳跃检测**：检测帧号异常跳跃

---

## 迁移到 v2.1

如果您的代码使用旧版 API，请参考 [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) 进行迁移。

### 旧版导入

```python
from models import Vector2D, PlayerData, GameStateData
```

### 新版导入（推荐）

```python
from models.base import Vector2D, EntityType
from models.entities import PlayerData, EnemyData
from models.state import GameStateData
```

---

## 文档链接

- [DATA_PROTOCOL.md](python/DATA_PROTOCOL.md) - 数据协议详细文档
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - v2.1 迁移指南
- [REFACTORING_PLAN.md](REFACTORING_PLAN.md) - 重构计划
- [KNOWN_GAME_ISSUES.md](KNOWN_GAME_ISSUES.md) - 已知游戏问题

---

## 许可证

本项目仅供学习和研究使用。

---

**最后更新：** 2026年2月2日
**版本：** 2.1
