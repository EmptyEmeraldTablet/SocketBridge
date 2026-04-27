"""
Bridge Hub Service

A local daemon that owns the single Lua connection and fans out data/events
to multiple Python applications over a local JSON-line TCP protocol.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

from isaac_bridge import IsaacBridge

logger = logging.getLogger(__name__)


@dataclass
class ClientSession:
    client_id: str
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    name: str = "unknown"
    subscriptions: set[str] = field(default_factory=set)


class BridgeHubService:
    """Single-owner bridge daemon for multi-application access."""

    def __init__(
        self,
        lua_host: str = "127.0.0.1",
        lua_port: int = 9527,
        host: str = "127.0.0.1",
        port: int = 9530,
    ):
        self.lua_host = lua_host
        self.lua_port = lua_port
        self.host = host
        self.port = port

        self.bridge = IsaacBridge(host=lua_host, port=lua_port)

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server: Optional[asyncio.AbstractServer] = None
        self._dispatch_task: Optional[asyncio.Task] = None
        self._running = False

        self._clients: dict[str, ClientSession] = {}
        self._bridge_events: asyncio.Queue = asyncio.Queue()
        self._pending_commands: deque[tuple[str, str]] = deque()

        self._game_connected = False
        self._last_frame = 0
        self._last_room = -1
        self._snapshot_payload: dict[str, Any] = {}

        self._setup_bridge_handlers()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._loop = asyncio.get_running_loop()

        self.bridge.start()

        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
        )
        self._dispatch_task = asyncio.create_task(self._dispatch_bridge_events())
        logger.info(
            "BridgeHub started: app-clients on %s:%d, Lua bridge on %s:%d",
            self.host,
            self.port,
            self.lua_host,
            self.lua_port,
        )

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False
        logger.info("BridgeHub stopping...")

        # 1) Cancel event dispatch
        if self._dispatch_task and not self._dispatch_task.done():
            self._dispatch_task.cancel()
            try:
                await asyncio.wait_for(self._dispatch_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            self._dispatch_task = None

        # 2) Close all client connections (abort transports to unblock readline)
        for client_id in list(self._clients.keys()):
            await self._close_client(client_id)

        # 3) Close server (don't wait for handlers — they're already aborted)
        if self._server:
            self._server.close()
            self._server = None

        # 4) Drain event queue briefly
        try:
            while not self._bridge_events.empty():
                self._bridge_events.get_nowait()
        except Exception:
            pass

        # 5) Stop bridge
        try:
            self.bridge.stop()
        except Exception as e:
            logger.warning("Bridge stop failed: %s", e)

        self._loop = None
        logger.info("BridgeHub stopped")

    # ------------------------------------------------------------------
    # Bridge callbacks (thread -> asyncio queue)
    # ------------------------------------------------------------------

    def _setup_bridge_handlers(self) -> None:
        @self.bridge.on("connected")
        def on_connected(data: dict):
            self._enqueue_bridge_event({"kind": "bridge_connected", "data": data})

        @self.bridge.on("disconnected")
        def on_disconnected(data: dict):
            self._enqueue_bridge_event({"kind": "bridge_disconnected", "data": data})

        @self.bridge.on("message")
        def on_message(raw_msg: dict, _processed: dict):
            self._enqueue_bridge_event({"kind": "bridge_data", "msg": raw_msg})

        @self.bridge.on("event")
        def on_event(evt):
            self._enqueue_bridge_event(
                {
                    "kind": "bridge_event",
                    "event": {
                        "type": getattr(evt, "type", ""),
                        "frame": getattr(evt, "frame", self._last_frame),
                        "data": getattr(evt, "data", {}),
                    },
                }
            )

        @self.bridge.on("command_result")
        def on_command_result(result: dict):
            self._enqueue_bridge_event({"kind": "bridge_command_result", "result": result})

    def _enqueue_bridge_event(self, event: dict) -> None:
        if not self._loop:
            return
        try:
            import sys
            kind = event.get("kind", "?")
            if kind == "bridge_data":
                msg = event.get("msg", {})
                print(f"[HUB ENQUEUE] kind={kind} frame={msg.get('frame','?')} ch={msg.get('channels','?')} qsize={self._bridge_events.qsize()}", file=sys.stderr, flush=True)
            self._loop.call_soon_threadsafe(self._bridge_events.put_nowait, event)
        except RuntimeError:
            return

    async def _dispatch_bridge_events(self) -> None:
        while self._running:
            event = await self._bridge_events.get()
            kind = event.get("kind")
            import sys
            print(f"[HUB DISPATCH] kind={kind} qsize={self._bridge_events.qsize()}", file=sys.stderr, flush=True)

            if kind == "bridge_connected":
                self._game_connected = True
                await self._broadcast(
                    {
                        "type": "CONNECTED",
                        "address": event.get("data", {}).get("address", [self.lua_host, self.lua_port]),
                    }
                )
                await self._broadcast_snapshot()

            elif kind == "bridge_disconnected":
                self._game_connected = False
                await self._broadcast({"type": "DISCONNECTED"})

            elif kind == "bridge_data":
                msg = event.get("msg", {})
                self._update_snapshot(msg)
                await self._broadcast_data(msg)

            elif kind == "bridge_event":
                evt = event.get("event", {})
                await self._broadcast(
                    {
                        "type": "EVENT",
                        "event": evt.get("type", ""),
                        "frame": evt.get("frame", self._last_frame),
                        "data": evt.get("data", {}),
                    }
                )

            elif kind == "bridge_command_result":
                result = event.get("result", {})
                if self._pending_commands:
                    client_id, request_id = self._pending_commands.popleft()
                    await self._send_to_client(
                        client_id,
                        {
                            "type": "COMMAND_RESULT",
                            "request_id": request_id,
                            "result": result,
                        },
                    )
                else:
                    await self._broadcast(
                        {
                            "type": "COMMAND_RESULT",
                            "request_id": None,
                            "result": result,
                        }
                    )

    # ------------------------------------------------------------------
    # Snapshot + data fanout
    # ------------------------------------------------------------------

    def _update_snapshot(self, msg: dict) -> None:
        self._last_frame = msg.get("frame", self._last_frame)
        self._last_room = msg.get("room_index", self._last_room)

        payload = msg.get("payload", {})
        if isinstance(payload, dict):
            self._snapshot_payload.update(payload)

    def _filter_payload_for_client(self, session: ClientSession, payload: dict, channels: list[str]) -> tuple[dict, list[str]]:
        if not session.subscriptions:
            return payload, channels

        filtered_channels: list[str] = []
        filtered_payload: dict[str, Any] = {}
        for ch in channels:
            if ch in session.subscriptions and ch in payload:
                filtered_channels.append(ch)
                filtered_payload[ch] = payload[ch]
        return filtered_payload, filtered_channels

    async def _broadcast_data(self, msg: dict) -> None:
        import sys
        payload = msg.get("payload", {})
        channels = msg.get("channels", list(payload.keys()) if isinstance(payload, dict) else [])

        if not isinstance(payload, dict):
            payload = {}
        if not isinstance(channels, list):
            channels = list(payload.keys())

        print(f"[HUB BC DATA] frame={msg.get('frame','?')} ch={channels} clients={len(self._clients)}", file=sys.stderr, flush=True)
        for cid, sess in list(self._clients.items()):
            print(f"[HUB BC DATA]   client={cid} subs={sorted(sess.subscriptions)}", file=sys.stderr, flush=True)

        # Debug: track room layout forwarding
        has_layout = "ROOM_LAYOUT" in channels and "ROOM_LAYOUT" in payload
        has_info = "ROOM_INFO" in channels and "ROOM_INFO" in payload
        if has_layout or has_info:
            logger.warning(
                "HUB DATA frame=%s room=%s channels=%s has_LAYOUT=%s has_INFO=%s clients=%d",
                msg.get("frame"), msg.get("room_index"), channels,
                has_layout, has_info, len(self._clients),
            )

        base = {
            "type": "DATA",
            "version": msg.get("version", "3.0"),
            "frame": msg.get("frame", self._last_frame),
            "room_index": msg.get("room_index", self._last_room),
            "timestamp": msg.get("timestamp", 0),
        }

        for client_id, session in list(self._clients.items()):
            filtered_payload, filtered_channels = self._filter_payload_for_client(session, payload, channels)
            if not filtered_payload:
                logger.debug("HUB skip client %s: no matching channels (subs=%s channels=%s)",
                            client_id, sorted(session.subscriptions), channels)
                continue

            if has_layout or has_info:
                logger.warning("HUB → client %s: layout=%s info=%s",
                              client_id,
                              "ROOM_LAYOUT" in filtered_channels,
                              "ROOM_INFO" in filtered_channels)

            out = dict(base)
            out["payload"] = filtered_payload
            out["channels"] = filtered_channels
            await self._send_to_client(client_id, out)

    async def _broadcast_snapshot(self) -> None:
        if not self._snapshot_payload:
            return

        for client_id, session in list(self._clients.items()):
            filtered_payload, filtered_channels = self._filter_payload_for_client(
                session,
                self._snapshot_payload,
                list(self._snapshot_payload.keys()),
            )
            if not filtered_payload:
                continue

            await self._send_to_client(
                client_id,
                {
                    "type": "SNAPSHOT",
                    "frame": self._last_frame,
                    "room_index": self._last_room,
                    "payload": filtered_payload,
                    "channels": filtered_channels,
                },
            )

    # ------------------------------------------------------------------
    # Client protocol
    # ------------------------------------------------------------------

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        client_id = uuid.uuid4().hex[:10]
        session = ClientSession(client_id=client_id, reader=reader, writer=writer)
        self._clients[client_id] = session

        peer = writer.get_extra_info("peername")
        logger.info("Hub client connected: %s (%s)", client_id, peer)

        await self._send_to_client(
            client_id,
            {
                "type": "WELCOME",
                "client_id": client_id,
                "game_connected": self._game_connected,
            },
        )

        if self._game_connected:
            await self._send_to_client(
                client_id,
                {
                    "type": "CONNECTED",
                    "address": [self.lua_host, self.lua_port],
                },
            )

        try:
            while self._running:
                try:
                    line = await asyncio.wait_for(reader.readline(), timeout=30.0)
                except asyncio.TimeoutError:
                    # Send keepalive ping; close on double timeout
                    ok = await self._send_to_client(client_id, {"type": "PING"})
                    if not ok:
                        break
                    continue

                if not line:
                    break

                raw = line.decode("utf-8").strip()
                if not raw:
                    continue

                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await self._send_to_client(client_id, {"type": "ERROR", "message": "invalid JSON"})
                    continue

                await self._process_client_message(session, msg)
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            await self._close_client(client_id)

    async def _process_client_message(self, session: ClientSession, msg: dict) -> None:
        msg_type = str(msg.get("type", "")).upper()

        if msg_type == "HELLO":
            session.name = str(msg.get("client_name", session.name))
            await self._send_to_client(
                session.client_id,
                {
                    "type": "HELLO_ACK",
                    "client_id": session.client_id,
                    "client_name": session.name,
                },
            )
            return

        if msg_type == "SUBSCRIBE":
            channels = msg.get("channels", [])
            if isinstance(channels, list):
                session.subscriptions.update(str(c) for c in channels)
            await self._send_to_client(
                session.client_id,
                {
                    "type": "SUBSCRIBE_ACK",
                    "channels": sorted(session.subscriptions),
                },
            )
            await self._send_snapshot_to_client(session)
            return

        if msg_type == "UNSUBSCRIBE":
            channels = msg.get("channels", [])
            if isinstance(channels, list):
                for c in channels:
                    session.subscriptions.discard(str(c))
            await self._send_to_client(
                session.client_id,
                {
                    "type": "UNSUBSCRIBE_ACK",
                    "channels": sorted(session.subscriptions),
                },
            )
            return

        if msg_type in ("GET_SNAPSHOT", "REQUEST_FULL_STATE"):
            await self._send_snapshot_to_client(session)
            # Also request Lua to emit a fresh full state in background.
            self.bridge.request_full_state()
            return

        if msg_type == "SEND_CONSOLE":
            command = str(msg.get("command", "")).strip()
            request_id = str(msg.get("request_id") or uuid.uuid4().hex)
            if not command:
                await self._send_to_client(session.client_id, {"type": "ERROR", "message": "empty console command"})
                return

            ok = self.bridge.send_console_command(command)
            if not ok:
                await self._send_to_client(
                    session.client_id,
                    {
                        "type": "COMMAND_RESULT",
                        "request_id": request_id,
                        "result": {"success": False, "error": "failed to send command"},
                    },
                )
                return

            self._pending_commands.append((session.client_id, request_id))
            return

        if msg_type == "SEND_BRIDGE_COMMAND":
            command = str(msg.get("command", "")).strip()
            params = msg.get("params", {})
            request_id = str(msg.get("request_id") or uuid.uuid4().hex)
            if not command:
                await self._send_to_client(session.client_id, {"type": "ERROR", "message": "empty bridge command"})
                return

            ok = self.bridge.send_command(command, params if isinstance(params, dict) else {})
            if not ok:
                await self._send_to_client(
                    session.client_id,
                    {
                        "type": "COMMAND_RESULT",
                        "request_id": request_id,
                        "result": {"success": False, "error": "failed to send command"},
                    },
                )
                return

            self._pending_commands.append((session.client_id, request_id))
            return

        if msg_type == "SEND_INPUT":
            request_id = str(msg.get("request_id") or uuid.uuid4().hex)
            ok = self.bridge.send_input(
                move=msg.get("move"),
                shoot=msg.get("shoot"),
                use_item=bool(msg.get("use_item", False)),
                use_bomb=bool(msg.get("use_bomb", False)),
                use_card=bool(msg.get("use_card", False)),
                use_pill=bool(msg.get("use_pill", False)),
                drop=bool(msg.get("drop", False)),
            )
            await self._send_to_client(
                session.client_id,
                {
                    "type": "COMMAND_RESULT",
                    "request_id": request_id,
                    "result": {"success": bool(ok), "command": "INPUT"},
                },
            )
            return

        if msg_type == "PING":
            await self._send_to_client(session.client_id, {"type": "PONG"})
            return

        await self._send_to_client(session.client_id, {"type": "ERROR", "message": f"unknown type: {msg_type}"})

    async def _send_snapshot_to_client(self, session: ClientSession) -> None:
        filtered_payload, filtered_channels = self._filter_payload_for_client(
            session,
            self._snapshot_payload,
            list(self._snapshot_payload.keys()),
        )
        await self._send_to_client(
            session.client_id,
            {
                "type": "SNAPSHOT",
                "frame": self._last_frame,
                "room_index": self._last_room,
                "payload": filtered_payload,
                "channels": filtered_channels,
            },
        )

    async def _broadcast(self, msg: dict) -> None:
        for client_id in list(self._clients.keys()):
            await self._send_to_client(client_id, msg)

    async def _send_to_client(self, client_id: str, msg: dict) -> bool:
        session = self._clients.get(client_id)
        if not session:
            return False

        try:
            payload = (json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8")
            session.writer.write(payload)
            await asyncio.wait_for(session.writer.drain(), timeout=2.0)
            return True
        except Exception:
            await self._close_client(client_id)
            return False

    async def _close_client(self, client_id: str) -> None:
        session = self._clients.pop(client_id, None)
        if not session:
            return

        try:
            session.writer.close()
            try:
                await asyncio.wait_for(session.writer.wait_closed(), timeout=1.0)
            except (asyncio.TimeoutError, Exception):
                pass
        except Exception:
            pass

        # Also close the underlying transport to unblock readline()
        try:
            transport = session.writer.transport
            if transport:
                transport.abort()
        except Exception:
            pass

        logger.info("Hub client disconnected: %s (%s)", client_id, session.name)
