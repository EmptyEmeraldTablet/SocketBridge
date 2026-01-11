"""
数据处理层

负责原始数据的解析、格式标准化和坐标转换。
处理来自游戏的JSON数据，转换为内部标准化的数据结构。

根据 DATA_PROTOCOL.md 中的数据格式定义。

=== 调试信息说明 ===
本模块在数据流的关键位置添加了调试输出，用于追踪：
1. 原始消息接收
2. 各数据通道的解析结果
3. 异常情况的定位

日志级别：
- DEBUG: 详细的数据解析过程
- INFO: 关键处理节点
- WARNING: 数据异常
- ERROR: 解析错误
"""

import math
import traceback
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import logging

from models import (
    Vector2D,
    GameStateData,
    PlayerData,
    EnemyData,
    ProjectileData,
    LaserData,
    RoomInfo,
    RoomLayout,
    GridTile,
    DoorData,
    ButtonData,
    BombData,
    InteractableData,
    PickupData,
    FireHazardData,
    DestructibleData,
    EntityType,
)

logger = logging.getLogger("DataProcessor")


@dataclass
class RawDataPacket:
    """原始数据包"""

    frame: int
    room_index: int
    payload: Dict[str, Any]
    channels: List[str]


class DataParser:
    """数据解析器

    将游戏发送的原始JSON数据解析为标准化的数据结构。
    处理JSON数组和对象的兼容性问题。
    """

    # 方向映射 (0-7)
    DIRECTION_MAP = {
        0: (0, -1),  # 上
        1: (1, -1),  # 右上
        2: (1, 0),  # 右
        3: (1, 1),  # 右下
        4: (0, 1),  # 下
        5: (-1, 1),  # 左下
        6: (-1, 0),  # 左
        7: (-1, -1),  # 左上
    }

    @staticmethod
    def parse_player_position(data: Dict[str, Any]) -> Dict[int, Dict]:
        """
        解析玩家位置数据

        处理 Lua 数组 {[1]=...} 序列化后的两种格式:
        - JSON数组 [...] -> Python list
        - JSON对象 {"1": ...} -> Python dict
        """
        if data is None:
            return {}

        result = {}

        # 如果是列表（JSON数组）
        if isinstance(data, list):
            for idx, player_data in enumerate(data):
                player_idx = idx + 1  # Lua 1-based
                result[player_idx] = player_data
        # 如果是字典（JSON对象）
        elif isinstance(data, dict):
            for key, player_data in data.items():
                try:
                    player_idx = int(key)
                    result[player_idx] = player_data
                except ValueError:
                    logger.warning(f"Invalid player key: {key}")

        return result

    @staticmethod
    def parse_vector2d(data: Dict[str, float]) -> Vector2D:
        """从字典解析Vector2D"""
        if data is None:
            return Vector2D(0, 0)
        return Vector2D(x=data.get("x", 0), y=data.get("y", 0))

    @staticmethod
    def parse_direction(direction: int) -> Vector2D:
        """将方向值(0-7)转换为向量"""
        if direction in DataParser.DIRECTION_MAP:
            dx, dy = DataParser.DIRECTION_MAP[direction]
            return Vector2D(float(dx), float(dy))
        return Vector2D(0, 0)

    @staticmethod
    def parse_player_stats(data: Dict[str, Any]) -> PlayerData:
        """解析玩家属性数据"""
        if data is None:
            return PlayerData(player_idx=1)

        return PlayerData(
            player_idx=1,  # 默认为玩家1
            player_type=data.get("player_type", 0),
            damage=data.get("damage", 3.0),
            speed=data.get("speed", 1.0),
            tears=data.get("tears", 10.0),
            shot_range=data.get("range", 300),
            tear_range=data.get("tear_range", 300),
            shot_speed=data.get("shot_speed", 1.0),
            luck=data.get("luck", 0),
            can_fly=data.get("can_fly", False),
            size=data.get("size", 10.0),
            sprite_scale=data.get("sprite_scale", 1.0),
        )

    @staticmethod
    def parse_player_health(data: Dict[str, Any]) -> Dict:
        """解析玩家生命值数据"""
        if data is None:
            return {}

        return {
            "red_hearts": data.get("red_hearts", 0),
            "max_hearts": data.get("max_hearts", 6),
            "soul_hearts": data.get("soul_hearts", 0),
            "black_hearts": data.get("black_hearts", 0),
            "bone_hearts": data.get("bone_hearts", 0),
            "golden_hearts": data.get("golden_hearts", 0),
            "eternal_hearts": data.get("eternal_hearts", 0),
            "rotten_hearts": data.get("rotten_hearts", 0),
            "broken_hearts": data.get("broken_hearts", 0),
            "extra_lives": data.get("extra_lives", 0),
        }

    @staticmethod
    def parse_player_inventory(data: Dict[str, Any]) -> Dict:
        """解析玩家物品栏数据"""
        if data is None:
            return {}

        collectibles = data.get("collectibles", {})
        active_items = data.get("active_items", {})

        return {
            "coins": data.get("coins", 0),
            "bombs": data.get("bombs", 0),
            "keys": data.get("keys", 0),
            "trinket_0": data.get("trinket_0", 0),
            "trinket_1": data.get("trinket_1", 0),
            "card_0": data.get("card_0", 0),
            "pill_0": data.get("pill_0", 0),
            "collectible_count": data.get("collectible_count", 0),
            "collectibles": {str(k): v for k, v in collectibles.items()},
            "active_items": active_items,
        }

    @staticmethod
    def parse_enemies(data: List[Dict]) -> Dict[int, EnemyData]:
        """解析敌人数据列表"""
        enemies = {}

        if not data:
            return enemies

        for enemy_dict in data:
            enemy_id = enemy_dict.get("id")
            if enemy_id is None:
                continue

            # 解析位置
            pos_data = enemy_dict.get("pos", {})
            vel_data = enemy_dict.get("vel", {})
            target_pos_data = enemy_dict.get("target_pos", {})

            enemy = EnemyData(
                id=enemy_id,
                enemy_type=enemy_dict.get("type", 0),
                variant=enemy_dict.get("variant", 0),
                subtype=enemy_dict.get("subtype", 0),
                position=DataParser.parse_vector2d(pos_data),
                velocity=DataParser.parse_vector2d(vel_data),
                hp=enemy_dict.get("hp", 0),
                max_hp=enemy_dict.get("max_hp", 0),
                is_boss=enemy_dict.get("is_boss", False),
                is_champion=enemy_dict.get("is_champion", False),
                state=enemy_dict.get("state", 0),
                state_frame=enemy_dict.get("state_frame", 0),
                projectile_cooldown=enemy_dict.get("projectile_cooldown", 0),
                projectile_delay=enemy_dict.get("projectile_delay", 60),
                collision_radius=enemy_dict.get("collision_radius", 15.0),
                target_position=DataParser.parse_vector2d(target_pos_data),
                distance=enemy_dict.get("distance", 9999),
            )

            enemies[enemy_id] = enemy

        return enemies

    @staticmethod
    def parse_projectiles(data: Dict[str, List[Dict]]) -> tuple:
        """解析投射物数据"""
        enemy_projs = {}
        player_projs = {}
        lasers = {}

        if not data:
            return enemy_projs, player_projs, lasers

        # 敌方投射物
        for proj_dict in data.get("enemy_projectiles", []):
            proj_id = proj_dict.get("id")
            if proj_id is None:
                continue

            proj = ProjectileData(
                id=proj_id,
                is_enemy=True,
                position=DataParser.parse_vector2d(proj_dict.get("pos", {})),
                velocity=DataParser.parse_vector2d(proj_dict.get("vel", {})),
                variant=proj_dict.get("variant", 0),
                collision_radius=proj_dict.get("collision_radius", 8.0),
                height=proj_dict.get("height", 0.0),
                falling_speed=proj_dict.get("falling_speed", 0.0),
            )
            enemy_projs[proj_id] = proj

        # 玩家投射物（眼泪）
        for proj_dict in data.get("player_tears", []):
            proj_id = proj_dict.get("id")
            if proj_id is None:
                continue

            proj = ProjectileData(
                id=proj_id,
                is_enemy=False,
                position=DataParser.parse_vector2d(proj_dict.get("pos", {})),
                velocity=DataParser.parse_vector2d(proj_dict.get("vel", {})),
                variant=proj_dict.get("variant", 0),
                collision_radius=proj_dict.get("collision_radius", 6.0),
                height=proj_dict.get("height", 0.0),
                scale=proj_dict.get("scale", 1.0),
            )
            player_projs[proj_id] = proj

        # 激光
        for laser_dict in data.get("lasers", []):
            laser_id = laser_dict.get("id")
            if laser_id is None:
                continue

            laser = LaserData(
                id=laser_id,
                is_enemy=laser_dict.get("is_enemy", False),
                position=DataParser.parse_vector2d(laser_dict.get("pos", {})),
                angle=laser_dict.get("angle", 0),
                max_distance=laser_dict.get("max_distance", 500),
            )
            lasers[laser_id] = laser

        return enemy_projs, player_projs, lasers

    @staticmethod
    def parse_room_info(data: Dict[str, Any]) -> Optional[RoomInfo]:
        """解析房间信息"""
        if data is None:
            return None

        return RoomInfo(
            room_type=data.get("room_type", 0),
            room_shape=data.get("room_shape", 0),
            room_index=data.get("room_idx", 0),
            stage=data.get("stage", 0),
            stage_type=data.get("stage_type", 0),
            difficulty=data.get("difficulty", 0),
            is_clear=data.get("is_clear", False),
            is_first_visit=data.get("is_first_visit", True),
            grid_width=data.get("grid_width", 13),
            grid_height=data.get("grid_height", 7),
            top_left=DataParser.parse_vector2d(data.get("top_left", {})),
            bottom_right=DataParser.parse_vector2d(data.get("bottom_right", {})),
            has_boss=data.get("has_boss", False),
            enemy_count=data.get("enemy_count", 0),
            room_variant=data.get("room_variant", 0),
        )

    @staticmethod
    def parse_room_layout(data: Dict[str, Any]) -> Optional[RoomLayout]:
        """解析房间布局"""
        if data is None:
            return None

        layout = RoomLayout(
            grid_size=data.get("grid_size", 91),
            width=data.get("width", 13),
            height=data.get("height", 7),
        )

        # 解析网格瓷砖
        grid_data = data.get("grid", {})
        for idx_str, tile_data in grid_data.items():
            try:
                idx = int(idx_str)
            except ValueError:
                continue

            tile = GridTile(
                grid_index=idx,
                tile_type=tile_data.get("type", 0),
                variant=tile_data.get("variant", 0),
                variant_name=tile_data.get("variant_name", "UNKNOWN"),
                state=tile_data.get("state", 0),
                has_collision=tile_data.get("collision", 1) > 0,
                position=DataParser.parse_vector2d(tile_data.get("pos", {})),
            )
            layout.tiles[idx] = tile

        # 解析门
        doors_data = data.get("doors", {})
        for slot_str, door_data in doors_data.items():
            try:
                slot = int(slot_str)
            except ValueError:
                continue

            door = DoorData(
                door_slot=slot,
                target_room=door_data.get("target_room", -1),
                target_room_type=door_data.get("target_room_type", 0),
                is_open=door_data.get("is_open", False),
                is_locked=door_data.get("is_locked", False),
            )
            layout.doors[slot] = door

        return layout

    @staticmethod
    def parse_buttons(data: Dict[str, Any]) -> Dict[int, ButtonData]:
        """解析按钮数据"""
        buttons = {}

        if not data:
            return buttons

        for idx_str, btn_data in data.items():
            try:
                idx = int(idx_str)
            except ValueError:
                continue

            button = ButtonData(
                button_idx=idx,
                button_type=btn_data.get("type", 0),
                variant=btn_data.get("variant", 0),
                variant_name=btn_data.get("variant_name", "NORMAL"),
                state=btn_data.get("state", 0),
                is_pressed=btn_data.get("is_pressed", False),
                position=DataParser.parse_vector2d(btn_data.get("pos", {})),
                distance=btn_data.get("distance", 0),
            )
            buttons[idx] = button

        return buttons

    @staticmethod
    def parse_bombs(data: List[Dict]) -> Dict[int, BombData]:
        """解析炸弹数据"""
        bombs = {}

        if not data:
            return bombs

        for bomb_dict in data:
            bomb_id = bomb_dict.get("id")
            if bomb_id is None:
                continue

            bomb = BombData(
                id=bomb_id,
                bomb_type=bomb_dict.get("type", 0),
                variant=bomb_dict.get("variant", 0),
                variant_name=bomb_dict.get("variant_name", "NORMAL"),
                sub_type=bomb_dict.get("sub_type", 0),
                position=DataParser.parse_vector2d(bomb_dict.get("pos", {})),
                velocity=DataParser.parse_vector2d(bomb_dict.get("vel", {})),
                explosion_radius=bomb_dict.get("explosion_radius", 80),
                timer=bomb_dict.get("timer", 60),
                distance=bomb_dict.get("distance", 0),
            )
            bombs[bomb_id] = bomb

        return bombs

    @staticmethod
    def parse_interactables(data: List[Dict]) -> Dict[int, InteractableData]:
        """解析可互动实体数据"""
        interactables = {}

        if not data:
            return interactables

        for entity_dict in data:
            entity_id = entity_dict.get("id")
            if entity_id is None:
                continue

            entity = InteractableData(
                id=entity_id,
                entity_type=entity_dict.get("type", 0),
                variant=entity_dict.get("variant", 0),
                variant_name=entity_dict.get("variant_name", "UNKNOWN"),
                sub_type=entity_dict.get("sub_type", 0),
                position=DataParser.parse_vector2d(entity_dict.get("pos", {})),
                velocity=DataParser.parse_vector2d(entity_dict.get("vel", {})),
                state=entity_dict.get("state", 0),
                state_frame=entity_dict.get("state_frame", 0),
                distance=entity_dict.get("distance", 0),
                target_position=DataParser.parse_vector2d(
                    entity_dict.get("target_pos", {})
                ),
            )
            interactables[entity_id] = entity

        return interactables

    @staticmethod
    def parse_pickups(data: List[Dict]) -> Dict[int, PickupData]:
        """解析可拾取物数据"""
        pickups = {}

        if not data:
            return pickups

        for item_dict in data:
            item_id = item_dict.get("id")
            if item_id is None:
                continue

            item = PickupData(
                id=item_id,
                variant=item_dict.get("variant", 0),
                sub_type=item_dict.get("sub_type", 0),
                position=DataParser.parse_vector2d(item_dict.get("pos", {})),
                price=item_dict.get("price", 0),
                shop_item_id=item_dict.get("shop_item_id", -1),
                wait=item_dict.get("wait", 0),
            )
            pickups[item_id] = item

        return pickups

    @staticmethod
    def parse_fire_hazards(data: List[Dict]) -> Dict[int, FireHazardData]:
        """解析火焰危险物数据"""
        hazards = {}

        if not data:
            return hazards

        for fire_dict in data:
            fire_id = fire_dict.get("id")
            if fire_id is None:
                continue

            fire = FireHazardData(
                id=fire_id,
                fire_type=fire_dict.get("fireplace_type", "NORMAL"),
                variant=fire_dict.get("variant", 0),
                sub_variant=fire_dict.get("sub_variant", 0),
                position=DataParser.parse_vector2d(fire_dict.get("pos", {})),
                hp=fire_dict.get("hp", 5.0),
                max_hp=fire_dict.get("max_hp", 10.0),
                state=fire_dict.get("state", 0),
                is_extinguished=fire_dict.get("is_extinguished", False),
                is_shooting=fire_dict.get("is_shooting", False),
                collision_radius=fire_dict.get("collision_radius", 25.0),
                distance=fire_dict.get("distance", 0),
                sprite_scale=fire_dict.get("sprite_scale", 1.0),
            )
            hazards[fire_id] = fire

        return hazards

    @staticmethod
    def parse_destructibles(data: List[Dict]) -> Dict[int, DestructibleData]:
        """解析可破坏障碍物数据"""
        destructibles = {}

        if not data:
            return destructibles

        for obj_dict in data:
            grid_idx = obj_dict.get("grid_index")
            if grid_idx is None:
                continue

            obj = DestructibleData(
                grid_index=grid_idx,
                obj_type=obj_dict.get("type", 0),
                name=obj_dict.get("name", "UNKNOWN"),
                position=DataParser.parse_vector2d(obj_dict.get("pos", {})),
                state=obj_dict.get("state", 0),
                distance=obj_dict.get("distance", 0),
                variant=obj_dict.get("variant", 0),
                variant_name=obj_dict.get("variant_name", "NORMAL"),
            )
            destructibles[grid_idx] = obj

        return destructibles


class CoordinateConverter:
    """坐标转换器

    像素坐标与逻辑坐标之间的转换。
    游戏内使用像素坐标，AI决策可能需要逻辑坐标。
    """

    # 像素到逻辑单位的比例
    PIXEL_TO_LOGICAL = 1.0  # 1:1 转换，可根据需要调整

    @staticmethod
    def pixel_to_logical(pixel_x: float, pixel_y: float) -> tuple:
        """像素坐标转逻辑坐标"""
        return (
            pixel_x * CoordinateConverter.PIXEL_TO_LOGICAL,
            pixel_y * CoordinateConverter.PIXEL_TO_LOGICAL,
        )

    @staticmethod
    def logical_to_pixel(logical_x: float, logical_y: float) -> tuple:
        """逻辑坐标转像素坐标"""
        return (
            logical_x / CoordinateConverter.PIXEL_TO_LOGICAL,
            logical_y / CoordinateConverter.PIXEL_TO_LOGICAL,
        )

    @staticmethod
    def vector_pixel_to_logical(vec: Vector2D) -> Vector2D:
        """向量从像素转换到逻辑空间"""
        return Vector2D(
            vec.x * CoordinateConverter.PIXEL_TO_LOGICAL,
            vec.y * CoordinateConverter.PIXEL_TO_LOGICAL,
        )

    @staticmethod
    def vector_logical_to_pixel(vec: Vector2D) -> Vector2D:
        """向量从逻辑空间转换到像素"""
        return Vector2D(
            vec.x / CoordinateConverter.PIXEL_TO_LOGICAL,
            vec.y / CoordinateConverter.PIXEL_TO_LOGICAL,
        )


class DataProcessor:
    """数据处理器

    整合数据解析和坐标转换，提供统一的数据处理接口。
    """

    def __init__(self):
        self.parser = DataParser()
        self.converter = CoordinateConverter()

        # 状态
        self.current_frame = 0
        self.current_room = -1

    def process_message(self, msg: Dict[str, Any]) -> GameStateData:
        """
        处理完整的游戏消息，返回标准化的游戏状态

        Args:
            msg: 来自游戏的JSON消息

        Returns:
            标准化的GameStateData对象

        === 调试信息 ===
        输入: 原始消息字典，包含 type, frame, room_index, payload
        处理流程:
            1. 解析消息类型和基本信息
            2. 解析玩家数据 (位置、属性、生命值、物品栏)
            3. 解析敌人数据
            4. 解析投射物数据
            5. 解析房间信息
            6. 解析房间布局
            7. 处理环境数据
        输出: GameStateData 对象
        """
        state = GameStateData()

        # [DEBUG] 记录原始消息概览
        msg_type = msg.get("type", "DATA")
        frame = msg.get("frame", 0)
        room_index = msg.get("room_index", -1)
        payload = msg.get("payload", {})

        logger.debug(f"[DataProcessor] === START process_message ===")
        logger.debug(
            f"[DataProcessor] type={msg_type}, frame={frame}, room_index={room_index}"
        )
        logger.debug(
            f"[DataProcessor] payload keys={list(payload.keys()) if payload else []}"
        )

        # [DEBUG] 详细记录每个通道的数据
        if payload:
            for channel, data in payload.items():
                if data is not None:
                    if isinstance(data, list):
                        logger.debug(
                            f"[DataProcessor] Channel {channel}: list length={len(data)}"
                        )
                    elif isinstance(data, dict):
                        logger.debug(
                            f"[DataProcessor] Channel {channel}: dict keys={list(data.keys())}"
                        )
                    else:
                        logger.debug(
                            f"[DataProcessor] Channel {channel}: {type(data).__name__}"
                        )
                else:
                    logger.debug(f"[DataProcessor] Channel {channel}: None")

        # [TRACKING] 记录帧变化
        if self.current_frame != 0 and frame < self.current_frame:
            logger.warning(
                f"[DataProcessor] Frame regression detected: {self.current_frame} -> {frame}"
            )

        # [TRACKING] 记录房间变化
        if self.current_room != -1 and room_index != self.current_room:
            logger.info(
                f"[DataProcessor] Room changed: {self.current_room} -> {room_index}"
            )

        state.frame = frame
        state.room_index = room_index

        if not payload:
            logger.debug(f"[DataProcessor] Empty payload, returning empty state")
            return state

        try:
            # 处理玩家数据
            logger.debug(f"[DataProcessor] Processing player data...")
            self._process_player_data(state, payload)
            player = state.get_primary_player()
            if player:
                logger.debug(
                    f"[DataProcessor] Player parsed: pos=({player.position.x:.1f}, {player.position.y:.1f}), "
                    f"hp={player.red_hearts}/{player.max_hearts}"
                )
            else:
                logger.warning(f"[DataProcessor] No player data found in payload")

            # 处理敌人
            if "ENEMIES" in payload:
                logger.debug(f"[DataProcessor] Processing ENEMIES...")
                state.enemies = self.parser.parse_enemies(payload["ENEMIES"])
                enemy_count = len(state.enemies)
                logger.debug(f"[DataProcessor] Enemies parsed: count={enemy_count}")
                if enemy_count > 0:
                    # 记录最近的敌人
                    if player:
                        nearest = state.get_nearest_enemy(player.position)
                        if nearest:
                            logger.debug(
                                f"[DataProcessor] Nearest enemy: id={nearest.id}, "
                                f"dist={nearest.distance:.1f}, hp={nearest.hp:.1f}/{nearest.max_hp}"
                            )

            # 处理投射物
            if "PROJECTILES" in payload:
                logger.debug(f"[DataProcessor] Processing PROJECTILES...")
                enemy_projs, player_projs, lasers = self.parser.parse_projectiles(
                    payload["PROJECTILES"]
                )
                state.enemy_projectiles = enemy_projs
                state.player_projectiles = player_projs
                state.lasers = lasers
                enemy_proj_count = len(enemy_projs)
                player_proj_count = len(player_projs)
                laser_count = len(lasers)
                logger.debug(
                    f"[DataProcessor] Projectiles parsed: enemy={enemy_proj_count}, "
                    f"player={player_proj_count}, lasers={laser_count}"
                )

            # 处理房间信息
            if "ROOM_INFO" in payload:
                logger.debug(f"[DataProcessor] Processing ROOM_INFO...")
                state.room_info = self.parser.parse_room_info(payload["ROOM_INFO"])
                if state.room_info:
                    logger.debug(
                        f"[DataProcessor] Room info: idx={state.room_info.room_index}, "
                        f"stage={state.room_info.stage}, enemy_count={state.room_info.enemy_count}, "
                        f"is_clear={state.room_info.is_clear}"
                    )

            # 处理房间布局
            if "ROOM_LAYOUT" in payload:
                logger.debug(f"[DataProcessor] Processing ROOM_LAYOUT...")
                state.room_layout = self.parser.parse_room_layout(
                    payload["ROOM_LAYOUT"]
                )
                if state.room_layout:
                    tile_count = len(state.room_layout.tiles)
                    door_count = len(state.room_layout.doors)
                    logger.debug(
                        f"[DataProcessor] Room layout: tiles={tile_count}, doors={door_count}"
                    )

            # 处理其他数据
            self._process_environment_data(state, payload)

            # 更新帧和房间状态
            self.current_frame = frame
            self.current_room = room_index

            logger.debug(f"[DataProcessor] === END process_message ===")

            return state

        except Exception as e:
            # [ERROR] 记录详细错误信息
            error_msg = f"Error processing message at frame {frame}: {str(e)}"
            logger.error(f"[DataProcessor] {error_msg}")
            logger.error(f"[DataProcessor] Traceback: {traceback.format_exc()}")
            logger.error(f"[DataProcessor] Payload at error: {payload}")

            # 抛出异常以便上层捕获
            raise RuntimeError(error_msg) from e

    def _process_player_data(self, state: GameStateData, payload: Dict[str, Any]):
        """处理玩家相关数据

        === 调试跟踪点 ===
        - PLAYER_POSITION: 玩家位置数据
        - PLAYER_STATS: 玩家属性数据
        - PLAYER_HEALTH: 玩家生命值
        - PLAYER_INVENTORY: 玩家物品栏
        """
        logger.debug(
            f"[DataProcessor] _process_player_data: payload keys = {list(payload.keys())}"
        )

        # 位置数据
        if "PLAYER_POSITION" in payload:
            logger.debug(f"[DataProcessor] Processing PLAYER_POSITION...")
            positions = self.parser.parse_player_position(payload["PLAYER_POSITION"])
            logger.debug(
                f"[DataProcessor] Parsed {len(positions)} player position entries"
            )
            for idx, pos_data in positions.items():
                if idx not in state.players:
                    state.players[idx] = PlayerData(player_idx=idx)

                player = state.players[idx]
                player.position = self.parser.parse_vector2d(pos_data.get("pos", {}))
                player.velocity = self.parser.parse_vector2d(pos_data.get("vel", {}))
                player.move_direction = pos_data.get("move_dir", 0)
                player.fire_direction = pos_data.get("fire_dir", 0)
                player.head_direction = pos_data.get("head_dir", 0)
                player.aim_direction = self.parser.parse_vector2d(
                    pos_data.get("aim_dir", {})
                )
                logger.debug(
                    f"[DataProcessor] Player {idx} position: ({player.position.x:.1f}, {player.position.y:.1f})"
                )

        # 属性数据
        if "PLAYER_STATS" in payload:
            logger.debug(f"[DataProcessor] Processing PLAYER_STATS...")
            stats = self.parser.parse_player_position(payload["PLAYER_STATS"])
            for idx, stats_data in stats.items():
                if idx not in state.players:
                    state.players[idx] = PlayerData(player_idx=idx)

                parsed_stats = self.parser.parse_player_stats(stats_data)
                for field in [
                    "player_type",
                    "damage",
                    "speed",
                    "tears",
                    "shot_range",
                    "tear_range",
                    "shot_speed",
                    "luck",
                    "can_fly",
                    "size",
                    "sprite_scale",
                ]:
                    setattr(state.players[idx], field, getattr(parsed_stats, field))
                logger.debug(
                    f"[DataProcessor] Player {idx} stats: damage={parsed_stats.damage}, "
                    f"speed={parsed_stats.speed}, tears={parsed_stats.tears}"
                )

        # 生命值
        if "PLAYER_HEALTH" in payload:
            logger.debug(f"[DataProcessor] Processing PLAYER_HEALTH...")
            health = self.parser.parse_player_position(payload["PLAYER_HEALTH"])
            for idx, health_data in health.items():
                if idx not in state.players:
                    state.players[idx] = PlayerData(player_idx=idx)

                parsed_health = self.parser.parse_player_health(health_data)
                for field, value in parsed_health.items():
                    setattr(state.players[idx], field, value)
                logger.debug(
                    f"[DataProcessor] Player {idx} health: red={parsed_health['red_hearts']}, "
                    f"max={parsed_health['max_hearts']}, soul={parsed_health['soul_hearts']}"
                )

        # 物品栏
        if "PLAYER_INVENTORY" in payload:
            logger.debug(f"[DataProcessor] Processing PLAYER_INVENTORY...")
            inventory = self.parser.parse_player_position(payload["PLAYER_INVENTORY"])
            for idx, inv_data in inventory.items():
                if idx not in state.players:
                    state.players[idx] = PlayerData(player_idx=idx)

                parsed_inv = self.parser.parse_player_inventory(inv_data)
                for field in [
                    "coins",
                    "bombs",
                    "keys",
                    "trinket_0",
                    "trinket_1",
                    "card_0",
                    "pill_0",
                    "collectible_count",
                ]:
                    setattr(state.players[idx], field, parsed_inv.get(field, 0))
                state.players[idx].collectibles = parsed_inv.get("collectibles", {})
                state.players[idx].active_items = parsed_inv.get("active_items", {})
                logger.debug(
                    f"[DataProcessor] Player {idx} inventory: coins={parsed_inv['coins']}, "
                    f"bombs={parsed_inv['bombs']}, keys={parsed_inv['keys']}, "
                    f"collectibles={parsed_inv['collectible_count']}"
                )

    def _process_environment_data(self, state: GameStateData, payload: Dict[str, Any]):
        """处理环境相关数据

        === 调试跟踪点 ===
        - BUTTONS: 按钮状态
        - BOMBS: 炸弹数据
        - INTERACTABLES: 可互动实体
        - PICKUPS: 可拾取物
        - FIRE_HAZARDS: 火焰危险物
        - DESTRUCTIBLES: 可破坏物
        """
        logger.debug(
            f"[DataProcessor] _process_environment_data: checking for environment channels"
        )

        # 按钮
        if "BUTTONS" in payload:
            logger.debug(f"[DataProcessor] Processing BUTTONS...")
            state.buttons = self.parser.parse_buttons(payload["BUTTONS"])
            logger.debug(f"[DataProcessor] Buttons: {len(state.buttons)}")

        # 炸弹
        if "BOMBS" in payload:
            logger.debug(f"[DataProcessor] Processing BOMBS...")
            state.bombs = self.parser.parse_bombs(payload["BOMBS"])
            bomb_count = len(state.bombs)
            logger.debug(f"[DataProcessor] Bombs: {bomb_count}")
            if bomb_count > 0:
                for bid, bomb in state.bombs.items():
                    logger.debug(
                        f"[DataProcessor] Bomb {bid}: type={bomb.variant_name}, timer={bomb.timer}"
                    )

        # 可互动实体
        if "INTERACTABLES" in payload:
            logger.debug(f"[DataProcessor] Processing INTERACTABLES...")
            state.interactables = self.parser.parse_interactables(
                payload["INTERACTABLES"]
            )
            logger.debug(f"[DataProcessor] Interactables: {len(state.interactables)}")

        # 可拾取物
        if "PICKUPS" in payload:
            logger.debug(f"[DataProcessor] Processing PICKUPS...")
            state.pickups = self.parser.parse_pickups(payload["PICKUPS"])
            logger.debug(f"[DataProcessor] Pickups: {len(state.pickups)}")

        # 火焰危险物
        if "FIRE_HAZARDS" in payload:
            logger.debug(f"[DataProcessor] Processing FIRE_HAZARDS...")
            state.fire_hazards = self.parser.parse_fire_hazards(payload["FIRE_HAZARDS"])
            fire_count = len(state.fire_hazards)
            logger.debug(f"[DataProcessor] Fire hazards: {fire_count}")

        # 可破坏物
        if "DESTRUCTIBLES" in payload:
            logger.debug(f"[DataProcessor] Processing DESTRUCTIBLES...")
            state.destructibles = self.parser.parse_destructibles(
                payload["DESTRUCTIBLES"]
            )
            logger.debug(f"[DataProcessor] Destructibles: {len(state.destructibles)}")

    def merge_state(self, current: GameStateData, new: GameStateData) -> GameStateData:
        """
        合并两个状态，保留已有数据并更新变化的部分

        用于增量更新，避免重复解析未变化的数据。
        """
        # 合并玩家数据
        for idx, player in new.players.items():
            if idx in current.players:
                # 保留完整对象，只更新变化的字段
                for field, value in player.__dict__.items():
                    if field != "player_idx":
                        setattr(current.players[idx], field, value)
            else:
                current.players[idx] = player

        # 更新敌人
        current.enemies = new.enemies

        # 更新投射物
        current.enemy_projectiles = new.enemy_projectiles
        current.player_projectiles = new.player_projectiles
        current.lasers = new.lasers

        # 更新房间信息
        if new.room_info:
            current.room_info = new.room_info

        if new.room_layout:
            current.room_layout = new.room_layout

        # 更新环境数据
        current.buttons = new.buttons
        current.bombs = new.bombs
        current.interactables = new.interactables
        current.pickups = new.pickups
        current.fire_hazards = new.fire_hazards
        current.destructibles = new.destructibles

        # 更新帧信息
        current.frame = new.frame
        current.room_index = new.room_index

        return current
