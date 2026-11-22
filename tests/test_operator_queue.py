import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from windows.operator_queue import ControlPoller,COMMAND_PREFIX,ACK_PREFIX

SHA="a"*64
class Remote:
    author="trusted"
    def __init__(self):
        self.priv=True;self.rows=[];self.out=[]
    def verify(self):
        if not self.priv:raise ValueError("Queue not private")
    def request(self,path="",data=None):
        if data is not None:self.out.append(data["body"]);return {}
        if "/comments?" in path:return self.rows
        if path=="/issues/7":return {"state":"open","comments":len(self.rows)}
        if path=="/issues/8":return {"title":"[ROM-TEST v1]","state":"open","user":{"login":"trusted"},"body":"{}"}
        return {}
def row(id,body,user="trusted",assoc="OWNER"):
    return {"id":id,"body":body,"user":{"login":user},"author_association":assoc}
class QueueTests(unittest.TestCase):
    def test_auth_replay_private_and_command_delivery(self):
        with tempfile.TemporaryDirectory() as d:
            r=Remote()
            command=lambda op:COMMAND_PREFIX+json.dumps({"version":1,"rom_sha256":SHA,"action":op,"args":{}})
            r.rows=[row(1,command("hard_reset"))]
            c=ControlPoller(r,7,SHA,d,{"rom":SHA},"runner","rom")
            c.poll_once() # ignore all preexisting controls at first start
            self.assertTrue(c.control.pending.empty())
            r.rows += [row(2,command("pause"),user="malicious"),row(3,command("pause")),
                       row(4,command("soft_reset"),assoc="NONE")]
            c.poll_once()
            self.assertEqual(c.control.pending.qsize(),1)
            self.assertEqual(c.control.pending.get_nowait()[1]["action"],"pause")
            c.poll_once();self.assertTrue(c.control.pending.empty())
            self.assertTrue(any(x.startswith(ACK_PREFIX) for x in r.out))
            r.priv=False
            r.rows.append(row(5,command("resume")))
            with self.assertRaises(ValueError):c.poll_once()
            self.assertTrue(c.control.pending.empty())
