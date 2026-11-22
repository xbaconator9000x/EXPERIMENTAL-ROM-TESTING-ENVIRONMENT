"""Empirical, per-map tile navigation memory for verified native movement.

Inspired by the *concept* of bump learning in pokemon-agent-os; no upstream
code is copied. Source of truth is independently verified GBA field coordinates,
not changed screenshot pixels or a model's description of a wall.

One inconclusive one-frame movement attempt must NOT teach a collision:
the controller retries that single step with a longer, bounded d-pad hold.
Two confirmed, unchanged steps to the same destination mark it temporarily
avoided by A*. A later verified arrival unblocks the tile.
"""
from core.jj_world_model import map_key

MAX_MAPS=48
MAX_TILES_PER_MAP=96
BLOCK_AFTER=2
LONGER_PROBE_FRAMES=12


def _tile(pos):
    if (not isinstance(pos,(list,tuple)) or len(pos)!=2
            or any(type(n) is not int or not 0<=n<256 for n in pos)):
        return None
    return f"{pos[0]}:{pos[1]}"


def _book(meta,create=False):
    book=meta.get("tile_observations")
    if isinstance(book,dict) and book.get("version")==1 and isinstance(book.get("maps"),dict):
        return book
    if not create:return None
    book={"version":1,"maps":{}}
    meta["tile_observations"]=book
    return book


def _map(meta,map_id,create=False):
    k=map_key(map_id)
    if k is None:return None
    book=_book(meta,create)
    if book is None:return None
    states=book["maps"]
    node=states.get(k)
    if not isinstance(node,dict):
        if not create:return None
        node={"attempts":{}}
    if not isinstance(node.get("attempts"),dict):
        if not create:return None
        node={"attempts":{}}
    if create:
        states.pop(k,None)
        states[k]=node
        while len(states)>MAX_MAPS:states.pop(next(iter(states)))
    return node


def failures(meta,map_id,destination):
    node=_map(meta,map_id)
    key=_tile(destination)
    if node is None or key is None:return 0
    value=node["attempts"].get(key,0)
    return value if type(value) is int and 0<=value<=BLOCK_AFTER else 0


def blocked_tiles(meta,map_id):
    node=_map(meta,map_id)
    if node is None:return set()
    out=set()
    for key,val in node["attempts"].items():
        if type(val) is not int or val<BLOCK_AFTER:continue
        try:x,y=(int(v) for v in key.split(":"))
        except (TypeError,ValueError,AttributeError):continue
        if _tile((x,y))==key:out.add((x,y))
    return out


def probe_frames(meta,map_id,destination):
    return LONGER_PROBE_FRAMES if failures(meta,map_id,destination)==1 else 1


def confirm_native_position(meta,map_id,pos,*,verified):
    """A verified player location overrides provisional bump evidence.

    In particular, a scripted warp may already have been entered by the
    player or an operator; stale two-bump memory must never prevent the
    native planner from stepping off and back onto that same trigger.
    Screenshots alone cannot authorize this correction.
    """
    if not verified:return False
    node=_map(meta,map_id)
    key=_tile(pos)
    if node is None or key is None:return False
    return node["attempts"].pop(key,None) is not None


def record(meta,before,after,command,*,verified_before,verified_after):
    """Return 'retry', 'blocked', 'moved' or None; never create evidence on a lock.

    The check excludes turns that merely rotate, battle/menu/script interruptions,
    unverified callbacks, map changes, unknown movement, or diagonal jumps.
    """
    if (not verified_before or not verified_after or not before or not after
            or not isinstance(command,tuple) or len(command)!=2
            or command[0]!="move"):
        return None
    try:
        f,callback,_=before;g,after_callback,_=after
        expected=tuple(command[1])
        map_id=map_key(f.map_id)
        if (map_id is None or tuple(f.map_id)!=tuple(g.map_id)
                or type(callback) is not int or callback!=after_callback
                or _tile(expected) is None
                or abs(expected[0]-f.pos[0])+abs(expected[1]-f.pos[1])!=1
                or not 0<=expected[0]<f.width or not 0<=expected[1]<f.height
                or not f.passable(*expected)):
            return None
    except (AttributeError,ValueError,TypeError,IndexError):
        return None
    if tuple(g.pos)!=tuple(f.pos) and tuple(g.pos)!=expected:return None
    node=_map(meta,f.map_id,create=True)
    attempts=node["attempts"]
    key=_tile(expected)
    if tuple(g.pos)==expected:
        attempts.pop(key,None)
        # Successful real movement supersedes a previous provisional bump.
        return "moved"
    value=attempts.get(key,0)
    n=min(BLOCK_AFTER,(value if type(value) is int and 0<=value<=BLOCK_AFTER else 0)+1)
    attempts.pop(key,None)
    attempts[key]=n
    while len(attempts)>MAX_TILES_PER_MAP:attempts.pop(next(iter(attempts)))
    return "blocked" if n>=BLOCK_AFTER else "retry"


def refresh_on_verified_arrival(meta,previous_map,new_map,*,verified):
    """Reset provisional obstacle assumptions on a genuinely different map.

    NPCs, event flags and scripted blockers can move or change between visits.
    A previous collision is not permanent ROM tile metadata. A same-map
    screenshot change or unverified fade cannot clear observations.
    """
    before,after=map_key(previous_map),map_key(new_map)
    if not verified or before is None or after is None or before==after:
        return False
    book=_book(meta)
    if book is None:return False
    return book["maps"].pop(after,None) is not None


def diagnostics(meta):
    book=_book(meta)
    if not book:return {"maps":0,"blocked_tiles":0,"probing_tiles":0}
    states=book["maps"]
    return {"maps":len(states),
            "blocked_tiles":sum(v>=BLOCK_AFTER for node in states.values()
                 if isinstance(node,dict) for v in node.get("attempts",{}).values()
                 if type(v) is int),
            "probing_tiles":sum(v==1 for node in states.values()
                 if isinstance(node,dict) for v in node.get("attempts",{}).values()
                 if type(v) is int)}
