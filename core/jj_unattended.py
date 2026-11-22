"""Persistent bounded unattended recovery. No reset, game-memory writes or cheats."""
import hashlib
import json
from core.jj_fast import DIR, ordinary_dialogue
from core.live import LiveError
from core.jj_world_model import summary as world_summary
from core.jj_tile_memory import diagnostics as tile_diagnostics

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

def oscillation(history,screen):
    """Evidence of a repeated two-screen reversal, independent of AI labels.

    Return the controller direction which has repeatedly led *back* to the
    previous screenshot. Only completed, changed, cardinal single-step
    transitions count; animation flicker and self-loops are not sufficient.
    This evidence lives in the checkpoint's ordinary bounded history.
    """
    rows=history[-12:]
    if len(rows)<8 or rows[-1].get("after")!=screen:return None
    screens={row.get("after") for row in rows}
    if len(screens)!=2 or None in screens:return None
    if any(row.get("before") not in screens or row.get("before")==row.get("after")
           or len(row.get("actions",[]))!=1 or
           row["actions"][0].get("button") not in DIR
           for row in rows):
        return None
    # A genuine oscillation alternates a->b, b->a with no third position.
    if any(a.get("after")!=b.get("before") for a,b in zip(rows,rows[1:])):
        return None
    escaping=[row["actions"][0]["button"] for row in rows
              if row.get("before")==screen]
    if len(escaping)<3 or len(set(escaping))!=1:return None
    return {"screens":sorted(screens),"avoid_button":escaping[0],
            "repetitions":len(escaping)}


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
    if not loop or ordinary_dialogue(rgb):return None
    proof=meta.get("field_proof",{})
    has_native_motion=(isinstance(proof,dict) and isinstance(proof.get("callback"),int)
                       and len(set(proof.get("directions",[])))>=1)
    # The visual model can retain the last dialogue scene label long after
    # dialogue disappears. One independently verified native movement witness
    # plus a repeated two-screen directional oscillation is stronger evidence
    # for bounded field recovery than that stale AI label. Never use this to
    # confirm a dialogue, menu, battle, or unknown uncorroborated screen.
    if not (verified or field_hint(history)
            or (has_native_motion and oscillation(history,screen))):return None
    record=meta.setdefault("recovery",{"attempts":[],"screens":[]})
    if not set(record["screens"])&set(loop):
        record.update(attempts=[],screens=loop)
    else:record["screens"]=sorted(set(record["screens"]+loop))[-16:]
    if len(record["attempts"])>=8:return None
    recent=[a["button"] for x in history[-12:] if x.get("before") in loop for a in x.get("actions",[])]
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

def vision_stall(meta, field, *, limit=8):
    """Stop repeated expensive inference on any verified field map.

    Fail closed with a checkpoint/review rather than heat the host while
    vision repeatedly reverses ordinary movement. Native exploration does
    not consume this budget; a verified map crossing or acquired party
    clears the no-progress condition.
    """
    if not field:
        return False
    history=meta.get("history",[])
    if not isinstance(history,list):return False
    map_id=list(field[0].map_id)
    calls=0
    for row in reversed(history):
        if not isinstance(row,dict):break
        position=row.get("field_after")
        if not isinstance(position,dict) or position.get("map")!=map_id:break
        if row.get("source")=="native_explore":break
        # Dialogue, menus and battles are meaningful interactions rather
        # than aimless field navigation. Never exhaust a movement budget by
        # reading a story conversation or selecting a battle command.
        if row.get("observed_stage") in ("dialogue","menu","battle_command","battle_moves","party","bag"):
            break
        actions=row.get("actions",[])
        if str(row.get("source","")).startswith("vision") and (
                not isinstance(actions,list) or
                any(isinstance(a,dict) and a.get("button") in ("UP","DOWN","LEFT","RIGHT") for a in actions)):
            calls+=1
        if calls>=limit:return True
    return False


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
    # Carry only witnessed native outcomes into durable quest milestones.
    # Story text inferred by Qwen is a hypothesis, not a finished objective.
    book=meta.get("party_knowledge",{})
    outcomes=book.get("verified_outcomes",[]) if isinstance(book,dict) else []
    for row in outcomes[-16:]:
        if not isinstance(row,dict):continue
        evidence={"battle_win":"battle_win_observed",
                  "wild_capture":"capture_observed",
                  "healing":"healing_observed"}.get(row.get("kind"))
        if evidence and evidence not in q["milestones"]:q["milestones"].append(evidence)
    world=meta.get("world_model",{})
    if (isinstance(world,dict)
            and any(isinstance(r,dict) and r.get("result")=="native_verified"
                    for r in world.get("skill_outcomes",[]))
            and "native_exit_observed" not in q["milestones"]):
        q["milestones"].append("native_exit_observed")
    if obs and isinstance(obs.get("fact"),str) and obs["fact"]:
        q["fact"]=obs["fact"][:180]
        q["fact_source"]="model_hypothesis_not_a_verified_story_flag"
    if q.get("phase")=="obtain_initial_party":
        # A local recovery action must not replace the strategic objective.
        # Keep the observed starting Poké Ball as the target until native
        # party evidence confirms initial acquisition.
        q["task"]="Find the Poké Ball in the starting bedroom, approach it, face it and press A; verify a Pokémon is acquired."
        q["task_source"]="campaign_priority_pending_native_party_witness"
    elif isinstance(objective,str) and objective:
        q["task"]=objective[:240]
        q["task_source"]="planner_proposal"
    q["milestones"]=q["milestones"][-24:]
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
            "field_lock_probe":getattr(adapter,"lock_probe",None),
            "movement_witnesses":len(meta.get("field_proof",{}).get("directions",[])),
            "battle_callbacks":len(battles.callbacks),"battle_witnesses":len(meta.get("battle_proof",[])),
            "catalog":battles.catalog is not None,"inventory":battles.field_inventory,
            "bag_candidate":menus.bag_ok,"party_candidate":menus.party_ok,
            "event_probe":meta.get("native_event_probe"),
            "world":world_summary(meta),"tile_learning":tile_diagnostics(meta)}


def bootstrap(meta,candidate,screen):
    """Obtain native movement witnesses in a plausible field without model
    calls for every probe. Same map/callback capped at four ordinary moves."""
    if not candidate:return None
    history=meta.get("history",[])
    if not field_hint(history):
        # A ROM-verified native field is stronger evidence than repeated
        # hallucinated 'title_screen' labels. This only permits bounded
        # ordinary movement with Reader-validated map/player structures.
        last=history[-3:]
        stale_title=(len(last)==3
                     and all(h.get("scene","").lower() in ("title_screen","title") for h in last)
                     and any(a.get("button")=="START" for h in last for a in h.get("actions",[])))
        if not stale_title:return None
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
