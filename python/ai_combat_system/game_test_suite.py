"""
AI Combat System - 游戏测试脚本

功能:
1. 利用控制台指令搭建游戏测试场景
2. 测试AI Combat System各模块的实际表现
3. 安全的spawn机制，防止游戏崩溃

注意事项:
- spawn指令有严格冷却时间（默认20秒）
- 每次测试场景的敌人生成数量有限制（单次最多2个）
- 包含自动清理机制（使用 debug 10 命令）

使用方法:
1. 先启动游戏并启用SocketBridge模组
2. 运行此脚本: python game_test_suite.py
3. 脚本会自动连接游戏并执行测试场景
"""

import sys
import os
import time
import json
import logging
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import threading

# 添加 python/ 目录到路径（兼容 Windows 和不同运行目录）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PYTHON_ROOT = os.path.dirname(_SCRIPT_DIR)  # python/ 目录
if _PYTHON_ROOT not in sys.path:
    sys.path.insert(0, _PYTHON_ROOT)

# 导入IsaacBridge和AI模块
from isaac_bridge import IsaacBridge, GameDataAccessor
from ai_combat_system import (
    create_perception_module,
    create_analysis_module,
    create_decision_module,
    create_planning_module,
    create_control_module,
    create_evaluation_module,
    create_orchestrator,
    SystemConfig,
    Vector2D,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("AITestSuite")


class TestScenario(Enum):
    """测试场景类型"""

    EMPTY = "empty"  # 空房间测试
    SINGLE_ENEMY = "single_enemy"  # 单个敌人
    FEW_ENEMIES = "few_enemies"  # 少量敌人 (3-5个)
    MANY_ENEMIES = "many_enemies"  # 多个敌人 (5-10个)
    PROJECTILE_TEST = "projectile"  # 投射物测试
    MIXED_TEST = "mixed"  # 混合测试
    SURVIVAL = "survival"  # 生存测试


@dataclass
class TestResult:
    """测试结果"""

    scenario: str
    success: bool
    frame_count: int
    enemies_spawned: int
    player_damage_taken: int
    enemies_killed: int
    ai_decisions: int
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


# 常用敌人类型 (entity.type.subtype 格式)
COMMON_ENEMIES = {
    "fly": "10.0.0",  # Fly
    "spider": "11.0.0",  # Spider
    "maw": "18.0.0",  # Maw
    "horf": "19.0.0",  # Horf
    "knife": "20.0.0",  # Knife
    "leaper": "24.0.0",  # Leaper
    "baby": "26.0.0",  # Baby
    "globin": "2001.0",  # Globin
    "cochleary": "2002.0",  # Cochleary
}


def spawn_enemy(bridge: IsaacBridge, enemy_type: str, count: int = 1) -> bool:
    """
    直接使用控制台命令生成敌人

    Args:
        bridge: IsaacBridge 实例
        enemy_type: 敌人类型 (如 "10.0.0" 或预定义键如 "fly")
        count: 生成数量

    Returns:
        bool: 是否成功
    """
    # 解析敌人类型
    enemy_id = COMMON_ENEMIES.get(enemy_type.lower(), enemy_type)

    success = True
    spawned = 0

    for i in range(count):
        cmd = f"spawn {enemy_id}"
        if bridge.send_console_command(cmd):
            spawned += 1
            logger.info(f"生成敌人: {enemy_id}")
        else:
            success = False
            logger.error(f"生成失败: {enemy_id}")

        time.sleep(0.2)  # 短暂延迟

    if spawned > 0:
        logger.info(f"成功生成 {spawned} 个敌人")

    return success


def spawn_enemies(bridge: IsaacBridge, enemies: List[Tuple[str, int]]) -> int:
    """
    批量生成多种敌人

    Args:
        bridge: IsaacBridge 实例
        enemies: [(敌人类型, 数量), ...]

    Returns:
        int: 成功生成的数量
    """
    total = 0
    for enemy_type, count in enemies:
        if spawn_enemy(bridge, enemy_type, count):
            total += count
    return total


def clear_enemies(bridge: IsaacBridge):
    """清理房间内所有敌人"""
    bridge.send_console_command("debug 10")
    time.sleep(0.3)
    logger.info("已清理房间所有敌人")


def get_enemy_count(bridge: IsaacBridge) -> int:
    """获取当前房间敌人数量"""
    try:
        enemies_data = bridge.get_channel("ENEMIES")
        if enemies_data is None:
            return 0
        if isinstance(enemies_data, list):
            return len(enemies_data)
        elif isinstance(enemies_data, dict):
            return len(enemies_data.get("enemies", []))
        return 0
    except Exception:
        return 0


class AITestSuite:
    """
    AI Combat System 测试套件

    功能:
    1. 连接游戏并搭建测试场景
    2. 执行AI模块测试
    3. 收集测试结果
    4. 生成测试报告
    """

    def __init__(self, bridge: IsaacBridge):
        self.bridge = bridge
        self.data = GameDataAccessor(bridge)

        # 创建AI模块
        self.perception = create_perception_module()
        self.analysis = create_analysis_module()
        self.decision = create_decision_module()
        self.planning = create_planning_module()
        self.control = create_control_module()
        self.evaluation = create_evaluation_module()
        self.orchestrator = create_orchestrator(SystemConfig())

        # 测试状态
        self.test_results: List[TestResult] = []
        self.test_frame_count = 0
        self.test_enemies_killed = 0
        self.test_damage_taken = 0

        # 事件处理
        self._setup_event_handlers()

    def _setup_event_handlers(self):
        """设置事件处理器"""

        @self.bridge.on("event:PLAYER_DAMAGE")
        def on_damage(event_data):
            amount = event_data.get("amount", 0)
            self.test_damage_taken += amount
            logger.warning(f"玩家受到伤害: {amount}")

        @self.bridge.on("event:NPC_DEATH")
        def on_npc_death(event_data):
            self.test_enemies_killed += 1
            logger.info(f"敌人被击杀 (总计: {self.test_enemies_killed})")

        @self.bridge.on("event:ROOM_ENTER")
        def on_room_enter(event_data):
            logger.info(f"进入房间 {event_data.get('room_index', -1)}")

    def _get_raw_data(self) -> Dict:
        """获取当前游戏原始数据"""
        raw_data = {
            "PLAYER_POSITION": self.data.get_player_position() or {},
            "PLAYER_STATS": self.data.get_player_stats() or {},
            "PLAYER_HEALTH": self.data.get_player_health() or {},
            "ENEMIES": self.data.get_enemies(),
            "PROJECTILES": self.data.get_projectiles(),
            "ROOM_INFO": self.data.get_room_info() or {},
            "ROOM_LAYOUT": self.data.get_room_layout() or {},
        }
        return raw_data

    def _ai_step(self) -> Optional[Tuple]:
        """
        执行单步AI处理

        Returns:
            (action, plan, command) 或 None
        """
        # 1. 感知
        raw_data = self._get_raw_data()
        game_state = self.perception.process_raw_data(
            raw_data, frame=self.test_frame_count
        )

        # 2. 分析
        situation = self.analysis.analyze(game_state)

        # 3. 决策
        action = self.decision.decide(situation, game_state)

        # 4. 规划
        plan = self.planning.plan(action, game_state)

        # 5. 控制
        current_state = {
            "position": game_state.player.position.pos
            if game_state.player and game_state.player.position
            else Vector2D(400, 300),
            "velocity": game_state.player.velocity.vel
            if game_state.player and game_state.player.velocity
            else Vector2D(0, 0),
        }
        command = self.control.execute(
            plan, current_state, current_frame=self.test_frame_count
        )

        # 发送控制指令
        if command.move:
            self.bridge.send_input(move=command.move)
        if command.shoot:
            self.bridge.send_input(shoot=command.shoot)
        if command.use_bomb:
            self.bridge.send_input(use_bomb=True)
        if command.use_item:
            self.bridge.send_input(use_item=True)

        return (action, plan, command)

    def run_scenario(
        self, scenario: TestScenario, duration_seconds: float = 10
    ) -> TestResult:
        """
        运行指定测试场景

        Args:
            scenario: 测试场景类型
            duration_seconds: 场景持续时间（秒）

        Returns:
            TestResult: 测试结果
        """
        logger.info(f"开始测试场景: {scenario.value}")

        start_time = time.time()
        errors = []

        # 重置测试状态
        self.test_frame_count = 0
        self.test_enemies_killed = 0
        self.test_damage_taken = 0
        decisions_made = 0

        try:
            # 1. 场景准备
            self._setup_scenario(scenario)

            # 2. 等待场景稳定
            logger.info("等待场景稳定...")
            time.sleep(2)

            # 3. 执行AI测试循环
            logger.info(f"开始AI测试循环 ({duration_seconds}秒)...")
            loop_start = time.time()

            while time.time() - loop_start < duration_seconds:
                # 执行AI步骤
                result = self._ai_step()
                if result:
                    decisions_made += 1

                self.test_frame_count += 1

                # 控制执行频率
                time.sleep(1 / 30)  # ~30 FPS

                # 定期日志输出
                if self.test_frame_count % 100 == 0:
                    pos = self.data.get_player_position()
                    pos_str = (
                        f"({pos['pos']['x']:.0f}, {pos['pos']['y']:.0f})"
                        if pos
                        else "N/A"
                    )
                    enemies = self.data.get_enemies()
                    logger.info(
                        f"帧 {self.test_frame_count} | 位置 {pos_str} | 敌人 {len(enemies)} | AI决策 {decisions_made}"
                    )

            # 4. 清理场景
            self._cleanup_scenario(scenario)

        except Exception as e:
            error_msg = f"场景 {scenario.value} 执行错误: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

        duration_ms = (time.time() - start_time) * 1000

        result = TestResult(
            scenario=scenario.value,
            success=len(errors) == 0,
            frame_count=self.test_frame_count,
            enemies_spawned=get_enemy_count(self.bridge),
            player_damage_taken=self.test_damage_taken,
            enemies_killed=self.test_enemies_killed,
            ai_decisions=decisions_made,
            errors=errors,
            duration_ms=duration_ms,
        )

        self.test_results.append(result)
        return result

    def _setup_scenario(self, scenario: TestScenario):
        """搭建测试场景"""
        logger.info(f"搭建场景: {scenario.value}")

        if scenario == TestScenario.EMPTY:
            # 空房间 - 确保没有敌人
            clear_enemies(self.bridge)

        elif scenario == TestScenario.SINGLE_ENEMY:
            # 单个敌人
            clear_enemies(self.bridge)
            time.sleep(1)
            spawn_enemy(self.bridge, "fly")

        elif scenario == TestScenario.FEW_ENEMIES:
            # 少量敌人 (3-5个)
            clear_enemies(self.bridge)
            time.sleep(1)
            spawn_enemy(self.bridge, "fly")
            time.sleep(1)
            spawn_enemy(self.bridge, "spider")
            time.sleep(1)
            spawn_enemy(self.bridge, "globin")

        elif scenario == TestScenario.MANY_ENEMIES:
            # 多个敌人
            clear_enemies(self.bridge)
            time.sleep(1)
            spawn_enemy(self.bridge, "fly", 2)
            time.sleep(1)
            spawn_enemy(self.bridge, "spider", 2)
            time.sleep(1)
            spawn_enemy(self.bridge, "cochleary")

        elif scenario == TestScenario.PROJECTILE_TEST:
            # 投射物测试 - 使用会发射投射物的敌人
            clear_enemies(self.bridge)
            time.sleep(1)
            # Maw 会呕吐投射物
            spawn_enemy(self.bridge, "maw", 2)

        elif scenario == TestScenario.MIXED_TEST:
            # 混合测试
            clear_enemies(self.bridge)
            time.sleep(1)
            spawn_enemy(self.bridge, "fly", 2)
            time.sleep(1)
            spawn_enemy(self.bridge, "maw")
            time.sleep(1)
            spawn_enemy(self.bridge, "spider", 2)
            time.sleep(1)
            spawn_enemy(self.bridge, "globin")

        elif scenario == TestScenario.SURVIVAL:
            # 生存测试 - 生成较多敌人
            clear_enemies(self.bridge)
            time.sleep(1)
            spawn_enemy(self.bridge, "fly", 3)
            time.sleep(2)
            spawn_enemy(self.bridge, "spider", 2)
            time.sleep(2)
            spawn_enemy(self.bridge, "maw", 2)

    def _cleanup_scenario(self, scenario: TestScenario):
        """清理测试场景"""
        logger.info(f"清理场景: {scenario.value}")
        clear_enemies(self.bridge)

        # 给予玩家无敌状态以便离开
        self.bridge.send_console_command("giveitem c1")  # 以撒的眼泪

    def run_all_tests(self) -> List[TestResult]:
        """运行所有测试场景"""
        results = []

        # 连接成功后运行测试
        if not self.bridge.is_connected():
            logger.error("未连接到游戏，无法运行测试")
            return results

        logger.info("=" * 60)
        logger.info("AI Combat System - 游戏测试套件")
        logger.info("=" * 60)

        # 初始化AI模块
        logger.info("初始化AI模块...")
        self.orchestrator.initialize()
        logger.info("  ✓ AI模块初始化完成")

        # 运行各个场景
        test_scenarios = [
            (TestScenario.EMPTY, 5),
            (TestScenario.SINGLE_ENEMY, 10),
            (TestScenario.FEW_ENEMIES, 15),
            (TestScenario.PROJECTILE_TEST, 10),
            (TestScenario.MIXED_TEST, 15),
        ]

        for scenario, duration in test_scenarios:
            logger.info("")
            logger.info("-" * 40)

            # 等待一下再进行下一个测试
            time.sleep(2)

            result = self.run_scenario(scenario, duration)
            results.append(result)

            # 输出结果摘要
            logger.info("")
            logger.info(f"场景 '{result.scenario}' 结果:")
            logger.info(f"  ✓ 成功: {result.success}")
            logger.info(f"  ✓ 帧数: {result.frame_count}")
            logger.info(f"  ✓ 生成敌人: {result.enemies_spawned}")
            logger.info(f"  ✓ 击杀敌人: {result.enemies_killed}")
            logger.info(f"  ✓ 受到伤害: {result.player_damage_taken}")
            logger.info(f"  ✓ AI决策: {result.ai_decisions}")
            if result.errors:
                logger.error(f"  ✗ 错误: {result.errors}")

        # 清理
        self.orchestrator.shutdown()

        return results

    def print_summary(self):
        """打印测试结果摘要"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("测试结果摘要")
        logger.info("=" * 60)

        passed = sum(1 for r in self.test_results if r.success)
        total = len(self.test_results)

        logger.info(f"总测试数: {total}")
        logger.info(f"通过: {passed}")
        logger.info(f"失败: {total - passed}")
        logger.info("")

        for result in self.test_results:
            status = "✓ PASS" if result.success else "✗ FAIL"
            logger.info(f"[{status}] {result.scenario}")
            logger.info(f"  帧数: {result.frame_count}, AI决策: {result.ai_decisions}")
            logger.info(
                f"  敌人: {result.enemies_spawned}生成, {result.enemies_killed}击杀"
            )
            logger.info(f"  伤害: {result.player_damage_taken}")
            if result.errors:
                logger.info(f"  错误: {result.errors[0]}")


def main():
    """主函数"""
    logger.info("启动AI Combat System测试套件...")

    # 创建桥接器
    bridge = IsaacBridge(host="127.0.0.1", port=9527)

    # 注册连接事件
    @bridge.on("connected")
    def on_connected(info):
        logger.info(f"游戏已连接: {info['address']}")

    @bridge.on("disconnected")
    def on_disconnected(_):
        logger.warning("游戏已断开连接")

    # 启动服务器
    bridge.start()

    # 等待游戏连接
    logger.info("等待游戏连接...")
    connection_timeout = 60  # 60秒超时
    start_wait = time.time()

    while not bridge.is_connected():
        time.sleep(1)
        if time.time() - start_wait > connection_timeout:
            logger.error("连接超时，游戏未在指定时间内连接")
            bridge.stop()
            return

    logger.info("游戏连接成功!")

    try:
        # 创建测试套件
        test_suite = AITestSuite(bridge)

        # 运行测试
        results = test_suite.run_all_tests()

        # 打印摘要
        test_suite.print_summary()

    finally:
        # 停止服务器
        bridge.stop()
        logger.info("测试完成，服务器已停止")


if __name__ == "__main__":
    main()
