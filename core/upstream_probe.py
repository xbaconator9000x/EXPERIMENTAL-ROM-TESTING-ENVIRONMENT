"""Local vanilla-ROM probe; never exports ROM bytes or overwrites checkpoints."""
import argparse
import dataclasses
import json
from pathlib import Path
from core.live import Live
from core.upstream_port import admit

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--runner",required=True)
    p.add_argument("--rom",required=True)
    p.add_argument("--sha256",required=True)
    p.add_argument("--state")
    p.add_argument("--tile",nargs=2,type=int)
    a=p.parse_args()
    with Live(a.runner,a.rom,a.sha256) as live:
        port=admit(a.rom,live)
        if a.state:
            path=Path(a.state)
            if not 0<path.stat().st_size<=2*1024*1024:
                raise ValueError("invalid checkpoint size")
            live.load_state(path.read_bytes())
        result=port.observe()
        if result["state"] is not None:
            result["state"]=dataclasses.asdict(result["state"])
        if a.tile:
            result["route"]=port.route(*a.tile)
        print(json.dumps(result,default=lambda obj:obj.name))

if __name__=="__main__":
    main()
