import json
from pathlib import Path
import tempfile
import threading
import unittest
from windows.queue_host import validate, Remote, run, TITLE

def job():return {"version":1,"sha256":"0"*64,"scenario":["press A 2","assert 32 0x02000000 1 1","capture"]}

class QueueTests(unittest.TestCase):
    def test_valid(self):self.assertEqual(validate(json.dumps(job())),job())
    def test_reject(self):
        for line in ("exec cmd.exe","capture ../../secret","press A 0","idle 200001","assert 8 0x04000000 1 1","assert 32 0x02000001 1 1","press A 2\ncapture"):
            with self.subTest(line=line),self.assertRaises(ValueError):
                validate(json.dumps({**job(),"scenario":[line,"assert 32 0x02000000 1 1"]}))
    def test_requires_assertion(self):
        with self.assertRaises(ValueError):validate(json.dumps({**job(),"scenario":["idle 1"]}))
    def test_duplicate_keys(self):
        with self.assertRaises(ValueError):validate('{"version":1,"version":1}')
    def test_no_remote_path_or_command(self):
        for update in ({"sha256":"../secret"},{"command":"whoami"},{"version":True}):
            with self.assertRaises(ValueError):validate(json.dumps({**job(),**update}))
    def test_private_only(self):
        q=Remote("owner/repo","owner","dummy")
        q.request=lambda *a,**k:{"private":False}
        with self.assertRaises(ValueError):list(q.pending())
    def test_author_and_title(self):
        q=Remote("owner/repo","owner","dummy")
        good={"id":1,"number":1,"title":TITLE,"user":{"login":"owner"}}
        q.request=lambda p="": {"private":True} if not p else [good,{**good,"id":2,"user":{"login":"other"}},{**good,"id":3,"title":"other"},{**good,"id":4,"pull_request":{}}]
        self.assertEqual(list(q.pending()),[good])
    def test_missing_rom_and_wrong_hash(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);runner=p/"runner.exe";runner.touch()
            self.assertEqual(run(job(),threading.Event(),runner,p,p),"ROM_NOT_REGISTERED")
            (p/("0"*64+".gba")).write_bytes(b"abc")
            self.assertEqual(run(job(),threading.Event(),runner,p,p),"ROM_HASH_MISMATCH")
    def test_result_only_status(self):
        q=Remote("owner/repo","owner","dummy")
        events=[]
        def request(path="",data=None):
            events.append((path,data));return {"private":True}
        q.request=request;q.result(5,"PASS")
        self.assertEqual(events[-1],("/issues/5/comments",{"body":"ROM Test Host v1: **PASS**. Detailed evidence retained locally."}))
        with self.assertRaises(ValueError):q.result(5,"private path")

if __name__=="__main__":unittest.main()
