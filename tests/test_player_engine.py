import os
import unittest

from src.managers.player_engine import (
    PlayerSlot,
    SlotRole,
    SlotState,
)


class FakeSource:
    def __init__(self, path=""):
        self.path = path

    def toLocalFile(self):
        return self.path


class FakePlayer:
    def __init__(self):
        self.source_path = ""
        self.set_source_calls = []
        self.stop_count = 0
        self.play_count = 0
        self.pause_count = 0
        self.position = 0
        self.rate = 1.0
        self.status = None
        self.blocked = False

    def source(self):
        return FakeSource(self.source_path)

    def setSource(self, source):
        self.set_source_calls.append(source)
        if hasattr(source, "toLocalFile"):
            self.source_path = source.toLocalFile()
        else:
            self.source_path = ""

    def stop(self):
        self.stop_count += 1

    def play(self):
        self.play_count += 1

    def pause(self):
        self.pause_count += 1

    def setPosition(self, position):
        self.position = position

    def setPlaybackRate(self, rate):
        self.rate = rate

    def mediaStatus(self):
        return self.status

    def blockSignals(self, blocked):
        self.blocked = blocked


class FakeAudio:
    def __init__(self):
        self.muted = False

    def setMuted(self, muted):
        self.muted = muted


class FakeItem:
    def __init__(self):
        self.opacity = 0.0
        self.z = 0.0

    def setOpacity(self, opacity):
        self.opacity = opacity

    def setZValue(self, z):
        self.z = z


def make_slot(slot_id=0, path=None, state=SlotState.EMPTY, generation=0, role=SlotRole.SPARE):
    slot = PlayerSlot(
        slot_id=slot_id,
        mode="main",
        player=FakePlayer(),
        audio=FakeAudio(),
        video_item=FakeItem(),
    )
    slot.expected_path = path
    slot.expected_generation = generation
    slot.state = state
    slot.role = role
    if path:
        slot.player.source_path = os.path.normpath(path)
    return slot


class PlayerSlotStateTest(unittest.TestCase):
    def test_new_slot_defaults_to_empty_spare(self):
        slot = make_slot()

        self.assertEqual(slot.state, SlotState.EMPTY)
        self.assertEqual(slot.role, SlotRole.SPARE)
        self.assertIsNone(slot.expected_path)
        self.assertEqual(slot.expected_generation, 0)
        self.assertIsNone(slot.last_error)
        self.assertIsNone(slot.last_status)


if __name__ == "__main__":
    unittest.main()
