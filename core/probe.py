"""Record private, read-only state witnesses at explicit input checkpoints.

A candidate is not a verified navigation profile. No profile is promoted by
plausibility alone. Keep the plan, trace and screenshots local.
"""
import argparse
import json
from pathlib import Path

from core.live import Live, LiveError
from core.firered import Profile, Reader

KEYS={"A":1,"B":2,"SELECT":4,"START":8,"RIGHT":16,"LEFT":32,
      "UP":64,"DOWN":128,"R":256,"L":512}

def inspect(live, candidate):
    p=Profile(**candidate)
    result={"callback":hex(live.integer(p.context_addr,4)),
            "saveblock":hex(live.integer(p.saveblock_ptr,4)),
            "layout":hex(live.integer(p.map_header,4)),
            "vmap":[live.integer(p.vmap+i,4) for i in (0,4,8)]}
    try:
        f=Reader(live,p).snapshot()
    except LiveError as e:
        result["field_error"]=str(e)
    else:
        result["field"]={"map_id":f.map_id,"position":f.pos,
                         "width":f.width,"height":f.height}
    return result

def run(live, candidate, plan, out):
    out=Path(out)
    out.mkdir(parents=True,exist_ok=False)
    with (out/"trace.jsonl").open("x") as log:
        for i,action in enumerate(plan):
            kind=action["op"]
            if kind=="press":
                live.step(KEYS[action["key"]],action["frames"])
                live.step(0,action.get("release",1))
            elif kind=="idle":
                live.step(0,action["frames"])
            elif kind!="observe":
                raise ValueError("unknown probe action")
            row={"index":i,"action":action,"observed":inspect(live,candidate)}
            if action.get("capture",False):
                live.screenshot(out/f"frame-{i:04}.ppm")
            log.write(json.dumps(row)+"\n")
            log.flush()
    print("PROBE COMPLETE: observations only; not gameplay acceptance")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("runner","rom","profile","plan","out"):
        p.add_argument("--"+name,required=True)
    a=p.parse_args()
    candidate=json.loads(Path(a.profile).read_text())
    plan=json.loads(Path(a.plan).read_text())
    if not isinstance(plan,list) or not 0<len(plan)<=500:
        p.error("plan must contain 1–500 explicit actions")
    with Live(a.runner,a.rom,candidate["sha256"]) as live:
        run(live,candidate,plan,a.out)
if __name__=="__main__":
    main()
