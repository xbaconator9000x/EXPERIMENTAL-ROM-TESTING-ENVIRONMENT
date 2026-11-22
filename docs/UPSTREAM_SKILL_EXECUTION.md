# Actual upstream skill execution (experimental)

The harness now invokes the original upstream AgentClient dispatcher from a
clean, exact-pinned MIT checkout of haggyroth/pokemon-agent at 594bfc7e3c208890c248269b67c5a1cf95074965.
No battle/catch/nav strategy was reimplemented. Existing native Live remains
the emulator. Battle cursor writes are translated into D-pad inputs with live
callback and cursor witnesses. All other memory writes fail closed. Upstream
battle/catch/party switching/healing/navigation/quest/menu/item/move-learning
skills are available through the allowlisted dispatcher; shop currently
requires an upstream read-only adaptation because it clears stale shop RAM.
The upstream options writer is never called. The upstream main loop is not used.

The experimental campaign drives the dispatcher with local Ollama Qwen,
journals exact masks/frames, records genuine RGB and atomically persists native
checkpoints in a separate file. It does not use or overwrite the production
player checkpoint. This is an opt-in vanilla LeafGreen campaign; no claim of
FireRed/Emerald or Jessie & James compatibility. No production install yet.

Prepare a separate pinned checkout and Python environment with upstream
requests, openai, rich and python-dotenv dependencies. Then run:

    python -m core.upstream_campaign --runner build/live_runner.exe --rom <local-leafgreen.gba> --sha256 <hash> --checkout <pinned-checkout> --out <separate-local-folder>

The exact SHA-1/revision gate rejects other ROMs. All private ROMs/checkpoints
stay on the user host. Test the adapter via tests/test_upstream_skills.py.
Native vanilla battle/catch/navigation acceptance, shop adaptation, revision
mapping, dashboard/queue connection and production installer are still
required. Never use a synthetic fixture as proof of real campaign completion.
