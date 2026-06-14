# YDManager Stabilization Master Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` for bounded implementation tasks, `superpowers:systematic-debugging` for failures, and `superpowers:verification-before-completion` before claiming completion. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 장기 방치된 YDManager를 다시 신뢰 가능한 상태로 만들기 위해 실행/테스트 baseline, 데이터 무결성, 경로/자산 안정성, UI/플레이어 안정성, 패키징 재현성, 문서까지 순차적으로 복구한다.

**Architecture:** 먼저 테스트와 실행 기준을 고정하고, 그 다음 순수 로직(`FileManager`, path/resource helpers)을 테스트로 잠근 뒤 GUI/Qt 의존 영역을 작게 나누어 안정화한다. 대규모 `main.py` 리팩터링은 즉시 분해하지 않고, 파일 액션/플레이어/검색/설정처럼 이미 분리된 경계를 강화하면서 진행한다.

**Tech Stack:** Python 3.10, PyQt6, Qt Multimedia, qtawesome, BlurWindow, send2trash, unittest, PyInstaller.

---

## Current Baseline

- Repository root during this run: project checkout root (`<repo-root>`)
- Branch: `master`
- Existing dirty files before this plan: `.gitignore`, `src/managers/file_manager.py`, `tests/test_file_manager.py`
- Stabilization edit already applied in this session: `tests/__init__.py`
- Stabilization fixes already applied in this session:
  - `tests/__init__.py` added so root unittest discovery works.
  - `src/managers/file_manager.py` now creates missing JSON parent directories.
  - `src/managers/file_manager.py` skips invalid trash cache entries instead of crashing on missing `path`.
  - `src/managers/file_manager.py` updates `global_files` when `rename_file_by_path()` renames a file.
  - `main.py` starts the search debounce timer for non-empty search text.
  - `src/ui/ui_components.py` has one merged `ProVideoView.resizeEvent()` handler.
  - `tools/run_checks.ps1` added for repeatable local checks.
  - `src/core/consts.py` now resolves project resources from the project root or PyInstaller `_MEIPASS`, not the current working directory.
  - `main.py`, `src/utils/utils_font.py`, `src/ui/settings_ui.py`, and `tools/generate_images.py` now use stable resource paths.
  - `src/core/threads.py` now ignores `OSError` during recursive scans so folders disappearing mid-scan do not kill indexing.
  - Mutable index data now defaults to `%LOCALAPPDATA%\YDManager\index`.
  - Existing project `index/*.json` files are copied to AppData only when the target file is missing.
  - `README.md` now documents venv setup, checks, AppData/log/font locations, and the corrected project folder structure.
  - `.gitignore` no longer ignores `BUILD.md`, `YDManager.spec`, or `setup.iss`.
  - `docs/maintenance/manual-smoke-test.md` records automated, startup, video, and packaging smoke checks.
  - GUI startup smoke was run with a short Qt timer and exited `startup smoke ok: 0`.
  - `YDManager.spec`, `BUILD.md`, and `setup.iss` were added for reproducible Windows builds.
  - PyInstaller build completed successfully and produced `dist\YDManager\YDManager.exe`.
  - Packaged startup smoke from a different working directory completed by launching the EXE and stopping the process after it stayed alive.
  - Packaging static tests now guard `YDManager.spec`, `setup.iss`, and `BUILD.md` basics.
  - `FileManager.update_global_cache()` and global search now skip invalid cache entries instead of crashing on missing `path`.
  - `FileManager.scan_folder()` now uses an `os.scandir` recursive helper and ignores `OSError` while preserving recursive video collection, trash exclusion, and sorted output.
  - `main.py` now stops pending search debounce work when search is cleared/submitted and prevents one-character debounce searches from resurrecting stale results.
  - `src/managers/file_manager.py` now requests interruption and waits longer when stopping the background indexer.
  - `src/core/threads.py` now checks cancellation before opening folders and avoids following symlink/reparse-point directories during recursive indexing.
  - `FileManager.scan_folder()` now avoids following symlink/reparse-point directories during direct scans.
  - `FileManager.start_indexing()` now passes a folder-history snapshot to the worker instead of the live list.
  - `FileManager.reset_all_data()` now stops the background indexer before clearing caches.
  - `FileManager.remove_folder_from_history()` now prunes matching global cache entries while skipping malformed entries.
  - `ShortcutHandler` now has regression coverage for privacy blocking, search-focus key passthrough, and Delete routing.
  - `PlayerManager` now has regression coverage for path reuse, idle-player selection, invalid mode/index defense, and loaded-file release visibility/audio cleanup.
  - `docs/maintenance/playback-state.md` documents player pool rules, mode switching, release semantics, and manual playback smoke focus.
  - Individual hard delete now asks for confirmation before releasing player handles or deleting files.
  - `ShortcutHandler` Tab search/file-list behavior is covered by regression tests.
  - Shift-alone search focus behavior is covered by regression tests.
  - Indexing chunk refresh now coalesces current-folder UI reloads through a single-shot timer instead of calling `load_files()` immediately per chunk.
  - Inno Setup compiler was checked on this machine; `ISCC.exe` was not found on `PATH` or the default Inno Setup 6 location.
  - `tools/smoke_video_workflow.py` now generates temporary MP4 files with `ffmpeg` and runs a real VideoSorter workflow against temporary app data.
  - `requirements-lock.txt` pins direct and transitive release dependencies.
  - `setup.iss` now uses a stable valid GUID-style `AppId`.
  - `BUILD.md` documents isolated PyInstaller `--workpath` usage and non-hardcoded packaged startup smoke commands.
  - `tools/run_checks.ps1` now includes a cross-CWD import smoke.
  - `README.md` download text now matches `YDManager_Setup_v8.1.exe` and documents media codec caveats.
  - `docs/maintenance/manual-smoke-test.md` now includes shortcut/privacy and loaded-file playback edge cases.
  - Bulk trash clearing now releases every trash media path before deletion and refreshes the visible trash list.
  - `FileManager.remove_folder_from_history()` now stops the indexer first and filters late worker chunks from removed folders.
  - `VideoSorter.delete_folder_history_item()` now clears stale `root_folder` state when the active folder is removed.
  - `FileManager.stop_indexing()` now reports timeout failure, and destructive reset aborts if the worker does not stop.
  - Background indexing cache chunks now merge in memory and persist once on finish or after a successful stop, instead of writing the full global cache JSON per chunk.
  - Current-folder reloads now use global cache first and fall back to direct scan only when the cache has no live entries, including search-clear restore paths.
  - Manual refresh and folder-history clicks now force a disk scan instead of trusting the cache-first reload path.
  - Zero-start new media loads now arm the fallback screen reveal path.
  - Malformed runtime file/trash/global-cache records are skipped during save, hard delete, clear trash, and rename cleanup paths.
  - Soft delete and restore now skip malformed trash/global-cache records instead of raising direct `path` lookup errors.
  - Background index chunks no longer re-add trashed files, removed-folder tombstones are cleared on re-add, stale `folder` metadata no longer overrides canonical path containment, and global search omits missing files.
  - Search submit now uses the same one-character guard as debounced search, privacy pause blocks Shift-only search focus, reset clears stale active player paths, and autoscan timers do not start while auto-play is disabled.
  - Background indexing now skips only the failing directory entry on transient entry-level `OSError`, not the rest of the directory.
  - Highlight display/add paths now sanitize malformed timestamp data, and restore refuses missing files so dead paths are not resurrected.
  - Playback-rate toast messages now use plain text so the escaped status renderer does not display raw HTML markup.
  - Package smoke now checks bundled assets, fonts, qtawesome data, and key Qt platform/multimedia plugin folders, and preserves temporary build output when a failure occurs.
  - Installer build script now derives the expected installer filename from `setup.iss` version metadata instead of hardcoding the release version in multiple places.
  - `tools/perf_scan_smoke.py` now generates a synthetic large-library tree and verifies direct scan plus global-cache reload counts/timings.
  - `tools/startup_smoke.py` now opens and closes the source GUI against temporary app data and is included in `tools/run_checks.ps1`.
  - `.github/workflows/ci.yml` now runs the project check script and generated-video workflow smoke on Windows.
  - `tools/build_installer.ps1` now validates the packaged runtime tree before invoking Inno Setup.
  - Background index chunks from nested folders under the active root now schedule the coalesced UI refresh timer.
  - `scan_folder()` and `get_current_list()` now skip malformed trash records.
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
- Verified commands:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test*.py" -v
.\.venv\Scripts\python.exe -m compileall -q main.py src tests
.\.venv\Scripts\python.exe -c "import main; import src.managers.file_manager; import src.managers.player_manager; import src.controllers.file_action_controller; import src.ui.ui_components; print('import smoke ok')"
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_checks.ps1
```

- Verified result on 2026-06-15: 173 unittests pass, compileall passes, source GUI startup smoke passes, release audit passes, synthetic scan/cache smoke passes, root import smoke and cross-CWD import smoke pass, `tools/run_checks.ps1` exits 0.
- Verified release build on 2026-06-14: `tools\package_smoke.ps1` creates a clean temporary venv using `requirements-lock.txt`, isolated PyInstaller `--workpath`/`--distpath`, and packaged startup smoke from a non-repository working directory; it exits 0 and cleans its temporary build output.
- Verified scripted video workflow on 2026-06-14: `.\.venv\Scripts\python.exe .\tools\smoke_video_workflow.py` generated two temporary H.264 MP4 files and exited with `video workflow smoke ok`.
- Verified synthetic large-library smoke on 2026-06-12: `.\.venv\Scripts\python.exe .\tools\perf_scan_smoke.py` generated 800 placeholder video files and exited with `PERF_SCAN_SMOKE_OK`.

## Execution Policy

- Do not revert user changes.
- Before behavior changes, write or extend tests first.
- Keep write scopes disjoint for parallel workers.
- Use the `.venv` interpreter for baseline verification.
- Treat real GUI playback and PyInstaller checks as manual or Windows desktop smoke checks unless a safe automated harness exists.

---

## Phase 1: Baseline Freeze And Workspace Hygiene

**Goal Prompt:**  
Audit the repository's current dirty state, test discovery, importability, dependency availability, and generated local artifacts. Preserve user changes. Make only low-risk changes that improve future verification, such as making existing tests discoverable.

**Files:**
- Inspect: `.gitignore`
- Inspect: `requirements.txt`
- Inspect: `tests/test_file_manager.py`
- Modify if needed: `tests/__init__.py`

- [x] Run `git status --short --branch`.
- [x] Run default and explicit unittest discovery.
- [x] Run compile smoke.
- [x] Run import smoke.
- [x] Add `tests/__init__.py` so `unittest discover -v` finds tests from repo root.

**Gate:**  
`.\.venv\Scripts\python.exe -m unittest discover -v` must run at least one test and exit 0.

## Phase 2: Test Harness And CI-Ready Commands

**Goal Prompt:**  
Turn the current ad hoc test baseline into repeatable project commands. Add a minimal documented test command and, if accepted, a lightweight test runner script that works on Windows PowerShell without requiring pytest.

**Files:**
- Modify: `README.md`
- Optional create: `tools/run_checks.ps1`
- Optional create: `docs/maintenance/test-baseline.md`

- [x] Document the `.venv` test command.
- [x] Document import smoke and compile smoke via `tools/run_checks.ps1`.
- [x] Add a PowerShell check script only if it does not conflict with existing project style.
- [x] Verify from repository root.
- [x] Verify import smoke from a different working directory.
- [x] Add Windows GitHub Actions CI for the project check script and generated-video workflow smoke.

**Gate:**  
One command should run unittest, compileall, and import smoke with exit code 0.

## Phase 3: FileManager Data Integrity

**Goal Prompt:**  
Stabilize JSON persistence, path normalization, folder history, tag/highlight persistence, trash cache behavior, and file rename/delete bookkeeping. Use unittest with temporary directories and no real user media files.

**Files:**
- Modify: `tests/test_file_manager.py`
- Modify only after failing tests: `src/managers/file_manager.py`

- [x] Add tests for `save_json()` creating missing parent directories.
- [x] Add tests for invalid JSON fallback behavior.
- [x] Add tests for invalid trash cache entries.
- [x] Add tests for malformed trash records in direct scan and current-list paths.
- [x] Add tests for duplicate folder history normalization.
- [x] Add tests for tag toggle persistence and display text refresh.
- [x] Add tests for soft delete and restore using in-memory lists.
- [x] Add tests for bulk restore with mixed existing and missing trash entries.
- [x] Add tests for `rename_file_by_path()` updating tags, highlights, and global cache.

**Gate:**  
`.\.venv\Scripts\python.exe -m unittest discover -v` passes with the new FileManager tests.

## Phase 4: Path, Resource, And App Data Strategy

**Goal Prompt:**  
Remove accidental current-working-directory dependence from resource and app-data paths. Separate immutable bundled resources from mutable user data, and make behavior consistent for source runs and PyInstaller builds.

**Files:**
- Modify: `src/core/consts.py`
- Modify: `src/utils/utils_font.py`
- Modify: `src/ui/settings_ui.py`
- Modify: `main.py`
- Modify or create tests around path helpers.

- [x] Define project root/resource root from `__file__` and PyInstaller `_MEIPASS`.
- [x] Define mutable app data root under `%LOCALAPPDATA%\YDManager`.
- [x] Keep migration/backward compatibility for existing `index/*.json` if required.
- [x] Replace direct `os.getcwd()` asset lookups with shared helpers.
- [x] Test helper behavior without launching the GUI.

**Gate:**  
Path helper tests pass, import smoke passes from repository root and from one different working directory.

## Phase 5: Indexing And Search Smoothness

**Goal Prompt:**  
Audit background indexing, global cache updates, search debounce, duplicate prevention, and UI refresh pressure. Fix root causes only after reproducing with tests or focused instrumentation.

**Files:**
- Modify: `src/core/threads.py`
- Modify: `src/managers/file_manager.py`
- Modify if needed: `main.py`
- Test: `tests/test_file_manager.py`
- Optional test: `tests/test_indexing.py`

- [x] Test that scanning ignores non-video files and duplicates.
- [x] Test recursive folder scan, non-video exclusion, trash exclusion, and sorted output.
- [x] Test that removed folder history prunes global cache correctly.
- [x] Add regression coverage for stale search debounce clearing and one-character debounce behavior.
- [x] Add regression coverage for direct scanner and background indexer symlink/reparse-point avoidance.
- [x] Add basic `BackgroundIndexer` cancellation checks and make `FileManager.stop_indexing()` request interruption.
- [x] Stop indexing before reset and pass a history snapshot to each indexing worker.
- [x] Test that missing folders during recursive scan are ignored instead of crashing.
- [x] Replace `scan_folder()` `os.walk` traversal with guarded `os.scandir` recursion.
- [x] Prevent repeated heavy `load_files()` calls during large chunk updates with a single-shot refresh timer.
- [x] Schedule the coalesced refresh timer for nested-folder chunks under the active root.

**Gate:**  
Unit tests pass and manual large-folder indexing does not freeze the UI beyond acceptable short pauses.

## Phase 6: Playback State Machine Stability

**Goal Prompt:**  
Map the player state transitions for main/highlight/trash/filter modes and reduce race-prone direct player manipulation. Prioritize file lock release, same-file seek behavior, preload safety, and privacy mode visibility.

**Files:**
- Modify: `src/managers/player_manager.py`
- Modify: `main.py`
- Modify: `src/controllers/file_action_controller.py`
- Optional create: `docs/maintenance/playback-state.md`

- [x] Document current player pool modes and active index rules.
- [x] Add lightweight tests for pure `PlayerManager` selection logic only if Qt object creation is stable in test mode.
- [x] Run scripted video workflow smoke with generated MP4 files for source load, tag, highlight, hash rename, soft delete, trash, and restore.
- [x] Add regression coverage for hash rename updating the UI item's stored path before subsequent file actions.
- [x] Add stale-row guard coverage for highlight replay.
- [x] Add coverage for highlight replay seeking to the selected start position.
- [x] Add coverage for saving an end-of-media highlight at the media duration.
- [x] Add hard-delete failure branch coverage to prevent UI/model drift.
- [ ] Manually verify play, pause, next/previous, same-file highlight replay, rename while loaded, and delete while loaded.
- [ ] Remove duplicated log lines and unreachable legacy members after verification.

**Gate:**  
Manual playback smoke checklist passes on Windows with at least one sample video outside the repository.

## Phase 7: UI Event And Shortcut Reliability

**Goal Prompt:**  
Stabilize keyboard-first workflows, focus changes, privacy mode input blocking, drag/drop folder handling, and destructive action confirmations.

**Files:**
- Modify: `src/core/event_handler.py`
- Modify: `src/core/signal_setup.py`
- Modify: `src/ui/ui_components.py`
- Modify if needed: `main.py`

- [x] Verify shortcut matrix from README against actual code.
- [ ] Test or manually verify Tab focus cycle, Shift search focus, Delete behavior in folder/file/trash modes, Enter behavior in main/highlight/trash modes.
- [x] Add ShortcutHandler regression tests for privacy Delete blocking, privacy Space resume, search-focus Delete passthrough, and Delete routing.
- [x] Add ShortcutHandler regression coverage so Delete in highlight mode deletes the highlight, not the source file.
- [x] Add ShortcutHandler regression coverage for Enter/R/3/arrow/playback-rate routing.
- [x] Add README static coverage for mode-specific shortcut documentation.
- [x] Add ShortcutHandler regression tests for Tab search/file-list focus behavior.
- [x] Add regression tests for Shift-alone search focus behavior.
- [x] Ensure destructive actions always have confirmation or safe trash behavior.
- [ ] Remove duplicate imports and low-value dead comments from UI modules only when touching nearby code.

**Gate:**  
Shortcut manual smoke checklist passes and README shortcut table matches behavior.

## Phase 8: Packaging And Release Reproducibility

**Goal Prompt:**  
Make Windows release builds reproducible. Align source version, release version, PyInstaller assets, Qt plugins, fonts, icons, and installer metadata.

**Files:**
- Inspect/modify: `.gitignore`
- Optional restore or create: `YDManager.spec`
- Optional restore or create: `setup.iss`
- Modify: `requirements.txt`
- Modify: `README.md`

- [x] Decide whether `YDManager.spec`, `setup.iss`, and `BUILD.md` should be tracked.
- [x] Split runtime requirements from build requirements if useful.
- [x] Pin or lock dependency versions for release builds.
- [x] Ensure `assets/icon.ico`, `assets/fonts/*`, and qtawesome package data are included in the PyInstaller output.
- [x] Exclude installer-only bitmap assets from the PyInstaller runtime bundle.
- [x] Disable UPX so release output does not depend on builder-local UPX availability.
- [x] Verify direct dependency pins stay represented in `requirements-lock.txt`.
- [x] Add Python 3.10.x preflight to local checks and package smoke.
- [ ] Confirm Qt multimedia/platform plugin coverage on the final release installer.
- [x] Build in the current Windows virtual environment.
- [x] Build from a clean temporary virtual environment with isolated PyInstaller work/dist paths.
- [x] Validate required packaged runtime paths before invoking the Inno installer build.
- [x] Document installer output using the version derived from `setup.iss`.
- [ ] Build in a separate clean Windows machine or VM.

**Gate:**  
Fresh environment can build an executable, launch it, show fonts/icons, and play a video.

## Phase 9: Documentation And Onboarding

**Goal Prompt:**  
Update user/developer documentation so a future maintainer can install, test, run, build, and troubleshoot without rediscovering local assumptions.

**Files:**
- Modify: `README.md`
- Optional create: `docs/maintenance/developer-guide.md`
- Optional create: `docs/maintenance/manual-smoke-test.md`

- [x] Fix README encoding replacement characters found in section headings.
- [x] Correct clone directory and project structure.
- [x] Align version text with `src/core/consts.py`.
- [x] Add Windows-only note, `.venv` setup, test command, and log location.
- [x] Add known media codec caveats.
- [x] Add manual smoke checklist, including shortcut/privacy and packaging checks.

**Gate:**  
README commands work from a clean clone on Windows.

## Phase 10: Final Regression, Review, And Release Gate

**Goal Prompt:**  
Run the full automated baseline, execute manual GUI smoke tests, review git diff, and produce a release readiness report with fixed items, remaining risks, and next recommended branch/PR scope.

**Files:**
- Inspect all changed files.
- Optional create: `docs/maintenance/stabilization-report-2026-06-12.md`

- [x] Run unittest discovery.
- [x] Run compileall.
- [x] Run import smoke, including cross-CWD import smoke.
- [x] Run GUI startup smoke.
- [x] Run scripted video workflow smoke with generated sample videos.
- [ ] Run full manual video workflow smoke checklist.
- [x] Review diff for accidental generated files, personal paths, or user-data leakage.
- [x] Request code review before final integration.

**Gate:**  
Automated commands pass and manual smoke results are recorded.

---

## Parallel Work Lanes

**Lane A: Test And Data Core**
- Owns: `tests/`, `src/managers/file_manager.py`, `src/core/threads.py`
- Starts at Phase 2 and Phase 3.

**Lane B: Path, Packaging, And Docs**
- Owns: `src/core/consts.py`, `src/utils/utils_font.py`, `README.md`, packaging files.
- Starts after Phase 1 and can run beside FileManager tests.

**Lane C: Playback And UI**
- Owns: `main.py`, `src/managers/player_manager.py`, `src/controllers/file_action_controller.py`, `src/core/event_handler.py`, `src/ui/`.
- Starts after baseline tests exist, because GUI regressions need a known-good checkpoint.

## Additional Audit Findings

- `main.py` remains the largest risk surface and still mixes UI, playback, search, and workflow orchestration.
- `FileActionController` still reaches deeply into the `VideoSorter` instance; future work should narrow that contract.
- `load_files()` now uses cache first, but cache-miss direct scans can still run on the UI thread.
- `BackgroundIndexer` now has cancellation and `OSError` guards; global cache writes are batched to finish/stop, and synthetic large-library scan/cache smoke exists, but profiling on user-like storage is still needed.
- CWD-based resource paths were removed from `src/core/consts.py`, `main.py`, `src/utils/utils_font.py`, `src/ui/settings_ui.py`, and `tools/generate_images.py`; mutable data now defaults to `%LOCALAPPDATA%\YDManager\index` with one-time copy-if-missing migration from the legacy source-tree `index/`.
- README version/path drift found during the audit has been corrected for the visible release badge, clone folder, AppData/log/font locations, and `assets/fonts/`.
- Packaging reproducibility now has `YDManager.spec`, `BUILD.md`, `setup.iss`, `requirements-lock.txt`, runtime-only PyInstaller asset scope, UPX-disabled output, clean temporary venv build validation, packaged startup smoke, installer preflight validation, and Windows CI; remaining work is repo-local installer compilation on a machine with `ISCC.exe`, Qt multimedia/plugin confirmation in the installed app, and full video playback smoke.

## Master Order

1. Finish Phase 1 immediately.
2. Execute Phase 2 and Phase 3 first because they improve every later change.
3. Run Phase 4 before packaging work because paths affect runtime and release.
4. Run Phase 5, Phase 6, and Phase 7 as separate focused branches or disjoint worker tasks.
5. Run Phase 8 and Phase 9 together after source behavior stabilizes.
6. Run Phase 10 only after all planned code changes are complete.
