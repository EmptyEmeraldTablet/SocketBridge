# Archive 归档目录说明

> 创建日期: 2026-02-02
> 归档原因: SocketBridge 重构 Phase 0-4 完成，这些文件暂时不需要

## 归档内容

### legacy/
旧版本代码，已被新架构替代：
- `advanced_ai_example.py` - 旧 AI 示例
- `game_space.py` - 旧游戏空间模型
- `visualize_space.py` - 旧可视化工具
- `QUICKSTART.md` - 旧快速开始文档
- `QUICKSTART_TRACKING.md` - 旧追踪文档
- `TRACKING_SYSTEM.md` - 旧追踪系统文档

### apps/
上层应用和测试脚本，Phase 5 搁置后暂不需要：
- `test_*.py` - 各种测试脚本
- 其他 AI/分析脚本（如果有）

### ai_combat_system/
完整的 AI 战斗系统，依赖底层数据：
- `analysis/` - 分析模块
- `control/` - 控制模块
- `decision/` - 决策模块
- `evaluation/` - 评估模块
- `orchestrator/` - 编排模块
- `perception/` - 感知模块
- `planning/` - 规划模块

### temp_tests/
临时阶段测试文件，已完成使命：
- `test_data_channels.py`
- `test_phase2_channels.py`
- `test_phase3_services.py`
- `test_timing_protocol.py`

## 恢复方法

如需恢复某个文件：
```powershell
# 恢复单个文件
Move-Item -Path "archive\apps\example.py" -Destination "apps\" -Force

# 恢复整个目录
Move-Item -Path "archive\ai_combat_system" -Destination ".\" -Force
```

## 注意事项

1. 这些文件可能依赖旧的 API，恢复后可能需要适配新架构
2. `ai_combat_system` 是完整的系统，恢复时需整体恢复
3. 测试文件可能引用已更改的模块路径
