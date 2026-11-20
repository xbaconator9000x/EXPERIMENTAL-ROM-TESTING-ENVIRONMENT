import struct,unittest
from core.firered import Field
from core.jj_fast import MAP_HEADER,VMAP
from core.jj_connections import crossings,observe_arrival
class Live:
    def __init__(self):
        self.ptr={MAP_HEADER+12:0x08000100,VMAP:19,VMAP+4:18,VMAP+8:0x02001000}
        self.data={0x08000100:struct.pack("<iI",1,0x08000200),0x08000200:struct.pack("<B3xiBB2x",4,0,3,4)}
        self.grid=bytearray(b"\xff\x03"*(19*18))
        self.grid[2*(8*19+11):2*(8*19+11)+2]=b"\x00\x00"
    def integer(self,a,n):return self.ptr[a]
    def read(self,a,n):return bytes(self.grid) if a==0x02001000 else self.data[a]
class Tests(unittest.TestCase):
    def test_live_boundary(self):
        f=Field((1,2),(2,1),4,4,(0,)*16)
        e=crossings(Live(),0x20000,f)
        self.assertEqual(e,[{"kind":"connection","x":3,"y":1,"id":0,"direction":"RIGHT","destination":[3,4]}])
        l=Live();l.grid[2*(8*19+11):2*(8*19+11)+2]=b"\x00\x04"
        self.assertEqual(crossings(l,0x20000,f),[])
    def test_observation_not_prediction(self):
        m={"pending_crossing":{"from":[1,2],"destination":[3,4],"event":0}}
        observe_arrival(m,None,False)
        self.assertNotIn("verified_crossings",m)
        observe_arrival(m,(Field((3,4),(0,1),4,4,(0,)*16),1,set()),True)
        self.assertTrue(m["verified_crossings"][0]["matched"])
        self.assertNotIn("pending_crossing",m)

    def test_explore_crossing_and_initial_party_priority(self):
        from core.jj_explore import Explorer
        class Adapter:
            def verified_field(self,c,m):return bool(c)
        ex=Explorer(Adapter());f=Field((1,2),(3,1),4,4,(0,)*16);c=(f,1,set())
        events=crossings(Live(),0x20000,f);m={}
        self.assertTrue(ex.request(c,m,(events,"RIGHT"),"exit"))
        d,cmd=ex.next(c,m,(events,"RIGHT"))
        self.assertEqual(cmd,("cross",None))
        self.assertEqual(d["actions"][0]["button"],"RIGHT")
        ex.finish(m,c,None,cmd)
        self.assertNotIn("verified_crossings",m)
        self.assertEqual(m["pending_crossing"]["destination"],[3,4])
        npc={"kind":"npc","x":0,"y":0,"id":1,"gfx":1}
        c=(f,1,{(0,0)})
        m={"native_party_count":0}
        self.assertTrue(ex.request(c,m,(events+[npc],"RIGHT"),"explore"))
        self.assertEqual(m["event_goal"]["event"]["kind"],"npc")
        m={"native_party_count":1}
        self.assertTrue(ex.request(c,m,(events+[npc],"RIGHT"),"explore"))
        self.assertEqual(m["event_goal"]["event"]["kind"],"connection")
