import unittest

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtMultimedia import QMediaPlayer

from src.core.event_handler import ShortcutHandler


class FakeEvent:
    def __init__(self, event_type, key=None):
        self._type = event_type
        self._key = key

    def type(self):
        return self._type

    def key(self):
        return self._key


class FakeFocusWidget:
    def __init__(self, focused=False):
        self.focused = focused
        self.selected_all = False

    def hasFocus(self):
        return self.focused

    def setFocus(self):
        self.focused = True

    def selectAll(self):
        self.selected_all = True


class FakeListItem:
    def __init__(self, path="C:/videos/sample.mp4"):
        self.path = path
        self.selected = False

    def data(self, role):
        if role == Qt.ItemDataRole.UserRole:
            return self.path
        return None

    def setSelected(self, selected):
        self.selected = selected


class FakeListWidget(FakeFocusWidget):
    def __init__(self, focused=False, items=None):
        super().__init__(focused)
        self.items = items or []
        self.current_row = -1
        self.signals_blocked = False
        self.repainted = False
        self.scrolled_items = []
        self.cleared_selection = False

    def count(self):
        return len(self.items)

    def blockSignals(self, blocked):
        self.signals_blocked = blocked

    def clearSelection(self):
        self.cleared_selection = True
        for item in self.items:
            item.setSelected(False)

    def setCurrentRow(self, row):
        self.current_row = row

    def currentRow(self):
        return self.current_row

    def item(self, row):
        return self.items[row]

    def scrollToItem(self, item, *args):
        self.scrolled_items.append(item)

    def repaint(self):
        self.repainted = True


class FakePlayer:
    def __init__(self, state=QMediaPlayer.PlaybackState.PlayingState):
        self.state = state
        self.position_value = 10000
        self.duration_value = 60000

    def playbackState(self):
        return self.state

    def position(self):
        return self.position_value

    def duration(self):
        return self.duration_value

    def setPosition(self, position):
        self.position_value = position


class FakeFileManager:
    def __init__(self):
        self.current_mode = "main"
        self.is_trash_mode = False
        self.search_keyword = ""


class FakeMainWindow:
    def __init__(self):
        self.calls = []
        self.conf_privacy_mode = False
        self.conf_seek_interval = 5
        self.player = FakePlayer()
        self.file_manager = FakeFileManager()
        self.input_search = FakeFocusWidget(False)
        self.file_list = FakeListWidget(False, [FakeListItem()])
        self.folder_list_widget = FakeListWidget(False, [FakeListItem("C:/folders/root")])
        self.root_folder = "C:/folders/root"

    def toggle_play(self):
        self.calls.append("toggle_play")

    def close(self):
        self.calls.append("close")

    def hard_delete_file(self):
        self.calls.append("hard_delete_file")

    def delete_folder_history_item(self):
        self.calls.append("delete_folder_history_item")

    def soft_delete_file(self):
        self.calls.append("soft_delete_file")

    def delete_current_highlight_item(self):
        self.calls.append("delete_current_highlight_item")

    def restore_file(self):
        self.calls.append("restore_file")

    def toggle_hash_mark(self):
        self.calls.append("toggle_hash_mark")

    def replay_current_highlight(self):
        self.calls.append("replay_current_highlight")

    def save_current_highlight(self):
        self.calls.append("save_current_highlight")

    def toggle_tag_file(self, tag):
        self.calls.append(("toggle_tag_file", tag))

    def change_playback_rate(self, delta):
        self.calls.append(("change_playback_rate", delta))

    def reset_playback_rate(self):
        self.calls.append("reset_playback_rate")

    def move_selection(self, delta):
        self.calls.append(("move_selection", delta))

    def play_video(self, row):
        self.calls.append(("play_video", row))


class ShortcutHandlerTest(unittest.TestCase):
    def make_handler(self, main=None):
        main = main or FakeMainWindow()
        return ShortcutHandler(main), main

    def test_privacy_mode_blocks_delete_key_without_destructive_action(self):
        handler, main = self.make_handler()
        main.conf_privacy_mode = True
        main.player = FakePlayer(QMediaPlayer.PlaybackState.PausedState)

        handled = handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete),
        )

        self.assertTrue(handled)
        self.assertEqual(main.calls, [])

    def test_privacy_mode_allows_space_to_resume_playback(self):
        handler, main = self.make_handler()
        main.conf_privacy_mode = True
        main.player = FakePlayer(QMediaPlayer.PlaybackState.PausedState)

        handled = handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space),
        )

        self.assertTrue(handled)
        self.assertEqual(main.calls, ["toggle_play"])

    def test_search_focus_lets_text_input_handle_delete_key(self):
        handler, main = self.make_handler()
        main.input_search = FakeFocusWidget(True)

        handled = handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete),
        )

        self.assertFalse(handled)
        self.assertEqual(main.calls, [])

    def test_delete_key_routes_by_current_focus_and_mode(self):
        handler, main = self.make_handler()

        self.assertTrue(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete),
        ))
        self.assertEqual(main.calls, ["soft_delete_file"])

        main.calls.clear()
        main.folder_list_widget = FakeFocusWidget(True)
        self.assertTrue(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete),
        ))
        self.assertEqual(main.calls, ["delete_folder_history_item"])

        main.calls.clear()
        main.file_manager.is_trash_mode = True
        self.assertTrue(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete),
        ))
        self.assertEqual(main.calls, ["hard_delete_file"])

    def test_delete_key_in_highlight_mode_deletes_highlight_not_source_file(self):
        handler, main = self.make_handler()
        main.file_manager.current_mode = "highlight"

        handled = handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete),
        )

        self.assertTrue(handled)
        self.assertEqual(main.calls, ["delete_current_highlight_item"])

    def test_enter_key_routes_by_mode(self):
        handler, main = self.make_handler()

        self.assertTrue(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return),
        ))
        self.assertEqual(main.calls, ["toggle_hash_mark"])

        main.calls.clear()
        main.file_manager.is_trash_mode = True
        self.assertTrue(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return),
        ))
        self.assertEqual(main.calls, ["restore_file"])

        main.calls.clear()
        main.file_manager.is_trash_mode = False
        main.file_manager.current_mode = "highlight"
        self.assertTrue(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Enter),
        ))
        self.assertEqual(main.calls, ["replay_current_highlight"])

    def test_highlight_key_saves_or_deletes_by_mode(self):
        handler, main = self.make_handler()

        self.assertTrue(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_3),
        ))
        self.assertEqual(main.calls, ["save_current_highlight"])

        main.calls.clear()
        main.file_manager.current_mode = "highlight"
        self.assertTrue(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_3),
        ))
        self.assertEqual(main.calls, ["delete_current_highlight_item"])

    def test_restore_key_only_handles_trash_mode(self):
        handler, main = self.make_handler()

        self.assertFalse(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_R),
        ))
        self.assertEqual(main.calls, [])

        main.file_manager.is_trash_mode = True
        self.assertTrue(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_R),
        ))
        self.assertEqual(main.calls, ["restore_file"])

    def test_playback_and_rate_shortcuts_route_to_player_and_window(self):
        handler, main = self.make_handler()

        self.assertTrue(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Left),
        ))
        self.assertEqual(main.player.position_value, 5000)

        self.assertTrue(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Right),
        ))
        self.assertEqual(main.player.position_value, 10000)

        self.assertTrue(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_BracketLeft),
        ))
        self.assertTrue(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_BracketRight),
        ))
        self.assertTrue(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Backspace),
        ))
        self.assertEqual(
            main.calls,
            [
                ("change_playback_rate", -1.0),
                ("change_playback_rate", 1.0),
                "reset_playback_rate",
            ],
        )

    def test_arrow_up_down_move_selection_when_file_list_is_active(self):
        handler, main = self.make_handler()
        main.file_list = FakeListWidget(True, [FakeListItem("C:/videos/first.mp4")])

        self.assertTrue(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Up),
        ))
        self.assertTrue(handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down),
        ))

        self.assertEqual(main.calls, [("move_selection", -1), ("move_selection", 1)])

    def test_tab_from_search_focus_moves_to_file_list_without_starting_playback(self):
        handler, main = self.make_handler()
        main.input_search = FakeFocusWidget(True)
        main.file_list = FakeListWidget(False, [FakeListItem("C:/videos/first.mp4")])

        handled = handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab),
        )

        self.assertTrue(handled)
        self.assertTrue(main.file_list.hasFocus())
        self.assertEqual(main.file_list.current_row, 0)
        self.assertTrue(main.file_list.items[0].selected)
        self.assertEqual(main.calls, [])

    def test_tab_from_file_list_during_search_returns_to_search_input(self):
        handler, main = self.make_handler()
        main.file_list = FakeListWidget(True, [FakeListItem("C:/videos/first.mp4")])
        main.input_search = FakeFocusWidget(False)
        main.file_manager.search_keyword = "sample"

        handled = handler.process_event(
            main,
            FakeEvent(QEvent.Type.KeyPress, Qt.Key.Key_Tab),
        )

        self.assertTrue(handled)
        self.assertTrue(main.input_search.hasFocus())
        self.assertTrue(main.input_search.selected_all)


if __name__ == "__main__":
    unittest.main()
