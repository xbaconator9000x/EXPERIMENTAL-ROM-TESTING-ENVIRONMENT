import unittest
from core.upstream_battle import witnessed_kind, classic_multiplier, safe_damage_kind, catch_setup_slot, EFFECT_IDS
class UpstreamBattleTests(unittest.TestCase):
    def row(self,name,fx,typ="normal"):
        return dict(name=name,effect=EFFECT_IDS[fx],type=typ,power=40,accuracy=100)
    def test_real_upstream_kinds(self):
        self.assertEqual(witnessed_kind(self.row("FALSESWIPE","FALSE_SWIPE")),"false_swipe")
        self.assertIsNone(witnessed_kind(self.row("FALSESWIPE","HIT")))
        self.assertIsNone(safe_damage_kind(self.row("EXPLOSION","EXPLOSION"),0))
        self.assertIsNone(safe_damage_kind(self.row("DREAM EATER","DREAM_EATER"),0))
        self.assertEqual(safe_damage_kind(self.row("DREAM EATER","DREAM_EATER"),2),"req_foe_asleep")
        self.assertIsNone(safe_damage_kind(self.row("FURY ATTACK","MULTI_HIT"),0,True))
    def test_classic_chart(self):
        self.assertEqual(classic_multiplier("ghost",["steel"]),.5)
        self.assertEqual(classic_multiplier("electric",["water","flying"]),4)
        self.assertIsNone(classic_multiplier("fairy",["dragon"]))
    def test_capture_setup(self):
        own={"moves":[206,95,0,0],"pp":[5,5,0,0]}
        enemy={"types":["normal"],"status":0,"hp":20}
        rows={206:self.row("False Swipe","FALSE_SWIPE"),95:self.row("Hypnosis","SLEEP","psychic")}
        self.assertEqual(catch_setup_slot(own,enemy,rows,0),0)
        self.assertEqual(catch_setup_slot(own,enemy,rows,206),1)
        self.assertIsNone(catch_setup_slot(own,{**enemy,"status":1},rows,206))
