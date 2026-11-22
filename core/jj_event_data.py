"""Read-only stock FireRed persistent flag/var table candidate for JJ.

Offsets come from pret/pokefirered include/global.h SaveBlock1:
flags at 0xEE0, 0x120 bytes; vars at 0x1000, 0x200 bytes.
Runtime map/position corroboration is required; unknown hacks may relocate
these tables. No flags/vars, raw bytes, addresses or hashes are reported.
"""
from dataclasses import dataclass
from core.firered import span
from core.jj_fast import SAVE_PTR
from core.live import LiveError

EWRAM_LO=0x02000000
EWRAM_HI=0x02040000
FLAGS_OFFSET=0x0EE0
FLAGS_LENGTH=0x120
VARS_OFFSET=0x1000
VARS_LENGTH=0x200

@dataclass(frozen=True)
class EventData:
    map_id:tuple
    flags:bytes
    variables:bytes
    def flag(self,index):
        # FlagGet(0) is invalid; special flags >=0x4000 are not in save.
        if type(index) is not int or not 1<=index<FLAGS_LENGTH*8:
            raise ValueError("FLAG_OUT_OF_PERSISTENT_RANGE")
        return bool(self.flags[index//8]&(1<<(index&7)))
    def var(self,index):
        # Variables >=0x8000 are special RAM vars and need separate witnesses.
        if type(index) is not int or not 0x4000<=index<0x4000+VARS_LENGTH//2:
            raise ValueError("VAR_OUT_OF_PERSISTENT_RANGE")
        off=(index-0x4000)*2
        return int.from_bytes(self.variables[off:off+2],"little")

def read_event_data(live,field):
    """Read only after a separately verified field/callback/ROM identity."""
    if field is None or len(field.map_id)!=2 or len(field.pos)!=2:
        raise ValueError("FIELD_NOT_VERIFIED")
    save=live.integer(SAVE_PTR,4)
    if (type(save) is not int or save%4 or
            not span(save,VARS_OFFSET+VARS_LENGTH,EWRAM_LO,EWRAM_HI)):
        raise ValueError("SAVE_POINTER_INVALID")
    header=live.read(save,8)
    if len(header)!=8:raise ValueError("SAVE_HEADER_UNREADABLE")
    x,y=(int.from_bytes(header[i:i+2],"little") for i in (0,2))
    if (x,y)!=field.pos or tuple(header[4:6])!=tuple(field.map_id):
        raise ValueError("FIELD_IDENTITY_MISMATCH")
    data=live.read(save+FLAGS_OFFSET,FLAGS_LENGTH+VARS_LENGTH)
    if len(data)!=FLAGS_LENGTH+VARS_LENGTH:raise ValueError("EVENT_DATA_UNREADABLE")
    return EventData(tuple(field.map_id),data[:FLAGS_LENGTH],data[FLAGS_LENGTH:])

def transition_counts(before,after):
    """Observed save-table differences are NOT proof of story completion."""
    if before.map_id!=after.map_id:
        return {"status":"DIFFERENT_MAPS_NO_COMPARISON"}
    raised=cleared=0
    for x,y in zip(before.flags,after.flags):
        raised+=(~x&y&255).bit_count()
        cleared+=(x&~y&255).bit_count()
    changed_vars=sum(before.variables[i:i+2]!=after.variables[i:i+2]
                     for i in range(0,VARS_LENGTH,2))
    return {"status":"STOCK_LAYOUT_CANDIDATE_DELTA",
            "flags_raised":raised,"flags_cleared":cleared,
            "variables_changed":changed_vars,
            "story_completion_verified":False}

def safe_event_data(live,field):
    """Return only unidentifying aggregate evidence in private diagnostics."""
    try:
        snap=read_event_data(live,field)
        return {"status":"STOCK_SAVE_LAYOUT_CANDIDATE",
                "flags_set":sum(b.bit_count() for b in snap.flags),
                "nonzero_variables":sum(snap.variables[i:i+2]!=b"\x00\x00"
                    for i in range(0,VARS_LENGTH,2)),
                "story_completion_verified":False}
    except (ValueError,LiveError,OSError,IndexError,TypeError) as exc:
        code=str(exc) if isinstance(exc,ValueError) else "READ_FAILED"
        if code not in {"FIELD_NOT_VERIFIED","SAVE_POINTER_INVALID",
                        "SAVE_HEADER_UNREADABLE","FIELD_IDENTITY_MISMATCH",
                        "EVENT_DATA_UNREADABLE"}:
            code="READ_FAILED"
        return {"status":"STOCK_SAVE_LAYOUT_REJECTED","reason":code,
                "story_completion_verified":False}
