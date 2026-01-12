"""
Windows Compatibility Test Suite
验证 Python 代码在 Windows 平台上的兼容性
"""

import sys
import os
import tempfile
from pathlib import Path


def test_path_handling():
    """测试路径处理兼容性"""
    print("=" * 60)
    print("测试 1: 路径处理")
    print("=" * 60)

    # 测试相对路径
    relative_paths = [
        "./data",
        "./logs",
        "./recordings",
        "data/output",
        "logs/test.txt",
    ]

    for path_str in relative_paths:
        p = Path(path_str)
        # 验证路径创建和操作
        str_repr = str(p)
        parts = p.parts
        parent = p.parent
        print(f"  ✓ 相对路径 '{path_str}' -> parts={len(parts)}")

    # 测试路径拼接
    base = Path("./data")
    subdir = base / "output" / "file.txt"
    print(f"  ✓ 路径拼接: {subdir}")

    print("  [PASS] 路径处理测试通过\n")
    return True


def test_socket_compatibility():
    """测试 socket 兼容性"""
    print("=" * 60)
    print("测试 2: Socket 兼容性")
    print("=" * 60)

    import socket

    # 测试基本 socket 创建
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))  # 使用随机端口
        s.listen(1)
        s.close()
        print("  ✓ TCP socket 创建和绑定正常")
    except Exception as e:
        print(f"  ✗ Socket 错误: {e}")
        return False

    # 测试超时设置
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.close()
        print("  ✓ Socket 超时设置正常")
    except Exception as e:
        print(f"  ✗ 超时设置错误: {e}")
        return False

    print("  [PASS] Socket 兼容性测试通过\n")
    return True


def test_threading_compatibility():
    """测试 threading 兼容性"""
    print("=" * 60)
    print("测试 3: Threading 兼容性")
    print("=" * 60)

    import threading
    import time

    result = {"value": 0}
    lock = threading.Lock()

    def worker():
        time.sleep(0.1)
        with lock:
            result["value"] += 1

    # 测试 daemon 线程
    threads = []
    for i in range(3):
        t = threading.Thread(target=worker, daemon=True)
        threads.append(t)
        t.start()

    # 等待所有线程完成
    for t in threads:
        t.join(timeout=2.0)

    if result["value"] == 3:
        print("  ✓ Daemon 线程创建和执行正常")
    else:
        print(f"  ✗ 线程执行结果异常: {result['value']}")
        return False

    # 测试 Queue
    from queue import Queue

    q = Queue()
    q.put(1)
    q.put(2)

    if q.get() == 1 and q.get() == 2:
        print("  ✓ Queue 操作正常")
    else:
        print("  ✗ Queue 操作异常")
        return False

    print("  [PASS] Threading 兼容性测试通过\n")
    return True


def test_encoding_compatibility():
    """测试编码兼容性"""
    print("=" * 60)
    print("测试 4: 编码兼容性")
    print("=" * 60)

    import tempfile
    import json

    # 测试 UTF-8 编码读写
    test_strings = [
        "Hello World",
        "中文测试",
        "한국어 테스트",
        "🎮 游戏",
        "Special chars: é ü ñ @#$%",
    ]

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", delete=False, suffix=".json"
    ) as f:
        temp_path = f.name
        data = {"strings": test_strings, "mixed": "Hello 世界"}
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 验证读取
    with open(temp_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    # 清理
    os.unlink(temp_path)

    if loaded["strings"] == test_strings:
        print("  ✓ UTF-8 编码读写正常")
    else:
        print("  ✗ 编码读写异常")
        return False

    print("  [PASS] 编码兼容性测试通过\n")
    return True


def test_json_compatibility():
    """测试 JSON 兼容性"""
    print("=" * 60)
    print("测试 5: JSON 兼容性")
    print("=" * 60)

    import json
    import gzip

    test_data = {
        "frame": 100,
        "position": {"x": 400.5, "y": 300.2},
        "strings": ["test", "中文", "🎮"],
        "nested": {"level1": {"level2": "value"}},
    }

    # 测试标准 JSON
    json_str = json.dumps(test_data, ensure_ascii=False)
    loaded = json.loads(json_str)

    if loaded["frame"] == 100:
        print("  ✓ JSON 序列化/反序列化正常")
    else:
        print("  ✗ JSON 处理异常")
        return False

    # 测试 gzip + JSON
    with tempfile.NamedTemporaryFile(suffix=".json.gz", delete=False) as f:
        temp_path = f.name

    try:
        with gzip.open(temp_path, "wt", encoding="utf-8") as f:
            json.dump(test_data, f, ensure_ascii=False)

        with gzip.open(temp_path, "rt", encoding="utf-8") as f:
            loaded_gzip = json.load(f)

        if loaded_gzip["frame"] == 100:
            print("  ✓ Gzip + JSON 压缩正常")
        else:
            print("  ✗ Gzip 处理异常")
            return False
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    print("  [PASS] JSON 兼容性测试通过\n")
    return True


def test_import_compatibility():
    """测试模块导入兼容性"""
    print("=" * 60)
    print("测试 6: 模块导入兼容性")
    print("=" * 60)

    # 测试核心模块导入
    try:
        from isaac_bridge import IsaacBridge, GameDataAccessor

        print("  ✓ isaac_bridge 模块导入正常")
    except ImportError as e:
        print(f"  ✗ isaac_bridge 导入失败: {e}")
        return False

    try:
        from data_processor import DataProcessor

        print("  ✓ data_processor 模块导入正常")
    except ImportError as e:
        print(f"  ✗ data_processor 导入失败: {e}")
        return False

    try:
        from orchestrator_enhanced import EnhancedCombatOrchestrator, SimpleAI

        print("  ✓ orchestrator_enhanced 模块导入正常")
    except ImportError as e:
        print(f"  ✗ orchestrator_enhanced 导入失败: {e}")
        return False

    try:
        from state_machine import HierarchicalStateMachine

        print("  ✓ state_machine 模块导入正常")
    except ImportError as e:
        print(f"  ✗ state_machine 导入失败: {e}")
        return False

    try:
        from strategy_system import StrategyManager

        print("  ✓ strategy_system 模块导入正常")
    except ImportError as e:
        print(f"  ✗ strategy_system 导入失败: {e}")
        return False

    try:
        from behavior_tree import BehaviorTree

        print("  ✓ behavior_tree 模块导入正常")
    except ImportError as e:
        print(f"  ✗ behavior_tree 导入失败: {e}")
        return False

    try:
        from smart_aiming import SmartAimingSystem

        print("  ✓ smart_aiming 模块导入正常")
    except ImportError as e:
        print(f"  ✗ smart_aiming 导入失败: {e}")
        return False

    try:
        from adaptive_system import AdaptiveParameterSystem

        print("  ✓ adaptive_system 模块导入正常")
    except ImportError as e:
        print(f"  ✗ adaptive_system 导入失败: {e}")
        return False

    print("  [PASS] 模块导入兼容性测试通过\n")
    return True


def test_main_modules():
    """测试主模块功能"""
    print("=" * 60)
    print("测试 7: 主模块功能测试")
    print("=" * 60)

    try:
        from orchestrator_enhanced import (
            EnhancedCombatOrchestrator,
            SimpleAI,
            AIConfig,
            CombatState,
        )

        # 测试配置创建
        config = AIConfig(
            enable_behavior_tree=True,
            enable_advanced_control=True,
            enable_adaptive_behavior=True,
        )
        print("  ✓ AIConfig 创建正常")

        # 测试 orchestrator 创建
        orchestrator = EnhancedCombatOrchestrator(config)
        orchestrator.initialize()
        print("  ✓ EnhancedCombatOrchestrator 初始化正常")

        # 测试 SimpleAI
        ai = SimpleAI(use_enhanced=True)
        ai.connect()
        print("  ✓ SimpleAI 创建和连接正常")

        return True
    except Exception as e:
        print(f"  ✗ 主模块测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def run_all_tests():
    """运行所有兼容性测试"""
    print("\n" + "=" * 60)
    print("Windows 兼容性测试套件")
    print("=" * 60)
    print(f"Python 版本: {sys.version}")
    print(f"操作系统: {sys.platform}")
    print("=" * 60 + "\n")

    tests = [
        ("路径处理", test_path_handling),
        ("Socket 兼容性", test_socket_compatibility),
        ("Threading 兼容性", test_threading_compatibility),
        ("编码兼容性", test_encoding_compatibility),
        ("JSON 兼容性", test_json_compatibility),
        ("模块导入", test_import_compatibility),
        ("主模块功能", test_main_modules),
    ]

    results = []
    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"  ✗ 测试异常: {e}")
            results.append((name, False))

    # 汇总结果
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("✅ 所有兼容性测试通过!")
        print("代码可以在 Windows 平台上正常运行。")
    else:
        print("❌ 部分测试失败，请检查上述问题。")
    print("=" * 60 + "\n")

    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
