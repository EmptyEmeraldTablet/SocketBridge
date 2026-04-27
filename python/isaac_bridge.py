"""
Backward-compatibility wrapper for SocketBridge v3.0.

This file preserves the old IsaacBridge API surface so existing apps
(console.py, recorder.py, tests/) continue to work during migration.

All actual logic is delegated to the new architecture (facade.py + layers).
"""

from facade import SocketBridgeSync as _SocketBridgeSync
from protocol.schema import MessageType, CollectInterval, Vector2D
from sensors.base import SensorRegistry

# ══════════════════════════════════════════════════════════════════════════
# Backward-compat type aliases
# ══════════════════════════════════════════════════════════════════════════

__all__ = [
    "IsaacBridge",
    "GameDataAccessor",
    "DataMessage",
    "Event",
    "MessageType",
    "CollectInterval",
    "Vector2D",
]

# ══════════════════════════════════════════════════════════════════════════
# IsaacBridge — Compat wrapper
# ══════════════════════════════════════════════════════════════════════════

class IsaacBridge:
    """DEPRECATED: Use SocketBridge (facade.py) for new code.

    This wrapper delegates to the new architecture and provides
    the old event/callback API for backward compatibility.
    """

    def __init__(self, host="127.0.0.1", port=9527):
        self._bridge = _SocketBridgeSync(host=host, port=port)
        self.host = host
        self.port = port

        # Emulate old state object
        class _LegacyState:
            data: dict = {}
            frame: int = 0
            room_index: int = -1

            def get(self, channel, default=None):
                return self.data.get(channel, default)

            def update(self, channel, payload, frame):
                self.data[channel] = payload
                self.frame = frame

            def update_batch(self, payload, frame, room_index=None):
                self.data.update(payload)
                self.frame = max(self.frame, frame)
                if room_index is not None:
                    self.room_index = room_index

            def get_full_state(self):
                return {"frame": self.frame, "room_index": self.room_index, "data": dict(self.data)}

            def clear(self):
                self.data.clear()
                self.frame = 0
                self.room_index = -1

        self.state = _LegacyState()
        self.connected = False
        self.handlers: dict = {}

        # Stats
        self.stats = {"messages_received": 0, "events_received": 0, "commands_sent": 0, "errors": 0}

        # Event queue (for poll-based consumers)
        from queue import Queue
        self.event_queue = Queue()

        # Wire up internal handlers
        self._setup_handlers()

    def _setup_handlers(self):
        # TCP connection events (routed through BridgeServer)
        @self._bridge._server.on_connected
        async def _on_connected():
            self.connected = True
            self._trigger("connected", {"address": (self.host, self.port)})

        @self._bridge._server.on_disconnected
        async def _on_disconnected():
            self.connected = False
            self._trigger("disconnected", {})

        # Per-frame data
        @self._bridge.on_frame
        def _on_frame(frame, room):
            self.state.frame = frame
            self.state.room_index = room
            self.stats["messages_received"] += 1

            # Sync sensor data into legacy state dict
            for name in SensorRegistry.all_names():
                data = self._bridge.get_raw_data(name)
                if data is not None:
                    self.state.data[name] = data
                    # Propagate per-channel handlers: "data:PLAYER_POSITION", etc.
                    self._trigger(f"data:{name}", data)

            # Propagate to legacy "data" handlers
            for h in self.handlers.get("data", []):
                try:
                    h(self.state.data)
                except Exception:
                    pass

        @self._bridge.on("ROOM_ENTER")
        def _on_room_enter(data):
            self._trigger("event:ROOM_ENTER", data)

        @self._bridge.on("ROOM_CLEAR")
        def _on_room_clear(data):
            self._trigger("event:ROOM_CLEAR", data)

        @self._bridge.on("PLAYER_DAMAGE")
        def _on_damage(data):
            self._trigger("event:PLAYER_DAMAGE", data)

        @self._bridge.on("GAME_START")
        def _on_game_start(data):
            self._trigger("event:GAME_START", data)

        @self._bridge.on("GAME_END")
        def _on_game_end(data):
            self._trigger("event:GAME_END", data)

        @self._bridge.on("NPC_DEATH")
        def _on_npc_death(data):
            self._trigger("event:NPC_DEATH", data)

        @self._bridge.on("PLAYER_DEATH")
        def _on_player_death(data):
            self._trigger("event:PLAYER_DEATH", data)

        @self._bridge.on("ITEM_COLLECTED")
        def _on_item(data):
            self._trigger("event:ITEM_COLLECTED", data)

        @self._bridge.on("command_result")
        def _on_cmd_result(data):
            self._trigger("command_result", data)

    def _trigger(self, event_name, data):
        for h in self.handlers.get(event_name, []):
            try:
                h(data)
            except Exception:
                pass
        for h in self.handlers.get("event", []):
            try:
                h(data)
            except Exception:
                pass

    # ── Old API ──────────────────────────────────────────────────────

    def start(self):
        self._bridge.start()

    def stop(self):
        self._bridge.stop()

    def on(self, event: str):
        """Decorator: register handler for event.

        Events: "connected", "disconnected", "data", "data:CHANNEL",
                "event", "event:TYPE", "full_state", "command_result",
                "message", "raw_message"
        """
        def decorator(handler):
            self.handlers.setdefault(event, []).append(handler)
            return handler
        return decorator

    def off(self, event, handler=None):
        if handler:
            self.handlers.get(event, []).remove(handler)
        else:
            self.handlers.pop(event, None)

    def send_input(self, move=None, shoot=None, **kwargs):
        return self._bridge.send_input(move=move, shoot=shoot, **kwargs)

    def send_command(self, command: str, params: dict = None):
        self.stats["commands_sent"] += 1
        return self._bridge._run_async(
            self._bridge._server.send({
                "command": command,
                "params": params or {},
            })
        )

    def send_console_command(self, command: str):
        self.stats["commands_sent"] += 1
        return self._bridge.send_console(command)

    def set_channel(self, channel, enabled):
        return self.send_command("SET_CHANNEL", {"channel": channel, "enabled": enabled})

    def set_interval(self, channel, interval):
        if hasattr(interval, "value"):
            interval = interval.value
        return self.send_command("SET_INTERVAL", {"channel": channel, "interval": interval})

    def request_full_state(self):
        return self.send_command("GET_FULL_STATE")

    def set_manual_mode(self, enabled):
        return self.send_command("SET_MANUAL", {"enabled": enabled})

    def get_event(self, timeout=None):
        from queue import Empty
        try:
            return self.event_queue.get(timeout=timeout)
        except Empty:
            return None

    def get_state(self):
        return self.state

    def get_channel(self, channel):
        return self.state.get(channel)

    def get_stats(self):
        return dict(self.stats)

    def is_connected(self):
        return self.connected

    def _send(self, data):
        return self._bridge._run_async(self._bridge._server.send(data))


# ══════════════════════════════════════════════════════════════════════════
# Legacy types for backward compat
# ══════════════════════════════════════════════════════════════════════════

from dataclasses import dataclass, field
import time as _time
from typing import Any, Optional, List

@dataclass
class DataMessage:
    """Legacy DataMessage — wraps new DataMessage for backward compat."""
    version: int = 2
    msg_type: str = "DATA"
    timestamp: int = 0
    frame: int = 0
    room_index: int = -1
    payload: Optional[dict] = None
    channels: Optional[list] = None

    @property
    def is_data(self):
        return self.msg_type in ("DATA", "FULL")

    @property
    def is_event(self):
        return self.msg_type == "EVENT"

    @property
    def is_full_state(self):
        return self.msg_type == "FULL"

    def to_dict(self):
        return {
            "version": self.version, "type": self.msg_type,
            "timestamp": self.timestamp, "frame": self.frame,
            "room_index": self.room_index, "payload": self.payload,
            "channels": self.channels,
        }

    def __getitem__(self, key):
        return self.payload[key] if self.payload else None

    def __contains__(self, key):
        return self.payload is not None and key in self.payload

    def get(self, key, default=None):
        return self.payload.get(key, default) if self.payload else default

    def keys(self):
        return self.payload.keys() if self.payload else []

    def values(self):
        return self.payload.values() if self.payload else []

    def items(self):
        return self.payload.items() if self.payload else []

    def __len__(self):
        return len(self.payload) if self.payload else 0


@dataclass
class Event:
    """Legacy Event type."""
    type: str = ""
    data: dict = field(default_factory=dict)
    frame: int = 0
    timestamp: float = field(default_factory=_time.time)


class GameDataAccessor:
    """Legacy data accessor — delegates to bridge state."""

    def __init__(self, bridge: IsaacBridge):
        self.bridge = bridge

    @property
    def state(self):
        return self.bridge.state

    @property
    def frame(self):
        return self.state.frame

    @property
    def room_index(self):
        return self.state.room_index

    def _get_player_data(self, channel, player_idx=1):
        data = self.state.get(channel)
        if not data:
            return None
        if isinstance(data, list):
            idx = player_idx - 1
            return data[idx] if 0 <= idx < len(data) else None
        if isinstance(data, dict):
            return data.get(str(player_idx)) or data.get(player_idx)
        return None

    def get_player_position(self, player_idx=1):
        return self._get_player_data("PLAYER_POSITION", player_idx)

    def get_player_stats(self, player_idx=1):
        return self._get_player_data("PLAYER_STATS", player_idx)

    def get_player_health(self, player_idx=1):
        return self._get_player_data("PLAYER_HEALTH", player_idx)

    def get_player_inventory(self, player_idx=1):
        return self._get_player_data("PLAYER_INVENTORY", player_idx)

    def get_room_info(self):
        return self.state.get("ROOM_INFO")

    def get_room_layout(self):
        return self.state.get("ROOM_LAYOUT")

    def is_room_clear(self):
        info = self.get_room_info()
        return info.get("is_clear", False) if info else False

    def get_enemies(self):
        return self.state.get("ENEMIES") or []

    def get_projectiles(self):
        return self.state.get("PROJECTILES") or {"enemy_projectiles": [], "player_tears": [], "lasers": []}

    def get_enemy_projectiles(self):
        return self.get_projectiles().get("enemy_projectiles", [])

    def get_pickups(self):
        return self.state.get("PICKUPS") or []

    def get_fire_hazards(self):
        return self.state.get("FIRE_HAZARDS") or []

    def get_bombs(self):
        return self.state.get("BOMBS") or []

    def get_interactables(self):
        return self.state.get("INTERACTABLES") or []


# ══════════════════════════════════════════════════════════════════════════
# Fallback standalone usage (keeps the old main() working)
# ══════════════════════════════════════════════════════════════════════════

def main():
    """Legacy standalone entry point."""
    import logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    logger = logging.getLogger("IsaacBridge")

    bridge = IsaacBridge()
    data = GameDataAccessor(bridge)

    @bridge.on("connected")
    def on_connected(info):
        logger.info("Game connected from %s", info.get("address") if isinstance(info, dict) else info)
        bridge.request_full_state()

    @bridge.on("disconnected")
    def on_disconnected(_):
        logger.info("Game disconnected")

    @bridge.on("event:PLAYER_DAMAGE")
    def on_damage(event_data):
        amt = event_data.get("amount", 0) if isinstance(event_data, dict) else 0
        logger.warning("Player took %d damage!", amt)

    bridge.start()

    try:
        import time
        logger.info("Waiting for game connection... (Ctrl+C to stop)")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        bridge.stop()


if __name__ == "__main__":
    main()
