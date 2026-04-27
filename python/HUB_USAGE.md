# BridgeHub 使用说明

BridgeHub 提供一个常驻连接服务：
- 仅 BridgeHub 与 Lua 端（SocketBridge mod）建立连接
- 多个上层应用通过本地 Hub 端口读取数据 / 发送命令
- 单个上层应用退出不会中断 Lua 连接

## 1. 启动 Hub

```bash
python -m apps.bridge_hub
```

可选参数：

```bash
python -m apps.bridge_hub --hub-host 127.0.0.1 --hub-port 9530 --lua-host 127.0.0.1 --lua-port 9527
```

## 2. 启动可视化（Hub 模式）

```bash
python -m apps.room_layout_visualizer live --hub
```

可选指定 Hub 地址：

```bash
python -m apps.room_layout_visualizer live --hub --hub-host 127.0.0.1 --hub-port 9530
```

## 3. 启动控制台（Hub 模式）

```bash
python -m apps.console --hub
```

可选指定 Hub 地址：

```bash
python -m apps.console --hub --hub-host 127.0.0.1 --hub-port 9530
```

## 4. 典型并行运行

1. 启动 `bridge_hub`
2. 启动游戏并加载 SocketBridge mod
3. 启动 `room_layout_visualizer --hub`
4. 启动 `console --hub`

此时可实现：
- 可视化持续接收地形数据
- 控制台同时发送指令（如 `giveitem c1`）
- 任一上层应用退出，不影响 Hub 与 Lua 的连接

## 5. 协议行为（当前实现）

- 应用侧通过本地 JSON-line 协议连接 Hub
- 每个应用可独立订阅通道（Hub 本地过滤）
- 命令结果回传到命令发起者（FIFO 路由）

## 6. 与直连模式兼容

当前仍保留旧模式：
- `apps.room_layout_visualizer` 默认直连（不加 `--hub`）
- `apps.console` 默认直连（不加 `--hub`）

建议多应用并行时统一使用 `--hub`。

## 7. 面向新工具开发的 Sensor 接入规范

如果你正在开发新的 Hub 应用（例如新可视化器、自动化代理、验证器），请先阅读：

- [HUB_SENSOR_GUIDE.md](HUB_SENSOR_GUIDE.md)

该文档定义了：
- Hub 模式下 Sensor 的职责边界（Lua 注册 / Hub 过滤 / App 订阅）
- 标准接入流程（subscribe + request_full_state）
- 断线重连、通道缺失、刷新策略的统一实践
