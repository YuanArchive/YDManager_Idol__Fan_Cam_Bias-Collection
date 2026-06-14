# Player Engine v4 Directional Preload Design

Date: 2026-06-15

## Objective

Make rapid sequential video exploration faster without weakening the Player Engine v3 watch-session continuity guarantees.

The app should still preserve the active watch session across passive menu changes, but explicit next/previous browsing should preload the most likely upcoming videos more aggressively. Fast exploration is prioritized over minimum resource use.

## Current State

`VideoSorter.play_video(index)` now activates playback through `PlayerEngine.activate(...)` and immediately calls `PlayerEngine.plan_neighbors(index, playlist, generation)`.

`PlayerEngine.plan_neighbors(...)` currently uses a balanced policy:

- preload row `index + 1` as `NEXT`;
- preload row `index - 1` as `PREVIOUS`;
- clear other non-active preloads in the current mode.

This is safe and deterministic, but it is not ideal for rapid one-direction browsing. With a three-player pool, the engine can keep only two non-active candidates. When the user repeatedly moves forward, keeping the previous row resident consumes a slot that could instead preload the next-next row.

Legacy methods such as `preload_next_file(...)` and `_execute_media_load(...)` were removed after v4 because they directly loaded `QMediaPlayer` sources outside `PlayerEngine`. The production playback path now uses `PlayerEngine.activate(...)` and `PlayerEngine.plan_neighbors(...)`.

## Approaches Considered

### Approach A: Increase Player Pool Size

Create more `QMediaPlayer` slots per mode and keep a wider preload window.

Benefits:

- Better hit rate for both forward and backward browsing.
- Simple policy once more slots exist.

Costs:

- More media handles, memory, decoder load, and file locks.
- Higher risk for hard delete/rename and lower-end machines.
- Larger regression surface before we have transition metrics.

### Approach B: Directional Policy Within Existing Three Slots

Track browsing direction at the UI coordinator and pass a directional hint to `PlayerEngine.plan_neighbors(...)`.

Policy:

- no clear direction: keep `current + next + previous`;
- repeated forward movement: keep `current + next + next2`;
- repeated backward movement: keep `current + previous + previous2`.

Benefits:

- Uses existing slot count and engine boundaries.
- Directly improves rapid sequential browsing.
- Keeps balanced behavior for the first move, clicks, and non-sequential jumps.
- Easy to test with fake players.

Costs:

- A sudden reverse after a long forward run may need to load the previous item again.

Recommendation: use Approach B first.

During code inspection, two additional preload-quality risks were identified and included in this v4 scope:

- obsolete `READY` slots can block a newly needed preload target until the next planning pass;
- passive list refreshes preserve playback correctly, but can leave next/previous preloads planned for an older visible playlist.

Both are fixed inside the same engine boundary: stale preload slots may be repurposed in the same planning pass, and passive refreshes may call `plan_neighbors(...)` without replacing the watch session.

### Approach C: Predictive Preload From Candidate Selection

Start or refresh preloads when the user merely highlights a list row, before explicit playback activation.

Benefits:

- Can improve click/keyboard latency before playback starts.

Costs:

- More coupling between passive selection and playback.
- Higher risk of accidentally stealing the watch session, which v3 just fixed.
- Needs more UI event audit before implementation.

This should be considered after directional activation preloading is stable.

## Target Behavior

### Balanced Mode

Used when:

- this is the first playback in the list;
- the user jumps to a non-adjacent row;
- the user changes direction;
- the same row is replayed;
- the direction streak is below the threshold.

Targets:

1. `index + 1` as `NEXT`
2. `index - 1` as `PREVIOUS`

### Forward Directional Mode

Used after repeated forward playback movement.

Targets:

1. `index + 1` as `NEXT`
2. `index + 2` as `FORWARD_LOOKAHEAD`
3. `index - 1` as `PREVIOUS`, only if an additional spare slot exists

### Backward Directional Mode

Used after repeated backward playback movement.

Targets:

1. `index - 1` as `PREVIOUS`
2. `index - 2` as `BACKWARD_LOOKAHEAD`
3. `index + 1` as `NEXT`, only if an additional spare slot exists

### Direction Threshold

The first adjacent move stays balanced. Directional mode starts after two consecutive moves in the same direction.

This prevents the first accidental arrow/wheel movement from evicting the opposite neighbor too aggressively.

## API Changes

`SlotRole` gains two roles:

```python
FORWARD_LOOKAHEAD = "forward_lookahead"
BACKWARD_LOOKAHEAD = "backward_lookahead"
```

`PlayerEngine.plan_neighbors(...)` gains a defaulted hint:

```python
def plan_neighbors(
    self,
    current_index: int,
    playlist: list[PlaybackItem],
    generation: int,
    preferred_direction: int = 0,
) -> None:
    ...
```

`preferred_direction` values:

- `1`: prefer forward lookahead;
- `-1`: prefer backward lookahead;
- `0`: balanced next/previous behavior.

`VideoSorter` tracks only explicit playback activation direction:

```python
last_playback_index: int | None
last_navigation_direction: int
navigation_direction_streak: int
```

Passive menu switches, search refreshes, tag/trash/highlight list rebuilds, and candidate selection do not update this direction state.

## Error Handling

The existing source/generation guards remain mandatory:

- A slot is reusable only when its actual `player.source()` matches the expected path.
- Old-generation preloads are cleared before planning new candidates.
- Active watch slots are never cleared by preload planning.
- Failed slots can be reused only after they are explicitly cleared and assigned a new source.

Directional planning must be a target-order change only. It must not bypass these guards.

When a `PRELOADING` slot emits a loaded/buffered status, the engine may mark it `READY` only if the slot generation matches the current engine generation, the slot has an expected path, and the actual player source matches that expected path.

## Tests

Add unit tests before production changes:

- `test_directional_forward_plan_prefers_next_two_items`
- `test_directional_backward_plan_prefers_previous_two_items`
- `test_balanced_plan_remains_default_without_direction`
- `test_play_video_uses_balanced_preload_until_direction_streak_repeats`
- `test_play_video_passes_forward_direction_after_repeated_forward_moves`
- `test_play_video_resets_direction_after_reverse_move`
- `test_plan_neighbors_replaces_obsolete_ready_slot_in_same_pass`
- `test_plan_neighbors_retains_same_source_ready_neighbor_across_generation_change`
- `test_activate_repairs_expected_path_when_reusing_slot_by_matching_source`
- `test_loaded_status_does_not_mark_mismatched_preload_ready`
- `test_preserve_list_refresh_replans_neighbors_for_visible_watch_without_playing`
- `test_folder_history_click_clears_engine_session_before_loading_new_folder`

Update fake engine signatures so existing app-level tests keep asserting the generation and playlist passed to the engine.

## Acceptance Criteria

- Existing v3 continuity behavior remains unchanged.
- Existing `plan_neighbors(...)` callers keep working through the default argument.
- With three slots, repeated forward browsing preloads `next` and `next2`.
- With three slots, repeated backward browsing preloads `previous` and `previous2`.
- First move and direction changes remain balanced.
- Full automated checks pass.
- `tools/smoke_player_continuity.py` still passes.
- Passive refreshes can replan preloads for a visible active watch path without calling `play_video(...)`.
- Mismatched media-status signals cannot create false `READY` preload hits.

## Spec Self-Review

- No placeholder sections remain.
- Scope is limited to directional preload planning, stale preload reuse, and passive refresh replanning.
- Pool size changes and passive candidate preloading are explicitly deferred.
- The design preserves v3 watch-session separation and file-action safety.
