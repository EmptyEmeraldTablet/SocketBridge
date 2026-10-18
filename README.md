# SocketBridge v4

用 TypeScript 编写的 REPENTOGON 游戏运行时观察与控制接口，用于测试以撒模组逻辑。主机为 Node/TS，游戏端通过 TypeScriptToLua 编译；测试主要依赖状态、事件和日志，不依赖截图。

设计及机制说明：[docs/V4_DESIGN.md](docs/V4_DESIGN.md)，接口参考：[docs/PROTOCOL.md](docs/PROTOCOL.md)。v3 源码保留在 [legacy/main.v3.lua](legacy/main.v3.lua)，旧 Python 工具保留但不兼容 v4 协议。

## 构建与安装

需要 Node ≥22、REPENTOGON，以及实际运行时可加载的 `socket.core`。**本机 REPENTOGON 1.1.3 实测需要通过 Launcher 加 `--luadebug`，或在其配置中启用 `[Vanilla] LuaDebug=1`；DLL 存在不代表默认能加载。** 当前锁定 TypeScript 5.9.3、TSTL 1.34.0、Isaac definitions 43.0.6。

```powershell
npm ci
npm run check
# 游戏完全退出后：备份原 mods/SocketBridge，再安装新构建
npm run deploy
```

构建产物是 `mod/`，不要将整个源码仓库复制为模组。首次构建生成本机 `config.local.json`（随机 token、端口 9527、console 默认禁用），同时生成游戏端配置；更改配置后重新构建和部署。主机与游戏必须使用同一份配置。

部署命令输出 `backupId` 和 `backupRoot`。旧安装完整保留在游戏根目录 `.socketbridge-deploy-backups/<backupId>/previous/`（与安装目标同卷），可在游戏退出后恢复：

```powershell
npm run deploy -- --restore <backupId>
```

部署检查 manifest 文件哈希，不改其他模组或存档。恢复会检查当前 v4 文件是否被改动；不会静默覆盖修改。若安装进程被系统强制终止，保留的 journal、previous 和 staged 用于定位恢复阶段，勿手工删除备份。

## 实时观察

先运行主机，再通过 REPENTOGON Launcher 启动游戏：

```powershell
npm run serve -- --sensors players,room,pickups --interval 15
```

主机可在主菜单握手，进入游戏后开始采集。`waitReady()` 只表示通信就绪；`waitForRuntime({ inGame: true, adapters: ["my-mod"] })` 等待正式入局和指定模组初始化。菜单阶段通过 REPENTOGON `MC_MAIN_MENU_RENDER` 维护网络，不访问玩家/房间。stdout 输出结构化事件/遥测，stderr 输出进度；完整双向消息录制在 `runs/<timestamp>/messages.jsonl`。Ctrl+C 关闭连接，游戏端释放桥的暂停和输入控制。桥不会自动开始新局。

REPENTOGON 可跳过片头：游戏退出后，在文档目录 `My Games/Binding of Isaac Repentance+/Repentogon/options.ini` 的 `[VanillaTweaks]` 中设置 `SkipIntro = 1`。这是 REPENTOGON 设置，不是 Launcher 的 `--skip-wizard`；跳过片头仍停留在菜单，不会替测试选择存档或开局。

`--config <file>` 可指定主机配置；只改主机 `--port` 不会改变游戏配置。默认监听仅 `127.0.0.1`。同一主机只接受一个已认证游戏连接；不要让旧 Python Hub 占用同一端口。

## 逻辑测试

可以先启动测试再进入可用于测试的局面，CLI 会等待正式入局：

```powershell
npm run scenario -- examples/logic-smoke.json --wait 120
node --experimental-strip-types examples/sdk-smoke.ts
```

示例验证引擎身份、完整快照，以及 `runtime.step(3)` 恰好产生三个实际 update。命令等待墙钟有上限；原生暂停、切房或断线不会伪装成更新完成。测试退出会释放输入和桥的暂停；业务数据恢复由用例自己的 cleanup 负责，**给道具再移除并不保证撤销所有触发副作用**，请用独立测试存档验证修改型场景。

场景可添加 `"requires": { "inGame": true, "adapters": ["example-mod"] }`。CLI 默认要求 `inGame=true`；纯菜单检查可以显式改为 false。`--wait` 分别约束初次连接和场景就绪等待。adapter 的 `ready()` 应由待测模组在业务初始化完成后返回 true，退出时恢复 false；未提供该函数则注册即视为 adapter 就绪。

| op | 用途 |
|---|---|
| `command` | 执行具名命令，保存关联后的终态结果 |
| `snapshot` | 请求新鲜完整 sensor 快照 |
| `step` | 在桥暂停模式推进指定实际更新步 |
| `assert` | `equals/min/max`，可用 `deltaFrom` 比较变化 |
| `event` | 检查本次用例期间已收到或随后收到的具名事件，可按字段过滤 |
| `eventually` | 暂停后逐步推进，检查有限步内快照字段满足等值条件 |

`{"$ref":"before.sensors.players.data.0.damage"}` 引用早先步骤的结果。只支持字段访问，不执行表达式或任意代码。`event` 不能证明事件与某条命令有唯一因果关系；复杂业务用独立 fixture、事件字段和快照共同验证。

退出码：`0` 通过且清理完成；`1` 配置/连接/运行错误；`2` 断言失败；`4` 清理失败。`--json` 不改变判定。报告写入 `report.json`。

## SDK 命令

```ts
import { BridgeServer } from "./dist/host/index.js";
const bridge = new BridgeServer({ port: 9527, token: "从本机配置读取" });
await bridge.listen();
await bridge.waitReady();
await bridge.waitForRuntime({ inGame: true });
const state = await bridge.snapshot(["players", "inventory", "npcs"]);
```

| 类别 | 方法 |
|---|---|
| 观察 | `runtime.describe`、`state.snapshot`、`telemetry.subscribe`、`item.resolve`、`mod.observe` |
| 更新控制 | `runtime.pause`、`runtime.resume`、`runtime.step` |
| 输入 | `input.pulse`、`input.clear` |
| 测试场景修改 | `entity.spawn`、`entity.remove`、`player.giveCollectible`、`player.removeCollectible`、`mod.invoke` |
| 可选控制台 | `console.execute`，需要配置 `allowConsole=true` |

`request()` 收到 completed 才 resolve；accepted 不等于完成。失败抛 `BridgeError`；TIMEOUT/DISCONNECTED 的 outcome 为 unknown，不能盲重试有副作用的操作。runtime.step 和 input.pulse 可以并发提交：先发输入 Promise，再 step，最后等待两者完成；桥暂停时直接 await 输入会等不到逻辑更新。

空 `telemetry.subscribe.sensors` 表示取消全部遥测。心跳和控制结果不受订阅影响。每条连接最多接受 2048 个新 requestId，超限应启动新会话；不通过淘汰去重记录后重执行旧请求。

## 数据与扩展

Sensors：`players/inventory/room/grid/entities/npcs/pickups/projectiles/tears/lasers/bombs/familiars/slots/effects`。只请求需要的范围，库存/地形适合低频或检查点采集。同次快照内共享一次实体枚举。

数据语义：集合完整替换；`[]` 是确实为空，error/unsupported 不是零值。红心、魂心按半心单位；黑心字段为位掩码字符串；MaxFireDelay 不称作射速；NPC 不按当前可受伤状态筛除；槽机不按 NPC 解释。实际生成、道具添加、自然拾取、死亡和移除分别记录，不相互冒充。

REPENTOGON 扩展用于更新前控制、伤害后观察、道具添加/使用后事件及菜单网络维护。能力存在性从实际运行环境读取；更复杂的角色、buff、特殊道具与第三方 mod 行为通过 adapter 扩展。

[examples/mod-adapter.ts](examples/mod-adapter.ts) 演示 `SocketBridgeV4.register()`。在双方加载完成后注册，公开方法采用 `this: void` 的 dot 调用约定；返回 JSON 数据，禁止 userdata/函数/循环表。空数组用 `SocketBridgeV4.array([])` 显式标记。release 构建不注册 debug adapter。

## 验证边界

`npm run check` 执行主机类型检查、TSTL 编译、Node loopback 集成，以及编译后 Lua 的 Fengari 行为测试。Fengari 不包含 Isaac 引擎，不能证明真实 callback 顺序、复杂角色心量规则、所有 native API、桌面启动链已正确。实机验证记录见 [docs/VALIDATION.md](docs/VALIDATION.md)。

Launcher/存档隔离属于外部运行器；当前桥不会复制旧资产脚本的全进程强制退出、部分存档备份或未经确认的自动恢复流程。图像捕获和自动通关不在本次重构范围。

本机菜单实测脚本会启动并关闭本次拥有的游戏进程，使用 `--luadebug`，不自动开局：

```powershell
node tools/menu-smoke.mjs --launcher 'D:/blankpage/isaac/REPENTOGONLauncher.exe' --ini '../ai-assets/launcher.ci.ini'
```

菜单启动仍会触发引擎自己的配置/持久数据写入，这个脚本不构成存档隔离运行器。
