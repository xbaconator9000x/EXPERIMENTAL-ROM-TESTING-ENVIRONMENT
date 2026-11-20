# Continuous local AI playthrough (experimental)

Unlike scheduled ChatGPT actions, the local controller makes its next decision as
soon as the vision model replies. It is a separate process from the existing
bounded test queue. Use an explicitly installed local Ollama vision model; no
cloud inference credentials, paid API, or unattended executable updates.

1. Update/rebuild the reviewed host source, including core/live_runner.c.
2. Install Ollama for Windows from its official site and download a local
   vision model, e.g. ollama pull qwen3-vl:4b-instruct (larger model optional).
3. Leave the local Ollama service running on its default loopback interface.
4. From the repository folder, run:
   py -3.12 -m windows.autoplay --queue OWNER/PRIVATE-QUEUE --author OWNER --model qwen3-vl:4b-instruct
   Enter the existing Issues-only token at the hidden prompt. It remains in RAM.
5. Dispatch a private issue titled exactly [ROM-PLAY v1] with JSON:
   {"version":1,"sha256":"<exact imported ROM SHA-256>","goal":"Play the game to its ending through normal controls and report defects."}

The controller starts the exact ROM in a disposable local copy. A local vision
model sees a nearest-neighbor 3x enlarged emulator screenshot, recent decisions
and the game objective. It returns at most three bounded button actions. The
controller checks the JSON and executes only normal GBA buttons. No model output
is executed as code, no arbitrary files or remote model URLs are accepted.

It saves a native checkpoint and decision journal locally each turn. A restarted
controller resumes the exact ROM/runner/model/goal identity. Native frame-budget
rollover reloads the local state. The private issue receives periodic screenshots
and recent action summaries. Closing the goal issue requests stop (checked at
most every 30 seconds between decisions); Ctrl+C stops locally. An emulator error
preserves the last good checkpoint. A model review or repeated stall is not a
claim of completion; a human or external AI must examine evidence. A terminal
goal is not automatically restarted; use a new goal or explicit local review.
The current agent cannot reliably solve arbitrary RPGs; model quality, game
context, battle tactics, navigation and long-term memory require live evaluation.

The model is never sent the ROM, raw state, player saves, host paths, or access
token. It runs locally. Screenshots and summaries are sent only to the explicitly
configured private queue. Keep it private. Running this controller is an explicit
opt-in to screenshot sharing. The existing hourly ChatGPT task can independently
investigate confirmed bugs and develop source-only repairs, but must not dispatch
competing playthroughs when the continuous goal is active.

Tests use a fake model for schema, action safety and checkpoint continuity, plus
the original synthetic ROM for native live-state roundtrip. Neither proves
real-model or Jessie & James gameplay acceptance. Decision speed depends on
hardware and model; no fixed seconds guarantee.
