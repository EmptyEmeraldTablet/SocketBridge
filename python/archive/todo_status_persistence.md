# 状态保持功能开发任务清单

> **分支**: `test/status-persistence`
> **创建时间**: 2026-01-13
> **最后更新**: 2026-01-14

---

## 概述

本分支实现了游戏数据通道的状态保持功能，确保低频数据通道（如 `PLAYER_STATS`）不会被高频通道（如 `ENEMIES`）的更新所覆盖。

**已完成功能:**
- ✅ 状态保持机制 (`mark_channel_updated`, `is_channel_stale`)
- ✅ 实体过期清理 (`cleanup_stale_entities`)
- ✅ 新数据通道解析 (`PLAYER_STATS`, `PLAYER_HEALTH`, `BUTTONS`, `FIRE_HAZARDS`, `INTERACTABLES`, `BOMBS`, `DESTRUCTIBLES`)
- ✅ 提交: `77fc68a feat: Add state persistence for game data channels`

---

## 任务列表

### P0 - 紧急 (当前迭代必须完成)

| ID | 任务 | 状态 | 负责人 | 优先级 | 预估工时 | 备注 |
|----|------|------|--------|--------|----------|------|
| P0-001 | 在 strategy_system.py 中使用 player_stats 数据 | ✅ 已完成 | - | P0 | 2h | GameContext 新增 player_stats 字段 |
| P0-002 | 统一 player 数据访问入口 (PlayerData + player_stats) | ✅ 已完成 | - | P0 | 4h | 添加 get_primary_player_stats() 方法 |

### P1 - 高优先级 (建议本分支完成)

| ID | 任务 | 状态 | 负责人 | 优先级 | 预估工时 | 备注 |
|----|------|------|--------|--------|----------|------|
| P1-001 | 保留 PLAYER_HEALTH 详细心类型数据 | ✅ 已完成 | - | P1 | 2h | 添加 get_primary_player_health_info() 方法 |
| P1-002 | 在 GameStateData 中添加 player 数据快捷访问方法 | ✅ 已完成 | - | P1 | 1h | 添加 get_primary_player_health_ratio() 回退支持 |
| P1-003 | 清理 PlayerData 中冗余的属性字段 | ✅ 已完成 | - | P1 | 2h | 添加文档注释和 get_stats() 方法 |

### P2 - 中优先级 (后续迭代)

| ID | 任务 | 状态 | 负责人 | 优先级 | 预估工时 | 备注 |
|----|------|------|--------|--------|----------|------|
| P2-001 | 将 room 实体集成到环境建模 (buttons, fire_hazards, etc.) | ✅ 已完成 | - | P2 | 6h | environment.py entities 注册表已填充 |
| P2-002 | 在路径规划中避开 room 实体障碍物 | ⏳ 待处理 | - | P2 | 4h | 完善 dynamic_obstacles 逻辑 |
| P2-003 | 为 room 实体添加可交互行为树节点 | ⏳ 待处理 | - | P2 | 8h | AI 能够与机器、按钮等交互 |

### P3 - 低优先级 (功能增强)

| ID | 任务 | 状态 | 负责人 | 优先级 | 预估工时 | 备注 |
|----|------|------|--------|--------|----------|------|
| P3-001 | 添加新通道的单元测试 | ✅ 已完成 | - | P3 | 2h | 测试 state persistence 行为 |
| P3-002 | 添加新通道的集成测试 | ⏳ 待处理 | - | P3 | 4h | 测试完整数据流 |
| P3-003 | 编写新通道的使用文档 | ⏳ 待处理 | - | P3 | 2h | 更新 DATA_PROTOCOL.md |
| P3-004 | 性能优化: 减少状态跟踪开销 | ⏳ 待处理 | - | P3 | 4h | 评估 channel_last_update 的性能影响 |

---

## 问题追踪

### 已识别问题

| ID | 问题描述 | 严重程度 | 状态 | 解决方案 |
|----|----------|----------|------|----------|
| Q-001 | PLAYER_STATS 解析后未被任何模块使用 | 严重 | 已修复 | 在 strategy_system.py 中使用 |
| Q-002 | PLAYER_HEALTH 详细心类型数据可能丢失 | 中等 | 已修复 | 保留 player_health 字典的完整数据 |
| Q-003 | PlayerData 与 player_stats 数据重复 | 低 | 已修复 | 添加文档注释和 get_stats() 方法 |
| Q-004 | room 实体数据未被环境建模使用 | 低 | 已修复 | 根据需求决定是否实现 |
| Q-005 | PLAYER_INVENTORY 通道未在 data_processor.py 中解析 | 中 | 搁置 | 游戏API限制，非战斗必须 |
| Q-006 | BOMBS 通道未集成到 AI 系统 | 低 | **已修复** | 添加 DangerSystem 炸弹威胁检测 |
| Q-007 | Room 实体（fire_hazards, buttons 等）缺少过期清理 | 低 | 待评估 | 当前通过 entity_data 重建缓解 |

### 风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 数据不一致 | player_stats 与 PlayerData 属性不同步 | 中 | 添加数据同步逻辑 |
| 性能下降 | channel_last_update 增加内存和计算开销 | 低 | 评估后优化 |
| 兼容性问题 | 新数据格式可能影响现有模块 | 低 | 添加向后兼容逻辑 |
| 炸弹误伤 | 玩家自己的炸弹可能炸到自己 | 低 | DangerSystem 降低玩家炸弹优先级 |
| 静态危险遗漏 | Room 实体过期未清理 | 低 | entity_data 每次重建缓解 |

---

## 开发进度

### 2026-01-14

- [x] P0-001: 在 strategy_system.py 中使用 player_stats 数据
- [x] P0-002: 统一 player 数据访问入口
- [x] P1-001: 保留 PLAYER_HEALTH 详细心类型数据
- [x] P1-002: 添加 player 数据快捷访问方法
- [x] P1-003: 添加 PlayerData 文档注释和 get_stats() 方法
- [x] **新增**: BOMBS 通道集成到 AI 系统
  - [x] environment.py: 添加 update_bombs() 方法
  - [x] socket_ai_agent.py: 添加 entity_data["BOMBS"] 构建
  - [x] danger_system.py: 添加炸弹威胁检测
- [x] 提交: `cffdce6 feat: Integrate player_stats data access with fallback support`
- [x] 提交: `c1b54a1 docs: Add status persistence development todo list`

### 待完成

- [ ] 解决 P2 级别问题（room 实体交互）
- [ ] 解决 P3 级别问题（测试、文档）
- [ ] 运行完整测试套件
- [ ] 合并到主分支

---

## 技术决策记录

### 决策 #1: 独立通道存储

**日期**: 2026-01-13  
**问题**: 不同频率的数据通道如何存储？

**决定**:
- 每个通道使用独立的字典字段（如 `players`, `enemies`, `player_stats`）
- 未更新的通道保留上次的数据
- 实体（敌人、投射物）通过 `cleanup_stale_entities()` 自动清理

**优点**:
- 数据来源清晰
- 便于独立更新和访问

**缺点**:
- 需要额外的状态跟踪开销

### 决策 #2: PlayerData 结构

**日期**: 2026-01-13  
**问题**: PlayerData 是否应该包含属性数据？

**当前状态**:
- PlayerData 同时包含位置数据和属性数据
- 新增了独立的 `player_stats` 字典

**待解决问题**:
- 数据来源不清晰
- 可能导致数据不一致

**建议**:
- 在下次迭代中统一 player 数据访问方式

---

## 测试用例

### 已通过测试

| 测试文件 | 测试内容 | 状态 |
|----------|----------|------|
| test_suite.py | 基础数据解析测试 | ✅ 通过 |
| test_replay_modules.py | 回放模块测试 | ✅ 通过 |
| test_room_shape.py | 房间形状测试 | ✅ 通过 |

### 待添加测试

| 测试内容 | 优先级 | 备注 |
|----------|--------|------|
| 状态保持行为测试 | P1 | 验证未更新通道的数据保留 |
| 实体过期清理测试 | P1 | 验证 cleanup_stale_entities 行为 |
| 新通道集成测试 | P2 | 验证完整数据流 |

---

## 资源链接

- **相关文档**: [data-sync-timestamp-fix.md](../docs/data-sync-timestamp-fix.md)
- **协议文档**: [DATA_PROTOCOL.md](../docs/DATA_PROTOCOL.md)
- **架构设计**: [reference.md](../docs/reference.md)

---

## 更新日志

| 日期 | 更新内容 | 更新人 |
|------|----------|--------|
| 2026-01-13 | 创建文档，初始化任务列表 | - |
