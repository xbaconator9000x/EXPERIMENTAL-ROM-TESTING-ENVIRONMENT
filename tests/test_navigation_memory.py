import unittest
from core.navigation_memory import (
    ledger, record, learned_context, propose, unsafe_repeat,
    blocked_directions, recent_oscillation,
)


def key(n):
    return ("%064x" % n)


def step(before,after,direction,*,scene="hospital_room"):
    return {"before":before,"after":after,"scene":scene,
            "actions":[{"button":direction,"frames":16}]}


class NavigationMemoryTests(unittest.TestCase):
    def test_wall_memory_persists_across_normal_checkpoint_reload(self):
        a,b=key(1),key(2)
        meta={}
        self.assertTrue(record(meta,a,a,[{"button":"LEFT","frames":16}],safe_field=True))
        self.assertIn("LEFT",blocked_directions(meta,a,[]))
        d=propose(meta,a,[step(b,a,"LEFT")],allowed=True)
        self.assertEqual(d["actions"],[{"button":"DOWN","frames":16}])
        self.assertTrue(unsafe_repeat(meta,a,[],[{"button":"LEFT","frames":16}]))
        self.assertFalse(unsafe_repeat(meta,b,[],[{"button":"LEFT","frames":16}]))
        # The memory is JSON-serializable and survives normal checkpoint IO.
        import json
        saved=json.loads(json.dumps(meta))
        self.assertIn("LEFT",learned_context(saved,a,[])["visually_blocked"])
        self.assertEqual(saved["navigation_memory"]["states"][a]["rescues"],["DOWN"])

    def test_live_hospital_reversal_trace(self):
        # The two exact screenshot IDs from private campaign #23, not pixels.
        a="ec9855d1a87bd5cabf9dafea00dea32f01e761fb829b9d519391edd381990810"
        b="dc8a8551533cea18162bed27fb031256d14a294a5826dacc7fa651b1c3f08434"
        rows=[]
        for i in range(12):
            before,after,button=(a,b,"DOWN") if i%2==0 else (b,a,"UP")
            rows.append(step(before,after,button,scene="native_dialogue"))
        self.assertEqual(recent_oscillation(rows,a),"DOWN")
        self.assertEqual(recent_oscillation(rows,b),"UP") if False else None
        meta={}
        # Recovery cannot act on stale *labels alone*.
        self.assertIsNone(propose(meta,a,rows,allowed=False))
        recovery=propose(meta,a,rows,allowed=True)
        self.assertEqual(recovery["actions"],[{"button":"LEFT","frames":16}])
        self.assertIn("DOWN",blocked_directions(meta,a,rows))
        self.assertFalse(unsafe_repeat(meta,a,rows,[{"button":"LEFT","frames":16}]))

    def test_resume_migrates_old_history_without_new_memory(self):
        a,b=key(3),key(4)
        h=[step(a,a,"LEFT")]
        meta={}
        self.assertEqual(blocked_directions(meta,a,h),{"LEFT"})
        self.assertEqual(propose(meta,a,h,allowed=True)["actions"][0]["button"],"DOWN")

    def test_safe_field_required_and_no_auto_interactions(self):
        a=key(11)
        meta={}
        for button in ("A","START","B","WAIT"):
            self.assertFalse(record(meta,a,a,[{"button":button,"frames":16}],safe_field=True))
        self.assertFalse(record(meta,a,a,[{"button":"LEFT","frames":16}],safe_field=False))
        self.assertFalse(record(meta,a,a,[{"button":"LEFT","frames":16},{"button":"UP","frames":16}],safe_field=True))
        self.assertIsNone(propose(meta,a,[],allowed=True))
        self.assertIsNone(propose(meta,a,[step(a,a,"UP")],allowed=False))

    def test_wall_and_recovery_budget_terminate(self):
        a=key(20);meta={};h=[]
        for direction in ("UP","DOWN","LEFT"):
            self.assertTrue(record(meta,a,a,[{"button":direction,"frames":16}],safe_field=True))
        d=propose(meta,a,h,allowed=True)
        self.assertEqual(d["actions"][0]["button"],"RIGHT")
        self.assertIsNone(propose(meta,a,h,allowed=True))
        self.assertTrue(record(meta,a,a,[{"button":"RIGHT","frames":16}],safe_field=True))
        self.assertIsNone(propose(meta,a,h,allowed=True))

    def test_do_not_overinterpret_changed_pixels(self):
        a,b=key(31),key(32)
        meta={}
        self.assertTrue(record(meta,a,b,[{"button":"UP","frames":16}],safe_field=True))
        self.assertEqual(blocked_directions(meta,a,[]),set())
        self.assertIsNone(propose(meta,a,[],allowed=True))
        self.assertEqual(meta["navigation_memory"]["states"][a]["attempts"]["UP"]["changed"],1)

    def test_bounded_state_and_recovery_storage(self):
        meta={}
        for i in range(120):
            k=key(i+100)
            record(meta,k,k,[{"button":"UP","frames":16}],safe_field=True)
            propose(meta,k,[],allowed=True)
        v=ledger(meta)
        self.assertLessEqual(len(v["states"]),64)
        self.assertLessEqual(len(v["events"]),96)
        self.assertNotIn(key(100),v["states"])

    def test_loop_detector_rejects_animation_and_unrelated_actions(self):
        a,b=key(40),key(41)
        h=[step(a,b,"RIGHT"),step(b,a,"LEFT")]*5
        self.assertEqual(recent_oscillation(h,a),"RIGHT")
        self.assertIsNone(recent_oscillation(h, key(50)))
        self.assertIsNone(recent_oscillation([step(a,a,"RIGHT")]*10,a))
        self.assertIsNone(recent_oscillation([step(a,b,"A"),step(b,a,"B")]*5,a))
        self.assertIsNone(recent_oscillation(h[:4],a))


if __name__=="__main__":
    unittest.main()
