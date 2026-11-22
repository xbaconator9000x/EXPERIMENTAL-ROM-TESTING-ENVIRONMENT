import unittest
from core.jj_unattended import cycle,oscillation,recovery,quarantine,quarantined,quest_state,replay
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
    def test_stale_dialogue_label_cannot_disable_proved_navigation_recovery(self):
        # Reproduce campaign #23 around decision 174: visually two different
        # overworld positions but the vision model keeps the obsolete
        # "native_dialogue" scene label and alternates UP/DOWN indefinitely.
        h=[]
        for i in range(12):
            h.append({"before":"a" if i%2==0 else "b",
                      "after":"b" if i%2==0 else "a",
                      "scene":"native_dialogue",
                      "observed_stage":"dialogue",
                      "actions":[{"button":"DOWN" if i%2==0 else "UP","frames":16}]})
        self.assertFalse(__import__("core.jj_unattended",fromlist=["field_hint"]).field_hint(h))
        loop=oscillation(h,"a")
        self.assertEqual(loop["avoid_button"],"DOWN")
        self.assertEqual(loop["repetitions"],6)
        # Without an independent native movement witness, the stale label
        # cannot authorize blind controls in a potentially interactive menu.
        self.assertIsNone(recovery({"history":h},"a",bytes(115200)))
        meta={"history":h,"field_proof":{"callback":0x08001235,"directions":["LEFT"]}}
        decision=recovery(meta,"a",bytes(115200))
        self.assertIsNotNone(decision)
        self.assertIn(decision["actions"][0]["button"],("LEFT","RIGHT"))
        self.assertNotIn(decision["actions"][0]["button"],("UP","DOWN"))
        self.assertEqual(len(meta["recovery"]["attempts"]),1)

    def test_oscillation_requires_real_directional_transitions(self):
        h=[{"before":"a" if i%2==0 else "b","after":"b" if i%2==0 else "a",
            "actions":[{"button":"DOWN" if i%2==0 else "UP","frames":16}]}
           for i in range(8)]
        self.assertIsNotNone(oscillation(h,"a"))
        self.assertIsNone(oscillation(h[:5],"b"))
        self.assertIsNone(oscillation([{**r,"actions":[{"button":"A","frames":5}]} for r in h],"a"))
        self.assertIsNone(oscillation([{**r,"before":r["after"]} for r in h],"a"))
        self.assertIsNone(oscillation(h,"unrelated"))
        # Having a native witness does not justify skipping real dialogue.
        from unittest.mock import patch
        with patch("core.jj_unattended.ordinary_dialogue",return_value="page"):
            self.assertIsNone(recovery({"history":h,
                "field_proof":{"callback":0x08001235,"directions":["LEFT"]}},"a",bytes(115200)))

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
    def test_quest_notebook_separates_model_hypotheses_from_witnessed_progress(self):
        meta={}
        q=quest_state(meta,None,None,{"fact":"I think the rocket ship sank"},"Find the ship")
        self.assertEqual(q["fact_source"],"model_hypothesis_not_a_verified_story_flag")
        self.assertEqual(q["task_source"],"planner_proposal")
        self.assertEqual(q["milestones"],[])
        meta["party_knowledge"]={"verified_outcomes":[
            {"kind":"wild_capture","decision":12},
            {"kind":"battle_win","decision":15},
            {"kind":"healing","decision":21},
            {"kind":"fake_ending","decision":22},
        ]}
        meta["world_model"]={"skill_outcomes":[{"task":"exit","result":"native_verified"}]}
        q=quest_state(meta,None,None)
        self.assertIn("capture_observed",q["milestones"])
        self.assertIn("battle_win_observed",q["milestones"])
        self.assertIn("native_exit_observed",q["milestones"])
        self.assertNotIn("ending_verified",q["milestones"])
        n=len(q["milestones"])
        self.assertEqual(len(quest_state(meta,None,None)["milestones"]),n)

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
    def test_stale_title_label_cannot_mask_verified_native_field(self):
        from core.jj_unattended import bootstrap
        from core.firered import Field
        f=Field((1,2),(2,2),5,5,(0,)*25)
        rows=[{"scene":"title_screen","actions":[{"button":"START","frames":16}],
               "before":"a","after":"a"} for _ in range(3)]
        self.assertIsNotNone(bootstrap({"history":rows},(f,123,set()),"a"))
        rows[-1]["scene"]="battle_command"
        self.assertIsNone(bootstrap({"history":rows},(f,123,set()),"a"))
        self.assertIsNone(bootstrap({"history":rows},None,"a"))

    def test_replay_success_returns_state_and_rgb(self):
        class Live:
            def step(self,*a):pass
            def close(self):pass
            def save_state(self):return b"state"
            def rgb(self):return bytes(115200)
        status,result=replay(lambda s:Live(),b"x",[{"button":"A","frames":5}],24,{"A":1})
        self.assertEqual(status,"REPLAY_SUCCEEDED")
        self.assertEqual(result[0],b"state")
