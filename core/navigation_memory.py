"""Persistent, bounded action/outcome navigation memory for one local campaign.

Screens are opaque SHA-256 keys, not claimed map coordinates. Pixel changes are
only visual evidence; they NEVER count as verified native movement. All
automatic recovery requires a separate, safe field-context witness.
"""
import re

DIRECTIONS=("UP","DOWN","LEFT","RIGHT")
KEY=re.compile(r"[a-f0-9]{64}\Z")
MAX_STATES=64
MAX_EVENTS=96
MAX_RESCUES_PER_SCREEN=4


def valid_key(value):
    return isinstance(value,str) and KEY.fullmatch(value) is not None


def ledger(meta):
    v=meta.get("navigation_memory")
    if not isinstance(v,dict) or v.get("version")!=1 or not isinstance(v.get("states"),dict):
        v={"version":1,"states":{},"events":[]}
        meta["navigation_memory"]=v
    if not isinstance(v.get("events"),list):v["events"]=[]
    return v


def _state(meta,screen):
    if not valid_key(screen):return None
    v=ledger(meta);states=v["states"]
    node=states.pop(screen,{"attempts":{},"rescues":[]})
    if not isinstance(node,dict) or not isinstance(node.get("attempts"),dict):
        node={"attempts":{},"rescues":[]}
    if not isinstance(node.get("rescues"),list):node["rescues"]=[]
    states[screen]=node
    while len(states)>MAX_STATES:states.pop(next(iter(states)))
    return node


def record(meta,before,after,actions,*,safe_field):
    """Remember a completed, witnessed one-direction input and its result.

    safe_field is the *caller*-verified absence of battle, dialogue and menus.
    A changed LCD is never interpreted as an authoritative map movement.
    """
    if not safe_field or not valid_key(before) or not valid_key(after):
        return False
    if not isinstance(actions,list) or len(actions)!=1:return False
    action=actions[0]
    if not isinstance(action,dict) or action.get("button") not in DIRECTIONS:return False
    if type(action.get("frames")) is not int or not 1<=action["frames"]<=120:return False
    v=ledger(meta);state=_state(meta,before)
    direction=action["button"]
    pair=state["attempts"].get(direction,{"unchanged":0,"changed":0})
    if not isinstance(pair,dict):pair={"unchanged":0,"changed":0}
    kind="unchanged" if before==after else "changed"
    pair[kind]=min(1000,max(0,int(pair.get(kind,0)))+1)
    state["attempts"][direction]=pair
    v["events"].append({"from":before,"to":after,"direction":direction,"changed":before!=after})
    v["events"]=v["events"][-MAX_EVENTS:]
    return True


def recent_oscillation(history,screen):
    """Recognise genuine A->B->A reversals, not animation or random changes."""
    if not valid_key(screen) or not isinstance(history,list):return None
    rows=history[-10:]
    if len(rows)<6 or rows[-1].get("after")!=screen:return None
    seen={h.get("before") for h in rows}|{h.get("after") for h in rows}
    if len(seen)!=2 or not all(valid_key(k) for k in seen):return None
    for h in rows:
        a=h.get("actions")
        if not isinstance(a,list) or len(a)!=1 or not isinstance(a[0],dict) or a[0].get("button") not in DIRECTIONS:
            return None
        if h.get("before")==h.get("after"):return None
    if any(a.get("after")!=b.get("before") for a,b in zip(rows,rows[1:])):return None
    returning={h["actions"][0]["button"] for h in rows if h["before"]==screen}
    if len(returning)!=1:return None
    return next(iter(returning))


def blocked_directions(meta,screen,history):
    result=set()
    v=meta.get("navigation_memory")
    if isinstance(v,dict) and isinstance(v.get("states"),dict):
        node=v["states"].get(screen,{})
        if isinstance(node,dict):
            for direction,stats in node.get("attempts",{}).items():
                if (direction in DIRECTIONS and isinstance(stats,dict) and
                        stats.get("unchanged",0)>=1):
                    result.add(direction)
    # Check old checkpoint history too: no migration/restart required.
    for h in history[-40:]:
        if h.get("before")==screen and h.get("after")==screen:
            actions=h.get("actions",[])
            if len(actions)==1 and actions[0].get("button") in DIRECTIONS:
                result.add(actions[0]["button"])
    back=recent_oscillation(history,screen)
    if back:result.add(back)
    return result


def learned_context(meta,screen,history):
    blocked=blocked_directions(meta,screen,history)
    return {"visually_blocked":sorted(blocked),
            "two_screen_return":recent_oscillation(history,screen),
            "note":"LCD changes do not prove native movement; never interpret this as collision-map data"}


def propose(meta,screen,history,*,allowed,candidate=None):
    """One small, audited field recovery; no dialogues/menus/battles.

    The caller must corroborate a field context independently. No model can
    authorize these inputs solely with a string such as 'hospital_room'.
    """
    if not allowed or not valid_key(screen):return None
    blocked=blocked_directions(meta,screen,history)
    if not blocked:return None
    node=_state(meta,screen)
    rescued=node["rescues"]
    if len(rescued)>=MAX_RESCUES_PER_SCREEN:return None
    options=("LEFT","RIGHT","DOWN","UP") if recent_oscillation(history,screen) else ("DOWN","LEFT","RIGHT","UP")
    if candidate:
        try:
            from core.jj_fast import DIR
            field,_,occupied=candidate
            options=tuple(d for d in options
                if field.passable(field.pos[0]+DIR[d][0],field.pos[1]+DIR[d][1])
                and (field.pos[0]+DIR[d][0],field.pos[1]+DIR[d][1]) not in occupied)
        except (ValueError,TypeError,AttributeError,IndexError,KeyError):
            return None
    for direction in options:
        # Never test the exact direction that has just proved ineffective.
        if direction in blocked or direction in rescued:continue
        state=node["attempts"].get(direction,{})
        if state.get("unchanged",0)>0:continue
        rescued.append(direction)
        return {"scene":"field_recovery","objective":"Find a different route after a witnessed blocked step or reversal",
                "actions":[{"button":direction,"frames":16}],"review":False}
    return None


def unsafe_repeat(meta,screen,history,actions):
    if len(actions)!=1 or not isinstance(actions[0],dict):return False
    return actions[0].get("button") in blocked_directions(meta,screen,history)
