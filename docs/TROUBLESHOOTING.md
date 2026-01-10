# 故障排除指南

## 目录

1. [连接问题](#连接问题)
2. [性能问题](#性能问题)
3. [AI行为问题](#ai行为问题)
4. [游戏兼容性问题](#游戏兼容性问题)
5. [Windows特定问题](#windows特定问题)

---

## 连接问题

### 问题: 无法连接到游戏

**错误信息**:
```
Connection refused
或
Timeout waiting for connection
```

**解决方案**:

1. 检查模组是否启用
   ```
   游戏内: Mods → SocketBridge → Enabled
   ```

2. 检查端口是否正确
   ```python
   bridge = IsaacBridge(port=9527)  # 默认端口
   ```

3. 检查防火墙设置
   ```bash
   # Linux
   sudo ufw allow 9527

   # Windows
   # 控制面板 → 防火墙 → 允许应用通过
   ```

4. 检查端口占用
   ```bash
   # Linux
   netstat -tuln | grep 9527

   # Windows
   netstat -ano | findstr :9527
   ```

---

### 问题: 连接频繁断开

**可能原因和解决方案**:

1. **网络不稳定**
   - 降低决策频率
   - 使用有线连接

2. **游戏卡顿**
   - 降低游戏画质
   - 关闭后台程序

3. **AI计算超时**
   ```python
   config = AIConfig(decision_interval=0.1)  # 降低到10Hz
   ```

---

## 性能问题

### 问题: AI反应慢

**诊断步骤**:

```python
# 检查决策延迟
stats = orchestrator.get_performance_stats()
print(f"每秒决策: {stats['decisions_per_second']:.1f}")
```

**优化方案**:

1. 降低决策频率
   ```python
   config = AIConfig(decision_interval=0.1)  # 10Hz
   ```

2. 禁用不需要的模块
   ```python
   config = AIConfig(
       enable_behavior_tree=False,
       enable_advanced_control=False,
       enable_adaptive_behavior=False,
   )
   ```

3. 减少日志输出
   ```python
   import logging
   logging.basicConfig(level=logging.WARNING)
   ```

---

### 问题: CPU占用过高

**解决方案**:

1. 使用轻量配置
   ```python
   config = AIConfig(
       enable_pathfinding=True,
       enable_threat_analysis=True,
       enable_behavior_tree=False,
       enable_advanced_control=False,
       enable_adaptive_behavior=False,
   )
   ```

2. 关闭详细日志
   ```python
   logging.basicConfig(level=logging.ERROR)
   ```

3. 降低帧率
   ```python
   config = AIConfig(decision_interval=0.05)  # 20Hz
   ```

---

## AI行为问题

### 问题: AI不动

**诊断**:

```python
# 检查AI是否启用
print(f"AI enabled: {orchestrator.is_enabled}")

# 检查当前状态
stats = orchestrator.get_performance_stats()
print(f"Current state: {stats['current_state']}")
```

**可能原因**:

1. AI未启用
   ```python
   orchestrator.enable()
   ```

2. 游戏中没有敌人
   - 正常行为，AI会进入探索模式

3. 坐标解析失败
   - 检查数据协议版本

---

### 问题: AI乱跑

**可能原因**:

1. 坐标系问题
   ```python
   # 检查数据格式
   print(player.position.x, player.position.y)
   ```

2. 障碍物检测问题
   ```python
   # 重置环境模型
   orchestrator.path_planner.clear_dynamic_obstacles()
   ```

3. 策略配置问题
   ```python
   # 使用平衡策略
   orchestrator.set_movement_style("balanced")
   ```

---

### 问题: 瞄准不准确

**解决方案**:

1. 检查智能瞄准系统
   ```python
   accuracy = aiming.get_accuracy()
   print(f"Aim accuracy: {accuracy:.1%}")
   ```

2. 调整瞄准参数
   ```python
   from socketbridge import AimConfig
   config = AimConfig(
       prediction_strength=0.8,
       jitter_amount=0.1,
   )
   ```

3. 清除命中率记录
   ```python
   aiming.reset()
   ```

---

### 问题: 不会躲避

**诊断**:

```python
# 检查威胁分析
assessment = orchestrator.threat_analyzer.analyze(...)
print(f"Threat level: {assessment.overall_threat_level}")
```

**解决方案**:

1. 启用威胁分析
   ```python
   config = AIConfig(enable_threat_analysis=True)
   ```

2. 调整威胁阈值
   ```python
   config.immediate_threat_threshold = 0.3  # 更敏感
   ```

3. 检查投射物检测
   ```python
   # 确认数据中有 enemy_projectiles
   print(game_state.enemy_projectiles)
   ```

---

## 游戏兼容性问题

### 问题: 数据格式不匹配

**错误信息**:
```
KeyError: 'player_position'
或
AttributeError: 'NoneType' has no attribute 'x'
```

**解决方案**:

1. 检查数据协议版本
   ```python
   # 查看 DATA_PROTOCOL.md 了解当前版本
   ```

2. 更新模组
   ```bash
   # 确保使用最新版本的 main.lua
   ```

3. 检查数据完整性
   ```python
   def safe_get_position(data):
       try:
           return data['player']['pos']
       except (KeyError, TypeError):
           return None
   ```

---

### 问题: 某些功能不工作

**功能支持矩阵**:

| 功能 | 支持状态 | 说明 |
|------|---------|------|
| 移动 | ✅ 完整 | 支持8方向 |
| 射击 | ✅ 完整 | 支持方向控制 |
| 使用道具 | ✅ 完整 | 主动道具 |
| 放置炸弹 | ✅ 完整 | |
| 丢弃物品 | ⚠️ 部分 | 某些版本不支持 |
| 房间切换 | ✅ 完整 | 自动检测 |

---

## Windows特定问题

### 问题: 中文显示乱码

**解决方案**:

```cmd
chcp 65001
```

或在Python中:
```python
import sys
sys.stdout.reconfigure(encoding='utf-8')
```

---

### 问题: 权限错误

**解决方案**:

1. 以管理员身份运行命令提示符
2. 确保游戏目录可写
3. 禁用杀毒软件或添加排除

---

### 问题: 找不到Python

**解决方案**:

1. 添加Python到PATH
   ```cmd
   # 检查是否已安装
   python --version
   ```

2. 或使用完整路径
   ```cmd
   C:\Python311\python.exe run.py
   ```

---

## 日志查看

### 启用详细日志

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('debug.log'),
        logging.StreamHandler(),
    ]
)
```

### 查看日志文件

```bash
# Linux
tail -f debug.log

# Windows
Get-Content debug.log -Wait -Tail 50
```

---

## 常见问题FAQ

### Q: 需要什么Python版本?
A: Python 3.8+

### Q: 需要安装依赖吗?
A: 不需要，所有依赖都是标准库

### Q: 支持Windows/Mac/Linux?
A: 支持，代码已进行跨平台兼容

### Q: AI可以自定义吗?
A: 可以，所有参数都可配置

### Q: 支持多人游戏吗?
A: 当前仅支持单人游戏

### Q: 如何重置AI状态?
A: ```python
orchestrator.reset()
```

---

**相关文档**:
- [完整系统文档](SYSTEM_DOCUMENTATION.md)
- [快速开始](QUICKSTART.md)
- [API参考](API_QUICK_REFERENCE.md)
