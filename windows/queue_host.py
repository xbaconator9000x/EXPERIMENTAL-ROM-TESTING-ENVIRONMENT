"""Outbound-only private GitHub queue. Remote data is never executed as code."""
from __future__ import annotations
import base64
import hashlib
import struct
import zlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import uuid
try:
    from .host import ROOT, LIBRARY, RUNS, RUNNER, fingerprint, tk, ttk, messagebox
except ImportError:
    from host import ROOT, LIBRARY, RUNS, RUNNER, fingerprint, tk, ttk, messagebox

TITLE = "[ROM-TEST v1]"
KEYS = set("A B SELECT START RIGHT LEFT UP DOWN R L".split())
STATUSES = {"PASS","FAIL","TIMEOUT","CANCELLED","INVALID_JOB","ROM_NOT_REGISTERED",
            "ROM_HASH_MISMATCH","RUNNER_NOT_INSTALLED","HOST_ERROR"}

def number(s):
    if not re.fullmatch(r"(?:0[xX][0-9a-fA-F]{1,8}|0|[1-9][0-9]{0,9})",s):
        raise ValueError("Invalid number")
    n=int(s,16 if s.lower().startswith("0x") else 10)
    if n>0xffffffff: raise ValueError("Number too large")
    return n

def validate(body):
    if not isinstance(body,str) or len(body)>65536: raise ValueError("Invalid job size")
    def unique(pairs):
        d={}
        for k,v in pairs:
            if k in d: raise ValueError("Duplicate key")
            d[k]=v
        return d
    job=json.loads(body,object_pairs_hook=unique)
    if type(job) is not dict or set(job)!={"version","sha256","scenario"} or type(job["version"]) is not int or job["version"]!=1:
        raise ValueError("Unsupported job schema")
    if not isinstance(job["sha256"],str) or not re.fullmatch(r"[a-f0-9]{64}",job["sha256"]):
        raise ValueError("Invalid ROM SHA256")
    lines=job["scenario"]
    if type(lines) is not list or not 1<=len(lines)<=500: raise ValueError("Invalid scenario size")
    frames=checks=captures=0
    normalized=[]
    for line in lines:
        if type(line) is not str or not line.isascii() or len(line)>120 or "\n" in line or "\r" in line:
            raise ValueError("Invalid line")
        t=line.split()
        if not t: raise ValueError("Empty line")
        op=t[0]
        if (op=="idle" and len(t)==2) or (op=="press" and len(t)==3 and t[1] in KEYS):
            n=number(t[-1])
            if not n:raise ValueError("Zero frames")
            frames+=n
        elif op in ("assert","wait") and len(t)==(6 if op=="wait" else 5):
            w,a,m,e=map(number,t[1:5])
            if w not in (8,16,32):raise ValueError("Invalid width")
            n=w//8
            if a%n or not any(lo<=a<=hi-n for lo,hi in ((0x02000000,0x02040000),(0x03000000,0x03008000),(0x06000000,0x06018000))):
                raise ValueError("Address outside permitted emulator memory")
            if not m or m>=1<<w or e&~m:raise ValueError("Invalid mask")
            if op=="wait":
                n=number(t[5])
                if not n:raise ValueError("Zero wait")
                frames+=n
            checks+=1
        elif op=="capture" and len(t)==1:captures+=1
        else:raise ValueError("Unsupported instruction")
        normalized.append(" ".join(t))
    if not checks or frames>200000 or captures>20:raise ValueError("Scenario exceeds limits or lacks assertion")
    return {"version":1,"sha256":job["sha256"],"scenario":normalized}

def run(job,stop,runner=RUNNER,library=LIBRARY,runs=RUNS,timeout=600,run_id=None):
    job=validate(json.dumps(job))
    if not runner.is_file():return "RUNNER_NOT_INSTALLED"
    sha=job["sha256"]
    source=library/(sha+".gba")
    if not source.is_file():return "ROM_NOT_REGISTERED"
    if not 0<source.stat().st_size<=32*1024*1024 or fingerprint(source)!=sha:return "ROM_HASH_MISMATCH"
    folder=runs/("remote-"+uuid.uuid4().hex if run_id is None else run_id)
    if not re.fullmatch(r"remote-[a-f0-9]{32}",folder.name):raise ValueError("Invalid run id")
    folder.mkdir(parents=True)
    with tempfile.TemporaryDirectory(dir=folder,prefix="private-") as work:
        work=Path(work)
        rom=work/"game.gba"
        shutil.copyfile(source,rom)
        if fingerprint(rom)!=sha:return "ROM_HASH_MISMATCH"
        scenario=work/"scenario.txt"
        scenario.write_text("\n".join(job["scenario"])+"\n",encoding="ascii")
        env=os.environ.copy()
        binpath=env.get("MSYS2_UCRT64_BIN",r"C:\msys64\ucrt64\bin")
        env["PATH"]=binpath+os.pathsep+env.get("PATH","")
        with (folder/"native.log").open("wb") as log:
            p=subprocess.Popen([str(runner.resolve()),str(rom),str(scenario),str(folder/"captures")],
                    cwd=work,env=env,stdout=log,stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            try:
                deadline=time.monotonic()+timeout
                while p.poll() is None:
                    if stop.is_set() or time.monotonic()>=deadline:
                        p.kill();p.wait()
                        return "CANCELLED" if stop.is_set() else "TIMEOUT"
                    stop.wait(.1)
            finally:
                if p.poll() is None:p.kill();p.wait()
        log=(folder/"native.log").read_text(encoding="utf-8",errors="replace")
        if p.returncode==0 and re.search(r"^RESULT PASS frame=\d+ checks=[1-9]\d* line=\d+ core_crash=0\s*$",log,re.M):
            return "PASS"
        return "FAIL"


# Evidence is opt-in locally, never requested by an issue. Fixed output paths only.
# PNGs are reconstructed from the runner's exact P6 framebuffer format.
FRAME = re.compile(r"frame_\d{6}_line_\d+\.ppm")
CHUNK = 44000
MAX_FRAMES = 21  # 20 requested captures plus the runner's terminal failure capture
MAX_LOG = 24000

def png_frame(path):
    if path.is_symlink() or not path.is_file():raise ValueError("Not a regular capture")
    header=b"P6\n240 160\n255\n"
    expected=len(header)+240*160*3
    if path.stat().st_size!=expected:raise ValueError("Invalid framebuffer length")
    with path.open("rb") as f:raw=f.read(expected+1)
    if len(raw)!=expected or not raw.startswith(header):raise ValueError("Invalid framebuffer")
    rgb=raw[len(header):]
    def chunk(kind,data):
        return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data)&0xffffffff)
    # PNG Sub filter preserves every pixel and compresses repetitive GBA tiles.
    rows=[]
    for y in range(160):
        row=rgb[y*720:(y+1)*720]
        rows.append(b"\x01"+row[:3]+bytes((row[i]-row[i-3])&255 for i in range(3,720)))
    return b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">IIBBBBB",240,160,8,2,0,0,0))+chunk(b"IDAT",zlib.compress(b"".join(rows),9))+chunk(b"IEND",b"")

def safe_log(path):
    # Only recognized emulator diagnostic lines; no arbitrary host paths,
    # stderr tracebacks, raw memory dumps, environment variables or save data.
    if path.is_symlink() or not path.is_file():return ""
    allowed=(
        re.compile(r"INPUT line=\d+ frame=\d+ keys=-?\d+ duration=\d+"),
        re.compile(r"(?:PASS|FAIL) line=\d+ frame=\d+ addr=[0-9a-fA-F]{8} actual=[0-9a-fA-F]{8} mask=[0-9a-fA-F]{8} expected=[0-9a-fA-F]{8}"),
        re.compile(r"RESULT (?:PASS|FAIL) frame=\d+ checks=\d+ line=\d+ core_crash=[01]"),
        re.compile(r"(?:GBA(?: [A-Za-z]+)*|ARM|GB): [A-Za-z0-9 ,:()_.+!?\-]{1,180}"),
    )
    with path.open("rb") as f:
        head=f.read(32000)
        f.seek(max(0,path.stat().st_size-32000))
        tail=f.read(32000)
    def select(raw):
        return [line for line in raw.decode("ascii",errors="replace").splitlines()
                if any(p.fullmatch(line) for p in allowed)]
    first=select(head);last=select(tail)
    if path.stat().st_size<=32000:return "\n".join(first)[:MAX_LOG]
    return ("\n".join(first)[:MAX_LOG//2]+"\n[log excerpt; middle omitted]\n"+"\n".join(last)[-MAX_LOG//2:])

def evidence_parts(folder):
    if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r"remote-[a-f0-9]{32}",folder.name):
        return []
    result=[]
    log=safe_log(folder/"native.log")
    if log:
        result.append(("native.log","text/plain",log.encode("ascii")))
    captures=folder/"captures"
    if captures.is_dir() and not captures.is_symlink():
        frames=sorted((p for p in captures.iterdir() if FRAME.fullmatch(p.name)),
                      key=lambda p:tuple(map(int,re.findall(r"\d+",p.name))))
        for p in frames[:MAX_FRAMES]:
            try:result.append((p.stem+".png","image/png",png_frame(p)))
            except (ValueError,OSError):continue
    parts=[]
    for name,mime,data in result:
        b64=base64.b64encode(data).decode("ascii")
        digest=hashlib.sha256(data).hexdigest()
        total=(len(b64)+CHUNK-1)//CHUNK
        for i in range(total):
            # A bounded text envelope, machine-readable via the existing Issues permission.
            payload={"name":name,"mime":mime,"sha256":digest,"part":i+1,"parts":total,
                     "base64":b64[i*CHUNK:(i+1)*CHUNK]}
            parts.append("ROM-EVIDENCE v1\n"+json.dumps(payload,separators=(",",":")))
    return parts


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError("Unexpected redirect")

class Remote:
    def __init__(self,repo,author,token,share_evidence=False):
        if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+",repo) or not re.fullmatch(r"[A-Za-z0-9-]{1,39}",author) or not token:
            raise ValueError("Invalid settings")
        self.base="https://api.github.com/repos/"+repo
        self.author=author.lower()
        self.token=token
        self.share_evidence=bool(share_evidence)
        self.repo_id=None
        self.opener=urllib.request.build_opener(NoRedirect)
    def request(self,path="",data=None):
        req=urllib.request.Request(self.base+path,data=None if data is None else json.dumps(data).encode(),
             headers={"Authorization":"Bearer "+self.token,"Accept":"application/vnd.github+json",
                      "X-GitHub-Api-Version":"2022-11-28","User-Agent":"Windows-ROM-Host/1",
                      "Content-Type":"application/json"})
        with self.opener.open(req,timeout=15) as res:raw=res.read(2*1024*1024+1)
        if len(raw)>2*1024*1024:raise ValueError("Response too large")
        return json.loads(raw)
    def verify(self):
        meta=self.request()
        if meta.get("private") is not True:raise ValueError("Queue must be private")
        if self.share_evidence:
            ident=meta.get("id")
            if type(ident) is not int or ident<=0:raise ValueError("Invalid queue identity")
            if self.repo_id is None:self.repo_id=ident
            if self.repo_id!=ident:raise ValueError("Queue identity changed")
    def pending(self):
        self.verify()
        for page in range(1,11):
            rows=self.request("/issues?state=open&sort=created&direction=desc&per_page=100&page="+str(page))
            if not isinstance(rows,list):raise ValueError("Invalid issue response")
            for issue in rows:
                if ("pull_request" not in issue and issue.get("title")==TITLE
                    and issue.get("user",{}).get("login","").lower()==self.author
                    and type(issue.get("id")) is int and type(issue.get("number")) is int):
                    yield issue
            if len(rows)<100:return
    def result(self,n,status):
        if type(n) is not int or n<1 or status not in STATUSES:raise ValueError("Invalid result")
        self.verify()
        self.request("/issues/"+str(n)+"/comments",{"body":"ROM Test Host v1: **"+status+"**. Detailed evidence retained locally."})

    def evidence(self,n,body):
        if not self.share_evidence:raise ValueError("Evidence sharing disabled")
        if type(n) is not int or n<1 or not body.startswith("ROM-EVIDENCE v1\n") or len(body)>48000:
            raise ValueError("Invalid evidence envelope")
        self.verify()
        self.request("/issues/"+str(n)+"/comments",{"body":body})

def write_ledger(path,ledger):
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger,indent=2),encoding="utf-8")
    os.replace(tmp,path)

def poll(remote,path,stop,emit):
    # One Windows process may own the queue ledger at a time.
    import msvcrt
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.with_suffix(".lock").open("a+b") as lock:
        if lock.tell()==0:lock.write(b"0");lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        ledger=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        while not stop.is_set():
            try:
                for issue in remote.pending():
                    if stop.is_set():break
                    key=str(issue["id"])
                    if key not in ledger:
                        ledger[key]={"status":"HOST_ERROR","posted":False,"run_id":"remote-"+uuid.uuid4().hex,"evidence_next":0}
                        write_ledger(path,ledger)
                        try:job=validate(issue.get("body"))
                        except Exception:status="INVALID_JOB"
                        else:
                            emit("Running issue #"+str(issue["number"]))
                            try:status=run(job,stop,run_id=ledger[key]["run_id"])
                            except Exception:status="HOST_ERROR"
                        ledger[key]["status"]=status
                        write_ledger(path,ledger)
                    if not ledger[key]["posted"]:
                        remote.result(issue["number"],ledger[key]["status"])
                        ledger[key]["posted"]=True
                        write_ledger(path,ledger)
                        emit("Issue #"+str(issue["number"])+": "+ledger[key]["status"])
                    entry=ledger[key]
                    if remote.share_evidence and entry.get("run_id") and not entry.get("evidence_done"):
                        parts=evidence_parts(RUNS/entry["run_id"])
                        for index in range(entry.get("evidence_next",0),len(parts)):
                            if stop.is_set():break
                            remote.evidence(issue["number"],parts[index])
                            entry["evidence_next"]=index+1
                            write_ledger(path,ledger)
                            stop.wait(1.2)
                        if entry.get("evidence_next",0)==len(parts):
                            entry["evidence_done"]=True
                            write_ledger(path,ledger)
                            emit("Issue #"+str(issue["number"])+": evidence sent ("+str(len(parts))+" parts)")
            except Exception as e:
                emit("Queue unavailable ("+type(e).__name__+"); retrying.")
            stop.wait(15)

def main():
    if tk is None:raise SystemExit("Tkinter required")
    window=tk.Tk();window.title("ROM Testing Host | Private queue");window.geometry("730x500")
    box=ttk.Frame(window,padding=18);box.pack(fill="both",expand=True)
    ttk.Label(box,text="Private remote testing queue",font=("Segoe UI",18,"bold")).pack(anchor="w")
    ttk.Label(box,text="Only bounded GBA scenarios. No incoming connections or remote code.").pack(anchor="w",pady=(0,12))
    fields=ttk.Frame(box);fields.pack(fill="x")
    repo,author,token=(tk.StringVar() for _ in range(3))
    for i,(label,var,show) in enumerate([("Private repository owner/name",repo,""),("Allowed issue author",author,""),("Fine-grained token (RAM only)",token,"*")]):
        ttk.Label(fields,text=label).grid(row=i,column=0,sticky="w",padx=(0,8),pady=4)
        ttk.Entry(fields,textvariable=var,show=show).grid(row=i,column=1,sticky="ew")
    fields.columnconfigure(1,weight=1)
    share=tk.BooleanVar(value=False)
    ttk.Checkbutton(box,text="Share game screenshots and bounded diagnostics in this private queue",variable=share).pack(anchor="w",pady=4)
    ttk.Label(box,text="ROMs, saves and arbitrary files stay local. Keep the repository private.").pack(anchor="w")
    status=tk.StringVar(value="Stopped");ttk.Label(box,textvariable=status).pack(anchor="w",pady=8)
    actions=ttk.Frame(box);actions.pack(fill="x")
    log=tk.Text(box,height=9,state="disabled",wrap="word");log.pack(fill="both",expand=True,pady=8)
    stop=threading.Event();messages=queue.Queue();worker=None
    def start():
        nonlocal worker
        if worker and worker.is_alive():return
        try:remote=Remote(repo.get().strip(),author.get().strip(),token.get().strip(),share_evidence=share.get())
        except ValueError as e:messagebox.showerror("Settings",str(e));return
        if share.get() and not messagebox.askyesno("Private evidence","Upload only test screenshots and filtered emulator diagnostics to this private GitHub issue queue? Keep the repository private."):return
        if not RUNNER.is_file():messagebox.showerror("Native runner","Build the Windows runner first.");return
        key=hashlib.sha256(repo.get().strip().lower().encode()).hexdigest()
        token.set("");stop.clear()
        def work():
            try:poll(remote,ROOT/"queues"/(key+".json"),stop,messages.put)
            except Exception as e:messages.put("Host stopped: "+type(e).__name__)
            finally:messages.put("Stopped")
        worker=threading.Thread(target=work,daemon=False);worker.start()
        status.set("Polling")
    ttk.Button(actions,text="Start polling",command=start).pack(side="left")
    ttk.Button(actions,text="Stop / cancel",command=stop.set).pack(side="left",padx=8)
    def drain():
        while not messages.empty():
            s=messages.get();status.set(s)
            log.configure(state="normal");log.insert("end",s+"\n");log.see("end");log.configure(state="disabled")
        window.after(150,drain)
    def close():
        stop.set()
        if worker and worker.is_alive():window.after(150,close)
        else:window.destroy()
    window.protocol("WM_DELETE_WINDOW",close);window.after(150,drain);window.mainloop()

if __name__=="__main__":main()
