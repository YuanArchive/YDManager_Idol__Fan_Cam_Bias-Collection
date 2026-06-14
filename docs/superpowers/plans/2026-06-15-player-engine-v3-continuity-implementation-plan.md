# Player Engine v3 Continuity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make video playback independent from menu/list navigation so the watched video survives A tag, B tag, highlight, trash, search, and return-to-main round trips without forced reloads or reset-to-zero behavior.

**Architecture:** Introduce a watch-session boundary in `PlayerEngine`, make `PlayerManager.switch_mode()` passive by default, and split visible-list candidate selection from explicit playback activation in `VideoSorter`. Destructive cleanup remains explicit for hard delete, rename, reset, folder close, and app shutdown.

**Tech Stack:** Python 3.10, PyQt6 Qt Multimedia, `unittest`, existing fake QMediaPlayer-style test doubles, `tools/run_checks.ps1`.

---

## File Structure

- Modify: `src/managers/player_engine.py`
  - Add `WatchSession`.
  - Record active watch metadata during activation.
  - Keep `active_player()` and `active_audio()` independent from visible menu mode.
  - Demote old active slots globally when explicit playback activation replaces the watch session.
  - Clear watch metadata when the active path is released.

- Modify: `src/managers/player_manager.py`
  - Make `switch_mode()` passive by default.
  - Keep explicit destructive release available through `preserve_current=False`, `stop_all_in_mode(...)`, `cleanup()`, and `stop_and_release_path(...)`.

- Modify: `main.py`
  - Route `player` and `audio_output` properties through `PlayerEngine` active watch state.
  - Add helpers for watch-session existence, path matching, candidate-row restoration, and post-refresh activation policy.
  - Change passive menu/search refreshes so they do not call `play_video(0)`.
  - Keep initial folder load and explicit row changes able to start playback.

- Modify: `src/controllers/file_action_controller.py`
  - Do not auto-replace playback after deleting/restoring a visible candidate that is not the active watch path.
  - Keep auto-advance when the active watch file is deleted, moved, renamed, or invalidated.

- Modify: `src/core/event_handler.py`
  - Ensure keyboard focus navigation does not start playback merely because a row becomes selected.
  - Keep explicit keyboard navigation that changes the current file as playback intent.

- Modify: `tests/test_player_manager.py`
  - Add passive/destructive mode-switch tests.

- Modify: `tests/test_player_engine.py`
  - Add watch-session tests.
  - Add cross-mode explicit activation tests.

- Modify: `tests/test_video_sorter.py`
  - Add active-player routing tests.
  - Add passive menu/list refresh tests.
  - Add search refresh continuity tests.

- Modify: `tests/test_file_action_controller.py`
  - Add selected-candidate delete/restore tests that do not steal playback.
  - Add active-watch delete/rename tests that still release and replace playback.

- Modify: `docs/maintenance/playback-state.md`
  - Update mode-switching notes from destructive pool release to passive view switching plus explicit release.

- Modify when the automated unittest count changes:
  - `docs/maintenance/stabilization-report-2026-06-12.md`
  - any static packaging/docs test that asserts the current automated test count.

---

### Task 1: Lock Passive Mode Switching In PlayerManager

**Files:**
- Modify: `tests/test_player_manager.py`
- Modify: `src/managers/player_manager.py`

- [ ] **Step 1: Write failing passive/destructive mode-switch tests**

Add these tests to `PlayerManagerTest`:

```python
def test_passive_switch_mode_preserves_current_pool_sources(self):
    manager = make_manager()
    active = manager.pools["main"][0]

    manager.switch_mode("A", preserve_current=True)

    self.assertEqual(manager.current_mode, "A")
    self.assertFalse(active["player"].stopped)
    self.assertEqual(active["player"].source, "loaded")
    self.assertEqual(active["path"], "C:/videos/active.mp4")
    self.assertFalse(active["audio"].muted)
    self.assertEqual(active["item"].opacity, 1.0)


def test_destructive_switch_mode_releases_current_pool_when_requested(self):
    manager = make_manager()
    active = manager.pools["main"][0]

    manager.switch_mode("A", preserve_current=False)

    self.assertEqual(manager.current_mode, "A")
    self.assertTrue(active["player"].stopped)
    self.assertIsNone(active["path"])
    self.assertEqual(active["item"].opacity, 0.0)
    self.assertTrue(active["audio"].muted)
```

- [ ] **Step 2: Run the focused tests and confirm the expected failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_manager.PlayerManagerTest -v
```

Expected: FAIL or ERROR because `switch_mode()` does not accept `preserve_current`.

- [ ] **Step 3: Implement passive switching**

Change `PlayerManager.switch_mode()` in `src/managers/player_manager.py` to:

```python
def switch_mode(self, target_mode, *, preserve_current=True):
    """Switch visible player mode.

    Passive switches keep existing media sources alive. Destructive release is
    reserved for explicit cleanup paths such as reset, folder close, and delete.
    """
    if target_mode not in self.pools:
        raise ValueError(f"Unknown player mode: {target_mode}")

    if self.current_mode == target_mode:
        return

    if not preserve_current:
        old_pool = self.pools[self.current_mode]
        for p_data in old_pool:
            p_data["player"].stop()
            p_data["player"].setSource(QUrl())
            p_data["item"].setOpacity(0.0)
            p_data["audio"].setMuted(True)
            p_data["path"] = None

    self.current_mode = target_mode
    active_idx = self.active_indices[target_mode]
    self.pools[target_mode][active_idx]["player"].blockSignals(False)
```

- [ ] **Step 4: Run the focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_manager.PlayerManagerTest -v
```

Expected: all `PlayerManagerTest` tests pass.

- [ ] **Step 5: Commit**

```powershell
git add tests/test_player_manager.py src/managers/player_manager.py
git commit -m "refactor: make player mode switches passive"
```

---

### Task 2: Add WatchSession To PlayerEngine

**Files:**
- Modify: `tests/test_player_engine.py`
- Modify: `src/managers/player_engine.py`

- [ ] **Step 1: Write failing watch-session tests**

Add `WatchSession` to the import list in `tests/test_player_engine.py`.

Add these tests to `PlayerEngineActivationTest`:

```python
def test_activate_records_watch_session_metadata(self):
    slot = make_slot(0)
    engine = make_engine([slot])

    result = engine.activate(
        "C:/videos/a.mp4",
        start_pos=1200,
        generation=4,
        autoplay=True,
        view_origin="main",
    )

    session = engine.active_session()
    self.assertIsNotNone(session)
    self.assertEqual(session.path, os.path.normpath("C:/videos/a.mp4"))
    self.assertEqual(session.slot_id, result.slot_id)
    self.assertEqual(session.generation, 4)
    self.assertEqual(session.view_origin, "main")
    self.assertEqual(session.requested_start_pos, 1200)


def test_clear_path_clears_active_watch_session(self):
    slot = make_slot(0)
    engine = make_engine([slot])
    engine.activate("C:/videos/a.mp4", start_pos=0, generation=1, autoplay=True, view_origin="main")

    cleared = engine.clear_path("C:/videos/a.mp4")

    self.assertTrue(cleared)
    self.assertIsNone(engine.active_session())
    self.assertIsNone(engine.active_player())
```

- [ ] **Step 2: Run the focused tests and confirm the expected failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerEngineActivationTest -v
```

Expected: ERROR because `activate()` does not accept `view_origin` and `active_session()` does not exist.

- [ ] **Step 3: Implement WatchSession**

In `src/managers/player_engine.py`, add this dataclass after `ActivationResult`:

```python
@dataclass(frozen=True)
class WatchSession:
    path: str
    slot_id: int
    generation: int
    view_origin: str
    requested_start_pos: int
    last_known_position: int = 0
    preserve_across_menu: bool = True
```

In `PlayerEngine.__init__`, add:

```python
self.watch_session: WatchSession | None = None
```

Add:

```python
def active_session(self):
    return self.watch_session
```

Change the activation signature:

```python
def activate(
    self,
    path: str,
    start_pos: int,
    generation: int,
    autoplay: bool,
    view_origin: str = "",
) -> ActivationResult:
```

After `self.active_slot_id = slot.slot_id`, set:

```python
self.watch_session = WatchSession(
    path=norm_path,
    slot_id=slot.slot_id,
    generation=generation,
    view_origin=view_origin or getattr(slot, "mode", ""),
    requested_start_pos=start_pos,
)
```

In `clear_all()`, add:

```python
self.watch_session = None
```

In `clear_path(...)`, when the cleared slot is active, add:

```python
self.watch_session = None
```

- [ ] **Step 4: Update the existing integration test activation expectation**

In `tests/test_video_sorter.py`, update `FakePlaybackEngine.activate(...)` to accept the new defaulted argument:

```python
def activate(self, path, start_pos, generation, autoplay, view_origin=""):
    self.activate_calls.append((path, start_pos, generation, autoplay, view_origin))
    return type("Activation", (), {"waiting_for_media": False})()
```

Update the existing expected call in `PlayerEngineIntegrationTest` from:

```python
self.assertEqual(window.player_engine.activate_calls, [("C:/videos/b.mp4", 2000, 6, True)])
```

to:

```python
self.assertEqual(window.player_engine.activate_calls, [("C:/videos/b.mp4", 2000, 6, True, "")])
```

- [ ] **Step 5: Run the focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerEngineActivationTest tests.test_video_sorter.PlayerEngineIntegrationTest -v
```

Expected: all focused tests pass.

- [ ] **Step 6: Commit**

```powershell
git add src/managers/player_engine.py tests/test_player_engine.py tests/test_video_sorter.py
git commit -m "feat: track active watch session"
```

---

### Task 3: Make Explicit Activation Replace Watch Globally

**Files:**
- Modify: `tests/test_player_engine.py`
- Modify: `src/managers/player_engine.py`

- [ ] **Step 1: Extend `make_slot(...)` for mode-specific tests**

Change the helper signature in `tests/test_player_engine.py`:

```python
def make_slot(slot_id=0, path=None, state=SlotState.EMPTY, generation=0, role=SlotRole.SPARE, mode="main"):
```

Change the `PlayerSlot(...)` call inside the helper:

```python
slot = PlayerSlot(
    slot_id=slot_id,
    mode=mode,
    player=FakePlayer(),
    audio=FakeAudio(),
    video_item=FakeItem(),
)
```

- [ ] **Step 2: Write failing global-demotion and same-path tests**

Add these tests to `PlayerEngineActivationTest`:

```python
def test_explicit_activation_in_new_mode_demotes_previous_active_slot(self):
    current_mode = {"value": "A"}
    main_slot = make_slot(0, "C:/videos/main.mp4", SlotState.ACTIVE, 1, SlotRole.CURRENT, mode="main")
    a_slot = make_slot(1, mode="A")
    engine = PlayerEngine(
        slots=[main_slot, a_slot],
        fallback_timer=FakeTimer(),
        privacy_guard=FakePrivacy(False),
        autoplay_getter=lambda: True,
        audio_enabled_getter=lambda: True,
        mode_getter=lambda: current_mode["value"],
    )
    engine.active_slot_id = main_slot.slot_id
    engine.watch_session = WatchSession(
        path=os.path.normpath("C:/videos/main.mp4"),
        slot_id=main_slot.slot_id,
        generation=1,
        view_origin="main",
        requested_start_pos=0,
    )

    engine.activate("C:/videos/a.mp4", start_pos=0, generation=2, autoplay=True, view_origin="A")

    self.assertEqual(main_slot.state, SlotState.READY)
    self.assertEqual(main_slot.role, SlotRole.SPARE)
    self.assertEqual(main_slot.video_item.opacity, 0.0)
    self.assertTrue(main_slot.audio.muted)
    self.assertEqual(main_slot.player.pause_count, 1)
    self.assertEqual(engine.active_slot_id, a_slot.slot_id)


def test_activating_same_path_keeps_existing_active_slot_across_modes(self):
    current_mode = {"value": "A"}
    main_slot = make_slot(0, "C:/videos/shared.mp4", SlotState.ACTIVE, 1, SlotRole.CURRENT, mode="main")
    a_slot = make_slot(1, mode="A")
    engine = PlayerEngine(
        slots=[main_slot, a_slot],
        fallback_timer=FakeTimer(),
        privacy_guard=FakePrivacy(False),
        autoplay_getter=lambda: True,
        audio_enabled_getter=lambda: True,
        mode_getter=lambda: current_mode["value"],
    )
    engine.active_slot_id = main_slot.slot_id

    result = engine.activate("C:/videos/shared.mp4", start_pos=3000, generation=2, autoplay=True, view_origin="A")

    self.assertEqual(result.slot_id, main_slot.slot_id)
    self.assertTrue(result.reused_source)
    self.assertEqual(len(a_slot.player.set_source_calls), 0)
    self.assertEqual(engine.active_session().slot_id, main_slot.slot_id)
```

- [ ] **Step 3: Run the focused tests and confirm the expected failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerEngineActivationTest -v
```

Expected: FAIL because `_demote_other_active_slots(...)` only considers active slots in the current visible mode and same-path cross-mode activation does not reuse the existing active slot.

- [ ] **Step 4: Implement global active-slot handling**

In `PlayerEngine`, add:

```python
def _active_slot_matching_source(self, path: str):
    slot = self.active_slot()
    if slot is not None and slot.state == SlotState.ACTIVE and source_matches_path(slot, path):
        return slot
    return None
```

At the beginning of `activate(...)`, after `norm_path = self._normalize_path(path)`, prefer the current active slot:

```python
slot = self._active_slot_matching_source(norm_path)
if slot is not None:
    slot.expected_generation = generation
    self._set_slot_path(slot, norm_path)
else:
    slot = self._find_valid_slot(norm_path, generation)
    if slot is None:
        slot = self._find_loaded_slot_by_source(norm_path)
        if slot is not None:
            slot.expected_generation = generation
            self._set_slot_path(slot, norm_path)
reused = slot is not None
```

Remove the old duplicate `slot = self._find_valid_slot(...)` block from `activate(...)`.

Change `_demote_other_active_slots(...)` to iterate every slot:

```python
def _demote_other_active_slots(self, active_slot):
    for slot in self.slots:
        if slot is active_slot:
            continue
        if slot.state == SlotState.ACTIVE:
            slot.video_item.setOpacity(0.0)
            slot.video_item.setZValue(0.0)
            slot.audio.setMuted(True)
            slot.player.pause()
            slot.expected_generation = self.current_generation
            slot.state = SlotState.READY
            slot.role = SlotRole.SPARE
```

- [ ] **Step 5: Run the focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerEngineActivationTest -v
```

Expected: all activation tests pass.

- [ ] **Step 6: Commit**

```powershell
git add src/managers/player_engine.py tests/test_player_engine.py
git commit -m "fix: replace watch sessions across modes safely"
```

---

### Task 4: Route VideoSorter Controls To The Watch Session

**Files:**
- Modify: `tests/test_video_sorter.py`
- Modify: `main.py`

- [ ] **Step 1: Write failing property routing tests**

Add this test class to `tests/test_video_sorter.py`:

```python
class PlayerPropertyRoutingTest(unittest.TestCase):
    def test_player_property_prefers_engine_active_player(self):
        engine_player = object()
        manager_player = object()

        class Engine:
            def active_player(self):
                return engine_player

        class Manager:
            def get_active_player(self):
                return {"player": manager_player, "audio": object()}

        window = type("FakeWindow", (), {})()
        window.player_engine = Engine()
        window.player_manager = Manager()

        self.assertIs(VideoSorter.player.fget(window), engine_player)

    def test_player_property_falls_back_to_manager_when_engine_has_no_active_player(self):
        manager_player = object()

        class Engine:
            def active_player(self):
                return None

        class Manager:
            def get_active_player(self):
                return {"player": manager_player, "audio": object()}

        window = type("FakeWindow", (), {})()
        window.player_engine = Engine()
        window.player_manager = Manager()

        self.assertIs(VideoSorter.player.fget(window), manager_player)

    def test_audio_output_property_prefers_engine_active_audio(self):
        engine_audio = object()
        manager_audio = object()

        class Engine:
            def active_audio(self):
                return engine_audio

        class Manager:
            def get_active_player(self):
                return {"player": object(), "audio": manager_audio}

        window = type("FakeWindow", (), {})()
        window.player_engine = Engine()
        window.player_manager = Manager()

        self.assertIs(VideoSorter.audio_output.fget(window), engine_audio)
```

- [ ] **Step 2: Run the focused tests and confirm the expected failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_video_sorter.PlayerPropertyRoutingTest -v
```

Expected: FAIL because `VideoSorter.player` and `audio_output` always use `PlayerManager.current_mode`.

- [ ] **Step 3: Implement property routing**

In `main.py`, replace the `player` and `audio_output` properties with:

```python
@property
def player(self) -> QMediaPlayer:
    """Return the player that owns the active watch session."""
    if hasattr(self, "player_engine"):
        active = self.player_engine.active_player()
        if active is not None:
            return active
    return self.player_manager.get_active_player()["player"]

@property
def audio_output(self) -> QAudioOutput:
    """Return the audio output for the active watch session."""
    if hasattr(self, "player_engine"):
        active = self.player_engine.active_audio()
        if active is not None:
            return active
    return self.player_manager.get_active_player()["audio"]
```

- [ ] **Step 4: Run the focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_video_sorter.PlayerPropertyRoutingTest -v
```

Expected: all `PlayerPropertyRoutingTest` tests pass.

- [ ] **Step 5: Commit**

```powershell
git add main.py tests/test_video_sorter.py
git commit -m "fix: route controls to active watch player"
```

---

### Task 5: Split Candidate Selection From Playback Activation

**Files:**
- Modify: `tests/test_video_sorter.py`
- Modify: `main.py`

- [ ] **Step 1: Write failing helper tests**

Add minimal fakes near the existing fakes in `tests/test_video_sorter.py`:

```python
class FakeSelectableItem:
    def __init__(self, path):
        self.path = path

    def data(self, role):
        if role == Qt.ItemDataRole.UserRole:
            return self.path
        return None


class FakeSelectableList:
    def __init__(self, paths):
        self.items = [FakeSelectableItem(path) for path in paths]
        self.current_row = -1
        self.block_history = []
        self.scrolled_to = None

    def count(self):
        return len(self.items)

    def item(self, row):
        return self.items[row]

    def setCurrentRow(self, row):
        self.current_row = row

    def currentRow(self):
        return self.current_row

    def scrollToItem(self, item, hint=None):
        self.scrolled_to = item

    def blockSignals(self, blocked):
        self.block_history.append(blocked)
```

Add this test class:

```python
class PassiveListRefreshTest(unittest.TestCase):
    def test_preserve_policy_selects_watch_path_without_playing(self):
        window = type("FakeWindow", (), {})()
        window.file_list = FakeSelectableList(["C:/videos/a.mp4", "C:/videos/b.mp4"])
        window.play_calls = []
        window.last_main_path = None
        window.last_main_row = 0

        class Engine:
            def active_session(self):
                return type("Session", (), {"path": os.path.normpath("C:/videos/b.mp4")})()

        window.player_engine = Engine()
        window.play_video = lambda row, specific_start_pos=None: window.play_calls.append((row, specific_start_pos))

        VideoSorter._maybe_activate_after_list_refresh(window, "A", "preserve")

        self.assertEqual(window.file_list.current_row, 1)
        self.assertEqual(window.play_calls, [])

    def test_auto_if_no_watch_plays_main_restored_row(self):
        window = type("FakeWindow", (), {})()
        window.file_list = FakeSelectableList(["C:/videos/a.mp4", "C:/videos/b.mp4"])
        window.play_calls = []
        window.last_main_path = "C:/videos/b.mp4"
        window.last_main_row = 0
        window.last_main_pos = 2400
        window.player_engine = type("Engine", (), {"active_session": lambda self: None})()
        window.play_video = lambda row, specific_start_pos=None: window.play_calls.append((row, specific_start_pos))

        VideoSorter._maybe_activate_after_list_refresh(window, "main", "auto_if_no_watch")

        self.assertEqual(window.file_list.current_row, 1)
        self.assertEqual(window.play_calls, [(1, 2400)])

    def test_auto_if_no_watch_preserves_when_watch_exists(self):
        window = type("FakeWindow", (), {})()
        window.file_list = FakeSelectableList(["C:/videos/a.mp4"])
        window.play_calls = []
        window.last_main_path = None
        window.last_main_row = 0
        window.player_engine = type("Engine", (), {"active_session": lambda self: object()})()
        window.play_video = lambda row, specific_start_pos=None: window.play_calls.append((row, specific_start_pos))

        VideoSorter._maybe_activate_after_list_refresh(window, "main", "auto_if_no_watch")

        self.assertEqual(window.file_list.current_row, 0)
        self.assertEqual(window.play_calls, [])
```

- [ ] **Step 2: Run the focused tests and confirm the expected failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_video_sorter.PassiveListRefreshTest -v
```

Expected: ERROR because `_maybe_activate_after_list_refresh(...)` does not exist.

- [ ] **Step 3: Implement watch/candidate helper methods**

Add these methods to `VideoSorter` near `_current_playlist_items(...)`:

```python
def _active_watch_session(self):
    if hasattr(self, "player_engine"):
        return self.player_engine.active_session()
    return None

def _has_active_watch_session(self) -> bool:
    session = self._active_watch_session()
    return session is not None and bool(getattr(session, "path", None))

def _row_for_path(self, path: str | None) -> int:
    if not path:
        return -1
    target = os.path.normcase(os.path.normpath(path))
    for row in range(self.file_list.count()):
        item = self.file_list.item(row)
        if item is None:
            continue
        item_path = item.data(Qt.ItemDataRole.UserRole)
        if item_path and os.path.normcase(os.path.normpath(item_path)) == target:
            return row
    return -1

def _select_candidate_row(self, row: int) -> None:
    if row < 0 or row >= self.file_list.count():
        return
    self.file_list.setCurrentRow(row)
    item = self.file_list.item(row)
    if item is not None:
        self.file_list.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)

def _candidate_row_for_target_mode(self, target_mode: str) -> int:
    session = self._active_watch_session()
    session_row = self._row_for_path(getattr(session, "path", None))
    if session_row >= 0:
        return session_row
    if target_mode == "main":
        path_row = self._row_for_path(getattr(self, "last_main_path", None))
        if path_row >= 0:
            return path_row
        return max(0, min(getattr(self, "last_main_row", 0), self.file_list.count() - 1))
    return 0

def _maybe_activate_after_list_refresh(self, target_mode: str, activation_policy: str) -> None:
    if self.file_list.count() <= 0:
        return

    target_row = self._candidate_row_for_target_mode(target_mode)
    self._select_candidate_row(target_row)

    if activation_policy == "preserve":
        return
    if activation_policy == "auto_if_no_watch" and self._has_active_watch_session():
        return

    if target_mode == "main":
        start_pos = self.last_main_pos if getattr(self, "last_main_pos", 0) > 0 else 0
        self.play_video(target_row, specific_start_pos=start_pos)
    else:
        self.play_video(target_row)
```

- [ ] **Step 4: Run the focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_video_sorter.PassiveListRefreshTest -v
```

Expected: all `PassiveListRefreshTest` tests pass.

- [ ] **Step 5: Commit**

```powershell
git add main.py tests/test_video_sorter.py
git commit -m "refactor: separate list selection from playback"
```

---

### Task 6: Make update_ui_mode Use Activation Policy

**Files:**
- Modify: `tests/test_video_sorter.py`
- Modify: `main.py`

- [ ] **Step 1: Write focused behavior tests for passive update policy**

Add this test to `PassiveListRefreshTest`:

```python
def test_change_view_mode_requests_preserve_refresh(self):
    class FileManager:
        current_mode = "main"
        is_trash_mode = False
        filter_type = None

        def set_search_keyword(self, value):
            self.search_keyword = value

        def set_view_state(self, mode, filter_type, is_trash):
            self.view_state = (mode, filter_type, is_trash)

    class Input:
        def blockSignals(self, blocked):
            pass

        def clear(self):
            self.cleared = True

    window = type("FakeWindow", (), {})()
    window.file_manager = FileManager()
    window.input_search = Input()
    window.btn_filter_a = type("Button", (), {"setChecked": lambda self, value: setattr(self, "checked", value)})()
    window.btn_filter_b = type("Button", (), {"setChecked": lambda self, value: setattr(self, "checked", value)})()
    window.save_main_state = lambda: setattr(window, "saved_main", True)
    window.update_calls = []
    window.update_ui_mode = lambda activation_policy="auto_if_no_watch": window.update_calls.append(activation_policy)

    VideoSorter._change_view_mode(window, "highlight", None, False)

    self.assertEqual(window.update_calls, ["preserve"])
    self.assertTrue(window.saved_main)
```

- [ ] **Step 2: Run the focused test and confirm the expected failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_video_sorter.PassiveListRefreshTest.test_change_view_mode_requests_preserve_refresh -v
```

Expected: FAIL because `_change_view_mode(...)` calls `update_ui_mode()` without `activation_policy="preserve"`.

- [ ] **Step 3: Change `update_ui_mode` signature**

In `main.py`, change:

```python
def update_ui_mode(self):
```

to:

```python
def update_ui_mode(self, activation_policy: str = "auto_if_no_watch"):
```

- [ ] **Step 4: Make menu switches passive**

In `_change_view_mode(...)`, change:

```python
self.update_ui_mode()
```

to:

```python
self.update_ui_mode(activation_policy="preserve")
```

- [ ] **Step 5: Make player mode switch passive**

In `update_ui_mode(...)`, keep the mode change passive:

```python
self.player_manager.switch_mode(target_mode, preserve_current=True)
```

- [ ] **Step 6: Replace direct auto-play block in `update_ui_mode(...)`**

Replace the current block that sets rows and calls `play_video(...)` with:

```python
if self.file_list.count() > 0:
    self.video_view.set_progressbar_visible(True)

    if self.input_search.hasFocus():
        self.file_list.blockSignals(False)
        return

    self._maybe_activate_after_list_refresh(target_mode, activation_policy)
else:
    if self._has_active_watch_session():
        self.video_view.set_progressbar_visible(True)
    else:
        self.video_view.set_progressbar_visible(False)
        self.reset_viewer_state()
```

- [ ] **Step 7: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_video_sorter.PassiveListRefreshTest tests.test_player_manager.PlayerManagerTest -v
```

Expected: all focused tests pass.

- [ ] **Step 8: Commit**

```powershell
git add main.py tests/test_video_sorter.py
git commit -m "fix: keep menu refresh passive"
```

---

### Task 7: Update Search, Load, And Folder Flows

**Files:**
- Modify: `tests/test_video_sorter.py`
- Modify: `main.py`
- Modify: `src/core/event_handler.py`

- [ ] **Step 1: Write failing tests for search refresh policy**

Update existing tests that define fake `update_ui_mode(self)` methods so they accept the policy:

```python
def update_ui_mode(self, activation_policy="auto_if_no_watch"):
    self.updated = activation_policy
```

Add this test to the search-related test class:

```python
def test_execute_search_uses_preserve_refresh_policy(self):
    class FakeWindow:
        def update_ui_mode(self, activation_policy="auto_if_no_watch"):
            self.updated_policy = activation_policy

    window = FakeWindow()
    window.root_folder = "C:/videos"
    window._pending_search_text = "sample"
    window.file_manager = FakeFileManager()
    window.file_list = FakeFileList()
    window.lbl_info = FakeLabel()

    VideoSorter._execute_search(window)

    self.assertEqual(window.updated_policy, "preserve")
```

- [ ] **Step 2: Run focused tests and confirm the expected failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_video_sorter.SearchBehaviorTest -v
```

The broad fallback command is:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_video_sorter -v
```

Expected: at least the new search policy test fails because search uses the default activation policy.

- [ ] **Step 3: Change search refresh calls to preserve**

In `on_search_changed(...)`, replace both empty-search refresh calls:

```python
self.update_ui_mode()
```

with:

```python
self.update_ui_mode(activation_policy="preserve")
```

In `_execute_search(...)`, replace both refresh calls:

```python
self.update_ui_mode()
```

with:

```python
self.update_ui_mode(activation_policy="preserve")
```

- [ ] **Step 4: Keep folder load auto only when there is no watch session**

In `load_files(...)`, keep:

```python
self.update_ui_mode()
```

because the new default is `auto_if_no_watch`.

In `on_folder_history_clicked(...)`, keep explicit destructive folder behavior, but change it from main-only release to full watch reset:

```python
if hasattr(self, "player_engine"):
    self.player_engine.clear_all()
else:
    self.player_manager.stop_all_in_mode("main")
```

This is correct because folder switching invalidates the current visible library context.

- [ ] **Step 5: Prevent Tab focus from auto-playing the first search result**

In `src/core/event_handler.py`, inside `_handle_tab_navigation(...)`, remove the automatic playback call after selecting the first row:

```python
# Remove this call:
m.play_video(0)
```

Tab should move focus and select a candidate. The user can press Enter, click, or use explicit navigation to start playback.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_video_sorter -v
```

Expected: all `test_video_sorter` tests pass.

- [ ] **Step 7: Commit**

```powershell
git add main.py src/core/event_handler.py tests/test_video_sorter.py
git commit -m "fix: preserve playback during search and focus changes"
```

---

### Task 8: Make File Actions Watch-Path Aware

**Files:**
- Modify: `tests/test_file_action_controller.py`
- Modify: `src/controllers/file_action_controller.py`
- Modify: `main.py`

- [ ] **Step 1: Add a watch-path helper to VideoSorter**

Add tests to `tests/test_video_sorter.py`:

```python
class WatchPathMatchingTest(unittest.TestCase):
    def test_is_active_watch_path_matches_normalized_session_path(self):
        class Engine:
            def active_session(self):
                return type("Session", (), {"path": os.path.normpath("C:/videos/a.mp4")})()

        window = type("FakeWindow", (), {})()
        window.player_engine = Engine()

        self.assertTrue(VideoSorter.is_active_watch_path(window, "C:/videos/./a.mp4"))
        self.assertFalse(VideoSorter.is_active_watch_path(window, "C:/videos/b.mp4"))
```

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_video_sorter.WatchPathMatchingTest -v
```

Expected: ERROR because `is_active_watch_path(...)` does not exist.

- [ ] **Step 2: Implement watch-path matching**

Add this method to `VideoSorter` near `_has_active_watch_session(...)`:

```python
def is_active_watch_path(self, path: str | None) -> bool:
    if not path:
        return False
    session = self._active_watch_session()
    session_path = getattr(session, "path", None)
    if not session_path:
        return False
    return os.path.normcase(os.path.normpath(session_path)) == os.path.normcase(os.path.normpath(path))
```

- [ ] **Step 3: Add file-action regression tests**

Add tests in `tests/test_file_action_controller.py` for the two branches:

```python
def test_hard_delete_visible_candidate_does_not_auto_play_next_when_not_active_watch(self):
    app = make_file_action_app()
    app.active_watch_path = "C:/videos/watching.mp4"
    app.is_active_watch_path = lambda path: os.path.normcase(os.path.normpath(path)) == os.path.normcase(os.path.normpath(app.active_watch_path))
    app.play_calls = []
    app.auto_play_next = lambda row: app.play_calls.append(row)
    app.file_list.current_path = "C:/videos/delete.mp4"
    app.file_manager.hard_delete_success = True

    with patch("src.controllers.file_action_controller.ThemeMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
        app.file_action.hard_delete_file()

    self.assertEqual(app.play_calls, [])


def test_hard_delete_active_watch_auto_plays_next_after_release(self):
    app = make_file_action_app()
    app.active_watch_path = "C:/videos/delete.mp4"
    app.is_active_watch_path = lambda path: os.path.normcase(os.path.normpath(path)) == os.path.normcase(os.path.normpath(app.active_watch_path))
    app.play_calls = []
    app.auto_play_next = lambda row: app.play_calls.append(row)
    app.file_list.current_path = "C:/videos/delete.mp4"
    app.file_manager.hard_delete_success = True

    with patch("src.controllers.file_action_controller.ThemeMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
        app.file_action.hard_delete_file()

    self.assertEqual(app.play_calls, [0])
```

Use the existing fake app factory and fake list names in `tests/test_file_action_controller.py`. If the helper names differ, adapt only the fake wiring, not the expected behavior.

- [ ] **Step 4: Run focused file-action tests and confirm the expected failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_file_action_controller -v
```

Expected: new candidate-delete test fails because `hard_delete_file()` always calls `auto_play_next(row)`.

- [ ] **Step 5: Change auto-advance policy in file actions**

In `hard_delete_file(...)`, compute before releasing:

```python
was_active_watch = (
    not hasattr(self.app, "is_active_watch_path")
    or self.app.is_active_watch_path(path)
)
```

After successful delete, replace:

```python
self.app.auto_play_next(row)
```

with:

```python
if was_active_watch:
    self.app.auto_play_next(row)
else:
    self.app.file_list.blockSignals(True)
    next_row = min(row, self.app.file_list.count() - 1)
    if next_row >= 0:
        self.app.file_list.setCurrentRow(next_row)
    self.app.file_list.blockSignals(False)
```

Apply the same pattern to `soft_delete_file(...)`, `restore_file(...)`, and `delete_current_highlight_item(...)`.

For `delete_all_trash_files(...)`, replace the unconditional reset:

```python
self.app.reset_viewer_state()
```

with:

```python
active_deleted = any(
    hasattr(self.app, "is_active_watch_path") and self.app.is_active_watch_path(path)
    for path in trash_paths
)
if active_deleted:
    self.app.reset_viewer_state()
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_file_action_controller tests.test_video_sorter.WatchPathMatchingTest -v
```

Expected: all focused tests pass.

- [ ] **Step 7: Commit**

```powershell
git add main.py src/controllers/file_action_controller.py tests/test_file_action_controller.py tests/test_video_sorter.py
git commit -m "fix: keep file actions watch-session aware"
```

---

### Task 9: Update Playback Documentation

**Files:**
- Modify: `docs/maintenance/playback-state.md`

- [ ] **Step 1: Update mode-switching documentation**

Replace the `## Mode Switching` section with:

```markdown
## Mode Switching

Visible menu mode and active playback are separate.

`switch_mode(target_mode, preserve_current=True)` is passive by default:

- it changes the visible player/list mode,
- it does not stop the active watch player,
- it does not clear the active watch media source,
- it does not auto-play row 0 in the target list.

Explicit destructive paths still release media handles:

- `PlayerEngine.clear_all()` for full reset, folder context replacement, and app shutdown,
- `PlayerEngine.clear_path(path)` before hard delete or rename,
- `PlayerManager.cleanup()` on app close,
- `PlayerManager.stop_and_release_path(path)` as a legacy fallback.

A/B tag, highlight, trash, and search views rebuild candidate lists while the watch session continues until the user explicitly activates another video or the active file is invalidated.
```

- [ ] **Step 2: Run docs/static tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_packaging_static -v
```

Expected: packaging/static tests pass, or report the exact failing assertion to update in Task 11.

- [ ] **Step 3: Commit**

```powershell
git add docs/maintenance/playback-state.md
git commit -m "docs: describe passive playback mode switching"
```

---

### Task 10: Run Full Automated Verification And Fix Regressions

**Files:**
- Modify only files required by failing tests.

- [ ] **Step 1: Run full checks**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_checks.ps1
```

Expected: all unittest, compile, GUI startup smoke, release audit, scan/cache smoke, and import smoke steps pass.

- [ ] **Step 2: Fix every failure by root cause**

Use this rule for every failure:

```text
Read the failing assertion or traceback.
Identify the exact caller contract that changed.
Add or adjust the narrowest regression test if the failure exposes untested behavior.
Patch the production code once.
Rerun the focused failing test.
Rerun tools/run_checks.ps1 after all focused failures are resolved.
```

- [ ] **Step 3: Update automated test count docs when the count changes**

If `tools/run_checks.ps1` reports a new unittest count and a static test asserts the old count, update the count in the relevant docs. The current known count after the continuity implementation is `192`.

- [ ] **Step 4: Commit verification/doc-count changes**

```powershell
git add main.py src tests docs
git commit -m "test: verify player continuity refactor"
```

When verification creates no file changes, do not create an empty commit; record the verification result in the final implementation summary.

---

### Task 11: Direct GUI Continuity Smoke

**Files:**
- Modify: `docs/maintenance/manual-smoke-test.md` if the checklist needs a new section.
- Modify production/test files only if a reproduced GUI issue requires a fix.

- [ ] **Step 1: Start the source app with isolated app data**

Run:

```powershell
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = (Resolve-Path '.\.venv\Scripts\pythonw.exe')
$psi.Arguments = 'main.py'
$psi.WorkingDirectory = (Get-Location).Path
$psi.Environment['LOCALAPPDATA'] = (Resolve-Path '.\manual_test_appdata')
$psi.Environment['QT_LOGGING_RULES'] = '*.debug=false'
$p = [System.Diagnostics.Process]::Start($psi)
Write-Output "YDManager_PID=$($p.Id)"
```

Expected: source app opens and returns a PID.

- [ ] **Step 2: Exercise menu round trips**

Use direct desktop control to perform this sequence:

```text
1. Load the local manual media fixture.
2. Start a known video.
3. Wait until playback position is greater than zero.
4. Switch to A tag view.
5. Return to main.
6. Switch to B tag view.
7. Return to main.
8. Switch to highlight view.
9. Return to main.
10. Switch to trash view.
11. Return to main.
12. Type a search query.
13. Clear the search query.
```

Expected after every passive switch:

```text
watched path unchanged
playback position not reset to zero
no persistent black frame
play/pause controls still affect the watched video
seek/wheel controls still affect the watched video
visible candidate list can change without stealing playback
```

- [ ] **Step 3: Exercise destructive exceptions**

Use disposable media only:

```text
1. Soft delete the active video.
2. Confirm playback advances intentionally to the next valid item.
3. Restore a non-active trash item.
4. Confirm playback does not change.
5. Hard delete a non-active trash item.
6. Confirm playback does not change.
7. Rename the active video with # toggle.
8. Confirm the file handle is released and playback resumes at the prior position.
```

- [ ] **Step 4: Record GUI smoke result**

Append this section to `docs/maintenance/manual-smoke-test.md`:

```markdown
## Player Engine v3 Continuity Smoke

Date: 2026-06-15

- Main -> A -> Main: record observed result
- Main -> B -> Main: record observed result
- Main -> Highlight -> Main: record observed result
- Main -> Trash -> Main: record observed result
- Search while watching: record observed result
- Non-active trash delete/restore does not steal playback: record observed result
- Active delete/rename intentionally replaces or resumes playback: record observed result
```

Replace every `record observed result` item with the measured outcome before committing.

- [ ] **Step 5: Commit smoke documentation and fixes**

```powershell
git add docs/maintenance/manual-smoke-test.md main.py src tests
git commit -m "test: record player continuity smoke"
```

---

### Task 12: Final Push And Handoff

**Files:**
- No planned file edits.

- [ ] **Step 1: Run final verification**

Run:

```powershell
git status -sb
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_checks.ps1
git log --oneline -8
```

Expected:

```text
working tree clean except intentional uncommitted smoke artifacts
tools/run_checks.ps1 exits 0
recent commits show the v3 continuity sequence
```

- [ ] **Step 2: Push**

Run:

```powershell
git push
```

Expected: branch pushes successfully to `origin/codex/player-engine-stabilization`.

- [ ] **Step 3: Final implementation summary**

Report:

```text
- commits created
- files changed
- automated verification command and result
- GUI smoke result
- any remaining risk or follow-up item
```

Do not claim smooth playback is fixed unless automated tests and direct GUI smoke have both been run in this implementation pass.
