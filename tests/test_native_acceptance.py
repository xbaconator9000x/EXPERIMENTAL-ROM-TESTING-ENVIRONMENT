import unittest
from types import SimpleNamespace
from core.native_acceptance import Acceptance
from core.gen3_profiles import FIRERED
def mon(species=19,hp=20):
    return {"slot":0,"species_id":species,"level":5,"hp":hp,"max_hp":30}
class AcceptanceTest(unittest.TestCase):
    def get(self,meta=None):
        return Acceptance({} if meta is None else meta,"a"*64,"b"*64,FIRERED,SimpleNamespace(),SimpleNamespace())
    def test_reject_stale_outcome(self):
        a=self.get();a.observe({"party":[mon()],"outcome":7},{"party":[mon(),mon(25)],"outcome":7},"vision",1,"a","b",[])
        self.assertEqual(a.ledger["counts"]["wild_capture"],0)
    def test_capture_needs_actual_party_growth(self):
        a=self.get();before={"battle":{"enemy":25,"wild":True,"own":19,"moves":[33],"pp":[10]},"party":[mon()],"outcome":0}
        a.observe(before,{"party":[mon()],"outcome":7},"native_menu",1,"a","b",[])
        self.assertEqual(a.ledger["counts"]["wild_capture"],0)
        a.observe({"outcome":7,"party":[mon()]},{"outcome":7,"party":[mon(),{**mon(25),"slot":1}],"field":{"map":[1,1],"pos":[2,2]}},"vision",2,"b","c",[])
        self.assertEqual(a.ledger["counts"]["wild_capture"],1)
        a.observe({"outcome":7},{"outcome":7,"party":[mon(),mon(25)]},"vision",3,"c","d",[])
        self.assertEqual(a.ledger["counts"]["wild_capture"],1)
    def test_trainer_win_not_capture(self):
        a=self.get();before={"battle":{"enemy":25,"wild":False,"own":19,"moves":[33],"pp":[10]},"party":[mon()],"outcome":0}
        a.observe(before,{"outcome":1,"party":[mon()]},"native_battle",1,"a","b",[])
        self.assertEqual(a.ledger["counts"]["battle_win"],1)
        self.assertEqual(a.ledger["counts"]["wild_capture"],0)
        self.assertEqual(a.ledger["status"],"INCOMPLETE")
    def test_native_walk_and_reload(self):
        a=self.get()
        a.observe({"outcome":0,"field":{"map":[1,1],"pos":[1,1]}},{"outcome":0,"field":{"map":[1,1],"pos":[2,1]}},"native_route",1,"a","b",[])
        self.assertEqual(a.ledger["counts"]["native_step"],1)
        a.reload(1,b"a",b"b");self.assertEqual(a.ledger["counts"]["checkpoint_reload"],0)
        a.reload(1,b"a",b"a");self.assertEqual(a.ledger["counts"]["checkpoint_reload"],1)
        a.reload(1,b"a",b"a")
        self.assertEqual(a.ledger["counts"]["checkpoint_reload"],2)
        self.assertEqual([e["detail"]["ordinal"] for e in a.ledger["events"]
                          if e["kind"]=="checkpoint_reload"],[1,2])
        a.reload(1,b"a",b"b")
        self.assertEqual(a.ledger["counts"]["checkpoint_reload"],2)
