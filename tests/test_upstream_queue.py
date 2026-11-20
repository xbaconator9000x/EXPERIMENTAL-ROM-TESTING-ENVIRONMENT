import unittest,json
from windows.autoplay import goal,TITLE,UPSTREAM_TITLE
from windows.dashboard import action_text
class UpstreamQueueTests(unittest.TestCase):
    def test_explicit_version(self):
        job={"version":2,"sha256":"a"*64,"goal":"Play LeafGreen"}
        self.assertEqual(goal(json.dumps(job),UPSTREAM_TITLE),job)
        with self.assertRaises(ValueError):goal(json.dumps(job),TITLE)
        job["version"]=1
        with self.assertRaises(ValueError):goal(json.dumps(job),UPSTREAM_TITLE)
        self.assertEqual(goal(json.dumps(job)),job)
    def test_dashboard_skill(self):
        self.assertEqual(action_text({"source":"upstream_skill","skill":"catch","frames":120}),"catch (120f)")
