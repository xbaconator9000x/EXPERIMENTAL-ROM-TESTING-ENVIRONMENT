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
