"""
对象跟踪系统测试工具

用于测试和验证对象跟踪器功能
"""

import time
import json
import sys
from typing import Dict, Any
from isaac_bridge import IsaacBridge, GameDataAccessor
from game_tracker import ObjectTracker, Position


class TrackerTester:
    """跟踪器测试工具"""
    
    def __init__(self, bridge: IsaacBridge):
        self.bridge = bridge
        self.data = GameDataAccessor(bridge)
        
        # 核心组件 - 只保留对象跟踪器
        self.tracker = ObjectTracker(max_missing_frames=30)
        
        # 统计
        self.frame_count = 0
        self.room_changes = 0
        self.current_room_index = -1
        
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
        
        player_pos = Position(
            player_data.get("pos", {}).get("x", 0),
            player_data.get("pos", {}).get("y", 0)
        )
        
        # 获取敌人和投射物
        enemies = self.data.get_enemies() or []
        projectiles = self.data.get_projectiles() or {}
        
        # 更新跟踪器
        self.tracker.update(frame, enemies, projectiles)
        
        self.frame_count += 1
    
    def _on_room_change(self, room_index: int):
        """房间变化处理（刷新模式）"""
        self.room_changes += 1
        
        # 获取房间信息
        room_info = self.data.get_room_info()
        if room_info:
            print(f"\n>>> 进入房间 {room_index} | 类型={room_info.get('room_type')} | 敌人={room_info.get('enemy_count', 0)}")
        else:
            print(f"\n>>> 进入房间 {room_index}")
        
        sys.stdout.flush()
    
    def print_status(self):
        """打印当前状态（刷新模式）"""
        # 清屏并移动光标到左上角
        print("\033[2J\033[H", end="")
        
        print(f"{'='*60}")
        print(f"帧数: {self.frame_count}  |  房间: {self.current_room_index}")
        print(f"{'='*60}")
        
        # 跟踪器统计
        tracker_stats = self.tracker.get_stats()
        print(f"\n跟踪器统计:")
        print(f"  总敌人数: {tracker_stats['total_enemies_seen']}")
        print(f"  活跃敌人: {tracker_stats['active_enemies']}")
        print(f"  击杀敌人: {tracker_stats['enemies_killed']}")
        print(f"  总投射物: {tracker_stats['total_projectiles_seen']}")
        print(f"  活跃投射物: {tracker_stats['active_projectiles']}")
        
        # 活跃敌人详情
        active_enemies = self.tracker.get_active_enemies()
        if active_enemies:
            print(f"\n活跃敌人详情:")
            for enemy in active_enemies:
                print(f"  ID={enemy.id}, 类型={enemy.obj_type}, "
                      f"HP={enemy.hp:.1f}/{enemy.max_hp:.1f}, "
                      f"Pos=({enemy.pos.x:.0f},{enemy.pos.y:.0f}), "
                      f"模式={enemy.movement_pattern}")
        else:
            print(f"\n活跃敌人: 0")
        
        # 刷新输出
        sys.stdout.flush()
        
    def print_enemy_lifecycles(self):
        """打印敌人生命周期信息"""
        print(f"\n{'='*60}")
        print("敌人生命周期统计")
        print(f"{'='*60}")
        
        # 获取所有历史敌人（包括已死亡的）
        all_enemies = list(self.tracker.enemies.values())
        
        if not all_enemies:
            print("暂无敌人数据")
            return
        
        # 按存活时间排序
        all_enemies.sort(key=lambda e: e.get_lifetime_frames(), reverse=True)
        
        print(f"\n总敌人数量: {len(all_enemies)}")
        print(f"存活敌人: {len([e for e in all_enemies if e.is_alive()])}")
        print(f"死亡敌人: {len([e for e in all_enemies if not e.is_alive()])}")
        
        print(f"\n敌人详情:")
        for enemy in all_enemies:
            status = "存活" if enemy.is_alive() else "死亡"
            print(f"  ID={enemy.id}, 类型={enemy.obj_type}, "
                  f"状态={status}, 存活帧数={enemy.get_lifetime_frames()}, "
                  f"移动模式={enemy.movement_pattern}")
            
            # 如果有攻击历史
            if hasattr(enemy, 'attack_pattern') and enemy.attack_pattern:
                avg_interval = enemy.get_avg_attack_interval()
                print(f"    攻击次数: {len(enemy.attack_pattern)}, "
                      f"平均间隔: {avg_interval:.1f}帧")
    
    def export_tracking_data(self, filename: str = "tracking_data.json"):
        """导出跟踪数据"""
        data = {
            "frame_count": self.frame_count,
            "room_changes": self.room_changes,
            "current_room": self.current_room_index,
            "tracker_stats": self.tracker.get_stats(),
            "enemies": [
                {
                    "id": e.id,
                    "type": e.obj_type,
                    "variant": e.variant,
                    "subtype": e.subtype,
                    "hp": e.hp,
                    "max_hp": e.max_hp,
                    "is_boss": e.is_boss,
                    "is_champion": e.is_champion,
                    "state": e.state.value,
                    "first_seen_frame": e.first_seen_frame,
                    "last_seen_frame": e.last_seen_frame,
                    "lifetime_frames": e.get_lifetime_frames(),
                    "movement_pattern": e.movement_pattern,
                    "position_history": [
                        {"x": p.x, "y": p.y} for p in e.position_history
                    ],
                    "velocity_history": [
                        {"x": v.x, "y": v.y} for v in e.velocity_history
                    ]
                }
                for e in self.tracker.enemies.values()
            ]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n跟踪数据已导出到: {filename}")


def main():
    """主函数"""
    print("对象跟踪系统测试工具")
    print("="*60)
    
    # 创建桥接
    bridge = IsaacBridge()
    
    # 创建测试器
    tester = TrackerTester(bridge)
    
    # 启动桥接
    bridge.start()
    
    print("\n测试工具已启动，等待游戏数据...")
    print("按 Ctrl+C 退出")
    print("每 60 帧输出一次状态")
    print("="*60)
    
    try:
        last_output_frame = 0
        
        while True:
            frame = bridge.state.frame
            
            # 每60帧输出一次状态
            if frame - last_output_frame >= 60:
                tester.print_status()
                last_output_frame = frame
            
            # 控制更新频率
            time.sleep(0.016)  # ~60 FPS
    
    except KeyboardInterrupt:
        # 退出刷新模式
        print("\n\n正在退出...")
        
        # 打印敌人生命周期
        tester.print_enemy_lifecycles()
        
        # 导出数据
        tester.export_tracking_data()
        
        print("\n测试工具已停止")
        bridge.stop()


if __name__ == "__main__":
    main()
