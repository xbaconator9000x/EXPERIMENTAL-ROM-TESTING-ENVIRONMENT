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

# Capture a known white framebuffer and verify the complete RGB payload.
from core.probe import inspect, run
from dataclasses import asdict
from tempfile import TemporaryDirectory

input_rom=Path("build/synthetic.gba")
input_sha=hashlib.sha256(input_rom.read_bytes()).hexdigest()
with TemporaryDirectory() as folder:
    image=Path(folder)/"frame.ppm"
    with Live("build/live_runner",input_rom,input_sha) as live:
        live.step(0,120)
        live.screenshot(image)
        raw=image.read_bytes()
        header=b"P6\n240 160\n255\n"
        assert raw.startswith(header) and len(raw)==len(header)+240*160*3
        assert raw[len(header):]==b"\xff"*(240*160*3),"unexpected framebuffer pixels"
        print("NATIVE FRAME PASS: exact white RGB framebuffer")
    with Live("build/live_runner",rom,sha) as live:
        live.step(0,120)
        candidate=asdict(profile)
        out=Path(folder)/"probe"
        run(live,candidate,[{"op":"observe"},{"op":"press","key":"DOWN","frames":1,"release":2,"capture":True}],out)
        import json
        observations=[json.loads(line)["observed"]["field"] for line in (out/"trace.jsonl").read_text().splitlines()]
        assert observations[0]["position"]==[0,0]
        assert observations[1]["position"]==[0,1]
        assert (out/"frame-0001.ppm").stat().st_size==len(header)+240*160*3
        print("NATIVE PROBE PASS: two observed positions")
