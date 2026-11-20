$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $python) { throw "Install Python 3.11+ for Windows from https://www.python.org/downloads/windows/ (include Tkinter)." }
if (-not (Test-Path (Join-Path $root "build\state_runner.exe"))) {
    & (Join-Path $PSScriptRoot "build.ps1")
}
Push-Location $root
try {
    if ($python.Name -eq "py.exe" -or $python.Name -eq "py") { & $python.Source -3 windows/host.py }
    else { & $python.Source windows/host.py }
} finally { Pop-Location }
