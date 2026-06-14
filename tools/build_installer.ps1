$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$SetupScript = Join-Path $Root "setup.iss"

function Find-InnoCompiler {
    $fromPath = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($fromPath) {
        return $fromPath.Source
    }

    $candidates = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    return $null
}

function Get-InnoAppVersion($Path) {
    $content = Get-Content -LiteralPath $Path -Raw
    if ($content -notmatch '(?m)^#define\s+MyAppVersion\s+"([^"]+)"') {
        throw "Could not read MyAppVersion from setup.iss"
    }
    return $Matches[1]
}

function Test-RequiredPackagedPath($PackageRoot, $RelativePath) {
    $path = Join-Path $PackageRoot $RelativePath
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Missing packaged path: $RelativePath. Rebuild dist\YDManager before building the installer."
    }
}

function Test-ForbiddenPackagedPath($PackageRoot, $RelativePath) {
    $path = Join-Path $PackageRoot $RelativePath
    if (Test-Path -LiteralPath $path) {
        throw "Installer-only asset was bundled unexpectedly: $RelativePath. Rebuild dist\YDManager from the current YDManager.spec."
    }
}

function Test-PackagePreflight($PackageRoot) {
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

Push-Location $Root
try {
    if (-not (Test-Path -LiteralPath $SetupScript)) {
        throw "Missing setup script: $SetupScript"
    }

    $AppVersion = Get-InnoAppVersion $SetupScript
    $ExpectedInstaller = Join-Path $Root "installer\YDManager_Setup_v$AppVersion.exe"
    $ExpectedInstallerDisplay = "installer\YDManager_Setup_v$AppVersion.exe"
    $PackageRoot = Join-Path $Root "dist\YDManager"

    if (-not (Test-Path -LiteralPath (Join-Path $PackageRoot "YDManager.exe"))) {
        throw "Missing PyInstaller output. Run a local PyInstaller build that writes to .\dist before building the installer."
    }
    Test-PackagePreflight $PackageRoot

    $Compiler = Find-InnoCompiler
    if (-not $Compiler) {
        Write-Output "INNO_SETUP_NOT_FOUND: ISCC.exe was not found on PATH or the default Inno Setup 6 install paths."
        exit 2
    }

    & $Compiler $SetupScript
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    if (-not (Test-Path -LiteralPath $ExpectedInstaller)) {
        throw "Installer build finished but expected output was not found: $ExpectedInstallerDisplay"
    }

    Write-Output "INSTALLER_BUILD_OK path=$ExpectedInstallerDisplay"
} finally {
    Pop-Location
}
