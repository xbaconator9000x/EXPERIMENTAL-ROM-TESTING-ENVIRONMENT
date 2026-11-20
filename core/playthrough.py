"""Evidence-driven playthrough controller primitives.

The external planner interprets screenshots and supplies an action/scene label.
This module verifies the transport and constructs bounded, reproducible jobs;
it does not pretend to recognize arbitrary game scenes or run a local LLM.
"""
import base64
import hashlib
import json
import re
from dataclasses import dataclass
from windows.queue_host import validate

HASH=re.compile(r"[a-f0-9]{64}")
FRAME=re.compile(r"frame_(\d{6})_line_(\d+)\.png")
RESULT=re.compile(r"^RESULT (PASS|FAIL) frame=(\d+) checks=(\d+) line=(\d+) core_crash=([01])$",re.M)
LIMIT=10

@dataclass(frozen=True)
class Evidence:
    status:str
    frames:tuple
    log:str
    terminal:tuple|None

    @property
    def screen_hash(self):
        return hashlib.sha256(self.frames[-1][1]).hexdigest() if self.frames else None

def decode_evidence(comments):
    """Accept only a complete manifest with exact, hash-verified parts."""
    manifest=None;groups={}
    for body in comments:
        if not isinstance(body,str):continue
        if body.startswith("ROM-EVIDENCE-COMPLETE v1\n"):
            m=json.loads(body.split("\n",1)[1])
            if manifest is not None and m!=manifest:raise ValueError("Conflicting manifests")
            manifest=m
        elif body.startswith("ROM-EVIDENCE v1\n"):
            p=json.loads(body.split("\n",1)[1])
            name=p["name"];digest=p["sha256"];part=p["part"];count=p["parts"];data=p["base64"]
            if not (name=="native.log" or FRAME.fullmatch(name)) or not HASH.fullmatch(digest):
                raise ValueError("Invalid evidence identity")
            if p["mime"]!=("text/plain" if name=="native.log" else "image/png"):raise ValueError("Invalid MIME")
            if type(part) is not int or type(count) is not int or not 1<=part<=count<=8 or type(data) is not str or len(data)>44000:
                raise ValueError("Invalid evidence chunk")
            meta,chunks=groups.setdefault(name,((digest,count),{}))
            if meta!=(digest,count) or (part in chunks and chunks[part]!=data):raise ValueError("Conflicting evidence")
            chunks[part]=data
    if manifest is None:raise ValueError("Incomplete transfer")
    if type(manifest.get("files")) is not list or sorted(manifest["files"])!=sorted(groups) or manifest["parts"]!=sum(len(c) for _,c in groups.values()):
        raise ValueError("Manifest mismatch")
    if len(groups)>22:raise ValueError("Evidence limit")
    files={}
    for name,((digest,count),chunks) in groups.items():
        if set(chunks)!=set(range(1,count+1)):raise ValueError("Missing evidence chunk")
        data=base64.b64decode("".join(chunks[i] for i in range(1,count+1)),validate=True)
        if hashlib.sha256(data).hexdigest()!=digest:raise ValueError("Evidence hash mismatch")
        files[name]=data
    frames=tuple(sorted(((name,data) for name,data in files.items() if FRAME.fullmatch(name)),
                        key=lambda x:tuple(map(int,FRAME.fullmatch(x[0]).groups()))))
    for name,data in frames:
        if len(data)<33 or data[:8]!=b"\x89PNG\r\n\x1a\n" or data[12:16]!=b"IHDR" or data[16:24]!=b"\x00\x00\x00\xf0\x00\x00\x00\xa0":
            raise ValueError("Invalid frame format")
    log=files.get("native.log",b"").decode("ascii")
    match=RESULT.search(log)
    terminal=match.groups() if match else None
    if manifest["status"]=="PASS" and (not terminal or terminal[0]!="PASS" or int(terminal[2])<1 or terminal[4]!="0"):
        raise ValueError("PASS without native witness")
    return Evidence(manifest["status"],frames,log,terminal)

def action_key(actions):
    return hashlib.sha256(json.dumps(list(actions),separators=(",",":")).encode()).hexdigest()

def recoverable_actions(previous,screen_hash,alternatives):
    """Avoid reissuing the same failed action from the same observed screen.
    Identical pixels alone are not proof of a hang (menus/dialogue can wait).
    """
    tried={row["action_hash"] for row in previous if row["screen_hash"]==screen_hash and row["outcome"] in ("unchanged","failed")}
    return [list(a) for a in alternatives if action_key(a) not in tried][:LIMIT]

def next_job(parent,actions,*,resume=None,checkpoint=None,assertions=()):
    """Continue from a verified exact replay or an immutable native checkpoint.
    Constrain each action batch; force final capture; never remote shell/code.
    """
    if not 1<=len(actions)<=40 or any(a.split()[0] not in ("press","idle","capture") for a in actions):
        raise ValueError("Invalid action batch")
    if resume is None:
        # Captures do not advance emulation; remove old ones to preserve quota.
        lines=[s for s in parent["scenario"] if s!="capture"]
        job={"version":parent["version"],"sha256":parent["sha256"],"scenario":lines}
        if "resume" in parent:job["resume"]=parent["resume"]
    else:
        if not assertions:raise ValueError("Resume requires independent state assertion")
        job={"version":2,"sha256":parent["sha256"],"resume":resume,"scenario":[]}
    if checkpoint is not None:
        job["version"]=2;job["checkpoint"]=checkpoint
    job["scenario"]+=list(assertions)+list(actions)
    if job["scenario"][-1]!="capture":job["scenario"].append("capture")
    return validate(json.dumps(job))

def progress_record(*,job,scene,previous_screen,action,evidence,verified_transition=False,ending_verified=False):
    """Only a planner's independent scene witness can establish progress/end."""
    if not scene or not evidence.frames:raise ValueError("Scene evidence required")
    if ending_verified and (not verified_transition or evidence.status!="PASS"):
        raise ValueError("Ending requires successful independent witness")
    if evidence.status!="PASS":outcome="failed"
    elif verified_transition:outcome="progress"
    elif evidence.screen_hash==previous_screen:outcome="unchanged"
    else:outcome="changed_unverified"
    return {"job":job,"scene":scene,"screen_hash":previous_screen,"result_screen_hash":evidence.screen_hash,
            "action_hash":action_key(action),"outcome":outcome,"ending_verified":bool(ending_verified)}
