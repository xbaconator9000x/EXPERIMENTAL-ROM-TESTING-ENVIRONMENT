import unittest
from core.jj_runtime import animation_wait,record_field,count_decision,recovery_allowed
from core.jj_fast import MAIN
from core.jj_battle import BATTLE_CB,FLAGS
from core.firered import Field

class Live:
    def integer(self,a,n):return {MAIN+4:BATTLE_CB,FLAGS:12}[a]
class Battles:
    callbacks={BATTLE_CB}
class RuntimeTests(unittest.TestCase):
    def test_bounded_animation_wait(self):
        m={"battle_proof":[123],"history":[{"source":"native_battle","actions":[{"button":"A","frames":5}]}]}
        self.assertEqual(animation_wait(Live(),Battles(),None,m)["actions"][0]["button"],"WAIT")
        self.assertIsNone(animation_wait(Live(),Battles(),{"stage":"battle_command"},m))
        m["history"]+=[{"source":"native_battle_wait"}]*2
        self.assertIsNone(animation_wait(Live(),Battles(),None,m))
    def test_metrics_count_actual_model_work(self):
        m={};count_decision(m,"native_route",.2,None,17);count_decision(m,"native_battle",8,7,125)
        self.assertEqual(m["engine_metrics"]["native"],2)
        self.assertEqual(m["engine_metrics"]["model_calls"],1)
        self.assertEqual(m["engine_metrics"]["frames"],142)
        count_decision(m,"batch_navigation",.12,None,40)
        self.assertEqual(m["engine_metrics"]["native"],3)
        self.assertEqual(m["engine_metrics"]["model_calls"],1)
    def test_map_transition_and_stall(self):
        m={};a=(Field((1,1),(1,1),4,4,(0,)*16),123,set())
        b=(Field((2,1),(1,2),4,4,(0,)*16),123,set())
        record_field(m,a,True);record_field(m,None,False);record_field(m,b,True)
        self.assertEqual(m["observed_field_transitions"],[{"from":[1,1],"to":[2,1],"arrival":[1,2]}])
        m["history"]=[{"source":"vision_compact","field_after":{"map":[2,1],"pos":[1,2]}}]*5
        self.assertTrue(recovery_allowed(b,m,True))
        self.assertFalse(recovery_allowed(b,m,False))
