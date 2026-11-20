# Experimental ROM Testing Environment

Reusable, deterministic GBA gameplay regression tools built on libmGBA. The first target is Pokémon Team Rocket: Jessie & James Edition. The emulator runs normal controller inputs and reads game state; tests do not modify game RAM or depend on a model.

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

The pathfinder is independently tested, not yet integrated with live game collision data. Game-specific RAM maps and story witnesses are not yet established. First gameplay gate: demonstrate the known Oak's lab failure on v1.0 and successful story progression on v1.01 using verified release hashes and ordinary inputs. Then expand to state-aware navigation, dialogue and battle control.

[Third-party navigation licence](vendor/pokemon_agent/LICENSE).
