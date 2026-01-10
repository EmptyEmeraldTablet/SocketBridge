"""
AI Combat System Test Suite

测试所有模块的功能和集成。
"""

import sys
import os
import time
import math
from typing import Dict, List, Optional
from dataclasses import dataclass, field

# 添加 python/ 目录到路径（兼容 Windows 和不同运行目录）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PYTHON_ROOT = os.path.dirname(_SCRIPT_DIR)  # python/ 目录
if _PYTHON_ROOT not in sys.path:
    sys.path.insert(0, _PYTHON_ROOT)

# 导入AI战斗系统
from ai_combat_system import (
    create_orchestrator,
    SystemConfig,
    Vector2D,
    ThreatLevel,
    ActionType,
    GameState,
    PlayerState,
    EnemyState,
    RoomLayout,
    SituationAssessment,
    ActionIntent,
)


def create_mock_game_state() -> GameState:
    """创建模拟游戏状态"""
    # 创建房间
    room = RoomLayout(
        room_index=1,
        room_type=1,
        top_left=Vector2D(0, 0),
        bottom_right=Vector2D(800, 600),
        grid_width=20,
        grid_height=15,
    )

    # 创建玩家
    player = PlayerState(
        player_id=1, position=field(default=None), velocity=field(default=None)
    )

    # 创建敌人
    enemies = {
        1: EnemyState(
            entity_id=1,
            enemy_type=18,
            variant=0,
            subtype=0,
            position=field(default=None),
            velocity=field(default=None),
            hp=50,
            max_hp=100,
            is_boss=False,
            distance_to_player=200,
        )
    }

    # 创建游戏状态
    state = GameState(frame=0, room_index=1, player=player, enemies=enemies, room=room)

    return state


def create_mock_raw_data() -> Dict:
    """创建模拟原始数据"""
    return {
        "PLAYER_POSITION": {
            "1": {
                "pos": {"x": 400.0, "y": 300.0},
                "vel": {"x": 0.0, "y": 0.0},
                "aim_dir": {"x": 1.0, "y": 0.0},
                "hp": 6,
                "max_hp": 6,
            }
        },
        "PLAYER_STATS": {"1": {"damage": 3.5, "speed": 1.0, "tears": 15, "range": 300}},
        "PLAYER_HEALTH": {"1": {"red_hearts": 6, "max_hearts": 6}},
        "ENEMIES": [
            {
                "id": 1,
                "type": 18,
                "variant": 0,
                "subtype": 0,
                "pos": {"x": 600.0, "y": 300.0},
                "vel": {"x": 1.0, "y": 0.0},
                "hp": 50,
                "max_hp": 100,
                "is_boss": False,
                "distance": 200,
            }
        ],
        "PROJECTILES": {"enemy_projectiles": [], "player_tears": [], "lasers": []},
        "ROOM_INFO": {
            "room_idx": 1,
            "room_type": 1,
            "is_clear": False,
            "enemy_count": 1,
        },
        "ROOM_LAYOUT": {
            "room_idx": 1,
            "top_left": {"x": 0, "y": 0},
            "bottom_right": {"x": 800, "y": 600},
            "grid_width": 20,
            "grid_height": 15,
            "grid": {},
            "doors": {},
        },
    }


def test_perception_module():
    """测试感知模块"""
    print("\n" + "=" * 60)
    print("Testing Perception Module")
    print("=" * 60)

    from ai_combat_system import create_perception_module

    perception = create_perception_module()

    # 处理模拟数据
    raw_data = create_mock_raw_data()
    game_state = perception.process_raw_data(raw_data, frame=100, room_index=1)

    # 验证结果
    assert game_state is not None, "GameState should not be None"
    assert game_state.player is not None, "Player should not be None"
    assert game_state.player.position is not None, "Player position should not be None"
    assert len(game_state.enemies) > 0, "Should have enemies"

    # 检查位置解析
    player_pos = game_state.player.position.pos
    assert abs(player_pos.x - 400.0) < 1, f"Player X should be ~400, got {player_pos.x}"
    assert abs(player_pos.y - 300.0) < 1, f"Player Y should be ~300, got {player_pos.y}"

    # 检查敌人解析
    enemy = list(game_state.enemies.values())[0]
    assert enemy.entity_id == 1, "Enemy ID should be 1"
    assert enemy.hp == 50, "Enemy HP should be 50"

    print("✓ Perception module tests passed!")

    return True


def test_analysis_module():
    """测试分析模块"""
    print("\n" + "=" * 60)
    print("Testing Analysis Module")
    print("=" * 60)

    from ai_combat_system import create_analysis_module, create_perception_module

    # 创建模块
    perception = create_perception_module()
    analysis = create_analysis_module()

    # 处理数据
    raw_data = create_mock_raw_data()
    game_state = perception.process_raw_data(raw_data, frame=100, room_index=1)

    # 分析
    situation = analysis.analyze(game_state)

    # 验证结果
    assert situation is not None, "Situation should not be None"
    assert situation.enemy_count >= 0, "Enemy count should be non-negative"
    assert situation.resources is not None, "Resources should not be None"

    # 检查威胁评估
    if len(game_state.get_active_enemies()) > 0:
        assert situation.is_combat == True, "Should be in combat"

    # 检查资源分析
    assert situation.resources.hp_percentage > 0, "HP percentage should be positive"

    print("✓ Analysis module tests passed!")

    return True


def test_decision_module():
    """测试决策模块"""
    print("\n" + "=" * 60)
    print("Testing Decision Module")
    print("=" * 60)

    from ai_combat_system import create_analysis_module, create_decision_module
    from ai_combat_system import create_perception_module, StrategyProfile

    # 创建模块
    perception = create_perception_module()
    analysis = create_analysis_module()
    decision = create_decision_module()

    # 处理数据
    raw_data = create_mock_raw_data()
    game_state = perception.process_raw_data(raw_data, frame=100, room_index=1)
    situation = analysis.analyze(game_state)

    # 决策
    action = decision.decide(situation, game_state)

    # 验证结果
    assert action is not None, "Action should not be None"
    assert action.action_type is not None, "Action type should not be None"
    assert action.priority >= 0, "Priority should be non-negative"

    # 测试策略切换
    decision.set_strategy(StrategyProfile.aggressive())
    action_aggressive = decision.decide(situation, game_state)

    decision.set_strategy(StrategyProfile.defensive())
    action_defensive = decision.decide(situation, game_state)

    print(f"✓ Action type: {action.action_type.value}")
    print(f"✓ Aggressive action: {action_aggressive.action_type.value}")
    print(f"✓ Defensive action: {action_defensive.action_type.value}")
    print("✓ Decision module tests passed!")

    return True


def test_planning_module():
    """测试规划模块"""
    print("\n" + "=" * 60)
    print("Testing Planning Module")
    print("=" * 60)

    from ai_combat_system import create_planning_module, create_decision_module
    from ai_combat_system import create_analysis_module, create_perception_module
    from ai_combat_system import ActionType

    # 创建模块
    perception = create_perception_module()
    analysis = create_analysis_module()
    decision = create_decision_module()
    planning = create_planning_module()

    # 处理数据
    raw_data = create_mock_raw_data()
    game_state = perception.process_raw_data(raw_data, frame=100, room_index=1)
    situation = analysis.analyze(game_state)
    action = decision.decide(situation, game_state)

    # 规划
    plan = planning.plan(action, game_state)

    # 验证结果
    assert plan is not None, "Plan should not be None"
    assert plan.action_intent is not None, "Action intent should not be None"
    assert plan.overall_risk >= 0, "Risk should be non-negative"
    assert plan.success_probability >= 0, "Success probability should be non-negative"

    print(f"✓ Plan action: {plan.action_intent.action_type.value}")
    print(f"✓ Plan risk: {plan.overall_risk:.2f}")
    print(f"✓ Plan success rate: {plan.success_probability:.2f}")
    print("✓ Planning module tests passed!")

    return True


def test_control_module():
    """测试控制模块"""
    print("\n" + "=" * 60)
    print("Testing Control Module")
    print("=" * 60)

    from ai_combat_system import create_control_module, create_planning_module
    from ai_combat_system import create_decision_module, create_analysis_module
    from ai_combat_system import create_perception_module

    # 创建模块
    perception = create_perception_module()
    analysis = create_analysis_module()
    decision = create_decision_module()
    planning = create_planning_module()
    control = create_control_module()

    # 处理数据
    raw_data = create_mock_raw_data()
    game_state = perception.process_raw_data(raw_data, frame=100, room_index=1)
    situation = analysis.analyze(game_state)
    action = decision.decide(situation, game_state)
    plan = planning.plan(action, game_state)

    # 控制
    current_state = {"position": Vector2D(400, 300), "velocity": Vector2D(0, 0)}

    command = control.execute(plan, current_state, current_frame=100)

    # 验证结果
    assert command is not None, "Command should not be None"
    assert hasattr(command, "move"), "Command should have move attribute"
    assert hasattr(command, "shoot"), "Command should have shoot attribute"

    print(f"✓ Move command: {command.move}")
    print(f"✓ Shoot command: {command.shoot}")
    print("✓ Control module tests passed!")

    return True


def test_orchestrator():
    """测试主控模块"""
    print("\n" + "=" * 60)
    print("Testing Orchestrator Module")
    print("=" * 60)

    # 创建主控器
    config = SystemConfig()
    orchestrator = create_orchestrator(config)

    # 初始化
    orchestrator.initialize()
    assert orchestrator.status.is_running == True, "Should be running"

    # 处理帧
    raw_data = create_mock_raw_data()
    command = orchestrator.process_frame(raw_data, frame=1)

    # 验证结果
    assert command is not None, "Command should not be None"
    assert orchestrator.status.total_frames == 1, "Should have processed 1 frame"

    # 获取统计
    stats = orchestrator.get_stats()
    assert stats is not None, "Stats should not be None"
    assert "status" in stats, "Stats should have status"
    assert "modules" in stats, "Stats should have modules"

    print(f"✓ FPS: {stats['status'].get('fps', 0):.1f}")
    print(f"✓ Total frames: {stats['status'].get('total_frames', 0)}")
    print(f"✓ Combat state: {stats['status'].get('combat_state', 'unknown')}")
    print("✓ Orchestrator tests passed!")

    # 关闭
    orchestrator.shutdown()
    assert orchestrator.status.is_running == False, "Should be stopped"

    return True


def test_module_integration():
    """测试模块集成"""
    print("\n" + "=" * 60)
    print("Testing Module Integration")
    print("=" * 60)

    from ai_combat_system import (
        create_orchestrator,
        SystemConfig,
        create_perception_module,
        create_analysis_module,
        create_decision_module,
        create_planning_module,
        create_control_module,
        create_evaluation_module,
    )

    # 测试所有模块创建
    modules = {
        "perception": create_perception_module(),
        "analysis": create_analysis_module(),
        "decision": create_decision_module(),
        "planning": create_planning_module(),
        "control": create_control_module(),
        "evaluation": create_evaluation_module(),
    }

    # 验证所有模块都有必要的方法
    for name, module in modules.items():
        assert module is not None, f"{name} module should not be None"
        print(f"✓ {name} module created successfully")

    # 测试完整流程
    orchestrator = create_orchestrator(SystemConfig())
    orchestrator.initialize()

    # 处理多帧
    for i in range(10):
        raw_data = create_mock_raw_data()
        # 修改数据以模拟变化
        raw_data["PLAYER_POSITION"]["1"]["pos"]["x"] = 400 + i * 5
        command = orchestrator.process_frame(raw_data, frame=i)

    # 验证统计
    stats = orchestrator.get_stats()
    assert stats["status"]["total_frames"] >= 10, "Should process multiple frames"

    orchestrator.shutdown()

    print("✓ Module integration tests passed!")
    return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("AI Combat System - Test Suite")
    print("=" * 60)

    tests = [
        ("Perception Module", test_perception_module),
        ("Analysis Module", test_analysis_module),
        ("Decision Module", test_decision_module),
        ("Planning Module", test_planning_module),
        ("Control Module", test_control_module),
        ("Orchestrator Module", test_orchestrator),
        ("Module Integration", test_module_integration),
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, "PASSED" if result else "FAILED", None))
        except Exception as e:
            results.append((name, "ERROR", str(e)))
            print(f"✗ {name} failed with error: {e}")

    # 打印结果摘要
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    passed = 0
    failed = 0
    errors = 0

    for name, status, error in results:
        if status == "PASSED":
            passed += 1
            print(f"✓ {name}: PASSED")
        elif status == "FAILED":
            failed += 1
            print(f"✗ {name}: FAILED")
        else:
            errors += 1
            print(f"✗ {name}: ERROR - {error}")

    print(f"\nTotal: {passed + failed + errors}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Errors: {errors}")

    return passed == len(tests)


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
