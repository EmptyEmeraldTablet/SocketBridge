"""
高级AI示例 - 使用对象跟踪和空间感知

演示如何使用游戏跟踪器和空间模型构建更智能的AI
"""

import math
import time
import logging
from typing import Tuple, Optional, List, Dict, Any
from isaac_bridge import IsaacBridge, GameDataAccessor
from game_tracker import ObjectTracker, Position, Velocity, Enemy, Projectile
from game_space import GameSpace, ThreatAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("AdvancedAI")


class AdvancedAI:
    """高级AI控制器 - 使用对象跟踪和空间感知"""
    
    def __init__(self, bridge: IsaacBridge):
        self.bridge = bridge
        self.data = GameDataAccessor(bridge)
        
        # 核心组件
        self.tracker = ObjectTracker(max_missing_frames=30)
        self.space = GameSpace(grid_size=40.0)
        self.threat_analyzer = None
        
        # AI状态
        self.last_action_frame = 0
        self.action_interval = 3  # 每3帧决策一次
        self.current_room_index = -1
        
        # 统计信息
        self.stats = {
            "decisions_made": 0,
            "evasions": 0,
            "attacks": 0,
            "tactical_moves": 0
        }
        
        # 注册事件回调
        self._setup_callbacks()
    
    def _setup_callbacks(self):
        """设置事件回调"""
        @self.bridge.on("data")
        def on_data_update(data):
            """处理数据更新"""
            self._update_state(data)
    
    def _update_state(self, data: Dict[str, Any]):
        """更新AI状态"""
        # 获取当前帧
        frame = self.bridge.state.frame
        room_index = self.bridge.state.room_index
        
        # 检查房间是否变化
        if room_index != self.current_room_index:
            self._on_room_change(room_index)
            self.current_room_index = room_index
        
        # 获取玩家位置
        player_data = self.data.get_player_position()
        if not player_data:
            return
        
        player_pos = Position(
            player_data.get("pos", {}).get("x", 0),
            player_data.get("pos", {}).get("y", 0)
        )
        
        # 获取敌人和投射物数据
        enemies = self.data.get_enemies() or []
        projectiles = self.data.get_projectiles() or {}
        
        # 更新跟踪器
        self.tracker.update(frame, enemies, projectiles)
        
        # 更新空间模型
        if self.space.player_position:
            self.space.update(player_pos, self.tracker)
        
        # 更新威胁分析器
        if self.threat_analyzer:
            self.threat_analyzer.space = self.space
            self.threat_analyzer.tracker = self.tracker
    
    def _on_room_change(self, room_index: int):
        """房间变化时的处理"""
        logger.info(f"Room changed to {room_index}")
        
        # 获取房间信息
        room_info = self.data.get_room_info()
        room_layout = self.data.get_room_layout()
        
        if room_info and room_layout:
            # 初始化空间模型
            self.space.initialize_from_room(room_info, room_layout)
            
            # 创建威胁分析器
            self.threat_analyzer = ThreatAnalyzer(self.space, self.tracker)
            
            logger.info(f"Space initialized for room {room_index}")
    
    def update(self) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        每帧更新，返回 (移动方向, 射击方向)
        方向值: -1, 0, 1
        """
        frame = self.bridge.state.frame
        
        # 检查是否需要决策
        if frame - self.last_action_frame < self.action_interval:
            return (0, 0), (0, 0)
        
        self.last_action_frame = frame
        
        # 获取玩家位置
        player_data = self.data.get_player_position()
        if not player_data:
            return (0, 0), (0, 0)
        
        player_pos = Position(
            player_data.get("pos", {}).get("x", 0),
            player_data.get("pos", {}).get("y", 0)
        )
        
        # 如果威胁分析器未初始化，使用简单策略
        if not self.threat_analyzer:
            return self._simple_strategy(player_pos)
        
        # 使用高级策略
        return self._advanced_strategy(player_pos)
    
    def _simple_strategy(self, player_pos: Position) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """简单策略（当空间模型未初始化时）"""
        enemies = self.tracker.get_active_enemies()
        projectiles = self.tracker.get_enemy_projectiles()
        
        # 移动决策：远离危险
        move_dir = self._decide_movement_simple(player_pos, enemies, projectiles)
        
        # 射击决策：朝向最近的敌人
        shoot_dir = self._decide_shooting_simple(player_pos, enemies)
        
        return move_dir, shoot_dir
    
    def _advanced_strategy(self, player_pos: Position) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """高级策略（使用威胁分析）"""
        # 获取威胁分析
        threat_analysis = self.threat_analyzer.analyze_player_threat(player_pos)
        
        # 获取推荐行动
        recommendation = self.threat_analyzer.get_recommended_action(player_pos)
        
        # 更新统计
        self.stats["decisions_made"] += 1
        if recommendation["action"] == "evade":
            self.stats["evasions"] += 1
        elif recommendation["action"] == "tactical_move":
            self.stats["tactical_moves"] += 1
        
        # 转换为离散方向
        move_dir = self._continuous_to_discrete(recommendation["move_dir"])
        shoot_dir = self._continuous_to_discrete(recommendation["shoot_dir"])
        
        # 记录决策
        logger.debug(f"Decision: {recommendation['action']}, "
                    f"threat={threat_analysis['threat_level']}, "
                    f"move={move_dir}, shoot={shoot_dir}")
        
        return move_dir, shoot_dir
    
    def _decide_movement_simple(self, player_pos: Position, 
                                 enemies: List[Enemy], 
                                 projectiles: List[Projectile]) -> Tuple[int, int]:
        """简单移动决策"""
        danger_x, danger_y = 0.0, 0.0
        
        # 计算来自投射物的威胁
        for proj in projectiles:
            dx = proj.pos.x - player_pos.x
            dy = proj.pos.y - player_pos.y
            dist = math.sqrt(dx*dx + dy*dy)
            
            if dist < 150 and dist > 0:
                weight = (150 - dist) / 150
                danger_x += dx / dist * weight
                danger_y += dy / dist * weight
        
        # 计算来自敌人的威胁
        for enemy in enemies:
            dx = enemy.pos.x - player_pos.x
            dy = enemy.pos.y - player_pos.y
            dist = math.sqrt(dx*dx + dy*dy)
            
            if dist < 300 and dist > 0:
                weight = (300 - dist) / 300 * 0.8
                if enemy.is_boss:
                    weight *= 1.5
                danger_x += dx / dist * weight
                danger_y += dy / dist * weight
        
        # 转换为方向
        move_x = 0
        move_y = 0
        
        if danger_x > 0.1:
            move_x = -1
        elif danger_x < -0.1:
            move_x = 1
        
        if danger_y > 0.1:
            move_y = -1
        elif danger_y < -0.1:
            move_y = 1
        
        return (move_x, move_y)
    
    def _decide_shooting_simple(self, player_pos: Position, 
                                 enemies: List[Enemy]) -> Tuple[int, int]:
        """简单射击决策"""
        if not enemies:
            return (0, 0)
        
        # 找到最近的敌人
        nearest = min(enemies, key=lambda e: e.pos.distance_to(player_pos))
        
        # 计算方向
        dx = nearest.pos.x - player_pos.x
        dy = nearest.pos.y - player_pos.y
        dist = math.sqrt(dx*dx + dy*dy)
        
        if dist == 0:
            return (0, 0)
        
        # 转换为离散方向
        shoot_x = 0
        shoot_y = 0
        
        if abs(dx) > abs(dy):
            shoot_x = 1 if dx > 0 else -1
        else:
            shoot_y = 1 if dy > 0 else -1
        
        return (shoot_x, shoot_y)
    
    def _continuous_to_discrete(self, continuous: Tuple[float, float]) -> Tuple[int, int]:
        """将连续方向转换为离散方向"""
        x, y = continuous
        
        # 阈值
        threshold = 0.3
        
        discrete_x = 0
        discrete_y = 0
        
        if x > threshold:
            discrete_x = 1
        elif x < -threshold:
            discrete_x = -1
        
        if y > threshold:
            discrete_y = 1
        elif y < -threshold:
            discrete_y = -1
        
        return (discrete_x, discrete_y)
    
    def get_tracked_objects_info(self) -> Dict[str, Any]:
        """获取跟踪对象信息"""
        active_enemies = self.tracker.get_active_enemies()
        enemy_projectiles = self.tracker.get_enemy_projectiles()
        
        return {
            "active_enemies": len(active_enemies),
            "enemy_projectiles": len(enemy_projectiles),
            "tracker_stats": self.tracker.get_stats(),
            "enemies": [
                {
                    "id": e.id,
                    "type": e.obj_type,
                    "hp": e.hp,
                    "max_hp": e.max_hp,
                    "is_boss": e.is_boss,
                    "is_champion": e.is_champion,
                    "position": (e.pos.x, e.pos.y),
                    "velocity": (e.vel.x, e.vel.y),
                    "movement_pattern": e.movement_pattern,
                    "lifetime_frames": e.get_lifetime_frames()
                }
                for e in active_enemies
            ]
        }
    
    def get_space_info(self) -> Dict[str, Any]:
        """获取空间信息"""
        if not self.space.player_position:
            return {}
        
        return {
            "space_features": self.space.get_space_features(),
            "grid_size": (self.space.grid_width, self.space.grid_height),
            "threat_sources": len(self.space.threat_sources)
        }
    
    def get_threat_info(self) -> Optional[Dict[str, Any]]:
        """获取威胁信息"""
        if not self.threat_analyzer or not self.space.player_position:
            return None
        
        return self.threat_analyzer.analyze_player_threat(self.space.player_position)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取AI统计信息"""
        return {
            **self.stats,
            "tracker_stats": self.tracker.get_stats(),
            "space_info": self.get_space_info()
        }


def main():
    """主函数"""
    # 创建桥接
    bridge = IsaacBridge()
    
    # 创建AI
    ai = AdvancedAI(bridge)
    
    # 启动桥接
    bridge.start()
    
    logger.info("Advanced AI started")
    
    try:
        # 主循环
        while True:
            # 获取AI决策
            move_dir, shoot_dir = ai.update()
            
            # 发送控制指令
            if move_dir != (0, 0) or shoot_dir != (0, 0):
                bridge.send_input(move_dir=move_dir, shoot_dir=shoot_dir)
            
            # 每60帧输出一次状态
            if bridge.state.frame % 60 == 0:
                logger.info(f"Frame {bridge.state.frame}: "
                           f"Enemies={len(ai.tracker.get_active_enemies())}, "
                           f"Projectiles={len(ai.tracker.get_enemy_projectiles())}")
                
                # 输出威胁信息
                threat_info = ai.get_threat_info()
                if threat_info:
                    logger.info(f"Threat level: {threat_info['threat_level']}, "
                               f"Current threat: {threat_info['current_threat']:.2f}")
            
            # 控制更新频率
            time.sleep(0.016)  # ~60 FPS
    
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        bridge.stop()


if __name__ == "__main__":
    main()
