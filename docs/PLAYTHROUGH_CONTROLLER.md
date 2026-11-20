# Goal-driven playthrough

The private queue may have a planning issue titled "Play through GAME — full-game autonomous QA" containing a goal, exact ROM digest, start scene and policy. It is a durable controller record, not a command the PC interprets. The host still accepts only strict bounded scenarios and optional explicitly enabled ROM-only patches.

## Controller loop

1. Fetch the latest linked test and require the complete evidence manifest.
2. Verify chunks, hashes, native result and screenshot dimensions using core/playthrough.py.
3. Interpret the screenshots. Record witnessed scene, visible menu/dialogue, current route objective and previous attempted actions. A changed screen is not necessarily progression. An unchanged screen may be an ordinary wait.
4. Choose a small normal-controller action batch; no arbitrary code. Use next_job to replay the verified prefix or resume a compatible immutable checkpoint with independent state assertions. Capture final state. Dispatch one bounded test.
5. Compare actual evidence to intended transition. Record failures, competing routes or menu choices using progress_record and recoverable_actions; avoid repeating unsuccessful action from same screen indefinitely.
6. At a verified transition, name checkpoint (v2 only) and advance to the next goal. Treat core crashes and reproducible script hangs as defects, distinguish from navigational stalls and assertion failures. Never claim credits/end until actual screenshots and evidence support it.
7. If a fix is independently verified, preserve source and deploy only an authorized SHA-locked ROM-only patch. Checkpoints cannot cross ROM versions. Reconstruct on the corrected ROM and retest.

The external AI supplies interpretation and decisions. This module is deterministic planning and evidence validation, not a visual model or standalone AI. The current ChatGPT scheduled controller can make decisions hourly; the PC processes queued batches every 15 seconds. Continuous low-latency decisions would need a separately authorized model/controller runtime and credentials. No API token, remote host code or unattended executable updater is included. Native checkpoint capability requires a verified upgraded host.

Public CI uses synthetic evidence exclusively. Private game screenshots, ROMs, states and saves never belong in the public source repository.
