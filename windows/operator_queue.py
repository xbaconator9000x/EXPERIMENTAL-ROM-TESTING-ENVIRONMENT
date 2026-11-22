"""Private outbound-only GitHub command poller; native emulator stays in main thread."""
import json
import os
from pathlib import Path
import threading
import time
import uuid
import base64
import hashlib
from core.operator_control import validate_command,OperatorControl
from windows.queue_host import validate as validate_test, run as run_test, RUNNER as TEST_RUNNER, evidence_parts
from windows.host import ROOT,LIBRARY,RUNS,fingerprint

COMMAND_PREFIX="ROM-CONTROL v1\n"
ACK_PREFIX="ROM-CONTROL-ACK v1\n"

class ControlPoller:
    def __init__(self,remote,issue,sha,folder,identity,runner,rom):
        self.remote=remote;self.issue=issue;self.sha=sha;self.folder=Path(folder)
        self.identity=identity;self.runner=runner;self.rom=rom
        self.stop=threading.Event()
        self.thread=None
        self.control=OperatorControl(folder,identity,runner,rom,sha,ack=self.ack)
        self.cursor_file=self.folder/"operator-cursor.json"
        self.seen=0
        if self.cursor_file.exists():
            row=json.loads(self.cursor_file.read_text(encoding="utf-8"))
            if row.get("issue")!=issue or row.get("sha256")!=sha or type(row.get("last_seen")) is not int:
                raise ValueError("Operator cursor identity mismatch")
            self.seen=row["last_seen"]
        self.test_thread=None
        self.test_stop=threading.Event()
        self.last_feedback=time.monotonic()
        self.poll_failures=0
        self.announced=False

    def save_cursor(self):
        tmp=self.cursor_file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"issue":self.issue,"sha256":self.sha,"last_seen":self.seen}),encoding="ascii")
        os.replace(tmp,self.cursor_file)

    def ack(self,id,status,action,meta=None,rgb=None,reason=None):
        # Never include emulator states, local paths or secrets.
        body={"id":id,"status":status,"action":action}
        if meta is not None:body["decisions"]=meta.get("decisions")
        if rgb is not None:
            import hashlib
            body["screen"]=hashlib.sha256(rgb).hexdigest()
        if reason:body["reason"]=reason
        try:
            self.remote.verify()
            self.remote.request("/issues/"+str(self.issue)+"/comments",
                                {"body":ACK_PREFIX+json.dumps(body,separators=(",",":"))})
        except (OSError,ValueError,KeyError):
            # Local audit is authoritative for execution. Never replay native input
            # merely because a GitHub acknowledgement was lost.
            pass
        if status=="EXECUTED" and rgb is not None and action not in ("status","pause","resume"):
            try:
                from core.autoplay import png
                raw=png(rgb)
                encoded=base64.b64encode(raw).decode("ascii")
                total=(len(encoded)+43999)//44000
                if total<=24:
                    for part in range(total):
                        packet={"id":id,"sha256":hashlib.sha256(raw).hexdigest(),
                                "part":part+1,"parts":total,"base64":encoded[part*44000:(part+1)*44000]}
                        self.remote.request("/issues/"+str(self.issue)+"/comments",
                                            {"body":"ROM-CONTROL-FRAME v1\n"+json.dumps(packet,separators=(",",":"))})
            except (OSError,ValueError,KeyError):
                pass

    def _test_worker(self,id,issue,job):
        try:
            run_id="remote-"+uuid.uuid4().hex
            status=run_test(job,self.test_stop,runner=TEST_RUNNER,library=LIBRARY,
                            timeout=600,allow_v2=False,run_id=run_id)
            self.ack(id,"TEST_"+status,"test")
            if self.remote.share_evidence:
                for part in evidence_parts(RUNS/run_id):
                    if self.test_stop.is_set():break
                    self.remote.evidence(issue,part)
        except (OSError,ValueError,RuntimeError):
            self.ack(id,"FAILED","test",reason="HOST_ERROR")

    def dispatch_test(self,id,cmd):
        if self.test_thread is not None and self.test_thread.is_alive():
            self.ack(id,"FAILED","test",reason="TEST_ALREADY_RUNNING");return
        number=cmd["args"]["issue"]
        row=self.remote.request("/issues/"+str(number))
        if row.get("title")!="[ROM-TEST v1]" or row.get("state")!="open" or row.get("user",{}).get("login","").lower()!=self.remote.author:
            self.ack(id,"FAILED","test",reason="TEST_ISSUE_NOT_AUTHORIZED");return
        job=validate_test(row.get("body"))
        if job["version"]!=1 or job["sha256"]!=self.sha:
            self.ack(id,"FAILED","test",reason="TEST_ROM_MISMATCH");return
        self.test_stop.clear()
        self.test_thread=threading.Thread(target=self._test_worker,args=(id,number,job),daemon=True)
        self.test_thread.start()
        self.ack(id,"ACCEPTED","test")

    def announce(self):
        if self.announced:return
        body={"version":1,"rom_sha256":self.sha,
              "capabilities":["pause","resume","status","snapshot","restore",
                              "input","soft_reset","hard_reset","test"],
              "checkpoint_bytes":"local_only","engine":"advanced"}
        self.remote.request("/issues/"+str(self.issue)+"/comments",
                            {"body":"ROM-CONTROL-READY v1\n"+json.dumps(body,separators=(",",":"))})
        self.announced=True

    def poll_once(self):
        self.remote.verify() # includes mandatory private repository identity
        details=self.remote.request("/issues/"+str(self.issue))
        if details.get("state")!="open":return
        count=details.get("comments",0)
        if type(count) is not int or count<0:return
        # A playthrough can have thousands of screenshot comments.
        # Each page must stay under Remote.request's 2-MiB response cap,
        # even when all comments contain maximal 44-KiB base64 chunks.
        # Scan the latest three pages at 20 comments/page rather than
        # requesting a 100-comment page that can silently fail forever.
        page=max(1,(count+19)//20)
        rows=[]
        for p in range(max(1,page-2),page+1):
            rows.extend(self.remote.request("/issues/"+str(self.issue)+"/comments?per_page=20&page="+str(p)))
        rows.sort(key=lambda x:x.get("id",0))
        if not self.cursor_file.exists():
            self.seen=max((x["id"] for x in rows if type(x.get("id")) is int),default=0)
            self.save_cursor()
            self.announce()
            return
        self.announce()
        for comment in rows:
            id=comment.get("id")
            if type(id) is not int or id<=self.seen:continue
            # Cursor is durable BEFORE dispatch; a crash can lose a command,
            # but can never invisibly repeat a reset or state load.
            self.seen=id;self.save_cursor()
            raw=comment.get("body")
            if not isinstance(raw,str) or not raw.startswith(COMMAND_PREFIX):continue
            if comment.get("user",{}).get("login","").lower()!=self.remote.author or comment.get("author_association") not in ("OWNER","MEMBER","COLLABORATOR"):
                continue
            try:cmd=validate_command(raw[len(COMMAND_PREFIX):],self.sha)
            except (ValueError,TypeError,KeyError):
                self.ack(id,"REJECTED","invalid",reason="INVALID_SCHEMA");continue
            if cmd["action"]=="test":
                try:self.dispatch_test(id,cmd)
                except (ValueError,OSError,KeyError):self.ack(id,"FAILED","test",reason="FETCH_OR_VALIDATION")
            else:
                try:self.control.offer(id,cmd);self.ack(id,"ACCEPTED",cmd["action"])
                except Exception:self.ack(id,"FAILED",cmd["action"],reason="CONTROL_QUEUE_FULL")

    def run(self):
        while not self.stop.is_set():
            try:self.poll_once();self.poll_failures=0
            except (OSError,ValueError,KeyError,TypeError):
                self.poll_failures=min(self.poll_failures+1,6)
            self.stop.wait(min(60,5*(2**min(self.poll_failures,3))))

    def __enter__(self):
        self.thread=threading.Thread(target=self.run,daemon=True)
        self.thread.start()
        return self.control

    def __exit__(self,*args):
        self.stop.set()
        if self.thread is not None:self.thread.join(timeout=20)
        self.test_stop.set()
        if self.test_thread is not None:self.test_thread.join(timeout=2)
