# YDManager Playback State Notes

## Player Engine v2

`PlayerEngine` owns explicit slot state for each Qt player:

- `EMPTY`
- `PRELOADING`
- `READY`
- `ACTIVE`
- `FAILED`
- `STALE`

Fast browsing keeps the active video plus next and previous candidates in the current generation. A `READY` neighbor can be promoted without resetting its media source. A `PRELOADING` neighbor can be promoted while the fallback reveal timer remains armed. A slot is never reused solely because a stale metadata path matches; the actual `QMediaPlayer.source()` must match the expected path.

`PlayerManager` still owns the physical Qt pools per view mode:

- `main`, `A`, `B`, and `trash`: 3 players each.
- `highlight`: 1 player for deterministic highlight replay.

`PlayerEngine` wraps those pool entries with `PlayerSlot` records. Activation updates `PlayerManager.active_indices[current_mode]`, so legacy `VideoSorter.player` and `audio_output` properties continue to point at the selected engine slot.

## Selection Rules

`VideoSorter.play_video(index)` now:

1. Stops stale scan/preload/fallback timers for the previous request.
2. Increments `playback_generation`.
3. Resolves the selected path and start position.
4. Delegates source activation to `PlayerEngine.activate(...)`.
5. Plans next/previous preloads immediately with `PlayerEngine.plan_neighbors(...)`.

READY preloads are revealed immediately when promoted. New loads remain hidden until `LoadedMedia`/`BufferedMedia` or a guarded fallback reveal. Media status and position callbacks are ignored when they come from an inactive player or fail generation/source/privacy checks.

## Mode Switching

`switch_mode(target_mode)` releases all players in the old pool by:

- stopping playback,
- clearing the media source,
- hiding the video item,
- muting audio,
- clearing the loaded path.

It then changes `current_mode` and unblocks signals on the target mode's active player.

## Loaded File Release

Before hard-delete or other physical file operations, callers should use `PlayerEngine.clear_path(path)`. It scans every engine slot and, for matching normalized paths or matching actual player sources:

- stops the player,
- clears the media source to release the file handle,
- hides the video item,
- lowers the video item z value,
- mutes audio,
- clears `path`.

Soft delete moves only app metadata into internal trash and does not physically remove the file, so it does not require the same pre-delete file-handle release.

## Same-File Seek And Highlight Replay

`PlayerEngine.activate()` intentionally avoids reloading the same source. If the current source already matches the target path, the slot is reused across the new playback generation instead of calling `setSource()` again. Highlight replay delegates to `_execute_seek_and_play(start_pos)`, so repeated replay of the same highlight should seek on the active player rather than creating an unnecessary source load.

## Manual Smoke Focus

The manual playback checklist should cover:

- play/pause,
- previous/next file,
- same-file highlight replay,
- rename while loaded,
- hard delete while loaded,
- soft delete followed by auto-play next,
- mode switches between main, A/B filter, highlight, and trash.
