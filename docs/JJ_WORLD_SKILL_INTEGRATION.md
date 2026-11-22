# Verified task execution: reuse before reinvention

This milestone extends the EXISTING Jessie & James native Windows player.
It is not a second emulator, a save editor, a walkthrough, or an alternate
autonomous client. No proprietary ROM/save files or private frames are shipped.

## Existing open-source foundations

- **haggyroth/pokemon-agent (MIT)**: already vendored
  `vendor/pokemon_agent/pathfinding.py` with its license, and ported
  compatible memory/navigation/battle ideas into the existing
  `core/upstream_leafgreen/` source set.
  Source: https://github.com/haggyroth/pokemon-agent
- **mGBA**: the single existing local Windows runner handles GBA buttons,
  framebuffer reads and native save-state checkpointing. There is no
  additional mGBA instance or HTTP daemon.
- **Existing project internals**: `core/jj_explore.py` handles verified
  warps, NPC approaches, connections and A* navigation; `core/jj_battle.py`
  handles verified menu callbacks, current PP/HP and moves; the existing
  `core/upstream_skills.py` experimental skill vocabulary informed the
  production task interface. The experimental LeafGreen campaign never
  shares production Jessie & James saves.
- **External architectural reference only**:
  https://github.com/daniel4x/JevEmon demonstrates destination selection
  from RAM-backed reachability rather than one LLM decision per button.
  It is GPL-3.0, so no code from that project has been copied or vendored.
- **Additional comparison**:
  https://github.com/nori00000/pokemon-agent-os uses deterministic map
  exploration and evidence-scored recovery for Gen I. Its architecture is
  informative, but its Gen I memory addresses and tools must not be
  transplanted into a FireRed ROM hack.

## Jessie & James verified world model

`core/jj_world_model.py` is a thin coordinator over the existing A* and
native progress systems. It records a bounded map visit ledger, player
positions, observed NPC/warp/connection counts and *native-witnessed* map
crossings. It does NOT infer coordinates from a changed screenshot, nor
treat a proposed warp as an observed transition.

It selects high-level skill intents:

- **interact** when a verified party is empty and an NPC is reachable
- **explore** when the party is healthy, preferring an unvisited exit,
  then a story NPC, and only then previously visited connections
- **review** for a party with no healthy members or a critically injured
  party; do not blindly walk into another encounter
- **explicit exit/interact** if the model has chosen a supported task
  and the native field reader corroborates it

The original `Explorer` remains responsible for actual pathfinding,
occupancy checks, single-tile movement and menu/interaction inputs. A model
cannot claim a skill completed. `complete()` recognises only witnessed
crossings in the existing native `observed_field_transitions` evidence.

`core/jj_unattended.quest_state()` distinguishes:
- party/movement/battle/capture/healing milestones from native evidence;
- vision-derived dialogue clues and proposed objectives, marked as hypotheses.

## Controller and QA boundaries

No memory writes, direct warp injection, save editing, training shortcuts or
random battle/menu spam. Each input goes through the same checkpoint,
per-action scene checking and private operator control as before. Unknown
script/fade locks and incorrect map/party/battle structures continue to
fail closed.

Static tests cover an empty starter party, new exit vs already explored
connection, fallback to an NPC, a critically injured party, invalid
native fields, identity-locked checkpoints and no invented map crossings or
story completion. The native mGBA Windows smoke test proves control, not
real Jessie & James hospital escape or game completion.

## Next evidence required after the user's local install

1. A verified native field snapshot on Jessie & James v1.03.3 with an exact
   map ID and player coordinates and a real field-control callback.
2. Consecutive `native_explore` inputs moving along a witnessed A* path;
   visible native evidence of crossing a room exit.
3. The durable world graph records the new destination only once the
   game independently corroborates a map transition.
4. A party-growth/capture/battle milestone verified by the existing native
   acceptance ledger; no success claim from dialog or a model comment alone.
5. Real-world latency measurements of Qwen calls vs native instructions;
   no claimed uninterrupted 60fps display during the inference pause.

Only after these pass in a private ROM run should this be called an
autonomous story-navigation acceptance milestone.
