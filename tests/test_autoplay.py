import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core.autoplay import parse_decision, choose, png, save_progress, load_progress, play, title_recovery, model_error
from windows.autoplay import goal

def decision(button="A"):
    return {"scene":"test","objective":"move","actions":[{"button":button,"frames":5}],"review":False}

class Model:
    model="fake"
    def decide(self,*args):return decision()

class FakeLive:
    def __init__(self,*args):self.n=0
    def step(self,k,f):self.n=(self.n+f+k)%256
    def rgb(self):return bytes([self.n])*115200
    def save_state(self):return bytes([self.n])
    def load_state(self,data):self.n=data[0]
    def close(self):pass

class AutoTests(unittest.TestCase):
    def test_model_boundary(self):
        self.assertEqual(parse_decision(json.dumps(decision())),decision())
        for d in (decision("cmd.exe"),{**decision(),"actions":[{"button":"A","frames":True}]},{**decision(),"actions":[{"button":"A","frames":121}]},{**decision(),"review":True},{**decision(),"exec":"x"}):
            with self.assertRaises(ValueError):parse_decision(json.dumps(d))
    def test_recovery(self):
        d=decision();h=[{"before":"x","after":"x","actions":d["actions"]}]
        self.assertNotEqual(choose(d,h,"x"),d["actions"])
        self.assertEqual(choose(d,h,"other"),d["actions"])
    def test_goal_boundary(self):
        g={"version":1,"sha256":"a"*64,"goal":"play to the credits"}
        self.assertEqual(goal(json.dumps(g)),g)
        for bad in ({**g,"path":"C:/x"},{**g,"sha256":"../x"},{**g,"version":True}):
            with self.assertRaises(ValueError):goal(json.dumps(bad))
    def test_png_size(self):
        p=png(bytes(115200),3)
        self.assertEqual(p[:8],b"\x89PNG\r\n\x1a\n")
        self.assertEqual(int.from_bytes(p[16:20],"big"),720)
        self.assertEqual(int.from_bytes(p[20:24],"big"),480)
    def test_persistent_loop(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);runner=folder/"runner";runner.write_bytes(b"fake")
            with patch("core.autoplay.Live",FakeLive):
                status,meta,rgb=play(runner,folder/"rom","a"*64,"goal",folder,Model(),max_decisions=3)
                self.assertEqual(status,"BUDGET_REACHED");self.assertEqual(meta["decisions"],3)
                status,meta2,rgb2=play(runner,folder/"rom","a"*64,"goal",folder,Model(),max_decisions=5)
                self.assertEqual(meta2["decisions"],5);self.assertGreater(meta2["frames"],meta["frames"])
                self.assertNotEqual(rgb,rgb2)
                with self.assertRaises(ValueError):play(runner,folder/"rom","a"*64,"different goal",folder,Model(),max_decisions=6)
    def test_checkpoint_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"state";save_progress(p,{"id":1},{"turn":1},b"a",bytes(115200))
            self.assertEqual(load_progress(p,{"id":1})[1],b"a")
            p.write_bytes(p.read_bytes()[:-1]+b"x")
            with self.assertRaises(ValueError):load_progress(p,{"id":1})

    def test_title_recovery_animated_screen(self):
        h=[{"scene":"title_screen","actions":[{"button":"A","frames":16}],"before":"a","after":"b"},
           {"scene":"title_screen","actions":[{"button":"A","frames":16}],"before":"b","after":"c"}]
        wait=title_recovery({"history":h,"frames":280})
        self.assertTrue(all(a["button"]=="WAIT" for a in wait["actions"]))
        self.assertEqual(title_recovery({"history":h,"frames":900})["actions"][0]["button"],"START")
        self.assertIsNone(title_recovery({"history":[h[0],{**h[1],"scene":"battle"}],"frames":900}))
        self.assertIsNone(title_recovery({"history":[h[0],{**h[1],"actions":[{"button":"START","frames":6}]}],"frames":900}))
    def test_model_error_enum(self):
        self.assertEqual(model_error(TimeoutError("private path")),"LOCAL_TIMEOUT")
        self.assertEqual(model_error(ValueError("private content")),"INVALID_DECISION_SCHEMA")
