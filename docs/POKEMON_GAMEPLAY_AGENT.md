# Pokémon gameplay agent: hybrid vision + policies

The continuous player is now the execution path, not a scripted regression
runner. It observes each screen and selects ordinary inputs. The vision
planner proposes a scene, objective, controls and optional structured
observations. A bounded policy can substitute one controller action for a
proposed action when enough observations are available.

- Battle command/move menus: use the observed cursor, enemy/own types,
  PP, power and accuracy. Gen III Classic and optional Modern type rules
  differ for Steel/Fairy. Select one direction at a time, then re-observe
  before confirming. Unknown types/moves fall back to the vision planner.
- Catching: only a model-observed wild encounter with explicit capture intent
  triggers catch strategy. Weaken using lower-scoring damage, choose BAG
  when weak/statused, and let the model identify the correct item. Healing
  chooses BAG when low HP and item availability is observed. No memory edits.
- Navigation: optional vision-estimated 15x10 screen grid; BFS avoids unknown
  tiles, proposes only one step and avoids observed blocked directions on
  identical screens. This is not proven collision data. The exact-revision
  FireRed memory profile is still unverified; never use guessed addresses.
- Quest notebook: bounded deduplicated facts and locations persisted inside
  the existing atomic checkpoint. Includes prior objectives in future model
  prompts. Model-read statements remain hypotheses, not proven story flags.
- The model still handles unfamiliar menus, inventory, dialogue, interactions,
  switches and puzzles. It is not a guaranteed competent campaign player.
  Never claim battle/catch/route acceptance without actual gameplay evidence.

Synthetic tests cover rules, route detours, observation validation and
checkpoint compatibility. Real battles, captures, map navigation and ending
remain to be demonstrated on the actual ROM.
