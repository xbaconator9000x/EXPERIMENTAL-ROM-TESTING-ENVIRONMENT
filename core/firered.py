"""FireRed field ABI reader with externally verified, exact-ROM symbol addresses."""
from dataclasses import dataclass
from core.live import LiveError
from vendor.pokemon_agent.pathfinding import find_path

DIR = {"Right": (16, 1, 0), "Left": (32, -1, 0),
       "Up": (64, 0, -1), "Down": (128, 0, 1)}

@dataclass(frozen=True)
class Profile:
    sha256: str
    saveblock_ptr: int
    map_header: int
    vmap: int
    context_addr: int
    context_value: int
    locks: tuple = ()

@dataclass(frozen=True)
class Field:
    map_id: tuple
    pos: tuple
    width: int
    height: int
    tiles: tuple

    def tile(self,x,y):
        return self.tiles[y*self.width+x]

    def passable(self,x,y):
        if not (0<=x<self.width and 0<=y<self.height):
            return False
        tile=self.tile(x,y)
        return ((tile&0x3ff)!=0x3ff and not (tile&0xc00)
                and (tile>>12) in (0,self.tile(*self.pos)>>12))

def span(a,n,lo,hi):
    return lo<=a<hi and 0<n<=hi-a

class Reader:
    def __init__(self,live,profile):
        if live.sha256!=profile.sha256:
            raise LiveError("profile hash mismatch")
        self.live,self.p=live,profile

    def u(self,a,n):
        return self.live.integer(a,n)

    def snapshot(self):
        p=self.p
        if self.u(p.context_addr,4)!=p.context_value:
            raise LiveError("not in verified field context")
        for address,width,mask,value in p.locks:
            if width not in (1,2,4) or not mask or value&~mask:
                raise LiveError("invalid lock predicate")
            if self.u(address,width)&mask!=value:
                raise LiveError("field locked")
        save=self.u(p.saveblock_ptr,4)
        if save%4 or not span(save,8,0x02000000,0x02040000):
            raise LiveError("invalid saveblock pointer")
        x,y=self.u(save,2),self.u(save+2,2)
        identity=(self.u(save+4,1),self.u(save+5,1))
        layout=self.u(p.map_header,4)
        if layout%4 or not span(layout,8,0x08000000,0x0a000000):
            raise LiveError("invalid map layout pointer")
        w,h=self.u(layout,4),self.u(layout+4,4)
        vw,vh,grid=(self.u(p.vmap+i,4) for i in (0,4,8))
        if not (0<w<=255 and 0<h<=255 and 0<=x<w and 0<=y<h):
            raise LiveError("invalid field dimensions or coordinates")
        if (vw,vh)!=(w+15,h+14) or vw*vh>0x2800:
            raise LiveError("invalid live map dimensions")
        if grid%2 or not span(grid,vw*vh*2,0x02000000,0x02040000):
            raise LiveError("invalid live map pointer")
        raw=self.live.read(grid,vw*vh*2)
        tiles=tuple(int.from_bytes(raw[2*((r+7)*vw+c+7):2*((r+7)*vw+c+7)+2],"little")
                    for r in range(h) for c in range(w))
        return Field(identity,(x,y),w,h,tiles)

def walk(reader,goal,*,max_steps=128,move_frames=1,settle_frames=16):
    """Plain intra-map walking; stop on any unexpected transition."""
    start=reader.snapshot()
    trace=[start.pos]
    if not start.passable(*goal):
        raise LiveError("goal blocked or outside map")
    if start.pos==goal:
        return trace
    for _ in range(max_steps):
        state=reader.snapshot()
        if state.map_id!=start.map_id or state.pos!=trace[-1]:
            raise LiveError("unexpected state before move")
        path=find_path(state.pos,goal,state.passable,state.width,state.height)
        if not path:
            raise LiveError("no bounded route")
        key,dx,dy=DIR[path[0]]
        intended=(state.pos[0]+dx,state.pos[1]+dy)
        reader.live.step(key,move_frames)
        reader.live.step(0,settle_frames)
        after=reader.snapshot()
        if after.map_id!=start.map_id or after.pos!=intended:
            raise LiveError(f"movement mismatch: expected {intended}, observed {after.pos}")
        trace.append(after.pos)
        if after.pos==goal:
            return trace
    raise LiveError("navigation step budget exhausted")
