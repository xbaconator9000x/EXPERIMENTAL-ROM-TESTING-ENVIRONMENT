import tempfile,threading,unittest
from core.operator_model import interruptible_decision
from core.operator_control import OperatorControl,validate_command
import json
class Fake:
    def __init__(self):self.i=1
    def rgb(self):return bytes((self.i,))*115200
    def save_state(self):return bytes((self.i,))*8
    def step(self,keys,frames):self.i=2
class ModelTests(unittest.TestCase):
    def test_user_input_invalidates_inflight_vision(self):
        with tempfile.TemporaryDirectory() as d:
            c=OperatorControl(d,{"rom":"a"*64},"runner","rom","a"*64)
            gate=threading.Event()
            def inference():
                gate.wait(.1)
                return {"action":"stale"}
            f=Fake();m={"decisions":0,"frames":0,"history":[]}
            body=json.dumps({"version":1,"rom_sha256":"a"*64,"action":"input","args":{"actions":[{"button":"A","frames":5}]}})
            c.offer(4,validate_command(body,"a"*64))
            result,f,m,rgb,stale,stop=interruptible_decision(inference,c,f,m,f.rgb(),lambda:False)
            self.assertIsNone(result)
            self.assertTrue(stale);self.assertFalse(stop)
            self.assertEqual(f.i,2)
    def test_plain_inference(self):
        with tempfile.TemporaryDirectory() as d:
            c=OperatorControl(d,{"rom":"a"*64},"runner","rom","a"*64)
            f=Fake();m={"decisions":0,"frames":0,"history":[]}
            result,_,_,_,stale,stop=interruptible_decision(lambda:"valid",c,f,m,f.rgb())
            self.assertEqual(result,"valid");self.assertFalse(stale);self.assertFalse(stop)
