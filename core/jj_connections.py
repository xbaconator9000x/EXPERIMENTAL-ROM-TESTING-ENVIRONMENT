"""Conservative native cardinal map crossings; never write game memory."""
from core.firered import span
from core.jj_fast import MAP_HEADER,VMAP,DIR,u
from core.live import LiveError
DIRECTION={1:"DOWN",2:"UP",3:"LEFT",4:"RIGHT"}

def crossings(live,size,field):
    def romread(ptr,n):
        if ptr%4 or not span(ptr,n,0x08000000,0x08000000+size):raise ValueError("connection pointer")
        return live.read(ptr,n)
    ptr=live.integer(MAP_HEADER+12,4)
    if not ptr:return []
    head=romread(ptr,8)
    count=int.from_bytes(head[:4],"little",signed=True)
    if not 0<=count<=32:raise ValueError("connection count")
    if not count:return []
    raw=romread(u(head,4,4),count*12)
    rows=[]
    for i in range(count):
        row=raw[i*12:(i+1)*12];direction=DIRECTION.get(row[0])
        if direction:rows.append((i,direction,int.from_bytes(row[4:8],"little",signed=True),[row[8],row[9]]))
    vw,vh,grid=(live.integer(VMAP+i,4) for i in (0,4,8))
    if (vw,vh)!=(field.width+15,field.height+14) or vw*vh>0x2800 or grid%2 or not span(grid,vw*vh*2,0x02000000,0x02040000):raise ValueError("connection grid")
    padded=live.read(grid,vw*vh*2)
    result=[]
    for i,direction,offset,dest in rows:
        # Ambiguous multiple connections on a side require target map bounds.
        if sum(d==direction for _,d,_,_ in rows)!=1:continue
        dx,dy=DIR[direction]
        edge=([(x,0 if dy<0 else field.height-1) for x in range(field.width)] if dy else
              [(0 if dx<0 else field.width-1,y) for y in range(field.height)])
        valid=[]
        for x,y in edge:
            if not field.passable(x,y) or (x if dy else y)<offset:continue
            ix,iy=x+dx+7,y+dy+7
            if not (0<=ix<vw and 0<=iy<vh):continue
            tile=u(padded,2*(iy*vw+ix))
            if tile&0x3ff==0x3ff or tile&0xc00 or tile>>12 not in (0,field.tile(x,y)>>12):continue
            valid.append((x,y))
        valid.sort(key=lambda p:abs(p[0]-field.pos[0])+abs(p[1]-field.pos[1]))
        for x,y in valid[:8]:result.append({"kind":"connection","x":x,"y":y,"id":i,"direction":direction,"destination":dest})
    return result

def observe_arrival(meta,field,verified):
    p=meta.get("pending_crossing")
    if not p or not field or not verified:return
    arrived=list(field[0].map_id)
    if arrived!=p["from"]:
        row={"from":p["from"],"to":arrived,"event":p["event"],"matched":arrived==p["destination"]}
        edges=meta.setdefault("verified_crossings",[])
        if row not in edges:edges.append(row)
        meta["verified_crossings"]=edges[-100:]
    meta.pop("pending_crossing",None)
