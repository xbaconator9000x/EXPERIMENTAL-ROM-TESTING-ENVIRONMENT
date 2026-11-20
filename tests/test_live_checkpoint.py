import hashlib
import tempfile
import unittest
from pathlib import Path
from core.live import Live
from make_gba_fixture import make_rom
from windows.host import REPO

RUNNER=REPO/"build"/"live_runner.exe"
if not RUNNER.is_file():RUNNER=REPO/"build"/"live_runner"

class LiveCheckpointTests(unittest.TestCase):
    @unittest.skipUnless(RUNNER.is_file(),"native live runner not built")
    def test_native_live_state_and_frame(self):
        with tempfile.TemporaryDirectory() as d:
            rom=Path(d)/"fixture.gba";data=make_rom();rom.write_bytes(data)
            sha=hashlib.sha256(data).hexdigest()
            with Live(RUNNER,rom,sha) as live:
                live.step(0,120)
                self.assertEqual(live.integer(0x02000000,4),1)
                live.step(1,2)
                self.assertEqual(live.integer(0x02000000,4),0)
                state=live.save_state()
                self.assertEqual(len(live.rgb()),240*160*3)
            with Live(RUNNER,rom,sha) as live:
                live.load_state(state)
                self.assertEqual(live.integer(0x02000000,4),0)
                live.step(0,2)
                self.assertEqual(live.integer(0x02000000,4),1)
                self.assertEqual(live.rgb(),b"\xff"*240*160*3)
