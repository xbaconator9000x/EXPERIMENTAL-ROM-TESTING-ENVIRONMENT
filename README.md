# Experimental ROM Testing Environment

Reusable, deterministic GBA gameplay regression tools built on libmGBA. The first target is Pokémon Team Rocket: Jessie & James Edition. The emulator runs normal controller inputs and reads game state; tests do not modify game RAM or depend on a model.

## Native Windows desktop host

The [Windows host](windows/README.md) is a native Python/Tkinter desktop
control panel backed by Windows-compiled libmGBA. It imports owned ROMs
into a private SHA-256-addressed local library, runs selected local scenarios,
keeps evidence on the PC, and needs no WSL. The optional private GitHub
remote queue and startup service are **not yet implemented**. The Windows
workflow verifies the native engine against an authored synthetic cartridge.

## Layout

- `core/` — native emulator runner and exact-ROM hash guard.
- `vendor/` — licensed reusable route planner.
- `profiles/` — version-specific ROM identity and verified engine mappings.
- `tests/` — original homebrew fixture, unit and native positive/negative tests.

## Run

On Ubuntu 24.04 with Python 3 and libmgba-dev installed:
```sh
bash scripts/test.sh
```

This deliberately uses only an original synthetic cartridge, not a commercial ROM. The native input witness tests actual A-button down and release through emulated memory; assertion failure, timeout, malformed scenario, absent assertions and wrong ROM fingerprints must fail. Screenshot output is local. The public CI runs the same suite.

## Real-game testing

Use locally owned ROMs and saves on a trusted local or private runner. Do not publish ROMs, saves, game-derived dumps, private build archives, or screenshots through this public repository or its Actions artifacts. No actual game ROM or private record is bundled. Keep real-game outputs local. Public CI uses only the synthetic fixture.

```sh
python3 core/run_locked.py --runner build/state_runner --rom /private/game.gba --sha256 VERIFIED_SHA256 --scenario /private/scenario.txt --out /private/evidence
```

Scenario instructions: `press KEY frames`, `idle frames`, `wait width address mask expected timeout_frames`, `assert width address mask expected`, `capture`. A failed assertion or wait is a nonzero exit. Every scenario needs a successful assertion. A pass is specific to the observed conditions, not proof of full-game completion.

The local read-only native transport and FireRed field reader feed the route planner from the live padded collision grid. Each step must produce the intended coordinates in the same map and verified field context; stalled or unexpected movement fails. The synthetic ARM fixture includes a real collision wall and checks the full four-step detour. Real-game symbol addresses, lock predicates, NPC occupancy, warps, ledges, dialogue and battle state are not yet verified. Do not use guessed addresses. First gameplay gate: demonstrate the known Oak's lab failure on v1.0 and successful story progression on v1.01 using verified release hashes and ordinary inputs. Then expand to state-aware navigation, dialogue and battle control.

[Third-party navigation licence](vendor/pokemon_agent/LICENSE).

## FireRed state reader

The ABI follows `SaveBlock1`, `MapHeader`, `MapLayout` and `VMap` in [pret/pokefirered](https://github.com/pret/pokefirered/tree/ce6406d8c2eaf46d543c8a2606de0c3cb1951982), particularly `include/global.h`, `include/global.fieldmap.h` and `include/fieldmap.h`. A `Profile` requires exact verified addresses for each game revision; use the same expected hash when opening `Live`. Public CI uses a synthetic ARM fixture only. Plain intra-map walking is not complete gameplay automation.

For local, exact-release reconstruction and observational state probes, see [Jessie & James profile](profiles/jessie-james/README.md). Public CI still uses synthetic cartridges only.

## Heart & Soul native beta

[Source-built Heart & Soul v2.0.6](profiles/heart-and-soul/README.md) is the first real-game test target. An exact-ELF-symbol-driven intro controller executes actual inputs in native mGBA. The first milestone is challenge setup, not full campaign completion. Public CI retains only symbolic observations, not the game ROM or assets.
