import struct
import unittest
from unittest.mock import patch
from core.jj_fast import ordinary_dialogue,quick_dialogue,decode_party,ORDERS,Adapter,SHA,MAIN,SCRIPT,FADE,OBJECTS
from core.firered import Field

def frame(choice=False,center=False,navy=False,blank=False,furniture=False):
    rgb=bytearray(bytes((4,8,12))*38400)
    def rect(x,y,w,h,c):
        for j in range(y,y+h):
            rgb[(j*240+x)*3:(j*240+x+w)*3]=bytes(c)*w
    x=17 if center else 1;w=206 if center else 238
    rect(x,113,w,6,(214,74,57))
    rect(x,119,w,34,(21,31,80) if navy else (255,255,255))
    rect(x,153,w,6,(82,90,90))
    if not blank:
        rect(24,125,15,4,(255,255,255) if navy else (20,20,90))
    if furniture:rect(55,65,32,20,(255,255,255))
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
        self.assertIsNotNone(ordinary_dialogue(frame(navy=True)))
        self.assertIsNotNone(ordinary_dialogue(frame(navy=True,furniture=True)))
        self.assertIsNotNone(quick_dialogue(frame(navy=True),{"history":[]}))
        self.assertIsNone(ordinary_dialogue(frame(navy=True,choice=True)))
        self.assertIsNone(ordinary_dialogue(frame(navy=True,center=True)))
        self.assertIsNone(ordinary_dialogue(frame(navy=True,blank=True)))
        self.assertIsNone(ordinary_dialogue(frame(blank=True)))
        self.assertIsNotNone(quick_dialogue(frame(),{"history":[{"source":"fast_dialogue"}]*9}))
        self.assertIsNone(quick_dialogue(frame(),{"history":[{"source":"fast_dialogue"}]*10}))
        h=[{"source":"fast_dialogue","dialogue_page":ordinary_dialogue(frame(navy=True)), "before":"same","after":"same"}]
        self.assertIsNone(quick_dialogue(frame(navy=True),{"history":h}))
        self.assertIsNotNone(quick_dialogue(frame(navy=True),{"history":[{"source":"vision_compact"}]}))
    def test_actual_orange_border_and_dense_second_line(self):
        # Synthetic recreation of the user's v1.03.3 dialogue geometry:
        # exactly one full-width orange (206,82,0) border scanline, white
        # text body and densely printed second line. No ROM/screenshot data.
        raw=bytearray(bytes((4,8,12))*38400)
        def rect(x,y,w,h,color):
            for row in range(y,y+h):
                raw[(row*240+x)*3:(row*240+x+w)*3]=bytes(color)*w
        rect(7,116,225,1,(206,82,0))
        rect(7,119,225,34,(255,255,255))
        rect(7,153,225,6,(66,66,82))
        rect(20,125,15,4,(99,99,99))
        rect(22,146,120,3,(99,99,99))
        rgb=bytes(raw)
        self.assertIsNotNone(ordinary_dialogue(rgb))
        self.assertIsNotNone(quick_dialogue(rgb,{"history":[]}))
        # A one-line orange horizontal decoration is insufficient:
        # safety also requires the full-width lower edge and text.
        rect(7,153,225,6,(4,8,12))
        self.assertIsNone(ordinary_dialogue(bytes(raw)))

    def test_real_style_starter_warning_box_with_dark_lower_border(self):
        # A real v1.03.3 playthrough showed a full-width field message
        # while script controls were locked. The previous lower-border detector demanded gray/
        # navy and silently returned to vision-driven directional movement.
        rgb=bytearray(frame())
        for y in range(113,119):
            rgb[(y*240+1)*3:(y*240+239)*3]=bytes((158,70,36))*238
        for y in range(153,159):
            rgb[(y*240+1)*3:(y*240+239)*3]=bytes((16,16,21))*238
        shown=bytes(rgb)
        self.assertIsNotNone(ordinary_dialogue(shown))
        self.assertEqual(quick_dialogue(shown,{"history":[]})[0]["actions"],
                         [{"button":"A","frames":5}])
        # A real secondary choice panel must still inhibit blind A.
        self.assertIsNone(ordinary_dialogue(frame(choice=True)))

    def test_native_lock_flags_diagnose_only_and_do_not_bypass(self):
        class FakeLive:
            def __init__(self,script,fade):self.script,self.fade=script,fade
            def integer(self,address,size):
                return {MAIN+4:0x08000001,SCRIPT:self.script,FADE:self.fade}.get(address,0)
        a=Adapter("unused","wrong")
        a.admitted=True;a.size=0x10000
        for script,fade in ((1,0),(0,1),(1,1)):
            a.attach(FakeLive(script,fade))
            self.assertIsNone(a.candidate(bytes(115200)))
            self.assertEqual(a.reason,"SCRIPT_CONTROL_LOCK")
            self.assertEqual(a.lock_probe,{"script_active":bool(script),"script_context2_active":bool(fade)})

    def test_stale_script_flag_recovered_only_by_verified_operator_movement(self):
        # Synthetic regression for v1.03.3 decision 989: native movement was
        # witnessed before a manual input, yet SCRIPT remained nonzero.
        class FakeLive:
            def __init__(self,script=1,context2=0,frozen=False):
                self.script,self.context2,self.frozen=script,context2,frozen
            def integer(self,address,size):
                return {MAIN+4:0x08000001,SCRIPT:self.script,FADE:self.context2}.get(address,0)
            def read(self,address,size):
                if address!=OBJECTS or size!=36*16:raise AssertionError("unexpected read")
                objects=bytearray(size)
                struct.pack_into("<I",objects,0,0x10101 if self.frozen else 0x10001)
                struct.pack_into("<hh",objects,16,10,13)
                return bytes(objects)
        field=Field((43,1),(3,6),12,12,(0,)*144)
        meta={"decisions":989,"operator_last_action":"input",
              "last_native_field":{"map":[43,1],"pos":[4,3]},
              "history":[
                  {"decision":977,"source":"native_explore","field_after":{"map":[43,1],"pos":[4,6]}},
                  {"decision":978,"source":"native_explore","field_after":{"map":[43,1],"pos":[4,5]}},
                  {"decision":980,"source":"native_explore","field_after":{"map":[43,1],"pos":[4,3]}}]}
        def candidate(m,live):
            a=Adapter("unused","wrong");a.admitted=True;a.size=0x10000;a.attach(live,m)
            with patch("core.jj_fast.Reader") as reader:
                reader.return_value.snapshot.return_value=field
                answer=a.candidate(bytes(115200))
                return a,answer,reader
        a,out,reader=candidate(None,FakeLive())
        self.assertIsNone(out)
        self.assertEqual(a.reason,"SCRIPT_CONTROL_LOCK")
        self.assertFalse(reader.called)
        a,out,_=candidate({**meta,"operator_last_action":"status"},FakeLive())
        self.assertIsNone(out)
        a,out,_=candidate(meta,FakeLive())
        self.assertIsNotNone(out)
        self.assertTrue(a.verified_field(out,meta))
        self.assertEqual(a.reason,"FIELD_STRUCTURES_VALID_STALE_SCRIPT_BYTE")
        self.assertEqual(meta["stale_script_field"]["source"],"operator_input_plus_native_movement")
        # Once recovered, the same checked map/callback can navigate further
        # without re-running the manual override.
        meta.pop("operator_last_action")
        self.assertIsNotNone(candidate(meta,FakeLive())[1])
        self.assertIsNone(candidate(meta,FakeLive(context2=1))[1])
        self.assertIsNone(candidate(meta,FakeLive(frozen=True))[1])
        with patch("core.jj_fast.Reader") as reader:
            reader.return_value.snapshot.return_value=Field((43,2),(3,6),12,12,(0,)*144)
            self.assertIsNone(a.candidate(bytes(115200)))
        # Visually confirmed dialogue always wins over stale-script recovery.
        self.assertIsNone(a.candidate(frame()))

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
