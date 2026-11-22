"""End-to-end checkpoint replay with mocked transport, no private ROM bytes.

Tests actual play() selection order: memory -> safe recovery -> native input ->
new checkpoint. Also proves the same persistent field evidence cannot drive
blind recovery when a menu is present.
"""
import hashlib
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from core.autoplay import play, save_progress, digest


class LocalLive:
    def __init__(self,*args):
        self.value=42
    def step(self,button,frames):
        self.value=(self.value+button+frames)%256
    def rgb(self):
        # Nonblank RGB: menu interlock must be tested as a real rendered scene,
        # not short-circuited by the blank/transition detector.
        return bytes((self.value,0,255-self.value))*38400
    def save_state(self):
        return bytes((self.value,))
    def load_state(self,state):
        self.value=state[0]
    def integer(self,*args):
        return 0
    def close(self):
        pass


class LocalAdapter:
    admitted=True
    reason="SCRIPT_OR_FADE_LOCK"
    lock_probe={"script_active":True,"fade_active":False}
    def __init__(self,*args):pass
    def attach(self,live):self.live=live
    def candidate(self,rgb):return None
    def verified_field(self,*args):return False
    def structured(self,*args):return None
    def route_action(self,*args):return None
    def start_route(self,*args):return False
    def observe_move(self,*args):pass


class LocalBattles:
    callbacks=set()
    catalog=None
    field_inventory=None
    def __init__(self,*args):pass
    def snapshot(self,*args):return None
    def summary(self,*args):return None
    def action(self,*args):return None
    def corroborate(self,*args):pass


class LocalMenus:
    bag_ok=False
    party_ok=False
    show_menu=False
    def __init__(self,*args):pass
    def snapshot(self,*args):
        return {"stage":"menu"} if type(self).show_menu else None
    def action(self,*args):return None
    def corroborate(self,*args):pass


class LocalExplorer:
    def __init__(self,*args):pass
    def inspect(self,*args):return None
    def request(self,*args):return False
    def next(self,*args):return None


class LocalAcceptance:
    def __init__(self,*args):pass
    def reload(self,*args):pass
    def witness(self,*args):return None
    def observe(self,*args):pass


class CountingModel:
    model="fake"
    def __init__(self):self.calls=0
    def decide(self,*args):
        self.calls+=1
        return {"scene":"menu","objective":"Observe current screen",
                "actions":[{"button":"A","frames":5}],"review":False}


class NativeRecoveryIntegrationTests(unittest.TestCase):
    def run_sample(self,menu=False):
        rom_sha="a"*64
        initial=bytes((42,0,213))*38400
        screen=digest(initial)
        model=CountingModel()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            runner=root/"runner";runner.write_bytes(b"native fake")
            checkpoint=root/"progress.bin"
            identity={"rom":rom_sha,
                      "runner":hashlib.sha256(runner.read_bytes()).hexdigest(),
                      "goal":"continue story","model":"fake"}
            history=[{"decision":1,"before":screen,"after":screen,
                      "scene":"hospital_room",
                      "actions":[{"button":"LEFT","frames":16}]}]
            meta={"decisions":1,"frames":120,"history":history,
                  "field_proof":{"callback":0x08001235,"directions":["UP"]}}
            save_progress(checkpoint,identity,meta,bytes((42,)),initial)
            with ExitStack() as stack:
                for name,value in (
                    ("Live",LocalLive),("Adapter",LocalAdapter),
                    ("BattleAdapter",LocalBattles),("MenuDriver",LocalMenus),
                    ("Explorer",LocalExplorer),("Acceptance",LocalAcceptance),
                    ("JJ_RELEASES",{rom_sha}),
                ):
                    stack.enter_context(patch("core.autoplay."+name,value))
                stack.enter_context(patch("core.autoplay.try_catalog",return_value=None))
                stack.enter_context(patch("core.autoplay.open_profile",return_value=(None,None)))
                LocalMenus.show_menu=menu
                try:
                    status,result,rgb=play(runner,root/"rom",rom_sha,
                                           "continue story",root,model,max_decisions=2)
                finally:
                    LocalMenus.show_menu=False
            self.assertEqual(status,"BUDGET_REACHED")
            self.assertEqual(result["decisions"],2)
            return result,model.calls

    def test_known_wall_is_rerouted_without_another_llm_call(self):
        meta,calls=self.run_sample(menu=False)
        last=meta["history"][-1]
        self.assertEqual(last["source"],"field_recovery")
        self.assertEqual(last["actions"],[{"button":"DOWN","frames":16}])
        self.assertEqual(calls,0)
        self.assertTrue(last.get("navigation_recovery"))
        self.assertIn("navigation_memory",meta)

    def test_existing_explorer_executes_starter_npc_skill_without_qwen(self):
        from core.firered import Field
        from core.jj_explore import Explorer as ActualExplorer

        class FieldAdapter(LocalAdapter):
            def candidate(self,rgb):
                return (Field((1,2),(1,1),6,6,(0,)*36),
                        0x08001235,{(3,1)})
            def verified_field(self,c,meta):
                return c is not None

        class PartyAcceptance(LocalAcceptance):
            enabled=True
            def read_party(self,live):return []

        class InventoryBattles(LocalBattles):
            def bag(self,live):return {"balls":[],"items":[]}

        class EventExplorer(ActualExplorer):
            def inspect(self,candidate,meta):
                return ([{"kind":"npc","x":3,"y":1,"id":1,"gfx":12},
                         {"kind":"warp","x":4,"y":4,"id":0,"destination":[3,4]}],"RIGHT")

        model=CountingModel()
        sha="a"*64
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            runner=root/"runner";runner.write_bytes(b"native fake")
            with ExitStack() as stack:
                for name,value in (
                    ("Live",LocalLive),("Adapter",FieldAdapter),
                    ("BattleAdapter",InventoryBattles),("MenuDriver",LocalMenus),
                    ("Explorer",EventExplorer),("Acceptance",PartyAcceptance),
                    ("JJ_RELEASES",{sha})
                ):
                    stack.enter_context(patch("core.autoplay."+name,value))
                stack.enter_context(patch("core.autoplay.try_catalog",return_value=None))
                stack.enter_context(patch("core.autoplay.open_profile",return_value=(None,None)))
                status,meta,rgb=play(runner,root/"rom",sha,
                     "Find first story NPC",root,model,max_decisions=1)
        self.assertEqual(status,"BUDGET_REACHED")
        self.assertEqual(model.calls,0)
        last=meta["history"][-1]
        self.assertEqual(last["source"],"native_explore")
        self.assertEqual(last["actions"],[{"button":"RIGHT","frames":1}])
        self.assertEqual(meta["world_model"]["maps"]["1:2"]["event_kinds"],
                         {"npc":1,"warp":1})
        self.assertEqual(meta["world_model"]["edges"],[])
        self.assertNotIn("skill_outcomes",meta["world_model"])

    def test_menu_blocks_all_automatic_navigation_recovery(self):
        meta,calls=self.run_sample(menu=True)
        self.assertEqual(calls,1)
        self.assertEqual(meta["history"][-1]["actions"][0]["button"],"A")
        self.assertNotEqual(meta["history"][-1]["source"],"field_recovery")


if __name__=="__main__":
    unittest.main()
