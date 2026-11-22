# Persistent party knowledge and safe tactical automation

Jessie & James v1.03.3 retains two distinct kinds of knowledge:

1. **Historical party facts** survive checkpoint reloads: slot, species ID,
   level, last observed HP/status, current PP at the last verified observation,
   and four move IDs. Names, base power, accuracy, effect code and types are
   enriched only from the pinned, anchor-validated local ROM tables. Unknown
   or modified species/moves remain **unknown**; the player does not invent
   their abilities or strengths from standard Pokémon knowledge.
2. **Current battle state** is live-only: enemy species/type/HP/status,
   battler moves/current PP, cursor location, disable state, inventory and
   active callback. These are always re-read before any native controller action.
   The tactical notebook stores a signature of the fresh corroborated state;
   it is an *advisory record*, not permission to replay a previous input.

The party reader checks Gen III personality-key XOR data, Pokémon checksums,
individual slot bounds, Bad Egg flags, and an independent party-count witness.
An invalid read does not overwrite the last verified roster. Each new campaign
retains its existing ROM/model/goal identity-locked checkpoint format; the
knowledge is a bounded JSON field inside the same local checkpoint.

## Battle planning without repeated inference

Once a battle command/move callback is independently corroborated by a vision
observation, the existing native controller can handle repeated ordinary battle
choices without another Qwen call. Its existing tactics use:

- Classic Gen III type effectiveness from the pinned chart, STAB, real base
  power/accuracy, live stats and stages, current PP, burn and disabled moves
- Fresh HP and opponent status to select attacks, switch or heal
- Verified False Swipe/sleep/paralysis effects, cautious HP management and
  item availability for a capture attempt
- Verified party composition: initial team building first, then new type
  diversity only with a reserve of ordinary Poké Balls

A successful prior action does **not** mean another press will have the same
meaning on the next frame. Battle inputs are state-by-state (read callback and
cursor, send one short input, capture/checkpoint, re-read state); this is how
multi-turn battles avoid needless model inferences without blindly queuing ten
attacks. No shortcuts past fainting, switching, an opponent's response, status,
capture confirmation, team/menu changes, or story dialogue.

The tactical notebook computes a type coverage and defensive-pressure summary
only from species/types verified in the current exact ROM. It does not claim
weather/ability, critical-hit, move-prediction, or deterministic damage accuracy.
Trainer battles never throw Poké Balls. A full party, duplicate species,
insufficient ball reserve, or unverified type information prevents optional
type-diversity catches.

## Recovery and safety

- All local ROM, party, battle and checkpoint data stay on the user's computer.
  No party details, ROM bytes, proprietary graphics or state snapshots are
  added to the public source repository.
- For prompts, a small historical party summary is supplied as context with a
  stale-data warning. The current battle note is provided only when its native
  callback has been independently corroborated.
- Invalid ROM layouts, incorrect checksums, unsupported effect IDs or stale
  visual menus fail closed. A previous party/move fact cannot itself dispatch
  controller input.
- Static CI and native Windows controller tests do **not** prove battle and
  catching acceptance in the private v1.03.3 ROM. That requires subsequent
  user-host evidence of a battle victory, a capture/party-growth witness, a
  checkpoint reload and continued story progress.

The feature is part of `core/party_knowledge.py`, with regression coverage
in `tests/test_party_knowledge.py`. It augments rather than duplicates
`core/jj_battle.py`, `core/jj_menus.py`, `core/rom_catalog.py` and
`core/native_acceptance.py`.
