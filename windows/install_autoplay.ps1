# Install the reviewed Python player over the existing Windows ROM Testing Host.
# Never modifies the user's ROM library, native runner binary or checkpoints.
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{40}$')][string]$Commit,
    [ValidatePattern('^[A-Za-z0-9-]+/[A-Za-z0-9_.-]+$')][string]$Queue = 'xbaconator9000x/ROM-TESTING-QUEUE',
    [ValidatePattern('^[A-Za-z0-9-]{1,39}$')][string]$Author = 'xbaconator9000x'
)
$ErrorActionPreference = 'Stop'
$root = (Get-Location).Path
if (!(Test-Path '.\build\live_runner.exe') -or !(Test-Path '.\windows\host.py')) {
    throw 'Open PowerShell inside the existing testing harness folder first.'
}
$py = (Get-Command py.exe -ErrorAction Stop).Source
$ollama = (Get-Command ollama.exe -ErrorAction Stop).Source
$files = @(
    'core/live.py','core/playthrough.py','core/gameplay.py','core/guidance.py','core/rom_catalog.py','core/firered.py','core/jj_fast.py','core/jj_battle.py','core/jj_explore.py','core/jj_menus.py','core/jj_runtime.py','core/jj_connections.py','core/jj_unattended.py','core/autoplay.py',
    'vendor/pokemon_agent/pathfinding.py','vendor/pokemon_agent/LICENSE','vendor/pokemon_agent/README.md',
    'windows/host.py','windows/local_state.py','windows/queue_host.py','windows/autoplay.py','windows/dashboard.py',
    'tests/test_autoplay.py','tests/test_gameplay.py','tests/test_redundancy.py','tests/test_dashboard.py','tests/test_rom_catalog.py','tests/test_jj_fast.py','tests/test_jj_battle.py','tests/test_jj_explore.py','tests/test_jj_menus.py','tests/test_jj_runtime.py','tests/test_jj_connections.py','tests/test_jj_unattended.py',
    'docs/CONTINUOUS_AUTOPLAY.md','docs/POKEMON_GAMEPLAY_AGENT.md','docs/CONSOLIDATED_PLAYER.md','docs/JJ_FAST_GAMEPLAY.md','docs/JJ_NATIVE_BATTLE.md','docs/JJ_EXPLORATION.md','docs/JJ_MENU_DRIVER.md','docs/JJ_RUNTIME_METRICS.md','docs/JJ_CONNECTIONS.md'
)
$base = "https://raw.githubusercontent.com/xbaconator9000x/EXPERIMENTAL-ROM-TESTING-ENVIRONMENT/$Commit"
$stage = Join-Path $env:TEMP ("rom-player-" + [Guid]::NewGuid().ToString('N'))
$backup = Join-Path $stage 'backup'
$incoming = Join-Path $stage 'incoming'
$installed = @()
# The user must stop the old player; the local checkpoint stays in LOCALAPPDATA.
$lockPath = & $py -3.12 -c "import hashlib,os; from pathlib import Path; print(Path(os.environ['LOCALAPPDATA'])/'ROMTestingHost'/'autoplay'/hashlib.sha256('$($Queue.ToLower())'.encode()).hexdigest()/'controller.lock')"
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is not available.' }
if (Test-Path $lockPath) {
    try {
        $lockCheck = [IO.File]::Open($lockPath,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
        $lockCheck.Dispose()
    } catch { throw 'Stop the existing AI player with Ctrl+C before installing.' }
}
Write-Host 'Downloading the pinned player upgrade...' -ForegroundColor Cyan
try {
    foreach ($file in $files) {
        $dest = Join-Path $incoming $file
        New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
        Invoke-WebRequest -UseBasicParsing -Uri "$base/$file" -OutFile $dest
    }
    foreach ($file in $files) {
        $dest = Join-Path $root $file
        if (Test-Path $dest) {
            $old = Join-Path $backup $file
            New-Item -ItemType Directory -Force (Split-Path $old) | Out-Null
            Copy-Item $dest $old
        }
        New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
        $installed += $file
        Copy-Item (Join-Path $incoming $file) $dest -Force
    }
    foreach ($pattern in @('test_autoplay.py','test_gameplay.py','test_redundancy.py','test_dashboard.py','test_rom_catalog.py','test_jj_fast.py','test_jj_battle.py','test_jj_explore.py','test_jj_menus.py','test_jj_runtime.py','test_jj_connections.py','test_jj_unattended.py')) {
        & $py -3.12 -m unittest discover -s tests -p $pattern
        if ($LASTEXITCODE -ne 0) { throw "Local regression failed: $pattern" }
    }
} catch {
    foreach ($file in $installed) {
        $dest = Join-Path $root $file
        $old = Join-Path $backup $file
        if (Test-Path $old) { Copy-Item $old $dest -Force }
        elseif (Test-Path $dest) { Remove-Item $dest -Force }
    }
    throw
} finally {
    if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
}
Write-Host 'Installing the lighter backup vision model (one-time download)...' -ForegroundColor Cyan
& $ollama pull qwen3-vl:2b-instruct
if ($LASTEXITCODE -ne 0) { throw 'Backup model download failed. Run this installer again when connected.' }
Write-Host 'Player installed. The original gameplay checkpoint is retained.' -ForegroundColor Green
Start-Process -FilePath $py -ArgumentList '-3.12','-m','windows.dashboard','--queue',$Queue -WorkingDirectory $root
& $py -3.12 -m windows.autoplay --queue $Queue --author $Author --model qwen3-vl:4b-instruct --fallback qwen3-vl:2b-instruct
