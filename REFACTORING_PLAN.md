# SocketBridge 重构规划文档

> 版本: 1.1  
> 日期: 2026-02-02  
> 状态: Phase 1 完成 ✅

---

## 目录

1. [项目现状分析](#1-项目现状分析)
2. [核心问题诊断](#2-核心问题诊断)
3. [重构目标与原则](#3-重构目标与原则)
4. [重构方案](#4-重构方案)
5. [实施路线图](#5-实施路线图)
6. [风险评估与缓解措施](#6-风险评估与缓解措施)

---

## 1. 项目现状分析

### 1.1 项目架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        游戏端 (Lua)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Collector    │  │  Protocol    │  │   InputExecutor      │   │
│  │ Registry     │──│  (JSON)      │──│   (控制输入)          │   │
│  │ (数据采集)   │  │              │  │                      │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│         │                 │                     ▲                │
│         └─────────────────┼─────────────────────┘                │
│                           │ TCP/IP                               │
└───────────────────────────┼─────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────┐
│                           ▼                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ IsaacBridge  │──│ DataMessage  │──│   GameState          │   │
│  │ (网络层)     │  │ (协议解析)   │  │   (状态容器)         │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│         │                                      │                 │
│         ▼                                      ▼                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ DataProcessor│──│   models.py  │──│   上层应用 (apps/)    │   │
│  │ (数据处理)   │  │ (数据模型)   │  │   AI/可视化/录制等    │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                  │
│                        Python 端                                 │
└──────────────────────────────────────────────────────────────────┘
```

### 1.2 核心组件职责

| 组件 | 文件 | 职责 | 当前状态 |
|-----|------|------|---------|
| **Lua 端** | `main.lua` | 数据采集、协议封装、输入执行 | 相对稳定 |
| **网络层** | `isaac_bridge.py` | TCP 服务器、消息收发、事件系统 | 功能完整 |
| **协议解析** | `isaac_bridge.py` (DataMessage) | 消息结构定义、向后兼容 | 有重复定义 |
| **数据处理** | `data_processor.py` | JSON 解析、类型转换、格式标准化 | 存在问题 |
| **数据模型** | `models.py` | 实体类定义、状态容器 | 臃肿、职责混乱 |
| **数据验证** | `data_validator.py` | 数据校验、问题检测 | 独立运行 |
| **上层应用** | `apps/*.py` | AI 决策、可视化、录制回放 | 已隔离 |

### 1.3 数据通道清单

| 通道名 | 频率 | 描述 | Lua 发送格式 | Python 接收问题 |
|-------|------|------|-------------|----------------|
| `PLAYER_POSITION` | HIGH | 玩家位置 | `{[1]={pos=..}}` | list/dict 两种格式 |
| `PLAYER_STATS` | LOW | 玩家属性 | `{[1]={damage=..}}` | 同上 |
| `PLAYER_HEALTH` | LOW | 玩家血量 | `{[1]={red_hearts=..}}` | 同上 |
| `PLAYER_INVENTORY` | RARE | 玩家物品 | `{[1]={coins=..}}` | 同上 |
| `ENEMIES` | HIGH | 敌人列表 | `[{id=..}]` | 正常 |
| `PROJECTILES` | HIGH | 投射物 | `{enemy_projectiles=..}` | 正常 |
| `ROOM_INFO` | LOW | 房间信息 | `{room_type=..}` | 正常 |
| `ROOM_LAYOUT` | LOW | 房间布局 | `{grid={}, doors={}}` | 正常 |
| `BOMBS` | LOW | 炸弹 | `[{id=..}]` | 正常 |
| `INTERACTABLES` | LOW | 可互动实体 | `[{id=..}]` | 正常 |
| `PICKUPS` | LOW | 拾取物 | `[{id=..}]` | 正常 |
| `FIRE_HAZARDS` | LOW | 火焰危险 | `[{id=..}]` | 正常 |

---

## 2. 核心问题诊断

### 2.1 类型安全问题

#### 问题描述
Lua 和 Python 都是动态类型语言，缺乏编译期类型检查，导致：

1. **Lua 数组序列化不一致**：`{[1]=val}` 可能序列化为 JSON 数组 `[val]` 或对象 `{"1": val}`
2. **字段缺失静默失败**：缺少字段时返回 `nil/None`，不会报错
3. **类型错误延迟暴露**：数据类型不匹配时，错误在运行时才出现

#### 当前代码示例
```python
# isaac_bridge.py - 被迫处理两种格式
def _get_player_data(self, channel: str, player_idx: int = 1):
    data = self.state.get(channel)
    if isinstance(data, list):
        idx = player_idx - 1  # Lua 1-based -> Python 0-based
        return data[idx] if 0 <= idx < len(data) else None
    elif isinstance(data, dict):
        return data.get(str(player_idx)) or data.get(player_idx)
    return None
```

#### 影响
- 多处代码重复处理同一问题
- 难以追踪数据来源和类型
- 新开发者容易踩坑

### 2.2 协议版本管理问题

#### 问题描述
1. **版本号仅用于标记**：`version: 2` 但实际未用于兼容性控制
2. **协议变更无追踪**：没有变更日志或迁移工具
3. **向后兼容代码分散**：兼容逻辑散落在各处

#### 示例
```lua
-- main.lua
Protocol = { VERSION = "2.0", ... }
```
```python
# isaac_bridge.py
version=msg.get("version", 2),  # 默认假设为 2
```

### 2.3 数据验证与处理分离问题

#### 问题描述
1. **验证框架独立运行**：`data_validator.py` 是独立工具，非实时验证
2. **已知问题分散记录**：`KNOWN_GAME_ISSUES.md` 与代码脱节
3. **异常处理不统一**：各组件自行处理异常

### 2.4 模型层职责混乱

#### 问题描述
`models.py` 文件过于庞大（1138 行），包含：
- 基础类型定义（Vector2D）
- 实体数据类（PlayerData, EnemyData 等）
- 状态容器（GameStateData）
- 房间布局逻辑（RoomLayout）
- 坐标转换逻辑

#### 影响
- 单一文件难以维护
- 循环依赖风险
- 测试粒度过粗

### 2.5 游戏端问题 vs Python 端问题区分困难

#### 已知游戏端问题（来自 KNOWN_GAME_ISSUES.md）

| 问题 | 类型 | 严重程度 |
|------|------|---------|
| GRID_FIREPLACE (ID 13) 已废弃 | 游戏 API | 低 |
| GRID_DOOR (ID 16) 出现在 grid | 游戏 API | 低 |
| aim_dir 返回 (0,0) | 游戏 API | 低 |
| 敌人负数 HP | 游戏 API | 中 |
| HP > max_hp | 游戏 API | 中 |
| 投射物 ID 复用 | 游戏 API | 低 |

#### 已知 Python 端问题（已修复）

| 问题 | 严重程度 | 状态 |
|------|---------|------|
| 房间切换数据残留 | 高 | ✅ 已修复 |
| 实体过期清理不完整 | 高 | ✅ 已修复 |
| 数据格式不一致 | 中 | ✅ 已修复 |

### 2.6 数据时序问题（重要）

#### 问题描述

由于 Lua 端采用分频采集机制，不同通道的数据采集时机不同，加上游戏卡顿、网络延迟等因素，Python 端接收到的数据存在严重的时序问题：

```
游戏帧:    1   2   3   4   5   6   7   8   9   10  11  12  ...
           │   │   │   │   │   │   │   │   │   │   │   │
HIGH(1帧): ●   ●   ●   ●   ●   ●   ●   ●   ●   ●   ●   ●   <- PLAYER_POSITION, ENEMIES
MEDIUM(5帧):●               ●               ●               <- (未使用)
LOW(30帧): ●                                               ● <- PLAYER_STATS, ROOM_INFO
RARE(90帧):●                                                  <- PLAYER_INVENTORY

问题场景:
1. 消息包含 frame=100，但 PLAYER_STATS 实际采集于 frame=90
2. 游戏卡顿导致 frame 跳跃：99 -> 102（丢失 100, 101）
3. TCP 缓冲导致多个消息合并或乱序到达
```

#### 当前协议的时序字段

```json
{
    "version": "2.0",
    "type": "DATA",
    "timestamp": 1234567890,  // Isaac.GetTime() 毫秒时间戳
    "frame": 123,             // 发送时的帧号（全局）
    "room_index": 5,
    "payload": { ... },
    "channels": ["PLAYER_POSITION", "ENEMIES"]
}
```

**问题**：
1. `frame` 是消息发送时的帧号，不是各通道数据采集时的帧号
2. 无法区分高频数据和低频数据的实际采集时机
3. 无法检测帧丢失或跳跃
4. 无消息序列号，无法检测乱序

#### 时序问题分类

| 问题类型 | 原因 | 当前能否检测 | 影响 |
|---------|------|-------------|------|
| **采集时机不一致** | 分频采集机制 | ❌ 无法检测 | 低频数据可能已过期 |
| **帧丢失** | 游戏卡顿、网络拥塞 | ❌ 无法检测 | 状态跳变 |
| **帧跳跃** | 游戏暂停/恢复 | ⚠️ 可部分检测 | 时间计算错误 |
| **消息乱序** | TCP 缓冲、处理延迟 | ❌ 无法检测 | 使用过期数据 |
| **消息合并** | TCP Nagle 算法 | ⚠️ 可检测 | 处理延迟 |

#### 影响场景

1. **AI 决策错误**：使用 30 帧前的 `PLAYER_STATS` 与当前 `ENEMIES` 计算伤害
2. **状态机混乱**：房间切换时，旧房间数据与新房间数据混合
3. **录制回放不准**：回放时无法精确还原各通道的时序关系
4. **调试困难**：无法判断问题是时序问题还是数据本身问题

---

## 3. 重构目标与原则

### 3.1 重构目标

#### 目标 1: 规范化 Python 端开发约束
- 引入类型注解和运行时验证
- 建立数据契约（Data Contract）机制
- 实现协议版本管理

#### 目标 2: 系统化数据质量监控
- 实时数据验证（非独立工具）
- 游戏端问题自动检测与标记
- 异常数据统计与报告

#### 目标 3: 支持灵活扩展
- 模块化架构，职责单一
- 插件式数据通道注册
- 简化的协议扩展流程

#### 目标 4: 解决数据时序问题（新增）
- 协议层添加细粒度时序字段
- Python 端实现时序感知的状态管理
- 提供时序异常检测与告警
- 支持精确的数据回放与调试

### 3.2 设计原则

1. **单一职责原则**：每个模块只做一件事
2. **开闭原则**：对扩展开放，对修改关闭
3. **显式优于隐式**：类型明确、错误显式
4. **向后兼容**：不破坏现有上层应用

---

## 4. 重构方案

### 4.1 架构重设计

#### 新架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                            python/                               │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                       core/ (核心层)                         ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐ ││
│  │  │ connection/ │  │  protocol/  │  │     validation/      │ ││
│  │  │ bridge.py   │  │ schema.py   │  │ validators.py        │ ││
│  │  │ events.py   │  │ messages.py │  │ sanitizers.py        │ ││
│  │  │             │  │ version.py  │  │ known_issues.py      │ ││
│  │  └─────────────┘  └─────────────┘  └──────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────┘│
│                               │                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                      models/ (模型层)                        ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐ ││
│  │  │  base.py    │  │ entities.py │  │     state.py         │ ││
│  │  │ Vector2D    │  │ PlayerData  │  │ GameStateData        │ ││
│  │  │ Enums       │  │ EnemyData   │  │ StateManager         │ ││
│  │  │             │  │ ...         │  │                      │ ││
│  │  └─────────────┘  └─────────────┘  └──────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────┘│
│                               │                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    channels/ (通道层)                        ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐ ││
│  │  │  base.py    │  │  player.py  │  │     room.py          │ ││
│  │  │ Channel ABC │  │ Position    │  │ RoomInfo             │ ││
│  │  │ Registry    │  │ Stats       │  │ RoomLayout           │ ││
│  │  │             │  │ Health      │  │                      │ ││
│  │  └─────────────┘  └─────────────┘  └──────────────────────┘ ││
│  │  ┌─────────────┐  ┌─────────────┐                           ││
│  │  │ entities.py │  │  hazards.py │                           ││
│  │  │ Enemies     │  │ FireHazards │                           ││
│  │  │ Projectiles │  │ Bombs       │                           ││
│  │  │ Pickups     │  │             │                           ││
│  │  └─────────────┘  └─────────────┘                           ││
│  └─────────────────────────────────────────────────────────────┘│
│                               │                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                   services/ (服务层)                         ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐ ││
│  │  │ processor.py│  │ monitor.py  │  │     facade.py        │ ││
│  │  │ 数据处理    │  │ 质量监控    │  │ 简化 API            │ ││
│  │  └─────────────┘  └─────────────┘  └──────────────────────┘ ││
│  └─────────────────────────────────────────────────────────────┘│
│                               │                                  │
│                        apps/ (应用层，已隔离)                    │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 协议扩展：时序字段设计（重要）

为解决数据时序问题，需要对 Lua 端和 Python 端的协议进行扩展。

#### 4.2.1 新协议格式 (v2.1)

**消息级别新增字段：**

```json
{
    "version": "2.1",
    "type": "DATA",
    
    // === 现有字段 ===
    "timestamp": 1234567890,      // Isaac.GetTime() 毫秒时间戳
    "frame": 123,                 // 发送时的帧号
    "room_index": 5,
    
    // === 新增时序字段 ===
    "seq": 1001,                  // 消息序列号（单调递增）
    "game_time": 12345,           // 游戏内运行时间（Isaac.GetTime()）
    "prev_frame": 122,            // 上一条消息的帧号（用于检测丢帧）
    
    // === 通道级别时序信息 ===
    "channel_meta": {
        "PLAYER_POSITION": {
            "collect_frame": 123,    // 该通道实际采集的帧号
            "collect_time": 1234567880,
            "interval": "HIGH"
        },
        "PLAYER_STATS": {
            "collect_frame": 90,     // 低频通道，30帧前采集
            "collect_time": 1234566000,
            "interval": "LOW",
            "stale_frames": 33       // 数据已过期的帧数
        },
        "ENEMIES": {
            "collect_frame": 123,
            "collect_time": 1234567880,
            "interval": "HIGH"
        }
    },
    
    "payload": { ... },
    "channels": ["PLAYER_POSITION", "PLAYER_STATS", "ENEMIES"]
}
```

#### 4.2.2 Lua 端实现

```lua
-- main.lua 修改

-- 全局状态新增
local State = {
    -- ... 现有字段 ...
    messageSeq = 0,           -- 消息序列号
    prevFrameSent = 0,        -- 上一条消息的帧号
    channelLastCollect = {},  -- 各通道最后采集帧号
}

-- CollectorRegistry 增强
function CollectorRegistry:collect(name, forceCollect)
    local collector = self.collectors[name]
    if not collector then return nil, nil end
    
    if not forceCollect and not self:shouldCollect(name) then
        return nil, nil
    end
    
    local success, data = pcall(collector.collect)
    if not success or data == nil then
        return nil, nil
    end
    
    -- ON_CHANGE 变化检测
    if collector.interval == "ON_CHANGE" and not forceCollect then
        local hashFunc = collector.hash or simpleHash
        local newHash = hashFunc(data)
        if self.changeHashes[name] == newHash then
            return nil, nil
        end
        self.changeHashes[name] = newHash
    end
    
    self.cache[name] = data
    
    -- 记录采集时的帧号和时间
    local collectMeta = {
        collect_frame = State.frameCounter,
        collect_time = Isaac.GetTime(),
        interval = collector.interval,
    }
    State.channelLastCollect[name] = collectMeta
    
    return data, collectMeta
end

-- Protocol 层增强
function Protocol.createDataMessage(data, channels)
    State.messageSeq = State.messageSeq + 1
    
    -- 构建通道元数据
    local channelMeta = {}
    for _, channelName in ipairs(channels) do
        local meta = State.channelLastCollect[channelName]
        if meta then
            channelMeta[channelName] = {
                collect_frame = meta.collect_frame,
                collect_time = meta.collect_time,
                interval = meta.interval,
                stale_frames = State.frameCounter - meta.collect_frame,
            }
        end
    end
    
    local msg = {
        version = "2.1",
        type = Protocol.MessageType.DATA,
        timestamp = Isaac.GetTime(),
        frame = State.frameCounter,
        room_index = State.currentRoomIndex,
        
        -- 新增时序字段
        seq = State.messageSeq,
        game_time = Isaac.GetTime(),
        prev_frame = State.prevFrameSent,
        channel_meta = channelMeta,
        
        payload = data,
        channels = channels
    }
    
    State.prevFrameSent = State.frameCounter
    return msg
end
```

#### 4.2.3 Python 端时序处理

```python
# core/protocol/timing.py
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TimingIssueType(Enum):
    """时序问题类型"""
    FRAME_GAP = "frame_gap"           # 帧间隙（可能丢帧）
    FRAME_JUMP = "frame_jump"         # 帧跳跃（大于阈值）
    OUT_OF_ORDER = "out_of_order"     # 消息乱序
    STALE_DATA = "stale_data"         # 数据过期
    CHANNEL_DESYNC = "channel_desync" # 通道不同步


@dataclass
class ChannelTimingInfo:
    """通道时序信息"""
    channel: str
    collect_frame: int
    collect_time: int
    interval: str
    stale_frames: int = 0
    
    @property
    def is_stale(self) -> bool:
        """数据是否过期（超过采集间隔的2倍）"""
        interval_frames = {
            "HIGH": 1,
            "MEDIUM": 5,
            "LOW": 30,
            "RARE": 90,
            "ON_CHANGE": 60,
        }
        threshold = interval_frames.get(self.interval, 30) * 2
        return self.stale_frames > threshold


@dataclass
class MessageTimingInfo:
    """消息时序信息"""
    seq: int
    frame: int
    game_time: int
    prev_frame: int
    channel_meta: Dict[str, ChannelTimingInfo] = field(default_factory=dict)
    
    @classmethod
    def from_message(cls, msg: dict) -> "MessageTimingInfo":
        """从消息中解析时序信息"""
        channel_meta = {}
        for name, meta in msg.get("channel_meta", {}).items():
            channel_meta[name] = ChannelTimingInfo(
                channel=name,
                collect_frame=meta.get("collect_frame", msg.get("frame", 0)),
                collect_time=meta.get("collect_time", msg.get("timestamp", 0)),
                interval=meta.get("interval", "UNKNOWN"),
                stale_frames=meta.get("stale_frames", 0),
            )
        
        return cls(
            seq=msg.get("seq", 0),
            frame=msg.get("frame", 0),
            game_time=msg.get("game_time", msg.get("timestamp", 0)),
            prev_frame=msg.get("prev_frame", 0),
            channel_meta=channel_meta,
        )


@dataclass 
class TimingIssue:
    """时序问题"""
    issue_type: TimingIssueType
    frame: int
    seq: int
    details: Dict
    severity: str = "warning"  # info, warning, error


class TimingMonitor:
    """时序监控器
    
    检测和记录时序问题：
    - 帧丢失/跳跃
    - 消息乱序
    - 数据过期
    """
    
    def __init__(self):
        self.last_seq = 0
        self.last_frame = 0
        self.expected_frame_gap = 1
        self.issues: List[TimingIssue] = []
        
        # 统计
        self.total_messages = 0
        self.frame_gaps = 0
        self.out_of_order = 0
        self.stale_channels = 0
    
    def check_message(self, timing: MessageTimingInfo) -> List[TimingIssue]:
        """检查消息时序"""
        issues = []
        self.total_messages += 1
        
        # 1. 检查消息序列号（乱序检测）
        if timing.seq > 0 and self.last_seq > 0:
            if timing.seq != self.last_seq + 1:
                if timing.seq <= self.last_seq:
                    # 乱序
                    issues.append(TimingIssue(
                        issue_type=TimingIssueType.OUT_OF_ORDER,
                        frame=timing.frame,
                        seq=timing.seq,
                        details={
                            "expected_seq": self.last_seq + 1,
                            "actual_seq": timing.seq,
                        },
                        severity="error",
                    ))
                    self.out_of_order += 1
                else:
                    # 序列号跳跃（可能丢消息）
                    gap = timing.seq - self.last_seq - 1
                    issues.append(TimingIssue(
                        issue_type=TimingIssueType.FRAME_GAP,
                        frame=timing.frame,
                        seq=timing.seq,
                        details={
                            "missing_count": gap,
                            "last_seq": self.last_seq,
                        },
                        severity="warning",
                    ))
        
        # 2. 检查帧号（帧跳跃检测）
        if self.last_frame > 0:
            frame_gap = timing.frame - self.last_frame
            
            if frame_gap <= 0:
                # 帧号倒退（异常）
                issues.append(TimingIssue(
                    issue_type=TimingIssueType.OUT_OF_ORDER,
                    frame=timing.frame,
                    seq=timing.seq,
                    details={
                        "last_frame": self.last_frame,
                        "current_frame": timing.frame,
                    },
                    severity="error",
                ))
            elif frame_gap > 5:
                # 帧跳跃（可能游戏卡顿）
                issues.append(TimingIssue(
                    issue_type=TimingIssueType.FRAME_JUMP,
                    frame=timing.frame,
                    seq=timing.seq,
                    details={
                        "frame_gap": frame_gap,
                        "last_frame": self.last_frame,
                    },
                    severity="warning" if frame_gap < 30 else "error",
                ))
                self.frame_gaps += 1
        
        # 3. 检查各通道数据新鲜度
        for channel_name, channel_timing in timing.channel_meta.items():
            if channel_timing.is_stale:
                issues.append(TimingIssue(
                    issue_type=TimingIssueType.STALE_DATA,
                    frame=timing.frame,
                    seq=timing.seq,
                    details={
                        "channel": channel_name,
                        "stale_frames": channel_timing.stale_frames,
                        "collect_frame": channel_timing.collect_frame,
                        "interval": channel_timing.interval,
                    },
                    severity="info",
                ))
                self.stale_channels += 1
        
        # 4. 检查高频通道间的同步性
        high_freq_channels = [
            (name, meta) for name, meta in timing.channel_meta.items()
            if meta.interval == "HIGH"
        ]
        if len(high_freq_channels) > 1:
            frames = [meta.collect_frame for _, meta in high_freq_channels]
            if max(frames) - min(frames) > 1:
                issues.append(TimingIssue(
                    issue_type=TimingIssueType.CHANNEL_DESYNC,
                    frame=timing.frame,
                    seq=timing.seq,
                    details={
                        "channels": {name: meta.collect_frame for name, meta in high_freq_channels},
                    },
                    severity="warning",
                ))
        
        # 更新状态
        self.last_seq = timing.seq
        self.last_frame = timing.frame
        self.issues.extend(issues)
        
        return issues
    
    def get_stats(self) -> Dict:
        """获取时序统计"""
        return {
            "total_messages": self.total_messages,
            "frame_gaps": self.frame_gaps,
            "out_of_order": self.out_of_order,
            "stale_channels": self.stale_channels,
            "issue_rate": len(self.issues) / max(self.total_messages, 1),
        }
```

#### 4.2.4 时序感知的状态管理

```python
# models/state.py 增强

@dataclass
class ChannelState:
    """通道状态（带时序信息）"""
    data: Any
    collect_frame: int
    collect_time: int
    receive_frame: int  # Python 端接收时的帧号
    receive_time: float # Python 端接收时的时间戳
    is_stale: bool = False


class TimingAwareStateManager:
    """时序感知的状态管理器
    
    特性：
    1. 记录每个通道数据的采集时间
    2. 提供数据新鲜度查询
    3. 支持按时间点查询历史状态
    4. 自动标记过期数据
    """
    
    def __init__(self, max_history: int = 300):
        self.channels: Dict[str, ChannelState] = {}
        self.history: Dict[str, deque] = {}  # 通道历史
        self.max_history = max_history
        self.current_frame = 0
    
    def update_channel(
        self,
        channel: str,
        data: Any,
        timing: ChannelTimingInfo,
        current_frame: int
    ):
        """更新通道数据（带时序信息）"""
        state = ChannelState(
            data=data,
            collect_frame=timing.collect_frame,
            collect_time=timing.collect_time,
            receive_frame=current_frame,
            receive_time=time.time(),
            is_stale=timing.is_stale,
        )
        
        # 保存历史
        if channel not in self.history:
            self.history[channel] = deque(maxlen=self.max_history)
        self.history[channel].append(state)
        
        # 更新当前状态
        self.channels[channel] = state
        self.current_frame = max(self.current_frame, current_frame)
    
    def get_channel(self, channel: str) -> Optional[ChannelState]:
        """获取通道状态"""
        return self.channels.get(channel)
    
    def get_channel_data(self, channel: str) -> Optional[Any]:
        """获取通道数据（仅数据，不含时序信息）"""
        state = self.channels.get(channel)
        return state.data if state else None
    
    def is_channel_fresh(self, channel: str, max_stale_frames: int = 5) -> bool:
        """检查通道数据是否新鲜"""
        state = self.channels.get(channel)
        if not state:
            return False
        return (self.current_frame - state.collect_frame) <= max_stale_frames
    
    def get_channel_age(self, channel: str) -> int:
        """获取通道数据年龄（帧数）"""
        state = self.channels.get(channel)
        if not state:
            return -1
        return self.current_frame - state.collect_frame
    
    def get_synchronized_snapshot(
        self,
        channels: List[str],
        max_frame_diff: int = 5
    ) -> Optional[Dict[str, Any]]:
        """获取同步的多通道快照
        
        只有当所有请求的通道的采集帧差异在阈值内时才返回。
        用于需要多个通道数据同步的场景（如 AI 决策）。
        
        Args:
            channels: 需要同步的通道列表
            max_frame_diff: 最大允许的帧差异
            
        Returns:
            同步的数据快照，如果无法同步则返回 None
        """
        states = []
        for channel in channels:
            state = self.channels.get(channel)
            if not state:
                return None
            states.append((channel, state))
        
        # 检查帧差异
        frames = [s.collect_frame for _, s in states]
        if max(frames) - min(frames) > max_frame_diff:
            logger.warning(
                f"Channels not synchronized: {dict(zip(channels, frames))}"
            )
            return None
        
        return {channel: state.data for channel, state in states}
    
    def get_state_at_frame(self, channel: str, target_frame: int) -> Optional[Any]:
        """获取指定帧的通道数据（用于回放）"""
        history = self.history.get(channel, [])
        
        # 查找最接近目标帧的数据
        best_match = None
        best_diff = float('inf')
        
        for state in history:
            diff = abs(state.collect_frame - target_frame)
            if diff < best_diff:
                best_diff = diff
                best_match = state
        
        return best_match.data if best_match else None
```

### 4.3 核心模块设计

#### 4.3.1 协议模式定义 (protocol/schema.py)

使用 Pydantic 定义严格的数据模式，实现运行时类型验证：

```python
# protocol/schema.py
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Union
from enum import Enum


class ProtocolVersion(str, Enum):
    V2_0 = "2.0"
    V2_1 = "2.1"  # 当前版本


class MessageType(str, Enum):
    DATA = "DATA"
    FULL_STATE = "FULL"
    EVENT = "EVENT"
    COMMAND = "CMD"


class Vector2DSchema(BaseModel):
    """二维向量模式"""
    x: float = 0.0
    y: float = 0.0
    
    class Config:
        frozen = True  # 不可变


class PlayerPositionSchema(BaseModel):
    """玩家位置数据模式"""
    pos: Vector2DSchema
    vel: Vector2DSchema
    move_dir: int = Field(ge=-1, le=7, default=0)
    fire_dir: int = Field(ge=-1, le=7, default=0)
    head_dir: int = Field(ge=-1, le=7, default=0)
    aim_dir: Vector2DSchema
    
    @validator('aim_dir', pre=True)
    def handle_zero_aim(cls, v):
        """处理已知游戏问题：aim_dir 可能为 (0,0)"""
        if isinstance(v, dict) and v.get('x') == 0 and v.get('y') == 0:
            # 标记为已知问题，不是错误
            pass
        return v


class EnemySchema(BaseModel):
    """敌人数据模式"""
    id: int
    type: int
    variant: int = 0
    subtype: int = 0
    pos: Vector2DSchema
    vel: Vector2DSchema
    hp: float
    max_hp: float
    is_boss: bool = False
    is_champion: bool = False
    state: int = 0
    collision_radius: float = 10.0
    distance: float = 0.0
    
    @validator('hp', pre=True)
    def handle_negative_hp(cls, v):
        """处理已知游戏问题：负数 HP"""
        if v < 0:
            return 0.0
        return v
    
    @validator('hp')
    def hp_not_exceed_max(cls, v, values):
        """处理已知游戏问题：HP > max_hp"""
        max_hp = values.get('max_hp', v)
        if v > max_hp:
            return max_hp
        return v


class DataMessageSchema(BaseModel):
    """完整数据消息模式"""
    version: str = ProtocolVersion.V2_1.value
    type: MessageType = Field(alias='msg_type')
    timestamp: int
    frame: int = Field(ge=0)
    room_index: int = Field(ge=-1)
    payload: Optional[Dict[str, Any]] = None
    channels: Optional[List[str]] = None
    
    class Config:
        populate_by_name = True  # 支持别名
```

#### 4.3.2 数据通道注册系统 (channels/base.py)

```python
# channels/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Type, TypeVar, Generic
from pydantic import BaseModel
import logging

T = TypeVar('T', bound=BaseModel)

logger = logging.getLogger(__name__)


class DataChannel(ABC, Generic[T]):
    """数据通道抽象基类
    
    每个数据通道负责：
    1. 定义数据模式（Schema）
    2. 解析原始 JSON
    3. 验证数据有效性
    4. 处理已知游戏问题
    5. 转换为标准化模型
    """
    
    name: str  # 通道名称（与 Lua 端一致）
    schema: Type[T]  # Pydantic 模式类
    
    @abstractmethod
    def parse(self, raw_data: Any, frame: int) -> T:
        """解析原始数据
        
        Args:
            raw_data: 从 JSON 解析的原始数据
            frame: 当前帧号
            
        Returns:
            标准化的数据对象
            
        Raises:
            ValidationError: 数据验证失败
        """
        pass
    
    @abstractmethod
    def validate(self, data: T) -> List[ValidationIssue]:
        """额外验证逻辑
        
        Returns:
            验证问题列表（空列表表示无问题）
        """
        pass
    
    def on_known_issue(self, issue_type: str, details: Dict[str, Any]):
        """处理已知游戏问题的钩子"""
        logger.debug(f"[{self.name}] Known issue: {issue_type} - {details}")


class ChannelRegistry:
    """数据通道注册中心"""
    
    _channels: Dict[str, DataChannel] = {}
    
    @classmethod
    def register(cls, channel: DataChannel):
        """注册数据通道"""
        cls._channels[channel.name] = channel
        logger.info(f"Registered channel: {channel.name}")
    
    @classmethod
    def get(cls, name: str) -> Optional[DataChannel]:
        """获取数据通道"""
        return cls._channels.get(name)
    
    @classmethod
    def parse_payload(cls, payload: Dict[str, Any], frame: int) -> Dict[str, Any]:
        """解析整个 payload"""
        results = {}
        for channel_name, raw_data in payload.items():
            channel = cls.get(channel_name)
            if channel:
                try:
                    results[channel_name] = channel.parse(raw_data, frame)
                except Exception as e:
                    logger.error(f"Failed to parse {channel_name}: {e}")
            else:
                logger.warning(f"Unknown channel: {channel_name}")
                results[channel_name] = raw_data  # 保留原始数据
        return results
```

#### 4.3.3 玩家数据通道示例 (channels/player.py)

```python
# channels/player.py
from typing import Any, Dict, List, Union
from .base import DataChannel, ChannelRegistry
from ..protocol.schema import PlayerPositionSchema, Vector2DSchema
from ..validation.issues import ValidationIssue, IssueSeverity


class PlayerPositionChannel(DataChannel[Dict[int, PlayerPositionSchema]]):
    """玩家位置数据通道"""
    
    name = "PLAYER_POSITION"
    schema = PlayerPositionSchema
    
    def parse(self, raw_data: Any, frame: int) -> Dict[int, PlayerPositionSchema]:
        """解析玩家位置数据
        
        处理 Lua 数组两种可能的 JSON 格式：
        1. JSON 数组: [{pos:..}, {pos:..}]
        2. JSON 对象: {"1": {pos:..}, "2": {pos:..}}
        """
        result = {}
        
        if isinstance(raw_data, list):
            # JSON 数组格式
            for idx, player_data in enumerate(raw_data):
                player_idx = idx + 1  # Lua 1-based
                result[player_idx] = self._parse_single(player_data, player_idx)
                
        elif isinstance(raw_data, dict):
            # JSON 对象格式
            for key, player_data in raw_data.items():
                try:
                    player_idx = int(key)
                    result[player_idx] = self._parse_single(player_data, player_idx)
                except ValueError:
                    continue
        
        return result
    
    def _parse_single(self, data: Dict, player_idx: int) -> PlayerPositionSchema:
        """解析单个玩家数据"""
        # 处理可能缺失的字段
        pos = data.get('pos', {'x': 0, 'y': 0})
        vel = data.get('vel', {'x': 0, 'y': 0})
        aim_dir = data.get('aim_dir', {'x': 0, 'y': 0})
        
        return PlayerPositionSchema(
            pos=Vector2DSchema(**pos),
            vel=Vector2DSchema(**vel),
            move_dir=data.get('move_dir', 0),
            fire_dir=data.get('fire_dir', 0),
            head_dir=data.get('head_dir', 0),
            aim_dir=Vector2DSchema(**aim_dir),
        )
    
    def validate(self, data: Dict[int, PlayerPositionSchema]) -> List[ValidationIssue]:
        issues = []
        for player_idx, player in data.items():
            # 检查 aim_dir 为零（已知游戏问题）
            if player.aim_dir.x == 0 and player.aim_dir.y == 0:
                issues.append(ValidationIssue(
                    channel=self.name,
                    severity=IssueSeverity.INFO,
                    issue_type="AIM_DIR_ZERO",
                    message=f"Player {player_idx} aim_dir is (0,0)",
                    is_game_side=True,  # 标记为游戏端问题
                ))
        return issues


# 注册通道
ChannelRegistry.register(PlayerPositionChannel())
```

#### 4.3.4 验证与已知问题管理 (validation/known_issues.py)

```python
# validation/known_issues.py
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any, Callable


class IssueSource(Enum):
    """问题来源"""
    GAME_API = "game_api"  # 游戏 API 问题
    LUA_IMPL = "lua_impl"  # Lua 端实现问题
    PYTHON_IMPL = "python_impl"  # Python 端实现问题
    UNKNOWN = "unknown"


class IssueSeverity(Enum):
    """问题严重程度"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    INFO = 5


@dataclass
class KnownIssue:
    """已知问题定义"""
    id: str
    channel: str
    severity: IssueSeverity
    source: IssueSource
    description: str
    detection_rule: Callable[[Any], bool]
    sanitizer: Optional[Callable[[Any], Any]] = None
    documentation_url: Optional[str] = None


class KnownIssueRegistry:
    """已知问题注册中心
    
    集中管理所有已知的游戏端和实现端问题，
    提供检测和修正功能。
    """
    
    _issues: Dict[str, KnownIssue] = {}
    _by_channel: Dict[str, List[KnownIssue]] = {}
    
    @classmethod
    def register(cls, issue: KnownIssue):
        """注册已知问题"""
        cls._issues[issue.id] = issue
        if issue.channel not in cls._by_channel:
            cls._by_channel[issue.channel] = []
        cls._by_channel[issue.channel].append(issue)
    
    @classmethod
    def detect_issues(cls, channel: str, data: Any) -> List[KnownIssue]:
        """检测数据中的已知问题"""
        detected = []
        for issue in cls._by_channel.get(channel, []):
            if issue.detection_rule(data):
                detected.append(issue)
        return detected
    
    @classmethod
    def sanitize(cls, channel: str, data: Any) -> Any:
        """修正已知问题的数据"""
        result = data
        for issue in cls._by_channel.get(channel, []):
            if issue.sanitizer and issue.detection_rule(data):
                result = issue.sanitizer(result)
        return result


# 注册已知问题
KnownIssueRegistry.register(KnownIssue(
    id="ENEMY_NEGATIVE_HP",
    channel="ENEMIES",
    severity=IssueSeverity.MEDIUM,
    source=IssueSource.GAME_API,
    description="某些敌人类型在受伤或死亡时会短暂报告负数 HP 值",
    detection_rule=lambda enemies: any(e.get('hp', 0) < 0 for e in enemies) if isinstance(enemies, list) else False,
    sanitizer=lambda enemies: [{**e, 'hp': max(0, e.get('hp', 0))} for e in enemies],
    documentation_url="KNOWN_GAME_ISSUES.md#4-负数-hp-问题"
))

KnownIssueRegistry.register(KnownIssue(
    id="PLAYER_AIM_DIR_ZERO",
    channel="PLAYER_POSITION",
    severity=IssueSeverity.INFO,
    source=IssueSource.GAME_API,
    description="当玩家不瞄准时，aim_dir 可能返回 (0, 0)",
    detection_rule=lambda data: any(
        p.get('aim_dir', {}).get('x') == 0 and p.get('aim_dir', {}).get('y') == 0
        for p in (data.values() if isinstance(data, dict) else data if isinstance(data, list) else [])
    ),
    sanitizer=None,  # 不需要修正，只是标记
    documentation_url="KNOWN_GAME_ISSUES.md#3-aim_dir-0-0-问题"
))

KnownIssueRegistry.register(KnownIssue(
    id="GRID_FIREPLACE_DEPRECATED",
    channel="ROOM_LAYOUT",
    severity=IssueSeverity.LOW,
    source=IssueSource.GAME_API,
    description="游戏 API 已废弃 GRID_FIREPLACE (ID 13)",
    detection_rule=lambda data: any(
        g.get('type') == 13 for g in data.get('grid', {}).values()
    ) if isinstance(data, dict) else False,
    sanitizer=lambda data: {
        **data,
        'grid': {k: v for k, v in data.get('grid', {}).items() if v.get('type') != 13}
    },
    documentation_url="KNOWN_GAME_ISSUES.md#1-grid_fireplace-id-13-问题"
))
```

#### 4.3.5 数据质量监控服务 (services/monitor.py)

```python
# services/monitor.py
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any
from collections import deque
from threading import Lock

from ..validation.known_issues import KnownIssueRegistry, KnownIssue, IssueSeverity


logger = logging.getLogger(__name__)


@dataclass
class ChannelMetrics:
    """通道统计指标"""
    channel: str
    message_count: int = 0
    validation_pass: int = 0
    validation_fail: int = 0
    known_issues_count: Dict[str, int] = field(default_factory=dict)
    last_update_frame: int = -1
    avg_processing_time_ms: float = 0.0


@dataclass
class DataQualityReport:
    """数据质量报告"""
    timestamp: float
    duration_seconds: float
    total_messages: int
    channel_metrics: Dict[str, ChannelMetrics]
    top_issues: List[Dict[str, Any]]
    game_side_issue_rate: float
    python_side_issue_rate: float


class DataQualityMonitor:
    """数据质量监控器
    
    实时监控数据质量，区分游戏端和 Python 端问题，
    生成质量报告。
    """
    
    def __init__(self, report_interval_seconds: float = 60.0):
        self.report_interval = report_interval_seconds
        self.start_time = time.time()
        self.channel_metrics: Dict[str, ChannelMetrics] = {}
        self.issue_history: deque = deque(maxlen=10000)
        self.lock = Lock()
        self.enabled = True
        
        # 计数器
        self.total_messages = 0
        self.game_side_issues = 0
        self.python_side_issues = 0
    
    def record_message(self, channel: str, frame: int, processing_time_ms: float):
        """记录消息处理"""
        if not self.enabled:
            return
        
        with self.lock:
            if channel not in self.channel_metrics:
                self.channel_metrics[channel] = ChannelMetrics(channel=channel)
            
            metrics = self.channel_metrics[channel]
            metrics.message_count += 1
            metrics.last_update_frame = frame
            
            # 滚动平均
            n = metrics.message_count
            metrics.avg_processing_time_ms = (
                metrics.avg_processing_time_ms * (n - 1) + processing_time_ms
            ) / n
            
            self.total_messages += 1
    
    def record_validation(self, channel: str, passed: bool):
        """记录验证结果"""
        if not self.enabled:
            return
        
        with self.lock:
            if channel in self.channel_metrics:
                if passed:
                    self.channel_metrics[channel].validation_pass += 1
                else:
                    self.channel_metrics[channel].validation_fail += 1
    
    def record_known_issue(self, issue: KnownIssue, frame: int, details: Dict = None):
        """记录已知问题"""
        if not self.enabled:
            return
        
        with self.lock:
            if issue.channel in self.channel_metrics:
                metrics = self.channel_metrics[issue.channel]
                if issue.id not in metrics.known_issues_count:
                    metrics.known_issues_count[issue.id] = 0
                metrics.known_issues_count[issue.id] += 1
            
            self.issue_history.append({
                'issue_id': issue.id,
                'channel': issue.channel,
                'severity': issue.severity.name,
                'source': issue.source.value,
                'frame': frame,
                'timestamp': time.time(),
                'details': details or {},
            })
            
            if issue.source.value == 'game_api':
                self.game_side_issues += 1
            else:
                self.python_side_issues += 1
    
    def generate_report(self) -> DataQualityReport:
        """生成数据质量报告"""
        with self.lock:
            duration = time.time() - self.start_time
            total_issues = self.game_side_issues + self.python_side_issues
            
            # 统计 Top Issues
            issue_counts = {}
            for item in self.issue_history:
                key = item['issue_id']
                if key not in issue_counts:
                    issue_counts[key] = {'count': 0, 'issue_id': key, 'source': item['source']}
                issue_counts[key]['count'] += 1
            
            top_issues = sorted(issue_counts.values(), key=lambda x: x['count'], reverse=True)[:10]
            
            return DataQualityReport(
                timestamp=time.time(),
                duration_seconds=duration,
                total_messages=self.total_messages,
                channel_metrics=dict(self.channel_metrics),
                top_issues=top_issues,
                game_side_issue_rate=self.game_side_issues / max(total_issues, 1),
                python_side_issue_rate=self.python_side_issues / max(total_issues, 1),
            )
    
    def print_report(self):
        """打印报告到日志"""
        report = self.generate_report()
        
        logger.info("=" * 60)
        logger.info("DATA QUALITY REPORT")
        logger.info("=" * 60)
        logger.info(f"Duration: {report.duration_seconds:.1f}s")
        logger.info(f"Total Messages: {report.total_messages}")
        logger.info(f"Game-side Issue Rate: {report.game_side_issue_rate:.1%}")
        logger.info(f"Python-side Issue Rate: {report.python_side_issue_rate:.1%}")
        logger.info("-" * 60)
        logger.info("TOP ISSUES:")
        for issue in report.top_issues[:5]:
            logger.info(f"  {issue['issue_id']}: {issue['count']} ({issue['source']})")
        logger.info("=" * 60)
```

#### 4.3.6 统一门面 API (services/facade.py)

```python
# services/facade.py
"""
SocketBridge Facade API

提供简化的、类型安全的 API 供上层应用使用。
隐藏底层复杂性，提供一致的接口。
"""

from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass
import logging

from ..core.connection.bridge import IsaacBridgeCore
from ..models.entities import PlayerData, EnemyData, ProjectileData
from ..models.state import GameStateManager
from ..services.monitor import DataQualityMonitor
from ..validation.known_issues import KnownIssueRegistry


logger = logging.getLogger(__name__)


@dataclass
class PlayerSnapshot:
    """玩家状态快照（只读）"""
    player_idx: int
    x: float
    y: float
    vel_x: float
    vel_y: float
    health: float
    max_health: float
    damage: float
    speed: float
    can_fly: bool


@dataclass
class EnemySnapshot:
    """敌人状态快照（只读）"""
    enemy_id: int
    x: float
    y: float
    vel_x: float
    vel_y: float
    hp: float
    max_hp: float
    is_boss: bool
    distance_to_player: float


class SocketBridgeFacade:
    """SocketBridge 门面 API
    
    提供简化的接口供上层应用使用。
    
    示例:
        bridge = SocketBridgeFacade()
        bridge.start()
        
        @bridge.on_data
        def handle_data(frame: int, room: int):
            player = bridge.get_player()
            enemies = bridge.get_enemies()
            print(f"Frame {frame}: Player at ({player.x}, {player.y})")
            
            if bridge.is_in_danger():
                bridge.send_move(-1, 0)  # 向左移动
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 9527):
        self._bridge = IsaacBridgeCore(host, port)
        self._state = GameStateManager()
        self._monitor = DataQualityMonitor()
        self._data_callbacks: List[Callable] = []
        self._event_callbacks: Dict[str, List[Callable]] = {}
        
        # 内部事件绑定
        self._bridge.on_message(self._handle_message)
        self._bridge.on_event(self._handle_event)
    
    def start(self):
        """启动连接"""
        self._bridge.start()
        logger.info("SocketBridge started")
    
    def stop(self):
        """停止连接"""
        self._monitor.print_report()
        self._bridge.stop()
        logger.info("SocketBridge stopped")
    
    # ==================== 玩家数据 ====================
    
    def get_player(self, player_idx: int = 1) -> Optional[PlayerSnapshot]:
        """获取玩家快照
        
        Returns:
            PlayerSnapshot 或 None（如果玩家不存在）
        """
        player = self._state.get_player(player_idx)
        if not player:
            return None
        
        return PlayerSnapshot(
            player_idx=player_idx,
            x=player.position.x,
            y=player.position.y,
            vel_x=player.velocity.x,
            vel_y=player.velocity.y,
            health=player.health,
            max_health=player.max_health,
            damage=player.damage,
            speed=player.speed,
            can_fly=player.can_fly,
        )
    
    # ==================== 敌人数据 ====================
    
    def get_enemies(self, max_distance: float = None) -> List[EnemySnapshot]:
        """获取敌人列表
        
        Args:
            max_distance: 最大距离过滤（可选）
            
        Returns:
            敌人快照列表，按距离排序
        """
        player = self._state.get_player(1)
        if not player:
            return []
        
        enemies = self._state.get_active_enemies()
        snapshots = []
        
        for enemy in enemies:
            dist = player.position.distance_to(enemy.position)
            if max_distance and dist > max_distance:
                continue
            
            snapshots.append(EnemySnapshot(
                enemy_id=enemy.id,
                x=enemy.position.x,
                y=enemy.position.y,
                vel_x=enemy.velocity.x,
                vel_y=enemy.velocity.y,
                hp=enemy.hp,
                max_hp=enemy.max_hp,
                is_boss=enemy.is_boss,
                distance_to_player=dist,
            ))
        
        # 按距离排序
        return sorted(snapshots, key=lambda e: e.distance_to_player)
    
    def get_nearest_enemy(self) -> Optional[EnemySnapshot]:
        """获取最近的敌人"""
        enemies = self.get_enemies()
        return enemies[0] if enemies else None
    
    # ==================== 危险判断 ====================
    
    def is_in_danger(self, danger_radius: float = 100.0) -> bool:
        """判断玩家是否处于危险中
        
        检查：
        1. 附近是否有敌人
        2. 附近是否有敌方投射物
        """
        enemies = self.get_enemies(max_distance=danger_radius)
        projectiles = self._state.get_enemy_projectiles_near_player(danger_radius)
        return len(enemies) > 0 or len(projectiles) > 0
    
    def get_danger_level(self) -> float:
        """获取危险等级 (0.0 - 1.0)"""
        enemies = self.get_enemies()
        projectiles = self._state.get_enemy_projectiles()
        
        enemy_threat = sum(1 / max(e.distance_to_player, 10) for e in enemies)
        projectile_threat = len(projectiles) * 0.1
        
        total_threat = enemy_threat + projectile_threat
        return min(1.0, total_threat / 5.0)  # 归一化
    
    # ==================== 控制指令 ====================
    
    def send_move(self, dx: int, dy: int):
        """发送移动指令
        
        Args:
            dx: X 方向 (-1, 0, 1)
            dy: Y 方向 (-1, 0, 1)
        """
        self._bridge.send_input(move=(dx, dy))
    
    def send_shoot(self, dx: int, dy: int):
        """发送射击指令"""
        self._bridge.send_input(shoot=(dx, dy))
    
    def send_move_and_shoot(self, move_dx: int, move_dy: int, shoot_dx: int, shoot_dy: int):
        """同时发送移动和射击指令"""
        self._bridge.send_input(move=(move_dx, move_dy), shoot=(shoot_dx, shoot_dy))
    
    def use_bomb(self):
        """使用炸弹"""
        self._bridge.send_input(use_bomb=True)
    
    def use_item(self):
        """使用主动道具"""
        self._bridge.send_input(use_item=True)
    
    # ==================== 事件回调 ====================
    
    def on_data(self, callback: Callable[[int, int], None]):
        """注册数据回调
        
        Args:
            callback: 回调函数 (frame, room_index) -> None
        """
        self._data_callbacks.append(callback)
        return callback
    
    def on_event(self, event_type: str):
        """注册事件回调（装饰器）
        
        Args:
            event_type: 事件类型 (ROOM_ENTER, PLAYER_DAMAGE, etc.)
        """
        def decorator(callback: Callable):
            if event_type not in self._event_callbacks:
                self._event_callbacks[event_type] = []
            self._event_callbacks[event_type].append(callback)
            return callback
        return decorator
    
    # ==================== 房间数据 ====================
    
    @property
    def frame(self) -> int:
        """当前帧号"""
        return self._state.frame
    
    @property
    def room_index(self) -> int:
        """当前房间索引"""
        return self._state.room_index
    
    @property
    def is_room_clear(self) -> bool:
        """房间是否已清空"""
        return self._state.is_room_clear
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._bridge.is_connected
    
    # ==================== 质量监控 ====================
    
    def get_quality_report(self) -> Dict[str, Any]:
        """获取数据质量报告"""
        report = self._monitor.generate_report()
        return {
            'duration_seconds': report.duration_seconds,
            'total_messages': report.total_messages,
            'game_side_issue_rate': report.game_side_issue_rate,
            'python_side_issue_rate': report.python_side_issue_rate,
            'top_issues': report.top_issues,
        }
    
    # ==================== 内部方法 ====================
    
    def _handle_message(self, msg):
        """处理收到的消息"""
        # 更新状态
        self._state.update_from_message(msg)
        
        # 检测已知问题
        for channel in msg.channels or []:
            data = msg.payload.get(channel) if msg.payload else None
            if data:
                issues = KnownIssueRegistry.detect_issues(channel, data)
                for issue in issues:
                    self._monitor.record_known_issue(issue, msg.frame)
        
        # 触发回调
        for callback in self._data_callbacks:
            try:
                callback(msg.frame, msg.room_index)
            except Exception as e:
                logger.error(f"Data callback error: {e}")
    
    def _handle_event(self, event):
        """处理游戏事件"""
        callbacks = self._event_callbacks.get(event.type, [])
        for callback in callbacks:
            try:
                callback(event.data)
            except Exception as e:
                logger.error(f"Event callback error: {e}")
```

### 4.4 协议扩展流程

当需要添加新的数据通道时，遵循以下步骤：

#### Step 1: Lua 端添加收集器

```lua
-- main.lua
CollectorRegistry:register("NEW_CHANNEL", {
    interval = "MEDIUM",
    priority = 5,
    collect = function()
        -- 收集数据逻辑
        return { ... }
    end
})
```

#### Step 2: Python 端定义 Schema

```python
# protocol/schema.py
class NewChannelSchema(BaseModel):
    """新通道数据模式"""
    field1: int
    field2: str
    optional_field: Optional[float] = None
    
    @validator('field1')
    def validate_field1(cls, v):
        # 添加验证逻辑
        return v
```

#### Step 3: 实现数据通道

```python
# channels/new_channel.py
class NewChannel(DataChannel[NewChannelSchema]):
    name = "NEW_CHANNEL"
    schema = NewChannelSchema
    
    def parse(self, raw_data: Any, frame: int) -> NewChannelSchema:
        return NewChannelSchema(**raw_data)
    
    def validate(self, data: NewChannelSchema) -> List[ValidationIssue]:
        return []

# 注册
ChannelRegistry.register(NewChannel())
```

#### Step 4: 更新文档

```markdown
# DATA_PROTOCOL.md

## NEW_CHANNEL - 新通道（采集频率）

**JSON 结构**:
```json
{
    "field1": 123,
    "field2": "value"
}
```
```

### 4.5 目录结构

重构后的目录结构：

```
python/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── connection/
│   │   ├── __init__.py
│   │   ├── bridge.py          # TCP 服务器核心
│   │   └── events.py          # 事件系统
│   ├── protocol/
│   │   ├── __init__.py
│   │   ├── schema.py          # Pydantic 模式定义
│   │   ├── messages.py        # 消息类型定义
│   │   ├── version.py         # 协议版本管理
│   │   └── timing.py          # 时序处理（新增）
│   └── validation/
│       ├── __init__.py
│       ├── validators.py      # 验证器
│       ├── sanitizers.py      # 数据修正器
│       └── known_issues.py    # 已知问题注册
├── models/
│   ├── __init__.py
│   ├── base.py               # Vector2D, Enums
│   ├── entities.py           # PlayerData, EnemyData, etc.
│   └── state.py              # GameStateData, TimingAwareStateManager（增强）
├── channels/
│   ├── __init__.py
│   ├── base.py               # DataChannel ABC, Registry
│   ├── player.py             # PLAYER_* 通道
│   ├── room.py               # ROOM_* 通道
│   ├── entities.py           # ENEMIES, PROJECTILES, PICKUPS
│   └── hazards.py            # BOMBS, FIRE_HAZARDS
├── services/
│   ├── __init__.py
│   ├── processor.py          # 数据处理服务
│   ├── monitor.py            # 质量监控服务（集成时序监控）
│   └── facade.py             # 统一 API 门面
├── apps/                     # 上层应用（已有）
│   ├── ...
└── tests/                    # 测试
    ├── __init__.py
    ├── test_schema.py
    ├── test_channels.py
    ├── test_validation.py
    └── fixtures/             # 测试数据
        └── sample_messages.json
```

---

## 5. 实施路线图

### Phase 0: 协议时序扩展（优先，1 周）✅ 已完成

**目标**: 解决数据时序问题，为后续重构奠定基础

| 任务 | 预估时间 | 优先级 | 状态 |
|-----|---------|-------|------|
| **Lua 端**：扩展 Protocol 添加时序字段 | 1 天 | P0 | ✅ |
| **Lua 端**：CollectorRegistry 记录采集帧号 | 0.5 天 | P0 | ✅ |
| **Lua 端**：添加消息序列号机制 | 0.5 天 | P0 | ✅ |
| **Python 端**：创建 `core/protocol/timing.py` | 1 天 | P0 | ✅ |
| **Python 端**：实现 TimingMonitor | 1 天 | P0 | ✅ |
| **Python 端**：实现 TimingAwareStateManager | 1.5 天 | P0 | ✅ |
| 编写时序相关测试 | 1 天 | P1 | ✅ |
| 更新 DATA_PROTOCOL.md 文档 | 0.5 天 | P1 | 待定 |

**验收标准**:
- 协议版本升级到 v2.1
- 每个通道数据包含独立的 collect_frame
- Python 端可检测帧丢失、乱序、数据过期
- 时序问题有统计报告

**关键代码变更**:

```lua
-- Lua 端协议升级关键点
-- 1. State 新增字段
State.messageSeq = 0
State.channelLastCollect = {}

-- 2. createDataMessage 新增 channel_meta
channel_meta = {
    [channelName] = {
        collect_frame = ...,
        collect_time = ...,
        interval = ...,
        stale_frames = ...,
    }
}
```

```python
# Python 端关键接口
timing_info = MessageTimingInfo.from_message(msg)
issues = timing_monitor.check_message(timing_info)

# 时序感知状态访问
if state_manager.is_channel_fresh("PLAYER_STATS", max_stale_frames=10):
    # 使用数据
else:
    # 数据过期，使用缓存或跳过
```

### Phase 1: 基础设施（1-2 周）✅ 已完成

**目标**: 建立核心基础设施，不破坏现有功能

| 任务 | 预估时间 | 优先级 | 状态 |
|-----|---------|-------|------|
| 创建 `core/protocol/schema.py`，定义核心 Pydantic 模式 | 2 天 | P0 | ✅ |
| 创建 `core/validation/known_issues.py`，迁移已知问题 | 1 天 | P0 | ✅ |
| 创建 `channels/base.py`，实现通道注册机制 | 1 天 | P0 | ✅ |
| 实现 PLAYER_POSITION 通道作为模板 | 1 天 | P0 | ✅ |
| 集成 Phase 0 的时序模块 | 1 天 | P0 | ✅ |
| 编写基础测试 | 2 天 | P1 | ✅ |

**验收标准**:
- 新模块可独立运行
- 原有代码不受影响
- 至少一个通道完成迁移
- 时序信息可访问

### Phase 2: 通道迁移（2-3 周）

**目标**: 将所有数据通道迁移到新架构

| 任务 | 预估时间 | 优先级 |
|-----|---------|-------|
| 迁移玩家相关通道 (STATS, HEALTH, INVENTORY) | 2 天 | P0 |
| 迁移房间相关通道 (ROOM_INFO, ROOM_LAYOUT) | 2 天 | P0 |
| 迁移实体通道 (ENEMIES, PROJECTILES, PICKUPS) | 3 天 | P0 |
| 迁移危险物通道 (BOMBS, FIRE_HAZARDS) | 1 天 | P1 |
| 迁移 INTERACTABLES, BUTTONS | 1 天 | P1 |
| 编写集成测试 | 2 天 | P1 |

**验收标准**:
- 所有通道完成迁移
- 集成测试通过
- 验证与原逻辑一致

### Phase 3: 服务层与监控（1-2 周）

**目标**: 实现数据质量监控和服务层

| 任务 | 预估时间 | 优先级 |
|-----|---------|-------|
| 实现 `services/monitor.py` | 2 天 | P0 |
| 实现 `services/processor.py` 整合所有通道 | 2 天 | P0 |
| 实现 `services/facade.py` 简化 API | 2 天 | P1 |
| 集成监控到主流程 | 1 天 | P1 |
| 质量报告功能 | 1 天 | P2 |

**验收标准**:
- 监控系统实时运行
- 能区分游戏端和 Python 端问题
- 提供质量报告

### Phase 4: 清理与文档（1 周）

**目标**: 清理旧代码，完善文档

| 任务 | 预估时间 | 优先级 |
|-----|---------|-------|
| 重构 `models.py`，拆分为模块 | 2 天 | P1 |
| 弃用旧代码路径，保留兼容层 | 1 天 | P1 |
| 更新 `DATA_PROTOCOL.md` | 1 天 | P0 |
| 更新 `README.md` | 0.5 天 | P1 |
| 编写迁移指南 | 0.5 天 | P1 |

**验收标准**:
- 文档完整更新
- 迁移指南可用
- CI 通过

### Phase 5: 上层应用适配（持续）

**目标**: 逐步将 `apps/` 下的应用迁移到新 API

| 任务 | 预估时间 | 优先级 |
|-----|---------|-------|
| 选择 2-3 个核心应用作为试点 | 3 天 | P1 |
| 收集反馈，迭代 Facade API | 持续 | P2 |
| 编写最佳实践文档 | 1 天 | P2 |

---

## 6. 风险评估与缓解措施

### 6.1 风险清单

| 风险 | 可能性 | 影响 | 缓解措施 |
|-----|-------|------|---------|
| Pydantic 性能影响 | 中 | 中 | 可选的验证模式，关键路径可跳过验证 |
| 向后兼容性破坏 | 中 | 高 | 保留兼容层，分阶段迁移 |
| 测试覆盖不足 | 中 | 中 | 使用真实游戏数据录制作为测试用例 |
| 开发时间超预期 | 高 | 中 | 优先核心功能，非必要功能延后 |
| 新架构学习成本 | 中 | 低 | 详细文档和示例代码 |

### 6.2 回滚策略

1. **Git 分支策略**：使用 `refactor/v2` 分支进行开发
2. **功能开关**：关键功能通过配置开关控制
3. **兼容层**：保留旧 API 作为别名
4. **快速回滚**：确保可随时切换回 `main` 分支

### 6.3 依赖管理

新增依赖：
- `pydantic>=2.0`：数据验证
- `typing-extensions`：类型注解扩展

安装命令：
```bash
uv pip install pydantic typing-extensions
```

---

## 附录

### A. 相关文档

- [DATA_PROTOCOL.md](python/DATA_PROTOCOL.md) - 数据协议详细文档
- [KNOWN_GAME_ISSUES.md](KNOWN_GAME_ISSUES.md) - 已知游戏问题
- [ARCHITECTURE_ANALYSIS.md](python/ARCHITECTURE_ANALYSIS.md) - 架构分析

### B. 参考资料

- [Pydantic 文档](https://docs.pydantic.dev/)
- [Python typing 模块](https://docs.python.org/3/library/typing.html)
- [《以撒的结合》Modding API 文档](https://moddingofisaac.com/)

### C. 变更日志

| 日期 | 版本 | 变更内容 |
|-----|------|---------|
| 2026-02-02 | 1.0 | 初始版本 |
| 2026-02-02 | 1.1 | Phase 0 完成：时序协议 v2.1 实现，TimingMonitor 和 TimingAwareStateManager 完成 |
| 2026-02-02 | 1.1 | Phase 1 完成：Pydantic schema、已知问题注册表、通道框架、73个测试用例全部通过 |

---

*本文档由项目团队维护，如有问题请联系项目负责人。*
