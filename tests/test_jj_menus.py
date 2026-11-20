import unittest,struct
from core.jj_menus import select_item,decode_order,decode_bag,intent_from_battle,MenuDriver

class Menus(unittest.TestCase):
    def test_item_selection(self):
        b={"items":[{"id":13,"count":3},{"id":22,"count":2},{"id":19,"count":1}],"balls":[{"id":1,"count":1},{"id":4,"count":5},{"id":3,"count":2}]}
        self.assertEqual(select_item(b,"heal",18),13)
        self.assertEqual(select_item(b,"heal",40),22)
        self.assertEqual(select_item(b,"catch"),3)
        self.assertIsNone(select_item(b,"heal",0))
    def test_decoding(self):
        self.assertEqual(decode_order(bytes([1,35,69])),[0,1,2,3,4,5])
        with self.assertRaises(ValueError):decode_order(bytes(3))
        raw=bytearray(20);raw[4:6]=bytes([5,1]);struct.pack_into("<H",raw,6,2)
        struct.pack_into("<H",raw,12,1)
        b={"items":[],"balls":[{"id":4,"count":5},{"id":3,"count":2}]}
        self.assertEqual(decode_bag(raw,b)["cursor"],1)
        raw[5]=0
        with self.assertRaises(ValueError):decode_bag(raw,b)
    def test_menu_intent_and_witness(self):
        s={"stage":"battle_command","cursor":1,"wild":True,"own":{"species":19,"hp":5,"max_hp":20},"bag":{"items":[],"balls":[{"id":4,"count":5},{"id":3,"count":2}]},"party":[]}
        d={"objective":"Open bag to catch a new wild Pokémon","actions":[{"button":"A","frames":5}]}
        intent=intent_from_battle(s,d);self.assertEqual(intent["item"],3)
        self.assertIsNone(intent_from_battle({**s,"wild":False},d))
        m={"menu_intent":intent};drv=MenuDriver("unused","wrong",None)
        bag={"stage":"bag","callback":123,"pocket":2,"cursor":0,"rows":s["bag"]["balls"]}
        self.assertIsNone(drv.action(bag,m))
        drv.corroborate(bag,{"stage":"bag","list_cursor":0,"items":[{"slot":0,"name":"Potion","count":5}]},m)
        self.assertIsNone(drv.action(bag,m))
        drv.corroborate(bag,{"stage":"bag","list_cursor":0,"items":[{"slot":0,"name":"Poké Ball","count":5}]},m)
        d,_=drv.action(bag,m);self.assertEqual(d["actions"][0]["button"],"DOWN")
        after={**bag,"cursor":1};drv.finish(m,bag,after,d)
        d,_=drv.action(after,m);self.assertEqual(d["actions"][0]["button"],"A")
        drv.finish(m,after,None,d)
        self.assertIsNone(drv.action(after,m))
    def test_party_requires_new_visual_witness(self):
        drv=MenuDriver("unused","wrong",None)
        m={"menu_intent":{"purpose":"switch","slot":2,"phase":"list","remaining":5}}
        s={"stage":"party","callback":123,"cursor":1,"target":2,"count":3}
        self.assertIsNone(drv.action(s,m))
        drv.corroborate(s,{"stage":"party","list_cursor":1},m)
        self.assertEqual(drv.action(s,m)[0]["actions"][0]["button"],"DOWN")
        self.assertIsNone(drv.action({**s,"cursor":0},m))
