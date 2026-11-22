"""Bounded purposeful exploration using witnessed native field state."""
from core.jj_fast import OBJECTS, MAP_HEADER, DIR, u, signed
from core.firered import span
from core.live import LiveError
from core.jj_connections import crossings
from core.jj_world_model import rank as rank_goal
from core.jj_tile_memory import blocked_tiles, probe_frames, record as record_tile_step
from vendor.pokemon_agent.pathfinding import find_path

FACING={1:"DOWN",2:"UP",3:"LEFT",4:"RIGHT"}

def event_targets(live,rom_size,field,map_header=MAP_HEADER,object_base=OBJECTS,vmap=None):
    """Only expose in-map coordinates from structurally checked ROM pointers."""
    def romread(ptr,n):
        if not span(ptr,n,0x08000000,0x08000000+rom_size):raise ValueError("event pointer")
        return live.read(ptr,n)
    ptr=live.integer(map_header+4,4)
    if ptr%4:raise ValueError("events alignment")
    data=romread(ptr,20);count=data[1];warps=[]
    if count>64:raise ValueError("warp count")
    if count:
        raw=romread(u(data,8,4),count*8)
        for i in range(count):
            x,y=signed(raw,i*8),signed(raw,i*8+2)
            if not (0<=x<field.width and 0<=y<field.height):raise ValueError("warp location")
            warps.append({"kind":"warp","x":x,"y":y,"id":i,"destination":[raw[i*8+7],raw[i*8+6]]})
    objects=live.read(object_base,36*16);npcs=[];facing=None
    for i in range(16):
        o=objects[i*36:(i+1)*36];flags=u(o,0,4)
        if not flags&1:continue
        x,y=signed(o,16)-7,signed(o,18)-7
        if flags&0x10000:facing=FACING.get(o[24]&15);continue
        if flags&0x2000:continue # invisible
        if 0<=x<field.width and 0<=y<field.height:
            npcs.append({"kind":"npc","x":x,"y":y,"id":o[8],"gfx":o[5]})
    try:connections=crossings(live,rom_size,field,map_header=map_header,**({"vmap":vmap} if vmap is not None else {}))
    except (ValueError,LiveError,IndexError):connections=[]
    return warps+npcs+connections,facing

def event_key(field,event):
    return ":".join(map(str,(*field.map_id,event["kind"],event["id"],event["x"],event["y"])))

def options(field,occupied,events,attempted,blocked=()):
    """Rank reachable untried events, staying off unrelated warp tiles."""
    candidates=[]
    blocked=set(blocked)
    warps={(e["x"],e["y"]) for e in events if e["kind"]=="warp"}
    for e in events:
        key=event_key(field,e)
        if key in attempted:continue
        p=(e["x"],e["y"])
        if e["kind"] in ("warp","connection"):goals=[(p,e.get("direction"))]
        else:goals=[((p[0]-dx,p[1]-dy),d) for d,(dx,dy) in DIR.items()]
        for target,direction in goals:
            if target==field.pos and target not in blocked:path=[]
            else:
                path=find_path(field.pos,target,lambda x,y:field.passable(x,y) and (x,y) not in occupied and (x,y) not in blocked and ((x,y) not in warps or (x,y)==target),field.width,field.height)
                if path is None:continue
            candidates.append((len(path),key,tuple(target),direction,e,path))
    return sorted(candidates,key=lambda c:(c[0],c[1],c[2]))

class Explorer:
    def __init__(self,adapter):self.adapter=adapter
    def inspect(self,candidate,meta):
        if not self.adapter.verified_field(candidate,meta):return None
        try:return event_targets(self.adapter.live,self.adapter.size,candidate[0],getattr(self.adapter,"map_header",MAP_HEADER),getattr(self.adapter,"objects",OBJECTS),getattr(self.adapter,"vmap",None))
        except (ValueError,LiveError,IndexError):return None
    def describe(self,candidate,meta,info):
        if not info:return {}
        f,_,occupied=candidate;events,_=info
        tried=meta.get("event_attempts",[])
        choices=options(f,occupied,events,tried,blocked_tiles(meta,f.map_id))
        result=[];seen=set()
        for dist,key,target,facing,event,path in choices:
            if key in seen:continue
            seen.add(key)
            result.append(dict(event,approach=list(target),distance=dist))
            if len(result)>=12:break
        return {"reachable_events":result,"recent_map_transitions":meta.get("map_transitions",[])[-8:]}
    def request(self,candidate,meta,info,task):
        if not info or task not in ("explore","interact","exit"):return False
        f,_,occupied=candidate;events,_=info
        if task=="interact":events=[e for e in events if e["kind"]=="npc"]
        elif task=="exit":events=[e for e in events if e["kind"] in ("warp","connection")]
        choices=options(f,occupied,events,meta.get("event_attempts",[]),blocked_tiles(meta,f.map_id))
        if not choices:return False
        choices=[c for c in choices if c[5] or c[4]["kind"]!="warp"]
        if not choices:return False
        # Select intent, then let the existing tested A* paths and per-step
        # witness checks do the movement. Avoid repeating visited routes while
        # retaining the option to return through story-gated map connections.
        party=meta.get("native_party_count")
        chosen=rank_goal(meta,choices,party,current_map=f.map_id,task_name=task)
        if chosen is None:return False
        _,key,target,facing,event,path=chosen
        meta["event_goal"]={"map":list(f.map_id),"key":key,"event":event,"target":list(target),"facing":facing,"remaining":min(48,len(path)+3)}
        return True
    def next(self,candidate,meta,info):
        goal=meta.get("event_goal")
        if not goal or not info or not candidate:return None
        f,_,occupied=candidate;events,facing=info
        if goal["map"]!=list(f.map_id) or goal["remaining"]<=0 or goal["event"] not in events:return None
        target=tuple(goal["target"]);event=goal["event"]
        warps={(e["x"],e["y"]) for e in events if e["kind"]=="warp"}
        blocked=blocked_tiles(meta,f.map_id)
        if f.pos==target:
            if event["kind"]=="warp":return None
            if event["kind"]=="connection":
                action=event["direction"];expected=None;kind="cross"
            elif facing!=goal["facing"]:
                action=goal["facing"];expected=f.pos;kind="face"
            else:action="A";expected=None;kind="interact"
        else:
            path=find_path(f.pos,target,lambda x,y:f.passable(x,y) and (x,y) not in occupied and (x,y) not in blocked and ((x,y) not in warps or (x,y)==target),f.width,f.height)
            if not path:return None
            action=path[0].upper();dx,dy=DIR[action];expected=(f.pos[0]+dx,f.pos[1]+dy);kind="move"
        frames=(probe_frames(meta,f.map_id,expected) if kind=="move" else (1 if action!="A" else 5))
        return {"scene":"native_exploration","objective":("Interact with observed NPC" if event["kind"]=="npc" else "Travel toward observed connection" if event["kind"]=="connection" else "Approach observed warp"),"actions":[{"button":action,"frames":frames}],"review":False},(kind,expected)
    def interrupt(self,meta,reason):
        """Discard a stale skill path without treating its objective as failed.

        A native battle, scripted transition or temporary menu interrupts the
        route; the agent must re-plan from the next corroborated field state.
        The event stays eligible for another attempt.
        """
        if reason not in ("battle","menu","transition"):return False
        goal=meta.pop("event_goal",None)
        if not isinstance(goal,dict):return False
        row={"map":goal.get("map"),"event":goal.get("key"),"reason":reason}
        history=meta.get("skill_interruptions",[])
        if not isinstance(history,list):history=[]
        history.append(row)
        meta["skill_interruptions"]=history[-24:]
        return True
    def finish(self,meta,before,after,command,*,interrupted=False):
        goal=meta.get("event_goal")
        if not goal:return
        if interrupted:
            self.interrupt(meta,"battle")
            return
        f=before[0];kind,expected=command
        if kind=="move" and expected is not None:
            outcome=record_tile_step(meta,before,after,command,
                verified_before=self.adapter.verified_field(before,meta),
                verified_after=self.adapter.verified_field(after,meta))
            if outcome=="retry" and goal["remaining"]>1:
                # A one-frame tap can turn the player without walking.
                # Keep this target once, retry with a bounded 12-frame hold,
                # then avoid that tile if movement is still unobserved.
                goal["remaining"]-=1
                return
            if outcome=="blocked":
                # The approach tile, not the entire NPC/exit, is unusable.
                # Re-evaluate other A* approaches before marking the story
                # event itself as attempted.
                meta.pop("event_goal",None)
                return
        if after and after[0].map_id!=f.map_id:
            edges=meta.get("map_transitions",[])
            edge={"from":list(f.map_id),"to":list(after[0].map_id),"event":goal["event"]["id"]}
            if edge not in edges:edges.append(edge)
            meta["map_transitions"]=edges[-100:]
        if kind=="cross":
            meta["pending_crossing"]={"from":list(f.map_id),"destination":goal["event"]["destination"],"event":goal["event"]["id"]}
        if kind in ("interact","cross") or not after or after[0].map_id!=f.map_id or (expected is not None and after[0].pos!=expected):
            attempted=meta.get("event_attempts",[])
            if goal["key"] not in attempted:attempted.append(goal["key"])
            meta["event_attempts"]=attempted[-300:]
            meta.pop("event_goal",None)
        else:
            goal["remaining"]-=1
