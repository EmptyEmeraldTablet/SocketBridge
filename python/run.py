#!/usr/bin/env python3
"""
SocketBridge AI Combat System - Launcher

Usage:
    python run.py                    # Interactive mode
    python run.py --basic            # Basic bridge only
    python run.py --ai               # AI mode
    python run.py --test             # Run tests only
    python run.py --status           # Check system status
    python run.py --help             # Show this help

Requirements:
    - The Binding of Isaac: Repentance
    - SocketBridge mod enabled in game
"""

import sys
import os
import argparse
import time
import threading
from pathlib import Path

# Add python directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_banner():
    """Print system banner"""
    print(f"""
{BOLD}╔════════════════════════════════════════════════════════════╗
║     SocketBridge AI Combat System v2.0                      ║
║     The Binding of Isaac: Repentance                        ║
╚════════════════════════════════════════════════════════════╝{RESET}
    """)


def print_section(title):
    """Print section header"""
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BOLD}{title}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")


def print_status(label, value, status="OK"):
    """Print status line"""
    if status == "OK":
        icon = f"{GREEN}✓{RESET}"
    elif status == "WARN":
        icon = f"{YELLOW}⚠{RESET}"
    else:
        icon = f"{RED}✗{RESET}"
    print(f"  {icon} {label:<30} {value}")


def check_environment():
    """Check if environment is ready"""
    print_section("Environment Check")

    checks = []

    # Check Python version
    py_version = sys.version.split()[0]
    if tuple(map(int, py_version.split(".")[:2])) >= (3, 8):
        print_status("Python Version", py_version, "OK")
        checks.append(True)
    else:
        print_status("Python Version", py_version, "FAIL")
        checks.append(False)

    # Check required modules
    modules = [
        ("isaac_bridge", "Core Bridge"),
        ("models", "Data Models"),
        ("data_processor", "Data Processor"),
        ("environment", "Environment"),
        ("basic_controllers", "Basic Controllers"),
        ("threat_analysis", "Threat Analysis"),
        ("pathfinding", "Pathfinding"),
        ("state_machine", "State Machine"),
        ("strategy_system", "Strategy System"),
        ("behavior_tree", "Behavior Tree"),
        ("orchestrator", "Combat Orchestrator"),
        ("orchestrator_enhanced", "Enhanced Orchestrator"),
        ("smart_aiming", "Smart Aiming"),
        ("adaptive_system", "Adaptive System"),
    ]

    for module_name, description in modules:
        try:
            __import__(module_name)
            print_status(f"{description} ({module_name})", "Loaded", "OK")
            checks.append(True)
        except ImportError as e:
            print_status(f"{description} ({module_name})", str(e), "FAIL")
            checks.append(False)

    return all(checks)


def run_tests():
    """Run test suite"""
    print_section("Running Tests")

    print("Running integration tests...\n")

    try:
        import subprocess

        result = subprocess.run(
            [sys.executable, "test_integration.py"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"{RED}Integration tests failed!{RESET}")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"{RED}Failed to run tests: {e}{RESET}")
        return False

    return True


def run_compatibility_tests():
    """Run Windows compatibility tests"""
    print_section("Running Compatibility Tests")

    try:
        import subprocess

        result = subprocess.run(
            [sys.executable, "test_windows_compatibility.py"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"{YELLOW}Some compatibility tests failed{RESET}")
            return False
    except Exception as e:
        print(f"{YELLOW}Could not run compatibility tests: {e}{RESET}")
        return False

    return True


def start_basic_mode():
    """Start basic bridge mode"""
    print_section("Starting Basic Bridge")

    try:
        from isaac_bridge import IsaacBridge

        bridge = IsaacBridge(host="127.0.0.1", port=9527)

        @bridge.on("connected")
        def on_connected(info):
            print(f"\n{GREEN}Game connected!{RESET}")
            print(f"  Address: {info['address']}")

        @bridge.on("disconnected")
        def on_disconnected():
            print(f"\n{YELLOW}Game disconnected{RESET}")

        @bridge.on("data:PLAYER_POSITION")
        def on_position(pos):
            if pos and isinstance(pos, list) and len(pos) > 0:
                p = pos[0]
                x = p.get("pos", {}).get("x", 0)
                y = p.get("pos", {}).get("y", 0)
                print(f"\rPlayer: ({x:.0f}, {y:.0f})", end="", flush=True)

        print("Starting bridge server...")
        print(f"  Host: 127.0.0.1")
        print(f"  Port: 9527")
        print(f"\n{YELLOW}Waiting for game connection... (Ctrl+C to stop){RESET}\n")

        bridge.start()

        if not bridge.running:
            print(f"{RED}Server failed to start{RESET}")
            return False

        while bridge.running and not bridge.connected:
            time.sleep(0.1)
            if not bridge.running:
                print(f"\n{RED}Server stopped unexpectedly{RESET}")
                return False

        while bridge.running and bridge.connected:
            time.sleep(0.1)

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Stopping bridge...{RESET}")
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
        return False

    return True


def start_ai_mode():
    """Start AI mode"""
    print_section("Starting AI Combat System")

    orchestrator = None  # Initialize to avoid unbound variable warnings
    bridge = None

    try:
        # Import directly from modules
        from isaac_bridge import IsaacBridge
        from orchestrator import SimpleAI
        from orchestrator_enhanced import EnhancedCombatOrchestrator, AIConfig

        # Create configuration
        config = AIConfig(
            enable_behavior_tree=True,
            enable_advanced_control=True,
            enable_adaptive_behavior=True,
            attack_aggression=0.7,
            movement_style="kiting",
        )

        # Create AI
        orchestrator = EnhancedCombatOrchestrator(config)
        orchestrator.initialize()

        # Create bridge
        bridge = IsaacBridge(host="127.0.0.1", port=9527)

        # Statistics
        frame_count = [0]
        last_report = [time.time()]

        @bridge.on("connected")
        def on_connected(info):
            print(f"\n{GREEN}Game connected!{RESET}")
            print(f"  Address: {info['address']}")
            orchestrator.enable()
            print(f"\n{YELLOW}AI enabled - Fighting!{RESET}\n")

        @bridge.on("disconnected")
        def on_disconnected():
            print(f"\n{YELLOW}Game disconnected{RESET}")
            if orchestrator is not None:
                orchestrator.disable()

        @bridge.on("data")
        def on_game_data(data):
            # [DEBUG] 追踪数据流
            import logging
            import json

            logger = logging.getLogger("RunAI")

            # 基本信息
            logger.debug(f"[RunAI] on_game_data received: type={type(data).__name__}")

            if isinstance(data, dict):
                logger.debug(f"[RunAI]   keys={list(data.keys())}")

                # [DEBUG] 详细显示各通道数据
                for channel, value in data.items():
                    if isinstance(value, list):
                        logger.debug(f"[RunAI]   {channel}: list length={len(value)}")
                        if len(value) > 0:
                            # 显示第一条数据的摘要
                            first_item = value[0]
                            if isinstance(first_item, dict):
                                item_keys = list(first_item.keys())[:5]  # 只显示前5个键
                                logger.debug(
                                    f"[RunAI]     {channel}[0] keys: {item_keys}..."
                                )
                    elif isinstance(value, dict):
                        logger.debug(
                            f"[RunAI]   {channel}: dict keys={list(value.keys())}"
                        )
                    else:
                        logger.debug(f"[RunAI]   {channel}: {type(value).__name__}")

                # [DEBUG] 特别检查 PLAYER_POSITION
                if "PLAYER_POSITION" in data:
                    player_data = data["PLAYER_POSITION"]
                    logger.debug(f"[RunAI]   PLAYER_POSITION detail: {player_data}")

                    # [CONSOLE WARNING] 如果数据格式有问题，在控制台显示警告
                    print(f"\n{YELLOW}[DATA FORMAT ISSUE DETECTED]{RESET}")
                    print(
                        f"  Received: payload-only message (missing type/frame/payload wrapper)"
                    )
                    print(f"  Channels: {list(data.keys())}")
                    print(f"  This causes 'No player found' error in orchestrator!")
                    print(f"  See debug logs for details.\n")

            control = orchestrator.update(data)

            move = (int(control.move_x), int(control.move_y))
            shoot = (
                (int(control.shoot_x), int(control.shoot_y))
                if control.shoot
                else (0, 0)
            )
            bridge.send_input(move=move, shoot=shoot)

            frame_count[0] += 1

            now = time.time()
            if now - last_report[0] >= 5.0:
                last_report[0] = now
                stats = orchestrator.get_performance_stats()
                state_val = (
                    orchestrator.current_state.value
                    if hasattr(orchestrator.current_state, "value")
                    else "N/A"
                )
                print(
                    f"\n  Frames: {stats['decisions']} | DPS: {stats['enemies_killed']} | HP: {state_val}"
                )

        print("Starting AI combat system...")
        print(f"  Mode: Enhanced Combat")
        print(f"  Aggression: {config.attack_aggression:.0%}")
        print(f"  Movement: {config.movement_style}")
        print(f"\n{YELLOW}Waiting for game connection... (Ctrl+C to stop){RESET}\n")

        bridge.start()

        if not bridge.running:
            print(f"{RED}Server failed to start{RESET}")
            return False

        while bridge.running and not bridge.connected:
            time.sleep(0.1)
            if not bridge.running:
                print(f"\n{RED}Server stopped unexpectedly{RESET}")
                return False

        while bridge.running and bridge.connected:
            time.sleep(0.1)

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Stopping AI...{RESET}")
        if orchestrator is not None:
            orchestrator.disable()
        if bridge is not None:
            try:
                bridge.stop()
            except Exception:
                pass
    except Exception as e:
        import traceback

        print(f"{RED}Error: {e}{RESET}")
        traceback.print_exc()
        return False

    return True


def show_status():
    """Show system status"""
    print_section("System Status")

    print(f"Python: {sys.version.split()[0]}")
    print(f"Working Directory: {os.getcwd()}")

    # Module status
    print("\nModule Status:")

    modules_status = []

    core_modules = [
        ("isaac_bridge", "Bridge"),
        ("models", "Models"),
        ("data_processor", "Data Processor"),
        ("environment", "Environment"),
    ]

    ai_modules = [
        ("basic_controllers", "Controllers"),
        ("threat_analysis", "Threat Analysis"),
        ("pathfinding", "Pathfinding"),
        ("state_machine", "State Machine"),
        ("strategy_system", "Strategy"),
        ("behavior_tree", "Behavior Tree"),
        ("smart_aiming", "Smart Aiming"),
        ("adaptive_system", "Adaptive"),
        ("orchestrator", "Orchestrator"),
        ("orchestrator_enhanced", "Enhanced"),
    ]

    print("  Core Modules:")
    for name, desc in core_modules:
        try:
            __import__(name)
            print_status(desc, "OK", "OK")
            modules_status.append(True)
        except ImportError:
            print_status(desc, "MISSING", "FAIL")
            modules_status.append(False)

    print("\n  AI Modules:")
    for name, desc in ai_modules:
        try:
            __import__(name)
            print_status(desc, "OK", "OK")
            modules_status.append(True)
        except ImportError:
            print_status(desc, "MISSING", "FAIL")
            modules_status.append(False)

    # Summary
    print("\nSummary:")
    total = len(modules_status)
    loaded = sum(modules_status)
    print(f"  Loaded: {loaded}/{total}")

    if loaded == total:
        print(f"\n{GREEN}System ready!{RESET}")
        return True
    else:
        print(f"\n{YELLOW}Some modules missing{RESET}")
        return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="SocketBridge AI Combat System Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                  # Interactive mode
  python run.py --basic          # Basic bridge only
  python run.py --ai             # Full AI mode
  python run.py --test           # Run tests
  python run.py --status         # Check status
        """,
    )

    parser.add_argument("--basic", action="store_true", help="Start basic bridge mode")
    parser.add_argument("--ai", action="store_true", help="Start AI combat mode")
    parser.add_argument("--test", action="store_true", help="Run tests only")
    parser.add_argument("--status", action="store_true", help="Show system status only")
    parser.add_argument("--compat", action="store_true", help="Run compatibility tests")

    args = parser.parse_args()

    print_banner()

    # Default to interactive mode if no args
    if not any([args.basic, args.ai, args.test, args.status, args.compat]):
        args.interactive = True
    else:
        args.interactive = False

    # Check environment first
    env_ok = check_environment()

    if not env_ok:
        print(f"\n{RED}Environment check failed!{RESET}")
        print("Please ensure all modules are properly installed.")
        sys.exit(1)

    if args.status:
        show_status()
        return

    if args.test:
        run_tests()
        return

    if args.compat:
        run_compatibility_tests()
        return

    if args.basic:
        start_basic_mode()
        return

    if args.ai:
        start_ai_mode()
        return

    # Interactive mode
    print_section("Interactive Mode")

    print("Select mode:")
    print("  1. Basic Bridge (receive data, manual control)")
    print("  2. AI Combat (automatic combat)")
    print("  3. Run Tests")
    print("  4. Show Status")
    print("  5. Exit")

    choice = input("\nEnter choice (1-5): ").strip()

    if choice == "1":
        start_basic_mode()
    elif choice == "2":
        start_ai_mode()
    elif choice == "3":
        run_tests()
    elif choice == "4":
        show_status()
    elif choice == "5":
        print("Goodbye!")
    else:
        print("Invalid choice")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Interrupted by user{RESET}")
        sys.exit(0)
    except Exception as e:
        import traceback

        print(f"\n{RED}Fatal error: {e}{RESET}")
        traceback.print_exc()
        sys.exit(1)
