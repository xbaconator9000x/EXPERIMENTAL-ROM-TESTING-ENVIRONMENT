"""Pokémon gameplay policies using only observed information and ordinary inputs.

Vision observations are hypotheses, not a trusted memory map. Deterministic
rules choose bounded menu/navigation actions; every subsequent screen is
re-observed. No ROM-specific RAM guesses, memory writes, or fixed story route.
"""
from collections import deque
import re

TYPES=set("normal fire water electric grass ice fighting poison ground flying psychic bug rock ghost dragon dark steel fairy".split())
# Type attack multipliers. Fairy and post-Gen-V Steel rules are Modern-only.
SUPER={
"fire":"grass ice bug steel","water":"fire ground rock","electric":"water flying","grass":"water ground rock","ice":"grass ground flying dragon",
"fighting":"normal ice rock dark steel","poison":"grass fairy","ground":"fire electric poison rock steel","flying":"grass fighting bug",
"psychic":"fighting poison","bug":"grass psychic dark","rock":"fire ice flying bug","ghost":"psychic ghost","dragon":"dragon",
"dark":"psychic ghost","steel":"ice rock fairy","fairy":"fighting dragon dark"}
RESIST={
"normal":"rock steel","fire":"fire water rock dragon","water":"water grass dragon","electric":"electric grass dragon","grass":"fire grass poison flying bug dragon steel",
"ice":"fire water ice steel","fighting":"poison flying psychic bug fairy","poison":"poison ground rock ghost","ground":"grass bug","flying":"electric rock steel",
"psychic":"psychic steel","bug":"fire fighting poison flying ghost steel fairy","rock":"fighting ground steel","ghost":"dark","dragon":"steel",
"dark":"fighting dark fairy","steel":"fire water electric steel","fairy":"fire poison steel"}
IMMUNE={"normal":"ghost","electric":"ground","fighting":"ghost","poison":"steel","ground":"flying","psychic":"dark","ghost":"normal","dragon":"fairy"}
def effectiveness(move,targets,modern=False):
    if move not in TYPES or not targets or any(t not in TYPES for t in targets):return None
    if not modern and ("fairy" in targets or move=="fairy"):return None
    result=1.0
    for t in set(targets):
        if t in IMMUNE.get(move,"").split():return 0.0
        if not modern and t=="steel" and move in ("ghost","dark"):result*=.5
        elif t in SUPER.get(move,"").split():result*=2
        elif t in RESIST.get(move,"").split():result*=.5
    return result

def act(button,frames=5):return {"button":button,"frames":frames}

def cursor_action(current,target):
    # Four-move / four-command Gen III 2x2 grid, row-major.
    if type(current) is not int or type(target) is not int or not 0<=current<4 or not 0<=target<4:return None
    if current==target:return [act("A")]
    if current//2!=target//2:return [act("DOWN" if target//2>current//2 else "UP")]
    return [act("RIGHT" if target%2>current%2 else "LEFT")]

def number(value,lo,hi):
    return type(value) is int and lo<=value<=hi

def type_list(value):
    if type(value) is not list or not 1<=len(value)<=2 or any(type(t) is not str or t.lower() not in TYPES for t in value):return []
    return list(dict.fromkeys(t.lower() for t in value))

def clean_observation(raw):
    """Fail closed on unsupported/malformed fields; base vision actions still work."""
    if type(raw) is not dict:return {}
    stage=raw.get("stage")
    if stage not in ("field","dialogue","battle_command","battle_moves","bag","party","title","menu","transition","other"):return {}
    out={"stage":stage}
    for key in ("location","fact","target","enemy","own","bag_purpose"):
        v=raw.get(key)
        if isinstance(v,str) and 0<len(v)<=180 and not any(ord(c)<32 for c in v):out[key]=v
    for key,lo,hi in (("cursor",0,3),("list_cursor",0,15),("hp",0,100),("enemy_hp",0,100),("balls",0,999),("healing_items",0,999),("party_count",0,6)):
        if number(raw.get(key),lo,hi):out[key]=raw[key]
    for key in ("wild","capture_target","enemy_status"):
        if type(raw.get(key)) is bool:out[key]=raw[key]
    for key in ("own_types","enemy_types"):
        t=type_list(raw.get(key))
        if t:out[key]=t
    moves=raw.get("moves")
    if type(moves) is list and 1<=len(moves)<=4:
        clean=[]
        for m in moves:
            if type(m) is not dict or not number(m.get("slot"),0,3) or not isinstance(m.get("name"),str) or not 1<=len(m["name"])<=30:continue
            if any(ord(c)<32 for c in m["name"]):continue
            row={"slot":m["slot"],"name":m["name"]}
            mt=m.get("type")
            if type(mt) is str and mt.lower() in TYPES:row["type"]=mt.lower()
            for key,lo,hi in (("power",0,250),("pp",0,64),("accuracy",1,100)):
                if number(m.get(key),lo,hi):row[key]=m[key]
            clean.append(row)
        if len({m["slot"] for m in clean})==len(clean):out["moves"]=clean
    items=raw.get("items")
    if isinstance(items,list) and 1<=len(items)<=16:
        out["items"]=[{"slot":m["slot"],"name":m["name"],"count":m["count"]} for m in items if isinstance(m,dict) and number(m.get("slot"),0,15) and isinstance(m.get("name"),str) and 0<len(m["name"])<=40 and number(m.get("count"),1,999)]
    party=raw.get("party")
    if isinstance(party,list) and 1<=len(party)<=6:
        out["party"]=[{"slot":m["slot"],"hp":m["hp"],"types":type_list(m.get("types"))} for m in party if isinstance(m,dict) and number(m.get("slot"),0,5) and number(m.get("hp"),0,100)]
    # Optional 15x10 screen-space grid; unknown/blocked tiles are impassable.
    # Coordinates are model estimates, not authoritative map collision.
    grid=raw.get("grid");start=raw.get("start");target=raw.get("destination")
    def xy(x):return type(x) is list and len(x)==2 and number(x[0],0,14) and number(x[1],0,9)
    if (stage=="field" and type(grid) is list and len(grid)==10 and all(type(row) is str and len(row)==15 and set(row)<=set(".#?") for row in grid)
        and xy(start) and xy(target) and grid[target[1]][target[0]]=="."):
        out.update(grid=grid,start=start,destination=target)
    return out

def best_move(obs,modern=False):
    targets=obs.get("enemy_types",[])
    if not targets:return None
    own=obs.get("own_types",[])
    candidates=[]
    for m in obs.get("moves",[]):
        if not m.get("pp") or not m.get("power") or "type" not in m or "accuracy" not in m:continue
        e=effectiveness(m["type"],targets,modern)
        if e is None or not e:continue
        score=m["power"]*m["accuracy"]/100*e*(1.5 if m["type"] in own else 1)
        # Catch intent: avoid high-power/high-effectiveness damage when possible.
        if obs.get("wild") is True and obs.get("capture_target") is True:
            if obs.get("enemy_hp",100)<=35:continue
            score=-score
        candidates.append((score,-m["slot"],m))
    return max(candidates,key=lambda x:x[:2])[2] if candidates else None

def battle_policy(obs,modern=False):
    stage=obs.get("stage")
    if stage not in ("battle_command","battle_moves"):return None
    cursor=obs.get("cursor")
    if cursor is None:return None
    capture=obs.get("wild") is True and obs.get("capture_target") is True
    heal=obs.get("hp",100)<=25 and obs.get("healing_items",0)>0
    throw=capture and obs.get("balls",0)>0 and (obs.get("enemy_hp",100)<=35 or obs.get("enemy_status") is True)
    if stage=="battle_command":
        if heal:return cursor_action(cursor,1),"Open BAG to heal low HP"
        if throw:return cursor_action(cursor,1),"Open BAG to attempt a wild catch"
        # Don't select generic FIGHT when a switch/run is needed but unobserved.
        if obs.get("hp",100)<=15 and any(m["hp"]>30 for m in obs.get("party",[]) if m["slot"]!=0):return cursor_action(cursor,2),"Open POKéMON to switch from low HP"
        if obs.get("hp",100)<=15:return None
        if capture and obs.get("balls",0)==0:return None
        if obs.get("enemy_types"):return cursor_action(cursor,0),"Open FIGHT and inspect moves"
    else:
        if heal or throw:return [act("B")],"Return to battle command menu for BAG"
        if capture and (obs.get("balls",0)==0 or obs.get("enemy_hp",100)<=35):return None
        move=best_move(obs,modern)
        if move:
            return cursor_action(cursor,move["slot"]),"Choose "+move["name"]+(" cautiously to weaken wild Pokémon" if capture else " by type, power, accuracy and PP")
    return None

def item_policy(obs):
    if obs.get("stage")!="bag" or obs.get("list_cursor") is None:return None
    purpose=obs.get("bag_purpose","").lower()
    cursor=obs["list_cursor"]
    if purpose=="catch" and obs.get("wild") is True and obs.get("capture_target") is True:
        allowed={"poke ball":1,"poké ball":1,"great ball":2,"ultra ball":3}
    elif purpose=="heal":
        allowed={"potion":1,"super potion":2,"hyper potion":3,"max potion":4,"full restore":5}
    else:return None
    choices=[(allowed[m["name"].lower()],m["slot"],m["name"]) for m in obs.get("items",[]) if m["name"].lower() in allowed]
    if not choices:return None
    if purpose=="heal" and obs.get("hp",100)>50:return None
    # Use a small potion first; for capture prefer stronger ordinary balls.
    _,slot,name=(min if purpose=="heal" else max)(choices)
    return [act("A" if slot==cursor else ("DOWN" if slot>cursor else "UP"))],"Select observed "+name+" for "+purpose

DIRECTIONS=(("UP",0,-1),("LEFT",-1,0),("RIGHT",1,0),("DOWN",0,1))
def route_step(obs,blocked=()):
    if obs.get("stage")!="field" or "grid" not in obs:return None
    start=tuple(obs["start"]);goal=tuple(obs["destination"]);grid=obs["grid"]
    if start==goal:return None
    q=deque([(start,None)]);seen={start}
    while q:
        (x,y),first=q.popleft()
        if (x,y)==goal:return [act(first,16)],"Explore toward observed target "+obs.get("target","")
        for name,dx,dy in DIRECTIONS:
            nxt=(x+dx,y+dy)
            if nxt in seen or not (0<=nxt[0]<15 and 0<=nxt[1]<10) or grid[nxt[1]][nxt[0]]!=".":continue
            if first is None and name in blocked:continue
            seen.add(nxt);q.append((nxt,first or name))
    return None

def policy(obs,goal,history,screen):
    if not obs:return None
    modern="modern" in goal.lower() and "classic" not in goal.lower()
    result=item_policy(obs) or battle_policy(obs,modern)
    if result:return result
    blocked={a["button"] for h in history[-20:] if h.get("before")==screen==h.get("after") for a in h.get("actions",[]) if a.get("button")}
    return route_step(obs,blocked)

def remember(memory,obs,decision,after,turn):
    """Bounded cross-session quest notebook. Entries are model hypotheses."""
    if not isinstance(memory,dict):memory={}
    facts=list(memory.get("facts",[]))[-40:];places=list(memory.get("places",[]))[-30:]
    if obs.get("fact"):
        entry={"location":obs.get("location","unknown"),"fact":obs["fact"],"turn":turn}
        if not any(x["location"]==entry["location"] and x["fact"]==entry["fact"] for x in facts):facts.append(entry)
    if obs.get("location"):
        place=obs["location"]
        old=next((v for v in places if v["location"]==place),None)
        if old:places.remove(old)
        places.append({"location":place,"target":obs.get("target",""),"turn":turn})
    edges=list(memory.get("edges",[]))[-50:]
    previous=memory.get("last_location")
    current=obs.get("location")
    if current and previous and previous!=current:
        e={"from":previous,"to":current}
        if e not in edges:edges.append(e)
    return {"facts":facts[-40:],"places":places[-30:],"edges":edges[-50:],"last_location":current or previous,"last_objective":decision["objective"],"last_screen":after}

def memory_context(memory):
    return {"facts":memory.get("facts",[])[-12:],"places":memory.get("places",[])[-8:],"last_objective":memory.get("last_objective",""),"observed_connections":memory.get("edges",[])[-8:]}
