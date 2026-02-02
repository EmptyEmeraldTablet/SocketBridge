#!/usr/bin/env python3
"""
SocketBridge Data Channel Test Suite
=====================================

Comprehensive tests for all data channels to verify:
- Data format correctness
- Schema validation
- Entity lifecycle tracking
- Known issue detection
- Game-side vs Python-side issue identification

Usage:
    python3 test_data_channels.py                    # Run all tests
    python3 test_data_channels.py --channel ENEMIES  # Test specific channel
    python3 test_data_channels.py --known-issues     # Test known issue detection
    python3 test_data_channels.py --compare          # Compare with recorded data
"""

import json
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

# Import the data validator
from data_validator import (
    DataValidator,
    ValidationIssue,
    IssueSeverity,
    DataChannel,
    ValidationStatus,
)


@dataclass
class TestResult:
    """Result of a single test"""

    test_name: str
    passed: bool
    expected_issues: int
    actual_issues: int
    details: str = ""
    issues: List[Dict] = field(default_factory=list)


class DataChannelTestSuite:
    """Test suite for all data channels"""

    def __init__(self):
        self.validator = DataValidator()
        self.results: List[TestResult] = []
        self.passed_count = 0
        self.failed_count = 0

    def run_all_tests(self) -> Dict:
        """Run all data channel tests"""
        print("=" * 60)
        print("SOCKETBRIDGE DATA CHANNEL TEST SUITE")
        print("=" * 60)
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Run tests for each channel
        self.test_player_position()
        self.test_player_health()
        self.test_enemies()
        self.test_projectiles()
        self.test_room_info()
        self.test_room_layout()
        self.test_pickups()
        self.test_fire_hazards()
        self.test_bombs()

        # Test known issues
        self.test_known_game_issues()

        # Test entity lifecycle
        self.test_entity_lifecycle()

        # Test room transitions
        self.test_room_transitions()

        # Print summary
        self.print_summary()

        return self.get_summary()

    def test_player_position(self):
        """Test PLAYER_POSITION channel validation"""
        print("Testing PLAYER_POSITION channel...")

        # Valid data
        valid_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 100,
            "room_index": 42,
            "channels": ["PLAYER_POSITION"],
            "payload": {
                "PLAYER_POSITION": {
                    "1": {
                        "pos": {"x": 100.0, "y": 200.0},
                        "vel": {"x": 0.0, "y": 0.0},
                        "move_dir": 0,
                        "fire_dir": 4,
                        "aim_dir": {"x": 1.0, "y": 0.0},
                    }
                }
            },
        }

        issues = self.validator.validate_message(valid_data)
        self.add_result("PLAYER_POSITION valid data", len(issues) == 0, 0, len(issues))

        # Missing required field
        invalid_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 101,
            "room_index": 42,
            "channels": ["PLAYER_POSITION"],
            "payload": {
                "PLAYER_POSITION": {
                    "1": {
                        "pos": {"x": 100.0, "y": 200.0},
                        # Missing vel and aim_dir
                    }
                }
            },
        }

        issues = self.validator.validate_message(invalid_data)
        self.add_result(
            "PLAYER_POSITION missing field", len(issues) > 0, 1, len(issues)
        )

        # Invalid type
        invalid_type = {
            "version": "2.0",
            "type": "DATA",
            "frame": 102,
            "room_index": 42,
            "channels": ["PLAYER_POSITION"],
            "payload": {
                "PLAYER_POSITION": "invalid"  # Should be dict
            },
        }

        issues = self.validator.validate_message(invalid_type)
        self.add_result("PLAYER_POSITION invalid type", len(issues) > 0, 1, len(issues))

        print(
            f"  PLAYER_POSITION: {self.results[-1].passed and '✅ PASS' or '❌ FAIL'}"
        )

    def test_player_health(self):
        """Test PLAYER_HEALTH channel validation"""
        print("Testing PLAYER_HEALTH channel...")

        valid_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 100,
            "room_index": 42,
            "channels": ["PLAYER_HEALTH"],
            "payload": {
                "PLAYER_HEALTH": {
                    "1": {
                        "red_hearts": 3,
                        "max_hearts": 6,
                        "soul_hearts": 2,
                        "black_hearts": 0,
                    }
                }
            },
        }

        issues = self.validator.validate_message(valid_data)
        self.add_result("PLAYER_HEALTH valid data", len(issues) == 0, 0, len(issues))

        # Negative hearts
        invalid_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 101,
            "room_index": 42,
            "channels": ["PLAYER_HEALTH"],
            "payload": {
                "PLAYER_HEALTH": {
                    "1": {
                        "red_hearts": -1,  # Invalid
                        "max_hearts": 6,
                    }
                }
            },
        }

        issues = self.validator.validate_message(invalid_data)
        self.add_result(
            "PLAYER_HEALTH negative hearts", len(issues) > 0, 1, len(issues)
        )

        print(f"  PLAYER_HEALTH: {self.results[-1].passed and '✅ PASS' or '❌ FAIL'}")

    def test_enemies(self):
        """Test ENEMIES channel validation"""
        print("Testing ENEMIES channel...")

        valid_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 100,
            "room_index": 42,
            "channels": ["ENEMIES"],
            "payload": {
                "ENEMIES": [
                    {
                        "id": 1,
                        "type": 10,
                        "variant": 0,
                        "pos": {"x": 300.0, "y": 200.0},
                        "hp": 10.0,
                        "max_hp": 10.0,
                    }
                ]
            },
        }

        issues = self.validator.validate_message(valid_data)
        self.add_result("ENEMIES valid data", len(issues) == 0, 0, len(issues))

        # Duplicate IDs
        dup_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 101,
            "room_index": 42,
            "channels": ["ENEMIES"],
            "payload": {
                "ENEMIES": [
                    {
                        "id": 1,
                        "type": 10,
                        "pos": {"x": 300.0, "y": 200.0},
                        "hp": 10.0,
                        "max_hp": 10.0,
                    },
                    {
                        "id": 1,
                        "type": 10,
                        "pos": {"x": 400.0, "y": 200.0},
                        "hp": 10.0,
                        "max_hp": 10.0,
                    },
                ]
            },
        }

        issues = self.validator.validate_message(dup_data)
        self.add_result("ENEMIES duplicate IDs", len(issues) > 0, 1, len(issues))

        # HP > max_hp
        hp_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 102,
            "room_index": 42,
            "channels": ["ENEMIES"],
            "payload": {
                "ENEMIES": [
                    {
                        "id": 1,
                        "type": 10,
                        "pos": {"x": 300.0, "y": 200.0},
                        "hp": 15.0,
                        "max_hp": 10.0,
                    }
                ]
            },
        }

        issues = self.validator.validate_message(hp_data)
        self.add_result("ENEMIES HP > max_hp", len(issues) > 0, 1, len(issues))

        print(f"  ENEMIES: {self.results[-1].passed and '✅ PASS' or '❌ FAIL'}")

    def test_projectiles(self):
        """Test PROJECTILES channel validation"""
        print("Testing PROJECTILES channel...")

        valid_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 100,
            "room_index": 42,
            "channels": ["PROJECTILES"],
            "payload": {
                "PROJECTILES": {
                    "enemy_projectiles": [
                        {
                            "id": 1,
                            "pos": {"x": 250.0, "y": 180.0},
                            "vel": {"x": -2.0, "y": 0.0},
                        }
                    ],
                    "player_tears": [],
                    "lasers": [],
                }
            },
        }

        issues = self.validator.validate_message(valid_data)
        self.add_result("PROJECTILES valid data", len(issues) == 0, 0, len(issues))

        # Invalid structure
        invalid_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 101,
            "room_index": 42,
            "channels": ["PROJECTILES"],
            "payload": {"PROJECTILES": "should be dict"},
        }

        issues = self.validator.validate_message(invalid_data)
        self.add_result(
            "PROJECTILES invalid structure", len(issues) > 0, 1, len(issues)
        )

        print(f"  PROJECTILES: {self.results[-1].passed and '✅ PASS' or '❌ FAIL'}")

    def test_room_info(self):
        """Test ROOM_INFO channel validation"""
        print("Testing ROOM_INFO channel...")

        valid_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 100,
            "room_index": 42,
            "channels": ["ROOM_INFO"],
            "payload": {
                "ROOM_INFO": {
                    "room_index": 42,
                    "stage": 2,
                    "grid_width": 13,
                    "grid_height": 7,
                    "is_clear": False,
                    "enemy_count": 5,
                }
            },
        }

        issues = self.validator.validate_message(valid_data)
        self.add_result("ROOM_INFO valid data", len(issues) == 0, 0, len(issues))

        # Invalid stage
        invalid_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 101,
            "room_index": 42,
            "channels": ["ROOM_INFO"],
            "payload": {
                "ROOM_INFO": {
                    "room_index": 42,
                    "stage": 99,  # Invalid
                    "grid_width": 13,
                    "grid_height": 7,
                }
            },
        }

        issues = self.validator.validate_message(invalid_data)
        self.add_result("ROOM_INFO invalid stage", len(issues) > 0, 1, len(issues))

        print(f"  ROOM_INFO: {self.results[-1].passed and '✅ PASS' or '❌ FAIL'}")

    def test_room_layout(self):
        """Test ROOM_LAYOUT channel validation"""
        print("Testing ROOM_LAYOUT channel...")

        valid_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 100,
            "room_index": 42,
            "channels": ["ROOM_LAYOUT"],
            "payload": {
                "ROOM_LAYOUT": {
                    "grid": {
                        "0": {"type": 2, "variant": 0, "x": 280.0, "y": 140.0},
                        "1": {"type": 3, "variant": 0, "x": 371.0, "y": 140.0},
                    },
                    "doors": {"0": {"target_room": 41, "is_open": True}},
                }
            },
        }

        issues = self.validator.validate_message(valid_data)
        self.add_result("ROOM_LAYOUT valid data", len(issues) == 0, 0, len(issues))

        # Deprecated grid type (GRID_FIREPLACE)
        deprecated_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 101,
            "room_index": 42,
            "channels": ["ROOM_LAYOUT"],
            "payload": {
                "ROOM_LAYOUT": {
                    "grid": {
                        "0": {"type": 13, "variant": 0}  # GRID_FIREPLACE deprecated
                    },
                    "doors": {},
                }
            },
        }

        issues = self.validator.validate_message(deprecated_data)
        # Should detect deprecated type (as INFO level)
        self.add_result("ROOM_LAYOUT deprecated type", len(issues) > 0, 1, len(issues))

        # Invalid grid type
        invalid_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 102,
            "room_index": 42,
            "channels": ["ROOM_LAYOUT"],
            "payload": {
                "ROOM_LAYOUT": {
                    "grid": {
                        "0": {"type": 999, "variant": 0}  # Invalid
                    },
                    "doors": {},
                }
            },
        }

        issues = self.validator.validate_message(invalid_data)
        self.add_result("ROOM_LAYOUT invalid type", len(issues) > 0, 1, len(issues))

        print(f"  ROOM_LAYOUT: {self.results[-1].passed and '✅ PASS' or '❌ FAIL'}")

    def test_pickups(self):
        """Test PICKUPS channel validation"""
        print("Testing PICKUPS channel...")

        valid_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 100,
            "room_index": 42,
            "channels": ["PICKUPS"],
            "payload": {
                "PICKUPS": [{"id": 1, "variant": 20, "pos": {"x": 350.0, "y": 300.0}}]
            },
        }

        issues = self.validator.validate_message(valid_data)
        self.add_result("PICKUPS valid data", len(issues) == 0, 0, len(issues))

        # Missing required field
        invalid_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 101,
            "room_index": 42,
            "channels": ["PICKUPS"],
            "payload": {
                "PICKUPS": [
                    {"id": 1, "pos": {"x": 350.0, "y": 300.0}}  # Missing variant
                ]
            },
        }

        issues = self.validator.validate_message(invalid_data)
        self.add_result("PICKUPS missing variant", len(issues) > 0, 1, len(issues))

        print(f"  PICKUPS: {self.results[-1].passed and '✅ PASS' or '❌ FAIL'}")

    def test_fire_hazards(self):
        """Test FIRE_HAZARDS channel validation"""
        print("Testing FIRE_HAZARDS channel...")

        valid_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 100,
            "room_index": 42,
            "channels": ["FIRE_HAZARDS"],
            "payload": {
                "FIRE_HAZARDS": [
                    {
                        "id": 1,
                        "type": "FIREPLACE",
                        "hp": 5.0,
                        "pos": {"x": 400.0, "y": 350.0},
                    }
                ]
            },
        }

        issues = self.validator.validate_message(valid_data)
        self.add_result("FIRE_HAZARDS valid data", len(issues) == 0, 0, len(issues))

        print(f"  FIRE_HAZARDS: {self.results[-1].passed and '✅ PASS' or '❌ FAIL'}")

    def test_bombs(self):
        """Test BOMBS channel validation"""
        print("Testing BOMBS channel...")

        valid_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 100,
            "room_index": 42,
            "channels": ["BOMBS"],
            "payload": {
                "BOMBS": [
                    {"id": 1, "type": 4, "timer": 60, "pos": {"x": 350.0, "y": 300.0}}
                ]
            },
        }

        issues = self.validator.validate_message(valid_data)
        self.add_result("BOMBS valid data", len(issues) == 0, 0, len(issues))

        # Negative timer
        invalid_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 101,
            "room_index": 42,
            "channels": ["BOMBS"],
            "payload": {
                "BOMBS": [
                    {"id": 1, "type": 4, "timer": -1, "pos": {"x": 350.0, "y": 300.0}}
                ]
            },
        }

        issues = self.validator.validate_message(invalid_data)
        self.add_result("BOMBS negative timer", len(issues) > 0, 1, len(issues))

        print(f"  BOMBS: {self.results[-1].passed and '✅ PASS' or '❌ FAIL'}")

    def test_known_game_issues(self):
        """Test detection of known game-side issues"""
        print("Testing known game issue detection...")

        # Test aim_dir zero
        aim_zero_data = {
            "version": "2.0",
            "type": "DATA",
            "frame": 100,
            "room_index": 42,
            "channels": ["PLAYER_POSITION"],
            "payload": {
                "PLAYER_POSITION": {
                    "1": {
                        "pos": {"x": 100.0, "y": 200.0},
                        "vel": {"x": 0.0, "y": 0.0},
                        "move_dir": 0,
                        "fire_dir": 4,
                        "aim_dir": {"x": 0.0, "y": 0.0},  # Known issue
                    }
                }
            },
        }

        issues = self.validator.validate_message(aim_zero_data)
        self.add_result("Known issue: aim_dir (0,0)", len(issues) > 0, 1, len(issues))

        print(f"  Known issues: {self.results[-1].passed and '✅ PASS' or '❌ FAIL'}")

    def test_entity_lifecycle(self):
        """Test entity lifecycle tracking"""
        print("Testing entity lifecycle tracking...")

        # Simulate enemy appearing and disappearing
        enemy_appear = {
            "version": "2.0",
            "type": "DATA",
            "frame": 100,
            "room_index": 42,
            "channels": ["ENEMIES"],
            "payload": {
                "ENEMIES": [
                    {
                        "id": 1,
                        "type": 10,
                        "pos": {"x": 300.0, "y": 200.0},
                        "hp": 10.0,
                        "max_hp": 10.0,
                    }
                ]
            },
        }

        self.validator.validate_message(enemy_appear)

        # Enemy disappears (no ENEMIES in payload)
        enemy_disappear = {
            "version": "2.0",
            "type": "DATA",
            "frame": 200,
            "room_index": 42,
            "channels": ["ENEMIES"],
            "payload": {
                "ENEMIES": []  # Enemy gone
            },
        }

        self.validator.validate_message(enemy_disappear)

        # Check lifecycle tracking
        # Note: When enemy disappears (empty list), we don't process it
        # so tracker.last_seen_frame remains at 100 (first seen)
        # This is expected - we only track when we see the enemy
        tracker_key = ("enemy", 1)
        if tracker_key in self.validator.entity_trackers:
            tracker = self.validator.entity_trackers[tracker_key]
            # Tracker should have first_seen_frame = 100
            self.add_result(
                "Entity lifecycle tracking",
                tracker.first_seen_frame == 100,  # First seen at frame 100
                1,
                1,
            )
        else:
            self.add_result("Entity lifecycle tracking", False, 1, 0)

        print(
            f"  Entity lifecycle: {self.results[-1].passed and '✅ PASS' or '❌ FAIL'}"
        )

    def test_room_transitions(self):
        """Test room transition detection"""
        print("Testing room transition detection...")

        # Room 42
        room_42 = {
            "version": "2.0",
            "type": "DATA",
            "frame": 100,
            "room_index": 42,
            "channels": ["ROOM_INFO"],
            "payload": {
                "ROOM_INFO": {
                    "room_index": 42,
                    "stage": 2,
                    "grid_width": 13,
                    "grid_height": 7,
                }
            },
        }

        self.validator.validate_message(room_42)

        # Transition to room 43
        room_43 = {
            "version": "2.0",
            "type": "DATA",
            "frame": 150,
            "room_index": 43,
            "channels": ["ROOM_INFO"],
            "payload": {
                "ROOM_INFO": {
                    "room_index": 43,
                    "stage": 2,
                    "grid_width": 13,
                    "grid_height": 7,
                }
            },
        }

        self.validator.validate_message(room_43)

        # Check transition recorded
        if len(self.validator.room_transitions) > 0:
            transition = self.validator.room_transitions[0]
            self.add_result(
                "Room transition detection", transition == (150, 42, 43), 1, 1
            )
        else:
            self.add_result("Room transition detection", False, 1, 0)

        print(
            f"  Room transitions: {self.results[-1].passed and '✅ PASS' or '❌ FAIL'}"
        )

    def add_result(
        self,
        test_name: str,
        passed: bool,
        expected: int,
        actual: int,
        details: str = "",
    ):
        """Add a test result"""
        result = TestResult(
            test_name=test_name,
            passed=passed,
            expected_issues=expected,
            actual_issues=actual,
            details=details,
        )
        self.results.append(result)

        if passed:
            self.passed_count += 1
        else:
            self.failed_count += 1

    def print_summary(self):
        """Print test summary"""
        print()
        print("=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"Total tests: {len(self.results)}")
        print(f"Passed: {self.passed_count} ✅")
        print(f"Failed: {self.failed_count} ❌")
        print()

        if self.failed_count > 0:
            print("Failed tests:")
            for result in self.results:
                if not result.passed:
                    print(f"  ❌ {result.test_name}")
                    print(
                        f"     Expected {result.expected_issues} issues, got {result.actual_issues}"
                    )

        print()
        print("=" * 60)

    def get_summary(self) -> Dict:
        """Get test summary as dictionary"""
        return {
            "total_tests": len(self.results),
            "passed": self.passed_count,
            "failed": self.failed_count,
            "pass_rate": f"{100 * self.passed_count / max(1, len(self.results)):.1f}%",
            "results": [
                {
                    "test": r.test_name,
                    "passed": r.passed,
                    "expected_issues": r.expected_issues,
                    "actual_issues": r.actual_issues,
                }
                for r in self.results
            ],
        }


def main():
    parser = argparse.ArgumentParser(
        description="SocketBridge Data Channel Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 test_data_channels.py                    # Run all tests
  python3 test_data_channels.py --channel ENEMIES  # Test specific channel
  python3 test_data_channels.py --known-issues     # Test known issue detection
        """,
    )

    parser.add_argument(
        "--channel",
        choices=[
            "PLAYER_POSITION",
            "PLAYER_HEALTH",
            "ENEMIES",
            "PROJECTILES",
            "ROOM_INFO",
            "ROOM_LAYOUT",
            "PICKUPS",
            "FIRE_HAZARDS",
            "BOMBS",
        ],
        help="Test specific channel only",
    )
    parser.add_argument(
        "--known-issues", action="store_true", help="Test known issue detection"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    suite = DataChannelTestSuite()

    if args.channel:
        # Test specific channel
        test_method = getattr(suite, f"test_{args.channel.lower()}")
        test_method()
    else:
        # Run all tests
        summary = suite.run_all_tests()

        if args.json:
            print(json.dumps(summary, indent=2))

        # Exit with appropriate code
        sys.exit(0 if summary["failed"] == 0 else 1)


if __name__ == "__main__":
    main()
