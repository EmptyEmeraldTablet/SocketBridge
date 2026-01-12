"""
SocketBridge Complete AI Agent

Integrates all modules for complete game AI control:
- DataProcessor: Game data parsing
- EnvironmentModel: Environmental awareness
- ThreatAnalyzer: Threat assessment
- SmartAimingSystem: Smart aiming
- BehaviorTree: Tactical decision making
- Pathfinding: A* path planning
- EvaluationSystem: Performance evaluation

Usage:
1. Replay test: python socket_ai_agent.py --replay
2. Real-time game: python socket_ai_agent.py --realtime
"""

import sys
import time
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent))

from models import Vector2D, GameStateData, ControlOutput, PlayerData, EnemyData
from data_processor import DataProcessor
from environment import EnvironmentModel
from threat_analysis import ThreatAnalyzer, ThreatLevel, ThreatAssessment, ThreatInfo
from smart_aiming import SmartAimingSystem, ShotType, AimResult
from behavior_tree import BehaviorTree, NodeContext, NodeStatus, BehaviorTreeBuilder
from pathfinding import AStarPathfinder, PathfindingConfig
from evaluation_system import EvaluationSystem

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("SocketAIAgent")


class MovementMode(Enum):
    KITING = "kiting"
    AGGRESSIVE = "aggressive"
    DEFENSIVE = "defensive"
    BALANCED = "balanced"


@dataclass
class AIConfig:
    decision_interval: float = 0.016
    aim_interval: int = 1
    combat_distance: float = 150.0
    retreat_health_threshold: float = 0.3
    shoot_confidence_threshold: float = 0.6
    movement_mode: str = "balanced"
    pathfinding_enabled: bool = True
    stay_in_bounds: bool = True
    evaluation_enabled: bool = True
    verbose_output: bool = False


class SocketAIAgent:
    """Complete AI Agent integrating all modules."""

    def __init__(self, config: Optional[AIConfig] = None):
        self.config = config if config is not None else AIConfig()
        self.enabled = True

        self._init_modules()
        self.current_frame = 0
        self.performance = {
            "total_frames": 0,
            "total_decisions": 0,
            "avg_decision_time_ms": 0.0,
        }

        logger.info("SocketAIAgent initialized")

    def _init_modules(self):
        # Phase 1: Data processing
        self.data_processor = DataProcessor()

        # Phase 2: Environment awareness
        self.environment = EnvironmentModel()

        # Phase 3: Threat analysis
        self.threat_analyzer = ThreatAnalyzer()

        # Phase 4: Smart aiming
        self.aiming = SmartAimingSystem()

        # Phase 5: Behavior tree
        self.behavior_tree = self._build_behavior_tree()

        # Phase 6: Pathfinding
        path_config = PathfindingConfig(
            grid_size=40.0, allow_diagonal=True, smoothing_enabled=True
        )
        self.pathfinder = AStarPathfinder(path_config)

        # Phase 7: Performance evaluation
        self.evaluation = EvaluationSystem()

        self.current_threat = None
        self.target_enemy_id = None

    def _build_behavior_tree(self) -> BehaviorTree:
        builder = BehaviorTreeBuilder()
        builder.selector("CombatRoot")

        # Priority 1: Emergency dodge
        builder.sequence("EmergencyDodge")
        builder.condition("HasThreats", lambda ctx: len(ctx.projectiles) > 0)
        builder.action("Dodge", lambda ctx: NodeStatus.SUCCESS)
        builder.end()

        # Priority 2: Combat
        builder.sequence("Combat")
        builder.condition("HasEnemies", lambda ctx: len(ctx.enemies) > 0)
        builder.selector("CombatActions")
        builder.action("Attack", lambda ctx: NodeStatus.SUCCESS)
        builder.end()
        builder.end()

        # Priority 3: Explore
        builder.sequence("Explore")
        builder.condition("NoEnemies", lambda ctx: len(ctx.enemies) == 0)
        builder.action("Explore", lambda ctx: NodeStatus.SUCCESS)
        builder.end()

        return builder.build()

    def initialize(self):
        logger.info("SocketAIAgent initialized successfully")

    def update(self, raw_message: Dict[str, Any]) -> ControlOutput:
        if not self.enabled:
            return ControlOutput()

        start_time = time.time()
        self.current_frame += 1
        control = ControlOutput()

        try:
            # === DEBUG: 打印原始消息结构 ===
            if self.config.verbose_output and self.current_frame <= 5:
                print(f"[DEBUG] update() frame={self.current_frame}")
                print(f"[DEBUG]   raw_message type: {type(raw_message)}")
                if isinstance(raw_message, dict):
                    print(f"[DEBUG]   raw_message keys: {list(raw_message.keys())}")
                    if "payload" in raw_message:
                        payload = raw_message["payload"]
                        print(f"[DEBUG]   payload type: {type(payload)}")
                        if isinstance(payload, dict):
                            print(f"[DEBUG]   payload keys: {list(payload.keys())}")
                        else:
                            print(f"[DEBUG]   payload value: {payload}")
                    else:
                        print(f"[DEBUG]   NO 'payload' key in raw_message!")
                else:
                    print(f"[DEBUG]   raw_message is not a dict!")

            # 1. Process game data
            game_state = self.data_processor.process_message(raw_message)

            # === DEBUG: 验证处理结果 ===
            if self.config.verbose_output and self.current_frame <= 10:
                print(f"[DEBUG] After process_message:")
                print(f"[DEBUG]   frame: {game_state.frame}")
                print(f"[DEBUG]   players: {list(game_state.players.keys())}")
                print(f"[DEBUG]   player count: {len(game_state.players)}")
                print(f"[DEBUG]   enemies: {len(game_state.active_enemies)}")
                print(f"[DEBUG]   room_info: {game_state.room_info is not None}")

            # === DEBUG: 打印房间信息（关键：grid_width和grid_height）===
            if self.config.verbose_output and self.current_frame % 30 == 0:
                if game_state.room_info:
                    # 计算房间边界（假设每个格子40像素）
                    room_left = 280  # 从Lua端获取的固定偏移
                    room_top = 140
                    room_width = game_state.room_info.grid_width * 40
                    room_height = game_state.room_info.grid_height * 40
                    room_right = room_left + room_width
                    room_bottom = room_top + room_height

                    print(
                        f"[DEBUG-ROOM] grid={game_state.room_info.grid_width}x{game_state.room_info.grid_height}, "
                        f"bounds=({room_left},{room_top})-({room_right},{room_bottom}), "
                        f"enemy_count={game_state.room_info.enemy_count}"
                    )
                else:
                    print("[DEBUG-ROOM] No room_info available")

            player = game_state.get_primary_player()

            if not player:
                return control

            # 2. Update environment
            if game_state.room_info:
                self.environment.update_room(
                    room_info=game_state.room_info,
                    enemies=game_state.enemies,
                    projectiles=game_state.projectiles,
                    room_layout=game_state.raw_room_layout,
                )

            # 3. Threat analysis
            threat = self.threat_analyzer.analyze(game_state)
            self.current_threat = threat

            # 4. Target selection
            target_enemy = self._select_target(game_state, threat)
            if target_enemy:
                self.target_enemy_id = target_enemy.id

            # 5. Smart aiming
            aim_result = None
            if target_enemy and self.current_frame % self.config.aim_interval == 0:
                shot_type = ShotType.NORMAL
                aim_result = self.aiming.aim(
                    shooter_pos=player.position,
                    target=target_enemy,
                    shot_type=shot_type,
                    check_los=True,
                    environment_los_checker=self.environment,
                )

                # DEBUG: 打印瞄准结果和视线状态
                if self.config.verbose_output and self.current_frame % 30 == 0:
                    los_status = self.aiming.last_los_result or "N/A"
                    if target_enemy:
                        print(
                            f"[DEBUG-AIM] Target={target_enemy.id} LOS={los_status} "
                            f"Conf={aim_result.confidence:.2f} Reason={aim_result.reasoning} "
                            f"TargetPos=({target_enemy.position.x:.0f},{target_enemy.position.y:.0f})"
                        )

            # 6. Movement computation
            move_x, move_y = self._compute_movement(
                game_state, player, threat, target_enemy
            )

            # DEBUG: 检查移动目标位置是否可走
            if self.config.verbose_output and self.current_frame % 30 == 0:
                if move_x != 0 or move_y != 0:
                    target_pos = Vector2D(
                        player.position.x + move_x * 50, player.position.y + move_y * 50
                    )
                    in_bounds = self.environment.game_map.is_in_bounds(target_pos)
                    has_obstacle = self.environment.game_map.is_obstacle(
                        target_pos, 15.0
                    )
                    can_reach = self.environment.can_reach_position(
                        player.position, target_pos
                    )

                    # 额外调试：检查玩家当前位置是否在边界内
                    player_in_bounds = self.environment.game_map.is_in_bounds(
                        player.position
                    )

                    print(
                        f"[DEBUG-MOVE] Move=({move_x:.2f},{move_y:.2f}) "
                        f"Player=({player.position.x:.0f},{player.position.y:.0f})->Target=({target_pos.x:.0f},{target_pos.y:.0f}) "
                        f"PlayerInBounds={player_in_bounds} TargetInBounds={in_bounds} Obstacle={has_obstacle} CanReach={can_reach}"
                    )

            control.move_x = int(max(-1, min(1, move_x)))
            control.move_y = int(max(-1, min(1, move_y)))

            # 7. Shooting decision
            if (
                aim_result
                and aim_result.confidence > self.config.shoot_confidence_threshold
            ):
                control.shoot = True
                dx, dy = self._vector_to_direction(aim_result.direction)
                control.shoot_x = dx
                control.shoot_y = dy
            elif target_enemy:
                direction = target_enemy.position - player.position
                if direction.magnitude() > 0:
                    dx, dy = self._vector_to_direction(direction)
                    control.shoot = True
                    control.shoot_x = dx
                    control.shoot_y = dy

            # 8. Behavior tree
            bt_context = self._build_behavior_context(game_state, threat)
            self.behavior_tree.context = bt_context
            self.behavior_tree.update()

            # 9. Bounds check
            if self.config.stay_in_bounds:
                control = self._apply_bounds_check(control, player, game_state)

            # 10. Evaluation
            if self.config.evaluation_enabled:
                self.evaluation.update(
                    decision="attack" if control.shoot else "move",
                    action="attack" if control.shoot else "move",
                    outcome="partial",
                    latency_ms=(time.time() - start_time) * 1000,
                    state=raw_message,
                )

            # Statistics
            decision_time = (time.time() - start_time) * 1000
            self.performance["total_frames"] += 1
            self.performance["total_decisions"] += 1
            self.performance["avg_decision_time_ms"] = (
                self.performance["avg_decision_time_ms"] * 0.9 + decision_time * 0.1
            )

        except Exception as e:
            logger.error(f"Error in AI update: {e}")

        return control

    def _select_target(
        self, game_state: GameStateData, threat: ThreatAssessment
    ) -> Optional[EnemyData]:
        player = game_state.get_primary_player()
        if not player:
            return None

        if threat.immediate_threats:
            for t in threat.immediate_threats:
                if t.source_id in game_state.enemies:
                    return game_state.enemies[t.source_id]

        return game_state.get_nearest_enemy(player.position)

    def _compute_movement(
        self,
        game_state: GameStateData,
        player: PlayerData,
        threat: ThreatAssessment,
        target: Optional[EnemyData],
    ) -> Tuple[float, float]:
        move_x, move_y = 0.0, 0.0

        # 1. Emergency evasion
        if threat.immediate_threats:
            evasion = self._compute_evasion(player, threat.immediate_threats)
            return self._normalize_direction(evasion)

        # 2. Combat distance control
        if target:
            direction = target.position - player.position
            distance = direction.magnitude()

            if distance > self.config.combat_distance:
                move_x, move_y = self._normalize_direction(direction)
            elif distance < self.config.combat_distance * 0.5:
                retreat = Vector2D(-direction.x, -direction.y)
                move_x, move_y = self._normalize_direction(retreat)
            else:
                perpendicular = Vector2D(-direction.y, direction.x)
                move_x, move_y = self._normalize_direction(perpendicular)

        # 3. Explore mode
        if not target and game_state.room_info:
            center = Vector2D(
                game_state.room_info.grid_width * 40 / 2,
                game_state.room_info.grid_height * 40 / 2,
            )
            direction = center - player.position
            move_x, move_y = self._normalize_direction(direction)

        return move_x, move_y

    def _compute_evasion(
        self, player: PlayerData, threats: List[ThreatInfo]
    ) -> Vector2D:
        evasion = Vector2D(0, 0)
        for t in threats:
            direction = player.position - t.position
            distance = direction.magnitude()
            if distance > 0:
                weight = 80.0 / distance
                norm_x = direction.x / distance
                norm_y = direction.y / distance
                evasion.x += norm_x * weight
                evasion.y += norm_y * weight
        return evasion if evasion.magnitude() > 0 else Vector2D(1, 0)

    def _normalize_direction(self, direction: Vector2D) -> Tuple[float, float]:
        mag = direction.magnitude()
        if mag < 0.1:
            return 0.0, 0.0
        return direction.x / mag, direction.y / mag

    def _vector_to_direction(self, vec: Vector2D) -> Tuple[int, int]:
        x, y = 0, 0
        threshold = 0.3
        if vec.x > threshold:
            x = 1
        elif vec.x < -threshold:
            x = -1
        if vec.y > threshold:
            y = 1
        elif vec.y < -threshold:
            y = -1
        return x, y

    def _build_behavior_context(
        self, game_state: GameStateData, threat: ThreatAssessment
    ) -> NodeContext:
        player = game_state.get_primary_player()
        context = NodeContext()
        context.game_state = game_state
        context.enemies = list(game_state.active_enemies)
        context.projectiles = [t.source_id for t in threat.immediate_threats]

        if player:
            context.player_health = player.health / max(player.max_health, 1)
            context.player_position = player.position.to_tuple()
            context.nearest_enemy = game_state.get_nearest_enemy(player.position)

        context.threat_level = threat.overall_threat_level.value / 3
        return context

    def _apply_bounds_check(
        self, control: ControlOutput, player: PlayerData, game_state: GameStateData
    ) -> ControlOutput:
        if not self.environment.game_map.is_in_bounds(player.position):
            if player.position.x < 50:
                control.move_x = 1
            elif player.position.x > 470:
                control.move_x = -1
            if player.position.y < 50:
                control.move_y = 1
            elif player.position.y > 230:
                control.move_y = -1
        return control

    def get_performance_stats(self) -> Dict[str, Any]:
        return {
            **self.performance,
            "evaluation": self.evaluation.get_performance_summary()
            if self.config.evaluation_enabled
            else None,
        }

    def reset(self):
        self.data_processor.reset()
        self.pathfinder.clear_dynamic_obstacles()
        if self.config.evaluation_enabled:
            self.evaluation.reset()
        self.current_frame = 0

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False


def run_replay_test(session_id: Optional[str] = None, verbose: bool = False):
    from data_replay_system import LuaSimulator
    import gzip
    import json
    from pathlib import Path

    print("\n" + "=" * 60)
    print("SocketAIAgent Replay Test")
    print("=" * 60)

    agent = SocketAIAgent(AIConfig(verbose_output=verbose))
    agent.initialize()

    # Find and load session
    recordings_dir = Path("recordings")
    if not recordings_dir.exists():
        print("No recordings directory found")
        return

    if session_id is None:
        chunks = list(recordings_dir.glob("*_chunk_*.json.gz"))
        if chunks:
            session_id = chunks[0].name.rsplit("_chunk_", 1)[0]

    if session_id is None:
        print("No replay session found")
        return

    print(f"Using session: {session_id}")

    # Load messages directly
    messages = []
    for chunk_file in sorted(recordings_dir.glob(f"{session_id}_chunk_*.json.gz")):
        with gzip.open(chunk_file, "rt", encoding="utf-8") as fp:
            data = json.load(fp)
            for msg_dict in data.get("messages", []):
                from data_replay_system import RawMessage

                messages.append(RawMessage.from_dict(msg_dict))

    data_messages = [m for m in messages if m.msg_type == "DATA"]
    print(f"Loaded {len(data_messages)} frames")

    frame_count = 0
    shoot_count = 0

    for msg in data_messages:
        control = agent.update(msg.to_dict())
        if control.shoot:
            shoot_count += 1
        frame_count += 1

        if verbose and frame_count % 100 == 0:
            threat = agent.current_threat
            threat_level = threat.overall_threat_level.name if threat else "N/A"
            print(
                f"Frame {frame_count}: Threat={threat_level}, Move=({control.move_x},{control.move_y}), Shoot={control.shoot}"
            )

    print("\n" + "-" * 60)
    print(f"Total frames: {frame_count}")
    print(
        f"Shoot frames: {shoot_count} ({shoot_count / max(1, frame_count) * 100:.1f}%)"
    )
    print(f"Avg decision time: {agent.performance['avg_decision_time_ms']:.2f}ms")

    if agent.config.evaluation_enabled:
        print("\n" + "-" * 60)
        print("Performance Evaluation:")
        print(agent.get_performance_stats().get("evaluation", "N/A"))

    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)


def run_realtime_test(host: str = "127.0.0.1", port: int = 9527):
    from isaac_bridge import IsaacBridge

    print("\n" + "=" * 60)
    print("SocketAIAgent Real-time Game Test")
    print(f"Connecting to: {host}:{port}")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    agent = SocketAIAgent(AIConfig(verbose_output=True))
    agent.initialize()

    bridge = IsaacBridge(host=host, port=port)

    @bridge.on("connected")
    def on_connected(info):
        print(f"Connected to {info['address']}")

    @bridge.on("disconnected")
    def on_disconnected():
        print("Disconnected")
        agent.disable()

    @bridge.on("data")
    def on_data(data):
        # === DEBUG: 打印原始数据 ===
        if agent.current_frame <= 3:
            print(
                f"[DEBUG] on_data called - type: {type(data)}, keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}"
            )

        # === 修复：重新组织数据格式 ===
        # IsaacBridge 的 "data" 回调直接发送 payload dict
        # DataProcessor.process_message() 需要完整的消息结构
        raw_message = {
            "type": "DATA",
            "frame": bridge.state.frame,
            "room_index": bridge.state.room_index,
            "timestamp": 0,
            "payload": data,
            "channels": list(data.keys()) if isinstance(data, dict) else [],
        }

        # === DEBUG: 验证重组后的数据 ===
        if agent.current_frame <= 3:
            print(
                f"[DEBUG] restructured: frame={raw_message['frame']}, room={raw_message['room_index']}"
            )
            print(f"[DEBUG] payload keys: {list(raw_message['payload'].keys())}")

        control = agent.update(raw_message)

        # === DEBUG: 打印处理结果 ===
        if agent.current_frame <= 10 and agent.current_frame % 5 == 0:
            state = agent.data_processor.current_state
            print(
                f"[DEBUG] After update - frame: {state.frame}, players: {list(state.players.keys())}, enemies: {len(state.active_enemies)}"
            )
            print(f"[DEBUG] Current threat: {agent.current_threat}")

        if agent.enabled and (
            control.move_x != 0 or control.move_y != 0 or control.shoot
        ):
            if control.shoot:
                bridge.send_input(
                    move=(control.move_x, control.move_y),
                    shoot=(control.shoot_x, control.shoot_y),
                )
            else:
                bridge.send_input(move=(control.move_x, control.move_y))

        if agent.current_frame % 30 == 0:
            state = agent.data_processor.current_state
            player = state.get_primary_player()
            threat = agent.current_threat

            player_info = (
                f"PlayerPos: ({player.position.x:.1f},{player.position.y:.1f})"
                if player
                else "NoPlayer"
            )
            enemy_count = len(state.active_enemies)
            threat_level = threat.overall_threat_level.name if threat else "N/A"

            # === DEBUG: 环境状态 ===
            env = agent.environment
            if hasattr(env, "game_map") and env.game_map:
                game_map = env.game_map
                map_size = f"MapSize: {game_map.width}x{game_map.height} ({game_map.pixel_width}x{game_map.pixel_height}px)"
                static_obs = len(game_map.static_obstacles)
                dynamic_obs = len(game_map.dynamic_obstacles)
                env_info = f" StaticObs: {static_obs}, DynamicObs: {dynamic_obs}"
            else:
                map_size = "No map"
                env_info = ""

            print(
                f"Frame {agent.current_frame:5d} | {player_info:20} | Enemies: {enemy_count:2} | "
                f"Threat: {threat_level:8} | Move: ({control.move_x:2},{control.move_y:2}) | Shoot: {control.shoot}"
            )
            print(f"                | {map_size}{env_info}")

    @bridge.on("event:PLAYER_DAMAGE")
    def on_damage(data):
        print(f"\nPlayer damaged! HP: {data.get('hp_after', '?')}")

    @bridge.on("event:NPC_DEATH")
    def on_npc_death(data):
        print(f"\nEnemy killed!")

    bridge.start()

    try:
        while bridge.running:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopping...")
        agent.disable()
        bridge.stop()


def main():
    parser = argparse.ArgumentParser(description="SocketAIAgent - Complete AI System")
    parser.add_argument("--replay", action="store_true", help="Run replay test")
    parser.add_argument(
        "--realtime", action="store_true", help="Run real-time game test"
    )
    parser.add_argument("--session", type=str, default=None, help="Replay session ID")
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Game server address"
    )
    parser.add_argument("--port", type=int, default=9527, help="Game server port")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.replay:
        run_replay_test(args.session, args.verbose)
    elif args.realtime:
        run_realtime_test(args.host, args.port)
    else:
        run_replay_test(args.session, args.verbose)


if __name__ == "__main__":
    main()
