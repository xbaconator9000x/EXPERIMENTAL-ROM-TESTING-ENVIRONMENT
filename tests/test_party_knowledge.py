import copy
import json
import unittest

from core.party_knowledge import (
    observe_party, observe_battle, knowledge_context, capture_preference,
    battle_advice, valid_party,
)


class Catalog:
    species_ids={
        7:{"name":"SQUIRTLE","types":["water"]},
        19:{"name":"RATTATA","types":["normal"]},
        25:{"name":"PIKACHU","types":["electric"]},
        43:{"name":"ODDISH","types":["grass","poison"]},
    }
    move_ids={
        33:{"name":"TACKLE","type":"normal","power":35,"accuracy":95,"effect":0},
        55:{"name":"WATERGUN","type":"water","power":40,"accuracy":100,"effect":0},
        85:{"name":"THUNDERBOLT","type":"electric","power":95,"accuracy":100,"effect":0},
        100:{"name":"MYSTERY","type":"water","power":80,"accuracy":100},
    }


def mon(slot=0,species=7,hp=24,pp=13,moves=None):
    return {"slot":slot,"species_id":species,"level":12,"hp":hp,"max_hp":30,
            "moves":moves or [33,55,0,0],"pp":[20,pp,0,0],"status":0}


def battle(party):
    return {"callback":0x0802EA11,"stage":"battle_moves","cursor":1,"wild":True,
            "own":{"species":7,"hp":24,"max_hp":30,"types":["water"],
                   "moves":[33,55,0,0],"pp":[20,13,0,0],"status":0},
            "enemy":{"species":43,"hp":15,"max_hp":30,"types":["grass","poison"],
                    "status":0},"party":party,"disabled":0}


class PartyKnowledgeTests(unittest.TestCase):
    def test_party_is_persistent_and_move_pp_is_current_not_base(self):
        meta={}
        first=[mon()]
        self.assertTrue(observe_party(meta,first,Catalog,decision=7))
        before=copy.deepcopy(meta["party_knowledge"])
        current=before["current"]
        self.assertEqual(current["members"][0]["species"]["types"],["water"])
        self.assertEqual(current["members"][0]["moves"][1]["pp"],13)
        self.assertEqual(current["members"][0]["moves"][1]["name"],"WATERGUN")
        second=[mon(hp=18,pp=8),mon(1,25,pp=5)]
        self.assertTrue(observe_party(meta,second,Catalog,decision=15))
        last=json.loads(json.dumps(meta))
        self.assertEqual(last["party_knowledge"]["current"]["members"][0]["moves"][1]["pp"],8)
        self.assertEqual(len(last["party_knowledge"]["current"]["members"]),2)
        self.assertEqual(last["party_knowledge"]["events"][-1]["species_id"],25)
        self.assertEqual(knowledge_context(last)["last_verified_decision"],15)
        self.assertEqual(knowledge_context(last)["party"][0]["last_hp"],18)

    def test_invalid_or_corrupted_candidate_never_erases_last_good_party(self):
        meta={};observe_party(meta,[mon()],Catalog,decision=5)
        good=copy.deepcopy(meta["party_knowledge"])
        bad=mon();bad["hp"]=100
        self.assertFalse(observe_party(meta,[bad],Catalog,decision=6))
        bad=mon();bad["pp"]=[99,0,0,0]
        self.assertFalse(observe_party(meta,[bad],Catalog,decision=6))
        bad=mon();bad["moves"]=[33,0,0,0];bad["pp"]=[1,10,0,0]
        self.assertFalse(observe_party(meta,[bad],Catalog,decision=6))
        self.assertFalse(observe_party(meta,[mon(),mon()],Catalog,decision=6))
        self.assertFalse(observe_party(meta,[{"species_id":7}],Catalog,decision=6))
        self.assertEqual(meta["party_knowledge"],good)

    def test_unknown_rom_move_is_not_invented(self):
        m=mon(moves=[33,500,0,0])
        meta={}
        self.assertTrue(observe_party(meta,[m],Catalog,decision=9))
        second=meta["party_knowledge"]["current"]["members"][0]["moves"][1]
        self.assertEqual(second["id"],500)
        self.assertTrue(second["unresolved_rom_move"])
        self.assertNotIn("power",second)
        self.assertNotIn("name",second)

    def test_inventory_is_newly_verified_or_marked_stale(self):
        meta={}
        bag={"balls":[{"id":4,"count":6}],"items":[{"id":13,"count":3}]}
        self.assertTrue(observe_party(meta,[mon()],Catalog,decision=3,bag=bag))
        self.assertEqual(meta["party_knowledge"]["current"]["bag"]["balls"][0]["count"],6)
        self.assertTrue(observe_party(meta,[mon()],Catalog,decision=4,bag=None))
        self.assertNotIn("bag",meta["party_knowledge"]["current"])
        self.assertEqual(meta["party_knowledge"]["current"]["last_known_bag"],bag)
        self.assertTrue(observe_party(meta,[mon()],Catalog,decision=5,
                                      bag={"balls":[{"id":4,"count":5}],"items":[]}))
        self.assertEqual(meta["party_knowledge"]["current"]["bag"]["balls"][0]["count"],5)

    def test_corroborated_battle_summary_is_state_locked(self):
        team=[mon()]
        state=battle(team)
        meta={}
        self.assertFalse(observe_battle(meta,state,Catalog,decision=3))
        meta["battle_proof"]=[0x0802EA11]
        self.assertTrue(observe_battle(meta,state,Catalog,decision=3))
        saved=copy.deepcopy(meta["battle_knowledge"])
        move=saved["current"]["moves"][1]
        self.assertEqual(move["effectiveness"],.5)  # Water -> Grass/Poison
        self.assertEqual(move["pp"],13)
        self.assertTrue(move["safe_effect_verified"])
        self.assertEqual(saved["current"]["incoming_type_matchups"]["electric"],2.0)
        new=copy.deepcopy(state);new["own"]["pp"][1]=11
        self.assertTrue(observe_battle(meta,new,Catalog,decision=4))
        self.assertNotEqual(saved["signature"],meta["battle_knowledge"]["signature"])
        self.assertEqual(meta["battle_knowledge"]["current"]["moves"][1]["pp"],11)
        meta["battle_proof"]=[]
        self.assertFalse(observe_battle(meta,new,Catalog,decision=5))
        self.assertEqual(meta["battle_knowledge"]["decision"],4)

    def test_capture_roster_diversity_and_resource_reserve(self):
        enemy={"species":43}
        balls={"balls":[{"id":4,"count":5}],"items":[]}
        first=[mon()]
        self.assertEqual(capture_preference(first,enemy,Catalog,balls)["reason"],"build_initial_team")
        self.assertFalse(capture_preference(first,enemy,Catalog,balls,wild=False)["eligible"])
        self.assertFalse(capture_preference(first,{"species":7},Catalog,balls)["eligible"])
        trio=[mon(),mon(1,19),mon(2,25)]
        p=capture_preference(trio,enemy,Catalog,balls)
        self.assertEqual(p["reason"],"new_type_coverage")
        self.assertEqual(p["new_types"],["grass","poison"])
        same=capture_preference(trio,{"species":19},Catalog,balls)
        self.assertFalse(same["eligible"])
        self.assertFalse(capture_preference(trio,enemy,Catalog,
            {"balls":[{"id":4,"count":1}],"items":[]})["eligible"])
        full=trio+[mon(i,19) for i in range(3,6)]
        self.assertEqual(capture_preference(full,enemy,Catalog,balls)["reason"],"full_party")
        self.assertEqual(capture_preference(trio,{"species":400},Catalog,balls)["reason"],
                         "unknown_type_coverage")

    def test_unknown_move_effect_is_not_promoted_to_safe_macro(self):
        state=battle([mon()])
        state["own"]["moves"]=[100,0,0,0]
        state["own"]["pp"]=[8,0,0,0]
        advice=battle_advice(state,Catalog)
        self.assertFalse(advice["moves"][0]["safe_effect_verified"])
        # Historic knowledge never authorizes a move even if no live callback.
        meta={};observe_party(meta,[mon()],Catalog,decision=2)
        self.assertFalse(observe_battle(meta,state,Catalog,decision=3))
        self.assertNotIn("battle_knowledge",meta)


if __name__=="__main__":
    unittest.main()
