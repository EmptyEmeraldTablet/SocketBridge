"""Test sensor layer — parsing, validation, and SensorRegistry."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest

# Import sensors (triggers auto-registration)
import sensors.player
import sensors.entities
import sensors.room
import sensors.hazards
from sensors.base import SensorRegistry


class TestSensorRegistry(unittest.TestCase):
    def test_all_registered(self):
        names = SensorRegistry.all_names()
        self.assertIn("PLAYER_POSITION", names)
        self.assertIn("ENEMIES", names)
        self.assertIn("PROJECTILES", names)
        self.assertIn("ROOM_INFO", names)
        self.assertIn("ROOM_LAYOUT", names)
        self.assertIn("PICKUPS", names)
        self.assertIn("BOMBS", names)
        self.assertIn("FIRE_HAZARDS", names)
        self.assertIn("INTERACTABLES", names)
        self.assertIn("PLAYER_STATS", names)
        self.assertIn("PLAYER_HEALTH", names)
        self.assertIn("PLAYER_INVENTORY", names)
        self.assertEqual(len(names), 12)

    def test_entity_sensors(self):
        entity_names = list(SensorRegistry.get_entity_sensors().keys())
        self.assertIn("ENEMIES", entity_names)
        self.assertIn("PROJECTILES", entity_names)
        self.assertIn("PICKUPS", entity_names)
        self.assertIn("BOMBS", entity_names)

    def test_get_sensor(self):
        sensor = SensorRegistry.get("ENEMIES")
        self.assertIsNotNone(sensor)
        self.assertEqual(sensor.name, "ENEMIES")
        self.assertTrue(sensor.produces_entities)
        self.assertTrue(sensor.enabled)

    def test_process_player_position(self):
        sensor = SensorRegistry.get("PLAYER_POSITION")
        raw = [{"pos": {"x": 320, "y": 240}, "vel": {"x": 5, "y": -2},
                "move_dir": 3, "fire_dir": 2, "head_dir": 0,
                "aim_dir": {"x": 1, "y": 0}}]
        result = sensor.process(raw, frame=100)
        self.assertIsNotNone(result)
        self.assertIn(1, result)
        self.assertEqual(result[1].pos.x, 320.0)
        self.assertEqual(result[1].pos.y, 240.0)

    def test_process_enemies(self):
        sensor = SensorRegistry.get("ENEMIES")
        raw = [{"id": 10, "type": 18, "hp": 10.0, "max_hp": 10.0,
                "pos": {"x": 400, "y": 300}, "vel": {"x": 1, "y": 0},
                "distance": 150.0}]
        result = sensor.process(raw, frame=100)
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, 10)

    def test_process_room_info(self):
        sensor = SensorRegistry.get("ROOM_INFO")
        raw = {"room_type": 2, "room_shape": 1, "room_idx": 5, "stage": 2,
               "grid_width": 13, "grid_height": 7,
               "top_left": {"x": 0, "y": 0}, "bottom_right": {"x": 832, "y": 448},
               "enemy_count": 5, "has_boss": False, "is_clear": False}
        result = sensor.process(raw, frame=100)
        self.assertIsNotNone(result)
        self.assertEqual(result.grid_width, 13)
        self.assertFalse(result.is_clear)

    def test_process_message(self):
        payload = {
            "ENEMIES": [{"id": 1, "type": 18, "hp": 10.0, "max_hp": 10.0,
                         "pos": {"x": 400, "y": 300}, "vel": {"x": 0, "y": 0}}],
            "ROOM_INFO": {"room_type": 2, "room_shape": 1, "room_idx": 5, "stage": 2,
                          "grid_width": 13, "grid_height": 7,
                          "top_left": {"x": 0, "y": 0}, "bottom_right": {"x": 832, "y": 448},
                          "enemy_count": 1},
        }
        results = SensorRegistry.process_message(payload, frame=100)
        self.assertIn("ENEMIES", results)
        self.assertIn("ROOM_INFO", results)


if __name__ == "__main__":
    unittest.main()
