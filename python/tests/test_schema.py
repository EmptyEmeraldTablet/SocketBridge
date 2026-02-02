"""
Schema Tests - Pydantic 模式验证测试

测试内容：
1. 基础类型验证（Vector2D）
2. 玩家数据模式验证
3. 敌人数据模式验证
4. 消息模式验证
5. 边界条件和错误处理
"""

import pytest
import json
from pathlib import Path

# 添加路径
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.protocol.schema import (
    Vector2DSchema,
    PlayerPositionData,
    PlayerStatsData,
    PlayerHealthData,
    EnemyData,
    ProjectileData,
    RoomInfoData,
    DataMessageSchema,
    EventMessageSchema,
    MessageType,
    ChannelMeta,
    ChannelMeta,
    CollectInterval,
)
from pydantic import ValidationError


# ==================== Fixtures ====================

@pytest.fixture
def sample_data():
    """加载测试数据"""
    fixtures_path = Path(__file__).parent / "fixtures" / "sample_messages.json"
    with open(fixtures_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ==================== Vector2D Tests ====================

class TestVector2DSchema:
    """Vector2D 模式测试"""
    
    def test_valid_vector(self):
        """测试有效向量"""
        v = Vector2DSchema(x=1.5, y=-2.3)
        assert v.x == 1.5
        assert v.y == -2.3
    
    def test_integer_coords(self):
        """测试整数坐标（自动转换为浮点）"""
        v = Vector2DSchema(x=1, y=2)
        assert isinstance(v.x, float)
        assert isinstance(v.y, float)
    
    def test_zero_vector(self):
        """测试零向量"""
        v = Vector2DSchema(x=0, y=0)
        assert v.x == 0.0
        assert v.y == 0.0
    
    def test_invalid_type(self):
        """测试无效类型"""
        with pytest.raises(ValidationError):
            Vector2DSchema(x="invalid", y=1.0)


# ==================== Player Data Tests ====================

class TestPlayerPositionData:
    """玩家位置数据测试"""
    
    def test_valid_position(self, sample_data):
        """测试有效玩家位置"""
        raw = sample_data["player_position_samples"]["valid_single_player"]["1"]
        data = PlayerPositionData(
            pos=Vector2DSchema(**raw["pos"]),
            vel=Vector2DSchema(**raw["vel"]),
            move_dir=raw["move_dir"],
            fire_dir=raw["fire_dir"],
            head_dir=raw["head_dir"],
            aim_dir=Vector2DSchema(**raw["aim_dir"]),
        )
        assert data.pos.x == 320.5
        assert data.vel.y == -0.5
        assert data.move_dir == 2
    
    def test_aim_dir_zero(self, sample_data):
        """测试 aim_dir 为零的情况（已知游戏问题）"""
        raw = sample_data["player_position_samples"]["aim_dir_zero"]["1"]
        data = PlayerPositionData(
            pos=Vector2DSchema(**raw["pos"]),
            vel=Vector2DSchema(**raw["vel"]),
            move_dir=raw["move_dir"],
            fire_dir=raw["fire_dir"],
            head_dir=raw["head_dir"],
            aim_dir=Vector2DSchema(**raw["aim_dir"]),
        )
        assert data.aim_dir.x == 0.0
        assert data.aim_dir.y == 0.0
    
    def test_direction_bounds(self):
        """测试方向值边界"""
        # 有效范围 -1 到 7
        data = PlayerPositionData(
            pos=Vector2DSchema(x=0, y=0),
            vel=Vector2DSchema(x=0, y=0),
            move_dir=-1,
            fire_dir=7,
            head_dir=0,
            aim_dir=Vector2DSchema(x=0, y=0),
        )
        assert data.move_dir == -1
        assert data.fire_dir == 7


class TestPlayerStatsData:
    """玩家属性数据测试"""
    
    def test_valid_stats(self):
        """测试有效属性"""
        data = PlayerStatsData(
            player_type=0,
            damage=3.5,
            speed=1.0,
            tears=10.0,
            range=350.0,
        )
        assert data.damage == 3.5
        assert data.speed == 1.0
    
    def test_luck_float_to_int(self):
        """测试 luck 浮点转整数（已知问题）"""
        data = PlayerStatsData(
            player_type=0,
            damage=3.5,
            speed=1.0,
            luck=2.5,  # 浮点数
        )
        assert data.luck == 2  # 应转为整数
        assert isinstance(data.luck, int)
    
    def test_default_values(self):
        """测试默认值"""
        data = PlayerStatsData(
            player_type=0,
            damage=3.5,
            speed=1.0,
        )
        assert data.tears == 10.0
        assert data.can_fly == False


class TestPlayerHealthData:
    """玩家生命值数据测试"""
    
    def test_valid_health(self):
        """测试有效生命值"""
        data = PlayerHealthData(
            red_hearts=6,
            max_hearts=6.0,
            soul_hearts=2,
        )
        assert data.red_hearts == 6
        assert data.soul_hearts == 2
    
    def test_total_hearts(self):
        """测试总生命计算"""
        data = PlayerHealthData(
            red_hearts=6,
            max_hearts=6.0,
            soul_hearts=4,
            black_hearts=2,
        )
        # 6 + 4*0.5 + 2*0.5 = 6 + 2 + 1 = 9
        assert data.total_hearts == 9.0


# ==================== Enemy Data Tests ====================

class TestEnemyData:
    """敌人数据测试"""
    
    def test_normal_enemy(self, sample_data):
        """测试普通敌人"""
        raw = sample_data["enemy_samples"]["normal_enemy"]
        data = EnemyData(
            id=raw["id"],
            type=raw["type"],
            pos=Vector2DSchema(**raw["pos"]),
            vel=Vector2DSchema(**raw["vel"]),
            hp=raw["hp"],
            max_hp=raw["max_hp"],
        )
        assert data.hp == 15.0
        assert data.is_boss == False
    
    def test_boss_enemy(self, sample_data):
        """测试 Boss 敌人"""
        raw = sample_data["enemy_samples"]["boss_enemy"]
        data = EnemyData(
            id=raw["id"],
            type=raw["type"],
            pos=Vector2DSchema(**raw["pos"]),
            vel=Vector2DSchema(**raw["vel"]),
            hp=raw["hp"],
            max_hp=raw["max_hp"],
            is_boss=raw["is_boss"],
        )
        assert data.is_boss == True
        assert data.hp == 250.0


# ==================== Message Schema Tests ====================

class TestDataMessageSchema:
    """数据消息模式测试"""
    
    def test_v21_message(self, sample_data):
        """测试 v2.1 消息格式"""
        raw = sample_data["data_message_v21"]
        # 需要预处理 channel_meta，因为 DataMessageSchema 期望 ChannelMeta 对象
        msg_data = {**raw}
        if "channel_meta" in msg_data and msg_data["channel_meta"]:
            msg_data["channel_meta"] = {
                k: ChannelMeta(**v) for k, v in msg_data["channel_meta"].items()
            }
        msg = DataMessageSchema(**msg_data)
        
        assert msg.version == "2.1"
        assert msg.type == MessageType.DATA
        assert msg.seq == 50
        assert msg.prev_frame == 99
        assert "PLAYER_POSITION" in msg.channel_meta
    
    def test_v20_message_backward_compatible(self, sample_data):
        """测试 v2.0 消息向后兼容"""
        raw = sample_data["data_message_v20"]
        msg = DataMessageSchema(**raw)
        
        assert msg.version == "2.0"
        assert msg.seq is None  # v2.0 没有 seq
        assert msg.channel_meta is None
    
    def test_channel_meta_parsing(self, sample_data):
        """测试通道元数据解析"""
        raw = sample_data["data_message_v21"]
        msg_data = {**raw}
        if "channel_meta" in msg_data and msg_data["channel_meta"]:
            msg_data["channel_meta"] = {
                k: ChannelMeta(**v) for k, v in msg_data["channel_meta"].items()
            }
        msg = DataMessageSchema(**msg_data)
        
        player_meta = msg.channel_meta["PLAYER_POSITION"]
        assert player_meta.collect_frame == 100
        assert player_meta.interval == "HIGH"
        
        stats_meta = msg.channel_meta["PLAYER_STATS"]
        assert stats_meta.stale_frames == 10


class TestEventMessageSchema:
    """事件消息模式测试"""
    
    def test_event_message(self, sample_data):
        """测试事件消息"""
        raw = sample_data["event_message"]
        msg = EventMessageSchema(**raw)
        
        assert msg.type == MessageType.EVENT
        assert msg.event == "PLAYER_DAMAGE"
        assert msg.data["damage"] == 1.0


# ==================== Room Data Tests ====================

class TestRoomInfoData:
    """房间信息数据测试"""
    
    def test_valid_room_info(self, sample_data):
        """测试有效房间信息"""
        raw = sample_data["room_info_sample"]
        data = RoomInfoData(
            room_type=raw["room_type"],
            room_shape=raw["room_shape"],
            room_idx=raw["room_idx"],
            stage=raw["stage"],
            grid_width=raw["grid_width"],
            grid_height=raw["grid_height"],
            top_left=Vector2DSchema(**raw["top_left"]),
            bottom_right=Vector2DSchema(**raw["bottom_right"]),
            is_clear=raw["is_clear"],
        )
        assert data.room_idx == 5
        assert data.is_clear == True
        assert data.grid_width == 15


# ==================== Run Tests ====================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
