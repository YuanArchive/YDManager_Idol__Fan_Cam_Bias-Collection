import os
import unittest

from src.managers.player_engine import (
    PlayerEngine,
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


class PlayerSlotClearTest(unittest.TestCase):
    def test_clear_slot_releases_media_and_hides_item(self):
        slot = make_slot(path="C:/videos/a.mp4", state=SlotState.READY, generation=3, role=SlotRole.NEXT)

        slot.clear()

        self.assertEqual(slot.state, SlotState.EMPTY)
        self.assertEqual(slot.role, SlotRole.SPARE)
        self.assertIsNone(slot.expected_path)
        self.assertEqual(slot.expected_generation, 0)
        self.assertEqual(slot.player.stop_count, 1)
        self.assertEqual(slot.player.source_path, "")
        self.assertTrue(slot.audio.muted)
        self.assertEqual(slot.video_item.opacity, 0.0)
        self.assertEqual(slot.video_item.z, 0.0)

    def test_source_matches_path_uses_real_player_source_not_only_metadata(self):
        from src.managers.player_engine import source_matches_path

        slot = make_slot(path="C:/videos/a.mp4", state=SlotState.READY, generation=1)
        slot.expected_path = "C:/videos/b.mp4"

        self.assertFalse(source_matches_path(slot, "C:/videos/b.mp4"))
        self.assertTrue(source_matches_path(slot, "C:/videos/a.mp4"))


class FakeTimer:
    def __init__(self):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class FakePrivacy:
    def __init__(self, blocked=False):
        self.blocked = blocked

    def __call__(self):
        return self.blocked


def make_engine(slots, privacy_blocked=False):
    return PlayerEngine(
        slots=slots,
        fallback_timer=FakeTimer(),
        privacy_guard=FakePrivacy(privacy_blocked),
        autoplay_getter=lambda: True,
        audio_enabled_getter=lambda: True,
    )


class PlayerEngineActivationTest(unittest.TestCase):
    def test_ready_preload_promotes_without_setting_source_again(self):
        slot = make_slot(1, "C:/videos/next.mp4", SlotState.READY, 7, SlotRole.NEXT)
        engine = make_engine([make_slot(0, "C:/videos/current.mp4", SlotState.ACTIVE, 7, SlotRole.CURRENT), slot])

        result = engine.activate("C:/videos/next.mp4", start_pos=0, generation=7, autoplay=True)

        self.assertEqual(result.slot_id, 1)
        self.assertTrue(result.reused_source)
        self.assertFalse(result.waiting_for_media)
        self.assertEqual(slot.state, SlotState.ACTIVE)
        self.assertEqual(slot.role, SlotRole.CURRENT)
        self.assertEqual(len(slot.player.set_source_calls), 0)

    def test_preloading_hit_promotes_and_arms_fallback(self):
        slot = make_slot(1, "C:/videos/next.mp4", SlotState.PRELOADING, 7, SlotRole.NEXT)
        engine = make_engine([make_slot(0, "C:/videos/current.mp4", SlotState.ACTIVE, 7, SlotRole.CURRENT), slot])

        result = engine.activate("C:/videos/next.mp4", start_pos=0, generation=7, autoplay=True)

        self.assertEqual(result.slot_id, 1)
        self.assertTrue(result.reused_source)
        self.assertTrue(result.waiting_for_media)
        self.assertTrue(result.fallback_required)
        self.assertTrue(engine.fallback_timer.started)

    def test_new_activation_sets_source_and_arms_fallback(self):
        slot = make_slot(0)
        engine = make_engine([slot])

        result = engine.activate("C:/videos/a.mp4", start_pos=0, generation=2, autoplay=True)

        self.assertEqual(result.slot_id, 0)
        self.assertFalse(result.reused_source)
        self.assertTrue(result.waiting_for_media)
        self.assertEqual(slot.expected_path, os.path.normpath("C:/videos/a.mp4"))
        self.assertEqual(slot.expected_generation, 2)
        self.assertEqual(slot.state, SlotState.ACTIVE)
        self.assertTrue(engine.fallback_timer.started)


if __name__ == "__main__":
    unittest.main()
