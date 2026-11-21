"""Read-only transport for actual upstream LeafGreen components.

No memory writes, menu cursor edits, or changes to the running production player.
The first memory profile is vanilla English LeafGreen rev 0 only.
"""
import hashlib
from pathlib import Path
from core.upstream_leafgreen.memory_reader import LeafGreenReader
from core.upstream_leafgreen.tilemap_reader import TilemapReader
from core.upstream_leafgreen.state import GameContext
from core.upstream_leafgreen.pathfinding import find_path
from core.upstream_leafgreen.type_chart import get_effectiveness

LEAFGREEN_SHA1 = "574fa542ffebb14be69902d1d36f1ec0a4afd71e"
UPSTREAM_COMMIT = "594bfc7e3c208890c248269b67c5a1cf95074965"

class PortError(RuntimeError):
    pass

class ReadOnlyClient:
    """Duck-type the upstream read API over the existing native transport."""
    def __init__(self, live):
        self.live = live

    def read_range(self, address, length):
        if type(address) is not int or type(length) is not int or not 0 <= length <= 0x100000:
            raise PortError("invalid memory request")
        if length == 0:
            return b""
        if not any(lo <= address < hi and length <= hi-address for lo,hi in
                   ((0x02000000,0x02040000),(0x03000000,0x03008000),(0x08000000,0x0a000000))):
            raise PortError("read outside bounded GBA memory")
        parts=[]
        for offset in range(0,length,32768):
            n=min(32768,length-offset)
            part=self.live.read(address+offset,n)
            if not isinstance(part,bytes) or len(part)!=n:
                raise PortError("short native read")
            parts.append(part)
        return b"".join(parts)

    def read8(self,address):
        return int.from_bytes(self.read_range(address,1),"little")

    def read16(self,address):
        return int.from_bytes(self.read_range(address,2),"little")

    def read32(self,address):
        return int.from_bytes(self.read_range(address,4),"little")

def admit(rom, live):
    """Reject hacks, other revisions, and mismatched live cartridge identities."""
    path=Path(rom)
    if path.stat().st_size != 16*1024*1024:
        raise PortError("unsupported cartridge size")
    raw=path.read_bytes()
    if (raw[0xac:0xb0]!=b"BPGE" or raw[0xbc]!=0
        or hashlib.sha1(raw).hexdigest()!=LEAFGREEN_SHA1
        or hashlib.sha256(raw).hexdigest()!=live.sha256):
        raise PortError("no verified upstream memory profile for this cartridge")
    return LeafGreenPort(ReadOnlyClient(live))

class LeafGreenPort:
    def __init__(self, client):
        self.reader=LeafGreenReader(client)
        self.tiles=TilemapReader(client)

    def observe(self):
        context=self.reader.detect_context()
        # Unknown, title, fade and menus may expose stale pointers.
        if context not in (GameContext.OVERWORLD,GameContext.IN_BATTLE):
            return {"context":context.name,"state":None}
        state=self.reader.read_state()
        if state.context!=context:
            raise PortError("context changed during observation")
        return {"context":state.context.name,"state":state}

    def route(self,x,y,blocked=()):
        if type(x) is not int or type(y) is not int:
            raise PortError("invalid tile")
        if self.reader.detect_context()!=GameContext.OVERWORLD:
            raise PortError("route requires live overworld")
        if not self.tiles.refresh():
            raise PortError("no live map")
        w,h=self.tiles._width,self.tiles._height
        if not isinstance(w,int) or not isinstance(h,int) or not 0<w<=256 or not 0<h<=256:
            raise PortError("invalid map dimensions")
        grid,w,h=self.tiles.passable_grid()
        if grid is None:
            raise PortError("no collision grid")
        start=self.reader.read_player_pos()
        if not (0<=start[0]<w and 0<=start[1]<h):
            raise PortError("invalid live position")
        blocked=set(blocked)
        return find_path(start,(x,y),lambda a,b: grid[b][a] and (a,b) not in blocked,w,h)

def classic_effectiveness(move_type,defender_types):
    """Actual upstream Gen III chart, not the Modern rules."""
    result=1.0
    for t in set(defender_types):
        result*=get_effectiveness(move_type,t)
    return result
