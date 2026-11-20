# Intent-bound bag and party controller

Native battle selection carries a bounded intent into the next menu, including
the intended item or party slot. Capture never selects a Master Ball. Healing
chooses the smallest sufficient ordinary healing item. The adapter reads
candidate battle-bag position and pocket arrays and packed party display order
only after exact ROM admission and source fingerprints/pointer anchors.
Each intent needs an independent visible cursor witness; bag additionally
needs a matching visible item name and count. Subsequent cursor moves are
checked against one-step expected changes. A confirms once only: USE/SHIFT,
target selection, forced switches, different pockets and ambiguous layouts
return to vision until more per-revision runtime witnesses are available.
This is partial native item/switch automation, not demonstrated completed
captures or healed battles. All game actions use normal GBA buttons.

Original Spanish source party-callback fingerprint and aligned bag/party
RAM references were rechecked locally. Source layout reference:
haggyroth/pokemon-agent game/constants.py; pret/pokefirered items.h.
No ROM bytes or private screenshots included in this commit.
