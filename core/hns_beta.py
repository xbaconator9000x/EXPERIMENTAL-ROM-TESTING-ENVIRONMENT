"""Bounded source-symbol-driven Heart & Soul new-game beta.

This is a state machine, not a blind replay. Every milestone is witnessed
in native mGBA using the exact locally compiled ELF. No RAM writes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from core.live import Live, LiveError

A, START = 1, 8
PREFIX = "Task_NewGameHnsSpeech_"
CHALLENGE = "CB2_InitChallengeMenu"

def symbols(elf):
    raw = subprocess.check_output(["arm-none-eabi-nm", "-an", str(elf)], text=True)
    result = {}
    for line in raw.splitlines():
        p = line.split()
        if len(p) == 3 and p[1] in "tTbBdDrR":
            try:
                address = int(p[0],16)
            except ValueError:
                continue
            result.setdefault(p[2],set()).add(address)
    return result

class Beta:
    def __init__(self, live, syms, report):
        self.live, self.syms, self.report = live, syms, report
        self.frames = 0
        self.main = self.address("gMain")
        self.tasks = self.address("gTasks")
        self.address("Task_TitleScreenPhase3")
        self.address("Task_HandleMainMenuInput")
        self.address("CB2_NamingScreen")
        self.address(CHALLENGE)
        self.last = None

    def address(self, name):
        values = self.syms.get(name,set())
        if len(values)!=1:
            raise LiveError(f"missing or ambiguous ELF symbol: {name}")
        return next(iter(values))

    def step(self, keys=0, frames=1):
        self.frames = self.live.step(keys,frames)
        if self.frames>45000:
            raise LiveError("overall beta frame budget exhausted")

    def tap(self, keys):
        self.step(keys,2)
        self.step(0,2)

    def state(self):
        callback=self.live.integer(self.main+4,4)&~1
        raw=self.live.read(self.tasks,40*16)
        active={int.from_bytes(raw[i:i+4],"little")&~1
                for i in range(0,len(raw),40) if raw[i+4]==1}
        return callback,active

    def has(self,state,name,callback=False):
        values={a&~1 for a in self.syms.get(name,())}
        return state[0] in values if callback else bool(state[1]&values)

    def note(self,label):
        self.report["milestones"].append({"name":label,"frame":self.frames})
        print(f"HNS MILESTONE {label} frame={self.frames}",flush=True)

    def wait(self, target, allowed=(), *, callback=False, budget=12000):
        deadline=self.frames+budget
        while self.frames<deadline:
            s=self.state()
            if self.has(s,target,callback):
                self.note(target)
                return
            # Input only in source-identified tasks. Unknown states idle.
            if any(self.has(s,name) for name in allowed):
                self.tap(A)
                self.step(0,8)
            else:
                self.step(0,2)
        # Retain descriptive diagnostics; do not dump memory or game data.
        c,t=self.state()
        names=sorted(n for n,v in self.syms.items() if any((a&~1) in t for a in v)
                     and n.startswith("Task_"))
        cb=sorted(n for n,v in self.syms.items() if any((a&~1)==c for a in v)
                  and (n.startswith("CB2_") or n.startswith("MainCB")))
        self.report["last_state"]={"callback":cb,"tasks":names,"frame":self.frames}
        raise LiveError(f"timed out waiting for {target}")

    def execute(self):
        self.wait("Task_TitleScreenPhase3",("Task_CallIntroCallback",
                  "Task_HandleExpansionIntro","Task_TitleScreenPhase1","Task_TitleScreenPhase2"))
        self.tap(START)
        self.wait("Task_HandleMainMenuInput",
                  ("Task_MainMenuCheckSaveFile","Task_MainMenuCheckBattery"))
        self.tap(A)
        speech=[PREFIX+x for x in ("ThisIsAPokemon","MainSpeech","AndYouAre")]
        self.wait(PREFIX+"ChooseGender",speech)
        self.tap(A)
        self.wait("CB2_NamingScreen",(PREFIX+"WaitPressBeforeNameChoice",),callback=True)
        self.step(0,90)
        if not self.has(self.state(),"CB2_NamingScreen",True):
            raise LiveError("unexpected naming exit")
        # First visible keyboard character; START selects OK, A confirms.
        self.tap(A)
        self.step(0,12)
        self.tap(START)
        self.step(0,12)
        self.tap(A)
        self.wait(PREFIX+"ProcessNameYesNoMenu",(),budget=12000)
        self.tap(A)
        self.wait(CHALLENGE,(PREFIX+"WaitPressDisclaimer",),callback=True,budget=12000)
        self.report["acceptance"]="challenge_setup_reached"
        self.report["full_campaign_complete"]=False

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("runner","rom","elf","out"):
        p.add_argument("--"+n,required=True)
    a=p.parse_args()
    report={"rom_sha256":hashlib.sha256(Path(a.rom).read_bytes()).hexdigest(),
            "elf_sha256":hashlib.sha256(Path(a.elf).read_bytes()).hexdigest(),
            "milestones":[],"acceptance":"not_passed","full_campaign_complete":False}
    try:
        with Live(a.runner,a.rom,report["rom_sha256"]) as live:
            beta=Beta(live,symbols(a.elf),report)
            beta.execute()
        print("HNS BETA PASS: challenge setup reached; not a full campaign")
    except Exception as e:
        report["failure"]=str(e)
        raise
    finally:
        out=Path(a.out)
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(report,indent=2)+"\n")

if __name__=="__main__":
    main()
