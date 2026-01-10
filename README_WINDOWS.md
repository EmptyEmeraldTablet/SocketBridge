# Windows 运行指南

## 环境要求

- **Python 3.8+** (推荐 3.10 或 3.11)
- **《以撒的结合：重生》** 游戏
- **Windows 10/11** (64位)

## 安装步骤

### 1. 安装 Python

1. 访问 [Python 官网](https://www.python.org/downloads/)
2. 下载 Python 3.11.x (64位 installer)
3. 运行安装程序
4. **重要**: 勾选 `Add Python to PATH`
5. 点击 `Install Now`

### 2. 安装模组

1. 复制整个 `SocketBridge` 文件夹到游戏 mods 目录:
   ```
   C:\Program Files (x86)\Steam\steamapps\common\The Binding of Isaac Repentance\mods\
   ```
2. 在游戏中启用 SocketBridge 模组

### 3. 安装依赖

打开命令提示符 (CMD) 或 PowerShell:

```cmd
cd C:\你的路径\SocketBridge\python
pip install -r requirements.txt
```

> **注意**: 本项目仅使用标准库，无需额外安装

### 4. 启动 Python 服务器

```cmd
cd C:\你的路径\SocketBridge\python
python isaac_bridge.py
```

## 运行测试

```cmd
cd C:\你的路径\SocketBridge\python
python test_windows_compatibility.py
```

## 常见问题

### Q1: 连接失败

**问题**: `Failed to start server: [Errno 10048]`

**原因**: 端口 9527 已被占用

**解决**:
```cmd
# 查看占用端口的进程
netstat -ano | findstr :9527

# 结束进程 (如果需要)
taskkill /PID <进程ID> /F
```

或者修改端口:
```python
# 在代码中修改
bridge = IsaacBridge(host="127.0.0.1", port=9528)
```

### Q2: 找不到模块

**问题**: `ModuleNotFoundError: No module named '...'`

**解决**:
```cmd
# 确保在正确目录
cd C:\你的路径\SocketBridge\python

# 检查 Python 路径
python -c "import sys; print(sys.path)"
```

### Q3: 权限错误

**问题**: `[PermissionError]`

**解决**:
- 以管理员身份运行命令提示符
- 确保游戏目录可写

### Q4: 编码问题

**问题**: 中文显示乱码

**解决**:
```cmd
# 设置控制台编码
chcp 65001

# 或使用 PowerShell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

## 目录结构

```
SocketBridge/
├── main.lua           # 游戏模组
├── metadata.xml       # 模组元数据
└── python/            # Python 端
    ├── isaac_bridge.py      # 核心桥接
    ├── orchestrator_enhanced.py  # AI 主控
    ├── test_windows_compatibility.py  # 兼容性测试
    ├── data_recorder.py     # 数据记录
    ├── example_ai.py        # AI 示例
    ├── logs/                # 日志目录
    └── recordings/          # 录制目录
```

## 性能优化

### Windows 优化建议

1. **电源计划**: 使用"高性能"模式
2. **杀毒软件**: 将游戏目录添加到排除项
3. **后台程序**: 关闭不必要的后台应用

### Python 优化

```python
# 减少日志输出
import logging
logging.basicConfig(level=logging.WARNING)
```

## 已知问题

| 问题 | 状态 | 解决方案 |
|------|------|----------|
| 控制台中文乱码 | ✅ 已修复 | 使用 UTF-8 编码 |
| 端口占用 | ⚠️ 需手动 | 更换端口或结束进程 |
| 路径分隔符 | ✅ 兼容 | 使用 pathlib |

## 技术支持

- GitHub Issues: 报告问题
- 运行测试获取诊断信息:
```cmd
python test_windows_compatibility.py
```

---

**最后更新**: 2024年1月
**版本**: 2.0
