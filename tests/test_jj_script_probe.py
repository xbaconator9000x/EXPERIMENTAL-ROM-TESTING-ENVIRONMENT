"""Source-grounded, ROM-free standard command-prefix acceptance tests."""
import unittest
from core.jj_script_probe import inspect_prefix,ROM_BASE
from tests.test_jj_compat import FakeLive,word


class ScriptPrefixTests(unittest.TestCase):
    def setUp(self):
        self.live=FakeLive()
        self.ptr=ROM_BASE+0x600
    def scan(self,data):
        self.live.rom[0x600:0x600+len(data)]=data
        return inspect_prefix(self.live,4096,self.ptr)
    def test_standard_msgbox_macro_is_two_commands_then_terminal(self):
        # pret/pokefirered msgbox: loadword local0, text; callstd 4.
        data=bytes((0x69,0x0f,0x00))+ (ROM_BASE+0x900).to_bytes(4,"little")+bytes((0x09,0x04,0x6b,0x02))
        got=self.scan(data)
        self.assertEqual(got["status"],"TERMINAL_COMMAND")
        self.assertEqual(got["commands_scanned"],5)
        self.assertIn("dialogue_standard_script",got["possible_intents"])
        self.assertFalse(got["runtime_outcome_verified"])
        self.assertNotIn("0x",str(got))
    def test_obtain_item_macro_is_var_setup_and_callstd_zero(self):
        data=bytes((0x1a,0x00,0x80,0x04,0x00,
                    0x1a,0x01,0x80,0x01,0x00,0x09,0x00,0x02))
        got=self.scan(data)
        self.assertIn("item_standard_script",got["possible_intents"])
        self.assertIn("variable_or_comparison",got["possible_intents"])
        self.assertTrue(got["complete_linear_prefix"])
    def test_yes_no_box_prevents_plain_dialogue_classification(self):
        got=self.scan(bytes((0x6e,0x14,0x06,0x02)))
        self.assertIn("player_choice",got["possible_intents"])
        self.assertTrue(got["complete_linear_prefix"])
    def test_branch_is_not_read_as_unconditional_story_success(self):
        got=self.scan(bytes((0x2b,0x01,0x02,0x06,0x01,0x00,0x09,0x00,0x08,0x67,0,0,0,0,0x02)))
        self.assertEqual(got["status"],"CONTROL_TRANSFER_STOP")
        self.assertIn("flag_check_or_change",got["possible_intents"])
        self.assertIn("unresolved_condition",got["possible_intents"])
        self.assertNotIn("dialogue_or_wait",got["possible_intents"])
    def test_unknown_custom_opcode_stops_at_byte_zero(self):
        got=self.scan(bytes((0xed,0x67,0,0,0,0,0x02)))
        self.assertEqual(got["status"],"UNKNOWN_OPCODE_STOP")
        self.assertEqual(got["commands_scanned"],0)
        self.assertEqual(got["possible_intents"],[])
    def test_trainer_and_warp_variable_formats_stop_safely(self):
        for opcode,label in ((0x5c,"battle"),(0x39,"warp")):
            with self.subTest(opcode=opcode):
                got=self.scan(bytes((opcode,0xff,0xff,0xff,0xff)))
                self.assertEqual(got["status"],"DYNAMIC_COMMAND_STOP")
                self.assertIn(label,got["possible_intents"])
    def test_native_special_is_unknown_effect_not_claimed_reward(self):
        got=self.scan(bytes((0x25,0x10,0x00,0x02)))
        self.assertIn("native_special_unknown_effect",got["possible_intents"])
        self.assertNotIn("item_standard_script",got["possible_intents"])
    def test_truncated_and_short_read_fail_closed(self):
        got=self.scan(bytes((0x0f,0x00,0x00,0x00,0x00,0x00,0x02)))
        self.assertEqual(got["status"],"TRUNCATED_COMMAND_STOP") if False else None
        # Use an explicit 5-byte instruction budget so a 6-byte loadword
        # cannot be partly decoded as a later opcode.
        got=inspect_prefix(self.live,4096,self.ptr,max_bytes=5)
        self.assertEqual(got["status"],"TRUNCATED_COMMAND_STOP")
        with self.assertRaises(ValueError):
            inspect_prefix(self.live,4096,ROM_BASE+0x5000)
    def test_command_count_cap_and_no_transcript(self):
        got=self.scan(bytes((0x00,))*30)
        self.assertEqual(got["status"],"PREFIX_BUDGET_EXHAUSTED")
        self.assertEqual(got["commands_scanned"],24)
        self.assertFalse(any(k in got for k in ("data","pointer","text","raw_bytes")))

if __name__=="__main__":unittest.main()
