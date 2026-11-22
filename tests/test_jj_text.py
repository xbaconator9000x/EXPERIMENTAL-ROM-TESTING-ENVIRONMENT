"""No-ROM tests grounded in actual FireRed TextPrinter layout and states."""
import unittest
from core.jj_text import decide,probe,floating_choice,BOX_TYPE,PRINTER_0,PRINTER_SIZE

ROM_BASE=0x08000000
class Live:
    def __init__(self,kind=2,state=2,active=1,ptr=ROM_BASE+0x500,font=2):
        self.kind=kind
        self.bytes=bytearray(PRINTER_SIZE)
        self.bytes[:4]=ptr.to_bytes(4,"little")
        self.bytes[4]=0
        self.bytes[5]=font
        self.bytes[27]=active
        self.bytes[28]=state
        self.ptr=ptr
    def integer(self,address,size):
        if (address,size)!=(BOX_TYPE,1):raise AssertionError("unexpected integer")
        return self.kind
    def read(self,address,size):
        if (address,size)==(PRINTER_0,PRINTER_SIZE):return bytes(self.bytes)
        if address==self.ptr and size==1:return b"\xff"
        raise OSError("unexpected read")

def image(choice=False):
    rgb=bytearray(bytes((8,20,30))*38400)
    def rect(x,y,w,h,col):
        for yy in range(y,y+h):
            rgb[(yy*240+x)*3:(yy*240+x+w)*3]=bytes(col)*w
    rect(1,116,238,5,(206,82,0))
    rect(1,121,238,33,(255,255,255))
    rect(25,127,40,5,(30,30,30))
    rect(1,155,238,5,(45,45,55))
    if choice:
        rect(165,48,55,4,(206,82,0))
        rect(165,52,55,25,(255,255,255))
    return bytes(rgb)

class TextEngineTests(unittest.TestCase):
    def run_decide(self,live,meta=None,rgb=None):
        if meta is None:meta={}
        if rgb is None:rgb=image()
        return decide(live,rgb,meta,16*1024*1024,script_locked=True),meta
    def test_source_grounded_printer_wait_advances_without_model(self):
        live=Live(state=2)
        decision,meta=self.run_decide(live)
        self.assertEqual(decision["actions"],[{"button":"A","frames":4}])
        self.assertEqual(meta["native_text_probe"]["status"],"PRINTER_READY")
        self.assertTrue(meta["native_text_guard"]["token"])
    def test_waiting_states_handle_page_and_scroll(self):
        for state in (1,2,3):
            self.assertEqual(self.run_decide(Live(state=state))[0]["actions"][0]["button"],"A")
    def test_typing_waits_without_pressing_a(self):
        for state in (0,4,5,6):
            action,_=self.run_decide(Live(state=state))
            self.assertEqual(action["actions"],[{"button":"WAIT","frames":24}])
    def test_autoscroll_never_presses(self):
        for state in range(7):
            action,_=self.run_decide(Live(kind=3,state=state))
            self.assertEqual(action["actions"][0]["button"],"WAIT")
    def test_repeated_ready_page_is_not_blindly_confirmed(self):
        meta={}
        a,_=self.run_decide(Live(),meta)
        self.assertEqual(a["actions"][0]["button"],"A")
        b,_=self.run_decide(Live(),meta)
        self.assertIsNone(b)
        self.assertEqual(meta["native_text_probe"]["status"],"REPEATED_READY_PAGE_GUARDED")
        altered=bytearray(image())
        altered[(130*240+30)*3:(130*240+31)*3]=b"\xff\x00\x00"
        c,_=self.run_decide(Live(),meta,bytes(altered))
        self.assertEqual(c["actions"][0]["button"],"A")
    def test_choice_panel_vetoes_input(self):
        self.assertTrue(floating_choice(image(choice=True)))
        self.assertFalse(floating_choice(image()))
        decision,meta=self.run_decide(Live(),{},image(choice=True))
        self.assertIsNone(decision)
        self.assertEqual(meta["native_text_probe"]["status"],"CHOICE_OR_UNSAFE_PANEL")
    def test_no_script_or_dialogue_proof_no_action(self):
        m={}
        self.assertIsNone(decide(Live(),image(),m,16*1024*1024))
        self.assertEqual(m,{})
    def test_rejects_relocated_or_malformed_memory(self):
        for l in (Live(kind=1),Live(active=0),Live(state=7),Live(ptr=0),
                  Live(font=10),Live(ptr=ROM_BASE+0x2000000)):
            self.assertIsNone(probe(l,16*1024*1024))
    def test_unadmitted_printer_uses_one_visually_verified_page_action(self):
        meta={}
        a,_=self.run_decide(Live(kind=0),meta)
        self.assertEqual(a["scene"],"native_visual_text_advance")
        self.assertEqual(a["actions"],[{"button":"A","frames":4}])
        self.assertEqual(meta["native_text_probe"]["status"],"VISUAL_DIALOGUE_FALLBACK")
        b,_=self.run_decide(Live(kind=0),meta)
        self.assertIsNone(b)
        self.assertEqual(meta["native_text_probe"]["status"],
                         "REPEATED_VISUAL_PAGE_GUARDED")
        changed=bytearray(image())
        changed[(130*240+30)*3:(130*240+31)*3]=b"\\xff\\x00\\x00"
        c,_=self.run_decide(Live(kind=0),meta,bytes(changed))
        self.assertEqual(c["actions"],[{"button":"A","frames":4}])
        d,_=self.run_decide(Live(kind=0),meta,image(choice=True))
        self.assertIsNone(d)
        self.assertNotEqual(meta["native_text_probe"]["status"],"VISUAL_DIALOGUE_FALLBACK")

    def test_unknown_memory_state_without_visible_page_clears_guard(self):
        meta={"native_text_guard":{"token":"old"}}
        d,_=self.run_decide(Live(kind=0),meta,bytes(115200))
        self.assertIsNone(d)
        self.assertNotIn("native_text_guard",meta)
        self.assertEqual(meta["native_text_probe"]["status"],"NOT_ADMITTED")
    def test_untested_rom_extent_is_not_admitted(self):
        self.assertIsNone(probe(Live(),0))
        self.assertIsNone(probe(Live(),64*1024*1024))
    def test_no_dialogue_but_auto_box_cannot_fake_a_choice(self):
        d,_=self.run_decide(Live(kind=3,state=2))
        self.assertEqual(d["actions"][0]["button"],"WAIT")

if __name__=="__main__":unittest.main()
