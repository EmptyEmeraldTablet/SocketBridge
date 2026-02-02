from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Union
from enum import Enum
import math
import logging

logger = logging.getLogger("Models")


class EntityType(Enum):
    PLAYER = "player"
    ENEMY = "enemy"
    PROJECTILE = "projectile"
    LASER = "laser"
    PICKUP = "pickup"
    OBSTACLE = "obstacle"
    BUTTON = "button"
    BOMB = "bomb"
    INTERACTABLE = "interactable"
    FIRE_HAZARD = "fire_hazard"
    DESTRUCTIBLE = "destructible"


class ObjectState(Enum):
    ACTIVE = "active"
    DYING = "dying"
    DEAD = "dead"
    ESCAPED = "escaped"


@dataclass
class Vector2D:
    x: float = 0.0
    y: float = 0.0

    def __add__(self, other: "Vector2D") -> "Vector2D":
        return Vector2D(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector2D") -> "Vector2D":
        return Vector2D(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vector2D":
        return Vector2D(self.x * scalar, self.y * scalar)

    def __truediv__(self, scalar: float) -> "Vector2D":
        if scalar == 0:
            return Vector2D(0, 0)
        return Vector2D(self.x / scalar, self.y / scalar)

    def __neg__(self) -> "Vector2D":
        return Vector2D(-self.x, -self.y)

    def __eq__(self, other: "Vector2D") -> bool:
        return abs(self.x - other.x) < 0.001 and abs(self.y - other.y) < 0.001

    def __hash__(self) -> int:
        return hash((round(self.x, 3), round(self.y, 3)))

    def magnitude(self) -> float:
        return math.sqrt(self.x**2 + self.y**2)

    def normalized(self) -> "Vector2D":
        mag = self.magnitude()
        if mag == 0:
            return Vector2D(0, 0)
        return self / mag

    def dot(self, other: "Vector2D") -> float:
        return self.x * other.x + self.y * other.y

    def distance_to(self, other: "Vector2D") -> float:
        return (self - other).magnitude()

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def to_dict(self) -> Dict[str, float]:
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "Vector2D":
        return cls(x=data.get("x", 0), y=data.get("y", 0))

    @classmethod
    def from_tuple(cls, data: Tuple[float, float]) -> "Vector2D":
        return cls(x=data[0], y=data[1])

    @classmethod
    def from_player_dir(cls, direction: int) -> "Vector2D":
        directions = [
            (0, -1),
            (1, -1),
            (1, 0),
            (1, 1),
            (0, 1),
            (-1, 1),
            (-1, 0),
            (-1, -1),
        ]
        if 0 <= direction < len(directions):
            dx, dy = directions[direction]
            return cls(x=float(dx), y=float(dy))
        return cls(0, 0)

    @staticmethod
    def direction_to_vector(dx: int, dy: int) -> Tuple[int, int]:
        if dx == 0 and dy == -1:
            return 0
        elif dx == 1 and dy == -1:
            return 1
        elif dx == 1 and dy == 0:
            return 2
        elif dx == 1 and dy == 1:
            return 3
        elif dx == 0 and dy == 1:
            return 4
        elif dx == -1 and dy == 1:
            return 5
        elif dx == -1 and dy == 0:
            return 6
        elif dx == -1 and dy == -1:
            return 7
        return 0
