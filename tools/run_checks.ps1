$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

if (Test-Path $VenvPython) {
    $Python = $VenvPython
} else {
    $Python = "python"
}

Push-Location $Root
try {
    $env:PYTHONDONTWRITEBYTECODE = "1"

    & $Python .\tools\check_python_version.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $Python -m unittest discover -v
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $Python -m compileall -q main.py src tests tools
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $Python .\tools\perf_scan_smoke.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $Python .\tools\startup_smoke.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $Python .\tools\release_audit.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $Python -c "import main; import src.managers.file_manager; import src.managers.player_manager; import src.controllers.file_action_controller; import src.ui.ui_components; print('import smoke ok')"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $PreviousPythonPath = $env:PYTHONPATH
    if ([string]::IsNullOrEmpty($PreviousPythonPath)) {
        $env:PYTHONPATH = $Root
    } else {
        $env:PYTHONPATH = "$Root;$PreviousPythonPath"
    }

    Push-Location $env:TEMP
    try {
        & $Python -c "import main; import src.managers.file_manager; import src.managers.player_manager; import src.controllers.file_action_controller; import src.ui.ui_components; print('cross-cwd import smoke ok')"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    } finally {
        Pop-Location
        $env:PYTHONPATH = $PreviousPythonPath
    }
} finally {
    Pop-Location
}
