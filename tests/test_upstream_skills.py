import unittest
from core.upstream_skills import SkillTransport,SkillAbort,validate_tool
from core.upstream_leafgreen.constants import Addr

class Fixture:
    def __init__(self):
        self.menu=Addr.CTRL_CHOOSE_MOVE
        self.cursor=0
        self.steps=[]
    def read(self,a,n):
        v={Addr.GMAIN_CALLBACK2:Addr.CB2_BATTLE,Addr.BATTLE_CTRL_FUNC:self.menu,
           Addr.MOVE_CURSOR:self.cursor,Addr.ACTION_CURSOR:self.cursor}.get(a,0)
        return v.to_bytes(n,"little")
    def step(self,mask,n):
        self.steps.append((mask,n))
        if mask==16:self.cursor|=1
        elif mask==32:self.cursor&=2
        elif mask==128:self.cursor|=2
        elif mask==64:self.cursor&=1
    def rgb(self):
        return bytes(115200)

class SkillTests(unittest.TestCase):
    def test_move_selection_uses_real_directions(self):
        f=Fixture();t=SkillTransport(f);t.start()
        self.assertTrue(t.write8(Addr.MOVE_CURSOR,3))
        self.assertEqual(f.steps,[(128,8),(0,8),(16,8),(0,8)])
        self.assertEqual(f.cursor,3)
    def test_wrong_menu_fails_before_input(self):
        f=Fixture();t=SkillTransport(f);f.menu=0
        with self.assertRaises(SkillAbort):t.write8(Addr.MOVE_CURSOR,2)
        self.assertFalse(f.steps)
    def test_action_menu_and_text(self):
        f=Fixture();t=SkillTransport(f);f.menu=Addr.CTRL_CHOOSE_ACTION_ALT
        self.assertTrue(t.write8(Addr.ACTION_CURSOR,1))
        f.menu=0
        steps=list(f.steps)
        self.assertTrue(t.write8(Addr.ACTION_CURSOR,0))
        self.assertEqual(steps,f.steps)
    def test_no_memory_write_or_shop_clear(self):
        t=SkillTransport(Fixture())
        with self.assertRaises(SkillAbort):t.write8(Addr.SHOP_DATA+Addr.SHOP_ITEMLIST,0)
        with self.assertRaises(SkillAbort):t.write16(0x02000000,0)
    def test_budget_and_stop(self):
        f=Fixture();t=SkillTransport(f,max_frames=20);t.start()
        with self.assertRaises(SkillAbort):t.tick(21)
        t=SkillTransport(f,should_stop=lambda:True)
        with self.assertRaises(SkillAbort):t.tap("A")
        self.assertEqual(f.steps,[])
    def test_tool_allowlist(self):
        self.assertEqual(validate_tool("use_move",{"move":"Tackle"})[0],"use_move")
        self.assertEqual(validate_tool("shop",{"item":"Potion","quantity":3})[0],"shop")
        for tool,args in [("load_state",{}),("use_move",{}),("press_button",{"button":"A","times":11}),("walk_to",{"x":1,"y":True}),("shop",{"quantity":0})]:
            with self.assertRaises(ValueError):validate_tool(tool,args)

if __name__=="__main__":
    unittest.main()
