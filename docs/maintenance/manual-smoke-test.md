# YDManager Manual Smoke Test

Run these checks on Windows after automated checks pass.

## Automated Baseline

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_checks.ps1
```

Expected:
- `unittest` passes.
- `compileall` passes.
- Synthetic scan/cache smoke prints `PERF_SCAN_SMOKE_OK`.
- Source GUI startup smoke prints `STARTUP_SMOKE_OK`.
- Import smoke prints `import smoke ok`.
- Cross-CWD import smoke prints `cross-cwd import smoke ok`.

## GUI Startup

```powershell
.\.venv\Scripts\python.exe .\tools\startup_smoke.py
```

Expected:
- The app opens briefly and closes by itself.
- Output includes `STARTUP_SMOKE_OK`.

## Scripted Video Workflow

If `ffmpeg` is available, run the generated-MP4 workflow smoke:

```powershell
.\.venv\Scripts\python.exe .\tools\smoke_video_workflow.py
```

Expected:
- Two temporary H.264 MP4 files are generated outside the repository.
- The app opens against temporary `%LOCALAPPDATA%`.
- Output includes `video workflow smoke ok`.
- The workflow covers source loading, A-tag persistence, highlight save/replay, hash rename while loaded, soft delete, trash mode, and restore.

## Synthetic Large-Library Scan

Run the generated placeholder-file scan/cache smoke:

```powershell
.\.venv\Scripts\python.exe .\tools\perf_scan_smoke.py
```

Expected:
- A temporary folder tree is generated outside the repository.
- `scan_folder()` discovers all generated video placeholders.
- `load_main_files_from_cache()` reloads the same list from global cache.
- Output includes `PERF_SCAN_SMOKE_OK`.

## Video Workflow

See `docs/maintenance/playback-state.md` for the player mode and file-release rules this checklist exercises.

- Add a folder containing at least two small videos.
- Select the first video and verify playback starts or the first frame renders.
- Toggle audio and verify mute state changes.
- Press `Space` to pause/play.
- Use arrow keys to seek.
- Use `Up` and `Down` to move to the previous/next file.
- Press `1` and `2` to toggle A/B tags.
- Press `Enter` to add/remove `#` in the filename.
- Press `3` to save a highlight, open Highlight mode, replay it, then delete it.
- Replay the same highlight twice and verify the player seeks instead of leaving a blank frame.
- Rename the currently loaded file and verify the list, tag/highlight state, and player state stay consistent.
- Delete the currently loaded file and verify playback releases the file before it moves to internal trash.
- Press `Delete` in main mode and verify the item moves to internal trash.
- Open Trash mode, press `Delete`, choose `No`, and verify the file remains in trash.
- Press `Delete` again, choose `Yes`, and verify the file is permanently deleted only after confirmation.
- Restore another trash item and verify it appears in the main list.
- Close and relaunch the app; verify folder history, tags, trash, and highlights persist under `%LOCALAPPDATA%\YDManager\index`.

## Shortcut And Privacy Workflow

- Press `Tab` repeatedly and verify focus cycles through the expected panels.
- Press `Shift` while the main list has focus and verify the search box receives focus.
- Press `Delete` while the folder list has focus and verify the selected folder history entry is removed only after confirmation.
- Press `Delete` in file mode and verify the selected video moves to internal trash, not permanent deletion.
- Enable privacy mode, press `Space`, and verify playback pauses, audio mutes, and the video surface hides.
- While privacy mode is active, press ordinary organization keys and verify hidden video state is not accidentally changed.
- Press `ESC` only when you are ready to close the app and verify it exits immediately.

## Packaging Workflow

- Build from a clean virtual environment with `requirements-lock.txt` for release builds.
- Use a fresh PyInstaller work path outside the repository if the existing `build\` folder is locked.
- Confirm the packaged app includes `assets/icon.ico`, `assets/fonts/*`, qtawesome resources, and Qt multimedia/platform plugins.
- Launch the packaged app from a different working directory.
- Verify logs appear under `%LOCALAPPDATA%\YDManager\logs`.
