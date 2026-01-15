"""
SocketBridge 数据处理层

负责原始数据的解析、格式标准化和坐标转换。
处理来自游戏的JSON数据，转换为内部标准化的数据结构。

根据 DATA_PROTOCOL.md 中的数据格式定义。
"""

import math
import traceback
from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass
import logging

from models import (
    Vector2D,
    GameStateData,
    PlayerData,
    EnemyData,
    ProjectileData,
    RoomInfo,
    RoomLayout,
    GridTile,
    DoorData,
    EntityType,
    ObjectState,
    ButtonData,
    FireHazardData,
    InteractableData,
    PickupData,
    DestructibleData,
    BombData,
    PlayerHealthData,
    PlayerStatsData,
    PlayerInventoryData,
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
        """解析玩家位置数据

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
    def parse_vector2d(data: Optional[Dict[str, float]]) -> Vector2D:
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

        player = PlayerData(player_idx=data.get("player_idx", 1))

        # 位置和速度
        if "pos" in data:
            player.position = DataParser.parse_vector2d(data["pos"])
        if "vel" in data:
            player.velocity = DataParser.parse_vector2d(data["vel"])

        # 属性
        player.player_type = data.get("player_type", 0)
        player.health = data.get("health", 3.0)
        player.max_health = data.get("max_health", 3.0)
        player.damage = data.get("damage", 3.0)
        player.speed = data.get("speed", 1.0)
        player.tears = data.get("tears", 10.0)
        player.tear_range = data.get("tear_range", 300)
        player.shot_speed = data.get("shot_speed", 1.0)
        player.luck = data.get("luck", 0)
        player.can_fly = data.get("can_fly", False)
        player.size = data.get("size", 10.0)

        # 方向
        player.facing_direction = data.get("direction", 0)

        # 状态
        player.is_invincible = data.get("invincible", False)
        player.is_shooting = data.get("shooting", False)
        player.is_charging = data.get("charging", False)

        return player

    @staticmethod
    def parse_enemy(data: Dict[str, Any]) -> Optional[EnemyData]:
        """解析敌人数据"""
        if data is None:
            return None

        enemy_id = data.get("id")
        if enemy_id is None:
            return None

        enemy = EnemyData(enemy_id=enemy_id)

        # 位置和速度
        if "pos" in data:
            enemy.position = DataParser.parse_vector2d(data["pos"])
        if "vel" in data:
            enemy.velocity = DataParser.parse_vector2d(data["vel"])

        # 属性
        enemy.enemy_type = data.get("type", 0)
        enemy.hp = data.get("hp", 10.0)
        enemy.max_hp = data.get("max_hp", 10.0)
        enemy.damage = data.get("damage", 1.0)

        # 状态标记
        enemy.is_boss = data.get("is_boss", False)
        enemy.is_champion = data.get("is_champion", False)
        enemy.is_flying = data.get("is_flying", False)
        enemy.is_attacking = data.get("is_attacking", False)

        # 状态
        if data.get("dead"):
            enemy.state = ObjectState.DEAD
        elif data.get("dying"):
            enemy.state = ObjectState.DYING

        return enemy

    @staticmethod
    def parse_enemies(data: Dict[str, Any]) -> Dict[int, EnemyData]:
        """解析敌人字典"""
        if data is None:
            return {}

        enemies = {}
        for enemy_id, enemy_data in data.items():
            try:
                eid = int(enemy_id)
                enemy = DataParser.parse_enemy(enemy_data)
                if enemy:
                    enemies[eid] = enemy
            except (ValueError, TypeError):
                logger.warning(f"Invalid enemy ID: {enemy_id}")

        return enemies

    @staticmethod
    def parse_projectile(data: Dict[str, Any]) -> Optional[ProjectileData]:
        """解析投射物数据"""
        if data is None:
            return None

        proj_id = data.get("id")
        if proj_id is None:
            return None

        proj = ProjectileData(projectile_id=proj_id)

        # 位置和速度
        if "pos" in data:
            proj.position = DataParser.parse_vector2d(data["pos"])
        if "vel" in data:
            proj.velocity = DataParser.parse_vector2d(data["vel"])

        # 属性
        proj.projectile_type = data.get("type", 0)
        proj.damage = data.get("damage", 1.0)
        proj.size = data.get("size", 5.0)
        proj.lifetime = data.get("lifetime", 300)
        proj.is_enemy = data.get("is_enemy", False)

        # 特殊属性
        proj.is_spectral = data.get("spectral", False)
        proj.is_homing = data.get("homing", False)
        proj.piercing = data.get("piercing", 0)

        return proj

    @staticmethod
    def parse_projectiles(data: Dict[str, Any]) -> Dict[int, ProjectileData]:
        """解析投射物字典"""
        if data is None:
            return {}

        projectiles = {}
        for proj_id, proj_data in data.items():
            try:
                pid = int(proj_id)
                proj = DataParser.parse_projectile(proj_data)
                if proj:
                    projectiles[pid] = proj
            except (ValueError, TypeError):
                logger.warning(f"Invalid projectile ID: {proj_id}")

        return projectiles

    @staticmethod
    def parse_room_info(data: Dict[str, Any]) -> Optional[RoomInfo]:
        """解析房间信息

        DEBUG: Added room_shape parsing based on analyzed_rooms findings.
        Room shape codes:
          0 = normal (rectangle)
          1 = rectangle
          2 = L-shape (top fold)
          3 = shop (small rectangle)
          4 = tall rectangle
          5 = wide rectangle
          6 = wide_tight (grid_size=252)
          7-11 = L-shaped variants
        """
        if data is None:
            return None

        info = RoomInfo()

        info.room_index = data.get("room_index", -1)
        info.stage = data.get("stage", 1)
        info.stage_type = data.get("stage_type", 0)
        info.difficulty = data.get("difficulty", 0)

        info.grid_width = data.get("grid_width", 13)
        info.grid_height = data.get("grid_height", 7)

        info.pixel_width = data.get("pixel_width", 0)
        info.pixel_height = data.get("pixel_height", 0)

        # 解析房间边界坐标（top_left 和 bottom_right）
        top_left = data.get("top_left")
        if top_left and isinstance(top_left, dict):
            info.top_left = (top_left.get("x", 0.0), top_left.get("y", 0.0))

        bottom_right = data.get("bottom_right")
        if bottom_right and isinstance(bottom_right, dict):
            info.bottom_right = (bottom_right.get("x", 0.0), bottom_right.get("y", 0.0))

        info.room_type = data.get("room_type", "normal")

        # DEBUG: Parse room_shape (MISSING before fix)
        # Key finding: room_shape determines grid_size and L-shape handling
        # - Shape 2 = L-shape with top fold (confirmed from analyzed_rooms)
        # - Shape 6 = wide_tight with grid_size=252 (special case)
        info.room_shape = data.get("room_shape", 0)
        logger.debug(
            f"[DataParser] Parsed room_shape={info.room_shape} for room {info.room_index}"
        )

        info.is_clear = data.get("is_clear", False)
        info.enemy_count = data.get("enemy_count", 0)

        logger.debug(
            f"[DataParser] Parsed room_info: idx={info.room_index}, "
            f"grid={info.grid_width}x{info.grid_height}, shape={info.room_shape}"
        )

        return info

    @staticmethod
    def parse_room_layout(data: Dict[str, Any]) -> Optional[RoomLayout]:
        """解析房间布局"""
        if data is None:
            return None

        room_info = DataParser.parse_room_info(data.get("info"))

        layout = RoomLayout(room_info=room_info)

        # 解析网格
        if "grid" in data:
            grid_data = data["grid"]
            if isinstance(grid_data, list):
                for y, row in enumerate(grid_data):
                    for x, tile_data in enumerate(row):
                        if x < len(layout.grid) and y < len(layout.grid[0]):
                            tile = layout.grid[x][y]
                            tile.tile_type = tile_data.get("type", "empty")
                            tile.is_solid = tile_data.get("solid", False)

        # 解析门
        # DEBUG: Fix doors parsing - doors is dict format per DATA_PROTOCOL.md
        # {"0": {"target_room": 3, "is_open": true, ...}, "1": {...}}
        if "doors" in data:
            for door_idx, door_data in data["doors"].items():
                door = DoorData(
                    direction=int(door_idx) if door_idx.isdigit() else 0,
                    door_type=door_data.get("type", "door"),
                    target_room=door_data.get("target_room", -1),
                    is_open=door_data.get("is_open", False),
                )
                layout.doors.append(door)
            logger.debug(f"[DataParser] Parsed {len(layout.doors)} doors")

        return layout


class DataProcessor:
    """数据处理器

    整合数据解析，提供统一的数据处理接口。
    """

    def __init__(self):
        self.parser = DataParser()
        self.current_state = GameStateData()
        self._prev_room_index: Optional[int] = None

    def _clear_room_entities(self):
        """清除所有房间特有的实体（切换房间时调用）

        保留玩家数据（玩家会跟随进入新房间）
        清除：敌人、投射物、拾取物、障碍物、按钮、火焰、可交互物、炸弹
        """
        self.current_state.enemies.clear()
        self.current_state.projectiles.clear()
        self.current_state.pickups.clear()
        self.current_state.obstacles.clear()
        self.current_state.buttons.clear()
        self.current_state.fire_hazards.clear()
        self.current_state.interactables.clear()
        self.current_state.bombs.clear()
        self.current_state.lasers.clear()
        logger.debug("[DataProcessor] Cleared all room entities on room transition")

    def _handle_room_transition(self, new_room_index: int):
        """处理房间切换

        当 room_index 变化时，清除旧房间的实体数据
        """
        if (
            self._prev_room_index is not None
            and new_room_index != self._prev_room_index
        ):
            logger.debug(
                f"[DataProcessor] Room transition: {self._prev_room_index} -> {new_room_index}"
            )
            self._clear_room_entities()
        self._prev_room_index = new_room_index

    def process_message(self, raw_message: Dict[str, Any]) -> GameStateData:
        """处理原始消息，更新游戏状态

        Args:
            raw_message: 原始消息字典

        Returns:
            更新后的游戏状态
        """
        try:
            msg_type = raw_message.get("type", "DATA")

            if msg_type == "DATA":
                return self._process_data_message(raw_message)
            elif msg_type == "EVENT":
                self._process_event(raw_message)
                return self.current_state
            elif msg_type == "FULL":
                return self._process_full_state(raw_message)
            else:
                logger.warning(f"Unknown message type: {msg_type}")
                return self.current_state

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            logger.debug(traceback.format_exc())
            return self.current_state

    def _process_data_message(self, message: Dict[str, Any]) -> GameStateData:
        """处理DATA消息

        状态保持机制：
        - 只更新 payload 中存在的通道
        - 未更新的通道保留上次的数据
        - 自动清理超过 ENTITY_EXPIRY_FRAMES 未更新的实体
        """
        # 更新基本信息
        self.current_state.frame = message.get("frame", 0)
        self.current_state.timestamp = message.get("timestamp", 0)

        # 处理房间切换（检测 room_index 变化并清除旧房间实体）
        new_room_index = message.get("room_index", -1)
        self._handle_room_transition(new_room_index)
        self.current_state.room_index = new_room_index

        payload = message.get("payload", {})

        # ============================================================
        # 解析玩家 (支持 "players" 和 "PLAYER_POSITION")
        # 录制数据格式: PLAYER_POSITION = [{...}, ...] 或 {"1": {...}, ...}
        # ============================================================
        player_data = payload.get("players") or payload.get("PLAYER_POSITION")
        if player_data is not None:
            self.current_state.mark_channel_updated(
                "PLAYER_POSITION", self.current_state.frame
            )

            # 支持列表格式 [{...}, ...]
            if isinstance(player_data, list):
                for idx, pdata in enumerate(player_data):
                    if not isinstance(pdata, dict):
                        continue

                    pos = self.parser.parse_vector2d(pdata.get("pos"))
                    vel = self.parser.parse_vector2d(pdata.get("vel"))

                    # 创建或更新玩家
                    player_idx = idx + 1
                    if player_idx not in self.current_state.players:
                        player_obj = PlayerData(
                            player_idx=player_idx, position=pos, velocity=vel
                        )
                        player_obj.first_seen_frame = self.current_state.frame
                    else:
                        player_obj = self.current_state.players[player_idx]
                        player_obj.position = pos
                        player_obj.velocity = vel

                    player_obj.last_seen_frame = self.current_state.frame

                    # 解析方向
                    player_obj.facing_direction = pdata.get("head_dir", 0)

                    self.current_state.players[player_idx] = player_obj

            # 支持字典格式 {"1": {...}, "2": {...}}
            elif isinstance(player_data, dict):
                for player_idx_str, pdata in player_data.items():
                    if not isinstance(pdata, dict):
                        continue

                    try:
                        player_idx = int(player_idx_str)
                    except ValueError:
                        continue

                    pos = self.parser.parse_vector2d(pdata.get("pos"))
                    vel = self.parser.parse_vector2d(pdata.get("vel"))

                    if player_idx not in self.current_state.players:
                        player_obj = PlayerData(
                            player_idx=player_idx, position=pos, velocity=vel
                        )
                        player_obj.first_seen_frame = self.current_state.frame
                    else:
                        player_obj = self.current_state.players[player_idx]
                        player_obj.position = pos
                        player_obj.velocity = vel

                    player_obj.last_seen_frame = self.current_state.frame

                    # 解析方向（支持 head_dir 或 direction）
                    player_obj.facing_direction = pdata.get(
                        "head_dir", pdata.get("direction", 0)
                    )

                    self.current_state.players[player_idx] = player_obj

        # ============================================================
        # 解析敌人 (支持 "enemies" 和 "ENEMIES")
        # 录制数据格式: ENEMIES = [{...}, ...] 或 {"id": {...}, ...}
        # ============================================================
        enemy_data = payload.get("enemies") or payload.get("ENEMIES")
        if enemy_data is not None:
            self.current_state.mark_channel_updated("ENEMIES", self.current_state.frame)

            # 支持列表格式 [{...}, ...]
            if isinstance(enemy_data, list):
                for enemy_dict in enemy_data:
                    if not isinstance(enemy_dict, dict):
                        continue

                    try:
                        enemy_id = enemy_dict.get("id")
                        if enemy_id is None:
                            continue

                        enemy = EnemyData(enemy_id=enemy_id)
                        enemy.position = self.parser.parse_vector2d(
                            enemy_dict.get("pos")
                        )
                        enemy.velocity = self.parser.parse_vector2d(
                            enemy_dict.get("vel")
                        )
                        enemy.enemy_type = enemy_dict.get("type", 0)
                        enemy.hp = enemy_dict.get("hp", 10.0)
                        enemy.max_hp = enemy_dict.get("max_hp", 10.0)
                        enemy.damage = enemy_dict.get("damage", 1.0)
                        enemy.is_boss = enemy_dict.get("is_boss", False)
                        enemy.is_champion = enemy_dict.get("is_champion", False)
                        enemy.is_flying = enemy_dict.get("is_flying", False)

                        # 根据状态判断是否在攻击
                        state = enemy_dict.get("state", 1)
                        enemy.is_attacking = state in [2, 3]

                        if enemy_id not in self.current_state.enemies:
                            enemy.first_seen_frame = self.current_state.frame
                        enemy.last_seen_frame = self.current_state.frame
                        self.current_state.enemies[enemy_id] = enemy
                    except (ValueError, TypeError, KeyError):
                        pass

            # 支持字典格式 {"id": {...}, ...}
            elif isinstance(enemy_data, dict):
                for enemy_id_str, enemy_dict in enemy_data.items():
                    if not isinstance(enemy_dict, dict):
                        continue

                    try:
                        enemy_id = int(enemy_id_str)
                    except ValueError:
                        enemy_id = enemy_dict.get("id")
                        if enemy_id is None:
                            continue

                    try:
                        enemy = EnemyData(enemy_id=enemy_id)
                        enemy.position = self.parser.parse_vector2d(
                            enemy_dict.get("pos")
                        )
                        enemy.velocity = self.parser.parse_vector2d(
                            enemy_dict.get("vel")
                        )
                        enemy.enemy_type = enemy_dict.get("type", 0)
                        enemy.hp = enemy_dict.get("hp", 10.0)
                        enemy.max_hp = enemy_dict.get("max_hp", 10.0)
                        enemy.damage = enemy_dict.get("damage", 1.0)
                        enemy.is_boss = enemy_dict.get("is_boss", False)
                        enemy.is_champion = enemy_dict.get("is_champion", False)
                        enemy.is_flying = enemy_dict.get("is_flying", False)

                        # 根据状态判断是否在攻击
                        state = enemy_dict.get("state", 1)
                        enemy.is_attacking = state in [2, 3]

                        if enemy_id not in self.current_state.enemies:
                            enemy.first_seen_frame = self.current_state.frame
                        enemy.last_seen_frame = self.current_state.frame
                        self.current_state.enemies[enemy_id] = enemy
                    except (ValueError, TypeError, KeyError):
                        pass

        # ============================================================
        # 解析投射物 (支持 "projectiles" 和 "PROJECTILES")
        # 录制数据格式: PROJECTILES = {enemy_projectiles: [...], player_tears: [...]}
        # 或直接格式 {"id": {...}, ...} (测试数据格式)
        # ============================================================
        proj_data = payload.get("projectiles") or payload.get("PROJECTILES")
        if proj_data is not None and isinstance(proj_data, dict):
            self.current_state.mark_channel_updated(
                "PROJECTILES", self.current_state.frame
            )

            # 检测是否是直接格式 {"id": {...}, ...}
            first_key = next(iter(proj_data.keys())) if proj_data else None
            if (
                first_key is not None
                and not isinstance(proj_data[first_key], dict)
                or first_key not in ("enemy_projectiles", "player_tears", "lasers")
            ):
                # 直接格式：{"100": {...}, "101": {...}}
                for proj_id_str, proj_dict in proj_data.items():
                    if not isinstance(proj_dict, dict):
                        continue

                    try:
                        proj_id = int(proj_id_str)
                    except ValueError:
                        proj_id = proj_dict.get("id")
                        if proj_id is None:
                            continue

                    try:
                        proj = ProjectileData(projectile_id=proj_id)
                        proj.position = self.parser.parse_vector2d(proj_dict.get("pos"))
                        proj.velocity = self.parser.parse_vector2d(proj_dict.get("vel"))
                        proj.projectile_type = proj_dict.get(
                            "variant", proj_dict.get("type", 0)
                        )
                        proj.damage = proj_dict.get("damage", 1.0)
                        proj.size = proj_dict.get(
                            "collision_radius", proj_dict.get("size", 5.0)
                        )
                        proj.is_enemy = proj_dict.get("is_enemy", True)

                        if proj_id not in self.current_state.projectiles:
                            proj.first_seen_frame = self.current_state.frame
                        proj.last_seen_frame = self.current_state.frame
                        self.current_state.projectiles[proj_id] = proj
                    except (ValueError, TypeError, KeyError):
                        pass
            else:
                # 标准格式：{enemy_projectiles: [...], player_tears: [...]}
                # 解析敌人投射物
                enemy_projs = proj_data.get("enemy_projectiles", [])
                if isinstance(enemy_projs, list):
                    for proj_dict in enemy_projs:
                        if not isinstance(proj_dict, dict):
                            continue

                        try:
                            proj_id = proj_dict.get("id")
                            if proj_id is None:
                                continue

                            proj = ProjectileData(projectile_id=proj_id)
                            proj.position = self.parser.parse_vector2d(
                                proj_dict.get("pos")
                            )
                            proj.velocity = self.parser.parse_vector2d(
                                proj_dict.get("vel")
                            )
                            proj.projectile_type = proj_dict.get("variant", 0)
                            proj.damage = proj_dict.get("damage", 1.0)
                            proj.size = proj_dict.get("collision_radius", 5.0)
                            proj.is_enemy = True

                            if proj_id not in self.current_state.projectiles:
                                proj.first_seen_frame = self.current_state.frame
                            proj.last_seen_frame = self.current_state.frame
                            self.current_state.projectiles[proj_id] = proj
                        except (ValueError, TypeError, KeyError):
                            pass

                # 解析玩家眼泪
                player_tears = proj_data.get("player_tears", [])
                if isinstance(player_tears, list):
                    for proj_dict in player_tears:
                        if not isinstance(proj_dict, dict):
                            continue

                        try:
                            proj_id = proj_dict.get("id")
                            if proj_id is None:
                                continue

                            proj = ProjectileData(projectile_id=proj_id)
                            proj.position = self.parser.parse_vector2d(
                                proj_dict.get("pos")
                            )
                            proj.velocity = self.parser.parse_vector2d(
                                proj_dict.get("vel")
                            )
                            proj.projectile_type = proj_dict.get("variant", 0)
                            proj.damage = proj_dict.get("damage", 1.0)
                            proj.size = proj_dict.get("collision_radius", 5.0)
                            proj.is_enemy = False

                            if proj_id not in self.current_state.projectiles:
                                proj.first_seen_frame = self.current_state.frame
                            proj.last_seen_frame = self.current_state.frame
                            self.current_state.projectiles[proj_id] = proj
                        except (ValueError, TypeError, KeyError):
                            pass

        # ============================================================
        # 解析房间信息 (支持 "room", "ROOM" 和 "ROOM_INFO")
        # ============================================================
        # 解析房间信息 (支持 "room", "ROOM" 和 "ROOM_INFO")
        # 录制数据格式: ROOM_INFO = {room_index, stage, room_type, is_clear, enemy_count, ...}
        # ============================================================
        room_data = (
            payload.get("room") or payload.get("ROOM") or payload.get("ROOM_INFO")
        )
        if room_data is not None and isinstance(room_data, dict):
            self.current_state.mark_channel_updated(
                "ROOM_INFO", self.current_state.frame
            )

            room_info = RoomInfo()
            room_info.room_index = room_data.get("room_index", -1)
            room_info.stage = room_data.get("stage", 1)
            room_info.stage_type = room_data.get("stage_type", 0)
            room_info.difficulty = room_data.get("difficulty", 0)
            room_info.grid_width = room_data.get("grid_width", 13)
            room_info.grid_height = room_data.get("grid_height", 7)
            room_info.pixel_width = room_data.get("pixel_width", 0)
            room_info.pixel_height = room_data.get("pixel_height", 0)

            # 解析房间边界坐标（top_left 和 bottom_right）
            # 这些值用于正确的世界坐标到网格坐标转换
            # 来源: python/analyzed_rooms/ROOM_GEOMETRY_BY_SESSION.md
            top_left = room_data.get("top_left")
            if top_left and isinstance(top_left, dict):
                room_info.top_left = (top_left.get("x", 0.0), top_left.get("y", 0.0))

            bottom_right = room_data.get("bottom_right")
            if bottom_right and isinstance(bottom_right, dict):
                room_info.bottom_right = (
                    bottom_right.get("x", 0.0),
                    bottom_right.get("y", 0.0),
                )

            room_info.room_type = room_data.get("room_type", "normal")
            room_info.room_shape = room_data.get("room_shape", 0)
            room_info.is_clear = room_data.get("is_clear", False)
            room_info.enemy_count = room_data.get("enemy_count", 0)
            self.current_state.room_info = room_info

        # ============================================================
        # 存储原始ROOM_LAYOUT数据（用于L型房间支持）
        # ============================================================
        layout_data = payload.get("ROOM_LAYOUT") or payload.get("room_layout")
        if layout_data is not None and isinstance(layout_data, dict):
            self.current_state.mark_channel_updated(
                "ROOM_LAYOUT", self.current_state.frame
            )
            self.current_state.raw_room_layout = layout_data

        # ============================================================
        # 解析PLAYER_HEALTH（玩家生命值）
        # 格式: {"1": {"red_hearts": 3, "max_hearts": 6, ...}, ...}
        # ============================================================
        health_data = payload.get("PLAYER_HEALTH") or payload.get("player_health")
        if health_data is not None and isinstance(health_data, dict):
            self.current_state.mark_channel_updated(
                "PLAYER_HEALTH", self.current_state.frame
            )
            for player_idx_str, hdata in health_data.items():
                if not isinstance(hdata, dict):
                    continue
                try:
                    player_idx = int(player_idx_str)
                except ValueError:
                    continue

                health = PlayerHealthData(player_idx=player_idx)
                health.red_hearts = hdata.get("red_hearts", 0)
                health.max_red_hearts = hdata.get("max_hearts", 0)
                health.soul_hearts = hdata.get("soul_hearts", 0)
                health.black_hearts = hdata.get("black_hearts", 0)
                health.bone_hearts = hdata.get("bone_hearts", 0)
                health.golden_hearts = hdata.get("golden_hearts", 0)
                health.eternal_hearts = hdata.get("eternal_hearts", 0)
                health.rotten_hearts = hdata.get("rotten_hearts", 0)
                health.broken_hearts = hdata.get("broken_hearts", 0)
                health.extra_lives = hdata.get("extra_lives", 0)
                self.current_state.player_health[player_idx] = health

        # ============================================================
        # 解析PLAYER_STATS（玩家属性）
        # 格式: {"1": {"player_type": 0, "damage": 3.5, "speed": 1.0, ...}, ...}
        # ============================================================
        stats_data = payload.get("PLAYER_STATS") or payload.get("player_stats")
        if stats_data is not None and isinstance(stats_data, dict):
            self.current_state.mark_channel_updated(
                "PLAYER_STATS", self.current_state.frame
            )
            for player_idx_str, sdata in stats_data.items():
                if not isinstance(sdata, dict):
                    continue
                try:
                    player_idx = int(player_idx_str)
                except ValueError:
                    continue

                stats = PlayerStatsData(player_idx=player_idx)
                stats.player_type = sdata.get("player_type", 0)
                stats.damage = sdata.get("damage", 3.0)
                stats.speed = sdata.get("speed", 1.0)
                stats.tears = sdata.get("tears", sdata.get("tears_delay", 10.0))
                stats.tear_range = sdata.get("tear_range", sdata.get("range", 300.0))
                stats.shot_speed = sdata.get("shot_speed", 1.0)
                stats.luck = sdata.get("luck", 0)
                stats.can_fly = sdata.get("can_fly", False)
                stats.size = sdata.get("size", 10.0)
                stats.active_item = sdata.get("active_item")
                stats.active_charge = sdata.get("active_charge", 0)
                stats.max_charge = sdata.get("max_charge", 0)
                self.current_state.player_stats[player_idx] = stats

        # ============================================================
        # 解析BUTTONS（按钮）
        # 格式: {"0": {"type": 18, "variant_name": "NORMAL", ...}, ...}
        # ============================================================
        buttons_data = payload.get("BUTTONS") or payload.get("buttons")
        if buttons_data is not None and isinstance(buttons_data, dict):
            self.current_state.mark_channel_updated("BUTTONS", self.current_state.frame)
            for btn_idx_str, bdata in buttons_data.items():
                if not isinstance(bdata, dict):
                    continue
                try:
                    btn_idx = int(btn_idx_str)
                except ValueError:
                    continue

                pos = self.parser.parse_vector2d(bdata.get("pos"))
                btn = ButtonData(
                    button_id=btn_idx,
                    position=pos,
                )
                btn.button_type = bdata.get("type", 0)
                btn.variant = bdata.get("variant", 0)
                btn.variant_name = bdata.get("variant_name", "NORMAL")
                btn.state = bdata.get("state", 0)
                btn.is_pressed = bdata.get("is_pressed", False)
                btn.distance = bdata.get("distance", 0.0)
                btn.last_seen_frame = self.current_state.frame
                self.current_state.buttons[btn_idx] = btn

        # ============================================================
        # 解析FIRE_HAZARDS（火焰危险物）
        # 格式: [{"id": 60, "type": "FIREPLACE", ...}, ...]
        # ============================================================
        fire_data = payload.get("FIRE_HAZARDS") or payload.get("fire_hazards")
        if fire_data is not None and isinstance(fire_data, list):
            self.current_state.mark_channel_updated(
                "FIRE_HAZARDS", self.current_state.frame
            )
            for fdata in fire_data:
                if not isinstance(fdata, dict):
                    continue
                fire_id = fdata.get("id")
                if fire_id is None:
                    continue

                pos = self.parser.parse_vector2d(fdata.get("pos"))
                fire = FireHazardData(
                    fire_id=fire_id,
                    position=pos,
                )
                fire.fire_type = fdata.get(
                    "fireplace_type", fdata.get("type", "NORMAL")
                )
                fire.variant = fdata.get("variant", 0)
                fire.hp = fdata.get("hp", 10.0)
                fire.max_hp = fdata.get("max_hp", 10.0)
                fire.is_extinguished = fdata.get("is_extinguished", False)
                fire.is_shooting = fdata.get("is_shooting", False)
                fire.collision_radius = fdata.get("collision_radius", 25.0)
                fire.last_seen_frame = self.current_state.frame
                self.current_state.fire_hazards[fire_id] = fire

        # ============================================================
        # 解析INTERACTABLES（可互动实体）
        # 格式: [{"id": 40, "variant_name": "SLOT_MACHINE", ...}, ...]
        # ============================================================
        interact_data = payload.get("INTERACTABLES") or payload.get("interactables")
        if interact_data is not None and isinstance(interact_data, list):
            self.current_state.mark_channel_updated(
                "INTERACTABLES", self.current_state.frame
            )
            for idata in interact_data:
                if not isinstance(idata, dict):
                    continue
                entity_id = idata.get("id")
                if entity_id is None:
                    continue

                pos = self.parser.parse_vector2d(idata.get("pos"))
                entity = InteractableData(
                    entity_id=entity_id,
                    position=pos,
                )
                entity.entity_type = idata.get("type", 0)
                entity.variant = idata.get("variant", 0)
                entity.variant_name = idata.get("variant_name", "UNKNOWN")
                entity.sub_type = idata.get("sub_type", 0)
                entity.state = idata.get("state", 0)
                entity.state_frame = idata.get("state_frame", 0)
                entity.last_seen_frame = self.current_state.frame
                self.current_state.interactables[entity_id] = entity

        # ============================================================
        # 解析PICKUPS（可拾取物）
        # 格式: [{"id": 50, "variant": 20, ...}, ...]
        # ============================================================
        pickups_data = payload.get("PICKUPS") or payload.get("pickups")
        if pickups_data is not None and isinstance(pickups_data, list):
            self.current_state.mark_channel_updated("PICKUPS", self.current_state.frame)
            for pdata in pickups_data:
                if not isinstance(pdata, dict):
                    continue
                pickup_id = pdata.get("id")
                if pickup_id is None:
                    continue

                pos = self.parser.parse_vector2d(pdata.get("pos"))
                pickup = PickupData(
                    pickup_id=pickup_id,
                    position=pos,
                )
                pickup.variant = pdata.get("variant", 0)
                pickup.sub_type = pdata.get("sub_type", 0)
                pickup.pickup_type = pdata.get("variant", 0)
                pickup.is_shop_item = pdata.get("shop_item_id", -1) >= 0
                pickup.price = pdata.get("price", 0)
                pickup.last_seen_frame = self.current_state.frame
                self.current_state.pickups[pickup_id] = pickup

        # ============================================================
        # 解析BOMBS（炸弹）
        # 格式: [{"id": 30, "variant_name": "NORMAL", ...}, ...]
        # ============================================================
        bombs_data = payload.get("BOMBS") or payload.get("bombs")
        if bombs_data is not None and isinstance(bombs_data, list):
            self.current_state.mark_channel_updated("BOMBS", self.current_state.frame)
            for bdata in bombs_data:
                if not isinstance(bdata, dict):
                    continue
                bomb_id = bdata.get("id")
                if bomb_id is None:
                    continue

                pos = self.parser.parse_vector2d(bdata.get("pos"))
                vel = self.parser.parse_vector2d(bdata.get("vel"))
                bomb = BombData(
                    bomb_id=bomb_id,
                    position=pos,
                    velocity=vel,
                )
                bomb.timer = bdata.get("timer", 90)
                bomb.radius = bdata.get("explosion_radius", 100.0)
                bomb.damage = bdata.get("damage", 100.0)
                bomb.is_player_bomb = True
                bomb.last_seen_frame = self.current_state.frame
                self.current_state.bombs[bomb_id] = bomb

        # ============================================================
        # 解析DESTRUCTIBLES（可破坏物）
        # 格式: [{"id": 70, "type": 9, "variant": 0, ...}, ...]
        # ============================================================
        destructibles_data = payload.get("DESTRUCTIBLES") or payload.get(
            "destructibles"
        )
        if destructibles_data is not None and isinstance(destructibles_data, list):
            self.current_state.mark_channel_updated(
                "DESTRUCTIBLES", self.current_state.frame
            )
            for ddata in destructibles_data:
                if not isinstance(ddata, dict):
                    continue
                obj_id = ddata.get("id")
                if obj_id is None:
                    continue

                pos = self.parser.parse_vector2d(ddata.get("pos"))
                destructible = DestructibleData(
                    obj_id=obj_id,
                    position=pos,
                )
                destructible.obj_type = ddata.get("type", 0)
                destructible.variant = ddata.get("variant", 0)
                destructible.hp = ddata.get("hp", ddata.get("health", 1))
                destructible.last_seen_frame = self.current_state.frame
                self.current_state.obstacles[obj_id] = destructible

        # ============================================================
        # 清理过期实体（状态保持的一部分）
        # ============================================================
        self.current_state.cleanup_stale_entities(self.current_state.frame)

        return self.current_state

    def _process_event(self, message: Dict[str, Any]):
        """处理EVENT消息"""
        event_type = message.get("event_type", "UNKNOWN")
        event_data = message.get("event_data", {})

        logger.debug(f"Event: {event_type}, Data: {event_data}")

        # 根据事件类型更新状态
        if event_type == "ROOM_ENTERED":
            # 进入新房间，清除敌人状态
            for enemy in self.current_state.enemies.values():
                enemy.state = ObjectState.DEAD

        elif event_type == "PLAYER_DAMAGED":
            # 玩家受伤，更新玩家血量
            player = self.current_state.get_primary_player()
            if player and "damage" in event_data:
                player.health -= event_data["damage"]

        elif event_type == "ENEMY_KILLED":
            # 敌人死亡
            enemy_id = event_data.get("enemy_id")
            if enemy_id and enemy_id in self.current_state.enemies:
                self.current_state.enemies[enemy_id].state = ObjectState.DEAD

    def _process_full_state(self, message: Dict[str, Any]) -> GameStateData:
        """处理FULL状态消息（全量更新）"""
        # 清空当前状态
        self.current_state = GameStateData()

        # 重新处理
        return self._process_data_message(message)

    def get_game_state(self) -> GameStateData:
        """获取当前游戏状态"""
        return self.current_state

    def get_primary_player(self) -> Optional[PlayerData]:
        """获取主玩家"""
        return self.current_state.get_primary_player()

    def get_active_enemies(self) -> List[EnemyData]:
        """获取活跃敌人"""
        return self.current_state.active_enemies

    def get_enemy_projectiles(self) -> List[ProjectileData]:
        """获取敌人投射物"""
        return self.current_state.enemy_projectiles

    def reset(self):
        """重置状态"""
        self.current_state = GameStateData()


def create_data_processor() -> DataProcessor:
    """创建数据处理器实例"""
    return DataProcessor()
