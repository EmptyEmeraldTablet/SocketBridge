"""
Validation rules and known-issue registry.

Registers known game-side data quirks so they can be:
- Detected and logged (not treated as errors)
- Counted for quality reports
- Optionally auto-corrected via normalizers
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Callable
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class IssueSeverity(str, Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationRule:
    """A known data validation rule."""
    id: str
    channel: str
    description: str
    severity: IssueSeverity = IssueSeverity.INFO
    # Detection: return True if the issue is present
    detect: Optional[Callable[[Any], bool]] = None
    # Correction: return corrected data (None = no correction available)
    correct: Optional[Callable[[Any], Any]] = None


class KnownIssueRegistry:
    """Registry of known game-side data issues."""

    _instance: Optional["KnownIssueRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._rules: dict[str, ValidationRule] = {}
        self._counts: dict[str, int] = defaultdict(int)
        self._total_checked: int = 0
        self._register_defaults()

    def _register_defaults(self):
        self.register(ValidationRule(
            id="ENEMY_NEGATIVE_HP", channel="ENEMIES",
            description="Enemy reports negative HP briefly when dying",
            severity=IssueSeverity.INFO,
        ))
        self.register(ValidationRule(
            id="PLAYER_AIM_ZERO", channel="PLAYER_POSITION",
            description="Player aim_dir is (0,0) when not aiming",
            severity=IssueSeverity.INFO,
        ))
        self.register(ValidationRule(
            id="GRID_FIREPLACE_DEPRECATED", channel="ROOM_LAYOUT",
            description="GRID_FIREPLACE (ID 13) is deprecated by game API",
            severity=IssueSeverity.INFO,
        ))
        self.register(ValidationRule(
            id="DOOR_IN_GRID", channel="ROOM_LAYOUT",
            description="GRID_DOOR (ID 16) may appear in grid data",
            severity=IssueSeverity.INFO,
        ))

    def register(self, rule: ValidationRule):
        self._rules[rule.id] = rule

    def check(self, channel: str, data: Any) -> Optional[ValidationRule]:
        """Check data against known issues. Returns matching rule or None."""
        self._total_checked += 1
        for rule in self._rules.values():
            if rule.channel != channel:
                continue
            if rule.detect and rule.detect(data):
                self._counts[rule.id] += 1
                return rule
        return None

    def get_stats(self) -> dict:
        return {
            "total_checked": self._total_checked,
            "by_issue": dict(self._counts),
            "total_issues": sum(self._counts.values()),
        }
