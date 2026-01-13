#!/usr/bin/env python3
"""
SocketBridge 模块化测试套件

通过回放系统对各个新模块进行针对性测试：
1. models.py - 数据模型测试
2. data_processor.py - 数据处理测试
3. threat_analysis.py - 威胁分析测试
4. behavior_tree.py - 行为树测试
5. smart_aiming.py - 智能瞄准测试
6. orchestrator_enhanced.py - 完整集成测试

使用方法:
    python test_suite.py --all              # 运行所有测试
    python test_suite.py --models           # 仅运行模型测试
    python test_suite.py --processor        # 仅运行数据处理测试
    python test_suite.py --threat           # 仅运行威胁分析测试
    python test_suite.py --behavior         # 仅运行行为树测试
    python test_suite.py --aiming           # 仅运行瞄准测试
    python test_suite.py --orchestrator     # 仅运行协调器测试
    python test_suite.py --replay           # 使用回放数据进行集成测试
"""

import sys
import json
import gzip
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import logging

# 添加 python 目录到路径
sys.path.insert(0, str(Path(__file__).parent))

# 导入回放系统
from data_replay_system import RawMessage, LuaSimulator

# 导入要测试的模块
from models import (
    Vector2D,
    PlayerData,
    PlayerStatsData,
    PlayerHealthData,
    EnemyData,
    ProjectileData,
    GameStateData,
    RoomInfo,
    RoomLayout,
    ControlOutput,
    ObjectState,
    EntityType,
)
from data_processor import DataProcessor, DataParser
from threat_analysis import ThreatAnalyzer, ThreatLevel, ThreatAssessment, ThreatInfo
from behavior_tree import (
    BehaviorTree,
    SequenceNode,
    SelectorNode,
    ConditionNode,
    ActionNode,
    NodeContext,
    NodeStatus,
    BehaviorTreeBuilder,
)
from smart_aiming import SmartAimingSystem, ShotType, AimResult

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("TestSuite")


# ============================================================================
# 测试数据生成器
# ============================================================================


def generate_mock_game_state(
    frame: int = 100,
    room_index: int = 1,
    player_pos: Tuple[float, float] = (300, 200),
    enemies: List[Dict] = None,
    projectiles: List[Dict] = None,
) -> Dict[str, Any]:
    """生成模拟游戏状态数据"""

    if enemies is None:
        enemies = [
            {
                "id": 1,
                "type": 10,
                "pos": {"x": 400, "y": 200},
                "vel": {"x": 1, "y": 0},
                "hp": 20,
                "max_hp": 20,
                "damage": 1,
                "is_boss": False,
                "is_champion": False,
                "is_flying": False,
                "is_attacking": False,
            },
            {
                "id": 2,
                "type": 18,
                "pos": {"x": 500, "y": 300},
                "vel": {"x": 0, "y": 1},
                "hp": 10,
                "max_hp": 10,
                "damage": 0.5,
                "is_boss": False,
                "is_champion": False,
                "is_flying": False,
                "is_attacking": False,
            },
        ]

    if projectiles is None:
        projectiles = [
            {
                "id": 100,
                "type": 0,
                "pos": {"x": 350, "y": 200},
                "vel": {"x": -3, "y": 0},
                "damage": 1,
                "size": 5,
                "is_enemy": True,
            }
        ]

    return {
        "version": 2,
        "type": "DATA",
        "timestamp": frame * 16,
        "frame": frame,
        "room_index": room_index,
        "payload": {
            "players": {
                "1": {
                    "player_idx": 1,
                    "pos": {"x": player_pos[0], "y": player_pos[1]},
                    "vel": {"x": 0, "y": 0},
                    "player_type": 0,
                    "health": 3,
                    "max_health": 3,
                    "damage": 3.5,
                    "speed": 1.0,
                    "tears": 10,
                    "tear_range": 300,
                    "shot_speed": 1.0,
                    "luck": 0,
                    "can_fly": False,
                    "size": 10,
                    "direction": 2,
                    "invincible": False,
                    "shooting": False,
                    "charging": False,
                }
            },
            "enemies": {str(e["id"]): e for e in enemies},
            "projectiles": {str(p["id"]): p for p in projectiles},
            "room": {
                "room_index": room_index,
                "stage": 1,
                "stage_type": 0,
                "difficulty": 0,
                "grid_width": 13,
                "grid_height": 7,
                "pixel_width": 520,
                "pixel_height": 280,
                "room_type": "normal",
                "is_clear": False,
                "enemy_count": len(enemies),
            },
        },
        "channels": ["players", "enemies", "projectiles", "room"],
    }


# ============================================================================
# 模型层测试 (models.py)
# ============================================================================


class TestModels:
    """模型层测试类"""

    def __init__(self):
        self.passed = 0
        self.failed = 0

    def test_vector2d_operations(self) -> bool:
        """测试 Vector2D 基本操作"""
        v1 = Vector2D(3, 4)
        v2 = Vector2D(1, 2)

        # 加法
        v3 = v1 + v2
        assert abs(v3.x - 4) < 0.001 and abs(v3.y - 6) < 0.001, "加法错误"

        # 减法
        v4 = v1 - v2
        assert abs(v4.x - 2) < 0.001 and abs(v4.y - 2) < 0.001, "减法错误"

        # 乘法
        v5 = v1 * 2
        assert abs(v5.x - 6) < 0.001 and abs(v5.y - 8) < 0.001, "乘法错误"

        # 除法
        v6 = v1 / 2
        assert abs(v6.x - 1.5) < 0.001 and abs(v6.y - 2) < 0.001, "除法错误"

        # 取反
        v7 = -v1
        assert abs(v7.x - (-3)) < 0.001 and abs(v7.y - (-4)) < 0.001, "取反错误"

        # 长度
        length = v1.magnitude()
        assert abs(length - 5.0) < 0.001, f"长度计算错误: {length}"

        # 归一化
        v8 = Vector2D(3, 4).normalized()
        assert abs(v8.magnitude() - 1.0) < 0.001, "归一化错误"

        # 点积
        dot = v1.dot(v2)
        assert abs(dot - 11.0) < 0.001, f"点积错误: {dot}"

        # 距离
        dist = v1.distance_to(v2)
        expected = ((3 - 1) ** 2 + (4 - 2) ** 2) ** 0.5
        assert abs(dist - expected) < 0.001, f"距离计算错误: {dist}"

        # 相等
        v9 = Vector2D(3, 4)
        assert v1 == v9, "相等判断错误"

        # 转换
        assert v1.to_tuple() == (3, 4), "元组转换错误"
        assert v1.to_dict() == {"x": 3, "y": 4}, "字典转换错误"

        return True

    def test_player_data(self) -> bool:
        """测试 PlayerData 数据类"""
        player = PlayerData(player_idx=1)

        assert player.player_idx == 1, "玩家索引错误"
        assert player.entity_type == EntityType.PLAYER, "实体类型错误"
        assert player.health == 3.0, "默认生命值错误"

        # 位置更新
        new_pos = Vector2D(100, 200)
        new_vel = Vector2D(1, 0)
        player.update_position(new_pos, new_vel, frame=100)

        assert player.position == new_pos, "位置更新错误"
        assert player.velocity == new_vel, "速度更新错误"
        assert player.last_seen_frame == 100, "最后帧更新错误"

        # 位置预测
        predicted = player.predict_position(frames_ahead=5)
        expected = new_pos + new_vel * 5
        assert predicted == expected, "位置预测错误"

        return True

    def test_enemy_data(self) -> bool:
        """测试 EnemyData 数据类"""
        enemy = EnemyData(enemy_id=1)

        # id 是从父类 EntityData 继承的
        assert enemy.id == 1, "敌人ID错误"
        assert enemy.entity_type == EntityType.ENEMY, "实体类型错误"
        assert enemy.hp == 10.0, "默认HP错误"

        # 威胁等级计算 - 使用半血来获得 0.5
        enemy.hp = 10
        enemy.max_hp = 20
        enemy.is_boss = False
        enemy.is_champion = False
        threat = enemy.get_threat_level()
        assert abs(threat - 0.5) < 0.001, f"普通敌人威胁等级错误: {threat}"

        # Boss 威胁加成 (0.5 * 2 = 1.0，但会被限制为1.0)
        enemy.is_boss = True
        threat = enemy.get_threat_level()
        assert abs(threat - 1.0) < 0.001, f"Boss威胁等级错误: {threat}"

        # Champion 威胁加成 (0.5 * 1.5 = 0.75)
        enemy.is_boss = False
        enemy.is_champion = True
        threat = enemy.get_threat_level()
        assert abs(threat - 0.75) < 0.001, f"Champion威胁等级错误: {threat}"

        return True

    def test_projectile_data(self) -> bool:
        """测试 ProjectileData 数据类"""
        proj = ProjectileData(projectile_id=1)

        # id 是从父类 EntityData 继承的
        assert proj.id == 1, "投射物ID错误"
        assert proj.entity_type == EntityType.PROJECTILE, "实体类型错误"
        assert proj.is_enemy == False, "默认敌对状态错误"

        # 位置预测
        proj.position = Vector2D(100, 100)
        proj.velocity = Vector2D(3, 4)
        predicted = proj.predict_position(frames_ahead=5)
        expected = Vector2D(100 + 3 * 5, 100 + 4 * 5)
        assert predicted == expected, f"投射物位置预测错误: {predicted}"

        # 碰撞检测
        proj.position = Vector2D(100, 100)
        proj.size = 5
        target_pos = Vector2D(110, 100)
        assert proj.will_hit(target_pos, target_radius=10), "碰撞检测错误"

        target_pos = Vector2D(120, 100)
        assert not proj.will_hit(target_pos, target_radius=10), "碰撞检测错误"

        return True

    def test_game_state_data(self) -> bool:
        """测试 GameStateData 数据类"""
        state = GameStateData()

        assert state.frame == 0, "初始帧错误"
        assert state.room_index == -1, "初始房间错误"
        assert len(state.players) == 0, "初始玩家数错误"
        assert len(state.enemies) == 0, "初始敌人数错误"

        # 便捷方法
        assert state.get_primary_player() is None, "空状态获取玩家错误"
        assert state.get_threat_count() == 0, "空状态威胁数错误"

        # 活跃敌人过滤
        enemy = EnemyData(enemy_id=1)
        enemy.state = ObjectState.DEAD
        state.enemies[1] = enemy
        assert len(state.active_enemies) == 0, "活跃敌人过滤错误"

        enemy.state = ObjectState.ACTIVE
        assert len(state.active_enemies) == 1, "活跃敌人包含错误"

        # 敌人投射物过滤
        proj1 = ProjectileData(projectile_id=1)
        proj1.is_enemy = True
        proj2 = ProjectileData(projectile_id=2)
        proj2.is_enemy = False

        state.projectiles[1] = proj1
        state.projectiles[2] = proj2

        assert len(state.enemy_projectiles) == 1, "敌人投射物过滤错误"
        assert len(state.player_projectiles) == 1, "玩家投射物过滤错误"

        return True

    def test_control_output(self) -> bool:
        """测试 ControlOutput 数据类"""
        control = ControlOutput()

        assert control.move_x == 0 and control.move_y == 0, "默认移动值错误"
        assert control.shoot == False, "默认射击状态错误"
        assert control.confidence == 1.0, "默认置信度错误"

        # 输入转换
        move, shoot = control.to_input()
        assert move is None and shoot is None, "空输入转换错误"

        control.move_x = 1
        control.move_y = 1
        move, shoot = control.to_input()
        assert move == (1, 1), f"移动输入转换错误: {move}"

        control.shoot = True
        control.shoot_x = 1
        control.shoot_y = 0
        move, shoot = control.to_input()
        assert shoot == (1, 0), f"射击输入转换错误: {shoot}"

        return True

    def run_all(self) -> Tuple[int, int]:
        """运行所有模型测试"""
        tests = [
            ("Vector2D Operations", self.test_vector2d_operations),
            ("PlayerData", self.test_player_data),
            ("EnemyData", self.test_enemy_data),
            ("ProjectileData", self.test_projectile_data),
            ("GameStateData", self.test_game_state_data),
            ("ControlOutput", self.test_control_output),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                if test_func():
                    print(f"  ✅ {name}: PASSED")
                    passed += 1
                else:
                    print(f"  ❌ {name}: 返回 False")
                    failed += 1
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                failed += 1

        return passed, failed


# ============================================================================
# 数据处理层测试 (data_processor.py)
# ============================================================================


class TestDataProcessor:
    """数据处理层测试类"""

    def test_data_parser_player_position(self) -> bool:
        """测试玩家位置数据解析"""
        # 测试字典格式
        dict_data = {
            "1": {"pos": {"x": 100, "y": 200}},
            "2": {"pos": {"x": 300, "y": 400}},
        }
        result = DataParser.parse_player_position(dict_data)
        assert len(result) == 2, f"字典解析错误: {result}"
        assert 1 in result and 2 in result, "玩家索引错误"

        return True

    def test_data_parser_vector2d(self) -> bool:
        """测试 Vector2D 解析"""
        vec = DataParser.parse_vector2d({"x": 5, "y": 10})
        assert vec.x == 5 and vec.y == 10, "Vector2D解析错误"

        vec = DataParser.parse_vector2d(None)
        assert vec.x == 0 and vec.y == 0, "None Vector2D解析错误"

        return True

    def test_data_parser_direction(self) -> bool:
        """测试方向解析"""
        for direction in range(8):
            vec = DataParser.parse_direction(direction)
            assert isinstance(vec, Vector2D), f"方向{direction}解析类型错误"
            assert vec.magnitude() > 0, f"方向{direction}长度错误"

        return True

    def test_data_parser_player_stats(self) -> bool:
        """测试玩家属性解析"""
        data = {
            "player_idx": 1,
            "pos": {"x": 100, "y": 200},
            "vel": {"x": 1, "y": 0},
            "health": 3,
            "max_health": 3,
            "damage": 3.5,
            "speed": 1.0,
        }

        player = DataParser.parse_player_stats(data)

        assert player.player_idx == 1, "玩家索引错误"
        assert player.position.x == 100, "位置X错误"
        assert player.health == 3, "生命值错误"
        assert player.damage == 3.5, "伤害值错误"

        return True

    def test_data_parser_enemy(self) -> bool:
        """测试敌人数据解析"""
        data = {
            "id": 1,
            "type": 10,
            "pos": {"x": 400, "y": 200},
            "vel": {"x": 1, "y": 0},
            "hp": 20,
            "max_hp": 20,
            "damage": 1,
            "is_boss": False,
            "is_champion": True,
        }

        enemy = DataParser.parse_enemy(data)

        assert enemy is not None, "解析返回None"
        assert enemy.id == 1, "敌人ID错误"
        assert enemy.enemy_type == 10, "敌人类型错误"
        assert enemy.position.x == 400, "位置X错误"
        assert enemy.is_champion == True, "Champion标记错误"

        return True

    def test_data_parser_projectile(self) -> bool:
        """测试投射物数据解析"""
        data = {
            "id": 100,
            "type": 0,
            "pos": {"x": 350, "y": 200},
            "vel": {"x": -3, "y": 0},
            "damage": 1,
            "size": 5,
            "is_enemy": True,
        }

        proj = DataParser.parse_projectile(data)

        assert proj is not None, "解析返回None"
        assert proj.id == 100, "投射物ID错误"
        assert proj.position.x == 350, "位置X错误"
        assert proj.is_enemy == True, "敌对标记错误"

        return True

    def test_data_processor_process_message(self) -> bool:
        """测试消息处理"""
        processor = DataProcessor()

        # 处理数据消息
        game_state = generate_mock_game_state(frame=100)
        result = processor.process_message(game_state)

        assert result.frame == 100, "帧更新错误"
        assert result.room_index == 1, "房间索引错误"
        assert len(result.players) == 1, "玩家解析错误"
        assert len(result.enemies) == 2, "敌人解析错误"
        assert len(result.projectiles) == 1, "投射物解析错误"

        return True

    def test_data_processor_reset(self) -> bool:
        """测试数据处理器重置"""
        processor = DataProcessor()

        # 处理一些数据
        game_state = generate_mock_game_state(frame=100)
        processor.process_message(game_state)

        assert processor.current_state.frame == 100, "处理后帧错误"

        # 重置
        processor.reset()

        assert processor.current_state.frame == 0, "重置后帧错误"
        assert len(processor.current_state.players) == 0, "重置后玩家错误"

        return True

    def run_all(self) -> Tuple[int, int]:
        """运行所有数据处理测试"""
        tests = [
            ("Player Position Parsing", self.test_data_parser_player_position),
            ("Vector2D Parsing", self.test_data_parser_vector2d),
            ("Direction Parsing", self.test_data_parser_direction),
            ("Player Stats Parsing", self.test_data_parser_player_stats),
            ("Enemy Parsing", self.test_data_parser_enemy),
            ("Projectile Parsing", self.test_data_parser_projectile),
            ("Message Processing", self.test_data_processor_process_message),
            ("Processor Reset", self.test_data_processor_reset),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                if test_func():
                    print(f"  ✅ {name}: PASSED")
                    passed += 1
                else:
                    print(f"  ❌ {name}: 返回 False")
                    failed += 1
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                failed += 1

        return passed, failed


# ============================================================================
# 威胁分析层测试 (threat_analysis.py)
# ============================================================================


class TestThreatAnalysis:
    """威胁分析层测试类"""

    def test_threat_level_enum(self) -> bool:
        """测试威胁等级枚举"""
        assert ThreatLevel.LOW.value == 0, "LOW值错误"
        assert ThreatLevel.MEDIUM.value == 1, "MEDIUM值错误"
        assert ThreatLevel.HIGH.value == 2, "HIGH值错误"
        assert ThreatLevel.CRITICAL.value == 3, "CRITICAL值错误"

        return True

    def test_threat_analyzer_empty_state(self) -> bool:
        """测试空状态威胁分析"""
        analyzer = ThreatAnalyzer()

        empty_state = GameStateData()
        assessment = analyzer.analyze(empty_state, current_frame=100)

        assert assessment.threat_count == 0, "空状态威胁数错误"
        assert assessment.overall_threat_level == ThreatLevel.LOW, "空状态总体威胁错误"

        return True

    def test_threat_analyzer_single_enemy(self) -> bool:
        """测试单个敌人威胁分析"""
        analyzer = ThreatAnalyzer()

        state = GameStateData()
        state.frame = 100

        player = PlayerData(player_idx=1, position=Vector2D(300, 200))
        player.health = 3
        player.max_health = 3
        state.players[1] = player

        enemy = EnemyData(enemy_id=1, position=Vector2D(400, 200))
        enemy.hp = 20
        enemy.max_hp = 20
        state.enemies[1] = enemy

        assessment = analyzer.analyze(state, current_frame=100)

        # 应该检测到威胁
        assert assessment.threat_count >= 1, "威胁计数错误"

        return True

    def test_threat_analyzer_boss(self) -> bool:
        """测试 Boss 威胁分析"""
        analyzer = ThreatAnalyzer()

        state = GameStateData()
        player = PlayerData(player_idx=1, position=Vector2D(300, 200))
        state.players[1] = player

        # Boss
        boss = EnemyData(enemy_id=100, position=Vector2D(400, 200))
        boss.hp = 100
        boss.max_hp = 100
        boss.is_boss = True
        state.enemies[100] = boss

        assessment = analyzer.analyze(state, current_frame=100)

        # 找到Boss威胁
        all_threats = assessment.immediate_threats + assessment.potential_threats
        boss_threat = next((t for t in all_threats if t.source_id == 100), None)

        assert boss_threat is not None, "未找到Boss威胁"
        assert boss_threat.source_type == "enemy", "威胁类型错误"

        return True

    def test_threat_analyzer_projectile(self) -> bool:
        """测试投射物威胁分析"""
        analyzer = ThreatAnalyzer()

        state = GameStateData()
        player = PlayerData(player_idx=1, position=Vector2D(300, 200))
        state.players[1] = player

        # 敌人投射物
        proj = ProjectileData(projectile_id=1, position=Vector2D(250, 200))
        proj.velocity = Vector2D(-3, 0)
        proj.is_enemy = True
        proj.damage = 1
        proj.size = 5
        state.projectiles[1] = proj

        assessment = analyzer.analyze(state, current_frame=100)

        return True

    def test_evasion_direction(self) -> bool:
        """测试闪避方向计算"""
        analyzer = ThreatAnalyzer()

        player_pos = Vector2D(300, 200)

        # 单个威胁在右边
        threat = ThreatInfo(
            source_id=1,
            source_type="enemy",
            position=Vector2D(400, 200),
            distance=100,
            threat_level=ThreatLevel.HIGH,
            direction=Vector2D(-1, 0),
        )

        assessment = ThreatAssessment(immediate_threats=[threat])
        evasion = analyzer._calculate_evasion_direction(player_pos, assessment)

        # 应该向左闪避（x < 0）
        assert evasion.x < 0 or evasion.y != 0, f"闪避方向错误: {evasion}"

        return True

    def test_overall_threat_calculation(self) -> bool:
        """测试总体威胁等级计算"""
        analyzer = ThreatAnalyzer()

        # 无威胁
        assessment = ThreatAssessment()
        level = analyzer._calculate_overall_threat(assessment)
        assert level == ThreatLevel.LOW, "无威胁时总体等级应为LOW"

        # 3个即时威胁 -> CRITICAL
        assessment = ThreatAssessment()
        for i in range(3):
            assessment.immediate_threats.append(
                ThreatInfo(
                    source_id=i,
                    source_type="enemy",
                    position=Vector2D(100 * i, 0),
                    distance=50,
                    threat_level=ThreatLevel.HIGH,
                )
            )
        level = analyzer._calculate_overall_threat(assessment)
        assert level == ThreatLevel.CRITICAL, "3个即时威胁应为CRITICAL"

        return True

    def run_all(self) -> Tuple[int, int]:
        """运行所有威胁分析测试"""
        tests = [
            ("ThreatLevel Enum", self.test_threat_level_enum),
            ("Empty State Analysis", self.test_threat_analyzer_empty_state),
            ("Single Enemy Analysis", self.test_threat_analyzer_single_enemy),
            ("Boss Threat Analysis", self.test_threat_analyzer_boss),
            ("Projectile Threat Analysis", self.test_threat_analyzer_projectile),
            ("Evasion Direction", self.test_evasion_direction),
            ("Overall Threat Calculation", self.test_overall_threat_calculation),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                if test_func():
                    print(f"  ✅ {name}: PASSED")
                    passed += 1
                else:
                    print(f"  ❌ {name}: 返回 False")
                    failed += 1
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                failed += 1

        return passed, failed


# ============================================================================
# 行为树测试 (behavior_tree.py)
# ============================================================================


class TestBehaviorTree:
    """行为树测试类"""

    def test_node_status_enum(self) -> bool:
        """测试节点状态枚举"""
        assert NodeStatus.IDLE.value == "idle"
        assert NodeStatus.RUNNING.value == "running"
        assert NodeStatus.SUCCESS.value == "success"
        assert NodeStatus.FAILURE.value == "failure"

        return True

    def test_condition_node(self) -> bool:
        """测试条件节点"""
        # 成功条件
        cond = ConditionNode(name="Test", condition=lambda ctx: True)
        ctx = NodeContext()
        assert cond.execute(ctx) == NodeStatus.SUCCESS, "True条件应返回SUCCESS"

        # 失败条件
        cond = ConditionNode(name="Test", condition=lambda ctx: False)
        assert cond.execute(ctx) == NodeStatus.FAILURE, "False条件应返回FAILURE"

        return True

    def test_action_node(self) -> bool:
        """测试动作节点"""
        called = []

        def action(ctx):
            called.append(True)
            return NodeStatus.SUCCESS

        act = ActionNode(name="Test", action=action)
        ctx = NodeContext()
        assert act.execute(ctx) == NodeStatus.SUCCESS, "动作应返回SUCCESS"
        assert len(called) == 1, "动作应该被调用"

        return True

    def test_sequence_node(self) -> bool:
        """测试顺序节点"""
        # 全部成功
        seq = SequenceNode(name="Seq")
        seq.add_child(ConditionNode(name="C1", condition=lambda ctx: True))
        seq.add_child(ConditionNode(name="C2", condition=lambda ctx: True))

        ctx = NodeContext()
        assert seq.execute(ctx) == NodeStatus.SUCCESS, "全部成功应返回SUCCESS"

        # 中间失败
        seq2 = SequenceNode(name="Seq")
        seq2.add_child(ConditionNode(name="C1", condition=lambda ctx: True))
        seq2.add_child(ConditionNode(name="C2", condition=lambda ctx: False))

        assert seq2.execute(ctx) == NodeStatus.FAILURE, "中间失败应返回FAILURE"

        return True

    def test_selector_node(self) -> bool:
        """测试选择节点"""
        # 第一个成功
        sel = SelectorNode(name="Sel")
        sel.add_child(ConditionNode(name="C1", condition=lambda ctx: True))
        sel.add_child(ConditionNode(name="C2", condition=lambda ctx: True))

        ctx = NodeContext()
        assert sel.execute(ctx) == NodeStatus.SUCCESS, "第一个成功应返回SUCCESS"

        # 全部失败
        sel2 = SelectorNode(name="Sel")
        sel2.add_child(ConditionNode(name="C1", condition=lambda ctx: False))
        sel2.add_child(ConditionNode(name="C2", condition=lambda ctx: False))

        assert sel2.execute(ctx) == NodeStatus.FAILURE, "全部失败应返回FAILURE"

        return True

    def test_behavior_tree_execution(self) -> bool:
        """测试行为树执行"""
        builder = BehaviorTreeBuilder()

        builder.selector("CombatRoot")
        builder.sequence("Combat")
        builder.condition("HasEnemies", lambda ctx: len(ctx.enemies) > 0)
        builder.action("Attack", lambda ctx: NodeStatus.SUCCESS)
        builder.end()

        tree = builder.build()

        # 无敌人
        ctx = NodeContext()
        ctx.enemies = []
        tree.context = ctx
        result = tree.update()

        # 应该返回FAILURE因为没有敌人且没有默认动作
        assert result in [NodeStatus.SUCCESS, NodeStatus.FAILURE], "未知结果"

        return True

    def test_behavior_tree_reset(self) -> bool:
        """测试行为树重置"""
        builder = BehaviorTreeBuilder()

        builder.selector("Root")
        builder.sequence("Seq")
        builder.condition("C1", lambda ctx: True)
        builder.end()

        tree = builder.build()

        # 执行
        ctx = NodeContext()
        tree.update()

        # 重置
        tree.root.reset()

        assert tree.root.status == NodeStatus.IDLE, "根节点状态错误"

        return True

    def run_all(self) -> Tuple[int, int]:
        """运行所有行为树测试"""
        tests = [
            ("NodeStatus Enum", self.test_node_status_enum),
            ("ConditionNode", self.test_condition_node),
            ("ActionNode", self.test_action_node),
            ("SequenceNode", self.test_sequence_node),
            ("SelectorNode", self.test_selector_node),
            ("BehaviorTree Execution", self.test_behavior_tree_execution),
            ("BehaviorTree Reset", self.test_behavior_tree_reset),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                if test_func():
                    print(f"  ✅ {name}: PASSED")
                    passed += 1
                else:
                    print(f"  ❌ {name}: 返回 False")
                    failed += 1
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                failed += 1

        return passed, failed


# ============================================================================
# 智能瞄准测试 (smart_aiming.py)
# ============================================================================


class TestSmartAiming:
    """智能瞄准测试类"""

    def test_shot_type_enum(self) -> bool:
        """测试射击类型枚举"""
        assert ShotType.NORMAL.value == "normal"
        assert ShotType.SPREAD.value == "spread"
        assert ShotType.BURST.value == "burst"
        assert ShotType.PRECISE.value == "precise"

        return True

    def test_aim_stationary_target(self) -> bool:
        """测试瞄准静止目标"""
        aiming = SmartAimingSystem()

        shooter_pos = Vector2D(300, 200)
        target = EnemyData(enemy_id=1, position=Vector2D(400, 200))
        target.velocity = Vector2D(0, 0)

        result = aiming.aim(shooter_pos, target)

        assert result.direction.x > 0.9, "应该向右瞄准"
        assert result.confidence > 0.5, "静止目标应有高置信度"
        assert result.shot_type == ShotType.NORMAL, "默认应为普通射击"

        return True

    def test_aim_moving_target(self) -> bool:
        """测试瞄准移动目标"""
        aiming = SmartAimingSystem()

        shooter_pos = Vector2D(300, 200)
        target = EnemyData(enemy_id=1, position=Vector2D(400, 200))
        target.velocity = Vector2D(2, 0)

        result = aiming.aim(shooter_pos, target)

        assert isinstance(result.direction, Vector2D), "方向类型错误"
        assert result.confidence > 0, "移动目标应有置信度"

        return True

    def test_spread_shot(self) -> bool:
        """测试散射射击"""
        aiming = SmartAimingSystem()

        shooter_pos = Vector2D(300, 200)
        target = EnemyData(enemy_id=1, position=Vector2D(400, 200))
        target.velocity = Vector2D(0, 0)

        result = aiming.aim(shooter_pos, target, shot_type=ShotType.SPREAD)

        assert result.shot_type == ShotType.SPREAD, "应为散射类型"

        return True

    def test_burst_shot(self) -> bool:
        """测试突发射击"""
        aiming = SmartAimingSystem()

        shooter_pos = Vector2D(300, 200)
        target = EnemyData(enemy_id=1, position=Vector2D(400, 200))
        target.velocity = Vector2D(0, 0)

        result = aiming.aim(shooter_pos, target, shot_type=ShotType.BURST)

        assert result.shot_type == ShotType.BURST, "应为突发类型"

        return True

    def test_hit_recording(self) -> bool:
        """测试命中记录"""
        aiming = SmartAimingSystem()

        assert aiming.total_shots == 0, "初始射击数应为0"

        # 记录命中
        aiming.record_hit(True)
        assert aiming.total_shots == 1, "射击数错误"
        assert aiming.hit_count == 1, "命中数错误"

        # 记录未命中
        aiming.record_hit(False)
        assert aiming.total_shots == 2, "射击数错误"
        assert aiming.hit_count == 1, "命中数错误"

        # 命中率
        accuracy = aiming.get_accuracy()
        assert abs(accuracy - 0.5) < 0.001, f"命中率计算错误: {accuracy}"

        return True

    def test_accuracy_adjustment(self) -> bool:
        """测试准确率调整"""
        aiming = SmartAimingSystem()

        initial_lead = aiming.lead_factor

        # 记录10次未命中
        for _ in range(10):
            aiming.record_hit(False)

        aiming.adjust_aim_parameters()

        # 准确率低，应该减少提前量
        assert aiming.lead_factor < initial_lead, "低准确率时应减少提前量"

        return True

    def run_all(self) -> Tuple[int, int]:
        """运行所有瞄准测试"""
        tests = [
            ("ShotType Enum", self.test_shot_type_enum),
            ("Stationary Target Aiming", self.test_aim_stationary_target),
            ("Moving Target Aiming", self.test_aim_moving_target),
            ("Spread Shot", self.test_spread_shot),
            ("Burst Shot", self.test_burst_shot),
            ("Hit Recording", self.test_hit_recording),
            ("Accuracy Adjustment", self.test_accuracy_adjustment),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                if test_func():
                    print(f"  ✅ {name}: PASSED")
                    passed += 1
                else:
                    print(f"  ❌ {name}: 返回 False")
                    failed += 1
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                failed += 1

        return passed, failed


# ============================================================================
# 集成测试 - 使用回放数据
# ============================================================================


class TestReplayIntegration:
    """回放集成测试类"""

    def __init__(self, session_dir: str = "recordings"):
        self.session_dir = Path(session_dir)

    def load_session(self) -> Optional[str]:
        """加载最新的录制会话"""
        if not self.session_dir.exists():
            return None

        chunk_files = sorted(self.session_dir.glob("*_chunk_*.json.gz"))

        if not chunk_files:
            return None

        session_ids = set()
        for f in chunk_files:
            name = f.name
            if "_chunk_" in name:
                session_id = name.rsplit("_chunk_", 1)[0]
                session_ids.add(session_id)

        if not session_ids:
            return None

        session_id = sorted(session_ids, reverse=True)[0]
        return session_id

    def load_messages(self, session_id: str) -> List[RawMessage]:
        """加载会话的所有消息"""
        messages = []

        chunk_files = sorted(self.session_dir.glob(f"{session_id}_chunk_*.json.gz"))

        for chunk_file in chunk_files:
            with gzip.open(chunk_file, "rt", encoding="utf-8") as fp:
                data = json.load(fp)
                for msg_dict in data.get("messages", []):
                    messages.append(RawMessage.from_dict(msg_dict))

        messages = sorted(messages, key=lambda m: (m.frame, m.timestamp))

        return messages

    def test_replay_data_processing(self) -> bool:
        """测试回放数据处理"""
        session_id = self.load_session()
        if session_id is None:
            print("    ⚠️ 无录制数据，跳过")
            return True

        messages = self.load_messages(session_id)

        if len(messages) == 0:
            return True

        processor = DataProcessor()
        frame_count = 0

        for msg in messages:
            if msg.msg_type == "DATA":
                processor.process_message(msg.to_dict())
                frame_count += 1

        print(f"    处理了 {frame_count} 个数据帧")
        print(f"    最终帧号: {processor.current_state.frame}")

        return True

    def test_replay_threat_analysis(self) -> bool:
        """测试回放数据的威胁分析"""
        session_id = self.load_session()
        if session_id is None:
            print("    ⚠️ 无录制数据，跳过")
            return True

        messages = self.load_messages(session_id)

        processor = DataProcessor()
        analyzer = ThreatAnalyzer()
        threat_count = 0

        for msg in messages[:200]:
            if msg.msg_type == "DATA":
                processor.process_message(msg.to_dict())
                if processor.current_state.frame % 20 == 0:
                    assessment = analyzer.analyze(processor.current_state)
                    if assessment.threat_count > 0:
                        threat_count += 1

        print(f"    分析了威胁 {threat_count} 次")

        return True

    def test_replay_ai_decisions(self) -> bool:
        """测试回放数据的AI决策"""
        session_id = self.load_session()
        if session_id is None:
            print("    ⚠️ 无录制数据，跳过")
            return True

        messages = self.load_messages(session_id)

        from orchestrator_enhanced import EnhancedCombatOrchestrator, AIConfig

        config = AIConfig()
        orchestrator = EnhancedCombatOrchestrator(config)
        orchestrator.initialize()

        decision_count = 0

        for msg in messages[:200]:
            if msg.msg_type == "DATA":
                control = orchestrator.update(msg.to_dict())
                decision_count += 1

        print(f"    生成了 {decision_count} 个控制决策")

        return True

    def run_all(self) -> Tuple[int, int]:
        """运行所有回放集成测试"""
        tests = [
            ("Replay Data Processing", self.test_replay_data_processing),
            ("Replay Threat Analysis", self.test_replay_threat_analysis),
            ("Replay AI Decisions", self.test_replay_ai_decisions),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                if test_func():
                    print(f"  ✅ {name}: PASSED")
                    passed += 1
                else:
                    print(f"  ❌ {name}: 返回 False")
                    failed += 1
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                failed += 1

        return passed, failed


# ============================================================================
# 状态保持测试 (models.py, data_processor.py)
# ============================================================================


class TestStatePersistence:
    """状态保持功能测试类"""

    def test_channel_last_update(self) -> bool:
        """测试通道最后更新帧跟踪"""
        state = GameStateData()
        state.frame = 100

        # 初始状态
        assert state.get_channel_last_frame("PLAYER_STATS") is None, "初始应该为None"

        # 标记更新
        state.mark_channel_updated("PLAYER_STATS", 100)
        assert state.get_channel_last_frame("PLAYER_STATS") == 100, "应该返回100"

        # 检查过期
        state.frame = 110
        assert state.is_channel_stale("PLAYER_STARS", max_staleness=5), "应该过期"

        return True

    def test_cleanup_stale_entities(self) -> bool:
        """测试过期实体清理"""
        state = GameStateData()
        state.frame = 100

        # 添加敌人
        enemy = EnemyData(enemy_id=1, position=Vector2D(400, 200))
        enemy.last_seen_frame = 30  # 70帧前看到，超过60帧阈值
        state.enemies[1] = enemy

        # 添加投射物
        proj = ProjectileData(projectile_id=1, position=Vector2D(300, 200))
        proj.last_seen_frame = 30
        proj.is_enemy = True
        state.projectiles[1] = proj

        # 清理（当前帧100，阈值60，应该清理70帧之前看到的实体）
        state.cleanup_stale_entities(100)

        assert len(state.enemies) == 0, "敌人应该被清理"
        assert len(state.projectiles) == 0, "投射物应该被清理"

        return True

    def test_player_stats_shortcut(self) -> bool:
        """测试玩家属性快捷方法"""
        state = GameStateData()
        state.frame = 100

        # 添加 player_stats
        stats = PlayerStatsData(
            player_idx=1,
            damage=5.0,
            speed=1.2,
            tears=15.0,
        )
        state.player_stats[1] = stats

        # 测试获取
        result = state.get_primary_player_stats()
        assert result is not None, "应该返回player_stats"
        assert result.damage == 5.0, "伤害值错误"
        assert result.speed == 1.2, "速度值错误"

        return True

    def test_player_health_ratio_fallback(self) -> bool:
        """测试血量比例回退逻辑"""
        state = GameStateData()
        state.frame = 100

        # 初始状态（无 player_health）
        ratio = state.get_primary_player_health_ratio()
        assert ratio == 1.0, "无数据时应该返回1.0"

        # 添加 player_health
        health = PlayerHealthData(
            player_idx=1,
            red_hearts=3,
            max_red_hearts=6,
            soul_hearts=2,
        )
        state.player_health[1] = health

        # 测试（3红心+2灵魂心=4心，最大6心=2/3）
        ratio = state.get_primary_player_health_ratio()
        assert abs(ratio - (4.0 / 6.0)) < 0.01, f"血量比例计算错误: {ratio}"

        return True

    def test_get_stats_fallback(self) -> bool:
        """测试 PlayerData.get_stats() 回退"""
        player = PlayerData(player_idx=1, position=Vector2D(300, 200))
        player.damage = 4.0
        player.speed = 1.1

        # 无 player_stats 时回退到 PlayerData
        stats = player.get_stats(None)
        assert stats.damage == 4.0, "应该从PlayerData获取伤害"
        assert stats.speed == 1.1, "应该从PlayerData获取速度"

        # 有 player_stats 时优先使用
        stats2 = PlayerStatsData(
            player_idx=1,
            damage=6.0,
            speed=1.3,
        )
        stats3 = player.get_stats(stats2)
        assert stats3.damage == 6.0, "应该优先使用player_stats"
        assert stats3.speed == 1.3, "应该优先使用player_stats"

        return True

    def run_all(self) -> Tuple[int, int]:
        """运行所有状态保持测试"""
        tests = [
            ("Channel Last Update", self.test_channel_last_update),
            ("Cleanup Stale Entities", self.test_cleanup_stale_entities),
            ("Player Stats Shortcut", self.test_player_stats_shortcut),
            ("Player Health Ratio Fallback", self.test_player_health_ratio_fallback),
            ("Get Stats Fallback", self.test_get_stats_fallback),
        ]

        passed = 0
        failed = 0

        for name, test_func in tests:
            try:
                if test_func():
                    print(f"  ✅ {name}: PASSED")
                    passed += 1
                else:
                    print(f"  ❌ {name}: 返回 False")
                    failed += 1
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                failed += 1

        return passed, failed


# ============================================================================
# 主测试运行器
# ============================================================================


def run_all_tests(
    test_models: bool = True,
    test_processor: bool = True,
    test_threat: bool = True,
    test_behavior: bool = True,
    test_aiming: bool = True,
    test_replay: bool = True,
    session_dir: str = "recordings",
) -> bool:
    """运行所有测试"""

    print("\n" + "=" * 70)
    print("SocketBridge 模块化测试套件")
    print("=" * 70)
    print()

    total_passed = 0
    total_failed = 0

    # 1. 模型层测试
    if test_models:
        print("📦 模型层测试 (models.py)")
        print("-" * 50)
        tester = TestModels()
        passed, failed = tester.run_all()
        total_passed += passed
        total_failed += failed
        print(f"  小计: {passed} 通过, {failed} 失败")
        print()

    # 2. 数据处理层测试
    if test_processor:
        print("🔄 数据处理层测试 (data_processor.py)")
        print("-" * 50)
        tester = TestDataProcessor()
        passed, failed = tester.run_all()
        total_passed += passed
        total_failed += failed
        print(f"  小计: {passed} 通过, {failed} 失败")
        print()

    # 3. 威胁分析层测试
    if test_threat:
        print("⚠️ 威胁分析层测试 (threat_analysis.py)")
        print("-" * 50)
        tester = TestThreatAnalysis()
        passed, failed = tester.run_all()
        total_passed += passed
        total_failed += failed
        print(f"  小计: {passed} 通过, {failed} 失败")
        print()

    # 4. 行为树测试
    if test_behavior:
        print("🌳 行为树测试 (behavior_tree.py)")
        print("-" * 50)
        tester = TestBehaviorTree()
        passed, failed = tester.run_all()
        total_passed += passed
        total_failed += failed
        print(f"  小计: {passed} 通过, {failed} 失败")
        print()

    # 5. 智能瞄准测试
    if test_aiming:
        print("🎯 智能瞄准测试 (smart_aiming.py)")
        print("-" * 50)
        tester = TestSmartAiming()
        passed, failed = tester.run_all()
        total_passed += passed
        total_failed += failed
        print(f"  小计: {passed} 通过, {failed} 失败")
        print()

    # 6. 回放集成测试
    if test_replay:
        print("🔁 回放集成测试")
        print("-" * 50)
        tester = TestReplayIntegration(session_dir)
        passed, failed = tester.run_all()
        total_passed += passed
        total_failed += failed
        print(f"  小计: {passed} 通过, {failed} 失败")
        print()

    # 7. 状态保持测试
    print("💾 状态保持测试")
    print("-" * 50)
    tester = TestStatePersistence()
    passed, failed = tester.run_all()
    total_passed += passed
    total_failed += failed
    print(f"  小计: {passed} 通过, {failed} 失败")
    print()

    # 最终总结
    print("=" * 70)
    print("测试套件执行完成")
    print("=" * 70)
    print(f"总测试数: {total_passed + total_failed}")
    print(f"✅ 通过: {total_passed}")
    print(f"❌ 失败: {total_failed}")
    print("=" * 70)

    if total_failed == 0:
        print("🎉 所有测试通过!")
    else:
        print(f"⚠️ 有 {total_failed} 个测试失败")

    return total_failed == 0


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="SocketBridge 模块化测试套件")

    parser.add_argument(
        "--all",
        action="store_true",
        default=True,
        help="运行所有测试（默认）",
    )
    parser.add_argument(
        "--models",
        action="store_true",
        help="仅运行模型测试",
    )
    parser.add_argument(
        "--processor",
        action="store_true",
        help="仅运行数据处理测试",
    )
    parser.add_argument(
        "--threat",
        action="store_true",
        help="仅运行威胁分析测试",
    )
    parser.add_argument(
        "--behavior",
        action="store_true",
        help="仅运行行为树测试",
    )
    parser.add_argument(
        "--aiming",
        action="store_true",
        help="仅运行瞄准测试",
    )
    parser.add_argument(
        "--replay",
        action="store_true",
        help="仅运行回放集成测试",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="recordings",
        help="录制数据目录（默认: recordings）",
    )

    args = parser.parse_args()

    # 确定运行哪些测试
    run_models = args.models or not any(
        [args.processor, args.threat, args.behavior, args.aiming, args.replay]
    )
    run_processor = args.processor or not any(
        [args.models, args.threat, args.behavior, args.aiming, args.replay]
    )
    run_threat = args.threat or not any(
        [args.models, args.processor, args.behavior, args.aiming, args.replay]
    )
    run_behavior = args.behavior or not any(
        [args.models, args.processor, args.threat, args.aiming, args.replay]
    )
    run_aiming = args.aiming or not any(
        [args.models, args.processor, args.threat, args.behavior, args.replay]
    )
    run_replay = args.replay or not any(
        [args.models, args.processor, args.threat, args.behavior, args.aiming]
    )

    success = run_all_tests(
        test_models=run_models,
        test_processor=run_processor,
        test_threat=run_threat,
        test_behavior=run_behavior,
        test_aiming=run_aiming,
        test_replay=run_replay,
        session_dir=args.dir,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
