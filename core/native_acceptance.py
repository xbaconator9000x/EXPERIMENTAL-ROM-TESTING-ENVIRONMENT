"""Fail-closed gameplay evidence from real native read-only checkpoints.

No fixture or CI result is interpreted as a completed campaign. This is a
milestone ledger, not an automatic release approval.
"""
import hashlib
from pathlib import Path
from core.live import LiveError
from core.jj_fast import ADMITTED_SHA256S,MAIN,PARTY,decode_party
from core.jj_battle import BATTLE_CB
from core.gen3_profiles import party_snapshot

KEYS=("native_step","map_crossing","battle_win","wild_capture","healing",
      "native_move","checkpoint_reload")
SOURCE_FILES=("autoplay.py","action_batch.py","gen3_profiles.py","jj_fast.py","jj_battle.py",
              "jj_menus.py","jj_explore.py","jj_connections.py","upstream_battle.py",
              "native_acceptance.py","firered.py","rom_catalog.py","live.py",
              "upstream_leafgreen/type_chart.py","upstream_leafgreen/move_kinds.py",
              "upstream_leafgreen/move_effects.py")

def engine_hash():
    root=Path(__file__).resolve().parent
    h=hashlib.sha256()
    for name in SOURCE_FILES:
        h.update(name.encode()+b"\0"+hashlib.sha256((root/name).read_bytes()).digest())
    return h.hexdigest()

class Acceptance:
    def __init__(self,meta,sha,runner_hash,profile,adapter,battles):
        self.meta=meta
        self.profile=profile
        self.adapter=adapter
        self.battles=battles
        self.enabled=bool(profile or (sha in ADMITTED_SHA256S and adapter.admitted and BATTLE_CB in battles.callbacks))
        identity={"rom":sha,"runner":runner_hash,"engine":engine_hash()}
        prev=meta.get("native_acceptance",{})
        if prev.get("identity")!=identity:
            if prev.get("identity"):
                archive=meta.setdefault("previous_acceptance",[])
                archive.append({"identity":prev["identity"],"counts":prev.get("counts",{})})
                meta["previous_acceptance"]=archive[-5:]
            meta["native_acceptance"]={"identity":identity,"counts":{k:0 for k in KEYS},
                "events":[],"status":"INCOMPLETE"}
        self.ledger=meta["native_acceptance"]
        self.ledger["profile_admitted"]=self.enabled

    def read_party(self,live):
        if self.profile:return party_snapshot(live,self.profile)
        # Exact hack has unique separately admitted layout, with checksum
        # checking, not vanilla geography. Party count must agree.
        party=decode_party(live.read(PARTY,600))
        if live.integer(0x02024029,1)!=len(party):raise ValueError("party count witness")
        return party

    def witness(self,live,field,battle):
        if not self.enabled:return None
        try:
            p=self.profile
            cb=live.integer(p.main+4 if p else MAIN+4,4)
            battle_cb=p.battle_cb if p else BATTLE_CB
            state={"in_battle":cb==battle_cb,"outcome":live.integer(p.outcome if p else 0x02023e8a,1)}
            if field and self.adapter.verified_field(field,self.meta):
                f=field[0]
                state["field"]={"map":list(f.map_id),"pos":list(f.pos)}
            if battle and battle["callback"] in self.meta.get("battle_proof",[]):
                state["battle"]={"wild":battle["wild"],"enemy":battle["enemy"]["species"],
                    "own":battle["own"]["species"],"pp":list(battle["own"]["pp"]),
                    "moves":list(battle["own"]["moves"])}
            if state.get("field") or state.get("battle") or state["in_battle"] or self.ledger.get("pending_battle"):
                try:state["party"]=self.read_party(live)
                except (ValueError,LiveError):
                    state["party"]=None
                    if state.get("field") or state.get("battle"):
                        self.ledger["party_validation_faults"]=self.ledger.get("party_validation_faults",0)+1
            return state
        except (ValueError,LiveError,KeyError):return None

    def record(self,key,decision,before,after,source,detail=None):
        if not self.enabled or key not in KEYS:return
        row={"kind":key,"decision":decision,"before":before,"after":after,"source":source}
        if detail:row["detail"]=detail
        if row in self.ledger["events"]:return
        self.ledger["counts"][key]+=1
        self.ledger["events"]=(self.ledger["events"]+[row])[-32:]

    def observe(self,before,after,source,decision,screen_before,screen_after,actions):
        if not self.enabled or before is None or after is None:return
        def event(key,detail=None):
            self.record(key,decision,screen_before,screen_after,source,detail)
        f,g=before.get("field"),after.get("field")
        if f and g and f["map"]==g["map"] and source in ("native_route","native_explore"):
            a,b=f["pos"],g["pos"]
            if sum(abs(x-y) for x,y in zip(a,b))==1:
                event("native_step",{"map":g["map"],"from":a,"to":b})
        if f:
            self.ledger["last_field"]=f
        previous=self.ledger.get("last_field")
        if g and previous and previous["map"]!=g["map"]:
            event("map_crossing",{"from":previous["map"],"to":g["map"]})
        if g:self.ledger["last_field"]=g
        b=before.get("battle")
        if b and before["outcome"]==0 and before.get("party") is not None:
            self.ledger.setdefault("pending_battle",{"enemy":b["enemy"],"wild":b["wild"],"party":before["party"],"start":decision})
        a=after.get("battle")
        if a and b and a["own"]==b["own"] and a["moves"]==b["moves"] and source=="native_battle" and any(x<y for x,y in zip(a["pp"],b["pp"])):
            event("native_move")
        pending=self.ledger.get("pending_battle")
        if pending and decision-pending["start"]>2000:
            self.ledger.pop("pending_battle",None);pending=None
        if pending and after["outcome"] in (1,7):
            if after["outcome"]==1:
                event("battle_win")
                self.ledger.pop("pending_battle",None)
            elif pending["wild"] and after.get("party") is not None:
                old=pending["party"];new=after["party"]
                if len(new)==len(old)+1 and sum(m["species_id"]==pending["enemy"] for m in new)>sum(m["species_id"]==pending["enemy"] for m in old):
                    event("wild_capture",{"species":pending["enemy"]})
                    self.ledger.pop("pending_battle",None)
                elif g:self.ledger.pop("pending_battle",None)
        elif pending and after["outcome"] not in (0,1,7):
            self.ledger.pop("pending_battle",None)
        if before.get("party") and after.get("party") and (f or b) and (g or a):
            old={m["slot"]:m for m in before["party"]}
            for m in after["party"]:
                n=old.get(m["slot"])
                if n and m["species_id"]==n["species_id"] and m["level"]==n["level"] and m["max_hp"]==n["max_hp"] and m["hp"]>n["hp"] and m["hp"]==m["max_hp"]:
                    event("healing",{"slot":m["slot"],"hp_before":n["hp"],"hp_after":m["hp"]})
                    break
        # A stalled run, completed unit tests or even these milestones do not
        # constitute a story/credits pass. Keep a distinct manual review gate.
        self.ledger["status"]="MILESTONES_WITNESSED" if all(self.ledger["counts"][k] for k in KEYS) and not self.ledger.get("party_validation_faults") else "INCOMPLETE"

    def reload(self,decision,expected_rgb,actual_rgb):
        if self.enabled and expected_rgb==actual_rgb:
            h=hashlib.sha256(actual_rgb).hexdigest()
            self.record("checkpoint_reload",decision,h,h,"native_restart")
