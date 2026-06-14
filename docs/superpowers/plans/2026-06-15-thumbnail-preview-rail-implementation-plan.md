# Thumbnail Preview Rail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an orientation-capable 12-cell thumbnail preview rail that keeps the 16:9 video unobstructed, supports 200% hover preview, click-to-seek, current/highlight markers, smarter sampling, lazy cache generation, and thumbnail-assisted random start.

**Architecture:** Add a separate preview subsystem beside `PlayerEngine`: `ThumbnailPreviewRailWidget` renders and handles input, `ThumbnailTimelineManager` owns cache/requests/stale guards, `thumbnail_sampling` computes exactly 12 useful timestamps, and `ThumbnailWorker` extracts images off the GUI thread. `VideoSorter` only coordinates state and routes clicks through `_execute_seek_and_play(...)`.

**Tech Stack:** Python 3, PyQt6, existing `QThread` pattern, PyAV for frame extraction, Pillow for resize/save, existing pytest suite and smoke scripts.

---

## Required Feature Set

Implement these requirements together as one coherent preview feature:

1. Use smarter 12-frame sampling that avoids black, low-information, blurry, or near-duplicate frames where possible.
2. Show current playback position on the nearest thumbnail cell.
3. Show saved highlight markers on the nearest thumbnail cells.
4. Click seeks to that cell timestamp. Shift-click and modifier-click actions are not assigned.
5. Generate active/selected/nearby preview timelines by priority, with bounded lazy background work.
6. Always render exactly 12 cells for every video, regardless of duration.
7. Use cached thumbnail quality data to improve random-start selection without blocking playback.

Also:

- default UI is a right-side vertical rail;
- widget internals support future horizontal placement;
- hover shows a 200% enlarged preview without resizing the rail;
- thumbnail generation never uses `QMediaPlayer` and never bypasses `PlayerEngine`.

## File Structure

Create:

- `src/ui/thumbnail_rail.py`
  - Orientation-capable 12-cell UI widget, hover preview, markers, click signal.

- `src/managers/thumbnail_sampling.py`
  - Pure functions for exact 12 timestamp sampling, frame-quality scoring, replacement decisions, and random-start candidate selection.

- `src/managers/thumbnail_manager.py`
  - Manifest loading, cache validation, request prioritization, stale-result guards, manager signals.

- `src/core/thumbnail_threads.py`
  - Background extraction worker.

- `tests/test_thumbnail_sampling.py`
  - Sampling and random-start unit tests.

- `tests/test_thumbnail_manager.py`
  - Manifest, cache, queue, stale-result, and boundary unit tests.

- `tests/test_thumbnail_rail.py`
  - Widget model, orientation, hover, click, and marker behavior tests.

Modify:

- `requirements.txt`
  - Add `av` and `Pillow` after verifying package compatibility.

- `src/core/consts.py`
  - Add thumbnail cache directory and manifest paths.

- `src/ui/ui_layout.py`
  - Add `ThumbnailPreviewRailWidget` as a sibling to `ProVideoView`.

- `src/core/signal_setup.py`
  - Wire rail click signal to `VideoSorter.seek_to_thumbnail(...)`.

- `main.py`
  - Create manager, request timelines, pass position/highlight data, route click seek, improve random start, shut down worker.

- `src/managers/player_engine.py`
  - No functional changes planned. This file is listed only because tests must prove the thumbnail subsystem does not bypass it.

- `tests/test_video_sorter.py`
  - Add coordinator tests for click seek, random-start fallback, passive selection, and playback boundary.

- `tests/test_cleanup_static.py`
  - Add static guards against thumbnail code calling `QMediaPlayer.setSource(...)`.

- `docs/maintenance/manual-smoke-test.md`
  - Add preview rail smoke checklist.

## Task 1: Exact 12-Cell Sampling Core

**Files:**

- Create: `src/managers/thumbnail_sampling.py`
- Test: `tests/test_thumbnail_sampling.py`

- [ ] **Step 1: Write failing sampling tests**

Create `tests/test_thumbnail_sampling.py`:

```python
import unittest

from src.managers.thumbnail_sampling import (
    choose_random_start_candidate,
    sample_timestamps,
)


class ThumbnailSamplingTest(unittest.TestCase):
    def test_sample_timestamps_always_returns_twelve_for_short_video(self):
        result = sample_timestamps(duration_ms=5000)

        self.assertEqual(len(result), 12)
        self.assertTrue(all(0 <= value <= 5000 for value in result))
        self.assertEqual(result, sorted(result))

    def test_sample_timestamps_always_returns_twelve_for_long_video(self):
        result = sample_timestamps(duration_ms=30 * 60 * 1000)

        self.assertEqual(len(result), 12)
        self.assertGreater(result[0], 0)
        self.assertLess(result[-1], 30 * 60 * 1000)

    def test_random_start_prefers_good_quality_candidate(self):
        timestamps = [1000, 2000, 3000, 4000]
        scores = [0.1, 0.95, 0.2, 0.3]

        result = choose_random_start_candidate(timestamps, scores, duration_ms=5000, seed=1)

        self.assertEqual(result, 2000)

    def test_random_start_returns_none_without_candidates(self):
        self.assertIsNone(choose_random_start_candidate([], [], duration_ms=10000, seed=1))
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_thumbnail_sampling.py -q
```

Expected:

- import fails because `thumbnail_sampling.py` does not exist.

- [ ] **Step 3: Implement minimal sampling module**

Create `src/managers/thumbnail_sampling.py`:

```python
from __future__ import annotations

import random

THUMBNAIL_CELL_COUNT = 12


def sample_timestamps(duration_ms: int | None, count: int = THUMBNAIL_CELL_COUNT) -> list[int]:
    if count <= 0:
        return []
    if not duration_ms or duration_ms <= 0:
        return [0 for _ in range(count)]

    safe_start = int(duration_ms * 0.05)
    safe_end = int(duration_ms * 0.95)
    if safe_end <= safe_start:
        safe_start = 0
        safe_end = max(0, duration_ms)

    if count == 1:
        return [min(duration_ms, max(0, (safe_start + safe_end) // 2))]

    span = max(0, safe_end - safe_start)
    values = []
    for index in range(count):
        ratio = index / (count - 1)
        timestamp = safe_start + int(span * ratio)
        values.append(min(duration_ms, max(0, timestamp)))
    return values


def choose_random_start_candidate(
    timestamps_ms: list[int],
    quality_scores: list[float],
    duration_ms: int,
    seed: int | None = None,
) -> int | None:
    if not timestamps_ms or not quality_scores:
        return None
    safe_start = int(duration_ms * 0.05)
    safe_end = int(duration_ms * 0.95)
    candidates = [
        (timestamp, score)
        for timestamp, score in zip(timestamps_ms, quality_scores)
        if safe_start <= timestamp <= safe_end and score >= 0.5
    ]
    if not candidates:
        return None
    max_score = max(score for _, score in candidates)
    best = [timestamp for timestamp, score in candidates if score == max_score]
    rng = random.Random(seed)
    return rng.choice(best)
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_thumbnail_sampling.py -q
```

Expected:

- all sampling tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/managers/thumbnail_sampling.py tests/test_thumbnail_sampling.py
git commit -m "feat: add thumbnail sampling core"
```

## Task 2: Frame Quality Scoring And Sample Replacement

**Files:**

- Modify: `src/managers/thumbnail_sampling.py`
- Test: `tests/test_thumbnail_sampling.py`

- [ ] **Step 1: Add failing quality tests**

Append to `tests/test_thumbnail_sampling.py`:

```python
from src.managers.thumbnail_sampling import (
    choose_replacement_timestamp,
    frame_quality_score,
)


class ThumbnailQualityTest(unittest.TestCase):
    def test_black_frame_scores_low(self):
        score = frame_quality_score(brightness=2.0, contrast=1.0, blur=50.0, similarity=0.1)

        self.assertLess(score, 0.3)

    def test_clear_distinct_frame_scores_high(self):
        score = frame_quality_score(brightness=120.0, contrast=45.0, blur=180.0, similarity=0.25)

        self.assertGreater(score, 0.7)

    def test_replacement_stays_near_original_time(self):
        replacement = choose_replacement_timestamp(
            original_ms=10000,
            duration_ms=60000,
            attempt_index=1,
        )

        self.assertTrue(7000 <= replacement <= 13000)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_thumbnail_sampling.py -q
```

Expected:

- fails because quality helpers do not exist.

- [ ] **Step 3: Implement deterministic quality helpers**

Add to `src/managers/thumbnail_sampling.py`:

```python
def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def frame_quality_score(
    brightness: float,
    contrast: float,
    blur: float,
    similarity: float,
) -> float:
    brightness_score = _clamp((brightness - 8.0) / 100.0)
    contrast_score = _clamp(contrast / 45.0)
    blur_score = _clamp(blur / 160.0)
    distinct_score = _clamp(1.0 - similarity)
    return round(
        brightness_score * 0.35
        + contrast_score * 0.25
        + blur_score * 0.20
        + distinct_score * 0.20,
        4,
    )


def choose_replacement_timestamp(
    original_ms: int,
    duration_ms: int,
    attempt_index: int,
) -> int:
    offsets = [1500, -1500, 3000, -3000, 5000, -5000]
    offset = offsets[attempt_index % len(offsets)]
    return max(0, min(duration_ms, original_ms + offset))
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_thumbnail_sampling.py -q
```

Expected:

- sampling and quality tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/managers/thumbnail_sampling.py tests/test_thumbnail_sampling.py
git commit -m "feat: score thumbnail frame quality"
```

## Task 3: Orientation-Capable Rail Widget With Hover

**Files:**

- Create: `src/ui/thumbnail_rail.py`
- Test: `tests/test_thumbnail_rail.py`

- [ ] **Step 1: Write failing widget model tests**

Create `tests/test_thumbnail_rail.py`:

```python
import unittest

from PyQt6.QtWidgets import QApplication

from src.ui.thumbnail_rail import (
    PreviewOrientation,
    ThumbnailCell,
    ThumbnailPreviewRailWidget,
)


app = QApplication.instance() or QApplication([])


class ThumbnailPreviewRailWidgetTest(unittest.TestCase):
    def test_widget_defaults_to_vertical_and_twelve_cells(self):
        widget = ThumbnailPreviewRailWidget()

        self.assertEqual(widget.orientation, PreviewOrientation.VERTICAL)
        self.assertEqual(widget.cell_count, 12)

    def test_set_cells_requires_twelve_cells(self):
        widget = ThumbnailPreviewRailWidget()
        cells = [
            ThumbnailCell(index=i, timestamp_ms=i * 1000, image_path=None, state="loading")
            for i in range(12)
        ]

        widget.set_cells(cells)

        self.assertEqual(len(widget.cells), 12)

    def test_orientation_can_switch_to_horizontal(self):
        widget = ThumbnailPreviewRailWidget()

        widget.set_orientation(PreviewOrientation.HORIZONTAL)

        self.assertEqual(widget.orientation, PreviewOrientation.HORIZONTAL)

    def test_click_signal_emits_timestamp(self):
        widget = ThumbnailPreviewRailWidget()
        cells = [
            ThumbnailCell(index=i, timestamp_ms=i * 1000, image_path=None, state="ready")
            for i in range(12)
        ]
        emitted = []
        widget.thumbnail_clicked.connect(emitted.append)

        widget.set_cells(cells)
        widget.activate_cell_for_test(3)

        self.assertEqual(emitted, [3000])
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_thumbnail_rail.py -q
```

Expected:

- import fails because `thumbnail_rail.py` does not exist.

- [ ] **Step 3: Implement minimal widget API**

Create `src/ui/thumbnail_rail.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget


class PreviewOrientation(str, Enum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"


@dataclass(frozen=True)
class ThumbnailCell:
    index: int
    timestamp_ms: int
    image_path: str | None
    state: str
    quality_score: float = 0.0
    is_current: bool = False
    highlight_count: int = 0


class ThumbnailPreviewRailWidget(QWidget):
    thumbnail_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cell_count = 12
        self.orientation = PreviewOrientation.VERTICAL
        self.cells: list[ThumbnailCell] = []
        self.hover_scale = 2.0

    def set_orientation(self, orientation: PreviewOrientation | str) -> None:
        self.orientation = PreviewOrientation(orientation)
        self.updateGeometry()
        self.update()

    def set_cells(self, cells: list[ThumbnailCell]) -> None:
        if len(cells) != self.cell_count:
            raise ValueError("Thumbnail rail requires exactly 12 cells.")
        self.cells = list(cells)
        self.update()

    def activate_cell_for_test(self, index: int) -> None:
        cell = self.cells[index]
        self.thumbnail_clicked.emit(cell.timestamp_ms)
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_thumbnail_rail.py -q
```

Expected:

- widget model tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/ui/thumbnail_rail.py tests/test_thumbnail_rail.py
git commit -m "feat: add thumbnail preview rail widget shell"
```

## Task 4: Cache Manifest And Manager

**Files:**

- Modify: `src/core/consts.py`
- Create: `src/managers/thumbnail_manager.py`
- Test: `tests/test_thumbnail_manager.py`

- [ ] **Step 1: Write failing manager tests**

Create `tests/test_thumbnail_manager.py`:

```python
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
        os.makedirs(self.index_dir, exist_ok=True)
        with open(consts.THUMBNAIL_MANIFEST_FILE, "w", encoding="utf-8") as file:
            json.dump({
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
            }, file)

        manager = ThumbnailTimelineManager()
        cells = manager.cached_cells(path)

        self.assertEqual(len(cells), 12)
        self.assertTrue(all(cell.state == "ready" for cell in cells))

    def test_changed_file_size_invalidates_cache(self):
        path = self.make_video()
        manager = ThumbnailTimelineManager()

        self.assertFalse(manager.is_manifest_record_valid(path, {"size": -1, "mtime_ns": 0}))
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_thumbnail_manager.py -q
```

Expected:

- fails because `ThumbnailTimelineManager` does not exist.

- [ ] **Step 3: Add constants**

Modify `src/core/consts.py`:

```python
THUMBNAIL_CACHE_DIR = os.path.join(USER_DATA_ROOT, "thumbnail_cache")
THUMBNAIL_MANIFEST_FILE = os.path.join(INDEX_DIR, "thumbnail_manifest.json")
```

- [ ] **Step 4: Implement manager cache API**

Create `src/managers/thumbnail_manager.py`:

```python
from __future__ import annotations

import json
import os

from src.core import consts
from src.ui.thumbnail_rail import ThumbnailCell


class ThumbnailTimelineManager:
    def __init__(self):
        self.manifest_path = consts.THUMBNAIL_MANIFEST_FILE
        self.cache_dir = consts.THUMBNAIL_CACHE_DIR
        self.manifest = self._load_manifest()

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

    def is_manifest_record_valid(self, path: str, record: dict) -> bool:
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
```

- [ ] **Step 5: Run tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_thumbnail_manager.py -q
```

Expected:

- manager cache tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/core/consts.py src/managers/thumbnail_manager.py tests/test_thumbnail_manager.py
git commit -m "feat: add thumbnail cache manager"
```

## Task 5: UI Layout Integration Without Covering Video

**Files:**

- Modify: `src/ui/ui_layout.py`
- Modify: `main.py`
- Test: `tests/test_video_sorter.py`

- [ ] **Step 1: Add failing layout/coordinator tests**

Add to `tests/test_video_sorter.py`:

```python
def test_thumbnail_seek_routes_through_guarded_seek():
    class FakeWindow:
        def __init__(self):
            self.seek_calls = []

        def _execute_seek_and_play(self, timestamp):
            self.seek_calls.append(timestamp)

    window = FakeWindow()

    VideoSorter.seek_to_thumbnail(window, 42000)

    assert window.seek_calls == [42000]
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_video_sorter.py::test_thumbnail_seek_routes_through_guarded_seek -q
```

Expected:

- fails because `seek_to_thumbnail` does not exist.

- [ ] **Step 3: Add rail to right panel layout**

Modify `src/ui/ui_layout.py`:

```python
from .thumbnail_rail import ThumbnailPreviewRailWidget
```

Replace the direct video add with a player row:

```python
player_row = QHBoxLayout()
player_row.setContentsMargins(0, 0, 0, 0)
player_row.setSpacing(5)

window.video_view = ProVideoView()
window.thumbnail_rail = ThumbnailPreviewRailWidget()
window.thumbnail_rail.setFixedWidth(105)

player_row.addWidget(window.video_view, 1)
player_row.addWidget(window.thumbnail_rail, 0)
right_layout.addLayout(player_row, 1)
```

Do not add the rail to `window.video_view.scene`.

- [ ] **Step 4: Add seek coordinator**

Add to `main.py`:

```python
def seek_to_thumbnail(self, timestamp_ms: int) -> None:
    self._execute_seek_and_play(int(timestamp_ms))
```

- [ ] **Step 5: Wire signal**

Modify `src/core/signal_setup.py`:

```python
if hasattr(window, "thumbnail_rail"):
    window.thumbnail_rail.thumbnail_clicked.connect(window.seek_to_thumbnail)
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_video_sorter.py::test_thumbnail_seek_routes_through_guarded_seek tests/test_thumbnail_rail.py -q
```

Expected:

- coordinator and widget tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add main.py src/ui/ui_layout.py src/core/signal_setup.py tests/test_video_sorter.py
git commit -m "feat: place thumbnail rail beside video"
```

## Task 6: Position And Highlight Markers

**Files:**

- Modify: `src/ui/thumbnail_rail.py`
- Modify: `main.py`
- Test: `tests/test_thumbnail_rail.py`

- [ ] **Step 1: Add failing marker tests**

Append to `tests/test_thumbnail_rail.py`:

```python
class ThumbnailMarkerTest(unittest.TestCase):
    def test_playback_position_marks_nearest_cell(self):
        widget = ThumbnailPreviewRailWidget()
        widget.set_cells([
            ThumbnailCell(index=i, timestamp_ms=i * 1000, image_path=None, state="ready")
            for i in range(12)
        ])

        widget.set_playback_position(3400)

        self.assertEqual(widget.current_cell_index, 3)

    def test_highlight_markers_count_nearest_cells(self):
        widget = ThumbnailPreviewRailWidget()
        widget.set_cells([
            ThumbnailCell(index=i, timestamp_ms=i * 1000, image_path=None, state="ready")
            for i in range(12)
        ])

        widget.set_highlights([3100, 3200])

        self.assertEqual(widget.highlight_counts[3], 2)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_thumbnail_rail.py -q
```

Expected:

- fails because marker methods do not exist.

- [ ] **Step 3: Implement marker methods**

Add to `ThumbnailPreviewRailWidget`:

```python
def _nearest_cell_index(self, timestamp_ms: int) -> int | None:
    if not self.cells:
        return None
    distances = [
        (abs(cell.timestamp_ms - timestamp_ms), cell.index)
        for cell in self.cells
    ]
    return min(distances)[1]

def set_playback_position(self, timestamp_ms: int) -> None:
    self.current_cell_index = self._nearest_cell_index(timestamp_ms)
    self.update()

def set_highlights(self, timestamps_ms: list[int]) -> None:
    counts = {index: 0 for index in range(self.cell_count)}
    for timestamp in timestamps_ms:
        index = self._nearest_cell_index(timestamp)
        if index is not None:
            counts[index] += 1
    self.highlight_counts = counts
    self.update()
```

Initialize in `__init__`:

```python
self.current_cell_index = None
self.highlight_counts = {index: 0 for index in range(self.cell_count)}
```

- [ ] **Step 4: Forward position and highlights from `VideoSorter`**

In `on_position_changed(...)`, after updating the progress bar:

```python
if hasattr(self, "thumbnail_rail"):
    self.thumbnail_rail.set_playback_position(position)
```

When active path changes, derive highlight times:

```python
def _highlight_times_for_path(self, path: str) -> list[int]:
    key = self.file_manager._get_norm_key(path)
    values = self.file_manager.highlights.get(key, [])
    return [int(value) for value in values if isinstance(value, (int, float))]
```

Then pass them after timeline cells are set.

- [ ] **Step 5: Run tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_thumbnail_rail.py -q
```

Expected:

- marker tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add main.py src/ui/thumbnail_rail.py tests/test_thumbnail_rail.py
git commit -m "feat: mark thumbnail playback and highlights"
```

## Task 7: Background Extraction Worker

**Files:**

- Modify: `requirements.txt`
- Create: `src/core/thumbnail_threads.py`
- Modify: `src/managers/thumbnail_manager.py`
- Test: `tests/test_thumbnail_manager.py`

- [ ] **Step 1: Add dependency entries**

Modify `requirements.txt`:

```text
av
Pillow
```

Pin exact versions only after verifying installation in the project environment.

- [ ] **Step 2: Add worker interface tests**

Append to `tests/test_thumbnail_manager.py`:

```python
def test_request_timeline_queues_only_requested_path():
    path = self.make_video()
    manager = ThumbnailTimelineManager()

    manager.request_timeline(path, duration_ms=120000, priority="active")

    self.assertEqual([job.path for job in manager.pending_jobs], [path])
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_thumbnail_manager.py -q
```

Expected:

- fails because request queue API is not implemented.

- [ ] **Step 4: Implement bounded request queue**

Add a simple job dataclass and queue to `thumbnail_manager.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ThumbnailJob:
    path: str
    duration_ms: int | None
    priority: str


def request_timeline(self, path: str, duration_ms: int | None = None, priority: str = "active") -> None:
    if self.cached_cells(path):
        return
    job = ThumbnailJob(path=path, duration_ms=duration_ms, priority=priority)
    self.pending_jobs = [existing for existing in getattr(self, "pending_jobs", []) if existing.path != path]
    self.pending_jobs.insert(0 if priority == "active" else len(self.pending_jobs), job)
    self.pending_jobs = self.pending_jobs[:6]
```

Initialize:

```python
self.pending_jobs = []
```

- [ ] **Step 5: Add worker shell**

Create `src/core/thumbnail_threads.py`:

```python
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal


class ThumbnailWorker(QThread):
    finished_path = pyqtSignal(str, list)
    failed_path = pyqtSignal(str, str)

    def __init__(self, path: str, timestamps_ms: list[int], output_dir: str):
        super().__init__()
        self.path = path
        self.timestamps_ms = timestamps_ms
        self.output_dir = output_dir

    def run(self):
        try:
            self.finished_path.emit(self.path, [])
        except Exception as exc:
            self.failed_path.emit(self.path, str(exc))
```

Real PyAV extraction should replace the shell in the same file in a later step of this task, keeping the same signals.

- [ ] **Step 6: Run tests and verify pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_thumbnail_manager.py -q
```

Expected:

- manager request queue tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add requirements.txt src/core/thumbnail_threads.py src/managers/thumbnail_manager.py tests/test_thumbnail_manager.py
git commit -m "feat: queue thumbnail extraction work"
```

## Task 8: Thumbnail-Assisted Random Start

**Files:**

- Modify: `src/managers/thumbnail_manager.py`
- Modify: `main.py`
- Test: `tests/test_video_sorter.py`

- [ ] **Step 1: Add failing random-start coordinator test**

Add to `tests/test_video_sorter.py`:

```python
def test_random_start_uses_thumbnail_candidate_when_available():
    class FakeManager:
        def best_random_start(self, path, duration_ms):
            return 12345

    class FakePlayer:
        def duration(self):
            return 90000

    class FakeWindow:
        thumbnail_manager = FakeManager()
        player = FakePlayer()

    result = VideoSorter._thumbnail_random_start_candidate(FakeWindow(), "C:/videos/a.mp4")

    assert result == 12345
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_video_sorter.py::test_random_start_uses_thumbnail_candidate_when_available -q
```

Expected:

- fails because helper does not exist.

- [ ] **Step 3: Implement manager candidate API**

Add to `ThumbnailTimelineManager`:

```python
def best_random_start(self, path: str, duration_ms: int) -> int | None:
    record = self.manifest.get(self._path_key(path), {})
    if not self.is_manifest_record_valid(path, record):
        return None
    from src.managers.thumbnail_sampling import choose_random_start_candidate

    return choose_random_start_candidate(
        list(record.get("timestamps_ms", [])),
        list(record.get("quality_scores", [])),
        duration_ms=duration_ms,
    )
```

- [ ] **Step 4: Add `VideoSorter` helper**

Add to `main.py`:

```python
def _thumbnail_random_start_candidate(self, path: str) -> int | None:
    manager = getattr(self, "thumbnail_manager", None)
    if manager is None:
        return None
    duration = self.player.duration()
    if duration <= 0:
        return None
    return manager.best_random_start(path, duration)
```

Use it in `_handle_immediate_seek(...)` and `on_media_status_changed(...)` before raw random fallback:

```python
candidate = self._thumbnail_random_start_candidate(active_slot.expected_path if active_slot else "")
if candidate is not None:
    self._execute_seek_and_play(candidate)
else:
    self._execute_seek_and_play(rand_pos)
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_video_sorter.py::test_random_start_uses_thumbnail_candidate_when_available tests/test_thumbnail_sampling.py tests/test_thumbnail_manager.py -q
```

Expected:

- random-start tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add main.py src/managers/thumbnail_manager.py tests/test_video_sorter.py
git commit -m "feat: use thumbnail candidates for random start"
```

## Task 9: Player Boundary And Privacy Guards

**Files:**

- Modify: `tests/test_cleanup_static.py`
- Modify: `src/ui/thumbnail_rail.py`
- Modify: `main.py`

- [ ] **Step 1: Add static boundary test**

Append to `tests/test_cleanup_static.py`:

```python
def test_thumbnail_subsystem_does_not_load_qmediaplayer_sources(self):
    forbidden = "setSource("
    for path in [
        Path("src/managers/thumbnail_manager.py"),
        Path("src/core/thumbnail_threads.py"),
        Path("src/ui/thumbnail_rail.py"),
    ]:
        source = path.read_text(encoding="utf-8")
        assert forbidden not in source
```

- [ ] **Step 2: Run static test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cleanup_static.py::test_thumbnail_subsystem_does_not_load_qmediaplayer_sources -q
```

Expected:

- static boundary test passes.

- [ ] **Step 3: Add privacy rail API**

Add to `ThumbnailPreviewRailWidget`:

```python
def set_privacy_hidden(self, hidden: bool) -> None:
    self.privacy_hidden = bool(hidden)
    self.update()
```

Initialize:

```python
self.privacy_hidden = False
```

In paint/render logic, draw neutral cells when `privacy_hidden` is true.

- [ ] **Step 4: Wire privacy state**

In `VideoSorter._apply_privacy_visibility(...)`, add:

```python
if hasattr(self, "thumbnail_rail"):
    self.thumbnail_rail.set_privacy_hidden(privacy_active)
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cleanup_static.py tests/test_thumbnail_rail.py -q
```

Expected:

- static boundary and rail tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add main.py src/ui/thumbnail_rail.py tests/test_cleanup_static.py
git commit -m "feat: guard thumbnail privacy and player boundary"
```

## Task 10: Full Verification

**Files:**

- Modify only if verification finds a concrete defect.

- [ ] **Step 1: Run focused thumbnail tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_thumbnail_sampling.py tests/test_thumbnail_manager.py tests/test_thumbnail_rail.py tests/test_video_sorter.py tests/test_cleanup_static.py -q
```

Expected:

- all focused tests pass.

- [ ] **Step 2: Run project checks**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_checks.ps1
```

Expected:

- full test suite passes;
- cleanup static guards pass;
- no diff check failure appears.

- [ ] **Step 3: Run continuity smoke**

Run:

```powershell
.\.venv\Scripts\python.exe .\tools\smoke_player_continuity.py
```

Expected:

- playback continues across A/B, highlight, trash, search, and non-active actions.

- [ ] **Step 4: Manual UI smoke**

Run:

```powershell
.\.venv\Scripts\python.exe main.py
```

Manual expected results:

- video remains 16:9;
- right rail shows exactly 12 cells;
- hover shows 200% preview without moving layout;
- click seeks through the guarded seek path;
- current position marker follows playback;
- highlight marker appears after saving a highlight;
- random position playback does not wait for thumbnails;
- privacy pause hides thumbnails and hover preview;
- A/B, highlight, trash, search, and passive menu continuity still work.

- [ ] **Step 5: Commit final fixes if needed**

If verification required corrections:

```powershell
git add main.py src tests docs requirements.txt
git commit -m "fix: harden thumbnail preview rail"
```

## Self-Review

Spec coverage:

- exact 12 cells are covered by Tasks 1, 3, and 4;
- smarter sampling is covered by Tasks 1 and 2;
- current position and highlight markers are covered by Task 6;
- click-to-seek without Shift-click is covered by Task 5;
- priority lazy generation is covered by Tasks 4 and 7;
- thumbnail-assisted random start is covered by Task 8;
- future horizontal rail support is covered by Task 3;
- privacy and `PlayerEngine` boundary protection are covered by Task 9.

Placeholder scan:

- this plan contains concrete files, tests, commands, expected outcomes, and commit points.

Type consistency:

- `ThumbnailCell` uses `timestamp_ms`, `image_path`, `state`, `quality_score`, `is_current`, and `highlight_count`;
- orientation values are `vertical` and `horizontal`;
- manager API names match the design: `request_timeline(...)`, `cached_cells(...)`, `best_random_start(...)`, and `shutdown()`.

## Execution Choice

Recommended execution is subagent-driven. The plan naturally splits into independent tasks: sampling, widget shell, cache manager, worker, UI integration, markers, random start, and static guards.
