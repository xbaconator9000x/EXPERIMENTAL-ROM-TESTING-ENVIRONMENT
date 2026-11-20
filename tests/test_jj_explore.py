import unittest
from core.firered import Field
from core.jj_explore import Explorer,options,event_key

class MockAdapter:
    def verified_field(self,c,m):return bool(c)

class TestExplorer(unittest.TestCase):
    def setup(self):
        f=Field((1,2),(1,1),5,5,(0,)*25)
        npc={"kind":"npc","x":3,"y":1,"id":1,"gfx":12}
        warp={"kind":"warp","x":4,"y":4,"id":0,"destination":[3,4]}
        return f,npc,warp
    def test_event_approach_and_interaction(self):
        f,npc,warp=self.setup();c=(f,1,{(3,1)})
        ex=Explorer(MockAdapter());m={};info=([npc,warp],"RIGHT")
        self.assertTrue(ex.request(c,m,info,"interact"))
        d,cmd=ex.next(c,m,info)
        self.assertEqual(d["actions"][0]["button"],"RIGHT")
        moved=Field(f.map_id,(2,1),5,5,f.tiles);c2=(moved,1,c[2])
        ex.finish(m,c,c2,cmd)
        d,cmd=ex.next(c2,m,info)
        self.assertEqual(d["actions"][0]["button"],"A")
        ex.finish(m,c2,None,cmd)
        self.assertEqual(m["event_attempts"],[event_key(f,npc)])
        self.assertIsNone(ex.next(c2,m,info))
    def test_warp_and_mismatch(self):
        f,npc,warp=self.setup();m={};c=(f,1,{(3,1)})
        ex=Explorer(MockAdapter());self.assertTrue(ex.request(c,m,([npc,warp],"DOWN"),"exit"))
        d,cmd=ex.next(c,m,([npc,warp],"DOWN"))
        changed=Field((3,4),(0,0),5,5,f.tiles)
        ex.finish(m,c,(changed,1,set()),cmd)
        self.assertEqual(m["map_transitions"][0]["to"],[3,4])
        self.assertNotIn("event_goal",m)
    def test_previously_attempted_filtered(self):
        f,npc,warp=self.setup()
        self.assertTrue(all(c[4]["kind"]=="warp" for c in options(f,{(3,1)},[npc,warp],[event_key(f,npc)])))
