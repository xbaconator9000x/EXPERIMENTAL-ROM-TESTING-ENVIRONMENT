# Jessie & James isolated gameplay evaluations

Goal-scoped deterministic evaluation of the **existing** native Windows
mGBA/Qwen player. Inspired by the *evaluation idea* in
[NuzlockeSolver](https://github.com/Fracture17/NuzlockeSolver) (MIT),
with an independent, source-only implementation. No Emerald simulation,
new emulator, hosted API or copyrighted game files are included.

**Scope:** This is **not** proof of Jessie & James story completion. Real
gameplay acceptance requires playing the user-owned v1.03.3 ROM on the
Windows computer and collecting new native witnesses.

## Five scenarios

| Scenario | Exact acceptance criterion |
| --- | --- |
| `leave_current_map` | At least one NEW independently witnessed native map-crossing event after the copied checkpoint |
| `navigation_progress` | At least three NEW independent, one-tile native steps recorded by the actual controller |
| `win_battle` | At least one NEW battle-win event from a native battle outcome |
| `catch_pokemon` | At least one NEW wild capture confirmed by native outcome **and** party size/species growth |
| `checkpoint_resume` | A verified cold reload of the copied state **and** at least one subsequent native step |

`leave_current_map` deliberately does **not** claim it left a
specific hospital: no hospital map ID is invented. Start the episode
from the verified hospital checkpoint to interpret it as a hospital
escape test. Unknown exact-ROM memory fields will cause a FAIL rather
than a simulated pass.

## Running a private episode on Windows

Stop the regular AI player before starting a new evaluation to avoid
simultaneous emulator/Ollama load. Leave GPU-enabled Ollama running.
Keep the same user-owned ROM and runner files. In PowerShell, open the
existing harness directory, then run:

```powershell
py -3.12 -m core.jj_eval list

$checkpoint = "C:\path\to\your\existing\progress.bin"
$rom = "C:\path\to\your\private\JessieJames_v1.03.3.gba"
$results = Join-Path (Get-Location) "private-evaluations"

py -3.12 -m core.jj_eval run `
  --scenario leave_current_map `
  --checkpoint $checkpoint `
  --output-root $results `
  --runner ".\build\live_runner.exe" `
  --rom $rom `
  --rom-sha "bb4fd81b32f5e2a69254fc18fbc47e7c7bcbfb35baeace45be2b5dda7876803b" `
  --budget 40
```

The checkpoint's existing **goal and model ID** are read from its bounded
header and verified by the regular state checksums. If overrides are supplied,
they must agree exactly. The ROM hash must match **before** opening an
emulator. A different game, runner, model, goal, symlinked checkpoint, output
directory overlapping the live checkpoint, or invalid state is rejected.

Each run creates a *fresh* `jj-eval-<scenario>-...` directory:
- `progress.bin`: an independently written checkpoint COPY for that episode
- `actions.jsonl`: private native/controller action trace
- `evaluation.json`: pass/fail, reason, evidence counts, stuck ratio,
  novel maps, capped progress score, frames, native actions and Qwen calls
- any private screenshots or dialogue evidence created by the original player

All outputs remain **local**. They are never placed in the public repository
or automatically uploaded to the GitHub gameplay queue. No source checkpoint
is overwritten or renamed. A run may stop early after evidence of its goal,
but only at a regular reported checkpoint boundary.

To score two previously saved checkpoints **without** launching mGBA or Qwen:

```powershell
py -3.12 -m core.jj_eval score `
  --scenario leave_current_map `
  --before $checkpoint `
  --after "C:\path\to\private-evaluations\jj-eval-...\progress.bin" `
  --runner ".\build\live_runner.exe" `
  --rom-sha "bb4fd81b32f5e2a69254fc18fbc47e7c7bcbfb35baeace45be2b5dda7876803b"
```

## What counts as evidence

Only *new* events after the checkpoint's recorded decision number,
from the exact current `Acceptance` engine hash and the exact
ROM/runner identity, can satisfy the goal. Event kinds, decision numbers,
SHA-256 witnesses and structured map/capture details must validate.

The report deliberately ignores apparent progress from model narrative,
screenshots, raw decision totals and unverified acceptance counters.

Stuck ratio counts repeated native map/coordinates following directional
actions (where both states are known). When only the bounded checkpoint
history is available, the report sets `audit_limited=true`. When native
coordinates are unavailable it reports a null stuck ratio, **not zero**.
The score favours new maps and witnessed milestones, with caps to reduce
reward farming by traversing old routes repeatedly.

CI tests use synthetic state bytes and fake controllers. They verify
provenance, scratch isolation, new events, capture logic, scoring and no
writes to the source checkpoint. Real physical game acceptance is still
marked pending until the user-owned host runs the episodes.
