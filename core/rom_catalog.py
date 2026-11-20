"""Optional read-only FireRed BPRE v0 cartridge lookup.

Public layout reference: pret/pokefirered include/pokemon.h and
https://datacrystal.tcrf.net/wiki/Pok%C3%A9mon_3rd_Generation .
The layout is a candidate, not a runtime symbol map; validate anchors and
pointer use before enabling it. Use Classic only on the admitted release.
No ROM bytes are transmitted, no RAM addresses are guessed.
"""
import hashlib
import re
from pathlib import Path

JJ="06d9c87234400f45f1fc3a356881f0ad8bd9b977bc5cbed450e5c7eedd01b632"
SPECIES_NAMES=0x245EE0
MOVE_NAMES=0x247094
MOVE_DATA=0x250C04
SPECIES_DATA=0x254784
TYPES=("normal","fighting","flying","poison","ground","rock","bug","ghost","steel",None,"fire","water","grass","electric","psychic","ice","dragon","dark")
# Exact names and expected anchor *types*, not hard-coded move power.
SPECIES_ANCHORS={1:("BULBASAUR",("grass","poison")),4:("CHARMANDER",("fire",)),7:("SQUIRTLE",("water",)),25:("PIKACHU",("electric",)),19:("RATTATA",("normal",))}
MOVE_ANCHORS={1:("POUND","normal"),2:("KARATE CHOP","fighting"),33:("TACKLE","normal"),52:("EMBER","fire"),55:("WATER GUN","water"),85:("THUNDERBOLT","electric")}
TABLES=(SPECIES_NAMES,MOVE_NAMES,MOVE_DATA,SPECIES_DATA)

def name_key(s):return re.sub(r"[^A-Z0-9]","",s.upper()) if isinstance(s,str) else ""

def decode_name(raw):
    out=[]
    for x in raw:
        if x==255:return "".join(out).strip()
        if 0xBB<=x<=0xD4:out.append(chr(65+x-0xBB))
        elif 0xD5<=x<=0xEE:out.append(chr(97+x-0xD5))
        elif 0xA1<=x<=0xAA:out.append(chr(48+x-0xA1))
        elif x==0:out.append(" ")
        elif x==0xAE:out.append("-")
        elif x in (0xB5,0xB6):continue
        else:return ""
    return ""

def read_name(rom,base,stride,index):
    i=base+index*stride
    return decode_name(rom[i:i+stride])

def species_row(rom,index):
    i=SPECIES_DATA+index*28;b=rom[i:i+28]
    if len(b)!=28 or any(x==0 for x in b[:6]) or max(b[6:8])>=len(TYPES) or any(TYPES[x] is None for x in b[6:8]):return None
    return list(dict.fromkeys(TYPES[x] for x in b[6:8]))

def move_row(rom,index):
    i=MOVE_DATA+index*12;b=rom[i:i+12]
    if len(b)!=12 or b[2]>=len(TYPES) or TYPES[b[2]] is None or b[3]>100 or not 1<=b[4]<=64:return None
    return {"type":TYPES[b[2]],"power":b[1],"accuracy":b[3] or 100}

def table_referenced(rom,offset):
    # At least one aligned pointer to the candidate legacy table.
    needle=(0x08000000+offset).to_bytes(4,"little")
    i=rom.find(needle)
    while i>=0:
        if i%4==0:return True
        i=rom.find(needle,i+1)
    return False

class Catalog:
    def __init__(self,rom):
        if len(rom)<SPECIES_DATA+412*28 or rom[0xAC:0xB0]!=b"BPRE" or rom[0xBC]!=0:
            raise ValueError("Not a supported candidate FireRed layout")
        if not all(table_referenced(rom,x) for x in TABLES):
            raise ValueError("No live-layout pointer witnesses")
        for i,(name,types) in SPECIES_ANCHORS.items():
            if name_key(read_name(rom,SPECIES_NAMES,11,i))!=name_key(name) or set(species_row(rom,i) or [])!=set(types):
                raise ValueError("Species table anchor mismatch")
        for i,(name,t) in MOVE_ANCHORS.items():
            row=move_row(rom,i)
            if name_key(read_name(rom,MOVE_NAMES,13,i))!=name_key(name) or not row or row["type"]!=t or not row["power"]:
                raise ValueError("Move table anchor mismatch")
        self.species={};self.moves={}
        for i in range(1,412):
            name=name_key(read_name(rom,SPECIES_NAMES,11,i));row=species_row(rom,i)
            if name and row:self.species[name]=row if name not in self.species else None
        for i in range(1,355):
            name=name_key(read_name(rom,MOVE_NAMES,13,i));row=move_row(rom,i)
            if name and row:self.moves[name]=row if name not in self.moves else None

    def enrich(self,obs):
        if obs.get("stage") not in ("battle_command","battle_moves","bag","party"):return obs
        out=dict(obs)
        for name,field in (("enemy","enemy_types"),("own","own_types")):
            types=self.species.get(name_key(out.get(name)))
            # A visible type disagreement may signal transform, changed types,
            # or incompatible variant: do not overwrite conflicting evidence.
            if types and not out.get(field):out[field]=types
        if "moves" in out:
            rows=[]
            for m in out["moves"]:
                data=self.moves.get(name_key(m["name"]))
                if data:
                    row={**m,**data}
                    # No base PP substitution; current PP must come from screen.
                    rows.append(row)
                else:rows.append(m)
            out["moves"]=rows
        return out

def try_catalog(path,sha,goal):
    if sha!=JJ or "classic" not in goal.lower() or "modern" in goal.lower():return None
    try:
        p=Path(path)
        if not 0<p.stat().st_size<=32*1024*1024:return None
        rom=p.read_bytes()
        if hashlib.sha256(rom).hexdigest()!=sha:return None
        return Catalog(rom)
    except (ValueError,OSError):return None
