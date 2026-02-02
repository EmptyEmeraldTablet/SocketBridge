"""
游戏抽象空间模型

将连续的游戏空间转换为离散化的抽象模型
为AI决策提供结构化的空间感知

核心功能:
1. 空间网格化 - 将连续空间划分为网格
2. 威胁场分析 - 计算空间中每个位置的威胁程度
3. 安全区域识别 - 识别相对安全的区域
4. 路径规划 - 基于威胁场的路径规划
5. 空间特征提取 - 提取空间的关键特征
"""

import math
import logging
from typing import Dict, List, Tuple, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from game_tracker import Position, Velocity, Enemy, Projectile, ObjectTracker

logger = logging.getLogger("GameSpace")


class CellType(Enum):
    """网格单元类型"""
    EMPTY = "empty"           # 空地
    OBSTACLE = "obstacle"     # 障碍物
    DOOR = "door"             # 门
    HAZARD = "hazard"         # 危险区域（尖刺等）
    SAFE = "safe"             # 安全区域


@dataclass
class GridCell:
    """网格单元"""
    x: int                    # 网格X坐标
    y: int                    # 网格Y坐标
    cell_type: CellType = CellType.EMPTY
    
    # 威胁信息
    threat_level: float = 0.0  # 威胁等级 [0, 1]
    threat_sources: List[int] = field(default_factory=list)  # 威胁源对象ID列表
    
    # 距离信息
    distance_to_player: float = float('inf')
    distance_to_nearest_enemy: float = float('inf')
    
    # 路径规划
    path_cost: float = float('inf')
    parent: Optional[Tuple[int, int]] = None
    
    def is_walkable(self) -> bool:
        """是否可通行"""
        return self.cell_type in [CellType.EMPTY, CellType.DOOR, CellType.SAFE]
    
    def is_safe(self, threshold: float = 0.3) -> bool:
        """是否安全（威胁等级低于阈值）"""
        return self.threat_level < threshold


@dataclass
class ThreatSource:
    """威胁源"""
    obj_id: int
    position: Position
    velocity: Velocity
    threat_type: str  # "enemy", "projectile", "laser"
    threat_radius: float
    threat_intensity: float  # 威胁强度 [0, 1]
    
    def get_threat_at(self, pos: Position) -> float:
        """计算对指定位置的威胁值"""
        distance = self.position.distance_to(pos)
        if distance > self.threat_radius:
            return 0.0
        
        # 威胁随距离衰减
        decay = 1.0 - (distance / self.threat_radius)
        return self.threat_intensity * decay


class GameSpace:
    """游戏抽象空间模型"""
    
    def __init__(self, grid_size: float = 40.0):
        """
        初始化空间模型
        
        Args:
            grid_size: 网格单元大小（像素）
        """
        self.grid_size = grid_size
        
        # 空间边界
        self.bounds = {
            "min_x": 0, "max_x": 0,
            "min_y": 0, "max_y": 0
        }
        
        # 网格
        self.grid: Dict[Tuple[int, int], GridCell] = {}
        self.grid_width = 0
        self.grid_height = 0
        
        # 威胁源
        self.threat_sources: List[ThreatSource] = []
        
        # 玩家位置
        self.player_position: Optional[Position] = None
    
    def initialize_from_room(self, room_info: dict, room_layout: dict):
        """
        从房间数据初始化空间
        
        Args:
            room_info: 房间信息
            room_layout: 房间布局
        """
        # 设置边界
        top_left = room_info.get("top_left", {"x": 0, "y": 0})
        bottom_right = room_info.get("bottom_right", {"x": 0, "y": 0})
        
        self.bounds = {
            "min_x": top_left.get("x", 0),
            "max_x": bottom_right.get("x", 0),
            "min_y": top_left.get("y", 0),
            "max_y": bottom_right.get("y", 0)
        }
        
        # 计算网格尺寸
        self.grid_width = int((self.bounds["max_x"] - self.bounds["min_x"]) / self.grid_size) + 1
        self.grid_height = int((self.bounds["max_y"] - self.bounds["min_y"]) / self.grid_size) + 1
        
        # 创建网格
        self.grid = {}
        for gx in range(self.grid_width):
            for gy in range(self.grid_height):
                self.grid[(gx, gy)] = GridCell(x=gx, y=gy)
        
        # 处理房间布局（障碍物）
        grid_data = room_layout.get("grid", {})
        if isinstance(grid_data, list):
            # 如果是列表，遍历列表
            for grid_cell in grid_data:
                collision = grid_cell.get("collision", 0)
                if collision > 0:
                    # 转换为网格坐标
                    cell_x = grid_cell.get("x", 0)
                    cell_y = grid_cell.get("y", 0)
                    gx = int((cell_x - self.bounds["min_x"]) / self.grid_size)
                    gy = int((cell_y - self.bounds["min_y"]) / self.grid_size)
                    
                    if (gx, gy) in self.grid:
                        self.grid[(gx, gy)].cell_type = CellType.OBSTACLE
        elif isinstance(grid_data, dict):
            # 如果是字典，按原逻辑处理
            for grid_idx, grid_cell in grid_data.items():
                collision = grid_cell.get("collision", 0)
                if collision > 0:
                    cell_x = grid_cell.get("x", 0)
                    cell_y = grid_cell.get("y", 0)
                    gx = int((cell_x - self.bounds["min_x"]) / self.grid_size)
                    gy = int((cell_y - self.bounds["min_y"]) / self.grid_size)
                    
                    if (gx, gy) in self.grid:
                        self.grid[(gx, gy)].cell_type = CellType.OBSTACLE
            collision = grid_cell.get("collision", 0)
            if collision > 0:
                # 转换为网格坐标
                cell_x = grid_cell.get("x", 0)
                cell_y = grid_cell.get("y", 0)
                gx = int((cell_x - self.bounds["min_x"]) / self.grid_size)
                gy = int((cell_y - self.bounds["min_y"]) / self.grid_size)
                
                if (gx, gy) in self.grid:
                    self.grid[(gx, gy)].cell_type = CellType.OBSTACLE
        
        # 处理门
        doors = room_layout.get("doors", {})
        for door_idx, door in doors.items():
            # 简化处理：将门标记为可通行
            # 实际需要根据门的位置计算网格坐标
            pass
        
        logger.info(f"Game space initialized: {self.grid_width}x{self.grid_height} grid")
    
    def update(self, player_pos: Position, tracker: ObjectTracker):
        """
        更新空间状态
        
        Args:
            player_pos: 玩家位置
            tracker: 对象跟踪器
        """
        self.player_position = player_pos
        
        # 更新威胁源
        self._update_threat_sources(tracker)
        
        # 计算威胁场
        self._compute_threat_field()
        
        # 计算距离信息
        self._compute_distances()
    
    def _update_threat_sources(self, tracker: ObjectTracker):
        """更新威胁源"""
        self.threat_sources.clear()
        
        # 添加敌人威胁
        for enemy in tracker.get_active_enemies():
            # 威胁半径基于敌人类型和状态
            threat_radius = 200.0
            if enemy.is_boss:
                threat_radius = 400.0
            elif enemy.is_champion:
                threat_radius = 250.0
            
            # 威胁强度基于敌人血量和距离
            threat_intensity = 0.5
            if enemy.is_boss:
                threat_intensity = 0.8
            elif enemy.is_champion:
                threat_intensity = 0.6
            
            self.threat_sources.append(ThreatSource(
                obj_id=enemy.id,
                position=enemy.pos,
                velocity=enemy.vel,
                threat_type="enemy",
                threat_radius=threat_radius,
                threat_intensity=threat_intensity
            ))
        
        # 添加投射物威胁
        for proj in tracker.get_enemy_projectiles():
            # 投射物威胁半径较小
            threat_radius = 100.0
            
            # 威胁强度基于投射物速度
            threat_intensity = min(0.9, proj.vel.magnitude / 10.0)
            
            self.threat_sources.append(ThreatSource(
                obj_id=proj.id,
                position=proj.pos,
                velocity=proj.vel,
                threat_type="projectile",
                threat_radius=threat_radius,
                threat_intensity=threat_intensity
            ))
    
    def _compute_threat_field(self):
        """计算威胁场"""
        # 清空威胁信息
        for cell in self.grid.values():
            cell.threat_level = 0.0
            cell.threat_sources.clear()
        
        # 计算每个网格单元的威胁
        for (gx, gy), cell in self.grid.items():
            if not cell.is_walkable():
                continue
            
            # 计算网格单元中心的世界坐标
            world_pos = self._grid_to_world(gx, gy)
            
            # 累加所有威胁源的威胁
            total_threat = 0.0
            threat_sources = []
            
            for threat in self.threat_sources:
                threat_value = threat.get_threat_at(world_pos)
                if threat_value > 0:
                    total_threat += threat_value
                    threat_sources.append(threat.obj_id)
            
            # 限制威胁等级在 [0, 1]
            cell.threat_level = min(1.0, total_threat)
            cell.threat_sources = threat_sources
    
    def _compute_distances(self):
        """计算距离信息"""
        if self.player_position is None:
            return
        
        # 计算到玩家的距离
        for cell in self.grid.values():
            world_pos = self._grid_to_world(cell.x, cell.y)
            cell.distance_to_player = world_pos.distance_to(self.player_position)
        
        # 计算到最近敌人的距离
        for cell in self.grid.values():
            world_pos = self._grid_to_world(cell.x, cell.y)
            min_dist = float('inf')
            
            for threat in self.threat_sources:
                if threat.threat_type == "enemy":
                    dist = world_pos.distance_to(threat.position)
                    if dist < min_dist:
                        min_dist = dist
            
            cell.distance_to_nearest_enemy = min_dist
    
    def _world_to_grid(self, world_pos: Position) -> Tuple[int, int]:
        """世界坐标转网格坐标"""
        gx = int((world_pos.x - self.bounds["min_x"]) / self.grid_size)
        gy = int((world_pos.y - self.bounds["min_y"]) / self.grid_size)
        return (gx, gy)
    
    def _grid_to_world(self, gx: int, gy: int) -> Position:
        """网格坐标转世界坐标"""
        x = self.bounds["min_x"] + gx * self.grid_size + self.grid_size / 2
        y = self.bounds["min_y"] + gy * self.grid_size + self.grid_size / 2
        return Position(x, y)
    
    def get_cell(self, world_pos: Position) -> Optional[GridCell]:
        """获取指定世界坐标的网格单元"""
        gx, gy = self._world_to_grid(world_pos)
        return self.grid.get((gx, gy))
    
    def get_safe_cells(self, threshold: float = 0.3) -> List[GridCell]:
        """获取所有安全的网格单元"""
        return [cell for cell in self.grid.values() 
                if cell.is_walkable() and cell.is_safe(threshold)]
    
    def get_safest_cell_nearby(self, world_pos: Position, max_distance: float = 200.0) -> Optional[GridCell]:
        """获取附近最安全的网格单元"""
        center_gx, center_gy = self._world_to_grid(world_pos)
        max_cells = int(max_distance / self.grid_size)
        
        safest_cell = None
        min_threat = float('inf')
        
        # 搜索附近的网格
        for dx in range(-max_cells, max_cells + 1):
            for dy in range(-max_cells, max_cells + 1):
                gx, gy = center_gx + dx, center_gy + dy
                cell = self.grid.get((gx, gy))
                
                if cell and cell.is_walkable():
                    # 计算实际距离
                    cell_world_pos = self._grid_to_world(gx, gy)
                    distance = cell_world_pos.distance_to(world_pos)
                    
                    if distance <= max_distance and cell.threat_level < min_threat:
                        min_threat = cell.threat_level
                        safest_cell = cell
        
        return safest_cell
    
    def find_path(self, start: Position, goal: Position, 
                  max_threat: float = 0.5) -> Optional[List[Position]]:
        """
        使用A*算法寻找路径
        
        Args:
            start: 起始位置
            goal: 目标位置
            max_threat: 最大允许威胁等级
            
        Returns:
            路径位置列表，如果无法到达则返回None
        """
        # 转换为网格坐标
        start_gx, start_gy = self._world_to_grid(start)
        goal_gx, goal_gy = self._world_to_grid(goal)
        
        # 检查起点和终点是否有效
        if (start_gx, start_gy) not in self.grid or (goal_gx, goal_gy) not in self.grid:
            return None
        
        # 重置路径规划信息
        for cell in self.grid.values():
            cell.path_cost = float('inf')
            cell.parent = None
        
        # A*算法
        open_set = [(start_gx, start_gy)]
        self.grid[(start_gx, start_gy)].path_cost = 0
        
        while open_set:
            # 获取路径成本最低的节点
            current = min(open_set, key=lambda pos: self.grid[pos].path_cost)
            open_set.remove(current)
            
            # 到达目标
            if current == (goal_gx, goal_gy):
                return self._reconstruct_path(current)
            
            # 扩展邻居
            for neighbor in self._get_neighbors(current):
                cell = self.grid[neighbor]
                
                # 检查是否可通行且威胁等级可接受
                if not cell.is_walkable() or cell.threat_level > max_threat:
                    continue
                
                # 计算新的路径成本
                current_cost = self.grid[current].path_cost
                move_cost = 1.0 + cell.threat_level * 2.0  # 威胁增加移动成本
                new_cost = current_cost + move_cost
                
                # 如果找到更优路径
                if new_cost < cell.path_cost:
                    cell.path_cost = new_cost
                    cell.parent = current
                    
                    if neighbor not in open_set:
                        open_set.append(neighbor)
        
        return None
    
    def _get_neighbors(self, pos: Tuple[int, int]) -> List[Tuple[int, int]]:
        """获取邻居节点（8方向）"""
        x, y = pos
        neighbors = []
        
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                
                nx, ny = x + dx, y + dy
                if (nx, ny) in self.grid:
                    neighbors.append((nx, ny))
        
        return neighbors
    
    def _reconstruct_path(self, end_pos: Tuple[int, int]) -> List[Position]:
        """重建路径"""
        path = []
        current = end_pos
        
        while current is not None:
            world_pos = self._grid_to_world(current[0], current[1])
            path.append(world_pos)
            current = self.grid[current].parent
        
        path.reverse()
        return path
    
    def get_threat_at(self, pos: Position) -> float:
        """获取指定位置的威胁等级"""
        cell = self.get_cell(pos)
        return cell.threat_level if cell else 1.0
    
    def get_space_features(self) -> Dict[str, Any]:
        """获取空间特征"""
        if not self.grid:
            return {}
        
        # 统计威胁分布
        threat_levels = [cell.threat_level for cell in self.grid.values() if cell.is_walkable()]
        
        if not threat_levels:
            return {}
        
        return {
            "avg_threat": sum(threat_levels) / len(threat_levels),
            "max_threat": max(threat_levels),
            "safe_cell_ratio": len([t for t in threat_levels if t < 0.3]) / len(threat_levels),
            "threat_sources_count": len(self.threat_sources),
            "grid_size": (self.grid_width, self.grid_height)
        }


class ThreatAnalyzer:
    """威胁分析器"""
    
    def __init__(self, space: GameSpace, tracker: ObjectTracker):
        """
        初始化威胁分析器
        
        Args:
            space: 游戏空间模型
            tracker: 对象跟踪器
        """
        self.space = space
        self.tracker = tracker
    
    def analyze_player_threat(self, player_pos: Position) -> Dict[str, Any]:
        """
        分析玩家面临的威胁
        
        Returns:
            威胁分析结果
        """
        # 获取最近的敌人
        nearest_enemy = self.tracker.get_nearest_enemy(player_pos)
        enemy_dist = nearest_enemy.pos.distance_to(player_pos) if nearest_enemy else float('inf')
        
        # 获取危险的投射物
        dangerous_projs = self.tracker.get_dangerous_projectiles(player_pos)
        nearest_proj = min(dangerous_projs, key=lambda p: p.pos.distance_to(player_pos)) if dangerous_projs else None
        proj_dist = nearest_proj.pos.distance_to(player_pos) if nearest_proj else float('inf')
        
        # 获取当前位置的威胁等级
        current_threat = self.space.get_threat_at(player_pos)
        
        # 获取附近最安全的位置
        safest_cell = self.space.get_safest_cell_nearby(player_pos, max_distance=200.0)
        safest_pos = self.space._grid_to_world(safest_cell.x, safest_cell.y) if safest_cell else None
        safest_threat = safest_cell.threat_level if safest_cell else current_threat
        
        # 计算威胁向量（指向威胁源）
        threat_vector = self._compute_threat_vector(player_pos)
        
        return {
            "current_threat": current_threat,
            "nearest_enemy_distance": enemy_dist,
            "nearest_projectile_distance": proj_dist,
            "dangerous_projectiles_count": len(dangerous_projs),
            "safest_position": safest_pos.to_tuple() if safest_pos else None,
            "safest_threat": safest_threat,
            "threat_vector": threat_vector,
            "threat_level": self._classify_threat_level(current_threat, enemy_dist, proj_dist)
        }
    
    def _compute_threat_vector(self, player_pos: Position) -> Tuple[float, float]:
        """
        计算威胁向量（指向威胁源）
        
        Returns:
            (x, y) 归一化的威胁向量
        """
        threat_x, threat_y = 0.0, 0.0
        
        # 来自敌人的威胁
        for enemy in self.tracker.get_active_enemies():
            dx = enemy.pos.x - player_pos.x
            dy = enemy.pos.y - player_pos.y
            dist = math.sqrt(dx*dx + dy*dy)
            
            if dist > 0 and dist < 300:
                weight = (300 - dist) / 300
                if enemy.is_boss:
                    weight *= 1.5
                threat_x += dx / dist * weight
                threat_y += dy / dist * weight
        
        # 来自投射物的威胁
        for proj in self.tracker.get_enemy_projectiles():
            dx = proj.pos.x - player_pos.x
            dy = proj.pos.y - player_pos.y
            dist = math.sqrt(dx*dx + dy*dy)
            
            if dist > 0 and dist < 200:
                weight = (200 - dist) / 200 * 1.5  # 投射物威胁权重更高
                threat_x += dx / dist * weight
                threat_y += dy / dist * weight
        
        # 归一化
        magnitude = math.sqrt(threat_x**2 + threat_y**2)
        if magnitude > 0:
            threat_x /= magnitude
            threat_y /= magnitude
        
        return (threat_x, threat_y)
    
    def _classify_threat_level(self, current_threat: float, 
                               enemy_dist: float, proj_dist: float) -> str:
        """分类威胁等级"""
        if current_threat > 0.7 or proj_dist < 50:
            return "critical"
        elif current_threat > 0.4 or enemy_dist < 100:
            return "high"
        elif current_threat > 0.2 or enemy_dist < 200:
            return "medium"
        else:
            return "low"
    
    def get_recommended_action(self, player_pos: Position) -> Dict[str, Any]:
        """
        获取推荐行动
        
        Returns:
            推荐行动信息
        """
        threat_analysis = self.analyze_player_threat(player_pos)
        threat_level = threat_analysis["threat_level"]
        threat_vector = threat_analysis["threat_vector"]
        
        # 根据威胁等级推荐行动
        if threat_level == "critical":
            # 紧急躲避
            move_dir = (-threat_vector[0], -threat_vector[1])
            action = "evade"
        elif threat_level == "high":
            # 谨慎移动
            move_dir = (-threat_vector[0], -threat_vector[1])
            action = "cautious_move"
        elif threat_level == "medium":
            # 战术移动
            safest_pos = threat_analysis["safest_position"]
            if safest_pos:
                dx = safest_pos[0] - player_pos.x
                dy = safest_pos[1] - player_pos.y
                dist = math.sqrt(dx*dx + dy*dy)
                if dist > 0:
                    move_dir = (dx/dist, dy/dist)
                else:
                    move_dir = (0, 0)
            else:
                move_dir = (0, 0)
            action = "tactical_move"
        else:
            # 自由移动
            move_dir = (0, 0)
            action = "free_move"
        
        # 推荐射击方向（朝向最近的敌人）
        nearest_enemy = self.tracker.get_nearest_enemy(player_pos)
        if nearest_enemy:
            dx = nearest_enemy.pos.x - player_pos.x
            dy = nearest_enemy.pos.y - player_pos.y
            dist = math.sqrt(dx*dx + dy*dy)
            if dist > 0:
                shoot_dir = (dx/dist, dy/dist)
            else:
                shoot_dir = (0, 0)
        else:
            shoot_dir = (0, 0)
        
        return {
            "action": action,
            "move_dir": move_dir,
            "shoot_dir": shoot_dir,
            "threat_level": threat_level,
            "confidence": self._compute_confidence(threat_analysis)
        }
    
    def _compute_confidence(self, threat_analysis: Dict[str, Any]) -> float:
        """计算推荐行动的置信度"""
        threat_level = threat_analysis["threat_level"]
        
        if threat_level == "critical":
            return 0.9
        elif threat_level == "high":
            return 0.8
        elif threat_level == "medium":
            return 0.6
        else:
            return 0.4
