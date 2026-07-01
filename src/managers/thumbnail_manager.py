from __future__ import annotations

import json
import os
import hashlib
from dataclasses import dataclass

from PyQt6.QtCore import QObject, pyqtSignal

from src.core import consts
from src.core.thumbnail_threads import ThumbnailWorker
from src.managers.thumbnail_sampling import choose_random_start_candidate, sample_timestamps
from src.ui.thumbnail_rail import ThumbnailCell


@dataclass(frozen=True)
class ThumbnailJob:
    path: str
    duration_ms: int | None
    priority: str


class ThumbnailTimelineManager(QObject):
    timeline_ready = pyqtSignal(str, list)
    timeline_failed = pyqtSignal(str, str)

    def __init__(self, max_workers: int = 4, max_pending_jobs: int | None = 512):
        super().__init__()
        self.manifest_path = consts.THUMBNAIL_MANIFEST_FILE
        self.cache_dir = consts.THUMBNAIL_CACHE_DIR
        self.manifest = self._load_manifest()
        self.max_workers = max(1, int(max_workers))
        self.max_pending_jobs = max_pending_jobs
        self.pending_jobs = []
        self.active_workers = {}
        self.active_job_contexts = {}
        # Workers that have signalled completion but whose underlying QThread may
        # not have fully finished yet. Holding a reference here prevents CPython
        # from finalising the QThread while it is still running.
        self._retiring = set()
        self._shutting_down = False

    @property
    def active_worker(self):
        return next(iter(self.active_workers.values()), None)

    @property
    def active_job_context(self):
        return next(iter(self.active_job_contexts.values()), None)

    def _path_key(self, path: str) -> str:
        return os.path.normcase(os.path.normpath(path))

    def _load_manifest(self) -> dict:
        if not os.path.exists(self.manifest_path):
            return {}
        try:
            with open(self.manifest_path, encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save_manifest(self) -> None:
        os.makedirs(os.path.dirname(self.manifest_path), exist_ok=True)
        temp_path = f"{self.manifest_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as file:
            json.dump(self.manifest, file, ensure_ascii=False, indent=2)
        os.replace(temp_path, self.manifest_path)

    def is_manifest_record_valid(self, path: str, record: dict | None) -> bool:
        if not isinstance(record, dict):
            return False
        if record.get("thumb_count") != 12:
            return False
        try:
            stat = os.stat(path)
        except OSError:
            return False
        return record.get("size") == stat.st_size and record.get("mtime_ns") == stat.st_mtime_ns

    def cached_cells(self, path: str) -> list[ThumbnailCell]:
        record = self.manifest.get(self._path_key(path))
        if not self.is_manifest_record_valid(path, record):
            return []

        timestamps = record.get("timestamps_ms", [])
        files = record.get("files", [])
        scores = record.get("quality_scores", [0.0] * 12)
        cache_id = record.get("cache_id", "")
        if len(timestamps) != 12 or len(files) != 12:
            return []

        cells = []
        for index, (timestamp, name) in enumerate(zip(timestamps, files)):
            image_path = os.path.join(self.cache_dir, cache_id, name)
            if not os.path.exists(image_path):
                return []
            cells.append(
                ThumbnailCell(
                    index=index,
                    timestamp_ms=int(timestamp),
                    image_path=image_path,
                    state="ready",
                    quality_score=float(scores[index]) if index < len(scores) else 0.0,
                )
            )
        return cells

    def best_random_start(self, path: str, duration_ms: int) -> int | None:
        cells = self.cached_cells(path)
        if not cells:
            return None
        return choose_random_start_candidate(
            [cell.timestamp_ms for cell in cells],
            [cell.quality_score for cell in cells],
            duration_ms=duration_ms,
        )

    def record_completed_timeline(
        self,
        path: str,
        duration_ms: int,
        cache_id: str,
        timestamps_ms: list[int],
        files: list[str],
        quality_scores: list[float],
    ) -> None:
        if len(timestamps_ms) != 12 or len(files) != 12:
            return
        try:
            stat = os.stat(path)
        except OSError:
            return

        self.manifest[self._path_key(path)] = {
            "path": path,
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "duration_ms": int(duration_ms),
            "thumb_count": 12,
            "cache_id": cache_id,
            "timestamps_ms": [int(value) for value in timestamps_ms],
            "quality_scores": [float(value) for value in quality_scores],
            "files": list(files),
        }
        self._save_manifest()

    def _cache_id_for(self, path: str) -> str:
        try:
            stat = os.stat(path)
            raw = f"{self._path_key(path)}|{stat.st_size}|{stat.st_mtime_ns}"
        except OSError:
            raw = self._path_key(path)
        return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]

    def _next_startable_job(self) -> ThumbnailJob | None:
        while self.pending_jobs:
            job = self.pending_jobs.pop(0)
            key = self._path_key(job.path)
            if key in self.active_workers:
                continue
            if self.cached_cells(job.path):
                continue
            return job
        return None

    def start_next_job(self, worker_factory=ThumbnailWorker, autostart: bool = True):
        if self._shutting_down:
            return self.active_worker
        if len(self.active_workers) >= self.max_workers:
            return self.active_worker

        first_started = None
        target_count = 1 if not autostart else self.max_workers - len(self.active_workers)

        for _ in range(target_count):
            if len(self.active_workers) >= self.max_workers:
                break
            job = self._next_startable_job()
            if job is None:
                break

            timestamps = sample_timestamps(job.duration_ms) if job.duration_ms and job.duration_ms > 0 else []
            cache_id = self._cache_id_for(job.path)
            output_dir = os.path.join(self.cache_dir, cache_id)
            worker = worker_factory(job.path, timestamps, output_dir)
            if hasattr(worker, "set_duration_ms"):
                worker.set_duration_ms(job.duration_ms)

            key = self._path_key(job.path)
            self.active_workers[key] = worker
            self.active_job_contexts[key] = {
                "path": job.path,
                "duration_ms": job.duration_ms,
                "cache_id": cache_id,
                "timestamps_ms": timestamps,
                "worker": worker,
            }
            worker.finished_path.connect(self._on_worker_finished)
            worker.failed_path.connect(self._on_worker_failed)
            # Real QThread workers expose the built-in `finished` signal, which
            # only fires once run() has fully returned and the thread has torn
            # down. Retire (deleteLater) the worker then so its C++ QThread is
            # never destroyed while still running.
            finished_signal = getattr(worker, "finished", None)
            if finished_signal is not None and hasattr(finished_signal, "connect"):
                finished_signal.connect(lambda w=worker: self._retire_worker(w))
            if autostart:
                worker.start()
            if first_started is None:
                first_started = worker

        return first_started or self.active_worker

    def _hold_until_finished(self, worker) -> None:
        """Keep a reference to a completed QThread until it has fully finished.

        The custom finished_path/failed_path signals are emitted from the last
        line of run(), before the QThread has torn down. Dropping the only
        reference here would let CPython finalise the QThread while it is still
        running ("QThread: Destroyed while thread is still running"). Real
        QThreads expose isFinished()/wait(); plain test doubles do not and are
        simply released.
        """
        if worker is None:
            return
        if hasattr(worker, "isFinished") and hasattr(worker, "wait"):
            self._retiring.add(worker)

    def _retire_worker(self, worker) -> None:
        self._retiring.discard(worker)
        deleter = getattr(worker, "deleteLater", None)
        if callable(deleter):
            try:
                deleter()
            except RuntimeError:
                pass

    def _on_worker_finished(self, path: str, files: list[str]) -> None:
        key = self._path_key(path)
        context = self.active_job_contexts.get(key)
        if not context or self._path_key(path) != self._path_key(context["path"]):
            return
        worker = self.active_workers.get(key)
        duration_ms = getattr(worker, "resolved_duration_ms", None) or context["duration_ms"]
        timestamps_ms = getattr(worker, "resolved_timestamps_ms", None) or context["timestamps_ms"]
        self.active_workers.pop(key, None)
        self.active_job_contexts.pop(key, None)
        self._hold_until_finished(worker)

        if self._shutting_down:
            return

        if duration_ms and timestamps_ms:
            self.record_completed_timeline(
                path=path,
                duration_ms=int(duration_ms),
                cache_id=str(context["cache_id"]),
                timestamps_ms=list(timestamps_ms),
                files=list(files),
                quality_scores=[0.8 for _ in files],
            )
        cells = self.cached_cells(path)
        self.timeline_ready.emit(path, cells)
        self.start_next_job()

    def _on_worker_failed(self, path: str, error: str) -> None:
        key = self._path_key(path)
        worker = self.active_workers.get(key)
        self.active_workers.pop(key, None)
        self.active_job_contexts.pop(key, None)
        self._hold_until_finished(worker)
        if self._shutting_down:
            return
        self.timeline_failed.emit(path, error)
        self.start_next_job()

    def shutdown(self, wait_ms: int = 3000) -> None:
        """Stop all thumbnail workers and join their QThreads before teardown.

        Safe to call from the UI thread in closeEvent. Prevents orphaned ffmpeg
        subprocesses (which keep video file handles open) and the fatal
        'QThread: Destroyed while thread is still running' abort at exit.
        """
        self._shutting_down = True
        self.pending_jobs = []
        workers = list(self.active_workers.values()) + list(self._retiring)

        for worker in workers:
            for signal_name in ("finished_path", "failed_path"):
                signal = getattr(worker, signal_name, None)
                disconnect = getattr(signal, "disconnect", None)
                if callable(disconnect):
                    try:
                        disconnect()
                    except (TypeError, RuntimeError):
                        pass
            cancel = getattr(worker, "cancel", None)
            if callable(cancel):
                try:
                    cancel()
                except RuntimeError:
                    pass

        for worker in workers:
            waiter = getattr(worker, "wait", None)
            if callable(waiter):
                try:
                    if not waiter(wait_ms):
                        terminate = getattr(worker, "terminate", None)
                        if callable(terminate):
                            terminate()
                            waiter(1000)
                except RuntimeError:
                    pass
            deleter = getattr(worker, "deleteLater", None)
            if callable(deleter):
                try:
                    deleter()
                except RuntimeError:
                    pass

        self.active_workers.clear()
        self.active_job_contexts.clear()
        self._retiring.clear()

    def _trim_pending_jobs(self) -> None:
        if self.max_pending_jobs is not None:
            self.pending_jobs = self.pending_jobs[: max(0, int(self.max_pending_jobs))]

    def request_timeline(
        self,
        path: str,
        duration_ms: int | None = None,
        priority: str = "active",
    ) -> bool:
        if not path or self.cached_cells(path):
            return False

        key = self._path_key(path)
        if key in self.active_workers:
            return False

        existing_index = next(
            (
                index
                for index, existing in enumerate(self.pending_jobs)
                if self._path_key(existing.path) == key
            ),
            None,
        )
        job = ThumbnailJob(path=path, duration_ms=duration_ms, priority=priority)
        if existing_index is not None:
            self.pending_jobs.pop(existing_index)
            if priority == "active":
                self.pending_jobs.insert(0, job)
            else:
                self.pending_jobs.insert(existing_index, job)
            self._trim_pending_jobs()
            return False

        if priority == "active":
            self.pending_jobs.insert(0, job)
        else:
            self.pending_jobs.append(job)
        self._trim_pending_jobs()
        return True
