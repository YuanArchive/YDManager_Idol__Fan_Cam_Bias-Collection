import unittest
from unittest.mock import patch

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtMultimedia import QMediaPlayer

from main import VideoSorter


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

    def set_info_visible(self, visible):
        self.info_visible = visible

    def show_temp_message(self, message):
        self.message = message


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
            def update_ui_mode(self):
                self.updated = True

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

    def test_empty_search_text_uses_cache_before_direct_scan(self):
        class FakeWindow:
            def update_ui_mode(self):
                self.updated = True

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

    def test_one_character_debounced_search_clears_previous_results(self):
        class FakeWindow:
            def update_ui_mode(self):
                self.updated = True

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
        self.assertIn("2글자", window.lbl_info.text)

    def test_one_character_submitted_search_uses_same_guard_as_debounced_search(self):
        class FakeInput:
            def text(self):
                return "a"

        class FakeWindow:
            def update_ui_mode(self):
                self.updated = True

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
        self.assertIn("2글자", window.lbl_info.text)

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

    def test_zero_start_new_media_sets_fallback_wait_flag_until_force_show(self):
        class FakeWindow:
            def setWindowTitle(self, title):
                self.title = title

        item = FakeVideoItem()
        active_data = {
            "path": None,
            "item": item,
            "player": FakeLoadPlayer(),
        }
        window = FakeWindow()
        window.video_view = FakeVideoView()
        window.conf_auto_play = False
        window.conf_privacy_mode = False
        window.target_start_pos = 0
        window.seek_safety_timer = FakeTimer()
        window.playback_rate = 1.0
        window.chk_autoscan = FakeCheck(False)
        window.scan_timer = FakeTimer()
        window.preload_timer = FakeTimer()
        window.is_waiting_for_seek = False
        window.player_manager = FakePlayerManager(active_data)

        VideoSorter._execute_media_load(window, active_data, "C:/videos/new.mp4")

        self.assertTrue(window.is_waiting_for_seek)
        self.assertEqual(item.opacity, 0.0)
        self.assertTrue(window.seek_safety_timer.started)

        VideoSorter._force_show_screen(window)

        self.assertFalse(window.is_waiting_for_seek)
        self.assertEqual(item.opacity, 1.0)

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

    def test_autoscan_timer_does_not_start_when_auto_play_is_disabled(self):
        active_data = {
            "path": None,
            "item": FakeVideoItem(),
            "player": FakeLoadPlayer(),
        }
        window = type("FakeWindow", (), {"setWindowTitle": lambda self, title: None})()
        window.video_view = FakeVideoView()
        window.conf_auto_play = False
        window.conf_privacy_mode = False
        window.target_start_pos = 0
        window.seek_safety_timer = FakeTimer()
        window.playback_rate = 1.0
        window.chk_autoscan = FakeCheck(True)
        window.scan_timer = FakeTimer()
        window.preload_timer = FakeTimer()
        window.is_waiting_for_seek = False

        VideoSorter._execute_media_load(window, active_data, "C:/videos/new.mp4")

        self.assertFalse(window.scan_timer.started)

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
