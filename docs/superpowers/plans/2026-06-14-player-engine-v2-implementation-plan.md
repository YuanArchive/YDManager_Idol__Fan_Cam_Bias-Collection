# Player Engine v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic player engine that makes rapid next/previous video browsing stable, preload-aware, and guarded against black-screen, stale-source, privacy, delete, restore, and mode-switch regressions.

**Architecture:** Add `src/managers/player_engine.py` as a focused state-machine layer around the existing `PlayerManager` pool. `VideoSorter` keeps UI coordination, but activation, preload planning, reveal validation, slot clearing, and media-status handling move behind the engine boundary.

**Tech Stack:** Python 3.10, PyQt6 Qt Multimedia, unittest, fake QMediaPlayer-style test doubles, existing PowerShell verification scripts.

---

## File Structure

- Create: `src/managers/player_engine.py`
  - Owns `SlotState`, `SlotRole`, `PlaybackItem`, `ActivationResult`, `PlayerSlot`, and `PlayerEngine`.
  - Contains pure state transitions where possible so tests can run without constructing Qt objects.
- Create: `tests/test_player_engine.py`
  - Unit tests for preload state, activation, reveal guards, failed media, generation guards, and slot clearing.
- Modify: `src/managers/player_manager.py`
  - Keep existing Qt player pool creation.
  - Add small helpers needed by `PlayerEngine`, such as iterating current-mode slots and looking up slot indexes.
- Modify: `main.py`
  - Instantiate `PlayerEngine`.
  - Delegate `play_video()`, preload, status, position, reset, and mode-switch related playback decisions.
  - Maintain playlist generation.
- Modify: `src/controllers/file_action_controller.py`
  - Replace direct QMediaPlayer resets with engine calls where file path state changes.
  - Prevent duplicate playback entry after delete/restore.
- Modify: `src/core/event_handler.py`
  - Use the shared privacy predicate where shortcut blocking depends on privacy state.
- Modify: `tools/smoke_video_workflow.py`
  - Add generated-video checks for preload promotion and mode-switch cleanup.
- Modify: `docs/maintenance/playback-state.md`
  - Replace old opportunistic preload notes with v2 state-machine rules.
- Modify: `docs/maintenance/manual-smoke-test.md`
  - Add rapid navigation and privacy auto-play-off checks.

---

## Task 1: Player Engine State Model

**Files:**
- Create: `src/managers/player_engine.py`
- Create: `tests/test_player_engine.py`

- [ ] **Step 1: Write failing tests for state model defaults**

Add this initial test file:

```python
import os
import unittest

from src.managers.player_engine import (
    PlayerSlot,
    SlotRole,
    SlotState,
)


class FakeSource:
    def __init__(self, path=""):
        self.path = path

    def toLocalFile(self):
        return self.path


class FakePlayer:
    def __init__(self):
        self.source_path = ""
        self.set_source_calls = []
        self.stop_count = 0
        self.play_count = 0
        self.pause_count = 0
        self.position = 0
        self.rate = 1.0
        self.status = None
        self.blocked = False

    def source(self):
        return FakeSource(self.source_path)

    def setSource(self, source):
        self.set_source_calls.append(source)
        if hasattr(source, "toLocalFile"):
            self.source_path = source.toLocalFile()
        else:
            self.source_path = ""

    def stop(self):
        self.stop_count += 1

    def play(self):
        self.play_count += 1

    def pause(self):
        self.pause_count += 1

    def setPosition(self, position):
        self.position = position

    def setPlaybackRate(self, rate):
        self.rate = rate

    def mediaStatus(self):
        return self.status

    def blockSignals(self, blocked):
        self.blocked = blocked


class FakeAudio:
    def __init__(self):
        self.muted = False

    def setMuted(self, muted):
        self.muted = muted


class FakeItem:
    def __init__(self):
        self.opacity = 0.0
        self.z = 0.0

    def setOpacity(self, opacity):
        self.opacity = opacity

    def setZValue(self, z):
        self.z = z


def make_slot(slot_id=0, path=None, state=SlotState.EMPTY, generation=0, role=SlotRole.SPARE):
    slot = PlayerSlot(
        slot_id=slot_id,
        mode="main",
        player=FakePlayer(),
        audio=FakeAudio(),
        video_item=FakeItem(),
    )
    slot.expected_path = path
    slot.expected_generation = generation
    slot.state = state
    slot.role = role
    if path:
        slot.player.source_path = os.path.normpath(path)
    return slot


class PlayerSlotStateTest(unittest.TestCase):
    def test_new_slot_defaults_to_empty_spare(self):
        slot = make_slot()

        self.assertEqual(slot.state, SlotState.EMPTY)
        self.assertEqual(slot.role, SlotRole.SPARE)
        self.assertIsNone(slot.expected_path)
        self.assertEqual(slot.expected_generation, 0)
        self.assertIsNone(slot.last_error)
        self.assertIsNone(slot.last_status)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerSlotStateTest.test_new_slot_defaults_to_empty_spare -v
```

Expected result:

```text
ImportError: No module named 'src.managers.player_engine'
```

- [ ] **Step 3: Add the minimal state model**

Create `src/managers/player_engine.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SlotState(str, Enum):
    EMPTY = "empty"
    PRELOADING = "preloading"
    READY = "ready"
    ACTIVE = "active"
    FAILED = "failed"
    STALE = "stale"


class SlotRole(str, Enum):
    CURRENT = "current"
    NEXT = "next"
    PREVIOUS = "previous"
    SPARE = "spare"


@dataclass(frozen=True)
class PlaybackItem:
    path: str
    start_pos: int = 0


@dataclass
class ActivationResult:
    slot_id: int
    path: str
    reused_source: bool
    waiting_for_media: bool
    fallback_required: bool


@dataclass
class PlayerSlot:
    slot_id: int
    mode: str
    player: Any
    audio: Any
    video_item: Any
    expected_path: str | None = None
    expected_generation: int = 0
    state: SlotState = SlotState.EMPTY
    role: SlotRole = SlotRole.SPARE
    last_error: str | None = None
    last_status: Any = None
    requested_start_pos: int = 0
```

- [ ] **Step 4: Run the test and verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerSlotStateTest.test_new_slot_defaults_to_empty_spare -v
```

Expected result:

```text
OK
```

- [ ] **Step 5: Commit**

```powershell
git add src/managers/player_engine.py tests/test_player_engine.py
git commit -m "add player engine state model"
```

---

## Task 2: Slot Clearing And Source Validation

**Files:**
- Modify: `src/managers/player_engine.py`
- Modify: `tests/test_player_engine.py`

- [ ] **Step 1: Write failing tests for clear and source validation**

Append to `tests/test_player_engine.py`:

```python
from src.managers.player_engine import source_matches_path


class PlayerSlotClearTest(unittest.TestCase):
    def test_clear_slot_releases_media_and_hides_item(self):
        slot = make_slot(path="C:/videos/a.mp4", state=SlotState.READY, generation=3, role=SlotRole.NEXT)

        slot.clear()

        self.assertEqual(slot.state, SlotState.EMPTY)
        self.assertEqual(slot.role, SlotRole.SPARE)
        self.assertIsNone(slot.expected_path)
        self.assertEqual(slot.expected_generation, 0)
        self.assertEqual(slot.player.stop_count, 1)
        self.assertEqual(slot.player.source_path, "")
        self.assertTrue(slot.audio.muted)
        self.assertEqual(slot.video_item.opacity, 0.0)
        self.assertEqual(slot.video_item.z, 0.0)

    def test_source_matches_path_uses_real_player_source_not_only_metadata(self):
        slot = make_slot(path="C:/videos/a.mp4", state=SlotState.READY, generation=1)
        slot.expected_path = "C:/videos/b.mp4"

        self.assertFalse(source_matches_path(slot, "C:/videos/b.mp4"))
        self.assertTrue(source_matches_path(slot, "C:/videos/a.mp4"))
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerSlotClearTest -v
```

Expected result:

```text
AttributeError: 'PlayerSlot' object has no attribute 'clear'
```

- [ ] **Step 3: Implement clear and source validation**

Add to `src/managers/player_engine.py`:

```python
import os


def _empty_qurl():
    try:
        from PyQt6.QtCore import QUrl
        return QUrl()
    except Exception:
        return None


def _source_path(player: Any) -> str:
    try:
        source = player.source()
        if source and hasattr(source, "toLocalFile"):
            return os.path.normpath(source.toLocalFile())
    except Exception:
        return ""
    return ""


def source_matches_path(slot: PlayerSlot, path: str) -> bool:
    source_path = _source_path(slot.player)
    if not source_path or not path:
        return False
    return os.path.normcase(source_path) == os.path.normcase(os.path.normpath(path))
```

Add this method to `PlayerSlot`:

```python
    def clear(self) -> None:
        self.player.stop()
        self.player.setSource(_empty_qurl())
        self.audio.setMuted(True)
        self.video_item.setOpacity(0.0)
        self.video_item.setZValue(0.0)
        self.expected_path = None
        self.expected_generation = 0
        self.state = SlotState.EMPTY
        self.role = SlotRole.SPARE
        self.last_error = None
        self.last_status = None
        self.requested_start_pos = 0
```

- [ ] **Step 4: Run the tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerSlotClearTest -v
```

Expected result:

```text
OK
```

- [ ] **Step 5: Commit**

```powershell
git add src/managers/player_engine.py tests/test_player_engine.py
git commit -m "add player slot clearing"
```

---

## Task 3: Core Activation And Preload Promotion

**Files:**
- Modify: `src/managers/player_engine.py`
- Modify: `tests/test_player_engine.py`

- [ ] **Step 1: Write failing activation tests**

Append to `tests/test_player_engine.py`:

```python
from src.managers.player_engine import PlayerEngine


class FakeTimer:
    def __init__(self):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class FakePrivacy:
    def __init__(self, blocked=False):
        self.blocked = blocked

    def __call__(self):
        return self.blocked


def make_engine(slots, privacy_blocked=False):
    return PlayerEngine(
        slots=slots,
        fallback_timer=FakeTimer(),
        privacy_guard=FakePrivacy(privacy_blocked),
        autoplay_getter=lambda: True,
        audio_enabled_getter=lambda: True,
    )


class PlayerEngineActivationTest(unittest.TestCase):
    def test_ready_preload_promotes_without_setting_source_again(self):
        slot = make_slot(1, "C:/videos/next.mp4", SlotState.READY, 7, SlotRole.NEXT)
        engine = make_engine([make_slot(0, "C:/videos/current.mp4", SlotState.ACTIVE, 7, SlotRole.CURRENT), slot])

        result = engine.activate("C:/videos/next.mp4", start_pos=0, generation=7, autoplay=True)

        self.assertEqual(result.slot_id, 1)
        self.assertTrue(result.reused_source)
        self.assertFalse(result.waiting_for_media)
        self.assertEqual(slot.state, SlotState.ACTIVE)
        self.assertEqual(slot.role, SlotRole.CURRENT)
        self.assertEqual(len(slot.player.set_source_calls), 0)

    def test_preloading_hit_promotes_and_arms_fallback(self):
        slot = make_slot(1, "C:/videos/next.mp4", SlotState.PRELOADING, 7, SlotRole.NEXT)
        engine = make_engine([make_slot(0, "C:/videos/current.mp4", SlotState.ACTIVE, 7, SlotRole.CURRENT), slot])

        result = engine.activate("C:/videos/next.mp4", start_pos=0, generation=7, autoplay=True)

        self.assertEqual(result.slot_id, 1)
        self.assertTrue(result.reused_source)
        self.assertTrue(result.waiting_for_media)
        self.assertTrue(result.fallback_required)
        self.assertTrue(engine.fallback_timer.started)

    def test_new_activation_sets_source_and_arms_fallback(self):
        slot = make_slot(0)
        engine = make_engine([slot])

        result = engine.activate("C:/videos/a.mp4", start_pos=0, generation=2, autoplay=True)

        self.assertEqual(result.slot_id, 0)
        self.assertFalse(result.reused_source)
        self.assertTrue(result.waiting_for_media)
        self.assertEqual(slot.expected_path, os.path.normpath("C:/videos/a.mp4"))
        self.assertEqual(slot.expected_generation, 2)
        self.assertEqual(slot.state, SlotState.ACTIVE)
        self.assertTrue(engine.fallback_timer.started)
```

- [ ] **Step 2: Run the activation tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerEngineActivationTest -v
```

Expected result:

```text
ImportError: cannot import name 'PlayerEngine'
```

- [ ] **Step 3: Implement minimal `PlayerEngine.activate()`**

Add to `src/managers/player_engine.py`:

```python
def _qurl_from_path(path: str):
    try:
        from PyQt6.QtCore import QUrl
        return QUrl.fromLocalFile(path)
    except Exception:
        class FakeUrl:
            def __init__(self, value):
                self.value = value

            def toLocalFile(self):
                return self.value

        return FakeUrl(path)


class PlayerEngine:
    def __init__(self, slots, fallback_timer, privacy_guard, autoplay_getter, audio_enabled_getter):
        self.slots = slots
        self.fallback_timer = fallback_timer
        self.privacy_guard = privacy_guard
        self.autoplay_getter = autoplay_getter
        self.audio_enabled_getter = audio_enabled_getter
        self.active_slot_id = None
        self.current_generation = 0

    def _normalize_path(self, path: str) -> str:
        return os.path.normpath(path)

    def _find_valid_slot(self, path: str, generation: int):
        norm_path = self._normalize_path(path)
        for slot in self.slots:
            if slot.state in {SlotState.READY, SlotState.PRELOADING, SlotState.ACTIVE}:
                if slot.expected_generation == generation and source_matches_path(slot, norm_path):
                    return slot
        return None

    def _choose_slot(self):
        for slot in self.slots:
            if slot.state in {SlotState.EMPTY, SlotState.STALE, SlotState.FAILED}:
                return slot
        for slot in self.slots:
            if slot.state != SlotState.ACTIVE:
                return slot
        return self.slots[0]

    def _demote_other_active_slots(self, active_slot):
        for slot in self.slots:
            if slot is active_slot:
                continue
            if slot.state == SlotState.ACTIVE:
                slot.video_item.setOpacity(0.0)
                slot.video_item.setZValue(0.0)
                slot.audio.setMuted(True)
                slot.state = SlotState.STALE
                slot.role = SlotRole.SPARE

    def _arm_fallback(self):
        self.fallback_timer.stop()
        self.fallback_timer.start()

    def activate(self, path: str, start_pos: int, generation: int, autoplay: bool) -> ActivationResult:
        norm_path = self._normalize_path(path)
        self.current_generation = generation
        slot = self._find_valid_slot(norm_path, generation)
        reused = slot is not None

        if slot is None:
            slot = self._choose_slot()
            if slot.state != SlotState.EMPTY:
                slot.clear()
            slot.player.setSource(_qurl_from_path(norm_path))
            slot.expected_path = norm_path
            slot.expected_generation = generation
            slot.requested_start_pos = start_pos
            waiting = True
        else:
            waiting = slot.state == SlotState.PRELOADING

        self._demote_other_active_slots(slot)
        slot.state = SlotState.ACTIVE
        slot.role = SlotRole.CURRENT
        slot.requested_start_pos = start_pos
        slot.audio.setMuted(not self.audio_enabled_getter())
        slot.video_item.setZValue(20.0)
        self.active_slot_id = slot.slot_id

        if waiting:
            self._arm_fallback()

        if autoplay:
            slot.player.play()
        else:
            slot.player.setPosition(start_pos)

        return ActivationResult(
            slot_id=slot.slot_id,
            path=norm_path,
            reused_source=reused,
            waiting_for_media=waiting,
            fallback_required=waiting,
        )
```

- [ ] **Step 4: Run the activation tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerEngineActivationTest -v
```

Expected result:

```text
OK
```

- [ ] **Step 5: Commit**

```powershell
git add src/managers/player_engine.py tests/test_player_engine.py
git commit -m "add player engine activation"
```

---

## Task 4: Neighbor Preload Planning And Eviction

**Files:**
- Modify: `src/managers/player_engine.py`
- Modify: `tests/test_player_engine.py`

- [ ] **Step 1: Write failing preload planning tests**

Append to `tests/test_player_engine.py`:

```python
from src.managers.player_engine import PlaybackItem


class PlayerEnginePreloadPlanTest(unittest.TestCase):
    def test_plan_neighbors_keeps_next_and_previous_slots(self):
        active = make_slot(0, "C:/videos/b.mp4", SlotState.ACTIVE, 4, SlotRole.CURRENT)
        next_slot = make_slot(1)
        prev_slot = make_slot(2)
        engine = make_engine([active, next_slot, prev_slot])
        playlist = [
            PlaybackItem("C:/videos/a.mp4"),
            PlaybackItem("C:/videos/b.mp4"),
            PlaybackItem("C:/videos/c.mp4"),
        ]

        engine.plan_neighbors(current_index=1, playlist=playlist, generation=4)

        self.assertEqual(next_slot.state, SlotState.PRELOADING)
        self.assertEqual(next_slot.role, SlotRole.NEXT)
        self.assertEqual(next_slot.expected_path, os.path.normpath("C:/videos/c.mp4"))
        self.assertEqual(prev_slot.state, SlotState.PRELOADING)
        self.assertEqual(prev_slot.role, SlotRole.PREVIOUS)
        self.assertEqual(prev_slot.expected_path, os.path.normpath("C:/videos/a.mp4"))

    def test_plan_neighbors_does_not_clear_ready_neighbor(self):
        active = make_slot(0, "C:/videos/b.mp4", SlotState.ACTIVE, 4, SlotRole.CURRENT)
        ready_next = make_slot(1, "C:/videos/c.mp4", SlotState.READY, 4, SlotRole.NEXT)
        spare = make_slot(2)
        engine = make_engine([active, ready_next, spare])
        playlist = [
            PlaybackItem("C:/videos/a.mp4"),
            PlaybackItem("C:/videos/b.mp4"),
            PlaybackItem("C:/videos/c.mp4"),
        ]

        engine.plan_neighbors(current_index=1, playlist=playlist, generation=4)

        self.assertEqual(ready_next.state, SlotState.READY)
        self.assertEqual(ready_next.role, SlotRole.NEXT)
        self.assertEqual(ready_next.player.stop_count, 0)
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerEnginePreloadPlanTest -v
```

Expected result:

```text
AttributeError: 'PlayerEngine' object has no attribute 'plan_neighbors'
```

- [ ] **Step 3: Implement neighbor planning**

Add to `PlayerEngine`:

```python
    def _slot_matches(self, slot, path: str, generation: int) -> bool:
        return (
            slot.expected_generation == generation
            and slot.expected_path is not None
            and os.path.normcase(os.path.normpath(slot.expected_path)) == os.path.normcase(os.path.normpath(path))
            and slot.state in {SlotState.PRELOADING, SlotState.READY, SlotState.ACTIVE}
        )

    def _find_or_assign_neighbor_slot(self, path: str, generation: int):
        for slot in self.slots:
            if self._slot_matches(slot, path, generation):
                return slot
        for slot in self.slots:
            if slot.state == SlotState.EMPTY:
                return slot
        for slot in self.slots:
            if slot.state not in {SlotState.ACTIVE, SlotState.READY}:
                slot.clear()
                return slot
        return None

    def _start_preload(self, slot, item: PlaybackItem, generation: int, role: SlotRole) -> None:
        norm_path = self._normalize_path(item.path)
        if self._slot_matches(slot, norm_path, generation):
            slot.role = role
            return
        slot.clear()
        slot.expected_path = norm_path
        slot.expected_generation = generation
        slot.requested_start_pos = item.start_pos
        slot.role = role
        slot.state = SlotState.PRELOADING
        slot.audio.setMuted(True)
        slot.video_item.setOpacity(0.0)
        slot.video_item.setZValue(0.0)
        slot.player.setSource(_qurl_from_path(norm_path))
        slot.player.pause()
        if item.start_pos > 0:
            slot.player.setPosition(item.start_pos)

    def plan_neighbors(self, current_index: int, playlist: list[PlaybackItem], generation: int) -> None:
        targets = []
        if current_index + 1 < len(playlist):
            targets.append((playlist[current_index + 1], SlotRole.NEXT))
        if current_index - 1 >= 0:
            targets.append((playlist[current_index - 1], SlotRole.PREVIOUS))

        protected_paths = {self._normalize_path(item.path) for item, _role in targets}
        for item, role in targets:
            slot = self._find_or_assign_neighbor_slot(item.path, generation)
            if slot and slot.state != SlotState.READY:
                self._start_preload(slot, item, generation, role)
            elif slot:
                slot.role = role

        for slot in self.slots:
            if slot.state == SlotState.ACTIVE:
                continue
            if slot.expected_path and self._normalize_path(slot.expected_path) in protected_paths:
                continue
            if slot.state in {SlotState.PRELOADING, SlotState.READY, SlotState.STALE, SlotState.FAILED}:
                slot.clear()
```

- [ ] **Step 4: Run the tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerEnginePreloadPlanTest -v
```

Expected result:

```text
OK
```

- [ ] **Step 5: Commit**

```powershell
git add src/managers/player_engine.py tests/test_player_engine.py
git commit -m "add deterministic preload planning"
```

---

## Task 5: Media Status Handling And Reveal Guards

**Files:**
- Modify: `src/managers/player_engine.py`
- Modify: `tests/test_player_engine.py`

- [ ] **Step 1: Write failing reveal/status tests**

Append to `tests/test_player_engine.py`:

```python
class MediaStatus:
    LoadedMedia = "loaded"
    BufferedMedia = "buffered"
    LoadingMedia = "loading"
    InvalidMedia = "invalid"
    NoMedia = "none"
    EndOfMedia = "end"


class PlayerEngineStatusTest(unittest.TestCase):
    def test_ready_preload_survives_active_loaded_status(self):
        active = make_slot(0, "C:/videos/a.mp4", SlotState.ACTIVE, 3, SlotRole.CURRENT)
        ready_next = make_slot(1, "C:/videos/b.mp4", SlotState.READY, 3, SlotRole.NEXT)
        engine = make_engine([active, ready_next])

        engine.handle_media_status(active.player, MediaStatus.LoadedMedia)

        self.assertEqual(ready_next.state, SlotState.READY)
        self.assertEqual(ready_next.player.stop_count, 0)

    def test_reveal_requires_active_generation_source_and_privacy_clear(self):
        active = make_slot(0, "C:/videos/a.mp4", SlotState.ACTIVE, 3, SlotRole.CURRENT)
        engine = make_engine([active], privacy_blocked=True)
        engine.current_generation = 3

        revealed = engine.reveal_if_allowed(active, MediaStatus.LoadedMedia)

        self.assertFalse(revealed)
        self.assertEqual(active.video_item.opacity, 0.0)

    def test_invalid_media_marks_slot_failed_and_clears_reuse_metadata(self):
        active = make_slot(0, "C:/videos/broken.mp4", SlotState.ACTIVE, 3, SlotRole.CURRENT)
        engine = make_engine([active])
        engine.current_generation = 3

        engine.handle_media_status(active.player, MediaStatus.InvalidMedia)

        self.assertEqual(active.state, SlotState.FAILED)
        self.assertIsNone(active.expected_path)
        self.assertEqual(active.video_item.opacity, 0.0)
        self.assertTrue(active.audio.muted)
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerEngineStatusTest -v
```

Expected result:

```text
AttributeError: 'PlayerEngine' object has no attribute 'handle_media_status'
```

- [ ] **Step 3: Implement status handling and reveal guard**

Add to `PlayerEngine`:

```python
    def _slot_for_player(self, player):
        for slot in self.slots:
            if slot.player is player:
                return slot
        return None

    def _status_name(self, status) -> str:
        return getattr(status, "name", str(status)).lower()

    def _is_loaded_status(self, status) -> bool:
        name = self._status_name(status)
        return "loaded" in name or "buffered" in name

    def _is_failed_status(self, status) -> bool:
        name = self._status_name(status)
        return "invalid" in name or "nomedia" in name or name == "none"

    def reveal_if_allowed(self, slot, status, fallback_expired: bool = False) -> bool:
        if slot.state != SlotState.ACTIVE:
            return False
        if slot.expected_generation != self.current_generation:
            return False
        if not slot.expected_path or not source_matches_path(slot, slot.expected_path):
            return False
        if self.privacy_guard():
            return False
        if not fallback_expired and not self._is_loaded_status(status):
            return False
        slot.video_item.setOpacity(1.0)
        slot.video_item.setZValue(20.0)
        return True

    def _mark_failed(self, slot, status) -> None:
        slot.last_status = status
        slot.last_error = self._status_name(status)
        slot.player.stop()
        slot.player.setSource(_empty_qurl())
        slot.audio.setMuted(True)
        slot.video_item.setOpacity(0.0)
        slot.video_item.setZValue(0.0)
        slot.expected_path = None
        slot.state = SlotState.FAILED
        slot.role = SlotRole.SPARE

    def handle_media_status(self, player, status) -> bool:
        slot = self._slot_for_player(player)
        if slot is None:
            return False
        slot.last_status = status
        if self._is_failed_status(status):
            self._mark_failed(slot, status)
            return False
        if slot.state == SlotState.PRELOADING and self._is_loaded_status(status):
            slot.state = SlotState.READY
            return False
        if slot.state == SlotState.ACTIVE:
            return self.reveal_if_allowed(slot, status)
        return False
```

- [ ] **Step 4: Run the tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine.PlayerEngineStatusTest -v
```

Expected result:

```text
OK
```

- [ ] **Step 5: Commit**

```powershell
git add src/managers/player_engine.py tests/test_player_engine.py
git commit -m "add player engine reveal guards"
```

---

## Task 6: Integrate Engine With `VideoSorter`

**Files:**
- Modify: `main.py`
- Modify: `tests/test_video_sorter.py`
- Modify: `src/managers/player_manager.py`

- [ ] **Step 1: Write failing integration tests for generation and double entry**

Append to `tests/test_video_sorter.py`:

```python
class FakePlaybackEngine:
    def __init__(self):
        self.activate_calls = []
        self.plan_calls = []
        self.clear_all_count = 0

    def activate(self, path, start_pos, generation, autoplay):
        self.activate_calls.append((path, start_pos, generation, autoplay))
        return type("ActivationResult", (), {"slot_id": 0, "waiting_for_media": False})()

    def plan_neighbors(self, current_index, playlist, generation):
        self.plan_calls.append((current_index, [(item.path, item.start_pos) for item in playlist], generation))

    def clear_all(self):
        self.clear_all_count += 1


class FakeListItem:
    def __init__(self, path, start_pos=None):
        self.path = path
        self.start_pos = start_pos

    def data(self, role):
        if role == Qt.ItemDataRole.UserRole:
            return self.path
        if role == Qt.ItemDataRole.UserRole + 1:
            return self.start_pos
        return None


class FakePlayableList:
    def __init__(self):
        self.items = [
            FakeListItem("C:/videos/a.mp4"),
            FakeListItem("C:/videos/b.mp4", 2000),
            FakeListItem("C:/videos/c.mp4"),
        ]
        self.current_row = 0
        self.signals_blocked = False

    def count(self):
        return len(self.items)

    def item(self, index):
        return self.items[index]

    def currentRow(self):
        return self.current_row

    def setCurrentRow(self, row):
        self.current_row = row

    def blockSignals(self, blocked):
        self.signals_blocked = blocked


class PlayerEngineIntegrationTest(unittest.TestCase):
    def test_play_video_delegates_activation_and_neighbor_planning(self):
        window = type("FakeWindow", (), {})()
        window.file_list = FakePlayableList()
        window.scan_timer = FakeTimer()
        window.preload_timer = FakeTimer()
        window.seek_safety_timer = FakeTimer()
        window.is_waiting_for_seek = False
        window.chk_random = FakeCheck(False)
        window.conf_auto_play = True
        window.playback_generation = 5
        window.player_engine = FakePlaybackEngine()

        VideoSorter.play_video(window, 1)

        self.assertEqual(window.player_engine.activate_calls, [("C:/videos/b.mp4", 2000, 5, True)])
        self.assertEqual(window.player_engine.plan_calls[0][0], 1)

    def test_auto_play_next_blocks_selection_signal_before_explicit_play(self):
        window = type("FakeWindow", (), {})()
        window.file_list = FakePlayableList()
        window.play_calls = []
        window.reset_viewer_state = lambda: None
        window.setWindowTitle = lambda title: None

        def record_play(row):
            window.play_calls.append(row)

        window.play_video = record_play

        VideoSorter.auto_play_next(window, 1)

        self.assertEqual(window.play_calls, [1])
        self.assertFalse(window.file_list.signals_blocked)
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_video_sorter.PlayerEngineIntegrationTest -v
```

Expected result:

```text
AttributeError: 'FakeWindow' object has no attribute 'player'
```

- [ ] **Step 3: Add engine construction and playlist helpers**

Modify `main.py` imports:

```python
from src.managers.player_engine import PlaybackItem, PlayerEngine
```

In `VideoSorter.__init__`, after `self.player_manager = PlayerManager(...)`, add:

```python
        self.playback_generation = 0
        self.player_engine = PlayerEngine(
            slots=self.player_manager.engine_slots(),
            fallback_timer=self.seek_safety_timer,
            privacy_guard=self.is_privacy_blocking_video,
            autoplay_getter=lambda: self.conf_auto_play,
            audio_enabled_getter=lambda: self.chk_audio.isChecked(),
        )
```

Add to `PlayerManager`:

```python
    def engine_slots(self):
        from src.managers.player_engine import PlayerSlot

        slots = []
        slot_id = 0
        for mode, pool in self.pools.items():
            for entry in pool:
                slots.append(PlayerSlot(
                    slot_id=slot_id,
                    mode=mode,
                    player=entry["player"],
                    audio=entry["audio"],
                    video_item=entry["item"],
                    expected_path=entry.get("path"),
                ))
                slot_id += 1
        return slots
```

Add to `main.py`:

```python
    def is_privacy_blocking_video(self) -> bool:
        return bool(getattr(self, "conf_privacy_mode", False) and not getattr(self, "_user_has_requested_visible_playback", False))

    def _increment_playback_generation(self) -> None:
        self.playback_generation = getattr(self, "playback_generation", 0) + 1

    def _current_playlist_items(self):
        items = []
        for row in range(self.file_list.count()):
            item = self.file_list.item(row)
            path = item.data(Qt.ItemDataRole.UserRole)
            start_pos = item.data(Qt.ItemDataRole.UserRole + 1)
            items.append(PlaybackItem(path=path, start_pos=int(start_pos) if start_pos is not None else 0))
        return items
```

- [ ] **Step 4: Replace `play_video()` body with engine delegation**

Use this body:

```python
    def play_video(self, index: int, specific_start_pos: Optional[int] = None) -> None:
        target_path, item_widget = self._prepare_playback(index)
        if not target_path:
            return

        start_pos = self._resolve_start_pos(item_widget, specific_start_pos)
        self.target_start_pos = start_pos
        generation = getattr(self, "playback_generation", 0)
        autoplay = bool(self.conf_auto_play)

        self.video_view.set_info_visible(False)
        if getattr(self, "conf_privacy_mode", False) and not autoplay:
            self.setWindowTitle("YDManager")
        else:
            self.setWindowTitle(f"재생: {os.path.basename(target_path)}")

        self.player_engine.activate(target_path, start_pos, generation, autoplay)
        self.player_engine.plan_neighbors(index, self._current_playlist_items(), generation)

        if autoplay and self.chk_autoscan.isChecked():
            self.scan_timer.start()
        else:
            self.scan_timer.stop()
```

- [ ] **Step 5: Update `auto_play_next()` to prevent double-entry**

Replace the first branch with:

```python
        if row < current_len:
            self.file_list.blockSignals(True)
            self.file_list.setCurrentRow(row)
            self.file_list.blockSignals(False)
            self.play_video(row)
```

Replace the second branch with:

```python
        elif current_len > 0:
            target_row = current_len - 1
            self.file_list.blockSignals(True)
            self.file_list.setCurrentRow(target_row)
            self.file_list.blockSignals(False)
            self.play_video(target_row)
```

- [ ] **Step 6: Run the integration tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_video_sorter.PlayerEngineIntegrationTest -v
```

Expected result:

```text
OK
```

- [ ] **Step 7: Commit**

```powershell
git add main.py src/managers/player_manager.py tests/test_video_sorter.py
git commit -m "wire player engine into playback"
```

---

## Task 7: Replace Legacy Media Status, Position, Reset, And Path Release

**Files:**
- Modify: `main.py`
- Modify: `src/controllers/file_action_controller.py`
- Modify: `tests/test_video_sorter.py`
- Modify: `tests/test_file_action_controller.py`

- [ ] **Step 1: Write failing tests for privacy reveal and reset clearing**

Append to `tests/test_video_sorter.py`:

```python
class PlayerEngineResetAndPrivacyTest(unittest.TestCase):
    def test_reset_viewer_state_clears_engine_slots(self):
        window = type("FakeWindow", (), {})()
        window.player_engine = FakePlaybackEngine()
        window.lbl_info = FakeLabel()
        window.video_view = FakeVideoView()

        VideoSorter.reset_viewer_state(window)

        self.assertEqual(window.player_engine.clear_all_count, 1)

    def test_privacy_blocking_uses_shared_predicate(self):
        window = type("FakeWindow", (), {})()
        window.conf_privacy_mode = True
        window._user_has_requested_visible_playback = False

        self.assertTrue(VideoSorter.is_privacy_blocking_video(window))

        window._user_has_requested_visible_playback = True

        self.assertFalse(VideoSorter.is_privacy_blocking_video(window))
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_video_sorter.PlayerEngineResetAndPrivacyTest -v
```

Expected result:

```text
AssertionError: 0 != 1
```

- [ ] **Step 3: Delegate status and position handlers to engine**

Replace `on_media_status_changed()` in `main.py` with:

```python
    def on_media_status_changed(self, status):
        sender_player = self.sender()
        revealed = self.player_engine.handle_media_status(sender_player, status)
        if revealed:
            self.video_view.set_duration(self.player_engine.active_player().duration())
            self.player_engine.active_player().setPlaybackRate(self.playback_rate)
```

Replace `on_position_changed()` waiting reveal block with:

```python
        if self.is_waiting_for_seek:
            target = getattr(self, "_pending_seek_pos", -1)
            if target != -1 and abs(position - target) < 1000:
                active_slot = self.player_engine.active_slot()
                if active_slot:
                    self.player_engine.reveal_if_allowed(active_slot, active_slot.last_status, fallback_expired=True)
                self.is_waiting_for_seek = False
                self.seek_safety_timer.stop()
                if self.conf_auto_play and self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                    self.player.play()
```

Add these engine methods:

```python
    def active_slot(self):
        for slot in self.slots:
            if slot.slot_id == self.active_slot_id:
                return slot
        return None

    def active_player(self):
        slot = self.active_slot()
        return slot.player if slot else None

    def active_audio(self):
        slot = self.active_slot()
        return slot.audio if slot else None

    def clear_all(self) -> None:
        for slot in self.slots:
            slot.clear()
        self.active_slot_id = None
```

- [ ] **Step 4: Update reset to clear all slots**

In `reset_viewer_state()`, replace active-player direct reset with:

```python
        if hasattr(self, "player_engine"):
            self.player_engine.clear_all()
        elif hasattr(self, "player_manager"):
            active_data = self.player_manager.get_active_player()
            if active_data:
                active_data["player"].stop()
                active_data["player"].setSource(QUrl())
                active_data["path"] = None
                active_data["item"].setOpacity(0.0)
```

- [ ] **Step 5: Run reset/privacy tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_video_sorter.PlayerEngineResetAndPrivacyTest -v
```

Expected result:

```text
OK
```

- [ ] **Step 6: Commit**

```powershell
git add main.py src/managers/player_engine.py tests/test_video_sorter.py
git commit -m "route status and reset through player engine"
```

---

## Task 8: File Actions Use Engine APIs

**Files:**
- Modify: `src/managers/player_engine.py`
- Modify: `src/controllers/file_action_controller.py`
- Modify: `tests/test_file_action_controller.py`

- [ ] **Step 1: Write failing tests for path clearing**

Add a fake engine to `tests/test_file_action_controller.py`:

```python
class FakePlayerEngine:
    def __init__(self):
        self.cleared_paths = []

    def clear_path(self, path):
        self.cleared_paths.append(path)
        return True
```

Add this test:

```python
    def test_hard_delete_uses_player_engine_path_release(self):
        app = FakeApp("C:/videos/delete.mp4")
        app.player_engine = FakePlayerEngine()
        controller = FileActionController(app)

        with patch("src.controllers.file_action_controller.ThemeMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            controller.hard_delete_file()

        self.assertEqual(app.player_engine.cleared_paths, ["C:/videos/delete.mp4"])
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_file_action_controller.FileActionControllerTest.test_hard_delete_uses_player_engine_path_release -v
```

Expected result:

```text
AssertionError: [] != ['C:/videos/delete.mp4']
```

- [ ] **Step 3: Implement `clear_path()`**

Add to `PlayerEngine`:

```python
    def clear_path(self, path: str) -> bool:
        norm_path = self._normalize_path(path)
        cleared = False
        for slot in self.slots:
            if slot.expected_path and os.path.normcase(os.path.normpath(slot.expected_path)) == os.path.normcase(norm_path):
                slot.clear()
                cleared = True
            elif source_matches_path(slot, norm_path):
                slot.clear()
                cleared = True
        return cleared
```

- [ ] **Step 4: Route file actions through engine first**

In `FileActionController.hard_delete_file()` replace the player release block with:

```python
        if hasattr(self.app, "player_engine"):
            self.app.player_engine.clear_path(path)
        elif hasattr(self.app, "player_manager"):
            self.app.player_manager.stop_and_release_path(path)
```

In `delete_all_trash_files()`, use the same branch inside the loop:

```python
            if hasattr(self.app, "player_engine"):
                for path in trash_paths:
                    self.app.player_engine.clear_path(path)
            elif hasattr(self.app, "player_manager"):
                for path in trash_paths:
                    self.app.player_manager.stop_and_release_path(path)
```

- [ ] **Step 5: Run file action tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_file_action_controller -v
```

Expected result:

```text
OK
```

- [ ] **Step 6: Commit**

```powershell
git add src/managers/player_engine.py src/controllers/file_action_controller.py tests/test_file_action_controller.py
git commit -m "use player engine for file action release"
```

---

## Task 9: Smoke Coverage And Documentation

**Files:**
- Modify: `tools/smoke_video_workflow.py`
- Modify: `docs/maintenance/playback-state.md`
- Modify: `docs/maintenance/manual-smoke-test.md`
- Modify: `docs/maintenance/stabilization-report-2026-06-12.md`

- [ ] **Step 1: Extend generated-video smoke with engine state checks**

In `tools/smoke_video_workflow.py`, after the first `window.play_video(0)` check, add:

```python
            window.play_video(1)
            _pump_events(app, 1000)
            second_loaded = Path(window.file_list.item(1).data(Qt.ItemDataRole.UserRole))
            _assert(
                _norm(window.player_engine.active_player().source().toLocalFile()) == _norm(second_loaded),
                "player engine did not promote the second selected source",
            )

            window.play_video(0)
            _pump_events(app, 1000)
            _assert(
                _norm(window.player_engine.active_player().source().toLocalFile()) == _norm(first_loaded),
                "player engine did not return to the first selected source",
            )
```

- [ ] **Step 2: Run smoke and verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe .\tools\smoke_video_workflow.py
```

Expected result:

```text
video workflow smoke ok
```

- [ ] **Step 3: Update playback documentation**

Replace the current `Player Pools` and `Selection Rules` sections in `docs/maintenance/playback-state.md` with:

```markdown
## Player Engine v2

`PlayerEngine` owns explicit slot state for each Qt player:

- `EMPTY`
- `PRELOADING`
- `READY`
- `ACTIVE`
- `FAILED`
- `STALE`

Fast browsing keeps the active video plus next and previous candidates in the current generation. A `READY` neighbor can be promoted without resetting its media source. A `PRELOADING` neighbor can be promoted while the fallback reveal timer remains armed. A slot is never reused solely because a stale metadata path matches; the actual `QMediaPlayer.source()` must match the expected path.
```

- [ ] **Step 4: Update manual smoke checklist**

Add this checklist to `docs/maintenance/manual-smoke-test.md`:

```markdown
## Player Engine v2 Manual Smoke

- [ ] Load two or more H.264/AAC videos outside the repository.
- [ ] Press Down/Up rapidly and confirm the selected video source follows the visible row.
- [ ] Confirm next/previous transitions do not show a persistent black screen.
- [ ] Pause with privacy mode enabled and confirm video/list/title are hidden.
- [ ] Disable auto-play with privacy mode enabled and select another video; confirm no video is revealed until visible playback is requested.
- [ ] Rename the active video with `#` and confirm playback can resume from the renamed path.
- [ ] Soft delete the active video and confirm the next row plays once, not twice.
- [ ] Hard delete the active video and confirm no file-lock error occurs.
- [ ] Enter search, play a result, clear search, and confirm active source remains valid.
```

- [ ] **Step 5: Update stabilization report**

Add to `docs/maintenance/stabilization-report-2026-06-12.md`:

```markdown
- Player Engine v2 introduces explicit slot state, generation guards, preload promotion, path/source reveal validation, and privacy-aware reveal checks.
```

- [ ] **Step 6: Commit**

```powershell
git add tools/smoke_video_workflow.py docs/maintenance/playback-state.md docs/maintenance/manual-smoke-test.md docs/maintenance/stabilization-report-2026-06-12.md
git commit -m "document player engine v2 smoke coverage"
```

---

## Task 10: Full Verification And Push

**Files:**
- Inspect all changed files.

- [ ] **Step 1: Run focused player engine tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_player_engine -v
```

Expected result:

```text
OK
```

- [ ] **Step 2: Run full local checks**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_checks.ps1
```

Expected result:

```text
PYTHON_VERSION_OK 3.10.11
RELEASE_AUDIT_OK
OK
```

- [ ] **Step 3: Run generated-video workflow smoke**

Run:

```powershell
.\.venv\Scripts\python.exe .\tools\smoke_video_workflow.py
```

Expected result:

```text
video workflow smoke ok
```

- [ ] **Step 4: Run package smoke**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\package_smoke.ps1
```

Expected result:

```text
PACKAGE_SMOKE_OK
```

- [ ] **Step 5: Run whitespace and stale-string checks**

Run:

```powershell
git diff --check
rg -n '124 unittest|131 unittest|Ran 124|Ran 131|ydm-debug-smoke|F:\\YDM|F:/YDM' docs README.md BUILD.md tests tools .github src main.py setup.iss YDManager.spec requirements.txt requirements-build.txt requirements-lock.txt
```

Expected result:

```text
git diff --check exits 0
rg exits 1 with no matches
```

- [ ] **Step 6: Commit verification docs if counts changed**

If `run_checks.ps1` reports a new test count, update:

- `docs/maintenance/stabilization-report-2026-06-12.md`
- `docs/superpowers/plans/2026-06-12-project-stabilization-master-plan.md`

Then run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_packaging_static.PackagingStaticTest.test_stabilization_docs_record_current_automated_count -v
git add docs/maintenance/stabilization-report-2026-06-12.md docs/superpowers/plans/2026-06-12-project-stabilization-master-plan.md
git commit -m "update player engine verification evidence"
```

Expected result:

```text
OK
```

- [ ] **Step 7: Push branch**

Run:

```powershell
git push
```

Expected result:

```text
codex/player-engine-stabilization is up to date on origin after push
```
