"""Private phone-to-player guidance: no code, paths, memory writes or stale inputs."""
import json
import hashlib
import os
from pathlib import Path
import re
from core.autoplay import parse_decision

PREFIX="ROM-GUIDE v1\n"
def parse_guide(body,decision,screen):
    if not isinstance(body,str) or not body.startswith(PREFIX) or len(body)>4096:return None
    try:
        def unique(pairs):
            obj={}
            for k,v in pairs:
                if k in obj:raise ValueError("Duplicate guide field")
                obj[k]=v
            return obj
        v=json.loads(body[len(PREFIX):],object_pairs_hook=unique)
        if type(v) is not dict or set(v)!={"decision","screen","scene","objective","actions"}:return None
        if type(v["decision"]) is not int or v["decision"]!=decision or v["screen"]!=screen or not re.fullmatch(r"[a-f0-9]{64}",screen):return None
        return parse_decision(json.dumps({"scene":v["scene"],"objective":v["objective"],"actions":v["actions"],"review":False}))
    except (ValueError,TypeError,KeyError):return None

def newest_guide(rows,author,decision,screen):
    for c in reversed(rows):
        if c.get("user",{}).get("login","").lower()!=author.lower():continue
        if c.get("author_association") not in ("OWNER","MEMBER","COLLABORATOR"):continue
        d=parse_guide(c.get("body"),decision,screen)
        if d:return d
    return None


def claim_guide(path,decision,screen,proposal,consume=False):
    """A failed remote action must not be replayed on every recovery poll."""
    path=Path(path)
    raw=json.dumps([decision,screen,proposal],sort_keys=True,separators=(",",":")).encode()
    key=hashlib.sha256(raw).hexdigest()
    if path.is_symlink():raise ValueError("Invalid guide history")
    seen=[]
    if path.is_file():
        if path.stat().st_size>128*1024:raise ValueError("Guide history size")
        seen=json.loads(path.read_text(encoding="ascii"))
        if not isinstance(seen,list) or any(not isinstance(x,str) or not re.fullmatch(r"[a-f0-9]{64}",x) for x in seen):
            raise ValueError("Invalid guide history")
    if key in seen:return False
    if consume:
        tmp=path.with_suffix(".tmp")
        tmp.write_text(json.dumps((seen+[key])[-1000:]),encoding="ascii")
        os.replace(tmp,path)
    return True
