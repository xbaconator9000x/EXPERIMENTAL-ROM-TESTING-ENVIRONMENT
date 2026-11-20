# Native Windows x64 build; no WSL, Docker, or administrator privileges.
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$msys = if ($env:MSYS2_UCRT64_BIN) { $env:MSYS2_UCRT64_BIN } else { "C:\msys64\ucrt64\bin" }
$gcc = Join-Path $msys "gcc.exe"
if (-not (Test-Path $gcc)) {
    throw "MSYS2 UCRT64 GCC not installed. Install MSYS2 from https://www.msys2.org/ and in the 'MSYS2 UCRT64' terminal run: pacman -Syu ; then pacman -S --needed mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-mgba"
}
$header = Join-Path (Split-Path $msys -Parent) "include\mgba\core\core.h"
if (-not (Test-Path $header)) {
    throw "mGBA UCRT64 development package missing. Open MSYS2 UCRT64 terminal and run: pacman -S --needed mingw-w64-ucrt-x86_64-mgba"
}
$env:PATH = "$msys;$env:PATH"
New-Item -ItemType Directory -Force -Path (Join-Path $root "build") | Out-Null
Push-Location $root
try {
    & $gcc -std=gnu11 -O2 -Wall -Wextra core/state_runner.c -o build/state_runner.exe -lmgba
    if ($LASTEXITCODE -ne 0) { throw "Native state runner compile failed" }
    & $gcc -std=gnu11 -O2 -Wall -Wextra core/live_runner.c -o build/live_runner.exe -lmgba
    if ($LASTEXITCODE -ne 0) { throw "Native live runner compile failed" }
    Write-Host "Native Windows test runners built under build/" -ForegroundColor Green
} finally {
    Pop-Location
}
