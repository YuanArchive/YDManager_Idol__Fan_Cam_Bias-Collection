import tempfile
import unittest
from unittest.mock import patch

from src.core.thumbnail_threads import ThumbnailWorker, extract_thumbnails_ffmpeg


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

    def test_ffmpeg_extractor_reports_missing_ffmpeg(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("src.core.thumbnail_threads.shutil.which", return_value=None):
                with self.assertRaises(RuntimeError):
                    extract_thumbnails_ffmpeg("C:/videos/a.mp4", [0], temp_dir)
