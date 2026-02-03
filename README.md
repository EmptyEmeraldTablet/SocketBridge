# SocketBridge 项目文档

> **版本**: 2.1  
> **更新日期**: 2026年2月3日  
> **状态**: 核心功能完成 ✅  
> **English**: [README_EN.md](README_EN.md)

---

## 目录

1. [项目概述](#项目概述)
2. [快速开始](#快速开始)
3. [应用工具指南](#应用工具指南)
4. [开发者指南](#开发者指南)
5. [新通道注册流程](#新通道注册流程)
6. [常见问题与解答](#常见问题与解答)
7. [架构参考](#架构参考)
8. [相关文档](#相关文档)
9. [许可证](#许可证)

---

## 项目概述

**SocketBridge** 是一个为《以撒的结合：重生》（The Binding of Isaac: Repentance）游戏开发的模组，实现了游戏与 Python 程序之间的实时数据桥接。该项目旨在为游戏 AI 开发、数据分析和自动化测试提供强大的基础设施。

### 核心特性

| 特性 | 说明 |
|------|------|
| **实时数据采集** | 高效采集游戏内各类数据（玩家、敌人、投射物、房间等） |
| **多频率采集** | 支持 HIGH/MEDIUM/LOW/ON_CHANGE 四种采集模式 |
| **双向通信** | 游戏数据实时传输到 Python，Python 可发送控制指令回游戏 |
| **事件系统** | 完整的游戏事件监听与回调机制 |
| **AI 控制支持** | 内置 AI 控制框架，支持手动/AI 模式切换（F3 键） |
| **数据录制** | 完整的游戏会话录制与回放系统 |
| **时序感知** | v2.1 协议支持通道级时序信息，解决数据同步问题 |
| **质量监控** | 自动检测游戏端和 Python 端问题 |

### 应用场景与限制

#### ✅ 本项目能够实现的功能

| 应用领域 | 具体应用 | 技术实现 |
|---------|---------|----------|
| **游戏 AI 开发** | 自动游戏、智能走位、自动射击、敌人回避 | 实时位置数据 + 控制指令发送 |
| **游戏机制研究** | 伤害计算、敌人行为模式、房间生成规律 | 完整的实体数据采集与分析 |
| **数据统计分析** | 游戏进度追踪、死亡原因统计、道具效果分析 | 事件系统 + 数据录制回放 |
| **自动化测试** | 模组兼容性测试、游戏平衡性验证、性能测试 | 可重复的录制回放机制 |
| **可视化工具** | 房间布局显示、实体轨迹追踪、实时数据监控 | 实时数据流 + 图形渲染 |
| **学习研究** | 游戏开发学习、网络编程实践、数据处理算法 | 完整的开源代码架构 |

#### ❌ 本项目无法实现的功能

| 限制类别 | 具体限制 | 原因 | 影响范围 |
|---------|---------|------|----------|
| **道具系统深度分析** | 无法获取道具的隐藏属性、触发条件、协同效果 | 官方 API 不完善 | 道具推荐系统、Build 优化 AI |
| **完整游戏状态还原** | 无法保存/加载完整游戏状态，无法实现游戏存档 | 游戏引擎限制 | 状态回溯、A/B 测试 |
| **实时性要求极高的应用** | 帧级精确控制、零延迟响应 | 网络通信固有延迟 (5-20ms) | 高频操作类 AI、TAS 录制 |
| **商业化应用** | 外挂、作弊工具、商业 AI 助手 | 违反游戏 ToS + 项目许可证限制 | 任何盈利性应用 |
| **完整的游戏逆向工程** | 游戏内部算法、隐藏机制完全解析 | 仅能采集暴露的 API 数据 | 完美仿真、算法复现 |

#### 🎯 推荐使用场景

**最适合的项目类型：**
- 🤖 **学习型 AI**：基于游戏数据训练的 AI 助手（如路径规划、危险识别）
- 📊 **数据科学项目**：游戏行为分析、统计建模、可视化研究
- 🛠️ **开发工具**：模组开发辅助、游戏内容创建工具
- 📚 **教育项目**：游戏开发教学、网络编程实践、数据处理学习

**需要谨慎考虑的场景：**
- ⚡ **高实时性要求**：需要评估网络延迟是否可接受
- 🎮 **复杂游戏策略**：受限于 API 能获取的信息深度
- 🔒 **商业应用**：需要确保符合游戏服务条款和项目许可证

### 已知限制

由于《以撒的结合》官方 Modding API 的不完善以及技术限制，本项目**无法采集到游戏的所有数据**：

| 限制类型 | 说明 |
|---------|------|
| **道具系统** | 道具效果、触发条件等 API 不明确，`PLAYER_INVENTORY` 通道功能受限 |
| **被动道具效果** | 无法准确获取被动道具的实时效果（如叠加、协同效果） |
| **部分实体属性** | 某些实体的特殊属性无法通过 API 获取 |
| **内部状态机** | 敌人/Boss 的内部 AI 状态无法直接访问 |
| **隐藏房间机制** | 部分隐藏机制的判定逻辑不公开 |
| **网络延迟** | Socket 通信存在固有延迟，高频数据可能丢失 |

> ⚠️ **注意**：部分通道（如 `PLAYER_INVENTORY`、`INTERACTABLES`）虽然在架构中有设计，但由于上述 API 限制，实际功能可能不完整或未完全实现。详见 [docs/archivedDoc/KNOWN_GAME_ISSUES.md](docs/archivedDoc/KNOWN_GAME_ISSUES.md)。

### 目录结构

```
SocketBridge/
├── main.lua                    # 游戏模组主文件（Lua）
├── metadata.xml                # 模组元数据
├── README.md                   # 本文档
├── README_EN.md                # 英文文档
├── REFACTORING_PLAN.md         # 重构计划文档
├── LICENCE                     # 许可证
├── .gitignore                  # Git 忽略文件
│
├── docs/                       # 文档目录
│   ├── archivedDoc/            # 归档文档
│   │   └── KNOWN_GAME_ISSUES.md # 已知游戏问题
│   ├── reference_from_2026.1.11/ # 历史参考文档
│   ├── ROOM_GEOMETRY_FIX.md    # 房间几何修复文档
│   └── TERRAIN_VALIDATION.md   # 地形验证文档
│
└── python/                     # Python 端代码
    ├── isaac_bridge.py         # 核心网络桥接库
    ├── environment.py          # 游戏地图环境建模
    ├── models.py               # 兼容层（重导出）
    ├── requirements.txt        # Python 依赖列表
    ├── CONSOLE_COMMANDS.md     # 控制台命令文档
    ├── DATA_PROTOCOL.md        # 数据协议文档
    │
    ├── models/                 # 数据模型层
    │   ├── __init__.py
    │   ├── base.py             # 基础类型 (Vector2D, EntityType)
    │   ├── entities.py         # 实体数据类
    │   └── state.py            # 状态管理
    │
    ├── channels/               # 数据通道层
    │   ├── __init__.py
    │   ├── base.py             # DataChannel 基类, ChannelRegistry
    │   ├── player.py           # 玩家相关通道
    │   ├── room.py             # 房间相关通道
    │   ├── entities.py         # 实体通道
    │   ├── danger.py           # 危险物通道
    │   └── interactables.py    # 可互动实体通道
    │
    ├── services/               # 服务层
    │   ├── __init__.py
    │   ├── facade.py           # 统一 API 门面
    │   ├── processor.py        # 数据处理服务
    │   ├── monitor.py          # 质量监控服务
    │   └── entity_state.py     # 实体状态管理
    │
    ├── core/                   # 核心层
    │   ├── __init__.py
    │   ├── connection/         # 连接适配器
    │   │   ├── __init__.py
    │   │   └── adapter.py      # 连接适配器
    │   ├── protocol/           # 协议处理
    │   │   ├── __init__.py
    │   │   ├── schema.py       # Pydantic 数据模式
    │   │   └── timing.py       # 时序处理
    │   ├── validation/         # 数据验证
    │   │   ├── __init__.py
    │   │   └── known_issues.py # 已知问题处理
    │   └── replay/             # 录制回放系统
    │       ├── __init__.py
    │       ├── message.py      # RawMessage v2.1
    │       ├── recorder.py     # 数据录制器
    │       ├── replayer.py     # 数据回放器
    │       └── session.py      # 会话管理
    │
    ├── apps/                   # 应用工具
    │   ├── console.py          # 交互式控制台
    │   ├── recorder.py         # 游戏数据录制器
    │   ├── replay_test.py      # 回放测试工具
    │   ├── room_layout_visualizer.py  # 房间布局可视化
    │   └── terrain_validator.py       # 地形数据验证器
    │
    ├── tests/                  # 测试用例 (20+ tests)
    │   ├── __init__.py
    │   ├── test_adapter.py     # 连接适配器测试
    │   ├── test_channels.py    # 通道测试
    │   ├── test_entity_state.py # 实体状态测试
    │   ├── test_live_connection.py # 实时连接测试
    │   ├── test_replay.py      # 回放测试
    │   ├── test_schema.py      # 模式验证测试
    │   ├── test_timing.py      # 时序测试
    │   ├── test_validation.py  # 验证测试
    │   └── fixtures/           # 测试固件
    │       ├── __init__.py
    │       ├── README.md       # 测试数据说明
    │       ├── sample_messages.json # 样例消息
    │       └── session_20260202_234038/ # 测试会话数据
    │
    ├── recordings/             # 录制数据目录 (运行时)
    └── archive/                # 归档代码
```

---

## 快速开始

### 环境要求

- 《以撒的结合：重生》游戏（Repentance DLC）/ Repentance+ IS OK
- Python 3.8+
- 依赖包：

```bash
pip install pydantic
```

### 安装步骤

#### 1. 安装游戏模组

将 `SocketBridge` 文件夹复制到游戏 mods 目录：

```
Windows: C:\Users\<用户名>\Documents\My Games\Binding of Isaac Repentance\mods\
```

在游戏中启用 SocketBridge 模组。

#### 2. 启动 Python 端

```bash
cd python
python isaac_bridge.py
```

或使用应用工具：

```bash
# 交互式控制台
python apps/console.py

# 自动录制模式
python apps/recorder.py --auto
```

#### 3. 启动游戏

> ⚠️ **重要：必须添加 `--luadebug` 启动参数**
>
> 在 Steam 中右键游戏 → 属性 → 通用 → 启动选项，添加：
> ```
> --luadebug
> ```
> **如果不添加此参数，Lua 的 Socket 网络模块将无法加载，导致游戏与 Python 端完全无法通信！**

启动《以撒的结合：重生》，模组会自动连接到 Python 服务器（默认 127.0.0.1:9527）。

### 验证安装

启动游戏后，Python 端应显示：

```
✓ 游戏已连接! (127.0.0.1:xxxxx)
```

---

## 应用工具指南

所有工具位于 `python/apps/` 目录下。

### 1. 交互式控制台 (console.py)

用于向游戏发送控制台命令。

```bash
python apps/console.py
```

**使用方法：**

```
Isaac Console> giveitem c1      # 给予道具
Isaac Console> spawn 13         # 生成敌人
Isaac Console> debug 3          # 开启调试信息
Isaac Console> help             # 显示帮助
Isaac Console> status           # 显示连接状态
Isaac Console> quit             # 退出
```

**常用命令：**

| 命令 | 说明 |
|------|------|
| `giveitem c<ID>` | 给予收藏品道具 |
| `giveitem t<ID>` | 给予饰品 |
| `spawn <ID>` | 生成实体 |
| `goto s.boss.0` | 跳转到 Boss 房间 |
| `debug 3` | 开启调试地图 |
| `debug 8` | 显示伤害数值 |

---

### 2. 游戏数据录制器 (recorder.py)

录制游戏数据用于回放和分析。

```bash
# 启动录制器（手动控制）
python apps/recorder.py

# 自动录制模式（连接即开始）
python apps/recorder.py --auto

# 列出所有录制
python apps/recorder.py --list

# 清理旧录制（保留最新5个）
python apps/recorder.py --cleanup --keep 5
```

**运行时快捷键：**

| 按键 | 功能 |
|------|------|
| `r` | 开始/停止录制 |
| `p` | 暂停/恢复录制 |
| `s` | 显示当前状态 |
| `l` | 列出所有会话 |
| `q` | 退出 |

**命令行参数：**

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--output, -o` | 输出目录 | `./recordings` |
| `--host` | 监听地址 | `127.0.0.1` |
| `--port, -p` | 监听端口 | `9527` |
| `--auto, -a` | 自动录制模式 | 关闭 |
| `--list, -l` | 列出所有会话 | - |
| `--cleanup` | 清理旧录制 | - |
| `--keep` | 保留数量 | `10` |

**自动录制行为：**
- 游戏连接时自动开始录制
- 游戏断开时暂停（不停止），等待重连
- 只有手动按 `r` 或 `q` 才会真正停止录制

---

### 3. 回放测试工具 (replay_test.py)

测试录制数据的回放功能。

```bash
# 测试最新会话
python apps/replay_test.py

# 显示前20条消息
python apps/replay_test.py --count 20

# 测试指定会话
python apps/replay_test.py --session session_20260202_234038

# 显示所有消息（慎用）
python apps/replay_test.py --all
```

**输出示例：**

```
找到 1 个会话:
  1. session_20260202_234038  时长: 03:07  帧数: 4989

会话信息:
  总消息数: 9978
  总帧数: 4989

前 5 条消息:
----------------------------------------------------------------------
[   1] frame=  684 | type=DATA  | PLAYER_POSITION, PROJECTILES, ENEMIES
[   2] frame=  684 | type=DATA  | PLAYER_POSITION, PROJECTILES, ENEMIES
----------------------------------------------------------------------
✓ 回放测试完成!
```

---

### 4. 房间布局可视化器 (room_layout_visualizer.py)

将房间布局渲染为字符网格，方便调试和验证。

```bash
# 实时模式（持续更新）
python apps/room_layout_visualizer.py live

# 快照模式（进房间后截取一次）
python apps/room_layout_visualizer.py snapshot

# 与游戏画面对比
python apps/room_layout_visualizer.py compare
```

**字符图例：**

| 字符 | 含义 |
|------|------|
| `.` | 空地/装饰 |
| `#` | 岩石/墙壁 |
| `O` | 坑洞 |
| `^` | 尖刺 |
| `T` | 染色岩石 |
| `D` | 门 |
| `@` | 玩家位置 |

---

### 5. 地形数据验证器 (terrain_validator.py)

验证地形数据的正确性，区分 Lua 端和 Python 端问题。

```bash
# 实时验证模式
python apps/terrain_validator.py live

# 打印原始数据
python apps/terrain_validator.py dump
```

---

## 开发者指南

### 基本数据接收

```python
import sys
sys.path.insert(0, './python')

from services.facade import SocketBridgeFacade

facade = SocketBridgeFacade()

@facade.on_data
def on_data(frame, room):
    player = facade.get_player()
    if player:
        print(f"Frame {frame}: Player at ({player.x}, {player.y})")

facade.start()
```

### 使用 IsaacBridge（底层 API）

```python
from isaac_bridge import IsaacBridge

bridge = IsaacBridge()

@bridge.on("connected")
def on_connected(data):
    print("游戏已连接!")

@bridge.on("message")
def on_message(msg):
    print(f"Frame {msg.frame}: {msg.channels}")

@bridge.on("event")
def on_event(event):
    print(f"Event: {event.type} - {event.data}")

bridge.start()
```

### AI 控制示例

```python
from services.facade import SocketBridgeFacade

facade = SocketBridgeFacade()

@facade.on_data
def ai_update(frame, room):
    player = facade.get_player()
    enemies = facade.get_enemies()

    if enemies and player:
        # 找到最近的敌人
        nearest = min(enemies, key=lambda e: 
            (e.x - player.x)**2 + (e.y - player.y)**2)
        
        # 计算移动方向（远离敌人）
        dx = player.x - nearest.x
        dy = player.y - nearest.y
        
        move_x = 1 if dx > 0 else -1 if dx < 0 else 0
        move_y = 1 if dy > 0 else -1 if dy < 0 else 0
        
        # 向敌人射击
        shoot_x = -move_x
        shoot_y = -move_y
        
        facade.send_move_and_shoot(move_x, move_y, shoot_x, shoot_y)

facade.start()
```

### 使用录制回放系统

```python
from core.replay import DataReplayer, ReplayerConfig, list_sessions

# 列出所有会话
sessions = list_sessions('./recordings')
print(f"找到 {len(sessions)} 个会话")

# 加载并回放
config = ReplayerConfig(recordings_dir='./recordings')
replayer = DataReplayer(config)
session = replayer.load_session(sessions[0].session_id)

# 迭代所有消息
for msg in replayer.iter_messages():
    print(f"Frame {msg.frame}: {msg.channels}")
    # 处理消息...
```

### 实体状态管理

SocketBridge 提供两层状态管理机制：

#### 状态保持层级

| 层级 | 说明 | 实现 |
|------|------|------|
| **通道级状态** | 缓存各通道最新数据 | `DataProcessor._data_cache` |
| **实体级状态** | 跨帧跟踪实体，合并状态 | `GameEntityState` (v2.1 新增) |

#### 问题背景

由于游戏数据采集频率不同（如敌人每 5 帧采集一次），直接获取某帧数据可能是空的：

```python
# ❌ 问题：敌人通道可能返回空列表（因为本帧没采集）
enemies = facade.get_enemies()  # 可能是 []，即使房间里有敌人
```

#### 解决方案：有状态实体管理

```python
from services.facade import SocketBridgeFacade, BridgeConfig

# 配置实体状态管理
config = BridgeConfig(
    entity_state_enabled=True,      # 启用实体状态管理
    enemy_expiry_frames=60,         # 敌人 60 帧未更新则过期
    projectile_expiry_frames=30,    # 投射物 30 帧过期
    pickup_expiry_frames=120,       # 拾取物 120 帧过期
)

facade = SocketBridgeFacade(config)

# ✅ 使用有状态版本获取敌人
enemies = facade.get_enemies_stateful(max_stale_frames=5)
# 返回最近 5 帧内见过的所有敌人，即使本帧没采集也能获取

# 获取投射物（有状态）
projectiles = facade.get_projectiles_stateful(max_stale_frames=3)
# 返回 {"enemy_projectiles": [...], "player_tears": [...], "lasers": [...]}

# 获取拾取物（有状态）
pickups = facade.get_pickups_stateful()

# 获取炸弹（有状态）
bombs = facade.get_bombs_stateful()

# 获取威胁数量
threat_count = facade.get_threat_count()  # 敌人数 + 敌方投射物数
```

#### 工作原理

```
帧 100: ENEMIES 采集 → [Enemy A, Enemy B]
帧 101: ENEMIES 未采集
帧 102: ENEMIES 未采集
帧 103: ENEMIES 未采集
帧 104: ENEMIES 未采集
帧 105: ENEMIES 采集 → [Enemy A, Enemy C]  (B 已死亡，C 是新生成的)

# 在帧 102 调用 get_enemies_stateful(max_stale_frames=5)
# 返回 [Enemy A, Enemy B] ✓ (使用帧 100 的缓存数据)

# 在帧 105 调用 get_enemies_stateful(max_stale_frames=5)  
# 返回 [Enemy A, Enemy C] ✓ (最新数据)
# Enemy B 因超过 60 帧未更新而被自动清理
```

#### 实体生命周期

1. **首次出现** - 实体被添加到状态管理器，记录 `first_seen_frame`
2. **更新** - 每次通道采集时更新 `last_seen_frame` 和实体数据
3. **过期清理** - 超过 `expiry_frames` 帧未更新的实体自动移除
4. **房间切换** - 切换房间时自动清空所有实体状态

#### 直接使用 EntityStateManager

```python
from services.entity_state import EntityStateManager, EntityStateConfig

# 创建自定义实体管理器
config = EntityStateConfig(
    expiry_frames=60,      # 过期帧数
    enable_history=True,   # 启用历史记录
    max_history=10,        # 保留最近 10 条历史
    id_field="id",         # 实体 ID 字段名
)

manager = EntityStateManager[EnemyData](
    name="CUSTOM_ENEMIES",
    config=config,
    id_getter=lambda e: e.id,  # 自定义 ID 获取函数
)

# 更新（每帧调用）
changes = manager.update(enemies_list, current_frame)
# changes = {"added": [1, 2], "updated": [3], "removed": [4]}

# 获取活跃实体
active = manager.get_fresh(max_stale_frames=5)

# 获取单个实体
enemy = manager.get(entity_id=123)

# 获取实体历史
history = manager.get_history(entity_id=123)

# 检查实体是否活跃
is_active = manager.is_entity_active(entity_id=123)

# 获取统计信息
stats = manager.get_stats()
```

#### 配置参考

| 实体类型 | 类型 | 采集频率 | 建议过期帧数 | 说明 |
|---------|------|---------|-------------|------|
| 敌人 | 动态 | HIGH (每帧) | 10 | 与采集频率匹配，~0.17 秒 |
| 投射物 | 动态 | HIGH (每帧) | 5 | 快速移动，短过期 |
| 激光 | 动态 | HIGH (每帧) | 5 | 与投射物相同 |
| 拾取物 | 动态 | LOW (每15帧) | 30 | 采集间隔 × 2 |
| 炸弹 | 动态 | LOW (每15帧) | 30 | 采集间隔 × 2 |
| 网格实体 | 静态 | ON_CHANGE/LOW | -1 (禁用) | 障碍物破坏是状态变化，不是移除 |

> **设计原则**：
> - **动态实体**：过期帧数 = 采集间隔 × 2，确保跨帧稳定
> - **静态实体**：禁用自动过期（-1），状态变化由游戏端通知

---

## 新通道注册流程

当需要添加新的数据采集通道时，按照以下步骤操作：

### 步骤 1: 定义数据模式 (Pydantic)

在 `core/protocol/schema.py` 中添加数据模式：

```python
class MyNewChannelData(BaseModel):
    """我的新通道数据"""
    
    model_config = {"extra": "allow"}
    
    value1: float = Field(default=0.0, description="字段1")
    value2: int = Field(default=0, description="字段2")
    items: List[str] = Field(default_factory=list, description="列表字段")
```

### 步骤 2: 创建通道类

在 `channels/` 目录下创建或修改通道文件：

```python
# channels/my_channel.py

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

from channels.base import DataChannel, ChannelConfig, ChannelRegistry
from core.protocol.schema import MyNewChannelData
from core.validation.known_issues import ValidationIssue

logger = logging.getLogger(__name__)


@dataclass
class MyChannelData:
    """通道数据封装"""
    items: Dict[int, MyNewChannelData]
    
    def get_item(self, idx: int) -> Optional[MyNewChannelData]:
        return self.items.get(idx)


class MyNewChannel(DataChannel[MyChannelData]):
    """我的新通道
    
    采集频率: MEDIUM
    优先级: 5
    """
    
    name = "MY_NEW_CHANNEL"  # 必须与 Lua 端通道名一致
    config = ChannelConfig(
        name="MY_NEW_CHANNEL",
        interval="MEDIUM",
        priority=5,
        enabled=True,
        validation_enabled=True,
    )
    
    def parse(self, raw_data: Dict[str, Any], frame: int) -> Optional[MyChannelData]:
        """解析原始数据"""
        try:
            items = {}
            
            # 处理列表格式 [1]=..., [2]=...
            if isinstance(raw_data, dict):
                for key, value in raw_data.items():
                    try:
                        idx = int(key)
                        items[idx] = MyNewChannelData(**value)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse item {key}: {e}")
            
            return MyChannelData(items=items)
            
        except Exception as e:
            logger.error(f"Failed to parse {self.name}: {e}")
            return None
    
    def validate(self, data: MyChannelData) -> List[ValidationIssue]:
        """验证数据（可选）"""
        issues = []
        # 添加自定义验证逻辑
        return issues


# 注册通道
ChannelRegistry.register_class(MyNewChannel)
```

### 步骤 3: 在 Lua 端注册采集器

在 `main.lua` 中找到 **数据收集器定义** 部分（约第 580 行），添加新的采集器：

```lua
-- ============================================================================
-- 我的新通道 (自定义)
-- ============================================================================
CollectorRegistry:register("MY_NEW_CHANNEL", {
    interval = "MEDIUM",  -- 采集频率: HIGH/MEDIUM/LOW/RARE/ON_CHANGE
    priority = 5,         -- 优先级: 1-10
    collect = function()
        local data = {}
        
        -- 采集数据逻辑示例
        data[1] = {
            value1 = 1.5,
            value2 = 10,
            items = {"a", "b", "c"}
        }
        
        return data
    end
})
```

#### Lua 采集器配置说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `interval` | string | 采集频率，见下表 |
| `priority` | number | 优先级 1-10，越高越先采集 |
| `collect` | function | 采集函数，返回数据表 |
| `enabled` | boolean | 是否启用（默认 true） |
| `hash` | function | 可选，自定义变化检测哈希函数 |

#### 采集频率说明

| 频率 | 帧间隔 | 说明 |
|------|--------|------|
| `HIGH` | 1 | 每帧采集（位置、投射物等） |
| `MEDIUM` | 5 | 每5帧采集 |
| `LOW` | 15 | 每15帧采集（属性、生命等） |
| `RARE` | 60 | 每60帧采集（物品栏等） |
| `ON_CHANGE` | -1 | 仅在数据变化时采集 |

#### Lua 辅助函数

`main.lua` 中提供了常用的辅助函数：

```lua
-- 向量转表
Helpers.vectorToTable(vector)  -- 返回 {x=..., y=...}

-- 获取所有玩家
Helpers.getPlayers()  -- 返回玩家列表

-- 获取当前房间
Game():GetRoom()

-- 获取房间实体
Isaac.GetRoomEntities()

-- 获取游戏时间
Isaac.GetTime()
```

#### 完整 Lua 采集器示例

```lua
-- 采集所有拾取物
CollectorRegistry:register("PICKUPS", {
    interval = "LOW",
    priority = 4,
    collect = function()
        local pickups = {}
        
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if entity.Type == EntityType.ENTITY_PICKUP then
                table.insert(pickups, {
                    id = entity.Index,
                    type = entity.Type,
                    variant = entity.Variant,
                    subtype = entity.SubType,
                    pos = Helpers.vectorToTable(entity.Position),
                    price = entity:ToPickup().Price,
                    shop_item = entity:ToPickup().IsShopItem,
                })
            end
        end
        
        return pickups
    end
})
```

### 步骤 4: 更新服务层（可选）

如果需要通过 `SocketBridgeFacade` 访问新通道，在 `services/facade.py` 添加：

```python
def get_my_channel_data(self) -> Optional[MyChannelData]:
    """获取我的通道数据"""
    channel = ChannelRegistry.get("MY_NEW_CHANNEL")
    if channel:
        return channel.get_data()
    return None
```

### 步骤 5: 添加测试

在 `tests/` 目录添加测试：

```python
# tests/test_my_channel.py

import pytest
from channels.my_channel import MyNewChannel, MyChannelData

def test_parse_valid_data():
    channel = MyNewChannel()
    raw_data = {
        "1": {"value1": 1.5, "value2": 10, "items": ["a", "b"]}
    }
    result = channel.parse(raw_data, frame=100)
    
    assert result is not None
    assert 1 in result.items
    assert result.items[1].value1 == 1.5
```

### 步骤 6: 集成实体状态管理（如需跨帧跟踪）

如果新通道包含需要跨帧跟踪的实体（如敌人、投射物等），需要将其集成到实体状态管理模块。

#### 6.1 在 GameEntityState 中添加管理器

修改 `services/entity_state.py`：

```python
class GameEntityState:
    def __init__(
        self,
        # ... 现有参数 ...
        my_entity_expiry: int = 30,  # 新增：根据采集频率设置过期帧数
    ):
        # ... 现有管理器 ...
        
        # 新增：我的实体状态管理器
        self.my_entities = EntityStateManager(
            name="MY_ENTITIES",
            config=EntityStateConfig(expiry_frames=my_entity_expiry),
            # id_getter: 根据实体数据结构指定 ID 获取方式
            id_getter=lambda x: x.id if hasattr(x, "id") else x.get("id", 0),
        )
    
    # 新增更新方法
    def update_my_entities(self, entities: List[Any], frame: int):
        """更新我的实体状态"""
        self._current_frame = frame
        self.my_entities.update(entities, frame)
    
    # 新增获取方法
    def get_my_entities(self, max_stale_frames: int = 15) -> List[Any]:
        """获取我的实体"""
        return self.my_entities.get_fresh(max_stale_frames)
    
    # 更新 on_room_change 添加清理
    def on_room_change(self, new_room: int):
        # ... 现有代码 ...
        self.my_entities.clear()  # 新增
    
    # 更新 get_stats 添加统计
    def get_stats(self) -> Dict[str, Any]:
        return {
            # ... 现有字段 ...
            "my_entities": self.my_entities.get_stats(),  # 新增
        }
```

#### 6.2 在 BridgeConfig 中添加配置

修改 `services/facade.py`：

```python
@dataclass
class BridgeConfig:
    # ... 现有配置 ...
    my_entity_expiry_frames: int = 30  # 新增：根据采集频率设置
```

#### 6.3 在 SocketBridgeFacade 中添加更新和获取方法

修改 `services/facade.py`：

```python
class SocketBridgeFacade:
    def __init__(self, config: Optional[BridgeConfig] = None):
        # ... 现有代码 ...
        if self.config.entity_state_enabled:
            self.entity_state = GameEntityState(
                # ... 现有参数 ...
                my_entity_expiry=self.config.my_entity_expiry_frames,  # 新增
            )
    
    def _update_entity_state(self, channels: Dict[str, ProcessedChannel], frame: int):
        # ... 现有更新逻辑 ...
        
        # 新增：更新我的实体
        if "MY_NEW_CHANNEL" in channels and channels["MY_NEW_CHANNEL"].data:
            my_data = channels["MY_NEW_CHANNEL"].data
            if isinstance(my_data, list):
                self.entity_state.update_my_entities(my_data, frame)
    
    # 新增：获取方法（有状态保持版）
    def get_my_entities_stateful(self, max_stale_frames: int = 15) -> List[Any]:
        """获取我的实体（有状态保持版）"""
        if self.entity_state:
            return self.entity_state.get_my_entities(max_stale_frames)
        return []
```

#### 6.4 过期帧数设置指南

| 实体类型 | 采集频率 | 建议过期帧数 | 计算公式 |
|---------|---------|-------------|---------|
| 动态实体 | HIGH (每帧) | 5-10 | 采集间隔 × 5~10 |
| 动态实体 | LOW (每15帧) | 30 | 采集间隔 × 2 |
| 静态实体 | ON_CHANGE | -1 (禁用) | 不自动过期 |

**选择依据**：
- **动态实体**（会移动、会消失）：启用过期，过期帧数 = 采集间隔 × 2
- **静态实体**（障碍物、地形）：禁用过期（-1），状态变化由游戏通知

### 注意事项

1. **通道名称必须一致** - Python 端 `name = "MY_NEW_CHANNEL"` 必须与 Lua 端 `CollectorRegistry:register("MY_NEW_CHANNEL", ...)` 完全相同

2. **数据格式约定** - Lua 表会被转换为 JSON，注意：
   - Lua 数组索引从 1 开始
   - 使用 `data[1]` 而不是 `data[0]`
   - 嵌套表会转换为嵌套 JSON 对象

3. **错误处理** - Lua 采集函数应使用 `pcall` 保护，框架已内置错误处理

4. **性能考虑** - 高频通道（HIGH）避免复杂计算，使用适当的采集频率---

## 常见问题与解答

### Q1: 游戏完全无法与 Python 通信 / Socket 模块加载失败

**原因：**
未在 Steam 启动选项中添加 `--luadebug` 参数。

**说明：**
《以撒的结合》默认禁用 Lua 的 Socket 网络模块（出于安全考虑）。必须通过 `--luadebug` 参数显式启用，否则模组的网络通信功能完全无法工作。

**解决方案：**
1. 在 Steam 中右键《以撒的结合：重生》
2. 选择「属性」→「通用」→「启动选项」
3. 添加 `--luadebug`
4. 重启游戏

**验证方法：**
- 游戏启动后，Python 端应显示 `✓ 游戏已连接!`
- 如果 Python 端一直显示等待连接，说明 `--luadebug` 未生效

---

### Q2: 游戏无法连接到 Python 服务器

**原因：**
- Python 服务器未启动
- 端口被占用
- 防火墙阻止连接
- 连接端口未被释放（windows上较为常见）

**解决方案：**
```bash
# 检查端口占用
netstat -ano | findstr 9527

# 使用不同端口
python apps/recorder.py --port 9528

# 确保 main.lua 中端口一致
local PORT = 9527

#关闭之前的终端窗口

#等待5分钟左右连接被释放再次尝试

```

### Q3: ModuleNotFoundError: No module named 'xxx'

**原因：** 
工作目录不正确或 Python 路径问题。

**解决方案：**
```bash
# 确保在 python 目录下运行
cd python
python apps/xxx.py

# 或者使用模块方式运行
python -m apps.xxx
```

### Q4: 录制的事件数为 0

**原因：**
旧版本使用了不支持的通配符 `event:*`。

**解决方案：**
更新到最新版本的 `recorder.py`，使用 `@bridge.on("event")` 监听所有事件。

### Q5: 房间布局显示不正确

**原因：**
坐标转换公式问题（已在 v2.1 修复）。

**解决方案：**
确保使用正确的坐标公式：
```python
GRID_SIZE = 40  # 每格 40 像素
adjusted_tl = top_left - 40
grid_x = int((world_x - adjusted_tl.x) / GRID_SIZE)
grid_y = int((world_y - adjusted_tl.y) / GRID_SIZE)
```

### Q6: Pydantic 验证错误

**原因：**
v2.0 到 v2.1 迁移时 Pydantic 配置变化。

**解决方案：**
使用新的配置方式：
```python
# 旧方式（已废弃）
class Config:
    extra = "allow"

# 新方式
model_config = {"extra": "allow"}
```

### Q7: 如何查看原始 Lua 数据？

**方法 1:** 使用地形验证器
```bash
python apps/terrain_validator.py dump
```

**方法 2:** 在代码中打印
```python
@bridge.on("message")
def on_message(msg):
    print(json.dumps(msg.payload, indent=2))
```

### Q8: 如何在游戏中切换 AI/手动模式？

在游戏中按 **F3** 键切换。
- AI 模式：Python 控制角色移动和射击
- 手动模式：玩家正常控制

### Q9: 录制文件存储在哪里？

默认存储在 `python/recordings/` 目录：
```
recordings/
├── session_20260202_234038/
│   ├── metadata.json        # 会话元数据
│   └── messages_0000.jsonl.gz  # 压缩的消息数据
```

---

## 架构参考

### 数据流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        游戏端 (Lua)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Collector    │  │  Protocol    │  │   InputExecutor      │   │
│  │ Registry     │──│  v2.1        │──│   (控制输入)          │   │
│  │ (数据采集)   │  │              │  │                      │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│         │                 │                     ▲                │
│         └─────────────────┼─────────────────────┘                │
│                           │ TCP/IP :9527                         │
└───────────────────────────┼─────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────┐
│                           ▼                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ IsaacBridge  │──│ DataMessage  │──│   Channels           │   │
│  │ (网络层)     │  │ (协议解析)   │  │   (数据通道)         │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│         │                                      │                 │
│         ▼                                      ▼                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Recorder     │  │   Services   │  │   Apps               │   │
│  │ (录制回放)   │  │ (Facade等)   │  │   (上层应用)         │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                  │
│                        Python 端                                 │
└──────────────────────────────────────────────────────────────────┘
```

### 数据通道列表

| 通道名称 | 频率 | 优先级 | 说明 |
|---------|------|--------|------|
| `PLAYER_POSITION` | HIGH | 10 | 玩家位置、速度、朝向 |
| `PLAYER_STATS` | LOW | 5 | 玩家属性（伤害、速度、射程等） |
| `PLAYER_HEALTH` | ON_CHANGE | 8 | 玩家生命值 |
| `PLAYER_INVENTORY` | ON_CHANGE | 3 | 玩家物品栏 |
| `ENEMIES` | HIGH | 7 | 敌人信息 |
| `PROJECTILES` | HIGH | 9 | 投射物 |
| `ROOM_INFO` | LOW | 4 | 房间基本信息 |
| `ROOM_LAYOUT` | ON_CHANGE | 2 | 房间布局网格 |
| `BOMBS` | LOW | 5 | 炸弹 |
| `FIRE_HAZARDS` | LOW | 6 | 火焰危险物 |
| `PICKUPS` | LOW | 4 | 拾取物 |
| `INTERACTABLES` | LOW | 4 | 可互动实体 |

### 通道新架构集成状态

> ⚠️ **设计说明**  
> 当前的通道设计沿用自早期版本，部分设计并不合理（如通道划分粒度、数据结构、采集频率配置等）。未来计划适配新架构对通道进行重新设计，包括：
> - 重新评估通道划分逻辑（按实体类型 vs 按功能场景）
> - 统一数据结构规范（ID 字段、坐标系、时间戳等）
> - 优化采集频率与状态管理的配合
> - 完善 `GRID_ENTITIES` 等缺失通道
> 
> 在此之前，下表仅反映现有通道对新架构各层的集成程度，不代表最终设计。

下表说明各通道对新架构各层的集成程度：

| 通道 | Channel 类 | Pydantic Schema | 验证 | Facade 方法 | 实体状态管理 |
|------|-----------|-----------------|------|-------------|-------------|
| `PLAYER_POSITION` | ✅ 完整 | ✅ `PlayerPositionData` | ✅ | ✅ `get_player_position()` | ❌ 不适用 |
| `PLAYER_STATS` | ✅ 完整 | ✅ `PlayerStatsData` | ✅ | ✅ `get_player_stats()` | ❌ 不适用 |
| `PLAYER_HEALTH` | ✅ 完整 | ✅ `PlayerHealthData` | ✅ | ⚠️ 通用方法 | ❌ 不适用 |
| `PLAYER_INVENTORY` | ✅ 完整 | ✅ `PlayerInventoryData` | ✅ | ⚠️ 通用方法 | ❌ 不适用 |
| `ENEMIES` | ✅ 完整 | ✅ `EnemyData` | ✅ | ✅ `get_enemies()` | ✅ `get_enemies_stateful()` |
| `PROJECTILES` | ✅ 完整 | ✅ `ProjectilesData` | ✅ | ⚠️ 通用方法 | ✅ `get_projectiles_stateful()` |
| `ROOM_INFO` | ✅ 完整 | ✅ `RoomInfoData` | ✅ | ✅ `get_room_info()` | ❌ 不适用 |
| `ROOM_LAYOUT` | ✅ 完整 | ✅ `RoomLayoutData` | ✅ | ⚠️ 通用方法 | ❌ 不适用 |
| `BOMBS` | ✅ 完整 | ✅ `BombData` | ✅ | ⚠️ 通用方法 | ✅ `get_bombs_stateful()` |
| `FIRE_HAZARDS` | ✅ 完整 | ✅ `FireHazardData` | ✅ | ⚠️ 通用方法 | ❌ 未集成 |
| `PICKUPS` | ✅ 完整 | ✅ `PickupData` | ✅ | ⚠️ 通用方法 | ✅ `get_pickups_stateful()` |
| `INTERACTABLES` | ✅ 完整 | ✅ `InteractableData` | ✅ | ⚠️ 通用方法 | ❌ 未集成 |
| `GRID_ENTITIES` | ❌ 未实现 | ❌ | ❌ | ❌ | ✅ 状态管理已准备 |

#### 图例说明

- **Channel 类**: 在 `channels/` 目录下的通道类实现
- **Pydantic Schema**: 在 `core/protocol/schema.py` 中的数据模式定义
- **验证**: 通道的 `validate()` 方法实现
- **Facade 方法**: `SocketBridgeFacade` 中的专用访问方法
  - ✅ 有专用方法（如 `get_player_position()`）
  - ⚠️ 使用通用方法（`get_channel()` / `get_data()`）
- **实体状态管理**: `GameEntityState` 中的跨帧状态保持
  - ✅ 已集成（有 `get_xxx_stateful()` 方法）
  - ❌ 不适用（非实体类数据，如玩家状态、房间信息）
  - ❌ 未集成（应集成但尚未实现）

#### 待完善项

1. **`GRID_ENTITIES` 通道**
   - 状态管理层已准备好 (`grid_entities` 管理器)
   - 需要实现 Channel 类和 Pydantic Schema
   - Lua 端需要添加对应采集器

2. **`FIRE_HAZARDS` 实体状态集成**
   - Channel 类已完整
   - 需要添加到 `GameEntityState` 和 `SocketBridgeFacade`

3. **`INTERACTABLES` 实体状态集成**
   - Channel 类已完整
   - 可选：根据需要决定是否需要跨帧状态保持

4. **Facade 专用方法**
   - 部分通道使用通用 `get_channel()` / `get_data()` 访问
   - 可根据使用频率添加专用便捷方法

### 协议版本

当前版本：**v2.1**

v2.1 新增特性：
- `seq` - 消息序列号
- `game_time` - 游戏时间戳
- `prev_frame` - 上一帧号
- `channel_meta` - 通道级时序元数据

---

## 相关文档

- [README_EN.md](README_EN.md) - English version
- [REFACTORING_PLAN.md](REFACTORING_PLAN.md) - 重构计划与进度
- [docs/archivedDoc/KNOWN_GAME_ISSUES.md](docs/archivedDoc/KNOWN_GAME_ISSUES.md) - 已知游戏问题
- [python/DATA_PROTOCOL.md](python/DATA_PROTOCOL.md) - 数据协议详细文档
- [python/CONSOLE_COMMANDS.md](python/CONSOLE_COMMANDS.md) - 控制台命令参考
- [docs/TERRAIN_VALIDATION.md](docs/TERRAIN_VALIDATION.md) - 地形验证文档
- [docs/ROOM_GEOMETRY_FIX.md](docs/ROOM_GEOMETRY_FIX.md) - 房间几何修复文档

---

## 许可证

本项目仅供学习和研究使用。

---

**最后更新：** 2026年2月3日  
**版本：** 2.1  
**版本：** 2.1
