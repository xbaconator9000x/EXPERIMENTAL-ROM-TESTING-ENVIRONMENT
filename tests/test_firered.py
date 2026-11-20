import struct
import unittest
from core.firered import Profile,Reader,walk
from core.live import LiveError

class Fixture:
    sha256="0"*64
    def __init__(self):
        self.mem={}
        self.profile=Profile(self.sha256,0x03000000,0x02000020,0x03000010,0x03000020,42)
        for a,v in ((0x03000000,0x02001000),(0x02000020,0x08001000),
                    (0x08001000,3),(0x08001004,2),(0x03000010,18),
                    (0x03000014,16),(0x03000018,0x02002000),(0x03000020,42)):
            self.put(a,v,4)
        self.put(0x02001000,0,4)
        self.put(0x02001004,0x0201,2)
        for i in range(18*16):
            self.put(0x02002000+i*2,0x3ff,2)
        for y in range(2):
            for x in range(3):
                self.put(0x02002000+2*((y+7)*18+x+7),0xc01 if (x,y)==(1,0) else 1,2)
        self.stall=False

    def put(self,a,v,n):
        for i,b in enumerate(v.to_bytes(n,"little")):
            self.mem[a+i]=b

    def read(self,a,n):
        return bytes(self.mem.get(a+i,0) for i in range(n))

    def integer(self,a,n):
        return int.from_bytes(self.read(a,n),"little")

    def step(self,keys,frames):
        if keys and not self.stall:
            dx,dy={16:(1,0),32:(-1,0),64:(0,-1),128:(0,1)}[keys]
            x,y=struct.unpack("<HH",self.read(0x02001000,4))
            self.put(0x02001000,x+dx,2)
            self.put(0x02001002,y+dy,2)

class FireRedTests(unittest.TestCase):
    def test_buffer_and_detour(self):
        f=Fixture();r=Reader(f,f.profile)
        self.assertEqual(r.snapshot().map_id,(1,2))
        self.assertFalse(r.snapshot().passable(1,0))
        self.assertEqual(walk(r,(2,0)),[(0,0),(0,1),(1,1),(2,1),(2,0)])

    def test_stall_fails(self):
        f=Fixture();f.stall=True
        with self.assertRaisesRegex(LiveError,"movement mismatch"):
            walk(Reader(f,f.profile),(2,0))

    def test_context_fails(self):
        f=Fixture();f.put(0x03000020,0,4)
        with self.assertRaisesRegex(LiveError,"context"):
            Reader(f,f.profile).snapshot()

    def test_bad_grid_fails(self):
        f=Fixture();f.put(0x03000018,0x0203fff0,4)
        with self.assertRaisesRegex(LiveError,"pointer"):
            Reader(f,f.profile).snapshot()

    def test_dimensions_fail(self):
        f=Fixture();f.put(0x03000010,19,4)
        with self.assertRaisesRegex(LiveError,"dimensions"):
            Reader(f,f.profile).snapshot()

    def test_wrong_hash_fails(self):
        f=Fixture();f.sha256="1"*64
        with self.assertRaisesRegex(LiveError,"hash"):
            Reader(f,f.profile)

    def test_blocked_goal_fails(self):
        f=Fixture()
        with self.assertRaisesRegex(LiveError,"blocked"):
            walk(Reader(f,f.profile),(1,0))
