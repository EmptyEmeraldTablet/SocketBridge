"""Test entity state management — EntityStateManager and GameEntityStore."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from entities.tracker import EntityStateManager, GameEntityStore, EntityStateConfig
from protocol.schema import Enemy, Projectile, Laser, Pickup, Bomb, GridEntity


class TestEntityStateManager(unittest.TestCase):
    def setUp(self):
        self.mgr = EntityStateManager[Enemy](
            "test", EntityStateConfig(expiry_frames=3),
            id_getter=lambda e: e.id,
        )

    def _enemy(self, eid, hp=10.0, max_hp=10.0):
        return Enemy(id=eid, type=18, hp=hp, max_hp=max_hp,
                     pos={"x": 0, "y": 0}, vel={"x": 0, "y": 0})

    def test_add_entity(self):
        changes = self.mgr.update([self._enemy(1)], frame=100)
        self.assertEqual(changes.added, [1])
        self.assertEqual(changes.updated, [])
        self.assertEqual(self.mgr.count, 1)

    def test_update_entity(self):
        self.mgr.update([self._enemy(1)], frame=100)
        changes = self.mgr.update([self._enemy(1, hp=8.0)], frame=101)
        self.assertEqual(changes.updated, [1])
        self.assertEqual(changes.added, [])
        self.assertEqual(self.mgr.get(1).hp, 8.0)

    def test_expire_entity(self):
        self.mgr.update([self._enemy(1)], frame=100)
        # Push frame past expiry
        self.mgr.update([], frame=104)
        self.assertEqual(self.mgr.count, 0)

    def test_no_expire_disabled(self):
        mgr = EntityStateManager[Bomb](
            "static", EntityStateConfig(expiry_frames=-1),
            id_getter=lambda e: e.id,
        )
        mgr.update([Bomb(id=1, type=0, pos={"x":0,"y":0}, vel={"x":0,"y":0})], 100)
        mgr.update([], 200)
        self.assertEqual(mgr.count, 1)

    def test_get_fresh(self):
        self.mgr.update([self._enemy(1), self._enemy(2)], frame=100)
        self.mgr.update([self._enemy(2)], frame=101)
        # Enemy 2 was at frame 101 (stale=0), Enemy 1 was at frame 100 (stale=1)
        # max_stale=0 means only entities seen THIS frame
        fresh = self.mgr.get_fresh(0)
        self.assertEqual(len(fresh), 1)
        self.assertEqual(fresh[0].id, 2)

    def test_get_active(self):
        self.mgr.update([self._enemy(1), self._enemy(2)], frame=100)
        active = self.mgr.get_active(5)
        self.assertEqual(len(active), 2)

    def test_clear(self):
        self.mgr.update([self._enemy(1), self._enemy(2)], frame=100)
        self.mgr.clear()
        self.assertEqual(self.mgr.count, 0)

    def test_remove(self):
        self.mgr.update([self._enemy(1)], frame=100)
        self.assertTrue(self.mgr.remove(1))
        self.assertEqual(self.mgr.count, 0)
        self.assertFalse(self.mgr.remove(99))

    def test_is_active(self):
        self.mgr.update([self._enemy(1)], frame=100)
        self.assertTrue(self.mgr.is_active(1))
        self.mgr.update([], frame=105)
        self.assertFalse(self.mgr.is_active(1))

    def test_get_stats(self):
        self.mgr.update([self._enemy(1), self._enemy(2)], frame=100)
        stats = self.mgr.get_stats()
        self.assertEqual(stats["current_count"], 2)


class TestGameEntityStore(unittest.TestCase):
    def setUp(self):
        self.store = GameEntityStore()

    def test_update_enemies(self):
        raw = [{"id": 1, "type": 18, "hp": 10.0, "max_hp": 10.0,
                "pos": {"x": 100, "y": 200}, "vel": {"x": 0, "y": 0}}]
        changes = self.store.update_enemies(raw, frame=100)
        self.assertIn(1, changes.added)
        self.assertEqual(self.store.get_threat_count(), 1)

    def test_update_projectiles(self):
        results = self.store.update_projectiles(
            [{"id": 5, "pos": {"x": 300, "y": 400}, "vel": {"x": 1, "y": 0}}],
            [], [], frame=100,
        )
        self.assertIn(5, results["enemy_projectiles"].added)

    def test_room_change_clears(self):
        self.store.update_enemies(
            [{"id": 1, "type": 18, "hp": 10.0, "max_hp": 10.0,
              "pos": {"x": 0, "y": 0}, "vel": {"x": 0, "y": 0}}], frame=100,
        )
        self.store.on_room_change(5)
        self.assertEqual(self.store.enemies.count, 0)
        self.assertEqual(self.store.get_threat_count(), 0)

    def test_stats(self):
        self.store.update_enemies(
            [{"id": 1, "type": 18, "hp": 10.0, "max_hp": 10.0,
              "pos": {"x": 0, "y": 0}, "vel": {"x": 0, "y": 0}}], frame=100,
        )
        stats = self.store.get_stats()
        self.assertEqual(stats["current_frame"], 100)
        self.assertEqual(stats["enemies"]["current_count"], 1)


if __name__ == "__main__":
    unittest.main()
