"""Isolated, evidence-gated Jessie & James gameplay evaluation.

Inspired by goal-scoped NuzlockeSolver evaluation. Independent implementation.
Only the already-verified native acceptance ledger can satisfy milestone goals;
LLM narration, pixel changes and decision count can never substitute.
The live checkpoint is read only, and the resumed player runs solely inside a
newly-created scratch directory under a separate evaluation root.
"""
import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from core.autoplay import OllamaVision, load_progress, play, save_progress
from core.native_acceptance import engine_hash
from core.jj_runtime import NATIVE

SHA=re.compile(r"[0-9a-f]{64}\Z")
SCENARIOS={
    "leave_current_map": {"description":"Witness a genuine map crossing from the copied checkpoint",
                          "needs":{"map_crossing":1}},
    "navigation_progress":{"description":"Complete at least three independently witnessed native field steps",
                           "needs":{"native_step":3}},
    "win_battle":{"description":"Witness a real native battle victory","needs":{"battle_win":1}},
    "catch_pokemon":{"description":"Witness a real wild capture and party growth","needs":{"wild_capture":1}},
    "checkpoint_resume":{"description":"Reload the copied checkpoint and then make a native field step",
                          "needs":{"checkpoint_reload":1,"native_step":1}},
}
EVENTS=frozenset(("native_step","map_crossing","battle_win","wild_capture",
                  "healing","native_move","checkpoint_reload"))
SUCCESS_STATUSES=frozenset(("BUDGET_REACHED","STOPPED","RUNNING"))
NAV_BUTTONS=frozenset(("UP","DOWN","LEFT","RIGHT"))
MAX_AUDIT_BYTES=4*1024*1024


def _digest_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def _map(value):
    if not isinstance(value,(tuple,list)) or len(value)!=2:return None
    if not all(type(v) is int and 0<=v<=255 for v in value):return None
    return tuple(value)


def _field(value):
    if not isinstance(value,dict):return None
    m=_map(value.get("map"))
    p=value.get("pos")
    if m is None or not isinstance(p,(tuple,list)) or len(p)!=2:return None
    if not all(type(v) is int and 0<=v<256 for v in p):return None
    return m,tuple(p)


def _metric_delta(before,after,key):
    x=(before or {}).get(key,0) if isinstance(before,dict) else 0
    y=(after or {}).get(key,0) if isinstance(after,dict) else 0
    if (type(x) not in (int,float) or type(y) not in (int,float)
            or x<0 or y<x or y>1e10):return None
    return round(y-x,3) if isinstance(x,float) or isinstance(y,float) else y-x


def _events(meta,identity,start_decision):
    """Validate the identity and each new acceptance event; never trust counts."""
    ledger=meta.get("native_acceptance",{})
    if not isinstance(ledger,dict) or ledger.get("profile_admitted") is not True:
        return None,"native_profile_not_admitted"
    key=ledger.get("identity",{})
    if (not isinstance(key,dict) or key.get("rom")!=identity["rom"]
            or key.get("runner")!=identity["runner"]
            or key.get("engine")!=engine_hash()):
        return None,"native_acceptance_identity_mismatch"
    events=ledger.get("events")
    if not isinstance(events,list):return None,"native_events_missing"
    accepted=[];seen=set()
    for row in events:
        if not isinstance(row,dict) or row.get("kind") not in EVENTS:continue
        decision=row.get("decision")
        if type(decision) is not int or decision<=start_decision:continue
        before,after=row.get("before"),row.get("after")
        if (not isinstance(before,str) or not SHA.fullmatch(before)
                or not isinstance(after,str) or not SHA.fullmatch(after)
                or not isinstance(row.get("source"),str)):
            continue
        if row["kind"]=="map_crossing":
            detail=row.get("detail",{})
            if (not isinstance(detail,dict) or _map(detail.get("from")) is None
                    or _map(detail.get("to")) is None
                    or _map(detail["from"])==_map(detail["to"])):
                continue
        if row["kind"]=="wild_capture":
            detail=row.get("detail",{})
            if (not isinstance(detail,dict) or type(detail.get("species")) is not int
                    or not 1<=detail["species"]<=411):
                continue
        key=(row["kind"],decision,before,after)
        if key not in seen:
            seen.add(key);accepted.append(row)
    return accepted,None


def _audit_rows(meta,source=None):
    """Prefer full scratch audit; otherwise report explicitly limited history."""
    if source is None:
        return meta.get("history",[])[-80:],True
    path=Path(source)
    if not path.is_file():return meta.get("history",[])[-80:],True
    if path.is_symlink() or path.stat().st_size>MAX_AUDIT_BYTES:
        return meta.get("history",[])[-80:],True
    rows=[]
    try:
        with path.open("r",encoding="utf-8") as f:
            for line in f:
                if len(line)>4096:raise ValueError("Oversized audit row")
                item=json.loads(line)
                if isinstance(item,dict):rows.append(item)
                if len(rows)>15000:raise ValueError("Audit row cap")
    except (ValueError,OSError,UnicodeError):
        return meta.get("history",[])[-80:],True
    return rows,False


def _stuck(rows,baseline):
    """Only *native coordinate* observations can prove non-progress."""
    last=_field(baseline.get("last_native_field"))
    failed=0;measured=0;navigation=0
    last_decision=baseline.get("decisions",0)
    for row in rows:
        if not isinstance(row,dict):continue
        n=row.get("decision")
        if type(n) is not int or n<=last_decision:continue
        field=_field(row.get("field_after"))
        actions=row.get("actions",[])
        is_move=(isinstance(actions,list) and len(actions)==1
                 and isinstance(actions[0],dict)
                 and actions[0].get("button") in NAV_BUTTONS)
        source=row.get("source")
        if is_move and isinstance(source,str) and (source in NATIVE or source.startswith("vision")):
            navigation+=1
            if field is not None and last is not None:
                measured+=1
                if field==last:failed+=1
        if field is not None:last=field
    return {"verified_comparisons":measured,"verified_no_progress":failed,
            "navigation_attempts":navigation,
            "stuck_ratio":round(failed/measured,4) if measured else None}


def evaluate(scenario,baseline,final,identity,*,status="BUDGET_REACHED",audit=None):
    """Pure analysis of the isolated episode, never advances a ROM."""
    if scenario not in SCENARIOS:raise ValueError("Unknown evaluation scenario")
    if not isinstance(baseline,dict) or not isinstance(final,dict):raise ValueError("Bad episode metadata")
    start,end=baseline.get("decisions"),final.get("decisions")
    if type(start) is not int or type(end) is not int or not 0<=start<=end<=10000000:
        raise ValueError("Invalid decision interval")
    events,error=_events(final,identity,start)
    counts={k:0 for k in EVENTS}
    if events is not None:
        for event in events:counts[event["kind"]]+=1
    before_maps={m for value in baseline.get("visited_native_maps",[])
                 if (m:=_map(value)) is not None}
    newly_visited=set()
    if events is not None:
        for item in events:
            if item["kind"]=="map_crossing":
                destination=_map(item["detail"]["to"])
                if destination not in before_maps:newly_visited.add(destination)
    before_metric=baseline.get("engine_metrics",{})
    after_metric=final.get("engine_metrics",{})
    metrics={
        "decisions":end-start,
        "frames":final.get("frames",0)-baseline.get("frames",0),
        "model_calls":_metric_delta(before_metric,after_metric,"model_calls"),
        "model_seconds":_metric_delta(before_metric,after_metric,"model_seconds"),
        "native_decisions":_metric_delta(before_metric,after_metric,"native"),
        "map_crossings":counts["map_crossing"],
        "new_maps":len(newly_visited),
        "native_steps":counts["native_step"],
        "battle_wins":counts["battle_win"],
        "wild_captures":counts["wild_capture"],
        "heals":counts["healing"],
        "checkpoint_reloads":counts["checkpoint_reload"],
    }
    if type(metrics["frames"]) is not int or metrics["frames"]<0:
        raise ValueError("Invalid episode frame interval")
    rows,limited=_audit_rows(final,audit)
    nav=_stuck(rows,baseline)
    metrics.update(nav)
    metrics["audit_limited"]=limited
    # Successful milestones and novel maps dominate the score; traversing
    # the same old corridor repeatedly cannot farm unlimited points.
    metrics["score"]=(len(newly_visited)*100+min(counts["map_crossing"],3)*10
                      +min(counts["native_step"],15)*2
                      +min(counts["battle_win"],3)*20
                      +min(counts["wild_capture"],3)*35
                      +min(counts["healing"],1)*8
                      -nav["verified_no_progress"]*4)
    need=SCENARIOS[scenario]["needs"]
    goal_met=events is not None and all(counts[k]>=n for k,n in need.items())
    valid_end=status in SUCCESS_STATUSES
    result="PASS" if goal_met and valid_end else "FAIL"
    if error:reason=error
    elif not goal_met:reason="required_native_milestone_not_witnessed"
    elif not valid_end:reason="terminal_failure_"+str(status)
    else:reason="verified_goal_met"
    return {"format":"ROM-EVAL v1","scenario":scenario,"description":SCENARIOS[scenario]["description"],
            "result":result,"reason":reason,"status":status,
            "start_decision":start,"end_decision":end,"metrics":metrics,
            "evidence":{"native_accepted":events is not None,
                        "new_native_events":len(events) if events is not None else 0,
                        "event_counts":counts,
                        "rom_sha256":identity.get("rom"),
                        "runner_sha256":identity.get("runner")},
            "limits":["Model narration is not a gameplay witness",
                      "Source checkpoint is read-only; all actions occur in scratch",
                      "A PASS is one scenario, never complete story acceptance"]}


def _overlaps(a,b):
    try:a.relative_to(b);return True
    except ValueError:pass
    try:b.relative_to(a);return True
    except ValueError:return False


def run_isolated(scenario,checkpoint,output_root,runner,rom,rom_sha,goal,model,
                 *,budget=30,player=play):
    """Play ONLY from a verified copy in a fresh private scratch directory.

    Each invocation leaves a verifiable original, never reuses a previous
    evaluation checkpoint and never opens the user's working save for writing.
    A ROM sha mismatch, identity mismatch or overlapping output root fails
    before any emulator starts.
    """
    if scenario not in SCENARIOS or type(budget) is not int or not 1<=budget<=300:
        raise ValueError("Unsupported scenario or decision budget")
    if not isinstance(rom_sha,str) or not SHA.fullmatch(rom_sha):
        raise ValueError("Invalid local ROM SHA-256")
    cp=Path(checkpoint).resolve(strict=True)
    out=Path(output_root).resolve()
    if not cp.is_file() or cp.is_symlink() or _overlaps(cp.parent,out):
        raise ValueError("Evaluation directory must be separate from the real checkpoint")
    if not Path(runner).is_file() or not Path(rom).is_file():
        raise ValueError("Runner and ROM must exist locally")
    if _digest_file(rom)!=rom_sha:raise ValueError("Local ROM checksum mismatch")
    model_id=getattr(model,"model",None)
    if not isinstance(model_id,str) or not model_id:
        raise ValueError("Model identity required")
    identity={"rom":rom_sha,"runner":_digest_file(runner),"goal":goal,"model":model_id}
    prior=load_progress(cp,identity)
    if prior is None:raise ValueError("Checkpoint missing")
    baseline,state,rgb=prior
    if type(baseline.get("decisions")) is not int:
        raise ValueError("Checkpoint missing decision index")
    out.mkdir(parents=True,exist_ok=True)
    scratch=Path(tempfile.mkdtemp(prefix="jj-eval-"+scenario+"-",dir=out))
    # Save once into scratch under the regular play() identity, then use
    # the same actual code path as the production player.
    save_progress(scratch/"progress.bin",identity,baseline,state,rgb)
    goal_reached=False
    def report(status,meta,current_rgb):
        nonlocal goal_reached
        if status=="RUNNING":
            interim=evaluate(scenario,baseline,meta,identity,status=status)
            if interim["result"]=="PASS":goal_reached=True
    status,final,last_rgb=player(runner,rom,rom_sha,goal,scratch,model,
                          max_decisions=baseline["decisions"]+budget,
                          should_stop=lambda:goal_reached,report=report)
    result=evaluate(scenario,baseline,final,identity,status=status,
                    audit=scratch/"actions.jsonl")
    result["scratch_directory"]=str(scratch)
    result["original_unchanged"]=_digest_file(cp)==_digest_file(checkpoint)
    if not result["original_unchanged"]:
        result["result"]="FAIL";result["reason"]="original_checkpoint_modified"
    path=scratch/"evaluation.json"
    tmp=path.with_suffix(".tmp")
    with tmp.open("w",encoding="utf-8") as handle:
        json.dump(result,handle,indent=2,sort_keys=True)
        handle.flush();os.fsync(handle.fileno())
    os.replace(tmp,path)
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("list",help="List evidence-gated real gameplay scenarios")
    run=sub.add_parser("run",help="Run in a fresh isolated folder; requires explicit local ROM")
    for key in ("scenario","checkpoint","output_root","runner","rom","rom_sha","goal","model"):
        run.add_argument("--"+key.replace("_","-"),required=True)
    run.add_argument("--budget",type=int,default=30)
    score=sub.add_parser("score",help="Score two validated checkpoint snapshots without emulation")
    for key in ("scenario","before","after","runner","rom_sha","goal","model"):
        score.add_argument("--"+key.replace("_","-"),required=True)
    score.add_argument("--status",default="BUDGET_REACHED")
    args=p.parse_args(argv)
    if args.command=="list":
        for k,v in SCENARIOS.items():print(k+"\t"+v["description"])
        return 0
    if args.command=="run":
        result=run_isolated(args.scenario,args.checkpoint,args.output_root,
                args.runner,args.rom,args.rom_sha,args.goal,
                OllamaVision(model=args.model),budget=args.budget)
    else:
        identity={"rom":args.rom_sha,"runner":_digest_file(args.runner),
                  "goal":args.goal,"model":args.model}
        initial=load_progress(Path(args.before),identity)
        final=load_progress(Path(args.after),identity)
        if initial is None or final is None:raise ValueError("Missing checkpoint")
        result=evaluate(args.scenario,initial[0],final[0],identity,status=args.status)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result["result"]=="PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
