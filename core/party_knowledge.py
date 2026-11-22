"""Enduring, read-only party and tactical memory for native Pokémon gameplay.

Facts are admitted only from a checksum-validated native party (with an
independent party-count witness) or a separately corroborated battle callback.
Exact-ROM move/species tables describe *base* data, never current status or PP.
No cached tactical preference is permission to send unobserved battle inputs.
"""
import hashlib
import json

from core.upstream_battle import classic_multiplier, safe_damage_kind

MAX_EVENTS=32
MAX_BATTLE_EVENTS=16
BALL_IDS=frozenset((2,3,4))
HEAL_IDS=frozenset((13,19,20,21,22))
ATTACK_TYPES=("normal","fire","water","electric","grass","ice","fighting","poison",
              "ground","flying","psychic","bug","rock","ghost","dragon","dark","steel")


def _int(value,low,high):
    return type(value) is int and low<=value<=high


def valid_party(party):
    """A last line of defence beyond the native reader's own checksum."""
    if type(party) is not list or len(party)>6:return False
    seen=set()
    for m in party:
        if type(m) is not dict or not all(k in m for k in
                ("slot","species_id","level","hp","max_hp","moves","pp","status")):
            return False
        slot=m["slot"]
        if not (_int(slot,0,5) and slot not in seen
                and _int(m["species_id"],1,411)
                and _int(m["level"],1,100)
                and _int(m["max_hp"],1,999)
                and _int(m["hp"],0,m["max_hp"])
                and _int(m["status"],0,0xffffffff)):
            return False
        seen.add(slot)
        if (type(m["moves"]) is not list or len(m["moves"])!=4
                or type(m["pp"]) is not list or len(m["pp"])!=4):
            return False
        for mid,pp in zip(m["moves"],m["pp"]):
            if not _int(mid,0,559) or not _int(pp,0,64):
                return False
            if mid==0 and pp:return False
    return True


def _known_species(catalog,species):
    row=getattr(catalog,"species_ids",{}).get(species) if catalog else None
    if not isinstance(row,dict):return None
    types=row.get("types")
    if (type(row.get("name")) is not str or type(types) is not list
            or not 1<=len(types)<=2
            or any(t not in ATTACK_TYPES for t in types)):
        return None
    return {"name":row["name"],"types":list(types)}


def _known_move(catalog,mid):
    row=getattr(catalog,"move_ids",{}).get(mid) if catalog and mid else None
    if not isinstance(row,dict) or not isinstance(row.get("name"),str):
        return None
    if row.get("type") not in ATTACK_TYPES:return None
    if not _int(row.get("power"),0,250) or not _int(row.get("accuracy"),1,100):
        return None
    # Do not infer modified move effects merely from an unchanged name.
    result={k:row[k] for k in ("name","type","power","accuracy")}
    if _int(row.get("effect"),0,255):result["effect"]=row["effect"]
    return result


def summarize_member(member,catalog):
    species=_known_species(catalog,member["species_id"])
    moves=[]
    for slot,(mid,pp) in enumerate(zip(member["moves"],member["pp"])):
        if not mid:continue
        row={"slot":slot,"id":mid,"pp":pp}
        info=_known_move(catalog,mid)
        if info:row.update(info)
        else:row["unresolved_rom_move"]=True
        moves.append(row)
    return {"slot":member["slot"],"species_id":member["species_id"],
            "level":member["level"],"hp":member["hp"],"max_hp":member["max_hp"],
            "status":member["status"],"species":species,"moves":moves}


def _safe_bag(bag):
    if type(bag) is not dict:return None
    result={}
    for pocket,allowed in (("balls",BALL_IDS),("items",HEAL_IDS)):
        rows=bag.get(pocket)
        if type(rows) is not list:return None
        checked=[]
        for item in rows:
            if (type(item) is not dict or not _int(item.get("id"),1,376)
                    or not _int(item.get("count"),1,999)):
                return None
            if item["id"] in allowed:
                checked.append({"id":item["id"],"count":item["count"]})
        result[pocket]=checked[:16]
    return result


def observe_party(meta,party,catalog=None,*,decision,bag=None):
    """Update authoritative current party; invalid probes cannot erase it."""
    if not valid_party(party) or not _int(decision,0,10000000):return False
    current={"decision":decision,"witness":"native_checksum_and_party_count",
             "members":[summarize_member(m,catalog) for m in sorted(party,key=lambda x:x["slot"])]}
    inventory=_safe_bag(bag)
    if inventory is not None:current["bag"]=inventory
    prior=meta.get("party_knowledge",{})
    if not isinstance(prior,dict) or prior.get("version")!=1:
        prior={"version":1,"events":[],"current":{}}
    previous=prior.get("current",{})
    events=list(prior.get("events",[]))[-MAX_EVENTS:]
    old_members={m["slot"]:m for m in previous.get("members",[])
                 if isinstance(m,dict) and "slot" in m}
    for member in current["members"]:
        old=old_members.get(member["slot"])
        if old is None or old.get("species_id")!=member["species_id"]:
            events.append({"decision":decision,"kind":"party_slot",
                           "slot":member["slot"],"species_id":member["species_id"]})
        elif {m["id"] for m in old.get("moves",[])}!={m["id"] for m in member["moves"]}:
            events.append({"decision":decision,"kind":"move_change","slot":member["slot"]})
    # A removed member is not automatically counted as fainted, lost or released.
    if len(current["members"])<len(old_members):
        events.append({"decision":decision,"kind":"roster_shrank"})
    if inventory is None and "bag" in previous:
        # Last observed quantities may be stale: label them as such and
        # NEVER use them to authorize a new bag action.
        current["last_known_bag"]=previous.get("bag")
    prior["events"]=events[-MAX_EVENTS:]
    prior["current"]=current
    meta["party_knowledge"]=prior
    return True


def _type_matchups(types):
    if not types:return None
    result={}
    for move_type in ATTACK_TYPES:
        mult=classic_multiplier(move_type,types)
        if mult is not None and mult!=1.0:result[move_type]=mult
    return result


def battle_advice(state,catalog):
    """Human-readable, NON-AUTHORISING battle strategy from a fresh witness."""
    if type(state) is not dict or not isinstance(state.get("own"),dict) or not isinstance(state.get("enemy"),dict):
        return None
    own,enemy=state["own"],state["enemy"]
    if (type(own.get("moves")) is not list or len(own["moves"])!=4
            or type(own.get("pp")) is not list or len(own["pp"])!=4
            or type(enemy.get("types")) is not list
            or not 1<=len(enemy["types"])<=2
            or any(t not in ATTACK_TYPES for t in enemy["types"])):
        return None
    ranked=[]
    for slot,(mid,pp) in enumerate(zip(own["moves"],own["pp"])):
        if not _int(mid,0,559) or not _int(pp,0,64) or not mid:continue
        row=_known_move(catalog,mid)
        if not row:continue
        effect=classic_multiplier(row["type"],enemy["types"])
        if effect is None:continue
        kind=safe_damage_kind(row,enemy.get("status",0),capture=False)
        # An actual hacked move may have an unknown effect; never recommend
        # it as a deterministic attack just because its name seems familiar.
        if "effect" not in row:kind=None
        ranked.append({"slot":slot,"id":mid,"name":row["name"],
                       "pp":pp,"type":row["type"],"power":row["power"],
                       "accuracy":row["accuracy"],"effectiveness":effect,
                       "safe_effect_verified":kind is not None})
    capture_plan=capture_preference(state.get("party"),enemy,catalog,state.get("bag"),wild=state.get("wild",False))
    return {"capture_preference":capture_plan,"enemy_species":enemy.get("species"),"enemy_types":list(enemy["types"]),
            "enemy_hp":enemy.get("hp"),"enemy_max_hp":enemy.get("max_hp"),
            "enemy_status":enemy.get("status"),
            "own_species":own.get("species"),"own_hp":own.get("hp"),
            "moves":ranked,"incoming_type_matchups":_type_matchups(own.get("types",[]))}


def observe_battle(meta,state,catalog,*,decision):
    """Never remember a battle candidate without its visual callback proof."""
    if not isinstance(state,dict) or state.get("callback") not in meta.get("battle_proof",[]):
        return False
    if not _int(decision,0,10000000):return False
    advice=battle_advice(state,catalog)
    if advice is None:return False
    token=[state.get("callback"),state.get("cursor"),state.get("disabled"),
           advice["enemy_species"],advice["enemy_hp"],advice["enemy_status"],
           advice["own_species"],advice["own_hp"],
           [(m["id"],m["pp"]) for m in advice["moves"]]]
    signature=hashlib.sha256(json.dumps(token,separators=(",",":")).encode()).hexdigest()
    previous=meta.get("battle_knowledge",{})
    history=list(previous.get("events",[]))[-MAX_BATTLE_EVENTS:] if isinstance(previous,dict) else []
    if not isinstance(previous,dict) or previous.get("signature")!=signature:
        history.append({"decision":decision,"kind":"battle_state_changed",
                        "enemy":advice["enemy_species"]})
    meta["battle_knowledge"]={"version":1,"decision":decision,
        "witness":"visually_corroborated_native_callback","signature":signature,
        "current":advice,"events":history[-MAX_BATTLE_EVENTS:]}
    return True


def party_coverage(meta):
    """Classic type coverage inferred only from exact-ROM species/move IDs.

    This is a team-planning summary, not a forecast of incoming damage:
    abilities, weather, actual movesets and hack-specific effects may differ.
    """
    data=meta.get("party_knowledge",{})
    current=data.get("current",{}) if isinstance(data,dict) else {}
    members=current.get("members",[]) if isinstance(current,dict) else []
    alive=[m for m in members if isinstance(m,dict) and m.get("hp",0)>0]
    if not alive:return None
    typed=[]
    offensive=set()
    for m in alive:
        info=m.get("species")
        if not isinstance(info,dict) or not isinstance(info.get("types"),list):
            return {"coverage_verified":False,"reason":"incomplete_species_typing"}
        types=info["types"]
        if not types or any(t not in ATTACK_TYPES for t in types):
            return {"coverage_verified":False,"reason":"unknown_species_typing"}
        typed.append(types)
        for move in m.get("moves",[]):
            if (isinstance(move,dict) and move.get("type") in ATTACK_TYPES
                    and _int(move.get("power"),1,250)
                    and _int(move.get("pp"),1,64)
                    and _int(move.get("effect"),0,255)
                    and safe_damage_kind(move,0,False) is not None):
                offensive.add(move["type"])
    pressures=[]
    for attack in ATTACK_TYPES:
        multipliers=[classic_multiplier(attack,ts) for ts in typed]
        if any(x is None for x in multipliers):continue
        weak=sum(x>1 for x in multipliers)
        resists=sum(x<1 for x in multipliers)
        if weak:
            pressures.append({"attack_type":attack,"weak_members":weak,
                              "resisting_members":resists})
    pressures.sort(key=lambda x:(-x["weak_members"],x["resisting_members"],x["attack_type"]))
    return {"coverage_verified":True,
            "party_types":sorted({t for group in typed for t in group}),
            "currently_usable_damaging_types":sorted(offensive),
            "defensive_pressures":pressures[:8],
            "warning":"Type chart only. Actual damage, abilities, weather and modified moves are not predicted."}


def retain_verified_outcomes(meta):
    """Copy only actual acceptance-ledger milestones into durable experience.

    A party slot change, model speculation, or battle callback alone cannot
    count as a battle win or capture; NativeAcceptance supplies those proofs.
    """
    evidence=meta.get("native_acceptance")
    if not isinstance(evidence,dict) or not evidence.get("profile_admitted"):
        return 0
    events=evidence.get("events",[])
    if not isinstance(events,list):return 0
    book=meta.get("party_knowledge")
    if not isinstance(book,dict) or book.get("version")!=1:
        book={"version":1,"events":[],"current":{}}
        meta["party_knowledge"]=book
    known=list(book.get("verified_outcomes",[]))[-24:]
    existing={(x.get("kind"),x.get("decision"),x.get("before"),x.get("after"))
              for x in known if isinstance(x,dict)}
    added=0
    for e in events:
        if not isinstance(e,dict) or e.get("kind") not in ("battle_win","wild_capture","healing"):
            continue
        if not _int(e.get("decision"),0,10000000):
            continue
        before,after=e.get("before"),e.get("after")
        if not (isinstance(before,str) and isinstance(after,str)
                and len(before)==64 and len(after)==64):
            continue
        key=(e["kind"],e["decision"],before,after)
        if key in existing:continue
        row={"kind":e["kind"],"decision":e["decision"],"before":before,"after":after}
        detail=e.get("detail")
        if isinstance(detail,dict):
            if e["kind"]=="wild_capture" and _int(detail.get("species"),1,411):
                row["species_id"]=detail["species"]
            if e["kind"]=="healing" and _int(detail.get("slot"),0,5):
                row["slot"]=detail["slot"]
        known.append(row);existing.add(key);added+=1
    book["verified_outcomes"]=known[-24:]
    return added


def knowledge_context(meta):
    """Small bounded prompt note. Never substitute it for live HP/PP or cursor."""
    data=meta.get("party_knowledge")
    if not isinstance(data,dict) or data.get("version")!=1:return None
    current=data.get("current")
    if not isinstance(current,dict):return None
    roster=[]
    for m in current.get("members",[])[:6]:
        if not isinstance(m,dict):continue
        row={"slot":m["slot"],"species_id":m["species_id"],
             "name":m.get("species",{}).get("name") if m.get("species") else None,
             "types":m.get("species",{}).get("types") if m.get("species") else None,
             "level":m["level"],"last_hp":m["hp"],"max_hp":m["max_hp"],
             "moves":[{k:x[k] for k in ("slot","name","type","power","pp") if k in x}
                      for x in m.get("moves",[])[:4]]}
        roster.append(row)
    return {"last_verified_decision":current.get("decision"),
            "party":roster,"coverage":party_coverage(meta),
            "verified_outcomes":[{k:x[k] for k in ("kind","decision","species_id","slot") if k in x}
                for x in data.get("verified_outcomes",[])[-6:] if isinstance(x,dict)],
            "warning":"Historical party knowledge; never trust remembered PP/HP/menus for controller actions."}


def capture_preference(party,enemy,catalog,bag,*,wild=True):
    """Conservative roster-building intent, not a raw throw command."""
    if not wild:return {"eligible":False,"reason":"trainer_battle"}
    if not valid_party(party):return {"eligible":False,"reason":"unverified_party"}
    if not isinstance(enemy,dict) or not _int(enemy.get("species"),1,411):
        return {"eligible":False,"reason":"unverified_enemy"}
    if len(party)>=6:return {"eligible":False,"reason":"full_party"}
    if any(m["species_id"]==enemy["species"] for m in party):
        return {"eligible":False,"reason":"duplicate_species"}
    balls=_safe_bag(bag)
    if balls is None:return {"eligible":False,"reason":"unverified_bag"}
    available=sum(x["count"] for x in balls["balls"])
    if not available:return {"eligible":False,"reason":"no_balls"}
    if len(party)<3:
        return {"eligible":True,"reason":"build_initial_team"}
    # After the initial team, catch only for confirmed offensive/defensive
    # type diversity, with a reserve of balls for future encounters.
    if available<3:return {"eligible":False,"reason":"reserve_balls"}
    target=_known_species(catalog,enemy["species"])
    current=[_known_species(catalog,m["species_id"]) for m in party]
    if target is None or any(x is None for x in current):
        return {"eligible":False,"reason":"unknown_type_coverage"}
    if (isinstance(enemy.get("types"),list) and set(enemy["types"])!=set(target["types"])):
        return {"eligible":False,"reason":"changed_or_conflicting_types"}
    current_types={t for mon in current for t in mon["types"]}
    novel=set(target["types"])-current_types
    return {"eligible":bool(novel),"reason":"new_type_coverage" if novel else "redundant_type_coverage",
            "new_types":sorted(novel)}
