import unittest
from unittest.mock import patch
from core.gen3_profiles import PROFILES,FIRERED,LEAFGREEN,FIRERED_REV1,LEAFGREEN_REV1,EMERALD,RUBY,SAPPHIRE,identify,party_snapshot,VanillaBattle
from core.jj_battle import decode_battler
import struct
def mon(species=19,ty=0):
    b=bytearray(88);struct.pack_into("<6H",b,0,species,24,25,26,27,28)
    struct.pack_into("<4H",b,12,33,52,55,0)
    b[24:32]=bytes([6]*8);b[33:35]=bytes([ty,ty]);b[36:40]=bytes([10,10,10,0])
    struct.pack_into("<H",b,40,30);b[42]=8;struct.pack_into("<H",b,44,30)
    return b

class Memory:
    def __init__(self,p,sha="0"*64):
        self.p=p;self.sha256=sha;self.values={}
    def integer(self,a,n):return int.from_bytes(self.read(a,n),"little")
    def read(self,a,n):return self.values.get(a,b"\0"*n)
    def set(self,a,v,n):self.values[a]=v.to_bytes(n,"little")

class Gen3ProfilesTests(unittest.TestCase):
    def test_profiles_are_revision_scoped(self):
        self.assertEqual(len({p.sha1 for p in PROFILES}),7)
        self.assertEqual(FIRERED.party,LEAFGREEN.party)
        self.assertNotEqual(FIRERED.field_cb,FIRERED_REV1.field_cb)
        self.assertNotEqual(FIRERED.party,EMERALD.party)
        self.assertIsNone(identify(b"\0"*16*1024*1024,"0"*64))
    def test_battle_context_and_party_gate(self):
        for p in PROFILES:
            m=Memory(p);a=VanillaBattle(p,m.sha256,None)
            self.assertIsNone(a.snapshot(m))
            m.set(p.main+4,p.battle_cb,4)
            m.set(p.controllers,p.command_cb,4);m.set(p.flags,4,4)
            m.values[p.battlers]=bytes(mon()+mon(4,10))
            with patch("core.gen3_profiles.party_snapshot",return_value=[{"species_id":19,"level":8,"max_hp":30}]):
                x=a.snapshot(m)
                self.assertIsNotNone(x,p.name)
                self.assertEqual(x["stage"],"battle_command")
                self.assertTrue(x["wild"])
                m.set(p.flags,20,4);self.assertFalse(a.snapshot(m)["wild"])
                m.set(p.flags,5,4);self.assertIsNone(a.snapshot(m))
    def test_party_count_is_independent_witness(self):
        m=Memory(EMERALD);m.set(EMERALD.party_count,1,1)
        with self.assertRaises(ValueError):party_snapshot(m,EMERALD)

    def test_fixed_save_inventory(self):
        from core.gen3_profiles import bag_snapshot
        for p in (RUBY,SAPPHIRE):
            m=Memory(p)
            m.set(p.save1+p.money,1234,4)
            m.values[p.save1+p.items]=struct.pack("<HH",13,2)+bytes((p.item_count-1)*4)
            m.values[p.save1+p.balls]=struct.pack("<HH",4,5)+bytes((p.ball_count-1)*4)
            self.assertEqual(bag_snapshot(m,p),{"money":1234,"items":[{"id":13,"count":2}],"balls":[{"id":4,"count":5}]})
            m.set(p.party_count,256,4)
            with self.assertRaises(ValueError):party_snapshot(m,p)
    def test_alternate_controller_is_profile_specific(self):
        for p in (FIRERED,LEAFGREEN,FIRERED_REV1,LEAFGREEN_REV1):
            m=Memory(p);a=VanillaBattle(p,m.sha256,None)
            m.set(p.main+4,p.battle_cb,4);m.set(p.controllers,p.alternate_command_cb,4);m.set(p.flags,4,4)
            m.values[p.battlers]=bytes(mon()+mon(4,10))
            with patch("core.gen3_profiles.party_snapshot",return_value=[{"species_id":19,"level":8,"max_hp":30}]):
                self.assertEqual(a.snapshot(m)["stage"],"battle_command")
    def test_emerald_battle_bag(self):
        from core.jj_menus import decode_emerald_bag,MenuDriver
        bag={"items":[{"id":13,"count":2}],"balls":[{"id":4,"count":5}]}
        raw=bytearray(28);raw[4]=1;raw[5]=1
        self.assertEqual(decode_emerald_bag(raw,bag)["pocket"],2)
        raw[4]=0
        with self.assertRaises(ValueError):decode_emerald_bag(raw,bag)
        a=VanillaBattle(EMERALD,"0"*64,None);d=MenuDriver("unused","0"*64,a)
        self.assertTrue(d.bag_ok);self.assertTrue(d.party_ok)
        m=Memory(EMERALD)
        intent={"menu_intent":{"phase":"list","purpose":"catch","remaining":3}}
        m.set(EMERALD.main+4,EMERALD.bag_cb,4);raw[4]=1;m.values[EMERALD.bag_base]=bytes(raw)
        with patch.object(a,"bag",return_value=bag):
            self.assertEqual(d.snapshot(m,intent)["rows"],bag["balls"])
            m.set(EMERALD.main+4,EMERALD.bag_cb+2,4)
            self.assertIsNone(d.snapshot(m,intent))
