"""Read-only, exact-release map structure audit for a running Jessie & James hack.

The probed map is NOT declared gameplay-compatible. Addresses and contents
remain on the owner-controlled Windows host.
"""
from core.firered import span
from core.jj_fast import MAP_HEADER
from core.live import LiveError
from core.jj_script_probe import inspect_prefix

ROM_BASE=0x08000000
STRIDES=(24,8,16,12)
NAMES=("objects","warps","coordinates","backgrounds")

def inspect_map(live,rom_size,field,map_header=MAP_HEADER):
    if field is None or not 0<rom_size<=32*1024*1024:
        raise ValueError("UNVERIFIED_FIELD_OR_ROM")
    def romread(ptr,size,align=False):
        if (type(ptr) is not int or (align and ptr%4)
                or not span(ptr,size,ROM_BASE,ROM_BASE+rom_size)):
            raise ValueError("INVALID_ROM_POINTER")
        return live.read(ptr,size)
    def u(data,offset,size=4):
        return int.from_bytes(data[offset:offset+size],"little")
    def tile(data,offset):
        x=u(data,offset,2);y=u(data,offset+2,2)
        if not (0<=x<field.width and 0<=y<field.height):
            raise ValueError("INVALID_EVENT_COORDINATE")
    scripts=0
    nulls=0
    refs=[]
    def script(ptr):
        nonlocal scripts,nulls
        if not ptr:
            nulls+=1
        else:
            romread(ptr,1)
            scripts+=1
            # Keep pointer addresses only in transient local memory.
            if ptr not in refs and len(refs)<8:refs.append(ptr)
    header=live.read(map_header,28)
    if len(header)!=28:raise ValueError("INVALID_MAP_HEADER")
    table=romread(u(header,4),20,True)
    counts=tuple(table[:4])
    if any(x>64 for x in counts):raise ValueError("INVALID_EVENT_COUNT")
    arrays=[romread(u(table,4+i*4),n*STRIDES[i],True) if n else b""
            for i,n in enumerate(counts)]
    unknown=0
    for i in range(counts[0]):
        off=i*24;kind=arrays[0][off+2]
        if kind==0:script(u(arrays[0],off+16))
        elif kind!=1:unknown+=1
    for i in range(counts[1]):tile(arrays[1],i*8)
    for i in range(counts[2]):
        off=i*16;tile(arrays[2],off);script(u(arrays[2],off+12))
    hidden=0
    for i in range(counts[3]):
        off=i*12;tile(arrays[3],off);kind=arrays[3][off+5]
        if kind<=4:script(u(arrays[3],off+8))
        elif kind==7:hidden+=1
        elif kind!=8:unknown+=1
    map_scripts=0
    conditional_map_entries=0
    ptr=u(header,8)
    if ptr:
        for i in range(64):
            row=romread(ptr+i*5,5)
            tag=row[0]
            if tag==0:break
            map_scripts+=1
            destination=u(row,1)
            if tag in (2,4):
                # pret/pokefirered src/script.c: ON_FRAME_TABLE and
                # ON_WARP_INTO_MAP_TABLE point to var-pair tables, NOT
                # directly to executable bytecode. Each 8-byte row contains
                # var1, var2, and a script pointer; zero var1 terminates.
                if not destination:raise ValueError("INVALID_ROM_POINTER")
                for j in range(64):
                    entry=romread(destination+j*8,2)
                    if u(entry,0,2)==0:break
                    entry=romread(destination+j*8,8)
                    conditional_map_entries+=1
                    script(u(entry,4))
                else:raise ValueError("UNTERMINATED_MAP_SCRIPT_TABLE")
            elif tag in (1,3,5,6,7):
                script(destination)
            else:
                unknown+=1
        else:raise ValueError("UNTERMINATED_MAP_SCRIPT_TABLE")
    prefix_status={}
    intent_counts={}
    for reference in refs:
        outcome=inspect_prefix(live,rom_size,reference)
        key=outcome["status"]
        prefix_status[key]=prefix_status.get(key,0)+1
        for feature in outcome["possible_intents"]:
            intent_counts[feature]=intent_counts.get(feature,0)+1
    return {"status":"UNCLASSIFIED_EVENT_KINDS" if unknown else "STRUCTURALLY_READABLE",
            "map":list(field.map_id),"counts":dict(zip(NAMES,counts)),
            "checked_script_pointers":scripts,"null_script_pointers":nulls,
            "hidden_items":hidden,"map_script_entries":map_scripts,
            "conditional_map_script_entries":conditional_map_entries,
            "script_prefixes_sampled":len(refs),
            "script_prefix_stop_reasons":prefix_status,
            "possible_script_intents":intent_counts,
            "unknown_event_kinds":unknown,"script_semantics_verified":False,
            "gameplay_compatibility_verified":False}

def safe_map_audit(live,rom_size,field):
    try:return inspect_map(live,rom_size,field)
    except (ValueError,LiveError,OSError,IndexError,TypeError) as exc:
        code=str(exc) if isinstance(exc,ValueError) else "NATIVE_READ_FAILED"
        if code not in {"UNVERIFIED_FIELD_OR_ROM","INVALID_ROM_POINTER",
                        "INVALID_EVENT_COORDINATE","INVALID_EVENT_COUNT",
                        "INVALID_MAP_HEADER","UNTERMINATED_MAP_SCRIPT_TABLE"}:
            code="NATIVE_READ_FAILED"
        return {"status":"STRUCTURE_READ_FAILED","reason":code,
                "script_semantics_verified":False,"gameplay_compatibility_verified":False}