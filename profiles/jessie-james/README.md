# Jessie & James profile

The release hashes are exact. Local reconstruction:

```sh
python3 core/prepare_rom.py --source /private/original.gba --patch /private/v101.bps --manifest profiles/jessie-james/releases.json --version 'English v1.01' --out /private/v101.gba
```

The v1.01 reconstructed ROM header identifies BPRE revision 0. This alone does not validate any vanilla RAM address or callback. Obtain candidate symbol addresses from the matching revision, then establish independent visual and memory witnesses for title, field, dialogue, menu, battle, movement, and lock states. Candidate JSON uses the fields of `core.firered.Profile` (integer addresses and values, exact ROM SHA-256); keep it local until verified. Do not use LeafGreen callback addresses as FireRed truth.

The local probe accepts a JSON list of explicit actions, e.g. `[{"op":"idle","frames":120,"capture":true},{"op":"observe"}]`. It records callback, saveblock pointer, layout/grid pointers, and decoded field state or a refusal reason with optional actual screenshots. It does not play the game, attempt random inputs, or declare a pass.

```sh
python3 -m core.probe --runner build/live_runner --rom /private/v101.gba --profile /private/candidate.json --plan /private/probe-plan.json --out /private/probe-evidence
```

Do not commit real ROMs, screenshots, saves, dumps or private probe evidence. A legitimate Oak's lab checkpoint and verified callback, lock predicates and progression flag remain required before a regression can be run.
