import json
import unittest
from core.firered import Field
from core.jj_world_model import map_key, observe, task, rank, summary, complete
from core.jj_explore import Explorer,options


def candidate(map_id=(1,2),pos=(2,2)):
    return (Field(map_id,pos,6,6,(0,)*36),0x08001235,set())


def event(kind,x,y,id,destination=None):
    v={"kind":kind,"x":x,"y":y,"id":id}
    if destination:v["destination"]=destination
    if kind=="connection":v["direction"]="RIGHT"
    return v


class Adapter:
    def verified_field(self,c,m):return c is not None


class WorldModelTests(unittest.TestCase):
    def test_no_unverified_map_records_or_fake_edges(self):
        c=candidate();meta={}
        self.assertFalse(observe(meta,c,[],verified=False,decision=1))
        self.assertNotIn("world_model",meta)
        self.assertTrue(observe(meta,c,[event("warp",4,4,0,[3,4])],verified=True,decision=1))
        self.assertEqual(summary(meta)["confirmed_maps"],1)
        self.assertEqual(summary(meta)["verified_edges"],0)
        self.assertEqual(meta["world_model"]["maps"]["1:2"]["event_kinds"],{"warp":1})
        # A known destination is a candidate, never proof of crossing.
        self.assertEqual(meta["world_model"]["edges"],[])
        # Only separately observed native transitions can be copied in.
        meta["observed_field_transitions"]=[{"from":[1,2],"to":[3,4],"arrival":[0,0]}]
        self.assertTrue(observe(meta,candidate((3,4)),None,verified=True,decision=8))
        self.assertEqual(summary(meta)["verified_edges"],1)
        self.assertEqual(meta["world_model"]["edges"],[{"from":"1:2","to":"3:4"}])
        self.assertEqual(json.loads(json.dumps(meta))["world_model"],meta["world_model"])

    def test_goal_first_party_then_new_exits_then_health_review(self):
        npc=event("npc",1,1,1)
        warp=event("warp",4,4,0,[3,4])
        self.assertEqual(task({},[],[npc,warp]),"interact")
        healthy=[{"hp":20,"max_hp":30}]
        self.assertEqual(task({},healthy,[npc,warp]),"explore")
        self.assertEqual(task({},healthy,[npc]),"explore")
        self.assertIsNone(task({},[{"hp":2,"max_hp":30}], [npc,warp]))
        self.assertIsNone(task({},[{"hp":0,"max_hp":30}], [npc,warp]))
        self.assertEqual(task({},None,[npc,warp]),"explore")

    def test_existing_native_explorer_prioritizes_new_route_without_new_controller(self):
        f=candidate()[0]
        npc=event("npc",1,1,1)
        new=event("warp",4,4,2,[5,6])
        visited=event("warp",3,4,3,[3,4])
        meta={"native_party_count":2}
        world=meta["world_model"]={"version":1,
            "maps":{"1:2":{"map":[1,2]},"3:4":{"map":[3,4]}},
            "edges":[{"from":"1:2","to":"3:4"}],
            "recent":[{"map":"3:4","pos":[1,1],"decision":4}]}
        info=([npc,visited,new],"RIGHT")
        explorer=Explorer(Adapter())
        self.assertTrue(explorer.request(candidate(),meta,info,"exit"))
        self.assertEqual(meta["event_goal"]["event"]["id"],2)
        self.assertEqual(meta["event_goal"]["event"]["destination"],[5,6])
        # A previous verified map visit must not ban story-dependent returns.
        meta["event_attempts"]=[meta["event_goal"]["key"]]
        self.assertTrue(explorer.request(candidate(),meta,info,"exit"))
        self.assertEqual(meta["event_goal"]["event"]["id"],3)
        # In mixed exploration mode, revisit a story NPC after the known
        # exits have already been explored; do not keep recrossing the same map.
        meta["event_attempts"]=[]
        self.assertTrue(explorer.request(candidate(),meta,info,"explore"))
        self.assertEqual(meta["event_goal"]["event"]["kind"],"npc")

    def test_one_task_only_and_never_execute_an_unverified_action(self):
        c=candidate();npc=event("npc",4,2,4)
        m={}
        self.assertIsNone(rank(m,[],0,current_map=(1,2),task_name="exit"))
        self.assertIsNone(rank(m,options(c[0],c[2],[npc],[]),0,
                               current_map=(1,2),task_name="invalid"))
        self.assertIsNone(explorer_action_without_field(c,m))
        self.assertFalse(complete(m,task_name="exit",observed=False))
        self.assertFalse(complete(m,task_name="exit",observed=True))
        self.assertFalse(complete(m,task_name="interact",observed=True))
        m["observed_field_transitions"]=[{"from":[1,2],"to":[3,4],"arrival":[0,0]}]
        self.assertTrue(complete(m,task_name="exit",observed=True))
        self.assertFalse(complete(m,task_name="exit",observed=True))
        self.assertEqual(m["world_model"]["skill_outcomes"],
            [{"task":"exit","result":"native_verified","from":"1:2","to":"3:4"}])

    def test_bounded_maps_positions_events(self):
        meta={}
        for i in range(180):
            c=candidate((i//100,i%100))
            self.assertTrue(observe(meta,c,[event("npc",1,1,i)],verified=True,decision=i))
        w=meta["world_model"]
        self.assertLessEqual(len(w["maps"]),160)
        self.assertLessEqual(len(w["recent"]),48)
        self.assertFalse(observe(meta,candidate(),[],verified=True,decision=-1))
        self.assertIsNone(map_key([256,1]))


def explorer_action_without_field(c,meta):
    ex=Explorer(Adapter())
    return ex.next(None,meta,([event("npc",4,2,4)],"RIGHT"))


if __name__=="__main__":
    unittest.main()
