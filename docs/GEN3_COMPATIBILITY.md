# Exact revision compatibility (native profiles, not release acceptance)
Seven pristine English vanilla identities plus the separately gated Jessie & James release.
FireRed and LeafGreen rev 0/1, Emerald rev 0, Ruby and Sapphire rev 0.
RS uses fixed unencrypted save blocks, 32-bit party count, IWRAM party/event
arrays, and the revision's actual symbol table; no ROM header-only admission.
FRLG and Emerald have separate bag and party callback witnesses; Emerald's
five-pocket BagPosition is not FRLG's three pocket layout. RS menus still use
vision; RS battle controller labels were matched to the pret source function
order and must be corroborated by actual on-screen cursor before automation.
The current player always retains vision fallback and cannot admit unknown
hacks merely because they use a familiar header.

Source addresses: 40Cakes/pokebot-gen3 commit f14ab79db960315db02333928ba444f9d425b6fc,
modules/data/symbols/:
- pokefirered.sym blob 5377ee48ca773d012000302545b477c936f40d46
- pokefirered_rev1.sym blob 7ad94aaabfdcfb976ce4d1f532561b8668feefe7
- pokeleafgreen.sym blob 2817a977dc8a48158591a12663a8d23d8f43fd0d
- pokeleafgreen_rev1.sym blob c973dbbced397553cb4bef1f99d4e856f769976f
- pokeemerald.sym blob df0cf99d7a88abc26234cc1ce5c3200a9794bdfb
- pokeruby.sym blob 5ede97531d6e478c85b7783f49acb577d7b7bc0c
- pokesapphire.sym blob 0de78dc8f0f02b768f13ccd08fc927bef975ded4
RS SaveBlock1 and battle_controller_player.c are cross-checked against
pret/pokeruby; Emerald BagPosition and PartyMenu against pret/pokeemerald
include/item_menu.h, include/party_menu.h and include/constants/item.h.
Only numeric symbol facts used; no PokéBot GPL gameplay code copied.

All profiles still require actual native visual/position/party evidence.
No native retail gameplay acceptance is established by fixture CI.

## ROM-hack map compatibility evidence
Exact-hash Jessie & James field maps receive a one-time, read-only native
MapHeader/MapEvents pointer-and-count audit after verified movement. The audit
checks object, warp, coordinate, background, and map script structures against
pret/pokefirered layouts. It understands hidden-item union metadata and
reports custom event kinds as unclassified. Only aggregate structural status
and counts enter private ROM-AUTOPLAY diagnostic reports; no game contents,
script bytes, addresses, paths, saves, or ROMs are uploaded.

STRUCTURALLY_READABLE applies solely to the observed map's layout and pointers,
not to script opcode semantics, battle, quest progression or the entire ROM.
Native Windows end-to-end compatibility must be demonstrated separately.
The audit adds no controller inputs, model calls, or mutable game state.

## Standard FRLG event-script prefix inspector
The on-host map audit now samples at most eight distinct ROM-backed script
entries per witnessed map. It decodes up to 24 **known-width** standard FRLG
commands per entry (maximum 160 bytes) from pret/pokefirered
asm/macros/event.inc, distinguishing possible dialogue, player choices,
flag/variable checks, item operations, trainer events, warps, and native
specials. A modified/unknown opcode, dynamic trainer/warp instruction, or
branch stops inspection; the script is never executed speculatively.

Map-header type 2 and 4 scripts are **conditional variable-pair tables**,
not bytecode, per pret/pokefirered src/script.c. Their targets are inspected
separately without evaluating live flags or claiming event completion.
The private audit emits only aggregate intent categories and stop reasons.
It does not expose text, item/flag IDs, bytecode, pointer addresses, script
paths, secrets or saves. Standard-looking bytecodes in a ROM hack are still
**hypotheses**, not proof of runtime semantics, and they cannot authorize
controller inputs without independently verified live game state.
Branch-aware static inspection additionally follows bounded ROM-backed call,
goto, and conditional-branch destinations. It inspects both conditional
possibilities, never claims that either ran, and stops at variable-width,
custom or opaque native commands. Loop detection and an eight-segment-per-
script budget prevent stalls. Invalid branch targets are counted only; their
addresses and raw command bytes never leave the host.

## Read-only persistent event state (candidate)
From pret/pokefirered include/global.h and src/event_data.c, the exact-release
adapter can additionally inspect a stock-layout candidate for 0x120 bytes of
flags (SaveBlock1 + 0xEE0) and 0x100 halfword variables (SaveBlock1 + 0x1000).
The live SaveBlock1 pointer and position/map identity must independently
match the verified overworld field. Special flags/variables remain unsupported
because they live outside this save region. Aggregate flag counts and nonzero
variable counts only are exposed privately; **no raw save data or IDs** enter
logs, GitHub issues, or PRs. Changes are never treated as quest completion
without a separately observed event and correct modified-ROM layout evidence.
When a native-verified action starts and ends on the same verified map,
the runner compares two private in-memory table snapshots and records only
aggregate counts of newly set/cleared flags and changed variables, plus the
action source and decision number. This is a candidate event-data delta,
not a completed-quest or item-acquisition claim. Unknown layouts and
script-locked after-states are skipped rather than guessed.

## Read-only native text-printer probe (candidate layout)
Derived from pret/pokefirered include/text.h, src/text_printer.c,
src/text.c and src/field_message_box.c, corroborated against the pinned
FireRed 1.0 symbol map. For SHA-admitted Jessie & James only, a candidate
sTextPrinters[0] and field message-box state can advance verified WAIT/CLEAR/
SCROLL_START text with a single GBA A press or wait while text is printing.
It does not call Qwen, assume a choice menu, write RAM, or read text content
into diagnostics. It rejects unknown addresses/states and floating choices;
identical ready-page repeats are guarded. Candidate symbol addresses are
NOT guaranteed to survive ROM-hack modifications. Real Windows mGBA
acceptance is required before this facility is considered validated.
