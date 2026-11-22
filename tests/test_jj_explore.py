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
    def test_native_scout_surveys_verified_floor_without_warp_or_npc_collision(self):
        from core.firered import Field
        field=Field((43,1),(2,2),5,5,(0,)*25)
        before=(field,0x08001235,{(1,2)})
        class A:
            def verified_field(self,c,m):return c is not None
        explorer=Explorer(A())
        meta={}
        info=([{"kind":"warp","x":2,"y":1,"id":0},
               {"kind":"coord","x":2,"y":3,"id":1},
               {"kind":"npc","x":1,"y":2,"id":2}],None)
        decision,command=explorer.scout(before,meta,info)
        self.assertEqual(decision["actions"][0]["button"],"RIGHT")
        self.assertEqual(command,("move",(3,2)))
        self.assertEqual(meta["native_scout"]["maps"]["43:1"]["visited"],[[2,2]])
        after=(Field((43,1),(3,2),5,5,(0,)*25),0x08001235,{(1,2)})
        self.assertEqual(explorer.finish_scout(meta,before,after,command),"moved")
        self.assertEqual(meta["native_scout"]["maps"]["43:1"]["visited"],[[2,2],[3,2]])
        self.assertIsNone(explorer.scout(before,meta,None))
        self.assertIsNone(explorer.scout(None,meta,info))

    def test_native_reconsider_exhausts_24_actual_rom_event_approaches(self):
        from core.jj_explore import NATIVE_RETRY_APPROACHES
        from core.firered import Field
        f=Field((43,1),(2,2),8,8,(0,)*64)
        warp={"kind":"warp","x":4,"y":2,"id":0,"destination":[43,2]}
        coord={"kind":"coord","x":3,"y":4,"id":0}
        ex=Explorer(MockAdapter())
        meta={"native_party_count":3,"event_attempts":[event_key(f,warp),event_key(f,coord)]}
        candidate=(f,0x08001235,set())
        for i in range(NATIVE_RETRY_APPROACHES):
            self.assertTrue(ex.reconsider(candidate,meta,([warp,coord],None)),i)
            self.assertIn("event_goal",meta)
            meta.pop("event_goal")
        self.assertEqual(meta["native_revisit"]["approaches"],24)
        self.assertFalse(ex.reconsider(candidate,meta,([warp,coord],None)))
        self.assertEqual(meta["event_attempts"],[event_key(f,warp),event_key(f,coord)])
        ex.restart_reconsider(meta)
        self.assertEqual(meta["native_revisit"]["sweeps"],1)
        self.assertTrue(ex.reconsider(candidate,meta,([warp,coord],None)))

    def test_checkpoint_shaped_43_1_still_has_reachable_warp_after_attempts(self):
        # The reported bedroom checkpoint has this native event layout.
        # The grid here is deliberately synthetic: it tests the planner's
        # prioritization, NOT real ROM collision data or map completion.
        f=Field((43,1),(9,8),16,13,(0,)*(16*13))
        warp={"kind":"warp","x":4,"y":2,"id":0,"destination":[43,2]}
        coords=[{"kind":"coord","x":4,"y":2,"id":0},
                {"kind":"coord","x":9,"y":6,"id":1},
                {"kind":"coord","x":11,"y":6,"id":2}]
        events=[warp,*coords]
        attempted=[event_key(f,e) for e in events]
        meta={"native_party_count":3,"event_attempts":attempted}
        c=(f,0x08001235,set());ex=Explorer(MockAdapter())
        self.assertEqual(options(f,set(),events,attempted,avoid_warps=events),[])
        self.assertTrue(ex.reconsider(c,meta,(events,None)))
        goal=meta["event_goal"]
        self.assertEqual(goal["event"],warp)
        action,command=ex.next(c,meta,(events,None))
        self.assertEqual(action["scene"],"native_exploration")
        self.assertEqual(command[0],"move")
        self.assertNotIn(command[1],{(4,2),(9,6),(11,6)})
        self.assertEqual(meta["event_attempts"],attempted)

    def test_normal_warp_request_reenters_without_first_exhausting_scout(self):
        f=Field((43,1),(4,2),8,8,(0,)*64)
        warp={"kind":"warp","x":4,"y":2,"id":0,"destination":[43,2]}
        coord={"kind":"coord","x":4,"y":2,"id":1}
        before=(f,0x08001235,set())
        ex=Explorer(MockAdapter());meta={"native_party_count":3}
        info=([warp,coord],None)
        self.assertTrue(ex.request(before,meta,info,"exit"))
        self.assertEqual(meta["event_goal"]["event"],warp)
        self.assertTrue(meta["event_goal"]["retry"])
        off,command=ex.next(before,meta,info)
        self.assertEqual(off["scene"],"native_event_reentry")
        self.assertEqual(command,("move",(4,1)))
        away=(Field(f.map_id,(4,1),8,8,f.tiles),0x08001235,set())
        ex.finish(meta,before,away,command)
        self.assertIn("event_goal",meta)
        go,command=ex.next(away,meta,info)
        self.assertEqual(go["actions"],[{"button":"DOWN","frames":1}])
        self.assertEqual(command,("move",(4,2)))
        ex.finish(meta,away,before,command)
        self.assertEqual(meta["native_event_witnesses"][-1]["result"],"trigger_tile_entered")
        self.assertIsNone(ex.next(before,meta,info))
        self.assertIn(event_key(f,warp),meta["event_attempts"])

    def test_event_witness_distinguishes_unverified_entry_from_map_transition(self):
        f=Field((43,1),(4,3),8,8,(0,)*64)
        warp={"kind":"warp","x":4,"y":2,"id":0,"destination":[43,2]}
        c=(f,0x08001235,set());ex=Explorer(MockAdapter());meta={}
        info=([warp],None)
        self.assertTrue(ex.request(c,meta,info,"exit"))
        result,cmd=ex.next(c,meta,info)
        ex.finish(meta,c,None,cmd)
        self.assertEqual(meta["native_event_witnesses"][-1]["result"],
                         "unverified_after_input")
        meta={}
        self.assertTrue(ex.request(c,meta,info,"exit"))
        changed=(Field((43,2),(3,4),8,8,(0,)*64),0x08001235,set())
        ex.finish(meta,c,changed,cmd)
        self.assertEqual(meta["native_event_witnesses"][-1]["result"],
                         "map_transition")

    def test_retry_warp_standing_on_trigger_steps_off_and_reenters(self):
        from core.firered import Field
        f=Field((43,1),(4,2),8,8,(0,)*64)
        warp={"kind":"warp","x":4,"y":2,"id":0,"destination":[43,2]}
        candidate=(f,0x08001235,set())
        ex=Explorer(MockAdapter());meta={"native_party_count":3}
        info=([warp],None)
        self.assertTrue(ex.reconsider(candidate,meta,info))
        away,move=ex.next(candidate,meta,info)
        self.assertEqual(away["scene"],"native_event_reentry")
        self.assertEqual(move[0],"move")
        self.assertNotEqual(move[1],(4,2))
        after=(Field((43,1),move[1],8,8,(0,)*64),0x08001235,set())
        ex.finish(meta,candidate,after,move)
        self.assertIn("event_goal",meta)
        toward,command=ex.next(after,meta,info)
        self.assertEqual(command,("move",(4,2)))
        self.assertEqual(toward["actions"][0]["button"],"DOWN")
        ex.finish(meta,after,candidate,command)
        self.assertTrue(meta["event_goal"]["reentered"])
        self.assertIsNone(ex.next(candidate,meta,info))
        self.assertNotIn("event_goal",meta)

    def test_coordinate_event_shared_with_warp_is_a_valid_native_target(self):
        from core.firered import Field
        f=Field((43,1),(4,3),8,8,(0,)*64)
        warp={"kind":"warp","x":4,"y":2,"id":0,"destination":[43,2]}
        coord={"kind":"coord","x":4,"y":2,"id":0}
        c=(f,0x08001235,set())
        ex=Explorer(MockAdapter())
        choices=options(f,set(),[coord],[],avoid_warps=[coord,warp])
        self.assertTrue(choices)
        self.assertEqual(choices[0][-1],["Up"])
        meta={"native_party_count":3}
        self.assertTrue(ex.reconsider(c,meta,([warp,coord],None)))
        self.assertEqual(ex.next(c,meta,([warp,coord],None))[0]["actions"][0]["button"],"UP")

    def test_guarded_visual_is_single_step_and_native_collision_checked(self):
        from core.firered import Field
        ex=Explorer(MockAdapter())
        f=Field((43,1),(2,2),6,6,(0,)*36)
        c=(f,0x08001235,{(1,2)})
        info=([{"kind":"warp","x":2,"y":1,"id":0},
               {"kind":"npc","x":3,"y":2,"id":1}],None)
        meta={}
        proposal=lambda button,frames=16:{"review":False,
            "actions":[{"button":button,"frames":frames}]}
        self.assertIsNone(ex.guarded_visual(c,meta,info,proposal("UP")))
        self.assertIsNone(ex.guarded_visual(c,meta,info,proposal("LEFT")))
        self.assertIsNone(ex.guarded_visual(c,meta,info,
            {"review":False,"actions":[{"button":"DOWN","frames":16},
                                      {"button":"DOWN","frames":16}]}))
        decision=ex.guarded_visual(c,meta,info,proposal("DOWN",120))
        self.assertEqual(decision["actions"],[{"button":"DOWN","frames":16}])
        self.assertEqual(decision["scene"],"native_guarded_visual")
        self.assertIsNone(ex.guarded_visual(c,meta,([],None),proposal("A")))
        # Without native facing, A is unsafe despite an adjacent NPC.
        self.assertIsNone(ex.guarded_visual(c,meta,info,proposal("A")))
        self.assertIsNone(ex.guarded_visual(c,meta,(info[0],"UP"),proposal("A")))
        self.assertEqual(ex.guarded_visual(c,meta,(info[0],"RIGHT"),proposal("A"))["actions"],
                         [{"button":"A","frames":5}])

    def test_native_event_probe_distinguishes_unverified_rejected_and_readable(self):
        from unittest.mock import patch
        f,npc,warp=self.setup()
        candidate=(f,0x08001235,{(3,1)})
        adapter=MockAdapter()
        adapter.live=object()
        adapter.size=16*1024*1024
        ex=Explorer(adapter);meta={}
        self.assertIsNone(ex.inspect(None,meta))
        self.assertEqual(meta["native_event_probe"]["status"],"FIELD_NOT_VERIFIED")
        with patch("core.jj_explore.event_targets",return_value=([npc,warp],"RIGHT")):
            result=ex.inspect(candidate,meta)
        self.assertEqual(result[0],[npc,warp])
        probe=meta["native_event_probe"]
        self.assertEqual(probe["status"],"EVENTS_READ")
        self.assertEqual(probe["counts"],{"npc":1,"warp":1,"bg":0,"coord":0,"connection":0})
        self.assertEqual(probe["reachable"],2)
        self.assertEqual(probe["attempted"],0)
        self.assertEqual(probe["event_positions"],[{"kind":"npc","x":3,"y":1},{"kind":"warp","x":4,"y":4}])
        with patch("core.jj_explore.event_targets",side_effect=ValueError("invalid event pointer")):
            self.assertIsNone(ex.inspect(candidate,meta))
        self.assertEqual(meta["native_event_probe"]["status"],"EVENTS_REJECTED")

    def test_background_event_is_native_interaction_target(self):
        f,npc,warp=self.setup()
        ball={"kind":"bg","x":2,"y":1,"id":0,"bg_kind":1}
        candidate=(f,0x08001235,{(3,1)})
        ex=Explorer(MockAdapter())
        meta={"native_party_count":0}
        info=([warp,npc,ball],"RIGHT")
        self.assertTrue(ex.request(candidate,meta,info,"interact"))
        self.assertEqual(meta["event_goal"]["event"],ball)
        # Player (1,1) already stands directly left of the scripted ball.
        choice,command=ex.next(candidate,meta,info)
        self.assertEqual(choice["actions"],[{"button":"A","frames":5}])
        self.assertEqual(command[0],"interact")
        ex.finish(meta,candidate,None,command)
        self.assertIn(event_key(f,ball),meta["event_attempts"])

    def test_background_event_reader_uses_checked_rom_pointers(self):
        from core.jj_explore import event_targets
        from unittest.mock import patch
        import struct
        f=Field((1,2),(1,1),5,5,(0,)*25)
        base=0x08000000
        header=base+0x20
        events=base+0x100
        bg=base+0x200
        buffer=bytearray(0x300)
        struct.pack_into("<I",buffer,0x24,events)
        buffer[0x103]=1  # one background event, zero NPCs/warps
        struct.pack_into("<I",buffer,0x110,bg)
        struct.pack_into("<hhBBHI",buffer,0x200,2,1,0,1,0,base+0x280)
        class Live:
            def integer(self,addr,n):return int.from_bytes(self.read(addr,n),"little")
            def read(self,addr,n):
                if addr==0x02000000:return bytes(576)
                if addr>=base and addr+n<=base+len(buffer):
                    return bytes(buffer[addr-base:addr-base+n])
                raise ValueError("out of range")
        live=Live()
        with patch("core.jj_explore.crossings",return_value=[]):
            result,facing=event_targets(live,len(buffer),f,header,0x02000000)
        self.assertEqual(result,[{"kind":"bg","x":2,"y":1,"id":0,"bg_kind":1}])
        buffer[0x103]=65
        with self.assertRaises(ValueError):
            event_targets(live,len(buffer),f,header,0x02000000)

    def test_coordinate_trigger_is_walk_on_not_press_a(self):
        f=Field((1,2),(1,1),5,5,(0,)*25)
        coord={"kind":"coord","x":2,"y":1,"id":0,"trigger":1,"index":2}
        c=(f,0x08001235,set())
        ex=Explorer(MockAdapter());meta={"native_party_count":1}
        info=([coord],"RIGHT")
        self.assertFalse(ex.request(c,meta,info,"interact"))
        self.assertTrue(ex.request(c,meta,info,"explore"))
        choice,command=ex.next(c,meta,info)
        self.assertEqual(choice["actions"],[{"button":"RIGHT","frames":1}])
        self.assertEqual(command[0],"move")
        at=Field(f.map_id,(2,1),5,5,f.tiles)
        ex.finish(meta,c,(at,c[1],set()),command)
        self.assertIsNone(ex.next((at,c[1],set()),meta,info))

    def test_coordinate_event_reader_uses_16_byte_entries_and_validates_bounds(self):
        from core.jj_explore import event_targets
        from unittest.mock import patch
        import struct
        f=Field((1,2),(1,1),5,5,(0,)*25)
        base=0x08000000
        header=base+0x20
        events=base+0x100
        coords=base+0x240
        buffer=bytearray(0x300)
        struct.pack_into("<I",buffer,0x24,events)
        buffer[0x102]=1
        struct.pack_into("<I",buffer,0x10c,coords)
        struct.pack_into("<hhBBHH2xI",buffer,0x240,2,1,0,0,3,4,base+0x280)
        class Live:
            def integer(self,addr,n):return int.from_bytes(self.read(addr,n),"little")
            def read(self,addr,n):
                if addr==0x02000000:return bytes(576)
                if addr>=base and addr+n<=base+len(buffer):
                    return bytes(buffer[addr-base:addr-base+n])
                raise ValueError("out of range")
        live=Live()
        with patch("core.jj_explore.crossings",return_value=[]):
            result,_=event_targets(live,len(buffer),f,header,0x02000000)
        self.assertEqual(result,[{"kind":"coord","x":2,"y":1,"id":0,"trigger":3,"index":4}])
        buffer[0x102]=65
        with self.assertRaises(ValueError):
            event_targets(live,len(buffer),f,header,0x02000000)

    def test_starter_event_retry_is_bounded_without_erasing_checkpoint_attempts(self):
        f,npc,warp=self.setup()
        candidate=(f,0x08001235,{(3,1)})
        key=event_key(f,npc)
        meta={"objective_state":{"phase":"obtain_initial_party"},
              "native_party_count":0,"event_attempts":[key]}
        ex=Explorer(MockAdapter())
        info=([npc,warp],"RIGHT")
        self.assertTrue(ex.request(candidate,meta,info,"interact"))
        self.assertEqual(meta["event_goal"]["event"],npc)
        self.assertEqual(meta["event_attempts"],[key])
        self.assertEqual(meta["starter_event_retry"],[1,2])
        meta.pop("event_goal")
        self.assertFalse(ex.request(candidate,meta,info,"interact"))

    def test_missing_facing_byte_finishes_one_turn_before_a(self):
        f,npc,warp=self.setup()
        f=Field(f.map_id,(2,1),f.width,f.height,f.tiles)
        candidate=(f,0x08001235,{(3,1)})
        ex=Explorer(MockAdapter());meta={"native_party_count":0}
        info=([npc,warp],None)
        self.assertTrue(ex.request(candidate,meta,info,"interact"))
        first,cmd=ex.next(candidate,meta,info)
        self.assertEqual(first["actions"],[{"button":"RIGHT","frames":1}])
        self.assertEqual(cmd[0],"face")
        ex.finish(meta,candidate,candidate,cmd)
        second,cmd=ex.next(candidate,meta,info)
        self.assertEqual(second["actions"],[{"button":"A","frames":5}])
        self.assertEqual(cmd[0],"interact")

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
