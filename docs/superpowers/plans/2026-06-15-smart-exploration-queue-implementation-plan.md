# Smart Exploration Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a simple, intuitive queue state layer that helps the user decide what to review next without replacing A/B tags, highlights, trash, search, or the fast player workflow.

**Architecture:** `FileManager` owns normalized queue metadata and filtering. `VideoSorter` owns passive view switching and UI coordination. `ShortcutHandler` adds one keyboard action for cycling the current file's queue state. Queue state is workflow progress, while A/B tags remain taste or priority labels.

**Tech Stack:** Python 3, PyQt6, existing JSON persistence in `FileManager`, existing `QListWidget` UI, existing unit and smoke test suite.

---

## Product Shape

The Smart Exploration Queue must feel like a small workflow layer, not a second tagging system.

Visible concepts:

- `All`
- `Unreviewed`
- `Kept`
- `Hold`
- `Delete Candidate`
- `Recently Viewed`

Explicit persisted states:

- `kept`
- `hold`
- `delete_candidate`

Derived states:

- `unreviewed`: no explicit queue state exists;
- `recently_viewed`: `last_viewed_at` is recent enough for the filter;
- `has_highlight`: derived from `FileManager.highlights`, not stored in queue state;
- `trashed`: derived from `FileManager.trash_files`, not stored in queue state.

A/B tags do not automatically change queue state in v1. This keeps the model understandable:

- A/B = taste, quality, or priority;
- queue state = review workflow.

## File Structure

Create:

- `tests/test_smart_queue.py`
  - FileManager queue metadata, filtering, rename, delete, and malformed-record coverage.

Modify:

- `src/core/consts.py`
  - Add `QUEUE_FILE`.
  - Add `video_queue.json` to legacy migration file names.

- `src/managers/file_manager.py`
  - Load `queue_states`.
  - Add queue state validation, persistence, filtering, viewing metadata, rename migration, hard-delete cleanup, and reset cleanup.

- `main.py`
  - Add queue filter toggling methods.
  - Update `update_ui_mode(...)` labels/watermarks/tooltips.
  - Add `cycle_current_queue_state()`.
  - Touch viewed metadata after explicit video activation.

- `src/ui/ui_layout.py`
  - Add one compact queue button/menu in the second row near A/B/filter controls.

- `src/core/signal_setup.py`
  - Wire the queue menu/button to `VideoSorter` methods.

- `src/core/event_handler.py`
  - Add `4` shortcut to cycle current file queue state.

- `tests/test_video_sorter.py`
  - Add passive queue filter behavior tests.

- `tests/test_event_handler.py`
  - Add shortcut tests for key `4`.

- `docs/maintenance/manual-smoke-test.md`
  - Add a short queue smoke section.

## Task 1: Add Queue Constants And FileManager Loading

**Files:**

- Modify: `src/core/consts.py`
- Modify: `src/managers/file_manager.py`
- Test: `tests/test_smart_queue.py`

- [ ] **Step 1: Write the failing tests**

Add `tests/test_smart_queue.py`:

```python
import json
import os
import tempfile
import unittest

from src.core import consts
from src.managers.file_manager import FileManager


class SmartQueueTest(unittest.TestCase):
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
            "QUEUE_FILE": getattr(consts, "QUEUE_FILE", None),
        }
        consts.LEGACY_INDEX_DIR = self.legacy_index_dir
        consts.INDEX_DIR = self.index_dir
        consts.TAGS_FILE = os.path.join(self.index_dir, "video_tags.json")
        consts.HIGHLIGHTS_FILE = os.path.join(self.index_dir, "video_highlights.json")
        consts.HISTORY_FILE = os.path.join(self.index_dir, "folder_history.json")
        consts.TRASH_CACHE_FILE = os.path.join(self.index_dir, "trash_cache.json")
        consts.GLOBAL_CACHE_FILE = os.path.join(self.index_dir, "video_global_cache.json")
        consts.QUEUE_FILE = os.path.join(self.index_dir, "video_queue.json")

    def tearDown(self):
        for name, value in self.original_paths.items():
            if value is None and hasattr(consts, name):
                delattr(consts, name)
            elif value is not None:
                setattr(consts, name, value)
        self.temp_dir.cleanup()

    def write_json(self, path, payload):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False)

    def make_video(self, name="sample.mp4"):
        path = os.path.join(self.temp_dir.name, name)
        with open(path, "w", encoding="utf-8") as file:
            file.write("video placeholder")
        return path

    def make_manager(self):
        return FileManager()

    def test_loads_queue_file_as_normalized_dict(self):
        video_path = self.make_video()
        self.write_json(consts.QUEUE_FILE, {video_path: {"state": "hold"}})

        manager = self.make_manager()

        key = manager._get_norm_key(video_path)
        self.assertEqual(manager.queue_states, {key: {"state": "hold"}})

    def test_malformed_queue_records_are_skipped(self):
        video_path = self.make_video()
        self.write_json(
            consts.QUEUE_FILE,
            {
                video_path: {"state": "hold"},
                "missing-state.mp4": {"state": "not-valid"},
                "not-a-record.mp4": "hold",
            },
        )

        manager = self.make_manager()

        self.assertEqual(list(manager.queue_states.values()), [{"state": "hold"}])
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_smart_queue.py -q
```

Expected:

- fails because `consts.QUEUE_FILE` or `FileManager.queue_states` does not exist.

- [ ] **Step 3: Add constants**

Modify `src/core/consts.py`:

```python
QUEUE_FILE = os.path.join(INDEX_DIR, "video_queue.json")

INDEX_FILE_NAMES = (
    "video_tags.json",
    "video_highlights.json",
    "folder_history.json",
    "trash_cache.json",
    "video_global_cache.json",
    "video_queue.json",
)
```

- [ ] **Step 4: Add queue loading and sanitizing**

Modify `src/managers/file_manager.py` inside `__init__`:

```python
self.queue_file_path = consts.QUEUE_FILE
self.queue_states = self.load_queue_states(self.queue_file_path)
self.queue_filter = None
```

Add methods near the JSON helpers:

```python
QUEUE_STATES = {"kept", "hold", "delete_candidate"}

def load_queue_states(self, path):
    raw = self.load_json(path)
    if not isinstance(raw, dict):
        return {}

    clean = {}
    for raw_path, record in raw.items():
        if not raw_path or not isinstance(record, dict):
            continue
        state = record.get("state")
        if state not in self.QUEUE_STATES:
            continue
        key = self._get_norm_key(raw_path)
        clean_record = {"state": state}
        if isinstance(record.get("reviewed_at"), str):
            clean_record["reviewed_at"] = record["reviewed_at"]
        if isinstance(record.get("last_viewed_at"), str):
            clean_record["last_viewed_at"] = record["last_viewed_at"]
        view_count = record.get("view_count", 0)
        if isinstance(view_count, int) and view_count > 0:
            clean_record["view_count"] = view_count
        clean[key] = clean_record
    return clean
```

- [ ] **Step 5: Verify tests pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_smart_queue.py -q
```

Expected:

- both tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/core/consts.py src/managers/file_manager.py tests/test_smart_queue.py
git commit -m "feat: load smart queue metadata"
```

## Task 2: Add Queue State API

**Files:**

- Modify: `src/managers/file_manager.py`
- Test: `tests/test_smart_queue.py`

- [ ] **Step 1: Add failing tests**

Append to `SmartQueueTest`:

```python
    def test_set_queue_state_persists_record(self):
        video_path = self.make_video()
        manager = self.make_manager()

        state = manager.set_queue_state(video_path, "hold")

        self.assertEqual(state, "hold")
        key = manager._get_norm_key(video_path)
        self.assertEqual(manager.queue_states[key]["state"], "hold")
        with open(consts.QUEUE_FILE, encoding="utf-8") as file:
            saved = json.load(file)
        self.assertEqual(saved[key]["state"], "hold")

    def test_set_unreviewed_removes_explicit_record(self):
        video_path = self.make_video()
        manager = self.make_manager()
        manager.set_queue_state(video_path, "hold")

        state = manager.set_queue_state(video_path, "unreviewed")

        self.assertIsNone(state)
        self.assertNotIn(manager._get_norm_key(video_path), manager.queue_states)

    def test_cycle_queue_state_uses_simple_order(self):
        video_path = self.make_video()
        manager = self.make_manager()

        self.assertEqual(manager.cycle_queue_state(video_path), "kept")
        self.assertEqual(manager.cycle_queue_state(video_path), "hold")
        self.assertEqual(manager.cycle_queue_state(video_path), "delete_candidate")
        self.assertIsNone(manager.cycle_queue_state(video_path))
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_smart_queue.py -q
```

Expected:

- fails because `set_queue_state` and `cycle_queue_state` do not exist.

- [ ] **Step 3: Implement API**

Add to `FileManager`:

```python
QUEUE_CYCLE = (None, "kept", "hold", "delete_candidate")

def save_queue_states(self):
    return self.save_json(self.queue_file_path, self.queue_states)

def get_queue_state(self, path):
    key = self._get_norm_key(path)
    record = self.queue_states.get(key)
    if not isinstance(record, dict):
        return None
    state = record.get("state")
    return state if state in self.QUEUE_STATES else None

def set_queue_state(self, path, state):
    key = self._get_norm_key(path)
    if state in (None, "", "unreviewed"):
        self.queue_states.pop(key, None)
        self.save_queue_states()
        return None
    if state not in self.QUEUE_STATES:
        return self.get_queue_state(path)
    record = dict(self.queue_states.get(key, {}))
    record["state"] = state
    self.queue_states[key] = record
    self.save_queue_states()
    return state

def cycle_queue_state(self, path):
    current = self.get_queue_state(path)
    index = self.QUEUE_CYCLE.index(current) if current in self.QUEUE_CYCLE else 0
    next_state = self.QUEUE_CYCLE[(index + 1) % len(self.QUEUE_CYCLE)]
    return self.set_queue_state(path, next_state)
```

- [ ] **Step 4: Verify tests pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_smart_queue.py -q
```

Expected:

- new queue API tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/managers/file_manager.py tests/test_smart_queue.py
git commit -m "feat: add smart queue state API"
```

## Task 3: Add Queue Filtering

**Files:**

- Modify: `src/managers/file_manager.py`
- Test: `tests/test_smart_queue.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
    def test_queue_filter_hold_returns_only_hold_items(self):
        hold_path = self.make_video("hold.mp4")
        kept_path = self.make_video("kept.mp4")
        manager = self.make_manager()
        manager.main_files = [
            {"path": hold_path, "text": "hold.mp4"},
            {"path": kept_path, "text": "kept.mp4"},
        ]
        manager.set_queue_state(hold_path, "hold")
        manager.set_queue_state(kept_path, "kept")
        manager.set_queue_filter("hold")

        result = manager.get_current_list()

        self.assertEqual([item["path"] for item in result], [hold_path])

    def test_queue_filter_unreviewed_excludes_explicit_states_and_trash(self):
        unreviewed_path = self.make_video("unreviewed.mp4")
        hold_path = self.make_video("hold.mp4")
        trash_path = self.make_video("trash.mp4")
        manager = self.make_manager()
        manager.main_files = [
            {"path": unreviewed_path, "text": "unreviewed.mp4"},
            {"path": hold_path, "text": "hold.mp4"},
            {"path": trash_path, "text": "trash.mp4"},
        ]
        manager.trash_files = [{"path": trash_path, "text": "trash.mp4"}]
        manager.set_queue_state(hold_path, "hold")
        manager.set_queue_filter("unreviewed")

        result = manager.get_current_list()

        self.assertEqual([item["path"] for item in result], [unreviewed_path])
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_smart_queue.py -q
```

Expected:

- fails because queue filtering is not implemented.

- [ ] **Step 3: Implement filtering helpers**

Add to `FileManager`:

```python
QUEUE_FILTERS = {"unreviewed", "kept", "hold", "delete_candidate", "recently_viewed"}

def set_queue_filter(self, queue_filter):
    self.queue_filter = queue_filter if queue_filter in self.QUEUE_FILTERS else None

def _matches_queue_filter(self, item, queue_filter, trash_keys):
    clean_item = self._normalize_file_item(item)
    if not clean_item:
        return False
    path = clean_item["path"]
    key = self._get_norm_key(path)
    if key in trash_keys:
        return False
    record = self.queue_states.get(key, {})
    state = record.get("state") if isinstance(record, dict) else None
    if queue_filter == "unreviewed":
        return state is None
    if queue_filter == "recently_viewed":
        return bool(isinstance(record, dict) and record.get("last_viewed_at"))
    return state == queue_filter

def _apply_queue_filter(self, items, queue_filter, trash_keys):
    result = []
    seen_keys = set()
    for item in items:
        clean_item = self._normalize_file_item(item)
        if not clean_item:
            continue
        key = self._get_norm_key(clean_item["path"])
        if key in seen_keys:
            continue
        if self._matches_queue_filter(clean_item, queue_filter, trash_keys):
            seen_keys.add(key)
            clean_item["text"] = self._format_display_text(clean_item["path"])
            result.append(clean_item)
    result.sort(key=lambda x: os.path.basename(x["path"]).lower())
    return result
```

In `get_current_list()`, after choosing `target_list` for main or global search and before search filtering, add:

```python
queue_filter = getattr(self, "queue_filter", None)
if queue_filter and self.current_mode not in {"trash", "highlight"}:
    return self._apply_queue_filter(target_list, queue_filter, trash_keys)
```

- [ ] **Step 4: Verify tests pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_smart_queue.py -q
```

Expected:

- queue filtering tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add src/managers/file_manager.py tests/test_smart_queue.py
git commit -m "feat: filter videos by smart queue state"
```

## Task 4: Preserve Metadata Through Rename And Delete

**Files:**

- Modify: `src/managers/file_manager.py`
- Test: `tests/test_smart_queue.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
    def test_rename_migrates_queue_state(self):
        old_path = self.make_video("old.mp4")
        new_name = "new.mp4"
        new_path = os.path.join(self.temp_dir.name, new_name)
        manager = self.make_manager()
        manager.main_files = [{"path": old_path, "text": "old.mp4"}]
        manager.root_folder = self.temp_dir.name
        manager.set_queue_state(old_path, "hold")

        success, message = manager.rename_file_by_path(old_path, new_name)

        self.assertTrue(success, message)
        old_key = manager._get_norm_key(old_path)
        new_key = manager._get_norm_key(new_path)
        self.assertNotIn(old_key, manager.queue_states)
        self.assertEqual(manager.queue_states[new_key]["state"], "hold")

    def test_clear_queue_state_removes_record(self):
        video_path = self.make_video()
        manager = self.make_manager()
        manager.set_queue_state(video_path, "delete_candidate")

        removed = manager.clear_queue_state(video_path)

        self.assertTrue(removed)
        self.assertNotIn(manager._get_norm_key(video_path), manager.queue_states)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_smart_queue.py -q
```

Expected:

- fails because queue rename migration and clear helper are not implemented.

- [ ] **Step 3: Implement clear helper**

Add to `FileManager`:

```python
def clear_queue_state(self, path):
    key = self._get_norm_key(path)
    existed = key in self.queue_states
    if existed:
        del self.queue_states[key]
        self.save_queue_states()
    return existed
```

- [ ] **Step 4: Migrate queue state during rename**

Inside `rename_file_by_path(...)`, where tags and highlights are migrated from `old_key` to `new_key`, add:

```python
if old_key in self.queue_states:
    self.queue_states[new_key] = self.queue_states.pop(old_key)
    self.save_queue_states()
```

- [ ] **Step 5: Remove queue metadata when physically deleting**

In the hard-delete cleanup path where tags and highlights are deleted for a path, add:

```python
self.clear_queue_state(path)
```

If the function operates on canonical keys instead of raw paths, delete directly:

```python
if key in self.queue_states:
    del self.queue_states[key]
    self.save_queue_states()
```

- [ ] **Step 6: Verify tests pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_smart_queue.py -q
```

Expected:

- queue metadata survives rename and can be cleared.

- [ ] **Step 7: Commit**

Run:

```powershell
git add src/managers/file_manager.py tests/test_smart_queue.py
git commit -m "feat: keep smart queue metadata consistent"
```

## Task 5: Add Viewed Metadata

**Files:**

- Modify: `src/managers/file_manager.py`
- Modify: `main.py`
- Test: `tests/test_smart_queue.py`

- [ ] **Step 1: Add failing test**

Append:

```python
    def test_touch_viewed_updates_count_and_timestamp(self):
        video_path = self.make_video()
        manager = self.make_manager()

        manager.touch_viewed(video_path, now_text="2026-06-15T12:00:00+09:00")
        manager.touch_viewed(video_path, now_text="2026-06-15T12:01:00+09:00")

        record = manager.queue_states[manager._get_norm_key(video_path)]
        self.assertEqual(record["last_viewed_at"], "2026-06-15T12:01:00+09:00")
        self.assertEqual(record["view_count"], 2)
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_smart_queue.py::SmartQueueTest::test_touch_viewed_updates_count_and_timestamp -q
```

Expected:

- fails because `touch_viewed` does not exist.

- [ ] **Step 3: Implement touch helper**

Add imports in `file_manager.py`:

```python
from datetime import datetime, timezone
```

Add method:

```python
def touch_viewed(self, path, now_text=None):
    key = self._get_norm_key(path)
    record = dict(self.queue_states.get(key, {}))
    if now_text is None:
        now_text = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    record["last_viewed_at"] = now_text
    view_count = record.get("view_count", 0)
    record["view_count"] = view_count + 1 if isinstance(view_count, int) else 1
    state = record.get("state")
    if state not in self.QUEUE_STATES:
        record.pop("state", None)
    self.queue_states[key] = record
    self.save_queue_states()
```

- [ ] **Step 4: Call touch after explicit activation**

In `VideoSorter.play_video(...)`, after successful path resolution and before returning, add:

```python
if hasattr(self.file_manager, "touch_viewed"):
    self.file_manager.touch_viewed(target_path)
```

Place it after `PlayerEngine.activate(...)` so malformed paths that do not activate are not marked viewed.

- [ ] **Step 5: Verify tests pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_smart_queue.py -q
```

Expected:

- viewed metadata test passes.

- [ ] **Step 6: Commit**

Run:

```powershell
git add src/managers/file_manager.py main.py tests/test_smart_queue.py
git commit -m "feat: track viewed videos for smart queue"
```

## Task 6: Add Minimal Queue UI

**Files:**

- Modify: `src/ui/ui_layout.py`
- Modify: `src/core/signal_setup.py`
- Modify: `main.py`
- Test: `tests/test_video_sorter.py`

- [ ] **Step 1: Add failing passive-refresh test**

Add to `tests/test_video_sorter.py` near existing mode/filter tests:

```python
def test_queue_filter_refresh_preserves_active_watch_session(self):
    class FakeFileManager:
        def __init__(self):
            self.queue_filter = None
            self.current_mode = "main"
            self.filter_type = None
            self.is_trash_mode = False

        def set_queue_filter(self, queue_filter):
            self.queue_filter = queue_filter

    class FakeWindow:
        def __init__(self):
            self.file_manager = FakeFileManager()
            self.update_calls = []

        def update_ui_mode(self, activation_policy="auto_if_no_watch"):
            self.update_calls.append(activation_policy)

    window = FakeWindow()

    VideoSorter.apply_queue_filter(window, "hold")

    self.assertEqual(window.file_manager.queue_filter, "hold")
    self.assertEqual(window.update_calls, ["preserve"])
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_video_sorter.py::test_queue_filter_refresh_preserves_active_watch_session -q
```

Expected:

- fails because `apply_queue_filter` does not exist.

- [ ] **Step 3: Add UI control**

In `src/ui/ui_layout.py`, add a compact button after B and before refresh:

```python
window.btn_queue = QPushButton("Q")
window.btn_queue.setFixedHeight(MENUHEIGHT)
window.btn_queue.setCheckable(True)
window.btn_queue.setToolTip("Smart Queue")
window.btn_queue.setStyleSheet(styles.BTN_FILTER_B)
```

Add it to the row:

```python
addr_layout.addWidget(window.btn_queue, 0)
```

Add it to `all_buttons` so focus policy remains consistent.

- [ ] **Step 4: Add coordinator methods**

In `main.py`, add:

```python
QUEUE_LABELS = {
    None: "All",
    "unreviewed": "Unreviewed",
    "kept": "Kept",
    "hold": "Hold",
    "delete_candidate": "Delete Candidate",
    "recently_viewed": "Recently Viewed",
}

def apply_queue_filter(self, queue_filter):
    if hasattr(self.file_manager, "set_queue_filter"):
        self.file_manager.set_queue_filter(queue_filter)
    self.update_ui_mode(activation_policy="preserve")

def clear_queue_filter(self):
    self.apply_queue_filter(None)
```

Update `_update_visible_widgets(...)`:

```python
queue_filter = getattr(self.file_manager, "queue_filter", None)
if queue_filter:
    self.folder_list_widget.hide()
    label = self.QUEUE_LABELS.get(queue_filter, queue_filter)
    self.file_list.set_watermark(f"[ Queue: {label} ]", Catppuccin.GREEN, 50)
    self.lbl_info.setText(f"Queue {label}: {list_count}개")
```

Place this before the normal main-mode folder visibility branch so queue filter behaves like A/B/search.

- [ ] **Step 5: Wire button**

In `src/core/signal_setup.py`, add a basic cycle for v1:

```python
window.btn_queue.clicked.connect(lambda: window.apply_queue_filter("hold" if window.btn_queue.isChecked() else None))
```

This first UI exposes `Hold` as the primary queue review list. A richer menu can follow without changing the data model.

- [ ] **Step 6: Verify tests pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_video_sorter.py::test_queue_filter_refresh_preserves_active_watch_session -q
```

Expected:

- passive queue filter test passes.

- [ ] **Step 7: Commit**

Run:

```powershell
git add main.py src/ui/ui_layout.py src/core/signal_setup.py tests/test_video_sorter.py
git commit -m "feat: add minimal smart queue filter UI"
```

## Task 7: Add Shortcut To Cycle Current Queue State

**Files:**

- Modify: `main.py`
- Modify: `src/core/event_handler.py`
- Test: `tests/test_event_handler.py`

- [ ] **Step 1: Add failing event-handler test**

Add to `tests/test_event_handler.py`:

```python
def test_key_4_cycles_queue_state():
    main = FakeMain()
    main.input_search.focused = False
    main.calls = []
    main.cycle_current_queue_state = lambda: main.calls.append("cycle_current_queue_state")

    handled = ShortcutHandler(main).process_event(main, FakeKeyEvent(Qt.Key.Key_4))

    self.assertTrue(handled)
    self.assertEqual(main.calls, ["cycle_current_queue_state"])
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_event_handler.py::test_key_4_cycles_queue_state -q
```

Expected:

- fails because key `4` is not handled.

- [ ] **Step 3: Add `VideoSorter` method**

In `main.py`, add:

```python
def cycle_current_queue_state(self):
    item = self.file_list.currentItem()
    if item is None:
        return
    path = item.data(Qt.ItemDataRole.UserRole)
    if not path or self.file_manager.is_trash_mode:
        return
    state = self.file_manager.cycle_queue_state(path)
    label = "Unreviewed" if state is None else self.QUEUE_LABELS.get(state, state)
    self.video_view.show_temp_message(f"Queue: {label}")
    self.update_ui_mode(activation_policy="preserve")
```

- [ ] **Step 4: Add event-handler shortcut**

In `src/core/event_handler.py`, after keys `1`, `2`, `3`, add:

```python
if key == Qt.Key.Key_4:
    self.main.cycle_current_queue_state()
    return True
```

- [ ] **Step 5: Verify tests pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_event_handler.py::test_key_4_cycles_queue_state -q
```

Expected:

- shortcut test passes.

- [ ] **Step 6: Commit**

Run:

```powershell
git add main.py src/core/event_handler.py tests/test_event_handler.py
git commit -m "feat: add smart queue shortcut"
```

## Task 8: Add Tooltips And Manual Smoke Coverage

**Files:**

- Modify: `main.py`
- Modify: `docs/maintenance/manual-smoke-test.md`
- Test: `tests/test_video_sorter.py`

- [ ] **Step 1: Add tooltip expectation test**

Add to `tests/test_video_sorter.py` near `_build_file_item_tooltip` tests:

```python
def test_file_tooltip_includes_queue_state():
    class FakeFileManager:
        queue_states = {"c:\\videos\\hold.mp4": {"state": "hold"}}
        file_tags = {}

        def _get_norm_key(self, path):
            return path.lower()

    class FakeWindow:
        file_manager = FakeFileManager()

    tooltip = VideoSorter._build_file_item_tooltip(
        FakeWindow(),
        {"path": "C:\\Videos\\hold.mp4"},
        is_trash=False,
    )

    self.assertIn("Queue: hold", tooltip)
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_video_sorter.py::test_file_tooltip_includes_queue_state -q
```

Expected:

- fails because tooltip does not include queue state.

- [ ] **Step 3: Update tooltip builder**

In `_build_file_item_tooltip(...)`, add:

```python
queue_states = getattr(self.file_manager, "queue_states", {})
queue_key = self.file_manager._get_norm_key(path) if hasattr(self.file_manager, "_get_norm_key") else os.path.normcase(os.path.normpath(path))
queue_record = queue_states.get(queue_key, {})
if isinstance(queue_record, dict) and queue_record.get("state"):
    lines.append(f"Queue: {queue_record['state']}")
```

- [ ] **Step 4: Update manual smoke checklist**

Append to `docs/maintenance/manual-smoke-test.md`:

```markdown
## Smart Queue Smoke

1. Open a folder with several videos.
2. Play a video and press `4` until it becomes `Hold`.
3. Switch to the queue filter and confirm the video appears without interrupting playback.
4. Press `4` again through `Kept`, `Hold`, `Delete Candidate`, and `Unreviewed`.
5. Confirm A/B tags, highlights, search, trash, and restore still behave as before.
6. Rename a queued file and confirm the queue state follows the renamed file.
7. Hard-delete a queued file from trash and confirm its queue state is removed.
```

- [ ] **Step 5: Verify tests pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_video_sorter.py::test_file_tooltip_includes_queue_state -q
```

Expected:

- tooltip test passes.

- [ ] **Step 6: Commit**

Run:

```powershell
git add main.py docs/maintenance/manual-smoke-test.md tests/test_video_sorter.py
git commit -m "docs: add smart queue smoke coverage"
```

## Task 9: Full Verification

**Files:**

- No planned edits.

- [ ] **Step 1: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_smart_queue.py tests/test_event_handler.py tests/test_video_sorter.py -q
```

Expected:

- all focused tests pass.

- [ ] **Step 2: Run full project checks**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_checks.ps1
```

Expected:

- full test suite passes;
- no static cleanup guard fails;
- no lint or diff-check failure appears.

- [ ] **Step 3: Run continuity smoke**

Run:

```powershell
.\.venv\Scripts\python.exe .\tools\smoke_player_continuity.py
```

Expected:

- playback continues across A/B, highlight, trash, search, and non-active actions.

- [ ] **Step 4: Manual app smoke**

Run the app and verify:

```powershell
.\.venv\Scripts\python.exe main.py
```

Manual expected results:

- arrow-key exploration still activates videos quickly;
- pressing `1`, `2`, `3`, `Enter`, `Del`, and `Space` still performs existing actions;
- pressing `4` cycles queue state;
- queue filter switching does not stop or replace the active watch session;
- queue view does not physically delete files;
- trash hard delete removes queue metadata.

- [ ] **Step 5: Final commit if needed**

If verification required small fixes:

```powershell
git add main.py src tests docs
git commit -m "fix: harden smart queue workflow"
```

## Self-Review

Spec coverage:

- minimal queue states are represented by explicit and derived states;
- A/B tags remain separate;
- UI is one compact control plus one shortcut;
- passive view refresh preserves playback;
- persistence is normalized JSON under app index data;
- trash, hard delete, rename, search, and highlight compatibility are covered;
- acceptance tests include file manager, UI, shortcut, and manual smoke coverage.

Placeholder scan:

- this plan contains no unresolved placeholders, no unbounded custom taxonomy, and no unspecified implementation areas.

Type consistency:

- queue state values are strings: `kept`, `hold`, `delete_candidate`;
- unset queue state is represented by missing record or `None` in memory;
- `set_queue_filter(None)` clears queue filtering;
- `cycle_queue_state(path)` returns the new explicit state or `None`.

## Execution Choice

Plan complete. Recommended execution is subagent-driven task execution because each task has a narrow file set and clear verification step.
