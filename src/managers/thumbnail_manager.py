from __future__ import annotations

import json
import os
from dataclasses import dataclass

from src.core import consts
from src.managers.thumbnail_sampling import choose_random_start_candidate
from src.ui.thumbnail_rail import ThumbnailCell


@dataclass(frozen=True)
class ThumbnailJob:
    path: str
    duration_ms: int | None
    priority: str


class ThumbnailTimelineManager:
    def __init__(self):
        self.manifest_path = consts.THUMBNAIL_MANIFEST_FILE
        self.cache_dir = consts.THUMBNAIL_CACHE_DIR
        self.manifest = self._load_manifest()
        self.pending_jobs = []

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

    def request_timeline(
        self,
        path: str,
        duration_ms: int | None = None,
        priority: str = "active",
    ) -> None:
        if self.cached_cells(path):
            return

        job = ThumbnailJob(path=path, duration_ms=duration_ms, priority=priority)
        self.pending_jobs = [existing for existing in self.pending_jobs if existing.path != path]
        if priority == "active":
            self.pending_jobs.insert(0, job)
        else:
            self.pending_jobs.append(job)
        self.pending_jobs = self.pending_jobs[:6]
