"""Test new protocol schema — Pydantic model validation."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from protocol.schema import (
    Vector2D, PlayerPosition, PlayerStats, PlayerHealth, PlayerInventory,
    Enemy, Projectile, Laser, Projectiles, Pickup,
    RoomInfo, GridEntity, Door, RoomLayout,
    Bomb, FireHazard, Interactable,
    DataMessage, SubscribeRequest, SubscribeAck,
    ActiveItem,
)
from pydantic import ValidationError


class TestVector2D(unittest.TestCase):
    def test_defaults(self):
        v = Vector2D()
        self.assertEqual(v.x, 0.0); self.assertEqual(v.y, 0.0)

    def test_from_dict(self):
        v = Vector2D(x=1.5, y=-2.3)
        self.assertEqual(v.x, 1.5); self.assertEqual(v.y, -2.3)

    def test_coerce_int(self):
        v = Vector2D(x=1, y=2)
        self.assertIsInstance(v.x, float)

    def test_coerce_none(self):
        v = Vector2D(x=None, y=None)
        self.assertEqual(v.x, 0.0); self.assertEqual(v.y, 0.0)

    def test_distance(self):
        a = Vector2D(x=0, y=0); b = Vector2D(x=3, y=4)
        self.assertAlmostEqual(a.distance_to(b), 5.0)

    def test_magnitude(self):
        self.assertAlmostEqual(Vector2D(x=3, y=4).magnitude(), 5.0)

    def test_ops(self):
        a = Vector2D(x=10, y=20); b = a + Vector2D(x=1, y=2)
        self.assertEqual(b.x, 11.0); self.assertEqual(b.y, 22.0)


class TestPlayerPosition(unittest.TestCase):
    def test_valid(self):
        p = PlayerPosition(
            pos={"x": 100, "y": 200}, vel={"x": 1, "y": -1},
            move_dir=3, fire_dir=2, head_dir=0,
            aim_dir={"x": 1, "y": 0},
        )
        self.assertEqual(p.pos.x, 100.0)
        self.assertEqual(p.vel.y, -1.0)

    def test_aim_dir_zero_allowed(self):
        p = PlayerPosition(aim_dir={"x": 0, "y": 0})
        self.assertEqual(p.aim_dir.x, 0.0)

    def test_extra_fields(self):
        p = PlayerPosition(extra="ignored"); self.assertEqual(p.pos.x, 0.0)


class TestPlayerStats(unittest.TestCase):
    def test_valid(self):
        s = PlayerStats(player_type=0, damage=3.5, speed=1.0, luck=3)
        self.assertEqual(s.damage, 3.5); self.assertEqual(s.luck, 3)

    def test_luck_coerce(self):
        s = PlayerStats(player_type=0, damage=3.5, speed=1.0, luck="2.5")
        self.assertEqual(s.luck, 2)

    def test_defaults(self):
        s = PlayerStats(player_type=0, damage=3.5, speed=1.0)
        self.assertEqual(s.tears, 10.0)


class TestPlayerHealth(unittest.TestCase):
    def test_valid(self):
        h = PlayerHealth(red_hearts=6, max_hearts=6.0, soul_hearts=2, black_hearts=2)
        self.assertEqual(h.red_hearts, 6)


class TestPlayerInventory(unittest.TestCase):
    def test_inventory(self):
        inv = PlayerInventory(coins=15, bombs=3, keys=2,
                               collectibles={"1": 1, "245": 1},
                               active_items={"0": {"item": 33, "charge": 6, "max_charge": 12}})
        self.assertEqual(inv.coins, 15)
        self.assertEqual(inv.collectibles["1"], 1)
        self.assertEqual(inv.active_items["0"].item, 33)


class TestEnemy(unittest.TestCase):
    def test_valid(self):
        e = Enemy(id=10, type=18, hp=10.0, max_hp=10.0, distance=150.0,
                  pos={"x": 400, "y": 300}, vel={"x": 1, "y": 0})
        self.assertEqual(e.id, 10); self.assertEqual(e.hp, 10.0)

    def test_negative_hp_clamped(self):
        e = Enemy(id=1, type=18, hp=-5.0)
        self.assertEqual(e.hp, 0.0)

    def test_none_hp(self):
        e = Enemy(id=1, type=18, hp=None)
        self.assertEqual(e.hp, 0.0)


class TestProjectiles(unittest.TestCase):
    def test_container(self):
        p = Projectiles(
            enemy_projectiles=[{"id": 1, "pos": {"x": 100, "y": 200},
                                "vel": {"x": 3, "y": 0}}],
            player_tears=[],
            lasers=[],
        )
        self.assertEqual(len(p.enemy_projectiles), 1)
        self.assertEqual(p.enemy_projectiles[0].id, 1)


class TestRoomInfo(unittest.TestCase):
    def test_valid(self):
        r = RoomInfo(room_type=2, room_shape=1, room_idx=5, stage=2,
                     grid_width=13, grid_height=7,
                     top_left={"x": 0, "y": 0}, bottom_right={"x": 832, "y": 448},
                     enemy_count=5)
        self.assertEqual(r.grid_width, 13)
        self.assertFalse(r.is_clear)

    def test_grid_entity(self):
        g = GridEntity(type=2, variant=0, state=0, collision=1, x=64.0, y=64.0)
        self.assertEqual(g.type, 2)


class TestDataMessage(unittest.TestCase):
    def test_from_v21(self):
        msg = DataMessage.from_dict({
            "version": "2.1", "type": "DATA", "frame": 100, "room_index": 5,
            "seq": 50, "payload": {"ENEMIES": []}, "channels": ["ENEMIES"],
            "channel_meta": {
                "ENEMIES": {"collect_frame": 100, "collect_time": 12345,
                            "interval": "HIGH", "stale_frames": 0}
            }
        })
        self.assertEqual(msg.frame, 100); self.assertEqual(msg.seq, 50)
        self.assertIn("ENEMIES", msg.sensors)

    def test_from_v30(self):
        msg = DataMessage.from_dict({
            "version": "3.0", "type": "DATA", "frame": 200, "room_index": 3,
            "seq": 100, "payload": {}, "channels": [],
            "sensors": {"ENEMIES": {"collect_frame": 200, "entity_count": 3}}
        })
        self.assertEqual(msg.version, "3.0")
        self.assertEqual(msg.sensors["ENEMIES"].entity_count, 3)


class TestSubscribe(unittest.TestCase):
    def test_request(self):
        req = SubscribeRequest(sensors=["ENEMIES", "PLAYER_POSITION"])
        d = req.model_dump()
        self.assertEqual(d["type"], "SUBSCRIBE")
        self.assertEqual(len(d["sensors"]), 2)

    def test_ack(self):
        ack = SubscribeAck(accepted=["ENEMIES"], rejected=["FAKE"],
                            sensor_configs={"ENEMIES": {"throttle": {}}})
        self.assertIn("ENEMIES", ack.accepted)
        self.assertIn("FAKE", ack.rejected)


if __name__ == "__main__":
    unittest.main()
