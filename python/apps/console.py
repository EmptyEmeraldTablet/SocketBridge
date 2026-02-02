"""
SocketBridge 交互式控制台
用于向游戏发送控制台命令

使用方法:
1. 启动游戏并加载 SocketBridge mod
2. 运行此脚本: python console.py
3. 输入控制台命令并按回车执行

连接说明:
- 本脚本作为 TCP 服务器运行 (127.0.0.1:9527)
- 游戏 mod 作为客户端连接到本服务器
- 当游戏连接后即可发送控制台命令

支持的操作:
- 输入命令直接执行，如: giveitem c1
- help - 显示帮助信息
- status - 显示连接状态
- clear - 清屏
- quit / exit - 退出
"""

import sys
import json
import cmd
import threading
import time
from datetime import datetime
from typing import Optional
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入 IsaacBridge 作为 TCP 服务器
from isaac_bridge import IsaacBridge, MessageType

# 颜色配置
class Colors:
    """ANSI 颜色代码"""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    
    @classmethod
    def success(cls, text: str) -> str:
        return f"{cls.GREEN}{text}{cls.RESET}"
    
    @classmethod
    def warning(cls, text: str) -> str:
        return f"{cls.YELLOW}{text}{cls.RESET}"
    
    @classmethod
    def error(cls, text: str) -> str:
        return f"{cls.RED}{text}{cls.RESET}"
    
    @classmethod
    def info(cls, text: str) -> str:
        return f"{cls.CYAN}{text}{cls.RESET}"


class CommandRecord:
    """命令记录"""
    
    def __init__(self, command: str, timestamp: float, success: bool, result: str = ""):
        self.command = command
        self.timestamp = timestamp
        self.success = success
        self.result = result
    
    def __str__(self):
        time_str = datetime.fromtimestamp(self.timestamp).strftime("%H:%M:%S")
        status = Colors.success("✓") if self.success else Colors.error("✗")
        return f"[{time_str}] {status} {self.command}"


class IsaacConsole(cmd.Cmd):
    """
    交互式以撒控制台
    
    特性:
    - 命令历史 (上下箭头)
    - Tab 自动补全
    - 命令执行结果显示
    - 实时连接状态
    """
    
    intro = f"""
{Colors.BOLD}╔════════════════════════════════════════════════════════════╗
║          SocketBridge 交互式控制台                    ║
║          以撒的结合: Rebirth                          ║
╚════════════════════════════════════════════════════════════╝
{Colors.RESET}
输入 {Colors.info('help')} 查看可用命令，{Colors.info('quit')} 退出
启动服务器，等待游戏连接...
"""
    
    prompt = f"{Colors.BOLD}isaac> {Colors.RESET}"
    
    # 控制台命令参考
    COMMON_COMMANDS = {
        # 物品相关
        "giveitem": "giveitem [type][ID] 或 giveitem [name] - 给予道具",
        "remove": "remove [type][ID] 或 remove [name] - 移除道具",
        
        # 实体生成
        "spawn": "spawn [type].[variant].[subtype].[champion] - 生成实体",
        
        # 传送
        "stage": "stage [floor] - 传送到楼层 (如 1a, 2b, basement, caves)",
        "goto": "goto s.[type].[ID] 或 goto d.[ID] - 传送到房间",
        
        # 房间
        "gridspawn": "gridspawn [ID] - 生成障碍物",
        
        # 调试
        "debug": "debug [rule] - 调试功能 (查看当前 debug 状态用: debug 0)",
        
        # 成就
        "achievement": "achievement [ID] 或 achievement [name] - 解锁成就",
        
        # 游戏
        "seed": "seed [seed] - 设置种子",
        "restart": "restart [character] - 重新开始 (如 restart isaac)",
        
        # Lua
        "lua": "lua [code] - 执行 Lua 代码",
        "luarun": "luarun [path] - 运行 Lua 文件",
        
        # 其他
        "clear": "clear - 清空控制台",
        "time": "time - 显示游戏时间",
    }
    
    def __init__(self):
        super().__init__()
        
        # 使用 IsaacBridge 作为 TCP 服务器
        self.bridge = IsaacBridge(host="127.0.0.1", port=9527)
        self.bridge.start()
        
        # 状态
        self.command_history: list[CommandRecord] = []
        self.running = True
        
        # 注册事件处理
        self._register_handlers()
    
    def _register_handlers(self):
        """注册事件处理器"""
        @self.bridge.on("connected")
        def on_connected(info):
            addr = info.get('address', ('unknown', 0))
            print(f"\n{Colors.success(f'✓ 游戏已连接: {addr}')}")
            self.prompt = f"{Colors.GREEN}(已连接) {Colors.BOLD}isaac> {Colors.RESET}"
            # 请求完整状态
            self.bridge.request_full_state()
        
        @self.bridge.on("disconnected")
        def on_disconnected(_):
            print(f"\n{Colors.warning('游戏已断开连接')}")
            self.prompt = f"{Colors.YELLOW}(断开) {Colors.BOLD}isaac> {Colors.RESET}"
        
        @self.bridge.on("command_result")
        def on_command_result(result):
            command = result.get('command', '')
            success = result.get('success', False)
            output = result.get('result', '')
            error = result.get('error', '')
            
            cmd_obj = CommandRecord(
                command=command,
                timestamp=time.time(),
                success=success,
                result=output or error
            )
            self.command_history.append(cmd_obj)
            
            if output:
                print(f"{Colors.info('输出:')} {output}")
            
            if success:
                print(f"{Colors.success('✓ 执行成功')}")
            else:
                print(f"{Colors.error(f'✗ 执行失败: {error}')}")
        
        @self.bridge.on("event")
        def on_event(event):
            """显示事件"""
            if hasattr(event, 'type'):
                print(f"{Colors.MAGENTA}[事件] {event.type}{Colors.RESET}")
    
    # ==================== 命令实现 ====================
    
    def do_help(self, arg):
        """显示帮助"""
        help_text = f"""
{Colors.BOLD}可用命令:{Colors.RESET}

{Colors.CYAN}控制台命令 (发送到游戏):{Colors.RESET}
  直接输入命令并回车执行
  例如: giveitem c1, spawn Monstro, stage 5a

{Colors.CYAN}系统命令:{Colors.RESET}
  help           - 显示此帮助
  status         - 显示连接状态
  clear          - 清屏
  history        - 显示命令历史
  quit / exit    - 退出

{Colors.CYAN}常用控制台指令参考:{Colors.RESET}
"""
        print(help_text)
        
        for cmd, desc in self.COMMON_COMMANDS.items():
            print(f"  {Colors.YELLOW}{cmd:<15}{Colors.RESET} - {desc}")
        
        print(f"""
{Colors.CYAN}示例:{Colors.RESET}
  {Colors.GREEN}giveitem c1{Colors.RESET}        - 给予以撒的眼泪
  {Colors.GREEN}spawn Monstro{Colors.RESET}     - 生成 Monstro
  {Colors.GREEN}stage 5a{Colors.RESET}          - 传送到第5层
  {Colors.GREEN}goto d.10{Colors.RESET}         - 传送到房间10
  {Colors.GREEN}lua print(game:GetFrameCount()){Colors.RESET} - 执行 Lua
  {Colors.GREEN}debug 1{Colors.RESET}           - 开启调试模式
  {Colors.GREEN}achievement 1{Colors.RESET}     - 解锁第一个成就
""")
    
    def do_status(self, _):
        """显示连接状态"""
        if self.bridge.is_connected():
            print(f"{Colors.success('✓ 已连接到游戏')}")
            stats = self.bridge.get_stats()
            print(f"  消息接收: {stats['messages_received']}")
            print(f"  命令发送: {stats['commands_sent']}")
        else:
            print(f"{Colors.warning('✗ 等待游戏连接中...')}")
            print(f"  服务器: 127.0.0.1:9527")
        
        print(f"  命令历史: {len(self.command_history)} 条")
    
    def do_clear(self, _):
        """清屏"""
        import os
        os.system('cls' if os.name == 'nt' else 'clear')
        print(self.intro)
    
    def do_history(self, arg):
        """显示命令历史"""
        if not self.command_history:
            print(f"{Colors.warning('暂无命令历史')}")
            return
        
        # 显示最近的10条
        recent = self.command_history[-10:]
        print(f"{Colors.BOLD}最近 10 条命令:{Colors.RESET}")
        
        for cmd in recent:
            status = Colors.success("✓") if cmd.success else Colors.error("✗")
            print(f"  {status} {cmd.command}")
    
    def do_quit(self, _):
        """退出"""
        self.running = False
        self.bridge.stop()
        print(f"{Colors.info('再见!')}")
        return True
    
    def do_exit(self, _):
        """退出"""
        return self.do_quit(_)
    
    # ==================== 默认命令处理 ====================
    
    def default(self, line: str):
        """处理控制台命令"""
        # 忽略空行
        if not line.strip():
            return
        
        # 检查连接
        if not self.bridge.is_connected():
            print(f"{Colors.warning('等待游戏连接中...')}")
            return
        
        # 发送控制台命令
        self.bridge.send_console_command(line.strip())
    
    # ==================== 自动补全 ====================
    
    def completenames(self, text: str, *ignored) -> list[str]:
        """补全命令名"""
        commands = ['help', 'status', 'clear', 'history', 'quit', 'exit']
        commands += list(self.COMMON_COMMANDS.keys())
        
        return [cmd for cmd in commands if cmd.startswith(text.lower())]
    
    def completedefault(self, text: str, line: str, begidx: int, endidx: int) -> list[str]:
        """默认补全"""
        return []


def main():
    """主函数"""
    import os
    
    # 确保在正确目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)) or '.')
    
    console = IsaacConsole()
    
    try:
        print(f"{Colors.info('服务器已启动在 127.0.0.1:9527')}")
        print(f"{Colors.info('请启动游戏并加载 SocketBridge mod')}\n")
        console.cmdloop()
    except KeyboardInterrupt:
        print(f"\n{Colors.info('正在退出...')}")
    except Exception as e:
        print(f"{Colors.error(f'错误: {e}')}")
        import traceback
        traceback.print_exc()
    finally:
        console.bridge.stop()


if __name__ == "__main__":
    main()
