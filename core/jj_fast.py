"""Jessie & James exact-release deterministic gameplay adapter.

Exact-release gated. Candidate FRLG memory addresses are admitted only if
present in the local cartridge, structurally valid at runtime, and corroborated
by actual movement. Never write RAM, inject flags or use another ROM's callbacks.
"""
import hashlib
import itertools
import struct
from pathlib import Path
from core.firered import Reader, Profile, span
from core.live import LiveError
from vendor.pokemon_agent.pathfinding import find_path

SHA="06d9c87234400f45f1fc3a356881f0ad8bd9b977bc5cbed450e5c7eedd01b632"
SHA_V1033="bb4fd81b32f5e2a69254fc18fbc47e7c7bcbfb35baeace45be2b5dda7876803b"
ADMITTED_SHA256S=frozenset((SHA,SHA_V1033))
SAVE_PTR=0x03005008
MAP_HEADER=0x02036DFC
VMAP=0x03005040
MAIN=0x030030F0
OBJECTS=0x02036E38
SCRIPT=0x03000EB0
SCRIPT_CONTEXT2=0x03000F9C
# Historical import compatibility only. This is not a proven palette-fade
# address; the script-context guard must not be described as screen fading.
FADE=SCRIPT_CONTEXT2
PARTY=0x02024284
BATTLE=0x02023BE4
CTRL=0x03004FE0
DIR={"UP":(0,-1),"DOWN":(0,1),"LEFT":(-1,0),"RIGHT":(1,0)}
KEYS={"UP":64,"DOWN":128,"LEFT":32,"RIGHT":16}
ORDERS=list(itertools.permutations("GAEM"))
def u(raw,offset,size=2):return int.from_bytes(raw[offset:offset+size],"little")
def signed(raw,offset):return int.from_bytes(raw[offset:offset+2],"little",signed=True)

def ordinary_dialogue(rgb):
    """Detect observed orange Gen III textbox border, not dialogue text.
    Refuse additional menu panels, unknown styles and battle split boxes.
    Only recognized full-width field dialogue; never auto-select YES/NO.
    """
    if len(rgb)!=115200:return None
    def colors(y):
        return [tuple(rgb[(y*240+x)*3:(y*240+x)*3+3]) for x in range(240)]
    # Actual v1.03.3 full-width dialogue border is orange RGB (206,82,0).
    # Older detector incorrectly required blue >=25, rejecting every pixel.
    def red(p):return p[0]>=145 and 20<=p[1]<=165 and p[2]<=145 and p[0]>p[1]+50
    def white(p):return min(p)>=232
    def gray(p):return 45<=p[0]<=125 and abs(p[0]-p[1])<=24 and abs(p[1]-p[2])<=24
    def navy(p):return p[0]<=100 and p[1]<=110 and 20<=p[2]<=170 and p[2]>=max(p[0],p[1])+8
    def ink(p):return p[0]<110 and p[1]<110 and p[2]<225
    def run(row,pred):
        best=(0,0);start=None
        for x,p in enumerate(row+[None]):
            if p is not None and pred(p):
                if start is None:start=x
            elif start is not None:
                if x-start>best[1]-best[0]:best=(start,x)
                start=None
        return best
    borders=[]
    for y in range(110,121):
        x0,x1=run(colors(y),red)
        if x1-x0>=180:borders.append((y,x0,x1))
    # A real scaled screenshot can have one thick aligned border scanline,
    # rather than two. The full-width fill, text and lower-edge witnesses
    # below must also pass before an automatic A press is allowed.
    if not borders:return None
    y,x0,x1=borders[0]
    # Field dialogue spans the screen; the centered battle-mode explanation
    # is deliberately left to the planner because it contains setting choices.
    if x0>10 or x1<229:return None
    # Heavily populated second lines of text obscure much of the white body.
    # Require a largely white first interior line plus a meaningful white
    # second line, rather than treating the dark text as missing dialogue.
    white_box=(sum(white(p) for p in colors(125)[12:228])>=150
               and sum(white(p) for p in colors(147)[12:228])>=75)
    navy_box=(sum(navy(p) for p in colors(125)[12:228])>=150
              and sum(navy(p) for p in colors(147)[12:228])>=75)
    if not white_box and not navy_box:return None
    # Original script dialogue uses a white body; Jessie & James v1.03.3 also
    # uses a dark-blue interior with white glyphs. Require a full-width lower
    # backing edge to reject transitional animation and partial windows.
    # An authentic v1.03.3 scripted field reminder has a
    # near-black lower border. Earlier checks only admitted gray/navy
    # borders, misclassifying this actual scripted message as field.
    def lower_edge(i):
        row=colors(i)
        outside=row[0]
        # Dark pixels count only if they form an actual window edge,
        # not the identical dark overworld/background behind a vanished box.
        return sum(gray(p) or navy(p) or
                   (ink(p) and sum(abs(a-b) for a,b in zip(p,outside))>=18)
                   for p in row[x0+3:x1-3])
    if not any(lower_edge(i)>=175 for i in range(152,160)):return None
    # Refuse an empty/opening dialogue box: A might become an interaction or a
    # menu confirmation after a text animation has cleared.
    glyphs=sum(sum(white(p) if navy_box else ink(p) for p in colors(i)[15:225])
               for i in range(123,149,2))
    if glyphs<12:return None
    # Additional colored/white panel above the dialogue (Yes/No, choice menu,
    # list, battle menu). Require two spaced orange horizontal runs over white.
    for row in range(0,105):
        lo,hi=run(colors(row),red)
        if hi-lo>=24 and row+7<112 and sum(white(p) or navy(p) for p in colors(row+7)[lo:hi])>=max(12,(hi-lo)//2):
            return None
    # A separate white panel without the orange frame is also ambiguous.
    for row in range(8,106,4):
        lo,hi=run(colors(row),white)
        # Non-framed choice panels are typically at the top-right. A wide
        # white bed, wall or window in the map is NOT a dialogue choice.
        if lo>=155 and hi>=200 and hi-lo>=36 and row+8<110 and sum(white(p) for p in colors(row+8)[lo:hi])>=hi-lo-5:
            return None
    # Text region only; exclude animated map background from stall identity.
    text=b"".join(rgb[(i*240+12)*3:(i*240+228)*3] for i in range(121,151))
    return hashlib.sha256(text).hexdigest()

def decode_party(raw):
    """Read-only Gen III XOR + checksum verification. Never trust corrupt slots."""
    if len(raw)!=600:raise ValueError("party length")
    result=[]
    for slot in range(6):
        b=raw[slot*100:(slot+1)*100]
        level=b[84]
        if level==0:continue
        key=u(b,0,4)^u(b,4,4)
        plain=b"".join((u(b,i,4)^key).to_bytes(4,"little") for i in range(32,80,4))
        if sum(u(plain,i) for i in range(0,48,2))&0xffff!=u(b,28):raise ValueError("party checksum")
        parts={letter:plain[i*12:i*12+12] for i,letter in enumerate(ORDERS[u(b,0,4)%24])}
        species=u(parts["G"],0);moves=[u(parts["A"],2*i) for i in range(4)]
        hp,mx=u(b,86),u(b,88)
        if not 1<=species<=411 or not 1<=level<=100 or not 0<=hp<=mx<=999 or mx==0 or any(m>559 for m in moves) or any(p>64 for p in parts["A"][8:12]):
            raise ValueError("party structure")
        if b[19]&1:raise ValueError("bad egg flag")
        result.append({"slot":slot,"species_id":species,"level":level,"hp":hp,"max_hp":mx,"moves":moves,"pp":list(parts["A"][8:12]),"status":u(b,80,4)})
    return result

class Adapter:
    def __init__(self,rom,sha):
        self.size=0;self.admitted=False;self.reason="ROM_NOT_ADMITTED";self.sha=sha;self.lock_probe=None
        if sha not in ADMITTED_SHA256S:return
        data=Path(rom).read_bytes();self.size=len(data)
        if hashlib.sha256(data).hexdigest()!=sha or data[0xac:0xb0]!=b"BPRE" or data[0xbc]!=0:return
        # Candidate address literals must exist aligned in the executable area.
        def anchored(addr):
            needle=addr.to_bytes(4,"little");i=data.find(needle,0,min(len(data),0x160000))
            while i>=0:
                if i%4==0:return True
                i=data.find(needle,i+1,min(len(data),0x160000))
            return False
        self.admitted=all(anchored(x) for x in (SAVE_PTR,MAP_HEADER,VMAP,MAIN,OBJECTS,SCRIPT,FADE,PARTY))
    def attach(self,live):
        self.live=live
    def candidate(self,rgb):
        meta=getattr(self,"meta",None)
        self.lock_probe=None
        if not self.admitted:return None
        if ordinary_dialogue(rgb):self.reason="DIALOGUE_ACTIVE";return None
        l=self.live
        try:
            cb=l.integer(MAIN+4,4)
            if not cb&1 or not span(cb&~1,2,0x08000000,0x08000000+self.size):self.reason="CALLBACK_INVALID";return None
            script_active=l.integer(SCRIPT,1)!=0
            context2_active=l.integer(SCRIPT_CONTEXT2,1)!=0
            # Both probes are script/field-control state, not palette-fade
            # evidence. A real story reminder is allowed to lock movement;
            # the dialogue handler must advance that message instead.
            self.lock_probe={"script_active":script_active,"script_context2_active":context2_active}
            # This release can leave SCRIPT nonzero even when the operator
            # demonstrably moved on a previously verified map. Do not turn
            # that single byte into an indefinite wait. Re-admit ONLY after
            # a guarded operator input plus recent native field witnesses,
            # or an already re-admitted map/callback. Context2 still locks.
            token=meta.get("stale_script_field") if isinstance(meta,dict) else None
            trusted_token=(isinstance(token,dict) and token.get("callback")==cb)
            witnessed=False
            if (script_active and not context2_active and not trusted_token
                    and isinstance(meta,dict) and meta.get("operator_last_action")=="input"):
                previous=meta.get("last_native_field")
                now=meta.get("decisions")
                rows=meta.get("history",[])
                if (isinstance(previous,dict) and isinstance(previous.get("map"),list)
                        and isinstance(previous.get("pos"),list) and type(now) is int
                        and isinstance(rows,list)):
                    positions=set()
                    for h in rows[-32:]:
                        if not isinstance(h,dict) or h.get("source")!="native_explore":continue
                        f=h.get("field_after")
                        d=h.get("decision")
                        if (isinstance(f,dict) and f.get("map")==previous["map"]
                                and isinstance(f.get("pos"),list) and len(f["pos"])==2
                                and type(d) is int and 0<=now-d<=32):
                            positions.add(tuple(f["pos"]))
                    witnessed=len(positions)>=2
            bypass=bool(script_active and not context2_active and (trusted_token or witnessed))
            if context2_active or (script_active and not bypass):
                self.reason="SCRIPT_CONTROL_LOCK";return None
            locks=((SCRIPT_CONTEXT2,1,255,0),) if bypass else ((SCRIPT,1,255,0),(SCRIPT_CONTEXT2,1,255,0))
            p=Profile(self.sha,SAVE_PTR,MAP_HEADER,VMAP,MAIN+4,cb,locks)
            field=Reader(l,p).snapshot()
            if bypass:
                if trusted_token:
                    permitted=token.get("map")==list(field.map_id)
                else:
                    previous=meta["last_native_field"]
                    permitted=(previous["map"]==list(field.map_id)
                               and previous["pos"]!=list(field.pos))
                if not permitted:
                    self.reason="SCRIPT_CONTROL_LOCK";return None
            objects=l.read(OBJECTS,36*16)
            players=[];occupied=set()
            for i in range(16):
                o=objects[i*36:(i+1)*36];flags=u(o,0,4)
                if not flags&1:continue
                x,y=signed(o,16)-7,signed(o,18)-7
                if flags&0x10000:
                    if flags&0x100:self.reason="PLAYER_FROZEN";return None
                    players.append((x,y))
                elif 0<=x<field.width and 0<=y<field.height:occupied.add((x,y))
            if players!=[field.pos]:self.reason="PLAYER_POSITION_MISMATCH";return None
            if bypass:
                if not trusted_token:
                    meta["stale_script_field"]={"callback":cb,"map":list(field.map_id),
                        "source":"operator_input_plus_native_movement"}
                self.reason="FIELD_STRUCTURES_VALID_STALE_SCRIPT_BYTE"
            else:
                self.reason="FIELD_STRUCTURES_VALID"
            return field,cb,occupied
        except (LiveError,ValueError,IndexError):self.reason="FIELD_READ_REJECTED";return None
    def observe_move(self,before,after,actions,meta):
        if not before or not after or len(actions)!=1:return
        f,cb,_=before;g,cb2,_=after
        direction=actions[0]["button"]
        if direction not in DIR or cb!=cb2 or f.map_id!=g.map_id:return
        dx,dy=DIR[direction]
        if g.pos!=(f.pos[0]+dx,f.pos[1]+dy):return
        proof=meta.setdefault("field_proof",{"callback":cb,"directions":[]})
        if proof.get("callback")!=cb:proof={"callback":cb,"directions":[]};meta["field_proof"]=proof
        if direction not in proof["directions"]:proof["directions"].append(direction)
    def verified_field(self,candidate,meta):
        if not candidate:return False
        proof=meta.get("field_proof",{})
        if candidate[1]==proof.get("callback") and len(set(proof.get("directions",[])))>=2:return True
        # An operator-recovered field is verified by independently witnessed
        # native steps plus a changed, fully checked player position. Only the
        # SAME admitted map/callback can reuse it; no other field inherits it.
        recovered=meta.get("stale_script_field",{})
        return bool(isinstance(recovered,dict) and
                    recovered.get("callback")==candidate[1] and
                    recovered.get("map")==list(candidate[0].map_id))
    def structured(self,candidate,meta):
        if not self.verified_field(candidate,meta):return None
        f,cb,objects=candidate
        # Bound planner grid while keeping actual coordinates.
        x,y=f.pos;left=max(0,x-8);top=max(0,y-6)
        rows=[]
        for j in range(top,min(top+13,f.height)):
            rows.append("".join("P" if (i,j)==f.pos else "N" if (i,j) in objects else "." if f.passable(i,j) else "#" for i in range(left,min(left+17,f.width))))
        out={"map":list(f.map_id),"player":list(f.pos),"origin":[left,top],"grid":rows,"legend":"P player,N object,. passable,# blocked"}
        try:out["party"]=decode_party(self.live.read(PARTY,600))
        except (ValueError,LiveError):out["party"]=None
        return out
    def route_action(self,candidate,meta):
        if not self.verified_field(candidate,meta):return None
        route=meta.get("native_route")
        f,cb,objects=candidate
        if not route or route.get("map")!=list(f.map_id) or route.get("remaining",0)<=0:return None
        target=tuple(route["target"])
        path=find_path(f.pos,target,lambda x,y:f.passable(x,y) and (x,y) not in objects,f.width,f.height)
        if not path:return None
        button=path[0].upper();dx,dy=DIR[button]
        return {"scene":"native_field","objective":"Navigate to "+str(target),"actions":[{"button":button,"frames":1}],"review":False},(f.pos[0]+dx,f.pos[1]+dy)
    def start_route(self,candidate,meta,target):
        if not self.verified_field(candidate,meta) or type(target) is not list or len(target)!=2 or any(type(x) is not int for x in target):return False
        f,cb,objects=candidate
        if not f.passable(*target) or tuple(target) in objects:return False
        path=find_path(f.pos,tuple(target),lambda x,y:f.passable(x,y) and (x,y) not in objects,f.width,f.height)
        if not path:return False
        meta["native_route"]={"map":list(f.map_id),"target":target,"remaining":min(64,len(path)+2)}
        return True

def quick_dialogue(rgb,meta):
    page=ordinary_dialogue(rgb)
    if not page:return None
    history=meta.get("history",[])
    if any(h.get("dialogue_page")==page and h.get("before")==h.get("after") for h in history[-5:]):return None
    recent=0
    for h in reversed(history):
        if h.get("source")!="fast_dialogue":break
        recent+=1
    # Batch up to ten independently witnessed pages, then require a new
    # strategic interpretation. Each press is checkpointed; never send ten
    # unobserved A presses or auto-select YES/NO options.
    if recent>=10:return None
    return {"scene":"native_dialogue","objective":"Advance recognized ordinary dialogue page","actions":[{"button":"A","frames":5}],"review":False},page
