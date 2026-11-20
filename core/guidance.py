"""Private phone-to-player guidance: no code, paths, memory writes or stale inputs."""
import json
import re
from core.autoplay import parse_decision

PREFIX="ROM-GUIDE v1\n"
def parse_guide(body,decision,screen):
    if not isinstance(body,str) or not body.startswith(PREFIX) or len(body)>4096:return None
    try:
        v=json.loads(body[len(PREFIX):])
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
