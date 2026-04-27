"""
BridgeServer — asyncio-based TCP server with JSON-line protocol.

Replaces the blocking socket + threading approach in isaac_bridge.py.
Provides clean async message stream with automatic reconnect support.
"""

import asyncio
import json
import logging
import time
from typing import Optional, Callable, Awaitable, Any

logger = logging.getLogger(__name__)


class BridgeServer:
    """
    asyncio TCP server for SocketBridge communication.

    Protocol: JSON-line (each message is a JSON object followed by \n)

    Usage:
        server = BridgeServer()
        server.on_message(lambda msg: print(msg))
        await server.start()
        await server.send({"command": "SUBSCRIBE", "sensors": ["ENEMIES"]})
        ...
        await server.stop()
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9527):
        self.host = host
        self.port = port
        self._server: Optional[asyncio.AbstractServer] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._running = False
        self._connected = False
        self._send_lock = asyncio.Lock()

        # Callbacks
        self._on_connected: list[Callable[[], Awaitable[None]]] = []
        self._on_disconnected: list[Callable[[], Awaitable[None]]] = []
        self._on_message: list[Callable[[dict], Awaitable[None]]] = []

        # Stats
        self.messages_received: int = 0
        self.messages_sent: int = 0
        self.errors: int = 0

    # ── lifecycle ───────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start listening for game connections."""
        self._running = True
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port,
        )
        logger.info("Server listening on %s:%d", self.host, self.port)
        asyncio.create_task(self._accept_loop())

    async def stop(self) -> None:
        """Stop the server."""
        self._running = False
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._connected = False
        logger.info("Server stopped")

    async def _accept_loop(self) -> None:
        """Accept connections (runs as background task)."""
        try:
            async with self._server:
                await self._server.serve_forever()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Server accept error: %s", e)
            self.errors += 1

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        """Handle a new game connection."""
        addr = writer.get_extra_info("peername")

        # Close previous connection if any
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass

        self._reader = reader
        self._writer = writer
        self._connected = True
        logger.info("Game connected from %s", addr)

        # Fire connected callbacks
        for cb in self._on_connected:
            try:
                await cb()
            except Exception as e:
                logger.error("Connected callback error: %s", e)

        # Read loop
        try:
            while self._running and self._connected:
                try:
                    line = await asyncio.wait_for(reader.readline(), timeout=5.0)
                except asyncio.TimeoutError:
                    continue  # heartbeat timeout — normal

                if not line:
                    logger.info("Game disconnected (EOF)")
                    break

                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue

                try:
                    msg = json.loads(line_str)
                    self.messages_received += 1

                    for cb in self._on_message:
                        try:
                            await cb(msg)
                        except Exception as e:
                            logger.error("Message callback error: %s", e)
                            self.errors += 1

                except json.JSONDecodeError as e:
                    logger.warning("JSON decode error: %s", e)
                    self.errors += 1

        except (ConnectionResetError, BrokenPipeError):
            logger.info("Connection reset by game")
        except Exception as e:
            logger.error("Read loop error: %s", e)
            self.errors += 1
        finally:
            self._connected = False
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

            for cb in self._on_disconnected:
                try:
                    await cb()
                except Exception as e:
                    logger.error("Disconnected callback error: %s", e)

    # ── send ────────────────────────────────────────────────────────────

    async def send(self, data: dict) -> bool:
        """Send a JSON message to the game."""
        if not self._connected or not self._writer:
            return False

        async with self._send_lock:
            try:
                payload = json.dumps(data, ensure_ascii=False) + "\n"
                self._writer.write(payload.encode("utf-8"))
                await self._writer.drain()
                self.messages_sent += 1
                return True
            except Exception as e:
                logger.error("Send error: %s", e)
                self.errors += 1
                return False

    # ── callbacks ───────────────────────────────────────────────────────

    def on_connected(self, cb: Callable[[], Awaitable[None]]):
        self._on_connected.append(cb)

    def on_disconnected(self, cb: Callable[[], Awaitable[None]]):
        self._on_disconnected.append(cb)

    def on_message(self, cb: Callable[[dict], Awaitable[None]]):
        self._on_message.append(cb)

    # ── properties ──────────────────────────────────────────────────────

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def running(self) -> bool:
        return self._running
