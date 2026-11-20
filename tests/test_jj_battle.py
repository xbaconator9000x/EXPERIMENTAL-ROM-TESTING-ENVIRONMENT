import struct
import unittest
from core.jj_battle import decode_battler,pocket,inventory,move_rank,BattleAdapter,MENUS

def mon(species=19,ty=0,hp=30):
    b=bytearray(88);struct.pack_into("<6H",b,0,species,24,25,26,27,28)
    struct.pack_into("<4H",b,12,33,52,55,0)
    b[24:32]=bytes([6]*8);b[33:35]=bytes([ty,ty]);b[36:40]=bytes([10,10,10,0])
    struct.pack_into("<H",b,40,hp);b[42]=8;struct.pack_into("<H",b,44,30)
    return b

class Catalog:
    move_ids={33:{"type":"normal","power":35,"accuracy":95},52:{"type":"fire","power":40,"accuracy":100},55:{"type":"water","power":40,"accuracy":100}}

class TestBattle(unittest.TestCase):
    def test_decode_and_rank(self):
        own=decode_battler(mon());enemy=decode_battler(mon(4,10))
        self.assertEqual(move_rank(own,enemy,Catalog.move_ids),2)
        self.assertNotEqual(move_rank(own,enemy,Catalog.move_ids,disabled=55),2)
        corrupt=mon();corrupt[42]=250
        with self.assertRaises(ValueError):decode_battler(corrupt)
    def test_pocket(self):
        raw=struct.pack("<4H",4,3^123,0,123)
        self.assertEqual(pocket(raw,123),[{"id":4,"count":3}])
        with self.assertRaises(ValueError):pocket(struct.pack("<2H",4,65535),123)
    def test_witness_and_catch(self):
        a=BattleAdapter("unused","bad","classic",Catalog())
        s={"callback":0x08030611,"stage":"battle_command","cursor":0,"wild":True,
           "own":decode_battler(mon()),"enemy":decode_battler(mon(4,10,5)),
           "party":[{"species_id":19,"hp":30,"max_hp":30}],
           "bag":{"balls":[{"id":4,"count":3}],"items":[]},"disabled":0}
        m={};self.assertIsNone(a.action(s,m))
        a.corroborate(s,{"stage":"battle_command","cursor":1},m)
        self.assertIsNone(a.action(s,m))
        a.corroborate(s,{"stage":"battle_command","cursor":0},m)
        self.assertEqual(a.action(s,m)[0]["actions"][0]["button"],"RIGHT")
        self.assertEqual(a.action({**s,"wild":False},m)[0]["actions"][0]["button"],"A")
        decision,sig=a.action(s,m);m["history"]=[{"battle_signature":sig}]*2
        self.assertIsNone(a.action(s,m))
