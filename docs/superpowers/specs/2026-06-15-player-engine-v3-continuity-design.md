# Player Engine v3 Continuity Design

Date: 2026-06-15

## Objective

Build a stable and fast video exploration player engine where the currently watched video continues smoothly while the user visits other app menus.

The strict user requirement is:

- While a video is playing, switching to highlight, A tag, B tag, trash, or another non-main menu must not reset the watched video.
- Returning to the previous menu must continue the same video at the correct position.
- The transition must avoid avoidable black frames, frame jumps, unnecessary source reloads, and control routing mistakes.
- Fast exploration is more important than minimizing resource usage.

## Current Finding

Static code inspection shows the current architecture does not fully satisfy that requirement.

Relevant code paths:

- `VideoSorter._change_view_mode(...)` saves main state, clears search state, updates `FileManager` view state, then calls `update_ui_mode()`.
- `VideoSorter.update_ui_mode()` computes `target_mode` and immediately calls `self.player_manager.switch_mode(target_mode)`.
- `PlayerManager.switch_mode(target_mode)` releases every player in the previous pool by calling `stop()`, `setSource(QUrl())`, hiding the video item, muting audio, and clearing `path`.
- `VideoSorter.update_ui_mode()` then auto-selects a row and calls `play_video(...)` for the target list.
- Returning to main uses `last_main_path` and `last_main_pos` to reload and resume the previous main item.

This means main -> A/B/highlight/trash -> main can restore the same logical path and position, but it does it through a stop/release/reload path. That is not a strict continuous watch session. It can produce black frames, seek drift, frame jumps, or a short stall depending on media status, codec, disk speed, and Qt Multimedia timing.

The current `docs/maintenance/playback-state.md` correctly documents this behavior: mode switching releases the old player pool. Player Engine v2 improved per-list fast browsing, but menu navigation and playback lifetime are still coupled.

Manual UI automation was attempted for menu round trips, but the desktop-control approval timed out. Therefore the current evidence is code-path evidence, not a completed GUI smoke recording.

## Non-Goals

- Do not replace Qt Multimedia in this phase.
- Do not rebuild the full UI.
- Do not introduce a database-backed media library in this phase.
- Do not remove existing tag, highlight, trash, delete, restore, privacy, or search behavior.
- Do not optimize for minimum RAM while it conflicts with smooth playback continuity.

## Approaches Considered

### Approach A: Minimal Passive Mode Patch

Add flags to `switch_mode(...)` and `update_ui_mode()` so passive menu switches avoid stopping the old player pool and avoid auto-playing the first item in the new list.

Benefits:

- Smallest code change.
- Can reduce the most visible reset behavior quickly.
- Lower immediate regression surface.

Costs:

- The active player is still conceptually tied to `current_mode`.
- Shortcut routing, seek controls, progress updates, and status labels can still point at the menu mode instead of the watched video.
- Hidden coupling remains and will likely create future bugs.

### Approach B: Watch Session Split

Introduce a first-class watch session that is independent from the current list/menu mode.

Benefits:

- Directly matches the requirement.
- Menu navigation can be passive, while explicit video selection starts a new playback session.
- Controls, progress, auto-scan, privacy reveal, and status can all target the watched player instead of the visible menu mode.
- Works with the existing Player Engine v2 slot model instead of replacing it.

Costs:

- Requires careful test coverage because many legacy methods currently call `self.player` through `PlayerManager.current_mode`.
- Requires changing mode-switch semantics and list-selection behavior.

Recommendation: use Approach B.

### Approach C: Unified Media Navigation Model

Replace mode-specific pools and lists with one query-driven media model. Main, A, B, highlight, trash, and search become filters over one playlist/session system.

Benefits:

- Cleanest long-term architecture.
- Removes many special cases around mode, filter, and list rebuilds.

Costs:

- Too large for the next stabilization step.
- High migration risk for delete, restore, highlight replay, search, and existing tests.

This can be revisited after the watch session boundary is stable.

## Target Architecture

### Concepts

`view_mode`

The visible list/menu context. Valid values are currently main, A, B, highlight, and trash. Changing `view_mode` updates lists, buttons, counters, search visibility, and menu-specific actions.

`watch_session`

The active playback session. It stores the watched path, slot id, source generation, playback start request, last stable position, autoplay state, and whether the source is expected to stay resident.

`candidate_selection`

The selected row in the currently visible list. It does not replace `watch_session` until the user explicitly requests playback from that row.

### Core Rule

Changing menus must not release, replace, seek, pause, or restart the active watch session.

Only these actions may replace or release the active watch session:

- User explicitly selects a different video for playback.
- Current file is physically deleted, renamed, or moved in a way that invalidates the loaded source.
- User triggers a full reset, folder switch, app shutdown, or media reload action.
- Current media fails and the engine marks its slot failed.

### Proposed Data Object

```python
@dataclass
class WatchSession:
    path: str
    slot_id: int
    generation: int
    view_origin: str
    requested_start_pos: int
    last_known_position: int = 0
    preserve_across_menu: bool = True
```

The exact module can be chosen during implementation. A good first location is `src/managers/player_engine.py` because `PlayerEngine` already owns slot ids and active-slot state.

### PlayerManager Responsibility

`PlayerManager` should continue to own physical Qt players and graphics items.

It should no longer treat every menu switch as a destructive pool switch. The current destructive behavior should become an explicit release operation.

Proposed API direction:

```python
def switch_mode(self, target_mode: str, *, preserve_watch_session: bool = True) -> None:
    ...

def release_mode(self, mode: str, *, except_slot_id: int | None = None) -> None:
    ...
```

When `preserve_watch_session=True`, switching visible mode should update `current_mode` and active indices only where needed for list context. It must not call `stop()` or `setSource(QUrl())` on the active watch slot.

### PlayerEngine Responsibility

`PlayerEngine` should own the active watch session and expose watch-session-safe APIs:

```python
def active_session(self) -> WatchSession | None:
    ...

def activate_watch(self, path: str, start_pos: int, generation: int, autoplay: bool, view_origin: str) -> ActivationResult:
    ...

def preserve_active_watch(self) -> bool:
    ...

def release_watch_path(self, path: str) -> bool:
    ...
```

Existing `activate(...)`, `plan_neighbors(...)`, `clear_path(...)`, and `active_player()` can stay, but callers should distinguish explicit playback activation from passive menu/list refresh.

### VideoSorter Responsibility

`VideoSorter` remains the UI coordinator.

It should split list navigation from playback activation:

- `change_view_mode(...)`: update menu state and rebuild the visible list.
- `refresh_visible_list(...)`: render rows and restore candidate selection.
- `activate_selected_video(...)`: start or replace the watch session only after explicit user playback intent.
- `restore_candidate_selection(...)`: select the row matching `watch_session.path` if present, otherwise restore the last row for that view.

The existing `player` and `audio_output` properties should route to the active watch session, not blindly to `PlayerManager.current_mode`.

## Required Behavior By Menu

### Main -> A Tag -> Main

- Main video keeps playing.
- A list appears without auto-playing row 0.
- If the watched path is also in A, the row can be selected as candidate.
- Returning to main selects the watched path if it still exists.
- No `stop()` or `setSource(QUrl())` is called for the watched slot.

### Main -> B Tag -> Main

Same as A tag.

### Main -> Highlight -> Main

- Entering highlight list does not steal playback.
- Highlight replay starts only when the user explicitly activates a highlight.
- If a highlight replay is activated, it becomes the watch session and should seek within the same source when possible.
- Returning to main preserves the highlight playback if it is still the active watch session, or restores the previous main watch if no highlight was activated.

### Main -> Trash -> Main

- Entering trash does not stop the current watched video.
- Soft-deleting metadata does not release the media source unless the active file is affected by a flow that requires replacement.
- Hard delete of the active file must call a watch-session release path first, then move to the next valid item or show a clear no-media state.
- Returning to main keeps playback if the active file still exists and remains valid.

### Search While Watching

- Typing in search should update the visible list only.
- Search result changes must not replace playback unless the user activates a result.
- If the watched path appears in results, select it as candidate; otherwise leave playback status separate from visible selection.

## Error Handling

The engine must handle invalid state without killing unrelated playback:

- If a passive menu switch produces an empty list, keep the watch session active and show empty-list UI only in the list area.
- If the watched file no longer exists, release that watch session and show a non-blocking status.
- If the target menu has no loaded players, do not reuse the active watch slot unless the user activates a video from that menu.
- If a stale media-status signal arrives from a non-watch slot, ignore it for watch-session state.
- If privacy mode hides video output, preserve the session and continue routing controls to it.

## Test Strategy

### Unit Tests

Add tests before implementation.

Player manager tests:

- `switch_mode(..., preserve_watch_session=True)` does not call `stop()` or `setSource(QUrl())` on the preserved active slot.
- Destructive release still calls `stop()` and `setSource(QUrl())` for explicit delete/reset cleanup.

Player engine tests:

- Active watch session survives passive mode changes.
- Active player lookup returns the watch-session player even when `PlayerManager.current_mode` changes.
- `clear_path(active_path)` releases the active watch session and clears session metadata.
- Stale non-active media status does not reveal or mutate the active session.

VideoSorter tests:

- Main -> A -> Main does not call `play_video(0)` during passive list switch.
- Main -> B -> Main does not reset `last_main_pos` to zero.
- Main -> Highlight -> Main does not auto-play the first highlight.
- Main -> Trash -> Main does not call `reset_viewer_state()` when the watch session is valid.
- Search result refresh does not replace the watch session.

### GUI Smoke Tests

Use the desktop app with a small local media fixture:

1. Load a folder.
2. Start playing a known video.
3. Wait until position is greater than zero and video frame is visible.
4. Switch to A, B, highlight, trash, and main.
5. Assert the watched path remains the same unless the user explicitly activates another video.
6. Assert playback position advances or stays within a small tolerance; it must not reset to zero.
7. Assert no black empty frame persists after returning.
8. Assert keyboard seek, play/pause, audio toggle, and auto-scan still control the watched video.

### Performance Measurements

Add lightweight debug counters or logs during development:

- menu switch duration in milliseconds
- watch-session source changes per menu switch
- number of `stop()` calls during passive menu switches
- number of `setSource(QUrl())` calls during passive menu switches
- time from explicit activation to visible frame

Acceptance for passive menu switches:

- watched path unchanged
- source unchanged
- no active-slot release
- no forced seek to zero
- no auto-play of unrelated row 0

## Implementation Phases

### Phase 1: Reproduce And Lock Regression Tests

Write failing tests that encode the current incorrect behavior around menu round trips. Do not change production code until these tests fail for the expected reason.

### Phase 2: Add WatchSession Boundary

Introduce watch-session metadata in the engine. Route active player and active audio access through this boundary.

### Phase 3: Make Menu Switches Passive

Change passive view switches so they rebuild visible lists without releasing or replacing the watch session.

### Phase 4: Separate Candidate Selection From Playback

Update `update_ui_mode()` so selecting a row for visual context does not automatically call `play_video(...)`. Playback activation should happen only through explicit user intent or existing flows that intentionally auto-advance.

### Phase 5: Preserve Destructive Cleanup

Keep reliable file-handle release for hard delete, rename, full reset, folder close, and app shutdown. This phase prevents the continuity change from breaking file operations.

### Phase 6: GUI Smoke And Timing Pass

Run direct app interaction against highlight, A, B, trash, search, delete, restore, and return-to-main flows. Record any remaining stutter sources and fix only after the failing path is identified.

## Acceptance Criteria

The implementation is acceptable only when all criteria are met:

- Passive menu changes do not call `stop()` or `setSource(QUrl())` on the active watch slot.
- Main, A, B, highlight, trash, and search can be visited while the watched video remains valid.
- Returning to main preserves the watched path and position.
- Explicit selection in another menu starts a new watch session intentionally.
- Hard delete and rename still release file handles before physical operations.
- Playback controls always target the watched video, not merely the visible menu mode.
- Existing playback engine tests pass.
- New menu-continuity tests pass.
- Manual GUI smoke confirms no persistent black frame and no reset-to-zero on menu round trips.

## Future Implementation Prompt

Use this prompt when starting the implementation pass:

```text
Implement the Player Engine v3 continuity design in docs/superpowers/specs/2026-06-15-player-engine-v3-continuity-design.md.

Goal: while a video is playing, switching to A tag, B tag, highlight, trash, search, and back to main must not reset, release, or replace the current watch session unless the user explicitly activates another video or the active file is physically invalidated.

Required process:
1. Use TDD.
2. Start with failing tests for passive menu round trips.
3. Add a WatchSession boundary independent from view_mode.
4. Make passive menu switches rebuild lists without calling play_video(0), stop(), setSource(QUrl()), or reset_viewer_state() for a valid active watch session.
5. Keep destructive cleanup correct for hard delete, rename, full reset, folder close, and app shutdown.
6. Run unit tests and a direct GUI smoke test against A, B, highlight, trash, search, delete, restore, and return-to-main flows.
```

## Spec Self-Review

- No incomplete sections remain.
- The recommended approach is Approach B: Watch Session Split.
- The spec is intentionally scoped to playback continuity across menu navigation.
- Larger library/index/database redesign is excluded from this phase.
- The current bug risk is based on code-path evidence; a fresh GUI smoke run is still required during implementation.
