import unittest
from core.jj_unattended import cycle,oscillation,recovery,quarantine,quarantined,quest_state,replay
from core.live import LiveError

def history():
    return [{"before":"a" if i%2==0 else "b","after":"b" if i%2==0 else "a","scene":"hospital_room","actions":[{"button":"UP" if i%2==0 else "DOWN","frames":16}]} for i in range(12)]
class Tests(unittest.TestCase):
    def test_sparse_strategic_referrals_have_map_party_budget(self):
        from core.jj_unattended import field_strategic_referral
        from core.firered import Field
        field=(Field((43,1),(4,2),8,8,(0,)*64),0x08001235,set())
        meta={"native_party_count":3}
        self.assertEqual([field_strategic_referral(meta,field) for _ in range(4)],
                         [True,True,False,False])
        self.assertEqual(meta["field_strategic_referral"]["calls"],2)
        meta["native_party_count"]=4
        self.assertTrue(field_strategic_referral(meta,field))

    def test_exceptional_vision_never_controls_native_field_and_is_bounded(self):
        from core.firered import Field
        from core.jj_unattended import exceptional_vision
        field=(Field((43,1),(4,2),6,6,(0,)*36),0x08001235,set())
        meta={"last_native_field":{"map":[43,1],"pos":[4,2]},"native_party_count":3}
        self.assertFalse(exceptional_vision(meta,field,"FIELD_STRUCTURES_VALID"))
        self.assertEqual([exceptional_vision(meta,None,"UNKNOWN") for _ in range(3)],
                         [True,False,False])
        # Flicker changes the screenshot, not the underlying scene/epoch.
        self.assertTrue(exceptional_vision(meta,None,"UNKNOWN",menu=True))
        self.assertFalse(exceptional_vision(meta,field,"FIELD_STRUCTURES_VALID"))
        meta["last_native_field"]["pos"]=[5,2]
        self.assertFalse(exceptional_vision(meta,None,"UNKNOWN"))
        meta["last_native_field"]["map"]=[43,2]
        self.assertTrue(exceptional_vision(meta,None,"UNKNOWN"))

    def test_verified_map_caps_expensive_vision_fallback(self):
        from core.firered import Field
        from core.jj_unattended import native_vision_budget
        one=(Field((43,1),(3,3),8,8,(0,)*64),0x08001235,set())
        meta={"native_party_count":1}
        self.assertEqual([native_vision_budget(meta,one) for _ in range(5)],
                         [True,True,True,False,False])
        moved=(Field((43,1),(4,3),8,8,(0,)*64),0x08001235,set())
        self.assertFalse(native_vision_budget(meta,moved))
        meta["native_party_count"]=2
        self.assertTrue(native_vision_budget(meta,moved))
        next_map=(Field((43,2),(1,1),8,8,(0,)*64),0x08001235,set())
        self.assertTrue(native_vision_budget(meta,next_map))

    def test_script_lock_waits_are_noninteractive_bounded_and_checkpointed(self):
        from core.jj_unattended import script_settle
        meta={}
        first=script_settle(meta,"script-warning")
        self.assertEqual(first["scene"],"native_script_settle")
        self.assertEqual(first["actions"],[{"button":"WAIT","frames":24}])
        self.assertEqual(script_settle(meta,"script-warning")["actions"],
                         [{"button":"WAIT","frames":24}])
        self.assertEqual(script_settle(meta,"script-warning")["actions"],
                         [{"button":"WAIT","frames":24}])
        self.assertIsNone(script_settle(meta,"script-warning"))
        self.assertEqual(meta["script_settle"]["same_screen"],3)
        # A new frame can legitimately be another step of a script, but
        # the total budget cannot be extended forever by animation frames.
        for i in range(5):
            self.assertIsNotNone(script_settle(meta,f"animated-{i}"))
        self.assertIsNone(script_settle(meta,"animated-5"))
        self.assertEqual(meta["script_settle"]["total"],8)

    def test_starter_vision_budget_parks_no_progress_instead_of_burning_gpu(self):
        from core.jj_unattended import vision_stall
        from core.firered import Field
        f=Field((43,1),(6,7),12,12,(0,)*144)
        field=(f,0x08001235,set())
        meta={"objective_state":{"phase":"obtain_initial_party"},"history":[]}
        for i in range(7):
            meta["history"].append({"source":"vision_compact","actions":[{"button":"UP","frames":16}],"field_after":{"map":[43,1],"pos":[6,i]}})
        self.assertFalse(vision_stall(meta,field))
        meta["history"].append({"source":"vision_rich","actions":[{"button":"DOWN","frames":16}],"field_after":{"map":[43,1],"pos":[6,8]}})
        self.assertTrue(vision_stall(meta,field))
        meta["history"].append({"source":"vision_rich","observed_stage":"dialogue","actions":[{"button":"A","frames":5}],"field_after":{"map":[43,1],"pos":[6,8]}})
        self.assertFalse(vision_stall(meta,field))
        meta["history"].pop()
        meta["history"].append({"source":"native_explore","field_after":{"map":[43,1],"pos":[7,8]}})
        self.assertFalse(vision_stall(meta,field))
        meta["history"].pop()
        meta["history"].append({"source":"vision_compact","field_after":{"map":[43,2],"pos":[0,0]}})
        self.assertFalse(vision_stall(meta,field))
        meta["history"].pop()
        meta["objective_state"]["phase"]="explore_and_advance_story"
        self.assertTrue(vision_stall(meta,field))

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
        self.assertIn("Poké Ball",q["task"])
        self.assertEqual(q["task_source"],"campaign_priority_pending_native_party_witness")
        quest_state(m,None,[{"hp":10,"max_hp":10}])
        self.assertEqual(q["phase"],"explore_and_advance_story")
        quest_state(m,None,[{"hp":1,"max_hp":10}])
        self.assertEqual(q["phase"],"restore_party_health")
    def test_native_skill_actions_do_not_replace_story_goal(self):
        meta={}
        q=quest_state(meta,None,None)
        self.assertIn("Poké Ball",q["task"])
        q=quest_state(meta,None,[{"hp":20,"max_hp":20}])
        self.assertEqual(q["task"],"Find the next verified story interaction or map exit.")
        self.assertEqual(q["task_source"],"campaign_priority_after_party")
        for objective in ("Survey a new native-verified walkable tile",
                          "Approach observed warp",
                          "Walk onto observed trigger",
                          "Re-enter previously attempted native trigger",
                          "Native-validated last-resort visual step"):
            q=quest_state(meta,None,None,objective=objective)
            self.assertEqual(q["task"],"Find the next verified story interaction or map exit.")
        # A genuine strategic proposal remains distinguishable and intact
        # when followed by the native movement needed to execute it.
        q=quest_state(meta,None,None,objective="Leave the bedroom and find the next story NPC")
        self.assertEqual(q["task"],"Leave the bedroom and find the next story NPC")
        q=quest_state(meta,None,None,objective="Survey a new native-verified walkable tile")
        self.assertEqual(q["task"],"Leave the bedroom and find the next story NPC")
        # Checkpoint migration from previously overwritten tactical tasks.
        meta["objective_state"]["task"]="Survey a new native-verified walkable tile"
        self.assertEqual(quest_state(meta,None,None,objective="Approach observed warp")["task"],
                         "Find the next verified story interaction or map exit.")

    def test_party_observed_discards_internal_stale_script_wait_objective(self):
        m={}
        quest_state(m,None,[{"hp":12,"max_hp":15}])
        q=quest_state(m,None,None,objective="Allow locked field script or transition to finish without walking")
        self.assertEqual(q["phase"],"explore_and_advance_story")
        self.assertEqual(q["task"],"Find the next verified story interaction or map exit.")
        self.assertEqual(q["task_source"],"campaign_priority_after_party")

    def test_party_acquisition_reopens_native_story_events_once(self):
        from core.jj_unattended import quest_state
        party=[{"hp":20,"max_hp":20}]
        meta={"event_attempts":["43:1:warp:0:4:2","43:1:npc:1:3:7"],
              "event_goal":{"map":[43,1]},"starter_event_retry":[43,1]}
        quest_state(meta,None,party)
        self.assertEqual(meta["event_attempts"],[])
        self.assertEqual(meta["event_attempt_party_count"],1)
        self.assertEqual(meta["prior_event_attempts"][0]["attempts"],
                         ["43:1:warp:0:4:2","43:1:npc:1:3:7"])
        self.assertNotIn("event_goal",meta)
        meta["event_attempts"]=["43:1:warp:0:4:2"]
        quest_state(meta,None,party)
        self.assertEqual(meta["event_attempts"],["43:1:warp:0:4:2"])
        quest_state(meta,None,party+[{"hp":10,"max_hp":20}])
        self.assertEqual(meta["event_attempts"],[])
        self.assertEqual(meta["event_attempt_party_count"],2)

    def test_starter_goal_overrides_repeated_field_recovery_and_yields_after_party(self):
        meta={}
        for _ in range(4):
            q=quest_state(meta,None,None,objective="Escape repeated field cycle using an untried direction")
            self.assertIn("Poké Ball",q["task"])
        q=quest_state(meta,None,[{"hp":12,"max_hp":15}],objective="Find exit")
        self.assertEqual(q["phase"],"explore_and_advance_story")
        self.assertEqual(q["task"],"Find exit")

    def test_quest_notebook_separates_model_hypotheses_from_witnessed_progress(self):
        meta={}
        q=quest_state(meta,None,None,{"fact":"I think the rocket ship sank"},"Find the ship")
        self.assertEqual(q["fact_source"],"model_hypothesis_not_a_verified_story_flag")
        self.assertEqual(q["task_source"],"campaign_priority_pending_native_party_witness")
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
