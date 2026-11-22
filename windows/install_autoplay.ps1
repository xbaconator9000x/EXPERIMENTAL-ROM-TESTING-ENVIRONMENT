# Install the reviewed Python player over the existing Windows ROM Testing Host.
# Never modifies the user's ROM library, native runner binary or checkpoints.
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{40}$')][string]$Commit,
    [ValidatePattern('^[A-Za-z0-9-]+/[A-Za-z0-9_.-]+$')][string]$Queue = 'xbaconator9000x/ROM-TESTING-QUEUE',
    [ValidatePattern('^[A-Za-z0-9-]{1,39}$')][string]$Author = 'xbaconator9000x',
    [switch]$EnableUpstreamLeafGreen
)
$ErrorActionPreference = 'Stop'
$root = (Get-Location).Path
if (!(Test-Path '.\build\live_runner.exe') -or !(Test-Path '.\windows\host.py')) {
    throw 'Open PowerShell inside the existing testing harness folder first.'
}
$py = (Get-Command py.exe -ErrorAction Stop).Source
$ollama = (Get-Command ollama.exe -ErrorAction Stop).Source
$files = @(
    'core/live.py','core/live_preview.py','core/playthrough.py','core/gameplay.py','core/guidance.py','core/rom_catalog.py','core/firered.py','core/jj_fast.py','core/jj_battle.py','core/jj_compat.py','core/jj_script_probe.py','core/jj_explore.py','core/jj_world_model.py','core/jj_tile_memory.py','core/jj_eval.py','core/jj_menus.py','core/jj_runtime.py','core/jj_connections.py','core/jj_unattended.py','core/autoplay.py','core/action_batch.py','core/navigation_memory.py','core/party_knowledge.py','core/upstream_battle.py','core/gen3_profiles.py','core/native_acceptance.py',
    'core/upstream_leafgreen/__init__.py','core/upstream_leafgreen/LICENSE','core/upstream_leafgreen/type_chart.py','core/upstream_leafgreen/move_kinds.py','core/upstream_leafgreen/move_effects.py',
    'core/upstream_leafgreen/constants.py','core/upstream_leafgreen/state.py','core/upstream_leafgreen/memory_reader.py','core/upstream_leafgreen/tilemap_reader.py','core/upstream_leafgreen/pathfinding.py','core/upstream_leafgreen/growth.py','core/upstream_leafgreen/growth_data.py',
    'core/upstream_port.py','core/upstream_probe.py','core/upstream_skills.py','core/upstream_campaign.py','core/upstream_shop.py','core/operator_control.py','core/operator_model.py',
    'vendor/pokemon_agent/pathfinding.py','vendor/pokemon_agent/LICENSE','vendor/pokemon_agent/README.md',
    'windows/host.py','windows/local_state.py','windows/queue_host.py','windows/autoplay.py','windows/dashboard.py','windows/operator_queue.py',
    'tests/test_autoplay.py','tests/test_live_preview.py','tests/test_action_batch.py','tests/test_navigation_memory.py','tests/test_navigation_integration.py','tests/test_party_knowledge.py','tests/test_gameplay.py','tests/test_redundancy.py','tests/test_dashboard.py','tests/test_rom_catalog.py','tests/test_jj_fast.py','tests/test_jj_v1033.py','tests/test_jj_battle.py','tests/test_jj_compat.py','tests/test_jj_script_probe.py','tests/test_jj_explore.py','tests/test_jj_world_model.py','tests/test_jj_tile_memory.py','tests/test_jj_eval.py','tests/test_jj_menus.py','tests/test_jj_runtime.py','tests/test_jj_connections.py','tests/test_jj_unattended.py','tests/test_upstream_battle.py','tests/test_upstream_port.py','tests/test_upstream_skills.py','tests/test_upstream_campaign_retry.py','tests/test_upstream_idle_frame_accounting.py','tests/test_upstream_checkpoint_abort.py','tests/test_upstream_queue.py','tests/test_upstream_shop.py','tests/test_gen3_profiles.py','tests/test_native_acceptance.py','tests/test_operator_control.py','tests/test_operator_model.py','tests/test_operator_queue.py',
    'docs/CONTINUOUS_AUTOPLAY.md','docs/POKEMON_GAMEPLAY_AGENT.md','docs/CONSOLIDATED_PLAYER.md','docs/JJ_FAST_GAMEPLAY.md','docs/JJ_NATIVE_BATTLE.md','docs/JJ_EXPLORATION.md','docs/JJ_MENU_DRIVER.md','docs/JJ_RUNTIME_METRICS.md','docs/JJ_CONNECTIONS.md','docs/JJ_UNATTENDED.md','docs/UPSTREAM_PORTS.md','docs/UPSTREAM_SKILL_EXECUTION.md','docs/UPSTREAM_QUEUE_AND_JJ.md','docs/GEN3_COMPATIBILITY.md','docs/NATIVE_ACCEPTANCE.md','docs/REMOTE_OPERATOR_CONTROL.md','docs/ADAPTIVE_BATCHING.md','docs/PARTY_BATTLE_KNOWLEDGE.md','docs/JJ_WORLD_SKILL_INTEGRATION.md','docs/JJ_AGENT_REUSE_FINDINGS.md','docs/JJ_EVALUATION.md'
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
    if ($EnableUpstreamLeafGreen) {
        $git = (Get-Command git.exe -ErrorAction Stop).Source
        $pin = '594bfc7e3c208890c248269b67c5a1cf95074965'
        $upstreamPath = Join-Path $env:LOCALAPPDATA "ROMTestingHost\upstream-$pin"
        if (!(Test-Path $upstreamPath)) {
            New-Item -ItemType Directory -Force (Split-Path $upstreamPath) | Out-Null
            $clone = "$upstreamPath.incoming"
            if (Test-Path $clone) { throw "Remove the failed staging checkout before retrying: $clone" }
            & $git clone --no-checkout https://github.com/haggyroth/pokemon-agent.git $clone
            if ($LASTEXITCODE -ne 0) { throw 'Upstream checkout failed.' }
            & $git -C $clone checkout --detach $pin
            if ($LASTEXITCODE -ne 0) { throw 'Pinned upstream checkout failed.' }
            Move-Item $clone $upstreamPath
        }
        $actual = & $git -C $upstreamPath rev-parse HEAD
        $dirty = & $git -C $upstreamPath status --porcelain --untracked-files=no
        if ($actual -ne $pin -or $dirty) { throw 'Upstream checkout is not clean and pinned.' }
        & $py -3.12 -m pip install requests openai rich python-dotenv
        if ($LASTEXITCODE -ne 0) { throw 'Upstream Python dependencies failed.' }
    }
    # Download before changing any installed player files.
    & $ollama pull qwen3-vl:2b-instruct
    if ($LASTEXITCODE -ne 0) { throw 'Backup model download failed; existing player preserved.' }
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
    foreach ($pattern in @('test_autoplay.py','test_live_preview.py','test_action_batch.py','test_navigation_memory.py','test_navigation_integration.py','test_party_knowledge.py','test_gameplay.py','test_redundancy.py','test_dashboard.py','test_rom_catalog.py','test_jj_fast.py','test_jj_v1033.py','test_jj_battle.py','test_jj_compat.py','test_jj_script_probe.py','test_jj_explore.py','test_jj_world_model.py','test_jj_tile_memory.py','test_jj_eval.py','test_jj_menus.py','test_jj_runtime.py','test_jj_connections.py','test_jj_unattended.py','test_upstream_battle.py','test_upstream_port.py','test_upstream_skills.py','test_upstream_campaign_retry.py','test_upstream_idle_frame_accounting.py','test_upstream_checkpoint_abort.py','test_upstream_queue.py','test_upstream_shop.py','test_gen3_profiles.py','test_native_acceptance.py','test_operator_control.py','test_operator_model.py','test_operator_queue.py')) {
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
Write-Host 'Player installed. The original gameplay checkpoint is retained.' -ForegroundColor Green
Start-Process -FilePath $py -ArgumentList '-3.12','-m','windows.dashboard','--queue',$Queue -WorkingDirectory $root
$playerArgs = @('-3.12','-m','windows.autoplay','--queue',$Queue,'--author',$Author,'--model','qwen3-vl:4b-instruct','--fallback','qwen3-vl:2b-instruct')
if ($EnableUpstreamLeafGreen) { $playerArgs += @('--upstream-checkout',$upstreamPath) }
& $py @playerArgs