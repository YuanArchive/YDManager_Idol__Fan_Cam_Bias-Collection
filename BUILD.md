# YDManager Build Guide

This project is Windows-only because it imports Win32 APIs, BlurWindow, and Qt Multimedia.
Use Python 3.10.x for source checks and release builds. The local check and
package smoke scripts run `tools\check_python_version.py` before continuing.

## Clean Build

For a full release smoke from a fresh temporary virtual environment:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\package_smoke.ps1
```

For a local developer build:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-build.txt
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_checks.ps1
$BuildWork = Join-Path $env:TEMP "YDManager-pyi-build"
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --workpath $BuildWork --distpath .\dist YDManager.spec
```

For release builds, install the fully pinned lock file instead of the shorter
runtime/build requirements files:

```powershell
pip install -r requirements-lock.txt
```

Expected output:

```text
dist\YDManager\YDManager.exe
dist\YDManager\_internal\assets\icon.ico
dist\YDManager\_internal\assets\fonts\Pretendard-Medium.ttf
```

## Included Assets

`YDManager.spec` includes:

- `dist\YDManager\_internal\assets\icon.ico`
- `dist\YDManager\_internal\assets\fonts\Pretendard-Medium.ttf`
- `dist\YDManager\_internal\assets\fonts\Pretendard-Bold.ttf`
- `dist\YDManager\_internal\assets\fonts\LICENSE_Pretendard.txt`
- qtawesome package data

Installer-only bitmap assets such as `assets\installer_sidebar.bmp` and
`assets\installer_header.bmp` are intentionally excluded from the PyInstaller
runtime bundle. UPX compression is disabled in `YDManager.spec` so release
outputs do not depend on whether UPX happens to be installed on the builder.

## Runtime Data

Mutable app data is stored outside the install directory:

- Index/cache files: `%LOCALAPPDATA%\YDManager\index`
- Logs: `%LOCALAPPDATA%\YDManager\logs`
- Font cache: `%LOCALAPPDATA%\YDManager\fonts`

On first run after upgrading from the source-tree cache layout, existing `index/*.json` files are copied into `%LOCALAPPDATA%\YDManager\index` only when the target file is missing.

## Smoke Test

After building, launch the executable from a directory other than the repository root:

```powershell
$ExePath = Join-Path (Get-Location) "dist\YDManager\YDManager.exe"
Push-Location $env:TEMP
& $ExePath
Pop-Location
```

Then run the manual checklist in `docs/maintenance/manual-smoke-test.md`.

If `ffmpeg` is installed, run the generated-video workflow smoke:

```powershell
.\.venv\Scripts\python.exe .\tools\smoke_video_workflow.py
```

## Installer

Install Inno Setup 6 and ensure `ISCC.exe` is on `PATH`, then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\build_installer.ps1
```

The script derives the installer filename from `MyAppVersion` in `setup.iss`.
Expected output pattern:

```text
installer\YDManager_Setup_v<version-from-setup.iss>.exe
```
