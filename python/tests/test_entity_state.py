"""
Tests for services.entity_state module - 实体状态管理模块测试

包括：
- EntityStateManager 单元测试
- GameEntityState 单元测试
- 使用录制数据的集成测试
"""

import pytest
import sys
from pathlib import Path
from typing import Dict, Any, List

# 确保可以导入模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.entity_state import (
    EntityStateManager,
    EntityStateConfig,
    TrackedEntity,
    GameEntityState,
)
from services.facade import SocketBridgeFacade, BridgeConfig
from core.replay import DataReplayer, ReplayerConfig, list_sessions


# ============================================================================
# EntityStateManager 单元测试
# ============================================================================


class TestEntityStateConfig:
    """EntityStateConfig 测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = EntityStateConfig()
        assert config.expiry_frames == 60
        assert config.auto_expire_enabled is True

    def test_disable_auto_expire(self):
        """测试禁用自动过期"""
        config = EntityStateConfig(expiry_frames=-1)
        assert config.auto_expire_enabled is False

        config2 = EntityStateConfig(expiry_frames=0)
        assert config2.auto_expire_enabled is False

        config3 = EntityStateConfig(expiry_frames=None)
        assert config3.auto_expire_enabled is False


class TestEntityStateManager:
    """EntityStateManager 测试"""

    def test_create_manager(self):
        """测试创建管理器"""
        manager = EntityStateManager(
            name="TEST",
            config=EntityStateConfig(expiry_frames=10),
            id_getter=lambda x: x["id"],
        )
        assert manager.name == "TEST"
        assert manager.count() == 0

    def test_update_add_entities(self):
        """测试添加实体"""
        manager = EntityStateManager(
            name="TEST",
            config=EntityStateConfig(expiry_frames=10),
            id_getter=lambda x: x["id"],
        )

        entities = [{"id": 1, "hp": 100}, {"id": 2, "hp": 80}]
        changes = manager.update(entities, frame=100)

        assert changes["added"] == [1, 2]
        assert changes["updated"] == []
        assert changes["removed"] == []
        assert manager.count() == 2

    def test_update_existing_entities(self):
        """测试更新现有实体"""
        manager = EntityStateManager(
            name="TEST",
            config=EntityStateConfig(expiry_frames=10),
            id_getter=lambda x: x["id"],
        )

        # 第一次更新
        manager.update([{"id": 1, "hp": 100}], frame=100)

        # 第二次更新（更新现有实体）
        changes = manager.update([{"id": 1, "hp": 50}], frame=105)

        assert changes["added"] == []
        assert changes["updated"] == [1]
        assert changes["removed"] == []

        # 验证数据已更新
        entity = manager.get(1)
        assert entity["hp"] == 50

    def test_entity_expiry(self):
        """测试实体过期"""
        manager = EntityStateManager(
            name="TEST",
            config=EntityStateConfig(expiry_frames=10),
            id_getter=lambda x: x["id"],
        )

        # 添加两个实体
        manager.update([{"id": 1}, {"id": 2}], frame=100)
        assert manager.count() == 2

        # 帧 105：只更新实体 1
        manager.update([{"id": 1}], frame=105)
        assert manager.count() == 2  # 实体 2 还没过期

        # 帧 115：实体 2 应该过期（100 + 10 = 110 < 115）
        changes = manager.update([{"id": 1}], frame=115)
        assert 2 in changes["removed"]
        assert manager.count() == 1

    def test_disable_expiry(self):
        """测试禁用过期"""
        manager = EntityStateManager(
            name="TEST",
            config=EntityStateConfig(expiry_frames=-1),  # 禁用过期
            id_getter=lambda x: x["id"],
        )

        # 添加两个实体
        manager.update([{"id": 1}, {"id": 2}], frame=100)

        # 过了很多帧，只更新实体 1
        manager.update([{"id": 1}], frame=10000)

        # 实体 2 仍然存在（不会过期）
        assert manager.count() == 2
        assert manager.get(2) is not None

    def test_get_fresh(self):
        """测试获取新鲜实体"""
        manager = EntityStateManager(
            name="TEST",
            config=EntityStateConfig(expiry_frames=60),
            id_getter=lambda x: x["id"],
        )

        manager.update([{"id": 1}, {"id": 2}], frame=100)
        manager.update([{"id": 1}], frame=110)  # 只更新实体 1

        # 获取最近 5 帧内的实体
        fresh = manager.get_fresh(max_stale_frames=5)
        assert len(fresh) == 1
        assert fresh[0]["id"] == 1

        # 获取最近 15 帧内的实体
        fresh2 = manager.get_fresh(max_stale_frames=15)
        assert len(fresh2) == 2

    def test_get_active_with_disabled_expiry(self):
        """测试禁用过期时 get_active 返回所有实体"""
        manager = EntityStateManager(
            name="TEST",
            config=EntityStateConfig(expiry_frames=-1),
            id_getter=lambda x: x["id"],
        )

        manager.update([{"id": 1}, {"id": 2}], frame=100)
        manager.update([{"id": 1}], frame=1000)

        # 即使不传参数也应返回所有实体
        active = manager.get_active()
        assert len(active) == 2

    def test_tracked_entity_metadata(self):
        """测试跟踪实体元数据"""
        manager = EntityStateManager(
            name="TEST",
            config=EntityStateConfig(expiry_frames=60),
            id_getter=lambda x: x["id"],
        )

        manager.update([{"id": 1}], frame=100)
        manager.update([{"id": 1}], frame=110)
        manager.update([{"id": 1}], frame=120)

        tracked = manager.get_tracked(1)
        assert tracked is not None
        assert tracked.first_seen_frame == 100
        assert tracked.last_seen_frame == 120
        assert tracked.update_count == 3
        assert tracked.age == 20

    def test_entity_staleness(self):
        """测试实体陈旧度"""
        manager = EntityStateManager(
            name="TEST",
            config=EntityStateConfig(expiry_frames=60),
            id_getter=lambda x: x["id"],
        )

        manager.update([{"id": 1}], frame=100)
        manager.update([], frame=110)  # 空更新，推进帧号

        staleness = manager.get_entity_staleness(1)
        assert staleness == 10

    def test_clear(self):
        """测试清空"""
        manager = EntityStateManager(
            name="TEST",
            config=EntityStateConfig(expiry_frames=60),
            id_getter=lambda x: x["id"],
        )

        manager.update([{"id": 1}, {"id": 2}], frame=100)
        assert manager.count() == 2

        manager.clear()
        assert manager.count() == 0

    def test_stats(self):
        """测试统计信息"""
        manager = EntityStateManager(
            name="TEST",
            config=EntityStateConfig(expiry_frames=10),
            id_getter=lambda x: x["id"],
        )

        manager.update([{"id": 1}, {"id": 2}], frame=100)
        manager.update([{"id": 1}], frame=115)  # id=2 过期

        stats = manager.get_stats()
        assert stats["name"] == "TEST"
        assert stats["current_count"] == 1
        assert stats["total_added"] == 2
        assert stats["total_expired"] == 1


# ============================================================================
# GameEntityState 单元测试
# ============================================================================


class TestGameEntityState:
    """GameEntityState 测试"""

    def test_create_default(self):
        """测试创建默认配置"""
        state = GameEntityState()

        # 验证动态实体启用过期
        assert state.enemies.config.auto_expire_enabled is True
        assert state.enemy_projectiles.config.auto_expire_enabled is True
        assert state.pickups.config.auto_expire_enabled is True
        assert state.bombs.config.auto_expire_enabled is True

        # 验证静态实体禁用过期
        assert state.grid_entities.config.auto_expire_enabled is False

    def test_update_enemies(self):
        """测试更新敌人"""
        state = GameEntityState()

        enemies = [
            {"id": 1, "hp": 100, "pos": {"x": 100, "y": 100}},
            {"id": 2, "hp": 80, "pos": {"x": 200, "y": 200}},
        ]
        state.update_enemies(enemies, frame=100)

        result = state.get_enemies(max_stale_frames=5)
        assert len(result) == 2

    def test_update_projectiles(self):
        """测试更新投射物"""
        state = GameEntityState()

        enemy_proj = [{"id": 1, "pos": {"x": 100, "y": 100}}]
        player_tears = [{"id": 2, "pos": {"x": 200, "y": 200}}]
        lasers = [{"id": 3, "pos": {"x": 300, "y": 300}}]

        state.update_projectiles(enemy_proj, player_tears, lasers, frame=100)

        assert len(state.get_enemy_projectiles(5)) == 1
        assert len(state.get_player_tears(5)) == 1
        assert len(state.get_lasers(5)) == 1

    def test_room_change_clears_state(self):
        """测试房间切换清空状态"""
        state = GameEntityState()

        # 添加一些实体
        state.update_enemies([{"id": 1}], frame=100)
        state.update_pickups([{"id": 2}], frame=100)
        state.update_grid_entities([{"grid_index": 10}], frame=100)

        assert state.enemies.count() == 1
        assert state.pickups.count() == 1
        assert state.grid_entities.count() == 1

        # 切换房间
        state.on_room_change(new_room=5)

        # 所有状态应被清空
        assert state.enemies.count() == 0
        assert state.pickups.count() == 0
        assert state.grid_entities.count() == 0

    def test_threat_count(self):
        """测试威胁计数"""
        state = GameEntityState()

        state.update_enemies([{"id": 1}, {"id": 2}], frame=100)
        state.update_projectiles([{"id": 3}], [], [], frame=100)

        assert state.get_threat_count() == 3

    def test_grid_entities_no_expiry(self):
        """测试网格实体不过期"""
        state = GameEntityState()

        state.update_grid_entities(
            [{"grid_index": 10, "type": "rock"}, {"grid_index": 20, "type": "pit"}],
            frame=100,
        )

        # 过了很多帧
        state.update_grid_entities([{"grid_index": 10, "type": "rock"}], frame=10000)

        # grid_index=20 仍然存在
        all_grids = state.get_grid_entities()
        assert len(all_grids) == 2


# ============================================================================
# SocketBridgeFacade 集成测试
# ============================================================================


class TestSocketBridgeFacadeEntityState:
    """SocketBridgeFacade 实体状态集成测试"""

    def test_facade_with_entity_state(self):
        """测试 Facade 集成实体状态"""
        config = BridgeConfig(entity_state_enabled=True)
        facade = SocketBridgeFacade(config)

        assert facade.entity_state is not None

    def test_facade_without_entity_state(self):
        """测试 Facade 禁用实体状态"""
        config = BridgeConfig(entity_state_enabled=False)
        facade = SocketBridgeFacade(config)

        assert facade.entity_state is None

    def test_stateful_methods_exist(self):
        """测试有状态方法存在"""
        facade = SocketBridgeFacade()

        assert hasattr(facade, "get_enemies_stateful")
        assert hasattr(facade, "get_projectiles_stateful")
        assert hasattr(facade, "get_pickups_stateful")
        assert hasattr(facade, "get_bombs_stateful")
        assert hasattr(facade, "get_grid_entities_stateful")
        assert hasattr(facade, "get_threat_count")
        assert hasattr(facade, "get_entity_state_stats")


# ============================================================================
# 使用录制数据的集成测试
# ============================================================================


class TestEntityStateWithReplayData:
    """使用录制数据测试实体状态管理"""

    @pytest.fixture
    def recordings_dir(self):
        """录制数据目录 - 使用 tests/fixtures 下的测试数据"""
        return Path(__file__).parent / "fixtures"

    @pytest.fixture
    def has_recordings(self, recordings_dir):
        """检查是否有录制数据"""
        if not recordings_dir.exists():
            return False
        sessions = list(recordings_dir.glob("session_*"))
        return len(sessions) > 0

    def test_replay_with_entity_state(self, recordings_dir, has_recordings):
        """测试使用录制数据回放并更新实体状态"""
        if not has_recordings:
            pytest.skip("没有可用的录制数据")

        # 创建回放器
        config = ReplayerConfig(recordings_dir=str(recordings_dir))
        replayer = DataReplayer(config)

        # 列出会话
        sessions = list_sessions(str(recordings_dir))
        if not sessions:
            pytest.skip("没有可用的会话")

        # 加载第一个会话
        session = replayer.load_session(sessions[0].session_id)
        assert session.total_messages > 0

        # 创建实体状态管理器
        entity_state = GameEntityState()
        
        # 统计
        enemies_seen = set()
        projectiles_seen = set()
        max_enemies = 0
        max_projectiles = 0
        frames_processed = 0

        # 回放消息并更新状态
        for msg in replayer.iter_messages():
            if not msg.is_data_message:
                continue

            frame = msg.frame
            payload = msg.payload or {}
            frames_processed += 1

            # 处理敌人
            if "ENEMIES" in payload:
                enemies_data = payload["ENEMIES"]
                if isinstance(enemies_data, dict):
                    enemies_list = list(enemies_data.values())
                elif isinstance(enemies_data, list):
                    enemies_list = enemies_data
                else:
                    enemies_list = []

                for e in enemies_list:
                    if isinstance(e, dict) and "id" in e:
                        enemies_seen.add(e["id"])

                entity_state.update_enemies(enemies_list, frame)
                current_enemies = entity_state.enemies.count()
                max_enemies = max(max_enemies, current_enemies)

            # 处理投射物
            if "PROJECTILES" in payload:
                proj_data = payload["PROJECTILES"]
                enemy_proj = []
                player_tears = []
                lasers = []

                if isinstance(proj_data, dict):
                    enemy_proj = proj_data.get("enemy_projectiles", [])
                    if isinstance(enemy_proj, dict):
                        enemy_proj = list(enemy_proj.values())
                    player_tears = proj_data.get("player_tears", [])
                    if isinstance(player_tears, dict):
                        player_tears = list(player_tears.values())
                    lasers = proj_data.get("lasers", [])
                    if isinstance(lasers, dict):
                        lasers = list(lasers.values())

                for p in enemy_proj:
                    if isinstance(p, dict) and "id" in p:
                        projectiles_seen.add(("enemy", p["id"]))
                for p in player_tears:
                    if isinstance(p, dict) and "id" in p:
                        projectiles_seen.add(("tear", p["id"]))

                entity_state.update_projectiles(enemy_proj, player_tears, lasers, frame)
                current_proj = (
                    entity_state.enemy_projectiles.count()
                    + entity_state.player_tears.count()
                )
                max_projectiles = max(max_projectiles, current_proj)

            # 限制处理数量
            if frames_processed >= 500:
                break

        # 验证结果
        print(f"\n=== 录制数据回放测试结果 ===")
        print(f"处理帧数: {frames_processed}")
        print(f"发现不同敌人数: {len(enemies_seen)}")
        print(f"发现不同投射物数: {len(projectiles_seen)}")
        print(f"最大同时敌人数: {max_enemies}")
        print(f"最大同时投射物数: {max_projectiles}")
        print(f"最终状态统计: {entity_state.get_stats()}")

        # 基本断言
        assert frames_processed > 0, "应该至少处理了一些帧"

    def test_entity_expiry_during_replay(self, recordings_dir, has_recordings):
        """测试回放过程中实体过期行为"""
        if not has_recordings:
            pytest.skip("没有可用的录制数据")

        config = ReplayerConfig(recordings_dir=str(recordings_dir))
        replayer = DataReplayer(config)
        sessions = list_sessions(str(recordings_dir))
        if not sessions:
            pytest.skip("没有可用的会话")

        replayer.load_session(sessions[0].session_id)

        # 使用较短的过期时间测试
        entity_state = GameEntityState(enemy_expiry=5, projectile_expiry=3)

        total_expired = 0
        frames_processed = 0

        for msg in replayer.iter_messages():
            if not msg.is_data_message:
                continue

            frame = msg.frame
            payload = msg.payload or {}
            frames_processed += 1

            # 记录过期前的数量
            enemies_before = entity_state.enemies.count()

            if "ENEMIES" in payload:
                enemies_data = payload["ENEMIES"]
                if isinstance(enemies_data, dict):
                    enemies_list = list(enemies_data.values())
                elif isinstance(enemies_data, list):
                    enemies_list = enemies_data
                else:
                    enemies_list = []
                entity_state.update_enemies(enemies_list, frame)

            # 检查是否有过期
            expired = entity_state.enemies._stats["total_expired"]
            if expired > total_expired:
                total_expired = expired

            if frames_processed >= 300:
                break

        print(f"\n=== 实体过期测试结果 ===")
        print(f"处理帧数: {frames_processed}")
        print(f"总过期敌人数: {total_expired}")
        print(f"当前敌人数: {entity_state.enemies.count()}")

    def test_facade_process_message_with_replay(self, recordings_dir, has_recordings):
        """测试 Facade.process_message 与录制数据"""
        if not has_recordings:
            pytest.skip("没有可用的录制数据")

        config = ReplayerConfig(recordings_dir=str(recordings_dir))
        replayer = DataReplayer(config)
        sessions = list_sessions(str(recordings_dir))
        if not sessions:
            pytest.skip("没有可用的会话")

        replayer.load_session(sessions[0].session_id)

        # 创建 Facade
        facade = SocketBridgeFacade(BridgeConfig(entity_state_enabled=True))

        frames_processed = 0
        room_changes = 0
        last_room = -1

        for msg in replayer.iter_messages():
            if not msg.is_data_message:
                continue

            # 构造消息字典
            msg_dict = {
                "version": msg.version,
                "type": msg.type,
                "frame": msg.frame,
                "room_index": msg.room_index,
                "payload": msg.payload or {},
            }

            # 使用 Facade 处理消息
            result = facade.process_message(msg_dict)
            frames_processed += 1

            # 检查房间变化
            if msg.room_index != last_room:
                room_changes += 1
                last_room = msg.room_index

            # 使用有状态方法获取数据
            enemies = facade.get_enemies_stateful()
            projectiles = facade.get_projectiles_stateful()
            threat_count = facade.get_threat_count()

            if frames_processed >= 200:
                break

        print(f"\n=== Facade 集成测试结果 ===")
        print(f"处理帧数: {frames_processed}")
        print(f"房间切换次数: {room_changes}")
        print(f"最终统计: {facade.get_stats()}")

        assert frames_processed > 0


# ============================================================================
# 性能测试
# ============================================================================


class TestEntityStatePerformance:
    """实体状态管理性能测试"""

    def test_bulk_update_performance(self):
        """测试大量实体更新性能"""
        import time

        manager = EntityStateManager(
            name="PERF_TEST",
            config=EntityStateConfig(expiry_frames=60),
            id_getter=lambda x: x["id"],
        )

        # 生成大量实体
        entities = [{"id": i, "hp": 100, "x": i * 10, "y": i * 10} for i in range(1000)]

        # 计时
        start = time.perf_counter()
        for frame in range(100):
            # 每帧更新部分实体（模拟实际情况）
            subset = entities[frame * 10 : (frame + 1) * 10]
            manager.update(subset, frame)
        elapsed = time.perf_counter() - start

        print(f"\n=== 性能测试 ===")
        print(f"100 帧 × 10 实体更新耗时: {elapsed * 1000:.2f} ms")
        print(f"平均每帧: {elapsed * 10:.3f} ms")

        # 性能断言（应该非常快）
        assert elapsed < 1.0, "100 帧更新应该在 1 秒内完成"

    def test_large_entity_count(self):
        """测试大量实体存储"""
        manager = EntityStateManager(
            name="LARGE_TEST",
            config=EntityStateConfig(expiry_frames=-1),  # 禁用过期
            id_getter=lambda x: x["id"],
        )

        # 添加 10000 个实体
        entities = [{"id": i} for i in range(10000)]
        manager.update(entities, frame=0)

        assert manager.count() == 10000

        # 获取所有应该很快
        import time

        start = time.perf_counter()
        all_entities = manager.get_all()
        elapsed = time.perf_counter() - start

        assert len(all_entities) == 10000
        assert elapsed < 0.1, "获取 10000 个实体应该在 100ms 内"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
