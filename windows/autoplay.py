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
from core.guidance import newest_guide, claim_guide
from windows.host import ROOT, LIBRARY, REPO, fingerprint
from windows.queue_host import Remote

TITLE="[ROM-PLAY v1]"
RUNNER=REPO/"build"/"live_runner.exe"

def goal(body):
    if not isinstance(body,str) or len(body)>4096:raise ValueError("Invalid playthrough goal")
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d:raise ValueError("Duplicate goal field")
            d[k]=v
        return d
    v=json.loads(body,object_pairs_hook=unique)
    if type(v) is not dict or set(v)!={"version","sha256","goal"} or type(v["version"]) is not int or v["version"]!=1:
        raise ValueError("Invalid goal schema")
    if type(v["sha256"]) is not str or not re.fullmatch(r"[a-f0-9]{64}",v["sha256"]):raise ValueError("Invalid ROM hash")
    if type(v["goal"]) is not str or not 1<=len(v["goal"].strip())<=1000 or any(ord(c)<32 for c in v["goal"]):raise ValueError("Invalid goal text")
    return v

def poll_goals(remote):
    remote.verify()
    for page in range(1,11):
        rows=remote.request("/issues?state=open&sort=created&direction=asc&per_page=100&page="+str(page))
        for i in rows:
            if ("pull_request" not in i and i.get("title")==TITLE and i.get("user",{}).get("login","").lower()==remote.author and
                    type(i.get("id")) is int and i["id"]>0 and type(i.get("number")) is int and i["number"]>0):
                yield i
        if len(rows)<100:return

def post(remote,number,status,meta,rgb):
    # Only a fixed, bounded screenshot and recent decisions. No states, ROM or files.
    remote.verify()
    payload={"status":status,"decisions":meta["decisions"],"frames":meta["frames"],
             "screen":hashlib.sha256(rgb).hexdigest(),"history":meta.get("history",[])[-4:],"review":meta.get("review"),"failed_action":meta.get("failed_action"),"model_error":meta.get("model_error")}
    remote.request("/issues/"+str(number)+"/comments",{"body":"ROM-AUTOPLAY v1\n"+json.dumps(payload,ensure_ascii=True,separators=(",",":"))})
    data=png(rgb);encoded=base64.b64encode(data).decode("ascii");parts=(len(encoded)+43999)//44000
    for i in range(parts):
        remote.verify()
        envelope={"name":"playthrough-"+str(meta["decisions"])+".png","sha256":hashlib.sha256(data).hexdigest(),"part":i+1,"parts":parts,"base64":encoded[i*44000:(i+1)*44000]}
        remote.request("/issues/"+str(number)+"/comments",{"body":"ROM-AUTOPLAY-FRAME v1\n"+json.dumps(envelope,separators=(",",":"))})

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--queue",required=True);p.add_argument("--author",required=True);p.add_argument("--model",default="qwen3-vl:4b-instruct");p.add_argument("--fallback",default="qwen3-vl:2b-instruct")
    a=p.parse_args()
    if not RUNNER.is_file():raise SystemExit("Rebuild native runners first.")
    remote=Remote(a.queue,a.author,getpass.getpass("Private issue token: "),share_evidence=True)
    remote.verify()
    model=OllamaVision(a.model,fallback=a.fallback)
    root=ROOT/"autoplay"/hashlib.sha256(a.queue.lower().encode()).hexdigest();root.mkdir(parents=True,exist_ok=True)
    # Windows exclusive lock prevents parallel controllers for this queue.
    import msvcrt
    with (root/"controller.lock").open("a+b") as lock:
        if lock.tell()==0:lock.write(b"0");lock.flush()
        lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        print("Continuous player polling private queue. Ctrl+C to stop.",flush=True)
        while True:
            try:
                for issue in poll_goals(remote):
                    number=issue["number"];folder=root/str(issue["id"]);folder.mkdir(exist_ok=True)
                    done=folder/"terminal.json"
                    if done.is_file():
                        try:finished=json.loads(done.read_text(encoding="utf-8"))
                        except (ValueError,OSError):continue
                        if finished.get("status") not in ("NEEDS_REVIEW","EMULATOR_ERROR"):continue
                    try:job=goal(issue.get("body"))
                    except ValueError:continue
                    rom=LIBRARY/(job["sha256"]+".gba")
                    if not rom.is_file() or rom.is_symlink() or fingerprint(rom)!=job["sha256"]:
                        print("ROM not registered for issue #"+str(number),flush=True);continue
                    last=[0.0];original=issue["body"]
                    def stop():
                        if time.monotonic()-last[0]<30:return False
                        last[0]=time.monotonic();remote.verify()
                        current=remote.request("/issues/"+str(number))
                        return current.get("state")!="open" or current.get("body")!=original or current.get("title")!=TITLE
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
                    # A failed guide is consumed before execution. An identical
                    # command cannot endlessly restart a crashing checkpoint.
                    if done.is_file():
                        identity={"rom":job["sha256"],"runner":fingerprint(RUNNER),"goal":job["goal"],"model":a.model}
                        try:prior=load_progress(folder/"progress.bin",identity)
                        except (ValueError,OSError,KeyError):continue
                        if not prior or not guidance(prior[0],hashlib.sha256(prior[2]).hexdigest()):continue
                        done.unlink()
                    def checked_guide(meta,screen):
                        try:return guidance(meta,screen,consume=True)
                        except (OSError,ValueError,KeyError):return None
                    def report(status,meta,rgb):
                        print(f"#{number}: {status}, decisions={meta['decisions']}, frames={meta['frames']}",flush=True)
                        try:post(remote,number,status,meta,rgb)
                        except (OSError,ValueError,KeyError):
                            print("Private progress report failed; local checkpoint retained.",flush=True)
                    status,meta,rgb=play(RUNNER,rom,job["sha256"],job["goal"],folder,model,should_stop=stop,report=report,guidance=checked_guide)
                    if status!="STOPPED":
                        if status not in ("NEEDS_REVIEW","EMULATOR_ERROR","MODEL_UNAVAILABLE_OR_INVALID"):report(status,meta,rgb)
                        if status!="MODEL_UNAVAILABLE_OR_INVALID":
                            tmp=done.with_suffix(".tmp");tmp.write_text(json.dumps({"status":status,"decisions":meta["decisions"]}),encoding="utf-8");os.replace(tmp,done)
                    break
            except (OSError,ValueError,KeyError,RuntimeError) as e:
                print("Controller retry: "+type(e).__name__,flush=True)
            time.sleep(15)

if __name__=="__main__":main()
