"""Bounded native recovery and cumulative real gameplay measurements."""
from core.jj_fast import MAIN
from core.jj_battle import BATTLE_CB,FLAGS
from core.live import LiveError

NATIVE={"fast_dialogue","native_route","native_explore","native_battle","native_menu","native_battle_wait","field_recovery"}

def animation_wait(live,battles,battle,meta):
    # No button press, no assumed text advance. Only a validated battle
    # dispatcher immediately after an input we actually issued.
    if battle or BATTLE_CB not in battles.callbacks:return None
    if not meta.get("battle_proof"):return None
    history=meta.get("history",[])
    recent=0
    for h in reversed(history):
        if h.get("source")!="native_battle_wait":break
        recent+=1
    if recent>=2 or len(history)<=recent:return None
    last=history[-1-recent]
    if last.get("source") not in ("native_battle","native_menu"):return None
    if not any(a.get("button") in ("A","B") for a in last.get("actions",[])):return None
    try:
        if live.integer(MAIN+4,4)!=BATTLE_CB or live.integer(FLAGS,4) not in (4,12):return None
    except LiveError:return None
    return {"scene":"battle_transition","objective":"Allow native battle animation to complete","actions":[{"button":"WAIT","frames":120}],"review":False}

def record_field(meta,field,verified):
    if not field or not verified:return
    f=field[0]
    current={"map":list(f.map_id),"pos":list(f.pos)}
    previous=meta.get("last_native_field")
    if previous and previous["map"]!=current["map"]:
        edges=meta.setdefault("observed_field_transitions",[])
        edge={"from":previous["map"],"to":current["map"],"arrival":current["pos"]}
        if edge not in edges:edges.append(edge)
        meta["observed_field_transitions"]=edges[-100:]
    meta["last_native_field"]=current
    visits=meta.setdefault("visited_native_maps",[])
    if current["map"] not in visits:visits.append(current["map"])
    meta["visited_native_maps"]=visits[-300:]

def count_decision(meta,source,elapsed,model_seconds,frames):
    stats=meta.setdefault("engine_metrics",{"native":0,"model_calls":0,"other":0,"seconds":0.0,"model_seconds":0.0,"frames":0})
    stats["native" if source in NATIVE else "other"]+=1
    if model_seconds is not None:
        stats["model_calls"]+=1;stats["model_seconds"]+=round(max(0,model_seconds),3)
    stats["seconds"]+=round(max(0,elapsed),3)
    stats["frames"]+=frames
    return stats

def recovery_allowed(candidate,meta,verified):
    """After repeated non-progress on a known field, try an unvisited event.
    A new map or verified movement resets the per-map attempt budget.
    """
    if not candidate or not verified:return False
    h=meta.get("history",[])[-5:]
    if len(h)<5 or not all(x.get("source","").startswith("vision") for x in h):return False
    # Prefer exact native coordinate repetition to animated frame comparison.
    pos=list(candidate[0].pos);map_id=list(candidate[0].map_id)
    witnesses=[x for x in h if x.get("field_after")=={"map":map_id,"pos":pos}]
    return len(witnesses)>=4
