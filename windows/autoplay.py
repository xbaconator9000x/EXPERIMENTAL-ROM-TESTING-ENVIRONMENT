"""Dedicated continuous localhost-model player for the private GitHub queue."""
import argparse
import base64
import getpass
import hashlib
import json
import os
import re
import time
from pathlib import Path
from core.autoplay import OllamaVision, play, png, load_progress
from core.jj_native_only import NativeOnly
from core.guidance import newest_guide, claim_guide
from windows.host import ROOT, LIBRARY, REPO, fingerprint
from windows.queue_host import Remote
from windows.operator_queue import ControlPoller
from core.upstream_port import UPSTREAM_COMMIT

TITLE="[ROM-PLAY v1]"
UPSTREAM_TITLE="[ROM-PLAY upstream v2]"
RUNNER=REPO/"build"/"live_runner.exe"

def goal(body, title=TITLE):
    if not isinstance(body,str) or len(body)>4096:raise ValueError("Invalid playthrough goal")
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d:raise ValueError("Duplicate goal field")
            d[k]=v
        return d
    v=json.loads(body,object_pairs_hook=unique)
    version=2 if title==UPSTREAM_TITLE else 1
    if type(v) is not dict or set(v)!={"version","sha256","goal"} or type(v["version"]) is not int or v["version"]!=version:
        raise ValueError("Invalid goal schema")
    if type(v["sha256"]) is not str or not re.fullmatch(r"[a-f0-9]{64}",v["sha256"]):raise ValueError("Invalid ROM hash")
    if type(v["goal"]) is not str or not 1<=len(v["goal"].strip())<=1000 or any(ord(c)<32 for c in v["goal"]):raise ValueError("Invalid goal text")
    return v

def poll_goals(remote):
    remote.verify()
    for page in range(1,11):
        rows=remote.request("/issues?state=open&sort=created&direction=asc&per_page=100&page="+str(page))
        for i in rows:
            if ("pull_request" not in i and i.get("title") in (TITLE,UPSTREAM_TITLE) and i.get("user",{}).get("login","").lower()==remote.author and
                    type(i.get("id")) is int and i["id"]>0 and type(i.get("number")) is int and i["number"]>0):
                yield i
        if len(rows)<100:return

def post(remote,number,status,meta,rgb):
    # Only a fixed, bounded screenshot and recent decisions. No states, ROM or files.
    remote.verify()
    payload={"status":status,"decisions":meta["decisions"],"frames":meta["frames"],"rom_profile":meta.get("rom_profile"),"native_acceptance":meta.get("native_acceptance"),
             "screen":hashlib.sha256(rgb).hexdigest(),"history":meta.get("history",[])[-4:],"review":meta.get("review"),"failed_action":meta.get("failed_action"),"model_error":meta.get("model_error"),"engine_metrics":meta.get("engine_metrics"),"model_trace":meta.get("last_model_trace"),"native_field":meta.get("last_native_field"),"native_transitions":len(meta.get("observed_field_transitions",[])),"native_diagnostics":meta.get("native_diagnostics"),"objective_state":meta.get("objective_state"),"last_incident":meta.get("last_incident"),"recovery_attempts":len(meta.get("recovery",{}).get("attempts",[]))}
    remote.request("/issues/"+str(number)+"/comments",{"body":"ROM-AUTOPLAY v1\n"+json.dumps(payload,ensure_ascii=True,separators=(",",":"))})
    data=png(rgb);encoded=base64.b64encode(data).decode("ascii");parts=(len(encoded)+43999)//44000
    for i in range(parts):
        remote.verify()
        envelope={"name":"playthrough-"+str(meta["decisions"])+".png","sha256":hashlib.sha256(data).hexdigest(),"part":i+1,"parts":parts,"base64":encoded[i*44000:(i+1)*44000]}
        remote.request("/issues/"+str(number)+"/comments",{"body":"ROM-AUTOPLAY-FRAME v1\n"+json.dumps(envelope,separators=(",",":"))})

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--queue",required=True);p.add_argument("--author",required=True);p.add_argument("--model",default="qwen3-vl:4b-instruct");p.add_argument("--fallback",default="qwen3-vl:2b-instruct")
    p.add_argument("--upstream-checkout",type=Path,help="Enable exact vanilla LeafGreen upstream v2 jobs")
    p.add_argument("--native-only",action="store_true",help="Deterministic gameplay; disable Ollama/GPU inference")
    a=p.parse_args()
    if not RUNNER.is_file():raise SystemExit("Rebuild native runners first.")
    remote=Remote(a.queue,a.author,getpass.getpass("Private issue token: "),share_evidence=True)
    remote.verify()
    model=NativeOnly(a.model) if a.native_only else OllamaVision(a.model,fallback=a.fallback)
    root=ROOT/"autoplay"/hashlib.sha256(a.queue.lower().encode()).hexdigest();root.mkdir(parents=True,exist_ok=True)
    # Windows exclusive lock prevents parallel controllers for this queue.
    import msvcrt
    with (root/"controller.lock").open("a+b") as lock:
        if lock.tell()==0:lock.write(b"0");lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        print("Continuous player polling private queue. Ctrl+C to stop.",flush=True)
        if a.native_only:print("Native-only mode: Qwen disabled; unsupported states hold for review.",flush=True)
        retry_delay=15
        while True:
            try:
                for issue in poll_goals(remote):
                    number=issue["number"];folder=root/str(issue["id"]);folder.mkdir(exist_ok=True)
                    upstream=issue["title"]==UPSTREAM_TITLE
                    if upstream and not a.upstream_checkout:continue
                    done=folder/"terminal.json"
                    if done.is_file():
                        try:finished=json.loads(done.read_text(encoding="utf-8"))
                        except (ValueError,OSError):continue
                        if finished.get("status") not in ("NEEDS_REVIEW","EMULATOR_ERROR","MODEL_UNAVAILABLE_OR_INVALID","UPSTREAM_SKILL_ERROR"):continue
                    try:job=goal(issue.get("body"),issue["title"])
                    except ValueError:continue
                    rom=LIBRARY/(job["sha256"]+".gba")
                    if not rom.is_file() or rom.is_symlink() or fingerprint(rom)!=job["sha256"]:
                        print("ROM not registered for issue #"+str(number),flush=True);continue
                    if upstream and (folder/"progress.bin").exists():continue
                    if not upstream and (folder/"upstream-progress.bin").exists():continue
                    last=[0.0];original=issue["body"];original_title=issue["title"]
                    def stop():
                        if time.monotonic()-last[0]<30:return False
                        last[0]=time.monotonic();remote.verify()
                        current=remote.request("/issues/"+str(number))
                        return current.get("state")!="open" or current.get("body")!=original or current.get("title")!=original_title
                    guide_rows={"time":0.0,"rows":[]}
                    def guidance(meta,screen,consume=False):
                        if time.monotonic()-guide_rows["time"]>30:
                            remote.verify()
                            current=remote.request("/issues/"+str(number))
                            if current.get("state")!="open" or current.get("body")!=original:return None
                            count=current.get("comments",0)
                            if type(count) is not int or count<1:return None
                            page=max(1,(count+19)//20)
                            rows=[]
                            for i in range(max(1,page-1),page+1):
                                rows+=remote.request("/issues/"+str(number)+"/comments?per_page=20&page="+str(i))
                            guide_rows.update(time=time.monotonic(),rows=rows)
                        proposal=newest_guide(guide_rows["rows"],remote.author,meta["decisions"],screen)
                        if proposal and claim_guide(folder/"guides.json",meta["decisions"],screen,proposal,consume):
                            return proposal
                        return None
                    # A terminal review must never gate the operator channel.
                    # Preserve the hash-verified checkpoint; do not require an
                    # old single-use upgrade marker or previously posted guide.
                    parked=False
                    if done.is_file():
                        identity={"rom":job["sha256"],"runner":fingerprint(RUNNER),
                                  "goal":job["goal"],"model":a.model}
                        if upstream:identity["upstream"]=UPSTREAM_COMMIT
                        checkpoint=folder/("upstream-progress.bin" if upstream else "progress.bin")
                        try:prior=load_progress(checkpoint,identity)
                        except (OSError,ValueError,KeyError) as exc:
                            print(f"#{number}: checkpoint not admitted ({type(exc).__name__}); preserving terminal state",flush=True)
                            continue
                        if not prior:
                            print(f"#{number}: checkpoint missing; preserving terminal state",flush=True)
                            continue
                        parked=True
                        print(f"#{number}: attaching operator to parked {finished['status']} at decision {prior[0]['decisions']}",flush=True)
                    def checked_guide(meta,screen):
                        try:return guidance(meta,screen,consume=True)
                        except (OSError,ValueError,KeyError):return None
                    def report(status,meta,rgb):
                        print(f"#{number}: {status}, decisions={meta['decisions']}, frames={meta['frames']}",flush=True)
                        try:post(remote,number,status,meta,rgb)
                        except (OSError,ValueError,KeyError):
                            print("Private progress report failed; local checkpoint retained.",flush=True)
                    identity={"rom":job["sha256"],"runner":fingerprint(RUNNER),"goal":job["goal"],"model":a.model}
                    if upstream:identity["upstream"]=UPSTREAM_COMMIT
                    with ControlPoller(remote,number,job["sha256"],folder,identity,RUNNER,rom) as control:
                        if parked:
                            # Native script/dialogue review can now run the
                            # bounded automated recovery ladder. Old terminal
                            # reviews of other kinds still require supervision,
                            # and an exhausted ladder never restarts on install.
                            prior_meta=prior[0]
                            prior_review=prior_meta.get("review",{})
                            prior_recovery=prior_meta.get("review_recovery",{})
                            auto_recover=(not upstream and
                                isinstance(prior_review,dict) and
                                prior_review.get("scene")=="native_script_locked" and
                                not (isinstance(prior_recovery,dict) and
                                     prior_recovery.get("status") in
                                     ("EXHAUSTED","FAILED")))
                            control.review=not auto_recover
                            if auto_recover:
                                print(f"#{number}: bounded native review recovery enabled",flush=True)
                            # Only after the control path is constructed do we
                            # mark the old terminal review as supervised.
                            done.unlink()
                        if upstream:
                            from core.upstream_campaign import campaign
                            from core.upstream_port import PortError
                            try:
                                status,meta,rgb=campaign(RUNNER,rom,job["sha256"],a.upstream_checkout,folder,a.model,job["goal"],100000,should_stop=stop,report=report,control=control)
                            except PortError as exc:
                                print("Upstream profile rejected: "+str(exc),flush=True);continue
                        else:
                            status,meta,rgb=play(RUNNER,rom,job["sha256"],job["goal"],folder,model,should_stop=stop,report=report,guidance=checked_guide,control=control)
                    if status!="STOPPED":
                        if status not in ("NEEDS_REVIEW","EMULATOR_ERROR","MODEL_UNAVAILABLE_OR_INVALID"):report(status,meta,rgb)
                        if status!="MODEL_UNAVAILABLE_OR_INVALID":
                            tmp=done.with_suffix(".tmp");tmp.write_text(json.dumps({"status":status,"decisions":meta["decisions"]}),encoding="utf-8");os.replace(tmp,done)
                    break
                retry_delay=15
            except (OSError,ValueError,KeyError,RuntimeError) as e:
                # No tokens, paths, ROM/save contents, or untrusted GitHub
                # body text in logs; report classification for diagnosis.
                print("Controller retry: "+type(e).__name__,flush=True)
                retry_delay=min(120,retry_delay*2)
            time.sleep(retry_delay)

if __name__=="__main__":main()