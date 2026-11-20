"""Native emulation of an original ARM field fixture; no retail game data."""
import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.live import Live, LiveError
from core.firered import Profile, Reader, walk
from make_gba_fixture import make_rom

base=bytearray(make_rom())
code=Path("build/field.bin").read_bytes()
base[0xc0:0xc0+len(code)]=code
rom=Path("build/field.gba")
rom.write_bytes(base)
sha=hashlib.sha256(base).hexdigest()
profile=Profile(sha,0x03000000,0x02000020,0x03000010,0x03000020,42)
with Live("build/live_runner",rom,sha) as live:
    live.step(0,120)
    reader=Reader(live,profile)
    assert reader.snapshot().pos==(0,0)
    # Actual emulated game code rejects walking straight through the wall.
    live.step(16,1)
    live.step(0,2)
    assert reader.snapshot().pos==(0,0)
    trace=walk(reader,(2,0),settle_frames=2)
    assert trace==[(0,0),(0,1),(1,1),(2,1),(2,0)],trace
    assert reader.snapshot().pos==(2,0)
    try:
        live.read(0x04000000,1)
    except LiveError:
        pass
    else:
        raise AssertionError("IO memory read unexpectedly permitted")
    print("NATIVE WALK PASS",trace)
