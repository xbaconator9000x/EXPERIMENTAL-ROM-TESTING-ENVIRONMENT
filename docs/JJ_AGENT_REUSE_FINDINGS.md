# Reuse study: Pokémon agents relevant to Jessie & James native testing

Evidence reviewed 22 November 2026. These are upstream *architectural*
references, not alternative clients to install on the user's Windows host.
Private ROM, save-state, local input token and screenshots stay on that host.

## Actual upstream source examined

| Source | Relevant source / verified pattern | What we used |
| --- | --- | --- |
| [haggyroth/pokemon-agent](https://github.com/haggyroth/pokemon-agent) | README and its MIT license; deterministic LeafGreen skills with native observation | The existing MIT-licensed A* and compatible helper code remain the foundation. No second emulator. |
| [daniel4x/JevEmon](https://github.com/daniel4x/JevEmon) | `ARCHITECTURE.md` and `jevemon/journey.py`: only prevalidated reachable destinations, walk legs, interruption handling, repeat counts and warp retrigger | Replan a walking leg after a battle rather than blacklisting a still-relevant NPC or exit. New code is ours; JevEmon is GPL-3.0 and its implementation is not copied. |
| [nori00000/pokemon-agent-os](https://github.com/nori00000/pokemon-agent-os) | `src/agent-os/pathfinder.ts`, `src/agent-os/os-runner.ts`, `src/agent-os/game-state.ts`: empirical occupancy learning, recovery/failure classification and map-progress scoring | Native Gen III tile-probe memory with a stronger second attempt, then pathfinding around a corroborated obstruction. This is an independent design, not copied Gen I code. |
| [Fracture17/NuzlockeSolver](https://github.com/Fracture17/NuzlockeSolver) | README, MIT license; embedded mGBA + Emerald battle simulation, isolated episode evaluations, stuck-ratio and success goals | Future candidate: goal-scoped private QA scenarios and verified progress metrics. Do NOT transplant Emerald enemy logic into the Jessie & James ROM without a faithful Gen III data/effect audit. |

The exact `JevEmon` and `pokemon-agent-os` algorithms were **not copied**.
Upstream Gen I addresses, Gen III FireRed v1.1 assumptions and Emerald
trainer AI cannot automatically be considered correct for a patched ROM.

## Implemented in this branch

### Empirical native tile calibration

`core/jj_tile_memory.py` reads the existing *corroborated* native map,
position, callback and planned destination. When one very short directional
tap leaves the avatar on the same tile, it records **one provisional probe**,
not an impassable tile. The next attempt of that same step can use a bounded
12-frame hold; only two independently verified unchanged attempts temporarily
block the tile for A*. Arrival unblocks it again. A separately verified map
reentry also expires provisional obstacle assumptions because NPCs and script
flags may have changed since the previous visit.

The memory is bounded to 48 maps / 96 recent tile probes per map, stored
inside the same local identity-locked checkpoint. It refuses to learn from
unverified fields, a changed callback, script/fade interruptions, a map
transition, a diagonal movement, or a native tile already declared
impassable. `core/jj_explore.py` now tries a different reachable approach
to the *same event* after a learned obstruction rather than marking the
entire NPC or doorway as failed.

### Interrupted skills are replanned

When a battle begins during a native walking leg, the original
`Explorer` discards that path and retains the underlying event as eligible.
This prevents replaying a stale route across battle transitions and prevents
falsely concluding that the target NPC/exit was unreachable merely because
a wild encounter interrupted the approach. Bounded interruption metadata
is retained, without adding a new server or new battle controller.

### Source-only regression acceptance

- One-frame unsuccessful taps remain **provisional**.
- A second confirmed unchanged movement creates a temporary blocked tile.
- A subsequently successful arrival clears the blockage.
- Fade, battle, unverified snapshots and different map/callback never teach
  a collision.
- A* avoids a learned blocked tile and searches for another approach.
- A battle interruption cancels the current skill path without marking the
  intended story event attempted; a fresh path can be calculated later.
- Production checkpoint-replay tests simulate a walking leg interrupted by
  a native battle callback and confirm no extra model inference or false
  event failure.

## Deliberately not claimed

The changes do not establish true movement from a screenshot difference.
They do not grant battle victory, complete the story, or validate novel
FireRed v1.03.3 memory addresses. The private Windows host must still
produce actual acceptance evidence of verified field coordinates, successful
native map crossing, resumed gameplay after a battle and lasting checkpoint
memory before an autonomous playthrough can be certified.

Potential future learning: JevEmon's guarded *same-warp-tile retrigger*
handling, deterministic task-specific test episodes from NuzlockeSolver,
and external failure-classification dashboards. These require dedicated
tests for ROM-specific map scripts and are **not** claimed as delivered.
