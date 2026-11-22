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
    def test_native_short_tap_calibrates_then_reroutes_around_bumped_tile(self):
        from core.jj_tile_memory import blocked_tiles,failures
        f,npc,warp=self.setup()
        c=(f,0x08001235,{(3,1)})
        ex=Explorer(MockAdapter());meta={}
        info=([npc,warp],"RIGHT")
        self.assertTrue(ex.request(c,meta,info,"interact"))
        first,cmd=ex.next(c,meta,info)
        self.assertEqual(first["actions"],[{"button":"RIGHT","frames":1}])
        ex.finish(meta,c,c,cmd)
        self.assertEqual(failures(meta,f.map_id,(2,1)),1)
        self.assertIn("event_goal",meta)
        self.assertNotIn((2,1),blocked_tiles(meta,f.map_id))
        retry,cmd=ex.next(c,meta,info)
        self.assertEqual(retry["actions"],[{"button":"RIGHT","frames":12}])
        ex.finish(meta,c,c,cmd)
        self.assertIn((2,1),blocked_tiles(meta,f.map_id))
        self.assertNotIn("event_goal",meta)
        self.assertEqual(meta.get("event_attempts",[]),[])
        self.assertTrue(ex.request(c,meta,info,"interact"))
        new,cmd=ex.next(c,meta,info)
        self.assertNotEqual(new["actions"][0]["button"],"RIGHT")
        self.assertEqual(new["actions"][0]["frames"],1)

    def test_unverified_noop_cannot_learn_or_retry_a_tile(self):
        from core.jj_tile_memory import diagnostics
        class UnprovedAdapter:
            def verified_field(self,c,m):return False
        f,npc,warp=self.setup();c=(f,0x08001235,{(3,1)})
        ex=Explorer(UnprovedAdapter());meta={}
        info=([npc,warp],"RIGHT")
        self.assertTrue(ex.request(c,meta,info,"interact"))
        first,cmd=ex.next(c,meta,info)
        ex.finish(meta,c,c,cmd)
        self.assertEqual(diagnostics(meta)["maps"],0)
        self.assertNotIn("event_goal",meta)

    def test_story_npc_path_never_uses_filtered_out_warp_as_a_shortcut(self):
        # The NPC task filters the candidate list to NPCs, but the nearby
        # door remains a real tile hazard. Walking straight RIGHT would
        # trigger the warp instead of reaching the NPC's interaction tile.
        f=Field((1,2),(1,2),5,5,(0,)*25)
        c=(f,0x08001235,{(3,2)})
        npc={"kind":"npc","x":3,"y":2,"id":1,"gfx":12}
        warp={"kind":"warp","x":2,"y":2,"id":0,"destination":[3,4]}
        ex=Explorer(MockAdapter());meta={"native_party_count":0}
        info=([npc,warp],"RIGHT")
        self.assertTrue(ex.request(c,meta,info,"interact"))
        result,cmd=ex.next(c,meta,info)
        self.assertIn(result["actions"][0]["button"],("UP","DOWN"))
        self.assertNotEqual(tuple(meta["event_goal"]["target"]),(2,2))

    def test_battle_interruption_replans_without_blacklisting_story_target(self):
        f,npc,warp=self.setup()
        c=(f,0x08001235,{(3,1)})
        ex=Explorer(MockAdapter());meta={};info=([npc,warp],"RIGHT")
        self.assertTrue(ex.request(c,meta,info,"interact"))
        attempt,cmd=ex.next(c,meta,info)
        self.assertEqual(attempt["actions"][0]["button"],"RIGHT")
        ex.finish(meta,c,None,cmd,interrupted=True)
        self.assertNotIn("event_goal",meta)
        self.assertEqual(meta.get("event_attempts",[]),[])
        self.assertEqual(meta["skill_interruptions"][-1]["reason"],"battle")
        # On the same map the agent must be able to recalculate its path.
        self.assertTrue(ex.request(c,meta,info,"interact"))
        self.assertIsNotNone(ex.next(c,meta,info))
        self.assertTrue(ex.interrupt(meta,"battle"))
        self.assertFalse(ex.interrupt(meta,"battle"))
        self.assertFalse(ex.interrupt(meta,"unexpected"))
        self.assertEqual(len(meta["skill_interruptions"]),2)

    def test_previously_attempted_filtered(self):
        f,npc,warp=self.setup()
        self.assertTrue(all(c[4]["kind"]=="warp" for c in options(f,{(3,1)},[npc,warp],[event_key(f,npc)])))
