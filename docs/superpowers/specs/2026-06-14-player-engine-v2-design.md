# Player Engine v2 Design

Date: 2026-06-14

## Objective

Build a stable, fast video exploration engine for YDManager.

The engine must prioritize immediate keyboard-first video browsing over minimal resource use. It should keep the current, next, and previous videos in a deterministic player pool so rapid navigation can switch videos without avoidable black frames, stale sources, or confused player state.

## Current Problems

The current implementation has useful pieces, but they are not a reliable engine:

- Preload is opportunistic. `play_video()` schedules preload, but active-player status handling can stop and clear idle players that already finished preloading.
- Preload hits are only instant if the target slot is still resident and already `LoadedMedia` or `BufferedMedia`.
- A reused preload slot that is still loading does not consistently arm the black-screen fallback timer.
- Slot metadata uses `path` as if it proved the QMediaPlayer source is valid. Failed or invalid loads can leave stale path state.
- `reset_viewer_state()` clears only the active player, so idle preload slots can survive resets.
- Privacy reveal guards are inconsistent when auto-play is off or playback is stopped.
- Folder selection, forced refresh, search, and some cache paths still run synchronous work on the UI thread.

## Recommended Approach

Implement a state-machine based player engine while preserving the existing PyQt UI and most file-management behavior.

This is intentionally not a full app rewrite. The goal is to isolate and harden the playback engine first, then reduce UI-thread stalls around loading/search as follow-up work.

## Non-Goals

- Do not replace Qt Multimedia.
- Do not build a new UI.
- Do not implement a database-backed media library in this phase.
- Do not optimize for minimum RAM or minimum player count. Fast browsing is the priority.
- Do not remove existing delete, restore, tag, highlight, privacy, or packaging behavior except where required to make player state correct.

## Engine Model

### Slot States

Each player slot has an explicit state:

- `EMPTY`: no source, safe for assignment.
- `PRELOADING`: source requested for a neighbor video, not yet proven ready.
- `READY`: source is loaded/buffered and safe to promote without calling `setSource()` again.
- `ACTIVE`: visible or current logical playback target.
- `FAILED`: load failed or media became invalid. Must not be reused as a hit.
- `STALE`: slot source no longer matches the playlist generation, mode, or expected path.

Each slot stores:

- `slot_id`
- `mode`
- `role`: `current`, `next`, `previous`, or `spare`
- `expected_path`
- `expected_generation`
- `state`
- `player`
- `audio`
- `video_item`
- `last_error`
- `last_status`
- `requested_start_pos`

### Generations

The engine increments a generation whenever the list context changes:

- mode switch
- folder switch
- search result replacement
- tag filter switch
- trash/highlight view switch
- full reset
- delete/restore that removes or changes the current list

Signals from old generations must not reveal video, start playback, or update active state.

## Target Architecture

### `PlayerEngine`

Create a focused playback service around the existing `QMediaPlayer` pool.

Responsibilities:

- Own player slots and slot state transitions.
- Promote a `READY` or `PRELOADING` slot to `ACTIVE`.
- Start preload for next/previous paths.
- Evict only slots that are not current, next, or previous for the active generation.
- Validate source/path/generation before reveal.
- Clear all slots for reset and mode switch.
- Expose a narrow API to `VideoSorter`.

Proposed API:

```python
class PlayerEngine:
    def activate(path: str, start_pos: int, generation: int, autoplay: bool) -> ActivationResult: ...
    def plan_neighbors(current_index: int, playlist: list[PlaybackItem], generation: int) -> None: ...
    def handle_media_status(player, status) -> None: ...
    def handle_position(player, position) -> None: ...
    def clear_generation(generation: int) -> None: ...
    def clear_path(path: str) -> bool: ...
    def clear_all() -> None: ...
    def active_player() -> QMediaPlayer: ...
    def active_audio() -> QAudioOutput: ...
```

### `VideoSorter`

`VideoSorter` remains the UI coordinator.

It should:

- Convert list rows into playback requests.
- Maintain current list generation.
- Delegate activation and preload planning to `PlayerEngine`.
- Update labels, title, progress bar, and privacy UI.
- Stop directly mutating player pool internals.

### `FileActionController`

File actions should notify the engine before and after operations that affect paths:

- hard delete
- hash rename
- bulk trash delete
- restore
- mode switch after delete/restore

The controller should not manually reset QMediaPlayer state except through the engine API.

## Playback Flow

### Normal Activation

1. User chooses row N.
2. `VideoSorter` resolves `PlaybackItem(path, start_pos)`.
3. `PlayerEngine.activate()` checks for a matching slot in the current generation.
4. If a `READY` slot exists, promote it to `ACTIVE` without `setSource()`.
5. If a `PRELOADING` slot exists, promote it to `ACTIVE`, arm fallback reveal, and wait for status.
6. If no valid slot exists, assign an `EMPTY` or evictable slot, call `setSource()`, mark it `ACTIVE`, and arm fallback reveal.
7. After activation, plan next/previous preloads for the current generation.

### Preload Planning

For non-highlight pools:

- Keep current active slot.
- Keep next item as `PRELOADING` or `READY`.
- Keep previous item as `PRELOADING` or `READY`.
- Mark other slots `STALE` and clear them only after they are not active.

For highlight mode:

- Keep single-slot behavior unless a later measurement proves preload is needed.

### Reveal Guard

Before any code sets video opacity to `1.0`, it must verify:

- slot is `ACTIVE`
- slot generation matches current generation
- slot expected path equals `player.source().toLocalFile()`
- privacy visibility allows reveal
- media status is loaded/buffered or fallback reveal has expired for the active request

If any check fails, do not reveal.

## Privacy Rules

Privacy state must be represented by one helper, not repeated ad hoc checks.

Proposed helper:

```python
def is_privacy_blocking_video(self) -> bool:
    return self.conf_privacy_mode and not self._user_has_requested_visible_playback
```

The exact implementation can use playback state, auto-play setting, and current privacy mode, but callers must use one shared predicate.

Video reveal, shortcut routing, fallback timers, and title updates must all use the same privacy decision.

## Error Handling

The engine must handle these media statuses explicitly:

- `LoadedMedia`
- `BufferedMedia`
- `LoadingMedia`
- `InvalidMedia`
- `NoMedia`
- `EndOfMedia`

On invalid or failed media:

- mark slot `FAILED`
- clear source if safe
- hide item
- mute audio
- avoid treating `expected_path` as reusable
- show a non-blocking status message through `VideoSorter`

## UI Thread Performance

Playback Engine v2 should not solve every library performance problem, but the implementation plan must include follow-up gates for the highest-risk UI stalls:

- folder selection should prefer cache and avoid forced recursive scan on the UI thread
- manual refresh may request a background rescan instead of blocking immediately
- global search should avoid per-keystroke full-cache `os.path.exists()` on the UI thread
- large result list rendering should be measured and, if needed, chunked or virtualized
- background indexing should avoid rebuilding and sorting the entire cache for every chunk

## Testing Strategy

### Unit Tests

Add fake-player tests for:

- `READY` preload is not cleared by active player status change.
- `READY` preload hit promotes without calling `setSource()` again.
- `PRELOADING` preload hit promotes and arms fallback reveal.
- failed media marks slot `FAILED` and prevents reuse.
- stale generation signals cannot reveal or activate video.
- reset clears active and idle preload slots.
- mode switch clears old-generation slots.
- delete/rename path release clears every matching slot.
- `auto_play_next()` does not double-enter playback.
- privacy blocking prevents reveal in auto-play-off and stopped states.

### Integration Smoke

Extend generated-video smoke to measure:

- first activation source path
- next activation after preload
- previous activation after preload
- black-screen fallback path
- delete while active
- rename while active
- mode switch after preloads exist

The smoke should not rely on visual pixel inspection unless a later browser/desktop harness is added. It can inspect engine state, active source path, slot state, opacity, and status transitions.

### Manual Smoke

Manual smoke remains required for real codecs and real Windows rendering:

- two or more H.264/AAC videos
- next/previous rapid keypresses
- wheel navigation
- pause/resume with privacy mode
- auto-play off with privacy mode
- rename while loaded
- soft delete then auto next
- hard delete while loaded
- search then play result
- folder switch with existing preload

## Acceptance Criteria

The work is complete only when:

- Automated tests cover all unit-test items above.
- Generated-video smoke passes.
- `tools/run_checks.ps1` passes.
- `tools/package_smoke.ps1` passes.
- Manual smoke results are recorded.
- No player slot can be reused solely because a stale `path` field matches.
- Preloaded next/previous slots survive active-player status updates.
- Active reveal is impossible when generation/path/privacy checks fail.
- Folder/search performance risks have either been fixed or documented with measured thresholds and follow-up tasks.

## Rollout Plan

1. Add state-machine data structures and fake-player tests.
2. Implement `PlayerEngine` around the existing pool behavior.
3. Redirect `VideoSorter.play_video()` through the engine.
4. Move preload planning into the engine.
5. Move reveal/status handling into the engine or a narrow callback boundary.
6. Update delete/rename/reset/mode-switch flows to use engine APIs.
7. Extend smoke tests.
8. Measure and reduce UI-thread scan/search stalls.
9. Update playback documentation and manual smoke checklist.

## Risks

- Qt media statuses can differ across codecs and Windows installations.
- Some sources may never emit the expected status sequence.
- Over-aggressive eviction could reduce preload effectiveness.
- Under-aggressive retention could hold file handles and break delete/rename.
- Privacy behavior must be tested carefully because reveal bugs are user-visible.

## Implementation Decisions

- Create `src/managers/player_engine.py` and keep `PlayerManager` as a lower-level pool/slot owner during migration.
- Keep highlight mode single-slot in v2.
- Include measurement hooks and smoke coverage for search/list rendering in the first implementation plan.
- Defer major list virtualization unless measurements prove that current rendering blocks real browsing.
