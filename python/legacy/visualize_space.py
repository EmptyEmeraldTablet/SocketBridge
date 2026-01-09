"""
空间可视化工具

将游戏空间和威胁场可视化输出到控制台
用于调试和理解空间模型的工作原理
"""

import time
from typing import Dict, Any, List, Tuple
from isaac_bridge import IsaacBridge, GameDataAccessor
from game_tracker import ObjectTracker, Position
from game_space import GameSpace, ThreatAnalyzer


class SpaceVisualizer:
    """空间可视化器"""
    
    def __init__(self, bridge: IsaacBridge, grid_size: float = 40.0):
        self.bridge = bridge
        self.data = GameDataAccessor(bridge)
        
        # 核心组件
        self.tracker = ObjectTracker(max_missing_frames=30)
        self.space = GameSpace(grid_size=grid_size)
        self.threat_analyzer = None
        
        # 可视化设置
        self.current_room_index = -1
        self.player_pos = None
        
        # 设置回调
        self._setup_callbacks()
    
    def _setup_callbacks(self):
        """设置事件回调"""
        @self.bridge.on("data")
        def on_data_update(data):
            self._update_state(data)
    
    def _update_state(self, data: Dict[str, Any]):
        """更新状态"""
        frame = self.bridge.state.frame
        room_index = self.bridge.state.room_index
        
        # 检查房间变化
        if room_index != self.current_room_index:
            self._on_room_change(room_index)
            self.current_room_index = room_index
        
        # 获取玩家位置
        player_data = self.data.get_player_position()
        if not player_data:
            return
        
        self.player_pos = Position(
            player_data.get("pos", {}).get("x", 0),
            player_data.get("pos", {}).get("y", 0)
        )
        
        # 获取敌人和投射物
        enemies = self.data.get_enemies() or []
        projectiles = self.data.get_projectiles() or {}
        
        # 更新跟踪器
        self.tracker.update(frame, enemies, projectiles)
        
        # 更新空间
        if self.space.player_position:
            self.space.update(self.player_pos, self.tracker)
        
        # 更新威胁分析器
        if self.threat_analyzer:
            self.threat_analyzer.space = self.space
            self.threat_analyzer.tracker = self.tracker
    
    def _on_room_change(self, room_index: int):
        """房间变化处理"""
        print(f"\n房间变化: {room_index}")
        
        # 获取房间信息
        room_info = self.data.get_room_info()
        room_layout = self.data.get_room_layout()
        
        if room_info and room_layout:
            self.space.initialize_from_room(room_info, room_layout)
            self.threat_analyzer = ThreatAnalyzer(self.space, self.tracker)
            
            print(f"空间初始化: {self.space.grid_width}x{self.space.grid_height} 网格")
    
    def visualize(self, show_threat: bool = True, show_objects: bool = True):
        """可视化空间"""
        if not self.space.grid:
            print("空间未初始化")
            return
        
        # 获取威胁分析
        threat_info = None
        if self.threat_analyzer and self.player_pos:
            threat_info = self.threat_analyzer.analyze_player_threat(self.player_pos)
        
        # 打印标题
        print(f"\n{'='*80}")
        print(f"空间可视化 - 帧 {self.bridge.state.frame}")
        print(f"{'='*80}")
        
        # 打印威胁信息
        if threat_info:
            print(f"\n威胁分析:")
            print(f"  当前威胁等级: {threat_info['current_threat']:.3f}")
            print(f"  威胁分类: {threat_info['threat_level']}")
            print(f"  最近敌人距离: {threat_info['nearest_enemy_distance']:.1f}")
            print(f"  最近投射物距离: {threat_info['nearest_projectile_distance']:.1f}")
            print(f"  危险投射物数量: {threat_info['dangerous_projectiles_count']}")
        
        # 打印空间网格
        self._print_grid(show_threat, show_objects)
        
        # 打印图例
        self._print_legend()
    
    def _print_grid(self, show_threat: bool, show_objects: bool):
        """打印空间网格"""
        # 获取玩家网格坐标
        player_gx, player_gy = -1, -1
        if self.player_pos:
            player_gx, player_gy = self.space._world_to_grid(self.player_pos)
        
        # 获取敌人网格坐标
        enemy_positions = []
        if show_objects:
            for enemy in self.tracker.get_active_enemies():
                gx, gy = self.space._world_to_grid(enemy.pos)
                enemy_positions.append((gx, gy))
        
        # 获取投射物网格坐标
        projectile_positions = []
        if show_objects:
            for proj in self.tracker.get_enemy_projectiles():
                gx, gy = self.space._world_to_grid(proj.pos)
                projectile_positions.append((gx, gy))
        
        # 打印网格
        for gy in range(self.space.grid_height - 1, -1, -1):
            row = ""
            for gx in range(self.space.grid_width):
                cell = self.space.grid.get((gx, gy))
                
                if not cell:
                    row += "?"
                    continue
                
                # 检查是否是玩家位置
                if gx == player_gx and gy == player_gy:
                    row += "@"
                    continue
                
                # 检查是否是敌人位置
                if (gx, gy) in enemy_positions:
                    row += "E"
                    continue
                
                # 检查是否是投射物位置
                if (gx, gy) in projectile_positions:
                    row += "*"
                    continue
                
                # 根据单元格类型显示
                if not cell.is_walkable():
                    row += "#"
                elif show_threat:
                    # 根据威胁等级显示
                    if cell.threat_level < 0.2:
                        row += "."
                    elif cell.threat_level < 0.4:
                        row += "°"
                    elif cell.threat_level < 0.6:
                        row += "°"
                    elif cell.threat_level < 0.8:
                        row += "^"
                    else:
                        row += "!"
                else:
                    row += "."
            
            print(row)
    
    def _print_legend(self):
        """打印图例"""
        print(f"\n图例:")
        print(f"  @ - 玩家位置")
        print(f"  E - 敌人")
        print(f"  * - 投射物")
        print(f"  # - 障碍物")
        print(f"  . - 安全区域 (威胁 < 0.2)")
        print(f"  ° - 低威胁 (0.2 - 0.4)")
        print(f"  ° - 中威胁 (0.4 - 0.6)")
        print(f"  ^ - 高威胁 (0.6 - 0.8)")
        print(f"  ! - 极高威胁 (> 0.8)")
    
    def print_threat_heatmap(self):
        """打印威胁热力图（数值版本）"""
        if not self.space.grid:
            print("空间未初始化")
            return
        
        print(f"\n威胁热力图:")
        print(f"{'='*80}")
        
        for gy in range(self.space.grid_height - 1, -1, -1):
            row = ""
            for gx in range(self.space.grid_width):
                cell = self.space.grid.get((gx, gy))
                
                if not cell:
                    row += " ? "
                elif not cell.is_walkable():
                    row += "###"
                else:
                    threat = cell.threat_level
                    row += f"{threat:3.0f}"
            
            print(row)
        
        print(f"{'='*80}")
        print(f"威胁等级: 0-9 (0=安全, 9=极高威胁)")
    
    def print_object_positions(self):
        """打印对象位置"""
        print(f"\n对象位置:")
        print(f"{'='*80}")
        
        # 玩家位置
        if self.player_pos:
            print(f"玩家: ({self.player_pos.x:.1f}, {self.player_pos.y:.1f})")
        
        # 敌人位置
        enemies = self.tracker.get_active_enemies()
        if enemies:
            print(f"\n敌人 ({len(enemies)}):")
            for enemy in enemies:
                print(f"  ID={enemy.id}, 类型={enemy.obj_type}, "
                      f"位置=({enemy.pos.x:.1f}, {enemy.pos.y:.1f}), "
                      f"血量={enemy.hp:.1f}/{enemy.max_hp:.1f}")
        
        # 投射物位置
        projectiles = self.tracker.get_enemy_projectiles()
        if projectiles:
            print(f"\n投射物 ({len(projectiles)}):")
            for proj in projectiles:
                print(f"  ID={proj.id}, "
                      f"位置=({proj.pos.x:.1f}, {proj.pos.y:.1f}), "
                      f"速度=({proj.vel.x:.1f}, {proj.vel.y:.1f})")
        
        print(f"{'='*80}")


def main():
    """主函数"""
    print("空间可视化工具")
    print("="*80)
    
    # 创建桥接
    bridge = IsaacBridge()
    
    # 创建可视化器
    visualizer = SpaceVisualizer(bridge, grid_size=40.0)
    
    # 启动桥接
    bridge.start()
    
    print("\n可视化工具已启动，等待游戏数据...")
    print("按 Ctrl+C 退出")
    print("每 30 帧输出一次可视化")
    print("="*80)
    
    try:
        last_output_frame = 0
        show_heatmap = False
        
        while True:
            frame = bridge.state.frame
            
            # 每30帧输出一次可视化
            if frame - last_output_frame >= 30:
                # 切换显示模式
                if show_heatmap:
                    visualizer.print_threat_heatmap()
                else:
                    visualizer.visualize(show_threat=True, show_objects=True)
                
                visualizer.print_object_positions()
                
                show_heatmap = not show_heatmap
                last_output_frame = frame
            
            # 控制更新频率
            time.sleep(0.016)  # ~60 FPS
    
    except KeyboardInterrupt:
        print("\n\n正在退出...")
        print("可视化工具已停止")
        bridge.stop()


if __name__ == "__main__":
    main()
