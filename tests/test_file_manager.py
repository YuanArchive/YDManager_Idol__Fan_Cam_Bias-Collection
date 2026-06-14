import json
import os
import stat
import tempfile
import unittest
from unittest.mock import patch

from src.core import consts
from src.managers.file_manager import FileManager


class FileManagerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.index_dir = os.path.join(self.temp_dir.name, "index")
        self.legacy_index_dir = os.path.join(self.temp_dir.name, "legacy_index")
        self.original_paths = {
            "LEGACY_INDEX_DIR": consts.LEGACY_INDEX_DIR,
            "INDEX_DIR": consts.INDEX_DIR,
            "TAGS_FILE": consts.TAGS_FILE,
            "HIGHLIGHTS_FILE": consts.HIGHLIGHTS_FILE,
            "HISTORY_FILE": consts.HISTORY_FILE,
            "TRASH_CACHE_FILE": consts.TRASH_CACHE_FILE,
            "GLOBAL_CACHE_FILE": consts.GLOBAL_CACHE_FILE,
        }
        consts.LEGACY_INDEX_DIR = self.legacy_index_dir
        consts.INDEX_DIR = self.index_dir
        consts.TAGS_FILE = os.path.join(self.index_dir, "video_tags.json")
        consts.HIGHLIGHTS_FILE = os.path.join(self.index_dir, "video_highlights.json")
        consts.HISTORY_FILE = os.path.join(self.index_dir, "folder_history.json")
        consts.TRASH_CACHE_FILE = os.path.join(self.index_dir, "trash_cache.json")
        consts.GLOBAL_CACHE_FILE = os.path.join(self.index_dir, "video_global_cache.json")

    def tearDown(self):
        for name, value in self.original_paths.items():
            setattr(consts, name, value)
        self.temp_dir.cleanup()

    def make_manager(self):
        return FileManager()

    def write_json(self, path, payload):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False)

    def test_save_json_creates_missing_parent_directory(self):
        manager = self.make_manager()
        target_path = os.path.join(self.index_dir, "nested", "video_tags.json")
        payload = {"sample.mp4": "A"}

        saved = manager.save_json(target_path, payload)

        self.assertTrue(saved)
        self.assertTrue(os.path.exists(target_path))
        with open(target_path, encoding="utf-8") as saved_file:
            self.assertEqual(json.load(saved_file), payload)

    def test_load_json_returns_empty_dict_for_malformed_json(self):
        os.makedirs(self.index_dir, exist_ok=True)
        with open(consts.TAGS_FILE, "w", encoding="utf-8") as file:
            file.write("{ broken json")
        manager = self.make_manager()

        self.assertEqual(manager.load_json(consts.TAGS_FILE), {})

    def test_file_manager_migrates_legacy_index_files_before_loading(self):
        legacy_tags_path = os.path.join(self.legacy_index_dir, "video_tags.json")
        os.makedirs(self.legacy_index_dir, exist_ok=True)
        legacy_file_path = os.path.join(self.temp_dir.name, "legacy.mp4")
        with open(legacy_tags_path, "w", encoding="utf-8") as file:
            json.dump({legacy_file_path: "A"}, file)

        manager = self.make_manager()

        migrated_tags_path = os.path.join(self.index_dir, "video_tags.json")
        self.assertTrue(os.path.exists(migrated_tags_path))
        self.assertEqual(manager.file_tags, {manager._get_norm_key(legacy_file_path): "A"})

    def test_add_folder_to_history_deduplicates_equivalent_paths(self):
        manager = self.make_manager()
        folder = os.path.join(self.temp_dir.name, "Videos")
        os.makedirs(folder)

        first_added = manager.add_folder_to_history(folder)
        second_added = manager.add_folder_to_history(os.path.join(folder, "."))

        self.assertTrue(first_added)
        self.assertFalse(second_added)
        self.assertEqual(manager.folder_history, [os.path.normpath(folder)])

    def test_toggle_file_tag_updates_memory_and_persisted_tags(self):
        manager = self.make_manager()
        video_path = os.path.join(self.temp_dir.name, "sample.mp4")
        manager.main_files = [{"path": video_path, "text": "sample.mp4"}]

        new_tag = manager.toggle_file_tag(video_path, "A")

        self.assertEqual(new_tag, "A")
        self.assertEqual(manager.main_files[0]["text"], "⭐ sample.mp4")
        with open(consts.TAGS_FILE, encoding="utf-8") as file:
            saved_tags = json.load(file)
        self.assertEqual(saved_tags, {manager._get_norm_key(video_path): "A"})

        removed_tag = manager.toggle_file_tag(video_path, "A")

        self.assertIsNone(removed_tag)
        self.assertEqual(manager.main_files[0]["text"], "sample.mp4")
        with open(consts.TAGS_FILE, encoding="utf-8") as file:
            self.assertEqual(json.load(file), {})

    def test_load_trash_skips_invalid_entries_and_deduplicates_paths(self):
        video_path = os.path.join(self.temp_dir.name, "sample.mp4")
        self.write_json(
            consts.TRASH_CACHE_FILE,
            [
                {"name": "missing-path.mp4"},
                {"path": video_path, "name": "sample.mp4"},
                {"path": video_path, "name": "sample-duplicate.mp4"},
            ],
        )

        manager = self.make_manager()

        self.assertEqual(len(manager.trash_files), 1)
        self.assertEqual(manager.trash_files[0]["path"], video_path)
        self.assertEqual(manager.trash_files[0]["text"], "sample.mp4")

    def test_save_trash_skips_invalid_entries_and_deduplicates_paths(self):
        video_path = os.path.join(self.temp_dir.name, "sample.mp4")
        manager = self.make_manager()
        manager.trash_files = [
            "not-a-trash-record",
            {"name": "missing-path.mp4"},
            {"path": video_path, "text": "sample.mp4"},
            {"path": video_path, "text": "sample-duplicate.mp4"},
        ]

        manager.save_trash()

        self.assertEqual(len(manager.trash_files), 1)
        self.assertEqual(manager.trash_files[0]["path"], video_path)

    def test_scan_folder_skips_malformed_trash_entries(self):
        manager = self.make_manager()
        root = os.path.join(self.temp_dir.name, "videos")
        os.makedirs(root)
        video_path = os.path.join(root, "sample.mp4")
        with open(video_path, "w", encoding="utf-8") as file:
            file.write("video placeholder")
        manager.trash_files = [
            {"name": "missing-path.mp4"},
            "not-a-trash-record",
        ]

        manager.scan_folder(root)

        self.assertEqual([item["path"] for item in manager.main_files], [video_path])

    def test_get_current_list_skips_malformed_trash_entries(self):
        manager = self.make_manager()
        valid_path = os.path.join(self.temp_dir.name, "valid.mp4")
        manager.trash_files = [
            {"name": "missing-path.mp4"},
            "not-a-trash-record",
            {"path": valid_path, "text": "valid.mp4"},
        ]
        manager.set_view_state("trash", is_trash=True)

        result = manager.get_current_list()

        self.assertEqual(result, [{"path": valid_path, "text": "valid.mp4", "name": "valid.mp4", "folder": self.temp_dir.name}])

    def test_soft_delete_and_restore_updates_lists_and_global_cache(self):
        manager = self.make_manager()
        video_path = os.path.join(self.temp_dir.name, "sample.mp4")
        with open(video_path, "w", encoding="utf-8") as file:
            file.write("video placeholder")
        item = {
            "path": video_path,
            "name": "sample.mp4",
            "text": "sample.mp4",
            "folder": self.temp_dir.name,
        }
        manager.root_folder = self.temp_dir.name
        manager.main_files = [item.copy()]
        manager.global_files = [item.copy()]

        deleted = manager.soft_delete_by_path(video_path)

        self.assertEqual(deleted["path"], video_path)
        self.assertEqual(manager.main_files, [])
        self.assertEqual(manager.global_files, [])
        self.assertEqual([entry["path"] for entry in manager.trash_files], [video_path])

        manager.set_view_state("trash", is_trash=True)
        restored = manager.restore(0)

        self.assertEqual(restored["path"], video_path)
        self.assertEqual([entry["path"] for entry in manager.trash_files], [])
        self.assertEqual([entry["path"] for entry in manager.global_files], [video_path])
        self.assertEqual([entry["path"] for entry in manager.main_files], [video_path])

    def test_soft_delete_skips_malformed_trash_and_global_cache_entries(self):
        manager = self.make_manager()
        video_path = os.path.join(self.temp_dir.name, "sample.mp4")
        with open(video_path, "w", encoding="utf-8") as file:
            file.write("video placeholder")
        item = {
            "path": video_path,
            "name": "sample.mp4",
            "text": "sample.mp4",
            "folder": self.temp_dir.name,
        }
        manager.main_files = [item.copy()]
        manager.trash_files = [
            "not-a-trash-record",
            {"name": "missing-path.mp4"},
        ]
        manager.global_files = [
            "not-a-file-record",
            {"name": "missing-path.mp4"},
            item.copy(),
        ]

        deleted = manager.soft_delete_by_path(video_path)

        self.assertEqual(deleted["path"], video_path)
        self.assertEqual(manager.main_files, [])
        self.assertEqual(manager.global_files, [])
        self.assertEqual([entry["path"] for entry in manager.trash_files], [video_path])

    def test_restore_skips_malformed_global_cache_entries(self):
        manager = self.make_manager()
        video_path = os.path.join(self.temp_dir.name, "sample.mp4")
        other_path = os.path.join(self.temp_dir.name, "other.mp4")
        for path in (video_path, other_path):
            with open(path, "w", encoding="utf-8") as file:
                file.write("video placeholder")
        manager.root_folder = self.temp_dir.name
        manager.trash_files = [{
            "path": video_path,
            "name": "sample.mp4",
            "text": "sample.mp4",
            "folder": self.temp_dir.name,
        }]
        manager.global_files = [
            "not-a-file-record",
            {"name": "missing-path.mp4"},
            {
                "path": other_path,
                "name": "other.mp4",
                "text": "other.mp4",
                "folder": self.temp_dir.name,
            },
        ]
        manager.set_view_state("trash", is_trash=True)

        restored = manager.restore(0)

        self.assertEqual(restored["path"], video_path)
        self.assertEqual([entry["path"] for entry in manager.trash_files], [])
        self.assertEqual(
            [entry["path"] for entry in manager.global_files],
            sorted([other_path, video_path]),
        )
        self.assertEqual([entry["path"] for entry in manager.main_files], [video_path])

    def test_restore_missing_file_does_not_readd_dead_path(self):
        manager = self.make_manager()
        missing_path = os.path.join(self.temp_dir.name, "missing.mp4")
        manager.root_folder = self.temp_dir.name
        manager.trash_files = [{
            "path": missing_path,
            "name": "missing.mp4",
            "text": "missing.mp4",
            "folder": self.temp_dir.name,
        }]
        manager.set_view_state("trash", is_trash=True)

        restored = manager.restore(0)

        self.assertIsNone(restored)
        self.assertEqual([entry["path"] for entry in manager.trash_files], [missing_path])
        self.assertEqual(manager.global_files, [])
        self.assertEqual(manager.main_files, [])

    def test_restore_all_restores_existing_files_and_leaves_missing_trash_entries(self):
        manager = self.make_manager()
        valid_path = os.path.join(self.temp_dir.name, "valid.mp4")
        missing_path = os.path.join(self.temp_dir.name, "missing.mp4")
        with open(valid_path, "w", encoding="utf-8") as file:
            file.write("video placeholder")
        manager.root_folder = self.temp_dir.name
        manager.trash_files = [
            {
                "path": valid_path,
                "name": "valid.mp4",
                "text": "valid.mp4",
                "folder": self.temp_dir.name,
            },
            {
                "path": missing_path,
                "name": "missing.mp4",
                "text": "missing.mp4",
                "folder": self.temp_dir.name,
            },
        ]
        manager.set_view_state("trash", is_trash=True)

        restored_count = manager.restore_all()

        self.assertEqual(restored_count, 1)
        self.assertEqual([entry["path"] for entry in manager.trash_files], [missing_path])
        self.assertEqual([entry["path"] for entry in manager.main_files], [valid_path])
        self.assertEqual([entry["path"] for entry in manager.global_files], [valid_path])

    def test_hard_delete_skips_malformed_trash_entries(self):
        manager = self.make_manager()
        video_path = os.path.join(self.temp_dir.name, "sample.mp4")
        manager.trash_files = [
            {"name": "missing-path.mp4"},
            {"path": video_path, "text": "sample.mp4"},
        ]

        success, message = manager.hard_delete_by_path(video_path)

        self.assertTrue(success, message)
        self.assertEqual(manager.trash_files, [])

    def test_clear_trash_skips_malformed_entries_and_clears_valid_items(self):
        manager = self.make_manager()
        video_path = os.path.join(self.temp_dir.name, "sample.mp4")
        manager.trash_files = [
            {"name": "missing-path.mp4"},
            {"path": video_path, "text": "sample.mp4"},
        ]
        manager.global_files = [
            "not-a-file-record",
            {"name": "missing-path.mp4"},
            {"path": video_path, "name": "sample.mp4", "folder": self.temp_dir.name},
        ]

        deleted_count = manager.clear_trash()

        self.assertEqual(deleted_count, 1)
        self.assertEqual(manager.trash_files, [])
        self.assertEqual(manager.global_files, [])

    def test_hard_delete_skips_malformed_main_and_global_entries(self):
        manager = self.make_manager()
        video_path = os.path.join(self.temp_dir.name, "sample.mp4")
        manager.main_files = [
            "not-a-file-record",
            {"name": "missing-path.mp4"},
            {"path": video_path, "text": "sample.mp4"},
        ]
        manager.global_files = [
            "not-a-file-record",
            {"name": "missing-path.mp4"},
            {"path": video_path, "name": "sample.mp4", "folder": self.temp_dir.name},
        ]

        success, message = manager.hard_delete_by_path(video_path)

        self.assertTrue(success, message)
        self.assertEqual(manager.main_files, [])
        self.assertEqual(manager.global_files, [])

    def test_rename_file_skips_malformed_global_cache_entries_after_os_rename(self):
        manager = self.make_manager()
        old_path = os.path.join(self.temp_dir.name, "sample.mp4")
        new_name = "#sample.mp4"
        new_path = os.path.join(self.temp_dir.name, new_name)
        with open(old_path, "w", encoding="utf-8") as file:
            file.write("video placeholder")

        manager.main_files = [{"path": old_path, "text": "sample.mp4"}]
        manager.global_files = [
            "not-a-file-record",
            {"name": "missing-path.mp4"},
            {
                "path": old_path,
                "name": "sample.mp4",
                "folder": self.temp_dir.name,
                "text": "sample.mp4",
            },
        ]

        success, message = manager.rename_file_by_path(old_path, new_name)

        self.assertTrue(success, message)
        self.assertTrue(os.path.exists(new_path))
        self.assertEqual([item["path"] for item in manager.global_files], [new_path])

    def test_highlight_operations_skip_malformed_timestamp_values(self):
        manager = self.make_manager()
        video_path = os.path.join(self.temp_dir.name, "sample.mp4")
        with open(video_path, "w", encoding="utf-8") as file:
            file.write("video placeholder")

        key = manager._get_norm_key(video_path)
        manager.highlights = {key: ["bad", None, 1500]}

        display_list = manager.get_highlight_display_list()

        self.assertEqual([item["start_pos"] for item in display_list], [1500])

        success, message = manager.add_highlight(video_path, 2500)

        self.assertTrue(success, message)
        self.assertEqual(manager.highlights[key], [1500, 2500])

    def test_update_global_cache_skips_invalid_entries_and_sorts_by_name(self):
        manager = self.make_manager()
        z_path = os.path.join(self.temp_dir.name, "zeta.mp4")
        a_path = os.path.join(self.temp_dir.name, "alpha.mp4")
        manager.global_files = [
            {"name": "missing-path.mp4"},
            {"path": z_path, "name": "zeta.mp4", "folder": self.temp_dir.name},
        ]

        manager.update_global_cache([
            {"path": a_path, "folder": self.temp_dir.name},
            {"name": "new-missing-path.mp4"},
        ])

        self.assertEqual(
            [item["path"] for item in manager.global_files],
            [a_path, z_path],
        )
        self.assertEqual(
            [item["name"] for item in manager.global_files],
            ["alpha.mp4", "zeta.mp4"],
        )

    def test_update_global_cache_persists_by_default_for_direct_calls(self):
        manager = self.make_manager()
        video_path = os.path.join(self.temp_dir.name, "sample.mp4")
        saved_paths = []

        def fake_save(path, payload):
            saved_paths.append((path, list(payload)))
            return True

        manager.save_json = fake_save

        manager.update_global_cache([{"path": video_path, "folder": self.temp_dir.name}])

        self.assertEqual(len(saved_paths), 1)
        self.assertEqual(saved_paths[0][0], manager.global_cache_path)
        self.assertEqual(saved_paths[0][1][0]["path"], video_path)

    def test_indexing_chunks_merge_in_memory_and_persist_once_on_finish(self):
        manager = self.make_manager()
        first = os.path.join(self.temp_dir.name, "videos", "b_second.mp4")
        second = os.path.join(self.temp_dir.name, "videos", "a_first.mp4")
        manager.folder_history = [os.path.join(self.temp_dir.name, "videos")]
        emitted_chunks = []
        manager.indexing_data_received.connect(lambda chunk: emitted_chunks.append(chunk))
        saved_payloads = []

        def fake_save(path, payload):
            saved_payloads.append((path, list(payload)))
            return True

        manager.save_json = fake_save

        manager._on_worker_data([{"path": first, "folder": os.path.dirname(first)}])
        manager._on_worker_data([{"path": second, "folder": os.path.dirname(second)}])

        self.assertEqual(saved_payloads, [])
        self.assertEqual([item["path"] for item in manager.global_files], [second, first])
        self.assertEqual(len(emitted_chunks), 2)

        manager._on_worker_finished(2)

        self.assertEqual(len(saved_payloads), 1)
        self.assertEqual(saved_payloads[0][0], manager.global_cache_path)
        self.assertEqual([item["path"] for item in saved_payloads[0][1]], [second, first])

    def test_indexing_chunk_does_not_readd_trashed_file_to_global_cache(self):
        manager = self.make_manager()
        root = os.path.join(self.temp_dir.name, "videos")
        video_path = os.path.join(root, "sample.mp4")
        manager.folder_history = [root]
        manager.trash_files = [{"path": video_path, "text": "sample.mp4"}]
        emitted_chunks = []
        manager.indexing_data_received.connect(lambda chunk: emitted_chunks.append(chunk))

        manager._on_worker_data([{"path": video_path, "folder": root}])

        self.assertEqual(manager.global_files, [])
        self.assertEqual(emitted_chunks, [])
        self.assertFalse(manager._global_cache_dirty)

    def test_readding_removed_folder_clears_removed_folder_tombstone(self):
        manager = self.make_manager()
        root = os.path.join(self.temp_dir.name, "videos")
        video_path = os.path.join(root, "sample.mp4")
        manager._removed_folder_keys.add(manager._folder_key_with_separator(root))

        added = manager.add_folder_to_history(root)
        manager._on_worker_data([{"path": video_path, "folder": root}])

        self.assertTrue(added)
        self.assertEqual([item["path"] for item in manager.global_files], [video_path])

    def test_global_search_skips_invalid_cache_entries(self):
        manager = self.make_manager()
        video_path = os.path.join(self.temp_dir.name, "sample.mp4")
        with open(video_path, "w", encoding="utf-8") as file:
            file.write("video placeholder")
        manager.global_files = [
            {"name": "missing-path.mp4", "text": "sample"},
            {"path": video_path, "name": "sample.mp4", "folder": self.temp_dir.name},
        ]
        manager.set_search_keyword("sample")

        result = manager.get_current_list()

        self.assertEqual([item["path"] for item in result], [video_path])

    def test_global_search_skips_missing_files(self):
        manager = self.make_manager()
        missing_path = os.path.join(self.temp_dir.name, "missing_sample.mp4")
        manager.global_files = [
            {"path": missing_path, "name": "missing_sample.mp4", "folder": self.temp_dir.name},
        ]
        manager.set_search_keyword("sample")

        result = manager.get_current_list()

        self.assertEqual(result, [])

    def test_stop_indexing_requests_thread_interruption(self):
        class FakeIndexerThread:
            def __init__(self):
                self.is_running = True
                self.interruption_requested = False
                self.quit_called = False
                self.wait_timeout = None

            def isRunning(self):
                return True

            def requestInterruption(self):
                self.interruption_requested = True

            def quit(self):
                self.quit_called = True

            def wait(self, timeout):
                self.wait_timeout = timeout
                return True

        manager = self.make_manager()
        fake_thread = FakeIndexerThread()
        manager.indexer_thread = fake_thread

        stopped = manager.stop_indexing()

        self.assertTrue(stopped)
        self.assertFalse(fake_thread.is_running)
        self.assertTrue(fake_thread.interruption_requested)
        self.assertTrue(fake_thread.quit_called)
        self.assertEqual(fake_thread.wait_timeout, 3000)

    def test_stop_indexing_returns_false_when_thread_wait_times_out(self):
        class FakeIndexerThread:
            def __init__(self):
                self.is_running = True
                self.wait_timeout = None

            def isRunning(self):
                return True

            def requestInterruption(self):
                pass

            def quit(self):
                pass

            def wait(self, timeout):
                self.wait_timeout = timeout
                return False

        manager = self.make_manager()
        fake_thread = FakeIndexerThread()
        manager.indexer_thread = fake_thread

        with self.assertLogs(level="WARNING") as logs:
            stopped = manager.stop_indexing()

        self.assertFalse(stopped)
        self.assertFalse(fake_thread.is_running)
        self.assertEqual(fake_thread.wait_timeout, 3000)
        self.assertIn("did not stop", "\n".join(logs.output))

    def test_stop_indexing_flushes_dirty_global_cache_after_thread_stops(self):
        class FakeIndexerThread:
            def __init__(self):
                self.is_running = True

            def isRunning(self):
                return True

            def requestInterruption(self):
                pass

            def quit(self):
                pass

            def wait(self, timeout):
                return True

        manager = self.make_manager()
        video_path = os.path.join(self.temp_dir.name, "sample.mp4")
        manager.indexer_thread = FakeIndexerThread()
        manager.global_files = [{"path": video_path, "name": "sample.mp4"}]
        manager._global_cache_dirty = True
        saved_payloads = []

        def fake_save(path, payload):
            saved_payloads.append((path, list(payload)))
            return True

        manager.save_json = fake_save

        stopped = manager.stop_indexing()

        self.assertTrue(stopped)
        self.assertFalse(manager._global_cache_dirty)
        self.assertEqual(len(saved_payloads), 1)
        self.assertEqual(saved_payloads[0][0], manager.global_cache_path)

    def test_reset_all_data_aborts_when_indexer_does_not_stop(self):
        manager = self.make_manager()
        manager.stop_indexing = lambda: False
        manager.file_tags = {"sample": "A"}
        manager.folder_history = [self.temp_dir.name]
        manager.global_files = [{"path": os.path.join(self.temp_dir.name, "sample.mp4")}]

        with self.assertLogs(level="WARNING") as logs:
            reset = manager.reset_all_data()

        self.assertFalse(reset)
        self.assertIn("Reset aborted", "\n".join(logs.output))
        self.assertEqual(manager.file_tags, {"sample": "A"})
        self.assertEqual(manager.folder_history, [self.temp_dir.name])
        self.assertEqual(manager.global_files, [{"path": os.path.join(self.temp_dir.name, "sample.mp4")}])

    def test_start_indexing_uses_folder_history_snapshot(self):
        class FakeSignal:
            def connect(self, callback):
                self.callback = callback

        class FakeIndexerThread:
            instances = []

            def __init__(self, folder_history):
                self.folder_history = folder_history
                self.data_signal = FakeSignal()
                self.finished_signal = FakeSignal()
                self.started = False
                FakeIndexerThread.instances.append(self)

            def start(self):
                self.started = True

        manager = self.make_manager()
        first_folder = os.path.join(self.temp_dir.name, "first")
        manager.folder_history = [first_folder]

        with patch("src.managers.file_manager.BackgroundIndexer", FakeIndexerThread):
            manager.start_indexing()

        indexer = FakeIndexerThread.instances[0]
        manager.folder_history.append(os.path.join(self.temp_dir.name, "second"))

        self.assertIsNot(indexer.folder_history, manager.folder_history)
        self.assertEqual(indexer.folder_history, [first_folder])
        self.assertTrue(indexer.started)

    def test_reset_all_data_stops_running_indexer_before_clearing_cache(self):
        manager = self.make_manager()
        called = []
        manager.stop_indexing = lambda: called.append("stopped")
        manager.file_tags = {"sample": "A"}
        manager.folder_history = [self.temp_dir.name]
        manager.global_files = [{"path": os.path.join(self.temp_dir.name, "sample.mp4")}]

        manager.reset_all_data()

        self.assertEqual(called, ["stopped"])
        self.assertEqual(manager.file_tags, {})
        self.assertEqual(manager.folder_history, [])
        self.assertEqual(manager.global_files, [])

    def test_remove_folder_from_history_prunes_cache_and_skips_invalid_entries(self):
        manager = self.make_manager()
        removed_root = os.path.join(self.temp_dir.name, "removed")
        kept_root = os.path.join(self.temp_dir.name, "removed_extra")
        nested_path = os.path.join(removed_root, "nested", "drop.mp4")
        root_path = os.path.join(removed_root, "drop_root.mp4")
        kept_path = os.path.join(kept_root, "keep.mp4")
        manager.folder_history = [removed_root, kept_root]
        manager.global_files = [
            {"path": nested_path, "name": "drop.mp4", "folder": os.path.dirname(nested_path)},
            {"path": root_path, "name": "drop_root.mp4"},
            {"path": kept_path, "name": "keep.mp4", "folder": kept_root},
            {"name": "invalid.mp4"},
        ]

        removed = manager.remove_folder_from_history(0)

        self.assertEqual(removed, os.path.normpath(removed_root))
        self.assertEqual(manager.folder_history, [kept_root])
        self.assertEqual([item["path"] for item in manager.global_files], [kept_path])

    def test_remove_folder_from_history_prunes_by_path_when_folder_metadata_is_stale(self):
        manager = self.make_manager()
        removed_root = os.path.join(self.temp_dir.name, "remove")
        kept_root = os.path.join(self.temp_dir.name, "keep")
        stale_path = os.path.join(removed_root, "nested", "drop.mp4")
        keep_path = os.path.join(kept_root, "keep.mp4")
        manager.folder_history = [removed_root, kept_root]
        manager.global_files = [
            {"path": stale_path, "name": "drop.mp4", "folder": kept_root},
            {"path": keep_path, "name": "keep.mp4", "folder": kept_root},
        ]

        removed = manager.remove_folder_from_history(0)

        self.assertEqual(removed, os.path.normpath(removed_root))
        self.assertEqual([item["path"] for item in manager.global_files], [keep_path])

    def test_remove_folder_from_history_stops_indexer_and_ignores_late_chunks_from_removed_folder(self):
        manager = self.make_manager()
        removed_root = os.path.join(self.temp_dir.name, "removed")
        kept_root = os.path.join(self.temp_dir.name, "kept")
        late_removed = os.path.join(removed_root, "late.mp4")
        late_kept = os.path.join(kept_root, "late.mp4")
        manager.folder_history = [removed_root, kept_root]
        stopped = []
        manager.stop_indexing = lambda: stopped.append("stopped")

        removed = manager.remove_folder_from_history(0)
        manager._on_worker_data([
            {"path": late_removed, "folder": removed_root},
            {"path": late_kept, "folder": kept_root},
        ])

        self.assertEqual(removed, os.path.normpath(removed_root))
        self.assertEqual(stopped, ["stopped"])
        self.assertEqual([item["path"] for item in manager.global_files], [late_kept])

    def test_scan_folder_collects_videos_recursively_and_excludes_trash(self):
        manager = self.make_manager()
        root = os.path.join(self.temp_dir.name, "videos")
        nested = os.path.join(root, "nested")
        os.makedirs(nested)
        keep_path = os.path.join(nested, "b_keep.mp4")
        first_path = os.path.join(root, "a_first.mkv")
        ignored_text = os.path.join(root, "notes.txt")
        trashed_path = os.path.join(root, "c_trash.mp4")
        for path in [keep_path, first_path, ignored_text, trashed_path]:
            with open(path, "w", encoding="utf-8") as file:
                file.write("placeholder")
        manager.trash_files = [{"path": trashed_path, "text": "c_trash.mp4"}]

        manager.scan_folder(root)

        self.assertEqual(
            [item["path"] for item in manager.main_files],
            [first_path, keep_path],
        )
        self.assertEqual(
            [item["text"] for item in manager.main_files],
            ["a_first.mkv", "b_keep.mp4"],
        )

    def test_scan_folder_deduplicates_equivalent_paths(self):
        manager = self.make_manager()
        root = os.path.join(self.temp_dir.name, "videos")
        os.makedirs(root)
        video_path = os.path.join(root, "sample.mp4")
        with open(video_path, "w", encoding="utf-8") as file:
            file.write("placeholder")

        with patch.object(
            manager,
            "_iter_video_paths",
            return_value=[video_path, os.path.join(root, ".", "sample.mp4")],
        ):
            manager.scan_folder(root)

        self.assertEqual([item["path"] for item in manager.main_files], [video_path])

    def test_load_main_files_from_cache_uses_existing_cache_without_scanning_folder(self):
        manager = self.make_manager()
        root = os.path.join(self.temp_dir.name, "videos")
        nested = os.path.join(root, "nested")
        other_root = os.path.join(self.temp_dir.name, "other")
        os.makedirs(nested)
        os.makedirs(other_root)
        first_path = os.path.join(root, "b_second.mp4")
        nested_path = os.path.join(nested, "a_first.mp4")
        trashed_path = os.path.join(root, "c_trash.mp4")
        other_path = os.path.join(other_root, "z_other.mp4")
        missing_path = os.path.join(root, "missing.mp4")
        for path in [first_path, nested_path, trashed_path, other_path]:
            with open(path, "w", encoding="utf-8") as file:
                file.write("placeholder")
        manager.global_files = [
            {"path": first_path, "name": "b_second.mp4", "folder": root},
            {"path": nested_path, "name": "a_first.mp4", "folder": nested},
            {"path": trashed_path, "name": "c_trash.mp4", "folder": root},
            {"path": other_path, "name": "z_other.mp4", "folder": other_root},
            {"path": missing_path, "name": "missing.mp4", "folder": root},
            {"name": "invalid.mp4"},
        ]
        manager.trash_files = [{"path": trashed_path, "text": "c_trash.mp4"}]

        with patch.object(manager, "_iter_video_paths", side_effect=AssertionError("scan should not run")):
            loaded = manager.load_main_files_from_cache(root)

        self.assertTrue(loaded)
        self.assertEqual(manager.root_folder, os.path.normpath(root))
        self.assertEqual(
            [item["path"] for item in manager.main_files],
            [nested_path, first_path],
        )
        self.assertEqual(
            [item["text"] for item in manager.main_files],
            ["a_first.mp4", "b_second.mp4"],
        )

    def test_load_main_files_from_cache_returns_false_when_cache_has_no_live_files(self):
        manager = self.make_manager()
        root = os.path.join(self.temp_dir.name, "videos")
        os.makedirs(root)
        manager.global_files = [{"path": os.path.join(root, "missing.mp4"), "folder": root}]

        loaded = manager.load_main_files_from_cache(root)

        self.assertFalse(loaded)
        self.assertEqual(manager.main_files, [])

    def test_iter_video_paths_does_not_follow_symlink_directories(self):
        manager = self.make_manager()
        root = os.path.join(self.temp_dir.name, "videos")
        os.makedirs(root)
        calls = []

        class FakeEntry:
            name = "linked"
            path = os.path.join(root, "linked")

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
                return iter([FakeEntry()] if self.path == root else [])

            def __exit__(self, exc_type, exc, traceback):
                return False

        with patch("src.managers.file_manager.os.scandir", side_effect=FakeScandir):
            result = list(manager._iter_video_paths(root))

        self.assertEqual(result, [])
        self.assertIn(("file", False), calls)
        self.assertIn(("dir", False), calls)
        self.assertNotIn(("dir", True), calls)

    def test_iter_video_paths_does_not_enter_reparse_point_directories(self):
        manager = self.make_manager()
        root = os.path.join(self.temp_dir.name, "videos")
        link_path = os.path.join(root, "junction")
        os.makedirs(root)
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

        with patch("src.managers.file_manager.os.scandir", side_effect=FakeScandir):
            result = list(manager._iter_video_paths(root))

        self.assertEqual(result, [])
        self.assertEqual(visited, [root])

    def test_rename_file_updates_global_cache_tags_and_highlights(self):
        manager = self.make_manager()
        old_path = os.path.join(self.temp_dir.name, "sample.mp4")
        new_name = "#sample.mp4"
        new_path = os.path.join(self.temp_dir.name, new_name)
        with open(old_path, "w", encoding="utf-8") as file:
            file.write("video placeholder")

        old_key = manager._get_norm_key(old_path)
        new_key = manager._get_norm_key(new_path)
        manager.main_files = [{"path": old_path, "text": "sample.mp4"}]
        manager.global_files = [{
            "path": old_path,
            "name": "sample.mp4",
            "folder": self.temp_dir.name,
            "text": "sample.mp4",
        }]
        manager.file_tags = {old_key: "A"}
        manager.highlights = {old_key: [1234]}

        success, message = manager.rename_file_by_path(old_path, new_name)

        self.assertTrue(success, message)
        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(new_path))
        self.assertEqual(manager.main_files[0]["path"], new_path)
        self.assertEqual(manager.global_files[0]["path"], new_path)
        self.assertEqual(manager.global_files[0]["name"], new_name)
        self.assertEqual(manager.file_tags, {new_key: "A"})
        self.assertEqual(manager.highlights, {new_key: [1234]})


if __name__ == "__main__":
    unittest.main()
