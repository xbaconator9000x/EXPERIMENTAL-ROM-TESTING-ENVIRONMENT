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

def script_settle(meta,screen,*,limit=32):
    """Advance only GBA time when field controls are script-locked.

    The caller first attempts a pixel-validated ordinary dialogue page.
    Unknown script screens are NEVER interpreted as overworld navigation.
    Repeated unchanged frames or too many waits fail closed for review,
    preserving the previous native checkpoint and avoiding repeated Qwen
    inferences against a control-locked scene. A live cutscene can move
    sprites and type multiple dialogue pages for longer than eight 24-frame
    waits; that is genuine screen progress, not an operator emergency.
    """
    state=meta.get("script_settle",{})
    if not isinstance(state,dict):state={}
    total=state.get("total",0)
    same=state.get("same_screen",0) if state.get("screen")==screen else 0
    if type(total) is not int or total<0:total=0
    if type(same) is not int or same<0:same=0
    if total>=limit or same>=3:
        return None
    meta["script_settle"]={"screen":screen,"total":total+1,
                           "same_screen":same+1}
    return {"scene":"native_script_settle",
            "objective":"Allow locked field script or transition to finish without walking",
            "actions":[{"button":"WAIT","frames":24}],"review":False}


def legacy_script_resume_candidate(meta):
    """Recognise one old checkpoint stranded after successful script recovery.

    A historical navigation-exhausted label alone is insufficient: require a
    recent actual A recovery and native text/script history on the same saved
    checkpoint. The current native field is checked again by the live caller.
    """
    if not isinstance(meta,dict) or meta.get("recovery_resume"):
        return False
    review=meta.get("review",{})
    if not isinstance(review,dict) or review.get("scene")!="native_navigation_exhausted":
        return False
    history=meta.get("history",[])
    if not isinstance(history,list):return False
    recent=[row for row in history[-12:] if isinstance(row,dict)]
    recovered=any(row.get("source")=="review_recovery" and
                 any(isinstance(a,dict) and a.get("button")=="A"
                     for a in row.get("actions",[]))
                 for row in recent)
    script_seen=any(row.get("source") in ("native_text",
                        "native_script_settle","fast_dialogue") for row in recent)
    diagnostics=meta.get("native_diagnostics",{})
    field_reason=(diagnostics.get("field_reason") if
                  isinstance(diagnostics,dict) else None)
    return recovered and script_seen and field_reason in (
        "FIELD_STRUCTURES_VALID","FIELD_STRUCTURES_VALID_STALE_SCRIPT_BYTE")


def rearm_after_script_recovery(meta,field,*,unlocked=False,visible_dialogue=False):
    """One-shot replan after *observed* dialogue completion.

    A visually changed page is not proof that the field has been unlocked.
    Keep the recovery pending until the native callback/map is readable,
    script control is released, and the dialogue panel is gone. Preserve the
    verified map/tile history; retire only the completed interaction's
    attempted-event and strategic-exhaustion budgets.
    """
    state=meta.get("recovery_resume")
    if not isinstance(state,dict) or state.get("kind")!="native_script_locked":
        return False
    if state.get("phase")!="pending" or not unlocked or visible_dialogue or not field:
        return False
    field_id=list(field[0].map_id)
    archive=meta.setdefault("prior_event_attempts",[])
    attempts=meta.get("event_attempts",[])
    if isinstance(archive,list) and isinstance(attempts,list) and attempts:
        archive.append({"reason":"new_script_epoch","attempts":attempts[-128:]})
        meta["prior_event_attempts"]=archive[-4:]
    meta["event_attempts"]=[]
    for key in ("event_goal","native_route","native_revisit",
                "field_strategic_referral","native_vision_budget",
                "exceptional_vision","bootstrap","stale_script_field"):
        meta.pop(key,None)
    # Existing world and tile observations remain authoritative; the
    # story interaction can change available exits without changing the map.
    objective=meta.get("objective_state")
    if isinstance(objective,dict) and objective.get("phase")=="explore_and_advance_story":
        task=objective.get("task","")
        if (not task or task.startswith(("Allow verified text printer",
                "Allow locked field script","Advance recognized ordinary dialogue",
                "Advance native-confirmed full-width dialogue",
                "Allow native auto-scroll text"))):
            objective["task"]="Find the next verified story interaction or map exit."
            objective["task_source"]="campaign_priority_after_dialogue"
    state.update(phase="calibrating",map=field_id)
    return True


def field_strategic_referral(meta,field,*,limit=2):
    """A rare strategic visual consult after 24 native event approaches.

    Only a verified map can use this counter. Each query opens another native
    sweep; visual commands are *never* accepted directly as field movement.
    After the last consult, the native navigator receives one more full
    sweep before a durable needs-review checkpoint.
    """
    if not field:return False
    key=[*field[0].map_id,meta.get("native_party_count")]
    state=meta.get("field_strategic_referral")
    if not isinstance(state,dict) or state.get("epoch")!=key:
        state={"epoch":key,"calls":0}
        meta["field_strategic_referral"]=state
    if type(state.get("calls")) is not int or not 0<=state["calls"]<limit:
        return False
    state["calls"]+=1
    return True


def exceptional_vision(meta,field,reason,*,battle=False,menu=False,dialogue=False,limit=1):
    """Allow vision only for an unknown scene, never an admitted field.

    A verified native scene must use event/path/field logic. Real battles,
    menus and text overlays may require separate screen classification.
    After a previously verified field disappears, just one exceptional
    inference is permitted per map/party and failure reason until new native
    evidence appears. Changing screenshot pixels cannot replenish calls.
    """
    if battle or menu or dialogue:
        return True
    if field is not None:
        return False
    previous=meta.get("last_native_field")
    if not isinstance(previous,dict) or not isinstance(previous.get("map"),list):
        # Title/intro before the first valid field is a true unknown stage.
        return True
    key={"map":previous["map"],"party_count":meta.get("native_party_count"),
         "field_reason":reason}
    state=meta.get("exceptional_vision")
    if not isinstance(state,dict) or any(state.get(k)!=v for k,v in key.items()):
        state=dict(key,calls=0)
        meta["exceptional_vision"]=state
    if type(state.get("calls")) is not int or not 0<=state["calls"]<limit:
        return False
    state["calls"]+=1
    return True


def native_vision_budget(meta,field,*,limit=3):
    """Cap expensive field vision when verified native skills run out.

    The counter is per native map and independently validated party count.
    Model-directed movement on the same map never renews its allowance.
    """
    f=field[0]
    identity={"map":list(f.map_id),"party_count":meta.get("native_party_count")}
    state=meta.get("native_vision_budget")
    if not isinstance(state,dict) or any(state.get(k)!=v for k,v in identity.items()):
        state=dict(identity,calls=0)
        meta["native_vision_budget"]=state
    if type(state.get("calls")) is not int or state["calls"]<0:
        state["calls"]=limit
    if state["calls"]>=limit:return False
    state["calls"]+=1
    return True


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


TACTICAL_OBJECTIVES=(
    "Allow locked field script",
    "Allow verified text printer",
    "Advance native-confirmed full-width dialogue",
    "Escape repeated field cycle",
    "Survey a new native-verified walkable tile",
    "Approach observed warp",
    "Walk onto observed trigger",
    "Travel toward observed connection",
    "Interact with observed map event",
    "Re-enter previously attempted native trigger",
    "Native-validated last-resort visual step",
    "Resume native navigation after strategic visual consultation",
    "Verify native field coordinates with ordinary movement",
    "Allow native battle animation to complete",
    "Wait for blank-screen animation",
    "Advance recognized ordinary dialogue page",
)


def quest_state(meta,field,party,obs=None,objective=None):
    """Keep a persistent goal above individual actions; only native facts
    can mark acquisition/transition milestones. Model facts stay hypotheses."""
    q=meta.setdefault("objective_state",{"phase":"obtain_initial_party","milestones":[],"task":"","fact":""})
    old_phase=q.get("phase")
    if isinstance(party,list) and party:
        # Previously attempted warps/NPCs can become available when the team
        # changes. Keep a bounded audit of attempts, then give the native
        # explorer a fresh attempt epoch. Also migrates old pre-party saves.
        previous_count=meta.get("event_attempt_party_count")
        if previous_count!=len(party):
            old=meta.get("event_attempts",[])
            if isinstance(old,list) and old:
                archive=meta.setdefault("prior_event_attempts",[])
                archive.append({"party_count":previous_count,
                                "attempts":old[-128:]})
                meta["prior_event_attempts"]=archive[-4:]
            meta["event_attempts"]=[]
            meta["event_attempt_party_count"]=len(party)
            meta.pop("starter_event_retry",None)
            meta.pop("event_goal",None)
        if "party_observed" not in q["milestones"]:q["milestones"].append("party_observed")
        healthy=[p for p in party if p["hp"]>0]
        if not healthy or max(p["hp"]/p["max_hp"] for p in healthy)<.25:q["phase"]="restore_party_health"
        elif q["phase"] in ("obtain_initial_party","restore_party_health"):q["phase"]="explore_and_advance_story"
    if (old_phase=="obtain_initial_party"
            and q.get("phase")=="explore_and_advance_story"):
        # Verified Pokémon acquisition retires the starter goal immediately.
        # Do not wait for a tactical action to overwrite it on a later turn.
        q["task"]="Find the next verified story interaction or map exit."
        q["task_source"]="campaign_priority_after_party"
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
        # Route steps, menu actions, idle waits, field calibration and scout
        # instructions are transient skills, NEVER durable story goals.
        # An older checkpoint may already contain one: repair it in place.
        current=q.get("task","")
        if (q.get("phase")=="explore_and_advance_story"
                and objective.startswith(TACTICAL_OBJECTIVES)):
            if (not isinstance(current,str) or not current
                    or current.startswith(TACTICAL_OBJECTIVES)
                    or "Poké Ball in the starting bedroom" in current):
                q["task"]="Find the next verified story interaction or map exit."
                q["task_source"]="campaign_priority_after_party"
        else:
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
            "script_settle":meta.get("script_settle"),
            "movement_witnesses":len(meta.get("field_proof",{}).get("directions",[])),
            "battle_callbacks":len(battles.callbacks),"battle_witnesses":len(meta.get("battle_proof",[])),
            "catalog":battles.catalog is not None,"inventory":battles.field_inventory,
            "bag_candidate":menus.bag_ok,"party_candidate":menus.party_ok,
            "event_probe":meta.get("native_event_probe"),
            "rom_hack_map_compat":meta.get("rom_hack_map_compat"),
            "native_text_probe":meta.get("native_text_probe"),
            "rom_hack_event_data":meta.get("rom_hack_event_data"),
            "last_observed_event_data_delta":meta.get("last_observed_event_data_delta"),
            "event_witnesses":meta.get("native_event_witnesses",[])[-3:],
            "native_retry":{k:v for k,v in meta.get("native_revisit",{}).items()
                 if k in ("epoch","approaches","sweeps","status")},
            "strategic_referral":meta.get("field_strategic_referral"),
            "native_vision_budget":meta.get("native_vision_budget"),
            "native_scout":{k:{"moves":v.get("moves"),"visited":len(v.get("visited",[])),
                              "status":v.get("status")}
                for k,v in meta.get("native_scout",{}).get("maps",{}).items()
                if isinstance(v,dict)},
            "world":world_summary(meta),"tile_learning":tile_diagnostics(meta)}


def bootstrap(meta,candidate,screen,*,post_dialogue=False):
    """Obtain native movement witnesses in a plausible field without a model.

    Post-dialogue calibration is gated by a structurally readable native field
    and independently observed script release. Ordinary bootstrap still needs
    the prior field/title witness. At most four inputs per callback and map.
    """
    if not candidate:return None
    if post_dialogue:
        pending=meta.get("recovery_resume",{})
        if (not isinstance(pending,dict) or
                pending.get("phase")!="calibrating" or
                pending.get("map")!=list(candidate[0].map_id)):
            return None
    history=meta.get("history",[])
    if not post_dialogue and not field_hint(history):
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
        action={"button":d,"frames":16 if post_dialogue else 1}
        if quarantined(meta,screen,[action]):continue
        tried.append(d)
        return {"scene":"field_calibration","objective":"Verify native field coordinates with ordinary movement","actions":[action],"review":False}
    return None