import struct
import unittest
from core.jj_fast import ordinary_dialogue,quick_dialogue,decode_party,ORDERS,Adapter,SHA
from core.firered import Field

def frame(choice=False,center=False):
    rgb=bytearray(bytes((4,8,12))*38400)
    def rect(x,y,w,h,c):
        for j in range(y,y+h):
            rgb[(j*240+x)*3:(j*240+x+w)*3]=bytes(c)*w
    x=17 if center else 1;w=206 if center else 238
    rect(x,113,w,6,(214,74,57));rect(x,119,w,34,(255,255,255));rect(x,153,w,6,(82,90,90))
    rect(24,125,15,4,(20,20,90))
    if choice:rect(163,40,58,4,(214,74,57));rect(163,44,58,24,(255,255,255))
    return bytes(rgb)
def party():
    raw=bytearray(600);pid=7;ot=13
    raw[:8]=struct.pack("<II",pid,ot);raw[84]=5
    struct.pack_into("<HH",raw,86,18,20)
    g=struct.pack("<H",19)+bytes(10);a=struct.pack("<4H",33,0,0,0)+bytes([35,0,0,0])
    blocks={"G":g,"A":a,"E":bytes(12),"M":bytes(12)}
    plain=b"".join(blocks[c] for c in ORDERS[pid%24])
    struct.pack_into("<H",raw,28,sum(struct.unpack("<24H",plain))&0xffff)
    raw[32:80]=b"".join((v^(pid^ot)).to_bytes(4,"little") for v in struct.unpack("<12I",plain))
    return raw
class FastTests(unittest.TestCase):
    def test_dialogue_not_choices_or_intro(self):
        self.assertIsNotNone(ordinary_dialogue(frame()))
        self.assertIsNone(ordinary_dialogue(frame(choice=True)))
        self.assertIsNone(ordinary_dialogue(frame(center=True)))
        self.assertIsNone(ordinary_dialogue(bytes(115200)))
        self.assertIsNotNone(quick_dialogue(frame(),{"history":[]}))
        self.assertIsNone(quick_dialogue(frame(),{"history":[{"source":"fast_dialogue"}]*6}))
    def test_native_party_checksum(self):
        p=party();m=decode_party(p)[0];self.assertEqual((m["species_id"],m["hp"],m["moves"][0]),(19,18,33))
        p[32]^=4
        with self.assertRaises(ValueError):decode_party(p)
    def test_motion_admission_and_route(self):
        a=Adapter("unused","wrong")
        def f(x,y):return (Field((1,2),(x,y),4,4,(1,)*16),0x08001235,set())
        m={};a.observe_move(f(0,0),f(1,0),[{"button":"RIGHT"}],m)
        self.assertFalse(a.verified_field(f(1,0),m))
        a.observe_move(f(1,0),f(1,1),[{"button":"DOWN"}],m)
        self.assertTrue(a.verified_field(f(1,1),m))
        self.assertTrue(a.start_route(f(1,1),m,[3,1]))
        self.assertEqual(a.route_action(f(1,1),m)[1],(2,1))
        self.assertIsNone(a.route_action((f(1,1)[0],0x08001237,set()),m))
