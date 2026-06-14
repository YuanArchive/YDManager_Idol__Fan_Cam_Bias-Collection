import os
import shutil
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MEDIA = ROOT / "manual_test_media"


def _pump_events(app, duration_ms=250):
    deadline = time.monotonic() + (duration_ms / 1000)
    while time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)


def _norm(path):
    return os.path.normcase(os.path.normpath(str(path)))


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _copy_fixture_media(media_dir):
    candidates = [
        SOURCE_MEDIA / "delta real red.avi",
        SOURCE_MEDIA / "epsilon real blue.avi",
        SOURCE_MEDIA / "zeta real green.avi",
    ]
    missing = [path for path in candidates if not path.exists()]
    if missing:
        raise RuntimeError(f"missing manual media fixture: {missing[0]}")

    copied = []
    for source in candidates:
        target = media_dir / source.name
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def _active_source(window):
    player = window.player_engine.active_player()
    return player.source().toLocalFile() if player is not None else ""


def _assert_watch(window, expected_path, label):
    session = window.player_engine.active_session()
    _assert(session is not None, f"{label}: missing active watch session")
    active_source = _active_source(window)
    _assert(
        _norm(session.path) == _norm(expected_path),
        f"{label}: watch session path changed from {expected_path} to {session.path}",
    )
    _assert(
        _norm(active_source) == _norm(expected_path),
        f"{label}: active player source changed from {expected_path} to {active_source}",
    )


def _set_candidate_row_without_playback(window, row):
    window.file_list.blockSignals(True)
    try:
        window.file_list.setCurrentRow(row)
    finally:
        window.file_list.blockSignals(False)


def run_smoke():
    with tempfile.TemporaryDirectory(prefix="ydm-continuity-smoke-") as temp_root:
        temp_root = Path(temp_root)
        media_dir = temp_root / "media"
        media_dir.mkdir()
        appdata_dir = temp_root / "appdata"
        os.environ["LOCALAPPDATA"] = str(appdata_dir)
        copied = _copy_fixture_media(media_dir)

        sys.path.insert(0, str(ROOT))
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QApplication

        from main import VideoSorter

        app = QApplication.instance() or QApplication([])
        window = VideoSorter()
        window.show()
        _pump_events(app, 500)

        try:
            window.root_folder = str(media_dir)
            window.file_manager.add_folder_to_history(str(media_dir))
            window.refresh_folder_history_ui()
            window.load_files()
            _pump_events(app, 500)

            _assert(window.file_list.count() >= 3, f"expected at least 3 videos, got {window.file_list.count()}")

            first_path = Path(window.file_list.item(0).data(Qt.ItemDataRole.UserRole))
            second_path = Path(window.file_list.item(1).data(Qt.ItemDataRole.UserRole))
            third_path = Path(window.file_list.item(2).data(Qt.ItemDataRole.UserRole))

            window.play_video(0)
            _pump_events(app, 800)
            _assert_watch(window, first_path, "initial play")

            window.file_manager.toggle_file_tag(str(first_path), "A")
            window.file_manager.toggle_file_tag(str(second_path), "B")
            window.file_manager.add_highlight(str(first_path), 0)

            window.apply_filter("A")
            _pump_events(app, 400)
            _assert_watch(window, first_path, "A filter round trip")

            window.go_to_main_mode()
            _pump_events(app, 400)
            _assert_watch(window, first_path, "return from A")

            window.apply_filter("B")
            _pump_events(app, 400)
            _assert_watch(window, first_path, "B filter passive view")

            window.go_to_main_mode()
            _pump_events(app, 400)
            _assert_watch(window, first_path, "return from B")

            window.toggle_highlight_mode()
            _pump_events(app, 400)
            _assert_watch(window, first_path, "highlight passive view")

            window.go_to_main_mode()
            _pump_events(app, 400)
            _assert_watch(window, first_path, "return from highlight")

            window.toggle_trash_mode()
            _pump_events(app, 400)
            _assert_watch(window, first_path, "trash passive view")

            window.go_to_main_mode()
            _pump_events(app, 400)
            _assert_watch(window, first_path, "return from trash")

            window._pending_search_text = "green"
            window._execute_search()
            _pump_events(app, 400)
            _assert_watch(window, first_path, "search passive refresh")

            window.on_search_changed("")
            _pump_events(app, 400)
            _assert_watch(window, first_path, "clear search passive refresh")

            main_row_for_third = VideoSorter._row_for_path(window, str(third_path))
            _assert(main_row_for_third >= 0, "third path not visible in main list")
            _set_candidate_row_without_playback(window, main_row_for_third)
            window.soft_delete_file()
            _pump_events(app, 400)
            _assert_watch(window, first_path, "non-watch soft delete")

            window.toggle_trash_mode()
            _pump_events(app, 400)
            _assert_watch(window, first_path, "trash after non-watch delete")
            if window.file_list.count() > 0:
                _set_candidate_row_without_playback(window, 0)
                window.restore_file()
                _pump_events(app, 400)
                _assert_watch(window, first_path, "non-watch restore")

            expected = {_norm(path) for path in copied}
            observed = {_norm(path) for path in media_dir.iterdir() if path.is_file()}
            _assert(expected.issubset(observed), "fixture files were not restored before smoke shutdown")

            print("player continuity smoke ok")
        finally:
            if not window.isHidden():
                window.close()
            _pump_events(app, 250)


if __name__ == "__main__":
    run_smoke()
