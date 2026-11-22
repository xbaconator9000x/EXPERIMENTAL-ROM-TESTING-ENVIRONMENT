import json
import tempfile
import unittest
from pathlib import Path
from core.operator_control import validate_command,OperatorControl
from core.autoplay import digest,load_progress

SHA="a"*64
def cmd(action,args=None,**rest):
    return json.dumps({"version":1,"rom_sha256":SHA,"action":action,"args":args or {},**rest})
class FakeLive:
    def __init__(self):
        self.value=1
        self.steps=[]
    def save_state(self):return bytes((self.value,))*24
    def load_state(self,b):self.value=b[0]
    def rgb(self):return bytes((self.value,))*115200
    def step(self,k,n):self.steps.append((k,n));self.value=(self.value+1)%255 or 1

class OperatorValidationTests(unittest.TestCase):
    def test_contract_and_bounded_native_inputs(self):
        self.assertEqual(validate_command(cmd("input",{"actions":[{"button":"A","frames":8}]}),SHA)["action"],"input")
        for raw in (cmd("input",{"actions":[{"button":"A","frames":960}]}),
                    cmd("test",{"issue":True}),cmd("restore",{"name":"../secret"}),
                    cmd("reset"),cmd("input",{"actions":[{"button":"A","frames":8}], "path":"x"}),
                    cmd("input",{"actions":[{"button":"A","frames":-1}]}),
                    cmd("input",{"actions":[{"button":"UP","frames":120}]*9}),
                    cmd("pause",expected_screen="deadbeef"),
                    '{"version":1,"version":1,"rom_sha256":"'+SHA+'","action":"pause","args":{}}'):
            with self.assertRaises(ValueError):validate_command(raw,SHA)

class OperatorRuntimeTests(unittest.TestCase):
    def test_snapshot_restore_persistent_and_no_emulator_writes(self):
        with tempfile.TemporaryDirectory() as d:
            events=[]
            identity={"rom":SHA,"runner":"b"*64,"model":"test","goal":"play"}
            o=OperatorControl(d,identity,"runner","rom",SHA,ack=lambda *a,**kw:events.append(a))
            f=FakeLive();meta={"decisions":1,"frames":120,"history":[]}
            f,meta,rgb,act=o.apply(11,validate_command(cmd("snapshot",{"name":"bedside"}),SHA),f,meta,f.rgb())
            self.assertEqual(act,"snapshot")
            f,meta,rgb,act=o.apply(12,validate_command(cmd("input",{"actions":[{"button":"DOWN","frames":4}]}),SHA),f,meta,rgb)
            self.assertEqual(f.steps,[(128,4),(0,3)])
            self.assertNotEqual(rgb,bytes((1,))*115200)
            f,meta,rgb,act=o.apply(13,validate_command(cmd("restore",{"name":"bedside"}),SHA),f,meta,rgb)
            self.assertEqual(rgb,bytes((1,))*115200)
            self.assertTrue((Path(d)/"operator-states"/"before-13.bin").is_file())
            self.assertEqual(load_progress(Path(d)/"progress.bin",identity)[1],f.save_state())
            with self.assertRaises(ValueError):
                o.apply(14,validate_command(cmd("snapshot",{"name":"bedside"}),SHA),f,meta,rgb)
            self.assertEqual([e[1] for e in events],["EXECUTED"]*3)
    def test_directional_operator_override_revalidates_after_verified_unlock(self):
        with tempfile.TemporaryDirectory() as d:
            identity={"rom":SHA,"runner":"b"*64,"model":"test","goal":"play"}
            o=OperatorControl(d,identity,"runner","rom",SHA)
            f=FakeLive()
            meta={"decisions":1178,"frames":62312,"history":[],
                  "review":{"scene":"unclassified_game_state"},
                  "native_revisit":{"approaches":24},
                  "field_strategic_referral":{"calls":2}}
            cmd_down=validate_command(cmd("input",{"actions":[{"button":"DOWN","frames":16}]}),SHA)
            _,meta,rgb,_=o.apply(25,cmd_down,f,meta,f.rgb())
            self.assertEqual(meta["recovery_resume"],
                {"kind":"native_script_locked","phase":"pending",
                 "source":"operator_directional_override"})
            # No navigation book is purged until native code confirms the
            # map callback is valid and scripted control has released.
            self.assertEqual(meta["native_revisit"]["approaches"],24)
            self.assertEqual(meta["field_strategic_referral"]["calls"],2)
            self.assertNotIn("review",meta)
            # A-only commands are never admitted as field-movement evidence.
            meta.pop("recovery_resume")
            meta["review"]={"scene":"unclassified_game_state"}
            _,meta,rgb,_=o.apply(26,validate_command(
                cmd("input",{"actions":[{"button":"A","frames":4}]}),SHA),f,meta,rgb)
            self.assertNotIn("recovery_resume",meta)
            # Identical screenshots are also insufficient.
            class StaticLive(FakeLive):
                def step(self,k,n):self.steps.append((k,n))
            stationary=StaticLive()
            meta["review"]={"scene":"native_navigation_exhausted"}
            _,meta,_,_=o.apply(27,cmd_down,stationary,meta,stationary.rgb())
            self.assertNotIn("recovery_resume",meta)

    def test_pause_resume_and_stale_screen(self):
        with tempfile.TemporaryDirectory() as d:
            o=OperatorControl(d,{"rom":SHA},"runner","rom",SHA)
            f=FakeLive();m={"decisions":0,"frames":0,"history":[]}
            f,m,rgb,_=o.apply(1,validate_command(cmd("pause"),SHA),f,m,f.rgb())
            self.assertTrue(o.paused)
            with self.assertRaises(ValueError):
                o.apply(2,validate_command(cmd("input",{"actions":[{"button":"A","frames":2}]},expected_screen="0"*64),SHA),f,m,rgb)
            f,m,rgb,_=o.apply(3,validate_command(cmd("resume"),SHA),f,m,rgb)
            self.assertFalse(o.paused)
