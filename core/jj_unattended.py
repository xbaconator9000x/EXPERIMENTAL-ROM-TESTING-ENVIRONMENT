"""Persistent bounded unattended recovery. No reset, game-memory writes or cheats."""
import hashlib
import json
from core.jj_fast import DIR, ordinary_dialogue
from core.live import LiveError

VERSION=1
def action_id(actions):
    return hashlib.sha256(json.dumps(actions,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def cycle(history,screen):
    """Detect exact repeating transitions including movement loops."""
    h=history[-12:]
    for n in (12,8,6):
        rows=h[-n:]
        if len(rows)<n:continue
        screens={x.get("after") for x in rows}
        if screen in screens and None not in screens and len(screens)<=2:return sorted(screens)
    return []

def field_hint(history):
    if not history:return False
    row=history[-1]
    if row.get("observed_stage")=="field":return True
    if row.get("observed_stage") in ("dialogue","menu","bag","party","battle_command","battle_moves","title"):return False
    scene=row.get("scene","").lower()
    return any(x in scene for x in ("overworld","bedroom","hospital_room","field","route","town","city","map_exploration"))

def recovery(meta,screen,rgb,candidate=None,verified=False):
    """Try distinctly different directional actions in a recognized field.
    Never select menus or confirm choices blindly. Bound attempts across a loop.
    """
    history=meta.get("history",[])
    loop=cycle(history,screen)
    if not loop or ordinary_dialogue(rgb) or not (verified or field_hint(history)):return None
    record=meta.setdefault("recovery",{"attempts":[],"screens":[]})
    if not set(record["screens"])&set(loop):
        record.update(attempts=[],screens=loop)
    else:record["screens"]=sorted(set(record["screens"]+loop))[-16:]
    if len(record["attempts"])>=8:return None
    recent=[a["button"] for x in history[-12:] if x.get("before")==screen for a in x.get("actions",[])]
    tried={a["button"] for a in record["attempts"]}
    directions=list(DIR)
    if candidate:
        f,_,occupied=candidate
        available=[d for d,(dx,dy) in DIR.items() if f.passable(f.pos[0]+dx,f.pos[1]+dy) and (f.pos[0]+dx,f.pos[1]+dy) not in occupied]
        if available:directions=available
    # Prefer a different direction over a different duration of the same move.
    choices=sorted(((d,n) for d in directions for n in (16,32)),key=lambda p:(p[0] in tried,p[0] in recent,p[1],p[0]))
    for d,n in choices:
        a={"button":d,"frames":n}
        if a in record["attempts"] or quarantined(meta,screen,[a]):continue
        record["attempts"].append(a)
        return {"scene":"field_recovery","objective":"Escape repeated field cycle using an untried direction","actions":[a],"review":False}
    return None

def quarantine(meta,screen,actions):
    key={"screen":screen,"action":action_id(actions)}
    rows=meta.setdefault("failed_inputs",[])
    if key not in rows:rows.append(key)
    meta["failed_inputs"]=rows[-32:]

def quarantined(meta,screen,actions):
    return {"screen":screen,"action":action_id(actions)} in meta.get("failed_inputs",[])

def alternative(meta,screen,candidate,history):
    # For suspected crashes, choose an untried directional action only in
    # field context; outside field defer to model or authenticated guidance.
    if not candidate and not field_hint(history):return None
    valid=list(DIR)
    if candidate:
        f,_,occupied=candidate
        valid=[d for d,(dx,dy) in DIR.items() if f.passable(f.pos[0]+dx,f.pos[1]+dy) and (f.pos[0]+dx,f.pos[1]+dy) not in occupied]
    for d in valid:
        a=[{"button":d,"frames":16}]
        if not quarantined(meta,screen,a):return a
    return None

def quest_state(meta,field,party,obs=None,objective=None):
    """Keep a persistent goal above individual actions; only native facts
    can mark acquisition/transition milestones. Model facts stay hypotheses."""
    q=meta.setdefault("objective_state",{"phase":"obtain_initial_party","milestones":[],"task":"","fact":""})
    if isinstance(party,list) and party:
        if "party_observed" not in q["milestones"]:q["milestones"].append("party_observed")
        healthy=[p for p in party if p["hp"]>0]
        if not healthy or max(p["hp"]/p["max_hp"] for p in healthy)<.25:q["phase"]="restore_party_health"
        elif q["phase"] in ("obtain_initial_party","restore_party_health"):q["phase"]="explore_and_advance_story"
    if field and meta.get("observed_field_transitions") and "map_transition_observed" not in q["milestones"]:
        q["milestones"].append("map_transition_observed")
    if obs and obs.get("fact"):
        q["fact"]=obs["fact"][:180]
    if objective:q["task"]=objective[:240]
    return q

def replay(open_live,state,actions,settle,buttons):
    """Independent emulator process, same pre-action checkpoint. Return
    result on success; report repeat failure separately from setup failure."""
    probe=None
    try:
        probe=open_live(state)
    except (LiveError,OSError,ValueError):return "REPLAY_SETUP_FAILED",None
    try:
        for a in actions:
            probe.step(buttons[a["button"]],a["frames"]);probe.step(0,settle)
        return "REPLAY_SUCCEEDED",(probe.save_state(),probe.rgb())
    except (LiveError,OSError):return "REPLAY_FAILED",None
    finally:
        try:probe.close()
        except (OSError,LiveError):pass

def diagnostic(adapter,battles,menus,field,meta):
    return {"version":VERSION,"field_rom":adapter.admitted,"field_candidate":bool(field),
            "field_verified":adapter.verified_field(field,meta),
            "field_reason":getattr(adapter,"reason","unknown"),
            "movement_witnesses":len(meta.get("field_proof",{}).get("directions",[])),
            "battle_callbacks":len(battles.callbacks),"battle_witnesses":len(meta.get("battle_proof",[])),
            "catalog":battles.catalog is not None,"inventory":battles.field_inventory,
            "bag_candidate":menus.bag_ok,"party_candidate":menus.party_ok}


def bootstrap(meta,candidate,screen):
    """Obtain native movement witnesses in a plausible field without model
    calls for every probe. Same map/callback capped at four ordinary moves."""
    if not candidate or not field_hint(meta.get("history",[])):return None
    f,cb,occupied=candidate
    previous=meta.get("field_proof",{}).get("directions",[])
    key=str(cb)+":"+":".join(map(str,f.map_id))
    ledger=meta.setdefault("bootstrap",{})
    tried=ledger.setdefault(key,[])
    if len(tried)>=4:return None
    if len(ledger)>32:
        for k in list(ledger)[:-32]:ledger.pop(k,None)
    for d,(dx,dy) in DIR.items():
        p=(f.pos[0]+dx,f.pos[1]+dy)
        if d in previous or d in tried or p in occupied or not f.passable(*p):continue
        action={"button":d,"frames":1}
        if quarantined(meta,screen,[action]):continue
        tried.append(d)
        return {"scene":"field_calibration","objective":"Verify native field coordinates with ordinary movement","actions":[action],"review":False}
    return None
