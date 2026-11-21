"""Regression: model retries cannot execute rejected skills or touch game state."""
import json
import unittest
from unittest.mock import patch
from core.autoplay import digest
from core.upstream_campaign import choose_skill

class Reply:
    def __init__(self,content):
        self.data=json.dumps({"message":{"content":content}}).encode()
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return self.data

class Opener:
    def __init__(self,replies):
        self.replies=iter(replies)
        self.requests=[]
    def open(self,request,timeout):
        self.requests.append(json.loads(request.data))
        return Reply(next(self.replies))

class CampaignSkillTests(unittest.TestCase):
    def run_model(self,replies,history=()):
        opener=Opener(replies)
        rgb=bytes(240*160*3)
        with patch("core.upstream_campaign.urllib.request.build_opener",return_value=opener):
            result=choose_skill("local-test","advance story",{},list(history),rgb)
        return result,opener
    def test_malformed_response_retries_same_observation(self):
        result,opener=self.run_model(["not-json",json.dumps({"name":"advance_dialog","args":{}})])
        self.assertEqual(result,("advance_dialog",{}))
        self.assertEqual(len(opener.requests),2)
        self.assertEqual(opener.requests[0]["messages"][1],opener.requests[1]["messages"][1])
    def test_rejected_skill_requires_distinct_action(self):
        rgb=bytes(240*160*3)
        previous={"result":"SKILL_STOPPED: no menu witness","before":digest(rgb),
                  "skill":"advance_dialog","args":{}}
        result,opener=self.run_model([json.dumps({"name":"advance_dialog","args":{}}),
                                       json.dumps({"name":"read_game_state","args":{}})],[previous])
        self.assertEqual(result,("read_game_state",{}))
        self.assertEqual(len(opener.requests),2)
    def test_twice_rejected_fails_closed(self):
        rgb=bytes(240*160*3)
        previous={"result":"SKILL_STOPPED: blocked","before":digest(rgb),
                  "skill":"advance_dialog","args":{}}
        with self.assertRaises(ValueError):
            self.run_model([json.dumps({"name":"advance_dialog","args":{}})]*2,[previous])
    def test_changed_screen_allows_retry(self):
        previous={"result":"SKILL_STOPPED: blocked","before":"other screen",
                  "skill":"advance_dialog","args":{}}
        result,_=self.run_model([json.dumps({"name":"advance_dialog","args":{}})],[previous])
        self.assertEqual(result,("advance_dialog",{}))

if __name__=="__main__":
    unittest.main()
