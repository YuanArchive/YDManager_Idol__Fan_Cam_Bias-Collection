import json
import os
import tempfile
import unittest

from src.core import consts
from src.managers.thumbnail_manager import ThumbnailTimelineManager


class ThumbnailTimelineManagerTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.index_dir = os.path.join(self.temp_dir.name, "index")
        self.cache_dir = os.path.join(self.temp_dir.name, "thumbs")
        self.original = {
            "THUMBNAIL_CACHE_DIR": getattr(consts, "THUMBNAIL_CACHE_DIR", None),
            "THUMBNAIL_MANIFEST_FILE": getattr(consts, "THUMBNAIL_MANIFEST_FILE", None),
        }
        consts.THUMBNAIL_CACHE_DIR = self.cache_dir
        consts.THUMBNAIL_MANIFEST_FILE = os.path.join(self.index_dir, "thumbnail_manifest.json")

    def tearDown(self):
        for key, value in self.original.items():
            if value is None and hasattr(consts, key):
                delattr(consts, key)
            elif value is not None:
                setattr(consts, key, value)
        self.temp_dir.cleanup()

    def make_video(self):
        path = os.path.join(self.temp_dir.name, "sample.mp4")
        with open(path, "w", encoding="utf-8") as file:
            file.write("video")
        return path

    def write_manifest(self, payload):
        os.makedirs(self.index_dir, exist_ok=True)
        with open(consts.THUMBNAIL_MANIFEST_FILE, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False)

    def test_cache_hit_returns_twelve_ready_cells(self):
        path = self.make_video()
        os.makedirs(os.path.join(self.cache_dir, "abc"), exist_ok=True)
        files = []
        for index in range(12):
            name = f"{index:03d}.jpg"
            thumb = os.path.join(self.cache_dir, "abc", name)
            with open(thumb, "wb") as file:
                file.write(b"jpg")
            files.append(name)
        stat = os.stat(path)
        self.write_manifest({
            os.path.normcase(os.path.normpath(path)): {
                "path": path,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "duration_ms": 120000,
                "thumb_count": 12,
                "cache_id": "abc",
                "timestamps_ms": [i * 1000 for i in range(12)],
                "quality_scores": [0.8 for _ in range(12)],
                "files": files,
            }
        })

        manager = ThumbnailTimelineManager()
        cells = manager.cached_cells(path)

        self.assertEqual(len(cells), 12)
        self.assertTrue(all(cell.state == "ready" for cell in cells))

    def test_changed_file_size_invalidates_cache(self):
        path = self.make_video()
        manager = ThumbnailTimelineManager()

        self.assertFalse(manager.is_manifest_record_valid(path, {"size": -1, "mtime_ns": 0}))

    def test_request_timeline_queues_only_requested_path(self):
        path = self.make_video()
        manager = ThumbnailTimelineManager()

        manager.request_timeline(path, duration_ms=120000, priority="active")

        self.assertEqual([job.path for job in manager.pending_jobs], [path])

    def test_default_manager_uses_four_parallel_workers(self):
        manager = ThumbnailTimelineManager()

        self.assertEqual(manager.max_workers, 4)

    def test_background_queue_keeps_all_requested_uncached_paths(self):
        manager = ThumbnailTimelineManager()
        paths = []
        for index in range(20):
            path = os.path.join(self.temp_dir.name, f"video_{index:02d}.mp4")
            with open(path, "w", encoding="utf-8") as file:
                file.write(f"video {index}")
            paths.append(path)

        for path in paths:
            manager.request_timeline(path, duration_ms=None, priority="background")

        self.assertEqual([job.path for job in manager.pending_jobs], paths)

    def test_start_next_job_fills_available_worker_slots(self):
        manager = ThumbnailTimelineManager()
        paths = []
        started = []

        class FakeSignal:
            def connect(self, callback):
                self.callback = callback

        class FakeWorker:
            def __init__(self, job_path, timestamps_ms, output_dir):
                self.path = job_path
                self.timestamps_ms = timestamps_ms
                self.output_dir = output_dir
                self.finished_path = FakeSignal()
                self.failed_path = FakeSignal()

            def set_duration_ms(self, duration_ms):
                self.duration_ms = duration_ms

            def start(self):
                started.append(self.path)

        for index in range(5):
            path = os.path.join(self.temp_dir.name, f"parallel_{index}.mp4")
            with open(path, "w", encoding="utf-8") as file:
                file.write(f"video {index}")
            paths.append(path)
            manager.request_timeline(path, duration_ms=120000, priority="background")

        first_worker = manager.start_next_job(worker_factory=FakeWorker)

        self.assertIsNotNone(first_worker)
        self.assertEqual(len(manager.active_workers), 4)
        self.assertEqual(started, paths[:4])
        self.assertEqual([job.path for job in manager.pending_jobs], paths[4:])

    def test_request_timeline_skips_cached_pending_and_active_duplicates(self):
        path = self.make_video()
        manager = ThumbnailTimelineManager(max_workers=1)

        class FakeSignal:
            def connect(self, callback):
                self.callback = callback

        class FakeWorker:
            def __init__(self, job_path, timestamps_ms, output_dir):
                self.path = job_path
                self.finished_path = FakeSignal()
                self.failed_path = FakeSignal()

            def set_duration_ms(self, duration_ms):
                self.duration_ms = duration_ms

            def start(self):
                pass

        manager.request_timeline(path, duration_ms=120000, priority="background")
        manager.request_timeline(path, duration_ms=120000, priority="background")
        self.assertEqual(len(manager.pending_jobs), 1)

        manager.start_next_job(worker_factory=FakeWorker)
        manager.request_timeline(path, duration_ms=120000, priority="active")

        self.assertEqual(len(manager.pending_jobs), 0)
        self.assertIn(manager._path_key(path), manager.active_workers)

    def test_best_random_start_uses_cached_quality_scores(self):
        path = self.make_video()
        os.makedirs(os.path.join(self.cache_dir, "abc"), exist_ok=True)
        files = []
        for index in range(12):
            name = f"{index:03d}.jpg"
            thumb = os.path.join(self.cache_dir, "abc", name)
            with open(thumb, "wb") as file:
                file.write(b"jpg")
            files.append(name)
        stat = os.stat(path)
        scores = [0.1 for _ in range(12)]
        scores[4] = 0.95
        self.write_manifest({
            os.path.normcase(os.path.normpath(path)): {
                "path": path,
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "duration_ms": 120000,
                "thumb_count": 12,
                "cache_id": "abc",
                "timestamps_ms": [i * 10000 for i in range(12)],
                "quality_scores": scores,
                "files": files,
            }
        })
        manager = ThumbnailTimelineManager()

        self.assertEqual(manager.best_random_start(path, duration_ms=120000), 40000)

    def test_record_completed_timeline_persists_valid_manifest(self):
        path = self.make_video()
        cache_id = "abc"
        os.makedirs(os.path.join(self.cache_dir, cache_id), exist_ok=True)
        files = []
        for index in range(12):
            name = f"{index:03d}.jpg"
            with open(os.path.join(self.cache_dir, cache_id, name), "wb") as file:
                file.write(b"jpg")
            files.append(name)
        manager = ThumbnailTimelineManager()

        manager.record_completed_timeline(
            path=path,
            duration_ms=120000,
            cache_id=cache_id,
            timestamps_ms=[i * 10000 for i in range(12)],
            files=files,
            quality_scores=[0.8 for _ in range(12)],
        )
        reloaded = ThumbnailTimelineManager()

        self.assertEqual(len(reloaded.cached_cells(path)), 12)

    def test_start_next_job_builds_worker_with_sampled_timestamps(self):
        path = self.make_video()
        manager = ThumbnailTimelineManager()
        captured = {}

        class FakeSignal:
            def connect(self, callback):
                self.callback = callback

        class FakeWorker:
            def __init__(self, job_path, timestamps_ms, output_dir):
                captured["path"] = job_path
                captured["timestamps_ms"] = timestamps_ms
                captured["output_dir"] = output_dir
                self.finished_path = FakeSignal()
                self.failed_path = FakeSignal()

            def start(self):
                captured["started"] = True

        manager.request_timeline(path, duration_ms=120000, priority="active")

        worker = manager.start_next_job(worker_factory=FakeWorker, autostart=False)

        self.assertIs(worker, manager.active_worker)
        self.assertEqual(captured["path"], path)
        self.assertEqual(len(captured["timestamps_ms"]), 12)
        self.assertTrue(captured["output_dir"].startswith(self.cache_dir))
        self.assertNotIn("started", captured)

    def test_shutdown_cancels_joins_and_clears_workers(self):
        manager = ThumbnailTimelineManager()
        events = []

        class FakeSignal:
            def __init__(self):
                self.callbacks = []

            def connect(self, callback):
                self.callbacks.append(callback)

            def disconnect(self):
                self.callbacks.clear()

            def emit(self, *args):
                for callback in list(self.callbacks):
                    callback(*args)

        class FakeThreadWorker:
            def __init__(self, job_path, timestamps_ms, output_dir):
                self.path = job_path
                self.finished_path = FakeSignal()
                self.failed_path = FakeSignal()
                self.finished = FakeSignal()
                self._done = False

            def set_duration_ms(self, duration_ms):
                pass

            def start(self):
                pass

            def cancel(self):
                events.append(("cancel", self.path))
                self._done = True

            def isFinished(self):
                return self._done

            def wait(self, ms=0):
                events.append(("wait", self.path))
                return self._done

            def terminate(self):
                events.append(("terminate", self.path))
                self._done = True

            def deleteLater(self):
                events.append(("delete", self.path))

        paths = []
        for index in range(2):
            path = os.path.join(self.temp_dir.name, f"shutdown_{index}.mp4")
            with open(path, "w", encoding="utf-8") as file:
                file.write("v")
            paths.append(path)
            manager.request_timeline(path, duration_ms=120000, priority="background")
        manager.start_next_job(worker_factory=FakeThreadWorker)
        self.assertEqual(len(manager.active_workers), 2)

        manager.shutdown(wait_ms=10)

        self.assertTrue(manager._shutting_down)
        self.assertEqual(len(manager.active_workers), 0)
        self.assertEqual(manager.pending_jobs, [])
        self.assertEqual(sum(1 for event in events if event[0] == "cancel"), 2)
        self.assertEqual(sum(1 for event in events if event[0] == "wait"), 2)

        # After shutdown, no new worker may be launched.
        manager.request_timeline(paths[0], duration_ms=120000, priority="active")
        self.assertIsNone(manager.start_next_job(worker_factory=FakeThreadWorker))
        self.assertEqual(len(manager.active_workers), 0)

    def test_finished_qthread_worker_is_held_until_thread_finishes(self):
        path = self.make_video()
        manager = ThumbnailTimelineManager()
        events = []

        class FakeSignal:
            def __init__(self):
                self.callbacks = []

            def connect(self, callback):
                self.callbacks.append(callback)

            def emit(self, *args):
                for callback in list(self.callbacks):
                    callback(*args)

        class FakeThreadWorker:
            def __init__(self, job_path, timestamps_ms, output_dir):
                self.path = job_path
                self.output_dir = output_dir
                self.finished_path = FakeSignal()
                self.failed_path = FakeSignal()
                self.finished = FakeSignal()
                self.resolved_duration_ms = 120000
                self.resolved_timestamps_ms = [i * 10000 for i in range(12)]

            def set_duration_ms(self, duration_ms):
                pass

            def start(self):
                pass

            def isFinished(self):
                return True

            def wait(self, ms=0):
                return True

            def deleteLater(self):
                events.append("delete")

        manager.request_timeline(path, duration_ms=120000, priority="active")
        worker = manager.start_next_job(worker_factory=FakeThreadWorker, autostart=False)
        os.makedirs(worker.output_dir, exist_ok=True)
        files = []
        for index in range(12):
            name = f"{index:03d}.jpg"
            with open(os.path.join(worker.output_dir, name), "wb") as file:
                file.write(b"jpg")
            files.append(name)

        worker.finished_path.emit(path, files)

        # The QThread reference is held (not dropped) until finished() fires.
        self.assertIn(worker, manager._retiring)
        self.assertNotIn(manager._path_key(path), manager.active_workers)

        worker.finished.emit()

        self.assertNotIn(worker, manager._retiring)
        self.assertIn("delete", events)

    def test_finished_worker_records_manifest_and_clears_active_worker(self):
        path = self.make_video()
        manager = ThumbnailTimelineManager()
        emitted_ready = []
        worker_box = {}

        class FakeSignal:
            def __init__(self):
                self.callbacks = []

            def connect(self, callback):
                self.callbacks.append(callback)

            def emit(self, *args):
                for callback in self.callbacks:
                    callback(*args)

        class FakeWorker:
            def __init__(self, job_path, timestamps_ms, output_dir):
                self.path = job_path
                self.timestamps_ms = timestamps_ms
                self.output_dir = output_dir
                self.finished_path = FakeSignal()
                self.failed_path = FakeSignal()
                worker_box["worker"] = self

            def start(self):
                pass

        manager.timeline_ready.connect(lambda ready_path, cells: emitted_ready.append((ready_path, cells)))
        manager.request_timeline(path, duration_ms=120000, priority="active")
        worker = manager.start_next_job(worker_factory=FakeWorker, autostart=False)
        os.makedirs(worker.output_dir, exist_ok=True)
        files = []
        for index in range(12):
            name = f"{index:03d}.jpg"
            with open(os.path.join(worker.output_dir, name), "wb") as file:
                file.write(b"jpg")
            files.append(name)

        worker.finished_path.emit(path, files)

        self.assertIsNone(manager.active_worker)
        self.assertEqual(len(manager.cached_cells(path)), 12)
        self.assertEqual(emitted_ready[0][0], path)
        self.assertEqual(len(emitted_ready[0][1]), 12)
