# Jessie & James fast gameplay adapter: first integration

Exact target v1.01 SHA-256 06d9c87234400f45f1fc3a356881f0ad8bd9b977bc5cbed450e5c7eedd01b632.
The original owner's Spanish source was inspected locally and contains aligned
references to candidate FRLG global addresses (SaveBlock1 pointer, map header,
backup layout, gMain, object events, party, script and fade). These are candidate
addresses, NOT a confirmed runtime symbol map. Admission repeats the checks on
the exact imported v1.01 ROM. No ROM or copyrighted data is included.

- Fast ordinary dialogue: inspect native RGB textbox geometry and additional
  overlays; refuse centered setup screens, choice menus and unknown layouts.
  Advance only one page with a bounded A press, wait for text, re-observe,
  give the strategic planner a turn after six fast decisions. Retain private
  local page screenshots (up to 5,000) for QA. Pixel heuristics are conservative
  but not a proof that all possible menu variants are excluded.
- Structured field: read candidate live map and active player object.
  Require valid pointers, matching player coordinates, stable callback and
  unlocked script/fade. Learn actual callback through TWO ordinary successful
  directional movements on the same map; do not import LeafGreen callbacks.
  Planner can supply a coordinate target; A* performs one ordinary D-pad
  action, re-reads field, and stops on mismatch, transition or lock. Dynamic
  objects are treated as obstacles. No movement memory writes.
- Party: decode Gen III encrypted substructures with checksum, sanity checks
  and bad-egg flag, only expose on corroborated field. No player identity
  data is exported. This is not yet live battle admission.
- Preserve checkpoint schema and remote guidance. Rate-limit fast reports.
- Source references: pret/pokefirered include/pokemon.h, include/global.fieldmap.h;
  haggyroth/pokemon-agent game/constants.py (candidate LeafGreen globals only);
  existing vendored A* from pokemon-agent. Original new code, no copied source
  other than pre-existing licensed vendor. All gameplay is read-only except
  ordinary emulator inputs.

This first batch does not establish real-game victory, catching, or battle menu
automation using RAM. Synthetic tests are for the structural logic, not gameplay
acceptance. Native exact-revision movement witnesses are required on the PC.
