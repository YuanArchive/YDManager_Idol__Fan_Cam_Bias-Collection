$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$TempBase = [System.IO.Path]::GetTempPath()
$TempRoot = Join-Path $TempBase ("ydm-package-smoke-" + [System.Guid]::NewGuid().ToString("N"))
$Log = Join-Path $TempBase ("ydm-package-smoke-" + [System.Guid]::NewGuid().ToString("N") + ".log")
$PackageSmokeSucceeded = $false

function Invoke-Step($Name, [scriptblock]$Block) {
    Add-Content -Path $Log -Value "=== $Name ==="
    Write-Output "STEP $Name"

    & $Block
}

function Invoke-NativeCommand($FilePath, [string[]]$Arguments) {
    # Verbose native tools can write progress to stderr even when they exit 0.
    Get-Command $FilePath -ErrorAction Stop | Out-Null

    $PreviousErrorActionPreference = $ErrorActionPreference
    $NativeCommandPreferenceExists = Test-Path Variable:\PSNativeCommandUseErrorActionPreference
    if ($NativeCommandPreferenceExists) {
        $PreviousNativeCommandUseErrorActionPreference = $PSNativeCommandUseErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $false
    }

    try {
        $ErrorActionPreference = "Continue"
        & $FilePath @Arguments *>> $Log
        $NativeExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
        if ($NativeCommandPreferenceExists) {
            $PSNativeCommandUseErrorActionPreference = $PreviousNativeCommandUseErrorActionPreference
        }
    }

    if ($NativeExitCode -ne 0) {
        throw "Native command failed: $FilePath $($Arguments -join ' ') (exit $NativeExitCode). See $Log"
    }
}

function Remove-TempRootSafely($Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $resolvedTarget = (Resolve-Path -LiteralPath $Path).Path
    $resolvedBase = (Resolve-Path -LiteralPath $TempBase).Path
    if (-not $resolvedTarget.StartsWith($resolvedBase, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove non-temp path: $resolvedTarget"
    }

    Remove-Item -LiteralPath $resolvedTarget -Recurse -Force -ErrorAction SilentlyContinue
}

function Test-RequiredPackagedPath($PackageRoot, $RelativePath) {
    $path = Join-Path $PackageRoot $RelativePath
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing packaged path: $RelativePath"
    }
}

function Test-ForbiddenPackagedPath($PackageRoot, $RelativePath) {
    $path = Join-Path $PackageRoot $RelativePath
    if (Test-Path -LiteralPath $path) {
        throw "Installer-only asset was bundled unexpectedly: $RelativePath"
    }
}

New-Item -ItemType Directory -Path $TempRoot | Out-Null

try {
    Set-Content -Path $Log -Value "package smoke started $(Get-Date -Format o)"

    Invoke-Step "python-version-host" {
        Invoke-NativeCommand "python" @((Join-Path $Root "tools\check_python_version.py"))
    }

    Invoke-Step "venv" {
        Invoke-NativeCommand "python" @("-m", "venv", (Join-Path $TempRoot ".venv"))
    }

    $Python = Join-Path $TempRoot ".venv\Scripts\python.exe"

    Invoke-Step "python-version-venv" {
        Invoke-NativeCommand $Python @((Join-Path $Root "tools\check_python_version.py"))
    }

    Invoke-Step "pip-upgrade" {
        Invoke-NativeCommand $Python @("-m", "pip", "install", "--upgrade", "pip")
    }

    Invoke-Step "pip-install-lock" {
        Invoke-NativeCommand $Python @("-m", "pip", "install", "-r", (Join-Path $Root "requirements-lock.txt"))
    }

    Push-Location $Root
    try {
        Invoke-Step "unittest" {
            Invoke-NativeCommand $Python @("-m", "unittest", "discover", "-v")
        }

        Invoke-Step "compileall" {
            Invoke-NativeCommand $Python @("-m", "compileall", "-q", "main.py", "src", "tests", "tools")
        }

        Invoke-Step "cross-cwd-imports" {
            $previousPythonPath = $env:PYTHONPATH
            $env:PYTHONPATH = $Root
            Push-Location $TempBase
            try {
                Invoke-NativeCommand $Python @("-c", "import main; import src.managers.file_manager; import src.managers.player_manager; import src.controllers.file_action_controller; import src.ui.ui_components; print('package smoke cross-cwd import ok')")
            } finally {
                Pop-Location
                $env:PYTHONPATH = $previousPythonPath
            }
        }

        Invoke-Step "pyinstaller-isolated" {
            Invoke-NativeCommand $Python @("-m", "PyInstaller", "--noconfirm", "--clean", "--workpath", (Join-Path $TempRoot "pyi-build"), "--distpath", (Join-Path $TempRoot "dist"), "YDManager.spec")
        }
    } finally {
        Pop-Location
    }

    $ExePath = Join-Path $TempRoot "dist\YDManager\YDManager.exe"
    if (-not (Test-Path -LiteralPath $ExePath)) {
        throw "Missing packaged executable: $ExePath"
    }

    $PackageRoot = Join-Path $TempRoot "dist\YDManager"
    Invoke-Step "packaged-assets" {
        $requiredPaths = @(
            "YDManager.exe",
            "_internal\assets\icon.ico",
            "_internal\assets\fonts\Pretendard-Medium.ttf",
            "_internal\assets\fonts\Pretendard-Bold.ttf",
            "_internal\assets\fonts\LICENSE_Pretendard.txt",
            "_internal\qtawesome",
            "_internal\PyQt6\Qt6\plugins\platforms",
            "_internal\PyQt6\Qt6\plugins\multimedia"
        )

        foreach ($relativePath in $requiredPaths) {
            Test-RequiredPackagedPath $PackageRoot $relativePath
        }

        $forbiddenPaths = @(
            "_internal\assets\installer_sidebar.bmp",
            "_internal\assets\installer_header.bmp"
        )

        foreach ($relativePath in $forbiddenPaths) {
            Test-ForbiddenPackagedPath $PackageRoot $relativePath
        }
    }

    Add-Content -Path $Log -Value "=== packaged-startup ==="
    Write-Output "STEP packaged-startup"
    $Process = Start-Process -FilePath $ExePath -WorkingDirectory $TempBase -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 4
    if ($Process.HasExited) {
        throw "Packaged app exited during startup smoke with code $($Process.ExitCode)"
    }
    Stop-Process -Id $Process.Id -Force
    $Process.WaitForExit()

    Add-Content -Path $Log -Value "package smoke completed $(Get-Date -Format o)"
    $PackageSmokeSucceeded = $true
    Write-Output "PACKAGE_SMOKE_OK log=$Log"
} catch {
    Write-Output "PACKAGE_SMOKE_FAILED log=$Log temp=$TempRoot"
    Write-Output $_.Exception.Message
    if (Test-Path -LiteralPath $Log) {
        Get-Content -Path $Log -Tail 160
    }
    exit 1
} finally {
    if ($PackageSmokeSucceeded) {
        Remove-TempRootSafely $TempRoot
    } else {
        Write-Output "Preserving failed package smoke temp output: $TempRoot"
    }
}
