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
    def test_long_screenshot_history_still_announces_and_dispatches(self):
        class Paged(Remote):
            def request(self,path="",data=None):
                if data is not None:
                    self.out.append(data["body"])
                    return {}
                if path=="/issues/7":
                    return {"state":"open","comments":len(self.rows)}
                if "/comments?" in path:
                    import re
                    page=int(re.search(r"(?:[?&])page=(\d+)",path).group(1))
                    count=int(re.search(r"per_page=(\d+)",path).group(1))
                    self.max_page_size=max(getattr(self,"max_page_size",0),count)
                    if count>20:
                        raise ValueError("Github comment page exceeds remote response cap")
                    return self.rows[(page-1)*count:page*count]
                return {}
        with tempfile.TemporaryDirectory() as d:
            r=Paged()
            # 141 old image comments could exceed the 2MiB transport limit
            # if fetched 100 at a time; fetching 20 remains bounded.
            r.rows=[row(i+1,"ROM-AUTOPLAY-FRAME v1\n"+"A"*44000)
                    for i in range(141)]
            poller=ControlPoller(r,7,SHA,d,{"rom":SHA},"runner","rom")
            poller.poll_once()
            self.assertEqual(r.max_page_size,20)
            self.assertTrue(any(v.startswith("ROM-CONTROL-READY v1\n")
                                for v in r.out))
            self.assertEqual(poller.seen,141)
            new=COMMAND_PREFIX+json.dumps({"version":1,"rom_sha256":SHA,
                                          "action":"status","args":{}})
            r.rows.append(row(142,new))
            poller.poll_once()
            self.assertEqual(poller.control.pending.get_nowait()[1]["action"],"status")
            self.assertTrue(any("ACCEPTED" in v for v in r.out))
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
