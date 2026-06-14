import os
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtMultimedia import QMediaPlayer

from main import VideoSorter
from src.managers.player_engine import SlotState


class FakeTimer:
    def __init__(self):
        self.started = False
        self.stopped = False
        self.started_with = None

    def start(self, interval=None):
        self.started = True
        self.started_with = interval

    def stop(self):
        self.stopped = True


class FakeFileManager:
    def __init__(self):
        self.search_keyword = "previous"
        self.scanned_folder = None
        self.current_mode = "main"
        self.cache_loaded = False
        self.main_files = []

    def set_search_keyword(self, text):
        self.search_keyword = text

    def scan_folder(self, folder):
        self.scanned_folder = folder

    def load_main_files_from_cache(self, folder):
        self.cache_load_folder = folder
        return self.cache_loaded

    def load_trash(self):
        self.trash_loaded = True

    def get_highlight_display_list(self):
        self.highlights_loaded = True


class FakeSource:
    def toLocalFile(self):
        return ""


class FakePlayer:
    def source(self):
        return FakeSource()

    def playbackState(self):
        return QMediaPlayer.PlaybackState.PausedState


class FakeFileList:
    def __init__(self):
        self.updates_enabled = True
        self.cleared = False

    def count(self):
        return 0

    def setUpdatesEnabled(self, enabled):
        self.updates_enabled = enabled

    def clear(self):
        self.cleared = True


class FakeListItem:
    def __init__(self, path, start_pos=None):
        self.path = path
        self.start_pos = start_pos

    def data(self, role):
        if role == Qt.ItemDataRole.UserRole:
            return self.path
        if role == Qt.ItemDataRole.UserRole + 1:
            return self.start_pos
        return None


class FakePlayableList:
    def __init__(self):
        self.items = [
            FakeListItem("C:/videos/a.mp4"),
            FakeListItem("C:/videos/b.mp4", 2000),
            FakeListItem("C:/videos/c.mp4"),
        ]
        self.current_row = 0
        self.signals_blocked = False
        self.block_history = []

    def count(self):
        return len(self.items)

    def item(self, index):
        return self.items[index]

    def currentRow(self):
        return self.current_row

    def setCurrentRow(self, row):
        self.current_row = row

    def currentItem(self):
        if 0 <= self.current_row < len(self.items):
            return self.items[self.current_row]
        return None

    def blockSignals(self, blocked):
        self.signals_blocked = blocked
        self.block_history.append(blocked)


class FakeSelectableItem:
    def __init__(self, path):
        self.path = path

    def data(self, role):
        if role == Qt.ItemDataRole.UserRole:
            return self.path
        return None


class FakeSelectableList:
    def __init__(self, paths):
        self.items = [FakeSelectableItem(path) for path in paths]
        self.current_row = -1
        self.block_history = []
        self.scrolled_to = None

    def count(self):
        return len(self.items)

    def item(self, row):
        return self.items[row]

    def setCurrentRow(self, row):
        self.current_row = row

    def currentRow(self):
        return self.current_row

    def scrollToItem(self, item, hint=None):
        self.scrolled_to = item

    def blockSignals(self, blocked):
        self.block_history.append(blocked)


class FakeLabel:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class FakeCheck:
    def __init__(self, checked=False):
        self.checked = checked

    def isChecked(self):
        return self.checked


class FakeVideoView:
    def __init__(self):
        self.info_visible = None
        self.message = None
        self.duration = None
        self.position = None

    def set_info_visible(self, visible):
        self.info_visible = visible

    def show_temp_message(self, message):
        self.message = message

    def set_duration(self, duration):
        self.duration = duration

    def set_position(self, position):
        self.position = position

    def set_privacy_screen(self, enabled):
        self.privacy_screen = enabled


class FakeThumbnailRail:
    def __init__(self):
        self.position = None
        self.privacy_values = []

    def set_playback_position(self, position):
        self.position = position

    def set_privacy_hidden(self, hidden):
        self.privacy_values.append(hidden)


class FakeSplitter:
    def __init__(self):
        self.hidden = False
        self.shown = False

    def hide(self):
        self.hidden = True

    def show(self):
        self.shown = True


class FakeVideoItem:
    def __init__(self):
        self.opacity = None

    def setOpacity(self, opacity):
        self.opacity = opacity


class FakeLoadPlayer:
    def __init__(self):
        self.source_set = None
        self.playback_rate = None
        self.position = None
        self.play_count = 0
        self.stop_count = 0

    def setSource(self, source):
        self.source_set = source

    def stop(self):
        self.stop_count += 1

    def setPlaybackRate(self, rate):
        self.playback_rate = rate

    def duration(self):
        return 0

    def mediaStatus(self):
        return QMediaPlayer.MediaStatus.LoadingMedia

    def setPosition(self, position):
        self.position = position

    def play(self):
        self.play_count += 1


class FakePlayerManager:
    def __init__(self, active_data):
        self.active_data = active_data

    def get_active_player(self):
        return self.active_data


class FakeKeyEvent:
    def __init__(self, event_type, key):
        self._type = event_type
        self._key = key

    def type(self):
        return self._type

    def key(self):
        return self._key


class AlwaysHandledShortcut:
    def process_event(self, source, event):
        return True


class FakePlaybackEngine:
    def __init__(self):
        self.activate_calls = []
        self.plan_calls = []
        self.clear_all_count = 0

    def activate(self, path, start_pos, generation, autoplay, view_origin=""):
        self.activate_calls.append((path, start_pos, generation, autoplay, view_origin))
        return type("ActivationResult", (), {"slot_id": 0, "waiting_for_media": False})()

    def plan_neighbors(self, current_index, playlist, generation, preferred_direction=0):
        self.plan_calls.append(
            (
                current_index,
                [(item.path, item.start_pos) for item in playlist],
                generation,
                preferred_direction,
            )
        )

    def clear_all(self):
        self.clear_all_count += 1


class PlayerEngineIntegrationTest(unittest.TestCase):
    def _make_direction_window(self):
        window = type("FakeWindow", (), {"setWindowTitle": lambda self, title: setattr(self, "title", title)})()
        window.file_list = FakePlayableList()
        window.scan_timer = FakeTimer()
        window.seek_safety_timer = FakeTimer()
        window.is_waiting_for_seek = False
        window.chk_random = FakeCheck(False)
        window.chk_autoscan = FakeCheck(False)
        window.conf_auto_play = True
        window.conf_privacy_mode = False
        window.playback_generation = 0
        window.player_engine = FakePlaybackEngine()
        window.video_view = FakeVideoView()
        window.player = FakeLoadPlayer()
        window.playback_rate = 1.0
        window._last_media_failure_key = None
        window._prepare_playback = lambda index: VideoSorter._prepare_playback(window, index)
        window._resolve_start_pos = lambda item, specific_pos: VideoSorter._resolve_start_pos(window, item, specific_pos)
        window._current_playlist_items = lambda: VideoSorter._current_playlist_items(window)
        window._increment_playback_generation = lambda: VideoSorter._increment_playback_generation(window)
        window._preload_direction_for_index = lambda index: VideoSorter._preload_direction_for_index(window, index)
        return window

    def test_play_video_delegates_activation_and_neighbor_planning_with_new_generation(self):
        window = type("FakeWindow", (), {"setWindowTitle": lambda self, title: setattr(self, "title", title)})()
        window.file_list = FakePlayableList()
        window.scan_timer = FakeTimer()
        window.seek_safety_timer = FakeTimer()
        window.is_waiting_for_seek = False
        window.chk_random = FakeCheck(False)
        window.chk_autoscan = FakeCheck(False)
        window.conf_auto_play = True
        window.conf_privacy_mode = False
        window.playback_generation = 5
        window.player_engine = FakePlaybackEngine()
        window.video_view = FakeVideoView()
        window.player = FakeLoadPlayer()
        window.playback_rate = 1.0
        window._last_media_failure_key = ("stale.mp4", "nomedia")
        window._prepare_playback = lambda index: VideoSorter._prepare_playback(window, index)
        window._resolve_start_pos = lambda item, specific_pos: VideoSorter._resolve_start_pos(window, item, specific_pos)
        window._current_playlist_items = lambda: VideoSorter._current_playlist_items(window)
        window._increment_playback_generation = lambda: VideoSorter._increment_playback_generation(window)
        window._preload_direction_for_index = lambda index: VideoSorter._preload_direction_for_index(window, index)

        VideoSorter.play_video(window, 1)

        self.assertEqual(window.playback_generation, 6)
        self.assertIsNone(window._last_media_failure_key)
        self.assertEqual(window.player_engine.activate_calls, [("C:/videos/b.mp4", 2000, 6, True, "")])
        self.assertEqual(
            window.player_engine.plan_calls,
            [
                (
                    1,
                    [
                        ("C:/videos/a.mp4", 0),
                        ("C:/videos/b.mp4", 2000),
                        ("C:/videos/c.mp4", 0),
                    ],
                    6,
                    0,
                )
            ],
        )

    def test_play_video_uses_balanced_preload_until_direction_streak_repeats(self):
        window = self._make_direction_window()

        VideoSorter.play_video(window, 0)
        VideoSorter.play_video(window, 1)

        self.assertEqual(window.player_engine.plan_calls[0][3], 0)
        self.assertEqual(window.player_engine.plan_calls[1][3], 0)

    def test_play_video_passes_forward_direction_after_repeated_forward_moves(self):
        window = self._make_direction_window()

        VideoSorter.play_video(window, 0)
        VideoSorter.play_video(window, 1)
        VideoSorter.play_video(window, 2)

        self.assertEqual(window.player_engine.plan_calls[-1][3], 1)

    def test_play_video_resets_direction_after_reverse_move(self):
        window = self._make_direction_window()

        VideoSorter.play_video(window, 0)
        VideoSorter.play_video(window, 1)
        VideoSorter.play_video(window, 2)
        VideoSorter.play_video(window, 1)

        self.assertEqual(window.player_engine.plan_calls[-1][3], 0)

    def test_auto_play_next_blocks_selection_signal_before_explicit_play(self):
        window = type("FakeWindow", (), {})()
        window.file_list = FakePlayableList()
        window.play_calls = []
        window.reset_viewer_state = lambda: None
        window.setWindowTitle = lambda title: None

        def record_play(row):
            window.play_calls.append(row)

        window.play_video = record_play

        VideoSorter.auto_play_next(window, 1)

        self.assertEqual(window.play_calls, [1])
        self.assertEqual(window.file_list.block_history, [True, False])
        self.assertFalse(window.file_list.signals_blocked)


class PlayerEngineResetAndPrivacyTest(unittest.TestCase):
    def test_reset_viewer_state_clears_engine_slots(self):
        window = type("FakeWindow", (), {})()
        window.player_engine = FakePlaybackEngine()
        window.lbl_info = FakeLabel()
        window.video_view = FakeVideoView()

        VideoSorter.reset_viewer_state(window)

        self.assertEqual(window.player_engine.clear_all_count, 1)

    def test_privacy_blocking_uses_shared_predicate(self):
        window = type("FakeWindow", (), {})()
        window.conf_privacy_mode = True
        window.conf_auto_play = True
        window._user_has_requested_visible_playback = False

        self.assertTrue(VideoSorter.is_privacy_blocking_video(window))

        window._user_has_requested_visible_playback = True

        self.assertFalse(VideoSorter.is_privacy_blocking_video(window))


class PlayerPropertyRoutingTest(unittest.TestCase):
    def test_player_property_prefers_engine_active_player(self):
        engine_player = object()
        manager_player = object()

        class Engine:
            def active_player(self):
                return engine_player

        class Manager:
            def get_active_player(self):
                return {"player": manager_player, "audio": object()}

        window = type("FakeWindow", (), {})()
        window.player_engine = Engine()
        window.player_manager = Manager()

        self.assertIs(VideoSorter.player.fget(window), engine_player)

    def test_player_property_falls_back_to_manager_when_engine_has_no_active_player(self):
        manager_player = object()

        class Engine:
            def active_player(self):
                return None

        class Manager:
            def get_active_player(self):
                return {"player": manager_player, "audio": object()}

        window = type("FakeWindow", (), {})()
        window.player_engine = Engine()
        window.player_manager = Manager()

        self.assertIs(VideoSorter.player.fget(window), manager_player)

    def test_audio_output_property_prefers_engine_active_audio(self):
        engine_audio = object()
        manager_audio = object()

        class Engine:
            def active_audio(self):
                return engine_audio

        class Manager:
            def get_active_player(self):
                return {"player": object(), "audio": manager_audio}

        window = type("FakeWindow", (), {})()
        window.player_engine = Engine()
        window.player_manager = Manager()

        self.assertIs(VideoSorter.audio_output.fget(window), engine_audio)


class PassiveListRefreshTest(unittest.TestCase):
    def test_preserve_policy_selects_watch_path_without_playing(self):
        window = type("FakeWindow", (), {})()
        window.file_list = FakeSelectableList(["C:/videos/a.mp4", "C:/videos/b.mp4"])
        window.play_calls = []
        window.last_main_path = None
        window.last_main_row = 0

        class Engine:
            def active_session(self):
                return type("Session", (), {"path": os.path.normpath("C:/videos/b.mp4")})()

        window.player_engine = Engine()
        window.play_video = lambda row, specific_start_pos=None: window.play_calls.append((row, specific_start_pos))

        VideoSorter._maybe_activate_after_list_refresh(window, "A", "preserve")

        self.assertEqual(window.file_list.current_row, 1)
        self.assertEqual(window.play_calls, [])

    def test_auto_if_no_watch_plays_main_restored_row(self):
        window = type("FakeWindow", (), {})()
        window.file_list = FakeSelectableList(["C:/videos/a.mp4", "C:/videos/b.mp4"])
        window.play_calls = []
        window.last_main_path = "C:/videos/b.mp4"
        window.last_main_row = 0
        window.last_main_pos = 2400
        window.player_engine = type("Engine", (), {"active_session": lambda self: None})()
        window.play_video = lambda row, specific_start_pos=None: window.play_calls.append((row, specific_start_pos))

        VideoSorter._maybe_activate_after_list_refresh(window, "main", "auto_if_no_watch")

        self.assertEqual(window.file_list.current_row, 1)
        self.assertEqual(window.play_calls, [(1, 2400)])

    def test_auto_if_no_watch_preserves_when_watch_exists(self):
        window = type("FakeWindow", (), {})()
        window.file_list = FakeSelectableList(["C:/videos/a.mp4"])
        window.play_calls = []
        window.last_main_path = None
        window.last_main_row = 0
        window.player_engine = type(
            "Engine",
            (),
            {"active_session": lambda self: type("Session", (), {"path": "C:/videos/a.mp4"})()},
        )()
        window.play_video = lambda row, specific_start_pos=None: window.play_calls.append((row, specific_start_pos))

        VideoSorter._maybe_activate_after_list_refresh(window, "main", "auto_if_no_watch")

        self.assertEqual(window.file_list.current_row, 0)
        self.assertEqual(window.play_calls, [])

    def test_preserve_list_refresh_replans_neighbors_for_visible_watch_without_playing(self):
        class Engine:
            def __init__(self):
                self.plan_calls = []

            def active_session(self):
                return type("Session", (), {"path": "C:/videos/b.mp4", "generation": 9})()

            def plan_neighbors(self, current_index, playlist, generation, preferred_direction=0):
                self.plan_calls.append(
                    (
                        current_index,
                        [(item.path, item.start_pos) for item in playlist],
                        generation,
                        preferred_direction,
                    )
                )

        window = type("FakeWindow", (), {})()
        window.file_list = FakeSelectableList(["C:/videos/a.mp4", "C:/videos/b.mp4", "C:/videos/c.mp4"])
        window.play_calls = []
        window.last_main_path = None
        window.last_main_row = 0
        window.chk_random = FakeCheck(False)
        window.player_engine = Engine()
        window.play_video = lambda row, specific_start_pos=None: window.play_calls.append((row, specific_start_pos))
        window._current_playlist_items = lambda: VideoSorter._current_playlist_items(window)

        VideoSorter._maybe_activate_after_list_refresh(window, "main", "preserve")

        self.assertEqual(window.file_list.current_row, 1)
        self.assertEqual(window.play_calls, [])
        self.assertEqual(
            window.player_engine.plan_calls,
            [
                (
                    1,
                    [
                        ("C:/videos/a.mp4", 0),
                        ("C:/videos/b.mp4", 0),
                        ("C:/videos/c.mp4", 0),
                    ],
                    9,
                    0,
                )
            ],
        )

    def test_change_view_mode_requests_preserve_refresh(self):
        class FileManager:
            current_mode = "main"
            is_trash_mode = False
            filter_type = None

            def set_search_keyword(self, value):
                self.search_keyword = value

            def set_view_state(self, mode, filter_type, is_trash):
                self.view_state = (mode, filter_type, is_trash)

        class Input:
            def blockSignals(self, blocked):
                pass

            def clear(self):
                self.cleared = True

        class Button:
            def setChecked(self, value):
                self.checked = value

        window = type("FakeWindow", (), {})()
        window.file_manager = FileManager()
        window.input_search = Input()
        window.btn_filter_a = Button()
        window.btn_filter_b = Button()
        window.save_main_state = lambda: setattr(window, "saved_main", True)
        window.update_calls = []
        window.update_ui_mode = lambda activation_policy="auto_if_no_watch": window.update_calls.append(activation_policy)

        VideoSorter._change_view_mode(window, "highlight", None, False)

        self.assertEqual(window.update_calls, ["preserve"])
        self.assertTrue(window.saved_main)


class WatchPathMatchingTest(unittest.TestCase):
    def test_is_active_watch_path_matches_normalized_session_path(self):
        class Engine:
            def active_session(self):
                return type("Session", (), {"path": os.path.normpath("C:/videos/a.mp4")})()

        window = type("FakeWindow", (), {})()
        window.player_engine = Engine()

        self.assertTrue(VideoSorter.is_active_watch_path(window, "C:/videos/./a.mp4"))
        self.assertFalse(VideoSorter.is_active_watch_path(window, "C:/videos/b.mp4"))


class ThumbnailPreviewCoordinatorTest(unittest.TestCase):
    def test_thumbnail_seek_routes_through_guarded_seek(self):
        class FakeWindow:
            def __init__(self):
                self.seek_calls = []

            def _execute_seek_and_play(self, timestamp):
                self.seek_calls.append(timestamp)

        window = FakeWindow()

        VideoSorter.seek_to_thumbnail(window, 42000)

        self.assertEqual(window.seek_calls, [42000])

    def test_random_start_uses_thumbnail_candidate_when_available(self):
        class FakeManager:
            def best_random_start(self, path, duration_ms):
                self.called_with = (path, duration_ms)
                return 12345

        class FakePlayer:
            def duration(self):
                return 90000

        class FakeWindow:
            def __init__(self):
                self.thumbnail_manager = FakeManager()
                self.player = FakePlayer()

        window = FakeWindow()

        result = VideoSorter._thumbnail_random_start_candidate(window, "C:/videos/a.mp4")

        self.assertEqual(result, 12345)
        self.assertEqual(window.thumbnail_manager.called_with, ("C:/videos/a.mp4", 90000))

    def test_random_start_uses_explicit_duration_when_available(self):
        class FakeManager:
            def best_random_start(self, path, duration_ms):
                self.called_with = (path, duration_ms)
                return 12345

        window = type("FakeWindow", (), {})()
        window.thumbnail_manager = FakeManager()

        result = VideoSorter._thumbnail_random_start_candidate(
            window,
            "C:/videos/a.mp4",
            duration_ms=77777,
        )

        self.assertEqual(result, 12345)
        self.assertEqual(window.thumbnail_manager.called_with, ("C:/videos/a.mp4", 77777))

    def test_immediate_random_seek_prefers_thumbnail_candidate(self):
        class FakePlayer:
            def duration(self):
                return 90000

        class FakeWindow:
            def __init__(self):
                self.target_start_pos = -1
                self.seek_calls = []
                self.player = FakePlayer()

            def _thumbnail_random_start_candidate(self, path, duration_ms=None):
                self.candidate_path = path
                self.candidate_duration = duration_ms
                return 22222

            def _execute_seek_and_play(self, timestamp):
                self.seek_calls.append(timestamp)

        window = FakeWindow()

        with patch("main.random.randint", return_value=11111):
            VideoSorter._handle_immediate_seek(
                window,
                {"player": window.player, "path": "C:/videos/a.mp4"},
            )

        self.assertEqual(window.candidate_path, "C:/videos/a.mp4")
        self.assertEqual(window.candidate_duration, 90000)
        self.assertEqual(window.seek_calls, [22222])


class FakeStatusEngine:
    def __init__(self, active_player, revealed=True, active_path=None):
        self.active = active_player
        self.revealed = revealed
        self.status_calls = []
        self.slot = type("FakeActiveSlot", (), {"expected_path": active_path})() if active_path else None

    def handle_media_status(self, player, status):
        self.status_calls.append((player, status))
        return self.revealed

    def active_player(self):
        return self.active

    def active_slot(self):
        return self.slot


class FakeFailedStatusEngine(FakeStatusEngine):
    def __init__(self, active_player, last_error="invalidmedia"):
        super().__init__(active_player=active_player, revealed=False)
        self.slot = type(
            "FakeFailedSlot",
            (),
            {
                "player": active_player,
                "state": SlotState.FAILED,
                "last_error": last_error,
            },
        )()

    def active_slot(self):
        return self.slot


class FakeErrorEngine(FakeFailedStatusEngine):
    def __init__(self, active_player):
        super().__init__(active_player, last_error="resourceerror")
        self.error_calls = []

    def handle_media_error(self, player, error_text):
        self.error_calls.append((player, error_text))
        return True


class FakeRevealEngine(FakeStatusEngine):
    def __init__(self, active_slot):
        super().__init__(active_player=None, revealed=True)
        self.slot = active_slot
        self.reveal_calls = []

    def active_slot(self):
        return self.slot

    def reveal_if_allowed(self, slot, status, fallback_expired=False):
        self.reveal_calls.append((slot, status, fallback_expired))
        return True


class FakeDurationPlayer(FakeLoadPlayer):
    def duration(self):
        return 10000


class PlayerEngineSignalHandlerTest(unittest.TestCase):
    def test_playback_status_uses_dedicated_label_when_available(self):
        window = type("FakeWindow", (), {})()
        window.lbl_playback_status = FakeLabel()
        window.lbl_info = FakeLabel()
        window.lbl_info.setText("검색 결과: 3개")
        window._last_media_failure_key = ("C:/videos/old.mp4", "invalid")

        VideoSorter._show_active_media_ready(window, "C:/videos/zeta.mp4")

        self.assertEqual(window.lbl_playback_status.text, "재생 중: zeta.mp4")
        self.assertEqual(window.lbl_info.text, "검색 결과: 3개")
        self.assertIsNone(window._last_media_failure_key)

    def test_media_status_changed_delegates_to_engine(self):
        active_player = FakeLoadPlayer()
        window = type(
            "FakeWindow",
            (),
            {
                "sender": lambda self: active_player,
                "_show_active_media_ready": VideoSorter._show_active_media_ready,
            },
        )()
        window.player_engine = FakeStatusEngine(active_player, revealed=True)
        window.video_view = FakeVideoView()
        window.lbl_info = FakeLabel()
        window.playback_rate = 1.75
        window.target_start_pos = 0

        VideoSorter.on_media_status_changed(window, "loaded")

        self.assertEqual(window.player_engine.status_calls, [(active_player, "loaded")])
        self.assertEqual(window.video_view.duration, 0)
        self.assertEqual(active_player.playback_rate, 1.75)

    def test_media_status_changed_clears_stale_failure_after_successful_reveal(self):
        active_player = FakeLoadPlayer()
        window = type(
            "FakeWindow",
            (),
            {
                "sender": lambda self: active_player,
                "_show_active_media_ready": VideoSorter._show_active_media_ready,
            },
        )()
        window.player_engine = FakeStatusEngine(active_player, revealed=True, active_path="C:/videos/b.mp4")
        window.video_view = FakeVideoView()
        window.lbl_info = FakeLabel()
        window.lbl_info.setText("재생 실패: b.mp4")
        window.playback_rate = 1.0
        window.target_start_pos = 0

        VideoSorter.on_media_status_changed(window, "loaded")

        self.assertEqual(window.lbl_info.text, "재생 중: b.mp4")

    def test_media_status_changed_updates_previous_ready_label_on_successful_reveal(self):
        active_player = FakeLoadPlayer()
        window = type(
            "FakeWindow",
            (),
            {
                "sender": lambda self: active_player,
                "_show_active_media_ready": VideoSorter._show_active_media_ready,
            },
        )()
        window.player_engine = FakeStatusEngine(active_player, revealed=True, active_path="C:/videos/zeta.mp4")
        window.video_view = FakeVideoView()
        window.lbl_info = FakeLabel()
        window.lbl_info.setText("재생 중: delta.mp4")
        window.playback_rate = 1.0
        window.target_start_pos = 0

        VideoSorter.on_media_status_changed(window, "loaded")

        self.assertEqual(window.lbl_info.text, "재생 중: zeta.mp4")

    def test_media_status_changed_random_start_prefers_thumbnail_candidate(self):
        active_player = FakeDurationPlayer()
        window = type(
            "FakeWindow",
            (),
            {
                "sender": lambda self: active_player,
                "_show_active_media_ready": VideoSorter._show_active_media_ready,
                "_thumbnail_random_start_candidate": lambda self, path, duration_ms=None: 3333,
                "_execute_seek_and_play": lambda self, timestamp: self.seek_calls.append(timestamp),
            },
        )()
        window.player_engine = FakeStatusEngine(active_player, revealed=True, active_path="C:/videos/zeta.mp4")
        window.video_view = FakeVideoView()
        window.lbl_info = FakeLabel()
        window.playback_rate = 1.0
        window.target_start_pos = -1
        window.seek_calls = []

        with patch("main.random.randint", return_value=1111):
            VideoSorter.on_media_status_changed(window, "loaded")

        self.assertEqual(window.seek_calls, [3333])

    def test_media_status_changed_random_start_uses_real_helper_and_active_duration(self):
        class FakeManager:
            def best_random_start(self, path, duration_ms):
                self.called_with = (path, duration_ms)
                return 4444

        active_player = FakeDurationPlayer()
        window = type(
            "FakeWindow",
            (),
            {
                "sender": lambda self: active_player,
                "_show_active_media_ready": VideoSorter._show_active_media_ready,
                "_thumbnail_random_start_candidate": VideoSorter._thumbnail_random_start_candidate,
                "_execute_seek_and_play": lambda self, timestamp: self.seek_calls.append(timestamp),
            },
        )()
        window.player_engine = FakeStatusEngine(active_player, revealed=True, active_path="C:/videos/zeta.mp4")
        window.video_view = FakeVideoView()
        window.lbl_info = FakeLabel()
        window.playback_rate = 1.0
        window.target_start_pos = -1
        window.seek_calls = []
        window.thumbnail_manager = FakeManager()

        VideoSorter.on_media_status_changed(window, "loaded")

        self.assertEqual(window.seek_calls, [4444])
        self.assertEqual(window.thumbnail_manager.called_with, ("C:/videos/zeta.mp4", 10000))

    def test_media_status_changed_random_start_falls_back_when_thumbnail_has_no_candidate(self):
        class FakeManager:
            def best_random_start(self, path, duration_ms):
                return None

        active_player = FakeDurationPlayer()
        window = type(
            "FakeWindow",
            (),
            {
                "sender": lambda self: active_player,
                "_show_active_media_ready": VideoSorter._show_active_media_ready,
                "_thumbnail_random_start_candidate": VideoSorter._thumbnail_random_start_candidate,
                "_execute_seek_and_play": lambda self, timestamp: self.seek_calls.append(timestamp),
            },
        )()
        window.player_engine = FakeStatusEngine(active_player, revealed=True, active_path="C:/videos/zeta.mp4")
        window.video_view = FakeVideoView()
        window.lbl_info = FakeLabel()
        window.playback_rate = 1.0
        window.target_start_pos = -1
        window.seek_calls = []
        window.thumbnail_manager = FakeManager()

        with patch("main.random.randint", return_value=1111) as randint:
            VideoSorter.on_media_status_changed(window, "loaded")

        self.assertEqual(window.seek_calls, [1111])
        randint.assert_called_once_with(0, 9000)

    def test_media_status_changed_random_start_seeks_once_per_activation(self):
        active_player = FakeDurationPlayer()
        window = type(
            "FakeWindow",
            (),
            {
                "sender": lambda self: active_player,
                "_show_active_media_ready": VideoSorter._show_active_media_ready,
                "_thumbnail_random_start_candidate": lambda self, path, duration_ms=None: 3333,
                "_execute_seek_and_play": lambda self, timestamp: self.seek_calls.append(timestamp),
            },
        )()
        window.player_engine = FakeStatusEngine(active_player, revealed=True, active_path="C:/videos/zeta.mp4")
        window.video_view = FakeVideoView()
        window.lbl_info = FakeLabel()
        window.playback_rate = 1.0
        window.target_start_pos = -1
        window.seek_calls = []

        VideoSorter.on_media_status_changed(window, "loaded")
        VideoSorter.on_media_status_changed(window, "buffered")

        self.assertEqual(window.seek_calls, [3333])

    def test_media_status_changed_reports_active_media_failure(self):
        active_player = FakeLoadPlayer()
        window = type(
            "FakeWindow",
            (),
            {
                "sender": lambda self: active_player,
                "_show_active_media_failure": VideoSorter._show_active_media_failure,
            },
        )()
        window.player_engine = FakeFailedStatusEngine(active_player)
        window.file_list = FakePlayableList()
        window.file_list.setCurrentRow(1)
        window.lbl_info = FakeLabel()
        window.video_view = FakeVideoView()

        with patch("main.logger.warning") as warning:
            VideoSorter.on_media_status_changed(window, "InvalidMedia")

        self.assertEqual(window.player_engine.status_calls, [(active_player, "InvalidMedia")])
        self.assertEqual(window.lbl_info.text, "재생 실패: b.mp4")
        self.assertEqual(window.video_view.message, "재생 실패: b.mp4")
        warning.assert_called_once()

    def test_media_status_changed_suppresses_intentional_release_failure(self):
        active_player = FakeLoadPlayer()
        window = type(
            "FakeWindow",
            (),
            {
                "sender": lambda self: active_player,
                "_show_active_media_failure": VideoSorter._show_active_media_failure,
            },
        )()
        window.player_engine = FakeFailedStatusEngine(active_player, last_error="nomedia")
        window.file_list = FakePlayableList()
        window.file_list.setCurrentRow(1)
        window.lbl_info = FakeLabel()
        window.video_view = FakeVideoView()
        suppressed_key = os.path.normcase(os.path.normpath("C:/videos/b.mp4"))
        window._suppressed_media_failure_paths = {suppressed_key}

        with patch("main.logger.warning") as warning:
            VideoSorter.on_media_status_changed(window, "NoMedia")

        self.assertEqual(window.lbl_info.text, "")
        self.assertIsNone(window.video_view.message)
        self.assertEqual(window._suppressed_media_failure_paths, set())
        warning.assert_not_called()

    def test_media_status_changed_reports_repeated_active_media_failure_once(self):
        active_player = FakeLoadPlayer()
        window = type(
            "FakeWindow",
            (),
            {
                "sender": lambda self: active_player,
                "_show_active_media_failure": VideoSorter._show_active_media_failure,
            },
        )()
        window.player_engine = FakeFailedStatusEngine(active_player, last_error="nomedia")
        window.file_list = FakePlayableList()
        window.file_list.setCurrentRow(1)
        window.lbl_info = FakeLabel()
        window.video_view = FakeVideoView()

        with patch("main.logger.warning") as warning:
            VideoSorter.on_media_status_changed(window, "NoMedia")
            VideoSorter.on_media_status_changed(window, "NoMedia")

        self.assertEqual(window.lbl_info.text, "재생 실패: b.mp4")
        self.assertEqual(window.video_view.message, "재생 실패: b.mp4")
        warning.assert_called_once()

    def test_media_error_reports_active_media_failure(self):
        active_player = FakeLoadPlayer()
        window = type(
            "FakeWindow",
            (),
            {
                "sender": lambda self: active_player,
                "_show_active_media_failure": VideoSorter._show_active_media_failure,
            },
        )()
        window.player_engine = FakeErrorEngine(active_player)
        window.file_list = FakePlayableList()
        window.file_list.setCurrentRow(1)
        window.lbl_info = FakeLabel()
        window.video_view = FakeVideoView()

        with patch("main.logger.warning") as warning:
            VideoSorter.on_media_error(window, "ResourceError", "codec failed")

        self.assertEqual(window.player_engine.error_calls, [(active_player, "codec failed")])
        self.assertEqual(window.lbl_info.text, "재생 실패: b.mp4")
        warning.assert_called_once()

    def test_position_changed_ignores_inactive_sender(self):
        active_player = FakeDurationPlayer()
        stale_player = FakeDurationPlayer()
        window = type(
            "FakeWindow",
            (),
            {"sender": lambda self: stale_player},
        )()
        window.player_engine = FakeStatusEngine(active_player)
        window.player = active_player
        window.video_view = FakeVideoView()
        window.is_waiting_for_seek = False

        VideoSorter.on_position_changed(window, 2000)

        self.assertIsNone(window.video_view.position)

    def test_position_changed_updates_thumbnail_rail_marker(self):
        active_player = FakeDurationPlayer()
        window = type(
            "FakeWindow",
            (),
            {"sender": lambda self: active_player},
        )()
        window.player_engine = FakeStatusEngine(active_player)
        window.player = active_player
        window.video_view = FakeVideoView()
        window.thumbnail_rail = FakeThumbnailRail()
        window.is_waiting_for_seek = False

        VideoSorter.on_position_changed(window, 2000)

        self.assertEqual(window.video_view.position, 2000)
        self.assertEqual(window.thumbnail_rail.position, 2000)

    def test_privacy_visibility_updates_thumbnail_rail(self):
        class Source:
            def toLocalFile(self):
                return "C:/videos/a.mp4"

        class Player:
            def source(self):
                return Source()

        window = type(
            "FakeWindow",
            (),
            {
                "setWindowTitle": lambda self, title: setattr(self, "title", title),
                "setFocus": lambda self: setattr(self, "focused", True),
            },
        )()
        window.conf_privacy_mode = True
        window.splitter = FakeSplitter()
        window.video_view = FakeVideoView()
        window.thumbnail_rail = FakeThumbnailRail()
        window.player = Player()

        VideoSorter._apply_privacy_visibility(window, False)
        VideoSorter._apply_privacy_visibility(window, True)

        self.assertEqual(window.thumbnail_rail.privacy_values, [True, False])

    def test_force_show_screen_uses_engine_reveal_guard(self):
        slot = type("FakeSlot", (), {"last_status": "loading"})()
        window = type("FakeWindow", (), {})()
        window.player_engine = FakeRevealEngine(slot)
        window.is_waiting_for_seek = True

        VideoSorter._force_show_screen(window)

        self.assertFalse(window.is_waiting_for_seek)
        self.assertEqual(window.player_engine.reveal_calls, [(slot, "loading", True)])


class VideoSorterSearchTest(unittest.TestCase):
    def test_non_empty_search_text_starts_debounce_timer(self):
        class FakeWindow:
            pass

        window = FakeWindow()
        window.search_debounce_timer = FakeTimer()

        VideoSorter.on_search_changed(window, "  sample  ")

        self.assertEqual(window._pending_search_text, "sample")
        self.assertTrue(window.search_debounce_timer.started)

    def test_empty_search_text_stops_pending_debounce_and_clears_pending_text(self):
        class FakeWindow:
            def update_ui_mode(self, activation_policy="auto_if_no_watch"):
                self.updated = True
                self.updated_policy = activation_policy

        window = FakeWindow()
        window.root_folder = "C:/videos"
        window._pending_search_text = "stale"
        window.search_debounce_timer = FakeTimer()
        window.file_manager = FakeFileManager()
        window.player = FakePlayer()
        window.lbl_info = FakeLabel()

        VideoSorter.on_search_changed(window, "   ")

        self.assertTrue(window.search_debounce_timer.stopped)
        self.assertEqual(window._pending_search_text, "")
        self.assertEqual(window.file_manager.search_keyword, "")
        self.assertEqual(window.file_manager.scanned_folder, "C:/videos")
        self.assertTrue(window.updated)
        self.assertEqual(window.updated_policy, "preserve")

    def test_empty_search_text_uses_cache_before_direct_scan(self):
        class FakeWindow:
            def update_ui_mode(self, activation_policy="auto_if_no_watch"):
                self.updated = True
                self.updated_policy = activation_policy

        window = FakeWindow()
        window.root_folder = "C:/videos"
        window._pending_search_text = "stale"
        window.search_debounce_timer = FakeTimer()
        window.file_manager = FakeFileManager()
        window.file_manager.cache_loaded = True
        window.player = FakePlayer()
        window.file_list = FakeFileList()
        window.lbl_info = FakeLabel()
        window.updated = False

        VideoSorter.on_search_changed(window, "")

        self.assertEqual(window.file_manager.cache_load_folder, "C:/videos")
        self.assertIsNone(window.file_manager.scanned_folder)
        self.assertTrue(window.updated)
        self.assertEqual(window.updated_policy, "preserve")

    def test_one_character_debounced_search_clears_previous_results(self):
        class FakeWindow:
            def update_ui_mode(self, activation_policy="auto_if_no_watch"):
                self.updated = True
                self.updated_policy = activation_policy

        window = FakeWindow()
        window.root_folder = "C:/videos"
        window._pending_search_text = "a"
        window.file_manager = FakeFileManager()
        window.file_list = FakeFileList()
        window.lbl_info = FakeLabel()

        VideoSorter._execute_search(window)

        self.assertEqual(window.file_manager.search_keyword, "")
        self.assertEqual(window.file_manager.scanned_folder, "C:/videos")
        self.assertTrue(window.updated)
        self.assertEqual(window.updated_policy, "preserve")
        self.assertIn("2글자", window.lbl_info.text)

    def test_one_character_submitted_search_uses_same_guard_as_debounced_search(self):
        class FakeInput:
            def text(self):
                return "a"

        class FakeWindow:
            def update_ui_mode(self, activation_policy="auto_if_no_watch"):
                self.updated = True
                self.updated_policy = activation_policy

        window = FakeWindow()
        window.input_search = FakeInput()
        window.root_folder = "C:/videos"
        window.search_debounce_timer = FakeTimer()
        window.file_manager = FakeFileManager()
        window.file_list = FakeFileList()
        window.lbl_info = FakeLabel()

        VideoSorter.on_search_submitted(window)

        self.assertTrue(window.search_debounce_timer.stopped)
        self.assertEqual(window.file_manager.search_keyword, "")
        self.assertEqual(window.file_manager.scanned_folder, "C:/videos")
        self.assertTrue(window.updated)
        self.assertEqual(window.updated_policy, "preserve")
        self.assertIn("2글자", window.lbl_info.text)

    def test_execute_search_uses_preserve_refresh_policy(self):
        class FakeWindow:
            def update_ui_mode(self, activation_policy="auto_if_no_watch"):
                self.updated_policy = activation_policy

        window = FakeWindow()
        window.root_folder = "C:/videos"
        window._pending_search_text = "sample"
        window.file_manager = FakeFileManager()
        window.file_list = FakeFileList()
        window.lbl_info = FakeLabel()

        VideoSorter._execute_search(window)

        self.assertEqual(window.updated_policy, "preserve")

    def test_shift_release_focuses_search_when_pressed_alone_outside_search(self):
        class FakeWindow:
            def focus_search_input(self):
                self.focused_search = True

        window = FakeWindow()
        window.input_search = object()
        window.shortcut_handler = AlwaysHandledShortcut()
        window._is_shift_pressed = False
        window._is_shift_combined = False
        window.focused_search = False
        source = object()

        VideoSorter.eventFilter(
            window,
            source,
            FakeKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Shift),
        )
        handled = VideoSorter.eventFilter(
            window,
            source,
            FakeKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Shift),
        )

        self.assertTrue(handled)
        self.assertTrue(window.focused_search)
        self.assertFalse(window._is_shift_pressed)

    def test_shift_release_does_not_focus_search_after_combination(self):
        class FakeWindow:
            def focus_search_input(self):
                self.focused_search = True

        window = FakeWindow()
        window.input_search = object()
        window.shortcut_handler = AlwaysHandledShortcut()
        window._is_shift_pressed = False
        window._is_shift_combined = False
        window.focused_search = False
        source = object()

        VideoSorter.eventFilter(
            window,
            source,
            FakeKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Shift),
        )
        VideoSorter.eventFilter(
            window,
            source,
            FakeKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A),
        )
        VideoSorter.eventFilter(
            window,
            source,
            FakeKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Shift),
        )

        self.assertFalse(window.focused_search)
        self.assertFalse(window._is_shift_pressed)

    def test_shift_release_does_not_focus_search_during_privacy_pause(self):
        class PrivacyShortcut:
            def process_event(self, source, event):
                return True

        class FakeWindow:
            def focus_search_input(self):
                self.focused_search = True

        window = FakeWindow()
        window.input_search = object()
        window.shortcut_handler = PrivacyShortcut()
        window.conf_privacy_mode = True
        window.player = FakePlayer()
        window._is_shift_pressed = False
        window._is_shift_combined = False
        window.focused_search = False
        source = object()

        self.assertTrue(VideoSorter.eventFilter(
            window,
            source,
            FakeKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Shift),
        ))
        VideoSorter.eventFilter(
            window,
            source,
            FakeKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Shift),
        )

        self.assertFalse(window.focused_search)
        self.assertFalse(window._is_shift_pressed)

    def test_indexing_data_received_schedules_refresh_instead_of_immediate_load(self):
        class FakeInput:
            def text(self):
                return ""

        class FakeManager:
            def get_folder_history(self):
                return ["C:/videos"]

        class FakeWindow:
            def load_files(self):
                self.load_count += 1

        window = FakeWindow()
        window.file_list = FakeFileList()
        window.input_search = FakeInput()
        window.file_manager = FakeManager()
        window.root_folder = "C:/videos"
        window.index_refresh_timer = FakeTimer()
        window.load_count = 0

        VideoSorter.on_indexing_data_received(
            window,
            [{"path": "C:/videos/a.mp4", "folder": "C:/videos"}],
        )

        self.assertEqual(window.load_count, 0)
        self.assertTrue(window.index_refresh_timer.started)
        self.assertTrue(window.file_list.updates_enabled)

    def test_indexing_data_received_schedules_refresh_for_nested_current_folder_chunk(self):
        class FakeInput:
            def text(self):
                return ""

        window = type("FakeWindow", (), {})()
        window.file_list = FakeFileList()
        window.input_search = FakeInput()
        window.root_folder = "C:/videos"
        window.index_refresh_timer = FakeTimer()

        VideoSorter.on_indexing_data_received(
            window,
            [{"path": "C:/videos/nested/a.mp4", "folder": "C:/videos/nested"}],
        )

        self.assertTrue(window.index_refresh_timer.started)
        self.assertTrue(window.file_list.updates_enabled)

    def test_reset_viewer_state_clears_active_player_path(self):
        active_data = {
            "path": "C:/videos/sample.mp4",
            "item": FakeVideoItem(),
            "player": FakeLoadPlayer(),
        }
        window = type("FakeWindow", (), {})()
        window.player_manager = FakePlayerManager(active_data)
        window.lbl_info = FakeLabel()
        window.video_view = FakeVideoView()

        VideoSorter.reset_viewer_state(window)

        self.assertIsNone(active_data["path"])
        self.assertEqual(active_data["player"].stop_count, 1)
        self.assertTrue(active_data["player"].source_set.isEmpty())
        self.assertEqual(active_data["item"].opacity, 0.0)

    def test_seek_does_not_start_autoscan_when_auto_play_is_disabled(self):
        window = type("FakeWindow", (), {})()
        window.conf_auto_play = False
        window.player = FakeLoadPlayer()
        window.seek_safety_timer = FakeTimer()
        window.chk_autoscan = FakeCheck(True)
        window.scan_timer = FakeTimer()

        VideoSorter._execute_seek_and_play(window, 1500)

        self.assertEqual(window.player.position, 1500)
        self.assertTrue(window.seek_safety_timer.started)
        self.assertFalse(window.scan_timer.started)

    def test_playback_rate_toast_uses_plain_text_not_escaped_html(self):
        window = type("FakeWindow", (), {})()
        window.playback_rate = 1.0
        window.player = FakeLoadPlayer()
        window.video_view = FakeVideoView()

        VideoSorter.change_playback_rate(window, 1.0)

        self.assertEqual(window.playback_rate, 2.0)
        self.assertEqual(window.player.playback_rate, 2.0)
        self.assertNotIn("<", window.video_view.message)
        self.assertNotIn(">", window.video_view.message)
        self.assertIn("x 2.0", window.video_view.message)

        VideoSorter.reset_playback_rate(window)

        self.assertEqual(window.playback_rate, 1.0)
        self.assertEqual(window.player.playback_rate, 1.0)
        self.assertNotIn("<", window.video_view.message)
        self.assertNotIn(">", window.video_view.message)
        self.assertIn("x 1.0", window.video_view.message)

    def test_delete_current_folder_history_item_clears_root_folder(self):
        class FakeFolderList:
            def currentRow(self):
                return 0

        class FakeManager:
            def __init__(self):
                self.history = []

            def remove_folder_from_history(self, row):
                self.removed_row = row
                return "C:/videos"

            def get_folder_history(self):
                return self.history

        class FakeInput:
            def text(self):
                return ""

        class FakeWindow:
            def refresh_folder_history_ui(self):
                self.refreshed = True

            def reset_viewer_state(self):
                self.reset = True

        window = FakeWindow()
        window.folder_list_widget = FakeFolderList()
        window.file_manager = FakeManager()
        window.root_folder = "C:/videos"
        window.file_list = FakeFileList()
        window.lbl_info = FakeLabel()
        window.input_search = FakeInput()
        window.refreshed = False
        window.reset = False

        VideoSorter.delete_folder_history_item(window)

        self.assertEqual(window.root_folder, "")
        self.assertTrue(window.file_list.cleared)
        self.assertTrue(window.reset)
        self.assertTrue(window.refreshed)

    def test_load_files_uses_cache_before_direct_folder_scan(self):
        class FakeThread:
            def isRunning(self):
                return False

        class FakeWindow:
            def update_ui_mode(self):
                self.updated = True

        window = FakeWindow()
        window.codec_thread = FakeThread()
        window.file_manager = FakeFileManager()
        window.file_manager.cache_loaded = True
        window.root_folder = "C:/videos"
        window.updated = False

        with patch("main.os.path.isdir", return_value=True):
            VideoSorter.load_files(window)

        self.assertEqual(window.file_manager.cache_load_folder, "C:/videos")
        self.assertIsNone(window.file_manager.scanned_folder)
        self.assertTrue(window.updated)

    def test_load_files_falls_back_to_scan_when_cache_is_empty(self):
        class FakeThread:
            def isRunning(self):
                return False

        class FakeWindow:
            def update_ui_mode(self):
                self.updated = True

        window = FakeWindow()
        window.codec_thread = FakeThread()
        window.file_manager = FakeFileManager()
        window.file_manager.cache_loaded = False
        window.root_folder = "C:/videos"
        window.updated = False

        with patch("main.os.path.isdir", return_value=True):
            VideoSorter.load_files(window)

        self.assertEqual(window.file_manager.cache_load_folder, "C:/videos")
        self.assertEqual(window.file_manager.scanned_folder, "C:/videos")
        self.assertTrue(window.updated)

    def test_load_files_force_scan_bypasses_cache(self):
        class FakeThread:
            def isRunning(self):
                return False

        class FakeWindow:
            def update_ui_mode(self):
                self.updated = True

        window = FakeWindow()
        window.codec_thread = FakeThread()
        window.file_manager = FakeFileManager()
        window.file_manager.cache_loaded = True
        window.root_folder = "C:/videos"
        window.updated = False

        with patch("main.os.path.isdir", return_value=True):
            VideoSorter.load_files(window, force_scan=True)

        self.assertFalse(hasattr(window.file_manager, "cache_load_folder"))
        self.assertEqual(window.file_manager.scanned_folder, "C:/videos")
        self.assertTrue(window.updated)

    def test_folder_history_click_forces_disk_scan(self):
        class FakeItem:
            def data(self, role):
                if role == Qt.ItemDataRole.UserRole:
                    return "C:/videos"
                return None

        class FakePlayerManager:
            def stop_all_in_mode(self, mode):
                self.stopped_mode = mode

        class FakeFolderList:
            def setFocus(self):
                self.focused = True

        class FakeWindow:
            def load_files(self, force_scan=False):
                self.load_force_scan = force_scan

        window = FakeWindow()
        window.player_manager = FakePlayerManager()
        window.folder_list_widget = FakeFolderList()
        window.lbl_info = FakeLabel()

        with patch("main.os.path.isdir", return_value=True):
            VideoSorter.on_folder_history_clicked(window, FakeItem())

        self.assertTrue(window.load_force_scan)
        self.assertEqual(window.root_folder, "C:/videos")
        self.assertEqual(window.player_manager.stopped_mode, "main")

    def test_folder_history_click_clears_engine_session_before_loading_new_folder(self):
        class FakeItem:
            def data(self, role):
                if role == Qt.ItemDataRole.UserRole:
                    return "C:/videos"
                return None

        class FakeEngine:
            def __init__(self):
                self.clear_all_count = 0

            def clear_all(self):
                self.clear_all_count += 1

        class FakePlayerManager:
            def stop_all_in_mode(self, mode):
                self.stopped_mode = mode

        class FakeFolderList:
            def setFocus(self):
                self.focused = True

        class FakeWindow:
            def load_files(self, force_scan=False):
                self.load_force_scan = force_scan

        window = FakeWindow()
        window.player_engine = FakeEngine()
        window.player_manager = FakePlayerManager()
        window.folder_list_widget = FakeFolderList()
        window.lbl_info = FakeLabel()

        with patch("main.os.path.isdir", return_value=True):
            VideoSorter.on_folder_history_clicked(window, FakeItem())

        self.assertEqual(window.player_engine.clear_all_count, 1)
        self.assertFalse(hasattr(window.player_manager, "stopped_mode"))
        self.assertTrue(window.load_force_scan)

    def test_shift_release_inside_search_does_not_refocus_search(self):
        class FakeWindow:
            def focus_search_input(self):
                self.focused_search = True

        search_source = object()
        window = FakeWindow()
        window.input_search = search_source
        window.shortcut_handler = AlwaysHandledShortcut()
        window._is_shift_pressed = False
        window._is_shift_combined = False
        window.focused_search = False

        VideoSorter.eventFilter(
            window,
            search_source,
            FakeKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Shift),
        )
        VideoSorter.eventFilter(
            window,
            search_source,
            FakeKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Shift),
        )

        self.assertFalse(window.focused_search)
        self.assertFalse(window._is_shift_pressed)


if __name__ == "__main__":
    unittest.main()
