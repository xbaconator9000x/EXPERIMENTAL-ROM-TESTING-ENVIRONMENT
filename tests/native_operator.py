"""Real native mGBA control acceptance on original synthetic test ROM only."""
import hashlib
import json
import os
import tempfile
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from core.live import Live
from core.autoplay import digest
from core.operator_control import OperatorControl,validate_command

root=Path(__file__).resolve().parent.parent
rom=root/"build"/"synthetic.gba"
runner=root/"build"/("live_runner.exe" if os.name=="nt" else "live_runner")
sha=digest(rom.read_bytes())
identity={"rom":sha,"runner":digest(runner.read_bytes()),"goal":"native synthetic operator smoke","model":"fixture"}
def command(action,args=None):
    return validate_command(json.dumps({"version":1,"rom_sha256":sha,"action":action,"args":args or {}}),sha)
with tempfile.TemporaryDirectory(prefix="operator-fixture-") as directory:
    responses=[]
    operator=OperatorControl(directory,identity,runner,rom,sha,ack=lambda *x,**kw:responses.append(x))
    live=Live(runner,rom,sha)
    try:
        live.step(0,600)
        live.step(0,300)
        live.step(1,6)
        assert live.integer(0x02000000,4)==0,"synthetic A event not native"
        meta={"decisions":0,"frames":906,"history":[]}
        live,meta,rgb,_=operator.apply(1,command("snapshot",{"name":"key-held"}),live,meta,live.rgb())
        live.step(0,16)
        assert live.integer(0x02000000,4)==1,"release should reach native EWRAM"
        live,meta,rgb,_=operator.apply(2,command("restore",{"name":"key-held"}),live,meta,live.rgb())
        assert live.integer(0x02000000,4)==0,"native state restore failed"
        live,meta,rgb,_=operator.apply(3,command("input",{"actions":[{"button":"A","frames":8}]}),live,meta,rgb)
        assert live.integer(0x02000000,4)==1,"native input must include key release"
        live,meta,rgb,_=operator.apply(4,command("hard_reset"),live,meta,rgb)
        assert live.integer(0x02000000,4)==1,"hard boot did not reset EWRAM"
        live,meta,rgb,_=operator.apply(5,command("restore",{"name":"key-held"}),live,meta,rgb)
        assert live.integer(0x02000000,4)==0,"restore after hard boot failed"
        assert [r[1] for r in responses]==["EXECUTED"]*5
        assert len(list((Path(directory)/"operator-states").glob("before-*.bin")))==4
        print("PASS: synthetic native control state restore, input, hard boot and restore")
    finally:live.close()
