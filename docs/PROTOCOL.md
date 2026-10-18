# SocketBridge v4 接口与测试约定

本文对应 `src/protocol/`、`src/runtime/bridge.ts` 和 Node SDK。协议名为 `socketbridge/4`，旧 Python/v3 客户端不兼容。建议通过 SDK 调用，不直接维护消息序号。

## 1. 连接与消息

游戏主动连接 `127.0.0.1:<port>`；主机监听端口默认 9527。传输为 UTF-8 JSON Lines，每行一个 JSON 对象。原生 LuaSocket 来自游戏运行环境，dkjson 随构建产物部署，用于保留空对象/空数组差异。

握手顺序：游戏 `hello`（protocol、kind、payload.token 与身份）→ 主机 `welcome`（新 sessionId/connectionId）→ 游戏 `ready`。hello 是无会话前缀消息，其余消息使用统一 envelope。主机每次握手创建新 session，断线不会重放前一会话的命令。

```json
{
  "protocol": "socketbridge/4",
  "sessionId": "session-uuid",
  "connectionId": "connection-uuid",
  "seq": 2,
  "runEpoch": 1,
  "roomEpoch": 2,
  "updateTick": 30,
  "renderTick": 70,
  "kind": "command",
  "requestId": "request-uuid",
  "payload": {
    "method": "state.snapshot",
    "args": { "sensors": ["players", "room"] },
    "timeoutMs": 5000
  }
}
```

- seq 按方向、按连接递增，发送成功进入 wire 的消息不允许跳号。
- updateTick 是该局实际 `MC_POST_UPDATE` 次数，不是墙钟、渲染帧或命令条数；renderTick 是桥的 render 回调计数。
- runEpoch 在正式进入新局/继续局时增加；roomEpoch 在切房、进入/退出局面时推进。旧局面命令被拒绝，旧实体引用不能跨这些边界使用。
- 主机消息中的时钟是它最后收到的游戏时钟，不表示引擎已经暂停在该时刻；Lua 侧执行前重新检查 epoch。
- token 只在本机配置和握手使用，JSONL 中的 hello 会脱敏；不要把本机配置、构建配置 Lua 或安装备份上传仓库。

## 2. 命令参数与完成语义

SDK：`bridge.request(method, args = {}, timeoutMs = 5000)`。所有 timeoutMs 为 50..120000；无参数仍传对象 `{}`，不能传 `[]`。表中列出的参数除注明外均必填。

| 方法 | args | 结果或语义 |
|---|---|---|
| `runtime.describe` | `{}` | buildId、REPENTOGON 版本、phase/inGame、暂停状态、能力、sensors/commands、adapter 版本和 readiness |
| `runtime.pause` | `{}` | 开启桥暂停；要求已入局及 PRE_UPDATE 能力，不修改原生 pause 菜单 |
| `runtime.resume` | `{}` | 释放桥暂停；未完成的 step 取消 |
| `runtime.step` | `{ticks}`，1..3600 | 完成指定数量的实际 update 后返回，并保持桥暂停 |
| `state.snapshot` | `{sensors: string[]}`，最多 16 项 | 一次完整替换快照；要求已入局 |
| `telemetry.subscribe` | `{sensors: string[], intervalTicks}`，间隔 1..3600 | 替换订阅；空 sensors 取消；入局后按 updateTick 采样 |
| `input.pulse` | `{playerIndex, action, value, ticks}` | 在指定玩家接下来的有限更新中提供输入，持续结束后才 completed |
| `input.clear` | `{}` | 释放全部桥输入，未完成 pulse 取消 |
| `item.resolve` | `{name}`，1..256 字符 | 按引擎道具名称查 ID；未找到报错；当前作为局内命令执行 |
| `entity.spawn` | `{type, variant, subtype, x, y}` | 使用 Isaac.Spawn，零速度、无 spawner；返回新 entityRef 与引擎类型字段 |
| `entity.remove` | `{entityRef}` | 移除本会话仍有效的实体；拒绝玩家；移除不等同于死亡 |
| `player.giveCollectible` | `{playerIndex, itemId}` | 程序添加一次道具，返回真实库存数量；不模拟拾取动画/购买 |
| `player.removeCollectible` | `{playerIndex, itemId}` | 程序移除一次道具；不保证撤销添加触发的其他副作用 |
| `mod.observe` | `{modId, name, params: {}}` | 调用已注册、已就绪 adapter 的具名只读方法 |
| `mod.invoke` | `{modId, name, params: {}}` | 调用已注册、已就绪 adapter 的具名 fixture/修改方法 |
| `console.execute` | `{command}`，1..1024 字符 | 仅 `allowConsole=true` 提供，局内执行；默认禁用 |

输入范围：playerIndex 0..15（执行时还要验证实际玩家存在），action 0..15，value 0..1，ticks 1..3600。action 使用当前游戏 `ButtonAction` 数值。输入 hook 的 pressed/triggered/value 分别返回布尔/布尔/数值；triggered 在首个实际更新内保持一致，不因同一帧多次查询而消耗。这里只覆盖 `Isaac.GetPlayer(index)` 可枚举的玩家；特殊子玩家机制仍需专项实测。

生成参数的结构范围：type 1..10000，variant 0..100000，subtype 0..2147483647，x/y -10000..10000。结构校验不等于已验证所有原生实体组合；场景应使用有效的 XML/引擎类型。道具 ID 会查询 ItemConfig 有效性。

菜单可执行 describe、订阅配置、resume、input.clear；pause/step 检查入局条件。其余命令必须入局，在 PRE_UPDATE 阶段执行，每次最多执行 8 个。桥暂停时 PRE_UPDATE 仍用于处理排队命令，然后取消主要更新，因此能够请求快照及恢复；原生暂停可能使该阶段不再运行，此时按 deadline 失败。

游戏先发 `result.status=accepted`，再发一个终态：

```json
{"status":"completed","appliedAtTick":30,"result":{"paused":true}}
```

```json
{"status":"failed","code":"STALE_WORLD","error":"Target run/room changed before command execution"}
```

accepted 只表示进入请求处理。completed 表示命令约定完成，不自动证明业务正确；failed/cancelled 也不表示已执行的副作用全部回滚。SDK 在 completed 时 resolve 终态 payload，在 failed/cancelled 时抛 BridgeError。`COMMAND_ERROR` 的 error 包含引擎/adapter 诊断；部分边界错误直接用 NOT_IN_GAME、STALE_WORLD、UNSUPPORTED、SESSION_LIMIT、RESULT_LIMIT 等 code。

主机 TIMEOUT/DISCONNECTED/CLOSED 的 `outcome=unknown`：效果可能已执行，但未确认。运行时 DEADLINE_EXCEEDED、RESULT_LIMIT 或 adapter 中途报错也不能据此假设“什么都没发生”。仅在明确建立新 fixture 后重试修改型测试。

同连接相同 requestId 与相同参数返回缓存终态/accepted；更改参数报 REQUEST_ID_REUSED。不同连接没有 exactly-once 保证。SDK 自动分配 requestId，不自动重试。

## 3. 快照与事件

```json
{
  "runEpoch": 1, "roomEpoch": 2, "updateTick": 30, "renderTick": 70,
  "mode": "replace", "complete": true,
  "sensors": {
    "pickups": { "status": "ok", "sampleTick": 30, "data": [] }
  }
}
```

集合的 `ok + []` 表示确实没有该类对象，应清空旧集合；缺失、error、unsupported 不能解释为空。`bridge.snapshot()` 要求所有请求的 sensor 均存在且成功，并拒绝已过期 epoch；原始 `request("state.snapshot")` 可以用于诊断部分失败的 sensor。订阅 telemetry 允许表达部分失败，不会把它转成通过。

| sensor | 数据形状与用途 |
|---|---|
| players | 玩家数组：索引/引用、位置/速度、Damage/MaxFireDelay 等属性、物资、原始心量字段 |
| inventory | 玩家数组：真实 collectible 数量、临时 collectible effects、饰品/卡/药丸、四个主动槽位 |
| room | 单对象：stage/type/dimension、descriptor、种子、门槛状态、边界、engineFrame、nativePaused |
| grid | 单对象：gridSize、cells 数组、doors 数组 |
| entities | 全部可枚举房间实体数组，保留类型及 Sprite 等状态 |
| npcs | ToNPC 成功的实体；不按当前 vulnerability 排除 |
| pickups/projectiles/tears/lasers/bombs/familiars/slots/effects | 按原生实体 type 筛选的完整数组 |

entityRef 是桥生成的会话内引用，不把 Index 或指针单独当永久 ID。心量保留原生语义：红心/魂心为半心单位；黑心为 mask 字符串；骨、腐、碎心字段分开。库存数量与临时效果分开；不能从某一个数值推断所有角色的有效生命或全部 buff。

事件 kind=event，payload 为 `{name, data, phase}`，外层携带时钟。当前事件：game.started、game.exited、room.entered、entity.damageApplied、collectible.added、item.used、npc.died、entity.removed、pickup.initialized，以及 `mod.<自定义名称>`。entity.removed 只对桥已追踪的引用发出；不能声称看到了所有未采样实体的完整历史。

伤害事件是 REPENTOGON post damage 阶段观测，字段名使用 hitPointsAtCallback/healthAtCallback，不保证已经经历同一更新内的所有后续修正。事件没有自动建立 command→业务回调的唯一因果关系。对时序敏感的断言应结合 fixture、phase、epoch、后续快照及 mod 自定义关联字段。

## 4. 启动和 adapter 就绪

```ts
await bridge.listen();
await bridge.waitReady(120000); // 主菜单即可完成
await bridge.waitForRuntime({ inGame: true, adapters: ["example-mod"] }, 120000);
const result = await bridge.request("mod.observe", {
  modId: "example-mod", name: "counters", params: {},
});
```

adapter 的 `ready(): boolean` 是可选的无副作用函数；省略意味着注册即就绪。函数报错或返回非 true 被视为未就绪，observe/invoke 会被拒绝。ready 不自动重置，待测模组应在退出/新局时正确维护自己的初始化状态。注册时机与业务初始化时机可以不同。

声明式场景增加 `requires`：

```json
{"id":"my-mod-regression","requires":{"inGame":true,"adapters":["example-mod"]},"steps":[
  {"id":"state","op":"command","method":"mod.observe","args":{"modId":"example-mod","name":"counters","params":{}}},
  {"op":"assert","path":"state.result.activationCount","equals":0}
]}
```

`requires.adapters` 只检查指定 ID 已注册并就绪；版本要求可用后续 runtime.describe 断言。模板见 `examples/mod-adapter.ts`。Lua/TSTL 空数组用桥提供的 `array()` 标记；公开函数使用 dot 调用（this:void）。

暂停状态下，input.pulse 必须和 step 并发提交，不能先 await pulse 再推进更新：

```ts
await bridge.request("runtime.pause");
const input = bridge.request("input.pulse", { playerIndex: 0, action: 0, value: 1, ticks: 3 });
const step = bridge.step(3);
await Promise.all([input, step]);
```

## 5. 限额和证据失败

单行最多 262144 bytes；游戏 RX buffer 1 MiB、TX 队列 1 MiB/256 行；每次 pump 读写各有 32768 bytes 配额、最多处理 32 行。Lua 连接建立超时约 2 秒，重试间隔至少约 1 秒；hello/welcome 之后使用心跳，游戏 6 秒未收到消息释放连接和控制，主机默认 8 秒未收到消息断开。进程挂起或回调完全不运行时，游戏端本身无法按墙钟执行清理，仍需外部运行器恢复。

每会话最多 2048 个新 requestId、世界命令队列 128 个；单个缓存结果约 250000 bytes，累计参数/结果受内存上限约束。达到限制明确失败，不丢掉去重记录后再次执行旧命令。长时间高频轮询 readiness/describe 也占请求额度，应安排新的测试会话。

JSON 嵌套深度最多 32，拒绝 userdata、函数、循环表和非有限数字；大整数 flags 使用字符串。adapter 应返回有界数据，不把完整引擎对象塞进 JSON。

JSONL 录制包含双向消息和连接生命周期；本地时间/monotonicNs 供传输分析，不能替代引擎 tick。录制失败或背压超限会关闭连接，场景不能继续报 PASS。场景事件缓冲上限 4096，溢出判证据不完整。退出码：0 通过且清理完成；1 运行错误；2 断言失败；4 清理失败。
