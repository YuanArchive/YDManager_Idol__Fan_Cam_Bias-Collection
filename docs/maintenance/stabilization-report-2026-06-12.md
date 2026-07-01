# YDManager Stabilization Report - 2026-06-12

## Automated Result

- Latest rerun: 2026-06-15.
- `tools/run_checks.ps1`: 272 unittest cases passed.
- `compileall`: passed for `main.py`, `src`, `tests`, and `tools`.
- Synthetic scan/cache smoke: passed from `tools/run_checks.ps1`.
- Source GUI startup smoke: passed from `tools/run_checks.ps1`.
- Release audit: passed from `tools/run_checks.ps1`.
- Import smoke: passed from repository root.
- Cross-CWD import smoke: passed from `%TEMP%` with the repository on `PYTHONPATH`.
- Clean release build smoke: passed in a temporary venv using `requirements-lock.txt`, isolated PyInstaller work/dist paths, and packaged startup from a non-repository working directory.
- Scripted video workflow smoke: passed with generated temporary H.264 MP4 files and temporary `%LOCALAPPDATA%`.
- Synthetic large-library scan/cache smoke: passed with generated placeholder video files and temporary `%LOCALAPPDATA%`.

## Stabilized In This Pass

- Test discovery and repeatable PowerShell verification.
- FileManager JSON parent creation, invalid trash/cache entry handling, rename bookkeeping, global search cache validation, and direct folder scan resilience.
- Resource path handling for source runs, packaged runs, fonts, icons, and image generation.
- App data migration to `%LOCALAPPDATA%\YDManager\index`.
- Search debounce cleanup so cleared or one-character searches do not resurrect stale results.
- Background indexer stop/cancellation basics, folder-history snapshots, reset-time shutdown, and symlink/reparse-point avoidance in recursive scans.
- Folder-history removal now prunes matching global cache entries and skips malformed cache records.
- ShortcutHandler regression coverage for privacy blocking, search input passthrough, and Delete routing.
- PlayerManager regression coverage for path reuse, idle-player selection, invalid mode/index defense, and loaded-file release visual/audio cleanup.
- Playback state notes document player pool rules and manual smoke focus.
- Individual hard delete now requires confirmation before file-handle release or deletion.
- ShortcutHandler regression coverage now includes Tab movement between search and file list.
- Shift-alone search focus behavior is covered by regression tests.
- Indexing chunk refresh now coalesces current-folder `load_files()` calls through a single-shot timer.
- Generated-video workflow smoke covers source loading, tag persistence, highlight save/replay, hash rename while loaded, soft delete, trash mode, and restore.
- PyInstaller spec, installer script, build guide, release lock file, and manual smoke checklist.
- Bulk trash clearing now releases loaded media paths before deletion and refreshes the trash list UI.
- Folder-history removal now stops indexing first, filters late worker chunks from removed folders, and clears stale `root_folder` state when the active folder is removed.
- Indexer stop timeout now returns failure and blocks destructive reset instead of clearing data while a worker may still emit chunks.
- Background indexing now merges cache chunks in memory and writes `video_global_cache.json` once at finish or after a successful stop, avoiding per-chunk JSON/fsync work on the GUI thread.
- Current-folder reload now uses global cache first and falls back to direct scan only when no live cached entries exist, including search-clear restore paths.
- Manual refresh and folder-history clicks now force a disk scan so explicit user reloads cannot be hidden by stale cache data.
- New zero-start media loads now arm the fallback screen reveal path so missed/delayed media status signals do not leave the video hidden.
- Malformed runtime file/trash/global-cache records are skipped during save, hard delete, clear trash, and rename cleanup paths.
- Soft delete and restore now skip malformed trash/global-cache records instead of raising direct `path` lookup errors.
- Background index chunks no longer re-add trashed files, removed-folder tombstones are cleared on re-add, stale `folder` metadata no longer overrides canonical path containment, and global search omits missing files.
- Search submit now uses the same one-character guard as debounced search, privacy pause blocks Shift-only search focus, reset clears stale active player paths, and autoscan timers do not start while auto-play is disabled.
- Background indexing now skips only the failing directory entry on transient entry-level `OSError`, not the rest of the directory.
- Highlight display/add paths now sanitize malformed timestamp data instead of crashing on corrupt JSON.
- Restore now refuses missing files so dead paths are not resurrected into main/global lists.
- Playback-rate toast messages now use plain text so the escaped status renderer does not display raw HTML markup.
- Package smoke now checks bundled assets, fonts, qtawesome data, and key Qt platform/multimedia plugin folders, and preserves temporary build output when a failure occurs.
- Installer build script now derives the expected installer filename from `setup.iss` version metadata instead of hardcoding the release version in multiple places.
- Synthetic large-library smoke now exercises direct folder scanning and cache reload with generated placeholder media files.
- Source GUI startup smoke is now a reusable script and part of the default local check command.
- GitHub Actions CI now runs the project check script and generated-video workflow smoke on Windows.
- Installer build script now validates the packaged runtime tree before invoking Inno Setup, reducing stale or partial `dist` release risk.
- Background index chunks from nested folders under the active root now schedule the same coalesced UI refresh as exact-root chunks.
- `scan_folder()` and `get_current_list()` now skip malformed trash records instead of crashing.
- `BUILD.md` now documents installer output as derived from `setup.iss` version metadata instead of hardcoding the current release filename.
- Hash rename now updates the UI item's stored path even when the current-list view is a sanitized copy, preventing follow-up soft delete from targeting the old filename.
- PyInstaller now bundles only runtime assets, excludes installer-only bitmap assets from `_internal\assets`, and disables UPX for more reproducible release output.
- Runtime and build requirements are split between `requirements.txt` and `requirements-build.txt`, while `requirements-lock.txt` remains the combined release lock.
- Packaging static tests now ensure every direct runtime/build requirement pin is represented in `requirements-lock.txt`.
- Packaging static tests now guard Inno installer assets, recursive install flags, PyInstaller hidden imports, and package preflight list parity.
- Delete in highlight mode now routes to highlight deletion instead of soft-deleting the source video.
- Highlight replay now ignores stale UI rows when the model list is shorter, avoiding an `IndexError`.
- Hard-delete failure behavior is covered so failed permanent deletes keep the row in place and do not advance playback.
- Source/release checks now run a Python 3.10.x preflight before continuing.
- Highlight save now has coverage for using duration when the player is at `EndOfMedia` with position `0`.
- Highlight replay now has coverage for seeking to the selected highlight start position.
- Bulk restore now has coverage for restoring existing trash entries while leaving missing-file trash records untouched.
- ShortcutHandler regression coverage now includes Enter/R/3/arrow/playback-rate routing across main, highlight, and trash modes.
- README shortcut tables now document mode-specific Delete, Enter, and R behavior and are guarded by a static test.
- Release audit now checks git candidate files for generated artifact roots and local machine path leakage.
- Cleanup static tests now guard against duplicated startup display logs and repeated names in import statements.
- Parallel code review found no critical issues; its important stale-count and malformed soft-delete/restore findings are addressed.
- Player Engine v2 introduces explicit slot state, generation guards, preload promotion, path/source reveal validation, and privacy-aware reveal checks.
- Player Engine v3 continuity work separates visible menu/list navigation from the active watch session, keeps passive A/B/highlight/trash/search refreshes from stealing playback, and makes non-active file actions avoid unintended auto-advance.

## Remaining Release Risks

- Full hands-on manual video workflow has not been completed with user-selected media; the generated-MP4 scripted workflow passed.
- Cache-miss folder loading can still scan on the GUI thread; synthetic scan/cache smoke now gives a repeatable baseline, but true huge-library profiling with user-like storage is still recommended.
- Player state transitions and same-highlight replay still need manual confirmation where real Qt playback timing matters.
- Shortcut/privacy workflows are broadly covered by unit tests; the full manual checklist still needs hands-on confirmation in the real UI.
- Inno Setup installer compilation was not verified because `ISCC.exe` is not available on this machine; it was not found on `PATH` or the default Inno Setup 6 install path.
- Symlinked or reparse-point media paths are intentionally skipped by scanners to avoid recursive loops; document a different policy before enabling symlink-file support.

## Recommended Next Scope

1. Run the manual smoke checklist with two small videos outside the repository.
2. Run `tools/perf_scan_smoke.py --files <larger-count>` on user-like storage and move remaining direct scans off the GUI thread if measured pauses are unacceptable.
3. Continue adding fake-main tests for unverified shortcut and player edge cases.
4. Add targeted `PlayerManager` tests or a scripted Qt smoke harness for loaded-file edge cases.
5. Build the Inno installer on a machine with Inno Setup 6 installed.
