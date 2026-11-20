# Read-only live gameplay dashboard

The continuous controller writes a hash-verified atomic snapshot after every AI
decision. Open a SECOND PowerShell window in the repository folder, while the
existing player remains running:

    py -3.12 -m windows.dashboard --queue OWNER/PRIVATE-QUEUE

Optional --goal-id selects a specific numeric GitHub issue database ID.
The dashboard shows the actual last saved emulator screen, latest model scene
and objective, last executed controls, history, decisions, frame count,
observed recent decision interval, checkpoint age and terminal alerts. It polls
the local checkpoint once per second. It neither advances nor pauses the game.
It does not require the GitHub token, make HTTP requests or expose a local
network server, and it can be closed independently of the player.

The screen updates when a decision finishes rather than at the GBA frame rate.
Scene and objective text reflect the model's previous interpretation and can
be wrong. A stale checkpoint is not proof of a crash; check the player terminal
and model. The first checkpoint is normally created before inference. On phone,
progress reports remain available in the private queue; no remote browser
access to the PC is offered by this dashboard.

Tests exercise the snapshot reader and checkpoint integrity. Windows GUI
appearance and actual model performance require a local user run.
