[CmdletBinding()]
param(
    [string]$OutputDirectory = [Environment]::GetFolderPath("Desktop")
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$version = (Get-Content -LiteralPath (Join-Path $projectRoot "VERSION") -Raw).Trim()
if ($version -notmatch '^\d+\.\d+\.\d+$') {
    throw "VERSION must be semantic X.Y.Z; got '$version'."
}

$sourceDirectory = Join-Path $projectRoot "Stopwatch"
if (-not (Test-Path -LiteralPath (Join-Path $sourceDirectory "Stopwatch.exe"))) {
    throw "Release build is missing: $sourceDirectory\Stopwatch.exe"
}

$compilerCandidates = @(
    "D:\dev\tools\Inno Setup 6\ISCC.exe",
    (Join-Path ${env:LOCALAPPDATA} "Programs\Inno Setup 6\ISCC.exe"),
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$compiler = $compilerCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $compiler) {
    throw "Inno Setup 6 (ISCC.exe) was not found. Install it before creating the installer."
}

if (-not (Test-Path -LiteralPath $OutputDirectory)) {
    throw "Installer output directory does not exist: $OutputDirectory"
}

$scriptPath = Join-Path $PSScriptRoot "Stopwatch.iss"
& $compiler "/DMyAppVersion=$version" "/DOutputDir=$OutputDirectory" $scriptPath
if ($LASTEXITCODE -ne 0) {
    throw "ISCC.exe failed with exit code $LASTEXITCODE."
}

$installer = Join-Path $OutputDirectory "Stopwatch_v${version}_Setup.exe"
if (-not (Test-Path -LiteralPath $installer)) {
    throw "ISCC.exe completed but the expected installer is missing: $installer"
}

Get-Item -LiteralPath $installer
