import unittest
from core.firered import Field
from core.jj_event_data import (EventData,read_event_data,safe_event_data,
                                transition_counts,FLAGS_LENGTH,VARS_LENGTH)
from core.jj_fast import SAVE_PTR

SAVE=0x02004000

class FakeSave:
    def __init__(self):
        self.memory=bytearray(0x2000)
        self.memory[:8]=bytes((4,0,3,0,43,1,0,0))
        self.memory[0xEE0+0x201//8]|=1<<(0x201&7)
        self.memory[0x1000:0x1002]=bytes((8,0))
        self.pointer=SAVE
    def integer(self,addr,n):
        if addr!=SAVE_PTR or n!=4:raise AssertionError("wrong pointer read")
        return self.pointer
    def read(self,addr,n):
        p=addr-SAVE
        if p<0 or p+n>len(self.memory):raise OSError("outside allocation")
        return bytes(self.memory[p:p+n])

class EventDataTests(unittest.TestCase):
    def setUp(self):
        self.live=FakeSave()
        self.field=Field((43,1),(4,3),12,12,(0,)*144)
    def test_exact_stock_offsets_and_bit_semantics(self):
        s=read_event_data(self.live,self.field)
        self.assertTrue(s.flag(0x201))
        self.assertFalse(s.flag(0x202))
        self.assertEqual(s.var(0x4000),8)
        self.assertEqual(s.var(0x4001),0)
        self.assertEqual(len(s.flags),FLAGS_LENGTH)
        self.assertEqual(len(s.variables),VARS_LENGTH)
    def test_special_or_out_of_bounds_flag_var_rejected(self):
        s=read_event_data(self.live,self.field)
        for index in (0,-1,0x900,0x4000):
            with self.subTest(flag=index),self.assertRaises(ValueError):s.flag(index)
        for index in (0x3FFF,0x4100,0x8000):
            with self.subTest(var=index),self.assertRaises(ValueError):s.var(index)
    def test_wrong_map_position_or_invalid_pointer_rejected(self):
        self.live.pointer=0x0203ff00
        self.assertEqual(safe_event_data(self.live,self.field)["reason"],"SAVE_POINTER_INVALID")
        self.live.pointer=SAVE
        wrong=Field((43,2),(4,3),12,12,(0,)*144)
        self.assertEqual(safe_event_data(self.live,wrong)["reason"],"FIELD_IDENTITY_MISMATCH")
    def test_rejects_unreadable_event_data(self):
        def bad_read(addr,n):
            return bytes(8) if n==8 else b"\x00"
        self.live.read=bad_read
        self.assertEqual(safe_event_data(self.live,self.field)["reason"],"FIELD_IDENTITY_MISMATCH")
    def test_different_maps_are_not_attributed_as_same_event(self):
        a=read_event_data(self.live,self.field)
        other=EventData((43,2),a.flags,a.variables)
        self.assertEqual(transition_counts(a,other)["status"],
                         "DIFFERENT_MAPS_NO_COMPARISON")

    def test_delta_counts_do_not_claim_story_event(self):
        a=read_event_data(self.live,self.field)
        self.live.memory[0xEE0+0x202//8]|=1<<(0x202&7)
        self.live.memory[0xEE0+0x201//8]&=~(1<<(0x201&7))
        self.live.memory[0x1002]=1
        b=read_event_data(self.live,self.field)
        r=transition_counts(a,b)
        self.assertEqual((r["flags_raised"],r["flags_cleared"],r["variables_changed"]),(1,1,1))
        self.assertFalse(r["story_completion_verified"])
    def test_aggregates_only_and_no_sensitive_state_in_diagnostics(self):
        r=safe_event_data(self.live,self.field)
        self.assertEqual(r["status"],"STOCK_SAVE_LAYOUT_CANDIDATE")
        self.assertEqual(r["flags_set"],1)
        self.assertEqual(r["nonzero_variables"],1)
        self.assertNotIn("pointer",r)
        self.assertNotIn("raw",r)
        self.assertFalse(r["story_completion_verified"])

if __name__=="__main__":unittest.main()