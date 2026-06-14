import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(command):
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _make_video(path: Path, color: str) -> None:
    base_command = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c={color}:s=160x90:d=1",
        "-an",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
    ]

    attempts = [
        base_command + ["-c:v", "libx264", str(path)],
        base_command + ["-c:v", "mpeg4", str(path)],
    ]
    last_error = None
    for command in attempts:
        try:
            _run(command)
            return
        except subprocess.CalledProcessError as exc:
            last_error = exc
    raise RuntimeError(f"ffmpeg could not create {path}: {last_error.stderr if last_error else ''}")


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


def run_smoke():
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required for this smoke test")

    with tempfile.TemporaryDirectory(prefix="ydm-video-smoke-") as temp_root:
        temp_root = Path(temp_root)
        media_dir = temp_root / "media"
        media_dir.mkdir()
        appdata_dir = temp_root / "appdata"
        os.environ["LOCALAPPDATA"] = str(appdata_dir)

        first_video = media_dir / "a_first.mp4"
        second_video = media_dir / "b_second.mp4"
        _make_video(first_video, "black")
        _make_video(second_video, "blue")

        sys.path.insert(0, str(ROOT))
        from PyQt6.QtCore import Qt, QUrl
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

            _assert(window.file_list.count() == 2, f"expected 2 videos, got {window.file_list.count()}")
            first_loaded = Path(window.file_list.item(0).data(Qt.ItemDataRole.UserRole))

            window.play_video(0)
            _pump_events(app, 1000)
            active_source = window.player.source().toLocalFile()
            _assert(_norm(active_source) == _norm(first_loaded), "play_video did not load the selected source")

            window.toggle_tag_file("A")
            _pump_events(app, 250)
            first_key = window.file_manager._get_norm_key(str(first_loaded))
            _assert(window.file_manager.file_tags.get(first_key) == "A", "A tag was not persisted in memory")

            window.save_current_highlight()
            _pump_events(app, 250)
            _assert(first_key in window.file_manager.highlights, "highlight was not saved")

            window.toggle_highlight_mode()
            _pump_events(app, 500)
            _assert(window.file_manager.current_mode == "highlight", "highlight mode did not activate")
            _assert(window.file_list.count() >= 1, "highlight list did not render saved highlight")
            window.replay_current_highlight()
            _pump_events(app, 500)

            window.go_to_main_mode()
            _pump_events(app, 500)
            window.file_list.setCurrentRow(0)
            before_hash_path = Path(window.file_list.currentItem().data(Qt.ItemDataRole.UserRole))
            window.play_video(0)
            _pump_events(app, 500)
            window.toggle_hash_mark()
            _pump_events(app, 700)
            hashed_path = before_hash_path.with_name("#" + before_hash_path.name)
            _assert(hashed_path.exists(), "hash rename did not create the expected renamed file")
            _assert(not before_hash_path.exists(), "hash rename left the original file in place")

            window.file_list.setCurrentRow(0)
            trash_target = Path(window.file_list.currentItem().data(Qt.ItemDataRole.UserRole))
            window.soft_delete_file()
            _pump_events(app, 500)
            trash_keys = {window.file_manager._get_norm_key(item["path"]) for item in window.file_manager.trash_files}
            _assert(window.file_manager._get_norm_key(str(trash_target)) in trash_keys, "soft delete did not add item to internal trash")

            window.toggle_trash_mode()
            _pump_events(app, 500)
            _assert(window.file_manager.is_trash_mode, "trash mode did not activate")
            window.file_list.setCurrentRow(0)
            window.restore_file()
            _pump_events(app, 500)
            restored_keys = {window.file_manager._get_norm_key(item["path"]) for item in window.file_manager.trash_files}
            _assert(window.file_manager._get_norm_key(str(trash_target)) not in restored_keys, "restore did not remove item from trash")

            window.player_manager.stop_and_release_path(str(trash_target))
            window.player.setSource(QUrl())
            window.close()
            _pump_events(app, 250)
        finally:
            if not window.isHidden():
                window.close()
            _pump_events(app, 250)

    print("video workflow smoke ok")


if __name__ == "__main__":
    run_smoke()
