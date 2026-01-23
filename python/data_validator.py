#!/usr/bin/env python3
"""
SocketBridge Data Validation Framework
=======================================

A comprehensive testing framework for validating data integrity
between Lua (game) and Python (AI backend).

Purpose:
- Detect data anomalies in real-time
- Identify game-side bugs vs Python-side bugs
- Track entity lifecycle inconsistencies
- Generate detailed validation reports
- Document known game issues

Usage:
    python3 data_validator.py --live           # Real-time validation
    python3 data_validator.py --replay FILE    # Validate recorded data
    python3 data_validator.py --report FILE    # Generate report from log
"""

import json
import time
import logging
import statistics
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set, Tuple
from collections import defaultdict, deque
from enum import Enum
from pathlib import Path
import argparse
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("DataValidator")


class ValidationStatus(Enum):
    """Validation result status"""

    PASS = "✅ PASS"
    FAIL = "❌ FAIL"
    WARN = "⚠️ WARN"
    SKIP = "⏭️ SKIP"
    UNKNOWN = "❓ UNKNOWN"


class IssueSeverity(Enum):
    """Issue severity levels"""

    CRITICAL = 1  # Data completely invalid
    HIGH = 2  # Significant data issue
    MEDIUM = 3  # Moderate issue
    LOW = 4  # Minor issue / inconsistency
    INFO = 5  # Informational


class DataChannel(Enum):
    """All supported data channels"""

    PLAYER_POSITION = "PLAYER_POSITION"
    PLAYER_STATS = "PLAYER_STATS"
    PLAYER_HEALTH = "PLAYER_HEALTH"
    PLAYER_INVENTORY = "PLAYER_INVENTORY"
    ENEMIES = "ENEMIES"
    PROJECTILES = "PROJECTILES"
    ROOM_INFO = "ROOM_INFO"
    ROOM_LAYOUT = "ROOM_LAYOUT"
    BOMBS = "BOMBS"
    INTERACTABLES = "INTERACTABLES"
    PICKUPS = "PICKUPS"
    FIRE_HAZARDS = "FIRE_HAZARDS"
    BUTTONS = "BUTTONS"


@dataclass
class ValidationIssue:
    """A single validation issue"""

    timestamp: float
    frame: int
    channel: str
    severity: IssueSeverity
    issue_type: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    is_game_side: bool = False  # True if confirmed game-side issue

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "frame": self.frame,
            "channel": self.channel,
            "severity": self.severity.name,
            "issue_type": self.issue_type,
            "message": self.message,
            "details": self.details,
            "is_game_side": self.is_game_side,
        }


@dataclass
class ChannelStats:
    """Statistics for a single data channel"""

    channel: str
    message_count: int = 0
    validation_count: int = 0
    pass_count: int = 0
    fail_count: int = 0
    warn_count: int = 0
    first_frame: int = -1
    last_frame: int = -1
    avg_processing_time_ms: float = 0.0
    issues: List[ValidationIssue] = field(default_factory=list)

    def record_validation(
        self, status: ValidationStatus, processing_time_ms: float = 0
    ):
        self.validation_count += 1
        self.avg_processing_time_ms = (
            self.avg_processing_time_ms * (self.validation_count - 1)
            + processing_time_ms
        ) / self.validation_count
        if status == ValidationStatus.PASS:
            self.pass_count += 1
        elif status == ValidationStatus.FAIL:
            self.fail_count += 1
        elif status == ValidationStatus.WARN:
            self.warn_count += 1


@dataclass
class EntityTracker:
    """Track entity lifecycle and detect anomalies"""

    entity_id: int
    entity_type: str
    first_seen_frame: int = -1
    last_seen_frame: int = -1
    positions: List[Tuple[int, int, int]] = field(default_factory=list)  # (frame, x, y)
    hp_history: List[Tuple[int, float]] = field(default_factory=list)  # (frame, hp)
    status_history: List[str] = field(default_factory=list)  # status changes
    is_suspicious: bool = False
    suspicion_reasons: List[str] = field(default_factory=list)

    def update(
        self,
        frame: int,
        pos: Optional[Tuple[float, float]] = None,
        hp: Optional[float] = None,
        status: Optional[str] = None,
    ):
        if self.first_seen_frame == -1:
            self.first_seen_frame = frame
        self.last_seen_frame = frame

        if pos:
            self.positions.append((frame, int(pos[0]), int(pos[1])))

        if hp is not None:
            self.hp_history.append((frame, hp))

        if status:
            self.status_history.append(status)

    def check_suspicious(self) -> bool:
        """Check for suspicious patterns"""
        # HP increase without pickup/regen (potential game bug)
        if len(self.hp_history) >= 2:
            for i in range(1, len(self.hp_history)):
                prev_hp = self.hp_history[i - 1][1]
                curr_hp = self.hp_history[i][1]
                if curr_hp > prev_hp:
                    self.is_suspicious = True
                    self.suspicion_reasons.append(
                        f"HP increased from {prev_hp} to {curr_hp}"
                    )

        # Teleportation (position jump without movement)
        if len(self.positions) >= 2:
            for i in range(1, len(self.positions)):
                prev_pos = self.positions[i - 1]
                curr_pos = self.positions[i]
                distance = (
                    (curr_pos[1] - prev_pos[1]) ** 2 + (curr_pos[2] - prev_pos[2]) ** 2
                ) ** 0.5
                frame_diff = curr_pos[0] - prev_pos[0]
                if frame_diff > 0 and distance > frame_diff * 100:
                    self.is_suspicious = True
                    self.suspicion_reasons.append(
                        f"Teleport detected: {distance:.1f}px in {frame_diff} frames"
                    )

        return self.is_suspicious


class DataValidator:
    """
    Comprehensive data validation framework for SocketBridge.

    Validates:
    - Data channel integrity
    - Entity lifecycle consistency
    - Room transition handling
    - Protocol compliance
    - Known game-side issues

    Usage:
        validator = DataValidator()
        validator.start()
        # ... receive game data ...
        validator.validate_message(raw_msg)
        validator.stop()
    """

    # Protocol version
    PROTOCOL_VERSION = "2.1"

    # Expected field definitions for each channel
    CHANNEL_SCHEMAS = {
        DataChannel.PLAYER_POSITION: {
            "required_fields": ["pos", "vel", "aim_dir"],
            "nested_fields": {
                "pos": ["x", "y"],
                "vel": ["x", "y"],
                "aim_dir": ["x", "y"],
            },
            "value_ranges": {"move_dir": (0, 7), "fire_dir": (0, 7)},
        },
        DataChannel.PLAYER_HEALTH: {
            "required_fields": ["red_hearts", "max_hearts"],
            "value_ranges": {
                "red_hearts": (0, 99),
                "soul_hearts": (0, 99),
                "black_hearts": (0, 99),
            },
        },
        DataChannel.ENEMIES: {
            "required_fields": ["id", "type", "pos", "hp", "max_hp"],
            "nested_fields": {"pos": ["x", "y"], "vel": ["x", "y"]},
            "value_ranges": {"hp": (0, None), "max_hp": (1, None)},
        },
        DataChannel.PROJECTILES: {
            "required_fields": ["id", "pos", "vel"],
            "nested_fields": {"pos": ["x", "y"], "vel": ["x", "y"]},
        },
        DataChannel.ROOM_INFO: {
            "required_fields": ["room_index", "stage", "grid_width", "grid_height"],
            "value_ranges": {
                "room_index": (0, 200),
                "stage": (1, 11),
                "grid_width": (1, 30),
                "grid_height": (1, 20),
            },
        },
        DataChannel.ROOM_LAYOUT: {
            "required_fields": ["grid", "doors"],
            "grid_types": list(range(28)),  # GridEntityType 0-27
            "known_issues": {
                13: "GRID_FIREPLACE deprecated - use ENTITY_EFFECT instead",
                16: "GRID_DOOR should not appear in grid - use doors instead",
            },
        },
        DataChannel.PICKUPS: {
            "required_fields": ["id", "variant", "pos"],
            "nested_fields": {"pos": ["x", "y"]},
            "value_ranges": {
                "variant": (10, 300)  # Approximate range for pickup variants
            },
        },
        DataChannel.FIRE_HAZARDS: {
            "required_fields": ["id", "type", "pos", "hp"],
            "nested_fields": {"pos": ["x", "y"]},
            "value_ranges": {"hp": (0, 100)},
        },
        DataChannel.BOMBS: {
            "required_fields": ["id", "type", "pos", "timer"],
            "nested_fields": {"pos": ["x", "y"]},
            "value_ranges": {"timer": (0, 600)},
        },
    }

    # Known game-side issues (confirmed from testing)
    KNOWN_GAME_ISSUES = {
        (
            "ROOM_LAYOUT",
            "GRID_FIREPLACE",
        ): "Game may send deprecated GRID_FIREPLACE (ID 13) in grid data",
        (
            "ROOM_LAYOUT",
            "GRID_DOOR",
        ): "Game may include GRID_DOOR (ID 16) in grid when it should be in doors",
        (
            "PLAYER_POSITION",
            "aim_dir_zero",
        ): "aim_dir may be (0,0) when player is not aiming",
        (
            "ENEMIES",
            "hp_negative",
        ): "Some enemy types may report negative HP temporarily",
        (
            "PROJECTILES",
            "id_reuse",
        ): "Projectile IDs may be reused within short timeframes",
        (
            "PICKUPS",
            "missing_last_seen",
        ): "Pickups may not have last_seen_frame set, causing cleanup issues",
    }

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.enabled = True
        self.channel_stats: Dict[str, ChannelStats] = {}
        self.entity_trackers: Dict[Tuple[str, int], EntityTracker] = {}
        self.issues: List[ValidationIssue] = []
        self.message_buffer: deque = deque(maxlen=1000)
        self.room_transitions: List[
            Tuple[int, int, int]
        ] = []  # (frame, old_room, new_room)
        self.current_room = -1
        self.frame_count = 0
        self.start_time = time.time()

        # Initialize stats for all channels
        for channel in DataChannel:
            self.channel_stats[channel.value] = ChannelStats(channel=channel.value)

        # Validation counters
        self.total_messages = 0
        self.total_validations = 0
        self.total_issues = 0

        # Issue tracking
        self.issues_by_severity: Dict[IssueSeverity, List[ValidationIssue]] = (
            defaultdict(list)
        )
        self.issues_by_channel: Dict[str, List[ValidationIssue]] = defaultdict(list)

        logger.info("DataValidator initialized")

    def validate_message(self, raw_msg: Dict) -> List[ValidationIssue]:
        """
        Validate a complete message from the game.

        Args:
            raw_msg: Raw message dictionary from Lua

        Returns:
            List of validation issues found
        """
        if not self.enabled:
            return []

        start_time = time.time()
        issues = []
        frame = -1  # Initialize for exception handling

        try:
            # Extract basic info
            frame = raw_msg.get("frame", -1)
            room_index = raw_msg.get("room_index", -1)
            msg_type = raw_msg.get("type", "UNKNOWN")
            channels = raw_msg.get("channels", [])
            payload = raw_msg.get("payload", {})

            self.frame_count = max(self.frame_count, frame)
            self.total_messages += 1

            # Track room transitions
            if self.current_room != -1 and room_index != self.current_room:
                self.room_transitions.append((frame, self.current_room, room_index))
                logger.info(
                    f"[Room Transition] Frame {frame}: {self.current_room} -> {room_index}"
                )
            self.current_room = room_index

            # Buffer message for later analysis
            self.message_buffer.append(
                {
                    "frame": frame,
                    "room_index": room_index,
                    "channels": channels,
                    "timestamp": time.time(),
                }
            )

            # Validate each channel in payload
            for channel_name in channels:
                if channel_name not in [c.value for c in DataChannel]:
                    issue = ValidationIssue(
                        timestamp=time.time(),
                        frame=frame,
                        channel=channel_name,
                        severity=IssueSeverity.LOW,
                        issue_type="UNKNOWN_CHANNEL",
                        message=f"Unknown channel: {channel_name}",
                    )
                    issues.append(issue)
                    continue

                channel_stats = self.channel_stats[channel_name]
                channel_stats.message_count += 1
                if channel_stats.first_frame == -1:
                    channel_stats.first_frame = frame
                channel_stats.last_frame = frame

                # Validate channel data
                channel_issues = self._validate_channel(
                    channel_name, payload.get(channel_name, {}), frame
                )
                issues.extend(channel_issues)

                # Update stats
                if channel_issues:
                    for issue in channel_issues:
                        channel_stats.issues.append(issue)
                        if issue.severity in [
                            IssueSeverity.CRITICAL,
                            IssueSeverity.HIGH,
                        ]:
                            channel_stats.fail_count += 1
                        elif issue.severity == IssueSeverity.MEDIUM:
                            channel_stats.warn_count += 1
                else:
                    channel_stats.pass_count += 1

                self.total_validations += 1

        except Exception as e:
            issue = ValidationIssue(
                timestamp=time.time(),
                frame=frame if "frame" in locals() else -1,
                channel="*",
                severity=IssueSeverity.HIGH,
                issue_type="VALIDATION_ERROR",
                message=f"Validation error: {str(e)}",
                details={"exception": str(e)},
            )
            issues.append(issue)

        processing_time_ms = (time.time() - start_time) * 1000
        for issue in issues:
            issue.timestamp = time.time()
        return issues

    def _validate_channel(
        self, channel_name: str, data: Any, frame: int
    ) -> List[ValidationIssue]:
        """Validate a single channel's data"""
        issues = []

        try:
            channel = DataChannel(channel_name)
            schema = self.CHANNEL_SCHEMAS.get(channel, {})

            if not data:
                # Empty data is valid (game may not send all channels every frame)
                return issues

            # Handle different channel types
            if channel == DataChannel.PLAYER_POSITION:
                issues.extend(self._validate_player_position(data, frame))
            elif channel == DataChannel.PLAYER_HEALTH:
                issues.extend(self._validate_player_health(data, frame))
            elif channel == DataChannel.ENEMIES:
                issues.extend(self._validate_enemies(data, frame))
            elif channel == DataChannel.PROJECTILES:
                issues.extend(self._validate_projectiles(data, frame))
            elif channel == DataChannel.ROOM_INFO:
                issues.extend(self._validate_room_info(data, frame))
            elif channel == DataChannel.ROOM_LAYOUT:
                issues.extend(self._validate_room_layout(data, frame))
            elif channel == DataChannel.PICKUPS:
                issues.extend(self._validate_pickups(data, frame))
            elif channel == DataChannel.FIRE_HAZARDS:
                issues.extend(self._validate_fire_hazards(data, frame))
            elif channel == DataChannel.BOMBS:
                issues.extend(self._validate_bombs(data, frame))

        except ValueError:
            # Unknown channel, already handled
            pass
        except Exception as e:
            issues.append(
                ValidationIssue(
                    timestamp=time.time(),
                    frame=frame,
                    channel=channel_name,
                    severity=IssueSeverity.MEDIUM,
                    issue_type="VALIDATION_ERROR",
                    message=f"Channel validation error: {str(e)}",
                    details={"exception": str(e)},
                )
            )

        return issues

    def _validate_player_position(
        self, data: Dict, frame: int
    ) -> List[ValidationIssue]:
        issues = []
        schema = self.CHANNEL_SCHEMAS[DataChannel.PLAYER_POSITION]

        for player_id, player_data in data.items():
            if not isinstance(player_data, dict):
                issues.append(
                    ValidationIssue(
                        timestamp=time.time(),
                        frame=frame,
                        channel="PLAYER_POSITION",
                        severity=IssueSeverity.HIGH,
                        issue_type="INVALID_TYPE",
                        message=f"Player {player_id} data is not a dict",
                    )
                )
                continue

            # Check required fields
            for field_name in schema["required_fields"]:
                if field_name not in player_data:
                    issues.append(
                        ValidationIssue(
                            timestamp=time.time(),
                            frame=frame,
                            channel="PLAYER_POSITION",
                            severity=IssueSeverity.HIGH,
                            issue_type="MISSING_FIELD",
                            message=f"Player {player_id} missing required field: {field_name}",
                        )
                    )

            # Validate nested fields
            for field_name, sub_fields in schema.get("nested_fields", {}).items():
                if field_name in player_data:
                    sub_data = player_data[field_name]
                    if isinstance(sub_data, dict):
                        for sub_field in sub_fields:
                            if sub_field not in sub_data:
                                issues.append(
                                    ValidationIssue(
                                        timestamp=time.time(),
                                        frame=frame,
                                        channel="PLAYER_POSITION",
                                        severity=IssueSeverity.MEDIUM,
                                        issue_type="MISSING_NESTED_FIELD",
                                        message=f"Player {player_id}.{field_name} missing: {sub_field}",
                                    )
                                )

            # Check value ranges
            for field_name, (min_val, max_val) in schema.get(
                "value_ranges", {}
            ).items():
                if field_name in player_data:
                    val = player_data[field_name]
                    if min_val is not None and val < min_val:
                        issues.append(
                            ValidationIssue(
                                timestamp=time.time(),
                                frame=frame,
                                channel="PLAYER_POSITION",
                                severity=IssueSeverity.LOW,
                                issue_type="VALUE_OUT_OF_RANGE",
                                message=f"Player {player_id} {field_name}={val} < {min_val}",
                            )
                        )
                    if max_val is not None and val > max_val:
                        issues.append(
                            ValidationIssue(
                                timestamp=time.time(),
                                frame=frame,
                                channel="PLAYER_POSITION",
                                severity=IssueSeverity.LOW,
                                issue_type="VALUE_OUT_OF_RANGE",
                                message=f"Player {player_id} {field_name}={val} > {max_val}",
                            )
                        )

            # Check for known game issue: aim_dir (0,0)
            if "aim_dir" in player_data and isinstance(player_data["aim_dir"], dict):
                aim_x = player_data["aim_dir"].get("x", 0)
                aim_y = player_data["aim_dir"].get("y", 0)
                if aim_x == 0 and aim_y == 0:
                    issues.append(
                        ValidationIssue(
                            timestamp=time.time(),
                            frame=frame,
                            channel="PLAYER_POSITION",
                            severity=IssueSeverity.INFO,
                            issue_type="KNOWN_GAME_ISSUE",
                            message=f"Player {player_id} aim_dir is (0,0) - player not aiming",
                            is_game_side=True,
                        )
                    )

            # Track entity
            entity_key = ("player", player_id)
            if entity_key not in self.entity_trackers:
                self.entity_trackers[entity_key] = EntityTracker(
                    entity_id=int(player_id), entity_type="player"
                )
            pos = None
            if "pos" in player_data:
                pos = (player_data["pos"].get("x"), player_data["pos"].get("y"))
            hp = None
            self.entity_trackers[entity_key].update(frame, pos, hp)

        return issues

    def _validate_player_health(self, data: Dict, frame: int) -> List[ValidationIssue]:
        issues = []
        schema = self.CHANNEL_SCHEMAS[DataChannel.PLAYER_HEALTH]

        for player_id, health_data in data.items():
            if not isinstance(health_data, dict):
                continue

            # Check required fields
            for field_name in schema["required_fields"]:
                if field_name not in health_data:
                    issues.append(
                        ValidationIssue(
                            timestamp=time.time(),
                            frame=frame,
                            channel="PLAYER_HEALTH",
                            severity=IssueSeverity.MEDIUM,
                            issue_type="MISSING_FIELD",
                            message=f"Player {player_id} missing: {field_name}",
                        )
                    )

            # Check value ranges
            for field_name, (min_val, max_val) in schema.get(
                "value_ranges", {}
            ).items():
                if field_name in health_data:
                    val = health_data[field_name]
                    if val < min_val:
                        issues.append(
                            ValidationIssue(
                                timestamp=time.time(),
                                frame=frame,
                                channel="PLAYER_HEALTH",
                                severity=IssueSeverity.HIGH,
                                issue_type="INVALID_VALUE",
                                message=f"Player {player_id} {field_name}={val} (negative?)",
                            )
                        )

        return issues

    def _validate_enemies(self, data: List, frame: int) -> List[ValidationIssue]:
        issues = []

        if not isinstance(data, list):
            issues.append(
                ValidationIssue(
                    timestamp=time.time(),
                    frame=frame,
                    channel="ENEMIES",
                    severity=IssueSeverity.HIGH,
                    issue_type="INVALID_TYPE",
                    message=f"ENEMIES data is not a list: {type(data)}",
                )
            )
            return issues

        entity_ids_seen: Set[int] = set()

        for i, enemy in enumerate(data):
            if not isinstance(enemy, dict):
                issues.append(
                    ValidationIssue(
                        timestamp=time.time(),
                        frame=frame,
                        channel="ENEMIES",
                        severity=IssueSeverity.HIGH,
                        issue_type="INVALID_TYPE",
                        message=f"Enemy {i} is not a dict",
                    )
                )
                continue

            # Check required fields
            for field_name in ["id", "type", "pos"]:
                if field_name not in enemy:
                    issues.append(
                        ValidationIssue(
                            timestamp=time.time(),
                            frame=frame,
                            channel="ENEMIES",
                            severity=IssueSeverity.HIGH,
                            issue_type="MISSING_FIELD",
                            message=f"Enemy {i} missing: {field_name}",
                        )
                    )

            # Check HP consistency
            if "hp" in enemy and "max_hp" in enemy:
                if enemy["hp"] > enemy["max_hp"]:
                    issues.append(
                        ValidationIssue(
                            timestamp=time.time(),
                            frame=frame,
                            channel="ENEMIES",
                            severity=IssueSeverity.MEDIUM,
                            issue_type="HP_INCONSISTENCY",
                            message=f"Enemy {enemy.get('id', i)} hp={enemy['hp']} > max_hp={enemy['max_hp']}",
                        )
                    )

            # Check for duplicate IDs in same frame
            if "id" in enemy:
                entity_id = enemy["id"]
                if entity_id in entity_ids_seen:
                    issues.append(
                        ValidationIssue(
                            timestamp=time.time(),
                            frame=frame,
                            channel="ENEMIES",
                            severity=IssueSeverity.HIGH,
                            issue_type="DUPLICATE_ID",
                            message=f"Duplicate enemy ID {entity_id} in same frame",
                        )
                    )
                entity_ids_seen.add(entity_id)

                # Track entity lifecycle
                entity_key = ("enemy", entity_id)
                if entity_key not in self.entity_trackers:
                    self.entity_trackers[entity_key] = EntityTracker(
                        entity_id=entity_id, entity_type="enemy"
                    )

                pos = None
                if "pos" in enemy:
                    pos = (enemy["pos"].get("x"), enemy["pos"].get("y"))
                hp = enemy.get("hp")
                self.entity_trackers[entity_key].update(frame, pos, hp)
                self.entity_trackers[entity_key].check_suspicious()

        return issues

    def _validate_projectiles(self, data: Dict, frame: int) -> List[ValidationIssue]:
        issues = []

        if not isinstance(data, dict):
            issues.append(
                ValidationIssue(
                    timestamp=time.time(),
                    frame=frame,
                    channel="PROJECTILES",
                    severity=IssueSeverity.HIGH,
                    issue_type="INVALID_TYPE",
                    message=f"PROJECTILES data is not a dict: {type(data)}",
                )
            )
            return issues

        for sub_channel in ["enemy_projectiles", "player_tears", "lasers"]:
            if sub_channel not in data:
                continue

            projectiles = data[sub_channel]
            if not isinstance(projectiles, list):
                issues.append(
                    ValidationIssue(
                        timestamp=time.time(),
                        frame=frame,
                        channel="PROJECTILES",
                        severity=IssueSeverity.HIGH,
                        issue_type="INVALID_TYPE",
                        message=f"{sub_channel} is not a list: {type(projectiles)}",
                    )
                )
                continue

            for i, proj in enumerate(projectiles):
                if not isinstance(proj, dict):
                    issues.append(
                        ValidationIssue(
                            timestamp=time.time(),
                            frame=frame,
                            channel="PROJECTILES",
                            severity=IssueSeverity.HIGH,
                            issue_type="INVALID_TYPE",
                            message=f"{sub_channel}[{i}] is not a dict",
                        )
                    )
                    continue

                # Track projectile lifecycle
                if "id" in proj:
                    entity_key = ("projectile", proj["id"])
                    if entity_key not in self.entity_trackers:
                        self.entity_trackers[entity_key] = EntityTracker(
                            entity_id=proj["id"], entity_type="projectile"
                        )

                    pos = None
                    if "pos" in proj:
                        pos = (proj["pos"].get("x"), proj["pos"].get("y"))
                    self.entity_trackers[entity_key].update(frame, pos)

        return issues

    def _validate_room_info(self, data: Dict, frame: int) -> List[ValidationIssue]:
        issues = []
        schema = self.CHANNEL_SCHEMAS[DataChannel.ROOM_INFO]

        if not isinstance(data, dict):
            return issues

        # Check required fields
        for field_name in schema["required_fields"]:
            if field_name not in data:
                issues.append(
                    ValidationIssue(
                        timestamp=time.time(),
                        frame=frame,
                        channel="ROOM_INFO",
                        severity=IssueSeverity.HIGH,
                        issue_type="MISSING_FIELD",
                        message=f"ROOM_INFO missing: {field_name}",
                    )
                )

        # Check value ranges
        for field_name, (min_val, max_val) in schema.get("value_ranges", {}).items():
            if field_name in data:
                val = data[field_name]
                if val < min_val:
                    issues.append(
                        ValidationIssue(
                            timestamp=time.time(),
                            frame=frame,
                            channel="ROOM_INFO",
                            severity=IssueSeverity.MEDIUM,
                            issue_type="VALUE_OUT_OF_RANGE",
                            message=f"ROOM_INFO {field_name}={val} < {min_val}",
                        )
                    )
                if max_val is not None and val > max_val:
                    issues.append(
                        ValidationIssue(
                            timestamp=time.time(),
                            frame=frame,
                            channel="ROOM_INFO",
                            severity=IssueSeverity.MEDIUM,
                            issue_type="VALUE_OUT_OF_RANGE",
                            message=f"ROOM_INFO {field_name}={val} > {max_val}",
                        )
                    )

        return issues

    def _validate_room_layout(self, data: Dict, frame: int) -> List[ValidationIssue]:
        issues = []
        schema = self.CHANNEL_SCHEMAS[DataChannel.ROOM_LAYOUT]

        if not isinstance(data, dict):
            return issues

        # Check required fields
        for field_name in schema["required_fields"]:
            if field_name not in data:
                issues.append(
                    ValidationIssue(
                        timestamp=time.time(),
                        frame=frame,
                        channel="ROOM_LAYOUT",
                        severity=IssueSeverity.HIGH,
                        issue_type="MISSING_FIELD",
                        message=f"ROOM_LAYOUT missing: {field_name}",
                    )
                )

        # Validate grid types
        if "grid" in data:
            for grid_index, grid_data in data["grid"].items():
                if not isinstance(grid_data, dict):
                    continue

                grid_type = grid_data.get("type", -1)

                # Check for known problematic types
                if grid_type in schema.get("known_issues", {}):
                    issues.append(
                        ValidationIssue(
                            timestamp=time.time(),
                            frame=frame,
                            channel="ROOM_LAYOUT",
                            severity=IssueSeverity.INFO,
                            issue_type="KNOWN_ISSUE",
                            message=f"Grid {grid_index}: {schema['known_issues'][grid_type]}",
                            is_game_side=True,
                        )
                    )

                # Check valid range
                if grid_type not in schema.get("grid_types", []):
                    issues.append(
                        ValidationIssue(
                            timestamp=time.time(),
                            frame=frame,
                            channel="ROOM_LAYOUT",
                            severity=IssueSeverity.MEDIUM,
                            issue_type="INVALID_GRID_TYPE",
                            message=f"Grid {grid_index} has invalid type: {grid_type}",
                        )
                    )

        return issues

    def _validate_pickups(self, data: List, frame: int) -> List[ValidationIssue]:
        issues = []

        if not isinstance(data, list):
            return issues

        for i, pickup in enumerate(data):
            if not isinstance(pickup, dict):
                continue

            # Check required fields
            for field_name in ["id", "variant"]:
                if field_name not in pickup:
                    issues.append(
                        ValidationIssue(
                            timestamp=time.time(),
                            frame=frame,
                            channel="PICKUPS",
                            severity=IssueSeverity.MEDIUM,
                            issue_type="MISSING_FIELD",
                            message=f"Pickup {i} missing: {field_name}",
                        )
                    )

            # Track pickup lifecycle
            if "id" in pickup:
                entity_key = ("pickup", pickup["id"])
                if entity_key not in self.entity_trackers:
                    self.entity_trackers[entity_key] = EntityTracker(
                        entity_id=pickup["id"], entity_type="pickup"
                    )

                pos = None
                if "pos" in pickup:
                    pos = (pickup["pos"].get("x"), pickup["pos"].get("y"))
                self.entity_trackers[entity_key].update(frame, pos)

        return issues

    def _validate_fire_hazards(self, data: List, frame: int) -> List[ValidationIssue]:
        issues = []

        if not isinstance(data, list):
            return issues

        for i, fire in enumerate(data):
            if not isinstance(fire, dict):
                continue

            for field_name in ["id", "type"]:
                if field_name not in fire:
                    issues.append(
                        ValidationIssue(
                            timestamp=time.time(),
                            frame=frame,
                            channel="FIRE_HAZARDS",
                            severity=IssueSeverity.MEDIUM,
                            issue_type="MISSING_FIELD",
                            message=f"Fire {i} missing: {field_name}",
                        )
                    )

            # Track fire lifecycle
            if "id" in fire:
                entity_key = ("fire", fire["id"])
                if entity_key not in self.entity_trackers:
                    self.entity_trackers[entity_key] = EntityTracker(
                        entity_id=fire["id"], entity_type="fire"
                    )

                pos = None
                hp = fire.get("hp")
                if "pos" in fire:
                    pos = (fire["pos"].get("x"), fire["pos"].get("y"))
                self.entity_trackers[entity_key].update(frame, pos, hp)

        return issues

    def _validate_bombs(self, data: List, frame: int) -> List[ValidationIssue]:
        issues = []

        if not isinstance(data, list):
            return issues

        for i, bomb in enumerate(data):
            if not isinstance(bomb, dict):
                continue

            for field_name in ["id", "timer"]:
                if field_name not in bomb:
                    issues.append(
                        ValidationIssue(
                            timestamp=time.time(),
                            frame=frame,
                            channel="BOMBS",
                            severity=IssueSeverity.MEDIUM,
                            issue_type="MISSING_FIELD",
                            message=f"Bomb {i} missing: {field_name}",
                        )
                    )

            # Check timer value range
            if "timer" in bomb and bomb["timer"] < 0:
                issues.append(
                    ValidationIssue(
                        timestamp=time.time(),
                        frame=frame,
                        channel="BOMBS",
                        severity=IssueSeverity.HIGH,
                        issue_type="INVALID_VALUE",
                        message=f"Bomb {i} has negative timer: {bomb['timer']}",
                    )
                )

        return issues

    def check_entity_lifecycle(self, current_frame: int) -> List[ValidationIssue]:
        """
        Check for entity lifecycle anomalies.

        Args:
            current_frame: Current game frame

        Returns:
            List of issues found
        """
        issues = []
        expiration_threshold = 600  # 10 seconds at 60fps

        for entity_key, tracker in self.entity_trackers.items():
            if tracker.last_seen_frame == -1:
                continue

            # Check for stale entities
            frames_since_seen = current_frame - tracker.last_seen_frame
            if frames_since_seen > expiration_threshold:
                # Entity hasn't been seen for 10+ seconds
                # This is expected for dead entities, not an error
                pass

            # Check for suspicious patterns
            if tracker.is_suspicious:
                for reason in tracker.suspicion_reasons:
                    issues.append(
                        ValidationIssue(
                            timestamp=time.time(),
                            frame=current_frame,
                            channel="*",
                            severity=IssueSeverity.MEDIUM,
                            issue_type="SUSPICIOUS_PATTERN",
                            message=f"Entity {tracker.entity_type}[{tracker.entity_id}]: {reason}",
                        )
                    )

        return issues

    def generate_report(self) -> Dict:
        """Generate a comprehensive validation report"""
        uptime = time.time() - self.start_time

        report = {
            "summary": {
                "uptime_seconds": round(uptime, 2),
                "total_messages": self.total_messages,
                "total_validations": self.total_validations,
                "total_issues": self.total_issues,
                "issues_by_severity": {
                    s.name: len(self.issues_by_severity[s]) for s in IssueSeverity
                },
                "protocol_version": self.PROTOCOL_VERSION,
            },
            "channel_stats": {},
            "room_transitions": len(self.room_transitions),
            "entity_trackers": len(self.entity_trackers),
            "suspicious_entities": sum(
                1 for t in self.entity_trackers.values() if t.is_suspicious
            ),
            "known_game_issues": [],
            "recent_issues": [],
        }

        # Channel statistics
        for channel_name, stats in self.channel_stats.items():
            report["channel_stats"][channel_name] = {
                "messages": stats.message_count,
                "validations": stats.validation_count,
                "passed": stats.pass_count,
                "failed": stats.fail_count,
                "warnings": stats.warn_count,
                "first_frame": stats.first_frame,
                "last_frame": stats.last_frame,
                "avg_processing_ms": round(stats.avg_processing_time_ms, 3),
            }

        # Recent issues (last 10)
        for issue in self.issues[-10:]:
            report["recent_issues"].append(issue.to_dict())

        # Known game-side issues found
        game_issues = [i for i in self.issues if i.is_game_side]
        report["known_game_issues"] = [
            {"channel": i.channel, "type": i.issue_type, "message": i.message}
            for i in game_issues[:20]
        ]

        return report

    def print_summary(self):
        """Print a quick summary to console"""
        report = self.generate_report()

        print("\n" + "=" * 60)
        print("DATA VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Uptime: {report['summary']['uptime_seconds']:.1f}s")
        print(f"Messages: {report['summary']['total_messages']}")
        print(f"Validations: {report['summary']['total_validations']}")
        print(f"Total Issues: {report['summary']['total_issues']}")

        print("\nIssues by Severity:")
        for severity, count in report["summary"]["issues_by_severity"].items():
            if count > 0:
                print(f"  {severity}: {count}")

        print("\nChannel Statistics:")
        for channel, stats in report["channel_stats"].items():
            if stats["messages"] > 0:
                status = (
                    "✅"
                    if stats["failed"] == 0
                    else "⚠️"
                    if stats["failed"] < 5
                    else "❌"
                )
                print(
                    f"  {status} {channel}: {stats['messages']} msgs, {stats['failed']} failed"
                )

        print(f"\nRoom Transitions: {report['room_transitions']}")
        print(f"Entity Trackers: {report['entity_trackers']}")
        print(f"Suspicious Entities: {report['suspicious_entities']}")

        if report["known_game_issues"]:
            print(f"\nKnown Game-Side Issues Found: {len(report['known_game_issues'])}")

        print("=" * 60)

    def save_report(self, filepath: str = "validation_report.json"):
        """Save report to file"""
        report = self.generate_report()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"Report saved to {filepath}")

    def export_issues(self, filepath: str = "validation_issues.jsonl"):
        """Export all issues as JSONL"""
        with open(filepath, "w", encoding="utf-8") as f:
            for issue in self.issues:
                f.write(json.dumps(issue.to_dict(), ensure_ascii=False) + "\n")
        logger.info(f"Issues exported to {filepath}")


class ValidationTestHarness:
    """
    Test harness for running validation tests on recorded or live data.
    """

    def __init__(self):
        self.validator = DataValidator()
        self.test_results: Dict[str, Dict] = {}

    def test_recorded_data(self, filepath: str):
        """Test validation on recorded data file"""
        logger.info(f"Testing recorded data: {filepath}")

        with open(filepath, "r") as f:
            for line in f:
                try:
                    msg = json.loads(line)
                    self.validator.validate_message(msg)
                except json.JSONDecodeError:
                    continue

        self.validator.print_summary()
        return self.validator.generate_report()

    def test_live(self, host: str = "127.0.0.1", port: int = 9527):
        """Run validation on live game connection"""
        import socket

        logger.info(f"Connecting to {host}:{port} for live validation...")

        validator = DataValidator()

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((host, port))
                sock.settimeout(1.0)

                buffer = ""
                while True:
                    try:
                        data = sock.recv(4096).decode("utf-8")
                        if not data:
                            break

                        buffer += data
                        lines = buffer.split("\n")
                        buffer = lines[-1]

                        for line in lines[:-1]:
                            if line.strip():
                                msg = json.loads(line)
                                issues = validator.validate_message(msg)

                                if issues:
                                    for issue in issues[:3]:  # Limit output
                                        print(
                                            f"[{issue.severity.name}] {issue.message}"
                                        )

                    except socket.timeout:
                        validator.print_summary()
                    except KeyboardInterrupt:
                        break

        except ConnectionRefusedError:
            logger.error(f"Cannot connect to {host}:{port}")
        except Exception as e:
            logger.error(f"Error: {e}")

        validator.print_summary()
        return validator.generate_report()


def main():
    parser = argparse.ArgumentParser(
        description="SocketBridge Data Validation Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 data_validator.py --live              # Real-time validation
  python3 data_validator.py --replay FILE       # Validate recorded data
  python3 data_validator.py --report FILE       # Generate report from log
  python3 data_validator.py --test              # Run self-test
        """,
    )

    parser.add_argument("--live", action="store_true", help="Run live validation")
    parser.add_argument("--replay", metavar="FILE", help="Validate recorded data file")
    parser.add_argument(
        "--report", metavar="FILE", help="Generate report from validation log"
    )
    parser.add_argument("--test", action="store_true", help="Run self-test")
    parser.add_argument("--host", default="127.0.0.1", help="Game server host")
    parser.add_argument("--port", type=int, default=9527, help="Game server port")
    parser.add_argument(
        "--output", default="validation_report.json", help="Output file for report"
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.test:
        # Run self-test
        print("Running DataValidator self-test...")

        # Create test message
        test_msg = {
            "version": "2.0",
            "type": "DATA",
            "frame": 100,
            "room_index": 42,
            "channels": ["PLAYER_POSITION", "ENEMIES", "ROOM_INFO"],
            "payload": {
                "PLAYER_POSITION": {
                    "1": {
                        "pos": {"x": 100.0, "y": 200.0},
                        "vel": {"x": 0.0, "y": 0.0},
                        "move_dir": 0,
                        "fire_dir": 4,
                        "aim_dir": {"x": 1.0, "y": 0.0},
                    }
                },
                "ENEMIES": [
                    {
                        "id": 1,
                        "type": 10,
                        "pos": {"x": 300.0, "y": 200.0},
                        "hp": 10.0,
                        "max_hp": 10.0,
                    }
                ],
                "ROOM_INFO": {
                    "room_index": 42,
                    "stage": 2,
                    "grid_width": 13,
                    "grid_height": 7,
                },
            },
        }

        validator = DataValidator()
        issues = validator.validate_message(test_msg)

        print(f"Test message validated with {len(issues)} issues")
        for issue in issues:
            print(f"  - {issue.severity.name}: {issue.message}")

        validator.print_summary()

    elif args.live:
        harness = ValidationTestHarness()
        harness.test_live(args.host, args.port)

    elif args.replay:
        harness = ValidationTestHarness()
        report = harness.test_recorded_data(args.replay)
        print(f"\nValidation complete. Report saved to {args.output}")
        # Save report
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)

    elif args.report:
        # Load and display report
        with open(args.report, "r") as f:
            report = json.load(f)
        print(json.dumps(report, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
