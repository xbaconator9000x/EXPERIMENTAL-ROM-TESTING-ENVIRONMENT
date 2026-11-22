"""Intent-bound native inventory and party menu navigation, using keys only.

Menu ABI candidates must be independently corroborated by a visible list and
cursor. A native confirmation is single-use: any USE/SHIFT/item-target submenu
is returned to the vision planner instead of replaying A on stale RAM.
"""
import hashlib
from pathlib import Path
from core.jj_battle import anchors,health_percent
from core.jj_fast import ADMITTED_SHA256S,MAIN,PARTY,decode_party,u
from core.party_knowledge import choose_verified_switch
from core.firered import span
from core.live import LiveError

BAG=0x0203ACFC
PARTY_CURSOR=0x0203B0A9
PARTY_ORDER=0x0203B0DC
PARTY_CB=0x0811EB79
PARTY_FP="2bd014f08c25409d05f6e6fe86a7e688824d3892b4dec5eab4c8d5241f7d85ad"
HEAL={13:20,22:50,21:200,20:999,19:999}
BALL={4:1,3:1.5,2:2}

def select_item(bag,purpose,missing=0):
    if not bag:return None
    if purpose=="catch":
        rows=[x for x in bag["balls"] if x["id"] in BALL and x["count"]>0]
        return max(rows,key=lambda x:BALL[x["id"]])["id"] if rows else None
    if purpose=="heal" and missing>0:
        rows=[x for x in bag["items"] if x["id"] in HEAL and x["count"]>0]
        if rows:
            return min(rows,key=lambda x:(HEAL[x["id"]]<missing,HEAL[x["id"]] if HEAL[x["id"]]>=missing else -HEAL[x["id"]],x["id"]==19))["id"]
    return None

def decode_order(raw):
    if len(raw)!=3:raise ValueError("party order size")
    order=[v for x in raw for v in (x>>4,x&15)]
    if sorted(order)!=list(range(6)):raise ValueError("party order")
    return order

def decode_bag(raw,inventory):
    if len(raw)!=20 or not inventory or raw[4]!=5 or raw[5]!=1:raise ValueError("not battle bag")
    pocket=u(raw,6)
    if pocket not in (0,2):raise ValueError("unsupported pocket")
    # Verified candidate position arrays: scroll + displayed row.
    row=u(raw,8+2*pocket);scroll=u(raw,14+2*pocket)
    # Some revisions order these arrays inversely; sum is invariant.
    rows=inventory["items" if pocket==0 else "balls"]
    cursor=row+scroll
    if row>42 or scroll>42 or cursor>len(rows):raise ValueError("bag position")
    return {"stage":"bag","pocket":pocket,"cursor":cursor,"rows":rows}

def decode_emerald_bag(raw,inventory):
    """Emerald BagPosition: 5 pockets, location byte, independent u16 arrays."""
    if len(raw)!=28 or not inventory or raw[4]!=1:raise ValueError("not battle bag")
    pocket=raw[5]
    if pocket not in (0,1):raise ValueError("unsupported pocket")
    row=u(raw,8+2*pocket);scroll=u(raw,18+2*pocket)
    rows=inventory["items" if pocket==0 else "balls"]
    cursor=row+scroll
    if row>30 or scroll>30 or cursor>len(rows):raise ValueError("bag position")
    # Normalize pocket to existing driver's internal semantic code.
    return {"stage":"bag","pocket":0 if pocket==0 else 2,"cursor":cursor,"rows":rows}

def intent_from_battle(state,decision,catalog=None):
    if not state or state["stage"]!="battle_command" or decision["actions"]!=[{"button":"A","frames":5}]:return None
    reason=decision["objective"]
    own=state["own"]
    if state["cursor"]==1 and reason=="Open bag to heal":
        item=select_item(state["bag"],"heal",own["max_hp"]-own["hp"])
        if item:return {"purpose":"heal","item":item,"active":own["species"],"remaining":16,"phase":"list"}
    elif state["cursor"]==1 and reason=="Open bag to catch a new wild Pokémon" and state["wild"]:
        item=select_item(state["bag"],"catch")
        if item:return {"purpose":"catch","item":item,"active":own["species"],"remaining":16,"phase":"list"}
    elif state["cursor"]==2 and reason=="Open party to switch safely":
        target=choose_verified_switch(state["party"],own["species"],state["enemy"],catalog)
        if target:
            return {"purpose":"switch","slot":target["slot"],"active":own["species"],"remaining":12,"phase":"list"}
    return None

class MenuDriver:
    def __init__(self,rom,sha,battle):
        self.battle=battle;self.bag_ok=False;self.party_ok=False;self.rom_size=0
        self.profile=getattr(battle,"p",None)
        self.main=MAIN;self.bag_base=BAG;self.bag_cb=None
        self.party_cb=PARTY_CB;self.party_cursor=PARTY_CURSOR;self.party_order=PARTY_ORDER
        if self.profile:
            p=self.profile
            # Caller admits a byte-identical vanilla revision through open_profile.
            self.main=p.main;self.bag_base=p.bag_base;self.bag_cb=p.bag_cb
            self.party_cb=p.party_cb;self.party_cursor=p.party_cursor;self.party_order=p.party_order
            self.rom_size=16*1024*1024
            self.bag_ok=bool(p.bag_base and p.bag_cb)
            self.party_ok=bool(p.party_cursor and p.party_order and p.party_cb)
            self.sha=sha
            return
        if sha not in ADMITTED_SHA256S or not battle.callbacks:return
        try:
            data=Path(rom).read_bytes();self.rom_size=len(data)
            if hashlib.sha256(data).hexdigest()!=sha:return
            self.bag_ok=anchors(data,(BAG,))
            i=(PARTY_CB&~1)-0x08000000
            self.party_ok=anchors(data,(PARTY_CURSOR,PARTY_ORDER)) and hashlib.sha256(data[i:i+32]).hexdigest()==PARTY_FP
        except (ValueError,OSError):return

    def snapshot(self,live,meta):
        intent=meta.get("menu_intent")
        if not intent or intent.get("phase")!="list" or intent.get("remaining",0)<=0:return None
        try:
            if self.profile and live.sha256!=self.sha:return None
            cb=live.integer(self.main+4,4)
            if not cb&1 or not span(cb&~1,2,0x08000000,0x08000000+self.rom_size) or cb in self.battle.callbacks:return None
            if intent["purpose"] in ("heal","catch") and self.bag_ok:
                if self.bag_cb and cb!=self.bag_cb:return None
                if self.profile and self.profile.code==b"BPEE":
                    s=decode_emerald_bag(live.read(self.bag_base,28),self.battle.bag(live))
                else:s=decode_bag(live.read(self.bag_base,20),self.battle.bag(live))
            elif intent["purpose"]=="switch" and self.party_ok and cb==self.party_cb:
                order=decode_order(live.read(self.party_order,3))
                cursor=live.integer(self.party_cursor,1)
                if self.profile:
                    from core.gen3_profiles import party_snapshot
                    party=party_snapshot(live,self.profile)
                else:party=decode_party(live.read(PARTY,600))
                slots={p["slot"]:p for p in party}
                if cursor>=len(party) or intent["slot"] not in slots or slots[intent["slot"]]["hp"]==0:return None
                if any(i not in slots for i in order[:len(party)]):return None
                s={"stage":"party","cursor":cursor,"target":order.index(intent["slot"]),"count":len(party)}
            else:return None
            s["callback"]=cb;return s
        except (LiveError,ValueError,KeyError):return None

    def corroborate(self,s,obs,meta):
        # A fresh intent must obtain its own screen witness. No stale callback
        # proof from a previous use. Bag witness checks actual pocket contents.
        intent=meta.get("menu_intent")
        if not intent or not s or obs.get("stage")!=s["stage"] or obs.get("list_cursor")!=s["cursor"]:return
        if s["stage"]=="bag":
            rows=obs.get("items",[])
            if not rows or s["cursor"]>=len(s["rows"]):return
            visible=next((x for x in rows if x["slot"]==s["cursor"]),None)
            if not visible or visible.get("count")!=s["rows"][s["cursor"]]["count"]:return
            # Confirm the actual pocket from a known item name, not count alone.
            def norm(x):return x.lower().replace("é","e").replace(" ","")
            names={2:"ultraball",3:"greatball",4:"pokeball",13:"potion",19:"fullrestore",20:"maxpotion",21:"hyperpotion",22:"superpotion"}
            if names.get(s["rows"][s["cursor"]]["id"])!=norm(visible["name"]):return
        intent["callback"]=s["callback"]

    def action(self,s,meta):
        intent=meta.get("menu_intent")
        if not intent or not s or intent.get("callback")!=s["callback"] or intent.get("phase")!="list":return None
        if s["stage"]=="bag":
            pocket=2 if intent["purpose"]=="catch" else 0
            # Wrong pocket: let visual planner handle pocket switching safely.
            if s["pocket"]!=pocket:return None
            target=next((i for i,x in enumerate(s["rows"]) if x["id"]==intent["item"] and x["count"]>0),None)
            if target is None:return None
            direction="DOWN" if target>s["cursor"] else "UP"
        else:
            target=s["target"]
            # Gen III party menu layout is not a linear vertical list when
            # moving between lead and reserves. Use vision for that transition.
            if target!=s["cursor"] and (target==0 or s["cursor"]==0):return None
            direction="DOWN" if target>s["cursor"] else "UP"
        button="A" if s["cursor"]==target else direction
        signature=hashlib.sha256(repr((s["callback"],s["cursor"],target,intent["purpose"],button)).encode()).hexdigest()
        if any(h.get("menu_signature")==signature for h in meta.get("history",[])[-6:]):return None
        return {"scene":s["stage"],"objective":"Select intended "+intent["purpose"]+" target using native cursor","actions":[{"button":button,"frames":5}],"review":False},signature

    def finish(self,meta,before,after,decision):
        intent=meta.get("menu_intent")
        if not intent:return
        intent["remaining"]-=1
        button=decision["actions"][0]["button"]
        if button=="A":
            # A may open USE/SHIFT or a healing target submenu; do not repeat.
            intent["phase"]="confirm";intent.pop("callback",None)
        elif not after or after["callback"]!=before["callback"] or after["stage"]!=before["stage"] or after["cursor"]!=before["cursor"]+(1 if button=="DOWN" else -1):
            intent.pop("callback",None) # fresh visual witness required
