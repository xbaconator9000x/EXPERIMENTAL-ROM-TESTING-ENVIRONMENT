# Upstream queue and Jessie & James integration
The existing v1 queue remains unchanged by default. A private issue with title
`[ROM-PLAY upstream v2]` and body `{"version":2,"sha256":"<exact vanilla LeafGreen digest>","goal":"..."}`
is explicitly admitted only if the controller is started with
`--upstream-checkout <clean pinned clone>`. The separate checkpoint is
`upstream-progress.bin`; the dashboard reads it and displays actual upstream
skills, and the existing private reporting function sends bounded evidence.
Switching an existing goal between engines is deliberately blocked.
The full upstream skill dispatcher is still vanilla LeafGreen only; shopping
still requires a read-only redesign. Do not install the branch as a complete
replacement until native acceptance.

The exact Jessie & James Classic battle adapter now directly uses the
upstream Gen III type chart and the upstream move-effect classification
(`knowledge/move_semantics.py`, extracted classification only) and
`knowledge/move_effects.py` from 594bfc7e3c208890c248269b67c5a1cf95074965. Numeric effect IDs come from
pret/pokefirered at ce6406d8c2eaf46d543c8a2606de0c3cb1951982.
Name and actual local effect byte must agree before using the classification.
Avoid suicide and reactive/conditional moves and risky capture moves; prefer
upstream catch setup order when a legal move is observed. Existing live
callback, ROM hash, visual witnesses, and native stats remain required. This
is a bounded adaptation, not full upstream story compatibility or proof of
successful catching. Real physical-host acceptance remains mandatory.
