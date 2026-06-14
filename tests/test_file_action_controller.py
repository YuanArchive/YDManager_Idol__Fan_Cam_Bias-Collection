import os
import unittest
from unittest.mock import patch

from PyQt6.QtCore import Qt
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtWidgets import QMessageBox

from src.controllers.file_action_controller import FileActionController


class FakeItem:
    def __init__(self, path):
        self.path = path
        self.text_value = os.path.basename(path) if path else ""

    def data(self, role):
        if role == Qt.ItemDataRole.UserRole:
            return self.path
        return None

    def setData(self, role, value):
        if role == Qt.ItemDataRole.UserRole:
            self.path = value

    def text(self):
        return self.text_value

    def setText(self, text):
        self.text_value = text


class FakeFileList:
    def __init__(self, path, paths=None):
        self.path = path
        self.paths = list(paths or ([path] if path else []))
        self.items = [FakeItem(path) for path in self.paths]
        self.taken_rows = []
        self.clear_count = 0

    def currentRow(self):
        return 0

    def item(self, row):
        return self.items[row]

    def takeItem(self, row):
        self.taken_rows.append(row)
        if 0 <= row < len(self.items):
            self.items.pop(row)
            self.paths.pop(row)

    def count(self):
        return len(self.items)

    def clear(self):
        self.clear_count += 1
        self.paths.clear()
        self.items.clear()


class FakeFileManager:
    def __init__(self):
        self.deleted_paths = []
        self.trash_files = []
        self.clear_trash_calls = 0

    def hard_delete_by_path(self, path):
        self.deleted_paths.append(path)
        return True, "deleted"

    def clear_trash(self):
        self.clear_trash_calls += 1
        return len(self.trash_files)


class FakePlayerManager:
    def __init__(self):
        self.released_paths = []
        self.current_mode = "main"
        self.active_indices = {"main": 0}
        self.active_data = None

    def stop_and_release_path(self, path):
        self.released_paths.append(path)
        return True

    def get_active_player(self):
        return self.active_data


class FakePlayerEngine:
    def __init__(self):
        self.cleared_paths = []

    def clear_path(self, path):
        self.cleared_paths.append(path)
        return True


class FakeLabel:
    def __init__(self):
        self.text = ""

    def setText(self, text):
        self.text = text


class FakeApp:
    def __init__(self, path, paths=None):
        self.file_list = FakeFileList(path, paths)
        self.file_manager = FakeFileManager()
        self.player_manager = FakePlayerManager()
        self.lbl_info = FakeLabel()
        self.trash_button_updates = 0
        self.auto_play_rows = []
        self.reset_count = 0
        self.update_mode_count = 0
        self.seek_calls = []
        self.title = ""

    def update_trash_button_text(self):
        self.trash_button_updates += 1

    def auto_play_next(self, row):
        self.auto_play_rows.append(row)

    def reset_viewer_state(self):
        self.reset_count += 1

    def update_ui_mode(self):
        self.update_mode_count += 1

    def _execute_seek_and_play(self, start_pos):
        self.seek_calls.append(start_pos)

    def setWindowTitle(self, title):
        self.title = title


class FakeHashPlayer:
    def __init__(self):
        self.position_value = 0
        self.source = None
        self.stop_count = 0
        self.play_count = 0

    def position(self):
        return self.position_value

    def stop(self):
        self.stop_count += 1

    def setSource(self, source):
        self.source = source

    def setPosition(self, position):
        self.position_value = position

    def play(self):
        self.play_count += 1


class FakeHighlightPlayer:
    def __init__(self, position=0, duration=0, media_status=QMediaPlayer.MediaStatus.LoadedMedia):
        self.position_value = position
        self.duration_value = duration
        self.media_status = media_status

    def position(self):
        return self.position_value

    def duration(self):
        return self.duration_value

    def mediaStatus(self):
        return self.media_status


class FakeVideoItem:
    def __init__(self):
        self.opacity = None
        self.z_value = None

    def setOpacity(self, opacity):
        self.opacity = opacity

    def setZValue(self, value):
        self.z_value = value


class FakeAudio:
    def __init__(self):
        self.muted = None

    def setMuted(self, muted):
        self.muted = muted


class FakeCheck:
    def __init__(self, checked=True):
        self.checked = checked

    def isChecked(self):
        return self.checked


class FileActionControllerTest(unittest.TestCase):
    def test_hard_delete_cancel_does_not_release_or_delete_file(self):
        app = FakeApp("C:/videos/delete.mp4")
        controller = FileActionController(app)

        with patch(
            "src.controllers.file_action_controller.ThemeMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ) as question:
            controller.hard_delete_file()

        question.assert_called_once()
        self.assertEqual(app.player_manager.released_paths, [])
        self.assertEqual(app.file_manager.deleted_paths, [])
        self.assertEqual(app.file_list.taken_rows, [])

    def test_hard_delete_confirmation_releases_then_deletes_file(self):
        app = FakeApp("C:/videos/delete.mp4")
        controller = FileActionController(app)

        with patch(
            "src.controllers.file_action_controller.ThemeMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ) as question:
            controller.hard_delete_file()

        question.assert_called_once()
        self.assertEqual(app.player_manager.released_paths, ["C:/videos/delete.mp4"])
        self.assertEqual(app.file_manager.deleted_paths, ["C:/videos/delete.mp4"])
        self.assertEqual(app.file_list.taken_rows, [0])
        self.assertEqual(app.trash_button_updates, 1)
        self.assertEqual(app.auto_play_rows, [0])

    def test_hard_delete_uses_player_engine_path_release(self):
        app = FakeApp("C:/videos/delete.mp4")
        app.player_engine = FakePlayerEngine()
        controller = FileActionController(app)

        with patch(
            "src.controllers.file_action_controller.ThemeMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            controller.hard_delete_file()

        self.assertEqual(app.player_engine.cleared_paths, ["C:/videos/delete.mp4"])
        self.assertEqual(app.player_manager.released_paths, [])

    def test_hard_delete_failure_keeps_list_item_and_does_not_advance_playback(self):
        class FailingFileManager(FakeFileManager):
            def hard_delete_by_path(self, path):
                self.deleted_paths.append(path)
                return False, "locked by another process"

        app = FakeApp("C:/videos/delete.mp4")
        app.file_manager = FailingFileManager()
        controller = FileActionController(app)

        with patch(
            "src.controllers.file_action_controller.ThemeMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ), patch(
            "src.controllers.file_action_controller.ThemeMessageBox.critical",
        ) as critical:
            controller.hard_delete_file()

        self.assertEqual(app.player_manager.released_paths, ["C:/videos/delete.mp4"])
        self.assertEqual(app.file_manager.deleted_paths, ["C:/videos/delete.mp4"])
        self.assertEqual(app.file_list.taken_rows, [])
        self.assertEqual(app.auto_play_rows, [])
        critical.assert_called_once()

    def test_delete_all_trash_releases_each_trash_path_before_clearing_and_refreshes_list(self):
        paths = ["C:/videos/a.mp4", "C:/videos/b.mp4"]
        app = FakeApp(paths[0], paths)
        app.file_manager.trash_files = [
            {"path": paths[0], "text": "a.mp4"},
            {"path": paths[1], "text": "b.mp4"},
        ]
        controller = FileActionController(app)

        with patch(
            "src.controllers.file_action_controller.ThemeMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            controller.delete_all_trash_files()

        self.assertEqual(app.player_manager.released_paths, paths)
        self.assertEqual(app.file_manager.clear_trash_calls, 1)
        self.assertEqual(app.file_list.clear_count, 1)
        self.assertEqual(app.update_mode_count, 1)
        self.assertEqual(app.reset_count, 1)

    def test_delete_all_trash_uses_player_engine_for_each_path(self):
        paths = ["C:/videos/a.mp4", "C:/videos/b.mp4"]
        app = FakeApp(paths[0], paths)
        app.player_engine = FakePlayerEngine()
        app.file_manager.trash_files = [
            {"path": paths[0], "text": "a.mp4"},
            {"path": paths[1], "text": "b.mp4"},
        ]
        controller = FileActionController(app)

        with patch(
            "src.controllers.file_action_controller.ThemeMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            controller.delete_all_trash_files()

        self.assertEqual(app.player_engine.cleared_paths, paths)
        self.assertEqual(app.player_manager.released_paths, [])

    def test_toggle_hash_mark_updates_ui_path_when_current_list_is_copy(self):
        old_path = os.path.normpath("C:/videos/a.mp4")
        new_path = os.path.normpath("C:/videos/#a.mp4")

        class HashFileManager(FakeFileManager):
            def __init__(self):
                super().__init__()
                self.current_mode = "main"

            def get_current_list(self):
                return [{"path": old_path, "text": "a.mp4"}]

            def rename_file_by_path(self, old, new_name):
                self.rename_args = (old, new_name)
                return True, "#a.mp4"

        app = FakeApp(old_path)
        app.file_manager = HashFileManager()
        app.player = FakeHashPlayer()
        app.player_manager.active_data = {
            "path": old_path,
            "player": app.player,
            "item": FakeVideoItem(),
            "audio": FakeAudio(),
        }
        app.player_engine = FakePlayerEngine()
        app.player.position_value = 4321
        app.play_calls = []
        app.play_video = lambda row, specific_start_pos=None: app.play_calls.append((row, specific_start_pos))
        app.conf_auto_play = False
        app.chk_audio = FakeCheck(True)
        controller = FileActionController(app)

        with patch(
            "src.controllers.file_action_controller.QTimer.singleShot",
            side_effect=lambda _interval, callback: callback(),
        ):
            controller.toggle_hash_mark()

        self.assertEqual(app.file_manager.rename_args, (old_path, "#a.mp4"))
        self.assertEqual(app.file_list.item(0).text(), "#a.mp4")
        self.assertEqual(app.file_list.item(0).data(Qt.ItemDataRole.UserRole), new_path)
        self.assertEqual(app.player_engine.cleared_paths, [old_path])
        self.assertEqual(app.play_calls, [(0, 4321)])

    def test_replay_current_highlight_ignores_stale_ui_row_when_current_list_is_shorter(self):
        class HighlightFileManager(FakeFileManager):
            def __init__(self):
                super().__init__()
                self.current_mode = "highlight"

            def get_current_list(self):
                return []

        app = FakeApp("C:/videos/highlight.mp4")
        app.file_manager = HighlightFileManager()
        controller = FileActionController(app)

        controller.replay_current_highlight()

        self.assertEqual(app.seek_calls, [])

    def test_save_current_highlight_uses_duration_at_end_of_media(self):
        path = "C:/videos/highlight.mp4"

        class HighlightFileManager(FakeFileManager):
            def get_current_list(self):
                return [{"path": path, "text": "highlight.mp4"}]

            def add_highlight(self, file_path, timestamp):
                self.saved_highlight = (file_path, timestamp)
                return True, "saved"

        app = FakeApp(path)
        app.file_manager = HighlightFileManager()
        app.player = FakeHighlightPlayer(
            position=0,
            duration=91000,
            media_status=QMediaPlayer.MediaStatus.EndOfMedia,
        )
        controller = FileActionController(app)

        with patch("src.controllers.file_action_controller.QTimer.singleShot"):
            controller.save_current_highlight()

        self.assertEqual(app.file_manager.saved_highlight, (path, 91000))
        self.assertIn("하이라이트 저장됨", app.title)

    def test_replay_current_highlight_seeks_to_selected_start_pos(self):
        class HighlightFileManager(FakeFileManager):
            def __init__(self):
                super().__init__()
                self.current_mode = "highlight"

            def get_current_list(self):
                return [{"path": "C:/videos/highlight.mp4", "start_pos": 12345}]

        app = FakeApp("C:/videos/highlight.mp4")
        app.file_manager = HighlightFileManager()
        controller = FileActionController(app)

        controller.replay_current_highlight()

        self.assertEqual(app.seek_calls, [12345])


if __name__ == "__main__":
    unittest.main()
