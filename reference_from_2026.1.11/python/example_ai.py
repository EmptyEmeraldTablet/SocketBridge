"""
以撒的结合 - AI 控制示例

演示如何使用 IsaacBridge 实现简单的 AI 控制逻辑
"""

import math
import time
from typing import Tuple, Optional, List
from isaac_bridge import IsaacBridge, GameDataAccessor, Event
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("IsaacAI")


class SimpleAI:
    """简单 AI 控制器示例"""
    
    def __init__(self, bridge: IsaacBridge):
        self.bridge = bridge
        self.data = GameDataAccessor(bridge)
        
        # AI 状态
        self.last_action_frame = 0
        self.action_interval = 3  # 每3帧决策一次
    
    def update(self) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        每帧更新，返回 (移动方向, 射击方向)
        方向值: -1, 0, 1
        """
        # 获取玩家位置
        player_pos = self.data.get_player_position()
        if not player_pos:
            return (0, 0), (0, 0)
        
        pos = player_pos.get("pos", {})
        player_x = pos.get("x", 0)
        player_y = pos.get("y", 0)
        
        # 获取敌人和投射物
        enemies = self.data.get_enemies()
        projectiles = self.data.get_enemy_projectiles()
        
        # 决策: 移动
        move_dir = self._decide_movement(player_x, player_y, enemies, projectiles)
        
        # 决策: 射击
        shoot_dir = self._decide_shooting(player_x, player_y, enemies)
        
        return move_dir, shoot_dir
    
    def _decide_movement(self, px: float, py: float, 
                         enemies: List[dict], 
                         projectiles: List[dict]) -> Tuple[int, int]:
        """决策移动方向"""
        # 简单策略: 远离最近的危险
        danger_x, danger_y = 0.0, 0.0
        
        # 计算来自投射物的威胁
        for proj in projectiles:
            proj_pos = proj.get("pos", {})
            dx = proj_pos.get("x", 0) - px
            dy = proj_pos.get("y", 0) - py
            dist = math.sqrt(dx * dx + dy * dy)
            
            if dist < 150 and dist > 0:
                # 加权远离（危险在正方向，我们往负方向移动）
                weight = (150 - dist) / 150
                danger_x += dx / dist * weight
                danger_y += dy / dist * weight
        
        # 计算来自敌人的威胁（增大检测范围到 300）
        for enemy in enemies:
            enemy_pos = enemy.get("pos", {})
            dx = enemy_pos.get("x", 0) - px
            dy = enemy_pos.get("y", 0) - py
            dist = math.sqrt(dx * dx + dy * dy)
            
            if dist < 300 and dist > 0:  # 增大范围
                weight = (300 - dist) / 300 * 0.8  # 增加权重
                danger_x += dx / dist * weight
                danger_y += dy / dist * weight
        
        # 调试输出
        if abs(danger_x) > 0.01 or abs(danger_y) > 0.01:
            logger.debug(f"Danger vector: ({danger_x:.2f}, {danger_y:.2f})")
        
        # 转换为方向（降低阈值到 0.1）
        move_x = 0
        move_y = 0
        
        if danger_x > 0.1:
            move_x = -1  # 向左躲避
        elif danger_x < -0.1:
            move_x = 1   # 向右躲避
        
        if danger_y > 0.1:
            move_y = -1  # 向上躲避
        elif danger_y < -0.1:
            move_y = 1   # 向下躲避
        
        return (move_x, move_y)
    
    def _decide_shooting(self, px: float, py: float, 
                         enemies: List[dict]) -> Tuple[int, int]:
        """决策射击方向"""
        if not enemies:
            return (0, 0)
        
        # 找最近的敌人
        nearest = None
        min_dist = float('inf')
        
        for enemy in enemies:
            dist = enemy.get("distance", 9999)
            if dist < min_dist:
                min_dist = dist
                nearest = enemy
        
        if not nearest or min_dist > 500:
            return (0, 0)
        
        # 计算射击方向
        enemy_pos = nearest.get("pos", {})
        dx = enemy_pos.get("x", 0) - px
        dy = enemy_pos.get("y", 0) - py
        
        # 转换为四方向
        shoot_x = 0
        shoot_y = 0
        
        if abs(dx) > abs(dy):
            shoot_x = 1 if dx > 0 else -1
        else:
            shoot_y = 1 if dy > 0 else -1
        
        return (shoot_x, shoot_y)


def main():
    """主函数"""
    bridge = IsaacBridge(host="127.0.0.1", port=9527)
    ai = SimpleAI(bridge)
    
    # 事件处理
    @bridge.on("connected")
    def on_connected(info):
        logger.info(f"Game connected: {info}")
    
    @bridge.on("event:PLAYER_DAMAGE")
    def on_damage(data):
        logger.warning(f"Took damage! HP after: {data.get('hp_after', '?')}")
    
    @bridge.on("event:ROOM_CLEAR")
    def on_clear(_):
        logger.info("Room cleared!")
        # 停止输入
        bridge.send_input(move=(0, 0), shoot=(0, 0))
    
    @bridge.on("event:PLAYER_DEATH")
    def on_death(_):
        logger.error("Player died!")
    
    # 启动
    bridge.start()
    logger.info("AI started, waiting for game...")
    
    try:
        update_interval = 1.0 / 30  # 30 FPS
        last_update = time.time()
        debug_counter = 0
        
        while True:
            current_time = time.time()
            
            if current_time - last_update >= update_interval:
                last_update = current_time
                
                if bridge.is_connected():
                    # 获取数据
                    room_info = ai.data.get_room_info()
                    enemies = ai.data.get_enemies()
                    projectiles = ai.data.get_enemy_projectiles()
                    
                    # 调试输出（每秒一次）
                    debug_counter += 1
                    if debug_counter % 30 == 0:
                        player_pos = ai.data.get_player_position()
                        is_clear = room_info.get('is_clear') if room_info else None
                        logger.info(f"State: room_clear={is_clear}, "
                                   f"player_pos={player_pos is not None}, enemies={len(enemies)}, proj={len(projectiles)}")
                    
                    # 判断是否需要战斗控制：有敌人或有投射物
                    # 不依赖 room_info，直接用实际敌人数量判断
                    in_combat = len(enemies) > 0 or len(projectiles) > 0
                    
                    if in_combat:
                        move_dir, shoot_dir = ai.update()
                        
                        # 调试：每秒输出一次决策
                        if debug_counter % 30 == 0:
                            logger.info(f"AI Decision: move={move_dir}, shoot={shoot_dir}")
                        
                        bridge.send_input(move=move_dir, shoot=shoot_dir)
            else:
                time.sleep(0.001)
    
    except KeyboardInterrupt:
        logger.info("Stopping AI...")
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
