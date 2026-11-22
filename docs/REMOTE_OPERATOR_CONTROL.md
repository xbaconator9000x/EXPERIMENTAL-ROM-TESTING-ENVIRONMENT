# Private operator controls for unattended native mGBA
This is the advanced controller, not the original vision-only installer.

Start the upgraded Windows player from the normal installer. It prompts for
the existing private GitHub issue token and launches an outbound-only polling
thread for the active play issue. No inbound port, GitHub-hosted ROM, save upload
or public emulator API is needed. The PC MUST remain on, awake and connected.
Your host must be upgraded to the commit containing this protocol: the old
player cannot receive operator commands.

## Where to send a command
Open your private issue `xbaconator9000x/ROM-TESTING-QUEUE#19` (Jessie &
James) or the private [ROM-PLAY upstream v2] goal for vanilla LeafGreen.
Post a new comment starting with the exact line `ROM-CONTROL v1` followed
by exactly one JSON command. For the Jessie & James queue ROM use:
```
ROM-CONTROL v1
{"version":1,"rom_sha256":"06d9c87234400f45f1fc3a356881f0ad8bd9b977bc5cbed450e5c7eedd01b632","action":"pause","args":{}}
```
Other supported actions:
- `resume`, `status` with `args:{}`
- `snapshot` with `args:{"name":"before-boss"}` creates an immutable local checkpoint
- `restore` with `args:{"name":"before-boss"}` loads it, retaining a local pre-restore checkpoint
- `input` with `args:{"actions":[{"button":"UP","frames":16},{"button":"A","frames":5}]}`
- `soft_reset` with `args:{}` presses GBA A+B+START+SELECT
- `hard_reset` with `args:{}` creates a fresh emulator boot, without
  transferring the previous process's Flash file. The last native checkpoint
  remains available for restore. This is not Flash cold-boot acceptance.
- `test` with `args:{"issue":<N>}` dispatches a separately authorized
  existing private `[ROM-TEST v1]` scenario for the identical ROM through
  the independent native state_runner.exe. It does not overwrite gameplay state.

Optional `"expected_screen":"<64 lowercase hex>"` requires the LCD hash to
match at execution. All commands require the exact selected ROM SHA-256.
Names cannot contain paths. Inputs are real GBA buttons (A, B, SELECT, START,
UP, DOWN, LEFT, RIGHT, L, R, WAIT) with at most 16 steps, 120 frames per
step, and 960 key-down frames total. The private queue owner must author
the comment and GitHub's author_association must be OWNER/MEMBER/COLLABORATOR.
A different author, wrong ROM or malformed JSON is rejected.

The host replies `ROM-CONTROL-ACK v1` with ACCEPTED then EXECUTED or
FAILED, a screen SHA and decision count (no state bytes). Once a command's
GitHub comment id is consumed it is durably marked and never replayed after
restart. New installations ignore commands already present at first sync.
Command history lives in local `operator-audit.jsonl`, status in
`operator-status.json`, and immutable native states in
`operator-states/<name>.bin`. The dashboard displays pause/recovery state.

On a model validation failure or repeated playthrough cycle, the emulator
enters a WAITING-for-operator hold instead of exiting. The remote thread keeps
polling even while the local model is thinking; an override invalidates its
old-screenshot proposal. An interrupted upstream skill stops after its next
bounded native step. Never interpret tests based on a synthetic ROM or CI as
real Jessie & James gameplay acceptance. Real native milestones are tracked
separately under docs/NATIVE_ACCEPTANCE.md.

## Constraints and recovery
A remote command cannot revive a dead Windows process, a sleeping PC,
disconnected internet, expired GitHub credentials or unavailable Ollama.
Native emulator errors that prevent it from restoring a valid checkpoint
still need a local host restart. On Windows launch, Ctrl+C cleanly stops the
player. Pause/resume only control the live emulator, not the independent
test runner. Do not expose this token or post ROM, save, or native checkpoint
bytes in GitHub comments.

## Diagnosing a parked previous-generation session
After installation, the PowerShell player must report
`Operator control READY on private playthrough issue #19` and the
private play issue must contain `ROM-CONTROL-READY v1`.
`Continuous player polling private queue` alone only confirms that the
outer queue loop launched: it does not establish that the ROM checkpoint
was admitted. An existing `NEEDS_REVIEW` terminal is now admitted into
operator hold without requiring a single-use upgrade marker or any old
`ROM-GUIDE v1` comment. This does not automatically press buttons: a
private `resume` or bounded `input` command must release the hold.
If checkpoint identity validation fails, PowerShell prints
`checkpoint not admitted` and retains every checkpoint unchanged.
If operator comments cannot be fetched, PowerShell prints
`Operator polling retry` with the exception class (not secrets).
Large screenshot-heavy issues are paginated at 20 comments per page to
stay below the GitHub response limit. Never clear the local controller
folder or delete the saved state to resolve a readiness failure.

## Automated recovery before NEEDS_REVIEW

The exact-release Jessie & James gameplay controller tries a bounded,
checkpointed recovery ladder before requesting operator intervention when
native scripted dialogue, navigation, or repeated-screen handling stalls:

1. A up to 10 times at 10-second wall-clock intervals.
2. B up to 10 times at the same interval.
3. UP, DOWN, LEFT, RIGHT, up to 3 times each at the same interval.
4. Up to two local Qwen consultations, each capped at one short GBA input.
5. NEEDS_REVIEW if every eligible attempt fails.

The first input is immediate; subsequent inputs are spaced by 10 actual
seconds. No inference runs during the deterministic button ladder. An
observed dialogue-page or substantial non-animated screen change interrupts
the ladder and returns to normal native control; this is a *candidate scene
transition*, not game-completion acceptance. A choice panel, battle or menu
blocks blind confirmation and routes to the visual fallback. Human
pause/input/restore commands interrupt the ladder. Before applying anything,
the host saves an immutable, exact-identity local generation, and each native
input checkpoints locally. No public ROM/save artifacts are created.

The dashboard displays `AUTOMATIC RECOVERY` with the current stage. A
completed exhausted ladder is recorded in local checkpoint metadata, and
the identical stalled screenshot will not restart the full sequence after
host restart. A previously parked `native_script_locked` checkpoint may
automatically enter the ladder after installing the revised player.
