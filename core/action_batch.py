"""Conservative, checkpoint-per-input reuse of vision navigation plans.

Model batches are permitted only in an explicitly observed overworld field.
Never batch menu confirmations, dialogue, battle turns, catches or saving.
A queued input is a separate ordinary player decision, with its own native
screen witness, incident handling, checkpoint and audit entry.
"""
import hashlib

MAX_BATCH = 10
MOVEMENT = frozenset(("UP", "DOWN", "LEFT", "RIGHT"))
FRAME_BYTES = 240 * 160 * 3


def digest(rgb):
    return hashlib.sha256(rgb).hexdigest()


def prepare(decision, source, *, battle=False, menu=False, field_witness=False):
    """Split a verified bounded field proposal into an initial input and queue.

    Refuse batching if a battle/menu is visible or neither the model nor the
    native/field-history controller corroborates a field. Vision-only ROMs
    are never allowed to batch battle turns.
    """
    actions = decision.get("actions")
    observed = decision.get("observation") or {}
    if not source.startswith("vision") or decision.get("review") or not isinstance(actions, list) or len(actions) <= 1:
        return decision, None
    safe_field = (not battle and not menu and isinstance(observed, dict)
                  and (observed.get("stage") == "field" or field_witness)
                  and len(actions) <= MAX_BATCH
                  and all(isinstance(a, dict) and a.get("button") in MOVEMENT
                          and type(a.get("frames")) is int and 1 <= a["frames"] <= 24
                          for a in actions))
    if not safe_field:
        # Unverified multi-action menus and battles must never be blindly
        # executed between observations. Verified native menus are unaffected.
        return {**decision, "actions": [dict(actions[0])]}, None
    queued = {
        "version": 1,
        "scene": decision["scene"][:240],
        "objective": decision["objective"][:240],
        "remaining": [dict(a) for a in actions[1:]],
        "expected_screen": None,
    }
    return {**decision, "actions": [dict(actions[0])]}, queued


def momentum(decision,source,history,*,field_witness=False,native_verified=False,battle=False,menu=False):
    """Expand a one-step field plan only after two witnessed forward steps.

    The inference is still one step at a time in unfamiliar/uncorroborated
    screens. With a credible field witness, two consecutive successful visual
    transitions in the same direction allow a *short* speculative continuation:
    at most 4 steps total with visual-only corroboration, or 10 with a
    verified native field. Every step is separately rechecked and checkpointed.
    """
    actions=decision.get("actions")
    if (not field_witness or battle or menu or not source.startswith("vision")
            or decision.get("review") or not isinstance(actions,list)
            or len(actions)!=1 or not isinstance(actions[0],dict)):
        return decision,None
    action=actions[0]
    button=action.get("button")
    if button not in MOVEMENT or type(action.get("frames")) is not int or not 8<=action["frames"]<=24:
        return decision,None
    if not isinstance(history,list) or len(history)<2:return decision,None
    recent=history[-2:]
    if any(not isinstance(h,dict) or h.get("before")==h.get("after")
           or not isinstance(h.get("actions"),list) or len(h["actions"])!=1
           or h["actions"][0].get("button")!=button
           or type(h["actions"][0].get("frames")) is not int
           or not 8<=h["actions"][0]["frames"]<=24 for h in recent):
        return decision,None
    limit=MAX_BATCH if native_verified else 4
    expanded={**decision,"actions":[dict(action) for _ in range(limit)]}
    return prepare(expanded,source,battle=battle,menu=menu,field_witness=True)


def frame_is_safe(before, after):
    """Fail closed on fades, popups, camera jumps or a stationary/blocked step.

    A sampling guard cannot prove that all overworld semantics stayed the same:
    it deliberately sacrifices batch length for safety when pixels are
    ambiguous. No UI, battle or irreversible action is ever queued.
    """
    if len(before) != FRAME_BYTES or len(after) != FRAME_BYTES:
        return False
    total = changed = bottom = bottom_changed = brightness = 0
    for y in range(0, 160, 4):
        for x in range(0, 240, 8):
            k = (y * 240 + x) * 3
            a = before[k:k+3]
            b = after[k:k+3]
            total += 1
            brightness += sum(b)
            different = sum(abs(a[c] - b[c]) for c in range(3)) >= 72
            changed += int(different)
            if y >= 108:
                bottom += 1
                bottom_changed += int(different)
    if not total or brightness < total * 30:
        return False
    # An unchanged picture means the planned movement may be blocked.
    if changed < max(2, total // 200):
        return False
    if changed * 100 > total * 24:
        return False
    if bottom and bottom_changed * 100 > bottom * 28:
        return False
    return True


def invalidate(meta):
    meta.pop("action_batch", None)


def take(meta, rgb, *, allowed):
    """Return one cached field input, or nothing if its witness became stale."""
    batch = meta.get("action_batch")
    if not batch:
        return None
    if (not allowed or not isinstance(batch, dict) or batch.get("version") != 1
            or batch.get("expected_screen") != digest(rgb)
            or not isinstance(batch.get("remaining"), list)
            or not batch["remaining"]):
        invalidate(meta)
        return None
    actions = batch["remaining"]
    action = actions.pop(0)
    if action.get("button") not in MOVEMENT or type(action.get("frames")) is not int or not 1 <= action["frames"] <= 24:
        invalidate(meta)
        return None
    if not actions:
        invalidate(meta)
    return {
        "scene": batch["scene"],
        "objective": batch["objective"],
        "actions": [dict(action)],
        "review": False,
    }


def observe(meta, before, after, *, field_ok=True, dialogue=False):
    """Run after each checkpointed input, before accepting its next plan step."""
    batch = meta.get("action_batch")
    if not batch:
        return False
    if not field_ok or dialogue or not frame_is_safe(before, after):
        invalidate(meta)
        return False
    batch["expected_screen"] = digest(after)
    return True
