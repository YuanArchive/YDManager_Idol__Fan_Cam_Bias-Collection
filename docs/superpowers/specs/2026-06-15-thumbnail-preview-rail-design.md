# Thumbnail Preview Rail Design

Date: 2026-06-15

## Purpose

YDManager's core value is fast video exploration with minimal waiting. The thumbnail preview feature must help the user understand a video quickly without covering the active 16:9 player, slowing playback, or bypassing `PlayerEngine`.

The feature is a right-side vertical preview rail:

- about 12 16:9 thumbnails for the active or selected video;
- placed to the far right of the player area as a sibling widget, not as an overlay;
- clicking a thumbnail seeks the active video to that timestamp;
- missing thumbnails show a lightweight generating state while playback continues;
- thumbnail extraction runs lazily in the background and never blocks video activation.

## Product Principles

The rail is not a media browser, gallery, or editor. It is a compact visual index for fast judgment.

The user should be able to:

1. keep using arrow-key video exploration as the primary flow;
2. glance at the rail to understand the video's rough contents;
3. click a representative frame to jump to that section;
4. ignore the rail completely when thumbnails are not ready.

## Non-Goals

- Do not convert the file list into thumbnail cards.
- Do not add a large bottom strip that covers or shrinks the video vertically.
- Do not generate thumbnails for all indexed videos immediately.
- Do not use `QMediaPlayer` or hidden media-player slots for thumbnail extraction.
- Do not let thumbnail extraction compete with `PlayerEngine` preloading.
- Do not write cache files beside source videos.
- Do not add AI classification, face detection, or automatic tagging in this phase.

## UI Layout

The current right panel contains:

```text
ProVideoView
bottom action buttons
```

The new layout should be:

```text
right panel
  player row
    ProVideoView
    ThumbnailRailWidget
  bottom action buttons
```

`ThumbnailRailWidget` is a sibling of `ProVideoView`. It must not be added as an item inside `ProVideoView.scene`.

### Default Size Model

The app should keep the video area at a stable 16:9 target and add rail width separately.

Recommended sizing rules:

- left panel target width: current app value, about 230 px;
- video target: exact 16:9, preferably 1280 x 720 at default size;
- rail target width: computed from available video height and 12 rows;
- total default width: left panel + video width + rail width + margins;
- total default height: video height + bottom controls + margins.

For a 720 px tall video area, 12 single-column 16:9 thumbnails must be compact:

```text
available height ~= 720 px
gaps ~= 11 * 5 px = 55 px
thumbnail height ~= floor((720 - 55) / 12) = 55 px
thumbnail width ~= floor(55 * 16 / 9) = 97 px
```

The rail should therefore compute thumbnail cell size from height, not hard-code a large width. On taller windows the thumbnails can grow. On smaller windows the rail can scroll, but the default fit should show all 12 without scrolling.

### Visual States

Each thumbnail cell has one of these states:

- `empty`: no active or selected video;
- `loading`: timestamp known, image not generated yet;
- `ready`: image available and clickable;
- `failed`: extraction failed for this timestamp;
- `active_time`: current playback position is near this timestamp.

The rail should be visually restrained:

- no permanent large labels;
- no decorative cards;
- no animation except subtle state changes;
- one small status line at the top or bottom: `Generating 4/12`, `Cached`, or `Unavailable`;
- cells use 16:9 ratio and stable dimensions so the layout does not shift while images arrive.

## Interaction

### Active Video Change

When `VideoSorter.play_video(index, ...)` activates a video:

1. playback continues through `PlayerEngine.activate(...)`;
2. neighbor preloading continues through `PlayerEngine.plan_neighbors(...)`;
3. `VideoSorter` requests thumbnails for the active path from `ThumbnailTimelineManager`;
4. the rail immediately shows placeholders or cached thumbnails;
5. background extraction fills missing thumbnails asynchronously.

Thumbnail work must never be awaited inside `play_video()`.

### Selected Row Change

The rail may update for the selected row when selection changes without explicit playback, but this must be passive:

- do not call `play_video()`;
- do not call `PlayerEngine.activate(...)`;
- do not affect the active watch session;
- queue thumbnail generation with lower priority than the active playing video.

This gives the user a preview while arrowing through the list, but playback remains governed by existing activation behavior.

### Thumbnail Click

Clicking a ready thumbnail emits a timestamp in milliseconds.

`VideoSorter` should route the click through the same guarded seek path used by highlight replay:

```python
VideoSorter.seek_to_thumbnail(timestamp_ms)
VideoSorter._execute_seek_and_play(timestamp_ms)
```

The click handler must not call `player.setPosition(...)` directly because `_execute_seek_and_play(...)` already manages waiting state, fallback reveal, autoplay, and autoscan timer state.

### Current Position Highlight

When `on_position_changed(position)` updates the progress bar, it can also notify the rail:

```python
thumbnail_rail.set_playback_position(position)
```

The rail highlights the nearest timestamp. This is only visual. It must not trigger generation or seek.

## Architecture

### `ThumbnailRailWidget`

Location:

```text
src/ui/thumbnail_rail.py
```

Responsibility:

- render 12 stable 16:9 cells vertically;
- show loading, ready, failed, and active-time states;
- expose `thumbnail_clicked = pyqtSignal(int)`;
- accept a timeline model from the coordinator;
- never inspect files, decode videos, or touch `QMediaPlayer`.

Suggested model objects:

```python
@dataclass(frozen=True)
class ThumbnailCell:
    timestamp_ms: int
    image_path: str | None
    state: str
```

### `ThumbnailTimelineManager`

Location:

```text
src/managers/thumbnail_manager.py
```

Responsibility:

- normalize paths consistently with `FileManager`;
- check cache manifest;
- decide whether a timeline is cached, stale, queued, or generating;
- create bounded background jobs;
- emit timeline updates to the UI;
- ignore stale worker results when the user has moved on.

Public API:

```python
request_timeline(path: str, duration_ms: int | None = None, priority: str = "active") -> None
cancel_path(path: str) -> None
invalidate(path: str) -> None
shutdown() -> None
```

Signals:

```python
timeline_started(path: str, total: int)
timeline_updated(path: str, cells: list[ThumbnailCell])
timeline_finished(path: str, cells: list[ThumbnailCell])
timeline_failed(path: str, reason: str)
```

### `ThumbnailWorker`

Location:

```text
src/core/thumbnail_threads.py
```

Responsibility:

- extract frames off the GUI thread;
- emit small batches or one completed result;
- avoid touching Qt widgets;
- stop when interrupted;
- report decode failures without crashing the app.

The worker should output image files into the app cache and pass file paths back to the GUI. If `QImage` is used across signals, conversion to `QPixmap` must happen on the GUI thread.

### `VideoSorter`

`VideoSorter` remains the coordinator:

- creates the rail widget and thumbnail manager;
- requests timelines when active or selected video changes;
- forwards thumbnail timeline updates to the rail;
- forwards thumbnail clicks to `_execute_seek_and_play(timestamp_ms)`;
- shuts down thumbnail workers in `closeEvent`.

It must not contain frame extraction code.

## Cache Design

The cache belongs under the app data root, not source folders.

Recommended constants:

```text
THUMBNAIL_CACHE_DIR = os.path.join(USER_DATA_ROOT, "thumbnail_cache")
THUMBNAIL_MANIFEST_FILE = os.path.join(INDEX_DIR, "thumbnail_manifest.json")
```

Manifest entry shape:

```json
{
  "normalized-path-key": {
    "path": "C:\\videos\\sample.mp4",
    "size": 123456789,
    "mtime_ns": 1780000000000000000,
    "duration_ms": 240000,
    "thumb_count": 12,
    "cache_id": "sha256-prefix",
    "timestamps_ms": [0, 21818, 43636],
    "files": ["000.jpg", "001.jpg", "002.jpg"],
    "created_at": "2026-06-15T12:00:00+09:00"
  }
}
```

Invalidation rule:

- if path key is missing, generate;
- if file is missing, report unavailable and do not retry aggressively;
- if size or `mtime_ns` differs, mark stale and regenerate;
- if any thumbnail file is missing, regenerate only the missing timeline folder or the full small set;
- if extraction fails, store a short failure record to avoid immediate tight retry loops.

### Storage Size

Small JPEG thumbnails are acceptable because the rail shows compact images. For 12 thumbnails per video:

- 100 x 56 to 160 x 90 px is enough for visual recognition;
- expected JPEG size can stay small;
- thousands of videos should remain manageable if generation is lazy and cache cleanup exists.

Cache cleanup should be deferred until after v1 unless disk usage becomes measurable. The v1 manager should still keep all thumbnails under one known cache root so cleanup can be added safely.

## Scheduling For Thousands Of Videos

Thumbnail generation must be priority-based and bounded.

Priority order:

1. active playing video;
2. selected visible candidate row;
3. immediate next/previous visible candidates;
4. idle background fill for visible list only;
5. full-library fill is deferred.

The first implementation should process one extraction job at a time. That is slower in raw throughput, but safer for playback smoothness.

Rules:

- do not scan all indexed videos just because a folder is opened;
- do not hash or stat thousands of files synchronously on the GUI thread;
- do not queue more than a small bounded number of jobs;
- clear or deprioritize old selected-row jobs when the user moves rapidly;
- keep active video extraction ahead of all other requests;
- persist manifest updates in batches or at job completion, not per cell.

## Extraction Strategy

Preferred extraction package:

- `PyAV` for direct frame extraction through FFmpeg bindings;
- `Pillow` for resizing and saving thumbnail images.

Fallback or prototype option:

- `imageio` can be considered for a simpler prototype, but the production path should favor deterministic extraction and explicit timestamp control.

OpenCV is not required for v1. It becomes useful later for near-duplicate detection, scene analysis, or visual similarity workflows.

Timestamp sampling:

- use 12 samples for normal videos;
- avoid the first and last 3-5 percent when duration is known so thumbnails do not overrepresent black intro/outro frames;
- if duration is unknown, use conservative fixed timestamps after probing;
- for very short clips, allow fewer unique timestamps and duplicate no frames.

Recommended sampling formula when duration is known:

```text
safe_start = duration_ms * 0.05
safe_end = duration_ms * 0.95
interval = (safe_end - safe_start) / 11
timestamp[i] = safe_start + interval * i
```

## PlayerEngine Boundary

Thumbnail extraction is not playback preload.

The only code paths that may load video into `QMediaPlayer` for playback remain:

- `PlayerEngine.activate(...)`;
- `PlayerEngine.plan_neighbors(...)`.

Thumbnail extraction must not:

- call `QMediaPlayer.setSource(...)`;
- create hidden `QMediaPlayer` instances;
- mutate player slots;
- clear active/preload slots;
- change `watch_session`;
- force `play_video(...)`.

This boundary keeps the v2/v3/v4 player-engine guarantees intact.

## Privacy And Safety

If privacy mode hides video while paused, the rail must also hide generated thumbnails or show neutral placeholders. The rail should follow the same visibility decision as the main player surface.

Rules:

- when privacy screen is active, do not display source frame thumbnails;
- do not write source path names into visible rail labels;
- do not log full paths when privacy logging is enabled;
- thumbnail cache can still exist on disk because it is app-managed local data, but cache cleanup should be available later.

## Failure Handling

Thumbnail failure must be non-fatal:

- unsupported codec: show `Unavailable`;
- file missing: show `Missing`;
- worker interrupted: ignore result and keep current rail state;
- late result for stale path: ignore by path + request generation token;
- corrupt image file: delete stale thumbnail and mark generation needed;
- cache manifest malformed: skip bad records and continue.

Failures should never show a modal dialog during exploration.

## Testing

### Unit Tests

- `ThumbnailTimelineManager` loads valid manifest entries.
- Malformed manifest records are skipped.
- Cache hit returns 12 ready cells without starting a worker.
- Changed file size invalidates the cached timeline.
- Changed mtime invalidates the cached timeline.
- Missing thumbnail file invalidates or regenerates the affected timeline.
- Requesting one path queues only that path, not every indexed video.
- Late worker results for an older request token are ignored.
- Shutdown interrupts the worker.

### UI Tests

- The right panel contains `ProVideoView` and `ThumbnailRailWidget` as siblings.
- The rail is not added to `video_view.scene`.
- Default sizing keeps `video_view` at 16:9 within tolerance while the rail consumes separate width.
- The rail shows 12 stable cells without shifting layout as images arrive.
- A ready cell click emits its timestamp.
- `VideoSorter.seek_to_thumbnail(ms)` calls `_execute_seek_and_play(ms)`.
- The click path does not call `player.setPosition(...)` directly.

### Player Boundary Tests

- Thumbnail manager code does not call `PlayerEngine.activate(...)`.
- Thumbnail manager code does not call `PlayerEngine.plan_neighbors(...)`.
- Thumbnail manager code does not call `QMediaPlayer.setSource(...)`.
- Existing preload and continuity smoke tests still pass.

### Manual Smoke

1. Open a folder with multiple videos.
2. Play a video and confirm playback starts with current preload behavior.
3. Confirm the rail shows placeholders immediately and cached/generated thumbnails later.
4. Click a thumbnail and confirm playback seeks smoothly to that region.
5. Enable autoscan and confirm thumbnail clicks do not break the scan timer behavior.
6. Toggle A/B, highlight, trash, and search views and confirm active playback continues.
7. Enable privacy mode, pause, and confirm thumbnails are hidden or neutral.
8. Rapidly move across videos and confirm late thumbnails do not appear for the wrong video.

## Rollout

### Phase 1: Passive UI Shell

Add the rail widget and default layout sizing with placeholder cells only. No extraction.

### Phase 2: Cache Manifest And Manager

Add manifest loading, cache-hit display, invalidation rules, and worker stubs.

### Phase 3: Background Extraction

Add real extraction with PyAV + Pillow, bounded queueing, and stale-result guards.

### Phase 4: Click-To-Seek

Route thumbnail clicks through `_execute_seek_and_play(...)` and verify autoscan/fallback behavior.

### Phase 5: Performance And Privacy Hardening

Add privacy hiding, large-library smoke, and tests protecting the `PlayerEngine` boundary.

## Acceptance Standard

The feature is acceptable when:

- active video playback remains the fastest path;
- the video area stays 16:9 and is not covered by thumbnails;
- 12 compact thumbnails appear on the far right when cached or generated;
- clicking a thumbnail seeks accurately;
- generating thumbnails for thousands of videos is lazy and bounded;
- missing or failed thumbnails do not interrupt playback;
- all existing player continuity and preload tests still pass.
