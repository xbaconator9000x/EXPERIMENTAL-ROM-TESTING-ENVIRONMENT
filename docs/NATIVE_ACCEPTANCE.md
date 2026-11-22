# Exact-build native gameplay acceptance

The v1 continuous player records a local milestone ledger keyed to ROM
SHA-256, runner SHA-256 and a hash of the gameplay source modules. Previous
engine evidence is archived, never silently counted toward a different build.
The private queue report carries this ledger. The dashboard identifies the
milestone status. Ordinary emulator inputs only; no ROM/save transfer.

Evidence: native one-tile movement, observed map transition, actual
battle win (live outcome after a previously witnessed battle), capture
(outcome and checksum-valid party growth matching the encountered species),
HP restoration without level/max-HP change, observed native move PP use,
and matching LCD on independent native checkpoint reload. Stale outcome
bytes, no prior battle witness, or wrong cartridge cannot establish a pass.
Party checksum/count failures are recorded when field/battle data is admitted.
A capture sent directly to PC is not counted by this conservative ledger.
HP restoration is not proof of a particular healing method; emulated state
reload is not battery-backed Flash cold-restart acceptance.

The status is INCOMPLETE or MILESTONES_WITNESSED, never RELEASE_ACCEPTED.
Actual credits/endgame, PC/caught Pokémon integrity, in-game Flash persistence
and any new hack-specific compatibility remain separately subject to genuine
native evidence and manual review. Synthetic fixture tests prove only the
ledger's fail-closed behavior. Current physical host must run this exact build
to produce qualifying evidence; earlier player reports are insufficient.
