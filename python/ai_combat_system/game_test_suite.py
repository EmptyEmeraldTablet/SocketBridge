"""
AI Combat System - 游戏测试脚本

功能:
1. 利用控制台指令搭建游戏测试场景
2. 测试AI Combat System各模块的实际表现
3. 安全的spawn机制，防止游戏崩溃

注意事项:
- spawn指令有严格冷却时间（默认3秒）
- 每次测试场景的敌人生成数量有限制
- 包含自动清理机制

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
class SpawnConfig:
    """生成配置"""

    # 冷却时间（秒）- 防止过度生成导致游戏崩溃，20秒以上
    spawn_cooldown: float = 20.0
    # 单次测试最大生成数量
    max_per_spawn: int = 2
    # 房间内最大敌人数量（通过游戏数据检测）
    max_enemies_in_room: int = 6
    # 生成间隔（帧）
    spawn_interval_frames: int = 60


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


class SafeSpawner:
    """
    安全生成器 - 防止过度生成导致游戏崩溃

    保护措施:
    1. 生成冷却时间
    2. 单次生成数量限制
    3. 总体敌人数量限制
    4. 生成间隔控制
    """

    # 安全的敌人类型列表（低风险）
    SAFE_ENEMIES = {
        # 基础敌人
        "10.0.0": "Fly (基础飞行敌人)",
        "10.0.1": "Fly (Champion)",
        "11.0.0": "Spider (基础蜘蛛)",
        "11.0.1": "Spider (Big)",
        "2001.0": "Globin (史莱姆)",
        "2002.0": "Cochleary (蜗牛)",
        # 中级敌人
        "18.0.0": "Maw (大嘴)",
        "19.0.0": "Horf (呕吐怪)",
        "20.0.0": "Knife (飞刀)",
        "24.0.0": "Leaper (跳跃者)",
        "26.0.0": "Baby (小宝宝)",
    }

    # 中等风险的敌人（需要谨慎使用）
    MEDIUM_RISK_ENEMIES = {
        "12.0.0": "Sucker (攻击型蜘蛛)",
        "13.0.0": "Boil (沸水怪)",
        "14.0.0": "Bouncer (弹跳者)",
        "15.0.0": "Dingbat (蝙蝠)",
        "17.0.0": "Mr.Maw (双头怪)",
        "21.0.0": "Pinky (粉红敌人)",
        "22.0.0": "Mom's Dead Hand (妈妈的手)",
        "23.0.0": "Mom's Hand (妈妈的手)",
        "25.0.0": "Scarred Baby (伤疤宝宝)",
    }

    def __init__(self, bridge: IsaacBridge, config: Optional["SpawnConfig"] = None):
        self.bridge = bridge
        self.config = config or SpawnConfig()
        self.last_spawn_time = 0
        self.total_spawned = 0
        self.spawn_lock = threading.Lock()

    def get_current_enemy_count(self) -> int:
        """
        从游戏数据获取当前房间内的敌人数量

        Returns:
            int: 当前敌人数量
        """
        try:
            enemies_data = self.bridge.get_channel("ENEMIES")
            if enemies_data is None:
                return 0
            if isinstance(enemies_data, list):
                return len(enemies_data)
            elif isinstance(enemies_data, dict):
                return len(enemies_data.get("enemies", []))
            return 0
        except Exception:
            return 0

    def can_spawn(self) -> Tuple[bool, str]:
        """
        检查是否可以生成（基于冷却时间和当前敌人数量）

        Returns:
            Tuple[bool, str]: (是否可以生成, 原因)
        """
        current_time = time.time()

        # 1. 冷却时间检查（主要限制）
        time_since_last = current_time - self.last_spawn_time
        if time_since_last < self.config.spawn_cooldown:
            remaining = self.config.spawn_cooldown - time_since_last
            return False, f"冷却中，{remaining:.1f}秒后可生成"

        # 2. 当前房间敌人数量检查
        current_count = self.get_current_enemy_count()
        if current_count >= self.config.max_enemies_in_room:
            return False, f"房间内已有 {current_count} 个敌人，达到上限"

        return True, "可以生成"

    def spawn_enemy(
        self, enemy_type: str, count: int = 1, champion: bool = False
    ) -> bool:
        """
        安全生成敌人

        Args:
            enemy_type: 敌人类型 (格式: "type.variant.subtype")
            count: 生成数量
            champion: 是否生成Champion版本

        Returns:
            bool: 生成是否成功
        """
        with self.spawn_lock:
            can_spawn, reason = self.can_spawn()
            if not can_spawn:
                logger.warning(f"无法生成: {reason}")
                return False

            # 检查生成数量限制（单次最多2个）
            actual_count = min(count, self.config.max_per_spawn)

            # 获取当前敌人数量
            current_count = self.get_current_enemy_count()
            remaining_slots = self.config.max_enemies_in_room - current_count
            actual_count = min(actual_count, remaining_slots)

            if actual_count <= 0:
                logger.warning("房间敌人数量已达上限")
                return False

            # 构建spawn命令
            cmd_parts = ["spawn"]
            cmd_parts.append(enemy_type)

            # 生成敌人
            success = True
            spawned_count = 0
            for i in range(actual_count):
                cmd = ".".join(cmd_parts)
                if champion:
                    cmd += ".0.1"  # Champion flag

                result = self.bridge.send_console_command(cmd)
                if result:
                    self.total_spawned += 1
                    spawned_count += 1
                    logger.info(f"生成敌人: {enemy_type}")
                    time.sleep(0.5)  # 短暂延迟，防止命令堆积
                else:
                    success = False
                    logger.error(f"生成失败: {enemy_type}")

            if success and spawned_count > 0:
                self.last_spawn_time = time.time()
                logger.info(
                    f"本次生成 {spawned_count} 个敌人，房间现有 {current_count + spawned_count} 个"
                )

            return success

    def spawn_single_enemy(self, enemy_key: str) -> bool:
        """生成单个敌人（使用预定义的敌人键）"""
        enemy_type = self.SAFE_ENEMIES.get(enemy_key)
        if not enemy_type:
            logger.error(f"未知的敌人键: {enemy_key}")
            return False
        return self.spawn_enemy(enemy_key)

    def clear_enemies(self):
        """清理当前房间的敌人"""
        # 使用游戏命令清理敌人
        self.bridge.send_console_command("gridspawn 9")  # 清理所有敌人
        time.sleep(0.5)
        logger.info("已清理房间敌人")

    def get_status(self) -> Dict:
        """获取生成器状态"""
        current_count = self.get_current_enemy_count()
        time_since = time.time() - self.last_spawn_time
        return {
            "total_spawned": self.total_spawned,
            "current_enemies": current_count,
            "can_spawn": self.can_spawn()[0],
            "cooldown_remaining": max(0, self.config.spawn_cooldown - time_since),
            "max_enemies_allowed": self.config.max_enemies_in_room,
        }


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

        # 测试配置
        self.spawn_config = SpawnConfig()
        self.spawner = SafeSpawner(bridge, self.spawn_config)

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

        # 获取生成的敌人总数
        enemies_spawned = self.spawner.total_spawned

        result = TestResult(
            scenario=scenario.value,
            success=len(errors) == 0,
            frame_count=self.test_frame_count,
            enemies_spawned=enemies_spawned,
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
            self.spawner.clear_enemies()

        elif scenario == TestScenario.SINGLE_ENEMY:
            # 单个敌人
            self.spawner.clear_enemies()
            time.sleep(1)
            self.spawner.spawn_single_enemy("10.0.0")  # Fly

        elif scenario == TestScenario.FEW_ENEMIES:
            # 少量敌人 (3-5个)
            self.spawner.clear_enemies()
            time.sleep(1)
            enemies = ["10.0.0", "11.0.0", "2001.0"]
            for enemy in enemies:
                self.spawner.spawn_single_enemy(enemy)
                time.sleep(1)  # 间隔生成

        elif scenario == TestScenario.MANY_ENEMIES:
            # 多个敌人
            self.spawner.clear_enemies()
            time.sleep(1)
            enemies = ["10.0.0", "10.0.0", "11.0.0", "11.0.0", "2001.0", "2002.0"]
            for i, enemy in enumerate(enemies):
                self.spawner.spawn_single_enemy(enemy)
                time.sleep(1.5)

        elif scenario == TestScenario.PROJECTILE_TEST:
            # 投射物测试 - 使用会发射投射物的敌人
            self.spawner.clear_enemies()
            time.sleep(1)
            # Horf (18.0.0) 会呕吐投射物
            self.spawner.spawn_enemy("18.0.0", 2)

        elif scenario == TestScenario.MIXED_TEST:
            # 混合测试
            self.spawner.clear_enemies()
            time.sleep(1)
            # 生成不同类型的敌人组合
            spawn_tasks = [
                ("10.0.0", 2),
                ("18.0.0", 1),
                ("11.0.0", 2),
                ("2001.0", 1),
            ]
            for enemy_type, count in spawn_tasks:
                self.spawner.spawn_enemy(enemy_type, count)
                time.sleep(2)

        elif scenario == TestScenario.SURVIVAL:
            # 生存测试 - 生成较多敌人
            self.spawner.clear_enemies()
            time.sleep(1)
            # 分批生成敌人
            for i in range(3):
                self.spawner.spawn_enemy("10.0.0", 3)
                self.spawner.spawn_enemy("11.0.0", 2)
                time.sleep(5)  # 等待清理后再生成

    def _cleanup_scenario(self, scenario: TestScenario):
        """清理测试场景"""
        logger.info(f"清理场景: {scenario.value}")
        self.spawner.clear_enemies()

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

            # 检查是否可以继续测试
            if not self.spawner.can_spawn():
                logger.warning("生成冷却中，跳过此测试...")
                continue

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
