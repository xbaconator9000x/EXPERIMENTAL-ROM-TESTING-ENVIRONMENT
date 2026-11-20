# Native Windows testing host

**Status:** First working desktop-host implementation. Not yet a remotely controlled GitHub queue.

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

## Remote operation later

A future remote queue should use a **dedicated private repository** and
a properly scoped Windows self-hosted GitHub Actions runner, with job data
validated and the ROM directory inaccessible to workflow upload steps.
**Never register this machine as a persistent runner for our public
development repositories.** Public pull requests and untrusted code must
not be able to execute arbitrary commands on your personal PC.

The GUI currently neither fetches GitHub tasks nor accepts remote commands.
A Windows PC must be turned on for local work, but **nothing is exposed to
the internet by this release**.

## Windows CI

`.github/workflows/windows-host.yml` compiles both real C emulator runners
with MSYS2 UCRT64, exercises a self-authored synthetic cartridge (including
actual controller input and memory assertions), and runs Python host tests.
Passing this is **Windows compatibility evidence, not real-ROM gameplay
acceptance**.
