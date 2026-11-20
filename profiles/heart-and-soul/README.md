# Heart & Soul v2.0.6 beta

Source: [PokemonHnS-Development/pokehns-expansion](https://github.com/PokemonHnS-Development/pokehns-expansion/tree/167aa6d537b109bb229c231ddce4616974c4da71).
Pinned source revision: `167aa6d537b109bb229c231ddce4616974c4da71`.

The workflow compiles the upstream game and ELF directly, connects the headless native mGBA controller, and resolves task and callback addresses from that exact ELF. No vanilla FireRed RAM addresses are assumed. The beta uses ordinary controller inputs only, and advances on observed title, menu, professor, gender, naming, name confirmation and challenge-menu states. It must actually reach the challenge setup after naming the player to pass; an emulator boot or a timeout is not a pass. The first gate does not yet cover the overworld, battles, or campaign completion.

The source checkout and built game are ephemeral. Do not upload ROMs, saves, upstream assets, or frames as public artifacts. Only the authored milestone trace (symbolic task names, frame counts, and runtime state) is retained. The public source location is not a blanket licence to redistribute game assets.

Local equivalent after building `pokehns.gba` and `pokehns.elf` from the pinned source:

```sh
cc -std=gnu11 -O2 -Wall -Wextra core/live_runner.c -o build/live_runner -lmgba
python3 -m core.hns_beta --runner build/live_runner --rom /path/pokehns.gba --elf /path/pokehns.elf --out /private/hns-beta.json
```
