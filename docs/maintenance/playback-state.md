# YDManager Playback State Notes

## Player Pools

`PlayerManager` owns separate player pools per view mode:

- `main`: 3 players for smoother file switching and preload.
- `A`: 3 players for tag-filter playback.
- `B`: 3 players for tag-filter playback.
- `trash`: 3 players for trash review.
- `highlight`: 1 player to keep highlight replay deterministic.

Each pool entry stores:

- `player`: `QMediaPlayer`
- `audio`: `QAudioOutput`
- `item`: `QGraphicsVideoItem`
- `path`: currently loaded path or `None`

`current_mode` selects the active pool. `active_indices[current_mode]` selects the visible/controllable player in that pool.

## Selection Rules

`prepare_player_for_path(path)`:

1. Reuses a player in the current pool if it already holds the requested normalized path.
2. Otherwise chooses the first idle player that is not the current active index.
3. Falls back to index `0` for single-player pools such as `highlight`.
4. Updates `active_indices[current_mode]` before returning the selected entry.

`set_active_index(index)` and `get_player_by_index(index)` reject out-of-range indexes. `switch_mode(mode)` rejects unknown modes before releasing the current pool, so a bad caller cannot accidentally blank the active player state.

## Mode Switching

`switch_mode(target_mode)` releases all players in the old pool by:

- stopping playback,
- clearing the media source,
- hiding the video item,
- muting audio,
- clearing the loaded path.

It then changes `current_mode` and unblocks signals on the target mode's active player.

## Loaded File Release

Before hard-delete or other physical file operations, callers should use `stop_and_release_path(path)`. It scans every mode pool and, for matching normalized paths:

- stops the player,
- clears the media source to release the file handle,
- hides the video item,
- lowers the video item z value,
- mutes audio,
- clears `path`.

Soft delete moves only app metadata into internal trash and does not physically remove the file, so it does not require the same pre-delete file-handle release.

## Same-File Seek And Highlight Replay

`VideoSorter.play_video()` intentionally avoids reloading the same source. If the current source already matches the target path, it seeks when the requested start position differs by more than one second, then resumes playback if needed. Highlight replay delegates to `_execute_seek_and_play(start_pos)`, so repeated replay of the same highlight should seek on the active player rather than creating a new source load.

## Manual Smoke Focus

The manual playback checklist should cover:

- play/pause,
- previous/next file,
- same-file highlight replay,
- rename while loaded,
- hard delete while loaded,
- soft delete followed by auto-play next,
- mode switches between main, A/B filter, highlight, and trash.
