"""Audited controller-only interventions on a local native mGBA session.

The caller owns the emulator; the GitHub poller is never allowed to touch it.
The only state mutations are native save-state LOAD, native controller STEP and
a new native emulator instance. All checkpoints stay local and hash-bound.
"""
import copy
import json
import os
from pathlib import Path
import queue
import re
import time
from core.live import Live
from core.autoplay import BUTTONS, digest, load_progress, save_progress

NAME=re.compile(r"[a-z0-9][a-z0-9_-]{0,47}\Z")
OPS=frozenset(("pause","resume","status","snapshot","restore","input","soft_reset","hard_reset","test"))
RUNNER_OPS=OPS-{"test"}

def validate_command(body,sha):
    if not isinstance(body,str) or len(body)>4096:raise ValueError("Invalid command length")
    def unique(pairs):
        o={}
        for k,v in pairs:
            if k in o:raise ValueError("Duplicate command key")
            o[k]=v
        return o
    v=json.loads(body,object_pairs_hook=unique)
    if type(v) is not dict or set(v) not in (
       {"version","rom_sha256","action","args"},
       {"version","rom_sha256","action","args","expected_screen"}):
        raise ValueError("Invalid command fields")
    if type(v["version"]) is not int or v["version"]!=1 or v["rom_sha256"]!=sha:
        raise ValueError("ROM identity mismatch")
    if type(v["action"]) is not str or v["action"] not in OPS or type(v["args"]) is not dict:
        raise ValueError("Unsupported action")
    a=v["args"];op=v["action"]
    expected={"snapshot":{"name"},"restore":{"name"},"input":{"actions"},"test":{"issue"}}.get(op,set())
    if set(a)!=expected:raise ValueError("Invalid action arguments")
    if op in ("snapshot","restore") and (type(a["name"]) is not str or not NAME.fullmatch(a["name"])):
        raise ValueError("Invalid checkpoint name")
    if op=="test" and (type(a["issue"]) is not int or not 1<=a["issue"]<=100000000):
        raise ValueError("Invalid test issue")
    if op=="input":
        actions=a["actions"]
        if type(actions) is not list or not 1<=len(actions)<=16:raise ValueError("Invalid input count")
        frames=0
        for item in actions:
            if type(item) is not dict or set(item)!={"button","frames"} or item["button"] not in BUTTONS or type(item["frames"]) is not int or not 1<=item["frames"]<=120:
                raise ValueError("Invalid native input")
            frames+=item["frames"]
        if frames>960:raise ValueError("Input frame budget exceeded")
    if "expected_screen" in v:
        if type(v["expected_screen"]) is not str or not re.fullmatch(r"[a-f0-9]{64}",v["expected_screen"]):
            raise ValueError("Invalid screen witness")
    return v

class OperatorControl:
    def __init__(self,folder,identity,runner,rom,sha,*,ack=lambda *args:None):
        self.folder=Path(folder).resolve()
        self.folder.mkdir(parents=True,exist_ok=True)
        self.identity=identity
        self.runner,self.rom,self.sha=runner,rom,sha
        self.ack=ack
        self.pending=queue.Queue(maxsize=32)
        self.paused=False
        self.review=False
        self.reported_pause=False
        self.status_path=self.folder/"operator-status.json"
        self.command_log=self.folder/"operator-audit.jsonl"
        self.states=self.folder/"operator-states"
        self.states.mkdir(exist_ok=True)
        self.last_active=time.monotonic()

    def offer(self,comment_id,command):
        if type(comment_id) is not int or comment_id<=0 or command["action"]=="test":
            raise ValueError("Not a native command")
        self.pending.put_nowait((comment_id,command))

    def persist(self,event,meta,rgb):
        # No save data, passwords, absolute paths or arbitrary model responses.
        row={"utc":int(time.time()),"event":event,"screen":digest(rgb),"decisions":meta["decisions"],"paused":self.paused}
        tmp=self.status_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(row,separators=(",",":")),encoding="utf-8")
        os.replace(tmp,self.status_path)
        with self.command_log.open("a",encoding="ascii") as f:
            f.write(json.dumps(row,separators=(",",":"))+"\n")

    def apply(self,comment_id,cmd,live,meta,rgb):
        op=cmd["action"]
        if cmd.get("expected_screen") and digest(rgb)!=cmd["expected_screen"]:
            raise ValueError("Stale screen witness")
        state=None
        if op in ("restore","input","soft_reset","hard_reset"):
            # Every forced mutation has an immutable pre-operation generation.
            # It is not the ordinary progress file and cannot replace it.
            before=self.states/("before-"+str(comment_id)+".bin")
            if before.exists() or before.is_symlink():raise ValueError("Duplicate operator command")
            save_progress(before,self.identity,copy.deepcopy(meta),live.save_state(),rgb)
        if op=="snapshot":
            name=cmd["args"]["name"]
            dest=self.states/(name+".bin")
            if dest.exists() or dest.is_symlink():raise ValueError("Immutable checkpoint already exists")
            save_progress(dest,self.identity,copy.deepcopy(meta),live.save_state(),rgb)
        elif op=="restore":
            name=cmd["args"]["name"]
            source=self.states/(name+".bin")
            saved=load_progress(source,self.identity)
            if saved is None:raise ValueError("Named checkpoint absent")
            old_meta,state,old_rgb=saved
            live.load_state(state)
            verified=live.rgb()
            if verified!=old_rgb:
                # Do not silently accept a different screen as the restored state.
                safe=load_progress(before,self.identity)
                if safe is not None:live.load_state(safe[1])
                raise ValueError("Loaded LCD witness differs")
            meta=old_meta;rgb=verified
            self.review=False
        elif op=="input":
            for item in cmd["args"]["actions"]:
                live.step(BUTTONS[item["button"]],item["frames"])
                # Release ordinary keys between separate button commands.
                if item["button"]!="WAIT":live.step(0,3)
            rgb=live.rgb()
            meta["frames"]+=sum(item["frames"]+(3 if item["button"]!="WAIT" else 0) for item in cmd["args"]["actions"])
            self.review=False
        elif op=="soft_reset":
            live.step(1|2|4|8,8)
            live.step(0,120)
            rgb=live.rgb();meta["frames"]+=128;self.review=False
        elif op=="hard_reset":
            # A fresh emulator boot intentionally does not load the old state;
            # the checkpoint remains available for explicit restore.
            new=Live(self.runner,self.rom,self.sha)
            try:
                new.step(0,120);newrgb=new.rgb()
                newstate=new.save_state()
            except BaseException:
                new.close();raise
            newmeta={"decisions":0,"frames":120,"history":[],"operator_new_boot":True}
            # Never close the known working native process until the fresh
            # boot and its durable progress file have both succeeded.
            save_progress(self.folder/("upstream-progress.bin" if "upstream" in self.identity else "progress.bin"),
                          self.identity,newmeta,newstate,newrgb)
            live.close();live=new;rgb=newrgb;meta=newmeta
            self.review=False
        elif op=="pause":
            self.paused=True
        elif op=="resume":
            self.paused=False
            self.review=False
        elif op=="status":
            pass
        else:raise ValueError("Unsupported runtime action")
        if op in ("input","restore","soft_reset","hard_reset"):
            meta.pop("native_route",None);meta.pop("menu_intent",None)
            meta.pop("field_proof",None);meta.pop("battle_proof",None)
            meta.pop("event_goal",None);meta.pop("review",None)
            meta.pop("failed_action",None)
            meta["operator_last_action"]=op
            meta["history"]=meta.get("history",[])[-80:]
            save_progress(self.folder/("upstream-progress.bin" if "upstream" in self.identity else "progress.bin"),
                          self.identity,meta,live.save_state(),rgb)
        self.persist({"comment_id":comment_id,"action":op,"result":"EXECUTED"},meta,rgb)
        self.ack(comment_id,"EXECUTED",op,meta,rgb)
        return live,meta,rgb,op

    def drain(self,live,meta,rgb):
        changed=False
        while True:
            try:comment_id,cmd=self.pending.get_nowait()
            except queue.Empty:break
            try:
                live,meta,rgb,op=self.apply(comment_id,cmd,live,meta,rgb)
                changed|=op in ("input","restore","soft_reset","hard_reset","pause","resume")
            except (ValueError,OSError,RuntimeError) as exc:
                # An error during native control must not let the autonomous
                # planner immediately make a second unverified input.
                self.paused=True
                self.review=True
                try:self.persist({"comment_id":comment_id,"action":cmd["action"],"result":"FAILED"},meta,rgb)
                except (OSError,ValueError):pass
                self.ack(comment_id,"FAILED",cmd["action"],meta,rgb,reason=type(exc).__name__)
        return live,meta,rgb,changed

    def serve(self,live,meta,rgb,should_stop=lambda:False):
        live,meta,rgb,changed=self.drain(live,meta,rgb)
        if self.paused or self.review:
            if not self.reported_pause:
                self.persist({"action":"operator_hold" if self.paused else "needs_review","result":"WAITING"},meta,rgb)
                self.reported_pause=True
            while (self.paused or self.review) and not should_stop():
                time.sleep(.25)
                live,meta,rgb,new=self.drain(live,meta,rgb)
                changed|=new
        else:self.reported_pause=False
        return live,meta,rgb,changed

    def hold_for_review(self,live,meta,rgb,should_stop=lambda:False):
        self.review=True
        return self.serve(live,meta,rgb,should_stop)
