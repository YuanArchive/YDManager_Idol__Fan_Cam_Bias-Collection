import os
import stat
import tempfile
import unittest
from unittest.mock import patch

from src.core.threads import BackgroundIndexer


class BackgroundIndexerTest(unittest.TestCase):
    def test_scan_recursive_ignores_missing_folder(self):
        indexer = BackgroundIndexer([])
        indexer.total_count = 0
        missing_dir = os.path.join(tempfile.gettempdir(), "ydmanager-missing-folder")

        indexer._scan_recursive(missing_dir, [])

        self.assertEqual(indexer.total_count, 0)

    def test_scan_recursive_respects_interruption_before_opening_folder(self):
        indexer = BackgroundIndexer([])
        indexer.total_count = 0
        indexer.is_running = False

        with patch("src.core.threads.os.scandir") as scandir:
            indexer._scan_recursive("C:/videos", [])

        scandir.assert_not_called()

    def test_scan_recursive_continues_after_entry_oserror(self):
        root = os.path.join(tempfile.gettempdir(), "ydmanager-root")
        good_path = os.path.join(root, "good.mp4")

        class FakeStat:
            st_size = 123

        class BadEntry:
            name = "bad.mp4"
            path = os.path.join(root, "bad.mp4")

            def is_file(self, follow_symlinks=True):
                raise OSError("transient stat failure")

        class GoodEntry:
            name = "good.mp4"
            path = good_path

            def is_file(self, follow_symlinks=True):
                return True

            def stat(self, follow_symlinks=True):
                return FakeStat()

        class FakeScandir:
            def __init__(self, path):
                self.path = path

            def __enter__(self):
                return iter([BadEntry(), GoodEntry()])

            def __exit__(self, exc_type, exc, traceback):
                return False

        indexer = BackgroundIndexer([])
        indexer.total_count = 0
        chunk = []

        with patch("src.core.threads.os.scandir", side_effect=FakeScandir):
            indexer._scan_recursive(root, chunk)

        self.assertEqual(indexer.total_count, 1)
        self.assertEqual(chunk[0]["path"], os.path.normpath(good_path))

    def test_scan_recursive_does_not_follow_symlink_directories(self):
        root = os.path.join(tempfile.gettempdir(), "ydmanager-root")
        link_path = os.path.join(root, "linked")
        visited = []
        calls = []

        class FakeEntry:
            name = "linked"
            path = link_path

            def is_file(self, follow_symlinks=True):
                calls.append(("file", follow_symlinks))
                return False

            def is_dir(self, follow_symlinks=True):
                calls.append(("dir", follow_symlinks))
                return follow_symlinks

        class FakeScandir:
            def __init__(self, path):
                self.path = path

            def __enter__(self):
                visited.append(self.path)
                return iter([FakeEntry()] if self.path == root else [])

            def __exit__(self, exc_type, exc, traceback):
                return False

        indexer = BackgroundIndexer([])
        indexer.total_count = 0

        with patch("src.core.threads.os.scandir", side_effect=FakeScandir):
            indexer._scan_recursive(root, [])

        self.assertEqual(visited, [root])
        self.assertIn(("file", False), calls)
        self.assertIn(("dir", False), calls)
        self.assertNotIn(("dir", True), calls)

    def test_scan_recursive_does_not_enter_reparse_point_directories(self):
        root = os.path.join(tempfile.gettempdir(), "ydmanager-root")
        link_path = os.path.join(root, "junction")
        visited = []

        class FakeStat:
            st_file_attributes = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

        class FakeEntry:
            name = "junction"
            path = link_path

            def is_file(self, follow_symlinks=True):
                return False

            def is_dir(self, follow_symlinks=True):
                return True

            def stat(self, follow_symlinks=True):
                return FakeStat()

        class FakeScandir:
            def __init__(self, path):
                self.path = path

            def __enter__(self):
                visited.append(self.path)
                return iter([FakeEntry()] if self.path == root else [])

            def __exit__(self, exc_type, exc, traceback):
                return False

        indexer = BackgroundIndexer([])
        indexer.total_count = 0

        with patch("src.core.threads.os.scandir", side_effect=FakeScandir):
            indexer._scan_recursive(root, [])

        self.assertEqual(visited, [root])


if __name__ == "__main__":
    unittest.main()
