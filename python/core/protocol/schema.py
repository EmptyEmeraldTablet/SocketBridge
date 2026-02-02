"""
Core Protocol Schemas - Pydantic 数据模式定义

提供运行时数据验证和类型安全保证。
可选的验证模式可在性能关键路径跳过验证。
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator, field_validator, model_validator
from enum import Enum
from datetime import datetime


class CollectInterval(str, Enum):
    """采集频率枚举"""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    RARE = "RARE"
    ON_CHANGE = "ON_CHANGE"


class MessageType(str, Enum):
    """消息类型枚举"""

    DATA = "DATA"
    FULL = "FULL"
    FULL_STATE = "FULL"
    EVENT = "EVENT"
    COMMAND = "CMD"


class ChannelMeta(BaseModel):
    """通道采集元数据"""

    channel: str = Field(..., description="通道名称")
    collect_frame: int = Field(..., ge=0, description="数据采集帧号")
    collect_time: int = Field(..., ge=0, description="数据采集时间戳")
    interval: CollectInterval = Field(..., description="采集频率")
    stale_frames: int = Field(default=0, ge=0, description="数据过期帧数")


class Vector2DSchema(BaseModel):
    """二维向量模式"""

    x: float = Field(..., description="X 坐标")
    y: float = Field(..., description="Y 坐标")

    @field_validator("x", "y")
    @classmethod
    def validate_coords(cls, v: float) -> float:
        if not isinstance(v, (int, float)):
            raise ValueError(f"坐标必须是数字, 收到 {type(v)}")
        return float(v)


class PlayerPositionData(BaseModel):
    """玩家位置数据"""

    pos: Vector2DSchema = Field(..., description="位置")
    vel: Vector2DSchema = Field(..., description="速度")
    move_dir: int = Field(..., ge=-1, le=7, description="移动方向")
    fire_dir: int = Field(..., ge=-1, le=7, description="射击方向")
    head_dir: int = Field(..., ge=-1, description="头部朝向")
    aim_dir: Vector2DSchema = Field(..., description="瞄准方向")

    @field_validator("move_dir", "fire_dir", "head_dir")
    @classmethod
    def validate_direction(cls, v: int) -> int:
        if v is None:
            return 0
        return v


class PlayerStatsData(BaseModel):
    """玩家属性数据"""

    player_type: int = Field(..., ge=0, description="玩家类型")
    damage: float = Field(..., ge=0, description="伤害")
    speed: float = Field(..., ge=0, description="移动速度")
    tears: float = Field(default=10.0, ge=0, description="眼泪延迟")
    range: float = Field(default=300.0, ge=0, description="射程")
    tear_range: float = Field(default=300.0, ge=0, description="射程（别名）")
    shot_speed: float = Field(default=1.0, ge=0, description="射击速度")
    luck: int = Field(default=0, ge=0, le=10, description="幸运值")
    tear_height: float = Field(default=0.0, description="眼泪高度")
    tear_falling_speed: float = Field(default=0.0, description="眼泪下落速度")
    can_fly: bool = Field(default=False, description="能否飞行")
    size: float = Field(default=10.0, ge=0, description="大小")
    sprite_scale: float = Field(default=1.0, ge=0, description="精灵缩放")

    @field_validator("luck")
    @classmethod
    def validate_luck(cls, v: float) -> int:
        return int(v) if v is not None else 0


class PlayerHealthData(BaseModel):
    """玩家生命值数据"""

    red_hearts: int = Field(..., ge=0, description="红心")
    max_hearts: float = Field(..., ge=0, description="最大红心")
    soul_hearts: int = Field(default=0, ge=0, description="灵魂心")
    black_hearts: int = Field(default=0, ge=0, description="黑心")
    bone_hearts: int = Field(default=0, ge=0, description="骨心")
    golden_hearts: int = Field(default=0, ge=0, description="金心")
    eternal_hearts: int = Field(default=0, ge=0, description="永恒心")
    rotten_hearts: int = Field(default=0, ge=0, description="腐烂心")
    broken_hearts: int = Field(default=0, ge=0, description="破碎心")
    extra_lives: int = Field(default=0, ge=0, description="额外生命")

    @property
    def total_hearts(self) -> float:
        return (
            self.red_hearts
            + self.soul_hearts * 0.5
            + self.black_hearts * 0.5
            + self.bone_hearts * 0.5
            + self.golden_hearts
            + self.eternal_hearts * 0.5
        )


class ActiveItemData(BaseModel):
    """主动道具数据"""

    item: int = Field(..., ge=0, description="物品ID")
    charge: int = Field(default=0, ge=0, description="当前充能")
    max_charge: int = Field(default=0, ge=0, description="最大充能")
    battery_charge: int = Field(default=0, ge=0, description="电池充能")


class PlayerInventoryData(BaseModel):
    """玩家物品栏数据"""

    coins: int = Field(default=0, ge=0, description="金币")
    bombs: int = Field(default=0, ge=0, description="炸弹")
    keys: int = Field(default=0, ge=0, description="钥匙")
    trinket_0: int = Field(default=0, ge=0, description="饰品槽0")
    trinket_1: int = Field(default=0, ge=0, description="饰品槽1")
    card_0: int = Field(default=0, description="卡牌槽")
    pill_0: int = Field(default=0, description="药丸槽")
    collectible_count: int = Field(default=0, ge=0, description="收集品总数")
    collectibles: Dict[str, int] = Field(default_factory=dict, description="收集品字典")
    active_items: Dict[str, ActiveItemData] = Field(
        default_factory=dict, description="主动道具"
    )


class EnemyData(BaseModel):
    """敌人数据"""

    id: int = Field(..., ge=0, description="实体索引")
    type: int = Field(..., ge=0, description="实体类型")
    variant: int = Field(default=0, ge=0, description="变种")
    subtype: int = Field(default=0, ge=0, description="子类型")
    pos: Vector2DSchema = Field(..., description="位置")
    vel: Vector2DSchema = Field(..., description="速度")
    hp: float = Field(..., ge=0, description="生命值")
    max_hp: float = Field(..., ge=0, description="最大生命值")
    is_boss: bool = Field(default=False, description="是否Boss")
    is_champion: bool = Field(default=False, description="是否冠军")
    state: int = Field(default=0, ge=0, description="状态")
    state_frame: int = Field(default=0, ge=0, description="状态帧")
    projectile_cooldown: int = Field(default=0, ge=0, description="投射物冷却")
    projectile_delay: int = Field(default=0, ge=0, description="投射物延迟")
    collision_radius: float = Field(default=10.0, ge=0, description="碰撞半径")
    distance: float = Field(default=0.0, ge=0, description="距离玩家")
    target_pos: Vector2DSchema = Field(
        default_factory=lambda: Vector2DSchema(x=0, y=0), description="目标位置"
    )
    v1: Vector2DSchema = Field(
        default_factory=lambda: Vector2DSchema(x=0, y=0), description="向量1"
    )
    v2: Vector2DSchema = Field(
        default_factory=lambda: Vector2DSchema(x=0, y=0), description="向量2"
    )


class ProjectileData(BaseModel):
    """投射物数据"""

    id: int = Field(..., ge=0, description="实体索引")
    pos: Vector2DSchema = Field(..., description="位置")
    vel: Vector2DSchema = Field(..., description="速度")
    variant: int = Field(default=0, ge=0, description="变种")
    collision_radius: float = Field(default=5.0, ge=0, description="碰撞半径")
    height: float = Field(default=0.0, description="高度")
    falling_speed: float = Field(default=0.0, description="下落速度")
    falling_accel: float = Field(default=0.0, description="下落加速度")


class LaserData(BaseModel):
    """激光数据"""

    id: int = Field(..., ge=0, description="实体索引")
    pos: Vector2DSchema = Field(..., description="位置")
    angle: float = Field(default=0.0, description="角度")
    max_distance: float = Field(default=0.0, ge=0, description="最大距离")
    is_enemy: bool = Field(default=False, description="是否敌方")


class ProjectilesData(BaseModel):
    """投射物容器数据"""

    enemy_projectiles: List[ProjectileData] = Field(
        default_factory=list, description="敌方投射物"
    )
    player_tears: List[ProjectileData] = Field(
        default_factory=list, description="玩家泪弹"
    )
    lasers: List[LaserData] = Field(default_factory=list, description="激光")


class RoomInfoData(BaseModel):
    """房间信息数据"""

    room_type: int = Field(..., ge=0, description="房间类型")
    room_shape: int = Field(..., ge=0, description="房间形状")
    room_idx: int = Field(..., ge=0, description="房间索引")
    stage: int = Field(..., ge=0, description="关卡")
    stage_type: int = Field(default=0, ge=0, description="关卡类型")
    difficulty: int = Field(default=0, ge=0, description="难度")
    is_clear: bool = Field(default=False, description="是否已清除")
    is_first_visit: bool = Field(default=True, description="是否首次访问")
    grid_width: int = Field(..., ge=0, description="网格宽度")
    grid_height: int = Field(..., ge=0, description="网格高度")
    top_left: Vector2DSchema = Field(..., description="左上角坐标")
    bottom_right: Vector2DSchema = Field(..., description="右下角坐标")
    has_boss: bool = Field(default=False, description="是否有Boss")
    enemy_count: int = Field(default=0, ge=0, description="敌人数")
    room_variant: int = Field(default=0, ge=0, description="房间变种")


class GridEntityData(BaseModel):
    """网格实体数据"""

    type: int = Field(..., ge=0, description="网格类型")
    variant: int = Field(default=0, ge=0, description="变种")
    state: int = Field(default=0, ge=0, description="状态")
    collision: int = Field(default=0, ge=0, description="碰撞类型")
    x: float = Field(..., description="世界坐标X")
    y: float = Field(..., description="世界坐标Y")


class DoorData(BaseModel):
    """门数据"""

    target_room: int = Field(..., ge=0, description="目标房间")
    target_room_type: int = Field(default=0, ge=0, description="目标房间类型")
    is_open: bool = Field(default=False, description="是否打开")
    is_locked: bool = Field(default=False, description="是否锁定")
    x: float = Field(..., description="世界坐标X")
    y: float = Field(..., description="世界坐标Y")


class RoomLayoutData(BaseModel):
    """房间布局数据"""

    grid: Dict[str, GridEntityData] = Field(
        default_factory=dict, description="网格实体"
    )
    doors: Dict[str, DoorData] = Field(default_factory=dict, description="门")
    grid_size: int = Field(default=0, ge=0, description="网格总数")
    width: int = Field(default=0, ge=0, description="宽度")
    height: int = Field(default=0, ge=0, description="高度")


class PickupData(BaseModel):
    """可拾取物数据"""

    id: int = Field(..., ge=0, description="实体索引")
    variant: int = Field(default=0, ge=0, description="变种")
    sub_type: int = Field(default=0, ge=0, description="子类型")
    pos: Vector2DSchema = Field(..., description="位置")
    price: int = Field(default=0, ge=0, description="价格")
    shop_item_id: int = Field(default=-1, ge=-1, description="商店物品ID")
    wait: int = Field(default=0, ge=0, description="等待时间")


class BombData(BaseModel):
    """炸弹数据"""

    id: int = Field(..., ge=0, description="实体索引")
    type: int = Field(default=0, ge=0, description="类型")
    variant: int = Field(default=0, ge=0, description="变种")
    variant_name: str = Field(default="UNKNOWN", description="变种名称")
    sub_type: int = Field(default=0, ge=0, description="子类型")
    pos: Vector2DSchema = Field(..., description="位置")
    vel: Vector2DSchema = Field(..., description="速度")
    explosion_radius: float = Field(default=0.0, ge=0, description="爆炸半径")
    timer: int = Field(default=0, ge=0, description="计时器")
    distance: float = Field(default=0.0, ge=0, description="距离玩家")


class FireHazardData(BaseModel):
    """火焰危险物数据"""

    id: int = Field(..., ge=0, description="实体索引")
    type: str = Field(default="UNKNOWN", description="类型")
    fireplace_type: Optional[str] = Field(None, description="火堆类型")
    variant: int = Field(default=0, ge=0, description="变种")
    sub_variant: int = Field(default=0, ge=0, description="子变种")
    pos: Vector2DSchema = Field(..., description="位置")
    hp: float = Field(default=0.0, ge=0, description="生命值")
    max_hp: float = Field(default=0.0, ge=0, description="最大生命值")
    state: int = Field(default=0, ge=0, description="状态")
    is_extinguished: bool = Field(default=False, description="是否熄灭")
    collision_radius: float = Field(default=20.0, ge=0, description="碰撞半径")
    distance: float = Field(default=0.0, ge=0, description="距离玩家")
    is_shooting: bool = Field(default=False, description="是否在射击")
    sprite_scale: float = Field(default=1.0, ge=0, description="精灵缩放")


class InteractableData(BaseModel):
    """可互动实体数据"""

    id: int = Field(..., ge=0, description="实体索引")
    type: int = Field(default=0, ge=0, description="类型")
    variant: int = Field(default=0, ge=0, description="变种")
    variant_name: str = Field(default="UNKNOWN", description="变种名称")
    sub_type: int = Field(default=0, ge=0, description="子类型")
    pos: Vector2DSchema = Field(..., description="位置")
    vel: Vector2DSchema = Field(..., description="速度")
    state: int = Field(default=0, ge=0, description="状态")
    state_frame: int = Field(default=0, ge=0, description="状态帧")
    target_pos: Vector2DSchema = Field(
        default_factory=lambda: Vector2DSchema(x=0, y=0), description="目标位置"
    )
    distance: float = Field(default=0.0, ge=0, description="距离玩家")


class DataMessageSchema(BaseModel):
    """数据消息模式（v2.1 时序扩展）"""

    version: str = Field(default="2.1", description="协议版本")
    type: MessageType = Field(..., description="消息类型")
    timestamp: int = Field(..., ge=0, description="时间戳")
    frame: int = Field(..., ge=0, description="帧号")
    room_index: int = Field(default=-1, ge=-1, description="房间索引")

    # v2.1 时序字段
    seq: Optional[int] = Field(default=None, ge=0, description="消息序列号")
    game_time: Optional[int] = Field(default=None, ge=0, description="游戏时间戳")
    prev_frame: Optional[int] = Field(default=None, ge=0, description="上一帧号")
    channel_meta: Optional[Dict[str, ChannelMeta]] = Field(
        default=None, description="通道元数据"
    )

    payload: Dict[str, Any] = Field(default_factory=dict, description="数据负载")
    channels: List[str] = Field(default_factory=list, description="通道列表")

    class Config:
        extra = "allow"  # 允许额外字段（向后兼容）


class EventMessageSchema(BaseModel):
    """事件消息模式"""

    version: str = Field(default="2.0", description="协议版本")
    type: MessageType = Field(default=MessageType.EVENT, description="消息类型")
    timestamp: int = Field(..., ge=0, description="时间戳")
    frame: int = Field(..., ge=0, description="帧号")
    event: str = Field(..., description="事件类型")
    data: Dict[str, Any] = Field(default_factory=dict, description="事件数据")


class CommandMessageSchema(BaseModel):
    """命令消息模式"""

    version: str = Field(default="2.0", description="协议版本")
    type: MessageType = Field(default=MessageType.COMMAND, description="消息类型")
    timestamp: int = Field(default=0, ge=0, description="时间戳")
    frame: int = Field(default=0, ge=0, description="帧号")
    command: str = Field(..., description="命令类型")
    params: Dict[str, Any] = Field(default_factory=dict, description="命令参数")
