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
    def test_interleaved_rejected_skill_remains_quarantined(self):
        rgb=bytes(240*160*3)
        history=[
            {"result":"SKILL_STOPPED: no witness","before":digest(rgb),
             "skill":"advance_dialog","args":{}},
            {"result":"read only","before":digest(rgb),"after":digest(rgb),
             "skill":"read_game_state","args":{}},
        ]
        result,opener=self.run_model([
            json.dumps({"name":"advance_dialog","args":{}}),
            json.dumps({"name":"team_report","args":{}})
        ],history)
        self.assertEqual(result,("team_report",{}))
        self.assertEqual(len(opener.requests),2)

    def test_interleaved_rejection_cannot_repeat_twice(self):
        rgb=bytes(240*160*3)
        history=[
            {"result":"SKILL_STOPPED: no witness","before":digest(rgb),
             "skill":"advance_dialog","args":{}},
            {"result":"read only","before":digest(rgb),"after":digest(rgb),
             "skill":"read_game_state","args":{}},
        ]
        with self.assertRaises(ValueError):
            self.run_model([json.dumps({"name":"advance_dialog","args":{}})]*2,history)

    def test_two_unchanged_successes_require_new_skill(self):
        rgb=bytes(240*160*3)
        history=[{"result":"read only","before":digest(rgb),"after":digest(rgb),
                  "skill":"read_game_state","args":{}} for _ in range(2)]
        result,opener=self.run_model([
            json.dumps({"name":"read_game_state","args":{}}),
            json.dumps({"name":"advance_dialog","args":{}})],history)
        self.assertEqual(result,("advance_dialog",{}))
        self.assertEqual(len(opener.requests),2)

    def test_no_progress_twice_fails_closed(self):
        rgb=bytes(240*160*3)
        history=[{"result":"ok","before":digest(rgb),"after":digest(rgb),
                  "skill":"team_report","args":{}} for _ in range(2)]
        with self.assertRaises(ValueError):
            self.run_model([json.dumps({"name":"team_report","args":{}})]*2,history)

    def test_transition_does_not_count_as_unchanged(self):
        rgb=bytes(240*160*3)
        history=[{"result":"ok","before":digest(rgb),"after":"different",
                  "skill":"advance_dialog","args":{}} for _ in range(2)]
        result,_=self.run_model([json.dumps({"name":"advance_dialog","args":{}})],history)
        self.assertEqual(result,("advance_dialog",{}))

    def test_changed_screen_allows_retry(self):
        previous={"result":"SKILL_STOPPED: blocked","before":"other screen",
                  "skill":"advance_dialog","args":{}}
        result,_=self.run_model([json.dumps({"name":"advance_dialog","args":{}})],[previous])
        self.assertEqual(result,("advance_dialog",{}))

if __name__=="__main__":
    unittest.main()
