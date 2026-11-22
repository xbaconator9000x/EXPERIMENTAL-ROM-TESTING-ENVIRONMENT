"""Bounded purposeful exploration using witnessed native field state."""
from collections import deque
from core.jj_fast import OBJECTS, MAP_HEADER, DIR, u, signed
from core.firered import span
from core.live import LiveError
from core.jj_connections import crossings
from core.jj_world_model import rank as rank_goal
from core.jj_tile_memory import blocked_tiles, probe_frames, record as record_tile_step
from vendor.pokemon_agent.pathfinding import find_path

FACING={1:"DOWN",2:"UP",3:"LEFT",4:"RIGHT"}
# Only after a full native event/frontier pass do we try previously attempted
# events again. The retry budget is *event approaches*, not repeated idle polls.
NATIVE_RETRY_APPROACHES=24
NATIVE_RETRY_PER_TARGET=12

def event_targets(live,rom_size,field,map_header=MAP_HEADER,object_base=OBJECTS,vmap=None):
    """Only expose in-map coordinates from structurally checked ROM pointers."""
    def romread(ptr,n):
        if not span(ptr,n,0x08000000,0x08000000+rom_size):raise ValueError("event pointer")
        return live.read(ptr,n)
    ptr=live.integer(map_header+4,4)
    if ptr%4:raise ValueError("events alignment")
    data=romread(ptr,20);count=data[1];warps=[]
    # FireRed MapEvents: object, warp, coord, background counts,
    # followed by four 32-bit ROM pointers. A ball sitting on a table
    # commonly uses a background/signpost event, not a live object sprite.
    coord_count=data[2]
    bg_count=data[3]
    if count>64:raise ValueError("warp count")
    if bg_count>64:raise ValueError("background event count")
    if coord_count>64:raise ValueError("coordinate trigger count")
    if count:
        raw=romread(u(data,8,4),count*8)
        for i in range(count):
            x,y=signed(raw,i*8),signed(raw,i*8+2)
            if not (0<=x<field.width and 0<=y<field.height):raise ValueError("warp location")
            warps.append({"kind":"warp","x":x,"y":y,"id":i,"destination":[raw[i*8+7],raw[i*8+6]]})
    coords=[]
    if coord_count:
        raw=romread(u(data,12,4),coord_count*16)
        for i in range(coord_count):
            off=i*16
            x,y=signed(raw,off),signed(raw,off+2)
            if not (0<=x<field.width and 0<=y<field.height):
                raise ValueError("coordinate trigger location")
            # Triggers activate on entering their tile, not by pressing A.
            # The native field reader verifies the subsequent transition.
            coords.append({"kind":"coord","x":x,"y":y,"id":i,
                           "trigger":u(raw,off+6,2),"index":u(raw,off+8,2)})
    backgrounds=[]
    if bg_count:
        raw=romread(u(data,16,4),bg_count*12)
        for i in range(bg_count):
            off=i*12
            x,y=signed(raw,off),signed(raw,off+2)
            if not (0<=x<field.width and 0<=y<field.height):
                raise ValueError("background event location")
            # Preserve game-defined event kind; never infer item success from
            # visual similarity. The ordinary A interaction is verified later.
            backgrounds.append({"kind":"bg","x":x,"y":y,"id":i,"bg_kind":raw[off+5]})
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
    return warps+npcs+backgrounds+coords+connections,facing

def event_key(field,event):
    return ":".join(map(str,(*field.map_id,event["kind"],event["id"],event["x"],event["y"])))


def reentry_neighbor(field,occupied,events,blocked=()):
    """A safe one-tile step OFF an existing warp or coordinate trigger.

    The next A* leg enters the trigger from the neighboring tile. A short
    turn, standing on the tile, or pressing A cannot activate a walk-on
    trigger; never substitute unverified visual movement.
    """
    hazards={(e["x"],e["y"]) for e in events
             if isinstance(e,dict) and e.get("kind") in ("warp","coord")}
    obstacles=set(occupied)|set(blocked)|hazards
    for direction,(dx,dy) in DIR.items():
        nxt=(field.pos[0]+dx,field.pos[1]+dy)
        if nxt not in obstacles and field.passable(*nxt):
            return direction,nxt
    return None


def options(field,occupied,events,attempted,blocked=(),avoid_warps=None):
    """Rank reachable untried events, staying off unrelated warp tiles."""
    candidates=[]
    blocked=set(blocked)
    # All original warp tiles remain hazardous even when the requested
    # task filters the candidates down to NPCs or route connections.
    triggers={(e["x"],e["y"]) for e in (events if avoid_warps is None else avoid_warps)
              if e["kind"] in ("warp","coord")}
    for e in events:
        key=event_key(field,e)
        if key in attempted:continue
        p=(e["x"],e["y"])
        if e["kind"] in ("warp","connection","coord"):goals=[(p,e.get("direction"))]
        else:goals=[((p[0]-dx,p[1]-dy),d) for d,(dx,dy) in DIR.items()]
        for target,direction in goals:
            if target==field.pos:path=[]
            else:
                path=find_path(field.pos,target,lambda x,y:field.passable(x,y) and (x,y) not in occupied and (x,y) not in blocked and ((x,y) not in triggers or (e["kind"] in ("warp","coord") and (x,y)==target)),field.width,field.height)
                if path is None:continue
            candidates.append((len(path),key,tuple(target),direction,e,path))
    return sorted(candidates,key=lambda c:(c[0],c[1],c[2]))

class Explorer:
    def __init__(self,adapter):self.adapter=adapter
    def inspect(self,candidate,meta):
        if not self.adapter.verified_field(candidate,meta):
            meta["native_event_probe"]={"status":"FIELD_NOT_VERIFIED"}
            return None
        try:
            info=event_targets(self.adapter.live,self.adapter.size,candidate[0],getattr(self.adapter,"map_header",MAP_HEADER),getattr(self.adapter,"objects",OBJECTS),getattr(self.adapter,"vmap",None))
            events,_=info
            field,_,occupied=candidate
            attempted=meta.get("event_attempts",[])
            if not isinstance(attempted,list):attempted=[]
            blocked=blocked_tiles(meta,field.map_id)
            choices=options(field,occupied,events,attempted,blocked,
                            avoid_warps=events)
            # Zero untried events does not mean no physically reachable
            # events. Explicitly distinguish an attempt-bookkeeping lockout
            # from a genuine collision-graph disconnection.
            retry_choices=(options(field,occupied,events,[],blocked,
                                   avoid_warps=events)
                           if attempted else choices)
            meta["native_event_probe"]={
                "status":"EVENTS_READ",
                "counts":{kind:sum(e["kind"]==kind for e in events) for kind in ("npc","warp","bg","coord","connection")},
                "reachable":len(set(c[1] for c in choices)),
                "reachable_if_retried":len(set(c[1] for c in retry_choices)),
                "attempted":sum(event_key(field,e) in attempted for e in events),
                "event_positions":[{"kind":e["kind"],"x":e["x"],"y":e["y"]} for e in events[:16]],
                "active_goal":bool(meta.get("event_goal")),
                "party_count":meta.get("native_party_count")
            }
            return info
        except (ValueError,LiveError,IndexError):
            # Keep the reader fail-closed, but expose why deterministic
            # event navigation was unavailable instead of silently using Qwen.
            meta["native_event_probe"]={"status":"EVENTS_REJECTED"}
            return None
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
        all_events=events
        if task=="interact":events=[e for e in events if e["kind"] in ("npc","bg")]
        elif task=="exit":events=[e for e in events if e["kind"] in ("warp","connection")]
        attempted=meta.get("event_attempts",[])
        choices=options(f,occupied,events,attempted,blocked_tiles(meta,f.map_id),avoid_warps=all_events)
        if (not choices and task=="interact"
                and meta.get("objective_state",{}).get("phase")=="obtain_initial_party"
                and meta.get("starter_event_retry")!=list(f.map_id)):
            # An old checkpoint may have marked every NPC/background event
            # attempted after a single A press without confirming a starter.
            # Retry each native event once, bounded to one sweep per map, and
            # leave the original attempt history intact.
            meta["starter_event_retry"]=list(f.map_id)
            choices=options(f,occupied,events,[],blocked_tiles(meta,f.map_id),avoid_warps=all_events)
        if not choices:return False
        # A normal exit can start while we already occupy its warp tile.
        # Re-enter it from a safe adjacent tile instead of rejecting the
        # only known exit and roaming the rest of the room.
        choices=[c for c in choices if c[5] or
                 (c[4]["kind"] in ("warp","coord")
                  and c[2]==f.pos
                  and reentry_neighbor(f,occupied,all_events,
                                       blocked_tiles(meta,f.map_id)) is not None)
                 or c[4]["kind"] not in ("warp","coord")]
        if not choices:return False
        # Select intent, then let the existing tested A* paths and per-step
        # witness checks do the movement. Avoid repeating visited routes while
        # retaining the option to return through story-gated map connections.
        party=meta.get("native_party_count")
        if task=="interact" and meta.get("objective_state",{}).get("phase")=="obtain_initial_party":
            party=0
        chosen=rank_goal(meta,choices,party,current_map=f.map_id,task_name=task)
        if chosen is None:return False
        _,key,target,facing,event,path=chosen
        meta["event_goal"]={"map":list(f.map_id),"key":key,"event":event,
                            "target":list(target),"facing":facing,
                            "retry":bool(f.pos==target and event["kind"] in ("warp","coord")),
                            "remaining":min(48,len(path)+6)}
        return True
    def reconsider(self,candidate,meta,info):
        """Systematically retry genuine ROM events after normal A* exploration.

        The original event-attempt audit is not cleared. A map/party-scoped
        round tries distinct exits and triggers before repeating them; up to
        24 *planned event approaches* between visual consultations. When no
        actual path exists the reader reports exhaustion immediately rather
        than burning emulator frames on blind movement.
        """
        if (not candidate or not info or
                not self.adapter.verified_field(candidate,meta)
                or meta.get("event_goal")):return False
        field,_,occupied=candidate;events,_=info
        if not isinstance(events,list):return False
        epoch=[*field.map_id,meta.get("native_party_count")]
        state=meta.get("native_revisit")
        if not isinstance(state,dict) or state.get("epoch")!=epoch:
            state={"epoch":epoch,"approaches":0,"per_target":{},"sweeps":0}
            meta["native_revisit"]=state
        approaches=state.get("approaches",0)
        if type(approaches) is not int or approaches>=NATIVE_RETRY_APPROACHES:
            state["status"]="retry_threshold_reached"
            return False
        counts=state.get("per_target",{})
        if not isinstance(counts,dict):counts={};state["per_target"]=counts
        viable=options(field,occupied,events,[],blocked_tiles(meta,field.map_id),
                       avoid_warps=events)
        # Repeated warp/coord entry requires an approach; being already
        # on the trigger is handled by a verified step off and then back.
        viable=[c for c in viable if c[4].get("kind") in
                ("warp","connection","coord","npc","bg")
                and counts.get(c[1],0)<NATIVE_RETRY_PER_TARGET
                and (bool(c[5]) or c[4]["kind"] not in ("warp","coord")
                     or reentry_neighbor(field,occupied,events,
                           blocked_tiles(meta,field.map_id)) is not None)]
        if not viable:
            state["status"]="no_reachable_native_events"
            return False
        kind_priority={"warp":0,"connection":1,"coord":2,"npc":3,"bg":4}
        chosen=min(viable,key=lambda c:(
            counts.get(c[1],0),kind_priority[c[4]["kind"]],c[0],c[1],c[2]))
        dist,key,target,facing,event,path=chosen
        counts[key]=counts.get(key,0)+1
        state["approaches"]=approaches+1
        state["status"]="retrying_native_events"
        meta["event_goal"]={"map":list(field.map_id),"key":key,"event":event,
                            "target":list(target),"facing":facing,
                            "retry":True,"remaining":min(64,len(path)+8)}
        return True

    def restart_reconsider(self,meta):
        """Allow a fresh native sweep after an exceptional strategic check."""
        state=meta.get("native_revisit")
        if not isinstance(state,dict):return
        state["sweeps"]=max(0,int(state.get("sweeps",0)))+1
        state["approaches"]=0
        state["per_target"]={}
        state["status"]="fresh_native_sweep_after_strategic_check"

    def guarded_visual(self,candidate,meta,info,proposal):
        """One last-resort vision suggestion, independently checked natively.

        No visual multi-step paths or wall/warp/NPC guesses can be executed.
        A proposal may move ONE passable grid tile (verified against current
        collision/objects/map triggers) or interact with a nearby observed
        story object. Native coordinates will corroborate the result.
        """
        if (not candidate or not info
                or not self.adapter.verified_field(candidate,meta)
                or not isinstance(proposal,dict) or proposal.get("review")):
            return None
        f,_,occupied=candidate
        events,_=info
        actions=proposal.get("actions",[])
        if not isinstance(actions,list) or len(actions)!=1:return None
        action=actions[0]
        if not isinstance(action,dict) or type(action.get("frames")) is not int:return None
        key=action.get("button")
        if key in DIR:
            dx,dy=DIR[key];nxt=(f.pos[0]+dx,f.pos[1]+dy)
            unsafe={(e["x"],e["y"]) for e in events if
                    isinstance(e,dict) and e.get("kind") in ("warp","coord")}
            if (not f.passable(*nxt) or nxt in occupied or nxt in unsafe
                    or nxt in blocked_tiles(meta,f.map_id)):return None
            frames=min(16,max(1,action["frames"]))
            return {"scene":"native_guarded_visual",
                    "objective":"Native-validated last-resort visual step",
                    "actions":[{"button":key,"frames":frames}],"review":False}
        if key=="A":
            neighbors={(f.pos[0]+dx,f.pos[1]+dy) for dx,dy in DIR.values()}
            if not any((e.get("x"),e.get("y")) in neighbors
                       and e.get("kind") in ("npc","bg")
                       for e in events if isinstance(e,dict)):return None
            return {"scene":"native_guarded_visual",
                    "objective":"Last-resort interaction with observed native object",
                    "actions":[{"button":"A","frames":5}],"review":False}
        return None

    def next(self,candidate,meta,info):
        goal=meta.get("event_goal")
        if not goal or not info or not candidate:return None
        f,_,occupied=candidate;events,facing=info
        if goal["map"]!=list(f.map_id) or goal["remaining"]<=0 or goal["event"] not in events:return None
        target=tuple(goal["target"]);event=goal["event"]
        warps={(e["x"],e["y"]) for e in events if e["kind"] in ("warp","coord")}
        blocked=blocked_tiles(meta,f.map_id)
        if f.pos==target:
            if (goal.get("retry") and not goal.get("reentered")
                    and event["kind"] in ("warp","coord")):
                # Walking *onto* a trigger is the event, not standing on it.
                # Re-enter via one known safe adjacent tile rather than
                # pressing A or relying on Qwen's guessed directions.
                detour=reentry_neighbor(f,occupied,events,blocked)
                if detour:
                    button,neighbor=detour
                    return ({"scene":"native_event_reentry",
                             "objective":"Re-enter previously attempted native trigger",
                             "actions":[{"button":button,
                                         "frames":probe_frames(meta,f.map_id,neighbor)}],
                             "review":False},("move",neighbor))
                meta.pop("event_goal",None)
                return None
            if event["kind"] in ("warp","coord"):
                # Standing on a native trigger is an attempted arrival,
                # not proof that its script ran or a warp completed.
                attempted=meta.get("event_attempts",[])
                if goal["key"] not in attempted:attempted.append(goal["key"])
                meta["event_attempts"]=attempted[-300:]
                meta.pop("event_goal",None)
                return None
            if event["kind"]=="connection":
                action=event["direction"];expected=None;kind="cross"
            elif facing!=goal["facing"] and not (facing is None and goal.get("face_confirmed")):
                action=goal["facing"];expected=f.pos;kind="face"
            else:action="A";expected=None;kind="interact"
        else:
            path=find_path(f.pos,target,lambda x,y:f.passable(x,y) and (x,y) not in occupied and (x,y) not in blocked and ((x,y) not in warps or (event["kind"] in ("warp","coord") and (x,y)==target)),f.width,f.height)
            if not path:return None
            action=path[0].upper();dx,dy=DIR[action];expected=(f.pos[0]+dx,f.pos[1]+dy);kind="move"
        frames=(probe_frames(meta,f.map_id,expected) if kind=="move" else (1 if action!="A" else 5))
        return {"scene":"native_exploration","objective":("Interact with observed map event" if event["kind"] in ("npc","bg") else "Travel toward observed connection" if event["kind"]=="connection" else "Walk onto observed trigger" if event["kind"]=="coord" else "Approach observed warp"),"actions":[{"button":action,"frames":frames}],"review":False},(kind,expected)
    def scout(self,candidate,meta,info,*,limit=384):
        """Select an unvisited passable native tile, never an unknown event.

        Only corroborated field state and parsed map events authorize a
        movement. Warps and coordinate triggers are reserved for event
        skills, not incidental frontier exploration.
        """
        if not candidate or not info or not self.adapter.verified_field(candidate,meta):
            return None
        f,_,occupied=candidate
        events,_=info
        if not isinstance(events,list):return None
        key=":".join(map(str,f.map_id))
        book=meta.setdefault("native_scout",{"maps":{}})
        maps=book.setdefault("maps",{})
        if key not in maps and len(maps)>=24:
            maps.pop(next(iter(maps)))
        node=maps.setdefault(key,{"visited":[],"moves":0})
        if not isinstance(node,dict):return None
        visited=node.setdefault("visited",[])
        if not isinstance(visited,list):return None
        if list(f.pos) not in visited:visited.append(list(f.pos))
        del visited[:-512]
        moves=node.get("moves",0)
        if type(moves) is not int or not 0<=moves<limit:
            node["status"]="budget_exhausted";return None
        hazards={(e["x"],e["y"]) for e in events if isinstance(e,dict)
            and e.get("kind") in ("warp","coord")
            and type(e.get("x")) is int and type(e.get("y")) is int}
        avoided=set(occupied)|hazards|blocked_tiles(meta,f.map_id)
        seen={tuple(f.pos)}
        queue=deque([(tuple(f.pos),None)])
        selected=None
        while queue:
            pos,first=queue.popleft()
            if pos not in avoided and list(pos) not in visited:
                selected=first
                break
            for direction,(dx,dy) in DIR.items():
                nxt=(pos[0]+dx,pos[1]+dy)
                if nxt in seen or nxt in avoided or not f.passable(*nxt):
                    continue
                seen.add(nxt)
                queue.append((nxt,first or (direction,nxt)))
        if selected is None:
            node["status"]="explored";return None
        direction,step=selected
        node["status"]="surveying"
        return ({"scene":"native_scout",
                 "objective":"Survey a new native-verified walkable tile",
                 "actions":[{"button":direction,
                             "frames":probe_frames(meta,f.map_id,step)}],
                 "review":False},("move",step))

    def finish_scout(self,meta,before,after,command):
        """Mark a scout step only after verified native coordinate movement."""
        if before is None or command is None:return None
        result=record_tile_step(meta,before,after,command,
            verified_before=self.adapter.verified_field(before,meta),
            verified_after=self.adapter.verified_field(after,meta))
        if result=="moved":
            f=before[0]
            node=meta.get("native_scout",{}).get("maps",{}).get(":".join(map(str,f.map_id)))
            if isinstance(node,dict) and after:
                node["moves"]=min(1000000,node.get("moves",0)+1)
                visited=node.setdefault("visited",[])
                pos=list(after[0].pos)
                if pos not in visited:visited.append(pos)
                del visited[:-512]
        return result

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
        trigger=goal["event"].get("kind") in ("warp","coord")
        attempted_entry=(kind=="move" and trigger and
                         expected is not None and
                         tuple(expected)==tuple(goal["target"]))
        if attempted_entry or kind in ("interact","cross"):
            # Reporting a reached tile is not reporting a story transition.
            # These bounded, ROM-neutral witnesses let the remote harness
            # distinguish route failure, script entry, and actual map crossing.
            successor=after[0] if after else None
            same_map=successor is not None and successor.map_id==f.map_id
            status=("unverified_after_input" if successor is None else
                    "map_transition" if not same_map else
                    "trigger_tile_entered" if attempted_entry and
                       tuple(successor.pos)==tuple(goal["target"]) else
                    "interaction_issued" if kind=="interact" else
                    "crossing_issued" if kind=="cross" else
                    "trigger_not_entered")
            witness={"event":goal["key"],"kind":goal["event"]["kind"],
                     "result":status,"decision":meta.get("decisions",0)+1}
            rows=meta.setdefault("native_event_witnesses",[])
            rows.append(witness)
            meta["native_event_witnesses"]=rows[-48:]
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
        if (kind=="face" and after and tuple(after[0].map_id)==tuple(f.map_id)
                and tuple(after[0].pos)==tuple(f.pos)
                and self.adapter.verified_field(after,meta)):
            # Some hacks expose a valid player position but no reliable
            # facing byte. One completed directional tap is sufficient to
            # proceed to A rather than turning forever.
            goal["face_confirmed"]=True
        if (kind=="move" and after and tuple(after[0].map_id)==tuple(f.map_id)
                and tuple(after[0].pos)==tuple(goal["target"])
                and tuple(f.pos)!=tuple(goal["target"]) and goal.get("retry")):
            goal["reentered"]=True
        if kind=="cross":
            meta["pending_crossing"]={"from":list(f.map_id),"destination":goal["event"]["destination"],"event":goal["event"]["id"]}
        if kind in ("interact","cross") or not after or after[0].map_id!=f.map_id or (expected is not None and after[0].pos!=expected):
            attempted=meta.get("event_attempts",[])
            if goal["key"] not in attempted:attempted.append(goal["key"])
            meta["event_attempts"]=attempted[-300:]
            meta.pop("event_goal",None)
        else:
            goal["remaining"]-=1
