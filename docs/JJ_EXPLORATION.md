# Native event exploration

After the field adapter has actual directional movement witnesses, read the
current MapHeader event pointer and bounded WarpEvent rows directly from the
local ROM. Read active visible object positions and player facing from native
RAM. Expose reachable events to the local model as structured state.

High-level field_task explore, interact, exit delegates one reachable untried
event. A* routes to a warp tile or an adjacent NPC interaction tile; unrelated
warp tiles are avoided. Recheck position, context, occupancy and facing each
step. Interact with A only when adjacent and facing the current NPC. Record
attempts and observed transitions; return to strategic planning on any
mismatch, dialogue, lock, warp, or bounded budget exhaustion. Dynamic NPCs that
move invalidate their plan. Only ordinary controls are sent. An event attempt
is not a completed quest. Boundary connections, doors needing a separate
action, hidden events and some special terrain remain planner responsibilities.

Installer now explicitly includes vendored pathfinding code and licence. Tests
exercise interaction and unexpected map transitions using synthetic fields;
actual v1.01 event pointer/layout compatibility remains a live acceptance
requirement.
