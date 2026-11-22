import unittest

from core.action_batch import prepare, take, observe, frame_is_safe, invalidate


def screen():
    return bytes((68, 116, 88)) * (240 * 160)


def patch_frame(rgb, x=20, y=20, width=20, height=20):
    b = bytearray(rgb)
    for row in range(y, y + height):
        for col in range(x, x + width):
            k = (row * 240 + col) * 3
            b[k:k+3] = bytes((176, 66, 45))
    return bytes(b)


def proposal(stage="field", buttons=("RIGHT", "RIGHT", "DOWN"), frames=16):
    return {
        "scene": "route",
        "objective": "Advance to the building",
        "actions": [{"button": button, "frames": frames} for button in buttons],
        "observation": {"stage": stage},
        "review": False,
    }


class BatchTests(unittest.TestCase):
    def test_navigation_is_split_but_each_step_is_checkpointed(self):
        d, plan = prepare(proposal(), "vision_compact")
        self.assertEqual(len(d["actions"]), 1)
        self.assertEqual(len(plan["remaining"]), 2)
        before = screen()
        after = patch_frame(before)
        meta = {"action_batch": plan}
        self.assertTrue(observe(meta, before, after))
        second = take(meta, after, allowed=True)
        self.assertEqual(second["actions"], [{"button": "RIGHT", "frames": 16}])
        third_screen = patch_frame(after, 50, 20)
        self.assertTrue(observe(meta, after, third_screen))
        third = take(meta, third_screen, allowed=True)
        self.assertEqual(third["actions"], [{"button": "DOWN", "frames": 16}])
        self.assertNotIn("action_batch", meta)

    def test_battles_menus_and_confirmations_never_batch(self):
        for d, source, opts in (
            (proposal("battle_command"), "vision_rich", {}),
            (proposal("menu"), "vision_rich", {}),
            (proposal(), "vision_rich", {"battle": True}),
            (proposal(), "vision_rich", {"menu": True}),
            (proposal(), "native_battle", {}),
            (proposal(buttons=("RIGHT", "A")), "vision_compact", {}),
            (proposal(frames=120), "vision_compact", {}),
        ):
            single, plan = prepare(d, source, **opts)
            self.assertEqual(single, d)
            self.assertIsNone(plan)

    def test_up_to_ten_navigation_steps_and_no_more(self):
        actions = ("RIGHT",) * 10
        d, plan = prepare(proposal(buttons=actions), "vision_rich")
        self.assertEqual(len(d["actions"]), 1)
        self.assertEqual(len(plan["remaining"]), 9)
        d, plan = prepare(proposal(buttons=actions + ("RIGHT",)), "vision_rich")
        self.assertIsNone(plan)

    def test_scene_change_cancels_queue(self):
        before = screen()
        good = patch_frame(before)
        sudden_battle = bytes((20, 20, 20)) * (240 * 160)
        popup = patch_frame(before, 0, 112, 240, 48)
        self.assertTrue(frame_is_safe(before, good))
        self.assertFalse(frame_is_safe(before, before))
        self.assertFalse(frame_is_safe(before, sudden_battle))
        self.assertFalse(frame_is_safe(before, popup))
        _, plan = prepare(proposal(), "vision_rich")
        meta = {"action_batch": plan}
        self.assertFalse(observe(meta, before, sudden_battle))
        self.assertNotIn("action_batch", meta)

    def test_remote_change_and_stale_screen_abort(self):
        first = screen()
        after = patch_frame(first)
        _, plan = prepare(proposal(), "vision_compact")
        meta = {"action_batch": plan}
        self.assertTrue(observe(meta, first, after))
        self.assertIsNone(take(meta, first, allowed=True))
        self.assertNotIn("action_batch", meta)
        _, plan = prepare(proposal(), "vision_compact")
        meta = {"action_batch": plan}
        self.assertTrue(observe(meta, first, after))
        self.assertIsNone(take(meta, after, allowed=False))
        self.assertNotIn("action_batch", meta)
        invalidate(meta)
        self.assertEqual(meta, {})


if __name__ == "__main__":
    unittest.main()
