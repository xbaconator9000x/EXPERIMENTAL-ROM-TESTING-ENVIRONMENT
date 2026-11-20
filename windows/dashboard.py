"""Read-only local dashboard for the running continuous GBA player.

No token, network listener, additional dependencies or emulator restart.
Reads only the controller's bounded atomic checkpoint envelope.
"""
import argparse
import hashlib
import json
import os
import struct
import time
from pathlib import Path
try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    tk=ttk=None

MAGIC=b"GBA-AUTOPLAY-1\n"
MAX_SIZE=2*1024*1024+512*1024
ROOT=Path(os.environ.get("LOCALAPPDATA") or Path.home())/"ROMTestingHost"/"autoplay"

def digest(data):return hashlib.sha256(data).hexdigest()

def snapshot(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file():raise ValueError("Checkpoint not available")
    with path.open("rb") as f:
        # Atomic replacement may happen while we read; use one file handle.
        info=os.fstat(f.fileno())
        if not 0<info.st_size<=MAX_SIZE:raise ValueError("Invalid checkpoint size")
        if f.read(len(MAGIC))!=MAGIC:raise ValueError("Invalid checkpoint format")
        raw=f.read(4)
        if len(raw)!=4:raise ValueError("Truncated header")
        n=struct.unpack(">I",raw)[0]
        if not 0<n<=256*1024:raise ValueError("Invalid header size")
        header=json.loads(f.read(n))
        size=header["size"]
        if type(size) is not int or not 0<size<=2*1024*1024:raise ValueError("Invalid state size")
        state=f.read(size);rgb=f.read(115201)
    if len(state)!=size or len(rgb)!=115200 or digest(state)!=header["state_sha"] or digest(rgb)!=header["rgb_sha"]:
        raise ValueError("Checkpoint hash mismatch")
    identity=header["identity"];meta=header["meta"]
    if type(identity) is not dict or type(meta) is not dict:raise ValueError("Invalid metadata")
    for key in ("frames","decisions"):
        if type(meta.get(key)) is not int or meta[key]<0:raise ValueError("Invalid counter")
    if type(meta.get("history")) is not list or len(meta["history"])>80:raise ValueError("Invalid history")
    return identity,meta,rgb,info.st_mtime

def find_goals(root=ROOT,queue=None):
    root=Path(root)
    if queue:root=root/hashlib.sha256(queue.lower().encode()).hexdigest()
    parents=[root] if queue else [p for p in root.iterdir() if p.is_dir() and not p.is_symlink() and len(p.name)==64] if root.is_dir() else []
    paths=[]
    for parent in parents:
        if not parent.is_dir() or parent.is_symlink():continue
        for p in parent.iterdir():
            if p.name.isdecimal() and p.is_dir() and not p.is_symlink():paths.append(p)
    return sorted(paths,key=lambda p:p.name,reverse=True)

def terminal(folder):
    p=folder/"terminal.json"
    if p.is_symlink() or not p.is_file() or p.stat().st_size>4096:return None
    try:
        status=json.loads(p.read_text(encoding="utf-8"))["status"]
        return status if status in ("NEEDS_REVIEW","EMULATOR_ERROR","BUDGET_REACHED") else None
    except (OSError,ValueError,KeyError):return None

def pretty_age(value):
    value=max(0,int(value))
    if value<60:return f"{value}s"
    if value<3600:return f"{value//60}m {value%60:02d}s"
    return f"{value//3600}h {(value%3600)//60:02d}m"

def action_text(row):
    actions=row.get("actions",[])
    return "  /  ".join(f"{a.get('button','?')} {a.get('frames','?')}f" for a in actions if isinstance(a,dict)) or "—"

class Dashboard:
    def __init__(self,root,queue=None,goal_id=None):
        self.root=root;self.queue=queue;self.goal_id=goal_id;self.selected=None
        self.last=None;self.picture=None;self.last_image=None;self.measure=None;self.seconds_per_turn=None
        root.title("ROM Testing Host | Live AI player")
        root.configure(bg="#111827");root.minsize(850,680)
        style=ttk.Style();style.theme_use("clam")
        style.configure("Panel.TFrame",background="#111827")
        style.configure("Card.TFrame",background="#1f2937")
        style.configure("Header.TLabel",background="#111827",foreground="#f9fafb",font=("Segoe UI",21,"bold"))
        style.configure("Sub.TLabel",background="#111827",foreground="#9ca3af",font=("Segoe UI",10))
        style.configure("Metric.TLabel",background="#1f2937",foreground="#f9fafb",font=("Segoe UI",19,"bold"))
        style.configure("Small.TLabel",background="#1f2937",foreground="#9ca3af",font=("Segoe UI",10))
        style.configure("Body.TLabel",background="#1f2937",foreground="#f3f4f6",font=("Segoe UI",11))
        wrapper=ttk.Frame(root,style="Panel.TFrame",padding=18);wrapper.pack(fill="both",expand=True)
        header=ttk.Frame(wrapper,style="Panel.TFrame");header.pack(fill="x")
        ttk.Label(header,text="Live AI Playthrough",style="Header.TLabel").pack(side="left")
        self.state=tk.Label(header,text="WAITING FOR PLAYER",font=("Segoe UI",11,"bold"),bg="#374151",fg="#f3f4f6",padx=10,pady=5);self.state.pack(side="right")
        self.subtitle=ttk.Label(wrapper,text="Read-only view · updates once per second",style="Sub.TLabel");self.subtitle.pack(anchor="w",pady=(2,12))
        self.goalpicker=ttk.Combobox(wrapper,state="readonly",width=28);self.goalpicker.pack(anchor="w",pady=(0,10))
        self.goalpicker.bind("<<ComboboxSelected>>",self.pick)
        metrics=ttk.Frame(wrapper,style="Panel.TFrame");metrics.pack(fill="x",pady=(0,12))
        self.metrics={}
        for i,(key,label) in enumerate([("decisions","AI decisions"),("frames","GBA frames"),("speed","Recent decision time"),("age","Checkpoint age")]):
            card=ttk.Frame(metrics,style="Card.TFrame",padding=10);card.grid(row=0,column=i,sticky="nsew",padx=(0,7))
            metrics.columnconfigure(i,weight=1)
            ttk.Label(card,text=label,style="Small.TLabel").pack(anchor="w")
            v=ttk.Label(card,text="—",style="Metric.TLabel");v.pack(anchor="w");self.metrics[key]=v
        content=ttk.Frame(wrapper,style="Panel.TFrame");content.pack(fill="both",expand=True)
        left=ttk.Frame(content,style="Card.TFrame",padding=10);left.pack(side="left",fill="both",expand=True,padx=(0,8))
        ttk.Label(left,text="Emulator screen",style="Small.TLabel").pack(anchor="w",pady=(0,5))
        self.canvas=tk.Label(left,bg="#030712",fg="#9ca3af",text="Waiting for first checkpoint",font=("Segoe UI",12),width=40,height=16)
        self.canvas.pack(fill="both",expand=True)
        self.model=ttk.Label(left,text="Model: —",style="Small.TLabel",wraplength=480);self.model.pack(anchor="w",pady=(6,0))
        right=ttk.Frame(content,style="Card.TFrame",padding=12);right.pack(side="right",fill="both",expand=True)
        ttk.Label(right,text="Most recent AI interpretation",style="Small.TLabel").pack(anchor="w")
        self.scene=ttk.Label(right,text="—",style="Body.TLabel",wraplength=310,justify="left");self.scene.pack(anchor="w",pady=(4,10))
        ttk.Label(right,text="Current goal",style="Small.TLabel").pack(anchor="w")
        self.objective=ttk.Label(right,text="—",style="Body.TLabel",wraplength=310,justify="left");self.objective.pack(anchor="w",pady=(4,10))
        ttk.Label(right,text="Last executed controls",style="Small.TLabel").pack(anchor="w")
        self.controls=ttk.Label(right,text="—",style="Metric.TLabel",wraplength=310);self.controls.pack(anchor="w",pady=(4,10))
        ttk.Label(right,text="Recent decision history",style="Small.TLabel").pack(anchor="w",pady=(3,4))
        self.history=tk.Text(right,height=10,width=38,bg="#111827",fg="#d1d5db",relief="flat",font=("Consolas",10),wrap="word",state="disabled")
        self.history.pack(fill="both",expand=True)
        self.footer=ttk.Label(wrapper,text="No host controls · no network exposure · close this window without stopping the AI.",style="Sub.TLabel",wraplength=800);self.footer.pack(anchor="w",pady=(10,0))
        self.refresh()
    def pick(self,event=None):
        idx=self.goalpicker.current()
        if idx>=0 and idx<len(self.paths):
            self.selected=self.paths[idx];self.last=None;self.measure=None;self.seconds_per_turn=None;self.last_image=None;self.goal_id=self.selected.name
    def status(self,text,color="#374151"):
        self.state.configure(text=text,bg=color)
    def refresh(self):
        try:
            self.paths=find_goals(queue=self.queue)
            self.goalpicker.configure(values=[f"Goal {p.name}" for p in self.paths])
            if self.selected not in self.paths:
                self.selected=next((p for p in self.paths if p.name==self.goal_id),None) if self.goal_id else (self.paths[0] if self.paths else None)
                if self.selected:self.goalpicker.current(self.paths.index(self.selected))
            if self.selected is None:
                self.status("WAITING FOR PLAYER")
                self.footer.configure(text="No goal folder yet. Check the continuous player PowerShell window.")
                return
            p=self.selected/"progress.bin"
            if not p.is_file():
                self.status("WAITING FOR CHECKPOINT")
                self.footer.configure(text="Goal found, but the emulator has not saved its first checkpoint.")
                return
            stamp=p.stat().st_mtime_ns
            if self.last!=(self.selected,stamp):
                identity,meta,rgb,mtime=snapshot(p)
                self.last=(self.selected,stamp);self.data=(identity,meta,rgb,mtime)
                if self.measure and meta["decisions"]>self.measure[0]:
                    self.seconds_per_turn=max(0,(mtime-self.measure[1])/(meta["decisions"]-self.measure[0]))
                self.measure=(meta["decisions"],mtime)
                if digest(rgb)!=self.last_image:
                    self.picture=tk.PhotoImage(data=b"P6\n240 160\n255\n"+rgb,format="PPM").zoom(2,2)
                    self.canvas.configure(image=self.picture,text="",width=480,height=320);self.last_image=digest(rgb)
                self.metrics["decisions"].configure(text=f'{meta["decisions"]:,}')
                self.metrics["frames"].configure(text=f'{meta["frames"]:,}')
                self.metrics["speed"].configure(text=f"{self.seconds_per_turn:.1f}s" if self.seconds_per_turn is not None else "—")
                history=meta["history"];recent=history[-1] if history else {}
                self.scene.configure(text=str(recent.get("scene","Waiting for first AI decision"))[:240])
                self.objective.configure(text=str(recent.get("objective",identity.get("goal","—")))[:500])
                self.controls.configure(text=action_text(recent) if recent else "—")
                self.model.configure(text="Model: "+str(identity.get("model","—"))[:100])
                self.history.configure(state="normal");self.history.delete("1.0","end")
                for row in reversed(history[-12:]):
                    self.history.insert("end",f"#{row.get('decision','?')}  {action_text(row)}\n{str(row.get('scene',''))[:100]}\n\n")
                self.history.configure(state="disabled")
            identity,meta,rgb,mtime=self.data;age=max(0,time.time()-mtime)
            self.metrics["age"].configure(text=pretty_age(age))
            end=terminal(self.selected)
            if end:self.status(end.replace("_"," "),"#92400e" if end!="EMULATOR_ERROR" else "#991b1b")
            elif meta.get("model_error"):self.status("MODEL RETRY: "+str(meta["model_error"]),"#92400e")
            elif meta.get("review"):self.status("REVIEW REQUESTED","#92400e")
            elif age>180:self.status("NO RECENT CHECKPOINT","#92400e")
            elif meta["decisions"]==0:self.status("FIRST DECISION PENDING","#1d4ed8")
            else:self.status("CHECKPOINT VERIFIED","#166534")
            self.footer.configure(text="Screen and counters reflect the last saved decision, not continuous 60 FPS video. "+("No recent update; the model may be slow, stopped, or retrying." if age>180 else "Hash-verified local checkpoint."))
        except (OSError,ValueError,KeyError,TypeError,tk.TclError):
            self.status("WAITING FOR VALID SNAPSHOT","#92400e")
            self.footer.configure(text="Checkpoint not readable yet; retrying automatically.")
            self.last=None
        finally:self.root.after(1000,self.refresh)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--queue");p.add_argument("--goal-id")
    a=p.parse_args()
    if a.goal_id and not a.goal_id.isdecimal():p.error("Goal ID must be numeric")
    if tk is None:raise SystemExit("Tkinter required for dashboard GUI")
    root=tk.Tk();Dashboard(root,a.queue,a.goal_id);root.mainloop()

if __name__=="__main__":main()
