"""Execute the pinned upstream LeafGreen agent's actual skill dispatcher.

The upstream checkout is an explicit local dependency, not downloaded/executed
by a model. All its emulator calls terminate in the harness's native Live API.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from core.upstream_port import ReadOnlyClient, PortError, UPSTREAM_COMMIT, admit
from core.upstream_leafgreen.constants import Addr

KEYS={"a":1,"b":2,"select":4,"start":8,"right":16,"left":32,"up":64,"down":128,"r":256,"l":512}
ACTION_CALLBACKS=(Addr.CTRL_CHOOSE_ACTION,Addr.CTRL_CHOOSE_ACTION_ALT,*Addr.SAFARI_MENU)

class SkillAbort(BaseException):
    """Do not allow upstream broad Exception handlers to swallow an unsafe action."""

class SkillTransport(ReadOnlyClient):
    def __init__(self,live,should_stop=lambda:False,max_frames=12000):
        super().__init__(live)
        self.should_stop=should_stop
        self.max_frames=max_frames
        self.frames=0
        self.actions=[]
        self.watchdog=None
        self.deadline=None

    def start(self):
        self.frames=0
        self.actions=[]
        self.deadline=time.monotonic()+180

    def set_watchdog(self,wd):
        self.watchdog=wd

    def _advance(self,mask,n):
        if type(n) is not int or not 0<=n<=self.max_frames:
            raise SkillAbort("invalid native frame request")
        while n:
            if self.should_stop() or (self.deadline is not None and time.monotonic()>self.deadline):
                raise SkillAbort("skill interrupted")
            k=min(n,600)
            if self.frames+k>self.max_frames:
                raise SkillAbort("harness frame budget reached")
            if self.watchdog is not None:
                self.watchdog.advance(k)
            self.live.step(mask,k)
            self.frames+=k
            self.actions.append([mask,k])
            n-=k

    def run_frames(self,n):
        self._advance(0,n)

    def tick(self,frames=6):
        self._advance(0,frames)

    def tap(self,button):
        self._advance(self._key(button),8)
        self.tick(8)

    def hold(self,button,duration_frames):
        self._advance(self._key(button),max(1,duration_frames))
        self.tick(2)

    @staticmethod
    def _key(button):
        try:return KEYS[button.lower()]
        except (AttributeError,KeyError):raise SkillAbort("unsupported button") from None

    def wait_until_idle(self,max_frames=300,stable=8):
        # Sample live RGB at four-frame intervals. Unlike the upstream native
        # binding the existing transport is a subprocess; avoid one IPC/frame.
        # A sparse pixel stride can alias two distinct menu/dialogue frames.
        # Hash the complete native RGB frame instead; do not mistake an
        # animation or an advancing dialogue box for an idle menu.
        import hashlib
        last=None
        count=0
        advanced=0
        while advanced<max_frames:
            n=min(4,max_frames-advanced)
            self.tick(n);advanced+=n
            frame=self.live.rgb()
            if not isinstance(frame,bytes) or len(frame)!=240*160*3:
                raise SkillAbort("invalid native RGB frame")
            sample=hashlib.blake2s(frame,digest_size=16).digest()
            count=count+n if sample==last else 0
            last=sample
            if count>=stable:return True
        return False

    def write8(self,address,value):
        """Translate ONLY the upstream battle-cursor API into real D-pad input."""
        if type(value) is not int or not 0<=value<=3:
            raise SkillAbort("unsupported memory write")
        if address not in (Addr.ACTION_CURSOR,Addr.MOVE_CURSOR):
            raise SkillAbort("unsupported memory write; skill requires a read-only adaptation")
        gates=ACTION_CALLBACKS if address==Addr.ACTION_CURSOR else (Addr.CTRL_CHOOSE_MOVE,)
        cb=self.read32(Addr.GMAIN_CALLBACK2)
        controller=self.read32(Addr.BATTLE_CTRL_FUNC)
        # upstream _battle_advance asks for FIGHT even during battle text.
        # Its write was only useful on the action menu; preserve no-op semantics
        # elsewhere WITHOUT changing even one byte of the game.
        if address==Addr.ACTION_CURSOR and value==0 and controller not in gates:
            if cb==Addr.CB2_BATTLE:return True
        if cb!=Addr.CB2_BATTLE or controller not in gates:
            raise SkillAbort("cursor selection lacks live menu witness")
        for _ in range(6):
            if self.read32(Addr.GMAIN_CALLBACK2)!=Addr.CB2_BATTLE or self.read32(Addr.BATTLE_CTRL_FUNC) not in gates:
                raise SkillAbort("menu changed during cursor selection")
            current=self.read8(address)
            if not 0<=current<=3:raise SkillAbort("invalid live cursor")
            if current==value:return True
            if current//2!=value//2:
                button="Down" if value//2>current//2 else "Up"
            else:
                button="Right" if value%2>current%2 else "Left"
            self.tap(button)
        raise SkillAbort("cursor did not reach requested selection")

    def write16(self,*args):
        raise SkillAbort("memory writes prohibited")
    write32=write16

    def screenshot(self,path):
        from core.autoplay import png
        Path(path).write_bytes(png(self.live.rgb()))

    def get_game_code(self):
        return "AGB-"+self.read_range(0x080000ac,4).decode("ascii")

    def get_game_title(self):
        return self.read_range(0x080000a0,12).rstrip(b"\x00").decode("ascii","replace")

    def verify_connection(self):
        return self.get_game_code()=="AGB-BPGE"

    def log(self,message):
        pass

    def save_state(self,*args):
        # The harness owns checkpoints; no hidden skill save/rollback.
        return False

    def load_state(self,*args):
        return False

    def saved_this_session(self,*args):
        return False

    def latest_session_slot(self):
        return None

# Deliberate allowlist; arbitrary upstream functions, resets and load-state are
# never exposed to the local model. Quest/story is still vanilla-only.
TOOL_ARGS={
    "read_game_state":{}, "advance_dialog":{}, "close_menus":{}, "heal":{},
    "flee_battle":{}, "train_party":{}, "team_report":{}, "pick_up_items":{},
    "challenge_leader":{}, "save_game":{},
    "press_button":{"button":str,"times":int},
    "walk_to":{"x":int,"y":int}, "go_to":{"destination":str},
    "go_to_map":{"direction":str}, "use_move":{"move":str},
    "switch_pokemon":{"target":str}, "catch":{"nickname":str},
    "use_item":{"item":str,"target":str}, "reorder_party":{"first":str,"second":str},
    "open_menu":{"menu":str}, "answer_prompt":{"answer":str}, "shop":{"item":str,"quantity":int},
    "quest":{"name":str}, "grind":{"level":int,"catch":bool},
    "inspect_pokemon":{"pokemon":str},
}
REQUIRED={
    "press_button":{"button"},"walk_to":{"x","y"},"go_to":{"destination"},
    "go_to_map":{"direction"},"use_move":{"move"},"switch_pokemon":{"target"},
    "use_item":{"item"},"reorder_party":{"first"},"open_menu":{"menu"},
    "answer_prompt":{"answer"},"quest":{"name"},"inspect_pokemon":{"pokemon"}
}

def validate_tool(name,args):
    if not isinstance(name,str) or name not in TOOL_ARGS or type(args) is not dict:
        raise ValueError("unsupported skill")
    schema=TOOL_ARGS[name]
    if not REQUIRED.get(name,set())<=args.keys()<=schema.keys():
        raise ValueError("invalid skill arguments")
    for key,v in args.items():
        if type(v) is not schema[key]:raise ValueError("invalid argument type")
        if isinstance(v,str) and (len(v)>120 or any(ord(c)<32 for c in v)):
            raise ValueError("invalid string")
        if type(v) is int and not 0<=v<=255:raise ValueError("invalid integer")
    if name=="press_button" and (args["button"].lower() not in KEYS or not 1<=args.get("times",1)<=10):
        raise ValueError("invalid button")
    if name=="shop" and not 1<=args.get("quantity",1)<=20:
        raise ValueError("invalid quantity")
    if name=="grind" and not 0<=args.get("level",0)<=100:
        raise ValueError("invalid level")
    return name,args

def verified_checkout(path):
    path=Path(path).resolve()
    def git(*args):
        return subprocess.check_output(["git","-C",str(path),*args],text=True,timeout=20).strip()
    if git("rev-parse","HEAD")!=UPSTREAM_COMMIT or git("status","--porcelain","--untracked-files=no"):
        raise PortError("upstream checkout must match the pinned clean commit")
    return path

class SkillSession:
    def __init__(self,checkout,rom,live,folder,model,should_stop=lambda:False):
        admit(rom,live)
        checkout=verified_checkout(checkout)
        # This entry point runs in the harness process, which must not already
        # have a different top-level upstream package loaded.
        for key,module in list(sys.modules.items()):
            if key.split(".")[0] not in ("agent","game","knowledge","memory","config"):continue
            origin=getattr(module,"__file__",None)
            if origin and not Path(origin).resolve().is_relative_to(checkout):
                raise PortError("upstream package namespace is already occupied")
            if not origin and any(not Path(p).resolve().is_relative_to(checkout) for p in getattr(module,"__path__",[])):
                raise PortError("upstream namespace is already occupied")
        if not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,100}",model):
            raise PortError("invalid local model")
        folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
        os.environ.update(LLM_BASE_URL="http://127.0.0.1:11434/v1",LLM_API_KEY="ollama",
                          MODEL_NAME=model,BATTLE_STYLE="",USE_VISION="false",SHOW_WINDOW="false",
                          SCREENSHOT_PATH=str(folder/"upstream-frame.png"))
        if str(checkout) not in sys.path:sys.path.insert(0,str(checkout))
        from agent.lm_studio_client import AgentClient
        from game.memory_reader import LeafGreenReader
        from memory.long_term import LongTermMemory
        self.transport=SkillTransport(live,should_stop)
        self.reader=LeafGreenReader(self.transport)
        from core.upstream_shop import ReadOnlyShopMixin
        class InputOnlyAgent(ReadOnlyShopMixin,AgentClient):
            pass
        self.client=InputOnlyAgent(self.transport,self.reader,LongTermMemory(path=str(folder/"upstream-memory.json")))

    def observe(self):
        from dataclasses import asdict
        s=asdict(self.reader.read_state())
        s["context"]=s["context"].name
        return s

    def execute(self,name,args):
        name,args=validate_tool(name,args)
        self.transport.start()
        try:
            result=self.client._execute(name,json.dumps(args))
            return str(result)[:2000]
        except SkillAbort as exc:
            return "SKILL_STOPPED: "+str(exc)
        finally:
            self.transport.set_watchdog(None)
