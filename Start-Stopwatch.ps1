[CmdletBinding()]
param()

$projectRoot = Split-Path -Parent $PSCommandPath
$pythonw = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"
$entryPoint = Join-Path $projectRoot "Stopwatch.pyw"

if (-not (Test-Path -LiteralPath $pythonw)) {
    throw "Не найден интерпретатор проекта: $pythonw"
}

if (-not (Test-Path -LiteralPath $entryPoint)) {
    throw "Не найден файл приложения: $entryPoint"
}

Start-Process -FilePath $pythonw -ArgumentList $entryPoint -WorkingDirectory $projectRoot
