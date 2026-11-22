# Guarded adaptive vision batches and Jessie & James v1.03.3

## Batching contract

A local Qwen call may propose **1–10** short sequential controller actions.
Only a model-observed `field` **or a separately corroborated field witness**
qualifies, and every cached action must be UP, DOWN, LEFT or RIGHT for 1–24
frames. A false or stale model label alone never authorises a batch. Every
movement is independently executed and committed as a normal native decision,
with its own RGB witness, mGBA save-state checksum and `actions.jsonl` entry.

After each input, the next cached action is abandoned if any of these apply:

- A dialogue frame is detected, the image has faded or suddenly changed, the
  screen has stayed effectively still, or the lower frame suggests a new panel.
- A verified native field changes map, stops moving, or ceases to validate.
- The prior screenshot hash no longer matches, a native menu or battle is
  detected, or an operator command changes the running game.
- A native step fails, a replay incident is captured, a review is requested or
  a new remote guide overrides the plan.

If a model emits only **one** directional action after two consecutive
visually changed steps in that same direction, the controller may seed a
bounded momentum plan: **four steps total** under partial field corroboration,
or **ten steps total** only after fully verified native field movement.
Each additional movement gets its own screen check and durable checkpoint;
a stationary screen, unexpected image change, dialogue, battle, menu or
operator intervention immediately discards the rest.\n\nThe conservative pixel guard can stop after one input; it is not a classifier
that proves a location is safe. **No unverified sequence containing A, START,
B, item use or battle choices is cached.** Unverified menus and battles now
execute only the first proposed vision action, obtaining a fresh observation
before making another choice. Verified native battle policy is still
re-evaluated using live PP, HP and cursor witnesses rather than caching blind
attacks.

## Exact v1.03.3 native release gate

The original exact-release profile is preserved. The privately supplied v1.03.3
ROM has SHA-256
`bb4fd81b32f5e2a69254fc18fbc47e7c7bcbfb35baeace45be2b5dda7876803b`.

Local read-only checks on that *specific* cartridge found BPRE revision 0,
the expected aligned field/inventory anchors, validated original species/move
table names and pointers, and matching battle/command callbacks. Its
move-menu callback 32-byte signature differs, and the new exact digest is pinned
only to this revision. All runtime callback, cursor, party checksum, field
movement and visual corroboration checks still apply. A static ROM signature
alone is **not** proof of playable battle/catching or complete story coverage.

No ROM, cartridge bytes, save data, save states or original story assets belong
in public source control or public CI. Existing private campaign #23 and older
campaign #19 are preserved and are not automatically modified by a source push.

## Verification and rollout

The Windows installer includes the new `core/action_batch.py`,
`core/navigation_memory.py`, independent boundary regressions, and an
end-to-end checkpoint replay test. The bounded navigation memory remembers
no-op steps per visual state and receives only SHA-256 screen keys and
controller actions; changed pixels never become asserted map coordinates. Install only a reviewed, CI-verified exact commit while the player
is stopped; the local checkpoint is preserved. The GPU-enabled Ollama service
can stay running. Check the dashboard decision counter and source labels for
`batch_navigation`, plus local checkpoint integrity, before claiming speedups.
