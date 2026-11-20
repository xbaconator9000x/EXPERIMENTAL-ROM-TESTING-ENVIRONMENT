# Outdoor connections and objective priorities

Reads candidate map connection headers and the live padded grid after native
field admission. Only unique cardinal connection sides with a passable adjacent
cell are considered. A* approaches the in-map edge, then issues one D-pad
input. Records actual arrival only after reading the next stable field.
Multiple destinations on a side, special movement and unknown geometry fall
back to vision. No changes to RAM, game flags, or ROM.

Exploration prioritizes reachable NPCs before obtaining a party and unvisited
destinations afterward. This is a baseline exploration strategy, not a complete
quest solver. Exact English release live witnesses and actual campaign
completion remain outstanding. Synthetic tests cover bounded grid and crossing
logic, not actual gameplay acceptance. Layout reference: pret/pokefirered
include/global.fieldmap.h, include/fieldmap.h, src/fieldmap.c.
