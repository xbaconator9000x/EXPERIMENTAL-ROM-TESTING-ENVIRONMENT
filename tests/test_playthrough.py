import base64
import hashlib
import json
import unittest
from core.playthrough import decode_evidence, next_job, recoverable_actions, progress_record, action_key

def envelope(name,data,mime):
    return "ROM-EVIDENCE v1\n"+json.dumps({"name":name,"mime":mime,"sha256":hashlib.sha256(data).hexdigest(),"part":1,"parts":1,"base64":base64.b64encode(data).decode()})

def evidence():
    # Minimal synthetic header for transport unit tests only, not a gameplay image.
    png=b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\xf0\x00\x00\x00\xa0"+b"\x08\x02\x00\x00\x00"+b"\x00"*4
    name="frame_000001_line_2.png"
    log=b"RESULT PASS frame=1 checks=1 line=2 core_crash=0"
    return [envelope(name,png,"image/png"),envelope("native.log",log,"text/plain"),"ROM-EVIDENCE-COMPLETE v1\n"+json.dumps({"status":"PASS","parts":2,"files":[name,"native.log"]})]

class PlaythroughTests(unittest.TestCase):
    def test_complete_and_duplicate(self):
        c=evidence();e=decode_evidence(c+[c[0]])
        self.assertEqual(e.status,"PASS")
        self.assertEqual(len(e.frames),1)
        for bad in (c[:-1],c[1:],c+[c[0].replace('"part": 1','"part": 2')]):
            with self.assertRaises(ValueError):decode_evidence(bad)
    def test_corruption(self):
        c=evidence();p=json.loads(c[0].split("\n",1)[1]);p["base64"]="AAAA"
        with self.assertRaises(ValueError):decode_evidence(["ROM-EVIDENCE v1\n"+json.dumps(p),*c[1:]])
    def test_replay_and_resume(self):
        p={"version":1,"sha256":"a"*64,"scenario":["assert 32 0x02000000 1 1","idle 40","capture"]}
        j=next_job(p,["press DOWN 16","idle 30"])
        self.assertEqual(j["scenario"],["assert 32 0x02000000 1 1","idle 40","press DOWN 16","idle 30","capture"])
        j=next_job(p,["press DOWN 16"],resume="room",checkpoint="hall",assertions=["assert 8 0x02000000 1 1"])
        self.assertEqual(j["version"],2)
        self.assertEqual(j["resume"],"room")
        with self.assertRaises(ValueError):next_job(p,["press DOWN 16"],resume="room")
        with self.assertRaises(ValueError):next_job(p,["exec cmd"])
    def test_stall_recovery_and_ending(self):
        e=decode_evidence(evidence());a=["press A 5","idle 60"];b=["press B 5","idle 60"]
        row=progress_record(job=1,scene="dialogue",previous_screen=e.screen_hash,action=a,evidence=e)
        self.assertEqual(row["outcome"],"unchanged")
        self.assertEqual(recoverable_actions([row],e.screen_hash,[a,b]),[b])
        with self.assertRaises(ValueError):progress_record(job=1,scene="ending",previous_screen=e.screen_hash,action=a,evidence=e,ending_verified=True)
