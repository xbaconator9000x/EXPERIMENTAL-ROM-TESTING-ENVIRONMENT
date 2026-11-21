# Upstream gameplay port: first isolated baseline

Branch is experimental, not a replacement installer. Existing Windows host and checkpoints remain untouched.

Vendored upstream MIT source: [haggyroth/pokemon-agent @ 594bfc7e3c208890c248269b67c5a1cf95074965](https://github.com/haggyroth/pokemon-agent/tree/594bfc7e3c208890c248269b67c5a1cf95074965).
Original paths and Git blob IDs:

- `LICENSE`: `e0e17f7144645446102a635b1db7a2b25b002e88`
- `game/constants.py`: `822f5fe3a07eabea681e88e44fe4f9d1408d4400`
- `game/state.py`: `4fb14ba12ae32f5d53d5033fbaaa0c7fb6f1afce`
- `game/memory_reader.py`: `3f6dd548188844696eb1dff48bb6187edb955571`
- `game/tilemap_reader.py`: `c2b45959874eb3f69bda759a2a677047f5d4d96d`
- `game/pathfinding.py`: `8aae86bb6473fadc01cc0bd4da14b10d30f90c64`
- `knowledge/growth.py`: `caa39064bf98762710d48312d89f448bce6f3dd4`
- `knowledge/growth_data.py`: `678d1f47f44298692c7d0047a1ef311b349c7544`
- `knowledge/type_chart.py`: `49c29ddcd16f0eb10976ca76d0c7d92acd89ceee`

Only import paths/type annotation dependency were adapted; retained upstream license.
Uses existing native mGBA transport for actual upstream party decoder, callback reader, map collision, A* and Classic type chart. No writes. Exact original LeafGreen USA SHA-1 identity from [PokéBot's ROM catalogue](https://github.com/40Cakes/pokebot-gen3/blob/f14ab79db960315db02333928ba444f9d425b6fc/modules/roms.py), matching SHA-256 of running local instance and game code/revision required. Upstream addresses must still be validated against live vanilla footage; no other revision/hack admitted.

Local read-only probe: `python -m core.upstream_probe --runner build/live_runner.exe --rom <local.gba> --sha256 <hash> --state <optional-native-checkpoint> --tile X Y`. Without checkpoint, title/unknown is expected and no route should be requested. Native checkpoint is read, not overwritten. Tile route is advisory, not autonomous movement; NPC blocking needs a verified live adapter. No new game data in CI.

Next: validate raw observations against native vanilla frames; port upstream navigation/skill code through input-only transport and replace direct cursor writes with gated controller navigation. Then derive FireRed/Emerald and Jessie & James layouts from verified source/runtime witnesses. PokéBot GPL-3.0 code has not been copied: resolve licensing before importing it. Do not mark battles/catches/campaign accepted until real evidence.
