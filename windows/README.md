# Native Windows testing host

**Status:** Desktop host plus optional outbound-only private GitHub issue queue (beta).

Works on Windows 10/11 x64 with the standard Python 3.11+ Tkinter GUI and
native libmGBA from MSYS2 UCRT64. **No WSL, Ubuntu, Docker, GitHub token,
administrator service or permanently open network port is required.**

## Install

1. Install Python 3.11+ for Windows (make sure Tkinter is included).
2. Install [MSYS2](https://www.msys2.org/) using its default `C:\msys64` path.
3. Open **MSYS2 UCRT64** from the Start menu and update it:

   ```sh
   pacman -Syu
   ```

   Restart the UCRT64 shell if requested, rerun `pacman -Syu`, then install:

   ```sh
   pacman -S --needed mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-mgba
   ```

4. Download/clone the repository. Open PowerShell in the repository folder:

   ```powershell
   .\windows\build.ps1
   .\windows\start.ps1
   ```

   If Windows script execution policy blocks a downloaded script, use a
   process-scoped bypass for the reviewed script only:

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\windows\start.ps1
   ```

## Using the host

- Import your own `.gba` from disk. The host streams SHA-256 and copies the
  game into `%LOCALAPPDATA%\ROMTestingHost\roms`, indexed by digest.
- Choose a **trusted local** test scenario (`tests/scenarios/input-pass.txt`
  is for our original synthetic test cartridge, NOT a retail Pokémon ROM).
- Click **Run selected test**. The emulator runs locally, without changing
  game RAM or sending the ROM to GitHub. Verify status and open local results.
- Every test writes its log and screenshot evidence only to
  `%LOCALAPPDATA%\ROMTestingHost\runs`. Stop is available in the UI.

Real-game scripts must use verified, revision-specific addresses and an
assertion; choosing a scenario for the wrong ROM is unsafe and should fail,
not be interpreted as acceptance. This application is a local control panel
for the native engine, not yet a fully automatic game-playtesting agent.
The first desktop version does not install a tray icon, startup task,
headless daemon, remotely authorized queue or a live video monitor.

## Private remote queue (optional)

Create a separate private GitHub repository with Issues enabled. Never register a persistent self-hosted Actions runner against a public development repository. The queue is a restricted data protocol, not an Actions runner.

1. Create a fine-grained personal access token for **only** the private queue repository, with Issues read/write and Metadata read (automatic). Use a short expiry.
2. After importing ROMs in the desktop host, launch the queue from the repository folder:
   ```powershell
   py -3 windows/queue_host.py
   ```
3. Enter the private repository owner/name, exact allowed issue author login, and token. Do not share the token in chat, commits, issue bodies or screenshots. The token stays in process memory and must be entered again after restart.
4. Click Start polling. Leave the window open while your PC is available. Stop cancels the active test; no inbound port is opened.

Create an issue titled exactly `[ROM-TEST v1]` with raw JSON (no Markdown fences), for example:

```json
{"version":1,"sha256":"replace_with_exact_64_character_rom_sha256","scenario":["idle 120","assert 32 0x02000000 1 1","capture"]}
```

The example is for the synthetic fixture only; use validated revision-specific assertions for real games. Only previously imported, exact SHA-256 ROMs are eligible. The queue accepts up to 500 bounded press/idle/assert/wait/capture instructions, 200,000 frames, 20 captures and 10 minutes per job. It rejects arbitrary commands, code, host paths, URLs, unknown users and public repositories. The ROM is copied into a disposable local folder, without existing saves. By default GitHub receives only a categorical result. Check the local **Share game screenshots and bounded diagnostics** box and confirm to additionally send exact 240×160 PNG framebuffer captures and filtered native diagnostics as bounded base64 JSON issue comments (ROM-EVIDENCE v1). No token permission change is needed. The host rechecks private repository identity before each upload, never sends ROMs/saves/arbitrary files, and resumes interrupted evidence transfers via its local ledger. Keep the repository private; evidence remains in its issue comments until deleted. Old completed v1 jobs cannot be backfilled automatically because their run folders were not associated with issue IDs. A dropped HTTP response can produce a duplicate part; consumers deduplicate by name, hash and part number. A final ROM-EVIDENCE-COMPLETE v1 comment lists the total number of unique parts, file names and result status. Do not treat incomplete evidence as a verified gameplay result. A durable ledger prevents automatic reruns; submit a new issue for a deliberate retry. A crash after claiming a job yields HOST_ERROR on reconnect. One process per queue is enforced. Use trusted local ROMs and run as a normal user; this is not an OS-level sandbox.

Automatic startup, system tray, live video, existing save reuse and remotely dispatched autonomous game agents remain pending. The evidence transport supports subsequent adaptive decisions by an external controller, not unrestricted remote execution. Keep the queue private and allow only trusted repository collaborators.

## Windows CI

`.github/workflows/windows-host.yml` compiles both real C emulator runners
with MSYS2 UCRT64, exercises a self-authored synthetic cartridge (including
actual controller input and memory assertions), and runs Python host tests.
Passing this is **Windows compatibility evidence, not real-ROM gameplay
acceptance**.
