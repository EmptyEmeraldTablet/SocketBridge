# v4 验证记录

日期：2026-10-05。当前结论：**TS 重构已构建并安装；30 项离线检查通过；真实 REPENTOGON 主菜单通信通过。局内玩法验收尚未完成。**

## 1. 验证环境与构建

| 项目 | 本次结果 |
|---|---|
| 系统/宿主 | Windows，Node 24.12.0 |
| 编译 | TypeScript 5.9.3 / TypeScriptToLua 1.34.0 / Lua 5.3 target |
| 类型定义 | isaac-typescript-definitions 43.0.6 |
| 实际游戏 | `Repentogon/isaac-ng.exe`，v1.9.7.12.J273 |
| REPENTOGON | 1.1.3，运行时身份已确认 |
| 最终 buildId | `4f9d0a0fd547ef7f6ee2` |
| 生成主 Lua | 85,070 bytes，另有 dkjson/config/metadata |
| 安装位置 | 游戏根目录 `mods/SocketBridge/` |

buildId 对源码、锁文件、TS 配置、枚举插件、vendor、构建脚本、metadata 求摘要；安装 manifest 另列每个部署文件 SHA-256。主机身份查询与安装 manifest 的 buildId 一致。

## 2. 离线检查

命令：`npm run check`。结果：**30 passed，0 failed，0 skipped**。检查包括 host TypeScript、TSTL 编译、Node 实际 loopback 通信、编译后 Lua/Fengari 与部署回归；未以手写 Lua 替代编译产物。

覆盖的主要失败模式：

- UTF-8 任意拆包、超长消息、无效命令；Lua connect 返回失败、异步连接、partial send/receive、配额。
- requestId 乱序匹配、accepted 非终态、重复命令去重、断线/超时未知结果、第二连接抢占、序号缺口、本地超长命令不消耗 wire 序号。
- 空集合替换、未知/失败 sensor、required scope 缺失、旧 epoch 不恢复过时房间、退出局面失效。
- 输入首帧 triggered、同帧重复查询、玩家隔离与期限；step 按实际 POST_UPDATE 扣步而非 PRE_UPDATE 调用次数。
- ItemConfig 范围超过 733 的道具，真实库存与临时 effects 分离；Lua 空对象/数组/null、Unicode、循环/深度检查。
- TSTL 隐藏 self、adapter 的 dot 调用和 ready 谓词；通信/入局/业务初始化分开等待。
- 负例断言失败、cleanup、eventually 墙钟期限、录制失败关闭连接、最后一步发生事件缓冲溢出也不能报成功。
- 临时模拟安装目录的备份/恢复，多次部署后回退原始安装，保留用户新增文件。

Fengari 的 fake API 只证明桥的处理规则，不能证明原生回调顺序、实际输入消费、游戏暂停语义或实体 API 在所有游戏版本有效。

## 3. 实机菜单检查

最终报告：[report.json](../runs/menu-1791178169601/report.json)，完整消息：[messages.jsonl](../runs/menu-1791178169601/messages.jsonl)。这些是本机生成证据，位于被 git 忽略的 runs 目录。开始于北京时间 2026-10-05 13:29:29，全过程约 19.9 秒，包含启动与关闭。

结果 **PASS**：

1. Launcher 启动实际 REPENTOGON，引擎日志出现 v4 bootstrap/loaded；HELLO→WELCOME→READY 完成。
2. runtime.describe 返回相同 buildId、REPENTOGON 1.1.3、`phase=outside-run`、`inGame=false`；PRE_UPDATE/menu/post damage/post add/post use 能力存在。
3. 菜单阶段能配置空订阅、清理输入与 resume；pause 被 NOT_IN_GAME 诊断拒绝，players 快照以 NOT_IN_GAME code 拒绝。
4. 本次拥有的 Isaac 进程正常关闭，未使用强制关闭后备分支。
5. 启用 SkipIntro 后日志出现 Menu Manager Init，未出现此前的 `playing cutscene 1 (Intro)`，与正式跳过片头设置一致。

这直接证明本机桥可在入局前运行通信，不证明待测业务模组已经初始化。菜单测试没有调用新开局、读玩家/房间、给予道具、实体生成、局内 step 或输入。

## 4. 实测修正与失败记录

首次菜单尝试因 socket 不可加载而没有握手。补齐 DebugString 启动诊断后定位：`LuaDebug=0` 时错误为 `module 'socket.core' not found`；显式 `--luadebug` 后通过。原资产文档“DLL 存在所以可能不需要 luadebug”的推测已在其入口标注修正。

排查时还修正了启动诊断 wrapper 的 Lua vararg 声明；最终编译 Lua 测试覆盖完整入口。较早一轮全套测试与实机检查同时执行，部署测试因“游戏正在运行”保护失败；游戏退出后已完整重跑通过。一次菜单检查脚本错误地在 error.message 查找新接口的错误码，后改为检查 error.code；运行时当时已正确拒绝菜单快照。中间失败的报告保留，最终结论只依据上述最终构建与 PASS 报告。

成功的早期菜单证据另见 [menu-1791177128328](../runs/menu-1791177128328/report.json)，buildId 为较早版本；不能用它替代最终产物验收。

## 5. 本机配置与可回退部署

原安装整目录备份在游戏根目录：

```text
.socketbridge-deploy-backups/2026-10-05T04-56-12-208Z/previous/
```

原安装与仓库里的旧 Lua 不完全相同，因此同时保留安装备份和 `legacy/main.v3.lua`，没有用仓库历史文件冒充安装备份。最终构建部署记录 ID 为 `2026-10-05T05-29-28-617Z`。游戏退出后，在 SocketBridge 源码目录运行以下命令可恢复最初安装（会验证当前构建未被修改）：

```powershell
npm run deploy -- --restore 2026-10-05T04-56-12-208Z
```

按用户建议，将文档目录 `Binding of Isaac Repentance+/Repentogon/options.ini` 的 `[VanillaTweaks] SkipIntro` 从 0 改为 1；原配置备份在 [repentogon-options-before-skipintro.ini](../runs/repentogon-options-before-skipintro.ini)。如需恢复片头，可将这一项改回 0，避免用整份旧配置覆盖后续其他设置变更。

检查未主动开局或执行玩法修改。**菜单启动仍会触发引擎自己的持久数据、备份和 options 写入**，因此不能将其描述为完全无存档写入，也不能把本轮脚本当作存档隔离实现。

## 6. 未完成的实机验收

| 项目 | 当前证据 | 下一步 |
|---|---|---|
| 桥暂停/精确 step/原生暂停差异 | 编译 Lua 测试 | 在专用测试局面核对引擎帧与实际更新 |
| input.pulse 与断线释放 | 编译 Lua 测试 | 玩家移动/射击、多玩家、卡顿/失焦场景 |
| post damage/add/use 回调 | 本机枚举及官方签名核对、能力存在 | 记录真实触发顺序和 callback 后的状态 |
| 道具、心量、NPC/slot 等传感器 | 类型检查与有限 fake API | 实际 mod 道具 ID、复杂角色、特殊实体 |
| 切房/continue/退出与业务 ready | 桥逻辑测试 | 原生回调时序、待测 mod 延迟初始化 |
| 长期耐久、复杂房间性能 | 消息/内存限额已实现 | 采样耗时、事件压力和多模组组合基准 |
| 无人值守玩法测试 | CLI/SDK/就绪门槛已实现 | 独立测试存档、fixture 启动和完整恢复运行器 |

当前可用于开发者在准备好的测试局面中逐项验证桥和业务场景；尚不能声称全自动玩法回归已经通过。
