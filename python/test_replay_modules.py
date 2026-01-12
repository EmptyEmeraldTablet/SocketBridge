#!/usr/bin/env python3
"""
SocketBridge 基于真实回放数据的模块化测试

使用录制会话的真实数据来测试各个模块：
1. 从录制数据中提取消息序列
2. 将数据依次输入到各个模块
3. 验证模块输出的正确性和一致性

这样可以确保模块在真实游戏数据流下能正常工作。
"""

import sys
import json
import gzip
import time
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Iterator
from dataclasses import dataclass, field
from collections import defaultdict
import logging

sys.path.insert(0, str(Path(__file__).parent))

from data_replay_system import RawMessage, LuaSimulator
from models import (
    Vector2D,
    PlayerData,
    EnemyData,
    ProjectileData,
    GameStateData,
    RoomInfo,
    ControlOutput,
    ObjectState,
)
from data_processor import DataProcessor, DataParser
from environment import EnvironmentModel
from threat_analysis import ThreatAnalyzer, ThreatLevel, ThreatAssessment
from behavior_tree import BehaviorTree, NodeContext, NodeStatus, BehaviorTreeBuilder
from smart_aiming import SmartAimingSystem, ShotType
from orchestrator_enhanced import EnhancedCombatOrchestrator, AIConfig
from pathfinding import (
    AStarPathfinder,
    DynamicPathPlanner,
    PathExecutor,
    PathfindingConfig,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("ReplayTest")


# ============================================================================
# 回放数据加载器
# ============================================================================


class ReplayDataLoader:
    """回放数据加载器"""

    def __init__(self, session_dir: str = "recordings"):
        self.session_dir = Path(session_dir)

    def find_latest_session(self) -> Optional[str]:
        """查找最新的录制会话"""
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

        return sorted(session_ids, reverse=True)[0]

    def load_messages(self, session_id: str) -> List[RawMessage]:
        """加载会话的所有消息"""
        messages = []

        chunk_files = sorted(self.session_dir.glob(f"{session_id}_chunk_*.json.gz"))

        for chunk_file in chunk_files:
            with gzip.open(chunk_file, "rt", encoding="utf-8") as fp:
                data = json.load(fp)
                for msg_dict in data.get("messages", []):
                    messages.append(RawMessage.from_dict(msg_dict))

        # 按帧和时间排序
        messages = sorted(messages, key=lambda m: (m.frame, m.timestamp))

        return messages

    def get_data_messages(self, session_id: str) -> List[RawMessage]:
        """获取所有DATA类型消息"""
        messages = self.load_messages(session_id)
        return [m for m in messages if m.msg_type == "DATA"]

    def get_event_messages(self, session_id: str) -> List[RawMessage]:
        """获取所有EVENT类型消息"""
        messages = self.load_messages(session_id)
        return [m for m in messages if m.msg_type == "EVENT"]


# ============================================================================
# 测试结果收集
# ============================================================================


@dataclass
class ModuleTestResult:
    """模块测试结果"""

    module_name: str
    passed: bool = False
    total_frames: int = 0
    total_events: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict = field(default_factory=dict)


# ============================================================================
# 模块测试基类
# ============================================================================


class BaseModuleTest:
    """模块测试基类"""

    def __init__(self, loader: ReplayDataLoader):
        self.loader = loader
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.stats: Dict = {}

    def run(self, session_id: str, messages: List[RawMessage]) -> ModuleTestResult:
        """运行测试"""
        raise NotImplementedError


# ============================================================================
# DataProcessor 模块测试
# ============================================================================


class DataProcessorTest(BaseModuleTest):
    """DataProcessor 模块测试"""

    def __init__(self, loader: ReplayDataLoader):
        super().__init__(loader)
        self.processor = DataProcessor()

    def run(self, session_id: str, messages: List[RawMessage]) -> ModuleTestResult:
        """运行 DataProcessor 测试"""
        result = ModuleTestResult(module_name="DataProcessor")

        data_messages = [m for m in messages if m.msg_type == "DATA"]
        event_messages = [m for m in messages if m.msg_type == "EVENT"]

        result.total_frames = len(data_messages)
        result.total_events = len(event_messages)

        # 统计
        frame_count = 0
        player_count = 0
        enemy_count = 0
        projectile_count = 0
        room_changes = 0
        last_room = -1

        # 跟踪实体
        seen_players = set()
        seen_enemies = set()
        seen_projectiles = set()

        for msg in data_messages:
            frame_count += 1

            # 处理消息
            state = self.processor.process_message(msg.to_dict())

            # 统计玩家
            current_players = set(state.players.keys())
            new_players = current_players - seen_players
            if new_players:
                player_count += len(new_players)
                seen_players.update(new_players)

            # 统计敌人
            current_enemies = set(state.enemies.keys())
            new_enemies = current_enemies - seen_enemies
            if new_enemies:
                enemy_count += len(new_enemies)
                seen_enemies.update(new_enemies)

            # 统计投射物
            current_projectiles = set(state.projectiles.keys())
            new_projectiles = current_projectiles - seen_projectiles
            if new_projectiles:
                projectile_count += len(new_projectiles)
                seen_projectiles.update(new_projectiles)

            # 跟踪房间变化
            if state.room_index != last_room and state.room_index > 0:
                room_changes += 1
                last_room = state.room_index

        # 验证结果
        result.stats = {
            "frames_processed": frame_count,
            "unique_players": len(seen_players),
            "unique_enemies": len(seen_enemies),
            "unique_projectiles": len(seen_projectiles),
            "room_changes": room_changes,
        }

        # 基本验证
        if frame_count == 0:
            result.errors.append("未处理任何数据帧")
        if player_count == 0:
            result.warnings.append("未检测到玩家数据")
        if enemy_count == 0:
            result.warnings.append("未检测到敌人数据")

        # 验证帧号递增
        self.processor.reset()
        last_frame = -1
        for msg in data_messages[:100]:  # 只检查前100帧
            self.processor.process_message(msg.to_dict())
            if self.processor.current_state.frame < last_frame:
                result.errors.append(
                    f"帧号未递增: {last_frame} -> {self.processor.current_state.frame}"
                )
            last_frame = self.processor.current_state.frame

        result.passed = len(result.errors) == 0
        return result


# ============================================================================
# ThreatAnalyzer 模块测试
# ============================================================================


class ThreatAnalyzerTest(BaseModuleTest):
    """ThreatAnalyzer 模块测试"""

    def __init__(self, loader: ReplayDataLoader):
        super().__init__(loader)
        self.processor = DataProcessor()
        self.analyzer = ThreatAnalyzer()

    def run(self, session_id: str, messages: List[RawMessage]) -> ModuleTestResult:
        """运行 ThreatAnalyzer 测试"""
        result = ModuleTestResult(module_name="ThreatAnalyzer")

        data_messages = [m for m in messages if m.msg_type == "DATA"]

        # 统计
        threat_levels = defaultdict(int)
        total_assessments = 0
        immediate_threats = 0
        potential_threats = 0

        for msg in data_messages:
            # 处理消息
            state = self.processor.process_message(msg.to_dict())

            # 每10帧分析一次威胁
            if state.frame % 10 == 0:
                assessment = self.analyzer.analyze(state)

                threat_levels[assessment.overall_threat_level.name] += 1
                total_assessments += 1
                immediate_threats += len(assessment.immediate_threats)
                potential_threats += len(assessment.potential_threats)

        result.stats = {
            "total_assessments": total_assessments,
            "threat_level_distribution": dict(threat_levels),
            "total_immediate_threats": immediate_threats,
            "total_potential_threats": potential_threats,
        }

        # 验证
        if total_assessments == 0:
            result.warnings.append("未进行任何威胁评估")

        # 验证威胁等级合理性
        for level_name, count in threat_levels.items():
            if count > 0:
                logger.info(f"  威胁等级 {level_name}: {count} 次")

        result.passed = len(result.errors) == 0
        return result


# ============================================================================
# Environment 模块测试
# ============================================================================


class EnvironmentTest(BaseModuleTest):
    """Environment 模块测试"""

    def __init__(self, loader: ReplayDataLoader):
        super().__init__(loader)
        self.processor = DataProcessor()
        self.env_model = EnvironmentModel()

    def run(self, session_id: str, messages: List[RawMessage]) -> ModuleTestResult:
        """运行 Environment 测试"""
        result = ModuleTestResult(module_name="Environment")

        data_messages = [m for m in messages if m.msg_type == "DATA"]

        # 统计
        room_updates = 0
        obstacle_updates = 0
        safe_spots_found = 0
        escape_routes = 0
        in_bounds_checks = 0
        obstacle_checks = 0

        for msg in data_messages:
            # 处理消息
            state = self.processor.process_message(msg.to_dict())

            # 更新环境模型
            if state.room_info:
                self.env_model.update_room(
                    room_info=state.room_info,
                    enemies=state.enemies,
                    projectiles=state.projectiles,
                )
                room_updates += 1

            # 每20帧进行环境查询
            if state.frame % 20 == 0 and state.get_primary_player():
                player = state.get_primary_player()

                # 检查边界
                in_bounds = self.env_model.game_map.is_in_bounds(player.position)
                in_bounds_checks += 1

                # 检查障碍物
                is_obstacle = self.env_model.game_map.is_obstacle(
                    player.position, margin=15.0
                )
                obstacle_checks += 1

                # 获取安全位置
                safe_pos = self.env_model.get_safe_spot(
                    player.position, min_distance=50, max_distance=150
                )
                if safe_pos:
                    safe_spots_found += 1

                # 寻找逃跑路线
                if len(state.active_enemies) > 0:
                    enemy_positions = [e.position for e in state.active_enemies]
                    route = self.env_model.find_escape_route(
                        player.position, enemy_positions
                    )
                    if route:
                        escape_routes += 1

        result.stats = {
            "room_updates": room_updates,
            "obstacle_updates": obstacle_updates,
            "safe_spots_found": safe_spots_found,
            "escape_routes": escape_routes,
            "in_bounds_checks": in_bounds_checks,
            "obstacle_checks": obstacle_checks,
            "map_width": self.env_model.game_map.pixel_width,
            "map_height": self.env_model.game_map.pixel_height,
        }

        if room_updates == 0:
            result.warnings.append("未更新任何房间")

        result.passed = len(result.errors) == 0
        return result


# ============================================================================
# Pathfinding 模块测试
# ============================================================================


class PathfindingTest(BaseModuleTest):
    """Pathfinding 模块测试"""

    def __init__(self, loader: ReplayDataLoader):
        super().__init__(loader)
        self.processor = DataProcessor()
        self.config = PathfindingConfig()
        self.pathfinder = AStarPathfinder(self.config)
        self.planner = DynamicPathPlanner(self.config)
        self.executor = PathExecutor(self.config)

    def run(self, session_id: str, messages: List[RawMessage]) -> ModuleTestResult:
        """运行 Pathfinding 测试"""
        result = ModuleTestResult(module_name="Pathfinding")

        data_messages = [m for m in messages if m.msg_type == "DATA"]

        # 统计
        path_requests = 0
        paths_found = 0
        path_executions = 0
        total_path_length = 0
        replan_count = 0

        # 模拟障碍物网格
        obstacles = set()

        for msg in data_messages:
            # 处理消息
            state = self.processor.process_message(msg.to_dict())

            player = state.get_primary_player()
            if not player:
                continue

            # 每30帧测试路径规划
            if state.frame % 30 == 0:
                # 动态设置障碍物
                for enemy in state.active_enemies:
                    self.pathfinder.add_dynamic_obstacle(enemy.position, 30.0)

                # 随机选择目标位置
                goal_x = (player.position.x + 100) % 400 + 100
                goal_y = (player.position.y + 100) % 200 + 100
                from models import Vector2D

                goal = Vector2D(goal_x, goal_y)

                # 规划路径
                path = self.planner.plan_path(player.position, goal, obstacles)

                path_requests += 1
                if path:
                    paths_found += 1
                    total_path_length += len(path)

                    # 执行路径
                    move = self.executor.execute_path(player.position, path)
                    if move != (0.0, 0.0):
                        path_executions += 1

                # 检查是否需要重规划
                dynamic_obstacles = [e.position for e in state.active_enemies]
                if self.planner.needs_replan(player.position, dynamic_obstacles):
                    replan_count += 1

                # 清除动态障碍物
                self.pathfinder.clear_dynamic_obstacles()

        if path_requests > 0:
            avg_path_length = total_path_length / path_requests
        else:
            avg_path_length = 0

        result.stats = {
            "path_requests": path_requests,
            "paths_found": paths_found,
            "path_executions": path_executions,
            "avg_path_length": avg_path_length,
            "replan_count": replan_count,
            "success_rate": paths_found / max(path_requests, 1),
        }

        if path_requests == 0:
            result.warnings.append("未进行任何路径规划请求")

        result.passed = len(result.errors) == 0
        return result


# ============================================================================
# BehaviorTree 模块测试
# ============================================================================


class BehaviorTreeTest(BaseModuleTest):
    """BehaviorTree 模块测试"""

    def __init__(self, loader: ReplayDataLoader):
        super().__init__(loader)
        self.processor = DataProcessor()

    def _build_combat_tree(self) -> BehaviorTree:
        """构建战斗行为树"""
        builder = BehaviorTreeBuilder()

        builder.selector("CombatRoot")

        # 优先级1: 躲避投射物
        builder.sequence("Dodge")
        builder.condition("HasProjectiles", lambda ctx: len(ctx.projectiles) > 0)
        builder.action("DodgeAction", lambda ctx: NodeStatus.SUCCESS)
        builder.end()

        # 优先级2: 战斗
        builder.sequence("Combat")
        builder.condition("HasEnemies", lambda ctx: len(ctx.enemies) > 0)
        builder.selector("CombatActions")
        builder.action(
            "Attack",
            lambda ctx: NodeStatus.SUCCESS if ctx.target else NodeStatus.FAILURE,
        )
        builder.end()
        builder.end()

        return builder.build()

    def run(self, session_id: str, messages: List[RawMessage]) -> ModuleTestResult:
        """运行 BehaviorTree 测试"""
        result = ModuleTestResult(module_name="BehaviorTree")

        data_messages = [m for m in messages if m.msg_type == "DATA"]

        # 构建行为树
        tree = self._build_combat_tree()

        # 统计
        executions = 0
        success_count = 0
        failure_count = 0
        running_count = 0

        for msg in data_messages:
            # 处理消息
            state = self.processor.process_message(msg.to_dict())

            # 构建行为树上下文
            ctx = NodeContext()
            ctx.game_state = state

            player = state.get_primary_player()
            if player:
                ctx.player_health = player.health / max(player.max_health, 1)
                ctx.player_position = player.position.to_tuple()

            ctx.enemies = list(state.active_enemies)
            ctx.nearest_enemy = (
                state.get_nearest_enemy(player.position) if player else None
            )
            ctx.projectiles = list(state.enemy_projectiles)

            tree.context = ctx

            # 执行行为树
            result_status = tree.update()
            executions += 1

            if result_status == NodeStatus.SUCCESS:
                success_count += 1
            elif result_status == NodeStatus.FAILURE:
                failure_count += 1
            elif result_status == NodeStatus.RUNNING:
                running_count += 1

        result.stats = {
            "total_executions": executions,
            "success": success_count,
            "failure": failure_count,
            "running": running_count,
        }

        if executions == 0:
            result.warnings.append("未执行任何行为树")

        result.passed = len(result.errors) == 0
        return result


# ============================================================================
# SmartAiming 模块测试
# ============================================================================


class SmartAimingTest(BaseModuleTest):
    """SmartAiming 模块测试"""

    def __init__(self, loader: ReplayDataLoader):
        super().__init__(loader)
        self.processor = DataProcessor()
        self.aiming = SmartAimingSystem()

    def run(self, session_id: str, messages: List[RawMessage]) -> ModuleTestResult:
        """运行 SmartAiming 测试"""
        result = ModuleTestResult(module_name="SmartAiming")

        data_messages = [m for m in messages if m.msg_type == "DATA"]

        # 统计
        aim_calculations = 0
        normal_shots = 0
        spread_shots = 0
        burst_shots = 0
        avg_confidence = 0.0

        for msg in data_messages:
            # 处理消息
            state = self.processor.process_message(msg.to_dict())

            player = state.get_primary_player()
            if not player:
                continue

            # 获取最近的敌人
            target = state.get_nearest_enemy(player.position)
            if not target:
                continue

            # 普通瞄准
            aim_result = self.aiming.aim(
                shooter_pos=player.position,
                target=target,
                shot_type=ShotType.NORMAL,
            )

            aim_calculations += 1
            avg_confidence += aim_result.confidence

            if aim_result.shot_type == ShotType.NORMAL:
                normal_shots += 1
            elif aim_result.shot_type == ShotType.SPREAD:
                spread_shots += 1
            elif aim_result.shot_type == ShotType.BURST:
                burst_shots += 1

        if aim_calculations > 0:
            avg_confidence /= aim_calculations

        result.stats = {
            "aim_calculations": aim_calculations,
            "normal_shots": normal_shots,
            "spread_shots": spread_shots,
            "burst_shots": burst_shots,
            "avg_confidence": avg_confidence,
        }

        if aim_calculations == 0:
            result.warnings.append("未进行任何瞄准计算")

        result.passed = len(result.errors) == 0
        return result


# ============================================================================
# Orchestrator 模块测试
# ============================================================================


class OrchestratorTest(BaseModuleTest):
    """Orchestrator 模块测试"""

    def __init__(self, loader: ReplayDataLoader):
        super().__init__(loader)
        self.config = AIConfig()
        self.orchestrator = EnhancedCombatOrchestrator(self.config)
        self.orchestrator.initialize()

    def run(self, session_id: str, messages: List[RawMessage]) -> ModuleTestResult:
        """运行 Orchestrator 测试"""
        result = ModuleTestResult(module_name="Orchestrator")

        data_messages = [m for m in messages if m.msg_type == "DATA"]

        # 统计
        decisions = 0
        move_decisions = 0
        shoot_decisions = 0
        avg_confidence = 0.0

        strategies_used = defaultdict(int)
        threat_levels = defaultdict(int)

        for msg in data_messages:
            # 更新 AI
            control = self.orchestrator.update(msg.to_dict())

            decisions += 1

            if control.move_x != 0 or control.move_y != 0:
                move_decisions += 1

            if control.shoot:
                shoot_decisions += 1

            avg_confidence += control.confidence

            # 记录策略和威胁
            strategies_used[
                self.orchestrator.debug_info.get("strategy", "UNKNOWN")
            ] += 1
            threat_levels[
                self.orchestrator.debug_info.get("threat_level", "UNKNOWN")
            ] += 1

        if decisions > 0:
            avg_confidence /= decisions

        result.stats = {
            "total_decisions": decisions,
            "move_decisions": move_decisions,
            "shoot_decisions": shoot_decisions,
            "move_ratio": move_decisions / max(decisions, 1),
            "shoot_ratio": shoot_decisions / max(decisions, 1),
            "avg_confidence": avg_confidence,
            "strategies_used": dict(strategies_used),
            "threat_levels": dict(threat_levels),
        }

        if decisions == 0:
            result.errors.append("未生成任何控制决策")

        result.passed = len(result.errors) == 0
        return result


# ============================================================================
# 综合集成测试
# ============================================================================


class IntegrationTest(BaseModuleTest):
    """综合集成测试"""

    def __init__(self, loader: ReplayDataLoader):
        super().__init__(loader)

        # 初始化所有模块
        self.processor = DataProcessor()
        self.analyzer = ThreatAnalyzer()
        self.aiming = SmartAimingSystem()
        self.config = AIConfig()
        self.orchestrator = EnhancedCombatOrchestrator(self.config)
        self.orchestrator.initialize()

    def run(self, session_id: str, messages: List[RawMessage]) -> ModuleTestResult:
        """运行综合集成测试"""
        result = ModuleTestResult(module_name="Integration")

        data_messages = [m for m in messages if m.msg_type == "DATA"]
        event_messages = [m for m in messages if m.msg_type == "EVENT"]

        # 统计
        frame_count = 0
        player_detected = False
        enemy_detected = False
        threat_detected = False
        control_outputs = 0

        event_types = defaultdict(int)

        for msg in data_messages:
            frame_count += 1

            # 1. 处理数据
            state = self.processor.process_message(msg.to_dict())

            # 2. 威胁分析
            assessment = self.analyzer.analyze(state)

            # 3. AI 决策
            control = self.orchestrator.update(msg.to_dict())
            control_outputs += 1

            # 检测各种情况
            if state.get_primary_player():
                player_detected = True

            if len(state.active_enemies) > 0:
                enemy_detected = True

            if assessment.threat_count > 0:
                threat_detected = True

        # 统计事件
        for msg in event_messages:
            if msg.event_type:
                event_types[msg.event_type] += 1

        result.stats = {
            "frames_processed": frame_count,
            "player_detected": player_detected,
            "enemy_detected": enemy_detected,
            "threat_detected": threat_detected,
            "control_outputs": control_outputs,
            "event_types": dict(event_types),
        }

        result.total_frames = frame_count
        result.total_events = len(event_messages)

        # 验证
        if frame_count == 0:
            result.errors.append("未处理任何帧")

        if not player_detected:
            result.warnings.append("回放中未检测到玩家")

        if not enemy_detected:
            result.warnings.append("回放中未检测到敌人")

        result.passed = len(result.errors) == 0
        return result


# ============================================================================
# 测试运行器
# ============================================================================


class ReplayTestRunner:
    """回放测试运行器"""

    def __init__(self, session_dir: str = "recordings"):
        self.loader = ReplayDataLoader(session_dir)
        self.tests: List[BaseModuleTest] = []

    def register_test(self, test: BaseModuleTest):
        """注册测试"""
        self.tests.append(test)

    def run_all(self, session_id: str = None) -> Tuple[bool, Dict]:
        """运行所有测试"""
        # 如果没有指定会话，查找最新的
        if session_id is None:
            session_id = self.loader.find_latest_session()

        if session_id is None:
            logger.error("未找到录制会话")
            return False, {}

        logger.info(f"使用会话: {session_id}")

        # 加载消息
        messages = self.loader.load_messages(session_id)

        logger.info(f"加载了 {len(messages)} 条消息")

        data_count = sum(1 for m in messages if m.msg_type == "DATA")
        event_count = sum(1 for m in messages if m.msg_type == "EVENT")
        logger.info(f"  DATA: {data_count}, EVENT: {event_count}")

        # 运行测试
        results = []
        all_passed = True

        for test in self.tests:
            logger.info(f"\n运行测试: {test.__class__.__name__}")

            result = test.run(session_id, messages)
            results.append(result)

            if result.passed:
                logger.info(f"  ✅ 通过")
            else:
                logger.info(f"  ❌ 失败")
                all_passed = False

            # 打印统计
            for key, value in result.stats.items():
                logger.info(f"    {key}: {value}")

            # 打印错误
            for error in result.errors:
                logger.error(f"    错误: {error}")

            # 打印警告
            for warning in result.warnings:
                logger.warning(f"    警告: {warning}")

        # 汇总结果
        summary = {
            "session_id": session_id,
            "total_messages": len(messages),
            "data_messages": data_count,
            "event_messages": event_count,
            "tests_passed": sum(1 for r in results if r.passed),
            "tests_failed": sum(1 for r in results if not r.passed),
            "results": [
                {
                    "module": r.module_name,
                    "passed": r.passed,
                    "stats": r.stats,
                    "errors": r.errors,
                    "warnings": r.warnings,
                }
                for r in results
            ],
        }

        return all_passed, summary


# ============================================================================
# 主函数
# ============================================================================


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="SocketBridge 基于真实回放数据的模块测试"
    )

    parser.add_argument(
        "--session",
        "-s",
        type=str,
        default=None,
        help="指定会话ID（默认使用最新的会话）",
    )
    parser.add_argument(
        "--dir",
        type=str,
        default="recordings",
        help="录制数据目录（默认: recordings）",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        default=True,
        help="运行所有测试（默认）",
    )
    parser.add_argument(
        "--processor",
        action="store_true",
        help="仅运行 DataProcessor 测试",
    )
    parser.add_argument(
        "--threat",
        action="store_true",
        help="仅运行 ThreatAnalyzer 测试",
    )
    parser.add_argument(
        "--behavior",
        action="store_true",
        help="仅运行 BehaviorTree 测试",
    )
    parser.add_argument(
        "--aiming",
        action="store_true",
        help="仅运行 SmartAiming 测试",
    )
    parser.add_argument(
        "--environment",
        action="store_true",
        help="仅运行 Environment 测试",
    )
    parser.add_argument(
        "--pathfinding",
        action="store_true",
        help="仅运行 Pathfinding 测试",
    )
    parser.add_argument(
        "--orchestrator",
        action="store_true",
        help="仅运行 Orchestrator 测试",
    )
    parser.add_argument(
        "--integration",
        "-i",
        action="store_true",
        help="仅运行综合集成测试",
    )

    args = parser.parse_args()

    # 创建测试运行器
    runner = ReplayTestRunner(args.dir)

    # 注册测试
    run_all = not any(
        [
            args.processor,
            args.threat,
            args.behavior,
            args.aiming,
            args.environment,
            args.pathfinding,
            args.orchestrator,
            args.integration,
        ]
    )

    if run_all or args.processor:
        runner.register_test(DataProcessorTest(runner.loader))

    if run_all or args.environment:
        runner.register_test(EnvironmentTest(runner.loader))

    if run_all or args.pathfinding:
        runner.register_test(PathfindingTest(runner.loader))

    if run_all or args.threat:
        runner.register_test(ThreatAnalyzerTest(runner.loader))

    if run_all or args.behavior:
        runner.register_test(BehaviorTreeTest(runner.loader))

    if run_all or args.aiming:
        runner.register_test(SmartAimingTest(runner.loader))

    if run_all or args.orchestrator:
        runner.register_test(OrchestratorTest(runner.loader))

    if run_all or args.integration:
        runner.register_test(IntegrationTest(runner.loader))

    # 运行测试
    print("\n" + "=" * 70)
    print("SocketBridge 基于真实回放数据的模块测试")
    print("=" * 70)

    all_passed, summary = runner.run_all(args.session)

    # 打印汇总
    print("\n" + "=" * 70)
    print("测试汇总")
    print("=" * 70)
    print(f"会话: {summary['session_id']}")
    print(
        f"总消息数: {summary['total_messages']} (DATA: {summary['data_messages']}, EVENT: {summary['event_messages']})"
    )
    print(f"测试通过: {summary['tests_passed']}")
    print(f"测试失败: {summary['tests_failed']}")
    print("=" * 70)

    if all_passed:
        print("🎉 所有模块测试通过!")
    else:
        print("❌ 有测试失败")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
