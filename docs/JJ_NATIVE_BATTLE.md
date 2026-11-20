# Native single-battle and inventory driver

Source-only adapter, exact Jessie & James v1.01 SHA-256; Classic only.
The authentic Spanish source ROM was inspected privately: candidates gMain,
battle mons, battle controller, action/move cursors, battle flags, disable
struct and both save block pointers have aligned executable references.
The four menu/dispatcher SHA-256 fingerprints are computed from that source
ROM, rechecked against the local English release before use. A patched
callback is not admitted. Runtime validation requires normal single-battle
flags, plausible active stats and types, matching checksum-verified party
member, and visual corroboration of cursor and menu callback. A stale or
unknown context falls back to vision. The first witness is not given the
candidate values. Subsequent selection uses normal controller inputs only.

Native move choice uses actual ROM catalog move data, live battle HP/stats,
PP, types, disabled move, estimated classic damage and type multipliers.
Catch intent defaults to a new species when the player's party has fewer
than three members and ordinary balls are present. Trainer encounters are
excluded; no Master Ball. The player opens BAG for captures or healing, or
party for a low-HP switch. Actual bag use and party selection still require
visual policy. Exact item counts and money are decoded via relocated save
block pointers and encryption key, with sanity checks. Bag values are passed
to the local strategic planner only in corroborated contexts. Unknown
moves, mismatched code, special battles, ambiguous status or repeated native
actions fall back. No RAM writes, debug battle injection or gameplay cheats.

Reference layout: pret/pokefirered include/pokemon.h and include/global.h;
haggyroth/pokemon-agent game/constants.py candidate addresses. No game data
or copyrighted bytes are included. The Spanish source fingerprint is NOT
proof the English ROM matches; the live player performs that admission.
Tests are structural, not evidence of real battle or capture completion.
