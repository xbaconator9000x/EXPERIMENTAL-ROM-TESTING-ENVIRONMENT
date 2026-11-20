# Broader native compatibility

Source: exact English vanilla symbols from pret/pokefirered symbols branch:
https://raw.githubusercontent.com/pret/pokefirered/symbols/pokefirered.sym
https://raw.githubusercontent.com/pret/pokefirered/symbols/pokefirered_rev1.sym
https://raw.githubusercontent.com/pret/pokefirered/symbols/pokeleafgreen.sym
and pret/pokeemerald:
https://raw.githubusercontent.com/pret/pokeemerald/symbols/pokeemerald.sym
SHA-1 identity reference: 40Cakes/pokebot-gen3 modules/roms.py at
f14ab79db960315db02333928ba444f9d425b6fc.

Vanilla FireRed v1.0/v1.1, LeafGreen v1.0 and Emerald now have separate
symbol-based read-only field, inventory, party and single-battle adapters
integrated into the existing v1 autoplay loop. They reuse the current
upstream-derived battle/type logic, field navigation, NPC/warp exploration,
and existing checkpoint and queue. Runtime party count, checksum, active
battler, controller callback, collision geometry and movement/visual
corroboration still gate actual use. The exact Jessie & James profile is
unchanged. Native vanilla menu driver is not yet enabled; vision handles
unverified bag/party screens. Unknown hacks remain vision-only, not falsely
admitted as vanilla. Full pinned upstream story dispatcher is still LeafGreen
v1.0 only. No actual ROM data is committed.

These are implementation profiles, not certified gameplay passes. Require
private native evidence for movement, battle, catch, healing, save/reload,
and story progression before declaring acceptance.
