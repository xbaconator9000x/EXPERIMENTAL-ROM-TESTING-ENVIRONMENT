import json
import unittest
import tempfile
from pathlib import Path
from core.guidance import PREFIX, parse_guide, newest_guide, claim_guide
from core.gameplay import clean_observation, item_policy
from core.autoplay import OllamaVision

class RedundancyTests(unittest.TestCase):
    def test_state_locked_guide(self):
        h="a"*64
        v={"decision":4,"screen":h,"scene":"menu","objective":"select option","actions":[{"button":"A","frames":5}]}
        body=PREFIX+json.dumps(v)
        self.assertIsNotNone(parse_guide(body,4,h))
        self.assertIsNone(parse_guide(body,5,h))
        self.assertIsNone(parse_guide(body,4,"b"*64))
        self.assertIsNone(parse_guide(PREFIX+json.dumps({**v,"actions":[{"button":"execute","frames":5}]}),4,h))
        c={"body":body,"user":{"login":"owner"},"author_association":"OWNER"}
        self.assertIsNone(newest_guide([c],"other",4,h))
        self.assertIsNotNone(newest_guide([c],"owner",4,h))
    def test_backup_model(self):
        m=OllamaVision()
        calls=[]
        def try_model(rgb,goal,history,blocked,memory,model,rich):
            calls.append((model,rich))
            if model==m.model:raise ValueError("invalid")
            return {"scene":"field","objective":"move","actions":[{"button":"A","frames":5}],"review":False}
        m._decide=try_model
        self.assertEqual(m.decide(b"","goal",[],[],{})["scene"],"field")
        self.assertEqual(m.last_source,"vision_backup")
        self.assertEqual(len(calls),3)
    def test_bag_selection(self):
        o=clean_observation({"stage":"bag","list_cursor":0,"bag_purpose":"catch","wild":True,"capture_target":True,"items":[{"slot":0,"name":"Potion","count":1},{"slot":1,"name":"Great Ball","count":3},{"slot":2,"name":"Master Ball","count":1}]})
        self.assertEqual(item_policy(o)[0],[{"button":"DOWN","frames":5}])
        self.assertEqual(item_policy({**o,"list_cursor":1})[0],[{"button":"A","frames":5}])
        self.assertIsNone(item_policy({**o,"wild":False}))

    def test_guide_consumption_is_persistent(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"guides.json";h="a"*64
            v={"scene":"field","objective":"walk","actions":[{"button":"LEFT","frames":16}],"review":False}
            self.assertTrue(claim_guide(p,4,h,v))
            self.assertFalse(p.exists())
            self.assertTrue(claim_guide(p,4,h,v,True))
            self.assertFalse(claim_guide(p,4,h,v))
            self.assertTrue(claim_guide(p,5,h,v))
