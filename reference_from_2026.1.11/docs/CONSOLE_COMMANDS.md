# 控制台指令参考

SocketBridge 支持通过 Python 端发送控制台指令到游戏执行。本文档列出了常用的控制台指令及其用法。

## 使用方法

### Python 代码

```python
from isaac_bridge import IsaacBridge, GameDataAccessor

bridge = IsaacBridge(host="127.0.0.1", port=9527)
data = GameDataAccessor(bridge)

# 启动服务器并连接游戏
bridge.start()

# ... 等待连接 ...

# 发送控制台指令
bridge.send_console_command("giveitem c1")       # 给予道具
bridge.send_console_command("spawn Monstro")     # 生成敌人
bridge.send_console_command("stage 5a")          # 传送到楼层
```

## 指令列表

### 生成实体

```
spawn [type].[variant].[subtype].[champion]
spawn [name]
```

**示例：**
```python
bridge.send_console_command("spawn 10")          # 生成苍蝇 (EntityType 10)
bridge.send_console_command("spawn 10.1")        # 生成苍蝇 (Variant 1)
bridge.send_console_command("spawn 10.2.0.4")    # 生成精英苍蝇
bridge.send_console_command("spawn Monstro")     # 通过名称生成
```

### 给予物品

```
giveitem [type][ID]
giveitem [name]
```

类型前缀：
- `c` - 道具 (Collectible)
- `t` / `T` - 饰品 (Trinket) / 金饰品
- `k` - 卡牌 (Card)
- `p` / `P` - 药丸 (Pill) / 大药丸

**示例：**
```python
bridge.send_console_command("giveitem c1")                   # 以撒的眼泪
bridge.send_console_command("giveitem The Sad Onion")        # 通过名称
bridge.send_console_command("giveitem t35")                  # 饰品
bridge.send_console_command("giveitem k31")                  # 卡牌
bridge.send_console_command("giveitem p0")                   # 药丸
bridge.send_console_command("g c118")                        # 缩写形式
```

### 移除物品

```
remove [type][ID]
remove [name]
remove *                    # 移除所有道具和饰品
```

**示例：**
```python
bridge.send_console_command("remove c1")                     # 移除以撒的眼泪
bridge.send_console_command("remove The Sad Onion")          # 通过名称
bridge.send_console_command("remove t35")                    # 移除饰品
bridge.send_console_command("remove *")                      # 移除所有
```

### 传送楼层

```
stage [floor]
```

**示例：**
```python
bridge.send_console_command("stage 1")          # 第1层
bridge.send_console_command("stage 5a")         # 第5层A面
bridge.send_console_command("stage 5b")         # 第5层B面
bridge.send_console_command("stage 10a")        # 虚空A面
```

### 传送到房间

```
goto s.[type].[ID]       # 特殊房间
goto d.[ID]              # 普通房间
goto x.[type].[ID]       # 特殊布局房间
```

**示例：**
```python
bridge.send_console_command("goto s.boss.1010")     # Boss房间
bridge.send_console_command("goto s.error.21")      # Error房间
bridge.send_console_command("goto d.10")            # 房间10
bridge.send_console_command("goto x.treasure.10000") # 宝箱房
```

### 生成障碍物

```
gridspawn [ID]
```

**示例：**
```python
bridge.send_console_command("gridspawn 1000")   # 岩石
bridge.send_console_command("gridspawn 9000")   # 门
```

### 调试功能

```
debug [rule]
```

**示例：**
```python
bridge.send_console_command("debug 3")    # 显示碰撞箱
bridge.send_console_command("debug 10")   # 显示实体索引
```

### 解锁成就

```
achievement [ID]
achievement [name]
achievement *           # 解锁所有成就
```

**示例：**
```python
bridge.send_console_command("achievement 339")      # Godhead
bridge.send_console_command("achievement Godhead")  # 通过名称
bridge.send_console_command("achievement *")        # 所有成就
```

### 设置种子

```
seed [seed]
```

**示例：**
```python
bridge.send_console_command("seed GGGG GGGG")   # 特定种子
```

### 重新开始

```
restart [character]
```

**示例：**
```python
bridge.send_console_command("restart")     # 当前角色
bridge.send_console_command("restart 2")   # 以撒
```

### 执行Lua代码

```
lua [code]
```

**示例：**
```python
bridge.send_console_command("lua print('Hello World!')")
bridge.send_console_command("lua Isaac.GetPlayer(0):AddSoulHearts(2)")
```

### 运行Lua文件

```
luarun [path]
```

**示例：**
```python
bridge.send_console_command("luarun mods/MyMod/test.lua")
```

### 其他指令

| 指令 | 描述 |
|------|------|
| `clear` | 清空控制台 |
| `time` | 显示游戏时间 |
| `listcollectibles` | 列出已获得的道具 |
| `clearseeds` | 清除彩蛋 |
| `restock` | 补充商店库存 |
| `rewind` | 返回上一个房间 |
| `cutscene [ID]` | 播放过场动画 |
| `playsfx [ID]` | 播放音效 |
| `challenge [ID]` | 开始挑战 |
| `combo [pool].[num]` | 随机道具组合 |
| `luamod [name]` | 重载Mod |
| `reloadshaders` | 重载光影 |
| `luamem` | 显示Lua内存使用 |

## 注意事项

1. **大小写敏感**：控制台指令区分大小写
2. **参数格式**：部分指令需要特定的参数格式
3. **风险提示**：
   - 使用控制台可能解锁成就（会同步到Steam）
   - 某些指令可能导致游戏崩溃
   - 在新存档使用控制台不会记录游戏进度
4. **高级用法**：
   - 使用 `lua` 指令可以执行任意Lua代码
   - 结合游戏API可以实现复杂的自动化操作

## 完整解决方案示例

```python
"""SocketBridge 控制台指令示例"""

from isaac_bridge import IsaacBridge, GameDataAccessor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    bridge = IsaacBridge(host="127.0.0.1", port=9527)
    
    @bridge.on("connected")
    def on_connected(info):
        logger.info(f"Game connected: {info['address']}")
        # 请求完整状态
        bridge.request_full_state()
        
        # 示例：游戏开始时给予基础道具
        logger.info("Giving starting items...")
        bridge.send_console_command("giveitem c1")      # 眼泪
        bridge.send_console_command("giveitem c118")    # 炸药
    
    @bridge.on("command_result")
    def on_command_result(result):
        if result.get("success"):
            logger.info(f"Command executed: {result.get('command')}")
        else:
            logger.error(f"Command failed: {result.get('error')}")
    
    bridge.start()
    
    try:
        logger.info("Waiting for game connection...")
        # 主循环中可以根据需要发送指令
        while True:
            import time
            time.sleep(1)
            
            # 示例：在第1层时传送到Boss房
            # data = GameDataAccessor(bridge)
            # if data.room_index == 1:
            #     bridge.send_console_command("goto s.boss.1010")
            
    except KeyboardInterrupt:
        bridge.stop()

if __name__ == "__main__":
    main()
```

## 相关资源

- [以撒的控制台文档](https://isaac.huijiwiki.com/wiki/%E6%8E%A7%E5%88%B6%E5%8F%B0)
- [实体变量表](https://isaac.huijiwiki.com/wiki/%E6%8E%A7%E5%88%B6%E5%8F%B0/%E5%8F%98%E9%87%8F%E8%A1%A8/spawn)
- [物品变量表](https://isaac.huijiwiki.com/wiki/%E6%8E%A7%E5%88%B6%E5%8F%B0/%E5%8F%98%E9%87%8F%E8%A1%A8/giveitem)
