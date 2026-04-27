"""
SocketBridge — unified entry point for v3.0 architecture.

Replaces: isaac_bridge.py (IsaacBridge + GameDataAccessor),
         core/connection/adapter.py (BridgeAdapter),
         services/facade.py (SocketBridgeFacade)

Single class that integrates:
- connection/    — async TCP server
- protocol/      — message parsing and validation
- sensors/       — data parsing and normalization
- entities/      — entity identity tracking across frames
- persistence/   — recording and replay
- validation/    — quality monitoring

Usage:
    bridge = SocketBridge()
    await bridge.start()
    await bridge.subscribe(["ENEMIES", "PLAYER_POSITION"])

    @bridge.on_frame
    def on_frame(frame, room):
        enemies = bridge.get_enemies()
        player = bridge.get_player()
        ...
"""

import asyncio
import logging
from typing import Optional, Callable, Any, Awaitable

from connection.server import BridgeServer
from protocol.messages import RawMessage
from protocol.schema import (
    PlayerPosition, PlayerStats, PlayerHealth, PlayerInventory,
    Enemy, Projectile, Laser, Projectiles, Pickup, Bomb, FireHazard,
    RoomInfo, RoomLayout, GridEntity, Interactable,
    DataMessage, SubscribeRequest, SubscribeAck,
    MessageType, Vector2D,
)
from sensors.base import SensorRegistry
from entities.tracker import GameEntityStore, EntityChanges
from persistence.recorder import SessionRecorder, RecorderConfig
from persistence.replayer import SessionReplayer, ReplayerConfig
from validation.monitor import QualityMonitor

logger = logging.getLogger(__name__)


class SocketBridge:
    """
    Unified SocketBridge entry point.

    Connects to the game via TCP, processes all data through the sensor
    pipeline, tracks entity identity across frames, and provides a clean
    typed API for applications.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9527,
                 entity_state_enabled: bool = True,
                 recording_enabled: bool = False,
                 recordings_dir: str = "./recordings"):
        self.host = host
        self.port = port

        # Layers
        self._server = BridgeServer(host, port)
        self._entities = GameEntityStore() if entity_state_enabled else None
        self._monitor = QualityMonitor()
        self._recorder: Optional[SessionRecorder] = None
        if recording_enabled:
            self._recorder = SessionRecorder(RecorderConfig(output_dir=recordings_dir))

        # State
        self._connected: bool = False
        self._frame: int = 0
        self._room: int = -1
        self._prev_room: int = -1
        self._message_count: int = 0

        # Cached parsed data (per-sensor, by name)
        self._data: dict[str, Any] = {}

        # Per-frame callbacks
        self._on_frame: list[Callable[[int, int], Any]] = []
        # Event callbacks: event_name → [callbacks]
        self._on_event: dict[str, list[Callable[[dict], Any]]] = {}
        # Raw message callbacks
        self._on_message: list[Callable[[RawMessage], Any]] = []

        # Setup internal message handler
        self._server.on_message(self._handle_message)
        self._server.on_connected(self._on_game_connected)
        self._server.on_disconnected(self._on_game_disconnected)

    # ══════════════════════════════════════════════════════════════════════
    # Lifecycle
    # ══════════════════════════════════════════════════════════════════════

    async def start(self) -> None:
        await self._server.start()

    async def stop(self) -> None:
        if self._recorder and self._recorder.is_recording:
            self._recorder.stop_session()
        await self._server.stop()

    async def _on_game_connected(self):
        self._connected = True
        logger.info("Game connected")

    async def _on_game_disconnected(self):
        self._connected = False
        logger.info("Game disconnected")

    # ══════════════════════════════════════════════════════════════════════
    # Communication
    # ══════════════════════════════════════════════════════════════════════

    async def subscribe(self, sensors: list[str],
                        config_overrides: Optional[dict] = None) -> dict:
        """Tell Lua which sensors to collect and send."""
        req = SubscribeRequest(
            sensors=sensors,
            config_overrides=config_overrides or {},
        )
        await self._server.send(req.model_dump())
        # Wait briefly for SUBSCRIBE_ACK (best-effort)
        await asyncio.sleep(0.1)
        return {"subscribed": sensors}

    async def send_input(self, *,
                         move: Optional[tuple[int, int]] = None,
                         shoot: Optional[tuple[int, int]] = None,
                         use_item: bool = False,
                         use_bomb: bool = False,
                         use_card: bool = False,
                         use_pill: bool = False,
                         drop: bool = False) -> bool:
        """Send game input commands."""
        cmd: dict[str, Any] = {}
        if move:
            cmd["move"] = {"x": move[0], "y": move[1]}
        if shoot:
            cmd["shoot"] = {"x": shoot[0], "y": shoot[1]}
        if use_item:
            cmd["use_item"] = True
        if use_bomb:
            cmd["use_bomb"] = True
        if use_card:
            cmd["use_card"] = True
        if use_pill:
            cmd["use_pill"] = True
        if drop:
            cmd["drop"] = True
        return await self._server.send(cmd)

    async def send_console(self, command: str) -> bool:
        """Execute a console command in the game."""
        return await self._server.send({
            "command": "EXEC_CONSOLE",
            "params": {"command": command},
        })

    async def reconfigure_sensor(self, sensor: str, config: dict) -> bool:
        """Reconfigure a Lua sensor at runtime."""
        return await self._server.send({
            "command": "CONFIGURE_SENSOR",
            "params": {"sensor": sensor, **config},
        })

    async def request_full_state(self) -> bool:
        return await self._server.send({"command": "GET_FULL_STATE"})

    # ══════════════════════════════════════════════════════════════════════
    # Internal message handling
    # ══════════════════════════════════════════════════════════════════════

    async def _handle_message(self, raw: dict):
        """Process an incoming message from the game."""
        msg_type = raw.get("type", "")

        if msg_type == MessageType.EVENT.value:
            await self._handle_event(raw)
            return

        if msg_type == MessageType.COMMAND.value or msg_type == "CMD":
            result = raw.get("result", raw)
            for cb in self._on_event.get("command_result", []):
                try:
                    r = cb(result)
                    if asyncio.iscoroutine(r): await r
                except Exception as e:
                    logger.error("command_result callback error: %s", e)
            return

        # Data message
        dm = DataMessage.from_dict(raw)
        self._frame = dm.frame
        if dm.room_index != self._room:
            self._prev_room = self._room
            self._room = dm.room_index
            if self._entities:
                self._entities.on_room_change(self._room)

        self._message_count += 1
        self._monitor.record_message(dm.channels)

        # Debug: log every 150th message
        if self._message_count % 150 == 1:
            logger.info("PY RX frame=%d room=%d seq=%d channels=%s",
                        dm.frame, dm.room_index, dm.seq, dm.channels)

        # Parse through sensors
        results = SensorRegistry.process_message(dm.payload, dm.frame)
        self._data.update(results)

        # Debug: log parsed results
        if self._message_count % 150 == 1:
            names = list(results.keys())
            logger.info("PY PARSED: %s", names)

        # Update entity state
        if self._entities:
            self._update_entities(results, dm.frame)

        # Record
        if self._recorder and self._recorder.is_recording:
            raw_msg = RawMessage.from_dict(raw)
            self._recorder.record(raw_msg)

        # Fire frame callbacks
        for cb in self._on_frame:
            try:
                result = cb(self._frame, self._room)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error("Frame callback error: %s", e)

    async def _handle_event(self, raw: dict):
        event_name = raw.get("event", raw.get("event_type", ""))
        event_data = raw.get("data", {})

        # Record
        if self._recorder and self._recorder.is_recording:
            raw_msg = RawMessage.from_dict(raw)
            self._recorder.record(raw_msg)

        # Fire event callbacks
        for cb in self._on_event.get(event_name, []):
            try:
                result = cb(event_data)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error("Event callback error for %s: %s", event_name, e)

    def _update_entities(self, results: dict[str, Any], frame: int):
        """Feed parsed sensor data into entity state managers."""
        # ENEMIES → enemies tracker
        if "ENEMIES" in results:
            self._entities.update_enemies(results["ENEMIES"], frame)

        # PROJECTILES → enemy_projectiles, player_tears, lasers
        if "PROJECTILES" in results:
            proj = results["PROJECTILES"]
            ep = proj.enemy_projectiles if hasattr(proj, "enemy_projectiles") else proj.get("enemy_projectiles", [])
            pt = proj.player_tears if hasattr(proj, "player_tears") else proj.get("player_tears", [])
            ls = proj.lasers if hasattr(proj, "lasers") else proj.get("lasers", [])
            self._entities.update_projectiles(ep, pt, ls, frame)

        # PICKUPS
        if "PICKUPS" in results:
            self._entities.update_pickups(results["PICKUPS"], frame)

        # BOMBS
        if "BOMBS" in results:
            self._entities.update_bombs(results["BOMBS"], frame)

    # ══════════════════════════════════════════════════════════════════════
    # Typed Data Access — Player
    # ══════════════════════════════════════════════════════════════════════

    def get_player(self, idx: int = 1) -> Optional[PlayerPosition]:
        data = self._data.get("PLAYER_POSITION", {})
        return data.get(idx) if isinstance(data, dict) else None

    def get_player_position(self, idx: int = 1) -> Optional[Vector2D]:
        p = self.get_player(idx)
        return p.pos if p else None

    def get_player_stats(self, idx: int = 1) -> Optional[PlayerStats]:
        data = self._data.get("PLAYER_STATS", {})
        return data.get(idx) if isinstance(data, dict) else None

    def get_player_health(self, idx: int = 1) -> Optional[PlayerHealth]:
        data = self._data.get("PLAYER_HEALTH", {})
        return data.get(idx) if isinstance(data, dict) else None

    def get_player_inventory(self, idx: int = 1) -> Optional[PlayerInventory]:
        data = self._data.get("PLAYER_INVENTORY", {})
        return data.get(idx) if isinstance(data, dict) else None

    # ══════════════════════════════════════════════════════════════════════
    # Typed Data Access — Room
    # ══════════════════════════════════════════════════════════════════════

    def get_room(self) -> Optional[RoomInfo]:
        return self._data.get("ROOM_INFO")

    def get_room_layout(self) -> Optional[RoomLayout]:
        return self._data.get("ROOM_LAYOUT")

    def is_room_clear(self) -> bool:
        room = self.get_room()
        return room.is_clear if room else False

    # ══════════════════════════════════════════════════════════════════════
    # Typed Data Access — Entities (with state persistence)
    # ══════════════════════════════════════════════════════════════════════

    def get_enemies(self, max_stale: int = 5) -> list[Enemy]:
        """Get active enemies with state persistence."""
        if self._entities:
            return self._entities.enemies.get_fresh(max_stale)
        return self._data.get("ENEMIES", [])

    def get_enemy_projectiles(self, max_stale: int = 3) -> list[Projectile]:
        if self._entities:
            return self._entities.enemy_projectiles.get_fresh(max_stale)
        proj = self._data.get("PROJECTILES")
        if proj:
            return proj.enemy_projectiles if hasattr(proj, "enemy_projectiles") else []
        return []

    def get_player_tears(self, max_stale: int = 3) -> list[Projectile]:
        if self._entities:
            return self._entities.player_tears.get_fresh(max_stale)
        proj = self._data.get("PROJECTILES")
        if proj:
            return proj.player_tears if hasattr(proj, "player_tears") else []
        return []

    def get_lasers(self, max_stale: int = 3) -> list[Laser]:
        if self._entities:
            return self._entities.lasers.get_fresh(max_stale)
        proj = self._data.get("PROJECTILES")
        if proj:
            return proj.lasers if hasattr(proj, "lasers") else []
        return []

    def get_pickups(self, max_stale: int = 30) -> list[Pickup]:
        if self._entities:
            return self._entities.pickups.get_fresh(max_stale)
        return self._data.get("PICKUPS", [])

    def get_bombs(self, max_stale: int = 30) -> list[Bomb]:
        if self._entities:
            return self._entities.bombs.get_fresh(max_stale)
        return self._data.get("BOMBS", [])

    def get_fire_hazards(self) -> list[FireHazard]:
        return self._data.get("FIRE_HAZARDS", [])

    def get_interactables(self) -> list[Interactable]:
        return self._data.get("INTERACTABLES", [])

    def get_grid_entities(self) -> list[GridEntity]:
        if self._entities:
            return self._entities.grid_entities.get_all()
        layout = self._data.get("ROOM_LAYOUT")
        if layout:
            return list(layout.grid.values()) if hasattr(layout, "grid") else []
        return []

    def get_nearest_enemy(self, pos: Optional[Vector2D] = None) -> Optional[Enemy]:
        enemies = self.get_enemies()
        if not enemies:
            return None
        if pos is None:
            return min(enemies, key=lambda e: e.distance)
        return min(enemies, key=lambda e: e.pos.distance_to(pos) if hasattr(e.pos, "distance_to") else 9999)

    # ══════════════════════════════════════════════════════════════════════
    # Computed Properties
    # ══════════════════════════════════════════════════════════════════════

    def get_threat_count(self) -> int:
        if self._entities:
            return self._entities.get_threat_count()
        return len(self.get_enemies()) + len(self.get_enemy_projectiles())

    def get_raw_data(self, sensor_name: str) -> Optional[Any]:
        """Get raw parsed data for any sensor by name."""
        return self._data.get(sensor_name)

    # ══════════════════════════════════════════════════════════════════════
    # Callback Registration
    # ══════════════════════════════════════════════════════════════════════

    def on_frame(self, callback: Callable[[int, int], Any]):
        """Register a per-frame callback: callback(frame, room_index)."""
        self._on_frame.append(callback)
        return callback

    def on(self, event: str):
        """Decorator: register a callback for a game event.

        Events: ROOM_ENTER, ROOM_CLEAR, PLAYER_DAMAGE, NPC_DEATH,
                PLAYER_DEATH, GAME_START, GAME_END, ITEM_COLLECTED
        """
        def decorator(callback: Callable[[dict], Any]):
            self._on_event.setdefault(event, []).append(callback)
            return callback
        return decorator

    # ══════════════════════════════════════════════════════════════════════
    # Recording
    # ══════════════════════════════════════════════════════════════════════

    def start_recording(self, session_id: Optional[str] = None):
        if not self._recorder:
            self._recorder = SessionRecorder()
        self._recorder.start_session(session_id)

    def stop_recording(self):
        if self._recorder:
            return self._recorder.stop_session()

    # ══════════════════════════════════════════════════════════════════════
    # Quality
    # ══════════════════════════════════════════════════════════════════════

    def get_quality_report(self) -> str:
        return str(self._monitor)

    def get_stats(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "frame": self._frame,
            "room": self._room,
            "message_count": self._message_count,
            "messages_sent": self._server.messages_sent,
            "messages_received": self._server.messages_received,
        }

    # ══════════════════════════════════════════════════════════════════════
    # Properties
    # ══════════════════════════════════════════════════════════════════════

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def frame(self) -> int:
        return self._frame

    @property
    def room(self) -> int:
        return self._room


# ══════════════════════════════════════════════════════════════════════════
# Synchronous wrapper for backward compatibility with old code
# ══════════════════════════════════════════════════════════════════════════

class SocketBridgeSync(SocketBridge):
    """
    Synchronous wrapper for use in non-async code.

    Manages its own event loop in a background thread.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread = None

    def start(self) -> None:
        """Start the bridge (blocking, runs event loop in thread)."""
        import threading
        _parent_start = super().start

        def _run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(_parent_start())
            self._loop.run_forever()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()
        import time
        time.sleep(0.1)

    def stop(self) -> None:
        """Stop the bridge."""
        _parent_stop = super().stop
        if self._loop:
            self._loop.call_soon_threadsafe(
                lambda: asyncio.create_task(_parent_stop())
            )
            self._loop.call_soon_threadsafe(self._loop.stop)

    def _run_async(self, coro):
        """Run a coroutine from sync code."""
        if self._loop and self._loop.is_running():
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            try:
                return future.result(timeout=2.0)
            except concurrent.futures.TimeoutError:
                return None
        return None

    def send_input(self, **kwargs) -> bool:
        result = self._run_async(super().send_input(**kwargs))
        return result is True

    def send_console(self, command: str) -> bool:
        result = self._run_async(super().send_console(command))
        return result is True

    def subscribe(self, sensors: list[str], **kwargs) -> dict:
        result = self._run_async(super().subscribe(sensors, **kwargs))
        return result or {}
