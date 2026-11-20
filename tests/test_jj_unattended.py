import unittest
from core.jj_unattended import cycle,recovery,quarantine,quarantined,quest_state,replay
from core.live import LiveError

def history():
    return [{"before":"a" if i%2==0 else "b","after":"b" if i%2==0 else "a","scene":"hospital_room","actions":[{"button":"UP" if i%2==0 else "DOWN","frames":16}]} for i in range(12)]
class Tests(unittest.TestCase):
    def test_recovery_escapes_loop_and_caps(self):
        m={"history":history()}
        self.assertEqual(cycle(m["history"],"a"),["a","b"])
        rgb=bytes(115200)
        first=recovery(m,"a",rgb)
        self.assertIn(first["actions"][0]["button"],("LEFT","RIGHT"))
        second=recovery(m,"b",rgb)
        self.assertIn(second["actions"][0]["button"],("LEFT","RIGHT"))
        self.assertNotEqual(first["actions"][0]["button"],second["actions"][0]["button"])
        for i in range(6):self.assertIsNotNone(recovery(m,"a",rgb))
        self.assertIsNone(recovery(m,"a",rgb))
    def test_menu_not_blindly_pressed(self):
        h=history();h[-1]["observed_stage"]="menu"
        self.assertIsNone(recovery({"history":h},"a",bytes(115200)))
    def test_quarantine_exact_input(self):
        m={};a=[{"button":"A","frames":5}];quarantine(m,"a",a)
        self.assertTrue(quarantined(m,"a",a));self.assertFalse(quarantined(m,"b",a))
    def test_objective_verified_party(self):
        m={};q=quest_state(m,None,None,{"fact":"meet Jessie"},"find exit")
        self.assertEqual(q["phase"],"obtain_initial_party")
        quest_state(m,None,[{"hp":10,"max_hp":10}])
        self.assertEqual(q["phase"],"explore_and_advance_story")
        quest_state(m,None,[{"hp":1,"max_hp":10}])
        self.assertEqual(q["phase"],"restore_party_health")
    def test_replay_classifies_failure(self):
        class Live:
            def step(self,*a):raise LiveError("transport")
            def close(self):pass
        self.assertEqual(replay(lambda s:Live(),b"x",[{"button":"A","frames":5}],24,{"A":1})[0],"REPLAY_FAILED")
        def broken(s):raise LiveError("setup")
        self.assertEqual(replay(broken,b"x",[],24,{})[0],"REPLAY_SETUP_FAILED")

    def test_native_bootstrap_bounded(self):
        from core.jj_unattended import bootstrap
        from core.firered import Field
        f=Field((1,2),(2,2),5,5,(0,)*25)
        m={"history":history()}
        self.assertEqual(len({bootstrap(m,(f,123,set()),"a")["actions"][0]["button"] for _ in range(4)}),4)
        self.assertIsNone(bootstrap(m,(f,123,set()),"a"))
    def test_replay_success_returns_state_and_rgb(self):
        class Live:
            def step(self,*a):pass
            def close(self):pass
            def save_state(self):return b"state"
            def rgb(self):return bytes(115200)
        status,result=replay(lambda s:Live(),b"x",[{"button":"A","frames":5}],24,{"A":1})
        self.assertEqual(status,"REPLAY_SUCCEEDED")
        self.assertEqual(result[0],b"state")
