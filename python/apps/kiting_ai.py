"""
以撒的结合 - 逃跑型 AI 策略

策略：逃跑优先，保持与敌人适当距离（射程80%），绕圈后撤

核心逻辑：
1. 躲避敌方投射物（最高优先级）
2. 保持与敌人的理想距离
3. 绕圈移动，持续后撤
4. 利用房间边界进行战术性撤退
"""

import math
import time
from typing import Tuple, Optional, List, Dict, Any
from isaac_bridge import IsaacBridge, GameDataAccessor
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("KitingAI")


class KitingAI:
    """
    逃跑型 AI 控制器
    
    策略核心：
    - 优先级1：躲避敌方投射物
    - 优先级2：保持与敌人的理想距离（射程80%）
    - 优先级3：绕圈后撤，利用房间边界
    """
    
    def __init__(self, bridge: IsaacBridge):
        self.bridge = bridge
        self.data = GameDataAccessor(bridge)
        
        # 状态追踪
        self.last_action_frame = 0
        self.action_interval = 2  # 每2帧决策一次
        
        # 策略参数
        self.proj_avoid_distance = 180  # 投射物躲避距离
        self.enemy_avoid_distance = 250  # 敌人基础躲避距离
        
        # 理想距离范围（射程的百分比）
        self.ideal_distance_ratio = 0.8  # 理想距离（80%射程）
        self.distance_tolerance = 0.3  # 距离容差（±30%）
        
        # 房间边界（默认值，会被实际房间大小覆盖）
        self.room_bounds = {
            "min_x": -400,
            "max_x": 400,
            "min_y": -300,
            "max_y": 300
        }
        
        # 移动历史（用于检测是否在绕圈）
        self.position_history = []  # [(x, y, time), ...]
        self.history_max_len = 30
        
        # 敌人历史位置（用于检测追逐）
        self.enemy_position_history = []  # [(x, y, time), ...]
        self.enemy_history_max_len = 20
        
        # 移动方向（顺时针绕圈）
        self.circle_direction = 1  # 1=顺时针, -1=逆时针
        
        # 敌人追逐状态
        self.enemy_chasing = False  # 敌人是否在追逐玩家
        
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
        
        # 更新房间边界
        self._update_room_bounds()
        
        # 记录位置历史
        self._update_position_history(player_x, player_y)
        
        # 获取环境信息
        enemies = self.data.get_enemies()
        projectiles = self.data.get_enemy_projectiles()
        
        # 获取玩家射程（如果有）
        player_range = self._get_player_range()
        print(player_range)
        # 决策
        move_dir, move_reason = self._decide_movement(
            player_x, player_y, enemies, projectiles,
            player_range
        )
        
        # 决策射击（朝向最近的敌人）
        shoot_dir = self._decide_shooting(player_x, player_y, enemies)
        
        # 记录决策日志（偶尔）
        if hasattr(self, '_debug_counter'):
            self._debug_counter += 1
        else:
            self._debug_counter = 1
            
        if self._debug_counter % 60 == 0:
            logger.info(f"Move: {move_dir} ({move_reason}), Shoot: {shoot_dir}, "
                       f"Enemies: {len(enemies)}, Proj: {len(projectiles)}")
        
        return move_dir, shoot_dir
    
    def _update_room_bounds(self):
        """更新房间边界"""
        room_layout = self.data.get_room_layout()
        if room_layout:
            # 房间布局通常包含尺寸信息
            grid_size = room_layout.get("grid_size", {})
            room_size = room_layout.get("room_size", {})
            
            # 计算边界（假设房间中心在原点）
            if room_size:
                width = room_size.get("width", 800)
                height = room_size.get("height", 600)
                self.room_bounds = {
                    "min_x": -width / 2 + 30,   # 留出边距
                    "max_x": width / 2 - 30,
                    "min_y": -height / 2 + 30,
                    "max_y": height / 2 - 30
                }
    
    def _update_position_history(self, x: float, y: float):
        """记录玩家位置历史"""
        self.position_history.append((x, y, time.time()))
        if len(self.position_history) > self.history_max_len:
            self.position_history.pop(0)
    
    def _update_enemy_position_history(self, enemy: dict):
        """记录敌人位置历史（用于检测追逐）"""
        enemy_pos = enemy.get("pos", {})
        ex = enemy_pos.get("x", 0)
        ey = enemy_pos.get("y", 0)
        self.enemy_position_history.append((ex, ey, time.time()))
        if len(self.enemy_position_history) > self.enemy_history_max_len:
            self.enemy_position_history.pop(0)
    
    def _calculate_axis_distance(self, px: float, py: float, ex: float, ey: float) -> Tuple[float, float]:
        """
        计算X/Y轴上的距离
        
        返回: (x轴距离, y轴距离)
        """
        return abs(px - ex), abs(py - ey)
    
    def _is_chasing_player(self, enemy: dict, px: float, py: float) -> bool:
        """
        检测敌人是否在追逐玩家
        
        通过分析敌人位置历史变化，判断是否朝向玩家移动
        """
        if len(self.enemy_position_history) < 5:
            return False
        
        enemy_pos = enemy.get("pos", {})
        ex = enemy_pos.get("x", 0)
        ey = enemy_pos.get("y", 0)
        
        # 计算敌人最近几帧的平均移动方向
        recent_positions = self.enemy_position_history[-10:]
        if len(recent_positions) < 2:
            return False
        
        # 计算敌人移动向量
        dx = ex - recent_positions[0][0]
        dy = ey - recent_positions[0][1]
        
        # 计算指向玩家的向量
        to_player_x = px - ex
        to_player_y = py - ey
        
        # 计算移动方向与指向玩家方向的夹角余弦
        move_magnitude = math.sqrt(dx * dx + dy * dy)
        if move_magnitude < 5:  # 移动太少，无法判断
            return False
        
        to_player_magnitude = math.sqrt(to_player_x**2 + to_player_y**2)
        if to_player_magnitude < 1:
            return False
        
        # 计算点积（夹角余弦）
        dot_product = (dx * to_player_x + dy * to_player_y) / (move_magnitude * to_player_magnitude)
        
        # 如果点积 > 0.5，表示敌人主要朝向玩家移动（夹角小于60度）
        return dot_product > 0.5
    
    def _get_enemy_velocity_direction(self, enemy: dict) -> Tuple[float, float]:
        """
        获取敌人速度方向的归一化向量
        
        返回: (vx_norm, vy_norm)
        """
        velocity = enemy.get("velocity", {})
        vx = velocity.get("x", 0)
        vy = velocity.get("y", 0)
        
        magnitude = math.sqrt(vx * vx + vy * vy)
        if magnitude < 0.1:
            return (0, 0)
        
        return (vx / magnitude, vy / magnitude)
    
    def _get_player_range(self) -> float:
        """获取玩家射程"""
        stats = self.data.get_player_stats()
        if stats:
            return 100  # 默认射程400像素
        return 100

    def _get_player_speed(self) -> float:
        """获取玩家移动速度"""
        stats = self.data.get_player_stats()
        if stats:
            return stats.get("speed", 1.0)
        return 1.0

    def _get_movement_per_frame(self) -> float:
        """
        计算每帧预期移动距离（像素）

        基于玩家MoveSpeed属性估算实际移动距离
        假设速度1.0时每帧移动约6像素（需要根据实际测试调整）
        """
        player_speed = self._get_player_speed()
        BASE_MOVEMENT = 6.0  # 速度1.0时的基准移动距离（像素/帧）
        return player_speed * BASE_MOVEMENT
    
    def _decide_movement(self, px: float, py: float,
                        enemies: List[dict],
                        projectiles: List[dict],
                        player_range: float) -> Tuple[Tuple[int, int], str]:
        """
        决策移动方向
        
        直接根据与敌人位置进行位置调整
        使用玩家移动速度估算每帧移动距离，防止超调
        
        返回: (移动方向元组, 决策原因说明)
        """
        move_x, move_y = 0, 0
        reason = "no_threat"
        
        # 获取每帧预期移动距离
        move_per_frame = self._get_movement_per_frame()
        
        # 计算理想距离（射程的80%）
        ideal_dist = player_range * self.ideal_distance_ratio
        # 动态容差：最小0.3 + 移动距离缓冲，防止超调
        dist_tolerance = max(0.3, move_per_frame * 0.15)
        
        # 直接根据敌人位置调整距离
        if enemies:
            # 找最近的敌人
            nearest = self._find_nearest_enemy(px, py, enemies)
            if nearest:
                enemy_pos = nearest.get("pos", {})
                ex = enemy_pos.get("x", 0)
                ey = enemy_pos.get("y", 0)
                
                # 更新敌人位置历史
                self._update_enemy_position_history(nearest)
                
                # 使用X/Y轴距离判断
                dist_x, dist_y = self._calculate_axis_distance(px, py, ex, ey)
                
                # 检测敌人是否在追逐
                was_chasing = self.enemy_chasing
                self.enemy_chasing = self._is_chasing_player(nearest, px, py)
                
                # 获取敌人速度方向
                enemy_vel = self._get_enemy_velocity_direction(nearest)
                
                # 计算方向向量（从敌人指向玩家）
                to_player_x = px - ex
                to_player_y = py - ey
                
                if dist_x > 0 or dist_y > 0:
                    # 判断是否超出理想距离范围（使用X/Y轴距离的最大值）
                    max_axis_dist = max(dist_x, dist_y)
                    
                    if max_axis_dist < ideal_dist - dist_tolerance:
                        # 太近！需要后退（朝敌人反方向移动）
                        if dist_x > dist_y:
                            # X轴距离更大，沿X轴后退
                            move_x = 1 if px < ex else -1
                        else:
                            # Y轴距离更大，沿Y轴后退
                            move_y = 1 if py < ey else -1
                        reason = "too_close"
                        
                    elif max_axis_dist > ideal_dist + dist_tolerance:
                        # 太远！需要靠近（朝敌人方向移动）
                        if dist_x > dist_y:
                            # X轴距离更大，沿X轴靠近
                            move_x = -1 if px < ex else 1
                        else:
                            # Y轴距离更大，沿Y轴靠近
                            move_y = -1 if py < ey else 1
                        reason = "too_far"
                    else:
                        # 距离合适，执行绕圈移动
                        move_x, move_y, reason = self._calculate_kiting_movement(
                            px, py, ex, ey, enemy_vel, was_chasing
                        )
        
        # 边界检查（防止走出房间）
        margin = 60
        if px < self.room_bounds["min_x"] + margin:
            move_x = max(move_x, 1)
        elif px > self.room_bounds["max_x"] - margin:
            move_x = min(move_x, -1)
            
        if py < self.room_bounds["min_y"] + margin:
            move_y = max(move_y, 1)
        elif py > self.room_bounds["max_y"] - margin:
            move_y = min(move_y, -1)
        
        return (move_x, move_y), reason
    
    def _find_nearest_enemy(self, px: float, py: float,
                            enemies: List[dict]) -> Optional[dict]:
        """找最近的敌人"""
        nearest = None
        min_dist = float('inf')
        
        for enemy in enemies:
            dist = enemy.get("distance", 9999)
            if dist < min_dist:
                min_dist = dist
                nearest = enemy
        
        return nearest
    
    def _calculate_kiting_movement(self, px: float, py: float,
                                    ex: float, ey: float,
                                    enemy_vel: Tuple[float, float],
                                    was_chasing: bool) -> Tuple[int, int, str]:
        """
        计算绕圈移动
        
        Args:
            px, py: 玩家位置
            ex, ey: 敌人位置
            enemy_vel: 敌人速度方向的归一化向量
            was_chasing: 敌人之前是否在追逐
        
        在保持距离的同时，围绕敌人移动
        如果敌人正在追逐，根据敌人速度方向调整绕圈方向
        """
        # 计算垂直于敌人-玩家连线的方向
        # 向量从敌人指向玩家
        to_player_x = px - ex
        to_player_y = py - ey
        
        # 计算当前距离
        current_dist = math.sqrt(to_player_x**2 + to_player_y**2)
        if current_dist < 1:
            current_dist = 1
        
        # 垂直向量（顺时针90度）
        perp_x = -to_player_y
        perp_y = to_player_x
        
        # 归一化
        perp_len = math.sqrt(perp_x**2 + perp_y**2)
        if perp_len > 0:
            perp_x /= perp_len
            perp_y /= perp_len
        
        # 如果敌人正在追逐且有速度，根据速度方向调整绕圈
        if self.enemy_chasing and (enemy_vel[0] != 0 or enemy_vel[1] != 0):
            # 计算敌人速度与垂直向量的点积
            vel_dot_perp = enemy_vel[0] * perp_x + enemy_vel[1] * perp_y
            
            # 如果速度方向与垂直方向相同（顺时针绕圈被追赶），切换为逆时针
            if vel_dot_perp > 0.3:  # 夹角小于约75度
                if self.circle_direction == 1:
                    self.circle_direction = -1
                    logger.debug("Enemy chasing - switching to counter-clockwise")
            elif vel_dot_perp < -0.3:  # 夹角大于约105度
                if self.circle_direction == -1:
                    self.circle_direction = 1
                    logger.debug("Enemy chasing - switching to clockwise")
        
        # 根据移动历史决定绕圈方向
        # 如果一直在原地打转，切换方向
        if len(self.position_history) >= 10:
            recent_movement = self._calculate_recent_movement()
            if recent_movement < 50:  # 移动距离很小
                self.circle_direction *= -1  # 切换方向
        
        # 应用绕圈方向
        move_x = int(round(perp_x * self.circle_direction))
        move_y = int(round(perp_y * self.circle_direction))
        
        # 添加远离敌人的分量（基于玩家移动速度调整）
        # 移动越快，需要的分量越小；移动越慢，需要的分量越大
        move_per_frame = self._get_movement_per_frame()
        away_factor = min(0.5, max(0.2, 2.0 / move_per_frame))  # 动态调整分量
        
        away_x = to_player_x / current_dist * away_factor
        away_y = to_player_y / current_dist * away_factor
        
        move_x = move_x + int(round(away_x))
        move_y = move_y + int(round(away_y))
        
        # 确保方向有效
        move_x = max(-1, min(1, move_x))
        move_y = max(-1, min(1, move_y))
        
        reason = "kiting_chasing" if self.enemy_chasing else "kiting"
        return move_x, move_y, reason
    
    def _calculate_recent_movement(self) -> float:
        """计算最近的移动距离"""
        if len(self.position_history) < 2:
            return 0
        
        total_dist = 0
        for i in range(1, len(self.position_history)):
            x1, y1, _ = self.position_history[i - 1]
            x2, y2, _ = self.position_history[i]
            total_dist += math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
        return total_dist
    
    def _decide_shooting(self, px: float, py: float,
                         enemies: List[dict]) -> Tuple[int, int]:
        """
        决策射击方向
        
        策略：射击最近的敌人，但只朝一个方向射击
        """
        if not enemies:
            return (0, 0)
        
        # 找最近的敌人
        nearest = self._find_nearest_enemy(px, py, enemies)
        if not nearest:
            return (0, 0)
        
        dist = nearest.get("distance", 9999)
        if dist > 600:  # 太远，不射击
            return (0, 0)
        
        # 计算射击方向
        enemy_pos = nearest.get("pos", {})
        ex = enemy_pos.get("x", 0)
        ey = enemy_pos.get("y", 0)
        
        dx = ex - px
        dy = ey - py
        
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
    ai = KitingAI(bridge)
    
    # 事件处理
    @bridge.on("connected")
    def on_connected(info):
        logger.info(f"Game connected: {info}")
        # 使用 AUTO 模式：战斗时AI，空房间手动
        bridge.send_command("SET_CONTROL_MODE", {"mode": "AUTO"})
        logger.info("Control mode: AUTO (AI in combat, manual otherwise)")
        # 请求完整状态
        bridge.request_full_state()
    
    @bridge.on("event:PLAYER_DAMAGE")
    def on_damage(data):
        logger.warning(f"Took damage! HP after: {data.get('hp_after', '?')}")
        # 受伤后暂时停止射击，专注逃跑
        bridge.send_input(move=(0, 0), shoot=(0, 0))
    
    @bridge.on("event:ROOM_CLEAR")
    def on_clear(_):
        logger.info("Room cleared!")
        bridge.send_input(move=(0, 0), shoot=(0, 0))
    
    @bridge.on("event:PLAYER_DEATH")
    def on_death(_):
        logger.error("Player died!")
    
    # 启动
    bridge.start()
    logger.info("Kiting AI started, waiting for game...")
    
    try:
        update_interval = 1.0 / 30  # 30 FPS
        last_update = time.time()
        
        while True:
            current_time = time.time()
            
            if current_time - last_update >= update_interval:
                last_update = current_time
                
                if bridge.is_connected():
                    # 获取数据
                    enemies = ai.data.get_enemies()
                    projectiles = ai.data.get_enemy_projectiles()
                    
                    # 判断是否需要战斗（AUTO 模式下：有敌人才发送输入）
                    in_combat = len(enemies) > 0 or len(projectiles) > 0
                    
                    if in_combat:
                        move_dir, shoot_dir = ai.update()
                        bridge.send_input(move=move_dir, shoot=shoot_dir)
                    else:
                        # 空房间时不发送输入，让玩家手动控制
                        # 不要发送 (0,0)，这会阻止玩家移动
                        pass
            else:
                time.sleep(0.001)
    
    except KeyboardInterrupt:
        logger.info("Stopping AI...")
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
