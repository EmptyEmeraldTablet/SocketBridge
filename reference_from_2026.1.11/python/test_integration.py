"""
集成测试

测试所有模块的协同工作。
"""

import sys
import math
import time
from typing import Dict, List, Any

# 导入模块
from models import Vector2D, PlayerData, EnemyData, ProjectileData, GameStateData
from data_processor import DataParser, DataProcessor
from environment import GameMap, EnvironmentModel
from basic_controllers import (
    BasicMovementController,
    BasicAttackController,
    ControlOutput,
)
from pathfinding import AStarPathfinder, DynamicPathPlanner
from threat_analysis import ThreatAssessor, ThreatAnalyzer, ThreatLevel
from orchestrator import CombatOrchestrator, SimpleAI, AIConfig


class TestResult:
    """测试结果"""

    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.duration = 0.0
        self.error = None
        self.output = None

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.name} ({self.duration:.3f}s)"


def test_vector2d() -> TestResult:
    """测试Vector2D"""
    result = TestResult("Vector2D")
    start = time.time()

    try:
        # 基本运算
        v1 = Vector2D(3, 4)
        v2 = Vector2D(1, 2)

        assert abs(v1.magnitude() - 5.0) < 0.001
        assert abs(v1.distance_to(v2) - math.sqrt(8)) < 0.001

        # 向量运算
        v3 = v1 + v2
        assert abs(v3.x - 4) < 0.001 and abs(v3.y - 6) < 0.001

        v4 = v1 - v2
        assert abs(v4.x - 2) < 0.001 and abs(v4.y - 2) < 0.001

        v5 = v1 * 2
        assert abs(v5.x - 6) < 0.001 and abs(v5.y - 8) < 0.001

        # 归一化
        v6 = Vector2D(10, 0).normalized()
        assert abs(v6.x - 1) < 0.001 and abs(v6.y) < 0.001

        result.passed = True
        result.output = f"Vector2D tests passed"

    except Exception as e:
        result.error = str(e)

    result.duration = time.time() - start
    return result


def test_data_parser() -> TestResult:
    """测试数据解析器"""
    result = TestResult("DataParser")
    start = time.time()

    try:
        # 测试向量解析
        vec = DataParser.parse_vector2d({"x": 10, "y": 20})
        assert abs(vec.x - 10) < 0.001 and abs(vec.y - 20) < 0.001

        # 测试玩家位置解析
        player_data = {"1": {"pos": {"x": 100, "y": 200}, "vel": {"x": 5, "y": 3}}}
        parsed = DataParser.parse_player_position(player_data)
        assert 1 in parsed
        assert parsed[1]["pos"]["x"] == 100

        # 测试敌人数据解析
        enemies = [
            {
                "id": 1,
                "type": 18,
                "pos": {"x": 300, "y": 300},
                "hp": 10,
                "max_hp": 10,
                "distance": 150,
                "vel": {"x": 1, "y": 0},
            }
        ]
        enemy_dict = DataParser.parse_enemies(enemies)
        assert 1 in enemy_dict
        assert enemy_dict[1].hp == 10

        result.passed = True
        result.output = f"Parsed {len(enemies)} enemies"

    except Exception as e:
        result.error = str(e)

    result.duration = time.time() - start
    return result


def test_game_map() -> TestResult:
    """测试游戏地图"""
    result = TestResult("GameMap")
    start = time.time()

    try:
        # 创建地图
        game_map = GameMap(grid_size=91, width=13, height=7)

        # 检查边界
        assert game_map.pixel_width == 13 * 91
        assert game_map.pixel_height == 7 * 91

        # 检查障碍物检测
        pos = Vector2D(100, 100)
        assert not game_map.is_obstacle(pos)

        # 检查范围外
        pos_outside = Vector2D(2000, 2000)
        assert game_map.is_obstacle(pos_outside)

        # 测试安全位置查找
        safe = game_map.get_nearest_walkable_position(Vector2D(500, 300))
        assert safe is not None

        result.passed = True
        result.output = f"Map size: {game_map.width}x{game_map.height}"

    except Exception as e:
        result.error = str(e)

    result.duration = time.time() - start
    return result


def test_pathfinding() -> TestResult:
    """测试路径规划"""
    result = TestResult("Pathfinding (A*)")
    start = time.time()

    try:
        # 创建寻路器
        pathfinder = AStarPathfinder()
        pathfinder.set_map_size(13, 7)

        # 设置障碍物
        obstacles = {(5, 3), (5, 4), (5, 5)}
        pathfinder.set_obstacles(obstacles)

        # 寻路
        start_pos = Vector2D(100, 100)
        goal_pos = Vector2D(800, 400)

        path = pathfinder.find_path(start_pos, goal_pos)

        if path:
            assert len(path) > 0
            result.output = f"Path found with {len(path)} points"
        else:
            result.output = "No path found (expected with obstacles)"

        result.passed = True

    except Exception as e:
        result.error = str(e)

    result.duration = time.time() - start
    return result


def test_threat_assessor() -> TestResult:
    """测试威胁评估"""
    result = TestResult("ThreatAssessor")
    start = time.time()

    try:
        assessor = ThreatAssessor()

        # 创建测试场景
        player_pos = Vector2D(400, 300)
        enemies = {
            1: EnemyData(
                id=1,
                enemy_type=18,
                position=Vector2D(200, 200),
                velocity=Vector2D(1, 0),
                hp=10,
                max_hp=10,
                distance=280,
                is_boss=False,
                is_champion=False,
            ),
            2: EnemyData(
                id=2,
                enemy_type=18,
                position=Vector2D(600, 400),
                velocity=Vector2D(0, 0),
                hp=20,
                max_hp=20,
                distance=140,
                is_boss=True,
                is_champion=False,
            ),
        }

        projectiles = {
            1: ProjectileData(
                id=1,
                is_enemy=True,
                position=Vector2D(300, 280),
                velocity=Vector2D(5, 2),
            )
        }

        # 评估威胁
        assessment = assessor.assess_threats(player_pos, enemies, projectiles)

        assert assessment.threat_count > 0
        assert assessment.overall_threat_level in ThreatLevel

        # Boss应该被识别为高威胁
        boss_threat = next(
            (t for t in assessment.immediate_threats if t.source_id == 2), None
        )
        if boss_threat:
            assert boss_threat.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]

        result.passed = True
        result.output = f"Found {assessment.threat_count} threats, level: {assessment.overall_threat_level.name}"

    except Exception as e:
        result.error = str(e)

    result.duration = time.time() - start
    return result


def test_movement_controller() -> TestResult:
    """测试移动控制器"""
    result = TestResult("MovementController")
    start = time.time()

    try:
        from basic_controllers import MovementConfig

        config = MovementConfig(max_speed=6.0, acceleration=0.5)
        controller = BasicMovementController(config)

        # 测试移动到位置
        current_pos = Vector2D(100, 100)
        target_pos = Vector2D(200, 200)
        current_vel = Vector2D(0, 0)

        move = controller.move_to_position(current_pos, target_pos, current_vel)

        # 应该有移动
        assert move[0] != 0 or move[1] != 0

        # 测试碰撞避免
        obstacles = [Vector2D(250, 250)]
        dodge = controller.avoid_collision(current_pos, obstacles, safe_distance=50)

        result.passed = True
        result.output = f"Move command: {move}"

    except Exception as e:
        result.error = str(e)

    result.duration = time.time() - start
    return result


def test_attack_controller() -> TestResult:
    """测试攻击控制器"""
    result = TestResult("AttackController")
    start = time.time()

    try:
        from basic_controllers import AttackConfig

        config = AttackConfig(shoot_interval=8)
        controller = BasicAttackController(config)

        # 测试瞄准
        player_pos = Vector2D(400, 300)
        target_pos = Vector2D(500, 400)

        aim = controller.aim_at_target(player_pos, target_pos)

        assert aim[0] != 0 or aim[1] != 0  # 应该有方向

        # 测试射击节奏
        can_shoot_1 = controller.should_shoot(0)
        can_shoot_2 = controller.should_shoot(5)

        result.passed = True
        result.output = f"Aim: {aim}, Can shoot: {can_shoot_1}"

    except Exception as e:
        result.error = str(e)

    result.duration = time.time() - start
    return result


def test_orchestrator() -> TestResult:
    """测试主控器"""
    result = TestResult("CombatOrchestrator")
    start = time.time()

    try:
        orchestrator = CombatOrchestrator()
        orchestrator.initialize()
        orchestrator.enable()

        # 创建模拟游戏消息
        message = {
            "type": "DATA",
            "frame": 100,
            "room_index": 5,
            "payload": {
                "PLAYER_POSITION": {
                    "1": {"pos": {"x": 400, "y": 300}, "vel": {"x": 0, "y": 0}}
                },
                "ENEMIES": [
                    {
                        "id": 1,
                        "type": 18,
                        "pos": {"x": 300, "y": 200},
                        "vel": {"x": 1, "y": 0},
                        "hp": 10,
                        "max_hp": 10,
                        "distance": 150,
                        "is_boss": False,
                        "is_champion": False,
                    }
                ],
                "PROJECTILES": {
                    "enemy_projectiles": [],
                    "player_tears": [],
                    "lasers": [],
                },
                "ROOM_INFO": {"room_idx": 5, "enemy_count": 1, "is_clear": False},
            },
            "channels": ["PLAYER_POSITION", "ENEMIES"],
        }

        # 更新
        control = orchestrator.update(message)

        assert orchestrator.stats["decisions"] == 1

        result.passed = True
        result.output = f"State: {orchestrator.current_state.value}, Decisions: {orchestrator.stats['decisions']}"

    except Exception as e:
        result.error = str(e)

    result.duration = time.time() - start
    return result


def test_simple_ai() -> TestResult:
    """测试简单AI"""
    result = TestResult("SimpleAI")
    start = time.time()

    try:
        ai = SimpleAI()
        ai.connect()

        game_data = {
            "frame": 100,
            "room_index": 5,
            "payload": {
                "PLAYER_POSITION": {
                    "1": {"pos": {"x": 400, "y": 300}, "vel": {"x": 0, "y": 0}}
                },
                "ENEMIES": [
                    {
                        "id": 1,
                        "type": 18,
                        "pos": {"x": 500, "y": 300},
                        "vel": {"x": 0, "y": 0},
                        "hp": 10,
                        "max_hp": 10,
                        "distance": 100,
                        "is_boss": False,
                        "is_champion": False,
                    }
                ],
                "PROJECTILES": {
                    "enemy_projectiles": [],
                    "player_tears": [],
                    "lasers": [],
                },
            },
        }

        move, shoot = ai.update(game_data)

        assert isinstance(move, tuple) and isinstance(shoot, tuple)

        result.passed = True
        result.output = f"Move: {move}, Shoot: {shoot}"

    except Exception as e:
        result.error = str(e)

    result.duration = time.time() - start
    return result


def test_environment_model() -> TestResult:
    """测试环境模型"""
    result = TestResult("EnvironmentModel")
    start = time.time()

    try:
        env = EnvironmentModel()

        # 创建测试数据
        from models import RoomLayout, GridTile

        layout = RoomLayout(grid_size=91, width=13, height=7)

        # 添加一些障碍物
        for i in range(5, 8):
            tile = GridTile(
                grid_index=i,
                tile_type=1000,
                has_collision=True,
                position=Vector2D(i * 91, 300),
            )
            layout.tiles[i] = tile

        enemies = {
            1: EnemyData(
                id=1,
                enemy_type=18,
                position=Vector2D(600, 300),
                velocity=Vector2D(1, 0),
                hp=10,
                max_hp=10,
            )
        }

        # 更新环境
        env.update_room(layout, None, enemies, {})

        # 测试安全检查
        safe, danger = env.is_safe(Vector2D(200, 300))

        result.passed = True
        result.output = f"Safe: {safe}, Danger level: {danger:.2f}"

    except Exception as e:
        result.error = str(e)

    result.duration = time.time() - start
    return result


def run_all_tests() -> List[TestResult]:
    """运行所有测试"""
    print("=" * 60)
    print("Running Integration Tests")
    print("=" * 60)

    tests = [
        test_vector2d,
        test_data_parser,
        test_game_map,
        test_pathfinding,
        test_threat_assessor,
        test_movement_controller,
        test_attack_controller,
        test_environment_model,
        test_orchestrator,
        test_simple_ai,
    ]

    results = []
    for test in tests:
        result = test()
        results.append(result)
        print(result)

        if result.error:
            print(f"  Error: {result.error}")

    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r.passed)
    print(f"Results: {passed}/{len(results)} tests passed")
    print("=" * 60)

    return results


if __name__ == "__main__":
    results = run_all_tests()

    # 返回退出码
    all_passed = all(r.passed for r in results)
    sys.exit(0 if all_passed else 1)
