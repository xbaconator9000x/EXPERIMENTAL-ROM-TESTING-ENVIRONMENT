import base64
import json
import struct
import zlib
from pathlib import Path
import tempfile
import threading
import unittest
from windows.queue_host import validate, Remote, run, TITLE, evidence_parts, png_frame, safe_log

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


class EvidenceTests(unittest.TestCase):
    def test_strict_frame_and_no_rom_save_or_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/("remote-"+"a"*32);folder.mkdir()
            cap=folder/"captures";cap.mkdir()
            pixels=bytes([10,20,30])*240*160
            (cap/"frame_000001_line_2.ppm").write_bytes(b"P6\n240 160\n255\n"+pixels)
            (cap/"frame_000002_line_2.ppm").write_bytes(b"not a frame")
            (cap/"game.gba").write_bytes(b"PRIVATE ROM")
            (folder/"game.sav").write_bytes(b"PRIVATE SAVE")
            (folder/"native.log").write_text("GBA Memory: Bad memory store: 1234\nSECRET C:\\Users\\Someone\nRESULT PASS frame=1 checks=1 line=2 core_crash=0\n")
            parts=[json.loads(p.split("\n",1)[1]) for p in evidence_parts(folder)]
            self.assertEqual({p["name"] for p in parts},{"native.log","frame_000001_line_2.png"})
            png=base64.b64decode("".join(p["base64"] for p in parts if p["mime"]=="image/png"))
            self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
            pos=8;compressed=b""
            while pos<len(png):
                n=struct.unpack(">I",png[pos:pos+4])[0]
                if png[pos+4:pos+8]==b"IDAT":compressed+=png[pos+8:pos+8+n]
                pos+=12+n
            row=zlib.decompress(compressed)[:721]
            self.assertEqual(row[:4],b"\x01\x0a\x14\x1e")
            self.assertEqual(row[4:],b"\0"*717)
            log=base64.b64decode(parts[0]["base64"])
            self.assertNotIn(b"SECRET",log)
            self.assertIn(b"RESULT PASS",log)
    def test_private_and_opt_in(self):
        q=Remote("owner/repo","owner","dummy")
        with self.assertRaises(ValueError):q.evidence(1,"ROM-EVIDENCE v1\n{}")
        q.share_evidence=True
        q.request=lambda *a,**k:{"private":False,"id":1}
        with self.assertRaises(ValueError):q.evidence(1,"ROM-EVIDENCE v1\n{}")
        q.request=lambda *a,**k:{"private":True,"id":1}
        q.evidence(1,"ROM-EVIDENCE v1\n{}")
        q.request=lambda *a,**k:{"private":True,"id":2}
        with self.assertRaises(ValueError):q.evidence(1,"ROM-EVIDENCE v1\n{}")

if __name__=="__main__":unittest.main()

