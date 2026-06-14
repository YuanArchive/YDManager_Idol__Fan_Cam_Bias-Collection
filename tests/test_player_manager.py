import os
import unittest

from src.managers.player_manager import PlayerManager


class FakePlayer:
    def __init__(self):
        self.stopped = False
        self.source = "loaded"

    def stop(self):
        self.stopped = True

    def setSource(self, source):
        self.source = source

    def blockSignals(self, blocked):
        self.blocked = blocked


class FakeAudio:
    def __init__(self):
        self.muted = False

    def setMuted(self, muted):
        self.muted = muted


class FakeItem:
    def __init__(self):
        self.opacity = 1.0
        self.z = 10.0

    def setOpacity(self, opacity):
        self.opacity = opacity

    def setZValue(self, z):
        self.z = z


def make_entry(path=None):
    return {
        "player": FakePlayer(),
        "audio": FakeAudio(),
        "item": FakeItem(),
        "path": path,
    }


def make_manager():
    manager = PlayerManager.__new__(PlayerManager)
    manager.modes = ["main", "highlight", "trash", "A", "B"]
    manager.current_mode = "main"
    manager.pools = {
        "main": [make_entry("C:/videos/active.mp4"), make_entry(), make_entry()],
        "highlight": [make_entry()],
        "trash": [make_entry()],
        "A": [make_entry()],
        "B": [make_entry()],
    }
    manager.active_indices = {mode: 0 for mode in manager.modes}
    return manager


class PlayerManagerTest(unittest.TestCase):
    def test_prepare_player_reuses_existing_loaded_path(self):
        manager = make_manager()
        target = os.path.normpath("C:/videos/target.mp4")
        manager.pools["main"][2]["path"] = target

        selected = manager.prepare_player_for_path(os.path.join("C:/videos", ".", "target.mp4"))

        self.assertIs(selected, manager.pools["main"][2])
        self.assertEqual(manager.active_indices["main"], 2)

    def test_prepare_player_chooses_idle_player_for_new_path(self):
        manager = make_manager()
        manager.active_indices["main"] = 0

        selected = manager.prepare_player_for_path("C:/videos/new.mp4")

        self.assertIs(selected, manager.pools["main"][1])
        self.assertEqual(manager.active_indices["main"], 1)

    def test_switch_mode_rejects_unknown_mode_without_releasing_current_pool(self):
        manager = make_manager()

        with self.assertRaises(ValueError):
            manager.switch_mode("missing")

        self.assertEqual(manager.current_mode, "main")
        self.assertFalse(manager.pools["main"][0]["player"].stopped)

    def test_set_active_index_rejects_out_of_range_index(self):
        manager = make_manager()

        with self.assertRaises(IndexError):
            manager.set_active_index(99)

        self.assertEqual(manager.active_indices["main"], 0)

    def test_stop_and_release_path_hides_video_item_and_mutes_audio(self):
        manager = make_manager()
        target = os.path.normpath("C:/videos/delete.mp4")
        entry = manager.pools["main"][1]
        entry["path"] = target

        released = manager.stop_and_release_path(os.path.join("C:/videos", ".", "delete.mp4"))

        self.assertTrue(released)
        self.assertTrue(entry["player"].stopped)
        self.assertIsNone(entry["path"])
        self.assertEqual(entry["item"].opacity, 0.0)
        self.assertEqual(entry["item"].z, 0.0)
        self.assertTrue(entry["audio"].muted)

    def test_engine_slots_preserve_mode_pool_index_and_backing_entry(self):
        manager = make_manager()

        slots = manager.engine_slots()

        main_slots = [slot for slot in slots if slot.mode == "main"]
        self.assertEqual([slot.pool_index for slot in main_slots], [0, 1, 2])
        self.assertIs(main_slots[0].entry, manager.pools["main"][0])
        self.assertEqual(main_slots[0].expected_path, os.path.normpath("C:/videos/active.mp4"))


if __name__ == "__main__":
    unittest.main()
