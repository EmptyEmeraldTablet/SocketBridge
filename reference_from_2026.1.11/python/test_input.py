"""
以撒的结合 - 随机按键测试脚本

用于测试游戏控制是否正常工作
随机触发所有可用操控按键
"""

import random
import time
import threading
from isaac_bridge import IsaacBridge
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("InputTest")


class RandomInputTester:
    """随机输入测试器"""
    
    # 所有可能的输入组合
    MOVE_DIRECTIONS = [
        (0, 0),   # 停止
        (1, 0),   # 右
        (-1, 0),  # 左
        (0, 1),   # 下
        (0, -1),  # 上
        (1, 1),   # 右下
        (1, -1),  # 右上
        (-1, 1),  # 左下
        (-1, -1), # 左上
    ]
    
    SHOOT_DIRECTIONS = [
        (0, 0),   # 不射击
        (1, 0),   # 右
        (-1, 0),  # 左
        (0, 1),   # 下
        (0, -1),  # 上
    ]
    
    def __init__(self, bridge: IsaacBridge, input_interval: float = 0.1):
        self.bridge = bridge
        self.input_interval = input_interval
        self.running = False
        self.stats = {
            "total_inputs": 0,
            "move_inputs": 0,
            "shoot_inputs": 0,
            "action_inputs": 0,
        }
    
    def start(self):
        """启动测试"""
        self.running = True
        logger.info("开始随机输入测试...")
        logger.info("按 Ctrl+C 停止测试")
        self._test_loop()
    
    def stop(self):
        """停止测试"""
        self.running = False
        # 发送停止指令
        self.bridge.send_input(move=(0, 0), shoot=(0, 0))
        self._print_stats()
    
    def _test_loop(self):
        """测试主循环"""
        try:
            while self.running:
                if self.bridge.is_connected():
                    # 随机选择测试模式
                    test_mode = random.choice(['move', 'shoot', 'action', 'combined'])
                    
                    if test_mode == 'move':
                        self._test_movement()
                    elif test_mode == 'shoot':
                        self._test_shooting()
                    elif test_mode == 'action':
                        self._test_actions()
                    else:  # combined
                        self._test_combined()
                
                time.sleep(self.input_interval)
                
        except KeyboardInterrupt:
            self.stop()
    
    def _test_movement(self):
        """测试移动"""
        move_dir = random.choice(self.MOVE_DIRECTIONS)
        success = self.bridge.send_input(move=move_dir, shoot=(0, 0))
        if success:
            self.stats["total_inputs"] += 1
            self.stats["move_inputs"] += 1
            logger.debug(f"移动: {move_dir}")
    
    def _test_shooting(self):
        """测试射击"""
        shoot_dir = random.choice(self.SHOOT_DIRECTIONS)
        success = self.bridge.send_input(move=(0, 0), shoot=shoot_dir)
        if success:
            self.stats["total_inputs"] += 1
            self.stats["shoot_inputs"] += 1
            logger.debug(f"射击: {shoot_dir}")
    
    def _test_actions(self):
        """测试动作按键"""
        # 随机选择一个或多个动作
        actions = []
        
        if random.random() < 0.3:  # 30% 概率触发 use_item
            actions.append('use_item')
        if random.random() < 0.2:  # 20% 概率触发 use_bomb
            actions.append('use_bomb')
        if random.random() < 0.1:  # 10% 概率触发 use_card
            actions.append('use_card')
        if random.random() < 0.1:  # 10% 概率触发 use_pill
            actions.append('use_pill')
        if random.random() < 0.05:  # 5% 概率触发 drop
            actions.append('drop')
        
        if not actions:
            return
        
        # 构建命令参数
        kwargs = {'move': (0, 0), 'shoot': (0, 0)}
        for action in actions:
            kwargs[action] = True
        
        success = self.bridge.send_input(**kwargs)
        if success:
            self.stats["total_inputs"] += len(actions)
            self.stats["action_inputs"] += len(actions)
            logger.info(f"动作: {actions}")
    
    def _test_combined(self):
        """测试组合输入"""
        move_dir = random.choice(self.MOVE_DIRECTIONS)
        shoot_dir = random.choice(self.SHOOT_DIRECTIONS)
        
        # 随机添加一个动作
        action = random.choice(['use_item', 'use_bomb', None])
        kwargs = {'move': move_dir, 'shoot': shoot_dir}
        if action:
            kwargs[action] = True
        
        success = self.bridge.send_input(**kwargs)
        if success:
            self.stats["total_inputs"] += 1
            if action:
                self.stats["action_inputs"] += 1
            logger.info(f"组合: 移动={move_dir}, 射击={shoot_dir}, 动作={action}")
    
    def _print_stats(self):
        """打印统计信息"""
        logger.info("=" * 50)
        logger.info("测试统计:")
        logger.info(f"  总输入次数: {self.stats['total_inputs']}")
        logger.info(f"  移动输入: {self.stats['move_inputs']}")
        logger.info(f"  射击输入: {self.stats['shoot_inputs']}")
        logger.info(f"  动作输入: {self.stats['action_inputs']}")
        logger.info("=" * 50)


def main():
    """主函数"""
    bridge = IsaacBridge(host="127.0.0.1", port=9527)
    tester = RandomInputTester(bridge, input_interval=0.1)
    
    # 事件处理
    @bridge.on("connected")
    def on_connected(info):
        logger.info(f"游戏已连接: {info}")
        # 使用 FORCE_AI 模式进行测试（确保始终可以控制）
        bridge.send_command("SET_CONTROL_MODE", {"mode": "FORCE_AI"})
        logger.info("控制模式: FORCE_AI (强制AI控制)")
        logger.info("开始发送随机输入...")
    
    @bridge.on("disconnected")
    def on_disconnected(_):
        logger.warning("游戏断开连接，停止测试")
        tester.stop()
    
    @bridge.on("event:PLAYER_DEATH")
    def on_death(_):
        logger.warning("玩家死亡! (这是测试，忽略)")
    
    @bridge.on("event:PLAYER_DAMAGE")
    def on_damage(data):
        logger.warning(f"受到伤害: {data.get('amount', '?')} (这是测试，继续)")
    
    # 启动
    bridge.start()
    
    try:
        # 等待连接
        while not bridge.is_connected():
            time.sleep(0.5)
        
        # 开始测试
        tester.start()
        
    except KeyboardInterrupt:
        logger.info("用户中断")
        tester.stop()
    finally:
        bridge.stop()
        logger.info("测试结束")


if __name__ == "__main__":
    main()
