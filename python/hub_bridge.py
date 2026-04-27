"""
HubBridge - app-side client for BridgeHubService.

Provides a legacy-friendly API surface similar to IsaacBridge so existing apps
can migrate with minimal changes.
"""

from __future__ import annotations

import inspect
import json
import select
import socket
import threading
import time
import uuid
from typing import Optional, Any, Callable

from isaac_bridge import DataMessage, Event


class _State:
    def __init__(self) -> None:
        self.data: dict[str, Any] = {}
        self.frame: int = 0
        self.room_index: int = -1

    def get(self, channel: str, default: Any = None) -> Any:
        return self.data.get(channel, default)


class HubBridge:
    """Bridge client for local Hub daemon."""

    def __init__(self, host: str = "127.0.0.1", port: int = 9530, client_name: str = "app"):
        self.host = host
        self.port = port
        self.client_name = client_name

        self.state = _State()
        self.connected = False  # Game connected status (mirrors IsaacBridge semantics)
        self.hub_connected = False

        self.handlers: dict[str, list[Callable[..., Any]]] = {}
        self._subscriptions: set[str] = set()

        self._sock: Optional[socket.socket] = None
        self._recv_buffer = b""
        self._send_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False

        self.stats: dict[str, int] = {
            "messages_received": 0,
            "events_received": 0,
            "commands_sent": 0,
            "errors": 0,
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._connection_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        self._close_socket()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def __del__(self) -> None:
        try:
            self._close_socket()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # API compatibility
    # ------------------------------------------------------------------

    def on(self, event: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(handler: Callable[..., Any]) -> Callable[..., Any]:
            self.handlers.setdefault(event, []).append(handler)
            return handler
        return decorator

    def off(self, event: str, handler: Optional[Callable[..., Any]] = None) -> None:
        if handler:
            hs = self.handlers.get(event, [])
            if handler in hs:
                hs.remove(handler)
        else:
            self.handlers.pop(event, None)

    def is_connected(self) -> bool:
        return self.connected

    def get_state(self) -> _State:
        return self.state

    def get_channel(self, channel: str) -> Any:
        return self.state.get(channel)

    def get_stats(self) -> dict[str, Any]:
        return {
            **self.stats,
            "hub_connected": self.hub_connected,
            "game_connected": self.connected,
        }

    def request_full_state(self) -> bool:
        return self._send({"type": "REQUEST_FULL_STATE"})

    def subscribe(self, channels: list[str]) -> bool:
        self._subscriptions.update(channels)
        return self._send({"type": "SUBSCRIBE", "channels": channels})

    def unsubscribe(self, channels: list[str]) -> bool:
        for ch in channels:
            self._subscriptions.discard(ch)
        return self._send({"type": "UNSUBSCRIBE", "channels": channels})

    def send_console_command(self, command: str) -> bool:
        self.stats["commands_sent"] += 1
        return self._send(
            {
                "type": "SEND_CONSOLE",
                "command": command,
                "request_id": uuid.uuid4().hex,
            }
        )

    def send_command(self, command: str, params: dict[str, Any] | None = None) -> bool:
        self.stats["commands_sent"] += 1
        return self._send(
            {
                "type": "SEND_BRIDGE_COMMAND",
                "command": command,
                "params": params or {},
                "request_id": uuid.uuid4().hex,
            }
        )

    def send_input(self, move: Any = None, shoot: Any = None, **kwargs: Any) -> bool:
        self.stats["commands_sent"] += 1
        msg: dict[str, Any] = {
            "type": "SEND_INPUT",
            "request_id": uuid.uuid4().hex,
            "move": move,
            "shoot": shoot,
        }
        msg.update(kwargs)
        return self._send(msg)

    def set_channel(self, channel: str, enabled: bool) -> bool:
        return self.send_command("SET_CHANNEL", {"channel": channel, "enabled": enabled})

    def set_interval(self, channel: str, interval: Any) -> bool:
        if hasattr(interval, "value"):
            interval = interval.value
        return self.send_command("SET_INTERVAL", {"channel": channel, "interval": interval})

    def set_manual_mode(self, enabled: bool) -> bool:
        return self.send_command("SET_MANUAL", {"enabled": enabled})

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _invoke_handler_with_fallback(self, handler: Callable[..., Any], *preferred_args: Any) -> None:
        call_variants = [preferred_args]
        for i in range(len(preferred_args) - 1, -1, -1):
            call_variants.append(preferred_args[:i])

        seen: set[int] = set()
        unique: list[tuple[Any, ...]] = []
        for args in call_variants:
            k = len(args)
            if k not in seen:
                seen.add(k)
                unique.append(args)

        for args in unique:
            try:
                handler(*args)
                return
            except TypeError:
                continue
            except Exception:
                return

    def _trigger(self, event_name: str, *args: Any) -> None:
        for handler in self.handlers.get(event_name, []):
            self._invoke_handler_with_fallback(handler, *args)

    def _trigger_message_handlers(self, raw_msg: dict[str, Any]) -> None:
        msg_type = raw_msg.get("type", "DATA")
        payload = raw_msg.get("payload", {})
        payload_dict: dict[str, Any] = payload if isinstance(payload, dict) else {}
        channels_raw = raw_msg.get("channels", list(payload_dict.keys()))
        channels: list[str] = channels_raw if isinstance(channels_raw, list) else list(payload_dict.keys())

        legacy_msg = DataMessage(
            version=raw_msg.get("version", 3),
            msg_type=msg_type,
            timestamp=raw_msg.get("timestamp", 0),
            frame=raw_msg.get("frame", self.state.frame),
            room_index=raw_msg.get("room_index", self.state.room_index),
            payload=payload_dict,
            channels=channels,
        )

        for handler in self.handlers.get("message", []):
            try:
                sig = inspect.signature(handler)
                positional = [
                    p for p in sig.parameters.values()
                    if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                ]
                has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in sig.parameters.values())
                arity = len(positional)
            except Exception:
                self._invoke_handler_with_fallback(handler, raw_msg, {}, legacy_msg)
                continue

            try:
                if has_varargs or arity >= 3:
                    handler(raw_msg, {}, legacy_msg)
                elif arity == 2:
                    handler(raw_msg, {})
                elif arity == 1:
                    handler(legacy_msg)
                else:
                    handler()
            except Exception:
                continue

    def _connection_loop(self) -> None:
        while self._running:
            if not self.hub_connected:
                if not self._connect_once():
                    time.sleep(1.0)
                    continue

            try:
                if self._sock is None:
                    raise ConnectionError("hub socket missing")

                ready, _, _ = select.select([self._sock], [], [], 1.0)
                if not ready:
                    continue

                chunk = self._sock.recv(4096)
                if not chunk:
                    raise ConnectionError("hub closed")

                self._recv_buffer += chunk
                while b"\n" in self._recv_buffer:
                    line, self._recv_buffer = self._recv_buffer.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                    except json.JSONDecodeError:
                        self.stats["errors"] += 1
                        continue
                    self._handle_hub_message(msg)
            except (ConnectionError, OSError):
                self._mark_disconnected()
                time.sleep(0.5)
            except Exception:
                self.stats["errors"] += 1
                self._mark_disconnected()
                time.sleep(0.5)

    def _connect_once(self) -> bool:
        try:
            sock = socket.create_connection((self.host, self.port), timeout=2.0)
            sock.settimeout(None)
            self._sock = sock
            self._recv_buffer = b""
            self.hub_connected = True

            self._send({"type": "HELLO", "client_name": self.client_name})
            if self._subscriptions:
                self._send({"type": "SUBSCRIBE", "channels": sorted(self._subscriptions)})
            self._send({"type": "REQUEST_FULL_STATE"})
            return True
        except Exception:
            self.stats["errors"] += 1
            self._close_socket()
            return False

    def _close_socket(self) -> None:
        try:
            if self._sock:
                try:
                    self._sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self._sock.close()
        except Exception:
            pass
        self._sock = None
        self._recv_buffer = b""

    def _mark_disconnected(self) -> None:
        was_game_connected = self.connected
        self.hub_connected = False
        self.connected = False
        self._close_socket()
        if was_game_connected:
            self._trigger("disconnected", {})

    def _send(self, msg: dict[str, Any]) -> bool:
        if not self.hub_connected or not self._sock:
            return False

        payload = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
        try:
            with self._send_lock:
                self._sock.sendall(payload)
            return True
        except Exception:
            self.stats["errors"] += 1
            self._mark_disconnected()
            return False

    def _handle_hub_message(self, msg: dict[str, Any]) -> None:
        msg_type = str(msg.get("type", "")).upper()

        if msg_type in ("WELCOME", "HELLO_ACK", "SUBSCRIBE_ACK", "UNSUBSCRIBE_ACK", "PONG"):
            return

        if msg_type == "CONNECTED":
            self.connected = True
            self._trigger("connected", {"address": msg.get("address", ["unknown", 0])})
            return

        if msg_type == "DISCONNECTED":
            self.connected = False
            self._trigger("disconnected", {})
            return

        if msg_type in ("DATA", "SNAPSHOT"):
            payload = msg.get("payload", {})
            payload_dict: dict[str, Any] = payload if isinstance(payload, dict) else {}
            channels_raw = msg.get("channels", list(payload_dict.keys()))
            channels: list[str] = channels_raw if isinstance(channels_raw, list) else list(payload_dict.keys())

            if payload_dict:
                self.state.data.update(payload_dict)
            self.state.frame = msg.get("frame", self.state.frame)
            self.state.room_index = msg.get("room_index", self.state.room_index)
            self.stats["messages_received"] += 1

            # Keep message schema consistent with IsaacBridge raw data callbacks.
            raw_msg: dict[str, Any] = {
                "type": "DATA",
                "version": msg.get("version", "3.0"),
                "timestamp": msg.get("timestamp", 0),
                "frame": self.state.frame,
                "room_index": self.state.room_index,
                "payload": payload_dict,
                "channels": channels,
            }
            self._trigger_message_handlers(raw_msg)
            return

        if msg_type == "EVENT":
            evt_name = msg.get("event", "")
            evt_data = msg.get("data", {})
            evt_frame = msg.get("frame", self.state.frame)

            self.stats["events_received"] += 1
            self._trigger(f"event:{evt_name}", evt_data)
            evt = Event(type=evt_name, data=evt_data, frame=evt_frame)
            self._trigger("event", evt)
            return

        if msg_type == "COMMAND_RESULT":
            result = msg.get("result", {})
            self._trigger("command_result", result)
            return

        if msg_type == "ERROR":
            self.stats["errors"] += 1
            self._trigger("error", msg.get("message", "unknown error"))
