"""No-ROM, no-Ollama regressions for isolated native gameplay evaluations."""
import copy
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from core.autoplay import load_progress,save_progress
from core.jj_eval import SCENARIOS,evaluate,main,run_isolated
from core.native_acceptance import engine_hash

A="a"*64
B="b"*64
C="c"*64
D="d"*64


def identity(rom=A,runner=B,model="mock"):
    return {"rom":rom,"runner":runner,"model":model,"goal":"Continue original story"}


def baseline():
    return {"decisions":10,"frames":200,"history":[],
            "last_native_field":{"map":[1,2],"pos":[1,1]},
            "visited_native_maps":[[1,2]],
            "engine_metrics":{"model_calls":7,"model_seconds":150.5,"native":2}}


def event(kind,decision=11,before=A,after=B,**detail):
    row={"kind":kind,"decision":decision,"before":before,"after":after,"source":"native_explore"}
    if detail:row["detail"]=detail
    return row


def result(base=None,events=(),ident=None,profile=True,**extra):
    start=baseline() if base is None else base
    key=identity() if ident is None else ident
    final=copy.deepcopy(start)
    final.update(decisions=start["decisions"]+4,frames=start["frames"]+120)
    final["engine_metrics"]={"model_calls":8,"model_seconds":158.5,"native":5}
    final["native_acceptance"]={"identity":{"rom":key["rom"],
                          "runner":key["runner"],"engine":engine_hash()},
                          "profile_admitted":profile,
                          "counts":{k:999 for k in ("native_step","map_crossing","battle_win","wild_capture")},
                          "events":list(events)}
    final.update(extra)
    return final


class EvidenceScoringTests(unittest.TestCase):
    def test_scenarios_have_only_native_event_goals(self):
        self.assertEqual(set(SCENARIOS),{"leave_current_map","navigation_progress",
                          "win_battle","catch_pokemon","checkpoint_resume"})
        for value in SCENARIOS.values():
            self.assertTrue(value["needs"])
            self.assertTrue(all(v>0 for v in value["needs"].values()))

    def test_map_transition_requires_new_native_witness_not_counter_or_visuals(self):
        base=baseline()
        pretend=result(base,[],screen="unrecognizable",visited_native_maps=[[1,2],[3,4]])
        scored=evaluate("leave_current_map",base,pretend,identity())
        self.assertEqual(scored["result"],"FAIL")
        self.assertEqual(scored["reason"],"required_native_milestone_not_witnessed")
        self.assertEqual(scored["metrics"]["map_crossings"],0)
        verified=result(base,[event("map_crossing",11,**{"from":[1,2],"to":[3,4]})])
        good=evaluate("leave_current_map",base,verified,identity())
        self.assertEqual(good["result"],"PASS")
        self.assertEqual(good["metrics"]["map_crossings"],1)
        self.assertEqual(good["metrics"]["new_maps"],1)
        self.assertEqual(good["metrics"]["decisions"],4)
        self.assertEqual(good["metrics"]["model_calls"],1)
        self.assertEqual(good["metrics"]["model_seconds"],8.0)

    def test_no_farming_same_route_as_new_map(self):
        base=baseline()
        arrivals=[
            event("map_crossing",11,A,B,**{"from":[1,2],"to":[3,4]}),
            event("map_crossing",12,B,C,**{"from":[3,4],"to":[1,2]}),
            event("map_crossing",13,C,D,**{"from":[1,2],"to":[3,4]}),
        ]
        x=evaluate("leave_current_map",base,result(base,arrivals),identity())
        self.assertEqual(x["metrics"]["map_crossings"],3)
        self.assertEqual(x["metrics"]["new_maps"],1)
        self.assertLessEqual(x["metrics"]["score"],130)

    def test_capture_requires_proven_party_growth_event(self):
        base=baseline()
        fake=result(base,[event("native_step")],party_knowledge={"events":[{"kind":"party_slot"}]})
        self.assertEqual(evaluate("catch_pokemon",base,fake,identity())["result"],"FAIL")
        accepted=result(base,[event("wild_capture",11,species=25)])
        self.assertEqual(evaluate("catch_pokemon",base,accepted,identity())["result"],"PASS")
        invalid=result(base,[event("wild_capture",11,species=0)])
        self.assertEqual(evaluate("catch_pokemon",base,invalid,identity())["result"],"FAIL")

    def test_battle_win_and_roundtrip_are_separate_goals(self):
        b=baseline()
        win=result(b,[event("battle_win")])
        self.assertEqual(evaluate("win_battle",b,win,identity())["result"],"PASS")
        self.assertEqual(evaluate("checkpoint_resume",b,win,identity())["result"],"FAIL")
        accepted=result(b,[event("checkpoint_reload",10,**{"ordinal":1}),event("native_step",12,B,C)])
        self.assertEqual(evaluate("checkpoint_resume",b,accepted,identity())["result"],"PASS")
        self.assertEqual(evaluate("navigation_progress",b,accepted,identity())["result"],"FAIL")

    def test_repeated_reload_requires_fresh_ordinal_for_same_decision(self):
        b=baseline()
        current=identity()
        old=event("checkpoint_reload",10,**{"ordinal":2})
        b["native_acceptance"]={"identity":{"rom":current["rom"],
              "runner":current["runner"],"engine":engine_hash()},
              "profile_admitted":True,"events":[old]}
        stale=result(b,[old],ident=current)
        self.assertEqual(evaluate("checkpoint_resume",b,stale,current)["result"],"FAIL")
        fresh=result(b,[old,event("checkpoint_reload",10,**{"ordinal":3}),
                        event("native_step",12,B,C)],ident=current)
        self.assertEqual(evaluate("checkpoint_resume",b,fresh,current)["result"],"PASS")
        # A new engine has reset its ledger; an ordinal of 1 is new even
        # when the source had higher ordinals from the previous engine.
        older=copy.deepcopy(b)
        older["native_acceptance"]["identity"]["engine"]=D
        upgraded=result(older,[event("checkpoint_reload",10,**{"ordinal":1}),
                               event("native_step",12,B,C)],ident=current)
        self.assertEqual(evaluate("checkpoint_resume",older,upgraded,current)["result"],"PASS")
        malformed=result(b,[event("checkpoint_reload",10),event("native_step",12,B,C)],ident=current)
        self.assertEqual(evaluate("checkpoint_resume",b,malformed,current)["result"],"FAIL")

    def test_profile_and_provenance_fail_closed(self):
        b=baseline()
        proof=[event("map_crossing",11,**{"from":[1,2],"to":[3,4]})]
        self.assertEqual(evaluate("leave_current_map",b,result(b,proof,profile=False),identity())["reason"],
                         "native_profile_not_admitted")
        tampered=result(b,proof)
        tampered["native_acceptance"]["identity"]["engine"]=C
        self.assertEqual(evaluate("leave_current_map",b,tampered,identity())["reason"],
                         "native_acceptance_identity_mismatch")
        self.assertEqual(evaluate("leave_current_map",b,result(b,proof),identity(),
                     status="EMULATOR_ERROR")["result"],"FAIL")
        old=result(b,[event("map_crossing",10,**{"from":[1,2],"to":[3,4]})])
        self.assertEqual(evaluate("leave_current_map",b,old,identity())["result"],"FAIL")

    def test_only_valid_map_crossings_are_counted(self):
        b=baseline()
        bad=[event("map_crossing",11,**{"from":[1,2],"to":[1,2]}),
             event("map_crossing",12,**{"from":[1,2],"to":[999,0]}),
             event("map_crossing",13,"invalid",B,**{"from":[1,2],"to":[3,4]})]
        self.assertEqual(evaluate("leave_current_map",b,result(b,bad),identity())["result"],"FAIL")

    def test_coordinate_based_stuck_measurement_not_animated_pixels(self):
        b=baseline()
        history=[
            {"decision":11,"before":A,"after":B,"source":"native_explore",
             "actions":[{"button":"RIGHT","frames":1}],
             "field_after":{"map":[1,2],"pos":[1,1]}},
            {"decision":12,"before":B,"after":C,"source":"native_explore",
             "actions":[{"button":"RIGHT","frames":12}],
             "field_after":{"map":[1,2],"pos":[1,1]}},
            {"decision":13,"before":C,"after":D,"source":"native_explore",
             "actions":[{"button":"UP","frames":1}],
             "field_after":{"map":[1,2],"pos":[1,0]}},
        ]
        x=evaluate("navigation_progress",b,result(b,[],history=history),identity())
        self.assertEqual(x["result"],"FAIL")
        self.assertEqual(x["metrics"]["stuck_ratio"],0.6667)
        self.assertEqual(x["metrics"]["verified_no_progress"],2)
        self.assertTrue(x["metrics"]["audit_limited"])
        y=evaluate("navigation_progress",b,result(b,[],history=[
            {"decision":11,"before":A,"after":D,"source":"vision_compact",
             "actions":[{"button":"LEFT","frames":16}]}]),identity())
        self.assertIsNone(y["metrics"]["stuck_ratio"])

    def test_invalid_interval_rejected(self):
        b=baseline()
        f=result(b,[])
        f["decisions"]=1
        with self.assertRaises(ValueError):evaluate("win_battle",b,f,identity())


class ScratchSafetyTests(unittest.TestCase):
    def setup(self,root):
        live=root/"live";live.mkdir()
        out=root/"evals"
        runner=root/"runner.exe";runner.write_bytes(b"fake runner bytes")
        rom=root/"private.gba";rom.write_bytes(b"private ROM fake bytes")
        sha=hashlib.sha256(rom.read_bytes()).hexdigest()
        model=type("Model",(),{"model":"mock"})()
        ident=identity(rom=sha,runner=hashlib.sha256(runner.read_bytes()).hexdigest())
        meta=baseline()
        save_progress(live/"progress.bin",ident,meta,b"fake native state",bytes(115200))
        return live/"progress.bin",out,runner,rom,sha,model,ident

    def test_run_uses_only_fresh_scratch_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as d:
            cp,out,runner,rom,sha,model,ident=self.setup(Path(d))
            original=cp.read_bytes();locations=[]
            def fake_player(runner_arg,rom_arg,sha_arg,goal,folder,actual_model,**opts):
                locations.append(Path(folder))
                self.assertEqual(sha_arg,sha)
                self.assertNotEqual(Path(folder),cp.parent)
                self.assertEqual(opts["max_decisions"],14)
                copy_meta,state,rgb=load_progress(Path(folder)/"progress.bin",ident)
                self.assertEqual(copy_meta,baseline())
                current=result(copy_meta,[event("map_crossing",11,
                    **{"from":[1,2],"to":[3,4]})],ident=ident)
                opts["report"]("RUNNING",current,rgb)
                self.assertTrue(opts["should_stop"]())
                save_progress(Path(folder)/"progress.bin",ident,current,state,rgb)
                return "STOPPED",current,rgb
            a=run_isolated("leave_current_map",cp,out,runner,rom,sha,
                        ident["goal"],model,budget=4,player=fake_player)
            b=run_isolated("leave_current_map",cp,out,runner,rom,sha,
                        ident["goal"],model,budget=4,player=fake_player)
            self.assertEqual(a["result"],"PASS")
            self.assertTrue(a["original_unchanged"])
            self.assertEqual(a["episode_identity"]["original_checkpoint_sha256"],hashlib.sha256(original).hexdigest())
            self.assertEqual(a["episode_identity"]["model"],"mock")
            self.assertEqual(len(a["episode_identity"]["isolated_checkpoint_sha256"]),64)
            self.assertEqual(cp.read_bytes(),original)
            self.assertEqual(len(set(locations)),2)
            self.assertTrue((locations[0]/"evaluation.json").exists())
            self.assertFalse((cp.parent/"evaluation.json").exists())

    def test_fabricated_success_not_saved_to_isolated_checkpoint_fails(self):
        with tempfile.TemporaryDirectory() as d:
            cp,out,runner,rom,sha,model,ident=self.setup(Path(d))
            def uncommitted_player(runner,rom,sha,goal,folder,model,**opts):
                stored,state,rgb=load_progress(Path(folder)/"progress.bin",ident)
                invented=result(stored,[event("battle_win")],ident=ident)
                return "STOPPED",invented,rgb
            report=run_isolated("win_battle",cp,out,runner,rom,sha,
                           ident["goal"],model,budget=4,player=uncommitted_player)
            self.assertEqual(report["result"],"FAIL")
            self.assertEqual(report["metrics"]["battle_wins"],0)
            self.assertEqual(report["reason"],"returned_state_does_not_match_isolated_checkpoint")

    def test_wrong_checkpoint_identity_cannot_run_or_create_scratch(self):
        with tempfile.TemporaryDirectory() as d:
            cp,out,runner,rom,sha,model,ident=self.setup(Path(d))
            with self.assertRaises(ValueError):
                run_isolated("win_battle",cp,out,runner,rom,sha,
                             "different goal",model,player=lambda *a,**k: None)
            self.assertFalse(out.exists())

    def test_reject_same_or_parent_output_directory(self):
        with tempfile.TemporaryDirectory() as d:
            cp,out,runner,rom,sha,model,ident=self.setup(Path(d))
            for unsafe in (cp.parent,cp.parent.parent,cp.parent/"nested"):
                with self.assertRaises(ValueError):
                    run_isolated("win_battle",cp,unsafe,runner,rom,sha,
                                 ident["goal"],model,player=lambda *a,**k: None)

    def test_bad_sha_or_budget_never_advances_player(self):
        with tempfile.TemporaryDirectory() as d:
            cp,out,runner,rom,sha,model,ident=self.setup(Path(d))
            for invalid in (0,301):
                with self.assertRaises(ValueError):
                    run_isolated("win_battle",cp,out,runner,rom,sha,ident["goal"],
                                 model,budget=invalid,player=lambda *a,**k: None)
            with self.assertRaises(ValueError):
                run_isolated("win_battle",cp,out,runner,rom,A,ident["goal"],
                             model,player=lambda *a,**k: None)
            self.assertFalse(out.exists())

    def test_score_command_validates_inputs_without_running_rom(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cp,out,runner,rom,sha,model,ident=self.setup(root)
            final=result(baseline(),[event("battle_win")],ident=ident)
            later=root/"later.bin"
            save_progress(later,ident,final,b"state",bytes(115200))
            with redirect_stdout(io.StringIO()) as output:
                exit_code=main(["score","--scenario","win_battle","--before",str(cp),
                    "--after",str(later),"--runner",str(runner),"--rom-sha",sha,
                    ])
            self.assertEqual(exit_code,0)
            self.assertEqual(json.loads(output.getvalue())["result"],"PASS")


if __name__=="__main__":
    unittest.main()
