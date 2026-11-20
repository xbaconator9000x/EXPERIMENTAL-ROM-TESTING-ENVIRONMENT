"""Exact vanilla revision profiles from pret symbol maps, not inferred from headers.

Only known pristine ROM SHA-1 plus local SHA-256 identity are admitted. Modified
ROMs require a separate explicit adapter (JJ remains independently gated).
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
from core.rom_catalog import Catalog
from core.jj_fast import Adapter,decode_party,ordinary_dialogue,u,signed
from core.jj_battle import BattleAdapter,decode_battler,pocket
from core.firered import Profile,Reader,span
from core.live import LiveError

@dataclass(frozen=True)
class Gen3:
    name:str
    sha1:str
    code:bytes
    revision:int
    main:int
    field_cb:int
    battle_cb:int
    command_cb:int
    move_cb:int
    party:int
    party_count:int
    battlers:int
    controllers:int
    flags:int
    action_cursor:int
    move_cursor:int
    disable:int
    outcome:int
    save1:int
    save2:int
    header:int
    vmap:int
    objects:int
    script:int
    lock:int
    money:int
    items:int
    item_count:int
    balls:int
    ball_count:int
    key:int
    tables:tuple
    direct_save:bool=False
    count_width:int=1
    bag_base:int=0
    bag_cb:int=0
    party_cursor:int=0
    party_order:int=0
    party_cb:int=0
    alternate_command_cb:int=0

def frlg(name,sha,code,rev,field_cb,battle_cb,command_cb,move_cb,tables,bag_cb,party_cb):
    return Gen3(name,sha,code,rev,0x030030F0,field_cb,battle_cb,command_cb,move_cb,
        0x02024284,0x02024029,0x02023BE4,0x03004FE0,0x02022B4C,0x02023FF8,
        0x02023FFC,0x02023E0C,0x02023E8A,0x03005008,0x0300500C,0x02036DFC,
        0x03005040,0x02036E38,0x03000EB0,0x03000F9C,0x290,0x310,42,0x430,13,0xf20,tables,
        bag_base=0x0203acfc,bag_cb=bag_cb,party_cursor=0x0203b0a9,
        party_order=0x0203b0dc,party_cb=party_cb,
        alternate_command_cb=0x08030611 if rev==0 else 0x08030625)

FIRERED=frlg("FireRed USA v1.0","41cb23d8dccc8ebd7c649cd8fbb58eeace6e2fdc",b"BPRE",0,
    0x080565B5,0x08011101,0x0802E439,0x0802EA11,(0x245EE0,0x247094,0x250C04,0x254784),0x08107ee1,0x0811eba1)
LEAFGREEN=frlg("LeafGreen USA v1.0","574fa542ffebb14be69902d1d36f1ec0a4afd71e",b"BPGE",0,
    0x080565B5,0x08011101,0x0802E439,0x0802EA11,(0x245EBC,0x247070,0x250BE0,0x254760),0x08107eb9,0x0811eb79)
FIRERED_REV1=frlg("FireRed USA v1.1","dd5945db9b930750cb39d00c84da8571feebf417",b"BPRE",1,
    0x080565C9,0x08011115,0x0802E44D,0x0802EA25,(0x245F50,0x247104,0x250C74,0x2547F4),0x08107f59,0x0811ec19)
LEAFGREEN_REV1=frlg("LeafGreen USA v1.1","7862c67bdecbe21d1d69ce082ce34327e1c6ed5e",b"BPGE",1,
    0x080565C9,0x08011115,0x0802E44D,0x0802EA25,(0x245f2c,0x2470e0,0x250c50,0x2547d0),0x08107f31,0x0811ebf1)
EMERALD=Gen3("Emerald USA v1.0","f3ae088181bf583e55daf962a92bb46f4f1d07b7",b"BPEE",0,
    0x030022C0,0x08085E5D,0x08038421,0x08057589,0x08057BFD,
    0x020244EC,0x020244E9,0x02024084,0x03005D60,0x02022FEC,0x020244AC,
    0x020244B0,0x020242BC,0x0202433A,0x03005D8C,0x03005D90,0x02037318,
    0x03005DC0,0x02037350,0x03000E40,0x03000F2C,0x490,0x560,30,0x650,16,
    0xAC,(0x3185C8,0x31977C,0x31C898,0x3203CC),
    bag_base=0x0203ce58,bag_cb=0x081aad5d,party_cursor=0x0203ced1,party_order=0x0203cf00,party_cb=0x081b01b1)
def rs(name,sha,code,field_cb,tables):
    # RS has fixed save blocks, unencrypted inventory, and IWRAM party/event
    # arrays. Old upstream symbols name the normal action controller
    # sub_802C098 and move controller HandleAction_ChooseMove; their order
    # matches pret/pokeruby battle_controller_player.c.
    return Gen3(name,sha,code,0,0x03001770,field_cb,0x0800f809,0x0802c099,0x0802c68d,
        0x03004360,0x03004350,0x02024a80,0x03004330,0x020239f8,0x02024e60,
        0x02024e64,0x02024ca8,0x02024d26,0x02025734,0x02024ea4,0x0202e828,
        0x03004870,0x030048a0,0x030005b8,0x030006a4,0x490,0x560,20,0x600,16,
        -1,tables,direct_save=True,count_width=4)
RUBY=rs("Ruby USA v1.0","f28b6ffc97847e94a6c21a63cacf633ee5c8df1e",b"AXVE",0x080543a5,
    (0x1f716c,0x1f8320,0x1fb12c,0x1fec18))
SAPPHIRE=rs("Sapphire USA v1.0","3ccbbd45f8553c36463f13b938e833f652b793e4",b"AXPE",0x080543a9,
    (0x1f70fc,0x1f82b0,0x1fb0bc,0x1feba8))
PROFILES=(FIRERED,LEAFGREEN,FIRERED_REV1,LEAFGREEN_REV1,EMERALD,RUBY,SAPPHIRE)

def identify(data,sha):
    if len(data)!=16*1024*1024 or hashlib.sha256(data).hexdigest()!=sha:return None
    digest=hashlib.sha1(data).hexdigest()
    return next((p for p in PROFILES if (p.sha1,p.code,p.revision)==(digest,data[0xac:0xb0],data[0xbc])),None)

def open_profile(rom,sha):
    try:
        path=Path(rom)
        if path.stat().st_size!=16*1024*1024:return None,None
        data=path.read_bytes()
        p=identify(data,sha)
        if p is None:return None,None
        # Known exact cartridge identity allows use of this revision's tables.
        # Still require name, type and aligned pointer anchors in Catalog.
        return p,Catalog(data,layout=p.tables,code=p.code,revision=p.revision)
    except (ValueError,OSError):return None,None

def party_snapshot(live,p):
    count=live.integer(p.party_count,p.count_width)
    if count>6:raise ValueError("party count")
    party=decode_party(live.read(p.party,600))
    if len(party)!=count or [m["slot"] for m in party]!=list(range(count)):
        raise ValueError("party count witness")
    return party

def bag_snapshot(live,p):
    one=p.save1 if p.direct_save else live.integer(p.save1,4)
    two=p.save2 if p.direct_save else live.integer(p.save2,4)
    if one%4 or two%4 or one==two or not span(one,p.balls+p.ball_count*4,0x02000000,0x02040000) or not span(two,max(4,p.key+4),0x02000000,0x02040000):
        raise ValueError("save pointer")
    key=0 if p.key<0 else live.integer(two+p.key,4)
    money=live.integer(one+p.money,4)^key
    if money>999999:raise ValueError("money")
    items=pocket(live.read(one+p.items,p.item_count*4),key&65535)
    balls=pocket(live.read(one+p.balls,p.ball_count*4),key&65535)
    if any(x["id"] not in range(1,13) for x in balls):raise ValueError("ball pocket")
    return {"money":money,"items":items,"balls":balls}

class VanillaField(Adapter):
    def __init__(self,profile,sha):
        self.p=profile;self.sha=sha;self.size=16*1024*1024
        self.admitted=True;self.reason="WAITING_FOR_RUNTIME_WITNESS"
        self.map_header=profile.header;self.objects=profile.objects;self.vmap=profile.vmap

    def candidate(self,rgb):
        p=self.p;l=self.live
        try:
            if l.sha256!=self.sha or l.integer(p.main+4,4)!=p.field_cb:
                self.reason="NOT_FIELD";return None
            if l.integer(p.script,1) or l.integer(p.lock,1) or ordinary_dialogue(rgb):
                self.reason="FIELD_LOCKED";return None
            field=Reader(l,Profile(self.sha,p.save1,p.header,p.vmap,p.main+4,p.field_cb,
                                  ((p.script,1,255,0),(p.lock,1,255,0)),direct_save=p.direct_save)).snapshot()
            raw=l.read(p.objects,576);players=[];occupied=set()
            for i in range(16):
                o=raw[i*36:(i+1)*36];flags=u(o,0,4)
                if not flags&1:continue
                pos=(signed(o,16)-7,signed(o,18)-7)
                if flags&0x10000:
                    if flags&0x100:return None
                    players.append(pos)
                elif 0<=pos[0]<field.width and 0<=pos[1]<field.height:occupied.add(pos)
            if players!=[field.pos]:
                self.reason="PLAYER_POSITION_MISMATCH";return None
            self.reason="FIELD_STRUCTURES_VALID"
            return field,p.field_cb,occupied
        except (LiveError,ValueError,IndexError):
            self.reason="FIELD_READ_REJECTED";return None

    def structured(self,candidate,meta):
        if not self.verified_field(candidate,meta):return None
        f,cb,objects=candidate;x,y=f.pos;left=max(0,x-8);top=max(0,y-6)
        rows=["".join("P" if (i,j)==f.pos else "N" if (i,j) in objects else "." if f.passable(i,j) else "#"
                     for i in range(left,min(left+17,f.width))) for j in range(top,min(top+13,f.height))]
        out={"map":list(f.map_id),"player":list(f.pos),"origin":[left,top],"grid":rows,"legend":"P player,N object,. passable,# blocked"}
        try:out["party"]=party_snapshot(self.live,self.p)
        except (ValueError,LiveError):out["party"]=None
        return out

class VanillaBattle(BattleAdapter):
    def __init__(self,profile,sha,catalog):
        self.p=profile;self.sha=sha;self.catalog=catalog
        self.callbacks={profile.battle_cb,profile.command_cb,profile.move_cb}
        if profile.alternate_command_cb:self.callbacks.add(profile.alternate_command_cb)
        self.field_inventory=True

    def bag(self,live):
        if live.sha256!=self.sha:return None
        try:return bag_snapshot(live,self.p)
        except (ValueError,LiveError):return None

    def snapshot(self,live):
        p=self.p
        try:
            if live.sha256!=self.sha or live.integer(p.main+4,4)!=p.battle_cb:return None
            cb=live.integer(p.controllers,4)
            if cb not in self.callbacks or cb==p.battle_cb:return None
            flags=live.integer(p.flags,4)
            # First-battle flag is allowed for the starter fight, but never catch.
            if flags not in (4,12,20,28):return None
            stage="battle_moves" if cb==p.move_cb else "battle_command"
            cursor=live.integer(p.action_cursor if stage=="battle_command" else p.move_cursor,1)
            if cursor>3:return None
            raw=live.read(p.battlers,176)
            own,enemy=decode_battler(raw[:88]),decode_battler(raw[88:])
            party=party_snapshot(live,p)
            if not own["hp"] or not enemy["hp"] or not any(m["species_id"]==own["species"] and m["level"]==own["level"] and m["max_hp"]==own["max_hp"] for m in party):return None
            disable=live.read(p.disable,12)
            disabled=u(disable,4) if disable[11]&15 else 0
            return {"stage":stage,"cursor":cursor,"callback":cb,"wild":flags==4,
                    "own":own,"enemy":enemy,"party":party,"bag":self.bag(live),"disabled":disabled}
        except (LiveError,ValueError,IndexError):return None
