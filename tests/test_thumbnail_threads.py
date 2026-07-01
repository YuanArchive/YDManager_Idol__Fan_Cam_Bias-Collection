import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from src.core.thumbnail_threads import (
    FFMPEG_FRAME_TIMEOUT_SEC,
    ThumbnailCancelled,
    ThumbnailWorker,
    extract_thumbnails_ffmpeg,
)
from src.managers.thumbnail_sampling import sample_timestamps


class ThumbnailWorkerTest(unittest.TestCase):
    def test_worker_uses_injected_extractor_and_emits_files(self):
        def extractor(path, timestamps_ms, output_dir):
            self.assertEqual(path, "C:/videos/a.mp4")
            self.assertEqual(timestamps_ms, [0, 1000])
            self.assertEqual(output_dir, "C:/thumbs")
            return ["000.jpg", "001.jpg"]

        worker = ThumbnailWorker(
            "C:/videos/a.mp4",
            [0, 1000],
            "C:/thumbs",
            extractor=extractor,
        )
        emitted = []
        worker.finished_path.connect(lambda path, files: emitted.append((path, files)))

        worker.run()

        self.assertEqual(emitted, [("C:/videos/a.mp4", ["000.jpg", "001.jpg"])])

    def test_worker_probes_duration_when_timestamps_are_unknown(self):
        captured = {}

        def extractor(path, timestamps_ms, output_dir):
            captured["path"] = path
            captured["timestamps_ms"] = timestamps_ms
            captured["output_dir"] = output_dir
            return [f"{index:03d}.jpg" for index in range(12)]

        worker = ThumbnailWorker(
            "C:/videos/a.mp4",
            [],
            "C:/thumbs",
            extractor=extractor,
        )
        emitted = []
        worker.finished_path.connect(lambda path, files: emitted.append((path, files)))

        with patch("src.core.thumbnail_threads.probe_duration_ms_ffprobe", return_value=120000):
            worker.run()

        self.assertEqual(captured["timestamps_ms"], sample_timestamps(120000))
        self.assertEqual(worker.resolved_duration_ms, 120000)
        self.assertEqual(worker.resolved_timestamps_ms, sample_timestamps(120000))
        self.assertEqual(len(emitted[0][1]), 12)

    def test_ffmpeg_extractor_builds_commands_without_shell(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.core.thumbnail_threads.shutil.which", return_value="ffmpeg"):
                with patch("src.core.thumbnail_threads.subprocess.run") as run:
                    result = extract_thumbnails_ffmpeg("C:/videos/a.mp4", [0, 1500], temp_dir)

        self.assertEqual(result, ["000.jpg", "001.jpg"])
        self.assertEqual(run.call_count, 2)
        first_args, first_kwargs = run.call_args_list[0]
        self.assertEqual(first_args[0][0], "ffmpeg")
        self.assertIn("-ss", first_args[0])
        self.assertIn("00:00:00.000", first_args[0])
        self.assertNotIn("shell", first_kwargs)

    @unittest.skipUnless(os.name == "nt", "Windows console-window behavior")
    def test_ffmpeg_extractor_hides_windows_console_window(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.core.thumbnail_threads.shutil.which", return_value="ffmpeg"):
                with patch("src.core.thumbnail_threads.subprocess.run") as run:
                    extract_thumbnails_ffmpeg("C:/videos/a.mp4", [0], temp_dir)

        _, first_kwargs = run.call_args
        self.assertEqual(first_kwargs.get("creationflags"), subprocess.CREATE_NO_WINDOW)

    def test_ffmpeg_extractor_reports_missing_ffmpeg(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.core.thumbnail_threads.shutil.which", return_value=None):
                with self.assertRaises(RuntimeError):
                    extract_thumbnails_ffmpeg("C:/videos/a.mp4", [0], temp_dir)

    def test_ffmpeg_extractor_passes_per_frame_timeout(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.core.thumbnail_threads.shutil.which", return_value="ffmpeg"):
                with patch("src.core.thumbnail_threads.subprocess.run") as run:
                    extract_thumbnails_ffmpeg("C:/videos/a.mp4", [0, 1500], temp_dir)

        for _, kwargs in run.call_args_list:
            self.assertEqual(kwargs.get("timeout"), FFMPEG_FRAME_TIMEOUT_SEC)

    def test_ffmpeg_extractor_stops_when_cancelled(self):
        calls = []

        def cancel_after_first():
            calls.append(1)
            return len(calls) > 1  # allow frame 0, cancel before frame 1

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.core.thumbnail_threads.shutil.which", return_value="ffmpeg"):
                with patch("src.core.thumbnail_threads.subprocess.run") as run:
                    with self.assertRaises(ThumbnailCancelled):
                        extract_thumbnails_ffmpeg(
                            "C:/videos/a.mp4",
                            [0, 1500, 3000],
                            temp_dir,
                            should_cancel=cancel_after_first,
                        )

        # Only the first frame ran before cancellation was observed.
        self.assertEqual(run.call_count, 1)

    def test_worker_cancel_aborts_default_extractor(self):
        worker = ThumbnailWorker("C:/videos/a.mp4", [0, 1500, 3000], "C:/thumbs")
        worker.cancel()
        emitted = {"finished": [], "failed": []}
        worker.finished_path.connect(lambda p, f: emitted["finished"].append((p, f)))
        worker.failed_path.connect(lambda p, e: emitted["failed"].append((p, e)))

        with patch("src.core.thumbnail_threads.shutil.which", return_value="ffmpeg"):
            with patch("src.core.thumbnail_threads.subprocess.run") as run:
                worker.run()

        self.assertEqual(emitted["finished"], [])
        self.assertEqual(len(emitted["failed"]), 1)
        self.assertEqual(run.call_count, 0)
