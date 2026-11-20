import json
import unittest
from core.gameplay import effectiveness, clean_observation, best_move, battle_policy, route_step, remember, policy
from core.autoplay import parse_decision, title_recovery

def move(slot,name,t,power,pp=10):
    return {"slot":slot,"name":name,"type":t,"power":power,"pp":pp,"accuracy":100}

class GameplayTests(unittest.TestCase):
    def test_type_rules_and_classic_steel(self):
        self.assertEqual(effectiveness("water",["rock","ground"]),4)
        self.assertEqual(effectiveness("electric",["ground","flying"]),0)
        self.assertEqual(effectiveness("ghost",["steel"]),.5)
        self.assertEqual(effectiveness("ghost",["steel"],True),1)
        self.assertIsNone(effectiveness("fairy",["dragon"]))
        self.assertEqual(effectiveness("fairy",["dragon"],True),2)
    def test_battle_move_selection(self):
        obs=clean_observation({"stage":"battle_moves","cursor":0,"enemy_types":["rock","ground"],"own_types":["water"],"moves":[move(0,"Tackle","normal",40),move(1,"Water Gun","water",40),move(2,"Thunder","electric",110),move(3,"Surf","water",95,0)]})
        self.assertEqual(best_move(obs)["name"],"Water Gun")
        self.assertEqual(battle_policy(obs)[0],[{"button":"RIGHT","frames":5}])
        self.assertEqual(battle_policy({**obs,"cursor":1})[0],[{"button":"A","frames":5}])
    def test_catching_and_healing(self):
        o={"stage":"battle_command","cursor":0,"wild":True,"capture_target":True,"balls":3,"enemy_hp":20,"hp":70}
        self.assertEqual(battle_policy(o)[0],[{"button":"RIGHT","frames":5}])
        self.assertIsNone(battle_policy({**o,"wild":False}))
        self.assertEqual(battle_policy({**o,"wild":False,"hp":12,"healing_items":1})[0],[{"button":"RIGHT","frames":5}])
        m={**o,"stage":"battle_moves","enemy_hp":75,"enemy_types":["grass"],"moves":[move(0,"Ember","fire",40),move(1,"Tackle","normal",40)]}
        self.assertEqual(best_move(m)["name"],"Tackle")
    def test_bounded_route_and_memory(self):
        grid=[".....##########"]*10
        o=clean_observation({"stage":"field","grid":grid,"start":[0,0],"destination":[2,0],"target":"door","fact":"Jessie says meet at the balloon","location":"house"})
        self.assertEqual(route_step(o)[0],[{"button":"RIGHT","frames":16}])
        self.assertEqual(route_step(o,["RIGHT"])[0],[{"button":"DOWN","frames":16}])
        m=remember({},o,{"objective":"Find balloon"},"abc",1)
        m=remember(m,o,{"objective":"Find balloon"},"def",2)
        self.assertEqual(len(m["facts"]),1)
        self.assertEqual(m["last_screen"],"def")
    def test_invalid_observation_fallback_and_no_stale_title(self):
        d={"scene":"field","objective":"walk","actions":[{"button":"A","frames":5}],"review":False,"observation":{"stage":"field","grid":["bad"],"cursor":True}}
        self.assertEqual(parse_decision(json.dumps(d))["observation"],{"stage":"field"})
        h=[{"scene":"title_screen","actions":[{"button":"A"}]}]*2
        self.assertIsNone(title_recovery({"history":h,"frames":582},bytes([240,240,254])*38400))
    def test_policy_does_not_override_review_or_unknown(self):
        self.assertIsNone(policy({"stage":"other"},"classic",[],"x"))
