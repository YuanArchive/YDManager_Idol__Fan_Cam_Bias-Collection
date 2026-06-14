# Thumbnail Preview Rail Design

Date: 2026-06-15

## Purpose

YDManager's core value is fast video exploration with minimal waiting. The thumbnail preview feature must help the user understand a video quickly without covering the active 16:9 player, slowing playback, or bypassing `PlayerEngine`.

The default feature is a right-side vertical preview rail:

- exactly 12 16:9 thumbnails for every active or selected video;
- placed to the far right of the player area as a sibling widget, not as an overlay;
- click a thumbnail to seek the active video to that timestamp;
- hover a thumbnail to show a 200% enlarged preview;
- show current playback position and saved highlight markers on the rail;
- use smarter sampling to avoid black, near-duplicate, or low-information frames where possible;
- use thumbnail metadata to improve random-start selection later;
- generate thumbnails lazily in the background while playback continues.

The layout must also be future-proofed for a horizontal rail. The first build uses a vertical rail because it does not cover the video, but the widget and data model should support `orientation="vertical"` and `orientation="horizontal"` without rewriting the thumbnail engine.

## Product Principles

The rail is not a media browser, gallery, or editor. It is a compact visual index for fast judgment.

The user should be able to:

1. keep using arrow-key video exploration as the primary flow;
2. glance at 12 consistent thumbnails to understand the video's rough contents;
3. hover one thumbnail for a larger 200% preview without committing a seek;
4. click one thumbnail to jump to that section;
5. see where current playback and saved highlights sit within the sampled timeline;
6. ignore the rail completely when thumbnails are not ready.

## Non-Goals

- Do not convert the file list into thumbnail cards.
- Do not add a large bottom strip that covers or shrinks the video vertically in the first build.
- Do not generate thumbnails for all indexed videos immediately.
- Do not use `QMediaPlayer` or hidden media-player slots for thumbnail extraction.
- Do not let thumbnail extraction compete with `PlayerEngine` preloading.
- Do not write cache files beside source videos.
- Do not add Shift-click or other modifier-click actions in v1.
- Do not add AI classification, face detection, or automatic tagging in this phase.

## UI Layout

The current right panel contains:

```text
ProVideoView
bottom action buttons
```

The new default layout should be:

```text
right panel
  player row
    ProVideoView
    ThumbnailPreviewRailWidget(orientation="vertical")
  bottom action buttons
```

`ThumbnailPreviewRailWidget` is a sibling of `ProVideoView`. It must not be added as an item inside `ProVideoView.scene`.

### Orientation Model

The widget should be orientation-capable from the start:

```python
class PreviewOrientation(str, Enum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
```

Default:

- `vertical`: far right of the player area;
- all 12 thumbnails in one column;
- hover preview opens beside or over the rail, not over the video unless there is no safe space.

Future:

- `horizontal`: above or below the video area;
- all 12 thumbnails in one row or a scrollable row;
- the same timeline data, cache, click-to-seek, hover zoom, markers, and sampling logic must work unchanged.

This means thumbnail generation, timestamp sampling, cache metadata, and click behavior must not assume vertical placement.

### Default Size Model

The app should keep the video area at a stable 16:9 target and add rail width separately.

Recommended sizing rules:

- left panel target width: current app value, about 230 px;
- video target: exact 16:9, preferably 1280 x 720 at default size;
- rail target width: computed from available video height and exactly 12 rows;
- total default width: left panel + video width + rail width + margins;
- total default height: video height + bottom controls + margins.

For a 720 px tall video area, 12 single-column 16:9 thumbnails must be compact:

```text
available height ~= 720 px
gaps ~= 11 * 5 px = 55 px
thumbnail height ~= floor((720 - 55) / 12) = 55 px
thumbnail width ~= floor(55 * 16 / 9) = 97 px
hover preview ~= 194 x 110 px
```

The rail should compute thumbnail cell size from height in vertical mode and from width in horizontal mode. On smaller windows the rail may scroll, but the default target should show all 12 without scrolling.

### Hover Preview

Hovering a ready thumbnail shows a 200% enlarged preview.

Rules:

- hover preview is read-only;
- hover does not seek;
- hover does not pause playback;
- hover should appear after a short delay, about 120-180 ms, to avoid flicker during mouse movement;
- hover hides immediately when the pointer leaves the cell or rail;
- the enlarged preview must not change layout dimensions;
- prefer drawing the preview outside the video surface;
- if the rail has no safe outside space, the preview may overlap the rail itself before overlapping video.

The hover preview should show:

- enlarged frame;
- timestamp text such as `01:24`;
- optional small markers for `current` or `highlight` if applicable.

### Visual States

Each thumbnail cell has one of these states:

- `empty`: no active or selected video;
- `loading`: timestamp known, image not generated yet;
- `ready`: image available and clickable;
- `failed`: extraction failed for this timestamp;
- `active_time`: current playback position is near this timestamp;
- `highlight`: the cell is nearest to one or more saved highlight timestamps.

The rail should be visually restrained:

- no permanent large labels;
- no decorative cards;
- no animation except subtle hover and state changes;
- one small status line at the top or bottom: `Generating 4/12`, `Cached`, or `Unavailable`;
- cells use 16:9 ratio and stable dimensions so the layout does not shift while images arrive;
- current position marker is a thin border or side bar;
- highlight marker is a small dot or thin line, not a large badge.

## Interaction

### Active Video Change

When `VideoSorter.play_video(index, ...)` activates a video:

1. playback continues through `PlayerEngine.activate(...)`;
2. neighbor preloading continues through `PlayerEngine.plan_neighbors(...)`;
3. `VideoSorter` requests thumbnails for the active path from `ThumbnailTimelineManager`;
4. the rail immediately shows pending cells or cached thumbnails;
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

Modifier clicks are intentionally unassigned in v1. In particular, Shift-click does not add highlights.

### Current Position Highlight

When `on_position_changed(position)` updates the progress bar, it can also notify the rail:

```python
thumbnail_rail.set_playback_position(position)
```

The rail highlights the nearest timestamp. This is only visual. It must not trigger generation or seek.

### Highlight Markers

Saved highlights should appear on the rail as small markers.

Rules:

- marker data is derived from `FileManager.highlights`;
- no duplicate storage in the thumbnail manifest;
- if multiple highlights map to the same thumbnail cell, show one marker with a subtle count only if needed;
- clicking the thumbnail still seeks to the thumbnail timestamp, not necessarily the exact highlight timestamp;
- exact highlight replay remains handled by the highlight mode.

## Architecture

### `ThumbnailPreviewRailWidget`

Location:

```text
src/ui/thumbnail_rail.py
```

Responsibility:

- render exactly 12 stable 16:9 cells;
- support vertical and horizontal orientation;
- show loading, ready, failed, active-time, and highlight marker states;
- show a 200% hover preview without changing layout;
- expose `thumbnail_clicked = pyqtSignal(int)`;
- accept a timeline model from the coordinator;
- never inspect files, decode videos, or touch `QMediaPlayer`.

Suggested model objects:

```python
@dataclass(frozen=True)
class ThumbnailCell:
    index: int
    timestamp_ms: int
    image_path: str | None
    state: str
    quality_score: float = 0.0
    is_current: bool = False
    highlight_count: int = 0
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
- compute exactly 12 candidate timestamps;
- apply scene-quality filtering to avoid low-information frames;
- create bounded background jobs;
- emit timeline updates to the UI;
- expose best random-start candidates for later use;
- ignore stale worker results when the user has moved on.

Public API:

```python
request_timeline(path: str, duration_ms: int | None = None, priority: str = "active") -> None
cancel_path(path: str) -> None
invalidate(path: str) -> None
best_random_start(path: str, duration_ms: int) -> int | None
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
- evaluate basic frame quality;
- emit exactly 12 final cells;
- avoid touching Qt widgets;
- stop when interrupted;
- report decode failures without crashing the app.

The worker should output image files into the app cache and pass file paths back to the GUI. If `QImage` is used across signals, conversion to `QPixmap` must happen on the GUI thread.

### `VideoSorter`

`VideoSorter` remains the coordinator:

- creates the rail widget and thumbnail manager;
- requests timelines when active or selected video changes;
- forwards thumbnail timeline updates to the rail;
- forwards playback position and highlight timestamps to the rail;
- forwards thumbnail clicks to `_execute_seek_and_play(timestamp_ms)`;
- asks `ThumbnailTimelineManager.best_random_start(...)` before falling back to raw random seek;
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
    "timestamps_ms": [12000, 31636, 51272],
    "quality_scores": [0.91, 0.84, 0.77],
    "random_start_candidates_ms": [31636, 90544, 160100],
    "files": ["000.jpg", "001.jpg", "002.jpg"],
    "created_at": "2026-06-15T12:00:00+09:00"
  }
}
```

Invalidation rule:

- if path key is missing, generate;
- if file is missing, report unavailable and do not retry aggressively;
- if size or `mtime_ns` differs, mark stale and regenerate;
- if `thumb_count` is not 12, regenerate;
- if any thumbnail file is missing, regenerate only the missing timeline folder or the full small set;
- if extraction fails, store a short failure record to avoid immediate tight retry loops.

### Storage Size

Small JPEG thumbnails are acceptable because the rail shows compact images. For 12 thumbnails per video:

- 100 x 56 to 160 x 90 px is enough for the rail;
- hover preview can reuse the same image if it is at least 200 px wide, or use a second cached size later;
- expected JPEG size can stay small;
- thousands of videos should remain manageable if generation is lazy and cache cleanup exists.

Cache cleanup should be deferred until after v1 unless disk usage becomes measurable. The v1 manager should still keep all thumbnails under one known cache root so cleanup can be added safely.

## Scheduling For Thousands Of Videos

Thumbnail generation must be priority-based and bounded.

Priority order:

1. active playing video;
2. selected visible candidate row;
3. immediate next/previous visible candidates, weighted by current navigation direction;
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

### Timestamp Sampling

Every video gets exactly 12 cells.

Baseline timestamp sampling when duration is known:

```text
safe_start = duration_ms * 0.05
safe_end = duration_ms * 0.95
interval = (safe_end - safe_start) / 11
timestamp[i] = safe_start + interval * i
```

Refinement:

- score frames for brightness, contrast, blur, and similarity to neighboring samples;
- replace black, very dark, nearly blank, or near-duplicate samples with nearby candidates;
- keep final cell count exactly 12 even when a clip is short;
- for very short clips, timestamps may be closer together, but the rail still renders 12 stable cells;
- if duration is unknown, probe conservatively and still produce 12 cells when extraction succeeds.

### Frame Quality Signals

The first version can use simple deterministic signals:

- brightness mean too low means likely black frame;
- contrast too low means low-information frame;
- blur score too low means visually weak frame;
- perceptual similarity too high means duplicate-like frame.

These signals should improve sample choice only. They must not become user-visible ratings.

### Thumbnail-Based Random Start

When random position playback is enabled, the app may ask the thumbnail manager for a better random-start candidate.

Rules:

- prefer timestamps whose thumbnail quality score is acceptable;
- avoid first and last 5 percent of duration;
- avoid known black/low-information samples;
- if no thumbnail timeline exists yet, keep the existing random behavior;
- never wait for thumbnail generation before playback;
- never let random-start logic trigger extraction synchronously.

This makes random exploration more useful without adding UI.

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

If privacy mode hides video while paused, the rail and hover preview must also hide generated thumbnails or show neutral pending cells. The rail should follow the same visibility decision as the main player surface.

Rules:

- when privacy screen is active, do not display source frame thumbnails;
- do not display the 200% hover preview;
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
- Cache hit returns exactly 12 ready cells without starting a worker.
- Changed file size invalidates the cached timeline.
- Changed mtime invalidates the cached timeline.
- Missing thumbnail file invalidates or regenerates the affected timeline.
- Requesting one path queues only that path, not every indexed video.
- Late worker results for an older request token are ignored.
- Sampling always returns 12 timestamps for short, normal, and long videos.
- Low-quality sample replacement preserves 12 final cells.
- Best random-start candidate returns `None` when no cached timeline exists.
- Shutdown interrupts the worker.

### UI Tests

- The right panel contains `ProVideoView` and `ThumbnailPreviewRailWidget` as siblings.
- The rail is not added to `video_view.scene`.
- Default sizing keeps `video_view` at 16:9 within tolerance while the vertical rail consumes separate width.
- The rail shows 12 stable cells without shifting layout as images arrive.
- The same widget can switch to horizontal orientation without changing the timeline model.
- A ready cell click emits its timestamp.
- Hovering a ready cell shows a 200% preview without resizing the rail.
- Leaving the cell hides the hover preview.
- Current playback position updates the nearest cell marker.
- Saved highlights render as small markers.
- `VideoSorter.seek_to_thumbnail(ms)` calls `_execute_seek_and_play(ms)`.
- The click path does not call `player.setPosition(...)` directly.

### Player Boundary Tests

- Thumbnail manager code does not call `PlayerEngine.activate(...)`.
- Thumbnail manager code does not call `PlayerEngine.plan_neighbors(...)`.
- Thumbnail manager code does not call `QMediaPlayer.setSource(...)`.
- Thumbnail-based random start does not block activation while thumbnails are missing.
- Existing preload and continuity smoke tests still pass.

### Manual Smoke

1. Open a folder with multiple videos.
2. Play a video and confirm playback starts with current preload behavior.
3. Confirm the rail shows 12 pending cells immediately and cached/generated thumbnails later.
4. Hover a thumbnail and confirm a 200% preview appears without moving layout.
5. Click a thumbnail and confirm playback seeks smoothly to that region.
6. Enable random position playback and confirm cached timelines improve start candidates without delaying playback.
7. Enable autoscan and confirm thumbnail clicks do not break the scan timer behavior.
8. Save highlights and confirm rail markers appear.
9. Toggle A/B, highlight, trash, and search views and confirm active playback continues.
10. Enable privacy mode, pause, and confirm thumbnails and hover preview are hidden or neutral.
11. Rapidly move across videos and confirm late thumbnails do not appear for the wrong video.
12. Switch the rail to horizontal mode in a development build and confirm the same 12-cell model renders correctly.

## Rollout

### Phase 1: Passive Orientation-Capable UI Shell

Add the rail widget and default layout sizing with 12 pending cells only. Include vertical default and horizontal-capable internals. No extraction.

### Phase 2: Cache Manifest And Manager

Add manifest loading, cache-hit display, invalidation rules, exact 12-cell model, and worker stubs.

### Phase 3: Background Extraction

Add real extraction with PyAV + Pillow, bounded queueing, stale-result guards, and exact 12 output cells.

### Phase 4: Smarter Sampling

Add black-frame, low-contrast, blur, and duplicate-like frame avoidance while preserving exactly 12 cells.

### Phase 5: Click, Hover, Position, And Highlight UI

Route thumbnail clicks through `_execute_seek_and_play(...)`, add 200% hover preview, current position marker, and highlight markers.

### Phase 6: Thumbnail-Based Random Start

Use cached quality-scored thumbnail timestamps to improve random-start selection without blocking playback.

### Phase 7: Performance And Privacy Hardening

Add privacy hiding, large-library smoke, and tests protecting the `PlayerEngine` boundary.

## Acceptance Standard

The feature is acceptable when:

- active video playback remains the fastest path;
- the video area stays 16:9 and is not covered by thumbnails;
- every video renders exactly 12 compact 16:9 cells;
- the default rail appears on the far right when cached or generated;
- the same rail model can later render horizontally;
- hovering a cell shows a 200% preview;
- clicking a thumbnail seeks accurately;
- current playback and saved highlights are visible as subtle markers;
- generating thumbnails for thousands of videos is lazy and bounded;
- thumbnail metadata can improve random-start selection without delaying playback;
- missing or failed thumbnails do not interrupt playback;
- all existing player continuity and preload tests still pass.
