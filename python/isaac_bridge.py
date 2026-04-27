"""
Backward-compatibility wrapper for SocketBridge v3.0.

This file preserves the old IsaacBridge API surface so existing apps
(console.py, recorder.py, tests/) continue to work during migration.

All actual logic is delegated to the new architecture (facade.py + layers).
"""

from facade import SocketBridgeSync as _SocketBridgeSync
from protocol.schema import MessageType, CollectInterval, Vector2D
import inspect

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

        @self._bridge._server.on_message
        async def _on_raw_message(raw_msg: dict):
            import sys
            ch = raw_msg.get("channels", [])
            print(f"[COMPAT RX] seq={raw_msg.get('seq','?')} frame={raw_msg.get('frame','?')} type={raw_msg.get('type','?')} ch={ch} n_msg_handlers={len(self.handlers.get('message',[]))}", file=sys.stderr, flush=True)
            # Keep legacy raw message stream for adapter-style consumers.
            self._trigger("raw_message", raw_msg)

            msg_type = raw_msg.get("type")
            if msg_type in (MessageType.DATA.value, MessageType.FULL.value):
                self._handle_data_message(raw_msg)
                return

            if msg_type == MessageType.EVENT.value:
                event_name = raw_msg.get("event") or raw_msg.get("event_type") or ""
                event_data = raw_msg.get("data") or raw_msg.get("event_data") or {}
                frame = raw_msg.get("frame", self.state.frame)
                self._emit_game_event(event_name, event_data, frame=frame)
                return

            if msg_type in (MessageType.COMMAND.value, "CMD"):
                result = raw_msg.get("result", raw_msg)
                self._trigger("command_result", result)

        # Per-frame data
        @self._bridge.on_frame
        def _on_frame(frame, room):
            self.state.frame = frame
            self.state.room_index = room

    def _invoke_handler_with_fallback(self, handler, *preferred_args):
        """Call handlers with graceful arity fallback for legacy compatibility."""
        call_variants = [preferred_args]

        # If handler has fewer params, retry with truncated args.
        for i in range(len(preferred_args) - 1, -1, -1):
            call_variants.append(preferred_args[:i])

        # De-duplicate variants while preserving order.
        seen = set()
        unique_variants = []
        for args in call_variants:
            key = len(args)
            if key not in seen:
                seen.add(key)
                unique_variants.append(args)

        for args in unique_variants:
            try:
                handler(*args)
                return
            except TypeError:
                continue
            except Exception:
                return

    def _trigger(self, event_name, *args):
        for handler in self.handlers.get(event_name, []):
            self._invoke_handler_with_fallback(handler, *args)

    def _extract_processed_channels(self, channels: list) -> dict:
        processed = {}
        for name in channels:
            data = self._bridge.get_raw_data(name)
            if data is not None:
                processed[name] = data
        return processed

    def _emit_legacy_message(self, raw_msg: dict, processed: dict):
        import sys
        msg_type = raw_msg.get("type", MessageType.DATA.value)
        payload = raw_msg.get("payload", {})
        channels = raw_msg.get("channels", list(payload.keys()) if isinstance(payload, dict) else [])

        handlers_list = self.handlers.get("message", [])
        print(f"[EMIT LEGACY] frame={raw_msg.get('frame','?')} type={msg_type} ch={channels} n_handlers={len(handlers_list)}", file=sys.stderr, flush=True)

        legacy_msg = DataMessage(
            version=raw_msg.get("version", 2),
            msg_type=msg_type,
            timestamp=raw_msg.get("timestamp", raw_msg.get("game_time", 0)),
            frame=raw_msg.get("frame", self.state.frame),
            room_index=raw_msg.get("room_index", self.state.room_index),
            payload=payload if isinstance(payload, dict) else {},
            channels=channels if isinstance(channels, list) else [],
        )

        for handler in self.handlers.get("message", []):
            # Preferred legacy style: (raw_msg, processed)
            # Single-arg consumers receive DataMessage for typed access.
            try:
                sig = inspect.signature(handler)
                positional = [
                    p for p in sig.parameters.values()
                    if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                ]
                has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in sig.parameters.values())
                arity = len(positional)
            except Exception:
                # Fallback best effort if introspection fails.
                self._invoke_handler_with_fallback(
                    handler,
                    raw_msg,
                    processed,
                    legacy_msg,
                )
                continue

            try:
                if has_varargs or arity >= 3:
                    handler(raw_msg, processed, legacy_msg)
                elif arity == 2:
                    handler(raw_msg, processed)
                elif arity == 1:
                    handler(legacy_msg)
                else:
                    handler()
            except Exception:
                # Keep compatibility behavior: handler exceptions should not break bridge loop.
                continue

        if msg_type == MessageType.FULL.value:
            self._trigger("full_state", legacy_msg)

    def _emit_game_event(self, event_name: str, event_data: dict, frame: int = 0):
        if not event_name:
            return

        data = event_data if isinstance(event_data, dict) else {"value": event_data}
        evt = Event(type=event_name, data=data, frame=frame or self.state.frame)

        self.stats["events_received"] += 1
        try:
            self.event_queue.put_nowait(evt)
        except Exception:
            pass

        self._trigger(f"event:{event_name}", data)

        # Backward-compat alias used by some legacy apps.
        if event_name == "ROOM_ENTER":
            self._trigger("event:ROOM_CHANGED", data)

        # Generic game event channel receives Event object only.
        self._trigger("event", evt)

    def _handle_data_message(self, raw_msg: dict):
        payload = raw_msg.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}

        channels = raw_msg.get("channels", list(payload.keys()))
        if not isinstance(channels, list):
            channels = list(payload.keys())

        frame = raw_msg.get("frame", self.state.frame)
        room_index = raw_msg.get("room_index", self.state.room_index)

        self.state.frame = frame
        self.state.room_index = room_index
        self.stats["messages_received"] += 1

        # Keep legacy state as raw payload (dict/list primitives), not Pydantic models.
        for name in channels:
            if name in payload:
                self.state.data[name] = payload[name]
                self._trigger(f"data:{name}", payload[name])

        self._trigger("data", self.state.data)

        processed = self._extract_processed_channels(channels)
        self._emit_legacy_message(raw_msg, processed)

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

    def _top_level(self):
        return {
            "version": self.version,
            "type": self.msg_type,
            "msg_type": self.msg_type,
            "timestamp": self.timestamp,
            "frame": self.frame,
            "room_index": self.room_index,
            "payload": self.payload,
            "channels": self.channels,
        }

    def __getitem__(self, key):
        top = self._top_level()
        if key in top:
            return top[key]
        if self.payload and key in self.payload:
            return self.payload[key]
        raise KeyError(key)

    def __contains__(self, key):
        return key in self._top_level() or (self.payload is not None and key in self.payload)

    def get(self, key, default=None):
        top = self._top_level()
        if key in top:
            return top[key]
        return self.payload.get(key, default) if self.payload else default

    def keys(self):
        return self._top_level().keys()

    def values(self):
        return self._top_level().values()

    def items(self):
        return self._top_level().items()

    def __len__(self):
        return len(self._top_level())


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
