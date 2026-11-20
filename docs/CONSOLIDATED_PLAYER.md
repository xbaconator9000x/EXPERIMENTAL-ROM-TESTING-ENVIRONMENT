# Consolidated autonomous player beta

Installs a single pinned version of the gameplay controller without rebuilding
the previously installed native runner. Preserves existing ROM imports,
progress.bin and action journals. Local models: 4B primary and 2B fallback;
compact schema retry, shorter prompts, rich battle/field observation, and
independent visual backup. Still requires real full-game acceptance.

The controller can now obtain an exact-state gameplay hint from the trusted
private goal issue. Comment format:
ROM-GUIDE v1
{"decision":15,"screen":"<current 64-character RGB SHA256>","scene":"menu","objective":"select option","actions":[{"button":"A","frames":5}]}

Only the authenticated configured author with OWNER/MEMBER/COLLABORATOR
association is accepted. A hint is scoped to one decision number and screen
hash, only bounded GBA controls, and is stale automatically after progress.
No arbitrary code or paths. Review/crash holds resume only with a matching
hint. The hourly external AI can inspect evidence and provide such guidance
when local models cannot decide; it is not on the critical path normally.
Checkpoint rollback to a previous hash-verified generation retains progress
if the latest checkpoint file is corrupt. This is not player save editing.

Battle/catch policies, visible bag selection, visual pathfinding, local quest
notebook and observed map connections are advisory: inaccurate perception
can still make inappropriate decisions. True ROM-specific field and battle RAM
profiles are not verified and are deliberately not guessed. A fully completed
campaign is not yet proven.

Neither the player nor remote guide can download or execute host updates.
An explicit reviewed local installer is used for any new controller code.

## Optional cartridge catalog

For the exact known Jessie & James v1.01 digest and Classic goal, the local
reader checks the BPRE header, aligned pointer witnesses, and multiple known
species/move name/type anchors before admitting candidate legacy FireRed
tables. It uses row data for recognized names, including actual ROM move
power/accuracy; it never substitutes base PP for observed current PP.
A relocated or incompatible table fails closed to vision. Anchor checks
are not proof of all runtime table usage, especially in modified ROMs.
No ROM data is exported. Source references:
https://github.com/pret/pokefirered/blob/master/include/pokemon.h
https://datacrystal.tcrf.net/wiki/Pok%C3%A9mon_3rd_Generation
https://bulbapedia.bulbagarden.net/wiki/Move_data_structure_in_Generation_III

Context-sensitive idle settling lets animations and dialogue finish before the next vision inference. Actual settle timing is recorded in the action journal. Remote exact-state guidance retains fixed 24-frame settling. Compact observations retain scene and quest facts; rich planning is periodic or context-triggered. This optimizes inference count, not a measured speed guarantee.
