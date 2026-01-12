# SocketBridge AI Combat System Documentation

## 文档目录

### 📚 用户指南

| 文档 | 说明 | 优先级 |
|------|------|--------|
| [README.md](../README.md) | 项目主说明 | ⭐⭐⭐ |
| [QUICKSTART.md](QUICKSTART.md) | 快速开始指南 | ⭐⭐⭐ |
| [README_WINDOWS.md](../README_WINDOWS.md) | Windows安装指南 | ⭐⭐⭐ |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | 快速参考卡片 | ⭐⭐ |

### 🔧 API 参考

| 文档 | 说明 | 优先级 |
|------|------|--------|
| [SYSTEM_DOCUMENTATION.md](SYSTEM_DOCUMENTATION.md) | 完整系统文档 | ⭐⭐⭐ |
| [DATA_PROTOCOL.md](DATA_PROTOCOL.md) | 数据协议规范 | ⭐⭐ |
| [API_QUICK_REFERENCE.md](API_QUICK_REFERENCE.md) | API快速参考 | ⭐⭐ |

### 💡 示例

| 文档 | 说明 |
|------|------|
| [CONSOLE_COMMANDS.md](CONSOLE_COMMANDS.md) | 控制台命令 |
| [TRACKING_SYSTEM_SIMPLE.md](TRACKING_SYSTEM_SIMPLE.md) | 追踪系统说明 |

---

## 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone https://github.com/EmptyEmeraldTablet/SocketBridge.git
cd SocketBridge/python

# 运行启动器
python run.py --status
```

### 2. 启动AI

```bash
# 方式1: 使用启动器 (推荐)
python run.py

# 方式2: 直接启动
python run.py --ai
```

### 3. 游戏内设置

1. 启用 SocketBridge 模组
2. 开始新游戏
3. AI自动连接

---

## 文档结构

```
docs/
├── README.md                    # 本文档
├── QUICKSTART.md               # 快速开始
├── QUICK_REFERENCE.md          # 快速参考
├── SYSTEM_DOCUMENTATION.md     # 完整系统文档
├── DATA_PROTOCOL.md            # 数据协议
├── CONSOLE_COMMANDS.md         # 控制台命令
└── TRACKING_SYSTEM_SIMPLE.md   # 追踪系统
```

---

## 常用命令

```bash
# 检查系统状态
python run.py --status

# 运行测试
python run.py --test

# 启动AI
python run.py --ai

# 启动桥接
python run.py --basic
```

---

## 文件结构

```
SocketBridge/
├── README.md           # 项目说明
├── README_WINDOWS.md   # Windows安装
├── reference.md        # 架构参考
└── python/
    ├── run.py          # 启动器 ⭐
    ├── isaac_bridge.py # 核心桥接
    ├── orchestrator_enhanced.py  # AI主控 ⭐
    ├── test_integration.py  # 测试 ⭐
    └── examples/
        ├── example_ai.py
        └── kiting_ai.py
```

---

## 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交变更
4. 发起 Pull Request

---

**最后更新**: 2024年1月
**版本**: 2.0.0
