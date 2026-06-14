import os
import unittest

from src.managers.player_engine import (
    PlaybackItem,
    PlayerEngine,
    PlayerSlot,
    SlotRole,
    SlotState,
    WatchSession,
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


def make_slot(slot_id=0, path=None, state=SlotState.EMPTY, generation=0, role=SlotRole.SPARE, mode="main"):
    slot = PlayerSlot(
        slot_id=slot_id,
        mode=mode,
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

    def test_clear_slot_updates_backing_entry_path(self):
        entry = {"path": "C:/videos/a.mp4"}
        slot = PlayerSlot(
            slot_id=0,
            mode="main",
            player=FakePlayer(),
            audio=FakeAudio(),
            video_item=FakeItem(),
            expected_path="C:/videos/a.mp4",
            entry=entry,
        )

        slot.clear()

        self.assertIsNone(entry["path"])


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

    def test_ready_preload_reveals_immediately_when_promoted(self):
        slot = make_slot(1, "C:/videos/next.mp4", SlotState.READY, 7, SlotRole.NEXT)
        engine = make_engine([make_slot(0, "C:/videos/current.mp4", SlotState.ACTIVE, 7, SlotRole.CURRENT), slot])

        engine.activate("C:/videos/next.mp4", start_pos=0, generation=7, autoplay=True)

        self.assertEqual(slot.video_item.opacity, 1.0)

    def test_activation_updates_backing_entry_and_active_callback(self):
        entry = {"path": None}
        slot = PlayerSlot(
            slot_id=3,
            mode="main",
            player=FakePlayer(),
            audio=FakeAudio(),
            video_item=FakeItem(),
            pool_index=2,
            entry=entry,
        )
        activated = []
        engine = PlayerEngine(
            slots=[slot],
            fallback_timer=FakeTimer(),
            privacy_guard=FakePrivacy(False),
            autoplay_getter=lambda: True,
            audio_enabled_getter=lambda: True,
            activate_slot_callback=lambda selected: activated.append((selected.mode, selected.pool_index)),
        )

        engine.activate("C:/videos/a.mp4", start_pos=0, generation=8, autoplay=True)

        self.assertEqual(entry["path"], os.path.normpath("C:/videos/a.mp4"))
        self.assertEqual(activated, [("main", 2)])

    def test_activate_records_watch_session_metadata(self):
        slot = make_slot(0)
        engine = make_engine([slot])

        result = engine.activate(
            "C:/videos/a.mp4",
            start_pos=1200,
            generation=4,
            autoplay=True,
            view_origin="main",
        )

        session = engine.active_session()
        self.assertIsInstance(session, WatchSession)
        self.assertEqual(session.path, os.path.normpath("C:/videos/a.mp4"))
        self.assertEqual(session.slot_id, result.slot_id)
        self.assertEqual(session.generation, 4)
        self.assertEqual(session.view_origin, "main")
        self.assertEqual(session.requested_start_pos, 1200)

    def test_clear_path_clears_active_watch_session(self):
        slot = make_slot(0)
        engine = make_engine([slot])
        engine.activate("C:/videos/a.mp4", start_pos=0, generation=1, autoplay=True, view_origin="main")

        cleared = engine.clear_path("C:/videos/a.mp4")

        self.assertTrue(cleared)
        self.assertIsNone(engine.active_session())
        self.assertIsNone(engine.active_player())

    def test_explicit_activation_in_new_mode_demotes_previous_active_slot(self):
        current_mode = {"value": "A"}
        main_slot = make_slot(0, "C:/videos/main.mp4", SlotState.ACTIVE, 1, SlotRole.CURRENT, mode="main")
        a_slot = make_slot(1, mode="A")
        engine = PlayerEngine(
            slots=[main_slot, a_slot],
            fallback_timer=FakeTimer(),
            privacy_guard=FakePrivacy(False),
            autoplay_getter=lambda: True,
            audio_enabled_getter=lambda: True,
            mode_getter=lambda: current_mode["value"],
        )
        engine.active_slot_id = main_slot.slot_id
        engine.watch_session = WatchSession(
            path=os.path.normpath("C:/videos/main.mp4"),
            slot_id=main_slot.slot_id,
            generation=1,
            view_origin="main",
            requested_start_pos=0,
        )

        engine.activate("C:/videos/a.mp4", start_pos=0, generation=2, autoplay=True, view_origin="A")

        self.assertEqual(main_slot.state, SlotState.READY)
        self.assertEqual(main_slot.role, SlotRole.SPARE)
        self.assertEqual(main_slot.video_item.opacity, 0.0)
        self.assertTrue(main_slot.audio.muted)
        self.assertEqual(main_slot.player.pause_count, 1)
        self.assertEqual(engine.active_slot_id, a_slot.slot_id)

    def test_activating_same_path_keeps_existing_active_slot_across_modes(self):
        current_mode = {"value": "A"}
        main_slot = make_slot(0, "C:/videos/shared.mp4", SlotState.ACTIVE, 1, SlotRole.CURRENT, mode="main")
        a_slot = make_slot(1, mode="A")
        engine = PlayerEngine(
            slots=[main_slot, a_slot],
            fallback_timer=FakeTimer(),
            privacy_guard=FakePrivacy(False),
            autoplay_getter=lambda: True,
            audio_enabled_getter=lambda: True,
            mode_getter=lambda: current_mode["value"],
        )
        engine.active_slot_id = main_slot.slot_id

        result = engine.activate("C:/videos/shared.mp4", start_pos=3000, generation=2, autoplay=True, view_origin="A")

        self.assertEqual(result.slot_id, main_slot.slot_id)
        self.assertTrue(result.reused_source)
        self.assertEqual(len(a_slot.player.set_source_calls), 0)
        self.assertEqual(engine.active_session().slot_id, main_slot.slot_id)

    def test_activation_uses_only_current_mode_slots(self):
        trash_slot = PlayerSlot(
            slot_id=0,
            mode="trash",
            player=FakePlayer(),
            audio=FakeAudio(),
            video_item=FakeItem(),
            pool_index=0,
        )
        main_slot = PlayerSlot(
            slot_id=1,
            mode="main",
            player=FakePlayer(),
            audio=FakeAudio(),
            video_item=FakeItem(),
            pool_index=0,
        )
        engine = PlayerEngine(
            slots=[trash_slot, main_slot],
            fallback_timer=FakeTimer(),
            privacy_guard=FakePrivacy(False),
            autoplay_getter=lambda: True,
            audio_enabled_getter=lambda: True,
            mode_getter=lambda: "main",
        )

        result = engine.activate("C:/videos/a.mp4", start_pos=0, generation=1, autoplay=True)

        self.assertEqual(result.slot_id, 1)
        self.assertEqual(trash_slot.state, SlotState.EMPTY)

    def test_same_source_active_slot_reuses_source_across_generation(self):
        active = make_slot(0, "C:/videos/a.mp4", SlotState.ACTIVE, 4, SlotRole.CURRENT)
        engine = make_engine([active])

        result = engine.activate("C:/videos/a.mp4", start_pos=3000, generation=5, autoplay=True)

        self.assertTrue(result.reused_source)
        self.assertEqual(active.expected_generation, 5)
        self.assertEqual(active.player.set_source_calls, [])

    def test_activate_repairs_expected_path_when_reusing_slot_by_matching_source(self):
        slot = make_slot(0, "C:/videos/stale-name.mp4", SlotState.READY, 4, SlotRole.NEXT)
        slot.player.source_path = os.path.normpath("C:/videos/a.mp4")
        engine = make_engine([slot])

        result = engine.activate("C:/videos/a.mp4", start_pos=0, generation=4, autoplay=True)

        self.assertTrue(result.reused_source)
        self.assertEqual(slot.expected_path, os.path.normpath("C:/videos/a.mp4"))
        self.assertEqual(slot.expected_generation, 4)

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


class PlayerEnginePreloadPlanTest(unittest.TestCase):
    def test_plan_neighbors_keeps_next_and_previous_slots(self):
        active = make_slot(0, "C:/videos/b.mp4", SlotState.ACTIVE, 4, SlotRole.CURRENT)
        next_slot = make_slot(1)
        prev_slot = make_slot(2)
        engine = make_engine([active, next_slot, prev_slot])
        playlist = [
            PlaybackItem("C:/videos/a.mp4"),
            PlaybackItem("C:/videos/b.mp4"),
            PlaybackItem("C:/videos/c.mp4"),
        ]

        engine.plan_neighbors(current_index=1, playlist=playlist, generation=4)

        self.assertEqual(next_slot.state, SlotState.PRELOADING)
        self.assertEqual(next_slot.role, SlotRole.NEXT)
        self.assertEqual(next_slot.expected_path, os.path.normpath("C:/videos/c.mp4"))
        self.assertEqual(prev_slot.state, SlotState.PRELOADING)
        self.assertEqual(prev_slot.role, SlotRole.PREVIOUS)
        self.assertEqual(prev_slot.expected_path, os.path.normpath("C:/videos/a.mp4"))

    def test_plan_neighbors_does_not_clear_ready_neighbor(self):
        active = make_slot(0, "C:/videos/b.mp4", SlotState.ACTIVE, 4, SlotRole.CURRENT)
        ready_next = make_slot(1, "C:/videos/c.mp4", SlotState.READY, 4, SlotRole.NEXT)
        spare = make_slot(2)
        engine = make_engine([active, ready_next, spare])
        playlist = [
            PlaybackItem("C:/videos/a.mp4"),
            PlaybackItem("C:/videos/b.mp4"),
            PlaybackItem("C:/videos/c.mp4"),
        ]

        engine.plan_neighbors(current_index=1, playlist=playlist, generation=4)

        self.assertEqual(ready_next.state, SlotState.READY)
        self.assertEqual(ready_next.role, SlotRole.NEXT)
        self.assertEqual(ready_next.player.stop_count, 0)

    def test_plan_neighbors_clears_ready_neighbor_when_real_source_is_stale(self):
        active = make_slot(0, "C:/videos/b.mp4", SlotState.ACTIVE, 4, SlotRole.CURRENT)
        stale_next = make_slot(1, "C:/videos/c.mp4", SlotState.READY, 4, SlotRole.NEXT)
        replacement = make_slot(2)
        stale_next.player.source_path = os.path.normpath("C:/videos/other.mp4")
        engine = make_engine([active, stale_next, replacement])
        playlist = [
            PlaybackItem("C:/videos/a.mp4"),
            PlaybackItem("C:/videos/b.mp4"),
            PlaybackItem("C:/videos/c.mp4"),
        ]

        engine.plan_neighbors(current_index=1, playlist=playlist, generation=4)

        self.assertEqual(stale_next.player.stop_count, 1)
        self.assertEqual(stale_next.state, SlotState.PRELOADING)
        self.assertEqual(stale_next.role, SlotRole.NEXT)
        self.assertEqual(stale_next.expected_path, os.path.normpath("C:/videos/c.mp4"))
        self.assertEqual(replacement.state, SlotState.PRELOADING)
        self.assertEqual(replacement.role, SlotRole.PREVIOUS)
        self.assertEqual(replacement.expected_path, os.path.normpath("C:/videos/a.mp4"))

    def test_plan_neighbors_does_not_steal_next_slot_when_only_one_spare_exists(self):
        active = make_slot(0, "C:/videos/b.mp4", SlotState.ACTIVE, 4, SlotRole.CURRENT)
        spare = make_slot(1)
        engine = make_engine([active, spare])
        playlist = [
            PlaybackItem("C:/videos/a.mp4"),
            PlaybackItem("C:/videos/b.mp4"),
            PlaybackItem("C:/videos/c.mp4"),
        ]

        engine.plan_neighbors(current_index=1, playlist=playlist, generation=4)

        self.assertEqual(spare.state, SlotState.PRELOADING)
        self.assertEqual(spare.role, SlotRole.NEXT)
        self.assertEqual(spare.expected_path, os.path.normpath("C:/videos/c.mp4"))

    def test_directional_forward_plan_prefers_next_two_items(self):
        active = make_slot(0, "C:/videos/c.mp4", SlotState.ACTIVE, 5, SlotRole.CURRENT)
        first = make_slot(1)
        second = make_slot(2)
        engine = make_engine([active, first, second])
        playlist = [
            PlaybackItem("C:/videos/a.mp4"),
            PlaybackItem("C:/videos/b.mp4"),
            PlaybackItem("C:/videos/c.mp4"),
            PlaybackItem("C:/videos/d.mp4"),
            PlaybackItem("C:/videos/e.mp4"),
        ]

        engine.plan_neighbors(current_index=2, playlist=playlist, generation=5, preferred_direction=1)

        self.assertEqual(first.state, SlotState.PRELOADING)
        self.assertEqual(first.role, SlotRole.NEXT)
        self.assertEqual(first.expected_path, os.path.normpath("C:/videos/d.mp4"))
        self.assertEqual(second.state, SlotState.PRELOADING)
        self.assertEqual(second.role, SlotRole.FORWARD_LOOKAHEAD)
        self.assertEqual(second.expected_path, os.path.normpath("C:/videos/e.mp4"))

    def test_directional_backward_plan_prefers_previous_two_items(self):
        active = make_slot(0, "C:/videos/c.mp4", SlotState.ACTIVE, 5, SlotRole.CURRENT)
        first = make_slot(1)
        second = make_slot(2)
        engine = make_engine([active, first, second])
        playlist = [
            PlaybackItem("C:/videos/a.mp4"),
            PlaybackItem("C:/videos/b.mp4"),
            PlaybackItem("C:/videos/c.mp4"),
            PlaybackItem("C:/videos/d.mp4"),
            PlaybackItem("C:/videos/e.mp4"),
        ]

        engine.plan_neighbors(current_index=2, playlist=playlist, generation=5, preferred_direction=-1)

        self.assertEqual(first.state, SlotState.PRELOADING)
        self.assertEqual(first.role, SlotRole.PREVIOUS)
        self.assertEqual(first.expected_path, os.path.normpath("C:/videos/b.mp4"))
        self.assertEqual(second.state, SlotState.PRELOADING)
        self.assertEqual(second.role, SlotRole.BACKWARD_LOOKAHEAD)
        self.assertEqual(second.expected_path, os.path.normpath("C:/videos/a.mp4"))

    def test_plan_neighbors_replaces_obsolete_ready_slot_in_same_pass(self):
        active = make_slot(0, "C:/videos/b.mp4", SlotState.ACTIVE, 7, SlotRole.CURRENT)
        obsolete_ready = make_slot(1, "C:/videos/old.mp4", SlotState.READY, 7, SlotRole.PREVIOUS)
        next_slot = make_slot(2)
        engine = make_engine([active, obsolete_ready, next_slot])
        playlist = [
            PlaybackItem("C:/videos/a.mp4"),
            PlaybackItem("C:/videos/b.mp4"),
            PlaybackItem("C:/videos/c.mp4"),
        ]

        engine.plan_neighbors(current_index=1, playlist=playlist, generation=7)

        self.assertEqual(next_slot.state, SlotState.PRELOADING)
        self.assertEqual(next_slot.role, SlotRole.NEXT)
        self.assertEqual(next_slot.expected_path, os.path.normpath("C:/videos/c.mp4"))
        self.assertEqual(obsolete_ready.state, SlotState.PRELOADING)
        self.assertEqual(obsolete_ready.role, SlotRole.PREVIOUS)
        self.assertEqual(obsolete_ready.expected_path, os.path.normpath("C:/videos/a.mp4"))

    def test_plan_neighbors_retains_same_source_ready_neighbor_across_generation_change(self):
        active = make_slot(0, "C:/videos/b.mp4", SlotState.ACTIVE, 8, SlotRole.CURRENT)
        ready_next = make_slot(1, "C:/videos/c.mp4", SlotState.READY, 7, SlotRole.NEXT)
        spare = make_slot(2)
        engine = make_engine([active, ready_next, spare])
        playlist = [
            PlaybackItem("C:/videos/a.mp4"),
            PlaybackItem("C:/videos/b.mp4"),
            PlaybackItem("C:/videos/c.mp4"),
        ]

        engine.plan_neighbors(current_index=1, playlist=playlist, generation=8)

        self.assertEqual(ready_next.state, SlotState.READY)
        self.assertEqual(ready_next.role, SlotRole.NEXT)
        self.assertEqual(ready_next.expected_generation, 8)
        self.assertEqual(ready_next.player.stop_count, 0)


class MediaStatus:
    LoadedMedia = "loaded"
    BufferedMedia = "buffered"
    LoadingMedia = "loading"
    InvalidMedia = "invalid"
    NoMedia = "none"
    EndOfMedia = "end"


class PlayerEngineStatusTest(unittest.TestCase):
    def test_ready_preload_survives_active_loaded_status(self):
        active = make_slot(0, "C:/videos/a.mp4", SlotState.ACTIVE, 3, SlotRole.CURRENT)
        ready_next = make_slot(1, "C:/videos/b.mp4", SlotState.READY, 3, SlotRole.NEXT)
        engine = make_engine([active, ready_next])

        engine.handle_media_status(active.player, MediaStatus.LoadedMedia)

        self.assertEqual(ready_next.state, SlotState.READY)
        self.assertEqual(ready_next.player.stop_count, 0)

    def test_loaded_status_does_not_mark_mismatched_preload_ready(self):
        preload = make_slot(0, "C:/videos/a.mp4", SlotState.PRELOADING, 3, SlotRole.NEXT)
        preload.player.source_path = os.path.normpath("C:/videos/other.mp4")
        engine = make_engine([preload])
        engine.current_generation = 3

        handled = engine.handle_media_status(preload.player, MediaStatus.LoadedMedia)

        self.assertFalse(handled)
        self.assertEqual(preload.state, SlotState.PRELOADING)

    def test_reveal_requires_active_generation_source_and_privacy_clear(self):
        active = make_slot(0, "C:/videos/a.mp4", SlotState.ACTIVE, 3, SlotRole.CURRENT)
        engine = make_engine([active], privacy_blocked=True)
        engine.current_generation = 3

        revealed = engine.reveal_if_allowed(active, MediaStatus.LoadedMedia)

        self.assertFalse(revealed)
        self.assertEqual(active.video_item.opacity, 0.0)

    def test_invalid_media_marks_slot_failed_and_clears_reuse_metadata(self):
        active = make_slot(0, "C:/videos/broken.mp4", SlotState.ACTIVE, 3, SlotRole.CURRENT)
        engine = make_engine([active])
        engine.current_generation = 3

        engine.handle_media_status(active.player, MediaStatus.InvalidMedia)

        self.assertEqual(active.state, SlotState.FAILED)
        self.assertIsNone(active.expected_path)
        self.assertEqual(active.video_item.opacity, 0.0)
        self.assertTrue(active.audio.muted)

    def test_no_media_status_does_not_mark_active_slot_failed(self):
        active = make_slot(0, "C:/videos/a.mp4", SlotState.ACTIVE, 3, SlotRole.CURRENT)
        engine = make_engine([active])
        engine.current_generation = 3

        revealed = engine.handle_media_status(active.player, MediaStatus.NoMedia)

        self.assertFalse(revealed)
        self.assertEqual(active.state, SlotState.ACTIVE)
        self.assertEqual(os.path.normpath(active.expected_path), os.path.normpath("C:/videos/a.mp4"))

    def test_media_error_marks_active_slot_failed(self):
        active = make_slot(0, "C:/videos/broken.mp4", SlotState.ACTIVE, 3, SlotRole.CURRENT)
        engine = make_engine([active])
        engine.current_generation = 3

        handled = engine.handle_media_error(active.player, "ResourceError")

        self.assertTrue(handled)
        self.assertEqual(active.state, SlotState.FAILED)
        self.assertIsNone(active.expected_path)
        self.assertEqual(active.last_error, "resourceerror")

    def test_loaded_active_reveals_screen_and_stops_fallback_timer(self):
        active = make_slot(0, "C:/videos/a.mp4", SlotState.ACTIVE, 3, SlotRole.CURRENT)
        engine = make_engine([active])
        engine.current_generation = 3
        engine.fallback_timer.start()

        revealed = engine.handle_media_status(active.player, MediaStatus.LoadedMedia)

        self.assertTrue(revealed)
        self.assertEqual(active.video_item.opacity, 1.0)
        self.assertTrue(engine.fallback_timer.stopped)

    def test_clear_all_stops_fallback_timer_and_clears_active_id(self):
        active = make_slot(0, "C:/videos/a.mp4", SlotState.ACTIVE, 3, SlotRole.CURRENT)
        engine = make_engine([active])
        engine.active_slot_id = 0
        engine.fallback_timer.start()

        engine.clear_all()

        self.assertTrue(engine.fallback_timer.stopped)
        self.assertIsNone(engine.active_slot_id)
        self.assertEqual(active.state, SlotState.EMPTY)


if __name__ == "__main__":
    unittest.main()
