"""Evidence-grounded world model and high-level field skill selection.

This module does not replace the upstream A* navigator, game-memory reader,
battle driver, or mGBA controller. It connects their independently corroborated
facts to durable map/exit memory and selects *intents*, never arbitrary buttons.

Only verified native fields can update the world.  An observed route or
proposed exit is not a completed map transition.  Repeated travel over an
already traversed edge is a cost, not a hard ban: story gates may require return.
"""
from collections import Counter

MAX_MAPS=160
MAX_POSITIONS=40
MAX_EDGES=100
MAX_EVENTS=32
MAX_LOG=48
TASKS=("interact","exit","explore")
MAP_CAP=255


def map_key(map_id):
    if isinstance(map_id,tuple):map_id=list(map_id)
    if (type(map_id) is not list or len(map_id)!=2
            or any(type(n) is not int or not 0<=n<=MAP_CAP for n in map_id)):
        return None
    return f"{map_id[0]}:{map_id[1]}"


def _world(meta):
    d=meta.get("world_model")
    if not isinstance(d,dict) or d.get("version")!=1 or not isinstance(d.get("maps"),dict):
        d={"version":1,"maps":{},"edges":[],"recent":[]}
        meta["world_model"]=d
    if not isinstance(d.get("edges"),list):d["edges"]=[]
    if not isinstance(d.get("recent"),list):d["recent"]=[]
    return d


def observe(meta,candidate,events,*,verified,decision):
    """Persist only read-only native facts with an independent movement proof."""
    if not verified or not candidate:return False
    try:
        field,callback,occupied=candidate
        k=map_key(field.map_id);x,y=field.pos
        if (k is None or type(callback) is not int or not 0x08000000<=callback<0x0a000000
                or type(x) is not int or type(y) is not int
                or not 0<=x<field.width or not 0<=y<field.height
                or not isinstance(occupied,set) or type(decision) is not int
                or not 0<=decision<=10000000):
            return False
    except (AttributeError,TypeError,ValueError):
        return False
    d=_world(meta);maps=d["maps"]
    node=maps.pop(k,{"map":list(field.map_id),"visits":0,"positions":[],"event_kinds":{}})
    if not isinstance(node,dict):node={"map":list(field.map_id),"visits":0,"positions":[],"event_kinds":{}}
    positions=node.get("positions",[])
    if not isinstance(positions,list):positions=[]
    pos=[x,y]
    if pos in positions:positions.remove(pos)
    positions.append(pos)
    node.update(visits=min(100000,int(node.get("visits",0))+1),
                positions=positions[-MAX_POSITIONS:],
                last_decision=decision)
    counts=Counter()
    if events and type(events) in (list,tuple) and len(events)<256:
        for event in events:
            if not isinstance(event,dict) or event.get("kind") not in ("npc","warp","connection"):continue
            if type(event.get("x")) is not int or type(event.get("y")) is not int:continue
            if not 0<=event["x"]<field.width or not 0<=event["y"]<field.height:continue
            counts[event["kind"]]+=1
    node["event_kinds"]=dict(counts)
    maps[k]=node
    while len(maps)>MAX_MAPS:maps.pop(next(iter(maps)))
    recent=d["recent"]
    prev=recent[-1] if recent else None
    if not prev or prev.get("map")!=k or prev.get("pos")!=pos:
        recent.append({"map":k,"pos":pos,"decision":decision})
    d["recent"]=recent[-MAX_LOG:]
    # Edges are not invented from a predicted destination. The existing
    # native verifier adds witnessed crossings to observed_field_transitions.
    for row in meta.get("observed_field_transitions",[])[-MAX_EDGES:]:
        if not isinstance(row,dict):continue
        source,target=map_key(row.get("from")),map_key(row.get("to"))
        if source is None or target is None or source==target:continue
        edge={"from":source,"to":target}
        if edge not in d["edges"]:d["edges"].append(edge)
    d["edges"]=d["edges"][-MAX_EDGES:]
    return True


def task(meta,party=None,events=None):
    """A high-level *request* for the existing Explorer, not a controller input.

    If a verified team is absent, interaction can provide a starter or story
    objective. Once a team exists, prefer new map exits. A critical-health
    condition requests strategic attention rather than blindly running toward
    an unverified Pokémon Center.
    """
    if not isinstance(party,list):return "explore"
    if not party:return "interact"
    alive=[m for m in party if isinstance(m,dict) and type(m.get("hp")) is int
           and type(m.get("max_hp")) is int and m["max_hp"]>0
           and m["hp"]>=0]
    if not alive:return "explore"
    if not any(m["hp"]>0 for m in alive):return None
    if max(m["hp"]/m["max_hp"] for m in alive)<0.25:return None
    if not events:return "explore"
    if any(isinstance(e,dict) and e.get("kind") in ("warp","connection") for e in events):
        return "exit"
    return "explore"


def rank(meta,choices,party_count,*,current_map=None,task_name="explore"):
    """Choose one of the already-verified Explorer.options() A* routes.

    The existing options() checks occupancy, passability and warp hazards.
    This ranker only considers evidence-supported *relevance* and repeat cost.
    """
    if not choices:return None
    if task_name not in TASKS:return None
    d=meta.get("world_model",{})
    maps=d.get("maps",{}) if isinstance(d,dict) else {}
    edges=d.get("edges",[]) if isinstance(d,dict) else []
    seen=set()
    if isinstance(maps,dict):seen=set(maps)
    known_edges={(x.get("from"),x.get("to")) for x in edges if isinstance(x,dict)}
    if type(party_count) is not int or party_count<0:party_count=None
    if current_map is not None:current_map=map_key(current_map)
    recent=d.get("recent",[]) if isinstance(d,dict) else []
    recent_maps=[x.get("map") for x in recent[-8:] if isinstance(x,dict)]
    def key(choice):
        dist,evkey,target,facing,event,path=choice
        kind=event["kind"]
        dest=map_key(event.get("destination"))
        edge=(current_map,dest)
        if party_count==0:purpose=0 if kind=="npc" else 1
        elif task_name=="interact":purpose=0 if kind=="npc" else 3
        elif task_name=="exit":purpose=0 if kind in ("warp","connection") else 3
        else:purpose=0 if kind in ("warp","connection") else 1
        # Prefer new map destinations, then less-repeated edges; never claim
        # a warp is successful just because it was selected as a destination.
        novelty=0 if kind in ("warp","connection") and dest is not None and dest not in seen else 1
        repeat=1 if edge in known_edges else 0
        recent_penalty=1 if dest in recent_maps[-4:] else 0
        return purpose,novelty,repeat,recent_penalty,dist,evkey,target
    return min(choices,key=key)


def summary(meta):
    d=meta.get("world_model",{})
    if not isinstance(d,dict) or d.get("version")!=1:return None
    maps=d.get("maps",{})
    if not isinstance(maps,dict):return None
    return {"confirmed_maps":len(maps),"verified_edges":len(d.get("edges",[])),
            "recent_positions":d.get("recent",[])[-4:],
            "note":"Only native-verified coordinates and crossings; predicted exits are not completed routes"}


def complete(meta,*,task_name,observed):
    """Only completed, independently recorded map transitions count.

    NPC dialogue and event attempts are *not* successful quest completions.
    The current native controller supplies observed_field_transitions only
    after corroborated arrival, never after merely attempting a warp.
    """
    if task_name not in ("exit","explore") or not observed:return False
    transitions=meta.get("observed_field_transitions",[])
    if not isinstance(transitions,list) or not transitions:return False
    last=transitions[-1]
    if not isinstance(last,dict):return False
    before,after=map_key(last.get("from")),map_key(last.get("to"))
    if before is None or after is None or before==after:return False
    d=_world(meta)
    outcomes=d.setdefault("skill_outcomes",[])
    if not isinstance(outcomes,list):outcomes=[]
    row={"task":task_name,"result":"native_verified","from":before,"to":after}
    if row in outcomes:return False
    outcomes.append(row)
    d["skill_outcomes"]=outcomes[-MAX_EVENTS:]
    return True
