"""
Bridge Hub Daemon

Runs a local process that owns the Lua connection and serves multiple
Python clients through a local JSON-line protocol.

Usage:
    python -m apps.bridge_hub
    python -m apps.bridge_hub --hub-port 9530 --lua-port 9527
"""

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

# Ensure python/ root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from bridge_hub_service import BridgeHubService


async def _run(args):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    service = BridgeHubService(
        lua_host=args.lua_host,
        lua_port=args.lua_port,
        host=args.hub_host,
        port=args.hub_port,
    )

    await service.start()

    print("=" * 60)
    print("BridgeHub 已启动")
    print(f"Lua 桥接监听: {args.lua_host}:{args.lua_port}")
    print(f"本地客户端入口: {args.hub_host}:{args.hub_port}")
    print("按 Ctrl+C 停止")
    print("=" * 60)

    stop_event = asyncio.Event()

    def _stop(*_):
        stop_event.set()

    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, _stop)
        loop.add_signal_handler(signal.SIGTERM, _stop)
    except NotImplementedError:
        # Windows event loop may not support signal handlers in all contexts.
        pass

    try:
        await stop_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        print("\n正在停止 BridgeHub...")
        try:
            await asyncio.wait_for(service.stop(), timeout=5.0)
        except asyncio.TimeoutError:
            print("停止超时，强制退出")
        except Exception as e:
            print(f"停止时出错: {e}")
        print("BridgeHub 已停止")


def main():
    parser = argparse.ArgumentParser(description="Run SocketBridge BridgeHub daemon")
    parser.add_argument("--lua-host", default="127.0.0.1", help="Lua connection host")
    parser.add_argument("--lua-port", type=int, default=9527, help="Lua connection port")
    parser.add_argument("--hub-host", default="127.0.0.1", help="Hub server host")
    parser.add_argument("--hub-port", type=int, default=9530, help="Hub server port")
    args = parser.parse_args()

    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
