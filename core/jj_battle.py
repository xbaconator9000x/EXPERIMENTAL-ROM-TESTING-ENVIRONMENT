"""Read-only battle and inventory controller for the exact Jessie & James release.

The source ROM contains these candidate FRLG globals and function entrypoints.
Hash the local executable spans before enabling each menu. Runtime checks and
visible menu corroboration are mandatory. No direct input cursor mutation.
"""
import hashlib
from pathlib import Path
from core.jj_fast import SHA, MAIN, PARTY, BATTLE, CTRL, SAVE_PTR, decode_party, u
from core.firered import span
from core.rom_catalog import TYPES
from core.live import LiveError
from core.gameplay import cursor_action
from core.upstream_battle import classic_multiplier, safe_damage_kind, catch_setup_slot

BATTLE_CB=0x08011101
ACTION_CURSOR=0x02023FF8
MOVE_CURSOR=0x02023FFC
FLAGS=0x02022B4C
DISABLE=0x02023E0C
SAVE2=0x0300500C
MENUS={0x08030611:"battle_command",0x0802E439:"battle_command",0x0802EA11:"battle_moves"}
FINGERPRINTS={
    BATTLE_CB:"443ba1d86888aa8c127daf9aabf4ff20ec4eda16c071517a25c1e14b12835469",
    0x08030611:"a87222f33e4f42eea1c7a6de1be30012c97fb2e58bec520b93080becafc58b77",
    0x0802E439:"1116443a18d9ddafd403e4f6ba064850bb0f3a42fc7188dc7e6c038abf8f4255",
    0x0802EA11:"2c835b19645b5808f66eb1b2c50d4d5538b6543ddd9c1d0f5d781869f94253f1",
}

def anchors(data,addresses):
    # Scan aligned literal references without a Python loop over every word.
    end=min(len(data),0x160000)
    for a in addresses:
        needle=a.to_bytes(4,"little");i=data.find(needle,0,end)
        while i>=0 and i%4:i=data.find(needle,i+1,end)
        if i<0:return False
    return True

def decode_battler(b):
    if len(b)!=88:raise ValueError("battler length")
    species=u(b,0);hp=u(b,40);mx=u(b,44);level=b[42];types=b[33:35]
    stats=[u(b,i) for i in (2,4,6,8,10)]
    moves=[u(b,i) for i in range(12,20,2)];pp=list(b[36:40])
    stages=list(b[24:32])
    if not 1<=species<=411 or not 1<=level<=100 or not 0<=hp<=mx<=999 or not mx or any(not 1<=s<=999 for s in stats) or any(s>12 for s in stages):
        raise ValueError("battler stats")
    if any(t>=len(TYPES) or TYPES[t] is None for t in types) or any(m>559 for m in moves) or any(p>64 for p in pp):
        raise ValueError("battler types/moves")
    return {"species":species,"hp":hp,"max_hp":mx,"level":level,"types":list(dict.fromkeys(TYPES[t] for t in types)),
        "stats":stats,"stages":stages,"moves":moves,"pp":pp,"status":u(b,76,4),"ability":b[32],"disabled":False}

def pocket(raw,key):
    if len(raw)%4:raise ValueError("pocket size")
    rows=[];seen=set()
    for i in range(0,len(raw),4):
        item=u(raw,i);quantity=u(raw,i+2)^key
        if not item:continue
        if not 1<=item<=376 or not 1<=quantity<=999 or item in seen:raise ValueError("pocket data")
        seen.add(item);rows.append({"id":item,"count":quantity})
    return rows

def inventory(live):
    one=live.integer(SAVE_PTR,4);two=live.integer(SAVE2,4)
    if one%4 or two%4 or not span(one,0x464,0x02000000,0x02040000) or not span(two,0xf24,0x02000000,0x02040000) or one==two:
        raise ValueError("save blocks")
    key=live.integer(two+0xf20,4)
    body=live.read(one+0x290,0x464-0x290)
    money=u(body,0,4)^key
    if money>999999:raise ValueError("money")
    items=pocket(body[0x80:0x80+42*4],key&65535)
    balls=pocket(body[0x1a0:0x1a0+13*4],key&65535)
    if any(x["id"] not in range(1,13) for x in balls):raise ValueError("ball pocket")
    return {"money":money,"items":items,"balls":balls}

def health_percent(mon):
    return 100*mon["hp"]//mon["max_hp"]

def move_rank(own,enemy,rows,disabled=0,capture=False):
    """Classic type-based category, real battle stats and stage-adjusted damage.
    This is a damage heuristic, not an exact prediction (abilities/weather,
    special damage effects, held items and multi-hit can alter the outcome).
    """
    candidates=[]
    for slot,mid in enumerate(own["moves"]):
        if not mid or not own["pp"][slot] or mid==disabled:continue
        row=rows.get(mid)
        if not row or not row["power"] or row["power"]==1:continue
        kind=safe_damage_kind(row,enemy["status"],capture)
        if kind is None:continue
        mult=classic_multiplier(row["type"],enemy["types"])
        if not mult:continue
        physical=row["type"] in ("normal","fighting","flying","poison","ground","rock","bug","ghost","steel")
        ai,di=(0,1) if physical else (3,4)
        # stage indexes atk=1, def=2, special attack=4, special defense=5
        ast,dst=(1,2) if physical else (4,5)
        def stage(n):return (2+max(0,n-6))/(2+max(0,6-n))
        a=own["stats"][ai]*stage(own["stages"][ast])
        d=enemy["stats"][di]*stage(enemy["stages"][dst])
        est=((2*own["level"]/5+2)*row["power"]*a/max(1,d)/50+2)*mult*(1.5 if row["type"] in own["types"] else 1)
        if physical and own["status"]&16:est*=.5
        if capture:
            # Leave margin for damage variation and critical hits. If no safe
            # damaging attack exists, caller should use the bag or vision.
            if kind!="false_swipe" and est*2.1>=enemy["hp"]:continue
            quality=est*row["accuracy"]/100
        else:quality=est*row["accuracy"]/100*(.5 if kind in ("charge","semi_inv","recharge") else 1)
        candidates.append((quality,-slot,slot))
    return max(candidates)[2] if candidates else None

class BattleAdapter:
    def __init__(self,rom,sha,goal,catalog):
        self.callbacks=set();self.field_inventory=False;self.catalog=catalog
        if sha!=SHA or "classic" not in goal.lower() or "modern" in goal.lower():return
        try:
            data=Path(rom).read_bytes()
            if hashlib.sha256(data).hexdigest()!=sha:return
            self.field_inventory=anchors(data,(SAVE_PTR,SAVE2))
            if not catalog or not anchors(data,(MAIN,PARTY,BATTLE,CTRL,FLAGS,DISABLE,ACTION_CURSOR,MOVE_CURSOR)):return
            self.callbacks={a for a,fp in FINGERPRINTS.items() if hashlib.sha256(data[(a&~1)-0x08000000:(a&~1)-0x08000000+32]).hexdigest()==fp}
            if BATTLE_CB not in self.callbacks:self.callbacks.clear()
        except (OSError,ValueError):return

    def bag(self,live):
        if not self.field_inventory:return None
        try:return inventory(live)
        except (ValueError,LiveError):return None

    def snapshot(self,live):
        if not self.callbacks:return None
        try:
            if live.integer(MAIN+4,4)!=BATTLE_CB:return None
            cb=live.integer(CTRL,4)
            if cb not in self.callbacks or cb not in MENUS:return None
            flags=live.integer(FLAGS,4)
            if flags not in (4,12):return None # standard single, not Safari/doubles/tutorials
            stage=MENUS[cb]
            cursor=live.integer(ACTION_CURSOR if stage=="battle_command" else MOVE_CURSOR,1)
            if cursor>3:return None
            raw=live.read(BATTLE,176)
            own=decode_battler(raw[:88]);enemy=decode_battler(raw[88:])
            party=decode_party(live.read(PARTY,600))
            if not party or not own["hp"] or not enemy["hp"]:return None
            if not any(p["species_id"]==own["species"] and p["level"]==own["level"] and p["max_hp"]==own["max_hp"] for p in party):return None
            disable=live.read(DISABLE,12)
            disabled=u(disable,4) if disable[11]&15 else 0
            bag=self.bag(live)
            return {"stage":stage,"cursor":cursor,"callback":cb,"wild":not bool(flags&8),"own":own,"enemy":enemy,"party":party,"bag":bag,"disabled":disabled}
        except (ValueError,LiveError):return None

    def corroborate(self,state,obs,meta):
        if not state or obs.get("stage")!=state["stage"] or obs.get("cursor")!=state["cursor"]:return
        # Require one actual visually identified cursor/stage per callback; the
        # model must not simply copy the candidate state (not in its prompt).
        proof=meta.setdefault("battle_proof",[])
        if state["callback"] not in proof:proof.append(state["callback"])

    def action(self,state,meta):
        if not state or state["callback"] not in meta.get("battle_proof",[]):return None
        own,enemy,bag=state["own"],state["enemy"],state["bag"]
        cursor=state["cursor"]
        rows=self.catalog.move_ids
        healing=sum(x["count"] for x in bag["items"] if x["id"] in (13,19,20,21,22)) if bag else 0
        balls=sum(x["count"] for x in bag["balls"] if x["id"] in (2,3,4)) if bag else 0
        # Capture useful new species while building a starting team. Never
        # throw at trainers, use a Master Ball, or deliberately farm captures.
        capture=state["wild"] and balls>0 and len(state["party"])<3 and not any(p["species_id"]==enemy["species"] for p in state["party"])
        safe=move_rank(own,enemy,rows,state["disabled"],capture)
        if capture and health_percent(enemy)>35 and not enemy["status"]:
            setup=catch_setup_slot(own,enemy,rows,state["disabled"])
            if setup is not None:safe=setup
        heal=health_percent(own)<=25 and healing>0
        throw=capture and (health_percent(enemy)<=35 or enemy["status"]!=0 or safe is None)
        if state["stage"]=="battle_command":
            if heal or throw:target=1;reason="Open bag to heal" if heal else "Open bag to catch a new wild Pokémon"
            elif health_percent(own)<=15:
                if any(p["species_id"]!=own["species"] and health_percent(p)>40 for p in state["party"]):target=2;reason="Open party to switch safely"
                else:return None
            elif safe is None:return None
            else:target=0;reason="Open fight menu"
            actions=cursor_action(cursor,target)
        else:
            if heal or throw:actions=[{"button":"B","frames":5}];reason="Return to battle command menu"
            elif safe is None:return None
            else:actions=cursor_action(cursor,safe);reason="Choose legal damage-ranked move "+str(own["moves"][safe])
        if not actions:return None
        signature=hashlib.sha256(repr((state["callback"],cursor,own["species"],own["hp"],own["pp"],enemy["species"],enemy["hp"],state["disabled"],actions)).encode()).hexdigest()
        if sum(h.get("battle_signature")==signature for h in meta.get("history",[])[-8:])>=2:return None
        return {"scene":state["stage"],"objective":reason,"actions":actions,"review":False},signature

    def summary(self,state,meta):
        if not state or state["callback"] not in meta.get("battle_proof",[]):return None
        return {k:v for k,v in state.items() if k!="callback"}
