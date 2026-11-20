import hashlib
import tempfile
import unittest
from pathlib import Path
from core.autoplay import save_progress
from windows.dashboard import snapshot, find_goals, terminal, pretty_age, action_text

class DashboardTests(unittest.TestCase):
    def test_reads_atomic_snapshot_without_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);queue="owner/repo";q=root/hashlib.sha256(queue.encode()).hexdigest();p=q/"123";p.mkdir(parents=True)
            file=p/"progress.bin";rgb=bytes([7])*115200
            identity={"rom":"a"*64,"model":"test"}
            meta={"decisions":5,"frames":100,"history":[{"actions":[{"button":"A","frames":5}]}]}
            save_progress(file,identity,meta,b"state",rgb);before=file.read_bytes()
            i,m,r,t=snapshot(file)
            self.assertEqual((i,m,r),(identity,meta,rgb));self.assertGreater(t,0)
            self.assertEqual(file.read_bytes(),before);self.assertEqual(find_goals(root,queue),[p])
            file.write_bytes(before[:-1]+b"x")
            with self.assertRaises(ValueError):snapshot(file)
    def test_status_and_display(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);self.assertIsNone(terminal(p))
            (p/"terminal.json").write_text('{"status":"NEEDS_REVIEW"}')
            self.assertEqual(terminal(p),"NEEDS_REVIEW")
            self.assertEqual(pretty_age(65),"1m 05s")
            self.assertEqual(action_text({"actions":[{"button":"A","frames":5}]}),"A 5f")
