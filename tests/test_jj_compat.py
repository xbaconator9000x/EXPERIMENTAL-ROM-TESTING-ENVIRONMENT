import unittest
from core.firered import Field
from core.jj_fast import MAP_HEADER
from core.jj_compat import inspect_map,safe_map_audit,ROM_BASE

def word(raw,offset,value,size=4):
    raw[offset:offset+size]=value.to_bytes(size,"little")

class FakeLive:
    def __init__(self):
        self.rom=bytearray(4096);self.header=bytearray(28)
        word(self.header,4,ROM_BASE+0x100)
        self.rom[0x100:0x104]=bytes((1,1,1,1))
        for off,p in ((0x104,0x200),(0x108,0x300),(0x10c,0x400),(0x110,0x500)):
            word(self.rom,off,ROM_BASE+p)
        word(self.rom,0x210,ROM_BASE+0x600)
        word(self.rom,0x300,4,2);word(self.rom,0x302,2,2)
        word(self.rom,0x400,5,2);word(self.rom,0x402,6,2)
        word(self.rom,0x40c,ROM_BASE+0x600)
        word(self.rom,0x500,7,2);word(self.rom,0x502,8,2)
        word(self.rom,0x508,ROM_BASE+0x600)
    def read(self,a,n):
        if a==MAP_HEADER and n==28:return bytes(self.header)
        p=a-ROM_BASE
        if 0<=p and p+n<=len(self.rom):return bytes(self.rom[p:p+n])
        raise OSError("out of range")

class RomHackMapAuditTests(unittest.TestCase):
    def setUp(self):
        self.live=FakeLive()
        self.field=Field((43,1),(4,3),12,12,(0,)*144)
    def read(self):
        return inspect_map(self.live,4096,self.field)
    def test_vanilla_structures_not_story_claim(self):
        r=self.read()
        self.assertEqual(r["counts"],dict(objects=1,warps=1,coordinates=1,backgrounds=1))
        self.assertEqual(r["checked_script_pointers"],3)
        self.assertEqual(r["status"],"STRUCTURALLY_READABLE")
        self.assertFalse(r["script_semantics_verified"])
        self.assertFalse(r["gameplay_compatibility_verified"])
    def test_hidden_item_union_not_false_pointer(self):
        self.live.rom[0x505]=7;word(self.live.rom,0x508,0xffffffff)
        self.assertEqual(self.read()["hidden_items"],1)
        self.assertEqual(self.read()["checked_script_pointers"],2)
    def test_relocated_script_pointer_allowed_if_rom_backed(self):
        for offset in (0x210,0x40c,0x508):word(self.live.rom,offset,ROM_BASE+0x9a0)
        self.assertEqual(self.read()["checked_script_pointers"],3)
    def test_invalid_pointer_fails_without_leakage(self):
        word(self.live.rom,0x40c,ROM_BASE+0x7000)
        r=safe_map_audit(self.live,4096,self.field)
        self.assertEqual(r["reason"],"INVALID_ROM_POINTER")
        self.assertNotIn("0x",str(r))
    def test_invalid_warp_or_count_rejected(self):
        word(self.live.rom,0x300,99,2)
        self.assertEqual(safe_map_audit(self.live,4096,self.field)["reason"],
                         "INVALID_EVENT_COORDINATE")
        self.live.rom[0x101]=90
        self.assertEqual(safe_map_audit(self.live,4096,self.field)["reason"],
                         "INVALID_EVENT_COUNT")
    def test_custom_event_kind_unclassified_not_assumed(self):
        self.live.rom[0x505]=55
        r=self.read()
        self.assertEqual(r["status"],"UNCLASSIFIED_EVENT_KINDS")
        self.assertEqual(r["unknown_event_kinds"],1)
    def test_map_script_table(self):
        word(self.live.header,8,ROM_BASE+0x700)
        self.live.rom[0x700]=1;word(self.live.rom,0x701,ROM_BASE+0x600)
        self.assertEqual(self.read()["map_script_entries"],1)
        word(self.live.rom,0x701,0x70000000)
        self.assertEqual(safe_map_audit(self.live,4096,self.field)["reason"],
                         "INVALID_ROM_POINTER")

    def test_frame_table_is_conditional_var_pairs_not_direct_script(self):
        # Source: pret/pokefirered src/script.c MapHeaderCheckScriptTable.
        word(self.live.header,8,ROM_BASE+0x700)
        self.live.rom[0x700]=2
        word(self.live.rom,0x701,ROM_BASE+0x800)
        word(self.live.rom,0x800,0x4020,2)
        word(self.live.rom,0x802,1,2)
        word(self.live.rom,0x804,ROM_BASE+0x600)
        # 0x808 zero terminator, so one conditional row.
        result=self.read()
        self.assertEqual(result["map_script_entries"],1)
        self.assertEqual(result["conditional_map_script_entries"],1)
        self.assertEqual(result["checked_script_pointers"],4)

    def test_prefix_intents_aggregated_without_private_script_contents(self):
        self.live.rom[0x600:0x607]=bytes((0x69,0x67,0,0,0,0,0x02))
        result=self.read()
        self.assertGreaterEqual(result["script_prefixes_sampled"],1)
        self.assertGreaterEqual(result["script_graph_segments_scanned"],1)
        self.assertGreaterEqual(result["possible_script_intents"].get("dialogue_or_wait",0),1)
        self.assertFalse(result["gameplay_compatibility_verified"])
        self.assertNotIn("0x080",str(result))
        self.assertNotIn("script_bytes",str(result))

if __name__=="__main__":unittest.main()