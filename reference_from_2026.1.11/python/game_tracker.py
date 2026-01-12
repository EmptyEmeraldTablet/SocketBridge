"""
游戏对象跟踪系统

将实时流式数据转换为稳定的、可追踪的抽象模型
为AI智能体提供可靠的游戏状态感知能力

核心功能:
1. 对象跟踪 - 识别并跟踪游戏中的实体（敌人、投射物等）
2. 生命周期管理 - 管理对象从出现到消失的完整生命周期
3. 历史轨迹 - 记录对象的位置和行为历史

注意:
- 使用 entity.Index 作为唯一标识符（每个房间内唯一）
- 支持同类型多敌人的独立跟踪
- 支持非线性运动敌人的位置记录（传送/钻地等）
"""

import math
import time
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import logging

logger = logging.getLogger("GameTracker")


class ObjectType(Enum):
    """对象类型"""
    ENEMY = "enemy"
    PLAYER = "player"
    PROJECTILE = "projectile"
    LASER = "laser"
    OBSTACLE = "obstacle"


class ObjectState(Enum):
    """对象状态"""
    SPAWNING = "spawning"      # 刚出现
    ACTIVE = "active"          # 活跃中
    DYING = "dying"            # 死亡中
    DEAD = "dead"              # 已死亡
    ESCAPED = "escaped"        # 离开房间


@dataclass
class Position:
    """位置信息"""
    x: float
    y: float
    
    def distance_to(self, other: 'Position') -> float:
        """计算到另一个位置的距离"""
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
    
    def direction_to(self, other: 'Position') -> Tuple[float, float]:
        """计算到另一个位置的方向向量（归一化）"""
        dx = other.x - self.x
        dy = other.y - self.y
        dist = math.sqrt(dx*dx + dy*dy)
        if dist == 0:
            return (0.0, 0.0)
        return (dx/dist, dy/dist)
    
    def to_tuple(self) -> Tuple[float, float]:
        """转换为元组"""
        return (self.x, self.y)


@dataclass
class Velocity:
    """速度信息"""
    x: float
    y: float
    
    @property
    def magnitude(self) -> float:
        """速度大小"""
        return math.sqrt(self.x**2 + self.y**2)
    
    @property
    def direction(self) -> Tuple[float, float]:
        """速度方向（归一化）"""
        mag = self.magnitude
        if mag == 0:
            return (0.0, 0.0)
        return (self.x/mag, self.y/mag)


@dataclass
class TrackedObject:
    """被跟踪的游戏对象"""
    id: int                              # 对象ID
    type: ObjectType                     # 对象类型
    pos: Position                        # 当前位置
    vel: Velocity                        # 当前速度
    state: ObjectState = ObjectState.ACTIVE
    
    # 对象属性
    obj_type: int = 0                    # 游戏内类型
    variant: int = 0                     # 变体
    subtype: int = 0                     # 子类型
    hp: float = 0.0                      # 当前生命值
    max_hp: float = 0.0                  # 最大生命值
    is_boss: bool = False                # 是否为Boss
    is_champion: bool = False            # 是否为精英
    
    # 跟踪信息
    first_seen_frame: int = 0            # 首次出现的帧
    last_seen_frame: int = 0             # 最后出现的帧
    frames_not_seen: int = 0            # 连续未看到的帧数
    
    # 历史轨迹（最多保存最近N帧）
    position_history: deque = field(default_factory=lambda: deque(maxlen=60))
    velocity_history: deque = field(default_factory=lambda: deque(maxlen=60))
    
    # 行为分析
    avg_velocity: Velocity = field(default_factory=lambda: Velocity(0, 0))
    movement_pattern: str = "unknown"    # 移动模式: stationary, chasing, fleeing, erratic
    
    # 自定义数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update(self, pos: Position, vel: Velocity, frame: int, **kwargs):
        """更新对象状态"""
        # 保存历史
        self.position_history.append(pos)
        self.velocity_history.append(vel)
        
        # 更新当前位置和速度
        self.pos = pos
        self.vel = vel
        
        # 更新帧信息
        self.last_seen_frame = frame
        self.frames_not_seen = 0
        
        # 更新属性
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                self.metadata[key] = value
        
        # 更新平均速度
        if len(self.velocity_history) > 0:
            avg_vx = sum(v.x for v in self.velocity_history) / len(self.velocity_history)
            avg_vy = sum(v.y for v in self.velocity_history) / len(self.velocity_history)
            self.avg_velocity = Velocity(avg_vx, avg_vy)
        
        # 分析移动模式
        self._analyze_movement_pattern()
    
    def mark_missing(self, frame: int):
        """标记对象在当前帧未出现"""
        self.frames_not_seen += 1
        self.last_seen_frame = frame
    
    def predict_position(self, frames_ahead: int = 1) -> Position:
        """预测未来位置（基于当前速度）"""
        return Position(
            x=self.pos.x + self.vel.x * frames_ahead,
            y=self.pos.y + self.vel.y * frames_ahead
        )
    
    def _analyze_movement_pattern(self):
        """分析移动模式"""
        if len(self.velocity_history) < 10:
            self.movement_pattern = "unknown"
            return
        
        # 计算速度变化
        velocities = list(self.velocity_history)
        speed_variance = sum(v.magnitude for v in velocities) / len(velocities)
        
        if speed_variance < 0.5:
            self.movement_pattern = "stationary"
        elif speed_variance > 3.0:
            self.movement_pattern = "erratic"
        else:
            self.movement_pattern = "chasing"
    
    def get_lifetime_frames(self) -> int:
        """获取对象存活的总帧数"""
        return self.last_seen_frame - self.first_seen_frame + 1
    
    def is_alive(self) -> bool:
        """对象是否仍然存活"""
        return self.state in [ObjectState.SPAWNING, ObjectState.ACTIVE]


@dataclass
class Projectile(TrackedObject):
    """投射物对象"""
    variant: int = 0
    collision_radius: float = 0.0
    height: float = 0.0
    is_enemy: bool = False
    
    def predict_impact_time(self, target_pos: Position) -> Optional[int]:
        """预测击中目标所需的帧数"""
        if self.vel.magnitude == 0:
            return None
        
        # 简单的线性预测
        direction = self.vel.direction
        to_target = target_pos.direction_to(self.pos)
        
        # 检查是否朝向目标
        dot = direction[0] * to_target[0] + direction[1] * to_target[1]
        if dot < 0.9:  # 不朝向目标
            return None
        
        distance = self.pos.distance_to(target_pos)
        speed = self.vel.magnitude
        return int(distance / speed) if speed > 0 else None


@dataclass
class Enemy(TrackedObject):
    """敌人对象"""
    state: int = 0                      # 游戏内状态
    state_frame: int = 0                 # 当前状态持续帧数
    projectile_cooldown: int = 0        # 投射物冷却
    projectile_delay: int = 60          # 投射物发射间隔
    collision_radius: float = 15.0
    
    # 行为分析
    last_attack_frame: int = 0          # 最后攻击帧
    attack_pattern: List[int] = field(default_factory=list)  # 攻击间隔历史
    
    def can_attack(self, current_frame: int) -> bool:
        """是否可以攻击"""
        return current_frame - self.last_attack_frame >= self.projectile_delay
    
    def record_attack(self, frame: int):
        """记录攻击"""
        self.last_attack_frame = frame
        self.attack_pattern.append(frame - self.last_attack_frame)
        if len(self.attack_pattern) > 10:
            self.attack_pattern.pop(0)
    
    def get_avg_attack_interval(self) -> float:
        """获取平均攻击间隔"""
        if not self.attack_pattern:
            return self.projectile_delay
        return sum(self.attack_pattern) / len(self.attack_pattern)
    
    def is_alive(self) -> bool:
        """敌人是否存活（基于HP判断）"""
        return self.hp > 0


class ObjectTracker:
    """对象跟踪器核心类"""
    
    def __init__(self, max_missing_frames: int = 30):
        """
        初始化跟踪器
        
        Args:
            max_missing_frames: 对象连续未出现的最大帧数，超过则认为对象消失
        """
        self.max_missing_frames = max_missing_frames
        
        # 跟踪的对象
        self.enemies: Dict[int, Enemy] = {}
        self.projectiles: Dict[int, Projectile] = {}
        self.lasers: Dict[int, TrackedObject] = {}
        
        # 当前帧
        self.current_frame = 0
        
        # 统计信息
        self.stats = {
            "total_enemies_seen": 0,
            "total_projectiles_seen": 0,
            "enemies_killed": 0,
        }
    
    def update(self, frame: int, enemies_data: List[dict], projectiles_data: dict):
        """
        更新跟踪器状态
        
        Args:
            frame: 当前帧号
            enemies_data: 敌人数据列表
            projectiles_data: 投射物数据字典
        """
        self.current_frame = frame
        
        # 更新敌人
        self._update_enemies(enemies_data, frame)
        
        # 更新投射物
        self._update_projectiles(projectiles_data, frame)
        
        # 清理消失的对象
        self._cleanup_missing_objects()
    
    def _update_enemies(self, enemies_data: List[dict], frame: int):
        """更新敌人跟踪"""
        # 标记所有敌人为"未看到"
        for enemy in self.enemies.values():
            enemy.mark_missing(frame)
        
        # 处理当前帧的敌人数据
        for enemy_dict in enemies_data:
            enemy_id = enemy_dict.get("id")
            if enemy_id is None:
                continue
            
            # 创建或更新敌人
            if enemy_id not in self.enemies:
                # 新敌人
                self.enemies[enemy_id] = Enemy(
                    id=enemy_id,
                    type=ObjectType.ENEMY,
                    pos=Position(0, 0),
                    vel=Velocity(0, 0),
                    first_seen_frame=frame,
                    last_seen_frame=frame
                )
                self.stats["total_enemies_seen"] += 1
                logger.debug(f"New enemy spawned: ID={enemy_id}")
            
            # 更新敌人状态
            enemy = self.enemies[enemy_id]
            pos = Position(
                enemy_dict.get("pos", {}).get("x", 0),
                enemy_dict.get("pos", {}).get("y", 0)
            )
            vel = Velocity(
                enemy_dict.get("vel", {}).get("x", 0),
                enemy_dict.get("vel", {}).get("y", 0)
            )
            
            enemy.update(
                pos=pos,
                vel=vel,
                frame=frame,
                obj_type=enemy_dict.get("type", 0),
                variant=enemy_dict.get("variant", 0),
                subtype=enemy_dict.get("subtype", 0),
                hp=enemy_dict.get("hp", 0),
                max_hp=enemy_dict.get("max_hp", 0),
                is_boss=enemy_dict.get("is_boss", False),
                is_champion=enemy_dict.get("is_champion", False),
                state=enemy_dict.get("state", 0),
                state_frame=enemy_dict.get("state_frame", 0),
                projectile_cooldown=enemy_dict.get("projectile_cooldown", 0),
                projectile_delay=enemy_dict.get("projectile_delay", 60),
                collision_radius=enemy_dict.get("collision_radius", 15.0)
            )
            
            # 检测敌人死亡
            if enemy.hp <= 0 and enemy.state != ObjectState.DEAD:
                enemy.state = ObjectState.DEAD
                self.stats["enemies_killed"] += 1
                logger.debug(f"Enemy killed: ID={enemy_id}")
    
    def _update_projectiles(self, projectiles_data: dict, frame: int):
        """更新投射物跟踪"""
        # 标记所有投射物为"未看到"
        for proj in self.projectiles.values():
            proj.mark_missing(frame)
        
        # 处理敌人投射物
        enemy_projs = projectiles_data.get("enemy_projectiles", [])
        for proj_dict in enemy_projs:
            proj_id = proj_dict.get("id")
            if proj_id is None:
                continue
            
            if proj_id not in self.projectiles:
                self.projectiles[proj_id] = Projectile(
                    id=proj_id,
                    type=ObjectType.PROJECTILE,
                    pos=Position(0, 0),
                    vel=Velocity(0, 0),
                    first_seen_frame=frame,
                    last_seen_frame=frame,
                    is_enemy=True
                )
                self.stats["total_projectiles_seen"] += 1
            
            proj = self.projectiles[proj_id]
            pos = Position(
                proj_dict.get("pos", {}).get("x", 0),
                proj_dict.get("pos", {}).get("y", 0)
            )
            vel = Velocity(
                proj_dict.get("vel", {}).get("x", 0),
                proj_dict.get("vel", {}).get("y", 0)
            )
            
            proj.update(
                pos=pos,
                vel=vel,
                frame=frame,
                variant=proj_dict.get("variant", 0),
                collision_radius=proj_dict.get("collision_radius", 8.0),
                height=proj_dict.get("height", 0.0)
            )
        
        # 处理玩家眼泪（如果需要）
        player_tears = projectiles_data.get("player_tears", [])
        for tear_dict in player_tears:
            tear_id = tear_dict.get("id")
            if tear_id is None:
                continue
            
            if tear_id not in self.projectiles:
                self.projectiles[tear_id] = Projectile(
                    id=tear_id,
                    type=ObjectType.PROJECTILE,
                    pos=Position(0, 0),
                    vel=Velocity(0, 0),
                    first_seen_frame=frame,
                    last_seen_frame=frame,
                    is_enemy=False
                )
            
            proj = self.projectiles[tear_id]
            pos = Position(
                tear_dict.get("pos", {}).get("x", 0),
                tear_dict.get("pos", {}).get("y", 0)
            )
            vel = Velocity(
                tear_dict.get("vel", {}).get("x", 0),
                tear_dict.get("vel", {}).get("y", 0)
            )
            
            proj.update(
                pos=pos,
                vel=vel,
                frame=frame,
                variant=tear_dict.get("variant", 0),
                collision_radius=tear_dict.get("collision_radius", 6.0),
                height=tear_dict.get("height", 0.0),
                scale=tear_dict.get("scale", 1.0)
            )
    
    def _cleanup_missing_objects(self):
        """清理消失的对象"""
        # 清理敌人
        dead_enemies = []
        for enemy_id, enemy in self.enemies.items():
            if enemy.frames_not_seen > self.max_missing_frames:
                if enemy.state != ObjectState.DEAD:
                    enemy.state = ObjectState.ESCAPED
                    logger.debug(f"Enemy escaped: ID={enemy_id}")
                dead_enemies.append(enemy_id)
        
        for enemy_id in dead_enemies:
            del self.enemies[enemy_id]
        
        # 清理投射物
        dead_projectiles = []
        for proj_id, proj in self.projectiles.items():
            if proj.frames_not_seen > self.max_missing_frames:
                proj.state = ObjectState.DEAD
                dead_projectiles.append(proj_id)
        
        for proj_id in dead_projectiles:
            del self.projectiles[proj_id]
    
    def get_active_enemies(self) -> List[Enemy]:
        """获取所有活跃的敌人"""
        return [e for e in self.enemies.values() if e.is_alive()]
    
    def get_enemy_by_id(self, enemy_id: int) -> Optional[Enemy]:
        """根据ID获取敌人"""
        return self.enemies.get(enemy_id)
    
    def get_nearest_enemy(self, pos: Position) -> Optional[Enemy]:
        """获取最近的敌人"""
        active_enemies = self.get_active_enemies()
        if not active_enemies:
            return None
        
        return min(active_enemies, key=lambda e: e.pos.distance_to(pos))
    
    def get_enemy_projectiles(self) -> List[Projectile]:
        """获取所有敌人投射物"""
        return [p for p in self.projectiles.values() if p.is_enemy and p.is_alive()]
    
    def get_dangerous_projectiles(self, pos: Position, max_distance: float = 200.0) -> List[Projectile]:
        """获取对玩家有威胁的投射物"""
        dangerous = []
        for proj in self.get_enemy_projectiles():
            dist = proj.pos.distance_to(pos)
            if dist <= max_distance:
                # 检查是否朝向玩家
                direction = proj.vel.direction
                to_player = pos.direction_to(proj.pos)
                dot = direction[0] * to_player[0] + direction[1] * to_player[1]
                if dot > 0.7:  # 朝向玩家
                    dangerous.append(proj)
        return dangerous
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "active_enemies": len(self.get_active_enemies()),
            "active_projectiles": len([p for p in self.projectiles.values() if p.is_alive()]),
            "current_frame": self.current_frame
        }
