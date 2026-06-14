# Player Engine v4 Directional Preload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve rapid sequential video browsing by making the preload planner direction-aware while preserving Player Engine v3 watch-session continuity.

**Architecture:** Keep the existing three-slot player pools. Add lookahead slot roles to `PlayerEngine`, add a defaulted `preferred_direction` argument to `plan_neighbors(...)`, and have `VideoSorter.play_video(...)` pass a directional hint only after repeated explicit playback movement.

**Tech Stack:** Python 3.10, PyQt6 Qt Multimedia, `unittest`, existing fake QMediaPlayer-style tests, `tools/run_checks.ps1`, `tools/smoke_player_continuity.py`.

---

## File Structure

- Modify: `src/managers/player_engine.py`
  - Add `FORWARD_LOOKAHEAD` and `BACKWARD_LOOKAHEAD` roles.
  - Add target-order helper for balanced/forward/backward planning.
  - Add `preferred_direction=0` to `plan_neighbors(...)`.
  - Reuse same-source preload slots across generation changes by repairing metadata.
  - Reuse obsolete `READY` slots in the same planning pass when they block new targets.
  - Guard `PRELOADING -> READY` against generation/source mismatches.

- Modify: `main.py`
  - Add explicit playback direction tracking helpers.
  - Pass the computed direction to `PlayerEngine.plan_neighbors(...)`.
  - Keep passive list refreshes from affecting direction state.
  - Replan neighbors after passive refresh when the active watch path is visible.
  - Clear the engine watch session on folder context replacement.

- Modify: `tests/test_player_engine.py`
  - Add directional planner tests.

- Modify: `tests/test_video_sorter.py`
  - Update fake engine signatures.
  - Add app-level direction hint tests.

- Modify: `docs/maintenance/playback-state.md`
  - Document balanced and directional preload modes.

---

### Task 1: Add Directional Planner Tests

**Files:**
- Modify: `tests/test_player_engine.py`

- [ ] **Step 1: Write failing tests**

Add tests to `PlayerEnginePreloadPlanTest`:

```python
def test_directional_forward_plan_prefers_next_two_items(self):
    active = make_slot(0, "C:/videos/c.mp4", SlotState.ACTIVE, 5, SlotRole.CURRENT)
    first = make_slot(1)
    second = make_slot(2)
    engine = make_engine([active, first, second])
    playlist = [
        PlaybackItem("C:/videos/a.mp4"),
        PlaybackItem("C:/videos/b.mp4"),
        PlaybackItem("C:/videos/c.mp4"),
        PlaybackItem("C:/videos/d.mp4"),
        PlaybackItem("C:/videos/e.mp4"),
    ]

    engine.plan_neighbors(current_index=2, playlist=playlist, generation=5, preferred_direction=1)

    self.assertEqual(first.state, SlotState.PRELOADING)
    self.assertEqual(first.role, SlotRole.NEXT)
    self.assertEqual(first.expected_path, os.path.normpath("C:/videos/d.mp4"))
    self.assertEqual(second.state, SlotState.PRELOADING)
    self.assertEqual(second.role, SlotRole.FORWARD_LOOKAHEAD)
    self.assertEqual(second.expected_path, os.path.normpath("C:/videos/e.mp4"))


def test_directional_backward_plan_prefers_previous_two_items(self):
    active = make_slot(0, "C:/videos/c.mp4", SlotState.ACTIVE, 5, SlotRole.CURRENT)
    first = make_slot(1)
    second = make_slot(2)
    engine = make_engine([active, first, second])
    playlist = [
        PlaybackItem("C:/videos/a.mp4"),
        PlaybackItem("C:/videos/b.mp4"),
        PlaybackItem("C:/videos/c.mp4"),
        PlaybackItem("C:/videos/d.mp4"),
        PlaybackItem("C:/videos/e.mp4"),
    ]

    engine.plan_neighbors(current_index=2, playlist=playlist, generation=5, preferred_direction=-1)

    self.assertEqual(first.state, SlotState.PRELOADING)
    self.assertEqual(first.role, SlotRole.PREVIOUS)
    self.assertEqual(first.expected_path, os.path.normpath("C:/videos/b.mp4"))
    self.assertEqual(second.state, SlotState.PRELOADING)
    self.assertEqual(second.role, SlotRole.BACKWARD_LOOKAHEAD)
    self.assertEqual(second.expected_path, os.path.normpath("C:/videos/a.mp4"))
```

- [ ] **Step 2: Verify red**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerEnginePreloadPlanTest -v
```

Expected: fail because `plan_neighbors(...)` does not accept `preferred_direction` and the new slot roles do not exist.

---

### Task 2: Implement Directional Planner

**Files:**
- Modify: `src/managers/player_engine.py`

- [ ] **Step 1: Add roles**

Add to `SlotRole`:

```python
FORWARD_LOOKAHEAD = "forward_lookahead"
BACKWARD_LOOKAHEAD = "backward_lookahead"
```

- [ ] **Step 2: Add target helper**

Add this method to `PlayerEngine`:

```python
def _preload_targets(
    self,
    current_index: int,
    playlist: list[PlaybackItem],
    preferred_direction: int = 0,
):
    if preferred_direction > 0:
        offsets = [
            (1, SlotRole.NEXT),
            (2, SlotRole.FORWARD_LOOKAHEAD),
            (-1, SlotRole.PREVIOUS),
        ]
    elif preferred_direction < 0:
        offsets = [
            (-1, SlotRole.PREVIOUS),
            (-2, SlotRole.BACKWARD_LOOKAHEAD),
            (1, SlotRole.NEXT),
        ]
    else:
        offsets = [
            (1, SlotRole.NEXT),
            (-1, SlotRole.PREVIOUS),
        ]

    targets = []
    for offset, role in offsets:
        index = current_index + offset
        if 0 <= index < len(playlist):
            targets.append((playlist[index], role))
    return targets
```

- [ ] **Step 3: Use helper in planner**

Change the signature:

```python
def plan_neighbors(
    self,
    current_index: int,
    playlist: list[PlaybackItem],
    generation: int,
    preferred_direction: int = 0,
) -> None:
```

Replace the manual next/previous target construction with:

```python
targets = self._preload_targets(current_index, playlist, preferred_direction)
```

- [ ] **Step 4: Verify green**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerEnginePreloadPlanTest -v
```

Expected: all preload planner tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/managers/player_engine.py tests/test_player_engine.py
git commit -m "feat: add directional preload planning"
```

---

### Task 3: Add App-Level Direction Hint Tests

**Files:**
- Modify: `tests/test_video_sorter.py`

- [ ] **Step 1: Update fake engine**

Change `FakePlaybackEngine.plan_neighbors(...)` to:

```python
def plan_neighbors(self, current_index, playlist, generation, preferred_direction=0):
    self.plan_calls.append(
        (
            current_index,
            [(item.path, item.start_pos) for item in playlist],
            generation,
            preferred_direction,
        )
    )
```

Update existing expected calls to include trailing `0`.

- [ ] **Step 2: Add failing tests**

Add to `PlayerEngineIntegrationTest`:

```python
def _make_direction_window(self):
    window = type("FakeWindow", (), {"setWindowTitle": lambda self, title: setattr(self, "title", title)})()
    window.file_list = FakePlayableList()
    window.scan_timer = FakeTimer()
    window.preload_timer = FakeTimer()
    window.seek_safety_timer = FakeTimer()
    window.is_waiting_for_seek = False
    window.chk_random = FakeCheck(False)
    window.chk_autoscan = FakeCheck(False)
    window.conf_auto_play = True
    window.conf_privacy_mode = False
    window.playback_generation = 0
    window.player_engine = FakePlaybackEngine()
    window.video_view = FakeVideoView()
    window.player = FakeLoadPlayer()
    window.playback_rate = 1.0
    window._last_media_failure_key = None
    window._prepare_playback = lambda index: VideoSorter._prepare_playback(window, index)
    window._resolve_start_pos = lambda item, specific_pos: VideoSorter._resolve_start_pos(window, item, specific_pos)
    window._current_playlist_items = lambda: VideoSorter._current_playlist_items(window)
    window._increment_playback_generation = lambda: VideoSorter._increment_playback_generation(window)
    window._preload_direction_for_index = lambda index: VideoSorter._preload_direction_for_index(window, index)
    return window


def test_play_video_uses_balanced_preload_until_direction_streak_repeats(self):
    window = self._make_direction_window()

    VideoSorter.play_video(window, 0)
    VideoSorter.play_video(window, 1)

    self.assertEqual(window.player_engine.plan_calls[0][3], 0)
    self.assertEqual(window.player_engine.plan_calls[1][3], 0)


def test_play_video_passes_forward_direction_after_repeated_forward_moves(self):
    window = self._make_direction_window()

    VideoSorter.play_video(window, 0)
    VideoSorter.play_video(window, 1)
    VideoSorter.play_video(window, 2)

    self.assertEqual(window.player_engine.plan_calls[-1][3], 1)


def test_play_video_resets_direction_after_reverse_move(self):
    window = self._make_direction_window()

    VideoSorter.play_video(window, 0)
    VideoSorter.play_video(window, 1)
    VideoSorter.play_video(window, 2)
    VideoSorter.play_video(window, 1)

    self.assertEqual(window.player_engine.plan_calls[-1][3], 0)
```

- [ ] **Step 3: Verify red**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_video_sorter.PlayerEngineIntegrationTest -v
```

Expected: fail because `_preload_direction_for_index(...)` does not exist and `play_video(...)` does not pass the hint.

---

### Task 4: Implement App-Level Direction Hint

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add helper**

Add near `_current_playlist_items(...)`:

```python
def _preload_direction_for_index(self, index: int) -> int:
    previous_index = getattr(self, "last_playback_index", None)
    previous_direction = getattr(self, "last_navigation_direction", 0)
    previous_streak = getattr(self, "navigation_direction_streak", 0)

    direction = 0
    if isinstance(previous_index, int):
        if index > previous_index:
            direction = 1
        elif index < previous_index:
            direction = -1

    if direction == 0:
        streak = 0
    elif direction == previous_direction:
        streak = previous_streak + 1
    else:
        streak = 1

    self.last_playback_index = index
    self.last_navigation_direction = direction
    self.navigation_direction_streak = streak

    return direction if streak >= 2 else 0
```

- [ ] **Step 2: Pass hint to engine**

In `play_video(...)`, before activation planning:

```python
preload_direction = self._preload_direction_for_index(index)
```

Then change:

```python
self.player_engine.plan_neighbors(index, self._current_playlist_items(), generation)
```

to:

```python
self.player_engine.plan_neighbors(
    index,
    self._current_playlist_items(),
    generation,
    preferred_direction=preload_direction,
)
```

- [ ] **Step 3: Verify green**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_video_sorter.PlayerEngineIntegrationTest -v
```

Expected: app-level direction tests pass.

- [ ] **Step 4: Commit**

```powershell
git add main.py tests/test_video_sorter.py
git commit -m "feat: pass directional preload hints"
```

---

### Task 5: Document And Verify

**Files:**
- Modify: `docs/maintenance/playback-state.md`

- [ ] **Step 1: Document v4 policy**

Add a `## Directional Preload` section:

```markdown
## Directional Preload

Player Engine v4 keeps balanced preload behavior until explicit playback movement shows a repeated direction:

- first play, jumps, replays, and direction changes keep `current + next + previous`;
- repeated forward movement keeps `current + next + next2` when slots allow;
- repeated backward movement keeps `current + previous + previous2` when slots allow.

The direction hint is produced only by explicit playback activation. Passive list refreshes for A/B tags, highlight, trash, and search do not change preload direction or replace the active watch session.
```

- [ ] **Step 2: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerEnginePreloadPlanTest tests.test_video_sorter.PlayerEngineIntegrationTest -v
```

Expected: all focused tests pass.

- [ ] **Step 3: Run full verification**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_checks.ps1
.\.venv\Scripts\python.exe .\tools\smoke_player_continuity.py
git diff --check
```

Expected: all commands exit 0.

- [ ] **Step 4: Commit docs and any count updates**

```powershell
git add docs/maintenance/playback-state.md docs/maintenance/stabilization-report-2026-06-12.md docs/superpowers/plans/2026-06-12-project-stabilization-master-plan.md docs/superpowers/plans/2026-06-15-player-engine-v4-directional-preload-implementation-plan.md
git commit -m "docs: describe directional preload policy"
```

Do not create this commit if only verification ran and no files changed.

---

### Task 6: Push

**Files:**
- No planned edits.

- [ ] **Step 1: Check clean state**

Run:

```powershell
git status -sb
```

Expected: no unstaged or staged changes.

- [ ] **Step 2: Push**

Run:

```powershell
git push
```

Expected: branch pushes to `origin/codex/player-engine-stabilization`.
