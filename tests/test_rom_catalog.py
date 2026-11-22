import unittest
from core.rom_catalog import Catalog, decode_name, TYPES, TABLES, SPECIES_NAMES, MOVE_NAMES, SPECIES_DATA, MOVE_DATA, SPECIES_ANCHORS, MOVE_ANCHORS
from core.gameplay import clean_observation, best_move

def encode(s,size):
    raw=bytes(0 if c==" " else 0xBB+ord(c)-65 for c in s)+b"\xff"
    return raw.ljust(size,b"\x00")

def fixture():
    rom=bytearray(0x260000);rom[0xAC:0xB0]=b"BPRE"
    for i,x in enumerate(TABLES):rom[0x1000+i*4:0x1004+i*4]=(0x08000000+x).to_bytes(4,"little")
    for i,(name,types) in SPECIES_ANCHORS.items():
        off=SPECIES_NAMES+i*11;rom[off:off+11]=encode(name,11)
        off=SPECIES_DATA+i*28;rom[off:off+6]=bytes([50]*6)
        a=TYPES.index(types[0]);b=TYPES.index(types[-1]);rom[off+6:off+8]=bytes([a,b])
    for i,(name,t) in MOVE_ANCHORS.items():
        off=MOVE_NAMES+i*13;rom[off:off+13]=encode(name,13)
        off=MOVE_DATA+i*12;rom[off:off+5]=bytes([0,40,TYPES.index(t),100,15])
    return rom

class CatalogTests(unittest.TestCase):
    def test_exact_data_and_current_pp(self):
        c=Catalog(fixture())
        o=clean_observation({"stage":"battle_moves","cursor":0,"enemy":"CHARMANDER","own":"SQUIRTLE","moves":[{"slot":0,"name":"Tackle","pp":10},{"slot":1,"name":"Water Gun","pp":5},{"slot":2,"name":"Thunderbolt"}]})
        o=c.enrich(o)
        self.assertEqual(o["enemy_types"],["fire"])
        self.assertEqual(c.species_ids[7]["types"],["water"])
        self.assertEqual(c.species_ids[25]["name"],"PIKACHU")
        self.assertEqual(best_move(o)["name"],"Water Gun")
        self.assertNotIn("pp",o["moves"][2])
    def test_anchors_fail_closed(self):
        r=fixture();r[0x1000:0x1004]=b"\0"*4
        with self.assertRaises(ValueError):Catalog(r)
        r=fixture();r[MOVE_DATA+12+2]=10
        with self.assertRaises(ValueError):Catalog(r)
